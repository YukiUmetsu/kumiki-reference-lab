"""Deterministic, spatially distributed corner detection and patch flow.

This is a small CPU baseline for reference research, not a replacement for
multi-scale Lucas-Kanade, semantic segmentation, or 3D camera reconstruction.
"""

from __future__ import annotations

import math
from typing import Any

from kumiki_reference_lab.analyzers.subjects.template import track_template


def _box_sum(array: Any, size: int) -> Any:
    import numpy as np

    radius = size // 2
    padded = np.pad(array, ((radius, radius), (radius, radius)), mode="reflect")
    integral = np.pad(padded, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    return (integral[size:, size:] - integral[:-size, size:]
            - integral[size:, :-size] + integral[:-size, :-size])


def select_corners(
    gray: bytes, width: int, height: int, *, max_points: int = 48,
    patch_size: int = 9, radius: int = 8, min_distance: int = 6,
) -> list[tuple[int, int]]:
    """Approximate Shi-Tomasi min-eigen corners with spatial quotas."""
    import numpy as np

    if not 4 <= max_points <= 80 or patch_size not in (9, 11, 13, 15) or not 2 <= radius <= 16:
        raise ValueError("unsupported sparse-flow feature budget")
    if len(gray) != width * height or width < 64 or height < 36:
        raise ValueError("invalid gray frame dimensions")
    image = np.frombuffer(gray, dtype=np.uint8).reshape(height, width).astype(np.float64)
    gx = np.zeros_like(image)
    gy = np.zeros_like(image)
    gx[:, 1:-1] = (image[:, 2:] - image[:, :-2]) / 2
    gy[1:-1, :] = (image[2:, :] - image[:-2, :]) / 2
    xx, xy, yy = (_box_sum(gx * gx, 3), _box_sum(gx * gy, 3),
                  _box_sum(gy * gy, 3))
    trace = xx + yy
    minimum_eigenvalue = 0.5 * (trace - np.sqrt(np.maximum((xx - yy) ** 2 + 4 * xy ** 2, 0)))
    margin = patch_size // 2 + radius + 1
    minimum_eigenvalue[:margin, :] = 0
    minimum_eigenvalue[-margin:, :] = 0
    minimum_eigenvalue[:, :margin] = 0
    minimum_eigenvalue[:, -margin:] = 0
    peak = float(minimum_eigenvalue.max())
    if not math.isfinite(peak) or peak < 25.0:
        return []
    threshold = max(25.0, peak * 0.04)
    candidate_rows, candidate_cols = np.where(minimum_eigenvalue >= threshold)
    order = sorted(zip(candidate_cols.tolist(), candidate_rows.tolist()),
                   key=lambda pair: (-float(minimum_eigenvalue[pair[1], pair[0]]),
                                     pair[1], pair[0]))

    chosen: list[tuple[int, int]] = []
    per_cell: dict[tuple[int, int], int] = {}
    distance_squared = min_distance * min_distance
    for x, y in order:
        cell = (min(7, x * 8 // width), min(5, y * 6 // height))
        if per_cell.get(cell, 0) >= 3:
            continue
        if any((x - px) ** 2 + (y - py) ** 2 < distance_squared for px, py in chosen):
            continue
        chosen.append((x, y))
        per_cell[cell] = per_cell.get(cell, 0) + 1
        if len(chosen) >= max_points:
            break
    return sorted(chosen, key=lambda point: (point[1], point[0]))


def sparse_patch_flows(
    before: bytes, after: bytes, width: int, height: int, *,
    max_points: int = 48, patch_size: int = 9, radius: int = 8,
    minimum_correlation: float = 0.68, pyramid_levels: int = 1,
    subpixel_refinement: bool = False,
) -> dict[str, Any]:
    """Track source-frame corners with forward/backward patch consistency.

    By default accepted displacements are integer pixels. Optional subpixel
    peak interpolation is a candidate, not a fractionally verified match;
    the reverse consistency gate still operates on integer patch centers.
    """
    if not 0 < minimum_correlation < 1:
        raise ValueError("minimum_correlation must be between 0 and 1")
    if type(pyramid_levels) is not int or pyramid_levels not in (1, 2):
        raise ValueError("sparse-flow pyramid_levels must be 1 or 2")
    if type(subpixel_refinement) is not bool:
        raise ValueError("sparse-flow subpixel_refinement must be a boolean")
    corners = select_corners(before, width, height, max_points=max_points,
                             patch_size=patch_size, radius=radius)
    half = patch_size // 2

    coarse_before: bytes | None = None
    coarse_after: bytes | None = None
    coarse_width, coarse_height = width // 2, height // 2
    if pyramid_levels == 2 and corners:
        import numpy as np

        def downscale(plane: bytes) -> bytes:
            image = np.frombuffer(plane, dtype=np.uint8).reshape(height, width)
            block = image[:coarse_height * 2, :coarse_width * 2]
            return np.rint(block.reshape(coarse_height, 2, coarse_width, 2)
                           .mean(axis=(1, 3))).astype(np.uint8).tobytes()

        coarse_before, coarse_after = downscale(before), downscale(after)

    def patch(plane: bytes, x: int, y: int, plane_width: int = width) -> bytes:
        left, top = x - half, y - half
        return b"".join(plane[(top + row) * plane_width + left:
                              (top + row) * plane_width + left + patch_size]
                        for row in range(patch_size))

    def coarse_refine(x: int, y: int, template: bytes) -> dict[str, Any] | None:
        if coarse_before is None or coarse_after is None:
            return None
        cx, cy = x // 2, y // 2
        if not (half <= cx < coarse_width - half and
                half <= cy < coarse_height - half):
            return None
        coarse_template = patch(coarse_before, cx, cy, coarse_width)
        candidate = track_template(coarse_template, coarse_after,
                                   coarse_width, coarse_height, patch_size, patch_size,
                                   cx - half, cy - half,
                                   radius=radius,
                                   minimum_correlation=minimum_correlation)
        if candidate["status"] != "matched-template":
            return None
        predicted_x = x - half + 2 * (candidate["x"] - (cx - half))
        predicted_y = y - half + 2 * (candidate["y"] - (cy - half))
        refined = track_template(template, after, width, height,
                                 patch_size, patch_size, predicted_x, predicted_y,
                                 radius=2, minimum_correlation=minimum_correlation,
                                 subpixel_peak=subpixel_refinement)
        return refined if refined["status"] == "matched-template" else None

    accepted: list[dict[str, Any]] = []
    rejected = {"low-texture": 0, "forward-failed": 0, "backward-failed": 0,
                "roundtrip-inconsistent": 0}
    for x, y in corners:
        template = patch(before, x, y)
        start_x, start_y = x - half, y - half
        initial = track_template(template, after, width, height,
                                 patch_size, patch_size, start_x, start_y,
                                 radius=radius, minimum_correlation=minimum_correlation,
                                 subpixel_peak=subpixel_refinement)
        failure = ("low-texture" if initial["status"] == "unobservable-low-texture"
                   else "forward-failed")
        for search_level in range(1, pyramid_levels + 1):
            forward = (initial if search_level == 1
                       else coarse_refine(x, y, template))
            if forward is None or forward["status"] != "matched-template":
                continue
            next_x, next_y = forward["x"] + half, forward["y"] + half
            reverse_template = patch(after, next_x, next_y)
            # A coarse-recovered displacement may exceed the local radius;
            # validate the patch against its known source neighborhood.
            reverse_x, reverse_y = ((start_x, start_y) if search_level == 2
                                    else (forward["x"], forward["y"]))
            backward = track_template(reverse_template, before, width, height,
                                      patch_size, patch_size, reverse_x, reverse_y,
                                      radius=radius, minimum_correlation=minimum_correlation)
            if backward["status"] != "matched-template":
                failure = "backward-failed"
                continue
            error = math.hypot(backward["x"] - start_x, backward["y"] - start_y)
            if error > 1.5:
                failure = "roundtrip-inconsistent"
                continue
            vector = {"x": x, "y": y, "dx": next_x - x, "dy": next_y - y,
                      "forwardCorrelation": forward["correlation"],
                      "backwardCorrelation": backward["correlation"],
                      "roundtripErrorPixels": round(error, 4)}
            if subpixel_refinement:
                offset = forward["subpixelPeakOffset"]
                if offset is not None:
                    vector["dx"] = round(vector["dx"] + offset["dx"], 4)
                    vector["dy"] = round(vector["dy"] + offset["dy"], 4)
                vector.update({"subpixelPeakStatus": forward["subpixelPeakStatus"],
                               "subpixelPeakOffsetPixels": offset,
                               "subpixelReverseVerification": "integer-peak-only"})
            if pyramid_levels == 2:
                vector["searchLevel"] = search_level
            accepted.append(vector)
            break
        else:
            rejected[failure] += 1
    return {"detectedCorners": len(corners), "accepted": accepted,
            "rejected": rejected}
