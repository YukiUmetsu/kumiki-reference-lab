"""Local opt-in whisper.cpp ASR for source-bound, unattributed character dialogue.

No downloads, face identification, diarization or demographic inference.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError, probe_media
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import parse_rational
from kumiki_reference_lab.reviews.character_scene import (
    SCHEMA_VERSION as CHARACTER_SCENE_VERSION, validate_character_scene,
)

SCHEMA_VERSION = "kumiki.local-speech-transcription.v1"
_MEDIA_EXTENSIONS = frozenset({".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi"})
_LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}\Z")


def _run_command(args: list[str], *, timeout: int, stage: str) -> None:
    """Run local subprocesses without a shell or unbounded output capture."""
    try:
        done = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise ValueError(f"{stage} executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"{stage} timed out") from exc
    except OSError as exc:
        raise ValueError(f"{stage} could not start") from exc
    if done.returncode:
        raise ValueError(f"{stage} failed (exit code {done.returncode})")


def _round_pts(seconds: Fraction, timebase: Fraction) -> int:
    """Nearest PTS tick, half away from zero; never map through video FPS."""
    value = seconds / timebase
    absolute = abs(value)
    nearest = (2 * absolute.numerator + absolute.denominator) // (2 * absolute.denominator)
    return nearest if value >= 0 else -nearest


def _language_code(json_value: Any, requested: str) -> str:
    if requested != "auto":
        return requested
    if (isinstance(json_value, dict) and isinstance(json_value.get("language"), str)
            and _LANGUAGE.fullmatch(json_value["language"])):
        return json_value["language"]
    return "und"


def _parse_whisper_json(data: Any, *, max_duration_ms: int, audio_start: Fraction,
                        video_timebase: Fraction, lang: str) -> list[dict[str, Any]]:
    """whisper.cpp -oj offsets.from/to are integer milliseconds."""
    if not isinstance(data, dict) or not isinstance(data.get("transcription"), list):
        raise ValueError("whisper.cpp output lacks transcription segments")
    segments = data["transcription"]
    if len(segments) > 1000:
        raise ValueError("whisper.cpp produced more than 1000 segments")
    utterances = []
    for index, item in enumerate(segments):
        if not isinstance(item, dict) or not isinstance(item.get("offsets"), dict):
            raise ValueError(f"whisper.cpp segment {index} lacks offsets")
        offsets = item["offsets"]
        lo, hi = offsets.get("from"), offsets.get("to")
        if (type(lo) is not int or type(hi) is not int or
                not 0 <= lo < hi <= max_duration_ms):
            raise ValueError(f"whisper.cpp segment {index} has invalid millisecond offsets")
        value = item.get("text")
        if type(value) is not str or not 1 <= len(value.strip()) <= 4000:
            raise ValueError(f"whisper.cpp segment {index} lacks bounded text")
        start_pts = _round_pts(audio_start + Fraction(lo, 1000), video_timebase)
        end_pts = _round_pts(audio_start + Fraction(hi, 1000), video_timebase)
        if start_pts >= end_pts:
            raise ValueError(f"whisper.cpp segment {index} collapses at video timebase")
        utterances.append({
            "speakerId": None, "startPts": start_pts, "endPts": end_pts,
            "text": value.strip(), "language": lang,
            "transcriptEvidence": "speech", "speakerEvidence": "unknown",
            "confidence": "low",
        })
    return utterances


def _audio_stream(metadata: dict[str, Any]) -> tuple[int, Fraction, int]:
    """Require original audio stream start PTS; never guess using frame rate."""
    streams = metadata.get("streams")
    if not isinstance(streams, list):
        raise ProbeError("ffprobe returned no stream inventory")
    audio = next((x for x in streams if isinstance(x, dict) and x.get("codec_type") == "audio"), None)
    if audio is None:
        raise ProbeError("source has no audio stream")
    audio_index, start_pts = audio.get("index"), audio.get("start_pts")
    timebase = parse_rational(audio.get("time_base"))
    if (type(audio_index) is not int or not 0 <= audio_index <= 64 or
            timebase is None or type(start_pts) is not int):
        raise ProbeError("audio stream lacks valid index, timebase or start_pts")
    return audio_index, timebase, start_pts


def transcribe_local_video(source: Path, out: Path, *, model: Path,
                           whisper_cli: str = "whisper-cli", ffmpeg: str = "ffmpeg",
                           ffprobe: str = "ffprobe", max_seconds: int = 30,
                           timeout_seconds: int = 600, language: str = "auto",
                           rights_status: str = "review-required",
                           retain_audio: bool = False) -> Path:
    """Run local ASR and atomically publish an unattributed dialogue scene.

    Alignment assumes the first decoded audio sample corresponds to audio
    start_pts. Encoder delay or timestamp discontinuities may violate that.
    """
    if type(retain_audio) is not bool:
        raise ValueError("retain_audio must be a boolean")
    if type(max_seconds) is not int or not 1 <= max_seconds <= 120:
        raise ValueError("max_seconds must be 1–120")
    if type(timeout_seconds) is not int or not 30 <= timeout_seconds <= 3600:
        raise ValueError("timeout_seconds must be 30–3600")
    if type(language) is not str or (language != "auto" and not _LANGUAGE.fullmatch(language)):
        raise ValueError("language must be auto or a short language code")
    if (not source.is_file() or source.is_symlink() or
            source.suffix.lower() not in _MEDIA_EXTENSIONS):
        raise ValueError("source must be an existing local regular video file")
    if model.is_symlink() or not model.is_file() or not 0 < model.stat().st_size <= 10 * 1024**3:
        raise ValueError("model must be a nonempty local regular file, max 10 GiB")
    if out.exists() or out.is_symlink():
        raise ValueError("output must be a new, nonexisting directory")

    source_signature = file_signature(source)
    model_signature = file_signature(model)
    source_info = inspect_source(source, ffprobe=ffprobe, rights_status=rights_status)
    audio_index, audio_tb, audio_start_pts = _audio_stream(probe_media(source, ffprobe=ffprobe))
    video_tb_data = source_info["video"]["sourceTimebase"]
    video_tb = Fraction(video_tb_data["numerator"], video_tb_data["denominator"])
    audio_origin = audio_start_pts * audio_tb
    model_sha = sha256_file(model)
    require_unchanged(model, model_signature)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".kumiki-speech-", dir=out.parent) as temp_name:
        temp = Path(temp_name)
        wav = temp / "speech.wav"
        prefix = temp / "whisper"
        _run_command([
            ffmpeg, "-nostdin", "-hide_banner", "-v", "error",
            "-protocol_whitelist", "file,pipe", "-i", str(source.resolve()),
            "-map", f"0:{audio_index}", "-vn", "-t", str(max_seconds),
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav",
            str(wav),
        ], timeout=min(240, 30 + max_seconds * 4), stage="ffmpeg audio extraction")
        if not wav.is_file() or not 44 < wav.stat().st_size <= 1_048_576 + 60_000 * max_seconds:
            raise ValueError("decoded WAV missing or exceeds bounded size")
        try:
            with wave.open(str(wav), "rb") as audio:
                if (audio.getnchannels() != 1 or audio.getsampwidth() != 2 or
                        audio.getframerate() != 16000):
                    raise ValueError("decoded audio is not mono PCM16 at 16 kHz")
                sample_count = audio.getnframes()
        except (wave.Error, EOFError, OSError) as exc:
            raise ValueError("decoded audio is not valid WAV") from exc
        if not 0 < sample_count <= max_seconds * 16000 + 2048:
            raise ValueError("decoded audio samples exceed scan budget or are empty")
        audio_sha = sha256_file(wav)
        window_start = _round_pts(audio_origin, video_tb)
        window_end = _round_pts(audio_origin + Fraction(sample_count, 16000), video_tb)
        if window_end <= window_start:
            raise ValueError("decoded audio window smaller than source video timebase")
        _run_command([
            whisper_cli, "-m", str(model.resolve()), "-f", str(wav),
            "-l", language, "-oj", "-of", str(prefix),
        ], timeout=timeout_seconds, stage="whisper.cpp transcription")
        transcript_path = temp / "whisper.json"
        if (transcript_path.is_symlink() or not transcript_path.is_file() or
                transcript_path.stat().st_size > 2 * 1024 * 1024):
            raise ValueError("whisper.cpp JSON missing or exceeds 2 MiB")

        def unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate Whisper JSON property: {key}")
                result[key] = value
            return result

        try:
            transcript = json.loads(transcript_path.read_text(encoding="utf-8"),
                                    object_pairs_hook=unique_fields,
                                    parse_constant=lambda value: (_ for _ in ()).throw(
                                        ValueError("non-finite Whisper JSON")))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("whisper.cpp JSON is invalid") from exc
        if not isinstance(transcript, dict):
            raise ValueError("whisper.cpp JSON root must be an object")
        lang = _language_code(transcript.get("result"), language)
        utterances = _parse_whisper_json(
            transcript, max_duration_ms=sample_count * 1000 // 16000,
            audio_start=audio_origin,
                                         video_timebase=video_tb, lang=lang)
        scene = {
            "schemaVersion": CHARACTER_SCENE_VERSION,
            "sourceSha256": source_info["source"]["sha256"],
            "sourceStreamIndex": source_info["video"]["streamIndex"],
            "sourceTimebase": video_tb_data,
            "reviewer": {"kind": "model", "id": "whisper.cpp-local-asr"},
            "window": {"startPts": window_start, "endPts": window_end,
                       "coverage": "partial-window"},
            "characters": [], "appearances": [], "actions": [],
            "utterances": utterances, "identityClaims": [],
        }
        validate_character_scene(scene)
        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "sourceSha256": scene["sourceSha256"], "modelSha256": model_sha,
            "sourceAudioStreamIndex": audio_index,
            "audioSourceTimebase": {"numerator": audio_tb.numerator,
                                    "denominator": audio_tb.denominator},
            "audioStartPts": audio_start_pts, "sourceVideoTimebase": video_tb_data,
            "requestedWindowSeconds": max_seconds,
            "decodedAudioSamples": sample_count, "sampleRateHz": 16000,
            "decodedAudioSha256": audio_sha, "retainedAudio": retain_audio,
            "utteranceCount": len(utterances), "language": lang,
            "rightsStatus": rights_status,
            "clockMapping": "whisper-offset-ms-plus-ffprobe-audio-start-pts-to-video-pts",
            "alignmentLimit": "Audio first decoded sample is assumed aligned to audio start_pts; "
                              "encoder delay and timestamp discontinuities are not calibrated.",
            "evidenceStatus": "model-generated-transcript-unverified; no-speaker-identification",
        }
        require_unchanged(source, source_signature)
        require_unchanged(model, model_signature)
        (temp / "character-scene.json").write_text(
            json.dumps(scene, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (temp / "speech-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if retain_audio:
            wav.rename(temp / "audio-for-diarization.wav")
        else:
            wav.unlink()
        transcript_path.unlink()
        os.replace(temp, out)
    return out / "character-scene.json"
