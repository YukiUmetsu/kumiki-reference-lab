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

    def test_census_row_projects_the_identity_block(self) -> None:
        spec = _census_spec("demo")
        block = {
            "kind": "duration+resolution+codec", "shaMatched": False,
            "durationDeltaSeconds": 0.16, "resolutionMatched": True,
            "containerMatched": True, "codecMatched": True,
        }
        record = {
            "record": {"id": "7", "slug": "clip"},
            "census": {"durationSeconds": 30.0, "cutCount": 2,
                       "cutsPerMinute": 4.0, "strobe": False},
            "acquisition": {"method": "hls-remux"},
            "identityVerification": block,
        }
        row = spec.summary(FakeAdapter, record, Path("census/7-clip.json"))
        self.assertEqual(row["identityVerification"], block)
        # The projected block is the record's own, not a re-derived summary.
        self.assertIs(row["identityVerification"], block)

    def test_census_row_without_an_identity_block_keeps_the_key_out(self) -> None:
        spec = _census_spec("demo")
        record = {
            "record": {"id": "1", "slug": "old"},
            "census": {"durationSeconds": 9.0, "cutCount": 1,
                       "cutsPerMinute": 6.666667, "strobe": False},
            "acquisition": {"method": "http-download"},
        }
        row = spec.summary(FakeAdapter, record, Path("census/1-old.json"))
        self.assertNotIn("identityVerification", row)


def _write_census_records(site: Path, entries: list[tuple[str, dict | None]]) -> None:
    (site / "census").mkdir(parents=True, exist_ok=True)
    for index, (slug, identity) in enumerate(entries):
        record = {
            "generatedAt": GENERATED_AT,
            "record": {"id": str(index), "slug": slug,
                       "path": f"demo/videos/{index}-{slug}.json"},
            "census": {"durationSeconds": 10.0 + index, "cutCount": index,
                       "cutsPerMinute": 6.0 * index, "strobe": False},
            "acquisition": {"method": "http-download"},
        }
        if identity is not None:
            record["identityVerification"] = identity
        write_json_atomic(site / "census" / f"{index}-{slug}.json", record)


def _stale_census_index(site: Path) -> None:
    write_json_atomic(site / "census-index.json", FakeAdapter.build_index(
        schema_version="kumiki.demo-census-index.v1",
        records=[{"id": "999", "slug": "stale",
                  "censusPath": "demo/census/stale.json"}],
        skips=[{"id": "1", "reason": "missing-url"}],
        failures=[{"id": "2", "reason": "media-changed"}],
        generated_at=GENERATED_AT,
        extra={
            "site": "demo",
            "sourceRoot": "demo/videos",
            "sampleSeconds": 1.0,
            "windowSeconds": 10.0,
            "identityCounts": {"strict-sha": 0, "tolerant": 0, "forced": 0},
            "limits": ["candidate count is not an edit count"],
        }))


class CensusIdentityCountTests(unittest.TestCase):
    def test_rebuild_recomputes_identity_counts_and_keeps_the_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "demo"
            _write_census_records(site, [
                ("byte", {"kind": "strict-sha", "shaMatched": True}),
                ("remux", {"kind": "duration+resolution+codec",
                           "shaMatched": False, "codecMatched": True}),
                ("forced", {"kind": "forced", "shaMatched": False,
                            "reason": "sha256 a != b"}),
                ("older", None),
            ])
            _stale_census_index(site)

            outcome = rebuild_index(site, "demo", _census_spec("demo"), FakeAdapter)

            self.assertTrue(outcome["written"])
            payload = json.loads((site / "census-index.json").read_text())
            self.assertEqual(payload["identityCounts"],
                             {"strict-sha": 1, "tolerant": 1, "forced": 1})
            self.assertEqual(payload["counts"],
                             {"measured": 4, "skipped": 1, "failed": 1})
            by_slug = {row["slug"]: row for row in payload["records"]}
            self.assertEqual(
                by_slug["byte"]["identityVerification"]["kind"], "strict-sha")
            self.assertEqual(
                by_slug["remux"]["identityVerification"]["kind"],
                "duration+resolution+codec")
            self.assertEqual(
                by_slug["forced"]["identityVerification"]["reason"],
                "sha256 a != b")
            # An older record carries no block, so no key is invented for it.
            self.assertNotIn("identityVerification", by_slug["older"])
            # Header fields the rebuild cannot re-derive survive unchanged.
            self.assertEqual(payload["site"], "demo")
            self.assertEqual(payload["sourceRoot"], "demo/videos")
            self.assertEqual(payload["sampleSeconds"], 1.0)
            self.assertEqual(payload["limits"],
                             ["candidate count is not an edit count"])
            self.assertEqual(payload["skips"][0]["reason"], "missing-url")
            self.assertEqual(payload["failures"][0]["reason"], "media-changed")

    def test_identity_counts_name_every_kind_and_ignore_missing_blocks(self) -> None:
        from scripts.rebuild_evidence_indexes import identity_counts

        rows = [
            {"identityVerification": {"kind": "strict-sha"}},
            {"identityVerification": {"kind": "duration+resolution+codec"}},
            {"identityVerification": {"kind": "duration+resolution+codec"}},
            {"identityVerification": {"kind": "forced"}},
            {"identityVerification": {"kind": ""}},
            {},
        ]
        self.assertEqual(identity_counts(rows),
                         {"strict-sha": 1, "tolerant": 2, "forced": 1})

    def test_census_rebuild_is_byte_identical_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "demo"
            _write_census_records(site, [
                ("byte", {"kind": "strict-sha", "shaMatched": True}),
                ("forced", {"kind": "forced", "reason": "duration delta 2s"}),
            ])
            _stale_census_index(site)
            spec = _census_spec("demo")

            first = rebuild_index(site, "demo", spec, FakeAdapter)
            after_first = (site / "census-index.json").read_bytes()
            second = rebuild_index(site, "demo", spec, FakeAdapter)

            self.assertTrue(first["changed"])
            self.assertFalse(second["changed"])
            self.assertEqual((site / "census-index.json").read_bytes(),
                             after_first)
            payload = json.loads(after_first)
            self.assertEqual(payload["identityCounts"],
                             {"strict-sha": 1, "tolerant": 0, "forced": 1})


if __name__ == "__main__":
    unittest.main()
