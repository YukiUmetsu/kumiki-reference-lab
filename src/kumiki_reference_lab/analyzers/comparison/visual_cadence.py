"""Observed edit, image-motion and display-brightness cadence, never camera/lighting inference."""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.contracts.analysis import APPEARANCE_VERSION, IMAGE_MOTION_VERSION


SCHEMA_VERSION = "kumiki.visual-cadence.v1"
_MAX_BYTES = 2_097_152


def load_cadence_input(path: Path) -> dict[str, Any]:
    """Read a bounded regular JSON artifact; never follow a supplied symlink."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BYTES:
        raise ValueError(f"cadence input must be a regular JSON file of at most 2 MiB: {path}")

    def distinct_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"duplicate cadence JSON key: {key}")
            obj[key] = value
        return obj

    try:
        result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=distinct_keys,
                            parse_constant=lambda value: (_ for _ in ()).throw(
                                ValueError(f"non-finite JSON value: {value}")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"invalid cadence JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise ValueError("cadence input must be a JSON object")
    return result


def _rational(value: Any, context: str) -> Fraction:
    if (not isinstance(value, dict) or set(value) != {"numerator", "denominator"}
            or type(value["numerator"]) is not int or type(value["denominator"]) is not int
            or not 1 <= value["denominator"] <= 1_000_000_000_000
            or abs(value["numerator"]) > 1_000_000_000_000):
        raise ValueError(f"{context} requires a positive-denominator rational")
    return Fraction(value["numerator"], value["denominator"])


def _measurement(value: Any, context: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError(f"{context} must be a finite number")
    return float(value)


def _validated_pairs(report: dict[str, Any], *, kind: str) -> tuple[list[dict[str, Any]], Fraction, int, int]:
    required_version = IMAGE_MOTION_VERSION if kind == "motion" else APPEARANCE_VERSION
    if report.get("schemaVersion") != required_version:
        raise ValueError(f"{kind} version is not supported")
    start_seconds = report.get("scanStartSeconds", 0)
    if (type(start_seconds) is not int or start_seconds < 0 or start_seconds > 119):
        raise ValueError(f"{kind} scan starting offset invalid")
    expected_coverage = ("bounded-source-window-not-necessarily-full-video" if start_seconds
                         else "bounded-from-start-not-necessarily-full-video")
    if report.get("coverage") != expected_coverage:
        raise ValueError(f"{kind} source coverage is not recognized")
    timebase = _rational(report.get("sourceTimebase"), f"{kind} timebase")
    if timebase <= 0 or timebase > 1:
        raise ValueError(f"{kind} source timebase must be positive and at most one second")
    samples = report.get("samples")
    pairs = report.get("pairs" if kind == "motion" else "changes")
    cuts = report.get("cutCandidatePts")
    if (not isinstance(samples, list) or not 2 <= len(samples) <= 120
            or not isinstance(pairs, list) or len(pairs) != len(samples) - 1
            or not isinstance(cuts, list) or len(cuts) > 40000
            or any(type(pts) is not int or abs(pts) > 2**63 - 1 for pts in cuts)
            or cuts != sorted(set(cuts))):
        raise ValueError(f"{kind} requires ordered samples, pairs and cut candidates")
    pts = [sample.get("sourcePts") if isinstance(sample, dict) else None for sample in samples]
    if (any(type(p) is not int or abs(p) > 2**63 - 1 for p in pts)
            or any(b <= a for a, b in zip(pts, pts[1:]))):
        raise ValueError(f"{kind} samples must have increasing source PTS")
    if (type(report.get("scanWindowSeconds")) is not int or
            not 1 <= report["scanWindowSeconds"] <= 30):
        raise ValueError(f"{kind} scan window is invalid")
    if start_seconds + report["scanWindowSeconds"] > 120:
        raise ValueError(f"{kind} decoded source prefix exceeds budget")
    if not 0 < (pts[-1] - pts[0]) * timebase <= report["scanWindowSeconds"] + 1:
        raise ValueError(f"{kind} observed span exceeds its declared scan window")
    for index, pair in enumerate(pairs):
        if (not isinstance(pair, dict) or pair.get("startPts") != pts[index]
                or pair.get("endPts") != pts[index + 1]
                or _rational(pair.get("deltaTimeSeconds"), f"{kind} pair duration") !=
                (pts[index + 1] - pts[index]) * timebase):
            raise ValueError(f"{kind} pair timestamps must match their source samples")
        if (pts[index + 1] - pts[index]) * timebase < Fraction(1, 1_000_000_000):
            raise ValueError(f"{kind} sample interval too small for stable rate reporting")
        crossing = any(pts[index] < cut <= pts[index + 1] for cut in cuts)
        if (pair.get("status") == "cut-boundary") != crossing:
            raise ValueError(f"{kind} cut boundaries contradict the cut candidates")
        if kind == "motion":
            valid = pair.get("status") == "measured-image-translation"
            if pair.get("status") not in {"measured-image-translation", "cut-boundary",
                                          "unobservable-low-texture", "ambiguous-correlation"}:
                raise ValueError("unknown motion pair status")
            for field in ("dxNormalized", "dyNormalized"):
                if valid:
                    if not -2 <= _measurement(pair.get(field), field) <= 2:
                        raise ValueError("motion displacement outside conservative range")
                elif pair.get(field) is not None:
                    raise ValueError("unobservable motion pair cannot contain displacement")
        else:
            valid = pair.get("status") == "measured-display-appearance-change"
            if pair.get("status") not in {"measured-display-appearance-change", "cut-boundary"}:
                raise ValueError("unknown appearance pair status")
            delta = pair.get("meanLumaProxyDelta")
            if valid:
                if not -1 <= _measurement(delta, "meanLumaProxyDelta") <= 1:
                    raise ValueError("appearance luma delta out of range")
            elif delta is not None:
                raise ValueError("cut boundary cannot contain a luma delta")
    return pairs, timebase, pts[0], pts[-1]


def _summarize(report: dict[str, Any], *, kind: str, threshold: float) -> dict[str, Any]:
    pairs, timebase, start, end = _validated_pairs(report, kind=kind)
    window = float((end - start) * timebase)
    valid_duration = 0.0
    active_duration = 0.0
    active_runs = 0
    active_before = False
    observed_speeds: list[float] = []
    measured_displacement = 0.0
    for pair in pairs:
        valid = pair["status"] == ("measured-image-translation" if kind == "motion"
                                   else "measured-display-appearance-change")
        if not valid:
            active_before = False
            continue
        seconds = float(_rational(pair["deltaTimeSeconds"], "pair duration"))
        speed = (math.hypot(pair["dxNormalized"], pair["dyNormalized"]) / seconds
                 if kind == "motion" else abs(pair["meanLumaProxyDelta"]) / seconds)
        observed_speeds.append(speed)
        measured_displacement += speed * seconds
        valid_duration += seconds
        active = speed >= threshold
        if active:
            active_duration += seconds
            if not active_before:
                active_runs += 1
        active_before = active
    cut_count = sum(start < cut <= end for cut in report["cutCandidatePts"])
    return {
        "sampledSpanSeconds": round(window, 6),
        "measuredPairSeconds": round(valid_duration, 6),
        "measuredPairFraction": round(valid_duration / window, 6),
        "pairCount": len(pairs),
        "measuredPairCount": len(observed_speeds),
        "unmeasurablePairCount": len(pairs) - len(observed_speeds),
        "thresholdPerSecond": threshold,
        "activeTimeFractionOfMeasured": (round(active_duration / valid_duration, 6)
                                         if valid_duration else None),
        "activeRunCountInSampledSpan": active_runs if observed_speeds else None,
        "activeRunsPerSampledMinute": (round(active_runs * 60 / window, 5)
                                       if observed_speeds else None),
        "timeWeightedMeanSpeedPerSecond": (round(measured_displacement / valid_duration, 6)
                                            if valid_duration else None),
        "cutCandidateCount": cut_count,
        "cutCandidatesPerSampledMinute": round(cut_count * 60 / window, 5),
        "frequencyInterpretation": "sampled proxy runs/candidates per sampled minute, not camera or lighting events",
    }


def summarize_visual_cadence(motion: dict[str, Any], appearance: dict[str, Any], *,
                             image_motion_threshold: float = 0.01,
                             luma_change_threshold: float = 0.05) -> dict[str, Any]:
    """Compute source-matched, independently sampled descriptive cadence rates.

    The two analyzers may use different frame samplings. No joint temporal
    correlation or motion-versus-light attribution is asserted.
    """
    for name, threshold in (("image-motion", image_motion_threshold),
                            ("display-luma", luma_change_threshold)):
        if not 0 < _measurement(threshold, name) <= 10:
            raise ValueError(f"{name} threshold must be positive and at most ten")
    source_sha = motion.get("sourceSha256")
    if (not isinstance(source_sha, str) or len(source_sha) != 64 or
            any(c not in "0123456789abcdef" for c in source_sha)):
        raise ValueError("motion source SHA-256 must be a lowercase digest")
    if (appearance.get("sourceSha256") != source_sha or
            motion.get("sourceStreamIndex") != appearance.get("sourceStreamIndex") or
            type(motion.get("sourceStreamIndex")) is not int or
            motion["sourceStreamIndex"] < 0):
        raise ValueError("motion and appearance must identify the same video stream")
    if _rational(motion.get("sourceTimebase"), "motion timebase") != _rational(
            appearance.get("sourceTimebase"), "appearance timebase"):
        raise ValueError("motion and appearance must have an identical source timebase")
    scan_start = motion.get("scanStartSeconds", 0)
    if appearance.get("scanStartSeconds", 0) != scan_start:
        raise ValueError("motion and appearance must describe the same source window start")
    motion_result = _summarize(motion, kind="motion", threshold=image_motion_threshold)
    appearance_result = _summarize(appearance, kind="appearance", threshold=luma_change_threshold)
    result = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": source_sha,
        "sourceStreamIndex": motion["sourceStreamIndex"],
        "sourceTimebase": motion["sourceTimebase"],
        "scope": "two independently sampled bounded source windows, not whole-film statistics",
        "imagePlaneMotion": motion_result,
        "displayLumaChange": appearance_result,
        "methodLimits": [
            "Image translation can arise from camera, subject, animated layers or compositing; camera moves are not classified.",
            "Display luma can change from lights, exposure, grading, objects, edits or composition; real lighting changes are not classified.",
            "Active runs depend on sparse source-PTS sampling, chosen thresholds, gaps, detector sensitivity and analyzed window; not frame-accurate event counts.",
            "The two analyses can use different sample times and do not establish that an image move and luma change coincide.",
            "Cut candidate rates describe detected candidates only; manually validate before comparing films.",
        ],
        "reviewStatus": "measurement-only-no-camera-or-lighting-verification",
    }
    if scan_start:
        result["scanStartSeconds"] = scan_start
    return result
