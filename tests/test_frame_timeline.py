import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from kumiki_reference_lab.analyzers.media.timeline import analyze_frame_timeline
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.contracts.frames import FramePts


class FrameTimelineTests(unittest.TestCase):
    def test_compact_pts_scan_preserves_negative_and_missing_values(self):
        stdout = ("pts=-9|best_effort_timestamp=-9\n"
                  "pts=0|best_effort_timestamp=0\n"
                  "pts=5|best_effort_timestamp=N/A\n"
                  "pts=N/A|best_effort_timestamp=N/A\n"
                  "pts=11|best_effort_timestamp=11\n")
        with patch("subprocess.run", return_value=CompletedProcess([], 0, stdout, "")):
            frames = read_frame_pts(Path("sample.mp4"), 1, seconds=3)
        self.assertEqual([f.pts for f in frames], [-9, 0, 5, None, 11])
        self.assertEqual(frames[2].origin, "pts-fallback")
        self.assertEqual(frames[3].origin, "missing")

    def test_duplicated_or_missing_pts_are_reported(self):
        manifest = {
            "source": {"sha256": "abc"},
            "video": {"streamIndex": 1,
                      "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }
        raw = [FramePts(0, -10, "best_effort_timestamp"),
               FramePts(1, 20, "best_effort_timestamp"),
               FramePts(2, 20, "best_effort_timestamp"),
               FramePts(3, None, "missing")]
        with patch("kumiki_reference_lab.analyzers.media.timeline.file_signature",
                   return_value=(0, 0, 0, 0)), patch(
            "kumiki_reference_lab.analyzers.media.timeline.require_unchanged"
        ), patch("kumiki_reference_lab.analyzers.media.timeline.inspect_source",
                   return_value=manifest), patch(
            "kumiki_reference_lab.analyzers.media.timeline.read_frame_pts", return_value=raw,
        ):
            report = analyze_frame_timeline(Path("sample.mp4"), seconds=3)
        self.assertEqual(report["frames"][0]["sourceSeconds"],
                         {"numerator": -1, "denominator": 100})
        self.assertEqual(report["frames"][1]["sourceSeconds"],
                         {"numerator": 1, "denominator": 50})
        self.assertEqual([a["reason"] for a in report["anomalies"]],
                         ["nonincreasing-source-pts", "missing-source-pts"])
        self.assertFalse(report["ptsDerivedFromFps"])

    def test_budget_guard(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 120"):
            read_frame_pts(Path("sample.mp4"), 0, seconds=0)
        with patch("subprocess.run", return_value=CompletedProcess(
            [], 0, "pts=1|best_effort_timestamp=1\n" * 3, "")):
            with self.assertRaisesRegex(ProbeError, "frame count"):
                read_frame_pts(Path("sample.mp4"), 0, max_frames=2)

    def test_detects_mutated_source_between_probe_and_pts_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.mp4"
            path.write_bytes(b"original")
            manifest = {"source": {"sha256": "abc"}, "video": {
                "sourceTimebase": {"numerator": 1, "denominator": 1000},
                "streamIndex": 0}}

            def mutate(*args, **kwargs):
                path.write_bytes(b"modified video bytes")
                return []

            with patch("kumiki_reference_lab.analyzers.media.timeline.inspect_source",
                       return_value=manifest), patch(
                "kumiki_reference_lab.analyzers.media.timeline.read_frame_pts",
                side_effect=mutate,
            ):
                with self.assertRaisesRegex(ValueError, "source changed"):
                    analyze_frame_timeline(path)


if __name__ == "__main__":
    unittest.main()
