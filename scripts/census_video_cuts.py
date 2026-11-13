#!/usr/bin/env python3
"""Full-runtime cut census over the existing video-evidence trees.

For every ``<root>/<site>/videos/*.json`` record this driver recovers the
canonical upstream URL, re-downloads the public media once, verifies the stored
media SHA-256, decodes the whole file twice (scene candidates + fixed-cadence
appearance), writes one census record atomically, and deletes the media.

Usage:
    PYTHONPATH=src python scripts/census_video_cuts.py --acknowledge-rights \
        --site promonews --limit 2

The output tree stays inside ``--root``; the smoke run uses a temporary root so
``research/analysis`` is never modified.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from kumiki_reference_lab.acquisition import (
    DIRECT, DEFAULT_YOUTUBE_HOSTS, HLS, YOUTUBE,
    allowlisted_youtube_url, build_census_evidence, build_index,
    download_media, run_batch, safe_error, safe_slug, scan_full_runtime,
    source_metadata, utc_now, write_json_atomic,
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
    "Media bytes are not retained and the media SHA-256 is the record's "
    "identity check, not a licence.",
]

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


class MediaChanged(Exception):
    """Raised when the re-downloaded media no longer matches the record."""

    reason = "media-changed"


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
        for key in ("id", "nid", "postId", "clipId", "projectId"):
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

    return {
        "id": record_id,
        "slug": slug,
        "videoUrl": video_url,
        "provider": provider,
        "mediaSha256": (media_sha256 or "").lower() or None,
        "durationSeconds": duration,
        "sizeBytes": size,
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


def load_items(
    root: Path, site: str, *, max_duration_seconds: float, max_file_bytes: int,
    resume: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load one site's records into work items plus pre-download skip rows."""
    policy = SITE_POLICY[site]
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
        if not identity["videoUrl"]:
            skips.append({**base, "reason": "missing-url"})
            continue
        try:
            delivery = _delivery_mode(identity["videoUrl"],
                                      identity["provider"])
            url = _canonical_url(identity["videoUrl"], delivery)
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
            "storedProvider": identity["provider"],
            "delivery": delivery,
            "mediaSha256": identity["mediaSha256"],
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
        path, method = download_media(
            item["videoUrl"], item["delivery"], media_dir,
            allowed_hosts=item["hosts"], max_bytes=options.max_file_bytes,
            max_width=1280,
            max_duration_seconds=options.max_duration_seconds,
            ffmpeg=options.ffmpeg, ffprobe=options.ffprobe,
            yt_dlp=options.yt_dlp, allow_query=item["allowQuery"])
        metadata = source_metadata(path, ffprobe=options.ffprobe)
        stored = item.get("mediaSha256")
        if stored and metadata["mediaSha256"] != stored:
            raise MediaChanged(
                f"stored {stored} != observed {metadata['mediaSha256']}")
        scan = scan_full_runtime(
            path, sample_seconds=options.sample_seconds,
            width=160, height=90,
            ffmpeg=options.ffmpeg, ffprobe=options.ffprobe,
            timeout_seconds=options.timeout_seconds)
        evidence = build_census_evidence(
            scan, source=metadata, video_url=item["videoUrl"],
            provider=item["storedProvider"] or item["delivery"],
            download_method=method, rights_basis=RIGHTS_BASIS,
            rights_note=RIGHTS_NOTE,
            schema_version=f"kumiki.{site}-census-evidence.v1",
            evidence_status=EVIDENCE_STATUS, limits=CENSUS_LIMITS)
        evidence["site"] = site
        evidence["record"] = {
            "id": item["id"],
            "slug": item["slug"],
            "path": item["recordPath"],
            "storedMediaSha256": stored,
        }
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
    }


def _failure_row(item: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "id": item["id"], "slug": item["slug"],
        "recordPath": item["recordPath"], "reason": reason,
    }


def _skip_row(item: dict[str, Any], reason: str) -> dict[str, Any]:
    return _failure_row(item, reason)


def _error_text(error: Exception) -> str:
    if isinstance(error, MediaChanged):
        return MediaChanged.reason
    return safe_error(error)


def census_site(
    root: Path, site: str, *, options: argparse.Namespace,
) -> Any:
    work, pre_skips = load_items(
        root, site, max_duration_seconds=options.max_duration_seconds,
        max_file_bytes=options.max_file_bytes, resume=options.resume)
    if options.limit and options.limit > 0:
        work = work[:options.limit]
    index_path = root / site / "census-index.json"
    schema = f"kumiki.{site}-census-index.v1"

    def build(records: list[dict[str, Any]], skips: list[dict[str, Any]],
              failures: list[dict[str, Any]]) -> dict[str, Any]:
        return build_index(
            schema_version=schema, records=records, skips=skips,
            failures=failures, generated_at=utc_now(),
            extra={
                "site": site,
                "sourceRoot": str((root / site / "videos").relative_to(root)),
                "sampleSeconds": options.sample_seconds,
                "windowSeconds": options.window_seconds,
                "limits": CENSUS_LIMITS,
            })

    def progress(position: int, total: int, status: str, label: str,
                 detail: str) -> None:
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
    return outcome


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="research/analysis",
                        help="evidence root containing <site>/videos")
    parser.add_argument("--site", action="append", default=[],
                        help="site directory name (repeatable)")
    parser.add_argument("--limit", type=int, default=0,
                        help="items per site; 0 means all remaining")
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
    for site in sites:
        if not (root / site / "videos").is_dir():
            parser.error(f"{site} has no videos directory under {root}")
        census_site(root, site, options=options)
    return 0


if __name__ == "__main__":
    sys.exit(main())
