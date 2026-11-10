"""Evidence-gated per-utterance links from speech to visible characters.

No face/voice identification and no cluster-wide inference across scenes.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from kumiki_reference_lab.reviews.character_scene import load_character_scene, validate_character_scene

SCHEMA_VERSION = "kumiki.character-speech-link-review.v1"
_CONFIDENCES = {"low", "medium", "high", "unresolved"}


def _load_review(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
        raise ValueError("character speech link review must be regular JSON under 256 KiB")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate link review JSON key")
            result[key] = value
        return result

    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda k: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid link review JSON") from exc
    if (not isinstance(data, dict) or set(data) !=
            {"schemaVersion", "sourceSha256", "sourceStreamIndex", "sourceTimebase", "reviewer", "links"}):
        raise ValueError("link review requires exact source, reviewer and links fields")
    return data


def link_characters_to_speech(speech_scene_path: Path, visual_scene_path: Path,
                              link_review_path: Path, out: Path) -> Path:
    """Create a source-bound scene, changing only explicitly evidenced utterances."""
    if out.exists() or out.is_symlink():
        raise ValueError("output must be a new, nonexisting directory")
    speech = load_character_scene(speech_scene_path)
    visual = load_character_scene(visual_scene_path)
    links = _load_review(link_review_path)
    if links["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("unsupported character speech link schema")
    for name, record in (("visual", visual), ("link review", links)):
        if (record.get("sourceSha256") != speech["sourceSha256"] or
                record.get("sourceStreamIndex") != speech["sourceStreamIndex"] or
                record.get("sourceTimebase") != speech["sourceTimebase"]):
            raise ValueError(f"{name} does not match the speech source fingerprint and clock")
    if visual["utterances"]:
        raise ValueError("visual scene must not already include independent speech segments")
    sw, vw = speech["window"], visual["window"]
    if not sw["startPts"] <= vw["startPts"] < vw["endPts"] <= sw["endPts"]:
        raise ValueError("visual review window must be bounded by speech window")
    if not isinstance(links["reviewer"], dict) or set(links["reviewer"]) != {"kind", "id"}:
        raise ValueError("link reviewer must have kind and id")
    reviewer = links["reviewer"]
    if (reviewer["kind"] not in ("human", "model") or
            type(reviewer["id"]) is not str or not 2 <= len(reviewer["id"].strip()) <= 100):
        raise ValueError("invalid link reviewer identity")
    if not isinstance(links["links"], list) or len(links["links"]) > 500:
        raise ValueError("link records must be a bounded list")
    roster_visual = {c["id"]: c for c in visual["characters"]}
    voice_roster = {c["id"]: c for c in speech["characters"]}
    if any(c["kind"] == "voice-only" for c in visual["characters"]):
        raise ValueError("visual scene cannot contain voice-only characters")
    if any(c["kind"] != "voice-only" for c in speech["characters"]):
        raise ValueError("speech scene roster must contain only voice-only speakers")
    if set(roster_visual) & set(voice_roster):
        raise ValueError("visual character IDs collide with voice cluster IDs")
    if (speech["appearances"] or speech["actions"] or speech["identityClaims"] or
            visual["identityClaims"]):
        raise ValueError("link pipeline expects separate speaker and visual observations without identity claims")
    utterances = [dict(row) for row in speech["utterances"]]
    seen: set[int] = set()
    linked = []
    for i, row in enumerate(links["links"]):
        required = {"utteranceIndex", "characterId", "evidencePts", "evidenceType",
                    "observation", "confidence"}
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError(f"link {i} must have exact evidence fields")
        index, cid, pts = row["utteranceIndex"], row["characterId"], row["evidencePts"]
        if type(index) is not int or not 0 <= index < len(utterances) or index in seen:
            raise ValueError(f"link {i} duplicate or invalid utterance index")
        seen.add(index)
        if type(cid) is not str or cid not in roster_visual:
            raise ValueError(f"link {i} unknown visible character")
        original = utterances[index]
        if type(pts) is not int or not original["startPts"] <= pts < original["endPts"]:
            raise ValueError(f"link {i} lacks a speech PTS anchor")
        if not any(a["characterId"] == cid and a["startPts"] <= pts < a["endPts"]
                   for a in visual["appearances"]):
            raise ValueError(f"link {i} character not visibly reviewed at speech anchor")
        if row["evidenceType"] != "visible-lip-motion":
            raise ValueError("active-speaker links require explicit visible-lip-motion evidence")
        observation = row["observation"]
        if type(observation) is not str or not 12 <= len(observation.strip()) <= 1000:
            raise ValueError("link observation must be a meaningful bounded statement")
        confidence = row["confidence"]
        if type(confidence) is not str or confidence not in _CONFIDENCES:
            raise ValueError("link confidence unsupported")
        if confidence == "unresolved":
            raise ValueError("unresolved lip-motion observations cannot force attribution")
        utterances[index] = {
            **original, "speakerId": cid, "speakerEvidence": "visible-lip-motion",
            "confidence": "low" if reviewer["kind"] == "model" else confidence,
        }
        linked.append({"utteranceIndex": index, "visualCharacterId": cid,
                       "originalVoiceId": original["speakerId"], "evidencePts": pts,
                       "reviewerConfidence": confidence, "observation": observation})
    retained_voices = {u["speakerId"] for u in utterances if u["speakerId"] in voice_roster}
    result = {
        **speech, "reviewer": dict(reviewer),
        "characters": visual["characters"] + [voice_roster[x] for x in sorted(retained_voices)],
        "appearances": visual["appearances"], "actions": visual["actions"],
        "utterances": utterances,
    }
    validate_character_scene(result)
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": speech["sourceSha256"],
        "reviewer": reviewer, "links": linked,
        "linkedUtteranceCount": len(linked),
        "unlinkedUtteranceCount": len(utterances) - len(linked),
        "reviewStatus": "reviewer-asserted-lip-motion-not-independently-verified",
        "limits": "No automatic lip detection, person identity, voiceprint recognition or proof of lip sync. "
                  "Only explicitly linked utterances change speaker; no track-wide assignment.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-speech-link-", dir=out.parent) as temp_name:
        temp = Path(temp_name)
        (temp / "character-scene.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        (temp / "character-speech-links.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        os.replace(temp, out)
    return out / "character-scene.json"
