"""Annotate committed still evidence with engine quality flags, offline.

Walks ``<root>/*/stills/*.json``, recomputes
:func:`kumiki_reference_lab.acquisition.stills.still_quality_flags` from each
record's *stored* metrics, and inserts or updates ``still.qualityFlags``.

Only records whose computed flags are non-empty are rewritten, and only when
the stored value differs. Everything else is left byte-for-byte untouched:
the numbers, key order, indentation (2 spaces), UTF-8 text, and trailing
newline match the acquisition writers. No image is fetched or decoded.

Run with::

    PYTHONPATH=src python scripts/mark_still_quality.py --root research/analysis
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition.stills import (  # noqa: E402
    still_quality_flags,
)

STILL_SCHEMA_MARKER = "-still-evidence.v"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Replace one record in place, matching the acquisition writers' layout."""
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=path.name + ".",
        suffix=".tmp", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False,
                      allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _is_still_record(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    schema = record.get("schemaVersion")
    return (isinstance(schema, str)
            and STILL_SCHEMA_MARKER in schema
            and isinstance(record.get("still"), dict))


def mark_site(site_dir: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Annotate one site's still records and return its counters."""
    flagged = 0
    written = 0
    counts: dict[str, int] = {}
    folder = site_dir / "stills"
    if not folder.is_dir():
        return {"flagged": 0, "written": 0, "counts": counts}
    for path in sorted(folder.glob("*.json")):
        try:
            record = _read_json(path)
        except (OSError, ValueError) as error:
            print(f"  skip {path.name}: {type(error).__name__}: {error}")
            continue
        if not _is_still_record(record):
            continue
        still = record["still"]
        metrics = still.get("metrics")
        if not isinstance(metrics, dict):
            continue
        flags = still_quality_flags(
            metrics, width=still.get("imageWidth"),
            height=still.get("imageHeight"))
        if not flags:
            continue
        flagged += 1
        for flag in flags:
            counts[flag] = counts.get(flag, 0) + 1
        if still.get("qualityFlags") == flags:
            continue
        still["qualityFlags"] = flags
        if not dry_run:
            _write_json_atomic(path, record)
        written += 1
    return {"flagged": flagged, "written": written, "counts": counts}


def run(root: Path, *, dry_run: bool = False) -> int:
    if not root.is_dir():
        raise ValueError(f"root is not a directory: {root}")
    print(f"root: {root}{' (dry run)' if dry_run else ''}")
    total_flagged = total_written = 0
    for site_dir in sorted(child for child in root.iterdir()
                           if child.is_dir()):
        result = mark_site(site_dir, dry_run=dry_run)
        if not result["flagged"] and not result["written"]:
            continue
        total_flagged += result["flagged"]
        total_written += result["written"]
        breakdown = ", ".join(f"{flag}={count}"
                              for flag, count in sorted(result["counts"].items()))
        print(f"{site_dir.name}: flagged={result['flagged']} "
              f"written={result['written']} ({breakdown})")
    print(f"total: flagged={total_flagged} written={total_written}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("research/analysis"),
                        help="directory whose child site trees are annotated")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change without writing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args.root, dry_run=args.dry_run)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
