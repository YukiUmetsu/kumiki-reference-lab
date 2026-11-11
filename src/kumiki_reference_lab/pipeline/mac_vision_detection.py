"""Opt-in Apple Vision people rectangles on local, PTS-verified video samples.

macOS only. No model downloads, face recognition, demographic inference or
automatic identification of animated characters.
"""

from __future__ import annotations

import json
import math
import os
import platform
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.motion.analyze import select_motion_samples
from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames
from kumiki_reference_lab.backends.ffmpeg.scene import detect_hard_cut_pts
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.subject_detections import (
    INPUT_VERSION, _check_box, _iou, validate_subject_detections,
)


def _native_rect(rect: Any) -> tuple[float, float, float, float]:
    """Convert Vision bottom-left normalized CGRect into top-left box."""
    try:
        x = float(rect.origin.x)
        y = float(rect.origin.y)
        width = float(rect.size.width)
        height = float(rect.size.height)
    except (AttributeError, TypeError):
        try:
            (x, y), (width, height) = rect
            x, y, width, height = float(x), float(y), float(width), float(height)
        except (TypeError, ValueError) as exc:
            raise ValueError("unexpected Apple Vision CGRect output") from exc
    if not all(math.isfinite(v) for v in (x, y, width, height)):
        raise ValueError("Apple Vision returned nonfinite bounding box")
    if width <= 0 or height <= 0 or x < -1e-5 or y < -1e-5 or x+width > 1+1e-5 or y+height > 1+1e-5:
        raise ValueError("Apple Vision returned an out-of-image box")
    x = min(1.0, max(0.0, x))
    y_top = min(1.0, max(0.0, 1.0 - y - height))
    width = min(width, 1-x)
    height = min(height, 1-y_top)
    box = [round(x, 7), round(y_top, 7), round(width, 7), round(height, 7)]
    _check_box(box, "Apple Vision image rect")
    return tuple(box)


def _detect_humans_with_vision(rgb: bytes, width: int, height: int) -> list[dict[str, Any]]:
    """Run Apple's built-in macOS Vision person detector, when PyObjC is present."""
    if sys.platform != "darwin":
        raise ValueError("Apple Vision human detector requires macOS")
    try:
        import Foundation
        import Vision
    except (ImportError, OSError) as exc:
        raise ValueError("Apple Vision backend requires PyObjC Foundation and Vision bindings") from exc
    png = _png_rgb(rgb, width, height)
    nsdata = Foundation.NSData.dataWithBytes_length_(png, len(png))
    request = Vision.VNDetectHumanRectanglesRequest.alloc().init()
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(nsdata, {})
    try:
        outcome = handler.performRequests_error_([request], None)
    except Exception as exc:
        raise ValueError("Apple Vision human detection request failed") from exc
    if isinstance(outcome, tuple):
        ok = outcome[0]
    else:
        ok = outcome
    if not ok:
        raise ValueError("Apple Vision reported an unsuccessful detection request")
    observations = request.results() or []
    proposed = []
    for observation in observations:
        score = float(observation.confidence())
        if not math.isfinite(score) or not 0 <= score <= 1:
            continue
        box = list(_native_rect(observation.boundingBox()))
        proposed.append({"category": "person", "score": round(score, 7), "box": box})
    # Bounded, source-order-independent output; duplicate same-class boxes removed.
    proposed.sort(key=lambda item: (-item["score"], item["box"][0], item["box"][1]))
    unique = []
    for item in proposed:
        if any(_iou(tuple(item["box"]), tuple(previous["box"])) >= .95 for previous in unique):
            continue
        unique.append(item)
        if len(unique) == 8:
            break
    return sorted(unique, key=lambda item: (item["box"][0], item["box"][1]))


def detect_mac_vision_people(
    source: Path, out: Path, *, seconds: int = 10, max_samples: int = 12,
    width: int = 320, height: int = 180, cut_threshold: float = 0.25,
    start_seconds: int = 0,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
) -> Path:
    """Produce the provider-neutral detections schema from on-device Vision."""
    if (type(seconds) is not int or not 1 <= seconds <= 30 or
            type(start_seconds) is not int or start_seconds < 0 or
            start_seconds + seconds > 120 or
            type(max_samples) is not int or not 5 <= max_samples <= 24 or
            type(width) is not int or type(height) is not int or
            not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("Apple Vision scan and frame budgets invalid")
    if type(cut_threshold) not in (int, float) or not math.isfinite(cut_threshold) or not 0 < cut_threshold < 1:
        raise ValueError("cut threshold must be finite between 0 and 1")
    if out.exists() or out.is_symlink():
        raise ValueError("output must be a new nonexisting JSON file")
    signature = file_signature(source)
    source_info = inspect_source(source, ffprobe=ffprobe, rights_status=rights_status)
    stream = source_info["video"]["streamIndex"]
    tb_dict = source_info["video"]["sourceTimebase"]
    tb = Fraction(tb_dict["numerator"], tb_dict["denominator"])
    all_frames = read_frame_pts(
        source, stream, seconds=seconds, ffprobe=ffprobe,
        start_seconds=start_seconds, source_timebase=tb,
    )
    selected = select_motion_samples(all_frames, max_samples)
    source_prefix = start_seconds + seconds
    rgb = read_rgb_frames(
        source, stream, [frame.ordinal for frame in selected],
        [frame.pts for frame in selected], timebase=tb,
        seconds=source_prefix, width=width, height=height, ffmpeg=ffmpeg)
    cuts = detect_hard_cut_pts(source, stream, seconds=source_prefix,
                               threshold=cut_threshold, ffmpeg=ffmpeg)
    if cuts.timebase != tb:
        raise ValueError("Apple Vision source cut timestamps differ from video timebase")
    entries = []
    for frame, pixels in zip(selected, rgb, strict=True):
        if frame.pts is None:
            raise ValueError("sample frame lacks original source PTS")
        entries.append({
            "sourcePts": frame.pts,
            "detections": _detect_humans_with_vision(pixels, width, height),
        })
    input_json = {
        "schemaVersion": INPUT_VERSION,
        "sourceSha256": source_info["source"]["sha256"],
        "sourceStreamIndex": stream,
        "sourceTimebase": tb_dict,
        "detector": {"name": f"apple-vision-human-rectangles-macos-{platform.mac_ver()[0] or 'unknown'}",
                     "modelSha256": None},
        "cutCandidatePts": sorted({int(pts) for pts in cuts.pts
                                   if selected[0].pts < pts <= selected[-1].pts}),
        "frames": entries,
    }
    validate_subject_detections(input_json)
    require_unchanged(source, signature)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-macos-vision-", dir=out.parent) as temporary:
        staging = Path(temporary) / "detections.json"
        staging.write_text(
            json.dumps(input_json, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        if out.exists() or out.is_symlink():
            raise ValueError("output became occupied before publish")
        os.replace(staging, out)
    return out
