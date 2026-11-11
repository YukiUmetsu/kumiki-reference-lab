"""Cost-bounded, three-anchor visual sequence review for existing ROI events.

Two *separate* two-image Magnitude calls evaluate start->middle and
middle->end.  This is NOT video understanding or semantic action detection.
Only existing shot-local, consecutively supported source-frame observations
can enter a sequence; no AI result changes seed identities or measurements.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from kumiki_reference_lab.pipeline.agent_frame_review import _frame_path, load_workspace
from kumiki_reference_lab.pipeline.magnitude_vision import _MODEL
from kumiki_reference_lab.pipeline.multi_region_temporal import _validate_tracks
from kumiki_reference_lab.pipeline.online_event_review import (
    _call_local_event_model, _outlined_preview,
)

SCHEMA_VERSION = "kumiki.online-three-anchor-sequence-review.v1"
_TEMPORAL_SCHEMA = "kumiki.online-multi-region-temporal.v1"
_ACTIVE = {"seeded-2d-region-motion-candidates",
           "auto-seeded-2d-region-motion-candidates"}


def _candidate_groups(temporal: dict[str, Any], *,
                      max_sequences: int) -> list[dict[str, Any]]:
    """Deduplicate costly image calls for events sharing the same anchors/ROI."""
    events = temporal.get("events")
    tasks = temporal.get("reviewTasks")
    if (not isinstance(events, list) or len(events) > 200
            or not isinstance(tasks, list) or len(tasks) > 48):
        raise ValueError("sequence plan exceeds event/review budgets")
    event_keys: set[tuple[Any, ...]] = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("sequence event must be an object")
        event_keys.add((
            event.get("eventType"), event.get("shotId"),
            event.get("subjectA"), event.get("subjectB"),
            event.get("startFrameIndex"), event.get("endFrameIndex"),
        ))
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("invalid temporal sequence review task")
        subjects = task.get("subjectIds")
        frames = task.get("frameIndices")
        if (not isinstance(subjects, list) or not 1 <= len(subjects) <= 2
                or any(type(subject) is not str or not subject
                       for subject in subjects)
                or len(subjects) != len(set(subjects))
                or not isinstance(frames, list) or len(frames) != 3
                or any(type(frame) is not int for frame in frames)
                or not frames[0] < frames[1] < frames[2]
                or type(task.get("shotId")) is not str
                or type(task.get("eventType")) is not str):
            raise ValueError("sequence needs exactly three distinct measured anchors")
        signature = (task["eventType"], task["shotId"],
                     subjects[0], subjects[1] if len(subjects) == 2 else None,
                     frames[0], frames[2])
        if signature not in event_keys:
            raise ValueError("sequence review task is not linked to a measured event")
        key = (task["shotId"], tuple(subjects), tuple(frames))
        if key not in grouped:
            grouped[key] = {
                "shotId": task["shotId"],
                "subjectIds": subjects,
                "frameIndices": frames,
                "measuredEventTypes": [],
            }
        if task["eventType"] not in grouped[key]["measuredEventTypes"]:
            grouped[key]["measuredEventTypes"].append(task["eventType"])
    # Pairwise evidence first, then coverage across shots, then chronological.
    ordered = sorted(grouped.values(), key=lambda item: (
        -len(item["subjectIds"]), -len(item["measuredEventTypes"]),
        item["frameIndices"][0], item["shotId"],
        ",".join(item["subjectIds"]),
    ))
    return ordered[:max_sequences]


def _sequence_key(source_sha: str, group: dict[str, Any]) -> str:
    material = (
        source_sha + ":" + group["shotId"] + ":" +
        ",".join(group["subjectIds"]) + ":" +
        ",".join(str(i) for i in group["frameIndices"])
    )
    return "sequence-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def review_three_anchor_sequences(
    workspace: Path, seeded: dict[str, Any], shots: dict[str, Any],
    temporal: dict[str, Any], *, model: str,
    max_sequences: int = 4, max_calls: int = 8,
    port: int = 10100, timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Compare two contiguous phases with independently bounded model calls.

    A two-frame image model may be wrong in both phases. The output therefore
    records consistency *of guesses*, not ground-truth actions or confidence.
    """
    if (type(model) is not str or not _MODEL.fullmatch(model)
            or type(max_sequences) is not int or not 1 <= max_sequences <= 12
            or type(max_calls) is not int or not 2 <= max_calls <= 24
            or type(port) is not int or not 1 <= port <= 65535
            or type(timeout_seconds) is not int
            or not 5 <= timeout_seconds <= 300):
        raise ValueError("invalid three-anchor review budgets or model")
    manifest, numeric, _ = load_workspace(workspace)
    sha = manifest["sourceSha256"]
    if (not isinstance(temporal, dict)
            or temporal.get("schemaVersion") != _TEMPORAL_SCHEMA
            or temporal.get("sourceSha256") != sha
            or temporal.get("frameCount") != manifest["frameCount"]
            or shots.get("sourceSha256") != sha
            or shots.get("frameCount") != manifest["frameCount"]):
        raise ValueError("sequence source and shot provenance mismatch")
    tracks = (_validate_tracks(seeded, numeric, shots)
              if seeded.get("status") in _ACTIVE else [])
    by_id = {t["id"]: t for t in tracks}
    by_shot = {s["shotId"]: s for s in shots["shots"]}
    proposed = _candidate_groups(temporal, max_sequences=max_sequences)
    width, height = manifest["width"], manifest["height"]
    if (type(width) is not int or type(height) is not int
            or not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("sequence preview resolution unsupported")

    # Validate the *full* proposed plan before any inference, not only the
    # initial calls the budget will permit.
    validated: list[dict[str, Any]] = []
    for group in proposed:
        shot = by_shot.get(group["shotId"])
        if shot is None or any(
                not shot["startFrameIndex"] <= f < shot["endFrameIndexExclusive"]
                for f in group["frameIndices"]):
            raise ValueError("three-anchor sequence crosses a source shot")
        references: list[list[tuple[float, float, float, float]]] = []
        for frame in group["frameIndices"]:
            boxes = []
            for ident in group["subjectIds"]:
                track = by_id.get(ident)
                if track is None or track["shotId"] != group["shotId"]:
                    raise ValueError("sequence track identity/shot mismatch")
                row = next((p for p in track["observations"]
                            if p["frame"] == frame), None)
                if row is None:
                    raise ValueError("sequence cannot interpolate missing track frames")
                boxes.append(row["box"])
            references.append(boxes)
        validated.append({**group, "boxes": references})

    candidates = len(validated)
    results: list[dict[str, Any]] = []
    total_calls = 0
    unavailable = False
    for group in validated:
        if unavailable or total_calls + 2 > max_calls:
            break
        frames = group["frameIndices"]
        source_times = [
            numeric["frames"][index]["decodedSeconds"] for index in frames]
        observations = []
        for (a, b) in ((0, 1), (1, 2)):
            images = [
                _outlined_preview(
                    _frame_path(workspace.absolute(), frames[slot]),
                    width, height, group["boxes"][slot])
                for slot in (a, b)
            ]
            total_calls += 1
            try:
                result = _call_local_event_model(
                    images, model=model, port=port,
                    timeout_seconds=timeout_seconds)
                label, evidence = result["category"], result["evidence"]
                status = "unverified-two-frame-phase-hypothesis"
            except (ValueError, OSError) as exc:
                label, evidence = "unknown", ""
                unavailable = "unavailable" in str(exc)
                status = ("local-model-unavailable" if unavailable
                          else "invalid-model-reply-abstention")
            observations.append({
                "phase": "first-to-middle" if a == 0 else "middle-to-last",
                "frameIndices": [frames[a], frames[b]],
                "categoryHypothesis": label,
                "visibleEvidenceHypothesis": evidence,
                "status": status,
            })
            if unavailable:
                break
        accepted = [
            p["categoryHypothesis"] for p in observations
            if p["status"] == "unverified-two-frame-phase-hypothesis"]
        if len(accepted) == 2 and accepted[0] == accepted[1] != "unknown":
            pattern = ("consistent-no-clear-change-unverified"
                       if accepted[0] == "no-clear-change"
                       else "repeated-visual-change-unverified")
        elif len(accepted) == 2 and all(
                x not in ("unknown", "no-clear-change") for x in accepted):
            pattern = "different-visible-phases-unverified"
        else:
            pattern = "insufficient-consistent-visual-evidence"
        results.append({
            "sequenceId": _sequence_key(sha, group),
            "shotId": group["shotId"],
            "subjectIds": group["subjectIds"],
            "identityProvenance": [
                by_id[ident]["origin"] for ident in group["subjectIds"]],
            "frameIndices": frames,
            "sourceDecodedSeconds": source_times,
            "measuredEventTypes": group["measuredEventTypes"],
            "phaseObservations": observations,
            "sequencePatternHypothesis": pattern,
            "status": "unverified-short-sequence-not-semantic-action",
        })
    return {
        "schemaVersion": SCHEMA_VERSION, "sourceSha256": sha,
        "frameCount": manifest["frameCount"], "modelTag": model,
        "modelCalls": total_calls, "maxModelCalls": max_calls,
        "maxSequences": max_sequences,
        "candidateSequences": candidates,
        "reviewedSequences": len(results),
        "remainingSequences": candidates - len(results),
        "sequences": results,
        "status": ("local-sequence-model-unavailable-partial" if unavailable
                   else "unverified-three-anchor-visual-sequences" if results
                   else "no-sequences-reviewed"),
        "limits": [
            "Two separate two-frame comparisons do not reconstruct continuous video.",
            "Matching predictions are model agreement, not calibrated action recognition.",
            "No character identity or same-person association across shot cuts.",
            "No skeletal pose, gesture intent, touch, speech, object transfer or causality.",
            "Movement could arise from camera, parallax, compositing, or different subjects.",
            "Only same-shot source-verified ROI track observations can enter the plan.",
            "No frame crops, original video, payloads or source images are saved.",
            "Magnitude must run on localhost; inference is strictly opt-in and bounded.",
        ],
    }
