"""Temporal image-grid support is not a pixel track or an occlusion mask."""

import copy
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from kumiki_reference_lab.analyzers.motion.temporal_support import (
    analyze_dense_temporal_support, analyze_dense_temporal_support_file,
)
from kumiki_reference_lab.cli.app import main


def _report(*, cut: bool = False):
    cells = [(x, y) for y in range(6, 84, 12) for x in range(6, 154, 12)]
    assert len(cells) == 91
    counts = [50, 12, 8, 45, 48]
    rejected = {"low-texture": 0, "out-of-frame": 0,
                "roundtrip-inconsistent": 0, "implausible-displacement": 0,
                "appearance-inconsistent": 0}
    samples = [{"sampleOrdinal": index, "sourcePts": (index + 1) * 100,
                "sourceSeconds": {"numerator": index + 1, "denominator": 10}}
               for index in range(6)]
    pairs = []
    for index, count in enumerate(counts):
        is_cut = cut and index == 2
        count = 0 if is_cut else count
        reject = dict(rejected)
        reject["low-texture"] = 0 if is_cut else 91 - count
        pairs.append({"startPts": samples[index]["sourcePts"],
                      "endPts": samples[index + 1]["sourcePts"],
                      "deltaTimeSeconds": {"numerator": 1, "denominator": 10},
                      "status": "cut-boundary" if is_cut else "flow-observed",
                      "candidateCount": 0 if is_cut else 91,
                      "rejected": reject,
                      "vectors": [{"x": x, "y": y, "dx": 2.0, "dy": 0.0,
                                   "roundtripErrorPixels": 0.1}
                                  for x, y in cells[:count]],
                      "acceptedFraction": round(count / 91, 5) if not is_cut else 0.0})
    return {"schemaVersion": "kumiki.dense-flow.v1", "sourceSha256": "a" * 64,
            "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "scanWindowSeconds": 2,
            "analyzer": {"resolution": {"width": 160, "height": 90},
                         "gridStepPixels": 12},
            "samples": samples, "pairs": pairs,
            "cutCandidatePts": [350] if cut else []}


class DenseTemporalSupportTests(unittest.TestCase):
    def test_drop_and_recovery_are_grid_support_only(self):
        report = analyze_dense_temporal_support(_report())
        self.assertEqual(report["schemaVersion"], "kumiki.dense-temporal-support.v1")
        self.assertFalse(report["sourceVerified"])
        self.assertFalse(report["semanticOcclusionVerified"])
        self.assertFalse(report["semanticIdentityVerified"])
        self.assertFalse(report["calibratedConfidence"])
        pairs = report["pairs"]
        self.assertIsNone(pairs[0]["previousPairComparison"])
        self.assertEqual(pairs[1]["previousPairComparison"]["status"],
                         "support-drop-candidate")
        self.assertEqual(pairs[1]["previousPairComparison"]["fixedGridLost"], 38)
        self.assertEqual(pairs[3]["previousPairComparison"]["status"],
                         "support-rise-candidate")
        self.assertEqual(pairs[3]["previousPairComparison"]["fixedGridGained"], 37)
        self.assertEqual(pairs[3]["startPts"], 400)
        self.assertEqual(pairs[3]["endPts"], 500)
        self.assertEqual(pairs[3]["rejected"]["low-texture"], 46)
        self.assertEqual(report["summary"]["dropCandidates"], 1)
        self.assertEqual(report["summary"]["riseCandidates"], 1)
        self.assertNotIn("cameraVerified", report)
        json.dumps(report, allow_nan=False)

    def test_cut_resets_adjacent_comparison_and_never_bridges(self):
        report = analyze_dense_temporal_support(_report(cut=True))
        self.assertEqual(report["pairs"][2]["status"], "cut-boundary")
        self.assertIsNone(report["pairs"][2]["previousPairComparison"])
        self.assertIsNone(report["pairs"][3]["previousPairComparison"])
        self.assertEqual(report["summary"]["skippedCutBoundaries"], 1)
        self.assertEqual(report["pairs"][4]["previousPairComparison"]["status"],
                         "no-large-aggregate-change")

    def test_cli_schema_immutable_artifact_and_malformed_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "dense-flow.json"
            path.write_text(json.dumps(_report()), encoding="utf-8")
            out = root / "out"
            self.assertEqual(main(["dense-temporal-support", str(path),
                                   "--out", str(out)]), 0)
            destination = out / "dense-temporal-support.json"
            original = json.loads(destination.read_text())
            self.assertEqual(analyze_dense_temporal_support_file(path), original)
            self.assertEqual(main(["dense-temporal-support", str(path),
                                   "--out", str(out)]), 0)
            if importlib.util.find_spec("jsonschema"):
                from jsonschema import Draft202012Validator
                schema = json.loads((Path(__file__).resolve().parents[1] /
                                     "schemas/v1/dense-temporal-support.schema.json").read_text())
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(original)

            altered = _report()
            altered["pairs"][0]["rejected"]["low-texture"] -= 1
            path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaises(ValueError):
                analyze_dense_temporal_support_file(path)
            self.assertEqual(json.loads(destination.read_text()), original)
            altered = copy.deepcopy(_report())
            altered["pairs"][0]["vectors"][0]["dx"] = 2.1
            path.write_text(json.dumps(altered), encoding="utf-8")
            self.assertNotEqual(analyze_dense_temporal_support_file(path), original)
            with redirect_stderr(io.StringIO()) as error:
                self.assertEqual(main(["dense-temporal-support", str(path),
                                       "--out", str(out)]), 2)
            self.assertIn("different content", error.getvalue())
            self.assertEqual(json.loads(destination.read_text()), original)


if __name__ == "__main__":
    unittest.main()
