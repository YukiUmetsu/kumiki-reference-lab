"""Measure authorized What Ships videos directly into version-controlled research.

Runs source-frame numeric analysis without requiring a local vision-language
model, character study, or private backfill. Each output is strictly checked
against the source fingerprint and original PTS before a safe Git-worktree sync.
"""
from __future__ import annotations

import json
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.appearance.source_visual_probe import (
    SCHEMA_VERSION as PROBE_SCHEMA, analyze_source_visual_window,
)
from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.catalog.video_sources import _load_snapshot
from kumiki_reference_lab.catalog.whatships_analysis_store import (
    INDEX_VERSION, SCHEMA_VERSION, _json_bytes, _validate_record,
    sync_repository_analysis, validate_repository_analysis,
)
from kumiki_reference_lab.catalog.whatships_media_bindings import (
    _media_path, _video_identity_map, load_media_bindings,
)
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.whatships_local_worker import _plan_windows

_LIMITATIONS = [
    "No record should be interpreted as verified full-video coverage.",
    "Observed browser moments lack original PTS unless separately analyzed.",
    "RGB/cut metrics are source-frame numerical proxies, not camera/lighting/style truth.",
    "Model-generated character observations have not been human-reviewed.",
    "No local paths, original media, private notes or source-video frames are included.",
]


def _checked_window(probe: dict[str, Any], *, expected_sha: str,
                    expected_stream: int, expected_timebase: dict[str, int],
                    start: int, end: int, width: int, height: int) -> dict[str, Any]:
    """Strict numeric-only projection; never copy private arbitrary probe fields."""
    if (not isinstance(probe, dict) or probe.get("schemaVersion") != PROBE_SCHEMA or
            probe.get("sourceSha256") != expected_sha or
            probe.get("sourceStreamIndex") != expected_stream or
            probe.get("sourceTimebase") != expected_timebase or
            probe.get("evidenceStatus") !=
            "original-source-pts-sampled-numeric-proxies-not-human-reviewed"):
        raise ValueError("source visual probe has wrong media provenance")
    scan = probe.get("scan")
    if (not isinstance(scan, dict) or scan.get("startSeconds") != start or
            scan.get("sourceWindowEndSeconds") != end or
            scan.get("requestedSeconds") != end-start or
            scan.get("frameWidth") != width or scan.get("frameHeight") != height or
            scan.get("sourceTimebaseVerified") is not True):
        raise ValueError("visual probe window dimensions or original source PTS mismatched")
    keep_scan = (
        "sampledSourcePtsCount", "decoder", "cutThreshold",
        "frameWidth", "frameHeight", "sourcePtsFramesSeenInInventory",
    )
    for name in keep_scan:
        if name not in scan:
            raise ValueError("visual probe lacks required scan data")
    for name in ("cutCandidatePts", "sampledFrames",
                 "sampledFramePairs", "sampledWindowSummary"):
        if name not in probe:
            raise ValueError("visual probe lacks actual original-source-frame observations")
    return {
        "startSeconds": start, "endSeconds": end,
        "scan": {
            "sourceStreamIndex": expected_stream,
            "sourceTimebase": expected_timebase,
            **{name: scan[name] for name in keep_scan},
        },
        "cutCandidatePts": probe["cutCandidatePts"],
        "sampledFrames": probe["sampledFrames"],
        "sampledFramePairs": probe["sampledFramePairs"],
        "sampledWindowSummary": probe["sampledWindowSummary"],
        "evidenceStatus": "source-PTS-RGB-metrics-unreviewed",
    }


def _duration_windows(duration: Any, *, window_seconds: int,
                      window_count: int) -> tuple[list[tuple[int, int]], float]:
    if type(duration) is not str:
        raise ValueError("source duration missing; require FFprobe-determined duration")
    try:
        decimal = Decimal(duration)
    except (ValueError, InvalidOperation):
        raise ValueError("source duration missing or invalid") from None
    if not decimal.is_finite() or decimal < 1:
        raise ValueError("source must have at least one second of known video duration")
    span, count, stride, fraction = _plan_windows(
        duration, window_seconds=window_seconds, window_count=window_count)
    windows = [(i*stride, i*stride+span) for i in range(count)]
    if (not windows or any(end > decimal or end > 3600 or
                           (i and start < windows[i-1][1])
                           for i, (start, end) in enumerate(windows))):
        raise ValueError("computed sample intervals extend outside the original video")
    return windows, fraction


def _remaining_windows(
    duration: Any, already: list[dict[str, Any]], *,
    window_seconds: int, window_count: int,
) -> tuple[list[tuple[int, int]], float]:
    """Select largest unmeasured whole-second gaps in a source timeline.

    Uses only the first 3600 source-relative seconds supported by the exact
    PTS decoder. Gap selection accounts for requested intervals, not every
    frame inside those intervals having been measured.
    """
    if (type(window_seconds) is not int or not 1 <= window_seconds <= 30 or
            type(window_count) is not int or not 1 <= window_count <= 6):
        raise ValueError("gap fill window budgets invalid")
    if type(duration) is not str:
        raise ValueError("source duration missing for gap planning")
    try:
        length = Decimal(duration)
    except (ValueError, InvalidOperation):
        raise ValueError("source duration invalid for gap planning") from None
    if not length.is_finite() or length < 1:
        raise ValueError("source duration must be at least one second")
    max_end = int(min(length, Decimal(3600)))
    cursor = 0
    gaps: list[tuple[int, int]] = []
    for row in already:
        start, end = row["startSeconds"], row["endSeconds"]
        if (type(start) is not int or type(end) is not int or
                not cursor <= start < end <= max_end):
            raise ValueError("previous numeric windows are outside current video duration")
        if cursor < start:
            gaps.append((cursor, start))
        cursor = end
    if cursor < max_end:
        gaps.append((cursor, max_end))
    selected: list[tuple[int,int]] = []
    for _ in range(window_count):
        if not gaps:
            break
        # Largest gap first; tie by original film time. A central interval
        # splits long gaps for subsequent fair and deterministic sampling.
        left, right = sorted(gaps, key=lambda x:(-(x[1]-x[0]),x[0]))[0]
        gaps.remove((left,right))
        width = min(window_seconds, right-left)
        start = left+(right-left-width)//2
        end = start+width
        selected.append((start,end))
        if left < start:
            gaps.append((left,start))
        if end < right:
            gaps.append((end,right))
    selected.sort()
    fraction = sum(end-start for start,end in selected)/length
    return selected, round(float(fraction),6)


def measure_whatships_to_repository(
    snapshot_path: Path, binding_path: Path, source_id: str,
    repository_root: Path, *, window_seconds: int = 10,
    window_count: int = 4, max_samples: int = 12,
    width: int = 160, height: int = 90, cut_threshold: float = 0.25,
    replace_existing: bool = False, fill_gaps: bool = False,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Record source-grounded pixels in research/analysis/whatships/<slug>.json.

    Never copies source files or private paths to Git. It only changes the
    canonical tracked working tree after ALL sampled windows and provenance
    validation succeed. Existing browser evidence is preserved by sync.
    """
    if type(source_id) is not str or not source_id.startswith("whatships:"):
        raise ValueError("must specify exact whatships:slug catalog identity")
    if (type(replace_existing) is not bool or type(fill_gaps) is not bool or
            (replace_existing and fill_gaps) or type(max_samples) is not int or
            not 5 <= max_samples <= 24 or type(width) is not int or
            not 64 <= width <= 320 or type(height) is not int or
            not 36 <= height <= 180 or type(cut_threshold) not in (int, float) or
            not 0 < cut_threshold < 1):
        raise ValueError("invalid local media measurement budgets")
    # Validate canonical Git corpus BEFORE any costly source decode.
    validate_repository_analysis(repository_root, snapshot_path)
    snapshot_sig = file_signature(snapshot_path)
    bindings_sig = file_signature(binding_path)
    snapshot = _load_snapshot(snapshot_path)
    indexed = _video_identity_map(snapshot)
    if source_id not in indexed:
        raise ValueError("source ID is not in the validated What Ships catalog")
    media_doc = load_media_bindings(binding_path, snapshot, verify_files=False)
    mapped = {row["sourceId"]: row for row in media_doc["bindings"]}
    if source_id not in mapped:
        raise ValueError("no authorized local video binding for this source ID")
    binding = mapped[source_id]
    source = _media_path(binding["localPath"])
    signature = file_signature(source)
    if (signature[0] != binding["mediaSizeBytes"] or
            sha256_file(source) != binding["mediaSha256"]):
        raise ValueError("authorized source video fingerprint differs from its binding")
    inspected = inspect_source(
        source, ffprobe=ffprobe, rights_status="user-declared-authorized")
    if (inspected["source"]["sha256"] != binding["mediaSha256"] or
            inspected["video"]["streamIndex"] != binding["sourceStreamIndex"] or
            inspected["video"]["sourceTimebase"] != binding["sourceTimebase"]):
        raise ValueError("source bytes, stream or timebase changed since binding")
    previous_windows: list[dict[str, Any]] = []
    if fill_gaps:
        from kumiki_reference_lab.catalog.whatships_media_bindings import _read_json
        previous_file = repository_root/(source_id.removeprefix("whatships:")+".json")
        if previous_file.exists():
            old = _read_json(previous_file)
            numeric = old["evidence"].get("numericVisual")
            if numeric is not None:
                if numeric["sourceSha256"] != binding["mediaSha256"]:
                    raise ValueError("cannot fill gaps using a different source video fingerprint")
                previous_windows = numeric["windows"]
        # This record has a bounded total number of stored source windows.
        # Check capacity *before* paying to decode frames that could not persist.
        from kumiki_reference_lab.catalog.whatships_analysis_store import _MAX_WINDOWS
        slots = _MAX_WINDOWS - len(previous_windows)
        if slots <= 0:
            raise ValueError("per-film source-window evidence limit reached; cannot append")
        windows, requested_fraction = _remaining_windows(
            inspected["video"]["durationSecondsReported"],previous_windows,
            window_seconds=window_seconds,window_count=min(window_count,slots))
    else:
        windows, requested_fraction = _duration_windows(
            inspected["video"]["durationSecondsReported"],
            window_seconds=window_seconds, window_count=window_count)
    if not windows:
        require_unchanged(source, signature)
        return {
            "schemaVersion":"kumiki.whatships-direct-numeric-video-study.v1",
            "sourceId":source_id,
            "measuredOriginalSourceWindows":0,
            "sampledOriginalSourceFrames":0,
            "framesInWindowPtsInventories":0,
            "sampledFrameFractionOfScannedWindowInventories":None,
            "requestedWindowTimeFractionOfReportedFilmDuration":0.0,
            "fullFilmReviewed":False,
            "gitWorkingTreeUpdated":False,
            "existingMeasuredWindowCount":len(previous_windows),
            "status":"no-remaining-whole-second-gaps-within-supported-timeline",
            "limitations":["No additional whole-second interval can be added to this numeric sample.","This does not establish that every original video frame was decoded or reviewed."],
        }
    numeric_windows = []
    original_pts_samples = 0
    frames_in_scanned_intervals = 0
    for start, end in windows:
        report = analyze_source_visual_window(
            source, start_seconds=start, seconds=end-start,
            max_samples=max_samples, width=width, height=height,
            cut_threshold=float(cut_threshold),
            rights_status="user-declared-authorized", ffmpeg=ffmpeg, ffprobe=ffprobe)
        numeric_windows.append(_checked_window(
            report, expected_sha=binding["mediaSha256"],
            expected_stream=binding["sourceStreamIndex"],
            expected_timebase=binding["sourceTimebase"],
            start=start, end=end, width=width, height=height))
        original_pts_samples += report["scan"]["sampledSourcePtsCount"]
        frames_in_scanned_intervals += report["scan"]["sourcePtsFramesSeenInInventory"]
    record = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceId": source_id,
        "watchUrl": indexed[source_id]["directoryUrl"],
        "catalogSnapshotOn": snapshot["retrievedOn"],
        "catalogSnapshotSha256": sha256_file(snapshot_path),
        "sourceMediaSha256": binding["mediaSha256"],
        "coverage": {
            "hasBrowserSpotCheck": False,
            "hasSampledNumericSourceFrames": True,
            "hasUnreviewedCharacterJob": False,
            "fullFilmReviewed": False,
        },
        "evidence": {
            "numericVisual": {
                "sourceSha256": binding["mediaSha256"],
                "windows": numeric_windows,
                "evidenceStatus": "sampled-original-source-pts-metrics-not-expert-reviewed",
            },
        },
        "limits": _LIMITATIONS,
    }
    _validate_record(record, source_id, record["catalogSnapshotSha256"])
    require_unchanged(source, signature)
    if sha256_file(source) != binding["mediaSha256"]:
        raise ValueError("source file changed during original-PTS analysis")
    require_unchanged(snapshot_path, snapshot_sig)
    require_unchanged(binding_path, bindings_sig)
    incoming_index = {
        "schemaVersion": INDEX_VERSION,
        "catalogSnapshotOn": snapshot["retrievedOn"],
        "catalogSnapshotSha256": record["catalogSnapshotSha256"],
        "catalogVideoCount": len(indexed),
        "sourceLinkedAnalysisCount": 1,
        "browserSpotCheckCount": 0,
        "sampledNumericVideoCount": 1,
        "unreviewedCharacterJobCount": 0,
        "fullFilmReviewedCount": 0,
        "entries": [{
            "sourceId": source_id,
            "recordPath": source_id.removeprefix("whatships:")+".json",
            "evidenceKinds": ["numericVisual"],
        }],
        "limits": [
            "Only records with actual observational evidence are stored here.",
            "Metadata-only catalog entries stay in research/whatships-index-2026-11-10.json.",
            "Do not equate a model completion or numeric frame sample with expert review.",
        ],
    }
    # Separate staging avoids requiring a VLM or private prior-study index.
    # Sync preserves existing browser evidence and handles partial write rollback.
    with tempfile.TemporaryDirectory(
        prefix=".kumiki-whatships-direct-",dir=repository_root.parent,
    ) as directory:
        incoming = Path(directory)
        (incoming/"index.json").write_bytes(_json_bytes(incoming_index))
        (incoming/(source_id.removeprefix("whatships:")+".json")).write_bytes(
            _json_bytes(record))
        validate_repository_analysis(incoming,snapshot_path)
        result = sync_repository_analysis(
            snapshot_path, incoming, repository_root,
            replace_existing=replace_existing,
            append_numeric_windows=fill_gaps)
    return {
        "schemaVersion":"kumiki.whatships-direct-numeric-video-study.v1",
        "sourceId":source_id,
        "measuredOriginalSourceWindows":len(windows),
        "existingMeasuredWindowCount":len(previous_windows),
        "measuredWindowsAfterRun":len(previous_windows)+len(windows),
        "sampledOriginalSourceFrames":original_pts_samples,
        "framesInWindowPtsInventories":frames_in_scanned_intervals,
        "sampledFrameFractionOfScannedWindowInventories":round(
            original_pts_samples/frames_in_scanned_intervals,6)
            if frames_in_scanned_intervals else None,
        "requestedWindowTimeFractionOfReportedFilmDuration":requested_fraction,
        "fullFilmReviewed":False,
        "gitWorkingTreeUpdated":bool(result["recordsChangedOrAdded"]),
        "repositoryRecord":f"research/analysis/whatships/{source_id.removeprefix('whatships:')}.json",
        "status":"sampled-numeric-source-PTS-evidence-not-human-reviewed",
        "limitations":[
            "Frame coverage counts only inventories of requested windows, not all film frames.",
            "Requested time-window fraction is not viewed/decoded-frame coverage.",
            "The Git working tree is updated but changes are not automatically committed or pushed.",
        ],
    }
