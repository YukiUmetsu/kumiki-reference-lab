"""Source inspection with explicit VFR uncertainty and no inferred frames."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError, probe_media
from kumiki_reference_lab.contracts.source import RIGHTS_STATUSES, SCHEMA_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict, parse_rational


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_source(
    path: Path, *, rights_status: str = "review-required", ffprobe: str = "ffprobe"
) -> dict[str, Any]:
    if rights_status not in RIGHTS_STATUSES:
        raise ValueError("invalid rights status")
    if not path.is_file():
        raise ValueError("source must be an existing regular file")
    source_before = file_signature(path)
    try:
        metadata = probe_media(path, ffprobe=ffprobe)
    except ProbeError:
        raise

    streams = metadata.get("streams")
    if not isinstance(streams, list):
        raise ProbeError("ffprobe did not provide a stream list")
    video = next((item for item in streams if isinstance(item, dict) and
                  item.get("codec_type") == "video" and not
                  (isinstance(item.get("disposition"), dict) and
                   item["disposition"].get("attached_pic") == 1)), None)
    if video is None:
        raise ProbeError("source has no video stream")

    width, height = video.get("width"), video.get("height")
    stream_index = video.get("index")
    codec = video.get("codec_name")
    timebase = parse_rational(video.get("time_base"))
    if (type(width) is not int or type(height) is not int or
            width <= 0 or height <= 0):
        raise ProbeError("video has invalid dimensions")
    if type(stream_index) is not int or stream_index < 0:
        raise ProbeError("video has no valid stream index")
    if codec is not None and not isinstance(codec, str):
        raise ProbeError("video has an invalid codec name")
    if timebase is None:
        raise ProbeError("video has no valid stream timebase")

    format_metadata = metadata.get("format")
    if not isinstance(format_metadata, dict):
        format_metadata = {}
    reported_duration = video.get("duration") or format_metadata.get("duration")
    if reported_duration is not None and not isinstance(reported_duration, str):
        raise ProbeError("video has an invalid duration field")

    source_hash = sha256_file(path)
    require_unchanged(path, source_before)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": {
            "fileName": path.name,
            "sizeBytes": source_before[0],
            "sha256": source_hash,
            # Status is user-declared metadata, not a legal determination.
            "rightsStatus": rights_status,
        },
        "video": {
            "streamIndex": stream_index,
            "codec": codec,
            "width": width,
            "height": height,
            "averageFrameRate": as_rational_dict(parse_rational(video.get("avg_frame_rate"))),
            "nominalFrameRate": as_rational_dict(parse_rational(video.get("r_frame_rate"))),
            "sourceTimebase": as_rational_dict(timebase),
            "durationSecondsReported": reported_duration,
        },
        "timestamps": {
            "sourceUnit": "stream-timebase-ticks",
            "originalFramePtsExtracted": False,
            "frameRateMode": "unknown-until-source-pts-are-inspected",
            "outputMapping": "not-performed",
        },
        "analysis": {"method": "ffprobe-metadata", "frameAnalysisPerformed": False},
    }
