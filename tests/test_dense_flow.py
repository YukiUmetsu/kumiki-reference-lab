"""Dense image-plane flow is bounded evidence, not a recovered camera path."""

import importlib.util
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout

from kumiki_reference_lab.cli.app import build_parser


class DenseFlowInterfaceTests(unittest.TestCase):
    def test_flags_are_opt_in_and_separate_from_sparse_flow(self):
        parser = build_parser()
        self.assertFalse(parser.parse_args(["analyze", "ref.mp4", "--out", "runs"])
                         .dense_flow)
        self.assertTrue(parser.parse_args(["analyze", "ref.mp4", "--out", "runs",
                                           "--dense-flow"]).dense_flow)
        self.assertEqual(parser.parse_args(["dense-flow", "ref.mp4",
                                            "--grid-step", "16"]).grid_step, 16)

    def test_opt_in_validation_rejects_bogus_budgets_before_reading_video(self):
        from kumiki_reference_lab.pipeline.analyze import run_analysis

        with self.assertRaisesRegex(ValueError, "dense-flow"):
            run_analysis(Path("missing.mp4"), Path("runs"), dense_flow=True,
                         dense_grid_step=2)


@unittest.skipUnless(importlib.util.find_spec("cv2") and
                     importlib.util.find_spec("numpy"), "OpenCV dense extra required")
class DenseFlowEstimatorTests(unittest.TestCase):
    @staticmethod
    def _texture():
        import cv2
        import numpy as np

        pixels = np.random.default_rng(812).integers(0, 256, (90, 160),
                                                     dtype=np.uint8)
        return cv2.GaussianBlur(pixels, (5, 5), 0.8)

    def test_multiscale_flow_predicts_translation_on_textured_pixels(self):
        import numpy as np
        from kumiki_reference_lab.analyzers.motion.dense import measure_dense_flow

        before = self._texture()
        after = np.zeros_like(before)
        after[:, 4:] = before[:, :-4]
        report = measure_dense_flow(before.tobytes(), after.tobytes(), 160, 90)
        self.assertEqual(report["status"], "flow-observed")
        self.assertGreater(len(report["vectors"]), 30)
        horizontal = np.median([v["dx"] for v in report["vectors"]])
        vertical = np.median([v["dy"] for v in report["vectors"]])
        self.assertAlmostEqual(horizontal, 4, delta=0.65)
        self.assertAlmostEqual(vertical, 0, delta=0.65)
        self.assertTrue(all(v["roundtripErrorPixels"] <= 1.5 for v in report["vectors"]))
        self.assertLessEqual(report["candidateCount"], 200)
        json.dumps(report, allow_nan=False)

    def test_uniform_and_fully_occluded_frames_abstain(self):
        import numpy as np
        from kumiki_reference_lab.analyzers.motion.dense import measure_dense_flow

        flat = bytes([128] * 160 * 90)
        empty = measure_dense_flow(flat, flat, 160, 90)
        self.assertEqual(empty["status"], "unobservable")
        self.assertEqual(empty["vectors"], [])
        self.assertEqual(empty["rejected"]["low-texture"], empty["candidateCount"])

        occluded = measure_dense_flow(self._texture().tobytes(), flat, 160, 90)
        self.assertEqual(occluded["status"], "unobservable")
        self.assertEqual(occluded["vectors"], [])

    def test_unrelated_textured_frames_do_not_pass_as_motion_evidence(self):
        import cv2
        import numpy as np
        from kumiki_reference_lab.analyzers.motion.dense import measure_dense_flow

        for seed in range(4):
            rng = np.random.default_rng(seed)
            before = cv2.GaussianBlur(rng.integers(0, 256, (90, 160),
                                                        dtype=np.uint8), (5, 5), 0.8)
            after = cv2.GaussianBlur(rng.integers(0, 256, (90, 160),
                                                       dtype=np.uint8), (5, 5), 0.8)
            report = measure_dense_flow(before.tobytes(), after.tobytes(), 160, 90)
            self.assertIn(report["status"],
                          ("unobservable", "insufficient-grid-support"))
            self.assertLessEqual(len(report["vectors"]), 3)
            self.assertGreater(report["rejected"]["appearance-inconsistent"], 10)

    def test_new_textured_occluder_is_not_mistaken_for_corresponding_surface(self):
        import cv2
        import numpy as np
        from kumiki_reference_lab.analyzers.motion.dense import measure_dense_flow

        before = self._texture()
        after = np.roll(before, 3, axis=1)
        new_texture = np.random.default_rng(619).integers(0, 256, (50, 50),
                                                          dtype=np.uint8)
        after[20:70, 55:105] = cv2.GaussianBlur(new_texture, (5, 5), 0.8)
        report = measure_dense_flow(before.tobytes(), after.tobytes(), 160, 90)
        self.assertTrue(all(not (66 <= v["x"] <= 90 and 30 <= v["y"] <= 54)
                            for v in report["vectors"]))
        self.assertGreater(report["rejected"]["appearance-inconsistent"], 0)
        self.assertGreater(len(report["vectors"]), 10)

    def test_appearance_gate_tolerates_global_brightness_offset(self):
        import numpy as np
        from kumiki_reference_lab.analyzers.motion.dense import measure_dense_flow

        before = self._texture()
        shifted = np.roll(before, 3, axis=1)
        brighter = np.clip(shifted.astype(np.int16) + 22, 0, 255).astype(np.uint8)
        report = measure_dense_flow(before.tobytes(), brighter.tobytes(), 160, 90)
        self.assertEqual(report["status"], "flow-observed")
        self.assertGreater(len(report["vectors"]), 25)
        self.assertAlmostEqual(float(np.median([v["dx"] for v in report["vectors"]])),
                               3, delta=0.8)

    def test_partial_occlusion_rejects_hidden_grid_cells_without_losing_visible_motion(self):
        import numpy as np
        from kumiki_reference_lab.analyzers.motion.dense import measure_dense_flow

        before = self._texture()
        after = np.zeros_like(before)
        after[:, 3:] = before[:, :-3]
        after[20:70, 55:105] = 128
        report = measure_dense_flow(before.tobytes(), after.tobytes(), 160, 90)
        self.assertGreater(len(report["vectors"]), 10)
        self.assertGreater(report["rejected"]["low-texture"], 0)
        self.assertTrue(all(not (59 <= v["x"] <= 96 and 26 <= v["y"] <= 64)
                            for v in report["vectors"]))

    def test_independent_layers_do_not_collapse_into_one_camera_motion(self):
        import numpy as np
        from kumiki_reference_lab.analyzers.motion.dense import measure_dense_flow

        before = self._texture().copy()
        subject = np.roll(self._texture()[20:70, 90:145], 3, axis=0)
        before[20:70, 90:145] = subject
        after = np.roll(before, 2, axis=1)
        after[20:70, 84:139] = subject
        report = measure_dense_flow(before.tobytes(), after.tobytes(), 160, 90)
        dxs = [v["dx"] for v in report["vectors"]]
        self.assertGreater(sum(1 for dx in dxs if 1 < dx < 3), 10)
        self.assertGreater(sum(1 for dx in dxs if -7 < dx < -4), 2)
        self.assertNotIn("camera", json.dumps(report))

    def test_invalid_planes_fail_fast(self):
        from kumiki_reference_lab.analyzers.motion.dense import measure_dense_flow

        with self.assertRaisesRegex(ValueError, "plane"):
            measure_dense_flow(b"short", b"short", 160, 90)
        with self.assertRaisesRegex(ValueError, "grid step"):
            measure_dense_flow(bytes(160 * 90), bytes(160 * 90), 160, 90,
                               grid_step=True)

    def test_tiny_valid_grid_reports_insufficient_support_not_no_observation(self):
        import cv2
        import numpy as np
        from kumiki_reference_lab.analyzers.motion.dense import measure_dense_flow

        base = np.random.default_rng(715).integers(0, 256, (36, 64),
                                                  dtype=np.uint8)
        before = cv2.GaussianBlur(base, (5, 5), 0.8)
        after = np.roll(before, 3, axis=1)
        report = measure_dense_flow(before.tobytes(), after.tobytes(), 64, 36,
                                    grid_step=24)
        self.assertGreater(len(report["vectors"]), 0)
        self.assertEqual(report["status"], "insufficient-grid-support")
        self.assertLess(report["candidateCount"], 5)


@unittest.skipUnless(importlib.util.find_spec("cv2") and
                     importlib.util.find_spec("numpy") and
                     shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "OpenCV, NumPy, FFmpeg, FFprobe required")
class EncodedDenseFlowTests(unittest.TestCase):
    def test_vfr_pts_are_preserved_with_nonuniform_pair_intervals(self):
        from kumiki_reference_lab.analyzers.motion.dense import analyze_dense_flow

        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "vfr-cut.mkv"
            result = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=1",
                "-vf", "setpts='if(lt(N,5),N,N*2)/(10*TB)'", "-fps_mode", "vfr",
                "-c:v", "ffv1", str(video),
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = analyze_dense_flow(video, seconds=2, max_samples=9,
                                        threshold=.95)
            self.assertGreater(len({(p["deltaTimeSeconds"]["numerator"],
                                     p["deltaTimeSeconds"]["denominator"])
                                    for p in report["pairs"]}), 1)
            self.assertTrue(all(p["startPts"] < p["endPts"]
                                for p in report["pairs"]))

    def test_hard_edit_skips_dense_measurement_across_boundary(self):
        import numpy as np
        from kumiki_reference_lab.analyzers.motion.dense import analyze_dense_flow

        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "hard-edit.mkv"
            base = np.random.default_rng(311).integers(0, 256, (90, 160),
                                                       dtype=np.uint8)
            first = np.repeat(base[:, :, None], 3, axis=2).tobytes()
            second = np.repeat((255 - base)[:, :, None], 3, axis=2).tobytes()
            proc = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "160x90",
                "-framerate", "10", "-i", "pipe:0", "-c:v", "ffv1", str(video),
            ], input=first * 5 + second * 5, capture_output=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode(errors="replace"))
            report = analyze_dense_flow(video, seconds=2, max_samples=10,
                                        threshold=.12)
            boundaries = [p for p in report["pairs"] if p["status"] == "cut-boundary"]
            self.assertEqual(len(boundaries), 1)
            self.assertEqual(boundaries[0]["vectors"], [])
            self.assertEqual(boundaries[0]["candidateCount"], 0)

    def test_timecoded_dense_flow_in_atomic_analysis_is_stable_and_schema_valid(self):
        import cv2
        import numpy as np
        from kumiki_reference_lab.pipeline.analyze import run_analysis

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "translated.mkv"
            pixels = np.random.default_rng(57).integers(0, 256, (90, 160),
                                                       dtype=np.uint8)
            base = cv2.GaussianBlur(pixels, (5, 5), 0.9)
            frames = b"".join(np.repeat(np.roll(base, 2 * i, axis=1)[:, :, None],
                                         3, axis=2).tobytes() for i in range(8))
            result = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "160x90",
                "-framerate", "10", "-i", "pipe:0", "-c:v", "ffv1", str(source),
            ], input=frames, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            run = run_analysis(source, root / "runs", seconds=2, thumbnails=4,
                               dense_flow=True, dense_samples=8, dense_grid_step=12,
                               threshold=.95)
            manifest = json.loads(run.read_text())
            self.assertIn("denseFlow", manifest["artifacts"])
            dense = json.loads((run.parent / manifest["artifacts"]["denseFlow"]).read_text())
            self.assertEqual(dense["schemaVersion"], "kumiki.dense-flow.v1")
            self.assertEqual(len(dense["pairs"]), len(dense["samples"]) - 1)
            self.assertTrue(all(p["deltaTimeSeconds"]["numerator"] > 0
                                for p in dense["pairs"]))
            self.assertTrue(any(p["status"] == "flow-observed" for p in dense["pairs"]))
            self.assertFalse(dense["analyzer"]["physicalCameraVerified"])
            if importlib.util.find_spec("jsonschema"):
                from jsonschema import Draft202012Validator

                schema_root = Path(__file__).resolve().parents[1] / "schemas/v1"
                schema = json.loads((schema_root / "dense-flow.schema.json").read_text())
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(dense)
                run_schema = json.loads((schema_root / "analysis-run.schema.json").read_text())
                Draft202012Validator.check_schema(run_schema)
                Draft202012Validator(run_schema).validate(manifest)

            from kumiki_reference_lab.cli.app import main
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["dense-flow", str(source), "--max-seconds", "2",
                                       "--max-samples", "8", "--threshold", ".95",
                                       "--out", str(root / "standalone")]), 0)
            self.assertTrue((root / "standalone" / "dense-flow.json").is_file())
            self.assertEqual(run, run_analysis(source, root / "runs", seconds=2,
                                               thumbnails=4, dense_flow=True,
                                               dense_samples=8, dense_grid_step=12,
                                               threshold=.95))


if __name__ == "__main__":
    unittest.main()
