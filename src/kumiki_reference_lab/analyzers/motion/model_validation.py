"""Spatial held-out tests of 2D motion models, never physical camera inference.

Unlike fitting residuals, each reported prediction error is measured on
correspondences excluded from that fold's parameter estimation. Fits are
intentionally unrobust: mixed motions and outliers should usually cause an
abstention, not be silently removed from the evaluation set.
"""

from __future__ import annotations

import math
from typing import Any

from kumiki_reference_lab.analyzers.motion.homography import (
    _fit_homography, _plausible, _project,
)


def compare_motion_models(vectors: list[dict[str, Any]], width: int,
                          height: int) -> dict[str, Any]:
    """Compare translation, affine and projective models on held-out cells.

    At most 64 matched 2D vectors are split into three interleaved spatial
    folds. The fold assignment is independent of measured displacement.
    Every point is evaluated exactly once and never helps train its own model.
    """
    import numpy as np

    if (type(width) is not int or type(height) is not int or
            not 64 <= width <= 240 or not 36 <= height <= 135):
        raise ValueError("model validation requires a bounded resolution")
    if not isinstance(vectors, list) or len(vectors) > 64:
        raise ValueError("model validation correspondences exceed bounded budget")
    for vector in vectors:
        if (not isinstance(vector, dict) or any(
            type(vector.get(key)) not in (int, float) or not math.isfinite(vector[key])
            for key in ("x", "y", "dx", "dy")
        )):
            raise ValueError("model validation requires finite image-plane vectors")
        if not 0 <= vector["x"] <= width or not 0 <= vector["y"] <= height:
            raise ValueError("model validation point lies outside the source frame")

    base: dict[str, Any] = {
        "status": "insufficient-correspondences", "preferredModel": None,
        "method": "spatial-three-fold-out-of-sample-v1",
        "correspondences": len(vectors), "validationPoints": 0,
        "models": {"translation": None, "affine": None, "projective": None},
        "calibratedConfidence": False, "physicalCameraVerified": False,
    }
    if len(vectors) < 18:
        return base
    origins = np.array([[p["x"], p["y"]] for p in vectors], dtype=np.float64)
    offsets = np.array([[p["dx"], p["dy"]] for p in vectors], dtype=np.float64)
    targets = origins + offsets

    def has_spatial_support(indices: Any) -> bool:
        """Require true 2D spread, not just large x/y extents on one line."""
        points = origins[indices]
        if (np.ptp(points[:, 0]) < width * 0.25 or
                np.ptp(points[:, 1]) < height * 0.25):
            return False
        normalized = points / np.array([width, height])
        singular = np.linalg.svd(normalized - normalized.mean(axis=0),
                                 compute_uv=False)
        return bool(singular[0] > 0 and singular[1] >= singular[0] * 0.20)

    if (np.ptp(origins[:, 0]) < width * 0.40 or
            np.ptp(origins[:, 1]) < height * 0.40 or
            not has_spatial_support(np.arange(len(vectors)))):
        return {**base, "status": "insufficient-spatial-validation"}

    # Spatial checkerboard rather than by input order, confidence, or motion.
    # Interleaving the cells tests generalization to different image regions.
    cell_x = np.minimum(5, (origins[:, 0] * 6 / width).astype(int))
    cell_y = np.minimum(3, (origins[:, 1] * 4 / height).astype(int))
    folds = (cell_x + 2 * cell_y) % 3
    regions = []
    for fold in range(3):
        testing = np.flatnonzero(folds == fold)
        training = np.flatnonzero(folds != fold)
        if len(testing) < 4 or len(training) < 10:
            return {**base, "status": "insufficient-spatial-validation"}
        if not has_spatial_support(training) or not has_spatial_support(testing):
            return {**base, "status": "insufficient-spatial-validation"}
        regions.append((training, testing))

    errors: dict[str, list[float] | None] = {
        "translation": [], "affine": [], "projective": [],
    }
    for training, testing in regions:
        origin_train, target_train = origins[training], targets[training]
        origin_test, target_test = origins[testing], targets[testing]
        median_offset = np.median(offsets[training], axis=0)
        predictions: dict[str, Any] = {
            "translation": origin_test + median_offset,
            "affine": None,
            "projective": None,
        }
        rows = np.column_stack((origin_train, np.ones(len(training))))
        if np.linalg.matrix_rank(rows) == 3:
            matrix, _, _, _ = np.linalg.lstsq(rows, target_train, rcond=None)
            predictions["affine"] = (np.column_stack(
                (origin_test, np.ones(len(testing)))) @ matrix)
        homography = _fit_homography(origin_train, target_train)
        if homography is not None and _plausible(homography, width, height):
            predictions["projective"] = _project(homography, origin_test)

        for name, prediction in predictions.items():
            if errors[name] is None:
                continue
            if prediction is None or not np.all(np.isfinite(prediction)):
                errors[name] = None
            else:
                errors[name].extend(np.linalg.norm(
                    prediction - target_test, axis=1).tolist())

    models: dict[str, Any] = {}
    for name, residuals in errors.items():
        if residuals is None or len(residuals) != len(vectors):
            models[name] = None
        else:
            values = np.asarray(residuals, dtype=np.float64)
            models[name] = {
                "rmsPixels": round(float(np.sqrt(np.mean(values ** 2))), 5),
                # Higher-nearest-rank avoids interpolating away gross misses
                # when two of the minimum eighteen samples are erroneous.
                "p90Pixels": round(float(np.percentile(values, 90,
                                                        method="higher")), 5),
            }

    def rms(name: str) -> float:
        return models[name]["rmsPixels"] if models[name] is not None else math.inf

    preferred = "translation" if rms("translation") <= 1.5 else None
    if (rms("affine") <= 1.5 and rms("translation") >= 1.0 and
            rms("translation") - rms("affine") >= 0.65 and
            rms("affine") <= rms("translation") * 0.70):
        preferred = "affine"
    if (rms("projective") <= 1.5 and rms("affine") >= 0.75 and
            rms("affine") - rms("projective") >= 0.35 and
            rms("projective") <= rms("affine") * 0.65):
        preferred = "projective"
    # Reject model choices that predict a large minority of points badly.
    if preferred is not None and models[preferred]["p90Pixels"] > 3.0:
        preferred = None
    return {
        **base,
        "status": "holdout-supported" if preferred is not None else "unreliable-holdout",
        "preferredModel": preferred,
        "validationPoints": len(vectors), "models": models,
    }
