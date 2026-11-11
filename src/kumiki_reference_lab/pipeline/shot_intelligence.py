"""Low-compute temporal grouping of per-frame evidence into provisional shots.

Only decoder-timestamped, measured image differences are used. A shot boundary
is a *candidate* hard edit, not an independently verified editing decision.
No AI, source video, or additional dependencies are required.
"""
from __future__ import annotations

import math
import statistics
from typing import Any

SCHEMA_VERSION = "kumiki.online-shot-intelligence.v1"


def _finite(value: Any, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + " must be finite")
    return float(value)


def _validated_rows(numeric: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(numeric, dict):
        raise ValueError("shot analysis requires numeric evidence")
    rows = numeric.get("frames")
    if (not isinstance(rows, list) or not 1 <= len(rows) <= 108000 or
            numeric.get("frameCount") != len(rows) or
            not isinstance(numeric.get("sourceSha256"), str) or
            len(numeric["sourceSha256"]) != 64):
        raise ValueError("invalid frame evidence")
    prev = float("-inf")
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("frameIndex") != i:
            raise ValueError("frame indices must be sequential")
        t = _finite(row.get("decodedSeconds"), "frame timestamp")
        if t <= prev:
            raise ValueError("frame timestamps must strictly increase")
        prev = t
        a = row.get("appearance")
        if not isinstance(a, dict):
            raise ValueError("appearance evidence missing")
        for field in ("displayLumaProxy", "saturationProxy",
                      "brightPixelFraction", "darkPixelFraction"):
            v = _finite(a.get(field), field)
            if not 0 <= v <= 1:
                raise ValueError("appearance range invalid")
        rgb = a.get("meanRgb")
        if (not isinstance(rgb, list) or len(rgb) != 3 or
                any(not 0 <= _finite(v, "meanRgb") <= 1 for v in rgb)):
            raise ValueError("mean RGB evidence invalid")
        change = row.get("changeFromPrevious")
        if i == 0 and change is not None:
            raise ValueError("first frame must not have a prior delta")
        if i > 0:
            if not isinstance(change, dict):
                raise ValueError("frame delta missing")
            for field in ("meanPixelDelta", "changedPixelFraction"):
                if not 0 <= _finite(change.get(field), field) <= 1:
                    raise ValueError("frame delta outside 0..1")
    return rows


def _representatives(rows: list[dict[str, Any]], begin: int, stop: int) -> list[int]:
    indices = {begin, (begin + stop - 1) // 2, stop - 1}
    # Include the most visually dynamic frame inside a shot without
    # spending model budget on every frame.
    if stop - begin > 2:
        active = max(range(begin + 1, stop),
                     key=lambda i: rows[i]["changeFromPrevious"]["meanPixelDelta"])
        indices.add(active)
    return sorted(indices)


def build_shot_intelligence(
    numeric: dict[str, Any], *, min_shot_frames: int = 4,
    absolute_cut_threshold: float = 0.27,
    outlier_ratio: float = 3.0, max_shots: int = 3000,
) -> dict[str, Any]:
    """Split frame evidence at conservative scene-change outliers.

    The frame at a cut is the first frame of the following shot. Very short
    flashes/rapid montage beats may be deliberately merged by the min-length
    gate; candidates remain available in the cutCandidates table.
    """
    if (type(min_shot_frames) is not int or not 2 <= min_shot_frames <= 300
            or type(max_shots) is not int or not 1 <= max_shots <= 10000
            or not .05 <= _finite(absolute_cut_threshold, "cut threshold") <= .9
            or not 1.25 <= _finite(outlier_ratio, "outlier ratio") <= 20):
        raise ValueError("invalid shot intelligence limits")
    rows = _validated_rows(numeric)
    n = len(rows)
    deltas = [0.] + [
        row["changeFromPrevious"]["meanPixelDelta"] for row in rows[1:]
    ]
    raw_candidates = []
    for i in range(1, n):
        value = deltas[i]
        baseline = statistics.median(deltas[max(1, i - 12):i] or [0.])
        strong = value >= absolute_cut_threshold
        surprise = (value >= max(.12, outlier_ratio * max(.02, baseline))
                    and rows[i]["changeFromPrevious"]["changedPixelFraction"] >= .2)
        if strong or surprise:
            raw_candidates.append({
                "frameIndex": i,
                "decodedSeconds": rows[i]["decodedSeconds"],
                "meanPixelDelta": value,
                "precedingMedianDelta": round(baseline, 5),
                "reason": "absolute-change" if strong else "relative-image-outlier",
                "boundaryStatus": "unverified-candidate",
            })
    boundaries = [0]
    rejected = 0
    for item in raw_candidates:
        i = item["frameIndex"]
        if i - boundaries[-1] < min_shot_frames or n - i < min_shot_frames:
            rejected += 1
            continue
        if len(boundaries) >= max_shots:
            raise ValueError("shot analysis exceeded maximum shot budget")
        boundaries.append(i)
    boundaries.append(n)
    intervals = [rows[i + 1]["decodedSeconds"] - rows[i]["decodedSeconds"]
                 for i in range(n - 1)]
    typical_dt = statistics.median(intervals) if intervals else 0.
    approx_end = rows[-1]["decodedSeconds"] + typical_dt
    shots = []
    for ordinal, (start, stop) in enumerate(zip(boundaries, boundaries[1:]), 1):
        block = rows[start:stop]
        appearances = [row["appearance"] for row in block]
        rgb = [round(statistics.mean(a["meanRgb"][k] for a in appearances), 5)
               for k in range(3)]
        activity = [deltas[i] for i in range(start + 1, stop)]
        start_sec = rows[start]["decodedSeconds"]
        end_sec = (rows[stop]["decodedSeconds"] if stop < n else approx_end)
        light = statistics.mean(a["displayLumaProxy"] for a in appearances)
        sat = statistics.mean(a["saturationProxy"] for a in appearances)
        shots.append({
            "shotId": f"shot-{ordinal:04d}",
            "startFrameIndex": start,
            "endFrameIndexExclusive": stop,
            "frameCount": stop - start,
            "startSeconds": start_sec,
            "endSecondsEstimate": round(end_sec, 6),
            "durationSecondsEstimate": round(end_sec - start_sec, 6),
            "startBoundary": "scan-start" if ordinal == 1 else "candidate-cut",
            "endBoundary": "scan-end" if stop == n else "candidate-cut",
            "representativeFrameIndices": _representatives(rows, start, stop),
            "imageEvidence": {
                "meanRgb": rgb,
                "meanLuma": round(light, 5),
                "meanSaturation": round(sat, 5),
                "meanBrightFraction": round(statistics.mean(
                    a["brightPixelFraction"] for a in appearances), 5),
                "meanDarkFraction": round(statistics.mean(
                    a["darkPixelFraction"] for a in appearances), 5),
                "meanWithinShotPixelDelta": (round(statistics.mean(activity), 5)
                                             if activity else None),
                "maxWithinShotPixelDelta": max(activity) if activity else None,
                "displayPaletteProxy": (
                    "bright" if light >= .68 else
                    "dark" if light <= .32 else
                    "mid-tone"
                ),
                "displaySaturationProxy": (
                    "vivid" if sat >= .65 else "muted" if sat <= .2 else "moderate"
                ),
            },
            "reviewStatus": "candidate-not-a-verified-shot",
        })
    durations = [s["durationSecondsEstimate"] for s in shots]
    cuts = [s["startFrameIndex"] for s in shots[1:]]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": numeric["sourceSha256"],
        "frameCount": n,
        "shotCount": len(shots),
        "candidateCutFrameIndices": cuts,
        "rawCandidateCount": len(raw_candidates),
        "suppressedCandidateCount": rejected,
        "cutCandidates": raw_candidates,
        "shots": shots,
        "editRhythm": {
            "observedCutCount": len(cuts),
            "medianShotDurationSecondsEstimate": (
                round(statistics.median(durations), 6) if durations else None),
            "shortestShotDurationSecondsEstimate": min(durations) if durations else None,
            "longestShotDurationSecondsEstimate": max(durations) if durations else None,
        },
        "confidence": "unverified-image-change-heuristic",
        "limitations": [
            "Frame changes can arise from animation, camera movement, lighting or editing.",
            "Fast edits shorter than the minimum shot interval may be merged.",
            "Gradual transitions and dissolves are not identified as verified boundaries.",
            "Shot timestamps use FFmpeg decoded presentation seconds.",
        ],
    }


def prioritized_frame_plan(
    shots: dict[str, Any], *, max_frames: int = 48,
) -> dict[str, Any]:
    """Round-robin shots so early long shots cannot monopolize a tiny agent."""
    if type(max_frames) is not int or not 1 <= max_frames <= 1000:
        raise ValueError("frame plan exceeds budget")
    intervals = shots.get("shots")
    if not isinstance(intervals, list) or not intervals:
        raise ValueError("shot plan needs shot intelligence")
    pending = [list(shot["representativeFrameIndices"]) for shot in intervals]
    selected: list[dict[str, Any]] = []
    round_number = 0
    while len(selected) < max_frames and any(pending):
        for shot, frames in zip(intervals, pending, strict=True):
            if len(selected) >= max_frames:
                break
            if frames:
                selected.append({
                    "frameIndex": frames.pop(0),
                    "shotId": shot["shotId"],
                    "reviewPurpose": (
                        "shot-first-frame" if round_number == 0 else
                        "within-shot-temporal-comparison"
                    ),
                    "categories": ["animation", "typography", "visual-style"],
                })
        round_number += 1
    return {
        "schemaVersion": "kumiki.shot-aware-agent-plan.v1",
        "sourceSha256": shots["sourceSha256"],
        "maxModelFrames": max_frames,
        "frameTasks": selected,
        "status": "bounded-review-plan-not-semantic-findings",
    }
