"""Self-declared visual-review labels with bounded-window camera/lighting event rates.

These are reviewer interpretations, unlike independently measured pixel proxies.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "kumiki.visual-events-review.v1"
CAMERA_KINDS = frozenset({
    "pan", "tilt", "dolly-in", "dolly-out", "truck", "crane", "orbit", "roll",
    "optical-zoom", "handheld", "virtual-parallax", "other-camera-motion",
})
LIGHTING_KINDS = frozenset({
    "light-sweep", "intensity-ramp", "color-temperature-shift", "hardness-transition",
    "backlight-reveal", "shadow-motion", "other-lighting-change",
})


def load_visual_events(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 131_072:
        raise ValueError("visual events review must be a regular JSON file of at most 128 KiB")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate review JSON property: {key}")
            result[key] = value
        return result

    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"visual events review JSON is invalid: {exc}") from exc
    validate_visual_events(data)
    return data


def validate_visual_events(review: Any) -> None:
    def shape(value: Any, expected: set[str], label: str) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError(f"{label} must contain exactly: {', '.join(sorted(expected))}")
        return value

    top = shape(review, {"schemaVersion", "sourceSha256", "sourceStreamIndex",
                         "sourceTimebase", "reviewer", "window", "events"}, "review")
    if top["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("unsupported visual events review version")
    if (not isinstance(top["sourceSha256"], str) or
            re.fullmatch(r"[a-f0-9]{64}", top["sourceSha256"]) is None):
        raise ValueError("review source SHA-256 is invalid")
    if type(top["sourceStreamIndex"]) is not int or top["sourceStreamIndex"] < 0:
        raise ValueError("review source stream index is invalid")
    timebase = shape(top["sourceTimebase"], {"numerator", "denominator"}, "timebase")
    if (type(timebase["numerator"]) is not int or type(timebase["denominator"]) is not int or
            not 1 <= timebase["denominator"] <= 1_000_000_000_000 or
            abs(timebase["numerator"]) > 1_000_000_000_000 or not 0 < Fraction(
                timebase["numerator"], timebase["denominator"]) <= 1):
        raise ValueError("review source timebase is invalid")
    reviewer = shape(top["reviewer"], {"kind", "id"}, "reviewer")
    if reviewer["kind"] not in ("human", "model") or not isinstance(reviewer["id"], str) or not 2 <= len(reviewer["id"]) <= 100:
        raise ValueError("reviewer must identify self-declared human or model author")
    window = shape(top["window"], {"startPts", "endPts", "coverage"}, "window")
    if (type(window["startPts"]) is not int or type(window["endPts"]) is not int or
            window["endPts"] <= window["startPts"] or
            any(abs(window[key]) > 2**63 - 1 for key in ("startPts", "endPts")) or
            window["coverage"] not in ("full-window-visual-review", "partial-window-visual-review")):
        raise ValueError("review window requires ordered source PTS and explicit review coverage")
    span = (window["endPts"] - window["startPts"]) * Fraction(
        timebase["numerator"], timebase["denominator"])
    if not Fraction(1, 1000) <= span <= 24 * 3600:
        raise ValueError("review window must span from 1 millisecond through 24 hours")
    events = top["events"]
    if not isinstance(events, list) or len(events) > 500:
        raise ValueError("visual events must be a bounded list")
    signatures: set[tuple[str, str, int, int]] = set()
    for index, raw in enumerate(events):
        item = shape(raw, {"category", "kind", "startPts", "endPts", "assessment",
                           "observation", "alternativeExplanation"}, f"event {index}")
        category = item["category"]
        if type(category) is not str or category not in ("camera-movement", "lighting-change"):
            raise ValueError(f"event {index} category unsupported")
        allowed = CAMERA_KINDS if category == "camera-movement" else LIGHTING_KINDS
        if type(item["kind"]) is not str or item["kind"] not in allowed:
            raise ValueError(f"event {index} kind unsupported")
        if (type(item["startPts"]) is not int or type(item["endPts"]) is not int or
                not window["startPts"] <= item["startPts"] < item["endPts"] <= window["endPts"]):
            raise ValueError(f"event {index} must lie within reviewed PTS window")
        if item["assessment"] not in ("reviewer-interpreted", "unresolved-hypothesis"):
            raise ValueError(f"event {index} assessment unsupported")
        for name in ("observation", "alternativeExplanation"):
            if not isinstance(item[name], str) or not 4 <= len(item[name].strip()) <= 1000:
                raise ValueError(f"event {index} {name} must be meaningful bounded text")
        signature = (category, item["kind"], item["startPts"], item["endPts"])
        if signature in signatures:
            raise ValueError(f"duplicate visual event at index {index}")
        signatures.add(signature)


def summarize_visual_events(review: dict[str, Any]) -> dict[str, Any]:
    """Only full-window self-declared reviews receive event/minute estimates."""
    validate_visual_events(review)
    timebase = review["sourceTimebase"]
    span = (review["window"]["endPts"] - review["window"]["startPts"]) * Fraction(
        timebase["numerator"], timebase["denominator"])
    seconds = float(span)
    full = review["window"]["coverage"] == "full-window-visual-review"
    observed = Counter((event["category"], event["kind"]) for event in review["events"]
                       if event["assessment"] == "reviewer-interpreted")
    uncertain = Counter(event["category"] for event in review["events"]
                        if event["assessment"] == "unresolved-hypothesis")
    by_type = [{"category": category, "kind": kind, "count": count,
                "eventsPerReviewedMinute": round(count * 60 / seconds, 6) if full else None}
               for (category, kind), count in sorted(observed.items())]
    return {
        "schemaVersion": "kumiki.visual-event-frequency.v1",
        "sourceSha256": review["sourceSha256"],
        "sourceStreamIndex": review["sourceStreamIndex"],
        "window": review["window"],
        "reviewedWindowSeconds": round(seconds, 6),
        "observer": {"kind": review["reviewer"]["kind"], "id": review["reviewer"]["id"],
                     "identityVerified": False},
        "interpretation": "self-declared visual-event annotations, not physically verified rigs or automated detections",
        "eventRatesAvailable": full,
        "cameraMovementEvents": sum(v for (category, _), v in observed.items()
                                    if category == "camera-movement"),
        "lightingChangeEvents": sum(v for (category, _), v in observed.items()
                                     if category == "lighting-change"),
        "cameraMovementEventsPerReviewedMinute": (round(
            sum(v for (category, _), v in observed.items() if category == "camera-movement")
            * 60 / seconds, 6) if full else None),
        "lightingChangeEventsPerReviewedMinute": (round(
            sum(v for (category, _), v in observed.items() if category == "lighting-change")
            * 60 / seconds, 6) if full else None),
        "unresolvedByCategory": dict(sorted(uncertain.items())),
        "eventTypeRates": by_type,
    }
