"""Directors' Library video classification and ephemeral numeric measurement.

``enumerate`` lists every ``video`` entry from the site's public WordPress REST
endpoint, then fetches each entry's public page once to classify the player it
embeds (the REST ``content`` field carries no player markup on this site).
Vimeo and YouTube embeds are recorded as ``unsupported-*`` skip rows and are
never attempted. Only a direct ``.mp4`` on the exact site host, with no query
string, is eligible.

``measure`` downloads eligible files one at a time into a ``TemporaryDirectory``,
measures source-PTS windows, writes a numeric evidence record, and deletes the
bytes in a ``finally``. No cookies, logins, tokens, or access-control bypass.

This is a *site adapter* over :mod:`kumiki_reference_lab.acquisition`: the
allowlisting, bounded download, probing, window measurement, evidence assembly,
atomic writes, resume check, and batch loop all come from the package. This
file holds only the site's endpoint, host allowlist, embed classification,
catalog/index shapes, schema strings, and rights text.
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import sys
import tempfile
import time
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition import (  # noqa: E402
    DIRECT, USER_AGENT, allowlisted_url, allowlisted_video_url, as_int,
    build_video_evidence, download_media, measure_windows, resume_matches,
    run_batch, safe_error, safe_slug, source_metadata, utc_now, write_json_atomic,
)
from kumiki_reference_lab.analyzers.media.inspect import sha256_file  # noqa: E402

SITE_HOST = "directorslibrary.com"
REST_ENDPOINT = f"https://{SITE_HOST}/wp-json/wp/v2/video"
REST_FIELDS = "id,slug,link,title,date,content"
PER_PAGE = 100
PAGE_HOSTS = (SITE_HOST,)
VIDEO_HOSTS = (SITE_HOST,)
VIMEO_HOSTS = ("vimeo.com",)
YOUTUBE_HOSTS = ("youtube.com", "youtube-nocookie.com", "youtu.be")
PROVIDER_PRIORITY = ("direct-mp4", "vimeo", "youtube", "other")
PROVIDER_STATUS = {
    "direct-mp4": "pending-measure",
    "vimeo": "unsupported-vimeo",
    "youtube": "unsupported-youtube",
    "other": "unsupported-other",
    "no-video": "no-video",
}
CATALOG_SCHEMA = "kumiki.directors-library-catalog.v1"
INDEX_SCHEMA = "kumiki.directors-library-index.v1"
VIDEO_SCHEMA = "kumiki.directors-library-video-evidence.v1"
EVIDENCE_STATUS = "sampled-original-source-pts-metrics-not-expert-reviewed"
RIGHTS_BASIS = "user-declared-research-use"
RIGHTS_STATUS = "review-required"
DEFAULT_RIGHTS_NOTE = (
    "operator attests public-page research use; downloaded media is deleted "
    "after numeric source-PTS measurement and is not redistributed")
DEFAULT_OUT_DIR = ROOT / "research" / "analysis" / "directors-library"
MIN_DELAY_SECONDS = 1.5
ATTEMPTS = 4
MAX_CONSECUTIVE_BLOCKS = 3
MAX_BACKOFF_SECONDS = 900
PAGE_BYTE_LIMIT = 4 * 1024 * 1024
REST_BYTE_LIMIT = 8 * 1024 * 1024
LIMITS = [
    "Sampled source-PTS windows only; this is not full-film review.",
    "Numeric display-RGB and cut-candidate proxies are not camera, lens, lighting, editing-intent, or style labels.",
    "No visual style, aesthetic quality, authorship, identity, or creative intent is inferred.",
    "Only a self-hosted direct MP4 on the exact site host is measured; Vimeo and YouTube embeds are never attempted.",
    "Public availability is not a license; rightsStatus remains review-required.",
    "Downloaded media, frames, thumbnails, and audio are never retained.",
]


class RateLimitStop(BaseException):
    """Raised after repeated 429/5xx/transport failures.

    Derives from BaseException so the batch loop's per-item ``except Exception``
    cannot swallow it: the run stops and the partial state already on disk is kept.
    """


# ---------------------------------------------------------------------------
# polite HTTP client (one request at a time, paced, 429/5xx aware)
# ---------------------------------------------------------------------------


def _lower_headers(headers: Any) -> dict[str, str]:
    if headers is None:
        return {}
    return {str(key).lower(): str(value) for key, value in headers.items()}


def _allowlisted_without_query(url: str) -> str:
    """Engine allowlist check on the path; REST query parameters are ours, not the URL's."""
    parts = urlsplit(url)
    return allowlisted_url(parts._replace(query="", fragment="").geturl(),
                           allowed_hosts=PAGE_HOSTS)


def _backoff_seconds(headers: dict[str, str], attempt: int) -> float:
    retry_after = headers.get("retry-after", "").strip()
    if retry_after.isdigit():
        return float(min(int(retry_after), MAX_BACKOFF_SECONDS))
    return float(min(60 * 2 ** attempt, MAX_BACKOFF_SECONDS))


class Client:
    """Serial GET client: paced by ``delay + jitter``, honours Retry-After."""

    def __init__(
        self, *, delay_seconds: float = MIN_DELAY_SECONDS,
        jitter_seconds: float = 0.5, timeout: float = 30.0,
        opener: Callable[..., Any] = urlopen, sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        if not isinstance(delay_seconds, (int, float)) or delay_seconds < MIN_DELAY_SECONDS:
            raise ValueError(f"delay must be at least {MIN_DELAY_SECONDS} seconds")
        if not isinstance(jitter_seconds, (int, float)) or jitter_seconds < 0:
            raise ValueError("jitter must be a non-negative number")
        self.delay = float(delay_seconds)
        self.jitter = float(jitter_seconds)
        self.timeout = timeout
        self.opener = opener
        self.sleep = sleep
        self.clock = clock
        self.uniform = uniform
        self.blocks = 0
        self._last: float | None = None

    def _pace(self) -> None:
        if self._last is not None:
            due = self._last + self.delay + self.uniform(0.0, self.jitter)
            wait = due - self.clock()
            if wait > 0:
                self.sleep(wait)

    def _request(self, url: str, *, accept: str, limit: int) -> tuple[int, dict[str, str], bytes]:
        request = Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
        with self.opener(request, timeout=self.timeout) as response:
            _allowlisted_without_query(response.geturl())
            status = int(getattr(response, "status", 200) or 200)
            headers = _lower_headers(getattr(response, "headers", None))
            body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError("response exceeded the bounded size limit")
        return status, headers, body

    def get(self, url: str, *, accept: str, limit: int) -> tuple[int, dict[str, str], bytes]:
        """Return (status, lowercased headers, body); 404 yields an empty body."""
        _allowlisted_without_query(url)
        for attempt in range(ATTEMPTS):
            self._pace()
            try:
                status, headers, body = self._request(url, accept=accept, limit=limit)
            except HTTPError as error:
                status, headers, body = error.code, _lower_headers(error.headers), b""
            except (URLError, OSError):  # includes socket timeouts
                status, headers, body = None, {}, b""
            finally:
                self._last = self.clock()
            if status is None or status == 429 or status >= 500:
                self.blocks += 1
                if self.blocks >= MAX_CONSECUTIVE_BLOCKS:
                    raise RateLimitStop(
                        f"stopped after {self.blocks} consecutive 429/5xx/transport failures")
                self.sleep(_backoff_seconds(headers, attempt))
                continue
            self.blocks = 0
            if status == 404:
                return status, headers, b""
            if status != 200:
                raise ValueError(f"unexpected HTTP {status}")
            return status, headers, body
        raise RateLimitStop("retries exhausted after repeated 429/5xx responses")


# ---------------------------------------------------------------------------
# REST enumeration
# ---------------------------------------------------------------------------


def _rest_entry(item: object) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("REST video item must be an object")
    entry_id = as_int(item.get("id"))
    if entry_id is None:
        raise ValueError("REST video item has no numeric id")
    title = item.get("title") if isinstance(item.get("title"), dict) else {}
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    rendered = str(content.get("rendered") or "")
    return {
        "id": entry_id,
        "slug": str(item.get("slug") or ""),
        "title": html.unescape(str(title.get("rendered") or "")).strip(),
        "date": str(item.get("date") or "") or None,
        "link": str(item.get("link") or ""),
        "restContentMediaTag": bool(re.search(r"<(iframe|video|embed)\b", rendered, re.I)),
    }


def fetch_rest_entries(
    client: Client, *, log: Callable[[str], None] = print,
) -> tuple[list[dict[str, Any]], int | None]:
    """Page through every ``video`` entry; return (entries, X-WP-Total)."""
    entries: list[dict[str, Any]] = []
    total: int | None = None
    pages: int | None = None
    page = 1
    while True:
        query = urlencode({"per_page": PER_PAGE, "page": page, "_fields": REST_FIELDS})
        _, headers, body = client.get(
            f"{REST_ENDPOINT}?{query}", accept="application/json", limit=REST_BYTE_LIMIT)
        if pages is None:
            pages = as_int(headers.get("x-wp-totalpages"))
            total = as_int(headers.get("x-wp-total"))
        try:
            payload = json.loads(body)
        except ValueError:
            raise ValueError("REST response was not valid JSON") from None
        if not isinstance(payload, list):
            raise ValueError("REST response was not a list")
        entries.extend(_rest_entry(item) for item in payload)
        log(f"rest page {page}/{pages}: {len(payload)} entries (total so far {len(entries)})")
        if not payload or pages is None or page >= pages:
            return entries, total
        page += 1


# ---------------------------------------------------------------------------
# embed classification (entry page)
# ---------------------------------------------------------------------------


class _MediaRefs(HTMLParser):
    """Collect player/media references: iframe, embed, object, video, source, og:video."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): (value or "").strip() for key, value in attrs}
        if tag in ("iframe", "embed", "video", "source"):
            src = values.get("src") or values.get("data-src")
            if src:
                self.refs.append((tag, src))
        elif tag == "object" and values.get("data"):
            self.refs.append((tag, values["data"]))
        elif tag == "meta" and values.get("content"):
            name = (values.get("property") or values.get("name") or "").lower()
            if name.startswith("og:video"):
                self.refs.append(("meta-og-video", values["content"]))


def _host_in(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)


def classify_ref(raw: str, page_url: str) -> tuple[str, str | None]:
    """Return (provider, eligible video URL or None) for one media reference."""
    absolute = urljoin(page_url, html.unescape(raw))
    try:
        parsed = urlsplit(absolute)
    except ValueError:
        return "other", None
    host = (parsed.hostname or "").lower()
    if _host_in(host, VIMEO_HOSTS):
        return "vimeo", None
    if _host_in(host, YOUTUBE_HOSTS):
        return "youtube", None
    if parsed.path.lower().endswith(".mp4"):
        try:
            allowlisted_video_url(absolute, allowed_hosts=VIDEO_HOSTS)
        except ValueError:
            return "other", None
        return "direct-mp4", absolute
    return "other", None


def classify_page(page_html: str, page_url: str) -> dict[str, Any]:
    """Classify one entry page's own player embeds by provider."""
    parser = _MediaRefs()
    parser.feed(page_html)
    parser.close()
    tags: set[str] = set()
    found: set[str] = set()
    video_url: str | None = None
    for tag, raw in parser.refs:
        provider, candidate = classify_ref(raw, page_url)
        tags.add(f"{tag}:{provider}")
        found.add(provider)
        if provider == "direct-mp4" and video_url is None:
            video_url = candidate
    provider = next((name for name in PROVIDER_PRIORITY if name in found), "no-video")
    return {
        "provider": provider,
        "eligible": provider == "direct-mp4",
        "videoUrl": video_url if provider == "direct-mp4" else None,
        "embedTags": sorted(tags),
    }


def classify_entry(client: Client, entry: dict[str, Any]) -> dict[str, Any]:
    """Fetch one entry page once and classify it; failures become a row, not a crash."""
    try:
        status, _, body = client.get(entry["link"], accept="text/html", limit=PAGE_BYTE_LIMIT)
    except RateLimitStop:
        raise
    except ValueError as error:
        return {"provider": "unclassified", "eligible": False, "videoUrl": None,
                "embedTags": [], "pageHttpStatus": None,
                "classifyError": safe_error(error, limit=200)}
    if status == 404:
        return {"provider": "unclassified", "eligible": False, "videoUrl": None,
                "embedTags": [], "pageHttpStatus": status,
                "classifyError": "entry page not found"}
    result = classify_page(body.decode("utf-8", "replace"), entry["link"])
    result["pageHttpStatus"] = status
    return result


# ---------------------------------------------------------------------------
# catalog, index
# ---------------------------------------------------------------------------


def _load_cache(path: Path) -> dict[int, dict[str, Any]]:
    cache: dict[int, dict[str, Any]] = {}
    if not path.exists():
        return cache
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            cache[int(row["id"])] = row["classification"]
    return cache


def build_catalog(
    entries: list[dict[str, Any]], classifications: dict[int, dict[str, Any]], *,
    total: int | None, endpoint: str = REST_ENDPOINT, retrieved_at: str | None = None,
) -> dict[str, Any]:
    rows = []
    for entry in entries:
        verdict = classifications[entry["id"]]
        row = {key: entry[key] for key in ("id", "slug", "title", "date", "link",
                                           "restContentMediaTag")}
        row.update({
            "provider": verdict["provider"], "eligible": verdict["eligible"],
            "embedTags": verdict["embedTags"],
            "pageHttpStatus": verdict.get("pageHttpStatus"),
        })
        if verdict.get("videoUrl"):
            row["videoUrl"] = verdict["videoUrl"]
        if verdict.get("classifyError"):
            row["classifyError"] = verdict["classifyError"]
        rows.append(row)
    counts = Counter(row["provider"] for row in rows)
    return {
        "schemaVersion": CATALOG_SCHEMA,
        "retrievedAt": retrieved_at or utc_now(),
        "endpoint": endpoint,
        "restTotal": total,
        "entryCount": len(rows),
        "eligibleCount": sum(1 for row in rows if row["eligible"]),
        "restContentMediaTagCount": sum(1 for row in rows if row["restContentMediaTag"]),
        "providerCounts": dict(sorted(counts.items())),
        "entries": rows,
    }


def _measured_ids(out_dir: Path) -> dict[int, str]:
    found: dict[int, str] = {}
    folder = out_dir / "videos"
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        found[int(payload["id"])] = path.relative_to(out_dir).as_posix()
    return found


def build_index(
    catalog: dict[str, Any], *, measured: dict[int, str],
    failures: dict[int, str] | None = None, catalog_sha256: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """One row per catalog entry with a single status from the fixed vocabulary."""
    failed = failures or {}
    rows: list[dict[str, Any]] = []
    for entry in catalog["entries"]:
        entry_id, provider = entry["id"], entry["provider"]
        row = {"id": entry_id, "slug": entry["slug"], "title": entry["title"],
               "provider": provider}
        if entry_id in measured:
            row.update(status="measured", recordPath=measured[entry_id])
        elif entry_id in failed or provider == "unclassified":
            row.update(status="failed",
                       reason=failed.get(entry_id) or entry.get("classifyError", ""))
        else:
            row["status"] = PROVIDER_STATUS.get(provider, "failed")
            if provider in ("vimeo", "youtube"):
                row["reason"] = f"{provider} embed: excluded by policy, never attempted"
        rows.append(row)
    return {
        "schemaVersion": INDEX_SCHEMA,
        "generatedAt": generated_at or utc_now(),
        "catalogSha256": catalog_sha256,
        "entryCount": len(rows),
        "counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "providerCounts": dict(sorted(Counter(row["provider"] for row in rows).items())),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# enumerate
# ---------------------------------------------------------------------------


def run_enumerate(
    out_dir: Path, *, limit: int | None = None, delay_seconds: float = MIN_DELAY_SECONDS,
    jitter_seconds: float = 0.5, refresh: bool = False, client: Client | None = None,
    log: Callable[[str], None] = print,
) -> int:
    """Write catalog.json and index.json; classification is cached for resume."""
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit must be a positive integer")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = client or Client(delay_seconds=delay_seconds, jitter_seconds=jitter_seconds)
    cache_path = out_dir / ".classify-cache.jsonl"
    if refresh and cache_path.exists():
        cache_path.unlink()
    cache = _load_cache(cache_path)
    entries, total = fetch_rest_entries(client, log=log)
    unique: dict[int, dict[str, Any]] = {}
    for entry in entries:
        unique.setdefault(entry["id"], entry)
    entries = list(unique.values())
    if limit is not None:
        entries = entries[:limit]
    if total is not None and total != len(unique):
        log(f"warning: REST total {total} differs from fetched {len(unique)}")
    classifications: dict[int, dict[str, Any]] = {}
    with cache_path.open("a", encoding="utf-8") as cache_file:
        for position, entry in enumerate(entries, start=1):
            verdict = cache.get(entry["id"])
            if verdict is None:
                verdict = classify_entry(client, entry)
                cache_file.write(json.dumps(
                    {"id": entry["id"], "classification": verdict}) + "\n")
                cache_file.flush()
            classifications[entry["id"]] = verdict
            if position % 100 == 0 or position == len(entries):
                log(f"classified {position}/{len(entries)}")
    catalog = build_catalog(entries, classifications, total=total)
    catalog_path = out_dir / "catalog.json"
    write_json_atomic(catalog_path, catalog)
    index = build_index(catalog, measured=_measured_ids(out_dir),
                        catalog_sha256=sha256_file(catalog_path))
    write_json_atomic(out_dir / "index.json", index)
    if limit is None and cache_path.exists():
        cache_path.unlink()
    log(f"entries={catalog['entryCount']} providers={catalog['providerCounts']} "
        f"index={out_dir / 'index.json'}")
    return 0


# ---------------------------------------------------------------------------
# measure
# ---------------------------------------------------------------------------


def build_video_record(
    entry: dict[str, Any], *, source: dict[str, Any], coverage: dict[str, Any],
    windows: list[dict[str, Any]], method: str, rights_note: str,
) -> dict[str, Any]:
    """Merge site identity around the package's neutral evidence payload."""
    evidence = build_video_evidence(
        source=source, coverage=coverage, windows=windows, method=method,
        provider=str(entry["provider"]), video_url=entry.get("videoUrl"),
        rights_basis=RIGHTS_BASIS, rights_note=rights_note,
        schema_version=VIDEO_SCHEMA, evidence_status=EVIDENCE_STATUS,
        limits=LIMITS, rights_status=RIGHTS_STATUS)
    return {"schemaVersion": VIDEO_SCHEMA, "id": entry["id"], "slug": entry["slug"],
            "title": entry["title"], "date": entry["date"], "link": entry["link"],
            "provider": entry["provider"], **evidence}


def collect_one(
    entry: dict[str, Any], out_dir: Path, *, windows: int = 4,
    window_seconds: int = 10, max_duration_seconds: float = 600.0,
    max_file_bytes: int = 400 * 1024 * 1024, rights_note: str = DEFAULT_RIGHTS_NOTE,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe", download_timeout: float = 360.0,
) -> dict[str, Any]:
    """Download -> measure -> write record; the scratch directory is always deleted."""
    if entry.get("provider") != "direct-mp4" or not entry.get("eligible"):
        raise ValueError("entry is not an eligible self-hosted MP4")
    url = allowlisted_video_url(entry.get("videoUrl"), allowed_hosts=VIDEO_HOSTS)
    slug = safe_slug(entry.get("slug"))
    record_path = out_dir / "videos" / f"{slug}.json"
    with tempfile.TemporaryDirectory(prefix="kumiki-directors-library-") as scratch:
        media_dir = Path(scratch) / "media"
        media_dir.mkdir()
        path, method = download_media(
            url, DIRECT, media_dir, allowed_hosts=VIDEO_HOSTS,
            max_bytes=max_file_bytes, ffmpeg=ffmpeg, ffprobe=ffprobe,
            timeout=download_timeout, max_duration_seconds=max_duration_seconds)
        source = source_metadata(path, ffprobe=ffprobe)
        if source["durationSeconds"] > max_duration_seconds:
            raise ValueError("source exceeds the bounded duration budget")
        coverage, measured = measure_windows(
            path, duration_seconds=source["durationSeconds"], window_count=windows,
            window_seconds=window_seconds, image_translation=False,
            ffmpeg=ffmpeg, ffprobe=ffprobe)
        record = build_video_record(
            entry, source=source, coverage=coverage, windows=measured,
            method=method, rights_note=rights_note)
        write_json_atomic(record_path, record)
        return record


def run_measure(
    catalog_path: Path, *, out_dir: Path, limit: int | None = None,
    resume: bool = True, delay_seconds: float = MIN_DELAY_SECONDS,
    acknowledge_rights: bool = False, log: Callable[[str], None] = print,
    **video_options: Any,
) -> int:
    if acknowledge_rights is not True:
        raise ValueError(
            "explicit --acknowledge-rights attestation is required: public "
            "availability is not a license, and each downloaded file is deleted "
            "after numeric measurement")
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < MIN_DELAY_SECONDS:
        raise ValueError(f"delay must be at least {MIN_DELAY_SECONDS} seconds")
    catalog_path, out_dir = Path(catalog_path), Path(out_dir)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog.get("schemaVersion") != CATALOG_SCHEMA:
        raise ValueError("unsupported catalog schema")
    catalog_sha = sha256_file(catalog_path)
    eligible = [entry for entry in catalog["entries"] if entry.get("eligible")]
    if limit is not None:
        eligible = eligible[:limit]
    failures: dict[int, str] = {}
    (out_dir / "videos").mkdir(parents=True, exist_ok=True)

    def skip_reason(entry: dict[str, Any]) -> str | None:
        if not resume:
            return None
        record = out_dir / "videos" / f"{safe_slug(entry.get('slug'))}.json"
        return "resume-existing-record" if resume_matches(record, entry["id"]) else None

    def index_for(_records: list, _skips: list, _failed: list) -> dict[str, Any]:
        return build_index(catalog, measured=_measured_ids(out_dir), failures=failures,
                           catalog_sha256=catalog_sha)

    def report(position: int, total: int, status: str, label: str, text: str) -> None:
        print(f"[{position}/{total}] {status} {label} {text}".rstrip(), flush=True)

    def failure_row(entry: dict[str, Any], reason: str) -> dict[str, Any]:
        failures[entry["id"]] = reason
        return {"id": entry["id"], "slug": entry["slug"], "reason": reason}

    blocks = {"consecutive": 0}

    def run_one(entry: dict[str, Any]) -> dict[str, Any]:
        try:
            record = collect_one(entry, out_dir, **video_options)
        except HTTPError as error:
            if error.code == 429 or error.code >= 500:
                blocks["consecutive"] += 1
                if blocks["consecutive"] >= MAX_CONSECUTIVE_BLOCKS:
                    raise RateLimitStop(
                        f"stopped after {blocks['consecutive']} consecutive "
                        "429/5xx download responses") from None
            raise
        blocks["consecutive"] = 0
        return record

    outcome = run_batch(
        eligible,
        run_one=run_one,
        index_path=out_dir / "index.json",
        build_index=index_for,
        summary_row=lambda record: {"id": record["id"], "slug": record["slug"]},
        skip_row=lambda entry, reason: {"id": entry["id"], "slug": entry["slug"],
                                        "reason": reason},
        failure_row=failure_row,
        describe=lambda entry: str(entry["slug"]),
        skip_reason=skip_reason,
        error_text=lambda error: safe_error(error, redact=(str(out_dir),)),
        progress=report, jobs=1, delay_seconds=delay_seconds)
    log(f"measured={outcome.measured} skipped={outcome.skipped} "
        f"failed={outcome.failed} attempted={outcome.attempted} "
        f"elapsed={outcome.elapsed_seconds:.1f}s index={out_dir / 'index.json'}")
    log("all downloaded media was deleted; only numeric evidence and metadata remain")
    return 1 if outcome.attempted and not outcome.measured and not _measured_ids(out_dir) else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Directors' Library video classification and ephemeral "
                    "numeric measurement (public, self-hosted MP4 only)")
    sub = parser.add_subparsers(dest="command", required=True)
    enumerate_cmd = sub.add_parser(
        "enumerate",
        help="list every video entry, classify each entry page's player once, "
             "and write catalog.json + index.json (no media downloaded)")
    enumerate_cmd.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    enumerate_cmd.add_argument(
        "--limit", type=int, default=None,
        help="trial runs only: classify the first N entries; use a scratch "
             "--out-dir so the real catalog is not overwritten")
    enumerate_cmd.add_argument(
        "--delay-seconds", type=float, default=MIN_DELAY_SECONDS,
        help=f"pause between requests, at least {MIN_DELAY_SECONDS} s (default %(default)s)")
    enumerate_cmd.add_argument("--jitter-seconds", type=float, default=0.5,
                               help="random extra pause per request (default %(default)s)")
    enumerate_cmd.add_argument("--refresh", action="store_true",
                               help="ignore the classification cache")
    measure = sub.add_parser(
        "measure",
        help="download each eligible self-hosted MP4 one at a time, measure "
             "source-PTS windows, write evidence, delete the media")
    measure.add_argument("--catalog", type=Path, default=None,
                         help="catalog JSON (default: <out-dir>/catalog.json)")
    measure.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    measure.add_argument("--limit", type=int, default=None,
                         help="trial runs only: measure at most N eligible entries")
    measure.add_argument("--acknowledge-rights", action="store_true",
                         help="required attestation of user-declared research use")
    measure.add_argument("--rights-note", default=DEFAULT_RIGHTS_NOTE)
    group = measure.add_mutually_exclusive_group()
    group.add_argument("--resume", dest="resume", action="store_true", default=True)
    group.add_argument("--refresh", dest="resume", action="store_false")
    measure.add_argument("--delay-seconds", type=float, default=MIN_DELAY_SECONDS,
                         help=f"pause (plus equal jitter) between videos, at least {MIN_DELAY_SECONDS} s")
    measure.add_argument("--windows", type=int, default=4)
    measure.add_argument("--window-seconds", type=int, default=10)
    measure.add_argument("--max-duration-seconds", type=float, default=600.0)
    measure.add_argument("--max-file-bytes", type=int, default=400 * 1024 * 1024)
    measure.add_argument("--ffmpeg", default="ffmpeg")
    measure.add_argument("--ffprobe", default="ffprobe")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "enumerate":
            return run_enumerate(
                args.out_dir, limit=args.limit, delay_seconds=args.delay_seconds,
                jitter_seconds=args.jitter_seconds, refresh=args.refresh)
        if args.command == "measure":
            catalog = args.catalog or (Path(args.out_dir) / "catalog.json")
            return run_measure(
                catalog, out_dir=args.out_dir, limit=args.limit,
                resume=args.resume, delay_seconds=args.delay_seconds,
                acknowledge_rights=args.acknowledge_rights,
                rights_note=args.rights_note, windows=args.windows,
                window_seconds=args.window_seconds,
                max_duration_seconds=args.max_duration_seconds,
                max_file_bytes=args.max_file_bytes, ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe)
    except RateLimitStop as error:
        print(f"stopped: {error}. Partial state is on disk; rerun later to resume.",
              file=sys.stderr)
        return 3
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
