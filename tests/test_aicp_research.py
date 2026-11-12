"""Offline tests for the AICP Awards ephemeral research collector.

Every network call, probe, and download is mocked; ffmpeg/ffprobe are never
required. The tests cover the GraphQL envelope, the HTTP-200-with-errors trap,
offset paging, duration parsing, screenshot joins, string-id resume, skip
reasons, the download/measure/delete lifecycle, stills, and report determinism.
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Callable
from unittest.mock import patch
from urllib.error import HTTPError

from kumiki_reference_lab import acquisition as acq
from scripts import research_aicp as aicp


def entry_node(**overrides: object) -> dict[str, object]:
    node: dict[str, object] = {
        "id": "1185644",
        "slug": "demo-commercial",
        "title": "Demo Commercial",
        "year": 2025,
        "company": "Demo Co",
        "duration": "02:29",
        "video": ("https://player.vimeo.com/external/123456789.m3u8"
                  "?s=abcdef&logging=false"),
        "videoType": [{"title": "Opening Title"}],
        "showCategory": {"title": "Craft"},
        "postCategory": None,
        "nextCategory": None,
        "screenshot": {"url": "/media/1185644.jpg",
                       "width": 1280, "height": 720},
    }
    node.update(overrides)
    return node


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._raw = (payload if isinstance(payload, bytes)
                     else json.dumps(payload).encode("utf-8"))

    def read(self, limit: int = -1) -> bytes:
        return self._raw if limit < 0 else self._raw[:limit]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> bool:
        return False


class GraphqlEnvelopeTests(unittest.TestCase):
    def test_request_body_uses_alias_envelope_and_reads_alias_data(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request: object, timeout: float = 0) -> FakeResponse:
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["url"] = request.full_url
            captured["headers"] = dict(request.headers)
            return FakeResponse({"rows": {"data": {"commercialsEntries": []}}})

        with patch.object(aicp, "urlopen", side_effect=fake_urlopen):
            data = aicp._post_graphql("rows", "{ commercialsEntries { id } }")

        self.assertEqual(
            captured["body"],
            {"rows": {"query": "{ commercialsEntries { id } }"}})
        self.assertEqual(captured["url"], aicp.ENDPOINT)
        self.assertEqual(captured["headers"].get("Content-type"),
                         "application/json")
        self.assertEqual(data, {"commercialsEntries": []})

    def test_http_200_with_graphql_errors_raises_loudly(self) -> None:
        payload = {"rows": {"errors": [{"message": "Cannot query field"}]}}
        with patch.object(aicp, "urlopen",
                          return_value=FakeResponse(payload)):
            with self.assertRaises(ValueError) as raised:
                aicp._post_graphql("rows", "{ broken }")
        self.assertIn("GraphQL returned errors", str(raised.exception))
        self.assertIn("Cannot query field", str(raised.exception))

    def test_top_level_errors_raise(self) -> None:
        with patch.object(aicp, "urlopen", return_value=FakeResponse(
                {"errors": [{"message": "synthetic"}]})):
            with self.assertRaises(ValueError):
                aicp._post_graphql("rows", "{ x }")

    def test_missing_alias_or_data_raises(self) -> None:
        for payload in ({"other": {"data": {}}}, {"rows": {"data": None}},
                        {"rows": {}}):
            with patch.object(aicp, "urlopen",
                              return_value=FakeResponse(payload)):
                with self.assertRaises(ValueError, msg=str(payload)):
                    aicp._post_graphql("rows", "{ x }")

    def test_non_allowlisted_endpoint_is_refused_without_network(self) -> None:
        with patch.object(aicp, "urlopen") as urlopen:
            with self.assertRaises(ValueError):
                aicp._post_graphql("rows", "{ x }",
                                   endpoint="https://evil.example/api")
        urlopen.assert_not_called()


class PagingTests(unittest.TestCase):
    def _post(self, pages: list[list[dict[str, object]]]):
        calls: list[int] = []

        def fake_post(alias: str, query: str) -> dict:
            self.assertEqual(alias, "rows")
            offset = int(re.search(r"offset: (\d+)", query).group(1))
            calls.append(offset)
            page = pages[len(calls) - 1]
            return {"commercialsEntries": page}

        return fake_post, calls

    def test_offset_paging_stops_on_short_page(self) -> None:
        pages = [
            [entry_node(id="1"), entry_node(id="2", slug="two")],
            [entry_node(id="3", slug="three")],
        ]
        post, offsets = self._post(pages)
        rows = aicp.fetch_all_entries(
            post=post, page_size=2, delay_seconds=0, log=lambda _: None)
        self.assertEqual([row["id"] for row in rows], ["1", "2", "3"])
        self.assertEqual(offsets, [0, 2])

    def test_empty_page_terminates(self) -> None:
        post, offsets = self._post([[]])
        rows = aicp.fetch_all_entries(
            post=post, page_size=100, delay_seconds=0, log=lambda _: None)
        self.assertEqual(rows, [])
        self.assertEqual(offsets, [0])

    def test_limit_caps_collection_and_requests_a_smaller_page(self) -> None:
        pages = [
            [entry_node(id="1"), entry_node(id="2", slug="two")],
            [entry_node(id="3", slug="three")],
        ]
        post, offsets = self._post(pages)
        posted: list[str] = []

        def wrapped(alias: str, query: str) -> dict:
            posted.append(query)
            return post(alias, query)

        rows = aicp.fetch_all_entries(
            post=wrapped, page_size=2, limit=3, delay_seconds=0,
            log=lambda _: None)
        self.assertEqual([row["id"] for row in rows], ["1", "2", "3"])
        self.assertEqual(offsets, [0, 2])
        self.assertIn("limit: 1", posted[-1])

    def test_limit_zero_means_all_remaining(self) -> None:
        pages = [
            [entry_node(id="1"), entry_node(id="2", slug="two")],
            [entry_node(id="3", slug="three")],
        ]
        post, _ = self._post(pages)
        rows = aicp.fetch_all_entries(
            post=post, page_size=2, limit=0, delay_seconds=0,
            log=lambda _: None)
        self.assertEqual(len(rows), 3)

    def test_missing_entries_list_raises(self) -> None:
        with self.assertRaises(ValueError):
            aicp.fetch_all_entries(
                post=lambda alias, query: {"somethingElse": []},
                delay_seconds=0, log=lambda _: None)


class EntryCountTests(unittest.TestCase):
    def test_entry_count_uses_section_argument(self) -> None:
        queries: list[str] = []

        def fake_post(alias: str, query: str) -> dict:
            self.assertEqual(alias, "c")
            queries.append(query)
            return {"entryCount": "2715"}

        self.assertEqual(aicp.fetch_entry_count(post=fake_post), 2715)
        self.assertIn('section: "commercials"', queries[0])
        self.assertNotIn("collection:", queries[0])

    def test_per_year_count_uses_year_argument(self) -> None:
        queries: list[str] = []

        def fake_post(alias: str, query: str) -> dict:
            queries.append(query)
            return {"entryCount": 84}

        self.assertEqual(
            aicp.fetch_entry_count(year=2025, post=fake_post), 84)
        self.assertIn("year: 2025", queries[0])

    def test_missing_count_is_null(self) -> None:
        self.assertIsNone(
            aicp.fetch_entry_count(post=lambda alias, query: {}))

    def test_catalog_records_reported_and_collected_counts(self) -> None:
        rows = [aicp.parse_entry(entry_node(id="1")),
                aicp.parse_entry(entry_node(
                    id="2", slug="two", year=2024)),
                aicp.parse_entry(entry_node(
                    id="3", slug="three", year=None))]
        catalog = aicp.build_catalog(rows, 2715, generated_at="2026-01-01T00:00:00Z")
        self.assertEqual(catalog["schemaVersion"], aicp.CATALOG_SCHEMA)
        self.assertEqual(catalog["counts"]["totalReported"], 2715)
        self.assertEqual(catalog["counts"]["collected"], 3)
        self.assertEqual(catalog["counts"]["byYear"],
                         {"2024": 1, "2025": 1, "unknown": 1})
        self.assertEqual(len(catalog["entries"]), 3)


class DurationParsingTests(unittest.TestCase):
    def test_two_component_durations(self) -> None:
        self.assertEqual(aicp.parse_duration_text("02:29"), 149)
        self.assertEqual(aicp.parse_duration_text("0:45"), 45)
        self.assertEqual(aicp.parse_duration_text("10:00"), 600)
        self.assertEqual(aicp.parse_duration_text(" 1:31 "), 91)

    def test_three_component_durations(self) -> None:
        self.assertEqual(aicp.parse_duration_text("1:31:34"), 5494)
        self.assertEqual(aicp.parse_duration_text("0:00:05"), 5)

    def test_garbage_returns_none(self) -> None:
        for value in ("", "  ", "garbage", "1:2:3:4", "1:61", "aa:bb",
                      "-1:30", "1.5", None, 149, True):
            self.assertIsNone(aicp.parse_duration_text(value), msg=str(value))


class ParseEntryTests(unittest.TestCase):
    def test_string_id_and_relative_screenshot_join(self) -> None:
        row = aicp.parse_entry(entry_node())
        self.assertEqual(row["id"], "1185644")
        self.assertIsInstance(row["id"], str)
        self.assertEqual(row["posterUrl"],
                         "https://aicpawards.com/media/1185644.jpg")
        self.assertEqual((row["posterWidth"], row["posterHeight"]),
                         (1280, 720))
        self.assertEqual(row["durationSeconds"], 149)
        self.assertEqual(row["durationText"], "02:29")
        self.assertEqual(row["videoType"], ["Opening Title"])
        self.assertEqual(row["categories"], ["Craft"])
        self.assertEqual(row["videoDelivery"], "hls")
        self.assertTrue(row["downloadable"])
        self.assertIsNone(row["downloadReason"])

    def test_screenshot_list_and_absolute_url(self) -> None:
        row = aicp.parse_entry(entry_node(screenshot=[{
            "url": "https://aicpawards.com/media/x.jpg",
            "width": 640, "height": 360}]))
        self.assertEqual(row["posterUrl"],
                         "https://aicpawards.com/media/x.jpg")

    def test_missing_screenshot_and_company_tolerated(self) -> None:
        row = aicp.parse_entry(entry_node(screenshot=None, company=None))
        self.assertIsNone(row["posterUrl"])
        self.assertIsNone(row["company"])

    def test_long_form_type_is_not_downloadable(self) -> None:
        row = aicp.parse_entry(
            entry_node(videoType=[{"title": "Full Show Reel"}]))
        self.assertFalse(row["downloadable"])
        self.assertEqual(row["downloadReason"], "unsupported-long-form")

    def test_missing_video_is_not_downloadable(self) -> None:
        row = aicp.parse_entry(entry_node(video=None))
        self.assertFalse(row["downloadable"])
        self.assertEqual(row["downloadReason"], "no-video-url")

    def test_missing_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            aicp.parse_entry(entry_node(id=None))

    def test_article_url(self) -> None:
        self.assertEqual(
            aicp.parse_entry(entry_node())["articleUrl"],
            "https://aicpawards.com/winners-gallery/details?id=1185644")


class DeliveryClassificationTests(unittest.TestCase):
    def test_vimeo_hls_and_direct(self) -> None:
        self.assertEqual(aicp.classify_delivery(
            "https://player.vimeo.com/external/1.m3u8?s=x&logging=false"), "hls")
        self.assertEqual(aicp.classify_delivery(
            "https://vod-adaptive-ak.vimeocdn.com/abc.m3u8?exp=1"), "hls")
        self.assertEqual(aicp.classify_delivery(
            "https://example.test/clip.mp4"), "direct")
        self.assertEqual(aicp.classify_delivery(
            "https://example.test/watch"), "other")
        self.assertIsNone(aicp.classify_delivery(None))

    def test_downloadability_reason_ladder(self) -> None:
        self.assertEqual(
            aicp.downloadability(None, []), (False, "no-video-url"))
        self.assertEqual(
            aicp.downloadability("https://example.test/watch", ["Opening Title"]),
            (False, "unsupported-provider"))
        self.assertEqual(
            aicp.downloadability(
                "https://player.vimeo.com/external/1.m3u8?s=x",
                ["Full Post Show Reel"]),
            (False, "unsupported-long-form"))
        self.assertEqual(
            aicp.downloadability(
                "https://player.vimeo.com/external/1.m3u8?s=x",
                ["Opening Title"]),
            (True, None))


class SkipReasonTests(unittest.TestCase):
    def row(self, **overrides: object) -> dict[str, object]:
        row = aicp.parse_entry(entry_node())
        row.update(overrides)
        return row

    def test_long_form(self) -> None:
        self.assertEqual(
            aicp.collect_skip_reason(
                self.row(videoType=["NEXT Premiere Show"])),
            "unsupported-long-form")

    def test_duration_over_cap(self) -> None:
        self.assertEqual(
            aicp.collect_skip_reason(self.row(), max_duration_seconds=60),
            "duration-over-cap")

    def test_missing_url_and_provider(self) -> None:
        self.assertEqual(
            aicp.collect_skip_reason(self.row(videoUrl=None)), "no-video-url")
        self.assertEqual(
            aicp.collect_skip_reason(self.row(videoDelivery="direct")),
            "unsupported-provider")

    def test_commercial_length_is_collectable(self) -> None:
        self.assertIsNone(
            aicp.collect_skip_reason(self.row(), max_duration_seconds=600))

    def test_unparseable_duration_is_not_silently_capped(self) -> None:
        row = self.row(durationText="garbage", durationSeconds=None)
        self.assertIsNone(aicp.collect_skip_reason(row))


class MasterResolutionTests(unittest.TestCase):
    class _Opener:
        def __init__(self, outcomes: list[object]) -> None:
            self.outcomes = list(outcomes)
            self.calls: list[str] = []

        def open(self, request: object, timeout: float = 0) -> object:
            self.calls.append(request.full_url)
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    class _Response:
        def __init__(self, url: str) -> None:
            self.url = url

        def geturl(self) -> str:
            return self.url

        def __enter__(self) -> "MasterResolutionTests._Response":
            return self

        def __exit__(self, *_: object) -> bool:
            return False

    def test_no_redirect_returns_the_public_master(self) -> None:
        url = "https://player.vimeo.com/external/1.m3u8?s=x"
        opener = self._Opener([self._Response(url)])
        with patch.object(aicp, "build_opener", return_value=opener):
            self.assertEqual(aicp.resolve_master_url(url), url)

    def test_redirect_to_signed_cdn_returns_final_url(self) -> None:
        url = "https://player.vimeo.com/external/1.m3u8?s=x"
        signed = "https://vod-adaptive-ak.vimeocdn.com/exp=1/x/master.m3u8?pathsig=y"
        opener = self._Opener([
            HTTPError(url, 302, "Found", {"Location": signed}, None),
            self._Response(signed),
        ])
        with patch.object(aicp, "build_opener", return_value=opener):
            self.assertEqual(aicp.resolve_master_url(url), signed)

    def test_redirect_to_non_allowlisted_host_is_refused(self) -> None:
        url = "https://player.vimeo.com/external/1.m3u8?s=x"
        opener = self._Opener([
            HTTPError(url, 302, "Found",
                      {"Location": "https://evil.example/master.m3u8"}, None),
        ])
        with patch.object(aicp, "build_opener", return_value=opener):
            with self.assertRaises(ValueError):
                aicp.resolve_master_url(url)
        self.assertEqual(len(opener.calls), 1)


class ResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_resume_matches_only_the_same_string_id(self) -> None:
        record = self.root / "videos" / "1185644-demo.json"
        acq.write_json_atomic(record, {"id": "1185644"})
        self.assertTrue(aicp.resume_matches(record, "1185644"))
        self.assertFalse(aicp.resume_matches(record, "1185645"))
        self.assertFalse(aicp.resume_matches(
            self.root / "missing.json", "1185644"))

    def test_resume_leaves_existing_record_byte_and_mtime_identical(self) -> None:
        row = aicp.parse_entry(entry_node())
        catalog_path = self.root / "catalog.json"
        acq.write_json_atomic(
            catalog_path, aicp.build_catalog([row], 1, generated_at="x"))
        out_dir = self.root / "out"
        record_path = out_dir / "videos" / f"{aicp.record_stem(row)}.json"
        acq.write_json_atomic(record_path, {"id": row["id"], "sentinel": 1})
        before_bytes = record_path.read_bytes()
        before_mtime = record_path.stat().st_mtime_ns

        with patch.object(aicp, "collect_one") as collect_one:
            code = aicp.run_collect(
                catalog_path, out_dir=out_dir, resume=True,
                acknowledge_rights=True, delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 0)
        collect_one.assert_not_called()
        self.assertEqual(record_path.read_bytes(), before_bytes)
        self.assertEqual(record_path.stat().st_mtime_ns, before_mtime)
        index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schemaVersion"], aicp.INDEX_SCHEMA)
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 1, "failed": 0})
        self.assertEqual(index["skips"][0]["reason"],
                         "resume-existing-record")

    def test_collect_requires_rights_acknowledgement(self) -> None:
        with self.assertRaises(ValueError):
            aicp.run_collect(
                self.root / "missing.json", out_dir=self.root / "out",
                acknowledge_rights=False, log=lambda _: None)


def synthetic_window(cuts: int = 2, luma: float = 0.4,
                     saturation: float = 0.3) -> dict:
    return {
        "startSeconds": 0,
        "endSeconds": 10,
        "probe": {
            "sampledWindowSummary": {
                "cutCandidateCountBetweenFirstAndLastSample": cuts,
                "meanSampledDisplayLumaProxy": luma,
                "meanSampledSaturationProxy": saturation,
                "cutSeparatedPairs": 1,
            },
            "sampledFrames": [{}, {}],
            "sampledFramePairs": [
                {"meanAbsoluteDisplayRgbDeltaPerSecond": 0.5}],
        },
    }


def synthetic_video_record(
    *, entry_id: str = "1185644", slug: str = "demo-commercial",
    year: int | None = 2025, title: str = "Demo Commercial",
    company: str | None = "Demo Co",
    video_type: list[str] | None = None,
    duration: float = 20.0, cuts: int = 4, luma: float = 0.4,
    saturation: float = 0.3,
    generated_at: str = "2026-01-01T00:00:00Z",
) -> dict:
    return {
        "schemaVersion": aicp.VIDEO_SCHEMA,
        "id": entry_id,
        "slug": slug,
        "articleUrl": f"https://aicpawards.com/winners-gallery/details?id={entry_id}",
        "catalog": {
            "title": title, "year": year, "company": company,
            "durationText": "00:20", "durationSeconds": int(duration),
            "videoType": video_type if video_type is not None else ["Opening Title"],
            "categories": ["Craft"],
        },
        "source": {
            "durationSeconds": duration, "sizeBytes": 10 * 1024 * 1024,
            "resolution": [1280, 720],
            "frameRate": {"numerator": 25, "denominator": 1},
        },
        "acquisition": {"provider": "hls"},
        "coverage": {
            "windowsMeasured": 2, "windowSeconds": 10,
            "sampledSeconds": 20,
            "fractionOfRuntime": round(min(1.0, 20 / duration), 6),
        },
        "summary": {
            "cutCandidates": cuts,
            "cutCandidateRatePerMinute": round(cuts * 60 / 20, 6),
            "meanDisplayLuma": luma,
            "meanSaturation": saturation,
            "meanWithinShotRgbDeltaPerSecond": 0.5,
        },
        "windows": [synthetic_window(cuts // 2, luma, saturation)],
        "generatedAt": generated_at,
    }


def synthetic_still_record(
    *, entry_id: str = "1185644", slug: str = "demo-commercial",
    year: int | None = 2025, luma: float = 0.7, hue: str = "blue",
    generated_at: str = "2026-01-02T00:00:00Z",
) -> dict:
    return {
        "schemaVersion": aicp.STILL_SCHEMA,
        "id": entry_id,
        "slug": slug,
        "catalog": {"title": "Demo Commercial", "year": year,
                    "company": "Demo Co", "videoType": ["Opening Title"]},
        "still": {"metrics": {
            "meanDisplayLumaProxy": luma, "dominantHueFamily": hue}},
        "generatedAt": generated_at,
    }


class CollectSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _catalog(self, rows: list[dict]) -> Path:
        path = self.root / "catalog.json"
        acq.write_json_atomic(
            path, aicp.build_catalog(rows, len(rows), generated_at="x"))
        return path

    def test_long_form_is_skipped_and_commercial_is_attempted(self) -> None:
        long_form = aicp.parse_entry(entry_node(
            id="1", slug="full-show", videoType=[{"title": "Full Show Reel"}]))
        commercial = aicp.parse_entry(entry_node(
            id="2", slug="commercial", videoType=[{"title": "Opening Title"}]))
        catalog_path = self._catalog([long_form, commercial])
        out_dir = self.root / "out"
        record = synthetic_video_record(entry_id="2", slug="commercial")

        with patch.object(aicp, "collect_one", return_value=record) as collect:
            code = aicp.run_collect(
                catalog_path, out_dir=out_dir, limit=1, resume=False,
                acknowledge_rights=True, delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 0)
        collect.assert_called_once()
        self.assertEqual(collect.call_args.args[0]["id"], "2")
        index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 1, "failed": 0})
        self.assertEqual(index["skips"][0]["reason"], "unsupported-long-form")

    def test_limit_zero_runs_all_remaining(self) -> None:
        first = aicp.parse_entry(entry_node(id="1", slug="one"))
        second = aicp.parse_entry(entry_node(id="2", slug="two"))
        catalog_path = self._catalog([first, second])
        out_dir = self.root / "out"

        def fake_collect(row: dict, _out_dir: Path, **_: object) -> dict:
            return synthetic_video_record(
                entry_id=str(row["id"]), slug=str(row["slug"]))

        with patch.object(aicp, "collect_one", side_effect=fake_collect) as collect:
            code = aicp.run_collect(
                catalog_path, out_dir=out_dir, limit=0, resume=False,
                acknowledge_rights=True, delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 0)
        self.assertEqual(collect.call_count, 2)
        index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"]["measured"], 2)

    def test_duration_over_cap_is_skipped_before_download(self) -> None:
        long_row = aicp.parse_entry(entry_node(
            id="1", slug="long", duration="20:00"))
        catalog_path = self._catalog([long_row])
        out_dir = self.root / "out"
        with patch.object(aicp, "collect_one") as collect:
            code = aicp.run_collect(
                catalog_path, out_dir=out_dir, resume=False,
                acknowledge_rights=True, delay_seconds=0,
                max_duration_seconds=600, log=lambda _: None)
        self.assertEqual(code, 0)
        collect.assert_not_called()
        index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["skips"][0]["reason"], "duration-over-cap")


class DownloadLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.out_dir = self.root / "out"
        self.row = aicp.parse_entry(entry_node())

    def _capture_scratch(self) -> tuple[Callable, list[Path]]:
        created: list[Path] = []
        real_mkdtemp = tempfile.mkdtemp

        def fake_mkdtemp(prefix: str = "tmp") -> str:
            path = Path(real_mkdtemp(prefix=prefix, dir=self.scratch))
            created.append(path)
            return str(path)

        return fake_mkdtemp, created

    def test_failed_download_deletes_scratch_and_writes_no_record(self) -> None:
        fake_mkdtemp, created = self._capture_scratch()
        with patch.object(aicp.tempfile, "mkdtemp", side_effect=fake_mkdtemp), \
                patch.object(aicp, "resolve_master_url",
                             return_value=self.row["videoUrl"]), \
                patch.object(aicp, "download_media",
                             side_effect=ValueError("synthetic download failure")):
            with self.assertRaises(aicp.DownloadFailed):
                aicp.collect_one(self.row, self.out_dir)

        self.assertTrue(created)
        self.assertFalse(created[0].exists())
        self.assertEqual(list(self.out_dir.rglob("*.mp4")), [])
        videos = self.out_dir / "videos"
        self.assertEqual(list(videos.iterdir()) if videos.exists() else [], [])

    def test_measurement_failure_after_download_leaves_no_media_or_record(self) -> None:
        fake_mkdtemp, created = self._capture_scratch()

        def fake_download(url: str, provider: str, directory: Path,
                          **_: object):
            target = directory / "source.mp4"
            target.write_bytes(b"\x00" * 2048)
            return target, "ffmpeg-hls-copy"

        with patch.object(aicp.tempfile, "mkdtemp", side_effect=fake_mkdtemp), \
                patch.object(aicp, "resolve_master_url",
                             return_value=self.row["videoUrl"]), \
                patch.object(aicp, "download_media", side_effect=fake_download), \
                patch.object(aicp, "source_metadata",
                             side_effect=ValueError("synthetic probe failure")):
            with self.assertRaises(aicp.ProbeFailed):
                aicp.collect_one(self.row, self.out_dir)

        self.assertTrue(created)
        self.assertFalse(created[0].exists())
        self.assertEqual(list(self.out_dir.rglob("*.mp4")), [])
        videos = self.out_dir / "videos"
        self.assertEqual(list(videos.iterdir()) if videos.exists() else [], [])

    def test_success_writes_record_and_deletes_media(self) -> None:
        fake_mkdtemp, created = self._capture_scratch()

        def fake_download(url: str, provider: str, directory: Path,
                          **_: object):
            self.assertEqual(provider, acq.HLS)
            target = directory / "source.mp4"
            target.write_bytes(b"\x00" * 2048)
            return target, "ffmpeg-hls-copy"

        source = {
            "mediaSha256": "a" * 64, "sizeBytes": 2048,
            "durationSeconds": 20.0, "resolution": [1280, 720],
            "frameRate": {"numerator": 25, "denominator": 1},
            "sourceTimebase": {"numerator": 1, "denominator": 12800},
            "container": "mp4", "videoCodec": "h264",
            "audioCodec": "aac", "hasAudio": True,
        }
        coverage = {
            "windowsMeasured": 1, "windowSeconds": 10, "sampledSeconds": 10,
            "fractionOfRuntime": 0.5, "fullRuntimeMeasured": False,
            "note": "synthetic",
        }
        with patch.object(aicp.tempfile, "mkdtemp", side_effect=fake_mkdtemp), \
                patch.object(aicp, "resolve_master_url",
                             return_value=self.row["videoUrl"]), \
                patch.object(aicp, "download_media", side_effect=fake_download), \
                patch.object(aicp, "source_metadata", return_value=source), \
                patch.object(aicp, "measure_windows",
                             return_value=(coverage, [synthetic_window()])):
            record = aicp.collect_one(self.row, self.out_dir)

        self.assertEqual(record["schemaVersion"], aicp.VIDEO_SCHEMA)
        self.assertEqual(record["id"], "1185644")
        self.assertFalse(record["acquisition"]["mediaRetained"])
        record_path = (self.out_dir / "videos"
                       / f"{aicp.record_stem(self.row)}.json")
        self.assertTrue(record_path.is_file())
        self.assertFalse(created[0].exists())
        self.assertEqual(list(self.out_dir.rglob("*.mp4")), [])

    def test_failure_reasons_are_classified(self) -> None:
        render = aicp._error_text(self.out_dir)
        self.assertTrue(render(aicp.DownloadFailed("boom"))
                        .startswith("download-failed: "))
        self.assertTrue(render(aicp.ProbeFailed("boom"))
                        .startswith("probe-failed: "))
        self.assertIn("[redacted-url]",
                      render(aicp.DownloadFailed(
                          "failed https://player.vimeo.com/x.m3u8?s=secret")))

    def test_policy_rejection_never_downloads(self) -> None:
        row = dict(self.row, videoUrl=None)
        with patch.object(aicp, "download_media") as download:
            with self.assertRaises(ValueError):
                aicp.collect_one(row, self.out_dir)
        download.assert_not_called()


class StillsRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _catalog(self, rows: list[dict]) -> Path:
        path = self.root / "catalog.json"
        acq.write_json_atomic(
            path, aicp.build_catalog(rows, len(rows), generated_at="x"))
        return path

    def test_resume_skips_existing_still_and_writes_atomic_index(self) -> None:
        row = aicp.parse_entry(entry_node())
        catalog_path = self._catalog([row])
        out_dir = self.root / "out"
        record_path = out_dir / "stills" / f"{aicp.record_stem(row)}.json"
        acq.write_json_atomic(record_path, {"id": row["id"]})

        with patch.object(aicp, "collect_still_one") as collect:
            code = aicp.run_stills(
                catalog_path, out_dir=out_dir, resume=True,
                delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 0)
        collect.assert_not_called()
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schemaVersion"], aicp.STILLS_INDEX_SCHEMA)
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 1, "failed": 0})
        self.assertEqual(index["skips"][0]["reason"],
                         "resume-existing-record")
        self.assertEqual(sorted(path.name for path in out_dir.iterdir()),
                         ["stills", "stills-index.json"])
        self.assertEqual(
            sorted(path.name for path in (out_dir / "stills").iterdir()),
            [f"{aicp.record_stem(row)}.json"])

    def test_refresh_measures_and_indexes_a_still_row(self) -> None:
        row = aicp.parse_entry(entry_node())
        catalog_path = self._catalog([row])
        out_dir = self.root / "out"
        record = synthetic_still_record()
        with patch.object(aicp, "collect_still_one",
                          return_value=record) as collect:
            code = aicp.run_stills(
                catalog_path, out_dir=out_dir, resume=False,
                delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 0)
        collect.assert_called_once()
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 0, "failed": 0})
        self.assertEqual(index["records"][0]["dominantHueFamily"], "blue")
        self.assertEqual(index["records"][0]["recordPath"],
                         f"stills/{aicp.record_stem(row)}.json")

    def test_entry_without_screenshot_is_skipped(self) -> None:
        row = aicp.parse_entry(entry_node(screenshot=None))
        catalog_path = self._catalog([row])
        out_dir = self.root / "out"
        with patch.object(aicp, "collect_still_one") as collect:
            code = aicp.run_stills(
                catalog_path, out_dir=out_dir, delay_seconds=0,
                log=lambda _: None)
        self.assertEqual(code, 0)
        collect.assert_not_called()
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["skips"][0]["reason"], "no-poster")

    def test_still_record_declares_not_a_video_frame(self) -> None:
        row = aicp.parse_entry(entry_node())
        record = aicp.build_still_record(row, still={
            "imageUrl": row["posterUrl"], "imageSha256": "a" * 64,
            "imageFormat": "jpg", "imageBytes": 1024,
            "imageWidth": 1280, "imageHeight": 720,
            "metrics": {"meanDisplayLumaProxy": 0.4,
                        "dominantHueFamily": "blue"}},
            generated_at="2026-01-01T00:00:00Z")
        self.assertEqual(record["schemaVersion"], aicp.STILL_SCHEMA)
        self.assertFalse(record["coverage"]["isSourceVideoFrame"])
        self.assertFalse(record["acquisition"]["imageRetained"])
        self.assertEqual(record["evidenceStatus"],
                         "single-published-still-metrics-not-video-measurement")


class ReportTests(unittest.TestCase):
    """The report is read-only, deterministic, and never mixes still evidence."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_video(self, out_dir: Path, record: dict) -> None:
        acq.write_json_atomic(
            out_dir / "videos" / f"{aicp.record_stem(record)}.json", record)

    def write_still(self, out_dir: Path, record: dict) -> None:
        acq.write_json_atomic(
            out_dir / "stills" / f"{aicp.record_stem(record)}.json", record)

    def test_empty_state_writes_valid_skeleton(self) -> None:
        out_dir = self.root / "out"
        code = aicp.run_report(out_dir, log=lambda _: None)
        self.assertEqual(code, 0)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["schemaVersion"], aicp.AGGREGATE_SCHEMA)
        self.assertEqual(aggregate["counts"]["videoMeasured"], 0)
        self.assertEqual(aggregate["videos"], [])
        self.assertEqual(aggregate["stills"]["n"], 0)
        self.assertIn("No video-measured records.", report)
        self.assertIn("None.", report)
        self.assertEqual(sorted(path.name for path in out_dir.iterdir()),
                         ["aggregate.json", "report.md"])

    def test_still_only_records_never_enter_motion_aggregates(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(
            entry_id="1", slug="measured", luma=0.2, saturation=0.1, cuts=4))
        self.write_still(out_dir, synthetic_still_record(
            entry_id="1", slug="measured", luma=0.9, hue="blue"))
        self.write_still(out_dir, synthetic_still_record(
            entry_id="2", slug="still-only", luma=0.9, hue="red"))

        code = aicp.run_report(out_dir, log=lambda _: None)
        self.assertEqual(code, 0)
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
        # The still-only id is absent from the video table.
        self.assertEqual([row["id"] for row in aggregate["videos"]], ["1"])

    def test_repeat_runs_are_byte_identical(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(
            entry_id="1", slug="a", year=2025))
        self.write_video(out_dir, synthetic_video_record(
            entry_id="2", slug="b", year=2024, luma=0.6))
        self.write_still(out_dir, synthetic_still_record(
            entry_id="3", slug="c", year=2023))

        aicp.run_report(out_dir, top=2, log=lambda _: None)
        first_report = (out_dir / "report.md").read_bytes()
        first_aggregate = (out_dir / "aggregate.json").read_bytes()
        aicp.run_report(out_dir, top=2, log=lambda _: None)

        self.assertEqual((out_dir / "report.md").read_bytes(), first_report)
        self.assertEqual((out_dir / "aggregate.json").read_bytes(),
                         first_aggregate)

    def test_order_is_year_descending_then_title(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(
            entry_id="1", slug="older", year=2024, title="B older"))
        self.write_video(out_dir, synthetic_video_record(
            entry_id="2", slug="newer", year=2025, title="A newer"))
        self.write_video(out_dir, synthetic_video_record(
            entry_id="3", slug="unknown", year=None, title="C unknown"))
        aicp.run_report(out_dir, log=lambda _: None)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in aggregate["videos"]],
                         ["2", "1", "3"])
        self.assertEqual(aggregate["aggregates"]["byYear"],
                         {"2024": 1, "2025": 1, "unknown": 1})

    def test_catalog_counts_are_reported(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record())
        acq.write_json_atomic(out_dir / "catalog.json", {
            "schemaVersion": aicp.CATALOG_SCHEMA,
            "generatedAt": "2026-01-03T00:00:00Z",
            "counts": {"totalReported": 2715, "collected": 1},
            "entries": []})
        aicp.run_report(out_dir, log=lambda _: None)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["counts"]["catalogTotalReported"], 2715)
        self.assertEqual(aggregate["counts"]["catalogCollected"], 1)
        self.assertEqual(aggregate["generatedAt"], "2026-01-01T00:00:00Z")

    def test_malformed_records_are_listed_and_do_not_stop_the_report(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(entry_id="1", slug="good"))
        (out_dir / "videos" / "broken.json").write_text(
            "{not json", encoding="utf-8")
        acq.write_json_atomic(out_dir / "videos" / "wrong-schema.json",
                              {"schemaVersion": "kumiki.other.v1"})

        code = aicp.run_report(out_dir, log=lambda _: None)
        self.assertEqual(code, 0)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["counts"]["videoMeasured"], 1)
        self.assertEqual(aggregate["counts"]["unreadable"], 2)
        files = sorted(item["file"] for item in aggregate["unreadableRecords"])
        self.assertEqual(files, ["videos/broken.json", "videos/wrong-schema.json"])

    def test_number_formatting_and_bitrate_derivation(self) -> None:
        self.assertEqual(aicp._num(None, 4), "—")
        self.assertEqual(aicp._num(0.123456789, 4), "0.1235")
        self.assertEqual(aicp._int(None), "—")
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(
            entry_id="1", slug="numbers", duration=20.0))
        aicp.run_report(out_dir, log=lambda _: None)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        row = next(line for line in report.splitlines()
                   if line.startswith("| 2025 | Demo Commercial |"))
        self.assertIn("| 20.00 |", row)
        self.assertIn("| 25.000 |", row)
        self.assertIn("| 4.19 |", row)   # 10 MiB / 20 s
        self.assertIn("| 0.4000 |", row)
        self.assertIn("| 0.3000 |", row)

    def test_report_is_read_only_for_records(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record())
        record_path = next((out_dir / "videos").glob("*.json"))
        before = (record_path.read_bytes(), record_path.stat().st_mtime_ns)
        aicp.run_report(out_dir, log=lambda _: None)
        self.assertEqual((record_path.read_bytes(),
                          record_path.stat().st_mtime_ns), before)


class ByteSizeTests(unittest.TestCase):
    def test_parses_suffixes_and_integers(self) -> None:
        self.assertEqual(aicp.parse_byte_size("250MiB"), 250 * 1024 ** 2)
        self.assertEqual(aicp.parse_byte_size("250M"), 250 * 1024 ** 2)
        self.assertEqual(aicp.parse_byte_size(1024), 1024)
        with self.assertRaises(ValueError):
            aicp.parse_byte_size("banana")
        with self.assertRaises(ValueError):
            aicp.parse_byte_size(0)


class CatalogRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_run_catalog_writes_atomic_slim_catalog(self) -> None:
        out_path = self.root / "catalog.json"

        def fake_post(alias: str, query: str) -> dict:
            if alias == "c":
                return {"entryCount": 2}
            return {"commercialsEntries": [
                entry_node(id="1"), entry_node(id="2", slug="two")]}

        catalog = aicp.run_catalog(
            out_path, delay_seconds=0, post=fake_post, log=lambda _: None)
        self.assertEqual(catalog["counts"],
                         {"totalReported": 2, "collected": 2,
                          "byYear": {"2025": 2},
                          "byVideoType": {"Opening Title": 2},
                          "downloadable": 2, "notDownloadable": 0})
        stored = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(stored, catalog)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()),
                         ["catalog.json"])
        self.assertEqual(stored["entries"][0]["id"], "1")


if __name__ == "__main__":
    unittest.main()
