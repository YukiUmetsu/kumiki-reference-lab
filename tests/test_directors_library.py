"""Directors' Library metadata collection must not imply video analysis."""

from __future__ import annotations

import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.catalog.directors_library import (
    collect_latest, parse_film, parse_listing, summarize_snapshot,
    validate_snapshot,
)
from kumiki_reference_lab.cli.app import main


ARCHIVE = "https://directorslibrary.com/videos/latest/"
FIRST = "https://directorslibrary.com/2026/latest/campaigns/distance-x-asics/"
SECOND = "https://directorslibrary.com/2026/latest/music-videos/ghazali-elyanna/"


def script(value):
    return '<script type="application/ld+json">' + json.dumps(value) + '</script>'


def listing(url, items, *, start=1):
    return script({
        "@context": "https://schema.org", "@type": "ItemList", "url": url,
        "numberOfItems": len(items),
        "itemListElement": [{
            "@type": "ListItem", "position": i + start,
            "item": {"@type": "WebPage", "url": page, "name": title},
        } for i, (page, title) in enumerate(items)],
    })


def film(page, name, embed, director="Evan Ravo"):
    return script({
        "@context": "https://schema.org", "@type": "VideoObject",
        "url": page, "name": name, "uploadDate": "2026-11-11T11:07:43+00:00",
        "embedUrl": embed,
        "director": [{"@type": "Person", "name": director}],
        "description": "Editorial text must not be copied into the analysis dataset.",
    })


class DirectorsLibraryTests(unittest.TestCase):
    def test_listing_rejects_untrusted_video_pages_and_duplicates(self):
        markup = listing(ARCHIVE, [(FIRST, "Distance x Asics"), (SECOND, "Ghazali")])
        self.assertEqual(parse_listing(markup, ARCHIVE), [FIRST, SECOND])
        for bad in ("https://directorslibrary.com.evil.test/2026/latest/campaigns/a/",
                    "https://directorslibrary.com@evil.test/2026/latest/campaigns/a/",
                    "http://directorslibrary.com/2026/latest/campaigns/a/",
                    "https://directorslibrary.com/robots.txt"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_listing(listing(ARCHIVE, [(bad, "unsafe")]), ARCHIVE)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_listing(listing(ARCHIVE, [(FIRST, "One"), (FIRST, "Two")]), ARCHIVE)

    def test_archive_page_two_uses_absolute_one_based_positions(self):
        second_page = ARCHIVE + "page/2/"
        self.assertEqual(parse_listing(listing(second_page, [(SECOND, "Ghazali")], start=16),
                                       second_page), [SECOND])

    def test_film_extracts_source_facts_not_editorial_or_inferred_techniques(self):
        movie = parse_film(
            film(FIRST, "Distance x Asics", "https://player.vimeo.com/video/1236008415?dnt=1&app_id=122963"),
            FIRST,
        )
        self.assertEqual(movie["id"], "directors-library:2026:campaigns:distance-x-asics")
        self.assertEqual(movie["directors"], ["Evan Ravo"])
        self.assertEqual(movie["playerUrl"], "https://player.vimeo.com/video/1236008415")
        self.assertEqual(movie["playerProvider"], "vimeo")
        self.assertEqual(movie["category"], "campaigns")
        self.assertEqual(movie["sitePublishedOn"], "2026-11-11")
        self.assertNotIn("publishedOn", movie)
        self.assertIsNone(movie["durationSeconds"])
        self.assertIsNone(movie["viewCount"])
        self.assertEqual(movie["videoAnalysisStatus"], "not-performed")
        self.assertEqual(movie["rightsStatus"], "permission-required")
        self.assertNotIn("description", movie)
        self.assertNotIn("cutFrequency", movie)

    def test_unavailable_embed_is_unknown_not_guessed(self):
        entry = parse_film(film(SECOND, "Ghazali", "https://unsupported.example/video/1"), SECOND)
        self.assertEqual(entry["playerProvider"], "unknown")
        self.assertIsNone(entry["playerUrl"])

    def test_collection_visits_exact_listing_pages_and_each_detail(self):
        pages = {
            ARCHIVE: listing(ARCHIVE, [(FIRST, "Distance x Asics")]),
            ARCHIVE + "page/2/": listing(ARCHIVE + "page/2/", [(SECOND, "Ghazali")], start=16),
            FIRST: film(FIRST, "Distance x Asics", "https://player.vimeo.com/video/1236008415"),
            SECOND: film(SECOND, "Ghazali", "https://www.youtube.com/embed/XyZ123abc_8", "Naghmeh Pour"),
        }
        visited = []

        def fetch(url):
            visited.append(url)
            return pages[url]

        result = collect_latest(fetch, pages=2, retrieved_on="2026-11-11")
        self.assertEqual(visited, [ARCHIVE, FIRST, ARCHIVE + "page/2/", SECOND])
        self.assertEqual(len(result["videos"]), 2)
        self.assertEqual(result["videos"][1]["playerProvider"], "youtube")
        self.assertEqual(result["videos"][1]["directors"], ["Naghmeh Pour"])
        self.assertEqual(result["totals"]["videoPagesInspected"], 2)
        self.assertEqual(summarize_snapshot(result)["analyzedVideos"], 0)
        self.assertEqual(summarize_snapshot(result)["players"], {"vimeo": 1, "youtube": 1})
        validate_snapshot(result)

    def test_snapshot_rejects_false_analysis_and_unsafe_player_provenance(self):
        result = collect_latest(lambda url: {
            ARCHIVE: listing(ARCHIVE, [(FIRST, "Distance x Asics")]),
            FIRST: film(FIRST, "Distance x Asics", "https://player.vimeo.com/video/1236008415"),
        }[url], pages=1, retrieved_on="2026-11-11")
        for label, mutation in (
            ("false analyzed", lambda d: d["videos"][0].update(videoAnalysisStatus="measured")),
            ("unsafe player", lambda d: d["videos"][0].update(playerUrl="https://vimeo.com.evil.test/video/1")),
            ("duplicate video", lambda d: d["videos"].append(copy.deepcopy(d["videos"][0]))),
            ("wrong count", lambda d: d["totals"].update(videoPagesInspected=9)),
        ):
            with self.subTest(label=label):
                broken = copy.deepcopy(result)
                mutation(broken)
                with self.assertRaises(ValueError):
                    validate_snapshot(broken)
        with self.assertRaises(ValueError):
            collect_latest(lambda _: "", pages=0, retrieved_on="2026-11-11")

    def test_cli_writes_immutable_snapshot_and_reports_no_video_measurement(self):
        pages = {
            ARCHIVE: listing(ARCHIVE, [(FIRST, "Distance x Asics")]),
            FIRST: film(FIRST, "Distance x Asics", "https://player.vimeo.com/video/1236008415"),
        }
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "index.json"
            with patch("kumiki_reference_lab.cli.app.fetch_public_page", side_effect=pages.__getitem__):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(main(["directors-library", "snapshot", "--pages", "1",
                                           "--retrieved-on", "2026-11-11",
                                           "--out", str(destination)]), 0)
            self.assertTrue(destination.is_file())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["directors-library", "validate", "--snapshot",
                                       str(destination)]), 0)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["directors-library", "report", "--snapshot",
                                       str(destination)]), 0)
            self.assertEqual(json.loads(out.getvalue())["analyzedVideos"], 0)
            with patch("kumiki_reference_lab.cli.app.fetch_public_page", side_effect=pages.__getitem__):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["directors-library", "snapshot", "--pages", "1",
                                           "--retrieved-on", "2026-11-12",
                                           "--out", str(destination)]), 2)


if __name__ == "__main__":
    unittest.main()
