"""Search-indexed YouTube links cannot silently turn into verified videos."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.audience_benchmarks import load_audience_benchmarks
from kumiki_reference_lab.catalog.video_id_candidates import (
    load_video_id_candidates, validate_video_id_candidates,
)


ROOT = Path(__file__).resolve().parents[1]


class CandidateIdentityTests(unittest.TestCase):
    def setUp(self):
        self.audience = load_audience_benchmarks(ROOT / "research/audience-recent-uploads.v1.json")
        self.candidates = load_video_id_candidates(
            ROOT / "research/video-id-candidates.v1.json", self.audience)

    def test_exact_rows_have_youtube_index_evidence_only(self):
        self.assertEqual(len(self.candidates["entries"]), 2)
        self.assertTrue(all(e["reviewStatus"] == "index-corroborated-watch-page-not-opened"
                            and e["videoUrl"] == e["evidenceUrl"]
                            for e in self.candidates["entries"]))

    def test_reject_stale_invented_duplicate_unsafe_or_unverified_links(self):
        for name, mutate in (
            ("mismatched hash", lambda x: x["entries"][0].update(sourceRowSha256="a" * 64)),
            ("wrong row", lambda x: x["entries"][0].update(rowIndex=21)),
            ("fake approval", lambda x: x["entries"][0].update(reviewStatus="physically-verified")),
            ("publisher", lambda x: x["entries"][0].update(indexedPublisher="Unrelated")),
            ("title", lambda x: x["entries"][0].update(indexedTitle="A different film")),
            ("date", lambda x: x["entries"][0].update(indexedPublishedOn="2025-11-01")),
            ("unsafe url", lambda x: x["entries"][0].update(videoUrl="https://www.youtube.com@evil.test/watch?v=j0ZZfIz9R1I")),
            ("wrong video", lambda x: x["entries"][0].update(youtubeId="01234567890")),
            ("duplicate video ID", lambda x: x["entries"][1].update(youtubeId=x["entries"][0]["youtubeId"])),
            ("duplicate row", lambda x: x["entries"].append(copy.deepcopy(x["entries"][0]))),
            ("extra field", lambda x: x["entries"][0].update(style="cinematic")),
            ("future schema", lambda x: x.update(schemaVersion="v2")),
        ):
            with self.subTest(name=name):
                changed = copy.deepcopy(self.candidates)
                mutate(changed)
                with self.assertRaises(ValueError):
                    validate_video_id_candidates(changed, self.audience)

    def test_io_guards_duplicate_keys_symlink_and_size(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "candidates.json"
            target.write_text('{"a":1,"a":2}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_video_id_candidates(target, self.audience)
            target.write_bytes(b" " * 131_073)
            with self.assertRaisesRegex(ValueError, "128 KiB"):
                load_video_id_candidates(target, self.audience)
            link = Path(directory) / "link.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "regular"):
                load_video_id_candidates(link, self.audience)
