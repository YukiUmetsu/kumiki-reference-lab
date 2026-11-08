"""Thin CLI for repeatable local analysis without optional neural dependencies."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.contracts.source import RIGHTS_STATUSES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kumiki-ref", description="Kumiki Reference Lab")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="inspect a local video, without AI")
    inspect.add_argument("source", type=Path)
    inspect.add_argument("--out", type=Path, help="output directory for source-manifest.json")
    inspect.add_argument("--ffprobe", default="ffprobe", help="ffprobe executable or path")
    inspect.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        manifest = inspect_source(args.source, ffprobe=args.ffprobe, rights_status=args.rights_status)
        payload = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.out is None:
            sys.stdout.write(payload)
            return 0
        args.out.mkdir(parents=True, exist_ok=True)
        destination = args.out / "source-manifest.json"
        if destination.exists():
            if destination.is_file() and destination.read_text(encoding="utf-8") == payload:
                print(str(destination))
                return 0
            raise ValueError("manifest already exists with different content; choose a new --out")

        # Publish a complete manifest atomically, without replacing another
        # process's output. The temporary file and destination share a volume.
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=args.out,
                prefix=".source-manifest-", suffix=".tmp", delete=False,
            ) as file:
                temporary = Path(file.name)
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if (destination.is_file() and
                        destination.read_text(encoding="utf-8") == payload):
                    print(str(destination))
                    return 0
                raise ValueError("manifest already exists with different content; choose a new --out")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(str(destination))
        return 0
    except (OSError, ValueError, ProbeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
