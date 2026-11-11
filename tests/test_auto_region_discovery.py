"""Fast, no-model tests for conservative automatic moving-region discovery."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.pipeline.agent_frame_review import finalize_frame_workspace
from kumiki_reference_lab.pipeline.auto_region_discovery import (
    _candidates, discover_motion_regions,
)
from kumiki_reference_lab.pipeline.cinematic_insights import analyze_cinematic_workspace
from kumiki_reference_lab.pipeline.motion_timing import build_seeded_motion_timing
from kumiki_reference_lab.pipeline.seeded_subjects import validate_region_seeds
from kumiki_reference_lab.pipeline.shot_intelligence import build_shot_intelligence

WIDTH, HEIGHT = 128, 72
SOURCE_SHA = "a" * 64


def rectangle(i: int, *, uniform: bool = True, flash: bool = False) -> bytes:
    pixels = bytearray(WIDTH * HEIGHT * 3)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            p = (y * WIDTH + x) * 3
            if uniform:
                color = (230, 230, 230)
            else:
                color = ((x * 17 + y * 37) % 255,
                         (x * 7 + y * 19) % 255,
                         (x * 41 + y * 3) % 255)
            if flash and i % 2:
                color = (8, 8, 8)
            elif 20 + i <= x < 44 + i and 20 <= y < 41:
                color = (35, 40, 175)
            pixels[p:p+3] = bytes(color)
    return bytes(pixels)


def numeric_evidence(frame_count: int = 32, cut_index: int | None = None) -> dict:
    rows = []
    for i in range(frame_count):
        jump = i == cut_index
        rows.append({
            "frameIndex": i,
            "decodedSeconds": round(i * .1, 6),
            "decodedPts": i * 100,
            "cutCandidate": jump,
            "appearance": {
                "meanRgb": [.5, .5, .5],
                "displayLumaProxy": .5,
                "saturationProxy": .2,
                "brightPixelFraction": .1,
                "darkPixelFraction": .1,
            },
            "changeFromPrevious": (
                {"meanPixelDelta": .7 if jump else .04,
                 "changedPixelFraction": .8 if jump else .08}
                if i else None),
        })
    return {
        "schemaVersion": "kumiki.online-frame-evidence.v1",
        "sourceSha256": SOURCE_SHA, "frameCount": frame_count,
        "frames": rows, "cutCandidateFrameIndices": [cut_index] if cut_index else [],
    }


class AutoRegionDiscoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "pyproject.toml").write_text("[project]\nname='mock'\n")
        self.workspace = self.root / "workspace" / "frame-review" / "auto-abc"
        (self.workspace / "frames").mkdir(parents=True)
        self.data = self.root / "research" / "analysis" / "online-videos"
        self.data.mkdir(parents=True)
        self.numeric = numeric_evidence()
        (self.data / "auto-abc.json").write_text(json.dumps({
            "schemaVersion": "kumiki.online-video-reference.v1",
            "id": "auto-abc",
            "numericEvidence": self.numeric,
        }))
        for i in range(self.numeric["frameCount"]):
            path = self.workspace / "frames" / f"frame-{i:06d}.png"
            path.write_bytes(_png_rgb(rectangle(i), WIDTH, HEIGHT))
        finalize_frame_workspace(
            self.workspace, study_id="auto-abc",
            watch_url="https://example.org/original",
            numeric=self.numeric, preview_width=WIDTH, preview_height=HEIGHT)

    def test_recurring_motion_generates_bounded_auto_seeds_with_truthful_origin(self):
        shots = build_shot_intelligence(self.numeric)
        data = discover_motion_regions(self.workspace, shots, max_regions=3)
        self.assertEqual(data["sourceSha256"], SOURCE_SHA)
        self.assertGreater(data["pairsInspected"], 1)
        self.assertGreaterEqual(data["autoTrackSeedCount"], 1)
        self.assertLessEqual(data["autoTrackSeedCount"], 3)
        seeds = data["autoTrackSeeds"]
        self.assertEqual(seeds["seedOrigin"], "auto-motion-proposal")
        validate_region_seeds(seeds, source_sha=SOURCE_SHA,
                              frame_count=self.numeric["frameCount"])
        for item in data["proposals"]:
            self.assertEqual(item["kind"], "other")
            self.assertTrue(item["label"].startswith("Unclassified"))
            self.assertIn("unverified", item["status"])
            self.assertGreater(item["startFrameIndex"], 0)
            self.assertLess(item["startFrameIndex"], self.numeric["frameCount"] - 4)
            self.assertGreaterEqual(len(item["observedFrameIndices"]), 2)
            self.assertTrue(0 < item["boxNormalized"][2] <= .5)
        self.assertFalse((self.workspace / "auto-regions.json").exists())

    def test_static_image_abstains_without_hallucinated_subject(self):
        (self.workspace / "frames").joinpath("frame-000000.png")
        for i in range(self.numeric["frameCount"]):
            (self.workspace / "frames" / f"frame-{i:06d}.png").write_bytes(
                _png_rgb(rectangle(0), WIDTH, HEIGHT))
        data = discover_motion_regions(
            self.workspace, build_shot_intelligence(self.numeric))
        self.assertEqual(data["autoTrackSeedCount"], 0)
        self.assertEqual(data["proposals"], [])
        self.assertIn("no-persistent", data["status"])

    def test_global_flash_pair_rejected_and_no_fake_subject(self):
        first = bytes([255, 255, 255]) * (WIDTH * HEIGHT)
        second = bytes([0, 0, 0]) * (WIDTH * HEIGHT)
        proposals, status = _candidates(first, second,
                                        width=WIDTH, height=HEIGHT)
        self.assertEqual(proposals, [])
        self.assertEqual(status, "global-change-flash-camera-or-cut")

    def test_complex_background_does_not_auto_track_diff_as_subject(self):
        a = rectangle(0, uniform=False)
        b = rectangle(4, uniform=False)
        proposed, method = _candidates(a, b, width=WIDTH, height=HEIGHT)
        self.assertEqual(method, "temporal-change-only-unverified-shape")
        self.assertFalse(any(p["eligibleForAutomaticTracking"] for p in proposed))

    def test_shot_boundary_and_source_mismatch_rejected(self):
        shots = build_shot_intelligence(self.numeric)
        shots["sourceSha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "provenance"):
            discover_motion_regions(self.workspace, shots)
        self.numeric["frames"][16]["cutCandidate"] = True
        self.numeric["frames"][16]["changeFromPrevious"]["meanPixelDelta"] = .7
        divided = build_shot_intelligence(self.numeric)
        data = discover_motion_regions(self.workspace, divided)
        by_id = {s["shotId"]: s for s in divided["shots"]}
        for proposal in data["proposals"]:
            shot = by_id[proposal["shotId"]]
            self.assertTrue(all(shot["startFrameIndex"] <= i <
                                shot["endFrameIndexExclusive"]
                                for i in proposal["observedFrameIndices"]))

    def test_rejects_malformed_preview(self):
        shot = build_shot_intelligence(self.numeric)
        (self.workspace / "frames" / "frame-000003.png").write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError, "PNG"):
            discover_motion_regions(self.workspace, shot)

    def test_small_local_machine_produces_roi_report_without_cv2_or_vision_model(self):
        with patch.dict(sys.modules, {"cv2": None, "numpy": None}):
            result = analyze_cinematic_workspace(
                self.workspace, motion=False, ocr=False, auto_regions=True,
                max_auto_regions=2)
        data = json.loads(result.read_text())
        self.assertEqual(data["autoRegionProposals"]["sourceSha256"], SOURCE_SHA)
        self.assertGreater(data["autoRegionProposals"]["autoTrackSeedCount"], 0)
        self.assertEqual(data["seededSubjectTracks"]["status"],
                         "not-run-install-pip-extra-dense")
        self.assertEqual(data["seededSubjectTracks"]["seedOrigin"],
                         "auto-motion-proposal")
        self.assertEqual(data["seededMotionTiming"]["status"],
                         "not-measured-no-supported-seeded-tracks")
        self.assertEqual(data["seededMotionTiming"]["sourceSha256"], SOURCE_SHA)
        self.assertEqual(data["kumikiTimingProposals"], [])

    @patch("kumiki_reference_lab.pipeline.cinematic_insights.build_seeded_region_tracks")
    def test_integrated_auto_tracker_receives_anonymous_in_memory_seeds(self, tracker):
        tracker.return_value = {
            "status": "auto-seeded-2d-region-motion-candidates",
            "sourceSha256": SOURCE_SHA, "tracks": [],
            "screenRelationshipProxies": [],
        }
        result = analyze_cinematic_workspace(
            self.workspace, motion=False, ocr=False,
            auto_regions=True, max_auto_regions=2)
        self.assertTrue(result.exists())
        doc = tracker.call_args.kwargs["seeds_document"]
        self.assertEqual(doc["seedOrigin"], "auto-motion-proposal")
        self.assertTrue(doc["subjects"])
        self.assertTrue(all(s["kind"] == "other" for s in doc["subjects"]))
        self.assertNotIn("seeds_file", tracker.call_args.kwargs)

    def test_bad_auto_labels_rejected(self):
        seed = {
            "schemaVersion": "kumiki.online-region-seeds.v1",
            "seedOrigin": "auto-motion-proposal",
            "sourceSha256": SOURCE_SHA,
            "subjects": [{
                "id": "unverified", "kind": "animated-character",
                "label": "Recognized hero", "startFrameIndex": 4,
                "boxNormalized": [.2, .2, .3, .3],
            }],
        }
        with self.assertRaisesRegex(ValueError, "unclassified"):
            validate_region_seeds(seed, source_sha=SOURCE_SHA, frame_count=32)

    def test_automatic_track_timing_provenance_never_claims_operator_label(self):
        from tests.test_motion_timing import seeded_track
        item = seeded_track(count=21)
        item["identityProvenance"] = "auto-motion-proposal-not-semantic-identity"
        item["kind"] = "other"
        item["observations"][0]["status"] = "auto-proposed-region"
        data = build_seeded_motion_timing({
            "status": "auto-seeded-2d-region-motion-candidates",
            "sourceSha256": SOURCE_SHA, "tracks": [item],
        })
        self.assertEqual(data["supportedCurveCount"], 1)
        self.assertEqual(data["tracks"][0]["status"],
                         "timing-shape-candidate-unverified-auto-region")
        self.assertIn("auto-motion", data["tracks"][0]["identityProvenance"])


if __name__ == "__main__":
    unittest.main()
