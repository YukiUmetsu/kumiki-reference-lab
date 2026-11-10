"""Source-linked dense-flow review must expose evidence, never invent motion."""

import copy
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.motion.dense_review import (
    build_dense_flow_review, render_dense_review_html, select_dense_review_frames,
    validate_dense_review_report,
)
from kumiki_reference_lab.cli.app import main


def _sample_report():
    timebase = {"numerator": 1, "denominator": 1000}
    samples = [{"sampleOrdinal": i, "sourcePts": 100 * (i + 1),
                "sourceSeconds": {"numerator": i + 1, "denominator": 10}}
               for i in range(3)]
    rejected = {"low-texture": 90, "out-of-frame": 0,
                "roundtrip-inconsistent": 0, "implausible-displacement": 0,
                "appearance-inconsistent": 0}
    return {
        "schemaVersion": "kumiki.dense-flow.v1", "sourceSha256": "a" * 64,
        "sourceStreamIndex": 0, "sourceTimebase": timebase, "scanWindowSeconds": 2,
        "analyzer": {"resolution": {"width": 160, "height": 90},
                     "gridStepPixels": 12},
        "cutCandidatePts": [250],
        "samples": samples,
        "pairs": [
            {"startPts": 100, "endPts": 200,
             "deltaTimeSeconds": {"numerator": 1, "denominator": 10},
             "status": "insufficient-grid-support", "candidateCount": 91,
             "rejected": rejected,
             "vectors": [{"x": 30, "y": 30, "dx": 2.5, "dy": -1.25,
                          "roundtripErrorPixels": 0.3}],
             "acceptedFraction": 0.01099},
            {"startPts": 200, "endPts": 300,
             "deltaTimeSeconds": {"numerator": 1, "denominator": 10},
             "status": "cut-boundary", "candidateCount": 0,
             "rejected": {key: 0 for key in rejected}, "vectors": [],
             "acceptedFraction": 0.0},
        ],
    }


class DenseReviewValidationTests(unittest.TestCase):
    def test_preserves_original_pts_and_selects_cut_endpoints(self):
        report = _sample_report()
        width, height, samples, pairs = validate_dense_review_report(report)
        self.assertEqual((width, height, len(samples), len(pairs)), (160, 90, 3, 2))
        self.assertEqual(select_dense_review_frames(samples, pairs, 3), [0, 1, 2])

    def test_rejects_forged_pts_seconds_and_cut_vectors(self):
        for change in (lambda r: r["samples"][1].update({"sourcePts": 150}),
                       lambda r: r["pairs"][0].update({"endPts": 250}),
                       lambda r: r["pairs"][0].update({"deltaTimeSeconds":
                                                         {"numerator": 1, "denominator": 2}}),
                       lambda r: r.update({"cutCandidatePts": []}),
                       lambda r: r["pairs"][0].update({"status": []}),
                       lambda r: r["pairs"][1].update({"vectors":
                                                         copy.deepcopy(r["pairs"][0]["vectors"]) })):
            report = _sample_report()
            change(report)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_dense_review_report(report)

    def test_rejects_forged_grid_points_displacement_and_accounting(self):
        for change in (lambda r: r["pairs"][0]["vectors"][0].update({"x": 31}),
                       lambda r: r["pairs"][0]["vectors"][0].update({"dx": 400}),
                       lambda r: r["pairs"][0]["vectors"][0].update({"dx": float("nan")}),
                       lambda r: r["pairs"][0].update({"candidateCount": 90}),
                       lambda r: r["pairs"][0].update({"acceptedFraction": 0.5}),
                       lambda r: r["pairs"][0]["rejected"].update({"low-texture": 89}),
                       lambda r: r["pairs"][0].update({"status": "flow-observed"})):
            report = _sample_report()
            change(report)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_dense_review_report(report)

    def test_allows_only_quantization_slack_at_image_boundary(self):
        # The estimator bounds the unrounded endpoint, then rounds dx to 4 dp.
        # A valid endpoint at 153.99998 may therefore serialize as 154.0000.
        report = _sample_report()
        report["pairs"][0]["vectors"][0].update({"x": 150, "dx": 4.0, "dy": 0.0})
        validate_dense_review_report(report)
        report["pairs"][0]["vectors"][0]["dx"] = 4.001
        with self.assertRaises(ValueError):
            validate_dense_review_report(report)

    def test_html_shows_only_measured_pair_and_escapes_source_name(self):
        report = _sample_report()
        frames = [{"sampleIndex": i, "sourcePts": p, "seconds": p / 1000,
                   "path": f"frames/frame-{i:03d}.png"}
                  for i, p in enumerate((100, 200, 300))]
        page = render_dense_review_html("<script>alert(1)</script>", report, frames,
                                        160, 90)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)
        self.assertIn('x1="30.00"', page)
        self.assertIn('x2="32.50"', page)
        self.assertIn("cut-boundary", page)
        self.assertIn("not verified camera motion", page.lower())


@unittest.skipUnless(importlib.util.find_spec("cv2") and shutil.which("ffmpeg") and
                     shutil.which("ffprobe"), "OpenCV/FFmpeg unavailable")
class DenseReviewIntegrationTests(unittest.TestCase):
    def test_real_pts_gallery_cli_schema_reuse_and_corruption(self):
        from kumiki_reference_lab.analyzers.motion.dense import analyze_dense_flow

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mkv"
            proc = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode(errors="replace"))
            report = analyze_dense_flow(source, seconds=2, max_samples=8,
                                        threshold=0.95)
            report_path = root / "dense-flow.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            output = root / "reviews"
            self.assertEqual(main(["review-dense-flow", str(source), str(report_path),
                                   "--out", str(output), "--max-frames", "6"]), 0)
            gallery = next(output.glob("dense-flow-review-*/index.html"))
            self.assertEqual(build_dense_flow_review(source, report_path, output,
                                                     max_frames=6), gallery)
            manifest = json.loads((gallery.parent / "dense-flow-review.json").read_text())
            self.assertEqual(manifest["qualityVerdict"], "not-performed")
            self.assertEqual(manifest["humanReviewStatus"], "unreviewed")
            self.assertEqual(manifest["settings"]["sourceTimebase"], report["sourceTimebase"])
            self.assertEqual(manifest["settings"]["selectedFrames"][0]["sourcePts"],
                             report["samples"][0]["sourcePts"])
            if importlib.util.find_spec("jsonschema"):
                from jsonschema import Draft202012Validator
                schema = json.loads((Path(__file__).resolve().parents[1] /
                                     "schemas/v1/dense-flow-review.schema.json").read_text())
                Draft202012Validator.check_schema(schema)
                Draft202012Validator(schema).validate(manifest)
            image = next((gallery.parent / "frames").glob("*.png"))
            image.write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "modified|incomplete"):
                build_dense_flow_review(source, report_path, output, max_frames=6)

    def test_changed_source_or_forged_pts_never_publish_gallery(self):
        from kumiki_reference_lab.analyzers.motion.dense import analyze_dense_flow

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mkv"
            proc = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, timeout=30)
            self.assertEqual(proc.returncode, 0)
            report = analyze_dense_flow(source, seconds=2, max_samples=8,
                                        threshold=0.95)
            path, output = root / "report.json", root / "reviews"
            forged = copy.deepcopy(report)
            forged["samples"][1]["sourcePts"] += 1
            path.write_text(json.dumps(forged), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_dense_flow_review(source, path, output)
            self.assertFalse(output.exists())
            path.write_text(json.dumps(report), encoding="utf-8")
            source.write_bytes(source.read_bytes() + b"extra")
            with self.assertRaisesRegex(ValueError, "source does not match"):
                build_dense_flow_review(source, path, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
