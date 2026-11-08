import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.study import study_reference


CATALOG = Path(__file__).resolve().parents[1] / "catalog" / "entries"


class StudyCommandTests(unittest.TestCase):
    def test_cli_parses_study_command(self):
        args = build_parser().parse_args(["study-reference", "source.mp4", "--out", "runs"])
        self.assertEqual(args.command, "study-reference")
        self.assertEqual(args.max_seconds, 10)

    def test_invalid_study_budget_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "missing"
            with self.assertRaisesRegex(ValueError, "study seconds"):
                study_reference(Path("not-a-file"), output, seconds=50,
                                catalog_root=CATALOG)
            self.assertFalse(output.exists())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                     importlib.util.find_spec("numpy"),
                     "FFmpeg/FFprobe and NumPy required")
class StudyReferenceIntegrationTests(unittest.TestCase):
    def test_one_command_publishes_complete_reusable_gallery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
            output = root / "studies"
            gallery = study_reference(source, output, catalog_root=CATALOG,
                                      seconds=2, thumbnails=4)
            self.assertTrue(gallery.is_file())
            manifest = gallery.parents[2] / "study-manifest.json"
            report = json.loads(manifest.read_text())
            self.assertEqual(report["schemaVersion"], "kumiki.reference-study.v1")
            self.assertEqual(report["humanReviewStatus"], "unreviewed")
            self.assertEqual(report["qualityVerdict"], "not-performed")
            self.assertTrue((manifest.parent / report["artifacts"]["shotEvidence"]).is_file())
            self.assertTrue((manifest.parent / report["artifacts"]["techniqueProposals"]).is_file())
            self.assertEqual(study_reference(source, output, catalog_root=CATALOG,
                                             seconds=2, thumbnails=4), gallery)
            # Image review files are immutable; damage must be reported on reuse.
            gallery.write_text("modified", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing, altered or untracked"):
                study_reference(source, output, catalog_root=CATALOG,
                                seconds=2, thumbnails=4)
            self.assertEqual(len(list(output.glob("analysis/analysis-*"))), 1)


if __name__ == "__main__":
    unittest.main()
