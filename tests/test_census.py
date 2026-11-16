"""Offline tests for the full-runtime census engine and corpus driver.

No network and no real ffmpeg: ffprobe/ffmpeg subprocess calls, downloads and
the scanner are patched. The live smoke is a separate, explicitly approved run.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.acquisition import census

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "census_video_cuts", ROOT / "scripts" / "census_video_cuts.py")
census_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(census_script)

WIDTH, HEIGHT = 64, 36
PLANE = WIDTH * HEIGHT * 3


def _scene_stderr(pts: list[int], timebase: str = "1/12800") -> str:
    lines = [
        f"[Parsed_showinfo_1 @ 0x1] config in time_base: {timebase}, "
        "time_base: 1/12800",
    ]
    for index, value in enumerate(pts):
        lines.append(
            f"[Parsed_showinfo_1 @ 0x1] n: {index:4d} pts: {value:8d} "
            "pts_time:0.0")
    return "\n".join(lines) + "\n"


def _cadence_stderr(pts: list[int], timebase: str = "1/12800") -> str:
    return _scene_stderr(pts, timebase)


def _frame(fill: int) -> bytes:
    return bytes([fill, fill, fill]) * (WIDTH * HEIGHT)


def _ffprobe_json(duration: float = 2.0) -> str:
    return json.dumps({
        "streams": [{
            "index": 0, "codec_type": "video", "width": WIDTH,
            "height": HEIGHT, "avg_frame_rate": "60/1",
            "r_frame_rate": "60/1", "time_base": "1/12800",
            "duration": str(duration),
        }],
        "format": {"duration": str(duration)},
    })


class _ScanFake:
    """Dispatch fake ffprobe/ffmpeg runs for scan_full_runtime."""

    def __init__(self, *, cut_pts: list[int], sample_pts: list[int],
                 frames: list[bytes], duration: float = 2.0,
                 timebase: str = "1/12800") -> None:
        self.cut_pts = cut_pts
        self.sample_pts = sample_pts
        self.frames = frames
        self.duration = duration
        self.timebase = timebase
        self.calls: list[list[str]] = []

    def __call__(self, command, **kwargs):  # noqa: ANN001 - test double
        self.calls.append(list(command))
        if command[0] == "ffprobe":
            return subprocess.CompletedProcess(
                command, 0, stdout=_ffprobe_json(self.duration), stderr="")
        if "rawvideo" in command:
            body = b"".join(self.frames)
            return subprocess.CompletedProcess(
                command, 0, stdout=body,
                stderr=_cadence_stderr(self.sample_pts, self.timebase))
        return subprocess.CompletedProcess(
            command, 0, stdout="",
            stderr=_scene_stderr(self.cut_pts, self.timebase))


class CensusScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / "clip.mp4"
        self.source.write_bytes(b"not really a video")

    def test_two_passes_parse_scene_and_series(self) -> None:
        fake = _ScanFake(
            cut_pts=[100, 200, 300],
            sample_pts=[0, 12800],
            frames=[_frame(0), _frame(255)])
        with patch.object(census.subprocess, "run", side_effect=fake):
            scan = census.scan_full_runtime(
                self.source, width=WIDTH, height=HEIGHT)
        self.assertEqual(scan["cutPts"], [100, 200, 300])
        self.assertEqual(scan["cutCount"], 3)
        self.assertTrue(scan["fullRuntimeDecoded"])
        self.assertEqual(scan["timebase"], {"numerator": 1, "denominator": 12800})
        self.assertEqual(scan["fps"], {"numerator": 60, "denominator": 1})
        self.assertEqual(scan["resolution"], [WIDTH, HEIGHT])
        self.assertEqual(scan["durationSeconds"], 2.0)
        self.assertEqual(scan["cutsPerMinute"], 90.0)
        self.assertAlmostEqual(scan["medianCutGapSeconds"], 100 / 12800, places=5)
        self.assertEqual(scan["cutCount"], len(scan["cutPts"]))
        self.assertEqual(len(scan["series"]), 2)
        first = scan["series"][0]
        self.assertEqual(first["sourcePts"], 0)
        self.assertEqual(first["sourceSeconds"], 0.0)
        for key in ("meanRgb", "meanDisplayLumaProxy", "meanSaturationProxy",
                    "shadowPixelFraction", "brightPixelFraction"):
            self.assertIn(key, first)
        self.assertEqual(scan["seriesSummary"]["samples"], 2)
        self.assertEqual(scan["seriesSummary"]["decodeCoverageFraction"], 1.0)
        self.assertEqual(scan["seriesSummary"]["sampledSeconds"], 2.0)
        # Exactly one ffprobe plus one scene pass plus one cadence pass.
        ffmpeg_calls = [call for call in fake.calls if call[0] != "ffprobe"]
        self.assertEqual(len(ffmpeg_calls), 2)

    def test_scene_pass_failure_is_bounded_and_redacted(self) -> None:
        def failing(command, **kwargs):  # noqa: ANN001 - test double
            if command[0] == "ffprobe":
                return subprocess.CompletedProcess(
                    command, 0, stdout=_ffprobe_json(), stderr="")
            return subprocess.CompletedProcess(
                command, 1, stdout="",
                stderr="failed https://media.example/clip?Signature=secret")

        with patch.object(census.subprocess, "run", side_effect=failing):
            with self.assertRaises(ValueError) as raised:
                census.scan_full_runtime(
                    self.source, width=WIDTH, height=HEIGHT)
        message = str(raised.exception)
        self.assertIn("scene pass", message)
        self.assertNotIn("secret", message)
        self.assertLessEqual(len(message), 400)

    def test_symlink_and_missing_paths_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            census.scan_full_runtime(
                Path(self.directory.name) / "absent.mp4")
        link = Path(self.directory.name) / "link.mp4"
        link.symlink_to(self.source)
        with self.assertRaises(ValueError):
            census.scan_full_runtime(link)

    def test_timeout_budget_is_bounded(self) -> None:
        with self.assertRaises(ValueError):
            census.scan_full_runtime(
                self.source, timeout_seconds=census.MAX_SCAN_TIMEOUT_SECONDS + 1)


class CensusMathsTests(unittest.TestCase):
    def test_60fps_strobe_sets_flag(self) -> None:
        stats = census._cut_statistics(
            [0, 100, 200, 300], timebase_seconds=1 / 12800,
            duration_seconds=2.0, fps=60.0)
        self.assertTrue(stats["strobe"])
        self.assertLess(stats["medianCutGapFrames"], 3)
        self.assertEqual(stats["burstFraction"], 1.0)
        self.assertEqual(stats["cutCount"], 4)
        self.assertEqual(stats["cutsPerMinute"], 120.0)

    def test_sparse_cuts_are_not_strobe(self) -> None:
        stats = census._cut_statistics(
            [0, 12800 * 2, 12800 * 4, 12800 * 6],
            timebase_seconds=1 / 12800, duration_seconds=8.0, fps=60.0)
        self.assertFalse(stats["strobe"])
        self.assertEqual(stats["medianCutGapFrames"], 120.0)
        self.assertEqual(stats["burstFraction"], 0.0)
        self.assertEqual(stats["minCutGapSeconds"], 2.0)
        self.assertEqual(stats["p10CutGapSeconds"], 2.0)

    def test_time_weighted_series_summary(self) -> None:
        series = [
            {"sourceSeconds": 0.0, "meanDisplayLumaProxy": 0.1,
             "meanSaturationProxy": 0.2},
            {"sourceSeconds": 1.0, "meanDisplayLumaProxy": 0.3,
             "meanSaturationProxy": 0.4},
            {"sourceSeconds": 2.0, "meanDisplayLumaProxy": 0.5,
             "meanSaturationProxy": 0.6},
        ]
        summary = census._series_summary(series, duration_seconds=4.0)
        self.assertEqual(summary["samples"], 3)
        self.assertEqual(summary["decodeCoverageFraction"], 1.0)
        self.assertEqual(summary["sampledSeconds"], 4.0)
        # Weights 1, 1, 2 tile [0, 4].
        self.assertAlmostEqual(summary["meanDisplayLuma"], 0.35)
        self.assertAlmostEqual(summary["meanSaturation"], 0.45)


class CensusEvidenceTests(unittest.TestCase):
    def test_build_census_evidence_field_completeness(self) -> None:
        scan = {
            "fullRuntimeDecoded": True,
            "durationSeconds": 12.0,
            "cutCount": 3,
            "cutsPerMinute": 15.0,
            "strobe": False,
            "seriesSummary": {"decodeCoverageFraction": 1.0},
        }
        evidence = census.build_census_evidence(
            scan, source={"mediaSha256": "a" * 64, "durationSeconds": 12.0},
            video_url="https://example.test/v.mp4", provider="direct-mp4",
            download_method="http-download", rights_basis="user-declared-research-use",
            rights_note="public page research", schema_version="x.census.v1",
            evidence_status="numeric", limits=["numeric only"],
            generated_at="2026-01-01T00:00:00Z")
        self.assertEqual(evidence["schemaVersion"], "x.census.v1")
        self.assertEqual(evidence["source"]["mediaSha256"], "a" * 64)
        self.assertEqual(evidence["acquisition"]["provider"], "direct-mp4")
        self.assertEqual(evidence["acquisition"]["method"], "http-download")
        self.assertFalse(evidence["acquisition"]["mediaRetained"])
        self.assertEqual(evidence["acquisition"]["attestation"]["rightsBasis"],
                         "user-declared-research-use")
        self.assertEqual(evidence["coverage"],
                         {"fullFilmDecoded": True,
                          "decodeCoverageFraction": 1.0})
        self.assertIs(evidence["census"], scan)
        self.assertEqual(evidence["rightsStatus"], "review-required")
        self.assertEqual(evidence["limits"], ["numeric only"])
        self.assertEqual(evidence["generatedAt"], "2026-01-01T00:00:00Z")

    def test_scan_without_full_decode_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            census.build_census_evidence(
                {"seriesSummary": {}}, source={}, video_url=None,
                provider="direct", download_method="http-download",
                rights_basis="basis", rights_note="note",
                schema_version="x", evidence_status="status", limits=[])


class ScriptExtractorTests(unittest.TestCase):
    def test_nested_adapter_shape(self) -> None:
        record = {
            "schemaVersion": "kumiki.motiondesignawards-video-evidence.v1",
            "projectId": "1811", "slug": "0800",
            "source": {"mediaSha256": "A" * 64, "durationSeconds": 60.0,
                       "sizeBytes": 123},
            "acquisition": {
                "provider": "cloudflare-stream",
                "videoUrl": "https://customer-x.cloudflarestream.com/x/manifest/video.m3u8",
            },
        }
        identity = census_script.extract_record_identity(record)
        self.assertEqual(identity["id"], "1811")
        self.assertEqual(identity["slug"], "0800")
        self.assertEqual(identity["provider"], "cloudflare-stream")
        self.assertEqual(identity["mediaSha256"], "a" * 64)
        self.assertEqual(identity["videoUrl"],
                         "https://customer-x.cloudflarestream.com/x/manifest/video.m3u8")

    def test_flat_adapter_shape(self) -> None:
        record = {
            "schemaVersion": "kumiki.promonews-video-evidence.v1",
            "nid": 94682, "slug": "isaiah-rashad", "provider": "youtube",
            "videoUrl": "https://www.youtube.com/watch?v=z_8vbppalKo",
            "source": {"mediaSha256": "b" * 64},
        }
        identity = census_script.extract_record_identity(record)
        self.assertEqual(identity["id"], "94682")
        self.assertEqual(identity["slug"], "isaiah-rashad")
        self.assertEqual(identity["provider"], "youtube")
        self.assertEqual(identity["mediaSha256"], "b" * 64)

    def test_evidence_wrapped_shape(self) -> None:
        record = {
            "id": "42", "slug": "wrapped",
            "evidence": {
                "source": {"videoUrl": "https://example.test/a.mp4",
                           "mediaSha256": "c" * 64},
                "acquisition": {"provider": "direct-mp4"},
            },
        }
        identity = census_script.extract_record_identity(record)
        self.assertEqual(identity["videoUrl"], "https://example.test/a.mp4")
        self.assertEqual(identity["provider"], "direct-mp4")
        self.assertEqual(identity["mediaSha256"], "c" * 64)


class _Options:
    def __init__(self, root: Path, **overrides) -> None:
        values = {
            "root": root, "max_file_bytes": 400 * 1024 ** 2,
            "max_duration_seconds": 600.0, "ffmpeg": "ffmpeg",
            "ffprobe": "ffprobe", "yt_dlp": "yt-dlp",
            "sample_seconds": 1.0, "timeout_seconds": 60.0,
        }
        values.update(overrides)
        self.__dict__.update(values)


def _item(root: Path, *, sha: str | None = "a" * 64) -> dict:
    return {
        "id": "123", "slug": "clip", "recordPath": "promonews/videos/123-clip.json",
        "videoUrl": "https://www.youtube.com/watch?v=abcdefghijk",
        "storedProvider": "youtube", "delivery": "youtube",
        "mediaSha256": sha, "hosts": ("youtube.com",),
        "allowQuery": False,
        "outputPath": root / "promonews" / "census" / "123-clip.json",
    }


def _fake_download(created: list[Path]):
    def download(url, delivery, directory, **kwargs):  # noqa: ANN001
        path = Path(directory) / "source.mp4"
        path.write_bytes(b"media")
        created.append(path)
        return path, "http-download"
    return download


def _scan_payload() -> dict:
    return {
        "fullRuntimeDecoded": True, "durationSeconds": 2.0,
        "cutCount": 1, "cutsPerMinute": 30.0, "strobe": False,
        "seriesSummary": {"decodeCoverageFraction": 1.0},
    }


class ScriptLifecycleTests(unittest.TestCase):
    def test_atomic_write_and_media_deletion_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created: list[Path] = []
            with patch.object(census_script, "download_media",
                              side_effect=_fake_download(created)), \
                 patch.object(census_script, "source_metadata",
                              return_value={"mediaSha256": "a" * 64}), \
                 patch.object(census_script, "scan_full_runtime",
                              return_value=_scan_payload()):
                row = census_script.run_census_item(
                    _item(root), site="promonews", options=_Options(root))
            output = root / "promonews" / "census" / "123-clip.json"
            self.assertTrue(output.is_file())
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["schemaVersion"],
                "kumiki.promonews-census-evidence.v1")
            self.assertEqual(payload["rightsStatus"], "review-required")
            self.assertFalse(payload["mediaRetained"])
            self.assertEqual(payload["census"], _scan_payload())
            self.assertEqual(row["cutsPerMinute"], 30.0)
            self.assertEqual(list(output.parent.glob("*.tmp")), [])
            self.assertTrue(created)
            self.assertFalse(created[0].exists())

    def test_media_changed_refuses_measurement_and_deletes_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created: list[Path] = []
            with patch.object(census_script, "download_media",
                              side_effect=_fake_download(created)), \
                 patch.object(census_script, "source_metadata",
                              return_value={"mediaSha256": "b" * 64}), \
                 patch.object(census_script, "scan_full_runtime") as scan:
                with self.assertRaises(census_script.MediaChanged):
                    census_script.run_census_item(
                        _item(root), site="promonews", options=_Options(root))
            scan.assert_not_called()
            self.assertFalse(created[0].exists())
            self.assertFalse((root / "promonews" / "census" / "123-clip.json").exists())

    def test_failure_deletes_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created: list[Path] = []
            with patch.object(census_script, "download_media",
                              side_effect=_fake_download(created)), \
                 patch.object(census_script, "source_metadata",
                              return_value={"mediaSha256": "a" * 64}), \
                 patch.object(census_script, "scan_full_runtime",
                              side_effect=RuntimeError("decode failed")):
                with self.assertRaises(RuntimeError):
                    census_script.run_census_item(
                        _item(root), site="promonews", options=_Options(root))
            self.assertFalse(created[0].exists())


class ScriptBatchTests(unittest.TestCase):
    def _record(self, slug: str = "clip", *, url: bool = True) -> dict:
        return {
            "schemaVersion": "kumiki.promonews-video-evidence.v1",
            "nid": 123, "slug": slug, "provider": "youtube",
            "videoUrl": "https://www.youtube.com/watch?v=abcdefghijk" if url else None,
            "source": {"mediaSha256": "a" * 64},
        }

    def test_missing_url_is_a_skip_not_a_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            videos = root / "promonews" / "videos"
            videos.mkdir(parents=True)
            (videos / "123-clip.json").write_text(
                json.dumps(self._record(url=False)), encoding="utf-8")
            with patch.object(census_script, "download_media") as download:
                code = census_script.main([
                    "--root", str(root), "--site", "promonews",
                    "--acknowledge-rights"])
            self.assertEqual(code, 0)
            download.assert_not_called()
            index = json.loads(
                (root / "promonews" / "census-index.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(index["counts"]["skipped"], 1)
            self.assertEqual(index["skips"][0]["reason"], "missing-url")

    def test_resume_skips_existing_record_without_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            videos = root / "promonews" / "videos"
            census_dir = root / "promonews" / "census"
            videos.mkdir(parents=True)
            census_dir.mkdir(parents=True)
            (videos / "123-clip.json").write_text(
                json.dumps(self._record()), encoding="utf-8")
            (census_dir / "123-clip.json").write_text("{}\n", encoding="utf-8")
            with patch.object(census_script, "download_media") as download:
                code = census_script.main([
                    "--root", str(root), "--site", "promonews",
                    "--acknowledge-rights", "--resume"])
            self.assertEqual(code, 0)
            download.assert_not_called()
            index = json.loads(
                (root / "promonews" / "census-index.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(index["counts"]["skipped"], 1)
            self.assertEqual(index["skips"][0]["reason"],
                             "resume-existing-record")

    def test_media_changed_is_a_failure_row(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            videos = root / "promonews" / "videos"
            videos.mkdir(parents=True)
            (videos / "123-clip.json").write_text(
                json.dumps(self._record()), encoding="utf-8")
            created: list[Path] = []
            with patch.object(census_script, "download_media",
                              side_effect=_fake_download(created)), \
                 patch.object(census_script, "source_metadata",
                              return_value={"mediaSha256": "b" * 64}):
                code = census_script.main([
                    "--root", str(root), "--site", "promonews",
                    "--acknowledge-rights", "--limit", "1"])
            self.assertEqual(code, 0)
            index = json.loads(
                (root / "promonews" / "census-index.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(index["counts"]["failed"], 1)
            self.assertEqual(index["failures"][0]["reason"], "media-changed")
            self.assertFalse(created[0].exists())


class ScriptCatalogFallbackTests(unittest.TestCase):
    def test_catalog_urls_index_every_adapter_id_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps({"entries": [
                {"id": "101", "videoUrl": "https://cdn.test/a.mp4"},
                {"nid": 202, "videoUrl": "https://cdn.test/b.mp4"},
                {"projectId": "303", "videoUrl": "https://cdn.test/c.mp4"},
                {"catalogId": "404", "videoUrl": "https://cdn.test/d.mp4"},
                {"id": "505", "posterUrl": "https://cdn.test/poster.png"},
            ]}), encoding="utf-8")
            urls = census_script.load_catalog_urls([path])
            self.assertEqual(urls["101"], "https://cdn.test/a.mp4")
            self.assertEqual(urls["202"], "https://cdn.test/b.mp4")
            self.assertEqual(urls["303"], "https://cdn.test/c.mp4")
            self.assertEqual(urls["404"], "https://cdn.test/d.mp4")
            self.assertNotIn("505", urls)

    def test_catalog_row_container_shapes(self) -> None:
        rows = {"id": "7", "videoUrl": "https://cdn.test/7.mp4"}
        for key in ("entries", "videos", "projects", "clips", "items",
                    "records"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "catalog.json"
                path.write_text(json.dumps({key: [rows]}), encoding="utf-8")
                self.assertEqual(census_script.load_catalog_urls([path])["7"],
                                 "https://cdn.test/7.mp4")

    def test_absent_catalog_keeps_missing_url_skip(self) -> None:
        self.assertEqual(census_script.load_catalog_urls([]), {})

    def test_stale_record_url_falls_back_and_records_catalog_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            videos = root / "shots" / "videos"
            videos.mkdir(parents=True)
            record = {
                "id": "123", "slug": "clip", "provider": "direct-mp4",
                "videoUrl": "https://d1ko11x0ybxl0h.cloudfront.net/old.mp4",
                "source": {"mediaSha256": "a" * 64},
            }
            (videos / "123-clip.json").write_text(
                json.dumps(record), encoding="utf-8")
            catalog = root / "shots" / "catalog.json"
            catalog.write_text(json.dumps({"clips": [{
                "id": 123,
                "videoUrl": "https://d1ko11x0ybxl0h.cloudfront.net/new.mp4",
            }]}), encoding="utf-8")
            calls: list[str] = []

            def download(url, delivery, directory, **kwargs):  # noqa: ANN001
                calls.append(url)
                if "old.mp4" in url:
                    raise ValueError(
                        "remote probe failed after 3 attempts: "
                        "[redacted-url] Server returned 404 Not Found")
                path = Path(directory) / "source.mp4"
                path.write_bytes(b"media")
                return path, "http-download"

            with patch.object(census_script, "download_media", side_effect=download), \
                 patch.object(census_script, "source_metadata",
                              return_value={"mediaSha256": "a" * 64}), \
                 patch.object(census_script, "scan_full_runtime",
                              return_value=_scan_payload()), \
                 contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = census_script.main([
                    "--root", str(root), "--site", "shots",
                    "--catalog", str(catalog),
                    "--acknowledge-rights", "--limit", "1",
                    "--delay-seconds", "0"])
            self.assertEqual(code, 0)
            self.assertEqual(calls, [
                "https://d1ko11x0ybxl0h.cloudfront.net/old.mp4",
                "https://d1ko11x0ybxl0h.cloudfront.net/new.mp4",
            ])
            self.assertIn("url-from-catalog", stdout.getvalue())
            index = json.loads(
                (root / "shots" / "census-index.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(index["counts"]["measured"], 1)
            self.assertEqual(index["records"][0]["urlSource"], "catalog")
            evidence = json.loads(
                (root / "shots" / "census" / "123-clip.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(evidence["acquisition"]["urlSource"], "catalog")
            self.assertEqual(evidence["record"]["urlSource"], "catalog")
            self.assertEqual(
                evidence["acquisition"]["videoUrl"],
                "https://d1ko11x0ybxl0h.cloudfront.net/new.mp4")

    def test_persistent_4xx_is_stale_signed_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = _item(root)
            item.update({
                "videoUrl": "https://cdn.test/old.mp4",
                "catalogUrl": "https://cdn.test/new.mp4",
                "urlSource": "record", "allowQuery": True,
                "hosts": ("cdn.test",), "storedProvider": "direct-mp4",
                "delivery": "direct",
            })
            calls: list[str] = []

            def download(url, delivery, directory, **kwargs):  # noqa: ANN001
                calls.append(url)
                raise ValueError("Server returned 404 Not Found")

            with patch.object(census_script, "download_media", side_effect=download):
                with self.assertRaises(census_script.StaleSignedUrl) as raised:
                    census_script.run_census_item(
                        item, site="promonews", options=_Options(root))
            self.assertEqual(raised.exception.reason, "stale-signed-url")
            self.assertEqual(calls, [
                "https://cdn.test/old.mp4",
                "https://cdn.test/new.mp4",
            ])
            self.assertEqual(census_script._error_text(raised.exception),
                             "stale-signed-url")

    def test_catalog_fallback_with_different_hash_is_media_changed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = _item(root)
            item.update({
                "videoUrl": "https://cdn.test/old.mp4",
                "catalogUrl": "https://cdn.test/new.mp4",
                "urlSource": "record", "allowQuery": True,
                "hosts": ("cdn.test",), "storedProvider": "direct-mp4",
                "delivery": "direct",
            })
            calls: list[str] = []

            def download(url, delivery, directory, **kwargs):  # noqa: ANN001
                calls.append(url)
                if "old.mp4" in url:
                    raise ValueError("HTTP Error 404: Not Found")
                path = Path(directory) / "source.mp4"
                path.write_bytes(b"media")
                return path, "http-download"

            with patch.object(census_script, "download_media", side_effect=download), \
                 patch.object(census_script, "source_metadata",
                              return_value={"mediaSha256": "c" * 64}), \
                 patch.object(census_script, "scan_full_runtime") as scan:
                with self.assertRaises(census_script.MediaChanged):
                    census_script.run_census_item(
                        item, site="promonews", options=_Options(root))
            scan.assert_not_called()
            self.assertEqual(calls, [
                "https://cdn.test/old.mp4",
                "https://cdn.test/new.mp4",
            ])


if __name__ == "__main__":
    unittest.main()
