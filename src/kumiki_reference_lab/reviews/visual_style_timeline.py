"""Timecoded reviewer interpretations of visual media and aesthetic treatments.

The labels are *not* learned from a YouTube title, studio reference, or still
thumbnail. A reviewed window is not independent proof of original film access.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "kumiki.visual-style-timeline-review.v1"
MEDIA = frozenset({
    "2d-animation", "2.5d-compositing", "3d-rendered", "live-action",
    "physical-stop-motion", "game-engine", "screen-recording", "mixed-media",
    "unclassified",
})
TREATMENTS = frozenset({
    "paper-cut", "paper-collage", "cutout-puppet", "clay", "hand-drawn",
    "cel-shaded", "painterly", "photorealistic", "2.5d-parallax",
    "halftone-print", "kinetic-typography", "motion-infographic",
    "procedural-abstract", "pixel-art", "naturalistic-documentary",
    "game-cinematic", "composited-live-action", "other",
})
LIGHTING_LOOKS = frozenset({
    "high-key", "low-key", "soft-diffuse", "hard-directional", "backlit",
    "flat-graphic", "mixed", "unclassified",
})
SHOT_SCALES = frozenset({
    "establishing", "wide", "medium", "close-up", "macro", "screen-capture",
    "mixed", "unclassified",
})
_SHA = re.compile(r"[0-9a-f]{64}")


def load_visual_style_timeline(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 262_144:
        raise ValueError("style timeline review must be regular JSON of at most 256 KiB")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate style timeline JSON property: {key}")
            result[key] = value
        return result

    try:
        review = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                            parse_constant=lambda value: (_ for _ in ()).throw(
                                ValueError(f"non-finite JSON in style review: {value}")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"invalid style review JSON: {exc}") from exc
    validate_visual_style_timeline(review)
    return review


def _exact(value: Any, expected: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{name} requires exact fields: {', '.join(sorted(expected))}")
    return value


def validate_visual_style_timeline(review: Any) -> None:
    top = _exact(review, {"schemaVersion", "sourceSha256", "sourceStreamIndex",
                          "sourceTimebase", "reviewer", "window", "segments"}, "style review")
    if top["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("style review schema version unsupported")
    if type(top["sourceSha256"]) is not str or _SHA.fullmatch(top["sourceSha256"]) is None:
        raise ValueError("style review requires lowercase source SHA-256")
    if type(top["sourceStreamIndex"]) is not int or not 0 <= top["sourceStreamIndex"] <= 64:
        raise ValueError("style review stream index invalid")
    timebase = _exact(top["sourceTimebase"], {"numerator", "denominator"}, "timebase")
    n, d = timebase["numerator"], timebase["denominator"]
    if (type(n) is not int or type(d) is not int or not 1 <= n <= 1_000_000_000_000 or
            not 1 <= d <= 1_000_000_000_000 or n > d):
        raise ValueError("style source timebase must be positive rational at most one second")
    reviewer = _exact(top["reviewer"], {"kind", "id"}, "reviewer")
    if (reviewer["kind"] not in ("human", "model") or type(reviewer["id"]) is not str or
            not 2 <= len(reviewer["id"].strip()) <= 100):
        raise ValueError("style review requires a bounded self-declared reviewer")
    window = _exact(top["window"], {"startPts", "endPts", "coverage"}, "window")
    start, end = window["startPts"], window["endPts"]
    if (type(start) is not int or type(end) is not int or not -2**63 < start < end < 2**63 or
            window["coverage"] not in ("full-window-visual-review", "partial-window-visual-review")):
        raise ValueError("style review requires an ordered bounded window and declared coverage")
    span = (end - start) * Fraction(n, d)
    if not Fraction(1, 1000) <= span <= 24 * 3600:
        raise ValueError("style reviewed window outside permitted duration")
    segments = top["segments"]
    if not isinstance(segments, list) or len(segments) > 500:
        raise ValueError("style segments must be a bounded list")
    previous_end = start
    for index, raw in enumerate(segments):
        item = _exact(raw, {"startPts", "endPts", "medium", "treatments",
                            "lightingLook", "shotScale", "confidence", "anchorPts",
                            "observation", "alternativeExplanation"}, f"segment {index}")
        lo, hi = item["startPts"], item["endPts"]
        if (type(lo) is not int or type(hi) is not int or
                not start <= previous_end <= lo < hi <= end):
            raise ValueError(f"segment {index} overlaps, is out of order or outside review window")
        previous_end = hi
        if type(item["medium"]) is not str or item["medium"] not in MEDIA:
            raise ValueError(f"segment {index} medium unsupported")
        treatments = item["treatments"]
        if (not isinstance(treatments, list) or len(treatments) > 6 or
                any(type(t) is not str or t not in TREATMENTS for t in treatments) or
                len(treatments) != len(set(treatments))):
            raise ValueError(f"segment {index} treatments must be distinct known tags")
        for key, allowed in (("lightingLook", LIGHTING_LOOKS), ("shotScale", SHOT_SCALES)):
            if type(item[key]) is not str or item[key] not in allowed:
                raise ValueError(f"segment {index} {key} unsupported")
        if item["confidence"] not in ("high", "medium", "low", "unresolved"):
            raise ValueError(f"segment {index} confidence unsupported")
        if item["confidence"] == "unresolved" and (
                item["medium"] != "unclassified" or item["treatments"] or
                item["lightingLook"] != "unclassified" or item["shotScale"] != "unclassified"):
            raise ValueError(f"segment {index} unresolved evidence must use explicit unclassified tags")
        anchors = item["anchorPts"]
        if (not isinstance(anchors, list) or not 1 <= len(anchors) <= 5 or
                any(type(p) is not int or not lo <= p < hi for p in anchors) or
                anchors != sorted(set(anchors))):
            raise ValueError(f"segment {index} requires 1-5 distinct ordered PTS anchors")
        for text_field in ("observation", "alternativeExplanation"):
            value = item[text_field]
            if type(value) is not str or not 4 <= len(value.strip()) <= 1000:
                raise ValueError(f"segment {index} {text_field} must be meaningful bounded text")
    if window["coverage"] == "full-window-visual-review":
        if not segments or segments[0]["startPts"] != start or previous_end != end or any(
                a["endPts"] != b["startPts"] for a, b in zip(segments, segments[1:])):
            raise ValueError("a full-window style review must tile the whole window without gaps")


def summarize_visual_style_timeline(review: dict[str, Any]) -> dict[str, Any]:
    """Time proportions use exact PTS intervals, not segment counts."""
    validate_visual_style_timeline(review)
    tb = review["sourceTimebase"]
    unit = Fraction(tb["numerator"], tb["denominator"])
    w = review["window"]
    span = (w["endPts"] - w["startPts"]) * unit
    labeled = Fraction(0)
    buckets: dict[str, dict[str, Fraction]] = {
        "medium": defaultdict(Fraction), "treatment": defaultdict(Fraction),
        "lightingLook": defaultdict(Fraction), "shotScale": defaultdict(Fraction),
        "confidence": defaultdict(Fraction),
    }
    for segment in review["segments"]:
        length = (segment["endPts"] - segment["startPts"]) * unit
        labeled += length
        for key, value in (("medium", segment["medium"]),
                           ("lightingLook", segment["lightingLook"]),
                           ("shotScale", segment["shotScale"]),
                           ("confidence", segment["confidence"])):
            buckets[key][value] += length
        for treatment in segment["treatments"]:
            buckets["treatment"][treatment] += length
    complete = (w["coverage"] == "full-window-visual-review" and labeled == span)
    return {
        "schemaVersion": "kumiki.visual-style-timeline-summary.v1",
        "sourceSha256": review["sourceSha256"],
        "sourceStreamIndex": review["sourceStreamIndex"],
        "sourceTimebase": review["sourceTimebase"],
        "reviewer": {**review["reviewer"], "identityVerified": False},
        "window": review["window"],
        "reviewedWindowSeconds": round(float(span), 6),
        "labeledSeconds": round(float(labeled), 6),
        "labeledFractionOfWindow": round(float(labeled / span), 6),
        "wholeWindowStyleCompositionAvailable": complete,
        "observedStyleTime": {
            key: [{"tag": tag, "seconds": round(float(value), 6),
                   "fractionOfLabeledTime": round(float(value / labeled), 6) if labeled else None,
                   "fractionOfEntireReviewedWindow": round(float(value / span), 6) if complete else None}
                  for tag, value in sorted(group.items())]
            for key, group in buckets.items()
        },
        "unresolvedSegments": sum(s["confidence"] == "unresolved" for s in review["segments"]),
        "evidenceStatus": "reviewer-interpreted-not-independently-frame-verified",
        "methodLimits": [
            "Time shares are self-declared visual labels, not automatic classification or proof of original media identity.",
            "Multiple aesthetic treatments can overlap, so treatment fractions need not sum to one.",
            "A gap or partial review forbids whole-window time-share estimates; unclassified spans must be explicit.",
            "Lighting looks and shot scale are interpretations, not recovered light rigs, physical lenses or editing events.",
            "No audience/camera-frequency relationship can be inferred from this review alone.",
        ],
    }
