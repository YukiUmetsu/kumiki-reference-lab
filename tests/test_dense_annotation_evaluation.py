"""Declared image-grid annotations may measure errors, not certify camera truth."""

import copy
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from kumiki_reference_lab.analyzers.motion.annotation_evaluation import (
    evaluate_dense_flow_annotations, evaluate_dense_flow_annotations_files,
)
from kumiki_reference_lab.cli.app import main
from tests.test_dense_temporal_support import _report


def _labels(report):
    return {
        "schemaVersion": "kumiki.dense-flow-annotations.v1",
        "sourceSha256": report["sourceSha256"],
        "sourceStreamIndex": report["sourceStreamIndex"],
        "sourceTimebase": report["sourceTimebase"],
        "analysisResolution": report["analyzer"]["resolution"],
        "gridStepPixels": report["analyzer"]["gridStepPixels"],
        "provenance": {"kind": "independently-generated", "reviewStatus": "unverified"},
        "pairLabels": [
            {"startPts": 100, "endPts": 200, "points": [
                {"x": 6, "y": 6, "dx": 2.0, "dy": 0.0},
                {"x": 18, "y": 6, "dx": 3.0, "dy": 0.0},
                {"x": 150, "y": 78, "dx": 2.0, "dy": 0.0},
            ]},
            {"startPts": 200, "endPts": 300, "points": [
                {"x": 6, "y": 6, "dx": 4.0, "dy": 0.0},
            ]},
        ],
    }


class DenseAnnotationEvaluationTests(unittest.TestCase):
    def test_measures_errors_and_coverage_without_rating_missing_as_zero(self):
        report = _report()
        result = evaluate_dense_flow_annotations(report, _labels(report))
        self.assertEqual(result["schemaVersion"], "kumiki.dense-flow-annotation-evaluation.v1")
        self.assertFalse(result["sourceVerified"])
        self.assertFalse(result["annotationsIndependentlyVerified"])
        self.assertFalse(result["physicalCameraVerified"])
        self.assertEqual(result["qualityVerdict"], "not-performed")
        self.assertEqual(result["summary"]["labeledCount"], 4)
        self.assertEqual(result["summary"]["observedCount"], 3)
        self.assertEqual(result["summary"]["missingCount"], 1)
        self.assertEqual(result["summary"]["coverageFraction"], 0.75)
        self.assertAlmostEqual(result["summary"]["meanEndpointErrorPixels"], 1.0)
        self.assertEqual(result["pairs"][0]["missingCount"], 1)
        self.assertEqual(result["pairs"][0]["points"][2]["status"], "not-observed")
        self.assertIsNone(result["pairs"][0]["points"][2]["endpointErrorPixels"])
        self.assertEqual(result["pairs"][1]["startPts"], 200)
        self.assertEqual(result["pairs"][1]["endPts"], 300)
        json.dumps(result, allow_nan=False)

    def test_rejects_wrong_provenance_timebase_grid_pts_and_duplicate_points(self):
        report = _report()
        mutations = [
            lambda x: x.update({"sourceSha256": "b" * 64}),
            lambda x: x.update({"sourceTimebase": {"numerator": 1, "denominator": 50}}),
            lambda x: x.update({"gridStepPixels": 8}),
            lambda x: x["pairLabels"][0].update({"endPts": 201}),
            lambda x: x["pairLabels"][0]["points"].append(
                copy.deepcopy(x["pairLabels"][0]["points"][0])),
            lambda x: x["pairLabels"][0]["points"][0].update({"x": 7}),
            lambda x: x["pairLabels"][0]["points"][0].update({"dx": float("nan")}),
            lambda x: x["provenance"].update({"reviewStatus": "verified"}),
        ]
        for mutate in mutations:
            labels = _labels(report)
            mutate(labels)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                evaluate_dense_flow_annotations(report, labels)

    def test_no_observations_remains_unscored_and_cut_is_not_evaluated(self):
        report = _report(cut=True)
        labels = _labels(report)
        labels["pairLabels"] = [
            {"startPts": 300, "endPts": 400, "points": [{"x": 6, "y": 6,
                                                          "dx": 2, "dy": 0}]},
        ]
        with self.assertRaises(ValueError):
            evaluate_dense_flow_annotations(report, labels)
        labels["pairLabels"][0].update({"startPts": 100, "endPts": 200})
        labels["pairLabels"][0]["points"] = [{"x": 150, "y": 78, "dx": 2, "dy": 0}]
        result = evaluate_dense_flow_annotations(report, labels)
        self.assertEqual(result["summary"]["observedCount"], 0)
        self.assertIsNone(result["summary"]["meanEndpointErrorPixels"])
        self.assertIsNone(result["summary"]["medianEndpointErrorPixels"])

    def test_cli_schemas_idempotency_and_input_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report, labels = _report(), _labels(_report())
            dense_path, label_path = root / "dense-flow.json", root / "labels.json"
            dense_path.write_text(json.dumps(report), encoding="utf-8")
            label_path.write_text(json.dumps(labels), encoding="utf-8")
            target = root / "output"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["evaluate-dense-flow", str(dense_path),
                                       str(label_path), "--out", str(target)]), 0)
            generated = json.loads((target / "dense-flow-evaluation.json").read_text())
            self.assertEqual(generated,
                             evaluate_dense_flow_annotations_files(dense_path, label_path))
            self.assertEqual(len(generated["inputHashes"]["denseFlowCanonicalSha256"]), 64)
            if importlib.util.find_spec("jsonschema"):
                from jsonschema import Draft202012Validator
                schema_root = Path(__file__).resolve().parents[1] / "schemas/v1"
                for name, doc in (("dense-flow-annotations", labels),
                                  ("dense-flow-evaluation", generated)):
                    schema = json.loads((schema_root / (name + ".schema.json")).read_text())
                    Draft202012Validator.check_schema(schema)
                    Draft202012Validator(schema).validate(doc)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["evaluate-dense-flow", str(dense_path),
                                       str(label_path), "--out", str(target)]), 0)
            labels["pairLabels"][0]["points"][0]["dx"] = 1.9
            label_path.write_text(json.dumps(labels), encoding="utf-8")
            with redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(main(["evaluate-dense-flow", str(dense_path),
                                       str(label_path), "--out", str(target)]), 2)
            self.assertIn("different content", errors.getvalue())
            self.assertEqual(json.loads((target / "dense-flow-evaluation.json").read_text()),
                             generated)

            alias = root / "labels-symlink.json"
            alias.symlink_to(label_path)
            with self.assertRaisesRegex(ValueError, "symbolic"):
                evaluate_dense_flow_annotations_files(dense_path, alias)
            duplicate = json.dumps(labels).replace(
                '"schemaVersion":', '"schemaVersion": "duplicate", "schemaVersion":', 1)
            label_path.write_text(duplicate, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                evaluate_dense_flow_annotations_files(dense_path, label_path)


if __name__ == "__main__":
    unittest.main()
