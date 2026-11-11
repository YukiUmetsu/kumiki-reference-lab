"""Resumable source-PTS numeric visual probes for completed What Ships local studies.

This independent backfill never re-runs expensive VLM inference. It uses the
original study's actual requested windows and the exact SHA-verified local
media, then checkpoints every completed film. No camera/lighting semantics.
"""
from __future__ import annotations

import json
import math
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.appearance.source_visual_probe import (
    SCHEMA_VERSION as PROBE_VERSION, analyze_source_visual_window,
)
from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.catalog.video_sources import _load_snapshot
from kumiki_reference_lab.catalog.whatships_full_coverage import build_full_coverage
from kumiki_reference_lab.catalog.whatships_media_bindings import (
    _media_path, _read_json, _video_identity_map, load_media_bindings,
)
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.whatships_local_worker import (
    _atomic_json, _read_previous_index,
)

SCHEMA_VERSION = "kumiki.whatships-source-visual-backfill.v1"
REPORT_VERSION = "kumiki.whatships-source-visual-coverage.v1"
_DONE = "measured-numeric-proxies-unreviewed"
_FAILED = "failed-preserved-for-retry"


def _validate_study_windows(path: Path, *, expected_sha: str,
                            expected_windows: int) -> list[tuple[int, int]]:
    """Trust only original batch windows with canonical paths/source evidence."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 131072:
        raise ValueError("character batch manifest is missing or oversized")
    try:
        study = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("character batch report unreadable") from exc
    if (not isinstance(study, dict) or
            study.get("schemaVersion") != "kumiki.local-character-study-batch.v1" or
            study.get("sourceSha256") != expected_sha or
            study.get("status") != "completed-multiple-independent-unverified-studies" or
            study.get("windowCount") != expected_windows):
        raise ValueError("source-batch study provenance mismatched")
    windows = study.get("windows")
    if not isinstance(windows, list) or len(windows) != expected_windows:
        raise ValueError("source-batch study windows missing")
    checked = []
    last_end = -1
    for i, item in enumerate(windows):
        if (not isinstance(item, dict) or
                item.get("index") != i or
                item.get("manifest") != f"windows/window-{i:03d}/study-manifest.json" or
                type(item.get("startSeconds")) is not int or
                type(item.get("endSeconds")) is not int):
            raise ValueError("invalid source-batch window identity")
        start, end = item["startSeconds"], item["endSeconds"]
        if not 0 <= start < end <= 3600 or not 1 <= end-start <= 30 or start < last_end:
            raise ValueError("invalid/crossing source-PTS window bounds")
        child = path.parent/item["manifest"]
        if child.is_symlink() or not child.is_file() or child.stat().st_size > 131072:
            raise ValueError("source-batch window child evidence missing")
        try:
            child_data = json.loads(child.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("source-batch child JSON unreadable") from exc
        if (child_data.get("schemaVersion") != "kumiki.local-character-study.v1" or
                child_data.get("sourceSha256") != expected_sha or
                child_data.get("scanStartSeconds") != start or
                child_data.get("maxSeconds") != end-start or
                child_data.get("status") != "completed-unverified-model-proposals"):
            raise ValueError("source-batch child does not match original source window")
        last_end = end
        checked.append((start, end))
    return checked


def _config(*, max_samples: int, width: int, height: int,
            cut_threshold: float) -> dict[str, Any]:
    if (type(max_samples) is not int or not 5 <= max_samples <= 24 or
            type(width) is not int or not 64 <= width <= 320 or
            type(height) is not int or not 36 <= height <= 180 or
            type(cut_threshold) not in (int, float) or
            not math.isfinite(cut_threshold) or not 0 < cut_threshold < 1):
        raise ValueError("visual backfill probe budgets invalid")
    return {
        "maxSamplesPerWindow": max_samples,
        "width": width, "height": height, "cutThreshold": float(cut_threshold),
        "method": "actual-source-PTS-RGB-and-cut-candidates-v1",
    }


def _read_previous_visual_index(path: Path, *, config: dict[str, Any],
                                source_rows: dict[str, dict[str, Any]],
                                original_studies: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    doc = _read_json(path)
    if (not isinstance(doc, dict) or doc.get("schemaVersion") != SCHEMA_VERSION or
            doc.get("configuration") != config or
            doc.get("catalogIndexUrl") != "https://whatships.com/search-index.json"):
        raise ValueError("previous visual backfill index settings incompatible")
    records = doc.get("entries")
    if not isinstance(records, list) or len(records) > 3000:
        raise ValueError("previous visual backfill index malformed")
    seen = set()
    result = []
    for row in records:
        if (not isinstance(row, dict) or set(row) != {
                "sourceId", "mediaSha256", "studyManifestSha256", "status",
                "windowCount", "probeArtifacts", "error"}):
            raise ValueError("previous visual backfill record format invalid")
        sid = row["sourceId"]
        if (type(sid) is not str or sid in seen or sid not in source_rows or
                sid not in original_studies or
                original_studies[sid]["status"] != "completed-unreviewed" or
                row["mediaSha256"] != source_rows[sid]["mediaSha256"] or
                row["studyManifestSha256"] != original_studies[sid]["studyManifestSha256"]):
            raise ValueError("previous visual backfill source provenance invalid")
        seen.add(sid)
        if (type(row["windowCount"]) is not int or not 0 <= row["windowCount"] <= 6 or
                row["status"] not in (_DONE, _FAILED)):
            raise ValueError("previous visual backfill counters or status invalid")
        if row["status"] == _DONE:
            items = row["probeArtifacts"]
            if not isinstance(items, list) or len(items) != row["windowCount"]:
                raise ValueError("previous visual probes are incomplete")
            for i, item in enumerate(items):
                if (not isinstance(item, dict) or set(item) != {
                        "path", "sha256", "startSeconds", "endSeconds", "sampledFrameCount"} or
                        type(item["path"]) is not str or
                        not Path(item["path"]).is_absolute()):
                    raise ValueError("previous visual probe artifact malformed")
                file = Path(item["path"])
                if file.is_symlink() or not file.is_file() or file.stat().st_size > 262144:
                    raise ValueError("previous visual probe is missing or oversized")
                if sha256_file(file) != item["sha256"]:
                    raise ValueError("previous visual probe artifact changed")
                if type(item["sampledFrameCount"]) is not int or not 2 <= item["sampledFrameCount"] <= 24:
                    raise ValueError("previous visual probe frame count invalid")
                parsed = _read_json(file)
                if (parsed.get("schemaVersion") != PROBE_VERSION or
                        parsed.get("sourceSha256") != row["mediaSha256"] or
                        parsed.get("scan",{}).get("startSeconds") != item["startSeconds"] or
                        parsed.get("scan",{}).get("sourceWindowEndSeconds") != item["endSeconds"] or
                        parsed.get("scan",{}).get("sampledSourcePtsCount") != item["sampledFrameCount"]):
                    raise ValueError("previous visual probe did not match source-PTS evidence")
            if row["error"] is not None:
                raise ValueError("completed numeric probe includes an error")
        else:
            if (row["probeArtifacts"] or
                    type(row["error"]) is not str or not row["error"]):
                raise ValueError("failed visual probe cannot have approved artifacts")
        result.append(dict(row))
    return result


def _coverage(snapshot: dict[str, Any], bindings: dict[str, dict[str, Any]],
              entries: list[dict[str, Any]], *, completed_now: int) -> dict[str, Any]:
    source_map = _video_identity_map(snapshot)
    known = {r["sourceId"]:r for r in entries}
    categories: dict[str, Counter] = {}
    for sid, meta in source_map.items():
        category = meta["indexMetadata"].rsplit(" · ",1)[-1]
        count = categories.setdefault(category, Counter())
        count["indexed"] += 1
        if sid in bindings:
            count["bound"] += 1
        if sid in known:
            count[known[sid]["status"]] += 1
    completed = [r for r in entries if r["status"] == _DONE]
    return {
        "schemaVersion": REPORT_VERSION,
        "snapshotOn": snapshot["retrievedOn"],
        "catalogVideoCount": len(source_map),
        "operatorBoundMediaCount": len(bindings),
        "completedNumericProbeVideos": len(completed),
        "completedThisInvocation": completed_now,
        "measuredOriginalSourceWindows": sum(r["windowCount"] for r in completed),
        "humanReviewedNumericProbeVideos": 0,
        "byCategory": {
            cat: {
                "indexed":c["indexed"],"bound":c["bound"],
                "measuredUnreviewed":c[_DONE],"failed":c[_FAILED],
            } for cat,c in sorted(categories.items())
        },
        "entries": [
            {"sourceId":r["sourceId"],"status":r["status"],
             "windowCount":r["windowCount"],
             "reviewStatus":"not-human-reviewed"}
            for r in entries
        ],
        "methodLimits": [
            "Actual source-PTS RGB/cut measurements are not expert judgments of camera moves or lighting.",
            "Sampled windows and frames never imply complete coverage of unobserved video time.",
            "The private source/video paths and error messages have been redacted.",
            "Rights and precise catalog-to-video identity remain operator-attested.",
        ],
    }


def backfill_whatships_visual_probes(
    snapshot_path: Path, binding_path: Path, original_index_path: Path,
    out: Path, *, previous_index: Path | None = None,
    max_videos: int = 1, start_offset: int = 0,
    max_samples: int = 12, width: int = 160, height: int = 90,
    cut_threshold: float = .25,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> Path:
    """Checkpoint genuine per-window numeric video evidence without repeating VLM calls."""
    config = _config(max_samples=max_samples, width=width,
                     height=height, cut_threshold=cut_threshold)
    if (type(max_videos) is not int or not 1 <= max_videos <= 4 or
            type(start_offset) is not int or start_offset < 0):
        raise ValueError("visual backfill batch size/offset invalid")
    if out.exists() or out.is_symlink():
        raise ValueError("visual backfill output must be a new private directory")
    input_paths = (snapshot_path, binding_path, original_index_path)
    signatures = [file_signature(p) for p in input_paths]
    snapshot = _load_snapshot(snapshot_path)
    media_doc = load_media_bindings(binding_path, snapshot, verify_files=False)
    bindings = {r["sourceId"]:r for r in media_doc["bindings"]}
    original = _read_json(original_index_path)
    if not isinstance(original, dict) or not isinstance(original.get("configuration"),dict):
        raise ValueError("original private What Ships analysis index missing configuration")
    source_results = _read_previous_index(
        original_index_path, config=original["configuration"], bindings=bindings)
    studies = {r["sourceId"]:r for r in source_results
               if r["status"] == "completed-unreviewed"}
    previous_sig = file_signature(previous_index) if previous_index is not None else None
    results = (_read_previous_visual_index(
        previous_index, config=config, source_rows=bindings,
        original_studies=studies) if previous_index is not None else [])
    previous_by_id = {r["sourceId"]:r for r in results}
    _, queue = build_full_coverage(snapshot)
    eligible = [
        x["id"] for x in queue["entries"]
        if x["id"] in studies and
        (x["id"] not in previous_by_id or previous_by_id[x["id"]]["status"] != _DONE)
    ]
    if start_offset > len(eligible):
        raise ValueError("visual backfill offset exceeds current eligible queue")
    todo = eligible[start_offset:start_offset+max_videos]
    for path, signature in zip(input_paths, signatures, strict=True):
        require_unchanged(path, signature)
    if previous_index is not None and previous_sig is not None:
        require_unchanged(previous_index, previous_sig)
    out.mkdir(parents=True)
    (out/"runs").mkdir()
    output_index = {
        "schemaVersion": SCHEMA_VERSION,
        "catalogIndexUrl": "https://whatships.com/search-index.json",
        "configuration": config, "entries": results,
        "methodLimits": [
            "This is source-PTS numeric evidence for verified local files, not a human review.",
            "Camera, real lighting and visual style are not classified from RGB pixel proxies.",
            "Previous character-model inferences are not rerun or reclassified.",
        ],
    }
    _atomic_json(out/"visual-index.json", output_index)
    done_now = 0
    _atomic_json(out/"coverage.json", _coverage(
        snapshot, bindings, output_index["entries"], completed_now=0))
    for sid in todo:
        binding = bindings[sid]
        character_study = studies[sid]
        folder = out/"runs"/sid.removeprefix("whatships:")
        frame_artifacts = []
        failure = None
        count = 0
        try:
            source = _media_path(binding["localPath"])
            signature = file_signature(source)
            if (signature[0] != binding["mediaSizeBytes"] or
                    sha256_file(source) != binding["mediaSha256"]):
                raise ValueError("bound media fingerprint differs from its registration")
            info = inspect_source(source, ffprobe=ffprobe,
                                  rights_status="user-declared-authorized")
            if (info["source"]["sha256"] != binding["mediaSha256"] or
                    info["video"]["streamIndex"] != binding["sourceStreamIndex"] or
                    info["video"]["sourceTimebase"] != binding["sourceTimebase"]):
                raise ValueError("source file bytes/stream/timebase do not match bound identity")
            manifest = Path(character_study["studyManifestPath"])
            if sha256_file(manifest) != character_study["studyManifestSha256"]:
                raise ValueError("prior model study manifest was modified")
            windows = _validate_study_windows(
                manifest, expected_sha=binding["mediaSha256"],
                expected_windows=character_study["windowCount"])
            count = len(windows)
            folder.mkdir()
            for i,(start,end) in enumerate(windows):
                report = analyze_source_visual_window(
                    source, start_seconds=start, seconds=end-start,
                    max_samples=max_samples, width=width, height=height,
                    cut_threshold=cut_threshold,
                    rights_status="user-declared-authorized",
                    ffmpeg=ffmpeg, ffprobe=ffprobe,
                )
                if (report.get("schemaVersion") != PROBE_VERSION or
                        report.get("sourceSha256") != binding["mediaSha256"] or
                        report.get("sourceStreamIndex") != binding["sourceStreamIndex"] or
                        report.get("sourceTimebase") != binding["sourceTimebase"] or
                        report.get("scan",{}).get("startSeconds") != start or
                        report.get("scan",{}).get("sourceWindowEndSeconds") != end):
                    raise ValueError("numeric source probe returned inconsistent source-PTS evidence")
                file = folder/f"window-{i:03d}.json"
                _atomic_json(file, report)
                frame_artifacts.append({
                    "path": str(file.resolve()),
                    "sha256": sha256_file(file),
                    "startSeconds": start, "endSeconds": end,
                    "sampledFrameCount": report["scan"]["sampledSourcePtsCount"],
                })
            require_unchanged(source, signature)
            if sha256_file(source) != binding["mediaSha256"]:
                raise ValueError("local source changed after visual measurement")
        except (ValueError, OSError, TimeoutError, KeyError, TypeError,
                json.JSONDecodeError) as exc:
            failure = type(exc).__name__+": "+str(exc)[:320]
            frame_artifacts = []
            if folder.exists():
                shutil.rmtree(folder)
        previous_by_id[sid] = {
            "sourceId":sid,
            "mediaSha256":binding["mediaSha256"],
            "studyManifestSha256":character_study["studyManifestSha256"],
            "status":_DONE if failure is None else _FAILED,
            "windowCount":count,
            "probeArtifacts":frame_artifacts,
            "error":failure,
        }
        if failure is None:
            done_now += 1
        output_index["entries"] = sorted(
            previous_by_id.values(), key=lambda value:value["sourceId"])
        for path, signature in zip(input_paths, signatures, strict=True):
            require_unchanged(path, signature)
        if previous_index is not None and previous_sig is not None:
            require_unchanged(previous_index, previous_sig)
        _atomic_json(out/"visual-index.json", output_index)
        _atomic_json(out/"coverage.json", _coverage(
            snapshot, bindings, output_index["entries"], completed_now=done_now))
    return out/"coverage.json"
