"""Generic, opt-in ephemeral acquisition of public HTTPS video references.

yt-dlp handles provider discovery. No fixed site or platform allowlist exists.
Callers must use a temporary directory and provide a lawful acquisition basis.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
import subprocess
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

RIGHTS_BASES = frozenset({
    "own-original-work", "written-permission", "permissive-license",
    "other-lawful-authorization",
})
MAX_MEDIA_BYTES = 200 * 1024 * 1024
_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".mkv", ".webm"})
_HOST = re.compile(r"(?=.{1,253}\Z)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\Z")
_SECRET_KEYS = frozenset({
    "token", "access_token", "apikey", "api_key", "auth", "authorization",
    "password", "cookie", "session", "signature", "sig", "secret", "key",
})


def validate_watch_url(url: str) -> str:
    """Accept any publicly-addressable HTTPS website; reject obvious local URLs."""
    if type(url) is not str or not 1 <= len(url) <= 2048:
        raise ValueError("video URL must be a bounded string")
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid source URL") from exc
    if (parsed.scheme != "https" or not parsed.netloc or
            parsed.username is not None or parsed.password is not None or
            port not in (None, 443) or parsed.fragment or
            not _HOST.fullmatch(hostname) or ".." in hostname or
            "." not in hostname):
        raise ValueError("expected a public HTTPS website URL without credentials or fragments")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("IP-address source URLs are unsupported")
    if hostname.endswith((".localhost", ".local", ".internal", ".test", ".invalid")):
        raise ValueError("private hostnames cannot be video sources")
    if hostname in ("localhost", "metadata.google.internal"):
        raise ValueError("private hostnames cannot be video sources")
    if any(key.lower() in _SECRET_KEYS for key, _ in parse_qsl(
            parsed.query, keep_blank_values=True)):
        raise ValueError("do not pass auth tokens or signed URLs")
    return url


def require_public_dns(url: str) -> None:
    """Reject any private/reserved DNS answer at acquisition time.

    Note: extractors may follow redirects. Use network isolation for untrusted
    URLs; a DNS pre-check cannot enforce policy inside a third-party extractor.
    """
    host = urlsplit(validate_watch_url(url)).hostname
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("source hostname did not resolve") from exc
    if not answers:
        raise ValueError("source hostname did not resolve")
    for answer in answers:
        try:
            ip = ipaddress.ip_address(answer[4][0])
        except ValueError as exc:
            raise ValueError("invalid source DNS answer") from exc
        if not ip.is_global:
            raise ValueError("source hostname resolves to non-public network address")


def require_rights(basis: str, note: str, *, acknowledged: bool) -> None:
    if (acknowledged is not True or basis not in RIGHTS_BASES or
            type(note) is not str or not 12 <= len(note.strip()) <= 500):
        raise ValueError("explicit lawful acquisition basis and rights explanation required")


def reference_id(url: str) -> str:
    parsed = urlsplit(url)
    host = re.sub(r"[^a-z0-9]+", "-", (parsed.hostname or "").lower()).strip("-")
    return host[:36] + "-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def download_public_video(
    url: str, directory: Path, *, rights_basis: str, rights_note: str,
    acknowledge_rights: bool, yt_dlp: str = "yt-dlp",
    timeout_seconds: int = 600, max_bytes: int = MAX_MEDIA_BYTES,
) -> Path:
    """Acquire one publicly accessible video, without browser credentials.

    Directory must be empty and caller-owned. This cannot bypass DRM, logins
    or source restrictions. Third-party extractor redirects require OS sandboxing
    for hostile URLs; validation here is not a complete SSRF containment layer.
    """
    validate_watch_url(url)
    require_rights(rights_basis, rights_note, acknowledged=acknowledge_rights)
    if (type(timeout_seconds) is not int or not 30 <= timeout_seconds <= 3600
            or type(max_bytes) is not int or not 1 <= max_bytes <= MAX_MEDIA_BYTES
            or directory.is_symlink() or not directory.is_dir()
            or any(directory.iterdir())):
        raise ValueError("unsafe media download limits or scratch directory")
    require_public_dns(url)
    command = [
        yt_dlp, "--ignore-config", "--no-plugin-dirs", "--no-playlist",
        "--max-downloads", "1", "--no-mtime", "--no-progress", "--quiet",
        "--no-warnings", "--no-continue", "--no-part", "--no-overwrites",
        "--retries", "1", "--fragment-retries", "1",
        "--socket-timeout", "15", "--max-filesize", str(max_bytes),
        "--merge-output-format", "mp4", "--paths", str(directory.resolve()),
        "--output", "source.%(ext)s", "--", url,
    ]
    try:
        result = subprocess.run(
            command, cwd=directory, capture_output=True, text=True,
            timeout=timeout_seconds, check=False,
        )
    except FileNotFoundError as exc:
        raise ValueError("yt-dlp executable is required") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("online video download timed out") from exc
    if result.returncode != 0:
        # Extractor errors can contain private CDN tokens. Do not echo stderr.
        raise ValueError("video is unavailable to the unauthenticated extractor")
    entries = list(directory.iterdir())
    media = [p for p in entries if p.name.startswith("source.")
             and p.suffix.lower() in _VIDEO_EXTENSIONS and p.is_file() and not p.is_symlink()]
    if (len(entries) != 1 or len(media) != 1 or
            not 0 < media[0].stat().st_size <= max_bytes):
        raise ValueError("expected exactly one bounded local video file")
    return media[0]
