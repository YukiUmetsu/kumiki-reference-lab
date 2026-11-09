import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.cli.app import main


class CliTests(unittest.TestCase):
    def test_review_roi_cli_passes_bounded_options(self):
        with patch("kumiki_reference_lab.cli.app.build_roi_review",
                   return_value=Path("/tmp/example/index.html")) as builder:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["review-roi", "reference.mkv", "track.json",
                                       "--out", "reviews", "--max-frames", "7"]), 0)
        self.assertEqual(builder.call_args.kwargs["max_frames"], 7)

    def test_output_is_idempotent_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            source.write_bytes(b"test")
            out = Path(directory) / "output"
            with patch("kumiki_reference_lab.cli.app.inspect_source",
                       return_value={"schemaVersion": "test"}):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["inspect", str(source), "--out", str(out)]), 0)
                    self.assertEqual(main(["inspect", str(source), "--out", str(out)]), 0)
                manifest = out / "source-manifest.json"
                self.assertIn("test", manifest.read_text())
                self.assertEqual(list(out.glob("*.tmp")), [])
                manifest.write_text("user-owned content")
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    self.assertEqual(main(["inspect", str(source), "--out", str(out)]), 2)
                self.assertEqual(manifest.read_text(), "user-owned content")


if __name__ == "__main__":
    unittest.main()
