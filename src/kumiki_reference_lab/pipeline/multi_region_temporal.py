"""Offline, timecoded screen-geometry events from *existing* supported ROI tracks.

No media decoding, model inference, automatic identity linking, skeleton pose,
human action detection, or claims of physical interaction. Sources are exact
shot-local frame/time observations already measured by the ROI tracker.
"""
from __future__ import annotations

import math
import statistics
from itertools import combinations
from typing import Any

SCHEMA_VERSION = "kumiki.online-multi-region-temporal.v1"
_ACTIVE = {"seeded-2d-region-motion-candidates",
           "auto-seeded-2d-region-motion-candidates"}
_MISSING = {"not-requested", "not-run-install-pip-extra-dense",
            "not-measured-no-auto-regions"}
_SEED = {"operator-provided-seed", "auto-proposed-region"}
_KINDS = {"animated-character", "person", "product", "text", "prop", "other"}
_ORIGINS = {"operator-seeded-not-model-recognized",
            "auto-motion-proposal-not-semantic-identity"}


def _number(value: Any, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite numeric evidence")
    return float(value)


def _box(raw: Any) -> tuple[float, float, float, float]:
    if not isinstance(raw, list) or len(raw) != 4:
        raise ValueError("multi-region observation lacks a normalized box")
    x, y, w, h = (_number(value, "normalized box") for value in raw)
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1.00001 or y + h > 1.00001:
        raise ValueError("multi-region box lies outside the preview")
    return x, y, w, h


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x, y, w, h = box
    return x + w / 2, y + h / 2


def _iou(a: tuple[float, float, float, float],
         b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    w = max(0., min(ax + aw, bx + bw) - max(ax, bx))
    h = max(0., min(ay + ah, by + bh) - max(ay, by))
    union = aw * ah + bw * bh - w * h
    return w * h / union if union else 0.


def _validate_tracks(data: dict[str, Any], numeric: dict[str, Any],
                     shots: dict[str, Any]) -> list[dict[str, Any]]:
    frames = numeric["frames"]
    shot_by_id = {s["shotId"]: s for s in shots["shots"]}
    output: list[dict[str, Any]] = []
    ids = set()
    tracks = data.get("tracks")
    if not isinstance(tracks, list) or len(tracks) > 8:
        raise ValueError("multi-region track count must be bounded to eight")
    for track in tracks:
        if not isinstance(track, dict):
            raise ValueError("invalid multi-region track")
        ident = track.get("id")
        if (type(ident) is not str or not 1 <= len(ident) <= 48
                or ident in ids or track.get("kind") not in _KINDS
                or track.get("identityProvenance") not in _ORIGINS):
            raise ValueError("invalid multi-region subject provenance or duplicate ID")
        ids.add(ident)
        shot = shot_by_id.get(track.get("shotId"))
        if not shot:
            raise ValueError("multi-region track has unknown shot")
        observations = track.get("observations")
        if not isinstance(observations, list) or not 1 <= len(observations) <= 900:
            raise ValueError("multi-region observation count is unsupported")
        first_status = ("auto-proposed-region"
                        if track["identityProvenance"] ==
                        "auto-motion-proposal-not-semantic-identity"
                        else "operator-provided-seed")
        samples: list[dict[str, Any]] = []
        for n, observation in enumerate(observations):
            if not isinstance(observation, dict):
                raise ValueError("multi-region sample is not an observation")
            i = observation.get("frameIndex")
            if (type(i) is not int or not
                    shot["startFrameIndex"] <= i < shot["endFrameIndexExclusive"]
                    or i >= len(frames)):
                raise ValueError("multi-region sample crosses a shot or frame boundary")
            seconds = _number(observation.get("decodedSeconds"), "decoded time")
            if n and (i != samples[-1]["frame"] + 1 or
                      seconds <= samples[-1]["time"]):
                raise ValueError("multi-region observations cannot bridge a frame gap")
            if (frames[i].get("frameIndex") != i or
                    abs(seconds - _number(frames[i].get("decodedSeconds"),
                                          "source decoded time")) > .00001):
                raise ValueError("multi-region sample has mismatched source PTS")
            box = _box(observation.get("boxNormalized"))
            if n == 0:
                if (observation.get("status") != first_status or
                        i != track.get("startFrameIndex")):
                    raise ValueError("multi-region seed origin and first frame disagree")
            else:
                if (observation.get("status") != "tracked-screen-region-candidate"
                        or type(observation.get("supportFeatureCount")) is not int
                        or observation["supportFeatureCount"] < 4
                        or not .6 <= _number(observation.get("inlierFraction"),
                                              "tracking inlier fraction") <= 1.0):
                    raise ValueError("multi-region observed track has unsupported geometry")
            samples.append({"frame": i, "time": seconds, "box": box,
                            "center": _center(box)})
        if (track.get("lastObservedFrameIndex") != samples[-1]["frame"]
                or track.get("observationCount") != len(samples)):
            raise ValueError("multi-region track summary disagrees with observations")
        output.append({"id": ident, "kind": track["kind"],
                       "shotId": track["shotId"], "origin": track["identityProvenance"],
                       "observations": samples})
    return output


def _event(kind: str, *, a: dict[str, Any],
           first: dict[str, Any], last: dict[str, Any],
           measurements: dict[str, Any],
           b: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "eventType": kind,
        "subjectA": a["id"],
        "subjectB": b["id"] if b is not None else None,
        "shotId": a["shotId"],
        "startFrameIndex": first["frame"],
        "endFrameIndex": last["frame"],
        "startSeconds": round(first["time"], 6),
        "endSeconds": round(last["time"], 6),
        "measurements": measurements,
        "status": "measured-screen-geometry-not-semantic-action",
        "identityProvenance": ([a["origin"], b["origin"]] if b is not None
                               else [a["origin"]]),
    }


def _direction(dx: float, dy: float) -> str:
    if abs(dx) >= abs(dy) * 1.5:
        return "right-in-image" if dx > 0 else "left-in-image"
    if abs(dy) >= abs(dx) * 1.5:
        return "down-in-image" if dy > 0 else "up-in-image"
    return "diagonal-in-image"


def _single_events(track: dict[str, Any], *,
                   min_frames: int) -> list[dict[str, Any]]:
    samples = track["observations"]
    if len(samples) < min_frames:
        return []
    first, last = samples[0], samples[-1]
    duration = last["time"] - first["time"]
    if duration < .2:
        return []
    dx = last["center"][0] - first["center"][0]
    dy = last["center"][1] - first["center"][1]
    net = math.hypot(dx, dy)
    steps = [math.dist(a["center"], b["center"])
             for a, b in zip(samples, samples[1:])]
    traveled = sum(steps)
    out: list[dict[str, Any]] = []
    if net >= .035:
        out.append(_event(
            "region-image-plane-translation", a=track,
            first=first, last=last, measurements={
                "deltaCenterNormalized": [round(dx, 5), round(dy, 5)],
                "netDistanceNormalized": round(net, 5),
                "pathDistanceNormalized": round(traveled, 5),
                "straightnessProxy": round(net / traveled, 5) if traveled else None,
                "direction": _direction(dx, dy),
                "avgNetSpeedNormalizedPerSecond": round(net / duration, 5),
            }))
    start_area = first["box"][2] * first["box"][3]
    end_area = last["box"][2] * last["box"][3]
    ratio = end_area / start_area
    if ratio >= 1.30 or ratio <= .77:
        out.append(_event(
            "region-apparent-box-area-change", a=track,
            first=first, last=last, measurements={
                "endToStartBoxAreaRatio": round(ratio, 5),
                "appearance": ("larger-in-image" if ratio > 1
                               else "smaller-in-image"),
            }))
    return out


def _pair_events(a: dict[str, Any], b: dict[str, Any], *,
                 min_frames: int) -> tuple[dict[str, Any] | None,
                                           list[dict[str, Any]]]:
    if a["shotId"] != b["shotId"]:
        return None, []
    aa = {p["frame"]: p for p in a["observations"]}
    bb = {p["frame"]: p for p in b["observations"]}
    common = sorted(set(aa).intersection(bb))
    if len(common) < min_frames:
        return None, []
    # Never bridge discontinuity or claim unseen co-visibility.
    if any(y != x + 1 for x, y in zip(common, common[1:])):
        return None, []
    first_frame, last_frame = common[0], common[-1]
    start, end = aa[first_frame], aa[last_frame]
    duration = end["time"] - start["time"]
    if duration < .2:
        return None, []
    if any(abs(aa[i]["time"] - bb[i]["time"]) > .00001 for i in common):
        raise ValueError("pairwise ROI decoder timestamps do not agree")
    d = [math.dist(aa[i]["center"], bb[i]["center"]) for i in common]
    overlap = [_iou(aa[i]["box"], bb[i]["box"]) for i in common]
    horizontal = [aa[i]["center"][0] - bb[i]["center"][0] for i in common]
    start_distance = statistics.median(d[:2])
    end_distance = statistics.median(d[-2:])
    separation_change = end_distance - start_distance
    first = {"frame": first_frame, "time": start["time"]}
    last = {"frame": last_frame, "time": end["time"]}
    metrics = {
        "subjectA": a["id"], "subjectB": b["id"], "shotId": a["shotId"],
        "startFrameIndex": first_frame, "endFrameIndex": last_frame,
        "coObservedConsecutiveFrameCount": len(common),
        "startCenterDistanceNormalized": round(start_distance, 5),
        "endCenterDistanceNormalized": round(end_distance, 5),
        "closestCenterDistanceNormalized": round(min(d), 5),
        "closestFrameIndex": common[min(range(len(d)), key=lambda i: d[i])],
        "overlapFrameCount": sum(value > .02 for value in overlap),
        "maximumBoxIoU": round(max(overlap), 5),
        "status": "pairwise-screen-measurement-not-physical-interaction",
        "identityProvenance": [a["origin"], b["origin"]],
    }
    ev: list[dict[str, Any]] = []
    if abs(separation_change) >= .05:
        ev.append(_event(
            ("screen-centers-closer" if separation_change < 0
             else "screen-centers-farther"), a=a, b=b, first=first,
            last=last, measurements={
                "distanceChangeNormalized": round(separation_change, 5),
                "startDistanceNormalized": round(start_distance, 5),
                "endDistanceNormalized": round(end_distance, 5),
            }))
    if (max(overlap[:2]) <= .01 and min(overlap[-2:]) >= .05):
        hit = next(i for i, value in enumerate(overlap) if value >= .05)
        ev.append(_event(
            "screen-box-overlap-onset", a=a, b=b, first=first, last=last,
            measurements={"firstObservedOverlapFrameIndex": common[hit],
                          "endBoxIoU": round(overlap[-1], 5)}))
    h0, h1 = statistics.median(horizontal[:2]), statistics.median(horizontal[-2:])
    if h0 * h1 < 0 and min(abs(h0), abs(h1)) >= .03:
        ev.append(_event(
            "horizontal-image-order-reversal", a=a, b=b,
            first=first, last=last, measurements={
                "firstAminusBCenterX": round(h0, 5),
                "lastAminusBCenterX": round(h1, 5),
            }))
    da = (aa[last_frame]["center"][0] - aa[first_frame]["center"][0],
          aa[last_frame]["center"][1] - aa[first_frame]["center"][1])
    db = (bb[last_frame]["center"][0] - bb[first_frame]["center"][0],
          bb[last_frame]["center"][1] - bb[first_frame]["center"][1])
    coherent = (math.hypot(*da) >= .04 and math.hypot(*db) >= .04
                and math.dist(da, db) <= .025)
    if coherent:
        ev.append(_event(
            "shared-image-plane-displacement", a=a, b=b,
            first=first, last=last, measurements={
                "aDeltaCenterNormalized": [round(v, 5) for v in da],
                "bDeltaCenterNormalized": [round(v, 5) for v in db],
                "possibleAlternatives": ["shared camera motion", "parallax",
                                         "independent synchronized motion"],
            }))
    return metrics, ev


def build_multi_region_temporal(
    seeded: dict[str, Any], numeric: dict[str, Any],
    shots: dict[str, Any], *,
    min_supported_frames: int = 6,
    max_events: int = 80, max_review_tasks: int = 24,
) -> dict[str, Any]:
    """Source-bound per-track and concurrent pairwise image-plane events."""
    if (type(min_supported_frames) is not int
            or not 4 <= min_supported_frames <= 30
            or type(max_events) is not int or not 1 <= max_events <= 200
            or type(max_review_tasks) is not int or not 1 <= max_review_tasks <= 48):
        raise ValueError("invalid multi-region timing/report budgets")
    if (not isinstance(seeded, dict) or not isinstance(numeric, dict)
            or not isinstance(shots, dict)
            or type(numeric.get("sourceSha256")) is not str
            or len(numeric["sourceSha256"]) != 64
            or any(c not in "0123456789abcdef" for c in numeric["sourceSha256"])
            or numeric.get("frameCount") != len(numeric.get("frames", []))
            or shots.get("sourceSha256") != numeric["sourceSha256"]
            or shots.get("frameCount") != numeric["frameCount"]):
        raise ValueError("multi-region source/shot evidence mismatch")
    sha = numeric["sourceSha256"]
    status = seeded.get("status")
    base = {
        "schemaVersion": SCHEMA_VERSION, "sourceSha256": sha,
        "frameCount": numeric["frameCount"],
        "trackCount": 0, "pairCount": 0,
        "pairMetrics": [], "events": [], "reviewTasks": [],
        "limitations": [
            "Only existing consecutive feature-supported, shot-local ROI boxes are measured.",
            "Operator seeds are not independently recognized identities.",
            "Automatic ROI labels remain anonymous motion regions.",
            "Center proximity and box overlap do not establish touch, interaction, intent or dialogue.",
            "Similar displacement can result from camera motion or layered animation.",
            "Bounding-box size changes do not prove a 3D zoom or a real action.",
            "No post-cut reidentification, inferred missing frames, pose or skeletal tracking.",
            "Frame review tasks are prompts for future inspection, not verified scene actions.",
        ],
    }
    if status in _MISSING:
        return {**base, "status": "not-measured-no-supported-roi-tracks"}
    if status not in _ACTIVE or seeded.get("sourceSha256") != sha:
        raise ValueError("multi-region ROI provenance/status mismatch")
    tracks = _validate_tracks(seeded, numeric, shots)
    events = []
    pairs = []
    for track in tracks:
        events.extend(_single_events(track, min_frames=min_supported_frames))
    for a, b in combinations(tracks, 2):
        measured, pair_events = _pair_events(a, b,
                                              min_frames=min_supported_frames)
        if measured is not None:
            pairs.append(measured)
            events.extend(pair_events)
    events.sort(key=lambda e: (
        e["startFrameIndex"], e["endFrameIndex"],
        e["eventType"], e["subjectA"], e["subjectB"] or ""))
    events = events[:max_events]
    review = []
    for item in events[:max_review_tasks]:
        start, end = item["startFrameIndex"], item["endFrameIndex"]
        anchors = sorted({start, (start + end) // 2, end})
        review.append({
            "shotId": item["shotId"], "eventType": item["eventType"],
            "subjectIds": [item["subjectA"]] + (
                [item["subjectB"]] if item["subjectB"] else []),
            "frameIndices": anchors,
            "reviewPurpose": "verify-visible-screen-geometry-and-alternatives",
            "status": "unreviewed-source-frame-suggestion-not-model-call",
        })
    return {
        **base,
        "status": ("measured-shot-local-screen-geometry-events" if events
                   else "no-supported-screen-geometry-events"),
        "trackCount": len(tracks), "pairCount": len(pairs),
        "pairMetrics": pairs[:28], "events": events, "reviewTasks": review,
    }
