"""Out-of-sample geometric evidence must not reward flexible in-sample fits."""

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.cli.app import build_parser


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy unavailable")
class SpatialModelValidationTests(unittest.TestCase):
    @staticmethod
    def _points(kind):
        points = []
        for y in range(12, 84, 12):
            for x in range(12, 156, 16):
                if kind == "translation":
                    dx, dy = 3.0, -2.0
                elif kind == "affine":
                    dx, dy = 2 + 0.08 * (x - 80), -1 + 0.06 * (y - 45)
                elif kind == "projective":
                    denominator = 1 + 0.003 * (x - 80) + 0.0018 * (y - 45)
                    dx, dy = (x + 1.5) / denominator - x, (y - 0.8) / denominator - y
                else:
                    raise AssertionError(kind)
                points.append({"x": x, "y": y, "dx": dx, "dy": dy})
        return points

    def test_translation_does_not_get_promoted_to_more_complex_model(self):
        from kumiki_reference_lab.analyzers.motion.model_validation import compare_motion_models

        report = compare_motion_models(self._points("translation"), 160, 90)
        self.assertEqual(report["status"], "holdout-supported")
        self.assertEqual(report["preferredModel"], "translation")
        self.assertEqual(report["validationPoints"], 54)
        self.assertLess(report["models"]["translation"]["rmsPixels"], 0.0001)
        self.assertFalse(report["calibratedConfidence"])
        self.assertFalse(report["physicalCameraVerified"])
        json.dumps(report, allow_nan=False)

    def test_affine_motion_requires_unseen_point_improvement(self):
        from kumiki_reference_lab.analyzers.motion.model_validation import compare_motion_models

        report = compare_motion_models(self._points("affine"), 160, 90)
        self.assertEqual(report["status"], "holdout-supported")
        self.assertEqual(report["preferredModel"], "affine")
        self.assertGreater(report["models"]["translation"]["rmsPixels"], 3)
        self.assertLess(report["models"]["affine"]["rmsPixels"], 0.001)

    def test_projective_motion_requires_independent_prediction_gain(self):
        from kumiki_reference_lab.analyzers.motion.model_validation import compare_motion_models

        report = compare_motion_models(self._points("projective"), 160, 90)
        self.assertEqual(report["status"], "holdout-supported")
        self.assertEqual(report["preferredModel"], "projective")
        self.assertGreater(report["models"]["affine"]["rmsPixels"], 0.75)
        self.assertLess(report["models"]["projective"]["rmsPixels"], 0.001)

    def test_competing_motion_and_sparse_support_abstain(self):
        from kumiki_reference_lab.analyzers.motion.model_validation import compare_motion_models

        mixed = self._points("translation")
        for i in range(0, len(mixed), 2):
            mixed[i] = {**mixed[i], "dx": -8, "dy": 6}
        report = compare_motion_models(mixed, 160, 90)
        self.assertEqual(report["status"], "unreliable-holdout")
        self.assertIsNone(report["preferredModel"])
        self.assertEqual(compare_motion_models(mixed[:7], 160, 90)["status"],
                         "insufficient-correspondences")
        collinear = [{"x": 10 + i * 3, "y": 40, "dx": 3, "dy": 2}
                     for i in range(25)]
        self.assertEqual(compare_motion_models(collinear, 160, 90)["status"],
                         "insufficient-spatial-validation")

    def test_diagonal_points_do_not_fake_two_dimensional_model_comparison(self):
        from kumiki_reference_lab.analyzers.motion.model_validation import compare_motion_models

        diagonal = [{"x": 12 + 8 * i, "y": 10 + 0.4 * (12 + 8 * i),
                     "dx": 3.0, "dy": -2.0} for i in range(18)]
        result = compare_motion_models(diagonal, 160, 90)
        self.assertEqual(result["status"], "insufficient-spatial-validation")
        self.assertIsNone(result["preferredModel"])

    def test_small_outlier_group_cannot_hide_beyond_interpolated_percentile(self):
        from kumiki_reference_lab.analyzers.motion.model_validation import compare_motion_models

        points = [p for index, p in enumerate(self._points("translation"))
                  if index % 3 == 0]
        # Two of eighteen matches are wrong by 4.2 px; interpolation of the
        # 90th percentile can conceal them despite 11% bad predictions.
        for index in (2, 11):
            points[index] = {**points[index], "dx": points[index]["dx"] + 4.2}
        report = compare_motion_models(points, 160, 90)
        self.assertEqual(report["status"], "unreliable-holdout")
        self.assertIsNone(report["preferredModel"])
        self.assertGreater(report["models"]["translation"]["p90Pixels"], 3.0)

    def test_invalid_or_nonfinite_input_fails_closed(self):
        from kumiki_reference_lab.analyzers.motion.model_validation import compare_motion_models

        with self.assertRaisesRegex(ValueError, "bounded"):
            compare_motion_models(self._points("affine"), 2000, 1000)
        with self.assertRaisesRegex(ValueError, "finite"):
            compare_motion_models([{**p, "dx": float("nan")} if i == 0 else p
                                   for i, p in enumerate(self._points("affine"))], 160, 90)
        with self.assertRaisesRegex(ValueError, "budget"):
            compare_motion_models(self._points("affine") * 2, 160, 90)

    def test_cli_opt_in_and_analysis_run_flag(self):
        parser = build_parser()
        self.assertFalse(parser.parse_args(["sparse-flow", "movie.mp4"])
                         .model_validation)
        self.assertTrue(parser.parse_args(["sparse-flow", "movie.mp4",
                                           "--model-validation"]).model_validation)
        self.assertTrue(parser.parse_args(["analyze", "movie.mp4", "--out", "runs",
                                           "--sparse-flow", "--sparse-model-validation"])
                        .sparse_model_validation)

    def test_model_validation_cannot_be_silently_ignored_without_sparse_stage(self):
        from kumiki_reference_lab.pipeline.analyze import run_analysis

        with self.assertRaisesRegex(ValueError, "requires sparse-flow"):
            run_analysis(Path("unused.mp4"), Path("runs"),
                         sparse_flow=False, sparse_model_validation=True)


@unittest.skipUnless(importlib.util.find_spec("numpy") and shutil.which("ffmpeg") and
                     shutil.which("ffprobe"), "NumPy and FFmpeg required")
class EncodedModelValidationTests(unittest.TestCase):
    def test_encoded_source_and_immutable_analysis_preserve_opt_in_holdout_evidence(self):
        import numpy as np
        from kumiki_reference_lab.analyzers.motion.sparse import analyze_sparse_flow
        from kumiki_reference_lab.pipeline.analyze import run_analysis

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video = root / "translated.mkv"
            base = np.random.default_rng(423).integers(0, 256, (90, 160), dtype=np.uint8)
            frames = b"".join(np.repeat(np.roll(base, 2 * i, axis=1)[:, :, None],
                                         3, axis=2).tobytes() for i in range(8))
            proc = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "160x90",
                "-framerate", "10", "-i", "pipe:0", "-c:v", "ffv1", str(video),
            ], input=frames, capture_output=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode(errors="replace"))

            ordinary = analyze_sparse_flow(video, seconds=2, max_samples=8,
                                           max_points=64, threshold=.95)
            self.assertNotIn("modelValidationMethod", ordinary["analyzer"])
            self.assertTrue(all("modelValidation" not in pair
                                for pair in ordinary["pairs"]))
            run = run_analysis(video, root / "runs", seconds=2, thumbnails=4,
                               sparse_flow=True, sparse_samples=8, sparse_points=64,
                               sparse_model_validation=True, threshold=.95)
            manifest = json.loads(run.read_text())
            report = json.loads((run.parent / manifest["artifacts"]["sparseFlow"]).read_text())
            self.assertEqual(report["samples"], ordinary["samples"])
            self.assertEqual(report["analyzer"]["modelValidationMethod"],
                             "spatial-three-fold-out-of-sample-v1")
            self.assertTrue(all("modelValidation" in pair for pair in report["pairs"]))
            self.assertTrue(any(pair["modelValidation"]["preferredModel"] == "translation"
                                for pair in report["pairs"]))
            self.assertTrue(all(pair["modelValidation"]["physicalCameraVerified"] is False
                                for pair in report["pairs"]))
            if importlib.util.find_spec("jsonschema"):
                from jsonschema import Draft202012Validator, ValidationError

                schema = json.loads((Path(__file__).resolve().parents[1] /
                                     "schemas/v1/sparse-flow.schema.json").read_text())
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(report)
                malformed = json.loads(json.dumps(report))
                del malformed["pairs"][0]["modelValidation"]
                with self.assertRaises(ValidationError):
                    Draft202012Validator(schema).validate(malformed)
            self.assertEqual(run_analysis(video, root / "runs", seconds=2, thumbnails=4,
                                          sparse_flow=True, sparse_samples=8,
                                          sparse_points=64, sparse_model_validation=True,
                                          threshold=.95), run)


if __name__ == "__main__":
    unittest.main()
