import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.cli.app import main


class CliTests(unittest.TestCase):
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
