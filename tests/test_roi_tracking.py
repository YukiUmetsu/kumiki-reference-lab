import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from fractions import Fraction
from unittest.mock import patch as mock_patch

from kumiki_reference_lab.analyzers.subjects.roi import analyze_roi_track
from kumiki_reference_lab.analyzers.subjects.template import track_template
from kumiki_reference_lab.contracts.analysis import ROI_TRACK_VERSION, ROI_TRACK_RESEED_VERSION
from kumiki_reference_lab.backends.ffmpeg.scene import CutScan


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
    def _make_source(self, output: Path, *, disappear_after: int = 999,
                     hidden_range: tuple[int, int] | None = None,
                     vfr: bool = False) -> None:
        import numpy as np
        patch = np.random.default_rng(30).integers(0, 255, (18, 24), dtype=np.uint8)
        frames = []
        for i in range(12):
            image = np.zeros((90, 160), dtype=np.uint8)
            if i < disappear_after and not (hidden_range and hidden_range[0] <= i < hidden_range[1]):
                x, y = 30 + 2 * i, 20 + i
                image[y:y + 18, x:x + 24] = patch
            frames.append(image.tobytes())
        args = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "rawvideo", "-pixel_format", "gray", "-video_size", "160x90",
            "-framerate", "10", "-i", "-",
        ]
        if vfr:
            args += ["-vf", "setpts='if(lt(N,5),N,N*2)/(10*TB)'", "-fps_mode", "vfr"]
        args += ["-c:v", "ffv1", str(output)]
        completed = subprocess.run(args, input=b"".join(frames), capture_output=True, timeout=30)
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

    def test_manual_reseed_starts_new_unlinked_segment_after_occlusion(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "occluded.mkv"
            self._make_source(source, hidden_range=(4, 7))
            seed = (30/160, 20/90, 24/160, 18/90)
            initial = analyze_roi_track(source, seed, seconds=2, max_samples=12,
                                        radius=5, cut_threshold=0.95)
            resume_pts = initial["observations"][7]["sourcePts"]
            report = analyze_roi_track(
                source, seed, seconds=2, max_samples=12, radius=5, cut_threshold=0.95,
                reseeds=[{"sourcePts": resume_pts,
                          "box": [44/160, 27/90, 24/160, 18/90]}])
            observations = report["observations"]
            self.assertEqual(observations[0]["segmentIndex"], 0)
            self.assertIn("lost-low-correlation", [o["status"] for o in observations[4:7]])
            self.assertTrue(all(o["boxPixels"] is None for o in observations[4:7]))
            self.assertTrue(all(o["segmentIndex"] is None for o in observations[4:7]))
            self.assertEqual(observations[7]["status"], "manual-reseed")
            self.assertEqual(observations[7]["segmentIndex"], 1)
            self.assertEqual(observations[7]["boxPixels"]["x"], 44)
            self.assertEqual(observations[7]["displacementPixels"], {"dx": 0, "dy": 0})
            self.assertEqual(observations[8]["status"], "matched-template")
            self.assertEqual(observations[8]["boxPixels"]["x"], 46)
            self.assertEqual(observations[8]["displacementPixels"], {"dx": 2, "dy": 1})
            self.assertEqual(report["analyzer"]["manualReseeds"][0]["sourcePts"], resume_pts)
            self.assertEqual(report["analyzer"]["identityLinkStatus"], "not-established")
            self.assertEqual(report["schemaVersion"], ROI_TRACK_RESEED_VERSION)
            self.assertEqual(initial["schemaVersion"], ROI_TRACK_VERSION)
            self.assertNotIn("manualReseeds", initial["analyzer"])
            self.assertNotIn("segmentIndex", initial["observations"][0])
            json.dumps(report, allow_nan=False)

    def test_reseed_requires_existing_sample_pts_after_start(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "subject.mkv"
            self._make_source(source)
            seed = (30/160, 20/90, 24/160, 18/90)
            initial = analyze_roi_track(source, seed, seconds=2, max_samples=8,
                                        radius=5, cut_threshold=0.95)
            pts = [o["sourcePts"] for o in initial["observations"]]
            missing = next(p for p in range(pts[0]+1, pts[-1]) if p not in pts)
            with self.assertRaisesRegex(ValueError, "sampled sourcePts"):
                analyze_roi_track(source, seed, seconds=2, max_samples=8,
                                  reseeds=[{"sourcePts": missing, "box": list(seed)}])
            with self.assertRaisesRegex(ValueError, "first sampled"):
                analyze_roi_track(source, seed, seconds=2, max_samples=8,
                                  reseeds=[{"sourcePts": pts[0], "box": list(seed)}])

    def test_reseed_rejects_untextured_and_invalid_boxes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "occluded.mkv"
            self._make_source(source, hidden_range=(4, 7))
            seed = (30/160, 20/90, 24/160, 18/90)
            pts = analyze_roi_track(source, seed, seconds=2, max_samples=12,
                                    radius=5, cut_threshold=0.95)["observations"]
            with self.assertRaisesRegex(ValueError, "insufficient texture"):
                analyze_roi_track(source, seed, seconds=2, max_samples=12,
                                  reseeds=[{"sourcePts": pts[5]["sourcePts"], "box": list(seed)}])
            for invalid in ([{"sourcePts": pts[7]["sourcePts"], "box": [0.9, 0.1, 0.3, 0.2]}],
                            [{"sourcePts": True, "box": list(seed)}],
                            [{"sourcePts": pts[7]["sourcePts"], "box": list(seed), "extra": 1}],
                            [{"sourcePts": pts[8]["sourcePts"], "box": list(seed)},
                             {"sourcePts": pts[7]["sourcePts"], "box": list(seed)}]):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    analyze_roi_track(source, seed, seconds=2, max_samples=12, reseeds=invalid)

    def test_vfr_reseed_preserves_exact_pts_and_skipped_time(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "vfr.mkv"
            self._make_source(source, hidden_range=(4, 7), vfr=True)
            seed = (30/160, 20/90, 24/160, 18/90)
            baseline = analyze_roi_track(source, seed, seconds=3, max_samples=12,
                                         radius=5, cut_threshold=0.95)
            pts = baseline["observations"][7]["sourcePts"]
            report = analyze_roi_track(
                source, seed, seconds=3, max_samples=12, radius=5,
                cut_threshold=0.95,
                reseeds=[{"sourcePts": pts, "box": [44/160, 27/90, 24/160, 18/90]}])
            self.assertEqual(report["observations"][7]["sourcePts"], pts)
            self.assertEqual(report["observations"][7]["sourceSeconds"], baseline["observations"][7]["sourceSeconds"])
            self.assertGreater(pts - report["observations"][6]["sourcePts"],
                               report["observations"][2]["sourcePts"] - report["observations"][1]["sourcePts"])
            self.assertEqual(report["observations"][7]["status"], "manual-reseed")

    def test_manual_reseed_after_cut_does_not_match_across_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "cut.mkv"
            self._make_source(source)
            seed = (30/160, 20/90, 24/160, 18/90)
            baseline = analyze_roi_track(source, seed, seconds=2, max_samples=12,
                                         radius=5, cut_threshold=0.95)
            observations = baseline["observations"]
            rational = baseline["sourceTimebase"]
            cut_scan = CutScan(Fraction(rational["numerator"], rational["denominator"]),
                               (observations[4]["sourcePts"],))
            with mock_patch("kumiki_reference_lab.analyzers.subjects.roi.detect_hard_cut_pts",
                            return_value=cut_scan):
                result = analyze_roi_track(
                    source, seed, seconds=2, max_samples=12, radius=5,
                    reseeds=[{"sourcePts": observations[7]["sourcePts"],
                              "box": [44/160, 27/90, 24/160, 18/90]}])
            self.assertEqual(result["observations"][4]["status"], "cut-boundary")
            self.assertEqual(result["observations"][6]["status"], "not-tracked-after-cut")
            self.assertEqual(result["observations"][7]["status"], "manual-reseed")
            self.assertEqual(result["observations"][8]["status"], "matched-template")

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
