"""What Ships research corpus: source-linked, privacy-safe, versioned observations."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.whatships_analysis_store import (
    build_repository_analysis, export_repository_analysis,
    validate_repository_analysis,
)
from kumiki_reference_lab.catalog.whatships_data_dashboard import (
    _csv, _html, build_whatships_browser, write_whatships_browser,
)
from kumiki_reference_lab.cli.app import main
from tests.test_video_sources import whatships_fixture


ROOT = Path(__file__).resolve().parents[1]


class WhatshipsRepositoryAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = self.root/"catalog.json"
        self.snapshot.write_text(
            json.dumps(whatships_fixture()), encoding="utf-8")
        self.spotchecks = self.root/"browser-notes.json"
        self.spotchecks.write_text(json.dumps({
            "schemaVersion":"kumiki.browser-video-observations.v1",
            "reviewedOn":"2026-11-10",
            "methodology":"selected public-player moments, without source PTS",
            "observations":[{
                "sourceId":"whatships:film-one",
                "reviewedOn":"2026-11-10",
                "method":"browser-player",
                "coverage":"selected-moments-only",
                "visualTags":["paper-cut","kinetic-typography"],
                "visibleMoments":["A paper-like letter card shifts against a dark background."],
                "techniqueHypotheses":["Model layered plane transforms in Kumiki."],
            }],
        }))
        self.out = self.root/"git-ready"
        self.web = self.root/"browser"

    def test_exports_per_video_json_only_for_actual_spotchecks_not_all_catalog(self):
        index_path = export_repository_analysis(
            self.snapshot,self.out,observations_path=self.spotchecks)
        index = json.loads(index_path.read_text())
        self.assertEqual(index["catalogVideoCount"],2)
        self.assertEqual(index["sourceLinkedAnalysisCount"],1)
        self.assertEqual(index["browserSpotCheckCount"],1)
        self.assertEqual(index["sampledNumericVideoCount"],0)
        self.assertEqual(index["fullFilmReviewedCount"],0)
        self.assertEqual(index["entries"][0]["recordPath"],"film-one.json")
        result = json.loads((self.out/"film-one.json").read_text())
        self.assertEqual(result["sourceId"],"whatships:film-one")
        self.assertIsNone(result["sourceMediaSha256"])
        self.assertFalse(result["coverage"]["fullFilmReviewed"])
        self.assertFalse(result["coverage"]["hasSampledNumericSourceFrames"])
        self.assertIsNone(result["evidence"]["browserSpotCheck"]["sourcePts"])
        self.assertFalse((self.out/"film-two.json").exists())
        validated = validate_repository_analysis(self.out,self.snapshot)
        self.assertEqual(validated["sourceLinkedAnalysisRecords"],1)
        self.assertEqual(validated["numericSampledVideos"],0)
        self.assertNotIn(str(self.root),index_path.read_text())
        self.assertNotIn(str(self.root),(self.out/"film-one.json").read_text())
        with self.assertRaisesRegex(ValueError,"new directory"):
            export_repository_analysis(self.snapshot,self.out)

    def test_no_footage_or_notes_yields_empty_source_linked_analysis_index(self):
        index_path = export_repository_analysis(self.snapshot,self.out)
        self.assertEqual(json.loads(index_path.read_text())["sourceLinkedAnalysisCount"],0)
        self.assertEqual(set(p.name for p in self.out.iterdir()),{"index.json"})

    def test_rejects_unknown_observation_not_in_full_catalog(self):
        data = json.loads(self.spotchecks.read_text())
        data["observations"][0]["sourceId"] = "whatships:not-a-video"
        self.spotchecks.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,"reference one catalog"):
            export_repository_analysis(self.snapshot,self.out,observations_path=self.spotchecks)
        self.assertFalse(self.out.exists())

    def test_rejects_tampered_index_or_source_snapshot_sha(self):
        export_repository_analysis(self.snapshot,self.out,observations_path=self.spotchecks)
        index_file = self.out/"index.json"
        original = json.loads(index_file.read_text())
        for mutation in (
            lambda x:x.update(catalogSnapshotSha256="b"*64),
            lambda x:x.update(browserSpotCheckCount=900),
            lambda x:x["entries"][0].update(recordPath="../../private.json"),
            lambda x:x["entries"][0].update(sourceId="whatships:wrong"),
        ):
            data = json.loads(json.dumps(original))
            mutation(data)
            index_file.write_text(json.dumps(data))
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                validate_repository_analysis(self.out,self.snapshot)
        index_file.write_text(json.dumps(original))
        self.snapshot.write_text(self.snapshot.read_text()+" ")
        with self.assertRaisesRegex(ValueError,"snapshot"):
            validate_repository_analysis(self.out,self.snapshot)

    def test_committed_nine_spotcheck_records_match_original_catalog_sha(self):
        path = ROOT/"research/analysis/whatships"
        result = validate_repository_analysis(
            path,ROOT/"research/whatships-index-2026-11-10.json")
        self.assertEqual(result["indexedCatalogVideos"],2861)
        self.assertEqual(result["sourceLinkedAnalysisRecords"],9)
        self.assertEqual(result["browserSpotChecks"],9)
        self.assertEqual(result["numericSampledVideos"],0)
        self.assertEqual(result["humanReviewedFullVideos"],0)

    def test_browser_full_catalog_but_no_false_visual_data(self):
        data = build_whatships_browser(self.snapshot)
        self.assertEqual(data["totalVideos"],2)
        self.assertEqual(data["counts"]["metadataStatus:detail-snapshot"],1)
        self.assertEqual(data["counts"]["characterStatus:not-run"],2)
        self.assertEqual(data["counts"]["numericStatus:not-run"],2)
        self.assertEqual(sum(bool(row["numeric"]) for row in data["entries"]),0)
        report = write_whatships_browser(self.snapshot,self.web)
        self.assertTrue(report.is_file())
        self.assertTrue((self.web/"whatships-videos.csv").exists())
        self.assertTrue((self.web/"whatships-videos.json").exists())
        html = report.read_text()
        self.assertIn("Content-Security-Policy",html)
        self.assertIn("connect-src 'none'",html)
        self.assertNotIn("https://fonts.",html)
        self.assertNotIn(str(self.root),html)
        with self.assertRaisesRegex(ValueError,"new nonexisting"):
            write_whatships_browser(self.snapshot,self.web)

    def test_browser_escapes_html_script_and_csv_formula_names(self):
        data = whatships_fixture()
        data["videos"][0]["title"] = "</script><script>alert(1)</script>"
        data["videos"][0]["detail"]["title"] = "</script><script>alert(1)</script>"
        data["videos"][1]["title"] = "=HYPERLINK('https://bad.example','click')"
        self.snapshot.write_text(json.dumps(data))
        dataset = build_whatships_browser(self.snapshot)
        html = _html(dataset)
        self.assertNotIn("</script><script>alert(1)",html)
        self.assertIn("\\u003c/script\\u003e",html)
        csv_body = _csv(dataset)
        self.assertIn("'=HYPERLINK(",csv_body)
        self.assertIn("whatships:film-one",csv_body)

    def test_cli_exports_and_validates_git_ready_files(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            code=main([
                "whatships-all","export-analysis","--snapshot",str(self.snapshot),
                "--observations",str(self.spotchecks),"--out",str(self.out),
            ])
        self.assertEqual(code,0)
        self.assertEqual(Path(output.getvalue().strip()),self.out/"index.json")
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            code=main([
                "whatships-all","validate-analysis","--snapshot",str(self.snapshot),
                "--root",str(self.out),
            ])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(output.getvalue())["browserSpotChecks"],1)


if __name__ == "__main__":
    unittest.main()
