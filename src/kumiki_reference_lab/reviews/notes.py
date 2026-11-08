"""Source-PTS-grounded, non-authoritative cinematic review annotations.

This module validates attribution and evidence links, not the truth of prose.
Neither a human review note nor a model observation modifies the analysis run,
proposals, catalog or study manifest.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.contracts.analysis import (
    REVIEW_NOTES_VERSION, REFERENCE_STUDY_VERSION, REFERENCE_STUDY_V1_VERSION,
    REFERENCE_STUDY_V2_VERSION, REFERENCE_STUDY_V3_VERSION,
    REFERENCE_STUDY_V4_VERSION,
)
from kumiki_reference_lab.core.artifacts import write_json_artifact
from kumiki_reference_lab.pipeline.analyze import _validate_existing
from kumiki_reference_lab.pipeline.study import _verify_study


_CATEGORIES = frozenset({
    "story", "attention", "composition", "camera", "lighting", "materials",
    "animation", "editing", "sound", "other",
})
_LAYERS = frozenset({
    "visible-observation", "visual-hypothesis", "story-interpretation",
    "implementation-suggestion",
})
_CONFIDENCES = frozenset({"low", "medium", "high"})
_ASSESSMENTS = frozenset({"supports", "contradicts", "unresolved", "not-applicable"})
_ID_PATTERN = re.compile(r"^note-[a-z0-9][a-z0-9-]{0,62}$")


def _fields(item: Any, *, expected: set[str], optional: set[str] | None = None,
            label: str) -> dict[str, Any]:
    if not isinstance(item, dict) or not expected.issubset(item) or (
            set(item) - expected - (optional or set())):
        raise ValueError(f"{label} must contain only its required/optional fields")
    return item


def _string(value: Any, *, label: str, limit: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be a nonempty bounded string")
    return value


def _hash(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch("[a-f0-9]{64}", value):
        raise ValueError(f"{label} must be a sha256 hex digest")
    return value


def _study_context(manifest_path: Path) -> tuple[dict[str, Any], dict[str, Any],
                                                 dict[str, Any], set[int]]:
    if manifest_path.name != "study-manifest.json":
        raise ValueError("expected study-manifest.json")
    study = _json_file(manifest_path, limit=262_144)
    settings = study.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("study has missing settings")
    _verify_study(manifest_path.parent, settings)
    run_name = settings.get("analysisRunDirectory")
    if (not isinstance(run_name, str) or
            not re.fullmatch(r"analysis-[a-f0-9]{12}-[a-f0-9]{20}", run_name)):
        raise ValueError("study analysis directory has an unsafe identity")
    if study["schemaVersion"] not in (
            REFERENCE_STUDY_V1_VERSION, REFERENCE_STUDY_V2_VERSION,
            REFERENCE_STUDY_V3_VERSION,
            REFERENCE_STUDY_V4_VERSION,
            REFERENCE_STUDY_VERSION):
        raise ValueError("unsupported reference study")
    proposals = _json_file(manifest_path.parent / "technique-proposals.json",
                           limit=4_194_304)
    regions = _json_file(manifest_path.parent / "shot-evidence.json",
                         limit=4_194_304)
    if (proposals.get("source", {}).get("sha256") != settings["sourceSha256"] or
            proposals.get("provenance", {}).get("analysisRunSha256") !=
            settings["analysisRunSha256"] or
            regions.get("sourceSha256") != settings["sourceSha256"] or
            regions.get("analysisRunSha256") != settings["analysisRunSha256"]):
        raise ValueError("study reports have inconsistent analysis provenance")
    analysis = (manifest_path.parent.parent / "analysis" /
                settings["analysisRunDirectory"])
    analysis_manifest = analysis / "analysis-run.json"
    if (not analysis_manifest.is_file() or analysis_manifest.is_symlink() or
            sha256_file(analysis_manifest) != settings["analysisRunSha256"]):
        raise ValueError("study analysis run is missing or no longer matches")
    run = _json_file(analysis_manifest, limit=262_144)
    _validate_existing(analysis, run["settings"])
    timeline = _json_file(analysis / "frame-timeline.json", limit=4_194_304)
    if (timeline.get("sourceSha256") != settings["sourceSha256"] or
            timeline.get("sourceTimebase") != proposals["source"]["sourceTimebase"] or
            timeline.get("sourceStreamIndex") != proposals["source"]["streamIndex"]):
        raise ValueError("source frame timeline does not match study")
    pts = [row.get("sourcePts") for row in timeline["frames"]]
    if (not pts or any(type(value) is not int for value in pts) or
            pts != sorted(set(pts)) or timeline.get("anomalies")):
        raise ValueError("source PTS are unreliable for review annotations")
    return study, proposals, regions, set(pts)


def review_notes_template(study_manifest: Path, output: Path, *, reviewer_kind: str,
                          reviewer_id: str, model_id: str | None = None) -> Path:
    """Publish a deliberately empty draft; no claims are synthesized by code."""
    study, _, _, _ = _study_context(study_manifest)
    settings = study["settings"]
    # Appending a draft inside either immutable bundle would poison its
    # checksum inventory and make subsequent study reuse fail.
    study_root = study_manifest.parent.resolve()
    analysis_root = (study_root.parent / "analysis" /
                     settings["analysisRunDirectory"]).resolve()
    destination = output.resolve()
    if destination.is_relative_to(study_root) or destination.is_relative_to(analysis_root):
        raise ValueError("review drafts must be stored outside immutable study/analysis bundles")
    if reviewer_kind not in ("human", "ai"):
        raise ValueError("reviewer kind must be human or ai")
    _string(reviewer_id, label="reviewer id", limit=128)
    if (reviewer_kind == "ai") != (model_id is not None):
        raise ValueError("AI reviewer requires model id; human reviewer must omit it")
    if model_id is not None:
        _string(model_id, label="model id", limit=256)
    notes = {
        "schemaVersion": REVIEW_NOTES_VERSION,
        "study": {
            "manifestSha256": sha256_file(study_manifest),
            "sourceSha256": settings["sourceSha256"],
            "analysisRunSha256": settings["analysisRunSha256"],
            "proposalsSha256": settings["proposalsSha256"],
            "shotEvidenceSha256": settings["shotEvidenceSha256"],
        },
        "reviewer": {"kind": reviewer_kind, "id": reviewer_id,
                     "modelId": model_id},
        "reviewStatus": "draft",
        "annotations": [],
    }
    # Use an immutable, no-overwrite writer. An authored version should be
    # stored outside the study directory and never amend its manifest.
    return write_json_artifact(output, "review-notes.json", notes)


def validate_review_notes(study_manifest: Path, notes_path: Path) -> dict[str, Any]:
    """Validate shape, reviewer and exact source-timeline anchors.

    A successful result is *structural verification* only. It never
    certifies interpretation correctness or premium artistic quality.
    """
    study, proposals, regions, original_pts = _study_context(study_manifest)
    if notes_path.name != "review-notes.json":
        raise ValueError("expected review-notes.json")
    notes = _json_file(notes_path, limit=1_048_576)
    _fields(notes, expected={"schemaVersion", "study", "reviewer",
                             "reviewStatus", "annotations"}, label="review notes")
    if notes["schemaVersion"] != REVIEW_NOTES_VERSION:
        raise ValueError("unsupported review notes version")
    expected_study = {
        "manifestSha256": sha256_file(study_manifest),
        "sourceSha256": study["settings"]["sourceSha256"],
        "analysisRunSha256": study["settings"]["analysisRunSha256"],
        "proposalsSha256": study["settings"]["proposalsSha256"],
        "shotEvidenceSha256": study["settings"]["shotEvidenceSha256"],
    }
    _fields(notes["study"], expected=set(expected_study), label="study identity")
    for key, value in expected_study.items():
        _hash(notes["study"][key], label=f"study {key}")
        if notes["study"][key] != value:
            raise ValueError(f"review notes contain stale study identity: {key}")
    reviewer = _fields(notes["reviewer"], expected={"kind", "id", "modelId"},
                       label="reviewer")
    if reviewer["kind"] not in ("human", "ai"):
        raise ValueError("invalid reviewer kind")
    _string(reviewer["id"], label="reviewer id", limit=128)
    if reviewer["kind"] == "ai":
        _string(reviewer["modelId"], label="AI model id", limit=256)
    elif reviewer["modelId"] is not None:
        raise ValueError("human reviewer must not specify an AI model")
    if notes["reviewStatus"] != "draft":
        raise ValueError("review notes never grant human approval")
    entries = notes["annotations"]
    if not isinstance(entries, list) or len(entries) > 64:
        raise ValueError("annotations must be a bounded list (max 64)")
    targets: dict[tuple[str, str], tuple[int, int]] = {}
    for cue in proposals["candidates"]:
        pts = cue["sourcePtsRange"]
        targets[("cue", cue["id"])] = (pts["startPts"], pts["endPts"])
    for region in regions["regions"]:
        targets[("region", region["id"])] = (
            region["startPtsInclusive"], region["lastObservedFramePts"])
    seen: set[str] = set()
    count_by_layer: dict[str, int] = {}
    for annotation in entries:
        row = _fields(annotation, expected={
            "id", "target", "category", "layer", "statement",
            "confidence", "assessment", "evidenceFrames", "uncertainties",
        }, label="annotation")
        if not isinstance(row["id"], str) or not _ID_PATTERN.fullmatch(row["id"]):
            raise ValueError("annotation ids must use note-<slug>")
        if row["id"] in seen:
            raise ValueError("duplicate annotation id")
        seen.add(row["id"])
        target = _fields(row["target"], expected={"kind", "id"}, label="target")
        if (not isinstance(target["kind"], str) or
                not isinstance(target["id"], str)):
            raise ValueError("annotation target kind/id must be strings")
        if (target["kind"], target["id"]) not in targets:
            raise ValueError("annotation target is absent from verified study")
        if (not isinstance(row["category"], str) or
                not isinstance(row["layer"], str)):
            raise ValueError("annotation category/layer must be strings")
        if row["category"] not in _CATEGORIES or row["layer"] not in _LAYERS:
            raise ValueError("unsupported annotation category/layer")
        _string(row["statement"], label="statement", limit=2000)
        if (not isinstance(row["confidence"], str) or
                not isinstance(row["assessment"], str)):
            raise ValueError("confidence and cue assessment must be strings")
        if row["confidence"] not in _CONFIDENCES or row["assessment"] not in _ASSESSMENTS:
            raise ValueError("invalid confidence or cue assessment")
        if target["kind"] == "region" and row["assessment"] != "not-applicable":
            raise ValueError("region annotations cannot assess a technique cue")
        if target["kind"] == "cue" and row["assessment"] == "not-applicable":
            raise ValueError("cue annotations must assess their candidate hypothesis")
        uncertainties = row["uncertainties"]
        if (not isinstance(uncertainties, list) or len(uncertainties) > 8 or
                any(not isinstance(v, str) or not v.strip() or len(v) > 500
                    for v in uncertainties)):
            raise ValueError("uncertainties must be a bounded list of strings")
        if row["layer"] != "visible-observation" and not uncertainties:
            raise ValueError("interpretations and proposals require stated uncertainties")
        frame_evidence = row["evidenceFrames"]
        if (not isinstance(frame_evidence, list) or not 1 <= len(frame_evidence) <= 8):
            raise ValueError("annotations require 1..8 source frame anchors")
        first, last = targets[(target["kind"], target["id"])]
        observed: set[int] = set()
        for frame in frame_evidence:
            point = _fields(frame, expected={"sourcePts", "description"},
                            optional={"normalizedBox"}, label="frame evidence")
            pts = point["sourcePts"]
            if type(pts) is not int or pts not in original_pts or not first <= pts <= last:
                raise ValueError("frame anchor is not an observed PTS inside its target")
            if pts in observed:
                raise ValueError("duplicate source PTS in one annotation")
            observed.add(pts)
            _string(point["description"], label="frame description", limit=500)
            if "normalizedBox" in point:
                box = point["normalizedBox"]
                if (not isinstance(box, list) or len(box) != 4 or
                        any(type(value) not in (int, float) or
                            not 0 <= value <= 1 for value in box) or
                        box[2] <= 0 or box[3] <= 0 or
                        box[0] + box[2] > 1 + 1e-9 or
                        box[1] + box[3] > 1 + 1e-9):
                    raise ValueError("normalizedBox must fit inside the unit frame")
        count_by_layer[row["layer"]] = count_by_layer.get(row["layer"], 0) + 1
    return {
        "schemaVersion": REVIEW_NOTES_VERSION,
        "sourceSha256": study["settings"]["sourceSha256"],
        "reviewerKind": reviewer["kind"],
        "annotationCount": len(entries),
        "layers": dict(sorted(count_by_layer.items())),
        "structureStatus": "source-anchors-verified",
        "semanticStatus": "not-verified",
        "artisticApproval": "not-granted",
    }
