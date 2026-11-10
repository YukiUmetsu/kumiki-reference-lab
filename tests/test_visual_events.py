"""Camera/lighting frequencies depend on explicit reviewer coverage and honest labels."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.cli.app import main
from kumiki_reference_lab.reviews.visual_events import (
    load_visual_events, summarize_visual_events, validate_visual_events,
)


def fixture() -> dict:
    return {
        "schemaVersion": "kumiki.visual-events-review.v1",
        "sourceSha256": "a" * 64, "sourceStreamIndex": 0,
        "sourceTimebase": {"numerator": 1, "denominator": 1000},
        "reviewer": {"kind": "human", "id": "example-reviewer"},
        "window": {"startPts": 2000, "endPts": 62000,
                   "coverage": "full-window-visual-review"},
        "events": [
            {"category": "camera-movement", "kind": "pan", "startPts": 3000, "endPts": 7000,
             "assessment": "reviewer-interpreted", "observation": "Background scrolls laterally.",
             "alternativeExplanation": "Could be moving composited layers."},
            {"category": "camera-movement", "kind": "dolly-in", "startPts": 9000, "endPts": 11000,
             "assessment": "reviewer-interpreted", "observation": "Foreground and back planes change scale.",
             "alternativeExplanation": "Could be keyframed graphic scaling."},
            {"category": "lighting-change", "kind": "light-sweep", "startPts": 12000,
             "endPts": 15000, "assessment": "reviewer-interpreted",
             "observation": "A bright highlight travels across the subject.",
             "alternativeExplanation": "Could be an animated texture."},
            {"category": "camera-movement", "kind": "orbit", "startPts": 18000,
             "endPts": 25000, "assessment": "unresolved-hypothesis",
             "observation": "Apparent angle changes relative to the object.",
             "alternativeExplanation": "The subject could be rotating instead."},
        ],
    }


class VisualEventsTests(unittest.TestCase):
    def test_reviewed_window_counts_interpretations_separate_from_uncertainty(self):
        result = summarize_visual_events(fixture())
        self.assertTrue(result["eventRatesAvailable"])
        self.assertEqual(result["reviewedWindowSeconds"], 60)
        self.assertEqual(result["cameraMovementEvents"], 2)
        self.assertEqual(result["lightingChangeEvents"], 1)
        self.assertEqual(result["cameraMovementEventsPerReviewedMinute"], 2)
        self.assertEqual(result["lightingChangeEventsPerReviewedMinute"], 1)
        self.assertEqual(result["unresolvedByCategory"], {"camera-movement": 1})
        self.assertFalse(result["observer"]["identityVerified"])

    def test_partial_review_refuses_unsupported_frequency_estimate(self):
        review = fixture()
        review["window"]["coverage"] = "partial-window-visual-review"
        report = summarize_visual_events(review)
        self.assertFalse(report["eventRatesAvailable"])
        self.assertIsNone(report["cameraMovementEventsPerReviewedMinute"])
        self.assertTrue(all(x["eventsPerReviewedMinute"] is None for x in report["eventTypeRates"]))
        review["events"].clear()
        report = summarize_visual_events(review)
        self.assertIsNone(report["cameraMovementEventsPerReviewedMinute"])
        review["window"]["coverage"] = "full-window-visual-review"
        report = summarize_visual_events(review)
        self.assertEqual(report["cameraMovementEventsPerReviewedMinute"], 0)

    def test_rejects_unsafe_ambiguous_and_outside_annotations(self):
        for name, mutate in (
            ("wrong version", lambda r: r.update(schemaVersion="v2")),
            ("extra field", lambda r: r["events"][0].update(viewCount=100)),
            ("camera category", lambda r: r["events"][0].update(category="lighting-change")),
            ("unsupported status", lambda r: r["events"][0].update(assessment="physically-verified")),
            ("outside", lambda r: r["events"][0].update(startPts=0)),
            ("zero duration", lambda r: r["events"][0].update(endPts=3000)),
            ("missing alternative", lambda r: r["events"][0].update(alternativeExplanation="")),
            ("malformed reviewer", lambda r: r["reviewer"].update(kind="unknown")),
            ("wrong timebase", lambda r: r["sourceTimebase"].update(denominator=0)),
            ("duplicate event", lambda r: r["events"].append(copy.deepcopy(r["events"][0]))),
            ("huge", lambda r: r["events"].extend(copy.deepcopy(r["events"][:1]) * 501)),
        ):
            with self.subTest(name=name):
                review = fixture()
                mutate(review)
                with self.assertRaises(ValueError):
                    validate_visual_events(review)

    def test_cli_validate_report_and_symlink_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(json.dumps(fixture()))
            for action in ("validate", "report"):
                with self.subTest(action=action):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        self.assertEqual(main(["visual-events", action, str(path)]), 0)
                    self.assertTrue(json.loads(output.getvalue()))
            path.write_text('{"a":1,"a":2}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_visual_events(path)
            alias = Path(directory) / "alias.json"
            alias.symlink_to(path)
            with self.assertRaisesRegex(ValueError, "regular"):
                load_visual_events(alias)
