"""Offline deterministic diarization join, including overlapping voice conflicts."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.pipeline.speaker_association import associate_speakers
from kumiki_reference_lab.reviews.character_scene import load_character_scene
from kumiki_reference_lab.cli.app import build_parser


class DiarizationJoinTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        root = Path(self.dir.name)
        self.run = root / "asr"
        self.run.mkdir()
        self.out = root / "joined"
        self.rttm = root / "diarization.rttm"
        self.scene = {
            "schemaVersion": "kumiki.character-scene-review.v1",
            "sourceSha256": "a" * 64,
            "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "reviewer": {"kind": "model", "id": "whisper.cpp-local-asr"},
            "window": {"startPts": 1000, "endPts": 5000, "coverage": "partial-window"},
            "characters": [], "appearances": [], "actions": [], "identityClaims": [],
            "utterances": [
                {"speakerId": None, "startPts": 1000, "endPts": 2200,
                 "text": "Hello there.", "language": "en", "transcriptEvidence": "speech",
                 "speakerEvidence": "unknown", "confidence": "low"},
                {"speakerId": None, "startPts": 2450, "endPts": 4000,
                 "text": "Welcome back.", "language": "en", "transcriptEvidence": "speech",
                 "speakerEvidence": "unknown", "confidence": "low"},
            ],
        }
        self.manifest = {
            "schemaVersion": "kumiki.local-speech-transcription.v1",
            "sourceSha256": "a" * 64,
            "modelSha256": "b" * 64,
            "sourceVideoTimebase": {"numerator": 1, "denominator": 1000},
            "audioSourceTimebase": {"numerator": 1, "denominator": 48000},
            "audioStartPts": 48000,
            "decodedAudioSamples": 64000,
            "sampleRateHz": 16000,
        }
        self.save()
        self.rttm.write_text(
            "SPEAKER trackA 1 0.0 1.3 <NA> <NA> speaker_A <NA> <NA>\n"
            "SPEAKER trackA 1 1.45 1.6 <NA> <NA> speaker_B <NA> <NA>\n")

    def save(self):
        (self.run / "character-scene.json").write_text(json.dumps(self.scene))
        (self.run / "speech-manifest.json").write_text(json.dumps(self.manifest))

    def test_two_voice_clusters_source_timed_dialogue(self):
        result = load_character_scene(associate_speakers(self.run, self.rttm, self.out))
        self.assertEqual([c["id"] for c in result["characters"]], ["voice_001", "voice_002"])
        self.assertTrue(all(c["kind"] == "voice-only" and c["visualDescription"] is None
                            for c in result["characters"]))
        self.assertEqual([u["speakerId"] for u in result["utterances"]],
                         ["voice_001", "voice_002"])
        self.assertTrue(all(u["confidence"] == "low" for u in result["utterances"]))
        report = json.loads((self.out / "speaker-association.json").read_text())
        self.assertEqual(report["attributedUtterances"], 2)
        self.assertEqual(report["unknownUtterances"], 0)
        with self.assertRaisesRegex(ValueError, "nonexisting"):
            associate_speakers(self.run, self.rttm, self.out)

    def test_competing_speakers_remain_unknown(self):
        self.rttm.write_text(
            "SPEAKER trackA 1 0 1.3 <NA> <NA> speaker_A <NA> <NA>\n"
            "SPEAKER trackA 1 0.5 3 <NA> <NA> speaker_B <NA> <NA>\n")
        result = load_character_scene(associate_speakers(self.run, self.rttm, self.out))
        self.assertIsNone(result["utterances"][0]["speakerId"])
        self.assertEqual(result["utterances"][1]["speakerId"], "voice_002")
        report = json.loads((self.out / "speaker-association.json").read_text())
        self.assertEqual(report["unknownUtterances"], 1)
        self.assertGreater(report["decisions"][0]["nextCoverage"], 0.1)

    def test_empty_diarization_creates_no_speakers(self):
        self.rttm.write_text("")
        result = load_character_scene(associate_speakers(self.run, self.rttm, self.out))
        self.assertEqual(result["characters"], [])
        self.assertTrue(all(s["speakerId"] is None for s in result["utterances"]))

    def test_wrong_provenance_fails_without_publishing(self):
        self.manifest["sourceSha256"] = "f" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "hashes disagree"):
            associate_speakers(self.run, self.rttm, self.out)
        self.assertFalse(self.out.exists())

    def test_invalid_rttm_rejected(self):
        invalid = [
            "SPEAKER trackA 1 1 500 <NA> <NA> speaker_A <NA> <NA>\n",
            "SPEAKER trackA 1 1 -1 <NA> <NA> speaker_A <NA> <NA>\n",
            "SPEAKER trackA 1 1 1 <NA> <NA> ../../evil <NA> <NA>\n",
            "SPEAKER trackA 2 1 1 <NA> <NA> speaker_A <NA> <NA>\n",
            "SPEAKER trackA 1 0 1 <NA> <NA> speaker_A <NA> <NA>\n"
            "SPEAKER trackB 1 0 1 <NA> <NA> speaker_A <NA> <NA>\n",
        ]
        for line in invalid:
            self.rttm.write_text(line)
            with self.subTest(line=line), self.assertRaises(ValueError):
                associate_speakers(self.run, self.rttm, self.out)
            self.assertFalse(self.out.exists())

    def test_preattributed_character_scene_rejected(self):
        self.scene["characters"].append(
            {"id": "person_a", "kind": "human", "label": "A",
             "visualDescription": "White coat"})
        self.scene["utterances"][0]["speakerId"] = "person_a"
        self.scene["utterances"][0]["speakerEvidence"] = "speaker-diarization"
        self.save()
        with self.assertRaisesRegex(ValueError, "pristine unattributed"):
            associate_speakers(self.run, self.rttm, self.out)

    def test_threshold_validation(self):
        for kwargs in ({"min_coverage": float("nan")}, {"max_competing": 2},
                       {"min_coverage": False}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                associate_speakers(self.run, self.rttm, self.out, **kwargs)

    def test_cli(self):
        args = build_parser().parse_args(
            ["speech-associate", "speech-run", "voice.rttm", "--out", "joined"])
        self.assertEqual(args.command, "speech-associate")
        self.assertEqual(args.min_coverage, 0.80)


if __name__ == "__main__":
    unittest.main()
