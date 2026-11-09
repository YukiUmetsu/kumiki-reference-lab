"""Bounded source-time-based apparent global image translation analysis."""

from __future__ import annotations

import importlib.util
from bisect import bisect_left, bisect_right
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.motion.easing import fit_easing_candidates
from kumiki_reference_lab.analyzers.motion.phase import measure_image_shift
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_gray_frames
from kumiki_reference_lab.backends.ffmpeg.scene import detect_hard_cut_pts
from kumiki_reference_lab.contracts.analysis import IMAGE_MOTION_VERSION
from kumiki_reference_lab.contracts.frames import FramePts
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict


def select_motion_samples(frames: list[FramePts], limit: int) -> list[FramePts]:
    """Sample uniformly in real presentation time, not frame index or FPS."""
    if type(limit) is not int or not 5 <= limit <= 120:
        raise ValueError("motion sample limit must be between 5 and 120")
    usable = [frame for frame in frames if frame.pts is not None]
    if len(usable) < 2:
        raise ValueError("need at least two decoded frames with source timestamps")
    pts = [int(frame.pts) for frame in usable]
    if any(b <= a for a, b in zip(pts, pts[1:])):
        raise ValueError("motion analysis requires a strictly increasing source PTS sequence")
    if len(usable) <= limit:
        return usable
    selected: set[int] = set()
    first, last = pts[0], pts[-1]
    for i in range(limit):
        target = Fraction(first) + Fraction((last - first) * i, limit - 1)
        upper = bisect_left(pts, target)
        if upper >= len(pts):
            chosen = len(pts) - 1
        elif upper == 0:
            chosen = 0
        else:
            chosen = min((upper - 1, upper), key=lambda j: (abs(pts[j] - target), j))
        selected.add(chosen)
    return [usable[index] for index in sorted(selected)]


def analyze_image_motion(
    source: Path, *, seconds: int = 10, max_samples: int = 48,
    width: int = 160, height: int = 90, threshold: float = 0.25,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
) -> dict[str, Any]:
    if type(seconds) is not int or not 1 <= seconds <= 30:
        raise ValueError("seconds must be between 1 and 30")
    if type(max_samples) is not int or not 5 <= max_samples <= 120:
        raise ValueError("max_samples must be between 5 and 120")
    if (type(width) is not int or type(height) is not int or
            not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("motion analysis width/height are out of range")
    if not isinstance(threshold, (float, int)) or not 0 < threshold < 1:
        raise ValueError("cut threshold must be between 0 and 1")
    if importlib.util.find_spec("numpy") is None:
        raise ValueError("motion requires NumPy; install with pip install '.[motion]'")
    import numpy as np

    signature = file_signature(source)
    inspected = inspect_source(source, rights_status=rights_status, ffprobe=ffprobe)
    stream = inspected["video"]["streamIndex"]
    rational = inspected["video"]["sourceTimebase"]
    timebase = Fraction(rational["numerator"], rational["denominator"])
    source_frames = read_frame_pts(source, stream, seconds=seconds, ffprobe=ffprobe)
    samples = select_motion_samples(source_frames, max_samples)
    cuts = detect_hard_cut_pts(source, stream, seconds=seconds,
                               threshold=threshold, ffmpeg=ffmpeg)
    if cuts.timebase != timebase:
        raise ValueError("cut detector changed source timebase")
    planes = read_gray_frames(
        source, stream, [frame.ordinal for frame in samples],
        [int(frame.pts) for frame in samples], timebase=timebase,
        seconds=seconds, width=width, height=height, ffmpeg=ffmpeg,
    )
    require_unchanged(source, signature)

    points = [{"sampleOrdinal": frame.ordinal, "sourcePts": frame.pts,
               "sourceSeconds": as_rational_dict(int(frame.pts) * timebase)}
              for frame in samples]
    pairs: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    cut_pts = sorted(set(cuts.pts))
    path: list[tuple[Fraction, float, float]] = [(int(samples[0].pts) * timebase, 0.0, 0.0)]
    path_frames = [samples[0]]

    def finish_segment() -> None:
        nonlocal path, path_frames
        if len(path) >= 2:
            segments.append({
                "startPts": path_frames[0].pts,
                "endPts": path_frames[-1].pts,
                "samples": [{
                    "sourcePts": frame.pts,
                    "sourceSeconds": as_rational_dict(moment),
                    "cumulativeDxPixels": round(x, 5),
                    "cumulativeDyPixels": round(y, 5),
                } for frame, (moment, x, y) in zip(path_frames, path, strict=True)],
                "easing": fit_easing_candidates(path),
            })

    for i in range(1, len(samples)):
        before, after = samples[i - 1], samples[i]
        before_pts, after_pts = int(before.pts), int(after.pts)
        # Include an edit at the later timestamp and exclude one at the start.
        crosses_cut = (bisect_right(cut_pts, before_pts) <
                       bisect_right(cut_pts, after_pts))
        if crosses_cut:
            measured = {"status": "cut-boundary", "dxPixels": None,
                        "dyPixels": None, "peakToSidelobeRatio": None}
        else:
            measured = measure_image_shift(planes[i - 1], planes[i], width, height)
        dt = (after_pts - before_pts) * timebase
        pairs.append({
            "startPts": before_pts, "endPts": after_pts,
            "deltaTimeSeconds": as_rational_dict(dt),
            "status": measured["status"],
            "dxPixels": measured["dxPixels"], "dyPixels": measured["dyPixels"],
            "dxNormalized": (round(measured["dxPixels"] / width, 7)
                             if measured["dxPixels"] is not None else None),
            "dyNormalized": (round(measured["dyPixels"] / height, 7)
                             if measured["dyPixels"] is not None else None),
            "peakToSidelobeRatio": measured["peakToSidelobeRatio"],
        })
        if measured["dxPixels"] is None:
            finish_segment()
            path = [(after_pts * timebase, 0.0, 0.0)]
            path_frames = [after]
        else:
            _, x, y = path[-1]
            path.append((after_pts * timebase,
                         x + measured["dxPixels"], y + measured["dyPixels"]))
            path_frames.append(after)
    finish_segment()
    return {
        "schemaVersion": IMAGE_MOTION_VERSION,
        "sourceSha256": inspected["source"]["sha256"],
        "sourceStreamIndex": stream, "sourceTimebase": rational,
        "scanWindowSeconds": seconds,
        "coverage": "bounded-from-start-not-necessarily-full-video",
        "analysis": {
            "method": "fft-phase-correlation-global-translation-v1",
            "easingModel": "net-path-projection-with-geometry-abstention-v2",
            "numpyVersion": np.__version__,
            "ffmpegExecutable": ffmpeg,
            "ffprobeExecutable": ffprobe,
            "resolution": {"width": width, "height": height},
            "maxSamples": max_samples,
            "observedFrameCount": len(source_frames),
            "missingSourcePtsCount": sum(frame.pts is None for frame in source_frames),
            "selection": "uniform-original-pts-nearest-frame",
            "cutThreshold": float(threshold),
            "calibratedConfidence": False,
            "limits": "apparent image shift only; cannot identify camera versus object, parallax, zoom, or 3D motion",
        },
        "cutCandidatePts": cut_pts,
        "samples": points,
        "pairs": pairs,
        "segments": segments,
    }
