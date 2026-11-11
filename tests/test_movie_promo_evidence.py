"""Regression checks for committed numeric-only studio trailer measurements."""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research/analysis/movie-promotions"
SUMMARY = EVIDENCE / "index.json"


class MoviePromoEvidenceTests(unittest.TestCase):
    def test_all_sources_have_three_source_hashed_numeric_windows(self):
        summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
        self.assertEqual(summary["schemaVersion"], "kumiki.movie-promotion-measurements.v1")
        self.assertEqual(summary["rightsStatus"], "review-required")
        self.assertEqual(summary["mediaCleanupStatus"], "verified-deleted-after-export")
        expected_sources = {
            "inside-out-2", "frozen-2", "moana-2", "infinity-war",
            "endgame", "zootopia-2", "force-awakens", "barbie",
            "oppenheimer", "spider-man-no-way-home", "dune-part-two",
            "super-mario-bros", "deadpool-wolverine",
        }
        ids = [video["id"] for video in summary["videos"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate trailer IDs")
        self.assertTrue(expected_sources.issubset(ids))
        self.assertEqual(
            {path.name for path in EVIDENCE.glob("*.json")},
            {"index.json", *(video_id + ".json" for video_id in ids)},
            "each summary trailer must have exactly one tracked evidence file",
        )
        sha = re.compile(r"^[0-9a-f]{64}$")
        for video in summary["videos"]:
            with self.subTest(video=video["id"]):
                report = json.loads((EVIDENCE / (video["id"] + ".json")).read_text())
                self.assertEqual(report["schemaVersion"],
                                 "kumiki.movie-promotion-window-evidence.v1")
                self.assertEqual(report["catalogId"], video["catalogId"])
                self.assertEqual(report["originalSourceSha256"], video["sourceSha256"])
                self.assertRegex(report["originalSourceSha256"], sha)
                if "sourceEdition" in video:
                    self.assertEqual(report["sourceEdition"], video["sourceEdition"])
                    self.assertEqual(report["sourceTrackId"], video["sourceTrackId"])
                    self.assertEqual(video["catalogUploadIdentityMatch"], "not-verified")
                    self.assertEqual(report["catalogUploadIdentityMatch"], "not-verified")
                    self.assertTrue(video["sourceTrackId"].isdigit())
                self.assertEqual([w["window"] for w in report["windows"]],
                                 ["opening", "middle", "ending"])
                for reported, planned in zip(report["windows"], video["windows"], strict=True):
                    self.assertEqual(reported["scanWindowSeconds"], 20)
                    self.assertEqual(reported["windowSourceSha256"],
                                     planned["windowSourceSha256"])
                    self.assertEqual(len(reported["shotCutCandidates"]),
                                     planned["cutCandidateCount"])
                    self.assertEqual(reported["defaultCutThreshold"], 0.25)
                    self.assertEqual(reported["sensitivityCutCandidateCount"],
                                     planned["cutCandidateCountAtThreshold015"])
                    self.assertGreaterEqual(reported["sensitivityCutCandidateCount"],
                                            len(reported["shotCutCandidates"]))
                    self.assertGreater(len(reported["audioLevels"]["rows"]), 100)
                    self.assertIn(reported["audioLevels"].get(
                        "excludedPartialBoundaryFrames", 0), (0, 1))
                    self.assertEqual(reported["audioLevels"]["columns"],
                                     ["sourcePts", "decodedSampleCount", "rmsDbFs", "peakDbFs"])
                    pts = [row[0] for row in reported["audioLevels"]["rows"]]
                    self.assertEqual(pts, sorted(set(pts)))
                    self.assertGreaterEqual(len(reported["appearanceSamples"]), 10)
                    self.assertGreaterEqual(len(reported["imageMotion"]["pairs"]), 20)

    def test_evidence_contains_no_local_media_or_signed_cdn_links(self):
        for file in EVIDENCE.glob("*.json"):
            with self.subTest(file=file.name):
                data = file.read_text(encoding="utf-8")
                self.assertNotIn("/tmp/", data)
                self.assertNotIn("__hdnea__", data)
                self.assertNotIn(".mp4/", data)
                self.assertNotIn("video-ssl.itunes.apple.com", data)
                self.assertNotIn("mh-kaltura.akamaized.net", data)
                self.assertNotIn("data:image", data)


if __name__ == "__main__":
    unittest.main()
