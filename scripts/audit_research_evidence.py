"""Offline, schema-agnostic audit of on-disk research evidence records.

The auditor walks site trees under ``--root`` (each a directory containing a
``videos/`` and/or ``stills/`` folder), detects each record family from its
``schemaVersion`` string, and checks JSON shape, identity, window arithmetic,
internal consistency, cross-record duplicates, still quality, and index/tree
reconciliation. It never downloads anything.

Integrity violations (schema, identity, window arithmetic, consistency,
histogram, unreadable JSON, unknown schema) are errors. Duplicate media is a
warning: the source catalogues legitimately list one work under several
categories or sites, and every work is expected to have both video and still
evidence. Duplicate findings are aggregated one-per-group and classified as
``same-media-same-site-same-family``, ``same-media-cross-site`` or
``same-media-cross-family``; pass ``--strict-duplicates`` to promote them back
to errors.

Only the Python standard library is used. Run with::

    python scripts/audit_research_evidence.py --root research/analysis
    python scripts/audit_research_evidence.py --root research/analysis \
        --json-out /tmp/audit.json [--strict-duplicates]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:  # match the other research_* adapters
    sys.path.insert(0, str(ROOT / "src"))

# ---------------------------------------------------------------------------
# Documented vocabularies and tolerances
# ---------------------------------------------------------------------------

SCHEMA_RE = re.compile(
    r"^kumiki\.(?P<site>[a-z0-9][a-z0-9-]*)-(?P<family>video|still)"
    r"-evidence\.v(?P<version>\d+)$"
)

IDENTITY_KEYS = ("id", "postId", "projectId", "nid", "clipId")

VIDEO_TOP_KEYS = (
    "source", "acquisition", "coverage", "windows", "summary",
    "evidenceStatus", "rightsStatus", "limits", "generatedAt",
)
STILL_TOP_KEYS = (
    "still", "acquisition", "coverage", "evidenceStatus", "limits",
    "generatedAt",
)

DOCUMENTED_PAIR_STATUSES = frozenset({
    "rgb-image-difference-proxy",
    "cut-candidate-between-samples",
})

DOCUMENTED_HUE_FAMILIES = frozenset({
    "neutral", "red", "orange", "yellow", "green", "cyan", "blue",
    "purple", "magenta",
})

STILL_METRIC_RANGES = (
    "meanDisplayLumaProxy",
    "displayLumaStdDev",
    "meanSaturationProxy",
    "shadowPixelFraction",
    "brightPixelFraction",
    "edgeDensityProxy",
)

DUPLICATE_CLASS_SAME_SITE = "same-media-same-site-same-family"
DUPLICATE_CLASS_CROSS_SITE = "same-media-cross-site"
DUPLICATE_CLASS_CROSS_FAMILY = "same-media-cross-family"
DUPLICATE_CLASSES = (
    DUPLICATE_CLASS_SAME_SITE,
    DUPLICATE_CLASS_CROSS_SITE,
    DUPLICATE_CLASS_CROSS_FAMILY,
)
DUPLICATE_RULES = frozenset({
    "duplicate.source-sha256",
    "duplicate.media-cross-family",
})

MEDIA_EXTENSIONS = (
    ".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".m2ts", ".ts",
    ".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg",
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff",
)

# Stored numbers are rounded to six decimal places; arithmetic tolerance only
# needs to absorb that rounding and normal float associativity noise.
ARITHMETIC_TOLERANCE = 2e-5
COVERAGE_TOLERANCE = 0.005  # 0.5 percentage points
WINDOW_SPAN_TOLERANCE = 0.01
IMAGE_BYTES_MIN = 1024
IMAGE_BYTES_MAX = 16 * 1024 * 1024

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LOCAL_PATH_RE = re.compile(
    r"^(?:/Users/|/private/|/tmp/|/var/|/Volumes/|/home/|/root/|/mnt/|"
    r"/media/|\./|\.\./|file:|[A-Za-z]:[\\/])")
URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _finding(
    rule: str, severity: str, path: str, detail: str, **extra: Any,
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "rule": rule,
        "severity": severity,
        "path": path,
        "detail": detail,
    }
    finding.update(extra)
    return finding


def _is_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _is_positive_number(value: Any) -> bool:
    return _is_number(value) and value > 0


def _short(value: Any, limit: int = 80) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _walk(node: Any) -> Iterable[tuple[str, Any]]:
    """Yield ``(key, value)`` for every dict entry, recursively."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _walk_strings(node: Any) -> Iterable[str]:
    if isinstance(node, dict):
        for value in node.values():
            yield from _walk_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_strings(value)
    elif isinstance(node, str):
        yield node


def _local_media_paths(record: Any) -> list[str]:
    found = []
    for value in _walk_strings(record):
        if URL_SCHEME_RE.match(value):
            continue
        if not value.lower().endswith(MEDIA_EXTENSIONS):
            continue
        if LOCAL_PATH_RE.match(value) or "/" in value or "\\" in value:
            found.append(value)
    return found


def _identity_key(record: dict[str, Any]) -> str | None:
    for key in IDENTITY_KEYS:
        if key in record and record[key] is not None:
            return key
    return None


def _identity_value(record: dict[str, Any]) -> Any:
    key = _identity_key(record)
    return record.get(key) if key else None


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, f"{type(error).__name__}: {error}"


# ---------------------------------------------------------------------------
# Record checks
# ---------------------------------------------------------------------------


def _check_schema(record: dict[str, Any], rel: str) -> tuple[str | None, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    schema = record.get("schemaVersion")
    if not isinstance(schema, str) or not schema.strip():
        findings.append(_finding(
            "schema.missing", "error", rel,
            "missing or blank schemaVersion"))
        return None, findings
    match = SCHEMA_RE.match(schema.strip())
    if match is None:
        findings.append(_finding(
            "schema.unknown", "error", rel,
            f"unrecognised schemaVersion {_short(schema)}"))
        return None, findings

    family = match.group("family")
    expected = VIDEO_TOP_KEYS if family == "video" else STILL_TOP_KEYS
    missing = [key for key in expected if key not in record]
    if missing:
        findings.append(_finding(
            "schema.missing-keys", "error", rel,
            "missing top-level keys: " + ", ".join(missing)))
    if _identity_key(record) is None:
        findings.append(_finding(
            "schema.missing-identity", "error", rel,
            "no identity key from " + ", ".join(IDENTITY_KEYS)))
    if not isinstance(record.get("slug"), str) or not record["slug"].strip():
        findings.append(_finding(
            "schema.missing-identity", "error", rel,
            "missing or blank slug"))
    return family, findings


def _check_video_identity(record: dict[str, Any], rel: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    source = record.get("source")
    if not isinstance(source, dict):
        findings.append(_finding(
            "identity.source", "error", rel, "source is not an object"))
        source = {}

    sha = source.get("mediaSha256")
    if not isinstance(sha, str) or SHA256_RE.fullmatch(sha) is None:
        findings.append(_finding(
            "identity.source-sha256", "error", rel,
            f"invalid mediaSha256 {_short(sha)}"))

    duration = source.get("durationSeconds")
    if not _is_positive_number(duration):
        findings.append(_finding(
            "identity.duration", "error", rel,
            f"non-positive/invalid durationSeconds {_short(duration)}"))

    resolution = source.get("resolution")
    if (not isinstance(resolution, list) or len(resolution) != 2
            or not all(_is_positive_number(value) for value in resolution)):
        findings.append(_finding(
            "identity.resolution", "error", rel,
            f"invalid resolution {_short(resolution)}"))

    retained = [(key, value) for key, value in _walk(record)
                if key == "mediaRetained" and value is not False]
    for _, value in retained:
        findings.append(_finding(
            "identity.media-retained", "error", rel,
            f"mediaRetained must be absent or false, found {_short(value)}"))

    paths = _local_media_paths(record)
    for value in paths:
        findings.append(_finding(
            "identity.media-path", "error", rel,
            f"local media path referenced: {_short(value)}"))
    return findings


def _check_still_identity(record: dict[str, Any], rel: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    still = record.get("still")
    if not isinstance(still, dict):
        findings.append(_finding(
            "identity.still", "error", rel, "still is not an object"))
        still = {}

    sha = still.get("imageSha256")
    if not isinstance(sha, str) or SHA256_RE.fullmatch(sha) is None:
        findings.append(_finding(
            "identity.image-sha256", "error", rel,
            f"invalid imageSha256 {_short(sha)}"))

    for key in ("imageWidth", "imageHeight"):
        value = still.get(key)
        if not _is_positive_number(value):
            findings.append(_finding(
                "identity.image-dimensions", "error", rel,
                f"non-positive/invalid {key} {_short(value)}"))

    size = still.get("imageBytes")
    if not _is_positive_number(size):
        findings.append(_finding(
            "identity.image-bytes", "error", rel,
            f"non-positive/invalid imageBytes {_short(size)}"))

    acquisition = record.get("acquisition")
    retained = acquisition.get("imageRetained") if isinstance(acquisition, dict) else None
    if retained is not False:
        findings.append(_finding(
            "identity.image-retained", "error", rel,
            f"imageRetained must be false, found {_short(retained)}"))

    coverage = record.get("coverage")
    frame_flag = coverage.get("isSourceVideoFrame") if isinstance(coverage, dict) else None
    if not isinstance(frame_flag, bool):
        findings.append(_finding(
            "identity.is-source-video-frame", "error", rel,
            f"coverage.isSourceVideoFrame must be boolean, found {_short(frame_flag)}"))
    return findings


def _window_appearance_averages(probe: dict[str, Any]) -> tuple[float | None, float | None]:
    frames = probe.get("sampledFrames")
    if not isinstance(frames, list) or not frames:
        return None, None
    luma: list[float] = []
    saturation: list[float] = []
    for frame in frames:
        appearance = frame.get("appearance") if isinstance(frame, dict) else None
        if not isinstance(appearance, dict):
            continue
        luma_value = appearance.get("meanDisplayLumaProxy")
        saturation_value = appearance.get("meanSaturationProxy")
        if _is_number(luma_value):
            luma.append(luma_value)
        if _is_number(saturation_value):
            saturation.append(saturation_value)
    return (
        sum(luma) / len(luma) if luma else None,
        sum(saturation) / len(saturation) if saturation else None,
    )


def _window_pair_averages(probe: dict[str, Any]) -> tuple[float | None, int, int]:
    pairs = probe.get("sampledFramePairs")
    if not isinstance(pairs, list):
        return None, 0, 0
    within: list[float] = []
    cut_separated = 0
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        if pair.get("status") == "cut-candidate-between-samples":
            cut_separated += 1
        delta = pair.get("meanAbsoluteDisplayRgbDelta")
        if _is_number(delta):
            within.append(delta)
    return (
        sum(within) / len(within) if within else None,
        len(within),
        cut_separated,
    )


def _check_window_arithmetic(
    window: dict[str, Any], probe: dict[str, Any], rel: str,
    index: int,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    summary = probe.get("sampledWindowSummary")
    if not isinstance(summary, dict):
        return findings
    where = f"window[{index}]"

    calculated_luma, calculated_saturation = _window_appearance_averages(probe)
    for rule, field, calculated in (
        ("arithmetic.window-luma", "meanSampledDisplayLumaProxy", calculated_luma),
        ("arithmetic.window-saturation", "meanSampledSaturationProxy",
         calculated_saturation),
    ):
        if calculated is None:
            continue
        stored = summary.get(field)
        if not _is_number(stored) or abs(stored - calculated) > ARITHMETIC_TOLERANCE:
            findings.append(_finding(
                rule, "error", rel,
                f"{where} {field} stored={_short(stored)} recomputed={calculated:.6f}"))

    calculated_delta, within_count, cut_separated = _window_pair_averages(probe)
    if calculated_delta is not None:
        stored = summary.get("meanWithinShotDisplayRgbDelta")
        if (not _is_number(stored)
                or abs(stored - calculated_delta) > ARITHMETIC_TOLERANCE):
            findings.append(_finding(
                "arithmetic.window-delta", "error", rel,
                f"{where} meanWithinShotDisplayRgbDelta stored={_short(stored)} "
                f"recomputed={calculated_delta:.6f}"))
    stored_within = summary.get("withinShotComparedPairs")
    if stored_within != within_count:
        findings.append(_finding(
            "arithmetic.window-within-pairs", "error", rel,
            f"{where} withinShotComparedPairs stored={_short(stored_within)} "
            f"recomputed={within_count}"))
    stored_cut_pairs = summary.get("cutSeparatedPairs")
    if stored_cut_pairs != cut_separated:
        findings.append(_finding(
            "arithmetic.window-cut-pairs", "error", rel,
            f"{where} cutSeparatedPairs stored={_short(stored_cut_pairs)} "
            f"recomputed={cut_separated}"))

    cuts = probe.get("cutCandidatePts")
    cut_count = len(cuts) if isinstance(cuts, list) else 0
    stored_cuts = summary.get("cutCandidateCountBetweenFirstAndLastSample")
    if stored_cuts != cut_count:
        findings.append(_finding(
            "arithmetic.window-cut-count", "error", rel,
            f"{where} cutCandidateCount stored={_short(stored_cuts)} "
            f"recomputed={cut_count}"))

    scan = probe.get("scan")
    requested = scan.get("requestedSeconds") if isinstance(scan, dict) else None
    if _is_positive_number(requested):
        stored_rate = summary.get("cutCandidateRatePerRequestedMinute")
        calculated_rate = cut_count * 60.0 / requested
        if (not _is_number(stored_rate)
                or abs(stored_rate - calculated_rate) > 1e-4):
            findings.append(_finding(
                "arithmetic.window-cut-rate", "error", rel,
                f"{where} cutCandidateRate stored={_short(stored_rate)} "
                f"recomputed={calculated_rate:.6f}"))

        start = window.get("startSeconds")
        end = window.get("endSeconds")
        if _is_number(start) and _is_number(end):
            span = end - start
            if abs(span - requested) > WINDOW_SPAN_TOLERANCE:
                findings.append(_finding(
                    "arithmetic.window-span", "error", rel,
                    f"{where} span={span:.6f} requestedSeconds={requested:.6f}"))
    return findings


def _check_coverage(record: dict[str, Any], rel: str) -> list[dict[str, str]]:
    coverage = record.get("coverage")
    source = record.get("source")
    if not isinstance(coverage, dict) or not isinstance(source, dict):
        return []
    measured = coverage.get("windowsMeasured")
    window_seconds = coverage.get("windowSeconds")
    duration = source.get("durationSeconds")
    if (not _is_positive_number(measured)
            or not _is_positive_number(window_seconds)
            or not _is_positive_number(duration)):
        return []
    calculated = measured * window_seconds / duration
    stored = coverage.get("fractionOfRuntime")
    if not _is_number(stored) or abs(stored - calculated) > COVERAGE_TOLERANCE:
        return [_finding(
            "arithmetic.coverage-fraction", "error", rel,
            f"fractionOfRuntime stored={_short(stored)} "
            f"recomputed={calculated:.6f} "
            f"({measured} windows x {window_seconds}s / {duration}s)")]
    return []


def _check_record_summary(
    record: dict[str, Any], rel: str,
) -> list[dict[str, str]]:
    summary = record.get("summary")
    windows = record.get("windows")
    coverage = record.get("coverage")
    if not isinstance(summary, dict) or not isinstance(windows, list):
        return []
    probes = [window.get("probe") for window in windows
              if isinstance(window, dict) and isinstance(window.get("probe"), dict)]
    if not probes:
        return []

    cuts = 0
    windows_with_cuts = 0
    sampled_frames = 0
    luma: list[float] = []
    saturation: list[float] = []
    deltas_per_second: list[float] = []
    for probe in probes:
        window_summary = probe.get("sampledWindowSummary")
        if isinstance(window_summary, dict):
            cut_value = window_summary.get("cutCandidateCountBetweenFirstAndLastSample")
            if isinstance(cut_value, int) and not isinstance(cut_value, bool):
                cuts += cut_value
                windows_with_cuts += int(cut_value > 0)
            luma_value = window_summary.get("meanSampledDisplayLumaProxy")
            if _is_number(luma_value):
                luma.append(luma_value)
            saturation_value = window_summary.get("meanSampledSaturationProxy")
            if _is_number(saturation_value):
                saturation.append(saturation_value)
        frames = probe.get("sampledFrames")
        if isinstance(frames, list):
            sampled_frames += len(frames)
        pairs = probe.get("sampledFramePairs")
        if isinstance(pairs, list):
            for pair in pairs:
                if not isinstance(pair, dict):
                    continue
                value = pair.get("meanAbsoluteDisplayRgbDeltaPerSecond")
                if _is_number(value):
                    deltas_per_second.append(value)

    expected: dict[str, Any] = {
        "cutCandidates": cuts,
        "windowsWithCuts": windows_with_cuts,
        "sampledFrames": sampled_frames,
    }
    if luma:
        expected["meanDisplayLuma"] = sum(luma) / len(luma)
    if saturation:
        expected["meanSaturation"] = sum(saturation) / len(saturation)
    if deltas_per_second:
        expected["meanWithinShotRgbDeltaPerSecond"] = (
            sum(deltas_per_second) / len(deltas_per_second))
    if isinstance(coverage, dict):
        sampled_seconds = coverage.get("sampledSeconds")
        if _is_positive_number(sampled_seconds):
            expected["cutCandidateRatePerMinute"] = cuts * 60.0 / sampled_seconds

    findings: list[dict[str, str]] = []
    for field, calculated in expected.items():
        stored = summary.get(field)
        tolerance = ARITHMETIC_TOLERANCE if isinstance(calculated, float) else 0
        if (not _is_number(stored)
                or abs(stored - calculated) > tolerance):
            findings.append(_finding(
                "arithmetic.record-summary", "error", rel,
                f"summary {field} stored={_short(stored)} "
                f"recomputed={calculated}"))
    return findings


def _check_window_consistency(
    record: dict[str, Any], rel: str,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    windows = record.get("windows")
    if not isinstance(windows, list):
        return findings

    previous_end: float | None = None
    for index, window in enumerate(windows):
        if not isinstance(window, dict):
            findings.append(_finding(
                "consistency.window-shape", "error", rel,
                f"window[{index}] is not an object"))
            continue
        start = window.get("startSeconds")
        end = window.get("endSeconds")
        if not _is_number(start) or not _is_number(end):
            findings.append(_finding(
                "consistency.window-bounds", "error", rel,
                f"window[{index}] invalid start/end {_short(start)}..{_short(end)}"))
            continue
        if end <= start:
            findings.append(_finding(
                "consistency.window-bounds", "error", rel,
                f"window[{index}] endSeconds <= startSeconds"))
        if previous_end is not None and start < previous_end:
            findings.append(_finding(
                "consistency.window-overlap", "error", rel,
                f"window[{index}] starts at {start} before previous end {previous_end}"))
        previous_end = end

        probe = window.get("probe")
        if not isinstance(probe, dict):
            continue
        where = f"window[{index}]"

        timebase = probe.get("sourceTimebase")
        numerator = timebase.get("numerator") if isinstance(timebase, dict) else None
        denominator = timebase.get("denominator") if isinstance(timebase, dict) else None
        valid_timebase = (_is_positive_number(numerator)
                          and _is_positive_number(denominator))

        cuts = probe.get("cutCandidatePts")
        if isinstance(cuts, list):
            for position, pts in enumerate(cuts):
                if not isinstance(pts, int) or isinstance(pts, bool):
                    findings.append(_finding(
                        "consistency.cut-pts-type", "error", rel,
                        f"{where} cutCandidatePts[{position}] is not an int: "
                        f"{_short(pts)}"))
                    continue
                if valid_timebase:
                    seconds = pts * numerator / denominator
                    if not (start - 1e-6 <= seconds <= end + 1e-6):
                        findings.append(_finding(
                            "consistency.cut-pts-bounds", "error", rel,
                            f"{where} cut PTS {pts} = {seconds:.6f}s outside "
                            f"[{start}, {end}]"))

        frames = probe.get("sampledFrames")
        if isinstance(frames, list):
            for frame_index, frame in enumerate(frames):
                appearance = frame.get("appearance") if isinstance(frame, dict) else None
                if not isinstance(appearance, dict):
                    findings.append(_finding(
                        "consistency.appearance-range", "error", rel,
                        f"{where} sampledFrames[{frame_index}] has no appearance object"))
                    continue
                bad = _first_out_of_range(appearance)
                if bad is not None:
                    findings.append(_finding(
                        "consistency.appearance-range", "error", rel,
                        f"{where} sampledFrames[{frame_index}] {bad}"))
                    break

        pairs = probe.get("sampledFramePairs")
        if isinstance(pairs, list):
            for pair_index, pair in enumerate(pairs):
                status = pair.get("status") if isinstance(pair, dict) else None
                if status not in DOCUMENTED_PAIR_STATUSES:
                    findings.append(_finding(
                        "consistency.pair-status", "error", rel,
                        f"{where} sampledFramePairs[{pair_index}] status "
                        f"{_short(status)} not documented"))
    return findings


def _first_out_of_range(node: Any, path: str = "") -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            bad = _first_out_of_range(value, f"{path}.{key}" if path else key)
            if bad is not None:
                return bad
    elif isinstance(node, list):
        for index, value in enumerate(node):
            bad = _first_out_of_range(value, f"{path}[{index}]")
            if bad is not None:
                return bad
    elif isinstance(node, bool):
        return f"{path} is boolean"
    elif isinstance(node, (int, float)):
        if not math.isfinite(node) or not 0.0 <= node <= 1.0:
            return f"{path}={node!r} outside [0,1]"
    return None


def _check_still_quality(record: dict[str, Any], rel: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    still = record.get("still")
    if not isinstance(still, dict):
        return findings
    metrics = still.get("metrics")
    if not isinstance(metrics, dict):
        findings.append(_finding(
            "still.metrics", "error", rel, "still.metrics is not an object"))
        return findings

    histogram = metrics.get("lumaHistogram")
    if not isinstance(histogram, list) or len(histogram) != 5:
        findings.append(_finding(
            "still.histogram-shape", "error", rel,
            f"lumaHistogram must have 5 buckets, found {_short(histogram)}"))
    else:
        if any(not _is_number(value) for value in histogram):
            findings.append(_finding(
                "still.histogram-range", "error", rel,
                f"lumaHistogram contains non-finite values {_short(histogram)}"))
        else:
            if any(value < 0.0 or value > 1.0 for value in histogram):
                findings.append(_finding(
                    "still.histogram-range", "error", rel,
                    f"lumaHistogram bucket outside [0,1] {_short(histogram)}"))
            total = sum(histogram)
            if abs(total - 1.0) > 0.02:
                findings.append(_finding(
                    "still.histogram-sum", "error", rel,
                    f"lumaHistogram sums to {total:.6f}, expected 1.0 +/- 0.02"))

    mean_rgb = metrics.get("meanRgb")
    if (not isinstance(mean_rgb, list) or len(mean_rgb) != 3
            or any(not _is_number(value) or not 0.0 <= value <= 1.0
                   for value in mean_rgb)):
        findings.append(_finding(
            "still.metric-range", "error", rel,
            f"meanRgb invalid {_short(mean_rgb)}"))

    for field in STILL_METRIC_RANGES:
        value = metrics.get(field)
        if not _is_number(value) or not 0.0 <= value <= 1.0:
            findings.append(_finding(
                "still.metric-range", "error", rel,
                f"{field}={_short(value)} outside [0,1]"))

    hue = metrics.get("dominantHueFamily")
    if hue not in DOCUMENTED_HUE_FAMILIES:
        findings.append(_finding(
            "still.hue-family", "error", rel,
            f"dominantHueFamily {_short(hue)} not in documented vocabulary"))

    size = still.get("imageBytes")
    if (_is_positive_number(size)
            and not IMAGE_BYTES_MIN <= size <= IMAGE_BYTES_MAX):
        findings.append(_finding(
            "still.image-bytes-range", "error", rel,
            f"imageBytes {size} outside {IMAGE_BYTES_MIN}..{IMAGE_BYTES_MAX}"))
    return findings


# ---------------------------------------------------------------------------
# Tree walk and aggregation
# ---------------------------------------------------------------------------


def discover_sites(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    sites = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if (child / "videos").is_dir() or (child / "stills").is_dir():
            sites.append(child)
    return sites


def _load_records(site_dir: Path) -> list[dict[str, Any]]:
    records = []
    for folder in ("videos", "stills"):
        directory = site_dir / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            records.append({"path": path, "folder": folder})
    return records


def _check_index(
    site_dir: Path, root: Path,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for index_name, folder in (
        ("index.json", "videos"),
        ("stills-index.json", "stills"),
    ):
        index_path = site_dir / index_name
        if not index_path.is_file():
            continue
        rel = _relative(index_path, root)
        data, error = _read_json(index_path)
        if error is not None:
            findings.append(_finding(
                "index.unreadable", "warning", rel, error))
            continue
        if not isinstance(data, dict):
            findings.append(_finding(
                "index.unreadable", "warning", rel,
                "index root is not an object"))
            continue
        counts = data.get("counts")
        measured = counts.get("measured") if isinstance(counts, dict) else None
        if not isinstance(measured, int) or isinstance(measured, bool):
            records = data.get("records")
            measured = len(records) if isinstance(records, list) else None
        if measured is None:
            findings.append(_finding(
                "index.unreadable", "warning", rel,
                "index has no usable measured count or records list"))
            continue
        folder_path = site_dir / folder
        on_disk = len(list(folder_path.glob("*.json"))) if folder_path.is_dir() else 0
        if measured != on_disk:
            findings.append(_finding(
                "index.count-mismatch", "warning", rel,
                f"index measured={measured} but {on_disk} {folder}/*.json on disk "
                f"(delta {measured - on_disk:+d})"))
    return findings


def run_audit(
    root: Path, sites: list[str] | None = None,
    strict_duplicates: bool = False,
) -> dict[str, Any]:
    """Audit ``root`` and return a JSON-serialisable report.

    Duplicate-media findings are warnings by default; ``strict_duplicates``
    promotes them to errors for an integrity push.
    """
    root = root.resolve()
    requested = set(sites) if sites else None
    site_reports: dict[str, Any] = {}
    global_counts: dict[str, int] = {"video": 0, "still": 0, "unclassified": 0}

    # Media duplicates are keyed by sha256 across families: the source
    # catalogues repeat a work under several categories/sites, and byte
    # identity is the only reliable signal for the same file. A video record
    # and a still record for the same work intentionally have different bytes;
    # that pairing is detected separately by work identity below.
    sha_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    id_map: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    work_map: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = (
        defaultdict(lambda: defaultdict(list)))

    for site_dir in discover_sites(root):
        site = site_dir.name
        if requested is not None and site not in requested:
            continue
        findings: list[dict[str, Any]] = []
        counts = {"video": 0, "still": 0, "unclassified": 0}

        for entry in _load_records(site_dir):
            path: Path = entry["path"]
            rel = _relative(path, root)
            record, error = _read_json(path)
            if error is not None:
                findings.append(_finding("json.parse", "error", rel, error))
                counts["unclassified"] += 1
                continue
            if not isinstance(record, dict):
                findings.append(_finding(
                    "json.shape", "error", rel, "record root is not an object"))
                counts["unclassified"] += 1
                continue

            family, schema_findings = _check_schema(record, rel)
            findings.extend(schema_findings)
            if family is None:
                # Unknown schema: still gather duplicate keys when possible.
                counts["unclassified"] += 1
            else:
                counts[family] += 1
                if family == "video":
                    findings.extend(_check_video_identity(record, rel))
                    if isinstance(record.get("windows"), list):
                        for index, window in enumerate(record["windows"]):
                            if not isinstance(window, dict):
                                continue
                            probe = window.get("probe")
                            if not isinstance(probe, dict):
                                continue
                            findings.extend(_check_window_arithmetic(
                                window, probe, rel, index))
                        findings.extend(_check_window_consistency(record, rel))
                        findings.extend(_check_record_summary(record, rel))
                        findings.extend(_check_coverage(record, rel))
                else:
                    findings.extend(_check_still_identity(record, rel))
                    findings.extend(_check_still_quality(record, rel))

            sha = None
            if family in ("video", None) and isinstance(record.get("source"), dict):
                sha = record["source"].get("mediaSha256")
            elif family in ("still", None) and isinstance(record.get("still"), dict):
                sha = record["still"].get("imageSha256")
            if isinstance(sha, str) and sha.strip():
                sha_map[sha.strip()].append({
                    "site": site,
                    "family": family or "unknown",
                    "id": _identity_value(record),
                    "path": rel,
                })

            identity = _identity_value(record)
            if identity is not None:
                id_map[(family or "unknown", site, str(identity))].append(rel)
                if family in ("video", "still"):
                    work_map[(site, str(identity))][family].append({
                        "site": site,
                        "family": family,
                        "id": identity,
                        "path": rel,
                    })

        findings.extend(_check_index(site_dir, root))
        site_reports[site] = {
            "recordCounts": counts,
            "findings": findings,
        }
        for family in counts:
            global_counts[family] += counts[family]

    duplicate_counts: dict[str, Any] = {
        "groups": 0,
        "byClass": {name: 0 for name in DUPLICATE_CLASSES},
        "memberRecords": 0,
    }
    duplicate_severity = "error" if strict_duplicates else "warning"

    def add_duplicate(
        rule: str, duplicate_class: str,
        members: list[dict[str, Any]], detail: str,
    ) -> None:
        members.sort(key=lambda member: (member["path"], member["site"],
                                         member["family"]))
        anchor = members[0]
        target = site_reports.get(anchor["site"])
        if target is None:
            return
        target["findings"].append(_finding(
            rule, duplicate_severity, anchor["path"], detail,
            **{"class": duplicate_class, "group": members}))
        duplicate_counts["groups"] += 1
        duplicate_counts["byClass"][duplicate_class] += 1
        duplicate_counts["memberRecords"] += len(members)

    def classify(members: list[dict[str, Any]]) -> str:
        if len({member["family"] for member in members}) > 1:
            return DUPLICATE_CLASS_CROSS_FAMILY
        if len({member["site"] for member in members}) > 1:
            return DUPLICATE_CLASS_CROSS_SITE
        return DUPLICATE_CLASS_SAME_SITE

    # Byte-identical media: one finding per sha256 group, anchored at the
    # alphabetically first record so cross-site groups land deterministically.
    for sha, members in sorted(sha_map.items()):
        if len(members) < 2:
            continue
        duplicate_class = classify(members)
        sites = sorted({member["site"] for member in members})
        families = sorted({member["family"] for member in members})
        add_duplicate(
            "duplicate.source-sha256", duplicate_class, members,
            f"sha256 {sha[:12]}... shared by {len(members)} "
            f"{'/'.join(families)} records across {', '.join(sites)}")

    # Cross-family pairing: a video record and a still record for the same
    # work intentionally have different bytes, so this is reported separately
    # as expected evidence pairing rather than a byte duplicate.
    for (site, identity), families in sorted(work_map.items()):
        if not {"video", "still"} <= set(families):
            continue
        members = [member for group in families.values() for member in group]
        add_duplicate(
            "duplicate.media-cross-family", DUPLICATE_CLASS_CROSS_FAMILY, members,
            f"work {identity} at {site} has both video and still evidence "
            f"({len(members)} records); expected pairing, not duplicate bytes")

    # Same-family identity reuse is a genuine bookkeeping error.
    for (family, site, identity), paths in id_map.items():
        if len(paths) < 2:
            continue
        paths = sorted(paths)
        site_reports[site]["findings"].append(_finding(
            "duplicate.identity", "error", paths[0],
            f"({site}, {identity}) appears in {len(paths)} {family} records: "
            + ", ".join(paths[1:])))

    duplicate_counts["crossFamilyGroups"] = duplicate_counts["byClass"][
        DUPLICATE_CLASS_CROSS_FAMILY]
    duplicate_counts["byteIdenticalGroups"] = (
        duplicate_counts["groups"] - duplicate_counts["crossFamilyGroups"])

    # Per-site and global summaries.
    global_severity: dict[str, int] = {"error": 0, "warning": 0}
    global_rules: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"error": 0, "warning": 0, "severity": "warning"})
    for report in site_reports.values():
        findings = report["findings"]
        by_severity = {"error": 0, "warning": 0}
        by_rule: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"error": 0, "warning": 0, "severity": "warning"})
        for finding in findings:
            severity = finding["severity"]
            by_severity[severity] = by_severity.get(severity, 0) + 1
            entry = by_rule[finding["rule"]]
            entry[severity] += 1
            entry["severity"] = "error" if entry["error"] else "warning"
            global_severity[severity] += 1
            global_entry = global_rules[finding["rule"]]
            global_entry[severity] += 1
            global_entry["severity"] = (
                "error" if global_entry["error"] else "warning")
        findings.sort(key=lambda item: (item["severity"] != "error",
                                        item["rule"], item["path"]))
        report["bySeverity"] = by_severity
        report["byRule"] = {rule: dict(values)
                            for rule, values in sorted(by_rule.items())}
        report["duplicateGroups"] = sum(
            1 for finding in findings if finding["rule"] in DUPLICATE_RULES)

    all_findings = [finding for report in site_reports.values()
                    for finding in report["findings"]]
    all_findings.sort(key=lambda item: (item["severity"] != "error",
                                        item["path"], item["rule"]))
    return {
        "root": str(root),
        "sites": site_reports,
        "summary": {
            "recordCounts": global_counts,
            "bySeverity": global_severity,
            "byRule": {rule: dict(values)
                       for rule, values in sorted(global_rules.items())},
            "duplicates": duplicate_counts,
        },
        "findings": all_findings,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _write_json_atomic(path: Path, payload: Any) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=path.name + ".",
        suffix=".tmp", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _print_report(report: dict[str, Any]) -> None:
    print(f"root: {report['root']}")
    print()
    header = (f"{'site':<24} {'videos':>7} {'stills':>7} {'errors':>7} "
              f"{'warnings':>9} {'dup groups':>10}")
    print(header)
    print("-" * len(header))
    for site, data in report["sites"].items():
        counts = data["recordCounts"]
        severity = data["bySeverity"]
        print(f"{site:<24} {counts['video']:>7} {counts['still']:>7} "
              f"{severity['error']:>7} {severity['warning']:>9} "
              f"{data['duplicateGroups']:>10}")
    totals = report["summary"]["recordCounts"]
    severity = report["summary"]["bySeverity"]
    print("-" * len(header))
    print(f"{'GLOBAL':<24} {totals['video']:>7} {totals['still']:>7} "
          f"{severity['error']:>7} {severity['warning']:>9} "
          f"{report['summary']['duplicates']['groups']:>10}")
    if totals["unclassified"]:
        print(f"unclassified records: {totals['unclassified']}")
    print()

    duplicates = report["summary"]["duplicates"]
    by_class = duplicates["byClass"]
    print(
        f"duplicate media groups: {duplicates['groups']:,} "
        f"(same-site {by_class[DUPLICATE_CLASS_SAME_SITE]:,}, "
        f"cross-site {by_class[DUPLICATE_CLASS_CROSS_SITE]:,}, "
        f"cross-family {by_class[DUPLICATE_CLASS_CROSS_FAMILY]:,})")
    print(
        f"  byte-identical groups: {duplicates['byteIdenticalGroups']:,} "
        f"({duplicates['memberRecords']:,} records in all duplicate groups); "
        "cross-family groups are expected video+still evidence for one work")
    print()

    print("rules:")
    rules = report["summary"]["byRule"]
    if not rules:
        print("  (none)")
    for rule, values in rules.items():
        total = values["error"] + values["warning"]
        print(f"  {values['severity']:<7} {rule:<38} {total:>6} "
              f"(error={values['error']}, warning={values['warning']})")
    print()

    print("per-site rules:")
    for site, data in report["sites"].items():
        if not data["byRule"]:
            continue
        parts = []
        for rule, values in data["byRule"].items():
            total = values["error"] + values["warning"]
            parts.append(f"{rule}={total}({values['severity']})")
        print(f"  {site}: " + ", ".join(parts))
    print()

    findings = report["findings"]
    if findings:
        print(f"findings ({len(findings)}):")
        for finding in findings:
            print(f"  {finding['severity'].upper():<7} {finding['rule']:<38} "
                  f"{finding['path']}: {finding['detail']}")
            if "class" in finding:
                print(f"          [{finding['class']}] group: "
                      + ", ".join(member["path"]
                                  for member in finding["group"]))
    else:
        print("findings: none")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path("research/analysis"),
        help="directory whose child site trees are audited")
    parser.add_argument(
        "--json-out", type=Path, default=None,
        help="write the full report as JSON to this path (atomic replace)")
    parser.add_argument(
        "--site", action="append", default=None, metavar="SLUG",
        help="restrict the audit to one site slug; repeatable")
    parser.add_argument(
        "--strict-duplicates", action="store_true",
        help="promote duplicate-media findings back to errors")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_audit(
        args.root, args.site, strict_duplicates=args.strict_duplicates)
    if args.json_out is not None:
        _write_json_atomic(args.json_out, report)
    _print_report(report)
    return 1 if report["summary"]["bySeverity"]["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
