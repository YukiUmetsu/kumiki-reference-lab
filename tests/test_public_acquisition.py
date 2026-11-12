"""Offline contract tests for the site-agnostic acquisition package.

No network and no ffmpeg: HTTP is replaced by an in-memory response and the
ffprobe adapter is exercised through a patched ``subprocess.run``.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab import acquisition as acq

ALLOWED_HOSTS = ("media.example", ".cdn.example")


class _FakeResponse:
    """Minimal urlopen-compatible response over an in-memory body."""

    def __init__(self, body: bytes, url: str) -> None:
        self._body = body
        self._url = url
        self._position = 0

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


def patched_urlopen(body: bytes, response_url: str):
    def fake_urlopen(request, timeout=None):  # noqa: ANN001 - test double
        return _FakeResponse(body, response_url)

    return patch.object(acq.media, "urlopen", side_effect=fake_urlopen)


def rgb_buffer(width: int, height: int, pixel) -> bytes:  # noqa: ANN001
    return bytes(
        component
        for y in range(height)
        for x in range(width)
        for component in pixel(x, y)
    )


def synthetic_probe(
    cuts: int, luma: float, saturation: float, frame_count: int,
    per_second: list[float | None],
) -> dict:
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


class AllowlistTests(unittest.TestCase):
    def test_accepts_exact_host_and_explicit_subdomain(self) -> None:
        for url in (
            "https://media.example/clip.mp4",
            "https://media.example:443/clip.mp4",
            "https://edge.cdn.example/clip.mp4",
            "https://MEDIA.EXAMPLE/clip.mp4",
        ):
            self.assertEqual(
                acq.allowlisted_url(url, allowed_hosts=ALLOWED_HOSTS), url)

    def test_rejects_scheme_userinfo_port_query_fragment_and_host_forms(self) -> None:
        for url in (
            "http://media.example/clip.mp4",
            "ftp://media.example/clip.mp4",
            "https://user:pass@media.example/clip.mp4",
            "https://user@media.example/clip.mp4",
            "https://media.example:8443/clip.mp4",
            "https://media.example/clip.mp4?token=abc",
            "https://media.example/clip.mp4#frag",
            "https://evil.example/clip.mp4",
            "https://media.example.evil.example/clip.mp4",
            "https://evil.example/media.example/clip.mp4",
            "https://sub.media.example/clip.mp4",
            "https://cdn.example/clip.mp4",
            "https://cdn.example.evil.example/clip.mp4",
            "https://media.example./clip.mp4",
            "https:///clip.mp4",
            "https://127.0.0.1/clip.mp4",
            "https://[::1]/clip.mp4",
            "https://localhost/clip.mp4",
            "",
            "   ",
            None,
            42,
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                acq.allowlisted_url(url, allowed_hosts=ALLOWED_HOSTS)

    def test_thin_helpers_share_the_policy(self) -> None:
        self.assertEqual(
            acq.allowlisted_video_url(
                "https://media.example/clip.mp4", allowed_hosts=ALLOWED_HOSTS),
            "https://media.example/clip.mp4")
        self.assertEqual(
            acq.allowlisted_image_url(
                "https://media.example/poster.png", allowed_hosts=ALLOWED_HOSTS),
            "https://media.example/poster.png")
        with self.assertRaisesRegex(ValueError, "video source URL"):
            acq.allowlisted_video_url(
                "https://evil.example/clip.mp4", allowed_hosts=ALLOWED_HOSTS)
        with self.assertRaisesRegex(ValueError, "still image URL"):
            acq.allowlisted_image_url(
                "http://media.example/poster.png", allowed_hosts=ALLOWED_HOSTS)

    def test_allowlist_configuration_is_validated(self) -> None:
        for hosts in ("media.example", (), ("bad_host!",), (".",), (None,)):
            with self.subTest(hosts=hosts), self.assertRaises(ValueError):
                acq.allowlisted_url(
                    "https://media.example/clip.mp4", allowed_hosts=hosts)

    def test_any_public_host_wildcard_admits_every_public_dns_name(self) -> None:
        for url in ("https://media.example/clip.mp4",
                    "https://cdn.other-site.test/a/b.mp4",
                    "https://vimeo.com/123456"):
            with self.subTest(url=url):
                self.assertEqual(
                    acq.allowlisted_url(url, allowed_hosts=("*",)), url)

    def test_any_public_host_wildcard_keeps_every_other_guard(self) -> None:
        for url in ("http://media.example/clip.mp4",
                    "https://user:pw@media.example/clip.mp4",
                    "https://media.example:8443/clip.mp4",
                    "https://media.example/clip.mp4?token=1",
                    "https://media.example/clip.mp4#frag",
                    "https://192.0.2.10/clip.mp4",
                    "https://[2001:db8::1]/clip.mp4",
                    "https://localhost/clip.mp4",
                    "https://intranet/clip.mp4"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                acq.allowlisted_url(url, allowed_hosts=("*",))

    def test_wildcard_mixes_with_explicit_entries(self) -> None:
        self.assertEqual(
            acq.allowlisted_url("https://a.test/x.mp4",
                                allowed_hosts=("media.example", "*")),
            "https://a.test/x.mp4")

    def test_query_is_rejected_by_default_and_admitted_only_on_opt_in(self) -> None:
        signed = ("https://media.example/clip.mp4?"
                  "AWSAccessKeyId=AKIAEXAMPLE&Expires=1&Signature=abc")
        with self.assertRaisesRegex(ValueError, "query string"):
            acq.allowlisted_url(signed, allowed_hosts=ALLOWED_HOSTS)
        self.assertEqual(
            acq.allowlisted_url(
                signed, allowed_hosts=ALLOWED_HOSTS, allow_query=True),
            signed)
        self.assertEqual(
            acq.allowlisted_url(
                "https://edge.cdn.example/clip.mp4?profile=1&useCDN=true",
                allowed_hosts=ALLOWED_HOSTS, allow_query=True),
            "https://edge.cdn.example/clip.mp4?profile=1&useCDN=true")

    def test_query_opt_in_keeps_every_other_invariant(self) -> None:
        for url in (
            "http://media.example/clip.mp4?Signature=x",
            "https://user:pass@media.example/clip.mp4?Signature=x",
            "https://user@media.example/clip.mp4?Signature=x",
            "https://media.example:8443/clip.mp4?Signature=x",
            "https://media.example/clip.mp4?Signature=x#frag",
            "https://evil.example/clip.mp4?Signature=x",
            "https://media.example.evil.example/clip.mp4?Signature=x",
            "https://sub.media.example/clip.mp4?Signature=x",
            "https://cdn.example/clip.mp4?Signature=x",
            "https://media.example./clip.mp4?Signature=x",
            "https://127.0.0.1/clip.mp4?Signature=x",
            "https://[::1]/clip.mp4?Signature=x",
            "https://localhost/clip.mp4?Signature=x",
            "",
            None,
            42,
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                acq.allowlisted_url(
                    url, allowed_hosts=ALLOWED_HOSTS, allow_query=True)

    def test_thin_helpers_thread_the_query_opt_in(self) -> None:
        signed = "https://media.example/clip.mp4?Signature=x"
        self.assertEqual(
            acq.allowlisted_video_url(
                signed, allowed_hosts=ALLOWED_HOSTS, allow_query=True),
            signed)
        self.assertEqual(
            acq.allowlisted_image_url(
                "https://media.example/poster.png?Signature=x",
                allowed_hosts=ALLOWED_HOSTS, allow_query=True),
            "https://media.example/poster.png?Signature=x")
        with self.assertRaisesRegex(ValueError, "query string"):
            acq.allowlisted_video_url(signed, allowed_hosts=ALLOWED_HOSTS)


class AsciiUrlTests(unittest.TestCase):
    def test_non_ascii_path_is_percent_encoded_as_utf8(self) -> None:
        self.assertEqual(
            acq.ascii_url(
                "https://media.example/Ordinary-Rio-40°-André.jpg"),
            "https://media.example/Ordinary-Rio-40%C2%B0-Andr%C3%A9.jpg")

    def test_already_encoded_url_is_unchanged(self) -> None:
        url = ("https://media.example/a%20b%C3%A9.jpg?"
               "name=Andr%C3%A9&x=1#frag%20ment")
        self.assertEqual(acq.ascii_url(url), url)

    def test_plain_ascii_url_is_byte_identical(self) -> None:
        for url in (
            "https://media.example/clip.mp4",
            "https://MEDIA.EXAMPLE:443/a/b.mp4?Signature=x&Expires=1",
            "http://www.stashmedia.tv/wp-content/uploads/poster.jpg",
        ):
            with self.subTest(url=url):
                self.assertEqual(acq.ascii_url(url), url)

    def test_non_ascii_query_value_is_encoded(self) -> None:
        self.assertEqual(
            acq.ascii_url("https://media.example/p.jpg?name=André&x=1"),
            "https://media.example/p.jpg?name=Andr%C3%A9&x=1")

    def test_non_ascii_fragment_is_encoded(self) -> None:
        self.assertEqual(
            acq.ascii_url("https://media.example/p.jpg#André"),
            "https://media.example/p.jpg#Andr%C3%A9")

    def test_non_ascii_host_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "host"):
            acq.ascii_url("https://exämple.com/p.jpg")

    def test_port_and_userinfo_are_preserved(self) -> None:
        self.assertEqual(
            acq.ascii_url("https://user:pw@media.example:8443/André.jpg"),
            "https://user:pw@media.example:8443/Andr%C3%A9.jpg")

    def test_scheme_is_enforced(self) -> None:
        for url in (
            "ftp://media.example/André.jpg",
            "file:///tmp/André.jpg",
            "mailto:andre@example.com",
            "https:///André.jpg",
            "",
            "   ",
            None,
            42,
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                acq.ascii_url(url)

    def test_allowlist_validates_the_normalized_form(self) -> None:
        self.assertEqual(
            acq.allowlisted_url(
                "https://media.example/André.jpg?name=André",
                allowed_hosts=ALLOWED_HOSTS, allow_query=True),
            "https://media.example/Andr%C3%A9.jpg?name=Andr%C3%A9")
        self.assertEqual(
            acq.allowlisted_image_url(
                "https://media.example/André.png", allowed_hosts=ALLOWED_HOSTS),
            "https://media.example/Andr%C3%A9.png")
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            acq.allowlisted_url(
                "https://evil.example/André.jpg", allowed_hosts=ALLOWED_HOSTS)
        with self.assertRaisesRegex(ValueError, "host"):
            acq.allowlisted_url(
                "https://exämple.com/André.jpg", allowed_hosts=ALLOWED_HOSTS)

    def test_fetch_bytes_requests_the_encoded_url(self) -> None:
        seen: list[str] = []

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            seen.append(request.full_url)
            return _FakeResponse(b"#EXTM3U\n", request.full_url)

        iri = "https://media.example/Ordinary-Rio-40°-André.m3u8"
        encoded = ("https://media.example/"
                   "Ordinary-Rio-40%C2%B0-Andr%C3%A9.m3u8")
        with patch.object(acq.media, "urlopen", side_effect=fake_urlopen):
            payload = acq.fetch_bytes(
                iri, allowed_hosts=ALLOWED_HOSTS, max_bytes=64)
        self.assertEqual(payload, b"#EXTM3U\n")
        self.assertEqual(seen, [encoded])

    def test_download_http_requests_the_encoded_url(self) -> None:
        seen: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "poster.img"

            def fake_urlopen(request, timeout=None):  # noqa: ANN001
                seen.append(request.full_url)
                return _FakeResponse(b"image-bytes", request.full_url)

            iri = "https://media.example/André poster.jpg"
            encoded = "https://media.example/Andr%C3%A9%20poster.jpg"
            with patch.object(acq.media, "urlopen", side_effect=fake_urlopen):
                result = acq.download_http(
                    iri, target, allowed_hosts=ALLOWED_HOSTS, max_bytes=1024)
            self.assertEqual(result, target)
            self.assertEqual(target.read_bytes(), b"image-bytes")
        self.assertEqual(seen, [encoded])


class BoundedFetchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_download_http_enforces_the_byte_cap(self) -> None:
        target = self.root / "source.mp4"
        with patched_urlopen(b"x" * 4000, "https://media.example/clip.mp4"):
            with self.assertRaisesRegex(ValueError, "bounded local size cap"):
                acq.download_http(
                    "https://media.example/clip.mp4", target,
                    allowed_hosts=ALLOWED_HOSTS, max_bytes=1024,
                    chunk_size=512)
        self.assertTrue(target.is_file())
        self.assertLessEqual(target.stat().st_size, 1024)

    def test_download_http_accepts_an_in_budget_body(self) -> None:
        target = self.root / "source.mp4"
        body = b"media-bytes" * 100
        with patched_urlopen(body, "https://media.example/clip.mp4"):
            result = acq.download_http(
                "https://media.example/clip.mp4", target,
                allowed_hosts=ALLOWED_HOSTS, max_bytes=len(body))
        self.assertEqual(result, target)
        self.assertEqual(target.read_bytes(), body)

    def test_redirect_to_a_non_allowlisted_host_is_refused(self) -> None:
        target = self.root / "source.mp4"
        with patched_urlopen(b"payload", "https://evil.example/clip.mp4"):
            with self.assertRaisesRegex(ValueError, "not allowlisted"):
                acq.download_http(
                    "https://media.example/clip.mp4", target,
                    allowed_hosts=ALLOWED_HOSTS, max_bytes=1024)
        self.assertFalse(target.exists())

    def test_signed_redirect_is_followed_and_its_query_preserved(self) -> None:
        target = self.root / "source.mp4"
        initial = ("https://media.example/download?profile=1&useCDN=true")
        signed = ("https://edge.cdn.example/clip.mp4?"
                  "AWSAccessKeyId=AKIAEXAMPLE&Expires=1&Signature=abc")
        seen: list[str] = []

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            seen.append(request.full_url)
            return _FakeResponse(b"payload", signed)

        with patch.object(acq.media, "urlopen", side_effect=fake_urlopen):
            result = acq.download_http(
                initial, target, allowed_hosts=ALLOWED_HOSTS,
                max_bytes=1024, allow_query=True)
        self.assertEqual(result, target)
        self.assertEqual(target.read_bytes(), b"payload")
        self.assertEqual(seen, [initial])
        self.assertIn("AWSAccessKeyId=AKIAEXAMPLE", signed)

    def test_signed_redirect_is_refused_without_the_opt_in(self) -> None:
        target = self.root / "source.mp4"
        signed = ("https://edge.cdn.example/clip.mp4?"
                  "AWSAccessKeyId=AKIAEXAMPLE&Expires=1&Signature=abc")
        with patched_urlopen(b"payload", signed):
            with self.assertRaisesRegex(ValueError, "query string"):
                acq.download_http(
                    "https://media.example/clip.mp4", target,
                    allowed_hosts=ALLOWED_HOSTS, max_bytes=1024)
        self.assertFalse(target.exists())

    def test_signed_redirect_to_a_non_allowlisted_host_is_still_refused(self) -> None:
        target = self.root / "source.mp4"
        with patched_urlopen(
                b"payload", "https://evil.example/clip.mp4?Signature=abc"):
            with self.assertRaisesRegex(ValueError, "not allowlisted"):
                acq.download_http(
                    "https://media.example/clip.mp4", target,
                    allowed_hosts=ALLOWED_HOSTS, max_bytes=1024,
                    allow_query=True)
        self.assertFalse(target.exists())

    def test_fetch_bytes_truncates_and_fetch_text_decodes(self) -> None:
        with patched_urlopen(b"a" * 5000, "https://media.example/playlist.m3u8"):
            payload = acq.fetch_bytes(
                "https://media.example/playlist.m3u8",
                allowed_hosts=ALLOWED_HOSTS, max_bytes=1000)
            self.assertEqual(len(payload), 1000)
        with patched_urlopen(b"#EXTM3U\n", "https://media.example/playlist.m3u8"):
            text = acq.fetch_text(
                "https://media.example/playlist.m3u8",
                allowed_hosts=ALLOWED_HOSTS)
        self.assertEqual(text, "#EXTM3U\n")

    def test_check_downloaded_rejects_empty_oversized_and_symlinks(self) -> None:
        empty = self.root / "empty.mp4"
        empty.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "empty"):
            acq.check_downloaded(empty, max_bytes=10)
        large = self.root / "large.mp4"
        large.write_bytes(b"x" * 64)
        with self.assertRaisesRegex(ValueError, "bounded local size cap"):
            acq.check_downloaded(large, max_bytes=8)
        link = self.root / "link.mp4"
        link.symlink_to(large)
        with self.assertRaisesRegex(ValueError, "no regular"):
            acq.check_downloaded(link, max_bytes=1024)
        with self.assertRaises(ValueError):
            acq.download_http(
                "https://media.example/clip.mp4", self.root / "x.mp4",
                allowed_hosts=ALLOWED_HOSTS, max_bytes=0)

    def test_target_names_keep_known_suffixes_only(self) -> None:
        directory = self.root
        self.assertEqual(
            acq.media_target(directory, "https://media.example/a.WEBM").name,
            "source.webm")
        self.assertEqual(
            acq.media_target(directory, "https://media.example/a.m3u8").name,
            "source.mp4")
        self.assertEqual(
            acq.image_target(directory, "https://media.example/a.png").name,
            "poster.png")
        self.assertEqual(
            acq.image_target(directory, "https://media.example/a.bin").name,
            "poster.img")


HLS_MASTER = """#EXTM3U
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud-hi",NAME="hi",URI="audio/hi.m3u8"
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud-lo",NAME="lo",URI="audio/lo.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360,AUDIO="aud-lo"
low/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2400000,RESOLUTION=1280x720,AUDIO="aud-hi"
mid/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=5200000,RESOLUTION=1920x1080,AUDIO="aud-hi"
high/index.m3u8
"""


class HlsPlanTests(unittest.TestCase):
    master = "https://edge.cdn.example/master.m3u8"

    def plan(self, **kwargs) -> dict:
        return acq.plan_hls_download(
            self.master, allowed_hosts=ALLOWED_HOSTS,
            master_text=HLS_MASTER, **kwargs)

    def test_picks_the_widest_variant_within_the_width_budget(self) -> None:
        plan = self.plan(max_width=1280)
        self.assertEqual(plan["variantUrl"],
                         "https://edge.cdn.example/mid/index.m3u8")
        self.assertEqual((plan["width"], plan["height"]), (1280, 720))
        self.assertEqual(plan["audioUrl"],
                         "https://edge.cdn.example/audio/hi.m3u8")

    def test_resolves_the_audio_group_of_the_chosen_variant(self) -> None:
        plan = self.plan(max_width=1000)
        self.assertEqual(plan["variantUrl"],
                         "https://edge.cdn.example/low/index.m3u8")
        self.assertEqual(plan["audioUrl"],
                         "https://edge.cdn.example/audio/lo.m3u8")

    def test_falls_back_to_the_smallest_variant_when_none_fit(self) -> None:
        plan = self.plan(max_width=400)
        self.assertEqual(plan["variantUrl"],
                         "https://edge.cdn.example/low/index.m3u8")
        self.assertEqual((plan["width"], plan["height"]), (640, 360))

    def test_accepts_the_largest_variant_when_the_budget_allows(self) -> None:
        plan = self.plan(max_width=4000)
        self.assertEqual(plan["variantUrl"],
                         "https://edge.cdn.example/high/index.m3u8")
        self.assertEqual((plan["width"], plan["height"]), (1920, 1080))

    def test_master_without_variants_returns_the_master(self) -> None:
        plan = acq.plan_hls_download(
            self.master, allowed_hosts=ALLOWED_HOSTS,
            master_text='#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="a",'
                        'URI="audio.m3u8"\n')
        self.assertEqual(plan["variantUrl"], self.master)
        self.assertEqual(plan["audioUrl"],
                         "https://edge.cdn.example/audio.m3u8")
        self.assertIsNone(plan["width"])
        self.assertIsNone(plan["height"])

    def test_allowlist_iterables_are_materialised_for_repeated_checks(self) -> None:
        plan = acq.plan_hls_download(
            self.master, allowed_hosts=iter(ALLOWED_HOSTS),
            master_text=HLS_MASTER, max_width=1280)
        self.assertEqual(plan["variantUrl"],
                         "https://edge.cdn.example/mid/index.m3u8")

    def test_rejects_non_playlists_disallowed_hosts_and_bad_budgets(self) -> None:
        with self.assertRaisesRegex(ValueError, "not returned"):
            acq.plan_hls_download(
                self.master, allowed_hosts=ALLOWED_HOSTS,
                master_text="not a playlist")
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            acq.plan_hls_download(
                "https://evil.example/master.m3u8",
                allowed_hosts=ALLOWED_HOSTS, master_text=HLS_MASTER)
        with self.assertRaises(ValueError):
            self.plan(max_width=0)
        rogue = (
            '#EXTM3U\n#EXT-X-STREAM-INF:RESOLUTION=640x360\n'
            'https://evil.example/low.m3u8\n')
        with self.assertRaisesRegex(ValueError, "variant URL"):
            acq.plan_hls_download(
                self.master, allowed_hosts=ALLOWED_HOSTS, master_text=rogue)

    def test_query_bearing_variants_need_the_opt_in(self) -> None:
        text = (
            '#EXTM3U\n#EXT-X-STREAM-INF:RESOLUTION=640x360\n'
            'low/index.m3u8?AWSAccessKeyId=x&Signature=y\n')
        with self.assertRaisesRegex(ValueError, "query string"):
            acq.plan_hls_download(
                self.master, allowed_hosts=ALLOWED_HOSTS, master_text=text)
        plan = acq.plan_hls_download(
            self.master, allowed_hosts=ALLOWED_HOSTS, master_text=text,
            allow_query=True)
        self.assertEqual(
            plan["variantUrl"],
            "https://edge.cdn.example/low/index.m3u8?AWSAccessKeyId=x&Signature=y")


class WindowAndSummaryTests(unittest.TestCase):
    def test_window_plan_starts_at_zero_and_skips_the_trailing_decile(self) -> None:
        span, count, starts, fraction = acq.plan_windows(
            45.2, count=4, seconds=10)
        self.assertEqual((span, count), (10, 4))
        self.assertEqual(starts[0], 0)
        self.assertLessEqual(starts[-1] + span, 45.2 * 0.9)
        self.assertAlmostEqual(fraction, round(40 / 45.2, 6))
        for earlier, later in zip(starts, starts[1:]):
            self.assertGreaterEqual(later, earlier + span)

    def test_short_source_collapses_to_one_window(self) -> None:
        self.assertEqual(
            acq.plan_windows(8.0, count=4, seconds=10), (7, 1, [0], 0.875))

    def test_count_larger_than_available_runtime_is_capped(self) -> None:
        span, count, starts, fraction = acq.plan_windows(
            15.0, count=4, seconds=10)
        self.assertEqual((span, count, starts), (10, 1, [0]))
        self.assertAlmostEqual(fraction, round(10 / 15.0, 6))

    def test_usable_runtime_is_capped_at_one_hour(self) -> None:
        span, count, starts, _ = acq.plan_windows(10000.0, count=4, seconds=30)
        self.assertEqual((span, count), (30, 4))
        self.assertEqual(starts, [0, 1190, 2380, 3570])
        self.assertEqual(starts[-1] + span, 3600)

    def test_invalid_budgets_and_durations_are_refused(self) -> None:
        for duration, count, seconds in (
            (0.0, 4, 10), (-1.0, 4, 10), (float("nan"), 4, 10),
            (30.0, 0, 10), (30.0, 21, 10), (30.0, 4, 0), (30.0, 4, 31),
            (0.5, 4, 10),
        ):
            with self.subTest(duration=duration, count=count, seconds=seconds), \
                    self.assertRaises(ValueError):
                acq.plan_windows(duration, count=count, seconds=seconds)

    def test_summary_derives_only_from_probe_fields(self) -> None:
        summary = acq.summarize_probes([
            synthetic_probe(2, 0.5, 0.25, 3, [1.0, 3.0, None]),
            synthetic_probe(0, 0.7, 0.35, 2, [2.0]),
        ], sampled_seconds=20.0)
        self.assertEqual(summary["cutCandidates"], 2)
        self.assertAlmostEqual(summary["cutCandidateRatePerMinute"], 6.0)
        self.assertAlmostEqual(summary["meanDisplayLuma"], 0.6)
        self.assertAlmostEqual(summary["meanSaturation"], 0.3)
        self.assertAlmostEqual(summary["meanWithinShotRgbDeltaPerSecond"], 2.0)
        self.assertEqual(summary["sampledFrames"], 5)
        self.assertEqual(summary["windowsWithCuts"], 1)

    def test_missing_probe_fields_become_null(self) -> None:
        summary = acq.summarize_probes(
            [{"sampledWindowSummary": {}, "sampledFrames": [],
              "sampledFramePairs": []}],
            sampled_seconds=10.0)
        self.assertEqual(summary["cutCandidates"], 0)
        self.assertEqual(summary["cutCandidateRatePerMinute"], 0.0)
        self.assertIsNone(summary["meanDisplayLuma"])
        self.assertIsNone(summary["meanSaturation"])
        self.assertIsNone(summary["meanWithinShotRgbDeltaPerSecond"])


class ProbeAdapterTests(unittest.TestCase):
    def test_metadata_reduction_reports_duration_dimensions_and_size(self) -> None:
        metadata = acq.metadata_from_probe({
            "format": {"duration": "10.0", "bit_rate": "800000"},
            "streams": [{"codec_type": "video", "width": 640, "height": 360}],
        })
        self.assertEqual(metadata["durationSeconds"], 10.0)
        self.assertEqual((metadata["width"], metadata["height"]), (640, 360))
        self.assertEqual(metadata["bitRate"], 800000.0)
        self.assertEqual(metadata["estimatedBytes"], 1_000_000.0)

    def test_probe_retries_with_linear_backoff_then_succeeds(self) -> None:
        responses = [
            subprocess.CompletedProcess([], 1, "", "first failure"),
            subprocess.CompletedProcess([], 1, "", ""),
            subprocess.CompletedProcess([], 0, '{"streams": []}', ""),
        ]
        backoff: list[float] = []
        with patch.object(acq.probe.subprocess, "run", side_effect=responses):
            payload = acq.run_ffprobe_json(
                "https://media.example/clip.mp4", attempts=3, network=True,
                sleep=backoff.append)
        self.assertEqual(payload, {"streams": []})
        self.assertEqual(backoff, [1.5, 3.0])

    def test_probe_failure_reports_the_last_stderr_tail(self) -> None:
        failures = [
            subprocess.CompletedProcess([], 1, "", "transport reset"),
            subprocess.CompletedProcess([], 1, "", "still failing"),
            subprocess.CompletedProcess([], 1, "", "giving up"),
        ]
        with patch.object(acq.probe.subprocess, "run", side_effect=failures):
            with self.assertRaisesRegex(ValueError, "giving up"):
                acq.run_ffprobe_json("local.mp4", attempts=3,
                                     sleep=lambda _s: None)

    def test_missing_ffprobe_and_unusable_json_are_contract_errors(self) -> None:
        with patch.object(acq.probe.subprocess, "run",
                          side_effect=FileNotFoundError("ffprobe")):
            with self.assertRaisesRegex(ValueError, "not installed"):
                acq.run_ffprobe_json("local.mp4", attempts=1)
        with patch.object(
                acq.probe.subprocess, "run",
                return_value=subprocess.CompletedProcess([], 0, "not-json", "")):
            with self.assertRaisesRegex(ValueError, "unusable JSON"):
                acq.run_ffprobe_json("local.mp4", attempts=1)

    def test_remote_probe_validates_the_allowlist_before_running(self) -> None:
        with patch.object(acq.probe.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "not allowlisted"):
                acq.ffprobe_remote_json(
                    "https://evil.example/clip.mp4", allowed_hosts=ALLOWED_HOSTS)
        run.assert_not_called()


class StillMetricTests(unittest.TestCase):
    def test_metrics_on_a_solid_synthetic_buffer(self) -> None:
        metrics = acq.compute_still_metrics(
            rgb_buffer(64, 36, lambda _x, _y: (0, 0, 255)), width=64, height=36)
        self.assertEqual(metrics["meanRgb"], [0.0, 0.0, 1.0])
        self.assertAlmostEqual(metrics["meanDisplayLumaProxy"], 0.0722, places=4)
        self.assertEqual(metrics["meanSaturationProxy"], 1.0)
        self.assertEqual(metrics["dominantHueFamily"], "blue")
        self.assertEqual(metrics["edgeDensityProxy"], 0.0)
        self.assertEqual(len(metrics["lumaHistogram"]), 5)
        self.assertAlmostEqual(sum(metrics["lumaHistogram"]), 1.0, places=5)
        self.assertEqual(metrics["lumaHistogram"][0], 1.0)

    def test_histogram_and_edge_density_on_a_split_buffer(self) -> None:
        metrics = acq.compute_still_metrics(
            rgb_buffer(64, 36,
                       lambda _x, y: (0, 0, 0) if y < 18 else (255, 255, 255)),
            width=64, height=36)
        self.assertAlmostEqual(metrics["meanDisplayLumaProxy"], 0.5, places=4)
        self.assertEqual(metrics["dominantHueFamily"], "neutral")
        self.assertGreater(metrics["edgeDensityProxy"], 0.0)
        self.assertEqual(metrics["lumaHistogram"][0], 0.5)
        self.assertEqual(metrics["lumaHistogram"][4], 0.5)
        self.assertAlmostEqual(sum(metrics["lumaHistogram"]), 1.0, places=5)

    def test_hue_family_buckets(self) -> None:
        for mean_rgb, expected in (
            ([0.5, 0.5, 0.5], "neutral"),
            ([0.0, 0.0, 0.0], "neutral"),
            ([1.0, 0.0, 0.0], "red"),
            ([0.0, 1.0, 0.0], "green"),
            ([0.0, 0.0, 1.0], "blue"),
            ([1.0, 0.0, 1.0], "magenta"),
            ([1.0, 0.6, 0.0], "orange"),
        ):
            self.assertEqual(acq.dominant_hue_family(mean_rgb), expected)
        with self.assertRaises(ValueError):
            acq.dominant_hue_family([0.5, 0.5])

    def test_decoded_dimension_inference_uses_the_source_aspect(self) -> None:
        # 160x90 scaled RGB plane for a 16:9 source.
        self.assertEqual(
            acq.infer_decoded_dimensions(160 * 90 * 3, 1280, 720), (160, 90))
        with self.assertRaisesRegex(ValueError, "whole number"):
            acq.infer_decoded_dimensions(1001, 1280, 720)
        with self.assertRaises(ValueError):
            acq.infer_decoded_dimensions(0, 1280, 720)

    def test_still_image_format_prefers_the_codec_then_the_url_suffix(self) -> None:
        self.assertEqual(
            acq.still_image_format("https://media.example/a.bin", "mjpeg"),
            "jpg")
        self.assertEqual(
            acq.still_image_format("https://media.example/a.PNG", None), "png")
        self.assertEqual(
            acq.still_image_format("https://media.example/a", "png"), "png")
        self.assertEqual(
            acq.still_image_format("https://media.example/a", None), "unknown")


class EvidenceBuilderTests(unittest.TestCase):
    def test_video_evidence_is_neutral_and_keeps_the_field_shape(self) -> None:
        coverage = {
            "windowsMeasured": 1, "windowSeconds": 10, "sampledSeconds": 10,
            "fractionOfRuntime": 0.5, "fullRuntimeMeasured": False,
            "note": "evenly spread source-PTS windows, not full-film review",
        }
        payload = acq.build_video_evidence(
            source={"durationSeconds": 12.0, "resolution": [640, 360]},
            coverage=coverage,
            windows=[{"startSeconds": 0, "endSeconds": 10,
                      "probe": synthetic_probe(1, 0.5, 0.2, 2, [1.0])}],
            method=acq.METHOD_HTTP_DOWNLOAD, provider=acq.DIRECT,
            video_url="https://media.example/clip.mp4",
            rights_basis="user-declared-research-use",
            rights_note="deleted after measurement",
            schema_version="test.video-evidence.v1",
            evidence_status="numeric-not-reviewed",
            limits=["limit one", "limit two"],
            generated_at="2026-01-01T00:00:00Z")
        self.assertEqual(set(payload), {
            "schemaVersion", "source", "acquisition", "coverage", "windows",
            "summary", "evidenceStatus", "rightsStatus", "limits",
            "generatedAt",
        })
        self.assertNotIn("projectId", payload)
        self.assertNotIn("slug", payload)
        self.assertEqual(payload["acquisition"], {
            "provider": "direct",
            "videoUrl": "https://media.example/clip.mp4",
            "method": "http-download",
            "mediaRetained": False,
            "attestation": {
                "rightsBasis": "user-declared-research-use",
                "note": "deleted after measurement",
            },
        })
        self.assertEqual(payload["summary"]["cutCandidates"], 1)
        self.assertEqual(payload["summary"]["cutCandidateRatePerMinute"], 6.0)
        self.assertEqual(payload["limits"], ["limit one", "limit two"])
        self.assertEqual(payload["rightsStatus"], "review-required")
        self.assertEqual(payload["generatedAt"], "2026-01-01T00:00:00Z")

    def test_video_evidence_rejects_contract_violations(self) -> None:
        args = dict(
            source={}, coverage={"sampledSeconds": 10}, windows=[],
            method="http-download", provider="direct",
            video_url="https://media.example/clip.mp4",
            rights_basis="basis", rights_note="note",
            schema_version="test.v1", evidence_status="status", limits=[])
        for broken in (
            {"schema_version": ""}, {"evidence_status": ""}, {"method": ""},
            {"provider": ""}, {"rights_basis": ""}, {"rights_note": ""},
        ):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                acq.build_video_evidence(**{**args, **broken})
        with self.assertRaisesRegex(ValueError, "sampled seconds"):
            acq.build_video_evidence(**{**args, "coverage": {}})

    def test_still_evidence_is_neutral_and_never_retains_images(self) -> None:
        payload = acq.build_still_evidence(
            still={"imageUrl": "https://media.example/poster.png",
                   "imageSha256": "a" * 64},
            schema_version="test.still-evidence.v1",
            evidence_status="single-published-still",
            limits=["no motion evidence"],
            coverage_note="published poster still, not a video frame",
            generated_at="2026-01-01T00:00:00Z")
        self.assertEqual(set(payload), {
            "schemaVersion", "still", "acquisition", "coverage",
            "evidenceStatus", "limits", "generatedAt",
        })
        self.assertEqual(payload["acquisition"],
                         {"method": acq.STILL_METHOD, "imageRetained": False})
        self.assertFalse(payload["coverage"]["isSourceVideoFrame"])
        with self.assertRaises(ValueError):
            acq.build_still_evidence(
                still={}, schema_version="test.v1", evidence_status="s",
                limits=[], coverage_note="")


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_atomic_write_overwrites_without_staging_leftovers(self) -> None:
        target = self.root / "nested" / "index.json"
        acq.write_json_atomic(target, {"value": 1})
        acq.write_json_atomic(target, {"value": 2})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")),
                         {"value": 2})
        self.assertEqual(sorted(path.name for path in target.parent.iterdir()),
                         ["index.json"])

    def test_safe_slug_and_resume_matching(self) -> None:
        self.assertEqual(acq.safe_slug("Hello world!"), "Hello-world")
        self.assertEqual(acq.safe_slug("film-42"), "film-42")
        for value in ("", "..", ".", "a" * 130, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                acq.safe_slug(value)
        record = self.root / "records" / "film.json"
        acq.write_json_atomic(record, {"projectId": "42"})
        self.assertTrue(acq.resume_matches(record, "42", field="projectId"))
        self.assertFalse(acq.resume_matches(record, "43", field="projectId"))
        self.assertFalse(
            acq.resume_matches(self.root / "missing.json", "42",
                               field="projectId"))
        with self.assertRaises(ValueError):
            acq.resume_matches(record, "42", field="")

    def test_index_assembly_uses_the_caller_schema_and_counts(self) -> None:
        index = acq.build_index(
            schema_version="test.index.v1",
            records=[{"id": "1"}, {"id": "2"}],
            skips=[{"id": "3"}],
            failures=[{"id": "4"}],
            generated_at="2026-01-01T00:00:00Z",
            extra={"catalogSha256": "f" * 64})
        self.assertEqual(index["schemaVersion"], "test.index.v1")
        self.assertEqual(index["generatedAt"], "2026-01-01T00:00:00Z")
        self.assertEqual(index["catalogSha256"], "f" * 64)
        self.assertEqual(index["counts"],
                         {"measured": 2, "skipped": 1, "failed": 1})
        self.assertEqual(len(index["records"]), 2)
        with self.assertRaises(ValueError):
            acq.build_index(schema_version="", records=[], skips=[],
                            failures=[], generated_at="T")


class BatchRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.index_path = self.root / "index.json"

    def _build_index(self, records, skips, failures) -> dict:
        return acq.build_index(
            schema_version="test.index.v1", records=records, skips=skips,
            failures=failures, generated_at="2026-01-01T00:00:00Z")

    def test_sequential_batch_isolates_failures_and_skips_resumed_items(self) -> None:
        durations: list[float] = []
        progress: list[tuple] = []

        def run_one(item: str) -> dict:
            if item == "bad":
                raise ValueError(
                    "boom at https://secret.example/x "
                    "in /tmp/kumiki-acquire-77/media")
            return {"id": item}

        outcome = acq.run_batch(
            ["a", "bad", "skip-me", "b"],
            run_one=run_one,
            index_path=self.index_path,
            build_index=self._build_index,
            summary_row=lambda record: {"id": record["id"]},
            skip_row=lambda item, reason: {"id": item, "reason": reason},
            skip_reason=(lambda item: "resume-existing-record"
                         if item == "skip-me" else None),
            progress=lambda *args: progress.append(args),
            delay_seconds=0.25, jitter=lambda _base: 0.0,
            sleeper=durations.append, describe=str)
        self.assertEqual(
            (outcome.measured, outcome.skipped, outcome.failed,
             outcome.attempted),
            (2, 1, 1, 3))
        self.assertEqual(outcome.index_path, self.index_path)
        self.assertEqual(durations, [0.25, 0.25])
        self.assertEqual(len(progress), 3)
        index = json.loads(self.index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 2, "skipped": 1, "failed": 1})
        reason = index["failures"][0]["reason"]
        self.assertIn("[redacted-url]", reason)
        self.assertIn("[scratch]", reason)
        self.assertNotIn("secret.example", reason)
        self.assertNotIn("kumiki-acquire", reason)

    def test_pooled_batch_runs_every_item_and_keeps_the_index_current(self) -> None:
        def run_one(item: int) -> dict:
            if item == 3:
                raise ValueError("synthetic failure")
            return {"id": item}

        outcome = acq.run_batch(
            [1, 2, 3, 4],
            run_one=run_one,
            index_path=self.index_path,
            build_index=self._build_index,
            summary_row=lambda record: {"id": record["id"]},
            skip_row=lambda item, reason: {"id": item, "reason": reason},
            jobs=2)
        self.assertEqual(
            (outcome.measured, outcome.skipped, outcome.failed,
             outcome.attempted),
            (3, 0, 1, 4))
        index = json.loads(self.index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["counts"],
                         {"measured": 3, "skipped": 0, "failed": 1})
        self.assertEqual(sorted(row["id"] for row in index["records"]),
                         [1, 2, 4])

    def test_batch_budgets_are_validated(self) -> None:
        common = dict(
            run_one=lambda item: {"id": item},
            index_path=self.index_path,
            build_index=self._build_index,
            summary_row=lambda record: record,
            skip_row=lambda item, reason: {"id": item})
        for jobs, delay in ((0, 0.0), (1, -1.0)):
            with self.subTest(jobs=jobs, delay=delay), \
                    self.assertRaises(ValueError):
                acq.run_batch([1], jobs=jobs, delay_seconds=delay, **common)

    def test_safe_error_redacts_urls_paths_secrets_and_truncates(self) -> None:
        message = acq.safe_error(
            ValueError(
                "failed https://secret.example/a at /tmp/kumiki-acquire-9/x "
                "with /private/var/private-out " + "z" * 400),
            redact=["/private/var/private-out"])
        self.assertIn("[redacted-url]", message)
        self.assertIn("[scratch]", message)
        self.assertIn("[redacted]", message)
        self.assertNotIn("secret.example", message)
        self.assertNotIn("kumiki-acquire", message)
        self.assertLessEqual(len(message), 300)

    def test_safe_error_redacts_signed_query_material(self) -> None:
        message = acq.safe_error(ValueError(
            "GET failed: AWSAccessKeyId=AKIAEXAMPLE&Expires=1"
            "&Signature=abc%2Fdef and Signature=deadbeef&x=1"))
        self.assertNotIn("AKIAEXAMPLE", message)
        self.assertNotIn("abc%2Fdef", message)
        self.assertNotIn("deadbeef", message)
        self.assertIn("AWSAccessKeyId=[redacted]", message)
        self.assertIn("Signature=[redacted]", message)


class YtDlpUrlTests(unittest.TestCase):
    def test_accepts_the_four_single_video_shapes(self) -> None:
        for url in (
            "https://www.youtube.com/watch?v=ZfJOq_B_XBM",
            "https://youtube.com/watch?v=ZfJOq_B_XBM",
            "https://m.youtube.com/watch?v=ZfJOq_B_XBM",
            "https://www.youtube.com/shorts/ZfJOq_B_XBM",
            "https://www.youtube.com/embed/ZfJOq_B_XBM",
            "https://youtu.be/ZfJOq_B_XBM",
        ):
            with self.subTest(url=url):
                self.assertEqual(acq.allowlisted_youtube_url(url), url)

    def test_rejects_playlists_channels_live_and_host_tricks(self) -> None:
        for url in (
            "http://www.youtube.com/watch?v=ZfJOq_B_XBM",
            "https://www.youtube.com/playlist?list=PL123",
            "https://www.youtube.com/watch?v=ZfJOq_B_XBM&list=PL123",
            "https://www.youtube.com/watch?v=ZfJOq_B_XBM&t=10s",
            "https://www.youtube.com/watch?v=short",
            "https://www.youtube.com/watch?v=ZfJOq_B_XBM#frag",
            "https://www.youtube.com/channel/UC1234567890",
            "https://www.youtube.com/live/ZfJOq_B_XBM",
            "https://www.youtube.com/watch/",
            "https://www.youtube.com/shorts/ZfJOq_B_XBM/extra",
            "https://youtu.be/ZfJOq_B_XBM?t=1",
            "https://youtu.be/short",
            "https://evil.example/watch?v=ZfJOq_B_XBM",
            "https://youtube.com.evil.example/watch?v=ZfJOq_B_XBM",
            "https://user:pass@youtube.com/watch?v=ZfJOq_B_XBM",
            "https://www.youtube.com:8443/watch?v=ZfJOq_B_XBM",
            "",
            "   ",
            None,
            42,
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                acq.allowlisted_youtube_url(url)

    def test_honours_a_caller_supplied_host_allowlist(self) -> None:
        self.assertEqual(
            acq.allowlisted_youtube_url(
                "https://youtu.be/ZfJOq_B_XBM", allowed_hosts=("youtu.be",)),
            "https://youtu.be/ZfJOq_B_XBM")
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            acq.allowlisted_youtube_url(
                "https://www.youtube.com/watch?v=ZfJOq_B_XBM",
                allowed_hosts=("youtu.be",))


class YtDlpDownloadTests(unittest.TestCase):
    url = "https://www.youtube.com/watch?v=ZfJOq_B_XBM"
    forbidden_flags = (
        "--cookies", "--cookies-from-browser", "--username", "--password",
        "--netrc", "--netrc-file", "--browser", "--remote-components",
        "--config-location",
    )

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.destination = self.root / "media"
        self.destination.mkdir()

    def _clear(self) -> None:
        for entry in self.destination.iterdir():
            entry.unlink()

    def _run_download(self, fake_run, **kwargs):
        with patch.object(acq.ytdlp.subprocess, "run", side_effect=fake_run):
            return acq.download_via_ytdlp(
                self.url, self.destination, **kwargs)

    def test_emits_only_bounded_flags_and_no_cookie_or_login_state(self) -> None:
        captured: dict = {}

        def fake_run(args, **kwargs):  # noqa: ANN001 - test double
            captured["args"] = list(args)
            captured["kwargs"] = dict(kwargs)
            (Path(kwargs["cwd"]) / "source.mp4").write_bytes(b"x" * 64)
            return subprocess.CompletedProcess(args, 0, b"", b"")

        result = self._run_download(fake_run)
        self.assertEqual(result, self.destination / "source.mp4")
        args = captured["args"]
        self.assertEqual(args[0], "yt-dlp")
        self.assertEqual(args[-2:], ["--", self.url])
        for flag in (
            "--ignore-config", "--no-plugin-dirs", "--no-playlist",
            "--no-mtime", "--no-progress", "--no-continue", "--no-part",
            "--no-cache-dir", "--no-write-info-json", "--merge-output-format",
        ):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("--playlist-items") + 1], "1")
        self.assertEqual(args[args.index("--retries") + 1], "1")
        self.assertEqual(args[args.index("--fragment-retries") + 1], "1")
        self.assertEqual(args[args.index("--concurrent-fragments") + 1], "1")
        self.assertEqual(args[args.index("--socket-timeout") + 1], "15")
        self.assertEqual(args[args.index("--max-filesize") + 1], "250M")
        self.assertEqual(args[args.index("--paths") + 1],
                         str(self.destination.resolve()))
        self.assertEqual(args[args.index("--output") + 1], "source.%(ext)s")
        for flag in self.forbidden_flags:
            self.assertFalse(
                any(arg == flag or arg.startswith(flag + "=") for arg in args),
                f"{flag} must never be emitted")
        self.assertIs(captured["kwargs"]["stdout"], subprocess.DEVNULL)
        self.assertEqual(captured["kwargs"]["timeout"], 300.0)
        self.assertEqual(captured["kwargs"]["cwd"], self.destination)

    def test_format_selector_prefers_h264_and_respects_the_height_cap(self) -> None:
        selectors: list[str] = []

        def fake_run(args, **kwargs):  # noqa: ANN001 - test double
            selectors.append(args[args.index("--format") + 1])
            (Path(kwargs["cwd"]) / "source.mp4").write_bytes(b"x" * 8)
            return subprocess.CompletedProcess(args, 0, b"", b"")

        self._run_download(fake_run, max_height=480, prefer_h264=True)
        self._clear()
        self._run_download(fake_run, max_height=480, prefer_h264=False)
        self.assertIn("[height<=480][vcodec^=avc1]", selectors[0])
        self.assertIn("[acodec^=mp4a]", selectors[0])
        self.assertNotIn("avc1", selectors[1])
        self.assertIn("[height<=480]", selectors[1])

    def test_requires_an_empty_real_directory(self) -> None:
        def fake_run(args, **kwargs):  # noqa: ANN001 - test double
            raise AssertionError("no process may start")

        occupied = self.root / "occupied"
        occupied.mkdir()
        (occupied / "leftover.txt").write_text("x", encoding="utf-8")
        with patch.object(acq.ytdlp.subprocess, "run", side_effect=fake_run):
            with self.assertRaisesRegex(ValueError, "must be empty"):
                acq.download_via_ytdlp(self.url, occupied)
            with self.assertRaisesRegex(ValueError, "not a real directory"):
                acq.download_via_ytdlp(self.url, self.root / "missing")
        link = self.root / "linked"
        link.symlink_to(occupied, target_is_directory=True)
        with patch.object(acq.ytdlp.subprocess, "run", side_effect=fake_run):
            with self.assertRaisesRegex(ValueError, "not a real directory"):
                acq.download_via_ytdlp(self.url, link)

    def test_rejects_out_of_bounds_parameters_before_running(self) -> None:
        def fake_run(args, **kwargs):  # noqa: ANN001 - test double
            raise AssertionError("no process may start")

        for kwargs in (
            {"max_bytes": 0}, {"max_height": 0}, {"timeout_seconds": 5},
            {"prefer_h264": "yes"}, {"yt_dlp": ""},
            {"attempts": "2"}, {"attempts": True},
            {"backoff_seconds": -1}, {"backoff_seconds": 600},
            {"sleeper": None},
        ):
            with self.subTest(kwargs=kwargs), \
                    patch.object(acq.ytdlp.subprocess,
                                 "run", side_effect=fake_run), \
                    self.assertRaises(ValueError):
                acq.download_via_ytdlp(self.url, self.destination, **kwargs)

    def test_enforces_exactly_one_regular_known_suffix_file(self) -> None:
        def run_writing(*names: str, size: int = 8):
            def fake_run(args, **kwargs):  # noqa: ANN001 - test double
                for name in names:
                    (Path(kwargs["cwd"]) / name).write_bytes(b"x" * size)
                return subprocess.CompletedProcess(args, 0, b"", b"")

            return fake_run

        for fake_run in (
            run_writing(),
            run_writing("source.mp4", "source.webm"),
            run_writing("source.txt"),
            run_writing("source.mp4", size=0),
        ):
            self._clear()
            with self.subTest(fake_run=fake_run), \
                    patch.object(acq.ytdlp.subprocess,
                                 "run", side_effect=fake_run), \
                    self.assertRaises(acq.YtDlpError):
                acq.download_via_ytdlp(self.url, self.destination)

    def test_rejects_symlinked_and_oversized_results(self) -> None:
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"x" * 8)

        def symlink_run(args, **kwargs):  # noqa: ANN001 - test double
            (Path(kwargs["cwd"]) / "source.mp4").symlink_to(outside)
            return subprocess.CompletedProcess(args, 0, b"", b"")

        with patch.object(acq.ytdlp.subprocess, "run", side_effect=symlink_run):
            with self.assertRaisesRegex(acq.YtDlpError, "no regular"):
                acq.download_via_ytdlp(self.url, self.destination)
        self._clear()

        def oversize_run(args, **kwargs):  # noqa: ANN001 - test double
            (Path(kwargs["cwd"]) / "source.mp4").write_bytes(b"x" * 64)
            return subprocess.CompletedProcess(args, 0, b"", b"")

        with patch.object(acq.ytdlp.subprocess, "run", side_effect=oversize_run):
            with self.assertRaisesRegex(acq.YtDlpError, "size cap"):
                acq.download_via_ytdlp(
                    self.url, self.destination, max_bytes=32)

    def test_provider_refusal_is_distinct_and_never_leaks_stderr(self) -> None:
        stderr = (b"ERROR: [youtube] ZfJOq_B_XBM: HTTP Error 403: Forbidden; "
                  b"visit https://www.youtube.com/watch?v=ZfJOq_B_XBM")
        fake = subprocess.CompletedProcess([], 1, b"", stderr)
        with patch.object(acq.ytdlp.subprocess, "run",
                          return_value=fake) as run:
            with self.assertRaises(acq.YtDlpRefusedError) as raised:
                acq.download_via_ytdlp(self.url, self.destination, attempts=1)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(raised.exception.reason, "provider-refused")
        message = str(raised.exception)
        for leaked in ("403", "Forbidden", "youtube.com", "ERROR"):
            self.assertNotIn(leaked, message)

    def test_outdated_client_and_login_only_are_refusals(self) -> None:
        for stderr in (
            b"ERROR: Unsupported client 'web_safari'; please update yt-dlp",
            b"ERROR: Sign in to confirm you're not a bot",
            b"ERROR: This video is only available when logged-in",
            b"WARNING: nsig extraction failed",
        ):
            with self.subTest(stderr=stderr), \
                    patch.object(
                        acq.ytdlp.subprocess, "run",
                        return_value=subprocess.CompletedProcess(
                            [], 1, b"", stderr)), \
                    self.assertRaises(acq.YtDlpRefusedError):
                acq.download_via_ytdlp(self.url, self.destination)
        self.assertEqual(acq.classify_ytdlp_failure(b"connection reset"),
                         "transient")

    def test_plain_transient_failure_does_not_leak_stderr(self) -> None:
        stderr = b"ERROR: unable to connect to https://secret.example/x"
        with patch.object(
                acq.ytdlp.subprocess, "run",
                return_value=subprocess.CompletedProcess([], 1, b"", stderr)):
            with self.assertRaises(acq.YtDlpError) as raised:
                acq.download_via_ytdlp(self.url, self.destination)
        self.assertNotIsInstance(raised.exception, acq.YtDlpRefusedError)
        self.assertEqual(raised.exception.reason, "transient")
        self.assertNotIn("secret.example", str(raised.exception))

    def test_missing_executable_is_a_contract_error(self) -> None:
        with patch.object(acq.ytdlp.subprocess, "run",
                          side_effect=FileNotFoundError("yt-dlp")):
            with self.assertRaisesRegex(acq.YtDlpError, "not installed"):
                acq.download_via_ytdlp(self.url, self.destination)

    forbidden_stderr = (
        b"ERROR: [youtube] ZfJOq_B_XBM: unable to download video data: "
        b"HTTP Error 403: Forbidden")

    def test_retries_the_403_class_once_then_succeeds(self) -> None:
        calls: list[int] = []
        sleeps: list[float] = []
        seen: list[list[str]] = []

        def fake_run(args, **kwargs):  # noqa: ANN001 - test double
            calls.append(1)
            if len(calls) == 1:
                (Path(kwargs["cwd"]) / "source.mp4").write_bytes(b"x" * 16)
                return subprocess.CompletedProcess(
                    args, 1, b"", self.forbidden_stderr)
            seen.append(sorted(entry.name
                               for entry in Path(kwargs["cwd"]).iterdir()))
            (Path(kwargs["cwd"]) / "source.mp4").write_bytes(b"y" * 64)
            return subprocess.CompletedProcess(args, 0, b"", b"")

        result = self._run_download(fake_run, sleeper=sleeps.append)
        self.assertEqual(result, self.destination / "source.mp4")
        self.assertEqual(result.stat().st_size, 64)
        self.assertEqual(len(calls), 2)
        # The partial from the refused attempt is gone before the retry runs.
        self.assertEqual(seen, [[]])
        self.assertEqual(len(sleeps), 1)
        # backoff (6.0) plus equal jitter, so [6.0, 12.0].
        self.assertGreaterEqual(sleeps[0], 6.0)
        self.assertLessEqual(sleeps[0], 12.0)

    def test_two_403_attempts_still_raise_a_provider_refusal(self) -> None:
        sleeps: list[float] = []
        fake = subprocess.CompletedProcess([], 1, b"", self.forbidden_stderr)
        with patch.object(acq.ytdlp.subprocess, "run",
                          return_value=fake) as run:
            with self.assertRaises(acq.YtDlpRefusedError) as raised:
                acq.download_via_ytdlp(
                    self.url, self.destination,
                    backoff_seconds=0.25, sleeper=sleeps.append)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(raised.exception.reason, "provider-refused")
        self.assertEqual(len(sleeps), 1)
        self.assertGreaterEqual(sleeps[0], 0.25)
        self.assertLessEqual(sleeps[0], 0.5)

    def test_hard_refusal_markers_are_never_retried(self) -> None:
        for stderr in (
            b"ERROR: Sign in to confirm you're not a bot",
            b"ERROR: Sign in to confirm you're not a bot; HTTP Error 403",
            b"ERROR: Private video. Sign in if you've been granted access",
            b"ERROR: This video is members-only",
            b"ERROR: Unsupported client 'web_safari'; please update yt-dlp",
        ):
            sleeps: list[float] = []
            with self.subTest(stderr=stderr), \
                    patch.object(
                        acq.ytdlp.subprocess, "run",
                        return_value=subprocess.CompletedProcess(
                            [], 1, b"", stderr)) as run, \
                    self.assertRaises(acq.YtDlpRefusedError):
                acq.download_via_ytdlp(
                    self.url, self.destination, sleeper=sleeps.append)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(sleeps, [])

    def test_attempts_one_disables_the_retry(self) -> None:
        sleeps: list[float] = []
        fake = subprocess.CompletedProcess([], 1, b"", self.forbidden_stderr)
        with patch.object(acq.ytdlp.subprocess, "run",
                          return_value=fake) as run:
            with self.assertRaises(acq.YtDlpRefusedError):
                acq.download_via_ytdlp(
                    self.url, self.destination, attempts=1,
                    sleeper=sleeps.append)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(sleeps, [])

    def test_attempts_are_bounded_and_clamped(self) -> None:
        sleeps: list[float] = []
        fake = subprocess.CompletedProcess([], 1, b"", self.forbidden_stderr)
        with patch.object(acq.ytdlp.subprocess, "run",
                          return_value=fake) as run:
            with self.assertRaises(acq.YtDlpRefusedError):
                acq.download_via_ytdlp(
                    self.url, self.destination, attempts=0,
                    backoff_seconds=0.0, sleeper=sleeps.append)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(sleeps, [])

        sleeps.clear()
        with patch.object(acq.ytdlp.subprocess, "run",
                          return_value=fake) as run:
            with self.assertRaises(acq.YtDlpRefusedError):
                acq.download_via_ytdlp(
                    self.url, self.destination, attempts=99,
                    backoff_seconds=0.0, sleeper=sleeps.append)
        self.assertEqual(run.call_count, acq.ytdlp._MAX_ATTEMPTS)
        self.assertEqual(len(sleeps), acq.ytdlp._MAX_ATTEMPTS - 1)
        for seconds in sleeps:
            self.assertEqual(seconds, 0.0)

    def test_retryable_refusal_is_split_from_hard_refusal(self) -> None:
        for stderr in (
            b"ERROR: HTTP Error 403: Forbidden",
            b"ERROR: [youtube] x: unable to download video data: HTTP Error 403",
            b"ERROR: got error 403 from the CDN",
        ):
            with self.subTest(stderr=stderr):
                self.assertTrue(acq.is_retryable_refusal(stderr))
                self.assertEqual(acq.classify_ytdlp_failure(stderr),
                                 "provider-refused")
        for stderr in (
            b"ERROR: Sign in to confirm you're not a bot",
            b"ERROR: Private video",
            b"ERROR: This video is members-only",
            b"ERROR: unable to connect to the host",
            b"ERROR: Sign in to confirm you're not a bot; HTTP Error 403",
        ):
            with self.subTest(stderr=stderr):
                self.assertFalse(acq.is_retryable_refusal(stderr))
        self.assertEqual(acq.classify_ytdlp_failure(b"connection reset"),
                         "transient")


class YtDlpMetadataTests(unittest.TestCase):
    url = "https://www.youtube.com/watch?v=ZfJOq_B_XBM"

    def _metadata(self, payload, *, returncode: int = 0,
                  stderr: bytes = b"") -> dict:
        body = payload if isinstance(payload, bytes) else json.dumps(
            payload).encode("utf-8")
        fake = subprocess.CompletedProcess([], returncode, body, stderr)
        with patch.object(acq.ytdlp.subprocess, "run", return_value=fake):
            return acq.youtube_source_metadata(
                self.url, yt_dlp="/opt/yt-dlp")

    def test_reduces_the_info_json_to_the_neutral_shape(self) -> None:
        metadata = self._metadata({
            "duration": 42.5, "width": 1280, "height": 720, "fps": 29.97,
            "vcodec": "avc1.64001F", "tbr": 1200.0, "filesize": 1_234_567,
            "title": "Demo clip", "format_id": "137",
        })
        self.assertEqual(metadata["durationSeconds"], 42.5)
        self.assertEqual((metadata["width"], metadata["height"]), (1280, 720))
        self.assertEqual(metadata["fps"], 29.97)
        self.assertEqual(metadata["codec"], "avc1.64001F")
        self.assertEqual(metadata["bitRate"], 1_200_000.0)
        self.assertEqual(metadata["sizeBytes"], 1_234_567)
        self.assertEqual(metadata["estimatedBytes"], 6_375_000.0)
        self.assertEqual(metadata["title"], "Demo clip")
        self.assertEqual(metadata["formatId"], "137")

    def test_missing_fields_stay_none_instead_of_being_invented(self) -> None:
        metadata = self._metadata({"duration": 10})
        self.assertEqual(metadata["durationSeconds"], 10.0)
        for field in ("width", "height", "fps", "codec", "bitRate",
                      "sizeBytes", "estimatedBytes", "title", "formatId"):
            self.assertIsNone(metadata[field], field)
        estimated = self._metadata({"duration": 10, "vbr": 800})
        self.assertEqual(estimated["bitRate"], 800_000.0)
        self.assertEqual(estimated["estimatedBytes"], 1_000_000.0)
        self.assertEqual(estimated["sizeBytes"], 1_000_000.0)

    def test_uses_dump_single_json_without_media_or_login_state(self) -> None:
        captured: dict = {}

        def fake_run(args, **kwargs):  # noqa: ANN001 - test double
            captured["args"] = list(args)
            return subprocess.CompletedProcess(args, 0, b"{}", b"")

        with patch.object(acq.ytdlp.subprocess, "run", side_effect=fake_run):
            acq.youtube_source_metadata(self.url, yt_dlp="/opt/yt-dlp")
        args = captured["args"]
        self.assertEqual(args[0], "/opt/yt-dlp")
        self.assertIn("--dump-single-json", args)
        self.assertIn("--skip-download", args)
        self.assertIn("--no-warnings", args)
        self.assertEqual(args[-2:], ["--", self.url])
        for flag in ("--cookies", "--cookies-from-browser", "--username",
                     "--password", "--netrc", "--browser",
                     "--remote-components"):
            self.assertNotIn(flag, args)

    def test_metadata_failures_are_classified_and_never_echo_stderr(self) -> None:
        with self.assertRaises(acq.YtDlpRefusedError):
            self._metadata(b"", returncode=1,
                           stderr=b"ERROR: HTTP Error 403: Forbidden")
        with self.assertRaisesRegex(acq.YtDlpError, "unusable metadata"):
            self._metadata(b"not-json")

    def test_validates_the_url_before_starting_a_process(self) -> None:
        with patch.object(acq.ytdlp.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "single-video"):
                acq.youtube_source_metadata(
                    "https://www.youtube.com/playlist?list=PL123")
        run.assert_not_called()


class YoutubeDownloadMediaTests(unittest.TestCase):
    url = "https://www.youtube.com/watch?v=ZfJOq_B_XBM"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_dispatches_youtube_to_the_bounded_ytdlp_path(self) -> None:
        target = self.directory / "source.mp4"
        with patch.object(acq.ytdlp, "youtube_source_metadata",
                          return_value={"durationSeconds": 30.0}) as metadata, \
                patch.object(acq.ytdlp, "download_via_ytdlp",
                             return_value=target) as download:
            path, method = acq.download_media(
                self.url, acq.YOUTUBE, self.directory,
                allowed_hosts=("*",), max_bytes=4096,
                max_duration_seconds=60.0)
        self.assertEqual((path, method), (target, acq.METHOD_YTDLP_MERGE))
        metadata.assert_called_once()
        download.assert_called_once()
        self.assertEqual(download.call_args.args[0], self.url)
        self.assertEqual(download.call_args.args[1], self.directory)

    def test_pre_rejects_over_long_videos_before_downloading(self) -> None:
        with patch.object(acq.ytdlp, "youtube_source_metadata",
                          return_value={"durationSeconds": 1000.0}), \
                patch.object(acq.ytdlp, "download_via_ytdlp") as download:
            with self.assertRaisesRegex(ValueError, "duration budget"):
                acq.download_media(
                    self.url, acq.YOUTUBE, self.directory,
                    allowed_hosts=("*",), max_bytes=4096,
                    max_duration_seconds=60.0)
        download.assert_not_called()

    def test_unavailable_metadata_does_not_block_the_download(self) -> None:
        target = self.directory / "source.mp4"
        messages: list[str] = []
        with patch.object(acq.ytdlp, "youtube_source_metadata",
                          side_effect=ValueError("metadata pre-check failed")), \
                patch.object(acq.ytdlp, "download_via_ytdlp",
                             return_value=target):
            path, method = acq.download_media(
                self.url, acq.YOUTUBE, self.directory,
                allowed_hosts=("*",), max_bytes=4096,
                log=messages.append)
        self.assertEqual((path, method), (target, acq.METHOD_YTDLP_MERGE))
        self.assertTrue(messages)

    def test_playlist_urls_are_refused_before_any_download(self) -> None:
        with patch.object(acq.ytdlp, "download_via_ytdlp") as download:
            with self.assertRaisesRegex(ValueError, "single-video"):
                acq.download_media(
                    "https://www.youtube.com/playlist?list=PL123",
                    acq.YOUTUBE, self.directory,
                    allowed_hosts=("*",), max_bytes=4096)
        download.assert_not_called()

    def test_threads_the_bounded_retry_policy_into_the_ytdlp_path(self) -> None:
        target = self.directory / "source.mp4"
        sleeper = lambda _seconds: None  # noqa: E731 - test double

        with patch.object(acq.ytdlp, "youtube_source_metadata",
                          return_value={}), \
                patch.object(acq.ytdlp, "download_via_ytdlp",
                             return_value=target) as download:
            acq.download_media(
                self.url, acq.YOUTUBE, self.directory,
                allowed_hosts=("*",), max_bytes=4096,
                attempts=3, backoff_seconds=1.5, sleeper=sleeper)
        kwargs = download.call_args.kwargs
        self.assertEqual(kwargs["attempts"], 3)
        self.assertEqual(kwargs["backoff_seconds"], 1.5)
        self.assertIs(kwargs["sleeper"], sleeper)

    def test_direct_downloads_ignore_the_retry_policy(self) -> None:
        target = self.directory / "source.mp4"

        def never_sleeps(_seconds):  # noqa: ANN001 - test double
            raise AssertionError("direct downloads must not sleep")

        with patch.object(acq.probe, "remote_source_metadata",
                          return_value={"durationSeconds": 5.0,
                                        "estimatedBytes": None}), \
                patch.object(acq.media, "download_http",
                             return_value=target):
            path, method = acq.download_media(
                "https://media.example/clip.mp4", acq.DIRECT, self.directory,
                allowed_hosts=ALLOWED_HOSTS, max_bytes=4096,
                attempts=3, backoff_seconds=0.5, sleeper=never_sleeps)
        self.assertEqual((path, method), (target, acq.METHOD_HTTP_DOWNLOAD))

    def test_safe_error_redacts_url_signature_material(self) -> None:
        message = acq.safe_error(ValueError(
            "googlevideo failed: expire=1700000000&ip=203.0.113.9"
            "&sig=abcd&ei=xyz"))
        for leaked in ("1700000000", "203.0.113.9", "abcd", "xyz"):
            self.assertNotIn(leaked, message)


if __name__ == "__main__":
    unittest.main()
