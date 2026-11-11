"""A tiny REAL FFmpeg round-trip for the character study's source PTS pipeline.

Unlike mocked unit tests, this checks actual media probing, source-timecoded
decode, sample selection, cut candidates, region crops and all QA gallery
rendering. Only the private local VLM service is mocked.

Runs in seconds on standard CI; no source video/download/model weights are needed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.pipeline.local_character_study import run_local_character_study
from kumiki_reference_lab.reviews.character_scene import load_character_scene


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg and FFprobe required for local real-media smoke")
class RealVideoCharacterStudySmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.video = self.root / "synthetic-two-subjects.mp4"
        self.out = self.root / "character-study"
        # Entirely original synthetic media: two large colored geometric boxes
        # on a constant background; no external clips or copyrighted footage.
        # MPEG4 encoding avoids optional proprietary codec dependencies.
        result = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i",
            ("color=c=gray:s=160x90:r=5:d=2,"
             "drawbox=x=10:y=18:w=30:h=50:color=red:t=fill,"
             "drawbox=x=100:y=12:w=28:h=56:color=blue:t=fill"),
            "-c:v", "mpeg4", "-q:v", "4", "-pix_fmt", "yuv420p",
            str(self.video),
        ], timeout=20, text=True, capture_output=True, check=False)
        if result.returncode:
            self.fail("Failed to synthesize the original synthetic FFmpeg fixture")

    @staticmethod
    def local_boxes(images, **kwargs):
        if len(images) != 1 or not images[0].startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("local detector was not given real encoded PNG frame")
        return {
            "subjects": [
                {"category": "animated-character", "box": [0.05, 0.15, 0.24, 0.60]},
                {"category": "animated-character", "box": [0.60, 0.10, 0.24, 0.65]},
            ],
        }

    @staticmethod
    def local_appearance(images, *, previous, **kwargs):
        if not all(x.startswith(b"\x89PNG\r\n\x1a\n") for x in images):
            raise ValueError("character crops must be real PNGs")
        return {
            "appearance": "A stylized colored rectangular figure with clear silhouette.",
            "visibleTraits": ["solid-colored surface", "rectangular silhouette"],
            "observedAction": "none",
            "motionEvidence": "",
        }

    @staticmethod
    def local_interaction(images, **kwargs):
        if len(images) != 2 or not all(
            x.startswith(b"\x89PNG\r\n\x1a\n") for x in images
        ):
            raise ValueError("interaction frame pair must be real PNG images")
        return {
            "actorColor": "none", "interaction": "none", "visualEvidence": "",
        }

    def run_full(self, *, interactions=True):
        with (
            patch(
                "kumiki_reference_lab.pipeline.ollama_subject_detection._ollama_json",
                side_effect=self.local_boxes,
            ) as detection_calls,
            patch(
                "kumiki_reference_lab.pipeline.ollama_character_perception._ollama_chat",
                side_effect=self.local_appearance,
            ) as vision_calls,
            patch(
                "kumiki_reference_lab.pipeline.local_character_interactions._ollama_json",
                side_effect=self.local_interaction,
            ) as interaction_calls,
        ):
            result = run_local_character_study(
                self.video, self.out, model="synthetic-local-vision:1b",
                detector="ollama", max_seconds=2, max_samples=5,
                max_calls=10, max_pairs=4, width=160, height=90,
                timeout_seconds=10, review=True, interactions=interactions,
            )
        return result, (
            detection_calls.call_count, vision_calls.call_count,
            interaction_calls.call_count,
        )

    def test_full_real_pts_decode_and_original_qa_galleries(self):
        result, calls = self.run_full()
        manifest = json.loads(result.read_text(encoding="utf-8"))
        self.assertEqual(manifest["sourceSha256"], sha256_file(self.video))
        self.assertEqual(manifest["status"], "completed-unverified-model-proposals")
        self.assertEqual(manifest["detectorBackend"], "ollama")
        self.assertEqual(manifest["provisionalTracklets"], 2)
        self.assertEqual(manifest["detectedRegionProposals"], 10)
        self.assertEqual(manifest["visionAppearanceProposals"], 10)
        self.assertEqual(calls, (5, 10, 4))
        self.assertEqual(manifest["provisionalCharacterIdsObserved"], 2)
        detections = json.loads(
            (self.out / manifest["paths"]["detections"]).read_text(encoding="utf-8"))
        pts = [frame["sourcePts"] for frame in detections["frames"]]
        self.assertEqual(len(pts), 5)
        self.assertEqual(pts, sorted(set(pts)))
        self.assertEqual(detections["sourceTimebase"], {"numerator": 1, "denominator": 10240})
        scene = load_character_scene(self.out / manifest["paths"]["interactions"])
        self.assertEqual(scene["actions"], [])
        self.assertEqual(scene["utterances"], [])
        self.assertEqual(scene["identityClaims"], [])
        for key in ("trackletQa", "characterQa", "interactionQa"):
            self.assertTrue((self.out / manifest["paths"][key]).is_file())
        qa_frames = list((self.out / "character-qa" / "frames").glob("*.png"))
        self.assertTrue(qa_frames)
        self.assertTrue(all(
            frame.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
            for frame in qa_frames
        ))
        self.assertEqual(json.loads(
            (self.out / "interaction-qa" / "interaction-feedback.json").read_text()
        )["pairs"][0]["verdict"], "pending")

    def test_later_window_preserves_original_pts_through_all_galleries(self):
        with (
            patch(
                "kumiki_reference_lab.pipeline.ollama_subject_detection._ollama_json",
                side_effect=self.local_boxes,
            ),
            patch(
                "kumiki_reference_lab.pipeline.ollama_character_perception._ollama_chat",
                side_effect=self.local_appearance,
            ),
            patch(
                "kumiki_reference_lab.pipeline.local_character_interactions._ollama_json",
                side_effect=self.local_interaction,
            ),
        ):
            path = run_local_character_study(
                self.video, self.out, model="synthetic-local-vision:1b",
                start_seconds=1, max_seconds=1, max_samples=5,
                max_calls=10, max_pairs=4, width=160, height=90,
                timeout_seconds=10, review=True, interactions=True,
            )
        manifest = json.loads(path.read_text())
        self.assertEqual(manifest["scanStartSeconds"], 1)
        self.assertEqual(manifest["scanPrefixSeconds"], 2)
        predictions = json.loads(
            (self.out / "subject-detections.json").read_text())
        frame_pts = [x["sourcePts"] for x in predictions["frames"]]
        self.assertEqual(len(frame_pts), 5)
        self.assertEqual(frame_pts[0], 10240)
        self.assertTrue(all(10240 <= x < 20480 for x in frame_pts))
        scene = load_character_scene(
            self.out / "character-vision" / "character-scene.json")
        self.assertGreaterEqual(scene["window"]["startPts"], frame_pts[0])
        self.assertEqual(len(scene["appearances"]), 10)
        for key in ("trackletQa", "characterQa", "interactionQa"):
            self.assertTrue((self.out / manifest["paths"][key]).is_file())

    def test_vision_error_leaves_no_partial_study(self):
        def no_model(*args, **kwargs):
            raise ValueError("vision model unavailable")
        with (
            patch(
                "kumiki_reference_lab.pipeline.ollama_subject_detection._ollama_json",
                side_effect=self.local_boxes,
            ),
            patch(
                "kumiki_reference_lab.pipeline.ollama_character_perception._ollama_chat",
                side_effect=no_model,
            ),
        ):
            with self.assertRaisesRegex(ValueError, "model unavailable"):
                run_local_character_study(
                    self.video, self.out, model="synthetic-local-vision:1b",
                    max_seconds=2, max_samples=5, width=160, height=90,
                )
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
