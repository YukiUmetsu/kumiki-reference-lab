"""Cheap source-stability check around bounded analysis stages.

This complements content SHA-256. It is not a secure immutable snapshot against
an adversary who can rewrite a file and deliberately restore its metadata.
"""

from __future__ import annotations

from pathlib import Path


def file_signature(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ino, stat.st_dev


def require_unchanged(path: Path, signature: tuple[int, int, int, int]) -> None:
    if file_signature(path) != signature:
        raise ValueError("source changed during analysis; retry with stable input")
