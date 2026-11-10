import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.subjects.review import build_roi_review
from kumiki_reference_lab.analyzers.subjects.roi import analyze_roi_track
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError


@unittest.skipUnless(importlib.util.find_spec("numpy") and shutil.which("ffmpeg") and
                     shutil.which("ffprobe"), "NumPy/FFmpeg required")
class RoiReviewIntegrationTests(unittest.TestCase):
    def _source_and_report(self, root: Path) -> tuple[Path, Path, dict]:
        import numpy as np
        source = root / "moving.mkv"
        patch = np.random.default_rng(713).integers(0, 255, (18, 24), dtype=np.uint8)
        frames = []
        for index in range(12):
            frame = np.zeros((90, 160), dtype=np.uint8)
            if index not in (4, 5, 6):
                x, y = 30 + 2 * index, 20 + index
                frame[y:y+18, x:x+24] = patch
            frames.append(frame.tobytes())
        process = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "rawvideo", "-pixel_format", "gray", "-video_size", "160x90",
            "-framerate", "10", "-i", "-", "-c:v", "ffv1", str(source),
        ], input=b"".join(frames), capture_output=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
        report = analyze_roi_track(source, (30/160, 20/90, 24/160, 18/90),
                                   seconds=2, max_samples=12, radius=5, cut_threshold=0.95)
        path = root / "roi-track.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return source, path, report

    def test_review_renders_bounded_pts_verified_frames_and_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, report_path, report = self._source_and_report(root)
            index = build_roi_review(source, report_path, root / "reviews", max_frames=8)
            document = index.read_text()
            self.assertIn("ROI observations on original frames", document)
            self.assertIn('x="30.00" y="20.00"', document)
            self.assertIn("not-tracked-after-loss", document)
            self.assertIn("no reported box", document)
            self.assertIn("not independently verified matches", document)
            self.assertNotIn("<script", document)
            manifest = json.loads((index.parent / "roi-review.json").read_text())
            self.assertEqual(manifest["schemaVersion"], "kumiki.roi-review.v1")
            self.assertEqual(manifest["humanReviewStatus"], "unreviewed")
            self.assertEqual(len(manifest["settings"]["selectedFrames"]), 8)
            self.assertIn(report["observations"][4]["sourcePts"],
                          [entry["sourcePts"] for entry in manifest["settings"]["selectedFrames"]])
            self.assertEqual(len(list((index.parent / "frames").glob("*.png"))), 8)
            self.assertEqual(build_roi_review(source, report_path, root / "reviews",
                                              max_frames=8), index)
            (index.parent / "index.html").write_text("corrupt", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "modified|incomplete"):
                build_roi_review(source, report_path, root / "reviews", max_frames=8)

    def test_modified_provenance_and_forged_positions_fail_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, path, report = self._source_and_report(root)
            out = root / "reviews"
            report["sourceSha256"] = "0" * 64
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source does not match"):
                build_roi_review(source, path, out)
            self.assertFalse(out.exists())

            report["sourceSha256"] = analyze_roi_track(
                source, (30/160, 20/90, 24/160, 18/90), seconds=2,
                max_samples=12, cut_threshold=0.95)["sourceSha256"]
            report["observations"][4]["boxPixels"] = {"x": 20, "y": 30, "width": 24, "height": 18}
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unverified position"):
                build_roi_review(source, path, out)
            self.assertFalse(out.exists())

    def test_v2_reseed_segments_are_visually_distinct_and_unlinked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, path, report = self._source_and_report(root)
            report["schemaVersion"] = "kumiki.roi-track.v2"
            anchor = report["observations"][7]
            anchor["status"] = "manual-reseed"
            anchor["boxPixels"] = {"x": 44, "y": 27, "width": 24, "height": 18}
            anchor["boxNormalized"] = {"x": 44/160, "y": 27/90, "width": 24/160, "height": 18/90}
            anchor["displacementPixels"] = {"dx": 0, "dy": 0}
            for entry in report["observations"]:
                entry["segmentIndex"] = (None if entry["boxPixels"] is None else
                                         1 if entry["sourcePts"] >= anchor["sourcePts"] else 0)
            report["analyzer"]["manualReseeds"] = [{"sourcePts": anchor["sourcePts"],
                                                     "box": [44/160, 27/90, 24/160, 18/90]}]
            report["analyzer"]["identityLinkStatus"] = "not-established"
            path.write_text(json.dumps(report), encoding="utf-8")
            index = build_roi_review(source, path, root / "reviews", max_frames=12)
            document = index.read_text()
            self.assertIn("manual-reseed", document)
            self.assertIn("segment 1", document)
            self.assertIn("not verified as the same physical object", document)

    def test_real_reseed_v2_report_is_accepted_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, path, baseline = self._source_and_report(root)
            seed = (30/160, 20/90, 24/160, 18/90)
            anchor_pts = baseline["observations"][7]["sourcePts"]
            result = analyze_roi_track(
                source, seed, seconds=2, max_samples=12, radius=5,
                cut_threshold=0.95,
                reseeds=[{"sourcePts": anchor_pts, "box": [44/160, 27/90, 24/160, 18/90]}])
            self.assertEqual(result["schemaVersion"], "kumiki.roi-track.v2")
            path.write_text(json.dumps(result), encoding="utf-8")
            index = build_roi_review(source, path, root / "reviews", max_frames=12)
            self.assertIn("manual-reseed", index.read_text())
            self.assertIn("segment 1", index.read_text())
            self.assertEqual(json.loads((index.parent / "roi-review.json").read_text())
                             ["settings"]["sourceTrackVersion"], "kumiki.roi-track.v2")

    def test_invalid_limits_are_rejected_before_io(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "max_frames"):
                build_roi_review(root / "missing.mkv", root / "missing.json",
                                 root / "reviews", max_frames=1000)
            self.assertFalse((root / "reviews").exists())

    def test_false_sample_pts_and_inconsistent_manual_anchor_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, path, report = self._source_and_report(root)
            report["observations"][2]["sourcePts"] += 1
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "seconds disagree"):
                build_roi_review(source, path, root / "reviews")

            report["observations"][2]["sourcePts"] -= 1
            report["schemaVersion"] = "kumiki.roi-track.v2"
            anchor = report["observations"][7]
            anchor["status"] = "manual-reseed"
            anchor["boxPixels"] = {"x": 44, "y": 27, "width": 24, "height": 18}
            anchor["boxNormalized"] = {"x": 44/160, "y": 27/90, "width": 24/160, "height": 18/90}
            for obs in report["observations"]:
                obs["segmentIndex"] = (None if obs["boxPixels"] is None else
                                       1 if obs["sourcePts"] >= anchor["sourcePts"] else 0)
            report["analyzer"]["identityLinkStatus"] = "not-established"
            report["analyzer"]["manualReseeds"] = [{"sourcePts": anchor["sourcePts"],
                                                     "box": [0.6, 0.6, 0.15, 0.2]}]
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manual seed box"):
                build_roi_review(source, path, root / "reviews")
            self.assertFalse((root / "reviews").exists())

    def test_extreme_numeric_coordinates_fail_as_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, path, report = self._source_and_report(root)
            report["observations"][0]["boxNormalized"]["x"] = 10**400
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "finite numbers"):
                build_roi_review(source, path, root / "reviews")
            self.assertFalse((root / "reviews").exists())

    def test_failed_decoded_pts_verification_leaves_no_bundle_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, path, report = self._source_and_report(root)
            report["observations"][-1]["sampleOrdinal"] = 1000
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaises((ValueError, ProbeError)):
                build_roi_review(source, path, root / "reviews", max_frames=4)
            self.assertFalse((root / "reviews").exists())

    def test_forged_tracker_displacement_and_impossible_match_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, path, report = self._source_and_report(root)
            report["observations"][1]["displacementPixels"] = {"dx": 0, "dy": 0}
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "displacement"):
                build_roi_review(source, path, root / "reviews")

            report["observations"][1]["displacementPixels"] = {"dx": 2, "dy": 1}
            bad = report["observations"][2]
            bad["boxPixels"]["x"] = 70
            bad["boxNormalized"]["x"] = 70 / 160
            bad["displacementPixels"]["dx"] = 40
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "search radius"):
                build_roi_review(source, path, root / "reviews")
            self.assertFalse((root / "reviews").exists())

    def test_v2_bool_segment_index_is_not_an_integer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, path, report = self._source_and_report(root)
            report["schemaVersion"] = "kumiki.roi-track.v2"
            report["analyzer"]["manualReseeds"] = [{"sourcePts": report["observations"][7]["sourcePts"],
                                                      "box": [44/160, 27/90, 24/160, 18/90]}]
            report["analyzer"]["identityLinkStatus"] = "not-established"
            for obs in report["observations"]:
                obs["segmentIndex"] = 0 if obs["boxPixels"] is not None else None
            report["observations"][0]["segmentIndex"] = False
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "segment index"):
                build_roi_review(source, path, root / "reviews")
            self.assertFalse((root / "reviews").exists())

    def test_unexpected_rational_fields_are_validation_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, path, report = self._source_and_report(root)
            report["observations"][0]["sourceSeconds"]["extra"] = 7
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "seconds"):
                build_roi_review(source, path, root / "reviews")
            self.assertFalse((root / "reviews").exists())
