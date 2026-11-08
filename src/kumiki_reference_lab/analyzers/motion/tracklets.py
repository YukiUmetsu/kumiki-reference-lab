"""Conservative temporal links between independently detected sparse-flow vectors.

Each link is a two-dimensional image-plane candidate, never semantic identity,
camera motion, or recovery across a cut or occlusion. Ambiguity means abstain.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from kumiki_reference_lab.analyzers.motion.handoff_appearance import (
    MAX_ENDPOINT_SHIFT_PIXELS, MIN_NCC, PATCH_SIZE, two_hop_patch_agreement,
)

LINK_TOLERANCE_PIXELS = 2.0
AMBIGUITY_MARGIN_PIXELS = 0.5
MIN_TRACK_PAIRS = 2
MOTION_MIN_TOLERANCE_PIXELS = 2.5
MOTION_RELATIVE_TOLERANCE = 0.6


def _observation(pair: dict[str, Any], pair_index: int, vector_index: int,
                 handoff_error: float | None, *, motion_check: bool = False,
                 motion_residual: float | None = None,
                 motion_allowance: float | None = None,
                 appearance_check: bool = False,
                 appearance_score: float | None = None,
                 appearance_shift: dict[str, int] | None = None) -> dict[str, Any]:
    vector = pair["vectors"][vector_index]
    x, y = vector["x"], vector["y"]
    observation = {
        "pairIndex": pair_index, "vectorIndex": vector_index,
        "startPts": pair["startPts"], "endPts": pair["endPts"],
        "startPixels": {"x": x, "y": y},
        "endPixels": {"x": x + vector["dx"], "y": y + vector["dy"]},
        "handoffErrorPixels": round(handoff_error, 4) if handoff_error is not None else None,
        "group": vector.get("group", "unclassified"),
    }
    if motion_check:
        observation.update({"motionResidualPixels": (round(motion_residual, 4)
                                                      if motion_residual is not None else None),
                            "motionAllowancePixels": (round(motion_allowance, 4)
                                                       if motion_allowance is not None else None)})
    if appearance_check:
        observation.update({"twoHopAppearanceCorrelation": appearance_score,
                            "twoHopAppearanceShiftPixels": appearance_shift})
    return observation


def _motion_agreement(track: dict[str, Any], pair: dict[str, Any],
                      vector: dict[str, Any]) -> tuple[float, float]:
    """Compare two observed offsets over their *actual* source-PTS durations.

    Constant image-plane velocity is merely a cautious linking prior, not a
    physical object model; abrupt motion or occlusion can produce abstention.
    """
    prior = track["observations"][-1]
    old_duration = prior["endPts"] - prior["startPts"]
    new_duration = pair["endPts"] - pair["startPts"]
    if old_duration <= 0 or new_duration <= 0:
        raise ValueError("motion continuity requires increasing source PTS")
    ratio = new_duration / old_duration
    expected_x = (prior["endPixels"]["x"] - prior["startPixels"]["x"]) * ratio
    expected_y = (prior["endPixels"]["y"] - prior["startPixels"]["y"]) * ratio
    observed_x, observed_y = vector["dx"], vector["dy"]
    residual = math.hypot(observed_x - expected_x, observed_y - expected_y)
    tolerance = max(MOTION_MIN_TOLERANCE_PIXELS,
                    MOTION_RELATIVE_TOLERANCE * max(math.hypot(expected_x, expected_y),
                                                    math.hypot(observed_x, observed_y)))
    if not math.isfinite(residual) or not math.isfinite(tolerance):
        raise ValueError("motion continuity requires finite displacements")
    return residual, tolerance


def _unambiguous_links(
    previous: list[dict[str, Any]], vectors: list[dict[str, Any]],
    *, pair: dict[str, Any] | None = None,
    motion_consistency: bool = False,
    appearance_frames: tuple[bytes, bytes] | None = None,
    frame_size: tuple[int, int] | None = None,
) -> tuple[dict[int, tuple[Any, ...]], int, int, int]:
    """Return mutual nearest neighbors whose alternatives are not nearly as good."""
    candidates: list[tuple[float, int, int]] = []
    rejected_motion = 0
    rejected_appearance = 0
    unavailable_appearance = 0
    if motion_consistency and pair is None:
        raise ValueError("motion continuity requires the current source-PTS pair")
    if (appearance_frames is None) != (frame_size is None):
        raise ValueError("two-hop appearance requires paired frames and dimensions")
    for old_index, track in enumerate(previous):
        end = track["observations"][-1]["endPixels"]
        for new_index, vector in enumerate(vectors):
            distance = math.hypot(end["x"] - vector["x"], end["y"] - vector["y"])
            if distance <= LINK_TOLERANCE_PIXELS:
                candidates.append((distance, old_index, new_index))
    by_old: dict[int, list[tuple[float, int]]] = {}
    by_new: dict[int, list[tuple[float, int]]] = {}
    for distance, old_index, new_index in candidates:
        by_old.setdefault(old_index, []).append((distance, new_index))
        by_new.setdefault(new_index, []).append((distance, old_index))
    for options in (*by_old.values(), *by_new.values()):
        options.sort()

    links: dict[int, tuple[Any, ...]] = {}
    for old_index, options in sorted(by_old.items()):
        distance, new_index = options[0]
        back = by_new[new_index]
        if back[0][1] != old_index:
            continue
        if ((len(options) > 1 and options[1][0] - distance < AMBIGUITY_MARGIN_PIXELS) or
                (len(back) > 1 and back[1][0] - back[0][0] < AMBIGUITY_MARGIN_PIXELS)):
            continue
        residual, allowance = (None, None)
        if motion_consistency:
            residual, allowance = _motion_agreement(previous[old_index], pair,
                                                     vectors[new_index])
            if residual > allowance:
                rejected_motion += 1
                continue
        appearance_score, appearance_shift = (None, None)
        if appearance_frames is not None:
            vector = vectors[new_index]
            result = two_hop_patch_agreement(
                appearance_frames[0], appearance_frames[1], *frame_size,
                first_point=previous[old_index]["observations"][-1]["startPixels"],
                last_point={"x": vector["x"] + vector["dx"],
                            "y": vector["y"] + vector["dy"]})
            if result["status"] != "appearance-consistent":
                if result["status"] == "unobservable":
                    unavailable_appearance += 1
                else:
                    rejected_appearance += 1
                continue
            appearance_score, appearance_shift = result["correlation"], result["shiftPixels"]
        links[old_index] = (new_index, distance, residual, allowance,
                            appearance_score, appearance_shift)
    return links, rejected_motion, rejected_appearance, unavailable_appearance


def build_sparse_tracklets(
    pairs: list[dict[str, Any]], *, timebase: Fraction,
    motion_consistency: bool = False,
    appearance_consistency: bool = False,
    appearance_frames: list[bytes] | None = None,
    frame_width: int | None = None, frame_height: int | None = None,
) -> dict[str, Any]:
    """Link evidence across adjacent decoded samples with no guessed gap filling.

    Only tracks supported by >=2 consecutive pair vectors are published;
    single-pair vectors remain available in the original pair evidence.
    """
    if not isinstance(timebase, Fraction) or timebase <= 0:
        raise ValueError("sparse tracklet source timebase must be a positive rational")
    if type(motion_consistency) is not bool:
        raise ValueError("motion_consistency must be a boolean")
    if type(appearance_consistency) is not bool:
        raise ValueError("appearance_consistency must be a boolean")
    if appearance_consistency:
        if (type(frame_width) is not int or type(frame_height) is not int or
                not 64 <= frame_width <= 240 or not 36 <= frame_height <= 135 or
                not isinstance(appearance_frames, list) or
                len(appearance_frames) != len(pairs) + 1 or
                any(type(frame) is not bytes or len(frame) != frame_width * frame_height
                    for frame in appearance_frames)):
            raise ValueError("two-hop appearance requires all bounded sampled grayscale frames")

    active: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    singletons = 0
    motion_rejections = 0
    appearance_rejections = 0
    appearance_unavailable = 0
    next_id = 1

    def finish(track: dict[str, Any], reason: str) -> None:
        nonlocal singletons
        observations = track["observations"]
        if len(observations) < MIN_TRACK_PAIRS:
            singletons += 1
            return
        elapsed = (observations[-1]["endPts"] - observations[0]["startPts"]) * timebase
        if elapsed <= 0:
            raise ValueError("sparse tracklet has non-positive source presentation duration")
        dx = sum(o["endPixels"]["x"] - o["startPixels"]["x"] for o in observations)
        dy = sum(o["endPixels"]["y"] - o["startPixels"]["y"] for o in observations)
        distance = sum(math.hypot(o["endPixels"]["x"] - o["startPixels"]["x"],
                                  o["endPixels"]["y"] - o["startPixels"]["y"])
                       for o in observations)
        try:
            duration_seconds = float(elapsed)
        except OverflowError as exc:
            raise ValueError("sparse tracklet source presentation duration is not representable") from exc
        if not math.isfinite(duration_seconds) or duration_seconds <= 0:
            raise ValueError("sparse tracklet source presentation duration is not representable")
        completed.append({**track, "pairCount": len(track["observations"]),
                          "endReason": reason,
                          "kinematics": {
                              "durationSeconds": {
                                  "numerator": elapsed.numerator,
                                  "denominator": elapsed.denominator,
                              },
                              "summedImageDisplacementPixels": {
                                  "dx": dx, "dy": dy,
                              },
                              "observedPathLengthPixels": round(distance, 4),
                              "meanImageVelocityPixelsPerSecond": {
                                  "dx": round(dx / duration_seconds, 4),
                                  "dy": round(dy / duration_seconds, 4),
                              },
                              "meanImageSpeedPixelsPerSecond": round(
                                  distance / duration_seconds, 4),
                              "basis": "observed-pairs-only-no-gap-filling",
                              "calibratedConfidence": False,
                          }})

    for pair_index, pair in enumerate(pairs):
        if pair["endPts"] <= pair["startPts"]:
            raise ValueError("sparse tracklet pair must have increasing source PTS")
        vectors = pair["vectors"]
        is_cut = pair["status"] == "cut-boundary"
        adjacent = (pair_index > 0 and
                    pairs[pair_index - 1]["endPts"] == pair["startPts"] and
                    pairs[pair_index - 1]["status"] != "cut-boundary")
        if is_cut or not adjacent:
            reason = "cut-boundary" if is_cut else "nonadjacent-or-missing-observation"
            for track in active:
                finish(track, reason)
            active = []
        if is_cut:
            continue

        links, motion_lost, appearance_lost, appearance_missing = (
            _unambiguous_links(
                active, vectors, pair=pair, motion_consistency=motion_consistency,
                appearance_frames=(appearance_frames[pair_index - 1],
                                   appearance_frames[pair_index + 1])
                if appearance_consistency else None,
                frame_size=(frame_width, frame_height) if appearance_consistency else None)
            if adjacent else ({}, 0, 0, 0))
        motion_rejections += motion_lost
        appearance_rejections += appearance_lost
        appearance_unavailable += appearance_missing
        next_active: list[dict[str, Any]] = []
        linked_new: set[int] = set()
        for old_index, track in enumerate(active):
            if old_index not in links:
                finish(track, "no-safe-match")
                continue
            vector_index, error, residual, allowance, appearance_score, appearance_shift = (
                links[old_index])
            track["observations"].append(_observation(
                pair, pair_index, vector_index, error, motion_check=motion_consistency,
                motion_residual=residual, motion_allowance=allowance,
                appearance_check=appearance_consistency,
                appearance_score=appearance_score, appearance_shift=appearance_shift))
            next_active.append(track)
            linked_new.add(vector_index)
        for vector_index in range(len(vectors)):
            if vector_index in linked_new:
                continue
            track = {"id": f"tracklet-{next_id:04d}",
                     "observations": [_observation(pair, pair_index, vector_index, None,
                                                   motion_check=motion_consistency,
                                                   appearance_check=appearance_consistency)]}
            next_id += 1
            next_active.append(track)
        active = next_active

    for track in active:
        finish(track, "scan-end")
    completed.sort(key=lambda track: int(track["id"].split("-")[1]))
    result = {
        "status": "candidate-only" if completed else "insufficient-continuity",
        "method": ("mutual-nearest-adjacent-endpoint" +
                   ("-motion-gated" if motion_consistency else "") +
                   ("-appearance-gated" if appearance_consistency else "") + "-v1"),
        "linkTolerancePixels": LINK_TOLERANCE_PIXELS,
        "ambiguityMarginPixels": AMBIGUITY_MARGIN_PIXELS,
        "minConsecutivePairs": MIN_TRACK_PAIRS,
        "calibratedConfidence": False,
        "semanticIdentityVerified": False,
        "singlePairCandidatesDiscarded": singletons,
        "tracklets": completed,
    }
    if motion_consistency:
        result.update({"motionMinimumTolerancePixels": MOTION_MIN_TOLERANCE_PIXELS,
                       "motionRelativeTolerance": MOTION_RELATIVE_TOLERANCE,
                       "motionInconsistentLinkCandidates": motion_rejections})
    if appearance_consistency:
        result.update({"appearancePatchSizePixels": PATCH_SIZE,
                       "appearanceMaxEndpointShiftPixels": MAX_ENDPOINT_SHIFT_PIXELS,
                       "appearanceMinCorrelation": MIN_NCC,
                       "appearanceInconsistentLinkCandidates": appearance_rejections,
                       "appearanceUnobservableLinkCandidates": appearance_unavailable})
    return result
