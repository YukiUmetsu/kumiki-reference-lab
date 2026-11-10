"""Original-PTS visual QA must reject forged box/clock evidence."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.subject_detections import associate_detection_tracklets
from kumiki_reference_lab.pipeline.subject_tracklet_review import (
    _select_indices, _validate_report, build_subject_tracklet_review,
)


class SubjectVisualReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "reference.mp4"
        self.source.write_bytes(b"synthetic local source; probe mocked")
        self.report_path = self.root / "subject-tracklets.json"
        self.out = self.root / "gallery"
        self.data = {
            "schemaVersion": "kumiki.subject-detections.v1",
            "sourceSha256": "a"*64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "detector": {"name": "synthetic-detector", "modelSha256": None},
            "cutCandidatePts": [],
            "frames": [
                {"sourcePts": 0, "detections": [
                    {"category": "person", "score": .85, "box": [.1,.1,.2,.5]}]},
                {"sourcePts": 1000, "detections": [
                    {"category": "person", "score": .84, "box": [.12,.1,.2,.5]}]},
                {"sourcePts": 2000, "detections": [
                    {"category": "person", "score": .83, "box": [.14,.1,.2,.5]}]},
            ],
        }
        self.scene, self.report = associate_detection_tracklets(self.data)
        self.save()

    def save(self):
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")

    @staticmethod
    def metadata(name="reference.mp4"):
        return {
            "source": {"sha256": "a"*64, "fileName": name},
            "video": {"streamIndex": 0, "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }

    @staticmethod
    def frames():
        return [SimpleNamespace(pts=0, ordinal=0),
                SimpleNamespace(pts=1000, ordinal=1),
                SimpleNamespace(pts=2000, ordinal=2)]

    def run_mock(self, *, records=None, metadata=None):
        records = self.frames() if records is None else records
        metadata = self.metadata() if metadata is None else metadata
        with (patch("kumiki_reference_lab.pipeline.subject_tracklet_review.inspect_source",
                    return_value=metadata),
              patch("kumiki_reference_lab.pipeline.subject_tracklet_review.read_frame_pts",
                    return_value=records),
              patch("kumiki_reference_lab.pipeline.subject_tracklet_review.read_rgb_frames",
                    side_effect=lambda *args, **kwargs: [
                        b"\x7f" * (kwargs["width"]*kwargs["height"]*3)
                        for _ in args[2]])):
            return build_subject_tracklet_review(
                self.source, self.report_path, self.out,
                max_frames=3, width=160, height=90)

    def test_actual_source_frame_qa_gallery(self):
        result = self.run_mock()
        self.assertEqual(result, self.out / "index.html")
        page = result.read_text(encoding="utf-8")
        self.assertIn("subject_001", page)
        self.assertIn("Source PTS 1000", page)
        self.assertIn("unverified", page)
        images = sorted((self.out / "frames").glob("*.png"))
        self.assertEqual(len(images), 3)
        self.assertTrue(all(image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
                            for image in images))
        manifest = json.loads((self.out / "subject-visual-review.json").read_text())
        self.assertEqual(len(manifest["inputReportSha256"]), 64)
        self.assertEqual([x["sourcePts"] for x in manifest["frames"]], [0, 1000, 2000])
        with self.assertRaisesRegex(ValueError, "new directory"):
            self.run_mock()

    def test_html_escapes_source_filename(self):
        result = self.run_mock(metadata=self.metadata("<script>alert(1)</script>.mp4"))
        html = result.read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_missing_or_duplicated_pts_abstains(self):
        for records in (
            [SimpleNamespace(pts=0, ordinal=0), SimpleNamespace(pts=1000, ordinal=1)],
            self.frames() + [SimpleNamespace(pts=1000, ordinal=4)],
        ):
            with self.subTest(records=records), self.assertRaisesRegex(
                    ValueError, "PTS missing or ambiguous"):
                self.run_mock(records=records)
            self.assertFalse(self.out.exists())

    def test_report_source_mismatch_refused(self):
        with self.assertRaisesRegex(ValueError, "source hash/clock differs"):
            self.run_mock(metadata=self.metadata("other.mp4") | {
                "source": {"sha256": "f"*64, "fileName": "other.mp4"}})
        self.assertFalse(self.out.exists())

    def test_invalid_external_tracklet_report_refused(self):
        mutations = [
            lambda x: x.update(frameCount=999),
            lambda x: x.update(proposalCount=999),
            lambda x: x["frames"][0]["proposals"][0].update(trackletId="subject_999"),
            lambda x: x["frames"][0]["proposals"][0].update(detectorScore=True),
            lambda x: x["frames"][0]["proposals"][0].update(box=[0.99,0.2,0.5,0.4]),
            lambda x: x["frames"][1].update(sourcePts=0),
            lambda x: x.update(cutCandidatePts=[1500, 1200]),
            lambda x: x["frames"][0]["proposals"][0].update(
                association="<img src=x onerror=alert(1)>"),
        ]
        for mutate in mutations:
            report = copy.deepcopy(self.report)
            mutate(report)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                _validate_report(report)

    def test_select_indices_contains_ends_and_is_bounded(self):
        self.assertEqual(_select_indices(3, 3), [0,1,2])
        chosen = _select_indices(101, 8)
        self.assertEqual(len(chosen), 8)
        self.assertEqual((chosen[0], chosen[-1]), (0,100))
        self.assertEqual(chosen, sorted(set(chosen)))
        self.assertEqual(_select_indices(10, 4, priorities=[6, 5]), [0, 5, 6, 9])

    def test_decode_failure_never_publishes(self):
        with (patch("kumiki_reference_lab.pipeline.subject_tracklet_review.inspect_source",
                    return_value=self.metadata()),
              patch("kumiki_reference_lab.pipeline.subject_tracklet_review.read_frame_pts",
                    return_value=self.frames()),
              patch("kumiki_reference_lab.pipeline.subject_tracklet_review.read_rgb_frames",
                    side_effect=ValueError("bad source frame"))):
            with self.assertRaisesRegex(ValueError, "bad source frame"):
                build_subject_tracklet_review(self.source, self.report_path, self.out)
        self.assertFalse(self.out.exists())

    def test_cli_arguments(self):
        args = build_parser().parse_args([
            "review-subject-tracklets", "clip.mp4", "subject-tracklets.json",
            "--out", "review/gallery", "--max-frames", "10"])
        self.assertEqual(args.command, "review-subject-tracklets")
        self.assertEqual(args.max_frames, 10)


if __name__ == "__main__":
    unittest.main()
