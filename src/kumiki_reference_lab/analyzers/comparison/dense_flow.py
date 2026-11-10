"""Compare source-PTS-aligned dense *image-plane* flow from two video reports.

No sample is secretly reused, no missing vector is scored as zero error, and
fixed grid cells are never presented as physical feature correspondences.
"""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
from statistics import mean, median
from typing import Any

from kumiki_reference_lab.analyzers.comparison.timing import align_source_times
from kumiki_reference_lab.analyzers.motion.dense_review import validate_dense_review_report
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.contracts.analysis import DENSE_FLOW_COMPARISON_VERSION
from kumiki_reference_lab.core.timebase import as_rational_dict


def _canonical_hash(value: dict[str, Any]) -> str:
    try:
        content = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("dense comparison requires finite JSON reports") from exc
    return hashlib.sha256(content).hexdigest()


def _finite_duration_seconds(value: Fraction) -> float:
    """Reject unrepresentable rates before converting pixel displacement."""
    try:
        seconds = float(value)
    except OverflowError as exc:
        raise ValueError("dense comparison duration cannot be represented safely") from exc
    if not math.isfinite(seconds) or not 1e-9 <= seconds <= 3600:
        raise ValueError("dense comparison duration is outside finite supported bounds")
    return seconds


def compare_dense_flow(
    reference: dict[str, Any], candidate: dict[str, Any], *,
    reference_anchor_ms: int, candidate_anchor_ms: int,
    tolerance_ms: int = 150, time_scale: str = "1",
) -> dict[str, Any]:
    """Compare observed displacement *rates* on the same declared image grid."""
    rw, rh, _, reference_pairs = validate_dense_review_report(reference)
    cw, ch, _, candidate_pairs = validate_dense_review_report(candidate)
    reference_grid = reference["analyzer"]["gridStepPixels"]
    if ((rw, rh) != (cw, ch) or
            reference_grid != candidate["analyzer"]["gridStepPixels"]):
        raise ValueError("dense comparison requires identical analysis resolution/grid step")

    reference_tb = Fraction(reference["sourceTimebase"]["numerator"],
                            reference["sourceTimebase"]["denominator"])
    candidate_tb = Fraction(candidate["sourceTimebase"]["numerator"],
                            candidate["sourceTimebase"]["denominator"])
    reference_eligible = [p for p in reference_pairs if p["status"] != "cut-boundary"]
    candidate_eligible = [p for p in candidate_pairs if p["status"] != "cut-boundary"]

    def center(pair: dict[str, Any], timebase: Fraction) -> Fraction:
        return Fraction(pair["startPts"] + pair["endPts"], 2) * timebase

    alignment, matches = align_source_times(
        [center(p, reference_tb) for p in reference_eligible],
        [center(p, candidate_tb) for p in candidate_eligible],
        reference_anchor_ms=reference_anchor_ms,
        candidate_anchor_ms=candidate_anchor_ms,
        tolerance_ms=tolerance_ms, time_scale=time_scale,
    )
    all_errors: list[float] = []
    compared = incomparable = disjoint = insufficient_overlap = total_shared = 0
    compared_pairs: list[dict[str, Any]] = []
    for ci, ri, alignment_error in matches:
        r, c = reference_eligible[ri], candidate_eligible[ci]
        r_duration = (r["endPts"] - r["startPts"]) * reference_tb
        c_duration = (c["endPts"] - c["startPts"]) * candidate_tb * alignment["scale"]
        r_seconds, c_seconds = (_finite_duration_seconds(r_duration),
                                _finite_duration_seconds(c_duration))
        mapped_start = (alignment["referenceAnchor"] +
                        (c["startPts"] * candidate_tb - alignment["candidateAnchor"]) *
                        alignment["scale"])
        mapped_end = mapped_start + c_duration
        r_start, r_end = r["startPts"] * reference_tb, r["endPts"] * reference_tb
        overlap = min(r_end, mapped_end) - max(r_start, mapped_start)
        time_overlaps = overlap > 0
        sufficient_overlap = overlap >= min(r_duration, c_duration) / 2
        r_vectors = {(v["x"], v["y"]): v for v in r["vectors"]}
        c_vectors = {(v["x"], v["y"]): v for v in c["vectors"]}
        shared_coords = sorted(r_vectors.keys() & c_vectors.keys())
        union_count = len(r_vectors.keys() | c_vectors.keys())
        duration_comparable = (r_duration <= 2 * c_duration and
                               c_duration <= 2 * r_duration)
        errors: list[float] = []
        if duration_comparable and sufficient_overlap:
            for coordinate in shared_coords:
                rv, cv = r_vectors[coordinate], c_vectors[coordinate]
                rx, ry = rv["dx"] / r_seconds, rv["dy"] / r_seconds
                cx, cy = cv["dx"] / c_seconds, cv["dy"] / c_seconds
                errors.append(math.hypot(rx - cx, ry - cy))
            if errors:
                all_errors.extend(errors)
                compared += 1
                total_shared += len(errors)
        elif not time_overlaps:
            disjoint += 1
        elif not sufficient_overlap:
            insufficient_overlap += 1
        else:
            incomparable += 1
        compared_pairs.append({
            "referenceStartPts": r["startPts"], "referenceEndPts": r["endPts"],
            "candidateStartPts": c["startPts"], "candidateEndPts": c["endPts"],
            "signedAlignmentErrorSeconds": as_rational_dict(alignment_error),
            "referenceDurationSeconds": as_rational_dict(r_duration),
            "candidateMappedDurationSeconds": as_rational_dict(c_duration),
            "referenceAcceptedCellCount": len(r_vectors),
            "candidateAcceptedCellCount": len(c_vectors),
            "sharedCellCount": len(shared_coords),
            "referenceOnlyCellCount": len(r_vectors) - len(shared_coords),
            "candidateOnlyCellCount": len(c_vectors) - len(shared_coords),
            "supportJaccardFraction": round(len(shared_coords) / union_count, 6)
            if union_count else None,
            "status": ("time-disjoint" if not time_overlaps else
                       "insufficient-time-overlap" if not sufficient_overlap else
                       "duration-incomparable" if not duration_comparable else
                       "observed-comparison" if errors else "no-shared-cells"),
            "meanGridVelocityDifferencePxPerSecond": round(mean(errors), 5)
            if errors else None,
            "medianGridVelocityDifferencePxPerSecond": round(median(errors), 5)
            if errors else None,
        })

    return {
        "schemaVersion": DENSE_FLOW_COMPARISON_VERSION,
        "reference": {"sourceSha256": reference["sourceSha256"],
                      "reportCanonicalSha256": _canonical_hash(reference),
                      "sourceStreamIndex": reference["sourceStreamIndex"],
                      "sourceTimebase": reference["sourceTimebase"]},
        "candidate": {"sourceSha256": candidate["sourceSha256"],
                      "reportCanonicalSha256": _canonical_hash(candidate),
                      "sourceStreamIndex": candidate["sourceStreamIndex"],
                      "sourceTimebase": candidate["sourceTimebase"]},
        "grid": {"width": rw, "height": rh, "stepPixels": reference_grid},
        "alignment": {"method": "explicit-anchor-monotonic-pair-midpoints-v1",
                      "referenceAnchorSeconds": as_rational_dict(alignment["referenceAnchor"]),
                      "candidateAnchorSeconds": as_rational_dict(alignment["candidateAnchor"]),
                      "scale": as_rational_dict(alignment["scale"]),
                      "toleranceSeconds": as_rational_dict(alignment["tolerance"]),
                      "oneToOne": True},
        "comparison": {
            "status": "aligned-pairs" if matches else "no-aligned-pairs",
            "matchedPairCount": len(matches),
            "unmatchedReferencePairCount": len(reference_eligible) - len(matches),
            "unmatchedCandidatePairCount": len(candidate_eligible) - len(matches),
            "referenceCutPairCount": len(reference_pairs) - len(reference_eligible),
            "candidateCutPairCount": len(candidate_pairs) - len(candidate_eligible),
            "sourceVerified": False,
            "cameraMotionVerified": False,
            "semanticIdentityVerified": False,
            "qualityVerdict": "not-performed",
            "limits": "Aligned source PTS and fixed image-grid velocities, not pixel-to-pixel correspondences or physical tracks. Missing/no-overlap cells are unscored; camera, depth, semantics, timing equivalence and artistic quality are not verified.",
        },
        "pairs": compared_pairs,
        "summary": {
            "comparedPairCount": compared,
            "durationIncomparableCount": incomparable,
            "timeDisjointCount": disjoint,
            "insufficientOverlapCount": insufficient_overlap,
            "sharedCellCount": total_shared,
            "meanGridVelocityDifferencePxPerSecond": round(mean(all_errors), 5)
            if all_errors else None,
            "medianGridVelocityDifferencePxPerSecond": round(median(all_errors), 5)
            if all_errors else None,
        },
    }


def compare_dense_flow_files(
    reference_path: Path, candidate_path: Path, *,
    reference_anchor_ms: int, candidate_anchor_ms: int,
    tolerance_ms: int = 150, time_scale: str = "1",
) -> dict[str, Any]:
    """Read bounded local reports, rejecting symlinks and duplicate keys."""
    return compare_dense_flow(
        _json_file(reference_path, limit=4_000_000),
        _json_file(candidate_path, limit=4_000_000),
        reference_anchor_ms=reference_anchor_ms,
        candidate_anchor_ms=candidate_anchor_ms,
        tolerance_ms=tolerance_ms, time_scale=time_scale,
    )
