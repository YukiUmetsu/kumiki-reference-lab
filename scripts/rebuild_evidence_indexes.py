#!/usr/bin/env python3
"""Rebuild the derived ``*-index.json`` files from the on-disk evidence records.

Indexes are a *projection* of the record trees. When a lane is interrupted, or
records are added/removed after the last run, the index counts drift from the
files on disk. This tool re-derives each index from the records themselves,
using the owning adapter's own summary-row function and the shared
:func:`kumiki_reference_lab.acquisition.build_index`, so the rows and counts are
exactly the ones a live resume run would assemble.

What is rebuilt
---------------
- ``<site>/index.json`` from ``<site>/videos/*.json``
- ``<site>/stills-index.json`` from ``<site>/stills/*.json``
- ``<site>/census-index.json`` from ``<site>/census/*.json`` (the row shape is
  the projection written by ``scripts/census_video_cuts.py``, including the
  record's ``identityVerification`` block and the recomputed
  ``identityCounts: {"strict-sha": n, "tolerant": n, "forced": n}``)

Rows are ordered by record file name. That is the order a resumed lane uses for
its retained rows, and it makes two rebuilds byte-identical.

Preserved, not invented
-----------------------
``skips``, ``failures`` and every header field (including ``generatedAt``,
``catalogSha256`` and the run budgets) are carried over from the existing
index: they describe attempts that left no record on disk and cannot be
recomputed offline. Only ``records``, ``counts`` and the census
``identityCounts`` header are re-derived. If an index does not exist yet,
``generatedAt`` is the newest record timestamp (or the Unix epoch for an empty
tree) so the output stays deterministic.

Usage::

    PYTHONPATH=src python scripts/rebuild_evidence_indexes.py \
        --root research/analysis [--site motiondesignawards] [--dry-run]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

# Header fields owned by ``build_index``; everything else is carried through.
_RESERVED = frozenset({"schemaVersion", "generatedAt", "counts", "records",
                       "skips", "failures"})

ADAPTER_FILES = {
    "motiondesignawards": "research_motiondesignawards",
    "shots": "research_shots",
    "aicp": "research_aicp",
    "promonews": "research_promonews",
    "directorslibrary": "research_wordpress_stills",
    "stash": "research_wordpress_stills",
}


@dataclass(frozen=True)
class IndexSpec:
    """One record family and the projection/index that summarises it."""

    folder: str
    index_name: str
    schema: Callable[[Any], str]
    summary: Callable[[Any, dict[str, Any], Path], dict[str, Any]]
    extras: Callable[[list[dict[str, Any]]], dict[str, Any]] | None = None


# Identity count keys, exactly the vocabulary ``census_video_cuts.py`` writes
# into ``census-index.json`` and prints in its run summary.
IDENTITY_COUNT_KEYS = ("strict-sha", "tolerant", "forced")


def _identity_count_key(block: Any) -> str | None:
    """Mirror ``census_video_cuts._identity_count_key``."""
    kind = block.get("kind") if isinstance(block, dict) else None
    if kind == "strict-sha":
        return "strict-sha"
    if kind == "forced":
        return "forced"
    if isinstance(kind, str) and kind.strip():
        return "tolerant"
    return None


def identity_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Mirror ``census_video_cuts.identity_counts`` over projected rows.

    A record with no ``identityVerification`` block contributes to no bucket, so
    the three counts may sum to less than ``counts.measured`` — the same shape
    the census driver writes.
    """
    counts = {key: 0 for key in IDENTITY_COUNT_KEYS}
    for row in rows:
        key = _identity_count_key(row.get("identityVerification"))
        if key is not None:
            counts[key] += 1
    return counts


def _census_spec(site: str) -> IndexSpec:
    """Mirror ``census_video_cuts.run_census_item``'s index projection."""

    def summary(module: Any, record: dict[str, Any], path: Path) -> dict[str, Any]:
        source = record.get("record") or {}
        census = record.get("census") or {}
        acquisition = record.get("acquisition") or {}
        row = {
            "id": source.get("id"),
            "slug": source.get("slug"),
            "recordPath": source.get("path") or f"{site}/videos/{path.stem}.json",
            "censusPath": f"{site}/census/{path.name}",
            "durationSeconds": census.get("durationSeconds"),
            "cutCount": census.get("cutCount"),
            "cutsPerMinute": census.get("cutsPerMinute"),
            "strobe": census.get("strobe"),
            "method": acquisition.get("method"),
        }
        if "urlSource" in source:
            row["urlSource"] = source["urlSource"]
        identity = record.get("identityVerification")
        if isinstance(identity, dict):
            row["identityVerification"] = identity
        return row

    return IndexSpec(
        folder="census", index_name="census-index.json",
        schema=lambda module: f"kumiki.{site}-census-index.v1",
        summary=summary,
        extras=lambda records: {"identityCounts": identity_counts(records)})


def specs_for_site(site: str, module: Any) -> list[IndexSpec]:
    """Return the index families owned by ``site``'s adapter."""
    if site == "motiondesignawards":
        return [
            IndexSpec(
                "videos", "index.json", lambda m: m.INDEX_SCHEMA,
                lambda m, record, path: m._video_summary_row(record)),
            IndexSpec(
                "stills", "stills-index.json",
                lambda m: m.STILLS_INDEX_SCHEMA,
                lambda m, record, path: m._still_summary_row(
                    record, Path("stills") / f"{m.safe_slug(record.get('slug'))}.json")),
            _census_spec(site),
        ]
    if site == "shots":
        return [
            IndexSpec("videos", "index.json", lambda m: m.INDEX_SCHEMA,
                      lambda m, record, path: m._video_summary_row(record, path)),
            IndexSpec("stills", "stills-index.json",
                      lambda m: m.STILLS_INDEX_SCHEMA,
                      lambda m, record, path: m._still_summary_row(record, path)),
            _census_spec(site),
        ]
    if site == "aicp":
        return [
            IndexSpec("videos", "index.json", lambda m: m.INDEX_SCHEMA,
                      lambda m, record, path: m._video_summary_row(record, path)),
            IndexSpec("stills", "stills-index.json",
                      lambda m: m.STILLS_INDEX_SCHEMA,
                      lambda m, record, path: m._still_summary_row(record, path)),
            _census_spec(site),
        ]
    if site == "promonews":
        return [
            IndexSpec("videos", "index.json", lambda m: m.VIDEO_INDEX_SCHEMA,
                      lambda m, record, path: m._video_summary_row(record, path)),
            IndexSpec("stills", "stills-index.json",
                      lambda m: m.STILLS_INDEX_SCHEMA,
                      lambda m, record, path: m._still_summary_row(record, path)),
            _census_spec(site),
        ]
    if site in ("directorslibrary", "stash"):
        config = module.SITES[site]
        return [
            IndexSpec(
                "videos", "index.json",
                lambda m: m.schema_name(config, "index"),
                lambda m, record, path: m._video_summary_row(record, path)),
            IndexSpec(
                "stills", "stills-index.json",
                lambda m: m.schema_name(config, "stills-index"),
                lambda m, record, path: m._still_summary_row(record, path)),
            _census_spec(site),
        ]
    raise ValueError(f"no index specification for site {site!r}")


@lru_cache(maxsize=None)
def load_adapter(site: str) -> Any:
    """Import the adapter module that owns ``site`` as a private module."""
    filename = ADAPTER_FILES.get(site)
    if filename is None:
        return None
    path = Path(__file__).resolve().parent / f"{filename}.py"
    spec = importlib.util.spec_from_file_location(f"_kumiki_{filename}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import adapter {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _latest_generated_at(existing: dict[str, Any] | None,
                         records: list[dict[str, Any]], folder: Path) -> str:
    """Newest timestamp among the old index and the records, deterministically."""
    stamps: list[str] = []
    if isinstance(existing, dict) and isinstance(existing.get("generatedAt"), str):
        stamps.append(existing["generatedAt"])
    stamps.extend(record["generatedAt"] for record in records
                  if isinstance(record.get("generatedAt"), str))
    if stamps:
        return max(stamps)
    mtimes = [path.stat().st_mtime for path in folder.glob("*.json")]
    if not mtimes:
        return "1970-01-01T00:00:00Z"
    moment = datetime.fromtimestamp(max(mtimes), tz=timezone.utc)
    return moment.isoformat().replace("+00:00", "Z")


def rebuild_index(
    site_dir: Path, site: str, spec: IndexSpec, module: Any, *,
    dry_run: bool = False,
) -> dict[str, Any] | None:
    """Re-derive one index in place (or report the change under ``dry_run``).

    Returns ``None`` when neither the index nor its record folder exists.
    """
    site_dir = Path(site_dir)
    folder = site_dir / spec.folder
    index_path = site_dir / spec.index_name
    existing = _read_json(index_path)
    if existing is None and not folder.is_dir():
        return None

    records: list[dict[str, Any]] = []
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise ValueError(f"cannot read record {path}: {error}") from error
            if not isinstance(record, dict):
                raise ValueError(f"record {path} is not a JSON object")
            records.append(spec.summary(module, record, Path(spec.folder) / path.name))

    skips = existing.get("skips") if isinstance(existing, dict) else None
    failures = existing.get("failures") if isinstance(existing, dict) else None
    skips = list(skips) if isinstance(skips, list) else []
    failures = list(failures) if isinstance(failures, list) else []
    generated_at = _latest_generated_at(existing, records, folder)
    schema = (existing.get("schemaVersion")
              if isinstance(existing, dict)
              and isinstance(existing.get("schemaVersion"), str)
              else spec.schema(module))
    extra = {key: value for key, value in (existing or {}).items()
             if key not in _RESERVED}
    if spec.extras is not None:
        extra.update(spec.extras(records))

    payload = module.build_index(
        schema_version=schema, records=records, skips=skips,
        failures=failures, generated_at=generated_at, extra=extra)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False,
                          allow_nan=False) + "\n"
    previous = (index_path.read_text(encoding="utf-8")
                if index_path.is_file() else None)
    changed = rendered != previous
    if changed and not dry_run:
        module.write_json_atomic(index_path, payload)
    return {
        "site": site,
        "index": spec.index_name,
        "measured": len(records),
        "skipped": len(skips),
        "failed": len(failures),
        "changed": changed,
        "written": changed and not dry_run,
        "path": str(index_path),
    }


def discover_sites(root: Path) -> list[Path]:
    """Directories that actually hold a record family (same rule as auditor)."""
    if not root.is_dir():
        return []
    return [child for child in sorted(root.iterdir())
            if child.is_dir()
            and any((child / folder).is_dir()
                    for folder in ("videos", "stills", "census"))]


def run_rebuild(
    root: Path, sites: list[str] | None = None, *, dry_run: bool = False,
) -> dict[str, Any]:
    """Rebuild every known site under ``root``; return per-index results."""
    root = Path(root)
    requested = list(sites) if sites else None
    wanted = set(requested) if requested else None
    results: list[dict[str, Any]] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for site_dir in discover_sites(root):
        site = site_dir.name
        if wanted is not None and site not in wanted:
            continue
        seen.add(site)
        module = load_adapter(site)
        if module is None:
            unknown.append(site)
            continue
        for spec in specs_for_site(site, module):
            outcome = rebuild_index(site_dir, site, spec, module, dry_run=dry_run)
            if outcome is not None:
                results.append(outcome)
    if wanted is not None:
        unknown.extend(sorted(wanted - seen - set(unknown)))
    return {
        "root": str(root),
        "dryRun": dry_run,
        "results": results,
        "unknownSites": sorted(set(unknown)),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="research/analysis",
                        help="evidence root containing <site>/videos records")
    parser.add_argument("--site", action="append", default=[],
                        help="site directory name (repeatable; default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report the rebuild without writing any index")
    return parser


def main(argv: list[str] | None = None) -> int:
    options = build_parser().parse_args(argv)
    report = run_rebuild(
        Path(options.root), options.site or None, dry_run=options.dry_run)
    for outcome in report["results"]:
        state = ("dry-run " if report["dryRun"] else
                 ("updated" if outcome["written"] else "unchanged"))
        print(f"{outcome['site']}/{outcome['index']}: "
              f"measured={outcome['measured']} skipped={outcome['skipped']} "
              f"failed={outcome['failed']} {state}")
    for site in report["unknownSites"]:
        print(f"skipped {site!r}: no known adapter", file=sys.stderr)
    changed = sum(1 for outcome in report["results"] if outcome["changed"])
    print(f"{len(report['results'])} indexes inspected, {changed} "
          f"{'would change' if report['dryRun'] else 'changed'}")
    return 1 if report["unknownSites"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
