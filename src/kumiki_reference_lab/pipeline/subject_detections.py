"""Provider-neutral, source-verified object detections to provisional tracklets.

Detections are provided by an external, locally run vision model. This
module neither runs a model nor asserts character identity, age or ethnicity.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from bisect import bisect_right
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.reviews.character_scene import (
    SCHEMA_VERSION as SCENE_VERSION, validate_character_scene,
)

INPUT_VERSION = "kumiki.subject-detections.v1"
OUTPUT_VERSION = "kumiki.subject-tracklets.v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_CLASS_TO_KIND = {
    "person": "human",
    "animated-character": "animated-human",
    "animal": "animal",
    "anthropomorphic": "anthropomorphic",
    "other-subject": "other",
}


def _check_float(value: Any, field: str, *, lower: float = 0, upper: float = 1) -> float:
    try:
        finite = type(value) in (float, int) and math.isfinite(value)
    except (ValueError, OverflowError):
        finite = False
    if not finite or not lower <= value <= upper:
        raise ValueError(f"{field} must be a finite number between {lower} and {upper}")
    return float(value)


def _check_box(value: Any, name: str) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{name} requires normalized [x,y,width,height]")
    x, y, w, h = [_check_float(item, name) for item in value]
    if w <= 0 or h <= 0 or x + w > 1 or y + h > 1:
        raise ValueError(f"{name} is outside normalized image bounds")
    return x, y, w, h


def _iou(a: tuple[float, float, float, float],
         b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    iw = max(0.0, min(ax+aw, bx+bw) - max(ax, bx))
    ih = max(0.0, min(ay+ah, by+bh) - max(ay, by))
    intersection = iw * ih
    union = aw*ah + bw*bh - intersection
    return intersection/union if union > 0 else 0.0


def load_subject_detections(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_048_576:
        raise ValueError("detections must be a regular local JSON file at most 1 MiB")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate detection JSON property: {key}")
            result[key] = value
        return result

    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                             parse_constant=lambda value: (_ for _ in ()).throw(
                                 ValueError(f"non-finite JSON value: {value}")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid detections JSON") from exc
    validate_subject_detections(payload)
    return payload


def validate_subject_detections(data: Any) -> None:
    required = {"schemaVersion", "sourceSha256", "sourceStreamIndex", "sourceTimebase",
                "detector", "cutCandidatePts", "frames"}
    if not isinstance(data, dict) or set(data) != required or data["schemaVersion"] != INPUT_VERSION:
        raise ValueError("unsupported subject detections schema")
    if type(data["sourceSha256"]) is not str or not _SHA.fullmatch(data["sourceSha256"]):
        raise ValueError("detections require source SHA-256")
    if type(data["sourceStreamIndex"]) is not int or not 0 <= data["sourceStreamIndex"] <= 64:
        raise ValueError("detections require a valid video stream index")
    tb = data["sourceTimebase"]
    if not isinstance(tb, dict) or set(tb) != {"numerator", "denominator"}:
        raise ValueError("detections need a rational timebase")
    n, d = tb["numerator"], tb["denominator"]
    if (type(n) is not int or type(d) is not int or
            not 1 <= n <= d <= 1_000_000_000_000):
        raise ValueError("detections source timebase invalid")
    info = data["detector"]
    if not isinstance(info, dict) or set(info) != {"name", "modelSha256"}:
        raise ValueError("detector needs name and model fingerprint")
    if type(info["name"]) is not str or not 2 <= len(info["name"].strip()) <= 100:
        raise ValueError("detector name invalid")
    model_sha = info["modelSha256"]
    if model_sha is not None and (type(model_sha) is not str or not _SHA.fullmatch(model_sha)):
        raise ValueError("detector modelSha256 must be null or lowercase SHA-256")
    frames = data["frames"]
    if not isinstance(frames, list) or not 2 <= len(frames) <= 120:
        raise ValueError("detections must contain 2–120 sampled frames")
    prev_pts = None
    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, dict) or set(frame) != {"sourcePts", "detections"}:
            raise ValueError(f"frame {frame_index} must have sourcePts and detections")
        pts = frame["sourcePts"]
        if type(pts) is not int or not -(2**63) < pts < 2**63 or (
                prev_pts is not None and pts <= prev_pts):
            raise ValueError("detection frames must have strictly increasing source PTS")
        prev_pts = pts
        detections = frame["detections"]
        if not isinstance(detections, list) or len(detections) > 8:
            raise ValueError(f"frame {frame_index} exceeds 8 detections")
        checked: list[tuple[str, tuple[float, float, float, float]]] = []
        for j, proposal in enumerate(detections):
            if not isinstance(proposal, dict) or set(proposal) != {"category", "score", "box"}:
                raise ValueError(f"detection {frame_index}:{j} requires category, score and box")
            category = proposal["category"]
            if type(category) is not str or category not in _CLASS_TO_KIND:
                raise ValueError(f"detection {frame_index}:{j} category unsupported")
            _check_float(proposal["score"], f"detection {frame_index}:{j} score")
            box = _check_box(proposal["box"], f"detection {frame_index}:{j} box")
            if any(category == other_category and _iou(box, other_box) >= 0.95
                   for other_category, other_box in checked):
                raise ValueError("near-duplicate same-class boxes require detector-side deduplication")
            checked.append((category, box))
    if (frames[-1]["sourcePts"] - frames[0]["sourcePts"]) * n > d * 120:
        raise ValueError("detector sample window exceeds 120 seconds")
    cuts = data["cutCandidatePts"]
    if (not isinstance(cuts, list) or len(cuts) > 120 or
            any(type(p) is not int or not frames[0]["sourcePts"] < p <= frames[-1]["sourcePts"]
                for p in cuts) or cuts != sorted(set(cuts))):
        raise ValueError("cut candidates must be distinct increasing source PTS within samples")


def _match_previous(active: dict[str, dict[str, Any]], proposed: list[dict[str, Any]],
                    min_iou: float, margin: float) -> dict[int, str]:
    """Mutual best matches only, abstaining on close competitors in either direction."""
    by_detection: dict[int, list[tuple[float, str]]] = {}
    by_track: dict[str, list[tuple[float, int]]] = {}
    for idx, det in enumerate(proposed):
        candidates = []
        for tid, previous in active.items():
            if previous["category"] != det["category"]:
                continue
            overlap = _iou(tuple(det["box"]), tuple(previous["box"]))
            if overlap >= min_iou:
                candidates.append((overlap, tid))
                by_track.setdefault(tid, []).append((overlap, idx))
        by_detection[idx] = sorted(candidates, key=lambda x: (-x[0], x[1]))
    matches = {}
    for idx, candidates in by_detection.items():
        if not candidates:
            continue
        best, tid = candidates[0]
        second = candidates[1][0] if len(candidates) > 1 else 0.0
        track_candidates = sorted(by_track[tid], key=lambda x: (-x[0], x[1]))
        track_second = track_candidates[1][0] if len(track_candidates) > 1 else 0.0
        if (track_candidates[0][1] == idx and best-second > margin and
                best-track_second > margin):
            matches[idx] = tid
    return matches


def associate_detection_tracklets(data: dict[str, Any], *, min_iou: float = 0.35,
                                  ambiguity_margin: float = 0.10,
                                  min_score: float = 0.25) -> tuple[dict[str, Any], dict[str, Any]]:
    """Deterministic tracklets within adjacent non-cut frames only."""
    validate_subject_detections(data)
    for name, value, low, high in [
        ("min_iou", min_iou, 0.05, 0.95),
        ("ambiguity_margin", ambiguity_margin, 0.0, 0.5),
        ("min_score", min_score, 0.0, 1.0),
    ]:
        _check_float(value, name, lower=low, upper=high)
    cuts = data["cutCandidatePts"]
    active: dict[str, dict[str, Any]] = {}
    roster: list[dict[str, Any]] = []
    appearances: list[dict[str, Any]] = []
    out_frames = []
    track_counts = {}
    serial = 0
    previous_pts = None
    unlinked_due_to_ambiguity = 0
    score_rejections = 0
    for frame in data["frames"]:
        pts = frame["sourcePts"]
        crosses_cut = (previous_pts is not None and
                       bisect_right(cuts, previous_pts) < bisect_right(cuts, pts))
        if crosses_cut:
            active = {}
        proposed = [dict(p) for p in frame["detections"] if p["score"] >= min_score]
        score_rejections += len(frame["detections"]) - len(proposed)
        matches = _match_previous(active, proposed, min_iou, ambiguity_margin)
        new_active = {}
        per_frame = []
        for index, p in enumerate(proposed):
            tid = matches.get(index)
            matched = tid is not None
            if tid is None:
                serial += 1
                if serial > 100:
                    raise ValueError("too many provisional subjects for character-scene roster")
                tid = f"subject_{serial:03d}"
                category = p["category"]
                roster.append({
                    "id": tid, "kind": _CLASS_TO_KIND[category],
                    "label": f"Unverified subject tracklet {serial:03d}",
                    "visualDescription": f"Detector-labeled {category} image region; appearance and identity not verified.",
                })
                if active and any(
                    previous["category"] == category and
                    _iou(tuple(p["box"]), tuple(previous["box"])) >= min_iou
                    for previous in active.values()
                ):
                    unlinked_due_to_ambiguity += 1
            new_active[tid] = {"category": p["category"], "box": p["box"]}
            track_counts[tid] = track_counts.get(tid, 0) + 1
            per_frame.append({
                "trackletId": tid, "category": p["category"], "box": p["box"],
                "detectorScore": p["score"],
                "association": "mutual-iou-match" if matched else "new-unverified-tracklet",
                "crossedCutBeforeFrame": crosses_cut,
            })
            appearances.append({
                "characterId": tid, "startPts": pts, "endPts": pts+1,
                "anchorPts": [pts], "anchorBox": list(p["box"]),
                "visibleTraits": [],
                "observation": "Detector-proposed image region at one sampled PTS; no independently verified character identity.",
                "confidence": "low",
            })
        out_frames.append({"sourcePts": pts, "proposals": per_frame,
                           "rejectedLowScore": len(frame["detections"]) - len(proposed)})
        previous_pts, active = pts, new_active
    scene = {
        "schemaVersion": SCENE_VERSION,
        "sourceSha256": data["sourceSha256"],
        "sourceStreamIndex": data["sourceStreamIndex"],
        "sourceTimebase": data["sourceTimebase"],
        "reviewer": {"kind": "model", "id": "kumiki-external-detection-tracklets"},
        "window": {"startPts": data["frames"][0]["sourcePts"],
                   "endPts": data["frames"][-1]["sourcePts"]+1,
                   "coverage": "partial-window"},
        "characters": roster, "appearances": appearances,
        "actions": [], "utterances": [], "identityClaims": [],
    }
    validate_character_scene(scene)
    output = {
        "schemaVersion": OUTPUT_VERSION,
        "sourceSha256": data["sourceSha256"],
        "sourceStreamIndex": data["sourceStreamIndex"],
        "sourceTimebase": data["sourceTimebase"],
        "detector": data["detector"],
        "cutCandidatePts": cuts,
        "frameCount": len(data["frames"]), "trackletCount": len(roster),
        "proposalCount": len(appearances), "lowScoreRejected": score_rejections,
        "uncertainAssociationStarts": unlinked_due_to_ambiguity,
        "tracklets": [{"id": tid, "observedFrameCount": count}
                      for tid, count in sorted(track_counts.items())],
        "frames": out_frames,
        "evidenceStatus": "external-detector-proposals-unverified",
        "methodLimits": [
            "Detections, their category labels and confidence scores come from an external model, not independently frame-verified.",
            "Mutual IoU association produces provisional tracklets, not individual identity, re-identification, action, emotion or demographics.",
            "No association crosses supplied cut candidates, missing detection frames or unresolved competing matches.",
            "Cut candidates are supplied by the caller and are not independently verified by this step.",
            "One-tick appearances are discrete samples, not whole-interval visibility claims.",
        ],
    }
    return scene, output


def run_subject_detections(source: Path, detections_path: Path, out: Path, *,
                           min_iou: float = 0.35, ambiguity_margin: float = 0.10,
                           min_score: float = 0.25, ffprobe: str = "ffprobe",
                           rights_status: str = "review-required") -> Path:
    """Inspect authorized local source before accepting external detector proposals."""
    if out.exists() or out.is_symlink():
        raise ValueError("output must be a new, nonexisting directory")
    before = file_signature(source)
    input_before = file_signature(detections_path)
    detections = load_subject_detections(detections_path)
    detections_sha = sha256_file(detections_path)
    metadata = inspect_source(source, ffprobe=ffprobe, rights_status=rights_status)
    expected = {
        "sourceSha256": metadata["source"]["sha256"],
        "sourceStreamIndex": metadata["video"]["streamIndex"],
        "sourceTimebase": metadata["video"]["sourceTimebase"],
    }
    if any(detections[key] != value for key, value in expected.items()):
        raise ValueError("detector output source identity or timebase does not match video")
    scene, report = associate_detection_tracklets(
        detections, min_iou=min_iou, ambiguity_margin=ambiguity_margin, min_score=min_score)
    require_unchanged(source, before)
    require_unchanged(detections_path, input_before)
    report["rightsStatus"] = rights_status
    report["detectionFileSha256"] = detections_sha
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-detections-", dir=out.parent) as folder:
        temp = Path(folder)
        (temp / "subject-tracklets.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        (temp / "character-scene.json").write_text(
            json.dumps(scene, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        os.replace(temp, out)
    return out / "subject-tracklets.json"
