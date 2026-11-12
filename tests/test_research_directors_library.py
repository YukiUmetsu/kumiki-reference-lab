"""Offline tests for the Directors' Library video research adapter (no network)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from kumiki_reference_lab import acquisition as acq
from scripts import research_directors_library as drl

ROOT = Path(__file__).resolve().parents[1]
PAGE = "https://directorslibrary.com/2026/latest/campaigns/demo/"


class _FakeResponse:
    def __init__(self, body: bytes, *, url: str, status: int = 200, headers=None):
        self._body = body
        self._url = url
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size: int = -1) -> bytes:
        chunk, self._body = self._body[:size], self._body[size:]
        return chunk

    def geturl(self) -> str:
        return self._url


class _Router:
    """Serves canned responses by URL prefix and records every request."""

    def __init__(self, routes: dict[str, object]):
        self.routes = routes
        self.requested: list[str] = []

    def __call__(self, request, timeout=None):
        url = request.full_url
        self.requested.append(url)
        for prefix, reply in self.routes.items():
            if url.startswith(prefix):
                if isinstance(reply, list):
                    outcome = reply.pop(0)
                    if isinstance(outcome, Exception):
                        raise outcome
                    return outcome
                return reply
        raise AssertionError(f"unexpected request: {url}")


def _http_error(url: str, code: int, retry_after: str | None = None) -> HTTPError:
    headers = {"Retry-After": retry_after} if retry_after else {}
    return HTTPError(url, code, "blocked", headers, None)


def _client(opener, sleeps: list[float]) -> drl.Client:
    return drl.Client(
        delay_seconds=1.5, jitter_seconds=0.0, opener=opener,
        sleep=sleeps.append, clock=lambda: 0.0, uniform=lambda a, b: a)


class ClassifyTests(unittest.TestCase):
    def test_vimeo_iframe_is_unsupported_vimeo(self) -> None:
        html = ('<iframe class="dl-primary-video-frame" src="https://player.vimeo.com/'
                'video/1236008415?dnt=1&amp;app_id=122963"></iframe>')
        verdict = drl.classify_page(html, PAGE)
        self.assertEqual(verdict["provider"], "vimeo")
        self.assertFalse(verdict["eligible"])
        self.assertIsNone(verdict["videoUrl"])

    def test_youtube_embed_variants_are_unsupported_youtube(self) -> None:
        for src in ("https://www.youtube.com/embed/abc",
                    "https://www.youtube-nocookie.com/embed/abc",
                    "https://youtu.be/abc"):
            verdict = drl.classify_page(f'<iframe src="{src}"></iframe>', PAGE)
            self.assertEqual(verdict["provider"], "youtube", src)

    def test_channel_link_is_not_an_embed(self) -> None:
        html = '<a href="https://www.youtube.com/@directorslibrary">channel</a>'
        self.assertEqual(drl.classify_page(html, PAGE)["provider"], "no-video")

    def test_self_hosted_mp4_on_exact_host_is_eligible(self) -> None:
        html = ('<video><source src="https://directorslibrary.com/wp-content/demo.mp4">'
                '</video>')
        verdict = drl.classify_page(html, PAGE)
        self.assertEqual(verdict["provider"], "direct-mp4")
        self.assertTrue(verdict["eligible"])
        self.assertEqual(verdict["videoUrl"],
                         "https://directorslibrary.com/wp-content/demo.mp4")

    def test_tokenised_mp4_is_not_eligible(self) -> None:
        html = '<video><source src="https://directorslibrary.com/a.mp4?sig=1"></video>'
        verdict = drl.classify_page(html, PAGE)
        self.assertEqual(verdict["provider"], "other")
        self.assertFalse(verdict["eligible"])

    def test_mp4_on_other_host_or_hls_is_not_eligible(self) -> None:
        for src in ("https://cdn.example.com/a.mp4",
                    "https://directorslibrary.com/a.m3u8",
                    "https://sub.directorslibrary.com/a.mp4",
                    "http://directorslibrary.com/a.mp4"):
            verdict = drl.classify_page(f'<video><source src="{src}"></video>', PAGE)
            self.assertNotEqual(verdict["provider"], "direct-mp4", src)

    def test_og_video_meta_is_read(self) -> None:
        html = ('<meta property="og:video" content="https://player.vimeo.com/video/9">')
        self.assertEqual(drl.classify_page(html, PAGE)["provider"], "vimeo")


class ClientTests(unittest.TestCase):
    def test_refuses_delay_below_site_minimum(self) -> None:
        with self.assertRaises(ValueError):
            drl.Client(delay_seconds=1.0)

    def test_honours_retry_after_then_succeeds(self) -> None:
        sleeps: list[float] = []
        router = _Router({PAGE: [
            _http_error(PAGE, 429, retry_after="7"),
            _FakeResponse(b"<html></html>", url=PAGE, headers={}),
        ]})
        status, _, body = _client(router, sleeps).get(PAGE, accept="text/html", limit=1000)
        self.assertEqual((status, body), (200, b"<html></html>"))
        self.assertIn(7.0, sleeps)
        self.assertEqual(len(router.requested), 2)

    def test_stops_after_three_consecutive_blocks(self) -> None:
        sleeps: list[float] = []
        router = _Router({PAGE: [_http_error(PAGE, 503) for _ in range(4)]})
        with self.assertRaises(drl.RateLimitStop):
            _client(router, sleeps).get(PAGE, accept="text/html", limit=1000)
        self.assertEqual(len(router.requested), 3)

    def test_paces_consecutive_requests(self) -> None:
        sleeps: list[float] = []
        times = iter([0.0, 0.2, 0.2, 0.2])
        router = _Router({PAGE: [
            _FakeResponse(b"a", url=PAGE), _FakeResponse(b"b", url=PAGE)]})
        client = drl.Client(delay_seconds=1.5, jitter_seconds=0.0, opener=router,
                            sleep=sleeps.append, clock=lambda: next(times),
                            uniform=lambda a, b: a)
        client.get(PAGE, accept="text/html", limit=10)
        client.get(PAGE, accept="text/html", limit=10)
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 1.3, places=6)

    def test_rejects_off_host_and_query_only_on_page_urls(self) -> None:
        router = _Router({})
        with self.assertRaises(ValueError):
            _client(router, []).get("https://evil.example.com/x/", accept="text/html", limit=10)
        self.assertEqual(router.requested, [])


class EnumerateTests(unittest.TestCase):
    def _routes(self, entries: list[dict], pages: dict[str, bytes]) -> _Router:
        rest = "https://directorslibrary.com/wp-json/wp/v2/video"
        payload = json.dumps(entries).encode()
        routes: dict[str, object] = {
            rest: _FakeResponse(payload, url=rest + "?x", headers={
                "x-wp-totalpages": "1", "x-wp-total": str(len(entries))}),
        }
        for link, body in pages.items():
            routes[link] = _FakeResponse(body, url=link)
        return _Router(routes)

    def test_enumerate_writes_catalog_and_index_without_fetching_media(self) -> None:
        entries = [
            {"id": 3, "slug": "a", "link": PAGE + "a/", "title": {"rendered": "A &amp; B"},
             "date": "2026-01-01T00:00:00", "content": {"rendered": "<p>x</p>"}},
            {"id": 2, "slug": "b", "link": PAGE + "b/", "title": {"rendered": "B"},
             "date": None, "content": {"rendered": "<iframe src='https://youtu.be/x'>"}},
            {"id": 1, "slug": "c", "link": PAGE + "c/", "title": {"rendered": "C"},
             "date": None, "content": {"rendered": ""}},
        ]
        pages = {
            PAGE + "a/": b'<iframe src="https://player.vimeo.com/video/1"></iframe>',
            PAGE + "b/": b'<iframe src="https://www.youtube.com/embed/x"></iframe>',
            PAGE + "c/": b'<video><source src="https://directorslibrary.com/c.mp4"></video>',
        }
        router = self._routes(entries, pages)
        sleeps: list[float] = []
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            drl.run_enumerate(out, client=_client(router, sleeps), log=lambda *_: None)
            catalog = json.loads((out / "catalog.json").read_text())
            index = json.loads((out / "index.json").read_text())
            self.assertFalse((out / ".classify-cache.jsonl").exists())
        self.assertEqual(catalog["entryCount"], 3)
        self.assertEqual(catalog["providerCounts"],
                         {"direct-mp4": 1, "vimeo": 1, "youtube": 1})
        self.assertEqual(catalog["eligibleCount"], 1)
        titles = {row["id"]: row["title"] for row in catalog["entries"]}
        self.assertEqual(titles[3], "A & B")
        self.assertEqual(index["counts"], {"pending-measure": 1,
                                           "unsupported-vimeo": 1,
                                           "unsupported-youtube": 1})
        self.assertEqual(index["entryCount"], 3)
        self.assertFalse(any("player.vimeo.com" in url or "youtube" in url
                             for url in router.requested))

    def test_index_status_vocabulary_and_failures(self) -> None:
        catalog = {"entries": [
            {"id": 1, "slug": "a", "title": "A", "provider": "vimeo"},
            {"id": 2, "slug": "b", "title": "B", "provider": "no-video"},
            {"id": 3, "slug": "c", "title": "C", "provider": "direct-mp4"},
            {"id": 4, "slug": "d", "title": "D", "provider": "unclassified",
             "classifyError": "entry page not found"},
            {"id": 5, "slug": "e", "title": "E", "provider": "direct-mp4"},
        ]}
        index = drl.build_index(catalog, measured={5: "videos/e.json"},
                                failures={3: "download failed"}, catalog_sha256="0" * 64)
        status = {row["id"]: row["status"] for row in index["rows"]}
        self.assertEqual(status, {1: "unsupported-vimeo", 2: "no-video", 3: "failed",
                                  4: "failed", 5: "measured"})
        self.assertEqual(index["entryCount"], 5)


class MeasureGuardTests(unittest.TestCase):
    def test_collect_one_refuses_non_eligible_and_foreign_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with self.assertRaises(ValueError):
                drl.collect_one({"id": 1, "slug": "a", "provider": "vimeo",
                                 "eligible": False, "videoUrl": None}, out)
            with self.assertRaises(ValueError):
                drl.collect_one({"id": 1, "slug": "a", "provider": "direct-mp4",
                                 "eligible": True,
                                 "videoUrl": "https://cdn.example.com/a.mp4"}, out)
            self.assertFalse((out / "videos").exists())

    def test_measure_requires_rights_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                drl.run_measure(Path(tmp) / "catalog.json", out_dir=Path(tmp))


class CliTests(unittest.TestCase):
    def test_help_documents_commands_and_limit(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), self.assertRaises(SystemExit):
            drl.main(["--help"])
        text = buffer.getvalue()
        self.assertIn("enumerate", text)
        self.assertIn("measure", text)

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), self.assertRaises(SystemExit):
            drl.main(["enumerate", "--help"])
        self.assertIn("--limit", buffer.getvalue())


class BoundaryTests(unittest.TestCase):
    def test_engine_stays_site_agnostic(self) -> None:
        engine = ROOT / "src" / "kumiki_reference_lab" / "acquisition"
        text = "\n".join(path.read_text(encoding="utf-8").lower()
                         for path in engine.glob("*.py"))
        for term in ("directorslibrary", "directors-library", "vimeo", "youtube",
                     "keyfram", "cloudflare", "yt-dlp", "motiondesignawards"):
            self.assertNotIn(term, text)

    def test_engine_allowlist_rejects_query_for_media(self) -> None:
        with self.assertRaises(ValueError):
            acq.allowlisted_video_url(
                "https://directorslibrary.com/a.mp4?token=1",
                allowed_hosts=drl.VIDEO_HOSTS)


if __name__ == "__main__":
    unittest.main()
