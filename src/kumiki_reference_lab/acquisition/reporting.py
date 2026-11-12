"""Site-agnostic report-assembly helpers for acquisition evidence.

Everything in this module is pure: it reads stored record dictionaries and
returns report-ready values. It contains no site vocabulary, endpoints, or
schema strings, so every adapter can share exactly the same rankability,
dedupe, coverage and comparability rules.

The helpers deliberately separate two ideas that earlier report tables
conflated:

``rankable``
    A row may only enter a cut/pacing ranking when it carries none of the
    disqualifying cut-validity flags (:data:`RANKABILITY_FLAGS`). The other
    flags (``sparse-delta-basis``, ``low-coverage``, ``no-cuts-observed``)
    qualify a row but do not by themselves make its candidate count a cut
    measure.
``unique media``
    A catalogue can list the same uploaded work more than once. Aggregates
    dedupe by media hash, while the record count before dedupe is still
    reported so the collapse is visible.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Callable, Iterable, Mapping

from .probe import as_int, as_text, finite_float
from .windows import cut_validity

__all__ = [
    "RANKABILITY_FLAGS", "aggregate_extremes", "comparability_block",
    "coverage_distribution", "cut_columns", "duplicate_summary",
    "still_decode_counts", "still_decode_dimensions", "unique_media_rows",
]

# Flags that say the candidate count is not measuring edits. A row carrying any
# of these must not enter a cut/pacing ranking.
RANKABILITY_FLAGS = frozenset({
    "non-edit-scene-change", "burst-heavy", "no-delta-basis", "short-sample",
})

COMPARABLE_WITHIN = [
    "same site",
    "same rendition",
    "same runtime band",
    "non-burst",
    ">=25% coverage",
]
NOT_COMPARABLE_TO = ["other sites", "other renditions", "full-film claims"]

_DEFAULT_DECODE_WIDTH = 160
_DEFAULT_DECODE_HEIGHT = 90
_TRAILING_DECILE = 0.9
_MAX_USABLE_SECONDS = 3600.0


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _resolve(record: Mapping[str, Any], key: str | Callable[[Mapping[str, Any]], object]) -> object:
    """Read a value by dotted path or callable (site-agnostic accessor)."""
    if callable(key):
        return key(record)
    value: object = record
    for part in key.split("."):
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)
    return value


def _record_id(record: Mapping[str, Any], fallback: int) -> str:
    for key in ("id", "slug"):
        text = as_text(record.get(key))
        if text is not None:
            return text
    return f"record-{fallback}"


def _round(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def _percentile(sorted_values: list[float], fraction: float) -> float | None:
    """Linear-interpolation percentile over an already sorted list."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[int(position)]
    weight = position - lower
    return (sorted_values[lower] * (1.0 - weight)
            + sorted_values[upper] * weight)


def _source_frame_rate(source: Mapping[str, Any]) -> object:
    for key in ("frameRate", "framesPerSecond", "nominalFrameRate"):
        value = source.get(key)
        if value is not None:
            return value
    return None


def cut_columns(record: Mapping[str, Any]) -> dict[str, Any]:
    """Report columns for one video record's cut-candidate summary.

    Stored summary keys win when present (the acquisition lane already
    derived them); otherwise the values are recomputed from the stored probe
    payloads through :func:`~.windows.cut_validity`. The result is therefore
    available even for a record written before the validity fields existed.
    """
    summary = _mapping(record.get("summary"))
    coverage = _mapping(record.get("coverage"))
    source = _mapping(record.get("source"))
    windows = record.get("windows")
    windows = windows if isinstance(windows, list) else []
    probes = [
        window.get("probe") for window in windows
        if isinstance(window, Mapping) and isinstance(window.get("probe"), Mapping)
    ]
    sampled_seconds = finite_float(coverage.get("sampledSeconds"))
    sampled_fraction = finite_float(coverage.get("fractionOfRuntime"))

    computed = cut_validity(
        probes, sampled_seconds=sampled_seconds or 0.0,
        fps=_source_frame_rate(source), timebase=source.get("sourceTimebase"),
        sampled_fraction=sampled_fraction)

    def stored(key: str, fallback: object) -> object:
        value = summary.get(key)
        return fallback if value is None else value

    candidate_count = as_int(stored(
        "cutCandidateCount", computed["cutCandidateCount"]))
    if (candidate_count == 0 and "cutCandidateCount" not in summary
            and not any(isinstance(probe.get("cutCandidatePts"), list)
                        for probe in probes)):
        # Legacy records that never stored a union: fall back to the summed
        # per-window count rather than reporting a false zero.
        legacy = as_int(summary.get("cutCandidates"))
        if legacy is not None:
            candidate_count = legacy
    candidate_count = candidate_count or 0

    rate = None
    if sampled_seconds is not None and sampled_seconds > 0:
        rate = round(candidate_count * 60.0 / sampled_seconds, 6)

    interval = stored("cutsPerMinuteCi95", computed["cutsPerMinuteCi95"])
    if isinstance(interval, (list, tuple)) and len(interval) == 2:
        interval = (finite_float(interval[0]), finite_float(interval[1]))
    else:
        interval = None

    flags = stored("validityFlags", computed["validityFlags"])
    flags = sorted(str(flag) for flag in flags) if isinstance(flags, (list, tuple)) else []
    rankable = not any(flag in RANKABILITY_FLAGS for flag in flags)

    return {
        "candidate_count": candidate_count,
        "candidates_per_min": rate,
        "ci95": interval,
        "median_gap_frames": finite_float(stored(
            "medianCutGapFrames", computed["medianCutGapFrames"])),
        "burst_fraction": finite_float(stored(
            "burstFraction", computed["burstFraction"])),
        "within_shot_pairs": as_int(stored(
            "withinShotPairs", computed["withinShotPairs"])),
        "cut_separated_pairs": as_int(stored(
            "cutSeparatedPairs", computed["cutSeparatedPairs"])),
        "delta_basis_pairs": as_int(stored(
            "deltaBasisPairs", computed["deltaBasisPairs"])),
        "validity_flags": flags,
        "rankable": rankable,
    }


def _gap_seconds(row: Mapping[str, Any]) -> float | None:
    """Unobserved seconds between two consecutive windows for one record."""
    runtime = finite_float(
        row.get("runtimeSeconds")
        if row.get("runtimeSeconds") is not None
        else row.get("durationSeconds"))
    windows = as_int(
        row.get("windowsMeasured")
        if row.get("windowsMeasured") is not None
        else row.get("windowCount"))
    sampled = finite_float(row.get("sampledSeconds"))
    if (runtime is None or runtime <= 0 or windows is None or windows < 2
            or sampled is None or sampled <= 0):
        return None
    span = sampled / windows
    usable_end = min(runtime * _TRAILING_DECILE, _MAX_USABLE_SECONDS)
    if usable_end <= span:
        return None
    stride = int((usable_end - span) // (windows - 1))
    gap = stride - span
    return round(gap, 6) if gap >= 0 else None


def coverage_distribution(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Distribution of per-record coverage percent plus the window gap.

    ``below20Pct``/``below10Pct`` are percentages of the tabulated rows (not
    fractions). ``gapSecondsMedian`` is the median unobserved gap between two
    consecutive windows, derived from runtime, window count and sampled
    seconds with the same stride rule as
    :func:`~.windows.plan_windows`.
    """
    row_list = [row for row in rows if isinstance(row, Mapping)]
    percents: list[float] = []
    gaps: list[float] = []
    for row in row_list:
        percent = finite_float(row.get("coveragePercent"))
        if percent is None:
            fraction = finite_float(row.get("fractionOfRuntime"))
            if fraction is not None:
                percent = fraction * 100.0
        if percent is not None:
            percents.append(float(percent))
        gap = _gap_seconds(row)
        if gap is not None:
            gaps.append(gap)

    ordered = sorted(percents)
    total = len(ordered)
    return {
        "min": _round(ordered[0] if ordered else None),
        "p10": _round(_percentile(ordered, 0.10)),
        "median": _round(statistics.median(ordered) if ordered else None),
        "p90": _round(_percentile(ordered, 0.90)),
        "max": _round(ordered[-1] if ordered else None),
        "below20Pct": (round(100.0 * sum(1 for value in ordered if value < 20.0)
                             / total, 6) if total else None),
        "below10Pct": (round(100.0 * sum(1 for value in ordered if value < 10.0)
                             / total, 6) if total else None),
        "gapSecondsMedian": _round(
            statistics.median(gaps) if gaps else None),
    }


def _describe_counts(counts: object, *, limit: int | None = None) -> str:
    counts = _mapping(counts)
    if not counts:
        return "none recorded"
    items = sorted(counts.items(),
                   key=lambda item: (-item[1], str(item[0])))
    if limit is not None and len(items) > limit:
        shown = items[:limit]
        text = ", ".join(f"{key} x {value}" for key, value in shown)
        return text + f", +{len(items) - limit} more"
    return ", ".join(f"{key} x {value}" for key, value in items)


def comparability_block(
    *, site: object, catalog_size: object, measured: object,
    selection_rule: object, provider_counts: object, rendition_notes: object,
    resolution_counts: object, fps_counts: object, bitrate_counts: object,
    coverage: object, duplicate_groups: object, still_overlap: object,
) -> dict[str, Any]:
    """Build the explicit non-poolability block every report renders.

    The echoed inputs are kept verbatim (as plain JSON-ready values) so an
    aggregate can be audited without re-reading the report prose. ``caveats``
    is a deterministic list of plain sentences.
    """
    coverage = _mapping(coverage)
    duplicate_groups = _mapping(duplicate_groups)
    measured_count = as_int(measured) or 0
    catalog_count = as_int(catalog_size)
    share = (round(100.0 * measured_count / catalog_count, 3)
             if catalog_count else None)
    caveats: list[str] = [
        f"{site}: poolable is false; every number describes this site's "
        "measured sample only.",
        (f"{measured_count} of {catalog_count} catalogue items were measured "
         f"({share}%) by {selection_rule}." if catalog_count
         else f"{measured_count} catalogue items were measured by "
              f"{selection_rule}; the catalogue size is unavailable."),
        "Measured rows are not a random sample: availability and recency "
        "select them, so cross-site pooling is invalid.",
        "Provider families are not interchangeable: " +
        _describe_counts(provider_counts) + ".",
    ]
    if rendition_notes:
        caveats.append(f"Renditions differ by site and record: {rendition_notes}.")
    caveats.append(
        "Measured renditions vary by resolution (" + _describe_counts(
            resolution_counts, limit=8)
        + "), frame rate (" + _describe_counts(fps_counts, limit=8)
        + ") and bitrate (" + _describe_counts(bitrate_counts, limit=8)
        + "), so the sample is not a controlled transform.")
    if coverage.get("median") is None and coverage.get("below20Pct") is None:
        caveats.append(
            "Coverage is not applicable: this lane measures no video runtime, "
            "so no sampled fraction or window gap exists.")
    else:
        caveats.append(
            "Coverage is sampled, not full-film: median "
            f"{coverage.get('median')}% per record, p10 {coverage.get('p10')}%, "
            f"p90 {coverage.get('p90')}%; "
            f"{coverage.get('below20Pct')}% of rows are below 20% and "
            f"{coverage.get('below10Pct')}% below 10%; median unobserved gap "
            f"between windows is {coverage.get('gapSecondsMedian')} s.")
    caveats.append(
        f"{duplicate_groups.get('extraRecords', 0)} extra record(s) in "
        f"{duplicate_groups.get('groups', 0)} duplicate group(s) share media; "
        f"unique media after dedupe is "
        f"{duplicate_groups.get('uniqueMedia')}.")
    caveats.append(f"Still/video overlap: {still_overlap}.")
    return {
        "site": site,
        "poolable": False,
        "catalogSize": catalog_size,
        "measured": measured,
        "selectionRule": selection_rule,
        "providerCounts": dict(provider_counts) if isinstance(
            provider_counts, Mapping) else provider_counts,
        "renditionNotes": rendition_notes,
        "resolutionCounts": dict(resolution_counts) if isinstance(
            resolution_counts, Mapping) else resolution_counts,
        "fpsCounts": dict(fps_counts) if isinstance(fps_counts, Mapping) else fps_counts,
        "bitrateCounts": dict(bitrate_counts) if isinstance(
            bitrate_counts, Mapping) else bitrate_counts,
        "coverage": coverage,
        "duplicateGroups": duplicate_groups,
        "stillOverlap": still_overlap,
        "comparableWithin": list(COMPARABLE_WITHIN),
        "notComparableTo": list(NOT_COMPARABLE_TO),
        "caveats": caveats,
    }


def duplicate_summary(
    records: Iterable[Mapping[str, Any]], sha_key: str | Callable[[Mapping[str, Any]], object],
) -> dict[str, Any]:
    """Summarise records sharing a media hash.

    ``sha_key`` is a dotted path (``"source.mediaSha256"``) or a callable.
    Records without a hash stay unique and are never grouped together.
    ``groupsDetail`` lists only groups with more than one member.
    """
    entries: list[tuple[str | None, str]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            continue
        sha = as_text(_resolve(record, sha_key))
        entries.append((sha, _record_id(record, index)))

    buckets: dict[str, list[str]] = {}
    for sha, identifier in entries:
        if sha is not None:
            buckets.setdefault(sha, []).append(identifier)

    detail = [
        {"id": sha, "members": sorted(members)}
        for sha, members in sorted(buckets.items()) if len(members) > 1
    ]
    extra = sum(len(group["members"]) - 1 for group in detail)
    return {
        "groups": len(detail),
        "extraRecords": extra,
        "uniqueMedia": len(entries) - extra,
        "groupsDetail": detail,
    }


def unique_media_rows(
    rows: Iterable[Mapping[str, Any]], *, key: str = "mediaSha256",
) -> list[Mapping[str, Any]]:
    """Keep the first row per media hash; rows without a hash stay unique."""
    seen: set[str] = set()
    unique: list[Mapping[str, Any]] = []
    for row in rows:
        sha = as_text(row.get(key))
        if sha is not None and sha in seen:
            continue
        if sha is not None:
            seen.add(sha)
        unique.append(row)
    return unique


def aggregate_extremes(
    rows: Iterable[Mapping[str, Any]], key: str, *,
    id_key: str = "id", gate: bool = False,
    rankable_key: str = "rankable",
    flags_key: str = "validityFlags",
) -> dict[str, Any]:
    """Annotated min/max of one metric, optionally gated to rankable rows.

    Every extreme names its record id and its validity flags, so an aggregate
    maximum is never printed without attribution. When ``gate`` is true,
    non-rankable rows are excluded and their count is returned.
    """
    row_list = [row for row in rows if isinstance(row, Mapping)]

    def entry_id(row: Mapping[str, Any], index: int) -> str:
        if id_key and row.get(id_key) is not None:
            text = as_text(row.get(id_key))
            if text is not None:
                return text
        return _record_id(row, index)

    valued = []
    excluded_entries = []
    excluded = 0
    for index, row in enumerate(row_list):
        value = finite_float(row.get(key))
        if value is None:
            continue
        flags = row.get(flags_key)
        flags = [str(flag) for flag in flags] if isinstance(flags, (list, tuple)) else []
        rankable = row.get(rankable_key) is not False
        if gate and not rankable:
            excluded += 1
            excluded_entries.append({
                "id": entry_id(row, index), "value": _round(value),
                "validityFlags": sorted(flags)})
            continue
        valued.append((value, entry_id(row, index), sorted(flags)))

    valued.sort(key=lambda item: (item[0], item[1]))
    excluded_entries.sort(key=lambda entry: (-entry["value"], entry["id"]))
    def entry(item: tuple[float, str, list[str]] | None) -> dict[str, Any] | None:
        if item is None:
            return None
        return {"id": item[1], "value": _round(item[0]), "validityFlags": item[2]}

    return {
        "metric": key,
        "n": len(valued),
        "gate": gate,
        "excludedNonRankable": excluded,
        "excluded": excluded_entries,
        "median": _round(statistics.median([item[0] for item in valued])
                         if valued else None),
        "min": entry(valued[0] if valued else None),
        "max": entry(valued[-1] if valued else None),
    }


def coverage_lines(distribution: Mapping[str, Any]) -> list[str]:
    """Markdown lines for a ``coverage_distribution`` result."""
    def number(value: object) -> str:
        return "—" if value is None else f"{value:.1f}"

    return [
        "| statistic | coverage_pct |",
        "| --- | --- |",
        f"| min | {number(distribution.get('min'))} |",
        f"| p10 | {number(distribution.get('p10'))} |",
        f"| median | {number(distribution.get('median'))} |",
        f"| p90 | {number(distribution.get('p90'))} |",
        f"| max | {number(distribution.get('max'))} |",
        f"| below 20% | {number(distribution.get('below20Pct'))}% |",
        f"| below 10% | {number(distribution.get('below10Pct'))}% |",
        f"| median unobserved gap between windows | "
        f"{number(distribution.get('gapSecondsMedian'))} s |",
    ]


def comparability_lines(block: Mapping[str, Any]) -> list[str]:
    """Markdown lines for a ``comparability_block`` result."""
    def items(value: object) -> str:
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value)
        return str(value)

    lines = [
        f"- poolable: `{str(block.get('poolable')).lower()}`",
        f"- comparable within: {items(block.get('comparableWithin'))}",
        f"- not comparable to: {items(block.get('notComparableTo'))}",
        "",
        "Caveats:",
        "",
    ]
    for caveat in block.get("caveats") or []:
        lines.append(f"- {caveat}")
    return lines


def extreme_text(entry: Mapping[str, Any] | None, *, digits: int = 2) -> str:
    """Render one annotated extreme as ``value (record; flags)``."""
    if not entry:
        return "—"
    value = entry.get("value")
    number = "—" if value is None else f"{value:.{digits}f}"
    flags = entry.get("validityFlags") or []
    flag_text = ", ".join(str(flag) for flag in flags) if flags else "—"
    return f"{number} ({entry.get('id')}; {flag_text})"


def excluded_leaders_lines(
    extremes: Mapping[str, Any], *, digits: int = 2, limit: int = 5,
    metric: str = "value",
) -> list[str]:
    """Markdown lines naming the non-rankable records kept out of an aggregate."""
    entries = (extremes or {}).get("excluded") or []
    if not entries:
        return []
    lines = [
        "Excluded as non-rankable (largest first):",
        "",
        f"| record | {metric} | validity |",
        "| --- | --- | --- |",
    ]
    for entry in entries[:limit]:
        value = entry.get("value")
        number = "—" if value is None else f"{value:.{digits}f}"
        flags = entry.get("validityFlags") or []
        flag_text = ", ".join(str(flag) for flag in flags) if flags else "—"
        lines.append(f"| {entry.get('id')} | {number} | {flag_text} |")
    return lines


def still_decode_counts(
    records: Iterable[Mapping[str, Any]], *, still_key: str = "still",
) -> dict[str, int]:
    """Count ``source WxH -> decode WxH`` pairs across still records."""
    counts: dict[str, int] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        still = _mapping(record.get(still_key))
        width = as_int(still.get("imageWidth"))
        height = as_int(still.get("imageHeight"))
        decode = still_decode_dimensions(still)
        if not width or not height or not decode["width"] or not decode["height"]:
            continue
        key = f"{width}x{height} -> {decode['width']}x{decode['height']}"
        counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def still_decode_dimensions(
    still: Mapping[str, Any], *, max_width: int = _DEFAULT_DECODE_WIDTH,
    max_height: int = _DEFAULT_DECODE_HEIGHT,
) -> dict[str, Any]:
    """Return the size a still was measured at, flagging a derivation.

    Reads ``still.decodeWidth``/``decodeHeight`` when the record stored them.
    Otherwise applies the same aspect-preserving ``160x90`` fit used by the
    still decoder (``force_original_aspect_ratio=decrease``).
    """
    stored_width = as_int(still.get("decodeWidth"))
    stored_height = as_int(still.get("decodeHeight"))
    if (stored_width is not None and stored_height is not None
            and stored_width > 0 and stored_height > 0):
        return {"width": stored_width, "height": stored_height, "derived": False}

    source_width = as_int(still.get("imageWidth"))
    source_height = as_int(still.get("imageHeight"))
    if not source_width or not source_height or source_width <= 0 or source_height <= 0:
        return {"width": None, "height": None, "derived": True}
    scale = min(max_width / source_width, max_height / source_height)
    width = max(2, min(max_width, int(source_width * scale + 0.5)))
    height = max(2, min(max_height, int(source_height * scale + 0.5)))
    return {"width": width, "height": height, "derived": True}
