"""Conservative candidate global luma ramps from sampled source appearances.

This describes an image change, not an editorial fade, exposure change or
physical light. Spatial coherence suppresses locally moving bright objects.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from kumiki_reference_lab.core.timebase import as_rational_dict

MIN_STEP_LUMA = 0.025
MIN_CELL_STEP_LUMA = 0.012
MIN_COHERENT_CELLS = 8
MIN_CONSECUTIVE_STEPS = 3
MIN_TOTAL_LUMA = 0.20
MIN_DURATION = Fraction(1, 5)
NEAR_BLACK_LUMA = 0.12


def detect_luma_ramp_candidates(
    samples: list[dict[str, Any]], changes: list[dict[str, Any]],
    *, timebase: Fraction,
) -> list[dict[str, Any]]:
    """Find multi-frame global display-referred ramps without altering cuts.

    Every candidate is anchored only at observed PTS. Sparse samples cannot
    establish the actual transition boundaries or the cause of the change.
    """
    if (not isinstance(timebase, Fraction) or timebase <= 0 or
            len(samples) != len(changes) + 1):
        raise ValueError("luma ramp detection requires aligned samples and source timebase")
    candidates: list[dict[str, Any]] = []
    run_start: int | None = None
    run_sign: int | None = None

    def finish(end_index: int) -> None:
        nonlocal run_start, run_sign
        if run_start is not None and end_index - run_start >= MIN_CONSECUTIVE_STEPS:
            first, last = samples[run_start], samples[end_index]
            first_luma = first["appearance"]["meanLumaProxy"]
            last_luma = last["appearance"]["meanLumaProxy"]
            if (abs(last_luma - first_luma) >= MIN_TOTAL_LUMA and
                    (last["sourcePts"] - first["sourcePts"]) * timebase >= MIN_DURATION):
                start_pts, end_pts = first["sourcePts"], last["sourcePts"]
                if start_pts >= end_pts:
                    raise ValueError("luma ramp samples must have increasing source PTS")
                kind = ("fade-to-black-candidate" if run_sign == -1 and
                        last_luma <= NEAR_BLACK_LUMA else
                        "fade-from-black-candidate" if run_sign == 1 and
                        first_luma <= NEAR_BLACK_LUMA else
                        "global-brightness-ramp-candidate")
                candidates.append({
                    "kind": kind,
                    "startPts": start_pts, "endPts": end_pts,
                    "durationSeconds": as_rational_dict((end_pts - start_pts) * timebase),
                    "observedSampleCount": end_index - run_start + 1,
                    "startMeanLumaProxy": first_luma,
                    "endMeanLumaProxy": last_luma,
                    "interpretationStatus": "review-required-not-verified",
                })
        run_start = None
        run_sign = None

    for i, change in enumerate(changes):
        first, last = samples[i], samples[i + 1]
        if first["sourcePts"] >= last["sourcePts"]:
            raise ValueError("luma ramp samples must have increasing source PTS")
        delta = last["appearance"]["meanLumaProxy"] - first["appearance"]["meanLumaProxy"]
        sign = 1 if delta > 0 else -1
        coherent = sum(
            1 for a, b in zip(first["appearance"]["spatialGrid3x3"],
                              last["appearance"]["spatialGrid3x3"], strict=True)
            if (b["meanLumaProxy"] - a["meanLumaProxy"]) * sign >= MIN_CELL_STEP_LUMA
        )
        qualifies = (change["status"] != "cut-boundary" and
                     abs(delta) >= MIN_STEP_LUMA and coherent >= MIN_COHERENT_CELLS)
        if not qualifies:
            finish(i)
        elif run_start is None:
            run_start, run_sign = i, sign
        elif sign != run_sign:
            finish(i)
            run_start, run_sign = i, sign
    finish(len(changes))
    return candidates
