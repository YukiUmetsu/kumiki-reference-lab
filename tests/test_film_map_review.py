import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.core.timebase import as_rational_dict
from kumiki_reference_lab.integrations.kumiki.film_map_review import build_film_map_review
from kumiki_reference_lab.cli.app import build_parser


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe required for local visual evidence")
class FilmMapReviewTests(unittest.TestCase):
    def test_cli_accepts_explicit_review_map_and_render(self):
        args = build_parser().parse_args([
            "review-film-map", "mapping.json", "film.json", "reference.mp4", "render.mp4",
            "--out", "review-runs", "--max-seconds", "12", "--width", "320",
        ])
        self.assertEqual(args.command, "review-film-map")
        self.assertEqual(args.max_seconds, 12)
        self.assertEqual(args.render, Path("render.mp4"))

    def setup_videos(self, root: Path):
        source, render = root / "reference.mkv", root / "render.mkv"
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
               "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=1",
               "-c:v", "ffv1", str(source)]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        shutil.copyfile(source, render)
        film = root / "authored.film.json"
        film_data = {"schemaVersion": 1, "id": "author-test", "fps": {"num": 10, "den": 1},
                     "scenes": [{"id": "scene-a", "durationFrames": 10}]}
        film.write_text(json.dumps(film_data) + "\n")
        stream = inspect_source(source)["video"]
        frames = read_frame_pts(source, stream["streamIndex"], seconds=2)
        timebase = Fraction(**stream["sourceTimebase"])
        anchors = []
        for ordinal in (1, 3):
            frame = frames[ordinal]
            time = as_rational_dict(frame.pts * timebase)
            anchors.append({
                "id": f"step-{ordinal}", "relationship": "inspired-by",
                "note": "Compare the authored transformation against this source beat.",
                "reviewStatus": "not-reviewed",
                "source": {"sourcePts": frame.pts, "seconds": time},
                "film": {"sceneId": "scene-a", "frameOffset": ordinal, "frame": ordinal,
                         "seconds": as_rational_dict(Fraction(ordinal, 10))},
            })
        mapping = {"schemaVersion": "kumiki.reference-film-map.v1",
                   "status": "editorial-anchor-plan-not-a-visual-match",
                   "provenance": {
                       "referenceVideoSha256": sha256_file(source),
                       "authoredFilmSha256": sha256_file(film),
                       "handoffSha256": "f" * 64,
                   }, "film": {"id": "author-test", "fps": {"num": 10, "den": 1},
                               "durationFrames": 10},
                   "anchors": anchors}
        map_path = root / "reference-film-map.json"
        map_path.write_text(json.dumps(mapping, indent=2))
        return source, render, film, map_path, mapping

    def test_exact_pts_and_film_ordinals_create_reusable_side_by_side_evidence(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            source, render, film, map_path, _ = self.setup_videos(root)
            out = root / "runs"
            index = build_film_map_review(map_path, film, source, render, out,
                                          seconds=2, width=320)
            self.assertTrue(index.is_file())
            self.assertIn("Source ↔ authored film", index.read_text())
            report = json.loads((index.parent / "film-map-review.json").read_text())
            self.assertEqual(report["schemaVersion"], "kumiki.film-map-review.v1")
            self.assertEqual(report["qualityVerdict"], "not-performed")
            self.assertEqual(len(report["pairs"]), 2)
            self.assertEqual(len(report["files"]), 5)
            for pair in report["pairs"]:
                self.assertEqual((index.parent / pair["source"]["image"]).read_bytes(),
                                 (index.parent / pair["film"]["image"]).read_bytes())
            self.assertEqual(build_film_map_review(map_path, film, source, render,
                                                   out, seconds=2, width=320), index)

            image = index.parent / report["pairs"][0]["film"]["image"]
            image.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "modified"):
                build_film_map_review(map_path, film, source, render,
                                      out, seconds=2, width=320)

    def test_stale_film_or_wrong_source_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            source, render, film, map_path, mapping = self.setup_videos(root)
            out = root / "runs"
            film.write_text('{"schemaVersion":1,"id":"modified"}\n')
            with self.assertRaisesRegex(ValueError, "stale"):
                build_film_map_review(map_path, film, source, render, out, seconds=2)
            self.assertFalse(out.exists())

            film.write_text(json.dumps({"schemaVersion": 1, "id": "author-test",
                                        "fps": {"num": 10, "den": 1},
                                        "scenes": [{"id": "scene-a", "durationFrames": 10}]}) + "\n")
            mapping["provenance"]["referenceVideoSha256"] = "0" * 64
            map_path.write_text(json.dumps(mapping))
            with self.assertRaisesRegex(ValueError, "source bytes"):
                build_film_map_review(map_path, film, source, render, out, seconds=2)
            self.assertFalse(out.exists())

    def test_bad_film_frame_time_or_reused_source_pts_is_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            source, render, film, map_path, mapping = self.setup_videos(root)
            out = root / "runs"
            mapping["anchors"][0]["film"]["seconds"] = {"numerator": 1, "denominator": 9}
            map_path.write_text(json.dumps(mapping))
            with self.assertRaisesRegex(ValueError, "scene clock"):
                build_film_map_review(map_path, film, source, render, out, seconds=2)
            mapping["anchors"][0]["film"]["seconds"] = {"numerator": 1, "denominator": 10}
            mapping["anchors"][1]["source"] = mapping["anchors"][0]["source"].copy()
            map_path.write_text(json.dumps(mapping))
            with self.assertRaisesRegex(ValueError, "unique and monotonically"):
                build_film_map_review(map_path, film, source, render, out, seconds=2)
            self.assertFalse(out.exists())

    def test_forged_scene_offset_or_declared_fps_is_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            source, render, film, map_path, mapping = self.setup_videos(root)
            out = root / "runs"
            mapping["anchors"][0]["film"]["frameOffset"] = 5
            map_path.write_text(json.dumps(mapping))
            with self.assertRaisesRegex(ValueError, "scene clock"):
                build_film_map_review(map_path, film, source, render, out, seconds=2)
            mapping["anchors"][0]["film"]["frameOffset"] = 1
            mapping["film"]["fps"] = {"num": 24, "den": 1}
            map_path.write_text(json.dumps(mapping))
            with self.assertRaisesRegex(ValueError, "identity/FPS"):
                build_film_map_review(map_path, film, source, render, out, seconds=2)
            self.assertFalse(out.exists())

    def test_no_anchors_or_excessive_scan_budget_is_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            source, render, film, map_path, mapping = self.setup_videos(root)
            out = root / "runs"
            mapping["anchors"] = []
            map_path.write_text(json.dumps(mapping))
            with self.assertRaisesRegex(ValueError, "bounded"):
                build_film_map_review(map_path, film, source, render, out)
            with self.assertRaisesRegex(ValueError, "1..120"):
                build_film_map_review(map_path, film, source, render, out, seconds=121)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
