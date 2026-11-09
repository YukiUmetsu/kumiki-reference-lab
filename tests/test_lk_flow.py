"""Controlled LK refinement QA; never treats 2D motion as camera evidence."""

import importlib.util
import math
import unittest

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows


class LKCliTests(unittest.TestCase):
    def test_lk_flags_are_opt_in(self):
        parser = build_parser()
        self.assertFalse(parser.parse_args(["sparse-flow", "source.mp4"]).lk_refinement)
        self.assertTrue(parser.parse_args([
            "sparse-flow", "source.mp4", "--lk-refinement"
        ]).lk_refinement)
        self.assertTrue(parser.parse_args([
            "analyze", "source.mp4", "--out", "runs", "--sparse-flow",
            "--sparse-lk-refinement"
        ]).sparse_lk_refinement)


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy unavailable")
class LKFlowTests(unittest.TestCase):
    def test_fractional_lk_bidirectional_refines_without_changing_integer_acceptance(self):
        from tests.test_subpixel_flow import SubpixelFlowTests

        before, after, dx, dy = SubpixelFlowTests._fractionally_translated_frames()
        baseline = sparse_patch_flows(before, after, 160, 90, max_points=48)
        refined = sparse_patch_flows(before, after, 160, 90, max_points=48,
                                     lk_refinement=True)
        self.assertEqual(baseline["detectedCorners"], refined["detectedCorners"])
        self.assertEqual(len(baseline["accepted"]), len(refined["accepted"]))
        self.assertEqual([v["x"] for v in baseline["accepted"]],
                         [v["x"] for v in refined["accepted"]])
        candidates = [v for v in refined["accepted"]
                      if v["lkStatus"] == "fractional-lk-bidirectional-candidate"]
        self.assertGreaterEqual(len(candidates), 35)
        self.assertTrue(all(v["lkReverseErrorPixels"] <= 0.75
                            and v["lkPhotometricRmsGray"] >= 0
                            and 1 <= v["lkIterations"] <= 8
                            and abs(v["lkOffsetPixels"]["dx"]) <= 1.25
                            and abs(v["lkOffsetPixels"]["dy"]) <= 1.25
                            for v in candidates))
        original = {(v["x"], v["y"]): v for v in baseline["accepted"]}
        before_error = sum(math.hypot(original[(v["x"], v["y"])]["dx"] - dx,
                                      original[(v["x"], v["y"])]["dy"] - dy)
                           for v in candidates) / len(candidates)
        after_error = sum(math.hypot(v["dx"] - dx, v["dy"] - dy)
                          for v in candidates) / len(candidates)
        self.assertLess(after_error, before_error - 0.12)
        self.assertEqual(refined, sparse_patch_flows(before, after, 160, 90,
                                                     max_points=48, lk_refinement=True))

    def test_fail_closed_and_legacy_compatibility(self):
        from kumiki_reference_lab.analyzers.motion.optical_flow_lk import BoundedLKPair

        flat = bytes([128] * (160 * 90))
        self.assertEqual(sparse_patch_flows(flat, flat, 160, 90,
                                            lk_refinement=True)["accepted"], [])
        pair = BoundedLKPair(flat, flat, 160, 90)
        self.assertEqual(pair.refine(30, 30, 1, 0)["status"], "integer-fallback")
        self.assertIsNone(pair.refine(30, 30, 1, 0)["offsetPixels"])
        self.assertEqual(pair.refine(2, 2, 1, 0)["status"], "integer-fallback")
        with self.assertRaisesRegex(ValueError, "integer"):
            pair.refine(30, 30, 0.5, 0)
        with self.assertRaisesRegex(ValueError, "boolean"):
            sparse_patch_flows(flat, flat, 160, 90, lk_refinement=1)
        with self.assertRaisesRegex(ValueError, "cannot combine"):
            sparse_patch_flows(flat, flat, 160, 90,
                               subpixel_refinement=True, lk_refinement=True)
        with self.assertRaisesRegex(ValueError, "fixed 9-pixel"):
            sparse_patch_flows(flat, flat, 160, 90, patch_size=11,
                               lk_refinement=True)


if __name__ == "__main__":
    unittest.main()
