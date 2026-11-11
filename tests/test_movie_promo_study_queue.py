"""Regression tests: study queue metadata must never be confused with measured evidence."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.audit_movie_promo_study_queue import audit


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "research/analysis/movie-promotions/study-queue.v1.json"
CATALOG = ROOT / "research/popular-movie-videos.v1.json"


class MoviePromoQueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = json.loads(QUEUE.read_text(encoding="utf-8"))
        self.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    def test_valid_unmeasured_queue_is_studio_diverse(self):
        self.assertEqual(audit(self.queue, self.catalog), [])
        self.assertGreaterEqual(len(self.queue["entries"]), 26)
        self.assertGreaterEqual(len({item["filmStudio"] for item in self.queue["entries"]}), 15)
        self.assertTrue(all(item["mediaAnalysisStatus"] == "not-performed" for item in self.queue["entries"]))

    def test_duplicate_existing_upload_rejected(self):
        data = copy.deepcopy(self.queue)
        data["entries"][0]["youtubeId"] = self.catalog["entries"][0]["youtubeId"]
        self.assertTrue(any("duplicate official upload" in x for x in audit(data, self.catalog)))

    def test_false_analysis_evidence_rejected(self):
        data = copy.deepcopy(self.queue)
        data["entries"][0]["mediaAnalysisStatus"] = "measured"
        data["entries"][0]["sourceSha256"] = "0" * 64
        result = audit(data, self.catalog)
        self.assertTrue(any("false evidence status" in x for x in result))
        self.assertTrue(any("must not contain source evidence" in x for x in result))

    def test_untrusted_rights_rejected(self):
        data = copy.deepcopy(self.queue)
        data["entries"][0]["rights"]["redistributionAuthorized"] = True
        self.assertTrue(any("rights declaration" in x for x in audit(data, self.catalog)))

    def test_invalid_upload_url_and_duplicate_ids_rejected(self):
        data = copy.deepcopy(self.queue)
        data["entries"][0]["officialYoutubeUrl"] = "https://example.invalid"
        data["entries"][1]["id"] = data["entries"][0]["id"]
        result = audit(data, self.catalog)
        self.assertTrue(any("upload URL mismatch" in x for x in result))
        self.assertTrue(any("duplicate slug" in x for x in result))

    def test_disguised_evidence_host_rejected(self):
        data = copy.deepcopy(self.queue)
        data["entries"][0]["viewEvidence"]["sourceUrl"] = "https://youtube.com@evil.example/watch?v=123"
        self.assertTrue(any("unsafe evidence URL" in x for x in audit(data, self.catalog)))

    def test_missing_film_metadata_rejected(self):
        data = copy.deepcopy(self.queue)
        data["entries"][0]["filmStudio"] = ""
        self.assertTrue(any("invalid film metadata" in x for x in audit(data, self.catalog)))

    def test_recent_official_uploads_and_non_hollywood_film_styles(self):
        ids = {entry["youtubeId"] for entry in self.queue["entries"]}
        self.assertEqual(len(ids), len(self.queue["entries"]))
        for video_id in ("AzCAwdp1uIQ", "d_Z_tybgPgg", "nsXQijb0F4I",
                         "VvSrHIX5a-0", "Pu0pH5BuCPM", "9kb7vK11_Rw"):
            self.assertIn(video_id, ids)
        self.assertFalse(any("sourceSha256" in row or "windows" in row
                             for row in self.queue["entries"]))

    def test_third_party_video_evidence_requires_exact_source_id(self):
        data = copy.deepcopy(self.queue)
        row = next(item for item in data["entries"]
                   if item["id"] == "godzilla-minus-zero-trailer-3")
        self.assertEqual(audit(data, self.catalog), [])
        row["viewEvidence"]["sourceUrl"] = (
            "https://chartslist.com/youtube/video/different-film/video")
        self.assertTrue(any("unsafe evidence URL" in x for x in audit(data, self.catalog)))

    def test_third_party_video_evidence_rejects_masqueraded_host(self):
        data = copy.deepcopy(self.queue)
        row = next(item for item in data["entries"]
                   if item["id"] == "godzilla-minus-zero-trailer-3")
        row["viewEvidence"]["sourceUrl"] = (
            "https://chartslist.com.evil.example/youtube/video/"
            + row["youtubeId"] + "/video")
        self.assertTrue(any("unsafe evidence URL" in x for x in audit(data, self.catalog)))

    def test_view_counts_cannot_be_strings(self):
        data = copy.deepcopy(self.queue)
        data["entries"][0]["viewEvidence"]["reportedViews"] = "60 million"
        self.assertTrue(any("invalid reported views" in x for x in audit(data, self.catalog)))


if __name__ == "__main__":
    unittest.main()
