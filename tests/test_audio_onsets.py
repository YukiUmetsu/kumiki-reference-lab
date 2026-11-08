import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.audio.onsets import (
    analyze_audio_onsets, audio_onsets_from_levels,
)
from kumiki_reference_lab.cli.app import build_parser


def r(n, d=1):
    return {"numerator": n, "denominator": d}


def level_report(*, rms, pts=None, durations=None):
    pts = pts or list(range(len(rms)))
    durations = durations or [1] * len(rms)
    return {
        "sourceSha256": "a" * 64, "audioStreamIndex": 1,
        "sourceTimebase": r(1), "sampleRateHz": 100,
        "scanWindowSeconds": 10, "maxFrameBudget": 4096,
        "status": "source-pts-aligned-level-observations",
        "frames": [{
            "sourcePts": p, "sourceSeconds": r(p),
            "decodedDurationSeconds": r(d),
            "rmsDbFs": value,
            "peakDbFs": None if value is None else value + 3,
        } for p, d, value in zip(pts, durations, rms, strict=True)],
    }


class AudioOnsetsUnitTests(unittest.TestCase):
    def test_cli_parses_onset_options(self):
        args = build_parser().parse_args([
            "audio-onsets", "source.mp4", "--min-rise-db", "15",
            "--cooldown-ms", "200", "--out", "results",
        ])
        self.assertEqual(args.command, "audio-onsets")
        self.assertEqual(args.min_rise_db, 15)
        self.assertEqual(args.cooldown_ms, 200)

    def test_detects_measured_rise_without_claiming_sound_identity(self):
        result = audio_onsets_from_levels(level_report(rms=[-65, -60, -20, -18, -40]))
        self.assertEqual(result["schemaVersion"], "kumiki.audio-onsets.v1")
        self.assertEqual(result["eligibleAdjacentFramePairs"], 4)
        self.assertEqual(result["aboveThresholdPairCount"], 1)
        self.assertEqual(len(result["candidates"]), 1)
        onset = result["candidates"][0]
        self.assertEqual(onset["anchorSourcePts"], 2)
        self.assertEqual(onset["supportWindow"], {"startSeconds": r(1),
                                                   "endSeconds": r(3)})
        self.assertEqual(onset["measuredRmsRiseDb"], 40)
        self.assertEqual(onset["signal"], "candidate-rms-rise")
        self.assertEqual(onset["interpretationStatus"], "not-verified")
        self.assertNotIn("musicBeat", json.dumps(result))

    def test_floor_return_has_no_invented_rise_and_cooldown_is_counted(self):
        levels = level_report(rms=[None, -20, -70, -25, -60, -18])
        levels["sourceTimebase"] = r(1, 2)
        for frame in levels["frames"]:
            frame["sourceSeconds"] = r(frame["sourcePts"], 2)
            frame["decodedDurationSeconds"] = r(1, 2)
        result = audio_onsets_from_levels(levels, cooldown_ms=1200)
        self.assertEqual(result["aboveThresholdPairCount"], 3)
        self.assertEqual(result["cooldownSuppressedPairCount"], 1)
        self.assertEqual([r["anchorSourcePts"] for r in result["candidates"]], [1, 5])
        self.assertIsNone(result["candidates"][0]["measuredRmsRiseDb"])
        self.assertTrue(result["candidates"][0]["floorAssisted"])

    def test_discontinuity_is_not_a_rise_and_invalid_tuning_is_rejected(self):
        levels = level_report(rms=[-70, -15], pts=[0, 5])
        result = audio_onsets_from_levels(levels)
        self.assertEqual(result["discontinuityRejectedPairs"], 1)
        self.assertEqual(result["candidates"], [])
        with self.assertRaisesRegex(ValueError, "min_rise_db"):
            audio_onsets_from_levels(levels, min_rise_db=float("nan"))
        with self.assertRaisesRegex(ValueError, "cooldown_ms"):
            audio_onsets_from_levels(levels, cooldown_ms=-1)

    def test_missing_audio_is_not_invented_silence(self):
        source = level_report(rms=[])
        source.update({"status": "no-audio-stream", "audioStreamIndex": None,
                       "sourceTimebase": None, "sampleRateHz": None})
        result = audio_onsets_from_levels(source)
        self.assertEqual(result["status"], "no-audio-stream")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["observedFrameCount"], 0)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe required")
class AudioOnsetsIntegrationTests(unittest.TestCase):
    def test_gated_tone_start_produces_source_linked_attack_candidate(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "audio-attack.mkv"
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10:d=1.5",
                "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono:d=0.5",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000:duration=0.5",
                "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono:d=0.5",
                "-filter_complex", "[1:a][2:a][3:a]concat=n=3:v=0:a=1[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "ffv1", "-c:a", "pcm_s16le",
                "-shortest", str(source),
            ]
            process = subprocess.run(command, capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0,
                             process.stderr.decode(errors="replace"))
            report = analyze_audio_onsets(source, seconds=2)
            self.assertEqual(report["status"], "source-pts-aligned-level-attack-candidates")
            self.assertGreaterEqual(len(report["candidates"]), 1)
            self.assertTrue(any(
                0.4 <= row["anchorSourceSeconds"]["numerator"] /
                row["anchorSourceSeconds"]["denominator"] <= 0.8
                for row in report["candidates"]
            ))
            self.assertEqual(len(json.loads(json.dumps(report))["candidates"]),
                             len(report["candidates"]))

    def test_silent_video_has_no_audio_stream(self):
        with tempfile.TemporaryDirectory() as name:
            source = Path(name) / "silent.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0)
            report = analyze_audio_onsets(source, seconds=2)
            self.assertEqual(report["status"], "no-audio-stream")
            self.assertEqual(report["candidates"], [])


if __name__ == "__main__":
    unittest.main()
