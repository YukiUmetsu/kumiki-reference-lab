"""Regression gates for popularity sources, research provenance and safe lookup."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.popular_videos import (
    load_popular_videos, search_popular_videos, validate_popular_videos,
)
from kumiki_reference_lab.cli.app import main


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "research/popular-explainer-videos.v1.json"
CINEMATIC = ROOT / "research/popular-cinematic-videos.v1.json"
MOVIE_PROMOS = ROOT / "research/popular-movie-videos.v1.json"


class PopularVideoTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_popular_videos(COLLECTION)

    def test_collection_is_diverse_documented_and_not_reuse_licensed(self):
        items = self.catalog["entries"]
        self.assertEqual(len(items), 19)
        self.assertGreaterEqual(len({item["creator"] for item in items}), 10)
        self.assertTrue(all(item["viewEvidence"]["viewCount"] >= 5_000_000 for item in items))
        self.assertEqual(sum(item["viewEvidence"]["viewCount"] for item in items), 726_127_863)
        self.assertEqual([item["viewEvidence"]["viewCount"] for item in items],
                         sorted((item["viewEvidence"]["viewCount"] for item in items), reverse=True))
        self.assertGreaterEqual(sum("three-dimensional-explainer" in item["techniqueTags"]
                                    for item in items), 7)
        self.assertTrue(all(item["rights"]["usage"] == "inspiration-only" and
                            item["rights"]["redistributionAuthorized"] is False and
                            item["reviewStatus"] == "editorial-candidate-not-frame-reviewed"
                            for item in items))
        self.assertTrue(all(item["viewEvidence"]["sourceUrl"].startswith("https://")
                            and item["videoUrl"].endswith(item["youtubeId"])
                            for item in items))

    def test_tags_and_view_threshold_rank_deterministically(self):
        result = search_popular_videos(self.catalog, "camera scale", min_views=10_000_000)
        self.assertEqual(result[0]["id"], "kurzgesagt-largest-star")
        self.assertEqual(result, search_popular_videos(self.catalog, "camera scale", min_views=10_000_000))
        self.assertEqual(search_popular_videos(self.catalog, "qxzxqz-nonexistent"), [])
        self.assertEqual(search_popular_videos(self.catalog, min_views=100_000_000)[0]["id"],
                         "bill-wurtz-history-world")
        self.assertEqual(len(search_popular_videos(self.catalog, limit=3)), 3)
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            search_popular_videos(self.catalog, min_views=-1)
        with self.assertRaisesRegex(ValueError, "between 1 and 100"):
            search_popular_videos(self.catalog, limit=0)

    def test_broad_cinematic_cohort_and_combined_search(self):
        cinematic = load_popular_videos(CINEMATIC)
        items = cinematic["entries"]
        self.assertEqual(len(items), 21)
        self.assertGreaterEqual(len({item["creator"] for item in items}), 15)
        self.assertEqual(sum(item["viewEvidence"]["viewCount"] for item in items), 1_814_369_302)
        self.assertEqual([item["viewEvidence"]["viewCount"] for item in items],
                         sorted((item["viewEvidence"]["viewCount"] for item in items), reverse=True))
        self.assertTrue(all(item["viewEvidence"]["viewCount"] >= 5_000_000 for item in items))
        self.assertTrue(all(item["rights"] == {"usage": "inspiration-only", "redistributionAuthorized": False}
                            and item["reviewStatus"] == "editorial-candidate-not-frame-reviewed" for item in items))
        all_videos = load_popular_videos(ROOT / "research")
        self.assertEqual(len(all_videos["entries"]), 53)
        self.assertEqual(sum(item["viewEvidence"]["viewCount"] for item in all_videos["entries"]), 3_653_141_867)
        self.assertEqual(len({item["youtubeId"] for item in all_videos["entries"]}), 53)
        self.assertEqual(len({item["creator"] for item in all_videos["entries"]}), 34)
        self.assertEqual(search_popular_videos(all_videos, "title sequence")[0]["id"],
                         "stranger-things-title-sequence")
        self.assertEqual(search_popular_videos(all_videos, "match cut")[0]["id"],
                         "nike-you-cant-stop-us")

    def test_movie_promotion_cohort_is_separate_searchable_and_inspiration_only(self):
        movies = load_popular_videos(MOVIE_PROMOS)
        items = movies["entries"]
        self.assertEqual(len(items), 13)
        self.assertGreaterEqual(len({entry["creator"] for entry in items}), 8)
        self.assertEqual(sum(entry["viewEvidence"]["viewCount"] for entry in items), 1_112_644_702)
        self.assertEqual([entry["viewEvidence"]["viewCount"] for entry in items],
                         sorted((entry["viewEvidence"]["viewCount"] for entry in items), reverse=True))
        self.assertTrue(all(entry["reviewStatus"] == "editorial-candidate-not-frame-reviewed"
                            and entry["rights"] == {"usage": "inspiration-only", "redistributionAuthorized": False}
                            for entry in items))
        self.assertEqual(search_popular_videos(movies, "comic timing")[0]["id"],
                         "pixar-inside-out-2-trailer")

    def test_directory_rejects_ambiguous_or_unsafe_cohorts(self):
        with tempfile.TemporaryDirectory() as directory:
            research = Path(directory)
            with self.assertRaisesRegex(ValueError, "must contain"):
                load_popular_videos(research)
            (research / "popular-first-videos.v1.json").write_bytes(COLLECTION.read_bytes())
            (research / "popular-second-videos.v1.json").write_bytes(COLLECTION.read_bytes())
            with self.assertRaisesRegex(ValueError, "duplicate video across research cohorts"):
                load_popular_videos(research)
            (research / "popular-second-videos.v1.json").unlink()
            (research / "popular-second-videos.v1.json").symlink_to(CINEMATIC)
            with self.assertRaisesRegex(ValueError, "regular file"):
                load_popular_videos(research)
            with self.assertRaisesRegex(ValueError, "symlink"):
                load_popular_videos(research / "popular-second-videos.v1.json")

    def test_invalid_or_misrepresented_sources_cannot_be_loaded(self):
        mutations = [
            ("duplicate video", lambda c: c["entries"].append(copy.deepcopy(c["entries"][0]))),
            ("wrong video URL", lambda c: c["entries"][0].update(videoUrl="https://example.com/unsafe")),
            ("fake permissions", lambda c: c["entries"][0]["rights"].update(redistributionAuthorized=True)),
            ("fake approval", lambda c: c["entries"][0].update(reviewStatus="verified")),
            ("views string", lambda c: c["entries"][0]["viewEvidence"].update(viewCount="million")),
            ("unclear source", lambda c: c["entries"][0]["viewEvidence"].update(sourceUrl="http://invalid")),
            ("malformed host", lambda c: c["entries"][0]["viewEvidence"].update(sourceUrl="https://[invalid")),
            ("disguised host", lambda c: c["entries"][0]["viewEvidence"].update(sourceUrl="https://youtube.com@evil.example/")),
            ("future source", lambda c: c["entries"][3]["viewEvidence"].update(sourceSnapshotOn="2030-01-01")),
            ("malformed source kind", lambda c: c["entries"][0]["viewEvidence"].update(sourceKind=[])),
            ("duplicate technique tag", lambda c: c["entries"][0]["techniqueTags"].append("kinetic-typography")),
            ("unknown key", lambda c: c["entries"][0].update(mediaDownloadUrl="https://example.com")),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                candidate = copy.deepcopy(self.catalog)
                mutate(candidate)
                self.assertTrue(validate_popular_videos(candidate), name)

    def test_duplicate_keys_oversize_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "bad.json"
            bad.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON property"):
                load_popular_videos(bad)
            bad.write_bytes(b" " * 270_000)
            with self.assertRaisesRegex(ValueError, "256 KiB"):
                load_popular_videos(bad)
            link = root / "link.json"
            link.symlink_to(COLLECTION)
            with self.assertRaisesRegex(ValueError, "symlink"):
                load_popular_videos(link)

    def test_cli_validate_list_search_and_errors(self):
        for argv, expected_count in (
            (["validate"], 19),
            (["list", "--min-views", "100000000"], 2),
            (["search", "exploded view"], 2),
        ):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["video-references", *argv, "--root", str(COLLECTION)]), 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result.get("entryCount", result.get("count")), expected_count)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["video-references", "list", "--min-views", "-2",
                                   "--root", str(COLLECTION)]), 2)

    def test_cli_directory_search_and_validation(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(["video-references", "validate", "--root", str(ROOT / "research")]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["entryCount"], 53)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(["video-references", "search", "cinematic lighting", "--root",
                                   str(ROOT / "research")]), 0)
        self.assertIn("league-of-legends-the-call", [entry["id"] for entry in json.loads(stdout.getvalue())["results"]])


if __name__ == "__main__":
    unittest.main()
