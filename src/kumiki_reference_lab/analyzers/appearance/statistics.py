"""Deterministic, bounded descriptors of display-referred RGB pixels."""

from __future__ import annotations

from typing import Any


def describe_rgb_frame(rgb: bytes, width: int, height: int) -> dict[str, Any]:
    """Measure RGB appearance; luma is non-linear Y' proxy, not scene luminance."""
    import numpy as np

    if width < 64 or height < 36 or len(rgb) != width * height * 3:
        raise ValueError("invalid RGB frame dimensions")
    image = np.frombuffer(rgb, dtype=np.uint8).reshape(height, width, 3)
    normalized = image.astype(np.float64) / 255.0
    red, green, blue = (normalized[:, :, i] for i in range(3))
    luma = red * 0.2126 + green * 0.7152 + blue * 0.0722
    top = np.max(normalized, axis=2)
    bottom = np.min(normalized, axis=2)
    spread = top - bottom
    saturation = np.divide(spread, top, out=np.zeros_like(spread), where=top > 0)
    chromatic = (saturation >= 0.18) & (top >= 0.15)
    # Hue is purely descriptive of observed display-referred pixel color.
    hue = np.zeros_like(luma)
    safe_spread = np.where(spread > 0, spread, 1.0)
    red_max = (top == red) & chromatic
    green_max = (top == green) & chromatic & ~red_max
    blue_max = chromatic & ~(red_max | green_max)
    hue[red_max] = ((green - blue) / safe_spread)[red_max] % 6
    hue[green_max] = ((blue - red) / safe_spread + 2)[green_max]
    hue[blue_max] = ((red - green) / safe_spread + 4)[blue_max]
    hue = hue / 6.0
    hue_counts = np.histogram(hue[chromatic], bins=12, range=(0, 1))[0]
    chromatic_count = int(chromatic.sum())
    hue_fractions = (hue_counts / chromatic_count if chromatic_count else
                     np.zeros(12, dtype=np.float64))

    quantized = (image.astype(np.int16) * 6 // 256).reshape(-1, 3)
    color_codes = (quantized[:, 0] * 36 + quantized[:, 1] * 6 + quantized[:, 2])
    counts = np.bincount(color_codes, minlength=216)
    ranked = sorted((int(code) for code in np.flatnonzero(counts)),
                    key=lambda code: (-int(counts[code]), code))[:5]
    palette = [{"rgbApprox": [int(round(((code // 36) + .5) * 255 / 6)),
                              int(round((((code // 6) % 6) + .5) * 255 / 6)),
                              int(round(((code % 6) + .5) * 255 / 6))],
                "pixelFraction": round(float(counts[code]) / (width * height), 5)}
               for code in ranked]

    bright = luma >= 0.85
    if int(bright.sum()) >= 10:
        ys, xs = np.nonzero(bright)
        bright_center: dict[str, float] | None = {
            "x": round(float(np.mean(xs + .5)) / width, 6),
            "y": round(float(np.mean(ys + .5)) / height, 6),
        }
    else:
        bright_center = None
    grid = []
    for row in range(3):
        for column in range(3):
            y0, y1 = row * height // 3, (row + 1) * height // 3
            x0, x1 = column * width // 3, (column + 1) * width // 3
            area = luma[y0:y1, x0:x1]
            grid.append({"row": row, "column": column,
                         "meanLumaProxy": round(float(area.mean()), 5),
                         "lumaStdDev": round(float(area.std()), 5),
                         "brightPixelFraction": round(float((area >= 0.85).mean()), 5)})
    lower, upper = np.percentile(luma, [10, 90])
    return {
        "meanRgb": [round(float(x), 5) for x in normalized.mean(axis=(0, 1))],
        "meanLumaProxy": round(float(luma.mean()), 5),
        "medianLumaProxy": round(float(np.median(luma)), 5),
        "lumaP10": round(float(lower), 5),
        "lumaP90": round(float(upper), 5),
        "lumaContrastP90MinusP10": round(float(upper - lower), 5),
        "shadowPixelFraction": round(float((luma <= 0.15).mean()), 5),
        "brightPixelFraction": round(float(bright.mean()), 5),
        "brightPixelCentroid": bright_center,
        "meanSaturation": round(float(saturation.mean()), 5),
        "chromaticPixelFraction": round(float(chromatic.mean()), 5),
        "hueHistogram12": [round(float(x), 5) for x in hue_fractions],
        "dominantRgbBins": palette,
        "spatialGrid3x3": grid,
    }
