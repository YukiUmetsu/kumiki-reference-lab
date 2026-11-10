"""Decode selected original video frames as bounded gray/RGB pixel planes.

Selection uses decoded source-frame ordinals; presentation timestamps are
reverified against FFprobe's actual PTS, never reconstructed from nominal FPS.
"""

from __future__ import annotations

import re
import subprocess
from fractions import Fraction
from pathlib import Path

from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.core.timebase import parse_rational


_PTS = re.compile(r"\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:")
_TIMEBASE = re.compile(r"config in time_base:\s*(\d+/\d+)")


def read_gray_frames(
    path: Path, stream_index: int, ordinals: list[int], expected_pts: list[int],
    *, timebase: Fraction, seconds: int, width: int = 160, height: int = 90,
    ffmpeg: str = "ffmpeg",
) -> list[bytes]:
    return _read_pixel_frames(path, stream_index, ordinals, expected_pts,
                              timebase=timebase, seconds=seconds,
                              width=width, height=height, ffmpeg=ffmpeg,
                              pixel_format="gray", channels=1)


def read_rgb_frames(
    path: Path, stream_index: int, ordinals: list[int], expected_pts: list[int],
    *, timebase: Fraction, seconds: int, width: int = 160, height: int = 90,
    ffmpeg: str = "ffmpeg",
) -> list[bytes]:
    """Decode FFmpeg-converted 8-bit RGB, not calibrated scene-linear color."""
    return _read_pixel_frames(path, stream_index, ordinals, expected_pts,
                              timebase=timebase, seconds=seconds,
                              width=width, height=height, ffmpeg=ffmpeg,
                              pixel_format="rgb24", channels=3)


def _read_pixel_frames(
    path: Path, stream_index: int, ordinals: list[int], expected_pts: list[int],
    *, timebase: Fraction, seconds: int, width: int, height: int,
    ffmpeg: str, pixel_format: str, channels: int,
) -> list[bytes]:
    if (pixel_format, channels) not in (("gray", 1), ("rgb24", 3)):
        raise ValueError("unsupported pixel output format")
    if type(seconds) is not int or not 1 <= seconds <= 120:
        raise ValueError("decoded source prefix must be between 1 and 120 seconds")
    if (type(width) is not int or type(height) is not int or
            not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("motion analysis resolution is out of range")
    if not ordinals or len(ordinals) > 120 or ordinals != sorted(set(ordinals)):
        raise ValueError("motion frame ordinals must be unique, sorted and bounded")
    if any(type(value) is not int or value < 0 for value in ordinals):
        raise ValueError("invalid motion frame ordinal")
    if len(expected_pts) != len(ordinals):
        raise ValueError("frame ordinals and expected PTS count differ")
    if type(stream_index) is not int or stream_index < 0:
        raise ValueError("stream_index must be nonnegative")
    if timebase <= 0:
        raise ValueError("expected timebase must be positive")

    selector = "+".join(f"eq(n,{index})" for index in ordinals)
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "info", "-nostdin", "-t", str(seconds),
        "-i", str(path.resolve()), "-map", f"0:{stream_index}",
        "-vf", f"select='{selector}',scale={width}:{height}:flags=bicubic,format={pixel_format},showinfo",
        "-an", "-fps_mode", "passthrough", "-pix_fmt", pixel_format,
        "-f", "rawvideo", "-",
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=min(120, seconds * 3 + 20), check=False,
        )
    except FileNotFoundError as exc:
        raise ProbeError("ffmpeg executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("motion frame decoding timed out") from exc
    except OSError as exc:
        raise ProbeError("motion frame decoder could not start") from exc
    if completed.returncode != 0:
        raise ProbeError(f"motion frame decoder failed (exit code {completed.returncode})")
    if len(completed.stderr) > 8_000_000:
        raise ProbeError("motion frame decoder log exceeded budget")

    reported_pts: list[int] = []
    reported_timebases: set[Fraction] = set()
    for line in completed.stderr.decode("utf-8", errors="replace").splitlines():
        if "Parsed_showinfo" not in line:
            continue
        match = _TIMEBASE.search(line)
        if match:
            parsed = parse_rational(match.group(1))
            if parsed is None:
                raise ProbeError("motion filter reported invalid timebase")
            reported_timebases.add(parsed)
        elif " n:" in line:
            match = _PTS.search(line)
            if match is None:
                raise ProbeError("motion filter reported invalid frame PTS")
            reported_pts.append(int(match.group(1)))
    if reported_timebases != {timebase}:
        raise ProbeError("motion decoder changed or omitted source timebase")
    if reported_pts != expected_pts:
        raise ProbeError("motion decoded-frame timestamps do not match FFprobe")

    plane_size = width * height * channels
    if len(completed.stdout) != plane_size * len(ordinals):
        raise ProbeError("motion decoder produced unexpected pixel-buffer size")
    return [completed.stdout[i * plane_size:(i + 1) * plane_size]
            for i in range(len(ordinals))]
