"""Deterministic translation consensus across independently tracked image points.

Translation groups describe image motion only. Neither the largest group nor a
secondary group is proof of a camera, a background, or a semantic object.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Any


def _candidate_group(vectors: list[dict[str, Any]], indices: set[int],
                     tolerance: float) -> list[int]:
    """Pick a stable maximum-support translation with a median refinement."""
    best: list[int] = []
    for index in sorted(indices):
        seed = vectors[index]
        matching = [j for j in sorted(indices) if math.hypot(
            vectors[j]["dx"] - seed["dx"], vectors[j]["dy"] - seed["dy"]
        ) <= tolerance]
        if matching:
            dx = median(vectors[j]["dx"] for j in matching)
            dy = median(vectors[j]["dy"] for j in matching)
            refined = [j for j in sorted(indices) if math.hypot(
                vectors[j]["dx"] - dx, vectors[j]["dy"] - dy
            ) <= tolerance]
            # Stable resolution of ties, biased toward a compact residual.
            def rank(group: list[int]) -> tuple[int, float, int]:
                mx = median(vectors[j]["dx"] for j in group)
                my = median(vectors[j]["dy"] for j in group)
                return (len(group), -sum(math.hypot(vectors[j]["dx"] - mx,
                                                   vectors[j]["dy"] - my) for j in group),
                        -min(group))
            if not best or rank(refined) > rank(best):
                best = refined
    return best


def group_sparse_flows(vectors: list[dict[str, Any]], width: int, height: int,
                       *, tolerance: float = 1.5) -> dict[str, Any]:
    """Find up to two independent 2D translation groups, preserving outliers."""
    if not 0.5 <= tolerance <= 3:
        raise ValueError("flow consensus tolerance must be in [0.5, 3]")
    if width <= 0 or height <= 0:
        raise ValueError("invalid frame dimensions")
    for vector in vectors:
        if any(not math.isfinite(vector[key]) for key in ("x", "y", "dx", "dy")):
            raise ValueError("flow vectors must be finite")
    labels = ["unclassified"] * len(vectors)
    remaining = set(range(len(vectors)))
    clusters: list[dict[str, Any]] = []

    for role in ("dominant", "secondary"):
        indices = _candidate_group(vectors, remaining, tolerance) if remaining else []
        if len(indices) < 3:
            break
        dx = float(median(vectors[i]["dx"] for i in indices))
        dy = float(median(vectors[i]["dy"] for i in indices))
        if role == "secondary":
            first = clusters[0]
            if math.hypot(dx - first["dxPixels"], dy - first["dyPixels"]) < 2.5:
                break
        for i in indices:
            labels[i] = role
        remaining.difference_update(indices)
        xs = [vectors[i]["x"] for i in indices]
        ys = [vectors[i]["y"] for i in indices]
        cells = {(min(7, int(x * 8 / width)), min(5, int(y * 6 / height)))
                 for x, y in zip(xs, ys, strict=True)}
        residuals = [math.hypot(vectors[i]["dx"] - dx,
                                vectors[i]["dy"] - dy) for i in indices]
        clusters.append({
            "role": role, "support": len(indices),
            "supportFraction": round(len(indices) / len(vectors), 5),
            "dxPixels": round(dx, 4), "dyPixels": round(dy, 4),
            "medianResidualPixels": round(median(residuals), 4),
            "spatialCellCount": len(cells),
            "pointBoundsPixels": {"minX": min(xs), "minY": min(ys),
                                  "maxX": max(xs), "maxY": max(ys)},
        })

    if not clusters:
        status = "insufficient-consensus"
    elif len(clusters) == 2 and clusters[1]["support"] >= clusters[0]["support"] * 0.8:
        status = "ambiguous-dominant-group"
    elif len(clusters) == 2:
        status = "multiple-image-translations"
    else:
        status = "single-image-translation-candidate"
    return {"status": status, "clusters": clusters,
            "pointGroups": labels, "unclassifiedCount": len(remaining)}
