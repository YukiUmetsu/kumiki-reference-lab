"""Offline source-bound character box precision/recall against human-supplied labels."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.subject_detection_benchmark import (
    _maximum_cardinality_matches, evaluate_subject_boxes, run_subject_box_benchmark,
    create_subject_box_label_template,
)


def _proposal(box, *, category="animated-character"):
    return {"category": category, "score": .5, "box": box}


def _human(box, *, category="animated-character"):
    return {"category": category, "box": box}


class SubjectDetectionBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "licensed-test.mp4"
        self.source.write_bytes(b"synthetic source bytes with mocked FFprobe")
        self.pred_path = self.root / "predictions.json"
        self.gt_path = self.root / "labels.json"
        self.out = self.root / "benchmark"
        self.pred = {
            "schemaVersion": "kumiki.subject-detections.v1",
            "sourceSha256": "a" * 64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "detector": {"name": "ollama-local-vlm:test-model", "modelSha256": None},
            "cutCandidatePts": [],
            "frames": [
                {"sourcePts": 0, "detections": [
                    _proposal([.1,.1,.2,.4]),
                    _proposal([.6,.1,.2,.4]),
                    _proposal([.4,.7,.2,.2], category="animal"),
                ]},
                {"sourcePts": 1000, "detections": [
                    _proposal([.1,.1,.2,.4]),
                ]},
            ],
        }
        self.gt = {
            "schemaVersion": "kumiki.subject-box-ground-truth.v1",
            "sourceSha256": "a" * 64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "reviewer": {"kind": "human", "id": "human-reviewer-01"},
            "coverageDeclaration": "all-visibly-supported-subjects-on-each-listed-sampled-frame",
            "frames": [
                {"sourcePts": 0, "subjects": [
                    _human([.1,.1,.2,.4]), _human([.6,.1,.2,.4]),
                ]},
                {"sourcePts": 1000, "subjects": [
                    _human([.1,.1,.2,.4]), _human([.6,.1,.2,.4]),
                ]},
            ],
        }
        self.save()

    def save(self):
        self.pred_path.write_text(json.dumps(self.pred))
        self.gt_path.write_text(json.dumps(self.gt))

    def run_mock(self):
        inspected = {
            "source": {"sha256": "a"*64},
            "video": {"streamIndex": 0,
                      "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }
        with patch(
            "kumiki_reference_lab.pipeline.subject_detection_benchmark.inspect_source",
            return_value=inspected,
        ):
            return run_subject_box_benchmark(
                self.source, self.pred_path, self.gt_path, self.out)

    def test_precision_recall_and_class_metrics_from_complete_samples(self):
        path = self.run_mock()
        report = json.loads(path.read_text())
        self.assertEqual(report["sampledFrameCount"], 2)
        self.assertEqual(report["overall"]["truePositives"], 3)
        self.assertEqual(report["overall"]["falsePositives"], 1)
        self.assertEqual(report["overall"]["falseNegatives"], 1)
        self.assertEqual(report["overall"]["precision"], .75)
        self.assertEqual(report["overall"]["recall"], .75)
        self.assertEqual(report["byCategory"][0]["category"], "animal")
        self.assertIsNone(report["byCategory"][0]["recall"])
        self.assertEqual(report["frames"][0]["unmatchedPredictionIndices"], [2])
        self.assertEqual(report["frames"][1]["unmatchedHumanBoxIndices"], [1])
        self.assertEqual(len(report["groundTruthFileSha256"]), 64)
        self.assertIn("not-independently", report["evidenceStatus"])
        with self.assertRaisesRegex(ValueError, "new nonexisting"):
            self.run_mock()

    def test_empty_frames_are_not_perfect_accuracy(self):
        for frame in self.pred["frames"]:
            frame["detections"] = []
        for frame in self.gt["frames"]:
            frame["subjects"] = []
        summary = evaluate_subject_boxes(self.pred, self.gt)
        self.assertEqual(summary["overall"]["truePositives"], 0)
        self.assertIsNone(summary["overall"]["precision"])
        self.assertIsNone(summary["overall"]["recall"])
        self.assertIsNone(summary["overall"]["f1"])

    def test_wrong_class_counts_as_missed_and_false_positive(self):
        self.pred["frames"][0]["detections"] = [
            _proposal([.1,.1,.2,.4], category="person")
        ]
        self.pred["frames"][1]["detections"] = []
        self.gt["frames"][0]["subjects"] = [_human([.1,.1,.2,.4])]
        self.gt["frames"][1]["subjects"] = []
        report = evaluate_subject_boxes(self.pred, self.gt)
        self.assertEqual(report["overall"]["truePositives"], 0)
        self.assertEqual(report["overall"]["falsePositives"], 1)
        self.assertEqual(report["overall"]["falseNegatives"], 1)
        self.assertEqual(report["overall"]["f1"], 0)

    def test_bipartite_matching_can_reassign_ambiguous_first_choice(self):
        proposals = [
            _proposal([.20,.2,.4,.4]), _proposal([.08,.2,.4,.4])
        ]
        annotations = [
            _human([.10,.2,.4,.4]), _human([.30,.2,.4,.4])
        ]
        matches = _maximum_cardinality_matches(proposals, annotations, .5)
        self.assertEqual(len(matches), 2)
        self.assertEqual({j for _, j, _ in matches}, {0, 1})

    def test_rejects_missing_pts_and_unassigned_human_labels(self):
        mutations = [
            lambda x: x["frames"][1].update(sourcePts=2000),
            lambda x: x["frames"].pop(),
            lambda x: x["reviewer"].update(id="unassigned"),
            lambda x: x["reviewer"].update(kind="model"),
            lambda x: x.update(sourceSha256="f"*64),
            lambda x: x.update(coverageDeclaration="some-boxes"),
            lambda x: x["frames"][0]["subjects"].append(
                copy.deepcopy(x["frames"][0]["subjects"][0])),
            lambda x: x["frames"][0]["subjects"][0].update(category="ethnicity"),
            lambda x: x["frames"][0]["subjects"][0].update(box=[.95, .1, .2, .5]),
        ]
        for mutation in mutations:
            gt = copy.deepcopy(self.gt)
            mutation(gt)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                evaluate_subject_boxes(self.pred, gt)

    def test_rejects_unknown_source_before_writing(self):
        self.gt["sourceSha256"] = "b"*64
        self.save()
        with self.assertRaisesRegex(ValueError, "disagree"):
            self.run_mock()
        self.assertFalse(self.out.exists())

    def test_invalid_threshold_is_refused(self):
        for threshold in (True, float("nan"), .1, 1.1):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                evaluate_subject_boxes(self.pred, self.gt, min_iou=threshold)

    def test_label_template_is_explicitly_pending_until_human_approval(self):
        path = self.root / "pending-annotations.json"
        create_subject_box_label_template(self.pred_path, path)
        data = json.loads(path.read_text())
        self.assertEqual(data["coverageDeclaration"], "pending-review")
        self.assertEqual(data["reviewer"]["id"], "unassigned")
        self.assertEqual([f["sourcePts"] for f in data["frames"]], [0, 1000])
        self.assertTrue(all(f["subjects"] == [] for f in data["frames"]))
        with self.assertRaisesRegex(ValueError, "declare complete"):
            evaluate_subject_boxes(self.pred, data)
        with self.assertRaisesRegex(ValueError, "new file"):
            create_subject_box_label_template(self.pred_path, path)

    def test_cli(self):
        args = build_parser().parse_args([
            "evaluate-character-detections", "clip.mp4", "detections.json",
            "human-labels.json", "--min-iou", "0.7", "--out", "results"])
        self.assertEqual(args.command, "evaluate-character-detections")
        self.assertEqual(args.min_iou, .7)
        self.assertEqual(args.ground_truth, Path("human-labels.json"))
        template = build_parser().parse_args([
            "character-labels-template", "detections.json",
            "--out", "pending-labels.json"])
        self.assertEqual(template.command, "character-labels-template")


if __name__ == "__main__":
    unittest.main()
