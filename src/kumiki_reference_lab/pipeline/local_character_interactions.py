"""Opt-in low-confidence actor-target motion hypotheses from two verified frames.

Local Ollama sees only color-outlined subjects on adjacent within-shot frames.
No dialogue, physical-distance proof, identities or emotional inference.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.ollama_character_perception import (
    _ollama_json, _DISALLOWED, _MODEL, _VIDEO_EXTENSIONS,
    SCHEMA_VERSION as LOCAL_VISION_VERSION,
)
from kumiki_reference_lab.pipeline.subject_detections import _check_box, _iou
from kumiki_reference_lab.pipeline.subject_tracklet_review import _validate_report
from kumiki_reference_lab.reviews.character_scene import load_character_scene, validate_character_scene

SCHEMA_VERSION = "kumiki.local-character-interactions.v1"
_ALLOWED = frozenset({
    "none", "reaching-toward", "pointing-toward", "passing-object",
    "touching", "following", "gesturing-toward", "moving-toward", "moving-away",
})
_COLORS = {"red": (255, 55, 66), "cyan": (49, 239, 247)}


def _outline(frame: bytes, width: int, height: int, red: list[float],
             cyan: list[float]) -> bytes:
    """Create image-backed colored subject IDs with no external text/font dependency."""
    if len(frame) != width * height * 3:
        raise ValueError("interaction frame RGB buffer has invalid size")
    out = bytearray(frame)
    for box, color in ((red, _COLORS["red"]), (cyan, _COLORS["cyan"])):
        x, y, w, h = _check_box(box, "interaction subject region")
        x0, y0 = max(0, int(math.floor(x*width))), max(0, int(math.floor(y*height)))
        x1, y1 = min(width-1, int(math.ceil((x+w)*width))-1), min(height-1, int(math.ceil((y+h)*height))-1)
        if x1 <= x0 or y1 <= y0:
            raise ValueError("interaction subject bounding box is too small")
        for offset in range(2):
            lo_x, hi_x = min(x0+offset,x1), max(x0,x1-offset)
            lo_y, hi_y = min(y0+offset,y1), max(y0,y1-offset)
            for xx in range(lo_x, hi_x+1):
                for yy in (lo_y, hi_y):
                    pos = (yy*width+xx)*3
                    out[pos:pos+3] = bytes(color)
            for yy in range(lo_y, hi_y+1):
                for xx in (lo_x, hi_x):
                    pos = (yy*width+xx)*3
                    out[pos:pos+3] = bytes(color)
    return _png_rgb(bytes(out), width, height)


def _parse_response(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {
        "actorColor", "interaction", "visualEvidence"
    }:
        raise ValueError("interaction VLM must return actorColor, interaction and visualEvidence")
    actor, action, evidence = value["actorColor"], value["interaction"], value["visualEvidence"]
    if type(actor) is not str or actor not in ("red", "cyan", "none"):
        raise ValueError("interaction actor must be red, cyan or none")
    if type(action) is not str or action not in _ALLOWED:
        raise ValueError("unsupported or ungrounded interaction label")
    if type(evidence) is not str or len(evidence) > 400 or _DISALLOWED.search(evidence):
        raise ValueError("interaction evidence invalid or contains demographic identity claims")
    if action == "none":
        if actor != "none":
            raise ValueError("abstaining interaction must have actor none")
    elif actor == "none" or len(evidence.strip()) < 12:
        raise ValueError("interaction needs named color actor and concrete evidence")
    return {"actorColor": actor, "interaction": action, "visualEvidence": evidence.strip()}


def _candidates(tracklets: dict[str, Any], roster_ids: set[str], *,
                window_start: int, window_end: int, max_pairs: int,
                gap_seconds: int) -> list[dict[str, Any]]:
    frames = _validate_report(tracklets)
    timebase = Fraction(**tracklets["sourceTimebase"])
    cuts = tracklets["cutCandidatePts"]
    results = []
    for previous, current in zip(frames, frames[1:]):
        p, q = previous["sourcePts"], current["sourcePts"]
        if not window_start <= p < q < window_end:
            continue
        if (q-p)*timebase > gap_seconds or any(p < cut <= q for cut in cuts):
            continue
        previous_boxes = {x["trackletId"]: x["box"] for x in previous["proposals"]
                          if x["trackletId"] in roster_ids}
        current_boxes = {x["trackletId"]: x["box"] for x in current["proposals"]
                         if x["trackletId"] in roster_ids}
        common = sorted(set(previous_boxes) & set(current_boxes))
        for red, cyan in combinations(common, 2):
            r1, c1 = previous_boxes[red], previous_boxes[cyan]
            r2, c2 = current_boxes[red], current_boxes[cyan]
            if max(_iou(tuple(r1), tuple(c1)), _iou(tuple(r2), tuple(c2))) > .65:
                continue  # likely duplicate/ambiguous overlapping boxes, not two reliable subjects
            results.append({
                "startPts": p, "endPts": q,
                "redId": red, "cyanId": cyan,
                "previousRedBox": r1, "previousCyanBox": c1,
                "currentRedBox": r2, "currentCyanBox": c2,
            })
            if len(results) >= max_pairs:
                return results
    return results


def analyze_local_interactions(
    source: Path, report_path: Path, vision_run: Path, out: Path, *, model: str,
    port: int = 11434, max_pairs: int = 6, gap_seconds: int = 3,
    scan_seconds: int = 20, width: int = 320, height: int = 180,
    timeout_seconds: int = 180, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> Path:
    """Enrich a source-bound character scene without changing existing observations."""
    if (type(max_pairs) is not int or not 1 <= max_pairs <= 12 or
            type(gap_seconds) is not int or not 1 <= gap_seconds <= 5 or
            type(scan_seconds) is not int or not 1 <= scan_seconds <= 120 or
            type(width) is not int or not 64 <= width <= 320 or
            type(height) is not int or not 36 <= height <= 180):
        raise ValueError("interaction scanning budgets out of range")
    if type(model) is not str or not _MODEL.fullmatch(model):
        raise ValueError("a locally installed vision model tag is required")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("local Ollama port invalid")
    if type(timeout_seconds) is not int or not 5 <= timeout_seconds <= 300:
        raise ValueError("local Ollama timeout invalid")
    if source.is_symlink() or not source.is_file() or source.suffix.lower() not in _VIDEO_EXTENSIONS:
        raise ValueError("input must be a regular authorized local video")
    if out.exists() or out.is_symlink():
        raise ValueError("output must be a new nonexisting directory")
    scene_path = vision_run / "character-scene.json"
    vision_path = vision_run / "character-vision.json"
    files = (source, report_path, scene_path, vision_path)
    signatures = [file_signature(x) for x in files]
    tracklets = _json_file(report_path, limit=2_000_000)
    frames = _validate_report(tracklets)
    base_scene = load_character_scene(scene_path)
    vision = _json_file(vision_path, limit=262144)
    if (tracklets["sourceSha256"] != base_scene["sourceSha256"] or
            tracklets["sourceStreamIndex"] != base_scene["sourceStreamIndex"] or
            tracklets["sourceTimebase"] != base_scene["sourceTimebase"] or
            vision.get("schemaVersion") != LOCAL_VISION_VERSION or
            vision.get("sourceSha256") != base_scene["sourceSha256"] or
            vision.get("trackletReportSha256") != sha256_file(report_path) or
            vision.get("sourceTimebase") != base_scene["sourceTimebase"] or
            vision.get("modelDigestVerified") is not False):
        raise ValueError("interaction source/model provenance does not match input scene")
    roster = {x["id"]: x for x in base_scene["characters"] if x["kind"] != "voice-only"}
    if any(item["targetId"] is not None for item in base_scene["actions"]):
        raise ValueError("interaction inference expects a base scene without directed actions")
    candidates = _candidates(
        tracklets, set(roster), window_start=base_scene["window"]["startPts"],
        window_end=base_scene["window"]["endPts"], max_pairs=max_pairs,
        gap_seconds=gap_seconds,
    )
    metadata = inspect_source(source, ffprobe=ffprobe)
    if (metadata["source"]["sha256"] != tracklets["sourceSha256"] or
            metadata["video"]["streamIndex"] != tracklets["sourceStreamIndex"] or
            metadata["video"]["sourceTimebase"] != tracklets["sourceTimebase"]):
        raise ValueError("local interaction source differs from tracklet source")
    selected_pts = sorted({row[p] for row in candidates for p in ("startPts", "endPts")})
    by_frame: dict[int, bytes] = {}
    if selected_pts:
        decoded = read_frame_pts(source, tracklets["sourceStreamIndex"],
                                 seconds=scan_seconds, ffprobe=ffprobe)
        choices: dict[int, list[int]] = {}
        for row in decoded:
            if row.pts is not None:
                choices.setdefault(row.pts, []).append(row.ordinal)
        ordinals = []
        for pts in selected_pts:
            indices = choices.get(pts, [])
            if len(indices) != 1:
                raise ValueError("interaction source PTS missing or ambiguous")
            ordinals.append(indices[0])
        if ordinals != sorted(set(ordinals)):
            raise ValueError("interaction source ordinals out of decode order")
        images = read_rgb_frames(
            source, tracklets["sourceStreamIndex"], ordinals,
            selected_pts, timebase=Fraction(**tracklets["sourceTimebase"]),
            seconds=scan_seconds, width=width, height=height, ffmpeg=ffmpeg)
        by_frame = dict(zip(selected_pts, images, strict=True))
    for file, signature in zip(files, signatures, strict=True):
        require_unchanged(file, signature)

    responses, new_actions = [], []
    for row in candidates:
        earlier = _outline(by_frame[row["startPts"]], width, height,
                           row["previousRedBox"], row["previousCyanBox"])
        later = _outline(by_frame[row["endPts"]], width, height,
                         row["currentRedBox"], row["currentCyanBox"])
        instruction = (
            "These are TWO chronological frames from the SAME video shot. RED bounding box "
            "marks subject A; CYAN bounding box marks subject B in both frames. "
            "Do not use real names or infer personal identity, gender, ethnicity, age, "
            "emotion or speech. Only report a visually supported DIRECTIONAL interaction "
            "from one boxed subject to the other. Camera movement, coincidence, "
            "static proximity, uncertainty or no visible change require interaction none. "
            "Return ONLY JSON keys actorColor (red/cyan/none), interaction (none, "
            "reaching-toward, pointing-toward, passing-object, touching, following, "
            "gesturing-toward, moving-toward, moving-away) and visualEvidence (text). "
            "A non-none action requires direct observed evidence across both frames; "
            "never invent a prop, contact, or relationship."
        )
        raw = _ollama_json([earlier, later], model=model, port=port,
                           timeout_seconds=timeout_seconds, instruction=instruction)
        decision = _parse_response(raw)
        if decision["interaction"] != "none":
            actor_id = row["redId"] if decision["actorColor"] == "red" else row["cyanId"]
            target_id = row["cyanId"] if decision["actorColor"] == "red" else row["redId"]
            new_actions.append({
                "actorId": actor_id, "targetId": target_id,
                "action": decision["interaction"],
                "startPts": row["startPts"], "endPts": row["endPts"]+1,
                "anchorPts": [row["startPts"], row["endPts"]],
                "observation": "Unverified local VLM two-frame interaction: " +
                               decision["visualEvidence"],
                "confidence": "low",
            })
        responses.append({
            "startPts": row["startPts"], "endPts": row["endPts"],
            "redId": row["redId"], "cyanId": row["cyanId"],
            **decision, "status": "unreviewed-interaction-hypothesis",
        })
    merged = {**base_scene, "actions": base_scene["actions"] + new_actions}
    validate_character_scene(merged)
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": base_scene["sourceSha256"],
        "trackletReportSha256": sha256_file(report_path),
        "baseSceneSha256": sha256_file(scene_path),
        "modelTag": model, "modelDigestVerified": False,
        "inferenceEndpoint": f"http://127.0.0.1:{port}/api/chat",
        "candidatePairs": len(candidates), "actionProposals": len(new_actions),
        "pairDecisions": responses,
        "evidenceStatus": "low-confidence-unreviewed-local-vlm-pairwise-hypotheses",
        "limitations": [
            "Actor and target are local tracklet IDs, not verified individuals or identities.",
            "Box IoU and a two-frame comparison are not proof of intentional physical interaction.",
            "No association crosses supplied cuts or missing/different tracklets, and ambiguous overlapping boxes are skipped.",
            "Predictions are low confidence and require visual source review; no speech/emotion/demographics inferred.",
        ],
    }
    for file, signature in zip(files, signatures, strict=True):
        require_unchanged(file, signature)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-interaction-", dir=out.parent) as folder:
        staging = Path(folder)
        (staging / "character-scene.json").write_text(
            json.dumps(merged, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8")
        (staging / "character-interactions.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8")
        if out.exists() or out.is_symlink():
            raise ValueError("interaction output became occupied before publish")
        os.replace(staging, out)
    return out / "character-scene.json"
