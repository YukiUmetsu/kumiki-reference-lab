"""Published-still probing, decoding, and numeric measurement.

The base six metrics reuse the repository's canonical ``_frame_metrics`` so a
still and a decoded video frame are measured with identical formulas. The
additional still-only metrics (luma histogram, dominant hue family, edge
density proxy) are defined here.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from kumiki_reference_lab.analyzers.appearance.source_visual_probe import (
    _frame_metrics,
)

from .probe import probe_image_dimensions
from .store import utc_now

STILL_MAX_BYTES = 16 * 1024 * 1024
STILL_DECODE_WIDTH = 160
STILL_DECODE_HEIGHT = 90
STILL_METHOD = "poster-still-http"

__all__ = [
    "STILL_DECODE_HEIGHT", "STILL_DECODE_WIDTH", "STILL_MAX_BYTES",
    "STILL_METHOD", "build_still_evidence", "compute_still_metrics",
    "decode_still_rgb", "dominant_hue_family", "infer_decoded_dimensions",
    "measure_still", "probe_image_dimensions", "still_image_format",
]


def still_image_format(url: str, codec: str | None) -> str:
    """Best-effort image format label from the probed codec or the URL suffix."""
    if isinstance(codec, str) and codec.strip():
        label = codec.strip().lower()
    else:
        label = Path(urlsplit(url).path).suffix.lower().lstrip(".")
    if label == "mjpeg":
        return "jpg"
    return label or "unknown"


def decode_still_rgb(
    path: Path, *, ffmpeg: str = "ffmpeg",
    width: int = STILL_DECODE_WIDTH, height: int = STILL_DECODE_HEIGHT,
    timeout: float = 60.0,
) -> bytes:
    """Decode one bounded RGB plane from the still, preserving its aspect ratio."""
    command = [
        ffmpeg, "-hide_banner", "-v", "error", "-nostdin", "-i", str(path),
        "-frames:v", "1",
        "-vf", (f"scale={width}:{height}:"
                "force_original_aspect_ratio=decrease,format=rgb24"),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError as error:
        raise ValueError("ffmpeg is not installed locally") from error
    except subprocess.TimeoutExpired as error:
        raise ValueError("still image decode exceeded the bounded timeout") from error
    except OSError as error:
        raise ValueError("still image decoder could not start") from error
    if completed.returncode != 0:
        raise ValueError(
            f"still image decode failed (exit {completed.returncode})")
    if not completed.stdout:
        raise ValueError("still image decode produced no pixels")
    return completed.stdout


def infer_decoded_dimensions(
    byte_length: int, source_width: int, source_height: int, *,
    max_width: int = STILL_DECODE_WIDTH,
    max_height: int = STILL_DECODE_HEIGHT,
) -> tuple[int, int]:
    """Recover the exact scaled width/height from the raw RGB byte count.

    ``force_original_aspect_ratio=decrease`` keeps the aspect ratio, so the
    buffer length alone under-determines the dimensions; the candidate closest
    to the source aspect ratio is the real one.
    """
    if byte_length <= 0 or byte_length % 3:
        raise ValueError("decoded still buffer is not a whole number of RGB pixels")
    if source_width <= 0 or source_height <= 0:
        raise ValueError("source still dimensions must be positive")
    pixels = byte_length // 3
    target_aspect = source_width / source_height
    best: tuple[float, int, int] | None = None
    for width in range(2, max_width + 1):
        if pixels % width:
            continue
        height = pixels // width
        if not 2 <= height <= max_height:
            continue
        error = abs(math.log((width / height) / target_aspect))
        if best is None or error < best[0]:
            best = (error, width, height)
    if best is None:
        raise ValueError("could not infer decoded still dimensions")
    return best[1], best[2]


def dominant_hue_family(mean_rgb: Iterable[float]) -> str:
    """Bucket a mean RGB triple into one coarse HSV hue family."""
    values = list(mean_rgb)
    if len(values) < 3:
        raise ValueError("hue family requires three mean RGB components")
    r, g, b = (float(value) for value in values[:3])
    top, bottom = max(r, g, b), min(r, g, b)
    if top <= 0.0:
        return "neutral"
    delta = top - bottom
    if delta / top < 0.12:
        return "neutral"
    if top == r:
        hue = 60.0 * (((g - b) / delta) % 6.0)
    elif top == g:
        hue = 60.0 * (((b - r) / delta) + 2.0)
    else:
        hue = 60.0 * (((r - g) / delta) + 4.0)
    hue %= 360.0
    if hue < 15.0 or hue >= 345.0:
        return "red"
    if hue < 45.0:
        return "orange"
    if hue < 75.0:
        return "yellow"
    if hue < 165.0:
        return "green"
    if hue < 195.0:
        return "cyan"
    if hue < 255.0:
        return "blue"
    if hue < 285.0:
        return "purple"
    return "magenta"


def compute_still_metrics(
    rgb: bytes, *, width: int, height: int,
) -> dict[str, Any]:
    """Full-frame still metrics on one decoded 8-bit RGB buffer.

    - ``lumaHistogram``: five equal luma buckets (0..1), stored as fractions.
    - ``dominantHueFamily``: HSV hue of the mean RGB, bucketed coarsely.
    - ``edgeDensityProxy``: mean absolute horizontal+vertical neighbour luma
      difference over 0..1, a texture/detail indicator (not a sharpness score).
    """
    base = _frame_metrics(rgb, width=width, height=height)
    pixels = width * height
    luma = [0.0] * pixels
    histogram = [0, 0, 0, 0, 0]
    for index in range(pixels):
        r, g, b = rgb[3 * index], rgb[3 * index + 1], rgb[3 * index + 2]
        value = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        luma[index] = value
        bucket = min(4, int(value * 5.0))
        histogram[bucket] += 1
    difference = 0.0
    comparisons = 0
    for y in range(height):
        row = y * width
        for x in range(width):
            value = luma[row + x]
            if x + 1 < width:
                difference += abs(value - luma[row + x + 1])
                comparisons += 1
            if y + 1 < height:
                difference += abs(value - luma[row + width + x])
                comparisons += 1
    return {
        **base,
        "lumaHistogram": [round(count / pixels, 6) for count in histogram],
        "dominantHueFamily": dominant_hue_family(base["meanRgb"]),
        "edgeDensityProxy": (round(difference / comparisons, 6)
                             if comparisons else 0.0),
    }


def measure_still(
    path: Path, *, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Measure one already-downloaded still; the caller deletes the file."""
    dimensions = probe_image_dimensions(path, ffprobe=ffprobe)
    rgb = decode_still_rgb(path, ffmpeg=ffmpeg)
    width, height = infer_decoded_dimensions(
        len(rgb), dimensions["width"], dimensions["height"])
    return {
        "imageWidth": dimensions["width"],
        "imageHeight": dimensions["height"],
        "imageCodec": dimensions["codec"],
        "metrics": compute_still_metrics(rgb, width=width, height=height),
    }


def build_still_evidence(
    *, still: dict[str, Any], schema_version: str, evidence_status: str,
    limits: Iterable[str], coverage_note: str,
    method: str = STILL_METHOD, is_source_video_frame: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble the neutral still evidence payload (no subject identity fields).

    The caller merges its own subject fields and supplies the schema, status,
    limits, and the coverage note that explains what the still represents.
    Image bytes are never retained: ``imageRetained`` is fixed ``False``.
    """
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError("evidence schema version must be a non-empty string")
    if not isinstance(evidence_status, str) or not evidence_status.strip():
        raise ValueError("evidence status must be a non-empty string")
    if not isinstance(method, str) or not method.strip():
        raise ValueError("acquisition method must be a non-empty string")
    if not isinstance(coverage_note, str) or not coverage_note.strip():
        raise ValueError("coverage note must be a non-empty string")
    if not isinstance(is_source_video_frame, bool):
        raise ValueError("source-frame flag must be a boolean")
    return {
        "schemaVersion": schema_version,
        "still": still,
        "acquisition": {"method": method, "imageRetained": False},
        "coverage": {
            "isSourceVideoFrame": is_source_video_frame,
            "note": coverage_note,
        },
        "evidenceStatus": evidence_status,
        "limits": list(limits),
        "generatedAt": generated_at or utc_now(),
    }
