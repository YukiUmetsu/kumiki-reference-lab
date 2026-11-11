"""Deterministic, bounded audio energy and transient hints from ephemeral source media.

No speech recognition, music classification, beat certainty, or sync claim.
Runs BEFORE source media is removed by the online video runner.
"""
from __future__ import annotations

import math
import statistics
import struct
import subprocess
from pathlib import Path
from typing import Any

from kumiki_reference_lab.backends.ffmpeg.probe import probe_media

SCHEMA_VERSION = "kumiki.online-audio-cues.v1"
_RATE = 8000
_WINDOW = 800  # one 100ms energy window
_MAX_OUTPUT_WINDOWS = 36000


def _rms_dbfs(pcm: bytes) -> tuple[float, float]:
    if len(pcm) % 2 or not pcm:
        raise ValueError("invalid PCM audio window")
    ints = [n[0] for n in struct.iter_unpack("<h", pcm)]
    rms = math.sqrt(sum(n * n for n in ints) / len(ints)) / 32768.0
    peak = max(abs(n) for n in ints) / 32768.0
    return (round(20 * math.log10(max(rms, 1e-6)), 4),
            round(20 * math.log10(max(peak, 1e-6)), 4))


def _read_window(pipe: Any, size: int) -> bytes:
    remaining = size
    parts = []
    while remaining:
        chunk = pipe.read(remaining)
        if not chunk:
            break
        parts.append(chunk)
        remaining -= len(chunk)
    return b"".join(parts)


def build_online_audio_cues(
    source: Path, *, max_seconds: int = 180, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    if (type(max_seconds) is not int or not 1 <= max_seconds <= 3600
            or not source.is_file() or source.is_symlink()):
        raise ValueError("invalid bounded audio source")
    streams = probe_media(source, ffprobe=ffprobe).get("streams")
    if not isinstance(streams, list):
        raise ValueError("audio stream inventory invalid")
    audio = next((s for s in streams
                  if isinstance(s, dict) and s.get("codec_type") == "audio"), None)
    base = {
        "schemaVersion": SCHEMA_VERSION,
        "analysisWindowMaxSeconds": max_seconds,
        "pcmSampleRateHz": _RATE,
        "windowMs": 100,
        "audioStreamIndex": audio.get("index") if audio else None,
        "frames": [],
        "transientCandidates": [],
        "audioVideoClockStatus": "not-independently-aligned",
        "limits": [
            "Energy rises are not verified beats, sound effects, dialogue or musical cues.",
            "Audio PCM offset can differ from the video's decoded presentation origin.",
            "Candidates may be compression, speech attacks or background noise.",
        ],
    }
    if audio is None:
        return {**base, "status": "no-audio-stream"}
    if (type(audio.get("index")) is not int or not
            0 <= audio["index"] <= 64):
        raise ValueError("invalid audio stream index")
    cmd = [
        ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
        "-protocol_whitelist", "file,pipe",
        "-i", str(source.resolve()), "-map", f"0:{audio['index']}",
        "-vn", "-sn", "-dn", "-t", str(max_seconds),
        "-ac", "1", "-ar", str(_RATE), "-f", "s16le", "pipe:1",
    ]
    try:
        process = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise ValueError("FFmpeg audio analysis could not start") from exc
    frames: list[dict[str, Any]] = []
    try:
        assert process.stdout is not None
        while len(frames) < _MAX_OUTPUT_WINDOWS:
            raw = _read_window(process.stdout, _WINDOW * 2)
            if not raw:
                break
            if len(raw) % 2:
                raise ValueError("decoded PCM audio is malformed")
            rms, peak = _rms_dbfs(raw)
            frames.append({
                "decodedOffsetMs": len(frames) * 100,
                "rmsDbfs": rms, "peakDbfs": peak,
                "nearSilenceCandidate": rms <= -48,
            })
            if len(raw) < _WINDOW * 2:
                break
        process.stdout.close()
        try:
            code = process.wait(timeout=30)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("audio decoder did not exit after bounded scan") from exc
        if code:
            raise ValueError("FFmpeg audio decoding failed")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    if not frames:
        return {**base, "status": "no-decodable-audio-window"}
    candidates = []
    for i in range(2, len(frames) - 1):
        current = frames[i]["rmsDbfs"]
        previous = statistics.median(
            f["rmsDbfs"] for f in frames[max(0, i - 5):i])
        rise = current - previous
        if (rise >= 8 and current >= -38
                and current >= frames[i - 1]["rmsDbfs"]
                and current >= frames[i + 1]["rmsDbfs"]):
            candidates.append({
                "decodedOffsetMs": frames[i]["decodedOffsetMs"],
                "riseDb": round(rise, 4),
                "rmsDbfs": current,
                "status": "unverified-local-energy-attack",
            })
    return {
        **base, "status": "measured-decoded-audio-envelope",
        "frames": frames,
        "transientCandidates": candidates[:10000],
        "summary": {
            "measuredAudioWindowCount": len(frames),
            "durationSecondsApprox": round(len(frames) / 10, 2),
            "medianRmsDbfs": round(statistics.median(
                f["rmsDbfs"] for f in frames), 4),
            "nearSilenceWindowFraction": round(sum(
                f["nearSilenceCandidate"] for f in frames) / len(frames), 5),
        },
    }
