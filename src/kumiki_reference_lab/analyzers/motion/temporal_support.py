"""Conservative fixed-image-grid support transitions across dense-flow pairs.

This only compares *where a measurement was available* at consecutive image
coordinates. It is not temporal feature tracking, an occlusion mask, or evidence
of a camera or semantic identity. No trajectories are inferred through gaps.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.motion.dense_review import validate_dense_review_report
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.contracts.analysis import DENSE_TEMPORAL_SUPPORT_VERSION


def analyze_dense_temporal_support(report: dict[str, Any]) -> dict[str, Any]:
    """Measure support transitions only on an unchanged fixed image grid.

    A disappearance at a fixed pixel can be caused by image translation,
    optical-flow failure, exposure, blur, low texture, cuts or occlusion. The
    heuristic labels below never assign a cause or match across a gap.
    """
    width, height, samples, pairs = validate_dense_review_report(report)
    try:
        serialized = json.dumps(report, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("dense temporal support requires finite JSON evidence") from exc

    results: list[dict[str, Any]] = []
    counts = {"support-drop-candidate": 0, "support-rise-candidate": 0}
    previous_cells: set[tuple[int, int]] | None = None
    skipped_cuts = 0
    for index, pair in enumerate(pairs):
        cells = {(v["x"], v["y"]) for v in pair["vectors"]}
        comparison = None
        is_cut = pair["status"] == "cut-boundary"
        if is_cut:
            skipped_cuts += 1
        elif previous_cells is not None:
            retained = len(previous_cells & cells)
            lost = len(previous_cells) - retained
            gained = len(cells) - retained
            # Conservative aggregate threshold: counts below ten are too
            # small to call a meaningful *drop*; no probability is estimated.
            status = ("support-drop-candidate" if len(previous_cells) >= 10 and
                      2 * len(cells) <= len(previous_cells) else
                      "support-rise-candidate" if len(cells) >= 10 and
                      2 * len(previous_cells) <= len(cells) else
                      "no-large-aggregate-change")
            if status in counts:
                counts[status] += 1
            comparison = {
                "status": status,
                "previousStartPts": pairs[index - 1]["startPts"],
                "previousEndPts": pairs[index - 1]["endPts"],
                "previousAccepted": len(previous_cells),
                "fixedGridRetained": retained,
                "fixedGridLost": lost,
                "fixedGridGained": gained,
                "interpretation": "fixed-grid-occupancy-only-not-feature-correspondence",
            }
        results.append({
            "startPts": pair["startPts"], "endPts": pair["endPts"],
            "deltaTimeSeconds": pair["deltaTimeSeconds"],
            "status": pair["status"], "acceptedCellCount": len(cells),
            "candidateCellCount": pair["candidateCount"],
            "rejected": dict(pair["rejected"]),
            "previousPairComparison": comparison,
        })
        # Explicitly reset at a cut: neither the cut nor the next pair can
        # be connected to pre-cut measurements.
        previous_cells = None if is_cut else cells

    return {
        "schemaVersion": DENSE_TEMPORAL_SUPPORT_VERSION,
        "sourceSha256": report["sourceSha256"],
        "inputReportCanonicalSha256": hashlib.sha256(serialized).hexdigest(),
        "sourceStreamIndex": report["sourceStreamIndex"],
        "sourceTimebase": report["sourceTimebase"],
        "sampleCount": len(samples),
        "analysisResolution": {"width": width, "height": height},
        "gridStepPixels": report["analyzer"]["gridStepPixels"],
        "diagnosticMethod": "consecutive-fixed-grid-support-v1",
        "sourceVerified": False,
        "semanticOcclusionVerified": False,
        "semanticIdentityVerified": False,
        "calibratedConfidence": False,
        "limits": "Fixed image-grid support occupancy, not feature tracks, pixel visibility, occlusion masks, physical camera motion or semantic reidentification. An observed support gap may also reflect translation, blur, low texture, exposure or estimator failure.",
        "summary": {
            "dropCandidates": counts["support-drop-candidate"],
            "riseCandidates": counts["support-rise-candidate"],
            "skippedCutBoundaries": skipped_cuts,
        },
        "pairs": results,
    }


def analyze_dense_temporal_support_file(path: Path) -> dict[str, Any]:
    """Read a bounded, duplicate-key-rejecting dense-flow JSON artifact."""
    return analyze_dense_temporal_support(_json_file(path, limit=4_000_000))
