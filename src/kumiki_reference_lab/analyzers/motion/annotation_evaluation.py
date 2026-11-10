"""Compare dense image-plane flow to independent, user-supplied grid labels.

The labels are *declared* evidence, not independently validated ground truth.
Do not infer camera movement, physical depth, semantic identity or aesthetic
quality from agreement with manually or procedurally supplied displacements.
"""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
from statistics import mean, median
from typing import Any

from kumiki_reference_lab.analyzers.motion.dense_review import validate_dense_review_report
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.contracts.analysis import (
    DENSE_FLOW_ANNOTATIONS_VERSION, DENSE_FLOW_EVALUATION_VERSION,
)


def _canonical_hash(value: dict[str, Any]) -> str:
    try:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ValueError("flow evaluation requires finite JSON inputs") from exc
    return hashlib.sha256(payload).hexdigest()


def _bounded_number(value: Any, name: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"flow annotation {name} must be finite numeric evidence")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"flow annotation {name} must be finite numeric evidence") from exc
    if not math.isfinite(number) or abs(number) > 240:
        raise ValueError(f"flow annotation {name} is nonfinite or outside bounded pixels")
    return number


def evaluate_dense_flow_annotations(
    dense: dict[str, Any], annotations: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate exact grid-point/PTS matches; expose missing support separately."""
    width, height, _, dense_pairs = validate_dense_review_report(dense)
    if (not isinstance(annotations, dict) or
            set(annotations) != {"schemaVersion", "sourceSha256", "sourceStreamIndex",
                                 "sourceTimebase", "analysisResolution", "gridStepPixels",
                                 "provenance", "pairLabels"} or
            annotations["schemaVersion"] != DENSE_FLOW_ANNOTATIONS_VERSION or
            annotations["sourceSha256"] != dense["sourceSha256"] or
            type(annotations["sourceStreamIndex"]) is not int or
            annotations["sourceStreamIndex"] != dense["sourceStreamIndex"]):
        raise ValueError("flow annotations do not match the bounded source evidence")
    tb = annotations.get("sourceTimebase")
    source_tb = dense["sourceTimebase"]
    if (not isinstance(tb, dict) or set(tb) != {"numerator", "denominator"} or
            type(tb["numerator"]) is not int or type(tb["denominator"]) is not int or
            tb["numerator"] <= 0 or tb["denominator"] <= 0 or
            Fraction(tb["numerator"], tb["denominator"]) !=
            Fraction(source_tb["numerator"], source_tb["denominator"])):
        raise ValueError("flow annotation source timebase does not match")
    resolution = annotations.get("analysisResolution")
    step = dense["analyzer"]["gridStepPixels"]
    if (not isinstance(resolution, dict) or set(resolution) != {"width", "height"} or
            type(resolution["width"]) is not int or type(resolution["height"]) is not int or
            resolution != {"width": width, "height": height} or
            type(annotations.get("gridStepPixels")) is not int or
            annotations["gridStepPixels"] != step):
        raise ValueError("flow annotation grid does not match analysis geometry")
    provenance = annotations.get("provenance")
    if (not isinstance(provenance, dict) or set(provenance) != {"kind", "reviewStatus"} or
            provenance["kind"] not in ("independently-generated", "human-annotated") or
            provenance["reviewStatus"] not in ("unverified", "reviewed")):
        raise ValueError("flow annotation provenance must be declared, not certified")
    label_pairs = annotations.get("pairLabels")
    if (not isinstance(label_pairs, list) or not 1 <= len(label_pairs) <= len(dense_pairs)):
        raise ValueError("flow evaluation requires bounded labeled pairs")

    pair_lookup = {(p["startPts"], p["endPts"]): (i, p)
                   for i, p in enumerate(dense_pairs)}
    labeled_count = observed_count = 0
    errors: list[float] = []
    evaluated: list[dict[str, Any]] = []
    previous_index = -1
    for item in label_pairs:
        if (not isinstance(item, dict) or set(item) != {"startPts", "endPts", "points"} or
                type(item["startPts"]) is not int or type(item["endPts"]) is not int):
            raise ValueError("flow annotation pair timestamps are invalid")
        identified = pair_lookup.get((item["startPts"], item["endPts"]))
        if identified is None or identified[0] <= previous_index:
            raise ValueError("flow annotation pairs must match ascending observed source PTS")
        index, pair = identified
        previous_index = index
        if pair["status"] == "cut-boundary":
            raise ValueError("flow annotations cannot evaluate across cut candidates")
        points = item["points"]
        if not isinstance(points, list) or not 1 <= len(points) <= 512:
            raise ValueError("flow annotation point count must be 1..512")
        observed = {(v["x"], v["y"]): v for v in pair["vectors"]}
        point_results: list[dict[str, Any]] = []
        pair_errors: list[float] = []
        seen: set[tuple[int, int]] = set()
        for point in points:
            if (not isinstance(point, dict) or set(point) != {"x", "y", "dx", "dy"} or
                    type(point["x"]) is not int or type(point["y"]) is not int):
                raise ValueError("flow annotation point must be a grid observation")
            x, y = point["x"], point["y"]
            if (x not in range(step // 2, width - step // 2, step) or
                    y not in range(step // 2, height - step // 2, step) or
                    (x, y) in seen):
                raise ValueError("flow annotation coordinates must be distinct grid points")
            seen.add((x, y))
            dx, dy = _bounded_number(point["dx"], "dx"), _bounded_number(point["dy"], "dy")
            vector = observed.get((x, y))
            error = None
            if vector is not None:
                error = math.hypot(vector["dx"] - dx, vector["dy"] - dy)
                errors.append(error)
                pair_errors.append(error)
                observed_count += 1
            point_results.append({
                "x": x, "y": y, "labeledDx": dx, "labeledDy": dy,
                "observedDx": vector["dx"] if vector is not None else None,
                "observedDy": vector["dy"] if vector is not None else None,
                "endpointErrorPixels": round(error, 5) if error is not None else None,
                "status": "observed" if vector is not None else "not-observed",
            })
        labeled_count += len(points)
        evaluated.append({
            "startPts": pair["startPts"], "endPts": pair["endPts"],
            "deltaTimeSeconds": pair["deltaTimeSeconds"],
            "labeledCount": len(points), "observedCount": len(pair_errors),
            "missingCount": len(points) - len(pair_errors),
            "coverageFraction": round(len(pair_errors) / len(points), 6),
            "meanEndpointErrorPixels": round(mean(pair_errors), 5) if pair_errors else None,
            "points": point_results,
        })

    return {
        "schemaVersion": DENSE_FLOW_EVALUATION_VERSION,
        "inputHashes": {"denseFlowCanonicalSha256": _canonical_hash(dense),
                        "annotationsCanonicalSha256": _canonical_hash(annotations)},
        "sourceSha256": dense["sourceSha256"],
        "sourceStreamIndex": dense["sourceStreamIndex"],
        "sourceTimebase": dense["sourceTimebase"],
        "analysisResolution": {"width": width, "height": height},
        "gridStepPixels": step,
        "provenance": dict(provenance),
        "sourceVerified": False,
        "annotationsIndependentlyVerified": False,
        "physicalCameraVerified": False,
        "semanticIdentityVerified": False,
        "qualityVerdict": "not-performed",
        "limits": "Agreement with declared annotations only, at exact PTS and fixed grid points; missing vectors are counted, not assigned zero error. No source re-decode, independent annotation QA, physical camera/depth reconstruction, semantic identity or artistic approval.",
        "summary": {
            "labeledCount": labeled_count, "observedCount": observed_count,
            "missingCount": labeled_count - observed_count,
            "coverageFraction": round(observed_count / labeled_count, 6),
            "meanEndpointErrorPixels": round(mean(errors), 5) if errors else None,
            "medianEndpointErrorPixels": round(median(errors), 5) if errors else None,
        },
        "pairs": evaluated,
    }


def evaluate_dense_flow_annotations_files(
    dense_path: Path, annotations_path: Path,
) -> dict[str, Any]:
    """Reject duplicate keys and oversized local inputs before evaluating."""
    return evaluate_dense_flow_annotations(
        _json_file(dense_path, limit=4_000_000),
        _json_file(annotations_path, limit=1_000_000),
    )
