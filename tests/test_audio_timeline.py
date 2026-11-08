import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from kumiki_reference_lab.analyzers.audio.timeline import _audio_frames, analyze_audio_timeline
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.cli.app import build_parser


class AudioTimelineUnitTests(unittest.TestCase):
    def test_cli_arguments(self):
        args = build_parser().parse_args([
            "audio-timeline", "source.mp4", "--max-seconds", "2",
            "--max-frames", "5",
        ])
        self.assertEqual((args.max_seconds, args.max_frames), (2, 5))

    def test_missing_nonincreasing_pts_and_bad_counts_are_not_invented(self):
        fake_audio = [
            "pts=-10|best_effort_timestamp=-10|nb_samples=100",
            "pts=0|best_effort_timestamp=0|nb_samples=100",
            "pts=0|best_effort_timestamp=0|nb_samples=0",
            "pts=N/A|best_effort_timestamp=N/A|nb_samples=N/A",
        ]
        metadata = {"streams": [{
            "index": 1, "codec_type": "audio", "sample_rate": "1000",
            "channels": 1, "time_base": "1/1000",
        }]}
        inspected = {"source": {"sha256": "a" * 64}, "video": {"streamIndex": 0}}
        with patch("kumiki_reference_lab.analyzers.audio.timeline.file_signature",
                   return_value=(100, 0, 0, 0)), patch(
            "kumiki_reference_lab.analyzers.audio.timeline.require_unchanged"
        ), patch("kumiki_reference_lab.analyzers.audio.timeline.inspect_source",
                 return_value=inspected), patch(
            "kumiki_reference_lab.analyzers.audio.timeline.probe_media",
            return_value=metadata,
        ), patch("subprocess.run", return_value=CompletedProcess(
            [], 0, "\n".join(fake_audio) + "\n", "",
        )):
            result = analyze_audio_timeline(Path("fake.mkv"), seconds=2)
        self.assertEqual(result["status"], "audio-timing-incomplete")
        self.assertEqual([f["sourcePts"] for f in result["frames"]],
                         [-10, 0, 0, None])
        self.assertEqual([a["reason"] for a in result["ptsAnomalies"]],
                         ["nonincreasing-source-pts", "missing-or-invalid-sample-count",
                          "missing-source-pts", "missing-or-invalid-sample-count"])
        self.assertEqual(result["frames"][0]["sourceSeconds"],
                         {"numerator": -1, "denominator": 100})
        self.assertEqual(result["frames"][0]["decodedDurationSeconds"],
                         {"numerator": 1, "denominator": 10})

    def test_frame_budget_and_timeout(self):
        with patch("subprocess.run", return_value=CompletedProcess(
            [], 0, "pts=1|nb_samples=100\n" * 3, "",
        )):
            with self.assertRaisesRegex(ProbeError, "frame count"):
                _audio_frames(Path("dummy"), 1, 1, ffprobe="ffprobe", max_frames=2)
        with self.assertRaisesRegex(ValueError, "1..30"):
            analyze_audio_timeline(Path("dummy"), seconds=0)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe required")
class AudioTimelineIntegrationTests(unittest.TestCase):
    def test_original_audio_pts_with_multiplexed_video(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            clip = root / "clip.mkv"
            result = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=2",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000:duration=2",
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "ffv1", "-c:a", "pcm_s16le", "-shortest", str(clip),
            ], capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            report = analyze_audio_timeline(clip, seconds=2)
            self.assertEqual(report["status"], "source-timing-candidate")
            self.assertEqual(report["sampleRateHz"], 8000)
            self.assertNotEqual(report["sourceVideoStreamIndex"],
                                report["audioStreamIndex"])
            self.assertTrue(report["frames"])
            self.assertFalse(report["ptsAnomalies"])
            first = report["frames"][0]
            self.assertIsInstance(first["sourcePts"], int)
            self.assertIsInstance(first["decodedSampleCount"], int)
            duration = first["decodedDurationSeconds"]
            self.assertAlmostEqual(
                duration["numerator"] / duration["denominator"],
                first["decodedSampleCount"] / 8000)
            self.assertEqual(len(report["frames"]),
                             len({f["sourcePts"] for f in report["frames"]}))
            self.assertEqual(json.loads(json.dumps(report))["schemaVersion"],
                             "kumiki.audio-timeline.v1")

    def test_video_without_audio_has_explicit_status(self):
        with tempfile.TemporaryDirectory() as temp:
            clip = Path(temp) / "silent-video.mkv"
            result = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(clip),
            ], capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0)
            report = analyze_audio_timeline(clip, seconds=2)
            self.assertEqual(report["status"], "no-audio-stream")
            self.assertIsNone(report["audioStreamIndex"])
            self.assertEqual(report["frames"], [])


if __name__ == "__main__":
    unittest.main()
