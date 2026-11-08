import importlib.util
import math
import unittest

from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows
from kumiki_reference_lab.analyzers.subjects.template import _parabolic_peak_offset
from kumiki_reference_lab.cli.app import build_parser


class SubpixelPeakTests(unittest.TestCase):
    def test_cli_flags_are_explicit_and_off_by_default(self):
        parser = build_parser()
        self.assertFalse(parser.parse_args(["sparse-flow", "source.mp4"])
                         .subpixel_refinement)
        self.assertTrue(parser.parse_args([
            "sparse-flow", "source.mp4", "--subpixel-refinement"
        ]).subpixel_refinement)
        self.assertTrue(parser.parse_args([
            "analyze", "source.mp4", "--out", "runs", "--sparse-flow",
            "--sparse-subpixel-refinement"
        ]).sparse_subpixel_refinement)
        self.assertTrue(parser.parse_args([
            "sparse-flow", "source.mp4", "--subpixel-refinement",
            "--subpixel-reverse-check"
        ]).subpixel_reverse_check)
        self.assertTrue(parser.parse_args([
            "analyze", "source.mp4", "--out", "runs", "--sparse-flow",
            "--sparse-subpixel-refinement", "--sparse-subpixel-reverse-check"
        ]).sparse_subpixel_reverse_check)

    def test_parabolic_peak_interpolation_abstains_on_invalid_curvature(self):
        self.assertAlmostEqual(_parabolic_peak_offset(0.81, 1.0, 0.94), 0.26)
        self.assertIsNone(_parabolic_peak_offset(0.9, 0.9, 0.9))
        self.assertIsNone(_parabolic_peak_offset(1.1, 1.0, 1.1))
        self.assertIsNone(_parabolic_peak_offset(float("nan"), 1.0, 0.8))
        self.assertIsNone(_parabolic_peak_offset(1.9, 1.0, -1.0))


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy unavailable")
class SubpixelFlowTests(unittest.TestCase):
    @staticmethod
    def _fractionally_translated_frames():
        import numpy as np

        rng = np.random.default_rng(314)
        image = rng.uniform(0, 1, (90, 160))
        for _ in range(2):
            image = (4 * image + np.roll(image, 1, 0) +
                     np.roll(image, -1, 0) + np.roll(image, 1, 1) +
                     np.roll(image, -1, 1)) / 8
        before = np.rint(image * 255).astype(np.uint8)
        dx, dy = 0.45, 0.35
        shifted = ((1 - dx) * (1 - dy) * before.astype(np.float64) +
                   dx * (1 - dy) * np.roll(before, 1, axis=1) +
                   (1 - dx) * dy * np.roll(before, 1, axis=0) +
                   dx * dy * np.roll(np.roll(before, 1, axis=0), 1, axis=1))
        after = np.rint(shifted).astype(np.uint8)
        return before.tobytes(), after.tobytes(), dx, dy

    def test_fractional_peak_opt_in_improves_shift_estimate_without_legacy_change(self):
        before, after, dx, dy = self._fractionally_translated_frames()
        baseline = sparse_patch_flows(before, after, 160, 90, max_points=48)
        self.assertEqual(baseline, sparse_patch_flows(
            before, after, 160, 90, max_points=48, subpixel_refinement=False))
        refined = sparse_patch_flows(
            before, after, 160, 90, max_points=48, subpixel_refinement=True)
        self.assertEqual(baseline["detectedCorners"], refined["detectedCorners"])
        self.assertEqual(len(baseline["accepted"]), len(refined["accepted"]))
        self.assertGreaterEqual(len(refined["accepted"]), 6)
        candidates = [v for v in refined["accepted"]
                      if v["subpixelPeakStatus"] == "candidate-1d-parabola"]
        self.assertGreaterEqual(len(candidates), 5)
        self.assertTrue(all(v["subpixelReverseVerification"] == "integer-peak-only"
                            for v in refined["accepted"]))
        baseline_by_origin = {(v["x"], v["y"]): v for v in baseline["accepted"]}
        integer_errors = [math.hypot(baseline_by_origin[(v["x"], v["y"])]["dx"] - dx,
                                     baseline_by_origin[(v["x"], v["y"])]["dy"] - dy)
                          for v in candidates]
        refined_errors = [math.hypot(v["dx"] - dx, v["dy"] - dy) for v in candidates]
        self.assertLess(sum(refined_errors) / len(refined_errors),
                        sum(integer_errors) / len(integer_errors) - 0.07)

    def test_invalid_opt_in_and_repeated_texture_abstention(self):
        flat = bytes([120] * (160 * 90))
        with self.assertRaisesRegex(ValueError, "subpixel_refinement"):
            sparse_patch_flows(flat, flat, 160, 90, subpixel_refinement=1)
        result = sparse_patch_flows(flat, flat, 160, 90, subpixel_refinement=True)
        self.assertEqual(result["accepted"], [])

    def test_fractional_reverse_check_keeps_only_self_consistent_peak_candidates(self):
        before, after, dx, dy = self._fractionally_translated_frames()
        with self.assertRaisesRegex(ValueError, "requires subpixel_refinement"):
            sparse_patch_flows(before, after, 160, 90, subpixel_reverse_check=True)
        baseline = sparse_patch_flows(before, after, 160, 90, max_points=48)
        checked = sparse_patch_flows(before, after, 160, 90, max_points=48,
                                     subpixel_refinement=True,
                                     subpixel_reverse_check=True)
        self.assertEqual(len(checked["accepted"]), len(baseline["accepted"]))
        candidates = [v for v in checked["accepted"]
                      if v["subpixelReverseVerification"] ==
                      "fractional-bilinear-patch-checked"]
        self.assertGreaterEqual(len(candidates), 5)
        self.assertTrue(all(v["subpixelReverseErrorPixels"] <= 0.75
                            and v["subpixelPeakStatus"] == "candidate-1d-parabola"
                            for v in candidates))
        mean_error = sum(math.hypot(v["dx"] - dx, v["dy"] - dy)
                         for v in candidates) / len(candidates)
        self.assertLess(mean_error, 0.42)


if __name__ == "__main__":
    unittest.main()
