"""Evaluate optional online three-anchor VLM hypotheses against explicit human labels.

Unlike model agreement statistics, this benchmark can measure mistakes.
It never treats labels as reviewed until a human explicitly declares full
phase coverage. All scores describe only reviewed source-bound samples, not
full videos or ground-truth character actions.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

from kumiki_reference_lab.pipeline.online_event_review import _KINDS

LABEL_VERSION = "kumiki.three-anchor-human-phase-labels.v1"
BENCHMARK_VERSION = "kumiki.three-anchor-visual-benchmark.v1"
AGGREGATE_VERSION = "kumiki.three-anchor-benchmark-aggregate.v1"
_COVERAGE = "all-listed-source-frame-phases-human-reviewed"
_PHASES = ("first-to-middle", "middle-to-last")
_ABSTAIN = "abstain"
_UNOBSERVABLE = "not-observable"
_MODEL_OK = "unverified-two-frame-phase-hypothesis"
_MODEL_ABSTAIN = {"invalid-model-reply-abstention", "local-model-unavailable"}
_MAX_BYTES = 8_000_000


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError("duplicate JSON property in benchmark input")
        seen[key] = value
    return seen


def _load(path: Path) -> tuple[dict[str, Any], str]:
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= _MAX_BYTES):
        raise ValueError("benchmark input must be a bounded regular JSON file")
    raw = path.read_bytes()
    try:
        doc = json.loads(
            raw, object_pairs_hook=_unique,
            parse_constant=lambda v: (_ for _ in ()).throw(
                ValueError("nonfinite JSON number in benchmark input")))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("benchmark input is not strict JSON") from exc
    if not isinstance(doc, dict):
        raise ValueError("benchmark input must be a JSON object")
    return doc, hashlib.sha256(raw).hexdigest()


def _sha(raw: Any) -> bool:
    return (type(raw) is str and len(raw) == 64
            and all(c in "0123456789abcdef" for c in raw))


def _integer(value: Any, *, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _insights_sequences(insights: dict[str, Any]
                        ) -> tuple[str, str, list[dict[str, Any]]]:
    if insights.get("schemaVersion") != "kumiki.online-cinematic-insights.v1":
        raise ValueError("expected full online cinematic insights report")
    source = insights.get("source")
    sequence = insights.get("threeAnchorSequenceReview")
    shots = insights.get("shotIntelligence")
    if not isinstance(source, dict) or not isinstance(sequence, dict):
        raise ValueError("insights missing source or three-anchor sequence report")
    sha = source.get("sourceSha256")
    frame_count = source.get("frameCount")
    if (not _sha(sha) or not _integer(frame_count, low=1, high=108000)
            or sequence.get("schemaVersion") !=
            "kumiki.online-three-anchor-sequence-review.v1"
            or sequence.get("sourceSha256") != sha
            or sequence.get("frameCount") != frame_count
            or not isinstance(shots, dict)
            or shots.get("sourceSha256") != sha
            or shots.get("frameCount") != frame_count
            or not isinstance(shots.get("shots"), list)):
        raise ValueError("sequence/source SHA or frame-count provenance mismatch")
    model = sequence.get("modelTag")
    if type(model) is not str or not 1 <= len(model) <= 120:
        raise ValueError("model identity missing in sequence report")
    rows = sequence.get("sequences")
    if not isinstance(rows, list) or len(rows) > 12:
        raise ValueError("sequence report count exceeds supported bounds")
    by_shot = {s.get("shotId"): s for s in shots["shots"]
               if isinstance(s, dict) and type(s.get("shotId")) is str}
    result = []
    unique_ids = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid sequence row")
        ident, shot_id = row.get("sequenceId"), row.get("shotId")
        frames, times = row.get("frameIndices"), row.get("sourceDecodedSeconds")
        phases = row.get("phaseObservations")
        subjects = row.get("subjectIds")
        shot = by_shot.get(shot_id)
        if (type(ident) is not str or not ident.startswith("sequence-")
                or len(ident) > 70 or ident in unique_ids
                or not isinstance(frames, list) or len(frames) != 3
                or any(not _integer(i, low=0, high=frame_count-1) for i in frames)
                or frames != sorted(set(frames))
                or not isinstance(times, list) or len(times) != 3
                or any(type(t) not in (float, int) or not math.isfinite(t)
                       for t in times)
                or any(b <= a for a, b in zip(times, times[1:]))
                or not isinstance(subjects, list) or not 1 <= len(subjects) <= 2
                or any(type(s) is not str or not s for s in subjects)
                or len(set(subjects)) != len(subjects)
                or shot is None
                or any(not shot["startFrameIndex"] <= i <
                       shot["endFrameIndexExclusive"] for i in frames)
                or not isinstance(phases, list) or not 1 <= len(phases) <= 2):
            raise ValueError("malformed/duplicate source-bound sequence")
        unique_ids.add(ident)
        seen = set()
        predictions = {}
        for phase in phases:
            name = phase.get("phase") if isinstance(phase, dict) else None
            observed = (frames[:2] if name == _PHASES[0] else frames[1:])
            status = phase.get("status") if isinstance(phase, dict) else None
            category = phase.get("categoryHypothesis") if isinstance(phase, dict) else None
            if (name not in _PHASES or name in seen
                    or phase.get("frameIndices") != observed
                    or status not in {_MODEL_OK, *_MODEL_ABSTAIN}
                    or category not in _KINDS
                    or (status != _MODEL_OK and category != "unknown")):
                raise ValueError("sequence phase prediction is unsupported or misaligned")
            seen.add(name)
            predictions[name] = {
                "category": category,
                "status": status,
            }
        if phases[0]["phase"] != _PHASES[0]:
            raise ValueError("partial sequence must start at first-to-middle phase")
        result.append({
            "sequenceId": ident,
            "shotId": shot_id, "subjectIds": subjects,
            "frameIndices": frames,
            "sourceDecodedSeconds": times,
            "model": predictions,
        })
    return sha, model, result


def make_label_template(insights: dict[str, Any], *, insights_sha: str
                        ) -> dict[str, Any]:
    source, model, rows = _insights_sequences(insights)
    if not rows:
        raise ValueError("no three-anchor predictions available for human labeling")
    return {
        "schemaVersion": LABEL_VERSION, "sourceSha256": source,
        "insightsFileSha256": insights_sha,
        "reviewer": {"kind": "human", "id": "unassigned"},
        "coverageDeclaration": "pending-review",
        "modelTagObserved": model,
        "sequences": [{
            "sequenceId": row["sequenceId"],
            "shotId": row["shotId"],
            "subjectIds": row["subjectIds"],
            "frameIndices": row["frameIndices"],
            "sourceDecodedSeconds": row["sourceDecodedSeconds"],
            "phases": [
                {"phase": name, "humanCategory": None}
                for name in _PHASES
            ],
        } for row in rows],
        "instructions": (
            "Inspect actual authorized source previews for every sampled "
            "frame/phase, not the model's predictions. Assign each phase one "
            "visible-change category, or not-observable when ambiguous. "
            "An empty/null label is pending, never a negative example. "
            "Set reviewer.id and coverageDeclaration to "
            f"{_COVERAGE} only after all phases are reviewed."
        ),
    }


def _truth(labels: dict[str, Any], rows: list[dict[str, Any]],
           *, source_sha: str, insights_sha: str,
           model: str) -> tuple[str, dict[str, dict[str, str]]]:
    if (labels.get("schemaVersion") != LABEL_VERSION
            or labels.get("sourceSha256") != source_sha
            or labels.get("insightsFileSha256") != insights_sha
            or labels.get("modelTagObserved") != model
            or labels.get("coverageDeclaration") != _COVERAGE):
        raise ValueError("human labels incomplete or stale against current insights")
    reviewer = labels.get("reviewer")
    if (not isinstance(reviewer, dict)
            or set(reviewer) != {"kind", "id"}
            or reviewer["kind"] != "human"
            or type(reviewer["id"]) is not str
            or not 2 <= len(reviewer["id"].strip()) <= 100
            or reviewer["id"].strip() == "unassigned"):
        raise ValueError("human benchmark requires a named human reviewer")
    roster = labels.get("sequences")
    if not isinstance(roster, list) or len(roster) != len(rows):
        raise ValueError("human coverage must include every reported sequence")
    truth: dict[str, dict[str, str]] = {}
    for recorded, expected in zip(roster, rows, strict=True):
        if (not isinstance(recorded, dict)
                or set(recorded) != {
                    "sequenceId", "shotId", "subjectIds", "frameIndices",
                    "sourceDecodedSeconds", "phases"}
                or any(recorded[k] != expected[k] for k in (
                    "sequenceId", "shotId", "subjectIds", "frameIndices",
                    "sourceDecodedSeconds"))):
            raise ValueError("human labels have modified or reordered source anchors")
        phases = recorded["phases"]
        if not isinstance(phases, list) or len(phases) != 2:
            raise ValueError("each sequence needs both explicitly labeled phases")
        labels_by_phase = {}
        for idx, phase in enumerate(phases):
            category = phase.get("humanCategory") if isinstance(phase, dict) else None
            if (not isinstance(phase, dict)
                    or set(phase) != {"phase", "humanCategory"}
                    or phase["phase"] != _PHASES[idx]
                    or category not in (_KINDS | {_UNOBSERVABLE})
                    or category == "unknown"):
                raise ValueError("human phase is unlabeled, invalid, or out of order")
            labels_by_phase[phase["phase"]] = category
        truth[recorded["sequenceId"]] = labels_by_phase
    return reviewer["id"], truth


def _div(a: int, b: int) -> float | None:
    return round(a / b, 6) if b else None


def _score(phases: list[dict[str, Any]]) -> dict[str, Any]:
    for row in phases:
        actual, prediction = row["humanCategory"], row["prediction"]
        expected = ("human-unobservable-excluded" if actual == _UNOBSERVABLE
                    else "model-abstained" if prediction == _ABSTAIN
                    else "correct" if actual == prediction
                    else "incorrect-category")
        if row.get("status") != expected:
            raise ValueError("phase correctness field conflicts with reviewed labels")
    scored = [x for x in phases if x["humanCategory"] != _UNOBSERVABLE]
    excluded = len(phases) - len(scored)
    attempts = [x for x in scored if x["prediction"] != _ABSTAIN]
    correct = sum(x["status"] == "correct" for x in scored)
    wrong = sum(x["status"] == "incorrect-category" for x in scored)
    abstain = len(scored) - len(attempts)
    by_category = []
    all_categories = sorted(
        {x["humanCategory"] for x in scored}
        | {x["prediction"] for x in attempts})
    for category in all_categories:
        support = sum(x["humanCategory"] == category for x in scored)
        predicted = sum(x["prediction"] == category for x in attempts)
        tp = sum(x["status"] == "correct" and
                 x["humanCategory"] == category for x in scored)
        precision = _div(tp, predicted)
        recall = _div(tp, support)
        f1 = (round(2 * precision * recall / (precision + recall), 6)
              if precision is not None and recall is not None
              and precision + recall else
              0.0 if precision is not None and recall is not None
              else None)
        by_category.append({
            "category": category, "support": support, "predicted": predicted,
            "correct": tp, "precision": precision,
            "recall": recall, "f1": f1,
        })
    confusion = Counter((x["humanCategory"], x["prediction"]) for x in scored)
    return {
        "humanLabeledPhaseCount": len(phases),
        "observablePhaseCount": len(scored),
        "humanUnobservablePhaseCount": excluded,
        "attemptedPhaseCount": len(attempts),
        "correctPhaseCount": correct,
        "incorrectPhaseCount": wrong,
        "abstainedPhaseCount": abstain,
        "coverage": _div(len(attempts), len(scored)),
        "accuracyOnAttempts": _div(correct, len(attempts)),
        "correctFractionOfObservable": _div(correct, len(scored)),
        "errorRateOnAttempts": _div(wrong, len(attempts)),
        "abstentionRateOnObservable": _div(abstain, len(scored)),
        "byCategory": by_category,
        "confusion": [{
            "human": actual, "predicted": predicted, "count": count}
            for (actual, predicted), count in sorted(confusion.items())
        ],
    }


def _score_rows(rows: list[dict[str, Any]],
                truth: dict[str, dict[str, str]]) -> tuple[list[dict[str, Any]],
                                                            dict[str, Any]]:
    phases = []
    exact = 0
    entirely_scored = 0
    for row in rows:
        this_sequence = []
        for i, phase in enumerate(_PHASES):
            label = truth[row["sequenceId"]][phase]
            predicted = row["model"].get(phase)
            guess = (predicted["category"] if predicted
                     and predicted["status"] == _MODEL_OK
                     and predicted["category"] != "unknown" else _ABSTAIN)
            status = ("human-unobservable-excluded" if label == _UNOBSERVABLE
                      else "model-abstained" if guess == _ABSTAIN
                      else "correct" if label == guess else "incorrect-category")
            item = {
                "sequenceId": row["sequenceId"], "shotId": row["shotId"],
                "phase": phase, "frameIndices": (
                    row["frameIndices"][i:i+2]),
                "humanCategory": label, "prediction": guess,
                "status": status,
            }
            phases.append(item)
            this_sequence.append(item)
        if all(v["humanCategory"] != _UNOBSERVABLE for v in this_sequence):
            entirely_scored += 1
            if all(v["status"] == "correct" for v in this_sequence):
                exact += 1
    metrics = _score(phases)
    metrics.update({
        "fullyObservableSequenceCount": entirely_scored,
        "fullyCorrectSequenceCount": exact,
        "fullSequenceExactAccuracy": _div(exact, entirely_scored),
    })
    return phases, metrics


def evaluate_sequence_labels(
    insights: dict[str, Any], labels: dict[str, Any], *,
    insights_sha: str, labels_sha: str,
) -> dict[str, Any]:
    source, model, rows = _insights_sequences(insights)
    reviewer, truth = _truth(
        labels, rows, source_sha=source,
        insights_sha=insights_sha, model=model)
    phases, metrics = _score_rows(rows, truth)
    return {
        "schemaVersion": BENCHMARK_VERSION,
        "sourceSha256": source,
        "insightsFileSha256": insights_sha,
        "humanLabelsFileSha256": labels_sha,
        "modelTag": model,
        "reviewer": {"kind": "human", "id": reviewer},
        "sequenceCount": len(rows),
        "metrics": metrics,
        "phases": phases,
        "evidenceStatus": "human-declared-phase-review-not-independently-audited",
        "limitations": [
            "Only human-reviewed sampled source frame pairs are scored.",
            "Human truth is self-declared; no independent audit of labels is performed.",
            "Three anchor frames and model guesses do not establish real-world actions.",
            "Scores are non-generalizable without diverse real video coverage.",
            "Unobservable labels are excluded from accuracy and separately counted.",
            "Unknown, missing and invalid predictions are abstentions, not correctness.",
            "Zero eligible phases give null accuracy, not a perfect score.",
            "No video frames, source files, crop images or raw model prompts are retained.",
        ],
    }


def _full_sequence_metrics(phases: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in phases:
        grouped[row["sequenceId"]].append(row)
    reviewed, correct = 0, 0
    for samples in grouped.values():
        if (len(samples) != 2
                or [x["phase"] for x in samples] != list(_PHASES)
                or samples[0]["shotId"] != samples[1]["shotId"]
                or samples[0]["frameIndices"][1] != samples[1]["frameIndices"][0]):
            raise ValueError("aggregate sequence phase anchors are duplicated or misaligned")
        if all(x["humanCategory"] != _UNOBSERVABLE for x in samples):
            reviewed += 1
            correct += all(x["status"] == "correct" for x in samples)
    return {"fullyObservableSequenceCount": reviewed,
            "fullyCorrectSequenceCount": correct,
            "fullSequenceExactAccuracy": _div(correct, reviewed)}


def aggregate_benchmarks(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(reports, list) or not 1 <= len(reports) <= 100:
        raise ValueError("aggregate expects 1..100 bounded benchmark reports")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen = set()
    for report in reports:
        if (not isinstance(report, dict)
                or report.get("schemaVersion") != BENCHMARK_VERSION
                or not _sha(report.get("sourceSha256"))
                or type(report.get("modelTag")) is not str
                or not 1 <= len(report["modelTag"]) <= 120):
            raise ValueError("invalid benchmark report provenance")
        pair = report["modelTag"], report["sourceSha256"]
        if pair in seen:
            raise ValueError("duplicate source/model benchmark must not be double-counted")
        seen.add(pair)
        phase_rows = report.get("phases")
        if not isinstance(phase_rows, list) or len(phase_rows) > 24:
            raise ValueError("invalid bounded benchmark phase rows")
        if (not _integer(report.get("sequenceCount"), low=1, high=12)
                or len(phase_rows) != report["sequenceCount"] * 2):
            raise ValueError("aggregate benchmark sequence and phase counts differ")
        for phase in phase_rows:
            if (not isinstance(phase, dict)
                    or set(phase) != {"sequenceId", "shotId", "phase",
                                      "frameIndices", "humanCategory",
                                      "prediction", "status"}
                    or type(phase.get("sequenceId")) is not str
                    or type(phase.get("shotId")) is not str
                    or phase.get("phase") not in _PHASES
                    or not isinstance(phase.get("frameIndices"), list)
                    or len(phase["frameIndices"]) != 2
                    or any(type(i) is not int or i < 0
                           for i in phase["frameIndices"])
                    or phase["frameIndices"][0] >= phase["frameIndices"][1]
                    or phase.get("humanCategory") not in (_KINDS | {_UNOBSERVABLE})
                    or phase.get("humanCategory") == "unknown"
                    or phase.get("prediction") not in (_KINDS | {_ABSTAIN})
                    or phase.get("prediction") == "unknown"):
                raise ValueError("aggregate benchmark has invalid phase labels or anchors")
        recomputed = {**_score(phase_rows),
                      **_full_sequence_metrics(phase_rows)}
        metrics = report.get("metrics")
        if not isinstance(metrics, dict) or any(
                metrics.get(key) != value for key, value in recomputed.items()):
            raise ValueError("benchmark report metrics disagree with phase-level evidence")
        grouped[report["modelTag"]].append(report)
    models = []
    for model, entries in sorted(grouped.items()):
        rows = [phase for report in entries for phase in report["phases"]]
        models.append({
            "modelTag": model,
            "distinctSourceCount": len(entries),
            "sequenceCount": sum(r["sequenceCount"] for r in entries),
            "metrics": {**_score(rows), **_full_sequence_metrics(rows)},
            "status": "human-declared-sampled-source-evaluation",
        })
    return {
        "schemaVersion": AGGREGATE_VERSION,
        "sourceModelPairCount": len(reports),
        "modelCount": len(models),
        "models": models,
        "evidenceStatus": "aggregated-human-declared-sampled-phase-benchmarks",
        "limitations": [
            "Never pool model accuracy across different model tags.",
            "Reports must be from distinct source/model pairs; one video is not multiple independent videos.",
            "No claims of full video, real-world character identity or gesture accuracy.",
            "Human-review completeness is declared, not independently verified.",
            "An aggregate without diverse real audited video clips is not a general benchmark.",
        ],
    }


def _write_new(path: Path, doc: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError("benchmark output exists; choose a new path")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("benchmark output parent must be a real directory")
    data = (json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode()
    if len(data) > _MAX_BYTES:
        raise ValueError("benchmark result exceeds 8 MiB")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                prefix=".benchmark-", suffix=".tmp", dir=path.parent,
                mode="wb", delete=False) as stream:
            temp = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists() or path.is_symlink():
            raise ValueError("output was created by another writer")
        os.replace(temp, path)
        temp = None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate source-bound visual-change guesses only against reviewed human labels")
    sub = parser.add_subparsers(dest="operation", required=True)
    template = sub.add_parser("template", help="create a pending, never pre-approved label file")
    template.add_argument("--insights", type=Path, required=True)
    template.add_argument("--out", type=Path, required=True)
    evalp = sub.add_parser("evaluate", help="score an approved human phase label file")
    evalp.add_argument("--insights", type=Path, required=True)
    evalp.add_argument("--labels", type=Path, required=True)
    evalp.add_argument("--out", type=Path, required=True)
    aggregate = sub.add_parser("aggregate", help="aggregate independently reviewed per-video benchmarks")
    aggregate.add_argument("reports", type=Path, nargs="+")
    aggregate.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == "aggregate":
            reports = [_load(path)[0] for path in args.reports]
            result = aggregate_benchmarks(reports)
        else:
            insights, source_sha = _load(args.insights)
            if args.operation == "template":
                result = make_label_template(insights, insights_sha=source_sha)
            else:
                labels, human_sha = _load(args.labels)
                result = evaluate_sequence_labels(
                    insights, labels, insights_sha=source_sha,
                    labels_sha=human_sha)
        _write_new(args.out, result)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"three-anchor benchmark failed: {exc}\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
