"""Ephemeral, source-hashed measurement of public shots.net clips and stills.

Catalog metadata comes from shots.net's public, auth-free JSON search endpoint.
The video lane downloads the smallest usable public rendition on allowlisted
delivery hosts, measures sampled source-PTS windows, and deletes every byte.
The stills lane downloads the one published poster thumbnail, decodes it once at
160x90, and deletes it. Only numeric evidence, hashes, and catalog metadata are
committed.

This is a *site adapter*: allowlisting, bounded retrieval, probing, window and
still measurement, evidence assembly, atomic writes, resume checks, index
assembly, and the pooled batch loop come from
:mod:`kumiki_reference_lab.acquisition`. The adapter supplies the shots.net
endpoint, the catalog projection, the rendition ladder, the host allowlists,
schema/evidence/limits/rights strings, and the CLI.

``download_allowed`` is false for every observed clip. That fact is recorded,
not worked around: public availability is not a redistribution licence.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shlex
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition import (  # noqa: E402
    ANALYZER_RIGHTS_STATUS, DIRECT, MAX_WINDOWS, MAX_WINDOW_SECONDS,
    STILL_MAX_BYTES, STILL_NON_EVIDENCE_FLAGS, USER_AGENT, BatchSkip,
    aggregate_extremes, allowlisted_image_url, allowlisted_video_url, as_int,
    as_text, build_index, build_still_evidence, build_video_evidence,
    comparability_block, coverage_distribution, cut_columns, download_http,
    download_media, duplicate_summary, finite_float, image_target,
    measure_still, measure_windows, resume_matches as _resume_matches,
    run_batch, safe_error, safe_slug, source_metadata,
    still_decode_counts, still_decode_dimensions, still_has_quality_flags,
    still_image_format, still_quality_flags, still_quality_summary,
    unique_media_rows, utc_now, write_json_atomic,
)
from kumiki_reference_lab.acquisition.reporting import (  # noqa: E402
    comparability_lines, coverage_lines, excluded_leaders_lines, extreme_text,
)
from kumiki_reference_lab.analyzers.media.inspect import (  # noqa: E402
    inspect_source, sha256_file,
)

ENDPOINT = "https://shots.net/search"
SOURCE_HOST = "shots.net"
CLIP_PAGE_URL = "https://shots.net/news/view/{slug}"
EMBED_URL = "https://shots.net/embed/clip/{clip_id}"
CATALOG_SCHEMA = "kumiki.shots-catalog.v1"
INDEX_SCHEMA = "kumiki.shots-index.v1"
VIDEO_SCHEMA = "kumiki.shots-video-evidence.v1"
STILL_SCHEMA = "kumiki.shots-still-evidence.v1"
STILLS_INDEX_SCHEMA = "kumiki.shots-stills-index.v1"
AGGREGATE_SCHEMA = "kumiki.shots-aggregate.v1"

PROVIDER = "direct-mp4"
EVIDENCE_STATUS = "sampled-original-source-pts-metrics-not-expert-reviewed"
STILL_EVIDENCE_STATUS = "single-published-still-metrics-not-video-measurement"
RIGHTS_BASIS = "user-declared-research-use"
RIGHTS_STATUS = "review-required"
DEFAULT_RIGHTS_NOTE = (
    "operator attests public-page research use; downloaded media is deleted "
    "after numeric source-PTS measurement and is not redistributed")

# Delivery hosts observed in this catalog. The redirect host is passed
# explicitly because the engine re-validates every redirect against it.
MEDIA_HOSTS = (
    "d1ko11x0ybxl0h.cloudfront.net",
    "proxy.slatecdn.net",
    "app.extremereach.com",
    "d2290ppie00mze.cloudfront.net",
)
IMAGE_HOSTS = ("d1ko11x0ybxl0h.cloudfront.net", "images.slatecdn.net")

PORTRAIT_WIDTH = 160
PORTRAIT_HEIGHT = 90
DEFAULT_MAX_FILE_BYTES = 250 * 1024 * 1024
DEFAULT_MAX_DURATION_SECONDS = 600.0
DEFAULT_VIDEO_DELAY = 1.2
DEFAULT_STILL_DELAY = 0.5
DEFAULT_CATALOG_DELAY = 0.6
DEFAULT_CATALOG_LIMIT = 500
DEFAULT_CATALOG_PAGE_SIZE = 100
DEFAULT_VIDEO_LIMIT = 25
DEFAULT_STILL_PAGE_SIZE = 500
_MAX_PAGES = 1000
_MAX_RESPONSE_BYTES = 16_000_000

VIDEO_LIMITS = [
    "Only sampled source-PTS windows were measured; this is not a full-film review.",
    "The platform's published web rendition (or platform-encoded source / original "
    "download) is what was decoded, not the site's masters; every number describes "
    "that rendition only.",
    "The downloaded file was deleted immediately after measurement; no media, "
    "frames, thumbnails, or audio are retained.",
    "`downloadAllowed` was false on the platform for every sampled clip; this "
    "record is research evidence and must not be treated as a grant of "
    "redistribution rights.",
    "No cookies, logins, tokens, or DRM circumvention were used.",
    "Catalog metadata is self-reported by shots.net and is not independently verified.",
]
STILL_LIMITS = [
    "A published poster still is not a video frame: no motion, cut, pacing, "
    "timing, sequence, or edit-rhythm evidence is claimed.",
    "Colour, luminance, histogram, hue, and edge-density numbers describe one "
    "single image, not the clip's runtime behaviour.",
    "The poster is prepared by the platform, not necessarily by the work's author.",
    "The downloaded image was deleted immediately after measurement; no image "
    "bytes are retained.",
    "Public availability is not a licence; rightsStatus remains review-required.",
    "Catalog metadata is self-reported by shots.net and is not independently verified.",
    "No cookies, logins, tokens, or DRM circumvention were used.",
]
STILL_COVERAGE_NOTE = (
    "single published poster still, decoded once at 160x90 RGB; not a decoded "
    "video frame, no motion/time evidence")


# ---------------------------------------------------------------------------
# small coercion helpers
# ---------------------------------------------------------------------------


def _host(url: object) -> str | None:
    try:
        return (urlsplit(str(url)).hostname or "").lower() or None
    except (TypeError, ValueError):
        return None


def _name(value: object) -> str | None:
    if isinstance(value, dict):
        for key in ("name", "title", "company", "label"):
            text = as_text(value.get(key))
            if text:
                return text
        return None
    return as_text(value)


def _names(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = as_text(value)
        return [text] if text else []
    if isinstance(value, dict):
        text = _name(value)
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        names: list[str] = []
        for item in value:
            text = _name(item)
            if text and text not in names:
                names.append(text)
        return names
    return []


def _url_name(url: object) -> str | None:
    text = as_text(url)
    if text is None:
        return None
    try:
        return Path(urlsplit(text).path).name or None
    except ValueError:
        return None


# Basenames that are site chrome rather than a clip's published frame. The
# check is token-based on purpose: ``maxresdefault.jpg`` (a real YouTube
# thumbnail) must not match the ``default`` token, while ``yda-shotslogo.jpg``
# and ``spotify-no-logo.jpg`` must.
_SITE_ASSET_TOKENS = frozenset({
    "logo", "shotslogo", "favicon", "placeholder", "default", "noimage",
})


def is_site_asset_url(url: object) -> bool:
    """True when a poster URL's basename looks like site chrome, not a frame."""
    name = _url_name(url)
    if name is None:
        return False
    stem = name.rsplit(".", 1)[0].lower()
    tokens = {token for token in re.split(r"[^a-z0-9]+", stem) if token}
    compact = re.sub(r"[^a-z0-9]+", "", stem)
    return (bool(tokens & _SITE_ASSET_TOKENS)
            or "no-image" in stem
            or "noimage" in compact)


def _rational_float(value: object) -> float | None:
    if not isinstance(value, dict):
        return None
    numerator = finite_float(value.get("numerator"))
    denominator = finite_float(value.get("denominator"))
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _duration_seconds(raw: dict[str, Any]) -> float | None:
    for value in (
        raw.get("duration"),
        (raw.get("original_file") or {}).get("mediaInfo", {}).get("Duration")
        if isinstance(raw.get("original_file"), dict)
        and isinstance((raw.get("original_file") or {}).get("mediaInfo"), dict)
        else None,
        (raw.get("encoding_media_info") or {}).get("Duration")
        if isinstance(raw.get("encoding_media_info"), dict) else None,
    ):
        number = finite_float(value)
        if number is not None:
            return round(number, 6)
    return None


# ---------------------------------------------------------------------------
# catalog: search endpoint and the slim normalized projection
# ---------------------------------------------------------------------------


def search_url(limit: int, offset: int) -> str:
    """Build one public search URL; ``limit`` must stay at or below 100."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("catalog page size must be between 1 and 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("catalog offset must be a non-negative integer")
    query = urlencode({
        "types[0]": "clip", "as_json": 1, "limit": limit, "offset": offset,
        "sort": "newestFirst",
    })
    return f"{ENDPOINT}?{query}"


def _get_json(
    url: str, *, timeout: float = 45.0, retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """GET one JSON page with bounded retries on transport/5xx responses."""
    last_error: Exception | None = None
    for attempt in range(retries):
        request = Request(url, headers={
            "Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise ValueError(
                    f"catalog endpoint rejected the request (HTTP {error.code})") from None
            last_error = error
        except (URLError, TimeoutError, OSError) as error:
            last_error = error
        else:
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise ValueError("catalog response exceeded the expected size limit")
            try:
                payload = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise ValueError("catalog response was not valid JSON") from None
            if not isinstance(payload, dict):
                raise ValueError("catalog response was not a usable JSON object")
            return payload
        if attempt + 1 < retries:
            sleep(2 ** attempt)
    raise RuntimeError("catalog request failed after bounded retries") from last_error


def _file_url(file_value: object) -> str | None:
    """Read ``remote_address`` from a file object, tolerating ``{file: ...}``."""
    if not isinstance(file_value, dict):
        return None
    nested = file_value.get("file")
    if isinstance(nested, dict):
        return as_text(nested.get("remote_address"))
    return as_text(file_value.get("remote_address"))


def _file_name(file_value: object) -> str | None:
    if not isinstance(file_value, dict):
        return None
    nested = file_value.get("file")
    if isinstance(nested, dict):
        return as_text(nested.get("name"))
    return as_text(file_value.get("name"))


def _file_bytes(file_value: object) -> int | None:
    if not isinstance(file_value, dict):
        return None
    nested = file_value.get("file")
    if isinstance(nested, dict):
        return as_int(nested.get("size"))
    return as_int(file_value.get("size"))


def _candidate(
    rendition: str, file_value: object, *, ready: bool,
    rejection: str | None = None,
) -> dict[str, Any] | None:
    url = _file_url(file_value)
    if not url:
        return None
    try:
        allowed = _policy_media_url(url)
        allowlist_error = None
    except ValueError as error:
        allowed, allowlist_error = False, str(error)
    reason = rejection or allowlist_error
    usable = bool(ready and allowed)
    return {
        "rendition": rendition,
        "url": url,
        "host": _host(url),
        "bytes": _file_bytes(file_value),
        "name": _file_name(file_value),
        "ready": bool(ready),
        "allowlisted": bool(allowed),
        "usable": usable,
        "reason": None if usable else (reason or "stream-not-ready"),
    }


def _policy_media_url(url: object) -> str:
    # Signed originals (app.extremereach.com -> CloudFront) carry query strings;
    # this host list is the only place the engine's query opt-in is enabled.
    return allowlisted_video_url(
        url, allowed_hosts=MEDIA_HOSTS, allow_query=True)


def _policy_image_url(url: object) -> str:
    return allowlisted_image_url(url, allowed_hosts=IMAGE_HOSTS)


def media_candidates(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every observed candidate in the deterministic rendition ladder.

    The ladder is deliberately structural and never invents a variant:
    ``streams["1"]`` web rendition, then the first ready/allowlisted
    platform-encoded list stream, then the original file. The original rung is
    now first-class: the signed ``app.extremereach.com`` URL and its signed
    CloudFront redirect are accepted through the engine's ``allow_query``
    opt-in, so a clip with only ``original_file`` yields a real video target.
    """
    candidates: list[dict[str, Any]] = []
    streams = raw.get("streams")
    if isinstance(streams, dict):
        entry = streams.get("1")
        if isinstance(entry, dict):
            ready = as_int(entry.get("status")) == 3
            candidate = _candidate(
                "720p-web-rendition", entry.get("file"), ready=ready,
                rejection=None if ready else "stream-not-ready")
            if candidate:
                candidates.append(candidate)
    elif isinstance(streams, list):
        for entry in streams:
            if not isinstance(entry, dict):
                continue
            ready = as_int(entry.get("status")) == 3
            candidate = _candidate(
                "platform-encoded-source", entry.get("file"), ready=ready,
                rejection=None if ready else "stream-not-ready")
            if candidate:
                candidates.append(candidate)
    original = raw.get("original_file")
    candidate = _candidate("original-download", original, ready=True)
    if candidate:
        candidates.append(candidate)
    return candidates


def choose_media(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return ``(all candidates, first usable candidate in ladder order)``."""
    candidates = media_candidates(raw)
    chosen = next((candidate for candidate in candidates if candidate["usable"]), None)
    return candidates, chosen


def _poster_candidates(raw: dict[str, Any]) -> list[str]:
    """Poster URLs in preference order, before allowlist filtering.

    Preference is: the primary thumbnail's own file, then the first entry of
    ``thumbnails[]``, then the platform's ``image_player_url`` renders.
    """
    urls: list[str] = []
    thumbnail = raw.get("thumbnail")
    thumbnail_file = None
    if isinstance(thumbnail, dict):
        thumbnail_file = (thumbnail.get("file")
                          if isinstance(thumbnail.get("file"), dict) else thumbnail)
        value = _file_url(thumbnail_file)
        if value:
            urls.append(value)
    thumbnails = raw.get("thumbnails")
    if isinstance(thumbnails, list):
        for entry in thumbnails:
            if not isinstance(entry, dict):
                continue
            file_value = entry.get("file") if isinstance(entry.get("file"), dict) else entry
            value = _file_url(file_value)
            if value and value not in urls:
                urls.append(value)
    if isinstance(thumbnail_file, dict):
        value = as_text(thumbnail_file.get("image_player_url"))
        if value and value not in urls:
            urls.append(value)
    if isinstance(thumbnails, list):
        for entry in thumbnails:
            if not isinstance(entry, dict):
                continue
            file_value = entry.get("file") if isinstance(entry.get("file"), dict) else entry
            value = as_text(file_value.get("image_player_url"))
            if value and value not in urls:
                urls.append(value)
    return urls


def poster_url(raw: dict[str, Any]) -> str | None:
    """Choose the first allowlisted published poster; nothing else is fetched."""
    for value in _poster_candidates(raw):
        try:
            return _policy_image_url(value)
        except ValueError:
            continue
    return None


def normalize_clip(raw: dict[str, Any]) -> dict[str, Any]:
    """Project one raw search result into the slim, deterministic catalog row."""
    if not isinstance(raw, dict):
        raise ValueError("catalog clip must be an object")
    clip_id = as_int(raw.get("id"))
    if clip_id is None:
        raise ValueError("catalog clip has no integer id")
    urlname = as_text(raw.get("urlname"))
    slug = urlname or f"clip-{clip_id}"
    candidates, chosen = choose_media(raw)
    aspect = finite_float(raw.get("aspect_ratio"))
    return {
        "id": clip_id,
        "slug": slug,
        "title": as_text(raw.get("title")) or "",
        "publicationDate": as_text(raw.get("publication_date")),
        "durationSeconds": _duration_seconds(raw),
        "originalWidth": as_int(raw.get("original_width")),
        "originalHeight": as_int(raw.get("original_height")),
        "aspectRatio": aspect if aspect is not None else as_text(raw.get("aspect_ratio")),
        "brandName": _name(raw.get("brand")),
        "clientName": _name(raw.get("client")),
        "agencyName": _name(raw.get("agency")),
        "productionCompanies": _names(raw.get("production_company")),
        "artists": _names(raw.get("artists_names")),
        "categories": _names(raw.get("categories")),
        "contentTypes": _names(raw.get("content_types")),
        "awards": _names(raw.get("slate_award")),
        "downloadAllowed": bool(raw.get("download_allowed")),
        "embedUrl": as_text(raw.get("embedded_url")) or EMBED_URL.format(clip_id=clip_id),
        "articleUrl": (CLIP_PAGE_URL.format(slug=quote(urlname, safe="-._~"))
                       if urlname else
                       as_text(raw.get("__url"))
                       or EMBED_URL.format(clip_id=clip_id)),
        "thumbnailUrl": poster_url(raw),
        "videoUrl": chosen["url"] if chosen else None,
        "videoBytes": chosen["bytes"] if chosen else None,
        "videoRendition": chosen["rendition"] if chosen else None,
        "year": as_int(raw.get("year")),
        "candidates": [
            {"url": candidate["url"], "host": candidate["host"],
             "bytes": candidate["bytes"], "kind": candidate["rendition"]}
            for candidate in candidates
        ],
    }


def catalog_order(row: dict[str, Any]) -> tuple[str, int]:
    """Stable catalog order: publication date descending, then clip id descending."""
    clip_id = as_int(row.get("id"))
    return (as_text(row.get("publicationDate")) or "",
            clip_id if clip_id is not None else -1)


def _date_prefix(value: object) -> str | None:
    text = as_text(value)
    if text is None or len(text) < 10:
        return None
    return text[:10]


def fetch_catalog(
    *, limit: int = DEFAULT_CATALOG_LIMIT, offset: int = 0,
    since: str | None = None, page_size: int = DEFAULT_CATALOG_PAGE_SIZE,
    delay_seconds: float = DEFAULT_CATALOG_DELAY,
    fetch: Callable[[str], dict[str, Any]] = _get_json,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> tuple[list[dict[str, Any]], int | None]:
    """Page the public search endpoint and return normalized rows plus total hits.

    ``limit`` is the catalog size (0 is an offline no-op); ``offset`` pages into
    the live library; ``since`` stops once results are older than the date.
    Requests are spaced by at least 0.6 s plus equal jitter.
    """
    if type(limit) is not int or limit < 0:
        raise ValueError("catalog limit must be a non-negative integer")
    if type(offset) is not int or offset < 0:
        raise ValueError("catalog offset must be a non-negative integer")
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ValueError("catalog page size must be between 1 and 100")
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("catalog delay must be a non-negative number")
    since_date = _date_prefix(since) if since is not None else None
    if since is not None and (since_date is None or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", since_date)):
        raise ValueError("since must be a YYYY-MM-DD date")
    if limit == 0:
        return [], None

    rows: list[dict[str, Any]] = []
    total: int | None = None
    next_offset = offset
    pages = 0
    while len(rows) < limit and pages < _MAX_PAGES:
        payload = fetch(search_url(page_size, next_offset))
        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError("catalog response has no results list")
        hits = as_int(payload.get("hits"))
        if hits is not None:
            total = hits
        if not results:
            break
        keep: list[dict[str, Any]] = []
        older_seen = False
        for raw in results:
            if not isinstance(raw, dict):
                continue
            if since_date is not None:
                date = _date_prefix(raw.get("publication_date"))
                if date is None:
                    continue
                if date < since_date:
                    older_seen = True
                    continue
            keep.append(normalize_clip(raw))
        rows.extend(keep)
        log(f"catalog page {pages + 1}: {len(results)} clips "
            f"({len(keep)} normalized, {len(rows)} collected)")
        if older_seen or len(results) < page_size:
            break
        next_offset += len(results)
        pages += 1
        if len(rows) < limit:
            sleep(float(delay_seconds) + random.uniform(0, float(delay_seconds)))
    if pages >= _MAX_PAGES:
        raise ValueError("catalog pagination exceeded the safety page budget")
    rows = sorted(rows, key=catalog_order, reverse=True)[:limit]
    return rows, total


def build_catalog(
    rows: Iterable[dict[str, Any]], total: int | None, *,
    retrieved_at: str | None = None, offset: int = 0,
    limit: int = DEFAULT_CATALOG_LIMIT, since: str | None = None,
) -> dict[str, Any]:
    clips = sorted(rows, key=catalog_order, reverse=True)
    return {
        "schemaVersion": CATALOG_SCHEMA,
        "retrievedOn": retrieved_at or utc_now(),
        "sourceHost": SOURCE_HOST,
        "endpoint": ENDPOINT,
        "query": {"types": ["clip"], "sort": "newestFirst", "offset": offset,
                  "limit": limit, "since": since},
        "totalReportedHits": total if total is not None else len(clips),
        "clipCount": len(clips),
        "clips": clips,
    }


def _load_catalog(path: Path) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or catalog.get("schemaVersion") != CATALOG_SCHEMA:
        raise ValueError("unsupported catalog schema")
    if not isinstance(catalog.get("clips"), list):
        raise ValueError("catalog has no clip list")
    return catalog


def run_catalog(
    out: Path, *, limit: int = DEFAULT_CATALOG_LIMIT, offset: int = 0,
    since: str | None = None, page_size: int = DEFAULT_CATALOG_PAGE_SIZE,
    delay_seconds: float = DEFAULT_CATALOG_DELAY,
    log: Callable[[str], None] = print,
) -> int:
    rows, total = fetch_catalog(
        limit=limit, offset=offset, since=since, page_size=page_size,
        delay_seconds=delay_seconds, log=log)
    catalog = build_catalog(
        rows, total, offset=offset, limit=limit, since=since)
    write_json_atomic(Path(out), catalog)
    log(f"catalog: {catalog['clipCount']} clips of "
        f"{catalog['totalReportedHits']} reported -> {out}")
    return 0


# ---------------------------------------------------------------------------
# record identity and schemas
# ---------------------------------------------------------------------------


def record_stem(row: dict[str, Any]) -> str:
    """One stable ``<id>-<slug>`` file stem for a catalog row or record."""
    clip_id = as_int(row.get("id"))
    if clip_id is None:
        clip_id = as_int(row.get("clipId"))
    if clip_id is None and isinstance(row.get("clip"), dict):
        clip_id = as_int(row["clip"].get("id"))
    if clip_id is None:
        raise ValueError("row has no integer clip id")
    slug = safe_slug(row.get("slug") or f"clip-{clip_id}")
    return f"{clip_id}-{slug}"


def record_path(out_dir: Path, folder: str, row: dict[str, Any]) -> Path:
    return Path(out_dir) / folder / f"{record_stem(row)}.json"


def _clip_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": as_int(row.get("id")),
        "slug": row.get("slug"),
        "title": row.get("title"),
        "projectUrl": row.get("articleUrl"),
        "embedUrl": row.get("embedUrl"),
        "publicationDate": row.get("publicationDate"),
        "durationSeconds": finite_float(row.get("durationSeconds")),
        "aspectRatio": row.get("aspectRatio"),
        "originalWidth": as_int(row.get("originalWidth")),
        "originalHeight": as_int(row.get("originalHeight")),
        "brand": row.get("brandName"),
        "client": row.get("clientName"),
        "agency": row.get("agencyName"),
        "productionCompanies": row.get("productionCompanies") or [],
        "artists": row.get("artists") or [],
        "categories": row.get("categories") or [],
        "contentTypes": row.get("contentTypes") or [],
        "awards": row.get("awards") or [],
        "downloadAllowed": bool(row.get("downloadAllowed")),
        "year": as_int(row.get("year")),
    }


def build_video_record(
    row: dict[str, Any], *, media: dict[str, Any], source: dict[str, Any],
    coverage: dict[str, Any], windows: list[dict[str, Any]], method: str,
    downloaded_bytes: int, rights_note: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge clip identity and the rendition choice around neutral evidence."""
    evidence = build_video_evidence(
        source=source, coverage=coverage, windows=windows, method=method,
        provider=PROVIDER, video_url=media.get("url"),
        rights_basis=RIGHTS_BASIS, rights_note=rights_note,
        schema_version=VIDEO_SCHEMA, evidence_status=EVIDENCE_STATUS,
        limits=VIDEO_LIMITS, generated_at=generated_at,
        rights_status=RIGHTS_STATUS)
    acquisition = {
        **evidence["acquisition"],
        "rendition": media.get("rendition"),
        "url": media.get("url"),
        "bytes": downloaded_bytes,
    }
    chosen = {**media, "name": media.get("name") or _url_name(media.get("url"))}
    candidates = [{**candidate,
                   "name": candidate.get("name") or _url_name(candidate.get("url"))}
                  for candidate in (row.get("candidates") or [])]
    return {
        "schemaVersion": VIDEO_SCHEMA,
        "clipId": as_int(row.get("id")),
        "slug": row.get("slug"),
        "clip": _clip_identity(row),
        "media": {"chosen": chosen, "candidates": candidates},
        "source": evidence["source"],
        "acquisition": acquisition,
        "coverage": evidence["coverage"],
        "windows": evidence["windows"],
        "summary": evidence["summary"],
        "evidenceStatus": evidence["evidenceStatus"],
        "rightsStatus": evidence["rightsStatus"],
        "rights": {"basis": RIGHTS_BASIS, "status": RIGHTS_STATUS,
                   "note": rights_note},
        "limits": evidence["limits"],
        "generatedAt": evidence["generatedAt"],
    }


def build_still_record(
    row: dict[str, Any], *, still: dict[str, Any],
    quality_flags: list[str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge clip identity around neutral single-published-still evidence."""
    evidence = build_still_evidence(
        still=still, schema_version=STILL_SCHEMA,
        evidence_status=STILL_EVIDENCE_STATUS, limits=STILL_LIMITS,
        coverage_note=STILL_COVERAGE_NOTE, quality_flags=quality_flags,
        generated_at=generated_at)
    return {
        "schemaVersion": STILL_SCHEMA,
        "clipId": as_int(row.get("id")),
        "slug": row.get("slug"),
        "clip": _clip_identity(row),
        "still": evidence["still"],
        "acquisition": evidence["acquisition"],
        "coverage": evidence["coverage"],
        "evidenceStatus": evidence["evidenceStatus"],
        "rights": {"basis": RIGHTS_BASIS, "status": RIGHTS_STATUS},
        "limits": evidence["limits"],
        "generatedAt": evidence["generatedAt"],
    }


# ---------------------------------------------------------------------------
# video lane: download -> probe -> measure -> record -> always delete
# ---------------------------------------------------------------------------


def _source_identity(path: Path, *, ffprobe: str) -> dict[str, Any]:
    source = source_metadata(path, ffprobe=ffprobe)
    inspected = inspect_source(
        path, rights_status=ANALYZER_RIGHTS_STATUS, ffprobe=ffprobe)
    video = inspected["video"]
    source.update({
        "streamIndex": video["streamIndex"],
        "nominalFrameRate": video["nominalFrameRate"],
        "framesPerSecond": _rational_float(video["averageFrameRate"]),
        "sourceTimebase": video["sourceTimebase"],
    })
    return source


def _precheck_download(
    row: dict[str, Any], *, max_file_bytes: int,
    max_duration_seconds: float,
) -> None:
    duration = finite_float(row.get("durationSeconds"))
    if duration is not None and duration > max_duration_seconds:
        raise ValueError("catalog duration exceeds the bounded duration budget")
    size = as_int(row.get("videoBytes"))
    if size is not None and size > max_file_bytes:
        raise ValueError("catalog video size exceeds the bounded local size cap")


def collect_one(
    row: dict[str, Any], out_dir: Path, *, windows: int = 4,
    window_seconds: int = 10, max_samples: int = 12,
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    image_translation: bool = False,
    rights_note: str = DEFAULT_RIGHTS_NOTE, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe", download_timeout: float = 360.0,
) -> dict[str, Any]:
    """Download, measure, write one record, and always delete the media."""
    if (type(windows) is not int or not 1 <= windows <= MAX_WINDOWS
            or type(window_seconds) is not int
            or not 1 <= window_seconds <= MAX_WINDOW_SECONDS
            or type(max_samples) is not int or not 1 <= max_samples <= 60):
        raise ValueError("window/sample budgets are out of bounds")
    if (not finite_float(max_duration_seconds) or max_duration_seconds <= 0
            or type(max_file_bytes) is not int or max_file_bytes <= 0
            or type(image_translation) is not bool):
        raise ValueError("collection budgets are out of bounds")
    if not isinstance(rights_note, str) or not rights_note.strip():
        raise ValueError("rights note must be non-empty")
    if not row.get("videoUrl"):
        raise ValueError("clip has no allowlisted public rendition")
    _precheck_download(row, max_file_bytes=max_file_bytes,
                       max_duration_seconds=max_duration_seconds)
    media = {
        "rendition": row.get("videoRendition"),
        "url": row.get("videoUrl"),
        "host": _host(row.get("videoUrl")),
        "bytes": as_int(row.get("videoBytes")),
    }
    target_path = record_path(Path(out_dir), "videos", row)
    # The context manager deletes every downloaded byte on success and failure.
    with tempfile.TemporaryDirectory(prefix="kumiki-shots-") as directory:
        media_dir = Path(directory) / "media"
        media_dir.mkdir()
        path, method = download_media(
            media["url"], DIRECT, media_dir, allowed_hosts=MEDIA_HOSTS,
            max_bytes=max_file_bytes, ffmpeg=ffmpeg, ffprobe=ffprobe,
            timeout=download_timeout,
            max_duration_seconds=max_duration_seconds, allow_query=True)
        source = _source_identity(path, ffprobe=ffprobe)
        if source["durationSeconds"] > max_duration_seconds:
            raise ValueError("source exceeds the bounded duration budget")
        coverage, measured = measure_windows(
            path, duration_seconds=source["durationSeconds"],
            window_count=windows, window_seconds=window_seconds,
            image_translation=image_translation, max_samples=max_samples,
            frame_width=PORTRAIT_WIDTH, frame_height=PORTRAIT_HEIGHT,
            ffmpeg=ffmpeg, ffprobe=ffprobe)
        record = build_video_record(
            row, media=media, source=source, coverage=coverage,
            windows=measured, method=method,
            downloaded_bytes=path.stat().st_size, rights_note=rights_note)
        write_json_atomic(target_path, record)
        return record


def _video_detail(record: dict[str, Any]) -> str:
    source, summary = record.get("source") or {}, record.get("summary") or {}
    width, height = source.get("resolution") or (0, 0)
    return (f"{width}x{height} {(source.get('durationSeconds') or 0):.1f}s "
            f"{((source.get('sizeBytes') or 0) / (1024 * 1024)):.1f}MB "
            f"{(record.get('acquisition') or {}).get('rendition')} "
            f"cuts={summary.get('cutCandidates', 0)}")


def _video_summary_row(
    record: dict[str, Any], path: Path | None = None,
) -> dict[str, Any]:
    clip = record.get("clip") or {}
    source = record.get("source") or {}
    acquisition = record.get("acquisition") or {}
    coverage = record.get("coverage") or {}
    summary = record.get("summary") or {}
    fraction = finite_float(coverage.get("fractionOfRuntime"))
    return {
        "clipId": record.get("clipId"),
        "slug": record.get("slug"),
        "title": clip.get("title"),
        "brand": clip.get("brand"),
        "rendition": acquisition.get("rendition"),
        "durationSeconds": source.get("durationSeconds"),
        "resolution": source.get("resolution"),
        "framesPerSecond": source.get("framesPerSecond"),
        "sourceSha256": source.get("mediaSha256"),
        "downloadBytes": source.get("sizeBytes"),
        "windowCount": coverage.get("windowsMeasured"),
        "coveragePercent": (round(fraction * 100, 6)
                            if fraction is not None else None),
        "cutCandidates": summary.get("cutCandidates"),
        "cutsPerMinute": summary.get("cutCandidateRatePerMinute"),
        "meanDisplayLuma": summary.get("meanDisplayLuma"),
        "meanSaturation": summary.get("meanSaturation"),
        "recordPath": (path.as_posix() if path is not None else
                       f"videos/{record_stem(record)}.json"),
    }


def _skip_row(row: Any, reason: str) -> dict[str, Any]:
    return {"clipId": (row.get("id") if isinstance(row, dict) else None),
            "slug": (row.get("slug") if isinstance(row, dict) else None),
            "reason": reason}


def _error_text(out_dir: Path) -> Callable[[Exception], str]:
    def render(error: Exception) -> str:
        return re.sub(r"/[^\s:'\"]*kumiki-shots-[^\s:'\"]*", "[scratch]",
                      safe_error(error, redact=(str(out_dir),)))
    return render


def _run_lane(
    items: Iterable[dict[str, Any]], *, out_dir: Path, folder: str,
    index_name: str, schema: str, catalog_sha: str,
    run_one: Callable[[dict[str, Any]], dict[str, Any]],
    summary_row: Callable[[dict[str, Any], Path | None], dict[str, Any]],
    detail: Callable[[dict[str, Any]], str], label: str, final_note: str,
    initial_skips: Iterable[dict[str, Any]] = (),
    retained: list[dict[str, Any]] | None = None,
    progress_total: int | None = None, resume: bool = True, jobs: int = 1,
    delay_seconds: float = 0.0, offset: int = 0, limit: int | None = None,
    log: Callable[[str], None] = print,
) -> int:
    """Run one lane with resume, atomic index refresh, and progress lines."""
    if type(jobs) is not int or not 1 <= jobs <= 3:
        raise ValueError("jobs must be between 1 and 3")
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("delay_seconds must be a non-negative number")
    retained = retained or []
    (out_dir / folder).mkdir(parents=True, exist_ok=True)
    index_path, details = out_dir / index_name, {}

    def tracked(row: dict[str, Any]) -> dict[str, Any]:
        record = run_one(row)
        details[str(row.get("slug"))] = detail(record)
        return record

    def index_for(records: list[dict[str, Any]], skips: list[dict[str, Any]],
                  failures: list[dict[str, Any]]) -> dict[str, Any]:
        # ``run_batch`` passes rows already reduced by ``summary_row``.
        return build_index(
            schema_version=schema, records=[*retained, *records],
            skips=skips, failures=failures, generated_at=utc_now(),
            extra={"catalogSha256": catalog_sha, "offset": offset,
                   "limit": limit})

    def _summary_row_for(record: dict[str, Any]) -> dict[str, Any]:
        return summary_row(record, None)

    def skip_reason(row: dict[str, Any]) -> str | None:
        try:
            requested = record_path(out_dir, folder, row)
        except ValueError as error:
            return f"unsafe-slug: {error}"
        if not resume:
            return None
        return ("resume-existing-record" if _resume_matches(
            requested, row.get("id"), field="clipId") else None)

    def report(position: int, total: int, status: str, label_text: str,
               text: str) -> None:
        print(f"[{position}/{progress_total or total}] {status} {label_text} "
              f"{text or details.pop(label_text, '')}", flush=True)

    outcome = run_batch(
        items, run_one=tracked, index_path=index_path, build_index=index_for,
        summary_row=_summary_row_for, skip_row=_skip_row,
        describe=lambda row: str(row.get("slug")),
        skip_reason=skip_reason, initial_skips=initial_skips,
        error_text=_error_text(out_dir), progress=report, jobs=jobs,
        delay_seconds=delay_seconds)
    log(f"{label}={len(retained) + outcome.measured} skipped={outcome.skipped} "
        f"failed={outcome.failed} attempted={outcome.attempted} "
        f"elapsed={outcome.elapsed_seconds:.1f}s index={index_path}")
    log(final_note)
    # A batch whose attempts all ended as policy skips (for example degenerate
    # posters) is a successful run, not a failure.
    return 1 if (outcome.attempted and outcome.failed
                 and not (retained or outcome.measured)) else 0


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


def _empty_index(
    out_dir: Path, *, index_name: str, schema: str, catalog_sha: str | None,
    offset: int, limit: int | None,
) -> None:
    write_json_atomic(Path(out_dir) / index_name, build_index(
        schema_version=schema, records=[], skips=[], failures=[],
        generated_at=utc_now(),
        extra={"catalogSha256": catalog_sha, "offset": offset, "limit": limit}))


def run_collect(
    catalog_path: Path | None, *, out_dir: Path, limit: int = DEFAULT_VIDEO_LIMIT,
    offset: int = 0, resume: bool = True, jobs: int = 1,
    acknowledge_rights: bool = False, delay_seconds: float = DEFAULT_VIDEO_DELAY,
    windows: int = 4, window_seconds: int = 10, max_samples: int = 12,
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    image_translation: bool = False, rights_note: str = DEFAULT_RIGHTS_NOTE,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    download_timeout: float = 360.0, log: Callable[[str], None] = print,
) -> int:
    """Measure one catalog slice of clips; ``limit == 0`` is an offline no-op."""
    if acknowledge_rights is not True:
        raise ValueError(
            "explicit --acknowledge-rights attestation is required: public "
            "availability is not a license, and each downloaded file is "
            "deleted after numeric measurement")
    if type(limit) is not int or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    out_dir = Path(out_dir)
    if limit == 0:
        index_path = out_dir / "index.json"
        if index_path.is_file():
            log("limit=0: no catalog read, no network; existing index left untouched")
        else:
            _empty_index(out_dir, index_name="index.json", schema=INDEX_SCHEMA,
                         catalog_sha=None, offset=offset, limit=limit)
            log("limit=0: no catalog read, no network, empty index written")
        return 0
    if catalog_path is None:
        raise ValueError("a catalog file is required unless --limit 0 is used")
    catalog_file = Path(catalog_path)
    catalog_sha = sha256_file(catalog_file)
    rows = _load_catalog(catalog_file)["clips"]
    slice_rows = rows[offset:offset + limit]
    chosen = [row for row in slice_rows if row.get("videoUrl")]
    skips = [_skip_row(row, "no-allowlisted-public-rendition")
             for row in slice_rows if not row.get("videoUrl")]

    def policy_skip(row: dict[str, Any]) -> str | None:
        duration = finite_float(row.get("durationSeconds"))
        size = as_int(row.get("videoBytes"))
        if duration is not None and duration > max_duration_seconds:
            return "pre-download-duration-exceeds-budget"
        if size is not None and size > max_file_bytes:
            return "pre-download-size-exceeds-budget"
        return None

    retained = (_load_retained(out_dir, "videos", VIDEO_SCHEMA,
                               _video_summary_row) if resume else [])
    # Policy skips are recorded as index rows; the same checks also guard
    # direct collect_one calls.
    lane_skip: list[dict[str, Any]] = list(skips)

    def run_one(row: dict[str, Any]) -> dict[str, Any]:
        return collect_one(
            row, out_dir, windows=windows, window_seconds=window_seconds,
            max_samples=max_samples, max_duration_seconds=max_duration_seconds,
            max_file_bytes=max_file_bytes, image_translation=image_translation,
            rights_note=rights_note, ffmpeg=ffmpeg, ffprobe=ffprobe,
            download_timeout=download_timeout)

    # Items whose catalog metadata already exceeds a budget are skipped before
    # any download; the same checks also guard direct collect_one calls.
    eligible: list[dict[str, Any]] = []
    for row in chosen:
        reason = policy_skip(row)
        if reason is None:
            eligible.append(row)
        else:
            lane_skip.append(_skip_row(row, reason))

    return _run_lane(
        eligible, out_dir=out_dir, folder="videos", index_name="index.json",
        schema=INDEX_SCHEMA, catalog_sha=catalog_sha, run_one=run_one,
        summary_row=_video_summary_row, detail=_video_detail,
        label="measured", final_note="all downloaded media was deleted; only "
                                     "numeric evidence and metadata remain",
        initial_skips=lane_skip, retained=retained, resume=resume, jobs=jobs,
        delay_seconds=delay_seconds, offset=offset, limit=limit, log=log)


# ---------------------------------------------------------------------------
# stills lane: one published poster, decoded once, deleted immediately
# ---------------------------------------------------------------------------


def collect_still_one(
    row: dict[str, Any], out_dir: Path, *, max_bytes: int = STILL_MAX_BYTES,
    download_timeout: float = 60.0, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Download -> probe -> decode -> measure one poster; retain no image."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("still image byte cap must be positive")
    if not finite_float(download_timeout) or download_timeout <= 0:
        raise ValueError("still image timeout must be positive")
    url = row.get("thumbnailUrl")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("clip has no allowlisted published thumbnail")
    url = _policy_image_url(url)
    if is_site_asset_url(url):
        # Site chrome (logo/favicon/placeholder) is not a published frame.
        raise BatchSkip("content-identical-placeholder")
    target_path = record_path(Path(out_dir), "stills", row)
    with tempfile.TemporaryDirectory(prefix="kumiki-shots-still-") as directory:
        target = image_target(Path(directory), url)
        try:
            download_http(
                url, target, allowed_hosts=IMAGE_HOSTS, max_bytes=max_bytes,
                timeout=download_timeout, accept="image/*", label="poster still")
            image_bytes = target.stat().st_size
            digest = sha256_file(target)
            measured = measure_still(target, ffmpeg=ffmpeg, ffprobe=ffprobe)
        finally:
            # Guarantee: even a failed decode leaves no image bytes.
            target.unlink(missing_ok=True)
    flags = still_quality_flags(
        measured["metrics"], width=measured.get("imageWidth"),
        height=measured.get("imageHeight"))
    if any(flag in STILL_NON_EVIDENCE_FLAGS for flag in flags):
        # A near-empty placeholder is not poster evidence; record a skip row.
        raise BatchSkip("degenerate-poster")
    record = build_still_record(row, still={
        "imageUrl": url, "imageSha256": digest,
        "imageFormat": still_image_format(url, measured.pop("imageCodec", None)),
        "imageBytes": image_bytes, **measured}, quality_flags=flags)
    write_json_atomic(target_path, record)
    return record


def _still_detail(record: dict[str, Any]) -> str:
    still = record.get("still") or {}
    metrics = still.get("metrics") or {}
    return (f"{still.get('imageWidth')}x{still.get('imageHeight')} "
            f"luma={metrics.get('meanDisplayLumaProxy')} "
            f"hue={metrics.get('dominantHueFamily')} "
            f"bytes={still.get('imageBytes')}")


def _still_summary_row(
    record: dict[str, Any], path: Path | None = None,
) -> dict[str, Any]:
    clip = record.get("clip") or {}
    still = record.get("still") or {}
    metrics = still.get("metrics") or {}
    return {
        "clipId": record.get("clipId"),
        "slug": record.get("slug"),
        "title": clip.get("title"),
        "brand": clip.get("brand"),
        "imageUrl": still.get("imageUrl"),
        "imageSha256": still.get("imageSha256"),
        "imageFormat": still.get("imageFormat"),
        "imageBytes": still.get("imageBytes"),
        "imageWidth": still.get("imageWidth"),
        "imageHeight": still.get("imageHeight"),
        "meanDisplayLumaProxy": metrics.get("meanDisplayLumaProxy"),
        "dominantHueFamily": metrics.get("dominantHueFamily"),
        "edgeDensityProxy": metrics.get("edgeDensityProxy"),
        "qualityFlags": still.get("qualityFlags") or [],
        "recordPath": (path.as_posix() if path is not None else
                       f"stills/{record_stem(record)}.json"),
    }


def catalog_pages(
    rows: list[dict[str, Any]], *, offset: int = 0, page_size: int = DEFAULT_STILL_PAGE_SIZE,
) -> Iterable[list[dict[str, Any]]]:
    """Yield catalog pages from the local file; the final page is empty."""
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    if type(page_size) is not int or page_size < 1:
        raise ValueError("page size must be a positive integer")
    position = offset
    while True:
        page = rows[position:position + page_size]
        yield page
        if not page:
            return
        position += len(page)


def run_stills(
    catalog_path: Path | None, *, out_dir: Path, limit: int = 0,
    offset: int = 0, resume: bool = True, jobs: int = 1,
    delay_seconds: float = DEFAULT_STILL_DELAY,
    page_size: int = DEFAULT_STILL_PAGE_SIZE,
    max_image_bytes: int = STILL_MAX_BYTES, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe", log: Callable[[str], None] = print,
) -> int:
    """Measure one poster per clip from the local catalog; ``limit 0`` = all remaining."""
    if type(limit) is not int or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    out_dir = Path(out_dir)
    catalog_file = Path(catalog_path) if catalog_path is not None else (
        out_dir / "catalog.json")
    if not catalog_file.is_file():
        raise ValueError("a catalog file is required for the stills lane")
    catalog_sha = sha256_file(catalog_file)
    rows = _load_catalog(catalog_file)["clips"]

    pending: list[dict[str, Any]] = []
    initial_skips: list[dict[str, Any]] = []
    for page in catalog_pages(rows, offset=offset, page_size=page_size):
        if not page:
            break
        for row in page:
            if not row.get("thumbnailUrl"):
                initial_skips.append(_skip_row(row, "no-published-thumbnail"))
                continue
            if is_site_asset_url(row.get("thumbnailUrl")):
                initial_skips.append(
                    _skip_row(row, "content-identical-placeholder"))
                continue
            try:
                existing = record_path(out_dir, "stills", row)
            except ValueError as error:
                initial_skips.append(_skip_row(row, f"unsafe-slug: {error}"))
                continue
            if resume and _resume_matches(existing, row.get("id"), field="clipId"):
                initial_skips.append(_skip_row(row, "resume-existing-record"))
                continue
            pending.append(row)
            if limit and len(pending) >= limit:
                break
        if limit and len(pending) >= limit:
            break

    retained = (_load_retained(out_dir, "stills", STILL_SCHEMA,
                               _still_summary_row) if resume else [])

    def run_one(row: dict[str, Any]) -> dict[str, Any]:
        return collect_still_one(
            row, out_dir, max_bytes=max_image_bytes,
            ffmpeg=ffmpeg, ffprobe=ffprobe)

    return _run_lane(
        pending, out_dir=out_dir, folder="stills",
        index_name="stills-index.json", schema=STILLS_INDEX_SCHEMA,
        catalog_sha=catalog_sha, run_one=run_one,
        summary_row=_still_summary_row, detail=_still_detail,
        label="still-measured", final_note="all downloaded poster images were "
                                           "deleted; only hashes and numbers remain",
        initial_skips=initial_skips, retained=retained,
        progress_total=len(pending), resume=False, jobs=jobs,
        delay_seconds=delay_seconds, offset=offset, limit=limit, log=log)


# ---------------------------------------------------------------------------
# report: read-only, evidence-bound aggregation
# ---------------------------------------------------------------------------

_NULL_CELL = "—"
DETAIL_LIMIT_REMINDER = (
    "sampled source-PTS windows only (not full-film review); numeric display-RGB "
    "and cut-candidate proxies are not style, quality, lighting, editing-intent, "
    "or authorship labels.")


def _write_text_atomic(path: Path, text: str) -> Path:
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
                "reason": f"unexpected schemaVersion {payload.get('schemaVersion')!r}"})
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
    }


def _mean_pair_delta_per_second(probe: dict[str, Any]) -> float | None:
    pairs = probe.get("sampledFramePairs")
    if not isinstance(pairs, list):
        return None
    values = [value for pair in pairs if isinstance(pair, dict)
              for value in (finite_float(
                  pair.get("meanAbsoluteDisplayRgbDeltaPerSecond")),)
              if value is not None]
    return round(statistics.mean(values), 6) if values else None


def _video_row(record: dict[str, Any]) -> dict[str, Any]:
    clip = record.get("clip") if isinstance(record.get("clip"), dict) else {}
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    acquisition = (record.get("acquisition")
                   if isinstance(record.get("acquisition"), dict) else {})
    coverage = record.get("coverage") if isinstance(record.get("coverage"), dict) else {}
    summary = record.get("summary") if isinstance(record.get("summary"), dict) else {}
    resolution = source.get("resolution")
    resolution_text = None
    if isinstance(resolution, list) and len(resolution) == 2:
        width, height = as_int(resolution[0]), as_int(resolution[1])
        if width is not None and height is not None:
            resolution_text = f"{width}x{height}"
    fps = finite_float(source.get("framesPerSecond"))
    if fps is None:
        fps = _rational_float(source.get("frameRate"))
    duration = finite_float(source.get("durationSeconds"))
    size = finite_float(source.get("sizeBytes"))
    bitrate = (round(size * 8 / duration / 1_000_000, 6)
               if size is not None and duration is not None and duration > 0
               else None)
    windows = record.get("windows") if isinstance(record.get("windows"), list) else []
    cuts = cut_columns(record)
    fraction = finite_float(coverage.get("fractionOfRuntime"))
    return {
        "clipId": as_int(record.get("clipId")),
        "slug": record.get("slug"),
        "title": clip.get("title"),
        "brand": clip.get("brand"),
        "rendition": acquisition.get("rendition"),
        "mediaSha256": source.get("mediaSha256"),
        "runtimeSeconds": duration,
        "resolution": resolution_text,
        "fps": fps,
        "bitrateMbps": bitrate,
        "downloadMb": (round(size / (1024 * 1024), 6)
                       if size is not None else None),
        "windowsMeasured": as_int(coverage.get("windowsMeasured")),
        "coveragePercent": round(fraction * 100, 6) if fraction is not None else None,
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
        "windowRows": [_window_row(window) for window in windows],
    }


def _video_order(row: dict[str, Any]) -> tuple[int, str]:
    clip_id = as_int(row.get("clipId"))
    return (clip_id if clip_id is not None else 0, str(row.get("slug") or ""))


def _table_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "windowRows"}


def _distribution(values: Iterable[float | None], *, digits: int = 6) -> dict[str, Any]:
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


def _list_length(index: dict[str, Any] | None, key: str) -> int:
    rows = index.get(key) if isinstance(index, dict) else None
    return len(rows) if isinstance(rows, list) else 0


def _latest_timestamp(records: Iterable[dict[str, Any]],
                      catalog: dict[str, Any] | None) -> str | None:
    stamps = [text for record in records
              for text in (as_text(record.get("generatedAt")),)
              if text is not None]
    if stamps:
        return max(stamps)
    return as_text(catalog.get("retrievedOn")) if isinstance(catalog, dict) else None


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
                        limit: int | None, top: int) -> list[str]:
    out, catalog = shlex.quote(str(out_dir)), shlex.quote(str(catalog_path))
    report = (f"python scripts/research_shots.py report "
              f"--out-dir {out} --catalog {catalog}")
    if limit is not None:
        report += f" --limit {limit}"
    report += f" --top {top}"
    return [
        "python scripts/research_shots.py catalog "
        f"--out {catalog} --limit 500",
        "python scripts/research_shots.py stills "
        f"--catalog {catalog} --out-dir {out} --resume",
        "python scripts/research_shots.py collect --catalog " + catalog +
        f" --out-dir {out} --limit 500 --acknowledge-rights",
        report,
    ]


def _render_report(aggregate: dict[str, Any], *, out_dir: Path,
                   catalog_path: Path, limit: int | None,
                   top: int) -> str:
    counts = aggregate["counts"]
    rows = aggregate["videos"]
    details = aggregate["details"]
    aggregates = aggregate["aggregates"]
    stills = aggregate["stills"]
    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    add("# shots.net — measured reference report")
    add()
    add("This deliverable tabulates only what the committed evidence records "
        "contain: catalog metadata, sampled source-PTS numeric probes, and "
        "single-published-still metrics. It makes no aesthetic, stylistic, "
        "intentional, authorship, or quality claim.")
    add()

    add("## Provenance")
    add()
    add(f"- Catalog clips: {_int(counts['catalogClips'])}")
    add(f"- Video-measured records: {_int(counts['videoMeasured'])}")
    add(f"- Unique media after dedupe: {_int(counts.get('videoUniqueMedia'))} "
        f"({_int(counts.get('videoDuplicateExtra'))} extra record(s) in "
        f"{_int(counts.get('videoDuplicateGroups'))} duplicate group(s))")
    add(f"- Still-measured records: {_int(counts['stillMeasured'])}")
    add(f"- Still-only records (no matching video record): {_int(counts['stillOnly'])}")
    add(f"- Skipped video items (index context): {_int(counts['skippedVideo'])}")
    add(f"- Skipped still items (stills index context): {_int(counts['skippedStills'])}")
    add(f"- Failed video acquisitions (index context): {_int(counts['failedVideo'])}")
    add(f"- Failed still acquisitions (stills index context): {_int(counts['failedStills'])}")
    skip_reasons = aggregate.get("skipReasons")
    if isinstance(skip_reasons, dict) and skip_reasons:
        add("- Video skip reasons (index context): " + ", ".join(
            f"{_cell(reason)} x {count}"
            for reason, count in sorted(skip_reasons.items())))
    still_skip_reasons = (aggregate.get("stills") or {}).get("skipReasons")
    if isinstance(still_skip_reasons, dict) and still_skip_reasons:
        add("- Still skip reasons (stills index context): " + ", ".join(
            f"{_cell(reason)} x {count}"
            for reason, count in sorted(still_skip_reasons.items())))
    add(f"- Unreadable records: {_int(counts['unreadable'])}")
    add(f"- generatedAt: {_cell(aggregate.get('generatedAt'))}")
    if limit is not None:
        add(f"- `--limit {limit}` applied: the first {len(rows)} of "
            f"{counts['videoMeasuredTotal']} video-measured records are tabulated.")
    add()
    add("Skip rows and failure rows are different outcomes. A **skip** is a "
        "pre-download decision: `no-allowlisted-public-rendition` means no "
        "ladder rung (720p web rendition, ready list stream, or signed "
        "original) passed the host/query policy, and a `pre-download-*` "
        "reason means catalog metadata alone exceeded a budget. A **failure** "
        "means a rendition was selected and the attempted acquisition raised. "
        "Neither row is a claim about the clip itself.")
    add()
    add("Reproduce the inputs and this report with:")
    add()
    add("```bash")
    for command in _reproduce_commands(
            out_dir=out_dir, catalog_path=catalog_path, limit=limit, top=top):
        add(command)
    add("```")
    add()
    add("Sampling caveat: coverage is `windows measured × window seconds ÷ "
        "runtime`; every window is a sample, not a full-film review. Across "
        f"the tabulated records, {_num(aggregates['coverage']['totalSampledSeconds'], 1)} s "
        f"of {_num(aggregates['coverage']['totalRuntimeSeconds'], 1)} s of runtime "
        "were measured "
        f"({_num((aggregates['coverage']['sampledFractionOfTotalRuntime'] or 0) * 100, 1)}%).")
    add()

    add("## Per-video analysis")
    add()
    add(f"{len(rows)} video-measured record(s), ordered by clip id then slug. "
        "All columns are numeric record fields; `bitrate_mbps` is derived from "
        "`sizeBytes ÷ durationSeconds` and `download_mb` from "
        "`sizeBytes ÷ 1,048,576`.")
    add()
    columns = (
        "clip_id", "slug", "title", "brand", "rendition", "runtime_s",
        "resolution", "fps", "bitrate_mbps", "download_mb", "windows",
        "coverage_pct", "candidates_n", "sampled_cut_candidates_per_min",
        "ci95", "burst", "gap_frames", "within_shot_pairs", "cut_sep_pairs",
        "delta_basis_pairs", "validity", "mean_luma", "mean_sat", "delta_per_s")
    add("| " + " | ".join(columns) + " |")
    add("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        ci = row["ci95"]
        values = (
            _int(row["clipId"]), row["slug"], row["title"], row["brand"],
            row["rendition"], _num(row["runtimeSeconds"], 2), row["resolution"],
            _num(row["fps"], 3), _num(row["bitrateMbps"], 2),
            _num(row["downloadMb"], 1), _int(row["windowsMeasured"]),
            _num(row["coveragePercent"], 1), _int(row["candidateCount"]),
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

    add(f"## Per-video detail (first {len(details)} by clip id)")
    add()
    if not details:
        add("No video-measured records.")
        add()
    for row, detail in zip(rows, details):
        add(f"### {_cell(row['slug'])} — {_cell(row['title'])}")
        add()
        add("| field | value |")
        add("| --- | --- |")
        for label, value in (
                ("clip_id", _int(row["clipId"])), ("brand", row["brand"]),
                ("rendition", row["rendition"]),
                ("runtime_s", _num(row["runtimeSeconds"], 2)),
                ("resolution", row["resolution"]), ("fps", _num(row["fps"], 3)),
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
            add("| " + " | ".join((
                _num(window["windowSeconds"], 2),
                _num(window["startSeconds"], 2),
                _int(window["sampledFrames"]),
                _int(window["cutCandidates"]),
                _num(window["meanDisplayLuma"], 4),
                _num(window["meanSaturation"], 4),
                _num(window["withinShotDeltaPerSecond"], 4))) + " |")
        add()
        add(f"limits: {DETAIL_LIMIT_REMINDER}")
        add()

    add("## Aggregates (video-measured records only)")
    add()
    add("Every number in this section is computed ONLY over the video-measured "
        "records tabulated above. Published stills, including still-only "
        "clips, never enter the motion, cut, luma, or saturation aggregates.")
    add()
    add("### Counts")
    add()
    add("| rendition | records |")
    add("| --- | --- |")
    for key, value in aggregates["byRendition"].items():
        add(f"| {_cell(key)} | {value} |")
    add()
    add("| brand | records |")
    add("| --- | --- |")
    for key, value in aggregates["byBrand"].items():
        add(f"| {_cell(key)} | {value} |")
    add()
    add("### Distributions")
    add()
    add("All minima and maxima are computed over `rankable` records only and "
        "name the record id and validity flags.")
    add()
    ranking = aggregates["cutRanking"]
    add(f"Unique records before dedupe: "
        f"{aggregates.get('recordCountBeforeDedupe')}; after dedupe: "
        f"{aggregates.get('recordCount')} "
        f"({(aggregates.get('dedupe') or {}).get('extraRecords', 0)} "
        "duplicate extra record(s) collapsed).")
    add()
    add(f"Rankable records: {ranking['rankable']} of "
        f"{aggregates['recordCount']} unique; excluded as non-rankable: "
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
    coverage = aggregates["coverage"]
    add("Coverage-weighted caveat: "
        f"{_num(coverage['totalSampledSeconds'], 1)} sampled seconds cover "
        f"{_num(coverage['totalRuntimeSeconds'], 1)} runtime seconds "
        f"({_num((coverage['sampledFractionOfTotalRuntime'] or 0) * 100, 1)}%). "
        "Aggregates describe the sampled windows, not the full clips.")
    add()

    add("## Comparability")
    add()
    for line in comparability_lines(aggregates["comparability"]):
        add(line)
    add()

    add("## Coverage")
    add()
    add("Per-record coverage distribution over the deduped records. The "
        "unobserved gap is the median time between consecutive sampled windows, "
        "derived from runtime, window count and sampled seconds.")
    add()
    for line in coverage_lines(aggregates["coverageDistribution"]):
        add(line)
    add()

    add("## Published-still evidence (single-frame only)")
    add()
    add("Separate lane. A published poster still is not a video frame: these "
        "numbers are single-frame image metrics, carry no motion, cut, pacing, "
        "or timing evidence, and are never used in the video aggregates above.")
    add()
    add(f"- n: {stills['n']}")
    add("- decode size: stills are measured at the aspect-preserving "
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
    quality = aggregate.get("stillQuality") or {}
    add("### Still quality signals")
    add()
    add("Quality flags are measurements, not verdicts: the record keeps every "
        "number above so a consumer can decide. A still carrying any flag is "
        "excluded from this section's colour aggregates and counted separately "
        "here.")
    add()
    add(f"- flagged stills (excluded from colour aggregates): "
        f"{quality.get('flagged', 0)} of {stills['n']}")
    add()
    add("| quality flag | stills |")
    add("| --- | --- |")
    for key, value in (quality.get("flags") or {}).items():
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
            "Windows are sampled; `fullRuntimeMeasured` is false for every "
            "video record, so nothing here is a full-film review.",
            "Public availability is not a licence: `rightsStatus` remains "
            "`review-required`, and reuse needs its own review.",
            "`downloadAllowed` was false on the platform for every sampled "
            "clip; that fact is recorded, not worked around.",
            "Published stills are single images, not video frames, and carry "
            "no motion, cut, pacing, sequence, or timing evidence.",
            "Catalog metadata is self-reported by shots.net and is not "
            "independently verified.",
            "Downloaded media, frames, thumbnails, and audio are never retained."):
        add(f"- {claim}")
    add()
    return "\n".join(lines)


def run_report(
    out_dir: Path, *, catalog_path: Path | None = None,
    limit: int | None = None, top: int = 20,
    generated_at: str | None = None, log: Callable[[str], None] = print,
) -> int:
    """Read collected records read-only and write ``report.md`` + ``aggregate.json``."""
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a non-negative integer")
    if type(top) is not int or top < 0:
        raise ValueError("top must be a non-negative integer")
    out_dir = Path(out_dir)
    requested_catalog = Path(catalog_path) if catalog_path is not None else None
    if requested_catalog is not None and not requested_catalog.is_file():
        raise ValueError("catalog file does not exist")
    default_catalog = out_dir / "catalog.json"
    catalog_path = (requested_catalog if requested_catalog is not None
                    else (default_catalog if default_catalog.is_file() else None))

    video_records, problems = _load_records(out_dir / "videos", VIDEO_SCHEMA,
                                            prefix="videos")
    still_records, still_problems = _load_records(out_dir / "stills", STILL_SCHEMA,
                                                  prefix="stills")
    problems.extend(still_problems)
    catalog, catalog_problems = _load_json_context(catalog_path, prefix="catalog.json")
    index, index_problems = _load_json_context(out_dir / "index.json",
                                               prefix="index.json")
    stills_index, stills_index_problems = _load_json_context(
        out_dir / "stills-index.json", prefix="stills-index.json")
    problems.extend(catalog_problems)
    problems.extend(index_problems)
    problems.extend(stills_index_problems)
    problems.sort(key=lambda item: (item["file"], item["reason"]))

    if generated_at is None:
        generated_at = _latest_timestamp([*video_records, *still_records], catalog)

    all_rows = sorted((_video_row(record) for record in video_records),
                      key=_video_order)
    measured_total = len(all_rows)
    tabulated = all_rows[:limit] if limit is not None else all_rows
    unique_rows = list(unique_media_rows(tabulated))
    dedupe = duplicate_summary(
        [{"id": row["slug"], "mediaSha256": row["mediaSha256"]}
         for row in tabulated], "mediaSha256")
    details = [{"slug": row["slug"], "windows": row["windowRows"]}
               for row in tabulated[:top]]

    video_keys = {as_int(record.get("clipId")) for record in video_records}
    still_only = sum(1 for record in still_records
                     if as_int(record.get("clipId")) not in video_keys)
    skip_reasons = _skip_reasons(index)
    still_skip_reasons = _skip_reasons(stills_index)
    still_metrics = [((record.get("still") or {}).get("metrics") or {})
                     for record in still_records
                     if isinstance(record.get("still"), dict)
                     and not still_has_quality_flags(record)]
    still_evidence = [record for record in still_records
                      if not still_has_quality_flags(record)]
    still_lumas = [finite_float(metrics.get("meanDisplayLumaProxy"))
                   for metrics in still_metrics]
    still_lumas = [value for value in still_lumas if value is not None]
    paired = [(row["runtimeSeconds"], row["sampledSeconds"]) for row in unique_rows
              if row.get("runtimeSeconds") is not None and row["runtimeSeconds"] > 0
              and row.get("sampledSeconds") is not None]
    total_runtime = round(sum(runtime for runtime, _ in paired), 6) if paired else 0.0
    total_sampled = round(sum(sampled for _, sampled in paired), 6) if paired else 0.0
    catalog_clips = None
    if isinstance(catalog, dict):
        catalog_clips = as_int(catalog.get("clipCount"))
        if catalog_clips is None and isinstance(catalog.get("clips"), list):
            catalog_clips = len(catalog["clips"])

    aggregate = {
        "schemaVersion": AGGREGATE_SCHEMA,
        "generatedAt": generated_at,
        "counts": {
            "catalogClips": catalog_clips,
            "videoMeasured": len(tabulated),
            "videoMeasuredTotal": measured_total,
            "videoUniqueMedia": len(unique_rows),
            "videoDuplicateGroups": dedupe["groups"],
            "videoDuplicateExtra": dedupe["extraRecords"],
            "stillMeasured": len(still_records),
            "stillOnly": still_only,
            "skippedVideo": _list_length(index, "skips"),
            "skippedStills": _list_length(stills_index, "skips"),
            "failedVideo": _list_length(index, "failures"),
            "failedStills": _list_length(stills_index, "failures"),
            "unreadable": len(problems),
        },
        "videos": [_table_row(row) for row in tabulated],
        "details": details,
        "aggregates": {
            "basis": "video-measured records only; published stills never enter "
                     "these numbers",
            "recordCount": len(unique_rows),
            "recordCountBeforeDedupe": len(tabulated),
            "dedupe": dedupe,
            "byRendition": _counter(row["rendition"] for row in unique_rows),
            "byBrand": _counter(row["brand"] for row in unique_rows),
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
                "coveragePercent": _distribution(
                    row["coveragePercent"] for row in unique_rows),
            },
            "cutRanking": {
                "basis": "rankable unique records only; non-rankable rows are "
                         "excluded from cut aggregates",
                "rankable": sum(1 for row in unique_rows if row["rankable"]),
                "excluded": sum(1 for row in unique_rows
                                if not row["rankable"]),
                "candidatesPerMinute": aggregate_extremes(
                    unique_rows, "sampledCutCandidatesPerMinute", id_key="slug",
                    gate=True),
                "candidateCount": aggregate_extremes(
                    unique_rows, "candidateCount", id_key="slug", gate=True),
                "runtimeSeconds": aggregate_extremes(
                    unique_rows, "runtimeSeconds", id_key="slug",
                    gate=True),
                "meanDisplayLuma": aggregate_extremes(
                    unique_rows, "meanDisplayLuma", id_key="slug",
                    gate=True),
                "meanSaturation": aggregate_extremes(
                    unique_rows, "meanSaturation", id_key="slug",
                    gate=True),
                "meanWithinShotDeltaPerSecond": aggregate_extremes(
                    unique_rows, "meanWithinShotDeltaPerSecond",
                    id_key="slug", gate=True),
            },
            "coverage": {
                "recordsWithRuntime": sum(1 for row in unique_rows
                                          if row.get("runtimeSeconds") is not None),
                "recordsWithCoverage": len(paired),
                "totalRuntimeSeconds": total_runtime,
                "totalSampledSeconds": total_sampled,
                "sampledFractionOfTotalRuntime": (
                    round(total_sampled / total_runtime, 6)
                    if total_runtime else None),
            },
            "coverageDistribution": coverage_distribution(unique_rows),
            "comparability": comparability_block(
                site="shots.net",
                catalog_size=catalog_clips,
                measured=len(tabulated),
                selection_rule=("allowlisted 720p web rendition, ready list "
                                "stream, or signed original availability"),
                provider_counts=_counter(row["rendition"] for row in unique_rows),
                rendition_notes=("platform-encoded source renditions only; "
                                 "no ladder rung is the delivered master"),
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
            "skipReasons": still_skip_reasons,
            "decodeSizes": still_decode_counts(still_records),
        },
        "stillQuality": still_quality_summary(still_records),
        "skipReasons": skip_reasons,
        "unreadableRecords": problems,
    }

    report_path = out_dir / "report.md"
    aggregate_path = out_dir / "aggregate.json"
    write_json_atomic(aggregate_path, aggregate)
    _write_text_atomic(report_path, _render_report(
        aggregate, out_dir=out_dir,
        catalog_path=catalog_path or default_catalog, limit=limit, top=top))
    log(f"report: videos={len(tabulated)} stills={len(still_records)} "
        f"stillOnly={still_only} unreadable={len(problems)} -> {report_path}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _add_common_batch(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--resume", dest="resume", action="store_true",
                       default=True)
    group.add_argument("--refresh", dest="resume", action="store_false")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ephemeral shots.net video/still research collector")
    sub = parser.add_subparsers(dest="command", required=True)

    catalog = sub.add_parser(
        "catalog", help="fetch a slim normalized clip catalog from the public endpoint")
    catalog.add_argument("--out", type=Path, required=True,
                         help="path for the versioned catalog JSON")
    catalog.add_argument("--limit", type=int, default=DEFAULT_CATALOG_LIMIT,
                         help="catalog size (0 = no request)")
    catalog.add_argument("--offset", type=int, default=0,
                         help="offset into the live newest-first library")
    catalog.add_argument("--since", default=None,
                         help="stop paging once results are older than YYYY-MM-DD")
    catalog.add_argument("--page-size", type=int, default=DEFAULT_CATALOG_PAGE_SIZE)
    catalog.add_argument("--delay-seconds", type=float, default=DEFAULT_CATALOG_DELAY,
                         help="politeness pause (plus equal jitter) between pages")

    collect = sub.add_parser(
        "collect", help="download, measure, and delete public video renditions")
    collect.add_argument("--catalog", type=Path, default=None,
                         help="catalog JSON (required unless --limit 0)")
    collect.add_argument("--out-dir", type=Path, default=Path("research/analysis/shots"))
    collect.add_argument("--limit", type=int, default=DEFAULT_VIDEO_LIMIT,
                         help="clips in this slice (0 = offline no-op)")
    collect.add_argument("--offset", type=int, default=0)
    collect.add_argument("--windows", type=int, default=4)
    collect.add_argument("--window-seconds", type=int, default=10)
    collect.add_argument("--max-samples", type=int, default=12)
    collect.add_argument("--max-duration-seconds", type=float,
                         default=DEFAULT_MAX_DURATION_SECONDS)
    collect.add_argument("--max-file-bytes", type=int,
                         default=DEFAULT_MAX_FILE_BYTES)
    collect.add_argument("--image-translation",
                         action=argparse.BooleanOptionalAction, default=False)
    collect.add_argument("--acknowledge-rights", action="store_true")
    collect.add_argument("--rights-note", default=DEFAULT_RIGHTS_NOTE)
    collect.add_argument("--delay-seconds", type=float, default=DEFAULT_VIDEO_DELAY,
                         help="politeness pause (plus equal jitter) between videos")
    _add_common_batch(collect)

    stills = sub.add_parser(
        "stills", help="measure one published poster still per catalog clip")
    stills.add_argument("--catalog", type=Path, default=None,
                        help="catalog JSON (default: <out-dir>/catalog.json)")
    stills.add_argument("--out-dir", type=Path, default=Path("research/analysis/shots"))
    stills.add_argument("--limit", type=int, default=0,
                        help="0 = every remaining clip; N = first N pending")
    stills.add_argument("--offset", type=int, default=0)
    stills.add_argument("--delay-seconds", type=float, default=DEFAULT_STILL_DELAY,
                        help="politeness pause (plus equal jitter) between stills")
    stills.add_argument("--page-size", type=int, default=DEFAULT_STILL_PAGE_SIZE,
                        help="catalog rows per local page (empty page terminates)")
    stills.add_argument("--max-image-bytes", type=int, default=STILL_MAX_BYTES)
    _add_common_batch(stills)

    report = sub.add_parser(
        "report", help="write report.md + aggregate.json from collected records")
    report.add_argument("--out-dir", type=Path, required=True)
    report.add_argument("--catalog", type=Path, default=None,
                        help="catalog JSON (default: <out-dir>/catalog.json)")
    report.add_argument("--limit", type=int, default=None,
                        help="cap the video-measured records included")
    report.add_argument("--top", type=int, default=20,
                        help="per-video detail blocks to render")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            return run_catalog(
                args.out, limit=args.limit, offset=args.offset, since=args.since,
                page_size=args.page_size, delay_seconds=args.delay_seconds)
        if args.command == "report":
            return run_report(args.out_dir, catalog_path=args.catalog,
                              limit=args.limit, top=args.top)
        if args.command == "stills":
            return run_stills(
                args.catalog, out_dir=args.out_dir, limit=args.limit,
                offset=args.offset, resume=args.resume, jobs=args.jobs,
                delay_seconds=args.delay_seconds, page_size=args.page_size,
                max_image_bytes=args.max_image_bytes, ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe)
        if not args.acknowledge_rights:
            parser.error(
                "--acknowledge-rights is required: public availability is not a "
                "license and downloaded media is deleted after measurement")
        return run_collect(
            args.catalog, out_dir=args.out_dir, limit=args.limit,
            offset=args.offset, resume=args.resume, jobs=args.jobs,
            acknowledge_rights=args.acknowledge_rights,
            delay_seconds=args.delay_seconds, windows=args.windows,
            window_seconds=args.window_seconds, max_samples=args.max_samples,
            max_duration_seconds=args.max_duration_seconds,
            max_file_bytes=args.max_file_bytes,
            image_translation=args.image_translation,
            rights_note=args.rights_note, ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe)
    except ValueError as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    sys.exit(main())
