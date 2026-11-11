"""Resumable, SHA-verified local character-study batches for What Ships.

Each completed video is checkpointed independently. A later failure never
invalidates earlier completed local media analyses. Output includes unreviewed
model evidence, not reviewed cinematographic ground truth.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.catalog.video_sources import _load_snapshot
from kumiki_reference_lab.catalog.whatships_full_coverage import build_full_coverage
from kumiki_reference_lab.catalog.whatships_media_bindings import (
    _media_path, _read_json, _video_identity_map, load_media_bindings,
)
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.character_study_batch import run_character_study_batch
from kumiki_reference_lab.pipeline.ollama_character_perception import _MODEL

SCHEMA_VERSION = "kumiki.whatships-local-analysis-index.v1"
REPORT_VERSION = "kumiki.whatships-local-analysis-progress.v1"
_COMPLETED = "completed-unreviewed"
_FAILED = "failed-preserved-for-retry"
_MAX_ENTRIES = 3000


def _plan_windows(duration: Any, *, window_seconds: int,
                  window_count: int) -> tuple[int, int, int, float | None]:
    """Distribute nonoverlapping bounded samples across reported film duration.

    The returned span fraction is the *requested time-window fraction*, NOT
    measured frames, shot coverage, or vision accuracy.
    """
    if (type(window_seconds) is not int or not 1 <= window_seconds <= 30 or
            type(window_count) is not int or not 1 <= window_count <= 6):
        raise ValueError("window duration/count budgets are out of bounds")
    if not isinstance(duration, str):
        raise ValueError("FFprobe source did not report a usable duration")
    try:
        length = Decimal(duration)
    except (InvalidOperation, ValueError):
        raise ValueError("source duration could not be interpreted") from None
    if not length.is_finite() or length <= 0:
        raise ValueError("source reported invalid/nonpositive video duration")
    max_end = min(3600, max(1, int(length)))
    span = min(window_seconds, max_end)
    count = min(window_count, max(1, max_end // span))
    stride = span if count == 1 else (max_end-span)//(count-1)
    if stride < span:
        raise ValueError("computed media windows would overlap")
    # This reflects requested window spans only; each VLM actually samples
    # sparse PTS frames, and some catalog video may extend beyond one hour.
    requested_fraction = min(1.0, float(Decimal(span*count)/length))
    return span, count, stride, round(requested_fraction, 6)


def _configuration(*, model: str, detector: str, window_seconds: int,
                   window_count: int, max_samples: int, max_calls: int,
                   max_pairs: int, width: int, height: int, port: int,
                   timeout_seconds: int, review: bool,
                   interactions: bool) -> dict[str, Any]:
    if (type(model) is not str or not _MODEL.fullmatch(model) or len(model) > 72 or
            detector not in ("ollama", "apple-vision") or
            type(window_seconds) is not int or not 1 <= window_seconds <= 30 or
            type(window_count) is not int or not 1 <= window_count <= 6 or
            type(max_samples) is not int or not 5 <= max_samples <= 12 or
            type(max_calls) is not int or not 1 <= max_calls <= 12 or
            type(max_pairs) is not int or not 1 <= max_pairs <= 6 or
            type(width) is not int or not 64 <= width <= 320 or
            type(height) is not int or not 36 <= height <= 180 or
            type(port) is not int or not 1 <= port <= 65535 or
            type(timeout_seconds) is not int or not 5 <= timeout_seconds <= 300 or
            type(review) is not bool or type(interactions) is not bool):
        raise ValueError("local study worker model or resource budgets invalid")
    return {
        "modelTag": model, "detector": detector,
        "requestedWindowSeconds": window_seconds,
        "requestedWindowCount": window_count,
        "maxSamplesPerWindow": max_samples,
        "maxVisionCallsPerWindow": max_calls,
        "maxInteractionPairsPerWindow": max_pairs,
        "width": width, "height": height, "ollamaPort": port,
        "modelTimeoutSeconds": timeout_seconds,
        "createEvidenceGalleries": review, "inferPairwiseInteractions": interactions,
        "rightsStatus": "user-declared-authorized",
    }


def _new_index(config: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "catalogIndexUrl": "https://whatships.com/search-index.json",
        "sourceSnapshotDate": snapshot["retrievedOn"],
        "configuration": config,
        "entries": [],
        "methodLimits": [
            "Completed only means source-PTS-bound local inference ran; all model claims remain unreviewed.",
            "Source identity and lawful permission are operator-attested, not third-party verified.",
            "A time-window span fraction is NOT a frame-analysis fraction or complete film review.",
            "No cross-window/cross-video character identity, camera style, lighting or emotion is certified.",
        ],
    }


def _read_previous_index(path: Path, *, config: dict[str, Any],
                         bindings: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    previous = _read_json(path)
    if (not isinstance(previous, dict) or
            previous.get("schemaVersion") != SCHEMA_VERSION or
            previous.get("catalogIndexUrl") != "https://whatships.com/search-index.json" or
            previous.get("configuration") != config):
        raise ValueError("previous analysis index has incompatible version or model configuration")
    entries = previous.get("entries")
    if not isinstance(entries, list) or len(entries) > _MAX_ENTRIES:
        raise ValueError("previous analysis index has invalid entry list")
    seen = set()
    copied = []
    for row in entries:
        if (not isinstance(row, dict) or set(row) != {
                "sourceId", "mediaSha256", "status", "studyManifestPath",
                "studyManifestSha256", "windowCount", "requestedWindowSpanFraction",
                "error"}):
            raise ValueError("previous analysis record schema changed")
        source_id = row["sourceId"]
        if (type(source_id) is not str or source_id in seen or
                source_id not in bindings or
                row["mediaSha256"] != bindings[source_id]["mediaSha256"]):
            raise ValueError("previous analysis record mismatches bound local source media")
        seen.add(source_id)
        if row["status"] not in (_COMPLETED, _FAILED):
            raise ValueError("previous analysis record claims unknown review status")
        if row["status"] == _COMPLETED:
            path_value = row["studyManifestPath"]
            if type(path_value) is not str or not Path(path_value).is_absolute():
                raise ValueError("previous study manifest path must be absolute")
            report_file = Path(path_value)
            if report_file.is_symlink() or not report_file.is_file() or report_file.stat().st_size > 131072:
                raise ValueError("previous study manifest missing, symlinked or oversized")
            if sha256_file(report_file) != row["studyManifestSha256"]:
                raise ValueError("previous completed study manifest changed; cannot reuse")
            try:
                sub = json.loads(report_file.read_text(encoding="utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("previous completed study report is invalid JSON") from exc
            if (sub.get("schemaVersion") != "kumiki.local-character-study-batch.v1" or
                    sub.get("sourceSha256") != row["mediaSha256"] or
                    sub.get("status") != "completed-multiple-independent-unverified-studies" or
                    sub.get("windowCount") != row["windowCount"] or
                    sub.get("modelTag") != config["modelTag"] or
                    sub.get("detectorBackend") != config["detector"]):
                raise ValueError("previous study manifest source/configuration differs")
            if row["error"] is not None or row["studyManifestSha256"] is None:
                raise ValueError("completed study contains invalid failure metadata")
        else:
            if (row["studyManifestPath"] is not None or
                    row["studyManifestSha256"] is not None or
                    type(row["error"]) is not str or not row["error"]):
                raise ValueError("failed study must not masquerade as a complete result")
        if (type(row["windowCount"]) is not int or not 0 <= row["windowCount"] <= 6 or
                (row["requestedWindowSpanFraction"] is not None and
                 (type(row["requestedWindowSpanFraction"]) not in (int, float) or
                  not math.isfinite(row["requestedWindowSpanFraction"]) or
                  not 0 <= row["requestedWindowSpanFraction"] <= 1))):
            raise ValueError("previous study requested-window counters invalid")
        copied.append(dict(row))
    return copied


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         indent=2, allow_nan=False)+"\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=".study-state-",
        suffix=".json", delete=False,
    ) as file:
        temporary = Path(file.name)
        try:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        finally:
            pass
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _public_report(snapshot: dict[str, Any], bindings: dict[str, dict[str, Any]],
                   index: dict[str, Any], *, completed_this_run: int) -> dict[str, Any]:
    known = {row["sourceId"]: row for row in index["entries"]}
    sources = _video_identity_map(snapshot)
    by_category: dict[str, Counter] = {}
    for source_id, source in sources.items():
        category = source["indexMetadata"].rsplit(" · ", 1)[-1]
        metrics = by_category.setdefault(category, Counter())
        metrics["indexed"] += 1
        if source_id in bindings:
            metrics["bound"] += 1
        if source_id in known:
            metrics[known[source_id]["status"]] += 1
    completed = sum(row["status"] == _COMPLETED for row in known.values())
    failed = sum(row["status"] == _FAILED for row in known.values())
    # The report contains NO filesystem paths or private rights explanations.
    return {
        "schemaVersion": REPORT_VERSION,
        "snapshotOn": snapshot["retrievedOn"],
        "catalogVideoCount": len(sources),
        "operatorBoundMediaCount": len(bindings),
        "completedUnreviewedVideoCount": completed,
        "failedVideoCount": failed,
        "completedThisInvocation": completed_this_run,
        "boundNotYetCompleted": len(bindings)-completed,
        "unboundCatalogVideos": len(sources)-len(bindings),
        "humanReviewedVideos": 0,
        "byCategory": {
            k: {
                "indexed": v["indexed"], "bound": v["bound"],
                "completedUnreviewed": v[_COMPLETED], "failed": v[_FAILED],
            } for k, v in sorted(by_category.items())
        },
        "entries": [
            {
                "sourceId": row["sourceId"],
                "status": row["status"],
                "windowCount": row["windowCount"],
                "requestedWindowSpanFraction": row["requestedWindowSpanFraction"],
                "reviewStatus": "not-human-reviewed",
            }
            for row in index["entries"]
        ],
        "methodLimits": [
            "No automatic visual or speech inference can certify creator identity, rights or human review.",
            "Window-span fraction measures requested time intervals only, not actual PTS/frame coverage.",
            "Model observations and subject/character interactions are hypotheses requiring source review.",
            "Analysis of source audio, lighting and cinematography is not asserted by this character pipeline.",
            "Paths and private source evidence are omitted from this shareable report.",
        ],
    }


def run_whatships_local_analysis(
    snapshot_path: Path, media_manifest: Path, out: Path, *,
    model: str, previous_index: Path | None = None,
    source_id: str | None = None, max_videos: int = 1,
    start_offset: int = 0, detector: str = "ollama",
    window_seconds: int = 10, window_count: int = 2,
    max_samples: int = 6, max_calls: int = 6, max_pairs: int = 2,
    width: int = 320, height: int = 180,
    port: int = 11434, timeout_seconds: int = 180,
    review: bool = True, interactions: bool = True,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> Path:
    """Process up to four operator-bound videos and checkpoint each result.

    Failures are recorded independently; successful per-source analysis is
    preserved and can be resumed through a previous private analysis index.
    """
    config = _configuration(
        model=model, detector=detector, window_seconds=window_seconds,
        window_count=window_count, max_samples=max_samples, max_calls=max_calls,
        max_pairs=max_pairs, width=width, height=height, port=port,
        timeout_seconds=timeout_seconds, review=review, interactions=interactions,
    )
    if (type(max_videos) is not int or not 1 <= max_videos <= 4 or
            type(start_offset) is not int or start_offset < 0):
        raise ValueError("analysis batch must contain 1..4 videos with nonnegative offset")
    if out.exists() or out.is_symlink():
        raise ValueError("local analysis output must be a new private directory")
    source_sig = file_signature(snapshot_path)
    binding_sig = file_signature(media_manifest)
    prior_sig = file_signature(previous_index) if previous_index is not None else None
    snapshot = _load_snapshot(snapshot_path)
    doc = load_media_bindings(media_manifest, snapshot, verify_files=False)
    media = {row["sourceId"]: row for row in doc["bindings"]}
    if source_id is not None and (type(source_id) is not str or source_id not in media):
        raise ValueError("requested source ID is absent from private authorized media bindings")
    index = _new_index(config, snapshot)
    if previous_index is not None:
        index["entries"] = _read_previous_index(
            previous_index, config=config, bindings=media)
    previous_by_id = {entry["sourceId"]: entry for entry in index["entries"]}
    # The catalog-wide queue is round-robin by category, so a large AI section
    # cannot monopolize small categories. No view-count selection bias.
    _, backlog = build_full_coverage(snapshot)
    candidates = [
        item["id"] for item in backlog["entries"]
        if item["id"] in media and
        (source_id is None or item["id"] == source_id) and
        (item["id"] not in previous_by_id or
         previous_by_id[item["id"]]["status"] != _COMPLETED)
    ]
    if start_offset > len(candidates):
        raise ValueError("start offset exceeds unfinished authorized media queue")
    todo = candidates[start_offset:start_offset+max_videos]
    # No model or network call if no authorized media is available. A report
    # still distinguishes catalog enumeration from actual analyzed videos.
    require_unchanged(snapshot_path, source_sig)
    require_unchanged(media_manifest, binding_sig)
    if previous_index is not None and prior_sig is not None:
        require_unchanged(previous_index, prior_sig)
    out.mkdir(parents=True, exist_ok=False)
    (out/"runs").mkdir()
    completed_this_run = 0
    _atomic_json(out/"analysis-index.json", index)
    _atomic_json(out/"coverage.json", _public_report(
        snapshot, media, index, completed_this_run=0))
    for candidate in todo:
        row = media[candidate]
        slug = candidate.removeprefix("whatships:")
        folder = out/"runs"/slug
        requested_fraction = None
        observed_windows = 0
        failure = None
        manifest_file = None
        manifest_hash = None
        signature = None
        source = None
        try:
            source = _media_path(row["localPath"])
            signature = file_signature(source)
            if (signature[0] != row["mediaSizeBytes"] or
                    sha256_file(source) != row["mediaSha256"]):
                raise ValueError("registered media byte fingerprint changed")
            info = inspect_source(
                source, ffprobe=ffprobe, rights_status="user-declared-authorized")
            if (info["source"]["sha256"] != row["mediaSha256"] or
                    info["video"]["streamIndex"] != row["sourceStreamIndex"] or
                    info["video"]["sourceTimebase"] != row["sourceTimebase"]):
                raise ValueError("media stream/timebase/provenance changed from binding")
            span, count, stride, requested_fraction = _plan_windows(
                info["video"]["durationSecondsReported"],
                window_seconds=window_seconds, window_count=window_count,
            )
            observed_windows = count
            manifest_file = run_character_study_batch(
                source, folder, model=model, detector=detector,
                start_seconds=0, window_seconds=span,
                stride_seconds=stride, window_count=count,
                max_samples=max_samples, max_calls=max_calls,
                max_pairs=max_pairs, width=width, height=height,
                port=port, timeout_seconds=timeout_seconds,
                review=review, interactions=interactions,
                ffmpeg=ffmpeg, ffprobe=ffprobe,
                rights_status="user-declared-authorized",
            )
            if manifest_file != folder/"batch-manifest.json":
                raise ValueError("study returned unexpected manifest path")
            if manifest_file.is_symlink() or not manifest_file.is_file() or (
                    manifest_file.stat().st_size > 131072):
                raise ValueError("study reported missing/oversized final manifest")
            study = json.loads(manifest_file.read_text(encoding="utf-8"))
            if (study.get("schemaVersion") != "kumiki.local-character-study-batch.v1" or
                    study.get("sourceSha256") != row["mediaSha256"] or
                    study.get("modelTag") != model or
                    study.get("detectorBackend") != detector or
                    study.get("windowCount") != count or
                    study.get("status") != "completed-multiple-independent-unverified-studies"):
                raise ValueError("study manifest does not match source/model/window provenance")
            require_unchanged(source, signature)
            if sha256_file(source) != row["mediaSha256"]:
                raise ValueError("source video was modified after local model inference")
            manifest_hash = sha256_file(manifest_file)
            completed_this_run += 1
        except (ValueError, OSError, TimeoutError, KeyError, TypeError,
                json.JSONDecodeError) as exc:
            # A study that failed provenance or semantic validation is not
            # reusable and must never inflate the completed counter.
            failure = type(exc).__name__ + ": " + str(exc)[:320]
            manifest_file = None
            manifest_hash = None
            if folder.exists():
                shutil.rmtree(folder)
        record = {
            "sourceId": candidate,
            "mediaSha256": row["mediaSha256"],
            "status": _COMPLETED if failure is None else _FAILED,
            "studyManifestPath": str(manifest_file.resolve()) if manifest_file else None,
            "studyManifestSha256": manifest_hash,
            "windowCount": observed_windows,
            "requestedWindowSpanFraction": requested_fraction,
            "error": failure,
        }
        previous_by_id[candidate] = record
        # Preserve original category order and stable checkpoint semantics.
        index["entries"] = sorted(previous_by_id.values(), key=lambda item: item["sourceId"])
        index["updatedAt"] = datetime.now(timezone.utc).isoformat()
        require_unchanged(snapshot_path, source_sig)
        require_unchanged(media_manifest, binding_sig)
        if previous_index is not None and prior_sig is not None:
            require_unchanged(previous_index, prior_sig)
        _atomic_json(out/"analysis-index.json", index)
        _atomic_json(out/"coverage.json", _public_report(
            snapshot, media, index, completed_this_run=completed_this_run))
    return out/"coverage.json"
