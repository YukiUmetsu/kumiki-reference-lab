"""Bounded, local-only audio envelope measurements for real source video.

Audio output is numeric PCM energy summaries only. These are NOT speech,
music, sound-effect, beat, LUFS, or exact source-video PTS classifications.
"""
from __future__ import annotations

import math
import struct
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError, probe_media
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict, parse_rational
from kumiki_reference_lab.pipeline.ollama_character_perception import _VIDEO_EXTENSIONS

SCHEMA_VERSION = "kumiki.source-audio-energy-probe.v1"
_RATE = 8000
_FRAME_SAMPLES = 800
_MAX_AUDIO_BYTES = 480000  # 30 seconds * 8 kHz * 16-bit


def _dbfs(ratio: float) -> float:
    if not 0 <= ratio <= 1.0:
        raise ValueError("PCM amplitude is out of range")
    return round(max(-120.0, 20 * math.log10(ratio)) if ratio else -120.0, 4)


def _stats(raw: bytes, *, expected_samples: int) -> dict[str, Any]:
    if (not raw or len(raw) % 2 or len(raw) > _MAX_AUDIO_BYTES or
            not 1 <= len(raw) // 2 <= expected_samples + 2048):
        raise ValueError("decoded audio PCM is absent, malformed or over budget")
    samples = [sample[0] for sample in struct.iter_unpack("<h", raw)]
    frames = []
    total_squares = 0
    peak = 0
    for begin in range(0, len(samples), _FRAME_SAMPLES):
        values = samples[begin:begin + _FRAME_SAMPLES]
        power = sum(int(x) * int(x) for x in values)
        level = math.sqrt(power/len(values)) / 32768
        maximum = max(abs(int(x)) for x in values) / 32768
        total_squares += power
        peak = max(peak,maximum)
        frames.append({
            "decodedOffsetMs": begin * 1000 // _RATE,
            "sampleCount": len(values),
            "rmsDbfs": _dbfs(level),
            "peakDbfs": _dbfs(maximum),
            "nearSilence": _dbfs(level) <= -48.0,
        })
    return {
        "decodedPcmSampleCount":len(samples),
        "decodedDurationSecondsApprox":round(len(samples)/_RATE,6),
        "frames":frames,
        "summary":{
            "rmsDbfs":_dbfs(math.sqrt(total_squares/len(samples))/32768),
            "peakDbfs":_dbfs(peak),
            "nearSilenceFrameFraction":round(
                sum(frame["nearSilence"] for frame in frames)/len(frames),6),
        },
    }


def analyze_source_audio_window(
    source: Path, *, start_seconds: int = 0, seconds: int = 10,
    rights_status: str = "review-required", ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Decode a short media-timeline interval into mono PCM and measure energy.

    Exact audio/video synchronization is NOT inferred. Requested offsets and
    the audio stream start_pts/timebase are recorded separately so consumers
    cannot silently assume a sample-accurate original video clock alignment.
    """
    if (type(start_seconds) is not int or start_seconds < 0 or
            type(seconds) is not int or not 1 <= seconds <= 30 or
            start_seconds+seconds > 3600):
        raise ValueError("audio analysis needs 1..30 second bounded local video interval")
    if (source.is_symlink() or not source.is_file() or
            source.suffix.lower() not in _VIDEO_EXTENSIONS):
        raise ValueError("audio analysis needs a regular supported local video")
    sig = file_signature(source)
    media = inspect_source(source,ffprobe=ffprobe,rights_status=rights_status)
    tracks = probe_media(source,ffprobe=ffprobe).get("streams")
    if not isinstance(tracks,list):
        raise ProbeError("audio source stream inventory unavailable")
    stream = next((item for item in tracks if isinstance(item,dict) and
                   item.get("codec_type")=="audio"),None)
    if stream is None:
        raise ProbeError("source has no audio stream; silence cannot be inferred")
    index, start_pts = stream.get("index"), stream.get("start_pts")
    timebase = parse_rational(stream.get("time_base"))
    if (type(index) is not int or not 0 <= index <= 64 or
            type(start_pts) is not int or timebase is None):
        raise ProbeError("audio stream index, start PTS or rational timebase invalid")
    command = [
        ffmpeg,"-nostdin","-hide_banner","-loglevel","error",
        "-protocol_whitelist","file,pipe",
        "-i",str(source.resolve()),
        "-map",f"0:{index}","-vn",
        "-ss",str(start_seconds),"-t",str(seconds),
        "-ac","1","-ar",str(_RATE),
        "-f","s16le","pipe:1",
    ]
    try:
        run = subprocess.run(command,stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                             timeout=min(180,30+seconds*4),check=False)
    except FileNotFoundError as exc:
        raise ValueError("ffmpeg audio decoder not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("ffmpeg audio decoder timed out") from exc
    except OSError as exc:
        raise ValueError("ffmpeg audio decoder could not start") from exc
    if run.returncode:
        raise ValueError("ffmpeg audio decoder failed without a measurable output")
    stats = _stats(run.stdout,expected_samples=seconds*_RATE)
    require_unchanged(source,sig)
    return {
        "schemaVersion":SCHEMA_VERSION,
        "sourceSha256":media["source"]["sha256"],
        "videoStreamIndex":media["video"]["streamIndex"],
        "videoSourceTimebase":media["video"]["sourceTimebase"],
        "audioStreamIndex":index,
        "audioSourceTimebase":as_rational_dict(timebase),
        "audioStreamStartPts":start_pts,
        "requestedStartSeconds":start_seconds,
        "requestedSeconds":seconds,
        "decodedPcmSampleRate":_RATE,
        "decodedPcmSampleCount":stats["decodedPcmSampleCount"],
        "decodedDurationSecondsApprox":stats["decodedDurationSecondsApprox"],
        "decodedFrames":stats["frames"],
        "summary":stats["summary"],
        "rightsStatus":media["source"]["rightsStatus"],
        "evidenceStatus":"sampled-pcm-energy-not-original-pts-aligned-or-human-reviewed",
        "methodLimits":[
            "Audio sample windows are positioned by FFmpeg output-side seek; source video PTS alignment is not independently established.",
            "Encoder delay, resampling, stream offsets and timestamp discontinuities can shift audio relative to video.",
            "RMS and peak PCM dBFS are not LUFS, perceived loudness, music beats, narration, voice identity or sound design labels.",
            "Near-silence threshold is a signal-energy heuristic; low levels may include intentional ambient audio.",
            "No PCM bytes, music, speech, soundtrack or private local file paths are stored.",
        ],
    }
