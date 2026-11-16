"""Offline tests for ``scripts/rebuild_evidence_indexes.py``.

A fake adapter supplies the summary projection and the shared ``build_index``;
no real adapter, network, ffmpeg, or ``research/analysis`` tree is touched.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.acquisition import build_index, write_json_atomic
from scripts.rebuild_evidence_indexes import IndexSpec, _census_spec, rebuild_index

GENERATED_AT = "2026-01-02T03:04:05.000000Z"


class FakeAdapter:
    """Minimal stand-in exposing the adapter surface the rebuilder calls."""

    SCHEMA = "kumiki.demo-index.v1"

    @staticmethod
    def build_index(**kwargs):
        return build_index(**kwargs)

    @staticmethod
    def write_json_atomic(path, payload):
        return write_json_atomic(path, payload)

    @staticmethod
    def _video_summary_row(record, path=None):
        return {
            "id": record.get("id"),
            "slug": record.get("slug"),
            "recordPath": (path.as_posix() if path is not None
                           else f"videos/{record.get('id')}.json"),
        }


def _spec() -> IndexSpec:
    return IndexSpec(
        folder="videos", index_name="index.json",
        schema=lambda module: module.SCHEMA,
        summary=lambda module, record, path: module._video_summary_row(record, path))


def _write_records(site: Path, slugs: list[str]) -> None:
    (site / "videos").mkdir(parents=True, exist_ok=True)
    for index, slug in enumerate(slugs):
        write_json_atomic(site / "videos" / f"{index}-{slug}.json", {
            "id": f"{index}", "slug": slug, "generatedAt": GENERATED_AT,
        })


def _stale_index(site: Path) -> None:
    write_json_atomic(site / "index.json", build_index(
        schema_version="kumiki.demo-index.v1",
        records=[{"id": "999", "slug": "stale", "recordPath": "videos/stale.json"}],
        skips=[{"id": "1", "reason": "resume-existing-record"}],
        failures=[{"id": "2", "reason": "timeout"}],
        generated_at=GENERATED_AT,
        extra={"catalogSha256": "a" * 64, "limit": None}))


class RebuildIndexTests(unittest.TestCase):
    def test_rebuild_rederives_records_and_preserves_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "demo"
            _write_records(site, ["alpha", "beta", "gamma"])
            _stale_index(site)

            outcome = rebuild_index(site, "demo", _spec(), FakeAdapter)

            self.assertEqual(outcome["measured"], 3)
            self.assertTrue(outcome["written"])
            payload = json.loads((site / "index.json").read_text())
            self.assertEqual(payload["counts"],
                             {"measured": 3, "skipped": 1, "failed": 1})
            self.assertEqual([row["slug"] for row in payload["records"]],
                             ["alpha", "beta", "gamma"])
            # The stale row is gone; attempt history and run header survive.
            self.assertEqual(payload["skips"][0]["reason"],
                             "resume-existing-record")
            self.assertEqual(payload["failures"][0]["reason"], "timeout")
            self.assertEqual(payload["generatedAt"], GENERATED_AT)
            self.assertEqual(payload["schemaVersion"], "kumiki.demo-index.v1")
            self.assertEqual(payload["catalogSha256"], "a" * 64)
            self.assertIsNone(payload["limit"])

    def test_dry_run_reports_change_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "demo"
            _write_records(site, ["alpha", "beta"])
            _stale_index(site)
            before = (site / "index.json").read_bytes()

            outcome = rebuild_index(site, "demo", _spec(), FakeAdapter,
                                    dry_run=True)

            self.assertTrue(outcome["changed"])
            self.assertFalse(outcome["written"])
            self.assertEqual((site / "index.json").read_bytes(), before)

    def test_second_rebuild_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "demo"
            _write_records(site, ["alpha", "beta"])
            _stale_index(site)

            first = rebuild_index(site, "demo", _spec(), FakeAdapter)
            after_first = (site / "index.json").read_bytes()
            second = rebuild_index(site, "demo", _spec(), FakeAdapter)

            self.assertTrue(first["changed"])
            self.assertFalse(second["changed"])
            self.assertEqual((site / "index.json").read_bytes(), after_first)

    def test_empty_tree_keeps_an_empty_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "demo"
            (site / "videos").mkdir(parents=True)
            _stale_index(site)

            outcome = rebuild_index(site, "demo", _spec(), FakeAdapter)

            payload = json.loads((site / "index.json").read_text())
            self.assertEqual(outcome["measured"], 0)
            self.assertEqual(payload["counts"]["measured"], 0)
            self.assertEqual(payload["records"], [])
            self.assertEqual(payload["generatedAt"], GENERATED_AT)


class CensusProjectionTests(unittest.TestCase):
    def test_census_row_matches_driver_projection(self) -> None:
        spec = _census_spec("demo")
        record = {
            "record": {
                "id": "123", "slug": "clip",
                "path": "demo/videos/123-clip.json",
                "urlSource": "catalog",
            },
            "census": {
                "durationSeconds": 12.5, "cutCount": 4,
                "cutsPerMinute": 19.2, "strobe": False,
            },
            "acquisition": {"method": "http-download"},
        }
        row = spec.summary(FakeAdapter, record, Path("census/3-123-clip.json"))
        self.assertEqual(row, {
            "id": "123", "slug": "clip",
            "recordPath": "demo/videos/123-clip.json",
            "censusPath": "demo/census/3-123-clip.json",
            "durationSeconds": 12.5, "cutCount": 4,
            "cutsPerMinute": 19.2, "strobe": False,
            "method": "http-download", "urlSource": "catalog",
        })
        self.assertEqual(spec.schema(FakeAdapter), "kumiki.demo-census-index.v1")


if __name__ == "__main__":
    unittest.main()
