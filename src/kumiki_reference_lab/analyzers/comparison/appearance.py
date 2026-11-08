"""Time-aligned appearance comparison without fabricated visual quality scores."""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
from statistics import mean, median
from typing import Any

from kumiki_reference_lab.contracts.analysis import APPEARANCE_COMPARISON_VERSION, APPEARANCE_VERSION
from kumiki_reference_lab.core.timebase import as_rational_dict


def _read_appearance_report(path: Path) -> tuple[dict[str, Any], str, list[tuple[Fraction, dict[str, Any]]]]:
    if not path.is_file() or path.stat().st_size > 16_000_000:
        raise ValueError("appearance report is missing or exceeds 16 MB")
    raw = path.read_bytes()
    try:
        def reject_constant(value: str) -> Any:
            raise ValueError("nonfinite JSON constant is prohibited: " + value)

        report = json.loads(raw, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("appearance report contains invalid JSON") from exc
    if not isinstance(report, dict) or report.get("schemaVersion") != APPEARANCE_VERSION:
        raise ValueError("both inputs must be versioned appearance reports")
    hash_value = report.get("sourceSha256")
    if not isinstance(hash_value, str) or len(hash_value) != 64 or any(
            digit not in "0123456789abcdef" for digit in hash_value):
        raise ValueError("appearance source hash is invalid")
    tb = report.get("sourceTimebase")
    if not isinstance(tb, dict) or type(tb.get("numerator")) is not int or type(tb.get("denominator")) is not int:
        raise ValueError("appearance timebase is invalid")
    if tb["numerator"] <= 0 or tb["denominator"] <= 0:
        raise ValueError("appearance timebase must be positive")
    timebase = Fraction(tb["numerator"], tb["denominator"])
    items = report.get("samples")
    if not isinstance(items, list) or not 2 <= len(items) <= 40:
        raise ValueError("appearance report must contain 2..40 samples")
    samples: list[tuple[Fraction, dict[str, Any]]] = []
    for item in items:
        if not isinstance(item, dict) or type(item.get("sourcePts")) is not int:
            raise ValueError("appearance report has an invalid source PTS")
        t = item.get("sourceSeconds")
        if (not isinstance(t, dict) or type(t.get("numerator")) is not int or
                type(t.get("denominator")) is not int or t["denominator"] <= 0 or
                Fraction(t["numerator"], t["denominator"]) != item["sourcePts"] * timebase):
            raise ValueError("appearance report timestamps disagree with source timebase")
        moment = item["sourcePts"] * timebase
        if samples and moment <= samples[-1][0]:
            raise ValueError("appearance sample source timestamps must be strictly increasing")
        a = item.get("appearance")
        if not isinstance(a, dict):
            raise ValueError("appearance sample has no measurements")
        required = ("meanLumaProxy", "meanRgb", "meanSaturation", "brightPixelFraction",
                    "chromaticPixelFraction", "hueHistogram12", "spatialGrid3x3")
        if any(key not in a for key in required):
            raise ValueError("appearance sample is missing required measurements")
        if (not isinstance(a["meanRgb"], list) or len(a["meanRgb"]) != 3 or
                not isinstance(a["hueHistogram12"], list) or len(a["hueHistogram12"]) != 12 or
                not isinstance(a["spatialGrid3x3"], list) or len(a["spatialGrid3x3"]) != 9):
            raise ValueError("appearance sample arrays have invalid lengths")
        scalar_values = [a[key] for key in ("meanLumaProxy", "meanSaturation",
                                              "brightPixelFraction", "chromaticPixelFraction")]
        scalar_values += a["meanRgb"] + a["hueHistogram12"]
        for cell in a["spatialGrid3x3"]:
            if not isinstance(cell, dict) or "meanLumaProxy" not in cell:
                raise ValueError("appearance grid is malformed")
            scalar_values.append(cell["meanLumaProxy"])
        if any(type(value) not in (int, float) or not math.isfinite(value) or
               not 0 <= value <= 1 for value in scalar_values):
            raise ValueError("appearance measurements must be finite normalized quantities")
        if sum(a["hueHistogram12"]) > 1.001:
            raise ValueError("appearance hue histogram exceeds normalized mass")
        if any(cell.get("row") != i // 3 or cell.get("column") != i % 3
               for i, cell in enumerate(a["spatialGrid3x3"])):
            raise ValueError("appearance grid cells must use canonical row-major coordinates")
        samples.append((moment, a))
    return report, hashlib.sha256(raw).hexdigest(), samples


def compare_appearance(
    reference_path: Path, candidate_path: Path, *, reference_anchor_ms: int,
    candidate_anchor_ms: int, tolerance_ms: int = 150, time_scale: str = "1",
) -> dict[str, Any]:
    """Pair source PTS by a declared time transform, then compare RGB statistics."""
    if any(type(v) is not int or not -3_600_000 <= v <= 3_600_000
           for v in (reference_anchor_ms, candidate_anchor_ms)):
        raise ValueError("comparison anchors must be integer milliseconds within one hour")
    if type(tolerance_ms) is not int or not 0 <= tolerance_ms <= 5000:
        raise ValueError("comparison tolerance must be 0..5000 milliseconds")
    if not isinstance(time_scale, str) or len(time_scale) > 32:
        raise ValueError("invalid time scale")
    try:
        scale = Fraction(time_scale)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("time scale must be a decimal or positive rational") from exc
    if not Fraction(1, 4) <= scale <= 4 or scale.denominator > 1_000_000:
        raise ValueError("time scale must be between 1/4 and 4 with bounded precision")
    reference, ref_hash, ref_samples = _read_appearance_report(reference_path)
    candidate, candidate_hash, cand_samples = _read_appearance_report(candidate_path)

    ref_anchor = Fraction(reference_anchor_ms, 1000)
    candidate_anchor = Fraction(candidate_anchor_ms, 1000)
    tolerance = Fraction(tolerance_ms, 1000)
    # Optimal monotonic one-to-one pairing: maximize count, then minimize the
    # sum of absolute timestamp errors. A nearest-only greedy assignment can
    # incorrectly lose feasible pairs when frames compete for one reference.
    n, m = len(cand_samples), len(ref_samples)
    empty: tuple[int, Fraction, tuple[tuple[int, int, Fraction], ...]] = (0, Fraction(0), ())
    dp = [[empty for _ in range(m + 1)] for _ in range(n + 1)]

    def better(a: tuple, b: tuple) -> tuple:
        if a[0] != b[0]:
            return a if a[0] > b[0] else b
        if a[1] != b[1]:
            return a if a[1] < b[1] else b
        return a if a[2] <= b[2] else b

    for ci in range(1, n + 1):
        candidate_time = cand_samples[ci - 1][0]
        expected_time = ref_anchor + (candidate_time - candidate_anchor) * scale
        for ri in range(1, m + 1):
            best = better(dp[ci - 1][ri], dp[ci][ri - 1])
            error = ref_samples[ri - 1][0] - expected_time
            if abs(error) <= tolerance:
                count, total, matches = dp[ci - 1][ri - 1]
                proposed = (count + 1, total + abs(error),
                            matches + ((ci - 1, ri - 1, error),))
                best = better(proposed, best)
            dp[ci][ri] = best
    matched = dp[n][m][2]

    pairs = []
    for ci, ri, error in matched:
        _, observed = cand_samples[ci]
        _, source = ref_samples[ri]
        rgb_distance = math.sqrt(mean((b - a) ** 2 for a, b in zip(
            source["meanRgb"], observed["meanRgb"], strict=True)))
        grid_mae = mean(abs(b["meanLumaProxy"] - a["meanLumaProxy"])
                        for a, b in zip(source["spatialGrid3x3"],
                                        observed["spatialGrid3x3"], strict=True))
        hue_difference = .5 * sum(abs(b - a) for a, b in zip(
            source["hueHistogram12"], observed["hueHistogram12"], strict=True))
        pairs.append({
            "referencePts": reference["samples"][ri]["sourcePts"],
            "candidatePts": candidate["samples"][ci]["sourcePts"],
            "signedAlignmentErrorSeconds": as_rational_dict(error),
            "meanLumaProxyDelta": round(observed["meanLumaProxy"] - source["meanLumaProxy"], 6),
            "meanRgbDistance": round(rgb_distance, 6),
            "spatialGridLumaMae": round(grid_mae, 6),
            "hueHistogramTotalVariation": round(hue_difference, 6),
            "meanSaturationDelta": round(observed["meanSaturation"] - source["meanSaturation"], 6),
            "brightPixelFractionDelta": round(observed["brightPixelFraction"] - source["brightPixelFraction"], 6),
            "chromaticPixelFractionDelta": round(observed["chromaticPixelFraction"] - source["chromaticPixelFraction"], 6),
        })

    summary = None
    if pairs:
        summary = {"meanAbsoluteLumaProxyDelta": round(mean(abs(p["meanLumaProxyDelta"]) for p in pairs), 6),
                   "meanRgbDistance": round(mean(p["meanRgbDistance"] for p in pairs), 6),
                   "medianSpatialGridLumaMae": round(median(p["spatialGridLumaMae"] for p in pairs), 6),
                   "meanHueHistogramTotalVariation": round(mean(p["hueHistogramTotalVariation"] for p in pairs), 6)}
    return {
        "schemaVersion": APPEARANCE_COMPARISON_VERSION,
        "reference": {"sourceSha256": reference["sourceSha256"], "reportSha256": ref_hash,
                      "sourceTimebase": reference["sourceTimebase"],
                      "sampleCount": len(ref_samples)},
        "candidate": {"sourceSha256": candidate["sourceSha256"], "reportSha256": candidate_hash,
                      "sourceTimebase": candidate["sourceTimebase"],
                      "sampleCount": len(cand_samples)},
        "alignment": {"method": "explicit-two-anchor-max-cardinality-min-error-monotonic-pts-v1",
                      "referenceAnchorSeconds": as_rational_dict(ref_anchor),
                      "candidateAnchorSeconds": as_rational_dict(candidate_anchor),
                      "scale": as_rational_dict(scale), "toleranceSeconds": as_rational_dict(tolerance),
                      "oneToOne": True},
        "comparison": {"status": "measured-pairs" if pairs else "no-aligned-pairs",
                       "matchedCount": len(pairs),
                       "unmatchedReferenceCount": len(ref_samples) - len(matched),
                       "unmatchedCandidateCount": len(cand_samples) - len(matched),
                       "physicalPhotometry": False,
                       "qualityVerdict": "not-performed",
                       "limits": "display-referred RGB proxies and manually aligned timestamps only; no per-pixel visual similarity, semantic content, camera or lighting ground truth, or artistic-quality score"},
        "pairs": pairs, "summary": summary,
    }
