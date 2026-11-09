"""Local, bounded image color/contrast statistics with original source PTS."""

from __future__ import annotations

import importlib.util
import math
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.appearance.statistics import describe_rgb_frame
from kumiki_reference_lab.analyzers.appearance.ramps import detect_luma_ramp_candidates
from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.motion.analyze import select_motion_samples
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames
from kumiki_reference_lab.backends.ffmpeg.scene import detect_hard_cut_pts
from kumiki_reference_lab.contracts.analysis import APPEARANCE_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict


def analyze_appearance(
    source: Path, *, seconds: int = 10, max_samples: int = 24,
    width: int = 160, height: int = 90, threshold: float = 0.25,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
) -> dict[str, Any]:
    if type(seconds) is not int or not 1 <= seconds <= 20:
        raise ValueError("appearance seconds must be 1..20")
    if type(max_samples) is not int or not 5 <= max_samples <= 40:
        raise ValueError("appearance samples must be 5..40")
    if (type(width) is not int or type(height) is not int or
            not 64 <= width <= 240 or not 36 <= height <= 135):
        raise ValueError("appearance resolution is out of range")
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("appearance cut threshold must be between zero and one")
    if importlib.util.find_spec("numpy") is None:
        raise ValueError("appearance requires NumPy; install with pip install '.[motion]'")
    import numpy as np

    signature = file_signature(source)
    manifest = inspect_source(source, rights_status=rights_status, ffprobe=ffprobe)
    stream = manifest["video"]["streamIndex"]
    source_timebase = manifest["video"]["sourceTimebase"]
    timebase = Fraction(source_timebase["numerator"], source_timebase["denominator"])
    frames = read_frame_pts(source, stream, seconds=seconds, ffprobe=ffprobe)
    samples = select_motion_samples(frames, max_samples)
    cuts = detect_hard_cut_pts(source, stream, seconds=seconds,
                               threshold=threshold, ffmpeg=ffmpeg)
    if cuts.timebase != timebase:
        raise ValueError("appearance cut detector changed source timebase")
    planes = read_rgb_frames(source, stream, [f.ordinal for f in samples],
                             [int(f.pts) for f in samples], timebase=timebase,
                             seconds=seconds, width=width, height=height, ffmpeg=ffmpeg)
    require_unchanged(source, signature)

    observations = []
    for frame, rgb in zip(samples, planes, strict=True):
        observations.append({
            "sampleOrdinal": frame.ordinal,
            "sourcePts": int(frame.pts),
            "sourceSeconds": as_rational_dict(int(frame.pts) * timebase),
            "appearance": describe_rgb_frame(rgb, width, height),
        })
    cut_pts = sorted(set(cuts.pts))
    changes = []
    for earlier, later in zip(observations, observations[1:]):
        crosses = bisect_right(cut_pts, earlier["sourcePts"]) < bisect_right(
            cut_pts, later["sourcePts"])
        first, second = earlier["appearance"], later["appearance"]
        changes.append({
            "startPts": earlier["sourcePts"], "endPts": later["sourcePts"],
            "deltaTimeSeconds": as_rational_dict(
                (later["sourcePts"] - earlier["sourcePts"]) * timebase),
            "status": "cut-boundary" if crosses else "measured-display-appearance-change",
            "meanLumaProxyDelta": (None if crosses else round(
                second["meanLumaProxy"] - first["meanLumaProxy"], 5)),
            "meanRgbDelta": (None if crosses else [round(b - a, 5)
                             for a, b in zip(first["meanRgb"], second["meanRgb"], strict=True)]),
            "hueHistogramTotalVariation": (None if crosses else round(
                sum(abs(b - a) for a, b in zip(first["hueHistogram12"],
                                               second["hueHistogram12"], strict=True)) / 2, 5)),
        })
    return {
        "schemaVersion": APPEARANCE_VERSION,
        "sourceSha256": manifest["source"]["sha256"],
        "sourceStreamIndex": stream, "sourceTimebase": source_timebase,
        "scanWindowSeconds": seconds,
        "coverage": "bounded-from-start-not-necessarily-full-video",
        "analyzer": {
            "method": "rgb-display-proxy-statistics-v1",
            "rampModel": "spatially-coherent-luma-ramp-candidate-v1",
            "numpyVersion": np.__version__,
            "ffmpegExecutable": ffmpeg, "ffprobeExecutable": ffprobe,
            "resolution": {"width": width, "height": height},
            "pixelFormat": "ffmpeg-rgb24",
            "maxSamples": max_samples, "cutThreshold": float(threshold),
            "observedFrameCount": len(frames),
            "missingSourcePtsCount": sum(f.pts is None for f in frames),
            "selection": "uniform-original-pts-nearest-frame",
            "physicalPhotometry": False,
            "calibratedConfidence": False,
            "limits": "8-bit display-referred converted RGB; luma is non-linear Y-prime proxy, not physical luminance or exposure; saturation/hue and bright pixels do not identify real lights, materials, scene color or lighting motivation",
        },
        "cutCandidatePts": cut_pts,
        "samples": observations,
        "changes": changes,
        "lumaRampCandidates": detect_luma_ramp_candidates(
            observations, changes, timebase=timebase),
    }
