"""Deterministic external detector tracklets must abstain on ambiguous identity."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.subject_detections import (
    INPUT_VERSION, associate_detection_tracklets, load_subject_detections,
    run_subject_detections, validate_subject_detections,
)
from kumiki_reference_lab.reviews.character_scene import load_character_scene


def observation(x, y=0.2, w=0.24, h=0.4, *, category="person", score=0.91):
    return {"category": category, "score": score, "box": [x, y, w, h]}


def fixture():
    return {
        "schemaVersion": INPUT_VERSION,
        "sourceSha256": "a"*64, "sourceStreamIndex": 0,
        "sourceTimebase": {"numerator": 1, "denominator": 1000},
        "detector": {"name": "synthetic-offline-detector", "modelSha256": "b"*64},
        "cutCandidatePts": [],
        "frames": [
            {"sourcePts": 0, "detections": [observation(0.1), observation(0.6)]},
            {"sourcePts": 1000, "detections": [observation(0.13), observation(0.57)]},
            {"sourcePts": 2000, "detections": [observation(0.16), observation(0.54)]},
        ],
    }


class DetectionAssociationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "detections.json"
        self.source = self.root / "source.mp4"
        self.source.write_bytes(b"synthetic source; FFprobe mocked")
        self.out = self.root / "result"
        self.data = fixture()
        self.write()

    def write(self):
        self.path.write_text(json.dumps(self.data), encoding="utf-8")

    def test_multi_person_tracks_have_provisional_identity_only(self):
        scene, report = associate_detection_tracklets(self.data)
        self.assertEqual(len(scene["characters"]), 2)
        self.assertEqual(len(scene["appearances"]), 6)
        self.assertEqual(scene["actions"], [])
        self.assertEqual(scene["utterances"], [])
        self.assertEqual(scene["identityClaims"], [])
        self.assertEqual([row["trackletId"] for row in report["frames"][1]["proposals"]],
                         ["subject_001", "subject_002"])
        self.assertTrue(all(row["association"] == "mutual-iou-match"
                            for row in report["frames"][1]["proposals"]))
        self.assertTrue(all(a["confidence"] == "low" and not a["visibleTraits"]
                            and a["endPts"] - a["startPts"] == 1
                            for a in scene["appearances"]))
        self.assertEqual(report["trackletCount"], 2)
        self.assertEqual(report["tracklets"][0]["observedFrameCount"], 3)

    def test_cut_restarts_tracklets(self):
        self.data["cutCandidatePts"] = [1500]
        scene, report = associate_detection_tracklets(self.data)
        self.assertEqual(report["trackletCount"], 4)
        self.assertEqual([p["trackletId"] for p in report["frames"][2]["proposals"]],
                         ["subject_003", "subject_004"])
        self.assertTrue(all(p["crossedCutBeforeFrame"] for p in report["frames"][2]["proposals"]))

    def test_missing_frame_breaks_association(self):
        self.data["frames"][1]["detections"] = []
        scene, report = associate_detection_tracklets(self.data)
        self.assertEqual(report["trackletCount"], 4)
        self.assertEqual(report["frames"][1]["proposals"], [])

    def test_competing_iou_abstains_from_reidentification(self):
        self.data["frames"] = [
            {"sourcePts": 0, "detections": [observation(0.1, w=0.3),
                                             observation(0.3, w=0.3)]},
            {"sourcePts": 1000, "detections": [observation(0.2, w=0.3)]},
        ]
        scene, report = associate_detection_tracklets(self.data)
        self.assertEqual(report["frames"][1]["proposals"][0]["trackletId"], "subject_003")
        self.assertEqual(report["frames"][1]["proposals"][0]["association"], "new-unverified-tracklet")
        self.assertEqual(report["uncertainAssociationStarts"], 1)

    def test_low_scores_are_not_tracked(self):
        self.data["frames"][1]["detections"][1]["score"] = 0.01
        scene, report = associate_detection_tracklets(self.data)
        self.assertEqual(report["lowScoreRejected"], 1)
        self.assertEqual(len(report["frames"][1]["proposals"]), 1)
        self.assertEqual(report["trackletCount"], 3)

    def test_reject_bad_detection_input(self):
        mutations = [
            lambda x: x["frames"][0]["detections"][0].update(score=float("nan")),
            lambda x: x["frames"][0]["detections"][0].update(score=True),
            lambda x: x["frames"][0]["detections"][0].update(score=10**300),
            lambda x: x["frames"][0]["detections"][0].update(category="ethnicity"),
            lambda x: x["frames"][0]["detections"][0].update(box=[0.9, 0, 0.2, 0.3]),
            lambda x: x["frames"][0]["detections"][0].update(box=[0, 0, True, 0.3]),
            lambda x: x["frames"][0]["detections"].append(copy.deepcopy(x["frames"][0]["detections"][0])),
            lambda x: x["frames"][1].update(sourcePts=0),
            lambda x: x["cutCandidatePts"].extend([1300, 1100]),
            lambda x: x["sourceTimebase"].update(denominator=0),
            lambda x: x["detector"].update(name=[]),
        ]
        for mutation in mutations:
            subject = fixture()
            mutation(subject)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_subject_detections(subject)

    def test_external_input_loader_rejects_duplicate_keys_and_symlinks(self):
        self.path.write_text('{"schemaVersion":"x","schemaVersion":"y"}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_subject_detections(self.path)
        self.path.unlink()
        self.path.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "regular"):
            load_subject_detections(self.path)

    def test_runner_verifies_local_source_identity_and_publishes_atomically(self):
        inspected = {
            "source": {"sha256": "a"*64},
            "video": {"streamIndex": 0, "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }
        with patch("kumiki_reference_lab.pipeline.subject_detections.inspect_source",
                   return_value=inspected):
            result_path = run_subject_detections(self.source, self.path, self.out)
        self.assertTrue(result_path.is_file())
        report = json.loads(result_path.read_text())
        self.assertEqual(len(report["detectionFileSha256"]), 64)
        self.assertEqual(report["trackletCount"], 2)
        scene = load_character_scene(self.out / "character-scene.json")
        self.assertEqual(len(scene["characters"]), 2)
        self.assertEqual(scene["reviewer"]["kind"], "model")
        with self.assertRaisesRegex(ValueError, "nonexisting"):
            run_subject_detections(self.source, self.path, self.out)
        self.assertEqual(len(list(self.out.iterdir())), 2)

    def test_wrong_source_fingerprint_never_publishes(self):
        inspected = {
            "source": {"sha256": "f"*64},
            "video": {"streamIndex": 0, "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }
        with patch("kumiki_reference_lab.pipeline.subject_detections.inspect_source",
                   return_value=inspected):
            with self.assertRaisesRegex(ValueError, "does not match"):
                run_subject_detections(self.source, self.path, self.out)
        self.assertFalse(self.out.exists())

    def test_optional_parameters_are_guarded(self):
        for keyword in ({"min_iou": True}, {"ambiguity_margin": float("nan")},
                        {"min_score": -0.1}):
            with self.subTest(keyword=keyword), self.assertRaises(ValueError):
                associate_detection_tracklets(self.data, **keyword)

    def test_cli(self):
        args = build_parser().parse_args([
            "subject-detections", "source.mp4", "detections.json",
            "--out", "runs/detections", "--min-iou", "0.5"])
        self.assertEqual(args.command, "subject-detections")
        self.assertEqual(args.min_iou, 0.5)


if __name__ == "__main__":
    unittest.main()
