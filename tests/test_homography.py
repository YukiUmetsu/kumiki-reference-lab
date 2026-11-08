import importlib.util
import math
import unittest

from kumiki_reference_lab.analyzers.motion.homography import fit_image_homography
from kumiki_reference_lab.cli.app import build_parser


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy unavailable")
class ImageHomographyTests(unittest.TestCase):
    def test_cli_opt_in_is_off_by_default_and_explicit(self):
        parser = build_parser()
        self.assertFalse(parser.parse_args(["sparse-flow", "source.mp4"])
                         .projective_hypotheses)
        self.assertTrue(parser.parse_args([
            "sparse-flow", "source.mp4", "--projective-hypotheses"
        ]).projective_hypotheses)
        self.assertTrue(parser.parse_args([
            "analyze", "source.mp4", "--out", "runs", "--sparse-flow",
            "--sparse-projective-hypotheses"
        ]).sparse_projective_hypotheses)
        self.assertTrue(parser.parse_args([
            "sparse-flow", "source.mp4", "--tracklet-motion-consistency"
        ]).tracklet_motion_consistency)
        self.assertTrue(parser.parse_args([
            "analyze", "source.mp4", "--out", "runs", "--sparse-flow",
            "--sparse-tracklet-motion-consistency"
        ]).sparse_tracklet_motion_consistency)

    @staticmethod
    def _projective_points():
        points = []
        for y in range(12, 84, 12):
            for x in range(12, 156, 16):
                denominator = 1 + 0.003 * (x - 80) + 0.0018 * (y - 45)
                u = (x + 1.5) / denominator
                v = (y - 0.8) / denominator
                points.append({"x": x, "y": y, "dx": u - x, "dy": v - y})
        return points

    def test_projective_warp_beats_affine_on_same_broad_inliers(self):
        result = fit_image_homography(self._projective_points(), 160, 90)
        self.assertEqual(result["status"], "projective-image-plane-candidate")
        self.assertGreaterEqual(result["inliers"], 45)
        model = result["model"]
        self.assertLess(model["rmsHomographyPixels"], 0.001)
        self.assertGreater(model["rmsAffinePixels"], 0.75)
        self.assertGreater(model["cornerDenominatorRatio"], 1.03)
        self.assertFalse(model["calibratedConfidence"])
        self.assertEqual(len(model["matrix3x3"]), 3)

    def test_rejects_outliers_without_relabeling_independent_motion_camera(self):
        points = self._projective_points()
        for index in range(0, len(points), 6):
            points[index] = {**points[index], "dx": -12.0, "dy": 8.0}
        first = fit_image_homography(points, 160, 90)
        self.assertEqual(first, fit_image_homography(points, 160, 90))
        self.assertEqual(first["status"], "projective-image-plane-candidate")
        self.assertGreaterEqual(first["inliers"], 35)
        self.assertLess(first["inliers"], len(points))

    def test_equal_competing_motion_models_abstain(self):
        points = self._projective_points()
        for index in range(0, len(points), 2):
            points[index] = {**points[index], "dx": -8, "dy": 5}
        result = fit_image_homography(points, 160, 90)
        self.assertNotEqual(result["status"], "projective-image-plane-candidate")

    def test_affine_translation_and_collinear_data_do_not_force_perspective(self):
        affine = [{"x": x, "y": y, "dx": 1.2 + 0.02 * x + 0.03 * y,
                   "dy": -0.8 - 0.01 * x + 0.01 * y}
                  for x in range(12, 153, 20) for y in range(12, 79, 13)]
        result = fit_image_homography(affine, 160, 90)
        self.assertEqual(result["status"], "affine-sufficient")
        self.assertLess(result["model"]["rmsAffinePixels"], 0.001)
        self.assertEqual(fit_image_homography(affine[:9], 160, 90)["status"],
                         "insufficient-points")
        collinear = [{"x": 10 + i * 5, "y": 40, "dx": i * 0.1, "dy": 0}
                     for i in range(25)]
        self.assertNotEqual(fit_image_homography(collinear, 160, 90)["status"],
                            "projective-image-plane-candidate")

    def test_adversarial_measurements_fail_closed(self):
        points = self._projective_points()
        points[0]["dx"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            fit_image_homography(points, 160, 90)
        with self.assertRaisesRegex(ValueError, "bounded"):
            fit_image_homography([], 2000, 1000)
        with self.assertRaisesRegex(ValueError, "budget"):
            fit_image_homography([], 160, 90, max_hypotheses=10000)
        with self.assertRaisesRegex(ValueError, "budget"):
            fit_image_homography([{"x": 0}] * 65, 160, 90)


if __name__ == "__main__":
    unittest.main()
