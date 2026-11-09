"""Bounded pixel-blend hypotheses over five source-timestamped RGB samples.

A close linear blend of endpoint images is only evidence of compositing-like
pixels. It does not establish an editorial cross-dissolve or source layers.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from kumiki_reference_lab.core.timebase import as_rational_dict

WINDOW = 5
MIN_ENDPOINT_RMS = 30.0
MIN_ENDPOINT_STD = 18.0
MAX_ENDPOINT_CORRELATION = 0.8
MAX_BLEND_RMS = 8.0
MAX_RELATIVE_RESIDUAL = 0.16
MIN_DURATION = Fraction(1, 5)


def detect_linear_blend_candidates(
    rgb_frames: list[bytes], samples: list[dict[str, Any]],
    changes: list[dict[str, Any]], *, timebase: Fraction,
) -> list[dict[str, Any]]:
    """Return conservative, non-overlapping observed five-frame blend windows."""
    import numpy as np

    if (not isinstance(timebase, Fraction) or timebase <= 0 or
            len(rgb_frames) != len(samples) or len(samples) != len(changes) + 1):
        raise ValueError("blend candidates require aligned RGB, PTS and cut evidence")
    pts = [sample["sourcePts"] for sample in samples]
    if any(b <= a for a, b in zip(pts, pts[1:])):
        raise ValueError("blend candidate PTS must be strictly increasing")
    if not rgb_frames or len({len(frame) for frame in rgb_frames}) != 1 or any(
            type(frame) is not bytes for frame in rgb_frames):
        raise ValueError("blend candidate frames must be same-size RGB byte buffers")
    if len(rgb_frames[0]) % 3:
        raise ValueError("blend candidate frames must contain RGB triplets")

    planes = [np.frombuffer(frame, dtype=np.uint8).astype(np.float32)
              for frame in rgb_frames]
    matches: list[tuple[float, int, dict[str, Any]]] = []
    for start in range(len(samples) - WINDOW + 1):
        end = start + WINDOW - 1
        if any(change["status"] == "cut-boundary" for change in changes[start:end]):
            continue
        if (pts[end] - pts[start]) * timebase < MIN_DURATION:
            continue
        first, last = planes[start], planes[end]
        if (np.std(first.reshape(-1, 3), axis=0).mean() < MIN_ENDPOINT_STD or
                np.std(last.reshape(-1, 3), axis=0).mean() < MIN_ENDPOINT_STD):
            continue
        endpoint_rms = float(np.sqrt(np.mean((last - first) ** 2)))
        if endpoint_rms < MIN_ENDPOINT_RMS:
            continue
        centered_a, centered_b = first - first.mean(), last - last.mean()
        denominator = float(np.linalg.norm(centered_a) * np.linalg.norm(centered_b))
        if denominator <= 0:
            continue
        correlation = float(np.dot(centered_a, centered_b) / denominator)
        if correlation > MAX_ENDPOINT_CORRELATION:
            continue
        errors = []
        for index in range(start + 1, end):
            fraction = (pts[index] - pts[start]) / (pts[end] - pts[start])
            predicted = first * (1.0 - fraction) + last * fraction
            errors.append(float(np.mean((planes[index] - predicted) ** 2)))
        rms = float(np.sqrt(sum(errors) / len(errors)))
        if rms > MAX_BLEND_RMS or rms / endpoint_rms > MAX_RELATIVE_RESIDUAL:
            continue
        matches.append((rms / endpoint_rms, start, {
            "kind": "linear-image-blend-candidate",
            "startPts": pts[start], "endPts": pts[end],
            "durationSeconds": as_rational_dict((pts[end] - pts[start]) * timebase),
            "observedSampleCount": WINDOW,
            "endpointDifferenceRmsRgbCode": round(endpoint_rms, 4),
            "intermediateBlendResidualRmsRgbCode": round(rms, 4),
            "normalizedResidual": round(rms / endpoint_rms, 5),
            "interpretationStatus": "review-required-not-verified",
        }))

    # Prefer the best-fitting window when adjacent windows overlap. Two
    # candidates must not reuse any sampled evidence images.
    chosen: list[tuple[int, dict[str, Any]]] = []
    occupied: set[int] = set()
    for _, start, evidence in sorted(matches, key=lambda item: (item[0], item[1])):
        covered = set(range(start, start + WINDOW))
        if not occupied.intersection(covered):
            chosen.append((start, evidence))
            occupied.update(covered)
    return [evidence for _, evidence in sorted(chosen)]
