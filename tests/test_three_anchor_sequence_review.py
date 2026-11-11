"""Three source-anchor sequence review tests; no model, decoder or network needed."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.pipeline.agent_frame_review import finalize_frame_workspace
from kumiki_reference_lab.pipeline.cinematic_insights import analyze_cinematic_workspace
from kumiki_reference_lab.pipeline.multi_region_temporal import build_multi_region_temporal
from kumiki_reference_lab.pipeline.shot_intelligence import build_shot_intelligence
from kumiki_reference_lab.pipeline.three_anchor_sequence_review import (
    SCHEMA_VERSION, _candidate_groups, review_three_anchor_sequences,
)
from tests.test_auto_region_discovery import (
    WIDTH, HEIGHT, SOURCE_SHA, rectangle, numeric_evidence,
)
from tests.test_multi_region_temporal import make_track, make_report


class ThreeAnchorSequenceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root / "pyproject.toml").write_text("[project]\nname='synthetic'\n")
        self.workspace = self.root / "workspace" / "frame-review" / "auto-abc"
        (self.workspace / "frames").mkdir(parents=True)
        reference_dir = self.root / "research" / "analysis" / "online-videos"
        reference_dir.mkdir(parents=True)
        self.numeric = numeric_evidence()
        (reference_dir / "auto-abc.json").write_text(json.dumps({
            "schemaVersion": "kumiki.online-video-reference.v1",
            "id": "auto-abc",
            "numericEvidence": self.numeric,
        }))
        for i in range(self.numeric["frameCount"]):
            (self.workspace / "frames" / f"frame-{i:06d}.png").write_bytes(
                _png_rgb(rectangle(i), WIDTH, HEIGHT))
        finalize_frame_workspace(
            self.workspace, study_id="auto-abc",
            watch_url="https://example.org/reference",
            numeric=self.numeric, preview_width=WIDTH,
            preview_height=HEIGHT,
        )
        self.shots = build_shot_intelligence(self.numeric)
        self.seeded = make_report(
            make_track("region-a", dx=.025),
            make_track("region-b", x0=.70, dx=-.0375),
        )
        self.temporal = build_multi_region_temporal(
            self.seeded, self.numeric, self.shots,
        )

    def review(self, *, max_calls=8, max_sequences=4):
        return review_three_anchor_sequences(
            self.workspace, self.seeded, self.shots, self.temporal,
            model="local-small-q4", max_calls=max_calls,
            max_sequences=max_sequences,
        )

    def test_groups_multiple_events_into_one_bounded_pair_sequence(self):
        grouped = _candidate_groups(self.temporal, max_sequences=4)
        self.assertGreater(len(grouped), 1)
        self.assertEqual(len(grouped[0]["subjectIds"]), 2)
        self.assertGreaterEqual(len(grouped[0]["measuredEventTypes"]), 2)
        self.assertEqual(grouped[0]["frameIndices"], [0, 5, 11])
        self.assertEqual(len(set(grouped[0]["measuredEventTypes"])),
                         len(grouped[0]["measuredEventTypes"]))

    @patch("kumiki_reference_lab.pipeline.three_anchor_sequence_review._call_local_event_model")
    def test_two_window_consistency_is_only_unverified_visual_evidence(self, model):
        model.side_effect = [
            {"category": "apparent-relative-position-change",
             "evidence": "The colored boxes are closer"},
            {"category": "apparent-relative-position-change",
             "evidence": "Both outlined regions move together"},
        ]
        report = self.review(max_calls=2)
        self.assertEqual(report["schemaVersion"], SCHEMA_VERSION)
        self.assertEqual(report["sourceSha256"], SOURCE_SHA)
        self.assertEqual(report["modelCalls"], 2)
        self.assertEqual(report["reviewedSequences"], 1)
        self.assertGreater(report["remainingSequences"], 0)
        row = report["sequences"][0]
        self.assertEqual(row["frameIndices"], [0, 5, 11])
        self.assertEqual(row["sourceDecodedSeconds"], [0.0, 0.5, 1.1])
        self.assertEqual(row["sequencePatternHypothesis"],
                         "repeated-visual-change-unverified")
        self.assertEqual(
            [v["frameIndices"] for v in row["phaseObservations"]],
            [[0, 5], [5, 11]],
        )
        self.assertTrue(all(
            v["status"] == "unverified-two-frame-phase-hypothesis"
            for v in row["phaseObservations"]))
        self.assertEqual(len(row["identityProvenance"]), 2)
        self.assertIn("not-semantic-action", row["status"])
        self.assertTrue(all(
            call.kwargs["model"] == "local-small-q4"
            and len(call.args[0]) == 2
            for call in model.call_args_list))
        self.assertNotIn("base64", json.dumps(report).lower())
        self.assertNotIn("data:image", json.dumps(report).lower())
        self.assertNotIn("identityVerified", json.dumps(report))

    @patch("kumiki_reference_lab.pipeline.three_anchor_sequence_review._call_local_event_model")
    def test_two_different_phases_are_not_invented_gesture(self, model):
        model.side_effect = [
            {"category": "apparent-region-translation", "evidence": "Box moves right"},
            {"category": "apparent-turn", "evidence": "Outline appears to turn"},
        ]
        report = self.review(max_calls=2)
        self.assertEqual(report["sequences"][0]["sequencePatternHypothesis"],
                         "different-visible-phases-unverified")
        self.assertNotIn("walking", json.dumps(report))
        self.assertNotIn("touching", json.dumps(report))

    @patch("kumiki_reference_lab.pipeline.three_anchor_sequence_review._call_local_event_model")
    def test_unknown_phases_abstain_and_budget_is_two_calls_per_sequence(self, model):
        model.return_value = {"category": "unknown", "evidence": ""}
        report = self.review(max_calls=3)
        self.assertEqual(report["modelCalls"], 2)
        self.assertEqual(report["reviewedSequences"], 1)
        self.assertEqual(report["sequences"][0]["sequencePatternHypothesis"],
                         "insufficient-consistent-visual-evidence")
        self.assertEqual(model.call_count, 2)

    @patch("kumiki_reference_lab.pipeline.three_anchor_sequence_review._call_local_event_model")
    def test_local_model_outage_stops_early_with_partial_evidence(self, model):
        model.side_effect = ValueError("local event model endpoint unavailable")
        report = self.review(max_calls=8)
        self.assertEqual(report["status"],
                         "local-sequence-model-unavailable-partial")
        self.assertEqual(report["modelCalls"], 1)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(len(report["sequences"][0]["phaseObservations"]), 1)
        self.assertEqual(report["sequences"][0]["phaseObservations"][0][
            "categoryHypothesis"], "unknown")

    @patch("kumiki_reference_lab.pipeline.three_anchor_sequence_review._call_local_event_model")
    def test_malformed_model_hypotheses_abstain_not_infer(self, model):
        model.side_effect = ValueError("model event review lacks constrained JSON")
        report = self.review(max_calls=2)
        self.assertEqual(report["modelCalls"], 2)
        self.assertEqual(report["sequences"][0]["sequencePatternHypothesis"],
                         "insufficient-consistent-visual-evidence")

    def test_tampered_events_rejected_before_model_contact(self):
        self.temporal = {
            **self.temporal, "sourceSha256": "b" * 64,
        }
        with self.assertRaisesRegex(ValueError, "source and shot"):
            self.review(max_calls=2)
        self.temporal["sourceSha256"] = SOURCE_SHA
        fake = dict(self.temporal["reviewTasks"][0])
        fake["eventType"] = "verified-object-passing"
        self.temporal["reviewTasks"] = [fake]
        with self.assertRaisesRegex(ValueError, "not linked"):
            self.review(max_calls=2)

    def test_rejects_missing_anchors_bad_shot_or_mismatched_pts(self):
        fake = dict(self.temporal["reviewTasks"][0])
        fake["frameIndices"] = [0, 0, 11]
        self.temporal["reviewTasks"] = [fake]
        with self.assertRaisesRegex(ValueError, "three distinct"):
            self.review(max_calls=2)

        self.temporal = build_multi_region_temporal(
            self.seeded, self.numeric, self.shots)
        self.seeded["tracks"][0]["observations"][3]["decodedSeconds"] += .01
        with self.assertRaisesRegex(ValueError, "source PTS"):
            self.review(max_calls=2)

    def test_missing_roi_tracks_cannot_be_labeled_as_actions(self):
        temporal = {**self.temporal, "events": [], "reviewTasks": []}
        empty = review_three_anchor_sequences(
            self.workspace, {"status": "not-requested"},
            self.shots, temporal, model="small", max_calls=2)
        self.assertEqual(empty["modelCalls"], 0)
        self.assertEqual(empty["status"], "no-sequences-reviewed")
        self.assertEqual(empty["sequences"], [])

    def test_invalid_budgets_raise_before_any_model_inference(self):
        with self.assertRaisesRegex(ValueError, "budgets"):
            self.review(max_calls=1)
        with self.assertRaisesRegex(ValueError, "budgets"):
            self.review(max_sequences=20)


class ThreeAnchorInsightsIntegration(unittest.TestCase):
    @patch("kumiki_reference_lab.pipeline.cinematic_insights.review_three_anchor_sequences")
    @patch("kumiki_reference_lab.pipeline.cinematic_insights.build_seeded_region_tracks")
    def test_explicit_opt_in_and_no_model_default(self, tracker, sequence):
        from tests.test_cinematic_intelligence import fixture
        tracker.return_value = make_report(
            make_track("region-a", dx=.025),
            make_track("region-b", x0=.7, dx=-.0375))
        sequence.return_value = {
            "status": "unverified-three-anchor-visual-sequences",
            "sourceSha256": SOURCE_SHA, "modelCalls": 2,
            "sequences": [{"status": "unverified-short-sequence-not-semantic-action"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            workspace = fixture(Path(directory))
            output = analyze_cinematic_workspace(
                workspace, motion=False, roi_seeds=Path(directory) / "roi.json",
                sequence_model="local-q4", max_sequence_calls=2,
                max_sequences=1)
            report = json.loads(output.read_text())
            self.assertEqual(report["threeAnchorSequenceReview"]["modelCalls"], 2)
            self.assertEqual(sequence.call_args.kwargs["max_sequences"], 1)
            self.assertEqual(sequence.call_args.kwargs["max_calls"], 2)
        with tempfile.TemporaryDirectory() as directory:
            workspace = fixture(Path(directory))
            output = analyze_cinematic_workspace(
                workspace, motion=False, roi_seeds=Path(directory) / "roi.json")
            report = json.loads(output.read_text())
            self.assertEqual(report["threeAnchorSequenceReview"]["status"],
                             "not-requested")
            self.assertEqual(report["threeAnchorSequenceReview"]["modelCalls"], 0)
        self.assertEqual(sequence.call_count, 1)

    def test_local_sequence_mode_needs_tracking_opt_in(self):
        from tests.test_cinematic_intelligence import fixture
        with tempfile.TemporaryDirectory() as directory:
            workspace = fixture(Path(directory))
            with self.assertRaisesRegex(ValueError, "sequence-model requires"):
                analyze_cinematic_workspace(
                    workspace, motion=False, sequence_model="local-q4")


if __name__ == "__main__":
    unittest.main()
