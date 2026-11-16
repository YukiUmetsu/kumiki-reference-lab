"""Editorial measurements derived from a stored full-runtime census record.

Everything in this module is a pure function of one census scan dictionary: it
performs no I/O, decodes no media and knows nothing about any website. A caller
can therefore recompute every number here from the committed JSON, and two runs
over the same record are byte-identical.

Vocabulary that matters
-----------------------
``shot``
    A shot here is the interval between consecutive *detected scene changes*
    (``cutPts``), plus the opening interval from 0 to the first candidate and
    the closing interval from the last candidate to the duration. A shot is
    therefore a lower bound on the number of edits in the file, not a shot
    list: undetected cuts merge two shots, and a flash, a fast pan or a
    dissolve can add a candidate that is not an edit. ``shotCount`` is always
    ``len(cutPts) + 1`` for a well-formed record, including single-shot films
    (zero candidates, one shot).
``pace third``
    The runtime split into three equal spans. A cut belongs to the third that
    contains its timestamp; pace is candidates per minute within that span.
``flicker``
    ``flickerLumaPerSecond`` is the median absolute second-to-second change in
    mean display-luma across the fixed-cadence series. The series is sampled at
    roughly 1 Hz, so a real flicker above ~1 Hz is aliased: this number
    measures sample-to-sample instability, **not** a flicker frequency, and it
    must not be read as one. ``flickerP90`` is the corresponding high quantile.
``appearance slope``
    A least-squares line fit to a metric against time in minutes. The slope is
    reported with ``r2``; when ``r2`` is low the slope is a weak description
    and should not be cited as a trend.

Nothing here claims editorial intent, transition typing, music sync or a
verified edit list. :data:`EDITORIAL_LIMITS` spells out the omissions and is
copied into every block.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Mapping

__all__ = [
    "EDITORIAL_LIMITS",
    "FLICKER_OUTLIER_PER_SECOND",
    "STATIC_RGB_DELTA",
    "derive_editorial",
]

#: Last third ÷ first third at or above this is ``accelerating``.
PACE_BAND = 0.15
#: Consecutive samples whose mean absolute RGB delta is below this are static.
STATIC_RGB_DELTA = 0.01
#: A clip above this per-second luma delta is listed as a flicker outlier.
FLICKER_OUTLIER_PER_SECOND = 0.05
#: A drift ratio at or above this is a "last third more than 2× first" clip.
ACCELERATION_RATIO = 2.0
#: A drift ratio at or below this is a "last third under half the first" clip.
DECELERATION_RATIO = 0.5

EDITORIAL_LIMITS = [
    "No shot list: a shot is the interval between consecutive detected scene "
    "changes, a lower bound on edits; undetected cuts merge shots and false "
    "candidates split them.",
    "No transition typing: fades, wipes, dissolves, flashes and hard cuts are "
    "all the same candidate event here.",
    "No editorial intent: these numbers describe timing and appearance "
    "proxies, never meaning, style, quality or authorship.",
    "No music sync: audio is not measured, so no cut is aligned to a beat, "
    "bar or hit.",
    "No verified edits: cut candidates are ffmpeg scene-score exceedances; "
    "fast movement, flashes, transitions and compression can exceed the "
    "threshold.",
    "No flicker frequency: the 1 Hz appearance series aliases content above "
    "~1 Hz, so flickerLumaPerSecond is sample instability, not a frequency.",
    "No colour science: appearance values are display-RGB proxies at the "
    "census decode size, not scene-linear light or calibrated colour.",
]


def _number(value: object) -> float | None:
    """Finite float or ``None``; booleans and non-numeric objects are rejected."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _round(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(float(value), digits)


def _percentile(values: list[float], quantile: float) -> float | None:
    """Linear-interpolated percentile over an already sorted list."""
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * quantile
    lower = math.floor(position)
    upper = min(len(values) - 1, lower + 1)
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _unwrap_scan(census_scan: object) -> tuple[Mapping[str, Any], bool]:
    """Accept a bare scan block or a whole census evidence record."""
    if not isinstance(census_scan, Mapping):
        return {}, False
    if "durationSeconds" in census_scan or "cutPts" in census_scan:
        return census_scan, True
    for key in ("census", "scan"):
        inner = census_scan.get(key)
        if isinstance(inner, Mapping):
            return inner, True
    return census_scan, True


def _timebase_seconds(scan: Mapping[str, Any]) -> float | None:
    """Seconds per source PTS, from the timebase and then the frame rate."""
    for key, is_fps in (("timebase", False), ("fps", True)):
        rational = scan.get(key)
        if isinstance(rational, Mapping):
            numerator = _number(rational.get("numerator"))
            denominator = _number(rational.get("denominator"))
            if (numerator is not None and denominator is not None
                    and numerator > 0 and denominator > 0):
                value = (denominator / numerator if is_fps
                         else numerator / denominator)
                if math.isfinite(value) and value > 0:
                    return value
    fps = _number(scan.get("fps"))
    if fps is not None and fps > 0:
        return 1.0 / fps
    return None


def _cut_points(scan: Mapping[str, Any]) -> tuple[list[int] | None, int]:
    """Unique source PTS integers, or ``None`` when the field is unusable."""
    raw = scan.get("cutPts")
    if not isinstance(raw, (list, tuple)):
        return None, 0
    points: list[int] = []
    malformed = 0
    for value in raw:
        if isinstance(value, bool):
            malformed += 1
            continue
        if isinstance(value, int):
            points.append(value)
            continue
        number = _number(value)
        if number is not None and number.is_integer():
            points.append(int(number))
        else:
            malformed += 1
    return sorted(set(points)), malformed


def _series_rows(
    scan: Mapping[str, Any], timebase: float | None, degraded: list[str],
) -> tuple[list[Mapping[str, Any]], list[float | None]]:
    """Return stored series rows and one timestamp per row where derivable."""
    raw = scan.get("series")
    if not isinstance(raw, (list, tuple)):
        degraded.append("series-missing")
        return [], []
    rows = [row for row in raw if isinstance(row, Mapping)]
    if len(rows) != len(raw):
        degraded.append("series-rows-not-objects")
    times: list[float | None] = []
    fallback = False
    for index, row in enumerate(rows):
        seconds = _number(row.get("sourceSeconds"))
        if seconds is None:
            pts = _number(row.get("sourcePts"))
            if pts is not None and timebase is not None:
                seconds = pts * timebase
        if seconds is None:
            seconds = float(index)
            fallback = True
        times.append(seconds)
    if fallback:
        degraded.append("series-time-fallback-to-index")
    return rows, times


def _pairs(
    rows: list[Mapping[str, Any]], times: list[float | None], key: str,
) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for row, seconds in zip(rows, times):
        value = _number(row.get(key))
        if value is not None and seconds is not None:
            pairs.append((seconds, value))
    pairs.sort(key=lambda item: item[0])
    return pairs


def _ols(pairs: list[tuple[float, float]]) -> tuple[float | None, float | None]:
    """Least-squares slope and coefficient of determination, x in minutes."""
    points = [(seconds / 60.0, value) for seconds, value in pairs]
    count = len(points)
    if count < 2:
        return None, None
    mean_x = sum(x for x, _ in points) / count
    mean_y = sum(y for _, y in points) / count
    sxx = sum((x - mean_x) ** 2 for x, _ in points)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in points)
    if sxx <= 0:
        return None, None
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    ss_tot = sum((y - mean_y) ** 2 for _, y in points)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in points)
    r2 = None if ss_tot <= 0 else 1.0 - ss_res / ss_tot
    return slope, r2


def _rgb_delta(earlier: object, later: object) -> float | None:
    """Mean absolute component delta between two three-component RGB rows."""
    if (not isinstance(earlier, (list, tuple))
            or not isinstance(later, (list, tuple))
            or len(earlier) < 3 or len(later) < 3):
        return None
    deltas: list[float] = []
    for left, right in zip(earlier[:3], later[:3]):
        first = _number(left)
        second = _number(right)
        if first is None or second is None:
            return None
        deltas.append(abs(second - first))
    return sum(deltas) / len(deltas)


def _shot_block(
    cut_seconds: list[float] | None, cut_count: int | None,
    duration: float | None,
) -> dict[str, Any]:
    """Shot-length statistics from candidate timestamps and runtime."""
    block: dict[str, Any] = {
        "shotCount": (None if cut_count is None else cut_count + 1),
        "medianShotSeconds": None,
        "p10ShotSeconds": None,
        "p90ShotSeconds": None,
        "meanShotSeconds": None,
        "longestShotSeconds": None,
        "longestShotStartSeconds": None,
        "shotsUnderHalfSecond": None,
        "shotsUnderOneSecond": None,
        "shotsUnderHalfSecondFraction": None,
        "shotsUnderOneSecondFraction": None,
    }
    if duration is None or cut_seconds is None:
        return block

    boundaries = [0.0, *cut_seconds, duration]
    gaps = [later - earlier for earlier, later in
            zip(boundaries, boundaries[1:])]
    if not gaps:
        return block
    ordered = sorted(gaps)
    total = len(gaps)
    half = sum(1 for gap in gaps if gap < 0.5)
    one = sum(1 for gap in gaps if gap < 1.0)
    longest = max(gaps)
    longest_index = gaps.index(longest)
    block.update({
        "shotCount": total,
        "medianShotSeconds": _round(statistics.median(gaps)),
        "p10ShotSeconds": _round(_percentile(ordered, 0.10)),
        "p90ShotSeconds": _round(_percentile(ordered, 0.90)),
        "meanShotSeconds": _round(sum(gaps) / total),
        "longestShotSeconds": _round(longest),
        "longestShotStartSeconds": _round(boundaries[longest_index]),
        "shotsUnderHalfSecond": half,
        "shotsUnderOneSecond": one,
        "shotsUnderHalfSecondFraction": _round(half / total),
        "shotsUnderOneSecondFraction": _round(one / total),
    })
    return block


def _pace_block(
    cut_seconds: list[float] | None, duration: float | None,
) -> dict[str, Any]:
    """Per-third candidate rates, drift ratio, trend and median shot length."""
    block: dict[str, Any] = {
        "paceFirstThird": None,
        "paceMiddleThird": None,
        "paceLastThird": None,
        "paceDriftRatio": None,
        "paceTrend": None,
        "medianShotSecondsFirstThird": None,
        "medianShotSecondsLastThird": None,
    }
    if duration is None or duration <= 0 or cut_seconds is None:
        return block
    third = duration / 3.0
    counts = [0, 0, 0]
    for seconds in cut_seconds:
        index = 0 if seconds < third else (1 if seconds < 2 * third else 2)
        counts[index] += 1
    rates = [count / third * 60.0 for count in counts]
    block.update({
        "paceFirstThird": _round(rates[0]),
        "paceMiddleThird": _round(rates[1]),
        "paceLastThird": _round(rates[2]),
    })
    first, last = rates[0], rates[2]
    ratio = (last / first) if first > 0 else None
    block["paceDriftRatio"] = _round(ratio)
    if ratio is not None:
        if ratio >= 1.0 + PACE_BAND:
            block["paceTrend"] = "accelerating"
        elif ratio <= 1.0 - PACE_BAND:
            block["paceTrend"] = "decelerating"
        else:
            block["paceTrend"] = "steady"

    boundaries = [0.0, *cut_seconds, duration]
    first_gaps: list[float] = []
    last_gaps: list[float] = []
    for start, later in zip(boundaries, boundaries[1:]):
        gap = later - start
        if start < third:
            first_gaps.append(gap)
        if start >= 2 * third:
            last_gaps.append(gap)
    if first_gaps:
        block["medianShotSecondsFirstThird"] = _round(
            statistics.median(first_gaps))
    if last_gaps:
        block["medianShotSecondsLastThird"] = _round(
            statistics.median(last_gaps))
    return block


def _appearance_block(
    rows: list[Mapping[str, Any]], times: list[float | None],
    degraded: list[str],
) -> dict[str, Any]:
    """Least-squares drift, ranges and dispersion over the stored series."""
    luma_pairs = _pairs(rows, times, "meanDisplayLumaProxy")
    saturation_pairs = _pairs(rows, times, "meanSaturationProxy")
    luma_slope, luma_r2 = _ols(luma_pairs)
    saturation_slope, saturation_r2 = _ols(saturation_pairs)
    luma_values = [value for _, value in luma_pairs]
    saturation_values = [value for _, value in saturation_pairs]
    if len(rows) >= 2 and (
            len(luma_pairs) < 2 or len(saturation_pairs) < 2):
        degraded.append("series-metric-values-missing")
    return {
        "lumaSlopePerMinute": _round(luma_slope),
        "lumaSlopeR2": _round(luma_r2),
        "saturationSlopePerMinute": _round(saturation_slope),
        "saturationSlopeR2": _round(saturation_r2),
        "lumaRange": (_round(max(luma_values) - min(luma_values))
                      if luma_values else None),
        "saturationRange": (
            _round(max(saturation_values) - min(saturation_values))
            if saturation_values else None),
        "lumaStdDevAcrossSeries": (
            _round(statistics.pstdev(luma_values))
            if luma_values else None),
    }


def _instability_block(
    rows: list[Mapping[str, Any]], times: list[float | None],
) -> dict[str, Any]:
    """Second-to-second luma instability and static-pair fraction."""
    deltas: list[float] = []
    rgb_pairs = 0
    static_pairs = 0
    for index in range(len(rows) - 1):
        earlier_time, later_time = times[index], times[index + 1]
        if earlier_time is not None and later_time is not None:
            interval = later_time - earlier_time
            earlier = _number(rows[index].get("meanDisplayLumaProxy"))
            later = _number(rows[index + 1].get("meanDisplayLumaProxy"))
            if interval > 0 and earlier is not None and later is not None:
                deltas.append(abs(later - earlier) / interval)
        delta = _rgb_delta(rows[index].get("meanRgb"),
                           rows[index + 1].get("meanRgb"))
        if delta is not None:
            rgb_pairs += 1
            if delta < STATIC_RGB_DELTA:
                static_pairs += 1
    ordered = sorted(deltas)
    return {
        "flickerLumaPerSecond": (
            _round(statistics.median(deltas)) if deltas else None),
        "flickerP90": _round(_percentile(ordered, 0.90)),
        "staticFraction": (_round(static_pairs / rgb_pairs)
                           if rgb_pairs else None),
    }


def derive_editorial(census_scan: dict) -> dict:
    """Return the editorial block for one stored census scan.

    ``census_scan`` is the ``census`` (or legacy ``scan``) block of a stored
    evidence record; a whole record is accepted and unwrapped. No field is ever
    invented: a value that cannot be computed is ``None`` and the reason is
    listed in ``degraded``. The function does not raise on malformed input.

    The returned shot count is a *lower bound on edits*: it counts intervals
    between detected scene changes, not verified shots or cuts.
    """
    degraded: list[str] = []
    scan, ok = _unwrap_scan(census_scan)
    if not ok:
        degraded.append("scan-not-an-object")
    elif not scan:
        degraded.append("scan-empty")

    duration = _number(scan.get("durationSeconds"))
    if duration is None or duration <= 0:
        duration = None
        degraded.append("duration-missing-or-invalid")

    timebase = _timebase_seconds(scan)
    if timebase is None:
        degraded.append("timebase-missing-or-invalid")

    points, malformed = _cut_points(scan)
    if points is None:
        degraded.append("cut-pts-missing")
        cut_count: int | None = None
        cut_seconds: list[float] | None = None
    else:
        cut_count = len(points)
        if malformed:
            degraded.append(f"cut-pts-malformed={malformed}")
        if timebase is None:
            cut_seconds = None
        else:
            cut_seconds = []
            outside = 0
            for point in points:
                seconds = point * timebase
                if duration is None or 0.0 <= seconds < duration:
                    cut_seconds.append(seconds)
                else:
                    outside += 1
            if outside:
                degraded.append(f"cut-outside-runtime={outside}")

    series_summary = _mapping(scan.get("seriesSummary"))
    raw_series = scan.get("series")
    if isinstance(raw_series, (list, tuple)):
        series_samples = len(raw_series)
    else:
        series_samples = 0
    rows, times = _series_rows(scan, timebase, degraded)
    if not rows:
        if series_samples == 0 and isinstance(raw_series, (list, tuple)):
            degraded.append("series-empty")
    elif len(rows) == 1:
        degraded.append("series-single-sample")
    if len(rows) != series_samples and series_samples:
        degraded.append("series-rows-not-objects")

    sampled = _number(series_summary.get("sampledSeconds"))
    if sampled is None:
        sampled = duration

    cuts_per_minute = None
    usable_cuts = (len(cut_seconds) if cut_seconds is not None else cut_count)
    if usable_cuts is not None and duration is not None:
        cuts_per_minute = usable_cuts * 60.0 / duration

    strobe = scan.get("strobe")
    strobe_flag = strobe if isinstance(strobe, bool) else None
    if strobe_flag is None:
        degraded.append("strobe-missing")

    block: dict[str, Any] = {}
    block.update(_shot_block(cut_seconds, cut_count, duration))
    block.update(_pace_block(cut_seconds, duration))
    block.update(_appearance_block(rows, times, degraded))
    block.update(_instability_block(rows, times))
    block.update({
        "strobeFlag": strobe_flag,
        "seriesSamples": series_samples,
        "sampledSeconds": _round(sampled),
        "cutsPerMinuteOfRuntime": _round(cuts_per_minute),
    })
    block["limits"] = list(EDITORIAL_LIMITS)
    block["degraded"] = list(dict.fromkeys(degraded))
    return block
