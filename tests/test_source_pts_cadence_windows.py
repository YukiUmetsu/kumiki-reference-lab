"""Windowed visual cadence preserves source PTS and rejects mixed boundaries."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock

from kumiki_reference_lab.analyzers.appearance.analyze import analyze_appearance
from kumiki_reference_lab.analyzers.comparison.visual_cadence import summarize_visual_cadence
from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.motion.analyze import analyze_image_motion
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.cli.app import main


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "requires local FFmpeg/FFprobe, not hosted CI")
class SourcePtsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.source = Path(cls.temp.name) / "original.mkv"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                        "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=6:duration=37",
                        "-c:v", "ffv1", "-an", str(cls.source)], check=True, timeout=30)
        cls.inspected = inspect_source(cls.source)
        rational = cls.inspected["video"]["sourceTimebase"]
        cls.timebase = Fraction(rational["numerator"], rational["denominator"])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_late_window_keeps_original_frame_ordinals_and_source_pts(self):
        prefix = read_frame_pts(self.source, 0, seconds=5)
        chosen = read_frame_pts(self.source, 0, seconds=5, start_seconds=25,
                                source_timebase=self.timebase)
        self.assertEqual(prefix[0].ordinal, 0)
        self.assertGreater(chosen[0].ordinal, prefix[-1].ordinal)
        self.assertGreaterEqual(chosen[0].pts * self.timebase, 25)
        self.assertLess(chosen[-1].pts * self.timebase, 30)
        self.assertEqual(chosen[0].ordinal, 150)

    def test_windowed_motion_and_appearance_share_immutable_original_identity(self):
        motion = analyze_image_motion(self.source, seconds=5, start_seconds=25,
                                      max_samples=12)
        appearance = analyze_appearance(self.source, seconds=5, start_seconds=25,
                                        max_samples=12)
        self.assertEqual(motion["sourceSha256"], self.inspected["source"]["sha256"])
        self.assertEqual(motion["sourceSha256"], appearance["sourceSha256"])
        self.assertEqual(motion["sourceTimebase"], appearance["sourceTimebase"])
        self.assertEqual(motion["scanStartSeconds"], 25)
        self.assertEqual(appearance["scanStartSeconds"], 25)
        self.assertEqual(motion["coverage"], "bounded-source-window-not-necessarily-full-video")
        self.assertGreaterEqual(motion["samples"][0]["sourcePts"] * self.timebase, 25)
        self.assertGreaterEqual(appearance["samples"][0]["sourcePts"] * self.timebase, 25)
        report = summarize_visual_cadence(motion, appearance)
        self.assertEqual(report["scanStartSeconds"], 25)
        self.assertGreater(report["imagePlaneMotion"]["sampledSpanSeconds"], 3)
        mismatched = copy.deepcopy(appearance)
        mismatched["scanStartSeconds"] = 20
        with self.assertRaisesRegex(ValueError, "same source window start"):
            summarize_visual_cadence(motion, mismatched)
        mismatched["scanStartSeconds"] = 25
        mismatched["coverage"] = "bounded-from-start-not-necessarily-full-video"
        with self.assertRaisesRegex(ValueError, "coverage"):
            summarize_visual_cadence(motion, mismatched)

    def test_legacy_zero_offset_stays_backward_compatible(self):
        motion = analyze_image_motion(self.source, seconds=3, max_samples=10)
        appearance = analyze_appearance(self.source, seconds=3, max_samples=10)
        self.assertNotIn("scanStartSeconds", motion)
        self.assertNotIn("scanStartSeconds", appearance)
        self.assertEqual(motion["coverage"], "bounded-from-start-not-necessarily-full-video")
        self.assertNotIn("scanStartSeconds", summarize_visual_cadence(motion, appearance))

    def test_invalid_window_and_missing_source_timebase_rejected(self):
        with self.assertRaisesRegex(ValueError, "timebase"):
            read_frame_pts(self.source, 0, seconds=5, start_seconds=25)
        with self.assertRaisesRegex(ValueError, "120"):
            analyze_image_motion(self.source, seconds=10, start_seconds=111)
        with self.assertRaisesRegex(ValueError, "120"):
            analyze_appearance(self.source, seconds=10, start_seconds=111)
        with self.assertRaisesRegex(ValueError, "start_seconds"):
            analyze_appearance(self.source, seconds=5, start_seconds=-1)
        # An unanchored first frame makes "25s from source start" ambiguous.
        fake = subprocess.CompletedProcess(
            args=["ffprobe"], returncode=0,
            stdout="pts=N/A|best_effort_timestamp=N/A\npts=100|best_effort_timestamp=100\n",
            stderr="")
        with mock.patch("kumiki_reference_lab.backends.ffmpeg.frames.subprocess.run",
                        return_value=fake):
            with self.assertRaisesRegex(ProbeError, "timestamped opening frame"):
                read_frame_pts(self.source, 0, seconds=5, start_seconds=2,
                               source_timebase=self.timebase)

    def test_cli_accepts_explicit_source_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for kind, filename in (("motion", "image-motion.json"),
                                   ("appearance", "appearance.json")):
                result = main([kind, str(self.source), "--start-seconds", "20",
                               "--max-seconds", "3", "--max-samples", "9",
                               "--out", str(out / kind)])
                self.assertEqual(result, 0)
                report = json.loads((out / kind / filename).read_text(encoding="utf-8"))
                self.assertEqual(report["scanStartSeconds"], 20)


if __name__ == "__main__":
    unittest.main()
