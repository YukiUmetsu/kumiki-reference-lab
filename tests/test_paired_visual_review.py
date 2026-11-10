"""Source-bound camera/light review comparisons never imply independently seen films."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.audience_benchmarks import load_audience_benchmarks
from kumiki_reference_lab.catalog.paired_visual_review import (
    compare_paired_visual_reviews, load_visual_study_bindings,
)
from kumiki_reference_lab.catalog.video_id_candidates import load_video_id_candidates
from kumiki_reference_lab.catalog.visual_study_plan import build_visual_study_plan
from kumiki_reference_lab.cli.app import main


ROOT = Path(__file__).resolve().parents[1]
AUDIENCE = ROOT / "research/audience-recent-uploads.v1.json"
CANDIDATES = ROOT / "research/video-id-candidates.v1.json"


def event(kind: str, category: str, start: int, end: int) -> dict:
    return {"category": category, "kind": kind, "startPts": start, "endPts": end,
            "assessment": "reviewer-interpreted", "observation": "Seen on synthetic fixture",
            "alternativeExplanation": "Could be compositing or moving subject"}


def review(sha: str, events: list[dict], *, end: int = 71_000,
           coverage: str = "full-window-visual-review", reviewer_id: str = "fixture-reviewer") -> dict:
    return {"schemaVersion": "kumiki.visual-events-review.v1",
            "sourceSha256": sha, "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 1000},
            "reviewer": {"kind": "human", "id": reviewer_id},
            "window": {"startPts": 0, "endPts": end, "coverage": coverage},
            "events": events}


class PairedVisualReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audience = load_audience_benchmarks(AUDIENCE)
        cls.candidates = load_video_id_candidates(CANDIDATES, cls.audience)
        plan = build_visual_study_plan(cls.audience, identity_candidates=cls.candidates)
        cls.pair = next(pair for channel in plan["channels"]
                        for pair in channel["selectedPairs"] if pair["id"] == "kurzgesagt-12-11")

    def setUp(self):
        self.bindings = {"schemaVersion": "kumiki.visual-study-media-bindings.v1",
                         "pairId": self.pair["id"],
                         "evidenceStatus": "self-declared-source-video-to-local-media-not-independently-verified",
                         "mediaLinks": {
                             role: {"sourceRowSha256": self.pair[role]["sourceRowSha256"],
                                    "youtubeId": self.pair[role]["videoIdentityCandidate"]["youtubeId"],
                                    "mediaSha256": sha, "streamIndex": 0}
                             for role, sha in (("higherViewedRow", "a" * 64),
                                               ("lowerViewedRow", "b" * 64))}}
        self.higher = review("a" * 64, [event("pan", "camera-movement", 1_000, 5_000),
                                        event("orbit", "camera-movement", 5_000, 9_000),
                                        event("intensity-ramp", "lighting-change", 10_000, 11_000)])
        self.lower = review("b" * 64, [event("tilt", "camera-movement", 2_000, 6_000),
                                       event("light-sweep", "lighting-change", 7_000, 10_000),
                                       event("shadow-motion", "lighting-change", 12_000, 13_000)])

    def compare(self):
        return compare_paired_visual_reviews(
            self.audience, self.candidates, pair_id=self.pair["id"],
            bindings=self.bindings, higher_review=self.higher, lower_review=self.lower)

    def test_synthetic_equal_windows_produce_only_self_declared_frequency_differences(self):
        result = self.compare()
        self.assertTrue(result["pairedEventRateDifferencesAvailable"])
        self.assertEqual(result["reportedViewsRatio"], 3.0127)
        self.assertEqual(result["roles"]["higherViewedRow"]["mediaSha256"], "a" * 64)
        self.assertEqual(result["roles"]["higherViewedRow"]["review"]["cameraMovementEvents"], 2)
        self.assertAlmostEqual(
            result["pairedEventRateDifferences"]["cameraEventsPerReviewedMinuteHigherMinusLower"],
            60 / 71, delta=1e-6)
        self.assertAlmostEqual(
            result["pairedEventRateDifferences"]["lightingEventsPerReviewedMinuteHigherMinusLower"],
            -60 / 71, delta=1e-6)
        by_kind = {item["kind"]: item for item in result["pairedEventRateDifferences"]["byEventKind"]}
        self.assertEqual(by_kind["pan"]["lowerCount"], 0)
        self.assertEqual(by_kind["tilt"]["higherCount"], 0)
        self.assertGreater(by_kind["pan"]["higherMinusLowerEventsPerReviewedMinute"], 0)
        self.assertLess(by_kind["tilt"]["higherMinusLowerEventsPerReviewedMinute"], 0)
        self.assertIn("self-declared", result["evidenceStatus"])

    def test_partial_or_unbalanced_coverage_and_different_reviewers_abstain(self):
        self.lower["window"].update(endPts=20_000, coverage="partial-window-visual-review")
        self.lower["events"] = [self.lower["events"][0]]
        result = self.compare()
        self.assertFalse(result["pairedEventRateDifferencesAvailable"])
        self.assertIsNone(result["pairedEventRateDifferences"])
        self.lower = review("b" * 64, [], end=65_000)
        self.assertFalse(self.compare()["pairedEventRateDifferencesAvailable"])
        self.lower = review("b" * 64, [], reviewer_id="another-reviewer")
        result = self.compare()
        self.assertFalse(result["sameSelfDeclaredReviewer"])
        self.assertIsNone(result["pairedEventRateDifferences"])

    def test_rejects_stale_wrong_and_colliding_bindings(self):
        mutations = (
            ("stale source", lambda: self.bindings["mediaLinks"]["higherViewedRow"].update(
                sourceRowSha256="0" * 64)),
            ("false youtube", lambda: self.bindings["mediaLinks"]["higherViewedRow"].update(
                youtubeId="unknown-id-0")),
            ("same media", lambda: self.bindings["mediaLinks"]["lowerViewedRow"].update(
                mediaSha256="a" * 64)),
            ("wrong stream", lambda: self.bindings["mediaLinks"]["higherViewedRow"].update(
                streamIndex=1)),
            ("swapped roles", lambda: self.bindings["mediaLinks"].update(
                {"higherViewedRow": copy.deepcopy(self.bindings["mediaLinks"]["lowerViewedRow"])})),
            ("fake provenance", lambda: self.bindings.update(evidenceStatus="independently-verified")),
            ("different review source", lambda: self.higher.update(sourceSha256="c" * 64)),
        )
        for name, mutate in mutations:
            self.setUp()
            with self.subTest(name=name):
                mutate()
                with self.assertRaises(ValueError):
                    self.compare()
        self.setUp()
        with self.assertRaisesRegex(ValueError, "selected default study pair"):
            compare_paired_visual_reviews(self.audience, self.candidates,
                                          pair_id="not-a-pair", bindings=self.bindings,
                                          higher_review=self.higher, lower_review=self.lower)

    def test_rejects_duplicate_json_keys_symlinks_and_large_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bindings.json"
            path.write_text('{"pairId":"a","pairId":"b"}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_visual_study_bindings(path)
            path.write_bytes(b"a" * 16_385)
            with self.assertRaisesRegex(ValueError, "16 KiB"):
                load_visual_study_bindings(path)
            symlink = Path(directory) / "link.json"
            symlink.symlink_to(path)
            with self.assertRaisesRegex(ValueError, "regular"):
                load_visual_study_bindings(symlink)

    def test_cli_uses_same_contract_and_immutable_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for filename, value in (("bindings.json", self.bindings),
                                    ("high.json", self.higher), ("low.json", self.lower)):
                (folder / filename).write_text(json.dumps(value), encoding="utf-8")
            args = ["audience-benchmarks", "compare-visual", "--root", str(AUDIENCE),
                    "--identity-candidates", str(CANDIDATES),
                    "--pair-id", self.pair["id"], "--bindings", str(folder / "bindings.json"),
                    "--higher-review", str(folder / "high.json"),
                    "--lower-review", str(folder / "low.json"), "--out", str(folder / "out")]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
                self.assertEqual(main(args), 0)
            saved = json.loads((folder / "out/paired-visual-review.json").read_text())
            self.assertTrue(saved["pairedEventRateDifferencesAvailable"])
            self.assertEqual(saved["pairId"], self.pair["id"])
