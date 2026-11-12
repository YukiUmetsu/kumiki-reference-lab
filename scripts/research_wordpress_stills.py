"""Ephemeral, source-hashed measurement of published WordPress poster stills.

Two sites are covered by one config-driven adapter:

``directorslibrary``
    Directors' Library, a WordPress ``video`` post type. The public WP REST API
    exposes the full catalogue (5412 items) plus a self-hosted ``og_image``.
``stash``
    STASH, a WordPress magazine (``posts``). The feed mixes video posts with
    galleries; the public WP REST API exposes 5399 posts plus an ``og_image``.

Every video on both sites is a third-party Vimeo/YouTube embed. Vimeo's player
and ``/config`` endpoints answer 401/403 to scripted clients, and neither site
publishes a progressive MP4/HLS file. Per repository policy Vimeo is recorded
as unsupported and never attempted. For ``directorslibrary`` the embed URL is
read from the rendered article HTML and YouTube entries are measured through the
engine's cookie-free yt-dlp provider (the ``collect`` lane); ``stash`` is
Vimeo-only, so its ``collect`` run refuses every row explicitly. The honest
still deliverable is a full catalogue plus one measured *published poster still*
per item, with explicit still-only evidence limits.

This is a *site adapter*: allowlisting, bounded retrieval, still/video
measurement, evidence assembly, atomic writes, resume checks, index assembly,
and the pooled batch loop come from :mod:`kumiki_reference_lab.acquisition`. The
adapter supplies the WordPress endpoints, the slim catalogue projection, the
host allowlists, embed discovery, schema/evidence/limits/rights strings, and the
CLI.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import shlex
import statistics
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition import (  # noqa: E402
    DEFAULT_YOUTUBE_HOSTS, MAX_WINDOWS, MAX_WINDOW_SECONDS, STILL_MAX_BYTES,
    STILL_METHOD, USER_AGENT, YOUTUBE, YtDlpError, YtDlpRefusedError,
    allowlisted_image_url, allowlisted_url, allowlisted_youtube_url, as_int,
    as_text, build_index, build_still_evidence, build_video_evidence,
    download_http, download_media, fetch_text, finite_float, image_target,
    measure_still, measure_windows, resume_matches as _resume_matches,
    run_batch, safe_error, safe_slug, source_metadata, still_image_format,
    utc_now, write_json_atomic,
)
from kumiki_reference_lab.analyzers.media.inspect import sha256_file  # noqa: E402

# ---------------------------------------------------------------------------
# site configuration
# ---------------------------------------------------------------------------

SITES: dict[str, dict[str, Any]] = {
    "directorslibrary": {
        "key": "directorslibrary",
        "label": "Directors' Library",
        "baseUrl": "https://directorslibrary.com",
        "host": "directorslibrary.com",
        "postType": "video",
        "taxonomies": (
            "categories", "tags", "location", "aspect_ratio", "agency",
            "record_label", "festival", "award", "format",
        ),
        "schemaPrefix": "directorslibrary",
        "hasExcerpt": False,
        "catalogFields": (
            "id", "slug", "date", "link", "title", "featured_media",
            "categories", "tags", "location", "aspect_ratio", "agency",
            "record_label", "festival", "award", "format", "class_list",
            "yoast_head_json",
        ),
        "embedProviders": ("Vimeo", "YouTube"),
        "providerNote": (
            "Every item is a third-party embed (player.vimeo.com/video/<id> or "
            "www.youtube.com/embed/<id>); the site publishes no progressive "
            "MP4/HLS file. The embed URL exists only in the rendered article "
            "HTML: `collect` reads it, measures the YouTube rendition through a "
            "cookie-free yt-dlp, records Vimeo-only rows as `unsupported-vimeo`, "
            "and never uses cookies, logins, or DRM workarounds."),
        "caveat": (
            "The catalogue is the site's WordPress video post type. No ACF "
            "director/duration/brand fields are exposed by the REST API, so "
            "those fields stay null rather than being invented."),
    },
    "stash": {
        "key": "stash",
        "label": "STASH",
        "baseUrl": "https://www.stashmedia.tv",
        "host": "www.stashmedia.tv",
        "postType": "posts",
        "taxonomies": ("categories",),
        "schemaPrefix": "stash",
        "hasExcerpt": True,
        "catalogFields": (
            "id", "date", "slug", "link", "title", "excerpt", "featured_media",
            "categories", "author", "yoast_head_json",
        ),
        "embedProviders": ("Vimeo", "YouTube"),
        "providerNote": (
            "Video posts embed third-party players (player.vimeo.com/video/<id> "
            "or www.youtube.com/embed/<id>); no progressive MP4/HLS file is "
            "published, so video is recorded as unsupported and never attempted."),
        "caveat": (
            "STASH is a magazine feed: many posts are image galleries and not "
            "videos at all. A per-row `provider` value is only a downloadability "
            "label; it does not claim every post contains a video, and this "
            "adapter makes no video-coverage claim."),
    },
}

RIGHTS_BASIS = "user-declared-research-use"
RIGHTS_STATUS = "review-required"
STILL_EVIDENCE_STATUS = "single-published-still-metrics-not-video-measurement"
STILL_COVERAGE_NOTE = (
    "single published poster still from the site's own og:image, decoded once "
    "at 160x90 RGB; not a decoded video frame, no motion/time evidence")
STILL_LIMITS = [
    "A single published poster still is not a video frame: no motion, cut, "
    "pacing, timing, sequence, or edit-rhythm evidence is claimed.",
    "Colour, luminance, histogram, hue, and edge-density numbers describe one "
    "image only; they are not aesthetic, style, quality, authoring, or "
    "creative-intent judgements.",
    "The poster is prepared by the site/CMS, not necessarily by the work's "
    "author, and a poster may be a gallery image rather than a video frame.",
    "The downloaded image was deleted immediately after measurement; no image "
    "bytes are retained.",
    "Third-party Vimeo/YouTube embeds are not acquired: no cookies, logins, "
    "tokens, player-API tricks, or DRM circumvention were used.",
    "Public availability is not a licence; rightsStatus remains review-required.",
    "Catalogue metadata is self-reported by the site and is not independently "
    "verified.",
]

PORTRAIT_WIDTH = 160
PORTRAIT_HEIGHT = 90
DEFAULT_CATALOG_PAGE_SIZE = 100
DEFAULT_CATALOG_DELAY = 1.0
DEFAULT_STILL_DELAY = 0.8
DEFAULT_TOP = 50
DEFAULT_CATALOG_LIMIT: int | None = None
MAX_JOBS = 2
_MAX_PAGES = 500
_MAX_TERM_PAGES = 50
_MAX_RESPONSE_BYTES = 16_000_000

_STILL_FOLDER = "stills"
_INDEX_NAME = "stills-index.json"
_CATALOG_NAME = "catalog.json"
_VIDEO_FOLDER = "videos"
_VIDEO_INDEX_NAME = "index.json"
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# video-lane constants (Directors' Library YouTube rendition only)
# ---------------------------------------------------------------------------

DEFAULT_VIDEO_DELAY = 1.4
DEFAULT_COLLECT_LIMIT = 250
DEFAULT_MAX_DURATION_SECONDS = 600.0
DEFAULT_MAX_FILE_BYTES = 250 * 1024 * 1024
DEFAULT_WINDOW_COUNT = 4
DEFAULT_WINDOW_SECONDS = 10
ARTICLE_MAX_BYTES = 4_000_000
VIDEO_DOWNLOAD_TIMEOUT = 360.0

VIDEO_EVIDENCE_STATUS = "sampled-original-source-pts-metrics-not-expert-reviewed"
RENDITION_NOTE = (
    "platform-encoded YouTube rendition measured, not the work's delivered "
    "master")
DEFAULT_RIGHTS_NOTE = (
    "operator attests public-page research use; the public YouTube rendition is "
    "downloaded once by a cookie-free yt-dlp, measured numerically, and deleted "
    "without redistribution")
VIDEO_LIMITS = [
    "Only sampled source-PTS windows were measured; this is not a full-film "
    "review.",
    "The source is a platform-encoded YouTube rendition, not the work's "
    "delivered master; every number describes that rendition only.",
    "The embed URL was read from the public article HTML supplied by the site; "
    "no Vimeo player, `/config` endpoint, cookie, login, browser profile, "
    "netrc, remote component, or DRM/PO-token/nsig workaround was used.",
    "A provider refusal (403, login-only, unsupported client) is recorded and "
    "never retried.",
    "The downloaded file was deleted immediately after measurement; no media, "
    "frames, thumbnails, or audio are retained.",
    "Public availability is not a licence; rightsStatus remains "
    "review-required.",
    "Catalogue metadata is self-reported by the site and is not independently "
    "verified.",
]



# ---------------------------------------------------------------------------
# configuration helpers and schema names
# ---------------------------------------------------------------------------


class PageOverflow(Exception):
    """Terminal WordPress ``400 rest_post_invalid_page_number`` response."""


def site_config(site_key: str) -> dict[str, Any]:
    """Return one validated site configuration or raise."""
    site = SITES.get(site_key)
    if site is None:
        raise ValueError(
            f"unknown site {site_key!r}; expected one of {sorted(SITES)}")
    return site


def schema_name(site: Mapping[str, Any], kind: str) -> str:
    """Versioned schema name for one site and artefact kind."""
    return f"kumiki.{site['schemaPrefix']}-{kind}.v1"


# ---------------------------------------------------------------------------
# small coercion helpers
# ---------------------------------------------------------------------------


def _rendered(value: object) -> str:
    """Read a WordPress ``{rendered: ...}`` field and HTML-unescape it."""
    if isinstance(value, dict):
        value = value.get("rendered")
    text = as_text(value)
    if text is None:
        return ""
    return html.unescape(text).strip()


def _excerpt_text(value: object, *, limit: int = 100) -> str | None:
    """Strip tags from a rendered excerpt, unescape entities, and bound it."""
    text = _rendered(value)
    if not text:
        return None
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if not text:
        return None
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _unique_ints(values: object) -> list[int]:
    if not isinstance(values, (list, tuple)):
        return []
    result: list[int] = []
    for value in values:
        number = as_int(value)
        if number is not None and number not in result:
            result.append(number)
    return result


def _counter(values: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        text = as_text(value) or "unknown"
        counts[text] = counts.get(text, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _distribution(values: Iterable[float | None], *, digits: int = 6) -> dict[str, Any]:
    numbers = [value for value in values if value is not None]
    if not numbers:
        return {"n": 0, "min": None, "median": None, "max": None}
    return {
        "n": len(numbers),
        "min": round(min(numbers), digits),
        "median": round(statistics.median(numbers), digits),
        "max": round(max(numbers), digits),
    }


# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------


def api_root(site: Mapping[str, Any]) -> str:
    return f"{site['baseUrl']}/wp-json/wp/v2"


def catalog_url(site: Mapping[str, Any], *, page: int, page_size: int) -> str:
    query = urlencode({
        "per_page": page_size,
        "page": page,
        "orderby": "date",
        "order": "desc",
        "_fields": ",".join(site["catalogFields"]),
    })
    return f"{api_root(site)}/{site['postType']}?{query}"


def taxonomy_url(
    site: Mapping[str, Any], taxonomy: str, *, page: int, page_size: int = 100,
) -> str:
    query = urlencode({
        "per_page": page_size,
        "page": page,
        "_fields": "id,name,slug",
    })
    return f"{api_root(site)}/{taxonomy}?{query}"


# ---------------------------------------------------------------------------
# bounded JSON retrieval (WP REST API)
# ---------------------------------------------------------------------------


def _header_int(headers: Mapping[str, Any], name: str) -> int | None:
    try:
        value = headers.get(name)
    except AttributeError:
        return None
    if value is None:
        # Case-insensitive fallback for real HTTPMessage objects.
        for key, candidate in getattr(headers, "items", lambda: [])():
            if str(key).lower() == name.lower():
                value = candidate
                break
    return as_int(value)


def _http_error_body(error: HTTPError) -> bytes:
    try:
        return error.read(_MAX_RESPONSE_BYTES)
    except (OSError, ValueError):
        return b""


def _error_code(raw: bytes) -> str | None:
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, UnicodeDecodeError):
        return None
    if isinstance(payload, dict):
        code = payload.get("code")
        return code if isinstance(code, str) else None
    return None


def _get_json(
    url: str, *, allowed_hosts: Iterable[str], timeout: float = 45.0,
    retries: int = 3, sleep: Callable[[float], None] = time.sleep,
) -> tuple[Any, dict[str, str]]:
    """GET one allowlisted JSON page and return ``(payload, lower-case headers)``.

    A ``400 rest_post_invalid_page_number`` is terminal: it is raised as
    :class:`PageOverflow` immediately and never retried. Other 4xx errors are
    contract errors; only 429/5xx and transport errors are retried.
    """
    hosts = tuple(allowed_hosts)
    # The public WP REST projection itself is query-based (`per_page`, `page`,
    # `_fields`); these are benign projection parameters, not credentials.
    allowlisted_url(url, allowed_hosts=hosts, label="WP REST API URL",
                    allow_query=True)
    last_error: Exception | None = None
    for attempt in range(retries):
        request = Request(url, headers={
            "Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=timeout) as response:
                allowlisted_url(response.geturl(), allowed_hosts=hosts,
                                label="WP REST API redirect", allow_query=True)
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
                headers = {
                    str(key).lower(): str(value)
                    for key, value in response.headers.items()
                }
        except HTTPError as error:
            if error.code == 400 and _error_code(
                    _http_error_body(error)) == "rest_post_invalid_page_number":
                raise PageOverflow(
                    "WordPress reported rest_post_invalid_page_number") from None
            if error.code != 429 and error.code < 500:
                raise ValueError(
                    f"WP REST API rejected the request (HTTP {error.code})"
                ) from None
            last_error = error
        except (URLError, TimeoutError, OSError) as error:
            last_error = error
        else:
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise ValueError("WP REST API response exceeded the size limit")
            try:
                payload = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise ValueError("WP REST API response was not valid JSON") from None
            return payload, headers
        if attempt + 1 < retries:
            sleep(2 ** attempt)
    raise RuntimeError(
        "WP REST API request failed after bounded retries") from last_error


# ---------------------------------------------------------------------------
# term-name resolution
# ---------------------------------------------------------------------------


def resolve_terms(
    site: Mapping[str, Any],
    taxonomies: Iterable[str], *,
    fetch: Callable[[str], tuple[Any, Mapping[str, Any]]],
    sleep: Callable[[float], None] = time.sleep,
    delay_seconds: float = 0.0,
    log: Callable[[str], None] = print,
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, str]]:
    """Resolve term ids to ``{name, slug}`` with one request per taxonomy.

    Follows ``X-WP-TotalPages`` and stops on an empty page or the terminal
    page-overflow response. A taxonomy that cannot be read is recorded as an
    explicit error; its ids stay in the rows with a ``None`` name.
    """
    cache: dict[str, dict[str, dict[str, Any]]] = {}
    errors: dict[str, str] = {}
    for taxonomy in taxonomies:
        terms: dict[str, dict[str, Any]] = {}
        total_pages: int | None = None
        page = 1
        while page <= _MAX_TERM_PAGES:
            url = taxonomy_url(site, taxonomy, page=page)
            try:
                payload, headers = fetch(url)
            except PageOverflow:
                break
            except (ValueError, RuntimeError) as error:
                errors[taxonomy] = safe_error(error)
                break
            if not isinstance(payload, list):
                errors[taxonomy] = "taxonomy response was not a JSON array"
                break
            for item in payload:
                if not isinstance(item, dict):
                    continue
                term_id = as_int(item.get("id"))
                if term_id is None:
                    continue
                terms[str(term_id)] = {
                    "name": as_text(item.get("name")),
                    "slug": as_text(item.get("slug")),
                }
            total_pages = _header_int(headers, "X-WP-TotalPages") or total_pages
            if not payload:
                break
            if total_pages is not None and page >= total_pages:
                break
            page += 1
            if delay_seconds:
                sleep(float(delay_seconds) + random.uniform(0, float(delay_seconds)))
        cache[taxonomy] = terms
        log(f"terms {taxonomy}: {len(terms)} resolved")
    return cache, errors


# ---------------------------------------------------------------------------
# catalogue projection
# ---------------------------------------------------------------------------


def poster_from_head(yoast: object) -> dict[str, Any] | None:
    """Read ``og_image[0]`` as ``{url, width, height}``; nothing else."""
    if not isinstance(yoast, dict):
        return None
    images = yoast.get("og_image")
    if not isinstance(images, list) or not images:
        return None
    first = images[0]
    if not isinstance(first, dict):
        return None
    url = as_text(first.get("url"))
    if not url:
        return None
    return {
        "url": url,
        "width": as_int(first.get("width")),
        "height": as_int(first.get("height")),
    }


def policy_image_url(site: Mapping[str, Any], url: object) -> str:
    """Allowlist exactly the site's own host, with no query string.

    Some WordPress installs emit ``og:image`` as ``http://`` even though the
    site itself is HTTPS. For the *same* allowlisted host the scheme is
    upgraded to HTTPS before policy validation; nothing else is rewritten.
    Any other host, credentials, port, fragment, or query is still refused.

    The returned value is the engine's ASCII URI form of the URL: WordPress
    uploads keep raw UTF-8 characters in filenames (``André``, ``Rio 40°``), and
    the request line cannot carry them. Recording this return value is what
    keeps a record's ``imageUrl`` exactly the URL that was fetched, so a reader
    can reproduce the request.
    """
    text = as_text(url)
    if text is None:
        raise ValueError("still image URL is absent")
    try:
        parts = urlsplit(text)
    except ValueError:
        raise ValueError("still image URL is not parsable") from None
    if (parts.scheme == "http" and not parts.username and not parts.password
            and (parts.hostname or "").lower() == site["host"]):
        text = urlunsplit(("https", parts.netloc, parts.path, parts.query,
                           parts.fragment))
    return allowlisted_image_url(
        text, allowed_hosts=(site["host"],), allow_query=False)


def infer_provider(site: Mapping[str, Any], yoast: object) -> str | None:
    """Per-row downloadability label, never a claim that a video exists.

    The ``video`` post type is itself the site's video channel. For the STASH
    magazine feed, a Yoast ``og:video``/``og_type=video*`` is the only per-row
    hint the REST projection exposes; otherwise the value is ``None``.
    """
    if site["postType"] == "video":
        return "unsupported-embed"
    if isinstance(yoast, dict):
        og_type = (as_text(yoast.get("og_type")) or "").lower()
        if yoast.get("og_video") or og_type.startswith("video"):
            return "unsupported-embed"
    return None


def _term_projection(
    site: Mapping[str, Any], raw: Mapping[str, Any],
    term_cache: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> tuple[dict[str, list[int]], dict[str, list[str | None]]]:
    term_ids: dict[str, list[int]] = {}
    term_names: dict[str, list[str | None]] = {}
    for taxonomy in site["taxonomies"]:
        ids = _unique_ints(raw.get(taxonomy))
        if not ids:
            continue
        names: list[str | None] = []
        for term_id in ids:
            entry = (term_cache.get(taxonomy) or {}).get(str(term_id)) or {}
            names.append(as_text(entry.get("name")))
        term_ids[taxonomy] = ids
        term_names[taxonomy] = names
    return term_ids, term_names


def normalize_row(
    site: Mapping[str, Any], raw: Mapping[str, Any],
    term_cache: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Project one raw WP REST object into the slim, deterministic catalog row."""
    if not isinstance(raw, dict):
        raise ValueError("catalog item must be a JSON object")
    post_id = as_int(raw.get("id"))
    if post_id is None:
        raise ValueError("catalog item has no integer id")
    slug = as_text(raw.get("slug")) or f"{site['postType']}-{post_id}"
    yoast = raw.get("yoast_head_json")
    provider = infer_provider(site, yoast)
    poster = poster_from_head(yoast)
    poster_status = "missing-og-image"
    if poster is not None:
        try:
            poster["url"] = policy_image_url(site, poster["url"])
            poster_status = "ok"
        except ValueError:
            poster = None
            poster_status = "poster-host-not-allowlisted"
    term_ids, term_names = _term_projection(site, raw, term_cache)
    row: dict[str, Any] = {
        "id": post_id,
        "slug": slug,
        "title": _rendered(raw.get("title")),
        "publicationDate": as_text(raw.get("date")),
        "articleUrl": as_text(raw.get("link")),
        "featuredMediaId": as_int(raw.get("featured_media")),
        "posterUrl": poster["url"] if poster else None,
        "posterWidth": poster["width"] if poster else None,
        "posterHeight": poster["height"] if poster else None,
        "termIds": term_ids,
        "terms": term_names,
        "provider": provider,
        "videoDownloadable": False,
        "videoDownloadableReason": (
            "third-party-embed" if provider else "no-video-file"),
    }
    if poster_status != "ok":
        row["posterStatus"] = poster_status
    if site["hasExcerpt"]:
        row["excerptText"] = _excerpt_text(raw.get("excerpt"))
    return row


def catalog_order(row: Mapping[str, Any]) -> tuple[str, int]:
    post_id = as_int(row.get("id"))
    return (as_text(row.get("publicationDate")) or "",
            post_id if post_id is not None else -1)


def _fetch_raw_pages(
    site: Mapping[str, Any], *, limit: int | None, page_size: int,
    fetch: Callable[[str], tuple[Any, Mapping[str, Any]]],
    sleep: Callable[[float], None], delay_seconds: float,
    log: Callable[[str], None],
) -> tuple[list[Any], int | None, int, bool]:
    raw_items: list[Any] = []
    reported_total: int | None = None
    total_pages: int | None = None
    pages = 0
    overflow = False
    page = 1
    while page <= _MAX_PAGES:
        try:
            payload, headers = fetch(catalog_url(
                site, page=page, page_size=page_size))
        except PageOverflow:
            overflow = True
            log(f"catalog page {page}: terminal invalid-page response; stopping")
            break
        if not isinstance(payload, list):
            raise ValueError("catalog response was not a JSON array")
        reported_total = _header_int(headers, "X-WP-Total") or reported_total
        total_pages = _header_int(headers, "X-WP-TotalPages") or total_pages
        if not payload:
            break
        remaining = (limit - len(raw_items)) if limit is not None else None
        if remaining is not None and remaining < len(payload):
            raw_items.extend(payload[:remaining])
        else:
            raw_items.extend(payload)
        pages += 1
        log(f"catalog page {page}: {len(payload)} items "
            f"({len(raw_items)} collected)")
        if limit is not None and len(raw_items) >= limit:
            break
        if total_pages is not None and page >= total_pages:
            break
        if len(payload) < page_size:
            break
        page += 1
        if delay_seconds:
            sleep(float(delay_seconds) + random.uniform(0, float(delay_seconds)))
    if pages >= _MAX_PAGES:
        raise ValueError("catalog pagination exceeded the safety page budget")
    return raw_items, reported_total, pages, overflow


def fetch_catalog(
    site_key: str, *, limit: int | None = DEFAULT_CATALOG_LIMIT,
    page_size: int = DEFAULT_CATALOG_PAGE_SIZE,
    delay_seconds: float = DEFAULT_CATALOG_DELAY,
    fetch: Callable[[str], tuple[Any, Mapping[str, Any]]] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Page the public WP REST catalogue and resolve the term names it uses.

    ``limit=None`` means every page. ``limit=0`` is an offline no-op. The
    terminal ``rest_post_invalid_page_number`` 400 is a normal end-of-catalogue
    signal, not an error to retry.
    """
    site = site_config(site_key)
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("catalog limit must be a non-negative integer or None")
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ValueError("catalog page size must be between 1 and 100")
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("catalog delay must be a non-negative number")
    if limit == 0:
        return [], {
            "reportedTotal": 0, "pagesFetched": 0, "overflow": False,
            "termCache": {}, "termErrors": {},
        }
    if fetch is None:
        fetch = lambda url: _get_json(  # noqa: E731
            url, allowed_hosts=(site["host"],), sleep=sleep)

    raw_items, reported_total, pages, overflow = _fetch_raw_pages(
        site, limit=limit, page_size=page_size, fetch=fetch, sleep=sleep,
        delay_seconds=delay_seconds, log=log)

    used_taxonomies = [
        taxonomy for taxonomy in site["taxonomies"]
        if any(taxonomy in item and _unique_ints(item.get(taxonomy))
               for item in raw_items if isinstance(item, dict))
    ]
    term_cache, term_errors = resolve_terms(
        site, used_taxonomies, fetch=fetch, sleep=sleep,
        delay_seconds=delay_seconds, log=log)

    rows = [normalize_row(site, item, term_cache)
            for item in raw_items if isinstance(item, dict)]
    rows = sorted(rows, key=catalog_order, reverse=True)
    if limit is not None:
        rows = rows[:limit]
    return rows, {
        "reportedTotal": reported_total,
        "pagesFetched": pages,
        "overflow": overflow,
        "termCache": term_cache,
        "termErrors": term_errors,
    }


def build_catalog(
    site_key: str, rows: Iterable[dict[str, Any]], *, meta: Mapping[str, Any],
    generated_at: str | None = None,
    page_size: int = DEFAULT_CATALOG_PAGE_SIZE,
    limit: int | None = DEFAULT_CATALOG_LIMIT,
) -> dict[str, Any]:
    """Assemble the slim catalogue document with its counts and term cache."""
    site = site_config(site_key)
    items = sorted(rows, key=catalog_order, reverse=True)
    term_cache = dict(meta.get("termCache") or {})
    counts = {
        "catalogItems": len(items),
        "reportedTotal": meta.get("reportedTotal"),
        "pagesFetched": meta.get("pagesFetched", 0),
        "reachedPageOverflow": bool(meta.get("overflow")),
        "withPoster": sum(1 for row in items if row.get("posterUrl")),
        "withoutPoster": sum(1 for row in items if not row.get("posterUrl")),
        "providerCounts": _counter(row.get("provider") for row in items),
        "termCounts": {
            taxonomy: len(term_cache.get(taxonomy) or {})
            for taxonomy in site["taxonomies"]
            if taxonomy in term_cache
        },
        "termResolutionErrors": dict(meta.get("termErrors") or {}),
    }
    return {
        "schemaVersion": schema_name(site, "catalog"),
        "generatedAt": generated_at or utc_now(),
        "site": site["key"],
        "sourceHost": site["host"],
        "postType": site["postType"],
        "endpoints": {
            "catalog": catalog_url(site, page=1, page_size=page_size),
            "taxonomies": {
                taxonomy: taxonomy_url(site, taxonomy, page=1)
                for taxonomy in site["taxonomies"]
            },
        },
        "query": {
            "pageSize": page_size,
            "limit": limit,
            "orderby": "date",
            "order": "desc",
            "fields": list(site["catalogFields"]),
        },
        "provider": "unsupported-embed",
        "providerNote": site["providerNote"],
        "caveat": site["caveat"],
        "counts": counts,
        "termCache": term_cache,
        "items": items,
    }


def _load_catalog(path: Path, site: Mapping[str, Any]) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or catalog.get(
            "schemaVersion") != schema_name(site, "catalog"):
        raise ValueError("unsupported catalog schema")
    if not isinstance(catalog.get("items"), list):
        raise ValueError("catalog has no item list")
    return catalog


# ---------------------------------------------------------------------------
# record identity and builders
# ---------------------------------------------------------------------------


def record_stem(row: Mapping[str, Any]) -> str:
    post_id = as_int(row.get("id"))
    if post_id is None:
        post_id = as_int(row.get("postId"))
    if post_id is None:
        raise ValueError("row has no integer post id")
    slug = safe_slug(row.get("slug") or f"post-{post_id}")
    return f"{post_id}-{slug}"


def record_path(out_dir: Path, row: Mapping[str, Any]) -> Path:
    return Path(out_dir) / _STILL_FOLDER / f"{record_stem(row)}.json"


def build_still_record(
    site_key: str, row: Mapping[str, Any], *, still: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge row identity around the package's neutral still evidence payload."""
    site = site_config(site_key)
    evidence = build_still_evidence(
        still=still, schema_version=schema_name(site, "still-evidence"),
        evidence_status=STILL_EVIDENCE_STATUS, limits=STILL_LIMITS,
        coverage_note=STILL_COVERAGE_NOTE, method=STILL_METHOD,
        is_source_video_frame=False, generated_at=generated_at)
    return {
        "schemaVersion": schema_name(site, "still-evidence"),
        "site": site["key"],
        "postId": as_int(row.get("id")),
        "slug": row.get("slug"),
        "title": row.get("title"),
        "publicationDate": row.get("publicationDate"),
        "articleUrl": row.get("articleUrl"),
        "provider": row.get("provider"),
        "termIds": row.get("termIds") or {},
        "terms": row.get("terms") or {},
        "poster": {
            "url": row.get("posterUrl"),
            "width": as_int(row.get("posterWidth")),
            "height": as_int(row.get("posterHeight")),
        },
        "videoDownloadable": False,
        "still": evidence["still"],
        "acquisition": evidence["acquisition"],
        "coverage": evidence["coverage"],
        "evidenceStatus": evidence["evidenceStatus"],
        "rights": {"basis": RIGHTS_BASIS, "status": RIGHTS_STATUS,
                   "note": "published poster still measured and deleted; not "
                           "redistributed"},
        "limits": evidence["limits"],
        "generatedAt": evidence["generatedAt"],
    }


def collect_still_one(
    site_key: str, row: Mapping[str, Any], out_dir: Path, *,
    max_bytes: int = STILL_MAX_BYTES, download_timeout: float = 60.0,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Download -> probe -> decode -> measure one poster; retain no image."""
    site = site_config(site_key)
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("still image byte cap must be positive")
    if not finite_float(download_timeout) or download_timeout <= 0:
        raise ValueError("still image timeout must be positive")
    url = policy_image_url(site, row.get("posterUrl"))
    target_path = record_path(Path(out_dir), row)
    with tempfile.TemporaryDirectory(
            prefix=f"kumiki-{site['key']}-still-") as directory:
        target = image_target(Path(directory), url)
        try:
            download_http(
                url, target, allowed_hosts=(site["host"],), max_bytes=max_bytes,
                timeout=download_timeout, accept="image/*", label="poster still")
            image_bytes = target.stat().st_size
            digest = sha256_file(target)
            measured = measure_still(target, ffmpeg=ffmpeg, ffprobe=ffprobe)
        finally:
            # Guarantee: even a failed decode leaves no image bytes anywhere.
            target.unlink(missing_ok=True)
    record = build_still_record(site_key, row, still={
        "imageUrl": url,
        "imageSha256": digest,
        "imageFormat": still_image_format(url, measured.pop("imageCodec", None)),
        "imageBytes": image_bytes,
        **measured,
    })
    write_json_atomic(target_path, record)
    return record


# ---------------------------------------------------------------------------
# video lane: article embed discovery and YouTube measurement
# ---------------------------------------------------------------------------


class VideoSkip(Exception):
    """A row the video lane refuses before download; recorded, never retried."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ArticleRefused(RuntimeError):
    """The article page answered 403/429 (site refusal, not a transient fault)."""


_YT_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_YT_EMBED_PATTERNS = (
    re.compile(
        r"(?:https?:)?//(?:www\.|m\.)?youtube(?:-nocookie)?\.com/embed/"
        r"([A-Za-z0-9_-]{11})"),
    re.compile(
        r"(?:https?:)?//(?:www\.|m\.)?youtube(?:-nocookie)?\.com/shorts/"
        r"([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:https?:)?//youtu\.be/([A-Za-z0-9_-]{11})"),
)
_YT_WATCH_RE = re.compile(
    r"(?:https?:)?//(?:www\.|m\.)?youtube(?:-nocookie)?\.com/watch\?"
    r"([^\"'<>\s]*)")
_VIMEO_EMBED_RE = re.compile(
    r"(?:https?:)?//(?:player\.)?vimeo\.com/(?:video/)?\d+")
_JSONLD_SCRIPT_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL)


def _normalise_markup(text: str) -> str:
    """Undo HTML entities and JSON solidus escaping before URL scanning."""
    return html.unescape(text).replace("\\/", "/")


def _youtube_id_in_text(text: str) -> str | None:
    """Return the id at the earliest position across all supported shapes."""
    candidates: list[tuple[int, str]] = []
    for pattern in _YT_EMBED_PATTERNS:
        for match in pattern.finditer(text):
            candidates.append((match.start(), match.group(1)))
    for match in _YT_WATCH_RE.finditer(text):
        query = match.group(1)
        for part in re.split(r"[&;]", query):
            key, separator, value = part.partition("=")
            if separator and key == "v" and _YT_ID.fullmatch(value):
                candidates.append((match.start(), value))
                break
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1]


def _walk_embed_urls(value: object) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and key in ("embedUrl", "contentUrl"):
                yield item
            else:
                yield from _walk_embed_urls(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_embed_urls(item)


def _jsonld_embed_urls(page_html: str) -> list[str]:
    urls: list[str] = []
    for match in _JSONLD_SCRIPT_RE.finditer(page_html):
        payload_text = html.unescape(match.group(1)).strip()
        try:
            payload = json.loads(payload_text)
        except (TypeError, ValueError):
            continue
        urls.extend(_walk_embed_urls(payload))
    return urls


def find_youtube_id(page_html: str) -> str | None:
    """Extract the first YouTube single-video id from article HTML.

    Scans the whole document (which covers both the ``<iframe src>`` and the
    JSON-LD ``VideoObject.embedUrl``) for ``/embed/<11>``, ``/watch?v=<11>``,
    ``/shorts/<11>``, and ``youtu.be/<11>``. The JSON-LD block is parsed as a
    fallback when a direct scan finds nothing.
    """
    if not isinstance(page_html, str):
        return None
    found = _youtube_id_in_text(_normalise_markup(page_html))
    if found is not None:
        return found
    for url in _jsonld_embed_urls(page_html):
        found = _youtube_id_in_text(_normalise_markup(url))
        if found is not None:
            return found
    return None


def has_vimeo_embed(page_html: str) -> bool:
    if not isinstance(page_html, str):
        return False
    return _VIMEO_EMBED_RE.search(_normalise_markup(page_html)) is not None


def canonical_youtube_url(video_id: str) -> str:
    """Validate an 11-char id and return the canonical ``watch?v=`` URL."""
    candidate = f"https://www.youtube.com/watch?v={video_id}"
    return allowlisted_youtube_url(
        candidate, allowed_hosts=DEFAULT_YOUTUBE_HOSTS)


def _fetch_article_html(site: Mapping[str, Any], url: str) -> str:
    """Read one article page through the engine's allowlisted text fetch."""
    return fetch_text(
        url, allowed_hosts=(site["host"],), timeout=45.0,
        limit=ARTICLE_MAX_BYTES, allow_query=False)


def youtube_url_for_row(
    site: Mapping[str, Any], row: Mapping[str, Any], *,
    fetch: Callable[[str], str] | None = None,
) -> str:
    """Resolve the row's first YouTube embed or raise :class:`VideoSkip`.

    The embed URL exists only in the rendered article HTML, so this is the one
    per-row page read. A 403/429 is a site refusal (raised as
    :class:`ArticleRefused`), never retried. A Vimeo-only page and a page with
    no embed are distinct skips.
    """
    url = as_text(row.get("articleUrl"))
    if url is None:
        raise VideoSkip("no-article-url")
    try:
        allowlisted_url(url, allowed_hosts=(site["host"],),
                        label="article URL", allow_query=False)
    except ValueError:
        raise VideoSkip("article-url-not-allowlisted") from None
    reader = (fetch if fetch is not None
              else (lambda target: _fetch_article_html(site, target)))
    try:
        page_html = reader(url)
    except HTTPError as error:
        if error.code in (403, 429):
            raise ArticleRefused(
                f"article page refused (HTTP {error.code})") from None
        raise ValueError(f"article fetch failed (HTTP {error.code})") from None
    video_id = find_youtube_id(page_html)
    if video_id is not None:
        return canonical_youtube_url(video_id)
    if has_vimeo_embed(page_html):
        raise VideoSkip("unsupported-vimeo")
    raise VideoSkip("no-embed-found")


def video_record_path(out_dir: Path, row: Mapping[str, Any]) -> Path:
    return Path(out_dir) / _VIDEO_FOLDER / f"{record_stem(row)}.json"


def build_video_record(
    site_key: str, row: Mapping[str, Any], *, source: dict[str, Any],
    coverage: dict[str, Any], windows: list[dict[str, Any]], method: str,
    video_url: str, rights_note: str = DEFAULT_RIGHTS_NOTE,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge row identity around the package's neutral video evidence payload."""
    site = site_config(site_key)
    schema = schema_name(site, "video-evidence")
    evidence = build_video_evidence(
        source=source, coverage=coverage, windows=windows, method=method,
        provider=YOUTUBE, video_url=video_url, rights_basis=RIGHTS_BASIS,
        rights_note=rights_note, schema_version=schema,
        evidence_status=VIDEO_EVIDENCE_STATUS, limits=VIDEO_LIMITS,
        generated_at=generated_at, rights_status=RIGHTS_STATUS)
    return {
        "schemaVersion": schema,
        "site": site["key"],
        "postId": as_int(row.get("id")),
        "slug": row.get("slug"),
        "title": row.get("title"),
        "publicationDate": row.get("publicationDate"),
        "articleUrl": row.get("articleUrl"),
        "provider": YOUTUBE,
        "termIds": row.get("termIds") or {},
        "terms": row.get("terms") or {},
        # The source is a platform-encoded YouTube rendition, not a master.
        "videoUrl": video_url,
        "downloadMethod": method,
        "mediaRetained": False,
        "renditionNote": RENDITION_NOTE,
        **evidence,
    }


def _require_video_budgets(
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


def collect_video_one(
    site_key: str, row: Mapping[str, Any], out_dir: Path, *,
    windows: int = DEFAULT_WINDOW_COUNT,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    rights_note: str = DEFAULT_RIGHTS_NOTE, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe", yt_dlp: str = "yt-dlp",
    download_timeout: float = VIDEO_DOWNLOAD_TIMEOUT,
    article_fetch: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Resolve the embed, download, measure, write one record, delete the media."""
    site = site_config(site_key)
    _require_video_budgets(
        windows=windows, window_seconds=window_seconds,
        max_duration_seconds=max_duration_seconds,
        max_file_bytes=max_file_bytes)
    if not isinstance(rights_note, str) or not rights_note.strip():
        raise ValueError("rights note must be non-empty")
    video_url = youtube_url_for_row(site, row, fetch=article_fetch)
    target_path = video_record_path(Path(out_dir), row)
    with tempfile.TemporaryDirectory(
            prefix=f"kumiki-{site['key']}-video-") as directory:
        media_dir = Path(directory) / "media"
        media_dir.mkdir()
        path, method = download_media(
            video_url, YOUTUBE, media_dir,
            allowed_hosts=DEFAULT_YOUTUBE_HOSTS, max_bytes=max_file_bytes,
            ffmpeg=ffmpeg, ffprobe=ffprobe, timeout=download_timeout,
            max_duration_seconds=max_duration_seconds, yt_dlp=yt_dlp,
            max_height=720)
        source = source_metadata(path, ffprobe=ffprobe)
        if source["durationSeconds"] > max_duration_seconds:
            raise ValueError("source exceeds the bounded duration budget")
        coverage, measured = measure_windows(
            path, duration_seconds=source["durationSeconds"],
            window_count=windows, window_seconds=window_seconds,
            image_translation=False, ffmpeg=ffmpeg, ffprobe=ffprobe)
        record = build_video_record(
            site_key, row, source=source, coverage=coverage, windows=measured,
            method=method, video_url=video_url, rights_note=rights_note)
    # The TemporaryDirectory deleted the media before this write; only numerics
    # and the source hash leave the scratch directory.
    write_json_atomic(target_path, record)
    return record


def _video_sort_key(row: Mapping[str, Any]) -> tuple[int, str]:
    post_id = as_int(row.get("postId"))
    return (post_id if post_id is not None else -1,
            str(row.get("slug") or ""))


def _video_summary_row(
    record: Mapping[str, Any], path: Path | None = None,
) -> dict[str, Any]:
    source = record.get("source") or {}
    coverage = record.get("coverage") or {}
    summary = record.get("summary") or {}
    acquisition = record.get("acquisition") or {}
    return {
        "postId": as_int(record.get("postId")),
        "slug": record.get("slug"),
        "title": record.get("title"),
        "publicationDate": record.get("publicationDate"),
        "provider": acquisition.get("provider") or record.get("provider"),
        "videoUrl": acquisition.get("videoUrl") or record.get("videoUrl"),
        "downloadMethod": (record.get("downloadMethod")
                           or acquisition.get("method")),
        "durationSeconds": finite_float(source.get("durationSeconds")),
        "resolution": list(source.get("resolution") or []),
        "windowsMeasured": as_int(coverage.get("windowsMeasured")),
        "cutCandidates": as_int(summary.get("cutCandidates")),
        "cutsPerMinute": finite_float(
            summary.get("cutCandidateRatePerMinute")),
        "meanDisplayLuma": finite_float(summary.get("meanDisplayLuma")),
        "meanSaturation": finite_float(summary.get("meanSaturation")),
        "recordPath": (path.as_posix() if path is not None
                       else f"{_VIDEO_FOLDER}/{record_stem(record)}.json"),
    }


def _video_detail(record: Mapping[str, Any]) -> str:
    source = record.get("source") or {}
    summary = record.get("summary") or {}
    resolution = list(source.get("resolution") or [None, None])
    width, height = (resolution + [None, None])[:2]
    return (f"{width}x{height} {(source.get('durationSeconds') or 0):.1f}s "
            f"cuts={summary.get('cutCandidates', 0)}")


def _load_retained_videos(
    out_dir: Path, site: Mapping[str, Any],
) -> list[dict[str, Any]]:
    retained: list[dict[str, Any]] = []
    directory = Path(out_dir) / _VIDEO_FOLDER
    if not directory.is_dir():
        return retained
    expected = schema_name(site, "video-evidence")
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict) and payload.get(
                "schemaVersion") == expected:
            retained.append(
                _video_summary_row(payload, path.relative_to(Path(out_dir))))
    return retained


def _video_error_text(
    out_dir: Path, site: Mapping[str, Any],
) -> Callable[[Exception], str]:
    scratch = re.compile(
        rf"/[^\s:'\"]*kumiki-{re.escape(site['key'])}-video-[^\s:'\"]*")

    def render(error: Exception) -> str:
        if isinstance(error, YtDlpError):
            reason = error.reason
        elif isinstance(error, ArticleRefused):
            reason = "site-refused"
        elif isinstance(error, VideoSkip):
            reason = error.reason
        else:
            reason = type(error).__name__
        text = scratch.sub("[scratch]",
                           safe_error(error, redact=(str(out_dir),)))
        text = re.sub(r"^[A-Za-z_][A-Za-z0-9_.]*: ", "", text)
        return f"{reason}: {text}"[:360]
    return render


def run_collect(
    site_key: str, catalog_path: Path, *, out_dir: Path,
    limit: int | None = DEFAULT_COLLECT_LIMIT, resume: bool = True,
    jobs: int = 1, acknowledge_rights: bool = False,
    delay_seconds: float = DEFAULT_VIDEO_DELAY,
    windows: int = DEFAULT_WINDOW_COUNT,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe", yt_dlp: str = "yt-dlp",
    log: Callable[[str], None] = print,
    article_fetch: Callable[[str], str] | None = None,
) -> int:
    """Measure the Directors' Library YouTube lane; ``stash`` is refused whole.

    ``--limit`` counts only attempted rows: resume skips and the whole-site
    refusal do not consume it. A provider refusal and a Vimeo-only / embed-less
    / site-refused article are skip rows; a transient download failure is a
    failure row. No refusal is ever retried.
    """
    site = site_config(site_key)
    if acknowledge_rights is not True:
        raise ValueError(
            "explicit --acknowledge-rights attestation is required: public "
            "availability is not a license, and each downloaded file is "
            "deleted after numeric measurement")
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a non-negative integer or None")
    if type(jobs) is not int or not 1 <= jobs <= MAX_JOBS:
        raise ValueError(f"jobs must be between 1 and {MAX_JOBS}")
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("delay_seconds must be a non-negative number")
    _require_video_budgets(
        windows=windows, window_seconds=window_seconds,
        max_duration_seconds=max_duration_seconds,
        max_file_bytes=max_file_bytes)
    catalog_file = Path(catalog_path)
    if not catalog_file.is_file():
        raise ValueError("a catalog file is required for the video lane")
    catalog_sha = sha256_file(catalog_file)
    items = sorted(_load_catalog(catalog_file, site)["items"],
                   key=catalog_order, reverse=True)
    out_dir = Path(out_dir)
    (out_dir / _VIDEO_FOLDER).mkdir(parents=True, exist_ok=True)
    index_path = out_dir / _VIDEO_INDEX_NAME

    def build_video_index(
        records: list[dict[str, Any]], skips: list[dict[str, Any]],
        failures: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return build_index(
            schema_version=schema_name(site, "index"),
            records=records, skips=skips, failures=failures,
            generated_at=utc_now(),
            extra={"site": site["key"], "catalogSha256": catalog_sha,
                   "limit": limit, "resume": resume})

    # STASH is a magazine feed whose every embed is Vimeo; there is no
    # downloadable rendition, so every row is an explicit, honest refusal.
    if site["key"] != "directorslibrary":
        skips = [_skip_row(row, "site-has-no-downloadable-rendition")
                 for row in items]
        write_json_atomic(index_path, build_video_index([], skips, []))
        log(f"video-measured=0 skipped={len(skips)} failed=0 attempted=0 "
            f"index={index_path}")
        log("no video lane for this site: every row is refused, none attempted")
        return 0

    retained = _load_retained_videos(out_dir, site) if resume else []
    cap = None if limit in (None, 0) else limit
    skips: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    measured: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for row in items:
        try:
            existing = video_record_path(out_dir, row)
        except ValueError as error:
            skips.append(_skip_row(row, f"unsafe-slug: {error}"))
            continue
        if resume and _resume_matches(existing, row.get("id"), field="postId"):
            skips.append(_skip_row(row, "resume-existing-record"))
            continue
        pending.append(row)
        if cap is not None and len(pending) >= cap:
            break

    attempted = 0
    lock = threading.Lock()

    def refresh() -> None:
        write_json_atomic(index_path, build_video_index(
            [*retained, *sorted(measured, key=_video_sort_key)],
            sorted(skips, key=_video_sort_key),
            sorted(failures, key=_video_sort_key)))

    def handle(row: dict[str, Any]) -> None:
        nonlocal attempted
        with lock:
            attempted += 1
            position = attempted
        label = str(row.get("slug") or "")
        try:
            record = collect_video_one(
                site_key, row, out_dir, windows=windows,
                window_seconds=window_seconds,
                max_duration_seconds=max_duration_seconds,
                max_file_bytes=max_file_bytes, ffmpeg=ffmpeg,
                ffprobe=ffprobe, yt_dlp=yt_dlp, article_fetch=article_fetch)
        except VideoSkip as error:
            with lock:
                skips.append(_skip_row(row, error.reason))
                refresh()
            print(f"[{position}/{len(pending)}] skip {label} {error.reason}",
                  flush=True)
            return
        except ArticleRefused:
            with lock:
                skips.append(_skip_row(row, "site-refused"))
                refresh()
            print(f"[{position}/{len(pending)}] skip {label} site-refused",
                  flush=True)
            return
        except YtDlpRefusedError:
            with lock:
                skips.append(_skip_row(row, "provider-refused"))
                refresh()
            print(f"[{position}/{len(pending)}] skip {label} provider-refused",
                  flush=True)
            return
        except Exception as error:  # noqa: BLE001 - one row never aborts
            reason = _video_error_text(out_dir, site)(error)
            with lock:
                failures.append(_skip_row(row, reason))
                refresh()
            print(f"[{position}/{len(pending)}] fail {label} {reason}",
                  flush=True)
            return
        with lock:
            measured.append(_video_summary_row(record))
            refresh()
        print(f"[{position}/{len(pending)}] ok {label} {_video_detail(record)}",
              flush=True)

    refresh()
    if jobs == 1:
        for position, row in enumerate(pending):
            handle(row)
            if delay_seconds and position + 1 < len(pending):
                time.sleep(float(delay_seconds)
                           + random.uniform(0, float(delay_seconds)))
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = [pool.submit(handle, row) for row in pending]
            for future in as_completed(futures):
                future.result()
    refresh()
    log(f"video-measured={len(retained) + len(measured)} "
        f"skipped={len(skips)} failed={len(failures)} "
        f"attempted={attempted} index={index_path}")
    log("all downloaded media was deleted; only numeric evidence and catalogue "
        "metadata remain")
    return 1 if attempted and not (retained or measured) else 0


# ---------------------------------------------------------------------------
# stills lane
# ---------------------------------------------------------------------------


def _skip_row(row: Any, reason: str) -> dict[str, Any]:
    return {
        "postId": row.get("id") if isinstance(row, dict) else None,
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
    return {
        "postId": record.get("postId"),
        "slug": record.get("slug"),
        "title": record.get("title"),
        "provider": record.get("provider"),
        "posterUrl": (record.get("poster") or {}).get("url"),
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


def _load_retained(
    out_dir: Path, site: Mapping[str, Any],
) -> list[dict[str, Any]]:
    retained: list[dict[str, Any]] = []
    directory = out_dir / _STILL_FOLDER
    if not directory.is_dir():
        return retained
    expected = schema_name(site, "still-evidence")
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict) and payload.get("schemaVersion") == expected:
            retained.append(_still_summary_row(payload, path.relative_to(out_dir)))
    return retained


def _error_text(out_dir: Path, site: Mapping[str, Any]) -> Callable[[Exception], str]:
    scratch = re.compile(
        rf"/[^\s:'\"]*kumiki-{re.escape(site['key'])}-still-[^\s:'\"]*")

    def render(error: Exception) -> str:
        return scratch.sub("[scratch]",
                           safe_error(error, redact=(str(out_dir),)))
    return render


def run_stills(
    site_key: str, catalog_path: Path, *, out_dir: Path, limit: int = 0,
    resume: bool = True, jobs: int = 1, delay_seconds: float = DEFAULT_STILL_DELAY,
    max_image_bytes: int = STILL_MAX_BYTES, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe", log: Callable[[str], None] = print,
) -> int:
    """Measure one published poster per catalogue row.

    ``limit=0`` means *all remaining* rows and terminates cleanly when every
    row is already measured (or has no poster). ``--resume`` only reads existing
    records: their bytes and mtimes are left untouched.
    """
    site = site_config(site_key)
    if type(limit) is not int or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    if type(jobs) is not int or not 1 <= jobs <= MAX_JOBS:
        raise ValueError(f"jobs must be between 1 and {MAX_JOBS}")
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("delay_seconds must be a non-negative number")
    catalog_file = Path(catalog_path)
    if not catalog_file.is_file():
        raise ValueError("a catalog file is required for the stills lane")
    catalog_sha = sha256_file(catalog_file)
    items = _load_catalog(catalog_file, site)["items"]
    out_dir = Path(out_dir)
    (out_dir / _STILL_FOLDER).mkdir(parents=True, exist_ok=True)

    pending: list[dict[str, Any]] = []
    initial_skips: list[dict[str, Any]] = []
    for row in items:
        if not row.get("posterUrl"):
            initial_skips.append(_skip_row(row, "no-published-poster"))
            continue
        try:
            existing = record_path(out_dir, row)
        except ValueError as error:
            initial_skips.append(_skip_row(row, f"unsafe-slug: {error}"))
            continue
        if resume and _resume_matches(existing, row.get("id"), field="postId"):
            initial_skips.append(_skip_row(row, "resume-existing-record"))
            continue
        pending.append(row)
        if limit and len(pending) >= limit:
            break

    retained = _load_retained(out_dir, site) if resume else []
    index_path = out_dir / _INDEX_NAME
    details: dict[str, str] = {}

    def run_one(row: dict[str, Any]) -> dict[str, Any]:
        record = collect_still_one(
            site_key, row, out_dir, max_bytes=max_image_bytes,
            ffmpeg=ffmpeg, ffprobe=ffprobe)
        details[str(row.get("slug"))] = _still_detail(record)
        return record

    def build_index_for(
        records: list[dict[str, Any]], skips: list[dict[str, Any]],
        failures: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return build_index(
            schema_version=schema_name(site, "stills-index"),
            records=[*retained, *records], skips=skips, failures=failures,
            generated_at=utc_now(),
            extra={"site": site["key"], "catalogSha256": catalog_sha,
                   "limit": limit, "resume": resume})

    def report(position: int, total: int, status: str, label: str,
               text: str) -> None:
        print(f"[{position}/{len(pending) or total}] {status} {label} "
              f"{text or details.pop(label, '')}", flush=True)

    outcome = run_batch(
        pending, run_one=run_one, index_path=index_path,
        build_index=build_index_for,
        summary_row=lambda record: _still_summary_row(record, None),
        skip_row=_skip_row, describe=lambda row: str(row.get("slug")),
        initial_skips=initial_skips, error_text=_error_text(out_dir, site),
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


def _term_pairs(record: Mapping[str, Any]) -> list[tuple[str, int, str | None]]:
    term_ids = record.get("termIds")
    terms = record.get("terms")
    pairs: list[tuple[str, int, str | None]] = []
    if not isinstance(term_ids, dict):
        return pairs
    for taxonomy in sorted(term_ids):
        ids = term_ids.get(taxonomy)
        if not isinstance(ids, list):
            continue
        names = terms.get(taxonomy) if isinstance(terms, dict) else None
        for index, value in enumerate(ids):
            term_id = as_int(value)
            if term_id is None:
                continue
            name = None
            if (isinstance(names, list) and index < len(names)
                    and isinstance(names[index], str)):
                name = names[index]
            pairs.append((taxonomy, term_id, name))
    return pairs


def _still_row(record: Mapping[str, Any], path: Path | None = None) -> dict[str, Any]:
    still = record.get("still") if isinstance(record.get("still"), dict) else {}
    metrics = still.get("metrics") if isinstance(still.get("metrics"), dict) else {}
    poster = record.get("poster") if isinstance(record.get("poster"), dict) else {}
    return {
        "postId": as_int(record.get("postId")),
        "slug": record.get("slug"),
        "title": record.get("title"),
        "publicationDate": record.get("publicationDate"),
        "provider": record.get("provider"),
        "terms": record.get("terms") if isinstance(record.get("terms"), dict) else {},
        "termIds": record.get("termIds") if isinstance(record.get("termIds"), dict) else {},
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
        "lumaHistogram": metrics.get("lumaHistogram"),
        "generatedAt": record.get("generatedAt"),
        "recordPath": (path.as_posix() if path is not None else
                       f"{_STILL_FOLDER}/{record_stem(record)}.json"),
    }


def _still_order(row: Mapping[str, Any]) -> tuple[int, str]:
    post_id = as_int(row.get("postId"))
    return (post_id if post_id is not None else 0, str(row.get("slug") or ""))


def _record_video_relative(record: Mapping[str, Any]) -> str:
    try:
        return f"{_VIDEO_FOLDER}/{record_stem(record)}.json"
    except ValueError:
        post_id = as_int(record.get("postId"))
        return (f"{_VIDEO_FOLDER}/post-"
                f"{post_id if post_id is not None else 'unknown'}.json")


def _video_row(
    record: Mapping[str, Any], path: Path | None = None,
) -> dict[str, Any]:
    """Derive one per-video table row strictly from embedded record fields."""
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    acquisition = (record.get("acquisition")
                   if isinstance(record.get("acquisition"), dict) else {})
    coverage = (record.get("coverage")
                if isinstance(record.get("coverage"), dict) else {})
    summary = (record.get("summary")
               if isinstance(record.get("summary"), dict) else {})
    resolution = source.get("resolution")
    resolution_text = None
    if isinstance(resolution, (list, tuple)) and len(resolution) == 2:
        width, height = as_int(resolution[0]), as_int(resolution[1])
        if width is not None and height is not None:
            resolution_text = f"{width}x{height}"
    duration = finite_float(source.get("durationSeconds"))
    size = finite_float(source.get("sizeBytes"))
    bitrate = (round(size * 8 / duration / 1_000_000, 6)
               if size is not None and duration is not None and duration > 0
               else None)
    fraction = finite_float(coverage.get("fractionOfRuntime"))
    return {
        "postId": as_int(record.get("postId")),
        "slug": record.get("slug"),
        "title": record.get("title"),
        "publicationDate": record.get("publicationDate"),
        "provider": acquisition.get("provider") or record.get("provider"),
        "videoUrl": acquisition.get("videoUrl") or record.get("videoUrl"),
        "downloadMethod": (record.get("downloadMethod")
                           or acquisition.get("method")),
        "runtimeSeconds": duration,
        "resolution": resolution_text,
        "bitrateMbps": bitrate,
        "downloadMb": (round(size / (1024 * 1024), 6)
                       if size is not None else None),
        "windowsMeasured": as_int(coverage.get("windowsMeasured")),
        "coveragePercent": (round(fraction * 100, 6)
                            if fraction is not None else None),
        "sampledSeconds": finite_float(coverage.get("sampledSeconds")),
        "cutCandidates": as_int(summary.get("cutCandidates")),
        "cutsPerMinute": finite_float(
            summary.get("cutCandidateRatePerMinute")),
        "meanDisplayLuma": finite_float(summary.get("meanDisplayLuma")),
        "meanSaturation": finite_float(summary.get("meanSaturation")),
        "meanWithinShotDeltaPerSecond": finite_float(
            summary.get("meanWithinShotRgbDeltaPerSecond")),
        "recordPath": (path.as_posix() if path is not None
                       else _record_video_relative(record)),
    }


def _video_order(row: Mapping[str, Any]) -> tuple[bool, int, str]:
    """Newest catalogue row first, then post id descending; missing dates last."""
    published = as_text(row.get("publicationDate"))
    post_id = as_int(row.get("postId"))
    return (published is None, -(post_id or 0), str(row.get("slug") or ""))


def _coverage_aggregate(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    paired = [(row.get("runtimeSeconds"), row.get("sampledSeconds"))
              for row in rows
              if row.get("runtimeSeconds") and row.get("sampledSeconds")
              is not None]
    total_runtime = (round(sum(runtime for runtime, _ in paired), 6)
                     if paired else 0.0)
    total_sampled = (round(sum(sampled for _, sampled in paired), 6)
                     if paired else 0.0)
    return {
        "recordsWithRuntime": len(paired),
        "totalRuntimeSeconds": total_runtime,
        "totalSampledSeconds": total_sampled,
        "sampledFractionOfTotalRuntime": (
            round(total_sampled / total_runtime, 6) if total_runtime else None),
        "perRecordCoveragePercent": _distribution(
            row.get("coveragePercent") for row in rows),
    }



def _term_distributions(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, dict[tuple[int, str], dict[str, Any]]] = {}
    for row in rows:
        luma = finite_float(row.get("meanDisplayLuma"))
        record = {"termIds": row.get("termIds"), "terms": row.get("terms")}
        for taxonomy, term_id, name in _term_pairs(record):
            key = (term_id, name or "")
            entry = buckets.setdefault(taxonomy, {}).setdefault(key, {
                "termId": term_id, "name": name, "lumas": []})
            entry["lumas"].append(luma)
    result: dict[str, list[dict[str, Any]]] = {}
    for taxonomy in sorted(buckets):
        items = []
        for (term_id, name), entry in buckets[taxonomy].items():
            items.append({
                "termId": term_id,
                "name": name,
                "records": len(entry["lumas"]),
                "meanDisplayLuma": _distribution(entry["lumas"]),
            })
        items.sort(key=lambda item: (-item["records"], item["name"] or "",
                                     item["termId"]))
        result[taxonomy] = items
    return result


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
    records: Iterable[Mapping[str, Any]], catalog: dict[str, Any] | None,
    video_records: Iterable[Mapping[str, Any]] = (),
    video_index: dict[str, Any] | None = None,
) -> str | None:
    stamps = [text for record in records
              for text in (as_text(record.get("generatedAt")),)
              if text is not None]
    stamps.extend(
        text for record in video_records
        for text in (as_text(record.get("generatedAt")),)
        if text is not None)
    if isinstance(video_index, dict):
        stamp = as_text(video_index.get("generatedAt"))
        if stamp is not None:
            stamps.append(stamp)
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


def _reproduce_commands(
    *, site_key: str, out_dir: Path, catalog_path: Path, top: int,
) -> list[str]:
    out = shlex.quote(str(out_dir))
    catalog = shlex.quote(str(catalog_path))
    return [
        "python scripts/research_wordpress_stills.py catalog "
        f"--site {site_key} --out {catalog}",
        "python scripts/research_wordpress_stills.py collect "
        f"--site {site_key} --catalog {catalog} --out-dir {out} "
        "--acknowledge-rights",
        "python scripts/research_wordpress_stills.py stills "
        f"--site {site_key} --catalog {catalog} --out-dir {out} --resume",
        "python scripts/research_wordpress_stills.py report "
        f"--site {site_key} --out-dir {out} --top {top}",
    ]


def _render_report(
    aggregate: dict[str, Any], *, site: Mapping[str, Any], out_dir: Path,
    catalog_path: Path, top: int,
) -> str:
    counts = aggregate["counts"]
    rows = aggregate["stills"]
    by_term = aggregate["byTerm"]
    videos = aggregate.get("videos") or []
    video_aggregates = aggregate.get("videoAggregates") or {}
    video_top = videos[:top]
    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    if videos:
        add(f"# {site['label']} — measured video and still evidence report")
        add()
        add("This deliverable tabulates only what the committed evidence records "
            "contain: WordPress catalogue metadata, sampled source-PTS numeric "
            "probes of the public YouTube rendition, and one measured, "
            "published poster still per item where present. It makes no "
            "aesthetic, stylistic, intentional, authorship, or quality claim.")
    else:
        add(f"# {site['label']} — published-still evidence (still-only) report")
        add()
        add("This deliverable tabulates only what the committed evidence records "
            "contain: WordPress catalogue metadata and one measured, published "
            "poster still per item. It is **still-only**: it makes no motion, "
            "cut, pacing, timing, sequence, edit-rhythm, aesthetic, style, "
            "authorship, or quality claim.")
    add()

    add("## Provenance")
    add()
    add(f"- Catalog items: {_int(counts['catalogItems'])}")
    add(f"- Video-measured records: {_int(counts.get('videoMeasured'))}")
    add(f"- Still-measured records: {_int(counts['stillMeasured'])}")
    add(f"- Still-only records (no matching video record): "
        f"{_int(counts.get('stillOnly'))}")
    add(f"- Skipped rows (stills index context): {_int(counts['skipped'])}")
    add(f"- Failed acquisitions (stills index context): {_int(counts['failed'])}")
    add(f"- Skipped rows (video index context): "
        f"{_int(counts.get('videoSkipped'))}")
    add(f"- Failed acquisitions (video index context): "
        f"{_int(counts.get('videoFailed'))}")
    add(f"- Catalogue items without a usable poster: "
        f"{_int(counts['catalogWithoutPoster'])}")
    add(f"- Unreadable records: {_int(counts['unreadable'])}")
    add(f"- generatedAt: {_cell(aggregate.get('generatedAt'))}")
    skip_reasons = aggregate.get("skipReasons") or {}
    if skip_reasons:
        add("- Skip reasons (stills index): " + ", ".join(
            f"{_cell(reason)} x {count}"
            for reason, count in sorted(skip_reasons.items())))
    video_skip_reasons = aggregate.get("videoSkipReasons") or {}
    if video_skip_reasons:
        add("- Skip reasons (video index): " + ", ".join(
            f"{_cell(reason)} x {count}"
            for reason, count in sorted(video_skip_reasons.items())))
    providers = counts.get("providerCounts") or {}
    if providers:
        add("- Per-row provider labels: " + ", ".join(
            f"{_cell(provider)} x {count}"
            for provider, count in sorted(providers.items())))
    video_providers = counts.get("videoByProvider") or {}
    if video_providers:
        add("- Provider split (measured videos): " + ", ".join(
            f"{_cell(provider)} x {count}"
            for provider, count in sorted(video_providers.items())))
    if top < len(videos):
        add(f"- `--top {top}` applied: the first {top} of {len(videos)} "
            "video-measured rows are tabulated below; `aggregate.json` holds "
            "all.")
    if top < len(rows):
        add(f"- `--top {top}` applied: the first {top} of {len(rows)} "
            "measured stills are tabulated below; `aggregate.json` holds all.")
    add()
    add(site["caveat"])
    add()
    add("Reproduce the inputs and this report with:")
    add()
    add("```bash")
    for command in _reproduce_commands(
            site_key=site["key"], out_dir=out_dir, catalog_path=catalog_path,
            top=top):
        add(command)
    add("```")
    add()

    if videos:
        add("## Per-video analysis")
        add()
        add(f"{len(videos)} video-measured record(s), newest catalogue row "
            "first. All columns are numeric record fields from the sampled "
            "source-PTS windows of the public YouTube rendition; `duration_s` "
            "is the decoded local source duration, not a catalogue value.")
        add()
        video_columns = (
            "post_id", "slug", "title", "provider", "published", "duration_s",
            "resolution", "download_mb", "windows", "coverage_pct", "cuts",
            "cuts_per_min", "mean_luma", "mean_sat", "delta_per_s")
        add("| " + " | ".join(video_columns) + " |")
        add("| " + " | ".join("---" for _ in video_columns) + " |")
        for row in video_top:
            values = (
                _int(row["postId"]), row["slug"], row["title"], row["provider"],
                row["publicationDate"], _num(row["runtimeSeconds"], 2),
                row["resolution"], _num(row["downloadMb"], 1),
                _int(row["windowsMeasured"]), _num(row["coveragePercent"], 1),
                _int(row["cutCandidates"]), _num(row["cutsPerMinute"], 2),
                _num(row["meanDisplayLuma"], 4),
                _num(row["meanSaturation"], 4),
                _num(row["meanWithinShotDeltaPerSecond"], 4))
            add("| " + " | ".join(_cell(value) for value in values) + " |")
        add()
        add("| download_method | provider | video_url |")
        add("| --- | --- | --- |")
        for row in video_top:
            add("| " + " | ".join((
                _cell(row["downloadMethod"]), _cell(row["provider"]),
                _cell(row["videoUrl"]))) + " |")
        add()

        add("## Aggregates (video-measured records only)")
        add()
        add("Every number in this section is computed ONLY over the "
            "video-measured records tabulated above. Published stills, "
            "including still-only rows, never enter the motion, cut, luma, or "
            "saturation aggregates.")
        add()
        distributions = video_aggregates.get("distributions") or {}
        add("| metric | n | min | median | max |")
        add("| --- | --- | --- | --- | --- |")
        for label, key, digits in (
                ("duration_s", "runtimeSeconds", 2),
                ("cuts_per_min", "cutsPerMinute", 2),
                ("mean_luma", "meanDisplayLuma", 4),
                ("mean_sat", "meanSaturation", 4),
                ("delta_per_s", "meanWithinShotDeltaPerSecond", 4)):
            entry = distributions.get(key) or {"n": 0, "min": None,
                                               "median": None, "max": None}
            add(f"| {label} | {entry['n']} | {_num(entry['min'], digits)} | "
                f"{_num(entry['median'], digits)} | "
                f"{_num(entry['max'], digits)} |")
        add()
        coverage = video_aggregates.get("coverage") or {}
        add("Coverage-weighted caveat: "
            f"{_num(coverage.get('totalSampledSeconds'), 1)} sampled seconds "
            f"cover {_num(coverage.get('totalRuntimeSeconds'), 1)} runtime "
            "seconds "
            f"({_num((coverage.get('sampledFractionOfTotalRuntime') or 0) * 100, 1)}%). "
            "Aggregates describe the sampled windows, not the full films.")
        add()

    add("## Measured stills")
    add()
    add(f"{len(rows)} still-measured record(s), ordered by post id then slug. "
        "Every number describes one published image, never a video frame.")
    add()
    columns = (
        "post_id", "slug", "title", "poster_w", "poster_h", "img_w", "img_h",
        "img_bytes", "mean_luma", "mean_sat", "hue", "edge_density")
    add("| " + " | ".join(columns) + " |")
    add("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows[:top]:
        values = (
            _int(row["postId"]), row["slug"], row["title"],
            _int(row["posterWidth"]), _int(row["posterHeight"]),
            _int(row["imageWidth"]), _int(row["imageHeight"]),
            _int(row["imageBytes"]), _num(row["meanDisplayLuma"], 4),
            _num(row["meanSaturation"], 4), row["dominantHueFamily"],
            _num(row["edgeDensity"], 4))
        add("| " + " | ".join(_cell(value) for value in values) + " |")
    if not rows:
        add("| — | — | — | — | — | — | — | — | — | — | — | — |")
    add()

    add("## Distributions by term")
    add()
    add("Each term row aggregates only the measured stills that carry that "
        "term. Term names were resolved from the WordPress taxonomy endpoints "
        "and cached in the catalogue. Counts describe this measured sample, "
        "not the full catalogue.")
    add()
    if not by_term:
        add("No term-bearing still records.")
        add()
    for taxonomy in sorted(by_term):
        add(f"### {_cell(taxonomy)}")
        add()
        add("| term | term_id | stills | luma min | luma median | luma max |")
        add("| --- | --- | --- | --- | --- | --- |")
        for entry in by_term[taxonomy][:top]:
            luma = entry["meanDisplayLuma"]
            add("| " + " | ".join((
                _cell(entry["name"]), _int(entry["termId"]),
                _int(entry["records"]), _num(luma["min"], 4),
                _num(luma["median"], 4), _num(luma["max"], 4))) + " |")
        add()

    if videos:
        add("## What was measured, and what was not")
        add()
        add("The video lane measures YouTube entries only:")
        add()
        add("- Each video-measured row is a sampled source-PTS probe of the "
            "public YouTube rendition, obtained by a bounded, cookie-free local "
            "yt-dlp; it is not the work's delivered master.")
        add("- Vimeo references are recorded as `unsupported-vimeo` and were "
            "never fetched, probed, or player-inspected.")
        add("- No cookies, logins, browser profiles, remote components, or "
            "DRM/PO-token circumvention were used, and a provider refusal was "
            "never retried.")
        add("- Published poster stills are reported separately and never enter "
            "the motion, cut, luma, or saturation aggregates.")
        add()
    else:
        add("## Why there is no motion evidence")
        add()
        if site["key"] == "directorslibrary":
            add("This still-only evidence set contains no video-measured "
                "records:")
            add()
            add("- The video lane (`collect`) measures a YouTube rendition only "
                "once it is run; this output directory has no `videos/` "
                "records.")
            add("- A row whose article embeds only Vimeo is skipped as "
                "`unsupported-vimeo`; no Vimeo player or `/config` endpoint is "
                "ever fetched.")
            add("- Vimeo/YouTube embeds were never acquired or probed by the "
                "stills lane.")
        else:
            add("There is no video lane for this site, by design:")
            add()
            add(f"- Every video is a third-party "
                f"{'/'.join(site['embedProviders'])} embed "
                "(`player.vimeo.com/video/<id>` or "
                "`www.youtube.com/embed/<id>`); no progressive MP4/HLS file is "
                "published.")
            add("- This site's embeds are Vimeo-only, and the repository "
                "records Vimeo as unsupported.")
            add("- No cookies, auth, player-API tricks, or DRM circumvention "
                "were used, and no embed was probed.")
        add("- Therefore this report cannot and does not measure motion, cuts, "
            "pacing, timing, sequences, or edit rhythm. A poster still is not a "
            "video frame.")
        if site["key"] == "stash":
            add("- STASH is a magazine feed: many posts are image galleries, "
                "not videos, so even the per-row provider label is not a "
                "video-coverage claim.")
        add()

    add("## Explicit non-claims")
    add()
    claims = [
        "A published poster still is not a video frame; single-image "
        "colour, luminance, histogram, hue, and edge-density numbers carry "
        "no motion, cut, pacing, timing, sequence, or edit-rhythm evidence.",
        "No style, aesthetic quality, mood, lighting, camera/lens, "
        "editorial intent, authorship, identity, or creative-origin "
        "inference is made from these numbers.",
        "The poster is prepared by the site/CMS, not necessarily by the "
        "work's author; for STASH it may be a gallery image.",
        "Public availability is not a licence: `rightsStatus` remains "
        "`review-required`, and reuse needs its own review.",
        "Catalogue metadata is self-reported by the site and is not "
        "independently verified.",
        "The site's REST API exposes no director, duration, brand, or "
        "agency values for Directors' Library; those fields are absent, "
        "not invented.",
        "Downloaded poster images are never retained: only hashes and "
        "numbers remain.",
    ]
    if videos:
        claims.append(
            "The measured source is a platform-encoded YouTube rendition, not "
            "the work's delivered master; every video number describes that "
            "rendition only.")
        claims.append(
            "Downloaded video media is never retained: only hashes and numbers "
            "remain.")
    else:
        claims.append("Vimeo/YouTube embeds were never acquired or probed.")
    for claim in claims:
        add(f"- {claim}")
    add()
    return "\n".join(lines)


def run_report(
    site_key: str, out_dir: Path, *, catalog_path: Path | None = None,
    top: int = DEFAULT_TOP, generated_at: str | None = None,
    log: Callable[[str], None] = print,
) -> int:
    """Read collected records read-only and write ``report.md`` + ``aggregate.json``."""
    site = site_config(site_key)
    if type(top) is not int or top < 0:
        raise ValueError("top must be a non-negative integer")
    out_dir = Path(out_dir)
    requested = Path(catalog_path) if catalog_path is not None else None
    if requested is not None and not requested.is_file():
        raise ValueError("catalog file does not exist")
    default_catalog = out_dir / _CATALOG_NAME
    catalog_path = (requested if requested is not None else
                    (default_catalog if default_catalog.is_file() else None))

    records, problems = _load_records(
        out_dir / _STILL_FOLDER, schema_name(site, "still-evidence"),
        prefix=_STILL_FOLDER)
    video_records, video_problems = _load_records(
        out_dir / _VIDEO_FOLDER, schema_name(site, "video-evidence"),
        prefix=_VIDEO_FOLDER)
    problems.extend(video_problems)
    catalog, catalog_problems = _load_json_context(catalog_path,
                                                   prefix=_CATALOG_NAME)
    index, index_problems = _load_json_context(out_dir / _INDEX_NAME,
                                              prefix=_INDEX_NAME)
    video_index, video_index_problems = _load_json_context(
        out_dir / _VIDEO_INDEX_NAME, prefix=_VIDEO_INDEX_NAME)
    problems.extend(catalog_problems)
    problems.extend(index_problems)
    problems.extend(video_index_problems)
    problems.sort(key=lambda item: (item["file"], item["reason"]))

    if generated_at is None:
        generated_at = _latest_timestamp(
            records, catalog, video_records=video_records,
            video_index=video_index)

    rows = sorted(
        (_still_row(record, Path(_STILL_FOLDER) / f"{record_stem(record)}.json")
         for record in records),
        key=_still_order)
    measured_total = len(rows)
    by_term = _term_distributions(rows)
    video_rows = sorted(
        (_video_row(record, Path(_record_video_relative(record)))
         for record in video_records),
        key=_video_order)
    video_keys = {as_int(record.get("postId")) for record in video_records}
    still_only = sum(1 for record in records
                     if as_int(record.get("postId")) not in video_keys)

    catalog_items = None
    catalog_without_poster = None
    if isinstance(catalog, dict):
        catalog_items = as_int((catalog.get("counts") or {}).get("catalogItems"))
        if catalog_items is None and isinstance(catalog.get("items"), list):
            catalog_items = len(catalog["items"])
        catalog_without_poster = as_int(
            (catalog.get("counts") or {}).get("withoutPoster"))

    if video_rows and rows:
        evidence = "video-measured+still-measured"
    elif video_rows:
        evidence = "video-measured"
    else:
        evidence = "still-only"

    aggregate = {
        "schemaVersion": schema_name(site, "aggregate"),
        "site": site["key"],
        "generatedAt": generated_at,
        "evidence": evidence,
        "counts": {
            "catalogItems": catalog_items,
            "videoMeasured": len(video_rows),
            "stillMeasured": measured_total,
            "stillOnly": still_only,
            "skipped": _list_length(index, "skips"),
            "failed": _list_length(index, "failures"),
            "videoSkipped": _list_length(video_index, "skips"),
            "videoFailed": _list_length(video_index, "failures"),
            "catalogWithoutPoster": catalog_without_poster,
            "unreadable": len(problems),
            "providerCounts": _counter(row.get("provider") for row in rows),
            "videoByProvider": _counter(
                row.get("provider") for row in video_rows),
        },
        "skipReasons": _skip_reasons(index),
        "videoSkipReasons": _skip_reasons(video_index),
        "distributions": {
            "meanDisplayLuma": _distribution(
                row.get("meanDisplayLuma") for row in rows),
            "meanSaturation": _distribution(
                row.get("meanSaturation") for row in rows),
            "edgeDensity": _distribution(
                row.get("edgeDensity") for row in rows),
            "imageBytes": _distribution(
                row.get("imageBytes") for row in rows),
        },
        "videoAggregates": {
            "basis": ("video-measured records only; published stills and "
                      "still-only rows never enter these numbers"),
            "recordCount": len(video_rows),
            "distributions": {
                "runtimeSeconds": _distribution(
                    row.get("runtimeSeconds") for row in video_rows),
                "cutsPerMinute": _distribution(
                    row.get("cutsPerMinute") for row in video_rows),
                "meanDisplayLuma": _distribution(
                    row.get("meanDisplayLuma") for row in video_rows),
                "meanSaturation": _distribution(
                    row.get("meanSaturation") for row in video_rows),
                "meanWithinShotDeltaPerSecond": _distribution(
                    row.get("meanWithinShotDeltaPerSecond")
                    for row in video_rows),
            },
            "coverage": _coverage_aggregate(video_rows),
        },
        "byTerm": by_term,
        "videos": video_rows,
        "stills": rows,
        "limits": list(STILL_LIMITS),
        "videoLimits": list(VIDEO_LIMITS),
        "unreadableRecords": problems,
    }

    report_path = out_dir / "report.md"
    aggregate_path = out_dir / "aggregate.json"
    write_json_atomic(aggregate_path, aggregate)
    _write_text_atomic(report_path, _render_report(
        aggregate, site=site, out_dir=out_dir,
        catalog_path=catalog_path or default_catalog, top=top))
    log(f"report: videos={len(video_rows)} stills={measured_total} "
        f"skipped={aggregate['counts']['skipped']} "
        f"failed={aggregate['counts']['failed']} unreadable={len(problems)} "
        f"-> {report_path}")
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
        description="Ephemeral WordPress video + published-still research "
                    "collector (Directors' Library, STASH)")
    sub = parser.add_subparsers(dest="command", required=True)

    catalog = sub.add_parser(
        "catalog", help="fetch the slim WP REST catalogue and resolve term names")
    catalog.add_argument("--site", required=True, choices=sorted(SITES),
                         help="site key")
    catalog.add_argument("--out", type=Path, required=True,
                         help="path for the versioned catalog JSON")
    catalog.add_argument("--limit", type=int, default=None,
                         help="catalog size (default: all; 0 = no request)")
    catalog.add_argument("--page-size", type=int, default=DEFAULT_CATALOG_PAGE_SIZE)
    catalog.add_argument("--delay-seconds", type=float,
                         default=DEFAULT_CATALOG_DELAY,
                         help="politeness pause (plus equal jitter) between pages")

    collect = sub.add_parser(
        "collect", help="measure the YouTube video lane (Directors' Library "
                        "only; STASH is refused row by row)")
    collect.add_argument("--site", required=True, choices=sorted(SITES),
                         help="site key")
    collect.add_argument("--catalog", type=Path, required=True)
    collect.add_argument("--out-dir", type=Path, required=True)
    collect.add_argument("--limit", type=int, default=DEFAULT_COLLECT_LIMIT,
                         help="cap attempted rows (0 = all remaining); skips "
                              "do not count")
    collect.add_argument("--window-count", type=int,
                         default=DEFAULT_WINDOW_COUNT)
    collect.add_argument("--window-seconds", type=int,
                         default=DEFAULT_WINDOW_SECONDS)
    collect.add_argument("--max-duration-seconds", type=float,
                         default=DEFAULT_MAX_DURATION_SECONDS)
    collect.add_argument("--max-file-bytes", type=parse_byte_size,
                         default=DEFAULT_MAX_FILE_BYTES,
                         help="download cap in bytes or a size like 250MiB")
    collect.add_argument("--acknowledge-rights", action="store_true")
    collect_group = collect.add_mutually_exclusive_group()
    collect_group.add_argument("--resume", dest="resume", action="store_true",
                               default=True)
    collect_group.add_argument("--refresh", dest="resume",
                               action="store_false")
    collect.add_argument("--jobs", type=int, default=1)
    collect.add_argument("--delay-seconds", type=float,
                         default=DEFAULT_VIDEO_DELAY,
                         help="politeness pause (plus equal jitter) per row")
    collect.add_argument("--yt-dlp", default="yt-dlp")
    collect.add_argument("--ffmpeg", default="ffmpeg")
    collect.add_argument("--ffprobe", default="ffprobe")

    stills = sub.add_parser(
        "stills", help="measure one published poster still per catalog item")
    stills.add_argument("--site", required=True, choices=sorted(SITES),
                        help="site key")
    stills.add_argument("--catalog", type=Path, required=True)
    stills.add_argument("--out-dir", type=Path, required=True)
    stills.add_argument("--limit", type=int, default=0,
                        help="0 = every remaining row; N = first N pending")
    group = stills.add_mutually_exclusive_group()
    group.add_argument("--resume", dest="resume", action="store_true",
                       default=True)
    group.add_argument("--refresh", dest="resume", action="store_false")
    stills.add_argument("--jobs", type=int, default=1)
    stills.add_argument("--delay-seconds", type=float, default=DEFAULT_STILL_DELAY,
                        help="politeness pause (plus equal jitter) between stills")
    stills.add_argument("--max-image-bytes", type=int, default=STILL_MAX_BYTES)
    stills.add_argument("--ffmpeg", default="ffmpeg")
    stills.add_argument("--ffprobe", default="ffprobe")

    report = sub.add_parser(
        "report", help="write report.md + aggregate.json from still records "
                       "(read-only, offline)")
    report.add_argument("--site", required=True, choices=sorted(SITES),
                        help="site key")
    report.add_argument("--out-dir", type=Path, required=True)
    report.add_argument("--catalog", type=Path, default=None,
                        help="catalog JSON (default: <out-dir>/catalog.json)")
    report.add_argument("--top", type=int, default=DEFAULT_TOP,
                        help="table rows and per-term rows to render")
    return parser


def run_catalog(
    site_key: str, out: Path, *, limit: int | None = DEFAULT_CATALOG_LIMIT,
    page_size: int = DEFAULT_CATALOG_PAGE_SIZE,
    delay_seconds: float = DEFAULT_CATALOG_DELAY,
    log: Callable[[str], None] = print,
) -> int:
    rows, meta = fetch_catalog(
        site_key, limit=limit, page_size=page_size,
        delay_seconds=delay_seconds, log=log)
    catalog = build_catalog(
        site_key, rows, meta=meta, page_size=page_size, limit=limit)
    write_json_atomic(Path(out), catalog)
    log(f"catalog: {catalog['counts']['catalogItems']} items of "
        f"{catalog['counts']['reportedTotal']} reported -> {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            return run_catalog(
                args.site, args.out, limit=args.limit,
                page_size=args.page_size, delay_seconds=args.delay_seconds)
        if args.command == "stills":
            return run_stills(
                args.site, args.catalog, out_dir=args.out_dir,
                limit=args.limit, resume=args.resume, jobs=args.jobs,
                delay_seconds=args.delay_seconds,
                max_image_bytes=args.max_image_bytes, ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe)
        if args.command == "collect":
            return run_collect(
                args.site, args.catalog, out_dir=args.out_dir,
                limit=args.limit, resume=args.resume, jobs=args.jobs,
                acknowledge_rights=args.acknowledge_rights,
                delay_seconds=args.delay_seconds,
                windows=args.window_count, window_seconds=args.window_seconds,
                max_duration_seconds=args.max_duration_seconds,
                max_file_bytes=args.max_file_bytes, ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe, yt_dlp=args.yt_dlp)
        return run_report(
            args.site, args.out_dir, catalog_path=args.catalog, top=args.top)
    except ValueError as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    sys.exit(main())
