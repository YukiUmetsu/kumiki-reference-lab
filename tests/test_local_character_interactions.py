"""Conservative pairwise VLM proposals with source-bound actor/target IDs."""
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
from kumiki_reference_lab.pipeline.local_character_interactions import (
    _outline, _parse_response, analyze_local_interactions,
)
from kumiki_reference_lab.reviews.character_scene import load_character_scene


class LocalInteractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "film.mp4"
        self.source.write_bytes(b"synthetic test clip; decoder mocked")
        self.tracklet_path = self.root / "tracklets.json"
        self.vision_run = self.root / "vision"
        self.vision_run.mkdir()
        self.out = self.root / "interaction-output"
        self.detections = {
            "schemaVersion": "kumiki.subject-detections.v1",
            "sourceSha256": "a"*64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "detector": {"name": "synthetic local detector", "modelSha256": None},
            "cutCandidatePts": [],
            "frames": [
                {"sourcePts": i*1000, "detections": [
                    {"category": "animated-character", "score": .9,
                     "box": [0.1+i*.02,.1,.22,.55]},
                    {"category": "animated-character", "score": .9,
                     "box": [0.6-i*.02,.1,.22,.55]},
                ]} for i in range(3)
            ],
        }
        self.prepare()

    def prepare(self):
        _, self.report = associate_detection_tracklets(self.detections)
        self.tracklet_path.write_text(json.dumps(self.report))
        self.scene = {
            "schemaVersion": "kumiki.character-scene-review.v1",
            "sourceSha256": "a"*64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "reviewer": {"kind": "model", "id": "local-ollama-vision"},
            "window": {"startPts": 0, "endPts": 2001, "coverage": "partial-window"},
            "characters": [
                {"id": "subject_001", "kind": "animated-human",
                 "label": "First provisional character",
                 "visualDescription": "Red jacket with dark hair."},
                {"id": "subject_002", "kind": "animated-human",
                 "label": "Second provisional character",
                 "visualDescription": "Blue outfit and long scarf."},
            ],
            "appearances": [], "actions": [
                {"actorId": "subject_001", "targetId": None,
                 "action": "turning", "startPts": 0, "endPts": 1001,
                 "anchorPts": [0, 1000],
                 "observation": "Unverified two-frame turning observation.",
                 "confidence": "low"}
            ],
            "utterances": [], "identityClaims": [],
        }
        self.manifest = {
            "schemaVersion": "kumiki.local-character-vision-proposals.v1",
            "sourceSha256": "a"*64,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "trackletReportSha256": sha256_file(self.tracklet_path),
            "modelDigestVerified": False,
            "modelTag": "local-vision:8b",
        }
        (self.vision_run / "character-scene.json").write_text(json.dumps(self.scene))
        (self.vision_run / "character-vision.json").write_text(json.dumps(self.manifest))

    def run_mock(self, *, decision=None, meta=None):
        meta = meta or {
            "source": {"sha256": "a"*64},
            "video": {"streamIndex": 0, "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }
        decision = decision or {
            "actorColor": "red", "interaction": "reaching-toward",
            "visualEvidence": "Red subject extends its arm toward the cyan subject.",
        }
        with (patch("kumiki_reference_lab.pipeline.local_character_interactions.inspect_source",
                    return_value=meta),
              patch("kumiki_reference_lab.pipeline.local_character_interactions.read_frame_pts",
                    return_value=[SimpleNamespace(pts=i*1000, ordinal=i) for i in range(3)]),
              patch("kumiki_reference_lab.pipeline.local_character_interactions.read_rgb_frames",
                    side_effect=lambda *args, **kwargs: [
                        b"\x70" * (kwargs["width"]*kwargs["height"]*3)
                        for _ in args[2]]),
              patch("kumiki_reference_lab.pipeline.local_character_interactions._ollama_json",
                    return_value=decision) as call):
            path = analyze_local_interactions(
                self.source, self.tracklet_path, self.vision_run, self.out,
                model="local-vision:8b", width=160, height=90)
        return path, call.call_count

    def test_two_synchronized_characters_give_unreviewed_directed_actions(self):
        path, calls = self.run_mock()
        result = load_character_scene(path)
        self.assertEqual(calls, 2)
        self.assertEqual(len(result["actions"]), 3)  # base action remains intact
        self.assertEqual(result["actions"][0]["targetId"], None)
        self.assertEqual([x["targetId"] for x in result["actions"][1:]],
                         ["subject_002", "subject_002"])
        self.assertTrue(all(x["confidence"] == "low" for x in result["actions"][1:]))
        self.assertEqual(result["utterances"], [])
        self.assertEqual(result["identityClaims"], [])
        report = json.loads((self.out / "character-interactions.json").read_text())
        self.assertEqual(report["candidatePairs"], 2)
        self.assertEqual(report["actionProposals"], 2)
        self.assertFalse(report["modelDigestVerified"])
        with self.assertRaisesRegex(ValueError, "nonexisting"):
            self.run_mock()

    def test_model_can_abstain_without_fabricated_target(self):
        path, calls = self.run_mock(decision={
            "actorColor": "none", "interaction": "none", "visualEvidence": ""})
        scene = load_character_scene(path)
        self.assertEqual(len(scene["actions"]), 1)
        self.assertEqual(calls, 2)
        self.assertEqual(json.loads((self.out / "character-interactions.json").read_text())
                         ["actionProposals"], 0)

    def test_cut_never_bridges_unrelated_tracklets(self):
        self.detections["cutCandidatePts"] = [500]
        self.prepare()
        path, calls = self.run_mock()
        self.assertEqual(calls, 1)  # only pair after the cut can be considered
        scene = load_character_scene(path)
        self.assertEqual(scene["actions"][-1]["startPts"], 1000)

    def test_model_error_never_publishes(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.run_mock(decision={"actorColor": "red",
                                    "interaction": "I know their identity",
                                    "visualEvidence": "no source evidence"})
        self.assertFalse(self.out.exists())

    def test_reject_wrong_source_manifest_and_no_output(self):
        self.manifest["trackletReportSha256"] = "b"*64
        (self.vision_run / "character-vision.json").write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.run_mock()
        self.assertFalse(self.out.exists())

    def test_overlay_and_response_evidence_guards(self):
        image = _outline(b"\x80"*160*90*3, 160, 90,
                         [0.1,.1,.2,.3], [0.5,.1,.2,.3])
        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))
        with self.assertRaisesRegex(ValueError, "demographic"):
            _parse_response({"actorColor": "red", "interaction": "touching",
                             "visualEvidence": "An Asian woman touches another character."})
        with self.assertRaisesRegex(ValueError, "abstaining"):
            _parse_response({"actorColor": "red", "interaction": "none", "visualEvidence": ""})
        with self.assertRaisesRegex(ValueError, "concrete"):
            _parse_response({"actorColor": "red", "interaction": "touching", "visualEvidence": ""})

    def test_cli_and_budget_validation(self):
        args = build_parser().parse_args([
            "local-character-interactions", "film.mp4", "tracklets.json",
            "vision-dir", "--model", "model:8b", "--out", "interactions"])
        self.assertEqual(args.command, "local-character-interactions")
        for invalid in ({"max_pairs": 20}, {"gap_seconds": 8},
                        {"model": "../invalid"}, {"port": False}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                analyze_local_interactions(
                    self.source, self.tracklet_path, self.vision_run, self.out,
                    **{"model": "model:8b", **invalid})


if __name__ == "__main__":
    unittest.main()
