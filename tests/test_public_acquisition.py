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


if __name__ == "__main__":
    unittest.main()
