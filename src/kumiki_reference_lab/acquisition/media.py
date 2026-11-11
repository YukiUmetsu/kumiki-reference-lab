"""Allowlisted HTTPS retrieval, bounded downloads, and HLS planning/execution.

This module is site-agnostic: callers supply the host allowlist, byte caps,
timeouts, and the destination directory. Nothing here authenticates, follows
non-HTTPS redirects, or keeps bytes beyond the destination the caller passes in.
"""

from __future__ import annotations

import ipaddress
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

# Generic delivery modes. Callers map their own catalog vocabulary onto these.
HLS = "hls"
DIRECT = "direct"

# Acquisition method labels recorded in evidence with the video.
METHOD_HLS_REMUX = "ffmpeg-hls-copy"
METHOD_HTTP_DOWNLOAD = "http-download"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v", ".webm")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif")

DEFAULT_TEXT_LIMIT = 2 * 1024 * 1024
_DEFAULT_CHUNK = 1024 * 1024

# A host name needs at least one dot; single-label names and IP literals are
# refused so an allowlist entry cannot silently admit an intranet address.
_HOST_NAME = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)
_HLS_ATTRIBUTE = re.compile(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)')


# ---------------------------------------------------------------------------
# URL allowlisting
# ---------------------------------------------------------------------------


def _freeze_hosts(allowed_hosts: Iterable[str]) -> Iterable[str]:
    """Materialise one-shot iterables so repeated validations see the allowlist."""
    if isinstance(allowed_hosts, (str, bytes)):
        return allowed_hosts
    return tuple(allowed_hosts)


def _split_allowlist(allowed_hosts: Iterable[str]) -> tuple[frozenset[str], tuple[str, ...]]:
    """Return (exact hosts, subdomain suffixes) from caller-supplied entries.

    An entry without a leading dot matches that host exactly. An entry with a
    leading dot (``".cdn.example"``) matches subdomains of that host only; it
    never matches the bare host itself, so subdomain access is always an
    explicit, documented opt-in rather than an implicit wildcard.
    """
    if isinstance(allowed_hosts, (str, bytes)):
        raise ValueError("allowed hosts must be an iterable of host names, not a single string")
    exact: set[str] = set()
    suffixes: set[str] = set()
    for entry in allowed_hosts:
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError("allowlist entries must be non-empty host names")
        value = entry.strip().lower()
        if value.startswith("."):
            value = value[1:]
            if not _HOST_NAME.match(value):
                raise ValueError("allowlist subdomain entry is not a valid host name")
            suffixes.add(value)
        else:
            if not _HOST_NAME.match(value):
                raise ValueError("allowlist entry is not a valid host name")
            exact.add(value)
    if not exact and not suffixes:
        raise ValueError("allowlist must contain at least one host")
    return frozenset(exact), tuple(sorted(suffixes))


def _checked_host(host: str, *, label: str) -> str:
    if not host:
        raise ValueError(f"{label} has no host")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError(f"{label} host must not be an IP literal")
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError(f"{label} host must not be a loopback name")
    if not _HOST_NAME.match(host):
        raise ValueError(f"{label} host is not a public DNS name")
    return host


def allowlisted_url(
    url: object, *, allowed_hosts: Iterable[str], label: str = "media source URL",
) -> str:
    """Validate one public HTTPS URL against a caller-supplied host allowlist.

    Rejects non-HTTPS schemes, credentials, non-default ports, fragments,
    query strings, IP literals, loopback names, and any host that is not an
    exact allowlist entry (or an explicitly permitted subdomain).
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"{label} is absent")
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise ValueError(f"{label} is not a parsable URL") from None
    if parsed.scheme != "https":
        raise ValueError(f"{label} must use https")
    if parsed.username or parsed.password:
        raise ValueError(f"{label} must not carry credentials")
    try:
        port = parsed.port
    except ValueError:
        raise ValueError(f"{label} must not carry an invalid port") from None
    if port not in (None, 443):
        raise ValueError(f"{label} must not carry a custom port")
    if parsed.fragment:
        raise ValueError(f"{label} must not carry a fragment")
    if parsed.query:
        raise ValueError(f"{label} must not carry a query string")
    host = _checked_host((parsed.hostname or "").lower(), label=label)
    exact, suffixes = _split_allowlist(allowed_hosts)
    if host in exact:
        return url
    for suffix in suffixes:
        if host.endswith("." + suffix):
            return url
    raise ValueError(f"{label} host is not allowlisted")


def allowlisted_video_url(url: object, *, allowed_hosts: Iterable[str]) -> str:
    """Thin video-source policy wrapper around :func:`allowlisted_url`."""
    return allowlisted_url(url, allowed_hosts=allowed_hosts, label="video source URL")


def allowlisted_image_url(url: object, *, allowed_hosts: Iterable[str]) -> str:
    """Thin still-image policy wrapper around :func:`allowlisted_url`."""
    return allowlisted_url(url, allowed_hosts=allowed_hosts, label="still image URL")


# ---------------------------------------------------------------------------
# bounded retrieval
# ---------------------------------------------------------------------------


def media_target(
    directory: Path, url: str, *, suffixes: Iterable[str] = VIDEO_SUFFIXES,
    stem: str = "source", fallback: str = ".mp4",
) -> Path:
    """Pick a local file name for one video URL, keeping a known suffix."""
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix not in set(suffixes):
        suffix = fallback
    return directory / (stem + suffix)


def image_target(directory: Path, url: str) -> Path:
    """Pick a local file name for one still-image URL, keeping a known suffix."""
    return media_target(
        directory, url, suffixes=IMAGE_SUFFIXES, stem="poster", fallback=".img")


def check_downloaded(path: Path, *, max_bytes: int, label: str = "media") -> Path:
    """Require a regular, non-empty, size-capped local file; return it."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"download produced no regular {label} file")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError(f"download produced an empty {label} file")
    if size > max_bytes:
        raise ValueError(f"{label} exceeds the bounded local size cap")
    return path


def _checked_budget(max_bytes: int, *, label: str) -> int:
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return max_bytes


def fetch_bytes(
    url: str, *, allowed_hosts: Iterable[str], max_bytes: int,
    timeout: float = 30.0, accept: str | None = None,
    headers: dict[str, str] | None = None, user_agent: str = USER_AGENT,
    chunk_size: int = 256 * 1024,
) -> bytes:
    """Read at most ``max_bytes`` from one allowlisted HTTPS URL.

    The byte budget truncates instead of raising; this is the metadata-read
    primitive (playlists, ranged probes), not the media download path.
    """
    _checked_budget(max_bytes, label="read byte budget")
    allowed_hosts = _freeze_hosts(allowed_hosts)
    allowlisted_url(url, allowed_hosts=allowed_hosts)
    request_headers = {"User-Agent": user_agent}
    if accept is not None:
        request_headers["Accept"] = accept
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    chunks: list[bytes] = []
    total = 0
    with urlopen(request, timeout=timeout) as response:
        allowlisted_url(response.geturl(), allowed_hosts=allowed_hosts)
        while total < max_bytes:
            chunk = response.read(min(chunk_size, max_bytes - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    return b"".join(chunks)


def fetch_text(
    url: str, *, allowed_hosts: Iterable[str], timeout: float = 30.0,
    limit: int = DEFAULT_TEXT_LIMIT,
) -> str:
    """Read at most ``limit`` bytes of UTF-8 text from one allowlisted URL."""
    return fetch_bytes(
        url, allowed_hosts=allowed_hosts, max_bytes=limit, timeout=timeout,
    ).decode("utf-8", "replace")


def download_http(
    url: str, destination: Path, *, allowed_hosts: Iterable[str], max_bytes: int,
    timeout: float = 120.0, accept: str = "video/*", label: str = "source",
    user_agent: str = USER_AGENT, chunk_size: int = _DEFAULT_CHUNK,
) -> Path:
    """Stream one allowlisted HTTPS URL into ``destination`` under a hard cap.

    Exceeding ``max_bytes`` raises instead of truncating: a partial media file
    is never accepted as evidence. Redirect targets are re-validated.
    """
    _checked_budget(max_bytes, label="download byte budget")
    allowed_hosts = _freeze_hosts(allowed_hosts)
    allowlisted_url(url, allowed_hosts=allowed_hosts)
    request = Request(url, headers={"Accept": accept, "User-Agent": user_agent})
    total = 0
    with urlopen(request, timeout=timeout) as response:
        allowlisted_url(response.geturl(), allowed_hosts=allowed_hosts)
        with destination.open("wb") as outfile:
            while chunk := response.read(chunk_size):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"{label} exceeds the bounded local size cap")
                outfile.write(chunk)
    return check_downloaded(destination, max_bytes=max_bytes, label=label)


# ---------------------------------------------------------------------------
# HLS planning and execution
# ---------------------------------------------------------------------------


def _parse_attributes(line: str) -> dict[str, str]:
    _, _, payload = line.partition(":")
    attributes: dict[str, str] = {}
    for match in _HLS_ATTRIBUTE.finditer(payload):
        value = match.group(2)
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        attributes[match.group(1)] = value
    return attributes


def plan_hls_download(
    master_url: str, *, allowed_hosts: Iterable[str], max_width: int = 1280,
    master_text: str | None = None, timeout: float = 30.0,
) -> dict[str, Any]:
    """Choose one bounded rendition from an HLS master playlist.

    Picks the widest variant at or below ``max_width`` (falling back to the
    smallest declared variant). The audio rendition is resolved through the
    chosen variant's ``AUDIO`` group id when the master declares one, with the
    first declared audio rendition as a fallback. Returns the chosen URLs and
    dimensions; the caller builds the ffmpeg invocation.

    ``master_text`` lets a caller that already fetched the playlist (or an
    offline test) skip the network read.
    """
    allowed_hosts = _freeze_hosts(allowed_hosts)
    allowlisted_url(master_url, allowed_hosts=allowed_hosts, label="HLS master URL")
    if type(max_width) is not int or max_width < 1:
        raise ValueError("HLS max width must be a positive integer")
    text = (master_text if master_text is not None else fetch_text(
        master_url, allowed_hosts=allowed_hosts, timeout=timeout))
    if "#EXTM3U" not in text:
        raise ValueError("HLS master playlist was not returned")

    audio_by_group: dict[str, str] = {}
    first_audio_url: str | None = None
    variants: list[dict[str, Any]] = []
    pending: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXT-X-MEDIA:"):
            attributes = _parse_attributes(line)
            if attributes.get("TYPE") != "AUDIO" or not attributes.get("URI"):
                continue
            uri = urljoin(master_url, attributes["URI"])
            audio_by_group.setdefault(attributes.get("GROUP-ID") or "", uri)
            if first_audio_url is None:
                first_audio_url = uri
        elif line.startswith("#EXT-X-STREAM-INF:"):
            pending = _parse_attributes(line)
        elif line and not line.startswith("#") and pending is not None:
            resolution = re.search(r"(\d+)x(\d+)", pending.get("RESOLUTION", ""))
            variants.append({
                "width": int(resolution.group(1)) if resolution else 0,
                "height": int(resolution.group(2)) if resolution else 0,
                "url": urljoin(master_url, line),
                "audioGroup": pending.get("AUDIO") or "",
            })
            pending = None

    if not variants:
        return {
            "variantUrl": master_url, "audioUrl": first_audio_url,
            "width": None, "height": None,
        }
    bounded = [variant for variant in variants
               if variant["width"] and variant["width"] <= max_width]
    chosen = (max(bounded, key=lambda variant: variant["width"]) if bounded
              else min(variants, key=lambda variant: variant["width"] or 10 ** 6))
    audio_url = audio_by_group.get(chosen["audioGroup"]) or first_audio_url
    allowlisted_url(chosen["url"], allowed_hosts=allowed_hosts,
                    label="HLS variant URL")
    if audio_url:
        allowlisted_url(audio_url, allowed_hosts=allowed_hosts,
                        label="HLS audio URL")
    return {
        "variantUrl": chosen["url"], "audioUrl": audio_url,
        "width": chosen["width"] or None, "height": chosen["height"] or None,
    }


def _run_ffmpeg(
    args: list[str], *, timeout: float, label: str,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, check=False)
    except FileNotFoundError as error:
        raise ValueError("ffmpeg is not installed locally") from error
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"{label} exceeded the bounded timeout") from error
    except OSError as error:
        raise ValueError("ffmpeg process could not start") from error


def download_media(
    url: str, provider: str, directory: Path, *, allowed_hosts: Iterable[str],
    max_bytes: int, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    timeout: float = 360.0, max_width: int = 1280,
    max_duration_seconds: float | None = None,
    log: Callable[[str], None] | None = None,
) -> tuple[Path, str]:
    """Download one allowlisted public video into ``directory``.

    ``provider`` is the caller's generic delivery mode (:data:`HLS` or
    :data:`DIRECT`). HLS uses a stream-copy remux of one bounded rendition;
    direct sources use urllib. Oversized or duration-exceeding sources are
    rejected from remote metadata before bytes are written. Never
    authenticates. Returns ``(local path, method label)``.
    """
    # Local import: probe adapters themselves depend on this module's
    # allowlisting and bounded-read primitives.
    from . import probe as probe_adapter

    allowed_hosts = _freeze_hosts(allowed_hosts)
    allowlisted_url(url, allowed_hosts=allowed_hosts, label="video source URL")
    if provider not in (HLS, DIRECT):
        raise ValueError("provider is not downloadable by design")
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("download directory is not a real directory")
    target = media_target(directory, url)

    if provider == HLS:
        plan = plan_hls_download(url, allowed_hosts=allowed_hosts,
                                 max_width=max_width)
        variant = plan["variantUrl"]
        remote = probe_adapter.remote_source_metadata(
            variant, allowed_hosts=allowed_hosts, ffprobe=ffprobe)
        _reject_excess_duration(remote, max_duration_seconds)
        args = [ffmpeg, "-hide_banner", "-v", "error", "-y", "-i", variant]
        if plan["audioUrl"]:
            args += ["-i", plan["audioUrl"],
                     "-map", "0:v:0", "-map", "1:a:0?"]
        else:
            args += ["-map", "0:v:0"]
        args += ["-c", "copy", str(target)]
        result = _run_ffmpeg(args, timeout=timeout, label="HLS download")
        if result.returncode != 0:
            raise ValueError(f"ffmpeg HLS remux failed (exit {result.returncode})")
        if (result.stderr or "").strip() and log is not None:
            log("ffmpeg reported non-fatal stderr during HLS remux; continuing")
        return check_downloaded(target, max_bytes=max_bytes), METHOD_HLS_REMUX

    try:
        remote = probe_adapter.remote_source_metadata(
            url, allowed_hosts=allowed_hosts, ffprobe=ffprobe)
    except ValueError as probe_error:
        if log is not None:
            log(f"direct download remote probe failed ({probe_error}); "
                "falling back to a bounded ranged read")
        try:
            remote = probe_adapter.ranged_source_metadata(
                url, allowed_hosts=allowed_hosts, ffprobe=ffprobe)
        except ValueError as ranged_error:
            raise ValueError(
                "source could not be characterised: "
                f"remote probe: {probe_error}; ranged read: {ranged_error}"
            ) from None
        if log is not None:
            log("characterised the direct download from a bounded ranged read")
    _reject_excess_duration(remote, max_duration_seconds)
    if (remote["estimatedBytes"] and remote["estimatedBytes"] > max_bytes
            and log is not None):
        log("remote metadata estimates this source exceeds the local size cap; "
            "streaming until the cap is enforced")
    downloaded = download_http(url, target, allowed_hosts=allowed_hosts,
                               max_bytes=max_bytes)
    return downloaded, METHOD_HTTP_DOWNLOAD


def _reject_excess_duration(
    metadata: dict[str, Any], max_duration_seconds: float | None,
) -> None:
    duration = metadata.get("durationSeconds")
    if (max_duration_seconds is not None and duration
            and duration > max_duration_seconds):
        raise ValueError("source exceeds the bounded duration budget")
