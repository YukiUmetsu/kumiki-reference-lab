"""Bounded Directors' Library *metadata* import; never downloads film media.

The public archive uses schema.org ItemList, and each film page exposes a
VideoObject. Embedded players are recorded as identifiers, not acquired.
There is no rights grant for downloading and analyzing the films here.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from kumiki_reference_lab.catalog.video_sources import _unique_keys


SCHEMA = "kumiki.directors-library-metadata.v1"
ARCHIVE = "https://directorslibrary.com/videos/latest/"
TERMS = "https://directorslibrary.com/cookies-legal/"
_FILM_PATH = re.compile(
    r"/([0-9]{4})/latest/(film-tv|shorts|music-videos|campaigns)/"
    r"(?:[a-z0-9-]+/)?[a-z0-9-]+/\Z"
)
_VIMEO = re.compile(r"/video/[0-9]+\Z")
_YOUTUBE = re.compile(r"/embed/[A-Za-z0-9_-]{6,20}\Z")
_MAX_PAGE_BYTES = 2 * 1024 * 1024
_MAX_ENTRIES = 75


class _JsonLdScripts(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._in_script = False
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self._in_script = True
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_script:
            self.blocks.append("".join(self._text))
            self._in_script = False


def _structured_objects(markup: str) -> list[dict[str, Any]]:
    if not isinstance(markup, str) or len(markup.encode("utf-8")) > _MAX_PAGE_BYTES:
        raise ValueError("film page HTML missing or exceeds size budget")
    parser = _JsonLdScripts()
    parser.feed(markup)
    objects = []
    for block in parser.blocks:
        try:
            node = json.loads(block, object_pairs_hook=_unique_keys)
        except (UnicodeError, ValueError) as exc:
            raise ValueError("invalid schema.org JSON-LD") from exc
        if isinstance(node, dict):
            objects.extend(value for value in node.get("@graph", [])
                           if isinstance(value, dict))
            objects.append(node)
    return objects


def _safe_film_url(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url)
        return (parts.scheme == "https" and parts.hostname == "directorslibrary.com" and
                parts.username is None and parts.password is None and
                parts.port in (None, 443) and not parts.query and
                not parts.fragment and bool(_FILM_PATH.fullmatch(parts.path)))
    except ValueError:
        return False


def _archive_url(page: int) -> str:
    return ARCHIVE if page == 1 else f"{ARCHIVE}page/{page}/"


def _player(url: Any) -> tuple[str, str | None]:
    if not isinstance(url, str):
        return "unknown", None
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.username is not None or
                parts.password is not None or parts.port not in (None, 443) or
                parts.fragment):
            return "unknown", None
        if parts.hostname == "player.vimeo.com" and _VIMEO.fullmatch(parts.path):
            return "vimeo", "https://player.vimeo.com" + parts.path
        if parts.hostname in ("www.youtube.com", "www.youtube-nocookie.com") and _YOUTUBE.fullmatch(parts.path):
            return "youtube", f"https://{parts.hostname}{parts.path}"
    except ValueError:
        pass
    return "unknown", None


def parse_listing(markup: str, listing_url: str) -> list[str]:
    page_number = next((i for i in range(1, 6) if _archive_url(i) == listing_url), None)
    if page_number is None:
        raise ValueError("unsupported Directors' Library archive URL")
    candidates = [obj for obj in _structured_objects(markup)
                  if obj.get("@type") == "ItemList" and obj.get("url") == listing_url]
    if len(candidates) != 1:
        raise ValueError("expected one schema.org ItemList for the requested archive")
    items = candidates[0].get("itemListElement")
    if not isinstance(items, list) or not 1 <= len(items) <= 25:
        raise ValueError("missing or unexpectedly large film archive")
    urls: list[str] = []
    for ordinal, element in enumerate(items, (page_number - 1) * 15 + 1):
        if not isinstance(element, dict) or element.get("position") != ordinal:
            raise ValueError("invalid film archive item order")
        item = element.get("item")
        url = item.get("url") if isinstance(item, dict) else None
        if not _safe_film_url(url):
            raise ValueError("unsafe film page URL in archive")
        if url in urls:
            raise ValueError("duplicate film page in archive")
        urls.append(url)
    if candidates[0].get("numberOfItems") != len(urls):
        raise ValueError("film archive count differs from entries")
    return urls


def parse_film(markup: str, film_url: str) -> dict[str, Any]:
    if not _safe_film_url(film_url):
        raise ValueError("unsafe Directors' Library film page URL")
    candidates = [obj for obj in _structured_objects(markup)
                  if obj.get("@type") == "VideoObject" and obj.get("url") == film_url]
    if len(candidates) != 1:
        raise ValueError("film page lacks its matching VideoObject")
    video = candidates[0]
    title = video.get("name")
    if not isinstance(title, str) or not title.strip() or len(title) > 300:
        raise ValueError("film title missing or excessive")
    published = video.get("uploadDate")
    if not isinstance(published, str):
        raise ValueError("film has no publication provenance")
    try:
        timestamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("timezone missing")
    except ValueError as exc:
        raise ValueError("invalid film upload date") from exc
    director_field = video.get("director", [])
    if isinstance(director_field, dict):
        director_field = [director_field]
    if not isinstance(director_field, list) or len(director_field) > 20:
        raise ValueError("unexpected film director metadata")
    directors = []
    for row in director_field:
        name = row.get("name") if isinstance(row, dict) else None
        if not isinstance(name, str) or not name.strip() or len(name) > 180:
            raise ValueError("invalid director credit")
        directors.append(name.strip())
    parts = urlsplit(film_url).path.strip("/").split("/")
    provider, player = _player(video.get("embedUrl"))
    return {
        "id": "directors-library:" + ":".join([parts[0], *parts[2:]]),
        "title": title.strip(), "directors": directors,
        "category": parts[2], "subcategory": parts[3] if len(parts) == 5 else None,
        "watchUrl": film_url, "playerProvider": provider, "playerUrl": player,
        "sitePublishedOn": timestamp.date().isoformat(),
        "durationSeconds": None, "viewCount": None,
        "videoAnalysisStatus": "not-performed", "rightsStatus": "permission-required",
    }


def collect_latest(fetch: Callable[[str], str], *, pages: int, retrieved_on: str) -> dict[str, Any]:
    if type(pages) is not int or not 1 <= pages <= 5:
        raise ValueError("archive pages must be 1–5")
    try:
        date.fromisoformat(retrieved_on)
    except (TypeError, ValueError):
        raise ValueError("retrieved_on must be ISO YYYY-MM-DD") from None
    seen: set[str] = set()
    videos = []
    for page in range(1, pages + 1):
        url = _archive_url(page)
        for film_url in parse_listing(fetch(url), url):
            if film_url in seen:
                raise ValueError("duplicate film URL across pages")
            seen.add(film_url)
            videos.append(parse_film(fetch(film_url), film_url))
    if len(videos) > _MAX_ENTRIES:
        raise ValueError("too many films in a single snapshot")
    snapshot = {
        "schemaVersion": SCHEMA, "retrievedOn": retrieved_on,
        "source": {"publisher": "Directors' Library", "archiveUrl": ARCHIVE,
                   "termsUrl": TERMS, "pagesCrawled": pages},
        "methodology": "Public schema.org metadata only. Player references are not media licenses. "
                       "No video bytes, frames, audio, editorial descriptions or technique claims were collected.",
        "totals": {"videoPagesInspected": len(videos), "videoFilesDownloaded": 0,
                   "videosMeasured": 0},
        "videos": videos,
    }
    validate_snapshot(snapshot)
    return snapshot


def validate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict) or snapshot.get("schemaVersion") != SCHEMA:
        raise ValueError("unsupported Directors' Library snapshot")
    if not isinstance(snapshot.get("retrievedOn"), str):
        raise ValueError("snapshot lacks retrieval date")
    try:
        date.fromisoformat(snapshot["retrievedOn"])
    except ValueError:
        raise ValueError("invalid snapshot date") from None
    source = snapshot.get("source")
    if (not isinstance(source, dict) or source.get("archiveUrl") != ARCHIVE or
            source.get("termsUrl") != TERMS or
            type(source.get("pagesCrawled")) is not int or not 1 <= source["pagesCrawled"] <= 5):
        raise ValueError("unsupported source provenance")
    videos = snapshot.get("videos")
    if not isinstance(videos, list) or not 1 <= len(videos) <= _MAX_ENTRIES:
        raise ValueError("invalid video list")
    seen = set()
    expected_keys = {"id", "title", "directors", "category", "subcategory", "watchUrl",
                     "playerProvider", "playerUrl", "sitePublishedOn", "durationSeconds", "viewCount",
                     "videoAnalysisStatus", "rightsStatus"}
    for row in videos:
        if not isinstance(row, dict) or set(row) != expected_keys:
            raise ValueError("unexpected video metadata fields")
        if not _safe_film_url(row["watchUrl"]):
            raise ValueError("unsafe film URL")
        parts = urlsplit(row["watchUrl"]).path.strip("/").split("/")
        if (row["id"] != "directors-library:" + ":".join([parts[0], *parts[2:]]) or
                row["id"] in seen or row["category"] != parts[2] or
                row["subcategory"] != (parts[3] if len(parts) == 5 else None)):
            raise ValueError("duplicate or mismatched film identity")
        seen.add(row["id"])
        if not isinstance(row["title"], str) or not row["title"].strip():
            raise ValueError("invalid film title")
        if (not isinstance(row["directors"], list) or
                any(not isinstance(name, str) or not name.strip() for name in row["directors"])):
            raise ValueError("invalid director credits")
        if (row["playerProvider"], row["playerUrl"]) != _player(row["playerUrl"]):
            raise ValueError("unsafe or mismatched player")
        try:
            date.fromisoformat(row["sitePublishedOn"])
        except (TypeError, ValueError):
            raise ValueError("invalid publication date") from None
        if (row["durationSeconds"] is not None or row["viewCount"] is not None or
                row["videoAnalysisStatus"] != "not-performed" or
                row["rightsStatus"] != "permission-required"):
            raise ValueError("unsupported claim of measurement or download rights")
    totals = snapshot.get("totals")
    if (not isinstance(totals, dict) or totals != {
            "videoPagesInspected": len(videos), "videoFilesDownloaded": 0, "videosMeasured": 0}):
        raise ValueError("snapshot totals do not match metadata-only records")
    return snapshot


def summarize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(snapshot)
    return {
        "retrievedOn": snapshot["retrievedOn"],
        "listedVideos": len(snapshot["videos"]), "analyzedVideos": 0,
        "downloadedVideos": 0,
        "categories": dict(sorted(Counter(row["category"] for row in snapshot["videos"]).items())),
        "players": dict(sorted(Counter(row["playerProvider"] for row in snapshot["videos"]).items())),
    }


def load_snapshot(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("snapshot must be a regular JSON file no larger than 2 MiB")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("invalid Directors' Library JSON snapshot") from exc
    return validate_snapshot(raw)


class _RefuseRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Directors' Library page redirected unexpectedly")


def fetch_public_page(url: str, *, timeout: int = 20) -> str:
    """Only fetch explicit public archive/film pages, never player or media URLs."""
    if not (_safe_film_url(url) or url in {_archive_url(i) for i in range(1, 6)}):
        raise ValueError("non-allowlisted Directors' Library page")
    if type(timeout) is not int or not 5 <= timeout <= 60:
        raise ValueError("timeout must be 5–60 seconds")
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; KumikiReferenceLab/0.1; metadata research)",
        "Accept": "text/html",
    })
    try:
        with build_opener(_RefuseRedirects()).open(req, timeout=timeout) as response:
            if response.status != 200 or "html" not in response.headers.get("Content-Type", ""):
                raise ValueError("not a public HTML page")
            payload = response.read(_MAX_PAGE_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise ValueError(f"cannot fetch public metadata page: {url}") from exc
    if len(payload) > _MAX_PAGE_BYTES:
        raise ValueError("metadata page exceeds size budget")
    try:
        return payload.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("metadata page is not UTF-8") from exc
