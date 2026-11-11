"""Ephemeral, source-hashed measurement of public Motionographer MP4 posts.

Catalog metadata comes from the site's own public WordPress REST endpoint
(``/wp-json/wp/v2/posts``), read one page at a time with a polite delay. Each
post's rendered HTML is classified per media item: Vimeo and YouTube embeds are
recorded as explicit ``unsupported-*`` skip rows and are never attempted, and
only direct HTTPS MP4 files on an exact allowlisted site-owned host are
downloaded. Every downloaded byte lives in a ``TemporaryDirectory`` deleted in a
``finally`` block; only numeric source-PTS evidence, hashes, and catalog
metadata are committed.

This is a *site adapter*: every mechanic (allowlisting, retrieval, probing,
window measurement, evidence assembly, atomic writes, resume checks, pooled
batch loop) comes from :mod:`kumiki_reference_lab.acquisition`. Site-specific
hosts, path prefixes, and provider vocabulary live only here.

Subcommands::

    enumerate   walk the WordPress posts API, classify every media item, and
                write catalog.json plus index.json (no media is downloaded)
    measure     download, measure, and delete the eligible MP4s one at a time
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition import (  # noqa: E402
    DIRECT, USER_AGENT, VIDEO_SUFFIXES, allowlisted_video_url, as_int, as_text,
    build_video_evidence, download_media, finite_float, measure_windows,
    resume_matches as _resume_matches, run_batch, safe_error, safe_slug,
    source_metadata, utc_now, write_json_atomic,
)
from kumiki_reference_lab.analyzers.media.inspect import sha256_file  # noqa: E402

SITE = "https://motionographer.com"
POSTS_ENDPOINT = f"{SITE}/wp-json/wp/v2/posts"
POSTS_FIELDS = "id,slug,link,title,date,content"
PER_PAGE = 100
DEFAULT_OUT_DIR = ROOT / "research" / "analysis" / "motionographer"
CATALOG_SCHEMA = "kumiki.motionographer-catalog.v1"
INDEX_SCHEMA = "kumiki.motionographer-index.v1"
VIDEO_SCHEMA = "kumiki.motionographer-video-evidence.v1"
EVIDENCE_STATUS = "sampled-original-source-pts-metrics-not-expert-reviewed"
RIGHTS_BASIS = "user-declared-research-use"
RIGHTS_STATUS = "review-required"
DEFAULT_RIGHTS_NOTE = (
    "operator attests public-post research use; downloaded media is deleted "
    "after numeric source-PTS measurement and is not redistributed")
DELAY_SECONDS = 1.5
MAX_RETRY_AFTER_SECONDS = 900
SELF_HOSTED_PROVIDER = "self-hosted-mp4"
OTHER_HOST_MP4_PROVIDER = "direct-mp4-other-host"
SITE_UPLOADS_PREFIX = "/wp-content/uploads/"

# Exact-host allowlist for self-hosted MP4 media: the CDN host the public post pages
# serve uploads from. No wildcards. Origin and hosting-alias URLs that the public page
# does not serve (motionographer.com, motionograph.wpengine.com) are not allowlisted;
# see docs/motionographer-video-research.md.
VIDEO_HOSTS = ("s35726.pcdn.co",)

# Media-item status vocabulary for index.json.
STATUS_MEASURED = "measured"
STATUS_FAILED = "failed"
STATUS_PENDING = "pending"
STATUS_NO_VIDEO = "no-video"

LIMITS = [
    "Sampled source-PTS windows only; this is not full-film review.",
    "Numeric display-RGB and cut-candidate proxies are not camera, lens, lighting, editing-intent, or style labels.",
    "No visual style, aesthetic quality, authorship, identity, or creative intent is inferred.",
    "Public availability is not a license; rightsStatus remains review-required.",
    "Downloaded media, frames, thumbnails, and audio are never retained.",
    "Only direct MP4 files on the exact allowlisted site host are measured; Vimeo and YouTube embeds are never attempted.",
    "Post metadata is self-reported by the publisher site and is not independently verified.",
]

_URL = re.compile(r"""(?:https?:)?//[^\s"'<>()\\]+""", re.IGNORECASE)
_IFRAME_SRC = re.compile(r"""<iframe[^>]+?src\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_VIMEO_PLAYER = re.compile(r"^/video/(\d+)")
_YOUTUBE_EMBED = re.compile(r"^/embed/([A-Za-z0-9_-]{6,})")
_YOUTUBE_HOSTS = ("youtube.com", "www.youtube.com", "youtube-nocookie.com",
                  "www.youtube-nocookie.com")


# ---------------------------------------------------------------------------
# polite HTTP for the catalog endpoint
# ---------------------------------------------------------------------------


def _http_get(url: str, *, timeout: float = 45.0) -> tuple[int, dict[str, str], bytes]:
    """GET one URL; return (status, lower-cased headers, body) without raising on 4xx/5xx."""
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            headers = {k.lower(): v for k, v in response.headers.items()}
            return response.status, headers, response.read()
    except HTTPError as error:
        headers = {k.lower(): v for k, v in (error.headers or {}).items()}
        return error.code, headers, b""
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"catalog request failed: {type(error).__name__}") from None


def _retry_after_seconds(headers: dict[str, str]) -> float | None:
    value = headers.get("retry-after")
    if value is None:
        return None
    try:
        seconds = float(value.strip())
    except ValueError:
        return None  # HTTP-date form is not used by this endpoint; fall back to backoff
    return seconds if seconds >= 0 else None


def polite_delay(base: float = DELAY_SECONDS) -> float:
    """At least ``base`` seconds, plus up to ``base`` of jitter."""
    return base + random.uniform(0, base)


def get_with_backoff(
    url: str, *, get: Callable[[str], tuple[int, dict[str, str], bytes]] = _http_get,
    sleep: Callable[[float], None] = time.sleep, attempts: int = 3,
    log: Callable[[str], None] = print,
) -> tuple[dict[str, str], bytes]:
    """Honour 429/Retry-After and 5xx with bounded backoff; stop on repeated throttling."""
    for attempt in range(attempts):
        status, headers, body = get(url)
        if status == 200:
            return headers, body
        if status != 429 and status < 500:
            raise ValueError(f"catalog endpoint returned HTTP {status}")
        wait = _retry_after_seconds(headers)
        if wait is None:
            wait = 30.0 * (2 ** attempt)
        if wait > MAX_RETRY_AFTER_SECONDS:
            raise RuntimeError(
                f"stopping: HTTP {status} asked for a {wait:.0f}s wait; not retrying")
        log(f"HTTP {status} from catalog endpoint; backing off {wait:.0f}s "
            f"(attempt {attempt + 1}/{attempts})")
        if attempt + 1 < attempts:
            sleep(wait)
    raise RuntimeError(
        "stopping: repeated HTTP 429/5xx from the catalog endpoint; not retrying further")


# ---------------------------------------------------------------------------
# media classification (per post, from rendered HTML)
# ---------------------------------------------------------------------------


def _normalise_url(raw: str) -> str:
    url = html.unescape(raw.strip())
    return "https:" + url if url.startswith("//") else url


def _media_slug(provider: str, parsed_path: str, host: str, url: str) -> str:
    if provider == "vimeo":
        match = _VIMEO_PLAYER.match(parsed_path)
        return f"vimeo-{match.group(1)}" if match else "vimeo-embed"
    if provider == "youtube":
        match = _YOUTUBE_EMBED.match(parsed_path)
        return f"youtube-{match.group(1)}" if match else "youtube-embed"
    if provider == "other-embed":
        return safe_slug(f"embed-{host}", limit=80)
    stem = Path(parsed_path).stem or "media"
    return safe_slug(stem, limit=80)


_CACHE_BUSTER = re.compile(r"^_=\d+$")


def _canonical_media_url(url: str) -> tuple[str, bool]:
    """Drop a WordPress ``?_=N`` cache-buster, the only query form normalised here.

    The buster selects no different bytes, so the bare path is the same public
    file. Any other query string is left intact and stays refused by the engine.
    """
    parsed = urlsplit(url)
    if parsed.query and _CACHE_BUSTER.match(parsed.query) and not parsed.fragment:
        return parsed._replace(query="").geturl(), True
    return url, False


def classify_url(url: str, *, video_hosts: tuple[str, ...], iframe: bool) -> dict[str, Any] | None:
    """Classify one URL found in a post, or return None when it is not media."""
    try:
        url, buster_stripped = _canonical_media_url(url)
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return None
    path = parsed.path or ""
    lower_path = path.lower()
    base: dict[str, Any] = {"url": url, "host": host, "path": path,
                            "cacheBusterStripped": buster_stripped}
    if host == "player.vimeo.com" and _VIMEO_PLAYER.match(path):
        provider, reason = "vimeo", "unsupported-vimeo"
    elif host in _YOUTUBE_HOSTS and _YOUTUBE_EMBED.match(path):
        provider, reason = "youtube", "unsupported-youtube"
    elif lower_path.endswith(VIDEO_SUFFIXES):
        if not lower_path.endswith(".mp4"):
            provider, reason = "direct-other-format", "unsupported-format"
        elif parsed.scheme != "https" or port not in (None, 443) or parsed.username:
            provider, reason = OTHER_HOST_MP4_PROVIDER, "unsupported-url-form"
        elif parsed.query or parsed.fragment:
            provider, reason = OTHER_HOST_MP4_PROVIDER, "unsupported-query-string"
        elif host in video_hosts and lower_path.startswith(SITE_UPLOADS_PREFIX):
            provider, reason = SELF_HOSTED_PROVIDER, "eligible-site-mp4"
        else:
            provider, reason = OTHER_HOST_MP4_PROVIDER, "unsupported-host-not-allowlisted"
    elif iframe and host:
        provider, reason = "other-embed", "unsupported-other-embed"
    else:
        return None
    eligible = reason == "eligible-site-mp4"
    base.update({"provider": provider, "eligible": eligible, "reason": reason,
                 "mediaSlug": _media_slug(provider, path, host, url)})
    return base


def classify_media(content_html: str, *, video_hosts: tuple[str, ...] = VIDEO_HOSTS) -> list[dict[str, Any]]:
    """Return one media item per distinct media URL in a post's rendered HTML."""
    iframe_urls = {_normalise_url(match) for match in _IFRAME_SRC.findall(content_html or "")}
    seen: dict[str, dict[str, Any]] = {}
    for raw in _URL.findall(content_html or ""):
        url = _normalise_url(raw)
        if url in seen:
            continue
        item = classify_url(url, video_hosts=video_hosts, iframe=url in iframe_urls)
        if item is not None:
            seen[url] = item
    for url in iframe_urls:
        if url not in seen:
            item = classify_url(url, video_hosts=video_hosts, iframe=True)
            if item is not None:
                seen[url] = item
    items = list(seen.values())
    used: dict[str, int] = {}
    for item in items:
        slug = item["mediaSlug"]
        used[slug] = used.get(slug, 0) + 1
        if used[slug] > 1:
            item["mediaSlug"] = safe_slug(f"{slug}-{used[slug]}", limit=100)
    return items


# ---------------------------------------------------------------------------
# enumeration
# ---------------------------------------------------------------------------


def _post_row(post: dict[str, Any], *, video_hosts: tuple[str, ...]) -> dict[str, Any]:
    title = post.get("title") if isinstance(post.get("title"), dict) else {}
    content = post.get("content") if isinstance(post.get("content"), dict) else {}
    media = classify_media(as_text(content.get("rendered")) or "", video_hosts=video_hosts)
    post_id = as_int(post.get("id"))
    if post_id is None:
        raise ValueError("WordPress post has no numeric id")
    slug = as_text(post.get("slug")) or str(post_id)
    items = []
    for number, item in enumerate(media, start=1):
        items.append({
            "mediaId": f"{post_id}-{number}",
            "mediaSlug": item["mediaSlug"],
            "provider": item["provider"],
            "eligible": item["eligible"],
            "reason": item["reason"],
            "url": item["url"],
            "host": item["host"],
            "path": item["path"],
            "cacheBusterStripped": item["cacheBusterStripped"],
            "pageConfirmed": False,
        })
    return {
        "postId": post_id, "postSlug": slug,
        "title": html.unescape(as_text(title.get("rendered")) or ""),
        "date": as_text(post.get("date")), "link": as_text(post.get("link")),
        "media": items,
    }


def fetch_posts(
    *, get: Callable[[str], tuple[int, dict[str, str], bytes]] = _http_get,
    sleep: Callable[[float], None] = time.sleep,
    limit_pages: int | None = None, video_hosts: tuple[str, ...] = VIDEO_HOSTS,
    log: Callable[[str], None] = print,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Walk every posts page sequentially; return (post rows, header facts)."""
    if limit_pages is not None and (type(limit_pages) is not int or limit_pages < 1):
        raise ValueError("limit must be a positive integer")

    def page_url(page: int) -> str:
        return (f"{POSTS_ENDPOINT}?per_page={PER_PAGE}&page={page}"
                f"&_fields={quote(POSTS_FIELDS, safe=',')}")

    headers, body = get_with_backoff(page_url(1), get=get, sleep=sleep, log=log)
    total_pages = as_int(headers.get("x-wp-totalpages")) or 1
    total = as_int(headers.get("x-wp-total"))
    stop_at = min(total_pages, limit_pages) if limit_pages else total_pages
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = json.loads(body)
        if not isinstance(payload, list):
            raise ValueError("posts response is not a JSON list")
        rows.extend(_post_row(post, video_hosts=video_hosts) for post in payload
                    if isinstance(post, dict))
        log(f"posts page {page}/{total_pages}: {len(payload)} posts (so far {len(rows)})")
        if page >= stop_at:
            break
        page += 1
        sleep(polite_delay())
        headers, body = get_with_backoff(page_url(page), get=get, sleep=sleep, log=log)
    seen: set[int] = set()
    unique = []
    for row in rows:
        if row["postId"] not in seen:
            seen.add(row["postId"])
            unique.append(row)
    return unique, {"totalPosts": total, "totalPages": total_pages,
                    "pagesFetched": page}


def finalize_media(post: dict[str, Any]) -> None:
    """Dedupe a post's media on the canonical URL, then renumber ids and slugs.

    Two raw REST URLs can canonicalise to one file (a cache-buster variant), and a
    page-confirmed URL can coincide with another item's URL, so dedupe runs after
    canonicalisation and confirmation.
    """
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in post["media"]:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        kept.append(item)
    used: dict[str, int] = {}
    for number, item in enumerate(kept, start=1):
        item["mediaId"] = f"{post['postId']}-{number}"
        slug = _media_slug(item["provider"], item["path"], item["host"], item["url"])
        used[slug] = used.get(slug, 0) + 1
        item["mediaSlug"] = slug if used[slug] == 1 else safe_slug(
            f"{slug}-{used[slug]}", limit=100)
    post["media"] = kept


_PAGE_MP4 = re.compile(r"""https?://[^\s"'<>()\\]+?\.mp4(?:\?[^\s"'<>()\\]*)?""", re.IGNORECASE)
MP4_PROVIDERS = (SELF_HOSTED_PROVIDER, OTHER_HOST_MP4_PROVIDER)


def _demote_unconfirmed(post: dict[str, Any], reason: str) -> None:
    """An MP4 the public page does not serve is not measurable, whatever its REST host."""
    for item in post["media"]:
        if item["provider"] in MP4_PROVIDERS and not item["pageConfirmed"] and item["eligible"]:
            item.update({"eligible": False, "reason": reason})


def confirm_rendered_media(
    posts: list[dict[str, Any]], *, video_hosts: tuple[str, ...],
    get: Callable[[str], tuple[int, dict[str, str], bytes]] = _http_get,
    sleep: Callable[[float], None] = time.sleep, log: Callable[[str], None] = print,
) -> dict[str, int]:
    """Confirm REST MP4 candidates against each post's public page, one page at a time.

    The REST ``content.rendered`` field can carry origin URLs (for example
    ``motionographer.com``) while the public page serves the same file path from
    the site's CDN host. Only posts with a direct-MP4 candidate are fetched. A
    REST candidate is re-classified from the page URL when the page serves the
    same ``/wp-content/uploads/`` path; otherwise it keeps its REST
    classification and ``pageConfirmed`` stays false.
    """
    targets = [post for post in posts
               if any(item["provider"] in MP4_PROVIDERS for item in post["media"])]
    stats = {"postsChecked": len(targets), "pagesConfirmed": 0, "pagesUnavailable": 0,
             "itemsConfirmed": 0}
    for position, post in enumerate(targets, start=1):
        sleep(polite_delay())
        try:
            _, body = get_with_backoff(post["link"], get=get, sleep=sleep, log=log)
        except ValueError as error:  # a 4xx on one page: the MP4 cannot be confirmed
            stats["pagesUnavailable"] += 1
            post["pageConfirmation"] = {"status": "page-unavailable", "reason": str(error)}
            _demote_unconfirmed(post, "unsupported-page-unavailable")
            log(f"confirm [{position}/{len(targets)}] post {post['postId']} page unavailable")
            continue
        page_map: dict[str, str] = {}
        page_text = html.unescape(body.decode("utf-8", errors="replace")).replace("\\/", "/")
        for raw in _PAGE_MP4.findall(page_text):
            try:
                key = urlsplit(_canonical_media_url(raw)[0]).path.lower()
            except ValueError:
                continue
            page_map.setdefault(key, raw)
        served = 0
        for item in post["media"]:
            if item["provider"] not in MP4_PROVIDERS:
                continue
            page_url = page_map.get(item["path"].lower())
            if page_url is None:
                continue
            fresh = classify_url(page_url, video_hosts=video_hosts, iframe=False)
            if fresh is None:
                continue
            item.update({"restUrl": item["url"], "url": fresh["url"], "host": fresh["host"],
                         "path": fresh["path"], "provider": fresh["provider"],
                         "eligible": fresh["eligible"], "reason": fresh["reason"],
                         "cacheBusterStripped": fresh["cacheBusterStripped"],
                         "pageConfirmed": True})
            served += 1
        post["pageConfirmation"] = {"status": "confirmed" if served else "no-matching-path"}
        _demote_unconfirmed(post, "unsupported-not-served-on-page")
        stats["itemsConfirmed"] += served
        stats["pagesConfirmed"] += 1 if served else 0
        log(f"confirm [{position}/{len(targets)}] post {post['postId']}: {served} served on page")
    return stats


def build_catalog(posts: list[dict[str, Any]], *, facts: dict[str, Any],
                  video_hosts: tuple[str, ...], retrieved_at: str | None = None,
                  confirmation: dict[str, int] | None = None) -> dict[str, Any]:
    counts: dict[str, int] = {}
    eligible = 0
    for post in posts:
        for item in post["media"]:
            counts[item["provider"]] = counts.get(item["provider"], 0) + 1
            eligible += 1 if item["eligible"] else 0
    return {
        "schemaVersion": CATALOG_SCHEMA,
        "retrievedAt": retrieved_at or utc_now(),
        "endpoint": POSTS_ENDPOINT,
        "siteUrl": SITE,
        "totalPosts": facts.get("totalPosts") or len(posts),
        "totalPages": facts.get("totalPages"),
        "pagesFetched": facts.get("pagesFetched"),
        "postsEnumerated": len(posts),
        "postsWithoutMedia": sum(1 for post in posts if not post["media"]),
        "mediaItems": sum(len(post["media"]) for post in posts),
        "providerCounts": dict(sorted(counts.items())),
        "eligibleMediaItems": eligible,
        "videoHosts": list(video_hosts),
        "renderedPageConfirmation": confirmation or {},
        "posts": posts,
    }


def build_index_rows(catalog: dict[str, Any], *, measured: dict[str, dict[str, Any]],
                     failed: dict[str, str]) -> list[dict[str, Any]]:
    """One row per media item (or one ``no-video`` row per media-less post)."""
    rows: list[dict[str, Any]] = []
    for post in catalog["posts"]:
        base = {"postId": post["postId"], "postSlug": post["postSlug"], "link": post["link"]}
        if not post["media"]:
            rows.append({**base, "mediaId": None, "mediaSlug": None,
                         "provider": "none", "status": STATUS_NO_VIDEO, "reason": "no-video"})
            continue
        for item in post["media"]:
            row = {**base, "mediaId": item["mediaId"], "mediaSlug": item["mediaSlug"],
                   "provider": item["provider"], "reason": item["reason"]}
            if not item["eligible"]:
                row["status"] = item["reason"]
            elif item["mediaId"] in measured:
                row.update({"status": STATUS_MEASURED, **measured[item["mediaId"]]})
            elif item["mediaId"] in failed:
                row.update({"status": STATUS_FAILED, "reason": failed[item["mediaId"]]})
            else:
                row["status"] = STATUS_PENDING
            rows.append(row)
    return rows


def build_index(catalog: dict[str, Any], *, catalog_sha: str,
                measured: dict[str, dict[str, Any]] | None = None,
                failed: dict[str, str] | None = None,
                generated_at: str | None = None) -> dict[str, Any]:
    rows = build_index_rows(catalog, measured=measured or {}, failed=failed or {})
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    provider_counts: dict[str, int] = {}
    for row in rows:
        if row["mediaId"] is not None:
            provider_counts[row["provider"]] = provider_counts.get(row["provider"], 0) + 1
    return {
        "schemaVersion": INDEX_SCHEMA,
        "generatedAt": generated_at or utc_now(),
        "catalogSha256": catalog_sha,
        "counts": dict(sorted(status_counts.items())),
        "providerCounts": dict(sorted(provider_counts.items())),
        "rows": rows,
    }


def run_enumerate(
    *, out_dir: Path, limit_pages: int | None = None, log: Callable[[str], None] = print,
    get: Callable[[str], tuple[int, dict[str, str], bytes]] = _http_get,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    posts, facts = fetch_posts(get=get, sleep=sleep, limit_pages=limit_pages,
                               video_hosts=VIDEO_HOSTS, log=log)
    confirmation = confirm_rendered_media(posts, video_hosts=VIDEO_HOSTS, get=get,
                                          sleep=sleep, log=log)
    for post in posts:
        finalize_media(post)
    catalog = build_catalog(posts, facts=facts, video_hosts=VIDEO_HOSTS,
                            confirmation=confirmation)
    catalog_path = out_dir / "catalog.json"
    write_json_atomic(catalog_path, catalog)
    index = build_index(catalog, catalog_sha=sha256_file(catalog_path))
    write_json_atomic(out_dir / "index.json", index)
    log(f"enumerated posts={catalog['postsEnumerated']} media={catalog['mediaItems']} "
        f"eligible={catalog['eligibleMediaItems']} providers={catalog['providerCounts']}")
    return 0


# ---------------------------------------------------------------------------
# measurement
# ---------------------------------------------------------------------------


def _load_catalog(path: Path) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or catalog.get("schemaVersion") != CATALOG_SCHEMA:
        raise ValueError("unsupported catalog schema")
    if not isinstance(catalog.get("posts"), list):
        raise ValueError("catalog has no post list")
    return catalog


def eligible_items(catalog: dict[str, Any], *, limit: int | None = None) -> list[dict[str, Any]]:
    """Eligible self-hosted MP4 items in catalog order, carrying their post fields."""
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a non-negative integer")
    items: list[dict[str, Any]] = []
    for post in catalog["posts"]:
        for media in post["media"]:
            if media["eligible"]:
                items.append({**media, "postId": post["postId"], "postSlug": post["postSlug"],
                              "title": post["title"], "date": post["date"],
                              "link": post["link"]})
    return items[:limit] if limit is not None else items


def _resume_path(out_dir: Path, item: dict[str, Any]) -> Path:
    return out_dir / "videos" / f"{safe_slug(item['postSlug'])}--{safe_slug(item['mediaSlug'])}.json"


def resume_matches(record_path: Path, media_id: object) -> bool:
    return _resume_matches(record_path, media_id, field="mediaId")


def build_video_record(item: dict[str, Any], *, source: dict[str, Any],
                       coverage: dict[str, Any], windows: list[dict[str, Any]],
                       method: str, rights_note: str) -> dict[str, Any]:
    evidence = build_video_evidence(
        source=source, coverage=coverage, windows=windows, method=method,
        provider=SELF_HOSTED_PROVIDER, video_url=item["url"],
        rights_basis=RIGHTS_BASIS, rights_note=rights_note,
        schema_version=VIDEO_SCHEMA, evidence_status=EVIDENCE_STATUS,
        limits=LIMITS, rights_status=RIGHTS_STATUS)
    return {"schemaVersion": VIDEO_SCHEMA, "mediaId": item["mediaId"],
            "mediaSlug": item["mediaSlug"], "postId": item["postId"],
            "postSlug": item["postSlug"], "postLink": item["link"],
            "title": item["title"], "date": item["date"], **evidence}


def _summary_row(record: dict[str, Any]) -> dict[str, Any]:
    summary = record.get("summary") or {}
    source = record.get("source") or {}
    coverage = record.get("coverage") or {}
    return {
        "mediaId": record.get("mediaId"), "postId": record.get("postId"),
        "postSlug": record.get("postSlug"), "mediaSlug": record.get("mediaSlug"),
        "provider": SELF_HOSTED_PROVIDER, "status": STATUS_MEASURED,
        "durationSeconds": source.get("durationSeconds"),
        "resolution": source.get("resolution"),
        "sourceSha256": source.get("mediaSha256"),
        "windowCount": coverage.get("windowsMeasured"),
        "cutCandidateRatePerMinute": summary.get("cutCandidateRatePerMinute"),
        "meanDisplayLuma": summary.get("meanDisplayLuma"),
        "meanSaturation": summary.get("meanSaturation"),
        "recordPath": (Path("videos") / f"{record.get('postSlug')}--{record.get('mediaSlug')}.json").as_posix(),
    }


def collect_one(
    item: dict[str, Any], out_dir: Path, *, windows: int = 4, window_seconds: int = 10,
    max_duration_seconds: float = 600.0, max_file_bytes: int = 400 * 1024 * 1024,
    rights_note: str = DEFAULT_RIGHTS_NOTE, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    download_timeout: float = 360.0,
) -> dict[str, Any]:
    """Download -> measure -> write record; the media directory is always deleted."""
    url = allowlisted_video_url(item.get("url"), allowed_hosts=VIDEO_HOSTS)
    if item.get("provider") != SELF_HOSTED_PROVIDER or item.get("eligible") is not True:
        raise ValueError("media item is not eligible for measurement")
    with tempfile.TemporaryDirectory(prefix="kumiki-motionographer-") as scratch:
        # Hard guarantee: the TemporaryDirectory removes every byte on exit.
        media_dir = Path(scratch) / "media"
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
        record = build_video_record(item, source=source, coverage=coverage, windows=measured,
                                    method=method, rights_note=rights_note)
    write_json_atomic(_resume_path(out_dir, item), record)
    return record


def run_measure(
    catalog_path: Path, *, out_dir: Path, limit: int | None = None, resume: bool = True,
    retry_failed: bool = False, acknowledge_rights: bool = False,
    delay_seconds: float = DELAY_SECONDS, log: Callable[[str], None] = print,
    **video_options: Any,
) -> int:
    if acknowledge_rights is not True:
        raise ValueError(
            "explicit --acknowledge-rights attestation is required: public "
            "availability is not a license, and each downloaded file is deleted "
            "after numeric measurement")
    catalog_sha = sha256_file(Path(catalog_path))
    catalog = _load_catalog(Path(catalog_path))
    items = eligible_items(catalog, limit=limit)
    (out_dir / "videos").mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.json"
    measured: dict[str, dict[str, Any]] = {}
    failed: dict[str, str] = {}
    prior_failed: set[str] = set()
    for existing in sorted((out_dir / "videos").glob("*.json")):
        try:
            payload = json.loads(existing.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict) and payload.get("schemaVersion") == VIDEO_SCHEMA:
            measured[str(payload.get("mediaId"))] = _summary_row(payload)
    if not retry_failed and index_path.is_file():
        # A media item that already failed is not re-downloaded on every batch.
        prior = json.loads(index_path.read_text(encoding="utf-8"))
        for row in prior.get("rows", []):
            if row.get("status") == STATUS_FAILED and row.get("mediaId"):
                prior_failed.add(str(row["mediaId"]))
                failed[str(row["mediaId"])] = str(row.get("reason") or "failed")

    def skip_reason(item: dict[str, Any]) -> str | None:
        if item["mediaId"] in prior_failed:
            return "previous-failure-recorded"
        if not resume:
            return None
        return ("resume-existing-record"
                if resume_matches(_resume_path(out_dir, item), item["mediaId"]) else None)

    def run_one(item: dict[str, Any]) -> dict[str, Any]:
        return collect_one(item, out_dir, **video_options)

    def index_for(records: list[dict[str, Any]], skips: list[dict[str, Any]],
                  failures: list[dict[str, Any]]) -> dict[str, Any]:
        for row in records:
            measured[str(row["mediaId"])] = row
        for row in failures:
            failed[str(row["mediaId"])] = str(row["reason"])
        return build_index(catalog, catalog_sha=catalog_sha, measured=measured,
                           failed=failed, generated_at=utc_now())

    def report(position: int, total: int, status: str, label: str, text: str) -> None:
        print(f"[{position}/{total}] {status} {label} {text}", flush=True)

    outcome = run_batch(
        items, run_one=run_one, index_path=index_path, build_index=index_for,
        summary_row=_summary_row,
        skip_row=lambda item, reason: {"mediaId": item["mediaId"], "reason": reason},
        describe=lambda item: f"{item['postSlug']}--{item['mediaSlug']}",
        failure_row=lambda item, reason: {"mediaId": item["mediaId"], "reason": reason},
        skip_reason=skip_reason,
        error_text=lambda error: re.sub(
            r"/[^\s:'\"]*kumiki-motionographer-[^\s:'\"]*", "[scratch]",
            safe_error(error, redact=(str(out_dir),))),
        progress=report, jobs=1, delay_seconds=delay_seconds)
    log(f"measured={outcome.measured} skipped={outcome.skipped} failed={outcome.failed} "
        f"attempted={outcome.attempted} elapsed={outcome.elapsed_seconds:.1f}s "
        f"index={index_path}")
    log("all downloaded media was deleted; only numeric evidence and metadata remain")
    return 1 if outcome.attempted and not outcome.measured and outcome.failed else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ephemeral Motionographer MP4 video research: enumerate posts, "
                    "then measure each eligible self-hosted MP4 one at a time.")
    sub = parser.add_subparsers(dest="command", required=True)
    enumerate_cmd = sub.add_parser(
        "enumerate", help="walk the posts API, classify media, write catalog.json and index.json")
    enumerate_cmd.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    enumerate_cmd.add_argument(
        "--limit", type=int, default=None,
        help="trial run: fetch at most N pages of posts (default: all pages)")
    measure = sub.add_parser(
        "measure", help="download, measure, and delete eligible MP4s one at a time")
    measure.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    measure.add_argument("--catalog", type=Path, default=None,
                         help="catalog JSON (default: <out-dir>/catalog.json)")
    measure.add_argument(
        "--limit", type=int, default=None,
        help="trial run: measure at most N eligible media items")
    measure.add_argument("--windows", type=int, default=4)
    measure.add_argument("--window-seconds", type=int, default=10)
    measure.add_argument("--max-duration-seconds", type=float, default=600.0)
    measure.add_argument("--max-file-bytes", type=int, default=400 * 1024 * 1024)
    measure.add_argument("--acknowledge-rights", action="store_true")
    measure.add_argument("--rights-note", default=DEFAULT_RIGHTS_NOTE)
    group = measure.add_mutually_exclusive_group()
    group.add_argument("--resume", dest="resume", action="store_true", default=True)
    group.add_argument("--refresh", dest="resume", action="store_false")
    measure.add_argument("--retry-failed", action="store_true",
                         help="re-attempt media items recorded as failed in index.json")
    measure.add_argument("--delay-seconds", type=float, default=DELAY_SECONDS,
                         help="politeness pause (plus equal jitter) between media items")
    measure.add_argument("--ffmpeg", default="ffmpeg")
    measure.add_argument("--ffprobe", default="ffprobe")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "enumerate":
            return run_enumerate(out_dir=args.out_dir, limit_pages=args.limit)
        if not args.acknowledge_rights:
            parser.error(
                "--acknowledge-rights is required: public availability is not a "
                "license and downloaded media is deleted after measurement")
        catalog = args.catalog or (args.out_dir / "catalog.json")
        return run_measure(
            catalog, out_dir=args.out_dir, limit=args.limit, resume=args.resume,
            retry_failed=args.retry_failed, acknowledge_rights=args.acknowledge_rights,
            delay_seconds=args.delay_seconds, windows=args.windows,
            window_seconds=args.window_seconds,
            max_duration_seconds=args.max_duration_seconds,
            max_file_bytes=args.max_file_bytes, rights_note=args.rights_note,
            ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    sys.exit(main())
