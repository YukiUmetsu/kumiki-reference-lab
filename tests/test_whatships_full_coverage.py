"""Exhaustive What Ships index refresh, category-balanced coverage and evidence gaps."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.catalog.whatships_full_coverage import (
    INDEX_URL, _parse_json_bytes, build_full_coverage, fetch_public_whatships_index,
    plan_full_snapshot, reconcile_index, refresh_full_whatships_catalog,
    summarize_full_snapshot, validate_raw_whatships_index,
)
from kumiki_reference_lab.catalog.video_sources import _load_snapshot
from kumiki_reference_lab.cli.app import main
from tests.test_video_sources import whatships_fixture

ROOT = Path(__file__).resolve().parents[1]
BUNDLED_SNAPSHOT = ROOT / "research/whatships-index-2026-11-10.json"


def official_index():
    return [
        {"id":"plv-film-one","kind":"video","name":"Paper animation demo",
         "slug":"film-one","href":"/videos/film-one/","meta":"Studio A · Motion",
         "poster":"/posters/film-one-960.webp","searchText":"paper animation motion"},
        {"id":"plv-new-design","kind":"video","name":"New product with movement",
         "slug":"new-design","href":"/videos/new-design/","meta":"Studio B · Design",
         "poster":"/posters/new-design-960.webp","searchText":"new product design"},
        {"id":"plv-film-two","kind":"video","name":"Unverified trailer",
         "slug":"film-two","href":"/videos/film-two/","meta":"Studio B · Design",
         "poster":"/posters/film-two-960.webp","searchText":"unverified trailer"},
        {"id":"tool-example","kind":"tool","name":"Motion Maker","slug":"motion-maker",
         "href":"/tools/#tool-example","meta":"editor","poster":None,"searchText":"tool"},
        {"id":"studio-example","kind":"studio","name":"Render Studio","slug":"render-studio",
         "href":"/studios/#studio-example","meta":"studio","poster":None,"searchText":"studio"},
    ]


class WhatshipsFullCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.previous = self.root / "previous.json"
        self.index_file = self.root / "official-index.json"
        self.out = self.root / "refresh"
        self.previous.write_text(json.dumps(whatships_fixture()), encoding="utf-8")
        self.index_file.write_text(json.dumps(official_index()), encoding="utf-8")

    def test_full_raw_catalog_refresh_keeps_known_detail_and_adds_every_video(self):
        path = refresh_full_whatships_catalog(
            self.previous, self.out, index_file=self.index_file,
            retrieved_on="2026-11-10",
        )
        self.assertEqual(path, self.out / "coverage.json")
        snapshot = _load_snapshot(self.out / "whatships-all-videos.json")
        self.assertEqual(len(snapshot["videos"]), 3)
        self.assertEqual(snapshot["totals"]["indexed"], 3)
        self.assertEqual(snapshot["totals"]["enriched"], 1)
        self.assertEqual(snapshot["totals"]["withoutDetails"], 2)
        rows = {row["slug"]: row for row in snapshot["videos"]}
        self.assertEqual(rows["film-one"]["detail"]["views"], 189170)
        self.assertIsNone(rows["new-design"]["detail"])
        self.assertEqual(rows["new-design"]["directoryUrl"],
                         "https://whatships.com/videos/new-design/")
        diff = json.loads((self.out / "index-changes.json").read_text())
        self.assertEqual(diff["addedSlugs"], ["new-design"])
        self.assertEqual(diff["removedSlugs"], [])
        self.assertEqual(diff["retained"], 2)
        coverage = json.loads(path.read_text())
        self.assertEqual(coverage["totalVideoEntries"], 3)
        self.assertEqual(coverage["indexedMetadataCoveragePercent"], 100.0)
        self.assertEqual(coverage["detailedMetadataEntries"], 1)
        self.assertEqual(coverage["authorizedLocalMediaBindingsInThisDataset"], 0)
        self.assertEqual(coverage["frameAnalysisEvidenceInThisDataset"], 0)
        backlog = json.loads((self.out / "all-video-backlog.json").read_text())
        self.assertEqual(backlog["totalTasks"], 3)
        self.assertEqual(len(backlog["entries"]), 3)
        self.assertEqual({x["category"] for x in backlog["entries"]},
                         {"design", "motion"})
        self.assertTrue(all(x["localAuthorizedMediaStatus"] == "not-linked"
                            for x in backlog["entries"]))
        self.assertEqual(len({x["slug"] for x in backlog["entries"]}), 3)
        with self.assertRaisesRegex(ValueError, "new directory"):
            refresh_full_whatships_catalog(
                self.previous, self.out, index_file=self.index_file)

    def test_round_robin_does_not_starve_small_categories(self):
        previous = whatships_fixture()
        raw = official_index()
        for i in range(10):
            slug = f"ai-extra-{i}"
            raw.append({
                "id": "plv-"+slug,"kind":"video","name":"AI Product",
                "slug":slug,"href":f"/videos/{slug}/",
                "meta":"Studio X · AI","poster":f"/posters/{slug}-960.webp",
                "searchText":"AI model launch",
            })
        snap, diff = reconcile_index(raw, previous, retrieved_on="2026-11-10")
        coverage, queue = build_full_coverage(snap)
        cats = [row["category"] for row in queue["entries"][:5]]
        self.assertEqual(cats[:3], ["ai", "design", "motion"])
        self.assertEqual(queue["totalTasks"], 13)
        self.assertEqual(coverage["byCategory"]["ai"]["indexed"], 10)
        self.assertEqual(coverage["byCategory"]["motion"]["hasDetailMetadata"], 1)

    def test_removed_video_is_audited_not_silently_hidden(self):
        raw = official_index()
        raw = [x for x in raw if x["slug"] != "film-two"]
        snap, diff = reconcile_index(raw, whatships_fixture(),
                                    retrieved_on="2026-11-10", min_retained_fraction=.5)
        self.assertEqual(diff["removedSlugs"], ["film-two"])
        self.assertEqual({x["slug"] for x in snap["videos"]},
                         {"film-one", "new-design"})
        with self.assertRaisesRegex(ValueError, "dropped too many"):
            reconcile_index(raw[:1], whatships_fixture(), retrieved_on="2026-11-10",
                            min_retained_fraction=.90)

    def test_updated_category_discards_obsolete_detail(self):
        raw = official_index()
        raw[0]["meta"] = "Studio A · AI"
        snap, diff = reconcile_index(raw, whatships_fixture(), retrieved_on="2026-11-10")
        self.assertEqual(diff["discardedStaleDetailCount"], 1)
        self.assertIsNone(snap["videos"][0]["detail"])
        self.assertEqual(snap["totals"]["enriched"], 0)

    def test_no_relevant_media_or_website_fetched_from_offline_index(self):
        with patch("kumiki_reference_lab.catalog.whatships_full_coverage.fetch_public_whatships_index",
                   side_effect=AssertionError("should not contact network")):
            refresh_full_whatships_catalog(
                self.previous, self.out, index_file=self.index_file,
                retrieved_on="2026-11-10",
            )

    def test_rejects_invalid_urls_duplicate_slugs_and_bad_metadata(self):
        changes = [
            lambda x: x[1].update(slug="../../escape"),
            lambda x: x[1].update(href="https://other.test/hijack"),
            lambda x: x[1].update(href="/videos/film-one/"),
            lambda x: x[1].update(id="plv-film-one"),
            lambda x: x[1].update(meta="Studio B · Unknown"),
            lambda x: x[1].update(poster="https://bad.test/poster.webp"),
            lambda x: x[1].update(kind="person"),
            lambda x: x[1].update(searchText="x"*5000),
            lambda x: x.append(copy.deepcopy(x[0])),
        ]
        for change in changes:
            raw = copy.deepcopy(official_index())
            change(raw)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_raw_whatships_index(raw)
        with self.assertRaises(ValueError):
            _parse_json_bytes(b'[{"slug":"one","slug":"two"}]')
        with self.assertRaises(ValueError):
            _parse_json_bytes(b'{"value":NaN}')

    def test_plan_can_list_entire_backlog_or_only_missing_detail(self):
        filtered = plan_full_snapshot(self.previous, missing_detail_only=True)
        self.assertEqual(filtered["totalEligible"], 1)
        self.assertEqual(filtered["entries"][0]["slug"], "film-two")
        self.assertEqual(filtered["entries"][0]["nextMetadataTask"],
                         "fetch-read-only-detail")
        all_rows = plan_full_snapshot(self.previous, limit=None)
        self.assertEqual(all_rows["totalEligible"], 2)
        self.assertEqual(len(all_rows["entries"]), 2)
        design = plan_full_snapshot(self.previous, category="design", limit=10)
        self.assertEqual(design["displayedCount"], 1)
        with self.assertRaises(ValueError):
            plan_full_snapshot(self.previous, category="unknown")
        with self.assertRaises(ValueError):
            plan_full_snapshot(self.previous, limit=10001)

    def test_cli_report_queue_and_offline_refresh(self):
        for cmd, field, expected in (
            (["report", "--snapshot", str(self.previous)], "totalVideoEntries", 2),
            (["queue", "--snapshot", str(self.previous), "--limit", "1"],
             "displayedCount", 1),
        ):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(["whatships-all", *cmd])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())[field], expected)
        with contextlib.redirect_stdout(io.StringIO()):
            result = main([
                "whatships-all", "refresh", "--previous", str(self.previous),
                "--index-file", str(self.index_file), "--out", str(self.out),
                "--retrieved-on", "2026-11-10",
            ])
        self.assertEqual(result, 0)
        self.assertTrue((self.out / "coverage.json").exists())

    def test_bundled_index_already_has_all_2861_directory_entries(self):
        # Regression proves *index enumeration*, not 2861 actual visual reviews.
        data = summarize_full_snapshot(BUNDLED_SNAPSHOT)
        self.assertEqual(data["totalVideoEntries"], 2861)
        self.assertEqual(data["detailedMetadataEntries"], 419)
        self.assertEqual(data["detailMissingEntries"], 2442)
        self.assertEqual(data["indexedMetadataCoveragePercent"], 100.0)
        self.assertEqual(len(data["byCategory"]), 8)
        self.assertEqual(data["byCategory"]["motion"]["indexed"], 69)
        self.assertEqual(data["byCategory"]["ai"]["indexed"], 1122)
        self.assertEqual(data["frameAnalysisEvidenceInThisDataset"], 0)


if __name__ == "__main__":
    unittest.main()
