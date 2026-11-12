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

# Documented quality flags. Each threshold is deliberately conservative: a
# flag records a measured shape (near-black, flat, single-bucket), never a
# judgement about the work, the poster's intent, or its authorship.
STILL_FLAG_NEAR_BLACK = "near-black-placeholder"
STILL_FLAG_NEAR_WHITE = "near-white-placeholder"
STILL_FLAG_NEAR_UNIFORM = "near-uniform"
STILL_FLAG_DEGENERATE_HISTOGRAM = "degenerate-histogram"
STILL_FLAG_LOW_RESOLUTION = "low-information-resolution"
STILL_QUALITY_FLAGS = (
    STILL_FLAG_NEAR_BLACK, STILL_FLAG_NEAR_WHITE, STILL_FLAG_NEAR_UNIFORM,
    STILL_FLAG_DEGENERATE_HISTOGRAM, STILL_FLAG_LOW_RESOLUTION,
)
# Flags that are strong enough to treat a poster as non-evidence rather than
# a usable frame. ``near-uniform`` and ``low-information-resolution`` stay
# usable-but-flagged: a flat title card or a small poster can still be a real
# published still.
STILL_NON_EVIDENCE_FLAGS = frozenset({
    STILL_FLAG_NEAR_BLACK, STILL_FLAG_NEAR_WHITE,
    STILL_FLAG_DEGENERATE_HISTOGRAM,
})

STILL_NEAR_BLACK_LUMA = 0.05
STILL_NEAR_WHITE_LUMA = 0.97
STILL_NEAR_NEUTRAL_SATURATION = 0.02
STILL_NEAR_UNIFORM_STDDEV = 0.01
STILL_DEGENERATE_BUCKET_SHARE = 0.99
STILL_LOW_INFORMATION_PIXELS = 100_000

__all__ = [
    "STILL_DECODE_HEIGHT", "STILL_DECODE_WIDTH", "STILL_MAX_BYTES",
    "STILL_METHOD", "STILL_NON_EVIDENCE_FLAGS", "STILL_QUALITY_FLAGS",
    "build_still_evidence", "compute_still_metrics", "decode_still_rgb",
    "dominant_hue_family", "infer_decoded_dimensions", "measure_still",
    "probe_image_dimensions", "still_has_quality_flags", "still_image_format",
    "still_quality_counts", "still_quality_flags", "still_quality_summary",
    "still_record_flags",
]


def _metric_number(metrics: dict[str, Any], key: str) -> float | None:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def still_quality_flags(
    metrics: dict, *, width: int | None = None, height: int | None = None,
) -> list[str]:
    """Sorted quality *flags* for one still's stored metrics.

    These are flags, not verdicts: the record keeps the measured numbers and
    each consumer decides whether a flag disqualifies the still for its use.
    A clean still returns ``[]``.

    - ``near-black-placeholder``: mean luma < 0.05 and saturation < 0.02.
    - ``near-white-placeholder``: mean luma > 0.97 and saturation < 0.02.
    - ``near-uniform``: ``displayLumaStdDev`` < 0.01.
    - ``degenerate-histogram``: one luma bucket holds > 0.99 of pixels.
    - ``low-information-resolution``: width x height < 100,000 when both are
      supplied. The source image's pixel count is used; the decode size is
      always 160x90 and is not the measurement being flagged.
    """
    if not isinstance(metrics, dict):
        raise ValueError("still metrics must be a mapping")
    flags: set[str] = set()
    luma = _metric_number(metrics, "meanDisplayLumaProxy")
    saturation = _metric_number(metrics, "meanSaturationProxy")
    if luma is not None and saturation is not None:
        if (luma < STILL_NEAR_BLACK_LUMA
                and saturation < STILL_NEAR_NEUTRAL_SATURATION):
            flags.add(STILL_FLAG_NEAR_BLACK)
        if (luma > STILL_NEAR_WHITE_LUMA
                and saturation < STILL_NEAR_NEUTRAL_SATURATION):
            flags.add(STILL_FLAG_NEAR_WHITE)
    deviation = _metric_number(metrics, "displayLumaStdDev")
    if deviation is not None and deviation < STILL_NEAR_UNIFORM_STDDEV:
        flags.add(STILL_FLAG_NEAR_UNIFORM)
    histogram = metrics.get("lumaHistogram")
    if isinstance(histogram, (list, tuple)) and histogram:
        shares = [float(value) for value in histogram
                  if isinstance(value, (int, float))
                  and not isinstance(value, bool)
                  and math.isfinite(value)]
        if any(share > STILL_DEGENERATE_BUCKET_SHARE for share in shares):
            flags.add(STILL_FLAG_DEGENERATE_HISTOGRAM)
    if (type(width) is int and type(height) is int
            and width > 0 and height > 0
            and width * height < STILL_LOW_INFORMATION_PIXELS):
        flags.add(STILL_FLAG_LOW_RESOLUTION)
    return sorted(flags)


def still_record_flags(record: dict) -> list[str]:
    """Read ``still.qualityFlags`` from one evidence record, defensively."""
    if not isinstance(record, dict):
        return []
    still = record.get("still")
    if not isinstance(still, dict):
        return []
    flags = still.get("qualityFlags")
    if not isinstance(flags, list):
        return []
    return sorted({flag for flag in flags
                   if isinstance(flag, str) and flag.strip()})


def still_has_quality_flags(record: dict) -> bool:
    """True when a still record carries at least one quality flag."""
    return bool(still_record_flags(record))


def still_quality_counts(records: Iterable[dict]) -> dict[str, int]:
    """Count still records per documented quality flag (zeroes included)."""
    counts = {flag: 0 for flag in STILL_QUALITY_FLAGS}
    for record in records:
        for flag in still_record_flags(record):
            counts[flag] = counts.get(flag, 0) + 1
    return {flag: counts[flag] for flag in sorted(counts)}


def still_quality_summary(records: Iterable[dict]) -> dict[str, Any]:
    """Shared, report-ready still-quality block for every site adapter."""
    materialised = list(records)
    counts = still_quality_counts(materialised)
    flagged = sum(1 for record in materialised if still_has_quality_flags(record))
    return {
        "flags": counts,
        "flagged": flagged,
        "evidence": len(materialised) - flagged,
        "excludedFromColourAggregates": True,
        "note": ("quality flags are measurements, not verdicts; flagged stills "
                 "are counted here and excluded from colour aggregates"),
    }


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


def _quality_flag_list(quality_flags: Iterable[str] | None) -> list[str]:
    if quality_flags is None:
        return []
    if (isinstance(quality_flags, str)
            or not isinstance(quality_flags, (list, tuple))):
        raise ValueError("quality flags must be a list of strings")
    flags: list[str] = []
    for flag in quality_flags:
        if not isinstance(flag, str) or not flag.strip():
            raise ValueError("quality flags must be non-empty strings")
        if flag not in flags:
            flags.append(flag)
    return flags


def build_still_evidence(
    *, still: dict[str, Any], schema_version: str, evidence_status: str,
    limits: Iterable[str], coverage_note: str,
    method: str = STILL_METHOD, is_source_video_frame: bool = False,
    quality_flags: list[str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble the neutral still evidence payload (no subject identity fields).

    The caller merges its own subject fields and supplies the schema, status,
    limits, and the coverage note that explains what the still represents.
    Image bytes are never retained: ``imageRetained`` is fixed ``False``.
    ``quality_flags`` (see :func:`still_quality_flags`) is stored as
    ``still.qualityFlags``; it is always present and ``[]`` for a clean still.
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
    flags = _quality_flag_list(quality_flags)
    return {
        "schemaVersion": schema_version,
        "still": {**still, "qualityFlags": flags},
        "acquisition": {"method": method, "imageRetained": False},
        "coverage": {
            "isSourceVideoFrame": is_source_video_frame,
            "note": coverage_note,
        },
        "evidenceStatus": evidence_status,
        "limits": list(limits),
        "generatedAt": generated_at or utc_now(),
    }
