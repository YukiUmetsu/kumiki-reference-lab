"""Offline tests for the Promonews catalogue + poster-stills research adapter."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from kumiki_reference_lab import acquisition as acq
from scripts import research_promonews as pnm

ADMIN = "https://admin.promonews.tv"
THUMB = f"{ADMIN}/sites/default/files/styles/thumb/public/poster.png?itok=abc123"
FULL = f"{ADMIN}/sites/default/files/poster-full.png"
ORIGINAL = f"{ADMIN}/sites/default/files/poster-original.png"
CREATED = 1714953600  # 2024-05-06T00:00:00Z
VALID_VIDEO_URL = "https://www.youtube.com/watch?v=ZfJOq_B_XBM"
VALID_VIDEO_SHORT = "https://youtu.be/ZfJOq_B_XBM"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def raw_source(**overrides: object) -> dict:
    source: dict[str, object] = {
        "nid": 101,
        "uuid": "uuid-101",
        "title": "Demo Film",
        "published": "2024-05-06",
        "featured": True,
        "created": CREATED,
        "changed": CREATED + 60,
        "link": "https://admin.promonews.tv/videos/2024/05/06/demo-film",
        "videos": [{
            "url": "https://www.youtube.com/watch?v=abc123",
            "filemime": "video/youtube",
            "title": "Demo Film",
            "sort": 0,
        }],
        "images": [{
            "info": {"width": 1280, "height": 720},
            "original": ORIGINAL,
            "thumb": THUMB,
            "full": FULL,
        }],
        "body": "<p>ignored</p>",
        "files": [],
        "release_date": "2024-05-01",
        "submitted_release_date": "2024-04-30",
        "countries": [{"name": "United Kingdom", "tid": 1}],
        "credits": [
            {"uid": 1, "pro": 0, "name": "Alice Director",
             "role": "Director", "path": "/credits/1", "sort": 0},
            {"uid": 2, "pro": 0, "name": None,
             "role": "Production Company", "path": "/credits/2", "sort": 1},
        ],
        "categories": [{"name": "Music Videos", "tid": 2}],
        "tags": ["tag-a", "tag-b"],
        "genres": [{"name": "Pop", "tid": 3}],
        "director_notes": "",
    }
    source.update(overrides)
    return source


def row(**overrides: object) -> dict:
    return pnm.normalize_source(raw_source(**overrides))


def youtube_row(**overrides: object) -> dict:
    """A projected row whose embed URL passes the real YouTube allowlist."""
    projected = row(**overrides)
    projected["videoUrl"] = VALID_VIDEO_URL
    return projected


def payload(sources: list[dict], *, total: int | None = None) -> dict:
    return {"hits": {
        "total": len(sources) if total is None else total,
        "hits": [{"_source": source} for source in sources],
    }}


def synthetic_still_record(
    source: dict, *, luma: float = 0.6, hue: str = "blue",
    generated_at: str = "2026-01-02T00:00:00Z",
) -> dict:
    return pnm.build_still_record(source, still={
        "imageUrl": source.get("posterUrl") or THUMB,
        "imageSha256": "b" * 64,
        "imageFormat": "png",
        "imageBytes": 120_000,
        "imageWidth": 1280,
        "imageHeight": 720,
        "metrics": {
            "meanRgb": [0.1, 0.2, 0.3],
            "meanDisplayLumaProxy": luma,
            "displayLumaStdDev": 0.1,
            "meanSaturationProxy": 0.2,
            "shadowPixelFraction": 0.0,
            "brightPixelFraction": 0.0,
            "lumaHistogram": [0.2] * 5,
            "dominantHueFamily": hue,
            "edgeDensityProxy": 0.1,
        },
    }, generated_at=generated_at)


def synthetic_video_record(
    source: dict, *, luma: float = 0.5, cuts: int = 3,
    generated_at: str = "2026-01-02T00:00:00Z",
) -> dict:
    try:
        video_url = pnm.canonical_youtube_url(source.get("videoUrl"))
    except ValueError:
        video_url = VALID_VIDEO_URL
    return pnm.build_video_record(
        source,
        source={
            "mediaSha256": "a" * 64,
            "sizeBytes": 5_000_000,
            "durationSeconds": 120.0,
            "resolution": [1280, 720],
            "frameRate": {"numerator": 25, "denominator": 1},
            "sourceTimebase": None,
            "container": "mp4",
            "videoCodec": "h264",
            "audioCodec": "aac",
            "hasAudio": True,
        },
        coverage={
            "windowsMeasured": 2,
            "windowSeconds": 10,
            "sampledSeconds": 20,
            "fractionOfRuntime": 0.166667,
            "fullRuntimeMeasured": False,
            "note": "evenly spread source-PTS windows, not full-film review",
        },
        windows=[{
            "startSeconds": 0,
            "endSeconds": 10,
            "probe": {
                "sampledWindowSummary": {
                    "cutCandidateCountBetweenFirstAndLastSample": cuts,
                    "meanSampledDisplayLumaProxy": luma,
                    "meanSampledSaturationProxy": 0.2,
                    "cutSeparatedPairs": 2,
                },
                "sampledFrames": [0, 1],
                "sampledFramePairs": [
                    {"meanAbsoluteDisplayRgbDeltaPerSecond": 0.1}],
            },
        }],
        method=acq.METHOD_YTDLP_MERGE,
        video_url=video_url,
        generated_at=generated_at,
    )


class _FakeResponse:
    def __init__(self, body: bytes, url: str) -> None:
        self._body, self._url, self._position = body, url, 0

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk = self._body[self._position:]
            self._position = len(self._body)
            return chunk
        chunk = self._body[self._position:self._position + size]
        self._position += len(chunk)
        return chunk

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


# ---------------------------------------------------------------------------
# minimal DSL
# ---------------------------------------------------------------------------


class SearchBodyTests(unittest.TestCase):
    def test_minimal_dsl_shape(self) -> None:
        body = pnm.search_body(100, 0)
        self.assertEqual(set(body), {"size", "from", "query", "sort"})
        self.assertEqual(body["size"], 100)
        self.assertEqual(body["from"], 0)
        self.assertEqual(body["query"], {"match_all": {}})
        self.assertEqual(body["sort"], [{"created": {"order": "desc"}}])
        # The endpoint 500s on these; they must never be sent.
        self.assertNotIn("track_total_hits", body)
        self.assertNotIn("bool", body)
        self.assertNotIn("term", json.dumps(body))

    def test_shard_query_is_a_bare_range(self) -> None:
        body = pnm.search_body(100, 0, before=1700000000)
        self.assertEqual(body["query"],
                         {"range": {"created": {"lt": 1700000000}}})
        self.assertNotIn("match_all", body["query"])
        self.assertNotIn("bool", body["query"])
        self.assertEqual(body["from"], 0)

    def test_page_size_offset_and_boundary_validation(self) -> None:
        for size in (0, 101):
            with self.subTest(size=size), self.assertRaises(ValueError):
                pnm.search_body(size, 0)
        with self.assertRaises(ValueError):
            pnm.search_body(100, -1)
        with self.assertRaises(ValueError):
            pnm.search_body(100, 0, before=0)


class SearchTransportTests(unittest.TestCase):
    def test_http_500_is_a_query_error_and_is_not_retried(self) -> None:
        error = HTTPError(pnm.ENDPOINT, 500, "Internal Server Error", None, None)
        with patch.object(pnm, "urlopen", side_effect=error) as opener:
            with self.assertRaises(ValueError):
                pnm._post_search(pnm.search_body(100, 0), sleep=lambda _: None)
        self.assertEqual(opener.call_count, 1)

    def test_transport_error_is_retried_then_succeeds(self) -> None:
        body = json.dumps(payload([raw_source()])).encode()
        effect = [URLError("temporary"), _FakeResponse(body, pnm.ENDPOINT)]
        slept: list[float] = []
        with patch.object(pnm, "urlopen", side_effect=effect) as opener:
            result = pnm._post_search(
                pnm.search_body(100, 0), sleep=slept.append)
        self.assertEqual(opener.call_count, 2)
        self.assertEqual(slept, [1])
        self.assertEqual(result["hits"]["hits"][0]["_source"]["nid"], 101)


# ---------------------------------------------------------------------------
# catalogue paging and the result-window shard
# ---------------------------------------------------------------------------


class CatalogPagingTests(unittest.TestCase):
    def test_result_window_shards_on_created_and_never_requests_from_10000(
        self,
    ) -> None:
        def source(nid: int, created: int) -> dict:
            return raw_source(nid=nid, created=created,
                              link=f"https://admin.promonews.tv/videos/x/{nid}")

        pages = {
            (None, 0): payload([source(300, 300), source(200, 200)], total=5),
            (None, 2): payload([source(100, 100), source(90, 90)], total=5),
            (90, 0): payload([source(80, 80)], total=1),
        }
        bodies: list[dict] = []

        def fake_fetch(body: dict) -> dict:
            bodies.append(json.loads(json.dumps(body)))
            if body["from"] >= pnm.RESULT_WINDOW:
                raise AssertionError("from must stay below the result window")
            before = body["query"].get("range", {}).get("created", {}).get("lt")
            return pages[(before, body["from"])]

        logs: list[str] = []
        with patch.object(pnm, "RESULT_WINDOW", 4):
            rows, total, meta = pnm.fetch_catalog(
                page_size=2, delay_seconds=0, fetch=fake_fetch,
                sleep=lambda _s: None, log=logs.append)

        self.assertEqual([row["nid"] for row in rows], [300, 200, 100, 90, 80])
        self.assertEqual(total, 5)
        self.assertEqual(meta["shards"], 1)
        self.assertEqual(meta["boundaries"], [90])
        self.assertTrue(meta["exhausted"])
        self.assertEqual(len(bodies), 3)
        self.assertEqual(bodies[2]["query"],
                         {"range": {"created": {"lt": 90}}})
        self.assertEqual(bodies[2]["from"], 0)
        self.assertTrue(any("created < 90" in line for line in logs))

    def test_shard_triggers_before_from_plus_size_crosses_the_window(self) -> None:
        bodies: list[dict] = []

        def source(nid: int, created: int) -> dict:
            return raw_source(nid=nid, created=created)

        def fake_fetch(body: dict) -> dict:
            bodies.append(dict(body))
            if body["from"] + body["size"] > pnm.RESULT_WINDOW:
                raise AssertionError("from + size crossed the result window")
            start = body["from"]
            return payload([
                source(start + 1, 1000 - start),
                source(start + 2, 999 - start),
                source(start + 3, 998 - start),
                source(start + 4, 997 - start),
            ], total=99)

        with patch.object(pnm, "RESULT_WINDOW", 10):
            rows, _, meta = pnm.fetch_catalog(
                page_size=4, delay_seconds=0, fetch=fake_fetch,
                sleep=lambda _s: None, log=lambda _s: None)

        self.assertTrue(bodies)
        for body in bodies:
            self.assertLessEqual(body["from"] + body["size"],
                                 pnm.RESULT_WINDOW)
        self.assertGreaterEqual(meta["shards"], 1)
        self.assertEqual(len(rows), len({row["nid"] for row in rows}))

    def test_total_is_read_from_the_first_page_only(self) -> None:
        pages = [
            payload([raw_source(nid=1, created=200)], total=17_805),
            payload([], total=0),
        ]

        def fake_fetch(_body: dict) -> dict:
            return pages.pop(0)

        rows, total, _ = pnm.fetch_catalog(
            page_size=1, delay_seconds=0, fetch=fake_fetch,
            sleep=lambda _s: None, log=lambda _s: None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(total, 17_805)

    def test_limit_trims_and_marks_catalogue_incomplete(self) -> None:
        def fake_fetch(body: dict) -> dict:
            start = body["from"]
            return payload([
                raw_source(nid=start + 1, created=1000 - start),
                raw_source(nid=start + 2, created=999 - start),
            ], total=17_805)

        rows, total, _ = pnm.fetch_catalog(
            limit=3, page_size=2, delay_seconds=0, fetch=fake_fetch,
            sleep=lambda _s: None, log=lambda _s: None)
        catalog = pnm.build_catalog(rows, total, limit=3,
                                    generated_at="2026-01-01T00:00:00Z")
        self.assertEqual(len(rows), 3)
        self.assertEqual(total, 17_805)
        self.assertFalse(catalog["counts"]["complete"])
        self.assertEqual(catalog["counts"]["collected"], 3)
        self.assertEqual(catalog["counts"]["reportedTotal"], 17_805)

    def test_limit_zero_makes_no_request(self) -> None:
        def explode(_body: dict) -> dict:
            raise AssertionError("limit=0 must not fetch")

        rows, total, meta = pnm.fetch_catalog(
            limit=0, fetch=explode, sleep=lambda _s: None, log=lambda _s: None)
        self.assertEqual(rows, [])
        self.assertIsNone(total)
        self.assertEqual(meta["pagesFetched"], 0)

    def test_empty_first_page_terminates(self) -> None:
        calls: list[dict] = []

        def fake_fetch(body: dict) -> dict:
            calls.append(body)
            return payload([], total=0)

        rows, total, meta = pnm.fetch_catalog(
            delay_seconds=0, fetch=fake_fetch, sleep=lambda _s: None,
            log=lambda _s: None)
        self.assertEqual(rows, [])
        self.assertEqual(total, 0)
        self.assertEqual(len(calls), 1)
        self.assertTrue(meta["exhausted"])

    def test_short_page_stops_within_the_shard(self) -> None:
        calls: list[dict] = []

        def fake_fetch(body: dict) -> dict:
            calls.append(body)
            return payload([raw_source()], total=5)

        rows, _, meta = pnm.fetch_catalog(
            page_size=2, delay_seconds=0, fetch=fake_fetch,
            sleep=lambda _s: None, log=lambda _s: None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(calls), 1)
        self.assertTrue(meta["exhausted"])


class CatalogCountsTests(unittest.TestCase):
    def test_counts_reconcile_and_rank_genres(self) -> None:
        rows = [
            row(nid=1, genres=[{"name": "Pop", "tid": 1}]),
            row(nid=2, genres=[{"name": "Pop", "tid": 1},
                               {"name": "Rock", "tid": 2}]),
            row(nid=3,
                videos=[{"url": "https://vimeo.com/1", "filemime": "video/vimeo"}],
                genres=[]),
        ]
        catalog = pnm.build_catalog(
            rows, 17_805, generated_at="2026-01-01T00:00:00Z")
        counts = catalog["counts"]
        self.assertEqual(catalog["schemaVersion"], pnm.CATALOG_SCHEMA)
        self.assertEqual(counts["collected"], 3)
        self.assertEqual(counts["reportedTotal"], 17_805)
        self.assertFalse(counts["complete"])
        self.assertEqual(counts["byProvider"], {"vimeo": 1, "youtube": 2})
        self.assertEqual(counts["topGenres"],
                         [{"name": "Pop", "count": 2},
                          {"name": "Rock", "count": 1}])

    def test_complete_catalogue_reconciles_with_hits_total(self) -> None:
        rows = [row(nid=1), row(nid=2)]
        catalog = pnm.build_catalog(rows, 2, generated_at="2026-01-01T00:00:00Z")
        self.assertTrue(catalog["counts"]["complete"])


# ---------------------------------------------------------------------------
# row projection
# ---------------------------------------------------------------------------


class NormalizationTests(unittest.TestCase):
    def test_slim_projection_has_the_documented_keys(self) -> None:
        result = row()
        self.assertEqual(set(result), {
            "nid", "slug", "title", "publishedDate", "createdEpoch",
            "publicUrl", "cmsUrl", "provider", "unsupportedReason",
            "posterUrl", "posterWidth", "posterHeight", "durationSeconds",
            "categories", "genres", "tags", "countries", "credits",
            "videoUrl",
        })
        self.assertEqual(result["nid"], 101)
        self.assertEqual(result["slug"], "demo-film")
        self.assertIsNone(result["durationSeconds"])
        self.assertEqual(result["publishedDate"], "2024-05-06")
        self.assertEqual(result["createdEpoch"], CREATED)
        self.assertEqual(result["categories"], ["Music Videos"])
        self.assertEqual(result["genres"], ["Pop"])
        self.assertEqual(result["tags"], ["tag-a", "tag-b"])
        self.assertEqual(result["countries"], ["United Kingdom"])
        self.assertEqual(result["videoUrl"],
                         "https://www.youtube.com/watch?v=abc123")

    def test_public_and_cms_urls_are_derived_from_the_link(self) -> None:
        result = row()
        self.assertEqual(result["publicUrl"],
                         "https://www.promonews.tv/videos/2024/05/06/demo-film")
        self.assertEqual(result["cmsUrl"],
                         "https://admin.promonews.tv/videos/2024/05/06/demo-film")

    def test_urls_fall_back_to_created_and_title_when_link_is_absent(self) -> None:
        result = row(link=None, title="demo-film")
        self.assertEqual(result["publicUrl"],
                         "https://www.promonews.tv/videos/2024/05/06/demo-film")
        self.assertEqual(result["cmsUrl"],
                         "https://admin.promonews.tv/videos/2024/05/06/demo-film")

    def test_published_date_accepts_epoch_but_not_boolean_flags(self) -> None:
        self.assertEqual(row(published=CREATED)["publishedDate"], "2024-05-06")
        self.assertEqual(
            row(published=str(CREATED))["publishedDate"], "2024-05-06")
        self.assertEqual(
            row(published=True, release_date=CREATED)["publishedDate"],
            "2024-05-06")
        self.assertIsNone(row(published=False, release_date=None,
                              submitted_release_date=None)["publishedDate"])

    def test_credits_keep_roles_and_preserve_nulls(self) -> None:
        result = row(credits=[
            {"name": "Alice", "role": "Director"},
            {"name": None, "role": "Production Company"},
            {"name": "Label Co", "role": None},
            {"name": None, "role": None},
        ])
        self.assertEqual(result["credits"], [
            {"role": "Director", "name": "Alice"},
            {"role": "Production Company", "name": None},
            {"role": None, "name": "Label Co"},
        ])
        self.assertEqual(row(credits=None)["credits"], [])

    def test_missing_nid_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            pnm.normalize_source(raw_source(nid=None))


class ProviderClassificationTests(unittest.TestCase):
    def test_youtube_and_vimeo_from_mime(self) -> None:
        self.assertEqual(row()["provider"], "youtube")
        self.assertEqual(row()["unsupportedReason"], "unsupported-youtube")
        vimeo = row(videos=[{"url": "https://vimeo.com/123",
                             "filemime": "video/vimeo"}])
        self.assertEqual(vimeo["provider"], "vimeo")
        self.assertEqual(vimeo["unsupportedReason"], "unsupported-vimeo")

    def test_host_fallback_when_mime_is_absent(self) -> None:
        self.assertEqual(
            pnm.classify_provider("https://youtu.be/abc"), "youtube")
        self.assertEqual(
            pnm.classify_provider("https://player.vimeo.com/video/1"), "vimeo")
        self.assertEqual(pnm.classify_provider("https://example.test/x"), "other")

    def test_no_video_reference_is_explicit(self) -> None:
        result = row(videos=[])
        self.assertIsNone(result["provider"])
        self.assertIsNone(result["videoUrl"])
        self.assertEqual(result["unsupportedReason"], "no-video-reference")


class PosterPolicyTests(unittest.TestCase):
    def test_itok_query_is_accepted_on_the_admin_host_only(self) -> None:
        self.assertEqual(pnm.policy_image_url(THUMB), THUMB)
        for url in (
                "https://www.promonews.tv/sites/default/files/a.png?itok=abc",
                "https://evil.example/a.png?itok=abc",
                "https://admin.promonews.tv.evil.example/a.png?itok=abc",
                "http://admin.promonews.tv/sites/default/files/a.png?itok=abc",
                "https://admin.promonews.tv/a.png?itok=abc#fragment",
                "",
                None):
            with self.subTest(url=url), self.assertRaises(ValueError):
                pnm.policy_image_url(url)

    def test_poster_prefers_thumb_then_full_then_original(self) -> None:
        self.assertEqual(row()["posterUrl"], THUMB)
        self.assertEqual(row(images=[{
            "info": {"width": 10, "height": 20}, "full": FULL,
            "original": ORIGINAL}])["posterUrl"], FULL)
        self.assertEqual(row(images=[{
            "info": {"width": 10, "height": 20},
            "original": ORIGINAL}])["posterUrl"], ORIGINAL)

    def test_off_host_thumb_falls_back_to_an_allowed_full(self) -> None:
        result = row(images=[{
            "info": {"width": 10, "height": 20},
            "thumb": "https://evil.example/thumb.png?itok=x",
            "full": FULL,
        }])
        self.assertEqual(result["posterUrl"], FULL)

    def test_no_images_yields_null_poster(self) -> None:
        result = row(images=[])
        self.assertIsNone(result["posterUrl"])
        self.assertIsNone(result["posterWidth"])
        self.assertIsNone(result["posterHeight"])


# ---------------------------------------------------------------------------
# stills lane
# ---------------------------------------------------------------------------


class StillsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_catalog(self, rows: list[dict]) -> Path:
        path = self.root / "catalog.json"
        acq.write_json_atomic(path, pnm.build_catalog(
            rows, len(rows), generated_at="2026-01-01T00:00:00Z"))
        return path

    def test_still_record_is_still_only_and_retains_no_image(self) -> None:
        record = synthetic_still_record(row())
        self.assertEqual(record["schemaVersion"], pnm.STILL_SCHEMA)
        self.assertEqual(record["nid"], 101)
        self.assertEqual(record["provider"], "youtube")
        self.assertEqual(record["unsupportedReason"], "unsupported-youtube")
        self.assertIsNone(record["durationSeconds"])
        self.assertFalse(record["coverage"]["isSourceVideoFrame"])
        self.assertEqual(record["acquisition"]["method"], "poster-still-http")
        self.assertFalse(record["acquisition"]["imageRetained"])
        self.assertEqual(record["evidenceStatus"], pnm.STILL_EVIDENCE_STATUS)
        limits = " ".join(record["limits"]).lower()
        self.assertIn("not a video frame", limits)
        self.assertIn("no motion", limits)
        self.assertIn("timing", limits)
        self.assertIn("aesthetic", limits)

    def test_resume_leaves_existing_records_byte_and_mtime_identical(self) -> None:
        source = row()
        catalog_path = self.write_catalog([source])
        out_dir = self.root / "out"
        existing = pnm.record_path(out_dir, source)
        acq.write_json_atomic(existing, synthetic_still_record(source))
        before_bytes = existing.read_bytes()
        before_mtime = existing.stat().st_mtime_ns

        with patch.object(pnm, "collect_still_one") as collect:
            code = pnm.run_stills(catalog_path, out_dir=out_dir, resume=True,
                                  delay_seconds=0, log=lambda _s: None)

        self.assertEqual(code, 0)
        collect.assert_not_called()
        self.assertEqual(existing.read_bytes(), before_bytes)
        self.assertEqual(existing.stat().st_mtime_ns, before_mtime)
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schemaVersion"], pnm.STILLS_INDEX_SCHEMA)
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 1, "failed": 0})
        self.assertEqual(index["skips"][0]["reason"], "resume-existing-record")
        self.assertEqual(index["catalogSha256"], pnm.sha256_file(catalog_path))

    def test_refresh_measures_and_writes_an_atomic_index(self) -> None:
        source = row()
        catalog_path = self.write_catalog([source])
        out_dir = self.root / "out"
        record = synthetic_still_record(source)

        with patch.object(pnm, "collect_still_one",
                          return_value=record) as collect:
            code = pnm.run_stills(catalog_path, out_dir=out_dir, resume=False,
                                  delay_seconds=0, log=lambda _s: None)

        self.assertEqual(code, 0)
        collect.assert_called_once()
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 0, "failed": 0})
        self.assertEqual(index["records"][0]["dominantHueFamily"], "blue")
        self.assertEqual(index["records"][0]["recordPath"],
                         "stills/101-demo-film.json")
        self.assertEqual(sorted(path.name for path in out_dir.iterdir()),
                         ["stills", "stills-index.json"])

    def test_rows_without_a_poster_get_an_explicit_skip_reason(self) -> None:
        source = row(images=[])
        catalog_path = self.write_catalog([source])
        out_dir = self.root / "out"

        with patch.object(pnm, "collect_still_one") as collect:
            code = pnm.run_stills(catalog_path, out_dir=out_dir,
                                  delay_seconds=0, log=lambda _s: None)

        self.assertEqual(code, 0)
        collect.assert_not_called()
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 1, "failed": 0})
        self.assertEqual(index["skips"][0]["reason"], "no-usable-poster")

    def test_limit_zero_measures_all_remaining_and_then_terminates(self) -> None:
        sources = [row(nid=index, title=f"Film {index}")
                   for index in range(1, 4)]
        catalog_path = self.write_catalog(sources)
        out_dir = self.root / "out"

        def fake_collect(source: dict, out: Path, **_options: object) -> dict:
            record = synthetic_still_record(source)
            acq.write_json_atomic(pnm.record_path(out, source), record)
            return record

        with patch.object(pnm, "collect_still_one", side_effect=fake_collect):
            code = pnm.run_stills(catalog_path, out_dir=out_dir, limit=0,
                                  delay_seconds=0, log=lambda _s: None)
        self.assertEqual(code, 0)
        first = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(first["counts"],
                         {"measured": 3, "skipped": 0, "failed": 0})

        # A second limit-0 run finds everything measured and terminates.
        with patch.object(pnm, "collect_still_one") as collect:
            code = pnm.run_stills(catalog_path, out_dir=out_dir, limit=0,
                                  delay_seconds=0, log=lambda _s: None)
        self.assertEqual(code, 0)
        collect.assert_not_called()
        second = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(second["counts"],
                         {"measured": 3, "skipped": 3, "failed": 0})
        self.assertEqual({row["reason"] for row in second["skips"]},
                         {"resume-existing-record"})

    def test_collection_failure_becomes_an_index_failure_row(self) -> None:
        catalog_path = self.write_catalog([row()])
        out_dir = self.root / "out"

        with patch.object(pnm, "collect_still_one",
                          side_effect=ValueError("synthetic failure")):
            code = pnm.run_stills(catalog_path, out_dir=out_dir,
                                  delay_seconds=0, log=lambda _s: None)

        self.assertEqual(code, 1)
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 0, "failed": 1})
        self.assertIn("synthetic failure", index["failures"][0]["reason"])


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_still(self, out_dir: Path, record: dict) -> None:
        acq.write_json_atomic(
            out_dir / "stills" / f"{pnm.record_stem(record)}.json", record)

    def test_empty_state_is_a_valid_still_only_skeleton(self) -> None:
        out_dir = self.root / "out"
        code = pnm.run_report(out_dir, log=lambda _s: None)
        self.assertEqual(code, 0)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["schemaVersion"], pnm.AGGREGATE_SCHEMA)
        self.assertEqual(aggregate["evidence"], "still-only")
        self.assertEqual(aggregate["counts"]["stillMeasured"], 0)
        self.assertEqual(aggregate["stills"], [])
        self.assertIn("Why there is no motion evidence", report)
        self.assertIn("YouTube", report)
        self.assertIn("Vimeo", report)
        self.assertIn("Explicit non-claims", report)
        self.assertIn("still-only", report)
        self.assertEqual(sorted(path.name for path in out_dir.iterdir()),
                         ["aggregate.json", "report.md"])

    def test_report_is_byte_identical_across_runs(self) -> None:
        out_dir = self.root / "out"
        catalog = pnm.build_catalog(
            [row(nid=1), row(nid=2, title="Second Film")], 17_805,
            generated_at="2026-01-01T00:00:00Z")
        acq.write_json_atomic(out_dir / "catalog.json", catalog)
        self.write_still(out_dir, synthetic_still_record(
            row(nid=1), generated_at="2026-01-02T00:00:00Z"))
        self.write_still(out_dir, synthetic_still_record(
            row(nid=2, title="Second Film"), luma=0.3, hue="red",
            generated_at="2026-01-03T00:00:00Z"))

        pnm.run_report(out_dir, top=5, log=lambda _s: None)
        first_report = (out_dir / "report.md").read_bytes()
        first_aggregate = (out_dir / "aggregate.json").read_bytes()
        pnm.run_report(out_dir, top=5, log=lambda _s: None)

        self.assertEqual((out_dir / "report.md").read_bytes(), first_report)
        self.assertEqual(
            (out_dir / "aggregate.json").read_bytes(), first_aggregate)

    def test_provenance_reports_catalog_total_and_provider_split(self) -> None:
        out_dir = self.root / "out"
        sources = [row(nid=1), row(nid=2, videos=[
            {"url": "https://vimeo.com/1", "filemime": "video/vimeo"}])]
        catalog = pnm.build_catalog(
            sources, 17_805, generated_at="2026-01-01T00:00:00Z")
        acq.write_json_atomic(out_dir / "catalog.json", catalog)
        self.write_still(out_dir, synthetic_still_record(sources[0]))
        pnm.run_report(out_dir, log=lambda _s: None)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["counts"]["catalogCollected"], 2)
        self.assertEqual(aggregate["counts"]["catalogReportedTotal"], 17_805)
        self.assertIn("Catalog `hits.total` reported: 17805", report)
        self.assertIn("youtube x 1", report)
        self.assertIn("vimeo x 1", report)

    def test_distributions_by_genre_and_category(self) -> None:
        out_dir = self.root / "out"
        first = synthetic_still_record(
            row(nid=1, genres=[{"name": "Pop", "tid": 1}],
                categories=[{"name": "Music Videos", "tid": 2}]), luma=0.2)
        second = synthetic_still_record(
            row(nid=2, title="Second", genres=[{"name": "Pop", "tid": 1}],
                categories=[{"name": "Commercials", "tid": 3}]), luma=0.8)
        self.write_still(out_dir, first)
        self.write_still(out_dir, second)
        pnm.run_report(out_dir, log=lambda _s: None)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["byGenre"]["Pop"]["records"], 2)
        self.assertEqual(aggregate["byGenre"]["Pop"]["meanDisplayLuma"]["n"], 2)
        self.assertEqual(sorted(aggregate["byCategory"]),
                         ["Commercials", "Music Videos"])
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        self.assertIn("Distributions by genre and category", report)
        self.assertIn("| Pop | 2 |", report)

    def test_unreadable_records_are_listed_and_isolated(self) -> None:
        out_dir = self.root / "out"
        self.write_still(out_dir, synthetic_still_record(row(nid=1)))
        (out_dir / "stills" / "broken.json").write_text("{not json",
                                                       encoding="utf-8")
        acq.write_json_atomic(out_dir / "stills" / "wrong-schema.json",
                              {"schemaVersion": "kumiki.other.v1"})
        code = pnm.run_report(out_dir, log=lambda _s: None)
        self.assertEqual(code, 0)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["counts"]["stillMeasured"], 1)
        self.assertEqual(aggregate["counts"]["unreadable"], 2)
        files = sorted(item["file"]
                       for item in aggregate["unreadableRecords"])
        self.assertEqual(files, ["stills/broken.json",
                                 "stills/wrong-schema.json"])
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        self.assertNotIn("Broken", report)  # aggregate carries details
        self.assertIn("Unreadable records: 2", report)

    def test_number_formatting_is_fixed_precision(self) -> None:
        self.assertEqual(pnm._num(None, 4), "—")
        self.assertEqual(pnm._num(0.123456789, 4), "0.1235")
        self.assertEqual(pnm._int(None), "—")
        out_dir = self.root / "out"
        self.write_still(out_dir, synthetic_still_record(row(nid=7), luma=0.4))
        pnm.run_report(out_dir, log=lambda _s: None)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        row_line = next(line for line in report.splitlines()
                        if line.startswith("| 7 |"))
        self.assertIn("| 0.4000 |", row_line)
        self.assertIn("| 0.2000 |", row_line)
        self.assertIn("| 0.1000 |", row_line)


# ---------------------------------------------------------------------------
# video lane
# ---------------------------------------------------------------------------


class CollectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_catalog(self, rows: list[dict]) -> Path:
        path = self.root / "catalog.json"
        acq.write_json_atomic(path, pnm.build_catalog(
            rows, len(rows), generated_at="2026-01-01T00:00:00Z"))
        return path

    def index(self, out_dir: Path) -> dict:
        return json.loads(
            (out_dir / "index.json").read_text(encoding="utf-8"))

    def test_provider_routing_never_attempts_vimeo(self) -> None:
        youtube = youtube_row(nid=1)
        vimeo = row(nid=2, videos=[{
            "url": "https://vimeo.com/123", "filemime": "video/vimeo"}])
        absent = row(nid=3, videos=[])
        self.assertEqual(pnm.collect_reference(youtube),
                         ("youtube", VALID_VIDEO_URL))
        self.assertIsNone(pnm.collect_skip_reason(youtube))
        self.assertEqual(pnm.collect_skip_reason(vimeo), "unsupported-vimeo")
        self.assertEqual(pnm.collect_skip_reason(absent), "no-video-reference")
        self.assertEqual(
            pnm.canonical_youtube_url("https://youtu.be/xyz98765432"),
            "https://www.youtube.com/watch?v=xyz98765432")
        self.assertEqual(
            pnm.canonical_youtube_url(
                "https://www.youtube.com/shorts/xyz98765432"),
            "https://www.youtube.com/watch?v=xyz98765432")

    def test_first_youtube_entry_wins_over_a_leading_vimeo_entry(self) -> None:
        source = raw_source(videos=[
            {"url": "https://vimeo.com/123", "filemime": "video/vimeo"},
            {"url": "https://youtu.be/xyz98765432",
             "filemime": "video/youtube"},
        ])
        projected = pnm.normalize_source(source)
        self.assertEqual(projected["provider"], "youtube")
        self.assertEqual(projected["videoUrl"], "https://youtu.be/xyz98765432")
        self.assertIsNone(pnm.collect_skip_reason(projected))
        with_list = dict(projected)
        with_list["videos"] = source["videos"]
        self.assertEqual(pnm.collect_reference(with_list),
                         ("youtube", "https://youtu.be/xyz98765432"))

    def test_limit_counts_only_attempted_rows(self) -> None:
        vimeo = row(nid=3, created=300, videos=[{
            "url": "https://vimeo.com/123", "filemime": "video/vimeo"}])
        second = row(nid=2, created=200)
        first = row(nid=1, created=100)
        catalog_path = self.write_catalog([first, second, vimeo])
        out_dir = self.root / "out"

        def fake_collect(source: dict, out: Path, **_options: object) -> dict:
            record = synthetic_video_record(source)
            acq.write_json_atomic(pnm.video_record_path(out, source), record)
            return record

        with patch.object(pnm, "collect_one",
                          side_effect=fake_collect) as collect:
            code = pnm.run_collect(
                catalog_path, out_dir=out_dir, limit=1, delay_seconds=0,
                acknowledge_rights=True, log=lambda _s: None)

        self.assertEqual(code, 0)
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(collect.call_args.args[0]["nid"], 2)
        index = self.index(out_dir)
        self.assertEqual(index["schemaVersion"], pnm.VIDEO_INDEX_SCHEMA)
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 1, "failed": 0})
        self.assertEqual(index["skips"][0]["reason"], "unsupported-vimeo")

    def test_acknowledgement_is_required(self) -> None:
        catalog_path = self.write_catalog([row()])
        with self.assertRaises(ValueError):
            pnm.run_collect(
                catalog_path, out_dir=self.root / "out",
                acknowledge_rights=False, log=lambda _s: None)
        with self.assertRaises(SystemExit):
            pnm.main([
                "collect", "--catalog", str(catalog_path),
                "--out-dir", str(self.root / "out2")])

    def test_resume_skips_an_existing_video_record(self) -> None:
        source = row()
        catalog_path = self.write_catalog([source])
        out_dir = self.root / "out"
        existing = pnm.video_record_path(out_dir, source)
        acq.write_json_atomic(existing, synthetic_video_record(source))
        before = existing.read_bytes()

        with patch.object(pnm, "collect_one") as collect:
            code = pnm.run_collect(
                catalog_path, out_dir=out_dir, limit=0, resume=True,
                delay_seconds=0, acknowledge_rights=True, log=lambda _s: None)

        self.assertEqual(code, 0)
        collect.assert_not_called()
        self.assertEqual(existing.read_bytes(), before)
        index = self.index(out_dir)
        self.assertEqual(index["skips"][0]["reason"], "resume-existing-record")
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 1, "failed": 0})

    def test_refusal_is_a_skip_and_transient_is_a_failure(self) -> None:
        first = row(nid=1, created=100)
        second = row(nid=2, created=200)
        third = row(nid=3, created=300)
        catalog_path = self.write_catalog([first, second, third])
        out_dir = self.root / "out"
        effects = [
            acq.YtDlpRefusedError("provider refused"),
            acq.YtDlpError("network wobble"),
            synthetic_video_record(first),
        ]

        with patch.object(pnm, "collect_one", side_effect=effects) as collect:
            code = pnm.run_collect(
                catalog_path, out_dir=out_dir, limit=0, delay_seconds=0,
                acknowledge_rights=True, log=lambda _s: None)

        self.assertEqual(code, 0)
        self.assertEqual(collect.call_count, 3)  # a refusal is not retried
        index = self.index(out_dir)
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 1, "failed": 1})
        self.assertEqual(index["skips"][0]["nid"], 3)
        self.assertEqual(index["skips"][0]["reason"], "provider-refused")
        self.assertEqual(index["failures"][0]["nid"], 2)
        self.assertIn("transient", index["failures"][0]["reason"])

    def test_video_record_shape_and_evidence_labels(self) -> None:
        record = synthetic_video_record(row())
        self.assertEqual(record["schemaVersion"], pnm.VIDEO_SCHEMA)
        self.assertEqual(record["provider"], "youtube")
        self.assertEqual(record["videoUrl"], VALID_VIDEO_URL)
        self.assertEqual(record["downloadMethod"], acq.METHOD_YTDLP_MERGE)
        self.assertIsNone(record["unsupportedReason"])
        self.assertFalse(record["mediaRetained"])
        self.assertFalse(record["acquisition"]["mediaRetained"])
        self.assertEqual(record["acquisition"]["provider"], "youtube")
        self.assertEqual(record["acquisition"]["method"],
                         acq.METHOD_YTDLP_MERGE)
        self.assertEqual(record["evidenceStatus"],
                         pnm.VIDEO_EVIDENCE_STATUS)
        self.assertIn("rendition", record["renditionNote"].lower())
        limits = " ".join(record["limits"]).lower()
        self.assertIn("not the work's delivered master", limits)
        self.assertIn("deleted", limits)
        self.assertIn("provider refusal", limits)

    def test_collect_one_writes_a_record_and_retains_no_media(self) -> None:
        out_dir = self.root / "out"
        coverage = {
            "windowsMeasured": 1, "windowSeconds": 10,
            "sampledSeconds": 10, "fractionOfRuntime": 0.1,
            "fullRuntimeMeasured": False,
            "note": "evenly spread source-PTS windows, not full-film review",
        }
        measured = [{
            "startSeconds": 0, "endSeconds": 10,
            "probe": {"sampledWindowSummary": {
                "cutCandidateCountBetweenFirstAndLastSample": 1,
                "meanSampledDisplayLumaProxy": 0.4,
                "meanSampledSaturationProxy": 0.2,
                "cutSeparatedPairs": 0},
                "sampledFrames": [0],
                "sampledFramePairs": [
                    {"meanAbsoluteDisplayRgbDeltaPerSecond": 0.05}]},
        }]

        def fake_download(url: str, provider: str, directory: Path,
                          **_options: object) -> tuple[Path, str]:
            target = Path(directory) / "source.mp4"
            target.write_bytes(b"\x00" * 64)
            return target, acq.METHOD_YTDLP_MERGE

        with patch.object(pnm, "download_media", side_effect=fake_download), \
                patch.object(pnm, "source_metadata", return_value={
                    "mediaSha256": "a" * 64, "sizeBytes": 64,
                    "durationSeconds": 100.0, "resolution": [1280, 720],
                    "frameRate": {"numerator": 25, "denominator": 1},
                    "sourceTimebase": None, "container": "mp4",
                    "videoCodec": "h264", "audioCodec": "aac",
                    "hasAudio": True}), \
                patch.object(pnm, "measure_windows",
                             return_value=(coverage, measured)):
            record = pnm.collect_one(youtube_row(), out_dir)

        self.assertEqual(record["mediaRetained"], False)
        written = pnm.video_record_path(out_dir, youtube_row())
        self.assertTrue(written.is_file())
        self.assertEqual(
            json.loads(written.read_text(encoding="utf-8"))["schemaVersion"],
            pnm.VIDEO_SCHEMA)
        self.assertEqual(list(self.root.rglob("*.mp4")), [])

    def test_probe_failure_still_deletes_downloaded_media(self) -> None:
        created: list[Path] = []
        real_temporary = tempfile.TemporaryDirectory

        def factory(*args: object, **kwargs: object):
            manager = real_temporary(*args, dir=str(self.root), **kwargs)
            created.append(Path(manager.name))
            return manager

        def fake_download(url: str, provider: str, directory: Path,
                          **_options: object) -> tuple[Path, str]:
            target = Path(directory) / "source.mp4"
            target.write_bytes(b"\x00" * 64)
            return target, acq.METHOD_YTDLP_MERGE

        with patch.object(pnm.tempfile, "TemporaryDirectory",
                          side_effect=factory), \
                patch.object(pnm, "download_media", side_effect=fake_download), \
                patch.object(pnm, "source_metadata",
                             side_effect=ValueError("probe exploded")):
            with self.assertRaises(pnm.ProbeFailed):
                pnm.collect_one(youtube_row(), self.root / "out")

        self.assertTrue(created)
        for path in created:
            self.assertFalse(path.exists())
        self.assertEqual(list(self.root.rglob("*.mp4")), [])


class VideoReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_still(self, out_dir: Path, record: dict) -> None:
        acq.write_json_atomic(
            out_dir / "stills" / f"{pnm.record_stem(record)}.json", record)

    def write_video(self, out_dir: Path, record: dict) -> None:
        acq.write_json_atomic(
            out_dir / "videos" / f"{pnm.record_stem(record)}.json", record)

    def test_report_separates_video_and_still_evidence(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(row(nid=1), luma=0.5))
        self.write_still(out_dir, synthetic_still_record(row(nid=1), luma=0.9))
        self.write_still(out_dir, synthetic_still_record(
            row(nid=2, created=CREATED - 60), luma=0.0))

        code = pnm.run_report(out_dir, log=lambda _s: None)
        self.assertEqual(code, 0)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["evidence"],
                         "video-measured+still-measured")
        self.assertEqual(aggregate["counts"]["videoMeasured"], 1)
        self.assertEqual(aggregate["counts"]["stillMeasured"], 2)
        self.assertEqual(aggregate["counts"]["stillOnly"], 1)
        luma = aggregate["videoAggregates"]["distributions"]["meanDisplayLuma"]
        self.assertEqual(luma["n"], 1)
        self.assertEqual(luma["median"], 0.5)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        self.assertIn("Aggregates (video-measured records only)", report)
        self.assertIn("Still-only records", report)
        self.assertIn("Video-measured records: 1", report)
        self.assertIn("Unique video media after dedupe: 1", report)
        self.assertIn("sampled_cut_candidates_per_min", report)
        self.assertIn("candidates_n", report)
        self.assertIn("## Comparability", report)
        self.assertIn("## Coverage", report)
        self.assertIn("poolable: `false`", report)
        self.assertIn("below 20%", report)
        self.assertIn("median unobserved gap between windows", report)
        self.assertIn("ytdlp-merge", report)
        self.assertNotIn("Why there is no motion evidence", report)

    def test_report_with_videos_is_byte_identical_across_runs(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(
            row(nid=1), generated_at="2026-01-04T00:00:00Z"))
        self.write_still(out_dir, synthetic_still_record(
            row(nid=1), generated_at="2026-01-03T00:00:00Z"))
        self.write_still(out_dir, synthetic_still_record(
            row(nid=2, created=CREATED - 60), luma=0.1,
            generated_at="2026-01-02T00:00:00Z"))

        pnm.run_report(out_dir, top=5, log=lambda _s: None)
        first_report = (out_dir / "report.md").read_bytes()
        first_aggregate = (out_dir / "aggregate.json").read_bytes()
        pnm.run_report(out_dir, top=5, log=lambda _s: None)

        self.assertEqual((out_dir / "report.md").read_bytes(), first_report)
        self.assertEqual(
            (out_dir / "aggregate.json").read_bytes(), first_aggregate)


# ---------------------------------------------------------------------------
# CLI-level invariants
# ---------------------------------------------------------------------------


class CliTests(unittest.TestCase):
    def test_catalog_and_stills_commands_parse(self) -> None:
        parser = pnm.build_parser()
        args = parser.parse_args([
            "catalog", "--out", "/tmp/catalog.json", "--limit", "20"])
        self.assertEqual(args.command, "catalog")
        self.assertEqual(args.limit, 20)
        args = parser.parse_args([
            "stills", "--catalog", "/tmp/catalog.json", "--out-dir", "/tmp/out",
            "--refresh", "--jobs", "2"])
        self.assertEqual(args.command, "stills")
        self.assertFalse(args.resume)
        self.assertEqual(args.jobs, 2)

    def test_sha256_helper_used_for_catalog_digest(self) -> None:
        # The catalog digest recorded in the index is the file's SHA-256.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text("{}", encoding="utf-8")
            self.assertEqual(
                pnm.sha256_file(path),
                hashlib.sha256(b"{}").hexdigest())


if __name__ == "__main__":
    unittest.main()
