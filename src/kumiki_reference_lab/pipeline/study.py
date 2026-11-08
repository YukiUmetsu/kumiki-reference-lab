"""One-command, resumable reference study with atomic derived review outputs."""

from __future__ import annotations

import hashlib
import html
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.analyzers.shots.evidence import build_shot_evidence
from kumiki_reference_lab.analyzers.shots.gallery import build_shot_gallery
from kumiki_reference_lab.analyzers.techniques.propose import propose_techniques
from kumiki_reference_lab.analyzers.techniques.review import build_technique_review
from kumiki_reference_lab.core.artifacts import write_json_artifact
from kumiki_reference_lab.contracts.analysis import (
    REFERENCE_STUDY_VERSION, REFERENCE_STUDY_V1_VERSION,
)
from kumiki_reference_lab.pipeline.analyze import _file_records, _json_bytes, run_analysis


STUDY_VERSION = REFERENCE_STUDY_VERSION


def _verify_study(destination: Path, settings: dict[str, Any]) -> Path:
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError("study output is not a regular directory")
    manifest = destination / "study-manifest.json"
    if not manifest.is_file() or manifest.is_symlink() or manifest.stat().st_size > 262_144:
        raise ValueError("study output has no valid manifest")
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("study manifest JSON is unreadable") from exc
    version = payload.get("schemaVersion") if isinstance(payload, dict) else None
    if (version not in (REFERENCE_STUDY_V1_VERSION, STUDY_VERSION) or
            payload.get("settings") != settings or
            settings.get("studyVersion") != version or
            payload.get("qualityVerdict") != "not-performed" or
            payload.get("humanReviewStatus") != "unreviewed"):
        raise ValueError("study settings or review status were modified")
    artifacts = payload.get("artifacts")
    expected_keys = ({"techniqueProposals", "shotEvidence", "reviewGallery"}
                     if version == REFERENCE_STUDY_V1_VERSION else
                     {"techniqueProposals", "shotEvidence", "reviewGallery",
                      "shotGallery", "studyOverview"})
    if (not isinstance(artifacts, dict) or set(artifacts) != expected_keys or
            artifacts.get("techniqueProposals") != "technique-proposals.json" or
            artifacts.get("shotEvidence") != "shot-evidence.json"):
        raise ValueError("study artifact mapping was modified")
    def valid_gallery(value: Any, prefix: str) -> bool:
        if not isinstance(value, str):
            return False
        parts = PurePosixPath(value).parts
        return (len(parts) == 3 and parts[0] == "visual" and
                parts[1].startswith(prefix) and parts[2] == "index.html")

    gallery = artifacts["reviewGallery"]
    if not valid_gallery(gallery, "technique-review-"):
        raise ValueError("study technique gallery path is unsafe")
    expected = {"technique-proposals.json", "shot-evidence.json", gallery}
    if version == STUDY_VERSION:
        if (not valid_gallery(artifacts["shotGallery"], "shot-gallery-") or
                artifacts["studyOverview"] != "index.html"):
            raise ValueError("study shot gallery or overview path is unsafe")
        expected.update(("index.html", artifacts["shotGallery"]))
    actual = _file_records(destination)
    actual = [item for item in actual if item["path"] != "study-manifest.json"]
    records = payload.get("files")
    if (not isinstance(records, list) or records != actual or
            not expected.issubset({item["path"] for item in actual})):
        raise ValueError("study output contains missing, altered or untracked files")
    if (sha256_file(destination / "technique-proposals.json") !=
            settings["proposalsSha256"] or
            sha256_file(destination / "shot-evidence.json") !=
            settings["shotEvidenceSha256"]):
        raise ValueError("study evidence does not match its verified identity")
    return destination / artifacts.get("studyOverview", gallery)


def study_reference(
    source: Path, output: Path, *, catalog_root: Path,
    seconds: int = 10, thumbnails: int = 8, max_cues: int = 8,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
) -> Path:
    """Compose verified evidence stages without modifying an existing analysis run.

    A failed derived study may leave a *complete, reusable* analysis bundle,
    but never publishes a partial study directory.
    """
    if type(seconds) is not int or not 1 <= seconds <= 20:
        raise ValueError("study seconds must be 1..20")
    if type(thumbnails) is not int or not 2 <= thumbnails <= 24:
        raise ValueError("study thumbnails must be 2..24")
    if type(max_cues) is not int or not 1 <= max_cues <= 8:
        raise ValueError("study max_cues must be 1..8")
    # 160x90 samples and 10-second default are safe on an Apple M4/24 GiB.
    # Numeric stages are opt-in only through this explicit study command.
    analysis = run_analysis(
        source, output / "analysis", seconds=seconds, thumbnails=thumbnails,
        motion=True, sparse_flow=True, appearance=True,
        samples=24, sparse_samples=12, sparse_points=40,
        appearance_samples=12, width=160, height=90,
        ffmpeg=ffmpeg, ffprobe=ffprobe, rights_status=rights_status,
    )
    proposals = propose_techniques(analysis, catalog_root)
    evidence = build_shot_evidence(analysis)
    proposals_sha = hashlib.sha256((json.dumps(proposals, indent=2, sort_keys=True,
                                              ensure_ascii=False) + "\n").encode("utf-8")).hexdigest()
    evidence_sha = hashlib.sha256((json.dumps(evidence, indent=2, sort_keys=True,
                                             ensure_ascii=False) + "\n").encode("utf-8")).hexdigest()
    settings = {
        "sourceSha256": proposals["source"]["sha256"],
        "analysisRunDirectory": analysis.parent.name,
        "analysisRunSha256": proposals["provenance"]["analysisRunSha256"],
        "catalogEntries": proposals["provenance"]["catalogEntries"],
        "proposalsSha256": proposals_sha,
        "shotEvidenceSha256": evidence_sha,
        "seconds": seconds, "thumbnails": thumbnails, "maxCues": max_cues,
        "ffmpeg": ffmpeg, "ffprobe": ffprobe, "rightsStatus": rights_status,
        "sampling": {"motion": 24, "sparse": 12, "appearance": 12,
                     "sparsePoints": 40, "width": 160, "height": 90},
        "studyVersion": STUDY_VERSION,
    }
    digest = hashlib.sha256(_json_bytes(settings)).hexdigest()[:16]
    destination = output / f"study-{settings['sourceSha256'][:12]}-{digest}"
    output.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        return _verify_study(destination, settings)
    with tempfile.TemporaryDirectory(prefix=".study-", dir=output) as name:
        staging = Path(name)
        write_json_artifact(staging, "technique-proposals.json", proposals)
        write_json_artifact(staging, "shot-evidence.json", evidence)
        gallery = build_technique_review(
            source, analysis, staging / "visual", catalog_root=catalog_root,
            max_cues=max_cues, ffmpeg=ffmpeg, ffprobe=ffprobe,
        )
        shot_gallery = build_shot_gallery(
            source, analysis, staging / "visual",
            max_regions=8, width=480, ffmpeg=ffmpeg, ffprobe=ffprobe,
        )
        artifact_paths = {
            "techniqueProposals": "technique-proposals.json",
            "shotEvidence": "shot-evidence.json",
            "reviewGallery": gallery.relative_to(staging).as_posix(),
            "shotGallery": shot_gallery.relative_to(staging).as_posix(),
            "studyOverview": "index.html",
        }
        (staging / "index.html").write_text(
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Kumiki reference study</title>'
            '<style>body{font:18px system-ui;background:#0b111b;color:#f2f7ff;'
            'max-width:880px;margin:10vh auto;padding:20px;line-height:1.6}'
            'a{color:#98d1ff}li{margin:16px 0}</style></head>'
            '<body><h1>Cinematic reference study</h1><p>Verified source-image '
            'measurements are separate from interpretations. Neither gallery '
            'establishes physical camera/light rigs, artistic intent or quality.</p>'
            '<ul><li><a href="' +
            html.escape(artifact_paths["shotGallery"], quote=True) +
            '">Shot storyboard: chronological composition and story questions</a></li>'
            '<li><a href="' +
            html.escape(artifact_paths["reviewGallery"], quote=True) +
            '">Technique cues: measured movement/appearance hypotheses</a></li></ul>'
            '<p>Review the full original video, annotate evidence in a separate '
            'review-notes.json draft, and require human approval after rendering.</p>'
            '</body></html>\n', encoding="utf-8")
        write_json_artifact(staging, "study-manifest.json", {
            "schemaVersion": STUDY_VERSION, "settings": settings,
            "artifacts": artifact_paths, "files": _file_records(staging),
            "humanReviewStatus": "unreviewed", "qualityVerdict": "not-performed",
        })
        if destination.exists() or destination.is_symlink():
            return _verify_study(destination, settings)
        try:
            os.rename(staging, destination)
        except FileExistsError:
            return _verify_study(destination, settings)
    return destination / artifact_paths["studyOverview"]
