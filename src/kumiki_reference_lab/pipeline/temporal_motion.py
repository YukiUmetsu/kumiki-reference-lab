"""Opt-in CPU optical-flow evidence from local, low-resolution frame previews.

Requires the existing optional 'dense' extra (NumPy/OpenCV). Tracks image
features, NOT identifiable people, animated characters, objects or physical
camera trajectories. Never bridges candidate shots and never stores images.
"""
from __future__ import annotations

import math
import statistics
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kumiki.online-temporal-motion.v1"


def _pair_plan(shots: list[dict[str, Any]], *, max_pairs: int,
               burst_pairs: int = 4) -> list[tuple[str, int, int]]:
    if type(max_pairs) is not int or not 1 <= max_pairs <= 400:
        raise ValueError("motion analysis budget must be 1..400 frame pairs")
    candidates: list[tuple[str, int]] = []
    for shot in shots:
        a, b = shot["startFrameIndex"], shot["endFrameIndexExclusive"]
        # Every 4th frame is an anchor for an independent short tracklet.
        for i in range(a, b - 1, burst_pairs):
            candidates.append((shot["shotId"], i))
    if not candidates:
        return []
    bursts = max(1, max_pairs // burst_pairs)
    if len(candidates) > bursts:
        selection = sorted({round(k * (len(candidates) - 1) / max(1, bursts - 1))
                            for k in range(bursts)})
        candidates = [candidates[k] for k in selection]
    end_by_shot = {shot["shotId"]: shot["endFrameIndexExclusive"] for shot in shots}
    result: list[tuple[str, int, int]] = []
    for shot_id, start in candidates:
        for i in range(start, min(start + burst_pairs, end_by_shot[shot_id] - 1)):
            item = (shot_id, i, i + 1)
            if item not in result:
                result.append(item)
    return sorted(result, key=lambda p: (p[1], p[2]))[:max_pairs]


def _load_gray(path: Path, width: int, height: int, cv2: Any) -> Any:
    if (path.is_symlink() or not path.is_file() or
            path.stat().st_size > 1_000_000):
        raise ValueError("unsafe or oversized frame preview")
    pixels = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if pixels is None or pixels.shape != (height, width):
        raise ValueError("preview PNG shape does not match workspace manifest")
    return pixels


def _global_model(a: Any, b: Any, width: int, height: int,
                  cv2: Any, np: Any) -> tuple[dict[str, Any], Any]:
    if len(a) < 6:
        return {"status": "insufficient-correspondences"}, None
    matrix, inliers = cv2.estimateAffinePartial2D(
        a.reshape(-1, 2), b.reshape(-1, 2),
        method=cv2.RANSAC, ransacReprojThreshold=1.8,
        maxIters=200, confidence=.99, refineIters=10,
    )
    if matrix is None or inliers is None:
        return {"status": "no-robust-global-fit"}, None
    m = np.asarray(matrix, dtype=np.float64)
    support = np.asarray(inliers, dtype=np.uint8).ravel().astype(bool)
    fraction = float(np.mean(support))
    supported = a.reshape(-1, 2)[support]
    span_x = float(np.ptp(supported[:, 0]) / width) if len(supported) else 0
    span_y = float(np.ptp(supported[:, 1]) / height) if len(supported) else 0
    stable = (int(np.sum(support)) >= 6 and fraction >= .6 and
              span_x >= .25 and span_y >= .2)
    scale = math.hypot(float(m[0, 0]), float(m[1, 0]))
    radians = math.atan2(float(m[1, 0]), float(m[0, 0]))
    translation = [round(float(m[0, 2]), 4), round(float(m[1, 2]), 4)]
    if not np.all(np.isfinite(m)) or scale <= 0:
        return {"status": "invalid-global-fit"}, None
    if not stable:
        return {
            "status": "low-spatial-support",
            "matchedPointCount": len(a),
            "inlierCount": int(np.sum(support)),
            "inlierFraction": round(fraction, 4),
        }, None
    if abs(scale - 1) >= .012:
        cue = "global-image-scale-proxy"
    elif abs(math.degrees(radians)) >= 1.5:
        cue = "global-image-rotation-proxy"
    elif math.hypot(*translation) >= .75:
        cue = "global-image-translation-proxy"
    else:
        cue = "approximately-static-global-image"
    return {
        "status": "supported-screen-affine-candidate",
        "cue": cue,
        "matchedPointCount": len(a),
        "inlierCount": int(np.sum(support)),
        "inlierFraction": round(fraction, 4),
        "inlierSpanFraction": [round(span_x, 4), round(span_y, 4)],
        "translationPixels": translation,
        "scaleRatio": round(scale, 6),
        "rotationDegrees": round(math.degrees(radians), 4),
        "interpretation": "image-plane-candidate-not-verified-physical-camera",
    }, m


def _local_motion_candidates(a: Any, b: Any, m: Any,
                             width: int, height: int, np: Any) -> list[dict[str, Any]]:
    if m is None:
        return []
    start = a.reshape(-1, 2)
    end = b.reshape(-1, 2)
    projected = start @ m[:, :2].T + m[:, 2]
    residual = np.linalg.norm(end - projected, axis=1)
    tiles: dict[tuple[int, int], list[int]] = {}
    for index, (point, err) in enumerate(zip(start, residual, strict=True)):
        if float(err) < 2.:
            continue
        bucket = (min(3, int(float(point[0]) / width * 4)),
                  min(2, int(float(point[1]) / height * 3)))
        tiles.setdefault(bucket, []).append(index)
    result = []
    for tile, indices in sorted(tiles.items(),
                                key=lambda item: (-len(item[1]), item[0]))[:4]:
        if len(indices) < 3:
            continue
        points = start[indices]
        result.append({
            "tile": [tile[0], tile[1]],
            "supportFeatures": len(indices),
            "meanResidualPixels": round(float(np.mean(residual[indices])), 4),
            "boundingBoxNormalized": [
                round(float(np.min(points[:, 0]) / width), 4),
                round(float(np.min(points[:, 1]) / height), 4),
                round(float(np.ptp(points[:, 0]) / width), 4),
                round(float(np.ptp(points[:, 1]) / height), 4),
            ],
            "kind": "localized-screen-motion-not-a-recognized-object",
        })
    return result



def _cpu_motion_fallback(
    workspace: Path, *, plan: list[tuple[str, int, int]],
    manifest: dict[str, Any], numeric: dict[str, Any],
    base: dict[str, Any],
) -> dict[str, Any]:
    """Measure conservative image-plane movement when OpenCV is unavailable.

    Uses the SAME prevalidated shot-local pairs as the optional optical-flow
    implementation. No model inference, OpenCV, NumPy, extra source download,
    or persistent feature-track/physical-camera claim.
    """
    from kumiki_reference_lab.pipeline.agent_frame_review import _frame_path
    from kumiki_reference_lab.pipeline.online_temporal import (
        _decode_review_png, match_image_plane_motion,
    )

    width, height = manifest["width"], manifest["height"]
    if (type(width) is not int or type(height) is not int
            or not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("invalid local frame preview resolution")
    cached: dict[int, bytes] = {}
    def local_frame(index: int) -> bytes:
        if index not in cached:
            path = _frame_path(workspace.absolute(), index)
            cached[index] = _decode_review_png(
                path, width=width, height=height)
        while len(cached) > 3:
            cached.pop(next(iter(cached)))
        return cached[index]

    output: list[dict[str, Any]] = []
    for shot_id, before, after in plan:
        if after != before + 1:
            raise ValueError("CPU block motion needs adjacent frame pairs")
        earlier = numeric["frames"][before]
        later = numeric["frames"][after]
        interval = later["decodedSeconds"] - earlier["decodedSeconds"]
        if type(interval) not in (int, float) or not math.isfinite(interval) or interval <= 0:
            raise ValueError("frame motion requires increasing decoded PTS")
        evidence = match_image_plane_motion(
            local_frame(before), local_frame(after),
            width=width, height=height)
        vector = evidence["dominantVectorPixels"]
        reliable = evidence["status"] == "coherent-image-plane-proxy"
        output.append({
            "shotId": shot_id, "startFrameIndex": before,
            "endFrameIndex": after,
            "startSeconds": earlier["decodedSeconds"],
            "endSeconds": later["decodedSeconds"],
            "trackedFeatureCount": 0,
            "meanImageFeatureSpeedPixelsPerSecond": None,
            "globalImageMotion": {
                "status": ("sampled-stdlib-image-plane-translation-proxy"
                           if reliable else "insufficient-block-motion-evidence"),
                "translationPixels": [vector["dx"], vector["dy"]]
                                     if reliable and vector else None,
                "coherenceFraction": evidence["coherenceFraction"],
                "matchedRegionCount": evidence["matchedRegions"],
                "interpretation": "not-optical-flow-not-verified-physical-camera",
            },
            "localMotionCandidates": [
                {
                    "tile": [r["gridColumn"], r["gridRow"]],
                    "residualDxPixels": r["residualDxPixels"],
                    "residualDyPixels": r["residualDyPixels"],
                    "kind": "screen-region-residual-not-a-tracked-object",
                }
                for r in evidence["relativeMotionRegions"]
            ],
            "blockMatchMeasurement": {
                "method": "fixed-grid-textured-RGB-match-v1",
                "deltaSeconds": round(float(interval), 6),
                "spatialSamplingStepPixels": evidence["spatialSamplingStepPixels"],
                "searchRadiusPixels": evidence["searchRadiusPixels"],
                "modelConfidence": "not-calibrated",
            },
        })
    return {
        **base,
        "pairs": output,
        "reportedPairCount": len(output),
        "status": "measured-sampled-stdlib-block-motion-proxies",
        "featureTracklets": [],
        "limitations": base["limitations"] + [
            "The fallback estimates only local RGB patch displacement, not optical flow.",
            "No persisted feature tracks, camera trajectory, object identities or easing.",
            "Coherent shifts may reflect animation, editing or camera movement.",
        ],
    }


def build_temporal_motion(
    workspace: Path, shots: dict[str, Any], *,
    max_pairs: int = 120, max_features: int = 80,
) -> dict[str, Any]:
    """Decode bounded local preview pairs and follow short-lived feature points."""
    from kumiki_reference_lab.pipeline.agent_frame_review import load_workspace
    if (type(max_features) is not int or not 12 <= max_features <= 160
            or type(max_pairs) is not int or not 1 <= max_pairs <= 400):
        raise ValueError("motion feature budget invalid")
    manifest, numeric, _ = load_workspace(workspace)
    if (shots.get("sourceSha256") != manifest["sourceSha256"] or
            shots.get("frameCount") != manifest["frameCount"]):
        raise ValueError("shot and preview provenance mismatch")
    plan = _pair_plan(shots["shots"], max_pairs=max_pairs)
    base = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": manifest["sourceSha256"],
        "frameCount": manifest["frameCount"],
        "previewSize": [manifest["width"], manifest["height"]],
        "pairBudget": max_pairs,
        "plannedPairCount": len(plan),
        "pairs": [], "featureTracklets": [],
        "limitations": [
            "These are tracked image features, not identified people, objects, text or characters.",
            "Affine motion is a global screen-space candidate, NOT a calibrated camera path.",
            "Motion residuals may arise from parallax, compression, occlusion or lighting.",
            "The short sampled bursts do not establish continuous motion between uninspected frames.",
        ],
    }
    try:
        import cv2
        import numpy as np
    except ImportError:
        return _cpu_motion_fallback(
            workspace, plan=plan, manifest=manifest,
            numeric=numeric, base=base)
    width, height = manifest["width"], manifest["height"]
    if not 64 <= width <= 320 or not 36 <= height <= 180:
        raise ValueError("frame preview resolution outside analysis limit")
    next_id = 0
    tracks: dict[int, dict[str, Any]] = {}
    frame_cache: dict[int, Any] = {}
    previous_end = -1
    previous_shot = ""
    live_points: dict[int, tuple[float, float]] = {}

    def frame(i: int) -> Any:
        # The cache holds at most three <=320x180 grayscale frames.
        if i not in frame_cache:
            path = workspace / "frames" / f"frame-{i:06d}.png"
            frame_cache[i] = _load_gray(path, width, height, cv2)
        for k in list(frame_cache):
            if len(frame_cache) > 3 and k != i:
                del frame_cache[k]
        return frame_cache[i]

    for shot_id, first, second in plan:
        source = frame(first)
        target = frame(second)
        if first != previous_end or shot_id != previous_shot:
            live_points = {}
        if len(live_points) < 12:
            mask = np.full((height, width), 255, dtype=np.uint8)
            # Seeding excludes the image border and already followed points.
            mask[:7, :] = mask[-7:, :] = 0
            mask[:, :7] = mask[:, -7:] = 0
            for x, y in live_points.values():
                cv2.circle(mask, (round(x), round(y)), 6, 0, -1)
            seed = cv2.goodFeaturesToTrack(
                source, maxCorners=max_features - len(live_points),
                qualityLevel=.025, minDistance=6, mask=mask, blockSize=5)
            if seed is not None:
                for (x, y) in seed.reshape(-1, 2):
                    live_points[next_id] = (float(x), float(y))
                    tracks[next_id] = {
                        "featureId": f"screen-feature-{next_id:05d}",
                        "shotId": shot_id, "observations": [],
                    }
                    next_id += 1
        if not live_points:
            base["pairs"].append({
                "shotId": shot_id, "startFrameIndex": first,
                "endFrameIndex": second, "trackedFeatureCount": 0,
                "globalImageMotion": {"status": "no-trackable-image-features"},
                "localMotionCandidates": [],
            })
            previous_end, previous_shot = second, shot_id
            continue
        ids = sorted(live_points)
        points = np.array([live_points[i] for i in ids],
                          dtype=np.float32).reshape(-1, 1, 2)
        estimated, ok, _ = cv2.calcOpticalFlowPyrLK(
            source, target, points, None, winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, .03))
        valid: list[int] = []
        if estimated is not None and ok is not None:
            backward, back_ok, _ = cv2.calcOpticalFlowPyrLK(
                target, source, estimated, None, winSize=(15, 15),
                maxLevel=2)
            if backward is not None and back_ok is not None:
                for j, (start, end) in enumerate(
                        zip(points.reshape(-1, 2), estimated.reshape(-1, 2),
                            strict=True)):
                    error = float(np.linalg.norm(backward[j, 0] - start))
                    if (ok[j, 0] and back_ok[j, 0] and error <= 1.5
                            and 1 <= end[0] < width - 1
                            and 1 <= end[1] < height - 1):
                        valid.append(j)
        accepted_first = (points[valid].reshape(-1, 2)
                          if valid else np.empty((0, 2), dtype=np.float32))
        accepted_second = (estimated[valid].reshape(-1, 2)
                           if valid else np.empty((0, 2), dtype=np.float32))
        global_status, transform = _global_model(
            accepted_first, accepted_second, width, height, cv2, np)
        dt = (numeric["frames"][second]["decodedSeconds"] -
              numeric["frames"][first]["decodedSeconds"])
        if dt <= 0:
            raise ValueError("motion pairs require increasing PTS")
        delta = accepted_second - accepted_first
        vectors = np.linalg.norm(delta, axis=1)
        pair = {
            "shotId": shot_id,
            "startFrameIndex": first, "endFrameIndex": second,
            "startSeconds": numeric["frames"][first]["decodedSeconds"],
            "endSeconds": numeric["frames"][second]["decodedSeconds"],
            "trackedFeatureCount": len(valid),
            "meanImageFeatureSpeedPixelsPerSecond": (
                round(float(np.mean(vectors)) / dt, 4) if len(valid) else None),
            "globalImageMotion": global_status,
            "localMotionCandidates": _local_motion_candidates(
                accepted_first, accepted_second, transform, width, height, np),
        }
        base["pairs"].append(pair)
        new_live = {}
        for j, x0, x1 in zip(valid, accepted_first, accepted_second, strict=True):
            fid = ids[j]
            a = [round(float(x0[0]) / width, 5),
                 round(float(x0[1]) / height, 5)]
            b = [round(float(x1[0]) / width, 5),
                 round(float(x1[1]) / height, 5)]
            history = tracks[fid]["observations"]
            if not history:
                history.append({"frameIndex": first, "normalizedXy": a})
            history.append({"frameIndex": second, "normalizedXy": b})
            new_live[fid] = (float(x1[0]), float(x1[1]))
        live_points = new_live
        previous_end, previous_shot = second, shot_id
    kept = []
    for track in tracks.values():
        obs = track["observations"]
        if len(obs) < 3:
            continue
        start, end = obs[0], obs[-1]
        start_t = numeric["frames"][start["frameIndex"]]["decodedSeconds"]
        end_t = numeric["frames"][end["frameIndex"]]["decodedSeconds"]
        if end_t <= start_t:
            continue
        vx = (end["normalizedXy"][0] - start["normalizedXy"][0]) / (end_t - start_t)
        vy = (end["normalizedXy"][1] - start["normalizedXy"][1]) / (end_t - start_t)
        kept.append({
            **track, "startFrameIndex": start["frameIndex"],
            "endFrameIndex": end["frameIndex"],
            "meanNormalizedVelocityPerSecond": [round(vx, 5), round(vy, 5)],
            "status": "short-screen-feature-track-not-semantic-identity",
        })
    base["featureTracklets"] = kept[:max_features * len(shots["shots"])]
    base["status"] = "measured-sampled-screen-flow-candidates"
    base["reportedPairCount"] = len(base["pairs"])
    return base
