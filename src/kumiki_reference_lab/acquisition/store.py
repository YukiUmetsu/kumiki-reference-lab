"""Atomic JSON writes, safe file names, resume checks, and index assembly."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


def utc_now() -> str:
    """Return the current UTC instant as an ISO-8601 ``Z`` string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> Path:
    """Write one JSON document via a same-directory temporary file and rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=path.name + ".",
        suffix=".tmp", delete=False)
    temporary = Path(staging.name)
    try:
        with staging:
            json.dump(payload, staging, indent=2, ensure_ascii=False,
                      allow_nan=False)
            staging.write("\n")
            staging.flush()
            os.fsync(staging.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def safe_slug(value: object, *, limit: int = 120) -> str:
    """Reduce an identifier to a safe single-path file stem or raise."""
    if type(limit) is not int or limit < 1:
        raise ValueError("slug length limit must be a positive integer")
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip(".-")
    if not text or text in (".", "..") or len(text) > limit:
        raise ValueError("identifier is not a safe file name")
    return text


def resume_matches(
    record_path: Path, subject_id: object, *, field: str = "id",
) -> bool:
    """True when an existing record exists and carries the same subject id."""
    if not isinstance(field, str) or not field.strip():
        raise ValueError("resume field must be a non-empty record key")
    try:
        payload = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (isinstance(payload, dict)
            and str(payload.get(field)) == str(subject_id))


def build_index(
    *, schema_version: str, records: Iterable[dict[str, Any]],
    skips: Iterable[dict[str, Any]], failures: Iterable[dict[str, Any]],
    generated_at: str, extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble one batch index with measured/skipped/failed counts.

    ``extra`` carries caller-specific header fields (for example the digest of
    the input catalog); nothing about them is interpreted here.
    """
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError("index schema version must be a non-empty string")
    measured = list(records)
    skipped = list(skips)
    failed = list(failures)
    header = dict(extra or {})
    return {
        "schemaVersion": schema_version,
        "generatedAt": generated_at,
        **header,
        "counts": {
            "measured": len(measured),
            "skipped": len(skipped),
            "failed": len(failed),
        },
        "records": measured,
        "skips": skipped,
        "failures": failed,
    }
