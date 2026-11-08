"""Exercise actual FFmpeg decoding through review on original synthetic footage."""

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.shots.evidence import build_shot_evidence
from kumiki_reference_lab.analyzers.techniques.propose import propose_techniques
from kumiki_reference_lab.analyzers.techniques.review import build_technique_review
from kumiki_reference_lab.pipeline.analyze import run_analysis
from kumiki_reference_lab.pipeline.study import study_reference
from kumiki_reference_lab.reviews.notes import review_notes_template, validate_review_notes


CATALOG = Path(__file__).resolve().parents[1] / "catalog" / "entries"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                     importlib.util.find_spec("numpy"),
                     "FFmpeg/FFprobe and NumPy extra required")
class OriginalVideoTechniqueEndToEndTests(unittest.TestCase):
    @staticmethod
    def _encode_rgb_frames(output: Path, frames: bytes, *, frame_count: int) -> None:
        if len(frames) != 160 * 90 * 3 * frame_count:
            raise AssertionError("synthetic frame payload has an invalid size")
        result = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "160x90",
            "-framerate", "10", "-i", "pipe:0", "-c:v", "ffv1", str(output),
        ], input=frames, capture_output=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stderr.decode(errors="replace"))

    @staticmethod
    def _moving_bright_square(output: Path) -> None:
        """Constant bright area translating across a dark background.

        Ground truth is an animated bright object, *not* a physical moving light.
        """
        width, height = 160, 90
        frames = bytearray()
        for frame_index in range(10):
            x0, y0 = 10 + frame_index * 11, 35
            for y in range(height):
                for x in range(width):
                    pixel = 245 if x0 <= x < x0 + 16 and y0 <= y < y0 + 16 else 30
                    frames.extend((pixel, pixel, pixel))
        OriginalVideoTechniqueEndToEndTests._encode_rgb_frames(
            output, bytes(frames), frame_count=10)

    @staticmethod
    def _smooth_enlargement(output: Path) -> None:
        """A purely digital enlargement with identifiable smoothly shaded marks."""
        import numpy as np

        rng = np.random.default_rng(102)
        y, x = np.mgrid[0:90, 0:160]
        spots = [(float(rng.uniform(12, 148)), float(rng.uniform(10, 80)),
                  float(rng.uniform(2.0, 4.0)), float(rng.uniform(80, 180)))
                 for _ in range(95)]
        frames = bytearray()
        for index in range(8):
            scale = 1.0 + 0.055 * index
            sx = 80 + (x - 80) / scale
            sy = 45 + (y - 45) / scale
            image = np.full((90, 160), 24.0, dtype=np.float64)
            for px, py, radius, value in spots:
                image += value * np.exp(-((sx - px) ** 2 + (sy - py) ** 2) /
                                        (2 * radius * radius))
            gray = np.clip(image, 0, 245).astype(np.uint8)
            frames.extend(np.repeat(gray[:, :, None], 3, axis=2).tobytes())
        OriginalVideoTechniqueEndToEndTests._encode_rgb_frames(
            output, bytes(frames), frame_count=8)

    @staticmethod
    def _two_color_edits(output: Path) -> None:
        blue = bytes((10, 30, 235)) * (160 * 90)
        yellow = bytes((235, 225, 10)) * (160 * 90)
        OriginalVideoTechniqueEndToEndTests._encode_rgb_frames(
            output, blue * 5 + yellow * 5, frame_count=10)

    def test_bright_object_yields_review_cue_not_a_physical_light_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "moving-bright-object.mkv"
            self._moving_bright_square(source)
            run = run_analysis(source, root / "runs", seconds=2, thumbnails=4,
                               appearance=True, appearance_samples=10)
            proposals = propose_techniques(run, CATALOG)
            self.assertEqual(len(proposals["candidates"]), 1)
            cue = proposals["candidates"][0]
            self.assertEqual(cue["techniqueId"], "lighting.softbox-curvature-reveal")
            self.assertEqual(cue["interpretationStatus"], "review-required-not-verified")
            self.assertIn("bright object", " ".join(cue["plausibleAlternatives"]).lower())
            magnitude = cue["evidence"]["measurements"][
                "brightCentroidDisplacementMagnitudeNormalized"]
            self.assertGreater(magnitude, 0.5)
            self.assertLess(magnitude, 0.8)

            gallery = build_technique_review(source, run, root / "review", catalog_root=CATALOG)
            gallery_data = json.loads((gallery.parent / "technique-review.json").read_text())
            self.assertEqual(len(gallery_data["cues"]), 1)
            self.assertEqual(len(gallery_data["cues"][0]["images"]), 3)
            self.assertIn("Other explanations", gallery.read_text())

            evidence = build_shot_evidence(run)
            self.assertEqual(len(evidence["regions"]), 1)
            self.assertEqual(evidence["regions"][0]["observations"]
                             ["appearance"]["sampleCount"], 10)
            self.assertIsNone(evidence["regions"][0]["endPtsExclusive"])

            # The higher-level user workflow must preserve this same evidence
            # and generate a visual cue sheet without pretending it found a light.
            study_gallery = study_reference(source, root / "complete-study",
                                            catalog_root=CATALOG, seconds=2,
                                            thumbnails=4)
            study_manifest = json.loads(
                (study_gallery.parent / "study-manifest.json").read_text())
            self.assertEqual(study_manifest["humanReviewStatus"], "unreviewed")
            self.assertEqual(study_manifest["qualityVerdict"], "not-performed")
            self.assertIn("Shot storyboard", study_gallery.read_text())
            technique_gallery = study_gallery.parent / study_manifest["artifacts"]["reviewGallery"]
            self.assertIn("Other explanations", technique_gallery.read_text())
            # A reviewer may explicitly reject the *light* interpretation,
            # without mutating the reported bright-centroid observation.
            study_root = study_gallery.parent
            study_cues = json.loads((study_root / "technique-proposals.json").read_text())
            self.assertEqual(len(study_cues["candidates"]), 1)
            study_cue = study_cues["candidates"][0]
            draft_path = review_notes_template(
                study_root / "study-manifest.json", root / "notes",
                reviewer_kind="human", reviewer_id="test-director")
            draft = json.loads(draft_path.read_text())
            draft["annotations"] = [{
                "id": "note-bright-object",
                "target": {"kind": "cue", "id": study_cue["id"]},
                "category": "lighting",
                "layer": "visual-hypothesis",
                "statement": "The moving bright square is an animated object, not a light.",
                "confidence": "high",
                "assessment": "contradicts",
                "evidenceFrames": [
                    {"sourcePts": study_cue["sourcePtsRange"]["startPts"],
                     "description": "Original bright square on a flat dark background."},
                ],
                "uncertainties": ["A visual analysis cannot establish the authoring software."],
            }]
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            result = validate_review_notes(study_root / "study-manifest.json", draft_path)
            self.assertEqual(result["layers"], {"visual-hypothesis": 1})
            self.assertEqual(result["semanticStatus"], "not-verified")

    def test_digital_enlargement_does_not_get_misnamed_as_recovered_dolly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "digital-magnification.mkv"
            self._smooth_enlargement(source)
            run = run_analysis(source, root / "runs", seconds=2, thumbnails=4,
                               sparse_flow=True, sparse_samples=8, sparse_points=64,
                               sparse_correlation=.63)
            proposals = propose_techniques(run, CATALOG)
            proposals_by_id = {cue["techniqueId"]: cue
                               for cue in proposals["candidates"]}
            self.assertIn("camera.motivated-macro-dolly", proposals_by_id)
            cue = proposals_by_id["camera.motivated-macro-dolly"]
            self.assertIn("Digital crop", " ".join(cue["plausibleAlternatives"]))
            self.assertEqual(cue["interpretationStatus"], "review-required-not-verified")

    def test_real_shot_candidate_split_keeps_correct_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "two-color-edits.mkv"
            self._two_color_edits(source)
            run = run_analysis(source, root / "runs", seconds=2, thumbnails=4,
                               threshold=.12)
            report = build_shot_evidence(run)
            self.assertEqual(report["status"], "candidate-edit-regions")
            self.assertEqual(len(report["regions"]), 2)
            first, second = report["regions"]
            self.assertEqual((first["frameCount"], second["frameCount"]), (5, 5))
            self.assertEqual(first["endPtsExclusive"], second["startPtsInclusive"])
            self.assertEqual(first["boundaryAfter"], "hard-cut-candidate")
            self.assertEqual(second["boundaryBefore"], "hard-cut-candidate")


if __name__ == "__main__":
    unittest.main()
