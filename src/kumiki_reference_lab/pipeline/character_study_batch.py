"""Bounded multiple-window local character research, preserving independent identities.

This reuses the verified one-window pipeline. Window output stays separate:
subject IDs such as subject_001 must NOT be merged across different windows.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.local_character_study import run_local_character_study
from kumiki_reference_lab.pipeline.ollama_character_perception import _MODEL, _VIDEO_EXTENSIONS

SCHEMA_VERSION = "kumiki.local-character-study-batch.v1"


def _window_schedule(*, start_seconds: int, window_seconds: int,
                     stride_seconds: int | None, window_count: int) -> list[tuple[int, int]]:
    if (type(start_seconds) is not int or start_seconds < 0 or
            type(window_seconds) is not int or not 1 <= window_seconds <= 30 or
            type(window_count) is not int or not 1 <= window_count <= 6 or
            (stride_seconds is not None and type(stride_seconds) is not int)):
        raise ValueError("invalid bounded character batch window schedule")
    stride = window_seconds if stride_seconds is None else stride_seconds
    if stride < window_seconds:
        raise ValueError("character batch windows must not overlap")
    last_end = start_seconds + (window_count-1)*stride + window_seconds
    if last_end > 120:
        raise ValueError("character batch final window must end within first 120 seconds")
    return [(start_seconds + i*stride, start_seconds + i*stride + window_seconds)
            for i in range(window_count)]


def run_character_study_batch(
    source: Path, out: Path, *, model: str, detector: str = "ollama",
    start_seconds: int = 0, window_seconds: int = 10,
    stride_seconds: int | None = None, window_count: int = 3,
    max_samples: int = 8, max_calls: int = 8, max_pairs: int = 3,
    width: int = 320, height: int = 180, port: int = 11434,
    timeout_seconds: int = 180, review: bool = True,
    interactions: bool = True, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe", rights_status: str = "review-required",
) -> Path:
    """Atomically publish several independent original-PTS character studies."""
    windows = _window_schedule(
        start_seconds=start_seconds, window_seconds=window_seconds,
        stride_seconds=stride_seconds, window_count=window_count,
    )
    if (type(model) is not str or not _MODEL.fullmatch(model) or len(model) > 72 or
            detector not in ("ollama", "apple-vision") or
            type(max_samples) is not int or not 5 <= max_samples <= 12 or
            type(max_calls) is not int or not 1 <= max_calls <= 12 or
            type(max_pairs) is not int or not 1 <= max_pairs <= 6 or
            type(port) is not int or not 1 <= port <= 65535 or
            type(timeout_seconds) is not int or not 5 <= timeout_seconds <= 300 or
            type(width) is not int or not 64 <= width <= 320 or
            type(height) is not int or not 36 <= height <= 180 or
            type(review) is not bool or type(interactions) is not bool):
        raise ValueError("invalid character batch model or local resource bounds")
    if source.is_symlink() or not source.is_file() or source.suffix.lower() not in _VIDEO_EXTENSIONS:
        raise ValueError("character batch requires an authorized regular local video")
    if out.exists() or out.is_symlink():
        raise ValueError("batch output must be a new nonexisting directory")
    signature = file_signature(source)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-character-batch-", dir=out.parent) as directory:
        staging = Path(directory)
        (staging / "windows").mkdir()
        summaries: list[dict[str, Any]] = []
        source_sha: str | None = None
        totals = {
            "detectedRegionProposals": 0,
            "provisionalTracklets": 0,
            "provisionalCharacterTrackletAppearances": 0,
            "visionAppearanceProposals": 0,
        }
        for i, (start, end) in enumerate(windows):
            folder = staging / "windows" / f"window-{i:03d}"
            report_file = run_local_character_study(
                source, folder, model=model, detector=detector,
                start_seconds=start, max_seconds=end-start,
                max_samples=max_samples, max_calls=max_calls,
                max_pairs=max_pairs, width=width, height=height,
                port=port, timeout_seconds=timeout_seconds,
                review=review, interactions=interactions,
                ffmpeg=ffmpeg, ffprobe=ffprobe, rights_status=rights_status,
            )
            if report_file != folder / "study-manifest.json":
                raise ValueError("character batch unexpected study manifest location")
            report = json.loads(report_file.read_text(encoding="utf-8"))
            if (not isinstance(report, dict) or
                    report.get("schemaVersion") != "kumiki.local-character-study.v1" or
                    report.get("scanStartSeconds") != start or
                    report.get("maxSeconds") != end-start or
                    report.get("scanPrefixSeconds") != end or
                    report.get("status") != "completed-unverified-model-proposals" or
                    report.get("detectorBackend") != detector or
                    report.get("modelTag") != model):
                raise ValueError("character batch child report mismatched intended window")
            sha = report.get("sourceSha256")
            if type(sha) is not str or len(sha) != 64 or (
                    source_sha is not None and sha != source_sha):
                raise ValueError("character batch windows disagree on source identity")
            source_sha = sha
            for name in totals:
                field = ("provisionalCharacterIdsObserved"
                         if name == "provisionalCharacterTrackletAppearances" else name)
                value = report.get(field)
                if type(value) is not int or value < 0:
                    raise ValueError("character batch child summary count invalid")
                totals[name] += value
            summaries.append({
                "index": i, "startSeconds": start, "endSeconds": end,
                "manifest": f"windows/window-{i:03d}/study-manifest.json",
                "status": "completed-unverified-model-proposals",
                "provisionalTracklets": report["provisionalTracklets"],
                "visionAppearanceProposals": report["visionAppearanceProposals"],
            })
            require_unchanged(source, signature)

        require_unchanged(source, signature)
        if source_sha != sha256_file(source):
            raise ValueError("character batch child source fingerprint differs from actual video")
        batch = {
            "schemaVersion": SCHEMA_VERSION,
            "sourceSha256": source_sha,
            "modelTag": model, "modelDigestVerified": False,
            "detectorBackend": detector,
            "rightsStatus": rights_status,
            "windowCount": len(windows), "windows": summaries,
            "maxSamplesPerWindow": max_samples,
            "maxLocalVisionCallsPerWindow": max_calls,
            "maxInteractionPairsPerWindow": max_pairs,
            "upperBoundModelCalls": len(windows) * (
                max_samples + max_calls + (max_pairs if interactions else 0)
                if detector == "ollama" else
                max_calls + (max_pairs if interactions else 0)),
            "totalCounts": totals,
            "status": "completed-multiple-independent-unverified-studies",
            "identityContinuityAcrossWindows": "not-established",
            "methodLimits": [
                "Totals count repeated window-local detections and tracklets, NOT unique characters or identities.",
                "Every child analyzes only selected source PTS frames; windows do not imply exhaustive video coverage.",
                "No cross-window character ID matching is performed, even if two windows are adjacent.",
                "Model predictions and actor-to-target interactions remain unverified and may be wrong.",
                "No claims are made about video segments outside the requested bounded windows.",
                "Source-prefix decoding still limits the final window end to 120 seconds.",
            ],
        }
        (staging / "batch-manifest.json").write_text(
            json.dumps(batch, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        require_unchanged(source, signature)
        if out.exists() or out.is_symlink():
            raise ValueError("batch output was occupied before publication")
        os.replace(staging, out)
    return out / "batch-manifest.json"
