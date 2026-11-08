import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError, probe_media


GOOD_PROBE = {
    "streams": [{"index": 0, "codec_type": "video", "codec_name": "h264",
                 "width": 1920, "height": 1080, "time_base": "1/90000",
                 "avg_frame_rate": "30000/1001", "r_frame_rate": "30/1"}],
    "format": {"duration": "1.001000"},
}


class InspectionTests(unittest.TestCase):
    def test_manifest_keeps_rational_rates_and_does_not_fake_frame_pts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.mp4"
            path.write_bytes(b"local test fixture")
            with patch("kumiki_reference_lab.analyzers.media.inspect.probe_media",
                       return_value=GOOD_PROBE):
                manifest = inspect_source(path)
            self.assertEqual(manifest["source"]["sha256"],
                             hashlib.sha256(b"local test fixture").hexdigest())
            self.assertEqual(manifest["source"]["fileName"], "sample.mp4")
            self.assertEqual(manifest["video"]["sourceTimebase"],
                             {"numerator": 1, "denominator": 90000})
            self.assertEqual(manifest["video"]["averageFrameRate"],
                             {"numerator": 30000, "denominator": 1001})
            self.assertFalse(manifest["timestamps"]["originalFramePtsExtracted"])
            self.assertNotIn(str(Path(directory)), json.dumps(manifest))

    def test_rejects_missing_file(self):
        with self.assertRaisesRegex(ValueError, "regular file"):
            inspect_source(Path("no-such-reference-video-test.mp4"))

    def test_rejects_missing_video_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio-only.wav"
            path.write_bytes(b"fixture")
            with patch("kumiki_reference_lab.analyzers.media.inspect.probe_media",
                       return_value={"streams": [{"codec_type": "audio"}]}):
                with self.assertRaisesRegex(ProbeError, "no video stream"):
                    inspect_source(path)

    def test_ignores_cover_art_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "with-cover.mp4"
            path.write_bytes(b"fixture")
            picture = {**GOOD_PROBE["streams"][0], "index": 0,
                       "disposition": {"attached_pic": 1}, "width": 640}
            actual = {**GOOD_PROBE["streams"][0], "index": 1, "width": 1920}
            with patch("kumiki_reference_lab.analyzers.media.inspect.probe_media",
                       return_value={"streams": [picture, actual]}):
                manifest = inspect_source(path)
            self.assertEqual(manifest["video"]["streamIndex"], 1)
            self.assertEqual(manifest["video"]["width"], 1920)

    def test_rejects_invalid_timebase(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.mp4"
            path.write_bytes(b"fixture")
            probe = {"streams": [{**GOOD_PROBE["streams"][0], "time_base": "0/0"}]}
            with patch("kumiki_reference_lab.analyzers.media.inspect.probe_media",
                       return_value=probe):
                with self.assertRaisesRegex(ProbeError, "timebase"):
                    inspect_source(path)

    def test_rejects_source_changed_while_inspecting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changing.mp4"
            path.write_bytes(b"initial")

            def change_source(source):
                source.write_bytes(b"a changed source")
                return "0" * 64

            with patch("kumiki_reference_lab.analyzers.media.inspect.probe_media",
                       return_value=GOOD_PROBE), patch(
                "kumiki_reference_lab.analyzers.media.inspect.sha256_file",
                side_effect=change_source,
            ):
                with self.assertRaisesRegex(ValueError, "source changed"):
                    inspect_source(path)

    def test_ffprobe_process_failure_does_not_expose_stderr(self):
        from subprocess import CompletedProcess
        with patch("subprocess.run", return_value=CompletedProcess(
            ["ffprobe"], 1, "", "private path or token")):
            with self.assertRaisesRegex(ProbeError, r"exit code 1") as error:
                probe_media(Path("some.mp4"))
            self.assertNotIn("private", str(error.exception))

    def test_ffprobe_invalid_json(self):
        from subprocess import CompletedProcess
        with patch("subprocess.run", return_value=CompletedProcess(
            ["ffprobe"], 0, "invalid", "")):
            with self.assertRaisesRegex(ProbeError, "invalid JSON"):
                probe_media(Path("some.mp4"))


if __name__ == "__main__":
    unittest.main()
