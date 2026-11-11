"""Bounded, restartable What Ships source-PTS measurement across authorized videos.

The canonical tracked JSON is the checkpoint. A failed video cannot undo an
earlier successful source's committed worktree evidence. No video-model calls,
remote media retrieval, automatic Git commits or private-path output.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from kumiki_reference_lab.catalog.video_sources import _load_snapshot
from kumiki_reference_lab.catalog.whatships_analysis_store import validate_repository_analysis
from kumiki_reference_lab.catalog.whatships_direct_measure import measure_whatships_to_repository
from kumiki_reference_lab.catalog.whatships_full_coverage import build_full_coverage
from kumiki_reference_lab.catalog.whatships_media_bindings import (
    _read_json, load_media_bindings,
)
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged

SCHEMA_VERSION = "kumiki.whatships-bounded-measurement-batch.v1"


def measure_whatships_batch(
    snapshot_path: Path, binding_path: Path, repository_root: Path, *,
    max_videos: int = 2, start_offset: int = 0, category: str | None = None,
    window_seconds: int = 10, window_count: int = 4, max_samples: int = 12,
    width: int = 160, height: int = 90, cut_threshold: float = .25,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Process unmeasured bound videos in category-balanced catalog order.

    Successful files are durable in the Git worktree immediately. Failures
    leave their source unmeasured; the operator can move past them with
    --start-offset, without lying that a study succeeded.
    """
    if (type(max_videos) is not int or not 1 <= max_videos <= 4 or
            type(start_offset) is not int or start_offset < 0):
        raise ValueError("batch accepts 1..4 authorized videos and a nonnegative offset")
    if category is not None and category not in (
            "ai","developer-tools","design","motion","productivity",
            "consumer","hardware","other"):
        raise ValueError("unrecognized What Ships video category")
    # Never start partial experiments if the existing Git research corpus is
    # invalid, or the authorization ledger does not match the catalog.
    validate_repository_analysis(repository_root,snapshot_path)
    source_sig = file_signature(snapshot_path)
    binding_sig = file_signature(binding_path)
    snapshot = _load_snapshot(snapshot_path)
    doc = load_media_bindings(binding_path,snapshot,verify_files=False)
    bindings = {r["sourceId"]:r for r in doc["bindings"]}
    old_index = _read_json(repository_root/"index.json")
    tracked = {}
    for entry in old_index["entries"]:
        sid = entry["sourceId"]
        record = _read_json(repository_root/entry["recordPath"])
        tracked[sid] = record
    _, backlog = build_full_coverage(snapshot)
    bound_order = [
        x["id"] for x in backlog["entries"]
        if x["id"] in bindings and
        (category is None or x["category"] == category)
    ]
    pending, previously_measured, stale = [], [], []
    for sid in bound_order:
        record = tracked.get(sid)
        numeric = record["evidence"].get("numericVisual") if record else None
        if numeric is None:
            pending.append(sid)
        elif numeric["sourceSha256"] == bindings[sid]["mediaSha256"]:
            previously_measured.append(sid)
        else:
            # Do not silently replace prior source evidence with a different
            # video byte identity, even if the binding was changed deliberately.
            stale.append(sid)
    if start_offset > len(pending):
        raise ValueError("batch offset exceeds unmeasured authorized sources")
    selected = pending[start_offset:start_offset+max_videos]
    require_unchanged(snapshot_path,source_sig)
    require_unchanged(binding_path,binding_sig)
    successes, failures = [], []
    for sid in selected:
        require_unchanged(snapshot_path,source_sig)
        require_unchanged(binding_path,binding_sig)
        try:
            result = measure_whatships_to_repository(
                snapshot_path,binding_path,sid,repository_root,
                window_seconds=window_seconds,window_count=window_count,
                max_samples=max_samples,width=width,height=height,
                cut_threshold=cut_threshold,ffmpeg=ffmpeg,ffprobe=ffprobe,
                replace_existing=False)
            # Cross-check that the requested source is really stored in the
            # verified Git corpus before incrementing the completed count.
            validate_repository_analysis(repository_root,snapshot_path)
            committed = _read_json(
                repository_root/(sid.removeprefix("whatships:")+".json"))
            actual = committed["evidence"].get("numericVisual")
            if (actual is None or
                    actual["sourceSha256"] != bindings[sid]["mediaSha256"]):
                raise ValueError("video measurement did not appear in canonical Git research corpus")
            successes.append({
                "sourceId":sid,
                "sampledOriginalSourceFrames":result["sampledOriginalSourceFrames"],
                "framesInWindowPtsInventories":result["framesInWindowPtsInventories"],
                "measuredSourceWindows":result["measuredOriginalSourceWindows"],
                "status":"source-PTS-numeric-evidence-in-Git-not-human-reviewed",
            })
        except (ValueError,OSError,TimeoutError,RuntimeError) as exc:
            # No exception text is emitted because subprocess exceptions and
            # private manifests might include sensitive local file paths.
            failures.append({
                "sourceId":sid,
                "errorType":type(exc).__name__,
                "status":"source-not-measured-retry-eligible",
            })
    validate_repository_analysis(repository_root,snapshot_path)
    updated = _read_json(repository_root/"index.json")
    numeric_count = updated["sampledNumericVideoCount"]
    return {
        "schemaVersion":SCHEMA_VERSION,
        "catalogSnapshotOn":snapshot["retrievedOn"],
        "catalogVideoCount":len(snapshot["videos"]),
        "operatorBoundVideoCount":len(bindings),
        "categoryFilter":category,
        "previouslyMeasuredBoundSources":len(previously_measured),
        "stalePriorSourceFingerprintCount":len(stale),
        "staleSourceIds":stale,
        "unmeasuredEligibleBeforeRun":len(pending),
        "startOffset":start_offset,
        "requestedMaxVideos":max_videos,
        "attemptedThisRun":len(selected),
        "succeededThisRun":len(successes),
        "failedThisRun":len(failures),
        "succeeded":successes,
        "failed":failures,
        "trackedMeasuredVideoCount":numeric_count,
        "fullVideoHumanReviewCount":0,
        "gitWorkingTreeDataUpdated":bool(successes),
        "nextStep":"inspect Git diff and commit measured per-video research JSON",
        "methodLimits":[
            "Selection covers operator-bound local videos only, not all publicly cataloged videos.",
            "Existing numeric source samples are skipped; new windows/changed video sources need an explicit single-source replacement.",
            "Failed video records stay eligible; use --start-offset to proceed past repeatedly failing media.",
            "Only measured PTS samples enter Git; sampled windows and frames are not full video coverage.",
            "Never counts user-declared media permission or a successful numeric measurement as human visual review.",
        ],
    }
