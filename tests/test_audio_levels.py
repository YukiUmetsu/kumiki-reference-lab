import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from kumiki_reference_lab.analyzers.audio.levels import _read_levels, analyze_audio_levels
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.cli.app import build_parser


class AudioLevelsUnitTests(unittest.TestCase):
    def test_cli_and_reject_invalid_measurements(self):
        args = build_parser().parse_args([
            "audio-levels", "source.mkv", "--max-seconds", "2",
        ])
        self.assertEqual(args.command, "audio-levels")
        bad_frame = ("frame:0    pts:0       pts_time:0\n"
                     "lavfi.astats.Overall.RMS_level=-20.0\n")
        with patch("subprocess.run", return_value=CompletedProcess([], 0, bad_frame, "")):
            with self.assertRaisesRegex(ProbeError, "complete"):
                _read_levels(Path("fake"), 1, 1, ffmpeg="ffmpeg", max_frames=2)
        wrong_order = ("frame:1    pts:100       pts_time:0.1\n")
        with patch("subprocess.run", return_value=CompletedProcess([], 0, wrong_order, "")):
            with self.assertRaisesRegex(ProbeError, "ordinal"):
                _read_levels(Path("fake"), 1, 1, ffmpeg="ffmpeg", max_frames=2)

    def test_filter_clock_and_sample_count_mismatch_are_blocking(self):
        timeline = {
            "status": "source-timing-candidate", "sourceSha256": "a" * 64,
            "audioStreamIndex": 1, "sourceTimebase": {"numerator": 1, "denominator": 8000},
            "sampleRateHz": 8000, "frames": [{
                "sourcePts": 0, "sourceSeconds": {"numerator": 0, "denominator": 1},
                "decodedSampleCount": 1024,
                "decodedDurationSeconds": {"numerator": 16, "denominator": 125},
            }],
        }
        bad = {"ordinal": 0, "filterPtsTime": "0.5", "metrics": {
            "lavfi.astats.Overall.RMS_level": "-20",
            "lavfi.astats.Overall.Peak_level": "-18",
            "lavfi.astats.Overall.Number_of_samples": "1024.000000",
        }}
        with patch("kumiki_reference_lab.analyzers.audio.levels.file_signature",
                   return_value=(10, 0, 0, 0)), patch(
            "kumiki_reference_lab.analyzers.audio.levels.analyze_audio_timeline",
            return_value=timeline,
        ), patch("kumiki_reference_lab.analyzers.audio.levels._read_levels",
                 return_value=[bad]):
            with self.assertRaisesRegex(ValueError, "timing differs"):
                analyze_audio_levels(Path("dummy"))
            bad["filterPtsTime"] = "0"
            bad["metrics"]["lavfi.astats.Overall.Number_of_samples"] = "2048.000000"
            with self.assertRaisesRegex(ValueError, "sample count differs"):
                analyze_audio_levels(Path("dummy"))

    def test_only_a_small_later_filter_tail_may_be_excluded(self):
        timeline = {
            "status": "source-timing-candidate", "sourceSha256": "b" * 64,
            "audioStreamIndex": 1, "sourceTimebase": {"numerator": 1, "denominator": 8000},
            "sampleRateHz": 8000, "frames": [{
                "sourcePts": 0, "sourceSeconds": {"numerator": 0, "denominator": 1},
                "decodedSampleCount": 1024,
                "decodedDurationSeconds": {"numerator": 16, "denominator": 125},
            }],
        }
        def frame(ordinal, pts):
            return {"ordinal": ordinal, "filterPtsTime": pts, "metrics": {
                "lavfi.astats.Overall.RMS_level": "-20",
                "lavfi.astats.Overall.Peak_level": "-18",
                "lavfi.astats.Overall.Number_of_samples": "1024.000000",
            }}
        with patch("kumiki_reference_lab.analyzers.audio.levels.file_signature",
                   return_value=(10, 0, 0, 0)), patch(
            "kumiki_reference_lab.analyzers.audio.levels.require_unchanged",
        ), patch(
            "kumiki_reference_lab.analyzers.audio.levels.analyze_audio_timeline",
            return_value=timeline,
        ), patch("kumiki_reference_lab.analyzers.audio.levels._read_levels") as read:
            read.return_value = [frame(0, "0"), frame(1, "0.128")]
            report = analyze_audio_levels(Path("dummy"), seconds=1)
            self.assertEqual(len(report["frames"]), 1)
            read.return_value = [frame(0, "0"), frame(1, "0")]
            with self.assertRaisesRegex(ValueError, "valid trailing"):
                analyze_audio_levels(Path("dummy"), seconds=1)
            read.return_value = [frame(0, "0"), frame(1, "0.128"),
                                 frame(2, "0.256"), frame(3, "0.384"),
                                 frame(4, "0.512"), frame(5, "0.640")]
            with self.assertRaisesRegex(ValueError, "1:1"):
                analyze_audio_levels(Path("dummy"), seconds=1)

    def test_partial_final_audio_frame_is_excluded_only_at_scan_boundary(self):
        timeline = {
            "status": "source-timing-candidate", "sourceSha256": "c" * 64,
            "audioStreamIndex": 1, "sourceTimebase": {"numerator": 1, "denominator": 8000},
            "sampleRateHz": 8000, "frames": [
                {"sourcePts": 0, "sourceSeconds": {"numerator": 0, "denominator": 1},
                 "decodedSampleCount": 1024,
                 "decodedDurationSeconds": {"numerator": 16, "denominator": 125}},
                {"sourcePts": 7000, "sourceSeconds": {"numerator": 7, "denominator": 8},
                 "decodedSampleCount": 1024,
                 "decodedDurationSeconds": {"numerator": 16, "denominator": 125}},
            ],
        }
        def measured(pts, samples):
            return {"filterPtsTime": pts, "metrics": {
                "lavfi.astats.Overall.RMS_level": "-20",
                "lavfi.astats.Overall.Peak_level": "-18",
                "lavfi.astats.Overall.Number_of_samples": str(samples),
            }}
        with patch("kumiki_reference_lab.analyzers.audio.levels.file_signature",
                   return_value=(10, 0, 0, 0)), patch(
            "kumiki_reference_lab.analyzers.audio.levels.require_unchanged",
        ), patch(
            "kumiki_reference_lab.analyzers.audio.levels.analyze_audio_timeline",
            return_value=timeline,
        ), patch("kumiki_reference_lab.analyzers.audio.levels._read_levels") as read:
            read.return_value = [measured("0", 1024), measured("0.875", 1000)]
            report = analyze_audio_levels(Path("dummy"), seconds=1)
            self.assertEqual(report["excludedPartialBoundaryFrames"], 1)
            self.assertEqual([x["sourcePts"] for x in report["frames"]], [0])
            read.return_value = [measured("0", 1024), measured("0.875", 900)]
            with self.assertRaisesRegex(ValueError, "sample count differs"):
                analyze_audio_levels(Path("dummy"), seconds=1)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe required")
class AudioLevelsIntegrationTests(unittest.TestCase):
    def test_tone_then_digital_silence_reports_relative_levels_at_source_pts(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "tone-then-quiet.mkv"
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=2",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000:duration=1",
                "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono:d=1",
                "-filter_complex", "[1:a][2:a]concat=n=2:v=0:a=1[a]",
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "ffv1", "-c:a", "pcm_s16le", "-shortest", str(source),
            ]
            process = subprocess.run(command, capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0,
                             process.stderr.decode(errors="replace"))
            report = analyze_audio_levels(source, seconds=2)
            self.assertEqual(report["status"], "source-pts-aligned-level-observations")
            self.assertEqual(report["sampleRateHz"], 8000)
            self.assertGreaterEqual(len(report["frames"]), 10)
            self.assertGreater(report["frames"][0]["rmsDbFs"], -40)
            self.assertLess(report["frames"][0]["rmsDbFs"], -10)
            self.assertFalse(report["frames"][0]["quietFrameCandidate"])
            self.assertTrue(report["frames"][-1]["quietFrameCandidate"])
            self.assertTrue(report["frames"][-1]["belowMeasurementFloor"])
            self.assertIsNone(report["frames"][-1]["rmsDbFs"])
            self.assertEqual(len(report["frames"]),
                             len({frame["sourcePts"] for frame in report["frames"]}))
            self.assertEqual(json.loads(json.dumps(report))["schemaVersion"],
                             "kumiki.audio-levels.v1")

    def test_video_with_no_audio_does_not_invent_silence(self):
        with tempfile.TemporaryDirectory() as name:
            source = Path(name) / "no-audio.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0)
            report = analyze_audio_levels(source, seconds=2)
            self.assertEqual(report["status"], "no-audio-stream")
            self.assertEqual(report["frames"], [])


if __name__ == "__main__":
    unittest.main()
