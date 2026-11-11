"""Bounded random-access FFprobe/FFmpeg decoding with original source PTS.

Unlike prefix-ordinal decoding, this supports later windows without processing
the entire source. FFmpeg receives input-side -ss and -copyts: output PTS are
always verified against FFprobe's actual source timestamps. No FPS arithmetic,
timestamp renumbering or approximate nearest-frame fallback.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.backends.ffmpeg.scene import CutScan
from kumiki_reference_lab.core.timebase import parse_rational

_PTS = re.compile(r"\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:")
_TIMEBASE = re.compile(r"config in time_base:\s*(\d+/\d+)")
_MAX_SEEK_END = 3600


@dataclass(frozen=True)
class SourceWindowFrame:
    """Original source timestamp; local seek ordinals are intentionally omitted."""
    pts: int
    timestamp_origin: str


@dataclass(frozen=True)
class SourceWindow:
    timebase: Fraction
    first_source_pts: int
    start_seconds: int
    seconds: int
    frames: tuple[SourceWindowFrame, ...]


def _bounds(start_seconds: int, seconds: int) -> None:
    if (type(start_seconds) is not int or start_seconds < 0 or
            type(seconds) is not int or not 1 <= seconds <= 30 or
            start_seconds + seconds > _MAX_SEEK_END):
        raise ValueError("seek window must be 1–30s and end within 3600s")


def _original_opening_pts(path: Path, stream_index: int, *, ffprobe: str) -> int:
    first = read_frame_pts(
        path, stream_index, seconds=1, ffprobe=ffprobe, max_frames=1000)
    if not first or first[0].pts is None:
        raise ProbeError("cannot anchor seek window without original opening frame PTS")
    return first[0].pts


def probe_source_window(
    path: Path, stream_index: int, *, timebase: Fraction,
    start_seconds: int, seconds: int, ffprobe: str = "ffprobe",
    max_scan_frames: int = 8000,
) -> SourceWindow:
    """Read original PTS in a later bounded window using indexed FFprobe seek.

    FFprobe may start at an earlier keyframe, so the read interval deliberately
    includes 30s guard while the source-PTS filter enforces exact requested
    bounds. A short/long GOP can still yield incomplete coverage; callers
    must not claim every possible frame was reviewed.
    """
    _bounds(start_seconds, seconds)
    if type(stream_index) is not int or not 0 <= stream_index <= 64:
        raise ValueError("invalid window video stream index")
    if not isinstance(timebase, Fraction) or timebase <= 0:
        raise ValueError("seek requires exact positive source timebase")
    if type(max_scan_frames) is not int or not 2 <= max_scan_frames <= 10000:
        raise ValueError("invalid maximum window FFprobe frame budget")
    first_pts = _original_opening_pts(path, stream_index, ffprobe=ffprobe)
    read_seconds = seconds + 30
    cmd = [
        ffprobe, "-v", "error", "-select_streams", str(stream_index),
        "-read_intervals", f"{start_seconds}%+{read_seconds}",
        "-show_frames", "-show_entries", "frame=pts,best_effort_timestamp",
        "-of", "compact=p=0:nk=0", "-i", str(path.resolve()),
    ]
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace",
            encoding="utf-8", timeout=min(150, read_seconds*3+20), check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError("source window FFprobe seek failed or timed out") from exc
    if p.returncode:
        raise ProbeError(f"source window FFprobe failed (exit code {p.returncode})")
    if len(p.stdout) > 16_000_000:
        raise ProbeError("source window frame inventory too large")
    frames: list[SourceWindowFrame] = []
    count = 0
    lower, upper = Fraction(start_seconds), Fraction(start_seconds + seconds)
    for line in p.stdout.splitlines():
        if not line.strip():
            continue
        fields = dict(
            item.split("=", 1) for item in line.split("|") if "=" in item
        )
        if not ("pts" in fields or "best_effort_timestamp" in fields):
            continue
        count += 1
        if count > max_scan_frames:
            raise ProbeError("window FFprobe decoded frame inventory exceeds budget")
        pts = None
        origin = "missing"
        for field, name in (("best_effort_timestamp", "best_effort_timestamp"),
                            ("pts", "pts-fallback")):
            candidate = fields.get(field)
            if candidate is not None and candidate.lstrip("-").isdigit():
                pts, origin = int(candidate), name
                break
        if pts is None:
            continue
        relative = Fraction(pts-first_pts)*timebase
        if lower <= relative < upper:
            if frames and pts <= frames[-1].pts:
                raise ProbeError("source window returned repeated or nonmonotonic original PTS")
            frames.append(SourceWindowFrame(pts, origin))
    if not frames:
        raise ProbeError("no source video frames at the requested seek window")
    return SourceWindow(
        timebase=timebase, first_source_pts=first_pts,
        start_seconds=start_seconds, seconds=seconds, frames=tuple(frames),
    )


def decode_rgb_source_pts_seek(
    path: Path, stream_index: int, expected_pts: list[int], *,
    window: SourceWindow, width: int = 320, height: int = 180,
    ffmpeg: str = "ffmpeg",
) -> list[bytes]:
    """Decode specified PTS via input-side seek; validate exact PTS after filter."""
    _bounds(window.start_seconds, window.seconds)
    if type(stream_index) is not int or not 0 <= stream_index <= 64:
        raise ValueError("invalid seek decoder stream index")
    if (type(width) is not int or type(height) is not int or
            not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("seek decoder resolution is out of bounds")
    if (not isinstance(expected_pts, list) or not 1 <= len(expected_pts) <= 24 or
            any(type(x) is not int or abs(x) > 2**53 for x in expected_pts) or
            expected_pts != sorted(set(expected_pts))):
        raise ValueError("seek frame PTS must be unique sorted exact integers")
    known = {frame.pts for frame in window.frames}
    if not set(expected_pts).issubset(known):
        raise ValueError("seek decoder selected timestamps not verified by FFprobe")
    selector = "+".join(f"eq(pts,{pts})" for pts in expected_pts)
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "info", "-nostdin",
        "-ss", str(window.start_seconds), "-copyts",
        "-t", str(window.seconds), "-i", str(path.resolve()),
        "-map", f"0:{stream_index}",
        "-vf",
        f"select='{selector}',scale={width}:{height}:flags=bicubic,format=rgb24,showinfo",
        "-an", "-fps_mode", "passthrough", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
    ]
    try:
        p = subprocess.run(
            cmd, capture_output=True, timeout=min(180, window.seconds*4+30),
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError("source PTS seek decoder failed or timed out") from exc
    if p.returncode:
        raise ProbeError(f"source PTS seek decoder exited with code {p.returncode}")
    if len(p.stderr) > 8_000_000:
        raise ProbeError("source PTS seek decoder log exceeded budget")
    reported_pts: list[int] = []
    timebases: set[Fraction] = set()
    for line in p.stderr.decode("utf-8", errors="replace").splitlines():
        if "Parsed_showinfo" not in line:
            continue
        match_tb = _TIMEBASE.search(line)
        if match_tb is not None:
            tb = parse_rational(match_tb.group(1))
            if tb is None:
                raise ProbeError("invalid source seek decoder timebase")
            timebases.add(tb)
        elif " n:" in line:
            match = _PTS.search(line)
            if match is None:
                raise ProbeError("source seek decoder emitted a frame without original PTS")
            reported_pts.append(int(match.group(1)))
    if timebases != {window.timebase}:
        raise ProbeError("source seek decoder changed or omitted video timebase")
    if reported_pts != expected_pts:
        raise ProbeError("source seek decoder PTS mismatch; no approximate frame selection")
    frame_bytes = width*height*3
    if len(p.stdout) != frame_bytes*len(expected_pts):
        raise ProbeError("source seek decoder returned incomplete RGB pixel buffers")
    return [
        p.stdout[i*frame_bytes:(i+1)*frame_bytes] for i in range(len(expected_pts))
    ]


def detect_source_window_cuts_seek(
    path: Path, stream_index: int, *, window: SourceWindow,
    threshold: float = 0.25, ffmpeg: str = "ffmpeg",
) -> CutScan:
    """Seek-based FFmpeg cut candidates with verified *original* video PTS."""
    import math

    _bounds(window.start_seconds, window.seconds)
    if type(stream_index) is not int or not 0 <= stream_index <= 64:
        raise ValueError("invalid cut seek stream index")
    if (type(threshold) not in (float, int) or not math.isfinite(threshold)
            or not 0 < threshold < 1):
        raise ValueError("invalid cut seek threshold")
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "info", "-nostdin",
        "-ss", str(window.start_seconds), "-copyts", "-t", str(window.seconds),
        "-i", str(path.resolve()), "-map", f"0:{stream_index}",
        "-vf", f"select='gt(scene,{threshold:.17g})',showinfo",
        "-an", "-f", "null", "-",
    ]
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=min(180,window.seconds*4+30), check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError("source-window cut scan failed or timed out") from exc
    if p.returncode:
        raise ProbeError(f"source-window cut scan exited with code {p.returncode}")
    if len(p.stderr) > 8_000_000:
        raise ProbeError("source-window cut log exceeded 8 MiB")
    reported_pts: list[int] = []
    timebases: set[Fraction] = set()
    for line in p.stderr.splitlines():
        if "Parsed_showinfo" not in line:
            continue
        match_tb = _TIMEBASE.search(line)
        if match_tb:
            tb = parse_rational(match_tb.group(1))
            if tb is None:
                raise ProbeError("source-window cuts reported malformed timebase")
            timebases.add(tb)
        elif " n:" in line:
            match = _PTS.search(line)
            if match is None:
                raise ProbeError("source-window cut has missing original PTS")
            reported_pts.append(int(match.group(1)))
    if timebases != {window.timebase}:
        raise ProbeError("source-window cut filter changed video timebase")
    lower = Fraction(window.start_seconds)
    upper = Fraction(window.start_seconds+window.seconds)
    for pts in reported_pts:
        relative = Fraction(pts-window.first_source_pts)*window.timebase
        if not lower <= relative < upper:
            raise ProbeError("source-window cut PTS outside requested source interval")
    return CutScan(window.timebase, tuple(sorted(set(reported_pts))))
