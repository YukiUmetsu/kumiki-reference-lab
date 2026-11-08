import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from kumiki_reference_lab.analyzers.media.contact_sheet import (
    build_contact_sheet, select_evidence_indices,
)
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.backends.ffmpeg.thumbnails import extract_thumbnails
from kumiki_reference_lab.contracts.frames import FramePts


class EvidenceSelectionTests(unittest.TestCase):
    def test_sampling_covers_ends_and_cut_boundaries(self):
        frames = [FramePts(i, i * 100, "best_effort_timestamp") for i in range(30)]
        selection = select_evidence_indices(frames, (1000, 2000), 8)
        self.assertLessEqual(len(selection), 8)
        self.assertIn("opening", selection[0])
        self.assertIn("closing", selection[29])
        self.assertIn("cut-before", selection[9])
        self.assertIn("cut-after", selection[10])
        self.assertIn("cut-before", selection[19])
        self.assertIn("cut-after", selection[20])

    def test_missing_pts_do_not_generate_fake_timestamps(self):
        frames = [FramePts(0, None, "missing"), FramePts(1, -20, "pts"),
                  FramePts(2, None, "missing"), FramePts(3, 40, "pts")]
        self.assertEqual(set(select_evidence_indices(frames, (), 4)), {1, 3})
        with self.assertRaisesRegex(ProbeError, "valid source PTS"):
            select_evidence_indices([FramePts(0, None, "missing")], (), 4)

    def test_input_budgets(self):
        with self.assertRaises(ValueError):
            select_evidence_indices([FramePts(0, 0, "pts")], (), 50)

    def test_thumbnail_backend_does_not_accept_unverified_pts(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("subprocess.run", return_value=CompletedProcess(
                [], 0, "", "[Parsed_showinfo_1] config in time_base: 1/1000\n"
                               "[Parsed_showinfo_1] n: 0 pts: 111 pts_time:0.111\n"
            )):
                from fractions import Fraction
                with self.assertRaisesRegex(ProbeError, "did not match"):
                    extract_thumbnails(Path("source.mp4"), Path(directory), 0,
                                       [0], seconds=1, width=320,
                                       expected_timebase=Fraction(1, 1000), expected_pts=[100])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg binaries unavailable")
class ContactSheetIntegrationTests(unittest.TestCase):
    def test_real_two_shot_video_is_reviewable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "red-blue.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=red:s=160x90:r=10:d=1",
                "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1",
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[out]",
                "-map", "[out]", "-c:v", "ffv1", str(source),
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            target = root / "runs"
            index = build_contact_sheet(source, target, seconds=2, limit=8,
                                        width=240, threshold=0.1)
            self.assertTrue(index.is_file())
            manifest = json.loads((index.parent / "contact-sheet.json").read_text())
            entries = manifest["evidenceFrames"]
            self.assertGreaterEqual(len(entries), 2)
            self.assertTrue(all((index.parent / e["image"]).is_file() for e in entries))
            self.assertIn("opening", entries[0]["roles"])
            self.assertIn("closing", entries[-1]["roles"])
            self.assertEqual(build_contact_sheet(source, target, seconds=2, limit=8,
                                                 width=240, threshold=0.1), index)
            # Corrupted evidence must be detected, never silently overwritten.
            (index.parent / entries[0]["image"]).write_bytes(b"not an image")
            with self.assertRaisesRegex(ValueError, "modified images"):
                build_contact_sheet(source, target, seconds=2, limit=8,
                                    width=240, threshold=0.1)

    def test_variable_frame_rate_contact_sheet_retains_source_pts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "vfr.mkv"
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=1",
                "-vf", "setpts='if(lt(N,5),N,N*2)/(10*TB)'", "-fps_mode", "vfr",
                "-c:v", "ffv1", str(source),
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            index = build_contact_sheet(source, root / "out", seconds=2,
                                        limit=10, width=240, threshold=0.8)
            manifest = json.loads((index.parent / "contact-sheet.json").read_text())
            entries = manifest["evidenceFrames"]
            self.assertEqual(len(entries), 10)
            source_times = [entry["sourceSeconds"]["numerator"] /
                            entry["sourceSeconds"]["denominator"] for entry in entries]
            self.assertGreater(max(b - a for a, b in zip(source_times, source_times[1:])),
                               min(b - a for a, b in zip(source_times, source_times[1:])))


if __name__ == "__main__":
    unittest.main()
