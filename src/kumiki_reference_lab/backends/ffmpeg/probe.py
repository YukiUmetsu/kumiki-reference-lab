"""FFprobe adapter. Arguments are a list; no shell or network retrieval."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class ProbeError(ValueError):
    """Invalid media, unavailable ffprobe, or unsupported probe output."""


def probe_media(path: Path, *, ffprobe: str = "ffprobe", timeout: float = 30) -> dict[str, Any]:
    args = [
        ffprobe,
        "-v", "error",
        "-show_format", "-show_streams",
        "-of", "json",
        "-i", str(path.resolve()),
    ]
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
    except FileNotFoundError as exc:
        raise ProbeError("ffprobe executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("ffprobe timed out") from exc
    except OSError as exc:
        raise ProbeError("ffprobe could not start") from exc

    if result.returncode != 0:
        # Tool output can include private paths and filenames; do not echo it.
        raise ProbeError(f"ffprobe failed (exit code {result.returncode})")
    if len(result.stdout) > 8_000_000:
        raise ProbeError("ffprobe metadata exceeded the expected size limit")
    try:
        decoded = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError("ffprobe returned invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise ProbeError("ffprobe returned an unexpected JSON document")
    return decoded
