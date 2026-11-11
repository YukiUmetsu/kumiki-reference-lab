"""Actual FFprobe/FFmpeg long-video seek preserves original PTS without prefix scan."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.pipeline.local_character_study import run_local_character_study
from kumiki_reference_lab.reviews.character_scene import load_character_scene
from kumiki_reference_lab.backends.ffmpeg.source_seek import (
    probe_source_window, decode_rgb_source_pts_seek, detect_source_window_cuts_seek,
)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg and FFprobe required for real long-window seek tests")
class OriginalPtsSourceSeekTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name) / "original-long-test.mp4"
        # Original synthetic video, 150s at just 5 FPS, tiny encode/size.
        # No third-party media, downloaded model or network access.
        p = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i",
            ("color=c=gray:s=160x90:r=5:d=150,"
             "drawbox=x=14:y=13:w=30:h=50:color=red:t=fill,"
             "drawbox=x=90:y=13:w=32:h=50:color=blue:t=fill"),
            "-c:v", "mpeg4", "-q:v", "8", "-pix_fmt", "yuv420p", str(cls.path),
        ], capture_output=True, timeout=35, check=False)
        if p.returncode:
            raise AssertionError("Could not synthesize local long-video seek test")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_seeks_well_after_prefix_cap_and_preserves_original_pts(self):
        result = probe_source_window(
            self.path, 0, timebase=Fraction(1, 10240),
            start_seconds=125, seconds=3,
        )
        self.assertEqual(result.first_source_pts, 0)
        self.assertEqual(result.start_seconds, 125)
        self.assertGreaterEqual(len(result.frames), 10)
        first = result.frames[0].pts
        self.assertEqual(first, 125 * 10240)
        pts = [result.frames[i].pts for i in (0, len(result.frames)//2, -1)]
        self.assertEqual(pts, sorted(set(pts)))
        images = decode_rgb_source_pts_seek(
            self.path, 0, pts, window=result, width=160, height=90)
        self.assertEqual(len(images), 3)
        self.assertTrue(all(len(frame) == 160*90*3 for frame in images))
        self.assertEqual(images[0], images[1])
        self.assertEqual(images[1], images[2])
        cuts = detect_source_window_cuts_seek(
            self.path, 0, window=result)
        self.assertEqual(cuts.timebase, Fraction(1, 10240))
        self.assertEqual(cuts.pts, ())

    def test_full_character_study_from_125_seconds_uses_real_seek_and_all_galleries(self):
        destination = Path(self.temp.name) / "late-character-study"
        def boxes(images, **kwargs):
            self.assertTrue(images[0].startswith(b"\x89PNG\r\n\x1a\n"))
            return {"subjects": [
                {"category": "animated-character", "box": [.05,.10,.25,.65]},
                {"category": "animated-character", "box": [.53,.10,.25,.65]},
            ]}
        def appearance(images, *, previous, **kwargs):
            return {
                "appearance": "A clear rectangular figure in a vivid colored outfit.",
                "visibleTraits": ["vivid rectangular silhouette"],
                "observedAction": "none", "motionEvidence": "",
            }
        def pair(images, **kwargs):
            self.assertEqual(len(images), 2)
            return {"actorColor": "none", "interaction": "none",
                    "visualEvidence": ""}
        with (
            patch(
                "kumiki_reference_lab.pipeline.ollama_subject_detection._ollama_json",
                side_effect=boxes,
            ),
            patch(
                "kumiki_reference_lab.pipeline.ollama_character_perception._ollama_chat",
                side_effect=appearance,
            ),
            patch(
                "kumiki_reference_lab.pipeline.local_character_interactions._ollama_json",
                side_effect=pair,
            ),
        ):
            path = run_local_character_study(
                self.path, destination, model="original-synthetic:1b",
                detector="ollama", start_seconds=125, max_seconds=3,
                max_samples=5, max_calls=10, max_pairs=4,
                width=160, height=90, timeout_seconds=10,
                review=True, interactions=True,
            )
        import json
        manifest = json.loads(path.read_text())
        self.assertEqual(manifest["sourceWindowEndSeconds"], 128)
        self.assertEqual(manifest["sourceDecodeMode"], "verified-seek-original-pts-v1")
        self.assertIsNone(manifest["scanPrefixSeconds"])
        self.assertEqual(manifest["provisionalTracklets"], 2)
        self.assertEqual(manifest["visionAppearanceProposals"], 10)
        detections = json.loads(
            (destination / "subject-detections.json").read_text())
        pts = [x["sourcePts"] for x in detections["frames"]]
        self.assertEqual(len(pts), 5)
        self.assertEqual(pts[0], 125*10240)
        self.assertTrue(all(125*10240 <= p < 128*10240 for p in pts))
        scene = load_character_scene(
            destination / "character-interactions" / "character-scene.json")
        self.assertEqual(scene["actions"], [])
        self.assertEqual(scene["utterances"], [])
        for gallery in ("tracklet-qa", "character-qa", "interaction-qa"):
            self.assertTrue((destination / gallery / "index.html").is_file())

    def test_late_off_grid_start_is_not_rounded_or_renumbered(self):
        result = probe_source_window(
            self.path, 0, timebase=Fraction(1, 10240),
            start_seconds=141, seconds=2,
        )
        self.assertEqual(result.frames[0].pts, 141*10240)
        self.assertTrue(all(
            141 <= Fraction(row.pts, 10240) < 143
            for row in result.frames))
        image = decode_rgb_source_pts_seek(
            self.path, 0, [result.frames[0].pts],
            window=result, width=160, height=90)
        self.assertEqual(len(image), 1)

    def test_does_not_fall_back_to_nearest_timestamp(self):
        result = probe_source_window(
            self.path, 0, timebase=Fraction(1, 10240),
            start_seconds=125, seconds=2,
        )
        with self.assertRaisesRegex(ValueError, "not verified"):
            decode_rgb_source_pts_seek(
                self.path, 0, [result.frames[0].pts + 1],
                window=result, width=160, height=90)
        with self.assertRaises(ValueError):
            decode_rgb_source_pts_seek(
                self.path, 0, [result.frames[1].pts, result.frames[0].pts],
                window=result, width=160, height=90)

    def test_bounded_source_window_inputs(self):
        for start, seconds in ((-1, 3), (0, 0), (3600, 1), (125, 31)):
            with self.subTest(start=start, seconds=seconds), self.assertRaises(ValueError):
                probe_source_window(
                    self.path, 0, timebase=Fraction(1, 10240),
                    start_seconds=start, seconds=seconds,
                )
        with self.assertRaises(ValueError):
            probe_source_window(
                self.path, 0, timebase=Fraction(0, 1),
                start_seconds=125, seconds=2,
            )

    def test_fail_closed_on_missing_window_without_guessed_pts(self):
        with self.assertRaisesRegex(ProbeError, "no source video frames"):
            probe_source_window(
                self.path, 0, timebase=Fraction(1, 10240),
                start_seconds=170, seconds=2,
            )


if __name__ == "__main__":
    unittest.main()
