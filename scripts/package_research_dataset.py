#!/usr/bin/env python3
"""Package the research evidence trees into small, deterministic ``dataset/`` dirs.

The raw evidence JSON under ``research/analysis/<site>/`` is hundreds of
megabytes; committing it directly is not viable. For each site this tool writes
``research/analysis/<site>/dataset/`` containing:

- ``videos.tar.gz``, ``stills.tar.gz``, ``census.tar.gz`` — the record trees,
  gzip level 1, deterministic: sorted names, zeroed mtimes/uid/gid, empty
  uname/gname, no OS-specific metadata;
- ``catalog.json.gz``, ``index.json.gz``, ``stills-index.json.gz``,
  ``census-index.json.gz`` — the large JSON documents, gzip level 1 with a
  zero timestamp and no embedded file name;
- ``DATASET.md`` — counts, source catalog, acquisition window, schemas,
  retention statement, unpack commands and non-claims.

``report.md`` stays plain beside ``dataset/`` as the human-readable deliverable;
``aggregate.json`` is packaged as ``aggregate.json.gz``. Two packing runs over the
same records produce byte-identical archives.

Usage::

    PYTHONPATH=src python scripts/package_research_dataset.py \
        --root research/analysis [--site motiondesignawards]
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sys
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

FAMILIES = ("videos", "stills", "census", "audio")
COMPRESSED_JSON = ("catalog.json", "index.json", "stills-index.json",
                   "census-index.json", "audio-index.json", "aggregate.json",
                   "quality-selection.json", "components.json", "ids.json")
GZIP_LEVEL = 1


def _gzip_stream(dest: Path, source: Path) -> int:
    """Gzip ``source`` into ``dest`` deterministically; return bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, dest.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=GZIP_LEVEL,
                           mtime=0, filename="") as gz:
            shutil.copyfileobj(src, gz, length=1 << 20)
    return dest.stat().st_size


def _tar_gz_tree(source: Path, archive_root: str, dest: Path) -> int:
    """Archive one tree deterministically (sorted, zeroed metadata)."""
    files = (sorted(path for path in source.rglob("*") if path.is_file())
             if source.is_dir() else [])
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=GZIP_LEVEL,
                           mtime=0, filename="") as gz:
            with tarfile.open(fileobj=gz, mode="w|",
                              format=tarfile.PAX_FORMAT) as tar:
                for path in files:
                    relative = path.relative_to(source).as_posix()
                    info = tarfile.TarInfo(name=f"{archive_root}/{relative}")
                    info.size = path.stat().st_size
                    info.mtime = 0
                    info.mode = 0o644
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.type = tarfile.REGTYPE
                    with path.open("rb") as handle:
                        tar.addfile(info, handle)
    return dest.stat().st_size


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@dataclass
class FamilyStats:
    folder: str
    count: int = 0
    schemas: dict[str, int] = field(default_factory=dict)
    first: str | None = None
    last: str | None = None


def _family_stats(site_dir: Path, folder: str) -> FamilyStats:
    stats = FamilyStats(folder=folder)
    directory = site_dir / folder
    if not directory.is_dir():
        return stats
    stamps: list[str] = []
    for path in sorted(directory.glob("*.json")):
        stats.count += 1
        record = _read_json(path)
        if not isinstance(record, dict):
            stats.schemas["unreadable"] = stats.schemas.get("unreadable", 0) + 1
            continue
        schema = record.get("schemaVersion")
        key = schema if isinstance(schema, str) else "unknown"
        stats.schemas[key] = stats.schemas.get(key, 0) + 1
        if isinstance(record.get("generatedAt"), str):
            stamps.append(record["generatedAt"])
    if stamps:
        stats.first, stats.last = min(stamps), max(stamps)
    return stats


def _catalog_info(catalog: dict[str, Any] | None) -> dict[str, Any]:
    catalog = catalog if isinstance(catalog, dict) else {}
    endpoints = catalog.get("endpoints")
    url = catalog.get("endpoint")
    if not isinstance(url, str) and isinstance(endpoints, dict):
        url = endpoints.get("catalog")
    retrieved = (catalog.get("retrievedAt") or catalog.get("retrievedOn")
                 or catalog.get("generatedAt"))
    return {
        "url": url if isinstance(url, str) else "not recorded",
        "schema": catalog.get("schemaVersion") or "not recorded",
        "retrieved": retrieved if isinstance(retrieved, str) else "not recorded",
    }


def _table(stats: list[FamilyStats]) -> str:
    lines = ["| family | records | schema(s) | record `generatedAt` window (UTC) |",
             "|---|---:|---|---|"]
    for item in stats:
        schemas = (", ".join(f"`{name}` × {count}"
                             for name, count in sorted(item.schemas.items()))
                   or "—")
        window = (f"`{item.first}` .. `{item.last}`"
                  if item.first else "—")
        lines.append(f"| {item.folder} | {item.count:,} | {schemas} | {window} |")
    return "\n".join(lines)


def _dataset_markdown(site: str, stats: list[FamilyStats],
                      catalog: dict[str, Any],
                      compressed: list[str]) -> str:
    total = sum(item.count for item in stats)
    first = min((item.first for item in stats if item.first), default=None)
    last = max((item.last for item in stats if item.last), default=None)
    overall = (f"`{first}` .. `{last}`" if first and last else "not recorded")
    unpack = "\n".join(f"gzip -dk dataset/{name}.gz" for name in compressed)
    return f"""# {site} — measured evidence dataset

This directory is the compressed, committable form of the raw evidence trees
under `research/analysis/{site}/`. `report.md` stays plain beside it as the
human-readable deliverable; `aggregate.json` is packaged compressed.

## Counts and schemas

{_table(stats)}

Total records: **{total:,}**.

- Source catalog: {catalog['url']}
- Catalog schema: `{catalog['schema']}`; retrieved `{catalog['retrieved']}`.
- Overall record acquisition window (`generatedAt`, UTC): {overall}.

## What is retained

Every downloaded media file — each video rendition and each published poster
image — was measured in a temporary directory and then deleted. Only numeric
measurements, catalog metadata and SHA-256 hashes are retained. No video,
frame, thumbnail, audio, image or other media is included in this package or
redistributed. The record trees are archived verbatim; `catalog.json.gz` and the
`*-index.json.gz` files are the same JSON documents gzip-compressed.

## Unpack

```sh
cd research/analysis/{site}
tar -xzf dataset/videos.tar.gz
tar -xzf dataset/stills.tar.gz
tar -xzf dataset/census.tar.gz
{unpack}
```

The archives restore `videos/`, `stills/` and `census/` under the current
directory; `gzip -dk` writes each JSON beside its `.gz`. An empty family is an
empty archive. Rebuild the indexes with
`PYTHONPATH=src python scripts/rebuild_evidence_indexes.py --root research/analysis --site {site}`,
and repack this directory with
`PYTHONPATH=src python scripts/package_research_dataset.py --root research/analysis --site {site}`.

## Non-claims

- **Cut candidates are not edits.** Census and window cut candidates are ffmpeg
  scene-score exceedances; fast motion, flashes, transitions and compression can
  exceed the threshold. They are not verified edits.
- **Stills are not video frames.** A still is one published poster image, with
  no motion, cut, pacing or timing evidence.
- **Window values are samples.** They describe bounded source-PTS windows, not
  the whole runtime.
- **Census values are film-level.** They come from a full-runtime decode with a
  fixed-cadence appearance sample; they are not a human review.
- **Numbers are proxies.** Display-RGB luma/saturation at decode size are not
  scene-linear light, calibrated colour, or a style, quality, intent, identity
  or authorship judgement.
- **No expert review.** No human review was performed; these are automated
  numeric measurements.
"""


def package_site(site_dir: Path) -> dict[str, Any]:
    """Write ``site_dir/dataset`` and return its per-file sizes."""
    site = site_dir.name
    dataset = site_dir / "dataset"
    dataset.mkdir(parents=True, exist_ok=True)
    sizes: dict[str, int] = {}
    stats: list[FamilyStats] = []
    for folder in FAMILIES:
        archive = dataset / f"{folder}.tar.gz"
        sizes[archive.name] = _tar_gz_tree(site_dir / folder, folder, archive)
        if (site_dir / folder).is_dir():
            stats.append(_family_stats(site_dir, folder))
    compressed: list[str] = []
    for name in COMPRESSED_JSON:
        source = site_dir / name
        if not source.is_file():
            continue
        target = dataset / f"{name}.gz"
        sizes[target.name] = _gzip_stream(target, source)
        compressed.append(name)
    catalog = _read_json(site_dir / "catalog.json")
    markdown = _dataset_markdown(site, stats, _catalog_info(catalog), compressed)
    target = dataset / "DATASET.md"
    target.write_text(markdown, encoding="utf-8")
    sizes[target.name] = target.stat().st_size
    return {
        "site": site,
        "directory": str(dataset),
        "sizes": sizes,
        "totalBytes": sum(sizes.values()),
        "records": {item.folder: item.count for item in stats},
    }


def discover_sites(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return [child for child in sorted(root.iterdir())
            if child.is_dir()
            and any((child / folder).is_dir() for folder in FAMILIES)]


def run_package(root: Path, sites: list[str] | None = None) -> dict[str, Any]:
    root = Path(root)
    wanted = set(sites) if sites else None
    results = []
    for site_dir in discover_sites(root):
        if wanted is not None and site_dir.name not in wanted:
            continue
        results.append(package_site(site_dir))
    seen = {result["site"] for result in results}
    unknown = sorted(wanted - seen) if wanted else []
    return {
        "root": str(root),
        "results": results,
        "unknownSites": unknown,
        "totalBytes": sum(result["totalBytes"] for result in results),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="research/analysis",
                        help="evidence root containing <site>/ datasets")
    parser.add_argument("--site", action="append", default=[],
                        help="site directory name (repeatable; default: all)")
    return parser


def main(argv: list[str] | None = None) -> int:
    options = build_parser().parse_args(argv)
    report = run_package(Path(options.root), options.site or None)
    for result in report["results"]:
        print(f"{result['site']}: {result['totalBytes'] / (1024 * 1024):.2f} MiB "
              f"({result['records']})")
        for name, size in sorted(result["sizes"].items()):
            print(f"  {name:24} {size / (1024 * 1024):8.2f} MiB")
    print(f"total dataset/ size: {report['totalBytes'] / (1024 * 1024):.2f} MiB")
    for site in report["unknownSites"]:
        print(f"skipped {site!r}: no evidence tree", file=sys.stderr)
    return 1 if report["unknownSites"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
