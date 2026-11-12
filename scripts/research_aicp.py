"""Ephemeral, source-PTS measurement of the public AICP Awards video archive.

The archive lives at ``https://aicpawards.com`` behind a thin Vite single-page
app. Its only data door is an unauthenticated GraphQL POST endpoint that returns
commercial-entry metadata (string ids, ``MM:SS``/``H:MM:SS`` durations, relative
screenshots) and one signed HLS URL per entry. Every downloaded byte lives in a
private scratch directory deleted in a ``finally`` block; only numeric
source-PTS evidence and catalog metadata are committed. A second ``stills`` lane
measures each entry's published screenshot the same way.

This is a *site adapter*: allowlisting, retrieval, HLS planning/remux, probing,
window and still measurement, evidence assembly, atomic writes, resume checks,
index assembly, and the pooled batch loop all come from
:mod:`kumiki_reference_lab.acquisition`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import statistics
import sys
import tempfile
import time
from functools import partial
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import (
    HTTPRedirectHandler, Request, build_opener, urlopen,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition import (  # noqa: E402
    HLS, MAX_WINDOWS, MAX_WINDOW_SECONDS, STILL_MAX_BYTES, USER_AGENT,
    aggregate_extremes, allowlisted_image_url, allowlisted_url,
    allowlisted_video_url, as_int, as_text, build_index, build_still_evidence,
    build_video_evidence, comparability_block, coverage_distribution,
    cut_columns, download_http, download_media, duplicate_summary,
    finite_float, image_target, measure_still, measure_windows,
    resume_matches as _resume_matches, run_batch, safe_error, safe_slug,
    source_metadata, still_decode_counts, still_decode_dimensions,
    still_has_quality_flags, still_image_format, still_quality_summary,
    unique_media_rows, utc_now, write_json_atomic,
)
from kumiki_reference_lab.acquisition.reporting import (  # noqa: E402
    comparability_lines, coverage_lines, excluded_leaders_lines, extreme_text,
)
from kumiki_reference_lab.analyzers.media.inspect import sha256_file  # noqa: E402

SITE = "https://aicpawards.com"
ENDPOINT = f"{SITE}/api"
ARTICLE_URL = SITE + "/winners-gallery/details?id={entry_id}"
SPA_SHELL = SITE + "/"

CATALOG_SCHEMA = "kumiki.aicp-catalog.v1"
INDEX_SCHEMA = "kumiki.aicp-index.v1"
VIDEO_SCHEMA = "kumiki.aicp-video-evidence.v1"
STILL_SCHEMA = "kumiki.aicp-still-evidence.v1"
STILLS_INDEX_SCHEMA = "kumiki.aicp-stills-index.v1"
AGGREGATE_SCHEMA = "kumiki.aicp-aggregate.v1"

# The GraphQL ``video`` field 302s to a signed vod-adaptive origin. Only these
# hosts are admitted for video; the signed redirect host lives under
# ``*.vimeocdn.com``. Stills stay on the award site itself and keep the strict
# no-query policy.
MEDIA_HOSTS = ("player.vimeo.com", ".vimeocdn.com")
IMAGE_HOSTS = ("aicpawards.com",)
SITE_HOSTS = ("aicpawards.com",)

PROVIDER_DELIVERY = {"hls": HLS}
SUPPORTED_DELIVERIES = ("hls",)
# Labels that identify a full show/program rather than an individual entry.
LONG_FORM_VIDEO_TYPES = (
    "full show reel",
    "full post show reel",
    "next premiere show",
)

EVIDENCE_STATUS = "sampled-original-source-pts-metrics-not-expert-reviewed"
STILL_EVIDENCE_STATUS = "single-published-still-metrics-not-video-measurement"
RIGHTS_BASIS = "user-declared-research-use"
RIGHTS_STATUS = "review-required"
DEFAULT_RIGHTS_NOTE = (
    "operator attests public-page research use; the signed HLS stream is "
    "downloaded once, measured numerically, and deleted without redistribution")

DEFAULT_MAX_FILE_BYTES = 250 * 1024 * 1024
DEFAULT_MAX_DURATION_SECONDS = 600.0
DEFAULT_VIDEO_DELAY = 1.2
DEFAULT_STILL_DELAY = 0.8
DEFAULT_CATALOG_DELAY = 1.0
DEFAULT_TOP = 20
DEFAULT_PAGE_SIZE = 100
_MAX_PAGES = 200
_MAX_RESPONSE_BYTES = 8_000_000

POLICY_SKIP_REASONS = (
    "unsupported-long-form", "duration-over-cap", "no-video-url",
    "unsupported-provider", "no-poster",
)

LIMITS = [
    "Only sampled source-PTS windows were measured; this is not a full-film review.",
    "The platform's HLS web rendition was decoded, not the archive's master; "
    "every number describes that rendition only.",
    "The player.vimeo.com URL is resolved through its signed vod-adaptive "
    "redirect at download time; the signed target is never persisted.",
    "The downloaded file was deleted immediately after measurement; no media, "
    "frames, thumbnails, or audio are retained.",
    "Public availability is not a licence: rightsStatus remains review-required.",
    "Membership in commercialsEntries is the honoree signal; no award level "
    "(gold/silver/bronze) exists in the catalog and none is inferred.",
    "`company` is the only populated credit field in the archive; agency, "
    "director, and producer are absent on montages and are never invented.",
    "Catalog metadata is self-reported by aicpawards.com and is not "
    "independently verified.",
    "No cookies, logins, tokens, or access-control bypass were used.",
]
STILL_LIMITS = [
    "A published screenshot is not a video frame: no motion, cut, pacing, "
    "timing, sequence, or edit-rhythm evidence is claimed.",
    "Colour, luminance, histogram, hue, and edge-density numbers describe one "
    "single image, not the entry's runtime behaviour.",
    "The screenshot is prepared by the awards site, not necessarily by the "
    "work's author.",
    "The downloaded image was deleted immediately after measurement; no image "
    "bytes are retained.",
    "Public availability is not a licence; rightsStatus remains review-required.",
    "Catalog metadata is self-reported by aicpawards.com and is not "
    "independently verified.",
]
STILL_COVERAGE_NOTE = (
    "single screenshot published by the awards site, decoded once at 160x90 "
    "RGB; not a decoded video frame, no motion/time evidence")

ENTRY_FIELDS = (
    "... on commercials_commercial_Entry { "
    "id slug title year company duration video "
    "videoType { title } "
    "showCategory { title } postCategory { title } nextCategory { title } "
    "screenshot { url width height } "
    "}"
)


# ---------------------------------------------------------------------------
# small coercion helpers
# ---------------------------------------------------------------------------


def _titles(value: object) -> list[str]:
    """Read a list of ``{title: ...}`` relation nodes into unique strings."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    titles: list[str] = []
    for item in items:
        if isinstance(item, dict):
            text = as_text(item.get("title"))
        elif isinstance(item, str):
            text = as_text(item)
        else:
            text = None
        if text and text not in titles:
            titles.append(text)
    return titles


def parse_duration_text(value: object) -> int | None:
    """Parse the archive's ``MM:SS`` / ``H:MM:SS`` duration strings.

    ``float("02:29")`` yields nothing (and a plain ``float()`` would silently
    disable the duration guard), so this parser is explicit. Garbage, negative
    numbers, empty strings, and out-of-range components return ``None``.
    """
    text = as_text(value)
    if text is None:
        return None
    text = text.strip()
    parts = text.split(":")
    if len(parts) not in (2, 3):
        return None
    if any(not part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    if len(numbers) == 2:
        minutes, seconds = numbers
        if seconds >= 60:
            return None
        return minutes * 60 + seconds
    hours, minutes, seconds = numbers
    if minutes >= 60 or seconds >= 60:
        return None
    return hours * 3600 + minutes * 60 + seconds


def _first_screenshot(value: object) -> dict[str, Any] | None:
    """Return the first screenshot object, tolerating a list or a single node."""
    if isinstance(value, list):
        value = next((item for item in value if isinstance(item, dict)), None)
    if not isinstance(value, dict):
        return None
    url = as_text(value.get("url"))
    if url is None:
        return None
    return {"url": url, "width": as_int(value.get("width")),
            "height": as_int(value.get("height"))}


def classify_delivery(video_url: object) -> str | None:
    """Classify one catalog ``video`` URL by path/host, never by provider name."""
    text = as_text(video_url)
    if text is None:
        return None
    try:
        parsed = urlsplit(text)
    except ValueError:
        return "other"
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if path.endswith(".m3u8") and (
            host == "player.vimeo.com" or host.endswith(".vimeo.com")
            or host == "vimeo.com"):
        return "hls"
    if path.endswith(".m3u8"):
        return "hls"
    if path.endswith((".mp4", ".mov", ".m4v", ".webm")):
        return "direct"
    return "other"


def is_long_form(video_types: Iterable[object]) -> bool:
    """True when any declared video type names a full show/program."""
    for value in video_types or ():
        text = as_text(value)
        if text is None:
            continue
        if text.strip().casefold() in LONG_FORM_VIDEO_TYPES:
            return True
    return False


def downloadability(
    video_url: object, video_types: Iterable[object],
    delivery: str | None = None,
) -> tuple[bool, str | None]:
    """Static catalog-level downloadability and its explicit reason."""
    if as_text(video_url) is None:
        return False, "no-video-url"
    delivery = delivery if delivery is not None else classify_delivery(video_url)
    if delivery not in SUPPORTED_DELIVERIES:
        return False, "unsupported-provider"
    if is_long_form(video_types):
        return False, "unsupported-long-form"
    return True, None


def collect_skip_reason(
    row: dict[str, Any], *, max_duration_seconds: float | None = None,
) -> str | None:
    """Static pre-download skip reason for one slim catalog row."""
    if as_text(row.get("videoUrl")) is None:
        return "no-video-url"
    delivery = row.get("videoDelivery")
    if delivery not in SUPPORTED_DELIVERIES:
        return "unsupported-provider"
    if is_long_form(row.get("videoType") or ()):
        return "unsupported-long-form"
    duration = finite_float(row.get("durationSeconds"))
    if (max_duration_seconds is not None and duration is not None
            and duration > max_duration_seconds):
        return "duration-over-cap"
    return None


def record_stem(row: dict[str, Any]) -> str:
    """Stable ``<id>-<slug>`` record/file stem; raises on unsafe identifiers."""
    identifier = safe_slug(row.get("id"))
    slug = row.get("slug")
    if isinstance(slug, str) and slug.strip():
        return f"{identifier}-{safe_slug(slug)}"
    return identifier


# ---------------------------------------------------------------------------
# catalog: GraphQL POST envelope, offset paging, slim projection
# ---------------------------------------------------------------------------


def _graphql_error_text(errors: object) -> str:
    messages: list[str] = []
    if isinstance(errors, list):
        for item in errors[:5]:
            text = (as_text(item.get("message")) if isinstance(item, dict)
                    else as_text(item))
            if text:
                messages.append(text)
    text = "; ".join(messages)[:300] or "unspecified GraphQL error"
    return re.sub(r"https?://\S+", "[redacted-url]", text)


def _post_graphql(
    alias: str, query: str, *, endpoint: str = ENDPOINT, timeout: float = 45.0,
    retries: int = 3, sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """POST one ``{alias: {query: ...}}`` GraphQL request and return its data.

    The archive answers GraphQL failures with **HTTP 200** and an ``errors``
    list inside the alias, so a bare ``raise_for_status()`` would record garbage
    as success. This function checks the alias block explicitly and fails
    loudly. Transport errors and 429/5xx responses get bounded retries.
    """
    if not isinstance(alias, str) or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*", alias):
        raise ValueError("GraphQL alias must be a simple identifier")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("GraphQL query must be non-empty text")
    allowlisted_url(endpoint, allowed_hosts=SITE_HOSTS,
                    label="catalog endpoint")
    body = json.dumps({alias: {"query": query}}).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(retries):
        request = Request(endpoint, data=body, method="POST", headers={
            "Accept": "application/json", "Content-Type": "application/json",
            "User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise ValueError(
                    f"catalog endpoint rejected the request (HTTP {error.code})"
                ) from None
            last_error = error
        except (URLError, TimeoutError, OSError) as error:
            last_error = error
        else:
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise ValueError(
                    "catalog response exceeded the expected size limit")
            try:
                payload = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise ValueError("catalog response was not valid JSON") from None
            if not isinstance(payload, dict):
                raise ValueError("catalog response was not a JSON object")
            if payload.get("errors"):
                raise ValueError(
                    "catalog GraphQL returned errors: "
                    + _graphql_error_text(payload["errors"]))
            block = payload.get(alias)
            if not isinstance(block, dict):
                raise ValueError(
                    "catalog response did not carry the expected alias block")
            if block.get("errors"):
                raise ValueError(
                    "catalog GraphQL returned errors: "
                    + _graphql_error_text(block["errors"]))
            data = block.get("data")
            if not isinstance(data, dict):
                raise ValueError("catalog response carried no data block")
            return data
        if attempt + 1 < retries:
            sleep(2 ** attempt)
    raise RuntimeError(
        "catalog request failed after bounded retries") from last_error


def entries_query(limit: int, offset: int) -> str:
    """Build one ``commercialsEntries`` page query with literal ints."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("catalog page size must be between 1 and 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("catalog offset must be a non-negative integer")
    return (
        "{ commercialsEntries(limit: %d, offset: %d) { %s } }"
        % (limit, offset, ENTRY_FIELDS))


def entry_count_query(*, section: str = "commercials",
                      year: int | None = None) -> str:
    """Build the ``entryCount(section:, year:)`` query (section, not collection)."""
    if not isinstance(section, str) or not section.strip():
        raise ValueError("catalog section must be non-empty text")
    arguments = f"section: {json.dumps(section)}"
    if year is not None:
        if type(year) is not int or year < 1900:
            raise ValueError("entry-count year must be a plausible integer")
        arguments += f", year: {year}"
    return f"{{ entryCount({arguments}) }}"


def fetch_entry_count(
    *, section: str = "commercials", year: int | None = None,
    post: Callable[[str, str], dict[str, Any]] = _post_graphql,
) -> int | None:
    """Read the archive's reported entry count, or ``None`` when absent."""
    data = post("c", entry_count_query(section=section, year=year))
    return as_int(data.get("entryCount"))


def parse_entry(node: object) -> dict[str, Any]:
    """Map one ``commercialsEntries`` node to the slim catalog row."""
    if not isinstance(node, dict):
        raise ValueError("catalog entry node must be an object")
    entry_id = as_text(node.get("id"))
    if entry_id is None:
        raise ValueError("catalog entry node has no string id")
    video_url = as_text(node.get("video"))
    video_types = _titles(node.get("videoType"))
    categories: list[str] = []
    for key in ("showCategory", "postCategory", "nextCategory"):
        for title in _titles(node.get(key)):
            if title not in categories:
                categories.append(title)
    screenshot = _first_screenshot(node.get("screenshot"))
    poster_url = (urljoin(SPA_SHELL, screenshot["url"])
                  if screenshot is not None else None)
    duration_text = as_text(node.get("duration"))
    delivery = classify_delivery(video_url)
    downloadable, reason = downloadability(video_url, video_types, delivery)
    return {
        "id": str(entry_id),
        "slug": as_text(node.get("slug")) or "",
        "title": as_text(node.get("title")) or "",
        "year": as_int(node.get("year")),
        "company": as_text(node.get("company")),
        "durationText": duration_text,
        "durationSeconds": parse_duration_text(duration_text),
        "videoType": video_types,
        "categories": categories,
        "videoUrl": video_url,
        "videoDelivery": delivery,
        "posterUrl": poster_url,
        "posterWidth": (screenshot["width"] if screenshot else None),
        "posterHeight": (screenshot["height"] if screenshot else None),
        "articleUrl": ARTICLE_URL.format(
            entry_id=quote(str(entry_id), safe="")),
        "downloadable": downloadable,
        "downloadReason": reason,
    }


def fetch_all_entries(
    *, post: Callable[[str, str], dict[str, Any]] = _post_graphql,
    page_size: int = DEFAULT_PAGE_SIZE, limit: int | None = None,
    delay_seconds: float = DEFAULT_CATALOG_DELAY,
    sleeper: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> list[dict[str, Any]]:
    """Page ``commercialsEntries`` newest-first until a short/empty page."""
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ValueError("catalog page size must be between 1 and 100")
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a non-negative integer")
    if limit == 0:
        limit = None
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("delay_seconds must be a non-negative number")
    entries: list[dict[str, Any]] = []
    offset = 0
    pages = 0
    while pages < _MAX_PAGES:
        wanted = (page_size if limit is None
                  else min(page_size, limit - len(entries)))
        if wanted <= 0:
            break
        data = post("rows", entries_query(wanted, offset))
        rows = data.get("commercialsEntries")
        if not isinstance(rows, list):
            raise ValueError(
                "catalog response has no commercialsEntries list")
        entries.extend(parse_entry(node) for node in rows)
        log(f"catalog page {pages + 1}: {len(rows)} entries "
            f"(collected {len(entries)})")
        if limit is not None and len(entries) >= limit:
            del entries[limit:]
            break
        if len(rows) < wanted:
            break
        offset += len(rows)
        pages += 1
        if delay_seconds:
            sleeper(float(delay_seconds))
    else:
        raise ValueError("catalog pagination exceeded the safety page budget")
    return entries


def build_catalog(
    entries: Iterable[dict[str, Any]], total_reported: int | None, *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble the slim, versioned catalog with provenance counts."""
    rows = list(entries)
    by_year: dict[str, int] = {}
    by_type: dict[str, int] = {}
    downloadable = 0
    for row in rows:
        year = as_int(row.get("year"))
        key = str(year) if year is not None else "unknown"
        by_year[key] = by_year.get(key, 0) + 1
        types = row.get("videoType") or []
        if not types:
            by_type["unknown"] = by_type.get("unknown", 0) + 1
        for title in types:
            by_type[str(title)] = by_type.get(str(title), 0) + 1
        if row.get("downloadable") is True:
            downloadable += 1
    return {
        "schemaVersion": CATALOG_SCHEMA,
        "generatedAt": generated_at or utc_now(),
        "endpoint": ENDPOINT,
        "counts": {
            "totalReported": total_reported,
            "collected": len(rows),
            "byYear": {key: by_year[key] for key in sorted(by_year)},
            "byVideoType": {key: by_type[key] for key in sorted(by_type)},
            "downloadable": downloadable,
            "notDownloadable": len(rows) - downloadable,
        },
        "entries": rows,
    }


def _load_catalog(path: Path) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or catalog.get("schemaVersion") != CATALOG_SCHEMA:
        raise ValueError("unsupported catalog schema")
    if not isinstance(catalog.get("entries"), list):
        raise ValueError("catalog has no entry list")
    return catalog


def run_catalog(
    out_path: Path, *, limit: int | None = None,
    delay_seconds: float = DEFAULT_CATALOG_DELAY,
    post: Callable[[str, str], dict[str, Any]] = _post_graphql,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Fetch the reported total and every page, then write the catalog atomically."""
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a non-negative integer")
    total = fetch_entry_count(post=post)
    entries = fetch_all_entries(
        post=post, limit=limit, delay_seconds=delay_seconds, log=log)
    catalog = build_catalog(entries, total)
    write_json_atomic(Path(out_path), catalog)
    log(f"catalog: reported={total} collected={len(entries)} "
        f"downloadable={catalog['counts']['downloadable']} -> {out_path}")
    return catalog


# ---------------------------------------------------------------------------
# policies and record builders
# ---------------------------------------------------------------------------

_policy_video_url = partial(
    allowlisted_video_url, allowed_hosts=MEDIA_HOSTS, allow_query=True)
_policy_image_url = partial(allowlisted_image_url, allowed_hosts=IMAGE_HOSTS)


class _RefuseAutoRedirect(HTTPRedirectHandler):
    """Expose each redirect hop so the adapter can re-validate its target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def resolve_master_url(url: object, *, timeout: float = 30.0) -> str:
    """Resolve the public HLS entry's 302 chain to its signed master URL.

    ``player.vimeo.com/external/<id>.m3u8`` redirects to a signed
    ``vod-adaptive-ak.vimeocdn.com`` master whose variant/audio URIs are
    *relative*. Resolving those against the pre-redirect URL silently produces
    404s, so the adapter follows the chain itself, re-validating every hop with
    the same media allowlist and query opt-in, and hands the final URL to the
    acquisition engine. The signed URL is used immediately and never persisted.
    """
    current = _policy_video_url(url)
    opener = build_opener(_RefuseAutoRedirect())
    for _ in range(6):
        request = Request(current, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.apple.mpegurl,*/*",
            "Range": "bytes=0-0"})
        try:
            with opener.open(request, timeout=timeout) as response:
                return _policy_video_url(response.geturl())
        except HTTPError as error:
            headers = (getattr(error, "headers", None)
                       or getattr(error, "hdrs", None) or {})
            location = headers.get("Location") if hasattr(headers, "get") else None
            if error.code in (301, 302, 303, 307, 308) and location:
                current = _policy_video_url(urljoin(current, location))
                continue
            raise ValueError(
                f"HLS master resolution failed (HTTP {error.code})") from None
        except (URLError, TimeoutError, OSError) as error:
            raise ValueError("HLS master resolution failed") from error
    raise ValueError("HLS master redirected too many times")


def resume_matches(record_path: Path, entry_id: object) -> bool:
    """A record is complete when it carries the same string catalog ``id``."""
    return _resume_matches(record_path, entry_id, field="id")


def _skip_row(row: Any, reason: str) -> dict[str, Any]:
    return {
        "id": (row.get("id") if isinstance(row, dict) else None),
        "slug": (row.get("slug") if isinstance(row, dict) else None),
        "reason": reason,
    }


def build_video_record(
    row: dict[str, Any], *, source: dict[str, Any],
    coverage: dict[str, Any], windows: list[dict[str, Any]], method: str,
    rights_note: str, generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge AICP subject identity around the package's neutral evidence."""
    evidence = build_video_evidence(
        source=source, coverage=coverage, windows=windows, method=method,
        provider=HLS, video_url=row.get("videoUrl"),
        rights_basis=RIGHTS_BASIS, rights_note=rights_note,
        schema_version=VIDEO_SCHEMA, evidence_status=EVIDENCE_STATUS,
        limits=LIMITS, generated_at=generated_at, rights_status=RIGHTS_STATUS)
    return {
        "schemaVersion": VIDEO_SCHEMA,
        "id": str(row.get("id")),
        "slug": row.get("slug"),
        "articleUrl": row.get("articleUrl"),
        "catalog": {
            "title": row.get("title"),
            "year": as_int(row.get("year")),
            "company": row.get("company"),
            "durationText": row.get("durationText"),
            "durationSeconds": row.get("durationSeconds"),
            "videoType": row.get("videoType") or [],
            "categories": row.get("categories") or [],
            "posterUrl": row.get("posterUrl"),
        },
        **evidence,
    }


def build_still_record(
    row: dict[str, Any], *, still: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge AICP subject identity around the package's neutral still payload."""
    evidence = build_still_evidence(
        still=still, schema_version=STILL_SCHEMA,
        evidence_status=STILL_EVIDENCE_STATUS, limits=STILL_LIMITS,
        coverage_note=STILL_COVERAGE_NOTE, generated_at=generated_at)
    return {
        "schemaVersion": STILL_SCHEMA,
        "id": str(row.get("id")),
        "slug": row.get("slug"),
        "articleUrl": row.get("articleUrl"),
        "catalog": {
            "title": row.get("title"),
            "year": as_int(row.get("year")),
            "company": row.get("company"),
            "videoType": row.get("videoType") or [],
        },
        **evidence,
    }


def _video_summary_row(
    record: dict[str, Any], path: Path | None = None,
) -> dict[str, Any]:
    catalog = record.get("catalog") or {}
    source = record.get("source") or {}
    coverage = record.get("coverage") or {}
    summary = record.get("summary") or {}
    return {
        "id": record.get("id"),
        "slug": record.get("slug"),
        "title": catalog.get("title"),
        "year": catalog.get("year"),
        "company": catalog.get("company"),
        "videoType": catalog.get("videoType") or [],
        "durationText": catalog.get("durationText"),
        "durationSeconds": source.get("durationSeconds"),
        "resolution": source.get("resolution"),
        "sourceSha256": source.get("mediaSha256"),
        "windowCount": coverage.get("windowsMeasured"),
        "cutCandidates": summary.get("cutCandidates"),
        "cutsPerMinute": summary.get("cutCandidateRatePerMinute"),
        "meanDisplayLuma": summary.get("meanDisplayLuma"),
        "meanSaturation": summary.get("meanSaturation"),
        "recordPath": (path.as_posix() if path is not None
                       else f"videos/{record_stem(record)}.json"),
    }


def _still_summary_row(
    record: dict[str, Any], path: Path | None = None,
) -> dict[str, Any]:
    still = record.get("still") or {}
    metrics = still.get("metrics") or {}
    return {
        "id": record.get("id"),
        "slug": record.get("slug"),
        "title": (record.get("catalog") or {}).get("title"),
        "year": (record.get("catalog") or {}).get("year"),
        "imageUrl": still.get("imageUrl"),
        "imageSha256": still.get("imageSha256"),
        "imageFormat": still.get("imageFormat"),
        "imageBytes": still.get("imageBytes"),
        "imageWidth": still.get("imageWidth"),
        "imageHeight": still.get("imageHeight"),
        "meanDisplayLumaProxy": metrics.get("meanDisplayLumaProxy"),
        "dominantHueFamily": metrics.get("dominantHueFamily"),
        "edgeDensityProxy": metrics.get("edgeDensityProxy"),
        "recordPath": ((path.as_posix() if path is not None
                        else f"stills/{record_stem(record)}.json")),
    }


def _video_detail(record: dict[str, Any]) -> str:
    source = record.get("source") or {}
    summary = record.get("summary") or {}
    width, height = source.get("resolution") or (0, 0)
    return (f"{width}x{height} {(source.get('durationSeconds') or 0):.1f}s "
            f"{((source.get('sizeBytes') or 0) / (1024 * 1024)):.1f}MB "
            f"cuts={summary.get('cutCandidates', 0)}")


def _still_detail(record: dict[str, Any]) -> str:
    still = record.get("still") or {}
    metrics = still.get("metrics") or {}
    return (f"{still.get('imageWidth')}x{still.get('imageHeight')} "
            f"luma={metrics.get('meanDisplayLumaProxy')} "
            f"hue={metrics.get('dominantHueFamily')} "
            f"bytes={still.get('imageBytes')}")


# ---------------------------------------------------------------------------
# collect: download -> probe -> measure -> write -> always delete
# ---------------------------------------------------------------------------


class DownloadFailed(RuntimeError):
    """The bounded download (or its signed redirect) failed."""


class ProbeFailed(RuntimeError):
    """Post-download characterisation or window measurement failed."""


def _require_budgets(
    *, windows: int, window_seconds: int, max_duration_seconds: float,
    max_file_bytes: int,
) -> None:
    if (type(windows) is not int or not 1 <= windows <= MAX_WINDOWS
            or type(window_seconds) is not int
            or not 1 <= window_seconds <= MAX_WINDOW_SECONDS):
        raise ValueError("window budgets are out of bounds")
    if (not finite_float(max_duration_seconds) or max_duration_seconds <= 0
            or type(max_file_bytes) is not int or max_file_bytes <= 0):
        raise ValueError("collection budgets are out of bounds")


def collect_one(
    row: dict[str, Any], out_dir: Path, *, windows: int = 4,
    window_seconds: int = 10,
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    rights_note: str = DEFAULT_RIGHTS_NOTE, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe", download_timeout: float = 360.0,
) -> dict[str, Any]:
    """Download, validate, measure, write one record, and always delete media."""
    _require_budgets(
        windows=windows, window_seconds=window_seconds,
        max_duration_seconds=max_duration_seconds,
        max_file_bytes=max_file_bytes)
    if not isinstance(rights_note, str) or not rights_note.strip():
        raise ValueError("rights note must be non-empty")
    reason = collect_skip_reason(
        row, max_duration_seconds=max_duration_seconds)
    if reason is not None:
        raise ValueError(f"entry is not collectable: {reason}")
    # Resolve and validate the signed URL immediately before download; the
    # catalog copy is the only media source and no redirect target is cached.
    stem = record_stem(row)
    try:
        url = _policy_video_url(row.get("videoUrl"))
    except ValueError as error:
        raise DownloadFailed(str(error)) from None
    record_path = Path(out_dir) / "videos" / f"{stem}.json"
    scratch = Path(tempfile.mkdtemp(prefix="kumiki-aicp-"))
    try:
        media_dir = scratch / "media"
        media_dir.mkdir()
        try:
            master_url = resolve_master_url(url)
            path, method = download_media(
                master_url, HLS, media_dir, allowed_hosts=MEDIA_HOSTS,
                max_bytes=max_file_bytes, ffmpeg=ffmpeg, ffprobe=ffprobe,
                timeout=download_timeout,
                max_duration_seconds=max_duration_seconds, allow_query=True)
        except Exception as error:  # noqa: BLE001 - classified for the index
            raise DownloadFailed(str(error)) from None
        try:
            source = source_metadata(path, ffprobe=ffprobe)
            if source["durationSeconds"] > max_duration_seconds:
                raise ValueError("source exceeds the bounded duration budget")
            coverage, measured = measure_windows(
                path, duration_seconds=source["durationSeconds"],
                window_count=windows, window_seconds=window_seconds,
                image_translation=False, ffmpeg=ffmpeg, ffprobe=ffprobe)
        except Exception as error:  # noqa: BLE001 - classified for the index
            raise ProbeFailed(str(error)) from None
        record = build_video_record(
            row, source=source, coverage=coverage, windows=measured,
            method=method, rights_note=rights_note)
        write_json_atomic(record_path, record)
        return record
    finally:
        # Hard guarantee: no media, frames, thumbnails, or audio survive.
        shutil.rmtree(scratch, ignore_errors=True)


def collect_still_one(
    row: dict[str, Any], out_dir: Path, *, max_bytes: int = STILL_MAX_BYTES,
    download_timeout: float = 60.0, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Download, probe, decode, measure one screenshot; retain no image."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("still image byte cap must be positive")
    if not finite_float(download_timeout) or download_timeout <= 0:
        raise ValueError("still image timeout must be positive")
    if as_text(row.get("posterUrl")) is None:
        raise ValueError("entry has no published screenshot")
    url = _policy_image_url(row.get("posterUrl"))
    stem = record_stem(row)
    record_path = Path(out_dir) / "stills" / f"{stem}.json"
    with tempfile.TemporaryDirectory(prefix="kumiki-aicp-still-") as directory:
        target = image_target(Path(directory), url)
        try:
            download_http(
                url, target, allowed_hosts=IMAGE_HOSTS, max_bytes=max_bytes,
                timeout=download_timeout, accept="image/*",
                label="screenshot still")
            image_bytes = target.stat().st_size
            digest = sha256_file(target)
            measured = measure_still(target, ffmpeg=ffmpeg, ffprobe=ffprobe)
        finally:
            # Guarantee: even a failed decode leaves no image bytes.
            target.unlink(missing_ok=True)
    record = build_still_record(row, still={
        "imageUrl": url, "imageSha256": digest,
        "imageFormat": still_image_format(url, measured.pop("imageCodec", None)),
        "imageBytes": image_bytes, **measured})
    write_json_atomic(record_path, record)
    return record


# ---------------------------------------------------------------------------
# batch lane driver
# ---------------------------------------------------------------------------


def _error_text(out_dir: Path) -> Callable[[Exception], str]:
    def render(error: Exception) -> str:
        if isinstance(error, DownloadFailed):
            reason = "download-failed"
        elif isinstance(error, ProbeFailed):
            reason = "probe-failed"
        else:
            reason = type(error).__name__
        text = safe_error(error, redact=(str(out_dir),))
        text = re.sub(r"^[A-Za-z_][A-Za-z0-9_.]*: ", "", text)
        text = re.sub(r"/[^\s:'\"]*kumiki-aicp-[^\s:'\"]*", "[scratch]", text)
        return f"{reason}: {text}"[:360]
    return render


def _load_retained(
    out_dir: Path, folder: str, schema: str,
    summary_row: Callable[[dict[str, Any], Path | None], dict[str, Any]],
) -> list[dict[str, Any]]:
    retained: list[dict[str, Any]] = []
    directory = out_dir / folder
    if not directory.is_dir():
        return retained
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict) and payload.get("schemaVersion") == schema:
            retained.append(summary_row(payload, path.relative_to(out_dir)))
    return retained


def _lane_items(
    rows: Iterable[dict[str, Any]], *, limit: int | None,
    static_reason: Callable[[dict[str, Any]], str | None],
) -> list[dict[str, Any]]:
    """Rows up to ``limit`` statically eligible items, keeping encountered skips.

    ``limit is None`` or ``0`` means every remaining row. Rows after the limit is
    reached are not included at all, so a smoke run never reports thousands of
    unrelated policy skips.
    """
    if limit is not None and limit == 0:
        limit = None
    items: list[dict[str, Any]] = []
    eligible = 0
    for row in rows:
        items.append(row)
        if static_reason(row) is None:
            eligible += 1
            if limit is not None and eligible >= limit:
                break
    return items


def _run_lane(
    items: Iterable[dict[str, Any]], *, out_dir: Path, folder: str,
    index_name: str, schema: str, catalog_sha: str,
    run_one: Callable[[dict[str, Any]], dict[str, Any]],
    summary_row: Callable[[dict[str, Any], Path | None], dict[str, Any]],
    detail: Callable[[dict[str, Any]], str], label: str, final_note: str,
    static_reason: Callable[[dict[str, Any]], str | None],
    retained: list[dict[str, Any]] | None = None,
    resume: bool = True, jobs: int = 1, delay_seconds: float = 0.0,
    limit: int | None = None, log: Callable[[str], None] = print,
) -> int:
    """Run one lane: policy/resume skips, atomic index, progress, exit code."""
    if type(jobs) is not int or not 1 <= jobs <= 3:
        raise ValueError("jobs must be between 1 and 3")
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("delay_seconds must be a non-negative number")
    retained = retained or []
    payloads = list(items)
    (out_dir / folder).mkdir(parents=True, exist_ok=True)
    index_path, details = out_dir / index_name, {}

    def tracked(row: dict[str, Any]) -> dict[str, Any]:
        record = run_one(row)
        details[str(row.get("id"))] = detail(record)
        return record

    def index_for(records: list[dict[str, Any]], skips: list[dict[str, Any]],
                  failures: list[dict[str, Any]]) -> dict[str, Any]:
        return build_index(
            schema_version=schema, records=[*retained, *records],
            skips=skips, failures=failures, generated_at=utc_now(),
            extra={"catalogSha256": catalog_sha, "limit": limit})

    def skip_reason(row: dict[str, Any]) -> str | None:
        try:
            stem = record_stem(row)
        except ValueError as error:
            return f"unsafe-slug: {error}"
        reason = static_reason(row)
        if reason is not None:
            return reason
        if not resume:
            return None
        return ("resume-existing-record" if resume_matches(
            out_dir / folder / f"{stem}.json", row.get("id")) else None)

    def report(position: int, total: int, status: str, label_text: str,
               text: str) -> None:
        print(f"[{position}/{total}] {status} {label_text} "
              f"{text or details.pop(label_text, '')}", flush=True)

    outcome = run_batch(
        payloads, run_one=tracked, index_path=index_path,
        build_index=index_for,
        summary_row=lambda record: summary_row(record, None),
        skip_row=_skip_row,
        describe=lambda row: str(row.get("slug") or row.get("id")),
        skip_reason=skip_reason, error_text=_error_text(out_dir),
        progress=report, jobs=jobs, delay_seconds=delay_seconds)
    log(f"{label}={len(retained) + outcome.measured} skipped={outcome.skipped} "
        f"failed={outcome.failed} attempted={outcome.attempted} "
        f"elapsed={outcome.elapsed_seconds:.1f}s index={index_path}")
    log(final_note)
    return 1 if outcome.attempted and not (retained or outcome.measured) else 0


def run_collect(
    catalog_path: Path, *, out_dir: Path, limit: int | None = None,
    resume: bool = True, jobs: int = 1, acknowledge_rights: bool = False,
    delay_seconds: float = DEFAULT_VIDEO_DELAY, windows: int = 4,
    window_seconds: int = 10,
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    rights_note: str = DEFAULT_RIGHTS_NOTE, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe", log: Callable[[str], None] = print,
) -> int:
    """Measure eligible catalog entries; ``--limit 0`` means all remaining."""
    if acknowledge_rights is not True:
        raise ValueError(
            "explicit --acknowledge-rights attestation is required: public "
            "availability is not a license, and each downloaded file is "
            "deleted after numeric measurement")
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a non-negative integer")
    if type(jobs) is not int or not 1 <= jobs <= 2:
        raise ValueError("jobs must be between 1 and 2")
    _require_budgets(
        windows=windows, window_seconds=window_seconds,
        max_duration_seconds=max_duration_seconds,
        max_file_bytes=max_file_bytes)
    catalog_file = Path(catalog_path)
    catalog_sha = sha256_file(catalog_file)
    rows = _load_catalog(catalog_file)["entries"]
    out_dir = Path(out_dir)
    static = partial(
        collect_skip_reason, max_duration_seconds=max_duration_seconds)
    items = _lane_items(rows, limit=limit, static_reason=static)
    retained = (_load_retained(out_dir, "videos", VIDEO_SCHEMA,
                               _video_summary_row) if resume else [])
    return _run_lane(
        items, out_dir=out_dir, folder="videos", index_name="index.json",
        schema=INDEX_SCHEMA, catalog_sha=catalog_sha,
        run_one=lambda row: collect_one(
            row, out_dir, windows=windows, window_seconds=window_seconds,
            max_duration_seconds=max_duration_seconds,
            max_file_bytes=max_file_bytes, rights_note=rights_note,
            ffmpeg=ffmpeg, ffprobe=ffprobe),
        summary_row=_video_summary_row, detail=_video_detail,
        label="measured",
        final_note="all downloaded media was deleted; only numeric evidence "
                   "and catalog metadata remain",
        static_reason=static, retained=retained, resume=resume, jobs=jobs,
        delay_seconds=delay_seconds, limit=limit, log=log)


def _still_static_reason(row: dict[str, Any]) -> str | None:
    return None if as_text(row.get("posterUrl")) else "no-poster"


def run_stills(
    catalog_path: Path, *, out_dir: Path, limit: int | None = None,
    resume: bool = True, jobs: int = 1,
    delay_seconds: float = DEFAULT_STILL_DELAY,
    max_bytes: int = STILL_MAX_BYTES, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe", log: Callable[[str], None] = print,
) -> int:
    """Measure one published screenshot per entry; never fetch video."""
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a non-negative integer")
    if type(jobs) is not int or not 1 <= jobs <= 3:
        raise ValueError("jobs must be between 1 and 3")
    catalog_file = Path(catalog_path)
    catalog_sha = sha256_file(catalog_file)
    rows = _load_catalog(catalog_file)["entries"]
    out_dir = Path(out_dir)
    items = _lane_items(rows, limit=limit, static_reason=_still_static_reason)
    retained = (_load_retained(out_dir, "stills", STILL_SCHEMA,
                               _still_summary_row) if resume else [])
    return _run_lane(
        items, out_dir=out_dir, folder="stills",
        index_name="stills-index.json", schema=STILLS_INDEX_SCHEMA,
        catalog_sha=catalog_sha,
        run_one=lambda row: collect_still_one(
            row, out_dir, max_bytes=max_bytes, ffmpeg=ffmpeg,
            ffprobe=ffprobe),
        summary_row=_still_summary_row, detail=_still_detail,
        label="still-measured",
        final_note="all downloaded screenshots were deleted; only hashes and "
                   "numbers remain",
        static_reason=_still_static_reason, retained=retained, resume=resume,
        jobs=jobs, delay_seconds=delay_seconds, limit=limit, log=log)


# ---------------------------------------------------------------------------
# report: read-only, evidence-bound aggregation
# ---------------------------------------------------------------------------

_NULL_CELL = "—"
DETAIL_LIMIT_REMINDER = (
    "sampled source-PTS windows only (not full-film review); numeric display-RGB "
    "and cut-candidate proxies are not style, quality, lighting, editing-intent, "
    "or authorship labels.")


def _write_text_atomic(path: Path, text: str) -> Path:
    """Commit one UTF-8 text file via a same-directory temp file and rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=path.name + ".",
        suffix=".tmp", delete=False)
    temporary = Path(staging.name)
    try:
        with staging:
            staging.write(text)
            staging.flush()
            os.fsync(staging.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _load_records(
    directory: Path, expected_schema: str, *, prefix: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Read every ``*.json`` record in stable name order; isolate bad files."""
    records: list[dict[str, Any]] = []
    problems: list[dict[str, str]] = []
    if not directory.is_dir():
        return records, problems
    for path in sorted(directory.glob("*.json")):
        relative = f"{prefix}/{path.name}"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            problems.append({"file": relative,
                             "reason": f"{type(error).__name__}: {error}"})
            continue
        if not isinstance(payload, dict):
            problems.append({"file": relative,
                             "reason": "record is not a JSON object"})
            continue
        if payload.get("schemaVersion") != expected_schema:
            problems.append({
                "file": relative,
                "reason": (f"unexpected schemaVersion "
                           f"{payload.get('schemaVersion')!r}")})
            continue
        records.append(payload)
    return records, problems


def _load_json_context(
    path: Path | None, *, prefix: str,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    if path is None or not path.is_file():
        return None, []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return None, [{"file": prefix,
                       "reason": f"{type(error).__name__}: {error}"}]
    if not isinstance(payload, dict):
        return None, [{"file": prefix, "reason": "document is not a JSON object"}]
    return payload, []


def _record_key(record: dict[str, Any]) -> tuple[str, str]:
    entry_id = as_text(record.get("id"))
    if entry_id is not None:
        return ("id", entry_id)
    slug = as_text(record.get("slug"))
    return ("slug", slug) if slug is not None else ("unknown", "")


def _mean_pair_delta_per_second(probe: dict[str, Any]) -> float | None:
    pairs = probe.get("sampledFramePairs")
    if not isinstance(pairs, list):
        return None
    values = [value for pair in pairs if isinstance(pair, dict)
              for value in (finite_float(
                  pair.get("meanAbsoluteDisplayRgbDeltaPerSecond")),)
              if value is not None]
    return round(statistics.mean(values), 6) if values else None


def _window_row(window: object) -> dict[str, Any]:
    if not isinstance(window, dict):
        window = {}
    probe = window.get("probe") if isinstance(window.get("probe"), dict) else {}
    summary = (probe.get("sampledWindowSummary")
               if isinstance(probe.get("sampledWindowSummary"), dict) else {})
    frames = probe.get("sampledFrames")
    start = finite_float(window.get("startSeconds"))
    end = finite_float(window.get("endSeconds"))
    seconds = (round(end - start, 6)
               if start is not None and end is not None else None)
    return {
        "startSeconds": start,
        "endSeconds": end,
        "windowSeconds": seconds,
        "sampledFrames": len(frames) if isinstance(frames, list) else None,
        "cutCandidates": as_int(
            summary.get("cutCandidateCountBetweenFirstAndLastSample")),
        "meanDisplayLuma": finite_float(
            summary.get("meanSampledDisplayLumaProxy")),
        "meanSaturation": finite_float(
            summary.get("meanSampledSaturationProxy")),
        "withinShotDeltaPerSecond": _mean_pair_delta_per_second(probe),
        "cutSeparatedPairs": as_int(summary.get("cutSeparatedPairs")),
    }


def _video_row(record: dict[str, Any]) -> dict[str, Any]:
    """Derive one per-video table row strictly from embedded record fields."""
    catalog = record.get("catalog") if isinstance(record.get("catalog"), dict) else {}
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    acquisition = (record.get("acquisition")
                   if isinstance(record.get("acquisition"), dict) else {})
    coverage = record.get("coverage") if isinstance(record.get("coverage"), dict) else {}
    summary = record.get("summary") if isinstance(record.get("summary"), dict) else {}
    resolution = source.get("resolution")
    resolution_text = None
    if isinstance(resolution, (list, tuple)) and len(resolution) == 2:
        width, height = as_int(resolution[0]), as_int(resolution[1])
        if width is not None and height is not None:
            resolution_text = f"{width}x{height}"
    frame_rate = (source.get("frameRate")
                  if isinstance(source.get("frameRate"), dict) else {})
    numerator = finite_float(frame_rate.get("numerator"))
    denominator = finite_float(frame_rate.get("denominator"))
    fps = (round(numerator / denominator, 6)
           if numerator is not None and denominator else None)
    duration = finite_float(source.get("durationSeconds"))
    size = finite_float(source.get("sizeBytes"))
    bitrate = (round(size * 8 / duration / 1_000_000, 6)
               if size is not None and duration is not None and duration > 0
               else None)
    windows = record.get("windows") if isinstance(record.get("windows"), list) else []
    window_rows = [_window_row(window) for window in windows]
    cuts = cut_columns(record)
    fraction = finite_float(coverage.get("fractionOfRuntime"))
    video_types = catalog.get("videoType")
    if not isinstance(video_types, list):
        video_types = []
    return {
        "id": record.get("id"),
        "slug": record.get("slug"),
        "title": catalog.get("title"),
        "year": as_int(catalog.get("year")),
        "company": catalog.get("company"),
        "videoType": [str(value) for value in video_types],
        "durationText": catalog.get("durationText"),
        "provider": acquisition.get("provider"),
        "mediaSha256": source.get("mediaSha256"),
        "runtimeSeconds": duration,
        "resolution": resolution_text,
        "fps": fps,
        "bitrateMbps": bitrate,
        "downloadMb": (round(size / (1024 * 1024), 6)
                       if size is not None else None),
        "windowsMeasured": as_int(coverage.get("windowsMeasured")),
        "coveragePercent": (round(fraction * 100, 6)
                            if fraction is not None else None),
        "sampledSeconds": finite_float(coverage.get("sampledSeconds")),
        "cutCandidates": as_int(summary.get("cutCandidates")),
        "cutsPerMinute": finite_float(summary.get("cutCandidateRatePerMinute")),
        "candidateCount": cuts["candidate_count"],
        "sampledCutCandidatesPerMinute": cuts["candidates_per_min"],
        "ci95": cuts["ci95"],
        "medianGapFrames": cuts["median_gap_frames"],
        "burstFraction": cuts["burst_fraction"],
        "withinShotPairs": cuts["within_shot_pairs"],
        "cutSeparatedPairs": cuts["cut_separated_pairs"],
        "deltaBasisPairs": cuts["delta_basis_pairs"],
        "validityFlags": cuts["validity_flags"],
        "rankable": cuts["rankable"],
        "meanDisplayLuma": finite_float(summary.get("meanDisplayLuma")),
        "meanSaturation": finite_float(summary.get("meanSaturation")),
        "meanWithinShotDeltaPerSecond": finite_float(
            summary.get("meanWithinShotRgbDeltaPerSecond")),
        "windowRows": window_rows,
    }


def _video_order(row: dict[str, Any]) -> tuple[bool, int, str, str]:
    """Newest year first, then title, then id; missing years sort last."""
    year = row.get("year")
    return (year is None, -(year or 0), str(row.get("title") or ""),
            str(row.get("id") or ""))


def _table_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "windowRows"}


def _distribution(values: Iterable[float | None], *,
                  digits: int = 6) -> dict[str, Any]:
    numbers = [value for value in values if value is not None]
    if not numbers:
        return {"n": 0, "min": None, "median": None, "max": None}
    return {"n": len(numbers), "min": round(min(numbers), digits),
            "median": round(statistics.median(numbers), digits),
            "max": round(max(numbers), digits)}


def _counter(values: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        text = as_text(value) or "unknown"
        counts[text] = counts.get(text, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _type_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        types = row.get("videoType") or []
        if not types:
            counts["unknown"] = counts.get("unknown", 0) + 1
        for value in types:
            text = str(value)
            counts[text] = counts.get(text, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _coverage_aggregate(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    runtimes = [row["runtimeSeconds"] for row in rows
                if row.get("runtimeSeconds") is not None
                and row["runtimeSeconds"] > 0]
    paired = [(row["runtimeSeconds"], row["sampledSeconds"]) for row in rows
              if row.get("runtimeSeconds") is not None
              and row["runtimeSeconds"] > 0
              and row.get("sampledSeconds") is not None]
    total_runtime = (round(sum(runtime for runtime, _ in paired), 6)
                     if paired else 0.0)
    total_sampled = (round(sum(sampled for _, sampled in paired), 6)
                     if paired else 0.0)
    return {
        "recordsWithRuntime": len(runtimes),
        "recordsWithCoverage": len(paired),
        "totalRuntimeSeconds": total_runtime,
        "totalSampledSeconds": total_sampled,
        "sampledFractionOfTotalRuntime": (
            round(total_sampled / total_runtime, 6) if total_runtime else None),
        "perRecordCoveragePercent": _distribution(
            row.get("coveragePercent") for row in rows),
    }


def _skip_reasons(index: dict[str, Any] | None) -> dict[str, int]:
    rows = index.get("skips") if isinstance(index, dict) else None
    if not isinstance(rows, list):
        return {}
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        reason = as_text(row.get("reason")) or "unknown"
        counts[reason] = counts.get(reason, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _index_measured(index: dict[str, Any] | None) -> int | None:
    if not isinstance(index, dict):
        return None
    counts = index.get("counts")
    if isinstance(counts, dict):
        measured = as_int(counts.get("measured"))
        if measured is not None:
            return measured
    rows = index.get("records")
    return len(rows) if isinstance(rows, list) else None


def _list_length(index: dict[str, Any] | None, key: str) -> int:
    rows = index.get(key) if isinstance(index, dict) else None
    return len(rows) if isinstance(rows, list) else 0


def _still_metrics(record: dict[str, Any]) -> dict[str, Any]:
    still = record.get("still") if isinstance(record.get("still"), dict) else {}
    metrics = still.get("metrics") if isinstance(still.get("metrics"), dict) else {}
    return metrics


def _latest_timestamp(records: Iterable[dict[str, Any]],
                      catalog: dict[str, Any] | None) -> str | None:
    stamps = [text for record in records
              for text in (as_text(record.get("generatedAt")),)
              if text is not None]
    if stamps:
        return max(stamps)
    return as_text(catalog.get("generatedAt")) if isinstance(catalog, dict) else None


def _num(value: float | None, digits: int = 2) -> str:
    return _NULL_CELL if value is None else f"{value:.{digits}f}"


def _int(value: int | None) -> str:
    return _NULL_CELL if value is None else str(value)


def _cell(value: object) -> str:
    text = _NULL_CELL if value is None else str(value)
    if not text:
        text = _NULL_CELL
    return text.replace("|", "\\|").replace("\n", " ")


def _reproduce_commands(*, out_dir: Path, catalog_path: Path,
                        top: int) -> list[str]:
    out, catalog = shlex.quote(str(out_dir)), shlex.quote(str(catalog_path))
    return [
        "python scripts/research_aicp.py catalog "
        f"--out {catalog}",
        "python scripts/research_aicp.py stills "
        f"--catalog {catalog} --out-dir {out} --resume",
        "python scripts/research_aicp.py collect "
        f"--catalog {catalog} --out-dir {out} --acknowledge-rights",
        f"python scripts/research_aicp.py report --out-dir {out} --top {top}",
    ]


def _render_report(aggregate: dict[str, Any], *,
                   out_dir: Path, catalog_path: Path, top: int,
                   catalog_present: bool) -> str:
    counts = aggregate["counts"]
    video_rows = aggregate["videos"]
    details = aggregate["details"]
    video_aggregates = aggregate["aggregates"]
    stills = aggregate["stills"]
    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    add("# AICP Awards — measured reference report")
    add()
    add("This deliverable tabulates only what the committed evidence records "
        "contain: catalog metadata, sampled source-PTS numeric probes, and "
        "single-published-screenshot metrics. It makes no aesthetic, stylistic, "
        "intentional, award-level, or authorship claim.")
    add()

    add("## Provenance")
    add()
    add(f"- Catalog entries reported by the archive: "
        f"{_int(counts['catalogTotalReported'])}")
    add(f"- Catalog entries collected into the catalog file: "
        f"{_int(counts['catalogCollected'])}")
    add(f"- Video-measured records: {_int(counts['videoMeasured'])}")
    add(f"- Unique media after dedupe: {_int(counts.get('videoUniqueMedia'))} "
        f"({_int(counts.get('videoDuplicateExtra'))} extra record(s) in "
        f"{_int(counts.get('videoDuplicateGroups'))} duplicate group(s))")
    add(f"- Still-measured records: {_int(counts['stillMeasured'])}")
    add(f"- Still-only records (no matching video record): "
        f"{_int(counts['stillOnly'])}")
    add(f"- Skipped by policy (index context): {_int(counts['skippedPolicy'])}")
    add(f"- Skipped as already-measured (index context): "
        f"{_int(counts['skippedResume'])}")
    add(f"- Failed video acquisitions (index context): "
        f"{_int(counts['failed'])}")
    add(f"- Failed still acquisitions (stills index context): "
        f"{_int(counts['stillFailed'])}")
    add(f"- Unreadable records: {_int(counts['unreadable'])}")
    add(f"- generatedAt: {_cell(aggregate.get('generatedAt'))}")
    if not catalog_present:
        add("- Note: no catalog file was present, so reported/collected catalog "
            "counts are unavailable in this context.")
    if (counts["indexReportedVideoMeasured"] is not None
            and counts["indexReportedVideoMeasured"] != counts["videoMeasuredTotal"]):
        add(f"- Note: index.json reports {counts['indexReportedVideoMeasured']} "
            f"measured video records while the record directory holds "
            f"{counts['videoMeasuredTotal']}; this report reads the record files.")
    if (counts["indexReportedStillMeasured"] is not None
            and counts["indexReportedStillMeasured"] != counts["stillMeasured"]):
        add(f"- Note: stills-index.json reports "
            f"{counts['indexReportedStillMeasured']} measured stills while the "
            f"record directory holds {counts['stillMeasured']}.")
    add()
    add("Reproduce the inputs and this report with:")
    add()
    add("```bash")
    for command in _reproduce_commands(
            out_dir=out_dir, catalog_path=catalog_path, top=top):
        add(command)
    add("```")
    add()
    add("Sampling caveat: coverage is `windows measured × window seconds ÷ "
        "runtime`; every window is a sample, not a full-film review. Across the "
        "tabulated records, "
        f"{_num(video_aggregates['coverage']['totalSampledSeconds'], 1)} s of "
        f"{_num(video_aggregates['coverage']['totalRuntimeSeconds'], 1)} s of "
        "runtime were measured "
        f"({_num((video_aggregates['coverage']['sampledFractionOfTotalRuntime'] or 0) * 100, 1)}%).")
    add()

    add("## Per-video analysis")
    add()
    add(f"{len(video_rows)} video-measured record(s), ordered by descending "
        "year, then title, then id. All columns are numeric record fields; "
        "`bitrate_mbps` is derived from `sizeBytes ÷ durationSeconds` and "
        "`duration_s` is the decoded local source duration, not the catalog's "
        "self-reported `durationText`.")
    add()
    columns = (
        "year", "title", "company", "video_type", "duration_text",
        "duration_s", "resolution", "fps", "bitrate_mbps", "windows",
        "coverage_pct", "candidates_n", "sampled_cut_candidates_per_min",
        "ci95", "burst", "gap_frames", "within_shot_pairs", "cut_sep_pairs",
        "delta_basis_pairs", "validity", "mean_luma", "mean_sat", "delta_per_s")
    add("| " + " | ".join(columns) + " |")
    add("| " + " | ".join("---" for _ in columns) + " |")
    for row in video_rows:
        ci = row["ci95"]
        values = (
            _int(row["year"]), row["title"], row["company"],
            ", ".join(row["videoType"]) or None, row["durationText"],
            _num(row["runtimeSeconds"], 2), row["resolution"],
            _num(row["fps"], 3), _num(row["bitrateMbps"], 2),
            _int(row["windowsMeasured"]), _num(row["coveragePercent"], 1),
            _int(row["candidateCount"]),
            _num(row["sampledCutCandidatesPerMinute"], 2),
            (f"{_num(ci[0], 2)}-{_num(ci[1], 2)}" if ci else None),
            _num(row["burstFraction"], 3), _num(row["medianGapFrames"], 1),
            _int(row["withinShotPairs"]), _int(row["cutSeparatedPairs"]),
            _int(row["deltaBasisPairs"]),
            ", ".join(row["validityFlags"]) or "—",
            _num(row["meanDisplayLuma"], 4), _num(row["meanSaturation"], 4),
            _num(row["meanWithinShotDeltaPerSecond"], 4))
        add("| " + " | ".join(_cell(value) for value in values) + " |")
    add()

    add(f"## Per-video detail (top {len(details)} by report order)")
    add()
    if not details:
        add("No video-measured records.")
        add()
    for row, detail in zip(video_rows, details):
        add(f"### {_cell(row['id'])} — {_cell(row['title'])}")
        add()
        add("| field | value |")
        add("| --- | --- |")
        for label, value in (
                ("year", _int(row["year"])), ("company", row["company"]),
                ("video_type", ", ".join(row["videoType"]) or None),
                ("duration_text", row["durationText"]),
                ("duration_s", _num(row["runtimeSeconds"], 2)),
                ("resolution", row["resolution"]),
                ("fps", _num(row["fps"], 3)),
                ("bitrate_mbps", _num(row["bitrateMbps"], 2)),
                ("download_mb", _num(row["downloadMb"], 1)),
                ("windows", _int(row["windowsMeasured"])),
                ("coverage_pct", _num(row["coveragePercent"], 1)),
                ("candidates_n", _int(row["candidateCount"])),
                ("sampled_cut_candidates_per_min",
                 _num(row["sampledCutCandidatesPerMinute"], 2)),
                ("ci95", (f"{_num(row['ci95'][0], 2)}-{_num(row['ci95'][1], 2)}"
                          if row["ci95"] else None)),
                ("burst", _num(row["burstFraction"], 3)),
                ("gap_frames", _num(row["medianGapFrames"], 1)),
                ("within_shot_pairs", _int(row["withinShotPairs"])),
                ("cut_sep_pairs", _int(row["cutSeparatedPairs"])),
                ("delta_basis_pairs", _int(row["deltaBasisPairs"])),
                ("validity", ", ".join(row["validityFlags"]) or "—"),
                ("mean_luma", _num(row["meanDisplayLuma"], 4)),
                ("mean_sat", _num(row["meanSaturation"], 4)),
                ("delta_per_s", _num(row["meanWithinShotDeltaPerSecond"], 4))):
            add(f"| {label} | {_cell(value)} |")
        add()
        add("| window_s | start_s | sampled_frames | cut_candidates | "
            "mean_luma | mean_sat | delta_per_s |")
        add("| --- | --- | --- | --- | --- | --- | --- |")
        windows = detail.get("windows") if isinstance(detail.get("windows"), list) else []
        for window in windows:
            values = (
                _num(window["windowSeconds"], 2),
                _num(window["startSeconds"], 2),
                _int(window["sampledFrames"]),
                _int(window["cutCandidates"]),
                _num(window["meanDisplayLuma"], 4),
                _num(window["meanSaturation"], 4),
                _num(window["withinShotDeltaPerSecond"], 4))
            add("| " + " | ".join(values) + " |")
        add()
        add(f"limits: {DETAIL_LIMIT_REMINDER}")
        add()

    add("## Aggregates (video-measured records only)")
    add()
    add("Every number in this section is computed ONLY over the video-measured "
        "records tabulated above. Published screenshots, including still-only "
        "entries, never enter the motion, cut, luma, or saturation aggregates.")
    add()
    add("### Distributions")
    add()
    add("All minima and maxima are computed over `rankable` records only and "
        "name the record id and validity flags.")
    add()
    ranking = video_aggregates["cutRanking"]
    add(f"Unique records before dedupe: "
        f"{video_aggregates.get('recordCountBeforeDedupe')}; after dedupe: "
        f"{video_aggregates.get('recordCount')} "
        f"({(video_aggregates.get('dedupe') or {}).get('extraRecords', 0)} "
        "duplicate extra record(s) collapsed).")
    add()
    add(f"Rankable records: {ranking['rankable']} of "
        f"{video_aggregates['recordCount']} unique; excluded as non-rankable: "
        f"{ranking['excluded']}.")
    add()
    add("| metric | n | min (record; flags) | median | max (record; flags) |")
    add("| --- | --- | --- | --- | --- |")
    for label, extremes, digits in (
            ("runtime_s", ranking["runtimeSeconds"], 2),
            ("candidates_n", ranking["candidateCount"], 0),
            ("sampled_cut_candidates_per_min", ranking["candidatesPerMinute"], 2),
            ("mean_luma", ranking["meanDisplayLuma"], 4),
            ("mean_sat", ranking["meanSaturation"], 4)):
        add(f"| {label} | {extremes['n']} | "
            f"{_cell(extreme_text(extremes['min'], digits=digits))} | "
            f"{_num(extremes['median'], digits)} | "
            f"{_cell(extreme_text(extremes['max'], digits=digits))} |")
    for line in excluded_leaders_lines(
            ranking["candidatesPerMinute"],
            metric="sampled_cut_candidates_per_min"):
        add(line)
    add()

    coverage = video_aggregates["coverage"]
    add("Coverage-weighted caveat: "
        f"{_num(coverage['totalSampledSeconds'], 1)} sampled seconds cover "
        f"{_num(coverage['totalRuntimeSeconds'], 1)} runtime seconds "
        f"({_num((coverage['sampledFractionOfTotalRuntime'] or 0) * 100, 1)}%). "
        "Aggregates describe the sampled windows, not the full films.")
    add()

    add("## Comparability")
    add()
    for line in comparability_lines(video_aggregates["comparability"]):
        add(line)
    add()

    add("## Coverage")
    add()
    add("Per-record coverage distribution over the deduped records. The "
        "unobserved gap is the median time between consecutive sampled windows, "
        "derived from runtime, window count and sampled seconds.")
    add()
    for line in coverage_lines(video_aggregates["coverageDistribution"]):
        add(line)
    add()

    add("### By year")
    add()
    add("| year | records |")
    add("| --- | --- |")
    for key, value in video_aggregates["byYear"].items():
        add(f"| {_cell(key)} | {value} |")
    add()
    add("### By video type")
    add()
    add("A record contributes to every distinct type listed in its catalog row; "
        "rows without a type are counted once as `unknown`.")
    add()
    add("| video_type | records |")
    add("| --- | --- |")
    for key, value in video_aggregates["byVideoType"].items():
        add(f"| {_cell(key)} | {value} |")
    add()

    add("## Skip reasons (index context)")
    add()
    if not aggregate["skipReasons"]:
        add("No skip rows were present in the index.")
    else:
        add("| reason | rows |")
        add("| --- | --- |")
        for key, value in aggregate["skipReasons"].items():
            add(f"| {_cell(key)} | {value} |")
    add()

    add("## Published-screenshot evidence (single-frame only)")
    add()
    add("Separate lane. A published screenshot is not a video frame: these "
        "numbers are single-frame image metrics, carry no motion, cut, pacing, "
        "or timing evidence, and are never used in the video aggregates above.")
    add()
    add(f"- n: {stills['n']}")
    add("- decode size: screenshots are measured at the aspect-preserving "
        "`160×90` fit; the source dimensions stay in `img_w×img_h`, so the "
        "decode size is derived from the source aspect, not stored per record.")
    add()
    add("| source_img | decode | stills |")
    add("| --- | --- | --- |")
    decode_items = sorted(
        (stills.get("decodeSizes") or {}).items(),
        key=lambda item: (-item[1], item[0]))
    for key, value in decode_items[:20]:
        source, decode = key.split(" -> ", 1)
        add(f"| {_cell(source)} | {_cell(decode)} | {value} |")
    if len(decode_items) > 20:
        add(f"| (+{len(decode_items) - 20} more source/decode pairs) | — | — |")
    add()
    add(f"- stills carrying no quality flag (used for colour aggregates): "
        f"{stills.get('evidenceN', stills['n'])}")
    add(f"- median meanDisplayLumaProxy: "
        f"{_num(stills['medianMeanDisplayLumaProxy'], 4)}")
    add()
    add("| dominant_hue_family | stills |")
    add("| --- | --- |")
    for key, value in stills["dominantHueFamilyCounts"].items():
        add(f"| {_cell(key)} | {value} |")
    add()

    add("## Unreadable records")
    add()
    if not aggregate["unreadableRecords"]:
        add("None.")
    else:
        add("Malformed or wrong-schema files are skipped; all other records "
            "are still reported.")
        add()
        add("| file | reason |")
        add("| --- | --- |")
        for problem in aggregate["unreadableRecords"]:
            add(f"| {_cell(problem['file'])} | {_cell(problem['reason'])} |")
    add()

    add("## Explicit non-claims")
    add()
    for claim in (
            "No style, aesthetic quality, mood, lighting, camera/lens, "
            "editorial intent, authorship, identity, or creative-origin "
            "inference is made from these numbers.",
            "Display-RGB luma/saturation and cut candidates are numeric proxies "
            "only, not semantic labels.",
            "Windows are sampled; `fullRuntimeMeasured` is false for every video "
            "record, so nothing here is a full-film review.",
            "Public availability is not a licence: `rightsStatus` remains "
            "`review-required`, and reuse needs its own review.",
            "No award level is claimed: the archive exposes no gold/silver/bronze "
            "field, and membership in `commercialsEntries` is the only honoree "
            "signal.",
            "Agency, director, and producer credits are absent for most entries; "
            "`company` is reported only where the archive populates it.",
            "Screenshots are single published images, not video frames, and "
            "carry no motion, cut, pacing, or timing evidence.",
            "Signed CDN redirect targets are never persisted; only the "
            "catalog's public HLS entry URL appears in records.",
            "Catalog metadata (title, year, company, video type, categories) is "
            "self-reported by aicpawards.com and is not independently verified.",
            "Downloaded media, frames, thumbnails, and audio are never retained."):
        add(f"- {claim}")
    add()
    return "\n".join(lines)


def run_report(
    out_dir: Path, *, top: int = DEFAULT_TOP, log: Callable[[str], None] = print,
) -> int:
    """Read collected records read-only and write ``report.md`` + ``aggregate.json``."""
    if type(top) is not int or top < 0:
        raise ValueError("top must be a non-negative integer")
    out_dir = Path(out_dir)
    default_catalog = out_dir / "catalog.json"
    catalog_path = default_catalog if default_catalog.is_file() else out_dir / "catalog.json"

    video_records, problems = _load_records(
        out_dir / "videos", VIDEO_SCHEMA, prefix="videos")
    still_records, still_problems = _load_records(
        out_dir / "stills", STILL_SCHEMA, prefix="stills")
    problems.extend(still_problems)
    catalog, catalog_problems = _load_json_context(
        default_catalog, prefix="catalog.json")
    index, index_problems = _load_json_context(
        out_dir / "index.json", prefix="index.json")
    stills_index, stills_index_problems = _load_json_context(
        out_dir / "stills-index.json", prefix="stills-index.json")
    problems.extend(catalog_problems)
    problems.extend(index_problems)
    problems.extend(stills_index_problems)
    problems.sort(key=lambda item: (item["file"], item["reason"]))

    generated_at = _latest_timestamp(
        [*video_records, *still_records], catalog)

    rows = sorted((_video_row(record) for record in video_records),
                  key=_video_order)
    measured_total = len(rows)
    details = [{"id": row["id"], "windows": row["windowRows"]}
               for row in rows[:top]]
    table_rows = [_table_row(row) for row in rows]
    unique_rows = list(unique_media_rows(rows))
    dedupe = duplicate_summary(
        [{"id": row["id"], "mediaSha256": row["mediaSha256"]}
         for row in rows], "mediaSha256")

    video_keys = {_record_key(record) for record in video_records}
    still_only = sum(1 for record in still_records
                     if _record_key(record) not in video_keys)

    skip_reasons = _skip_reasons(index)
    policy_skips = sum(value for key, value in skip_reasons.items()
                       if key in POLICY_SKIP_REASONS)
    still_evidence = [record for record in still_records
                      if not still_has_quality_flags(record)]
    still_metrics = [_still_metrics(record) for record in still_evidence]
    still_lumas = [finite_float(metrics.get("meanDisplayLumaProxy"))
                   for metrics in still_metrics]
    still_lumas = [value for value in still_lumas if value is not None]
    catalog_counts = (catalog.get("counts")
                      if isinstance(catalog, dict)
                      and isinstance(catalog.get("counts"), dict) else {})

    aggregate = {
        "schemaVersion": AGGREGATE_SCHEMA,
        "generatedAt": generated_at,
        "counts": {
            "catalogTotalReported": as_int(
                catalog_counts.get("totalReported")),
            "catalogCollected": as_int(catalog_counts.get("collected")),
            "videoMeasured": len(table_rows),
            "videoMeasuredTotal": measured_total,
            "videoUniqueMedia": len(unique_rows),
            "videoDuplicateGroups": dedupe["groups"],
            "videoDuplicateExtra": dedupe["extraRecords"],
            "stillMeasured": len(still_records),
            "stillOnly": still_only,
            "skippedPolicy": policy_skips,
            "skippedResume": skip_reasons.get("resume-existing-record", 0),
            "failed": _list_length(index, "failures"),
            "stillFailed": _list_length(stills_index, "failures"),
            "unreadable": len(problems),
            "indexReportedVideoMeasured": _index_measured(index),
            "indexReportedStillMeasured": _index_measured(stills_index),
        },
        "videos": table_rows,
        "details": details,
        "aggregates": {
            "basis": ("video-measured records only; published screenshots "
                      "never enter these numbers"),
            "recordCount": len(unique_rows),
            "recordCountBeforeDedupe": len(rows),
            "dedupe": dedupe,
            "byYear": _counter(
                str(row["year"]) if row["year"] is not None else None
                for row in unique_rows),
            "byVideoType": _type_counts(unique_rows),
            "distributions": {
                "runtimeSeconds": _distribution(
                    row["runtimeSeconds"] for row in unique_rows),
                "cutsPerMinute": _distribution(
                    row["sampledCutCandidatesPerMinute"] for row in unique_rows
                    if row["rankable"]),
                "sampledCutCandidatesPerMinute": _distribution(
                    row["sampledCutCandidatesPerMinute"] for row in unique_rows
                    if row["rankable"]),
                "candidateCount": _distribution(
                    row["candidateCount"] for row in unique_rows
                    if row["rankable"]),
                "meanDisplayLuma": _distribution(
                    row["meanDisplayLuma"] for row in unique_rows),
                "meanSaturation": _distribution(
                    row["meanSaturation"] for row in unique_rows),
            },
            "cutRanking": {
                "basis": "rankable unique records only; non-rankable rows are "
                         "excluded from cut aggregates",
                "rankable": sum(1 for row in unique_rows if row["rankable"]),
                "excluded": sum(1 for row in unique_rows
                                if not row["rankable"]),
                "candidatesPerMinute": aggregate_extremes(
                    unique_rows, "sampledCutCandidatesPerMinute", id_key="id",
                    gate=True),
                "candidateCount": aggregate_extremes(
                    unique_rows, "candidateCount", id_key="id", gate=True),
                "runtimeSeconds": aggregate_extremes(
                    unique_rows, "runtimeSeconds", id_key="id",
                    gate=True),
                "meanDisplayLuma": aggregate_extremes(
                    unique_rows, "meanDisplayLuma", id_key="id",
                    gate=True),
                "meanSaturation": aggregate_extremes(
                    unique_rows, "meanSaturation", id_key="id",
                    gate=True),
                "meanWithinShotDeltaPerSecond": aggregate_extremes(
                    unique_rows, "meanWithinShotDeltaPerSecond",
                    id_key="id", gate=True),
            },
            "coverage": _coverage_aggregate(unique_rows),
            "coverageDistribution": coverage_distribution(unique_rows),
            "comparability": comparability_block(
                site="AICP Awards",
                catalog_size=as_int(catalog_counts.get("collected")),
                measured=len(rows),
                selection_rule=("public HLS availability in catalogue order "
                                "with a duration and byte budget"),
                provider_counts=_counter(row["provider"] for row in unique_rows),
                rendition_notes=("signed CDN HLS renditions only; the signed "
                                 "target is never persisted"),
                resolution_counts=_counter(row["resolution"] for row in unique_rows),
                fps_counts=_counter(
                    f"{row['fps']:g}" if row["fps"] is not None else None
                    for row in unique_rows),
                bitrate_counts=_counter(
                    f"{row['bitrateMbps']:.1f}"
                    if row["bitrateMbps"] is not None else None
                    for row in unique_rows),
                coverage=coverage_distribution(unique_rows),
                duplicate_groups=dedupe,
                still_overlap=(f"{len(still_records)} still record(s), "
                               f"{still_only} still-only, are a separate "
                               "single-frame lane and never enter these "
                               "aggregates"),
            ),
        },
        "skipReasons": skip_reasons,
        "stills": {
            "evidence": STILL_EVIDENCE_STATUS,
            "singleFrameOnly": True,
            "n": len(still_records),
            "evidenceN": len(still_evidence),
            "medianMeanDisplayLumaProxy": (
                round(statistics.median(still_lumas), 6)
                if still_lumas else None),
            "dominantHueFamilyCounts": _counter(
                metrics.get("dominantHueFamily") for metrics in still_metrics),
            "decodeSizes": still_decode_counts(still_records),
        },
        "stillQuality": still_quality_summary(still_records),
        "unreadableRecords": problems,
    }

    report_path = out_dir / "report.md"
    aggregate_path = out_dir / "aggregate.json"
    write_json_atomic(aggregate_path, aggregate)
    _write_text_atomic(report_path, _render_report(
        aggregate, out_dir=out_dir, catalog_path=catalog_path, top=top,
        catalog_present=catalog is not None))
    log(f"report: videos={len(table_rows)} stills={len(still_records)} "
        f"unreadable={len(problems)} -> {report_path} and {aggregate_path}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


_SIZE_UNITS = {
    "": 1, "b": 1,
    "k": 1024, "kb": 1024, "kib": 1024,
    "m": 1024 ** 2, "mb": 1024 ** 2, "mib": 1024 ** 2,
    "g": 1024 ** 3, "gb": 1024 ** 3, "gib": 1024 ** 3,
}


def parse_byte_size(value: object) -> int:
    """Parse ``250MiB``/``250M``/``262144000`` into bytes."""
    if isinstance(value, bool):
        raise ValueError("byte size must be an integer or a size string")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("byte size must be positive")
        return value
    text = as_text(value)
    if text is None:
        raise ValueError("byte size must be a positive integer or size string")
    match = re.fullmatch(r"(\d+)\s*([A-Za-z]*)", text)
    if match is None:
        raise ValueError("byte size is not a positive integer or size string")
    unit = match.group(2).lower()
    if unit not in _SIZE_UNITS:
        raise ValueError("byte size unit is not recognised")
    size = int(match.group(1)) * _SIZE_UNITS[unit]
    if size <= 0:
        raise ValueError("byte size must be positive")
    return size


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ephemeral AICP Awards video research collector")
    sub = parser.add_subparsers(dest="command", required=True)

    catalog = sub.add_parser(
        "catalog", help="fetch the public commercial-entry catalog")
    catalog.add_argument("--out", type=Path, required=True,
                         help="path for the versioned catalog JSON")
    catalog.add_argument("--limit", type=int, default=None,
                         help="cap collected entries (0 = all)")
    catalog.add_argument("--delay-seconds", type=float,
                         default=DEFAULT_CATALOG_DELAY,
                         help="politeness pause between catalog pages")

    collect = sub.add_parser(
        "collect", help="download, measure, and delete public HLS videos")
    collect.add_argument("--catalog", type=Path, required=True)
    collect.add_argument("--out-dir", type=Path, required=True)
    collect.add_argument("--limit", type=int, default=None,
                         help="cap attempted entries (0 = all remaining)")
    collect.add_argument("--acknowledge-rights", action="store_true")
    group = collect.add_mutually_exclusive_group()
    group.add_argument("--resume", dest="resume", action="store_true",
                       default=True)
    group.add_argument("--refresh", dest="resume", action="store_false")
    collect.add_argument("--delay-seconds", type=float,
                         default=DEFAULT_VIDEO_DELAY,
                         help="politeness pause (plus equal jitter) per video")
    collect.add_argument("--jobs", type=int, default=1)
    collect.add_argument("--windows", type=int, default=4)
    collect.add_argument("--window-seconds", type=int, default=10)
    collect.add_argument("--max-duration-seconds", type=float,
                         default=DEFAULT_MAX_DURATION_SECONDS)
    collect.add_argument("--max-file-bytes", type=parse_byte_size,
                         default=DEFAULT_MAX_FILE_BYTES,
                         help="download cap in bytes or a size like 250MiB")
    collect.add_argument("--rights-note", default=DEFAULT_RIGHTS_NOTE)
    collect.add_argument("--ffmpeg", default="ffmpeg")
    collect.add_argument("--ffprobe", default="ffprobe")

    stills = sub.add_parser(
        "stills", help="measure one published screenshot per catalog entry")
    stills.add_argument("--catalog", type=Path, required=True)
    stills.add_argument("--out-dir", type=Path, required=True)
    stills.add_argument("--limit", type=int, default=None,
                        help="cap measured stills (0 = all remaining)")
    still_group = stills.add_mutually_exclusive_group()
    still_group.add_argument("--resume", dest="resume", action="store_true",
                             default=True)
    still_group.add_argument("--refresh", dest="resume", action="store_false")
    stills.add_argument("--delay-seconds", type=float,
                        default=DEFAULT_STILL_DELAY,
                        help="politeness pause (plus equal jitter) per still")
    stills.add_argument("--jobs", type=int, default=1)
    stills.add_argument("--max-image-bytes", type=parse_byte_size,
                        default=STILL_MAX_BYTES)
    stills.add_argument("--ffmpeg", default="ffmpeg")
    stills.add_argument("--ffprobe", default="ffprobe")

    report = sub.add_parser(
        "report", help="write report.md + aggregate.json from records "
                       "(read-only, offline)")
    report.add_argument("--out-dir", type=Path, required=True)
    report.add_argument("--top", type=int, default=DEFAULT_TOP,
                        help="per-video detail blocks to render")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            run_catalog(args.out, limit=args.limit,
                        delay_seconds=args.delay_seconds)
            return 0
        if args.command == "report":
            return run_report(args.out_dir, top=args.top)
        if args.command == "stills":
            return run_stills(
                args.catalog, out_dir=args.out_dir, limit=args.limit,
                resume=args.resume, jobs=args.jobs,
                delay_seconds=args.delay_seconds,
                max_bytes=args.max_image_bytes, ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe)
        if not args.acknowledge_rights:
            parser.error(
                "--acknowledge-rights is required: public availability is not "
                "a license and downloaded media is deleted after measurement")
        return run_collect(
            args.catalog, out_dir=args.out_dir, limit=args.limit,
            resume=args.resume, jobs=args.jobs,
            acknowledge_rights=args.acknowledge_rights,
            delay_seconds=args.delay_seconds, windows=args.windows,
            window_seconds=args.window_seconds,
            max_duration_seconds=args.max_duration_seconds,
            max_file_bytes=args.max_file_bytes,
            rights_note=args.rights_note, ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe)
    except ValueError as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    sys.exit(main())
