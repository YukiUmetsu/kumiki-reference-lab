"""Transactional analysis bundles with immutable, source-linked artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from kumiki_reference_lab.analyzers.media.contact_sheet import build_contact_sheet
from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.media.timeline import analyze_frame_timeline
from kumiki_reference_lab.analyzers.motion.analyze import analyze_image_motion
from kumiki_reference_lab.analyzers.shots.detect import analyze_hard_cuts
from kumiki_reference_lab.analyzers.subjects.roi import analyze_roi_track
from kumiki_reference_lab.contracts.analysis import (
    ANALYSIS_RUN_VERSION, CONTACT_SHEET_VERSION, FRAME_TIMELINE_VERSION,
    IMAGE_MOTION_VERSION, ROI_TRACK_VERSION, SHOT_CANDIDATES_VERSION,
)
from kumiki_reference_lab.contracts.source import SCHEMA_VERSION as SOURCE_MANIFEST_VERSION
from kumiki_reference_lab.core.artifacts import write_json_artifact
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged


_STAGES = {
    "inspect": "source-manifest.json",
    "frames": "frame-timeline.json",
    "cuts": "shot-candidates.json",
    "motion": "image-motion.json",
    "trackRoi": "roi-track.json",
}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _file_records(folder: Path) -> list[dict[str, str]]:
    records = []
    for path in sorted(folder.rglob("*")):
        if path.is_symlink():
            raise ValueError("analysis output contains a symbolic link")
        if path.is_file():
            records.append({"path": path.relative_to(folder).as_posix(),
                            "sha256": sha256_file(path)})
    return records


def _validate_existing(destination: Path, settings: dict[str, Any]) -> Path:
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError("analysis destination exists but is not a regular directory")
    manifest_path = destination / "analysis-run.json"
    if (not manifest_path.is_file() or manifest_path.is_symlink() or
            manifest_path.stat().st_size > 262_144):
        raise ValueError("analysis destination has no valid run manifest")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("analysis destination has invalid JSON") from exc
    if (not isinstance(manifest, dict) or manifest.get("schemaVersion") != ANALYSIS_RUN_VERSION or
            manifest.get("settings") != settings):
        raise ValueError("analysis destination has mismatched run settings")
    recorded = manifest.get("files")
    if not isinstance(recorded, list) or not recorded:
        raise ValueError("analysis destination has no file inventory")
    # Reject symlinks and enumerate all children before reading paths supplied
    # by the cached manifest itself.
    actual_paths = {item["path"] for item in _file_records(destination)} - {"analysis-run.json"}
    recorded_paths: set[str] = set()
    for item in recorded:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("analysis destination has an invalid inventory entry")
        relative = PurePosixPath(item["path"])
        if (relative.is_absolute() or any(part in (".", "..") for part in relative.parts) or
                not relative.parts or len(item["path"]) > 4096):
            raise ValueError("analysis destination contains an unsafe artifact path")
        if item["path"] in recorded_paths:
            raise ValueError("analysis destination lists duplicate artifact paths")
        recorded_paths.add(item["path"])
        actual = destination / Path(*relative.parts)
        if not actual.is_file() or actual.is_symlink() or sha256_file(actual) != item.get("sha256"):
            raise ValueError("analysis destination has missing or modified artifacts")
    # Do not silently accept extra/corrupt files not listed in the manifest.
    if actual_paths != recorded_paths:
        raise ValueError("analysis destination contains untracked artifacts")
    return manifest_path


def run_analysis(
    source: Path, output: Path, *, seconds: int = 10, thumbnails: int = 12,
    motion: bool = False, roi: tuple[float, float, float, float] | None = None,
    samples: int = 48, width: int = 160, height: int = 90,
    threshold: float = 0.25, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
) -> Path:
    """Assemble all requested stages; publish only after everything succeeds."""
    if type(seconds) is not int or not 1 <= seconds <= 30:
        raise ValueError("seconds must be between 1 and 30")
    if type(thumbnails) is not int or not 2 <= thumbnails <= 24:
        raise ValueError("thumbnail count must be between 2 and 24")
    if type(samples) is not int or not 5 <= samples <= 120:
        raise ValueError("motion sample count must be between 5 and 120")
    if type(width) is not int or type(height) is not int or not 64 <= width <= 320 or not 36 <= height <= 180:
        raise ValueError("analysis width/height are out of range")
    if not isinstance(motion, bool):
        raise ValueError("motion must be a boolean")

    signature = file_signature(source)
    inspected = inspect_source(source, rights_status=rights_status, ffprobe=ffprobe)
    settings: dict[str, Any] = {
        "sourceSha256": inspected["source"]["sha256"],
        "streamIndex": inspected["video"]["streamIndex"],
        "seconds": seconds, "thumbnails": thumbnails, "motion": motion,
        "roi": list(roi) if roi is not None else None,
        "samples": samples, "width": width, "height": height,
        "cutThreshold": threshold, "ffmpeg": ffmpeg, "ffprobe": ffprobe,
        "rightsStatus": rights_status,
        "versions": {"run": ANALYSIS_RUN_VERSION,
                     "source": SOURCE_MANIFEST_VERSION,
                     "frames": FRAME_TIMELINE_VERSION, "cuts": SHOT_CANDIDATES_VERSION,
                     "contact": CONTACT_SHEET_VERSION, "motion": IMAGE_MOTION_VERSION,
                     "roi": ROI_TRACK_VERSION},
    }
    run_hash = hashlib.sha256(_json_bytes(settings)).hexdigest()[:20]
    destination = output / f"analysis-{settings['sourceSha256'][:12]}-{run_hash}"
    output.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        require_unchanged(source, signature)
        return _validate_existing(destination, settings)

    with tempfile.TemporaryDirectory(prefix=".analysis-", dir=output) as staging_name:
        staging = Path(staging_name)
        artifacts: dict[str, str] = {}
        write_json_artifact(staging, _STAGES["inspect"], inspected)
        artifacts["inspect"] = _STAGES["inspect"]

        frames = analyze_frame_timeline(source, seconds=seconds,
                                        ffprobe=ffprobe, rights_status=rights_status)
        write_json_artifact(staging, _STAGES["frames"], frames)
        artifacts["frames"] = _STAGES["frames"]

        cuts = analyze_hard_cuts(source, seconds=seconds, threshold=threshold,
                                 ffmpeg=ffmpeg, ffprobe=ffprobe,
                                 rights_status=rights_status)
        write_json_artifact(staging, _STAGES["cuts"], cuts)
        artifacts["cuts"] = _STAGES["cuts"]

        gallery = build_contact_sheet(
            source, staging / "visual", seconds=seconds, limit=thumbnails,
            threshold=threshold, ffmpeg=ffmpeg, ffprobe=ffprobe,
            rights_status=rights_status,
        )
        artifacts["contactSheet"] = gallery.relative_to(staging).as_posix()

        if motion:
            motions = analyze_image_motion(
                source, seconds=seconds, max_samples=samples, width=width,
                height=height, threshold=threshold, ffmpeg=ffmpeg,
                ffprobe=ffprobe, rights_status=rights_status,
            )
            write_json_artifact(staging, _STAGES["motion"], motions)
            artifacts["motion"] = _STAGES["motion"]
        if roi is not None:
            tracked = analyze_roi_track(
                source, roi, seconds=seconds, max_samples=samples, width=width,
                height=height, cut_threshold=threshold, ffmpeg=ffmpeg,
                ffprobe=ffprobe, rights_status=rights_status,
            )
            write_json_artifact(staging, _STAGES["trackRoi"], tracked)
            artifacts["trackRoi"] = _STAGES["trackRoi"]
        require_unchanged(source, signature)

        manifest = {
            "schemaVersion": ANALYSIS_RUN_VERSION,
            "settings": settings,
            "sourceTimebase": inspected["video"]["sourceTimebase"],
            "coverage": "bounded-from-start-not-necessarily-full-video",
            "artifacts": artifacts,
            "files": _file_records(staging),
            "catalogProposals": [],
            "interpretationStatus": "not-performed",
        }
        write_json_artifact(staging, "analysis-run.json", manifest)
        if destination.exists() or destination.is_symlink():
            return _validate_existing(destination, settings)
        try:
            os.rename(staging, destination)
        except FileExistsError:
            return _validate_existing(destination, settings)
    return destination / "analysis-run.json"
