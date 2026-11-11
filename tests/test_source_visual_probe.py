"""Source-PTS visual proxies: real FFmpeg image, color, cut, and abstention checks."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.appearance.source_visual_probe import (
    SCHEMA_VERSION, _frame_delta, _frame_metrics,
    analyze_source_visual_window, write_source_visual_probe,
)
from kumiki_reference_lab.cli.app import build_parser


class VisualProxyMathTests(unittest.TestCase):
    def test_full_frame_rgb_luma_is_explicitly_display_referred(self):
        red = bytes([255,0,0])*(64*36)
        data = _frame_metrics(red, width=64, height=36)
        self.assertAlmostEqual(data["meanDisplayLumaProxy"], 0.2126, places=4)
        self.assertEqual(data["meanSaturationProxy"], 1.0)
        self.assertEqual(data["shadowPixelFraction"], 0)
        self.assertEqual(data["brightPixelFraction"], 0)
        self.assertEqual(data["meanRgb"], [1.0,0.0,0.0])
        self.assertEqual(_frame_delta(red, red), 0)
        self.assertAlmostEqual(
            _frame_delta(red, bytes([0,0,255])*(64*36)), 2/3, places=5)
        with self.assertRaisesRegex(ValueError, "wrong size"):
            _frame_metrics(red[:-1], width=64, height=36)

    def test_rejects_invalid_budget_without_model_or_video(self):
        for argument in (
            {"start_seconds": True}, {"start_seconds": -1},
            {"start_seconds": 3599, "seconds": 3}, {"seconds": 0},
            {"seconds": 31}, {"max_samples": 4}, {"max_samples": 25},
            {"width": 20}, {"height": 400}, {"cut_threshold": float("nan")},
            {"cut_threshold": True},
        ):
            with self.subTest(argument=argument), self.assertRaises(ValueError):
                analyze_source_visual_window(
                    Path("not-a-film.mp4"), **argument)

    def test_command_parses_intended_source_start_and_cuts(self):
        args = build_parser().parse_args([
            "source-visual-probe", "my-video.mp4", "--out", "local-out",
            "--start-seconds", "125", "--max-seconds", "3",
            "--max-samples", "8", "--cut-threshold", "0.2",
        ])
        self.assertEqual(args.command, "source-visual-probe")
        self.assertEqual(args.start_seconds, 125)
        self.assertEqual(args.cut_threshold, 0.2)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Real FFmpeg + FFprobe required")
class RealVisualProxyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/"original-red-blue.mp4"
        self.out = self.root/"visual-probe"
        result = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=red:s=160x90:r=5:d=2",
            "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=5:d=2",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map", "[v]", "-c:v", "mpeg4", "-q:v", "5",
            "-pix_fmt", "yuv420p", str(self.source),
        ], capture_output=True, timeout=20, check=False)
        if result.returncode:
            self.fail("Could not synthesize original two-color FFmpeg clip")

    def test_real_rgb_cut_provenance_and_unreviewed_measurement(self):
        path = write_source_visual_probe(
            self.source, self.out, start_seconds=0, seconds=4,
            max_samples=10, width=160, height=90,
            rights_status="user-declared-authorized")
        result = json.loads(path.read_text())
        self.assertEqual(result["schemaVersion"], SCHEMA_VERSION)
        self.assertEqual(result["scan"]["decoder"], "source-prefix-ordinal-pts-v1")
        self.assertEqual(result["scan"]["sampledSourcePtsCount"], 10)
        self.assertEqual(result["rightsStatus"], "user-declared-authorized")
        self.assertEqual(result["sourceTimebase"], {"numerator":1, "denominator":10240})
        self.assertGreaterEqual(len(result["cutCandidatePts"]), 1)
        self.assertTrue(any(x["status"]=="cut-candidate-between-samples"
                            for x in result["sampledFramePairs"]))
        self.assertTrue(any(
            x["meanAbsoluteDisplayRgbDelta"] is None
            for x in result["sampledFramePairs"]))
        lumas = [x["appearance"]["meanDisplayLumaProxy"]
                 for x in result["sampledFrames"]]
        self.assertGreater(max(lumas), min(lumas))
        self.assertIn("not-human-reviewed", result["evidenceStatus"])
        self.assertNotIn(str(self.root), path.read_text())
        with self.assertRaisesRegex(ValueError, "new nonexisting"):
            write_source_visual_probe(self.source, self.out, seconds=4)

    def test_later_short_window_preserves_nonzero_source_pts(self):
        data = analyze_source_visual_window(
            self.source, start_seconds=2, seconds=2,
            max_samples=5, width=160, height=90)
        self.assertEqual(data["scan"]["decoder"], "source-prefix-ordinal-pts-v1")
        pts = [x["sourcePts"] for x in data["sampledFrames"]]
        self.assertTrue(all(p>=2*10240 for p in pts))
        self.assertEqual(pts, sorted(set(pts)))
        self.assertLessEqual(
            data["sampledWindowSummary"]["cutCandidateCountBetweenFirstAndLastSample"], 1)


if __name__ == "__main__":
    unittest.main()
