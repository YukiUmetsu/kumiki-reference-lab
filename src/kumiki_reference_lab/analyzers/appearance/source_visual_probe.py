"""Original-PTS source-frame visual proxies for systematic local film research.

Image motion/change and display RGB are NOT camera/lens, physical-lighting,
editing-intent, or aesthetic-style labels. No pretrained models required.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.motion.analyze import select_motion_samples
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames
from kumiki_reference_lab.backends.ffmpeg.scene import detect_hard_cut_pts
from kumiki_reference_lab.backends.ffmpeg.source_seek import (
    decode_rgb_source_pts_seek, detect_source_window_cuts_seek, probe_source_window,
)
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict
from kumiki_reference_lab.pipeline.ollama_character_perception import _VIDEO_EXTENSIONS

SCHEMA_VERSION = "kumiki.source-pts-visual-probe.v1"


def _frame_metrics(rgb: bytes, *, width: int, height: int) -> dict[str, Any]:
    """Full-frame deterministic 8-bit RGB statistics; no photometric calibration."""
    pixels = width*height
    if len(rgb) != pixels*3 or pixels < 64*36:
        raise ValueError("source-frame RGB buffer has wrong size")
    mean_r = mean_g = mean_b = 0
    luma_sum = luma_sq = saturation = 0.0
    bright = dark = 0
    for i in range(0, len(rgb), 3):
        r, g, b = rgb[i], rgb[i+1], rgb[i+2]
        mean_r += r
        mean_g += g
        mean_b += b
        luma = (0.2126*r + 0.7152*g + 0.0722*b)/255
        luma_sum += luma
        luma_sq += luma*luma
        if luma >= 0.85:
            bright += 1
        if luma <= 0.15:
            dark += 1
        top, bottom = max(r, g, b), min(r, g, b)
        saturation += (top-bottom)/top if top else 0.0
    mean_luma = luma_sum/pixels
    return {
        "meanRgb": [round(value/(pixels*255), 6)
                    for value in (mean_r, mean_g, mean_b)],
        "meanDisplayLumaProxy": round(mean_luma, 6),
        "displayLumaStdDev": round(math.sqrt(max(
            0.0, luma_sq/pixels - mean_luma*mean_luma)), 6),
        "meanSaturationProxy": round(saturation/pixels, 6),
        "shadowPixelFraction": round(dark/pixels, 6),
        "brightPixelFraction": round(bright/pixels, 6),
    }


def _frame_delta(before: bytes, after: bytes) -> float:
    if len(before) != len(after) or not before:
        raise ValueError("RGB comparison requires equal full frame buffers")
    return round(sum(abs(a-b) for a,b in zip(before, after, strict=True))
                 / (len(before)*255), 6)


def analyze_source_visual_window(
    source: Path, *, start_seconds: int = 0, seconds: int = 10,
    max_samples: int = 12, width: int = 160, height: int = 90,
    cut_threshold: float = .25, image_translation: bool = False,
    rights_status: str = "review-required",
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Inspect real source PTS, sampled RGB and cut candidates within a bounded window."""
    if (type(start_seconds) is not int or start_seconds < 0 or
            type(seconds) is not int or not 1 <= seconds <= 30 or
            start_seconds+seconds > 3600 or
            type(max_samples) is not int or not 5 <= max_samples <= 24 or
            type(width) is not int or not 64 <= width <= 320 or
            type(height) is not int or not 36 <= height <= 180 or
            type(cut_threshold) not in (float, int) or
            not math.isfinite(cut_threshold) or not 0 < cut_threshold < 1 or
            type(image_translation) is not bool):
        raise ValueError("source visual probe window, frame, or cut budgets invalid")
    if (source.is_symlink() or not source.is_file() or
            source.suffix.lower() not in _VIDEO_EXTENSIONS):
        raise ValueError("visual probe requires one authorized regular local video")
    signature = file_signature(source)
    media = inspect_source(source, rights_status=rights_status, ffprobe=ffprobe)
    stream = media["video"]["streamIndex"]
    tb_json = media["video"]["sourceTimebase"]
    timebase = Fraction(tb_json["numerator"],tb_json["denominator"])
    window_end = start_seconds+seconds
    if window_end > 120:
        seek = probe_source_window(
            source, stream, timebase=timebase,
            start_seconds=start_seconds, seconds=seconds, ffprobe=ffprobe,
        )
        sampled = select_motion_samples(list(seek.frames), max_samples)
        pts = [x.pts for x in sampled]
        frames_rgb = decode_rgb_source_pts_seek(
            source, stream, pts, window=seek,
            width=width, height=height, ffmpeg=ffmpeg)
        cuts = detect_source_window_cuts_seek(
            source, stream, window=seek,
            threshold=cut_threshold, ffmpeg=ffmpeg)
        decoder = "verified-seek-original-pts-v1"
        candidate_count = len(seek.frames)
    else:
        all_frames = read_frame_pts(
            source, stream, seconds=seconds, start_seconds=start_seconds,
            source_timebase=timebase, ffprobe=ffprobe,
        )
        sampled = select_motion_samples(all_frames, max_samples)
        pts = [int(x.pts) for x in sampled]
        frames_rgb = read_rgb_frames(
            source, stream, [x.ordinal for x in sampled], pts,
            timebase=timebase, seconds=window_end,
            width=width, height=height, ffmpeg=ffmpeg)
        cuts = detect_hard_cut_pts(
            source, stream, seconds=window_end, threshold=cut_threshold,
            ffmpeg=ffmpeg)
        decoder = "source-prefix-ordinal-pts-v1"
        candidate_count = len(all_frames)
    if cuts.timebase != timebase:
        raise ValueError("visual cut detection changed the original source timebase")
    # Filter out candidates from outside the requested interval (prefix scans
    # necessarily contain earlier cuts).
    first_pts = pts[0]
    last_pts = pts[-1]
    boundaries = sorted({
        p for p in cuts.pts if first_pts <= p <= last_pts
    })
    require_unchanged(source, signature)
    observations = [
        {"sourcePts": pts_value,
         "sourceSeconds": as_rational_dict(pts_value*timebase),
         "appearance": _frame_metrics(frame, width=width, height=height)}
        for pts_value, frame in zip(pts, frames_rgb, strict=True)
    ]
    planes = None
    if image_translation:
        # Optional reuse of the existing FFT phase-correlation code. A
        # grayscale global shift is only an image-plane motion hypothesis.
        from kumiki_reference_lab.analyzers.motion.phase import measure_image_shift
        planes = [
            bytes((77*frame[i] + 150*frame[i+1] + 29*frame[i+2])//256
                  for i in range(0, len(frame), 3))
            for frame in frames_rgb
        ]
    pairs: list[dict[str, Any]] = []
    for i in range(1, len(pts)):
        crossed = any(pts[i-1] < p <= pts[i] for p in boundaries)
        dt = Fraction(pts[i]-pts[i-1])*timebase
        if dt <= 0:
            raise ValueError("sampled video source PTS were nonmonotonic")
        value = None if crossed else _frame_delta(frames_rgb[i-1], frames_rgb[i])
        pair = {
            "startPts": pts[i-1], "endPts": pts[i],
            "sourceDeltaSeconds": as_rational_dict(dt),
            "status": "cut-candidate-between-samples" if crossed else "rgb-image-difference-proxy",
            "meanAbsoluteDisplayRgbDelta": value,
            "meanAbsoluteDisplayRgbDeltaPerSecond": (
                round(value/float(dt), 6) if value is not None else None),
        }
        if image_translation:
            if crossed:
                shift = {"status":"cut-boundary","dxPixels":None,
                         "dyPixels":None,"peakToSidelobeRatio":None}
            else:
                shift = measure_image_shift(
                    planes[i-1], planes[i], width, height)
            pair["imageTranslation"] = shift
        pairs.append(pair)
    within_shot = [x["meanAbsoluteDisplayRgbDelta"] for x in pairs
                   if x["meanAbsoluteDisplayRgbDelta"] is not None]
    brightnesses = [x["appearance"]["meanDisplayLumaProxy"] for x in observations]
    saturations = [x["appearance"]["meanSaturationProxy"] for x in observations]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": media["source"]["sha256"],
        "sourceStreamIndex": stream, "sourceTimebase": tb_json,
        "rightsStatus": media["source"]["rightsStatus"],
        "scan": {
            "startSeconds": start_seconds, "requestedSeconds": seconds,
            "sourceWindowEndSeconds": window_end,
            "decoder": decoder,
            "frameWidth": width, "frameHeight": height,
            "sourcePtsFramesSeenInInventory": candidate_count,
            "sampledSourcePtsCount": len(pts),
            "sampledPtsStart": first_pts,
            "sampledPtsEnd": last_pts,
            "cutThreshold": float(cut_threshold),
            "sourceTimebaseVerified": True,
        },
        "cutCandidatePts": boundaries,
        "sampledFrames": observations,
        "sampledFramePairs": pairs,
        "sampledWindowSummary": {
            "cutCandidateCountBetweenFirstAndLastSample": len(boundaries),
            "cutCandidateRatePerRequestedMinute": round(
                len(boundaries)*60/seconds, 6),
            "meanSampledDisplayLumaProxy": round(sum(brightnesses)/len(brightnesses), 6),
            "meanSampledSaturationProxy": round(sum(saturations)/len(saturations), 6),
            "meanWithinShotDisplayRgbDelta": (
                round(sum(within_shot)/len(within_shot), 6) if within_shot else None),
            "withinShotComparedPairs": len(within_shot),
            "cutSeparatedPairs": len(pairs)-len(within_shot),
        },
        "evidenceStatus": "original-source-pts-sampled-numeric-proxies-not-human-reviewed",
        "methodLimits": [
            "These are observed display RGB pixel values, not scene-linear physical luminance or measured lighting equipment.",
            "Interframe RGB differences combine animation, object movement, camera movement, compression, text and fades.",
            "The cut detector proposes edits; fast movement and transitions can cause false positives/negatives.",
            "Sampled intervals are not exhaustive source-frame measurement or full-video shot frequency.",
            "No lens, real camera trajectory, visual style, mood, demographic identity, character or speech inference is claimed.",
        ],
    }


def write_source_visual_probe(source: Path, out: Path, **kwargs: Any) -> Path:
    """Publish one verified local analysis atomically without copying source video."""
    if out.exists() or out.is_symlink():
        raise ValueError("visual probe output must be a new nonexisting directory")
    report = analyze_source_visual_window(source, **kwargs)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-visual-probe-", dir=out.parent) as directory:
        staging = Path(directory)
        (staging/"visual-probe.json").write_text(
            json.dumps(report, indent=2, sort_keys=True,
                       ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")
        if out.exists() or out.is_symlink():
            raise ValueError("visual probe output became occupied during analysis")
        os.replace(staging, out)
    return out/"visual-probe.json"
