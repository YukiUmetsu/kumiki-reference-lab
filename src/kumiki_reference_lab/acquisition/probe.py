"""Bounded ffprobe adapters for remote and local media metadata.

All probes are read-only, time-bounded, and retried a small fixed number of
times. The ranged fallback writes a bounded prefix into an ephemeral directory
that is deleted before the call returns; only numeric metadata survives.
"""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.backends.ffmpeg.probe import probe_media

from .media import _freeze_hosts, allowlisted_url, fetch_bytes, media_target

# One bounded ranged read is used only to characterise a direct download whose
# full remote probe is flaky; the bytes live in a temporary directory.
RANGED_PROBE_BYTES = 2 * 1024 * 1024
MAX_RANGED_PROBE_BYTES = 8 * 1024 * 1024

# The analyzers' source contract only admits these two declarations.
ANALYZER_RIGHTS_STATUS = "user-declared-authorized"


# ---------------------------------------------------------------------------
# small coercion helpers for ffprobe and JSON payloads
# ---------------------------------------------------------------------------


def finite_float(value: object) -> float | None:
    """Parse a finite number from ffprobe output (which emits numeric strings)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    elif isinstance(value, (int, float)):
        number = float(value)
    else:
        return None
    return number if math.isfinite(number) else None


def as_int(value: object) -> int | None:
    """Parse an integer from an int, numeric string, or integral float."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return None


def as_text(value: object) -> str | None:
    """Return stripped non-empty text, or ``None``."""
    if isinstance(value, str) and value.strip():
        return value
    return None


# ---------------------------------------------------------------------------
# process-level probe runner
# ---------------------------------------------------------------------------


def run_ffprobe_json(
    target: str, *, ffprobe: str = "ffprobe", timeout: float = 90.0,
    attempts: int = 3, network: bool = False, label: str = "remote probe",
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run one bounded ffprobe JSON read, retrying and reporting *why* it failed.

    Remote sources are read with HTTP range requests, so each attempt opens a
    fresh socket. ``-rw_timeout`` (30 s) replaces ffprobe's short default I/O
    timeout, which is the usual cause of a flaky remote probe on a large file.
    ``-v error`` stays quiet but its stderr tail is attached to the raised
    reason, so a transport failure is distinguishable from an unsupported
    container instead of collapsing into one opaque error.
    """
    args = [ffprobe, "-v", "error"]
    if network:
        args += ["-rw_timeout", "30000000"]
    args += ["-print_format", "json", "-show_format", "-show_streams",
             "-i", target]
    last_stderr = ""
    result: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout, check=False)
        except FileNotFoundError as error:
            raise ValueError("ffprobe is not installed locally") from error
        except subprocess.TimeoutExpired as error:
            raise ValueError(f"{label} exceeded the bounded timeout") from error
        if result.returncode == 0:
            break
        last_stderr = (result.stderr or "").strip()
        if attempt < attempts:
            sleep(1.5 * attempt)
    if result is None or result.returncode != 0:
        detail = f": {last_stderr[:240]}" if last_stderr else ""
        raise ValueError(f"{label} failed after {attempts} attempts{detail}")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} returned unusable JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} returned unusable JSON")
    return payload


def ffprobe_remote_json(
    url: str, *, allowed_hosts: Iterable[str], ffprobe: str = "ffprobe",
    timeout: float = 90.0, attempts: int = 3, allow_query: bool = False,
) -> dict[str, Any]:
    """Probe one allowlisted remote URL without downloading it."""
    allowlisted_url(url, allowed_hosts=allowed_hosts, label="probe source URL",
                    allow_query=allow_query)
    return run_ffprobe_json(url, ffprobe=ffprobe, timeout=timeout,
                            attempts=attempts, network=True,
                            label="remote probe")


# ---------------------------------------------------------------------------
# metadata adapters
# ---------------------------------------------------------------------------


def metadata_from_probe(payload: dict[str, Any]) -> dict[str, Any]:
    """Reduce one ffprobe payload to duration, dimensions, and bitrate."""
    format_metadata = payload.get("format")
    format_metadata = format_metadata if isinstance(format_metadata, dict) else {}
    streams = payload.get("streams")
    streams = streams if isinstance(streams, list) else []
    video = next((stream for stream in streams
                  if isinstance(stream, dict)
                  and stream.get("codec_type") == "video"), None) or {}
    duration = finite_float(format_metadata.get("duration"))
    if duration is None:
        duration = finite_float(video.get("duration"))
    bit_rate = finite_float(format_metadata.get("bit_rate")) or finite_float(
        video.get("bit_rate"))
    estimated_bytes = (bit_rate * duration / 8.0
                       if bit_rate and duration else None)
    return {"durationSeconds": duration,
            "width": video.get("width"), "height": video.get("height"),
            "bitRate": bit_rate, "estimatedBytes": estimated_bytes}


def remote_source_metadata(
    url: str, *, allowed_hosts: Iterable[str], ffprobe: str = "ffprobe",
    allow_query: bool = False,
) -> dict[str, Any]:
    """Cheap metadata-only probe used to reject oversized sources pre-download."""
    return metadata_from_probe(
        ffprobe_remote_json(url, allowed_hosts=allowed_hosts, ffprobe=ffprobe,
                            allow_query=allow_query))


def ranged_source_metadata(
    url: str, *, allowed_hosts: Iterable[str], ffprobe: str = "ffprobe",
    probe_bytes: int = RANGED_PROBE_BYTES, timeout: float = 60.0,
    allow_query: bool = False,
) -> dict[str, Any]:
    """Characterise a remote source from its first bounded bytes.

    Fallback for oversized sources whose full remote probe is flaky. One
    ``Range: bytes=0-<n>`` request is written into a temporary directory,
    probed locally, and deleted before returning; only numeric metadata
    survives. Faststart containers expose their index atom in this prefix,
    which is enough to report duration and bitrate.
    """
    allowed_hosts = _freeze_hosts(allowed_hosts)
    allowlisted_url(url, allowed_hosts=allowed_hosts, label="probe source URL",
                    allow_query=allow_query)
    if (type(probe_bytes) is not int
            or not 1 <= probe_bytes <= MAX_RANGED_PROBE_BYTES):
        raise ValueError("ranged probe byte budget is out of bounds")
    with tempfile.TemporaryDirectory(prefix="kumiki-acquire-probe-") as directory:
        target = media_target(Path(directory), url)
        data = fetch_bytes(
            url, allowed_hosts=allowed_hosts, max_bytes=probe_bytes,
            timeout=timeout, accept="video/*", allow_query=allow_query,
            headers={"Range": f"bytes=0-{probe_bytes - 1}"})
        if not data:
            raise ValueError("ranged probe returned no bytes")
        target.write_bytes(data)
        payload = run_ffprobe_json(
            str(target), ffprobe=ffprobe, timeout=max(timeout, 30.0),
            attempts=1, network=False, label="ranged probe")
    metadata = metadata_from_probe(payload)
    metadata["probeMethod"] = "ranged-read"
    return metadata


def source_metadata(
    path: Path, *, ffprobe: str = "ffprobe",
    rights_status: str = ANALYZER_RIGHTS_STATUS,
) -> dict[str, Any]:
    """Canonical local source identity via the repository's analyzer adapters."""
    inspected = inspect_source(path, rights_status=rights_status, ffprobe=ffprobe)
    probed = probe_media(path, ffprobe=ffprobe)
    streams = probed.get("streams")
    if not isinstance(streams, list):
        raise ValueError("ffprobe returned no stream list")
    audio = next((stream for stream in streams
                  if isinstance(stream, dict)
                  and stream.get("codec_type") == "audio"), None)
    format_metadata = probed.get("format")
    format_metadata = format_metadata if isinstance(format_metadata, dict) else {}
    duration = finite_float(format_metadata.get("duration"))
    if duration is None:
        duration = finite_float(inspected["video"].get("durationSecondsReported"))
    if duration is None or duration <= 0:
        raise ValueError("source reported no usable duration")
    video = inspected["video"]
    return {
        "mediaSha256": inspected["source"]["sha256"],
        "sizeBytes": inspected["source"]["sizeBytes"],
        "durationSeconds": round(duration, 6),
        "resolution": [video["width"], video["height"]],
        "frameRate": video["averageFrameRate"],
        "sourceTimebase": video["sourceTimebase"],
        "container": as_text(format_metadata.get("format_name")) or path.suffix.lstrip("."),
        "videoCodec": video.get("codec"),
        "audioCodec": (audio.get("codec_name")
                       if isinstance(audio, dict) else None),
        "hasAudio": audio is not None,
    }


def probe_image_dimensions(path: Path, *, ffprobe: str = "ffprobe") -> dict[str, Any]:
    """Read an image's own pixel dimensions and codec via one local ffprobe."""
    payload = run_ffprobe_json(
        str(path), ffprobe=ffprobe, timeout=30.0, attempts=1,
        network=False, label="still image probe")
    streams = payload.get("streams")
    streams = streams if isinstance(streams, list) else []
    video = next((stream for stream in streams
                  if isinstance(stream, dict)), None) or {}
    width = as_int(video.get("width"))
    height = as_int(video.get("height"))
    if width is None or height is None or width <= 0 or height <= 0:
        raise ValueError("still image probe reported no usable dimensions")
    return {"width": width, "height": height,
            "codec": as_text(video.get("codec_name"))}
