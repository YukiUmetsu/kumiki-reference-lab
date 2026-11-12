"""Offline tests for the Motion Design Awards ephemeral research collector."""

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
from kumiki_reference_lab.acquisition import probe as acq_probe
from scripts import research_motiondesignawards as mda

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "analysis" / "motiondesignawards"


def catalog_node(**overrides: object) -> dict[str, object]:
    node: dict[str, object] = {
        "id": 42,
        "slug": "demo-film",
        "title": "Demo Film",
        "video": "https://customer-demo.cloudflarestream.com/uid/manifest/video.m3u8",
        "video_provider": "Cloudflare Stream",
        "wa_overall": 8.5,
        "wa_concept": 8.0,
        "wa_design": 9.0,
        "wa_motion": 8.25,
        "wa_sound": 7.5,
        "total_votes": 12,
        "category": "Branding",
        "status": "published",
        "is_nominee": True,
        "is_incubating": False,
        "created_at": "2024-05-01T10:00:00Z",
        "voting_closed_at": "2024-06-01T10:00:00Z",
        "project_website": "https://studio.example/demo",
        "credits": {"team_size": "6", "budget_size": "medium"},
        "profile": {"id": 7, "company": "Demo Studio"},
        "awards": [{"id": 1, "type": "VOTD", "date": "2024-06-02"}],
        "tags": [{"id": 3, "title": "3d"}, {"id": 4, "title": "typography"}],
    }
    node.update(overrides)
    return node


def page(nodes: list[dict[str, object]], *, page_number: int, total: int,
         has_more: bool) -> dict[str, object]:
    return {"data": {"allProjects": {
        "paginatorInfo": {
            "total": total, "hasMorePages": has_more, "currentPage": page_number},
        "data": nodes,
    }}}


def project_row(project_id: str, *, overall: float | None, created: str | None,
                awards: list[dict[str, str]] | None = None,
                provider: str = "cloudflare-stream",
                downloadable: bool = True) -> dict[str, object]:
    return {
        "projectId": project_id,
        "slug": f"film-{project_id}",
        "videoUrl": "https://customer-demo.cloudflarestream.com/uid/manifest/video.m3u8",
        "provider": provider,
        "downloadable": downloadable,
        "scores": {"overall": overall},
        "createdAt": created,
        "awards": awards or [],
    }


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


class ProviderClassificationTests(unittest.TestCase):
    def test_cloudflare_and_proxy_hosts(self) -> None:
        self.assertEqual(
            mda.classify_provider(
                "https://customer-a1.cloudflarestream.com/uid/manifest/video.m3u8"),
            "cloudflare-stream")
        self.assertEqual(
            mda.classify_provider("https://videodelivery.net/uid/manifest/video.m3u8"),
            "cloudflare-stream")

    def test_direct_mp4_by_path_extension(self) -> None:
        self.assertEqual(
            mda.classify_provider("https://storage-01-mda.keyfram.es/a/b.mp4"),
            "direct-mp4")
        self.assertEqual(
            mda.classify_provider("https://example.test/clip.MOV?token=1"),
            "direct-mp4")

    def test_vimeo_and_other(self) -> None:
        self.assertEqual(mda.classify_provider("https://vimeo.com/12345"), "vimeo")
        self.assertEqual(
            mda.classify_provider("https://player.vimeo.com/video/12345"), "vimeo")
        self.assertEqual(mda.classify_provider("https://example.test/watch"), "other")
        self.assertEqual(mda.classify_provider(None), "other")


class CatalogParsingTests(unittest.TestCase):
    def test_single_page_parsing_and_mapping(self) -> None:
        calls: list[tuple[str, dict]] = []

        def fake_post(query: str, variables: dict) -> dict:
            calls.append((query, variables))
            return page([catalog_node()], page_number=1, total=1, has_more=False)

        projects, total = mda.fetch_all_projects(post=fake_post, log=lambda _: None)
        self.assertEqual(total, 1)
        self.assertEqual(len(projects), 1)
        self.assertEqual(calls[0][1], {"first": 100, "page": 1})
        self.assertIn("allProjects", calls[0][0])

        parsed = projects[0]
        self.assertEqual(parsed["projectId"], "42")
        self.assertEqual(parsed["provider"], "cloudflare-stream")
        self.assertTrue(parsed["downloadable"])
        self.assertEqual(
            parsed["projectUrl"],
            "https://www.motiondesignawards.com/project/42/demo-film")
        self.assertEqual(parsed["scores"]["motion"], 8.25)
        self.assertEqual(parsed["studio"], "Demo Studio")
        self.assertEqual(parsed["teamSize"], "6")
        self.assertEqual(parsed["budgetSize"], "medium")
        self.assertEqual([a["type"] for a in parsed["awards"]], ["VOTD"])
        self.assertEqual(parsed["tags"], ["3d", "typography"])

    def test_pagination_stops_on_has_more_pages_false(self) -> None:
        pages = [
            page([catalog_node(id=1), catalog_node(id=2)],
                 page_number=1, total=3, has_more=True),
            page([catalog_node(id=3)], page_number=2, total=3, has_more=False),
        ]

        def fake_post(query: str, variables: dict) -> dict:
            return pages[variables["page"] - 1]

        projects, total = mda.fetch_all_projects(post=fake_post, log=lambda _: None)
        self.assertEqual(len(projects), 3)
        self.assertEqual([p["projectId"] for p in projects], ["1", "2", "3"])
        self.assertEqual(total, 3)

    def test_vimeo_project_is_not_downloadable(self) -> None:
        parsed = mda.parse_project_node(
            catalog_node(video="https://vimeo.com/999"))
        self.assertEqual(parsed["provider"], "vimeo")
        self.assertFalse(parsed["downloadable"])

    def test_poster_url_mapping_and_absence(self) -> None:
        parsed = mda.parse_project_node(catalog_node(thumbnail={
            "src": "data:image/gif;base64,R0lGOD",
            "original": "https://storage-01-mda.keyfram.es/p/42/poster.png",
        }))
        self.assertEqual(
            parsed["posterUrl"],
            "https://storage-01-mda.keyfram.es/p/42/poster.png")
        # Older catalogs have no thumbnail field; absence must be tolerated.
        self.assertIsNone(mda.parse_project_node(catalog_node())["posterUrl"])

    def test_catalog_provider_counts(self) -> None:
        catalog = mda.build_catalog([
            {"provider": "vimeo"},
            {"provider": "cloudflare-stream"},
            {"provider": "cloudflare-stream"},
            {"provider": "direct-mp4"},
        ], 4, retrieved_at="2024-01-01T00:00:00Z")
        self.assertEqual(catalog["schemaVersion"], mda.CATALOG_SCHEMA)
        self.assertEqual(catalog["providerCounts"], {
            "vimeo": 1, "cloudflare-stream": 2, "direct-mp4": 1})
        self.assertEqual(catalog["totalProjects"], 4)


class SelectionOrderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            project_row("10", overall=7.0, created="2024-01-01T00:00:00Z"),
            project_row("20", overall=9.0, created="2024-03-01T00:00:00Z",
                        awards=[{"type": "VOTD", "date": None}]),
            project_row("30", overall=8.0, created="2024-02-01T00:00:00Z",
                        awards=[{"type": "HM", "date": None}]),
            project_row("40", overall=7.0, created="2024-04-01T00:00:00Z"),
        ]

    def chosen(self, order: str) -> list[str]:
        chosen, _ = mda.select_projects(self.rows, order=order)
        return [row["projectId"] for row in chosen]

    def test_best_orders_by_overall_with_numeric_tiebreak_desc(self) -> None:
        self.assertEqual(self.chosen("best"), ["20", "30", "40", "10"])

    def test_latest_orders_by_created_at_desc(self) -> None:
        self.assertEqual(self.chosen("latest"), ["40", "20", "30", "10"])

    def test_awards_first_then_overall_then_id(self) -> None:
        self.assertEqual(self.chosen("awards-first"), ["20", "30", "40", "10"])

    def test_limit_counts_only_supported_projects(self) -> None:
        rows = [
            project_row("1", overall=9.0, created=None),
            project_row("2", overall=8.0, created=None, provider="vimeo",
                        downloadable=False),
            project_row("3", overall=7.0, created=None),
        ]
        chosen, skips = mda.select_projects(rows, order="best", limit=2)
        self.assertEqual([row["projectId"] for row in chosen], ["1", "3"])
        self.assertEqual(len(skips), 1)
        self.assertEqual(skips[0]["reason"], "unsupported-vimeo")


class WindowAndSummaryTests(unittest.TestCase):
    def test_window_plan_starts_at_zero_and_skips_trailing_decile(self) -> None:
        span, count, starts, fraction = acq.plan_windows(45.2, count=4, seconds=10)
        self.assertEqual((span, count), (10, 4))
        self.assertEqual(starts[0], 0)
        self.assertLessEqual(starts[-1] + span, 45.2 * 0.9)
        self.assertAlmostEqual(fraction, round(40 / 45.2, 6))

    def test_windows_are_non_overlapping(self) -> None:
        span, count, starts, _ = acq.plan_windows(120.0, count=4, seconds=10)
        self.assertEqual(count, 4)
        for earlier, later in zip(starts, starts[1:]):
            self.assertGreaterEqual(later, earlier + span)

    def test_short_source_collapses_to_one_window(self) -> None:
        span, count, starts, _ = acq.plan_windows(8.0, count=4, seconds=10)
        self.assertEqual((span, count, starts), (7, 1, [0]))

    def test_summary_derives_only_from_probe_fields(self) -> None:
        probes = [
            synthetic_probe(2, 0.5, 0.25, 3, [1.0, 3.0, None]),
            synthetic_probe(0, 0.7, 0.35, 2, [2.0]),
        ]
        summary = acq.summarize_probes(probes, sampled_seconds=20.0)
        self.assertEqual(summary["cutCandidates"], 2)
        self.assertAlmostEqual(summary["cutCandidateRatePerMinute"], 6.0)
        self.assertAlmostEqual(summary["meanDisplayLuma"], 0.6)
        self.assertAlmostEqual(summary["meanSaturation"], 0.3)
        self.assertAlmostEqual(summary["meanWithinShotRgbDeltaPerSecond"], 2.0)
        self.assertEqual(summary["sampledFrames"], 5)
        self.assertEqual(summary["windowsWithCuts"], 1)

    def test_missing_probe_fields_become_null(self) -> None:
        summary = acq.summarize_probes(
            [{"sampledWindowSummary": {}, "sampledFrames": [], "sampledFramePairs": []}],
            sampled_seconds=10.0)
        self.assertEqual(summary["cutCandidates"], 0)
        self.assertEqual(summary["cutCandidateRatePerMinute"], 0.0)
        self.assertIsNone(summary["meanDisplayLuma"])
        self.assertIsNone(summary["meanSaturation"])
        self.assertIsNone(summary["meanWithinShotRgbDeltaPerSecond"])


class UrlAllowlistTests(unittest.TestCase):
    def test_approved_hosts(self) -> None:
        for url in (
            "https://customer-a.cloudflarestream.com/uid/manifest/video.m3u8",
            "https://videodelivery.net/uid/manifest/video.m3u8",
            "https://storage-01-mda.keyfram.es/path/clip.mp4",
        ):
            self.assertEqual(
                acq.allowlisted_video_url(url, allowed_hosts=mda.VIDEO_HOSTS), url)

    def test_rejected_schemes_hosts_and_forms(self) -> None:
        for url in (
            "http://customer-a.cloudflarestream.com/uid/manifest/video.m3u8",
            "https://customer-a.cloudflarestream.com.evil.example/video.m3u8",
            "https://evil.example/customer-a.cloudflarestream.com/video.m3u8",
            "https://storage-01-mda.keyfram.es.evil.example/clip.mp4",
            "https://user:pass@customer-a.cloudflarestream.com/video.m3u8",
            "https://customer-a.cloudflarestream.com:8443/video.m3u8",
            "https://videodelivery.net/uid/manifest/video.m3u8#fragment",
            "ftp://videodelivery.net/video.m3u8",
            "",
            None,
        ):
            with self.assertRaises(ValueError, msg=str(url)):
                acq.allowlisted_video_url(url, allowed_hosts=mda.VIDEO_HOSTS)


class ImageUrlAllowlistTests(unittest.TestCase):
    def test_accepts_https_storage_hosted_poster(self) -> None:
        for url in (
            "https://storage-01-mda.keyfram.es/p/7958/2751/"
            "61fb8c3ed18cbc73a1b426f55dac4842.png",
            "https://storage-01-mda.keyfram.es/p/1/2/poster.jpg",
        ):
            self.assertEqual(
                acq.allowlisted_image_url(url, allowed_hosts=mda.IMAGE_HOSTS), url)

    def test_rejects_http_and_other_hosts(self) -> None:
        for url in (
            "http://storage-01-mda.keyfram.es/p/1/poster.png",
            "https://evil.example/poster.png",
            "https://storage-01-mda.keyfram.es.evil.example/poster.png",
            "https://user:pass@storage-01-mda.keyfram.es/poster.png",
            "https://storage-01-mda.keyfram.es:8443/poster.png",
            "https://storage-01-mda.keyfram.es/poster.png#frag",
            "ftp://storage-01-mda.keyfram.es/poster.png",
            "",
            None,
        ):
            with self.assertRaises(ValueError, msg=str(url)):
                acq.allowlisted_image_url(url, allowed_hosts=mda.IMAGE_HOSTS)


def rgb_buffer(width: int, height: int,
               pixel: "callable[[int, int], tuple[int, int, int]]") -> bytes:
    return bytes(
        component
        for y in range(height)
        for x in range(width)
        for component in pixel(x, y)
    )


class StillMetricTests(unittest.TestCase):
    def test_metrics_on_solid_synthetic_rgb_buffer(self) -> None:
        buffer = rgb_buffer(64, 36, lambda _x, _y: (0, 0, 255))
        metrics = acq.compute_still_metrics(buffer, width=64, height=36)
        self.assertEqual(metrics["meanRgb"], [0.0, 0.0, 1.0])
        self.assertAlmostEqual(metrics["meanDisplayLumaProxy"], 0.0722, places=4)
        self.assertEqual(metrics["meanSaturationProxy"], 1.0)
        self.assertEqual(metrics["dominantHueFamily"], "blue")
        self.assertEqual(metrics["edgeDensityProxy"], 0.0)
        self.assertEqual(len(metrics["lumaHistogram"]), 5)
        self.assertAlmostEqual(sum(metrics["lumaHistogram"]), 1.0, places=5)
        # luma 0.0722 -> bucket 0 only
        self.assertEqual(metrics["lumaHistogram"][0], 1.0)

    def test_histogram_edge_density_and_neutral_hue(self) -> None:
        buffer = rgb_buffer(64, 36, lambda _x, y: (0, 0, 0) if y < 18 else (255, 255, 255))
        metrics = acq.compute_still_metrics(buffer, width=64, height=36)
        self.assertAlmostEqual(metrics["meanDisplayLumaProxy"], 0.5, places=4)
        self.assertEqual(metrics["dominantHueFamily"], "neutral")
        self.assertGreater(metrics["edgeDensityProxy"], 0.0)
        self.assertEqual(metrics["lumaHistogram"][0], 0.5)
        self.assertEqual(metrics["lumaHistogram"][4], 0.5)
        self.assertAlmostEqual(sum(metrics["lumaHistogram"]), 1.0, places=5)

    def test_hue_family_buckets(self) -> None:
        self.assertEqual(acq.dominant_hue_family([0.5, 0.5, 0.5]), "neutral")
        self.assertEqual(acq.dominant_hue_family([0.0, 0.0, 0.0]), "neutral")
        self.assertEqual(acq.dominant_hue_family([1.0, 0.0, 0.0]), "red")
        self.assertEqual(acq.dominant_hue_family([0.0, 1.0, 0.0]), "green")
        self.assertEqual(acq.dominant_hue_family([0.0, 0.0, 1.0]), "blue")
        self.assertEqual(acq.dominant_hue_family([1.0, 0.0, 1.0]), "magenta")


class AtomicWriteAndResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_atomic_write_leaves_no_staging_file(self) -> None:
        target = self.root / "nested" / "record.json"
        acq.write_json_atomic(target, {"schemaVersion": "x", "value": 1})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["value"], 1)
        self.assertEqual(sorted(p.name for p in target.parent.iterdir()),
                         ["record.json"])

    def test_resume_matches_only_the_same_project_id(self) -> None:
        record = self.root / "videos" / "demo.json"
        acq.write_json_atomic(record, {"projectId": "42"})
        self.assertTrue(mda.resume_matches(record, "42"))
        self.assertFalse(mda.resume_matches(record, "43"))
        self.assertFalse(mda.resume_matches(self.root / "missing.json", "42"))

    def test_run_collect_resume_skips_existing_record(self) -> None:
        row = mda.parse_project_node(catalog_node())
        catalog = mda.build_catalog([row], 1)
        catalog_path = self.root / "catalog.json"
        acq.write_json_atomic(catalog_path, catalog)
        out_dir = self.root / "out"
        record_path = out_dir / "videos" / f"{mda.safe_slug(row['slug'])}.json"
        acq.write_json_atomic(record_path, {"projectId": row["projectId"]})

        with patch.object(mda, "collect_one") as collect_one:
            code = mda.run_collect(
                catalog_path, out_dir=out_dir, resume=True,
                acknowledge_rights=True, log=lambda _: None)
        self.assertEqual(code, 0)
        collect_one.assert_not_called()
        index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schemaVersion"], mda.INDEX_SCHEMA)
        self.assertEqual(index["counts"], {"measured": 0, "skipped": 1, "failed": 0})
        self.assertEqual(index["skips"][0]["reason"], "resume-existing-record")
        self.assertEqual(index["catalogSha256"], mda.sha256_file(catalog_path))

    def test_run_collect_requires_rights_acknowledgement(self) -> None:
        with self.assertRaises(ValueError):
            mda.run_collect(self.root / "missing.json", out_dir=self.root / "out",
                            acknowledge_rights=False, log=lambda _: None)

    def test_run_collect_progress_line_keeps_operator_format(self) -> None:
        row = mda.parse_project_node(catalog_node())
        catalog_path = self.root / "catalog.json"
        acq.write_json_atomic(catalog_path, mda.build_catalog([row], 1))
        out_dir = self.root / "out"
        record = {
            "schemaVersion": mda.VIDEO_SCHEMA,
            "projectId": row["projectId"], "slug": row["slug"],
            "projectUrl": row["projectUrl"],
            "catalog": {"title": row["title"], "studio": row["studio"],
                        "category": row["category"],
                        "scores": row["scores"], "awards": [], "tags": []},
            "source": {"resolution": [1280, 720], "durationSeconds": 12.0,
                       "sizeBytes": 2 * 1024 * 1024, "mediaSha256": "a" * 64},
            "coverage": {"windowsMeasured": 1},
            "summary": {"cutCandidates": 3, "cutCandidateRatePerMinute": 15.0,
                        "meanDisplayLuma": 0.4, "meanSaturation": 0.2},
        }
        buffer = io.StringIO()
        with patch.object(mda, "collect_one", return_value=record), \
                contextlib.redirect_stdout(buffer):
            code = mda.run_collect(
                catalog_path, out_dir=out_dir, resume=True,
                acknowledge_rights=True, delay_seconds=0, log=lambda _: None)
        self.assertEqual(code, 0)
        self.assertIn("[1/1] ok demo-film 1280x720 12.0s 2.0MB cuts=3",
                      buffer.getvalue())
        index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"], {"measured": 1, "skipped": 0, "failed": 0})
        self.assertEqual(index["records"][0]["recordPath"], "videos/demo-film.json")


class DownloadFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.out_dir = self.root / "out"
        self.project = mda.parse_project_node(catalog_node())

    def test_failed_download_deletes_scratch_and_writes_no_record(self) -> None:
        created: list[Path] = []
        real_mkdtemp = tempfile.mkdtemp

        def fake_mkdtemp(prefix: str = "tmp") -> str:
            path = Path(real_mkdtemp(prefix=prefix, dir=self.scratch))
            created.append(path)
            return str(path)

        with patch.object(mda.tempfile, "mkdtemp", side_effect=fake_mkdtemp), \
                patch.object(mda, "download_media",
                             side_effect=ValueError("synthetic download failure")):
            with self.assertRaises(ValueError):
                mda.collect_one(self.project, self.out_dir)

        self.assertTrue(created)
        self.assertFalse(created[0].exists())
        self.assertEqual(list(self.out_dir.rglob("*.mp4")), [])
        videos = self.out_dir / "videos"
        self.assertEqual(list(videos.iterdir()) if videos.exists() else [], [])

    def test_measurement_failure_after_download_leaves_no_media(self) -> None:
        created: list[Path] = []
        real_mkdtemp = tempfile.mkdtemp

        def fake_mkdtemp(prefix: str = "tmp") -> str:
            path = Path(real_mkdtemp(prefix=prefix, dir=self.scratch))
            created.append(path)
            return str(path)

        def fake_download(url: str, provider: str, directory: Path, **_: object):
            target = directory / "source.mp4"
            target.write_bytes(b"\x00" * 2048)
            return target, "http-download"

        with patch.object(mda.tempfile, "mkdtemp", side_effect=fake_mkdtemp), \
                patch.object(mda, "download_media", side_effect=fake_download), \
                patch.object(mda, "source_metadata",
                             side_effect=ValueError("synthetic probe failure")):
            with self.assertRaises(ValueError):
                mda.collect_one(self.project, self.out_dir)

        self.assertTrue(created)
        self.assertFalse(created[0].exists())
        self.assertEqual(list(self.out_dir.rglob("*.mp4")), [])
        videos = self.out_dir / "videos"
        self.assertEqual(list(videos.iterdir()) if videos.exists() else [], [])

    def test_unsupported_provider_is_never_attempted(self) -> None:
        project = mda.parse_project_node(catalog_node())
        project["provider"] = "vimeo"
        with patch.object(mda, "download_media") as download:
            with self.assertRaises(ValueError):
                mda.collect_one(project, self.out_dir)
        download.assert_not_called()


class StillsRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _catalog(self) -> tuple[Path, dict[str, object]]:
        row = project_row("42", overall=7.2, created=None)
        row["posterUrl"] = (
            "https://storage-01-mda.keyfram.es/p/42/poster.png")
        catalog = mda.build_catalog([row], 1)
        path = self.root / "catalog.json"
        acq.write_json_atomic(path, catalog)
        return path, row

    def _synthetic_record(self, row: dict[str, object]) -> dict:
        return mda.build_still_record(row, still={
            "imageUrl": row["posterUrl"],
            "imageSha256": "a" * 64,
            "imageFormat": "png",
            "imageBytes": 123456,
            "imageWidth": 1280,
            "imageHeight": 720,
            "metrics": {
                "meanRgb": [0.1, 0.2, 0.3],
                "meanDisplayLumaProxy": 0.42,
                "displayLumaStdDev": 0.19,
                "meanSaturationProxy": 0.31,
                "shadowPixelFraction": 0.02,
                "brightPixelFraction": 0.05,
                "lumaHistogram": [0.1, 0.2, 0.3, 0.2, 0.2],
                "dominantHueFamily": "blue",
                "edgeDensityProxy": 0.07,
            },
        })

    def test_resume_skips_existing_still_and_writes_atomic_index(self) -> None:
        catalog_path, row = self._catalog()
        out_dir = self.root / "out"
        record_path = out_dir / "stills" / f"{mda.safe_slug(row['slug'])}.json"
        acq.write_json_atomic(record_path, {"projectId": row["projectId"]})

        with patch.object(mda, "collect_still_one") as collect:
            code = mda.run_stills(
                catalog_path, out_dir=out_dir, resume=True,
                delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 0)
        collect.assert_not_called()
        index_path = out_dir / "stills-index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["schemaVersion"], mda.STILLS_INDEX_SCHEMA)
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 1, "failed": 0})
        self.assertEqual(index["skips"][0]["reason"], "resume-existing-record")
        self.assertEqual(index["catalogSha256"],
                         mda.sha256_file(catalog_path))
        # Atomic write: only the record and index remain, no staging temp files.
        self.assertEqual(
            sorted(path.name for path in out_dir.iterdir()),
            ["stills", "stills-index.json"])
        self.assertEqual(
            sorted(path.name for path in (out_dir / "stills").iterdir()),
            [f"{mda.safe_slug(row['slug'])}.json"])

    def test_refresh_measures_and_indexes_a_still_row(self) -> None:
        catalog_path, row = self._catalog()
        out_dir = self.root / "out"
        record_path = out_dir / "stills" / f"{mda.safe_slug(row['slug'])}.json"
        acq.write_json_atomic(record_path, {"projectId": row["projectId"]})
        record = self._synthetic_record(row)

        with patch.object(mda, "collect_still_one",
                          return_value=record) as collect:
            code = mda.run_stills(
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
                         f"stills/{mda.safe_slug(row['slug'])}.json")

    def test_resume_index_retains_existing_measured_rows(self) -> None:
        catalog_path, row = self._catalog()
        out_dir = self.root / "out"
        record_path = out_dir / "stills" / f"{mda.safe_slug(row['slug'])}.json"
        acq.write_json_atomic(record_path, self._synthetic_record(row))

        with patch.object(mda, "collect_still_one") as collect:
            code = mda.run_stills(
                catalog_path, out_dir=out_dir, resume=True,
                delay_seconds=0, log=lambda _: None)

        self.assertEqual(code, 0)
        collect.assert_not_called()
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 1, "skipped": 1, "failed": 0})
        self.assertEqual(index["records"][0]["recordPath"],
                         f"stills/{mda.safe_slug(row['slug'])}.json")

    def test_project_without_poster_is_not_selected(self) -> None:
        row = project_row("7", overall=6.0, created=None)
        catalog = mda.build_catalog([row], 1)
        catalog_path = self.root / "catalog.json"
        acq.write_json_atomic(catalog_path, catalog)
        out_dir = self.root / "out"
        with patch.object(mda, "collect_still_one") as collect:
            code = mda.run_stills(
                catalog_path, out_dir=out_dir, delay_seconds=0,
                log=lambda _: None)
        self.assertEqual(code, 0)
        collect.assert_not_called()
        index = json.loads(
            (out_dir / "stills-index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 0, "skipped": 0, "failed": 0})


class DirectMp4ProbeFallbackTests(unittest.TestCase):
    """The direct-source probe fallback now lives in the shared acquisition package."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.url = ("https://storage-01-mda.keyfram.es/p/61/46/"
                    "ab076d933b66abf07a2df1a4cb794030.mp4")

    def test_probe_failure_falls_back_to_bounded_ranged_read(self) -> None:
        metadata = {
            "durationSeconds": 60.0, "width": 1920, "height": 1080,
            "bitRate": 49_800_000.0, "estimatedBytes": 373_500_000.0,
            "probeMethod": "ranged-read",
        }
        with patch.object(acq_probe, "remote_source_metadata",
                          side_effect=ValueError("remote probe failed")), \
                patch.object(acq_probe, "ranged_source_metadata",
                             return_value=metadata) as ranged, \
                patch.object(acq_media, "download_http",
                             return_value=self.directory / "source.mp4") \
                as download:
            path, method = acq.download_media(
                self.url, acq.DIRECT, self.directory,
                allowed_hosts=mda.VIDEO_HOSTS, max_bytes=400 * 1024 * 1024)

        self.assertEqual(method, "http-download")
        self.assertEqual(path, self.directory / "source.mp4")
        ranged.assert_called_once()
        download.assert_called_once()

    def test_unprobeable_source_reports_both_reasons(self) -> None:
        with patch.object(acq_probe, "remote_source_metadata",
                          side_effect=ValueError("remote probe failed: boom")), \
                patch.object(acq_probe, "ranged_source_metadata",
                             side_effect=ValueError("ranged probe returned no bytes")):
            with self.assertRaises(ValueError) as raised:
                acq.download_media(
                    self.url, acq.DIRECT, self.directory,
                    allowed_hosts=mda.VIDEO_HOSTS, max_bytes=400 * 1024 * 1024)

        message = str(raised.exception)
        self.assertIn("could not be characterised", message)
        self.assertIn("remote probe failed: boom", message)
        self.assertIn("ranged probe returned no bytes", message)

    def test_estimated_oversize_streams_and_aborts_at_cap(self) -> None:
        metadata = {
            "durationSeconds": 60.0, "width": 3840, "height": 2160,
            "bitRate": 120_000_000.0, "estimatedBytes": 900_000_000.0,
        }
        cap_error = ValueError("source exceeds the bounded local size cap")
        with patch.object(acq_probe, "remote_source_metadata",
                          return_value=metadata), \
                patch.object(acq_media, "download_http",
                             side_effect=cap_error) as download:
            with self.assertRaises(ValueError) as raised:
                acq.download_media(
                    self.url, acq.DIRECT, self.directory,
                    allowed_hosts=mda.VIDEO_HOSTS, max_bytes=400 * 1024 * 1024)

        self.assertEqual(str(raised.exception),
                         "source exceeds the bounded local size cap")
        download.assert_called_once()


def synthetic_video_record(
    *, slug: str = "demo-film", project_id: str = "42", overall: float = 8.5,
    title: str = "Demo Film", studio: str = "Demo Studio",
    category: str = "SHORT_FILMS", provider: str = "cloudflare-stream",
    awards: list[dict[str, str]] | None = None, duration: float = 20.0,
    windows: int = 2, cuts: int = 4, luma: float = 0.4,
    saturation: float = 0.3, cut_separated_pairs: int = 1,
    generated_at: str = "2026-01-01T00:00:00Z",
) -> dict:
    window_rows = []
    for index in range(windows):
        window_rows.append({
            "startSeconds": index * 10,
            "endSeconds": index * 10 + 10,
            "probe": {
                "sampledWindowSummary": {
                    "cutCandidateCountBetweenFirstAndLastSample": cuts // windows,
                    "meanSampledDisplayLumaProxy": luma,
                    "meanSampledSaturationProxy": saturation,
                    "cutSeparatedPairs": cut_separated_pairs,
                },
                "sampledFrames": [{}, {}],
                "sampledFramePairs": [
                    {"meanAbsoluteDisplayRgbDeltaPerSecond": 0.5},
                    {"meanAbsoluteDisplayRgbDeltaPerSecond": 0.25},
                ],
            },
        })
    sampled = windows * 10
    return {
        "schemaVersion": mda.VIDEO_SCHEMA,
        "projectId": project_id,
        "slug": slug,
        "catalog": {
            "title": title, "studio": studio, "category": category,
            "scores": {"overall": overall}, "awards": awards or [],
        },
        "source": {
            "durationSeconds": duration, "sizeBytes": 10 * 1024 * 1024,
            "resolution": [1280, 720],
            "frameRate": {"numerator": 25, "denominator": 1},
        },
        "acquisition": {"provider": provider},
        "coverage": {
            "windowsMeasured": windows, "windowSeconds": 10,
            "sampledSeconds": sampled,
            "fractionOfRuntime": round(min(1.0, sampled / duration), 6),
        },
        "summary": {
            "cutCandidates": cuts,
            "cutCandidateRatePerMinute": round(cuts * 60 / sampled, 6),
            "meanDisplayLuma": luma,
            "meanSaturation": saturation,
            "meanWithinShotRgbDeltaPerSecond": 0.375,
        },
        "windows": window_rows,
        "generatedAt": generated_at,
    }


def synthetic_still_record(
    *, slug: str = "demo-film", project_id: str = "42",
    luma: float = 0.7, hue: str = "blue",
    generated_at: str = "2026-01-02T00:00:00Z",
) -> dict:
    return {
        "schemaVersion": mda.STILL_SCHEMA,
        "projectId": project_id,
        "slug": slug,
        "still": {"metrics": {
            "meanDisplayLumaProxy": luma, "dominantHueFamily": hue}},
        "generatedAt": generated_at,
    }


class ReportTests(unittest.TestCase):
    """The report is read-only, deterministic, and never mixes still evidence."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_video(self, out_dir: Path, record: dict) -> None:
        acq.write_json_atomic(
            out_dir / "videos" / f"{mda.safe_slug(record['slug'])}.json", record)

    def write_still(self, out_dir: Path, record: dict) -> None:
        acq.write_json_atomic(
            out_dir / "stills" / f"{mda.safe_slug(record['slug'])}.json", record)

    def test_empty_state_writes_valid_skeleton(self) -> None:
        out_dir = self.root / "out"
        code = mda.run_report(out_dir, log=lambda _: None)
        self.assertEqual(code, 0)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["schemaVersion"], mda.AGGREGATE_SCHEMA)
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
            slug="measured", project_id="1", luma=0.2, saturation=0.1,
            cuts=4))
        self.write_still(out_dir, synthetic_still_record(
            slug="measured", project_id="1", luma=0.9, hue="blue"))
        self.write_still(out_dir, synthetic_still_record(
            slug="still-only", project_id="2", luma=0.9, hue="red"))

        code = mda.run_report(out_dir, log=lambda _: None)
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
        # The 0.9 still luma never leaks into the video table.
        self.assertEqual(aggregate["videos"][0]["meanDisplayLuma"], 0.2)

    def test_repeat_runs_are_byte_identical(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(slug="a", project_id="1"))
        self.write_video(out_dir, synthetic_video_record(
            slug="b", project_id="2", overall=9.0))
        self.write_still(out_dir, synthetic_still_record(slug="c", project_id="3"))

        mda.run_report(out_dir, top=2, log=lambda _: None)
        first_report = (out_dir / "report.md").read_bytes()
        first_aggregate = (out_dir / "aggregate.json").read_bytes()
        mda.run_report(out_dir, top=2, log=lambda _: None)

        self.assertEqual((out_dir / "report.md").read_bytes(), first_report)
        self.assertEqual((out_dir / "aggregate.json").read_bytes(), first_aggregate)

    def test_malformed_records_are_listed_and_do_not_stop_the_report(self) -> None:
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(slug="good", project_id="1"))
        (out_dir / "videos" / "broken.json").write_text(
            "{not json", encoding="utf-8")
        acq.write_json_atomic(out_dir / "videos" / "wrong-schema.json",
                              {"schemaVersion": "kumiki.other.v1"})

        code = mda.run_report(out_dir, log=lambda _: None)
        self.assertEqual(code, 0)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["counts"]["videoMeasured"], 1)
        self.assertEqual(aggregate["counts"]["unreadable"], 2)
        files = sorted(item["file"] for item in aggregate["unreadableRecords"])
        self.assertEqual(files, ["videos/broken.json", "videos/wrong-schema.json"])
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        self.assertIn("videos/broken.json", report)
        self.assertIn("unexpected schemaVersion", report)

    def test_number_formatting_is_fixed_precision(self) -> None:
        self.assertEqual(mda._num(None, 4), "—")
        self.assertEqual(mda._num(0.123456789, 4), "0.1235")
        self.assertEqual(mda._int(None), "—")
        out_dir = self.root / "out"
        self.write_video(out_dir, synthetic_video_record(
            slug="numbers", project_id="1", luma=0.4, saturation=0.3,
            duration=20.0))
        mda.run_report(out_dir, log=lambda _: None)
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        row = next(line for line in report.splitlines()
                   if line.startswith("| numbers |"))
        self.assertIn("| 8.50 |", row)
        self.assertIn("| 20.00 |", row)
        self.assertIn("| 25.000 |", row)
        self.assertIn("| 4.19 |", row)   # bitrate Mbps from 10 MiB / 20 s
        self.assertIn("| 10.0 |", row)   # download MB
        self.assertIn("| 0.4000 |", row)
        self.assertIn("| 0.3000 |", row)

    def test_aggregate_totals_reconcile_with_tables(self) -> None:
        out_dir = self.root / "out"
        for index in range(3):
            self.write_video(out_dir, synthetic_video_record(
                slug=f"clip-{index}", project_id=str(index),
                overall=9.0 - index,
                category="SHORT_FILMS" if index else "EXPERIMENTAL",
                provider="cloudflare-stream" if index else "direct-mp4"))
        self.write_still(out_dir, synthetic_still_record(slug="s1", project_id="9"))

        mda.run_report(out_dir, top=2, log=lambda _: None)
        aggregate = json.loads(
            (out_dir / "aggregate.json").read_text(encoding="utf-8"))
        report = (out_dir / "report.md").read_text(encoding="utf-8")
        table = report.split("## Per-video analysis", 1)[1].split(
            "## Per-video detail", 1)[0]
        data_rows = [line for line in table.splitlines()
                     if line.startswith("| ")
                     and not line.startswith("| slug |")
                     and not line.startswith("| --- |")]
        self.assertEqual(aggregate["counts"]["videoMeasured"], 3)
        self.assertEqual(aggregate["counts"]["videoMeasuredTotal"], 3)
        self.assertEqual(len(aggregate["videos"]), 3)
        self.assertEqual(len(data_rows), 3)
        self.assertEqual(aggregate["aggregates"]["recordCount"], 3)
        self.assertEqual(sum(aggregate["aggregates"]["byProvider"].values()), 3)
        self.assertEqual(sum(aggregate["aggregates"]["byCategory"].values()), 3)
        self.assertEqual(len(aggregate["details"]), 2)
        # Catalog order: descending wa_overall.
        self.assertEqual([row["slug"] for row in aggregate["videos"]],
                         ["clip-0", "clip-1", "clip-2"])
        self.assertIn("| cloudflare-stream | 2 |",
                      report)
        self.assertIn("| direct-mp4 | 1 |", report)


def _dump(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


SAMPLE_CATALOG = RESEARCH / "catalog.v2.json"


@unittest.skipUnless(SAMPLE_CATALOG.is_file(),
                     "committed MDA research tree is not present")
class RecordParityTests(unittest.TestCase):
    """A rebuilt record must be byte-identical to the committed sample."""

    def project(self, project_id: object) -> dict:
        catalog = json.loads(SAMPLE_CATALOG.read_text(encoding="utf-8"))
        return next(row for row in catalog["projects"]
                    if row["projectId"] == str(project_id))

    def test_video_record_matches_committed_sample_bytes(self) -> None:
        samples = sorted((RESEARCH / "videos").glob("*.json"))
        if not samples:
            self.skipTest("no committed video samples")
        path = samples[0]
        record = json.loads(path.read_text(encoding="utf-8"))
        rebuilt = mda.build_video_record(
            self.project(record["projectId"]), source=record["source"],
            coverage=record["coverage"], windows=record["windows"],
            method=record["acquisition"]["method"],
            rights_note=record["acquisition"]["attestation"]["note"],
            generated_at=record["generatedAt"])
        self.assertEqual(_dump(rebuilt), path.read_text(encoding="utf-8"))

    def test_still_record_matches_committed_sample_bytes(self) -> None:
        samples = sorted((RESEARCH / "stills").glob("*.json"))
        if not samples:
            self.skipTest("no committed still samples")
        path = samples[0]
        record = json.loads(path.read_text(encoding="utf-8"))
        rebuilt = mda.build_still_record(
            self.project(record["projectId"]), still=record["still"],
            generated_at=record["generatedAt"])
        # Schema addition: `still.qualityFlags` is now always present and `[]`
        # for a clean still (see docs/motiondesignawards-video-research.md).
        # Committed samples predate the key, so the expectation gains the
        # empty default; every other byte and key order is still compared.
        expected = json.loads(path.read_text(encoding="utf-8"))
        expected["still"].setdefault("qualityFlags", [])
        self.assertEqual(_dump(rebuilt), _dump(expected))


if __name__ == "__main__":
    unittest.main()
