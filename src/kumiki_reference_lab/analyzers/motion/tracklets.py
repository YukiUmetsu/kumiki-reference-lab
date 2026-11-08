"""Conservative temporal links between independently detected sparse-flow vectors.

Each link is a two-dimensional image-plane candidate, never semantic identity,
camera motion, or recovery across a cut or occlusion. Ambiguity means abstain.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

LINK_TOLERANCE_PIXELS = 2.0
AMBIGUITY_MARGIN_PIXELS = 0.5
MIN_TRACK_PAIRS = 2


def _observation(pair: dict[str, Any], pair_index: int, vector_index: int,
                 handoff_error: float | None) -> dict[str, Any]:
    vector = pair["vectors"][vector_index]
    x, y = vector["x"], vector["y"]
    return {
        "pairIndex": pair_index, "vectorIndex": vector_index,
        "startPts": pair["startPts"], "endPts": pair["endPts"],
        "startPixels": {"x": x, "y": y},
        "endPixels": {"x": x + vector["dx"], "y": y + vector["dy"]},
        "handoffErrorPixels": round(handoff_error, 4) if handoff_error is not None else None,
        "group": vector.get("group", "unclassified"),
    }


def _unambiguous_links(
    previous: list[dict[str, Any]], vectors: list[dict[str, Any]],
) -> dict[int, tuple[int, float]]:
    """Return mutual nearest neighbors whose alternatives are not nearly as good."""
    candidates: list[tuple[float, int, int]] = []
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

    links: dict[int, tuple[int, float]] = {}
    for old_index, options in sorted(by_old.items()):
        distance, new_index = options[0]
        back = by_new[new_index]
        if back[0][1] != old_index:
            continue
        if ((len(options) > 1 and options[1][0] - distance < AMBIGUITY_MARGIN_PIXELS) or
                (len(back) > 1 and back[1][0] - back[0][0] < AMBIGUITY_MARGIN_PIXELS)):
            continue
        links[old_index] = (new_index, distance)
    return links


def build_sparse_tracklets(
    pairs: list[dict[str, Any]], *, timebase: Fraction,
) -> dict[str, Any]:
    """Link evidence across adjacent decoded samples with no guessed gap filling.

    Only tracks supported by >=2 consecutive pair vectors are published;
    single-pair vectors remain available in the original pair evidence.
    """
    if not isinstance(timebase, Fraction) or timebase <= 0:
        raise ValueError("sparse tracklet source timebase must be a positive rational")

    active: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    singletons = 0
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

        links = _unambiguous_links(active, vectors) if adjacent else {}
        next_active: list[dict[str, Any]] = []
        linked_new: set[int] = set()
        for old_index, track in enumerate(active):
            if old_index not in links:
                finish(track, "no-safe-match")
                continue
            vector_index, error = links[old_index]
            track["observations"].append(_observation(pair, pair_index, vector_index, error))
            next_active.append(track)
            linked_new.add(vector_index)
        for vector_index in range(len(vectors)):
            if vector_index in linked_new:
                continue
            track = {"id": f"tracklet-{next_id:04d}",
                     "observations": [_observation(pair, pair_index, vector_index, None)]}
            next_id += 1
            next_active.append(track)
        active = next_active

    for track in active:
        finish(track, "scan-end")
    completed.sort(key=lambda track: int(track["id"].split("-")[1]))
    return {
        "status": "candidate-only" if completed else "insufficient-continuity",
        "method": "mutual-nearest-adjacent-endpoint-v1",
        "linkTolerancePixels": LINK_TOLERANCE_PIXELS,
        "ambiguityMarginPixels": AMBIGUITY_MARGIN_PIXELS,
        "minConsecutivePairs": MIN_TRACK_PAIRS,
        "calibratedConfidence": False,
        "semanticIdentityVerified": False,
        "singlePairCandidatesDiscarded": singletons,
        "tracklets": completed,
    }
