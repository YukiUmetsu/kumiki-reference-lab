"""Atomic one-command character analysis orchestration with only local, mocked stages."""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.local_character_study import run_local_character_study


class LocalCharacterStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "authorized.mp4"
        self.source.write_bytes(b"synthetic film for mocked stages")
        self.out = self.root / "studied-characters"
        self.calls = []
        self.number_of_characters = 2
        self.failure_stage = None

    def _maybe_fail(self, stage):
        self.calls.append(stage)
        if self.failure_stage == stage:
            raise ValueError("mock stage failed: " + stage)

    def _detect(self, source, path, **kwargs):
        self._maybe_fail("detect")
        path.parent.mkdir(parents=True, exist_ok=True)
        boxes = [
            {"category": "animated-character", "score": 0.5,
             "box": [0.10 + index*0.40, 0.2, 0.25, 0.5]}
            for index in range(self.number_of_characters)
        ]
        path.write_text(json.dumps({
            "schemaVersion": "kumiki.subject-detections.v1",
            "sourceSha256": "a"*64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "detector": {"name": "mock-local-model", "modelSha256": None},
            "cutCandidatePts": [],
            "frames": [
                {"sourcePts": 0, "detections": boxes},
                {"sourcePts": 1000, "detections": boxes},
            ],
        }))
        return path

    def _tracks(self, source, boxes, directory, **kwargs):
        self._maybe_fail("tracks")
        directory.mkdir()
        path = directory / "subject-tracklets.json"
        path.write_text(json.dumps({"trackletCount": self.number_of_characters}))
        return path

    def _vision(self, source, tracks, directory, **kwargs):
        self._maybe_fail("vision")
        directory.mkdir()
        people = [
            {"id": f"subject_{i+1:03d}", "kind": "animated-human",
             "label": f"Provisional character {i+1}",
             "visualDescription": "Animated figure wearing a brightly colored jacket."}
            for i in range(self.number_of_characters)
        ]
        scene = {
            "schemaVersion": "kumiki.character-scene-review.v1",
            "sourceSha256": "a"*64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "reviewer": {"kind": "model", "id": "mock-local-vision"},
            "window": {"startPts": 0, "endPts": 1001, "coverage": "partial-window"},
            "characters": people,
            "appearances": [
                {"characterId": c["id"], "startPts": 0, "endPts": 1,
                 "anchorPts": [0], "anchorBox": [0.1,0.2,0.2,0.4],
                 "visibleTraits": [], "observation": "Mock observed image region.",
                 "confidence": "low"} for c in people
            ],
            "actions": [], "utterances": [], "identityClaims": [],
        }
        (directory / "character-scene.json").write_text(json.dumps(scene))
        (directory / "character-vision.json").write_text("{}")
        return directory / "character-scene.json"

    def _interaction(self, source, report, vision, directory, **kwargs):
        self._maybe_fail("interactions")
        directory.mkdir()
        (directory / "character-scene.json").write_text("{}")
        (directory / "character-interactions.json").write_text("{}")
        return directory / "character-scene.json"

    def _qa(self, stage, directory):
        self._maybe_fail(stage)
        directory.mkdir()
        (directory / "index.html").write_text("<p>mock QA</p>")
        return directory / "index.html"

    def run_mock(self, *, detector="ollama", review=True, interactions=True):
        with ExitStack() as stack:
            for name, function in (
                ("detect_local_ollama_subjects", self._detect),
                ("detect_mac_vision_people", self._detect),
                ("run_subject_detections", self._tracks),
                ("describe_local_characters", self._vision),
                ("analyze_local_interactions", self._interaction),
                ("build_subject_tracklet_review",
                 lambda src, track, directory, **kw: self._qa("tracklet-qa", directory)),
                ("build_character_vision_review",
                 lambda src, track, vision, directory, **kw: self._qa("character-qa", directory)),
                ("build_interaction_review",
                 lambda src, track, vision, interactions_dir, directory, **kw:
                 self._qa("interaction-qa", directory)),
            ):
                stack.enter_context(patch(
                    "kumiki_reference_lab.pipeline.local_character_study." + name,
                    side_effect=function))
            return run_local_character_study(
                self.source, self.out, model="local-model:8b", detector=detector,
                max_seconds=10, max_samples=8, max_calls=8, max_pairs=6,
                review=review, interactions=interactions)

    def test_complete_workflow_is_atomic_and_source_grounded(self):
        manifest_path = self.run_mock()
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(self.calls, [
            "detect", "tracks", "tracklet-qa", "vision",
            "character-qa", "interactions", "interaction-qa",
        ])
        self.assertEqual(manifest["sourceSha256"], "a"*64)
        self.assertEqual(manifest["detectedRegionProposals"], 4)
        self.assertEqual(manifest["provisionalTracklets"], 2)
        self.assertEqual(manifest["provisionalCharacterIdsObserved"], 2)
        self.assertEqual(manifest["visionAppearanceProposals"], 2)
        self.assertEqual(manifest["detectorBackend"], "ollama")
        self.assertEqual(manifest["status"], "completed-unverified-model-proposals")
        for relative in manifest["paths"].values():
            if relative is not None:
                self.assertTrue((self.out / relative).is_file(), relative)
        with self.assertRaisesRegex(ValueError, "nonexisting directory"):
            self.run_mock()

    def test_detector_can_use_apple_vision_without_any_remote_source(self):
        result = self.run_mock(detector="apple-vision")
        data = json.loads(result.read_text())
        self.assertEqual(data["detectorBackend"], "apple-vision")
        self.assertIn("detect", self.calls)

    def test_skip_qa_and_interactions(self):
        result = self.run_mock(review=False, interactions=False)
        data = json.loads(result.read_text())
        self.assertEqual(self.calls, ["detect", "tracks", "vision"])
        self.assertIsNone(data["paths"]["trackletQa"])
        self.assertIsNone(data["paths"]["characterQa"])
        self.assertIsNone(data["paths"]["interactions"])

    def test_no_detected_characters_does_not_invent_semantics(self):
        self.number_of_characters = 0
        result = self.run_mock()
        data = json.loads(result.read_text())
        self.assertEqual(data["provisionalCharacterIdsObserved"], 0)
        self.assertEqual(data["detectedRegionProposals"], 0)
        self.assertEqual(self.calls, ["detect", "tracks", "tracklet-qa", "vision"])
        self.assertIsNone(data["paths"]["characterQa"])
        self.assertIsNone(data["paths"]["interactionQa"])
        self.assertIsNone(data["paths"]["interactions"])

    def test_stage_failure_does_not_publish_partially_completed_study(self):
        for stage in ("detect", "tracks", "tracklet-qa", "vision",
                      "character-qa", "interactions", "interaction-qa"):
            self.calls = []
            self.failure_stage = stage
            with self.subTest(stage=stage), self.assertRaisesRegex(
                    ValueError, "mock stage failed"):
                self.run_mock()
            self.assertFalse(self.out.exists())
        self.failure_stage = None

    def test_rejects_unsafe_configuration_before_running(self):
        cases = [
            {"max_samples": 2}, {"max_seconds": 60}, {"max_calls": 40},
            {"max_pairs": 13}, {"model": "../weird"}, {"detector": "cloud"},
            {"port": False}, {"review": None}, {"width": 800},
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                run_local_character_study(
                    self.source, self.out, **{"model": "local-model:8b", **args})
        self.assertEqual(self.calls, [])
        self.assertFalse(self.out.exists())

    def test_cli(self):
        args = build_parser().parse_args([
            "character-study-local", "film.mp4", "--model", "vision:8b",
            "--out", "runs/characters", "--detector", "ollama",
            "--skip-interactions"])
        self.assertEqual(args.command, "character-study-local")
        self.assertEqual(args.model, "vision:8b")
        self.assertTrue(args.skip_interactions)


if __name__ == "__main__":
    unittest.main()
