"""Offline speech stage tests. Never download models or third-party media."""
from __future__ import annotations

import json
import tempfile
import unittest
import wave
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.pipeline.speech_transcribe import (
    _audio_stream, _parse_whisper_json, _round_pts, transcribe_local_video,
)
from kumiki_reference_lab.reviews.character_scene import load_character_scene
from kumiki_reference_lab.cli.app import build_parser


class SpeechTranscribeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "input.mp4"
        self.source.write_bytes(b"synthetic-source-fixture")
        self.model = self.root / "model.bin"
        self.model.write_bytes(b"synthetic-model-fixture")
        self.out = self.root / "speech-output"
        self.media_info = {
            "source": {"sha256": "f" * 64},
            "video": {"streamIndex": 0, "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }
        self.streams = {"streams": [
            {"index": 0, "codec_type": "video"},
            {"index": 1, "codec_type": "audio", "time_base": "1/48000", "start_pts": 48000},
        ]}
        self.transcript = {"result": {"language": "en"}, "transcription": [
            {"offsets": {"from": 0, "to": 1200}, "text": " Hello there!"},
            {"offsets": {"from": 1450, "to": 3000}, "text": "Nice to see you."},
        ]}

    def fake_commands(self, args, *, timeout, stage):
        if stage.startswith("ffmpeg"):
            self.assertIn("-protocol_whitelist", args)
            self.assertEqual(args[args.index("-map") + 1], "0:1")
            with wave.open(str(args[-1]), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(b"\\0\\0" * 64000)
        elif stage.startswith("whisper"):
            self.assertEqual(args[args.index("-l") + 1], "auto")
            out_prefix = Path(args[args.index("-of") + 1])
            out_prefix.with_suffix(".json").write_text(
                json.dumps(self.transcript), encoding="utf-8")
        else:
            self.fail("unexpected subprocess")

    def run_fake(self):
        with (patch("kumiki_reference_lab.pipeline.speech_transcribe.inspect_source",
                    return_value=self.media_info),
              patch("kumiki_reference_lab.pipeline.speech_transcribe.probe_media",
                    return_value=self.streams),
              patch("kumiki_reference_lab.pipeline.speech_transcribe._run_command",
                    side_effect=self.fake_commands)):
            return transcribe_local_video(self.source, self.out, model=self.model,
                                          max_seconds=4)

    def test_source_timed_unattributed_scene_and_provenance(self):
        path = self.run_fake()
        scene = load_character_scene(path)
        self.assertEqual(scene["window"],
                         {"startPts": 1000, "endPts": 5000, "coverage": "partial-window"})
        self.assertEqual([(s["startPts"], s["endPts"]) for s in scene["utterances"]],
                         [(1000, 2200), (2450, 4000)])
        self.assertEqual([s["text"] for s in scene["utterances"]],
                         ["Hello there!", "Nice to see you."])
        self.assertTrue(all(s["speakerId"] is None and s["speakerEvidence"] == "unknown"
                            and s["confidence"] == "low" for s in scene["utterances"]))
        self.assertEqual(scene["characters"], [])
        self.assertEqual(scene["actions"], [])
        self.assertEqual(scene["identityClaims"], [])
        self.assertFalse(list(self.out.glob("*.wav")))
        manifest = json.loads((self.out / "speech-manifest.json").read_text())
        self.assertEqual(manifest["sourceAudioStreamIndex"], 1)
        self.assertEqual(manifest["audioStartPts"], 48000)
        self.assertEqual(manifest["utteranceCount"], 2)
        self.assertEqual(manifest["decodedAudioSamples"], 64000)
        self.assertIn("no-speaker-identification", manifest["evidenceStatus"])
        with self.assertRaisesRegex(ValueError, "nonexisting"):
            self.run_fake()

    def test_rational_timebase_mappings(self):
        self.assertEqual(_round_pts(Fraction(1, 1000), Fraction(1, 1001)), 1)
        self.assertEqual(_round_pts(Fraction(-1, 2000), Fraction(1, 1000)), -1)
        self.assertEqual(_round_pts(Fraction(1, 2000), Fraction(1, 1000)), 1)
        utterances = _parse_whisper_json(
            {"transcription": [{"offsets": {"from": 0, "to": 2000}, "text": "你好"}]},
            max_duration_ms=3000, audio_start=Fraction(1, 2), video_timebase=Fraction(1, 1000),
            lang="zh")
        self.assertEqual((utterances[0]["startPts"], utterances[0]["endPts"]),
                         (500, 2500))

    def test_zero_segments_are_not_no_speech_claim(self):
        self.transcript = {"result": {}, "transcription": []}
        scene = load_character_scene(self.run_fake())
        self.assertEqual(scene["utterances"], [])
        self.assertEqual(scene["window"]["coverage"], "partial-window")

    def test_reject_invalid_audio_origin(self):
        for audio in (
            [],
            [{"index": 1, "codec_type": "audio", "time_base": "1/48000"}],
            [{"index": True, "codec_type": "audio", "time_base": "1/48000",
              "start_pts": 0}],
        ):
            with self.subTest(audio=audio), self.assertRaises(ValueError):
                _audio_stream({"streams": audio})

    def test_reject_input_tricks(self):
        for opts in ({"max_seconds": 121}, {"max_seconds": True},
                     {"timeout_seconds": 1}, {"language": "en;rm -rf"}):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                transcribe_local_video(self.source, self.out, model=self.model, **opts)
        playlist = self.root / "payload.m3u8"
        playlist.write_text("https://example.invalid/asset.mp4")
        with self.assertRaisesRegex(ValueError, "local regular video"):
            transcribe_local_video(playlist, self.out, model=self.model)

    def test_bad_offsets_never_publish_partial_results(self):
        for offsets in (
            {"from": -1, "to": 100},
            {"from": True, "to": 100},
            {"from": 100, "to": 10000},
            {"from": 100, "to": 100},
            {"from": "0", "to": 100},
        ):
            self.transcript["transcription"][0]["offsets"] = offsets
            with self.subTest(offsets=offsets), self.assertRaises(ValueError):
                self.run_fake()
            self.assertFalse(self.out.exists())

    def test_failure_never_publishes(self):
        with (patch("kumiki_reference_lab.pipeline.speech_transcribe.inspect_source",
                    return_value=self.media_info),
              patch("kumiki_reference_lab.pipeline.speech_transcribe.probe_media",
                    return_value=self.streams),
              patch("kumiki_reference_lab.pipeline.speech_transcribe._run_command",
                    side_effect=ValueError("synthetic whisper failure"))):
            with self.assertRaisesRegex(ValueError, "synthetic whisper failure"):
                transcribe_local_video(self.source, self.out, model=self.model)
        self.assertFalse(self.out.exists())

    def test_cli_parses_explicit_model_and_local_source(self):
        args = build_parser().parse_args([
            "speech-transcribe", "clip.mp4", "--model", "model.bin",
            "--out", "runs/example", "--max-seconds", "60"])
        self.assertEqual(args.command, "speech-transcribe")
        self.assertEqual(args.max_seconds, 60)
        self.assertEqual(args.model, Path("model.bin"))


if __name__ == "__main__":
    unittest.main()
