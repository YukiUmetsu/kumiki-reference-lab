"""Recompute stored video-evidence summaries from their embedded probes.

The acquisition engine added additive cut-validity fields to
:func:`kumiki_reference_lab.acquisition.windows.summarize_probes`. Records
written before that change carry an older ``summary`` block. This script walks
``<root>/*/videos/*.json``, rebuilds the record-level summary with the engine's
own function, and rewrites a record only when the computed summary differs from
the stored one.

Two window layouts are accepted:

* ``record["windows"][].probe`` (every committed video adapter), and
* a flattened probe (``evidence.numericVisual.windows[]`` and its archived
  variants), where the probe fields live on the window itself.

The summary budget is the same as a fresh build: source frame rate, source
timebase, ``coverage.sampledSeconds`` and ``coverage.fractionOfRuntime``. When
the probes do not carry the data needed for a field (for example no
``sampledFramePairs`` at all), the stored value is preserved and the record is
reported as ``partial`` rather than silently nulling the field.

Only the standard library and the engine package are used. Writes are atomic,
UTF-8, two-space indented, and end with a newline; a second run is a no-op.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:  # match the other research_* adapters
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition import summarize_probes  # noqa: E402
from kumiki_reference_lab.acquisition.probe import finite_float  # noqa: E402

PROBE_MARKERS = (
    "cutCandidatePts",
    "sampledWindowSummary",
    "sampledFrames",
    "sampledFramePairs",
)
FRAME_RATE_KEYS = ("frameRate", "framesPerSecond", "nominalFrameRate")


# ---------------------------------------------------------------------------
# Record shapes
# ---------------------------------------------------------------------------


def _as_mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _probe_from_window(window: object) -> dict[str, Any] | None:
    """Return the probe payload for one window, handling both layouts."""
    if not isinstance(window, dict):
        return None
    probe = window.get("probe")
    if isinstance(probe, dict):
        return probe
    if any(marker in window for marker in PROBE_MARKERS):
        return window
    return None


def _probes_from_windows(windows: Iterable[object]) -> list[dict[str, Any]]:
    probes = []
    for window in windows:
        probe = _probe_from_window(window)
        if probe is not None:
            probes.append(probe)
    return probes


def _locate_payload(record: dict[str, Any]) -> dict[str, Any] | None:
    """Find a windows list and the summary block that belongs beside it.

    Returns ``None`` when the record has no recognisable window evidence. Both
    the committed top-level shape and the archived ``evidence.numericVisual``
    shape are supported.
    """
    windows = record.get("windows")
    if isinstance(windows, list):
        return {
            "windows": windows,
            "parent": record,
            "source": _as_mapping(record.get("source")),
            "coverage": _as_mapping(record.get("coverage")),
            "summaryKey": _summary_key(record),
        }

    candidates: list[dict[str, Any]] = []
    evidence = record.get("evidence")
    if isinstance(evidence, dict) and isinstance(
            evidence.get("numericVisual"), dict):
        candidates.append(evidence["numericVisual"])
    if isinstance(record.get("numericVisual"), dict):
        candidates.append(record["numericVisual"])
    if isinstance(record.get("sampledWindowSummary"), dict):
        candidates.append(record)

    for parent in candidates:
        windows = parent.get("windows")
        if not isinstance(windows, list):
            continue
        # Prefer a record-level summary block when one exists; otherwise the
        # summary lives beside the flattened windows.
        summary_parent = record if (
            isinstance(record.get("summary"), dict)
            or isinstance(record.get("sampledWindowSummary"), dict)
        ) else parent
        source = _as_mapping(parent.get("source")) or _as_mapping(
            record.get("source"))
        coverage = _as_mapping(parent.get("coverage")) or _as_mapping(
            record.get("coverage"))
        return {
            "windows": windows,
            "parent": summary_parent,
            "source": source,
            "coverage": coverage,
            "summaryKey": _summary_key(summary_parent),
        }
    return None


def _summary_key(parent: dict[str, Any]) -> str:
    if isinstance(parent.get("sampledWindowSummary"), dict):
        return "sampledWindowSummary"
    return "summary"


# ---------------------------------------------------------------------------
# Summary inputs
# ---------------------------------------------------------------------------


def _source_frame_rate(source: dict[str, Any]) -> object:
    """Mirror the engine's first-usable-frame-rate lookup."""
    for key in FRAME_RATE_KEYS:
        value = source.get(key)
        if value is not None:
            return value
    return None


def _probe_timebase(probes: list[dict[str, Any]]) -> object:
    """Read a timebase from a probe or its ``scan`` sub-document."""
    for probe in probes:
        value = probe.get("sourceTimebase")
        if value is not None:
            return value
        scan = probe.get("scan")
        if isinstance(scan, dict) and scan.get("sourceTimebase") is not None:
            return scan["sourceTimebase"]
    return None


def _sampled_seconds(
    windows: list[object], coverage: dict[str, Any], parent: dict[str, Any],
) -> float | None:
    for container in (coverage, parent):
        value = finite_float(container.get("sampledSeconds"))
        if value is not None and value > 0:
            return value
    total = 0.0
    found = False
    for window in windows:
        if not isinstance(window, dict):
            continue
        start = finite_float(window.get("startSeconds"))
        end = finite_float(window.get("endSeconds"))
        if start is not None and end is not None and end > start:
            total += end - start
            found = True
    return total if found and total > 0 else None


def _sampled_fraction(
    coverage: dict[str, Any], parent: dict[str, Any], source: dict[str, Any],
    sampled_seconds: float | None,
) -> float | None:
    for container in (coverage, parent):
        value = finite_float(container.get("fractionOfRuntime"))
        if value is not None:
            return value
    duration = finite_float(source.get("durationSeconds"))
    if sampled_seconds is not None and duration is not None and duration > 0:
        return sampled_seconds / duration
    return None


def _availability(
    probes: list[dict[str, Any]], *, sampled_seconds: float | None,
    fps: object, timebase: object,
) -> dict[str, bool]:
    """Which summary fields can be honestly recomputed from the probes."""
    has_candidates = any(
        isinstance(probe.get("cutCandidatePts"), list) for probe in probes)
    has_pairs = any(
        isinstance(probe.get("sampledFramePairs"), list) for probe in probes)
    has_counts = any(
        isinstance(probe.get("sampledWindowSummary"), dict) for probe in probes)
    has_frames = any(
        isinstance(probe.get("sampledFrames"), list) for probe in probes)
    has_timebase = timebase is not None or any(
        probe.get("sourceTimebase") is not None for probe in probes)
    has_sampled = sampled_seconds is not None and sampled_seconds > 0
    has_fps = fps is not None

    gaps = has_candidates and has_timebase
    return {
        "cutCandidates": has_counts,
        "cutCandidateRatePerMinute": has_counts and has_sampled,
        "meanDisplayLuma": has_counts,
        "meanSaturation": has_counts,
        "meanWithinShotRgbDeltaPerSecond": has_pairs,
        "sampledFrames": has_frames,
        "windowsWithCuts": has_counts,
        "medianCutGapSeconds": gaps,
        "medianCutGapFrames": gaps and has_fps,
        "minCutGapSeconds": gaps,
        "cutCandidateCount": has_candidates,
        "burstFraction": gaps,
        "withinShotPairs": has_counts or has_pairs,
        "cutSeparatedPairs": has_counts or has_pairs,
        "deltaBasisPairs": has_pairs,
        "cutsPerMinuteCi95": has_candidates and has_sampled,
        "validityFlags": gaps and has_pairs and has_sampled,
    }


def _merge_summary(
    existing: object, computed: dict[str, Any],
    recomputable: dict[str, bool],
) -> tuple[dict[str, Any], list[str]]:
    """Merge computed fields into the stored block, preserving key order."""
    stored = _as_mapping(existing)
    merged: dict[str, Any] = {}
    partial_fields: list[str] = []
    for key, value in stored.items():
        if key in computed:
            if recomputable.get(key, True):
                merged[key] = computed[key]
            else:
                merged[key] = value
                partial_fields.append(key)
        else:
            merged[key] = value
    for key, value in computed.items():
        if key in merged:
            continue
        if recomputable.get(key, True):
            merged[key] = value
        else:
            merged[key] = None
            partial_fields.append(key)
    return merged, partial_fields


# ---------------------------------------------------------------------------
# Refresh one record
# ---------------------------------------------------------------------------


def refresh_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return the refreshed record plus a small result description.

    The returned ``record`` is the same object when it is skipped, otherwise a
    shallow-updated copy whose summary block has been replaced.
    """
    payload = _locate_payload(record)
    if payload is None:
        return {
            "record": record, "status": "skipped", "partialFields": [],
            "changed": False, "reason": "no windows",
        }
    windows = payload["windows"]
    probes = _probes_from_windows(windows)
    if not probes:
        return {
            "record": record, "status": "skipped", "partialFields": [],
            "changed": False, "reason": "no usable probes",
        }

    parent = payload["parent"]
    summary_key = payload["summaryKey"]
    existing = parent.get(summary_key)
    source = payload["source"]
    coverage = payload["coverage"]

    sampled_seconds = _sampled_seconds(windows, coverage, parent)
    fps = _source_frame_rate(source)
    timebase = source.get("sourceTimebase")
    if timebase is None:
        timebase = parent.get("sourceTimebase")
    if timebase is None:
        timebase = _probe_timebase(probes)
    sampled_fraction = _sampled_fraction(
        coverage, parent, source, sampled_seconds)

    computed = summarize_probes(
        probes,
        sampled_seconds=sampled_seconds if sampled_seconds is not None else 0.0,
        fps=fps,
        timebase=timebase,
        sampled_fraction=sampled_fraction,
    )
    recomputable = _availability(
        probes, sampled_seconds=sampled_seconds, fps=fps, timebase=timebase)
    merged, partial_fields = _merge_summary(existing, computed, recomputable)
    changed = merged != _as_mapping(existing)

    if changed:
        # Mutate the freshly loaded record in place so nested summary blocks
        # (``evidence.numericVisual``) keep their position in the document.
        parent[summary_key] = merged

    return {
        "record": record,
        "status": "changed" if changed else "unchanged",
        "partialFields": partial_fields,
        "changed": changed,
        "reason": None,
    }


# ---------------------------------------------------------------------------
# Disk I/O
# ---------------------------------------------------------------------------


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def write_text_atomic(path: Path, text: str) -> Path:
    """Commit UTF-8 text via a same-directory temporary file and rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=path.name + ".",
        suffix=".tmp", delete=False)
    temporary = Path(staging.name)
    try:
        with staging:
            staging.write(text)
            staging.flush()
            os.fsync(staging.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def refresh_path(
    path: Path, *, dry_run: bool = False,
) -> dict[str, Any]:
    """Refresh one record file; write only when the payload actually changes."""
    try:
        text = path.read_text(encoding="utf-8")
        record = json.loads(text)
    except (OSError, ValueError) as exc:
        return {
            "status": "error", "error": str(exc), "partialFields": [],
            "changed": False,
        }
    if not isinstance(record, dict):
        return {
            "status": "skipped", "reason": "not a JSON object",
            "partialFields": [], "changed": False,
        }

    result = refresh_record(record)
    if result["status"] == "skipped":
        return result
    if not result["changed"]:
        return result

    output = _dump(result["record"])
    if not dry_run and output != text:
        try:
            write_text_atomic(path, output)
        except OSError as exc:
            return {
                "status": "error", "error": str(exc),
                "partialFields": result["partialFields"], "changed": False,
            }
    result["status"] = "changed"
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _record_paths(root: Path, site: str | None) -> list[tuple[str, Path]]:
    pattern = f"{site}/videos/*.json" if site else "*/videos/*.json"
    paths = []
    for path in sorted(root.glob(pattern)):
        site_name = path.parent.parent.name
        paths.append((site_name, path))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Recompute stored video-evidence summaries from probes.")
    parser.add_argument(
        "--root", type=Path, default=ROOT / "research" / "analysis",
        help="analysis root containing <site>/videos/*.json")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report what would change without writing")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="process at most N record files")
    parser.add_argument(
        "--site", default=None, help="only process this site directory")
    args = parser.parse_args(argv)

    started = time.perf_counter()
    root = args.root
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2
    if args.limit is not None and args.limit < 0:
        print("--limit must be non-negative", file=sys.stderr)
        return 2

    paths = _record_paths(root, args.site)
    if args.limit is not None:
        paths = paths[:args.limit]

    counts: dict[str, dict[str, int]] = {}
    partial_records: list[str] = []
    errors: list[str] = []
    for site_name, path in paths:
        site_counts = counts.setdefault(site_name, {
            "changed": 0, "unchanged": 0, "skipped": 0, "partial": 0,
            "errors": 0,
        })
        result = refresh_path(path, dry_run=args.dry_run)
        status = result["status"]
        if status == "error":
            site_counts["errors"] += 1
            errors.append(f"{path}: {result.get('error')}")
        elif status == "skipped":
            site_counts["skipped"] += 1
        elif status == "changed":
            site_counts["changed"] += 1
        else:
            site_counts["unchanged"] += 1
        if result.get("partialFields"):
            site_counts["partial"] += 1
            partial_records.append(
                f"{path}: {', '.join(result['partialFields'])}")

    for site_name in sorted(counts):
        site_counts = counts[site_name]
        print(
            f"{site_name}: changed={site_counts['changed']} "
            f"unchanged={site_counts['unchanged']} "
            f"skipped={site_counts['skipped']} "
            f"partial={site_counts['partial']} "
            f"errors={site_counts['errors']}")

    totals = {key: sum(c[key] for c in counts.values())
              for key in ("changed", "unchanged", "skipped", "partial",
                          "errors")}
    mode = "dry-run" if args.dry_run else "write"
    print(
        f"TOTAL ({mode}): changed={totals['changed']} "
        f"unchanged={totals['unchanged']} skipped={totals['skipped']} "
        f"partial={totals['partial']} errors={totals['errors']}")
    if partial_records:
        print("partial records:")
        for line in partial_records:
            print(f"  {line}")
    for line in errors:
        print(f"ERROR {line}", file=sys.stderr)
    elapsed = time.perf_counter() - started
    print(f"wall time: {elapsed:.3f}s")
    return 0 if totals["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
