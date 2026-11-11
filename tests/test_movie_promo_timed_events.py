"""Source-PTS-backed movie edit/audio timeline regression tests."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.derive_movie_promo_timed_events import derive_from_folder, derive_timed_events


def first_difference(expected, actual, path="root"):
    """Return the first useful field-level mismatch for stale-derived-data failures."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected or key not in actual:
                return f"{path}.{key}: missing key"
            diff = first_difference(expected[key], actual[key], f"{path}.{key}")
            if diff:
                return diff
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return f"{path}: lengths {len(expected)} vs {len(actual)}"
        for i, (a, b) in enumerate(zip(expected, actual)):
            diff = first_difference(a, b, f"{path}[{i}]")
            if diff:
                return diff
    elif expected != actual:
        return f"{path}: committed={expected!r}, generated={actual!r}"
    return None


class TimedMovieEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.source_hash = "a" * 64
        self.clip_hash = "b" * 64
        self.index = {
            "schemaVersion": "kumiki.movie-promotion-measurements.v1",
            "videos": [{
                "id": "film", "catalogId": "studio-film", "sourceSha256": self.source_hash,
                "sourceDurationSeconds": 100, "windows": [{
                    "window": "opening", "windowSourceSha256": self.clip_hash,
                    "sourceOffsetSeconds": 0, "scanSeconds": 20,
                    "cutCandidateCount": 2, "audioLevelAttackCandidateCount": 1,
                }],
            }],
        }
        self.detail = {
            "schemaVersion": "kumiki.movie-promotion-window-evidence.v1",
            "id": "film", "catalogId": "studio-film",
            "originalSourceSha256": self.source_hash,
            "originalDurationSeconds": 100, "rightsStatus": "review-required",
            "windows": [{
                "window": "opening", "windowSourceSha256": self.clip_hash,
                "sourceOffsetSeconds": 0, "scanWindowSeconds": 20,
                "sourceVideoTimebase": {"numerator": 1, "denominator": 1000},
                "sourceAudioTimebase": {"numerator": 1, "denominator": 1000},
                "shotCutCandidates": [
                    {"sourcePts": 900, "sourceSeconds": {"numerator": 9, "denominator": 10}},
                    {"sourcePts": 5100, "sourceSeconds": {"numerator": 51, "denominator": 10}},
                ],
                "audioOnsets": {
                    "sourceSha256": self.clip_hash,
                    "candidates": [{"anchorSourcePts": 1000,
                                    "anchorSourceSeconds": {"numerator": 1, "denominator": 1},
                                    "measuredRmsRiseDb": 12.5}],
                },
            }],
        }

    def derive(self):
        return derive_timed_events(self.index, {"film": (self.detail, "a" * 40)}, "b" * 40)

    def test_rational_pts_5s_bins_and_nearest_audio(self):
        result = self.derive()
        w = result["videos"][0]["windows"][0]
        self.assertEqual(w["cutCandidateCountsByFiveSecondBin"], [1, 1, 0, 0])
        self.assertEqual(w["cutCandidatesWithin250MsOfAudioAttack"], 1)
        self.assertEqual(w["medianInteriorCandidateGapSeconds"], 4.2)
        self.assertEqual([e["nearestAudioAttackDeltaMs"] for e in w["cutEvents"]], [100, -4100])
        self.assertEqual(result["coverage"]["cutCandidateCount025"], 2)
        self.assertEqual(result["coverage"]["audioLevelAttackCandidateCount"], 1)
        self.assertEqual(w["sourceOffsetPrecision"], "exact-opening")

    def test_no_audio_onsets_remain_unknown_not_zero_distance(self):
        self.detail["windows"][0]["audioOnsets"]["candidates"] = []
        self.index["videos"][0]["windows"][0]["audioLevelAttackCandidateCount"] = 0
        events = self.derive()["videos"][0]["windows"][0]["cutEvents"]
        self.assertTrue(all(e["nearestAudioAttackDeltaMs"] is None for e in events))
        self.assertTrue(all(not e["audioAttackWithin250Ms"] for e in events))

    def test_reject_pts_timebase_mismatch(self):
        self.detail["windows"][0]["shotCutCandidates"][0]["sourceSeconds"]["numerator"] = 8
        with self.assertRaisesRegex(ValueError, "PTS/timebase mismatch"):
            self.derive()

    def test_reject_outside_window(self):
        cut = self.detail["windows"][0]["shotCutCandidates"][-1]
        cut["sourcePts"] = 20000
        cut["sourceSeconds"] = {"numerator": 20, "denominator": 1}
        with self.assertRaisesRegex(ValueError, "outside measured window"):
            self.derive()

    def test_reject_source_hash_mismatch(self):
        self.detail["windows"][0]["audioOnsets"]["sourceSha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "index.*window mismatch"):
            self.derive()

    def test_reject_unordered_cut_candidates(self):
        w = self.detail["windows"][0]
        w["shotCutCandidates"].reverse()
        with self.assertRaisesRegex(ValueError, "nonmonotonic"):
            self.derive()

    def test_reencoded_window_offset_is_only_approximate(self):
        self.index["videos"][0]["windows"][0]["sourceOffsetSeconds"] = 40
        self.detail["windows"][0]["sourceOffsetSeconds"] = 40
        self.assertEqual(self.derive()["videos"][0]["windows"][0]["sourceOffsetPrecision"],
                         "approximate-reencoded-window")

    def test_committed_derived_data_matches_all_evidence(self):
        root = Path(__file__).resolve().parents[1] / "research/analysis/movie-promotions"
        output = root / "derived/timed-events.v1.json"
        if not (root / "index.json").is_file() or not output.is_file():
            self.skipTest("requires complete checked-out repository")
        committed = json.loads(output.read_text(encoding="utf-8"))
        generated = derive_from_folder(root)
        mismatch = first_difference(committed, generated)
        self.assertIsNone(mismatch, mismatch)


if __name__ == "__main__":
    unittest.main()
