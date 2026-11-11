"""Atomic one-command local character study across detection, VLM and visual QA.

All outputs remain unverified model evidence; no video download or remote inference.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.mac_vision_detection import detect_mac_vision_people
from kumiki_reference_lab.pipeline.ollama_subject_detection import detect_local_ollama_subjects
from kumiki_reference_lab.pipeline.subject_detections import (
    load_subject_detections, run_subject_detections,
)
from kumiki_reference_lab.pipeline.subject_tracklet_review import build_subject_tracklet_review
from kumiki_reference_lab.pipeline.ollama_character_perception import (
    _MODEL, _VIDEO_EXTENSIONS, describe_local_characters,
)
from kumiki_reference_lab.pipeline.character_vision_review import build_character_vision_review
from kumiki_reference_lab.pipeline.local_character_interactions import analyze_local_interactions
from kumiki_reference_lab.pipeline.interaction_review import build_interaction_review
from kumiki_reference_lab.reviews.character_scene import load_character_scene

SCHEMA_VERSION = "kumiki.local-character-study.v1"


def run_local_character_study(
    source: Path, out: Path, *, model: str, detector: str = "ollama",
    max_seconds: int = 10, start_seconds: int = 0,
    max_samples: int = 8, max_calls: int = 12,
    max_pairs: int = 6, width: int = 320, height: int = 180,
    port: int = 11434, timeout_seconds: int = 180,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
    review: bool = True, interactions: bool = True,
) -> Path:
    """Execute bounded components in staging; atomically publish only if all succeed.

    Local detector and perception semantics remain hypotheses. A complete run
    does not indicate character accuracy, identity or video-wide coverage.
    """
    if detector not in ("ollama", "apple-vision"):
        raise ValueError("detector must be ollama or apple-vision")
    if (type(model) is not str or not _MODEL.fullmatch(model) or len(model) > 72):
        raise ValueError("model must identify an installed local Ollama vision model")
    if (type(port) is not int or not 1 <= port <= 65535 or
            type(timeout_seconds) is not int or not 5 <= timeout_seconds <= 300 or
            type(max_seconds) is not int or not 1 <= max_seconds <= 30 or
            type(start_seconds) is not int or start_seconds < 0 or
            start_seconds + max_seconds > 3600 or
            type(max_samples) is not int or not 5 <= max_samples <= 12 or
            type(max_calls) is not int or not 1 <= max_calls <= 24 or
            type(max_pairs) is not int or not 1 <= max_pairs <= 12 or
            type(width) is not int or not 64 <= width <= 320 or
            type(height) is not int or not 36 <= height <= 180 or
            type(review) is not bool or type(interactions) is not bool):
        raise ValueError("local character study input budgets invalid")
    if (source.is_symlink() or not source.is_file() or
            source.suffix.lower() not in _VIDEO_EXTENSIONS):
        raise ValueError("local study requires an authorized regular local video")
    if out.exists() or out.is_symlink():
        raise ValueError("local study output must be a new nonexisting directory")

    signature = file_signature(source)
    scan_prefix = start_seconds + max_seconds
    seek_start = start_seconds if scan_prefix > 120 else None
    study_scan_seconds = max_seconds if seek_start is not None else scan_prefix
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-character-study-", dir=out.parent) as temp:
        staged = Path(temp)
        boxes_path = staged / "subject-detections.json"
        if detector == "ollama":
            detect_local_ollama_subjects(
                source, boxes_path, model=model, port=port,
                seconds=max_seconds, max_samples=max_samples,
                start_seconds=start_seconds,
                width=width, height=height, timeout_seconds=timeout_seconds,
                ffmpeg=ffmpeg, ffprobe=ffprobe, rights_status=rights_status,
            )
        else:
            detect_mac_vision_people(
                source, boxes_path, seconds=max_seconds, max_samples=max_samples,
                start_seconds=start_seconds,
                width=width, height=height,
                ffmpeg=ffmpeg, ffprobe=ffprobe, rights_status=rights_status,
            )
        detections = load_subject_detections(boxes_path)
        tracks_dir = staged / "tracklets"
        tracks_path = run_subject_detections(
            source, boxes_path, tracks_dir, ffprobe=ffprobe, rights_status=rights_status)
        tracklet_summary = json.loads(tracks_path.read_text(encoding="utf-8"))
        paths: dict[str, str | None] = {
            "detections": "subject-detections.json",
            "tracklets": "tracklets/subject-tracklets.json",
            "trackletQa": None,
            "characterVision": "character-vision/character-scene.json",
            "characterVisionManifest": "character-vision/character-vision.json",
            "characterQa": None,
            "interactions": None,
            "interactionManifest": None,
            "interactionQa": None,
        }
        if review:
            build_subject_tracklet_review(
                source, tracks_path, staged / "tracklet-qa",
                max_frames=min(max_samples, 8),
                scan_seconds=study_scan_seconds, seek_start_seconds=seek_start,
                width=width, height=height, ffmpeg=ffmpeg, ffprobe=ffprobe)
            paths["trackletQa"] = "tracklet-qa/index.html"

        vision_dir = staged / "character-vision"
        scene_path = describe_local_characters(
            source, tracks_path, vision_dir, model=model, port=port,
            max_frames=min(max_samples, 8), max_calls=max_calls,
            scan_seconds=study_scan_seconds, seek_start_seconds=seek_start,
            width=width, height=height,
            timeout_seconds=timeout_seconds, ffmpeg=ffmpeg, ffprobe=ffprobe)
        observed_scene = load_character_scene(scene_path)
        if review and observed_scene["appearances"]:
            build_character_vision_review(
                source, tracks_path, vision_dir, staged / "character-qa",
                scan_seconds=study_scan_seconds, seek_start_seconds=seek_start,
                width=width, height=height,
                ffmpeg=ffmpeg, ffprobe=ffprobe)
            paths["characterQa"] = "character-qa/index.html"
        if interactions and len(observed_scene["characters"]) >= 2:
            interaction_dir = staged / "character-interactions"
            analyze_local_interactions(
                source, tracks_path, vision_dir, interaction_dir,
                model=model, port=port, max_pairs=max_pairs,
                scan_seconds=study_scan_seconds, seek_start_seconds=seek_start,
                width=width, height=height,
                timeout_seconds=timeout_seconds, ffmpeg=ffmpeg, ffprobe=ffprobe)
            paths["interactions"] = "character-interactions/character-scene.json"
            paths["interactionManifest"] = "character-interactions/character-interactions.json"
            if review:
                build_interaction_review(
                    source, tracks_path, vision_dir, interaction_dir,
                    staged / "interaction-qa",
                    ffmpeg=ffmpeg, ffprobe=ffprobe)
                paths["interactionQa"] = "interaction-qa/index.html"

        require_unchanged(source, signature)
        manifest: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "sourceSha256": detections["sourceSha256"],
            "sourceStreamIndex": detections["sourceStreamIndex"],
            "sourceTimebase": detections["sourceTimebase"],
            "modelTag": model,
            "modelDigestVerified": False,
            "detectorBackend": detector,
            "rightsStatus": rights_status,
            "scanStartSeconds": start_seconds, "maxSeconds": max_seconds,
            "sourceWindowEndSeconds": scan_prefix,
            "sourceDecodeMode": ("verified-seek-original-pts-v1"
                                 if seek_start is not None else "prefix-ordinal-pts-v1"),
            "scanPrefixSeconds": scan_prefix if seek_start is None else None,
            "maxSamples": max_samples,
            "maxVisionCalls": max_calls, "maxInteractionPairs": max_pairs,
            "detectedRegionProposals": sum(
                len(frame["detections"]) for frame in detections["frames"]),
            "provisionalTracklets": tracklet_summary["trackletCount"],
            "provisionalCharacterIdsObserved": len(observed_scene["characters"]),
            "visionAppearanceProposals": len(observed_scene["appearances"]),
            "interactionStageRequested": interactions,
            "qaStageRequested": review,
            "paths": paths,
            "status": "completed-unverified-model-proposals",
            "methodLimits": [
                "Completed means tools ran, not that character detection, identity, actions or speech were verified.",
                "Tracklet IDs are local image associations with no cross-shot character identity guarantee.",
                "Only a bounded initial video prefix was analyzed and vision model calls may cover fewer detections.",
                "No demographics, actual named identities, dialogue, voice matching or emotion is inferred.",
                "A skipped interaction stage or zero model observations does not establish a character-free film.",
                "User-selected model weights/digest, rights and creative suitability are not independently audited.",
            ],
        }
        (staged / "study-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        require_unchanged(source, signature)
        if out.exists() or out.is_symlink():
            raise ValueError("output directory was occupied during study")
        os.replace(staged, out)
    return out / "study-manifest.json"
