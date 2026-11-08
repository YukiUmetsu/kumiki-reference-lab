"""Bounded, timecode-preserving sparse 2D point tracking across video samples."""

from __future__ import annotations

import importlib.util
import math
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.motion.analyze import select_motion_samples
from kumiki_reference_lab.analyzers.motion.consensus import group_sparse_flows
from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows
from kumiki_reference_lab.analyzers.motion.geometry import fit_image_affine
from kumiki_reference_lab.analyzers.motion.tracklets import build_sparse_tracklets
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_gray_frames
from kumiki_reference_lab.backends.ffmpeg.scene import detect_hard_cut_pts
from kumiki_reference_lab.contracts.analysis import SPARSE_FLOW_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict


def analyze_sparse_flow(
    source: Path, *, seconds: int = 10, max_samples: int = 24,
    width: int = 160, height: int = 90, max_points: int = 40,
    radius: int = 8, correlation: float = 0.68, threshold: float = 0.25,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
) -> dict[str, Any]:
    if type(seconds) is not int or not 1 <= seconds <= 20:
        raise ValueError("sparse-flow seconds must be 1..20")
    if type(max_samples) is not int or not 5 <= max_samples <= 40:
        raise ValueError("sparse-flow max_samples must be 5..40")
    if (type(width) is not int or type(height) is not int or
            not 64 <= width <= 240 or not 36 <= height <= 135):
        raise ValueError("sparse-flow resolution is out of range")
    if type(max_points) is not int or not 4 <= max_points <= 64:
        raise ValueError("sparse-flow max_points must be 4..64")
    if type(radius) is not int or not 2 <= radius <= 12:
        raise ValueError("sparse-flow radius must be 2..12")
    if not all(math.isfinite(v) and 0 < v < 1 for v in (correlation, threshold)):
        raise ValueError("sparse-flow correlation/threshold must be between zero and one")
    if importlib.util.find_spec("numpy") is None:
        raise ValueError("sparse-flow requires NumPy; install with pip install '.[motion]'")
    import numpy as np

    signature = file_signature(source)
    manifest = inspect_source(source, rights_status=rights_status, ffprobe=ffprobe)
    stream = manifest["video"]["streamIndex"]
    rational = manifest["video"]["sourceTimebase"]
    timebase = Fraction(rational["numerator"], rational["denominator"])
    frames = read_frame_pts(source, stream, seconds=seconds, ffprobe=ffprobe)
    samples = select_motion_samples(frames, max_samples)
    cuts = detect_hard_cut_pts(source, stream, seconds=seconds,
                               threshold=threshold, ffmpeg=ffmpeg)
    if cuts.timebase != timebase:
        raise ValueError("sparse-flow cut detector changed source timebase")
    planes = read_gray_frames(source, stream, [f.ordinal for f in samples],
                              [int(f.pts) for f in samples], timebase=timebase,
                              seconds=seconds, width=width, height=height, ffmpeg=ffmpeg)
    require_unchanged(source, signature)
    cut_pts = sorted(set(cuts.pts))
    pairs: list[dict[str, Any]] = []
    for index in range(1, len(samples)):
        first, last = samples[index - 1], samples[index]
        start_pts, end_pts = int(first.pts), int(last.pts)
        crosses_cut = bisect_right(cut_pts, start_pts) < bisect_right(cut_pts, end_pts)
        result: dict[str, Any] = {
            "startPts": start_pts, "endPts": end_pts,
            "deltaTimeSeconds": as_rational_dict((end_pts - start_pts) * timebase),
        }
        if crosses_cut:
            result.update({"status": "cut-boundary", "detectedCorners": 0,
                           "rejected": {key: 0 for key in (
                               "low-texture", "forward-failed", "backward-failed",
                               "roundtrip-inconsistent")},
                           "vectors": [], "consensus": None, "geometryHypothesis": None})
        else:
            tracks = sparse_patch_flows(planes[index - 1], planes[index], width, height,
                                       max_points=max_points, radius=radius,
                                       minimum_correlation=correlation)
            grouped = group_sparse_flows(tracks["accepted"], width, height)
            geometry = fit_image_affine(tracks["accepted"], width, height)
            vectors = [{**item, "group": group} for item, group in
                       zip(tracks["accepted"], grouped["pointGroups"], strict=True)]
            result.update({"status": grouped["status"],
                           "detectedCorners": tracks["detectedCorners"],
                           "rejected": tracks["rejected"], "vectors": vectors,
                           "consensus": {key: value for key, value in grouped.items()
                                         if key != "pointGroups"},
                           "geometryHypothesis": geometry})
        pairs.append(result)
    return {
        "schemaVersion": SPARSE_FLOW_VERSION,
        "sourceSha256": manifest["source"]["sha256"],
        "sourceStreamIndex": stream, "sourceTimebase": rational,
        "scanWindowSeconds": seconds,
        "coverage": "bounded-from-start-not-necessarily-full-video",
        "analyzer": {
            "method": "shi-tomasi-approx-patch-ncc-fb-consensus-affine-v1",
            "numpyVersion": np.__version__,
            "ffmpegExecutable": ffmpeg, "ffprobeExecutable": ffprobe,
            "resolution": {"width": width, "height": height},
            "maxSamples": max_samples, "maxCornersPerFramePair": max_points,
            "searchRadiusPixels": radius, "patchSizePixels": 9,
            "minimumAppearanceCorrelation": correlation,
            "roundtripTolerancePixels": 1.5,
            "consensusTolerancePixels": 1.5,
            "affineInlierTolerancePixels": 1.5,
            "affineMaxHypotheses": 384,
            "cutThreshold": float(threshold),
            "observedFrameCount": len(frames),
            "missingSourcePtsCount": sum(frame.pts is None for frame in frames),
            "selection": "uniform-original-pts-nearest-frame",
            "calibratedConfidence": False,
            "limits": "2D short-baseline integer patch displacement only; affine is an image-plane fit, not physical zoom/rotation/camera recovery; groups and linked tracklets are not semantic identities; no occlusion recovery or 3D inference",
        },
        "cutCandidatePts": cut_pts,
        "samples": [{"sampleOrdinal": f.ordinal, "sourcePts": f.pts,
                     "sourceSeconds": as_rational_dict(int(f.pts) * timebase)} for f in samples],
        "pairs": pairs,
        "temporalTracklets": build_sparse_tracklets(pairs),
    }
