"""Offline, provenance-aware discovery of popular reference-video metadata.

View counts are attributed *source observations*, not live measurements or
unique-viewer estimates. Loading this collection never requests remote media.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


SCHEMA_VERSION = "kumiki.popular-video-references.v1"
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]+$")
_TAG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_SOURCE_KINDS = {"youtube-search-index", "third-party-video-statistics"}


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"duplicate JSON property: {name}")
        result[name] = value
    return result


def _https_url(value: Any) -> bool:
    """Reject ambiguous hosts, credentials and malformed authority strings."""
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and bool(parsed.hostname) and
                parsed.username is None and parsed.password is None and
                parsed.port in (None, 443) and not parsed.fragment)
    except ValueError:
        return False


def validate_popular_videos(data: Any) -> list[str]:
    """Check the v1 contract and cross-entry invariants without dependencies."""
    errors: list[str] = []

    def obj(value: Any, path: str, required: set[str]) -> dict[str, Any]:
        if not isinstance(value, dict):
            errors.append(f"{path} must be an object")
            return {}
        for key in sorted(required - value.keys()):
            errors.append(f"{path}.{key} is required")
        for key in sorted(value.keys() - required):
            errors.append(f"{path}.{key} is unknown")
        return value

    def nonempty(value: Any, path: str) -> None:
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path} must be nonempty text")

    def iso_date(value: Any, path: str) -> bool:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            errors.append(f"{path} must be an ISO date")
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            errors.append(f"{path} must be a valid date")
            return False
        return True

    data = obj(data, "collection", {"schemaVersion", "retrievedOn", "methodology", "entries"})
    if data.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("collection.schemaVersion is unsupported")
    retrieved = data.get("retrievedOn")
    iso_date(retrieved, "collection.retrievedOn")
    nonempty(data.get("methodology"), "collection.methodology")
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("collection.entries must be a nonempty list")
        return errors

    seen_ids: set[str] = set()
    seen_youtube_ids: set[str] = set()
    for position, raw in enumerate(entries):
        path = f"entries[{position}]"
        entry = obj(raw, path, {"id", "title", "creator", "publishedOn", "youtubeId",
                                "videoUrl", "viewEvidence", "techniqueTags",
                                "studyQuestion", "reviewStatus", "rights"})
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier):
            errors.append(f"{path}.id must be a lowercase dashed identifier")
        elif identifier in seen_ids:
            errors.append(f"{path}.id is duplicated")
        else:
            seen_ids.add(identifier)
        for name in ("title", "creator", "studyQuestion"):
            nonempty(entry.get(name), f"{path}.{name}")
        iso_date(entry.get("publishedOn"), f"{path}.publishedOn")
        youtube_id = entry.get("youtubeId")
        if not isinstance(youtube_id, str) or not _VIDEO_ID.fullmatch(youtube_id):
            errors.append(f"{path}.youtubeId is invalid")
        elif youtube_id in seen_youtube_ids:
            errors.append(f"{path}.youtubeId is duplicated")
        else:
            seen_youtube_ids.add(youtube_id)
        video_url = entry.get("videoUrl")
        if not _https_url(video_url):
            errors.append(f"{path}.videoUrl must be a YouTube watch URL")
        else:
            parsed = urlsplit(video_url)
            if (parsed.scheme != "https" or parsed.hostname not in {"youtube.com", "www.youtube.com"}
                    or parsed.path != "/watch" or parse_qs(parsed.query) != {"v": [youtube_id]}):
                errors.append(f"{path}.videoUrl must reference its exact youtubeId")

        evidence = obj(entry.get("viewEvidence"), f"{path}.viewEvidence",
                       {"viewCount", "approximate", "sourceKind", "sourceUrl", "sourceSnapshotOn"})
        count = evidence.get("viewCount")
        if type(count) is not int or count < 1:
            errors.append(f"{path}.viewEvidence.viewCount must be a positive integer")
        if type(evidence.get("approximate")) is not bool:
            errors.append(f"{path}.viewEvidence.approximate must be boolean")
        kind = evidence.get("sourceKind")
        if not isinstance(kind, str) or kind not in _SOURCE_KINDS:
            errors.append(f"{path}.viewEvidence.sourceKind is unsupported")
        source_url = evidence.get("sourceUrl")
        if not _https_url(source_url):
            errors.append(f"{path}.viewEvidence.sourceUrl must be an HTTPS source")
        snapshot = evidence.get("sourceSnapshotOn")
        if snapshot is not None and iso_date(snapshot, f"{path}.viewEvidence.sourceSnapshotOn"):
            if isinstance(retrieved, str) and snapshot > retrieved:
                errors.append(f"{path}.viewEvidence.sourceSnapshotOn is after retrieval")
        if (evidence.get("sourceKind") == "youtube-search-index"
                and source_url != video_url):
            errors.append(f"{path}.viewEvidence.sourceUrl must match indexed YouTube URL")

        tags = entry.get("techniqueTags")
        if (not isinstance(tags, list) or not tags or
                any(not isinstance(tag, str) or not _TAG.fullmatch(tag) for tag in tags)):
            errors.append(f"{path}.techniqueTags must contain valid technique tags")
        elif len(tags) != len(set(tags)):
            errors.append(f"{path}.techniqueTags contains duplicates")
        if entry.get("reviewStatus") != "editorial-candidate-not-frame-reviewed":
            errors.append(f"{path}.reviewStatus must not imply visual verification")
        rights = obj(entry.get("rights"), f"{path}.rights",
                     {"usage", "redistributionAuthorized"})
        if rights.get("usage") != "inspiration-only" or rights.get("redistributionAuthorized") is not False:
            errors.append(f"{path}.rights must explicitly prohibit redistribution")
    return errors


def load_popular_videos(path: Path) -> dict[str, Any]:
    """Load a bounded, regular JSON file; reject malformed/ambiguous metadata."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"popular-video catalog must be a regular file: {path}")
    if path.stat().st_size > 262_144:
        raise ValueError("popular-video catalog exceeds 256 KiB")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"popular-video catalog is invalid JSON: {exc}") from exc
    errors = validate_popular_videos(payload)
    if errors:
        raise ValueError("popular-video catalog validation failed:\n" + "\n".join(errors))
    return payload


def search_popular_videos(data: dict[str, Any], query: str = "", *,
                          min_views: int = 0, limit: int = 20) -> list[dict[str, Any]]:
    """Rank by matching study/technique intent, then popularity (not quality)."""
    if type(min_views) is not int or min_views < 0:
        raise ValueError("minimum views must be a nonnegative integer")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("result limit must be between 1 and 100")
    tokens = set(re.findall(r"[a-z0-9]+", query.lower())) - {"a", "the", "to", "for", "of", "and", "how"}
    if query.strip() and not tokens:
        raise ValueError("search query needs a meaningful keyword")
    matched = []
    for entry in data["entries"]:
        views = entry["viewEvidence"]["viewCount"]
        if views < min_views:
            continue
        fields = ((" ".join(entry["techniqueTags"]).replace("-", " "), 5),
                  (entry["studyQuestion"], 3), (entry["title"], 2), (entry["creator"], 1))
        score = sum(weight * len(tokens & set(re.findall(r"[a-z0-9]+", field.lower())))
                    for field, weight in fields)
        if tokens and score == 0:
            continue
        matched.append((score, views, entry))
    matched.sort(key=lambda row: (-row[0], -row[1], row[2]["id"]))
    return [entry for _, _, entry in matched[:limit]]
