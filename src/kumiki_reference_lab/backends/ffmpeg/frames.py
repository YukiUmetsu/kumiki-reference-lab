"""Bounded FFprobe frame timestamp extraction; never uses nominal FPS as PTS."""

from __future__ import annotations

import subprocess
from fractions import Fraction
from pathlib import Path

from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.contracts.frames import FramePts


def read_frame_pts(
    path: Path, stream_index: int, *, seconds: int = 60,
    ffprobe: str = "ffprobe", max_frames: int = 20_000,
    start_seconds: int = 0, source_timebase: Fraction | None = None,
) -> list[FramePts]:
    if type(seconds) is not int or not 1 <= seconds <= 120:
        raise ValueError("seconds must be between 1 and 120")
    if type(stream_index) is not int or stream_index < 0:
        raise ValueError("stream_index must be nonnegative")
    if type(max_frames) is not int or max_frames < 1:
        raise ValueError("max_frames must be positive")
    if type(start_seconds) is not int or start_seconds < 0:
        raise ValueError("start_seconds must be a nonnegative integer")
    if start_seconds + seconds > 120:
        raise ValueError("total source-prefix scan must be at most 120 seconds")
    if start_seconds and (source_timebase is None or source_timebase <= 0):
        raise ValueError("a positive original source timebase is required for a later window")

    command = [
        ffprobe, "-v", "error", "-select_streams", str(stream_index),
        "-read_intervals", f"%+{start_seconds + seconds}",
        "-show_frames", "-show_entries", "frame=pts,best_effort_timestamp",
        "-of", "compact=p=0:nk=0", "-i", str(path.resolve()),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=min(180, (start_seconds + seconds) * 3 + 20), check=False,
        )
    except FileNotFoundError as exc:
        raise ProbeError("ffprobe executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("ffprobe frame scan timed out") from exc
    except OSError as exc:
        raise ProbeError("ffprobe frame scan could not start") from exc

    if result.returncode:
        raise ProbeError(f"ffprobe frame scan failed (exit code {result.returncode})")
    if len(result.stdout) > 16_000_000:
        raise ProbeError("frame timeline exceeded the bounded scan output")

    frames: list[FramePts] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        fields = dict(
            item.split("=", 1) for item in line.split("|") if "=" in item
        )
        if not ("pts" in fields or "best_effort_timestamp" in fields):
            continue
        if len(frames) >= max_frames:
            raise ProbeError("frame count exceeds the requested analysis budget")
        pts = None
        origin = "missing"
        for key, name in (("best_effort_timestamp", "best_effort_timestamp"),
                          ("pts", "pts-fallback")):
            value = fields.get(key)
            if value is not None and value.lstrip("-").isdigit():
                pts, origin = int(value), name
                break
        frames.append(FramePts(len(frames), pts, origin))
    if not start_seconds:
        return frames
    # Scan the bounded source prefix and preserve original decoded ordinals.
    # FFprobe's seeking can land on an earlier keyframe; prefix scanning avoids
    # introducing shifted or invented timestamps around the requested boundary.
    first_pts = frames[0].pts if frames else None
    if first_pts is None:
        raise ProbeError("cannot place source window without a timestamped opening frame")
    assert source_timebase is not None
    lower = Fraction(start_seconds)
    upper = Fraction(start_seconds + seconds)
    selected = [frame for frame in frames if frame.pts is not None and
                lower <= (frame.pts - first_pts) * source_timebase < upper]
    if not selected:
        raise ProbeError("requested source window contains no decoded timestamped frames")
    return selected
