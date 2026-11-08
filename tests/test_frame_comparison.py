import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.comparison.frames import build_frame_comparison


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg binaries unavailable")
class FrameComparisonTests(unittest.TestCase):
    def _clip(self, source: Path, vfr: bool = False) -> None:
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                   "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=1"]
        if vfr:
            command += ["-vf", "setpts='if(lt(N,5),N,N*2)/(10*TB)'", "-fps_mode", "vfr"]
        command += ["-c:v", "ffv1", str(source)]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_identical_videos_produce_timecoded_side_by_side_jpegs_and_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference, candidate = root / "reference.mkv", root / "render.mkv"
            self._clip(reference)
            shutil.copyfile(reference, candidate)
            output = root / "runs"
            index = build_frame_comparison(reference, candidate, output,
                                           reference_anchor_ms=0, candidate_anchor_ms=0,
                                           tolerance_ms=0, seconds=2, samples=6, width=320)
            report = json.loads((index.parent / "frame-comparison.json").read_text())
            self.assertEqual(report["schemaVersion"], "kumiki.frame-comparison.v1")
            self.assertEqual(report["qualityVerdict"], "not-performed")
            self.assertEqual(report["matchedPairs"], 6)
            self.assertIn("Aligned reference and render frames", index.read_text())
            self.assertEqual(len(report["files"]), 13)
            for pair in report["pairs"]:
                a, b = index.parent / pair["referenceImage"], index.parent / pair["candidateImage"]
                self.assertEqual(a.read_bytes(), b.read_bytes())
                self.assertEqual(pair["signedAlignmentErrorSeconds"]["numerator"], 0)
            self.assertEqual(build_frame_comparison(reference, candidate, output,
                                                    reference_anchor_ms=0,
                                                    candidate_anchor_ms=0,
                                                    tolerance_ms=0, seconds=2,
                                                    samples=6, width=320), index)

    def test_mutated_frame_cannot_be_reused_silently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mkv"
            self._clip(source)
            index = build_frame_comparison(source, source, root / "runs",
                                           reference_anchor_ms=0, candidate_anchor_ms=0,
                                           seconds=2, samples=5)
            report = json.loads((index.parent / "frame-comparison.json").read_text())
            image = index.parent / report["pairs"][0]["referenceImage"]
            image.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "modified"):
                build_frame_comparison(source, source, root / "runs",
                                       reference_anchor_ms=0, candidate_anchor_ms=0,
                                       seconds=2, samples=5)

    def test_mutated_pts_metadata_is_rejected_even_when_jpegs_are_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mkv"
            self._clip(source)
            index = build_frame_comparison(source, source, root / "runs",
                                           reference_anchor_ms=0, candidate_anchor_ms=0,
                                           seconds=2, samples=5)
            path = index.parent / "frame-comparison.json"
            report = json.loads(path.read_text())
            report["pairs"][0]["referencePts"] += 10
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "PTS evidence"):
                build_frame_comparison(source, source, root / "runs",
                                       reference_anchor_ms=0, candidate_anchor_ms=0,
                                       seconds=2, samples=5)

    def test_no_alignment_or_invalid_budget_never_publishes_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mkv"
            self._clip(source)
            out = root / "runs"
            with self.assertRaisesRegex(ValueError, "no frames fall"):
                build_frame_comparison(source, source, out,
                                       reference_anchor_ms=0, candidate_anchor_ms=5000,
                                       tolerance_ms=0, seconds=2, samples=5)
            self.assertFalse(out.exists())
            with self.assertRaisesRegex(ValueError, "sample limit"):
                build_frame_comparison(source, source, out,
                                       reference_anchor_ms=0, candidate_anchor_ms=0,
                                       seconds=2, samples=100)
            self.assertFalse(out.exists())

    def test_vfr_candidate_preserves_exact_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ref, candidate = root / "ref.mkv", root / "vfr.mkv"
            self._clip(ref)
            self._clip(candidate, vfr=True)
            index = build_frame_comparison(ref, candidate, root / "runs",
                                           reference_anchor_ms=0, candidate_anchor_ms=0,
                                           tolerance_ms=300, seconds=2, samples=8)
            report = json.loads((index.parent / "frame-comparison.json").read_text())
            self.assertGreater(report["matchedPairs"], 1)
            self.assertEqual(len({pair["candidatePts"] for pair in report["pairs"]}),
                             report["matchedPairs"])
            self.assertEqual(len({pair["referencePts"] for pair in report["pairs"]}),
                             report["matchedPairs"])


if __name__ == "__main__":
    unittest.main()
