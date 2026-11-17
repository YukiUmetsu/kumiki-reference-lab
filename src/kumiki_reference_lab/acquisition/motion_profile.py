"""Measured motion and transition proxies over decoded frames.

These helpers are pure functions over RGB24 frames, so they are unit-testable
without ffmpeg. They deliberately measure only image-plane, numeric properties:

- a fixed transition vocabulary over short windows around scene candidates;
- global translation from the existing phase-correlation implementation;
- a 3x3 distribution of frame-to-frame RGB change;
- temporal volatility of high-frequency luma detail in the upper/lower thirds.

Nothing here recognises an effect, matches a template, infers a camera or rig,
identifies an animation technique, or claims transition ground truth. The
vocabulary is a measurement shorthand, not an editorial label.
"""

from __future__ import annotations

import math
import statistics
from bisect import bisect_left, bisect_right
from typing import Any, Iterable, Mapping, Sequence

MOTION_PROFILE_SCHEMA = "kumiki.motion-profile.v1"

TRANSITION_CLASSES = (
    "hard-cut",
    "short-dissolve",
    "long-dissolve",
    "fade-through-black",
    "fade-through-white",
    "unknown",
)
TRANSITION_WINDOW_SECONDS = 0.4
SHORT_DISSOLVE_SECONDS = 0.25
LONG_DISSOLVE_SECONDS = 0.8
FADE_BLACK_LUMA = 0.10
FADE_WHITE_LUMA = 0.90
FADE_EDGE_LUMA = 0.15

# A pair is a pan when the image-plane displacement exceeds this many pixels
# per second; it is static below the smaller threshold. Both are at the
# measured decode scale, not source pixels.
PAN_PIXELS_PER_SECOND = 1.0
STATIC_PIXELS_PER_SECOND = 0.5
OVERLAY_VOLATILITY_SATURATION = 0.02

MOTION_PROFILE_LIMITS = [
    "Transitions are classified from short downsampled frame windows; labels "
    "are measurement proxies, never transition ground truth.",
    "No effect recognition: blur, glow, grain, distortion, particles and other "
    "effects are not identified.",
    "No template detection: overlays, logos and typography are not matched "
    "against any template.",
    "No camera or rig inference: global motion is an image-plane translation "
    "hypothesis on a coarse cadence, not a camera path or rig move.",
    "No animation-technique identification: the profile does not name "
    "stop-motion, CG, cel, collage or any other technique.",
    "Scene-score candidates and luma deltas can misclassify flashes, fast "
    "movement, compression and overlapping edits.",
    "The zoom proxy is an edge-density change ratio, not a scale, focal-length "
    "or dolly estimate.",
]


def _numpy():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - numpy is a test dependency
        raise ValueError(
            "motion profile requires NumPy; install with pip install '.[motion]'"
        ) from exc
    return np


def _checked_rgb(frame: object, *, width: int, height: int) -> bytes:
    if not isinstance(frame, (bytes, bytearray, memoryview)):
        raise ValueError("every frame must be RGB24 bytes")
    body = bytes(frame)
    if len(body) != width * height * 3:
        raise ValueError("RGB frame does not match declared dimensions")
    return body


def _checked_size(width: object, height: object) -> tuple[int, int]:
    if (type(width) is not int or type(height) is not int
            or width < 2 or height < 2):
        raise ValueError("frame width/height must be integers of at least 2")
    return width, height


def _mean_luma(frame: bytes) -> float:
    """Mean display-luma proxy in 0..1; no frame shape is required."""
    np = _numpy()
    values = np.frombuffer(frame, dtype=np.uint8).reshape(-1, 3).astype(
        np.int32)
    return float((77 * values[:, 0] + 150 * values[:, 1]
                  + 29 * values[:, 2]).mean() / (256.0 * 255.0))


def _mean_rgb_delta(before: bytes, after: bytes) -> float:
    np = _numpy()
    left = np.frombuffer(before, dtype=np.uint8).astype(np.int16)
    right = np.frombuffer(after, dtype=np.uint8).astype(np.int16)
    return float(np.abs(right - left).mean() / 255.0)


def _frame_entries(
    frames: object, *, fps: float,
) -> list[tuple[float, bytes]]:
    """Normalise a frame container to sorted ``(seconds, rgb bytes)`` pairs.

    Accepted shapes: a sequence of RGB bytes, or a sequence of
    ``(seconds, bytes)`` pairs where the first value is already source
    seconds. Bytes without a time are spaced at ``1/fps`` from zero.
    """
    if fps <= 0 or not math.isfinite(fps):
        raise ValueError("fps must be positive and finite")
    if isinstance(frames, Mapping):
        raise ValueError("a per-cut mapping must be handled by the caller")
    entries: list[tuple[float, bytes]] = []
    if not isinstance(frames, Sequence) or isinstance(frames, (bytes, str)):
        raise ValueError("frames must be a sequence of frames")
    for index, item in enumerate(frames):
        if isinstance(item, (tuple, list)) and len(item) == 2:
            moment_value, body = item
            if (isinstance(moment_value, bool)
                    or not isinstance(moment_value, (int, float))):
                raise ValueError("frame time must be numeric seconds")
            moment = float(moment_value)
        else:
            body = item
            moment = index / fps
        if not isinstance(body, (bytes, bytearray, memoryview)):
            raise ValueError("every frame must be RGB24 bytes")
        entries.append((moment, bytes(body)))
    entries.sort(key=lambda pair: pair[0])
    return entries


def _normalise_windows(
    frames: object, *, cut_pts: Sequence[int], timebase: float, fps: float,
    weight: float = TRANSITION_WINDOW_SECONDS,
) -> dict[int, list[tuple[float, bytes]]]:
    """Return ``{cut pts: [(seconds, frame), ...]}`` for every cut."""
    if timebase <= 0 or not math.isfinite(timebase):
        raise ValueError("timebase must be positive and finite")
    cuts = sorted({int(value) for value in cut_pts})
    cut_seconds = [value * timebase for value in cuts]
    if isinstance(frames, Mapping):
        windows: dict[int, list[tuple[float, bytes]]] = {}
        for cut in cuts:
            raw = frames.get(cut)
            if raw is None:
                raw = frames.get(str(cut), [])
            entries: list[tuple[float, bytes]] = []
            for index, item in enumerate(raw):
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    moment_value, body = item
                    if (isinstance(moment_value, bool)
                            or not isinstance(moment_value, (int, float))):
                        raise ValueError("frame time must be numeric seconds")
                    entries.append((float(moment_value), bytes(body)))
                else:
                    centred = (index - (len(raw) - 1) / 2.0) / fps
                    entries.append((cut * timebase + centred, bytes(item)))
            entries.sort(key=lambda pair: pair[0])
            windows[cut] = entries
        return windows
    entries = _frame_entries(frames, fps=fps)
    windows = {}
    times = [moment for moment, _ in entries]
    for cut, moment in zip(cuts, cut_seconds, strict=True):
        left = bisect_left(times, moment - weight)
        right = bisect_right(times, moment + weight)
        windows[cut] = list(entries[left:right])
    return windows


def _split_deltas(
    window: Sequence[tuple[float, bytes]],
) -> tuple[list[float], list[float], list[float]]:
    """Return frame times, luma series and consecutive mean-RGB deltas."""
    times = [moment for moment, _ in window]
    lumas = [_mean_luma(frame) for _, frame in window]
    deltas = [
        _mean_rgb_delta(window[index - 1][1], window[index][1])
        for index in range(1, len(window))
    ]
    return times, lumas, deltas


def _active_span_seconds(
    deltas: Sequence[float], times: Sequence[float], *, fallback_step: float,
) -> float:
    """Width of the contiguous graded-change run around the strongest delta.

    A single spike gives one sample; a dissolve gives a run. Gaps of one
    sample are bridged so a momentarily flat blend frame does not split it.
    """
    if not deltas:
        return 0.0
    peak = max(deltas)
    if peak <= 0:
        return 0.0
    floor = max(peak * 0.30, 0.004)
    active = [value >= floor for value in deltas]
    peak_index = deltas.index(peak)
    left = peak_index
    right = peak_index
    while left > 0 and (active[left - 1]
                        or (left > 1 and active[left - 2])):
        left -= 1
    while right < len(active) - 1 and (active[right + 1]
                                       or (right + 2 < len(active)
                                           and active[right + 2])):
        right += 1
    step = fallback_step
    if len(times) > 1:
        differences = [later - earlier
                       for earlier, later in zip(times, times[1:])
                       if later > earlier]
        if differences:
            step = statistics.median(differences)
    # ``deltas[i]`` spans times[i]..times[i+1]; the run spans one extra step.
    return (right - left + 2) * step


def _classify_window(
    window: Sequence[tuple[float, bytes]], *, fps: float,
) -> tuple[str, dict[str, Any]]:
    if len(window) < 3:
        return "unknown", {"reason": "fewer-than-three-frames-in-window"}
    times, lumas, deltas = _split_deltas(window)
    peak = max(deltas) if deltas else 0.0
    minimum = min(lumas)
    maximum = max(lumas)
    detail: dict[str, Any] = {
        "frameCount": len(window),
        "peakMeanRgbDelta": round(peak, 6),
        "minLuma": round(minimum, 6),
        "maxLuma": round(maximum, 6),
    }
    if peak < 0.02:
        return "unknown", {**detail, "reason": "below-change-floor"}

    # A recovered dip/peak needs more than a single dark/bright shot: at least
    # two samples inside the extreme band, with non-extreme window edges.
    black_samples = sum(value <= FADE_BLACK_LUMA for value in lumas)
    white_samples = sum(value >= FADE_WHITE_LUMA for value in lumas)
    if (black_samples >= 2 and lumas[0] >= FADE_EDGE_LUMA
            and lumas[-1] >= FADE_EDGE_LUMA):
        return "fade-through-black", {**detail, "extremeSamples": black_samples}
    if (white_samples >= 2 and lumas[0] <= 0.85 and lumas[-1] <= 0.85):
        return "fade-through-white", {**detail, "extremeSamples": white_samples}

    span = _active_span_seconds(deltas, times, fallback_step=1.0 / fps)
    ordered = sorted(deltas, reverse=True)
    second = ordered[1] if len(ordered) > 1 else 0.0
    uniformity = second / peak if peak > 0 else 0.0
    spike_share = peak / sum(deltas) if sum(deltas) > 0 else 0.0
    detail["activeSpanSeconds"] = round(span, 6)
    detail["peakDeltaShare"] = round(spike_share, 6)
    detail["secondDeltaRatio"] = round(uniformity, 6)
    typical_step = (statistics.median(
        [later - earlier for earlier, later in zip(times, times[1:])
         if later > earlier]) if len(times) > 1 else 1.0 / fps)
    single_step = span <= max(2.5 * typical_step, 0.12)
    # A dissolve leaves at least two near-quiet deltas on one side of the
    # window. Continuous motion (a pan, a moving graphic) has no such edge and
    # must not be read as a graded transition.
    quiet_floor = max(peak * 0.20, 0.004)
    left_quiet = 0
    while left_quiet < len(deltas) and deltas[left_quiet] <= quiet_floor:
        left_quiet += 1
    right_quiet = 0
    while (right_quiet < len(deltas)
           and deltas[-(right_quiet + 1)] <= quiet_floor):
        right_quiet += 1
    quiet_run = max(left_quiet, right_quiet)
    detail["quietEdgeSamples"] = quiet_run
    luma_steps = [later - earlier for earlier, later in zip(lumas, lumas[1:])
                  if abs(later - earlier) > 0.005]
    if luma_steps:
        direction = 1.0 if sum(luma_steps) >= 0 else -1.0
        monotonicity = sum(
            1 for step in luma_steps if step * direction > 0) / len(luma_steps)
    else:
        monotonicity = 1.0
    detail["lumaMonotonicity"] = round(monotonicity, 6)
    # A dissolve is a run of comparable graded deltas. A cut is one dominant
    # spike; surrounding motion may be active but is much smaller than the peak.
    graded = (uniformity >= 0.35 and quiet_run >= 2
              and monotonicity >= 0.72 and span >= max(
                  2.5 * typical_step, SHORT_DISSOLVE_SECONDS * 0.6))
    if single_step and (spike_share >= 0.30
                        or (peak >= 2.0 * second and peak >= 0.05)):
        return "hard-cut", detail
    if graded and SHORT_DISSOLVE_SECONDS <= span < LONG_DISSOLVE_SECONDS + typical_step:
        return "long-dissolve", detail
    if graded and 0 < span < SHORT_DISSOLVE_SECONDS:
        return "short-dissolve", detail
    return "unknown", {**detail, "reason": "outside-fixed-vocabulary"}


def classify_transitions(
    frames: object, *, cut_pts: Iterable[int], timebase: float,
    fps: float | None = None, duration_seconds: float | None = None,
) -> dict[str, Any]:
    """Classify each scene candidate into the fixed transition vocabulary.

    ``frames`` may be a full RGB24 sequence, a sequence of ``(seconds, frame)``
    pairs, or a mapping from cut PTS to the small window decoded for that cut.
    A mapping is the per-cut form used by the census. Windows are sampled
    within ±0.4 s of each candidate.

    ``duration_seconds`` is the runtime used for ``transitionRatePerMinute``;
    without it the observed frame span is used.
    """
    if fps is None:
        fps = 24.0
    if fps <= 0 or not math.isfinite(fps):
        raise ValueError("fps must be positive and finite")
    cuts = sorted({int(value) for value in cut_pts})
    windows = _normalise_windows(
        frames, cut_pts=cuts, timebase=timebase, fps=fps)
    counts = {name: 0 for name in TRANSITION_CLASSES}
    rows: list[dict[str, Any]] = []
    for cut in cuts:
        transition, detail = _classify_window(windows.get(cut, []), fps=fps)
        counts[transition] += 1
        rows.append({
            "cutPts": cut,
            "sourceSeconds": round(cut * timebase, 6),
            "transitionClass": transition,
            "detail": detail,
        })
    total = len(cuts)
    shares = {
        name: round(count / total, 6) if total else 0.0
        for name, count in counts.items()
    }
    if duration_seconds is not None and duration_seconds > 0:
        rate = round(total * 60.0 / duration_seconds, 6)
    else:
        moments = [row["sourceSeconds"] for row in rows]
        span = (max(moments) - min(moments) + TRANSITION_WINDOW_SECONDS * 2
                if moments else 0.0)
        rate = round(total * 60.0 / span, 6) if span > 0 else 0.0
    classified = total - counts["unknown"]
    return {
        "counts": counts,
        "shares": shares,
        "transitionCount": total,
        "classifiedCount": classified,
        "classifiedShare": (round(classified / total, 6) if total else 0.0),
        "transitionRatePerMinute": rate,
        "cuts": rows,
        "method": (
            "per-cut ±0.4 s RGB24 window; luma fades first, then a single-frame "
            "delta spike for hard-cut, then contiguous graded-change span "
            "(<0.25 s short, 0.25-0.8 s long); thresholds fixed in this module"),
    }


def _rgb_to_gray(frame: bytes, *, width: int, height: int):
    np = _numpy()
    body = _checked_rgb(frame, width=width, height=height)
    values = np.frombuffer(body, dtype=np.uint8).reshape(
        height, width, 3).astype(np.int32)
    return ((77 * values[:, :, 0] + 150 * values[:, :, 1]
             + 29 * values[:, :, 2]) // 256).astype(np.uint8)


def _edge_density(gray) -> float:
    np = _numpy()
    vertical = np.abs(np.diff(gray.astype(np.float64), axis=0)).mean()
    horizontal = np.abs(np.diff(gray.astype(np.float64), axis=1)).mean()
    return float((vertical + horizontal) / 255.0)


def _frame_sequence(
    frames: object, *, fps: float,
) -> list[tuple[float, bytes]]:
    if isinstance(frames, Mapping):
        raise ValueError("global motion needs a frame sequence, not a mapping")
    return _frame_entries(frames, fps=fps)


def global_motion(
    frames: object, *, width: int, height: int, window_frames: int = 2,
    sample_seconds: float = 1.0,
) -> dict[str, Any]:
    """Phase-correlation translation statistics on a fixed-cadence series.

    Each consecutive pair is measured with the existing
    ``analyzers.motion.phase.measure_image_shift``. ``window_frames`` is a
    trailing smoothing window over the per-pair displacement (1 disables it).
    Statistics are pixels per second at the measured decode scale.

    The estimate is a global 2-D translation hypothesis. It cannot separate
    camera, subject and post moves, and parallax, zooms or cuts violate it.
    """
    width, height = _checked_size(width, height)
    if type(window_frames) is not int or window_frames < 1:
        raise ValueError("window_frames must be a positive integer")
    if sample_seconds <= 0 or not math.isfinite(sample_seconds):
        raise ValueError("sample_seconds must be positive and finite")
    from kumiki_reference_lab.analyzers.motion.phase import measure_image_shift

    entries = _frame_sequence(frames, fps=1.0 / sample_seconds)
    if len(entries) < 2:
        return {
            "status": "insufficient-frames",
            "pairs": 0,
            "observablePairs": 0,
            "ambiguousPairs": 0,
            "medianAbsDxPixelsPerSecond": None,
            "medianAbsDyPixelsPerSecond": None,
            "panFraction": None,
            "staticFraction": None,
            "zoomProxy": None,
            "panThresholdPixelsPerSecond": PAN_PIXELS_PER_SECOND,
            "staticThresholdPixelsPerSecond": STATIC_PIXELS_PER_SECOND,
            "zoomProxyMethod": (
                "median per-pair ratio of mean gradient-magnitude edge density "
                "(later/earlier); a proxy, never a scale estimate"),
            "method": "fft-phase-correlation-global-translation-v1",
        }
    dx_values: list[float] = []
    dy_values: list[float] = []
    raw_dx: list[float | None] = []
    raw_dy: list[float | None] = []
    ratios: list[float] = []
    ambiguous = 0
    previous_gray = _rgb_to_gray(entries[0][1], width=width, height=height)
    previous_density = _edge_density(previous_gray)
    for index in range(1, len(entries)):
        start, _ = entries[index - 1]
        end, after = entries[index]
        current_gray = _rgb_to_gray(after, width=width, height=height)
        current_density = _edge_density(current_gray)
        if previous_density > 1e-9:
            ratios.append(current_density / previous_density)
        measured = measure_image_shift(
            previous_gray.tobytes(), current_gray.tobytes(), width, height)
        dt = end - start if end > start else sample_seconds
        if measured["dxPixels"] is None:
            ambiguous += 1
            raw_dx.append(None)
            raw_dy.append(None)
        else:
            raw_dx.append(float(measured["dxPixels"]) / dt)
            raw_dy.append(float(measured["dyPixels"]) / dt)
        previous_gray = current_gray
        previous_density = current_density

    def smoothed(values: list[float | None]) -> list[float]:
        result: list[float] = []
        for index, value in enumerate(values):
            if value is None:
                continue
            recent = [item for item in values[
                max(0, index - window_frames + 1):index + 1]
                if item is not None]
            result.append(float(statistics.median(recent)) if recent else value)
        return result

    dx_values = smoothed(raw_dx)
    dy_values = smoothed(raw_dy)
    magnitudes = [math.hypot(dx, dy)
                  for dx, dy in zip(dx_values, dy_values, strict=True)]
    observable = len(magnitudes)
    return {
        "status": ("measured" if observable else "ambiguous-correlation"),
        "pairs": len(entries) - 1,
        "observablePairs": observable,
        "ambiguousPairs": ambiguous,
        "medianAbsDxPixelsPerSecond": (
            round(statistics.median([abs(value) for value in dx_values]), 6)
            if dx_values else None),
        "medianAbsDyPixelsPerSecond": (
            round(statistics.median([abs(value) for value in dy_values]), 6)
            if dy_values else None),
        "panFraction": (
            round(sum(value >= PAN_PIXELS_PER_SECOND for value in magnitudes)
                  / observable, 6) if observable else None),
        "staticFraction": (
            round(sum(value <= STATIC_PIXELS_PER_SECOND for value in magnitudes)
                  / observable, 6) if observable else None),
        "zoomProxy": (
            round(statistics.median(ratios), 6) if ratios else None),
        "panThresholdPixelsPerSecond": PAN_PIXELS_PER_SECOND,
        "staticThresholdPixelsPerSecond": STATIC_PIXELS_PER_SECOND,
        "zoomProxyMethod": (
            "median per-pair ratio of mean gradient-magnitude edge density "
            "(later/earlier); a proxy, never a scale estimate"),
        "method": "fft-phase-correlation-global-translation-v1",
    }


def local_motion_distribution(
    frames: object, *, width: int, height: int,
) -> dict[str, Any]:
    """Distribute mean frame-to-frame RGB change over a 3x3 frame grid."""
    np = _numpy()
    width, height = _checked_size(width, height)
    entries = _frame_sequence(frames, fps=1.0)
    cells = np.zeros((3, 3), dtype=np.float64)
    pairs = 0
    row_edges = np.linspace(0, height, 4, dtype=int)
    col_edges = np.linspace(0, width, 4, dtype=int)
    for index in range(1, len(entries)):
        before = _checked_rgb(entries[index - 1][1], width=width, height=height)
        after = _checked_rgb(entries[index][1], width=width, height=height)
        left = np.frombuffer(before, dtype=np.uint8).reshape(
            height, width, 3).astype(np.float64)
        right = np.frombuffer(after, dtype=np.uint8).reshape(
            height, width, 3).astype(np.float64)
        delta = np.abs(right - left).mean(axis=2) / 255.0
        for row in range(3):
            for column in range(3):
                block = delta[row_edges[row]:row_edges[row + 1],
                              col_edges[column]:col_edges[column + 1]]
                if block.size:
                    cells[row, column] += float(block.mean())
        pairs += 1
    if pairs:
        cells /= pairs
    total = float(cells.sum())
    if total > 0:
        shares = cells / total
        distribution_status = "normalized"
    else:
        shares = np.full((3, 3), 1.0 / 9.0)
        distribution_status = "no-observable-change-uniform"
    peak = float(cells.max())
    coverage = (int(np.count_nonzero(cells >= peak / 20.0)) / 9.0
                if peak > 0 else 0.0)
    flat_shares = [round(float(shares[row, column]), 6)
                   for row in range(3) for column in range(3)]
    # Rounding can leave the public list short of 1 by a few 1e-6.
    flat_shares[-1] = round(flat_shares[-1] + 1.0 - sum(flat_shares), 6)
    dominant = np.unravel_index(int(np.argmax(cells)), cells.shape)
    return {
        "status": distribution_status,
        "pairs": pairs,
        "cellMeans": [[round(float(cells[row, column]), 6)
                       for column in range(3)] for row in range(3)],
        "cellShares": flat_shares,
        "centreShare": flat_shares[4],
        "motionCoverage": round(coverage, 6),
        "dominantCell": [int(dominant[0]), int(dominant[1])],
        "motionCoverageRule": "cells at or above 1/20 of the largest cell",
        "method": "mean absolute RGB delta per 3x3 cell, normalized to sum 1",
    }


def _laplacian(gray):
    np = _numpy()
    values = gray.astype(np.float64) / 255.0
    padded = np.pad(values, 1, mode="edge")
    return np.abs(
        4 * padded[1:-1, 1:-1]
        - padded[:-2, 1:-1] - padded[2:, 1:-1]
        - padded[1:-1, :-2] - padded[1:-1, 2:]) / 4.0


def _third_activity(volatilities: list[float]) -> float:
    if not volatilities:
        return 0.0
    mean = sum(volatilities) / len(volatilities)
    return round(min(1.0, mean / OVERLAY_VOLATILITY_SATURATION), 6)


def overlay_activity(
    frames: object, *, width: int, height: int,
) -> dict[str, Any]:
    """Text/graphic-overlay proxy from temporal high-frequency luma volatility.

    The method is deliberately blunt: a 3x3 Laplacian luma high-pass is taken
    per frame, then the mean absolute frame-to-frame change of that high-pass
    is measured in the top and bottom thirds and saturated at 0.02 luma units.
    It is a volatility proxy, not text, logo or graphic detection.
    """
    width, height = _checked_size(width, height)
    entries = _frame_sequence(frames, fps=1.0)
    upper: list[float] = []
    lower: list[float] = []
    upper_end = max(1, height // 3)
    lower_start = min(height - 1, (2 * height) // 3)
    for index in range(1, len(entries)):
        before = _laplacian(_rgb_to_gray(
            entries[index - 1][1], width=width, height=height))
        after = _laplacian(_rgb_to_gray(
            entries[index][1], width=width, height=height))
        change = abs(after - before)
        upper.append(float(change[:upper_end, :].mean()))
        lower.append(float(change[lower_start:, :].mean()))
    return {
        "status": "measured" if len(entries) >= 2 else "insufficient-frames",
        "pairs": max(0, len(entries) - 1),
        "lowerThirdActivity": _third_activity(lower),
        "upperThirdActivity": _third_activity(upper),
        "saturationLumaUnits": OVERLAY_VOLATILITY_SATURATION,
        "method": (
            "mean absolute frame-to-frame change of a 3x3 Laplacian luma "
            "high-pass in each third, saturated at "
            f"{OVERLAY_VOLATILITY_SATURATION:.2f} luma units; a volatility "
            "proxy, not overlay/text detection"),
    }


def motion_signature(
    frames: object, *, width: int, height: int,
    cut_pts: Iterable[int] = (), timebase: float = 1.0,
    fps: float | None = None, sample_seconds: float = 1.0,
    duration_seconds: float | None = None,
    transition_frames: object | None = None,
    transitions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose the transition, global, local and overlay blocks.

    ``transition_frames`` is the bounded per-cut window mapping when the full
    frame sequence is not the cut-neighbourhood source. A precomputed
    ``transitions`` block may be supplied instead.
    """
    width, height = _checked_size(width, height)
    if (sample_seconds <= 0 or not math.isfinite(sample_seconds)):
        raise ValueError("sample_seconds must be positive and finite")
    if transitions is None:
        source = frames if transition_frames is None else transition_frames
        transitions = classify_transitions(
            source, cut_pts=cut_pts, timebase=timebase, fps=fps,
            duration_seconds=duration_seconds)
    entries = _frame_sequence(frames, fps=1.0 / sample_seconds)
    return {
        "schemaVersion": MOTION_PROFILE_SCHEMA,
        "transitions": dict(transitions),
        "globalMotion": global_motion(
            entries, width=width, height=height,
            sample_seconds=sample_seconds),
        "localMotion": local_motion_distribution(
            entries, width=width, height=height),
        "overlayActivity": overlay_activity(
            entries, width=width, height=height),
        "limits": list(MOTION_PROFILE_LIMITS),
    }
