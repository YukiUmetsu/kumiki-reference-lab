"""Independent two-interval patch agreement for conservative tracklet links.

Compare actual source frames A and C, not the shared junction frame B. Two
valid A→B and B→C matches need not represent the same feature; this extra
appearance check may reject identity swaps, but cannot verify object identity.
"""

from __future__ import annotations

import math
from typing import Any

PATCH_SIZE = 9
MAX_ENDPOINT_SHIFT_PIXELS = 1
MIN_NCC = 0.62
MIN_PATCH_STANDARD_DEVIATION = 5.0


def _patch(plane: bytes, width: int, height: int,
           x: int, y: int) -> tuple[int, ...] | None:
    half = PATCH_SIZE // 2
    if not half <= x < width - half or not half <= y < height - half:
        return None
    return tuple(plane[row * width + col]
                 for row in range(y - half, y + half + 1)
                 for col in range(x - half, x + half + 1))


def _ncc(first: tuple[int, ...], second: tuple[int, ...]) -> float | None:
    n = len(first)
    mean_first, mean_second = sum(first) / n, sum(second) / n
    a = [value - mean_first for value in first]
    b = [value - mean_second for value in second]
    aa, bb = sum(v * v for v in a), sum(v * v for v in b)
    if min(aa, bb) < n * MIN_PATCH_STANDARD_DEVIATION ** 2:
        return None
    correlation = sum(x * y for x, y in zip(a, b, strict=True)) / math.sqrt(aa * bb)
    return correlation if math.isfinite(correlation) else None


def two_hop_patch_agreement(
    first_frame: bytes, last_frame: bytes, width: int, height: int, *,
    first_point: dict[str, Any], last_point: dict[str, Any],
) -> dict[str, Any]:
    """Compare the first observed source patch to the last observed patch.

    All positions are source-image pixel coordinates. A tiny endpoint search
    absorbs rounding/error; evidence remains a short-baseline image heuristic.
    """
    if (type(width) is not int or type(height) is not int or
            not 64 <= width <= 240 or not 36 <= height <= 135 or
            type(first_frame) is not bytes or type(last_frame) is not bytes or
            len(first_frame) != width * height or len(last_frame) != width * height):
        raise ValueError("two-hop appearance requires bounded same-size grayscale frames")
    for point in (first_point, last_point):
        if (not isinstance(point, dict) or
                any(type(point.get(key)) not in (int, float) or
                    not math.isfinite(point[key]) for key in ("x", "y"))):
            raise ValueError("two-hop appearance requires finite source pixels")

    start = _patch(first_frame, width, height,
                   round(first_point["x"]), round(first_point["y"]))
    if start is None:
        return {"status": "unobservable", "correlation": None, "shiftPixels": None}
    center_x, center_y = round(last_point["x"]), round(last_point["y"])
    candidates: list[tuple[float, int, int]] = []
    for dy in range(-MAX_ENDPOINT_SHIFT_PIXELS, MAX_ENDPOINT_SHIFT_PIXELS + 1):
        for dx in range(-MAX_ENDPOINT_SHIFT_PIXELS, MAX_ENDPOINT_SHIFT_PIXELS + 1):
            end = _patch(last_frame, width, height, center_x + dx, center_y + dy)
            score = _ncc(start, end) if end is not None else None
            if score is not None:
                candidates.append((score, dx, dy))
    if not candidates:
        return {"status": "unobservable", "correlation": None, "shiftPixels": None}
    score, dx, dy = max(candidates, key=lambda item: (item[0],
                                                     -abs(item[1]) - abs(item[2]),
                                                     -abs(item[2]), -abs(item[1])))
    return {"status": "appearance-consistent" if score >= MIN_NCC else
                       "appearance-disagrees",
            "correlation": round(score, 5),
            "shiftPixels": {"dx": dx, "dy": dy}}
