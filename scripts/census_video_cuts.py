#!/usr/bin/env python3
"""Full-runtime cut census over the existing video-evidence trees.

For every ``<root>/<site>/videos/*.json`` record this driver recovers the
canonical upstream URL, re-downloads the public media once, verifies the stored
source identity, decodes the whole file twice (scene candidates + fixed-cadence
appearance), writes one census record atomically, and deletes the media.

Identity is verified per delivery method: byte-stable direct downloads must
match the stored SHA-256 exactly, while remuxed HLS and platform-transcoded
YouTube renditions are checked for duration, resolution and container/codec
family. Every record states which rule ran in ``identityVerification``.
``--strict-identity`` forces the SHA gate everywhere; ``--allow-media-change``
measures a record whose identity could not be established and marks it
``forced``.

Usage:
    PYTHONPATH=src python scripts/census_video_cuts.py --acknowledge-rights \
        --site promonews --limit 2

The output tree stays inside ``--root``; the smoke run uses a temporary root so
``research/analysis`` is never modified.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from kumiki_reference_lab.acquisition import (
    DIRECT, DEFAULT_YOUTUBE_HOSTS, HLS, USER_AGENT, YOUTUBE,
    allowlisted_url, allowlisted_youtube_url, build_census_evidence,
    build_index, download_media, run_batch, safe_error, safe_slug,
    scan_full_runtime, source_metadata, utc_now, write_json_atomic,
)

# Hosts are read from the recorded URLs in each evidence tree. Signed CDNs are
# the only lanes that opt into query strings.
SITE_POLICY: dict[str, dict[str, Any]] = {
    "motiondesignawards": {
        "hosts": ("videodelivery.net", "storage-01-mda.keyfram.es",
                  ".cloudflarestream.com"),
        "allow_query": False,
    },
    "shots": {
        "hosts": ("d1ko11x0ybxl0h.cloudfront.net", "proxy.slatecdn.net",
                  "d2290ppie00mze.cloudfront.net", "app.extremereach.com"),
        "allow_query": True,
    },
    "aicp": {
        "hosts": ("player.vimeo.com", ".vimeocdn.com"),
        "allow_query": True,
    },
    "promonews": {
        "hosts": DEFAULT_YOUTUBE_HOSTS,
        "allow_query": False,
    },
    "directorslibrary": {
        "hosts": DEFAULT_YOUTUBE_HOSTS,
        "allow_query": False,
    },
}

RIGHTS_BASIS = "user-declared-research-use"
RIGHTS_NOTE = (
    "operator attests public-page research use; the public rendition is "
    "downloaded once, measured numerically over the full runtime, and deleted "
    "without redistribution")
EVIDENCE_STATUS = "full-runtime-numeric-census-not-human-reviewed"
CENSUS_LIMITS = [
    "Cut candidates are ffmpeg scene-score exceedances, not verified edits; "
    "fast movement, flashes, transitions and compression can exceed the "
    "threshold.",
    "Per-sample appearance numbers are display-RGB proxies at the requested "
    "decode size, not scene-linear light or calibrated colour.",
    "The full runtime is decoded, but appearance is sampled at a fixed "
    "cadence; numbers describe those samples and their time weights.",
    "Only numeric measurements, hashes and metadata are stored; no subject, "
    "intent, style, quality or identity claim is made.",
    "No human or expert review was performed; the record is not a verdict on "
    "the work.",
    "Media bytes are not retained; for byte-stable deliveries the media "
    "SHA-256 is a byte-identity check, never a licence.",
    "Remuxed HLS and platform-transcoded renditions are not asserted to be "
    "byte-identical: their identity is checked as duration within 0.5 s, "
    "resolution and container/codec family, as recorded in "
    "identityVerification.",
]

# Identity rules. ``strict-sha`` is byte identity; ``duration+resolution+codec``
# is content identity for remuxed/transcoded deliveries; ``forced`` records a
# measurement whose identity gate was explicitly waived.
IDENTITY_STRICT = "strict-sha"
IDENTITY_TOLERANT = "duration+resolution+codec"
IDENTITY_FORCED = "forced"
IDENTITY_COUNT_KEYS = ("strict-sha", "tolerant", "forced")
# A remux moves segment/mux boundaries; half a second absorbs that without
# admitting a different edit.
IDENTITY_DURATION_TOLERANCE_SECONDS = 0.5

_CODEC_FAMILIES = {
    "avc1": "h264", "avc3": "h264", "h264": "h264",
    "hev1": "hevc", "hvc1": "hevc", "h265": "hevc", "hevc": "hevc",
    "av01": "av1", "av1": "av1",
    "vp08": "vp8", "vp8": "vp8", "vp09": "vp9", "vp9": "vp9",
    "mp4v": "mpeg4", "mpeg4": "mpeg4",
}
# Provider vocabulary that denotes a streamed manifest rather than a file.
_STREAMING_PROVIDERS = frozenset({
    "hls", "dash", "m3u8", "mpd", "stream", "streaming", "mux",
    "cloudflare-stream", "vimeo", "brightcove",
})

_BYTES_SUFFIXES = {
    "": 1,
    "b": 1,
    "kib": 1024,
    "mib": 1024 ** 2,
    "gib": 1024 ** 3,
    "kb": 1000,
    "mb": 1000 ** 2,
    "gb": 1000 ** 3,
}

# Signed CDN URLs expire; a 4xx on one of these statuses is the signal to
# re-resolve the URL from the site catalog rather than to abort the record.
STALE_SIGNED_STATUSES = frozenset({400, 401, 403, 404, 410})
# Adapters spell the record identity differently; index every shape.
CATALOG_ID_KEYS = ("id", "nid", "projectId", "catalogId", "postId", "clipId")
# Catalog payloads also expose their rows under different top-level keys.
CATALOG_ROW_KEYS = ("entries", "videos", "projects", "clips", "items", "records")
CATALOG_URL_KEYS = ("videoUrl", "videoURL", "url", "sourceUrl", "mediaUrl")


class MediaChanged(Exception):
    """Raised when the re-downloaded media no longer matches the record."""

    reason = "media-changed"

    def __init__(self, message: str = "", *, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail or message or self.reason


class StaleSignedUrl(Exception):
    """Raised when a signed media URL still returns 4xx after a catalog retry."""

    reason = "stale-signed-url"


def parse_bytes(text: str) -> int:
    """Parse ``400MiB``/``12MB``/an integer into bytes."""
    match = re.fullmatch(r"\s*(\d+)\s*([A-Za-z]*)\s*", str(text))
    if match is None:
        raise argparse.ArgumentTypeError("byte budget must look like 400MiB")
    suffix = match.group(2).lower()
    if suffix not in _BYTES_SUFFIXES:
        raise argparse.ArgumentTypeError(f"unknown byte suffix {suffix!r}")
    value = int(match.group(1)) * _BYTES_SUFFIXES[suffix]
    if value <= 0:
        raise argparse.ArgumentTypeError("byte budget must be positive")
    return value


def _first_text(mapping: dict[str, Any], keys: Iterable[str]) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _containers(record: dict[str, Any]) -> list[dict[str, Any]]:
    found = [record]
    evidence = record.get("evidence")
    if isinstance(evidence, dict):
        found.append(evidence)
    return found


def _resolution(value: Any) -> list[int] | None:
    """Return a positive ``[width, height]`` pair or ``None``."""
    if (isinstance(value, (list, tuple)) and len(value) == 2
            and all(type(item) is int and item > 0 for item in value)):
        return [value[0], value[1]]
    return None


def extract_record_identity(
    record: dict[str, Any], *, fallback_id: str = "",
) -> dict[str, Any]:
    """Recover id/slug/URL/provider/SHA across adapter record shapes.

    Handles both a flat record (``videoUrl`` + ``source.mediaSha256``) and an
    evidence-wrapped one (``evidence.source`` / ``evidence.acquisition``).
    Returns ``None`` fields rather than inventing values.
    """
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object")
    containers = _containers(record)
    sources = [container.get("source") for container in containers
               if isinstance(container.get("source"), dict)]
    acquisitions = [container.get("acquisition") for container in containers
                    if isinstance(container.get("acquisition"), dict)]

    video_url = None
    for source in sources:
        video_url = _first_text(source, ("videoUrl",))
        if video_url:
            break
    if not video_url:
        for container in containers:
            video_url = _first_text(container, ("videoUrl",))
            if video_url:
                break
    if not video_url:
        for acquisition in acquisitions:
            video_url = _first_text(acquisition, ("videoUrl",))
            if video_url:
                break
    if not video_url:
        for container in containers:
            media = container.get("media")
            media = media if isinstance(media, dict) else {}
            chosen = media.get("chosen")
            chosen = chosen if isinstance(chosen, dict) else {}
            video_url = _first_text(chosen, ("url",))
            if video_url:
                break

    provider = None
    for container in containers:
        provider = _first_text(container, ("provider",))
        if provider:
            break
    if not provider:
        for acquisition in acquisitions:
            provider = _first_text(acquisition, ("provider",))
            if provider:
                break

    media_sha256 = None
    for source in sources:
        media_sha256 = _first_text(source, ("mediaSha256",))
        if media_sha256:
            break
    if not media_sha256:
        for container in containers:
            media_sha256 = _first_text(container, ("mediaSha256",))
            if media_sha256:
                break

    record_id = None
    for container in containers:
        for key in CATALOG_ID_KEYS:
            value = container.get(key)
            if value is not None and str(value).strip():
                record_id = str(value).strip()
                break
        if record_id:
            break
    record_id = record_id or fallback_id
    slug = None
    for container in containers:
        slug = _first_text(container, ("slug",))
        if slug:
            break
    slug = slug or "video"

    duration = None
    size = None
    for source in sources:
        if duration is None:
            duration = source.get("durationSeconds")
        if size is None:
            size = source.get("sizeBytes")
    for container in containers:
        if duration is None and isinstance(container.get("clip"), dict):
            duration = container["clip"].get("durationSeconds")
        if duration is None and isinstance(container.get("catalog"), dict):
            duration = container["catalog"].get("durationSeconds")

    resolution = None
    container_name = None
    video_codec = None
    for source in sources:
        if resolution is None:
            resolution = _resolution(source.get("resolution"))
        if container_name is None:
            container_name = _first_text(source, ("container",))
        if video_codec is None:
            video_codec = _first_text(source, ("videoCodec",))
    acquisition_method = None
    for acquisition in acquisitions:
        acquisition_method = _first_text(acquisition, ("method",))
        if acquisition_method:
            break

    return {
        "id": record_id,
        "slug": slug,
        "videoUrl": video_url,
        "provider": provider,
        "mediaSha256": (media_sha256 or "").lower() or None,
        "durationSeconds": duration,
        "sizeBytes": size,
        "resolution": resolution,
        "container": container_name,
        "videoCodec": video_codec,
        "acquisitionMethod": acquisition_method,
    }


def _delivery_mode(url: str, provider: str | None) -> str:
    name = (provider or "").lower()
    path = urlsplit(url).path.lower()
    if name == "youtube" or "youtube.com" in (urlsplit(url).hostname or "") \
            or "youtu.be" in (urlsplit(url).hostname or ""):
        return YOUTUBE
    if name in ("hls", "cloudflare-stream", "vimeo") or path.endswith(".m3u8"):
        return HLS
    return DIRECT


def _canonical_url(url: str, delivery: str) -> str:
    if delivery == YOUTUBE:
        return allowlisted_youtube_url(url, allowed_hosts=DEFAULT_YOUTUBE_HOSTS)
    return url


def _number(value: Any) -> float | None:
    """Return a finite float for a JSON number, else ``None``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _container_families(value: Any) -> set[str]:
    text = str(value or "").strip().lower()
    return {part.strip() for part in text.split(",") if part.strip()}


def _container_matches(stored: Any, observed: Any) -> bool | None:
    left = _container_families(stored)
    right = _container_families(observed)
    if not left or not right:
        return None
    return bool(left & right)


def _codec_family(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    return _CODEC_FAMILIES.get(text, text)


def _codec_matches(stored: Any, observed: Any) -> bool | None:
    left = _codec_family(stored)
    right = _codec_family(observed)
    if left is None or right is None:
        return None
    return left == right


def _identity_mode(item: dict[str, Any], method: str | None) -> str:
    """Return ``youtube``, ``remux`` or ``byte`` for the observed delivery."""
    provider = str(item.get("storedProvider") or "").strip().lower()
    delivery = item.get("delivery")
    observed = str(method or "").strip().lower()
    stored_method = str(item.get("storedMethod") or "").strip().lower()
    if delivery == YOUTUBE or provider == "youtube" or "ytdlp" in observed:
        return "youtube"
    path = urlsplit(str(item.get("videoUrl") or "")).path.lower()
    if (delivery == HLS or provider in _STREAMING_PROVIDERS
            or "stream" in provider or "hls" in observed
            or "hls" in stored_method
            or path.endswith((".m3u8", ".mpd"))):
        return "remux"
    return "byte"


def _tolerance_block(
    item: dict[str, Any], observed: dict[str, Any], sha_matched: bool,
) -> dict[str, Any]:
    """Describe content identity for a remuxed/transcoded delivery."""
    stored_duration = _number(item.get("durationSeconds"))
    observed_duration = _number(observed.get("durationSeconds"))
    if stored_duration is not None and observed_duration is not None:
        duration_delta: float | None = round(
            abs(observed_duration - stored_duration), 6)
    else:
        # Equal bytes are the same runtime by definition.
        duration_delta = 0.0 if sha_matched else None
    stored_resolution = _resolution(item.get("resolution"))
    observed_resolution = _resolution(observed.get("resolution"))
    if stored_resolution is not None and observed_resolution is not None:
        resolution_matched: bool | None = (
            stored_resolution == observed_resolution)
    else:
        resolution_matched = True if sha_matched else None
    container_matched = _container_matches(
        item.get("container"), observed.get("container"))
    if container_matched is None and sha_matched:
        container_matched = True
    codec_matched = _codec_matches(
        item.get("videoCodec"), observed.get("videoCodec"))
    if codec_matched is None and sha_matched:
        codec_matched = True
    return {
        "kind": IDENTITY_TOLERANT,
        "shaMatched": bool(sha_matched),
        "durationDeltaSeconds": duration_delta,
        "resolutionMatched": resolution_matched,
        "containerMatched": container_matched,
        "codecMatched": codec_matched,
    }


def _tolerance_problems(
    item: dict[str, Any], observed: dict[str, Any], mode: str,
) -> list[str]:
    """List every content-identity mismatch in stable, specific order."""
    problems: list[str] = []
    stored_duration = _number(item.get("durationSeconds"))
    observed_duration = _number(observed.get("durationSeconds"))
    if stored_duration is None or observed_duration is None:
        problems.append("no comparable stored duration")
    else:
        delta = abs(observed_duration - stored_duration)
        if delta > IDENTITY_DURATION_TOLERANCE_SECONDS:
            problems.append(
                f"duration delta {delta:.3f}s exceeds "
                f"{IDENTITY_DURATION_TOLERANCE_SECONDS:g}s")
    stored_resolution = _resolution(item.get("resolution"))
    observed_resolution = _resolution(observed.get("resolution"))
    if stored_resolution is None or observed_resolution is None:
        problems.append("no comparable stored resolution")
    elif stored_resolution != observed_resolution:
        problems.append(
            f"resolution {observed_resolution} != stored {stored_resolution}")
    container_matched = _container_matches(
        item.get("container"), observed.get("container"))
    if container_matched is None:
        problems.append("no comparable stored container")
    elif not container_matched:
        problems.append("container family changed")
    if mode != "youtube":
        codec_matched = _codec_matches(
            item.get("videoCodec"), observed.get("videoCodec"))
        if codec_matched is None:
            problems.append("no comparable stored video codec")
        elif not codec_matched:
            problems.append("video codec family changed")
    return problems


def _identity_failure(
    item: dict[str, Any], block: dict[str, Any], allow_media_change: bool,
    detail: str,
) -> dict[str, Any]:
    """Fail the gate, or record an explicitly forced measurement."""
    item["identityFailureDetail"] = detail
    if allow_media_change:
        return {
            **block,
            "kind": IDENTITY_FORCED,
            "shaMatched": False,
            "reason": detail,
        }
    raise MediaChanged(detail, detail=detail)


def verify_identity(
    item: dict[str, Any], observed: dict[str, Any], *, method: str | None,
    strict_identity: bool = False, allow_media_change: bool = False,
) -> dict[str, Any]:
    """Apply the delivery-dependent identity gate and return its record block.

    Direct HTTP/MP4 deliveries keep strict SHA-256 equality. Remuxed HLS and
    yt-dlp arrangements compare duration (within 0.5 s), resolution and
    container/codec family instead; YouTube additionally tolerates a codec
    family change because it serves different renditions per request.
    ``strict_identity`` forces the SHA rule for every method, and
    ``allow_media_change`` converts a would-be failure into a visible
    ``forced`` measurement. A tampered identity is never reported as bytes.
    """
    stored_sha = str(item.get("mediaSha256") or "").strip().lower() or None
    observed_sha = str(observed.get("mediaSha256") or "").strip().lower() or None
    sha_matched = bool(stored_sha and observed_sha and stored_sha == observed_sha)
    block = _tolerance_block(item, observed, sha_matched)
    mode = _identity_mode(item, method)

    if mode == "byte" or strict_identity:
        if stored_sha is None:
            # Nothing was stored to compare against; behaviour is unchanged.
            return {"kind": IDENTITY_STRICT, "shaMatched": None}
        if sha_matched:
            return {"kind": IDENTITY_STRICT, "shaMatched": True}
        detail = f"sha256 {observed_sha or 'unknown'} != stored {stored_sha}"
        return _identity_failure(
            item, block, allow_media_change, detail)

    if sha_matched:
        return {**block, "kind": IDENTITY_TOLERANT}
    problems = _tolerance_problems(item, observed, mode)
    if not problems:
        return {**block, "kind": IDENTITY_TOLERANT}
    return _identity_failure(
        item, block, allow_media_change, "; ".join(problems))


def _identity_count_key(block: Any) -> str | None:
    kind = block.get("kind") if isinstance(block, dict) else None
    if kind == IDENTITY_STRICT:
        return "strict-sha"
    if kind == IDENTITY_FORCED:
        return "forced"
    if isinstance(kind, str) and kind.strip():
        return "tolerant"
    return None


def identity_counts(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Count measured records by identity group for the run summary."""
    counts = {key: 0 for key in IDENTITY_COUNT_KEYS}
    for record in records:
        key = _identity_count_key(record.get("identityVerification"))
        if key is not None:
            counts[key] += 1
    return counts


def _catalog_rows(payload: Any) -> list[dict[str, Any]]:
    """Find a catalog's row list whatever the adapter calls it."""
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = None
        for key in CATALOG_ROW_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                candidates = value
                break
        if candidates is None:
            for value in payload.values():
                if (isinstance(value, list) and value
                        and isinstance(value[0], dict)):
                    candidates = value
                    break
        candidates = candidates or []
    else:
        candidates = []
    return [row for row in candidates if isinstance(row, dict)]


def load_catalog_urls(paths: Iterable[Path]) -> dict[str, str]:
    """Index catalog rows by every adapter id key, keeping the first URL seen.

    The catalog is read once per site. A row without a playable URL (for
    example a directorslibrary "unsupported-embed" item) contributes no
    fallback, but its identity keys are still harmless to skip.
    """
    urls: dict[str, str] = {}
    for path in paths:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(f"catalog {path}: unreadable ({safe_error(error)})",
                  file=sys.stderr)
            continue
        for row in _catalog_rows(payload):
            url = _first_text(row, CATALOG_URL_KEYS)
            if not url:
                continue
            for key in CATALOG_ID_KEYS:
                value = row.get(key)
                if value is not None and str(value).strip():
                    urls.setdefault(str(value).strip(), url)
    return urls


def catalog_paths_for_site(
    root: Path, site: str, explicit: Iterable[Path], *, single_site: bool,
) -> list[Path]:
    """Resolve one site's catalog paths from ``--catalog`` or auto-discovery."""
    explicit = [Path(path) for path in explicit]
    if not explicit:
        discovered = root / site / "catalog.json"
        return [discovered] if discovered.is_file() else []
    matching = [path for path in explicit if site in path.parts]
    if matching:
        return matching
    # An explicit catalog that does not name a site is unambiguous only when
    # the run itself has one site; never apply it to an unrelated site.
    return explicit if single_site else []


def _http_status(error: BaseException) -> int | None:
    """Extract an HTTP status from an error or its cause chain."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, HTTPError) and isinstance(current.code, int):
            return current.code
        code = getattr(current, "code", None)
        if isinstance(code, int) and 100 <= code <= 599:
            return code
        current = current.__cause__ or current.__context__
    return None


def is_stale_signed_url(error: BaseException) -> bool:
    """True when the failure is a 4xx that signed media URLs use for expiry.

    ffprobe/ffmpeg transport errors arrive as plain ``ValueError`` text
    (``Server returned 404 Not Found``), while urllib raises ``HTTPError``.
    Both shapes are covered without treating arbitrary 4xx-shaped numbers in
    unrelated messages as a status.
    """
    status = _http_status(error)
    if status is None:
        match = re.search(
            r"(?i)\b(?:http(?:\s+error)?|server returned|status(?:\s+code)?)"
            r"\s*[:=]?\s*(4\d\d)\b", str(error))
        if match:
            status = int(match.group(1))
    return status in STALE_SIGNED_STATUSES


class _NoRedirect(HTTPRedirectHandler):
    """Surface each redirect hop so a resolved HLS base can be validated."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def resolve_hls_base(
    url: str, *, allowed_hosts: Iterable[str], allow_query: bool,
    timeout: float = 30.0, attempts: int = 6,
) -> str:
    """Follow an HLS entry's redirect chain to its final master URL.

    Vimeo's ``player.vimeo.com/external/<id>.m3u8`` entry redirects to a signed
    ``vod-adaptive-*.vimeocdn.com`` master whose variant/audio URIs are
    *relative*. Resolving those against the pre-redirect URL silently produces
    404s, so the final URL is the base the playback planner needs. Every hop is
    re-validated with the same allowlist and query opt-in, and the expiry-bearing
    URL is used immediately, never persisted.
    """
    opener = build_opener(_NoRedirect())
    current = url
    for _ in range(attempts):
        allowlisted_url(current, allowed_hosts=allowed_hosts,
                        label="HLS entry URL", allow_query=allow_query)
        request = Request(current, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.apple.mpegurl,application/x-mpegURL,*/*",
        })
        try:
            with opener.open(request, timeout=timeout):
                return current
        except HTTPError as error:
            if error.code not in (301, 302, 303, 307, 308):
                raise
            location = error.headers.get("Location")
            if not location:
                raise ValueError("HLS redirect had no Location header") from None
            current = urljoin(current, location)
    raise ValueError("HLS redirect chain exceeded the bounded hop count")


def load_ids_file(path: Path) -> list[str]:
    """Read an explicit id selection: JSON list, ``{"ids": [...]}``, or lines.

    Ids are compared as ``str()`` everywhere, so catalog integers and JSON
    strings are interchangeable. Malformed files raise ``ValueError`` naming the
    path and the reason; blank ids are refused so an empty line cannot silently
    widen the selection.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"ids file {path}: unreadable ({error})") from None
    stripped = text.strip()
    if not stripped:
        raise ValueError(f"ids file {path}: file is empty")
    if stripped[0] in "[{\"":
        try:
            payload = json.loads(stripped)
        except ValueError as error:
            raise ValueError(f"ids file {path}: invalid JSON ({error})") from None
        if isinstance(payload, dict):
            if "ids" not in payload:
                raise ValueError(
                    f'ids file {path}: JSON object must contain an "ids" list')
            payload = payload["ids"]
        if not isinstance(payload, list):
            raise ValueError(
                f'ids file {path}: expected a JSON list or an object with an '
                f'"ids" list')
        raw = payload
    else:
        raw = text.splitlines()
    ids: list[str] = []
    for value in raw:
        if isinstance(value, (dict, list)):
            raise ValueError(f"ids file {path}: id {value!r} is not a scalar")
        if value is None:
            raise ValueError(f"ids file {path}: null id is not allowed")
        identifier = str(value).strip()
        if not identifier:
            raise ValueError(f"ids file {path}: empty id after stripping")
        ids.append(identifier)
    return ids


def select_ids(
    rows: Iterable[dict[str, Any]], ids: Iterable[str], *, key: str = "id",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Filter rows to the id set, preserving order; return missing ids."""
    wanted = {str(value) for value in ids}
    chosen = [row for row in rows
              if row.get(key) is not None and str(row.get(key)) in wanted]
    present = {str(row.get(key)) for row in rows if row.get(key) is not None}
    return chosen, sorted(wanted - present)


def load_items(
    root: Path, site: str, *, max_duration_seconds: float, max_file_bytes: int,
    resume: bool, catalog: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load one site's records into work items plus pre-download skip rows."""
    policy = SITE_POLICY[site]
    catalog = catalog or {}
    videos_dir = root / site / "videos"
    census_dir = root / site / "census"
    work: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []
    for record_path in sorted(videos_dir.glob("*.json")):
        relative = str(record_path.relative_to(root))
        try:
            payload = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            skips.append({"id": record_path.stem, "slug": "",
                          "recordPath": relative,
                          "reason": "unreadable-record"})
            continue
        identity = extract_record_identity(
            payload, fallback_id=record_path.stem.split("-", 1)[0])
        label_id = identity["id"] or record_path.stem
        label_slug = identity["slug"] or ""
        base = {"id": label_id, "slug": label_slug, "recordPath": relative}
        catalog_url = catalog.get(str(label_id))
        video_url = identity["videoUrl"]
        url_source = "record"
        if not video_url and catalog_url:
            video_url = catalog_url
            url_source = "catalog"
        if not video_url:
            skips.append({**base, "reason": "missing-url"})
            continue
        try:
            delivery = _delivery_mode(video_url, identity["provider"])
            url = _canonical_url(video_url, delivery)
        except ValueError:
            skips.append({**base, "reason": "unsupported-url"})
            continue
        duration = identity["durationSeconds"]
        if (isinstance(duration, (int, float)) and duration > 0
                and duration > max_duration_seconds):
            skips.append({**base, "reason": "duration-exceeds-limit"})
            continue
        size = identity["sizeBytes"]
        if isinstance(size, int) and size > max_file_bytes:
            skips.append({**base, "reason": "size-exceeds-limit"})
            continue
        stem = safe_slug(f"{label_id}-{identity['slug']}")
        output_path = census_dir / f"{stem}.json"
        if resume and output_path.exists():
            skips.append({**base, "reason": "resume-existing-record"})
            continue
        work.append({
            **base,
            "videoUrl": url,
            "catalogUrl": catalog_url,
            "urlSource": url_source,
            "storedProvider": identity["provider"],
            "storedMethod": identity["acquisitionMethod"],
            "delivery": delivery,
            "mediaSha256": identity["mediaSha256"],
            "durationSeconds": identity["durationSeconds"],
            "resolution": identity["resolution"],
            "container": identity["container"],
            "videoCodec": identity["videoCodec"],
            "hosts": policy["hosts"],
            "allowQuery": policy["allow_query"],
            "outputPath": output_path,
        })
    return work, skips


def run_census_item(
    item: dict[str, Any], *, site: str, options: argparse.Namespace,
) -> dict[str, Any]:
    """Acquire → verify → scan → write → delete for one work item."""
    with tempfile.TemporaryDirectory(prefix="kumiki-census-") as directory:
        media_dir = Path(directory)

        def acquire(url: str) -> tuple[Path, str]:
            target = url
            if item["delivery"] == HLS:
                target = resolve_hls_base(
                    url, allowed_hosts=item["hosts"],
                    allow_query=item["allowQuery"])
            return download_media(
                target, item["delivery"], media_dir,
                allowed_hosts=item["hosts"], max_bytes=options.max_file_bytes,
                max_width=1280,
                max_duration_seconds=options.max_duration_seconds,
                ffmpeg=options.ffmpeg, ffprobe=options.ffprobe,
                yt_dlp=options.yt_dlp, allow_query=item["allowQuery"])

        used_url = item["videoUrl"]
        used_source = item.get("urlSource", "record")
        try:
            path, method = acquire(used_url)
        except Exception as error:
            catalog_url = item.get("catalogUrl")
            signed_4xx = (item["allowQuery"]
                          and is_stale_signed_url(error))
            if (signed_4xx and used_source == "record" and catalog_url
                    and catalog_url != used_url):
                try:
                    path, method = acquire(catalog_url)
                except Exception as fallback_error:
                    if (item["allowQuery"]
                            and is_stale_signed_url(fallback_error)):
                        raise StaleSignedUrl(
                            "signed URL rejected with catalog fallback"
                        ) from None
                    raise
                used_url = catalog_url
                used_source = "catalog"
                item["urlSource"] = "catalog"
                item["fallbackApplied"] = True
            elif signed_4xx:
                raise StaleSignedUrl("signed URL rejected") from None
            else:
                raise
        metadata = source_metadata(path, ffprobe=options.ffprobe)
        item.pop("identityFailureDetail", None)
        identity = verify_identity(
            item, metadata, method=method,
            strict_identity=getattr(options, "strict_identity", False),
            allow_media_change=getattr(options, "allow_media_change", False))
        scan = scan_full_runtime(
            path, sample_seconds=options.sample_seconds,
            width=160, height=90,
            ffmpeg=options.ffmpeg, ffprobe=options.ffprobe,
            timeout_seconds=options.timeout_seconds)
        evidence = build_census_evidence(
            scan, source=metadata, video_url=used_url,
            provider=item["storedProvider"] or item["delivery"],
            download_method=method, rights_basis=RIGHTS_BASIS,
            rights_note=RIGHTS_NOTE,
            schema_version=f"kumiki.{site}-census-evidence.v1",
            evidence_status=EVIDENCE_STATUS, limits=CENSUS_LIMITS)
        evidence["site"] = site
        evidence["acquisition"]["urlSource"] = used_source
        evidence["record"] = {
            "id": item["id"],
            "slug": item["slug"],
            "path": item["recordPath"],
            "storedMediaSha256": item.get("mediaSha256"),
            "urlSource": used_source,
        }
        evidence["identityVerification"] = identity
        evidence["mediaRetained"] = False
        write_json_atomic(item["outputPath"], evidence)
    return {
        "id": item["id"],
        "slug": item["slug"],
        "recordPath": item["recordPath"],
        "censusPath": str(item["outputPath"].relative_to(options.root)),
        "durationSeconds": scan["durationSeconds"],
        "cutCount": scan["cutCount"],
        "cutsPerMinute": scan["cutsPerMinute"],
        "strobe": scan["strobe"],
        "method": method,
        "urlSource": used_source,
        "identityVerification": identity,
    }


def _failure_row(item: dict[str, Any], reason: str) -> dict[str, Any]:
    row = {
        "id": item["id"], "slug": item["slug"],
        "recordPath": item["recordPath"], "reason": reason,
    }
    detail = item.get("identityFailureDetail")
    if detail and reason == MediaChanged.reason:
        row["detail"] = detail
    return row


def _skip_row(item: dict[str, Any], reason: str) -> dict[str, Any]:
    return _failure_row(item, reason)


def _error_text(error: Exception) -> str:
    if isinstance(error, MediaChanged):
        return MediaChanged.reason
    if isinstance(error, StaleSignedUrl):
        return StaleSignedUrl.reason
    return safe_error(error)


def census_site(
    root: Path, site: str, *, options: argparse.Namespace,
    catalog_paths: Iterable[Path] = (),
) -> Any:
    catalog = load_catalog_urls(catalog_paths)
    work, pre_skips = load_items(
        root, site, max_duration_seconds=options.max_duration_seconds,
        max_file_bytes=options.max_file_bytes, resume=options.resume,
        catalog=catalog)
    ids = (load_ids_file(options.ids_file)
           if getattr(options, "ids_file", None) is not None else None)
    if ids is not None:
        wanted = set(ids)
        present = ({str(item["id"]) for item in work}
                   | {str(row["id"]) for row in pre_skips})
        print(f"ids={len(wanted)} matched={len(wanted & present)} "
              f"missing={len(wanted - present)}")
        work = [item for item in work if str(item["id"]) in wanted]
        pre_skips = [row for row in pre_skips if str(row["id"]) in wanted]
        pre_skips.extend(
            {"id": identifier, "slug": "", "recordPath": None,
             "reason": "missing-from-catalog"}
            for identifier in sorted(wanted - present))
    if options.limit and options.limit > 0:
        work = work[:options.limit]
    print(f"selection: {len(work)} items selected "
          f"(limit={'all' if not options.limit else options.limit}, ids="
          f"{'file' if ids is not None else 'records'})")
    index_path = root / site / "census-index.json"
    schema = f"kumiki.{site}-census-index.v1"
    identity_summary: dict[str, int] = {key: 0 for key in IDENTITY_COUNT_KEYS}

    def build(records: list[dict[str, Any]], skips: list[dict[str, Any]],
              failures: list[dict[str, Any]]) -> dict[str, Any]:
        counts = identity_counts(records)
        identity_summary.update(counts)
        return build_index(
            schema_version=schema, records=records, skips=skips,
            failures=failures, generated_at=utc_now(),
            extra={
                "site": site,
                "sourceRoot": str((root / site / "videos").relative_to(root)),
                "sampleSeconds": options.sample_seconds,
                "windowSeconds": options.window_seconds,
                "identityCounts": counts,
                "limits": CENSUS_LIMITS,
            })

    items_by_label = {f"{item['id']}-{item['slug']}": item for item in work}

    def progress(position: int, total: int, status: str, label: str,
                 detail: str) -> None:
        if status == "ok" and not detail:
            item = items_by_label.get(label)
            if item is not None and item.get("fallbackApplied"):
                detail = "url-from-catalog"
        suffix = f" {detail}" if detail else ""
        print(f"[{position}/{total}] {status} {label}{suffix}")

    outcome = run_batch(
        work,
        run_one=lambda item: run_census_item(
            item, site=site, options=options),
        index_path=index_path, build_index=build,
        summary_row=lambda record: record, skip_row=_skip_row,
        failure_row=_failure_row,
        describe=lambda item: f"{item['id']}-{item['slug']}",
        initial_skips=pre_skips,
        error_text=_error_text,
        progress=progress, jobs=options.jobs,
        delay_seconds=options.delay_seconds)
    print(f"{site}: measured={outcome.measured} skipped={outcome.skipped} "
          f"failed={outcome.failed} index={outcome.index_path}")
    print(f"{site}: identity strict-sha={identity_summary['strict-sha']} "
          f"tolerant={identity_summary['tolerant']} "
          f"forced={identity_summary['forced']}")
    return outcome


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="research/analysis",
                        help="evidence root containing <site>/videos")
    parser.add_argument("--site", action="append", default=[],
                        help="site directory name (repeatable)")
    parser.add_argument("--catalog", action="append", default=[],
                        type=Path,
                        help="catalog JSON for URL re-resolution (repeatable; "
                             "defaults to <root>/<site>/catalog.json)")
    parser.add_argument("--limit", type=int, default=0,
                        help="items per site; 0 means all remaining")
    parser.add_argument("--ids-file", type=Path, default=None,
                        help="JSON id list / {\"ids\": [...]} / newline ids; "
                             "--limit applies to the filtered selection")
    parser.add_argument("--jobs", type=int, default=1, choices=(1, 2))
    parser.add_argument("--delay-seconds", type=float, default=1.2)
    parser.add_argument("--max-duration-seconds", type=float, default=600.0)
    parser.add_argument("--max-file-bytes", type=parse_bytes,
                        default=parse_bytes("400MiB"))
    parser.add_argument("--window-seconds", type=float, default=None,
                        help="legacy cadence alias; defaults to sample seconds")
    parser.add_argument("--sample-seconds", type=float, default=None,
                        help="fixed appearance cadence (default 1.0)")
    parser.add_argument("--acknowledge-rights", action="store_true",
                        help="required: attest public research use")
    parser.add_argument("--strict-identity", action="store_true",
                        help="require the stored SHA-256 for every delivery "
                             "method, including remuxed HLS and YouTube")
    parser.add_argument("--allow-media-change", action="store_true",
                        help="measure a record whose identity cannot be "
                             "established and mark it identityVerification "
                             "kind=forced")
    parser.add_argument("--resume", dest="resume", action="store_true",
                        default=True, help="skip existing census records")
    parser.add_argument("--refresh", dest="resume", action="store_false",
                        help="re-measure existing census records")
    parser.add_argument("--timeout-seconds", type=float, default=3600.0,
                        help="per-ffmpeg-pass timeout")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--yt-dlp", default="yt-dlp")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    options = parser.parse_args(argv)
    if not options.acknowledge_rights:
        parser.error("--acknowledge-rights is required for public media work")
    if options.limit < 0:
        parser.error("--limit must be zero or positive")
    if options.jobs not in (1, 2):
        parser.error("--jobs must be 1 or 2")
    if options.strict_identity and options.allow_media_change:
        parser.error(
            "--strict-identity and --allow-media-change are mutually exclusive")
    options.sample_seconds = options.sample_seconds or options.window_seconds or 1.0
    options.window_seconds = options.window_seconds or options.sample_seconds
    root = Path(options.root)
    if not root.is_dir():
        parser.error(f"--root {root} is not a directory")
    sites = options.site or [
        name for name in SITE_POLICY
        if (root / name / "videos").is_dir()]
    unknown = [name for name in sites if name not in SITE_POLICY]
    if unknown:
        parser.error(f"no site policy for: {', '.join(unknown)}")
    options.root = root
    single_site = len(sites) == 1
    for site in sites:
        if not (root / site / "videos").is_dir():
            parser.error(f"{site} has no videos directory under {root}")
        catalog_paths = catalog_paths_for_site(
            root, site, options.catalog, single_site=single_site)
        census_site(root, site, options=options, catalog_paths=catalog_paths)
    return 0


if __name__ == "__main__":
    sys.exit(main())
