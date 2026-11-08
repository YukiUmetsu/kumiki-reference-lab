"""Atomic, idempotent JSON artifact publishing without silent replacement."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_json_artifact(directory: Path, filename: str, value: Any) -> Path:
    if not filename.endswith(".json") or Path(filename).name != filename:
        raise ValueError("artifact filename must be a plain .json name")
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / filename
    if destination.exists():
        if destination.is_file() and destination.read_text(encoding="utf-8") == payload:
            return destination
        raise ValueError("artifact already exists with different content; choose a new --out")

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=directory,
            prefix=f".{filename}-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.is_file() and destination.read_text(encoding="utf-8") == payload:
                return destination
            raise ValueError("artifact already exists with different content; choose a new --out")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination
