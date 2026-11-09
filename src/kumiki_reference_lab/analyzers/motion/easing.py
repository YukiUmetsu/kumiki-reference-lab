"""Bounded candidate easing fits to measured image-plane displacement."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any


def _curves(t: float) -> dict[str, float]:
    return {
        "linear": t,
        "ease-in-quad": t * t,
        "ease-out-quad": 1 - (1 - t) ** 2,
        "ease-in-out-cubic": 3 * t * t - 2 * t * t * t,
        "ease-in-out-quintic": 6 * t ** 5 - 15 * t ** 4 + 10 * t ** 3,
    }


def fit_easing_candidates(
    observations: list[tuple[Fraction, float, float]],
) -> dict[str, Any]:
    """Fit named reference curves only when image motion follows its net path.

    Candidate fits describe *measured pixels*, not the source project's true
    keyframes or a unique physical cause. Curvature can come from camera,
    foreground objects, and imperfect global translation measurements.
    """
    if len(observations) < 5:
        return {"status": "insufficient-samples", "candidates": [], "bestCandidate": None}
    start_t, start_x, start_y = observations[0]
    end_t, end_x, end_y = observations[-1]
    duration = end_t - start_t
    dx, dy = end_x - start_x, end_y - start_y
    distance_squared = dx * dx + dy * dy
    if duration <= 0:
        return {"status": "invalid-source-times", "candidates": [], "bestCandidate": None}
    if (not math.isfinite(distance_squared) or
            any(not math.isfinite(value) for _, x, y in observations for value in (x, y))):
        return {"status": "invalid-observations", "candidates": [], "bestCandidate": None}
    if distance_squared < 4.0:
        return {"status": "insufficient-net-motion", "candidates": [], "bestCandidate": None}
    times: list[float] = []
    progress: list[float] = []
    for moment, x, y in observations:
        times.append(float((moment - start_t) / duration))
        progress.append(((x - start_x) * dx + (y - start_y) * dy) / distance_squared)
    if (any(b <= a for a, b in zip(times, times[1:])) or
            min(progress) < -0.12 or max(progress) > 1.12 or
            any(b + 0.12 < a for a, b in zip(progress, progress[1:]))):
        return {"status": "nonmonotonic-or-overshooting", "candidates": [], "bestCandidate": None}

    # Projecting a curved 2D path onto its start-to-end direction can yield a
    # deceptively perfect linear/ease curve. Guard the *unmodeled* sideways
    # excursion and repeated detours before ranking any one-dimensional fit.
    distance = math.sqrt(distance_squared)
    lateral = max(abs((x - start_x) * dy - (y - start_y) * dx) / distance
                  for _, x, y in observations)
    traveled = sum(math.hypot(bx - ax, by - ay)
                   for (_, ax, ay), (_, bx, by) in zip(observations, observations[1:]))
    if not math.isfinite(lateral) or not math.isfinite(traveled):
        return {"status": "invalid-observations", "candidates": [], "bestCandidate": None}
    geometry = {"netDisplacementPixels": round(distance, 5),
                "sampleCount": len(observations),
                "maxLateralDeviationPixels": round(lateral, 5),
                "pathLengthRatio": round(traveled / distance, 5)}
    if lateral > max(2.0, distance * 0.15) or traveled > max(distance + 3.0,
                                                             distance * 1.2):
        return {"status": "nonlinear-image-path", "bestCandidate": None,
                "candidates": [], **geometry}

    curves = _curves(0.0)
    candidates: list[dict[str, Any]] = []
    for name in curves:
        residuals = [observed - _curves(t)[name] for t, observed in zip(times, progress)]
        rms = math.sqrt(sum(error * error for error in residuals) / len(residuals))
        candidates.append({"name": name, "normalizedRms": round(rms, 5),
                           "maxAbsoluteResidual": round(max(map(abs, residuals)), 5)})
    candidates.sort(key=lambda item: (item["normalizedRms"], item["name"]))
    best = candidates[0]
    if best["normalizedRms"] > 0.18:
        status = "poor-simple-curve-fit"
        best_name = None
    elif candidates[1]["normalizedRms"] - best["normalizedRms"] < 0.02:
        status = "ambiguous-curve-family"
        best_name = None
    else:
        status = "candidate-only"
        best_name = best["name"]
    return {"status": status, "bestCandidate": best_name,
            "candidates": candidates, **geometry}
