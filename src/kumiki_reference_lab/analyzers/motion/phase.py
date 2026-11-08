"""Global phase-correlation translation between two downsampled gray images."""

from __future__ import annotations

import math
from typing import Any


def measure_image_shift(before: bytes, after: bytes, width: int, height: int) -> dict[str, Any]:
    """Return image-plane shift (after relative to before) or ambiguity.

    This is a **global** translation model. Multiple independent objects,
    parallax, zoom, cuts and reflections violate its assumptions. The PSR
    diagnostic is NOT a calibrated probability or semantic confidence.
    """
    try:
        import numpy as np
    except ImportError as exc:
        raise ValueError("motion requires NumPy; install with pip install '.[motion]'") from exc

    if len(before) != width * height or len(after) != width * height:
        raise ValueError("gray frame does not match declared dimensions")
    first = np.frombuffer(before, dtype=np.uint8).reshape(height, width).astype(np.float64)
    second = np.frombuffer(after, dtype=np.uint8).reshape(height, width).astype(np.float64)
    if min(float(first.std()), float(second.std())) < 2.0:
        return {"status": "unobservable-low-texture", "dxPixels": None,
                "dyPixels": None, "peakToSidelobeRatio": None}

    # The window reduces periodic wrap artifacts at frame borders.
    window = np.outer(np.hanning(height), np.hanning(width))
    a = np.fft.fft2((first - first.mean()) * window)
    b = np.fft.fft2((second - second.mean()) * window)
    cross = b * np.conj(a)
    magnitudes = np.abs(cross)
    if int(np.count_nonzero(magnitudes > 1e-9)) < width * height // 20:
        return {"status": "unobservable-low-texture", "dxPixels": None,
                "dyPixels": None, "peakToSidelobeRatio": None}
    normalized = cross / np.maximum(magnitudes, 1e-12)
    correlation = np.abs(np.fft.ifft2(normalized))
    peak_row, peak_col = (int(v) for v in np.unravel_index(np.argmax(correlation),
                                                            correlation.shape))

    def subpixel_offset(axis: int, index: int) -> float:
        current = float(correlation[peak_row, peak_col])
        if axis == 0:
            left = float(correlation[(index - 1) % height, peak_col])
            right = float(correlation[(index + 1) % height, peak_col])
        else:
            left = float(correlation[peak_row, (index - 1) % width])
            right = float(correlation[peak_row, (index + 1) % width])
        denominator = left - 2 * current + right
        return max(-0.5, min(0.5, 0.5 * (left - right) / denominator)) if abs(denominator) > 1e-12 else 0.0

    dx = (peak_col if peak_col <= width // 2 else peak_col - width) + subpixel_offset(1, peak_col)
    dy = (peak_row if peak_row <= height // 2 else peak_row - height) + subpixel_offset(0, peak_row)

    # Exclude the peak's 7x7 neighborhood, wrapping at image boundaries.
    mask = np.ones_like(correlation, dtype=bool)
    for yy in range(-3, 4):
        for xx in range(-3, 4):
            mask[(peak_row + yy) % height, (peak_col + xx) % width] = False
    sidelobes = correlation[mask]
    mean, std = float(sidelobes.mean()), float(sidelobes.std())
    psr = (float(correlation[peak_row, peak_col]) - mean) / max(std, 1e-12)
    psr = round(psr, 4) if math.isfinite(psr) else None

    if (psr is None or psr < 6.0 or abs(dx) > width / 4 or abs(dy) > height / 4):
        return {"status": "ambiguous-correlation", "dxPixels": None,
                "dyPixels": None, "peakToSidelobeRatio": psr}
    return {"status": "measured-image-translation",
            "dxPixels": round(float(dx), 5), "dyPixels": round(float(dy), 5),
            "peakToSidelobeRatio": psr}
