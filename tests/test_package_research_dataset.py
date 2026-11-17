"""Offline tests for ``scripts/package_research_dataset.py``.

Synthetic records only; no real ``research/analysis`` tree is read or written.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.acquisition import write_json_atomic
from scripts.package_research_dataset import package_site


def _record(schema: str, folder: str, slug: str) -> dict[str, object]:
    return {
        "schemaVersion": schema,
        "slug": slug,
        "generatedAt": "2026-01-02T03:04:05.000000Z",
        "census" if folder == "census" else "source": {"durationSeconds": 1.0},
        "record": {"id": "1", "slug": slug, "path": f"demo/videos/{slug}.json"},
        "acquisition": {"method": "http-download"},
    }


class PackageDatasetTests(unittest.TestCase):
    def _site(self, directory: str) -> Path:
        site = Path(directory) / "demo"
        for folder, schema in (
            ("videos", "kumiki.demo-video-evidence.v1"),
            ("stills", "kumiki.demo-still-evidence.v1"),
            ("census", "kumiki.demo-census-evidence.v1"),
        ):
            write_json_atomic(site / folder / f"1-{folder}.json",
                              _record(schema, folder, folder))
        write_json_atomic(site / "catalog.json", {
            "schemaVersion": "kumiki.demo-catalog.v1",
            "endpoints": {"catalog": "https://example.test/wp-json/posts"},
            "generatedAt": "2026-01-01T00:00:00.000000Z",
        })
        write_json_atomic(site / "index.json", {
            "schemaVersion": "kumiki.demo-index.v1", "records": []})
        (site / "report.md").write_text("# report\n", encoding="utf-8")
        write_json_atomic(site / "aggregate.json", {"schemaVersion": "demo"})
        return site

    def test_package_writes_trees_compressed_json_and_readme(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = self._site(directory)
            outcome = package_site(site)
            dataset = site / "dataset"

            self.assertEqual(outcome["records"],
                             {"videos": 1, "stills": 1, "census": 1})
            for name in ("videos.tar.gz", "stills.tar.gz", "census.tar.gz",
                         "catalog.json.gz", "index.json.gz", "DATASET.md"):
                self.assertTrue((dataset / name).is_file(), name)
            # report.md and aggregate.json stay plain and outside dataset/.
            self.assertFalse((dataset / "report.md").exists())
            self.assertFalse((dataset / "aggregate.json").exists())

            with tarfile.open(dataset / "videos.tar.gz") as archive:
                self.assertEqual(archive.getnames(), ["videos/1-videos.json"])
                self.assertEqual(archive.getmember(
                    "videos/1-videos.json").mtime, 0)

            with gzip.open(dataset / "catalog.json.gz", "rt",
                           encoding="utf-8") as handle:
                self.assertEqual(json.load(handle),
                                 json.loads((site / "catalog.json").read_text()))

            text = (dataset / "DATASET.md").read_text(encoding="utf-8")
            self.assertIn("Every downloaded media file", text)
            self.assertIn("catalog metadata and SHA-256 hashes are retained", text)
            self.assertIn("Cut candidates are not edits", text)
            self.assertIn("Stills are not video frames", text)
            self.assertIn("https://example.test/wp-json/posts", text)
            self.assertIn("| videos | 1 |", text)
            self.assertIn("tar -xzf dataset/videos.tar.gz", text)

    def test_two_packaging_runs_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = self._site(directory)
            package_site(site)
            first = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted((site / "dataset").iterdir())}
            package_site(site)
            second = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in sorted((site / "dataset").iterdir())}
            self.assertEqual(first, second)

    def test_missing_family_is_an_empty_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "demo"
            (site / "videos").mkdir(parents=True)
            (site / "report.md").write_text("report\n", encoding="utf-8")

            package_site(site)

            for folder in ("videos", "stills", "census", "audio"):
                archive = site / "dataset" / f"{folder}.tar.gz"
                with tarfile.open(archive) as handle:
                    self.assertEqual(handle.getnames(), [])


if __name__ == "__main__":
    unittest.main()
