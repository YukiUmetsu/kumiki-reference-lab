"""Opt-in seeded character/product/text region tracking from local frame previews.

Seed labels come from the operator, not model identity recognition. Tracks
do not bridge cuts, resolve occlusions, recognize demographics or infer social
intent. Image-plane affine box motion is measured only while enough appearance
features survive forward/backward tests.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kumiki.online-seeded-region-tracks.v1"
SEEDS_VERSION = "kumiki.online-region-seeds.v1"
_KINDS = {"animated-character", "person", "product", "text", "prop", "other"}
_ID = re.compile(r"^[a-z][a-z0-9-]{0,47}$")


def validate_region_seeds(
    document: dict[str, Any], *, source_sha: str, frame_count: int,
) -> list[dict[str, Any]]:
    if (not isinstance(document, dict) or
            document.get("schemaVersion") != SEEDS_VERSION or
            document.get("sourceSha256") != source_sha):
        raise ValueError("ROI seeds source identity/version mismatch")
    subjects = document.get("subjects")
    if not isinstance(subjects, list) or not 1 <= len(subjects) <= 8:
        raise ValueError("ROI seeds must contain 1..8 subjects")
    identifiers = set()
    for item in subjects:
        if not isinstance(item, dict):
            raise ValueError("ROI seed must be an object")
        ident = item.get("id")
        box = item.get("boxNormalized")
        frame = item.get("startFrameIndex")
        if (type(ident) is not str or not _ID.fullmatch(ident) or
                ident in identifiers or item.get("kind") not in _KINDS or
                type(item.get("label")) is not str or
                not 1 <= len(item["label"].strip()) <= 80 or
                type(frame) is not int or not 0 <= frame < frame_count or
                not isinstance(box, list) or len(box) != 4 or
                any(type(v) not in (int, float) or not math.isfinite(v)
                    for v in box)):
            raise ValueError("invalid or duplicated ROI seed")
        x, y, w, h = box
        if (x < 0 or y < 0 or w <= 0 or h <= 0 or
                x + w > 1 + 1e-8 or y + h > 1 + 1e-8):
            raise ValueError("ROI seed box outside image")
        identifiers.add(ident)
    return subjects


def _normalized_box(corners: Any, *, width: int, height: int,
                    np: Any) -> list[float] | None:
    if not np.all(np.isfinite(corners)):
        return None
    left, top = float(np.min(corners[:, 0])), float(np.min(corners[:, 1]))
    right, bottom = float(np.max(corners[:, 0])), float(np.max(corners[:, 1]))
    if (left < 0 or top < 0 or right > width or bottom > height or
            right - left < 8 or bottom - top < 8):
        return None
    return [round(left / width, 5), round(top / height, 5),
            round((right - left) / width, 5),
            round((bottom - top) / height, 5)]


def _box_iou(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    iw = max(0., min(ax + aw, bx + bw) - max(ax, bx))
    ih = max(0., min(ay + ah, by + bh) - max(ay, by))
    area = aw * ah + bw * bh - iw * ih
    return round(iw * ih / area, 5) if area else 0.


def screen_relationship_proxies(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Concurrent box overlap/separation, never human intention or interaction."""
    pairs = []
    for i, a in enumerate(tracks):
        aa = {o["frameIndex"]: o for o in a["observations"]
              if o.get("boxNormalized")}
        for b in tracks[i+1:]:
            bb = {o["frameIndex"]: o for o in b["observations"]
                  if o.get("boxNormalized")}
            indices = sorted(set(aa).intersection(bb))
            if len(indices) < 2:
                continue
            movement = []
            overlaps = 0
            for frame in indices:
                x, y, w, h = aa[frame]["boxNormalized"]
                xx, yy, ww, hh = bb[frame]["boxNormalized"]
                center_distance = math.hypot(x + w/2 - xx - ww/2,
                                             y + h/2 - yy - hh/2)
                movement.append(center_distance)
                overlaps += _box_iou(
                    aa[frame]["boxNormalized"], bb[frame]["boxNormalized"]) > 0
            change = movement[-1] - movement[0]
            pairs.append({
                "subjectA": a["id"], "subjectB": b["id"],
                "startFrameIndex": indices[0],
                "endFrameIndex": indices[-1],
                "coVisibleSampleCount": len(indices),
                "boxOverlapSampleCount": overlaps,
                "screenCenterDistanceStartNormalized": round(movement[0], 5),
                "screenCenterDistanceEndNormalized": round(movement[-1], 5),
                "screenDistanceTrend": (
                    "closer" if change < -.03 else
                    "farther" if change > .03 else "approximately-stable"
                ),
                "status": "co-observed-screen-box-proxy-not-a-social-interaction",
            })
    return pairs[:28]


def build_seeded_region_tracks(
    workspace: Path, shots: dict[str, Any], seeds_file: Path,
    *, max_frames_per_subject: int = 240,
) -> dict[str, Any]:
    from kumiki_reference_lab.pipeline.agent_frame_review import load_workspace
    if type(max_frames_per_subject) is not int or not 2 <= max_frames_per_subject <= 900:
        raise ValueError("seeded tracking frame budget must be 2..900")
    manifest, numeric, _ = load_workspace(workspace)
    if shots["sourceSha256"] != manifest["sourceSha256"]:
        raise ValueError("ROI and shot source identity mismatch")
    if (seeds_file.is_symlink() or not seeds_file.is_file() or
            seeds_file.stat().st_size > 32768):
        raise ValueError("unsafe or oversized ROI seed JSON")
    source_doc = json.loads(seeds_file.read_text(encoding="utf-8"))
    seeds = validate_region_seeds(
        source_doc, source_sha=manifest["sourceSha256"],
        frame_count=manifest["frameCount"])
    base = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": manifest["sourceSha256"],
        "seedDocument": seeds_file.name,
        "tracks": [], "screenRelationshipProxies": [],
        "limitations": [
            "Identity/kind/label are operator-provided seeds, not video recognition.",
            "Feature tracking follows local 2D image changes, not semantic re-identification.",
            "A cut, occlusion, blur or low texture ends an unverified track; no hidden gaps are filled.",
            "Co-visible boxes, apparent proximity and overlap cannot establish human interaction.",
        ],
    }
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {**base, "status": "not-run-install-pip-extra-dense"}
    width, height = manifest["width"], manifest["height"]
    if not 64 <= width <= 320 or not 36 <= height <= 180:
        raise ValueError("unsupported local preview resolution")
    shot_for = {}
    for shot in shots["shots"]:
        for item in seeds:
            i = item["startFrameIndex"]
            if shot["startFrameIndex"] <= i < shot["endFrameIndexExclusive"]:
                shot_for[item["id"]] = shot
    for item in seeds:
        shot = shot_for[item["id"]]
        start = item["startFrameIndex"]
        path = workspace / "frames" / f"frame-{start:06d}.png"
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
            raise ValueError("seeded region preview missing or unsafe")
        previous = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if previous is None or previous.shape != (height, width):
            raise ValueError("seeded preview dimensions mismatch")
        x, y, w, h = item["boxNormalized"]
        corners = np.array([
            [x * width, y * height],
            [(x + w) * width, y * height],
            [(x + w) * width, (y + h) * height],
            [x * width, (y + h) * height],
        ], dtype=np.float32)
        obs = [{
            "frameIndex": start,
            "decodedSeconds": numeric["frames"][start]["decodedSeconds"],
            "boxNormalized": [round(float(v), 5) for v in item["boxNormalized"]],
            "screenRotationDegreesFromSeed": 0.,
            "screenScaleRatioFromSeed": 1.,
            "supportFeatureCount": None,
            "status": "operator-provided-seed",
        }]
        end_status = "shot-boundary-or-end"
        if w * width < 12 or h * height < 12:
            end_status = "insufficient-initial-region-size"
        else:
            mask = np.zeros_like(previous)
            x0 = max(0, int(corners[0, 0]))
            y0 = max(0, int(corners[0, 1]))
            x1 = min(width, int(corners[2, 0]))
            y1 = min(height, int(corners[2, 1]))
            mask[y0:y1, x0:x1] = 255
            points = cv2.goodFeaturesToTrack(
                previous, maxCorners=64, qualityLevel=.02,
                minDistance=3, mask=mask, blockSize=3)
            rotation = 0.
            scale = 1.
            if points is None or len(points) < 4:
                end_status = "insufficient-seeded-feature-support"
            else:
                stop = min(start + max_frames_per_subject,
                           shot["endFrameIndexExclusive"])
                for index in range(start + 1, stop):
                    next_path = workspace / "frames" / f"frame-{index:06d}.png"
                    if (next_path.is_symlink() or not next_path.is_file()
                            or next_path.stat().st_size > 1_000_000):
                        raise ValueError("seeded tracking frame preview unsafe")
                    following = cv2.imread(str(next_path), cv2.IMREAD_GRAYSCALE)
                    if following is None or following.shape != (height, width):
                        raise ValueError("seeded tracking image dimensions mismatch")
                    shifted, valid, _ = cv2.calcOpticalFlowPyrLK(
                        previous, following, points, None,
                        winSize=(15, 15), maxLevel=2)
                    if shifted is None or valid is None:
                        end_status = "feature-flow-not-observable"
                        break
                    reverse, reverse_ok, _ = cv2.calcOpticalFlowPyrLK(
                        following, previous, shifted, None,
                        winSize=(15, 15), maxLevel=2)
                    if reverse is None or reverse_ok is None:
                        end_status = "reverse-feature-flow-not-observable"
                        break
                    keep = []
                    for j in range(len(points)):
                        start_pt = points[j, 0]
                        endpoint = shifted[j, 0]
                        if (valid[j, 0] and reverse_ok[j, 0]
                                and np.linalg.norm(reverse[j, 0] - start_pt) <= 1.5
                                and 2 <= endpoint[0] < width-2
                                and 2 <= endpoint[1] < height-2):
                            keep.append(j)
                    if len(keep) < 4:
                        end_status = "insufficient-continuing-feature-support"
                        break
                    a = points[keep].reshape(-1, 2)
                    b = shifted[keep].reshape(-1, 2)
                    transform, inliers = cv2.estimateAffinePartial2D(
                        a, b, method=cv2.RANSAC,
                        ransacReprojThreshold=1.75,
                        maxIters=200, confidence=.99)
                    if transform is None or inliers is None:
                        end_status = "no-robust-local-box-affine"
                        break
                    accepted = int(np.sum(inliers))
                    fraction = accepted / len(keep)
                    affine = np.asarray(transform, dtype=np.float32)
                    local_scale = math.hypot(
                        float(affine[0, 0]), float(affine[1, 0]))
                    local_angle = math.degrees(math.atan2(
                        float(affine[1, 0]), float(affine[0, 0])))
                    if (accepted < 4 or fraction < .6 or
                            not .83 <= local_scale <= 1.2 or
                            abs(local_angle) > 18):
                        end_status = "ambiguous-local-box-motion"
                        break
                    new_corners = corners @ affine[:, :2].T + affine[:, 2]
                    box = _normalized_box(
                        new_corners, width=width, height=height, np=np)
                    if box is None:
                        end_status = "subject-region-outside-image"
                        break
                    corners = new_corners
                    rotation += local_angle
                    scale *= local_scale
                    obs.append({
                        "frameIndex": index,
                        "decodedSeconds": numeric["frames"][index]["decodedSeconds"],
                        "boxNormalized": box,
                        "screenRotationDegreesFromSeed": round(rotation, 4),
                        "screenScaleRatioFromSeed": round(scale, 5),
                        "supportFeatureCount": accepted,
                        "inlierFraction": round(fraction, 4),
                        "status": "tracked-screen-region-candidate",
                    })
                    points = shifted[keep].reshape(-1, 1, 2)
                    previous = following
                if len(obs) == max_frames_per_subject:
                    end_status = "tracking-budget-reached"
        base["tracks"].append({
            "id": item["id"], "label": item["label"], "kind": item["kind"],
            "shotId": shot["shotId"], "startFrameIndex": start,
            "lastObservedFrameIndex": obs[-1]["frameIndex"],
            "observationCount": len(obs),
            "observations": obs, "endStatus": end_status,
            "identityProvenance": "operator-seeded-not-model-recognized",
        })
    base["screenRelationshipProxies"] = screen_relationship_proxies(base["tracks"])
    base["status"] = "seeded-2d-region-motion-candidates"
    return base
