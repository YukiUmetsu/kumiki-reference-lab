"""Source-PTS-bound character scene review, including multi-character actions and speech."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.reviews.character_scene import (
    load_character_scene, summarize_character_scene, validate_character_scene,
)
from kumiki_reference_lab.cli.app import main

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/character-scene.synthetic.example.json"


class CharacterSceneTests(unittest.TestCase):
    def setUp(self):
        self.good = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_synthetic_character_action_and_speaker_summary(self):
        validate_character_scene(self.good)
        report = summarize_character_scene(self.good)
        self.assertEqual(report["windowSeconds"], 6)
        self.assertEqual(report["characterCount"], 3)
        self.assertEqual(report["appearanceCount"], 2)
        self.assertEqual(report["actionCount"], 2)
        self.assertEqual(report["interactionCount"], 1)
        self.assertEqual(report["utteranceCount"], 2)
        self.assertEqual(report["unattributedUtterances"], 1)
        self.assertEqual(report["characters"][0]["attributedUtterances"], 1)
        self.assertEqual(report["characters"][0]["visibleTraits"], ["red jacket", "round glasses"])
        self.assertEqual(report["interactionPairs"], [
            {"actorId": "person_a", "targetId": "person_b", "eventCount": 1}])
        self.assertEqual(report["actionTimeline"][0]["action"], "points-at")
        self.assertEqual(report["dialogueTimeline"][0]["text"], "Look over there!")
        self.assertEqual(report["reviewStatus"], "reviewer-declared-not-independently-media-verified")

    def test_cli_validate_and_report(self):
        import contextlib
        import io
        for sub, key, value in (("validate", "characterCount", 3),
                                ("report", "interactionCount", 1)):
            with self.subTest(sub=sub):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = main(["character-scene", sub, str(EXAMPLE)])
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(buf.getvalue())[key], value)

    def test_speaker_unknown_or_bound_to_roster(self):
        for speaker, basis in (("missing", "unknown"), (None, "visible-lip-motion"),
                               ([], "unknown")):
            x = copy.deepcopy(self.good)
            x["utterances"][0].update(speakerId=speaker, speakerEvidence=basis)
            with self.subTest(speaker=speaker), self.assertRaises(ValueError):
                validate_character_scene(x)

    def test_rejects_invalid_actions_appearance_and_window(self):
        changes = [
            lambda x: x["actions"][0].update(actorId="narrator"),
            lambda x: x["actions"][0].update(targetId="person_a"),
            lambda x: x["actions"][0].update(targetId="missing"),
            lambda x: x["actions"][0].update(anchorPts=[9999]),
            lambda x: x["actions"][0].update(endPts=100),
            lambda x: x["appearances"][0].update(anchorBox=[0.9, 0.5, 0.5, 0.5]),
            lambda x: x["appearances"][0].update(visibleTraits=[[]]),
            lambda x: x["characters"].append(copy.deepcopy(x["characters"][0])),
            lambda x: x["characters"][0].update(kind=[]),
            lambda x: x["window"].update(coverage="unexpected"),
            lambda x: x["sourceTimebase"].update(numerator=True),
            lambda x: x["actions"][0].update(startPts=True),
        ]
        for i, change in enumerate(changes):
            x = copy.deepcopy(self.good)
            change(x)
            with self.subTest(case=i), self.assertRaises(ValueError):
                validate_character_scene(x)

    def test_sensitive_identity_claim_needs_explicit_evidence(self):
        x = copy.deepcopy(self.good)
        x["identityClaims"] = [{
            "characterId": "person_a", "attribute": "gender-identity", "value": "woman",
            "evidenceKind": "explicit-dialogue", "evidencePts": 1700,
            "evidenceText": "I'm a woman", "confidence": "medium",
        }]
        self.assertEqual(summarize_character_scene(x)["identityClaims"], 1)
        for field, bad in (("evidenceKind", "face-appearance"),
                           ("evidencePts", 999999),
                           ("attribute", "biological-sex"),
                           ("characterId", "unknown")):
            y = copy.deepcopy(x)
            y["identityClaims"][0][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_character_scene(y)

    def test_unhashable_input_rejected_without_unhandled_type_errors(self):
        cases = [
            ("actions", "actorId"), ("actions", "targetId"),
            ("appearances", "characterId"), ("utterances", "speakerId"),
            ("utterances", "language"),
        ]
        for collection, field in cases:
            x = copy.deepcopy(self.good)
            x[collection][0][field] = []
            with self.subTest(collection=collection, field=field), self.assertRaises(ValueError):
                validate_character_scene(x)

    def test_overlapping_speech_and_bounds(self):
        x = copy.deepcopy(self.good)
        x["utterances"][1].update(startPts=1700, endPts=2300)
        validate_character_scene(x)  # overlapping speech is legitimate
        x["utterances"][1]["endPts"] = 9000
        with self.assertRaises(ValueError):
            validate_character_scene(x)

    def test_json_rejects_duplicates_nan_symlinks_and_oversize(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "review.json"
            p.write_text(json.dumps(self.good), encoding="utf-8")
            self.assertEqual(load_character_scene(p)["schemaVersion"], self.good["schemaVersion"])
            p.write_text('{"schemaVersion":"x","schemaVersion":"y"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_character_scene(p)
            p.write_text(json.dumps(self.good).replace('"sourceStreamIndex": 0',
                        '"sourceStreamIndex": NaN'), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite"):
                load_character_scene(p)
            p.write_bytes(b" " * (512 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, "512 KiB"):
                load_character_scene(p)
            p.unlink()
            p.symlink_to(EXAMPLE)
            with self.assertRaisesRegex(ValueError, "regular"):
                load_character_scene(p)


if __name__ == "__main__":
    unittest.main()
