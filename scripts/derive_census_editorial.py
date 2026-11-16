#!/usr/bin/env python3
"""Add the derived ``editorial`` block to every stored census record.

The driver walks ``<root>/<site>/census/*.json``, computes
:func:`kumiki_reference_lab.acquisition.derive_editorial` from the record's
own ``census`` block, and writes the result back as a top-level ``editorial``
key. No media, network or site vocabulary is involved: the block is a pure
function of fields already in the file, so the run is reproducible offline.

The write is additive and atomic. Key order, two-space indentation, UTF-8 and
the trailing newline are preserved, and a record whose stored block already
equals the computed block is left untouched. A second run therefore writes
nothing.

Usage::

    PYTHONPATH=src python scripts/derive_census_editorial.py \
        [--root research/analysis] [--site aicp] [--dry-run] \
        [--limit 5] [--report]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition import (  # noqa: E402
    derive_editorial, write_json_atomic,
)
from kumiki_reference_lab.acquisition.probe import finite_float  # noqa: E402


def _scan_for(record: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return the census scan block, accepting the legacy ``scan`` key."""
    for key in ("census", "scan"):
        scan = record.get(key)
        if isinstance(scan, Mapping):
            return scan
    return None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _median(values: Iterable[float]) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _fmt(value: object, digits: int = 2) -> str:
    number = finite_float(value)
    return "—" if number is None else f"{number:.{digits}f}"


def _summary(site: str, blocks: list[dict[str, Any]]) -> str:
    """One deterministic distribution line for a site's computed blocks."""
    plain = [block for block in blocks if block.get("strobeFlag") is not True]
    medians = [finite_float(block.get("medianShotSeconds"))
               for block in plain]
    medians = [value for value in medians if value is not None]
    rates = [finite_float(block.get("cutsPerMinuteOfRuntime"))
             for block in plain]
    rates = [value for value in rates if value is not None]
    counts = [block.get("shotCount") for block in plain
              if isinstance(block.get("shotCount"), int)]
    trends = {"accelerating": 0, "steady": 0, "decelerating": 0,
              "unclassified": 0}
    for block in blocks:
        trend = block.get("paceTrend")
        trends[trend if trend in trends else "unclassified"] += 1
    shot_range = (f"{min(counts)}–{max(counts)}" if counts else "—")
    return (
        f"{site}: clips={len(blocks)} non-strobe={len(plain)} "
        f"median_shot_s={_fmt(_median(medians))} "
        f"cut_rate_median={_fmt(_median(rates))} "
        f"shot_count_range={shot_range} "
        f"pace accelerating={trends['accelerating']} "
        f"steady={trends['steady']} "
        f"decelerating={trends['decelerating']} "
        f"unclassified={trends['unclassified']}")


def _sites(root: Path, site: str | None) -> list[Path]:
    if not root.is_dir():
        return []
    directories = [path for path in root.iterdir()
                   if path.is_dir() and (path / "census").is_dir()]
    if site is not None:
        directories = [path for path in directories if path.name == site]
    return sorted(directories, key=lambda path: path.name)


def run(
    *, root: Path, site: str | None, dry_run: bool, limit: int | None,
    report_only: bool,
) -> dict[str, Any]:
    """Compute and (unless reporting) persist the editorial block.

    Returns a deterministic summary so callers and tests can inspect counts
    without scraping stdout.
    """
    sites = _sites(root, site)
    summary: dict[str, Any] = {
        "root": str(root), "sites": {}, "written": 0, "unchanged": 0,
        "skipped": 0, "degraded": [], "problems": [],
    }
    for directory in sites:
        written = unchanged = skipped = 0
        blocks: list[dict[str, Any]] = []
        files = sorted((directory / "census").glob("*.json"),
                       key=lambda path: path.name)
        if limit is not None:
            files = files[:limit]
        for path in files:
            relative = f"{directory.name}/census/{path.name}"
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                skipped += 1
                summary["problems"].append(
                    {"file": relative,
                     "reason": f"{type(error).__name__}: {error}"})
                continue
            if not isinstance(record, dict):
                skipped += 1
                summary["problems"].append(
                    {"file": relative, "reason": "record is not a JSON object"})
                continue
            scan = _scan_for(record)
            if scan is None:
                skipped += 1
                summary["problems"].append(
                    {"file": relative, "reason": "record has no census block"})
                continue
            block = derive_editorial(scan)
            blocks.append(block)
            degraded = block.get("degraded") or []
            if degraded:
                summary["degraded"].append(
                    {"file": relative, "reasons": list(degraded)})
            if record.get("editorial") == block:
                unchanged += 1
                continue
            written += 1
            if dry_run or report_only:
                continue
            record["editorial"] = block
            write_json_atomic(path, record)
        summary["sites"][directory.name] = {
            "written": written, "unchanged": unchanged, "skipped": skipped,
            "blocks": blocks,
        }
        summary["written"] += written
        summary["unchanged"] += unchanged
        summary["skipped"] += skipped
    return summary


def _print_summary(summary: Mapping[str, Any], *, report_only: bool) -> None:
    mode = "report" if report_only else "write"
    print(f"editorial: root={summary['root']} mode={mode} "
          f"sites={len(summary['sites'])}")
    for site in sorted(summary["sites"]):
        entry = summary["sites"][site]
        print(f"{site}: written={entry['written']} "
              f"unchanged={entry['unchanged']} skipped={entry['skipped']}")
    print("")
    print("distribution (strobe records excluded from shot-length aggregates):")
    for site in sorted(summary["sites"]):
        print("  " + _summary(site, summary["sites"][site]["blocks"]))
    print("")
    degraded = summary["degraded"]
    print(f"degraded records: {len(degraded)}")
    for entry in degraded[:20]:
        print(f"  {entry['file']}: {', '.join(entry['reasons'])}")
    if len(degraded) > 20:
        print(f"  … {len(degraded) - 20} more")
    problems = summary["problems"]
    print(f"skipped records: {len(problems)}")
    for entry in problems[:20]:
        print(f"  {entry['file']}: {entry['reason']}")
    print(f"total: written={summary['written']} "
          f"unchanged={summary['unchanged']} skipped={summary['skipped']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "research" / "analysis",
                        help="census evidence root (default: research/analysis)")
    parser.add_argument("--site", default=None,
                        help="only process this site directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="compute and report without writing")
    parser.add_argument("--limit", type=int, default=None,
                        help="process at most N records per site")
    parser.add_argument("--report", action="store_true",
                        help="print the distribution summary instead of writing")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    summary = run(
        root=args.root, site=args.site, dry_run=args.dry_run,
        limit=args.limit, report_only=args.report)
    _print_summary(summary, report_only=args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
