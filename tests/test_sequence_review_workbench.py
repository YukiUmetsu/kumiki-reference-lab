"""Fully offline source-frame HTML review pack: no media copy, AI or network."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.pipeline.agent_frame_review import (
    finalize_frame_workspace,
)
from kumiki_reference_lab.pipeline.sequence_benchmark import (
    LABEL_VERSION, _load, main, make_label_template,
)
from kumiki_reference_lab.pipeline.sequence_review_workbench import (
    _CATEGORIES, create_review_pack,
)
from kumiki_reference_lab.pipeline.shot_intelligence import (
    build_shot_intelligence,
)
from kumiki_reference_lab.pipeline.online_event_review import _KINDS
from tests.test_auto_region_discovery import (
    WIDTH, HEIGHT, SOURCE_SHA, rectangle, numeric_evidence,
)
from tests.test_multi_region_temporal import make_track, make_report
from tests.test_sequence_benchmark import document


class OfflineReviewPackTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root / "pyproject.toml").write_text("[project]\nname='review-test'\n")
        self.workspace = self.root / "workspace" / "frame-review" / "auto-abc"
        (self.workspace / "frames").mkdir(parents=True)
        refs = self.root / "research" / "analysis" / "online-videos"
        refs.mkdir(parents=True)
        self.numeric = numeric_evidence()
        (refs / "auto-abc.json").write_text(json.dumps({
            "schemaVersion": "kumiki.online-video-reference.v1",
            "id": "auto-abc",
            "numericEvidence": self.numeric,
        }))
        for i in range(self.numeric["frameCount"]):
            (self.workspace / "frames" / f"frame-{i:06d}.png").write_bytes(
                _png_rgb(rectangle(i), WIDTH, HEIGHT))
        finalize_frame_workspace(
            self.workspace, study_id="auto-abc",
            watch_url="https://example.org/authorized",
            numeric=self.numeric, preview_width=WIDTH,
            preview_height=HEIGHT,
        )
        self.insights = document()
        self.insights["shotIntelligence"] = build_shot_intelligence(self.numeric)
        self.insights["seededSubjectTracks"] = make_report(
            make_track("roi-a", dx=.02),
            make_track("roi-b", x0=.7, dx=-.035),
            make_track("roi-c", start=12, dx=.01),
            make_track("roi-d", start=12, x0=.6, dx=-.02),
        )
        self.insights["threeAnchorSequenceReview"]["sequences"][1][
            "subjectIds"] = ["roi-c", "roi-d"]
        self.path = refs / "auto-abc.insights.json"
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.insights), encoding="utf-8")

    def test_offline_browser_pack_references_real_png_without_copying(self):
        original_frames = {
            f.name: f.read_bytes() for f in (self.workspace / "frames").iterdir()
        }
        result = create_review_pack(self.workspace, self.path)
        self.assertEqual(result, self.workspace / "review-sequences.html")
        html = result.read_text()
        self.assertIn('frames/frame-000000.png', html)
        self.assertIn('frames/frame-000005.png', html)
        self.assertIn('frames/frame-000011.png', html)
        self.assertIn('frames/frame-000012.png', html)
        self.assertIn('frames/frame-000023.png', html)
        self.assertIn('class="roi roi-A"', html)
        self.assertIn('class="roi roi-B"', html)
        self.assertIn('data-sequence="0" data-phase="0"', html)
        self.assertIn('data-sequence="1" data-phase="1"', html)
        self.assertIn("Export pending draft", html)
        self.assertIn("Export reviewed labels", html)
        self.assertIn("Resume draft", html)
        self.assertIn("connect-src 'none'", html)
        self.assertIn("file:", html)
        self.assertEqual(len(original_frames), len(list(
            (self.workspace / "frames").iterdir())))
        self.assertTrue(all(
            (self.workspace / "frames" / name).read_bytes() == raw
            for name, raw in original_frames.items()))
        self.assertNotIn("data:image/", html)
        self.assertNotIn("https://example.org/authorized", html)
        self.assertFalse((self.workspace / "human-labels.json").exists())
        # Exact pending template is included; model's *guesses* are hidden.
        self.assertIn('"coverageDeclaration":"pending-review"', html)
        self.assertIn('"humanCategory":null', html)

    def test_category_vocabulary_matches_human_benchmark_not_unknown(self):
        self.assertEqual(set(value for value, _ in _CATEGORIES),
                         (_KINDS - {"unknown"}) | {"not-observable"})

    def test_model_guesses_do_not_anchor_human_answers(self):
        row = self.insights["threeAnchorSequenceReview"]["sequences"][0]
        row["phaseObservations"][0]["visibleEvidenceHypothesis"] = (
            "MODEL_ONLY_HALLUCINATED_ACTION")
        row["phaseObservations"][0]["categoryHypothesis"] = "apparent-turn"
        self.save()
        html = create_review_pack(self.workspace, self.path).read_text()
        self.assertNotIn("MODEL_ONLY_HALLUCINATED_ACTION", html)
        self.assertNotIn('"categoryHypothesis"', html)
        self.assertIn('"modelTagObserved":"small-local-q4"', html)
        self.assertIn("Choose visible change", html)

    def test_browser_json_script_and_html_escape_untrusted_roi_identifiers(self):
        injection = '<img src=x onerror=alert(1)>'
        self.insights["seededSubjectTracks"]["tracks"][0]["id"] = injection
        self.insights["threeAnchorSequenceReview"]["sequences"][0][
            "subjectIds"][0] = injection
        self.save()
        html = create_review_pack(self.workspace, self.path).read_text()
        self.assertNotIn(injection, html)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)
        self.assertIn("\\u003cimg", html)
        self.assertNotIn("<img src=x onerror=", html)

    def test_previews_missing_changed_shape_or_symlink_abstain(self):
        file = self.workspace / "frames" / "frame-000005.png"
        original = file.read_bytes()
        file.write_bytes(b"not a PNG")
        with self.assertRaises(ValueError):
            create_review_pack(self.workspace, self.path)
        self.assertFalse((self.workspace / "review-sequences.html").exists())
        file.write_bytes(original)
        file.unlink()
        file.symlink_to(self.workspace / "frames" / "frame-000004.png")
        with self.assertRaises(ValueError):
            create_review_pack(self.workspace, self.path)

    def test_report_source_frame_times_and_provisional_roi_must_match(self):
        self.insights["threeAnchorSequenceReview"]["sequences"][0][
            "sourceDecodedSeconds"][1] = 0.6
        self.save()
        with self.assertRaisesRegex(ValueError, "decoded times"):
            create_review_pack(self.workspace, self.path)
        self.insights = document()
        self.insights["shotIntelligence"] = build_shot_intelligence(self.numeric)
        self.insights["seededSubjectTracks"] = make_report(
            make_track("roi-a"), make_track("roi-b", x0=.7, dx=-.03),
            make_track("roi-c", start=12),
            make_track("roi-d", start=12, x0=.7, dx=-.03),
        )
        self.insights["threeAnchorSequenceReview"]["sequences"][1][
            "subjectIds"] = ["roi-c", "roi-d"]
        self.insights["source"]["sourceSha256"] = "b" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "provenance"):
            create_review_pack(self.workspace, self.path)

    def test_output_is_private_create_only_and_cannot_escape_workspace(self):
        out = create_review_pack(self.workspace, self.path)
        before = out.read_bytes()
        with self.assertRaisesRegex(ValueError, "new .html"):
            create_review_pack(self.workspace, self.path)
        self.assertEqual(out.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "new .html"):
            create_review_pack(
                self.workspace, self.path,
                out=self.root / "leaked-review.html",
            )
        with self.assertRaisesRegex(ValueError, "new .html"):
            create_review_pack(
                self.workspace, self.path,
                out=self.workspace / "UPPER.html",
            )
        self.assertFalse((self.root / "leaked-review.html").exists())

    def test_cli_exposes_review_pack_and_is_idempotent_with_fail_closed_collision(self):
        self.assertEqual(main([
            "review-pack", "--workspace", str(self.workspace),
            "--insights", str(self.path),
        ]), 0)
        self.assertTrue((self.workspace / "review-sequences.html").exists())
        with self.assertRaises(SystemExit):
            main([
                "review-pack", "--workspace", str(self.workspace),
                "--insights", str(self.path),
            ])
        template = make_label_template(
            self.insights, insights_sha=_load(self.path)[1])
        self.assertEqual(template["schemaVersion"], LABEL_VERSION)
        self.assertEqual(template["coverageDeclaration"], "pending-review")
        self.assertTrue(all(
            phase["humanCategory"] is None
            for row in template["sequences"]
            for phase in row["phases"]
        ))

    @patch("kumiki_reference_lab.pipeline.sequence_review_workbench._decode_review_png")
    def test_pack_rejects_broken_image_decoder_before_creating_html(self, decoded):
        decoded.side_effect = ValueError("invalid PNG")
        with self.assertRaisesRegex(ValueError, "invalid PNG"):
            create_review_pack(self.workspace, self.path)
        self.assertFalse((self.workspace / "review-sequences.html").exists())


if __name__ == "__main__":
    unittest.main()
