"""Offline tests for the Motionographer adapter: no network, no ffmpeg, no media."""

from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import research_motionographer as mg

S35726_MP4 = "https://s35726.pcdn.co/wp-content/uploads/2026/11/dreamcat-01.mp4"
HOSTS = ("s35726.pcdn.co",)


def _post(post_id: int, content: str, slug: str | None = None) -> dict:
    return {"id": post_id, "slug": slug or f"post-{post_id}",
            "link": f"https://motionographer.com/post-{post_id}/",
            "date": "2026-11-10T08:00:00", "title": {"rendered": f"Post {post_id}"},
            "content": {"rendered": content}}


def _response(status: int, payload: object = None, headers: dict | None = None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else b""
    return status, {k.lower(): v for k, v in (headers or {}).items()}, body


class ClassifyMediaTests(unittest.TestCase):
    def test_vimeo_and_youtube_embeds_are_unsupported_and_never_eligible(self):
        html = (
            '<iframe src="https://player.vimeo.com/video/123456?h=abc" width="640"></iframe>'
            '<iframe src="https://www.youtube.com/embed/AbCdEf12345"></iframe>')
        items = mg.classify_media(html, video_hosts=HOSTS)
        by_provider = {item["provider"]: item for item in items}
        self.assertEqual(by_provider["vimeo"]["reason"], "unsupported-vimeo")
        self.assertEqual(by_provider["youtube"]["reason"], "unsupported-youtube")
        self.assertFalse(any(item["eligible"] for item in items))
        self.assertEqual(by_provider["vimeo"]["mediaSlug"], "vimeo-123456")

    def test_direct_mp4_on_exact_allowlisted_host_is_eligible(self):
        html = f'<video><source src="{S35726_MP4}" type="video/mp4"></video>'
        items = mg.classify_media(html, video_hosts=HOSTS)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["eligible"])
        self.assertEqual(items[0]["provider"], mg.SELF_HOSTED_PROVIDER)
        self.assertEqual(items[0]["mediaSlug"], "dreamcat-01")

    def test_mp4_on_unlisted_host_is_not_eligible(self):
        html = '<source src="https://sibling.pcdn.co/wp-content/uploads/x.mp4">'
        item = mg.classify_media(html, video_hosts=HOSTS)[0]
        self.assertFalse(item["eligible"])
        self.assertEqual(item["reason"], "unsupported-host-not-allowlisted")

    def test_wildcard_lookalike_host_is_not_eligible(self):
        html = '<source src="https://s35726.pcdn.co.evil.example/wp-content/uploads/x.mp4">'
        item = mg.classify_media(html, video_hosts=HOSTS)[0]
        self.assertFalse(item["eligible"])

    def test_query_string_and_non_mp4_are_recorded_not_eligible(self):
        html = (f'<source src="{S35726_MP4}?ver=2">'
                '<source src="https://s35726.pcdn.co/wp-content/uploads/x.webm">')
        items = mg.classify_media(html, video_hosts=HOSTS)
        reasons = sorted(item["reason"] for item in items)
        self.assertEqual(reasons, ["unsupported-format", "unsupported-query-string"])

    def test_repeated_urls_dedupe_and_duplicate_slugs_are_suffixed(self):
        other = S35726_MP4.replace("dreamcat-01", "dreamcat-01-alt").replace("/2026/11/", "/2026/10/")
        html = f'<a href="{S35726_MP4}">a</a><a href="{S35726_MP4}">b</a><a href="{other}">c</a>'
        items = mg.classify_media(html, video_hosts=HOSTS)
        self.assertEqual(len(items), 2)
        self.assertEqual(len({item["mediaSlug"] for item in items}), 2)

    def test_plain_text_vimeo_link_is_not_treated_as_embed(self):
        html = '<p>See <a href="https://vimeo.com/98765">the cut</a>.</p>'
        self.assertEqual(mg.classify_media(html, video_hosts=HOSTS), [])

    def test_unknown_iframe_is_recorded_as_other_embed(self):
        html = '<iframe src="https://embed.example.org/player/9"></iframe>'
        item = mg.classify_media(html, video_hosts=HOSTS)[0]
        self.assertEqual(item["provider"], "other-embed")
        self.assertFalse(item["eligible"])

    def test_html_entities_in_urls_are_unescaped(self):
        html = f'<a href="{S35726_MP4.replace("dreamcat-01", "dreamcat-01&amp;x")}">v</a>'
        item = mg.classify_media(html, video_hosts=HOSTS)[0]
        self.assertIn("&", item["url"])
        self.assertNotIn("&amp;", item["url"])


class ConfirmationTests(unittest.TestCase):
    REST_URL = "https://motionographer.com/wp-content/uploads/2026/11/dreamcat-making-of.mp4"
    PAGE_URL = "https://s35726.pcdn.co/wp-content/uploads/2026/11/dreamcat-making-of.mp4"

    def test_cache_buster_is_stripped_and_only_that_query_form(self):
        item = mg.classify_media(
            f'<source src="{self.REST_URL}?_=4">', video_hosts=HOSTS)[0]
        self.assertTrue(item["cacheBusterStripped"])
        self.assertEqual(item["url"], self.REST_URL)
        self.assertEqual(item["reason"], "unsupported-host-not-allowlisted")
        other = mg.classify_media(f'<source src="{self.REST_URL}?ver=4">', video_hosts=HOSTS)[0]
        self.assertEqual(other["reason"], "unsupported-query-string")
        self.assertFalse(other["cacheBusterStripped"])

    def test_page_served_cdn_url_replaces_rest_origin_url(self):
        html = f'<video><source src="{self.REST_URL}"></video>'
        post = mg._post_row(_post(7, html, slug="dreamcat"), video_hosts=HOSTS)
        page = f'<html><video><source src="{self.PAGE_URL}"></video></html>'.encode()
        stats = mg.confirm_rendered_media(
            [post], video_hosts=HOSTS, get=lambda url: (200, {}, page),
            sleep=lambda s: None, log=lambda m: None)
        item = post["media"][0]
        self.assertTrue(item["pageConfirmed"])
        self.assertEqual(item["restUrl"], self.REST_URL)
        self.assertEqual(item["url"], self.PAGE_URL)
        self.assertTrue(item["eligible"])
        self.assertEqual(stats["itemsConfirmed"], 1)

    def test_page_that_is_not_found_keeps_rest_classification(self):
        html = f'<video><source src="{self.REST_URL}"></video>'
        post = mg._post_row(_post(7, html, slug="dreamcat"), video_hosts=HOSTS)
        stats = mg.confirm_rendered_media(
            [post], video_hosts=HOSTS, get=lambda url: (404, {}, b""),
            sleep=lambda s: None, log=lambda m: None)
        self.assertEqual(stats["pagesUnavailable"], 1)
        self.assertFalse(post["media"][0]["pageConfirmed"])
        self.assertEqual(post["pageConfirmation"]["status"], "page-unavailable")

    def test_rest_only_mp4_on_allowlisted_host_is_demoted_when_page_does_not_serve_it(self):
        html = f'<video><source src="{self.PAGE_URL}"></video>'
        post = mg._post_row(_post(7, html, slug="dreamcat"), video_hosts=HOSTS)
        self.assertTrue(post["media"][0]["eligible"])
        mg.confirm_rendered_media(
            [post], video_hosts=HOSTS,
            get=lambda url: (200, {}, b"<html>no video here</html>"),
            sleep=lambda s: None, log=lambda m: None)
        self.assertFalse(post["media"][0]["eligible"])
        self.assertEqual(post["media"][0]["reason"], "unsupported-not-served-on-page")

    def test_finalize_dedupes_canonical_duplicates_and_renumbers(self):
        raw = f'<source src="{self.REST_URL}?_=4"><source src="{self.REST_URL}?_=9">'
        post = mg._post_row(_post(7, raw, slug="dreamcat"), video_hosts=HOSTS)
        self.assertEqual(len(post["media"]), 2)
        mg.finalize_media(post)
        self.assertEqual([m["mediaId"] for m in post["media"]], ["7-1"])
        self.assertEqual(post["media"][0]["mediaSlug"], "dreamcat-making-of")

    def test_posts_without_mp4_candidates_are_never_fetched(self):
        post = mg._post_row(_post(8, '<iframe src="https://player.vimeo.com/video/5"></iframe>'),
                            video_hosts=HOSTS)
        calls: list[str] = []
        stats = mg.confirm_rendered_media(
            [post], video_hosts=HOSTS, get=lambda url: calls.append(url) or (200, {}, b""),
            sleep=lambda s: None, log=lambda m: None)
        self.assertEqual(calls, [])
        self.assertEqual(stats["postsChecked"], 0)


class FetchAndBackoffTests(unittest.TestCase):
    def test_retry_after_is_honoured_then_page_succeeds(self):
        sleeps: list[float] = []
        responses = [
            _response(429, headers={"Retry-After": "7"}),
            _response(200, [_post(1, "<p>text</p>")],
                      headers={"X-WP-TotalPages": "1", "X-WP-Total": "1"}),
        ]
        headers, body = mg.get_with_backoff(
            "u", get=lambda url: responses.pop(0), sleep=sleeps.append,
            log=lambda message: None)
        self.assertEqual(sleeps, [7.0])
        self.assertEqual(headers["x-wp-total"], "1")
        self.assertEqual(json.loads(body)[0]["id"], 1)

    def test_repeated_throttling_stops_without_further_requests(self):
        calls: list[str] = []

        def always_429(url: str):
            calls.append(url)
            return _response(429, headers={"Retry-After": "1"})

        with self.assertRaisesRegex(RuntimeError, "repeated HTTP 429/5xx"):
            mg.get_with_backoff("u", get=always_429, sleep=lambda s: None,
                                log=lambda m: None, attempts=3)
        self.assertEqual(len(calls), 3)

    def test_long_retry_after_stops_immediately(self):
        with self.assertRaisesRegex(RuntimeError, "not retrying"):
            mg.get_with_backoff(
                "u", get=lambda url: _response(429, headers={"Retry-After": "86400"}),
                sleep=lambda s: None, log=lambda m: None)

    def test_client_error_is_not_retried(self):
        with self.assertRaisesRegex(ValueError, "HTTP 400"):
            mg.get_with_backoff("u", get=lambda url: _response(400),
                                sleep=lambda s: None, log=lambda m: None)

    def test_fetch_posts_walks_pages_sequentially_with_polite_delay(self):
        pages = {
            1: [_post(10, "<p>one</p>")],
            2: [_post(9, f'<source src="{S35726_MP4}">')],
        }
        seen: list[str] = []
        sleeps: list[float] = []

        def fake_get(url: str):
            page = int(re.search(r"[?&]page=(\d+)", url).group(1))
            seen.append(url)
            return _response(200, pages[page], headers={
                "X-WP-TotalPages": "2", "X-WP-Total": "3"})

        rows, facts = mg.fetch_posts(get=fake_get, sleep=sleeps.append,
                                     video_hosts=HOSTS, log=lambda m: None)
        self.assertEqual([row["postId"] for row in rows], [10, 9])
        self.assertEqual(facts["totalPages"], 2)
        self.assertEqual(len(seen), 2)
        self.assertEqual(len(sleeps), 1)
        self.assertGreaterEqual(sleeps[0], mg.DELAY_SECONDS)
        self.assertLessEqual(sleeps[0], 2 * mg.DELAY_SECONDS)

    def test_limit_pages_caps_a_trial_run(self):
        def fake_get(url: str):
            return _response(200, [_post(1, "")], headers={
                "X-WP-TotalPages": "91", "X-WP-Total": "9016"})

        rows, facts = mg.fetch_posts(get=fake_get, sleep=lambda s: None,
                                     limit_pages=1, log=lambda m: None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(facts["pagesFetched"], 1)


class CatalogAndIndexTests(unittest.TestCase):
    def _catalog(self):
        posts = [
            {"postId": 1, "postSlug": "a", "title": "A", "date": "d", "link": "l",
                 "media": [
                     {"mediaId": "1-1", "mediaSlug": "v", "provider": mg.SELF_HOSTED_PROVIDER,
                      "eligible": True, "reason": "eligible-site-mp4", "url": S35726_MP4,
                      "host": "s35726.pcdn.co", "path": "/x.mp4"},
                     {"mediaId": "1-2", "mediaSlug": "vimeo-1", "provider": "vimeo",
                      "eligible": False, "reason": "unsupported-vimeo", "url": "u",
                      "host": "player.vimeo.com", "path": "/video/1"}]},
            {"postId": 2, "postSlug": "b", "title": "B", "date": "d", "link": "l2", "media": []},
        ]
        return mg.build_catalog(posts, facts={"totalPosts": 2, "totalPages": 1,
                                              "pagesFetched": 1}, video_hosts=HOSTS,
                                retrieved_at="2026-11-11T00:00:00Z")

    def test_catalog_counts_providers_and_eligibility(self):
        catalog = self._catalog()
        self.assertEqual(catalog["mediaItems"], 2)
        self.assertEqual(catalog["eligibleMediaItems"], 1)
        self.assertEqual(catalog["postsWithoutMedia"], 1)
        self.assertEqual(catalog["providerCounts"],
                         {"self-hosted-mp4": 1, "vimeo": 1})
        self.assertEqual(catalog["videoHosts"], ["s35726.pcdn.co"])

    def test_index_has_one_row_per_media_item_and_no_video_rows(self):
        index = mg.build_index(self._catalog(), catalog_sha="abc")
        statuses = [row["status"] for row in index["rows"]]
        self.assertEqual(sorted(statuses), ["no-video", "pending", "unsupported-vimeo"])
        self.assertEqual(index["counts"], {"no-video": 1, "pending": 1, "unsupported-vimeo": 1})
        self.assertEqual(index["providerCounts"], {"self-hosted-mp4": 1, "vimeo": 1})

    def test_index_marks_measured_and_failed_rows(self):
        catalog = self._catalog()
        measured = {"1-1": {"mediaId": "1-1", "sourceSha256": "f" * 64, "durationSeconds": 3.0}}
        index = mg.build_index(catalog, catalog_sha="abc", measured=measured)
        row = next(row for row in index["rows"] if row["mediaId"] == "1-1")
        self.assertEqual(row["status"], "measured")
        self.assertEqual(row["sourceSha256"], "f" * 64)
        failed = mg.build_index(catalog, catalog_sha="abc", failed={"1-1": "HTTP 503"})
        row = next(row for row in failed["rows"] if row["mediaId"] == "1-1")
        self.assertEqual((row["status"], row["reason"]), ("failed", "HTTP 503"))

    def test_eligible_items_only_and_limit(self):
        catalog = self._catalog()
        items = mg.eligible_items(catalog)
        self.assertEqual([item["mediaId"] for item in items], ["1-1"])
        self.assertEqual(mg.eligible_items(catalog, limit=0), [])
        with self.assertRaises(ValueError):
            mg.eligible_items(catalog, limit=-1)


class MeasureTests(unittest.TestCase):
    def _item(self):
        return {"mediaId": "1-1", "mediaSlug": "dreamcat-01", "postId": 1, "postSlug": "a",
                "title": "A", "date": "d", "link": "l", "url": S35726_MP4,
                "provider": mg.SELF_HOSTED_PROVIDER, "eligible": True,
                "reason": "eligible-site-mp4"}

    def test_rights_attestation_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "catalog.json"
            catalog.write_text(json.dumps({"schemaVersion": mg.CATALOG_SCHEMA, "posts": []}))
            with self.assertRaisesRegex(ValueError, "acknowledge-rights"):
                mg.run_measure(catalog, out_dir=Path(tmp), acknowledge_rights=False)

    def test_collect_one_writes_numeric_record_and_retains_no_media(self):
        seen_paths: list[Path] = []

        def fake_download(url, provider, directory, **kwargs):
            target = Path(directory) / "source.mp4"
            target.write_bytes(b"\x00" * 16)
            seen_paths.append(target)
            return target, "http-download"

        source = {"durationSeconds": 12.0, "resolution": [640, 360], "sizeBytes": 16,
                  "mediaSha256": "a" * 64}
        coverage = {"windowsMeasured": 1, "windowSeconds": 10, "sampledSeconds": 10.0,
                    "fractionOfRuntime": 0.8, "fullRuntimeMeasured": False, "note": "n"}
        window = {"startSeconds": 0.0, "endSeconds": 10.0, "probe": {
            "sampledWindowSummary": {"cutCandidateCountBetweenFirstAndLastSample": 1,
                                     "meanSampledDisplayLumaProxy": 0.5,
                                     "meanSampledSaturationProxy": 0.2,
                                     "cutSeparatedPairs": 0},
            "sampledFrames": [{"t": 0.0}, {"t": 1.0}]}}
        out_dir = Path(tempfile.mkdtemp(prefix="mg-test-out-"))
        self.addCleanup(shutil.rmtree, out_dir, True)
        with mock.patch.object(mg, "download_media", side_effect=fake_download), \
                mock.patch.object(mg, "source_metadata", return_value=source), \
                mock.patch.object(mg, "measure_windows", return_value=(coverage, [window])):
            record = mg.collect_one(self._item(), out_dir, windows=1, window_seconds=10)
        self.assertFalse(seen_paths[0].exists())
        self.assertEqual(record["acquisition"]["mediaRetained"], False)
        self.assertEqual(record["acquisition"]["provider"], mg.SELF_HOSTED_PROVIDER)
        self.assertEqual(record["rightsStatus"], "review-required")
        self.assertEqual(record["acquisition"]["attestation"]["rightsBasis"],
                         "user-declared-research-use")
        self.assertEqual(record["mediaId"], "1-1")
        self.assertTrue(mg._resume_path(out_dir, self._item()).is_file())
        self.assertFalse(any(out_dir.rglob("*.mp4")))

    def test_media_is_deleted_even_when_measurement_fails(self):
        seen_paths: list[Path] = []

        def fake_download(url, provider, directory, **kwargs):
            target = Path(directory) / "source.mp4"
            target.write_bytes(b"\x00" * 16)
            seen_paths.append(target)
            return target, "http-download"

        out_dir = Path(tempfile.mkdtemp(prefix="mg-test-out-"))
        self.addCleanup(shutil.rmtree, out_dir, True)
        with mock.patch.object(mg, "download_media", side_effect=fake_download), \
                mock.patch.object(mg, "source_metadata", side_effect=ValueError("probe failed")):
            with self.assertRaises(ValueError):
                mg.collect_one(self._item(), out_dir, windows=1, window_seconds=10)
        self.assertFalse(seen_paths[0].exists())

    def test_previous_failure_is_not_retried_unless_requested(self):
        out_dir = Path(tempfile.mkdtemp(prefix="mg-test-out-"))
        self.addCleanup(shutil.rmtree, out_dir, True)
        catalog_path = out_dir / "catalog.json"
        post = {"postId": 1, "postSlug": "a", "title": "A", "date": "d", "link": "l",
                "media": [self._item()]}
        catalog = {"schemaVersion": mg.CATALOG_SCHEMA, "posts": [post]}
        catalog_path.write_text(json.dumps(catalog))
        attempts: list[str] = []

        def failing(item, out, **kwargs):
            attempts.append(item["mediaId"])
            raise ValueError("HTTP Error 503")

        with mock.patch.object(mg, "collect_one", side_effect=failing):
            mg.run_measure(catalog_path, out_dir=out_dir, acknowledge_rights=True,
                           delay_seconds=0, log=lambda m: None)
        self.assertEqual(attempts, ["1-1"])
        index = json.loads((out_dir / "index.json").read_text())
        self.assertEqual(index["counts"], {"failed": 1})

        with mock.patch.object(mg, "collect_one", side_effect=failing):
            mg.run_measure(catalog_path, out_dir=out_dir, acknowledge_rights=True,
                           delay_seconds=0, log=lambda m: None)
        self.assertEqual(attempts, ["1-1"])  # not re-downloaded

        with mock.patch.object(mg, "collect_one", side_effect=failing):
            mg.run_measure(catalog_path, out_dir=out_dir, acknowledge_rights=True,
                           retry_failed=True, delay_seconds=0, log=lambda m: None)
        self.assertEqual(attempts, ["1-1", "1-1"])

    def test_non_eligible_item_is_refused_before_any_download(self):
        item = dict(self._item(), eligible=False, provider="vimeo", url="https://player.vimeo.com/video/1")
        with mock.patch.object(mg, "download_media") as download:
            with self.assertRaises(ValueError):
                mg.collect_one(item, Path(tempfile.gettempdir()))
        download.assert_not_called()


class CliTests(unittest.TestCase):
    def test_help_documents_both_subcommands_and_limit(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), self.assertRaises(SystemExit):
            mg.main(["--help"])
        text = buffer.getvalue()
        self.assertIn("enumerate", text)
        self.assertIn("measure", text)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            mg.main(["measure", "--help"])


if __name__ == "__main__":
    unittest.main()
