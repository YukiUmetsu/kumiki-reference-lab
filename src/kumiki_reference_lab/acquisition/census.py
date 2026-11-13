"""Full-runtime cut census and fixed-cadence appearance series.

Windowed measurement samples four 10 s windows per clip, so a window rate
describes the windows, not the film. This module decodes the whole file once
for frame-accurate scene candidates and once at a fixed cadence for appearance
proxies. It performs no network access, writes no files, and knows nothing
about any website.

Both passes keep original source PTS. Candidate cuts are ffmpeg scene-score
exceedances, never verified edits; appearance rows are display-RGB proxies at
the requested decode size, never calibrated colour.
"""

from __future__ import annotations

import math
import re
import statistics
import subprocess
import time
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from kumiki_reference_lab.analyzers.appearance.source_visual_probe import (
    _frame_metrics,
)
from kumiki_reference_lab.backends.ffmpeg.probe import probe_media
from kumiki_reference_lab.backends.ffmpeg.scene import (
    _SHOWINFO_PTS, _SHOWINFO_TIMEBASE,
)
from kumiki_reference_lab.core.timebase import (
    as_rational_dict, parse_rational,
)

from .probe import finite_float
from .runner import safe_error
from .store import utc_now

CENSUS_SCHEMA = "kumiki.video-census.v1"

# Full-runtime scans are expensive; a caller may not queue an unbounded one.
MAX_SCAN_TIMEOUT_SECONDS = 7200.0
# A fixed cadence slower than this is a different measurement, not a census.
MAX_SAMPLE_SECONDS = 10.0
BURST_NEIGHBOUR_SECONDS = 0.25
NON_EDIT_MEDIAN_FRAMES = 3.0
_SEARCH_EXPRESSION = "isnan(prev_selected_t)+gte(t-prev_selected_t,{seconds})"
_MAX_LOG_BYTES = 8_000_000


def _checked_seconds(value: object, *, name: str = "sample_seconds") -> float:
    number = finite_float(value)
    if number is None or number <= 0 or number > MAX_SAMPLE_SECONDS:
        raise ValueError(
            f"{name} must be finite and in (0, {MAX_SAMPLE_SECONDS}]")
    return number


def _checked_timeout(value: object) -> float:
    number = finite_float(value)
    if number is None or number <= 0 or number > MAX_SCAN_TIMEOUT_SECONDS:
        raise ValueError(
            "timeout_seconds must be finite and in "
            f"(0, {MAX_SCAN_TIMEOUT_SECONDS}]")
    return number


def _checked_source(path: object, *, stream_index: object) -> tuple[Path, int]:
    if type(stream_index) is not int or stream_index < 0:
        raise ValueError("stream_index must be a nonnegative integer")
    if not isinstance(path, (str, Path)):
        raise ValueError("source path must be a local file path")
    source = Path(path)
    if source.is_symlink():
        raise ValueError("source path must not be a symbolic link")
    if not source.is_file():
        raise ValueError("source path is not an existing regular file")
    return source, stream_index


def _checked_frame_size(width: object, height: object) -> tuple[int, int]:
    if (type(width) is not int or type(height) is not int
            or not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("frame width/height are out of the 64..320/36..180 range")
    return width, height


def _checked_threshold(value: object) -> float:
    number = finite_float(value)
    if number is None or not 0 < number < 1:
        raise ValueError("cut_threshold must be finite and between 0 and 1")
    return number


def _run(command: list[str], *, timeout: float, label: str,
         text: bool, redact: Iterable[str] = ()) -> subprocess.CompletedProcess[Any]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=text,
            encoding="utf-8" if text else None,
            errors="replace" if text else None,
            timeout=timeout, check=False)
    except FileNotFoundError:
        raise ValueError(f"{label}: ffmpeg executable was not found") from None
    except subprocess.TimeoutExpired:
        raise ValueError(
            f"{label}: ffmpeg exceeded the {timeout:g} s timeout") from None
    except OSError:
        raise ValueError(f"{label}: ffmpeg could not start") from None
    if result.returncode:
        tail = result.stderr[-400:] if result.stderr else ""
        if isinstance(tail, bytes):
            tail = tail.decode("utf-8", errors="replace")
        raise ValueError(safe_error(
            ValueError(f"{label}: ffmpeg failed (exit {result.returncode}): "
                       f"{tail.strip()}"), redact=redact, limit=400))
    return result


def _scene_pass(
    source: Path, stream_index: int, *, threshold: float, ffmpeg: str,
    timeout: float,
) -> tuple[list[int], Fraction | None]:
    """One full-file scene-score pass; returns candidate PTS and its timebase."""
    filter_graph = f"select='gt(scene,{threshold:.17g})',showinfo"
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "info", "-nostdin", "-nostats",
        "-i", str(source.resolve()), "-map", f"0:{stream_index}",
        "-vf", filter_graph, "-an", "-f", "null", "-",
    ]
    result = _run(command, timeout=timeout, label="scene pass", text=True,
                  redact=(str(source), str(source.resolve())))
    stderr = result.stderr or ""
    if len(stderr) > _MAX_LOG_BYTES:
        raise ValueError("scene pass log exceeded the bounded scan")
    selected: list[int] = []
    timebases: set[Fraction] = set()
    for line in stderr.splitlines():
        if "Parsed_showinfo" not in line:
            continue
        match_timebase = _SHOWINFO_TIMEBASE.search(line)
        if match_timebase is not None:
            timebase = parse_rational(match_timebase.group(1))
            if timebase is None:
                raise ValueError("scene filter reported an invalid timebase")
            timebases.add(timebase)
        elif " n:" in line:
            match = _SHOWINFO_PTS.search(line)
            if match is None:
                raise ValueError(
                    "selected cut candidate lacked a valid source PTS")
            selected.append(int(match.group(1)))
    if len(timebases) > 1:
        raise ValueError("scene filter reported more than one timebase")
    return selected, (next(iter(timebases)) if timebases else None)


def _cadence_pass(
    source: Path, stream_index: int, *, sample_seconds: float, width: int,
    height: int, ffmpeg: str, timeout: float,
) -> tuple[list[int], list[bytes], Fraction]:
    """One full-file fixed-cadence decode; returns source PTS and RGB frames."""
    expression = _SEARCH_EXPRESSION.format(seconds=f"{sample_seconds:.17g}")
    filter_graph = (
        f"select='{expression}',scale={width}:{height}:flags=bicubic,"
        "format=rgb24,showinfo")
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "info", "-nostdin", "-nostats",
        "-i", str(source.resolve()), "-map", f"0:{stream_index}",
        "-vf", filter_graph, "-an", "-fps_mode", "passthrough",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ]
    result = _run(command, timeout=timeout, label="cadence pass", text=False,
                  redact=(str(source), str(source.resolve())))
    stderr = result.stderr or b""
    if isinstance(stderr, str):
        stderr = stderr.encode("utf-8", errors="replace")
    if len(stderr) > _MAX_LOG_BYTES:
        raise ValueError("cadence pass log exceeded the bounded scan")
    pts: list[int] = []
    timebases: set[Fraction] = set()
    for line in stderr.decode("utf-8", errors="replace").splitlines():
        if "Parsed_showinfo" not in line:
            continue
        match_timebase = _SHOWINFO_TIMEBASE.search(line)
        if match_timebase is not None:
            timebase = parse_rational(match_timebase.group(1))
            if timebase is None:
                raise ValueError("cadence filter reported an invalid timebase")
            timebases.add(timebase)
        elif " n:" in line:
            match = _SHOWINFO_PTS.search(line)
            if match is None:
                raise ValueError("cadence pass reported an invalid source PTS")
            pts.append(int(match.group(1)))
    if len(timebases) != 1:
        raise ValueError("cadence pass did not expose one unambiguous timebase")
    plane_size = width * height * 3
    body = result.stdout or b""
    if len(body) != plane_size * len(pts):
        raise ValueError(
            "cadence pass produced an unexpected pixel-buffer size")
    frames = [body[index * plane_size:(index + 1) * plane_size]
              for index in range(len(pts))]
    return pts, frames, next(iter(timebases))


def _percentile(values: list[float], quantile: float) -> float:
    """Linear-interpolated percentile over an already sorted list."""
    if not values:
        raise ValueError("percentile needs at least one value")
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * quantile
    lower = math.floor(position)
    upper = min(len(values) - 1, lower + 1)
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _cut_statistics(
    cut_pts: Iterable[int], *, timebase_seconds: float,
    duration_seconds: float, fps: float | None,
) -> dict[str, Any]:
    """Pure gap/burst/strobe maths over original-PTS cut candidates."""
    if (not math.isfinite(timebase_seconds) or timebase_seconds <= 0
            or not math.isfinite(duration_seconds) or duration_seconds <= 0):
        raise ValueError("cut statistics need a positive timebase and duration")
    ordered = sorted({int(value) for value in cut_pts})
    count = len(ordered)
    cuts_per_minute = round(count * 60.0 / duration_seconds, 6)
    gaps = [(later - earlier) * timebase_seconds
            for earlier, later in zip(ordered, ordered[1:])]
    median_gap_seconds = None
    median_gap_frames = None
    min_gap_seconds = None
    p10_gap_seconds = None
    burst_fraction = None
    if gaps:
        gap_mean = statistics.median(gaps)
        median_gap_seconds = round(gap_mean, 6)
        if fps is not None and fps > 0:
            median_gap_frames = round(gap_mean * fps, 6)
        min_gap_seconds = round(min(gaps), 6)
        p10_gap_seconds = round(_percentile(sorted(gaps), 0.10), 6)
        burst_count = 0
        for index in range(count):
            nearest = min(
                gaps[index - 1] if index > 0 else math.inf,
                gaps[index] if index < len(gaps) else math.inf,
            )
            if nearest < BURST_NEIGHBOUR_SECONDS:
                burst_count += 1
        burst_fraction = round(burst_count / count, 6)
    strobe = bool(
        (median_gap_frames is not None
         and median_gap_frames < NON_EDIT_MEDIAN_FRAMES)
        or (burst_fraction is not None
            and burst_fraction > 0.5))
    return {
        "cutCount": count,
        "cutsPerMinute": cuts_per_minute,
        "medianCutGapSeconds": median_gap_seconds,
        "medianCutGapFrames": median_gap_frames,
        "minCutGapSeconds": min_gap_seconds,
        "p10CutGapSeconds": p10_gap_seconds,
        "burstFraction": burst_fraction,
        "strobe": strobe,
    }


def _time_weights(times: list[float], duration_seconds: float) -> list[float]:
    """Interval weights that tile [0, duration] without gaps."""
    if not times:
        return []
    if len(times) == 1:
        return [max(duration_seconds, 1e-9)]
    widths = [max(0.0, later - earlier)
              for earlier, later in zip(times, times[1:])]
    if times[0] > 0:
        # The first sample also stands for the untouched prefix before it.
        widths[0] += times[0]
    positive = [width for width in widths if width > 0]
    typical = statistics.median(positive) if positive else 1.0
    trailing = duration_seconds - times[-1]
    widths.append(trailing if trailing > 0 else typical)
    if sum(widths) <= 0:
        return [1.0] * len(times)
    return widths


def _series_summary(
    series: list[dict[str, Any]], *, duration_seconds: float,
) -> dict[str, Any]:
    """Time-weighted luma/saturation means over the tiled runtime."""
    times = [float(row["sourceSeconds"]) for row in series]
    weights = _time_weights(times, duration_seconds)
    total = sum(weights)

    def weighted(key: str) -> float | None:
        pairs = [(float(row[key]), weight)
                 for row, weight in zip(series, weights)
                 if finite_float(row.get(key)) is not None]
        if not pairs or total <= 0:
            return None
        return round(sum(value * weight for value, weight in pairs) / total, 6)

    sampled_seconds = round(duration_seconds, 6)
    return {
        "meanDisplayLuma": weighted("meanDisplayLumaProxy"),
        "meanSaturation": weighted("meanSaturationProxy"),
        "sampledSeconds": sampled_seconds,
        "decodeCoverageFraction": 1.0,
        "samples": len(series),
    }


def scan_full_runtime(
    path: str | Path, *, stream_index: int = 0, sample_seconds: float = 1.0,
    width: int = 160, height: int = 90, cut_threshold: float = 0.25,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    timeout_seconds: float = 3600.0,
) -> dict[str, Any]:
    """Decode one whole local video twice and return a neutral census block.

    Pass 1 selects every frame whose scene score exceeds ``cut_threshold`` and
    reports its original PTS. Pass 2 selects one frame per ``sample_seconds``
    at ``width``×``height`` and reports display-RGB proxies. No window, seek,
    or network read is involved; ``fullRuntimeDecoded`` is therefore ``True``.
    """
    source, stream = _checked_source(path, stream_index=stream_index)
    sample = _checked_seconds(sample_seconds)
    width, height = _checked_frame_size(width, height)
    threshold = _checked_threshold(cut_threshold)
    timeout = _checked_timeout(timeout_seconds)
    started = time.monotonic()

    payload = probe_media(source, ffprobe=ffprobe, timeout=min(120.0, timeout))
    streams = payload.get("streams")
    streams = streams if isinstance(streams, list) else []
    video = next((item for item in streams
                  if isinstance(item, dict)
                  and item.get("index") == stream
                  and item.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError("requested stream index is not a video stream")
    source_width, source_height = video.get("width"), video.get("height")
    if (type(source_width) is not int or type(source_height) is not int
            or source_width <= 0 or source_height <= 0):
        raise ValueError("video stream reported invalid dimensions")
    format_metadata = payload.get("format")
    format_metadata = format_metadata if isinstance(format_metadata, dict) else {}
    duration = finite_float(format_metadata.get("duration"))
    if duration is None:
        duration = finite_float(video.get("duration"))
    if duration is None or duration <= 0:
        raise ValueError("video reported no usable duration")
    fps_fraction = (parse_rational(video.get("avg_frame_rate"))
                    or parse_rational(video.get("r_frame_rate")))
    probe_timebase = parse_rational(video.get("time_base"))
    fps_value = float(fps_fraction) if fps_fraction is not None else None

    cut_pts, scene_timebase = _scene_pass(
        source, stream, threshold=threshold, ffmpeg=ffmpeg, timeout=timeout)
    timebase = scene_timebase or probe_timebase
    if timebase is None:
        raise ValueError("source has no usable timebase")
    if probe_timebase is not None and timebase != probe_timebase:
        raise ValueError("scene filter changed the original source timebase")
    sample_pts, frames, cadence_timebase = _cadence_pass(
        source, stream, sample_seconds=sample, width=width, height=height,
        ffmpeg=ffmpeg, timeout=timeout)
    if cadence_timebase != timebase:
        raise ValueError("cadence pass changed the original source timebase")
    if len(sample_pts) != len(frames):
        raise ValueError("cadence pass PTS and frame counts differ")

    series: list[dict[str, Any]] = []
    for pts, frame in zip(sample_pts, frames, strict=True):
        metrics = _frame_metrics(frame, width=width, height=height)
        series.append({
            "sourcePts": pts,
            "sourceSeconds": round(pts * float(timebase), 6),
            "meanRgb": metrics["meanRgb"],
            "meanDisplayLumaProxy": metrics["meanDisplayLumaProxy"],
            "meanSaturationProxy": metrics["meanSaturationProxy"],
            "shadowPixelFraction": metrics["shadowPixelFraction"],
            "brightPixelFraction": metrics["brightPixelFraction"],
        })

    stats = _cut_statistics(
        cut_pts, timebase_seconds=float(timebase),
        duration_seconds=duration, fps=fps_value)
    summary = _series_summary(series, duration_seconds=duration)
    return {
        "durationSeconds": round(duration, 6),
        "timebase": as_rational_dict(timebase),
        "fps": as_rational_dict(fps_fraction),
        "resolution": [source_width, source_height],
        "cutPts": sorted({int(value) for value in cut_pts}),
        **stats,
        "series": series,
        "seriesSummary": summary,
        "scanSeconds": round(time.monotonic() - started, 3),
        "fullRuntimeDecoded": True,
    }


def build_census_evidence(
    scan: dict[str, Any], *, source: dict[str, Any], video_url: str | None,
    provider: str, download_method: str, rights_basis: str, rights_note: str,
    schema_version: str, evidence_status: str, limits: Iterable[str],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble the neutral full-runtime census evidence payload."""
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError("census schema version must be a non-empty string")
    if not isinstance(evidence_status, str) or not evidence_status.strip():
        raise ValueError("evidence status must be a non-empty string")
    for name, value in (("provider", provider),
                        ("download method", download_method),
                        ("rights basis", rights_basis),
                        ("rights note", rights_note)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    if not isinstance(source, dict):
        raise ValueError("census source must be a dict")
    if not isinstance(scan, dict):
        raise ValueError("census scan must be a dict")
    if scan.get("fullRuntimeDecoded") is not True:
        raise ValueError("census scan must declare a full-runtime decode")
    summary = scan.get("seriesSummary")
    summary = summary if isinstance(summary, dict) else {}
    coverage_fraction = finite_float(summary.get("decodeCoverageFraction"))
    return {
        "schemaVersion": schema_version,
        "source": dict(source),
        "acquisition": {
            "provider": provider,
            "videoUrl": video_url,
            "method": download_method,
            "mediaRetained": False,
            "attestation": {
                "rightsBasis": rights_basis,
                "note": rights_note,
            },
        },
        "coverage": {
            "fullFilmDecoded": True,
            "decodeCoverageFraction": (
                coverage_fraction if coverage_fraction is not None else 1.0),
        },
        "census": scan,
        "evidenceStatus": evidence_status,
        "rightsStatus": "review-required",
        "limits": list(limits),
        "generatedAt": generated_at or utc_now(),
    }
