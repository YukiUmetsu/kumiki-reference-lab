"""Offline tests for the shots.net ephemeral video/stills research adapter."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab import acquisition as acq
from kumiki_reference_lab.acquisition import media as acq_media
from scripts import research_shots as shots

CDN = "https://d1ko11x0ybxl0h.cloudfront.net"
PROXY = "https://proxy.slatecdn.net/media/abc"
ER = "https://app.extremereach.com/Media/Download/00000000-0000-0000-0000-000000000000"
REDIRECT = "https://d2290ppie00mze.cloudfront.net/out/clip.mp4"
EVIL = "https://evil.example/clip.mp4"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def media_file(url: str, size: int | None = 1_000_000,
               name: str = "clip.mp4") -> dict:
    return {"remote_address": url, "size": size, "name": name,
            "extension": "mp4", "mediaInfo": {"Duration": "30.0"}}


def raw_clip(**overrides: object) -> dict:
    clip: dict[str, object] = {
        "id": 101,
        "title": "Demo Clip",
        "urlname": "demo-clip",
        "duration": 30.0,
        "publication_date": "2026-11-01T00:00:00+00:00",
        "brand": {"id": 1, "name": "Acme", "logo": {"remote_address": "https://x/logo.png"}},
        "client": {"id": 2, "name": "Client Co"},
        "agency": {"id": 3, "name": "Agency Co"},
        "brand_office": None,
        "production_company": [{"id": 4, "name": "Studio Co"}],
        "artists_names": ["Artist A"],
        "categories": [{"id": 5, "name": "3D"}],
        "content_types": [{"id": 6, "name": "Branded"}],
        "original_width": 1920,
        "original_height": 1080,
        "aspect_ratio": 1.777,
        "download_allowed": False,
        "embedded_url": "https://shots.net/embed/clip/101",
        "__url": "https://shots.net/work/demo-clip",
        "slate_award": [],
        "year": 2026,
        "thumbnail": {"remote_address": f"{CDN}/thumb.jpg", "size": 123,
                      "image_player_url": "https://images.slatecdn.net/thumb.webp"},
        "thumbnails": [
            {"file": {"remote_address": f"{CDN}/thumb-0.jpg", "size": 111}},
            {"file": {"remote_address": f"{CDN}/thumb-1.jpg", "size": 112}},
        ],
        "original_file": {
            "remote_address": f"{CDN}/original.mp4",
            "size": 70_000_000,
            "mediaInfo": {"Duration": "30.0"},
        },
        "encoding_media_info": {"Duration": "30.0", "FileSize": "70000000"},
        "streams": {
            "1": {"status": 3, "file": media_file(f"{CDN}/web-1280x720.mp4", 9_000_000,
                                                  "web-1280x720.mp4")}
        },
    }
    clip.update(overrides)
    return clip


def synthetic_probe(cuts: int, luma: float, saturation: float,
                    frame_count: int, per_second: list[float | None]) -> dict:
    return {
        "sampledWindowSummary": {
            "cutCandidateCountBetweenFirstAndLastSample": cuts,
            "meanSampledDisplayLumaProxy": luma,
            "meanSampledSaturationProxy": saturation,
        },
        "sampledFrames": [{} for _ in range(frame_count)],
        "sampledFramePairs": [
            {"meanAbsoluteDisplayRgbDeltaPerSecond": value}
            for value in per_second
        ],
    }


def catalog_page(results: list[dict], *, hits: int = 99,
                 limit: int = 2, offset: int = 0) -> dict:
    return {"hits": hits, "has_hits": bool(results), "limit": limit,
            "offset": offset, "sort": "newestFirst", "types": ["clip"],
            "results": results}


def synthetic_source(**overrides: object) -> dict:
    source = {
        "mediaSha256": "a" * 64,
        "sizeBytes": 10 * 1024 * 1024,
        "durationSeconds": 20.0,
        "resolution": [1280, 720],
        "streamIndex": 0,
        "frameRate": {"numerator": 25, "denominator": 1},
        "framesPerSecond": 25.0,
        "sourceTimebase": {"numerator": 1, "denominator": 25000},
        "container": "mov,mp4,m4a,3gp,3g2,mj2",
        "videoCodec": "h264",
        "audioCodec": "aac",
        "hasAudio": True,
    }
    source.update(overrides)
    return source


def synthetic_coverage(*, windows: int = 2, seconds: int = 10,
                       duration: float = 20.0) -> dict:
    sampled = windows * seconds
    return {
        "windowsMeasured": windows, "windowSeconds": seconds,
        "sampledSeconds": sampled,
        "fractionOfRuntime": round(min(1.0, sampled / duration), 6),
        "fullRuntimeMeasured": False,
        "note": "evenly spread source-PTS windows, not full-film review",
    }


def synthetic_windows(*, count: int = 2, cuts: int = 2, luma: float = 0.4,
                      saturation: float = 0.3) -> list[dict]:
    return [{
        "startSeconds": index * 10,
        "endSeconds": index * 10 + 10,
        "probe": synthetic_probe(cuts, luma, saturation, 2, [0.5, 0.25]),
    } for index in range(count)]


def synthetic_video_record(row: dict, *, cuts: int = 4, luma: float = 0.4,
                           saturation: float = 0.3,
                           generated_at: str = "2026-01-01T00:00:00Z") -> dict:
    return shots.build_video_record(
        row,
        media={"rendition": row.get("videoRendition"), "url": row.get("videoUrl"),
               "host": "d1ko11x0ybxl0h.cloudfront.net",
               "bytes": row.get("videoBytes")},
        source=synthetic_source(),
        coverage=synthetic_coverage(),
        windows=synthetic_windows(cuts=cuts, luma=luma, saturation=saturation),
        method="http-download", downloaded_bytes=10 * 1024 * 1024,
        rights_note="research note", generated_at=generated_at)


def synthetic_still_record(row: dict, *, luma: float = 0.9,
                           hue: str = "blue",
                           generated_at: str = "2026-01-02T00:00:00Z") -> dict:
    return shots.build_still_record(row, still={
        "imageUrl": row.get("thumbnailUrl") or f"{CDN}/thumb.jpg",
        "imageSha256": "b" * 64,
        "imageFormat": "jpg",
        "imageBytes": 1234,
        "imageWidth": 640,
        "imageHeight": 360,
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


def catalog_row(**overrides: object) -> dict:
    row = shots.normalize_clip(raw_clip(**overrides))
    return row


# ---------------------------------------------------------------------------
# catalog and normalization
# ---------------------------------------------------------------------------


class CatalogFetchTests(unittest.TestCase):
    def test_paging_stops_on_a_short_page_and_keeps_total_hits(self) -> None:
        calls: list[str] = []
        pages = [
            catalog_page([raw_clip(id=1), raw_clip(id=2, urlname="two")],
                         hits=3, limit=2),
            catalog_page([raw_clip(id=3, urlname="three", publication_date="2026-10-20")],
                         hits=3, limit=2),
        ]

        def fake_fetch(url: str) -> dict:
            calls.append(url)
            return pages.pop(0)

        rows, total = shots.fetch_catalog(
            limit=3, page_size=2, delay_seconds=0, fetch=fake_fetch,
            sleep=lambda _s: None, log=lambda _s: None)
        self.assertEqual(total, 3)
        self.assertEqual([row["id"] for row in rows], [2, 1, 3])
        self.assertEqual(len(calls), 2)
        self.assertIn("limit=2", calls[0])
        self.assertIn("offset=0", calls[0])
        self.assertIn("offset=2", calls[1])

    def test_since_filter_stops_at_older_results(self) -> None:
        pages = [
            catalog_page([raw_clip(id=1, publication_date="2026-11-10T00:00:00Z"),
                          raw_clip(id=2, publication_date="2026-11-05T00:00:00Z")]),
            catalog_page([raw_clip(id=3, publication_date="2026-10-01T00:00:00Z"),
                          raw_clip(id=4, publication_date="2026-09-01T00:00:00Z")]),
        ]

        def fake_fetch(_url: str) -> dict:
            return pages.pop(0)

        rows, _ = shots.fetch_catalog(
            limit=10, page_size=2, since="2026-11-01", delay_seconds=0,
            fetch=fake_fetch, sleep=lambda _s: None, log=lambda _s: None)
        self.assertEqual([row["id"] for row in rows], [1, 2])

    def test_limit_zero_makes_no_request(self) -> None:
        def explode(_url: str) -> dict:
            raise AssertionError("limit=0 must not fetch")

        rows, total = shots.fetch_catalog(
            limit=0, fetch=explode, sleep=lambda _s: None, log=lambda _s: None)
        self.assertEqual(rows, [])
        self.assertIsNone(total)

    def test_empty_page_terminates(self) -> None:
        calls: list[str] = []

        def fake_fetch(url: str) -> dict:
            calls.append(url)
            return catalog_page([], hits=0)

        rows, total = shots.fetch_catalog(
            limit=10, page_size=2, delay_seconds=0, fetch=fake_fetch,
            sleep=lambda _s: None, log=lambda _s: None)
        self.assertEqual(rows, [])
        self.assertEqual(total, 0)
        self.assertEqual(len(calls), 1)

    def test_page_size_is_capped_at_one_hundred(self) -> None:
        for size in (0, 101):
            with self.subTest(size=size), self.assertRaises(ValueError):
                shots.fetch_catalog(limit=1, page_size=size, log=lambda _s: None)
        with self.assertRaises(ValueError):
            shots.search_url(101, 0)


class NormalizationTests(unittest.TestCase):
    def test_slim_projection_keeps_only_the_documented_keys(self) -> None:
        row = catalog_row()
        self.assertEqual(set(row), {
            "id", "slug", "title", "publicationDate", "durationSeconds",
            "originalWidth", "originalHeight", "aspectRatio", "brandName",
            "clientName", "agencyName", "productionCompanies", "artists",
            "categories", "contentTypes", "awards", "downloadAllowed",
            "embedUrl", "articleUrl", "thumbnailUrl", "videoUrl", "videoBytes",
            "videoRendition", "year", "candidates",
        })
        dumped = json.dumps(row)
        self.assertNotIn("logo", dumped)
        self.assertNotIn("mediaInfo", dumped)
        self.assertNotIn("encoding_media_info", dumped)
        self.assertNotIn("streams", dumped)

    def test_identity_and_poster_mapping(self) -> None:
        row = catalog_row()
        self.assertEqual(row["id"], 101)
        self.assertEqual(row["slug"], "demo-clip")
        self.assertEqual(row["articleUrl"], "https://shots.net/news/view/demo-clip")
        self.assertEqual(row["embedUrl"], "https://shots.net/embed/clip/101")
        self.assertEqual(row["brandName"], "Acme")
        self.assertEqual(row["clientName"], "Client Co")
        self.assertEqual(row["agencyName"], "Agency Co")
        self.assertEqual(row["productionCompanies"], ["Studio Co"])
        self.assertEqual(row["artists"], ["Artist A"])
        self.assertEqual(row["categories"], ["3D"])
        self.assertEqual(row["contentTypes"], ["Branded"])
        self.assertFalse(row["downloadAllowed"])
        # Primary thumbnail wins over thumbnails[].
        self.assertEqual(row["thumbnailUrl"], f"{CDN}/thumb.jpg")

    def test_thumbnail_falls_back_to_first_thumbnails_entry(self) -> None:
        row = catalog_row(thumbnail=None)
        self.assertEqual(row["thumbnailUrl"], f"{CDN}/thumb-0.jpg")

    def test_thumbnail_rejects_non_allowlisted_host(self) -> None:
        row = catalog_row(
            thumbnail={"remote_address": EVIL, "image_player_url": EVIL + "?x=1"},
            thumbnails=[{"file": {"remote_address": EVIL}}])
        self.assertIsNone(row["thumbnailUrl"])

    def test_catalog_rows_stay_approximately_slim(self) -> None:
        # Mix the observed shapes: most clips have only an original candidate,
        # a minority has a platform-encoded list stream or a 720p web rendition.
        rows: list[dict] = []
        for index in range(1, 51):
            if index % 20 == 0:
                overrides: dict = {}
            elif index % 7 == 0:
                overrides = {"streams": [
                    {"status": 3, "file": media_file(f"{PROXY}/ready.mp4")}]}
            else:
                overrides = {
                    "streams": [],
                    "original_file": {
                        "remote_address": f"{ER}?profile=1&useCDN=true&id={index}",
                        "size": 70_000_000,
                    },
                }
            rows.append(catalog_row(id=index, urlname=f"clip-{index}", **overrides))
        catalog = shots.build_catalog(rows, len(rows))
        payload = json.dumps(catalog, separators=(",", ":")).encode()
        per_row = len(payload) / len(rows)
        self.assertLess(per_row, 1100)
        self.assertNotIn(b"encoding_media_info", payload)
        self.assertNotIn(b"mediaInfo", payload)

    def test_catalog_is_deterministically_ordered(self) -> None:
        rows = [
            catalog_row(id=1, publication_date="2026-11-01T00:00:00Z"),
            catalog_row(id=3, publication_date="2026-11-02T00:00:00Z", urlname="three"),
            catalog_row(id=2, publication_date="2026-11-02T00:00:00Z", urlname="two"),
        ]
        catalog = shots.build_catalog(
            sorted(rows, key=shots.catalog_order, reverse=True), 3,
            retrieved_at="2026-01-01T00:00:00Z")
        self.assertEqual([row["id"] for row in catalog["clips"]], [3, 2, 1])
        self.assertEqual(catalog["schemaVersion"], shots.CATALOG_SCHEMA)


# ---------------------------------------------------------------------------
# rendition ladder
# ---------------------------------------------------------------------------


class MediaLadderTests(unittest.TestCase):
    def test_dict_stream_wins_the_web_rendition(self) -> None:
        candidates, chosen = shots.choose_media(raw_clip())
        self.assertEqual(chosen["rendition"], "720p-web-rendition")
        self.assertEqual(chosen["url"], f"{CDN}/web-1280x720.mp4")
        self.assertEqual([c["rendition"] for c in candidates],
                         ["720p-web-rendition", "original-download"])
        self.assertTrue(all(c["usable"] for c in candidates))

    def test_list_stream_skips_non_ready_and_non_allowlisted_entries(self) -> None:
        raw = raw_clip(streams=[
            {"status": 2, "file": media_file(f"{CDN}/not-ready.mp4")},
            {"status": 3, "file": media_file(EVIL)},
            {"status": 3, "file": media_file(f"{PROXY}/ready.mp4")},
        ])
        candidates, chosen = shots.choose_media(raw)
        self.assertEqual(chosen["rendition"], "platform-encoded-source")
        self.assertEqual(chosen["url"], f"{PROXY}/ready.mp4")
        self.assertFalse(candidates[0]["usable"])
        self.assertEqual(candidates[0]["reason"], "stream-not-ready")
        self.assertFalse(candidates[1]["usable"])
        self.assertFalse(candidates[1]["allowlisted"])
        self.assertTrue(candidates[2]["usable"])

    def test_original_download_is_the_last_resort(self) -> None:
        raw = raw_clip(streams=[])
        candidates, chosen = shots.choose_media(raw)
        self.assertEqual([c["rendition"] for c in candidates], ["original-download"])
        self.assertEqual(chosen["rendition"], "original-download")
        self.assertEqual(chosen["url"], f"{CDN}/original.mp4")

    def test_original_with_a_signed_query_string_is_now_usable(self) -> None:
        raw = raw_clip(streams=[], original_file={
            "remote_address": f"{ER}?profile=1&useCDN=true",
            "size": 70_000_000, "mediaInfo": {"Duration": "30.0"}})
        candidates, chosen = shots.choose_media(raw)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(chosen["rendition"], "original-download")
        self.assertEqual(chosen["url"], f"{ER}?profile=1&useCDN=true")
        self.assertTrue(chosen["allowlisted"])
        self.assertTrue(chosen["usable"])
        row = shots.normalize_clip(raw)
        self.assertEqual(row["videoUrl"], f"{ER}?profile=1&useCDN=true")
        self.assertEqual(row["videoBytes"], 70_000_000)
        self.assertEqual(row["videoRendition"], "original-download")

    def test_signed_cloudfront_original_is_also_usable(self) -> None:
        signed = (f"{REDIRECT}?AWSAccessKeyId=AKIAEXAMPLE&Expires=1"
                  "&Signature=abc&response-content-disposition=attachment")
        raw = raw_clip(streams=[], original_file={
            "remote_address": signed, "size": 70_000_000,
            "mediaInfo": {"Duration": "30.0"}})
        _, chosen = shots.choose_media(raw)
        self.assertEqual(chosen["rendition"], "original-download")
        self.assertEqual(chosen["url"], signed)

    def test_ladder_still_prefers_the_720p_rendition_over_a_signed_original(self) -> None:
        raw = raw_clip(original_file={
            "remote_address": f"{ER}?profile=1&useCDN=true",
            "size": 70_000_000, "mediaInfo": {"Duration": "30.0"}})
        candidates, chosen = shots.choose_media(raw)
        self.assertEqual([candidate["rendition"] for candidate in candidates],
                         ["720p-web-rendition", "original-download"])
        self.assertEqual(chosen["rendition"], "720p-web-rendition")
        self.assertEqual(chosen["url"], f"{CDN}/web-1280x720.mp4")
        self.assertTrue(candidates[1]["usable"])

    def test_non_allowlisted_original_is_not_usable(self) -> None:
        raw = raw_clip(streams=[], original_file=media_file(EVIL, 70_000_000))
        _, chosen = shots.choose_media(raw)
        self.assertIsNone(chosen)

    def test_selected_url_is_never_rewritten(self) -> None:
        raw = raw_clip()
        _, chosen = shots.choose_media(raw)
        row = shots.normalize_clip(raw)
        self.assertEqual(chosen["url"], row["videoUrl"])
        self.assertEqual(row["videoRendition"], "720p-web-rendition")


# ---------------------------------------------------------------------------
# record schemas
# ---------------------------------------------------------------------------


class RecordSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.row = catalog_row()

    def test_video_record_is_deterministic_and_carries_identity(self) -> None:
        first = synthetic_video_record(self.row)
        second = synthetic_video_record(self.row)
        self.assertEqual(first, second)
        self.assertEqual(first["schemaVersion"], shots.VIDEO_SCHEMA)
        self.assertEqual(first["clipId"], 101)
        self.assertEqual(first["clip"]["projectUrl"],
                         "https://shots.net/news/view/demo-clip")
        self.assertEqual(first["clip"]["embedUrl"],
                         "https://shots.net/embed/clip/101")
        self.assertEqual(first["clip"]["downloadAllowed"], False)
        self.assertEqual(first["source"]["mediaSha256"], "a" * 64)
        self.assertEqual(first["source"]["streamIndex"], 0)
        self.assertEqual(first["source"]["sourceTimebase"],
                         {"numerator": 1, "denominator": 25000})
        self.assertEqual(first["source"]["framesPerSecond"], 25.0)
        self.assertEqual(first["acquisition"]["provider"], "direct-mp4")
        self.assertEqual(first["acquisition"]["method"], "http-download")
        self.assertEqual(first["acquisition"]["rendition"], "720p-web-rendition")
        self.assertEqual(first["acquisition"]["url"], f"{CDN}/web-1280x720.mp4")
        self.assertEqual(first["acquisition"]["bytes"], 10 * 1024 * 1024)
        self.assertFalse(first["acquisition"]["mediaRetained"])
        self.assertEqual(first["rights"],
                         {"basis": shots.RIGHTS_BASIS, "status": "review-required",
                          "note": "research note"})
        self.assertEqual(first["coverage"]["fullRuntimeMeasured"], False)
        self.assertEqual(first["evidenceStatus"], shots.EVIDENCE_STATUS)
        limits = " ".join(first["limits"])
        self.assertIn("downloadAllowed", limits)
        self.assertIn("deleted", limits)
        self.assertIn("No cookies", limits)

    def test_video_record_keeps_every_candidate(self) -> None:
        record = synthetic_video_record(self.row)
        self.assertEqual(record["media"]["chosen"]["rendition"],
                         "720p-web-rendition")
        self.assertEqual(record["media"]["chosen"]["name"], "web-1280x720.mp4")
        self.assertEqual([row["kind"] for row in record["media"]["candidates"]],
                         ["720p-web-rendition", "original-download"])
        self.assertEqual(record["media"]["candidates"][0]["name"],
                         "web-1280x720.mp4")

    def test_still_record_denies_motion_and_retains_no_image(self) -> None:
        record = synthetic_still_record(self.row)
        self.assertEqual(record["schemaVersion"], shots.STILL_SCHEMA)
        self.assertEqual(record["clip"]["id"], 101)
        self.assertFalse(record["coverage"]["isSourceVideoFrame"])
        self.assertEqual(record["acquisition"]["method"], "poster-still-http")
        self.assertFalse(record["acquisition"]["imageRetained"])
        self.assertEqual(record["evidenceStatus"], shots.STILL_EVIDENCE_STATUS)
        limits = " ".join(record["limits"]).lower()
        self.assertIn("not a video frame", limits)
        self.assertIn("no motion", limits)
        self.assertIn("timing", limits)

    def test_still_record_is_deterministic(self) -> None:
        self.assertEqual(synthetic_still_record(self.row),
                         synthetic_still_record(self.row))


# ---------------------------------------------------------------------------
# collection failure, budgets, and resume
# ---------------------------------------------------------------------------


class CollectFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.out_dir = self.root / "out"
        self.row = catalog_row()

    def test_failed_download_deletes_the_temporary_directory_and_writes_no_record(self) -> None:
        captured: list[Path] = []

        def fake_download(url: str, provider: str, directory: Path,
                          **_: object):
            captured.append(directory)
            raise ValueError("synthetic download failure")

        with patch.object(shots, "download_media", side_effect=fake_download):
            with self.assertRaises(ValueError):
                shots.collect_one(self.row, self.out_dir)
        self.assertTrue(captured)
        self.assertFalse(captured[0].exists())
        self.assertEqual(list(self.out_dir.rglob("*.mp4")), [])
        videos = self.out_dir / "videos"
        self.assertEqual(list(videos.iterdir()) if videos.exists() else [], [])

    def test_measurement_failure_after_download_leaves_no_media(self) -> None:
        captured: list[Path] = []

        def fake_download(url: str, provider: str, directory: Path, **_: object):
            captured.append(directory)
            target = directory / "source.mp4"
            target.write_bytes(b"\x00" * 2048)
            return target, "http-download"

        with patch.object(shots, "download_media", side_effect=fake_download), \
                patch.object(shots, "source_metadata",
                             side_effect=ValueError("synthetic probe failure")):
            with self.assertRaises(ValueError):
                shots.collect_one(self.row, self.out_dir)
        self.assertTrue(captured)
        self.assertFalse(captured[0].exists())
        self.assertEqual(list(self.out_dir.rglob("*.mp4")), [])

    def test_pre_download_duration_rejection_never_fetches(self) -> None:
        row = dict(self.row, durationSeconds=10_000.0)
        with patch.object(shots, "download_media") as download:
            with self.assertRaisesRegex(ValueError, "duration"):
                shots.collect_one(row, self.out_dir)
        download.assert_not_called()

    def test_pre_download_size_rejection_never_fetches(self) -> None:
        row = dict(self.row, videoBytes=shots.DEFAULT_MAX_FILE_BYTES + 1)
        with patch.object(shots, "download_media") as download:
            with self.assertRaisesRegex(ValueError, "size"):
                shots.collect_one(row, self.out_dir)
        download.assert_not_called()

    def test_clip_without_rendition_is_never_attempted(self) -> None:
        row = dict(self.row, videoUrl=None, videoRendition=None)
        with patch.object(shots, "download_media") as download:
            with self.assertRaisesRegex(ValueError, "no allowlisted public rendition"):
                shots.collect_one(row, self.out_dir)
        download.assert_not_called()

    def test_signed_original_reaches_the_engine_with_query_opt_in(self) -> None:
        row = catalog_row(
            streams=[],
            original_file={
                "remote_address": f"{ER}?profile=1&useCDN=true",
                "size": 70_000_000, "mediaInfo": {"Duration": "30.0"}})
        with patch.object(shots, "download_media",
                          side_effect=ValueError("stop before measurement")) as download:
            with self.assertRaisesRegex(ValueError, "stop before measurement"):
                shots.collect_one(row, self.out_dir)
        download.assert_called_once()
        args, kwargs = download.call_args
        self.assertEqual(args[0], row["videoUrl"])
        self.assertTrue(kwargs["allow_query"])

    def test_signed_original_size_still_pre_rejects_oversize(self) -> None:
        row = catalog_row(
            streams=[],
            original_file={
                "remote_address": f"{ER}?profile=1&useCDN=true",
                "size": shots.DEFAULT_MAX_FILE_BYTES + 1,
                "mediaInfo": {"Duration": "30.0"}})
        with patch.object(shots, "download_media") as download:
            with self.assertRaisesRegex(ValueError, "size"):
                shots.collect_one(row, self.out_dir)
        download.assert_not_called()


class CollectRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out_dir = self.root / "out"

    def _write_catalog(self, rows: list[dict]) -> Path:
        path = self.root / "catalog.json"
        acq.write_json_atomic(path, shots.build_catalog(
            rows, len(rows), retrieved_at="2026-01-01T00:00:00Z"))
        return path

    def test_rights_gate_rejects_without_acknowledgement(self) -> None:
        with self.assertRaises(ValueError):
            shots.run_collect(None, out_dir=self.out_dir, limit=0,
                              acknowledge_rights=False, log=lambda _s: None)
        with self.assertRaises(SystemExit) as raised, \
                contextlib.redirect_stderr(io.StringIO()):
            shots.main(["collect", "--out-dir", str(self.out_dir),
                        "--limit", "0"])
        self.assertEqual(raised.exception.code, 2)

    def test_limit_zero_is_an_offline_noop_with_only_an_index(self) -> None:
        with patch.object(shots, "_load_catalog",
                          side_effect=AssertionError("must not read catalog")):
            code = shots.run_collect(
                None, out_dir=self.out_dir, limit=0,
                acknowledge_rights=True, log=lambda _s: None)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(path.name for path in self.out_dir.iterdir()),
                         ["index.json"])
        index = json.loads((self.out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schemaVersion"], shots.INDEX_SCHEMA)
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 0, "failed": 0})

    def test_resume_skips_an_existing_record_and_writes_an_atomic_index(self) -> None:
        row = catalog_row()
        catalog_path = self._write_catalog([row])
        existing = shots.record_path(self.out_dir, "videos", row)
        acq.write_json_atomic(existing, {"clipId": row["id"]})

        with patch.object(shots, "collect_one") as collect_one:
            code = shots.run_collect(
                catalog_path, out_dir=self.out_dir, limit=1, resume=True,
                acknowledge_rights=True, delay_seconds=0, log=lambda _s: None)
        self.assertEqual(code, 0)
        collect_one.assert_not_called()
        index = json.loads((self.out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 1, "failed": 0})
        self.assertEqual(index["skips"][0]["reason"], "resume-existing-record")
        self.assertEqual(index["catalogSha256"],
                         shots.sha256_file(catalog_path))
        self.assertEqual(
            sorted(path.name for path in self.out_dir.iterdir()),
            ["index.json", "videos"])

    def test_refresh_measures_and_indexes(self) -> None:
        row = catalog_row()
        catalog_path = self._write_catalog([row])
        record = synthetic_video_record(row)
        with patch.object(shots, "collect_one",
                          return_value=record) as collect_one:
            code = shots.run_collect(
                catalog_path, out_dir=self.out_dir, limit=1, resume=False,
                acknowledge_rights=True, delay_seconds=0, log=lambda _s: None)
        self.assertEqual(code, 0)
        collect_one.assert_called_once()
        index = json.loads((self.out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 0, "failed": 0})
        self.assertEqual(index["records"][0]["recordPath"],
                         f"videos/{shots.record_stem(row)}.json")
        self.assertEqual(index["records"][0]["rendition"], "720p-web-rendition")

    def test_policy_oversize_rows_become_skips(self) -> None:
        row = dict(catalog_row(), durationSeconds=10_000.0)
        catalog_path = self._write_catalog([row])
        with patch.object(shots, "collect_one") as collect_one:
            code = shots.run_collect(
                catalog_path, out_dir=self.out_dir, limit=1,
                acknowledge_rights=True, delay_seconds=0, log=lambda _s: None)
        self.assertEqual(code, 0)
        collect_one.assert_not_called()
        index = json.loads((self.out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["skips"][0]["reason"],
                         "pre-download-duration-exceeds-budget")

    def test_progress_line_keeps_the_operator_format(self) -> None:
        row = catalog_row()
        catalog_path = self._write_catalog([row])
        record = synthetic_video_record(row)
        buffer = io.StringIO()
        with patch.object(shots, "collect_one", return_value=record), \
                contextlib.redirect_stdout(buffer):
            shots.run_collect(
                catalog_path, out_dir=self.out_dir, limit=1,
                acknowledge_rights=True, delay_seconds=0, log=lambda _s: None)
        self.assertIn("[1/1] ok demo-clip 1280x720 20.0s 10.0MB "
                      "720p-web-rendition cuts=8", buffer.getvalue())


# ---------------------------------------------------------------------------
# stills lane
# ---------------------------------------------------------------------------


class StillAllowlistTests(unittest.TestCase):
    def test_poster_hosts_are_allowlisted(self) -> None:
        for url in (
            f"{CDN}/shotsmag/production/clips/a/thumb.jpg",
            "https://images.slatecdn.net/abc/w:1440/q:100/x.webp",
        ):
            self.assertEqual(shots._policy_image_url(url), url)

    def test_other_hosts_and_query_strings_are_rejected(self) -> None:
        for url in (
            f"{PROXY}/thumb.jpg",
            EVIL,
            f"{CDN}/thumb.jpg?token=1",
            "http://d1ko11x0ybxl0h.cloudfront.net/thumb.jpg",
            None,
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                shots._policy_image_url(url)


class StillRecordAndLaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out_dir = self.root / "out"

    def _write_catalog(self, rows: list[dict]) -> Path:
        path = self.root / "catalog.json"
        acq.write_json_atomic(path, shots.build_catalog(
            rows, len(rows), retrieved_at="2026-01-01T00:00:00Z"))
        return path

    def test_failed_decode_writes_no_record_and_retains_no_image(self) -> None:
        row = catalog_row()
        captured: list[Path] = []

        def fake_download(url: str, target: Path, **_: object) -> Path:
            target.write_bytes(b"\xff\xd8\xff\xe0")
            captured.append(target)
            return target

        with patch.object(shots, "download_http", side_effect=fake_download), \
                patch.object(shots, "measure_still",
                             side_effect=ValueError("synthetic decode failure")):
            with self.assertRaises(ValueError):
                shots.collect_still_one(row, self.out_dir)
        self.assertTrue(captured)
        self.assertFalse(captured[0].exists())
        self.assertFalse(shots.record_path(self.out_dir, "stills", row).exists())

    def test_resume_skips_existing_and_refresh_rebuilds(self) -> None:
        rows = [catalog_row(id=1, urlname="one"), catalog_row(id=2, urlname="two")]
        catalog_path = self._write_catalog(rows)
        existing = shots.record_path(self.out_dir, "stills", rows[0])
        acq.write_json_atomic(existing, {"clipId": rows[0]["id"]})

        def fake_still(row: dict, out_dir: Path, **_: object) -> dict:
            return synthetic_still_record(row)

        with patch.object(shots, "collect_still_one",
                          side_effect=fake_still) as collect:
            code = shots.run_stills(
                catalog_path, out_dir=self.out_dir, resume=True,
                delay_seconds=0, page_size=1, log=lambda _s: None)
        self.assertEqual(code, 0)
        collect.assert_called_once()
        index = json.loads(
            (self.out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schemaVersion"], shots.STILLS_INDEX_SCHEMA)
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 1, "failed": 0})
        self.assertEqual(index["skips"][0]["reason"], "resume-existing-record")
        self.assertEqual(sorted(path.name for path in self.out_dir.iterdir()),
                         ["stills", "stills-index.json"])

        with patch.object(shots, "collect_still_one",
                          side_effect=fake_still) as collect:
            code = shots.run_stills(
                catalog_path, out_dir=self.out_dir, resume=False,
                delay_seconds=0, page_size=1, log=lambda _s: None)
        self.assertEqual(code, 0)
        self.assertEqual(collect.call_count, 2)

    def test_limit_zero_measures_every_remaining_row_and_stops_on_empty(self) -> None:
        rows = [catalog_row(id=index, urlname=f"clip-{index}")
                for index in range(1, 4)]
        catalog_path = self._write_catalog(rows)

        def fake_still(row: dict, out_dir: Path, **_: object) -> dict:
            return synthetic_still_record(row)

        with patch.object(shots, "collect_still_one",
                          side_effect=fake_still) as collect:
            code = shots.run_stills(
                catalog_path, out_dir=self.out_dir, limit=0, resume=False,
                delay_seconds=0, page_size=1, log=lambda _s: None)
        self.assertEqual(code, 0)
        self.assertEqual(collect.call_count, 3)
        index = json.loads(
            (self.out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 3, "skipped": 0, "failed": 0})

    def test_empty_catalog_terminates_without_work(self) -> None:
        catalog_path = self._write_catalog([])
        with patch.object(shots, "collect_still_one") as collect:
            code = shots.run_stills(
                catalog_path, out_dir=self.out_dir, limit=0,
                delay_seconds=0, page_size=2, log=lambda _s: None)
        self.assertEqual(code, 0)
        collect.assert_not_called()
        self.assertTrue((self.out_dir / "stills-index.json").is_file())

    def test_catalog_pages_yield_an_empty_final_page(self) -> None:
        pages = list(shots.catalog_pages([1, 2, 3, 4, 5], page_size=2))
        self.assertEqual([len(page) for page in pages], [2, 2, 1, 0])
        self.assertEqual(list(shots.catalog_pages([], page_size=2)), [[]])


# ---------------------------------------------------------------------------
# redirect policy
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, body: bytes, url: str) -> None:
        self._body = body
        self._url = url
        self._position = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self._body[self._position:self._position + size]
        self._position += len(chunk)
        return chunk

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


class RedirectPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_redirect_to_a_non_allowlisted_host_is_refused(self) -> None:
        target = self.root / "source.mp4"

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            return _FakeResponse(b"payload", EVIL)

        with patch.object(acq_media, "urlopen", side_effect=fake_urlopen):
            with self.assertRaisesRegex(ValueError, "not allowlisted"):
                acq.download_http(
                    f"{CDN}/clip.mp4", target,
                    allowed_hosts=shots.MEDIA_HOSTS, max_bytes=1024)
        self.assertFalse(target.exists())

    def test_allowlist_explicitly_contains_the_redirect_host(self) -> None:
        self.assertIn("d2290ppie00mze.cloudfront.net", shots.MEDIA_HOSTS)
        self.assertIn("app.extremereach.com", shots.MEDIA_HOSTS)
        self.assertNotIn("evil.example", shots.MEDIA_HOSTS)
        self.assertEqual(shots._policy_media_url(REDIRECT), REDIRECT)
        with self.assertRaises(ValueError):
            shots._policy_media_url(EVIL)

    def test_signed_redirect_query_is_now_accepted_by_adapter_policy(self) -> None:
        signed = f"{REDIRECT}?AWSAccessKeyId=x&Expires=1&Signature=y"
        self.assertEqual(shots._policy_media_url(signed), signed)
        # Images stay on the stricter default: no query strings.
        with self.assertRaisesRegex(ValueError, "query string"):
            shots._policy_image_url(f"{CDN}/thumb.jpg?Signature=y")

    def test_engine_still_requires_the_query_opt_in(self) -> None:
        signed = f"{REDIRECT}?AWSAccessKeyId=x&Expires=1&Signature=y"
        with self.assertRaisesRegex(ValueError, "query string"):
            acq.allowlisted_video_url(signed, allowed_hosts=shots.MEDIA_HOSTS)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_video(self, out_dir: Path, record: dict) -> None:
        acq.write_json_atomic(
            out_dir / "videos" / f"{shots.record_stem(record)}.json", record)

    def write_still(self, out_dir: Path, record: dict) -> None:
        acq.write_json_atomic(
            out_dir / "stills" / f"{shots.record_stem(record)}.json", record)

    def test_empty_state_writes_valid_skeleton(self) -> None:
        out_dir = self.root / "out"
        code = shots.run_report(out_dir, log=lambda _s: None)
        self.assertEqual(code, 0)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["schemaVersion"], shots.AGGREGATE_SCHEMA)
        self.assertEqual(aggregate["counts"]["videoMeasured"], 0)
        self.assertEqual(aggregate["videos"], [])
        self.assertEqual(aggregate["stills"]["n"], 0)
        self.assertIn("No video-measured records.", report)
        self.assertIn("None.", report)
        self.assertEqual(sorted(path.name for path in out_dir.iterdir()),
                         ["aggregate.json", "report.md"])

    def test_repeat_runs_are_byte_identical(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(
            catalog_row(id=1, urlname="a"), luma=0.2))
        self.write_video(out_dir, synthetic_video_record(
            catalog_row(id=2, urlname="b"), luma=0.6))
        self.write_still(out_dir, synthetic_still_record(
            catalog_row(id=3, urlname="c"), luma=0.9))

        shots.run_report(out_dir, top=2, log=lambda _s: None)
        first_report = (out_dir / "report.md").read_bytes()
        first_aggregate = (out_dir / "aggregate.json").read_bytes()
        shots.run_report(out_dir, top=2, log=lambda _s: None)

        self.assertEqual((out_dir / "report.md").read_bytes(), first_report)
        self.assertEqual((out_dir / "aggregate.json").read_bytes(), first_aggregate)

    def test_still_only_records_never_enter_motion_aggregates(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(
            catalog_row(id=1, urlname="measured"), luma=0.2, saturation=0.1))
        self.write_still(out_dir, synthetic_still_record(
            catalog_row(id=1, urlname="measured"), luma=0.9, hue="blue"))
        self.write_still(out_dir, synthetic_still_record(
            catalog_row(id=2, urlname="still-only"), luma=0.9, hue="red"))

        shots.run_report(out_dir, log=lambda _s: None)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["counts"]["videoMeasured"], 1)
        self.assertEqual(aggregate["counts"]["stillMeasured"], 2)
        self.assertEqual(aggregate["counts"]["stillOnly"], 1)
        self.assertEqual(
            aggregate["aggregates"]["distributions"]["meanDisplayLuma"],
            {"n": 1, "min": 0.2, "median": 0.2, "max": 0.2})
        self.assertEqual(aggregate["stills"]["n"], 2)
        self.assertEqual(aggregate["stills"]["medianMeanDisplayLumaProxy"], 0.9)
        self.assertEqual(aggregate["stills"]["dominantHueFamilyCounts"],
                         {"blue": 1, "red": 1})
        self.assertEqual(aggregate["videos"][0]["meanDisplayLuma"], 0.2)

    def test_malformed_records_are_listed_but_not_aggregated(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(
            catalog_row(id=1, urlname="good"), luma=0.4))
        (out_dir / "videos" / "broken.json").write_text("{not json", encoding="utf-8")
        acq.write_json_atomic(out_dir / "videos" / "wrong-schema.json",
                              {"schemaVersion": "kumiki.other.v1"})

        code = shots.run_report(out_dir, log=lambda _s: None)
        self.assertEqual(code, 0)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["counts"]["videoMeasured"], 1)
        self.assertEqual(aggregate["counts"]["unreadable"], 2)
        self.assertEqual(
            sorted(item["file"] for item in aggregate["unreadableRecords"]),
            ["videos/broken.json", "videos/wrong-schema.json"])

    def test_skipped_and_failed_counts_come_from_each_index(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(
            catalog_row(id=1, urlname="good")))
        acq.write_json_atomic(out_dir / "index.json", {
            "schemaVersion": shots.INDEX_SCHEMA, "counts": {},
            "records": [], "skips": [{"reason": "resume-existing-record"}],
            "failures": [{"reason": "boom"}]})
        acq.write_json_atomic(out_dir / "stills-index.json", {
            "schemaVersion": shots.STILLS_INDEX_SCHEMA, "counts": {},
            "records": [], "skips": [{"reason": "no-published-thumbnail"}],
            "failures": [{"reason": "decode"}]})
        shots.run_report(out_dir, log=lambda _s: None)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["counts"]["skippedVideo"], 1)
        self.assertEqual(aggregate["counts"]["skippedStills"], 1)
        self.assertEqual(aggregate["counts"]["failedVideo"], 1)
        self.assertEqual(aggregate["counts"]["failedStills"], 1)

    def test_number_formatting_uses_an_explicit_missing_marker(self) -> None:
        self.assertEqual(shots._num(None, 4), "—")
        self.assertEqual(shots._num(0.123456789, 4), "0.1235")
        self.assertEqual(shots._int(None), "—")
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(
            catalog_row(id=1, urlname="numbers")))
        shots.run_report(out_dir, log=lambda _s: None)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        row = next(line for line in report.splitlines() if line.startswith("| 1 |"))
        self.assertIn("| 20.00 |", row)
        self.assertIn("| 25.000 |", row)
        self.assertIn("| 4.19 |", row)
        self.assertIn("| 10.0 |", row)


# ---------------------------------------------------------------------------
# catalog writer and CLI ergonomics
# ---------------------------------------------------------------------------


class CatalogWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_run_catalog_writes_one_atomic_file(self) -> None:
        row = catalog_row()
        with patch.object(shots, "fetch_catalog",
                          return_value=([row], 40908)):
            code = shots.run_catalog(
                self.root / "catalog.json", limit=1, log=lambda _s: None)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()),
                         ["catalog.json"])
        catalog = json.loads(
            (self.root / "catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schemaVersion"], shots.CATALOG_SCHEMA)
        self.assertEqual(catalog["sourceHost"], "shots.net")
        self.assertEqual(catalog["totalReportedHits"], 40908)
        self.assertEqual(catalog["clipCount"], 1)

    def test_cli_help_renders_for_each_command(self) -> None:
        for command in ("catalog", "collect", "stills", "report"):
            buffer = io.StringIO()
            with self.assertRaises(SystemExit) as raised, \
                    contextlib.redirect_stdout(buffer):
                shots.main([command, "--help"])
            self.assertEqual(raised.exception.code, 0)
            self.assertIn("usage:", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
