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

from .editorial import (
    ACCELERATION_RATIO, DECELERATION_RATIO, FLICKER_OUTLIER_PER_SECOND,
)
from .probe import as_int, as_text, finite_float
from .windows import cut_validity

__all__ = [
    "IDENTITY_COUNT_KEYS", "IDENTITY_MODES", "IDENTITY_TOLERANCE_SECONDS",
    "RANKABILITY_FLAGS", "aggregate_extremes", "census_aggregate",
    "census_annotate_rows", "census_columns", "census_context_lines",
    "census_delta_text", "census_for", "census_identity", "census_lookup",
    "census_reconciliation", "census_section_lines", "comparability_block",
    "coverage_distribution", "cut_columns", "duplicate_summary",
    "editorial_aggregate", "editorial_columns", "editorial_section_lines",
    "identity_verification", "still_decode_counts", "still_decode_dimensions",
    "unique_media_rows",
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
NOT_COMPARABLE_TO = ["other sites", "other renditions",
                     "full-film claims derived from window rates"]

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
            "Window coverage is sampled, not full-film: median "
            f"{coverage.get('median')}% per record, p10 {coverage.get('p10')}%, "
            f"p90 {coverage.get('p90')}%; "
            f"{coverage.get('below20Pct')}% of rows are below 20% and "
            f"{coverage.get('below10Pct')}% below 10%; median unobserved gap "
            f"between windows is {coverage.get('gapSecondsMedian')} s. Window "
            "rates describe those windows; a full-film census, when present, "
            "is reported separately.")
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


# ---------------------------------------------------------------------------
# full-film census columns, reconciliation and aggregation
# ---------------------------------------------------------------------------

_WINDOW_RATE_KEYS = (
    "windowRate", "sampledCutCandidatesPerMinute", "cutsPerMinute",
    "windowCutsPerMinute", "cutCandidateRatePerMinute",
)
_CENSUS_ID_KEYS = ("id", "slug", "clipId", "nid", "postId", "projectId")
_OVER_25 = 0.25
_RANK_CHANGE_THRESHOLD = 5

# Reacquired-media identity, as recorded by ``scripts/census_video_cuts.py`` in
# every census record's top-level ``identityVerification`` block. The census
# driver writes ``kind`` from this vocabulary: ``strict-sha`` (byte identity),
# ``duration+resolution+codec`` (content identity for a remuxed or
# platform-transcoded delivery) and ``forced`` (the identity gate was waived).
IDENTITY_STRICT = "strict-sha"
IDENTITY_TOLERANT = "duration+resolution+codec"
IDENTITY_FORCED = "forced"
IDENTITY_KINDS = (IDENTITY_STRICT, IDENTITY_TOLERANT, IDENTITY_FORCED)
# Count keys are the ones the census index writes, so the report, the index and
# the driver summary never drift into a second vocabulary.
IDENTITY_COUNT_KEYS = ("strict-sha", "tolerant", "forced")
# Report-facing delivery modes (the ``identity`` table column).
IDENTITY_MODES = ("byte", "remux", "youtube", "forced")
# A remux moves segment/mux boundaries; half a second absorbs that without
# admitting a different edit.
IDENTITY_TOLERANCE_SECONDS = 0.5
# Method/provider vocabulary that denotes a platform-transcoded rendition whose
# codec family may differ between two downloads.
_IDENTITY_YOUTUBE_HINTS = ("ytdlp", "youtube")


def identity_verification(record: Mapping[str, Any]) -> dict[str, Any]:
    """Normalise one census record's reacquired-media identity statement.

    Reads the top-level ``identityVerification`` block and maps its recorded
    ``kind`` onto the report-facing delivery mode:

    ``strict-sha``
        ``byte`` — direct-file delivery, byte identity asserted.
    ``duration+resolution+codec``
        ``remux`` for a remuxed manifest, ``youtube`` when the acquisition
        method/provider is a platform transcoder (yt-dlp/YouTube) or the
        block already records ``codecMatched: false``.
    ``forced``
        ``forced`` — measured with the identity gate waived.

    A record with no block (written before the tolerance rules) yields
    ``kind: None`` and ``mode: None`` so callers render ``—`` rather than
    inventing an identity claim.
    """
    record = _mapping(record)
    block = _mapping(record.get("identityVerification"))
    kind = as_text(block.get("kind"))
    acquisition = _mapping(record.get("acquisition"))
    method = (as_text(acquisition.get("method")) or "").lower()
    provider = (as_text(acquisition.get("provider")) or "").lower()

    mode: str | None = None
    if kind == IDENTITY_STRICT:
        mode = "byte"
    elif kind == IDENTITY_FORCED:
        mode = "forced"
    elif kind is not None:
        platform = block.get("codecMatched") is False or any(
            hint in method or hint == provider for hint in _IDENTITY_YOUTUBE_HINTS)
        mode = "youtube" if platform else "remux"
    return {
        "kind": kind,
        "mode": mode,
        "recorded": kind is not None,
        "forced": kind == IDENTITY_FORCED,
        "reason": as_text(block.get("reason")),
        "toleranceSeconds": IDENTITY_TOLERANCE_SECONDS,
    }


def _identity_for(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Identity info for a census record or an already-annotated report row."""
    if isinstance(entry, Mapping) and "identity_kind" in entry:
        kind = as_text(entry.get("identity_kind"))
        mode = as_text(entry.get("identity"))
        return {
            "kind": kind,
            "mode": mode,
            "recorded": kind is not None,
            "forced": (entry.get("identity_forced") is True
                       or mode == "forced"),
            "reason": as_text(entry.get("identity_reason")),
            "toleranceSeconds": IDENTITY_TOLERANCE_SECONDS,
        }
    return identity_verification(entry)


def _census_identity_id(entry: Mapping[str, Any], fallback: int) -> str:
    """Record id for a raw census record (id lives under ``record``) or a row."""
    inner = _mapping(entry.get("record"))
    for candidate in (inner.get("id"), inner.get("slug"),
                      entry.get("id"), entry.get("slug")):
        text = as_text(candidate)
        if text is not None:
            return text
    return _record_id(entry, fallback)


def census_identity(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Count the records behind a census section by identity mode.

    ``counts`` uses the census index vocabulary (``strict-sha``, ``tolerant``,
    ``forced``); ``unrecorded`` counts census records with no identity block at
    all, so ``sum(counts) + unrecorded`` is the number of census records. An
    annotated report row whose ``census_present`` is false is not a census
    record and is skipped. Every ``forced`` record is named by id (with its
    reason and rate when the caller passed an annotated row) because it must
    stay out of the aggregates.
    """
    counts = {key: 0 for key in IDENTITY_COUNT_KEYS}
    modes = {mode: 0 for mode in IDENTITY_MODES}
    forced: list[dict[str, Any]] = []
    unrecorded = 0
    n = 0
    for index, entry in enumerate(records or []):
        if not isinstance(entry, Mapping):
            continue
        if entry.get("census_present") is False:
            continue
        n += 1
        info = _identity_for(entry)
        if info["kind"] is None:
            unrecorded += 1
            continue
        if info["kind"] == IDENTITY_STRICT:
            counts["strict-sha"] += 1
        elif info["kind"] == IDENTITY_FORCED:
            counts["forced"] += 1
        else:
            counts["tolerant"] += 1
        mode = info["mode"]
        if mode in modes:
            modes[mode] += 1
        if info["forced"]:
            forced.append({
                "id": _census_identity_id(entry, index),
                "reason": info["reason"],
                "fullCutsPerMinute": finite_float(entry.get("full_cuts_per_min")),
            })
    forced.sort(key=lambda item: item["id"])
    return {
        "n": n,
        "counts": counts,
        "modes": modes,
        "unrecorded": unrecorded,
        "forced": forced,
        "forcedIds": [item["id"] for item in forced],
        "toleranceSeconds": IDENTITY_TOLERANCE_SECONDS,
    }


def census_columns(record: Mapping[str, Any]) -> dict[str, Any]:
    """Report columns for one full-runtime census record.

    The census evidence shape nests the scan under ``census``; a bare scan
    block (or an already flattened row) is accepted as well. ``evidence`` is
    always ``"full-film"`` so a consumer can tell these values apart from the
    window-sampled columns without inferring it from a key name.
    """
    record = _mapping(record)
    scan = _mapping(record.get("census"))
    if not scan:
        scan = record
    summary = _mapping(scan.get("seriesSummary"))
    coverage = _mapping(record.get("coverage"))
    decoded = finite_float(coverage.get("decodeCoverageFraction"))
    if decoded is None:
        decoded = finite_float(summary.get("decodeCoverageFraction"))
    identity = identity_verification(record)
    return {
        "full_cut_count": as_int(scan.get("cutCount")),
        "full_cuts_per_min": finite_float(scan.get("cutsPerMinute")),
        "median_gap_frames": finite_float(scan.get("medianCutGapFrames")),
        "burst_fraction": finite_float(scan.get("burstFraction")),
        "strobe": scan.get("strobe") is True,
        "mean_luma": finite_float(summary.get("meanDisplayLuma")),
        "mean_saturation": finite_float(summary.get("meanSaturation")),
        "decoded_fraction": decoded,
        "identity": identity["mode"],
        "identity_kind": identity["kind"],
        "identity_forced": identity["forced"],
        "identity_reason": identity["reason"],
        "census_present": True,
        "evidence": "full-film",
    }


def editorial_columns(record: Mapping[str, Any]) -> dict[str, Any]:
    """Report columns for one record's derived ``editorial`` block.

    The block is written beside the census scan by
    ``scripts/derive_census_editorial.py``. A record without one yields
    explicit ``None`` values, so the report renders ``—`` rather than implying
    a measurement that does not exist.
    """
    record = _mapping(record)
    block = _mapping(record.get("editorial"))
    if not block:
        scan = _mapping(record.get("census")) or _mapping(record.get("scan"))
        block = _mapping(scan.get("editorial"))
    fraction = finite_float(block.get("shotsUnderHalfSecondFraction"))
    return {
        "editorial_present": bool(block),
        "shot_count": as_int(block.get("shotCount")),
        "median_shot_s": finite_float(block.get("medianShotSeconds")),
        "shots_lt_0_5s_pct": (
            None if fraction is None else _round(fraction * 100.0)),
        "pace_trend": as_text(block.get("paceTrend")),
        "pace_drift_ratio": finite_float(block.get("paceDriftRatio")),
        "flicker": finite_float(block.get("flickerLumaPerSecond")),
    }


def census_for(
    row: Mapping[str, Any], lookup: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """Resolve a row's census record through every adapter identity field."""
    if not lookup or not isinstance(row, Mapping):
        return None
    for key in _CENSUS_ID_KEYS:
        value = row.get(key)
        if value is None:
            continue
        record = lookup.get(str(value))
        if record is not None:
            return record
    return None


def census_lookup(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """Index census records by their recorded id and slug, first one wins."""
    lookup: dict[str, Mapping[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        inner = _mapping(record.get("record"))
        for value in (inner.get("id"), inner.get("slug"),
                      record.get("id"), record.get("slug")):
            text = as_text(value)
            if text is not None:
                lookup.setdefault(text, record)
    return lookup


def census_delta_text(
    window_rate: object, full_rate: object,
) -> str:
    """Render a window rate against a film rate as ``+12%`` style text."""
    window = finite_float(window_rate)
    full = finite_float(full_rate)
    if window is None or full is None or full == 0:
        return "—"
    return f"{int(round((window - full) / full * 100.0)):+d}%"


def census_annotate_rows(
    rows: Iterable[dict[str, Any]],
    lookup: Mapping[str, Mapping[str, Any]],
    *, window_key: str = "sampledCutCandidatesPerMinute",
) -> None:
    """Add ``fullCutsPerMinute`` and ``fullVsWindow`` to per-video rows.

    Rows without a census record keep explicit ``None``/``—`` values, so a
    report never implies film-level evidence it does not have. The reacquired
    media identity travels with them as ``identity`` (the delivery mode shown
    in the ``identity`` column), ``identity_kind`` (the recorded vocabulary)
    and ``identity_forced`` (true when the identity gate was waived).
    """
    for row in rows:
        if not isinstance(row, dict):
            continue
        record = census_for(row, lookup)
        if record is None:
            row["fullCutsPerMinute"] = None
            row["fullVsWindow"] = "—"
            row.update({
                "identity": None,
                "identity_kind": None,
                "identity_forced": False,
                "identity_reason": None,
                "census_present": False,
                "editorial_present": False,
                "shot_count": None,
                "median_shot_s": None,
                "shots_lt_0_5s_pct": None,
                "pace_trend": None,
                "pace_drift_ratio": None,
                "flicker": None,
            })
            continue
        columns = census_columns(record)
        row.update(columns)
        row.update(editorial_columns(record))
        row["fullCutsPerMinute"] = columns["full_cuts_per_min"]
        row["fullVsWindow"] = census_delta_text(
            row.get(window_key), columns["full_cuts_per_min"])


def census_reconciliation(
    window_rows: Iterable[Mapping[str, Any]],
    census_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare window-sampled rates with full-film census rates.

    Relative error is ``(window_rate - full_rate) / full_rate`` per record: a
    positive value means the window estimate overstates the film rate. Records
    whose full-film rate is zero are not comparable and are counted separately.
    ``rank_changes`` lists records whose position changes by more than five
    places when the same records are ranked by each rate in turn.
    """
    pairs: list[dict[str, Any]] = []
    seen: set[str] = set()
    skipped_zero = 0
    skipped_forced = 0
    for index, row in enumerate(window_rows or []):
        if not isinstance(row, Mapping):
            continue
        if _identity_for(row)["forced"]:
            # A forced measurement must not move a film-level comparison.
            skipped_forced += 1
            continue
        census = census_for(row, census_by_id)
        if census is None:
            continue
        columns = census_columns(census)
        full_rate = finite_float(columns.get("full_cuts_per_min"))
        window_rate = finite_float(
            next((value for value in (
                row.get(key) for key in _WINDOW_RATE_KEYS)
                if finite_float(value) is not None), None))
        if full_rate is None or window_rate is None:
            continue
        identifier = _record_id(row, index)
        if identifier in seen:
            continue
        seen.add(identifier)
        if full_rate == 0:
            skipped_zero += 1
            continue
        error = (window_rate - full_rate) / full_rate
        pairs.append({
            "id": identifier,
            "window_rate": _round(window_rate),
            "full_rate": _round(full_rate),
            "relative_error": _round(error),
            "abs_relative_error": _round(abs(error)),
            "direction": ("window higher" if error > 0
                          else ("window lower" if error < 0 else "equal")),
        })

    pairs.sort(key=lambda entry: entry["id"])
    window_order = sorted(
        pairs, key=lambda entry: (-entry["window_rate"], entry["id"]))
    full_order = sorted(
        pairs, key=lambda entry: (-entry["full_rate"], entry["id"]))
    window_rank = {entry["id"]: position
                   for position, entry in enumerate(window_order, start=1)}
    full_rank = {entry["id"]: position
                 for position, entry in enumerate(full_order, start=1)}
    rank_changes = []
    for entry in pairs:
        change = window_rank[entry["id"]] - full_rank[entry["id"]]
        if abs(change) > _RANK_CHANGE_THRESHOLD:
            rank_changes.append({
                "id": entry["id"],
                "window_rank": window_rank[entry["id"]],
                "full_rank": full_rank[entry["id"]],
                "position_change": change,
                "window_rate": entry["window_rate"],
                "full_rate": entry["full_rate"],
                "relative_error": entry["relative_error"],
            })
    rank_changes.sort(key=lambda entry: (-abs(entry["position_change"]),
                                         entry["id"]))

    abs_errors = sorted(entry["abs_relative_error"] for entry in pairs)
    over_25 = sorted(
        (entry for entry in pairs
         if entry["abs_relative_error"] > _OVER_25),
        key=lambda entry: (-entry["abs_relative_error"], entry["id"]))
    improved_share = (round(len(over_25) / len(pairs), 6) if pairs else None)
    return {
        "n": len(pairs),
        "skipped_zero_full_rate": skipped_zero,
        "skipped_forced": skipped_forced,
        "median_abs_relative_error": _round(
            statistics.median(abs_errors) if abs_errors else None),
        "p90_abs_relative_error": _round(_percentile(abs_errors, 0.90)),
        "max_abs_relative_error": (_round(abs_errors[-1]) if abs_errors else None),
        "improved": len(over_25),
        "improved_share": improved_share,
        "direction_counts": {
            "window_higher": sum(1 for entry in pairs
                                 if entry["relative_error"] > 0),
            "window_lower": sum(1 for entry in pairs
                                if entry["relative_error"] < 0),
        },
        "over_25pct": over_25,
        "rank_changes": rank_changes,
    }


def _rate_range(entries: list[tuple[str, float]]) -> dict[str, Any]:
    values = sorted(value for _, value in entries)
    if not values:
        return {"n": 0, "min": None, "p10": None, "median": None,
                "p90": None, "max": None, "min_id": None, "max_id": None}
    low = min(entries, key=lambda item: (item[1], item[0]))
    high = max(entries, key=lambda item: (item[1], item[0]))
    return {
        "n": len(values),
        "min": _round(values[0]),
        "p10": _round(_percentile(values, 0.10)),
        "median": _round(statistics.median(values)),
        "p90": _round(_percentile(values, 0.90)),
        "max": _round(values[-1]),
        "min_id": low[0],
        "max_id": high[0],
    }


def census_aggregate(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarise full-film cut rates, never pooling strobe and non-strobe.

    Only rows carrying ``evidence == "full-film"`` (or rows built by
    :func:`census_columns`, where the key is present) enter the aggregate. The
    main range is computed over non-strobe records only; strobe records get
    their own block and are cited by id.

    A row whose reacquired media identity was ``forced`` (the identity gate
    was waived) is excluded from **both** ranges: a measurement of media whose
    identity was not established must not move a film-level number.
    :func:`census_identity` names those records for the report.
    """
    plain: list[tuple[str, float]] = []
    strobe: list[tuple[str, float]] = []
    strobe_rows: list[dict[str, Any]] = []
    row_list = [row for row in (rows or []) if isinstance(row, Mapping)]
    for index, row in enumerate(row_list):
        info = _identity_for(row)
        if info["forced"]:
            continue
        if row.get("evidence") not in (None, "full-film"):
            continue
        rate = finite_float(row.get("full_cuts_per_min"))
        if rate is None:
            continue
        identifier = _record_id(row, index)
        if row.get("strobe") is True:
            strobe.append((identifier, rate))
            strobe_rows.append({
                "id": identifier,
                "full_cuts_per_min": _round(rate),
                "identity": info["mode"],
                "median_gap_frames": finite_float(row.get("median_gap_frames")),
                "burst_fraction": finite_float(row.get("burst_fraction")),
            })
        else:
            plain.append((identifier, rate))
    strobe_rows.sort(key=lambda entry: entry["id"])
    return {
        **_rate_range(plain),
        "strobe_count": len(strobe),
        "strobe_ids": sorted(identifier for identifier, _ in strobe),
        "strobe": _rate_range(strobe),
        "strobe_rows": strobe_rows,
        "n_all": len(plain) + len(strobe),
    }


def _fmt(value: object, digits: int = 2) -> str:
    number = finite_float(value)
    return "—" if number is None else f"{number:.{digits}f}"


def _editorial_values(row: Mapping[str, Any]) -> dict[str, Any]:
    """Read the editorial columns from a row, deriving them if absent."""
    if "editorial_present" in row:
        return {
            "present": row.get("editorial_present") is True,
            "shot_count": as_int(row.get("shot_count")),
            "median_shot_s": finite_float(row.get("median_shot_s")),
            "pace_trend": as_text(row.get("pace_trend")),
            "pace_drift_ratio": finite_float(row.get("pace_drift_ratio")),
            "flicker": finite_float(row.get("flicker")),
        }
    columns = editorial_columns(row)
    return {
        "present": columns["editorial_present"],
        "shot_count": columns["shot_count"],
        "median_shot_s": columns["median_shot_s"],
        "pace_trend": columns["pace_trend"],
        "pace_drift_ratio": columns["pace_drift_ratio"],
        "flicker": columns["flicker"],
    }


def editorial_aggregate(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarise derived editorial structure across one site's video rows.

    Shot-length statistics are computed over non-strobe records only: a strobe
    record's "shots" are frame-scale candidate intervals, not editorial shots,
    so pooling them would pull every median toward zero. Flicker outliers are
    reported separately and are **not** filtered by strobe, because strobe is
    exactly the condition a high flicker value describes.
    """
    trends = {"accelerating": 0, "steady": 0, "decelerating": 0,
              "unclassified": 0}
    shot_medians: list[float] = []
    cut_rates: list[float] = []
    shot_counts: list[int] = []
    strobe_ids: list[str] = []
    accelerating: list[dict[str, Any]] = []
    decelerating: list[dict[str, Any]] = []
    flicker_outliers: list[dict[str, Any]] = []
    n = 0
    for index, row in enumerate(rows or []):
        if not isinstance(row, Mapping):
            continue
        value = _editorial_values(row)
        if not value["present"]:
            continue
        n += 1
        identifier = _record_id(row, index)
        trend = value["pace_trend"]
        trends[trend if trend in trends else "unclassified"] += 1
        strobe = row.get("strobe") is True
        if strobe:
            strobe_ids.append(identifier)
        else:
            if value["median_shot_s"] is not None:
                shot_medians.append(value["median_shot_s"])
            rate = finite_float(row.get("full_cuts_per_min"))
            if rate is not None:
                cut_rates.append(rate)
            if value["shot_count"] is not None:
                shot_counts.append(value["shot_count"])
            ratio = value["pace_drift_ratio"]
            if ratio is not None and ratio >= ACCELERATION_RATIO:
                accelerating.append({
                    "id": identifier,
                    "pace_drift_ratio": _round(ratio),
                    "median_shot_s": _round(value["median_shot_s"]),
                })
            elif ratio is not None and ratio <= DECELERATION_RATIO:
                decelerating.append({
                    "id": identifier,
                    "pace_drift_ratio": _round(ratio),
                    "median_shot_s": _round(value["median_shot_s"]),
                })
        flicker = value["flicker"]
        if flicker is not None and flicker > FLICKER_OUTLIER_PER_SECOND:
            flicker_outliers.append({
                "id": identifier,
                "flicker": _round(flicker),
            })

    ordered = sorted(shot_medians)
    accelerating.sort(key=lambda entry: (-entry["pace_drift_ratio"],
                                         entry["id"]))
    decelerating.sort(key=lambda entry: (entry["pace_drift_ratio"],
                                         entry["id"]))
    flicker_outliers.sort(key=lambda entry: (-entry["flicker"], entry["id"]))
    return {
        "n": n,
        "non_strobe_n": len(shot_medians),
        "shot_length": {
            "n": len(ordered),
            "min": _round(ordered[0]) if ordered else None,
            "p10": _round(_percentile(ordered, 0.10)),
            "median": _round(statistics.median(ordered)) if ordered else None,
            "p90": _round(_percentile(ordered, 0.90)),
            "max": _round(ordered[-1]) if ordered else None,
        },
        "median_cut_rate": (
            _round(statistics.median(cut_rates)) if cut_rates else None),
        "shot_count_range": {
            "min": min(shot_counts) if shot_counts else None,
            "max": max(shot_counts) if shot_counts else None,
        },
        "pace_trend_counts": trends,
        "accelerating_clips": accelerating,
        "decelerating_clips": decelerating,
        "flicker_threshold": FLICKER_OUTLIER_PER_SECOND,
        "flicker_outliers": flicker_outliers,
        "strobe_count": len(strobe_ids),
        "strobe_ids": sorted(strobe_ids),
    }


def editorial_section_lines(
    editorial: Mapping[str, Any], *, site: str, digits: int = 2,
) -> list[str]:
    """Markdown lines for the derived ``## Editorial structure`` section.

    Every number is read from the stored per-record ``editorial`` blocks (via
    :func:`editorial_aggregate`), so the section is deterministic and
    recomputable offline. Strobe records are named and kept out of the
    shot-length aggregates; their candidate intervals are frame-scale, not
    editorial shots.
    """
    editorial = _mapping(editorial)
    n = as_int(editorial.get("n")) or 0
    lines: list[str] = ["## Editorial structure", ""]
    if not n:
        lines.append(
            "editorial: not present (no video record on "
            f"{site} carries a derived `editorial` block; run "
            "`python scripts/derive_census_editorial.py`).")
        lines.append("")
        return lines

    shot = _mapping(editorial.get("shot_length"))
    lines.append(
        "Derived offline from each record's stored census cut candidates and "
        "1 Hz appearance series (pure function, no media re-decode). A `shot` "
        "is the interval between consecutive detected scene changes, a lower "
        "bound on edits; `shotCount` is always candidates + 1.")
    lines.append("")
    lines.append(
        f"Shot-length distribution across {editorial.get('non_strobe_n', 0)} "
        "non-strobe clip(s), using each clip's median shot length. Strobe "
        "records are excluded because their candidate intervals are "
        "frame-scale.")
    lines.append("")
    lines.append("| statistic | median_shot_s |")
    lines.append("| --- | --- |")
    for label in ("n", "min", "p10", "median", "p90", "max"):
        value = shot.get(label)
        rendered = str(value) if label == "n" else _fmt(value, digits)
        lines.append(f"| {label} | {rendered} |")
    lines.append("")
    shot_range = _mapping(editorial.get("shot_count_range"))
    lines.append(
        "Median cut rate (non-strobe): "
        f"{_fmt(editorial.get('median_cut_rate'), digits)} cuts/min. "
        "Shot counts across clips: "
        f"{shot_range.get('min', '—')}–{shot_range.get('max', '—')}.")
    lines.append("")

    trends = _mapping(editorial.get("pace_trend_counts"))
    lines.append(
        "Pace trend, last third ÷ first third with a ±15% band: "
        f"accelerating {trends.get('accelerating', 0)}, "
        f"steady {trends.get('steady', 0)}, "
        f"decelerating {trends.get('decelerating', 0)}, "
        f"unclassified {trends.get('unclassified', 0)} (unclassified means "
        "no cut candidate in the first third, so no ratio exists).")
    lines.append("")

    for label, key, comparison in (
            ("Clips whose last third is >2× their first third",
             "accelerating_clips", ">2×"),
            ("Clips whose last third is <0.5× their first third",
             "decelerating_clips", "<0.5×")):
        entries = editorial.get(key) or []
        lines.append(f"{label} ({comparison}; non-strobe):")
        lines.append("")
        if not entries:
            lines.append("None.")
            lines.append("")
            continue
        lines.append("| id | pace_drift_ratio | median_shot_s |")
        lines.append("| --- | --- | --- |")
        for entry in entries:
            entry = _mapping(entry)
            lines.append(
                f"| {_fmt_id(entry.get('id'))} | "
                f"{_fmt(entry.get('pace_drift_ratio'), 2)} | "
                f"{_fmt(entry.get('median_shot_s'), digits)} |")
        lines.append("")

    threshold = finite_float(editorial.get("flicker_threshold"))
    outliers = editorial.get("flicker_outliers") or []
    lines.append(
        "Flicker outliers (median absolute luma delta per second above "
        f"{_fmt(threshold, 3)}; sample instability, not a flicker frequency):")
    lines.append("")
    if not outliers:
        lines.append("None.")
    else:
        lines.append("| id | flicker_luma_per_s |")
        lines.append("| --- | --- |")
        for entry in outliers:
            entry = _mapping(entry)
            lines.append(
                f"| {_fmt_id(entry.get('id'))} | "
                f"{_fmt(entry.get('flicker'), 3)} |")
    lines.append("")
    strobe_ids = editorial.get("strobe_ids") or []
    if strobe_ids:
        lines.append(
            "Strobe records excluded from the shot-length aggregates: "
            + ", ".join(f"`{_fmt_id(value)}`" for value in strobe_ids) + ".")
    else:
        lines.append(
            "No strobe record was present, so no clip was excluded from the "
            "shot-length aggregates.")
    lines.append("")
    return lines


def _fmt_id(value: object) -> str:
    text = as_text(value)
    return text if text is not None else "—"


def _census_identity_lines(identity: Mapping[str, Any]) -> list[str]:
    """Render the identity-mode breakdown and the forced exclusions."""
    counts = _mapping(identity.get("counts"))
    modes = _mapping(identity.get("modes"))
    unrecorded = as_int(identity.get("unrecorded")) or 0
    tolerance = finite_float(identity.get("toleranceSeconds"))
    tolerance = (IDENTITY_TOLERANCE_SECONDS if tolerance is None else tolerance)
    counted = {
        key: as_int(counts.get(key)) or 0 for key in IDENTITY_COUNT_KEYS}
    mode_counts = {key: as_int(modes.get(key)) or 0 for key in IDENTITY_MODES}
    lines = [
        "Reacquired-media identity, per delivery mode: "
        f"strict-sha: {counted['strict-sha']}, "
        f"tolerant: {counted['tolerant']} (duration+resolution+codec), "
        f"forced: {counted['forced']}, unrecorded: {unrecorded}. "
        "Byte identity is asserted only for direct-file sources; remuxed and "
        f"platform-transcoded sources are matched on duration ±{tolerance:g} s, "
        "resolution and codec family.",
        "",
        "By delivery, the same records read: "
        f"byte {mode_counts['byte']}, remux {mode_counts['remux']}, "
        f"youtube {mode_counts['youtube']}, forced {mode_counts['forced']}. "
        "A row whose census record carries no `identityVerification` block is "
        "counted as `unrecorded`; a row with no census record at all also "
        "shows `—` in the `identity` column.",
        "",
    ]
    forced = identity.get("forced") or []
    if forced:
        names = []
        for entry in forced:
            entry = _mapping(entry)
            reason = as_text(entry.get("reason"))
            label = f"`{_fmt_id(entry.get('id'))}`"
            names.append(f"{label} ({reason})" if reason else label)
        lines.append(
            "Excluded from every census aggregate below because identity was "
            "not established (`forced`): " + ", ".join(names) + ".")
        lines.append("")
    return lines


def census_context_lines(
    context: Mapping[str, Any], *, site: str, digits: int = 2,
) -> list[str]:
    """Render the census sections plus the derived editorial section."""
    context = _mapping(context)
    coverage = _mapping(context.get("coverage"))
    counts = _mapping(context.get("indexCounts"))
    index_counts = None
    if counts:
        index_counts = (as_int(counts.get("measured")) or 0,
                        as_int(counts.get("failed")) or 0)
    lines = census_section_lines(
        _mapping(context.get("aggregate")),
        _mapping(context.get("reconciliation")),
        coverage_n=as_int(coverage.get("records")) or 0,
        coverage_m=as_int(coverage.get("videoRecords")) or 0,
        site=site,
        decode_fraction=finite_float(coverage.get("decodeFraction")),
        index_counts=index_counts, digits=digits,
        identity=_mapping(context.get("censusIdentity")))
    lines.extend(editorial_section_lines(
        _mapping(context.get("editorial")), site=site, digits=digits))
    return lines


def census_section_lines(
    aggregate: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    *, coverage_n: int, coverage_m: int, site: str,
    decode_fraction: float | None = 1.0,
    index_counts: tuple[int, int] | None = None,
    identity: Mapping[str, Any] | None = None,
    digits: int = 2,
) -> list[str]:
    """Markdown lines for the two census sections every adapter report renders.

    ``coverage_n`` is the number of census records and ``coverage_m`` the
    number of video-measured records in the same tree. With no census records
    the helper still emits both headings and an explicit ``census: not
    present`` line, so a window-only report degrades visibly rather than
    silently.

    ``identity`` is the block from :func:`census_identity`; absent entries mean
    the tree carries no identity statement and no identity claim is rendered.
    """
    lines: list[str] = []
    if not coverage_n:
        lines.append("## Full-film census")
        lines.append("")
        detail = (f"census: not present (0 of {coverage_m} video-measured "
                  "records have a census record)")
        if index_counts is not None:
            measured, failed = index_counts
            detail += (f"; `census-index.json` reports {measured} measured "
                       f"and {failed} failed")
        lines.append(detail + ".")
        lines.append("")
        lines.append("## Census reconciliation")
        lines.append("")
        lines.append("census: not present (reconciliation needs at least one "
                     "full-film census record).")
        lines.append("")
        return lines

    share = (100.0 * coverage_n / coverage_m) if coverage_m else 0.0
    lines.append("## Full-film census")
    lines.append("")
    lines.append(
        f"Film-level evidence: {coverage_n} of {coverage_m} video-measured "
        f"records ({share:.1f}%) on {site} have a full-runtime census record. "
        "Census values are **film-level**: every cut candidate in the file was "
        "counted and the appearance series is time-weighted over the whole "
        "runtime, so `decodeCoverageFraction` is "
        f"{_fmt(decode_fraction, 6)}. The `full_cuts_per_min` column is that "
        "film-level rate; every `sampled_cut_candidates_per_min` value remains "
        "a sample of its windows.")
    lines.append("")
    lines.append(
        "Census cut candidates are still ffmpeg scene-score exceedances, not "
        "verified edits; fast movement, flashes, transitions and compression "
        "can exceed the threshold. A `strobe` record's rate describes "
        "strobe-like candidate density and is **not comparable to a cut "
        "rate**, so strobe records are excluded from the range below and "
        "reported separately.")
    lines.append("")
    identity = _mapping(identity) or _mapping(aggregate.get("censusIdentity"))
    if identity:
        lines.extend(_census_identity_lines(identity))
    lines.append("| statistic | full_cuts_per_min (non-strobe) |")
    lines.append("| --- | --- |")
    for label in ("n", "min", "p10", "median", "p90", "max"):
        value = aggregate.get(label)
        rendered = str(value) if label == "n" else _fmt(value, digits)
        lines.append(f"| {label} | {rendered} |")
    lines.append("")
    if aggregate.get("n"):
        forced_note = (
            " `forced` records are excluded as well."
            if identity.get("forcedIds") else "")
        lines.append(
            "Range endpoints: min "
            f"{_fmt(aggregate.get('min'), digits)} "
            f"(`{aggregate.get('min_id')}`), max "
            f"{_fmt(aggregate.get('max'), digits)} "
            f"(`{aggregate.get('max_id')}`); n counts non-strobe records "
            "only." + forced_note)
        lines.append("")
    strobe = aggregate.get("strobe") or {}
    if aggregate.get("strobe_count"):
        lines.append(
            f"Strobe block (never pooled with the cut-rate range above): "
            f"{aggregate.get('strobe_count')} record(s), listed by id below. "
            f"Its own range is min {_fmt(strobe.get('min'), digits)}, median "
            f"{_fmt(strobe.get('median'), digits)}, max "
            f"{_fmt(strobe.get('max'), digits)}.")
        lines.append("")
        lines.append("| strobe id | full_cuts_per_min | median_gap_frames | "
                     "burst_fraction |")
        lines.append("| --- | --- | --- | --- |")
        for entry in aggregate.get("strobe_rows") or []:
            lines.append(
                f"| {entry.get('id')} | "
                f"{_fmt(entry.get('full_cuts_per_min'), digits)} | "
                f"{_fmt(entry.get('median_gap_frames'), 1)} | "
                f"{_fmt(entry.get('burst_fraction'), 3)} |")
    else:
        lines.append("No record met the `strobe` threshold.")
    lines.append("")

    lines.append("## Census reconciliation")
    lines.append("")
    lines.append(
        "Window values are samples of the runtime; census values cover the "
        "film. Relative error is `(window_rate - full_rate) / full_rate`, so a "
        "positive value means the window sample overestimated the film and a "
        "negative value means it underestimated it.")
    lines.append("")
    lines.append(
        f"- comparable records: {reconciliation.get('n', 0)}; "
        f"skipped for a zero full-film rate: "
        f"{reconciliation.get('skipped_zero_full_rate', 0)}; "
        "skipped as `forced` (identity not established): "
        f"{reconciliation.get('skipped_forced', 0)}")
    lines.append(
        "- median |relative error|: "
        f"{_fmt(reconciliation.get('median_abs_relative_error'), 3)}; "
        "p90 |relative error|: "
        f"{_fmt(reconciliation.get('p90_abs_relative_error'), 3)}; "
        "max |relative error|: "
        f"{_fmt(reconciliation.get('max_abs_relative_error'), 3)}")
    share_text = _fmt(
        (reconciliation.get("improved_share") or 0.0) * 100.0, 1)
    lines.append(
        "- window estimate off by more than 25%: "
        f"{reconciliation.get('improved', 0)} of "
        f"{reconciliation.get('n', 0)} ({share_text}%); window higher on "
        f"{(reconciliation.get('direction_counts') or {}).get('window_higher', 0)} "
        "record(s), lower on "
        f"{(reconciliation.get('direction_counts') or {}).get('window_lower', 0)}")
    lines.append(
        "- ordering changes beyond five positions when ranked by each rate: "
        f"{len(reconciliation.get('rank_changes') or [])}")
    lines.append("")
    over = reconciliation.get("over_25pct") or []
    if over:
        lines.append("| id | window_cuts_per_min | full_cuts_per_min | "
                     "relative_error | direction |")
        lines.append("| --- | --- | --- | --- | --- |")
        for entry in over:
            lines.append(
                f"| {entry.get('id')} | {_fmt(entry.get('window_rate'), digits)} | "
                f"{_fmt(entry.get('full_rate'), digits)} | "
                f"{_fmt(entry.get('relative_error'), 3)} | "
                f"{entry.get('direction')} |")
    else:
        lines.append("No record's window estimate was off by more than 25%.")
    lines.append("")
    changes = reconciliation.get("rank_changes") or []
    if changes:
        lines.append("| id | window_rank | full_rank | position_change | "
                     "window_cuts_per_min | full_cuts_per_min |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for entry in changes[:20]:
            lines.append(
                f"| {entry.get('id')} | {entry.get('window_rank')} | "
                f"{entry.get('full_rank')} | {entry.get('position_change')} | "
                f"{_fmt(entry.get('window_rate'), digits)} | "
                f"{_fmt(entry.get('full_rate'), digits)} |")
        if len(changes) > 20:
            lines.append(f"| (+{len(changes) - 20} more rank changes in "
                         "`aggregate.json`) | | | | | |")
        lines.append("")
    return lines
