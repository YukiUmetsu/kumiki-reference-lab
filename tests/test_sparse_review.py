import importlib.util
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from fractions import Fraction
from pathlib import Path

from kumiki_reference_lab.analyzers.motion.review import (
    _png_rgb, _render_html, _selection, _validate, build_sparse_flow_review,
)
from kumiki_reference_lab.analyzers.motion.sparse import analyze_sparse_flow
from kumiki_reference_lab.analyzers.motion.tracklets import build_sparse_tracklets


def _fixture():
    pairs = []
    for i in range(3):
        pairs.append({
            "startPts": i * 10, "endPts": (i + 1) * 10,
            "status": "single-image-translation-candidate",
            "vectors": [{"x": 20 + i * 2, "y": 30, "dx": 2, "dy": 0,
                         "group": "dominant"}],
        })
    return {
        "schemaVersion": "kumiki.sparse-flow.v1",
        "sourceSha256": "a" * 64,
        "sourceStreamIndex": 0,
        "sourceTimebase": {"numerator": 1, "denominator": 10},
        "scanWindowSeconds": 2,
        "analyzer": {"resolution": {"width": 160, "height": 90}},
        "samples": [{"sampleOrdinal": i, "sourcePts": i * 10}
                    for i in range(4)],
        "pairs": pairs,
        "temporalTracklets": build_sparse_tracklets(pairs, timebase=Fraction(1, 10)),
    }


class SparseReviewPureTests(unittest.TestCase):
    def test_rgb_png_has_valid_signature_crc_and_lossless_scanlines(self):
        width, height = 3, 2
        rgb = bytes(range(width * height * 3))
        data = _png_rgb(rgb, width, height)
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        cursor = 8
        chunks = {}
        while cursor < len(data):
            size = struct.unpack(">I", data[cursor:cursor+4])[0]
            kind = data[cursor+4:cursor+8]
            payload = data[cursor+8:cursor+8+size]
            crc = struct.unpack(">I", data[cursor+8+size:cursor+12+size])[0]
            self.assertEqual(zlib.crc32(kind + payload) & 0xffffffff, crc)
            chunks[kind] = payload
            cursor += 12 + size
        self.assertEqual(struct.unpack(">II", chunks[b"IHDR"][:8]), (3, 2))
        self.assertEqual(zlib.decompress(chunks[b"IDAT"]),
                         b"\0" + rgb[:9] + b"\0" + rgb[9:])
        with self.assertRaises(ValueError):
            _png_rgb(b"short", width, height)

    def test_report_validates_observation_origins_and_selected_indices(self):
        report = _fixture()
        width, height, samples, pairs, tracks = _validate(report)
        self.assertEqual((width, height, len(samples), len(pairs), len(tracks)),
                         (160, 90, 4, 3, 1))
        self.assertEqual(_selection(4, tracks, 3), [0, 2, 3])
        self.assertEqual(_selection(4, [], 4), [0, 1, 2, 3])

    def test_tampered_points_cut_pairs_and_tracklet_links_fail_closed(self):
        report = _fixture()
        report["pairs"][1]["vectors"][0]["dx"] = 300
        with self.assertRaisesRegex(ValueError, "leaves the analyzed image"):
            _validate(report)
        report = _fixture()
        report["pairs"][1]["status"] = "cut-boundary"
        with self.assertRaisesRegex(ValueError, "across a hard cut"):
            _validate(report)
        report = _fixture()
        report["temporalTracklets"]["tracklets"][0]["observations"][1]["vectorIndex"] = 10
        with self.assertRaisesRegex(ValueError, "nonadjacent evidence"):
            _validate(report)
        report = _fixture()
        report["samples"][2]["sourcePts"] = report["samples"][1]["sourcePts"]
        with self.assertRaisesRegex(ValueError, "not increasing"):
            _validate(report)

    def test_renderer_escapes_untrusted_labels_and_explains_uncertainty(self):
        report = _fixture()
        frames = [{"sampleIndex": 0, "sourcePts": 0, "seconds": 0.0,
                   "path": "frames/frame-000.png"},
                  {"sampleIndex": 3, "sourcePts": 30, "seconds": 3.0,
                   "path": "frames/frame-001.png"}]
        tracks = report["temporalTracklets"]["tracklets"]
        page = _render_html("<script>alert(1)</script>", report, frames, tracks,
                            160, 90, len(tracks))
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Image-plane motion does not verify", page)
        self.assertIn('viewBox="0 0 160 90"', page)
        self.assertIn("tracklet-0001", page)


@unittest.skipUnless(
    importlib.util.find_spec("numpy") and shutil.which("ffmpeg") and
    shutil.which("ffprobe"), "NumPy/FFmpeg unavailable",
)
class SparseReviewIntegrationTests(unittest.TestCase):
    def _video(self, path: Path, pattern: str = "testsrc2=s=160x90:r=10:d=1") -> None:
        process = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-f", "lavfi", "-i", pattern, "-c:v", "ffv1", str(path)],
            capture_output=True, timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))

    def test_real_source_frames_overlay_idempotent_and_tamper_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, report_path = root / "source.mkv", root / "sparse-flow.json"
            self._video(source)
            report = analyze_sparse_flow(source, seconds=2, max_samples=6)
            report_path.write_text(json.dumps(report), encoding="utf-8")
            runs = root / "runs"
            index = build_sparse_flow_review(source, report_path, runs, max_frames=4)
            page = index.read_text()
            self.assertIn("Motion paths on source frames", page)
            self.assertIn("Original source frame at PTS", page)
            manifest = json.loads((index.parent / "sparse-flow-review.json").read_text())
            self.assertEqual(manifest["humanReviewStatus"], "unreviewed")
            self.assertEqual(manifest["qualityVerdict"], "not-performed")
            self.assertEqual(len(manifest["settings"]["selectedFrames"]), 4)
            self.assertEqual(build_sparse_flow_review(
                source, report_path, runs, max_frames=4), index)
            frame = index.parent / "frames/frame-000.png"
            self.assertTrue(frame.read_bytes().startswith(b"\x89PNG"))
            frame.write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "incomplete or modified"):
                build_sparse_flow_review(source, report_path, runs, max_frames=4)

    def test_wrong_source_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "first.mkv"
            other = root / "other.mkv"
            self._video(source)
            self._video(other, "color=c=gray:s=160x90:r=10:d=1")
            report_path = root / "sparse-flow.json"
            report_path.write_text(json.dumps(analyze_sparse_flow(
                source, seconds=2, max_samples=5)), encoding="utf-8")
            runs = root / "runs"
            with self.assertRaisesRegex(ValueError, "does not match"):
                build_sparse_flow_review(other, report_path, runs)
            self.assertFalse(runs.exists())
            with self.assertRaisesRegex(ValueError, "max_frames"):
                build_sparse_flow_review(source, report_path, runs, max_frames=13)
            self.assertFalse(runs.exists())

    def test_fractional_candidate_vectors_remain_source_linked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mkv"
            self._video(source)
            report_path = root / "sparse-flow.json"
            report_path.write_text(json.dumps(analyze_sparse_flow(
                source, seconds=2, max_samples=6, subpixel_refinement=True)),
                encoding="utf-8")
            index = build_sparse_flow_review(source, report_path, root / "reviews")
            self.assertTrue(index.is_file())
            self.assertIn("not an artistic grade", index.read_text())


if __name__ == "__main__":
    unittest.main()
