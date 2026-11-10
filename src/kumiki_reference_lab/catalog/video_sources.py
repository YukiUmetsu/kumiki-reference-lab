"""Provider-neutral, offline reference-video discovery; never fetches media.

All watch URLs are browser-facing pages. Only an independently obtained,
authorized local media file may be passed to the numeric analysis pipeline.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from kumiki_reference_lab.catalog.popular_videos import load_popular_videos


SCHEMA_VERSION = "kumiki.video-source-index.v1"
WHATSHIPS_SCHEMA = "kumiki.whatships-metadata-snapshot.v1"
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_X_STATUS = re.compile(r"/[A-Za-z0-9_]+/status/[0-9]+\Z")
_WORDS = re.compile(r"[\w]+", re.UNICODE)
_CATEGORIES = {
    "AI": "ai", "Developer tools": "developer-tools", "Design": "design",
    "Motion": "motion", "Productivity": "productivity", "Consumer": "consumer",
    "Hardware": "hardware", "Other": "other",
}
_RIGHTS = {"usage": "inspiration-only", "redistributionAuthorized": False}
_PROVIDERS = {"all", "youtube", "whatships"}


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON property: {key}")
        result[key] = value
    return result


def _load_snapshot(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("What Ships snapshot cannot be a symlink")
    if not path.is_file():
        raise ValueError(f"What Ships snapshot must be a regular file: {path}")
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("What Ships snapshot exceeds 8 MiB")
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid What Ships JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("schemaVersion") != WHATSHIPS_SCHEMA:
        raise ValueError("unsupported What Ships snapshot schema")
    if not isinstance(data.get("source"), dict) or data["source"].get("indexUrl") != "https://whatships.com/search-index.json":
        raise ValueError("What Ships snapshot must cite the official index")
    retrieved = data.get("retrievedOn")
    try:
        date.fromisoformat(retrieved)
    except (TypeError, ValueError):
        raise ValueError("What Ships retrievedOn must be an ISO date") from None
    if not isinstance(data.get("videos"), list) or not data["videos"] or len(data["videos"]) > 10_000:
        raise ValueError("What Ships videos must contain 1–10000 entries")
    return data


def _page_url(url: Any, *, host: str, path: str) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname == host and
                parsed.username is None and parsed.password is None and
                parsed.port in (None, 443) and parsed.path == path and
                not parsed.query and not parsed.fragment)
    except ValueError:
        return False


def _valid_x_post(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname == "x.com" and
                parsed.username is None and parsed.password is None and
                parsed.port in (None, 443) and bool(_X_STATUS.fullmatch(parsed.path))
                and not parsed.query and not parsed.fragment)
    except ValueError:
        return False


def _iso_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None
    except ValueError:
        return False


def _from_whatships(data: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    slugs: set[str] = set()
    for index, raw in enumerate(data["videos"]):
        label = f"What Ships videos[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{label} must be an object")
        slug = raw.get("slug")
        if not isinstance(slug, str) or not _SLUG.fullmatch(slug) or slug in slugs:
            raise ValueError(f"{label} has an invalid or duplicate slug")
        slugs.add(slug)
        watch_url = f"https://whatships.com/videos/{slug}/"
        if not _page_url(raw.get("directoryUrl"), host="whatships.com", path=f"/videos/{slug}/"):
            raise ValueError(f"{label} has an unsafe watch URL")
        if not isinstance(raw.get("title"), str) or not raw["title"].strip():
            raise ValueError(f"{label} requires a title")
        if not isinstance(raw.get("indexMetadata"), str) or " · " not in raw["indexMetadata"]:
            raise ValueError(f"{label} lacks category provenance")
        creator, category_label = raw["indexMetadata"].rsplit(" · ", 1)
        if not creator.strip() or category_label not in _CATEGORIES:
            raise ValueError(f"{label} has an unsupported category")
        detail = raw.get("detail")
        entry = {
            "id": f"whatships:{slug}", "provider": "whatships", "title": raw["title"],
            "creator": creator, "category": _CATEGORIES[category_label],
            "watchUrl": watch_url, "originalUrl": None, "publishedOn": None,
            "durationSeconds": None, "views": None, "viewsCapturedAt": None,
            "tags": [], "description": "", "evidenceStatus": "index-only",
            "reviewStatus": "metadata-only-not-frame-reviewed", "rights": dict(_RIGHTS),
        }
        if detail is not None:
            if not isinstance(detail, dict) or detail.get("slug") != slug:
                raise ValueError(f"{label} detail slug does not match index")
            if not _page_url(detail.get("url"), host="whatships.com", path=f"/videos/{slug}/"):
                raise ValueError(f"{label} detail URL is unsafe")
            if not _valid_x_post(detail.get("tweetUrl")):
                raise ValueError(f"{label} original X URL is unsafe")
            if detail.get("category") != _CATEGORIES[category_label]:
                raise ValueError(f"{label} detail category differs from index")
            if not _iso_timestamp(detail.get("publishedAt")):
                raise ValueError(f"{label} needs a timezone-qualified publication timestamp")
            duration = detail.get("durationSeconds")
            views = detail.get("views")
            captured = detail.get("viewsCapturedAt")
            if type(duration) is not int or duration < 0:
                raise ValueError(f"{label} duration must be nonnegative seconds")
            if views is not None and (type(views) is not int or views < 0):
                raise ValueError(f"{label} view count must be nonnegative or null")
            if views is not None and captured is None:
                raise ValueError(f"{label} view count requires a source snapshot timestamp")
            if captured is not None and not _iso_timestamp(captured):
                raise ValueError(f"{label} view snapshot timestamp is invalid")
            tags = detail.get("tags")
            if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
                raise ValueError(f"{label} tags must be strings")
            if not isinstance(detail.get("description"), str):
                raise ValueError(f"{label} description must be text")
            if not isinstance(detail.get("title"), str) or not detail["title"].strip():
                raise ValueError(f"{label} detail title must be text")
            entry.update({
                "title": detail["title"], "originalUrl": detail["tweetUrl"],
                "publishedOn": detail["publishedAt"][:10], "durationSeconds": duration,
                "views": views, "viewsCapturedAt": captured, "tags": tags,
                "description": detail["description"], "evidenceStatus": "detail-snapshot",
            })
        entries.append(entry)
    return entries


def _from_youtube(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "id": f"youtube:{item['youtubeId']}", "provider": "youtube",
        "title": item["title"], "creator": item["creator"], "category": "editorial-reference",
        "watchUrl": item["videoUrl"], "originalUrl": item["videoUrl"],
        "publishedOn": item["publishedOn"], "durationSeconds": None,
        "views": item["viewEvidence"]["viewCount"],
        "viewsCapturedAt": item["viewEvidence"]["sourceSnapshotOn"],
        "tags": item["techniqueTags"], "description": item["studyQuestion"],
        "evidenceStatus": "reported-view-source", "reviewStatus": "metadata-only-not-frame-reviewed",
        "rights": dict(_RIGHTS),
    } for item in data["entries"]]


def load_source_references(youtube_root: Path, whatships_path: Path) -> dict[str, Any]:
    """Validate and combine metadata; perform no HTTP or video downloads."""
    youtube = load_popular_videos(youtube_root)
    whatships = _load_snapshot(whatships_path)
    entries = _from_youtube(youtube) + _from_whatships(whatships)
    return {"schemaVersion": SCHEMA_VERSION, "retrievedOn": whatships["retrievedOn"],
            "entries": entries}


def search_source_references(collection: dict[str, Any], query: str = "", *,
                             provider: str = "all", min_views: int = 0,
                             limit: int = 20) -> list[dict[str, Any]]:
    if not isinstance(provider, str) or provider not in _PROVIDERS:
        raise ValueError("provider must be all, youtube or whatships")
    if not isinstance(query, str):
        raise ValueError("query must be text")
    if type(min_views) is not int or min_views < 0:
        raise ValueError("minimum views must be nonnegative")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    tokens = set(_WORDS.findall(query.casefold()))
    result = []
    for item in collection["entries"]:
        if provider != "all" and item["provider"] != provider:
            continue
        views = item["views"]
        if min_views and (views is None or views < min_views):
            continue
        fields = ((item["title"], 3), (item["creator"], 1), (item["category"], 2),
                  (" ".join(item["tags"]).replace("-", " "), 4), (item["description"], 1))
        score = sum(weight * len(tokens & set(_WORDS.findall(value.casefold())))
                    for value, weight in fields)
        if tokens and score == 0:
            continue
        result.append((score, views is not None, views or 0, item["id"], item))
    result.sort(key=lambda row: (-row[0], -row[1], -row[2], row[3]))
    return [row[-1] for row in result[:limit]]


def get_source_reference(collection: dict[str, Any], identity: str) -> dict[str, Any]:
    for item in collection["entries"]:
        if item["id"] == identity:
            return item
    raise ValueError(f"unknown source reference: {identity}")
