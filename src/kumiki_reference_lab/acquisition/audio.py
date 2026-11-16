"""Audio-only census: loudness, dynamics and temporal structure.

The video census measures picture; this module measures the sound axis with
numeric evidence only. It performs no network access, writes no files of its
own, and knows nothing about any website. A caller downloads a public clip
into its own scratch directory, extracts a mono 8 kHz ``s16le`` PCM stream
(:func:`extract_audio`), runs ffmpeg's EBU R128 filter for the integrated/peak
summary (:func:`ebur128_summary`), and calls :func:`measure_audio` on the PCM.

The analysis is deliberately stdlib-only (``array``, ``math``,
``statistics``); the base package has no numpy dependency and must not gain
one. Nothing here identifies speech, music, instruments, genre, mood, mix
quality, or sync to picture. The ``limits`` list on every measurement names
what is not measured.

Onset detection
---------------

The PCM is cut into consecutive non-overlapping frames of ``window_seconds``
(20 ms by default, so 160 samples at 8 kHz). Each frame's RMS level in dBFS
forms an envelope. For frame ``i`` the rise is ``level[i] - level[i-1]``.

A frame is an onset when

1. its rise **exceeds** a local adaptive threshold: the median of the positive
   rises in the previous ~1 s (50 frames) multiplied by 1.5, with a floor of
   2 dB; and
2. the following 80 ms (4 frames) contains **no larger** rise. The look-ahead
   is clipped at the end of the clip.

The threshold is computed from prior frames only, so the detector is causal
and deterministic. It is a novelty detector for the amplitude envelope, not a
beat tracker: a perfectly steady rhythm whose every attack has the same height
produces few onsets, while a quiet noise floor between attacks lowers the
local median and makes distinct attacks visible.

Tempo is a **periodicity hypothesis** about the onset envelope, not a beat
grid, not a music-only detector. It is the peak normalized autocorrelation of
the positive-rise envelope (frame rises of at least 2 dB) over lags
corresponding to 60-200 BPM (0.3-1.0 s).
Speech, ambience and repeated sound effects can produce a false periodicity,
and the octave (half/double tempo) is inherently ambiguous: when several lags
correlate within 0.01 of the peak, the shortest (fastest) is reported.
"""

from __future__ import annotations

import math
import re
import statistics
import subprocess
import sys
from array import array
from pathlib import Path
from typing import Any, Iterable

from .runner import safe_error

AUDIO_SCHEMA = "kumiki.video-audio-census.v1"
METHOD_EBUR128 = "ffmpeg-ebur128"
METHOD_ENVELOPE = "ffmpeg-8k-envelope"

# The extracted PCM is always mono 8 kHz signed 16-bit little-endian.
PCM_SAMPLE_RATE = 8000
PCM_CHANNELS = 1
PCM_SAMPLE_WIDTH_BYTES = 2
MAX_PCM_SAMPLE_RATE = 48000

SILENCE_DBFS = -50.0
ONSET_LOOKAHEAD_SECONDS = 0.08
ONSET_THRESHOLD_MULTIPLIER = 1.5
ONSET_MINIMUM_RISE_DB = 2.0
ONSET_THRESHOLD_WINDOW_SECONDS = 1.0
ONSET_RATE_BUCKET_SECONDS = 5.0
ONSET_TREND_BAND = 0.15
MIN_REGULARITY_ONSETS = 8
TEMPO_MIN_BPM = 60.0
TEMPO_MAX_BPM = 200.0
TEMPO_TIE_TOLERANCE = 0.01

_LOUDNESS_FLOOR_LUFS = -70.0
_DBFS_FLOOR = -120.0
_SAMPLE_CEILING = 32768.0
_MAX_PCM_BYTES = 512 * 1024 * 1024
_MAX_FFMPEG_LOG_BYTES = 32 * 1024 * 1024
_MAX_TIMEOUT_SECONDS = 7200.0

AUDIO_LIMITS = [
    "No speech/music separation: one mixed audio stream is measured as a "
    "single signal.",
    "No dialogue transcription or speech recognition of any kind.",
    "No instrument, sound-source, genre or mood identification.",
    "No mix-quality, loudness-compliance or aesthetic judgement.",
    "No sync-to-picture claim: onset and loudness times are relative to the "
    "audio stream, not verified against video events.",
]

_MOMENTARY_LINE = re.compile(
    r"t:\s*(?P<seconds>[0-9]+(?:\.[0-9]+)?)\s+.*?"
    r"\bM:\s*(?P<lufs>-?(?:[0-9]+(?:\.[0-9]+)?|inf|nan))")
_INTEGRATED_LINE = re.compile(
    r"^\s*I:\s*(?P<value>-?(?:[0-9]+(?:\.[0-9]+)?|inf|nan))\s+LUFS",
    re.MULTILINE)
_RANGE_LINE = re.compile(
    r"^\s*LRA:\s*(?P<value>-?(?:[0-9]+(?:\.[0-9]+)?|inf|nan))\s+LU\b",
    re.MULTILINE)
_TRUE_PEAK_LINE = re.compile(
    r"^\s*Peak:\s*(?P<value>-?(?:[0-9]+(?:\.[0-9]+)?|inf|nan))\s+dBFS",
    re.MULTILINE)


def _checked_source(path: object) -> Path:
    if not isinstance(path, (str, Path)):
        raise ValueError("source path must be a local file path")
    source = Path(path)
    if source.is_symlink():
        raise ValueError("source path must not be a symbolic link")
    if not source.is_file():
        raise ValueError("source path is not an existing regular file")
    return source


def _checked_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("timeout_seconds must be a finite number")
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= _MAX_TIMEOUT_SECONDS:
        raise ValueError(
            "timeout_seconds must be finite and in "
            f"(0, {_MAX_TIMEOUT_SECONDS:g}]")
    return number


def _checked_window(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("window_seconds must be a finite number")
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 1.0:
        raise ValueError("window_seconds must be finite and in (0, 1]")
    return number


def _run_ffmpeg(
    command: list[str], *, timeout: float, label: str,
    redact: Iterable[str] = (),
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, check=False)
    except FileNotFoundError:
        raise ValueError(f"{label}: ffmpeg executable was not found") from None
    except subprocess.TimeoutExpired:
        raise ValueError(
            f"{label}: ffmpeg exceeded the {timeout:g} s timeout") from None
    except OSError:
        raise ValueError(f"{label}: ffmpeg could not start") from None
    if result.returncode:
        tail = (result.stderr or "").strip()[-400:]
        raise ValueError(safe_error(
            ValueError(f"{label}: ffmpeg failed (exit {result.returncode}): "
                       f"{tail}"), redact=redact, limit=400))
    return result


def extract_audio(
    path: str | Path, destination: str | Path, *, ffmpeg: str = "ffmpeg",
    sample_rate: int = PCM_SAMPLE_RATE, timeout_seconds: float = 600.0,
) -> Path:
    """Extract one mono PCM stream to ``destination`` and return its path.

    The output is raw ``s16le`` (no container, no ``wave`` header) so the
    analyzer needs only the standard library. Video streams and all other
    audio streams are dropped. The file is scratch data: the caller owns
    ``destination`` and is responsible for deleting it, which keeps this
    package's "never delete your files" contract intact.
    """
    source = _checked_source(path)
    if not isinstance(ffmpeg, str) or not ffmpeg.strip():
        raise ValueError("ffmpeg must be a non-empty executable name")
    if (type(sample_rate) is not int
            or not PCM_SAMPLE_RATE <= sample_rate <= MAX_PCM_SAMPLE_RATE):
        raise ValueError(
            f"sample_rate must be an integer in "
            f"{PCM_SAMPLE_RATE}..{MAX_PCM_SAMPLE_RATE}")
    timeout = _checked_timeout(timeout_seconds)
    if not isinstance(destination, (str, Path)):
        raise ValueError("destination must be a local file path")
    target = Path(destination)
    if target.is_symlink():
        raise ValueError("destination must not be a symbolic link")
    if target.resolve() == source.resolve():
        raise ValueError("destination must differ from the source")
    if not target.parent.is_dir():
        raise ValueError("destination directory does not exist")

    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-i", str(source.resolve()), "-vn", "-map", "0:a:0",
        "-ac", str(PCM_CHANNELS), "-ar", str(sample_rate),
        "-f", "s16le", "-acodec", "pcm_s16le", str(target),
    ]
    _run_ffmpeg(
        command, timeout=timeout, label="audio extraction",
        redact=(str(source), str(source.resolve()), str(target)))
    if not target.is_file():
        raise ValueError("audio extraction produced no output file")
    return target


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
    elif isinstance(value, (int, float)):
        number = float(value)
    else:
        return None
    return number if math.isfinite(number) else None


def parse_ebur128_log(text: object) -> dict[str, Any]:
    """Parse ffmpeg ``ebur128=peak=true`` stderr into a loudness summary.

    The per-100 ms momentary lines are kept as ``momentaryLufs`` entries; the
    block after ``Summary:`` supplies the integrated loudness, loudness range
    and true peak. Missing or non-finite values stay ``None`` rather than being
    invented. A filter floor of -120.7 LUFS is preserved here; the per-second
    series in :func:`measure_audio` clamps it to the -70 LUFS absolute gate.
    """
    if not isinstance(text, str):
        raise ValueError("ebur128 log must be text")
    if len(text) > _MAX_FFMPEG_LOG_BYTES:
        raise ValueError("ebur128 log exceeded the bounded scan")
    momentary: list[dict[str, float]] = []
    for line in text.splitlines():
        match = _MOMENTARY_LINE.search(line)
        if match is None:
            continue
        seconds = _optional_float(match.group("seconds"))
        lufs = _optional_float(match.group("lufs"))
        if seconds is None or lufs is None:
            continue
        momentary.append({"seconds": round(seconds, 6), "lufs": lufs})

    summary = text.split("Summary:", 1)[1] if "Summary:" in text else ""
    integrated = _INTEGRATED_LINE.search(summary)
    loudness_range = _RANGE_LINE.search(summary)
    true_peak = _TRUE_PEAK_LINE.search(summary)
    return {
        "integratedLufs": (
            _optional_float(integrated.group("value")) if integrated else None),
        "loudnessRangeLu": (
            _optional_float(loudness_range.group("value"))
            if loudness_range else None),
        "truePeakDbfs": (
            _optional_float(true_peak.group("value")) if true_peak else None),
        "momentaryLufs": momentary,
    }


def ebur128_summary(
    path: str | Path, *, ffmpeg: str = "ffmpeg",
    timeout_seconds: float = 600.0,
) -> dict[str, Any]:
    """Run one EBU R128 pass over a local file and return its summary.

    ``ffmpeg -af ebur128=peak=true -f null -`` decodes audio only. The filter
    logs momentary loudness at 100 ms intervals and prints an integrated /
    loudness-range / true-peak summary at the end; no media is written.
    """
    source = _checked_source(path)
    timeout = _checked_timeout(timeout_seconds)
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "info", "-nostdin", "-nostats",
        "-i", str(source.resolve()), "-map", "0:a:0",
        "-af", "ebur128=peak=true", "-f", "null", "-",
    ]
    result = _run_ffmpeg(
        command, timeout=timeout, label="ebur128 pass",
        redact=(str(source), str(source.resolve())))
    return parse_ebur128_log(result.stderr or "")


def has_audio_stream(probe_payload: dict[str, Any]) -> bool:
    """True when an ffprobe-shaped payload declares at least one audio stream."""
    if not isinstance(probe_payload, dict):
        raise ValueError("probe payload must be a JSON object")
    streams = probe_payload.get("streams")
    if not isinstance(streams, list):
        return False
    return any(
        isinstance(stream, dict) and stream.get("codec_type") == "audio"
        for stream in streams)


def _read_pcm(path: object) -> array:
    pcm_path = _checked_source(path)
    try:
        raw = pcm_path.read_bytes()
    except OSError as error:
        raise ValueError(
            f"PCM could not be read: {safe_error(error)}") from None
    if not raw:
        raise ValueError("PCM is empty")
    if len(raw) % PCM_SAMPLE_WIDTH_BYTES:
        raise ValueError("PCM length is not a whole number of 16-bit samples")
    if len(raw) > _MAX_PCM_BYTES:
        raise ValueError("PCM exceeded the bounded analysis size")
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _frame_levels(
    samples: array, *, frame_length: int,
) -> tuple[list[float], float, float, int]:
    """Per-frame RMS dBFS plus overall RMS dBFS and true sample peak."""
    levels: list[float] = []
    total_squares = 0
    peak = 0
    for start in range(0, len(samples), frame_length):
        frame = samples[start:start + frame_length]
        power = sum(int(value) * int(value) for value in frame)
        total_squares += power
        frame_peak = max((abs(int(value)) for value in frame), default=0)
        if frame_peak > peak:
            peak = frame_peak
        rms = math.sqrt(power / len(frame)) / _SAMPLE_CEILING
        levels.append(
            20.0 * math.log10(rms) if rms > 0 else _DBFS_FLOOR)
    overall_rms = math.sqrt(total_squares / len(samples)) / _SAMPLE_CEILING
    rms_dbfs = 20.0 * math.log10(overall_rms) if overall_rms > 0 else _DBFS_FLOOR
    peak_dbfs = (
        20.0 * math.log10(peak / _SAMPLE_CEILING) if peak > 0 else _DBFS_FLOOR)
    return levels, rms_dbfs, peak_dbfs, peak


def _silence_extents(
    levels: list[float], *, window_seconds: float,
) -> tuple[float, float, int]:
    silent = [level < SILENCE_DBFS for level in levels]
    count = sum(1 for flag in silent if flag)
    head = 0
    for flag in silent:
        if not flag:
            break
        head += 1
    tail = 0
    for flag in reversed(silent):
        if not flag:
            break
        tail += 1
    return (
        round(head * window_seconds, 3),
        round(tail * window_seconds, 3),
        count,
    )


def _onset_positions(
    levels: list[float], *, window_seconds: float,
) -> list[int]:
    """Causal adaptive-threshold onset detector over the dBFS envelope."""
    frames = len(levels)
    rises = [0.0] * frames
    for index in range(1, frames):
        rises[index] = levels[index] - levels[index - 1]
    threshold_window = max(1, int(round(
        ONSET_THRESHOLD_WINDOW_SECONDS / window_seconds)))
    lookahead = max(1, int(round(
        ONSET_LOOKAHEAD_SECONDS / window_seconds)))
    onsets: list[int] = []
    for index in range(1, frames):
        rise = rises[index]
        if rise <= ONSET_MINIMUM_RISE_DB:
            continue
        previous = rises[max(1, index - threshold_window):index]
        positive = [value for value in previous if value > 0]
        local = statistics.median(positive) if positive else 0.0
        threshold = max(
            ONSET_MINIMUM_RISE_DB, local * ONSET_THRESHOLD_MULTIPLIER)
        if rise <= threshold:
            continue
        limit = min(frames, index + lookahead + 1)
        if any(rises[later] > rise for later in range(index + 1, limit)):
            continue
        onsets.append(index)
    return onsets


def _onset_rate_series(
    onset_times: list[float], *, duration_seconds: float,
) -> tuple[list[dict[str, Any]], str]:
    """Onset counts per 5 s bucket plus a first-third vs last-third trend."""
    bucket_count = max(
        1, int(math.ceil(duration_seconds / ONSET_RATE_BUCKET_SECONDS)))
    counts = [0] * bucket_count
    for time in onset_times:
        index = int(time // ONSET_RATE_BUCKET_SECONDS)
        counts[min(bucket_count - 1, index)] += 1
    series: list[dict[str, Any]] = []
    spans: list[float] = []
    for index, count in enumerate(counts):
        start = index * ONSET_RATE_BUCKET_SECONDS
        end = min((index + 1) * ONSET_RATE_BUCKET_SECONDS, duration_seconds)
        span = max(end - start, 1e-9)
        spans.append(span)
        series.append({
            "startSeconds": round(start, 3),
            "endSeconds": round(end, 3),
            "onsetCount": count,
            "onsetsPerMinute": round(count * 60.0 / span, 3),
        })
    third = max(1, int(math.ceil(bucket_count / 3)))
    first_span = sum(spans[:third])
    last_span = sum(spans[-third:])
    first_rate = sum(counts[:third]) * 60.0 / first_span if first_span else 0.0
    last_rate = sum(counts[-third:]) * 60.0 / last_span if last_span else 0.0
    if first_rate <= 0 and last_rate <= 0:
        trend = "steady"
    elif first_rate <= 0:
        trend = "accelerating"
    elif last_rate <= 0:
        trend = "decelerating"
    elif last_rate >= first_rate * (1.0 + ONSET_TREND_BAND):
        trend = "accelerating"
    elif last_rate <= first_rate * (1.0 - ONSET_TREND_BAND):
        trend = "decelerating"
    else:
        trend = "steady"
    return series, trend


def _tempo_hypothesis(
    envelope: list[float], *, window_seconds: float,
) -> tuple[float | None, float | None]:
    """Peak normalized autocorrelation of the rise envelope over 60-200 BPM."""
    frames = len(envelope)
    if frames < 3:
        return None, None
    lag_min = max(1, int(math.ceil(
        (60.0 / TEMPO_MAX_BPM) / window_seconds)))
    lag_max = int(math.floor(
        (60.0 / TEMPO_MIN_BPM) / window_seconds))
    lag_max = min(lag_max, frames - 2)
    if lag_max < lag_min:
        return None, None
    candidates: list[tuple[int, float]] = []
    for lag in range(lag_min, lag_max + 1):
        left = envelope[:frames - lag]
        right = envelope[lag:]
        if len(left) < 4:
            continue
        left_mean = sum(left) / len(left)
        right_mean = sum(right) / len(right)
        numerator = 0.0
        left_squares = 0.0
        right_squares = 0.0
        for first, second in zip(left, right):
            centred_first = first - left_mean
            centred_second = second - right_mean
            numerator += centred_first * centred_second
            left_squares += centred_first * centred_first
            right_squares += centred_second * centred_second
        denominator = math.sqrt(left_squares * right_squares)
        if denominator <= 0:
            continue
        coefficient = numerator / denominator
        if math.isfinite(coefficient):
            candidates.append((lag, coefficient))
    if not candidates:
        return None, None
    best = max(coefficient for _, coefficient in candidates)
    if best <= 0:
        return None, None
    chosen = next(
        (lag, coefficient) for lag, coefficient in candidates
        if coefficient >= best - TEMPO_TIE_TOLERANCE)
    lag, coefficient = chosen
    bpm = 60.0 / (lag * window_seconds)
    return (
        round(bpm, 1),
        round(min(1.0, max(0.0, coefficient)), 3),
    )


def _loudness_series(
    loudness_summary: dict[str, Any],
) -> list[float | None]:
    """One momentary value per whole second, at 1 decimal, index = second."""
    momentary = loudness_summary.get("momentaryLufs")
    if not isinstance(momentary, list):
        return []
    per_second: dict[int, float] = {}
    for entry in momentary:
        if not isinstance(entry, dict):
            continue
        seconds = _optional_float(entry.get("seconds"))
        lufs = _optional_float(entry.get("lufs"))
        if seconds is None or lufs is None or seconds < 0:
            continue
        per_second[int(math.floor(seconds))] = max(
            lufs, _LOUDNESS_FLOOR_LUFS)
    highest = max(per_second) if per_second else -1
    return [
        round(per_second[second], 1) if second in per_second else None
        for second in range(highest + 1)
    ]


def _linear_slope(
    series: list[float | None],
) -> tuple[float | None, float | None]:
    """Least-squares slope per minute and r² over non-null seconds."""
    points = [
        (float(second), float(value))
        for second, value in enumerate(series) if value is not None]
    if len(points) < 2:
        return None, None
    count = len(points)
    mean_x = sum(x for x, _ in points) / count
    mean_y = sum(y for _, y in points) / count
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in points)
    variance = sum((x - mean_x) ** 2 for x, _ in points)
    if variance <= 0:
        return None, None
    slope = covariance / variance
    total = sum((y - mean_y) ** 2 for _, y in points)
    residual = sum(
        (y - (mean_y + slope * (x - mean_x))) ** 2 for x, y in points)
    r_squared = 1.0 - residual / total if total > 0 else None
    return (
        round(slope * 60.0, 3),
        round(r_squared, 3) if r_squared is not None else None,
    )


def _half_difference(series: list[float | None]) -> float | None:
    values = [float(value) for value in series if value is not None]
    if len(values) < 2:
        return None
    middle = len(values) // 2
    first = values[:middle]
    second = values[middle:]
    if not first or not second:
        return None
    return round(
        sum(second) / len(second) - sum(first) / len(first), 3)


def measure_audio(
    pcm_path: str | Path, *, loudness_summary: dict[str, Any],
    window_seconds: float = 0.02,
) -> dict[str, Any]:
    """Measure one mono 8 kHz ``s16le`` PCM stream into numeric evidence.

    ``loudness_summary`` is the dict returned by :func:`ebur128_summary` (or an
    equivalent mapping with ``integratedLufs``, ``loudnessRangeLu``,
    ``truePeakDbfs`` and ``momentaryLufs``). Level, dynamics and onset numbers
    are computed from the PCM with the standard library only; no numpy.
    """
    if not isinstance(loudness_summary, dict):
        raise ValueError("loudness_summary must be a dict")
    window = _checked_window(window_seconds)
    samples = _read_pcm(pcm_path)
    frame_length = max(1, int(round(window * PCM_SAMPLE_RATE)))
    if len(samples) < frame_length:
        raise ValueError("PCM is shorter than one analysis window")

    levels, rms_dbfs, sample_peak_dbfs, _peak = _frame_levels(
        samples, frame_length=frame_length)
    duration = len(samples) / PCM_SAMPLE_RATE
    head_silence, tail_silence, silent_frames = _silence_extents(
        levels, window_seconds=window)

    onsets = _onset_positions(levels, window_seconds=window)
    onset_times = [round(index * window, 3) for index in onsets]
    gaps = [
        later - earlier
        for earlier, later in zip(onset_times, onset_times[1:])]
    median_gap = round(statistics.median(gaps), 3) if gaps else None
    regularity = None
    if len(onsets) >= MIN_REGULARITY_ONSETS and gaps:
        mean_gap = sum(gaps) / len(gaps)
        if mean_gap > 0:
            normalized = statistics.pstdev(gaps) / mean_gap
            regularity = round(min(1.0, max(0.0, 1.0 - normalized)), 3)

    onset_series, trend = _onset_rate_series(
        onset_times, duration_seconds=duration)
    # The onset envelope keeps only frame rises at or above the detector's
    # 2 dB floor, so a constant tone's tiny frame-to-frame RMS ripple cannot
    # manufacture a periodicity hypothesis.
    envelope = [
        rise if rise >= ONSET_MINIMUM_RISE_DB else 0.0
        for rise in (later - earlier
                     for earlier, later in zip(levels, levels[1:]))]
    tempo_bpm, tempo_confidence = _tempo_hypothesis(
        envelope, window_seconds=window)

    series = _loudness_series(loudness_summary)
    reported = [value for value in series if value is not None]
    short_term_range = (
        round(max(reported) - min(reported), 1) if reported else None)
    slope, r_squared = _linear_slope(series)

    return {
        "durationSeconds": round(duration, 3),
        "sampleRateHz": PCM_SAMPLE_RATE,
        "windowSeconds": round(window, 3),
        "frameCount": len(levels),
        "integratedLufs": _optional_float(
            loudness_summary.get("integratedLufs")),
        "loudnessRangeLu": _optional_float(
            loudness_summary.get("loudnessRangeLu")),
        "truePeakDbfs": _optional_float(
            loudness_summary.get("truePeakDbfs")),
        "samplePeakDbfs": round(sample_peak_dbfs, 2),
        "rmsDbfs": round(rms_dbfs, 2),
        "silenceFraction": round(silent_frames / len(levels), 6),
        "headSilenceSeconds": head_silence,
        "tailSilenceSeconds": tail_silence,
        "shortTermLufsSeries": series,
        "shortTermRangeLu": short_term_range,
        "loudnessSlopeLuPerMinute": slope,
        "loudnessSlopeR2": r_squared,
        "firstHalfVsSecondHalfLu": _half_difference(series),
        "onsetCount": len(onsets),
        "onsetTimesSeconds": onset_times,
        "onsetsPerMinuteOfRuntime": round(
            len(onsets) * 60.0 / duration, 3) if duration > 0 else None,
        "onsetRateSeries": onset_series,
        "onsetRateTrend": trend,
        "medianOnsetGapSeconds": median_gap,
        "regularityIndex": regularity,
        "tempoHypothesisBpm": tempo_bpm,
        "tempoConfidence": tempo_confidence,
        "methods": {
            "loudness": METHOD_EBUR128,
            "envelope": METHOD_ENVELOPE,
        },
        "limits": list(AUDIO_LIMITS),
    }
