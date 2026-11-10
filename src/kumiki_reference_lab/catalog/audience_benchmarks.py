"""Offline audience-metadata comparisons, never a causal creative-quality model.

Recent-upload snapshots reduce the hits-only selection bias of the curated
reference catalog. They still cannot establish viewer retention, unique viewers,
actual creative techniques, paid promotion or a video's release-day trajectory.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any


SCHEMA_VERSION = "kumiki.audience-benchmark.v1"
_ID = re.compile(r"^[a-z][a-z0-9-]+$")
_SOURCE_PREFIX = "https://digitalcreators.jp/en/channel/en/"
_DURATION_BANDS = (
    ("under-1-minute", 0, 60),
    ("1-to-3-minutes", 60, 180),
    ("3-to-10-minutes", 180, 600),
    ("10-to-30-minutes", 600, 1800),
    ("30-minutes-plus", 1800, None),
)
_AGE_BANDS = (
    ("0-to-29-days", 0, 30),
    ("30-to-89-days", 30, 90),
    ("90-to-179-days", 90, 180),
    ("180-to-364-days", 180, 365),
    ("365-days-plus", 365, None),
)


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate audience metadata property: {key}")
        result[key] = value
    return result


def _check_date(value: Any, name: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{name} must be an ISO calendar date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid calendar date") from exc


def _object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label} must have exactly {sorted(keys)}")
    return value


def validate_audience_benchmarks(payload: Any) -> None:
    """Fail closed on malformed, duplicate or temporally ambiguous observations."""
    data = _object(payload, {"schemaVersion", "retrievedOn", "methodology", "channels"}, "collection")
    if data["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("unsupported audience benchmark schema")
    retrieved = _check_date(data["retrievedOn"], "retrievedOn")
    if not isinstance(data["methodology"], str) or not data["methodology"].strip():
        raise ValueError("methodology must document the sample")
    channels = data["channels"]
    if not isinstance(channels, list) or not 1 <= len(channels) <= 32:
        raise ValueError("channels must contain 1–32 source snapshots")
    seen: set[str] = set()
    for ci, raw in enumerate(channels):
        channel = _object(raw, {"id", "name", "sourceUrl", "sourceLastUpdatedOn", "videos"},
                          f"channels[{ci}]")
        identifier = channel["id"]
        if (not isinstance(identifier, str) or not _ID.fullmatch(identifier)
                or identifier in seen):
            raise ValueError(f"channels[{ci}].id invalid or duplicated")
        seen.add(identifier)
        if not isinstance(channel["name"], str) or not channel["name"].strip():
            raise ValueError(f"channels[{ci}].name must be nonempty")
        source = channel["sourceUrl"]
        if (not isinstance(source, str) or not source.startswith(_SOURCE_PREFIX)
                or not re.fullmatch(r"https://digitalcreators\.jp/en/channel/en/[A-Za-z0-9_-]+/videos/", source)):
            raise ValueError(f"channels[{ci}].sourceUrl must be the cited channel listing")
        snapshot = _check_date(channel["sourceLastUpdatedOn"], f"channels[{ci}].sourceLastUpdatedOn")
        if snapshot > retrieved:
            raise ValueError(f"channels[{ci}].sourceLastUpdatedOn is after retrieval")
        videos = channel["videos"]
        if not isinstance(videos, list) or not 1 <= len(videos) <= 50:
            raise ValueError(f"channels[{ci}].videos must contain 1–50 latest uploads")
        previous = snapshot
        for vi, raw_video in enumerate(videos):
            label = f"channels[{ci}].videos[{vi}]"
            video = _object(raw_video, {"title", "publishedOn", "durationSeconds",
                                          "views", "likes", "comments"}, label)
            if not isinstance(video["title"], str) or not video["title"].strip():
                raise ValueError(f"{label}.title must be nonempty")
            published = _check_date(video["publishedOn"], f"{label}.publishedOn")
            if published > previous:
                raise ValueError(f"{label}.publishedOn is newer than the preceding upload or source")
            previous = published
            duration = video["durationSeconds"]
            if duration is not None and (type(duration) is not int or not 1 <= duration <= 604800):
                raise ValueError(f"{label}.durationSeconds must be positive or unknown")
            for key in ("views", "likes", "comments"):
                count = video[key]
                if type(count) is not int or not 0 <= count <= 10**12:
                    raise ValueError(f"{label}.{key} must be a nonnegative integer")
            if video["views"] < 1:
                raise ValueError(f"{label}.views must be positive for a ratio")


def load_audience_benchmarks(path: Path) -> dict[str, Any]:
    """Read one regular, bounded local snapshot; no remote media or analytics calls."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"audience benchmark must be a regular file: {path}")
    if path.stat().st_size > 524288:
        raise ValueError("audience benchmark exceeds 512 KiB")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"audience benchmark JSON is invalid: {exc}") from exc
    validate_audience_benchmarks(payload)
    return payload


def _median(numbers: list[float | int]) -> float | None:
    return round(float(median(numbers)), 3) if numbers else None


def _summary(videos: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(videos),
        "medianViews": _median([v["views"] for v in videos]),
        "medianLikesPer1000Views": _median([1000 * v["likes"] / v["views"] for v in videos]),
        "medianCommentsPer1000Views": _median([1000 * v["comments"] / v["views"] for v in videos]),
    }


def build_audience_insights(data: dict[str, Any], *, minimum_comparison_count: int = 5) -> dict[str, Any]:
    """Descriptive within-source comparisons, never success predictions.

    Age is measured relative to each source's snapshot (not the retrieval date).
    Short/long comparisons use <3 minutes and >=3 minutes. These are *duration*
    labels, not claims about YouTube's Shorts distribution mechanism.
    """
    validate_audience_benchmarks(data)
    if type(minimum_comparison_count) is not int or not 2 <= minimum_comparison_count <= 50:
        raise ValueError("minimum comparison count must be between 2 and 50")
    channel_results = []
    for channel in data["channels"]:
        snapshot = date.fromisoformat(channel["sourceLastUpdatedOn"])
        enriched = [{**v, "ageDays": (snapshot - date.fromisoformat(v["publishedOn"])).days}
                    for v in channel["videos"]]
        durations = [{"band": label, **_summary([v for v in enriched
                     if v["durationSeconds"] is not None and v["durationSeconds"] >= start
                     and (end is None or v["durationSeconds"] < end)])}
                     for label, start, end in _DURATION_BANDS]
        durations.append({"band": "duration-unknown", **_summary(
            [v for v in enriched if v["durationSeconds"] is None])})
        ages = []
        contrasts = []
        for label, start, end in _AGE_BANDS:
            group = [v for v in enriched if v["ageDays"] >= start
                     and (end is None or v["ageDays"] < end)]
            ages.append({"band": label, **_summary(group)})
            short = [v for v in group if v["durationSeconds"] is not None and v["durationSeconds"] < 180]
            long = [v for v in group if v["durationSeconds"] is not None and v["durationSeconds"] >= 180]
            if len(short) >= minimum_comparison_count and len(long) >= minimum_comparison_count:
                short_median = _median([v["views"] for v in short])
                long_median = _median([v["views"] for v in long])
                contrasts.append({
                    "ageBand": label, "shorterThan3Minutes": _summary(short),
                    "atLeast3Minutes": _summary(long),
                    "medianViewRatioShortToLong": round(short_median / long_median, 3),
                })
        channel_results.append({
            "id": channel["id"], "name": channel["name"],
            "sourceUrl": channel["sourceUrl"], "sourceLastUpdatedOn": channel["sourceLastUpdatedOn"],
            "overall": _summary(enriched), "durationBands": durations,
            "ageBands": ages, "ageMatchedDurationContrasts": contrasts,
        })
    return {
        "schemaVersion": "kumiki.audience-insights.v1",
        "sourceSchemaVersion": SCHEMA_VERSION,
        "retrievedOn": data["retrievedOn"],
        "channelCount": len(channel_results),
        "sampleCount": sum(c["overall"]["count"] for c in channel_results),
        "minimumComparisonCount": minimum_comparison_count,
        "channelSummaries": channel_results,
        "interpretationStatus": "observational-metadata-only-no-causal-conclusions",
        "caveats": [
            "Recent 50 uploads per selected channel, not random videos or a representative YouTube sample.",
            "Source snapshot dates differ; compare age bands within each source, not raw channel totals.",
            "Age-matched windows remain broad and do not correct for promotion, channel audiences or topic.",
            "Duration under three minutes is NOT proof of YouTube Shorts format or recommendation treatment.",
            "Likes/comments per view are public reaction proxies, not retention, watch-time or audience satisfaction.",
            "No video was frame-reviewed and no visual technique was inferred from metadata.",
            "No statistically significant effect or causal relationship is claimed.",
        ],
    }
