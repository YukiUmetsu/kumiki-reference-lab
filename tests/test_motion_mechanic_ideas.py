"""Source-geometry-backed specific animation idea proposals with no action hallucinations."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.pipeline.motion_mechanic_ideas import (
    SCHEMA_VERSION, propose_motion_mechanics,
)
from kumiki_reference_lab.pipeline.multi_region_temporal import (
    build_multi_region_temporal,
)
from kumiki_reference_lab.pipeline.shot_intelligence import build_shot_intelligence
from tests.test_cinematic_intelligence import evidence, fixture
from tests.test_multi_region_temporal import make_track, make_report

HASH = "a" * 64


def observed_events() -> dict:
    numeric = evidence()
    shots = build_shot_intelligence(numeric)
    tracks = make_report(
        make_track("a", dx=.025),
        make_track("b", x0=.70, dx=-.0375),
        make_track("c", x0=.08, y0=.52, dx=0, area_scale=1.6),
        make_track("d", start=12, shot="shot-0002", x0=.4, dx=-.02),
        make_track("e", start=12, shot="shot-0002", x0=.5, dx=.025),
    )
    return build_multi_region_temporal(tracks, numeric, shots)


class OriginalMechanicIdeasTests(unittest.TestCase):
    def test_source_mechanics_are_specific_animation_templates_not_generic_ui(self):
        temporal = observed_events()
        report = propose_motion_mechanics(temporal)
        self.assertEqual(report["schemaVersion"], SCHEMA_VERSION)
        self.assertEqual(report["sourceSha256"], HASH)
        self.assertEqual(report["measuredEventCount"], len(temporal["events"]))
        self.assertTrue(report["proposals"])
        assertset = {p["originalRecipe"] for p in report["proposals"]}
        self.assertIn("directed-screen-travel", assertset)
        self.assertIn("apparent-scale-focus", assertset)
        self.assertIn("paired-convergence", assertset)
        self.assertIn("two-lane-swap", assertset)
        self.assertIn("layered-crossing-reveal", assertset)
        self.assertIn("paired-divergence", assertset)
        self.assertNotIn("object-handoff", assertset)
        self.assertNotIn("walking-character", assertset)
        for p in report["proposals"]:
            self.assertFalse(p["registryApiVerifiedForThisRecipe"])
            self.assertTrue(p["requiresOriginalArtAssets"])
            self.assertIn("unreviewed", p["status"])
            self.assertEqual(p["sourceEvidence"]["sourceSha256"], HASH)
            self.assertEqual(len(p["sourceEvidence"]["frameRange"]), 2)
            self.assertGreaterEqual(len(p["originalChoreographyStages"]), 3)
            self.assertGreaterEqual(len(p["authoringControlNames"]), 3)
            self.assertTrue(all(module.startswith("registry/")
                                for module in p["candidateRegistryModuleFiles"]))
        self.assertNotIn("data:image/", json.dumps(report))
        self.assertNotIn("targetComponentApiVerified\": true", json.dumps(report))
        self.assertIn("not verified", report["uiRegistryFileAudit"]["meaning"])

    def test_shipped_lane_swap_is_pinned_and_not_a_source_animation_spec(self):
        temporal = observed_events()
        report = propose_motion_mechanics(temporal)
        swaps = [proposal for proposal in report["proposals"]
                 if proposal["originalRecipe"] == "two-lane-swap"]
        self.assertEqual(len(swaps), 1)
        swap = swaps[0]
        shipped = swap["availableOriginalImplementation"]
        self.assertEqual(shipped["registryItem"], "two-lane-swap")
        self.assertEqual(shipped["repository"], "YukiUmetsu/kumiki-ui")
        self.assertEqual(shipped["commitSha"],
                         "662f60704851c01c0e6ef58244132fe9f29896ac")
        self.assertIn("registry/motion/two-lane-swap.ts",
                      shipped["modules"])
        self.assertIn("compileTwoLaneSwap", shipped["publicExports"])
        self.assertIn("TwoLaneSwapSvg", shipped["publicExports"])
        self.assertIn("visual-review-pending", shipped["status"])
        self.assertFalse(shipped["sourceGeometryCanBeUsedAsExecutableSpec"])
        self.assertTrue(shipped["requiresIndependentRenderedVisualApproval"])
        self.assertTrue(swap["requiresOriginalArtAssets"])
        self.assertFalse(swap["registryApiVerifiedForThisRecipe"])
        self.assertTrue(all(p["availableOriginalImplementation"] is None
                            for p in report["proposals"]
                            if p["originalRecipe"] != "two-lane-swap"))
        # Caller mutations must never change the static shipped registry map.
        shipped["modules"].append("invented-add-on.ts")
        shipped["publicExports"].clear()
        again = propose_motion_mechanics(temporal)
        available = next(p for p in again["proposals"] if
                         p["originalRecipe"] == "two-lane-swap")[
                             "availableOriginalImplementation"]
        self.assertNotIn("invented-add-on.ts", available["modules"])
        self.assertIn("TwoLaneSwapSvg", available["publicExports"])
        self.assertEqual(again["proposals"][0]["id"],
                         report["proposals"][0]["id"])

    def test_shared_background_motion_is_not_asserted_camera_pan(self):
        numeric = evidence()
        shots = build_shot_intelligence(numeric)
        tracks = make_report(
            make_track("a", dx=.02),
            make_track("b", x0=.55, dx=.02))
        temporal = build_multi_region_temporal(tracks, numeric, shots)
        result = propose_motion_mechanics(temporal)
        ideas = [p for p in result["proposals"]
                 if p["originalRecipe"] == "shared-shift-with-optional-parallax"]
        self.assertEqual(len(ideas), 1)
        self.assertIn("physical camera movement", ideas[0]["sourceDoesNotProve"])
        self.assertIn("layerParallaxFactors", ideas[0]["authoringControlNames"])
        self.assertFalse(ideas[0]["registryApiVerifiedForThisRecipe"])

    def test_safe_bounds_and_deterministic_ids(self):
        temporal = observed_events()
        a = propose_motion_mechanics(temporal, max_candidates=4, max_per_mechanic=1)
        b = propose_motion_mechanics(temporal, max_candidates=4, max_per_mechanic=1)
        self.assertEqual(a, b)
        self.assertLessEqual(len(a["proposals"]), 4)
        self.assertEqual(len({p["originalRecipe"] for p in a["proposals"]}),
                         len(a["proposals"]))
        self.assertEqual(len({p["id"] for p in a["proposals"]}),
                         len(a["proposals"]))
        with self.assertRaisesRegex(ValueError, "budgets"):
            propose_motion_mechanics(temporal, max_candidates=0)
        with self.assertRaisesRegex(ValueError, "budgets"):
            propose_motion_mechanics(temporal, max_per_mechanic=7)

    def test_empty_tracking_returns_no_mechanics_without_hallucinations(self):
        temporal = {
            "schemaVersion": "kumiki.online-multi-region-temporal.v1",
            "sourceSha256": HASH, "frameCount": 24,
            "status": "not-measured-no-supported-roi-tracks",
            "events": [],
        }
        report = propose_motion_mechanics(temporal)
        self.assertEqual(report["proposedMechanicCount"], 0)
        self.assertEqual(report["proposals"], [])
        self.assertIn("no-supported-geometry", report["status"])

    def test_rejects_tampered_source_events_or_false_semantic_tracking(self):
        temporal = observed_events()
        changed = copy.deepcopy(temporal)
        changed["sourceSha256"] = "not-a-real-hash"
        with self.assertRaisesRegex(ValueError, "source"):
            propose_motion_mechanics(changed)
        changed = copy.deepcopy(temporal)
        changed["events"][0]["status"] = "verified-person-walking"
        with self.assertRaisesRegex(ValueError, "identity"):
            propose_motion_mechanics(changed)
        changed = copy.deepcopy(temporal)
        changed["events"][0]["identityProvenance"] = ["real-name-verified"]
        with self.assertRaisesRegex(ValueError, "identity"):
            propose_motion_mechanics(changed)
        changed = copy.deepcopy(temporal)
        changed["events"][0]["measurements"]["netDistanceNormalized"] = float("nan")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            propose_motion_mechanics(changed)
        changed = copy.deepcopy(temporal)
        changed["events"].append(copy.deepcopy(changed["events"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            propose_motion_mechanics(changed)
        changed = copy.deepcopy(temporal)
        changed["events"][0]["subjectB"] = "invented-other-character"
        with self.assertRaisesRegex(ValueError, "identity"):
            propose_motion_mechanics(changed)

    def test_requires_real_measurement_fields_before_recommending_recipe(self):
        changed = observed_events()
        event = next(e for e in changed["events"] if
                     e["eventType"] == "region-image-plane-translation")
        del event["measurements"]["direction"]
        with self.assertRaisesRegex(ValueError, "required measured"):
            propose_motion_mechanics(changed)

    @patch("kumiki_reference_lab.pipeline.cinematic_insights.build_seeded_region_tracks")
    def test_cinematic_insights_persists_source_linked_mechanic_ideas(self, tracker):
        from kumiki_reference_lab.pipeline.cinematic_insights import (
            analyze_cinematic_workspace,
        )
        tracker.return_value = make_report(
            make_track("a", dx=.025),
            make_track("b", x0=.70, dx=-.0375),
        )
        with tempfile.TemporaryDirectory() as temp:
            workspace = fixture(Path(temp))
            path = analyze_cinematic_workspace(
                workspace, roi_seeds=Path(temp) / "seeds.json",
                max_mechanic_ideas=3, motion=False)
            report = json.loads(path.read_text())
            mechanics = report["originalMotionMechanicIdeas"]
            self.assertEqual(mechanics["sourceSha256"], HASH)
            self.assertLessEqual(mechanics["proposedMechanicCount"], 3)
            self.assertTrue(mechanics["proposals"])
            self.assertIn("No executable animation", json.dumps(mechanics["limitations"]))
            self.assertFalse(any(
                item["registryApiVerifiedForThisRecipe"]
                for item in mechanics["proposals"]
            ))


if __name__ == "__main__":
    unittest.main()
