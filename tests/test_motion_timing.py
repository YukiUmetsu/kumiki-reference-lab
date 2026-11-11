"""No-AI timing curve tests from synthetic operator-seeded frame boxes."""
from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.pipeline.motion_timing import (
    analyze_seeded_track, build_seeded_motion_timing,
    propose_original_timing_recipes,
)

SHA = "b" * 64


def seeded_track(shape: str = "linear", *, count: int = 21,
                 displacement: float = .4, seconds_step: float = .05) -> dict:
    def curve(t: float) -> float:
        if shape == "linear":
            return t
        if shape == "ease-in-quadratic":
            return t * t
        if shape == "ease-out-quadratic":
            return 1 - (1 - t) ** 2
        if shape == "ease-in-out-smoothstep":
            return 3 * t ** 2 - 2 * t ** 3
        if shape == "reverse":
            return t + .10 * math.sin(t * 4 * math.pi)
        if shape == "flat":
            return 0.0
        raise AssertionError(shape)
    observations = []
    for i in range(count):
        t = i / (count - 1)
        x = .1 + displacement * curve(t)
        observations.append({
            "frameIndex": 50 + i,
            "decodedSeconds": round(5 + i * seconds_step, 7),
            "boxNormalized": [x, .2, .16, .2],
            "screenRotationDegreesFromSeed": 0.,
            "screenScaleRatioFromSeed": 1.,
            "supportFeatureCount": None if i == 0 else 12,
            "inlierFraction": .85 if i else None,
            "status": ("operator-provided-seed" if i == 0
                       else "tracked-screen-region-candidate"),
        })
    return {
        "id": "seeded-product", "label": "Original product",
        "kind": "product", "shotId": "shot-0002",
        "startFrameIndex": 50, "lastObservedFrameIndex": 50 + count - 1,
        "observationCount": count, "observations": observations,
        "endStatus": "shot-boundary-or-end",
        "identityProvenance": "operator-seeded-not-model-recognized",
    }


def seeded_report(track: dict) -> dict:
    return {
        "schemaVersion": "kumiki.online-seeded-region-tracks.v1",
        "sourceSha256": SHA, "status": "seeded-2d-region-motion-candidates",
        "tracks": [track], "screenRelationshipProxies": [],
    }


class TimingInferenceTests(unittest.TestCase):
    def test_four_distinct_easing_shapes_and_no_generated_artwork(self):
        for shape in ("linear", "ease-in-quadratic", "ease-out-quadratic",
                      "ease-in-out-smoothstep"):
            with self.subTest(shape=shape):
                measured = analyze_seeded_track(seeded_track(shape))
                self.assertEqual(measured["status"], "timing-shape-candidate")
                self.assertEqual(measured["easingCandidate"]["family"], shape)
                self.assertLess(measured["easingCandidate"][
                    "normalizedRootMeanSquareError"], 1e-4)
                self.assertEqual(measured["observedFrameCount"], 21)
                self.assertEqual(measured["startFrameIndex"], 50)
                self.assertEqual(measured["endFrameIndex"], 70)
                self.assertAlmostEqual(measured["durationSeconds"], 1.0)
                self.assertEqual(measured["keyframeSamples"][0][
                    "projectedProgress"], 0)
                self.assertEqual(measured["keyframeSamples"][-1][
                    "projectedProgress"], 1)
                self.assertEqual(measured["identityProvenance"],
                                 "operator-seeded-not-model-recognized")
                report = build_seeded_motion_timing(seeded_report(seeded_track(shape)))
                recipes = propose_original_timing_recipes(report)
                self.assertEqual(len(recipes), 1)
                self.assertIsNone(recipes[0]["targetStartPosition"])
                self.assertIsNone(recipes[0]["targetDurationSeconds"])
                self.assertFalse(recipes[0]["targetComponentApiVerified"])

    def test_too_short_and_static_abstain(self):
        short = analyze_seeded_track(seeded_track(count=5))
        self.assertEqual(short["status"], "abstain-too-few-supported-observations")
        self.assertIsNone(short["easingCandidate"])
        static = analyze_seeded_track(seeded_track("flat"))
        self.assertEqual(static["status"], "abstain-insufficient-net-translation")
        self.assertFalse(static["keyframeSamples"])

    def test_curved_and_nonmonotonic_paths_abstain(self):
        track = seeded_track()
        for i, point in enumerate(track["observations"]):
            t = i / 20
            point["boxNormalized"][1] = .2 + .10 * math.sin(t * 2 * math.pi)
        curve = analyze_seeded_track(track)
        self.assertEqual(curve["status"], "abstain-curved-reversing-or-unstable-path")

        track = seeded_track()
        track["observations"][10]["boxNormalized"][0] -= .12
        result = analyze_seeded_track(track)
        self.assertTrue(result["status"].startswith("abstain-"))

    def test_nonconsecutive_or_unsourced_frames_are_rejected(self):
        track = seeded_track()
        track["observations"][5]["frameIndex"] += 4
        with self.assertRaisesRegex(ValueError, "missing or unordered"):
            analyze_seeded_track(track)
        track = seeded_track()
        track["observations"][3]["inlierFraction"] = .2
        with self.assertRaisesRegex(ValueError, "supported local"):
            analyze_seeded_track(track)
        track = seeded_track()
        track["identityProvenance"] = "guessed-by-model"
        with self.assertRaisesRegex(ValueError, "provenance"):
            analyze_seeded_track(track)

    def test_unsupported_or_missing_roi_data_requires_no_model(self):
        for status in ("not-requested", "not-run-install-pip-extra-dense"):
            result = build_seeded_motion_timing({
                "sourceSha256": SHA, "status": status, "tracks": []})
            self.assertEqual(result["status"],
                             "not-measured-no-supported-seeded-tracks")
            self.assertEqual(result["tracks"], [])
            self.assertEqual(propose_original_timing_recipes(result), [])
        with self.assertRaises(ValueError):
            build_seeded_motion_timing({
                **seeded_report(seeded_track()), "sourceSha256": "wrong"})
        with self.assertRaises(ValueError):
            build_seeded_motion_timing({
                **seeded_report(seeded_track()), "tracks": [seeded_track()] * 9})

    def test_large_observations_bounded_to_max_24_samples(self):
        track = seeded_track(count=241, seconds_step=.015)
        result = analyze_seeded_track(track)
        self.assertEqual(result["status"], "timing-shape-candidate")
        self.assertLessEqual(len(result["keyframeSamples"]), 24)
        self.assertEqual(result["keyframeSamples"][0]["frameIndex"], 50)
        self.assertEqual(result["keyframeSamples"][-1]["frameIndex"], 290)

    def test_large_temporal_gap_abstains(self):
        track = seeded_track()
        for row in track["observations"][10:]:
            row["decodedSeconds"] += .4
        result = analyze_seeded_track(track)
        self.assertEqual(result["status"], "abstain-uneven-sampling")

    def test_report_serializes_without_nan_or_inference(self):
        out = build_seeded_motion_timing(seeded_report(seeded_track()))
        self.assertEqual(out["supportedCurveCount"], 1)
        encoded = json.dumps(out, allow_nan=False)
        self.assertIn("timing-shape-candidate", encoded)
        self.assertNotIn("sourceImageData", encoded)


class CinematicTimingIntegrationTests(unittest.TestCase):
    def test_cinematic_insights_with_roi_includes_timing_proposals(self):
        from tests.test_cinematic_intelligence import fixture
        from kumiki_reference_lab.pipeline.cinematic_insights import (
            analyze_cinematic_workspace,
        )
        with tempfile.TemporaryDirectory() as folder:
            workspace = fixture(Path(folder))
            # No local vision service, CV2 or new footage is needed:
            # reuse a deterministic operator-seeded observation fixture.
            fake = seeded_report(seeded_track())
            with patch(
                "kumiki_reference_lab.pipeline.cinematic_insights.build_seeded_region_tracks",
                return_value=fake,
            ):
                output = analyze_cinematic_workspace(
                    workspace, roi_seeds=Path(folder) / "seed.json",
                    motion=False, ocr=False,
                )
            data = json.loads(output.read_text())
            self.assertEqual(data["seededMotionTiming"]["supportedCurveCount"], 1)
            self.assertEqual(len(data["kumikiTimingProposals"]), 1)
            self.assertEqual(data["kumikiTimingProposals"][0][
                "timingFamilyHypothesis"], "linear")
            self.assertEqual(data["seededMotionTiming"]["sourceSha256"], SHA if
                             False else "a" * 64)

    def test_cinematic_insights_no_roi_is_explicitly_not_measured(self):
        from tests.test_cinematic_intelligence import fixture
        from kumiki_reference_lab.pipeline.cinematic_insights import (
            analyze_cinematic_workspace,
        )
        with tempfile.TemporaryDirectory() as folder:
            workspace = fixture(Path(folder))
            output = analyze_cinematic_workspace(workspace, motion=False)
            data = json.loads(output.read_text())
            self.assertEqual(data["seededMotionTiming"]["status"],
                             "not-measured-no-supported-seeded-tracks")
            self.assertFalse(data["kumikiTimingProposals"])


if __name__ == "__main__":
    unittest.main()
