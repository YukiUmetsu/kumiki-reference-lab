"""Shot-aware, low-inference cinematic research and Kumiki recipe proposals.

All creative cues are traceable hypotheses, never claims that an original video
used a particular engine, layer stack or editing technique. No media is copied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

from kumiki_reference_lab.pipeline.agent_frame_review import (
    _write_json_atomic, load_workspace,
)
from kumiki_reference_lab.pipeline.shot_intelligence import (
    build_shot_intelligence, prioritized_frame_plan,
)
from kumiki_reference_lab.pipeline.temporal_motion import build_temporal_motion
from kumiki_reference_lab.pipeline.screen_text import build_screen_text
from kumiki_reference_lab.pipeline.seeded_subjects import build_seeded_region_tracks

SCHEMA_VERSION = "kumiki.online-cinematic-insights.v1"

# Vocabulary proposes reusable ORIGINAL animation families. It does not
# automatically identify copyrighted video techniques with certainty.
_VISUAL_FAMILIES = {
    "paper-cut": ("style.paper-cut-layered-motion", "layered-2d"),
    "paper cut": ("style.paper-cut-layered-motion", "layered-2d"),
    "parallax": ("camera.layer-parallax", "layered-2d-3d"),
    "masked reveal": ("type.masked-reveal", "text-and-mask"),
    "mask reveal": ("type.masked-reveal", "text-and-mask"),
    "kinetic typography": ("type.kinetic-typography", "text-motion"),
    "kinetic type": ("type.kinetic-typography", "text-motion"),
    "morph": ("effect.shape-morph", "shape-morph"),
    "squash and stretch": ("character.squash-stretch", "character-rig"),
    "squash/stretch": ("character.squash-stretch", "character-rig"),
    "stop-motion": ("style.stop-motion", "stepped-timing"),
    "particle": ("effect.particle-reveal", "particles"),
    "cel animation": ("style.cel-animation", "2d-cel"),
    "whip-pan": ("camera.whip-pan", "camera-motion"),
}


def _read_optional_notes(path: Path, *, source_sha: str,
                         frame_count: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8_000_000:
        raise ValueError("unsafe frame annotation file")
    document = json.loads(path.read_text(encoding="utf-8"))
    if (document.get("schemaVersion") != "kumiki.agent-frame-notes.v1" or
            document.get("sourceSha256") != source_sha or
            document.get("frameCount") != frame_count or
            not isinstance(document.get("observations"), list) or
            len(document["observations"]) > 10000):
        raise ValueError("annotation provenance mismatch")
    good = []
    for item in document["observations"]:
        if (not isinstance(item, dict) or
                type(item.get("startFrameIndex")) is not int or
                type(item.get("endFrameIndex")) is not int or
                not 0 <= item["startFrameIndex"] <= item["endFrameIndex"] < frame_count or
                item.get("category") not in (
                    "animation", "typography", "character", "camera",
                    "lighting", "composition", "visual-style", "transition",
                    "material", "other") or
                type(item.get("description")) is not str or
                len(item["description"]) > 240):
            raise ValueError("invalid bounded frame annotation")
        good.append(item)
    return good


def _cue(
    source_sha: str, shot: dict[str, Any], technique: str, family: str,
    *, start: int, end: int, measurements: dict[str, Any],
    grounding: str, alternatives: list[str],
) -> dict[str, Any]:
    label = f"{source_sha}:{shot['shotId']}:{technique}:{start}:{end}"
    return {
        "id": "cinema-cue-" + hashlib.sha256(label.encode()).hexdigest()[:16],
        "shotId": shot["shotId"],
        "techniqueId": technique, "componentFamily": family,
        "startFrameIndex": start, "endFrameIndex": end,
        "startSeconds": shot["startSeconds"],
        "endSecondsEstimate": shot["endSecondsEstimate"],
        "grounding": grounding,
        "measurements": measurements,
        "plausibleAlternatives": alternatives,
        "reviewStatus": "candidate-not-verified",
    }


def derive_technique_hypotheses(
    shots: dict[str, Any], motion: dict[str, Any],
    screen_text: dict[str, Any], notes: list[dict[str, Any]],
    *, max_cues: int = 200,
) -> list[dict[str, Any]]:
    if type(max_cues) is not int or not 1 <= max_cues <= 500:
        raise ValueError("technique output budget invalid")
    source_sha = shots["sourceSha256"]
    by_id = {shot["shotId"]: shot for shot in shots["shots"]}
    candidates: list[dict[str, Any]] = []
    for shot in shots["shots"][1:]:
        candidates.append(_cue(
            source_sha, shot, "edit.hard-cut-candidate", "shot-transition",
            start=shot["startFrameIndex"], end=shot["startFrameIndex"],
            measurements={"candidateFrameIndex": shot["startFrameIndex"]},
            grounding="numeric-image-change", alternatives=[
                "abrupt animation or lighting change", "flash", "camera movement",
            ]))
    motions: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for pair in motion.get("pairs", []):
        obj = pair.get("globalImageMotion", {})
        if obj.get("status") != "supported-screen-affine-candidate":
            continue
        key = pair["shotId"], obj["cue"]
        motions.setdefault(key, []).append(pair)
    for (shot_id, cue), pairs in motions.items():
        if len(pairs) < 2 or shot_id not in by_id:
            continue
        first, last = pairs[0], pairs[-1]
        candidates.append(_cue(
            source_sha, by_id[shot_id],
            "image-motion." + cue, "camera-or-object-motion",
            start=first["startFrameIndex"], end=last["endFrameIndex"],
            measurements={
                "supportedSampledPairs": len(pairs),
                "meanInlierFraction": round(statistics.mean(
                    p["globalImageMotion"]["inlierFraction"] for p in pairs), 4),
                "inlierImageTranslationPixels": [
                    p["globalImageMotion"]["translationPixels"] for p in pairs[:12]
                ],
            },
            grounding="robust-image-affine", alternatives=[
                "whole-scene animation", "parallax", "object movement",
                "physical camera motion", "picture-in-picture transform",
            ]))
    for item in screen_text.get("textMotionCandidates", []):
        shot = by_id.get(item["shotId"])
        if shot:
            candidates.append(_cue(
                source_sha, shot, "type.position-change-candidate",
                "text-motion", start=item["startFrameIndex"],
                end=item["endFrameIndex"],
                measurements={
                    "centerDisplacementNormalized":
                        item["centerDisplacementNormalized"],
                    "ocrTextSnippet": item["visibleText"][:80],
                }, grounding="local-ocr-image-boxes", alternatives=[
                    "OCR box jitter", "object movement", "camera movement",
                ]))
    for annotation in notes:
        text = annotation["description"].casefold()
        target = next((shot for shot in shots["shots"]
                       if shot["startFrameIndex"] <= annotation["startFrameIndex"]
                       < shot["endFrameIndexExclusive"]), None)
        if target is None:
            continue
        emitted: set[str] = set()
        for phrase, (technique, family) in _VISUAL_FAMILIES.items():
            if technique in emitted:
                continue
            for match in re.finditer(re.escape(phrase), text):
                # Avoid asserting a technique when the annotation explicitly
                # says it is absent or unlikely.
                prefix = text[max(0, match.start() - 12):match.start()].strip()
                if re.search(r"(?:no|not|without|unlikely)\s+$", prefix):
                    continue
                candidates.append(_cue(
                    source_sha, target, technique, family,
                    start=annotation["startFrameIndex"],
                    end=annotation["endFrameIndex"],
                    measurements={
                        "annotationId": annotation.get("id"),
                        "annotationCategory": annotation["category"],
                        "annotationConfidence": annotation.get("confidence", "low"),
                    },
                    grounding="unreviewed-agent-visual-annotation",
                    alternatives=["visual resemblance without the named technique"],
                ))
                emitted.add(technique)
                break
    # Stable ordering and deduplication keep repeated low-model phrases from
    # flooding the technique index.
    unique: dict[str, dict[str, Any]] = {}
    for cue in candidates:
        unique.setdefault(cue["id"], cue)
    return sorted(unique.values(),
                  key=lambda x: (x["startFrameIndex"], x["techniqueId"]))[:max_cues]


def derive_audio_visual_hypotheses(
    shots: dict[str, Any], audio: dict[str, Any] | None,
    *, alignment_tolerance_ms: int = 100,
) -> dict[str, Any]:
    if type(alignment_tolerance_ms) is not int or not 20 <= alignment_tolerance_ms <= 500:
        raise ValueError("invalid audio-video proximity tolerance")
    if audio is None:
        return {"status": "not-measured", "candidates": [],
                "clockRelation": "unknown"}
    if audio.get("status") != "measured-decoded-audio-envelope":
        return {"status": audio.get("status", "unavailable"), "candidates": [],
                "clockRelation": "not-independently-aligned"}
    cut_times = [
        (shot["shotId"], shot["startSeconds"] * 1000)
        for shot in shots["shots"][1:]
    ]
    pairs = []
    for candidate in audio["transientCandidates"]:
        time = candidate["decodedOffsetMs"]
        nearby = sorted(((abs(time - cut_ms), shot_id, cut_ms)
                         for shot_id, cut_ms in cut_times
                         if abs(time - cut_ms) <= alignment_tolerance_ms))
        if not nearby:
            continue
        difference, shot_id, cut_ms = nearby[0]
        pairs.append({
            "shotId": shot_id, "audioDecodedOffsetMs": time,
            "videoDecodedBoundaryMsEstimate": round(cut_ms, 3),
            "absoluteOffsetDifferenceMs": round(difference, 3),
            "status": "candidate-energy-attack-near-video-cut",
            "synchronization": "not-independently-verified",
        })
    return {
        "status": "unverified-decoder-clock-proximities",
        "clockRelation": "not-independently-aligned",
        "candidates": pairs,
        "note": "Do not call these music beats or edit sync without audio/video clock review.",
    }


def derive_kumiki_recipe_proposals(
    shots: dict[str, Any], cues: list[dict[str, Any]],
    *, max_recipes: int = 100,
) -> list[dict[str, Any]]:
    if type(max_recipes) is not int or not 1 <= max_recipes <= 500:
        raise ValueError("recipe budget invalid")
    by_id = {s["shotId"]: s for s in shots["shots"]}
    recipes = []
    for cue in cues[:max_recipes]:
        shot = by_id[cue["shotId"]]
        recipes.append({
            "id": "draft-recipe-" + cue["id"].rsplit("-", 1)[-1],
            "sourceCueId": cue["id"],
            "purpose": "original-inspired-technique-not-reference-reproduction",
            "techniqueFamily": cue["componentFamily"],
            "sourceTechniqueHypothesis": cue["techniqueId"],
            "originalImplementationRequired": True,
            "timing": {
                "referenceStartSeconds": cue["startSeconds"],
                "referenceEndSecondsEstimate": cue["endSecondsEstimate"],
                "shotDurationSecondsEstimate": shot["durationSecondsEstimate"],
            },
            "visualStartingPoint": {
                "displayMeanRgb": shot["imageEvidence"]["meanRgb"],
                "displayMeanLuma": shot["imageEvidence"]["meanLuma"],
                "displayMeanSaturation": shot["imageEvidence"]["meanSaturation"],
                "suggestedOriginalContent": None,
                "targetComponentId": None,
                "targetComponentApiVerified": False,
            },
            "evidence": {
                "sourceSha256": shots["sourceSha256"],
                "shotId": shot["shotId"],
                "frameRange": [cue["startFrameIndex"], cue["endFrameIndex"]],
                "cueGrounding": cue["grounding"],
            },
            "reviewGates": [
                "Verify visual reference and reject false-positive technique labels.",
                "Use independent artwork, type, characters and timing; do not copy frames.",
                "Check current kumiki-ui component registry before choosing an API.",
                "Author a new component if missing; visually compare rendered original.",
            ],
            "status": "not-executable-design-proposal",
        })
    return recipes


def analyze_cinematic_workspace(
    workspace: Path, *, motion: bool = True, ocr: bool = False,
    max_motion_pairs: int = 120, max_ocr_frames: int = 48,
    max_plan_frames: int = 48, overwrite: bool = False,
    roi_seeds: Path | None = None, max_roi_frames: int = 240,
) -> Path:
    manifest, numeric, reference = load_workspace(workspace)
    if any(type(v) is not bool for v in (motion, ocr, overwrite)):
        raise ValueError("insights options must be booleans")
    result = reference.with_suffix(".insights.json")
    if (result.exists() or result.is_symlink()) and not overwrite:
        raise ValueError("cinematic insights already exist; pass --overwrite")
    shots = build_shot_intelligence(numeric)
    plan = prioritized_frame_plan(shots, max_frames=max_plan_frames)
    movement = (build_temporal_motion(
        workspace, shots, max_pairs=max_motion_pairs)
        if motion else {
            "status": "not-requested", "pairs": [], "featureTracklets": [],
        })
    text = (build_screen_text(
        workspace, shots, max_frames=max_ocr_frames)
        if ocr else {
            "status": "not-requested", "observedFrames": [],
            "textMotionCandidates": [],
        })
    subjects = (build_seeded_region_tracks(
        workspace, shots, roi_seeds, max_frames_per_subject=max_roi_frames)
        if roi_seeds is not None else {
            "status": "not-requested", "tracks": [],
            "screenRelationshipProxies": [],
        })
    notes = _read_optional_notes(
        reference.with_suffix(".frame-notes.json"),
        source_sha=manifest["sourceSha256"],
        frame_count=manifest["frameCount"],
    )
    if reference.stat().st_size > 90_000_000:
        raise ValueError("reference too large")
    source_report = json.loads(reference.read_text(encoding="utf-8"))
    audio = source_report.get("audioEvidence")
    if audio is not None and audio.get("schemaVersion") != "kumiki.online-audio-cues.v1":
        raise ValueError("unknown audio evidence version")
    cues = derive_technique_hypotheses(shots, movement, text, notes)
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "id": manifest["id"],
        "source": {
            "sourceSha256": manifest["sourceSha256"],
            "numericReferenceFile": reference.name,
            "annotationReferenceFile": (reference.stem + ".frame-notes.json"
                                        if notes else None),
            "frameCount": manifest["frameCount"],
            "originalMediaRetained": False,
            "localPreviewsNotInGit": True,
        },
        "shotIntelligence": shots,
        "shotAwareAgentPlan": plan,
        "temporalMotion": movement,
        "screenText": text,
        "seededSubjectTracks": subjects,
        "audioVisualCues": derive_audio_visual_hypotheses(shots, audio),
        "techniqueHypotheses": cues,
        "kumikiRecipeProposals": derive_kumiki_recipe_proposals(shots, cues),
        "reviewRequests": {
            "characterIdentity": (
                "Use existing seeded ROI character tracker with verified identity; "
                "anonymous optical-flow points cannot establish identity."),
            "characterInteraction": (
                "Pair character tracks only when contemporaneous boxes are independently "
                "observed. Image overlap/relative movement alone is not a social interaction."),
            "exactTypography": (
                "OCR boxes and Magnitude notes do not establish an exact font family."),
            "lightingAndMaterials": (
                "Use measured color/luma and reviewed frame appearance; no physical "
                "lighting rig or material shader is recovered."),
        },
        "status": "measured-evidence-with-unreviewed-creative-proposals",
    }
    _write_json_atomic(result, document)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic shot-aware cinematic insights and draft Kumiki recipes.")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--no-motion", action="store_true")
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--max-motion-pairs", type=int, default=120)
    parser.add_argument("--max-ocr-frames", type=int, default=48)
    parser.add_argument("--max-plan-frames", type=int, default=48)
    parser.add_argument("--roi-seeds", type=Path,
                        help="optional small local ROI seed JSON for known subject regions")
    parser.add_argument("--max-roi-frames", type=int, default=240)
    parser.add_argument("--overwrite", action="store_true")
    opts = parser.parse_args(argv)
    try:
        out = analyze_cinematic_workspace(
            opts.workspace, motion=not opts.no_motion, ocr=opts.ocr,
            max_motion_pairs=opts.max_motion_pairs,
            max_ocr_frames=opts.max_ocr_frames,
            max_plan_frames=opts.max_plan_frames, overwrite=opts.overwrite,
            roi_seeds=opts.roi_seeds, max_roi_frames=opts.max_roi_frames,
        )
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"cinematic intelligence failed: {exc}\n")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
