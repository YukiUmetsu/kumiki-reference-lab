"""Bounded zero-mean normalized cross-correlation template tracker."""

from __future__ import annotations

import math
from typing import Any


def track_template(
    template: bytes, image: bytes, image_width: int, image_height: int,
    box_width: int, box_height: int, previous_x: int, previous_y: int,
    *, radius: int = 12, minimum_correlation: float = 0.62,
) -> dict[str, Any]:
    """Find a small static textured patch near its previous position.

    The normalized correlation is an appearance similarity, NOT a calibrated
    confidence or semantic identity proof. Repetitive backgrounds can mislead
    even a strong match; ambiguous peaks are rejected.
    """
    try:
        import numpy as np
        from numpy.lib.stride_tricks import sliding_window_view
    except ImportError as exc:
        raise ValueError("ROI tracking requires NumPy; install with pip install '.[motion]'") from exc

    if (type(radius) is not int or not 1 <= radius <= 48 or
            not math.isfinite(minimum_correlation) or not 0 < minimum_correlation < 1):
        raise ValueError("invalid template search radius or correlation threshold")
    if (box_width < 8 or box_height < 8 or box_width > image_width // 2 or
            box_height > image_height // 2):
        raise ValueError("template box must be at least 8px and at most half the frame")
    if (2 * radius + 1) ** 2 * box_width * box_height > 6_000_000:
        raise ValueError("ROI search window exceeds bounded compute budget")
    if len(template) != box_width * box_height or len(image) != image_width * image_height:
        raise ValueError("template or image buffer has invalid dimensions")

    reference = np.frombuffer(template, dtype=np.uint8).reshape(box_height, box_width).astype(np.float64)
    centered = reference - reference.mean()
    reference_energy = float(np.sum(centered ** 2))
    if reference_energy < box_width * box_height:
        return {"status": "unobservable-low-texture", "x": None, "y": None,
                "correlation": None, "peakMargin": None}
    frame = np.frombuffer(image, dtype=np.uint8).reshape(image_height, image_width)
    xmin = max(0, previous_x - radius)
    ymin = max(0, previous_y - radius)
    xmax = min(image_width - box_width, previous_x + radius)
    ymax = min(image_height - box_height, previous_y + radius)
    if xmin > xmax or ymin > ymax:
        return {"status": "out-of-frame", "x": None, "y": None,
                "correlation": None, "peakMargin": None}
    region = frame[ymin:ymax + box_height, xmin:xmax + box_width].astype(np.float64)
    windows = sliding_window_view(region, (box_height, box_width))
    # Dot(centered_template, window) already subtracts the window mean because
    # centered_template sums to zero. Denominator uses variance of each patch.
    covariance = np.einsum("yxij,ij->yx", windows, centered, optimize=True)
    sample_count = box_width * box_height
    sums = windows.sum(axis=(-2, -1))
    squares = np.square(windows).sum(axis=(-2, -1))
    energies = np.maximum(squares - (sums ** 2) / sample_count, 0.0)
    scores = covariance / np.sqrt(np.maximum(energies * reference_energy, 1e-12))
    row, column = (int(i) for i in np.unravel_index(np.argmax(scores), scores.shape))
    peak = float(scores[row, column])
    if peak < minimum_correlation:
        return {"status": "lost-low-correlation", "x": None, "y": None,
                "correlation": round(peak, 5), "peakMargin": None}

    # A second matching peak >2px away suggests a repeated texture or identity
    # ambiguity. Nearby scores are expected to correlate for subpixel motion.
    sidelobes = scores.copy()
    sidelobes[max(0, row - 2):row + 3, max(0, column - 2):column + 3] = -2
    alternative = float(sidelobes.max())
    margin = peak - alternative
    if margin < 0.025:
        return {"status": "ambiguous-multiple-matches", "x": None, "y": None,
                "correlation": round(peak, 5), "peakMargin": round(margin, 5)}
    return {"status": "matched-template", "x": xmin + column, "y": ymin + row,
            "correlation": round(peak, 5), "peakMargin": round(margin, 5)}
