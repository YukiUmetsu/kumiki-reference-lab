"""Matched source-row discovery does not invent stable video identity or causes."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.audience_benchmarks import load_audience_benchmarks
from kumiki_reference_lab.catalog.visual_study_plan import build_visual_study_plan
from kumiki_reference_lab.catalog.video_id_candidates import load_video_id_candidates
from kumiki_reference_lab.cli.app import main


ROOT = Path(__file__).resolve().parents[1]
AUDIENCE = ROOT / "research/audience-recent-uploads.v1.json"
CANDIDATES = ROOT / "research/video-id-candidates.v1.json"


class VisualStudyPlanTests(unittest.TestCase):
    def setUp(self):
        self.source = load_audience_benchmarks(AUDIENCE)

    def test_real_snapshot_picks_17_pairs_and_excludes_ambiguities(self):
        result = build_visual_study_plan(self.source)
        self.assertEqual(result["sourceRowCount"], 300)
        self.assertEqual(result["eligibleRowCount"], 283)
        self.assertEqual(result["selectedPairCount"], 17)
        self.assertEqual(result["selectedRowsWithIndexedIdCandidates"], 0)
        self.assertEqual(result["evidenceStatus"],
                         "candidate-row-comparisons-no-verified-video-ids-no-frame-review")
        self.assertTrue(all(len(c["selectedPairs"]) <= 3 for c in result["channels"]))
        self.assertTrue(all(not any(r["videoIdentityCandidate"] for p in c["selectedPairs"]
                                    for r in (p["higherViewedRow"], p["lowerViewedRow"]))
                            for c in result["channels"]))
        self.assertEqual(sum(len(c["ambiguousIdentityGroups"]) for c in result["channels"]), 2)
        for channel in result["channels"]:
            used = set()
            for pair in channel["selectedPairs"]:
                a, b = pair["higherViewedRow"], pair["lowerViewedRow"]
                self.assertNotIn(a["rowIndex"], used)
                self.assertNotIn(b["rowIndex"], used)
                used.update((a["rowIndex"], b["rowIndex"]))
                self.assertGreaterEqual(pair["reportedViewsRatio"], 2)
                self.assertLessEqual(pair["durationRatio"], 1.75)
                self.assertLessEqual(pair["sourceAgeGapDays"], 45)
                self.assertTrue(all(len(r["sourceRowSha256"]) == 64 for r in (a, b)))
                self.assertEqual(a["visualReviewStatus"], "not-performed")
        self.assertEqual(result, build_visual_study_plan(self.source))

    def test_stricter_constraints_abstain_or_return_fewer_pairs(self):
        strict = build_visual_study_plan(self.source, max_age_gap_days=0,
                                         max_duration_ratio=1.0, min_view_ratio=90)
        self.assertLessEqual(strict["selectedPairCount"], 17)
        self.assertTrue(all(len(c["selectedPairs"]) <= 3 for c in strict["channels"]))
        for name, overrides in (
            ("pairs", {"pairs_per_channel": 0}),
            ("age", {"max_age_gap_days": -1}),
            ("duration", {"max_duration_ratio": float("inf")}),
            ("views", {"min_view_ratio": float("nan")}),
            ("huge integer", {"max_duration_ratio": 10**400}),
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                build_visual_study_plan(self.source, **overrides)

    def test_indexed_candidates_are_attached_only_to_exact_source_rows(self):
        candidates = load_video_id_candidates(CANDIDATES, self.source)
        plan = build_visual_study_plan(self.source, identity_candidates=candidates)
        self.assertEqual(plan["selectedRowsWithIndexedIdCandidates"], 6)
        candidates_found = []
        for channel in plan["channels"]:
            for pair in channel["selectedPairs"]:
                for item in (pair["higherViewedRow"], pair["lowerViewedRow"]):
                    if item["videoIdentityCandidate"] is not None:
                        candidates_found.append((channel["channelId"], item["rowIndex"],
                                                 item["videoIdentityCandidate"]["youtubeId"]))
                        self.assertEqual(item["visualReviewStatus"], "not-performed")
        self.assertEqual(candidates_found, [
            ("alan-becker", 19, "xu0mrfxPhbY"),
            ("kurzgesagt", 12, "hiIIGMeMEuE"),
            ("kurzgesagt", 11, "NIifnIP_NnQ"),
            ("real-engineering", 2, "rCM6dvK2Hjg"),
            ("real-engineering", 23, "j0ZZfIz9R1I"),
            ("real-engineering", 24, "Vf_pS0XSTyo"),
        ])

    def test_cli_report_is_reproducible_and_bounded(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["audience-benchmarks", "study-plan", "--root", str(AUDIENCE),
                                   "--identity-candidates", str(CANDIDATES),
                                   "--pairs-per-channel", "1"]), 0)
        report = json.loads(output.getvalue())
        self.assertLessEqual(report["selectedPairCount"], 6)
        self.assertEqual(report["selection"]["pairsPerChannel"], 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["audience-benchmarks", "study-plan", "--root", str(AUDIENCE),
                                   "--max-runtime-ratio", "NaN"]), 2)
        with tempfile.TemporaryDirectory() as directory:
            args = ["audience-benchmarks", "study-plan", "--root", str(AUDIENCE),
                    "--out", directory]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
                self.assertEqual(main(args), 0)  # same-content idempotence
            artifact = json.loads((Path(directory) / "visual-study-plan.json").read_text())
            self.assertEqual(artifact["selectedPairCount"], 17)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([*args, "--pairs-per-channel", "1"]), 2)
