"""Original-audio-time-aligned RMS/peak observations using FFmpeg astats."""

from __future__ import annotations

import math
import re
import subprocess
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.audio.timeline import analyze_audio_timeline
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.contracts.analysis import AUDIO_LEVELS_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged


_FRAME_HEADER = re.compile(r"^frame:(\d+)\s+pts:(-?\d+)\s+pts_time:(\S+)$")
_RMS_KEY = "lavfi.astats.Overall.RMS_level"
_PEAK_KEY = "lavfi.astats.Overall.Peak_level"
_SAMPLES_KEY = "lavfi.astats.Overall.Number_of_samples"


def _level(value: str) -> float | None:
    try:
        number = float(value)
    except ValueError as exc:
        raise ProbeError("invalid FFmpeg audio level") from exc
    if math.isinf(number) and number < 0:
        return None  # Negative infinity is below measurable RMS/peak level.
    if not math.isfinite(number) or number > 2 or number < -400:
        raise ProbeError("FFmpeg audio level is non-finite or out of range")
    return round(number, 6)


def _read_levels(source: Path, stream_index: int, seconds: int, *,
                 ffmpeg: str, max_frames: int) -> list[dict[str, Any]]:
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
        "-t", str(seconds), "-i", str(source.resolve()),
        "-map", f"0:{stream_index}",
        "-af", "astats=metadata=1:reset=1,ametadata=print:file=-",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=min(180, seconds*3+20), check=False)
    except FileNotFoundError as exc:
        raise ProbeError("ffmpeg executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("FFmpeg audio-level scan timed out") from exc
    except OSError as exc:
        raise ProbeError("FFmpeg audio-level scan failed to start") from exc
    if result.returncode:
        raise ProbeError(f"audio-level scan failed (exit code {result.returncode})")
    if len(result.stdout) > 8_000_000:
        raise ProbeError("audio-level scan exceeded output budget")
    frames: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in result.stdout.splitlines():
        match = _FRAME_HEADER.fullmatch(line.strip())
        if match:
            if len(frames) >= max_frames:
                raise ProbeError("audio-level frame budget exceeded")
            if int(match.group(1)) != len(frames):
                raise ProbeError("audio-level frame ordinal is missing or reordered")
            current = {"ordinal": len(frames), "filterPtsTime": match.group(3),
                       "metrics": {}}
            frames.append(current)
            continue
        if line.startswith("lavfi.astats.Overall.") and "=" in line:
            if current is None:
                raise ProbeError("audio metrics appeared before a frame")
            key, value = line.split("=", 1)
            if key in current["metrics"]:
                raise ProbeError("duplicate audio metric in a frame")
            current["metrics"][key] = value
    for frame in frames:
        if not {_RMS_KEY, _PEAK_KEY, _SAMPLES_KEY}.issubset(frame["metrics"]):
            raise ProbeError("FFmpeg did not report complete per-frame audio levels")
    return frames


def analyze_audio_levels(source: Path, *, seconds: int = 10,
                         max_frames: int = 4096, ffmpeg: str = "ffmpeg",
                         ffprobe: str = "ffprobe",
                         rights_status: str = "review-required") -> dict[str, Any]:
    """Measure relative acoustic level only when audio PTS can be reconciled."""
    signature = file_signature(source)
    timeline = analyze_audio_timeline(
        source, seconds=seconds, max_frames=max_frames, ffprobe=ffprobe,
        rights_status=rights_status)
    base = {
        "schemaVersion": AUDIO_LEVELS_VERSION,
        "sourceSha256": timeline["sourceSha256"],
        "audioStreamIndex": timeline["audioStreamIndex"],
        "sourceTimebase": timeline["sourceTimebase"],
        "sampleRateHz": timeline["sampleRateHz"],
        "scanWindowSeconds": seconds,
        "maxFrameBudget": max_frames,
        "levelUnits": "dBFS-relative-to-decoded-audio-full-scale",
        "coverage": "bounded-first-audio-stream-not-necessarily-full-video",
        "limits": "FFmpeg decoded-frame RMS and peak levels, not music beats, speech, objective silence, original production mix, quality, semantic SFX or verified A/V sync. Up to four extra strictly later FFmpeg frames at the FFprobe read-interval boundary are excluded after timestamp checks. A final source frame that crosses the scan boundary may be excluded if FFmpeg trims its decoded sample count.",
    }
    if timeline["status"] == "no-audio-stream":
        require_unchanged(source, signature)
        return {**base, "status": "no-audio-stream", "frames": [],
                "excludedPartialBoundaryFrames": 0}
    if timeline["status"] != "source-timing-candidate":
        raise ValueError("audio levels require complete, monotonic original audio frame PTS")
    measured = _read_levels(source, timeline["audioStreamIndex"], seconds,
                            ffmpeg=ffmpeg, max_frames=max_frames)
    originals = timeline["frames"]
    # FFprobe's -read_intervals ends on a packet boundary, whereas FFmpeg's
    # -t filters decoded audio through the requested duration. AAC can yield
    # one or two additional *trailing* decoded frames in the latter. Preserve
    # strict 1:1 checks for every original frame; never extrapolate missing
    # frames, and only discard a small, timestamp-verified tail.
    if not len(originals) <= len(measured) <= len(originals) + 4:
        raise ValueError("FFmpeg audio levels cannot be aligned 1:1 with source frames")
    if len(measured) > len(originals):
        previous = Fraction(**originals[-1]["sourceSeconds"])
        for extra in measured[len(originals):]:
            try:
                timestamp = Fraction(Decimal(extra["filterPtsTime"]))
            except (InvalidOperation, ValueError, ZeroDivisionError) as exc:
                raise ProbeError("FFmpeg audio filter reported invalid PTS time") from exc
            if timestamp <= previous or timestamp >= Fraction(seconds) + Fraction(1, timeline["sampleRateHz"]):
                raise ValueError("FFmpeg extra audio frames are not a valid trailing interval")
            previous = timestamp
    rows: list[dict[str, Any]] = []
    excluded_partial_boundary = 0
    for index, (original, measured_frame) in enumerate(
            zip(originals, measured[:len(originals)], strict=True)):
        # A filter is free to change its timebase. Compare presentation seconds
        # using the *original* stream clock with <= 1 decoded sample tolerance.
        try:
            filter_seconds = Fraction(Decimal(measured_frame["filterPtsTime"]))
        except (InvalidOperation, ValueError, ZeroDivisionError) as exc:
            raise ProbeError("FFmpeg audio filter reported invalid PTS time") from exc
        source_seconds = Fraction(**original["sourceSeconds"])
        if abs(filter_seconds - source_seconds) > Fraction(1, timeline["sampleRateHz"]):
            raise ValueError("FFmpeg audio filter timing differs from original source PTS")
        metrics = measured_frame["metrics"]
        try:
            count = float(metrics[_SAMPLES_KEY])
        except ValueError as exc:
            raise ProbeError("invalid FFmpeg audio decoded sample count") from exc
        if not math.isfinite(count) or not count.is_integer():
            raise ValueError("FFmpeg audio-level sample count differs from original decode")
        if int(count) != original["decodedSampleCount"]:
            # FFprobe reports the *whole* decoded frame crossing a requested
            # read boundary. FFmpeg -t can instead output only its interior
            # samples. Never attach an RMS/peak computed on that shorter
            # sample span to the full source frame.
            original_end = source_seconds + Fraction(
                original["decodedSampleCount"], timeline["sampleRateHz"])
            expected_trimmed_count = round(
                (Fraction(seconds) - source_seconds) * timeline["sampleRateHz"])
            if (index == len(originals) - 1
                    and 0 < count < original["decodedSampleCount"]
                    and source_seconds < seconds < original_end
                    and abs(count - expected_trimmed_count) <= 1):
                excluded_partial_boundary += 1
                continue
            raise ValueError("FFmpeg audio-level sample count differs from original decode")
        rms, peak = _level(metrics[_RMS_KEY]), _level(metrics[_PEAK_KEY])
        rows.append({
            "sourcePts": original["sourcePts"],
            "sourceSeconds": original["sourceSeconds"],
            "decodedSampleCount": original["decodedSampleCount"],
            "decodedDurationSeconds": original["decodedDurationSeconds"],
            "rmsDbFs": rms, "peakDbFs": peak,
            "belowMeasurementFloor": rms is None,
            "quietFrameCandidate": rms is None or rms <= -45.0,
        })
    require_unchanged(source, signature)
    return {**base, "status": "source-pts-aligned-level-observations",
            "excludedPartialBoundaryFrames": excluded_partial_boundary,
            "frames": rows}
