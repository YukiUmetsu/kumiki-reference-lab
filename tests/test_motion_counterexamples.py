"""Lossless-video counterexamples for sparse motion, not semantic ground truth.

Run locally with NumPy and FFmpeg; the credit-limited CI checks stay unchanged.
"""

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from kumiki_reference_lab.analyzers.motion.sparse import analyze_sparse_flow


@unittest.skipUnless(
    importlib.util.find_spec("numpy") and shutil.which("ffmpeg") and
    shutil.which("ffprobe"), "NumPy, FFmpeg and FFprobe required")
class EncodedMotionCounterexamplesTests(unittest.TestCase):
    WIDTH = 160
    HEIGHT = 90

    @classmethod
    def _encode(cls, output: Path, gray_frames: list[object], *, vfr: bool = False) -> None:
        import numpy as np

        payload = b"".join(
            np.repeat(np.asarray(frame, dtype=np.uint8)[:, :, None], 3, axis=2)
            .tobytes() for frame in gray_frames)
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "160x90",
            "-framerate", "10", "-i", "pipe:0",
        ]
        if vfr:
            # A discontinuity in *source presentation time*, not an edit or
            # an extra frame. Constant frame-index intervals are deliberately false.
            command += ["-vf", "setpts='(N+if(gte(N,5),3,0))/(10*TB)'",
                        "-fps_mode", "vfr"]
        command += ["-c:v", "ffv1", str(output)]
        result = subprocess.run(command, input=payload, capture_output=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stderr.decode(errors="replace"))

    @staticmethod
    def _two_layers() -> list[object]:
        import numpy as np

        rng = np.random.default_rng(20261109)
        background = rng.integers(15, 240, (90, 160), dtype=np.uint8)
        foreground = rng.integers(15, 240, (36, 46), dtype=np.uint8)
        frames = []
        for index in range(9):
            image = np.roll(background, 2 * index, axis=1)
            left = 94 - 5 * index
            image[28:64, left:left + 46] = foreground
            frames.append(image)
        return frames

    @staticmethod
    def _full_frame_obstruction() -> list[object]:
        import numpy as np

        background = np.random.default_rng(20261110).integers(
            15, 240, (90, 160), dtype=np.uint8)
        frames = [np.roll(background, i, axis=1) for i in range(9)]
        # The subject becomes wholly invisible; subsequent identical flat
        # images contain no trackable evidence, even if the image returns.
        frames[3:6] = [np.full((90, 160), 116, dtype=np.uint8) for _ in range(3)]
        return frames

    def test_independent_foreground_motion_remains_unattributed(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "two-layers.mkv"
            self._encode(video, self._two_layers())
            result = analyze_sparse_flow(video, seconds=2, max_samples=9,
                                         max_points=64, threshold=0.95,
                                         lk_refinement=True)
            mixed = [pair for pair in result["pairs"]
                     if pair["status"] in ("multiple-image-translations",
                                           "ambiguous-dominant-group")]
            self.assertGreaterEqual(len(mixed), 2)
            for pair in mixed:
                centers = [cluster["dxPixels"] for cluster in pair["consensus"]["clusters"]]
                self.assertEqual(len(centers), 2)
                self.assertGreater(centers[0] - centers[1], 4)
                left, right = sorted(centers)
                self.assertAlmostEqual(left, -5, delta=1.0)
                self.assertAlmostEqual(right, 2, delta=1.0)
            self.assertFalse(result["temporalTracklets"]["semanticIdentityVerified"])
            self.assertFalse(result["analyzer"]["calibratedConfidence"])
            self.assertNotIn("camera", json.dumps([p["consensus"] for p in mixed]))
            json.dumps(result, allow_nan=False)

    def test_full_occlusion_stops_tracks_without_inventing_reidentification(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "opaque-obstruction.mkv"
            self._encode(video, self._full_frame_obstruction())
            result = analyze_sparse_flow(video, seconds=2, max_samples=9,
                                         max_points=64, threshold=0.95,
                                         tracklet_motion_consistency=True,
                                         tracklet_appearance_consistency=True)
            frames = result["samples"]
            self.assertEqual(len(frames), 9)
            self.assertTrue(any(pair["vectors"] for pair in result["pairs"][:2]))
            self.assertTrue(any(pair["vectors"] for pair in result["pairs"][6:]))
            # The two entirely flat->flat pairs have zero source corners.
            for pair in result["pairs"][3:5]:
                self.assertEqual(pair["vectors"], [])
            # No published temporal trace is allowed to bridge the three
            # invisible source frames by interpolation or reidentification.
            for track in result["temporalTracklets"]["tracklets"]:
                ordinals = [observation["pairIndex"] for observation in
                            track["observations"]]
                self.assertEqual(ordinals, list(range(ordinals[0], ordinals[-1] + 1)))
                self.assertFalse(ordinals[0] < 3 and ordinals[-1] >= 5)
                self.assertEqual(track["kinematics"]["basis"],
                                 "observed-pairs-only-no-gap-filling")
            self.assertFalse(result["temporalTracklets"]["semanticIdentityVerified"])
            json.dumps(result, allow_nan=False)

    def test_vfr_source_time_is_not_replaced_by_nominal_frame_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "two-layers-vfr.mkv"
            self._encode(video, self._two_layers(), vfr=True)
            result = analyze_sparse_flow(video, seconds=2, max_samples=9,
                                         max_points=64, threshold=0.95,
                                         tracklet_motion_consistency=True)
            samples = result["samples"]
            self.assertEqual(len(samples), 9)
            base = result["sourceTimebase"]
            timebase = Fraction(base["numerator"], base["denominator"])
            durations = []
            for i, pair in enumerate(result["pairs"]):
                self.assertEqual((pair["startPts"], pair["endPts"]),
                                 (samples[i]["sourcePts"], samples[i + 1]["sourcePts"]))
                expected = Fraction(pair["endPts"] - pair["startPts"]) * timebase
                self.assertEqual(pair["deltaTimeSeconds"], {
                    "numerator": expected.numerator,
                    "denominator": expected.denominator,
                })
                durations.append(expected)
            self.assertIn(Fraction(2, 5), durations)
            self.assertIn(Fraction(1, 10), durations)
            self.assertFalse(result["temporalTracklets"]["semanticIdentityVerified"])
            json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
