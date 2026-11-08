"""Exact timebase arithmetic; never infer source frame timestamps from FPS."""

from __future__ import annotations

from fractions import Fraction
from typing import Any


def parse_rational(value: Any) -> Fraction | None:
    """Parse ffprobe's numerator/denominator strings, including unknown 0/0."""
    if not isinstance(value, str) or not value or value == "N/A":
        return None
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return result if result > 0 else None


def as_rational_dict(value: Fraction | None) -> dict[str, int] | None:
    if value is None:
        return None
    return {"numerator": value.numerator, "denominator": value.denominator}


def presentation_seconds(pts: int, timebase: Fraction) -> Fraction:
    """Exact original presentation timestamp, not an inferred frame index."""
    if not isinstance(pts, int) or isinstance(pts, bool):
        raise TypeError("pts must be an integer timestamp")
    if timebase <= 0:
        raise ValueError("timebase must be positive")
    return pts * timebase


def map_pts_to_frame(
    pts: int, timebase: Fraction, output_fps: Fraction, *, origin_pts: int = 0
) -> int:
    """Nearest-frame mapping using exact arithmetic (half away from zero).

    This is a mapping for a chosen output clock, not a replacement for source PTS.
    VFR streams may map multiple source frames onto one output frame.
    """
    if output_fps <= 0:
        raise ValueError("output_fps must be positive")
    scaled = presentation_seconds(pts - origin_pts, timebase) * output_fps
    magnitude = abs(scaled)
    nearest = (2 * magnitude.numerator + magnitude.denominator) // (
        2 * magnitude.denominator
    )
    return nearest if scaled >= 0 else -nearest
