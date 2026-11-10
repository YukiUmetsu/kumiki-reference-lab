"""Regression gates for provenance-aware, non-causal audience comparisons."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.audience_benchmarks import (
    build_audience_insights, load_audience_benchmarks, validate_audience_benchmarks,
)
from kumiki_reference_lab.cli.app import main


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "research/audience-recent-uploads.v1.json"


class AudienceBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_audience_benchmarks(COLLECTION)

    def test_observations_have_comparable_source_boundaries(self):
        channels = self.catalog["channels"]
        self.assertEqual(len(channels), 6)
        self.assertTrue(all(len(channel["videos"]) == 50 for channel in channels))
        self.assertEqual(sum(len(channel["videos"]) for channel in channels), 300)
        self.assertEqual(len({channel["id"] for channel in channels}), 6)
        self.assertTrue(all(channel["sourceUrl"].startswith("https://digitalcreators.jp/en/channel/en/")
                            for channel in channels))
        self.assertTrue(any(video["durationSeconds"] is None for channel in channels
                            for video in channel["videos"]))

    def test_medians_age_matched_comparisons_and_caveats(self):
        report = build_audience_insights(self.catalog)
        self.assertEqual(report["sampleCount"], 300)
        self.assertEqual(report["channelCount"], 6)
        self.assertIn("no-causal", report["interpretationStatus"])
        self.assertGreaterEqual(len(report["caveats"]), 5)
        summaries = {channel["id"]: channel for channel in report["channelSummaries"]}
        self.assertEqual(summaries["alan-becker"]["overall"]["medianViews"], 11_041_486)
        self.assertEqual(summaries["kurzgesagt"]["overall"]["medianLikesPer1000Views"], 41.972)
        self.assertEqual(len(summaries["alan-becker"]["ageMatchedDurationContrasts"]), 2)
        self.assertEqual(summaries["alan-becker"]["ageMatchedDurationContrasts"][0]["medianViewRatioShortToLong"], 1.413)
        self.assertEqual(summaries["league-of-legends"]["ageMatchedDurationContrasts"], [])
        self.assertTrue(all(contrast["shorterThan3Minutes"]["count"] >= 5 and
                            contrast["atLeast3Minutes"]["count"] >= 5
                            for channel in report["channelSummaries"]
                            for contrast in channel["ageMatchedDurationContrasts"]))
        restrictive = build_audience_insights(self.catalog, minimum_comparison_count=50)
        self.assertTrue(all(not channel["ageMatchedDurationContrasts"]
                            for channel in restrictive["channelSummaries"]))
        with self.assertRaisesRegex(ValueError, "between 2 and 50"):
            build_audience_insights(self.catalog, minimum_comparison_count=True)

    def test_age_uses_source_snapshot_not_retrieval_date(self):
        newer_retrieval = copy.deepcopy(self.catalog)
        newer_retrieval["retrievedOn"] = "2027-11-10"
        original = build_audience_insights(self.catalog)
        updated = build_audience_insights(newer_retrieval)
        self.assertEqual(original["channelSummaries"], updated["channelSummaries"])

    def test_malformed_and_future_metadata_is_rejected(self):
        mutations = [
            lambda c: c["channels"].append(copy.deepcopy(c["channels"][0])),
            lambda c: c["channels"][0].update(sourceUrl="http://localhost/videos/"),
            lambda c: c["channels"][0].update(sourceLastUpdatedOn="2030-01-01"),
            lambda c: c["channels"][0]["videos"][0].update(publishedOn="2029-01-01"),
            lambda c: c["channels"][0]["videos"].reverse(),
            lambda c: c["channels"][0]["videos"][0].update(views=0),
            lambda c: c["channels"][0]["videos"][0].update(likes=True),
            lambda c: c["channels"][0]["videos"][0].update(durationSeconds=0),
            lambda c: c["channels"][0]["videos"][0].update(videoId="unknown"),
            lambda c: c["channels"][0]["videos"].append(copy.deepcopy(c["channels"][0]["videos"][0])),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                candidate = copy.deepcopy(self.catalog)
                mutate(candidate)
                with self.assertRaises(ValueError):
                    validate_audience_benchmarks(candidate)

    def test_rejects_duplicate_json_keys_oversize_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "bad.json"
            bad.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate audience metadata property"):
                load_audience_benchmarks(bad)
            bad.write_bytes(b" " * 524289)
            with self.assertRaisesRegex(ValueError, "512 KiB"):
                load_audience_benchmarks(bad)
            link = root / "link.json"
            link.symlink_to(COLLECTION)
            with self.assertRaisesRegex(ValueError, "regular file"):
                load_audience_benchmarks(link)

    def test_cli_validate_report_and_failure(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(["audience-benchmarks", "validate", "--root", str(COLLECTION)]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["sampleCount"], 300)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(["audience-benchmarks", "report", "--root", str(COLLECTION)]), 0)
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["channelCount"], 6)
        self.assertIn("caveats", report)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["audience-benchmarks", "report", "--root", str(COLLECTION),
                                   "--min-comparison-count", "-1"]), 2)


if __name__ == "__main__":
    unittest.main()
