"""Bounded original audio frame PTS and sample-count inventory via FFprobe."""

from __future__ import annotations

import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError, probe_media
from kumiki_reference_lab.contracts.analysis import AUDIO_TIMELINE_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict, parse_rational


def _audio_frames(path: Path, stream_index: int, seconds: int, *, ffprobe: str,
                  max_frames: int) -> list[dict[str, Any]]:
    args = [
        ffprobe, "-v", "error", "-select_streams", str(stream_index),
        "-read_intervals", f"%+{seconds}",
        "-show_frames", "-show_entries",
        "frame=pts,best_effort_timestamp,nb_samples",
        "-of", "compact=p=0:nk=0", "-i", str(path.resolve()),
    ]
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=min(180, seconds*3+20),
                                check=False)
    except FileNotFoundError as exc:
        raise ProbeError("ffprobe executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("audio timeline scan timed out") from exc
    except OSError as exc:
        raise ProbeError("audio timeline scan failed to start") from exc
    if result.returncode:
        raise ProbeError(f"audio timeline scan failed (exit code {result.returncode})")
    if len(result.stdout) > 8_000_000:
        raise ProbeError("audio timeline scan exceeded output budget")
    frames = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = [field.split("=", 1) for field in line.split("|") if "=" in field]
        data = dict(parts)
        if not any(key in data for key in ("pts", "best_effort_timestamp", "nb_samples")):
            continue
        if len(frames) >= max_frames:
            raise ProbeError("decoded audio frame count exceeds scan budget")
        pts = None
        origin = "missing"
        for key, name in (("best_effort_timestamp", "best_effort_timestamp"),
                          ("pts", "pts-fallback")):
            value = data.get(key)
            if value is not None and value.lstrip("-").isdigit():
                pts, origin = int(value), name
                break
        samples_raw = data.get("nb_samples")
        samples = int(samples_raw) if (samples_raw is not None and
                                      samples_raw.isdigit()) else None
        if samples is not None and samples <= 0:
            samples = None
        frames.append({"sampleOrdinal": len(frames), "sourcePts": pts,
                       "ptsSource": origin, "decodedSampleCount": samples})
    return frames


def analyze_audio_timeline(path: Path, *, seconds: int = 10,
                           max_frames: int = 4096, ffprobe: str = "ffprobe",
                           rights_status: str = "review-required") -> dict[str, Any]:
    """Inspect first audio stream without inventing its PTS from video FPS.

    Packet timing and sample count do not measure acoustic events. A later
    RMS/onset stage will require explicit alignment to this original clock.
    """
    if type(seconds) is not int or not 1 <= seconds <= 30:
        raise ValueError("audio seconds must be 1..30")
    if type(max_frames) is not int or not 1 <= max_frames <= 10000:
        raise ValueError("max_frames must be 1..10000")
    signature = file_signature(path)
    inspected = inspect_source(path, rights_status=rights_status, ffprobe=ffprobe)
    probed = probe_media(path, ffprobe=ffprobe)
    candidates = [stream for stream in probed["streams"]
                  if isinstance(stream, dict) and stream.get("codec_type") == "audio"]
    base = {
        "schemaVersion": AUDIO_TIMELINE_VERSION,
        "sourceSha256": inspected["source"]["sha256"],
        "sourceVideoStreamIndex": inspected["video"]["streamIndex"],
        "scanWindowSeconds": seconds,
        "maxFrameBudget": max_frames,
        "rightsStatus": rights_status,
        "coverage": "bounded-from-start-not-necessarily-full-audio",
        "limits": "Decoded audio frame PTS and sample counts only. No waveform energy, beats, silence, language, scene sync, music or story interpretation. Audio stream clocks may differ from video clock; no synthetic alignment.",
    }
    if not candidates:
        require_unchanged(path, signature)
        return {
            **base, "status": "no-audio-stream", "audioStreamIndex": None,
            "sourceTimebase": None, "sampleRateHz": None,
            "channels": None, "frames": [], "ptsAnomalies": [],
        }
    stream = candidates[0]
    index, sample_rate = stream.get("index"), stream.get("sample_rate")
    channels, timebase = stream.get("channels"), parse_rational(stream.get("time_base"))
    if (type(index) is not int or index < 0 or
            not isinstance(sample_rate, str) or not sample_rate.isdigit() or
            int(sample_rate) <= 0 or type(channels) is not int or channels <= 0 or
            timebase is None or timebase <= 0):
        raise ProbeError("audio stream lacks valid index, sample rate, channels or timebase")
    decoded = _audio_frames(path, index, seconds, ffprobe=ffprobe, max_frames=max_frames)
    last = None
    anomalies = []
    frames = []
    for row in decoded:
        pts = row["sourcePts"]
        reason = ("missing-source-pts" if pts is None else
                  "nonincreasing-source-pts" if last is not None and pts <= last
                  else None)
        if reason is not None:
            anomalies.append({"sampleOrdinal": row["sampleOrdinal"], "reason": reason})
        if pts is not None:
            last = pts
        if row["decodedSampleCount"] is None:
            anomalies.append({"sampleOrdinal": row["sampleOrdinal"],
                              "reason": "missing-or-invalid-sample-count"})
        frames.append({
            **row,
            "sourceSeconds": as_rational_dict(pts * timebase) if pts is not None else None,
            "decodedDurationSeconds": (
                as_rational_dict(Fraction(row["decodedSampleCount"], int(sample_rate)))
                if row["decodedSampleCount"] is not None else None
            ),
        })
    require_unchanged(path, signature)
    return {
        **base,
        "status": ("source-timing-candidate" if frames and not anomalies else
                   "audio-timing-incomplete"),
        "audioStreamIndex": index,
        "sourceTimebase": as_rational_dict(timebase),
        "sampleRateHz": int(sample_rate), "channels": channels,
        "frames": frames, "ptsAnomalies": anomalies,
    }
