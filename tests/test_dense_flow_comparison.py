"""Reference/render flow differences are image-plane evidence, not camera recovery."""

import copy
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from kumiki_reference_lab.analyzers.comparison.dense_flow import (
    compare_dense_flow, compare_dense_flow_files,
)
from kumiki_reference_lab.cli.app import main
from tests.test_dense_temporal_support import _report


def _candidate(reference, *, first_pts=1100, interval_pts=100):
    candidate = copy.deepcopy(reference)
    candidate["sourceSha256"] = "b" * 64
    for index, sample in enumerate(candidate["samples"]):
        sample["sourcePts"] = first_pts + index * interval_pts
        sample["sourceSeconds"] = {"numerator": sample["sourcePts"],
                                   "denominator": 1000}
    for index, pair in enumerate(candidate["pairs"]):
        pair["startPts"] = candidate["samples"][index]["sourcePts"]
        pair["endPts"] = candidate["samples"][index + 1]["sourcePts"]
        pair["deltaTimeSeconds"] = {"numerator": interval_pts, "denominator": 1000}
    return candidate


class DenseFlowComparisonTests(unittest.TestCase):
    def test_measures_shared_grid_velocity_and_missing_support(self):
        ref = _report()
        candidate = _candidate(ref)
        for pair in candidate["pairs"]:
            for vector in pair["vectors"]:
                vector["dx"] = 2.2
        first = candidate["pairs"][0]
        first["vectors"].pop()
        first["rejected"]["low-texture"] += 1
        first["acceptedFraction"] = round(len(first["vectors"]) / 91, 5)
        result = compare_dense_flow(ref, candidate,
                                    reference_anchor_ms=0, candidate_anchor_ms=1000,
                                    tolerance_ms=0)
        self.assertEqual(result["schemaVersion"], "kumiki.dense-flow-comparison.v1")
        self.assertEqual(result["comparison"]["matchedPairCount"], 5)
        self.assertEqual(result["comparison"]["unmatchedReferencePairCount"], 0)
        self.assertFalse(result["comparison"]["sourceVerified"])
        self.assertFalse(result["comparison"]["cameraMotionVerified"])
        self.assertEqual(result["pairs"][0]["sharedCellCount"], 49)
        self.assertEqual(result["pairs"][0]["referenceOnlyCellCount"], 1)
        self.assertEqual(result["pairs"][0]["candidateOnlyCellCount"], 0)
        self.assertAlmostEqual(result["pairs"][0]["supportJaccardFraction"], 0.98)
        self.assertAlmostEqual(result["pairs"][0]["meanGridVelocityDifferencePxPerSecond"], 2)
        self.assertEqual(result["pairs"][0]["referenceStartPts"], 100)
        self.assertEqual(result["pairs"][0]["candidateStartPts"], 1100)
        self.assertEqual(result["summary"]["durationIncomparableCount"], 0)
        self.assertGreater(result["summary"]["sharedCellCount"], 49)
        json.dumps(result, allow_nan=False)

    def test_two_to_one_clock_scale_normalizes_velocity(self):
        ref = _report()
        candidate = _candidate(ref, first_pts=1050, interval_pts=50)
        result = compare_dense_flow(ref, candidate,
                                    reference_anchor_ms=0, candidate_anchor_ms=1000,
                                    time_scale="2", tolerance_ms=0)
        self.assertEqual(result["comparison"]["matchedPairCount"], 5)
        self.assertAlmostEqual(result["summary"]["meanGridVelocityDifferencePxPerSecond"],
                               0, delta=0.00001)
        self.assertEqual(result["alignment"]["scale"], {"numerator": 2,
                                                        "denominator": 1})

    def test_unobserved_cells_and_cuts_do_not_produce_perfect_scores(self):
        ref = _report()
        candidate = _candidate(ref)
        candidate["pairs"][0]["vectors"] = []
        candidate["pairs"][0]["rejected"]["low-texture"] = 91
        candidate["pairs"][0]["acceptedFraction"] = 0.0
        candidate["pairs"][0]["status"] = "unobservable"
        result = compare_dense_flow(ref, candidate, reference_anchor_ms=0,
                                    candidate_anchor_ms=1000, tolerance_ms=0)
        self.assertEqual(result["pairs"][0]["status"], "no-shared-cells")
        self.assertIsNone(result["pairs"][0]["meanGridVelocityDifferencePxPerSecond"])
        self.assertEqual(result["pairs"][0]["supportJaccardFraction"], 0)

        candidate["cutCandidatePts"] = [1150]
        candidate["pairs"][0].update({
            "status": "cut-boundary", "candidateCount": 0,
            "rejected": {key: 0 for key in candidate["pairs"][0]["rejected"]},
        })
        cut = compare_dense_flow(ref, candidate, reference_anchor_ms=0,
                                 candidate_anchor_ms=1000, tolerance_ms=0)
        self.assertEqual(cut["comparison"]["matchedPairCount"], 4)
        self.assertEqual(cut["comparison"]["unmatchedReferencePairCount"], 1)

    def test_incompatible_grid_and_unaligned_pairs_fail_or_abstain(self):
        ref = _report()
        candidate = _candidate(ref)
        candidate["analyzer"]["gridStepPixels"] = 8
        with self.assertRaises(ValueError):
            compare_dense_flow(ref, candidate, reference_anchor_ms=0,
                               candidate_anchor_ms=1000)
        candidate = _candidate(ref)
        result = compare_dense_flow(ref, candidate, reference_anchor_ms=0,
                                    candidate_anchor_ms=4000, tolerance_ms=0)
        self.assertEqual(result["comparison"]["matchedPairCount"], 0)
        self.assertIsNone(result["summary"]["meanGridVelocityDifferencePxPerSecond"])

    def test_midpoint_match_must_also_have_actual_time_overlap(self):
        ref = _report()
        ref["samples"], ref["pairs"] = ref["samples"][:2], ref["pairs"][:1]
        candidate = _candidate(ref, first_pts=1210)
        result = compare_dense_flow(ref, candidate, reference_anchor_ms=0,
                                    candidate_anchor_ms=1000, tolerance_ms=150)
        self.assertEqual(result["comparison"]["matchedPairCount"], 1)
        self.assertEqual(result["pairs"][0]["status"], "time-disjoint")
        self.assertIsNone(result["pairs"][0]["meanGridVelocityDifferencePxPerSecond"])
        self.assertEqual(result["summary"]["timeDisjointCount"], 1)

    def test_tiny_time_overlap_cannot_be_scored_as_motion_match(self):
        ref = _report()
        ref["samples"], ref["pairs"] = ref["samples"][:2], ref["pairs"][:1]
        candidate = _candidate(ref, first_pts=1190)
        result = compare_dense_flow(ref, candidate, reference_anchor_ms=0,
                                    candidate_anchor_ms=1000, tolerance_ms=150)
        self.assertEqual(result["comparison"]["matchedPairCount"], 1)
        self.assertEqual(result["pairs"][0]["status"], "insufficient-time-overlap")
        self.assertEqual(result["summary"]["insufficientOverlapCount"], 1)
        self.assertIsNone(result["pairs"][0]["meanGridVelocityDifferencePxPerSecond"])

    def test_large_duration_mismatch_abstains_even_with_time_overlap(self):
        ref = _report()
        ref["samples"], ref["pairs"] = ref["samples"][:2], ref["pairs"][:1]
        candidate = _candidate(ref, first_pts=1140, interval_pts=20)
        result = compare_dense_flow(ref, candidate, reference_anchor_ms=0,
                                    candidate_anchor_ms=1000, tolerance_ms=0)
        self.assertEqual(result["comparison"]["matchedPairCount"], 1)
        self.assertEqual(result["pairs"][0]["status"], "duration-incomparable")
        self.assertEqual(result["summary"]["durationIncomparableCount"], 1)
        self.assertIsNone(result["summary"]["meanGridVelocityDifferencePxPerSecond"])

    def test_malformed_extreme_timebases_fail_with_value_error(self):
        reference = _report()
        for denominator in (10 ** 400,):
            bad = copy.deepcopy(reference)
            bad["sourceTimebase"] = {"numerator": 1, "denominator": denominator}
            for sample in bad["samples"]:
                sample["sourceSeconds"] = {"numerator": sample["sourcePts"],
                                           "denominator": denominator}
            for pair in bad["pairs"]:
                pair["deltaTimeSeconds"] = {"numerator": 100,
                                            "denominator": denominator}
            bad_candidate = copy.deepcopy(bad)
            bad_candidate["sourceSha256"] = "b" * 64
            with self.assertRaisesRegex(ValueError, "duration"):
                compare_dense_flow(bad, bad_candidate,
                                   reference_anchor_ms=0, candidate_anchor_ms=0,
                                   tolerance_ms=0)

    def test_cli_schema_no_overwrite_and_rejects_duplicate_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reference, candidate = _report(), _candidate(_report())
            ref_path, cand_path = root / "reference.json", root / "render.json"
            ref_path.write_text(json.dumps(reference), encoding="utf-8")
            cand_path.write_text(json.dumps(candidate), encoding="utf-8")
            out = root / "output"
            args = ["compare-dense-flow", str(ref_path), str(cand_path),
                    "--reference-anchor-ms", "0", "--candidate-anchor-ms", "1000",
                    "--tolerance-ms", "0", "--out", str(out)]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
            artifact = json.loads((out / "dense-flow-comparison.json").read_text())
            self.assertEqual(artifact, compare_dense_flow_files(
                ref_path, cand_path, reference_anchor_ms=0,
                candidate_anchor_ms=1000, tolerance_ms=0))
            if importlib.util.find_spec("jsonschema"):
                from jsonschema import Draft202012Validator
                schema = json.loads((Path(__file__).resolve().parents[1] /
                                     "schemas/v1/dense-flow-comparison.schema.json").read_text())
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(artifact)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
            candidate["pairs"][0]["vectors"][0]["dx"] = 2.1
            cand_path.write_text(json.dumps(candidate), encoding="utf-8")
            with redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(main(args), 2)
            self.assertIn("different content", errors.getvalue())
            self.assertEqual(json.loads((out / "dense-flow-comparison.json").read_text()),
                             artifact)
            cand_path.write_text(json.dumps(candidate).replace(
                '"sourceSha256":', '"sourceSha256": "duplicate", "sourceSha256":', 1),
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                compare_dense_flow_files(ref_path, cand_path,
                                         reference_anchor_ms=0, candidate_anchor_ms=1000)


if __name__ == "__main__":
    unittest.main()
