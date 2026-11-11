"""Regression checks for movie-promotion image-plane motion proxy summaries."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.derive_movie_promo_motion_proxies import build_motion_report, build_from_folder


class MovieMotionProxyTests(unittest.TestCase):
    def setUp(self):
        self.clip = "a" * 64
        self.source = "b" * 64
        self.index = {"schemaVersion": "kumiki.movie-promotion-measurements.v1", "videos": [{
            "id": "sample", "catalogId": "sample-catalog",
            "sourceSha256": self.source, "windows": [{
                "window": "opening", "sourceOffsetSeconds": 0,
                "scanSeconds": 20, "windowSourceSha256": self.clip,
            }],
        }]}
        self.detail = {
            "id": "sample", "catalogId": "sample-catalog",
            "originalSourceSha256": self.source,
            "rightsStatus": "review-required", "windows": [{
                "window": "opening", "sourceOffsetSeconds": 0,
                "scanWindowSeconds": 20, "windowSourceSha256": self.clip,
                "sourceVideoTimebase": {"numerator": 1, "denominator": 1000},
                "imageMotion": {"sourceSha256": self.clip, "pairs": [
                    {"status": "measured-image-translation", "startPts": 0, "endPts": 1000,
                     "deltaTimeSeconds": {"numerator": 1, "denominator": 1},
                     "dxNormalized": 0.03, "dyNormalized": 0.04},
                    {"status": "cut-boundary", "startPts": 1000, "endPts": 2000,
                     "deltaTimeSeconds": {"numerator": 1, "denominator": 1},
                     "dxNormalized": None, "dyNormalized": None},
                ]},
                "sparseFlow": {"sourceSha256": self.clip,
                               "pairs": [{"status": "insufficient-consensus"}]},
            }],
        }

    def build(self):
        return build_motion_report(self.index, {"sample": (self.detail, "c" * 40)}, "d" * 40)

    def test_counts_and_normalized_speed(self):
        report = self.build()
        w = report["videos"][0]["windows"][0]
        self.assertEqual(w["imageMotionPairCount"], 2)
        self.assertEqual(w["measuredImageTranslationPairs"], 1)
        self.assertEqual(w["measuredPairsAboveExploratoryMagnitudeThreshold"], 1)
        self.assertEqual(w["medianFrameNormalizedShiftPerSecondOfMeasuredPairs"], 0.05)
        self.assertEqual(w["sparseFlowPairStatuses"], {"insufficient-consensus": 1})
        self.assertEqual(report["coverage"]["imageMotionPairStatuses"],
                         {"cut-boundary": 1, "measured-image-translation": 1})
        self.assertFalse(w["calibratedPhysicalCameraConfidence"])

    def test_no_measured_pairs_is_null_not_zero_motion(self):
        self.detail["windows"][0]["imageMotion"]["pairs"] = [
            self.detail["windows"][0]["imageMotion"]["pairs"][1]]
        w = self.build()["videos"][0]["windows"][0]
        self.assertIsNone(w["medianFrameNormalizedShiftPerSecondOfMeasuredPairs"])
        self.assertEqual(w["measuredImageTranslationPairs"], 0)

    def test_reject_wrong_media_fingerprint(self):
        self.detail["windows"][0]["imageMotion"]["sourceSha256"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.build()

    def test_reject_corrupt_pts_delta(self):
        self.detail["windows"][0]["imageMotion"]["pairs"][0]["endPts"] = 500
        with self.assertRaisesRegex(ValueError, "PTS/timebase mismatch"):
            self.build()

    def test_reject_nonfinite_motion(self):
        self.detail["windows"][0]["imageMotion"]["pairs"][0]["dxNormalized"] = float("nan")
        with self.assertRaisesRegex(ValueError, "invalid measured displacement"):
            self.build()

    def test_committed_output_reproduces_all_measured_films(self):
        root = Path(__file__).resolve().parents[1] / "research/analysis/movie-promotions"
        output = root / "derived/image-motion-proxies.v1.json"
        if not output.is_file():
            self.skipTest("complete repository checkout required")
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), build_from_folder(root))


if __name__ == "__main__":
    unittest.main()
