import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.techniques.propose import _cue
from kumiki_reference_lab.analyzers.techniques.review import (
    _review_html, build_technique_review,
)
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.analyze import run_analysis


CATALOG = Path(__file__).resolve().parents[1] / "catalog" / "entries"


class TechniqueReviewUnitTests(unittest.TestCase):
    def test_gallery_escapes_untrusted_source_names(self):
        rendered = _review_html("<script>alert(1)</script>.mp4", [], total_cues=0)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)

    def test_cli_parser_exposes_bounded_review_command(self):
        args = build_parser().parse_args([
            "review-techniques", "source.mp4", "run/analysis-run.json", "--out", "review"])
        self.assertEqual(args.command, "review-techniques")
        self.assertEqual(args.max_cues, 8)
        self.assertEqual(args.cue_offset, 0)

    def test_invalid_budget_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "output"
            with self.assertRaisesRegex(ValueError, "max_cues"):
                build_technique_review(Path("missing"), Path("missing"), out,
                                       catalog_root=CATALOG, max_cues=100)
            with self.assertRaisesRegex(ValueError, "cue_offset"):
                build_technique_review(Path("missing"), Path("missing"), out,
                                       catalog_root=CATALOG, cue_offset=100)
            self.assertFalse(out.exists())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe unavailable")
class TechniqueReviewIntegrationTests(unittest.TestCase):
    def _input(self, root: Path):
        source = root / "sample.mkv"
        process = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
            "-c:v", "ffv1", str(source),
        ], capture_output=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
        manifest = run_analysis(source, root / "runs", seconds=2, thumbnails=4)
        return source, manifest

    def test_no_cues_has_reviewable_empty_gallery_and_is_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, manifest = self._input(root)
            out = root / "review"
            index = build_technique_review(source, manifest, out, catalog_root=CATALOG)
            report = json.loads((index.parent / "technique-review.json").read_text())
            self.assertIn("No review cues", index.read_text())
            self.assertEqual(report["totalCandidateCount"], 0)
            self.assertEqual(report["cues"], [])
            self.assertEqual(len(report["files"]), 2)
            self.assertEqual(build_technique_review(source, manifest, out,
                                                    catalog_root=CATALOG), index)
            index.write_text("tampered")
            with self.assertRaisesRegex(ValueError, "hash changed"):
                build_technique_review(source, manifest, out, catalog_root=CATALOG)

    def test_proposed_cue_renders_three_verified_source_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, manifest = self._input(root)
            inspected = inspect_source(source)
            sha = inspected["source"]["sha256"]
            pts = [frame.pts for frame in read_frame_pts(source,
                   inspected["video"]["streamIndex"], seconds=2, ffprobe="ffprobe")]
            cue = _cue(
                technique_id="camera.motivated-macro-dolly",
                entry={"revision": 1, "_entrySha256": "f" * 64},
                source_sha=sha, start=pts[0], end=pts[-1], artifact="sparse-flow.json",
                measurements={"sampledPairCount": 2},
            )
            cue["visibleCueHypothesis"] = "<script>evil()</script>"
            proposals = {
                "source": {"sha256": sha,
                           "streamIndex": inspected["video"]["streamIndex"],
                           "sourceTimebase": inspected["video"]["sourceTimebase"]},
                "provenance": {"analysisRunSha256": sha256_file(manifest),
                               "catalogEntries": []},
                "candidates": [cue],
            }
            out = root / "gallery"
            with patch("kumiki_reference_lab.analyzers.techniques.review.propose_techniques",
                       return_value=proposals):
                index = build_technique_review(source, manifest, out,
                                               catalog_root=CATALOG)
                report = json.loads((index.parent / "technique-review.json").read_text())
                self.assertEqual([f["role"] for f in report["cues"][0]["images"]],
                                 ["start", "middle", "end"])
                self.assertEqual([f["sourcePts"] for f in report["cues"][0]["images"]],
                                 [pts[0], pts[4], pts[-1]])
                self.assertEqual(len(report["files"]), 5)
                self.assertIn("&lt;script&gt;", index.read_text())
                self.assertNotIn("<script>evil()", index.read_text())
                self.assertEqual(build_technique_review(source, manifest, out,
                                                        catalog_root=CATALOG), index)
                image = index.parent / report["cues"][0]["images"][1]["path"]
                image.write_bytes(b"broken")
                with self.assertRaisesRegex(ValueError, "hash changed"):
                    build_technique_review(source, manifest, out,
                                           catalog_root=CATALOG)

    def test_wrong_source_is_rejected_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, manifest = self._input(root)
            wrong_source = root / "wrong.mkv"
            wrong_source.write_bytes(source.read_bytes() + b"different-file")
            out = root / "gallery"
            with self.assertRaisesRegex(ValueError, "does not match"):
                build_technique_review(wrong_source, manifest, out, catalog_root=CATALOG)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
