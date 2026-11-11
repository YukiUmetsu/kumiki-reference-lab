"""Explicit interaction evidence QA with no invented semantic approvals."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.subject_detections import associate_detection_tracklets
from kumiki_reference_lab.pipeline.interaction_review import (
    build_interaction_review, summarize_interaction_feedback,
)


class InteractionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "local-video.mp4"
        self.source.write_bytes(b"synthetic source; real decoder mocked")
        self.report_path = self.root / "tracklets.json"
        self.vision_dir = self.root / "vision"
        self.vision_dir.mkdir()
        self.interaction_dir = self.root / "interactions"
        self.interaction_dir.mkdir()
        self.out = self.root / "qa"
        detector = {
            "schemaVersion": "kumiki.subject-detections.v1",
            "sourceSha256": "a"*64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "detector": {"name": "synthetic detector", "modelSha256": None},
            "cutCandidatePts": [],
            "frames": [
                {"sourcePts": i * 1000, "detections": [
                    {"category": "animated-character", "score": .9,
                     "box": [.10 + i*.01, .2, .23, .5]},
                    {"category": "animated-character", "score": .91,
                     "box": [.62 - i*.01, .2, .23, .5]},
                ]} for i in range(3)
            ],
        }
        _, self.tracklets = associate_detection_tracklets(detector)
        self.report_path.write_text(json.dumps(self.tracklets))
        descriptors = {
            "subject_001": ("Red jacket, short dark hair.", ["red jacket"]),
            "subject_002": ("Blue coat and yellow scarf.", ["blue coat"]),
        }
        self.base = {
            "schemaVersion": "kumiki.character-scene-review.v1",
            "sourceSha256": "a"*64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "reviewer": {"kind": "model", "id": "local-ollama-vision"},
            "window": {"startPts": 0, "endPts": 2001, "coverage": "partial-window"},
            "characters": [
                {"id": cid, "kind": "animated-human", "label": f"Provisional {cid}",
                 "visualDescription": desc}
                for cid, (desc, _) in descriptors.items()
            ],
            "appearances": [], "actions": [], "utterances": [], "identityClaims": [],
        }
        observations = []
        for frame in self.tracklets["frames"]:
            for box in frame["proposals"]:
                cid = box["trackletId"]
                desc, traits = descriptors[cid]
                pts = frame["sourcePts"]
                self.base["appearances"].append({
                    "characterId": cid, "startPts": pts, "endPts": pts+1,
                    "anchorPts": [pts], "anchorBox": box["box"],
                    "visibleTraits": traits,
                    "observation": "Local VLM-proposed appearance at one decoded source frame; not verified.",
                    "confidence": "low",
                })
                observations.append({
                    "trackletId": cid, "sourcePts": pts, "comparisonStartPts": None,
                    "appearance": desc, "visibleTraits": traits,
                    "action": "none", "motionEvidence": "",
                    "evidenceStatus": "local-model-proposal-not-reviewed",
                })
        self.vision = {
            "schemaVersion": "kumiki.local-character-vision-proposals.v1",
            "sourceSha256": "a"*64,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "modelCalls": 6, "appearanceCount": 6, "actionProposalCount": 0,
            "trackletReportSha256": sha256_file(self.report_path),
            "modelDigestVerified": False, "observations": observations,
        }
        self.merged = copy.deepcopy(self.base)
        self.merged["actions"] = [{
            "actorId": "subject_001", "targetId": "subject_002",
            "action": "reaching-toward", "startPts": 0, "endPts": 1001,
            "anchorPts": [0, 1000],
            "observation": "Unverified local VLM two-frame interaction: "
                           "Red boxed character reaches toward cyan character.",
            "confidence": "low",
        }]
        self.manifest = {
            "schemaVersion": "kumiki.local-character-interactions.v1",
            "sourceSha256": "a"*64,
            "trackletReportSha256": sha256_file(self.report_path),
            "modelDigestVerified": False,
            "maxPairGapSeconds": 3, "renderWidth": 160, "renderHeight": 90,
            "scanSeconds": 10,
            "pairOrdering": "sorted-tracklet-ids-first-red-second-cyan",
            "candidatePairs": 2, "actionProposals": 1,
            "pairDecisions": [
                {"startPts": 0, "endPts": 1000,
                 "redId": "subject_001", "cyanId": "subject_002",
                 "actorColor": "red", "interaction": "reaching-toward",
                 "visualEvidence": "Red boxed character reaches toward cyan character.",
                 "status": "unreviewed-interaction-hypothesis"},
                {"startPts": 1000, "endPts": 2000,
                 "redId": "subject_001", "cyanId": "subject_002",
                 "actorColor": "none", "interaction": "none",
                 "visualEvidence": "", "status": "unreviewed-interaction-hypothesis"},
            ],
        }
        self.save()

    def save(self):
        (self.vision_dir / "character-scene.json").write_text(json.dumps(self.base))
        (self.vision_dir / "character-vision.json").write_text(json.dumps(self.vision))
        (self.interaction_dir / "character-scene.json").write_text(json.dumps(self.merged))
        self.manifest["baseSceneSha256"] = sha256_file(
            self.vision_dir / "character-scene.json")
        (self.interaction_dir / "character-interactions.json").write_text(
            json.dumps(self.manifest))

    def run_mock(self, *, frames=None, metadata=None):
        records = frames if frames is not None else [
            SimpleNamespace(pts=i*1000, ordinal=i) for i in range(3)]
        metadata = metadata if metadata is not None else {
            "source": {"sha256": "a"*64, "fileName": "local-video.mp4"},
            "video": {"streamIndex": 0,
                      "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }
        with (patch("kumiki_reference_lab.pipeline.interaction_review.inspect_source",
                    return_value=metadata),
              patch("kumiki_reference_lab.pipeline.interaction_review.read_frame_pts",
                    return_value=records),
              patch("kumiki_reference_lab.pipeline.interaction_review.read_rgb_frames",
                    side_effect=lambda *args, **kwargs: [
                        b"\x72"*(kwargs["width"]*kwargs["height"]*3)
                        for _ in args[2]])):
            return build_interaction_review(
                self.source, self.report_path, self.vision_dir,
                self.interaction_dir, self.out)

    def test_verified_source_gallery_and_pending_feedback(self):
        path = self.run_mock()
        page = path.read_text(encoding="utf-8")
        self.assertIn("subject_001", page)
        self.assertIn("reaching-toward", page)
        self.assertIn("No proposed interaction", page)
        self.assertEqual(len(list((self.out / "frames").glob("*.png"))), 4)
        self.assertTrue(all(
            f.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
            for f in (self.out / "frames").glob("*.png")
        ))
        feedback = json.loads((self.out / "interaction-feedback.json").read_text())
        self.assertEqual([x["verdict"] for x in feedback["pairs"]], ["pending", "pending"])
        metrics = summarize_interaction_feedback(
            self.out / "interaction-feedback.json",
            self.interaction_dir / "character-interactions.json")
        self.assertFalse(metrics["hasAnyHumanReview"])
        self.assertIsNone(metrics["positiveProposalSupportRate"])
        self.assertIsNone(metrics["abstentionSupportRate"])
        with self.assertRaisesRegex(ValueError, "must be new"):
            self.run_mock()

    def test_human_support_and_abstention_scores_are_separate(self):
        self.run_mock()
        path = self.out / "interaction-feedback.json"
        feedback = json.loads(path.read_text())
        feedback["reviewer"]["id"] = "annotator-01"
        feedback["pairs"][0]["verdict"] = "supported"
        feedback["pairs"][1]["verdict"] = "unsupported"
        path.write_text(json.dumps(feedback))
        metrics = summarize_interaction_feedback(
            path, self.interaction_dir / "character-interactions.json")
        self.assertTrue(metrics["hasAnyHumanReview"])
        self.assertEqual(metrics["proposedInteractionCount"], 1)
        self.assertEqual(metrics["abstentionCount"], 1)
        self.assertEqual(metrics["positiveProposalSupportRate"], 1.0)
        self.assertEqual(metrics["abstentionSupportRate"], 0.0)
        self.assertEqual(metrics["reviewedInteractionCount"], 1)
        self.assertEqual(metrics["reviewedAbstentionCount"], 1)

    def test_rejects_positive_review_by_unassigned_reviewer(self):
        self.run_mock()
        path = self.out / "interaction-feedback.json"
        feedback = json.loads(path.read_text())
        feedback["pairs"][0]["verdict"] = "supported"
        path.write_text(json.dumps(feedback))
        with self.assertRaisesRegex(ValueError, "assign a reviewer"):
            summarize_interaction_feedback(
                path, self.interaction_dir / "character-interactions.json")

    def test_inconsistent_source_hash_or_action_fails_closed(self):
        self.manifest["trackletReportSha256"] = "f"*64
        self.save()
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            self.run_mock()
        self.assertFalse(self.out.exists())

        self.manifest["trackletReportSha256"] = sha256_file(self.report_path)
        self.merged["actions"][0]["targetId"] = "subject_001"
        self.save()
        with self.assertRaises(ValueError):
            self.run_mock()
        self.assertFalse(self.out.exists())

    def test_missing_or_duplicate_source_pts_rejected(self):
        with self.assertRaisesRegex(ValueError, "PTS missing or ambiguous"):
            self.run_mock(frames=[
                SimpleNamespace(pts=0, ordinal=0),
                SimpleNamespace(pts=2000, ordinal=2),
            ])
        self.assertFalse(self.out.exists())
        with self.assertRaisesRegex(ValueError, "PTS missing or ambiguous"):
            self.run_mock(frames=[
                SimpleNamespace(pts=0, ordinal=0),
                SimpleNamespace(pts=1000, ordinal=1),
                SimpleNamespace(pts=1000, ordinal=5),
                SimpleNamespace(pts=2000, ordinal=2),
            ])
        self.assertFalse(self.out.exists())

    def test_model_text_is_escaped(self):
        text = "Red boxed subject moves <script>alert(1)</script> toward cyan."
        self.manifest["pairDecisions"][0]["visualEvidence"] = text
        self.merged["actions"][0]["observation"] = (
            "Unverified local VLM two-frame interaction: " + text)
        self.save()
        page = self.run_mock().read_text()
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>alert(1)</script>", page)

    def test_cut_and_missing_subject_boxes_never_create_positive_review(self):
        self.tracklets["cutCandidatePts"] = [500]
        self.report_path.write_text(json.dumps(self.tracklets))
        self.vision["trackletReportSha256"] = sha256_file(self.report_path)
        self.manifest["trackletReportSha256"] = sha256_file(self.report_path)
        self.save()
        with self.assertRaisesRegex(ValueError, "crosses cut"):
            self.run_mock()
        self.assertFalse(self.out.exists())

    def test_feedback_rejects_invalid_verdicts_and_modified_manifest(self):
        self.run_mock()
        file = self.out / "interaction-feedback.json"
        initial = json.loads(file.read_text())
        for edit in (
            lambda x: x["pairs"][0].update(verdict=[]),
            lambda x: x["pairs"][0].update(index=True),
            lambda x: x["pairs"][0].update(index=1),
            lambda x: x["pairs"][1].update(notes="x"*501),
            lambda x: x.update(sourceSha256="f"*64),
        ):
            data = copy.deepcopy(initial)
            edit(data)
            file.write_text(json.dumps(data))
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                summarize_interaction_feedback(
                    file, self.interaction_dir / "character-interactions.json")

    def test_cli_parses_both_commands(self):
        args = build_parser().parse_args([
            "review-character-interactions", "film.mp4", "tracklets.json",
            "vision-run", "interaction-run", "--out", "review"])
        self.assertEqual(args.command, "review-character-interactions")
        args = build_parser().parse_args([
            "character-interaction-feedback", "feedback.json", "interactions.json"])
        self.assertEqual(args.command, "character-interaction-feedback")


if __name__ == "__main__":
    unittest.main()
