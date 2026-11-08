"""Fast, FFmpeg-free provenance tests for post-render correction annotations."""

import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.integrations.kumiki.film_feedback import (
    init_film_feedback, validate_film_feedback,
)


class FilmFeedbackTests(unittest.TestCase):
    def make_review(self, root: Path) -> Path:
        bundle = root / "film-map-review-synthetic"
        for name in ("source", "film"):
            (bundle / name).mkdir(parents=True)
        (bundle / "index.html").write_text("<h1>test fixture only</h1>")
        (bundle / "source/frame-000.jpg").write_bytes(b"synthetic-source-still")
        (bundle / "film/frame-000.jpg").write_bytes(b"synthetic-render-still")
        pair = {
            "id": "focus-01", "relationship": "inspired-by", "note": "Original reference beat.",
            "source": {"pts": 10, "seconds": {"numerator": 1, "denominator": 10},
                       "image": "source/frame-000.jpg"},
            "film": {"frame": 3, "pts": 300, "seconds": {"numerator": 1, "denominator": 10},
                     "image": "film/frame-000.jpg"},
        }
        files = [
            {"path": filename, "sha256": sha256_file(bundle / filename)}
            for filename in ("index.html", "source/frame-000.jpg", "film/frame-000.jpg")
        ]
        settings = {"pairedIdentities": [pair],
                    "referenceVideoSha256": "a" * 64, "renderVideoSha256": "b" * 64}
        report = {"schemaVersion": "kumiki.film-map-review.v1",
                  "status": "verified-pts-paired-stills", "qualityVerdict": "not-performed",
                  "pairs": [pair], "settings": settings, "files": files}
        manifest = bundle / "film-map-review.json"
        manifest.write_text(json.dumps(report, indent=2))
        return manifest

    def test_template_has_exact_evidence_and_empty_unapproved_findings(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            manifest = self.make_review(root)
            feedback_path = init_film_feedback(
                manifest, root / "feedback", reviewer_kind="human", reviewer_id="editor-1")
            draft = json.loads(feedback_path.read_text())
            self.assertEqual(draft["findings"], [])
            self.assertEqual(draft["evidence"]["reviewManifestSha256"], sha256_file(manifest))
            self.assertEqual(draft["evidence"]["anchors"][0]["id"], "focus-01")
            self.assertEqual(draft["evidence"]["anchors"][0]["filmFrame"], 3)
            result = validate_film_feedback(manifest, feedback_path)
            self.assertEqual(result["artisticApproval"], "not-granted")
            self.assertEqual(result["findingCount"], 0)
            with self.assertRaises((ValueError, FileExistsError)):
                init_film_feedback(manifest, root / "feedback", reviewer_kind="human",
                                   reviewer_id="editor-2")

    def test_editor_notes_are_validated_but_never_automatically_approved(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            manifest = self.make_review(root)
            feedback_path = init_film_feedback(
                manifest, root / "feedback", reviewer_kind="human", reviewer_id="editor-1")
            draft = json.loads(feedback_path.read_text())
            draft["findings"] = [{
                "id": "finding-camera-mismatch", "anchorId": "focus-01",
                "category": "camera", "severity": "significant",
                "observation": "Camera angle obscures the causal explanation.",
                "suggestedChange": "Raise the camera and keep the main subject visible.",
            }]
            feedback_path.write_text(json.dumps(draft))
            result = validate_film_feedback(manifest, feedback_path)
            self.assertEqual(result["severityCounts"]["significant"], 1)
            self.assertEqual(result["artisticApproval"], "not-granted")
            draft["reviewStatus"] = "approved"
            feedback_path.write_text(json.dumps(draft))
            with self.assertRaisesRegex(ValueError, "approval"):
                validate_film_feedback(manifest, feedback_path)

    def test_stale_image_and_forged_anchor_are_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            manifest = self.make_review(root)
            feedback_path = init_film_feedback(
                manifest, root / "feedback", reviewer_kind="ai", reviewer_id="agent-1",
                model_id="local-model")
            draft = json.loads(feedback_path.read_text())
            draft["findings"] = [{
                "id": "finding-timing", "anchorId": "not-in-review",
                "category": "timing", "severity": "polish",
                "observation": "Motion is abrupt.", "suggestedChange": "Ease out the movement.",
            }]
            feedback_path.write_text(json.dumps(draft))
            with self.assertRaisesRegex(ValueError, "outside"):
                validate_film_feedback(manifest, feedback_path)
            (manifest.parent / "film/frame-000.jpg").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "modified"):
                validate_film_feedback(manifest, feedback_path)

    def test_immutable_review_directory_cannot_hold_feedback(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            manifest = self.make_review(root)
            with self.assertRaisesRegex(ValueError, "outside"):
                init_film_feedback(manifest, manifest.parent, reviewer_kind="human",
                                   reviewer_id="editor-1")
            args = build_parser().parse_args([
                "film-feedback", "validate", "film-map-review.json", "film-map-feedback.json"])
            self.assertEqual(args.feedback_action, "validate")


if __name__ == "__main__":
    unittest.main()
