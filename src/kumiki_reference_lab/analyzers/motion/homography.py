"""Bounded projective image-plane hypotheses from measured correspondences.

Projective agreement is not camera recovery or evidence of a physical lens,
plane, or subject. A four-point homography can overfit; require redundant,
spatially broad consensus and meaningful improvement over an affine fit.
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any


def _normalize(points: Any) -> tuple[Any, Any] | None:
    import numpy as np

    center = points.mean(axis=0)
    rms = float(np.sqrt(np.mean(np.sum((points - center) ** 2, axis=1))))
    if rms < 1e-6:
        return None
    scale = math.sqrt(2.0) / rms
    transform = np.array([[scale, 0, -scale * center[0]],
                          [0, scale, -scale * center[1]],
                          [0, 0, 1]], dtype=np.float64)
    return transform, (points - center) * scale


def _fit_homography(source: Any, target: Any) -> Any | None:
    import numpy as np

    before, after = _normalize(source), _normalize(target)
    if before is None or after is None:
        return None
    ts, src = before
    td, dst = after
    x, y, u, v = src[:, 0], src[:, 1], dst[:, 0], dst[:, 1]
    zero, one = np.zeros(len(source)), np.ones(len(source))
    design = np.empty((len(source) * 2, 9), dtype=np.float64)
    design[0::2] = np.column_stack((-x, -y, -one, zero, zero, zero,
                                     x * u, y * u, u))
    design[1::2] = np.column_stack((zero, zero, zero, -x, -y, -one,
                                     x * v, y * v, v))
    try:
        _, singular, right = np.linalg.svd(design, full_matrices=True)
    except np.linalg.LinAlgError:
        return None
    # Four pairs yield eight constrained directions; larger refits have one
    # expected null direction. Check the smallest *non-null* singular value.
    smallest_nonnull = singular[-1] if len(source) == 4 else singular[-2]
    if smallest_nonnull < 1e-7 or singular[0] / smallest_nonnull > 1e6:
        return None
    normalized = right[-1].reshape(3, 3)
    homography = np.linalg.solve(td, normalized @ ts)
    if abs(homography[2, 2]) < 1e-9:
        return None
    homography /= homography[2, 2]
    return homography if np.all(np.isfinite(homography)) else None


def _project(homography: Any, points: Any) -> Any | None:
    import numpy as np

    homogeneous = np.column_stack((points, np.ones(len(points))))
    result = homogeneous @ homography.T
    w = result[:, 2]
    if not np.all(np.isfinite(w)) or np.any(np.abs(w) < 1e-7):
        return None
    xy = result[:, :2] / w[:, None]
    return xy if np.all(np.isfinite(xy)) else None


def _plausible(homography: Any, width: int, height: int) -> bool:
    import numpy as np

    corners = np.array([[0, 0], [width, 0], [width, height], [0, height]],
                       dtype=np.float64)
    homogeneous = np.column_stack((corners, np.ones(4)))
    transformed = homogeneous @ homography.T
    w = transformed[:, 2]
    if (not np.all(np.isfinite(w)) or np.min(w) < 0.2 or
            np.max(w) > 4.0 or np.max(w) / np.min(w) > 4.0):
        return False
    mapped = transformed[:, :2] / w[:, None]
    if (not np.all(np.isfinite(mapped)) or
            np.any(mapped[:, 0] < -width * 0.5) or
            np.any(mapped[:, 0] > width * 1.5) or
            np.any(mapped[:, 1] < -height * 0.5) or
            np.any(mapped[:, 1] > height * 1.5)):
        return False
    center = np.array([width * 0.5, height * 0.5, 1.0])
    projected = homography @ center
    if projected[2] < 0.2:
        return False
    jacobian = ((homography[:2, :2] * projected[2] -
                np.outer(projected[:2], homography[2, :2])) /
                projected[2] ** 2)
    try:
        singular = np.linalg.svd(jacobian, compute_uv=False)
    except np.linalg.LinAlgError:
        return False
    return (float(np.linalg.det(jacobian)) > 0.0 and
            0.3 <= singular[-1] <= singular[0] <= 3.0)


def fit_image_homography(
    vectors: list[dict[str, Any]], width: int, height: int, *,
    inlier_tolerance: float = 1.5, max_hypotheses: int = 256,
) -> dict[str, Any]:
    """Candidate projective warp, only if it beats affine on the same inliers."""
    import numpy as np

    if (type(width) is not int or type(height) is not int or
            not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("projective analysis requires a bounded resolution")
    if (not math.isfinite(inlier_tolerance) or not 0.5 <= inlier_tolerance <= 4 or
            type(max_hypotheses) is not int or not 16 <= max_hypotheses <= 512):
        raise ValueError("invalid projective hypothesis budget")
    if not isinstance(vectors, list) or len(vectors) > 64:
        raise ValueError("projective correspondences exceed bounded budget")
    base: dict[str, Any] = {"status": "insufficient-points", "inliers": 0,
                            "correspondences": len(vectors),
                            "inlierPointIndices": [], "model": None}
    if len(vectors) < 10:
        return base
    for vector in vectors:
        if (not isinstance(vector, dict) or
                any(type(vector.get(key)) not in (int, float) or
                    not math.isfinite(vector[key])
                    for key in ("x", "y", "dx", "dy"))):
            raise ValueError("projective measurements must be finite numbers")
    origins = np.array([[v["x"], v["y"]] for v in vectors], dtype=np.float64)
    offsets = np.array([[v["dx"], v["dy"]] for v in vectors], dtype=np.float64)
    target = origins + offsets
    count = len(vectors)
    min_support = max(10, math.ceil(count * 0.60))
    if count <= 10:
        quadruples = list(combinations(range(count), 4))[:max_hypotheses]
    else:
        rng = np.random.default_rng(0)
        quadruples = []
        used: set[tuple[int, int, int, int]] = set()
        for _ in range(max_hypotheses * 4):
            indices = tuple(sorted(int(i) for i in rng.choice(count, 4, replace=False)))
            if indices not in used:
                used.add(indices)
                quadruples.append(indices)
            if len(quadruples) >= max_hypotheses:
                break

    best_indices = None
    best_rank = (-1, -math.inf)
    for indices in quadruples:
        subset = origins[list(indices)]
        if (float(np.ptp(subset[:, 0])) < width * 0.25 or
                float(np.ptp(subset[:, 1])) < height * 0.25):
            continue
        model = _fit_homography(subset, target[list(indices)])
        if model is None or not _plausible(model, width, height):
            continue
        projected = _project(model, origins)
        if projected is None:
            continue
        residuals = np.linalg.norm(projected - target, axis=1)
        inliers = np.flatnonzero(residuals <= inlier_tolerance)
        if len(inliers) < min_support:
            continue
        rank = (len(inliers), -float(np.median(residuals[inliers])))
        if rank > best_rank:
            best_indices, best_rank = inliers, rank

    if best_indices is None:
        return {**base, "status": "no-robust-projective-consensus"}
    model = _fit_homography(origins[best_indices], target[best_indices])
    if model is None or not _plausible(model, width, height):
        return {**base, "status": "unstable-projective-refinement"}
    projected = _project(model, origins)
    if projected is None:
        return {**base, "status": "unstable-projective-refinement"}
    residuals = np.linalg.norm(projected - target, axis=1)
    inliers = np.flatnonzero(residuals <= inlier_tolerance)
    if len(inliers) < min_support:
        return {**base, "status": "unstable-projective-refinement"}
    model = _fit_homography(origins[inliers], target[inliers])
    if model is None or not _plausible(model, width, height):
        return {**base, "status": "implausible-projective-warp",
                "inliers": len(inliers), "inlierPointIndices": inliers.tolist()}
    span_x = float(np.ptp(origins[inliers, 0]))
    span_y = float(np.ptp(origins[inliers, 1]))
    if span_x < width * 0.40 or span_y < height * 0.40:
        return {**base, "status": "insufficient-spatial-support",
                "inliers": len(inliers), "inlierPointIndices": inliers.tolist()}
    projected = _project(model, origins[inliers])
    if projected is None:
        return {**base, "status": "implausible-projective-warp"}
    homography_rms = float(np.sqrt(np.mean(np.sum(
        (projected - target[inliers]) ** 2, axis=1))))
    affine_rows = np.column_stack((origins[inliers], np.ones(len(inliers))))
    affine, _, _, _ = np.linalg.lstsq(affine_rows, target[inliers], rcond=None)
    affine_predictions = affine_rows @ affine
    affine_rms = float(np.sqrt(np.mean(np.sum(
        (affine_predictions - target[inliers]) ** 2, axis=1))))
    corners = np.array([[0, 0, 1], [width, 0, 1],
                        [width, height, 1], [0, height, 1]])
    denominators = (corners @ model.T)[:, 2]
    denominator_ratio = float(denominators.max() / denominators.min())
    prefer_projective = (affine_rms >= 0.75 and
                         affine_rms - homography_rms >= 0.35 and
                         homography_rms <= affine_rms * 0.65 and
                         denominator_ratio >= 1.03)
    return {
        "status": ("projective-image-plane-candidate" if prefer_projective
                   else "affine-sufficient"),
        "inliers": len(inliers), "correspondences": count,
        "inlierPointIndices": inliers.tolist(),
        "model": {
            "matrix3x3": [[round(float(value), 8) for value in row]
                          for row in model],
            "rmsHomographyPixels": round(homography_rms, 5),
            "rmsAffinePixels": round(affine_rms, 5),
            "inlierFraction": round(len(inliers) / count, 5),
            "inlierSpanFraction": {"x": round(span_x / width, 5),
                                   "y": round(span_y / height, 5)},
            "cornerDenominatorRatio": round(denominator_ratio, 5),
            "calibratedConfidence": False,
        },
    }
