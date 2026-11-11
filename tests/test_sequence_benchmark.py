"""Truthfully score three-anchor VLM sequence guesses only after human review."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.pipeline.sequence_benchmark import (
    AGGREGATE_VERSION, BENCHMARK_VERSION, LABEL_VERSION,
    _load, aggregate_benchmarks, evaluate_sequence_labels,
    main, make_label_template,
)

SHA = "a" * 64


def phase(name: str, frame_pair: list[int], category: str = "unknown",
          status: str = "unverified-two-frame-phase-hypothesis") -> dict:
    return {"phase": name, "frameIndices": frame_pair,
            "categoryHypothesis": category, "status": status,
            "visibleEvidenceHypothesis": "human review pending"}


def sequence(id: str, frames: list[int], *, first: str = "unknown",
             second: str = "unknown", partial: bool = False) -> dict:
    all_phases = [
        phase("first-to-middle", frames[:2], first),
        phase("middle-to-last", frames[1:], second),
    ]
    return {
        "sequenceId": id, "shotId": "shot-0001",
        "subjectIds": ["roi-a", "roi-b"], "frameIndices": frames,
        "sourceDecodedSeconds": [f / 10 for f in frames],
        "measuredEventTypes": ["screen-centers-closer"],
        "phaseObservations": all_phases[:1] if partial else all_phases,
        "sequencePatternHypothesis": "insufficient-consistent-visual-evidence",
        "status": "unverified-short-sequence-not-semantic-action",
    }


def document(*, source: str = SHA, model: str = "small-local-q4") -> dict:
    rows = [
        sequence("sequence-aaaaaaaaaaaaaaaa", [0, 5, 11],
                 first="apparent-region-translation", second="apparent-turn"),
        sequence("sequence-bbbbbbbbbbbbbbbb", [12, 17, 23],
                 first="unknown", partial=True),
    ]
    return {
        "schemaVersion": "kumiki.online-cinematic-insights.v1",
        "source": {"sourceSha256": source, "frameCount": 32},
        "shotIntelligence": {
            "sourceSha256": source, "frameCount": 32,
            "shots": [{"shotId": "shot-0001",
                       "startFrameIndex": 0,
                       "endFrameIndexExclusive": 32}],
        },
        "threeAnchorSequenceReview": {
            "schemaVersion": "kumiki.online-three-anchor-sequence-review.v1",
            "sourceSha256": source, "frameCount": 32,
            "modelTag": model, "sequences": rows,
        },
    }


class SequenceBenchmarkTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.insights = document()
        self.insights_path = self.root / "test.insights.json"
        self.insights_path.write_text(json.dumps(self.insights))
        self.insights_sha = _load(self.insights_path)[1]
        self.labels = make_label_template(
            self.insights, insights_sha=self.insights_sha)

    def review(self):
        self.labels["reviewer"] = {
            "kind": "human", "id": "test-human-001"}
        self.labels["coverageDeclaration"] = (
            "all-listed-source-frame-phases-human-reviewed")
        self.labels["sequences"][0]["phases"][0]["humanCategory"] = (
            "apparent-region-translation")
        self.labels["sequences"][0]["phases"][1]["humanCategory"] = (
            "no-clear-change")
        self.labels["sequences"][1]["phases"][0]["humanCategory"] = (
            "apparent-relative-position-change")
        self.labels["sequences"][1]["phases"][1]["humanCategory"] = (
            "not-observable")
        return self.labels

    def evaluate(self):
        return evaluate_sequence_labels(
            self.insights, self.labels,
            insights_sha=self.insights_sha,
            labels_sha="e" * 64)

    def test_pending_template_never_claims_reviewed_ground_truth(self):
        self.assertEqual(self.labels["schemaVersion"], LABEL_VERSION)
        self.assertEqual(self.labels["coverageDeclaration"], "pending-review")
        self.assertEqual(self.labels["reviewer"]["id"], "unassigned")
        self.assertEqual(len(self.labels["sequences"]), 2)
        self.assertTrue(all(
            p["humanCategory"] is None
            for item in self.labels["sequences"]
            for p in item["phases"]))
        with self.assertRaisesRegex(ValueError, "human labels incomplete"):
            self.evaluate()

    def test_measures_correct_error_abstention_and_unobservable_separately(self):
        self.review()
        result = self.evaluate()
        self.assertEqual(result["schemaVersion"], BENCHMARK_VERSION)
        self.assertEqual(result["sourceSha256"], SHA)
        self.assertEqual(result["modelTag"], "small-local-q4")
        m = result["metrics"]
        self.assertEqual(m["humanLabeledPhaseCount"], 4)
        self.assertEqual(m["observablePhaseCount"], 3)
        self.assertEqual(m["humanUnobservablePhaseCount"], 1)
        self.assertEqual(m["attemptedPhaseCount"], 2)
        self.assertEqual(m["correctPhaseCount"], 1)
        self.assertEqual(m["incorrectPhaseCount"], 1)
        self.assertEqual(m["abstainedPhaseCount"], 1)
        self.assertEqual(m["accuracyOnAttempts"], .5)
        self.assertEqual(m["correctFractionOfObservable"], .333333)
        self.assertEqual(m["coverage"], .666667)
        self.assertEqual(m["abstentionRateOnObservable"], .333333)
        self.assertEqual(m["errorRateOnAttempts"], .5)
        self.assertEqual(m["fullyObservableSequenceCount"], 1)
        self.assertEqual(m["fullyCorrectSequenceCount"], 0)
        self.assertEqual(m["fullSequenceExactAccuracy"], 0.)
        self.assertIn(
            {"human": "no-clear-change", "predicted": "apparent-turn", "count": 1},
            m["confusion"])
        self.assertIn(
            {"human": "apparent-relative-position-change",
             "predicted": "abstain", "count": 1},
            m["confusion"])
        self.assertEqual(result["phases"][-1]["status"],
                         "human-unobservable-excluded")
        self.assertIn("not-independently", result["evidenceStatus"])
        text = json.dumps(result, allow_nan=False)
        self.assertNotIn("data:image", text)
        self.assertNotIn("png", text.lower())

    def test_zero_observable_phases_is_null_not_perfect(self):
        self.review()
        for row in self.labels["sequences"]:
            for phase in row["phases"]:
                phase["humanCategory"] = "not-observable"
        report = self.evaluate()
        m = report["metrics"]
        self.assertEqual(m["humanUnobservablePhaseCount"], 4)
        self.assertEqual(m["observablePhaseCount"], 0)
        self.assertIsNone(m["coverage"])
        self.assertIsNone(m["accuracyOnAttempts"])
        self.assertIsNone(m["correctFractionOfObservable"])
        self.assertIsNone(m["fullSequenceExactAccuracy"])

    def test_no_approval_without_complete_human_labels(self):
        self.review()
        self.labels["sequences"][0]["phases"][0]["humanCategory"] = None
        with self.assertRaisesRegex(ValueError, "human phase"):
            self.evaluate()
        self.review()
        self.labels["reviewer"]["kind"] = "model"
        with self.assertRaisesRegex(ValueError, "human reviewer"):
            self.evaluate()
        self.review()
        self.labels["sequences"][0]["phases"][0]["humanCategory"] = "unknown"
        with self.assertRaisesRegex(ValueError, "human phase"):
            self.evaluate()

    def test_stale_report_sha_and_modified_source_anchors_rejected(self):
        self.review()
        self.labels["insightsFileSha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "stale"):
            self.evaluate()
        self.review()
        self.labels["insightsFileSha256"] = self.insights_sha
        self.labels["sequences"][0]["frameIndices"] = [0, 6, 11]
        with self.assertRaisesRegex(ValueError, "modified or reordered"):
            self.evaluate()
        self.review()
        self.labels["sequences"][0]["frameIndices"] = [0, 5, 11]
        self.insights["threeAnchorSequenceReview"]["sourceSha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.evaluate()

    def test_unsupported_prediction_taxonomy_and_source_rejected(self):
        self.review()
        self.insights["threeAnchorSequenceReview"]["sequences"][0][
            "phaseObservations"][0]["categoryHypothesis"] = "touching"
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.evaluate()
        self.insights = document()
        self.insights["threeAnchorSequenceReview"]["sequences"][0][
            "frameIndices"] = [0, 5, 60]
        with self.assertRaisesRegex(ValueError, "source-bound"):
            self.evaluate()
        self.insights = document()
        self.insights["threeAnchorSequenceReview"]["sequences"][0][
            "phaseObservations"][1]["frameIndices"] = [0, 11]
        with self.assertRaisesRegex(ValueError, "misaligned"):
            self.evaluate()

    def test_aggregate_avoids_duplicate_videos_and_different_model_pooling(self):
        self.review()
        a = self.evaluate()
        b = copy.deepcopy(a)
        b["sourceSha256"] = "b" * 64
        c = copy.deepcopy(a)
        c["modelTag"] = "different-mini"
        result = aggregate_benchmarks([a, b, c])
        self.assertEqual(result["schemaVersion"], AGGREGATE_VERSION)
        self.assertEqual(result["modelCount"], 2)
        self.assertEqual(result["sourceModelPairCount"], 3)
        models = {m["modelTag"]: m for m in result["models"]}
        self.assertEqual(models["small-local-q4"]["distinctSourceCount"], 2)
        self.assertEqual(models["small-local-q4"]["metrics"][
            "correctPhaseCount"], 2)
        self.assertEqual(models["different-mini"]["distinctSourceCount"], 1)
        with self.assertRaisesRegex(ValueError, "duplicate source/model"):
            aggregate_benchmarks([a, copy.deepcopy(a)])
        altered = copy.deepcopy(a)
        altered["metrics"]["correctPhaseCount"] = 99
        with self.assertRaisesRegex(ValueError, "metrics disagree"):
            aggregate_benchmarks([altered])

    def test_no_label_files_read_or_written_outside_explicit_local_paths(self):
        self.review()
        self.insights_path.write_text(json.dumps(self.insights))
        template_path = self.root / "pending-labels.json"
        self.assertEqual(
            main(["template", "--insights", str(self.insights_path),
                  "--out", str(template_path)]), 0)
        self.assertEqual(
            json.loads(template_path.read_text())["coverageDeclaration"],
            "pending-review")
        with self.assertRaises(SystemExit):
            main(["template", "--insights", str(self.insights_path),
                  "--out", str(template_path)])
        labels_path = self.root / "human-labels.json"
        labels_path.write_text(json.dumps(self.labels))
        output = self.root / "benchmark.json"
        self.assertEqual(
            main(["evaluate", "--insights", str(self.insights_path),
                  "--labels", str(labels_path), "--out", str(output)]), 0)
        self.assertEqual(json.loads(output.read_text())["metrics"][
            "correctPhaseCount"], 1)
        aggregate_path = self.root / "aggregate.json"
        self.assertEqual(
            main(["aggregate", str(output), "--out",
                  str(aggregate_path)]), 0)
        self.assertEqual(
            json.loads(aggregate_path.read_text())["modelCount"], 1)

    def test_strict_json_and_symlink_rejected(self):
        duplicate = self.root / "duplicate.json"
        duplicate.write_text('{"schemaVersion":1,"schemaVersion":2}')
        with self.assertRaisesRegex(ValueError, "strict JSON"):
            _load(duplicate)
        linked = self.root / "linked.json"
        linked.symlink_to(self.insights_path)
        with self.assertRaisesRegex(ValueError, "bounded regular"):
            _load(linked)


if __name__ == "__main__":
    unittest.main()
