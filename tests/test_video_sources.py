"""Offline provider-neutral references; neither source adapter fetches media."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.video_sources import (
    get_source_reference, load_source_references, search_source_references,
)
from kumiki_reference_lab.cli.app import main


ROOT = Path(__file__).resolve().parents[1]
YOUTUBE = ROOT / "research/popular-explainer-videos.v1.json"


def whatships_fixture():
    return {
        "schemaVersion": "kumiki.whatships-metadata-snapshot.v1",
        "retrievedOn": "2026-11-10",
        "source": {"indexUrl": "https://whatships.com/search-index.json"},
        "videos": [
            {
                "id": "plv-film-one", "slug": "film-one", "title": "Paper animation demo",
                "directoryUrl": "https://whatships.com/videos/film-one/",
                "indexMetadata": "Studio A · Motion", "searchText": "paper animation",
                "detail": {
                    "slug": "film-one", "title": "Paper animation demo", "product": "Paper",
                    "company": "Studio A", "category": "motion", "categoryLabel": "Motion",
                    "publishedAt": "2026-10-08T17:41:44.000Z", "durationSeconds": 61,
                    "views": 189170, "viewsCapturedAt": "2026-10-10T12:30:46.998Z",
                    "authorName": "Creator A", "authorHandle": "@creator_a",
                    "tags": ["paper", "motion"], "description": "Made entirely in code.",
                    "url": "https://whatships.com/videos/film-one/",
                    "tweetUrl": "https://x.com/creator_a/status/2108251509830140401",
                    "posterUrl": "https://whatships.com/posters/film-one.webp",
                },
            },
            {
                "id": "plv-film-two", "slug": "film-two", "title": "Unverified trailer",
                "directoryUrl": "https://whatships.com/videos/film-two/",
                "indexMetadata": "Studio B · Design", "searchText": "unverified trailer",
                "detail": None,
            },
        ],
    }


class VideoSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "whatships.json"
        self.write(whatships_fixture())

    def write(self, payload):
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def load(self):
        return load_source_references(YOUTUBE, self.path)

    def test_mixed_providers_keep_origin_and_distinct_missing_evidence(self):
        data = self.load()
        self.assertEqual(len(data["entries"]), 21)
        full = get_source_reference(data, "whatships:film-one")
        self.assertEqual(full["watchUrl"], "https://whatships.com/videos/film-one/")
        self.assertEqual(full["originalUrl"], "https://x.com/creator_a/status/2108251509830140401")
        self.assertEqual(full["views"], 189170)
        self.assertEqual(full["viewsCapturedAt"], "2026-10-10T12:30:46.998Z")
        self.assertEqual(full["durationSeconds"], 61)
        self.assertEqual(full["reviewStatus"], "metadata-only-not-frame-reviewed")
        self.assertEqual(full["rights"], {"usage": "inspiration-only", "redistributionAuthorized": False})
        partial = get_source_reference(data, "whatships:film-two")
        self.assertIsNone(partial["originalUrl"])
        self.assertIsNone(partial["views"])
        self.assertEqual(partial["evidenceStatus"], "index-only")
        youtube = get_source_reference(data, "youtube:xuCn8ux2gbs")
        self.assertEqual(youtube["watchUrl"], "https://www.youtube.com/watch?v=xuCn8ux2gbs")
        self.assertEqual(youtube["views"], 184476351)

    def test_offline_search_scopes_provider_and_ranks_real_counts_before_missing(self):
        data = self.load()
        found = search_source_references(data, "paper", provider="whatships")
        self.assertEqual([item["id"] for item in found], ["whatships:film-one"])
        self.assertEqual([item["id"] for item in search_source_references(data, provider="whatships")],
                         ["whatships:film-one", "whatships:film-two"])
        self.assertEqual([item["id"] for item in search_source_references(data, provider="whatships",
                                                                            min_views=200000)], [])
        self.assertTrue(all(item["provider"] == "youtube" for item in
                            search_source_references(data, provider="youtube")))
        with self.assertRaisesRegex(ValueError, "provider"):
            search_source_references(data, provider="untrusted")
        with self.assertRaisesRegex(ValueError, "provider"):
            search_source_references(data, provider=[])
        with self.assertRaisesRegex(ValueError, "query"):
            search_source_references(data, query=None)
        with self.assertRaisesRegex(ValueError, "minimum views"):
            search_source_references(data, min_views=-1)
        with self.assertRaisesRegex(ValueError, "limit"):
            search_source_references(data, limit=0)
        with self.assertRaisesRegex(ValueError, "unknown source"):
            get_source_reference(data, "whatships:missing")

    def test_rejects_invalid_origins_duplicates_and_evidence_types(self):
        mutations = [
            ("duplicate slug", lambda p: p["videos"].append(copy.deepcopy(p["videos"][0]))),
            ("unsafe watch URL", lambda p: p["videos"][0].update(directoryUrl="https://evil.test/videos/film-one/")),
            ("mismatched slug", lambda p: p["videos"][0]["detail"].update(slug="another")),
            ("unsafe original URL", lambda p: p["videos"][0]["detail"].update(tweetUrl="https://x.com@evil.test/status/1")),
            ("unsafe original path", lambda p: p["videos"][0]["detail"].update(tweetUrl="https://x.com/creator_a/")),
            ("negative views", lambda p: p["videos"][0]["detail"].update(views=-4)),
            ("boolean views", lambda p: p["videos"][0]["detail"].update(views=True)),
            ("views without capture date", lambda p: p["videos"][0]["detail"].update(viewsCapturedAt=None)),
            ("invalid date", lambda p: p["videos"][0]["detail"].update(publishedAt="not a date")),
            ("unsupported schema", lambda p: p.update(schemaVersion="unknown")),
        ]
        for label, mutation in mutations:
            with self.subTest(label=label):
                payload = whatships_fixture()
                mutation(payload)
                self.write(payload)
                with self.assertRaises(ValueError):
                    self.load()

    def test_rejects_ambiguous_duplicate_json_keys_and_oversized_or_symlink_files(self):
        self.path.write_text('{"schemaVersion":"one","schemaVersion":"two"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON property"):
            self.load()
        self.path.write_bytes(b" " * (8 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, "8 MiB"):
            self.load()
        self.path.unlink()
        self.path.symlink_to(YOUTUBE)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.load()

    def test_cli_lists_searches_and_shows_watch_page_without_download(self):
        for arguments, expected in (
            (["validate"], ("entryCount", 21)),
            (["list", "--provider", "whatships", "--limit", "10"], ("count", 2)),
            (["search", "paper", "--provider", "whatships"], ("count", 1)),
        ):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["video-sources", *arguments, "--youtube-root", str(YOUTUBE),
                             "--whatships", str(self.path)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.getvalue())[expected[0]], expected[1])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["video-sources", "show", "whatships:film-one", "--youtube-root",
                         str(YOUTUBE), "--whatships", str(self.path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["reference"]["watchUrl"],
                         "https://whatships.com/videos/film-one/")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["video-sources", "show", "whatships:missing", "--youtube-root",
                                   str(YOUTUBE), "--whatships", str(self.path)]), 2)

    def test_bundled_motion_snapshot_is_independently_searchable(self):
        snapshot = ROOT / "research/whatships-motion-2026-11-10.json"
        data = load_source_references(ROOT / "research", snapshot)
        self.assertEqual(len([item for item in data["entries"] if item["provider"] == "whatships"]), 69)
        self.assertEqual(len({item["id"] for item in data["entries"]}), len(data["entries"]))
        self.assertTrue(all(item["originalUrl"] is not None for item in data["entries"]
                            if item["provider"] == "whatships"))

    def test_default_cli_snapshot_covers_entire_whatships_index(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["video-sources", "validate", "--youtube-root", str(ROOT / "research")])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["byProvider"], {"youtube": 40, "whatships": 2861})


if __name__ == "__main__":
    unittest.main()
