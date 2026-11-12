"""Enumerate and ephemerally measure public STASH post videos (site adapter).

``enumerate`` walks the public WordPress REST posts endpoint, classifies each
post's video embed by host, and writes ``catalog.json`` and ``index.json``.
``measure`` downloads only self-hosted direct MP4 files on the exact allowlisted
site host, measures sampled source-PTS windows, writes one numeric record per
video, and deletes all media in a ``finally`` block.

Vimeo (including ``vimeocdn.com`` signed playback URLs) and YouTube are recorded
as ``unsupported-*`` skip rows and never requested. Paywalled or gated posts are
``unsupported-gated``. No login, cookie, trial, or access-control bypass exists.

This is a *site adapter*: every mechanic (allowlisting, bounded download, probing,
window measurement, evidence assembly, atomic writes, batch loop) comes from
:mod:`kumiki_reference_lab.acquisition`. Site knowledge (endpoint, host
allowlist, provider vocabulary, schema strings, rights text) lives only here.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import SplitResult, unquote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition import (  # noqa: E402
    DIRECT, MAX_WINDOWS, MAX_WINDOW_SECONDS, USER_AGENT, as_text, build_video_evidence,
    download_media, finite_float, measure_windows, resume_matches as _resume_matches,
    run_batch, safe_error, safe_slug, source_metadata, utc_now, write_json_atomic,
    allowlisted_video_url,
)
from kumiki_reference_lab.analyzers.media.inspect import sha256_file  # noqa: E402

SITE_ORIGIN = "https://www.stashmedia.tv"
ENDPOINT = f"{SITE_ORIGIN}/wp-json/wp/v2/posts"
PAGE_SIZE = 100
CATALOG_SCHEMA = "kumiki.stash-catalog.v1"
INDEX_SCHEMA = "kumiki.stash-index.v1"
VIDEO_SCHEMA = "kumiki.stash-video-evidence.v1"
RIGHTS_BASIS = "user-declared-research-use"
RIGHTS_STATUS = "review-required"
EVIDENCE_STATUS = "sampled-original-source-pts-metrics-not-expert-reviewed"
DEFAULT_RIGHTS_NOTE = (
    "operator attests public-page research use; downloaded media is deleted "
    "after numeric source-PTS measurement and is not redistributed")
# Exact host allowlist. Only the host observed on the site's own posts.
VIDEO_HOSTS = ("www.stashmedia.tv",)
ALLOWED_MEDIA_SUFFIXES = (".mp4",)
MEDIA_SUFFIXES = (".mp4", ".webm", ".m4v", ".mov", ".m3u8")
GATE_PATHS = ("/subscribe", "/login", "/trial", "/my-account", "/membership")
STATUSES = ("measured", "unsupported-vimeo", "unsupported-youtube",
            "unsupported-gated", "unsupported-host", "no-video", "failed",
            "not-attempted")
DEFAULT_OUT_DIR = ROOT / "research" / "analysis" / "stash"
_RETRYABLE_STATUS = 429
_MAX_PAGE_BYTES = 8_000_000
_MAX_RETRIES = 4
_RETRY_CAP_SECONDS = 300.0

LIMITS = [
    "Sampled source-PTS windows only; this is not full-film review.",
    "Numeric display-RGB and cut-candidate proxies are not camera, lens, lighting, editing-intent, or style labels.",
    "No visual style, aesthetic quality, authorship, identity, or creative intent is inferred.",
    "Public availability is not a license; rightsStatus remains review-required.",
    "Downloaded media, frames, thumbnails, and audio are never retained.",
    "Catalog metadata is taken from the site's public WordPress REST posts and is not independently verified.",
]

_ATTR_URL = re.compile(
    r"""(?:src|href|data-src|data-video|data-url|data-mp4)\s*=\s*["']([^"'\s]+)["']""",
    re.IGNORECASE)
_BARE_URL = re.compile(r"""https?://[^\s"'<>\\]+""", re.IGNORECASE)
_YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com", "ytimg.com")
_VIMEO_HOSTS = ("vimeo.com", "vimeocdn.com")


def _parse(url: str) -> SplitResult | None:
    """Parse one URL, or return None when the markup holds an unparsable string."""
    try:
        return urlsplit(url)
    except ValueError:
        return None


def _host(url: str) -> str:
    parsed = _parse(url)
    try:
        return (parsed.hostname or "").lower() if parsed else ""
    except ValueError:
        return ""


def _under(host: str, domains: Iterable[str]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _urls_in(content: str) -> list[str]:
    found = [html.unescape(match) for match in _ATTR_URL.findall(content)]
    found += [html.unescape(match).rstrip(".,;)") for match in _BARE_URL.findall(content)]
    return [url for url in dict.fromkeys(found)
            if url.lower().startswith("http") and _parse(url) is not None]


def classify_content(content: str) -> dict[str, Any]:
    """Classify one post's embedded video from its REST ``content.rendered`` markup.

    Returns neutral fields only: ``provider`` (the primary, in precedence order),
    ``providers`` (all observed), ``embedHosts`` (hostnames), ``eligible`` and
    ``eligibilityReason``, plus ``gated``. The media URL is returned only when
    it is eligible.
    """
    urls = _urls_in(content or "")
    hosts = sorted({host for host in (_host(url) for url in urls) if host})
    providers: list[str] = []
    media: list[str] = []
    gated = False
    for url in urls:
        host, path = _host(url), _parse(url).path.lower()
        if _under(host, _VIMEO_HOSTS):
            providers.append("vimeo")
        elif _under(host, _YOUTUBE_HOSTS):
            providers.append("youtube")
        elif path.endswith(MEDIA_SUFFIXES):
            media.append(url)
        if _under(host, (urlsplit(SITE_ORIGIN).hostname or "",)) and any(
                path.startswith(gate) for gate in GATE_PATHS):
            gated = True
    providers = sorted(set(providers))
    if "vimeo" in providers:
        return _result("vimeo", providers, hosts, gated, None, "vimeo embed or link")
    if "youtube" in providers:
        return _result("youtube", providers, hosts, gated, None, "youtube embed or link")
    if media:
        eligible_url, reason = _eligible_media(media)
        if eligible_url:
            return _result("direct-mp4", ["direct-mp4"], hosts, gated, eligible_url,
                           "self-hosted direct mp4 on allowlisted host")
        return _result("self-hosted-other", ["self-hosted-other"], hosts, gated, None,
                       reason)
    if gated:
        return _result("gated", [], hosts, True, None,
                       "subscription, login or trial link without an embed")
    return _result("none", [], hosts, False, None, "no video embed found")


def _eligible_media(media: list[str]) -> tuple[str | None, str]:
    """Return the first direct-MP4 URL on the exact allowlisted host, or a reason."""
    reasons: list[str] = []
    for url in media:
        parsed = _parse(url)
        if not parsed.path.lower().endswith(ALLOWED_MEDIA_SUFFIXES):
            reasons.append("non-mp4 media (hls/webm/mov) is out of scope")
            continue
        if parsed.query or parsed.fragment:
            reasons.append("media URL carries a query or fragment")
            continue
        try:
            return allowlisted_video_url(url, allowed_hosts=VIDEO_HOSTS), ""
        except ValueError as error:
            reasons.append(f"media host rejected: {safe_error(error)}")
    return None, "; ".join(dict.fromkeys(reasons)) or "media not allowlisted"


def _result(provider: str, providers: list[str], hosts: list[str], gated: bool,
            video_url: str | None, reason: str) -> dict[str, Any]:
    return {"provider": provider, "providers": providers, "embedHosts": hosts,
            "gated": gated, "eligible": video_url is not None,
            "eligibilityReason": reason, "videoUrl": video_url}


def _status_for(provider: str) -> str:
    return {"vimeo": "unsupported-vimeo", "youtube": "unsupported-youtube",
            "gated": "unsupported-gated", "self-hosted-other": "unsupported-host",
            "none": "no-video"}.get(provider, "not-attempted")


def _retry_after(headers: dict[str, str], attempt: int) -> float:
    raw = headers.get("retry-after", "")
    if raw.strip().isdigit():
        return min(float(raw), _RETRY_CAP_SECONDS)
    return min(5.0 * (2 ** attempt), _RETRY_CAP_SECONDS)


def _get_bytes(url: str, *, accept: str, timeout: float = 45.0,
               sleep: Callable[[float], None] = time.sleep) -> tuple[bytes, dict[str, str]]:
    """GET one public URL with bounded retries on 429 (Retry-After) and 5xx."""
    last: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        request = Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
        headers: dict[str, str] = {}
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(_MAX_PAGE_BYTES + 1)
                headers = {key.lower(): value for key, value in response.headers.items()}
        except HTTPError as error:
            headers = {key.lower(): value for key, value in (error.headers or {}).items()}
            if error.code != _RETRYABLE_STATUS and error.code < 500:
                raise ValueError(f"site refused the request (HTTP {error.code})") from None
            last = error
        except (URLError, TimeoutError, OSError) as error:
            last = error
        else:
            if len(raw) > _MAX_PAGE_BYTES:
                raise ValueError("response exceeded the expected size limit")
            return raw, headers
        if attempt + 1 < _MAX_RETRIES:
            sleep(_retry_after(headers, attempt))
    raise RuntimeError(f"request failed after bounded retries (last: {last})") from last


def fetch_page(url: str, *, timeout: float = 45.0,
               sleep: Callable[[float], None] = time.sleep) -> tuple[Any, dict[str, str]]:
    """GET one REST page and parse it as JSON."""
    raw, headers = _get_bytes(url, accept="application/json", timeout=timeout, sleep=sleep)
    try:
        return json.loads(raw), headers
    except (ValueError, UnicodeDecodeError):
        raise ValueError("REST page was not valid JSON") from None


def fetch_html(url: str, *, timeout: float = 60.0,
               sleep: Callable[[float], None] = time.sleep) -> str:
    """GET one public post page as text (only its single-post video block is read)."""
    raw, _ = _get_bytes(url, accept="text/html", timeout=timeout, sleep=sleep)
    return raw.decode("utf-8", "replace")


POSTVID_CLASS = "postvid_single"
LINK_FIELDS = ("provider", "providers", "embedHosts", "eligible", "eligibilityReason", "videoUrl")


def main_video_block(page_html: str) -> str | None:
    """Return the markup of the single-post video container, or None when absent.

    STASH renders a post's main player in a ``postvid_single`` container that is
    not part of the REST ``content.rendered`` field. Other page regions (nav,
    footer, related posts) are deliberately outside this block.
    """
    start = page_html.find(f'class="{POSTVID_CLASS}"')
    if start < 0:
        return None
    end = page_html.find("</div>", start)
    if end < 0:
        end = start + 4000
    return page_html[start:min(end + len("</div>"), start + 8000)]


def confirm_post_link(post: dict[str, Any], *, fetch: Callable[[str], str]) -> dict[str, Any]:
    """Re-classify a no-embed post from its own page's main video block.

    Only ``none`` and ``gated`` posts are confirmed; Vimeo and YouTube posts are
    already classified and never requested. A found block overrides the
    provider fields; the subscription-marker flag stays as classified from REST.
    """
    page = fetch(post["link"])
    block = main_video_block(page)
    if block is None:
        return {"checked": True, "mainVideoBlock": False}
    result = classify_content(block)
    for key in LINK_FIELDS:
        if key in result:
            post[key] = result[key]
    if post.get("gated") and result["provider"] == "none":
        post["provider"] = "gated"  # keep the subscription marker when the block has no embed
    post["embedHosts"] = sorted(set(post.get("embedHosts") or []) | set(result["embedHosts"]))
    return {"checked": True, "mainVideoBlock": True, "provider": result["provider"]}


def _link_checked(post: dict[str, Any]) -> bool:
    return bool((post.get("linkCheck") or {}).get("checked"))


def confirm_links(
    catalog: dict[str, Any], *, fetch: Callable[[str], str] = fetch_html,
    delay_seconds: float = 1.5, log: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    checkpoint: Callable[[dict[str, Any]], None] = lambda catalog: None,
    checkpoint_every: int = 25,
) -> dict[str, Any]:
    """Confirm ``none``/``gated`` posts one at a time, with resume and a breaker."""
    targets = [post for post in catalog["posts"]
               if post["provider"] in ("none", "gated") and not _link_checked(post)]
    breaker = _Breaker()
    for position, post in enumerate(targets, start=1):
        if position > 1:
            sleep(delay_seconds + random.uniform(0, delay_seconds))
        try:
            post["linkCheck"] = confirm_post_link(post, fetch=fetch)
            breaker.consecutive = 0
        except (ValueError, RuntimeError) as error:
            post["linkCheck"] = {"checked": False, "error": safe_error(error, limit=160)}
            breaker.observe(error)
            if breaker.open:
                checkpoint(catalog)
                raise RuntimeError(
                    "stopped after repeated 429/5xx responses; re-run to resume") from None
        if position % checkpoint_every == 0:
            checkpoint(catalog)
            log(f"link check {position}/{len(targets)}")
    checkpoint(catalog)
    return catalog


def _post_row(post: dict[str, Any], seen_slugs: set[str]) -> dict[str, Any]:
    post_id = post.get("id")
    if type(post_id) is not int:
        raise ValueError("post has no integer id")
    link = as_text(post.get("link")) or ""
    parsed_link = _parse(link) if link else None
    raw_slug = (unquote(parsed_link.path.strip("/").split("/")[-1])
                if parsed_link is not None else "")
    try:
        slug = safe_slug(raw_slug)
    except ValueError:
        slug = f"post-{post_id}"
    if slug in seen_slugs:
        slug = f"{slug}-{post_id}"
    seen_slugs.add(slug)
    title = html.unescape(re.sub(r"<[^>]+>", "", (post.get("title") or {}).get("rendered") or ""))
    content = (post.get("content") or {}).get("rendered") or ""
    classified = classify_content(content)
    return {"id": post_id, "slug": slug, "title": title.strip(), "date": as_text(post.get("date")),
            "link": link, **classified}


def enumerate_catalog(
    *, fetch: Callable[[str], tuple[Any, dict[str, str]]] = fetch_page,
    delay_seconds: float = 1.5, log: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep, prior: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Walk every REST page once, sequentially, and build the catalog payload."""
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("delay_seconds must be a non-negative number")
    query = f"per_page={PAGE_SIZE}&_fields=id,link,title,date,content"
    first, headers = fetch(f"{ENDPOINT}?{query}&page=1")
    total_posts = int(headers.get("x-wp-total", "0") or 0)
    total_pages = int(headers.get("x-wp-totalpages", "1") or 1)
    if not isinstance(first, list):
        raise ValueError("REST response is not a list of posts")
    posts = [first]
    log(f"page 1/{total_pages}: {len(first)} posts")
    for page in range(2, total_pages + 1):
        sleep(delay_seconds + random.uniform(0, delay_seconds))
        payload, _ = fetch(f"{ENDPOINT}?{query}&page={page}")
        if not isinstance(payload, list):
            raise ValueError("REST response is not a list of posts")
        posts.append(payload)
        log(f"page {page}/{total_pages}: {len(payload)} posts")
    seen: set[str] = set()
    rows = [_post_row(post, seen) for page_posts in posts for post in page_posts]
    if prior is not None:
        confirmed = {row["id"]: row for row in prior.get("posts", []) if _link_checked(row)}
        for row in rows:
            if row["id"] in confirmed:
                row.update({key: confirmed[row["id"]][key] for key in LINK_FIELDS
                            + ("linkCheck",) if key in confirmed[row["id"]]})
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate post ids across pages")
    return build_catalog(rows, total_posts=total_posts, total_pages=total_pages)


def build_catalog(rows: list[dict[str, Any]], *, total_posts: int | None,
                  total_pages: int | None, retrieved_at: str | None = None) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["provider"]] = counts.get(row["provider"], 0) + 1
    return {"schemaVersion": CATALOG_SCHEMA, "retrievedAt": retrieved_at or utc_now(),
            "endpoint": ENDPOINT, "totalPosts": total_posts if total_posts is not None else len(rows),
            "totalPages": total_pages, "providerCounts": dict(sorted(counts.items())),
            "posts": rows}


def build_index_rows(catalog: dict[str, Any], *, measured: dict[int, dict[str, Any]] | None = None,
                     failed: dict[int, str] | None = None) -> dict[str, Any]:
    """One index row per post: status from classification, then measurement outcome."""
    measured, failed = measured or {}, failed or {}
    rows: list[dict[str, Any]] = []
    for post in catalog["posts"]:
        status = _status_for(post["provider"]) if not post["eligible"] else "not-attempted"
        row = {"id": post["id"], "slug": post["slug"], "title": post["title"],
               "date": post["date"], "link": post["link"], "provider": post["provider"],
               "status": status, "reason": post["eligibilityReason"]}
        if post["id"] in measured:
            row.update(status="measured", **measured[post["id"]])
            row.pop("reason", None)
        elif post["id"] in failed:
            row.update(status="failed", reason=failed[post["id"]])
        rows.append(row)
    status_counts: dict[str, int] = {status: 0 for status in STATUSES}
    provider_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        provider_counts[row["provider"]] = provider_counts.get(row["provider"], 0) + 1
    return {"schemaVersion": INDEX_SCHEMA, "generatedAt": utc_now(),
            "catalogSha256": catalog.get("_sha256"), "totalPosts": len(rows),
            "statusCounts": {k: v for k, v in status_counts.items() if v},
            "providerCounts": dict(sorted(provider_counts.items())), "rows": rows}


def _strip_private(catalog: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in catalog.items() if not key.startswith("_")}


def _provider_counts(catalog: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for post in catalog["posts"]:
        counts[post["provider"]] = counts.get(post["provider"], 0) + 1
    return dict(sorted(counts.items()))


def _write_outputs(out_dir: Path, catalog: dict[str, Any]) -> None:
    """Commit catalog.json, then index.json that pins the catalog's SHA-256."""
    catalog["providerCounts"] = _provider_counts(catalog)
    catalog_path = out_dir / "catalog.json"
    write_json_atomic(catalog_path, _strip_private(catalog))
    catalog["_sha256"] = sha256_file(catalog_path)
    write_json_atomic(out_dir / "index.json", build_index_rows(catalog))


def build_video_record(post: dict[str, Any], *, source: dict[str, Any],
                       coverage: dict[str, Any], windows: list[dict[str, Any]],
                       method: str, rights_note: str) -> dict[str, Any]:
    evidence = build_video_evidence(
        source=source, coverage=coverage, windows=windows, method=method,
        provider=post["provider"], video_url=post.get("videoUrl"),
        rights_basis=RIGHTS_BASIS, rights_note=rights_note, schema_version=VIDEO_SCHEMA,
        evidence_status=EVIDENCE_STATUS, limits=LIMITS, rights_status=RIGHTS_STATUS)
    return {"schemaVersion": VIDEO_SCHEMA, "id": post["id"], "slug": post["slug"],
            "title": post["title"], "date": post["date"], "link": post["link"],
            **evidence}


def collect_one(post: dict[str, Any], out_dir: Path, *, windows: int = 4,
                window_seconds: int = 10, max_duration_seconds: float = 600.0,
                max_file_bytes: int = 400 * 1024 * 1024,
                rights_note: str = DEFAULT_RIGHTS_NOTE, ffmpeg: str = "ffmpeg",
                ffprobe: str = "ffprobe", download_timeout: float = 360.0) -> dict[str, Any]:
    """Download -> validate -> measure -> write record -> always delete media."""
    if (type(windows) is not int or not 1 <= windows <= MAX_WINDOWS
            or type(window_seconds) is not int or not 1 <= window_seconds <= MAX_WINDOW_SECONDS):
        raise ValueError("window budgets are out of bounds")
    if not finite_float(max_duration_seconds) or max_duration_seconds <= 0:
        raise ValueError("duration budget is out of bounds")
    if post.get("provider") != "direct-mp4":
        raise ValueError("post is not a self-hosted direct mp4 candidate")
    url = allowlisted_video_url(post.get("videoUrl"), allowed_hosts=VIDEO_HOSTS)
    slug = safe_slug(post.get("slug"))
    record_path = out_dir / "videos" / f"{slug}.json"
    scratch = Path(tempfile.mkdtemp(prefix="kumiki-stash-"))
    try:
        media_dir = scratch / "media"
        media_dir.mkdir()
        path, method = download_media(
            url, DIRECT, media_dir, allowed_hosts=VIDEO_HOSTS, max_bytes=max_file_bytes,
            ffmpeg=ffmpeg, ffprobe=ffprobe, timeout=download_timeout,
            max_duration_seconds=max_duration_seconds)
        source = source_metadata(path, ffprobe=ffprobe)
        if source["durationSeconds"] > max_duration_seconds:
            raise ValueError("source exceeds the bounded duration budget")
        coverage, measured = measure_windows(
            path, duration_seconds=source["durationSeconds"], window_count=windows,
            window_seconds=window_seconds, image_translation=False,
            ffmpeg=ffmpeg, ffprobe=ffprobe)
        record = build_video_record(post, source=source, coverage=coverage, windows=measured,
                                    method=method, rights_note=rights_note)
        write_json_atomic(record_path, record)
        return record
    finally:
        # Hard guarantee: no media, frames, thumbnails, or audio survive the job.
        shutil.rmtree(scratch, ignore_errors=True)


class _Breaker:
    """Stops the batch after repeated 429/5xx responses rather than hammering the site."""

    def __init__(self, threshold: int = 3) -> None:
        self.threshold, self.consecutive, self.open = threshold, 0, False

    def observe(self, error: Exception) -> None:
        if re.search(r"HTTP (?:Error )?(?:429|5\d\d)\b", str(error)):
            self.consecutive += 1
            if self.consecutive >= self.threshold:
                self.open = True
        else:
            self.consecutive = 0


def run_measure(
    catalog_path: Path, *, out_dir: Path, limit: int | None = None, resume: bool = True,
    delay_seconds: float = 1.5, acknowledge_rights: bool = False,
    log: Callable[[str], None] = print, **video_options: Any,
) -> int:
    if acknowledge_rights is not True:
        raise ValueError("explicit --acknowledge-rights attestation is required")
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a non-negative integer")
    raw = Path(catalog_path).read_bytes()
    catalog = json.loads(raw.decode("utf-8"))
    if not isinstance(catalog, dict) or catalog.get("schemaVersion") != CATALOG_SCHEMA:
        raise ValueError("unsupported catalog schema")
    catalog["_sha256"] = hashlib.sha256(raw).hexdigest()
    out_dir = Path(out_dir)
    (out_dir / "videos").mkdir(parents=True, exist_ok=True)
    eligible = [post for post in catalog["posts"] if post.get("eligible")]
    if limit is not None:
        eligible = eligible[:limit]
    breaker = _Breaker()
    failed: dict[int, str] = {}
    index_path = out_dir / "index.json"

    def run_one(post: dict[str, Any]) -> dict[str, Any]:
        if breaker.open:
            raise RuntimeError("circuit-open: repeated 429/5xx responses, batch halted")
        try:
            return collect_one(post, out_dir, **video_options)
        except Exception as error:
            breaker.observe(error)
            raise

    def skip_reason(post: dict[str, Any]) -> str | None:
        if not resume:
            return None
        return ("resume-existing-record" if _resume_matches(
            out_dir / "videos" / f"{safe_slug(post.get('slug'))}.json", post.get("id"),
            field="id") else None)

    def summary_row(record: dict[str, Any]) -> dict[str, Any]:
        source = record.get("source") or {}
        summary = record.get("summary") or {}
        return {"measured_id": record["id"],
                "measured": {"recordPath": f"videos/{record['slug']}.json",
                             "durationSeconds": source.get("durationSeconds"),
                             "resolution": source.get("resolution"),
                             "sourceSha256": source.get("mediaSha256"),
                             "cutCandidates": summary.get("cutCandidates")}}

    def build_index(measured: list[dict[str, Any]], skips: list[dict[str, Any]],
                    failures: list[dict[str, Any]]) -> dict[str, Any]:
        done = {row["measured_id"]: row["measured"] for row in measured}
        fails = {row["id"]: row["reason"] for row in failures}
        for skip in skips:
            if skip.get("reason") == "resume-existing-record":
                done.setdefault(skip["id"], _existing_measure(out_dir, catalog, skip["id"]))
        if index_path.exists():
            prior = json.loads(index_path.read_text(encoding="utf-8"))
            for row in prior.get("rows", []):
                if row.get("status") == "failed" and row["id"] not in fails and row["id"] not in done:
                    fails[row["id"]] = row.get("reason", "failed in a previous run")
        index_payload = build_index_rows(catalog, measured=done, failed=fails)
        index_payload["catalogSha256"] = catalog["_sha256"]
        return index_payload

    def failure_row(post: dict[str, Any], reason: str) -> dict[str, Any]:
        return {"id": post["id"], "reason": reason,
                "status": "not-attempted" if "circuit-open" in reason else "failed"}

    def progress(position: int, total: int, status: str, label: str, text: str) -> None:
        print(f"[{position}/{total}] {status} {label} {text}".rstrip(), flush=True)

    outcome = run_batch(
        eligible, run_one=run_one, index_path=index_path, build_index=build_index,
        summary_row=summary_row, skip_row=lambda post, reason: {"id": post["id"], "reason": reason},
        describe=lambda post: post["slug"], failure_row=failure_row,
        skip_reason=skip_reason, error_text=lambda error: safe_error(error, redact=(str(out_dir),)),
        progress=progress, jobs=1, delay_seconds=delay_seconds)
    log(f"measured={outcome.measured} skipped={outcome.skipped} failed={outcome.failed} "
        f"attempted={outcome.attempted} elapsed={outcome.elapsed_seconds:.1f}s index={index_path}")
    return 0 if outcome.measured or not outcome.attempted else 1


def _existing_measure(out_dir: Path, catalog: dict[str, Any], post_id: int) -> dict[str, Any]:
    post = next(post for post in catalog["posts"] if post["id"] == post_id)
    path = out_dir / "videos" / f"{post['slug']}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    source, summary = record.get("source") or {}, record.get("summary") or {}
    return {"recordPath": f"videos/{post['slug']}.json",
            "durationSeconds": source.get("durationSeconds"),
            "resolution": source.get("resolution"),
            "sourceSha256": source.get("mediaSha256"),
            "cutCandidates": summary.get("cutCandidates")}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "STASH public video research. 'enumerate' walks every public WordPress post "
            "and classifies embeds into catalog.json and index.json (no media). 'measure' "
            "downloads only self-hosted direct MP4s on the exact allowlisted host, "
            "measures sampled source-PTS windows, and deletes all media. Vimeo, YouTube, "
            "and gated posts are skip rows and are never requested."))
    sub = parser.add_subparsers(dest="command", required=True)
    out_default = str(DEFAULT_OUT_DIR)
    enum = sub.add_parser("enumerate", help="Build catalog.json and index.json (no media).")
    enum.add_argument("--out-dir", default=out_default, help="Output directory (default: %(default)s).")
    enum.add_argument("--delay-seconds", type=float, default=1.5,
                      help="Minimum delay between requests, jitter added (default: %(default)s).")
    enum.add_argument("--confirm-links", action="store_true",
                      help=("Also fetch the public page of each post classified 'none' or 'gated' and "
                            "read its single-post video block (one request at a time). Resumable."))
    meas = sub.add_parser("measure", help="Measure eligible self-hosted MP4s, one at a time.")
    meas.add_argument("--catalog", default=f"{out_default}/catalog.json",
                      help="catalog.json from 'enumerate' (default: %(default)s).")
    meas.add_argument("--out-dir", default=out_default, help="Output directory (default: %(default)s).")
    meas.add_argument("--limit", type=int, default=None,
                      help="Measure at most N eligible videos (trial runs; default: all).")
    meas.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True,
                      help="Skip videos whose record already exists for the same post id (default: on).")
    meas.add_argument("--delay-seconds", type=float, default=1.5,
                      help="Minimum delay between videos, jitter added (default: %(default)s).")
    meas.add_argument("--windows", type=int, default=4, help="Sampled windows per video (default: %(default)s).")
    meas.add_argument("--window-seconds", type=int, default=10, help="Seconds per window (default: %(default)s).")
    meas.add_argument("--max-duration-seconds", type=float, default=600.0,
                      help="Reject sources longer than this (default: %(default)s).")
    meas.add_argument("--max-file-bytes", type=int, default=400 * 1024 * 1024,
                      help="Reject sources larger than this (default: %(default)s).")
    meas.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg binary (default: %(default)s).")
    meas.add_argument("--ffprobe", default="ffprobe", help="ffprobe binary (default: %(default)s).")
    meas.add_argument("--acknowledge-rights", action="store_true",
                      help="Required attestation: public availability is not a license; media is deleted after measurement.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "enumerate":
            out_dir = Path(args.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            catalog_path = out_dir / "catalog.json"
            prior = (json.loads(catalog_path.read_text(encoding="utf-8"))
                     if catalog_path.exists() else None)
            catalog = enumerate_catalog(delay_seconds=args.delay_seconds, prior=prior)
            _write_outputs(out_dir, catalog)
            if args.confirm_links:
                confirm_links(catalog, delay_seconds=args.delay_seconds,
                              checkpoint=lambda current: _write_outputs(out_dir, current))
                _write_outputs(out_dir, catalog)
            print(f"enumerated {len(catalog['posts'])} posts; "
                  f"providers={_provider_counts(catalog)}", flush=True)
            return 0
        if not args.acknowledge_rights:
            parser.error("--acknowledge-rights is required: public availability is not a license "
                         "and downloaded media is deleted after measurement")
        return run_measure(
            Path(args.catalog), out_dir=Path(args.out_dir), limit=args.limit,
            resume=args.resume, delay_seconds=args.delay_seconds,
            acknowledge_rights=args.acknowledge_rights, windows=args.windows,
            window_seconds=args.window_seconds, max_duration_seconds=args.max_duration_seconds,
            max_file_bytes=args.max_file_bytes, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"error: {safe_error(error)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
