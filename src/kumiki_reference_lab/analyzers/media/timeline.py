"""Versioned report of decoded-frame source PTS and anomalies."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.contracts.analysis import FRAME_TIMELINE_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict


def analyze_frame_timeline(
    path: Path, *, seconds: int = 60, ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
) -> dict[str, Any]:
    if type(seconds) is not int or not 1 <= seconds <= 120:
        raise ValueError("seconds must be between 1 and 120")
    signature = file_signature(path)
    source = inspect_source(path, rights_status=rights_status, ffprobe=ffprobe)
    rational = source["video"]["sourceTimebase"]
    timebase = Fraction(rational["numerator"], rational["denominator"])
    frames = read_frame_pts(path, source["video"]["streamIndex"],
                            seconds=seconds, ffprobe=ffprobe)
    require_unchanged(path, signature)

    result: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    last_pts: int | None = None
    for frame in frames:
        if frame.pts is None:
            anomalies.append({"sampleOrdinal": frame.ordinal, "reason": "missing-source-pts"})
        elif last_pts is not None and frame.pts <= last_pts:
            anomalies.append({"sampleOrdinal": frame.ordinal, "reason": "nonincreasing-source-pts"})
        if frame.pts is not None:
            last_pts = frame.pts
        result.append({
            "sampleOrdinal": frame.ordinal,
            "sourcePts": frame.pts,
            "ptsSource": frame.origin,
            "sourceSeconds": (as_rational_dict(frame.pts * timebase)
                              if frame.pts is not None else None),
        })

    return {
        "schemaVersion": FRAME_TIMELINE_VERSION,
        "sourceSha256": source["source"]["sha256"],
        "sourceStreamIndex": source["video"]["streamIndex"],
        "sourceTimebase": rational,
        "scanWindowSeconds": seconds,
        "coverage": "bounded-from-start-not-necessarily-full-video",
        "ptsDerivedFromFps": False,
        "frames": result,
        "anomalies": anomalies,
    }
