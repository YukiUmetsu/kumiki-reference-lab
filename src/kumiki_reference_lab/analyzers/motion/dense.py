"""Optional bounded, multi-scale dense optical-flow *image-plane* evidence.

Farneback estimates each image pixel's displacement. Only a regular grid of
locally textured, forward/backward-consistent points is exported. Discarded
grid cells stay unknown: no occlusion fill, semantic identity or 3D inference.
"""

from __future__ import annotations

import importlib.util
import math
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.motion.analyze import select_motion_samples
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_gray_frames
from kumiki_reference_lab.backends.ffmpeg.scene import detect_hard_cut_pts
from kumiki_reference_lab.contracts.analysis import DENSE_FLOW_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict


def _sample_bilinear(array: Any, x: float, y: float) -> Any:
    """Interpolate an ndarray at an interior pixel coordinate."""
    left, top = int(x), int(y)
    fx, fy = x - left, y - top
    return ((1 - fx) * (1 - fy) * array[top, left] +
            fx * (1 - fy) * array[top, left + 1] +
            (1 - fx) * fy * array[top + 1, left] +
            fx * fy * array[top + 1, left + 1])


def measure_dense_flow(before: bytes, after: bytes, width: int, height: int,
                       *, grid_step: int = 12) -> dict[str, Any]:
    """Measure dense flow and expose only conservative sampled observations.

    No API download or model checkpoint is required. This method is not
    reliable through occlusion, motion blur, novel surfaces or flat texture.
    """
    if (type(width) is not int or type(height) is not int or
            not 64 <= width <= 240 or not 36 <= height <= 135):
        raise ValueError("dense-flow requires a bounded frame resolution")
    if type(grid_step) is not int or not 8 <= grid_step <= 24:
        raise ValueError("dense-flow grid step must be 8..24")
    if (type(before) is not bytes or type(after) is not bytes or
            len(before) != width * height or len(after) != width * height):
        raise ValueError("dense-flow requires two exact-size gray planes")
    if importlib.util.find_spec("cv2") is None or importlib.util.find_spec("numpy") is None:
        raise ValueError("dense-flow requires OpenCV; install with pip install '.[dense]'")

    import cv2
    import numpy as np

    first = np.frombuffer(before, np.uint8).reshape((height, width))
    second = np.frombuffer(after, np.uint8).reshape((height, width))
    forward = cv2.calcOpticalFlowFarneback(first, second, None,
                                          0.5, 3, 15, 3, 5, 1.2, 0)
    backward = cv2.calcOpticalFlowFarneback(second, first, None,
                                           0.5, 3, 15, 3, 5, 1.2, 0)

    # Two-sided local texture support is a visibility *proxy*, not a mask.
    def local_std(image: Any) -> Any:
        floats = image.astype(np.float32)
        means = cv2.boxFilter(floats, -1, (9, 9), normalize=True)
        squared = cv2.boxFilter(floats * floats, -1, (9, 9), normalize=True)
        return np.sqrt(np.maximum(squared - means * means, 0))

    before_std, after_std = local_std(first), local_std(second)
    accepted: list[dict[str, Any]] = []
    rejected = {"low-texture": 0, "out-of-frame": 0,
                "roundtrip-inconsistent": 0, "implausible-displacement": 0,
                "appearance-inconsistent": 0}
    candidates = 0
    for y in range(grid_step // 2, height - grid_step // 2, grid_step):
        for x in range(grid_step // 2, width - grid_step // 2, grid_step):
            candidates += 1
            dx, dy = (float(v) for v in forward[y, x])
            if not math.isfinite(dx) or not math.isfinite(dy) or math.hypot(dx, dy) > 24:
                rejected["implausible-displacement"] += 1
                continue
            destination_x, destination_y = x + dx, y + dy
            if not (5 <= destination_x < width - 6 and
                    5 <= destination_y < height - 6):
                rejected["out-of-frame"] += 1
                continue
            if (before_std[y, x] < 8.0 or
                    _sample_bilinear(after_std, destination_x, destination_y) < 8.0):
                rejected["low-texture"] += 1
                continue
            reverse_dx, reverse_dy = _sample_bilinear(backward, destination_x,
                                                     destination_y)
            roundtrip_error = math.hypot(dx + float(reverse_dx),
                                         dy + float(reverse_dy))
            if not math.isfinite(roundtrip_error) or roundtrip_error > 1.5:
                rejected["roundtrip-inconsistent"] += 1
                continue
            # Reverse flow can be self-consistent even between unrelated
            # textured images. Require source/warped-destination appearance
            # support separately; offset illumination is tolerated by ZNCC.
            first_patch = cv2.getRectSubPix(first, (9, 9),
                                            (float(x), float(y))).astype(np.float32)
            second_patch = cv2.getRectSubPix(second, (9, 9),
                                             (float(destination_x),
                                              float(destination_y))).astype(np.float32)
            centered_first = first_patch - first_patch.mean()
            centered_second = second_patch - second_patch.mean()
            denominator = math.sqrt(float(np.sum(centered_first ** 2)) *
                                    float(np.sum(centered_second ** 2)))
            correlation = (float(np.sum(centered_first * centered_second)) /
                           denominator) if denominator > 1e-6 else -1.0
            if not math.isfinite(correlation) or correlation < 0.62:
                rejected["appearance-inconsistent"] += 1
                continue
            accepted.append({
                "x": x, "y": y, "dx": round(dx, 4), "dy": round(dy, 4),
                "roundtripErrorPixels": round(roundtrip_error, 4),
            })
    status = ("flow-observed" if len(accepted) >= 5 else
              "insufficient-grid-support" if accepted else "unobservable")
    return {"status": status,
            "candidateCount": candidates, "rejected": rejected, "vectors": accepted,
            "acceptedFraction": round(len(accepted) / candidates, 5) if candidates else 0.0}


def analyze_dense_flow(
    source: Path, *, seconds: int = 10, max_samples: int = 24,
    width: int = 160, height: int = 90, grid_step: int = 12,
    threshold: float = 0.25, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
) -> dict[str, Any]:
    """Analyze bounded FFmpeg frames without interpolating their source clock."""
    if type(seconds) is not int or not 1 <= seconds <= 20:
        raise ValueError("dense-flow seconds must be 1..20")
    if type(max_samples) is not int or not 5 <= max_samples <= 40:
        raise ValueError("dense-flow max samples must be 5..40")
    if (type(width) is not int or type(height) is not int or
            not 64 <= width <= 240 or not 36 <= height <= 135):
        raise ValueError("dense-flow requires bounded resolution")
    if type(grid_step) is not int or not 8 <= grid_step <= 24:
        raise ValueError("dense-flow grid step must be 8..24")
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("dense-flow cut threshold must be between zero and one")
    if importlib.util.find_spec("cv2") is None or importlib.util.find_spec("numpy") is None:
        raise ValueError("dense-flow requires OpenCV; install with pip install '.[dense]'")
    import cv2
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
        raise ValueError("dense-flow cut detector changed source timebase")
    planes = read_gray_frames(source, stream, [f.ordinal for f in samples],
                              [int(f.pts) for f in samples], timebase=timebase,
                              seconds=seconds, width=width, height=height, ffmpeg=ffmpeg)
    require_unchanged(source, signature)
    cut_pts = sorted(set(cuts.pts))
    pairs: list[dict[str, Any]] = []
    for index in range(1, len(samples)):
        start_pts, end_pts = int(samples[index - 1].pts), int(samples[index].pts)
        pair = {"startPts": start_pts, "endPts": end_pts,
                "deltaTimeSeconds": as_rational_dict((end_pts - start_pts) * timebase)}
        if bisect_right(cut_pts, start_pts) < bisect_right(cut_pts, end_pts):
            pair.update({"status": "cut-boundary", "candidateCount": 0,
                         "rejected": {"low-texture": 0, "out-of-frame": 0,
                                      "roundtrip-inconsistent": 0,
                                      "implausible-displacement": 0,
                                      "appearance-inconsistent": 0},
                         "vectors": [], "acceptedFraction": 0.0})
        else:
            pair.update(measure_dense_flow(planes[index - 1], planes[index],
                                           width, height, grid_step=grid_step))
        pairs.append(pair)
    return {
        "schemaVersion": DENSE_FLOW_VERSION,
        "sourceSha256": manifest["source"]["sha256"],
        "sourceStreamIndex": stream, "sourceTimebase": rational,
        "scanWindowSeconds": seconds,
        "coverage": "bounded-from-start-not-necessarily-full-video",
        "analyzer": {
            "method": "farneback-pyramid3-fb-texture-v1",
            "opencvVersion": cv2.__version__, "numpyVersion": np.__version__,
            "ffmpegExecutable": ffmpeg, "ffprobeExecutable": ffprobe,
            "resolution": {"width": width, "height": height},
            "maxSamples": max_samples, "gridStepPixels": grid_step,
            "pyramidLevels": 3, "windowSizePixels": 15,
            "localTextureWindowPixels": 9, "minimumTextureStdGray": 8.0,
            "appearancePatchSizePixels": 9,
            "minimumAppearanceCorrelation": 0.62,
            "forwardBackwardTolerancePixels": 1.5, "maximumImageDisplacementPixels": 24,
            "cutThreshold": float(threshold),
            "observedFrameCount": len(frames),
            "missingSourcePtsCount": sum(f.pts is None for f in frames),
            "selection": "uniform-original-pts-nearest-frame",
            "calibratedConfidence": False,
            "physicalCameraVerified": False,
            "semanticIdentityVerified": False,
            "limits": "Dense image-plane optical flow, exported as a sampled grid; occlusion and texture gates are proxies, not proof of identities, masks, 3D depths or physical camera motion",
        },
        "cutCandidatePts": cut_pts,
        "samples": [{"sampleOrdinal": f.ordinal, "sourcePts": f.pts,
                     "sourceSeconds": as_rational_dict(int(f.pts) * timebase)}
                    for f in samples],
        "pairs": pairs,
    }
