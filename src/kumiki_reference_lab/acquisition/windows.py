"""Window planning, per-window measurement, probe summarisation, evidence assembly.

Cut-candidate summary fields
============================

Everything in :func:`cut_validity` is derived from the probe payloads alone
(``cutCandidatePts``, ``sampledWindowSummary`` and ``sampledFramePairs``), so a
report or audit can recompute the same numbers offline from a stored record.
A *cut candidate* is an ffmpeg scene-score exceedance inside a sampled window;
it is **not** an edit, and a record carrying a validity flag must not enter a
ranking.

Per-record fields:

``medianCutGapSeconds``
    Median gap between consecutive candidates in the sorted union of
    ``cutCandidatePts`` across windows, in source seconds. ``None`` when fewer
    than two candidates exist or the stream timebase is unavailable.
``medianCutGapFrames``
    The same median gap expressed in frames (the raw median gap in seconds
    multiplied by fps, rounded to 6 decimals) when an fps is available;
    otherwise ``None``.
``minCutGapSeconds``
    Smallest gap in the sorted union, in source seconds (``None`` under the same
    conditions as ``medianCutGapSeconds``).
``cutCandidateCount``
    Size of the sorted union of ``cutCandidatePts`` across all windows
    (duplicates removed). This is deliberately independent of the older
    ``cutCandidates`` sum, which trusts each window's stored count.
``burstFraction``
    Fraction of candidates whose nearest neighbour is closer than 0.25 s.
    ``None`` when fewer than two candidates exist or gaps cannot be converted
    to seconds. A high value is a strobe/flash indicator, not an edit rate.
``withinShotPairs``
    Sum of each window's ``sampledWindowSummary.withinShotComparedPairs``.
``cutSeparatedPairs``
    Sum of each window's ``sampledWindowSummary.cutSeparatedPairs``.
``deltaBasisPairs``
    Number of ``sampledFramePairs`` entries that actually carry a finite
    ``meanAbsoluteDisplayRgbDeltaPerSecond``. This is the real support for
    ``meanWithinShotRgbDeltaPerSecond`` and can differ from ``withinShotPairs``.
``cutsPerMinuteCi95``
    ``[low, high]`` Poisson 95% interval on the candidate count per sampled
    minute. The count interval is the exact Garwood interval
    (``P(X <= n-1 | low) = 0.975`` and ``P(X <= n | high) = 0.025``). When at
    least three windows exist and the mean window count is positive, each
    half-width is widened by ``sqrt(designEffect)`` where ``designEffect =
    max(1.0, sampleVariance(windowCounts) / mean(windowCounts))``. With zero
    candidates the interval is ``[0, 3.689 / sampledMinutes]``; when sampled
    minutes are unavailable it is ``None``.
``validityFlags``
    Sorted list (possibly empty) drawn from:

    - ``non-edit-scene-change``: ``medianCutGapFrames < 3`` or
      ``medianCutGapSeconds < 0.10``.
    - ``burst-heavy``: ``burstFraction > 0.5``.
    - ``sparse-delta-basis``: ``deltaBasisPairs < 8``.
    - ``no-delta-basis``: ``deltaBasisPairs == 0``.
    - ``low-coverage``: supplied sampled fraction < 0.25.
    - ``short-sample``: ``sampled_seconds < 20``.
    - ``no-cuts-observed``: ``cutCandidateCount == 0``.

Existing summary keys are never removed or renamed; the fields above are
additive.
"""

from __future__ import annotations

import math
import statistics
from pathlib import Path
from typing import Any, Callable, Iterable

from kumiki_reference_lab.analyzers.appearance.source_visual_probe import (
    analyze_source_visual_window,
)

from .probe import ANALYZER_RIGHTS_STATUS, as_int, finite_float
from .store import utc_now

MAX_WINDOWS = 20
MAX_WINDOW_SECONDS = 30
# Coverage deliberately stops short of the trailing decile of the runtime.
_TRAILING_DECILE = 0.9
_MAX_USABLE_SECONDS = 3600.0

# Cut-candidate classification budgets (see the module docstring).
_BURST_NEIGHBOUR_SECONDS = 0.25
_NON_EDIT_MEDIAN_FRAMES = 3.0
_NON_EDIT_MEDIAN_SECONDS = 0.10
_SPARSE_DELTA_BASIS_PAIRS = 8
_LOW_COVERAGE_FRACTION = 0.25
_SHORT_SAMPLE_SECONDS = 20.0
_ZERO_CANDIDATE_UPPER_95 = 3.689


def _rational_float(value: object) -> float | None:
    """Convert a rational dict/tuple or positive number to a finite float."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, dict):
        numerator = finite_float(value.get("numerator"))
        denominator = finite_float(value.get("denominator"))
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        numerator = finite_float(value[0])
        denominator = finite_float(value[1])
    elif isinstance(value, (int, float)):
        number = finite_float(value)
        return number if number is not None and number > 0 else None
    else:
        return None
    if numerator is None or denominator is None or denominator == 0:
        return None
    result = numerator / denominator
    return result if math.isfinite(result) and result > 0 else None


def _probe_tick_seconds(probes: list[dict[str, Any]]) -> float | None:
    """Read the first usable source timebase (seconds per PTS tick)."""
    for probe in probes:
        tick_seconds = _rational_float(probe.get("sourceTimebase"))
        if tick_seconds is not None:
            return tick_seconds
    return None


def _poisson_cdf(count: int, rate: float) -> float:
    """Return ``P(X <= count)`` for ``X ~ Poisson(rate)`` without scipy."""
    if count < 0:
        return 0.0
    if rate <= 0:
        return 1.0
    terms = [-rate + index * math.log(rate) - math.lgamma(index + 1)
             for index in range(count + 1)]
    peak = max(terms)
    return math.exp(peak) * math.fsum(
        math.exp(term - peak) for term in terms)


def _solve_poisson_cdf(count: int, target: float) -> float:
    """Solve ``P(X <= count | rate) == target`` for a decreasing CDF."""
    low, high = 0.0, 1.0
    while _poisson_cdf(count, high) >= target:
        high *= 2.0
    for _ in range(200):
        middle = (low + high) / 2.0
        if _poisson_cdf(count, middle) >= target:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _poisson_count_interval(count: int) -> tuple[float, float]:
    """Exact Garwood 95% interval for a Poisson count."""
    lower = _solve_poisson_cdf(count - 1, 0.975)
    upper = _solve_poisson_cdf(count, 0.025)
    return lower, upper


def _design_effect(window_counts: list[int]) -> float:
    """Between-window variance inflation, available with three windows."""
    if len(window_counts) < 3:
        return 1.0
    mean_count = statistics.mean(window_counts)
    if mean_count <= 0:
        return 1.0
    return max(1.0, statistics.variance(window_counts) / mean_count)


def cut_validity(
    probes: Iterable[dict[str, Any]], *, sampled_seconds: float,
    fps: object = None, timebase: object = None,
    sampled_fraction: float | None = None,
) -> dict[str, Any]:
    """Derive cut-candidate gap, burst, pair, interval and flag fields.

    Pure function of the probe payloads: the same stored probes, sampled
    seconds, fps/timebase and sampled fraction always produce the same dict.
    ``fps`` accepts a number or a ``{"numerator", "denominator"}`` rational;
    ``timebase`` accepts either a seconds-per-tick number or the rational dict
    used by the probes. Passing ``None`` lets the first embedded
    ``sourceTimebase`` supply the tick length.
    """
    probe_list = [probe for probe in probes if isinstance(probe, dict)]
    tick_seconds = (
        _rational_float(timebase) if timebase is not None
        else _probe_tick_seconds(probe_list))
    frames_per_second = _rational_float(fps) if fps is not None else None

    candidates: set[int] = set()
    window_counts: list[int] = []
    within_shot_pairs = 0
    cut_separated_pairs = 0
    delta_basis_pairs = 0
    for probe in probe_list:
        summary = probe.get("sampledWindowSummary")
        summary = summary if isinstance(summary, dict) else {}
        points = probe.get("cutCandidatePts")
        if isinstance(points, list):
            values = [value for value in (as_int(point) for point in points)
                      if value is not None]
            candidates.update(values)
            window_counts.append(len(values))
        else:
            count = as_int(
                summary.get("cutCandidateCountBetweenFirstAndLastSample"))
            window_counts.append(count if count is not None else 0)

        within = as_int(summary.get("withinShotComparedPairs"))
        separated = as_int(summary.get("cutSeparatedPairs"))
        pairs = probe.get("sampledFramePairs")
        pairs = pairs if isinstance(pairs, list) else []
        probe_delta_pairs = 0
        probe_separated_pairs = 0
        for pair in pairs:
            if not isinstance(pair, dict):
                continue
            if finite_float(
                    pair.get("meanAbsoluteDisplayRgbDeltaPerSecond")) is not None:
                probe_delta_pairs += 1
            else:
                probe_separated_pairs += 1
        delta_basis_pairs += probe_delta_pairs
        within_shot_pairs += (
            within if within is not None else probe_delta_pairs)
        cut_separated_pairs += (
            separated if separated is not None else probe_separated_pairs)

    ordered = sorted(candidates)
    cut_candidate_count = len(ordered)
    gaps_seconds: list[float] | None = None
    if len(ordered) >= 2 and tick_seconds is not None:
        gaps_seconds = [(later - earlier) * tick_seconds
                        for earlier, later in zip(ordered, ordered[1:])]

    median_gap_seconds = None
    median_gap_frames = None
    min_gap_seconds = None
    burst_fraction = None
    if gaps_seconds:
        median_gap = statistics.median(gaps_seconds)
        median_gap_seconds = round(median_gap, 6)
        if frames_per_second is not None:
            median_gap_frames = round(median_gap * frames_per_second, 6)
        min_gap_seconds = round(min(gaps_seconds), 6)
        burst_count = 0
        for index in range(cut_candidate_count):
            nearest = min(
                gaps_seconds[index - 1] if index > 0 else math.inf,
                gaps_seconds[index] if index < len(gaps_seconds) else math.inf,
            )
            if nearest < _BURST_NEIGHBOUR_SECONDS:
                burst_count += 1
        burst_fraction = round(burst_count / cut_candidate_count, 6)

    sampled_minutes = None
    sampled = finite_float(sampled_seconds)
    if sampled is not None and sampled > 0:
        sampled_minutes = sampled / 60.0
    interval = None
    if sampled_minutes is not None:
        if cut_candidate_count == 0:
            interval = [0.0, round(
                _ZERO_CANDIDATE_UPPER_95 / sampled_minutes, 6)]
        else:
            lower, upper = _poisson_count_interval(cut_candidate_count)
            design_effect = _design_effect(window_counts)
            root = math.sqrt(design_effect)
            widened_low = max(
                0.0, cut_candidate_count - root * (
                    cut_candidate_count - lower))
            widened_high = cut_candidate_count + root * (
                upper - cut_candidate_count)
            interval = [
                round(widened_low / sampled_minutes, 6),
                round(widened_high / sampled_minutes, 6),
            ]

    flags: list[str] = []
    if ((median_gap_frames is not None
         and median_gap_frames < _NON_EDIT_MEDIAN_FRAMES)
            or (median_gap_seconds is not None
                and median_gap_seconds < _NON_EDIT_MEDIAN_SECONDS)):
        flags.append("non-edit-scene-change")
    if burst_fraction is not None and burst_fraction > 0.5:
        flags.append("burst-heavy")
    if delta_basis_pairs < _SPARSE_DELTA_BASIS_PAIRS:
        flags.append("sparse-delta-basis")
    if delta_basis_pairs == 0:
        flags.append("no-delta-basis")
    sampled_fraction_value = finite_float(sampled_fraction)
    if (sampled_fraction_value is not None
            and sampled_fraction_value < _LOW_COVERAGE_FRACTION):
        flags.append("low-coverage")
    if sampled is not None and sampled < _SHORT_SAMPLE_SECONDS:
        flags.append("short-sample")
    if cut_candidate_count == 0:
        flags.append("no-cuts-observed")

    return {
        "medianCutGapSeconds": median_gap_seconds,
        "medianCutGapFrames": median_gap_frames,
        "minCutGapSeconds": min_gap_seconds,
        "cutCandidateCount": cut_candidate_count,
        "burstFraction": burst_fraction,
        "withinShotPairs": within_shot_pairs,
        "cutSeparatedPairs": cut_separated_pairs,
        "deltaBasisPairs": delta_basis_pairs,
        "cutsPerMinuteCi95": interval,
        "validityFlags": sorted(flags),
    }


def plan_windows(
    duration_seconds: float, *, count: int, seconds: int,
) -> tuple[int, int, list[int], float]:
    """Plan evenly spread non-overlapping windows, skipping the trailing 10%.

    The first window always starts at 0. Returns ``(window seconds, count,
    starts, sampled fraction of runtime)``.
    """
    if (type(count) is not int or not 1 <= count <= MAX_WINDOWS
            or type(seconds) is not int or not 1 <= seconds <= MAX_WINDOW_SECONDS):
        raise ValueError("window duration/count budgets are out of bounds")
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("source reported invalid/nonpositive duration")
    usable_end = min(duration_seconds * _TRAILING_DECILE, _MAX_USABLE_SECONDS)
    span = min(seconds, int(usable_end))
    if span < 1:
        raise ValueError("source is too short for a measurable window")
    window_count = min(count, max(1, int(usable_end) // span))
    stride = (0 if window_count == 1
              else int((usable_end - span) // (window_count - 1)))
    if window_count > 1 and stride < span:
        raise ValueError("computed media windows would overlap")
    starts = [index * stride for index in range(window_count)]
    if starts and starts[0] != 0:
        raise ValueError("first measurement window must start at zero")
    sampled = span * window_count
    return span, window_count, starts, round(
        min(1.0, sampled / duration_seconds), 6)


def summarize_probes(
    probes: Iterable[dict[str, Any]], *, sampled_seconds: float,
    fps: object = None, timebase: object = None,
    sampled_fraction: float | None = None,
) -> dict[str, Any]:
    """Derive record summary numbers strictly from embedded probe payloads.

    The cut-candidate validity fields come from :func:`cut_validity`, so the
    same numbers can be recomputed from stored ``cutCandidatePts``. ``fps`` and
    ``timebase`` are optional and only affect frame-denominated gaps; a missing
    timebase falls back to the probes' own ``sourceTimebase``.
    """
    probe_list = [probe for probe in probes if isinstance(probe, dict)]
    cuts = 0
    windows_with_cuts = 0
    sampled_frames = 0
    luma: list[float] = []
    saturation: list[float] = []
    deltas_per_second: list[float] = []
    for probe in probe_list:
        summary = probe.get("sampledWindowSummary")
        if isinstance(summary, dict):
            cut_count = as_int(
                summary.get("cutCandidateCountBetweenFirstAndLastSample"))
            if cut_count is not None:
                cuts += cut_count
                windows_with_cuts += int(cut_count > 0)
            luma_value = finite_float(summary.get("meanSampledDisplayLumaProxy"))
            if luma_value is not None:
                luma.append(luma_value)
            saturation_value = finite_float(
                summary.get("meanSampledSaturationProxy"))
            if saturation_value is not None:
                saturation.append(saturation_value)
        frames = probe.get("sampledFrames")
        if isinstance(frames, list):
            sampled_frames += len(frames)
        pairs = probe.get("sampledFramePairs")
        if isinstance(pairs, list):
            for pair in pairs:
                if not isinstance(pair, dict):
                    continue
                value = finite_float(
                    pair.get("meanAbsoluteDisplayRgbDeltaPerSecond"))
                if value is not None:
                    deltas_per_second.append(value)
    rate = (round(cuts * 60.0 / sampled_seconds, 6)
            if sampled_seconds > 0 else None)
    result = {
        "cutCandidates": cuts,
        "cutCandidateRatePerMinute": rate,
        "meanDisplayLuma": round(statistics.mean(luma), 6) if luma else None,
        "meanSaturation": (round(statistics.mean(saturation), 6)
                           if saturation else None),
        "meanWithinShotRgbDeltaPerSecond": (
            round(statistics.mean(deltas_per_second), 6)
            if deltas_per_second else None),
        "sampledFrames": sampled_frames,
        "windowsWithCuts": windows_with_cuts,
    }
    result.update(cut_validity(
        probe_list, sampled_seconds=sampled_seconds, fps=fps,
        timebase=timebase, sampled_fraction=sampled_fraction))
    return result


def measure_windows(
    source: Path, *, duration_seconds: float, window_count: int,
    window_seconds: int, image_translation: bool,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = ANALYZER_RIGHTS_STATUS,
    max_samples: int = 12, frame_width: int = 160, frame_height: int = 90,
    analyze: Callable[..., dict[str, Any]] = analyze_source_visual_window,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Measure evenly spread source-PTS windows; return ``(coverage, windows)``.

    ``analyze`` is injectable so an offline caller can substitute the source
    visual probe without touching ffmpeg.
    """
    span, count, starts, fraction = plan_windows(
        duration_seconds, count=window_count, seconds=window_seconds)
    windows: list[dict[str, Any]] = []
    for start in starts:
        probe = analyze(
            source, start_seconds=start, seconds=span, max_samples=max_samples,
            width=frame_width, height=frame_height,
            image_translation=image_translation,
            rights_status=rights_status, ffmpeg=ffmpeg, ffprobe=ffprobe,
        )
        windows.append({
            "startSeconds": start,
            "endSeconds": start + span,
            "probe": probe,
        })
    coverage = {
        "windowsMeasured": count,
        "windowSeconds": span,
        "sampledSeconds": span * count,
        "fractionOfRuntime": fraction,
        "fullRuntimeMeasured": False,
        "note": "evenly spread source-PTS windows, not full-film review",
    }
    return coverage, windows


def _source_frame_rate(source: object) -> object:
    """Pick the first usable frame-rate field an adapter attached to a source."""
    if not isinstance(source, dict):
        return None
    for key in ("frameRate", "framesPerSecond", "nominalFrameRate"):
        value = source.get(key)
        if value is not None:
            return value
    return None


def build_video_evidence(
    *, source: dict[str, Any], coverage: dict[str, Any],
    windows: list[dict[str, Any]], method: str, provider: str,
    video_url: str | None, rights_basis: str, rights_note: str,
    schema_version: str, evidence_status: str, limits: Iterable[str],
    generated_at: str | None = None, rights_status: str = "review-required",
) -> dict[str, Any]:
    """Assemble the neutral video evidence payload (no subject identity fields).

    The caller merges its own subject fields (catalog identity, URLs, scores)
    around this payload and supplies the schema, evidence-status string, and
    limits list. Media is never retained: ``mediaRetained`` is fixed ``False``
    so a caller cannot accidentally claim otherwise.
    """
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError("evidence schema version must be a non-empty string")
    if not isinstance(evidence_status, str) or not evidence_status.strip():
        raise ValueError("evidence status must be a non-empty string")
    if not isinstance(method, str) or not method.strip():
        raise ValueError("acquisition method must be a non-empty string")
    if not isinstance(provider, str) or not provider.strip():
        raise ValueError("acquisition provider must be a non-empty string")
    if not isinstance(rights_basis, str) or not rights_basis.strip():
        raise ValueError("rights basis must be a non-empty string")
    if not isinstance(rights_note, str) or not rights_note.strip():
        raise ValueError("rights note must be a non-empty string")
    if not isinstance(coverage.get("sampledSeconds"), (int, float)):
        raise ValueError("coverage must report sampled seconds")
    summary = summarize_probes(
        [window["probe"] for window in windows],
        sampled_seconds=float(coverage["sampledSeconds"]),
        fps=_source_frame_rate(source),
        timebase=source.get("sourceTimebase") if isinstance(source, dict) else None,
        sampled_fraction=finite_float(coverage.get("fractionOfRuntime")),
    )
    return {
        "schemaVersion": schema_version,
        "source": source,
        "acquisition": {
            "provider": provider,
            "videoUrl": video_url,
            "method": method,
            "mediaRetained": False,
            "attestation": {
                "rightsBasis": rights_basis,
                "note": rights_note,
            },
        },
        "coverage": coverage,
        "windows": windows,
        "summary": summary,
        "evidenceStatus": evidence_status,
        "rightsStatus": rights_status,
        "limits": list(limits),
        "generatedAt": generated_at or utc_now(),
    }
