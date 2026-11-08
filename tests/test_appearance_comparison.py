import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.comparison.appearance import compare_appearance
from kumiki_reference_lab.cli.app import main


def _appearance(luma: float) -> dict:
    return {"meanLumaProxy": luma, "meanRgb": [luma] * 3,
            "meanSaturation": 0.0, "brightPixelFraction": float(luma >= .85),
            "chromaticPixelFraction": 0.0, "hueHistogram12": [0.0] * 12,
            "spatialGrid3x3": [{"row": i // 3, "column": i % 3,
                                "meanLumaProxy": luma} for i in range(9)]}


def _report(pts: list[int], values: list[float], sha: str) -> dict:
    return {"schemaVersion": "kumiki.appearance.v1",
            "sourceSha256": sha * 64,
            "sourceTimebase": {"numerator": 1, "denominator": 10},
            "samples": [{"sourcePts": p, "sourceSeconds":
                         {"numerator": p, "denominator": 10},
                         "appearance": _appearance(v)}
                        for p, v in zip(pts, values, strict=True)]}


class AppearanceComparisonTests(unittest.TestCase):
    def _save(self, root: Path, ref: dict, candidate: dict) -> tuple[Path, Path]:
        a, b = root / "reference.json", root / "candidate.json"
        a.write_text(json.dumps(ref), encoding="utf-8")
        b.write_text(json.dumps(candidate), encoding="utf-8")
        return a, b

    def test_identical_observations_have_zero_descriptive_error_not_quality_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            ref, candidate = self._save(Path(directory),
                                        _report([0, 10, 20], [.1, .5, .9], "a"),
                                        _report([0, 10, 20], [.1, .5, .9], "b"))
            result = compare_appearance(ref, candidate, reference_anchor_ms=0,
                                        candidate_anchor_ms=0)
            self.assertEqual(result["comparison"]["matchedCount"], 3)
            self.assertEqual(result["summary"]["meanAbsoluteLumaProxyDelta"], 0)
            self.assertEqual(result["summary"]["meanRgbDistance"], 0)
            self.assertEqual(result["comparison"]["qualityVerdict"], "not-performed")
            self.assertTrue(result["alignment"]["oneToOne"])
            self.assertEqual(len(result["reference"]["reportSha256"]), 64)

    def test_declared_offset_and_speed_map_different_source_clocks(self):
        with tempfile.TemporaryDirectory() as directory:
            ref, candidate = self._save(Path(directory),
                                        _report([0, 10, 20], [.1, .5, .9], "a"),
                                        _report([10, 15, 20], [.1, .5, .9], "b"))
            result = compare_appearance(ref, candidate, reference_anchor_ms=0,
                                        candidate_anchor_ms=1000, time_scale="2")
            self.assertEqual(result["comparison"]["matchedCount"], 3)
            self.assertEqual(result["alignment"]["scale"],
                             {"numerator": 2, "denominator": 1})
            self.assertEqual([p["candidatePts"] for p in result["pairs"]], [10, 15, 20])

    def test_nonoverlap_emits_no_grade_or_fabricated_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            ref, candidate = self._save(Path(directory),
                                        _report([0, 10, 20], [.1, .5, .9], "a"),
                                        _report([50, 60, 70], [.1, .5, .9], "b"))
            result = compare_appearance(ref, candidate, reference_anchor_ms=0,
                                        candidate_anchor_ms=0, tolerance_ms=100)
            self.assertEqual(result["comparison"]["status"], "no-aligned-pairs")
            self.assertEqual(result["pairs"], [])
            self.assertIsNone(result["summary"])

    def test_one_to_one_matching_never_reuses_reference_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            ref, candidate = self._save(Path(directory),
                                        _report([0, 10, 20], [.1, .5, .9], "a"),
                                        _report([0, 1, 20], [.1, .1, .9], "b"))
            result = compare_appearance(ref, candidate, reference_anchor_ms=0,
                                        candidate_anchor_ms=0, tolerance_ms=150)
            self.assertEqual(result["comparison"]["matchedCount"], 2)
            self.assertEqual(len({p["referencePts"] for p in result["pairs"]}), 2)
            self.assertEqual(result["comparison"]["unmatchedCandidateCount"], 1)

    def test_alignment_maximizes_matched_frames_before_minimizing_time_error(self):
        # Greedy nearest-neighbor would use candidate PTS=2 for reference 0
        # and leave candidate -3 unmatched, despite a valid three-frame pairing.
        with tempfile.TemporaryDirectory() as directory:
            ref, candidate = self._save(Path(directory),
                                        _report([0, 6, 20], [.1, .5, .9], "a"),
                                        _report([-3, 2, 20], [.1, .5, .9], "b"))
            result = compare_appearance(ref, candidate, reference_anchor_ms=0,
                                        candidate_anchor_ms=0, tolerance_ms=400)
            self.assertEqual(result["comparison"]["matchedCount"], 3)
            self.assertEqual([(p["candidatePts"], p["referencePts"])
                              for p in result["pairs"]], [(-3, 0), (2, 6), (20, 20)])

    def test_malformed_timestamp_and_out_of_range_appearance_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = _report([0, 10, 20], [.1, .5, .9], "a")
            good = _report([0, 10, 20], [.1, .5, .9], "b")
            bad["samples"][1]["sourceSeconds"] = {"numerator": 99, "denominator": 10}
            ref, candidate = self._save(Path(directory), bad, good)
            with self.assertRaisesRegex(ValueError, "timestamps disagree"):
                compare_appearance(ref, candidate, reference_anchor_ms=0,
                                   candidate_anchor_ms=0)
            bad["samples"][1]["sourceSeconds"] = {"numerator": 10, "denominator": 10}
            bad["samples"][1]["appearance"]["meanRgb"][0] = 12.0
            ref, candidate = self._save(Path(directory), bad, good)
            with self.assertRaisesRegex(ValueError, "normalized quantities"):
                compare_appearance(ref, candidate, reference_anchor_ms=0,
                                   candidate_anchor_ms=0)

    def test_cli_requires_anchors_and_writes_idempotent_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ref, candidate = self._save(root,
                                        _report([0, 10], [.3, .4], "a"),
                                        _report([0, 10], [.3, .4], "b"))
            argv = ["compare-appearance", str(ref), str(candidate),
                    "--reference-anchor-ms", "0", "--candidate-anchor-ms", "0",
                    "--out", str(root / "results")]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv), 0)
                self.assertEqual(main(argv), 0)
            self.assertTrue((root / "results/appearance-comparison.json").is_file())


if __name__ == "__main__":
    unittest.main()
