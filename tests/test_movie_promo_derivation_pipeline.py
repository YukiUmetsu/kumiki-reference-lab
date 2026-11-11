"""Regression tests for coordinated, source-index-bound movie derivatives."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.rebuild_movie_promo_derived import (
    OUTPUT_NAMES, build_reports, verify_reports, write_reports,
)


ROOT = Path(__file__).resolve().parents[1] / "research/analysis/movie-promotions"


class MoviePromoDerivedPipelineTests(unittest.TestCase):
    def test_all_tracked_reports_reproduce_source_evidence(self):
        reports = build_reports(ROOT)
        self.assertEqual(set(reports), set(OUTPUT_NAMES))
        self.assertEqual(len({x["sourceIndexGitBlobSha"] for x in reports.values()}), 1)
        self.assertEqual(reports["comparison.v1.json"]["coverage"]["sourceCount"],
                         reports["timed-events.v1.json"]["coverage"]["sourceCount"])
        self.assertEqual(reports["timed-events.v1.json"]["coverage"]["sourceCount"],
                         reports["image-motion-proxies.v1.json"]["coverage"]["sourceCount"])
        verify_reports(ROOT, reports)

    def test_stale_report_is_rejected_without_regenerating_data(self):
        reports = build_reports(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_reports(root, reports)
            path = root / "derived" / "timed-events.v1.json"
            stale = json.loads(path.read_text(encoding="utf-8"))
            stale["coverage"]["sourceCount"] = -1
            path.write_text(json.dumps(stale), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "timed-events.v1.json: derived report"):
                verify_reports(root, reports)

    def test_unexpected_extra_json_is_not_silently_accepted(self):
        reports = build_reports(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_reports(root, reports)
            (root / "derived" / "unindexed.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected="):
                verify_reports(root, reports)

    def test_rebuild_creates_only_three_json_reports_and_preserves_other_files(self):
        reports = build_reports(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "keep.txt").write_text("unrelated", encoding="utf-8")
            write_reports(root, reports)
            self.assertEqual(
                {p.name for p in (root / "derived").iterdir()}, set(OUTPUT_NAMES))
            self.assertEqual((root / "keep.txt").read_text(), "unrelated")
            verify_reports(root, reports)
            self.assertFalse(list(root.glob(".movie-promo-derivatives-*")))

    def test_upstream_corruption_fails_before_writing_any_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.json").write_text(json.dumps({
                "schemaVersion": "kumiki.movie-promotion-measurements.v1",
                "videos": [{"id": "missing-detail", "sourceSha256": "a" * 64}],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing detail file"):
                build_reports(root)
            self.assertFalse((root / "derived").exists())


if __name__ == "__main__":
    unittest.main()
