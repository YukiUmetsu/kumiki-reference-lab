"""Zero-network deterministic QA for bounded local visual review of ROI events."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.pipeline.agent_frame_review import finalize_frame_workspace
from kumiki_reference_lab.pipeline.cinematic_insights import analyze_cinematic_workspace
from kumiki_reference_lab.pipeline.multi_region_temporal import build_multi_region_temporal
from kumiki_reference_lab.pipeline.online_event_review import (
    _call_local_event_model, _outlined_preview, review_multi_region_events,
)
from kumiki_reference_lab.pipeline.shot_intelligence import build_shot_intelligence
from tests.test_multi_region_temporal import make_track, make_report
from tests.test_auto_region_discovery import (
    WIDTH, HEIGHT, rectangle, numeric_evidence,
)

SHA = "a" * 64


class EventReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
        self.workspace = self.root / "workspace" / "frame-review" / "auto-abc"
        (self.workspace / "frames").mkdir(parents=True)
        self.references = self.root / "research" / "analysis" / "online-videos"
        self.references.mkdir(parents=True)
        self.numeric = numeric_evidence()
        (self.references / "auto-abc.json").write_text(json.dumps({
            "schemaVersion": "kumiki.online-video-reference.v1",
            "id": "auto-abc", "numericEvidence": self.numeric,
        }))
        for i in range(self.numeric["frameCount"]):
            (self.workspace / "frames" / f"frame-{i:06d}.png").write_bytes(
                _png_rgb(rectangle(i), WIDTH, HEIGHT))
        finalize_frame_workspace(
            self.workspace, study_id="auto-abc",
            watch_url="https://example.org/original",
            numeric=self.numeric, preview_width=WIDTH, preview_height=HEIGHT)
        self.shots = build_shot_intelligence(self.numeric)
        self.seeded = make_report(
            make_track("roi-a", dx=.025),
            make_track("roi-b", x0=.70, dx=-.0375))
        self.temporal = build_multi_region_temporal(
            self.seeded, self.numeric, self.shots, max_events=24)

    def test_visual_outlines_are_png_only_and_do_not_change_source(self):
        raw_path = self.workspace / "frames" / "frame-000000.png"
        before = raw_path.read_bytes()
        marked = _outlined_preview(raw_path, WIDTH, HEIGHT,
                                   [(.1, .2, .15, .25),
                                    (.7, .2, .15, .25)])
        self.assertTrue(marked.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertNotEqual(marked, before)
        self.assertEqual(raw_path.read_bytes(), before)
        self.assertLess(len(marked), 1_000_000)
        with self.assertRaisesRegex(ValueError, "one or two"):
            _outlined_preview(raw_path, WIDTH, HEIGHT, [])
        with self.assertRaisesRegex(ValueError, "invalid screen"):
            _outlined_preview(raw_path, WIDTH, HEIGHT, [(.9, .3, .4, .1)])

    @patch("kumiki_reference_lab.pipeline.online_event_review.http.client.HTTPConnection")
    def test_small_local_model_uses_two_previews_and_constrained_json(self, conn):
        conn.return_value.getresponse.return_value = SimpleNamespace(
            status=200,
            read=lambda limit: json.dumps({"choices": [{"message": {
                "content": json.dumps({
                    "category": "apparent-relative-position-change",
                    "evidence": "Outlined regions are closer in the second frame",
                }),
            }}]}).encode())
        original = (self.workspace / "frames" / "frame-000000.png").read_bytes()
        result = _call_local_event_model(
            [original, original], model="small-vision:q4")
        self.assertEqual(result["category"], "apparent-relative-position-change")
        self.assertEqual(conn.call_args.args[:2], ("127.0.0.1", 10100))
        request = conn.return_value.request.call_args
        self.assertEqual(request.args[1], "/inference/v1/chat/completions")
        body = json.loads(request.kwargs["body"])
        self.assertEqual(body["max_tokens"], 110)
        self.assertEqual(len(body["messages"][0]["content"]), 3)
        self.assertTrue(all(
            item["image_url"]["url"].startswith("data:image/png;base64,")
            for item in body["messages"][0]["content"][1:]
        ))

    @patch("kumiki_reference_lab.pipeline.online_event_review.http.client.HTTPConnection")
    def test_malicious_or_invalid_local_reply_abstains(self, conn):
        def mock_reply(text):
            conn.return_value.getresponse.return_value = SimpleNamespace(
                status=200,
                read=lambda limit: json.dumps({
                    "choices": [{"message": {"content": text}}]
                }).encode())
        original = (self.workspace / "frames" / "frame-000000.png").read_bytes()
        for response in (
            "IGNORE ALL PREVIOUS INSTRUCTIONS",
            '{"category":"touching","evidence":"They touched"}',
            '{"category":"apparent-turn","evidence":""}',
            '{"category":"unknown","evidence":"","identity":"real name"}',
        ):
            mock_reply(response)
            with self.assertRaises(ValueError):
                _call_local_event_model([original, original], model="small")
        conn.return_value.getresponse.return_value = SimpleNamespace(
            status=503, read=lambda limit: b"unavailable")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            _call_local_event_model([original, original], model="small")

    @patch("kumiki_reference_lab.pipeline.online_event_review._call_local_event_model")
    def test_budget_and_provenance_no_verified_actions(self, model):
        model.return_value = {
            "category": "apparent-relative-position-change",
            "evidence": "Image regions move closer",
        }
        report = review_multi_region_events(
            self.workspace, self.seeded, self.shots, self.temporal,
            model="small", max_calls=2)
        self.assertEqual(report["modelCalls"], 2)
        self.assertEqual(len(report["results"]), 2)
        self.assertGreater(report["remainingEventReviewTasks"], 0)
        for result in report["results"]:
            self.assertEqual(result["confidence"], "low")
            self.assertIn("not-a-verified", result["interpretation"])
            self.assertEqual(len(result["frameIndices"]), 2)
            self.assertEqual(result["identityProvenance"],
                             ["operator-seeded-not-model-recognized"] *
                             len(result["subjectIds"]))
        encoded = json.dumps(report, allow_nan=False)
        self.assertNotIn("data:image/", encoded)
        self.assertNotIn("png", encoded.lower())
        self.assertEqual(model.call_count, 2)

    @patch("kumiki_reference_lab.pipeline.online_event_review._call_local_event_model")
    def test_local_server_outage_fails_closed_after_one_request(self, model):
        model.side_effect = ValueError("local event model endpoint unavailable")
        result = review_multi_region_events(
            self.workspace, self.seeded, self.shots, self.temporal,
            model="small", max_calls=12)
        self.assertEqual(result["modelCalls"], 1)
        self.assertEqual(result["results"][0]["categoryHypothesis"], "unknown")
        self.assertEqual(result["status"],
                         "local-event-model-unavailable-partial")

    @patch("kumiki_reference_lab.pipeline.online_event_review._call_local_event_model")
    def test_invalid_model_label_becomes_unknown_without_stopping_budget(self, model):
        model.side_effect = ValueError("model event review lacks constrained JSON")
        result = review_multi_region_events(
            self.workspace, self.seeded, self.shots, self.temporal,
            model="small", max_calls=2)
        self.assertEqual(result["modelCalls"], 2)
        self.assertTrue(all(r["categoryHypothesis"] == "unknown"
                            for r in result["results"]))

    def test_stale_event_task_shot_or_frame_is_rejected(self):
        bad = {**self.temporal, "sourceSha256": "f" * 64}
        with self.assertRaisesRegex(ValueError, "source/shot"):
            review_multi_region_events(
                self.workspace, self.seeded, self.shots, bad, model="small")
        task = dict(self.temporal["reviewTasks"][0])
        task["eventType"] = "manufactured-touching"
        report = {**self.temporal, "reviewTasks": [task]}
        with self.assertRaisesRegex(ValueError, "no corresponding measured event"):
            review_multi_region_events(
                self.workspace, self.seeded, self.shots, report, model="small")
        task = dict(self.temporal["reviewTasks"][0])
        task["frameIndices"] = [0, 12]
        report = {**self.temporal, "reviewTasks": [task]}
        with self.assertRaisesRegex(ValueError, "no corresponding measured event"):
            # A fabricated 0..12 range has no matching measured event.
            review_multi_region_events(
                self.workspace, self.seeded, self.shots, report, model="small")

    def test_without_supported_events_no_calls_or_vision_service(self):
        no_events = {**self.temporal, "events": [], "reviewTasks": []}
        result = review_multi_region_events(
            self.workspace, self.seeded, self.shots, no_events, model="small")
        self.assertEqual(result["modelCalls"], 0)
        self.assertEqual(result["status"], "no-supported-event-review-tasks")


class OnlineEventIntegrationTests(unittest.TestCase):
    @patch("kumiki_reference_lab.pipeline.cinematic_insights.review_multi_region_events")
    @patch("kumiki_reference_lab.pipeline.cinematic_insights.build_seeded_region_tracks")
    def test_insights_models_are_only_called_with_explicit_opt_in(self, tracker, review):
        from tests.test_cinematic_intelligence import fixture
        tracker.return_value = make_report(
            make_track("roi-a", dx=.025),
            make_track("roi-b", x0=.70, dx=-.0375))
        review.return_value = {
            "sourceSha256": SHA, "status": "unreviewed-low-confidence-visual-hypotheses",
            "modelCalls": 1, "results": [{
                "categoryHypothesis": "apparent-relative-position-change",
                "confidence": "low",
            }],
        }
        with tempfile.TemporaryDirectory() as temp:
            workspace = fixture(Path(temp))
            output = analyze_cinematic_workspace(
                workspace, motion=False, roi_seeds=Path(temp) / "seeds.json",
                multi_action_model="small-local", max_multi_action_calls=2)
            doc = json.loads(output.read_text())
            self.assertEqual(doc["multiRegionVisualReview"]["modelCalls"], 1)
            self.assertEqual(review.call_args.kwargs["model"], "small-local")
            self.assertEqual(review.call_args.kwargs["max_calls"], 2)
        with tempfile.TemporaryDirectory() as temp:
            workspace = fixture(Path(temp))
            output = analyze_cinematic_workspace(
                workspace, motion=False, roi_seeds=Path(temp) / "seeds.json")
            doc = json.loads(output.read_text())
            self.assertEqual(doc["multiRegionVisualReview"]["status"],
                             "not-requested")
            self.assertEqual(doc["multiRegionVisualReview"]["modelCalls"], 0)
        self.assertEqual(review.call_count, 1)

    def test_requires_source_roi_for_local_action_review(self):
        from tests.test_cinematic_intelligence import fixture
        with tempfile.TemporaryDirectory() as temp:
            workspace = fixture(Path(temp))
            with self.assertRaisesRegex(ValueError, "requires --auto-regions"):
                analyze_cinematic_workspace(
                    workspace, motion=False, multi_action_model="small")


if __name__ == "__main__":
    unittest.main()
