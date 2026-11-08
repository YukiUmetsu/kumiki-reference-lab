import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.pipeline.analyze import run_analysis


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe binaries unavailable")
class AnalysisPipelineIntegrationTests(unittest.TestCase):
    def _flat_video(self, source: Path) -> None:
        process = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
            "-c:v", "ffv1", str(source),
        ], capture_output=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))

    def test_transactional_analysis_creates_complete_bundle_and_reuses_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            output = root / "runs"
            manifest_path = run_analysis(source, output, seconds=2, thumbnails=5)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["interpretationStatus"], "not-performed")
            self.assertEqual(manifest["catalogProposals"], [])
            self.assertEqual(set(manifest["artifacts"]), {"inspect", "frames", "cuts", "contactSheet"})
            for relative in manifest["artifacts"].values():
                self.assertTrue((manifest_path.parent / relative).is_file())
            self.assertEqual(run_analysis(source, output, seconds=2, thumbnails=5),
                             manifest_path)
            self.assertEqual(len(list(output.glob("analysis-*"))), 1)
            self.assertGreaterEqual(len(manifest["files"]), 7)

    def test_corruption_blocks_idempotent_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            output = root / "runs"
            manifest_path = run_analysis(source, output, seconds=2)
            manifest = json.loads(manifest_path.read_text())
            image = next(item["path"] for item in manifest["files"]
                         if item["path"].endswith(".jpg"))
            (manifest_path.parent / image).write_bytes(b"corruption")
            with self.assertRaisesRegex(ValueError, "missing or modified"):
                run_analysis(source, output, seconds=2)

    def test_modified_run_metadata_cannot_claim_interpretation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            output = root / "runs"
            manifest_path = run_analysis(source, output, seconds=2)
            manifest = json.loads(manifest_path.read_text())
            manifest["interpretationStatus"] = "complete"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "altered stage metadata"):
                run_analysis(source, output, seconds=2)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy extra unavailable")
    def test_motion_run_is_integrated_and_failed_roi_never_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            result = run_analysis(source, root / "good", seconds=2, motion=True,
                                  samples=10)
            manifest = json.loads(result.read_text())
            self.assertIn("motion", manifest["artifacts"])
            self.assertTrue((result.parent / "image-motion.json").is_file())

            failed_output = root / "failed"
            with self.assertRaisesRegex(ValueError, "insufficient texture"):
                run_analysis(source, failed_output, seconds=2,
                             roi=(0.2, 0.2, 0.1, 0.2), samples=10)
            self.assertEqual(list(failed_output.iterdir()), [])

    def test_invalid_budget_does_not_create_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs"
            with self.assertRaisesRegex(ValueError, "between 1 and 30"):
                run_analysis(Path("missing.mp4"), output, seconds=200)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
