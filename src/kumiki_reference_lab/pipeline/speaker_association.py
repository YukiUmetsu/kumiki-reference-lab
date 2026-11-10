"""Conservative offline RTTM voice-cluster association with ASR utterances.

Voice labels are not personal identities or visible character assignments.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import defaultdict
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.pipeline.speech_transcribe import _round_pts
from kumiki_reference_lab.reviews.character_scene import load_character_scene, validate_character_scene

SCHEMA_VERSION = "kumiki.speaker-diarization-association.v1"
_TIME = re.compile(r"[0-9]{1,6}(?:\.[0-9]{1,6})?\Z")
_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_-]{0,63}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
        raise ValueError("speech manifest must be regular JSON under 256 KiB")

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate speech manifest field: {key}")
            result[key] = value
        return result

    try:
        obj = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates,
                         parse_constant=lambda k: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid speech manifest JSON") from exc
    if not isinstance(obj, dict):
        raise ValueError("speech manifest must be a JSON object")
    return obj


def _clock(scene: dict[str, Any], manifest: dict[str, Any]) -> tuple[Fraction, Fraction, int]:
    if manifest.get("schemaVersion") != "kumiki.local-speech-transcription.v1":
        raise ValueError("unsupported or missing local speech manifest")
    if manifest.get("sourceSha256") != scene["sourceSha256"]:
        raise ValueError("scene and speech manifest source hashes disagree")
    if manifest.get("sourceVideoTimebase") != scene["sourceTimebase"]:
        raise ValueError("scene and speech manifest video timebases disagree")
    tb = manifest.get("audioSourceTimebase")
    if not isinstance(tb, dict) or set(tb) != {"numerator", "denominator"}:
        raise ValueError("audio source timebase missing")
    n, d = tb["numerator"], tb["denominator"]
    if (type(n) is not int or type(d) is not int or not 1 <= n <= 10**12 or
            not 1 <= d <= 10**12 or n > d):
        raise ValueError("audio source timebase invalid")
    audio_start_pts = manifest.get("audioStartPts")
    samples, rate = manifest.get("decodedAudioSamples"), manifest.get("sampleRateHz")
    if (type(audio_start_pts) is not int or not -(2**63) < audio_start_pts < 2**63 or
            type(samples) is not int or not 1 <= samples <= 16000 * 121 or
            type(rate) is not int or rate != 16000):
        raise ValueError("audio start PTS or decoded sample clock invalid")
    model_sha = manifest.get("modelSha256")
    if type(model_sha) is not str or not _SHA.fullmatch(model_sha):
        raise ValueError("missing ASR model SHA-256")
    video = scene["sourceTimebase"]
    video_tb = Fraction(video["numerator"], video["denominator"])
    audio_origin = audio_start_pts * Fraction(n, d)
    if (scene["window"]["startPts"] != _round_pts(audio_origin, video_tb) or
            scene["window"]["endPts"] != _round_pts(
                audio_origin + Fraction(samples, 16000), video_tb)):
        raise ValueError("scene and speech manifest window bounds disagree")
    return audio_origin, video_tb, samples


def _read_rttm(path: Path, duration: Fraction) -> tuple[dict[str, list[tuple[Fraction, Fraction]]], str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 512 * 1024:
        raise ValueError("RTTM must be a regular local file under 512 KiB")
    blob = path.read_bytes()
    try:
        lines = blob.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("RTTM must be UTF-8") from exc
    if len(lines) > 10000:
        raise ValueError("RTTM exceeds 10000 lines")
    speakers: dict[str, list[tuple[Fraction, Fraction]]] = defaultdict(list)
    file_id = None
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 10 or parts[0] != "SPEAKER" or parts[2] != "1":
            raise ValueError(f"RTTM line {lineno} requires a SPEAKER record on channel 1")
        if (not _LABEL.fullmatch(parts[1]) or not _LABEL.fullmatch(parts[7]) or
                any(not _TIME.fullmatch(v) for v in (parts[3], parts[4]))):
            raise ValueError(f"RTTM line {lineno} has unsupported labels or decimal offsets")
        if file_id is None:
            file_id = parts[1]
        elif parts[1] != file_id:
            raise ValueError("RTTM cannot mix different source file IDs")
        start, length = Fraction(Decimal(parts[3])), Fraction(Decimal(parts[4]))
        if length <= 0 or start < 0 or start + length > duration:
            raise ValueError(f"RTTM line {lineno} exceeds decoded audio window")
        speakers[parts[7]].append((start, start + length))
    if len(speakers) > 100:
        raise ValueError("RTTM contains more than 100 voice clusters")
    merged = {}
    for label, rows in speakers.items():
        regions = []
        for a, b in sorted(rows):
            if regions and a <= regions[-1][1]:
                regions[-1] = (regions[-1][0], max(b, regions[-1][1]))
            else:
                regions.append((a, b))
        merged[label] = regions
    return merged, hashlib.sha256(blob).hexdigest()


def _overlap(a: Fraction, b: Fraction, segments: list[tuple[Fraction, Fraction]]) -> Fraction:
    return sum((max(Fraction(0), min(b, y) - max(a, x)) for x, y in segments), Fraction(0))


def associate_speakers(speech_run: Path, rttm_path: Path, out: Path, *,
                       min_coverage: float = 0.80, max_competing: float = 0.10) -> Path:
    """Associate ASR segments with stable *voice clusters*, never visible people.

    Overlapping/ambiguous utterances remain unattributed. RTTM data must be
    relative to the exact audio decoded in the supplied speech run.
    """
    if ((type(min_coverage) not in (float, int) or not 0.5 <= min_coverage <= 1) or
            (type(max_competing) not in (float, int) or not 0 <= max_competing <= 0.25)):
        raise ValueError("coverage thresholds must be sensible finite numbers")
    if out.exists() or out.is_symlink():
        raise ValueError("output must be a new, nonexisting directory")
    scene = load_character_scene(speech_run / "character-scene.json")
    manifest = _load_json(speech_run / "speech-manifest.json")
    audio_origin, video_tb, samples = _clock(scene, manifest)
    if (scene["characters"] or scene["appearances"] or scene["actions"] or
            scene["identityClaims"] or any(x["speakerId"] is not None for x in scene["utterances"])):
        raise ValueError("speaker association accepts only a pristine unattributed ASR scene")
    diarized, rttm_sha = _read_rttm(rttm_path, Fraction(samples, 16000))
    speaker_ids = {label: f"voice_{i:03d}" for i, label in enumerate(sorted(diarized), 1)}
    decisions, out_utterances, used = [], [], set()
    for i, raw in enumerate(scene["utterances"]):
        start = raw["startPts"] * video_tb - audio_origin
        end = raw["endPts"] * video_tb - audio_origin
        length = end - start
        if length <= 0:
            raise ValueError("utterance has zero audio-relative duration")
        scored = sorted(((_overlap(start, end, regions) / length, label)
                         for label, regions in diarized.items()),
                        key=lambda x: (-x[0], x[1]))
        top = scored[0] if scored else (Fraction(0), None)
        runner_up = scored[1][0] if len(scored) > 1 else Fraction(0)
        accepted = bool(top[1] is not None and top[0] >= Fraction(str(min_coverage))
                        and runner_up <= Fraction(str(max_competing)))
        speaker = speaker_ids[top[1]] if accepted else None
        if speaker:
            used.add(top[1])
        out_utterances.append({**raw, "speakerId": speaker,
                               "speakerEvidence": "speaker-diarization" if speaker else "unknown",
                               "confidence": "low"})
        decisions.append({
            "utteranceIndex": i, "startPts": raw["startPts"], "endPts": raw["endPts"],
            "voiceId": speaker, "decision": "voice-cluster-candidate" if accepted else "unknown-or-overlap",
            "bestCoverage": round(float(top[0]), 5), "nextCoverage": round(float(runner_up), 5),
        })
    roster = [{"id": speaker_ids[label], "kind": "voice-only",
               "label": f"Unidentified voice {speaker_ids[label].split('_')[1]}", "visualDescription": None}
              for label in sorted(used)]
    result = {**scene, "reviewer": {"kind": "model", "id": "rttm-voice-cluster-join"},
              "characters": roster, "utterances": out_utterances}
    validate_character_scene(result)
    association = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": scene["sourceSha256"], "asrModelSha256": manifest["modelSha256"],
        "rttmSha256": rttm_sha, "minCoverage": min_coverage, "maxCompeting": max_competing,
        "voiceClusterCount": len(diarized),
        "attributedUtterances": sum(x["speakerId"] is not None for x in out_utterances),
        "unknownUtterances": sum(x["speakerId"] is None for x in out_utterances),
        "voiceClusterMap": [{"rttmSpeaker": label, "voiceId": speaker_ids[label]}
                            for label in sorted(used)],
        "decisions": decisions,
        "evidenceStatus": "unverified-rttm-voice-clusters; not-visual-character-identity",
        "limitations": "RTTM offsets must be relative to the same decoded audio as the speech run. "
                       "Diarization can confuse voices, music and overlap; no independent review.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-voices-", dir=out.parent) as temp_name:
        temp = Path(temp_name)
        (temp / "character-scene.json").write_text(
            json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        (temp / "speaker-association.json").write_text(
            json.dumps(association, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        os.replace(temp, out)
    return out / "character-scene.json"
