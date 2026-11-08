import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.shots.gallery import build_shot_gallery
from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.analyze import run_analysis
from tests import test_technique_end_to_end as fixture_videos


class ShotGalleryUnitTests(unittest.TestCase):
    def test_cli_parser_and_bad_budgets(self):
        args = build_parser().parse_args([
            "review-shots", "original.mp4", "analysis-run.json", "--out", "review",
            "--max-regions", "4", "--region-offset", "1",
        ])
        self.assertEqual((args.max_regions, args.region_offset), (4, 1))
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "do-not-create"
            with self.assertRaisesRegex(ValueError, "max_regions"):
                build_shot_gallery(Path("missing"), Path("missing"), target,
                                   max_regions=20)
            self.assertFalse(target.exists())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                     importlib.util.find_spec("numpy"),
                     "FFmpeg/FFprobe and NumPy required")
class ShotGalleryIntegrationTests(unittest.TestCase):
    def test_two_regions_have_true_original_frames_without_invented_end(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "two-color-edits.mkv"
            fixture_videos.OriginalVideoTechniqueEndToEndTests._two_color_edits(source)
            analysis = run_analysis(source, root / "runs",
                                    seconds=2, thumbnails=4, threshold=.12)
            gallery = build_shot_gallery(source, analysis, root / "gallery",
                                         max_regions=8)
            self.assertTrue(gallery.is_file())
            report = json.loads((gallery.parent / "shot-gallery.json").read_text())
            self.assertEqual(report["schemaVersion"], "kumiki.shot-gallery.v1")
            self.assertEqual(report["totalRegionCount"], 2)
            self.assertEqual(len(report["regions"]), 2)
            self.assertEqual([len(x["images"]) for x in report["regions"]], [3, 3])
            a, b = report["regions"]
            self.assertEqual(a["evidence"]["endPtsExclusive"],
                             b["evidence"]["startPtsInclusive"])
            self.assertIsNone(b["evidence"]["endPtsExclusive"])
            self.assertEqual(a["images"][0]["sourcePts"],
                             a["evidence"]["startPtsInclusive"])
            self.assertEqual(a["images"][-1]["sourcePts"],
                             a["evidence"]["lastObservedFramePts"])
            self.assertIn("unknown: bounded scan ended", gallery.read_text())
            self.assertEqual(len(list((gallery.parent / "frames").glob("*.jpg"))), 6)
            self.assertEqual(build_shot_gallery(source, analysis, root / "gallery"), gallery)
            gallery.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing, altered or untracked"):
                build_shot_gallery(source, analysis, root / "gallery")

    def test_gallery_is_useful_even_without_a_technique_cue(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "flat-edits.mkv"
            fixture_videos.OriginalVideoTechniqueEndToEndTests._two_color_edits(source)
            analysis = run_analysis(source, root / "runs",
                                    seconds=2, thumbnails=4, threshold=.12)
            gallery = build_shot_gallery(source, analysis, root / "pages",
                                         max_regions=1, region_offset=1)
            report = json.loads((gallery.parent / "shot-gallery.json").read_text())
            self.assertEqual(report["totalRegionCount"], 2)
            self.assertEqual([r["id"] for r in report["regions"]], ["region-002"])
            self.assertEqual(report["qualityVerdict"], "not-performed")
            alternate = root / "different-source.mkv"
            fixture_videos.OriginalVideoTechniqueEndToEndTests._moving_bright_square(alternate)
            with self.assertRaisesRegex(ValueError, "differs from verified analysis"):
                build_shot_gallery(alternate, analysis, root / "wrong-source")


if __name__ == "__main__":
    unittest.main()
