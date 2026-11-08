import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from kumiki_reference_lab.analyzers.shots.detect import analyze_hard_cuts
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.backends.ffmpeg.scene import CutScan, detect_hard_cut_pts


SHOWINFO = ("[Parsed_showinfo_1] config in time_base: 1/15360, frame_rate: 30/1\n"
            "[Parsed_showinfo_1] n:   0 pts:  15360 pts_time:1\n")


class CutDetectionTests(unittest.TestCase):
    def test_parses_filter_timebase_and_cut_pts(self):
        with patch("subprocess.run", return_value=CompletedProcess([], 0, "", SHOWINFO)):
            scan = detect_hard_cut_pts(Path("sample.mp4"), 0, threshold=0.1)
        self.assertEqual(scan.timebase, Fraction(1, 15360))
        self.assertEqual(scan.pts, (15360,))

    def test_rejects_missing_or_conflicting_timebase(self):
        with patch("subprocess.run", return_value=CompletedProcess(
            [], 0, "", "[Parsed_showinfo_1] n: 0 pts: 12 pts_time:1\n")):
            with self.assertRaisesRegex(ProbeError, "timebase"):
                detect_hard_cut_pts(Path("sample.mp4"), 0)
        with patch("subprocess.run", return_value=CompletedProcess(
            [], 0, "", SHOWINFO + "[Parsed_showinfo_1] config in time_base: 1/1000\n")):
            with self.assertRaisesRegex(ProbeError, "timebase"):
                detect_hard_cut_pts(Path("sample.mp4"), 0)

    def test_rejects_nonfinite_threshold(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            detect_hard_cut_pts(Path("sample.mp4"), 0, threshold=float("nan"))

    def test_rejects_rescaled_filter_timestamps(self):
        manifest = {
            "source": {"sha256": "abc"},
            "video": {"streamIndex": 0,
                      "sourceTimebase": {"numerator": 1, "denominator": 90000}},
        }
        with patch("kumiki_reference_lab.analyzers.shots.detect.file_signature",
                   return_value=(0, 0, 0, 0)), patch(
            "kumiki_reference_lab.analyzers.shots.detect.require_unchanged"
        ), patch("kumiki_reference_lab.analyzers.shots.detect.inspect_source",
                   return_value=manifest), patch(
            "kumiki_reference_lab.analyzers.shots.detect.detect_hard_cut_pts",
            return_value=CutScan(Fraction(1, 15360), (15360,)),
        ):
            with self.assertRaisesRegex(ValueError, "changed timebase"):
                analyze_hard_cuts(Path("sample.mp4"))

    def test_detects_mutated_source_during_cut_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.mp4"
            path.write_bytes(b"original")
            manifest = {"source": {"sha256": "abc"}, "video": {
                "sourceTimebase": {"numerator": 1, "denominator": 1000},
                "streamIndex": 0}}

            def mutate(*args, **kwargs):
                path.write_bytes(b"modified video bytes")
                return CutScan(Fraction(1, 1000), ())

            with patch("kumiki_reference_lab.analyzers.shots.detect.inspect_source",
                       return_value=manifest), patch(
                "kumiki_reference_lab.analyzers.shots.detect.detect_hard_cut_pts",
                side_effect=mutate,
            ):
                with self.assertRaisesRegex(ValueError, "source changed"):
                    analyze_hard_cuts(path)


if __name__ == "__main__":
    unittest.main()
