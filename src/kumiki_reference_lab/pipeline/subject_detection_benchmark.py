"""Measure provisional subject detection coverage against explicit human boxes.

Human labels are self-declared, not independently confirmed by this evaluator.
Scores are per sampled PTS frame only, never full-video accuracy.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.subject_detections import (
    _CLASS_TO_KIND, _check_box, _iou, load_subject_detections,
)
from kumiki_reference_lab.pipeline.character_vision_review import _load_json

GROUND_TRUTH_VERSION = "kumiki.subject-box-ground-truth.v1"
REPORT_VERSION = "kumiki.subject-detection-benchmark.v1"
_COVERAGE = "all-visibly-supported-subjects-on-each-listed-sampled-frame"


def _check_ground_truth(ground: dict[str, Any], detections: dict[str, Any]) -> None:
    if (not isinstance(ground, dict) or set(ground) != {
            "schemaVersion", "sourceSha256", "sourceStreamIndex",
            "sourceTimebase", "reviewer", "coverageDeclaration", "frames"
        } or ground["schemaVersion"] != GROUND_TRUTH_VERSION):
        raise ValueError("ground truth requires exact fields and supported version")
    if any(ground[k] != detections[k] for k in
           ("sourceSha256", "sourceStreamIndex", "sourceTimebase")):
        raise ValueError("ground truth and detections disagree on source identity/timebase")
    if ground["coverageDeclaration"] != _COVERAGE:
        raise ValueError("ground truth must explicitly declare complete sampled-frame labeling")
    reviewer = ground["reviewer"]
    if (not isinstance(reviewer, dict) or set(reviewer) != {"kind", "id"} or
            reviewer["kind"] != "human" or type(reviewer["id"]) is not str or
            not 2 <= len(reviewer["id"].strip()) <= 100 or
            reviewer["id"].strip() == "unassigned"):
        raise ValueError("ground truth requires an assigned human reviewer ID")
    frames = ground["frames"]
    samples = detections["frames"]
    if not isinstance(frames, list) or len(frames) != len(samples):
        raise ValueError("ground truth must cover every predicted sampled video PTS")
    for i, (observed, predicted) in enumerate(zip(frames, samples, strict=True)):
        if (not isinstance(observed, dict) or set(observed) != {"sourcePts", "subjects"} or
                type(observed["sourcePts"]) is not int or
                observed["sourcePts"] != predicted["sourcePts"]):
            raise ValueError(f"ground truth frame {i} must match the exact source PTS")
        subjects = observed["subjects"]
        if not isinstance(subjects, list) or len(subjects) > 20:
            raise ValueError(f"ground truth frame {i} has too many subject boxes")
        verified = []
        for j, item in enumerate(subjects):
            if not isinstance(item, dict) or set(item) != {"category", "box"}:
                raise ValueError(f"ground truth subject {i}:{j} must have category and box")
            category = item["category"]
            if type(category) is not str or category not in _CLASS_TO_KIND:
                raise ValueError("unsupported human subject category in ground truth")
            box = _check_box(item["box"], "ground truth subject box")
            if any(_iou(box, prior) >= .95 for prior in verified):
                raise ValueError("duplicate ground-truth boxes cannot be counted as separate characters")
            verified.append(box)


def _maximum_cardinality_matches(predicted: list[dict[str, Any]],
                                 labeled: list[dict[str, Any]],
                                 threshold: float) -> list[tuple[int, int, float]]:
    """Deterministic bipartite matching, not naive per-prediction greedy overlap.

    This maximizes the count of valid matches; it is not a maximum-IoU-sum optimizer.
    """
    edges: list[list[tuple[int, float]]] = []
    for detected in predicted:
        candidates = []
        for j, target in enumerate(labeled):
            if detected["category"] != target["category"]:
                continue
            overlap = _iou(tuple(detected["box"]), tuple(target["box"]))
            if overlap >= threshold:
                candidates.append((j, overlap))
        edges.append(sorted(candidates, key=lambda value: (-value[1], value[0])))
    gt_to_pred: dict[int, int] = {}

    def augment(index: int, seen: set[int]) -> bool:
        for j, score in edges[index]:
            if j in seen:
                continue
            seen.add(j)
            if j not in gt_to_pred or augment(gt_to_pred[j], seen):
                gt_to_pred[j] = index
                return True
        return False

    for i in range(len(predicted)):
        augment(i, set())
    matched = [(i, j, _iou(tuple(predicted[i]["box"]), tuple(labeled[j]["box"])))
               for j, i in gt_to_pred.items()]
    return sorted(matched, key=lambda item: item[0])


def _rates(counter: Counter) -> dict[str, Any]:
    tp, fp, fn = counter["tp"], counter["fp"], counter["fn"]
    p = round(tp/(tp+fp), 6) if tp+fp else None
    r = round(tp/(tp+fn), 6) if tp+fn else None
    if p is None or r is None:
        f1 = None
    elif p+r == 0:
        f1 = 0.0
    else:
        f1 = round(2*p*r/(p+r), 6)
    return {
        "truePositives": tp, "falsePositives": fp, "falseNegatives": fn,
        "precision": p, "recall": r, "f1": f1,
    }


def evaluate_subject_boxes(predictions: dict[str, Any],
                           ground_truth: dict[str, Any], *,
                           min_iou: float = 0.5) -> dict[str, Any]:
    if (type(min_iou) not in (float, int) or not math.isfinite(min_iou) or
            not .25 <= min_iou <= .9):
        raise ValueError("minimum IoU must be finite between 0.25 and 0.9")
    _check_ground_truth(ground_truth, predictions)
    overall = Counter()
    by_class: dict[str, Counter] = {}
    frames = []
    for annotation, prediction in zip(ground_truth["frames"], predictions["frames"], strict=True):
        proposals, labels = prediction["detections"], annotation["subjects"]
        matched = _maximum_cardinality_matches(proposals, labels, min_iou)
        observed_pred = {i for i, _, _ in matched}
        observed_gt = {j for _, j, _ in matched}
        matched_rows = []
        for i, j, overlap in matched:
            cat = proposals[i]["category"]
            by_class.setdefault(cat, Counter())["tp"] += 1
            overall["tp"] += 1
            matched_rows.append({"predictionIndex": i, "labelIndex": j,
                                 "category": cat, "iou": round(overlap, 6)})
        extra = [i for i in range(len(proposals)) if i not in observed_pred]
        missed = [j for j in range(len(labels)) if j not in observed_gt]
        for i in extra:
            cat = proposals[i]["category"]
            overall["fp"] += 1
            by_class.setdefault(cat, Counter())["fp"] += 1
        for j in missed:
            cat = labels[j]["category"]
            overall["fn"] += 1
            by_class.setdefault(cat, Counter())["fn"] += 1
        frames.append({
            "sourcePts": prediction["sourcePts"],
            "matches": matched_rows,
            "unmatchedPredictionIndices": extra,
            "unmatchedHumanBoxIndices": missed,
            **_rates(Counter(tp=len(matched), fp=len(extra), fn=len(missed))),
        })
    return {
        "schemaVersion": REPORT_VERSION,
        "sourceSha256": predictions["sourceSha256"],
        "sourceStreamIndex": predictions["sourceStreamIndex"],
        "sourceTimebase": predictions["sourceTimebase"],
        "reviewer": ground_truth["reviewer"],
        "iouMatchThreshold": min_iou,
        "sampledFrameCount": len(frames),
        "overall": _rates(overall),
        "byCategory": [
            {"category": cat, **_rates(stat)}
            for cat, stat in sorted(by_class.items())
        ],
        "frames": frames,
        "evidenceStatus": "human-declared-ground-truth-not-independently-media-verified",
        "limitations": [
            "Precision and recall are computed only against explicitly labeled sampled source frames, not all video frames.",
            "Human label completeness, box correctness and subject categories are declared but not independently audited.",
            "Matching maximizes the number of same-class IoU>=threshold pairs, not tracklet continuity or sum of IoUs.",
            "Model score 0.5 is an uncalibrated compatibility sentinel for Ollama boxes, never a probability.",
            "No character identity switches, dialogue, interactions, demographics or visual VLM descriptions are evaluated.",
            "Empty prediction and label sets have null precision/recall, never automatic perfect accuracy.",
        ],
    }



def create_subject_box_label_template(detection_path: Path, out: Path) -> Path:
    """Create a deliberately UNAPPROVED human label skeleton for each sampled PTS.

    Empty boxes mean labels are not yet supplied, never that the frame is empty.
    """
    if out.exists() or out.is_symlink():
        raise ValueError("human label template destination must be a new file")
    signature = file_signature(detection_path)
    predictions = load_subject_detections(detection_path)
    template = {
        "schemaVersion": GROUND_TRUTH_VERSION,
        "sourceSha256": predictions["sourceSha256"],
        "sourceStreamIndex": predictions["sourceStreamIndex"],
        "sourceTimebase": predictions["sourceTimebase"],
        "reviewer": {"kind": "human", "id": "unassigned"},
        "coverageDeclaration": "pending-review",
        "frames": [
            {"sourcePts": item["sourcePts"], "subjects": []}
            for item in predictions["frames"]
        ],
    }
    require_unchanged(detection_path, signature)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-box-labels-", dir=out.parent) as temp:
        staging = Path(temp) / "subject-box-labels.json"
        staging.write_text(
            json.dumps(template, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        require_unchanged(detection_path, signature)
        if out.exists() or out.is_symlink():
            raise ValueError("human label template output became occupied")
        os.replace(staging, out)
    return out



def run_subject_box_benchmark(source: Path, detection_path: Path,
                              ground_truth_path: Path, out: Path, *,
                              min_iou: float = 0.5,
                              ffprobe: str = "ffprobe") -> Path:
    """Verify source bytes/PTS contract before benchmarking human-provided boxes."""
    if out.exists() or out.is_symlink():
        raise ValueError("benchmark output must be a new nonexisting directory")
    if source.is_symlink() or not source.is_file():
        raise ValueError("benchmark requires an authorized regular local video")
    originals = (source, detection_path, ground_truth_path)
    signatures = [file_signature(path) for path in originals]
    predictions = load_subject_detections(detection_path)
    labels = _load_json(ground_truth_path, limit=512*1024)
    info = inspect_source(source, ffprobe=ffprobe)
    if (info["source"]["sha256"] != predictions["sourceSha256"] or
            info["video"]["streamIndex"] != predictions["sourceStreamIndex"] or
            info["video"]["sourceTimebase"] != predictions["sourceTimebase"]):
        raise ValueError("benchmark source bytes, stream or timebase do not match detections")
    report = evaluate_subject_boxes(predictions, labels, min_iou=min_iou)
    report["detectionFileSha256"] = sha256_file(detection_path)
    report["groundTruthFileSha256"] = sha256_file(ground_truth_path)
    for path, signature in zip(originals, signatures, strict=True):
        require_unchanged(path, signature)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-box-benchmark-", dir=out.parent) as temp:
        staging = Path(temp)
        (staging / "subject-detection-benchmark.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        for path, signature in zip(originals, signatures, strict=True):
            require_unchanged(path, signature)
        if out.exists() or out.is_symlink():
            raise ValueError("benchmark output path became occupied")
        os.replace(staging, out)
    return out / "subject-detection-benchmark.json"
