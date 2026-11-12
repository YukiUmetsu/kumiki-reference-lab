"""Offline tests for the WordPress poster-stills research adapter."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from kumiki_reference_lab import acquisition as acq
from scripts import research_wordpress_stills as wps

DL = "directorslibrary"
STASH = "stash"

DL_TAXONOMY_IDS = (
    "categories", "tags", "location", "aspect_ratio", "agency",
    "record_label", "festival", "award", "format",
)


def headers(*, total: int | None = None, total_pages: int | None = None) -> dict:
    result: dict[str, str] = {}
    if total is not None:
        result["x-wp-total"] = str(total)
    if total_pages is not None:
        result["x-wp-totalpages"] = str(total_pages)
    return result


def raw_item(**overrides: object) -> dict:
    """A typical Directors' Library WP REST row."""
    item: dict[str, object] = {
        "id": 101,
        "slug": "demo-video",
        "date": "2026-01-02T03:04:05",
        "link": "https://directorslibrary.com/video/demo-video/",
        "title": {"rendered": "Demo &#8217;Video&#8217; &#038; More"},
        "featured_media": 55,
        "categories": [3],
        "tags": [9, 10],
        "location": [],
        "aspect_ratio": [12],
        "agency": [],
        "record_label": [],
        "festival": [],
        "award": [],
        "format": [7],
        "class_list": ["post-101", "video"],
        "yoast_head_json": {
            "og_type": "video.other",
            "og_image": [{
                "url": "https://directorslibrary.com/wp-content/uploads/demo.jpg",
                "width": 1280,
                "height": 720,
            }],
        },
    }
    item.update(overrides)
    return item


def stash_item(**overrides: object) -> dict:
    item: dict[str, object] = {
        "id": 202,
        "slug": "stash-post",
        "date": "2026-02-03T04:05:06",
        "link": "https://www.stashmedia.tv/stash-post/",
        "title": {"rendered": "Stash &#038; Post"},
        "excerpt": {"rendered": "<p>Short <strong>teaser</strong> &#8220;here&#8221;</p>"},
        "featured_media": 77,
        "categories": [5],
        "author": 9,
        "yoast_head_json": {
            "og_type": "article",
            "og_image": [{
                "url": "https://www.stashmedia.tv/wp-content/uploads/poster.png",
                "width": 1200,
                "height": 630,
            }],
        },
    }
    item.update(overrides)
    return item


class FakeWP:
    """Offline WP REST double: routes catalogue pages and taxonomy pages."""

    def __init__(
        self, site_key: str, pages: dict[int, object],
        terms: dict[str, list[list[dict]]] | None = None,
        *, total: int | None = None, total_pages: int | None = None,
    ) -> None:
        self.site = wps.site_config(site_key)
        self.pages = pages
        self.terms = terms or {}
        self.total = total
        self.total_pages = total_pages
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[object, dict]:
        self.calls.append(url)
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        for taxonomy, pages in self.terms.items():
            if parts.path.endswith("/" + taxonomy):
                page = int(query["page"][0])
                payload = pages[page - 1]
                if isinstance(payload, Exception):
                    raise payload
                return payload, headers(total_pages=len(pages))
        page = int(query["page"][0])
        payload = self.pages.get(page, [])
        if isinstance(payload, Exception):
            raise payload
        return payload, headers(total=self.total, total_pages=self.total_pages)


class CatalogPagingTests(unittest.TestCase):
    def test_paging_stops_at_total_pages_and_orders_rows(self) -> None:
        pages = {
            1: [raw_item(id=1, date="2026-01-01T00:00:00"),
                raw_item(id=2, date="2026-01-03T00:00:00")],
            2: [raw_item(id=3, date="2026-01-02T00:00:00")],
        }
        fake = FakeWP(DL, pages, total=3, total_pages=2)
        rows, meta = wps.fetch_catalog(
            DL, page_size=2, delay_seconds=0, fetch=fake, sleep=lambda _: None,
            log=lambda _: None)

        self.assertEqual([row["id"] for row in rows], [2, 3, 1])
        self.assertEqual(meta["reportedTotal"], 3)
        self.assertEqual(meta["pagesFetched"], 2)
        self.assertFalse(meta["overflow"])
        # One request per page, and no third page fetch.
        self.assertEqual(len([url for url in fake.calls if "/video?" in url]), 2)

    def test_terminal_page_overflow_stops_without_retry(self) -> None:
        fake = FakeWP(
            DL, {1: [raw_item()], 2: wps.PageOverflow("synthetic overflow")},
            total=5412, total_pages=99)
        rows, meta = wps.fetch_catalog(
            DL, page_size=1, delay_seconds=0, fetch=fake, sleep=lambda _: None,
            log=lambda _: None)

        self.assertEqual(len(rows), 1)
        self.assertTrue(meta["overflow"])
        self.assertEqual(
            len([url for url in fake.calls if "/video?" in url]), 2)

    def test_http_400_invalid_page_number_is_terminal_and_not_retried(self) -> None:
        url = ("https://directorslibrary.com/wp-json/wp/v2/video?"
               "per_page=1&page=9")
        body = io.BytesIO(json.dumps(
            {"code": "rest_post_invalid_page_number",
             "message": "The page number requested is larger than the number "
                        "of pages available."}).encode())
        error = HTTPError(url, 400, "Bad Request", None, body)
        slept: list[float] = []
        with patch.object(wps, "urlopen", side_effect=error) as opener:
            with self.assertRaises(wps.PageOverflow):
                wps._get_json(
                    url, allowed_hosts=("directorslibrary.com",),
                    sleep=slept.append)
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(slept, [])

    def test_http_4xx_other_than_overflow_is_a_contract_error(self) -> None:
        url = ("https://directorslibrary.com/wp-json/wp/v2/video?"
               "per_page=1&page=1")
        body = io.BytesIO(json.dumps({"code": "rest_forbidden"}).encode())
        error = HTTPError(url, 403, "Forbidden", None, body)
        with patch.object(wps, "urlopen", side_effect=error):
            with self.assertRaises(ValueError):
                wps._get_json(
                    url, allowed_hosts=("directorslibrary.com",),
                    sleep=lambda _: None)

    def test_fields_projection_and_query_shape(self) -> None:
        fake = FakeWP(DL, {1: [raw_item()]}, total=1, total_pages=1)
        wps.fetch_catalog(
            DL, limit=1, page_size=100, delay_seconds=0, fetch=fake,
            sleep=lambda _: None, log=lambda _: None)
        catalog_calls = [url for url in fake.calls if "/video?" in url]
        parts = urlsplit(catalog_calls[0])
        query = parse_qs(parts.query)
        self.assertEqual(parts.path, "/wp-json/wp/v2/video")
        self.assertEqual(query["per_page"], ["100"])
        self.assertEqual(query["page"], ["1"])
        self.assertEqual(query["orderby"], ["date"])
        self.assertEqual(query["order"], ["desc"])
        self.assertEqual(query["_fields"], [",".join(
            wps.SITES[DL]["catalogFields"])])

    def test_stash_post_type_and_fields(self) -> None:
        fake = FakeWP(STASH, {1: [stash_item()]}, total=1, total_pages=1)
        wps.fetch_catalog(
            STASH, limit=1, delay_seconds=0, fetch=fake, sleep=lambda _: None,
            log=lambda _: None)
        parts = urlsplit(fake.calls[0])
        self.assertEqual(parts.path, "/wp-json/wp/v2/posts")
        self.assertIn("excerpt", parse_qs(parts.query)["_fields"][0])


class CatalogProjectionTests(unittest.TestCase):
    def resolve(self, site_key: str, fake: FakeWP, limit: int | None = None):
        return wps.fetch_catalog(
            site_key, limit=limit, page_size=100, delay_seconds=0, fetch=fake,
            sleep=lambda _: None, log=lambda _: None)

    def test_term_ids_are_resolved_to_names_and_cached(self) -> None:
        terms = {
            "categories": [
                [{"id": 3, "name": "Awards", "slug": "awards"}],
                [{"id": 4, "name": "Music Videos", "slug": "music-videos"}],
            ],
            "tags": [[{"id": 9, "name": "3d", "slug": "3d"},
                      {"id": 10, "name": "typography", "slug": "typography"}]],
            "aspect_ratio": [[{"id": 12, "name": "16:9", "slug": "16-9"}]],
            "format": [[{"id": 7, "name": "Short", "slug": "short"}]],
        }
        item = raw_item(categories=[3, 4])
        fake = FakeWP(DL, {1: [item]}, terms, total=1, total_pages=1)
        rows, meta = self.resolve(DL, fake)
        row = rows[0]

        self.assertEqual(row["termIds"]["categories"], [3, 4])
        self.assertEqual(row["terms"]["categories"], ["Awards", "Music Videos"])
        self.assertEqual(row["terms"]["tags"], ["3d", "typography"])
        self.assertEqual(row["terms"]["aspect_ratio"], ["16:9"])
        self.assertNotIn("agency", row["termIds"])
        self.assertNotIn("agency", row["terms"])
        cache = meta["termCache"]
        self.assertEqual(cache["categories"]["3"]["name"], "Awards")
        self.assertEqual(cache["categories"]["4"]["slug"], "music-videos")
        self.assertEqual(meta["termErrors"], {})
        # Two pages of categories were fetched, following X-WP-TotalPages.
        category_calls = [url for url in fake.calls
                          if "/categories?" in url]
        self.assertEqual(len(category_calls), 2)

    def test_taxonomy_absent_from_rows_is_not_fetched(self) -> None:
        item = raw_item()
        for taxonomy in DL_TAXONOMY_IDS:
            item[taxonomy] = []
        fake = FakeWP(DL, {1: [item]}, total=1, total_pages=1)
        _, meta = self.resolve(DL, fake)
        taxonomy_calls = [url for url in fake.calls
                          if any(f"/{tax}?" in url for tax in DL_TAXONOMY_IDS)]
        self.assertEqual(taxonomy_calls, [])
        self.assertEqual(meta["termCache"], {})

    def test_title_entities_are_unescaped(self) -> None:
        fake = FakeWP(DL, {1: [raw_item()]}, total=1, total_pages=1)
        rows, _ = self.resolve(DL, fake)
        self.assertEqual(rows[0]["title"], "Demo ’Video’ & More")

    def test_stash_excerpt_is_stripped_and_unescaped(self) -> None:
        fake = FakeWP(STASH, {1: [stash_item()]}, total=1, total_pages=1)
        rows, _ = self.resolve(STASH, fake)
        row = rows[0]
        self.assertEqual(row["title"], "Stash & Post")
        self.assertEqual(row["excerptText"], "Short teaser “here”")

    def test_directorslibrary_row_has_no_excerpt_field(self) -> None:
        fake = FakeWP(DL, {1: [raw_item()]}, total=1, total_pages=1)
        rows, _ = self.resolve(DL, fake)
        self.assertNotIn("excerptText", rows[0])

    def test_slim_row_stays_under_one_kilobyte(self) -> None:
        item = raw_item(
            tags=[9, 10, 11, 12, 13, 14],
            title={"rendered": "A reasonably long but realistic catalogue title "
                               "for a commercial &#038; short film"},
        )
        cache = {
            "categories": {"3": {"name": "Awards", "slug": "awards"}},
            "tags": {str(i): {"name": f"Tag {i}", "slug": f"tag-{i}"}
                     for i in (9, 10, 11, 12, 13, 14)},
            "aspect_ratio": {"12": {"name": "16:9", "slug": "16-9"}},
            "format": {"7": {"name": "Short", "slug": "short"}},
        }
        row = wps.normalize_row(wps.SITES[DL], item, cache)
        encoded = json.dumps(row, ensure_ascii=False)
        self.assertLess(len(encoded), 1024, encoded)

    def test_missing_og_image_is_a_row_not_a_crash(self) -> None:
        item = raw_item(yoast_head_json={})
        fake = FakeWP(DL, {1: [item]}, total=1, total_pages=1)
        rows, _ = self.resolve(DL, fake)
        row = rows[0]
        self.assertIsNone(row["posterUrl"])
        self.assertEqual(row["posterStatus"], "missing-og-image")
        self.assertFalse(row["videoDownloadable"])

    def test_missing_yoast_head_is_tolerated(self) -> None:
        item = raw_item()
        item.pop("yoast_head_json")
        fake = FakeWP(DL, {1: [item]}, total=1, total_pages=1)
        rows, _ = self.resolve(DL, fake)
        self.assertEqual(rows[0]["posterStatus"], "missing-og-image")

    def test_poster_on_wrong_host_is_rejected(self) -> None:
        item = raw_item(yoast_head_json={"og_image": [{
            "url": "https://evil.example/poster.jpg",
            "width": 100, "height": 100}]})
        fake = FakeWP(DL, {1: [item]}, total=1, total_pages=1)
        rows, _ = self.resolve(DL, fake)
        self.assertIsNone(rows[0]["posterUrl"])
        self.assertEqual(rows[0]["posterStatus"], "poster-host-not-allowlisted")
        with self.assertRaises(ValueError):
            wps.policy_image_url(
                wps.SITES[DL], "https://evil.example/poster.jpg")

    def test_poster_with_query_string_is_rejected(self) -> None:
        item = raw_item(yoast_head_json={"og_image": [{
            "url": "https://directorslibrary.com/p.jpg?token=1",
            "width": 100, "height": 100}]})
        fake = FakeWP(DL, {1: [item]}, total=1, total_pages=1)
        rows, _ = self.resolve(DL, fake)
        self.assertIsNone(rows[0]["posterUrl"])

    def test_http_poster_on_the_site_host_is_upgraded_to_https(self) -> None:
        item = stash_item(yoast_head_json={"og_image": [{
            "url": "http://www.stashmedia.tv/wp-content/uploads/poster.jpg",
            "width": 1200, "height": 630}]})
        fake = FakeWP(STASH, {1: [item]}, total=1, total_pages=1)
        rows, _ = self.resolve(STASH, fake)
        self.assertEqual(
            rows[0]["posterUrl"],
            "https://www.stashmedia.tv/wp-content/uploads/poster.jpg")
        self.assertEqual(rows[0].get("posterStatus", "ok"), "ok")
        self.assertEqual(
            wps.policy_image_url(
                wps.SITES[STASH],
                "http://www.stashmedia.tv/wp-content/uploads/poster.jpg"),
            "https://www.stashmedia.tv/wp-content/uploads/poster.jpg")

    def test_http_poster_on_another_host_is_still_rejected(self) -> None:
        item = raw_item(yoast_head_json={"og_image": [{
            "url": "http://evil.example/poster.jpg",
            "width": 100, "height": 100}]})
        fake = FakeWP(DL, {1: [item]}, total=1, total_pages=1)
        rows, _ = self.resolve(DL, fake)
        self.assertIsNone(rows[0]["posterUrl"])
        self.assertEqual(rows[0]["posterStatus"], "poster-host-not-allowlisted")

    def test_provider_is_embed_only_for_directorslibrary(self) -> None:
        fake = FakeWP(DL, {1: [raw_item()]}, total=1, total_pages=1)
        rows, _ = self.resolve(DL, fake)
        self.assertEqual(rows[0]["provider"], "unsupported-embed")
        self.assertEqual(rows[0]["videoDownloadableReason"],
                         "third-party-embed")

    def test_stash_gallery_row_has_null_provider(self) -> None:
        item = stash_item(yoast_head_json={
            "og_type": "article",
            "og_image": [{"url": "https://www.stashmedia.tv/p.png",
                          "width": 10, "height": 10}]})
        fake = FakeWP(STASH, {1: [item]}, total=1, total_pages=1)
        rows, _ = self.resolve(STASH, fake)
        self.assertIsNone(rows[0]["provider"])
        self.assertFalse(rows[0]["videoDownloadable"])

    def test_build_catalog_counts_and_schemas(self) -> None:
        fake = FakeWP(DL, {1: [raw_item(), raw_item(
            id=102, slug="no-poster", yoast_head_json={})]},
            total=2, total_pages=1)
        rows, meta = self.resolve(DL, fake)
        catalog = wps.build_catalog(
            DL, rows, meta=meta, generated_at="2026-01-01T00:00:00Z")
        self.assertEqual(catalog["schemaVersion"],
                         "kumiki.directorslibrary-catalog.v1")
        self.assertEqual(catalog["counts"]["catalogItems"], 2)
        self.assertEqual(catalog["counts"]["withPoster"], 1)
        self.assertEqual(catalog["counts"]["withoutPoster"], 1)
        self.assertEqual(catalog["counts"]["providerCounts"],
                         {"unsupported-embed": 2})
        self.assertEqual(catalog["generatedAt"], "2026-01-01T00:00:00Z")
        self.assertIn("Vimeo", catalog["providerNote"])

    def test_limit_zero_makes_no_request(self) -> None:
        calls: list[str] = []

        def fake(url: str):
            calls.append(url)
            return [], {}

        rows, meta = wps.fetch_catalog(
            DL, limit=0, fetch=fake, sleep=lambda _: None, log=lambda _: None)
        self.assertEqual(rows, [])
        self.assertEqual(calls, [])
        self.assertEqual(meta["pagesFetched"], 0)


class StillCollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def catalog(self, items: list[dict], *, site_key: str = DL) -> Path:
        cache = {
            "categories": {"3": {"name": "Awards", "slug": "awards"}},
            "tags": {"9": {"name": "3d", "slug": "3d"},
                     "10": {"name": "typography", "slug": "typography"}},
            "aspect_ratio": {"12": {"name": "16:9", "slug": "16-9"}},
            "format": {"7": {"name": "Short", "slug": "short"}},
        }
        rows = [wps.normalize_row(wps.SITES[site_key], item, cache)
                for item in items]
        catalog = wps.build_catalog(
            site_key, rows, meta={
                "reportedTotal": len(rows), "pagesFetched": 1,
                "termCache": cache, "termErrors": {}},
            generated_at="2026-01-01T00:00:00Z")
        path = self.root / "catalog.json"
        acq.write_json_atomic(path, catalog)
        return path

    def record(self, row: dict, *, site_key: str = DL,
               luma: float = 0.4, hue: str = "blue") -> dict:
        return wps.build_still_record(site_key, row, still={
            "imageUrl": row["posterUrl"],
            "imageSha256": "a" * 64,
            "imageFormat": "jpg",
            "imageBytes": 1234,
            "imageWidth": 1280,
            "imageHeight": 720,
            "metrics": {
                "meanRgb": [0.1, 0.2, 0.3],
                "meanDisplayLumaProxy": luma,
                "displayLumaStdDev": 0.1,
                "meanSaturationProxy": 0.3,
                "shadowPixelFraction": 0.02,
                "brightPixelFraction": 0.05,
                "lumaHistogram": [0.1, 0.2, 0.3, 0.2, 0.2],
                "dominantHueFamily": hue,
                "edgeDensityProxy": 0.07,
            },
        }, generated_at="2026-01-02T00:00:00Z")

    def test_resume_leaves_existing_record_bytes_and_mtime_untouched(self) -> None:
        catalog_path = self.catalog([
            raw_item(), raw_item(id=102, slug="no-poster", yoast_head_json={})])
        out_dir = self.root / "out"
        row = wps.normalize_row(
            wps.SITES[DL], raw_item(),
            {"categories": {"3": {"name": "Awards", "slug": "awards"}},
             "tags": {"9": {"name": "3d", "slug": "3d"},
                      "10": {"name": "typography", "slug": "typography"}},
             "aspect_ratio": {"12": {"name": "16:9", "slug": "16-9"}},
             "format": {"7": {"name": "Short", "slug": "short"}}})
        existing = wps.record_path(out_dir, row)
        acq.write_json_atomic(existing, self.record(row))
        before_bytes = existing.read_bytes()
        before_mtime = existing.stat().st_mtime_ns

        with patch.object(wps, "collect_still_one") as collect:
            code = wps.run_stills(
                DL, catalog_path, out_dir=out_dir, limit=0, resume=True,
                delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 0)
        collect.assert_not_called()
        self.assertEqual(existing.read_bytes(), before_bytes)
        self.assertEqual(existing.stat().st_mtime_ns, before_mtime)
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schemaVersion"],
                         "kumiki.directorslibrary-stills-index.v1")
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 2, "failed": 0})
        self.assertEqual(
            sorted(row["reason"] for row in index["skips"]),
            ["no-published-poster", "resume-existing-record"])
        self.assertEqual(
            sorted(path.name for path in out_dir.iterdir()),
            ["stills", "stills-index.json"])
        self.assertEqual(
            sorted(path.name for path in (out_dir / "stills").iterdir()),
            [existing.name])

    def test_refresh_measures_and_writes_atomic_index(self) -> None:
        catalog_path = self.catalog([
            raw_item(), raw_item(id=102, slug="no-poster", yoast_head_json={})])
        out_dir = self.root / "out"
        row = wps.normalize_row(
            wps.SITES[DL], raw_item(),
            {"categories": {"3": {"name": "Awards", "slug": "awards"}},
             "tags": {"9": {"name": "3d", "slug": "3d"},
                      "10": {"name": "typography", "slug": "typography"}},
             "aspect_ratio": {"12": {"name": "16:9", "slug": "16-9"}},
             "format": {"7": {"name": "Short", "slug": "short"}}})
        existing = wps.record_path(out_dir, row)
        acq.write_json_atomic(existing, self.record(row, luma=0.1))
        fresh = self.record(row, luma=0.8, hue="red")

        with patch.object(wps, "collect_still_one",
                          return_value=fresh) as collect:
            code = wps.run_stills(
                DL, catalog_path, out_dir=out_dir, limit=0, resume=False,
                delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 0)
        collect.assert_called_once()
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 1, "failed": 0})
        self.assertEqual(index["records"][0]["meanDisplayLumaProxy"], 0.8)
        self.assertEqual(index["records"][0]["dominantHueFamily"], "red")
        self.assertEqual(
            sorted(path.name for path in out_dir.iterdir()),
            ["stills", "stills-index.json"])
        # No staging files survive an atomic index/record write.
        self.assertEqual(list(out_dir.rglob("*.tmp")), [])

    def test_limit_zero_terminates_cleanly_on_complete_run(self) -> None:
        catalog_path = self.catalog([raw_item()])
        out_dir = self.root / "out"
        row = wps.normalize_row(
            wps.SITES[DL], raw_item(),
            {"categories": {"3": {"name": "Awards", "slug": "awards"}},
             "tags": {"9": {"name": "3d", "slug": "3d"},
                      "10": {"name": "typography", "slug": "typography"}},
             "aspect_ratio": {"12": {"name": "16:9", "slug": "16-9"}},
             "format": {"7": {"name": "Short", "slug": "short"}}})
        acq.write_json_atomic(wps.record_path(out_dir, row), self.record(row))

        with patch.object(wps, "collect_still_one") as collect:
            code = wps.run_stills(
                DL, catalog_path, out_dir=out_dir, limit=0, resume=True,
                delay_seconds=0, log=lambda _: None)
            second = wps.run_stills(
                DL, catalog_path, out_dir=out_dir, limit=0, resume=True,
                delay_seconds=0, log=lambda _: None)

        self.assertEqual((code, second), (0, 0))
        collect.assert_not_called()
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 1, "failed": 0})

    def test_limit_counts_only_pending_rows(self) -> None:
        catalog_path = self.catalog([
            raw_item(id=1, slug="one"),
            raw_item(id=2, slug="two"),
            raw_item(id=3, slug="three"),
        ])
        out_dir = self.root / "out"
        rows = [
            wps.normalize_row(
                wps.SITES[DL], raw_item(id=i, slug=slug), {})
            for i, slug in ((1, "one"), (2, "two"), (3, "three"))
        ]
        records = {wps.record_stem(row): self.record(row) for row in rows}

        def fake_collect(site_key, row, out_dir, **kwargs):
            return records[wps.record_stem(row)]

        with patch.object(wps, "collect_still_one",
                          side_effect=fake_collect) as collect:
            code = wps.run_stills(
                DL, catalog_path, out_dir=out_dir, limit=2, resume=True,
                delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 0)
        self.assertEqual(collect.call_count, 2)
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 2, "skipped": 0, "failed": 0})

    def test_missing_poster_is_skipped_with_an_explicit_reason(self) -> None:
        catalog_path = self.catalog([
            raw_item(id=7, slug="no-poster", yoast_head_json={})])
        out_dir = self.root / "out"
        with patch.object(wps, "collect_still_one") as collect:
            code = wps.run_stills(
                DL, catalog_path, out_dir=out_dir, limit=0, resume=True,
                delay_seconds=0, log=lambda _: None)
        self.assertEqual(code, 0)
        collect.assert_not_called()
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["skips"][0]["reason"], "no-published-poster")
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 1, "failed": 0})

    def test_jobs_above_two_and_negative_limit_are_refused(self) -> None:
        catalog_path = self.catalog([raw_item()])
        with self.assertRaises(ValueError):
            wps.run_stills(DL, catalog_path, out_dir=self.root / "o", jobs=3,
                           log=lambda _: None)
        with self.assertRaises(ValueError):
            wps.run_stills(DL, catalog_path, out_dir=self.root / "o", limit=-1,
                           log=lambda _: None)

    def test_collect_still_one_deletes_image_and_retains_only_numbers(self) -> None:
        row = wps.normalize_row(
            wps.SITES[DL], raw_item(),
            {"categories": {"3": {"name": "Awards", "slug": "awards"}},
             "tags": {"9": {"name": "3d", "slug": "3d"},
                      "10": {"name": "typography", "slug": "typography"}},
             "aspect_ratio": {"12": {"name": "16:9", "slug": "16-9"}},
             "format": {"7": {"name": "Short", "slug": "short"}}})
        out_dir = self.root / "out"
        created: list[Path] = []

        def fake_download(url: str, target: Path, **kwargs: object) -> Path:
            created.append(target)
            target.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")
            return target

        measured = {
            "imageWidth": 1280, "imageHeight": 720, "imageCodec": "mjpeg",
            "metrics": {
                "meanDisplayLumaProxy": 0.4,
                "meanSaturationProxy": 0.3,
                "dominantHueFamily": "blue",
                "edgeDensityProxy": 0.07,
                "lumaHistogram": [0.1, 0.2, 0.3, 0.2, 0.2],
            },
        }
        with patch.object(wps, "download_http", side_effect=fake_download), \
                patch.object(wps, "measure_still", return_value=measured):
            record = wps.collect_still_one(DL, row, out_dir)

        self.assertEqual(record["evidenceStatus"],
                         "single-published-still-metrics-not-video-measurement")
        self.assertFalse(record["coverage"]["isSourceVideoFrame"])
        self.assertEqual(record["acquisition"]["method"], "poster-still-http")
        self.assertFalse(record["acquisition"]["imageRetained"])
        self.assertIn("no motion, cut, pacing, timing, sequence, or "
                      "edit-rhythm", " ".join(record["limits"]))
        self.assertTrue(created)
        for target in created:
            self.assertFalse(target.exists())
        self.assertEqual(list(out_dir.rglob("*.jpg")), [])
        self.assertEqual(list(out_dir.rglob("*.jpeg")), [])
        saved = wps.record_path(out_dir, row)
        self.assertTrue(saved.is_file())
        self.assertEqual(
            saved.parent.name, "stills")

    def test_collect_still_one_rejects_a_wrong_host_before_download(self) -> None:
        row = wps.normalize_row(
            wps.SITES[DL], raw_item(yoast_head_json={"og_image": [{
                "url": "https://evil.example/poster.jpg",
                "width": 10, "height": 10}]}), {})
        out_dir = self.root / "out"
        with patch.object(wps, "download_http") as download:
            with self.assertRaises(ValueError):
                wps.collect_still_one(DL, row, out_dir)
        download.assert_not_called()
        self.assertFalse((out_dir / "stills").exists())


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def build_out_dir(self, *, top_catalog: int = 3) -> Path:
        out_dir = self.root / "out"
        cache = {
            "categories": {"3": {"name": "Awards", "slug": "awards"}},
            "tags": {"9": {"name": "3d", "slug": "3d"},
                     "10": {"name": "typography", "slug": "typography"}},
            "aspect_ratio": {"12": {"name": "16:9", "slug": "16-9"}},
            "format": {"7": {"name": "Short", "slug": "short"}},
        }
        items = [
            raw_item(id=1, slug="one", categories=[3], tags=[9]),
            raw_item(id=2, slug="two", categories=[3], tags=[10]),
            raw_item(id=3, slug="three", categories=[3], tags=[9, 10]),
        ][:top_catalog]
        rows = [wps.normalize_row(wps.SITES[DL], item, cache) for item in items]
        for row, luma, hue in zip(rows, (0.2, 0.6, 0.4), ("red", "blue", "green")):
            record = wps.build_still_record(DL, row, still={
                "imageUrl": row["posterUrl"],
                "imageSha256": "a" * 64,
                "imageFormat": "jpg",
                "imageBytes": 1000 + row["id"],
                "imageWidth": 1280,
                "imageHeight": 720,
                "metrics": {
                    "meanDisplayLumaProxy": luma,
                    "meanSaturationProxy": 0.3,
                    "dominantHueFamily": hue,
                    "edgeDensityProxy": 0.07,
                    "lumaHistogram": [0.1, 0.2, 0.3, 0.2, 0.2],
                },
            }, generated_at=f"2026-01-0{row['id']}T00:00:00Z")
            acq.write_json_atomic(wps.record_path(out_dir, row), record)
        catalog = wps.build_catalog(
            DL, rows, meta={"reportedTotal": len(rows), "pagesFetched": 1,
                            "termCache": cache, "termErrors": {}},
            generated_at="2026-01-01T00:00:00Z")
        acq.write_json_atomic(out_dir / "catalog.json", catalog)
        return out_dir

    def test_report_is_deterministic_and_still_only(self) -> None:
        out_dir = self.build_out_dir()
        code = wps.run_report(DL, out_dir, top=10, log=lambda _: None)
        self.assertEqual(code, 0)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        aggregate_bytes = (out_dir / "aggregate.json").read_bytes()
        first_report = report.encode()

        wps.run_report(DL, out_dir, top=10, log=lambda _: None)
        self.assertEqual((out_dir / "report.md").read_bytes(), first_report)
        self.assertEqual((out_dir / "aggregate.json").read_bytes(), aggregate_bytes)

        aggregate = json.loads(aggregate_bytes)
        self.assertEqual(aggregate["schemaVersion"],
                         "kumiki.directorslibrary-aggregate.v1")
        self.assertEqual(aggregate["evidence"], "still-only")
        self.assertEqual(aggregate["counts"]["stillMeasured"], 3)
        self.assertEqual(aggregate["counts"]["videoMeasured"], 0)
        self.assertEqual(aggregate["generatedAt"], "2026-01-03T00:00:00Z")
        self.assertEqual(aggregate["distributions"]["meanDisplayLuma"],
                         {"n": 3, "min": 0.2, "median": 0.4, "max": 0.6})
        self.assertEqual(aggregate["byTerm"]["categories"][0]["name"], "Awards")
        self.assertEqual(aggregate["byTerm"]["categories"][0]["records"], 3)
        self.assertIn("still-only", report.lower())
        self.assertIn("Why there is no motion evidence", report)
        self.assertIn("Vimeo/YouTube", report)
        self.assertIn("is not a video frame", report)
        self.assertIn("| one |", report)
        self.assertIn("| 0.2000 |", report)
        self.assertIn("## Explicit non-claims", report)

    def test_top_truncates_the_table_but_not_the_aggregate(self) -> None:
        out_dir = self.build_out_dir()
        wps.run_report(DL, out_dir, top=1, log=lambda _: None)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        table = report.split("## Measured stills", 1)[1].split(
            "## Distributions by term", 1)[0]
        data_rows = [line for line in table.splitlines()
                     if line.startswith("| ")
                     and not line.startswith("| post_id |")
                     and not line.startswith("| --- |")]
        self.assertEqual(len(data_rows), 1)
        self.assertEqual(len(aggregate["stills"]), 3)
        self.assertIn("`--top 1` applied", report)

    def test_empty_report_writes_a_valid_skeleton(self) -> None:
        out_dir = self.root / "empty"
        code = wps.run_report(DL, out_dir, log=lambda _: None)
        self.assertEqual(code, 0)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        self.assertEqual(aggregate["counts"]["stillMeasured"], 0)
        self.assertEqual(aggregate["stills"], [])
        self.assertIn("0 still-measured record(s)", report)
        self.assertIn("No term-bearing still records.", report)

    def test_malformed_records_are_listed_and_do_not_stop_the_report(self) -> None:
        out_dir = self.build_out_dir(top_catalog=1)
        (out_dir / "stills" / "broken.json").write_text(
            "{not json", encoding="utf-8")
        acq.write_json_atomic(
            out_dir / "stills" / "wrong-schema.json",
            {"schemaVersion": "kumiki.other.v1"})
        wps.run_report(DL, out_dir, log=lambda _: None)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["counts"]["stillMeasured"], 1)
        self.assertEqual(aggregate["counts"]["unreadable"], 2)
        self.assertEqual(
            sorted(item["file"] for item in aggregate["unreadableRecords"]),
            ["stills/broken.json", "stills/wrong-schema.json"])

    def test_report_reads_stash_schema_and_caveat(self) -> None:
        out_dir = self.root / "stash"
        cache = {"categories": {"5": {"name": "Campaigns", "slug": "campaigns"}}}
        row = wps.normalize_row(wps.SITES[STASH], stash_item(), cache)
        record = wps.build_still_record(STASH, row, still={
            "imageUrl": row["posterUrl"], "imageSha256": "b" * 64,
            "imageFormat": "png", "imageBytes": 900, "imageWidth": 1200,
            "imageHeight": 630,
            "metrics": {"meanDisplayLumaProxy": 0.5,
                        "meanSaturationProxy": 0.1,
                        "dominantHueFamily": "neutral",
                        "edgeDensityProxy": 0.02,
                        "lumaHistogram": [0.2, 0.2, 0.2, 0.2, 0.2]}},
            generated_at="2026-02-01T00:00:00Z")
        acq.write_json_atomic(wps.record_path(out_dir, row), record)
        catalog = wps.build_catalog(
            STASH, [row], meta={"reportedTotal": 1, "pagesFetched": 1,
                                "termCache": cache, "termErrors": {}},
            generated_at="2026-02-01T00:00:00Z")
        acq.write_json_atomic(out_dir / "catalog.json", catalog)

        wps.run_report(STASH, out_dir, log=lambda _: None)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        self.assertEqual(aggregate["schemaVersion"],
                         "kumiki.stash-aggregate.v1")
        self.assertIn("magazine feed", report)
        self.assertIn("image galleries", report)


class EmbedExtractionTests(unittest.TestCase):
    """Article HTML -> first YouTube embed, with Vimeo/no-embed skips."""

    def row(self, link: str = "https://directorslibrary.com/video/demo-video/"):
        return wps.normalize_row(
            wps.SITES[DL], raw_item(link=link), {})

    def test_iframe_embed_is_extracted_and_canonicalised(self) -> None:
        page = (
            '<html><body><iframe src="https://player.vimeo.com/video/1">'
            '</iframe><iframe src="https://www.youtube.com/embed/abcdefghijk'
            '?feature=oembed"></iframe></body></html>')
        self.assertEqual(wps.find_youtube_id(page), "abcdefghijk")
        url = wps.youtube_url_for_row(
            wps.SITES[DL], self.row(), fetch=lambda _: page)
        self.assertEqual(url, "https://www.youtube.com/watch?v=abcdefghijk")

    def test_jsonld_embed_is_the_fallback(self) -> None:
        # Unicode-escaped solidus keeps the direct scan from matching; only
        # json.loads -> embedUrl reveals the URL.
        page = (
            '<html><head><script type="application/ld+json">'
            '{"@type": "VideoObject", "embedUrl": '
            '"https:\\u002F\\u002Fwww.youtube.com\\u002Fembed\\u002Fzyxwvutsrqp'
            '?feature=oembed"}'
            "</script></head><body></body></html>")
        self.assertIsNone(
            wps._youtube_id_in_text(wps._normalise_markup(page)))
        self.assertEqual(wps.find_youtube_id(page), "zyxwvutsrqp")
        self.assertEqual(
            wps.youtube_url_for_row(
                wps.SITES[DL], self.row(), fetch=lambda _: page),
            "https://www.youtube.com/watch?v=zyxwvutsrqp")

    def test_watch_shorts_and_short_link_shapes(self) -> None:
        for url, expected in (
                ("https://www.youtube.com/watch?v=abcdefghijk&list=x",
                 "abcdefghijk"),
                ("https://m.youtube.com/shorts/ABCDEFGHIJK", "ABCDEFGHIJK"),
                ("https://youtu.be/12345678901", "12345678901")):
            with self.subTest(url=url):
                self.assertEqual(
                    wps.find_youtube_id(f'<a href="{url}">x</a>'), expected)

    def test_vimeo_only_is_an_explicit_skip(self) -> None:
        page = ('<iframe src="https://player.vimeo.com/video/98765">'
                "</iframe>")
        with self.assertRaises(wps.VideoSkip) as raised:
            wps.youtube_url_for_row(
                wps.SITES[DL], self.row(), fetch=lambda _: page)
        self.assertEqual(raised.exception.reason, "unsupported-vimeo")

    def test_no_embed_is_an_explicit_skip(self) -> None:
        with self.assertRaises(wps.VideoSkip) as raised:
            wps.youtube_url_for_row(
                wps.SITES[DL], self.row(), fetch=lambda _: "<p>no video</p>")
        self.assertEqual(raised.exception.reason, "no-embed-found")

    def test_article_403_is_a_site_refusal(self) -> None:
        def refuse(url: str) -> str:
            raise HTTPError(url, 403, "Forbidden", None, io.BytesIO(b""))

        with self.assertRaises(wps.ArticleRefused):
            wps.youtube_url_for_row(
                wps.SITES[DL], self.row(), fetch=refuse)

    def test_article_url_off_host_is_a_skip_before_fetch(self) -> None:
        called: list[str] = []

        def fetch(url: str) -> str:
            called.append(url)
            return ""

        row = self.row(link="https://evil.example/video/demo/")
        with self.assertRaises(wps.VideoSkip) as raised:
            wps.youtube_url_for_row(wps.SITES[DL], row, fetch=fetch)
        self.assertEqual(raised.exception.reason, "article-url-not-allowlisted")
        self.assertEqual(called, [])


def synthetic_video_probe(
    *, cuts: int = 2, luma: float = 0.3, saturation: float = 0.2,
    delta: float = 0.01,
) -> dict:
    return {
        "sampledWindowSummary": {
            "cutCandidateCountBetweenFirstAndLastSample": cuts,
            "meanSampledDisplayLumaProxy": luma,
            "meanSampledSaturationProxy": saturation,
        },
        "sampledFrames": [{}, {}],
        "sampledFramePairs": [
            {"meanAbsoluteDisplayRgbDeltaPerSecond": delta}],
    }


def synthetic_source(*, duration: float = 100.0) -> dict:
    return {
        "mediaSha256": "d" * 64,
        "sizeBytes": 2_000_000,
        "durationSeconds": duration,
        "resolution": [1280, 720],
        "frameRate": 25.0,
        "sourceTimebase": "1/25",
        "container": "mp4",
        "videoCodec": "h264",
        "audioCodec": "aac",
        "hasAudio": True,
    }


def build_video_record_for(
    row: dict, *, luma: float = 0.3, cuts: int = 2,
    generated_at: str = "2026-01-05T00:00:00Z",
) -> dict:
    return wps.build_video_record(
        DL, row, source=synthetic_source(),
        coverage={
            "windowsMeasured": 1, "windowSeconds": 10, "sampledSeconds": 10.0,
            "fractionOfRuntime": 0.1, "fullRuntimeMeasured": False,
            "note": "synthetic test window"},
        windows=[{
            "startSeconds": 0, "endSeconds": 10,
            "probe": synthetic_video_probe(cuts=cuts, luma=luma)}],
        method="ytdlp-merge",
        video_url="https://www.youtube.com/watch?v=abcdefghijk",
        generated_at=generated_at)


class CollectLaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def catalog(self, items: list[dict], *, site_key: str = DL) -> Path:
        cache = {
            "categories": {"3": {"name": "Awards", "slug": "awards"}},
            "tags": {"9": {"name": "3d", "slug": "3d"}},
        }
        rows = [wps.normalize_row(wps.SITES[site_key], item, cache)
                for item in items]
        catalog = wps.build_catalog(
            site_key, rows, meta={
                "reportedTotal": len(rows), "pagesFetched": 1,
                "termCache": cache, "termErrors": {}},
            generated_at="2026-01-01T00:00:00Z")
        path = self.root / "catalog.json"
        acq.write_json_atomic(path, catalog)
        return path

    def row(self, item: dict, site_key: str = DL) -> dict:
        return wps.normalize_row(wps.SITES[site_key], item, {})

    def test_acknowledgement_gate_refuses_without_attestation(self) -> None:
        catalog = self.catalog([raw_item()])
        with self.assertRaises(ValueError):
            wps.run_collect(
                DL, catalog, out_dir=self.root / "out",
                acknowledge_rights=False, delay_seconds=0, log=lambda _: None)

    def test_jobs_above_two_and_bad_budgets_are_refused(self) -> None:
        catalog = self.catalog([raw_item()])
        with self.assertRaises(ValueError):
            wps.run_collect(
                DL, catalog, out_dir=self.root / "o", jobs=3,
                acknowledge_rights=True, log=lambda _: None)
        with self.assertRaises(ValueError):
            wps.run_collect(
                DL, catalog, out_dir=self.root / "o", max_file_bytes=0,
                acknowledge_rights=True, log=lambda _: None)
        with self.assertRaises(ValueError):
            wps.run_collect(
                DL, catalog, out_dir=self.root / "o", window_seconds=31,
                acknowledge_rights=True, log=lambda _: None)

    def test_stash_every_row_is_refused_without_attempting(self) -> None:
        catalog = self.catalog(
            [stash_item(id=1, slug="one"), stash_item(id=2, slug="two")],
            site_key=STASH)
        out_dir = self.root / "out"
        with patch.object(wps, "collect_video_one") as collect:
            code = wps.run_collect(
                STASH, catalog, out_dir=out_dir, acknowledge_rights=True,
                delay_seconds=0, log=lambda _: None)
        self.assertEqual(code, 0)
        collect.assert_not_called()
        index = json.loads(
            (out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schemaVersion"], "kumiki.stash-index.v1")
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 2, "failed": 0})
        self.assertEqual(
            {row["reason"] for row in index["skips"]},
            {"site-has-no-downloadable-rendition"})
        self.assertEqual(list((out_dir / "videos").glob("*.json")), [])

    def test_resume_leaves_existing_video_record_untouched(self) -> None:
        catalog = self.catalog([raw_item()])
        out_dir = self.root / "out"
        row = self.row(raw_item())
        existing = wps.video_record_path(out_dir, row)
        acq.write_json_atomic(existing, build_video_record_for(row))
        before = existing.read_bytes()
        before_mtime = existing.stat().st_mtime_ns

        with patch.object(wps, "collect_video_one") as collect:
            code = wps.run_collect(
                DL, catalog, out_dir=out_dir, resume=True,
                acknowledge_rights=True, delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 0)
        collect.assert_not_called()
        self.assertEqual(existing.read_bytes(), before)
        self.assertEqual(existing.stat().st_mtime_ns, before_mtime)
        index = json.loads(
            (out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schemaVersion"],
                         "kumiki.directorslibrary-index.v1")
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 1, "failed": 0})
        self.assertEqual(index["skips"][0]["reason"],
                         "resume-existing-record")

    def test_refusal_is_a_skip_and_transient_is_a_failure_without_retry(self) -> None:
        catalog = self.catalog([
            raw_item(id=1, slug="refused"),
            raw_item(id=2, slug="transient"),
        ])
        out_dir = self.root / "out"
        calls: list[str] = []

        def fake_collect(site_key, row, out_dir, **kwargs):
            calls.append(row["slug"])
            if row["slug"] == "refused":
                raise acq.YtDlpRefusedError("provider refused")
            raise acq.YtDlpError("network wobble")

        with patch.object(wps, "collect_video_one", side_effect=fake_collect):
            code = wps.run_collect(
                DL, catalog, out_dir=out_dir, acknowledge_rights=True,
                delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 1)
        self.assertEqual(sorted(calls), ["refused", "transient"])
        index = json.loads(
            (out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual([row["reason"] for row in index["skips"]],
                         ["provider-refused"])
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 1, "failed": 1})
        self.assertTrue(index["failures"][0]["reason"].startswith("transient"))

    def test_site_refusal_is_a_skip_not_a_failure(self) -> None:
        catalog = self.catalog([raw_item()])
        out_dir = self.root / "out"

        def fake_collect(site_key, row, out_dir, **kwargs):
            raise wps.ArticleRefused("article page refused (HTTP 403)")

        with patch.object(wps, "collect_video_one", side_effect=fake_collect):
            code = wps.run_collect(
                DL, catalog, out_dir=out_dir, acknowledge_rights=True,
                delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 1)
        index = json.loads(
            (out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["skips"][0]["reason"], "site-refused")
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 1, "failed": 0})

    def test_limit_counts_only_attempted_rows(self) -> None:
        catalog = self.catalog([
            raw_item(id=1, slug="one"),
            raw_item(id=2, slug="two"),
            raw_item(id=3, slug="three"),
        ])
        out_dir = self.root / "out"
        resumed = self.row(raw_item(id=3, slug="three"))
        acq.write_json_atomic(
            wps.video_record_path(out_dir, resumed),
            build_video_record_for(resumed))

        with patch.object(
                wps, "collect_video_one",
                side_effect=lambda site_key, row, out_dir, **kw:
                    build_video_record_for(row)) as collect:
            wps.run_collect(
                DL, catalog, out_dir=out_dir, limit=2, acknowledge_rights=True,
                delay_seconds=0, log=lambda _: None)

        self.assertEqual(collect.call_count, 2)
        index = json.loads(
            (out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 3, "skipped": 1, "failed": 0})

    def test_collect_video_one_deletes_media_and_writes_video_schema(self) -> None:
        row = self.row(raw_item())
        out_dir = self.root / "out"
        created: list[Path] = []
        page = ('<iframe src="https://www.youtube.com/embed/abcdefghijk'
                '?feature=oembed"></iframe>')

        def fake_download(url, provider, directory, **kwargs):
            target = Path(directory) / "source.mp4"
            target.write_bytes(b"\x00" * 32)
            created.append(target)
            return target, "ytdlp-merge"

        coverage = {
            "windowsMeasured": 1, "windowSeconds": 10, "sampledSeconds": 10.0,
            "fractionOfRuntime": 0.1, "fullRuntimeMeasured": False,
            "note": "synthetic"}
        windows = [{"startSeconds": 0, "endSeconds": 10,
                    "probe": synthetic_video_probe()}]
        with patch.object(wps, "download_media", side_effect=fake_download), \
                patch.object(wps, "source_metadata",
                             return_value=synthetic_source()), \
                patch.object(wps, "measure_windows",
                             return_value=(coverage, windows)):
            record = wps.collect_video_one(
                DL, row, out_dir, article_fetch=lambda _: page)

        self.assertTrue(created and all(not path.exists() for path in created))
        self.assertEqual(list(out_dir.rglob("*.mp4")), [])
        saved = wps.video_record_path(out_dir, row)
        self.assertTrue(saved.is_file())
        self.assertEqual(saved.parent.name, "videos")
        self.assertEqual(record["schemaVersion"],
                         "kumiki.directorslibrary-video-evidence.v1")

    def test_video_record_shape_and_labels(self) -> None:
        row = self.row(raw_item())
        record = build_video_record_for(row, luma=0.3, cuts=2)
        self.assertEqual(record["schemaVersion"],
                         "kumiki.directorslibrary-video-evidence.v1")
        self.assertEqual(record["site"], DL)
        self.assertEqual(record["provider"], "youtube")
        self.assertEqual(record["videoUrl"],
                         "https://www.youtube.com/watch?v=abcdefghijk")
        self.assertEqual(record["downloadMethod"], "ytdlp-merge")
        self.assertFalse(record["mediaRetained"])
        self.assertFalse(record["acquisition"]["mediaRetained"])
        self.assertEqual(record["acquisition"]["provider"], "youtube")
        self.assertIn("platform-encoded YouTube rendition",
                      record["renditionNote"])
        self.assertEqual(record["evidenceStatus"],
                         "sampled-original-source-pts-metrics-not-expert-reviewed")
        self.assertTrue(any("delivered master" in limit
                            for limit in record["limits"]))
        self.assertEqual(record["summary"]["cutCandidates"], 2)


class VideoReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def build_out_dir(self) -> Path:
        out_dir = self.root / "out"
        cache = {
            "categories": {"3": {"name": "Awards", "slug": "awards"}},
            "tags": {"9": {"name": "3d", "slug": "3d"},
                     "10": {"name": "typography", "slug": "typography"}},
        }
        items = [
            raw_item(id=1, slug="one", categories=[3], tags=[9]),
            raw_item(id=2, slug="two", categories=[3], tags=[10]),
            raw_item(id=3, slug="three", categories=[3], tags=[9, 10]),
        ]
        rows = [wps.normalize_row(wps.SITES[DL], item, cache) for item in items]
        for row, luma, hue in zip(rows, (0.2, 0.6, 0.4),
                                  ("red", "blue", "green")):
            record = wps.build_still_record(DL, row, still={
                "imageUrl": row["posterUrl"],
                "imageSha256": "a" * 64,
                "imageFormat": "jpg",
                "imageBytes": 1000 + row["id"],
                "imageWidth": 1280,
                "imageHeight": 720,
                "metrics": {
                    "meanDisplayLumaProxy": luma,
                    "meanSaturationProxy": 0.3,
                    "dominantHueFamily": hue,
                    "edgeDensityProxy": 0.07,
                    "lumaHistogram": [0.1, 0.2, 0.3, 0.2, 0.2],
                },
            }, generated_at=f"2026-01-0{row['id']}T00:00:00Z")
            acq.write_json_atomic(wps.record_path(out_dir, row), record)
        for row, luma, cuts in ((rows[0], 0.9, 1), (rows[1], 0.7, 3)):
            acq.write_json_atomic(
                wps.video_record_path(out_dir, row),
                build_video_record_for(
                    row, luma=luma, cuts=cuts,
                    generated_at="2026-01-09T00:00:00Z"))
        catalog = wps.build_catalog(
            DL, rows, meta={"reportedTotal": len(rows), "pagesFetched": 1,
                            "termCache": cache, "termErrors": {}},
            generated_at="2026-01-01T00:00:00Z")
        acq.write_json_atomic(out_dir / "catalog.json", catalog)
        return out_dir

    def test_report_separates_video_still_and_still_only_and_is_deterministic(self) -> None:
        out_dir = self.build_out_dir()
        wps.run_report(DL, out_dir, top=10, log=lambda _: None)
        first_report = (out_dir / "report.md").read_bytes()
        first_aggregate = (out_dir / "aggregate.json").read_bytes()

        wps.run_report(DL, out_dir, top=10, log=lambda _: None)
        self.assertEqual((out_dir / "report.md").read_bytes(), first_report)
        self.assertEqual((out_dir / "aggregate.json").read_bytes(),
                         first_aggregate)

        aggregate = json.loads(first_aggregate)
        counts = aggregate["counts"]
        self.assertEqual(aggregate["evidence"],
                         "video-measured+still-measured")
        self.assertEqual(counts["videoMeasured"], 2)
        self.assertEqual(counts["stillMeasured"], 3)
        self.assertEqual(counts["stillOnly"], 1)
        self.assertEqual(counts["videoByProvider"], {"youtube": 2})
        # Still-only evidence stays out of the video aggregates.
        video_luma = aggregate["videoAggregates"]["distributions"][
            "meanDisplayLuma"]
        self.assertEqual(video_luma, {"n": 2, "min": 0.7, "median": 0.8,
                                      "max": 0.9})
        self.assertEqual(
            aggregate["distributions"]["meanDisplayLuma"],
            {"n": 3, "min": 0.2, "median": 0.4, "max": 0.6})
        self.assertEqual(len(aggregate["videos"]), 2)
        self.assertEqual(len(aggregate["stills"]), 3)
        report = first_report.decode("utf-8")
        self.assertIn("## Per-video analysis", report)
        self.assertIn("## Aggregates (video-measured records only)", report)
        self.assertIn("still-only rows, never enter", report)
        self.assertIn("platform-encoded YouTube rendition", report)
        self.assertIn("## Measured stills", report)


class SchemaAndConfigTests(unittest.TestCase):
    def test_unknown_site_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            wps.site_config("nope")

    def test_each_site_has_its_own_schema_prefix(self) -> None:
        for site_key in (DL, STASH):
            site = wps.site_config(site_key)
            self.assertEqual(site["schemaPrefix"], site_key)
            self.assertEqual(wps.schema_name(site, "catalog"),
                             f"kumiki.{site_key}-catalog.v1")
            self.assertEqual(wps.schema_name(site, "still-evidence"),
                             f"kumiki.{site_key}-still-evidence.v1")
            self.assertEqual(wps.schema_name(site, "stills-index"),
                             f"kumiki.{site_key}-stills-index.v1")
            self.assertEqual(wps.schema_name(site, "aggregate"),
                             f"kumiki.{site_key}-aggregate.v1")

    def test_cli_parser_requires_a_site(self) -> None:
        parser = wps.build_parser()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["catalog", "--out", "/tmp/x.json"])

    def test_collect_cli_defaults_and_surface(self) -> None:
        parser = wps.build_parser()
        args = parser.parse_args([
            "collect", "--site", DL, "--catalog", "c.json",
            "--out-dir", "out", "--acknowledge-rights", "--limit", "2"])
        self.assertEqual(args.limit, 2)
        self.assertEqual(args.window_count, 4)
        self.assertEqual(args.window_seconds, 10)
        self.assertEqual(args.max_duration_seconds, 600.0)
        self.assertEqual(args.max_file_bytes, 250 * 1024 * 1024)
        self.assertEqual(args.delay_seconds, 1.4)
        self.assertEqual(args.jobs, 1)
        self.assertTrue(args.resume)
        self.assertTrue(args.acknowledge_rights)
        self.assertEqual(args.yt_dlp, "yt-dlp")
        self.assertEqual(wps.parse_byte_size("250MiB"), 250 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
