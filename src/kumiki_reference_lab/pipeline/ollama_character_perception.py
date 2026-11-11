"""Opt-in localhost Ollama vision proposals grounded to verified video frames.

This is not character identification, calibrated action recognition, or human QA.
Never sends source images to a non-loopback endpoint.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import math
import re
import tempfile
import os
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.subject_tracklet_review import _validate_report, _select_indices
from kumiki_reference_lab.pipeline.subject_detections import _CLASS_TO_KIND, _check_box
from kumiki_reference_lab.reviews.character_scene import (
    SCHEMA_VERSION as CHARACTER_SCENE_VERSION, validate_character_scene,
)

SCHEMA_VERSION = "kumiki.local-character-vision-proposals.v1"
_ACTIONS = frozenset({
    "none", "walking", "running", "turning", "raising-arm", "lowering-arm",
    "waving", "pointing", "sitting-down", "standing-up", "gesturing",
    "moving-object", "other-visible-motion",
})
# This narrow filter rejects obvious demographic/identity assertions in proposed
# descriptive text; it does not verify that every remaining description is correct.
_DISALLOWED = re.compile(
    r"\b(?:ethnic(?:ity)?|race|racial|nationality|asian|african|caucasian|"
    r"latino|latina|hispanic|japanese|chinese|indian|korean|"
    r"man|woman|men|women|boy|girl|male|female|"
    r"teenager|elderly|middle-aged|years?-old|identity|named)\b",
    flags=re.IGNORECASE,
)
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}\Z")
_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"})


def _parse_model_response(value: Any, *, allow_action: bool) -> dict[str, Any]:
    """Reject prompt-injected or ambiguous model content rather than repairing it."""
    if (not isinstance(value, dict) or
            set(value) != {"appearance", "visibleTraits", "observedAction", "motionEvidence"}):
        raise ValueError("Ollama response must contain exact appearance/action fields")
    appearance = value["appearance"]
    traits = value["visibleTraits"]
    action = value["observedAction"]
    evidence = value["motionEvidence"]
    if (type(appearance) is not str or not 12 <= len(appearance.strip()) <= 450 or
            _DISALLOWED.search(appearance)):
        raise ValueError("visual description missing, unbounded or makes demographic identity claims")
    if (not isinstance(traits, list) or len(traits) > 8 or
            any(type(t) is not str or not 2 <= len(t.strip()) <= 100 or
                _DISALLOWED.search(t) for t in traits) or
            len(set(traits)) != len(traits)):
        raise ValueError("visible traits must be distinct bounded non-demographic descriptions")
    if type(action) is not str or action not in _ACTIONS:
        raise ValueError("observedAction must be a supported movement label or none")
    if type(evidence) is not str or len(evidence) > 400:
        raise ValueError("motionEvidence must be bounded text")
    if not allow_action and action != "none":
        raise ValueError("single frames cannot support an action proposal")
    if action != "none" and len(evidence.strip()) < 12:
        raise ValueError("action proposals need concrete visual motion evidence")
    if _DISALLOWED.search(evidence):
        raise ValueError("motion evidence contains demographic identity claims")
    return {"appearance": appearance.strip(), "visibleTraits": traits,
            "observedAction": action, "motionEvidence": evidence.strip()}


def _crop_rgb(pixels: bytes, width: int, height: int,
              box: list[float]) -> tuple[bytes, int, int]:
    x, y, w, h = _check_box(box, "vision crop box")
    if len(pixels) != width * height * 3:
        raise ValueError("decoded frame size does not match RGB dimensions")
    x0, y0 = max(0, math.floor(x * width)), max(0, math.floor(y * height))
    x1, y1 = min(width, math.ceil((x + w) * width)), min(height, math.ceil((y + h) * height))
    if x1 - x0 < 2 or y1 - y0 < 2:
        raise ValueError("vision crop is too small to inspect")
    row_stride = width * 3
    result = b"".join(pixels[row * row_stride + x0*3:row*row_stride + x1*3]
                      for row in range(y0, y1))
    return result, x1-x0, y1-y0


def _ollama_json(images: list[bytes], *, model: str, port: int,
                 timeout_seconds: int, instruction: str) -> dict[str, Any]:
    """Bounded localhost-only JSON vision inference shared by character and pair reviews."""
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Ollama port must be 1..65535")
    if type(timeout_seconds) is not int or not 5 <= timeout_seconds <= 300:
        raise ValueError("Ollama timeout must be 5..300 seconds")
    if type(model) is not str or not _MODEL.fullmatch(model):
        raise ValueError("Ollama model must be an explicit local model tag")
    if type(instruction) is not str or not 10 <= len(instruction) <= 2200:
        raise ValueError("Ollama instruction must be a bounded prompt")
    if not 1 <= len(images) <= 2 or any(
            not isinstance(image, bytes) or len(image) > 1_000_000 for image in images):
        raise ValueError("vision images must be bounded binary PNGs")
    body = json.dumps({
        "model": model, "stream": False, "format": "json",
        "options": {"temperature": 0, "num_predict": 280},
        "messages": [{"role": "user", "content": instruction,
                      "images": [base64.b64encode(image).decode("ascii") for image in images]}],
    }).encode("utf-8")
    if len(body) > 3_000_000:
        raise ValueError("Ollama vision request exceeds 3 MiB")
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout_seconds)
    try:
        connection.request("POST", "/api/chat", body=body,
                           headers={"Content-Type": "application/json", "Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"local Ollama request failed with HTTP status {response.status}")
        payload = response.read(131073)
        if len(payload) > 131072:
            raise ValueError("local Ollama response exceeds 128 KiB")
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        raise ValueError("local Ollama request failed or timed out") from exc
    finally:
        connection.close()

    def unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate Ollama response property")
            result[key] = value
        return result
    try:
        decoded = json.loads(payload.decode("utf-8"),
                             object_pairs_hook=unique_fields,
                             parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        message = decoded["message"]["content"]
        if type(message) is not str or len(message) > 16384:
            raise ValueError("Ollama returned missing or excessive model text")
        proposed = json.loads(message, object_pairs_hook=unique_fields,
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("Ollama did not return a valid JSON observation") from exc
    if not isinstance(proposed, dict):
        raise ValueError("Ollama observation must be a JSON object")
    return proposed


def _ollama_chat(images: list[bytes], *, model: str, port: int,
                 timeout_seconds: int, previous: bool) -> dict[str, Any]:
    """Describe one provisional subject on one or two original-frame crops."""
    instruction = (
        "You are reviewing cropped frames of a single provisional subject from a film. "
        "The images show the same local tracklet, not a verified person identity. "
        "Describe only OBSERVABLE colors, clothing, hairstyle, silhouette, pose and props. "
        "Never infer real identity, age, gender, race, ethnicity, nationality or personality. "
        "Do not attribute speech or emotion. The subject can be cartoon or live action. "
        "Return exactly a JSON object with appearance (12-450 chars), visibleTraits "
        "(0-8 short strings), observedAction (one of none, walking, running, turning, "
        "raising-arm, lowering-arm, waving, pointing, sitting-down, standing-up, "
        "gesturing, moving-object, other-visible-motion), and motionEvidence (string). "
        + ("First image is earlier; second is later. Only choose a motion action when "
           "the two frames clearly demonstrate the visible change. Motion due to "
           "camera movement or ambiguity must be none. Do not invent a target character."
           if previous else
           "Only one still image is present; observedAction MUST be none and "
           "motionEvidence MUST be empty.")
    )
    proposed = _ollama_json(images, model=model, port=port,
                            timeout_seconds=timeout_seconds, instruction=instruction)
    return _parse_model_response(proposed, allow_action=previous)


def describe_local_characters(
    source: Path, report_path: Path, out: Path, *, model: str,
    port: int = 11434, max_frames: int = 6, max_calls: int = 12,
    scan_seconds: int = 20, max_pair_gap_seconds: int = 3,
    width: int = 320, height: int = 180, timeout_seconds: int = 180,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> Path:
    """Generate unreviewed appearances/actions from locally hosted visual inference.

    No speaker binding, inferred demographics, action targets or re-ID over cuts.
    """
    if (type(max_frames) is not int or not 2 <= max_frames <= 12 or
            type(max_calls) is not int or not 1 <= max_calls <= 24 or
            type(scan_seconds) is not int or not 1 <= scan_seconds <= 120 or
            type(max_pair_gap_seconds) is not int or not 1 <= max_pair_gap_seconds <= 5 or
            type(width) is not int or not 64 <= width <= 320 or
            type(height) is not int or not 36 <= height <= 180):
        raise ValueError("vision sampling budgets outside supported bounds")
    if type(model) is not str or not _MODEL.fullmatch(model):
        raise ValueError("provide an installed local Ollama vision model tag")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Ollama port invalid")
    if type(timeout_seconds) is not int or not 5 <= timeout_seconds <= 300:
        raise ValueError("Ollama timeout invalid")
    if source.is_symlink() or not source.is_file() or source.suffix.lower() not in _VIDEO_EXTENSIONS:
        raise ValueError("source must be a regular local video file")
    if out.exists() or out.is_symlink():
        raise ValueError("output must be a new nonexisting directory")
    source_signature, report_signature = file_signature(source), file_signature(report_path)
    report = _json_file(report_path, limit=2_000_000)
    frames = _validate_report(report)
    metadata = inspect_source(source, ffprobe=ffprobe)
    if (report["sourceSha256"] != metadata["source"]["sha256"] or
            report["sourceStreamIndex"] != metadata["video"]["streamIndex"] or
            report["sourceTimebase"] != metadata["video"]["sourceTimebase"]):
        raise ValueError("source video and subject tracklets do not match")
    indices = _select_indices(len(frames), max_frames)
    selected = [frames[i] for i in indices]
    video_tb = Fraction(**report["sourceTimebase"])
    source_frames = read_frame_pts(source, report["sourceStreamIndex"],
                                   seconds=scan_seconds, ffprobe=ffprobe)
    by_pts: dict[int, list[int]] = {}
    for frame in source_frames:
        if frame.pts is not None:
            by_pts.setdefault(frame.pts, []).append(frame.ordinal)
    ordinals = []
    for frame in selected:
        possible = by_pts.get(frame["sourcePts"], [])
        if len(possible) != 1:
            raise ValueError("selected video PTS is missing or ambiguous in source")
        ordinals.append(possible[0])
    if ordinals != sorted(set(ordinals)):
        raise ValueError("selected source ordinals must be distinct and chronological")
    rgb = read_rgb_frames(
        source, report["sourceStreamIndex"], ordinals,
        [x["sourcePts"] for x in selected], timebase=video_tb,
        seconds=scan_seconds, width=width, height=height, ffmpeg=ffmpeg)
    require_unchanged(source, source_signature)
    require_unchanged(report_path, report_signature)

    roster: dict[str, dict[str, Any]] = {}
    appearances, actions, evidence = [], [], []
    previous_by_id: dict[str, tuple[int, bytes]] = {}
    calls = 0
    for frame, pixels in zip(selected, rgb, strict=True):
        pts = frame["sourcePts"]
        for detection in frame["proposals"]:
            if calls >= max_calls:
                break
            tid = detection["trackletId"]
            crop, cw, ch = _crop_rgb(pixels, width, height, detection["box"])
            current_image = _png_rgb(crop, cw, ch)
            prior = previous_by_id.get(tid)
            crosses_cut = bool(prior and any(
                prior[0] < cut <= pts for cut in report["cutCandidatePts"]))
            paired = bool(prior and not crosses_cut and
                          0 < (pts-prior[0])*video_tb <= max_pair_gap_seconds)
            images = [prior[1], current_image] if paired else [current_image]
            prediction = _ollama_chat(images, model=model, port=port,
                                      timeout_seconds=timeout_seconds, previous=paired)
            if tid not in roster:
                roster[tid] = {
                    "id": tid, "kind": _CLASS_TO_KIND[detection["category"]],
                    "label": f"Provisional character {tid}",
                    "visualDescription": prediction["appearance"],
                }
            appearances.append({
                "characterId": tid, "startPts": pts, "endPts": pts+1,
                "anchorPts": [pts], "anchorBox": detection["box"],
                "visibleTraits": prediction["visibleTraits"],
                "observation": "Local VLM-proposed appearance at one decoded source frame; not verified.",
                "confidence": "low",
            })
            if paired and prediction["observedAction"] != "none":
                actions.append({
                    "actorId": tid, "targetId": None,
                    "action": prediction["observedAction"],
                    "startPts": prior[0], "endPts": pts+1,
                    "anchorPts": [prior[0], pts],
                    "observation": "Unverified two-frame VLM proposal: " +
                                   prediction["motionEvidence"],
                    "confidence": "low",
                })
            evidence.append({
                "trackletId": tid, "sourcePts": pts,
                "comparisonStartPts": prior[0] if paired else None,
                "appearance": prediction["appearance"],
                "visibleTraits": prediction["visibleTraits"],
                "action": prediction["observedAction"],
                "motionEvidence": prediction["motionEvidence"],
                "evidenceStatus": "local-model-proposal-not-reviewed",
            })
            previous_by_id[tid] = (pts, current_image)
            calls += 1
        if calls >= max_calls:
            break
    scene = {
        "schemaVersion": CHARACTER_SCENE_VERSION,
        "sourceSha256": report["sourceSha256"],
        "sourceStreamIndex": report["sourceStreamIndex"],
        "sourceTimebase": report["sourceTimebase"],
        "reviewer": {"kind": "model", "id": "local-ollama-vision"},
        "window": {
            "startPts": selected[0]["sourcePts"],
            "endPts": selected[-1]["sourcePts"] + 1,
            "coverage": "partial-window",
        },
        "characters": list(roster.values()),
        "appearances": appearances,
        "actions": actions, "utterances": [], "identityClaims": [],
    }
    validate_character_scene(scene)
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": report["sourceSha256"],
        "trackletReportSha256": sha256_file(report_path),
        "sourceTimebase": report["sourceTimebase"],
        "modelTag": model,
        "modelDigestVerified": False,
        "inferenceEndpoint": f"http://127.0.0.1:{port}/api/chat",
        "frameCountSelected": len(selected), "modelCalls": calls,
        "appearanceCount": len(appearances), "actionProposalCount": len(actions),
        "observations": evidence,
        "evidenceStatus": "unreviewed-local-vlm-frame-hypotheses",
        "limitations": [
            "All appearances and actions are model hypotheses; source pixels/PTS are verified, interpretation is not.",
            "Character IDs are provisional tracklets; neither identity nor cross-shot continuity is established.",
            "Two-frame comparisons cannot reliably distinguish camera motion from character motion.",
            "No action target, dialogue, age, ethnicity, gender identity, or real name is inferred.",
            "Ollama model tag is operator-declared and its weight digest is not independently established.",
        ],
    }
    require_unchanged(source, source_signature)
    require_unchanged(report_path, report_signature)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-ollama-character-", dir=out.parent) as folder:
        staging = Path(folder)
        (staging / "character-scene.json").write_text(
            json.dumps(scene, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        (staging / "character-vision.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        if out.exists() or out.is_symlink():
            raise ValueError("output became occupied before publish")
        os.replace(staging, out)
    return out / "character-scene.json"
