import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.analyzers.audio.levels import analyze_audio_levels
from kumiki_reference_lab.analyzers.shots.timeline_view import (
    _timing, build_timeline_view, render_timeline_html,
)
from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.analyze import run_analysis


def rat(n):
    return {"numerator": n, "denominator": 1}


def reports(*, audio=True):
    identity = {"sourceSha256": "a" * 64, "analysisRunSha256": "b" * 64}
    regions = [
        {"id": "region-001", "startSeconds": rat(0),
         "lastObservedFrameSeconds": rat(0), "observations": {"motion": None,
                                                          "appearance": None}},
        {"id": "region-002", "startSeconds": rat(1),
         "lastObservedFrameSeconds": rat(2), "observations": {
             "motion": {"meanGlobalImageDisplacementNormalized": .012},
             "appearance": {"meanDisplayLumaProxy": .32}}},
    ]
    shot = {**identity, "sourceTimebase": rat(1), "regions": regions}
    rhythm = {**identity, "sourceTimebase": rat(1), "videoCutCandidateCount": 1,
              "intervals": []}
    av = {**identity, "videoSourceTimebase": rat(1), "videoCutCandidateCount": 1,
          "audioStreamIndex": 1 if audio else None,
          "audioSourceTimebase": rat(1) if audio else None,
          "scanWindowSeconds": 2,
          "status": "candidate-cross-stream-pts-association" if audio else "no-audio-stream",
          "cutCandidates": ([{"videoRegionId": "region-002", "status": "candidate-quiet-level-contrast",
                              "before": {"quietFrameFraction": 0.0, "frameCount": 3},
                              "after": {"quietFrameFraction": 1.0, "frameCount": 4}}]
                            if audio else [])}
    onsets = {"sourceSha256": identity["sourceSha256"],
              "audioStreamIndex": 1 if audio else None,
              "sourceTimebase": rat(1) if audio else None,
              "scanWindowSeconds": 2,
              "status": ("source-pts-aligned-level-attack-candidates" if audio else
                         "no-audio-stream"),
              "candidates": ([{"id": "onset-001", "anchorSourcePts": 1,
                               "anchorSourceSeconds": rat(1),
                               "supportWindow": {"startSeconds": rat(0),
                                                 "endSeconds": rat(2)},
                               "measuredRmsRiseDb": 20.0,
                               "signal": "candidate-rms-rise"}] if audio else [])}
    return shot, rhythm, av, onsets


class TimelinePureTests(unittest.TestCase):
    def test_accessible_static_graph_and_escaped_source_name(self):
        rendered = render_timeline_html(*reports(), source_label='<script>alert("unsafe")</script>.mkv')
        self.assertIn('role="img"', rendered)
        self.assertIn('tabindex="0"', rendered)
        self.assertIn('<th scope="col">', rendered)
        self.assertIn("Image-plane motion", rendered)
        self.assertIn("Quiet-level contrast candidate", rendered)
        self.assertIn("Audio level attack candidate", rendered)
        self.assertIn("onset-001", rendered)
        self.assertIn("+20.0 dB", rendered)
        self.assertIn("0% (3 frames)", rendered)
        self.assertIn("100% (4 frames)", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("prefers-reduced-motion", rendered)

    def test_no_audio_reports_absence_and_no_fabricated_sound(self):
        rendered = render_timeline_html(*reports(audio=False), source_label="no-audio.mkv")
        self.assertIn("No audio stream", rendered)
        self.assertNotIn("Quiet-level contrast candidate</td>", rendered)

    def test_onset_outside_video_axis_is_listed_without_plotting_offscreen(self):
        shot, rhythm, av, onsets = reports()
        onsets["candidates"][0]["anchorSourceSeconds"] = rat(3)
        rendered = render_timeline_html(shot, rhythm, av, onsets, source_label="test.mkv")
        self.assertIn("onset-001", rendered)
        self.assertIn("In plotted video range", rendered)
        self.assertIn("<td>No</td>", rendered)
        self.assertNotIn('fill="#81e3b5"', rendered)

    def test_mismatched_run_and_cut_identity_are_rejected(self):
        shot, rhythm, av, onsets = reports()
        av["analysisRunSha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "sources or analysis runs disagree"):
            _timing(shot, rhythm, av, onsets)
        av["analysisRunSha256"] = "b" * 64
        av["cutCandidates"][0]["videoRegionId"] = "region-evil"
        with self.assertRaisesRegex(ValueError, "candidate identities disagree"):
            _timing(shot, rhythm, av, onsets)
        av["cutCandidates"][0]["videoRegionId"] = "region-002"
        onsets["sourceSha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "audio onset evidence identity"):
            _timing(shot, rhythm, av, onsets)

    def test_cli_command_and_require_output(self):
        args = build_parser().parse_args([
            "review-timeline", "source.mp4", "runs/analysis-run.json", "--out", "out",
        ])
        self.assertEqual(args.command, "review-timeline")
        self.assertEqual(args.window_ms, 400)
        with self.assertRaisesRegex(ValueError, "outside immutable"):
            build_timeline_view(Path("sample.mkv"), Path("my-run/analysis-run.json"),
                                Path("my-run/reviews"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe unavailable")
class TimelineIntegrationTests(unittest.TestCase):
    @staticmethod
    def render(root, *, with_audio):
        source = root / ("with-audio.mkv" if with_audio else "silent-video.mkv")
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1",
            "-f", "lavfi", "-i", "color=c=yellow:s=160x90:r=10:d=1",
        ]
        if with_audio:
            command += [
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000:duration=1",
                "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono:d=1",
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v];"
                                   "[2:a][3:a]concat=n=2:v=0:a=1[a]",
                "-map", "[v]", "-map", "[a]", "-c:v", "ffv1", "-c:a", "pcm_s16le",
            ]
        else:
            command += ["-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                        "-map", "[v]", "-c:v", "ffv1"]
        command.append(str(source))
        result = subprocess.run(command, capture_output=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stderr.decode(errors="replace"))
        return source

    def test_atomic_audio_video_timeline_reuse_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = self.render(root, with_audio=True)
            analysis = run_analysis(source, root / "runs", seconds=2, thumbnails=4,
                                    threshold=.12)
            with patch("kumiki_reference_lab.analyzers.shots.timeline_view.analyze_audio_levels",
                       wraps=analyze_audio_levels) as audio_decode:
                page = build_timeline_view(source, analysis, root / "timelines")
                audio_decode.assert_called_once()
            self.assertTrue(page.is_file())
            self.assertIn("Candidate cut intervals", page.read_text())
            self.assertIn("quiet before", page.read_text().lower())
            self.assertIn("100%", page.read_text())
            manifest = json.loads((page.parent / "timeline-review.json").read_text())
            self.assertEqual(manifest["schemaVersion"], "kumiki.timeline-review.v2")
            self.assertEqual(len(manifest["files"]), 5)
            self.assertTrue((page.parent / "audio-onsets.json").is_file())
            self.assertEqual(page, build_timeline_view(source, analysis, root / "timelines"))
            (page.parent / "audio-onsets.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "altered"):
                build_timeline_view(source, analysis, root / "timelines")

    def test_video_without_audio_is_a_truthful_empty_audio_track(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = self.render(root, with_audio=False)
            analysis = run_analysis(source, root / "runs", seconds=2, thumbnails=4)
            page = build_timeline_view(source, analysis, root / "timelines")
            self.assertIn("No audio stream", page.read_text())
            audio = json.loads((page.parent / "av-cut-evidence.json").read_text())
            self.assertEqual(audio["status"], "no-audio-stream")


if __name__ == "__main__":
    unittest.main()
