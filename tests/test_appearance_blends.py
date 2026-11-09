"""Original RGB blend counterexamples; no third-party footage or model."""

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from kumiki_reference_lab.analyzers.appearance.blends import detect_linear_blend_candidates
from kumiki_reference_lab.analyzers.appearance.analyze import analyze_appearance


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy unavailable")
class LinearBlendCandidateTests(unittest.TestCase):
    @staticmethod
    def _samples(pts):
        return ([{"sourcePts": p} for p in pts],
                [{"status": "measured-display-appearance-change"} for _ in pts[1:]])

    @staticmethod
    def _blend_frames(pts):
        import numpy as np

        rng = np.random.default_rng(942)
        first = rng.integers(0, 256, (90, 160, 3), dtype=np.uint8).astype(float)
        last = rng.integers(0, 256, (90, 160, 3), dtype=np.uint8).astype(float)
        return [np.rint((1 - (p - pts[0]) / (pts[-1] - pts[0])) * first +
                        ((p - pts[0]) / (pts[-1] - pts[0])) * last)
                .astype(np.uint8).tobytes() for p in pts]

    def test_original_linear_blend_uses_source_pts_not_frame_index(self):
        pts = [0, 10, 15, 30, 40]
        samples, changes = self._samples(pts)
        candidates = detect_linear_blend_candidates(self._blend_frames(pts),
                                                     samples, changes,
                                                     timebase=Fraction(1, 100))
        self.assertEqual(len(candidates), 1)
        item = candidates[0]
        self.assertEqual(item["kind"], "linear-image-blend-candidate")
        self.assertEqual(item["durationSeconds"], {"numerator": 2, "denominator": 5})
        self.assertLess(item["normalizedResidual"], 0.02)
        self.assertEqual(item["interpretationStatus"], "review-required-not-verified")
        json.dumps(candidates, allow_nan=False)

    def test_cut_candidate_or_too_fast_sequence_is_not_blended_across(self):
        pts = [0, 10, 20, 30, 40]
        samples, changes = self._samples(pts)
        frames = self._blend_frames(pts)
        changes[2]["status"] = "cut-boundary"
        self.assertEqual(detect_linear_blend_candidates(
            frames, samples, changes, timebase=Fraction(1, 100)), [])
        changes[2]["status"] = "measured-display-appearance-change"
        self.assertEqual(detect_linear_blend_candidates(
            frames, samples, changes, timebase=Fraction(1, 1000)), [])

    def test_image_pan_and_black_fade_do_not_masquerade_as_blend(self):
        import numpy as np

        pts = [0, 10, 20, 30, 40]
        samples, changes = self._samples(pts)
        base = np.random.default_rng(124).integers(0, 256, (90, 160, 3), dtype=np.uint8)
        moved = [np.roll(base, 2 * i, axis=1).tobytes() for i in range(5)]
        self.assertEqual(detect_linear_blend_candidates(
            moved, samples, changes, timebase=Fraction(1, 100)), [])
        fade = [np.rint(base.astype(float) * (1 - i / 4))
                .astype(np.uint8).tobytes() for i in range(5)]
        self.assertEqual(detect_linear_blend_candidates(
            fade, samples, changes, timebase=Fraction(1, 100)), [])

    def test_flat_color_animation_is_not_evidence_for_two_textured_sources(self):
        import numpy as np

        pts = [0, 10, 20, 30, 40]
        samples, changes = self._samples(pts)
        frames = [np.full((90, 160, 3), (20 + i * 50), dtype=np.uint8).tobytes()
                  for i in range(5)]
        self.assertEqual(detect_linear_blend_candidates(
            frames, samples, changes, timebase=Fraction(1, 100)), [])


@unittest.skipUnless(importlib.util.find_spec("numpy") and shutil.which("ffmpeg") and
                     shutil.which("ffprobe"), "NumPy/FFmpeg unavailable")
class EncodedBlendCandidateTests(unittest.TestCase):
    def test_lossless_ffv1_source_retains_unverified_blend_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "blend.mkv"
            pts = [0, 10, 20, 30, 40]
            frames = LinearBlendCandidateTests._blend_frames(pts)
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "160x90",
                "-framerate", "10", "-i", "pipe:0", "-c:v", "ffv1", str(video),
            ], input=b"".join(frames), capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = analyze_appearance(video, seconds=2, max_samples=5,
                                        threshold=0.95)
            self.assertEqual(len(result["imageBlendCandidates"]), 1)
            self.assertEqual(result["analyzer"]["blendModel"],
                             "five-source-frame-linear-rgb-blend-candidate-v1")
            self.assertEqual(result["imageBlendCandidates"][0]["startPts"],
                             result["samples"][0]["sourcePts"])
            self.assertFalse(result["analyzer"]["physicalPhotometry"])
            json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
