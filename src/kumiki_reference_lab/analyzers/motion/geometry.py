"""Conservative affine hypotheses from sparse, measured 2D point motion.

An affine transform is an *image-plane model*, not a recovered physical camera.
Numerical agreement cannot distinguish lens/scene/camera/object mechanisms.
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any


def fit_image_affine(
    vectors: list[dict[str, Any]], width: int, height: int, *,
    inlier_tolerance: float = 1.5, max_hypotheses: int = 384,
) -> dict[str, Any]:
    """Fit a robust 2D affine *candidate*, preserving explicit failure reasons.

    A deterministic bounded three-point hypothesis search uses all accepted
    correspondences, then refits inliers. Require extensive spatial support and
    significant residual improvement before preferring affine to translation.
    """
    import numpy as np

    if width < 64 or height < 36:
        raise ValueError("affine analysis requires a valid image resolution")
    if (not math.isfinite(inlier_tolerance) or not 0.5 <= inlier_tolerance <= 4 or
            type(max_hypotheses) is not int or not 16 <= max_hypotheses <= 1024):
        raise ValueError("invalid affine hypothesis budget")
    base: dict[str, Any] = {"status": "insufficient-points", "inliers": 0,
                            "correspondences": len(vectors),
                            "inlierPointIndices": [], "model": None}
    if len(vectors) < 6:
        return base
    for v in vectors:
        if any(not math.isfinite(v[key]) for key in ("x", "y", "dx", "dy")):
            raise ValueError("affine measurements must be finite")

    origins = np.array([[v["x"], v["y"]] for v in vectors], dtype=np.float64)
    offsets = np.array([[v["dx"], v["dy"]] for v in vectors], dtype=np.float64)
    target = origins + offsets
    rows = np.column_stack((origins, np.ones(len(vectors))))
    min_support = max(6, math.ceil(len(vectors) * 0.55))
    available = len(vectors)
    if available <= 14:
        triples = list(combinations(range(available), 3))[:max_hypotheses]
    else:
        rng = np.random.default_rng(0)
        triples = []
        used: set[tuple[int, int, int]] = set()
        for _ in range(max_hypotheses * 3):
            triple = tuple(sorted(int(i) for i in rng.choice(available, 3, replace=False)))
            if triple not in used:
                used.add(triple)
                triples.append(triple)
            if len(triples) >= max_hypotheses:
                break

    best_indices: Any = None
    best_score = (-1, -math.inf)
    for triple in triples:
        triangle = rows[list(triple)]
        # Image-space triangle must span >1% of the frame's doubled area.
        if abs(float(np.linalg.det(triangle))) < width * height * 0.01:
            continue
        try:
            parameters = np.linalg.solve(triangle, target[list(triple)])
        except np.linalg.LinAlgError:
            continue
        residuals = np.linalg.norm(rows @ parameters - target, axis=1)
        indices = np.flatnonzero(residuals <= inlier_tolerance)
        if len(indices) < min_support:
            continue
        score = (len(indices), -float(np.median(residuals[indices])))
        if score > best_score:
            best_indices, best_score = indices, score

    if best_indices is None:
        return {**base, "status": "no-robust-affine-consensus"}
    # Refit and reclassify once. Final fit needs sufficient inlier support.
    parameters, _, _, _ = np.linalg.lstsq(rows[best_indices], target[best_indices], rcond=None)
    residuals = np.linalg.norm(rows @ parameters - target, axis=1)
    inliers = np.flatnonzero(residuals <= inlier_tolerance)
    if len(inliers) < min_support:
        return {**base, "status": "unstable-affine-refinement"}
    parameters, _, _, _ = np.linalg.lstsq(rows[inliers], target[inliers], rcond=None)
    span_x = float(np.ptp(origins[inliers, 0]))
    span_y = float(np.ptp(origins[inliers, 1]))
    if span_x < width * 0.30 or span_y < height * 0.30:
        return {**base, "status": "insufficient-spatial-support",
                "inliers": len(inliers),
                "inlierPointIndices": inliers.tolist()}

    predictions = rows[inliers] @ parameters
    affine_rms = float(np.sqrt(np.mean(np.sum((predictions - target[inliers]) ** 2, axis=1))))
    translation = np.median(offsets[inliers], axis=0)
    translation_rms = float(np.sqrt(np.mean(np.sum((offsets[inliers] - translation) ** 2, axis=1))))
    fit_gain = translation_rms - affine_rms
    prefer_affine = (fit_gain >= 0.65 and translation_rms >= 1.0 and
                     affine_rms <= translation_rms * 0.70)
    a, b, tx = parameters[:, 0]
    c, d, ty = parameters[:, 1]
    linear = np.array([[a, b], [c, d]])
    singular_values = np.linalg.svd(linear, compute_uv=False)
    determinant = float(np.linalg.det(linear))
    result = {
        "status": "affine-image-plane-candidate" if prefer_affine else "translation-sufficient",
        "inliers": len(inliers), "correspondences": len(vectors),
        "inlierPointIndices": inliers.tolist(),
        "model": {
            "matrix2x3": [[round(float(a), 6), round(float(b), 6), round(float(tx), 4)],
                          [round(float(c), 6), round(float(d), 6), round(float(ty), 4)]],
            "translationOnlyPixels": {"dx": round(float(translation[0]), 4),
                                      "dy": round(float(translation[1]), 4)},
            "rmsAffinePixels": round(affine_rms, 5),
            "rmsTranslationPixels": round(translation_rms, 5),
            "inlierFraction": round(len(inliers) / len(vectors), 5),
            "inlierSpanFraction": {"x": round(span_x / width, 5),
                                   "y": round(span_y / height, 5)},
            "areaScaleCandidate": round(math.sqrt(abs(determinant)), 6),
            "rotationDegreesCandidate": round(math.degrees(math.atan2(c, a)), 4),
            "anisotropyCandidate": round(float(singular_values[0] / max(singular_values[1], 1e-12)), 5),
            "reflectionOrInvalidGeometry": determinant <= 0,
            "calibratedConfidence": False,
        },
    }
    if determinant <= 0 or singular_values[0] > 3 or singular_values[1] < 0.3:
        return {**base, "status": "implausible-affine-geometry", "inliers": len(inliers),
                "inlierPointIndices": inliers.tolist()}
    return result
