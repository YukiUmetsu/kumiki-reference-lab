"""Local Ollama vision proposals remain source-PTS-bound and unverified."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.subject_detections import associate_detection_tracklets
from kumiki_reference_lab.pipeline.ollama_character_perception import (
    _crop_rgb, _ollama_chat, _parse_model_response, describe_local_characters,
)
from kumiki_reference_lab.reviews.character_scene import load_character_scene


def _proposal(*, action="none"):
    return {
        "appearance": "Red jacket and dark hair with squared shoulders.",
        "visibleTraits": ["red jacket", "dark hair"],
        "observedAction": action,
        "motionEvidence": ("Visible arm changes direction across frames."
                           if action != "none" else ""),
    }


class OllamaCharacterVisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "film.mp4"
        self.source.write_bytes(b"synthetic film; ffmpeg mocked")
        self.report = root / "subject-tracklets.json"
        self.out = root / "vision-out"
        self.data = {
            "schemaVersion": "kumiki.subject-detections.v1",
            "sourceSha256": "a"*64,
            "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "detector": {"name": "synthetic", "modelSha256": None},
            "cutCandidatePts": [],
            "frames": [
                {"sourcePts": i*1000, "detections": [
                    {"category": "animated-character", "score": 0.9,
                     "box": [0.1 + i*0.01, 0.2, 0.3, 0.5]}]}
                for i in range(3)
            ],
        }
        self.prepare()
        self.source_metadata = {
            "source": {"sha256": "a"*64},
            "video": {"streamIndex": 0, "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }

    def prepare(self):
        scene, tracklets = associate_detection_tracklets(self.data)
        self.report.write_text(json.dumps(tracklets))

    def run_fake(self, *, metadata=None, points=None, vlm=None):
        metadata = self.source_metadata if metadata is None else metadata
        points = points if points is not None else [
            SimpleNamespace(pts=1000*i, ordinal=i) for i in range(3)]
        def fake_rgb(*args, **kwargs):
            return [b"\x80" * (kwargs["width"] * kwargs["height"] * 3)
                    for _ in args[2]]
        def fake_vlm(images, *, model, port, timeout_seconds, previous):
            return _proposal(action="waving" if previous else "none")
        with (patch("kumiki_reference_lab.pipeline.ollama_character_perception.inspect_source",
                    return_value=metadata),
              patch("kumiki_reference_lab.pipeline.ollama_character_perception.read_frame_pts",
                    return_value=points),
              patch("kumiki_reference_lab.pipeline.ollama_character_perception.read_rgb_frames",
                    side_effect=fake_rgb),
              patch("kumiki_reference_lab.pipeline.ollama_character_perception._ollama_chat",
                    side_effect=vlm or fake_vlm)):
            return describe_local_characters(self.source, self.report, self.out,
                                             model="local-vision:7b", max_frames=3,
                                             width=160, height=90)

    def test_appearance_and_temporal_motion_are_low_confidence(self):
        result = load_character_scene(self.run_fake())
        self.assertEqual(len(result["characters"]), 1)
        self.assertEqual(len(result["appearances"]), 3)
        self.assertEqual(len(result["actions"]), 2)
        self.assertEqual([x["action"] for x in result["actions"]], ["waving", "waving"])
        self.assertEqual(result["actions"][0]["anchorPts"], [0, 1000])
        self.assertTrue(all(x["confidence"] == "low" for x in result["actions"]))
        self.assertEqual(result["characters"][0]["kind"], "animated-human")
        self.assertEqual(result["characters"][0]["visualDescription"],
                         _proposal()["appearance"])
        self.assertEqual(result["utterances"], [])
        self.assertEqual(result["identityClaims"], [])
        manifest = json.loads((self.out / "character-vision.json").read_text())
        self.assertEqual(manifest["modelCalls"], 3)
        self.assertEqual(manifest["actionProposalCount"], 2)
        self.assertFalse(manifest["modelDigestVerified"])
        self.assertEqual(manifest["evidenceStatus"], "unreviewed-local-vlm-frame-hypotheses")
        self.assertEqual(len(list(self.out.iterdir())), 2)
        with self.assertRaisesRegex(ValueError, "nonexisting"):
            self.run_fake()

    def test_report_mismatch_and_missing_frames_fail_without_output(self):
        incorrect = {
            "source": {"sha256": "b"*64},
            "video": {"streamIndex": 0, "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }
        with self.assertRaisesRegex(ValueError, "do not match"):
            self.run_fake(metadata=incorrect)
        self.assertFalse(self.out.exists())
        with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
            self.run_fake(points=[
                SimpleNamespace(pts=0, ordinal=0),
                SimpleNamespace(pts=2000, ordinal=2)])
        self.assertFalse(self.out.exists())

    def test_vision_failure_is_atomic(self):
        def fail(*args, **kwargs):
            raise ValueError("local model unavailable")
        with self.assertRaisesRegex(ValueError, "model unavailable"):
            self.run_fake(vlm=fail)
        self.assertFalse(self.out.exists())

    def test_output_refuses_demographic_inferences_or_action_from_still(self):
        with self.assertRaisesRegex(ValueError, "demographic"):
            _parse_model_response({
                **_proposal(), "appearance": "An Asian teenager with a red jacket."
            }, allow_action=False)
        with self.assertRaisesRegex(ValueError, "single frames"):
            _parse_model_response(_proposal(action="walking"), allow_action=False)
        with self.assertRaisesRegex(ValueError, "distinct bounded"):
            _parse_model_response({**_proposal(), "visibleTraits": ["red jacket", "red jacket"]},
                                  allow_action=True)
        with self.assertRaisesRegex(ValueError, "motion evidence"):
            _parse_model_response({**_proposal(action="waving"), "motionEvidence": ""},
                                  allow_action=True)

    def test_previous_frame_cannot_link_through_known_cut(self):
        self.data["cutCandidatePts"] = [500]
        self.prepare()
        result = load_character_scene(self.run_fake())
        # Detector stage restarts tracklets across cuts, so no action can bridge the cut.
        self.assertEqual(result["actions"][0]["startPts"], 1000)
        self.assertTrue(all(x["startPts"] >= 1000 for x in result["actions"]))

    def test_crop_validates_bounds_and_dimensions(self):
        rgb = b"\x7f" * 60 * 30 * 3
        crop, w, h = _crop_rgb(rgb, 60, 30, [0.1, 0.1, 0.5, 0.5])
        self.assertEqual(len(crop), w*h*3)
        with self.assertRaisesRegex(ValueError, "size"):
            _crop_rgb(b"short", 60, 30, [0.1, 0.1, 0.5, 0.5])
        with self.assertRaisesRegex(ValueError, "too small"):
            _crop_rgb(rgb, 60, 30, [0.1, 0.1, 0.01, 0.01])

    def test_loopback_ollama_payload_and_json_contract(self):
        class FakeResponse:
            status = 200
            def read(self, count):
                return json.dumps({"message": {"content": json.dumps(_proposal())}}).encode()
        calls = []
        class FakeConnection:
            def __init__(self, host, port, timeout):
                calls.append(("open", host, port, timeout))
            def request(self, method, path, body, headers):
                calls.append(("request", method, path, json.loads(body)))
            def getresponse(self):
                return FakeResponse()
            def close(self):
                calls.append(("close",))
        with patch("kumiki_reference_lab.pipeline.ollama_character_perception.http.client.HTTPConnection",
                   FakeConnection):
            response = _ollama_chat([b"PNG"], model="local-model:8b", port=11434,
                                    timeout_seconds=30, previous=False)
        self.assertEqual(response["observedAction"], "none")
        self.assertEqual(calls[0], ("open", "127.0.0.1", 11434, 30))
        self.assertEqual(calls[1][2], "/api/chat")
        self.assertFalse(calls[1][3]["stream"])
        self.assertEqual(calls[1][3]["format"], "json")
        self.assertEqual(calls[-1], ("close",))

    def test_rejects_invalid_configuration_before_contacting_model(self):
        for change in (
            {"max_calls": 25}, {"max_frames": 1}, {"model": "../bad"},
            {"port": False}, {"timeout_seconds": 10000}, {"scan_seconds": 121},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                describe_local_characters(self.source, self.report, self.out,
                                          **{"model": "vision:8b", **change})
        self.assertFalse(self.out.exists())

    def test_cli_arguments(self):
        args = build_parser().parse_args([
            "local-character-vision", "film.mp4", "tracklets.json",
            "--model", "vision:8b", "--out", "runs/vision",
            "--max-calls", "8"])
        self.assertEqual(args.command, "local-character-vision")
        self.assertEqual(args.max_calls, 8)
        self.assertEqual(args.model, "vision:8b")


if __name__ == "__main__":
    unittest.main()
