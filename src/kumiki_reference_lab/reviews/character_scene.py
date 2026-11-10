"""Source-PTS-bound character observations, actions and speaker evidence.

This is a *review data contract*, not a detector, diarizer or identity system.
Unverified demographic attributes cannot be inferred from appearance.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kumiki.character-scene-review.v1"
_SUMMARY_VERSION = "kumiki.character-scene-summary.v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
_LANG = re.compile(r"(?:[a-z]{2,3}|und)(?:-[A-Za-z0-9]{2,8}){0,3}\Z")
_CONFIDENCE = {"high", "medium", "low", "unresolved"}
_KINDS = {"human", "animated-human", "animal", "anthropomorphic", "other", "voice-only"}
_MODALITIES = {"speech", "subtitle", "script"}
_SPEAKER_EVIDENCE = {"visible-lip-motion", "speaker-diarization", "explicit-caption", "voice-over", "unknown"}
_IDENTITY_ATTRIBUTES = {"name", "age", "gender-identity", "ethnicity"}
_CLAIM_EVIDENCE = {"explicit-dialogue", "onscreen-text", "creator-metadata"}


def _fields(raw: Any, keys: set[str], location: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != keys:
        raise ValueError(f"{location} must have exact fields: {', '.join(sorted(keys))}")
    return raw


def _text(value: Any, location: str, *, max_length: int = 600, min_length: int = 1) -> str:
    if type(value) is not str or not min_length <= len(value.strip()) <= max_length:
        raise ValueError(f"{location} must be {min_length}-{max_length} characters")
    return value


def _pts(value: Any, start: int, end: int, name: str) -> int:
    if type(value) is not int or not start <= value < end:
        raise ValueError(f"{name} PTS outside source review window")
    return value


def _interval(item: dict[str, Any], window_start: int, window_end: int, location: str) -> tuple[int, int]:
    lo, hi = item["startPts"], item["endPts"]
    if (type(lo) is not int or type(hi) is not int or not window_start <= lo < hi <= window_end):
        raise ValueError(f"{location} must have ordered source PTS within review window")
    return lo, hi


def _anchors(item: dict[str, Any], lo: int, hi: int, location: str) -> None:
    points = item["anchorPts"]
    if (not isinstance(points, list) or not 1 <= len(points) <= 8 or
            any(type(p) is not int or not lo <= p < hi for p in points) or
            points != sorted(set(points))):
        raise ValueError(f"{location} requires 1–8 distinct source PTS anchors in interval")


def _confidence(value: Any, location: str) -> None:
    if type(value) is not str or value not in _CONFIDENCE:
        raise ValueError(f"{location} confidence must be high, medium, low or unresolved")


def _bounded_list(value: Any, name: str, maximum: int) -> list:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{name} exceeds {maximum} entries or is not a list")
    return value


def load_character_scene(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 512 * 1024:
        raise ValueError("character scene must be a regular JSON file under 512 KiB")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON property: {key}")
            result[key] = value
        return result

    try:
        review = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                            parse_constant=lambda value: (_ for _ in ()).throw(
                                ValueError(f"non-finite JSON value: {value}")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"invalid character scene JSON: {exc}") from exc
    validate_character_scene(review)
    return review


def validate_character_scene(review: Any) -> None:
    top = _fields(review, {"schemaVersion", "sourceSha256", "sourceStreamIndex",
                           "sourceTimebase", "reviewer", "window", "characters",
                           "appearances", "actions", "utterances", "identityClaims"}, "character scene")
    if top["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError("unsupported character scene version")
    if type(top["sourceSha256"]) is not str or not _SHA.fullmatch(top["sourceSha256"]):
        raise ValueError("sourceSha256 must be a lowercase SHA-256")
    if type(top["sourceStreamIndex"]) is not int or not 0 <= top["sourceStreamIndex"] <= 64:
        raise ValueError("sourceStreamIndex must be an actual nonnegative video stream index")
    tb = _fields(top["sourceTimebase"], {"numerator", "denominator"}, "sourceTimebase")
    n, d = tb["numerator"], tb["denominator"]
    if (type(n) is not int or type(d) is not int or not 1 <= n <= 10**12 or
            not 1 <= d <= 10**12 or n > d):
        raise ValueError("sourceTimebase must be a valid positive rational up to one second")
    reviewer = _fields(top["reviewer"], {"kind", "id"}, "reviewer")
    if reviewer["kind"] not in ("human", "model"):
        raise ValueError("reviewer.kind must be human or model")
    _text(reviewer["id"], "reviewer.id", max_length=100, min_length=2)
    window = _fields(top["window"], {"startPts", "endPts", "coverage"}, "window")
    start, end = window["startPts"], window["endPts"]
    if (type(start) is not int or type(end) is not int or not -(2**63) < start < end < 2**63 or
            window["coverage"] not in ("partial-window", "full-window-declared")):
        raise ValueError("window needs ordered source PTS and a valid declared coverage")
    unit = Fraction(n, d)
    if not Fraction(1, 1000) <= (end - start) * unit <= 86400:
        raise ValueError("window duration must be 1 ms to 24 hours")

    characters = _bounded_list(top["characters"], "characters", 100)
    ids = set()
    for i, raw in enumerate(characters):
        who = _fields(raw, {"id", "kind", "label", "visualDescription"}, f"character[{i}]")
        cid = who["id"]
        if type(cid) is not str or not _ID.fullmatch(cid) or cid in ids:
            raise ValueError(f"invalid or duplicate character id: {cid}")
        ids.add(cid)
        if type(who["kind"]) is not str or who["kind"] not in _KINDS:
            raise ValueError(f"character[{i}] kind unsupported")
        _text(who["label"], "character.label", max_length=120)
        if who["kind"] == "voice-only":
            if who["visualDescription"] is not None:
                raise ValueError("voice-only character must not have invented visual appearance")
        else:
            _text(who["visualDescription"], "character.visualDescription", max_length=800)

    for collection_name, maximum in (("appearances", 1000), ("actions", 2000), ("utterances", 3000)):
        _bounded_list(top[collection_name], collection_name, maximum)
    for i, raw in enumerate(top["appearances"]):
        entry = _fields(raw, {"characterId", "startPts", "endPts", "anchorPts",
                              "visibleTraits", "anchorBox", "observation", "confidence"}, f"appearance[{i}]")
        cid = entry["characterId"]
        if type(cid) is not str or cid not in ids or next(x for x in characters if x["id"] == cid)["kind"] == "voice-only":
            raise ValueError(f"appearance[{i}] refers to an unknown or voice-only character")
        lo, hi = _interval(entry, start, end, f"appearance[{i}]")
        _anchors(entry, lo, hi, f"appearance[{i}]")
        traits = _bounded_list(entry["visibleTraits"], "visibleTraits", 15)
        if any(type(t) is not str for t in traits) or len(traits) != len(set(traits)):
            raise ValueError("visibleTraits must be distinct strings")
        for t in traits:
            _text(t, "visible trait", max_length=120)
        box = entry["anchorBox"]
        if box is not None:
            if (not isinstance(box, list) or len(box) != 4 or
                    any(type(v) not in (float, int) or not 0 <= v <= 1 for v in box) or
                    box[2] <= 0 or box[3] <= 0 or box[0]+box[2] > 1 or box[1]+box[3] > 1):
                raise ValueError("anchorBox must be null or normalized [x,y,width,height]")
        _text(entry["observation"], "appearance.observation")
        _confidence(entry["confidence"], "appearance")

    for i, raw in enumerate(top["actions"]):
        entry = _fields(raw, {"actorId", "targetId", "action", "startPts", "endPts",
                              "anchorPts", "observation", "confidence"}, f"action[{i}]")
        if (type(entry["actorId"]) is not str or entry["actorId"] not in ids or
                entry["targetId"] is not None and (type(entry["targetId"]) is not str or entry["targetId"] not in ids)):
            raise ValueError(f"action[{i}] unknown actor or target")
        if entry["actorId"] == entry["targetId"]:
            raise ValueError(f"action[{i}] cannot target the actor itself")
        if next(x for x in characters if x["id"] == entry["actorId"])["kind"] == "voice-only":
            raise ValueError("voice-only speaker cannot have a physical action")
        _text(entry["action"], "action name", max_length=100)
        lo, hi = _interval(entry, start, end, f"action[{i}]")
        _anchors(entry, lo, hi, f"action[{i}]")
        _text(entry["observation"], "action observation")
        _confidence(entry["confidence"], "action")

    for i, raw in enumerate(top["utterances"]):
        item = _fields(raw, {"speakerId", "startPts", "endPts", "text", "language",
                             "transcriptEvidence", "speakerEvidence", "confidence"}, f"utterance[{i}]")
        if item["speakerId"] is not None and (type(item["speakerId"]) is not str or item["speakerId"] not in ids):
            raise ValueError(f"utterance[{i}] refers to unknown speaker")
        _interval(item, start, end, f"utterance[{i}]")
        _text(item["text"], "utterance text", max_length=4000)
        if type(item["language"]) is not str or not _LANG.fullmatch(item["language"]):
            raise ValueError("utterance.language must be a BCP47-like language code or und")
        if (type(item["transcriptEvidence"]) is not str or item["transcriptEvidence"] not in _MODALITIES or
                type(item["speakerEvidence"]) is not str or item["speakerEvidence"] not in _SPEAKER_EVIDENCE):
            raise ValueError("utterance requires explicit transcript and speaker evidence types")
        if item["speakerId"] is None and item["speakerEvidence"] != "unknown":
            raise ValueError("unattributed speech must use unknown speaker evidence")
        _confidence(item["confidence"], "utterance")

    claims = _bounded_list(top["identityClaims"], "identityClaims", 100)
    for i, raw in enumerate(claims):
        claim = _fields(raw, {"characterId", "attribute", "value", "evidenceKind",
                              "evidencePts", "evidenceText", "confidence"}, f"identityClaim[{i}]")
        if (type(claim["characterId"]) is not str or claim["characterId"] not in ids or
                type(claim["attribute"]) is not str or claim["attribute"] not in _IDENTITY_ATTRIBUTES):
            raise ValueError("identity claim must refer to a known character and supported attribute")
        _text(claim["value"], "identity claim value", max_length=120)
        if type(claim["evidenceKind"]) is not str or claim["evidenceKind"] not in _CLAIM_EVIDENCE:
            raise ValueError("demographic identity cannot be inferred from appearance")
        _pts(claim["evidencePts"], start, end, "identity claim")
        _text(claim["evidenceText"], "identity claim evidence", max_length=500)
        _confidence(claim["confidence"], "identity claim")


def summarize_character_scene(review: dict[str, Any]) -> dict[str, Any]:
    """Summarize self-declared event annotations; never extrapolate gaps or identities."""
    validate_character_scene(review)
    window = review["window"]
    tb = review["sourceTimebase"]
    sec_per_tick = Fraction(tb["numerator"], tb["denominator"])
    action_count = Counter(item["actorId"] for item in review["actions"])
    appearance_count = Counter(item["characterId"] for item in review["appearances"])
    speaking_count = Counter(item["speakerId"] for item in review["utterances"] if item["speakerId"] is not None)
    edge_count = Counter((item["actorId"], item["targetId"]) for item in review["actions"]
                         if item["targetId"] is not None)
    traits_by_character = {c["id"]: set() for c in review["characters"]}
    for item in review["appearances"]:
        traits_by_character[item["characterId"]].update(item["visibleTraits"])
    return {
        "schemaVersion": _SUMMARY_VERSION,
        "sourceSha256": review["sourceSha256"],
        "windowSeconds": round(float((window["endPts"] - window["startPts"]) * sec_per_tick), 6),
        "coverage": window["coverage"],
        "characterCount": len(review["characters"]),
        "appearanceCount": len(review["appearances"]),
        "actionCount": len(review["actions"]),
        "interactionCount": sum(item["targetId"] is not None for item in review["actions"]),
        "utteranceCount": len(review["utterances"]),
        "unattributedUtterances": sum(item["speakerId"] is None for item in review["utterances"]),
        "identityClaims": len(review["identityClaims"]),
        "characters": [{"id": character["id"], "label": character["label"],
                        "kind": character["kind"],
                        "visualDescription": character["visualDescription"],
                        "visibleTraits": sorted(traits_by_character[character["id"]]),
                        "appearances": appearance_count[character["id"]],
                        "actions": action_count[character["id"]],
                        "attributedUtterances": speaking_count[character["id"]]}
                       for character in review["characters"]],
        "interactionPairs": [{"actorId": actor, "targetId": target, "eventCount": count}
                             for (actor, target), count in sorted(edge_count.items())],
        "actionTimeline": review["actions"],
        "dialogueTimeline": review["utterances"],
        "sourcedIdentityClaims": review["identityClaims"],
        "reviewStatus": "reviewer-declared-not-independently-media-verified",
        "methodLimits": [
            "No automatic character detection, speaker diarization, transcription or identity recognition was performed.",
            "Identity attributes require explicit quoted speech, on-screen text or source metadata; never infer ethnicity or gender identity from appearance.",
            "Character IDs are local to a single source; continuity and speaker attribution are reviewer assertions.",
            "Event counts describe submitted annotations, not all actions or speech in the video.",
        ],
    }
