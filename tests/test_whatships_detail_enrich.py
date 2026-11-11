"""Read-only What Ships detail enrichment and missing-info preservation."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.catalog.whatships_detail_enrich import (
    _call_mcp_get_video, _normalize_detail, enrich_whatships_details,
)
from kumiki_reference_lab.catalog.video_sources import _load_snapshot
from kumiki_reference_lab.cli.app import main
from tests.test_video_sources import whatships_fixture


def response_for(slug="film-two", *, views=4567, captured="2026-11-09T12:00:00.000Z"):
    return {
        "jsonrpc": "2.0", "id": 1,
        "result": {"content": [{"type": "text", "text": json.dumps({
            "slug": slug, "title": "Unverified trailer", "product": "Trailer",
            "company": "Studio B", "category": "design",
            "publishedAt": "2026-10-08T17:41:44.000Z",
            "durationSeconds": 38, "views": views, "viewsCapturedAt": captured,
            "tags": ["animation", "video"], "description": "Launch teaser for a product.",
            "url": f"https://whatships.com/videos/{slug}/",
            "tweetUrl": "https://x.com/studiob/status/2108251509830140401",
            "authorName": "Studio B", "authorHandle": "@studiob",
        })}]},
    }


class WhatshipsDetailEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.previous = self.root / "previous.json"
        self.previous.write_text(json.dumps(whatships_fixture()), encoding="utf-8")
        self.responses = self.root / "responses.json"
        self.responses.write_text(
            json.dumps({"film-two": response_for()}), encoding="utf-8")
        self.out = self.root / "new-enriched-catalog"

    def run_offline(self, **changes):
        return enrich_whatships_details(
            self.previous, self.out,
            **{"max_details": 1, "delay_seconds": 1,
               "offline_responses": self.responses, **changes})

    def test_one_batch_preserves_previous_detail_and_updates_missing(self):
        path = self.run_offline()
        report = json.loads(path.read_text())
        self.assertEqual(report["attempted"], 1)
        self.assertEqual(report["succeeded"], 1)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["remainingIndexOnly"], 0)
        self.assertFalse(report["liveNetworkUsed"])
        data = _load_snapshot(self.out / "whatships-all-videos.json")
        self.assertEqual(data["totals"]["enriched"], 2)
        self.assertEqual(data["totals"]["withoutDetails"], 0)
        self.assertEqual(data["videos"][0]["detail"]["views"], 189170)
        self.assertEqual(data["videos"][1]["detail"]["views"], 4567)
        self.assertEqual(data["videos"][1]["detail"]["tweetUrl"],
                         "https://x.com/studiob/status/2108251509830140401")
        coverage = json.loads((self.out/"coverage.json").read_text())
        self.assertEqual(coverage["detailedMetadataEntries"], 2)
        self.assertEqual(coverage["frameAnalysisEvidenceInThisDataset"], 0)
        with self.assertRaisesRegex(ValueError, "new directory"):
            self.run_offline()

    def test_malformed_mcp_result_does_not_fabricate_a_detail(self):
        data = json.loads(self.responses.read_text())
        data["film-two"]["result"]["content"][0]["text"] = "this is not JSON"
        self.responses.write_text(json.dumps(data))
        path = self.run_offline()
        result = json.loads(path.read_text())
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["succeeded"], 0)
        self.assertEqual(result["remainingIndexOnly"], 1)
        snapshot = _load_snapshot(self.out / "whatships-all-videos.json")
        self.assertIsNone(snapshot["videos"][1]["detail"])
        self.assertIn("invalid JSON", result["failures"][0]["reason"])

    def test_cross_slug_or_category_details_are_refused(self):
        with self.assertRaisesRegex(ValueError, "slug"):
            _normalize_detail("film-two", response_for(slug="film-one"),
                              expected_category="design")
        with self.assertRaisesRegex(ValueError, "category"):
            _normalize_detail("film-two", response_for(),
                              expected_category="motion")
        with self.assertRaisesRegex(ValueError, "original X"):
            changed = response_for()
            raw = json.loads(changed["result"]["content"][0]["text"])
            raw["tweetUrl"] = "https://x.com@evil.test/studiob/status/123"
            changed["result"]["content"][0]["text"] = json.dumps(raw)
            _normalize_detail("film-two", changed, expected_category="design")

    def test_unanchored_views_remain_unknown_not_viral_claims(self):
        result = _normalize_detail(
            "film-two", response_for(views=1000000, captured=None),
            expected_category="design")
        self.assertIsNone(result["views"])
        self.assertIsNone(result["viewsCapturedAt"])
        self.assertEqual(result["durationSeconds"], 38)

    def test_mcp_client_only_calls_read_only_catalog_tool(self):
        calls = []
        payload = json.dumps(response_for()).encode()
        class FakeResponse:
            status = 200
            headers = {"Content-Type": "application/json"}
            def read(self, limit):
                return payload
        class FakeConn:
            def __init__(self, host, port, timeout):
                calls.append(("connect", host, port, timeout))
            def request(self, method, path, body, headers):
                calls.append(("request", method, path, json.loads(body), headers))
            def getresponse(self):
                return FakeResponse()
            def close(self):
                calls.append(("close",))
        with patch("kumiki_reference_lab.catalog.whatships_detail_enrich.http.client.HTTPSConnection",
                   FakeConn):
            result = _call_mcp_get_video("film-two", timeout=20)
        self.assertEqual(result, response_for())
        self.assertEqual(calls[0], ("connect", "whatships.com", 443, 20))
        self.assertEqual(calls[1][1:3], ("POST", "/mcp/"))
        self.assertEqual(calls[1][3]["method"], "tools/call")
        self.assertEqual(calls[1][3]["params"]["name"], "get_video")
        self.assertEqual(calls[1][3]["params"]["arguments"], {"slug":"film-two"})
        self.assertEqual(calls[-1], ("close",))

    def test_missing_response_stays_missing_without_network(self):
        self.responses.write_text(json.dumps({}))
        with patch("kumiki_reference_lab.catalog.whatships_detail_enrich._call_mcp_get_video",
                   side_effect=AssertionError("offline must never call MCP")):
            path = self.run_offline()
        self.assertEqual(json.loads(path.read_text())["remainingIndexOnly"], 1)

    def test_input_budgets_and_offset_are_bounded(self):
        for override in (
            {"max_details": 0}, {"max_details": 101}, {"delay_seconds": 0},
            {"delay_seconds": float("nan")}, {"timeout": 0},
            {"start_offset": True}, {"start_offset": -1},
            {"start_offset": 2},
        ):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.run_offline(**override)
        self.assertFalse(self.out.exists())

    def test_cli_offline_enrichment(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main([
                "whatships-all", "enrich",
                "--previous", str(self.previous),
                "--offline-responses", str(self.responses),
                "--out", str(self.out), "--max-details", "1",
            ])
        self.assertEqual(exit_code, 0)
        self.assertTrue(Path(output.getvalue().strip()).is_file())
        result = json.loads(Path(output.getvalue().strip()).read_text())
        self.assertEqual(result["succeeded"], 1)


if __name__ == "__main__":
    unittest.main()
