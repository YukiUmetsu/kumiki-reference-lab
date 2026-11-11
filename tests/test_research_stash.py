"""Offline tests for the STASH site adapter. No network access is performed."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import research_stash as stash

SITE = "https://www.stashmedia.tv"


def _post(post_id: int, content: str, slug: str = "sample-post") -> dict[str, object]:
    return {"id": post_id, "link": f"{SITE}/{slug}/", "date": "2024-01-02T03:04:05",
            "title": {"rendered": "A &amp; B"}, "content": {"rendered": content}}


class ClassifyContentTests(unittest.TestCase):
    def test_vimeo_player_is_unsupported_and_never_eligible(self) -> None:
        result = stash.classify_content(
            '<iframe src="https://player.vimeo.com/video/123?badge=0"></iframe>')
        self.assertEqual(result["provider"], "vimeo")
        self.assertFalse(result["eligible"])
        self.assertIsNone(result["videoUrl"])

    def test_signed_vimeocdn_playback_url_is_vimeo_not_media(self) -> None:
        result = stash.classify_content(
            '<a href="https://24.vimeocdn.com/progressive/x.mp4?token=abc">v</a>')
        self.assertEqual(result["provider"], "vimeo")
        self.assertFalse(result["eligible"])

    def test_mixed_vimeo_and_youtube_reports_both_and_stays_vimeo(self) -> None:
        result = stash.classify_content(
            '<iframe src="https://www.youtube.com/embed/abc"></iframe>'
            '<iframe src="https://player.vimeo.com/video/9"></iframe>')
        self.assertEqual(result["provider"], "vimeo")
        self.assertEqual(result["providers"], ["vimeo", "youtube"])

    def test_youtube_only(self) -> None:
        result = stash.classify_content('<iframe src="https://youtu.be/abc"></iframe>')
        self.assertEqual(result["provider"], "youtube")

    def test_exact_host_direct_mp4_is_eligible(self) -> None:
        result = stash.classify_content(
            f'<video><source src="{SITE}/wp-content/uploads/2024/clip.mp4"></video>')
        self.assertEqual(result["provider"], "direct-mp4")
        self.assertTrue(result["eligible"])
        self.assertEqual(result["videoUrl"], f"{SITE}/wp-content/uploads/2024/clip.mp4")

    def test_lookalike_host_is_not_allowlisted(self) -> None:
        result = stash.classify_content(
            '<a href="https://stashmedia.tv.evil.example/clip.mp4">x</a>')
        self.assertEqual(result["provider"], "self-hosted-other")
        self.assertFalse(result["eligible"])

    def test_http_media_is_rejected(self) -> None:
        result = stash.classify_content(
            '<a href="http://www.stashmedia.tv/wp-content/uploads/clip.mp4">x</a>')
        self.assertFalse(result["eligible"])
        self.assertEqual(result["provider"], "self-hosted-other")

    def test_query_string_media_is_rejected(self) -> None:
        result = stash.classify_content(
            f'<a href="{SITE}/wp-content/uploads/clip.mp4?v=1">x</a>')
        self.assertFalse(result["eligible"])

    def test_hls_playlist_is_out_of_scope(self) -> None:
        result = stash.classify_content(
            f'<a href="{SITE}/wp-content/uploads/master.m3u8">x</a>')
        self.assertFalse(result["eligible"])
        self.assertEqual(result["provider"], "self-hosted-other")

    def test_subscribe_link_without_embed_is_gated(self) -> None:
        result = stash.classify_content(f'<a href="{SITE}/subscribe/">join</a>')
        self.assertEqual(result["provider"], "gated")
        self.assertTrue(result["gated"])

    def test_plain_text_is_no_video(self) -> None:
        result = stash.classify_content("<p>Hello.</p>")
        self.assertEqual(result["provider"], "none")
        self.assertFalse(result["eligible"])

    def test_unparsable_markup_does_not_raise(self) -> None:
        result = stash.classify_content("<p>more：http://x</p>")
        self.assertEqual(result["provider"], "none")


class MainVideoBlockTests(unittest.TestCase):
    def test_extracts_postvid_container_only(self) -> None:
        page = ('<div id="nav"><a href="https://vimeo.com/stashmedia">v</a></div>'
                '<div id="content"><div class="postvid_single"><iframe src='
                '"https://player.vimeo.com/video/828872344"></iframe></div></div>')
        block = stash.main_video_block(page)
        self.assertIsNotNone(block)
        self.assertNotIn("stashmedia", block)
        self.assertEqual(stash.classify_content(block)["provider"], "vimeo")

    def test_absent_container_returns_none(self) -> None:
        self.assertIsNone(stash.main_video_block("<html><a href='https://vimeo.com/x'>"))


class ConfirmLinkTests(unittest.TestCase):
    def test_none_post_is_upgraded_from_its_main_video_block(self) -> None:
        post = {"id": 1, "link": f"{SITE}/p/", "provider": "none", "providers": [],
                "embedHosts": [], "eligible": False, "eligibilityReason": "x",
                "videoUrl": None, "gated": False}
        page = ('<div class="postvid_single"><iframe src="https://player.vimeo.com/video/7">'
                '</iframe></div>')
        check = stash.confirm_post_link(post, fetch=lambda url: page)
        self.assertEqual(post["provider"], "vimeo")
        self.assertEqual(check, {"checked": True, "mainVideoBlock": True, "provider": "vimeo"})

    def test_page_without_main_block_keeps_rest_classification(self) -> None:
        post = {"id": 2, "link": f"{SITE}/p/", "provider": "none", "providers": [],
                "embedHosts": [], "eligible": False, "eligibilityReason": "x",
                "videoUrl": None, "gated": False}
        check = stash.confirm_post_link(post, fetch=lambda url: "<html></html>")
        self.assertEqual(post["provider"], "none")
        self.assertFalse(check["mainVideoBlock"])

    def test_breaker_halts_after_repeated_429(self) -> None:
        catalog = {"posts": [
            {"id": i, "link": f"{SITE}/p{i}/", "provider": "none", "eligible": False,
             "providers": [], "embedHosts": [], "eligibilityReason": "x", "videoUrl": None,
             "gated": False} for i in range(5)]}

        def always_429(url: str) -> str:
            raise RuntimeError("request failed after bounded retries (last: "
                               "HTTP Error 429: Too Many Requests)")

        with self.assertRaises(RuntimeError) as raised:
            stash.confirm_links(catalog, fetch=always_429, sleep=lambda s: None,
                                delay_seconds=0)
        self.assertIn("repeated 429/5xx", str(raised.exception))
        checked = [p for p in catalog["posts"] if "linkCheck" in p]
        self.assertEqual(len(checked), 3)


class FetchAndEnumerateTests(unittest.TestCase):
    def test_retry_after_is_honoured_on_429(self) -> None:
        sleeps: list[float] = []
        calls = {"n": 0}

        class _Response:
            headers = {"content-type": "application/json"}

            def __enter__(self) -> "_Response":
                return self

            def __exit__(self, *exc: object) -> None:
                return None

            def read(self, n: int) -> bytes:
                return b'[{"id": 1}]'

        def fake_urlopen(request: object, timeout: float) -> _Response:
            calls["n"] += 1
            if calls["n"] == 1:
                raise HTTPError(request.full_url, 429, "Too Many", {"Retry-After": "7"}, None)
            return _Response()

        with patch.object(stash, "urlopen", side_effect=fake_urlopen):
            payload, _ = stash.fetch_page("https://www.stashmedia.tv/x", sleep=sleeps.append)
        self.assertEqual(payload, [{"id": 1}])
        self.assertEqual(sleeps, [7.0])

    def test_client_error_is_not_retried(self) -> None:
        def fake_urlopen(request: object, timeout: float) -> None:
            raise HTTPError(request.full_url, 404, "Not Found", {}, None)

        with patch.object(stash, "urlopen", side_effect=fake_urlopen):
            with self.assertRaises(ValueError):
                stash.fetch_page("https://www.stashmedia.tv/x", sleep=lambda s: None)

    def test_enumerate_walks_pages_and_keeps_all_posts(self) -> None:
        pages = {1: [_post(1, "<p>a</p>")], 2: [_post(2, '<iframe src="https://player.vimeo.com/video/3">')]}

        def fetch(url: str) -> tuple[object, dict[str, str]]:
            page_no = int(url.rsplit("page=", 1)[1])
            headers = {"x-wp-total": "2", "x-wp-totalpages": "2"}
            return pages[page_no], headers

        catalog = stash.enumerate_catalog(fetch=fetch, delay_seconds=0,
                                          sleep=lambda s: None, log=lambda m: None)
        self.assertEqual(catalog["totalPosts"], 2)
        self.assertEqual(catalog["totalPages"], 2)
        self.assertEqual(catalog["providerCounts"], {"none": 1, "vimeo": 1})
        self.assertEqual(catalog["posts"][0]["title"], "A & B")

    def test_duplicate_slugs_are_disambiguated(self) -> None:
        pages = {1: [_post(1, "", "same"), _post(2, "", "same")]}

        def fetch(url: str) -> tuple[object, dict[str, str]]:
            return pages[1], {"x-wp-total": "2", "x-wp-totalpages": "1"}

        catalog = stash.enumerate_catalog(fetch=fetch, delay_seconds=0, log=lambda m: None)
        self.assertEqual([p["slug"] for p in catalog["posts"]], ["same", "same-2"])


class IndexTests(unittest.TestCase):
    def test_index_has_one_row_per_post_and_counts(self) -> None:
        catalog = {"posts": [
            {"id": 1, "slug": "a", "title": "", "date": None, "link": "l", "provider": "vimeo",
             "eligible": False, "eligibilityReason": "vimeo", "videoUrl": None},
            {"id": 2, "slug": "b", "title": "", "date": None, "link": "l", "provider": "direct-mp4",
             "eligible": True, "eligibilityReason": "ok", "videoUrl": "u"},
            {"id": 3, "slug": "c", "title": "", "date": None, "link": "l", "provider": "none",
             "eligible": False, "eligibilityReason": "none", "videoUrl": None},
        ]}
        index = stash.build_index_rows(catalog, measured={2: {"recordPath": "videos/b.json"}})
        statuses = {row["id"]: row["status"] for row in index["rows"]}
        self.assertEqual(statuses, {1: "unsupported-vimeo", 2: "measured", 3: "no-video"})
        self.assertEqual(index["totalPosts"], 3)
        self.assertEqual(index["providerCounts"], {"direct-mp4": 1, "none": 1, "vimeo": 1})

    def test_failed_row_carries_reason(self) -> None:
        catalog = {"posts": [{"id": 9, "slug": "z", "title": "", "date": None, "link": "l",
                              "provider": "direct-mp4", "eligible": True,
                              "eligibilityReason": "ok", "videoUrl": "u"}]}
        index = stash.build_index_rows(catalog, failed={9: "download refused"})
        self.assertEqual(index["rows"][0]["status"], "failed")
        self.assertEqual(index["rows"][0]["reason"], "download refused")


class MeasureGuardTests(unittest.TestCase):
    def test_collect_refuses_non_direct_mp4(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                stash.collect_one({"id": 1, "slug": "v", "provider": "vimeo",
                                   "videoUrl": "https://player.vimeo.com/video/1"},
                                  Path(directory))

    def test_collect_rejects_non_allowlisted_host_before_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(stash, "download_media") as download:
                with self.assertRaises(ValueError):
                    stash.collect_one({"id": 1, "slug": "v", "provider": "direct-mp4",
                                       "videoUrl": "https://cdn.example.org/v.mp4"},
                                      Path(directory))
                download.assert_not_called()

    def test_media_is_deleted_and_record_marks_no_retention(self) -> None:
        seen: dict[str, Path] = {}

        def fake_download(url: str, provider: str, directory: Path, **kwargs: object):
            target = directory / "source.mp4"
            target.write_bytes(b"not really a video")
            seen["media"] = target
            return target, "http-download"

        def fake_source(path: Path, **kwargs: object) -> dict[str, object]:
            return {"durationSeconds": 5.0, "resolution": [1280, 720], "sizeBytes": 18,
                    "mediaSha256": "0" * 64}

        def fake_windows(path: Path, **kwargs: object):
            return {"sampledSeconds": 0.0}, []

        post = {"id": 5, "slug": "clip", "title": "Clip", "date": "2024", "link": f"{SITE}/clip/",
                "provider": "direct-mp4", "videoUrl": f"{SITE}/wp-content/clip.mp4"}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with patch.object(stash, "download_media", side_effect=fake_download), \
                    patch.object(stash, "source_metadata", side_effect=fake_source), \
                    patch.object(stash, "measure_windows", side_effect=fake_windows):
                record = stash.collect_one(post, out)
            self.assertFalse(seen["media"].exists())
            self.assertEqual(record["acquisition"]["mediaRetained"], False)
            self.assertEqual(record["rightsStatus"], "review-required")
            self.assertEqual(record["acquisition"]["attestation"]["rightsBasis"],
                             "user-declared-research-use")
            written = json.loads((out / "videos" / "clip.json").read_text(encoding="utf-8"))
            self.assertEqual(written["id"], 5)
            self.assertNotIn(".mp4", json.dumps(written.get("source", {}).get("path", "")))


class CliTests(unittest.TestCase):
    def test_help_documents_subcommands(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            stash.main(["--help"])
        text = out.getvalue()
        self.assertIn("enumerate", text)
        self.assertIn("measure", text)

    def test_measure_requires_rights_attestation(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            stash.main(["measure", "--catalog", "missing.json"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--acknowledge-rights", err.getvalue())

    def test_limit_must_be_non_negative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.json"
            catalog.write_text(json.dumps({"schemaVersion": stash.CATALOG_SCHEMA,
                                           "posts": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                stash.run_measure(catalog, out_dir=Path(directory), limit=-1,
                                  acknowledge_rights=True)


if __name__ == "__main__":
    unittest.main()
