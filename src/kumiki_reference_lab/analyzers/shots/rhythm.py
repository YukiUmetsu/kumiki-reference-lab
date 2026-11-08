"""Measured intervals between candidate hard-cut boundaries, without story claims.

The first and final bounded observation regions are censored: the scan need
not begin or end at a genuine edit. Only *interior* cut-to-cut gaps are used.
"""

from __future__ import annotations

import statistics
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.shots.evidence import build_shot_evidence
from kumiki_reference_lab.contracts.analysis import EDIT_RHYTHM_VERSION
from kumiki_reference_lab.core.timebase import as_rational_dict


def _fraction(value: dict[str, int]) -> Fraction:
    return Fraction(value["numerator"], value["denominator"])


def summarize_edit_rhythm(regions: list[dict[str, Any]]) -> dict[str, Any]:
    """Use exact rational times between successive *candidate* edit boundaries."""
    cuts = regions[1:]
    points = [_fraction(cut["startSeconds"]) for cut in cuts]
    if any(a >= b for a, b in zip(points, points[1:])):
        raise ValueError("candidate video cuts must have strictly increasing source time")
    intervals = []
    durations = []
    for n in range(1, len(cuts)):
        before, after = cuts[n - 1], cuts[n]
        start, end = points[n - 1], points[n]
        duration = end - start
        previous = durations[-1] if durations else None
        ratio = duration / previous if previous is not None else None
        intervals.append({
            "regionId": before["id"],
            "fromVideoCutCandidatePts": before["startPtsInclusive"],
            "toVideoCutCandidatePts": after["startPtsInclusive"],
            "fromSeconds": before["startSeconds"],
            "toSeconds": after["startSeconds"],
            "durationSeconds": as_rational_dict(duration),
            "durationRatioToPrevious": as_rational_dict(ratio) if ratio is not None else None,
            "changeVsPrevious": (
                "not-applicable-first-interval" if previous is None else
                "shorter" if duration < previous else
                "longer" if duration > previous else "same"),
            "interpretationStatus": "not-performed",
        })
        durations.append(duration)
    return {
        "videoCutCandidateCount": len(cuts),
        "observedInterCutIntervalCount": len(intervals),
        "status": "bounded-candidate-inter-cut-intervals" if intervals else
                  "insufficient-candidate-cuts-for-inter-cut-intervals",
        "intervals": intervals,
        "durationRangeSeconds": {
            "minimum": as_rational_dict(min(durations)) if durations else None,
            "median": as_rational_dict(statistics.median(durations)) if durations else None,
            "maximum": as_rational_dict(max(durations)) if durations else None,
        },
    }


def edit_rhythm_from_verified_shots(evidence: dict[str, Any]) -> dict[str, Any]:
    """Project already verified shot evidence into pure edit timing measurements."""
    if evidence["status"] != "candidate-edit-regions":
        raise ValueError("edit rhythm requires reliable original video presentation PTS")
    measured = summarize_edit_rhythm(evidence["regions"])
    return {
        "schemaVersion": EDIT_RHYTHM_VERSION,
        "sourceSha256": evidence["sourceSha256"],
        "analysisRunSha256": evidence["analysisRunSha256"],
        "sourceStreamIndex": evidence["sourceStreamIndex"],
        "sourceTimebase": evidence["sourceTimebase"],
        **measured,
        "censoring": "scan-start-may-be-mid-shot;final-region-has-no-verified-end",
        "cutStatus": "algorithmic-hard-cut-candidates-not-verified-edits",
        "qualityVerdict": "not-performed",
        "limits": "Only exact gaps between consecutive candidate cut PTS are measured. No claim is made about completed shots, cut intent, pace preference, film rhythm quality, or edits beyond the bounded scan.",
    }


def build_edit_rhythm(analysis_run: Path) -> dict[str, Any]:
    """Extract temporal cadence measurements from a checksum-verified run."""
    return edit_rhythm_from_verified_shots(build_shot_evidence(analysis_run))
