"""Read committed What Ships video observations without any private run files."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.whatships_analysis_store import (
    export_repository_analysis,
)
from kumiki_reference_lab.catalog.whatships_data_dashboard import (
    build_whatships_browser, write_whatships_browser,
)
from kumiki_reference_lab.catalog.whatships_research_summary import (
    summarize_tracked_whatships_observations,
)
from kumiki_reference_lab.cli.app import main
from tests.test_video_sources import whatships_fixture

ROOT = Path(__file__).resolve().parents[1]


class WhatshipsRepositoryExplorerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.catalog = self.work / "catalog.json"
        self.catalog.write_text(json.dumps(whatships_fixture()))
        self.observations = self.work / "notes.json"
        self.observations.write_text(json.dumps({
            "schemaVersion": "kumiki.browser-video-observations.v1",
            "reviewedOn": "2026-11-10",
            "methodology": "selected moments from browser only",
            "observations": [{
                "sourceId": "whatships:film-one",
                "reviewedOn": "2026-11-10",
                "method": "browser-player",
                "coverage": "selected-moments-only",
                "visualTags": ["paper-cut", "kinetic-typography"],
                "visibleMoments": ["A layered letter animation is visible."],
                "techniqueHypotheses": ["Consider layered planar transforms."],
            }],
        }))
        self.repository = self.work / "analysis"
        export_repository_analysis(
            self.catalog, self.repository, observations_path=self.observations)

    def test_verified_repository_overlay_populates_exact_video_only(self):
        browser = build_whatships_browser(
            self.catalog, repository_root=self.repository)
        self.assertEqual(browser["totalVideos"], 2)
        self.assertEqual(browser["counts"]["repositoryEvidenceRecords"], 1)
        self.assertEqual(browser["counts"]["browserSpotCheckRecords"], 1)
        rows = {x["sourceId"]: x for x in browser["entries"]}
        first = rows["whatships:film-one"]
        self.assertEqual(first["spotCheckCoverage"], "selected-moments-only")
        self.assertEqual(first["visualObservationTags"],
                         ["paper-cut", "kinetic-typography"])
        self.assertEqual(first["visibleMoments"],
                         ["A layered letter animation is visible."])
        self.assertEqual(first["repositoryAnalysisStatus"],
                         "tracked-partial-evidence")
        self.assertEqual(first["numericStatus"], "not-run")
        self.assertFalse(first["humanReviewed"])
        second = rows["whatships:film-two"]
        self.assertEqual(second["repositoryAnalysisStatus"], "none")
        self.assertEqual(second["visibleMoments"], [])
        self.assertEqual(second["visualObservationTags"], [])
        self.assertEqual(second["numericStatus"], "not-run")

    def test_browse_writes_actual_observations_to_offline_html(self):
        folder = self.work/"browser"
        path = write_whatships_browser(self.catalog, folder,
                                       repository_root=self.repository)
        self.assertTrue(path.exists())
        html = path.read_text()
        self.assertIn("A layered letter animation is visible.", html)
        self.assertIn("Saved partial visual spotcheck", html)
        self.assertIn("Unverified technique hypotheses", html)
        self.assertIn('connect-src \\'none\\'', html)
        self.assertNotIn(str(self.work), html)
        rows = json.loads((folder/"whatships-videos.json").read_text())
        self.assertEqual(len(rows["entries"]), 2)
        self.assertFalse(rows["entries"][0]["humanReviewed"])

    def test_research_report_counts_only_observed_not_all_videos(self):
        report = summarize_tracked_whatships_observations(
            self.catalog,self.repository)
        self.assertEqual(report["catalogVideoCount"],2)
        self.assertEqual(report["trackedEvidenceRecordCount"],1)
        self.assertEqual(report["partiallyObservedVideoCount"],1)
        self.assertEqual(report["sourcePtsNumericVideoCount"],0)
        self.assertEqual(report["fullyHumanReviewedVideoCount"],0)
        self.assertEqual(report["observedVisualTags"],
                         {"kinetic-typography":1,"paper-cut":1})
        self.assertEqual(report["trackedRecordsByCategory"],{"motion":1})
        self.assertIn("not population estimates",report["methodLimits"][2])

    def test_invalid_repository_snapshot_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"snapshot"):
            build_whatships_browser(
                ROOT/"research/whatships-index-2026-11-10.json",
                repository_root=self.repository)
        path = self.repository/"film-one.json"
        row = json.loads(path.read_text())
        row["evidence"]["browserSpotCheck"]["sourcePts"] = 100
        path.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError,"original PTS"):
            build_whatships_browser(self.catalog,
                                    repository_root=self.repository)

    def test_cli_research_report_over_committed_nine_video_cohort(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            result=main([
                "whatships-all","research-report",
                "--snapshot",str(ROOT/"research/whatships-index-2026-11-10.json"),
                "--root",str(ROOT/"research/analysis/whatships"),
            ])
        self.assertEqual(result,0)
        data=json.loads(output.getvalue())
        self.assertEqual(data["catalogVideoCount"],2861)
        self.assertEqual(data["trackedEvidenceRecordCount"],9)
        self.assertEqual(data["partiallyObservedVideoCount"],9)
        self.assertEqual(data["sourcePtsNumericVideoCount"],0)
        self.assertEqual(data["fullyHumanReviewedVideoCount"],0)

    def test_cli_browse_can_disable_committed_overlay(self):
        out=self.work/"cli-browser"
        buf=io.StringIO()
        with contextlib.redirect_stdout(buf):
            result=main([
                "whatships-all","browse",
                "--snapshot",str(self.catalog),
                "--out",str(out),
                "--repository-analysis",str(self.repository),
            ])
        self.assertEqual(result,0)
        self.assertEqual(Path(buf.getvalue().strip()),out/"whatships-videos.html")
        self.assertEqual(json.loads((out/"whatships-videos.json").read_text())
                         ["counts"]["repositoryEvidenceRecords"],1)
        empty=build_whatships_browser(self.catalog)
        self.assertNotIn("repositoryEvidenceRecords",empty["counts"])


if __name__=="__main__":
    unittest.main()
