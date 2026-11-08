"""Extract selected decoded frames without manufacturing frame times from FPS."""

from __future__ import annotations

import re
import subprocess
from fractions import Fraction
from pathlib import Path

from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.core.timebase import parse_rational


_SHOWINFO_PTS = re.compile(r"\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:")
_SHOWINFO_TIMEBASE = re.compile(r"config in time_base:\s*(\d+/\d+)")


def extract_thumbnails(
    source: Path, destination: Path, stream_index: int,
    selected_ordinals: list[int], *, seconds: int, width: int,
    expected_timebase: Fraction, expected_pts: list[int], ffmpeg: str = "ffmpeg",
) -> list[Path]:
    """Decode a bounded prefix, select source ordinals, and verify exact PTS.

    The caller owns destination (a private staging directory).  `select` is
    followed by `showinfo` before scaling, preserving the input stream clock.
    """
    if not 1 <= seconds <= 120 or not 128 <= width <= 800:
        raise ValueError("invalid thumbnail scan budget or width")
    if not selected_ordinals or selected_ordinals != sorted(set(selected_ordinals)):
        raise ValueError("selected frame ordinals must be sorted and unique")
    if any(type(i) is not int or i < 0 for i in selected_ordinals):
        raise ValueError("invalid selected frame ordinal")
    if len(selected_ordinals) != len(expected_pts) or len(selected_ordinals) > 24:
        raise ValueError("thumbnail count exceeds limit or expected PTS count")
    if not destination.is_dir():
        raise ValueError("destination must be an existing staging directory")

    expression = "+".join(f"eq(n,{ordinal})" for ordinal in selected_ordinals)
    filtergraph = f"select='{expression}',showinfo,scale={width}:-2"
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "info", "-nostdin", "-y",
        "-t", str(seconds), "-i", str(source.resolve()), "-map", f"0:{stream_index}",
        "-vf", filtergraph, "-an", "-fps_mode", "passthrough", "-q:v", "3",
        "-start_number", "0", str(destination / "frame-%03d.jpg"),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=min(180, seconds * 3 + 20), check=False,
        )
    except FileNotFoundError as exc:
        raise ProbeError("ffmpeg executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("thumbnail decoding timed out") from exc
    except OSError as exc:
        raise ProbeError("thumbnail decoding could not start") from exc
    if result.returncode:
        raise ProbeError(f"thumbnail decoding failed (exit code {result.returncode})")
    if len(result.stderr) > 8_000_000:
        raise ProbeError("thumbnail decoding log exceeded the scan budget")

    pts: list[int] = []
    timebases: set[Fraction] = set()
    for line in result.stderr.splitlines():
        if "Parsed_showinfo" not in line:
            continue
        match = _SHOWINFO_TIMEBASE.search(line)
        if match:
            timebase = parse_rational(match.group(1))
            if timebase is None:
                raise ProbeError("thumbnail filter reported invalid timebase")
            timebases.add(timebase)
        elif " n:" in line:
            match = _SHOWINFO_PTS.search(line)
            if match is None:
                raise ProbeError("thumbnail filter reported an invalid PTS")
            pts.append(int(match.group(1)))
    if timebases != {expected_timebase}:
        raise ProbeError("thumbnail filter changed or omitted source timebase")
    if pts != expected_pts:
        raise ProbeError("decoded thumbnail PTS did not match the source frame timeline")

    paths = [destination / f"frame-{i:03d}.jpg" for i in range(len(expected_pts))]
    if not all(path.is_file() and path.stat().st_size > 0 for path in paths):
        raise ProbeError("thumbnail decoder did not produce every expected image")
    if len(list(destination.glob("frame-*.jpg"))) != len(paths):
        raise ProbeError("thumbnail decoder wrote unexpected extra images")
    return paths
