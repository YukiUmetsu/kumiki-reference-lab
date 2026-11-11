"""Regression tests for source-hashed movie-promotion evidence index consistency."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_movie_promo_evidence import audit

HASH = "a" * 64


class MoviePromoAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.summary = {
            "id": "sample-trailer", "catalogId": "official-sample",
            "sourceSha256": HASH, "sourceDurationSeconds": 100,
            "windows": [{
                "window": "opening", "windowSourceSha256": HASH,
                "sourceOffsetSeconds": 0, "scanSeconds": 20, "cutCandidateCount": 1,
                "appearanceFrameSamples": 1, "cutCandidateCountAtThreshold015": 2,
            }],
        }
        self.detail = {
            "schemaVersion": "kumiki.movie-promotion-window-evidence.v1",
            "rightsStatus": "review-required",
            "id": "sample-trailer", "catalogId": "official-sample",
            "originalSourceSha256": HASH, "originalDurationSeconds": 100,
            "windows": [{
                "window": "opening", "windowSourceSha256": HASH,
                "sourceOffsetSeconds": 0, "scanWindowSeconds": 20, "shotCutCandidates": [{}],
                "appearanceSamples": [{}], "sensitivityCutCandidateCount": 2,
            }],
        }
        self.write()

    def write(self):
        (self.root / "index.json").write_text(json.dumps({
            "schemaVersion": "kumiki.movie-promotion-measurements.v1",
            "videos": [self.summary],
        }))
        (self.root / "sample-trailer.json").write_text(json.dumps(self.detail))

    def test_consistent(self):
        self.assertEqual(audit(self.root), [])

    def test_detects_source_hash_mismatch(self):
        self.detail["originalSourceSha256"] = "b" * 64
        self.write()
        self.assertTrue(any("sourceSha256 mismatch" in x for x in audit(self.root)))

    def test_detects_incorrect_cut_count(self):
        self.summary["windows"][0]["cutCandidateCount"] = 3
        self.write()
        self.assertTrue(any("cut candidate count mismatch" in x for x in audit(self.root)))

    def test_detects_window_outside_source(self):
        self.summary["windows"][0]["sourceOffsetSeconds"] = 90
        self.detail["windows"][0]["sourceOffsetSeconds"] = 90
        self.write()
        self.assertTrue(any("window exceeds source duration" in x for x in audit(self.root)))

    def test_detects_invalid_scan_duration(self):
        self.summary["windows"][0]["scanSeconds"] = -1
        self.write()
        self.assertTrue(any("invalid window bounds" in x for x in audit(self.root)))

    def test_detects_nonfinite_source_duration(self):
        self.summary["sourceDurationSeconds"] = float("nan")
        self.detail["originalDurationSeconds"] = float("nan")
        self.write()
        self.assertTrue(any("invalid source duration" in x for x in audit(self.root)))

    def test_detects_scan_duration_mismatch(self):
        self.detail["windows"][0]["scanWindowSeconds"] = 19
        self.write()
        self.assertTrue(any("scan duration mismatch" in x for x in audit(self.root)))

    def test_detects_unindexed_file(self):
        (self.root / "orphan.json").write_text("{}")
        self.assertTrue(any("unindexed" in x for x in audit(self.root)))


if __name__ == "__main__":
    unittest.main()
