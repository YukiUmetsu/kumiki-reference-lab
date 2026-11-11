"""Conservative offline motion-region suggestions from saved reference PNGs.

No AI, CV2, NumPy, face/person classification, cross-cut reidentification, or
download. Detects recurring visual changes; NEVER claims the region is a
particular character, product, or object. Only high-support regions against a
nearly uniform backdrop are eligible as *unverified* automatic ROI seeds.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from kumiki_reference_lab.pipeline.online_temporal import _decode_review_png

SCHEMA_VERSION = "kumiki.auto-motion-region-proposals.v1"
SEEDS_SCHEMA = "kumiki.online-region-seeds.v1"


def _preview_rgb(raw: bytes, width: int, height: int, *, step: int = 2
                 ) -> tuple[list[tuple[int, int, int]], int, int]:
    if len(raw) != width * height * 3:
        raise ValueError("auto ROI received unexpected RGB dimensions")
    cells = []
    for y in range(0, height, step):
        for x in range(0, width, step):
            at = (y * width + x) * 3
            cells.append((raw[at], raw[at + 1], raw[at + 2]))
    return cells, (width + step - 1) // step, (height + step - 1) // step


def _components(mask: list[bool], w: int, h: int, *,
                limit: int = 64) -> list[dict[str, int]]:
    """Bounded 4-connected areas on a small 2x spatially reduced grid."""
    if len(mask) != w * h or w * h > 15000:
        raise ValueError("auto ROI component grid exceeds bounds")
    seen = bytearray(w * h)
    out: list[dict[str, int]] = []
    for initial, flag in enumerate(mask):
        if not flag or seen[initial]:
            continue
        stack = [initial]
        seen[initial] = 1
        size = 0
        minx = maxx = initial % w
        miny = maxy = initial // w
        while stack:
            i = stack.pop()
            y, x = divmod(i, w)
            size += 1
            minx, maxx = min(x, minx), max(x, maxx)
            miny, maxy = min(y, miny), max(y, maxy)
            for next_i in (i - w if y else -1,
                           i + w if y < h - 1 else -1,
                           i - 1 if x else -1,
                           i + 1 if x < w - 1 else -1):
                if next_i >= 0 and mask[next_i] and not seen[next_i]:
                    seen[next_i] = 1
                    stack.append(next_i)
        if 12 <= size <= int(w * h * .44):
            out.append({"x0": minx, "x1": maxx + 1,
                        "y0": miny, "y1": maxy + 1,
                        "area": size})
        if len(out) > limit:
            # A noisy/dithered composite is not a reliable object detector.
            return []
    return out


def _box(component: dict[str, int], w: int, h: int,
         *, margin: int = 2) -> list[float]:
    x0 = max(0, component["x0"] - margin)
    x1 = min(w, component["x1"] + margin)
    y0 = max(0, component["y0"] - margin)
    y1 = min(h, component["y1"] + margin)
    return [round(x0 / w, 5), round(y0 / h, 5),
            round((x1 - x0) / w, 5), round((y1 - y0) / h, 5)]


def _iou(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x = max(0., min(ax + aw, bx + bw) - max(ax, bx))
    y = max(0., min(ay + ah, by + bh) - max(ay, by))
    union = aw * ah + bw * bh - x * y
    return x * y / union if union else 0.0


def _center_dist(a: list[float], b: list[float]) -> float:
    return math.hypot((a[0] + a[2] / 2) - (b[0] + b[2] / 2),
                      (a[1] + a[3] / 2) - (b[1] + b[3] / 2))


def _candidates(first: bytes, second: bytes, *,
                width: int, height: int) -> tuple[list[dict[str, Any]], str]:
    left, w, h = _preview_rgb(first, width, height)
    right, _, _ = _preview_rgb(second, width, height)
    delta = [
        (abs(a[0] - b[0]) + abs(a[1] - b[1]) +
         abs(a[2] - b[2])) >= 75
        for a, b in zip(left, right)
    ]
    changed = sum(delta) / len(delta)
    if changed < .003:
        return [], "insufficient-visible-change"
    if changed > .38:
        return [], "global-change-flash-camera-or-cut"
    corners = [right[0], right[w - 1],
               right[(h - 1) * w], right[-1]]
    background = tuple(round(sum(c[channel] for c in corners) / 4)
                       for channel in range(3))
    variance = max(
        max(abs(c[i] - background[i]) for i in range(3))
        for c in corners
    )
    uniform = variance <= 24
    if uniform:
        fg_mask = [
            max(abs(pixel[k] - background[k]) for k in range(3)) >= 52
            for pixel in right
        ]
        regions = _components(fg_mask, w, h)
        method = "uniform-border-foreground-intersected-with-change"
    else:
        regions = _components(delta, w, h)
        method = "temporal-change-only-unverified-shape"
    candidates = []
    for region in regions:
        rectangle = _box(region, w, h)
        if (rectangle[2] * width < 12 or rectangle[3] * height < 12
                or rectangle[2] * rectangle[3] > .5):
            continue
        active = sum(delta[y * w + x]
                     for y in range(region["y0"], region["y1"])
                     for x in range(region["x0"], region["x1"]))
        overlap = active / max(1, region["area"])
        if active < 6 or overlap < .035:
            continue
        candidates.append({
            "boxNormalized": rectangle,
            "changedCellCount": active,
            "componentCellCount": region["area"],
            "motionOverlapFraction": round(min(1., overlap), 5),
            "method": method,
            "eligibleForAutomaticTracking": uniform,
            "status": "motion-related-screen-region-not-recognized-subject",
        })
    return sorted(candidates, key=lambda r: (
        -r["motionOverlapFraction"], -r["changedCellCount"])
    )[:12], method


def _pair_schedule(shots: dict[str, Any], *,
                   max_pairs: int) -> list[tuple[str, int, int]]:
    pending: list[list[tuple[str, int, int]]] = []
    for shot in shots["shots"]:
        start, stop = shot["startFrameIndex"], shot["endFrameIndexExclusive"]
        # Allow >=4 frames after detection for the downstream flow tracker.
        # Three-frame lag helps observe a moving graphic on a simple background.
        pairs = [(shot["shotId"], frame - 3, frame)
                 for frame in range(start + 6, stop - 4, 3)]
        pending.append(pairs)
    chosen = []
    while len(chosen) < max_pairs and any(pending):
        for bucket in pending:
            if bucket and len(chosen) < max_pairs:
                chosen.append(bucket.pop(0))
    return sorted(chosen, key=lambda item: (item[1], item[2]))


def discover_motion_regions(workspace: Path, shots: dict[str, Any], *,
                            max_pairs: int = 36,
                            max_regions: int = 6) -> dict[str, Any]:
    """Find repeatable potential ROIs; never label semantic classes."""
    from kumiki_reference_lab.pipeline.agent_frame_review import (
        load_workspace, _frame_path,
    )
    if (type(max_pairs) is not int or not 2 <= max_pairs <= 120
            or type(max_regions) is not int or not 1 <= max_regions <= 8):
        raise ValueError("auto region analysis budget invalid")
    manifest, numeric, _ = load_workspace(workspace)
    if (not isinstance(shots, dict)
            or shots.get("sourceSha256") != manifest["sourceSha256"]
            or shots.get("frameCount") != manifest["frameCount"]):
        raise ValueError("auto region source/shot provenance mismatch")
    width, height = manifest["width"], manifest["height"]
    if (type(width) is not int or type(height) is not int
            or not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("auto region preview dimensions unsupported")
    selected = _pair_schedule(shots, max_pairs=max_pairs)
    cache: dict[int, bytes] = {}
    def frame(index: int) -> bytes:
        if index not in cache:
            cache[index] = _decode_review_png(
                _frame_path(workspace.absolute(), index),
                width=width, height=height)
        while len(cache) > 4:
            cache.pop(next(iter(cache)))
        return cache[index]

    groups: list[dict[str, Any]] = []
    rejected_global = 0
    for shot_id, before, after in selected:
        regions, status = _candidates(
            frame(before), frame(after), width=width, height=height)
        if status == "global-change-flash-camera-or-cut":
            rejected_global += 1
            continue
        for region in regions:
            box = region["boxNormalized"]
            # Match only within the same shot; this is NOT cross-cut identity.
            group = next((g for g in groups
                          if g["shotId"] == shot_id and
                          (g["lastFrameIndex"] != after and
                           (_iou(g["lastBoxNormalized"], box) >= .15 or
                            _center_dist(g["lastBoxNormalized"], box) <= .07))),
                         None)
            if group is None:
                if len(groups) >= 96:
                    continue
                groups.append({
                    "shotId": shot_id, "startFrameIndex": after,
                    "lastFrameIndex": after,
                    "firstBoxNormalized": box,
                    "lastBoxNormalized": box,
                    "observedFrameIndices": [after],
                    "method": region["method"],
                    "motionEvidenceCells": region["changedCellCount"],
                    "eligibleForAutomaticTracking": region[
                        "eligibleForAutomaticTracking"],
                })
            else:
                group["lastFrameIndex"] = after
                group["lastBoxNormalized"] = box
                group["observedFrameIndices"].append(after)
                group["motionEvidenceCells"] += region["changedCellCount"]
                group["eligibleForAutomaticTracking"] = (
                    group["eligibleForAutomaticTracking"] and
                    region["eligibleForAutomaticTracking"])
    eligible = [g for g in groups if len(g["observedFrameIndices"]) >= 2]
    eligible.sort(key=lambda g: (
        not g["eligibleForAutomaticTracking"],
        -len(g["observedFrameIndices"]),
        -g["motionEvidenceCells"],
        g["startFrameIndex"],
    ))
    chosen: list[dict[str, Any]] = []
    for group in eligible:
        if len(chosen) >= max_regions:
            break
        if any(other["shotId"] == group["shotId"] and
               _iou(other["firstBoxNormalized"],
                    group["firstBoxNormalized"]) >= .35
               for other in chosen):
            continue
        chosen.append(group)
    proposals = []
    for i, group in enumerate(chosen, 1):
        box = group["firstBoxNormalized"]
        proposals.append({
            "id": f"auto-region-{i:02d}",
            "kind": "other",
            "label": f"Unclassified motion region {i}",
            "startFrameIndex": group["startFrameIndex"],
            "boxNormalized": box,
            "shotId": group["shotId"],
            "observedFrameIndices": group["observedFrameIndices"],
            "motionEvidenceCells": group["motionEvidenceCells"],
            "regionDiscoveryMethod": group["method"],
            "eligibleForAutomaticTracking":
                group["eligibleForAutomaticTracking"],
            "status": "unverified-visual-region-proposal-not-subject-identity",
        })
    seeds = [{
        "id": proposal["id"], "kind": "other",
        "label": proposal["label"],
        "startFrameIndex": proposal["startFrameIndex"],
        "boxNormalized": proposal["boxNormalized"],
    } for proposal in proposals if proposal["eligibleForAutomaticTracking"]]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": manifest["sourceSha256"],
        "frameCount": manifest["frameCount"],
        "pairsInspected": len(selected),
        "rejectedGlobalChangePairs": rejected_global,
        "regionProposalCount": len(proposals),
        "autoTrackSeedCount": len(seeds),
        "proposals": proposals,
        "autoTrackSeeds": {
            "schemaVersion": SEEDS_SCHEMA,
            "seedOrigin": "auto-motion-proposal",
            "sourceSha256": manifest["sourceSha256"],
            "subjects": seeds,
        },
        "status": ("unverified-regions-proposed" if proposals
                   else "no-persistent-local-motion-regions-found"),
        "limitations": [
            "Movement or high visual contrast does not establish a character, product or other object class.",
            "Automatic tracking eligibility requires repeatable movement against an almost uniform border background.",
            "A changing mask can contain shadows, typography, fragments, or multiple objects.",
            "Complex backgrounds and moving cameras may produce no safe seeds; these are abstentions, not missing video.",
            "Region proposals never bridge cuts and must be reviewed before semantic labeling.",
            "Only low-resolution local RGB previews were read; no AI or downloaded video is used.",
        ],
    }
