import contextlib
import io
import json
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

    def test_track_roi_loads_bounded_manual_reseed_file(self):
        with tempfile.TemporaryDirectory() as directory:
            reseeds = Path(directory) / "reseeds.json"
            anchors = [{"sourcePts": 700, "box": [0.2, 0.3, 0.15, 0.2]}]
            reseeds.write_text(json.dumps(anchors), encoding="utf-8")
            with patch("kumiki_reference_lab.cli.app.analyze_roi_track",
                       return_value={"schemaVersion": "test"}) as tracker:
                with contextlib.redirect_stdout(io.StringIO()):
                    code = main(["track-roi", "video.mkv", "--box", "0.1", "0.2", "0.15", "0.2",
                                 "--reseeds", str(reseeds)])
                self.assertEqual(code, 0)
                self.assertEqual(tracker.call_args.kwargs["reseeds"], anchors)

    def test_cli_rejects_oversized_reseed_file_without_tracking(self):
        with tempfile.TemporaryDirectory() as directory:
            reseeds = Path(directory) / "reseeds.json"
            reseeds.write_text(" " * 33000, encoding="utf-8")
            with patch("kumiki_reference_lab.cli.app.analyze_roi_track") as tracker:
                with contextlib.redirect_stderr(io.StringIO()):
                    code = main(["track-roi", "video.mkv", "--box", "0.1", "0.2", "0.15", "0.2",
                                 "--reseeds", str(reseeds)])
                self.assertEqual(code, 2)
                tracker.assert_not_called()

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
