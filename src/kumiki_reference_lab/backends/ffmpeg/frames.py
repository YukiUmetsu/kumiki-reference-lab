"""Bounded FFprobe frame timestamp extraction; never uses nominal FPS as PTS."""

from __future__ import annotations

import subprocess
from pathlib import Path

from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.contracts.frames import FramePts


def read_frame_pts(
    path: Path, stream_index: int, *, seconds: int = 60,
    ffprobe: str = "ffprobe", max_frames: int = 20_000,
) -> list[FramePts]:
    if type(seconds) is not int or not 1 <= seconds <= 120:
        raise ValueError("seconds must be between 1 and 120")
    if type(stream_index) is not int or stream_index < 0:
        raise ValueError("stream_index must be nonnegative")
    if type(max_frames) is not int or max_frames < 1:
        raise ValueError("max_frames must be positive")

    command = [
        ffprobe, "-v", "error", "-select_streams", str(stream_index),
        "-read_intervals", f"%+{seconds}",
        "-show_frames", "-show_entries", "frame=pts,best_effort_timestamp",
        "-of", "compact=p=0:nk=0", "-i", str(path.resolve()),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=min(180, seconds * 3 + 20), check=False,
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
    return frames
