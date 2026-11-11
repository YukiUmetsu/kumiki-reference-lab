"""No-model, source-bound multi-region temporal events and pairwise motion QA."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.pipeline.multi_region_temporal import (
    SCHEMA_VERSION, build_multi_region_temporal,
)
from kumiki_reference_lab.pipeline.shot_intelligence import build_shot_intelligence
from tests.test_cinematic_intelligence import evidence, fixture

HASH = "a" * 64


def make_track(ident: str, *, shot: str = "shot-0001",
               start: int = 0, count: int = 12,
               x0: float = .10, dx: float = .02,
               y0: float = .20, dy: float = 0.,
               width: float = .15, height: float = .25,
               area_scale: float = 1.,
               origin: str = "operator-seeded-not-model-recognized") -> dict:
    obs = []
    for j in range(count):
        index = start + j
        box = [x0 + dx * j, y0 + dy * j,
               width * (1 + (area_scale - 1) * j / max(1, count - 1)),
               height]
        obs.append({
            "frameIndex": index,
            "decodedSeconds": index / 10,
            "boxNormalized": box,
            "status": ("auto-proposed-region" if j == 0 and
                       origin == "auto-motion-proposal-not-semantic-identity"
                       else "operator-provided-seed" if j == 0
                       else "tracked-screen-region-candidate"),
            "supportFeatureCount": None if j == 0 else 12,
            "inlierFraction": None if j == 0 else .83,
            "screenScaleRatioFromSeed": 1.,
            "screenRotationDegreesFromSeed": 0.,
        })
    return {
        "id": ident,
        "shotId": shot,
        "kind": "other" if origin.startswith("auto") else "animated-character",
        "label": "Unclassified region" if origin.startswith("auto") else ident,
        "startFrameIndex": start,
        "lastObservedFrameIndex": start + count - 1,
        "observationCount": count,
        "observations": obs,
        "identityProvenance": origin,
    }


def make_report(*tracks: dict) -> dict:
    return {
        "schemaVersion": "kumiki.online-seeded-region-tracks.v1",
        "sourceSha256": HASH,
        "status": ("auto-seeded-2d-region-motion-candidates"
                   if tracks and tracks[0]["identityProvenance"].startswith("auto")
                   else "seeded-2d-region-motion-candidates"),
        "tracks": list(tracks),
    }


class MultiRegionEventTests(unittest.TestCase):
    def setUp(self):
        self.numeric = evidence()
        self.shots = build_shot_intelligence(self.numeric)

    def derive(self, *tracks, **kwargs):
        return build_multi_region_temporal(
            make_report(*tracks), self.numeric, self.shots, **kwargs)

    def test_independent_motion_and_approach_with_box_overlap(self):
        a = make_track("hero-a", dx=.025)
        b = make_track("hero-b", x0=.70, dx=-.0375)
        result = self.derive(a, b)
        self.assertEqual(result["schemaVersion"], SCHEMA_VERSION)
        self.assertEqual(result["sourceSha256"], HASH)
        self.assertEqual(result["trackCount"], 2)
        self.assertEqual(result["pairCount"], 1)
        kinds = {e["eventType"] for e in result["events"]}
        self.assertIn("region-image-plane-translation", kinds)
        self.assertIn("screen-centers-closer", kinds)
        self.assertIn("screen-box-overlap-onset", kinds)
        self.assertIn("horizontal-image-order-reversal", kinds)
        self.assertNotIn("touching", kinds)
        self.assertNotIn("walking", kinds)
        pair = result["pairMetrics"][0]
        self.assertEqual(pair["coObservedConsecutiveFrameCount"], 12)
        self.assertGreater(pair["startCenterDistanceNormalized"],
                           pair["endCenterDistanceNormalized"])
        self.assertGreater(pair["overlapFrameCount"], 0)
        self.assertTrue(all(e["shotId"] == "shot-0001"
                            for e in result["events"]))
        self.assertTrue(all(
            e["startFrameIndex"] <= i <= e["endFrameIndex"]
            for e, task in zip(result["events"], result["reviewTasks"])
            for i in task["frameIndices"]
        ))
        output = json.dumps(result, allow_nan=False)
        self.assertNotIn("data:image", output)
        self.assertNotIn("png", output.lower())

    def test_parallel_motion_is_not_called_following(self):
        a = make_track("region-a", dx=.02)
        b = make_track("region-b", x0=.55, dx=.02)
        result = self.derive(a, b)
        kinds = [e["eventType"] for e in result["events"]]
        self.assertIn("shared-image-plane-displacement", kinds)
        self.assertNotIn("screen-centers-closer", kinds)
        self.assertNotIn("following", kinds)
        cue = next(e for e in result["events"]
                   if e["eventType"] == "shared-image-plane-displacement")
        self.assertIn("shared camera motion",
                      cue["measurements"]["possibleAlternatives"])

    def test_size_change_is_only_an_apparent_box_measurement(self):
        r = make_track("region-a", dx=0, area_scale=1.6)
        result = self.derive(r)
        self.assertIn("region-apparent-box-area-change",
                      [e["eventType"] for e in result["events"]])
        self.assertNotIn("camera-zoom", [e["eventType"] for e in result["events"]])

    def test_different_shots_cannot_be_joined_or_claim_colocated(self):
        a = make_track("region-a", start=0, count=12)
        b = make_track("region-b", shot="shot-0002",
                       start=12, count=12, x0=.4)
        result = self.derive(a, b)
        self.assertEqual(result["pairCount"], 0)
        self.assertEqual(result["pairMetrics"], [])
        self.assertTrue(all(e["subjectB"] is None for e in result["events"]))
        self.assertTrue(all(e["shotId"] in ("shot-0001", "shot-0002")
                            for e in result["events"]))

    def test_fewer_than_six_observations_cannot_make_an_action(self):
        a = make_track("region-a", count=4, dx=.04)
        b = make_track("region-b", count=4, x0=.7, dx=-.04)
        result = self.derive(a, b)
        self.assertEqual(result["pairCount"], 0)
        self.assertEqual(result["events"], [])
        self.assertEqual(result["status"], "no-supported-screen-geometry-events")

    def test_manual_and_anonymous_track_provenance_remains_distinct(self):
        a = make_track("region-a")
        b = make_track(
            "auto-region-01", x0=.7, dx=-.03,
            origin="auto-motion-proposal-not-semantic-identity")
        result = self.derive(a, b)
        self.assertEqual(result["trackCount"], 2)
        self.assertTrue(any(
            "auto-motion-proposal-not-semantic-identity"
            in e["identityProvenance"] for e in result["events"]))
        self.assertNotIn("confirmed", json.dumps(result).lower())

    def test_rejects_discontinuity_invalid_pts_or_provenance(self):
        a = make_track("region-a")
        a["observations"][5]["frameIndex"] += 2
        with self.assertRaisesRegex(ValueError, "frame gap"):
            self.derive(a)
        a = make_track("region-a")
        a["observations"][5]["decodedSeconds"] += .03
        with self.assertRaisesRegex(ValueError, "source PTS"):
            self.derive(a)
        a = make_track("region-a")
        a["observations"][4]["inlierFraction"] = .2
        with self.assertRaisesRegex(ValueError, "unsupported geometry"):
            self.derive(a)
        a = make_track("region-a")
        a["identityProvenance"] = "verified-same-actor-across-cuts"
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.derive(a)
        a = make_track("region-a")
        a["observations"][6]["boxNormalized"][0] = 1.3
        with self.assertRaisesRegex(ValueError, "outside"):
            self.derive(a)

    def test_sha_and_shot_disagreement_rejected(self):
        bad = make_report(make_track("a"))
        bad["sourceSha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "provenance"):
            build_multi_region_temporal(bad, self.numeric, self.shots)
        bad = make_report(make_track("a"))
        wrong_shots = {**self.shots, "sourceSha256": "b" * 64}
        with self.assertRaisesRegex(ValueError, "source/shot"):
            build_multi_region_temporal(bad, self.numeric, wrong_shots)

    def test_report_budgets_and_missing_tracking_explicit(self):
        for status in ("not-requested", "not-run-install-pip-extra-dense",
                       "not-measured-no-auto-regions"):
            result = build_multi_region_temporal(
                {"status": status}, self.numeric, self.shots)
            self.assertEqual(result["status"],
                             "not-measured-no-supported-roi-tracks")
            self.assertEqual(result["sourceSha256"], HASH)
        a = make_track("a", dx=.02)
        b = make_track("b", x0=.70, dx=-.03)
        trimmed = self.derive(a, b, max_events=2, max_review_tasks=1)
        self.assertLessEqual(len(trimmed["events"]), 2)
        self.assertLessEqual(len(trimmed["reviewTasks"]), 1)
        with self.assertRaisesRegex(ValueError, "budgets"):
            self.derive(a, max_events=0)

    def test_no_overlap_candidates_if_pair_observations_not_synchronous(self):
        a = make_track("a", start=0, count=8)
        b = make_track("b", start=8, count=4, x0=.5)
        result = self.derive(a, b)
        self.assertEqual(result["pairCount"], 0)


class CinematicMultiRegionIntegrationTests(unittest.TestCase):
    @patch("kumiki_reference_lab.pipeline.cinematic_insights.build_seeded_region_tracks")
    def test_source_hashed_events_in_standard_online_cinematic_report(self, tracker):
        from kumiki_reference_lab.pipeline.cinematic_insights import (
            analyze_cinematic_workspace,
        )
        tracker.return_value = make_report(
            make_track("actor-left", dx=.025),
            make_track("actor-right", x0=.7, dx=-.032))
        with tempfile.TemporaryDirectory() as directory:
            workspace = fixture(Path(directory))
            outfile = analyze_cinematic_workspace(
                workspace, motion=False, ocr=False,
                roi_seeds=Path(directory) / "sample-roi.json",
                max_multi_events=12, max_multi_review_tasks=4)
            data = json.loads(outfile.read_text())
            measured = data["multiRegionTemporal"]
            self.assertEqual(measured["sourceSha256"], HASH)
            self.assertEqual(measured["trackCount"], 2)
            self.assertEqual(measured["pairCount"], 1)
            self.assertTrue(measured["events"])
            self.assertLessEqual(len(measured["events"]), 12)
            self.assertLessEqual(len(measured["reviewTasks"]), 4)
            self.assertFalse(data["regionSemanticReview"]["modelCalls"])

    def test_no_roi_returns_explicit_no_measurement(self):
        from kumiki_reference_lab.pipeline.cinematic_insights import (
            analyze_cinematic_workspace,
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = fixture(Path(directory))
            report = analyze_cinematic_workspace(workspace, motion=False)
            data = json.loads(report.read_text())
            self.assertEqual(
                data["multiRegionTemporal"]["status"],
                "not-measured-no-supported-roi-tracks",
            )
            self.assertEqual(data["multiRegionTemporal"]["events"], [])


if __name__ == "__main__":
    unittest.main()
