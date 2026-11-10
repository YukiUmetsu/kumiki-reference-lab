"""Synthetic source-bound visual speaker links, not automatic face identification."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.pipeline.character_speech_link import link_characters_to_speech
from kumiki_reference_lab.reviews.character_scene import load_character_scene
from kumiki_reference_lab.cli.app import build_parser


class VisualSpeakerLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.voice_path = root / "voice-scene.json"
        self.visual_path = root / "visual-scene.json"
        self.links_path = root / "links.json"
        self.out = root / "output"
        base = {
            "schemaVersion": "kumiki.character-scene-review.v1",
            "sourceSha256": "a"*64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "reviewer": {"kind": "model", "id": "synthetic-test"},
            "window": {"startPts": 0, "endPts": 5000, "coverage": "partial-window"},
            "characters": [], "appearances": [], "actions": [], "utterances": [],
            "identityClaims": [],
        }
        self.voice = copy.deepcopy(base)
        self.voice["characters"] = [
            {"id": "voice_001", "kind": "voice-only", "label": "Voice one",
             "visualDescription": None},
            {"id": "voice_002", "kind": "voice-only", "label": "Voice two",
             "visualDescription": None},
        ]
        self.voice["utterances"] = [
            {"speakerId": "voice_001", "startPts": 500, "endPts": 1300,
             "text": "Hello", "language": "en", "transcriptEvidence": "speech",
             "speakerEvidence": "speaker-diarization", "confidence": "low"},
            {"speakerId": "voice_002", "startPts": 1800, "endPts": 3000,
             "text": "How are you?", "language": "en", "transcriptEvidence": "speech",
             "speakerEvidence": "speaker-diarization", "confidence": "low"},
        ]
        self.visual = copy.deepcopy(base)
        self.visual["characters"] = [
            {"id": "person_a", "kind": "animated-human", "label": "Character A",
             "visualDescription": "Short dark hair, round glasses and red jacket"},
            {"id": "person_b", "kind": "animated-human", "label": "Character B",
             "visualDescription": "Blue scarf and yellow backpack"},
        ]
        self.visual["appearances"] = [
            {"characterId": "person_a", "startPts": 400, "endPts": 1600,
             "anchorPts": [700], "visibleTraits": ["red jacket"],
             "anchorBox": [0.1,0.1,0.3,0.7],
             "observation": "Character A visible on left side", "confidence": "medium"},
            {"characterId": "person_b", "startPts": 1600, "endPts": 3300,
             "anchorPts": [2000], "visibleTraits": ["blue scarf"],
             "anchorBox": [0.6,0.1,0.3,0.7],
             "observation": "Character B visible on right side", "confidence": "medium"},
        ]
        self.review = {
            "schemaVersion": "kumiki.character-speech-link-review.v1",
            "sourceSha256": "a"*64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "reviewer": {"kind": "human", "id": "test-film-reviewer"},
            "links": [{
                "utteranceIndex": 0, "characterId": "person_a",
                "evidencePts": 700, "evidenceType": "visible-lip-motion",
                "observation": "Character A visibly moves lips during this phrase.",
                "confidence": "medium",
            }],
        }
        self.save()

    def save(self):
        self.voice_path.write_text(json.dumps(self.voice))
        self.visual_path.write_text(json.dumps(self.visual))
        self.links_path.write_text(json.dumps(self.review))

    def run_link(self):
        return link_characters_to_speech(
            self.voice_path, self.visual_path, self.links_path, self.out)

    def test_link_one_utterance_not_entire_voice_track(self):
        result = load_character_scene(self.run_link())
        self.assertEqual([u["speakerId"] for u in result["utterances"]],
                         ["person_a", "voice_002"])
        self.assertEqual(result["utterances"][0]["speakerEvidence"], "visible-lip-motion")
        self.assertEqual(result["utterances"][0]["confidence"], "medium")
        self.assertEqual([c["id"] for c in result["characters"]],
                         ["person_a", "person_b", "voice_002"])
        self.assertEqual(len(result["appearances"]), 2)
        report = json.loads((self.out / "character-speech-links.json").read_text())
        self.assertEqual(report["linkedUtteranceCount"], 1)
        self.assertEqual(report["links"][0]["originalVoiceId"], "voice_001")
        with self.assertRaisesRegex(ValueError, "nonexisting"):
            self.run_link()

    def test_model_review_cannot_promote_unverified_confidence(self):
        self.review["reviewer"]["kind"] = "model"
        self.review["links"][0]["confidence"] = "high"
        self.save()
        result = load_character_scene(self.run_link())
        self.assertEqual(result["utterances"][0]["confidence"], "low")

    def test_invalid_visual_anchor_or_duplicate_rejected(self):
        changes = [
            lambda x: x["links"][0].update(evidencePts=2200),
            lambda x: x["links"][0].update(characterId="unknown"),
            lambda x: x["links"][0].update(evidenceType="face-recognition"),
            lambda x: x["links"][0].update(confidence="unresolved"),
            lambda x: x["links"].append(copy.deepcopy(x["links"][0])),
            lambda x: x["links"][0].update(utteranceIndex=True),
        ]
        for mutate in changes:
            original = copy.deepcopy(self.review)
            mutate(self.review)
            self.save()
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.run_link()
            self.assertFalse(self.out.exists())
            self.review = original

    def test_reject_cross_source_or_review_outside_speech(self):
        self.visual["sourceSha256"] = "b"*64
        self.save()
        with self.assertRaisesRegex(ValueError, "source fingerprint"):
            self.run_link()
        self.visual["sourceSha256"] = "a"*64
        self.visual["window"]["endPts"] = 6000
        self.save()
        with self.assertRaisesRegex(ValueError, "bounded by speech"):
            self.run_link()

    def test_visual_scene_cannot_duplicate_speech(self):
        self.visual["utterances"] = copy.deepcopy(self.voice["utterances"])
        for utterance in self.visual["utterances"]:
            utterance["speakerId"] = None
            utterance["speakerEvidence"] = "unknown"
        self.save()
        with self.assertRaisesRegex(ValueError, "must not already include"):
            self.run_link()

    def test_cli(self):
        args = build_parser().parse_args([
            "speech-link-characters", "voice.json", "visual.json",
            "review.json", "--out", "result"])
        self.assertEqual(args.command, "speech-link-characters")
        self.assertEqual(args.link_review, Path("review.json"))


if __name__ == "__main__":
    unittest.main()
