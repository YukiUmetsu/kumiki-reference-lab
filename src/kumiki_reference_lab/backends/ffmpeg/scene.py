"""FFmpeg hard-cut candidate detection via the built-in scene comparison filter.

The filter does not expose an exact light/camera model and can mistake fast
action for an edit. Results are candidates, never automatic artistic truth.
"""

from __future__ import annotations

import math
import re
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.core.timebase import parse_rational


_SHOWINFO_PTS = re.compile(r"\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:")
_SHOWINFO_TIMEBASE = re.compile(r"config in time_base:\s*(\d+/\d+)")


@dataclass(frozen=True)
class CutScan:
    timebase: Fraction
    pts: tuple[int, ...]


def detect_hard_cut_pts(
    path: Path, stream_index: int, *, seconds: int = 60,
    threshold: float = 0.25, ffmpeg: str = "ffmpeg",
) -> CutScan:
    if type(seconds) is not int or not 1 <= seconds <= 120:
        raise ValueError("seconds must be between 1 and 120")
    if type(stream_index) is not int or stream_index < 0:
        raise ValueError("stream_index must be nonnegative")
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("threshold must be finite and between 0 and 1")

    command = [
        ffmpeg, "-hide_banner", "-loglevel", "info", "-nostdin",
        # Input-side -t bounds decoding even if zero output frames are selected.
        "-t", str(seconds), "-i", str(path.resolve()),
        "-map", f"0:{stream_index}",
        "-vf", f"select='gt(scene,{threshold:.17g})',showinfo",
        "-an", "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=min(180, seconds * 3 + 20), check=False,
        )
    except FileNotFoundError as exc:
        raise ProbeError("ffmpeg executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("ffmpeg cut detection timed out") from exc
    except OSError as exc:
        raise ProbeError("ffmpeg cut detection could not start") from exc

    if result.returncode:
        raise ProbeError(f"ffmpeg cut detection failed (exit code {result.returncode})")
    if len(result.stderr) > 8_000_000:
        raise ProbeError("cut detection output exceeded the bounded scan")

    selected: list[int] = []
    reported_timebases: set[Fraction] = set()
    for line in result.stderr.splitlines():
        if "Parsed_showinfo" not in line:
            continue
        match_timebase = _SHOWINFO_TIMEBASE.search(line)
        if match_timebase is not None:
            timebase = parse_rational(match_timebase.group(1))
            if timebase is None:
                raise ProbeError("cut filter reported an invalid timebase")
            reported_timebases.add(timebase)
        if " n:" not in line:
            continue
        match = _SHOWINFO_PTS.search(line)
        if match is None:
            raise ProbeError("selected cut candidate lacked a valid source PTS")
        selected.append(int(match.group(1)))
    if len(reported_timebases) != 1:
        raise ProbeError("cut filter did not expose one unambiguous timebase")
    return CutScan(next(iter(reported_timebases)), tuple(selected))
