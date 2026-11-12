"""Ephemeral, source-hashed measurement of Promonews poster stills.

Promonews' public catalogue is an Elasticsearch proxy (``POST
/api/content/video/_search``) with no auth. It reports 17,805 videos, and
virtually every one is a YouTube or Vimeo embed: the site publishes no
progressive MP4/HLS file. Per repository policy those providers are recorded as
unsupported and never attempted. There is therefore **no video lane**; the
honest deliverable is full catalogue coverage plus one measured *published
poster still* per item, labelled still-only.

The catalogues's ES-6-shaped result window is 10,000: ``from=10000`` answers
HTTP 500. Pagination is continued by sharding on the ``created`` epoch with a
bare ``{"range": {"created": {"lt": ...}}}`` query, restarting ``from`` at 0 at
each boundary. Every boundary is logged. The DSL is kept minimal on purpose:
``track_total_hits``, ``bool``, and term filters made this endpoint answer 500.

This is a *site adapter*: allowlisting, bounded retrieval, still measurement,
evidence assembly, atomic writes, resume checks, index assembly, and the pooled
batch loop come from :mod:`kumiki_reference_lab.acquisition`. The adapter
supplies the endpoint, the slim catalogue projection, the image host policy,
schema/evidence/limits/rights strings, and the CLI.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition import (  # noqa: E402
    STILL_MAX_BYTES, STILL_METHOD, USER_AGENT, allowlisted_image_url,
    allowlisted_url, as_int, as_text, build_index, build_still_evidence,
    download_http, finite_float, image_target, measure_still,
    resume_matches as _resume_matches, run_batch, safe_error, safe_slug,
    still_image_format, utc_now, write_json_atomic,
)
from kumiki_reference_lab.analyzers.media.inspect import sha256_file  # noqa: E402

# ---------------------------------------------------------------------------
# site constants and schemas
# ---------------------------------------------------------------------------

ENDPOINT = "https://www.promonews.tv/api/content/video/_search"
SOURCE_HOST = "www.promonews.tv"
PUBLIC_BASE = "https://www.promonews.tv"
CMS_BASE = "https://admin.promonews.tv"

CATALOG_SCHEMA = "kumiki.promonews-catalog.v1"
STILL_SCHEMA = "kumiki.promonews-still-evidence.v1"
STILLS_INDEX_SCHEMA = "kumiki.promonews-stills-index.v1"
AGGREGATE_SCHEMA = "kumiki.promonews-aggregate.v1"

# Drupal serves poster derivatives (``?itok=``) from the CMS host only. This is
# the one place the engine's query opt-in is enabled; ``www`` and every other
# host stay refused.
IMAGE_HOSTS = ("admin.promonews.tv",)
POSTER_ALLOW_QUERY = True

# ES-6 result window: from + size must stay below 10,000 or the endpoint 500s.
RESULT_WINDOW = 10_000
DEFAULT_PAGE_SIZE = 100
DEFAULT_CATALOG_DELAY = 1.0
DEFAULT_STILL_DELAY = 0.6
DEFAULT_TOP = 20
DEFAULT_LIMIT: int | None = None
MAX_JOBS = 3
_MAX_PAGES = 2_000
_MAX_RESPONSE_BYTES = 16_000_000

STILL_EVIDENCE_STATUS = "single-published-still-metrics-not-video-measurement"
STILL_COVERAGE_NOTE = (
    "single published poster still from Promonews' own image derivative, "
    "decoded once at 160x90 RGB; not a decoded video frame, no motion/time "
    "evidence")
RIGHTS_BASIS = "user-declared-research-use"
RIGHTS_STATUS = "review-required"

STILL_LIMITS = [
    "A published poster still is not a video frame: no motion, cut, pacing, "
    "timing, sequence, or edit-rhythm evidence is claimed.",
    "Colour, luminance, histogram, hue, and edge-density numbers describe one "
    "published image only; they are not aesthetic, style, quality, authorship, "
    "or creative-intent judgements.",
    "The poster is prepared by the site/CMS, not necessarily by the work's "
    "author.",
    "The downloaded image was deleted immediately after measurement; no image "
    "bytes are retained.",
    "Every catalogue video reference is a YouTube or Vimeo embed; no video was "
    "downloaded, probed, or player-inspected, and no cookies, logins, player-"
    "API tricks, or DRM circumvention were used.",
    "Public availability is not a licence; rightsStatus remains "
    "review-required.",
    "Catalogue metadata is self-reported by Promonews and is not independently "
    "verified.",
]

_STILL_FOLDER = "stills"
_INDEX_NAME = "stills-index.json"
_CATALOG_NAME = "catalog.json"
_SCRATCH_PREFIX = "kumiki-promonews-still-"


# ---------------------------------------------------------------------------
# small coercion helpers
# ---------------------------------------------------------------------------


def _name(value: object) -> str | None:
    if isinstance(value, dict):
        for key in ("name", "title", "label"):
            text = as_text(value.get(key))
            if text:
                return text
        return None
    return as_text(value)


def _names(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        text = _name(value)
        return [text] if text else []
    if isinstance(value, str):
        text = as_text(value)
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        names: list[str] = []
        for item in value:
            text = _name(item)
            if text and text not in names:
                names.append(text)
        return names
    return []


def _counter(values: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = as_text(value) or "none"
        counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _distribution(
    values: Iterable[float | None], *, digits: int = 6,
) -> dict[str, Any]:
    numbers = [value for value in values if value is not None]
    if not numbers:
        return {"n": 0, "min": None, "median": None, "max": None}
    return {
        "n": len(numbers),
        "min": round(min(numbers), digits),
        "median": round(statistics.median(numbers), digits),
        "max": round(max(numbers), digits),
    }


def _total_hits(value: object) -> int | None:
    """Read an ES-6 numeric ``hits.total`` (tolerating an ES-7 object form)."""
    number = as_int(value)
    if number is not None:
        return number
    if isinstance(value, dict):
        return as_int(value.get("value"))
    return None


# ---------------------------------------------------------------------------
# catalogue: the minimal ES query and the created-range shard
# ---------------------------------------------------------------------------


def search_body(
    page_size: int, offset: int, *, before: int | None = None,
) -> dict[str, Any]:
    """Build one minimal search body.

    The body carries exactly ``size``, ``from``, ``query`` and ``sort``.
    ``track_total_hits``, ``bool``, and term filters are deliberately absent:
    each produced HTTP 500 on this endpoint. Past the result window the query
    is replaced by a bare ``range`` on ``created`` (never both via ``bool``).
    """
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ValueError("catalog page size must be between 1 and 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("catalog offset must be a non-negative integer")
    if before is not None and (type(before) is not int or before <= 0):
        raise ValueError("created boundary must be a positive integer epoch")
    query: dict[str, Any] = (
        {"match_all": {}} if before is None
        else {"range": {"created": {"lt": before}}})
    return {
        "size": page_size,
        "from": offset,
        "query": query,
        "sort": [{"created": {"order": "desc"}}],
    }


def _post_search(
    body: dict[str, Any], *, timeout: float = 45.0, retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """POST one validated search body.

    A 4xx/5xx from this endpoint is treated as a *query* error, not a transient
    fault, and is never retried: bad DSL answers HTTP 500. Only transport and
    timeout errors are retried, with bounded exponential backoff.
    """
    allowlisted_url(ENDPOINT, allowed_hosts=(SOURCE_HOST,),
                    label="catalog endpoint")
    payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(retries):
        request = Request(ENDPOINT, data=payload, method="POST", headers={
            "Accept": "application/json", "Content-Type": "application/json",
            "User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=timeout) as response:
                allowlisted_url(response.geturl(), allowed_hosts=(SOURCE_HOST,),
                                label="catalog redirect")
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            raise ValueError(
                "catalog search rejected the query "
                f"(HTTP {error.code}); a 500 here is usually bad DSL, not a "
                "transient fault") from None
        except (URLError, TimeoutError, OSError) as error:
            last_error = error
        else:
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise ValueError("catalog response exceeded the size limit")
            try:
                result = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise ValueError("catalog response was not valid JSON") from None
            if not isinstance(result, dict):
                raise ValueError("catalog response was not a JSON object")
            hits = result.get("hits")
            if not isinstance(hits, dict) or not isinstance(hits.get("hits"), list):
                raise ValueError("catalog response has no hits.hits list")
            return result
        if attempt + 1 < retries:
            sleep(2 ** attempt)
    raise RuntimeError(
        "catalog request failed after bounded retries") from last_error


# ---------------------------------------------------------------------------
# row projection: identity, URLs, provider, poster, credits
# ---------------------------------------------------------------------------


def _created_epoch(source: Mapping[str, Any]) -> int | None:
    return as_int(source.get("created"))


def _link_path(source: Mapping[str, Any]) -> str | None:
    link = as_text(source.get("link"))
    if link is None:
        return None
    try:
        segments = [part for part in urlsplit(link).path.split("/") if part]
    except ValueError:
        return None
    if len(segments) >= 5 and segments[0] == "videos":
        return "/videos/" + "/".join(segments[1:])
    return None


def video_path(source: Mapping[str, Any], nid: int) -> str:
    """Derive ``/videos/YYYY/MM/DD/<slug>`` from ``link`` or ``created``."""
    path = _link_path(source)
    if path is not None:
        return path
    slug: str | None = None
    link = as_text(source.get("link"))
    if link is not None:
        try:
            segments = [part for part in urlsplit(link).path.split("/") if part]
        except ValueError:
            segments = []
        if segments:
            try:
                slug = safe_slug(segments[-1])
            except ValueError:
                slug = None
    if slug is None:
        title = as_text(source.get("title"))
        if title is not None:
            try:
                slug = safe_slug(title)
            except ValueError:
                slug = None
    slug = slug or f"video-{nid}"
    created = _created_epoch(source)
    if created is not None:
        moment = datetime.fromtimestamp(created, tz=timezone.utc)
        return f"/videos/{moment:%Y/%m/%d}/{slug}"
    return f"/videos/{slug}"


def _video_entries(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    videos = source.get("videos")
    if isinstance(videos, dict):
        return [videos]
    if isinstance(videos, list):
        return [entry for entry in videos if isinstance(entry, dict)]
    return []


def classify_provider(video_url: object, filemime: object = None) -> str:
    """Classify an embed by declared MIME first, host second. Never guesses."""
    mime = (as_text(filemime) or "").lower()
    if "youtube" in mime or "youtu" in mime:
        return "youtube"
    if "vimeo" in mime:
        return "vimeo"
    text = as_text(video_url)
    if text is not None:
        try:
            host = (urlsplit(text).hostname or "").lower()
        except ValueError:
            host = ""
        if (host == "youtu.be" or host.endswith(".youtube.com")
                or host == "youtube.com"
                or host.endswith(".youtube-nocookie.com")):
            return "youtube"
        if host == "vimeo.com" or host.endswith(".vimeo.com"):
            return "vimeo"
    return "other"


def unsupported_reason(provider: str | None) -> str | None:
    """The explicit, recorded reason a provider is never attempted."""
    if provider is None:
        return "no-video-reference"
    if provider == "youtube":
        return "unsupported-youtube"
    if provider == "vimeo":
        return "unsupported-vimeo"
    return "unsupported-provider"


def policy_image_url(url: object) -> str:
    """Allowlist exactly the CMS image host, with Drupal's ``?itok=`` token."""
    return allowlisted_image_url(
        url, allowed_hosts=IMAGE_HOSTS, allow_query=POSTER_ALLOW_QUERY)


def _poster(
    images: object,
) -> tuple[str | None, int | None, int | None]:
    """Prefer ``images[0].thumb``, then ``full``, then ``original``."""
    if not isinstance(images, list):
        return None, None, None
    for image in images:
        if not isinstance(image, dict):
            continue
        info = image.get("info") if isinstance(image.get("info"), dict) else {}
        width, height = as_int(info.get("width")), as_int(info.get("height"))
        for key in ("thumb", "full", "original"):
            value = image.get(key)
            if not as_text(value):
                continue
            try:
                return policy_image_url(value), width, height
            except ValueError:
                continue
    return None, None, None


def _credits(value: object) -> list[dict[str, Any]]:
    """Project ``credits[]`` to role→name pairs, preserving explicit nulls."""
    if not isinstance(value, list):
        return []
    credits: list[dict[str, Any]] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        role, name = as_text(entry.get("role")), as_text(entry.get("name"))
        if role is None and name is None:
            continue
        credits.append({"role": role, "name": name})
    return credits


_DATE_KEYS = ("published", "release_date", "submitted_release_date")


def _date_text(value: object) -> str | None:
    """Normalise a date or epoch-seconds value; reject boolean-ish 0/1."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = as_int(value)
        if number is None or number <= 100_000_000:
            return None
        return datetime.fromtimestamp(number, tz=timezone.utc).strftime("%Y-%m-%d")
    text = as_text(value)
    if text is not None:
        if text.isdigit() and 9 <= len(text) <= 11:
            return datetime.fromtimestamp(
                int(text), tz=timezone.utc).strftime("%Y-%m-%d")
        if len(text) >= 4 and not text.isdigit():
            return text
    return None


def published_date(source: Mapping[str, Any]) -> str | None:
    """Read a date-like ``published``/``release_date`` value; never booleans."""
    for key in _DATE_KEYS:
        text = _date_text(source.get(key))
        if text is not None:
            return text
    return None


def normalize_source(source: Mapping[str, Any]) -> dict[str, Any]:
    """Project one ``hits.hits[]._source`` into the slim, deterministic row."""
    if not isinstance(source, dict):
        raise ValueError("catalog hit source must be an object")
    nid = as_int(source.get("nid"))
    if nid is None:
        raise ValueError("catalog hit has no integer nid")
    path = video_path(source, nid)
    slug = path.rsplit("/", 1)[-1]
    entries = _video_entries(source)
    video_url = as_text(entries[0].get("url")) if entries else None
    provider = (classify_provider(video_url, entries[0].get("filemime"))
                if entries else None)
    poster_url, poster_width, poster_height = _poster(source.get("images"))
    return {
        "nid": nid,
        "slug": slug,
        "title": as_text(source.get("title")) or "",
        "publishedDate": published_date(source),
        "createdEpoch": _created_epoch(source),
        "publicUrl": f"{PUBLIC_BASE}{path}",
        "cmsUrl": f"{CMS_BASE}{path}",
        "provider": provider,
        "unsupportedReason": unsupported_reason(provider),
        "posterUrl": poster_url,
        "posterWidth": poster_width,
        "posterHeight": poster_height,
        "durationSeconds": None,
        "categories": _names(source.get("categories")),
        "genres": _names(source.get("genres")),
        "tags": _names(source.get("tags")),
        "countries": _names(source.get("countries")),
        "credits": _credits(source.get("credits")),
        "videoUrl": video_url,
    }


def catalog_order(row: Mapping[str, Any]) -> tuple[int, int]:
    """Stable catalogue order: created epoch descending, then nid descending."""
    created = as_int(row.get("createdEpoch"))
    nid = as_int(row.get("nid"))
    return (created if created is not None else -1,
            nid if nid is not None else -1)


def _page_last_created(page: Iterable[object]) -> int | None:
    stamps = [as_int((hit.get("_source") or {}).get("created"))
              for hit in page
              if isinstance(hit, dict) and isinstance(hit.get("_source"), dict)]
    values = [stamp for stamp in stamps if stamp is not None]
    return min(values) if values else None


def fetch_catalog(
    *, limit: int | None = DEFAULT_LIMIT,
    page_size: int = DEFAULT_PAGE_SIZE,
    delay_seconds: float = DEFAULT_CATALOG_DELAY,
    fetch: Callable[[dict[str, Any]], dict[str, Any]] = _post_search,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> tuple[list[dict[str, Any]], int | None, dict[str, Any]]:
    """Page the full catalogue, sharding on ``created`` past the 10k window.

    ``limit=None`` means every video; ``limit=0`` is an offline no-op. The
    returned meta block records pages, shard boundaries, and whether the
    catalogue was exhausted within a shard.
    """
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("catalog limit must be a non-negative integer or None")
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ValueError("catalog page size must be between 1 and 100")
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("catalog delay must be a non-negative number")
    meta: dict[str, Any] = {
        "pagesFetched": 0, "shards": 0, "boundaries": [],
        "exhausted": False, "skippedMalformed": 0,
    }
    if limit == 0:
        meta["exhausted"] = True
        return [], None, meta

    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    total: int | None = None
    offset, before = 0, None
    pages = shards = 0

    while pages < _MAX_PAGES:
        if limit is not None and len(rows) >= limit:
            break
        payload = fetch(search_body(page_size, offset, before=before))
        block = payload.get("hits") if isinstance(payload, dict) else None
        if not isinstance(block, dict) or not isinstance(block.get("hits"), list):
            raise ValueError("catalog response has no hits block")
        page = block["hits"]
        if total is None:
            total = _total_hits(block.get("total"))
        pages += 1
        for hit in page:
            if not isinstance(hit, dict):
                continue
            source = hit.get("_source")
            if not isinstance(source, dict):
                continue
            try:
                row = normalize_source(source)
            except ValueError:
                meta["skippedMalformed"] += 1
                continue
            if row["nid"] in seen:
                continue
            seen.add(row["nid"])
            rows.append(row)
        log(f"catalog page {pages}: {len(page)} hits "
            f"({len(rows)} collected, from={offset}"
            f"{f', created<{before}' if before is not None else ''})")

        if not page:
            meta["exhausted"] = True
            break
        if limit is not None and len(rows) >= limit:
            rows = rows[:limit]
            break
        if len(page) < page_size:
            meta["exhausted"] = True
            break

        next_offset = offset + len(page)
        # ES rejects a request whose ``from + size`` crosses the window at all
        # (even when ``from`` itself is below it), so shard before that happens.
        if next_offset + page_size > RESULT_WINDOW:
            last_created = _page_last_created(page)
            if last_created is None:
                log("catalog: result window reached without a created "
                    "boundary; stopping")
                meta["exhausted"] = True
                break
            if before is not None and last_created >= before:
                log("catalog: created boundary did not advance; stopping")
                meta["exhausted"] = True
                break
            shards += 1
            meta["boundaries"].append(last_created)
            log(f"catalog shard {shards}: created < {last_created}, "
                "from reset to 0")
            before, offset = last_created, 0
        else:
            offset = next_offset
        if delay_seconds:
            sleep(float(delay_seconds)
                  + random.uniform(0, float(delay_seconds)))

    if pages >= _MAX_PAGES:
        raise ValueError("catalog pagination exceeded the safety page budget")
    meta["pagesFetched"], meta["shards"] = pages, shards
    return sorted(rows, key=catalog_order, reverse=True), total, meta


def _top_genres(rows: Iterable[Mapping[str, Any]], top: int = 20) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        genres = row.get("genres")
        if not isinstance(genres, list):
            continue
        for genre in genres:
            text = as_text(genre)
            if text is not None:
                counts[text] = counts.get(text, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"name": name, "count": count} for name, count in ordered[:top]]


def build_catalog(
    rows: Iterable[dict[str, Any]], total: int | None, *,
    generated_at: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    limit: int | None = DEFAULT_LIMIT,
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the slim catalogue document with its reconciliation counts."""
    videos = sorted(rows, key=catalog_order, reverse=True)
    meta = dict(meta or {})
    provider_counts: dict[str, int] = {}
    for row in videos:
        key = row.get("provider") or "none"
        provider_counts[key] = provider_counts.get(key, 0) + 1
    counts = {
        "collected": len(videos),
        "reportedTotal": total,
        "complete": bool(limit is None and total is not None
                         and len(videos) >= total),
        "pagesFetched": meta.get("pagesFetched", 0),
        "shards": meta.get("shards", 0),
        "createdBoundaries": list(meta.get("boundaries") or []),
        "exhausted": bool(meta.get("exhausted", False)),
        "skippedMalformed": meta.get("skippedMalformed", 0),
        "resultWindow": RESULT_WINDOW,
        "byProvider": {key: provider_counts[key]
                       for key in sorted(provider_counts)},
        "topGenres": _top_genres(videos),
    }
    return {
        "schemaVersion": CATALOG_SCHEMA,
        "generatedAt": generated_at or utc_now(),
        "sourceHost": SOURCE_HOST,
        "endpoint": ENDPOINT,
        "query": {
            "pageSize": page_size,
            "limit": limit,
            "sort": [{"created": {"order": "desc"}}],
            "query": {"match_all": {}},
            "shardOn": "created",
        },
        "counts": counts,
        "videos": videos,
    }


def _load_catalog(path: Path) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or catalog.get(
            "schemaVersion") != CATALOG_SCHEMA:
        raise ValueError("unsupported catalog schema")
    if not isinstance(catalog.get("videos"), list):
        raise ValueError("catalog has no video list")
    return catalog


def run_catalog(
    out: Path, *, limit: int | None = DEFAULT_LIMIT,
    page_size: int = DEFAULT_PAGE_SIZE,
    delay_seconds: float = DEFAULT_CATALOG_DELAY,
    log: Callable[[str], None] = print,
) -> int:
    rows, total, meta = fetch_catalog(
        limit=limit, page_size=page_size, delay_seconds=delay_seconds, log=log)
    catalog = build_catalog(
        rows, total, page_size=page_size, limit=limit, meta=meta)
    write_json_atomic(Path(out), catalog)
    log(f"catalog: {catalog['counts']['collected']} videos of "
        f"{catalog['counts']['reportedTotal']} reported "
        f"({catalog['counts']['shards']} shard boundaries) -> {out}")
    return 0


# ---------------------------------------------------------------------------
# record identity and builders
# ---------------------------------------------------------------------------


def record_stem(row: Mapping[str, Any]) -> str:
    nid = as_int(row.get("nid"))
    if nid is None:
        raise ValueError("row has no integer nid")
    slug = safe_slug(row.get("slug") or f"video-{nid}")
    return f"{nid}-{slug}"


def record_path(out_dir: Path, row: Mapping[str, Any]) -> Path:
    return Path(out_dir) / _STILL_FOLDER / f"{record_stem(row)}.json"


def _identity(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "nid": as_int(row.get("nid")),
        "slug": row.get("slug"),
        "title": row.get("title"),
        "publishedDate": row.get("publishedDate"),
        "createdEpoch": as_int(row.get("createdEpoch")),
        "publicUrl": row.get("publicUrl"),
        "cmsUrl": row.get("cmsUrl"),
        "provider": row.get("provider"),
        "unsupportedReason": row.get("unsupportedReason"),
        "durationSeconds": None,
        "categories": list(row.get("categories") or []),
        "genres": list(row.get("genres") or []),
        "tags": list(row.get("tags") or []),
        "countries": list(row.get("countries") or []),
        "credits": list(row.get("credits") or []),
        "videoUrl": row.get("videoUrl"),
    }


def build_still_record(
    row: Mapping[str, Any], *, still: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge row identity around the package's neutral still evidence payload."""
    evidence = build_still_evidence(
        still=still, schema_version=STILL_SCHEMA,
        evidence_status=STILL_EVIDENCE_STATUS, limits=STILL_LIMITS,
        coverage_note=STILL_COVERAGE_NOTE, method=STILL_METHOD,
        is_source_video_frame=False, generated_at=generated_at)
    return {
        "schemaVersion": STILL_SCHEMA,
        **_identity(row),
        "poster": {
            "url": row.get("posterUrl"),
            "width": as_int(row.get("posterWidth")),
            "height": as_int(row.get("posterHeight")),
        },
        "still": evidence["still"],
        "acquisition": evidence["acquisition"],
        "coverage": evidence["coverage"],
        "evidenceStatus": evidence["evidenceStatus"],
        "rights": {
            "basis": RIGHTS_BASIS,
            "status": RIGHTS_STATUS,
            "note": "published poster still measured and deleted; not "
                    "redistributed",
        },
        "limits": evidence["limits"],
        "generatedAt": evidence["generatedAt"],
    }


def collect_still_one(
    row: Mapping[str, Any], out_dir: Path, *,
    max_bytes: int = STILL_MAX_BYTES, download_timeout: float = 60.0,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Download -> probe -> decode -> measure one poster; retain no image."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("still image byte cap must be positive")
    if not finite_float(download_timeout) or download_timeout <= 0:
        raise ValueError("still image timeout must be positive")
    url = policy_image_url(row.get("posterUrl"))
    target_path = record_path(Path(out_dir), row)
    with tempfile.TemporaryDirectory(prefix=_SCRATCH_PREFIX) as directory:
        target = image_target(Path(directory), url)
        try:
            download_http(
                url, target, allowed_hosts=IMAGE_HOSTS, max_bytes=max_bytes,
                timeout=download_timeout, accept="image/*", label="poster still",
                allow_query=POSTER_ALLOW_QUERY)
            image_bytes = target.stat().st_size
            digest = sha256_file(target)
            measured = measure_still(target, ffmpeg=ffmpeg, ffprobe=ffprobe)
        finally:
            # Guarantee: even a failed decode leaves no image bytes anywhere.
            target.unlink(missing_ok=True)
    record = build_still_record(row, still={
        "imageUrl": url,
        "imageSha256": digest,
        "imageFormat": still_image_format(url, measured.pop("imageCodec", None)),
        "imageBytes": image_bytes,
        **measured,
    })
    write_json_atomic(target_path, record)
    return record


# ---------------------------------------------------------------------------
# stills lane
# ---------------------------------------------------------------------------


def _skip_row(row: Any, reason: str) -> dict[str, Any]:
    return {
        "nid": row.get("nid") if isinstance(row, dict) else None,
        "slug": row.get("slug") if isinstance(row, dict) else None,
        "reason": reason,
    }


def _still_detail(record: Mapping[str, Any]) -> str:
    still = record.get("still") or {}
    metrics = still.get("metrics") or {}
    return (f"{still.get('imageWidth')}x{still.get('imageHeight')} "
            f"luma={metrics.get('meanDisplayLumaProxy')} "
            f"hue={metrics.get('dominantHueFamily')} "
            f"bytes={still.get('imageBytes')}")


def _still_summary_row(
    record: Mapping[str, Any], path: Path | None = None,
) -> dict[str, Any]:
    still = record.get("still") or {}
    metrics = still.get("metrics") or {}
    poster = record.get("poster") or {}
    return {
        "nid": as_int(record.get("nid")),
        "slug": record.get("slug"),
        "title": record.get("title"),
        "provider": record.get("provider"),
        "unsupportedReason": record.get("unsupportedReason"),
        "posterUrl": poster.get("url"),
        "imageSha256": still.get("imageSha256"),
        "imageFormat": still.get("imageFormat"),
        "imageBytes": still.get("imageBytes"),
        "imageWidth": still.get("imageWidth"),
        "imageHeight": still.get("imageHeight"),
        "meanDisplayLumaProxy": metrics.get("meanDisplayLumaProxy"),
        "meanSaturationProxy": metrics.get("meanSaturationProxy"),
        "dominantHueFamily": metrics.get("dominantHueFamily"),
        "edgeDensityProxy": metrics.get("edgeDensityProxy"),
        "recordPath": (path.as_posix() if path is not None else
                       f"{_STILL_FOLDER}/{record_stem(record)}.json"),
    }


def _load_retained(out_dir: Path) -> list[dict[str, Any]]:
    retained: list[dict[str, Any]] = []
    directory = out_dir / _STILL_FOLDER
    if not directory.is_dir():
        return retained
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict) and payload.get("schemaVersion") == STILL_SCHEMA:
            retained.append(_still_summary_row(payload, path.relative_to(out_dir)))
    return retained


def _error_text(out_dir: Path) -> Callable[[Exception], str]:
    scratch = re.compile(
        rf"/[^\s:'\"]*{re.escape(_SCRATCH_PREFIX)}[^\s:'\"]*")

    def render(error: Exception) -> str:
        return scratch.sub("[scratch]",
                           safe_error(error, redact=(str(out_dir),)))
    return render


def run_stills(
    catalog_path: Path | None, *, out_dir: Path, limit: int = 0,
    resume: bool = True, jobs: int = 1,
    delay_seconds: float = DEFAULT_STILL_DELAY,
    max_image_bytes: int = STILL_MAX_BYTES, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe", log: Callable[[str], None] = print,
) -> int:
    """Measure one published poster per catalogue row.

    ``limit=0`` means *all remaining* rows and terminates cleanly once every
    row is already measured (or has no usable poster). ``--resume`` only reads
    existing records: their bytes and mtimes are left untouched.
    """
    if type(limit) is not int or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    if type(jobs) is not int or not 1 <= jobs <= MAX_JOBS:
        raise ValueError(f"jobs must be between 1 and {MAX_JOBS}")
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("delay_seconds must be a non-negative number")
    catalog_file = Path(catalog_path) if catalog_path is not None else (
        Path(out_dir) / _CATALOG_NAME)
    if not catalog_file.is_file():
        raise ValueError("a catalog file is required for the stills lane")
    catalog_sha = sha256_file(catalog_file)
    rows = _load_catalog(catalog_file)["videos"]
    out_dir = Path(out_dir)
    (out_dir / _STILL_FOLDER).mkdir(parents=True, exist_ok=True)

    pending: list[dict[str, Any]] = []
    initial_skips: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("posterUrl"):
            initial_skips.append(_skip_row(row, "no-usable-poster"))
            continue
        try:
            existing = record_path(out_dir, row)
        except ValueError as error:
            initial_skips.append(_skip_row(row, f"unsafe-slug: {error}"))
            continue
        if resume and _resume_matches(existing, row.get("nid"), field="nid"):
            initial_skips.append(_skip_row(row, "resume-existing-record"))
            continue
        pending.append(row)
        if limit and len(pending) >= limit:
            break

    retained = _load_retained(out_dir) if resume else []
    index_path = out_dir / _INDEX_NAME
    details: dict[str, str] = {}

    def run_one(row: dict[str, Any]) -> dict[str, Any]:
        record = collect_still_one(
            row, out_dir, max_bytes=max_image_bytes,
            ffmpeg=ffmpeg, ffprobe=ffprobe)
        details[str(row.get("slug"))] = _still_detail(record)
        return record

    def build_index_for(
        records: list[dict[str, Any]], skips: list[dict[str, Any]],
        failures: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return build_index(
            schema_version=STILLS_INDEX_SCHEMA,
            records=[*retained, *records], skips=skips, failures=failures,
            generated_at=utc_now(),
            extra={"catalogSha256": catalog_sha, "limit": limit,
                   "resume": resume})

    def report(position: int, total: int, status: str, label: str,
               text: str) -> None:
        print(f"[{position}/{len(pending) or total}] {status} {label} "
              f"{text or details.pop(label, '')}", flush=True)

    outcome = run_batch(
        pending, run_one=run_one, index_path=index_path,
        build_index=build_index_for,
        summary_row=lambda record: _still_summary_row(record, None),
        skip_row=_skip_row, describe=lambda row: str(row.get("slug")),
        initial_skips=initial_skips, error_text=_error_text(out_dir),
        progress=report, jobs=jobs, delay_seconds=delay_seconds)
    log(f"still-measured={len(retained) + outcome.measured} "
        f"skipped={outcome.skipped} failed={outcome.failed} "
        f"attempted={outcome.attempted} "
        f"elapsed={outcome.elapsed_seconds:.1f}s index={index_path}")
    log("all downloaded poster images were deleted; only hashes and numbers remain")
    return 1 if outcome.attempted and not (retained or outcome.measured) else 0


# ---------------------------------------------------------------------------
# report: read-only, evidence-bound aggregation
# ---------------------------------------------------------------------------

_NULL_CELL = "—"


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
                "reason": f"unexpected schemaVersion "
                          f"{payload.get('schemaVersion')!r}"})
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


def _record_relative(record: Mapping[str, Any]) -> str:
    """Stable record path even for a schema-valid but identity-less record."""
    try:
        return f"{_STILL_FOLDER}/{record_stem(record)}.json"
    except ValueError:
        nid = as_int(record.get("nid"))
        return f"{_STILL_FOLDER}/nid-{nid if nid is not None else 'unknown'}.json"


def _still_row(record: Mapping[str, Any], path: Path | None = None) -> dict[str, Any]:
    still = record.get("still") if isinstance(record.get("still"), dict) else {}
    metrics = still.get("metrics") if isinstance(still.get("metrics"), dict) else {}
    poster = record.get("poster") if isinstance(record.get("poster"), dict) else {}
    return {
        "nid": as_int(record.get("nid")),
        "slug": record.get("slug"),
        "title": record.get("title"),
        "publishedDate": record.get("publishedDate"),
        "provider": record.get("provider"),
        "unsupportedReason": record.get("unsupportedReason"),
        "categories": list(record.get("categories") or []),
        "genres": list(record.get("genres") or []),
        "posterUrl": poster.get("url"),
        "posterWidth": as_int(poster.get("width")),
        "posterHeight": as_int(poster.get("height")),
        "imageSha256": still.get("imageSha256"),
        "imageFormat": still.get("imageFormat"),
        "imageBytes": as_int(still.get("imageBytes")),
        "imageWidth": as_int(still.get("imageWidth")),
        "imageHeight": as_int(still.get("imageHeight")),
        "meanDisplayLuma": finite_float(metrics.get("meanDisplayLumaProxy")),
        "meanSaturation": finite_float(metrics.get("meanSaturationProxy")),
        "dominantHueFamily": as_text(metrics.get("dominantHueFamily")),
        "edgeDensity": finite_float(metrics.get("edgeDensityProxy")),
        "generatedAt": record.get("generatedAt"),
        "recordPath": (path.as_posix() if path is not None
                       else _record_relative(record)),
    }


def _still_order(row: Mapping[str, Any]) -> tuple[int, str]:
    nid = as_int(row.get("nid"))
    return (nid if nid is not None else 0, str(row.get("slug") or ""))


def _term_distributions(
    rows: Iterable[Mapping[str, Any]], field: str,
) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[float | None]] = {}
    for row in rows:
        values = row.get(field)
        if not isinstance(values, list):
            continue
        for name in values:
            text = as_text(name)
            if text is not None:
                buckets.setdefault(text, []).append(row.get("meanDisplayLuma"))
    return {
        name: {"records": len(buckets[name]),
               "meanDisplayLuma": _distribution(buckets[name])}
        for name in sorted(buckets)
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


def _list_length(index: dict[str, Any] | None, key: str) -> int:
    rows = index.get(key) if isinstance(index, dict) else None
    return len(rows) if isinstance(rows, list) else 0


def _latest_timestamp(
    records: Iterable[Mapping[str, Any]],
    catalog: dict[str, Any] | None,
    index: dict[str, Any] | None,
) -> str | None:
    stamps = [text for record in records
              for text in (as_text(record.get("generatedAt")),)
              if text is not None]
    for document, key in ((index, "generatedAt"), (catalog, "generatedAt")):
        if isinstance(document, dict):
            text = as_text(document.get(key))
            if text is not None:
                stamps.append(text)
    return max(stamps) if stamps else None


def _num(value: float | None, digits: int = 2) -> str:
    return _NULL_CELL if value is None else f"{value:.{digits}f}"


def _int(value: int | None) -> str:
    return _NULL_CELL if value is None else str(value)


def _cell(value: object) -> str:
    text = _NULL_CELL if value is None else str(value)
    if not text:
        text = _NULL_CELL
    return text.replace("|", "\\|").replace("\n", " ")


def _reproduce_commands(
    *, out_dir: Path, catalog_path: Path, top: int,
) -> list[str]:
    out, catalog = shlex.quote(str(out_dir)), shlex.quote(str(catalog_path))
    return [
        "python scripts/research_promonews.py catalog "
        f"--out {catalog}",
        "python scripts/research_promonews.py stills "
        f"--catalog {catalog} --out-dir {out} --resume",
        "python scripts/research_promonews.py report "
        f"--out-dir {out} --top {top}",
    ]


def _render_report(
    aggregate: dict[str, Any], *, out_dir: Path, catalog_path: Path, top: int,
) -> str:
    counts = aggregate["counts"]
    rows = aggregate["stills"]
    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    add("# Promonews — published-still evidence (still-only) report")
    add()
    add("This deliverable tabulates only what the committed evidence records "
        "contain: Promonews catalogue metadata and one measured, published "
        "poster still per item. It is **still-only**: it makes no motion, cut, "
        "pacing, timing, sequence, edit-rhythm, aesthetic, style, authorship, "
        "or quality claim.")
    add()

    add("## Provenance")
    add()
    add(f"- Catalog videos collected: {_int(counts['catalogCollected'])}")
    add(f"- Catalog `hits.total` reported: {_int(counts['catalogReportedTotal'])}")
    add(f"- Catalog complete (all reported hits collected): "
        f"{_cell(counts['catalogComplete'])}")
    add(f"- Still-measured records: {_int(counts['stillMeasured'])}")
    add(f"- Skipped, no usable image: {_int(counts['skippedNoImage'])}")
    add(f"- Skipped (index context): {_int(counts['skipped'])}")
    add(f"- Failed acquisitions (index context): {_int(counts['failed'])}")
    add(f"- Unreadable records: {_int(counts['unreadable'])}")
    add(f"- generatedAt: {_cell(aggregate.get('generatedAt'))}")
    catalog_providers = counts.get("catalogByProvider") or {}
    if catalog_providers:
        add("- Provider split (catalog): " + ", ".join(
            f"{_cell(provider)} x {count}"
            for provider, count in sorted(catalog_providers.items())))
    measured_providers = counts.get("measuredByProvider") or {}
    if measured_providers:
        add("- Provider split (measured stills): " + ", ".join(
            f"{_cell(provider)} x {count}"
            for provider, count in sorted(measured_providers.items())))
    skip_reasons = aggregate.get("skipReasons") or {}
    if skip_reasons:
        add("- Skip reasons: " + ", ".join(
            f"{_cell(reason)} x {count}"
            for reason, count in sorted(skip_reasons.items())))
    if top < len(rows):
        add(f"- `--top {top}` applied: the first {top} of {len(rows)} measured "
            "stills are tabulated below; `aggregate.json` holds all.")
    add()
    add("Reproduce the inputs and this report with:")
    add()
    add("```bash")
    for command in _reproduce_commands(
            out_dir=out_dir, catalog_path=catalog_path, top=top):
        add(command)
    add("```")
    add()

    add("## Measured stills")
    add()
    add(f"{len(rows)} still-measured record(s), ordered by nid then slug. "
        "Every number describes one published image, never a video frame.")
    add()
    columns = (
        "nid", "slug", "title", "provider", "categories", "genres",
        "img_w", "img_h", "img_bytes", "mean_luma", "mean_sat", "hue",
        "edge_density")
    add("| " + " | ".join(columns) + " |")
    add("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows[:top]:
        values = (
            _int(row["nid"]), row["slug"], row["title"], row["provider"],
            ", ".join(row["categories"]) or None,
            ", ".join(row["genres"]) or None,
            _int(row["imageWidth"]), _int(row["imageHeight"]),
            _int(row["imageBytes"]), _num(row["meanDisplayLuma"], 4),
            _num(row["meanSaturation"], 4), row["dominantHueFamily"],
            _num(row["edgeDensity"], 4))
        add("| " + " | ".join(_cell(value) for value in values) + " |")
    if not rows:
        add("| " + " | ".join("—" for _ in columns) + " |")
    add()

    add("## Distributions by genre and category")
    add()
    add("Each row aggregates only the measured stills that carry that genre or "
        "category. Counts describe this measured sample, not the full "
        "catalogue.")
    add()
    for label, key in (
            ("Genre", "byGenre"), ("Category", "byCategory")):
        add(f"### {label}")
        add()
        buckets = aggregate.get(key) or {}
        if not buckets:
            add(f"No still records with a {label.lower()} value.")
            add()
            continue
        add("| value | stills | luma min | luma median | luma max |")
        add("| --- | --- | --- | --- | --- |")
        for name, entry in buckets.items():
            luma = entry["meanDisplayLuma"]
            add("| " + " | ".join((
                _cell(name), _int(entry["records"]), _num(luma["min"], 4),
                _num(luma["median"], 4), _num(luma["max"], 4))) + " |")
        add()

    add("## Why there is no motion evidence")
    add()
    add("There is no video lane for Promonews, by design:")
    add()
    add("- Every catalogue video reference is a YouTube or Vimeo embed "
        "(`video/youtube` or `video/vimeo`); the site publishes no progressive "
        "MP4/HLS file.")
    add("- YouTube and Vimeo players are third-party platforms. Per repository "
        "policy they are recorded as `unsupported-youtube` / "
        "`unsupported-vimeo` and are never probed.")
    add("- No cookies, logins, player-API tricks, or DRM circumvention were "
        "used, and no embed was fetched.")
    add("- Therefore this report cannot and does not measure motion, cuts, "
        "pacing, timing, sequences, or edit rhythm. A poster still is not a "
        "video frame.")
    if catalog_providers:
        add("- Catalogue provider split: " + ", ".join(
            f"{provider} x {count}"
            for provider, count in sorted(catalog_providers.items())) + ".")
    add()

    add("## Explicit non-claims")
    add()
    for claim in (
            "A published poster still is not a video frame; single-image "
            "colour, luminance, histogram, hue, and edge-density numbers carry "
            "no motion, cut, pacing, timing, sequence, or edit-rhythm evidence.",
            "No style, aesthetic quality, mood, lighting, camera/lens, "
            "editorial intent, authorship, identity, or creative-origin "
            "inference is made from these numbers.",
            "The poster is prepared by Promonews/the CMS, not necessarily by "
            "the work's author.",
            "No duration was derived from a YouTube or Vimeo id; "
            "`durationSeconds` is recorded as null everywhere because the "
            "catalogue exposes no duration field.",
            "Public availability is not a licence: `rightsStatus` remains "
            "`review-required`, and reuse needs its own review.",
            "YouTube/Vimeo embeds were never acquired or probed.",
            "Catalogue metadata is self-reported by Promonews and is not "
            "independently verified.",
            "Downloaded poster images are never retained: only hashes and "
            "numbers remain."):
        add(f"- {claim}")
    add()
    return "\n".join(lines)


def run_report(
    out_dir: Path, *, top: int = DEFAULT_TOP,
    catalog_path: Path | None = None,
    generated_at: str | None = None,
    log: Callable[[str], None] = print,
) -> int:
    """Read collected records read-only and write ``report.md`` + ``aggregate.json``."""
    if type(top) is not int or top < 0:
        raise ValueError("top must be a non-negative integer")
    out_dir = Path(out_dir)
    requested = Path(catalog_path) if catalog_path is not None else None
    if requested is not None and not requested.is_file():
        raise ValueError("catalog file does not exist")
    default_catalog = out_dir / _CATALOG_NAME
    catalog_file = (requested if requested is not None else
                    (default_catalog if default_catalog.is_file() else None))

    records, problems = _load_records(
        out_dir / _STILL_FOLDER, STILL_SCHEMA, prefix=_STILL_FOLDER)
    catalog, catalog_problems = _load_json_context(
        catalog_file, prefix=_CATALOG_NAME)
    index, index_problems = _load_json_context(
        out_dir / _INDEX_NAME, prefix=_INDEX_NAME)
    problems.extend(catalog_problems)
    problems.extend(index_problems)
    problems.sort(key=lambda item: (item["file"], item["reason"]))

    if generated_at is None:
        generated_at = _latest_timestamp(records, catalog, index)

    rows = sorted(
        (_still_row(record, Path(_record_relative(record)))
         for record in records),
        key=_still_order)
    skip_reasons = _skip_reasons(index)
    skipped_no_image = sum(
        count for reason, count in skip_reasons.items()
        if reason == "no-usable-poster" or reason.startswith("no-"))

    catalog_counts = (catalog.get("counts")
                      if isinstance(catalog, dict)
                      and isinstance(catalog.get("counts"), dict) else {})
    catalog_collected = as_int(catalog_counts.get("collected"))
    catalog_total = as_int(catalog_counts.get("reportedTotal"))
    if catalog_collected is None and isinstance(catalog, dict) and isinstance(
            catalog.get("videos"), list):
        catalog_collected = len(catalog["videos"])
    catalog_providers = catalog_counts.get("byProvider")
    if not isinstance(catalog_providers, dict):
        catalog_providers = {}

    aggregate = {
        "schemaVersion": AGGREGATE_SCHEMA,
        "generatedAt": generated_at,
        "evidence": "still-only",
        "counts": {
            "catalogCollected": catalog_collected,
            "catalogReportedTotal": catalog_total,
            "catalogComplete": bool(catalog_counts.get("complete")),
            "stillMeasured": len(rows),
            "skipped": _list_length(index, "skips"),
            "skippedNoImage": skipped_no_image,
            "failed": _list_length(index, "failures"),
            "unreadable": len(problems),
            "catalogByProvider": dict(catalog_providers),
            "measuredByProvider": _counter(row.get("provider") for row in rows),
        },
        "skipReasons": skip_reasons,
        "distributions": {
            "meanDisplayLuma": _distribution(
                row.get("meanDisplayLuma") for row in rows),
            "meanSaturation": _distribution(
                row.get("meanSaturation") for row in rows),
            "edgeDensity": _distribution(
                row.get("edgeDensity") for row in rows),
            "imageBytes": _distribution(row.get("imageBytes") for row in rows),
        },
        "byGenre": _term_distributions(rows, "genres"),
        "byCategory": _term_distributions(rows, "categories"),
        "stills": rows,
        "limits": list(STILL_LIMITS),
        "unreadableRecords": problems,
    }

    report_path = out_dir / "report.md"
    aggregate_path = out_dir / "aggregate.json"
    write_json_atomic(aggregate_path, aggregate)
    _write_text_atomic(report_path, _render_report(
        aggregate, out_dir=out_dir,
        catalog_path=catalog_file or default_catalog, top=top))
    log(f"report: stills={len(rows)} skipped={aggregate['counts']['skipped']} "
        f"failed={aggregate['counts']['failed']} unreadable={len(problems)} "
        f"-> {report_path}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ephemeral Promonews catalogue + poster-still research "
                    "collector (no video lane)")
    sub = parser.add_subparsers(dest="command", required=True)

    catalog = sub.add_parser(
        "catalog", help="enumerate the full Promonews catalogue")
    catalog.add_argument("--out", type=Path, required=True,
                         help="path for the versioned catalog JSON")
    catalog.add_argument("--limit", type=int, default=None,
                         help="catalog size (default: all; 0 = no request)")
    catalog.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    catalog.add_argument("--delay-seconds", type=float,
                         default=DEFAULT_CATALOG_DELAY,
                         help="politeness pause (plus equal jitter) between pages")

    stills = sub.add_parser(
        "stills", help="measure one published poster still per catalog item")
    stills.add_argument("--catalog", type=Path, required=True)
    stills.add_argument("--out-dir", type=Path, required=True)
    stills.add_argument("--limit", type=int, default=0,
                        help="0 = every remaining row; N = first N pending")
    group = stills.add_mutually_exclusive_group()
    group.add_argument("--resume", dest="resume", action="store_true",
                       default=True)
    group.add_argument("--refresh", dest="resume", action="store_false")
    stills.add_argument("--jobs", type=int, default=1)
    stills.add_argument("--delay-seconds", type=float,
                        default=DEFAULT_STILL_DELAY,
                        help="politeness pause (plus equal jitter) between stills")
    stills.add_argument("--max-image-bytes", type=int, default=STILL_MAX_BYTES)
    stills.add_argument("--ffmpeg", default="ffmpeg")
    stills.add_argument("--ffprobe", default="ffprobe")

    report = sub.add_parser(
        "report", help="write report.md + aggregate.json from still records "
                       "(read-only, offline)")
    report.add_argument("--out-dir", type=Path, required=True)
    report.add_argument("--catalog", type=Path, default=None,
                        help="catalog JSON (default: <out-dir>/catalog.json)")
    report.add_argument("--top", type=int, default=DEFAULT_TOP,
                        help="table rows and per-term rows to render")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            return run_catalog(
                args.out, limit=args.limit, page_size=args.page_size,
                delay_seconds=args.delay_seconds)
        if args.command == "stills":
            return run_stills(
                args.catalog, out_dir=args.out_dir, limit=args.limit,
                resume=args.resume, jobs=args.jobs,
                delay_seconds=args.delay_seconds,
                max_image_bytes=args.max_image_bytes, ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe)
        return run_report(
            args.out_dir, catalog_path=args.catalog, top=args.top)
    except ValueError as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    sys.exit(main())
