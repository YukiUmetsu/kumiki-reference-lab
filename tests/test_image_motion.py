import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from kumiki_reference_lab.analyzers.motion.analyze import (
    analyze_image_motion, select_motion_samples,
)
from kumiki_reference_lab.analyzers.motion.easing import fit_easing_candidates
from kumiki_reference_lab.analyzers.motion.phase import measure_image_shift
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_gray_frames
from kumiki_reference_lab.contracts.frames import FramePts


class MotionSamplingTests(unittest.TestCase):
    def test_variable_frame_rate_sampling_uses_pts_not_ordinals(self):
        frames = [FramePts(i, pts, "pts") for i, pts in enumerate(
            [0, 1, 2, 3, 4, 9, 15, 30, 45, 60])]
        samples = select_motion_samples(frames, 5)
        self.assertEqual([f.pts for f in samples], [0, 15, 30, 45, 60])

    def test_bad_pts_rejected_instead_of_inferred(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            select_motion_samples([FramePts(0, 1, "pts"),
                                   FramePts(1, 1, "pts")], 5)

    def test_decoder_rejects_unverified_pts(self):
        with patch("subprocess.run", return_value=CompletedProcess(
            [], 0, b"12345", b"[Parsed_showinfo_1] config in time_base: 1/1000\n"
                              b"[Parsed_showinfo_1] n: 0 pts: 200 pts_time:0.2\n"
        )):
            with self.assertRaisesRegex(ProbeError, "do not match"):
                read_gray_frames(Path("test.mkv"), 0, [0], [100],
                                 timebase=Fraction(1, 1000), seconds=1,
                                 width=64, height=36)


class EasingFitTests(unittest.TestCase):
    def test_linear_motion_has_linear_candidate(self):
        observations = [(Fraction(i, 10), i * 2.0, 0.0) for i in range(11)]
        fitted = fit_easing_candidates(observations)
        self.assertEqual(fitted["status"], "candidate-only")
        self.assertEqual(fitted["bestCandidate"], "linear")
        self.assertEqual(fitted["maxLateralDeviationPixels"], 0)
        self.assertEqual(fitted["pathLengthRatio"], 1)

    def test_straight_diagonal_image_motion_can_still_fit_easing(self):
        observations = [(Fraction(i, 10), i * 2.0, i * 1.5) for i in range(11)]
        fitted = fit_easing_candidates(observations)
        self.assertEqual(fitted["bestCandidate"], "linear")
        self.assertAlmostEqual(fitted["pathLengthRatio"], 1)

    def test_bent_path_does_not_get_a_false_perfect_linear_ease(self):
        # The x projection is perfectly linear, but the actual image path
        # rises 6 px off the start-to-end direction and comes back down.
        observations = [(Fraction(i, 10), i * 2.0, float(5 - abs(i - 5)) * 1.2)
                        for i in range(11)]
        fitted = fit_easing_candidates(observations)
        self.assertEqual(fitted["status"], "nonlinear-image-path")
        self.assertIsNone(fitted["bestCandidate"])
        self.assertEqual(fitted["candidates"], [])
        self.assertAlmostEqual(fitted["maxLateralDeviationPixels"], 6, delta=0.01)
        self.assertGreater(fitted["pathLengthRatio"], 1.1)

    def test_small_sideways_noise_is_tolerated_but_repeated_detours_are_not(self):
        subtle = [(Fraction(i, 10), i * 2.0, (i % 2) * 0.25)
                  for i in range(11)]
        self.assertEqual(fit_easing_candidates(subtle)["bestCandidate"], "linear")
        zigzag = [(Fraction(i, 10), i * 2.0, 1.6 if i % 2 else 0.0)
                  for i in range(11)]
        result = fit_easing_candidates(zigzag)
        self.assertEqual(result["status"], "nonlinear-image-path")
        self.assertLess(result["maxLateralDeviationPixels"], 2)
        self.assertGreater(result["pathLengthRatio"], 1.2)

    def test_nonfinite_image_positions_fail_closed(self):
        observations = [(Fraction(i), float(i), 0.0) for i in range(5)]
        observations[2] = (Fraction(2), float("nan"), 0.0)
        fitted = fit_easing_candidates(observations)
        self.assertEqual(fitted["status"], "invalid-observations")
        self.assertEqual(fitted["candidates"], [])
        json.dumps(fitted, allow_nan=False)

    def test_smoothstep_motion_has_cubic_candidate(self):
        observations = []
        for i in range(13):
            t = i / 12
            observations.append((Fraction(i, 12), (3 * t ** 2 - 2 * t ** 3) * 20, 0.0))
        fitted = fit_easing_candidates(observations)
        self.assertEqual(fitted["bestCandidate"], "ease-in-out-cubic")

    def test_short_or_reversing_path_is_not_misclassified(self):
        short = [(Fraction(i), float(i), 0.0) for i in range(3)]
        self.assertEqual(fit_easing_candidates(short)["status"], "insufficient-samples")
        reversing = [(Fraction(i), float(x), 0.0) for i, x in
                     enumerate([0, 5, 10, 6, 2, 15])]
        self.assertEqual(fit_easing_candidates(reversing)["status"],
                         "nonmonotonic-or-overshooting")


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy motion extra unavailable")
class PhaseCorrelationTests(unittest.TestCase):
    def test_detects_known_image_shift(self):
        import numpy as np
        original = np.random.default_rng(37).integers(0, 255, size=(90, 160), dtype=np.uint8)
        shifted = np.roll(np.roll(original, 3, axis=0), -5, axis=1)
        result = measure_image_shift(original.tobytes(), shifted.tobytes(), 160, 90)
        self.assertEqual(result["status"], "measured-image-translation")
        self.assertAlmostEqual(result["dxPixels"], -5, delta=0.15)
        self.assertAlmostEqual(result["dyPixels"], 3, delta=0.15)

    def test_uniform_frame_has_no_fabricated_motion(self):
        frame = bytes([128] * (160 * 90))
        result = measure_image_shift(frame, frame, 160, 90)
        self.assertEqual(result["status"], "unobservable-low-texture")
        self.assertIsNone(result["dxPixels"])


@unittest.skipUnless(importlib.util.find_spec("numpy") and
                     shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "NumPy/FFmpeg test dependencies unavailable")
class ImageMotionIntegrationTests(unittest.TestCase):
    def test_real_video_preserves_pts_and_returns_bounded_measurements(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "moving.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = analyze_image_motion(source, seconds=2, max_samples=10, threshold=0.95)
            self.assertEqual(len(result["samples"]), 10)
            self.assertEqual(len(result["pairs"]), 9)
            self.assertEqual(result["analysis"]["easingModel"],
                             "net-path-projection-with-geometry-abstention-v2")
            self.assertTrue(all(item["deltaTimeSeconds"]["numerator"] > 0
                                for item in result["pairs"]))
            self.assertEqual(result["analysis"]["calibratedConfidence"], False)
            json.dumps(result, allow_nan=False)

    def test_flat_video_reports_unobservable_instead_of_movement(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "flat.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = analyze_image_motion(source, seconds=2, max_samples=10, threshold=0.95)
            self.assertTrue(all(item["status"] == "unobservable-low-texture"
                                for item in result["pairs"]))
            self.assertEqual(result["segments"], [])

    def test_vfr_motion_sampling_and_decoder_preserve_real_times(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "variable-rate.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=1",
                "-vf", "setpts='if(lt(N,5),N,N*2)/(10*TB)'", "-fps_mode", "vfr",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            report = analyze_image_motion(source, seconds=2, max_samples=10, threshold=0.95)
            pts = [frame["sourcePts"] for frame in report["samples"]]
            increments = [b - a for a, b in zip(pts, pts[1:])]
            self.assertGreater(max(increments), min(increments))
            self.assertTrue(all(pair["deltaTimeSeconds"]["numerator"] > 0
                                for pair in report["pairs"]))


if __name__ == "__main__":
    unittest.main()
