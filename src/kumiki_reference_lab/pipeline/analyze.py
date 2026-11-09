"""Transactional analysis bundles with immutable, source-linked artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from kumiki_reference_lab.analyzers.media.contact_sheet import build_contact_sheet
from kumiki_reference_lab.analyzers.appearance.analyze import analyze_appearance
from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.media.timeline import analyze_frame_timeline
from kumiki_reference_lab.analyzers.motion.analyze import analyze_image_motion
from kumiki_reference_lab.analyzers.motion.dense import analyze_dense_flow
from kumiki_reference_lab.analyzers.motion.sparse import analyze_sparse_flow
from kumiki_reference_lab.analyzers.shots.detect import analyze_hard_cuts
from kumiki_reference_lab.analyzers.subjects.roi import analyze_roi_track
from kumiki_reference_lab.contracts.analysis import (
    ANALYSIS_RUN_VERSION, CONTACT_SHEET_VERSION, FRAME_TIMELINE_VERSION,
    IMAGE_MOTION_VERSION, ROI_TRACK_VERSION, SHOT_CANDIDATES_VERSION, SPARSE_FLOW_VERSION,
    APPEARANCE_VERSION, DENSE_FLOW_VERSION,
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
    "sparseFlow": "sparse-flow.json",
    "denseFlow": "dense-flow.json",
    "appearance": "appearance.json",
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
    expected_artifacts = {"inspect": _STAGES["inspect"],
                          "frames": _STAGES["frames"], "cuts": _STAGES["cuts"]}
    if settings["motion"]:
        expected_artifacts["motion"] = _STAGES["motion"]
    if settings["roi"] is not None:
        expected_artifacts["trackRoi"] = _STAGES["trackRoi"]
    if settings.get("sparseFlow", False):
        expected_artifacts["sparseFlow"] = _STAGES["sparseFlow"]
    if settings.get("denseFlow", False):
        expected_artifacts["denseFlow"] = _STAGES["denseFlow"]
    if settings.get("appearance", False):
        expected_artifacts["appearance"] = _STAGES["appearance"]
    artifacts = manifest.get("artifacts")
    if (not isinstance(artifacts, dict) or
            {key: value for key, value in artifacts.items() if key != "contactSheet"} != expected_artifacts or
            not isinstance(artifacts.get("contactSheet"), str) or
            len(PurePosixPath(artifacts["contactSheet"]).parts) != 3 or
            PurePosixPath(artifacts["contactSheet"]).parts[0] != "visual" or
            not PurePosixPath(artifacts["contactSheet"]).parts[1].startswith("contact-sheet-") or
            PurePosixPath(artifacts["contactSheet"]).parts[2] != "index.html" or
            manifest.get("catalogProposals") != [] or
            manifest.get("interpretationStatus") != "not-performed" or
            manifest.get("coverage") != "bounded-from-start-not-necessarily-full-video"):
        raise ValueError("analysis destination has altered stage metadata")
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
    if artifacts["contactSheet"] not in recorded_paths:
        raise ValueError("analysis destination contact sheet is absent from the inventory")
    source_report = json.loads((destination / _STAGES["inspect"]).read_text(encoding="utf-8"))
    if (manifest.get("sourceTimebase") != source_report.get("video", {}).get("sourceTimebase") or
            source_report.get("source", {}).get("sha256") != settings["sourceSha256"]):
        raise ValueError("analysis destination source provenance does not match")
    return manifest_path


def run_analysis(
    source: Path, output: Path, *, seconds: int = 10, thumbnails: int = 12,
    motion: bool = False, roi: tuple[float, float, float, float] | None = None,
    samples: int = 48, width: int = 160, height: int = 90,
    sparse_flow: bool = False, sparse_samples: int = 24,
    sparse_points: int = 40, sparse_radius: int = 8,
    sparse_correlation: float = 0.68, sparse_pyramid_levels: int = 1,
    sparse_subpixel_refinement: bool = False, sparse_subpixel_reverse_check: bool = False,
    sparse_lk_refinement: bool = False,
    sparse_quadrant_consistency: bool = False,
    sparse_projective_hypotheses: bool = False,
    sparse_tracklet_motion_consistency: bool = False,
    sparse_tracklet_appearance_consistency: bool = False,
    dense_flow: bool = False, dense_samples: int = 24,
    dense_grid_step: int = 12,
    appearance: bool = False, appearance_samples: int = 24,
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
    if not isinstance(sparse_flow, bool):
        raise ValueError("sparse_flow must be a boolean")
    if type(dense_flow) is not bool:
        raise ValueError("dense_flow must be a boolean")
    if dense_flow:
        if seconds > 20 or width > 240 or height > 135:
            raise ValueError("dense-flow requires seconds <=20, width <=240 and height <=135")
        if type(dense_samples) is not int or not 5 <= dense_samples <= 40:
            raise ValueError("dense-flow samples must be 5..40")
        if type(dense_grid_step) is not int or not 8 <= dense_grid_step <= 24:
            raise ValueError("dense-flow grid step must be 8..24")
    if sparse_flow:
        if seconds > 20 or width > 240 or height > 135:
            raise ValueError("sparse-flow requires seconds <=20, width <=240 and height <=135")
        if type(sparse_samples) is not int or not 5 <= sparse_samples <= 40:
            raise ValueError("sparse-flow samples must be 5..40")
        if type(sparse_points) is not int or not 4 <= sparse_points <= 64:
            raise ValueError("sparse-flow points must be 4..64")
        if type(sparse_radius) is not int or not 2 <= sparse_radius <= 12:
            raise ValueError("sparse-flow radius must be 2..12")
        if type(sparse_pyramid_levels) is not int or sparse_pyramid_levels not in (1, 2):
            raise ValueError("sparse-flow pyramid levels must be 1 or 2")
        if type(sparse_subpixel_refinement) is not bool:
            raise ValueError("sparse-flow subpixel refinement must be a boolean")
        if type(sparse_subpixel_reverse_check) is not bool or (sparse_subpixel_reverse_check and
                                                               not sparse_subpixel_refinement):
            raise ValueError("sparse-flow subpixel reverse check requires subpixel refinement")
        if type(sparse_lk_refinement) is not bool or (sparse_lk_refinement and
                                                     sparse_subpixel_refinement):
            raise ValueError("LK refinement cannot combine with subpixel peak refinement")
        if type(sparse_quadrant_consistency) is not bool:
            raise ValueError("sparse-flow quadrant consistency must be a boolean")
        if type(sparse_projective_hypotheses) is not bool:
            raise ValueError("sparse-flow projective hypotheses must be a boolean")
        if type(sparse_tracklet_motion_consistency) is not bool:
            raise ValueError("sparse-flow tracklet motion consistency must be a boolean")
        if type(sparse_tracklet_appearance_consistency) is not bool:
            raise ValueError("sparse-flow tracklet appearance consistency must be a boolean")
        if (not isinstance(sparse_correlation, (int, float)) or
                not 0 < sparse_correlation < 1):
            raise ValueError("sparse-flow correlation must be between zero and one")
    if not isinstance(appearance, bool):
        raise ValueError("appearance must be a boolean")
    if appearance:
        if seconds > 20 or width > 240 or height > 135:
            raise ValueError("appearance requires seconds <=20, width <=240 and height <=135")
        if type(appearance_samples) is not int or not 5 <= appearance_samples <= 40:
            raise ValueError("appearance samples must be 5..40")

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
    # Keep legacy/default run identity unchanged. Sparse-flow settings and its
    # version participate in the run hash only when that stage is requested.
    if sparse_flow:
        settings.update({"sparseFlow": True, "sparseSamples": sparse_samples,
                         "sparsePoints": sparse_points, "sparseRadius": sparse_radius,
                         "sparseCorrelation": float(sparse_correlation)})
        if sparse_pyramid_levels == 2:
            settings["sparsePyramidLevels"] = 2
        if sparse_subpixel_refinement:
            settings["sparseSubpixelRefinement"] = True
        if sparse_subpixel_reverse_check:
            settings["sparseSubpixelReverseCheck"] = True
        if sparse_lk_refinement:
            settings["sparseLkRefinement"] = True
        if sparse_quadrant_consistency:
            settings["sparseQuadrantConsistency"] = True
        if sparse_projective_hypotheses:
            settings["sparseProjectiveHypotheses"] = True
        if sparse_tracklet_motion_consistency:
            settings["sparseTrackletMotionConsistency"] = True
        if sparse_tracklet_appearance_consistency:
            settings["sparseTrackletAppearanceConsistency"] = True
        settings["versions"]["sparseFlow"] = SPARSE_FLOW_VERSION
    if dense_flow:
        settings.update({"denseFlow": True, "denseSamples": dense_samples,
                         "denseGridStep": dense_grid_step})
        settings["versions"]["denseFlow"] = DENSE_FLOW_VERSION
    if appearance:
        settings.update({"appearance": True, "appearanceSamples": appearance_samples})
        settings["versions"]["appearance"] = APPEARANCE_VERSION
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
        if sparse_flow:
            sparse = analyze_sparse_flow(
                source, seconds=seconds, max_samples=sparse_samples, width=width,
                height=height, max_points=sparse_points, radius=sparse_radius,
                correlation=sparse_correlation, threshold=threshold,
                pyramid_levels=sparse_pyramid_levels,
                subpixel_refinement=sparse_subpixel_refinement,
                subpixel_reverse_check=sparse_subpixel_reverse_check,
                lk_refinement=sparse_lk_refinement,
                quadrant_consistency=sparse_quadrant_consistency,
                projective_hypotheses=sparse_projective_hypotheses,
                tracklet_motion_consistency=sparse_tracklet_motion_consistency,
                tracklet_appearance_consistency=sparse_tracklet_appearance_consistency,
                ffmpeg=ffmpeg, ffprobe=ffprobe, rights_status=rights_status,
            )
            write_json_artifact(staging, _STAGES["sparseFlow"], sparse)
            artifacts["sparseFlow"] = _STAGES["sparseFlow"]
        if dense_flow:
            dense = analyze_dense_flow(source, seconds=seconds, max_samples=dense_samples,
                                       width=width, height=height, grid_step=dense_grid_step,
                                       threshold=threshold, ffmpeg=ffmpeg, ffprobe=ffprobe,
                                       rights_status=rights_status)
            write_json_artifact(staging, _STAGES["denseFlow"], dense)
            artifacts["denseFlow"] = _STAGES["denseFlow"]
        if appearance:
            report = analyze_appearance(
                source, seconds=seconds, max_samples=appearance_samples,
                width=width, height=height, threshold=threshold,
                ffmpeg=ffmpeg, ffprobe=ffprobe, rights_status=rights_status,
            )
            write_json_artifact(staging, _STAGES["appearance"], report)
            artifacts["appearance"] = _STAGES["appearance"]
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
