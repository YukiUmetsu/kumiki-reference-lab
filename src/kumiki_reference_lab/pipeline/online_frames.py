"""Sequential source-frame decoding with measured animation/color-change evidence.

Processes every decoded frame within explicit duration/frame budgets; never writes
frames to disk. FFmpeg showinfo PTS are validated against the decoded frame count.
"""
from __future__ import annotations

import math
import random
import re
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged

SCHEMA_VERSION = "kumiki.online-frame-evidence.v1"
_PTS = re.compile(r"\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:")
_TIMEBASE = re.compile(r"config in time_base:\s*(\d+)/(\d+)")


def frame_metrics(rgb: bytes, *, width: int, height: int) -> dict[str, Any]:
    """Deterministic display-RGB proxies, not physical lighting or font recognition."""
    if len(rgb) != width * height * 3:
        raise ValueError("decoded frame buffer size mismatch")
    luma = sat = red = green = blue = bright = dark = 0.0
    count = 0
    # Uniform grid of approximately 2,600 pixels, regardless of decode size.
    pixel_stride = max(1, width * height // 2600)
    for i in range(0, len(rgb), pixel_stride * 3):
        r, g, b = rgb[i], rgb[i + 1], rgb[i + 2]
        y = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        luma += y
        sat += (max(r, g, b) - min(r, g, b)) / max(1, max(r, g, b))
        red += r
        green += g
        blue += b
        bright += int(y >= .85)
        dark += int(y <= .15)
        count += 1
    return {
        "meanRgb": [round(v / (count * 255.0), 5) for v in (red, green, blue)],
        "displayLumaProxy": round(luma / count, 5),
        "saturationProxy": round(sat / count, 5),
        "brightPixelFraction": round(bright / count, 5),
        "darkPixelFraction": round(dark / count, 5),
    }


def frame_change(previous: bytes, current: bytes, *, width: int, height: int) -> dict[str, float]:
    if len(previous) != len(current) or len(current) != width * height * 3:
        raise ValueError("frame comparison size mismatch")
    stride = max(1, width * height // 2600) * 3
    total = changed = count = 0
    for i in range(0, len(current), stride):
        change = (abs(current[i] - previous[i]) +
                  abs(current[i + 1] - previous[i + 1]) +
                  abs(current[i + 2] - previous[i + 2])) / (3 * 255)
        total += change
        changed += int(change >= .12)
        count += 1
    return {
        "meanPixelDelta": round(total / count, 5),
        "changedPixelFraction": round(changed / count, 5),
    }


def _read_frame(pipe: Any, size: int) -> bytes:
    pieces = []
    remaining = size
    while remaining:
        data = pipe.read(remaining)
        if not data:
            break
        pieces.append(data)
        remaining -= len(data)
    if remaining and pieces:
        raise ValueError("FFmpeg returned an incomplete decoded RGB frame")
    return b"".join(pieces)


def analyze_all_frames(
    source: Path, *, max_seconds: int = 180, max_frames: int = 10800,
    width: int = 192, height: int = 108, semantic_stride: int = 24,
    max_semantic_frames: int = 24, cut_threshold: float = .28,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    frame_sink: Callable[[int, bytes], None] | None = None,
) -> tuple[dict[str, Any], list[tuple[int, bytes]]]:
    """Stream source frames and return numeric evidence plus bounded PNG proposals.

    'All frames' means all frames decoded WITHIN the requested resource limits,
    not all frames of an arbitrarily long hosted film. The report marks truncation.
    """
    if (type(max_seconds) is not int or not 1 <= max_seconds <= 3600 or
            type(max_frames) is not int or not 2 <= max_frames <= 108000 or
            type(width) is not int or not 64 <= width <= 320 or
            type(height) is not int or not 36 <= height <= 180 or
            type(semantic_stride) is not int or not 1 <= semantic_stride <= 1800 or
            type(max_semantic_frames) is not int or not 0 <= max_semantic_frames <= 120 or
            type(cut_threshold) not in (float, int) or
            not math.isfinite(cut_threshold) or not 0 < cut_threshold < 1):
        raise ValueError("invalid frame-decoder resource budgets")
    if not source.is_file() or source.is_symlink():
        raise ValueError("source must be a regular local file")
    signature = file_signature(source)
    metadata = inspect_source(source, ffprobe=ffprobe)
    pixels = width * height * 3
    command = [
        ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "info",
        "-i", str(source.resolve()), "-map", f"0:{metadata['video']['streamIndex']}", "-an", "-sn", "-dn",
        "-t", str(max_seconds), "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,showinfo",
        "-vsync", "0", "-frames:v", str(max_frames),
        "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1",
    ]
    measured: list[dict[str, Any]] = []
    visual_samples: list[tuple[int, bytes]] = []
    eligible_seen = 0
    candidate_capacity = max(0, max_semantic_frames - 2)
    selector = random.Random(int(metadata["source"]["sha256"][:16], 16))
    last: bytes | None = None
    with tempfile.TemporaryFile(mode="w+b") as log:
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=log)
        except (FileNotFoundError, OSError) as exc:
            raise ValueError("FFmpeg could not start") from exc
        try:
            assert process.stdout is not None
            while True:
                frame = _read_frame(process.stdout, pixels)
                if not frame:
                    break
                position = len(measured)
                metrics = frame_metrics(frame, width=width, height=height)
                delta = frame_change(last, frame, width=width, height=height) if last else None
                cut = bool(delta and delta["meanPixelDelta"] >= cut_threshold)
                measured.append({
                    "frameIndex": position, "appearance": metrics,
                    "changeFromPrevious": delta,
                    "cutCandidate": cut,
                })
                # Deterministic reservoir of eligible keyframes across the
                # ENTIRE decoded duration; do not exhaust the budget in the
                # first seconds. First and last frames are always represented.
                sample_png: bytes | None = None
                if frame_sink is not None:
                    sample_png = _png_rgb(frame, width, height)
                    frame_sink(position, sample_png)
                if max_semantic_frames and position == 0:
                    visual_samples.append((position, sample_png if sample_png is not None
                                           else _png_rgb(frame, width, height)))
                elif candidate_capacity and (position % semantic_stride == 0 or cut):
                    eligible_seen += 1
                    if len(visual_samples) - 1 < candidate_capacity:
                        visual_samples.append((position, sample_png if sample_png is not None
                                               else _png_rgb(frame, width, height)))
                    else:
                        slot = selector.randrange(eligible_seen)
                        if slot < candidate_capacity:
                            visual_samples[1 + slot] = (
                                position, sample_png if sample_png is not None
                                else _png_rgb(frame, width, height))
                last = frame
            process.stdout.close()
            try:
                return_code = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise ValueError("FFmpeg did not exit after decoding")
            if return_code:
                raise ValueError("FFmpeg frame decoding failed")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        if not measured:
            raise ValueError("decoded media contained no video frames")
        log.seek(0, 2)
        log_size = log.tell()
        if log_size > 48_000_000:
            raise ValueError("FFmpeg frame timing log exceeded size cap")
        log.seek(0)
        diagnostics = log.read().decode("utf-8", errors="replace")
    pts = [(int(n), int(tick)) for n, tick in _PTS.findall(diagnostics)]
    if len(pts) != len(measured) or any(n != i for i, (n, _) in enumerate(pts)):
        raise ValueError("FFmpeg source-frame PTS could not be matched to decoded frames")
    timebase_match = _TIMEBASE.search(diagnostics)
    if not timebase_match:
        raise ValueError("FFmpeg did not report the frame presentation timebase")
    tb = Fraction(int(timebase_match.group(1)), int(timebase_match.group(2)))
    if tb <= 0:
        raise ValueError("invalid decoded frame presentation timebase")
    original_tb_json = metadata["video"]["sourceTimebase"]
    original_tb = Fraction(original_tb_json["numerator"], original_tb_json["denominator"])
    for row, (_, tick) in zip(measured, pts, strict=True):
        row["decodedPts"] = tick
        row["decodedSeconds"] = round(float(tick * tb), 6)
    if any(pts[i][1] <= pts[i - 1][1] for i in range(1, len(pts))):
        raise ValueError("decoded frame timestamps are not strictly increasing")
    require_unchanged(source, signature)
    if (max_semantic_frames >= 2 and len(measured) > 1 and
            all(i != len(measured) - 1 for i, _ in visual_samples)):
        assert last is not None
        visual_samples.append((len(measured) - 1, _png_rgb(last, width, height)))
    visual_samples.sort(key=lambda item: item[0])
    raw_duration = metadata["video"]["durationSecondsReported"]
    try:
        duration = float(raw_duration) if raw_duration is not None else None
    except (TypeError, ValueError):
        duration = None
    last_seconds = measured[-1]["decodedSeconds"]
    evidence = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": metadata["source"]["sha256"],
        "video": metadata["video"],
        "frameCount": len(measured),
        "decoderTimebase": {"numerator": tb.numerator, "denominator": tb.denominator},
        "decoderTimebaseMatchesSource": tb == original_tb,
        "timestampStatus": "ffmpeg-showinfo-decoder-pts-not-independently-source-verified",
        "analysisWindow": {
            "startSeconds": 0, "requestedMaxSeconds": max_seconds,
            "requestedMaxFrames": max_frames,
            "lastDecodedSeconds": last_seconds,
            "reportedSourceDurationSeconds": duration,
            "completeVideo": bool(duration is not None and
                                  duration < max_seconds and len(measured) < max_frames),
        },
        "cutCandidateFrameIndices": [row["frameIndex"] for row in measured
                                     if row["cutCandidate"]],
        "frames": measured,
        "limits": [
            "Display color/luminance are uncalibrated proxies.",
            "Frame differences combine foreground animation, camera motion and edits.",
            "Cut candidates are thresholds, not verified edit decisions.",
            "Video is decoded sequentially without dropping frames within configured budgets.",
            "Decoder PTS are not independently verified original packet timestamps.",
        ],
    }
    return evidence, visual_samples
