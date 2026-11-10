"""Validated, provider-neutral notes from selected browser-player moments.

These observations are never a substitute for timecoded decoded-media evidence.
No site is visited and no video bytes are fetched by this module.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from kumiki_reference_lab.catalog.video_sources import _unique_keys


SCHEMA_VERSION = "kumiki.browser-video-observations.v1"
VISUAL_TAGS = frozenset({
    "kinetic-typography", "easing-demo", "high-contrast-color",
    "editorial-collage", "screen-recording", "product-ui-demo",
    "cinematic-imagery", "technical-illustration", "live-action",
    "character-icon", "refractive-ui", "generated-image-output",
    "3d-modeling", "talking-head", "multi-window-cursor", "product-demonstration",
})
_OBSERVATION_KEYS = {
    "sourceId", "reviewedOn", "method", "coverage", "visualTags",
    "visibleMoments", "techniqueHypotheses",
}
_CALENDAR_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def _date(value: Any) -> bool:
    if not isinstance(value, str) or not _CALENDAR_DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _notes(value: Any, *, min_length: int, max_items: int) -> bool:
    return (isinstance(value, list) and min_length <= len(value) <= max_items and
            all(isinstance(part, str) and 5 <= len(part.strip()) <= 500 for part in value))


def load_browser_observations(collection: dict[str, Any], path: Path) -> dict[str, Any]:
    """Join bounded, source-linked browser notes without upgrading source evidence."""
    if path.is_symlink():
        raise ValueError("browser observation file cannot be a symlink")
    if not path.is_file():
        raise ValueError(f"browser observations must be a regular file: {path}")
    if path.stat().st_size > 256 * 1024:
        raise ValueError("browser observations exceed 256 KiB")
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid browser observations JSON: {exc}") from exc
    if (not isinstance(data, dict) or
            set(data) != {"schemaVersion", "reviewedOn", "methodology", "observations"} or
            data["schemaVersion"] != SCHEMA_VERSION or not _date(data["reviewedOn"]) or
            not isinstance(data["methodology"], str) or
            not 30 <= len(data["methodology"]) <= 1000 or
            not isinstance(data["observations"], list) or
            not 1 <= len(data["observations"]) <= 100):
        raise ValueError("invalid browser observations collection")

    sources = {item["id"]: item for item in collection["entries"]}
    seen: set[str] = set()
    entries = []
    for index, raw in enumerate(data["observations"]):
        label = f"browser observations[{index}]"
        if not isinstance(raw, dict) or set(raw) != _OBSERVATION_KEYS:
            raise ValueError(f"{label} must have exact observation fields")
        source_id = raw["sourceId"]
        if not isinstance(source_id, str) or source_id not in sources or source_id in seen:
            raise ValueError(f"{label} source is unknown or duplicated")
        seen.add(source_id)
        if (not _date(raw["reviewedOn"]) or raw["reviewedOn"] > data["reviewedOn"] or
                raw["method"] != "browser-player" or
                raw["coverage"] != "selected-moments-only"):
            raise ValueError(f"{label} cannot assert a complete or timecoded review")
        tags = raw["visualTags"]
        if (not isinstance(tags, list) or not 1 <= len(tags) <= 8 or
                any(not isinstance(t, str) or t not in VISUAL_TAGS for t in tags) or
                len(tags) != len(set(tags))):
            raise ValueError(f"{label} has invalid visual tags")
        if (not _notes(raw["visibleMoments"], min_length=1, max_items=12) or
                not _notes(raw["techniqueHypotheses"], min_length=0, max_items=8)):
            raise ValueError(f"{label} needs bounded moment notes and hypotheses")
        source = sources[source_id]
        entries.append({
            **raw,
            "source": {
                "title": source["title"], "provider": source["provider"],
                "category": source["category"], "watchUrl": source["watchUrl"],
                "originalUrl": source["originalUrl"],
            },
        })
    return {"schemaVersion": SCHEMA_VERSION, "reviewedOn": data["reviewedOn"],
            "methodology": data["methodology"], "observations": entries}


def search_browser_observations(data: dict[str, Any], *, source_id: str = "",
                                visual_tag: str = "") -> list[dict[str, Any]]:
    if not isinstance(source_id, str):
        raise ValueError("source ID must be text")
    if not isinstance(visual_tag, str) or (visual_tag and visual_tag not in VISUAL_TAGS):
        raise ValueError("visual tag is not supported")
    return [item for item in data["observations"]
            if (not source_id or item["sourceId"] == source_id) and
            (not visual_tag or visual_tag in item["visualTags"])]
