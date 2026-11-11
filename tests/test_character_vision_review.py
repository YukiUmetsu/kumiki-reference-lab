"""Local vision quality QA on actual PTS frames, with explicit human verdicts."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.subject_detections import associate_detection_tracklets
from kumiki_reference_lab.pipeline.character_vision_review import (
    build_character_vision_review, summarize_character_vision_feedback,
)


class CharacterVisionReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "clip.mp4"
        self.source.write_bytes(b"synthetic video for mocked decoder")
        self.tracklet_path = self.root / "subject-tracklets.json"
        self.vision_dir = self.root / "vision-run"
        self.vision_dir.mkdir()
        self.out = self.root / "qa-gallery"
        frame_data = {
            "schemaVersion": "kumiki.subject-detections.v1",
            "sourceSha256": "a"*64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "detector": {"name": "synthetic local detector", "modelSha256": None},
            "cutCandidatePts": [],
            "frames": [
                {"sourcePts": i * 1000,
                 "detections": [{"category": "animated-character", "score": 0.92,
                                 "box": [0.15 + .01*i, .1, .3, .6]}]}
                for i in range(3)
            ],
        }
        _, report = associate_detection_tracklets(frame_data)
        self.tracklet_path.write_text(json.dumps(report))
        self.report = report
        self.vision = {
            "schemaVersion": "kumiki.local-character-vision-proposals.v1",
            "sourceSha256": "a"*64,
            "trackletReportSha256": sha256_file(self.tracklet_path),
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "modelTag": "model:8b", "modelCalls": 3,
            "appearanceCount": 3, "actionProposalCount": 2,
            "observations": [
                {"trackletId": "subject_001", "sourcePts": i*1000,
                 "comparisonStartPts": None if i == 0 else (i-1)*1000,
                 "appearance": "Red jacket with dark hair.",
                 "visibleTraits": ["red jacket"],
                 "action": "none" if i == 0 else "waving",
                 "motionEvidence": "" if i == 0 else
                                   "Arm changes position across the two sampled images.",
                 "evidenceStatus": "local-model-proposal-not-reviewed"}
                for i in range(3)
            ],
        }
        self.scene = {
            "schemaVersion": "kumiki.character-scene-review.v1",
            "sourceSha256": "a"*64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "reviewer": {"kind": "model", "id": "local-ollama-vision"},
            "window": {"startPts": 0, "endPts": 2001, "coverage": "partial-window"},
            "characters": [
                {"id": "subject_001", "kind": "animated-human",
                 "label": "Provisional character subject_001",
                 "visualDescription": "Red jacket with dark hair."}],
            "appearances": [
                {"characterId": "subject_001", "startPts": i*1000,
                 "endPts": i*1000+1, "anchorPts": [i*1000],
                 "visibleTraits": ["red jacket"],
                 "anchorBox": report["frames"][i]["proposals"][0]["box"],
                 "observation": "Model proposal from one video sample.",
                 "confidence": "low"}
                for i in range(3)
            ],
            "actions": [
                {"actorId": "subject_001", "targetId": None,
                 "action": "waving", "startPts": (i-1)*1000,
                 "endPts": i*1000+1, "anchorPts": [(i-1)*1000, i*1000],
                 "observation": "Unverified two-frame VLM proposal: arm changes position.",
                 "confidence": "low"} for i in (1, 2)
            ],
            "utterances": [], "identityClaims": [],
        }
        self.save()

    def save(self):
        (self.vision_dir / "character-vision.json").write_text(json.dumps(self.vision))
        (self.vision_dir / "character-scene.json").write_text(json.dumps(self.scene))

    def build(self, *, metadata=None, frames=None):
        metadata = metadata or {
            "source": {"sha256": "a"*64, "fileName": "clip.mp4"},
            "video": {"streamIndex": 0, "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }
        records = frames or [SimpleNamespace(pts=i*1000, ordinal=i) for i in range(3)]
        with (patch("kumiki_reference_lab.pipeline.character_vision_review.inspect_source",
                    return_value=metadata),
              patch("kumiki_reference_lab.pipeline.character_vision_review.read_frame_pts",
                    return_value=records),
              patch("kumiki_reference_lab.pipeline.character_vision_review.read_rgb_frames",
                    side_effect=lambda *args, **kwargs: [
                        b"\x80" * (kwargs["width"]*kwargs["height"]*3)
                        for _ in args[2]])):
            return build_character_vision_review(
                self.source, self.tracklet_path, self.vision_dir, self.out,
                scan_seconds=5, width=160, height=90)

    def test_gallery_has_original_frame_crops_and_pending_feedback(self):
        path = self.build()
        page = path.read_text()
        self.assertIn("Red jacket", page)
        self.assertIn("subject_001", page)
        self.assertIn("waving", page)
        self.assertEqual(len(list((self.out / "frames").glob("frame-*.png"))), 3)
        self.assertEqual(len(list((self.out / "frames").glob("crop-*.png"))), 3)
        self.assertTrue(all(f.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
                            for f in (self.out / "frames").glob("*.png")))
        feedback = json.loads((self.out / "review-feedback.json").read_text())
        self.assertEqual(feedback["observations"][0]["actionVerdict"], "not-applicable")
        self.assertTrue(all(x["appearanceVerdict"] == "pending"
                            for x in feedback["observations"]))
        empty = summarize_character_vision_feedback(
            self.out / "review-feedback.json", self.vision_dir / "character-vision.json")
        self.assertFalse(empty["qualityAssessmentAvailable"])
        self.assertIsNone(empty["appearanceDecidedSupportRate"])
        with self.assertRaisesRegex(ValueError, "must be new"):
            self.build()

    def test_reviewed_support_rates_do_not_count_unclear_or_pending(self):
        self.build()
        feedback_path = self.out / "review-feedback.json"
        feedback = json.loads(feedback_path.read_text())
        feedback["reviewer"]["id"] = "human-reviewer-01"
        feedback["observations"][0]["appearanceVerdict"] = "supported"
        feedback["observations"][1]["appearanceVerdict"] = "unsupported"
        feedback["observations"][1]["actionVerdict"] = "unsupported"
        feedback["observations"][2]["appearanceVerdict"] = "unclear"
        feedback["observations"][2]["actionVerdict"] = "supported"
        feedback_path.write_text(json.dumps(feedback))
        report = summarize_character_vision_feedback(
            feedback_path, self.vision_dir / "character-vision.json")
        self.assertTrue(report["qualityAssessmentAvailable"])
        self.assertEqual(report["appearanceReviewed"], 3)
        self.assertEqual(report["appearanceDecidedSupportRate"], 0.5)
        self.assertEqual(report["actionDecidedSupportRate"], 0.5)
        self.assertEqual(report["actionReviewed"], 2)

    def test_rejects_unattributed_positive_review(self):
        self.build()
        file = self.out / "review-feedback.json"
        feedback = json.loads(file.read_text())
        feedback["observations"][0]["appearanceVerdict"] = "supported"
        file.write_text(json.dumps(feedback))
        with self.assertRaisesRegex(ValueError, "reviewer must be assigned"):
            summarize_character_vision_feedback(file, self.vision_dir / "character-vision.json")

    def test_source_and_manifest_tamper_do_not_publish(self):
        self.vision["trackletReportSha256"] = "f"*64
        self.save()
        with self.assertRaisesRegex(ValueError, "not bound"):
            self.build()
        self.assertFalse(self.out.exists())
        self.vision["trackletReportSha256"] = sha256_file(self.tracklet_path)
        self.vision["observations"][0]["trackletId"] = "subject_999"
        self.save()
        with self.assertRaisesRegex(ValueError, "missing character"):
            self.build()
        self.assertFalse(self.out.exists())

    def test_missing_original_pts_fails(self):
        with self.assertRaisesRegex(ValueError, "source PTS missing or ambiguous"):
            self.build(frames=[SimpleNamespace(pts=0, ordinal=0),
                               SimpleNamespace(pts=2000, ordinal=2)])
        self.assertFalse(self.out.exists())

    def test_escaped_model_text_in_html(self):
        self.vision["observations"][0]["appearance"] = (
            "Red jacket <script>alert('x')</script> dark hair")
        self.scene["characters"][0]["visualDescription"] = (
            self.vision["observations"][0]["appearance"])
        self.save()
        page = self.build().read_text()
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>alert('x')</script>", page)

    def test_invalid_feedback_schema_values(self):
        self.build()
        path = self.out / "review-feedback.json"
        original = json.loads(path.read_text())
        variants = [
            lambda x: x["observations"][1].update(actionVerdict=[]),
            lambda x: x["observations"][0].update(actionVerdict="supported"),
            lambda x: x["observations"][1].update(index=0),
            lambda x: x.update(sourceSha256="f"*64),
            lambda x: x["observations"][1].update(notes="x"*501),
        ]
        for change in variants:
            data = json.loads(json.dumps(original))
            change(data)
            path.write_text(json.dumps(data))
            with self.subTest(change=change), self.assertRaises(ValueError):
                summarize_character_vision_feedback(
                    path, self.vision_dir / "character-vision.json")

    def test_cli_commands(self):
        a = build_parser().parse_args(
            ["review-character-vision", "clip.mp4", "tracklets.json", "vision-dir",
             "--out", "review"])
        self.assertEqual(a.command, "review-character-vision")
        b = build_parser().parse_args([
            "character-vision-feedback", "feedback.json", "character-vision.json"])
        self.assertEqual(b.command, "character-vision-feedback")


if __name__ == "__main__":
    unittest.main()
