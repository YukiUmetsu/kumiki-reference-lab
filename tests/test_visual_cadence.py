"""Source-PTS and epistemic regression gates for visual cadence summaries."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.comparison.visual_cadence import (
    load_cadence_input, summarize_visual_cadence,
)
from kumiki_reference_lab.cli.app import main
from kumiki_reference_lab.contracts.analysis import APPEARANCE_VERSION, IMAGE_MOTION_VERSION


def fixture() -> tuple[dict, dict]:
    base = {"sourceSha256": "a" * 64, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 4},
            "scanWindowSeconds": 10,
            "coverage": "bounded-from-start-not-necessarily-full-video"}
    motion = {
        **base, "schemaVersion": IMAGE_MOTION_VERSION, "cutCandidatePts": [30],
        "samples": [{"sourcePts": pts} for pts in (0, 10, 20, 30, 40)],
        "pairs": [
            {"startPts": 0, "endPts": 10, "deltaTimeSeconds": {"numerator": 5, "denominator": 2},
             "status": "measured-image-translation", "dxNormalized": 0.04, "dyNormalized": 0},
            {"startPts": 10, "endPts": 20, "deltaTimeSeconds": {"numerator": 5, "denominator": 2},
             "status": "measured-image-translation", "dxNormalized": 0, "dyNormalized": 0},
            {"startPts": 20, "endPts": 30, "deltaTimeSeconds": {"numerator": 5, "denominator": 2},
             "status": "cut-boundary", "dxNormalized": None, "dyNormalized": None},
            {"startPts": 30, "endPts": 40, "deltaTimeSeconds": {"numerator": 5, "denominator": 2},
             "status": "measured-image-translation", "dxNormalized": 0, "dyNormalized": 0.1},
        ],
    }
    appearance = {
        **base, "schemaVersion": APPEARANCE_VERSION, "cutCandidatePts": [30],
        "samples": [{"sourcePts": pts} for pts in (0, 20, 40)],
        "changes": [
            {"startPts": 0, "endPts": 20, "deltaTimeSeconds": {"numerator": 5, "denominator": 1},
             "status": "measured-display-appearance-change", "meanLumaProxyDelta": 0.3},
            {"startPts": 20, "endPts": 40, "deltaTimeSeconds": {"numerator": 5, "denominator": 1},
             "status": "cut-boundary", "meanLumaProxyDelta": None},
        ],
    }
    return motion, appearance


class VisualCadenceTests(unittest.TestCase):
    def test_distinct_sample_timelines_summarized_without_physical_claims(self):
        motion, appearance = fixture()
        summary = summarize_visual_cadence(motion, appearance)
        self.assertEqual(summary["schemaVersion"], "kumiki.visual-cadence.v1")
        self.assertEqual(summary["reviewStatus"], "measurement-only-no-camera-or-lighting-verification")
        image = summary["imagePlaneMotion"]
        self.assertEqual(image["pairCount"], 4)
        self.assertEqual(image["measuredPairCount"], 3)
        self.assertEqual(image["measuredPairSeconds"], 7.5)
        self.assertEqual(image["measuredPairFraction"], 0.75)
        self.assertEqual(image["activeTimeFractionOfMeasured"], round(5 / 7.5, 6))
        self.assertEqual(image["activeRunCountInSampledSpan"], 2)
        self.assertEqual(image["activeRunsPerSampledMinute"], 12)
        self.assertEqual(image["cutCandidatesPerSampledMinute"], 6)
        light = summary["displayLumaChange"]
        self.assertEqual(light["measuredPairSeconds"], 5)
        self.assertEqual(light["activeRunCountInSampledSpan"], 1)
        self.assertEqual(light["activeTimeFractionOfMeasured"], 1)

    def test_unobservable_pairs_abstain_not_fabricate_zero_motion(self):
        motion, appearance = fixture()
        for pair in motion["pairs"]:
            if pair["status"] == "measured-image-translation":
                pair.update(status="unobservable-low-texture", dxNormalized=None, dyNormalized=None)
        result = summarize_visual_cadence(motion, appearance)["imagePlaneMotion"]
        self.assertEqual(result["measuredPairSeconds"], 0)
        self.assertIsNone(result["activeTimeFractionOfMeasured"])
        self.assertIsNone(result["timeWeightedMeanSpeedPerSecond"])
        self.assertIsNone(result["activeRunCountInSampledSpan"])

    def test_reject_provenance_cut_status_nonnumeric_or_inconsistent_pts(self):
        for name, mutate in (
            ("source", lambda m, a: a.update(sourceSha256="b" * 64)),
            ("timebase", lambda m, a: a.update(sourceTimebase={"numerator": 1, "denominator": 30})),
            ("stream", lambda m, a: a.update(sourceStreamIndex=2)),
            ("cut", lambda m, a: m["pairs"][2].update(status="measured-image-translation",
                                                dxNormalized=0, dyNormalized=0)),
            ("missing", lambda m, a: m["pairs"][0].update(dxNormalized=None)),
            ("misleading status", lambda m, a: m["pairs"][0].update(status="camera-pan")),
            ("wrong duration", lambda m, a: a["changes"][0].update(
                deltaTimeSeconds={"numerator": 1, "denominator": 1})),
            ("nonfinite", lambda m, a: m["pairs"][0].update(dxNormalized=float("nan"))),
            ("descending PTS", lambda m, a: m["samples"][1].update(sourcePts=-1)),
        ):
            with self.subTest(name=name):
                motion, appearance = fixture()
                mutate(motion, appearance)
                with self.assertRaises(ValueError):
                    summarize_visual_cadence(motion, appearance)
        with self.assertRaisesRegex(ValueError, "threshold"):
            summarize_visual_cadence(*fixture(), luma_change_threshold=0)

    def test_cli_bounded_inputs_and_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            motion, appearance = fixture()
            mp = directory / "motion.json"
            ap = directory / "appearance.json"
            mp.write_text(json.dumps(motion))
            ap.write_text(json.dumps(appearance))
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                self.assertEqual(main(["visual-cadence", str(mp), str(ap)]), 0)
            self.assertEqual(json.loads(capture.getvalue())["imagePlaneMotion"]["activeRunCountInSampledSpan"], 2)
            mp.write_text('{"a":1,"a":2}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_cadence_input(mp)
            mp.write_text('{"a":NaN}')
            with self.assertRaisesRegex(ValueError, "non-finite"):
                load_cadence_input(mp)
            mp.write_bytes(b" " * 2_097_153)
            with self.assertRaisesRegex(ValueError, "2 MiB"):
                load_cadence_input(mp)
            alias = directory / "alias.json"
            alias.symlink_to(ap)
            with self.assertRaisesRegex(ValueError, "regular"):
                load_cadence_input(alias)
