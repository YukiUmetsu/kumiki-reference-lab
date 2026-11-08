"""User-seeded image-patch tracks with original video PTS and explicit loss."""

from __future__ import annotations

import importlib.util
import math
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.motion.analyze import select_motion_samples
from kumiki_reference_lab.analyzers.subjects.template import track_template
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_gray_frames
from kumiki_reference_lab.backends.ffmpeg.scene import detect_hard_cut_pts
from kumiki_reference_lab.contracts.analysis import ROI_TRACK_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict


def analyze_roi_track(
    source: Path, box: tuple[float, float, float, float], *, seconds: int = 10,
    max_samples: int = 48, width: int = 160, height: int = 90,
    radius: int = 12, correlation: float = 0.62, cut_threshold: float = 0.25,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
) -> dict[str, Any]:
    if (len(box) != 4 or any(type(x) not in (int, float) or not math.isfinite(x) for x in box) or
            box[0] < 0 or box[1] < 0 or box[2] <= 0 or box[3] <= 0 or
            box[0] + box[2] > 1 or box[1] + box[3] > 1):
        raise ValueError("box must be normalized x,y,width,height inside [0, 1]")
    if type(seconds) is not int or not 1 <= seconds <= 30:
        raise ValueError("seconds must be between 1 and 30")
    if type(max_samples) is not int or not 5 <= max_samples <= 120:
        raise ValueError("max_samples must be between 5 and 120")
    if type(width) is not int or type(height) is not int or not 64 <= width <= 320 or not 36 <= height <= 180:
        raise ValueError("ROI analysis resolution is out of range")
    if type(radius) is not int or not 1 <= radius <= 48:
        raise ValueError("ROI search radius must be between 1 and 48")
    if not 0 < correlation < 1 or not 0 < cut_threshold < 1:
        raise ValueError("ROI correlation and cut threshold must be between 0 and 1")
    if importlib.util.find_spec("numpy") is None:
        raise ValueError("ROI tracking requires NumPy; install with pip install '.[motion]'")
    import numpy as np

    x0, y0 = round(box[0] * width), round(box[1] * height)
    box_width, box_height = round(box[2] * width), round(box[3] * height)
    if (box_width < 8 or box_height < 8 or box_width > width // 2 or
            box_height > height // 2 or x0 + box_width > width or y0 + box_height > height):
        raise ValueError("ROI box must fit inside the analysis grid and be 8px to half-frame sized")
    if (2 * radius + 1) ** 2 * box_width * box_height > 6_000_000:
        raise ValueError("ROI search window exceeds bounded compute budget")

    signature = file_signature(source)
    manifest = inspect_source(source, rights_status=rights_status, ffprobe=ffprobe)
    stream = manifest["video"]["streamIndex"]
    rational = manifest["video"]["sourceTimebase"]
    timebase = Fraction(rational["numerator"], rational["denominator"])
    all_frames = read_frame_pts(source, stream, seconds=seconds, ffprobe=ffprobe)
    samples = select_motion_samples(all_frames, max_samples)
    cuts = detect_hard_cut_pts(source, stream, seconds=seconds,
                               threshold=cut_threshold, ffmpeg=ffmpeg)
    if cuts.timebase != timebase:
        raise ValueError("ROI cut detector changed source timebase")
    planes = read_gray_frames(
        source, stream, [frame.ordinal for frame in samples],
        [int(frame.pts) for frame in samples], timebase=timebase,
        seconds=seconds, width=width, height=height, ffmpeg=ffmpeg,
    )
    require_unchanged(source, signature)

    first_plane = planes[0]
    template = b"".join(first_plane[(y0 + row) * width + x0:
                                    (y0 + row) * width + x0 + box_width]
                        for row in range(box_height))
    # Check up front that the given region is actually measurable.
    texture_check = track_template(template, first_plane, width, height, box_width, box_height,
                                   x0, y0, radius=1, minimum_correlation=correlation)
    if texture_check["status"] == "unobservable-low-texture":
        raise ValueError("seeded ROI has insufficient texture to track")

    cut_pts = sorted(set(cuts.pts))
    observations: list[dict[str, Any]] = []
    px, py = x0, y0
    stopped: str | None = None
    for index, frame in enumerate(samples):
        pts = int(frame.pts)
        status = "seeded" if index == 0 else "not-tracked-after-loss"
        similarity: float | None = None
        peak_margin: float | None = None
        if index > 0:
            previous_pts = int(samples[index - 1].pts)
            crosses_cut = (bisect_right(cut_pts, previous_pts) < bisect_right(cut_pts, pts))
            if stopped == "cut":
                status = "not-tracked-after-cut"
            elif stopped == "lost":
                status = "not-tracked-after-loss"
            elif crosses_cut:
                stopped, status = "cut", "cut-boundary"
            else:
                matched = track_template(template, planes[index], width, height,
                                         box_width, box_height, px, py,
                                         radius=radius, minimum_correlation=correlation)
                status = matched["status"]
                similarity = matched["correlation"]
                peak_margin = matched["peakMargin"]
                if status == "matched-template":
                    px, py = matched["x"], matched["y"]
                else:
                    stopped = "lost"
        has_position = status in {"seeded", "matched-template"}
        observations.append({
            "sampleOrdinal": frame.ordinal,
            "sourcePts": pts,
            "sourceSeconds": as_rational_dict(pts * timebase),
            "status": status,
            "boxPixels": ({"x": px, "y": py, "width": box_width, "height": box_height}
                          if has_position else None),
            "boxNormalized": ({"x": round(px / width, 7), "y": round(py / height, 7),
                               "width": round(box_width / width, 7),
                               "height": round(box_height / height, 7)} if has_position else None),
            "displacementPixels": ({"dx": px - x0, "dy": py - y0} if has_position else None),
            "appearanceCorrelation": similarity,
            "peakMargin": peak_margin,
        })

    return {
        "schemaVersion": ROI_TRACK_VERSION,
        "sourceSha256": manifest["source"]["sha256"],
        "sourceStreamIndex": stream,
        "sourceTimebase": rational,
        "scanWindowSeconds": seconds,
        "coverage": "bounded-from-start-not-necessarily-full-video",
        "analyzer": {
            "method": "normalized-template-correlation-v1",
            "numpyVersion": np.__version__,
            "ffmpegExecutable": ffmpeg,
            "ffprobeExecutable": ffprobe,
            "seedBoxNormalized": list(box),
            "analysisResolution": {"width": width, "height": height},
            "maxSamples": max_samples, "searchRadiusPixels": radius,
            "minimumAppearanceCorrelation": correlation,
            "cutThreshold": cut_threshold,
            "observedFrameCount": len(all_frames),
            "missingSourcePtsCount": sum(frame.pts is None for frame in all_frames),
            "calibratedConfidence": False,
            "limits": "static patch/short-range tracking only; no semantic identity, occlusion recovery or 3D interpretation",
        },
        "cutCandidatePts": cut_pts,
        "observations": observations,
    }
