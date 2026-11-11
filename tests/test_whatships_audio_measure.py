"""Real generated MP4+AAC audio and Git-tracked numeric energy evidence."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.audio.source_audio_probe import (
    _stats, analyze_source_audio_window,
)
from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.catalog.whatships_analysis_store import (
    export_repository_analysis,validate_repository_analysis,
)
from kumiki_reference_lab.catalog.whatships_audio_measure import (
    measure_whatships_audio_to_repository,
)
from kumiki_reference_lab.cli.app import main
from tests.test_video_sources import whatships_fixture


class AudioEnvelopeMathTests(unittest.TestCase):
    def test_silence_and_loud_segment_are_raw_pcm_energy_not_music_labels(self):
        raw=struct.pack("<1600h",*([0]*800+[16000]*800))
        stats=_stats(raw,expected_samples=1600)
        self.assertEqual(stats["decodedPcmSampleCount"],1600)
        self.assertEqual(stats["frames"][0]["rmsDbfs"],-120)
        self.assertTrue(stats["frames"][0]["nearSilence"])
        self.assertFalse(stats["frames"][1]["nearSilence"])
        self.assertEqual(stats["frames"][1]["decodedOffsetMs"],100)
        self.assertEqual(stats["summary"]["nearSilenceFrameFraction"],.5)
        self.assertLess(stats["summary"]["rmsDbfs"],0)

    def test_empty_malformed_or_oversized_audio_is_not_silence(self):
        for raw in (b"",b"\x00",b"\x00\x00"*(1600+2049)):
            with self.subTest(size=len(raw)),self.assertRaises(ValueError):
                _stats(raw,expected_samples=1600)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Real FFmpeg and FFprobe are required for generated MP4 smoke")
class RealVideoAudioMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/"original-generated-audio.mp4"
        proc=subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error",
            "-nostdin","-y",
            "-f","lavfi","-i","color=c=black:s=160x90:r=5:d=4",
            "-f","lavfi","-i","sine=frequency=440:sample_rate=16000:duration=4",
            "-map","0:v:0","-map","1:a:0",
            "-c:v","mpeg4","-q:v","5","-c:a","aac",
            "-b:a","64k","-shortest",str(self.source),
        ],capture_output=True,timeout=25)
        if proc.returncode:
            self.fail("Unable to generate original local audio-video smoke fixture")
        self.info=inspect_source(self.source,rights_status="user-declared-authorized")
        self.sha=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.assertEqual(self.info["source"]["sha256"],self.sha)
        self.catalog=self.root/"catalog.json"
        self.catalog.write_text(json.dumps(whatships_fixture()))
        self.bindings=self.root/"private-ledger.json"
        self.bindings.write_text(json.dumps({
            "schemaVersion":"kumiki.whatships-local-media-bindings.v1",
            "createdOn":"2026-11-11",
            "catalogIndexUrl":"https://whatships.com/search-index.json",
            "disclaimer":"self-declared-source-identity-and-authorization-only",
            "bindings":[{
                "sourceId":"whatships:film-one",
                "watchUrl":"https://whatships.com/videos/film-one/",
                "localPath":str(self.source.resolve()),
                "mediaSha256":self.sha,
                "mediaSizeBytes":self.source.stat().st_size,
                "sourceStreamIndex":self.info["video"]["streamIndex"],
                "sourceTimebase":self.info["video"]["sourceTimebase"],
                "rightsBasis":"own-original-work",
                "rightsNote":"Generated original video and sine wave for local audio testing only.",
                "identityNote":"Synthetic film-one is a test fixture, not a published catalog video.",
                "rightsStatus":"user-declared-authorized",
                "verificationStatus":"operator-attestation-not-independently-verified",
                "boundOn":"2026-11-11",
            }],
        }))
        self.repository=self.root/"analysis"
        export_repository_analysis(self.catalog,self.repository)

    def test_true_audio_stream_is_measured_without_transcribing_speech_or_music(self):
        report=analyze_source_audio_window(
            self.source,start_seconds=0,seconds=2,
            rights_status="user-declared-authorized")
        self.assertEqual(report["schemaVersion"],"kumiki.source-audio-energy-probe.v1")
        self.assertEqual(report["sourceSha256"],self.sha)
        self.assertEqual(report["decodedPcmSampleRate"],8000)
        self.assertGreater(report["decodedPcmSampleCount"],10000)
        self.assertLessEqual(report["decodedPcmSampleCount"],18048)
        self.assertLess(report["summary"]["rmsDbfs"],0)
        self.assertGreater(report["summary"]["rmsDbfs"],-70)
        self.assertEqual(report["audioStreamIndex"],1)
        self.assertIn("not-original-pts-aligned",report["evidenceStatus"])
        self.assertNotIn(str(self.root),json.dumps(report))
        self.assertTrue(all(row["peakDbfs"]>=row["rmsDbfs"]
                            for row in report["decodedFrames"]))

    def test_real_aac_audio_is_persisted_into_git_without_media_or_private_notes(self):
        result=measure_whatships_audio_to_repository(
            self.catalog,self.bindings,"whatships:film-one",self.repository,
            window_seconds=2,window_count=2)
        self.assertEqual(result["measuredAudioWindows"],2)
        self.assertTrue(result["gitWorkingTreeUpdated"])
        data=json.loads((self.repository/"film-one.json").read_text())
        self.assertTrue(data["coverage"]["hasSampledAudioEnergy"])
        self.assertFalse(data["coverage"]["fullFilmReviewed"])
        self.assertIsNone(data["evidence"].get("numericVisual"))
        self.assertEqual(data["sourceMediaSha256"],self.sha)
        energy=data["evidence"]["numericAudio"]
        self.assertEqual(len(energy["windows"]),2)
        self.assertEqual(energy["windows"][0]["audioClockStatus"],
                         "ffmpeg-output-seek-not-original-source-pts-verified")
        self.assertGreater(len(energy["windows"][0]["decodedFrames"]),10)
        text=(self.repository/"film-one.json").read_text()
        self.assertNotIn(str(self.root),text)
        self.assertNotIn("original-generated-audio.mp4",text)
        verified=validate_repository_analysis(self.repository,self.catalog)
        self.assertEqual(verified["numericAudioSampledVideos"],1)
        self.assertEqual(verified["numericSampledVideos"],0)
        self.assertEqual(verified["humanReviewedFullVideos"],0)
        again=measure_whatships_audio_to_repository(
            self.catalog,self.bindings,"whatships:film-one",self.repository,
            window_seconds=2,window_count=2)
        self.assertFalse(again["gitWorkingTreeUpdated"])

    def test_audio_layer_does_not_allow_private_identity_or_transcription_fields(self):
        measure_whatships_audio_to_repository(
            self.catalog,self.bindings,"whatships:film-one",self.repository,
            window_seconds=2,window_count=1)
        record_path=self.repository/"film-one.json"
        original=json.loads(record_path.read_text())
        modified=json.loads(record_path.read_text())
        modified["evidence"]["numericAudio"]["windows"][0]["decodedFrames"][0]["transcript"]="private identity"
        record_path.write_text(json.dumps(modified))
        with self.assertRaisesRegex(ValueError,"audio energy frame duration"):
            validate_repository_analysis(self.repository,self.catalog)
        record_path.write_text(json.dumps(original))
        modified=json.loads(record_path.read_text())
        modified["evidence"]["numericAudio"]["windows"][0]["decodedFrames"][0]["rmsDbfs"]=999
        record_path.write_text(json.dumps(modified))
        with self.assertRaisesRegex(ValueError,"dBFS"):
            validate_repository_analysis(self.repository,self.catalog)

    def test_modified_source_fingerprint_refuses_audio_measurement(self):
        self.source.write_bytes(b"changed source bytes")
        with self.assertRaisesRegex(ValueError,"fingerprint changed"):
            measure_whatships_audio_to_repository(
                self.catalog,self.bindings,"whatships:film-one",self.repository,
                window_seconds=2,window_count=1)
        self.assertEqual(validate_repository_analysis(self.repository,self.catalog)
                         ["numericAudioSampledVideos"],0)

    def test_cli_audio_measure_produces_path_redacted_result(self):
        capture=io.StringIO()
        with contextlib.redirect_stdout(capture):
            result=main([
                "whatships-audio-measure",str(self.bindings),"whatships:film-one",
                "--snapshot",str(self.catalog),
                "--repository-root",str(self.repository),
                "--window-seconds","2","--window-count","1",
            ])
        self.assertEqual(result,0)
        output=json.loads(capture.getvalue())
        self.assertEqual(output["measuredAudioWindows"],1)
        self.assertNotIn(str(self.root),capture.getvalue())
        self.assertEqual(validate_repository_analysis(self.repository,self.catalog)
                         ["numericAudioSampledVideos"],1)


if __name__=="__main__":
    unittest.main()
