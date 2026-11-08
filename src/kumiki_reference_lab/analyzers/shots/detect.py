"""Source timebased hard-cut candidates, without fabricated confidence scores."""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.backends.ffmpeg.scene import detect_hard_cut_pts
from kumiki_reference_lab.contracts.analysis import SHOT_CANDIDATES_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict


def analyze_hard_cuts(
    path: Path, *, seconds: int = 60, threshold: float = 0.25,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
) -> dict[str, Any]:
    if type(seconds) is not int or not 1 <= seconds <= 120:
        raise ValueError("seconds must be between 1 and 120")
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("threshold must be finite and between 0 and 1")
    signature = file_signature(path)
    source = inspect_source(path, rights_status=rights_status, ffprobe=ffprobe)
    scan = detect_hard_cut_pts(
        path, source["video"]["streamIndex"],
        seconds=seconds, threshold=threshold, ffmpeg=ffmpeg,
    )
    require_unchanged(path, signature)
    rational = source["video"]["sourceTimebase"]
    timebase = Fraction(rational["numerator"], rational["denominator"])
    if scan.timebase != timebase:
        raise ValueError("FFmpeg cut filter changed timebase; cannot label PTS as original")
    return {
        "schemaVersion": SHOT_CANDIDATES_VERSION,
        "sourceSha256": source["source"]["sha256"],
        "sourceStreamIndex": source["video"]["streamIndex"],
        "sourceTimebase": rational,
        "scanWindowSeconds": seconds,
        "coverage": "bounded-from-start-not-necessarily-full-video",
        "detector": {
            "method": "ffmpeg-select-scene-difference",
            "threshold": float(threshold),
            "limits": "hard-cut-candidates-only; fast-motion-can-cause-false-positives",
        },
        "candidates": [{
            "sourcePts": pts,
            "sourceSeconds": as_rational_dict(pts * timebase),
            "kind": "hard-cut-candidate",
            "confidence": None,
        } for pts in scan.pts],
    }
