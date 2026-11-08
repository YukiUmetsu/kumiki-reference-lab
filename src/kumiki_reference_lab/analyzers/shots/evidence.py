"""Bounded edit-region evidence from verified original source timestamps.

Candidate cut boundaries are *not* proven edits or recovered story beats.
Image-plane motion and display-color measurements are only observations.
"""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.contracts.analysis import (
    APPEARANCE_VERSION, FRAME_TIMELINE_VERSION, IMAGE_MOTION_VERSION,
    SHOT_CANDIDATES_VERSION, SHOT_EVIDENCE_VERSION, SPARSE_FLOW_VERSION,
)
from kumiki_reference_lab.core.timebase import as_rational_dict
from kumiki_reference_lab.pipeline.analyze import _validate_existing


_REPORT_FILES = {
    "frames": ("frame-timeline.json", FRAME_TIMELINE_VERSION),
    "cuts": ("shot-candidates.json", SHOT_CANDIDATES_VERSION),
    "motion": ("image-motion.json", IMAGE_MOTION_VERSION),
    "sparseFlow": ("sparse-flow.json", SPARSE_FLOW_VERSION),
    "appearance": ("appearance.json", APPEARANCE_VERSION),
}

_REVIEW_QUESTIONS = [
    "Is the boundary a genuine edit, or motion-triggered scene-difference false positive?",
    "What must the audience understand or notice in this region?",
    "Do visual motion, composition, sound and timing support that purpose?",
]


def _mean(numbers: list[float]) -> float | None:
    return round(sum(numbers) / len(numbers), 6) if numbers else None


def _interval_summary(
    first: int, last: int, *, appearance: dict[str, Any] | None,
    motion: dict[str, Any] | None, sparse: dict[str, Any] | None,
) -> dict[str, Any]:
    appearance_summary = None
    if appearance is not None:
        sample_rows = [sample for sample in appearance["samples"]
                       if first <= sample["sourcePts"] <= last]
        appearance_summary = {
            "sampleCount": len(sample_rows),
            "sourcePts": [s["sourcePts"] for s in sample_rows],
            "meanDisplayLumaProxy": _mean([s["appearance"]["meanLumaProxy"]
                                           for s in sample_rows]),
            "meanContrastP90MinusP10": _mean([
                s["appearance"]["lumaContrastP90MinusP10"] for s in sample_rows]),
            "meanSaturation": _mean([s["appearance"]["meanSaturation"]
                                     for s in sample_rows]),
            "meanBrightPixelFraction": _mean([s["appearance"]["brightPixelFraction"]
                                              for s in sample_rows]),
        }
    motion_summary = None
    if motion is not None:
        pairs = [pair for pair in motion["pairs"]
                 if first <= pair["startPts"] < pair["endPts"] <= last]
        vectors = [math.hypot(pair["dxNormalized"], pair["dyNormalized"])
                   for pair in pairs if pair.get("dxNormalized") is not None and
                   pair.get("dyNormalized") is not None]
        motion_summary = {
            "pairCount": len(pairs),
            "measuredPairCount": len(vectors),
            "unmeasuredPairCount": len(pairs) - len(vectors),
            "meanGlobalImageDisplacementNormalized": _mean(vectors),
            "units": "normalized frame dimensions per sampled pair; not pixels per second or camera speed",
        }
    sparse_summary = None
    if sparse is not None:
        pairs = [pair for pair in sparse["pairs"]
                 if first <= pair["startPts"] < pair["endPts"] <= last]
        sparse_summary = {
            "pairCount": len(pairs),
            "affineImageCandidatePairCount": sum(
                pair.get("geometryHypothesis") is not None and
                pair["geometryHypothesis"].get("status") ==
                "affine-image-plane-candidate" for pair in pairs),
            "translationSufficientPairCount": sum(
                pair.get("geometryHypothesis") is not None and
                pair["geometryHypothesis"].get("status") ==
                "translation-sufficient" for pair in pairs),
            "limits": "2D sparse image geometry; no physical camera, object identity or depth recovery",
        }
    return {"appearance": appearance_summary, "motion": motion_summary,
            "sparseFlow": sparse_summary}


def summarize_edit_regions(
    frames: dict[str, Any], cuts: dict[str, Any], *,
    appearance: dict[str, Any] | None = None,
    motion: dict[str, Any] | None = None,
    sparse: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure source-timestamp segmentation; never interpolate missing PTS."""
    rows = frames["frames"]
    points = [row["sourcePts"] for row in rows]
    cut_pts = [candidate["sourcePts"] for candidate in cuts["candidates"]]
    if any(type(pts) is not int for pts in cut_pts) or cut_pts != sorted(set(cut_pts)):
        raise ValueError("cut candidates require increasing, unique integer PTS")
    anomalies = list(frames.get("anomalies", []))
    last_valid_pts = None
    for row in rows:
        pts = row["sourcePts"]
        reason = ("missing-source-pts" if type(pts) is not int else
                  "nonincreasing-source-pts" if
                  last_valid_pts is not None and pts <= last_valid_pts else None)
        if reason is not None and not any(
                a.get("sampleOrdinal") == row["sampleOrdinal"] and
                a.get("reason") == reason for a in anomalies):
            anomalies.append({"sampleOrdinal": row["sampleOrdinal"], "reason": reason})
        if type(pts) is int:
            last_valid_pts = pts
    if not points or anomalies:
        return {"status": "blocked-unreliable-source-pts",
                "framePtsAnomalies": anomalies,
                "ignoredCutCandidatePts": cut_pts,
                "regions": []}
    known_pts = set(points)
    for key, report in (("appearance", appearance), ("motion", motion),
                        ("sparseFlow", sparse)):
        if report is None:
            continue
        samples = report["samples"]
        sampled_pts = [s["sourcePts"] for s in samples]
        if (any(type(x) is not int for x in sampled_pts) or
                sampled_pts != sorted(set(sampled_pts)) or
                any(pts not in known_pts for pts in sampled_pts)):
            raise ValueError(f"{key} has sample PTS inconsistent with the decoded timeline")
    first, last = points[0], points[-1]
    boundaries = [pts for pts in cut_pts if first < pts <= last]
    if any(pts not in known_pts for pts in boundaries):
        raise ValueError("cut candidate PTS not present in the decoded frame timeline")
    groups: list[list[dict[str, Any]]] = []
    index = 0
    for boundary in boundaries + [None]:
        region = []
        while index < len(rows) and (boundary is None or rows[index]["sourcePts"] < boundary):
            region.append(rows[index])
            index += 1
        if region:
            groups.append(region)
    if index != len(rows):
        raise ValueError("shot regions do not cover the input frame timeline")
    regions = []
    timebase = Fraction(**frames["sourceTimebase"])
    for region_index, group in enumerate(groups):
        region_start, region_last = group[0]["sourcePts"], group[-1]["sourcePts"]
        next_start = groups[region_index + 1][0]["sourcePts"] if (
            region_index + 1 < len(groups)) else None
        regions.append({
            "id": f"region-{region_index + 1:03d}",
            "boundaryBefore": "bounded-scan-start" if region_index == 0
                              else "hard-cut-candidate",
            "boundaryAfter": "hard-cut-candidate" if next_start is not None
                             else "bounded-scan-end",
            "startPtsInclusive": region_start,
            "endPtsExclusive": next_start,
            "lastObservedFramePts": region_last,
            "startSeconds": as_rational_dict(region_start * timebase),
            "lastObservedFrameSeconds": as_rational_dict(region_last * timebase),
            "frameCount": len(group),
            "firstFrameOrdinal": group[0]["sampleOrdinal"],
            "lastFrameOrdinal": group[-1]["sampleOrdinal"],
            "observations": _interval_summary(region_start, region_last,
                                              appearance=appearance, motion=motion,
                                              sparse=sparse),
            "reviewQuestions": _REVIEW_QUESTIONS,
            "interpretationStatus": "not-performed",
        })
    return {
        "status": "candidate-edit-regions",
        "framePtsAnomalies": [],
        "ignoredCutCandidatePts": [pts for pts in cut_pts if pts <= first or pts > last],
        "regions": regions,
    }


def build_shot_evidence(analysis_run: Path) -> dict[str, Any]:
    if analysis_run.name != "analysis-run.json":
        raise ValueError("expected analysis-run.json")
    manifest = _json_file(analysis_run, limit=262_144)
    settings = manifest.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("analysis run settings are missing")
    _validate_existing(analysis_run.parent, settings)
    source = _json_file(analysis_run.parent / "source-manifest.json", limit=4_194_304)
    reports = {}
    for key, (filename, version) in _REPORT_FILES.items():
        if key not in manifest["artifacts"]:
            continue
        if manifest["artifacts"][key] != filename:
            raise ValueError(f"analysis artifact path mismatch for {key}")
        value = _json_file(analysis_run.parent / filename, limit=4_194_304)
        if (value.get("schemaVersion") != version or
                value.get("sourceSha256") != settings["sourceSha256"] or
                value.get("sourceStreamIndex") != settings["streamIndex"] or
                value.get("sourceTimebase") != manifest["sourceTimebase"]):
            raise ValueError(f"{key} report provenance does not match analysis bundle")
        reports[key] = value
    if source["video"]["sourceTimebase"] != manifest["sourceTimebase"]:
        raise ValueError("source timebase does not match analysis run")
    cut_pts = [item["sourcePts"] for item in reports["cuts"]["candidates"]]
    for key in ("motion", "sparseFlow", "appearance"):
        if key in reports and reports[key].get("cutCandidatePts") != cut_pts:
            raise ValueError(f"{key} cut boundaries disagree with the primary cut report")
    segmentation = summarize_edit_regions(
        reports["frames"], reports["cuts"],
        appearance=reports.get("appearance"), motion=reports.get("motion"),
        sparse=reports.get("sparseFlow"),
    )
    return {
        "schemaVersion": SHOT_EVIDENCE_VERSION,
        "sourceSha256": settings["sourceSha256"],
        "sourceStreamIndex": settings["streamIndex"],
        "sourceTimebase": manifest["sourceTimebase"],
        "analysisRunSha256": sha256_file(analysis_run),
        "coverage": "bounded-from-start-not-necessarily-full-video",
        "status": segmentation["status"],
        "availableStages": sorted(reports),
        "cutDetector": reports["cuts"]["detector"],
        "framePtsAnomalies": segmentation["framePtsAnomalies"],
        "ignoredCutCandidatePts": segmentation["ignoredCutCandidatePts"],
        "regions": segmentation["regions"],
        "limits": "Regions split on *candidate* cuts; false positives and missed edits remain possible. Final region has no invented exclusive end PTS. No object, shot purpose, camera, lighting, or editing intent is inferred.",
    }
