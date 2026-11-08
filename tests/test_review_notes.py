import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.cli.app import build_parser, main
from kumiki_reference_lab.pipeline.study import study_reference
from kumiki_reference_lab.reviews.notes import review_notes_template, validate_review_notes


CATALOG = Path(__file__).resolve().parents[1] / "catalog" / "entries"


class ReviewNotesUnitTests(unittest.TestCase):
    def test_cli_parses_init_and_validation(self):
        args = build_parser().parse_args([
            "review-notes", "init", "study-manifest.json", "--out", "reviews",
            "--reviewer-kind", "ai", "--reviewer-id", "local-agent",
            "--model-id", "offline-model",
        ])
        self.assertEqual(args.reviewer_kind, "ai")
        self.assertEqual(args.model_id, "offline-model")
        check = build_parser().parse_args([
            "review-notes", "validate", "study-manifest.json", "review-notes.json",
        ])
        self.assertEqual(check.review_notes_action, "validate")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                     importlib.util.find_spec("numpy"),
                     "FFmpeg/FFprobe and NumPy required")
class ReviewNotesIntegrationTests(unittest.TestCase):
    def test_draft_and_source_linked_annotations_and_rejection(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            video = root / "original.mkv"
            result = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(video),
            ], capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0,
                             result.stderr.decode(errors="replace"))
            gallery = study_reference(video, root / "runs", catalog_root=CATALOG,
                                      seconds=2, thumbnails=4)
            manifest = gallery.parent / "study-manifest.json"
            output = root / "review"
            notes_path = review_notes_template(manifest, output, reviewer_kind="human",
                                               reviewer_id="senior-director")
            with self.assertRaisesRegex(ValueError, "outside immutable"):
                review_notes_template(manifest, manifest.parent / "inside",
                                      reviewer_kind="human", reviewer_id="test")
            self.assertEqual(validate_review_notes(manifest, notes_path)["annotationCount"], 0)
            self.assertEqual(main(["review-notes", "validate", str(manifest),
                                   str(notes_path)]), 0)
            with self.assertRaisesRegex(ValueError, "different content"):
                review_notes_template(manifest, output, reviewer_kind="human",
                                      reviewer_id="another-person")
            study = json.loads(manifest.read_text(encoding="utf-8"))
            regions = json.loads((manifest.parent /
                                  study["artifacts"]["shotEvidence"]).read_text())
            proposals = json.loads((manifest.parent /
                                    study["artifacts"]["techniqueProposals"]).read_text())
            region = regions["regions"][0]
            first = region["startPtsInclusive"]
            original = json.loads(notes_path.read_text())
            human = original | {"annotations": [{
                "id": "note-001",
                "target": {"kind": "region", "id": region["id"]},
                "category": "story",
                "layer": "story-interpretation",
                "statement": "Possibly a transition to the next idea.",
                "confidence": "low",
                "assessment": "not-applicable",
                "evidenceFrames": [{"sourcePts": first,
                                    "description": "Bright test chart occupies the frame."}],
                "uncertainties": ["Visual structure alone does not establish the story."],
            }]}
            notes_path.write_text(json.dumps(human), encoding="utf-8")
            report = validate_review_notes(manifest, notes_path)
            self.assertEqual(report["structureStatus"], "source-anchors-verified")
            self.assertEqual(report["semanticStatus"], "not-verified")
            self.assertEqual(report["artisticApproval"], "not-granted")
            def rejected(patch, expected_error):
                notes_path.write_text(json.dumps(patch), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, expected_error):
                    validate_review_notes(manifest, notes_path)

            invalid_pts = json.loads(json.dumps(human))
            invalid_pts["annotations"][0]["evidenceFrames"][0]["sourcePts"] = first + 999_999
            rejected(invalid_pts, "frame anchor")
            no_uncertainty = json.loads(json.dumps(human))
            no_uncertainty["annotations"][0]["uncertainties"] = []
            rejected(no_uncertainty, "require stated uncertainties")
            false_approval = json.loads(json.dumps(human))
            false_approval["reviewStatus"] = "approved"
            rejected(false_approval, "never grant human approval")
            stale = json.loads(json.dumps(human))
            stale["study"]["sourceSha256"] = "f" * 64
            rejected(stale, "stale study identity")
            wrong_target = json.loads(json.dumps(human))
            wrong_target["annotations"][0]["target"]["id"] = "region-999"
            rejected(wrong_target, "absent from verified study")
            unhashable_target = json.loads(json.dumps(human))
            unhashable_target["annotations"][0]["target"]["kind"] = []
            rejected(unhashable_target, "target kind/id must be strings")
            unhashable_category = json.loads(json.dumps(human))
            unhashable_category["annotations"][0]["category"] = []
            rejected(unhashable_category, "category/layer must be strings")
            wrong_category = json.loads(json.dumps(human))
            wrong_category["annotations"][0]["assessment"] = "supports"
            rejected(wrong_category, "region annotations cannot assess")
            duplicate_id = json.loads(json.dumps(human))
            duplicate_id["annotations"].append(duplicate_id["annotations"][0])
            rejected(duplicate_id, "duplicate annotation")
            if proposals["candidates"]:
                cue = proposals["candidates"][0]
                cue_note = json.loads(json.dumps(human))
                cue_note["annotations"][0]["target"] = {
                    "kind": "cue", "id": cue["id"],
                }
                cue_note["annotations"][0]["assessment"] = "contradicts"
                # A cue anchor must be an actual decoded frame within the cue.
                timeline = json.loads((manifest.parent.parent / "analysis" /
                    study["settings"]["analysisRunDirectory"] /
                    "frame-timeline.json").read_text())
                candidate = [f["sourcePts"] for f in timeline["frames"]
                             if cue["sourcePtsRange"]["startPts"] <= f["sourcePts"] <=
                             cue["sourcePtsRange"]["endPts"]]
                self.assertTrue(candidate)
                cue_note["annotations"][0]["evidenceFrames"][0]["sourcePts"] = candidate[0]
                notes_path.write_text(json.dumps(cue_note), encoding="utf-8")
                self.assertEqual(validate_review_notes(
                    manifest, notes_path)["annotationCount"], 1)
            ai_folder = root / "ai-review"
            with self.assertRaisesRegex(ValueError, "AI reviewer requires model"):
                review_notes_template(manifest, ai_folder, reviewer_kind="ai",
                                      reviewer_id="local-model")
            ai_notes = review_notes_template(manifest, ai_folder,
                                             reviewer_kind="ai",
                                             reviewer_id="local-model",
                                             model_id="example-vlm")
            self.assertEqual(validate_review_notes(manifest, ai_notes)["reviewerKind"], "ai")
            # Break the immutable visual study; validation must refuse to link it.
            gallery.write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing, altered or untracked"):
                validate_review_notes(manifest, ai_notes)


if __name__ == "__main__":
    unittest.main()
