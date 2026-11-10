"""Time-weighted style labels are reviewer declarations, never detected films."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.cli.app import main
from kumiki_reference_lab.reviews.visual_style_timeline import (
    load_visual_style_timeline, summarize_visual_style_timeline,
    validate_visual_style_timeline,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/visual-style-review.example.json"


class VisualStyleTimelineTests(unittest.TestCase):
    def setUp(self):
        self.sample = load_visual_style_timeline(EXAMPLE)

    def test_time_weighted_hybrid_styles_and_lighting_report(self):
        report = summarize_visual_style_timeline(self.sample)
        self.assertTrue(report["wholeWindowStyleCompositionAvailable"])
        self.assertEqual(report["reviewedWindowSeconds"], 10)
        self.assertEqual(report["labeledFractionOfWindow"], 1)
        medium = {item["tag"]: item for item in report["observedStyleTime"]["medium"]}
        self.assertEqual(medium["2.5d-compositing"]["fractionOfEntireReviewedWindow"], 0.5)
        self.assertEqual(medium["live-action"]["seconds"], 5)
        tags = {item["tag"] for item in report["observedStyleTime"]["treatment"]}
        self.assertIn("paper-cut", tags)
        self.assertIn("2.5d-parallax", tags)
        self.assertIn("naturalistic-documentary", tags)
        self.assertGreater(sum(item["fractionOfLabeledTime"]
                               for item in report["observedStyleTime"]["treatment"]), 1)
        self.assertFalse(report["reviewer"]["identityVerified"])

    def test_partial_and_gapped_reviews_never_extrapolate_to_entire_window(self):
        sample = copy.deepcopy(self.sample)
        sample["window"]["coverage"] = "partial-window-visual-review"
        sample["segments"][0]["endPts"] = 4000
        report = summarize_visual_style_timeline(sample)
        self.assertFalse(report["wholeWindowStyleCompositionAvailable"])
        self.assertEqual(report["labeledFractionOfWindow"], 0.9)
        for group in report["observedStyleTime"].values():
            self.assertTrue(all(item["fractionOfEntireReviewedWindow"] is None for item in group))
        sample["window"]["coverage"] = "full-window-visual-review"
        with self.assertRaisesRegex(ValueError, "without gaps"):
            validate_visual_style_timeline(sample)
        sample["window"]["coverage"] = "partial-window-visual-review"
        sample["segments"] = []
        empty = summarize_visual_style_timeline(sample)
        self.assertEqual(empty["labeledFractionOfWindow"], 0)
        self.assertEqual(empty["observedStyleTime"]["treatment"], [])

    def test_reject_overlapping_and_malformed_interpretations(self):
        def mutate(name, fn):
            changed = copy.deepcopy(self.sample)
            fn(changed)
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_visual_style_timeline(changed)

        mutate("overlap", lambda x: x["segments"][1].update(startPts=4000))
        mutate("out-of-window", lambda x: x["segments"][0].update(startPts=-1))
        mutate("negative length", lambda x: x["segments"][0].update(endPts=0))
        mutate("boolean timebase", lambda x: x["sourceTimebase"].update(numerator=True))
        mutate("zero timebase", lambda x: x["sourceTimebase"].update(denominator=0))
        mutate("boolean interval", lambda x: x["segments"][0].update(startPts=False))
        mutate("bad media", lambda x: x["segments"][0].update(medium="youtube-explainer"))
        mutate("bad treatment", lambda x: x["segments"][0].update(treatments=["auto-premium"]))
        mutate("repeated tag", lambda x: x["segments"][0].update(treatments=["paper-cut", "paper-cut"]))
        mutate("bad look", lambda x: x["segments"][0].update(lightingLook="expensive-studio"))
        mutate("invalid anchor", lambda x: x["segments"][0].update(anchorPts=[6000]))
        mutate("repeated anchor", lambda x: x["segments"][0].update(anchorPts=[1000, 1000]))
        mutate("no anchor", lambda x: x["segments"][0].update(anchorPts=[]))
        mutate("bad confidence", lambda x: x["segments"][0].update(confidence="certain"))
        mutate("unsupported unresolved claim", lambda x: x["segments"][0].update(confidence="unresolved"))
        mutate("no explanation", lambda x: x["segments"][0].update(alternativeExplanation=""))
        mutate("new field", lambda x: x["segments"][0].update(causallyViral=True))
        mutate("future schema", lambda x: x.update(schemaVersion="v2"))

    def test_file_guards_and_cli_report(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            path = temp / "review.json"
            path.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_visual_style_timeline(path)
            path.write_text('{"segments":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite"):
                load_visual_style_timeline(path)
            path.write_bytes(b" " * 262_145)
            with self.assertRaisesRegex(ValueError, "256 KiB"):
                load_visual_style_timeline(path)
            link = temp / "link.json"
            link.symlink_to(path)
            with self.assertRaisesRegex(ValueError, "regular"):
                load_visual_style_timeline(link)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["visual-style-review", "report", str(EXAMPLE)]), 0)
            self.assertTrue(json.loads(output.getvalue())["wholeWindowStyleCompositionAvailable"])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["visual-style-review", "validate", str(EXAMPLE)]), 0)
