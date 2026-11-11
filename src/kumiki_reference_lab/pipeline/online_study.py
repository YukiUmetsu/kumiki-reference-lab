"""Reusable URL -> ephemeral video -> frame evidence -> visual reference JSON runner."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from kumiki_reference_lab.acquisition.online_video import (
    download_public_video, reference_id, require_rights, validate_watch_url,
)
from kumiki_reference_lab.pipeline.online_frames import analyze_all_frames
from kumiki_reference_lab.pipeline.online_semantics import analyze_visual_samples
from kumiki_reference_lab.pipeline.agent_frame_review import make_frame_sink, finalize_frame_workspace
from kumiki_reference_lab.pipeline.online_audio_cues import build_online_audio_cues

SCHEMA_VERSION = "kumiki.online-video-reference.v1"


def study_online_video(
    watch_url: str, repository_root: Path, *, rights_basis: str,
    rights_note: str, acknowledge_rights: bool = False,
    model: str | None = None, max_seconds: int = 180,
    max_frames: int = 10800, semantic_stride: int = 24,
    max_semantic_frames: int = 24, width: int = 192, height: int = 108,
    max_download_bytes: int = 200 * 1024 * 1024,
    port: int = 11434, overwrite: bool = False,
    review_frames: bool = False, max_review_bytes: int = 256 * 1024 * 1024,
    audio_cues: bool = False,
    yt_dlp: str = "yt-dlp", ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> Path:
    """Retain source-hashed JSON, never media or frame snapshots.

    If semantic model is omitted, typography/characters and style stay explicitly
    not-measured; numeric every-frame analysis still runs.
    """
    validate_watch_url(watch_url)
    require_rights(rights_basis, rights_note, acknowledged=acknowledge_rights)
    if type(model) not in (str, type(None)) or (model is not None and not model):
        raise ValueError("model must be a local Ollama model tag or omitted")
    if type(review_frames) is not bool or type(audio_cues) is not bool:
        raise ValueError("review_frames/audio_cues must be boolean")
    if not repository_root.is_dir() or not (repository_root / "pyproject.toml").is_file():
        raise ValueError("repository_root must be the project root")
    destination = repository_root / "research" / "analysis" / "online-videos"
    result_path = destination / f"{reference_id(watch_url)}.json"
    if (result_path.exists() or result_path.is_symlink()) and not overwrite:
        raise ValueError("reference already exists; pass --overwrite to re-analyze")
    with ExitStack() as resources:
        review_stage: Path | None = None
        review_destination: Path | None = None
        sink = None
        if review_frames:
            review_base = repository_root / "workspace"
            review_parent = review_base / "frame-review"
            if review_base.is_symlink() or review_parent.is_symlink():
                raise ValueError("local review path cannot be a symlink")
            review_parent.mkdir(parents=True, exist_ok=True)
            review_destination = review_parent / reference_id(watch_url)
            if review_destination.exists() or review_destination.is_symlink():
                raise ValueError("local frame workspace exists; clean it explicitly before replacing")
            review_stage = Path(resources.enter_context(
                tempfile.TemporaryDirectory(prefix=".agent-frames-", dir=review_parent)))
            sink = make_frame_sink(
                review_stage, max_bytes=max_review_bytes, max_frames=max_frames)
        with tempfile.TemporaryDirectory(prefix="kumiki-online-study-") as temp:
            workspace = Path(temp) / "source"
            workspace.mkdir()
            media = download_public_video(
                watch_url, workspace, rights_basis=rights_basis,
                rights_note=rights_note, acknowledge_rights=True,
                max_bytes=max_download_bytes, yt_dlp=yt_dlp,
            )
            numeric, samples = analyze_all_frames(
                media, max_seconds=max_seconds, max_frames=max_frames,
                semantic_stride=semantic_stride,
                max_semantic_frames=max_semantic_frames if model is not None else 0,
                width=width, height=height, ffmpeg=ffmpeg, ffprobe=ffprobe,
                frame_sink=sink,
            )
            audio = (build_online_audio_cues(
                media, max_seconds=max_seconds, ffmpeg=ffmpeg, ffprobe=ffprobe,
            ) if audio_cues else None)
            if audio is not None:
                audio["sourceSha256"] = numeric["sourceSha256"]
            semantics = (analyze_visual_samples(
                samples, model=model, port=port,
                cut_candidate_indices=tuple(numeric["cutCandidateFrameIndices"]),
            ) if model is not None else [])
            document: dict[str, Any] = {
                "schemaVersion": SCHEMA_VERSION,
                "id": reference_id(watch_url),
                "source": {
                    "watchUrl": watch_url,
                    "sourceSha256": numeric["sourceSha256"],
                    "video": numeric["video"],
                    "rightsBasis": rights_basis,
                    "rightsStatus": "operator-declared-review-required",
                    "mediaRetained": False,
                },
                "numericEvidence": numeric,
                "audioEvidence": audio,
                "semanticObservations": semantics,
                "semanticModel": model,
                "semanticStatus": ("unreviewed-local-vision-hypotheses"
                                   if model is not None else "not-measured"),
                "creativeReference": {
                    "purpose": "inspiration-not-reproduction",
                    "measuredFrameCount": numeric["frameCount"],
                    "observedAnimation": sorted({
                        term for s in semantics for term in s["observations"]["animation"]
                        if term
                    }),
                    "typographyNotes": sorted({
                        s["observations"]["typography"]["style"] for s in semantics
                        if s["observations"]["typography"]["style"]
                    }),
                    "visualStyles": sorted({
                        s["observations"]["visualStyle"] for s in semantics
                        if s["observations"]["visualStyle"]
                    }),
                    "characterAppearanceNotes": [
                        {"frameIndex": s["frameIndex"], "look": c["look"],
                         "action": c["action"]}
                        for s in semantics for c in s["observations"]["characters"]
                    ],
                    "reviewStatus": "unreviewed-machine-proposals",
                },
                "limitations": [
                    "URL is a locator; content identity is grounded by downloaded source SHA-256.",
                    "Not all video sites provide extractable public media; DRM and access controls are not bypassed.",
                    "No source videos, images, audio or model prompts are retained in Git.",
                    "Sampled semantic images do not imply semantic understanding of every frame.",
                    "Motion numbers are frame-difference proxies, not definitive object or camera tracks.",
                    "Semantic descriptions require human review before reuse or exact font/style claims.",
                    "Only configured duration and frame limits are decoded; inspect coverage before claiming entire film.",
                    "Research and private use alone are not proof of download permission.",
                ],
            }
        # Source media and semantic sample PNGs are out of scope, deleted on BOTH
        # success and failures before publishing any result.
        destination.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink() or result_path.is_symlink():
            raise ValueError("symlink output destination forbidden")
        payload = (json.dumps(document, indent=2, sort_keys=True,
                              ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", prefix=".online-study-",
                                             suffix=".tmp", dir=destination,
                                             delete=False) as staged:
                name = staged.name
                staged.write(payload)
                staged.flush()
                os.fsync(staged.fileno())
            if result_path.exists() and not overwrite:
                raise ValueError("reference became occupied during publishing")
            os.replace(name, result_path)
            name = None
        finally:
            if name is not None:
                Path(name).unlink(missing_ok=True)
        if review_stage is not None:
            assert review_destination is not None
            finalize_frame_workspace(
                review_stage, study_id=reference_id(watch_url), watch_url=watch_url,
                numeric=numeric, preview_width=width, preview_height=height,
            )
            os.replace(review_stage, review_destination)
        return result_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze a lawful online video frame-by-frame and retain JSON only."
    )
    parser.add_argument("url", help="public HTTPS video page on any website")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--rights-basis", required=True, choices=[
        "own-original-work", "written-permission", "permissive-license",
        "other-lawful-authorization",
    ])
    parser.add_argument("--rights-note", required=True,
                        help="brief description of authorization (not stored in Git)")
    parser.add_argument("--acknowledge-rights", action="store_true")
    parser.add_argument("--model", help="optional local Ollama vision model")
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--max-seconds", type=int, default=180)
    parser.add_argument("--max-frames", type=int, default=10800)
    parser.add_argument("--semantic-stride", type=int, default=24)
    parser.add_argument("--max-semantic-frames", type=int, default=24)
    parser.add_argument("--width", type=int, default=192)
    parser.add_argument("--height", type=int, default=108)
    parser.add_argument("--max-download-bytes", type=int, default=200 * 1024 * 1024)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--audio-cues", action="store_true",
                        help="measure bounded PCM energy/transients before source cleanup")
    parser.add_argument("--review-frames", action="store_true",
                        help="save all low-resolution frame previews only in ignored workspace/")
    parser.add_argument("--max-review-bytes", type=int, default=256 * 1024 * 1024)
    parser.add_argument("--yt-dlp", default="yt-dlp")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        path = study_online_video(
            args.url, args.repo, rights_basis=args.rights_basis,
            rights_note=args.rights_note, acknowledge_rights=args.acknowledge_rights,
            model=args.model, port=args.port, max_seconds=args.max_seconds,
            max_frames=args.max_frames, semantic_stride=args.semantic_stride,
            max_semantic_frames=args.max_semantic_frames,
            width=args.width, height=args.height,
            max_download_bytes=args.max_download_bytes, overwrite=args.overwrite,
            review_frames=args.review_frames, max_review_bytes=args.max_review_bytes,
            audio_cues=args.audio_cues,
            yt_dlp=args.yt_dlp, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
        )
    except (ValueError, OSError) as exc:
        raise SystemExit(f"online study failed: {exc}") from exc
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
