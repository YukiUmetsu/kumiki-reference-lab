"""Source-row-bound YouTube ID candidates with explicit verification limits.

An indexed YouTube search result corroborates a likely ID, not the direct
watch-page contents, rights clearance or a human visual review.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from kumiki_reference_lab.catalog.audience_benchmarks import validate_audience_benchmarks
from kumiki_reference_lab.catalog.visual_study_plan import _fingerprint


SCHEMA_VERSION = "kumiki.video-id-candidates.v1"
_YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}")


def _title_key(title: str) -> str:
    """Ignore only typography of single quotes, not substantive title edits."""
    return title.strip().casefold().translate(str.maketrans({"\u2018": "'", "\u2019": "'"}))


def _publisher_key(publisher: str) -> str:
    """Normalize typographic dashes in otherwise exact channel names."""
    return publisher.strip().casefold().translate(str.maketrans({"\u2013": "-", "\u2014": "-"}))


def validate_video_id_candidates(data: Any, audience: dict[str, Any]) -> None:
    """Reject stale or ambiguous row joins, without claiming visual verification."""
    validate_audience_benchmarks(audience)
    expected = {"schemaVersion", "indexedOn", "methodology", "entries"}
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError("video ID candidate catalog has unexpected or missing properties")
    if data["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("unsupported video ID candidate version")
    indexed_on = data["indexedOn"]
    if not isinstance(indexed_on, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", indexed_on):
        raise ValueError("candidate indexedOn requires an ISO calendar date")
    try:
        indexed_date = date.fromisoformat(indexed_on)
    except ValueError as exc:
        raise ValueError("candidate indexedOn must be a valid calendar date") from exc
    if indexed_date < date.fromisoformat(audience["retrievedOn"]):
        raise ValueError("candidate indexing must not predate the audience retrieval")
    if not isinstance(data["methodology"], str) or not 10 <= len(data["methodology"]) <= 2000:
        raise ValueError("candidate methodology must be documented")
    entries = data["entries"]
    if not isinstance(entries, list) or len(entries) > 300:
        raise ValueError("candidate entries must be a bounded array")
    channels = {channel["id"]: channel for channel in audience["channels"]}
    seen_rows: set[tuple[str, int]] = set()
    seen_ids: set[str] = set()
    for position, raw in enumerate(entries):
        required = {"channelId", "rowIndex", "sourceRowSha256", "youtubeId",
                    "videoUrl", "indexedTitle", "indexedPublisher", "indexedPublishedOn",
                    "evidenceKind", "evidenceUrl", "reviewStatus"}
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError(f"candidate {position} fields do not match the contract")
        channel_id = raw["channelId"]
        if type(channel_id) is not str or channel_id not in channels:
            raise ValueError(f"candidate {position} channel does not exist in source")
        channel = channels[channel_id]
        index = raw["rowIndex"]
        if type(index) is not int or not 0 <= index < len(channel["videos"]):
            raise ValueError(f"candidate {position} row index is invalid")
        key = (channel_id, index)
        if key in seen_rows:
            raise ValueError(f"candidate {position} repeats a source row")
        seen_rows.add(key)
        row = channel["videos"][index]
        fingerprint = _fingerprint(channel_id, channel["sourceLastUpdatedOn"], index, row)
        if raw["sourceRowSha256"] != fingerprint:
            raise ValueError(f"candidate {position} stale or incorrect source row fingerprint")
        youtube_id = raw["youtubeId"]
        if (not isinstance(youtube_id, str) or not _YOUTUBE_ID.fullmatch(youtube_id)
                or youtube_id in seen_ids):
            raise ValueError(f"candidate {position} invalid or repeated YouTube ID")
        seen_ids.add(youtube_id)
        url = raw["videoUrl"]
        if type(url) is not str or url != f"https://www.youtube.com/watch?v={youtube_id}":
            raise ValueError(f"candidate {position} YouTube URL is not canonical")
        if raw["evidenceUrl"] != url or raw["evidenceKind"] != "indexed-youtube-search-result":
            raise ValueError(f"candidate {position} evidence must be its exact indexed YouTube listing")
        if (not isinstance(raw["indexedTitle"], str) or
                _title_key(raw["indexedTitle"]) != _title_key(row["title"])):
            raise ValueError(f"candidate {position} source and indexed titles differ")
        if (not isinstance(raw["indexedPublisher"], str) or
                _publisher_key(raw["indexedPublisher"]) != _publisher_key(channel["name"])):
            raise ValueError(f"candidate {position} indexed publisher mismatches source channel")
        published = raw["indexedPublishedOn"]
        if not isinstance(published, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
            raise ValueError(f"candidate {position} indexed published date malformed")
        try:
            difference = abs((date.fromisoformat(published) - date.fromisoformat(row["publishedOn"])).days)
        except ValueError as exc:
            raise ValueError(f"candidate {position} indexed published date invalid") from exc
        if difference > 1:
            raise ValueError(f"candidate {position} indexed publication date differs by more than one UTC/local day")
        if raw["reviewStatus"] != "index-corroborated-watch-page-not-opened":
            raise ValueError(f"candidate {position} cannot assert stronger identity or visual verification")


def load_video_id_candidates(path: Path, audience: dict[str, Any]) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 131_072:
        raise ValueError("video ID candidates require a regular JSON file at most 128 KiB")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, value in pairs:
            if name in result:
                raise ValueError(f"duplicate video ID candidate JSON property: {name}")
            result[name] = value
        return result

    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"invalid video ID candidate JSON: {exc}") from exc
    validate_video_id_candidates(payload, audience)
    return payload
