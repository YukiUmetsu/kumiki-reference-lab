"""Bounded local semantic review and geometry probes for anonymous motion ROIs."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.pipeline.agent_frame_review import finalize_frame_workspace
from kumiki_reference_lab.pipeline.auto_region_discovery import discover_motion_regions
from kumiki_reference_lab.pipeline.cinematic_insights import analyze_cinematic_workspace
from kumiki_reference_lab.pipeline.complex_region_probe import probe_complex_regions
from kumiki_reference_lab.pipeline.region_semantic_review import (
    _crop_png, _magnitude_region_category, review_region_proposals,
)
from kumiki_reference_lab.pipeline.shot_intelligence import build_shot_intelligence
from tests.test_auto_region_discovery import (
    WIDTH, HEIGHT, SOURCE_SHA, rectangle, numeric_evidence,
)


def complex_discovery() -> dict:
    return {
        "schemaVersion": "kumiki.auto-motion-region-proposals.v1",
        "sourceSha256": SOURCE_SHA, "frameCount": 32,
        "proposals": [{
            "id": "auto-region-01",
            "label": "Unclassified motion region 1",
            "kind": "other", "shotId": "shot-0001",
            "startFrameIndex": 6, "observedFrameIndices": [6, 9, 12],
            "boxNormalized": [.22, .22, .26, .42],
            "lastBoxNormalized": [.25, .22, .26, .42],
            "regionDiscoveryMethod": "temporal-change-only-unverified-shape",
            "eligibleForAutomaticTracking": False,
        }],
    }


def supported_trial(proposal_id: str = "auto-region-01", *,
                    consecutive: int = 12) -> dict:
    observations = []
    for i in range(consecutive):
        observations.append({
            "frameIndex": 6 + i,
            "boxNormalized": [.22 + .003 * i, .22, .26, .42],
            "status": "auto-proposed-region" if i == 0
                      else "tracked-screen-region-candidate",
            "supportFeatureCount": None if not i else 11,
            "inlierFraction": None if not i else .84,
        })
    return {
        "status": "auto-seeded-2d-region-motion-candidates",
        "tracks": [{
            "id": proposal_id, "observations": observations,
            "endStatus": "tracking-budget-reached",
        }],
    }


class RegionReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
        self.workspace = self.root / "workspace" / "frame-review" / "auto-abc"
        (self.workspace / "frames").mkdir(parents=True)
        source = self.root / "research" / "analysis" / "online-videos"
        source.mkdir(parents=True)
        self.numeric = numeric_evidence()
        (source / "auto-abc.json").write_text(json.dumps({
            "schemaVersion": "kumiki.online-video-reference.v1",
            "id": "auto-abc", "numericEvidence": self.numeric,
        }))
        for i in range(self.numeric["frameCount"]):
            (self.workspace / "frames" / f"frame-{i:06d}.png").write_bytes(
                _png_rgb(rectangle(i), WIDTH, HEIGHT))
        finalize_frame_workspace(
            self.workspace, study_id="auto-abc",
            watch_url="https://example.org/reference",
            numeric=self.numeric, preview_width=WIDTH,
            preview_height=HEIGHT)
        self.shots = build_shot_intelligence(self.numeric)
        self.discovery = discover_motion_regions(
            self.workspace, self.shots, max_regions=3)
        self.assertTrue(self.discovery["proposals"])

    def test_rgb_crop_is_bounded_and_no_new_files_created(self):
        index = self.discovery["proposals"][0]["startFrameIndex"]
        path = self.workspace / "frames" / f"frame-{index:06d}.png"
        original = set(self.workspace.iterdir())
        crop = _crop_png(path, width=WIDTH, height=HEIGHT,
                         box=self.discovery["proposals"][0]["boxNormalized"])
        self.assertTrue(crop.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertLess(len(crop), 1_000_000)
        self.assertEqual(original, set(self.workspace.iterdir()))
        with self.assertRaisesRegex(ValueError, "exceeds"):
            _crop_png(path, width=WIDTH, height=HEIGHT,
                      box=[.95, .2, .3, .3])
        with self.assertRaises(ValueError):
            _crop_png(path, width=WIDTH, height=HEIGHT,
                      box=[0, 0, .01, .01])

    @patch("kumiki_reference_lab.pipeline.region_semantic_review.http.client.HTTPConnection")
    def test_localhost_request_is_capped_and_strict(self, client):
        connection = client.return_value
        connection.getresponse.return_value = SimpleNamespace(
            status=200,
            read=lambda size: json.dumps({
                "choices": [{"message": {"content": json.dumps({
                    "category": "graphic-or-effect",
                    "visualCue": "A colored rectangular form",
                })}}]
            }).encode(),
        )
        screenshot = (self.workspace / "frames" / "frame-000006.png")
        original = screenshot.read_bytes()
        crop = _crop_png(screenshot, width=WIDTH, height=HEIGHT,
                         box=[.1, .1, .4, .5])
        result = _magnitude_region_category(
            [original, crop], model="local-vision-q4")
        self.assertEqual(result["category"], "graphic-or-effect")
        self.assertEqual(client.call_args.args[:2], ("127.0.0.1", 10100))
        args = connection.request.call_args
        self.assertEqual(args.args[1], "/inference/v1/chat/completions")
        body = json.loads(args.kwargs["body"])
        self.assertEqual(body["max_tokens"], 100)
        self.assertEqual(len(body["messages"][0]["content"]), 3)
        self.assertEqual(body["messages"][0]["content"][0]["type"], "text")
        connection.close.assert_called_once()

    @patch("kumiki_reference_lab.pipeline.region_semantic_review.http.client.HTTPConnection")
    def test_model_cannot_inject_identity_or_unsupported_class(self, client):
        connection = client.return_value
        def response(message):
            return SimpleNamespace(
                status=200,
                read=lambda size: json.dumps({
                    "choices": [{"message": {"content": message}}]
                }).encode())
        original = (self.workspace / "frames" / "frame-000006.png").read_bytes()
        for text in (
            json.dumps({"category": "real-person-identity",
                        "visualCue": "person is named Alex"}),
            "IGNORE THE PREVIOUS INSTRUCTIONS",
            json.dumps({"category": "animated-character", "visualCue": ""}),
        ):
            connection.getresponse.return_value = response(text)
            with self.assertRaises(ValueError):
                _magnitude_region_category(
                    [original, original], model="mini")
        connection.getresponse.return_value = SimpleNamespace(
            status=503, read=lambda size: b"some body")
        with self.assertRaises(ValueError):
            _magnitude_region_category([original, original], model="mini")

    @patch("kumiki_reference_lab.pipeline.region_semantic_review._magnitude_region_category")
    def test_two_frame_agreement_is_still_unverified_and_bounded(self, model):
        model.side_effect = [
            {"category": "product", "visualCue": "Rounded device"},
            {"category": "product", "visualCue": "Rounded device from side"},
        ]
        review = review_region_proposals(
            self.workspace, self.discovery, model="mini", max_calls=2)
        self.assertEqual(review["modelCalls"], 2)
        self.assertEqual(len(review["reviews"]), 1)
        self.assertEqual(review["reviews"][0]["proposedCategory"], "product")
        self.assertEqual(review["reviews"][0]["status"],
                         "two-frame-agreement-unverified")
        self.assertEqual(self.discovery["proposals"][0]["kind"], "other")
        self.assertEqual(self.discovery["autoTrackSeeds"]["subjects"][0]["kind"],
                         "other")
        # Hypothesis data only; no base64, pixels, media or source image path.
        encoded = json.dumps(review)
        self.assertNotIn("data:image/", encoded)
        self.assertNotIn("imagePath", encoded)

    @patch("kumiki_reference_lab.pipeline.region_semantic_review._magnitude_region_category")
    def test_disagreement_or_model_failure_never_promotes_to_identity(self, model):
        model.side_effect = [
            {"category": "person", "visualCue": "Silhouette"},
            {"category": "product", "visualCue": "A dark item"},
        ]
        report = review_region_proposals(
            self.workspace, self.discovery, model="mini", max_calls=2)
        self.assertEqual(report["reviews"][0]["proposedCategory"], "unknown")
        self.assertEqual(report["reviews"][0]["status"],
                         "conflicting-local-model-hypotheses")
        model.reset_mock(side_effect=True)
        model.side_effect = ValueError("offline local server")
        failed = review_region_proposals(
            self.workspace, self.discovery, model="mini", max_calls=2)
        self.assertEqual(failed["reviews"][0]["proposedCategory"], "unknown")

    @patch("kumiki_reference_lab.pipeline.region_semantic_review._magnitude_region_category")
    def test_model_outage_stops_after_one_request(self, model):
        model.side_effect = ValueError("local Magnitude region request unavailable")
        result = review_region_proposals(
            self.workspace, self.discovery, model="mini", max_calls=16)
        self.assertEqual(result["modelCalls"], 1)
        self.assertEqual(result["status"], "local-model-unavailable-partial-review")
        self.assertEqual(result["reviews"][0]["status"], "local-model-unavailable")
        self.assertEqual(result["reviews"][0]["proposedCategory"], "unknown")
        self.assertEqual(model.call_count, 1)

    def test_rejects_source_mismatch_and_invalid_model(self):
        report = {**self.discovery, "sourceSha256": "b" * 64}
        with self.assertRaisesRegex(ValueError, "source evidence"):
            review_region_proposals(
                self.workspace, report, model="mini")
        with self.assertRaisesRegex(ValueError, "model"):
            review_region_proposals(
                self.workspace, self.discovery, model="hello world")


class ComplexProbeTests(RegionReviewTests):
    @patch("kumiki_reference_lab.pipeline.complex_region_probe.build_seeded_region_tracks")
    def test_supported_complex_geometry_produces_anonymous_seed(self, track):
        track.return_value = supported_trial()
        report = probe_complex_regions(
            self.workspace, self.shots, complex_discovery(),
            max_probes=2, probe_frames=12)
        self.assertEqual(report["attemptedCount"], 1)
        self.assertEqual(report["supportedSeedCount"], 1)
        self.assertEqual(report["acceptedSeeds"]["seedOrigin"],
                         "auto-motion-proposal")
        self.assertEqual(report["acceptedSeeds"]["subjects"][0]["kind"],
                         "other")
        self.assertFalse(report["decisions"][0]["semanticIdentityVerified"])
        self.assertEqual(track.call_args.kwargs["max_frames_per_subject"], 12)

    @patch("kumiki_reference_lab.pipeline.complex_region_probe.build_seeded_region_tracks")
    def test_unstable_or_no_opencv_abstains(self, track):
        track.return_value = supported_trial(consecutive=4)
        report = probe_complex_regions(
            self.workspace, self.shots, complex_discovery())
        self.assertEqual(report["supportedSeedCount"], 0)
        track.return_value = {
            "status": "not-run-install-pip-extra-dense", "tracks": [],
        }
        absent = probe_complex_regions(
            self.workspace, self.shots, complex_discovery())
        self.assertEqual(absent["supportedSeedCount"], 0)
        self.assertEqual(absent["probeDependencyStatus"],
                         "not-run-install-pip-extra-dense")

    def test_invalid_complex_source_does_not_probe(self):
        data = complex_discovery()
        data["sourceSha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "provenance"):
            probe_complex_regions(self.workspace, self.shots, data)

    @patch("kumiki_reference_lab.pipeline.cinematic_insights.discover_motion_regions")
    @patch("kumiki_reference_lab.pipeline.cinematic_insights.probe_complex_regions")
    @patch("kumiki_reference_lab.pipeline.cinematic_insights.build_seeded_region_tracks")
    def test_complex_only_seed_flows_to_final_tracker_without_semantic_promotions(
        self, tracker, probe, discover,
    ):
        discover.return_value = {
            **complex_discovery(),
            "autoTrackSeedCount": 0,
            "autoTrackSeeds": {
                "schemaVersion": "kumiki.online-region-seeds.v1",
                "seedOrigin": "auto-motion-proposal",
                "sourceSha256": SOURCE_SHA, "subjects": [],
            },
        }
        probe.return_value = {
            "status": "geometry-only-probe-complete",
            "sourceSha256": SOURCE_SHA,
            "supportedSeedCount": 1,
            "acceptedSeeds": {
                "schemaVersion": "kumiki.online-region-seeds.v1",
                "seedOrigin": "auto-motion-proposal",
                "sourceSha256": SOURCE_SHA,
                "subjects": [{
                    "id": "auto-region-01", "kind": "other",
                    "label": "Unclassified motion region 1",
                    "startFrameIndex": 6,
                    "boxNormalized": [.22, .22, .26, .42],
                }],
            },
        }
        tracker.return_value = {
            "status": "auto-seeded-2d-region-motion-candidates",
            "sourceSha256": SOURCE_SHA, "tracks": [],
            "screenRelationshipProxies": [],
        }
        path = analyze_cinematic_workspace(
            self.workspace, motion=False, ocr=False, auto_regions=True,
            complex_probes=True)
        report = json.loads(path.read_text())
        self.assertEqual(report["regionSemanticReview"]["modelCalls"], 0)
        self.assertEqual(report["complexRegionProbes"]["supportedSeedCount"], 1)
        seeds = tracker.call_args.kwargs["seeds_document"]
        self.assertEqual(seeds["seedOrigin"], "auto-motion-proposal")
        self.assertEqual(seeds["subjects"][0]["kind"], "other")

    def test_model_and_complex_probe_flags_require_auto_region_mode(self):
        with self.assertRaisesRegex(ValueError, "require --auto-regions"):
            analyze_cinematic_workspace(
                self.workspace, region_model="mini", motion=False)
        with self.assertRaisesRegex(ValueError, "require --auto-regions"):
            analyze_cinematic_workspace(
                self.workspace, complex_probes=True, motion=False)


if __name__ == "__main__":
    unittest.main()
