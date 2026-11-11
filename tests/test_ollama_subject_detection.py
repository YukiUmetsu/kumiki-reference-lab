"""Local animated character detection proposals with original-PTS source evidence."""
from __future__ import annotations

import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.ollama_subject_detection import (
    _parse_subject_boxes, detect_local_ollama_subjects,
)
from kumiki_reference_lab.pipeline.subject_detections import (
    associate_detection_tracklets, load_subject_detections,
)


def _boxes():
    return {"subjects": [
        {"category": "animated-character", "box": [0.1, 0.2, 0.26, 0.5]},
        {"category": "anthropomorphic", "box": [0.62, 0.15, 0.25, 0.6]},
    ]}


class OllamaSubjectDetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "authorized.mp4"
        self.source.write_bytes(b"synthetic local media; ffmpeg mocked")
        self.out = self.base / "subject-detections.json"
        self.source_info = {
            "source": {"sha256": "a" * 64},
            "video": {"streamIndex": 0, "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }
        self.frames = [SimpleNamespace(pts=i * 1000, ordinal=i) for i in range(3)]
        self.cuts = SimpleNamespace(timebase=Fraction(1, 1000), pts=(1500,))

    def run_fake(self, *, proposal=None, cut_scan=None, fail=None):
        frames = self.frames
        cuts = self.cuts if cut_scan is None else cut_scan
        input_box = _boxes() if proposal is None else proposal
        def fake_model(*args, **kwargs):
            if fail:
                raise ValueError(fail)
            self.assertEqual(kwargs["model"], "local-model:8b")
            self.assertEqual(kwargs["port"], 11434)
            self.assertEqual(len(args[0]), 1)
            self.assertTrue(args[0][0].startswith(b"\x89PNG\r\n\x1a\n"))
            return input_box
        with (patch("kumiki_reference_lab.pipeline.ollama_subject_detection.inspect_source",
                    return_value=self.source_info),
              patch("kumiki_reference_lab.pipeline.ollama_subject_detection.read_frame_pts",
                    return_value=frames),
              patch("kumiki_reference_lab.pipeline.ollama_subject_detection.read_rgb_frames",
                    side_effect=lambda *args, **kwargs: [
                        b"\x75" * (kwargs["width"] * kwargs["height"] * 3)
                        for _ in args[2]]),
              patch("kumiki_reference_lab.pipeline.ollama_subject_detection.detect_hard_cut_pts",
                    return_value=cuts),
              patch("kumiki_reference_lab.pipeline.ollama_subject_detection._ollama_json",
                    side_effect=fake_model) as called):
            path = detect_local_ollama_subjects(
                self.source, self.out, model="local-model:8b",
                max_samples=5, width=160, height=90,
            )
        return path, called.call_count

    def test_stylized_multi_character_detection_works_with_tracklet_adapter(self):
        path, calls = self.run_fake()
        self.assertEqual(calls, 3)
        result = load_subject_detections(path)
        self.assertEqual([x["sourcePts"] for x in result["frames"]], [0, 1000, 2000])
        self.assertEqual(result["cutCandidatePts"], [1500])
        self.assertEqual(result["detector"]["name"], "ollama-local-vlm:local-model:8b")
        self.assertIsNone(result["detector"]["modelSha256"])
        self.assertEqual([x["category"] for x in result["frames"][0]["detections"]],
                         ["animated-character", "anthropomorphic"])
        self.assertTrue(all(
            x["score"] == 0.5
            for frame in result["frames"] for x in frame["detections"]
        ))
        scene, report = associate_detection_tracklets(result)
        self.assertEqual(report["trackletCount"], 4)
        self.assertEqual(len(scene["characters"]), 4)
        self.assertEqual(scene["actions"], [])
        self.assertEqual(scene["identityClaims"], [])
        with self.assertRaisesRegex(ValueError, "nonexisting"):
            self.run_fake()

    def test_empty_result_does_not_invent_people(self):
        path, _ = self.run_fake(proposal={"subjects": []})
        result = load_subject_detections(path)
        self.assertTrue(all(not x["detections"] for x in result["frames"]))
        scene, report = associate_detection_tracklets(result)
        self.assertEqual(scene["characters"], [])
        self.assertEqual(report["trackletCount"], 0)

    def test_model_errors_do_not_publish_files(self):
        with self.assertRaisesRegex(ValueError, "synthetic model failure"):
            self.run_fake(fail="synthetic model failure")
        self.assertFalse(self.out.exists())

    def test_reject_bad_subject_schema_and_duplicate_boxes(self):
        invalid = [
            {"extra": True, "subjects": []},
            {"subjects": "red-haired person"},
            {"subjects": [{}]},
            {"subjects": [{"category": "Japanese", "box": [.2,.2,.3,.4]}]},
            {"subjects": [{"category": "animated-character", "box": [.9,.2,.2,.4]}]},
            {"subjects": [{"category": "person", "box": [.1,.1,True,.4]}]},
            {"subjects": [{"category": "person", "box": [.1,.1,.001,.01]}]},
            {"subjects": [
                {"category": "person", "box": [.1,.2,.3,.5]},
                {"category": "animated-character", "box": [.1,.2,.3,.5]},
            ]},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                _parse_subject_boxes(value, frame_width=160, frame_height=90)

    def test_vision_input_order_and_top_left_normalization(self):
        out = _parse_subject_boxes({
            "subjects": [
                {"category": "animal", "box": [.7,.1,.2,.3]},
                {"category": "person", "box": [.1,.1,.2,.3]},
            ],
        }, frame_width=160, frame_height=90)
        self.assertEqual([x["category"] for x in out], ["person", "animal"])
        self.assertEqual(out[0]["box"], [.1,.1,.2,.3])

    def test_source_cut_timebase_mismatch_abstains(self):
        with self.assertRaisesRegex(ValueError, "timebase differs"):
            self.run_fake(cut_scan=SimpleNamespace(
                timebase=Fraction(1,90000), pts=()))
        self.assertFalse(self.out.exists())

    def test_invalid_user_parameters_rejected_without_inference(self):
        errors = [
            {"seconds": True}, {"seconds": 31}, {"max_samples": 1},
            {"port": False}, {"model": "../secret"},
            {"model": "z"*73}, {"cut_threshold": float("nan")},
            {"timeout_seconds": 10000},
        ]
        for change in errors:
            with self.subTest(change=change), self.assertRaises(ValueError):
                detect_local_ollama_subjects(
                    self.source, self.out,
                    **{"model": "local-model:8b", **change})
        self.assertFalse(self.out.exists())

    def test_cli(self):
        args = build_parser().parse_args([
            "local-character-detect", "film.mp4",
            "--model", "local-vision:8b",
            "--out", "runs/detections.json", "--max-samples", "8"])
        self.assertEqual(args.command, "local-character-detect")
        self.assertEqual(args.max_samples, 8)
        self.assertEqual(args.model, "local-vision:8b")


if __name__ == "__main__":
    unittest.main()
