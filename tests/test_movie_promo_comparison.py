"""Unit tests for derived comparisons: only observed, non-overlapping windows."""
import unittest
import hashlib
import json
from pathlib import Path

from scripts.summarize_movie_promo_evidence import build_comparison


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.window = dict(window="opening", sourceOffsetSeconds=0, scanSeconds=20,
                           appearanceFrameSamples=10, cutCandidateCount=4,
                           cutCandidateCountAtThreshold015=7,
                           audioLevelAttackCandidateCount=2,
                           meanSampledLumaProxy=0.4, meanSampledSaturation=0.6)
        self.video = dict(id="sample-film", catalogId="sample-catalog",
                          sourceSha256="b" * 64, sourceDurationSeconds=80,
                          windows=[self.window])
        self.index = {"schemaVersion": "kumiki.movie-promotion-measurements.v1",
                      "videos": [self.video]}

    def build(self):
        return build_comparison(self.index, "a" * 40)

    def test_committed_comparison_matches_index(self):
        root = Path(__file__).resolve().parents[1]
        source = root / "research/analysis/movie-promotions/index.json"
        output = root / "research/analysis/movie-promotions/derived/comparison.v1.json"
        if not source.exists() or not output.exists():
            self.skipTest("run against complete repository tree")
        data = source.read_bytes()
        sha = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        expected = build_comparison(json.loads(data), sha)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), expected)

    def test_normalized_sample_rates_and_provenance(self):
        row = self.build()["videos"][0]
        self.assertEqual(row["cutCandidatesPerSampledMinute025"], 12)
        self.assertEqual(row["sampledSeconds"], 20)
        self.assertEqual(row["sampledSourceFraction"], 0.25)
        self.assertEqual(row["sensitivityExtraCandidates"], 3)
        self.assertEqual(row["meanSampledLumaProxy"], 0.4)
        self.assertEqual(self.build()["coverage"]["sampledSeconds"], 20)
        self.assertEqual(row["sourceFamily"], "disney-public-player")

    def test_rejects_overlapping_windows(self):
        self.video["windows"] = [self.window, dict(self.window, window="middle", sourceOffsetSeconds=10)]
        with self.assertRaisesRegex(ValueError, "overlapping"):
            self.build()

    def test_rejects_missing_data_or_unsupported_numbers(self):
        self.window["cutCandidateCountAtThreshold015"] = 2
        with self.assertRaisesRegex(ValueError, "sensitivity"):
            self.build()
        self.window["cutCandidateCountAtThreshold015"] = 7
        self.window["meanSampledLumaProxy"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            self.build()

    def test_reports_source_edition_and_does_not_imply_upload_match(self):
        self.video["sourceEdition"] = "Apple iTunes Store preview"
        self.video["catalogUploadIdentityMatch"] = "not-verified"
        row = self.build()["videos"][0]
        self.assertEqual(row["sourceFamily"], "apple-itunes-preview")
        self.assertEqual(row["catalogUploadIdentityMatch"], "not-verified")


if __name__ == "__main__":
    unittest.main()
