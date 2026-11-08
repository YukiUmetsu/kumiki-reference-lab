import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.subjects.roi import analyze_roi_track
from kumiki_reference_lab.analyzers.subjects.template import track_template


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy motion extra unavailable")
class TemplateTrackerTests(unittest.TestCase):
    def test_known_textured_patch_shift(self):
        import numpy as np
        patch = np.random.default_rng(123).integers(0, 255, (18, 24), dtype=np.uint8)
        image = np.zeros((90, 160), dtype=np.uint8)
        image[23:41, 34:58] = patch
        match = track_template(patch.tobytes(), image.tobytes(), 160, 90,
                               24, 18, 30, 20, radius=12)
        self.assertEqual((match["x"], match["y"]), (34, 23))
        self.assertEqual(match["status"], "matched-template")

    def test_flat_patch_is_unobservable(self):
        template = bytes([80] * (16 * 16))
        frame = bytes([80] * (160 * 90))
        result = track_template(template, frame, 160, 90, 16, 16, 20, 20)
        self.assertEqual(result["status"], "unobservable-low-texture")
        self.assertIsNone(result["x"])

    def test_no_matching_patch_does_not_fabricate_tracking(self):
        import numpy as np
        patch = np.random.default_rng(15).integers(0, 255, (16, 16), dtype=np.uint8)
        blank = bytes([80] * (160 * 90))
        result = track_template(patch.tobytes(), blank, 160, 90, 16, 16, 20, 20)
        self.assertEqual(result["status"], "lost-low-correlation")
        self.assertIsNone(result["x"])

    def test_repeated_identical_patches_are_ambiguous(self):
        import numpy as np
        patch = np.random.default_rng(54).integers(0, 255, (16, 16), dtype=np.uint8)
        frame = np.zeros((90, 160), dtype=np.uint8)
        frame[20:36, 30:46] = patch
        frame[20:36, 52:68] = patch
        result = track_template(patch.tobytes(), frame.tobytes(),
                                160, 90, 16, 16, 41, 20, radius=15)
        self.assertEqual(result["status"], "ambiguous-multiple-matches")
        self.assertIsNone(result["x"])

    def test_search_memory_budget_is_checked(self):
        template = bytes([20] * (80 * 45))
        image = bytes([20] * (160 * 90))
        with self.assertRaisesRegex(ValueError, "budget"):
            track_template(template, image, 160, 90, 80, 45, 20, 20, radius=48)


@unittest.skipUnless(importlib.util.find_spec("numpy") and
                     shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "NumPy/FFmpeg test dependencies unavailable")
class RoiIntegrationTests(unittest.TestCase):
    def _make_source(self, output: Path, *, disappear_after: int = 999) -> None:
        import numpy as np
        patch = np.random.default_rng(30).integers(0, 255, (18, 24), dtype=np.uint8)
        frames = []
        for i in range(12):
            image = np.zeros((90, 160), dtype=np.uint8)
            if i < disappear_after:
                x, y = 30 + 2 * i, 20 + i
                image[y:y + 18, x:x + 24] = patch
            frames.append(image.tobytes())
        completed = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "rawvideo", "-pixel_format", "gray", "-video_size", "160x90",
            "-framerate", "10", "-i", "-", "-c:v", "ffv1", str(output),
        ], input=b"".join(frames), capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))

    def test_video_tracks_moving_patch_at_original_pts(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "subject.mkv"
            self._make_source(source)
            report = analyze_roi_track(source, (30/160, 20/90, 24/160, 18/90),
                                       seconds=2, max_samples=12, radius=5, cut_threshold=0.95)
            self.assertEqual(len(report["observations"]), 12)
            self.assertEqual(report["observations"][0]["status"], "seeded")
            for i, frame in enumerate(report["observations"]):
                self.assertEqual(frame["boxPixels"]["x"], 30 + 2 * i)
                self.assertEqual(frame["boxPixels"]["y"], 20 + i)
            self.assertFalse(report["analyzer"]["calibratedConfidence"])
            json.dumps(report, allow_nan=False)

    def test_lost_subject_stays_lost_until_a_new_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "disappearing.mkv"
            self._make_source(source, disappear_after=5)
            report = analyze_roi_track(source, (30/160, 20/90, 24/160, 18/90),
                                       seconds=2, max_samples=12, radius=5, cut_threshold=0.95)
            states = [entry["status"] for entry in report["observations"]]
            self.assertIn("lost-low-correlation", states)
            self.assertEqual(states[-1], "not-tracked-after-loss")
            self.assertIsNone(report["observations"][-1]["boxPixels"])

    def test_rejects_box_outside_image(self):
        with self.assertRaisesRegex(ValueError, "normalized"):
            analyze_roi_track(Path("missing.mkv"), (0.9, 0.1, 0.3, 0.2))

    def test_flat_seed_is_rejected_without_fake_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "flat.mkv"
            completed = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, timeout=30)
            self.assertEqual(completed.returncode, 0)
            with self.assertRaisesRegex(ValueError, "insufficient texture"):
                analyze_roi_track(source, (0.2, 0.2, 0.1, 0.2), seconds=2, max_samples=10)


if __name__ == "__main__":
    unittest.main()
