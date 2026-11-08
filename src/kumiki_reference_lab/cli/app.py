"""Thin CLI for repeatable local analysis without optional neural dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.media.contact_sheet import build_contact_sheet
from kumiki_reference_lab.analyzers.motion.analyze import analyze_image_motion
from kumiki_reference_lab.analyzers.motion.sparse import analyze_sparse_flow
from kumiki_reference_lab.analyzers.subjects.roi import analyze_roi_track
from kumiki_reference_lab.analyzers.media.timeline import analyze_frame_timeline
from kumiki_reference_lab.analyzers.shots.detect import analyze_hard_cuts
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.catalog.store import build_catalog_index, load_catalog, search_catalog
from kumiki_reference_lab.contracts.source import RIGHTS_STATUSES
from kumiki_reference_lab.core.artifacts import write_json_artifact
from kumiki_reference_lab.pipeline.analyze import run_analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kumiki-ref", description="Kumiki Reference Lab")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="inspect a local video, without AI")
    inspect.add_argument("source", type=Path)
    inspect.add_argument("--out", type=Path, help="output directory for source-manifest.json")
    inspect.add_argument("--ffprobe", default="ffprobe", help="ffprobe executable or path")
    inspect.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    frames = commands.add_parser("frames", help="extract bounded source presentation timestamps")
    frames.add_argument("source", type=Path)
    frames.add_argument("--out", type=Path)
    frames.add_argument("--max-seconds", type=int, default=60)
    frames.add_argument("--ffprobe", default="ffprobe")
    frames.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    cuts = commands.add_parser("cuts", help="find bounded hard-cut candidates")
    cuts.add_argument("source", type=Path)
    cuts.add_argument("--out", type=Path)
    cuts.add_argument("--max-seconds", type=int, default=60)
    cuts.add_argument("--threshold", type=float, default=0.25)
    cuts.add_argument("--ffmpeg", default="ffmpeg")
    cuts.add_argument("--ffprobe", default="ffprobe")
    cuts.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    sheet = commands.add_parser("contact-sheet", help="create bounded timecoded JPEG/HTML evidence")
    sheet.add_argument("source", type=Path)
    sheet.add_argument("--out", type=Path, required=True, help="parent directory for immutable bundle")
    sheet.add_argument("--max-seconds", type=int, default=30)
    sheet.add_argument("--max-thumbnails", type=int, default=12)
    sheet.add_argument("--width", type=int, default=480)
    sheet.add_argument("--threshold", type=float, default=0.25)
    sheet.add_argument("--ffmpeg", default="ffmpeg")
    sheet.add_argument("--ffprobe", default="ffprobe")
    sheet.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    motion = commands.add_parser("motion", help="measure sampled global image-plane translation")
    motion.add_argument("source", type=Path)
    motion.add_argument("--out", type=Path)
    motion.add_argument("--max-seconds", type=int, default=10)
    motion.add_argument("--max-samples", type=int, default=48)
    motion.add_argument("--width", type=int, default=160)
    motion.add_argument("--height", type=int, default=90)
    motion.add_argument("--threshold", type=float, default=0.25)
    motion.add_argument("--ffmpeg", default="ffmpeg")
    motion.add_argument("--ffprobe", default="ffprobe")
    motion.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    roi = commands.add_parser("track-roi", help="track a manually seeded textured image region")
    roi.add_argument("source", type=Path)
    roi.add_argument("--box", type=float, nargs=4, required=True,
                     metavar=("X", "Y", "WIDTH", "HEIGHT"),
                     help="normalized bounding box on the first sampled frame")
    roi.add_argument("--out", type=Path)
    roi.add_argument("--max-seconds", type=int, default=10)
    roi.add_argument("--max-samples", type=int, default=48)
    roi.add_argument("--width", type=int, default=160)
    roi.add_argument("--height", type=int, default=90)
    roi.add_argument("--radius", type=int, default=12)
    roi.add_argument("--correlation", type=float, default=0.62)
    roi.add_argument("--threshold", type=float, default=0.25)
    roi.add_argument("--ffmpeg", default="ffmpeg")
    roi.add_argument("--ffprobe", default="ffprobe")
    roi.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    sparse = commands.add_parser("sparse-flow", help="track distributed 2D features and motion groups")
    sparse.add_argument("source", type=Path)
    sparse.add_argument("--out", type=Path)
    sparse.add_argument("--max-seconds", type=int, default=10)
    sparse.add_argument("--max-samples", type=int, default=24)
    sparse.add_argument("--width", type=int, default=160)
    sparse.add_argument("--height", type=int, default=90)
    sparse.add_argument("--max-points", type=int, default=40)
    sparse.add_argument("--radius", type=int, default=8)
    sparse.add_argument("--correlation", type=float, default=0.68)
    sparse.add_argument("--threshold", type=float, default=0.25)
    sparse.add_argument("--ffmpeg", default="ffmpeg")
    sparse.add_argument("--ffprobe", default="ffprobe")
    sparse.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    analyze = commands.add_parser("analyze", help="run a bounded, atomic multi-stage reference analysis")
    analyze.add_argument("source", type=Path)
    analyze.add_argument("--out", type=Path, required=True, help="parent directory for immutable run")
    analyze.add_argument("--max-seconds", type=int, default=10)
    analyze.add_argument("--thumbnails", type=int, default=12)
    analyze.add_argument("--motion", action="store_true", help="include optional NumPy motion measurements")
    analyze.add_argument("--box", type=float, nargs=4,
                         metavar=("X", "Y", "WIDTH", "HEIGHT"),
                         help="optional seeded ROI in normalized image coordinates")
    analyze.add_argument("--max-samples", type=int, default=48)
    analyze.add_argument("--width", type=int, default=160)
    analyze.add_argument("--height", type=int, default=90)
    analyze.add_argument("--threshold", type=float, default=0.25)
    analyze.add_argument("--ffmpeg", default="ffmpeg")
    analyze.add_argument("--ffprobe", default="ffprobe")
    analyze.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    catalog = commands.add_parser("catalog", help="search and validate cinematic technique research")
    catalog_actions = catalog.add_subparsers(dest="catalog_action", required=True)
    for action in ("validate", "search", "index"):
        sub = catalog_actions.add_parser(action)
        sub.add_argument("--root", type=Path, default=Path("catalog/entries"),
                         help="canonical technique JSON directory")
        if action == "search":
            sub.add_argument("query", help="free-text intent or visual technique query")
            sub.add_argument("--limit", type=int, default=20)
        elif action == "index":
            sub.add_argument("--out", type=Path, required=True,
                             help="directory for immutable catalog-index.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            entries = load_catalog(args.root)
            if args.catalog_action == "validate":
                print(json.dumps({"valid": True, "entryCount": len(entries)}, sort_keys=True))
            elif args.catalog_action == "search":
                print(json.dumps({"query": args.query, "results": search_catalog(
                    entries, args.query, args.limit)}, indent=2, sort_keys=True))
            else:
                destination = write_json_artifact(args.out, "catalog-index.json",
                                                  build_catalog_index(entries))
                print(str(destination))
            return 0
        if args.command == "analyze":
            manifest = run_analysis(
                args.source, args.out, seconds=args.max_seconds, thumbnails=args.thumbnails,
                motion=args.motion, roi=(tuple(args.box) if args.box is not None else None),
                samples=args.max_samples, width=args.width, height=args.height,
                threshold=args.threshold, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
                rights_status=args.rights_status,
            )
            print(str(manifest))
            return 0
        if args.command == "contact-sheet":
            index = build_contact_sheet(
                args.source, args.out, seconds=args.max_seconds,
                limit=args.max_thumbnails, width=args.width, threshold=args.threshold,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, rights_status=args.rights_status,
            )
            print(str(index))
            return 0
        if args.command == "inspect":
            artifact = inspect_source(args.source, ffprobe=args.ffprobe,
                                      rights_status=args.rights_status)
            filename = "source-manifest.json"
        elif args.command == "frames":
            artifact = analyze_frame_timeline(args.source, seconds=args.max_seconds,
                                              ffprobe=args.ffprobe,
                                              rights_status=args.rights_status)
            filename = "frame-timeline.json"
        elif args.command == "motion":
            artifact = analyze_image_motion(
                args.source, seconds=args.max_seconds, max_samples=args.max_samples,
                width=args.width, height=args.height, threshold=args.threshold,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, rights_status=args.rights_status,
            )
            filename = "image-motion.json"
        elif args.command == "track-roi":
            artifact = analyze_roi_track(
                args.source, tuple(args.box), seconds=args.max_seconds,
                max_samples=args.max_samples, width=args.width, height=args.height,
                radius=args.radius, correlation=args.correlation, cut_threshold=args.threshold,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, rights_status=args.rights_status,
            )
            filename = "roi-track.json"
        elif args.command == "sparse-flow":
            artifact = analyze_sparse_flow(
                args.source, seconds=args.max_seconds, max_samples=args.max_samples,
                width=args.width, height=args.height, max_points=args.max_points,
                radius=args.radius, correlation=args.correlation, threshold=args.threshold,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, rights_status=args.rights_status,
            )
            filename = "sparse-flow.json"
        else:
            artifact = analyze_hard_cuts(args.source, seconds=args.max_seconds,
                                         threshold=args.threshold, ffmpeg=args.ffmpeg,
                                         ffprobe=args.ffprobe, rights_status=args.rights_status)
            filename = "shot-candidates.json"
        payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.out is None:
            sys.stdout.write(payload)
            return 0
        destination = write_json_artifact(args.out, filename, artifact)
        print(str(destination))
        return 0
    except (OSError, ValueError, ProbeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
