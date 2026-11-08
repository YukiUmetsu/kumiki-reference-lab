"""Thin CLI for repeatable local analysis without optional neural dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.media.timeline import analyze_frame_timeline
from kumiki_reference_lab.analyzers.shots.detect import analyze_hard_cuts
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.contracts.source import RIGHTS_STATUSES
from kumiki_reference_lab.core.artifacts import write_json_artifact


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            artifact = inspect_source(args.source, ffprobe=args.ffprobe,
                                      rights_status=args.rights_status)
            filename = "source-manifest.json"
        elif args.command == "frames":
            artifact = analyze_frame_timeline(args.source, seconds=args.max_seconds,
                                              ffprobe=args.ffprobe,
                                              rights_status=args.rights_status)
            filename = "frame-timeline.json"
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
