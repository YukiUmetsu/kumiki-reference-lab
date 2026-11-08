import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.analyzers.audio.av_cuts import (
    build_av_cut_evidence, summarize_cut_audio,
)
from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.analyze import run_analysis


def rational(numerator, denominator=1):
    return {"numerator": numerator, "denominator": denominator}


def sample(start_ms, *, quiet=False, duration_ms=100):
    return {
        "sourcePts": start_ms,
        "sourceSeconds": rational(start_ms, 1000),
        "decodedDurationSeconds": rational(duration_ms, 1000),
        "quietFrameCandidate": quiet,
        "rmsDbFs": None if quiet else -21.5,
        "peakDbFs": None if quiet else -16.0,
    }


REGIONS = [
    {"id": "region-001", "startSeconds": rational(0), "startPtsInclusive": 0},
    {"id": "region-002", "startSeconds": rational(1), "startPtsInclusive": 10},
]


class AvCutPureTests(unittest.TestCase):
    def test_sufficient_quiet_contrast_and_exact_straddler_exclusion(self):
        frames = [sample(t) for t in (600, 700, 800, 900)]
        frames += [sample(950, quiet=False)]  # Spans the cut; excluded.
        frames += [sample(t, quiet=True) for t in (1000, 1100, 1200, 1300)]
        candidate, = summarize_cut_audio(REGIONS, frames, window_ms=400)
        self.assertEqual(candidate["status"], "candidate-quiet-level-contrast")
        self.assertEqual(candidate["before"]["frameCount"], 4)
        self.assertEqual(candidate["after"]["frameCount"], 4)
        self.assertEqual(candidate["before"]["quietFrameFraction"], 0)
        self.assertEqual(candidate["after"]["quietFrameFraction"], 1)
        self.assertEqual(candidate["before"]["lastAudioSourcePts"], 900)
        self.assertIsNone(candidate["after"]["medianFiniteRmsDbFs"])
        self.assertEqual(candidate["interpretationStatus"], "not-verified")

    def test_insufficient_frames_do_not_imply_contrast(self):
        result, = summarize_cut_audio(REGIONS, [sample(900), sample(1000, quiet=True)],
                                      window_ms=200)
        self.assertEqual(result["status"], "insufficient-fully-contained-audio-frames")
        self.assertEqual(result["before"]["frameCount"], 1)

    def test_uniform_audio_has_no_strong_contrast(self):
        result, = summarize_cut_audio(REGIONS,
                                      [sample(t) for t in (800, 900, 1000, 1100)],
                                      window_ms=200)
        self.assertEqual(result["status"], "no-strong-quiet-level-contrast")

    def test_reject_out_of_budget_windows_and_frame_counts(self):
        args = build_parser().parse_args([
            "av-cut-evidence", "sample.mkv", "runs/analysis-run.json", "--window-ms", "500",
        ])
        self.assertEqual(args.command, "av-cut-evidence")
        with self.assertRaisesRegex(ValueError, "window_ms"):
            summarize_cut_audio(REGIONS, [], window_ms=99)
        with self.assertRaisesRegex(ValueError, "max_audio_frames"):
            build_av_cut_evidence(Path("none"), Path("none"), max_audio_frames=10001)

    def test_cross_source_is_not_silently_compared(self):
        with patch("kumiki_reference_lab.analyzers.audio.av_cuts.build_shot_evidence",
                   return_value={"status": "candidate-edit-regions", "sourceSha256": "a" * 64}), \
             patch("kumiki_reference_lab.analyzers.audio.av_cuts._json_file",
                   return_value={"settings": {"seconds": 2, "rightsStatus": "review-required"}}), \
             patch("kumiki_reference_lab.analyzers.audio.av_cuts.analyze_audio_levels",
                   return_value={"sourceSha256": "b" * 64}):
            with self.assertRaisesRegex(ValueError, "different source bytes"):
                build_av_cut_evidence(Path("source"), Path("run"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe unavailable")
class AvCutIntegrationTests(unittest.TestCase):
    @staticmethod
    def render(source: Path, *, with_audio: bool) -> None:
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1",
            "-f", "lavfi", "-i", "color=c=yellow:s=160x90:r=10:d=1",
        ]
        if with_audio:
            command.extend([
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000:duration=1",
                "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono:d=1",
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v];"
                                   "[2:a][3:a]concat=n=2:v=0:a=1[a]",
                "-map", "[v]", "-map", "[a]", "-c:v", "ffv1", "-c:a", "pcm_s16le",
            ])
        else:
            command.extend([
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map", "[v]", "-c:v", "ffv1",
            ])
        command.append(str(source))
        result = subprocess.run(command, capture_output=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stderr.decode(errors="replace"))

    def test_video_cut_with_tone_to_silence_is_only_a_contrast_candidate(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "hard-cut-with-audio.mkv"
            self.render(source, with_audio=True)
            manifest = run_analysis(source, root / "runs", seconds=2, thumbnails=4,
                                    threshold=.12)
            result = build_av_cut_evidence(source, manifest)
            self.assertEqual(result["schemaVersion"], "kumiki.av-cut-evidence.v1")
            self.assertEqual(result["status"], "candidate-cross-stream-pts-association")
            self.assertEqual(result["videoCutCandidateCount"], 1)
            candidate, = result["cutCandidates"]
            self.assertEqual(candidate["status"], "candidate-quiet-level-contrast")
            self.assertLess(candidate["before"]["quietFrameFraction"],
                            candidate["after"]["quietFrameFraction"])
            self.assertEqual(result["qualityVerdict"], "not-performed")
            self.assertIn("no-independent-sync-verification", result["clockRelation"])

    def test_no_audio_stream_is_not_automatically_silence(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "hard-cut-video-only.mkv"
            self.render(source, with_audio=False)
            manifest = run_analysis(source, root / "runs", seconds=2, thumbnails=4)
            result = build_av_cut_evidence(source, manifest)
            self.assertEqual(result["status"], "no-audio-stream")
            self.assertEqual(result["cutCandidates"], [])
            self.assertIsNone(result["audioStreamIndex"])


if __name__ == "__main__":
    unittest.main()
