#!/usr/bin/env python3
"""Audio census over the existing video-evidence trees.

For every ``<root>/<site>/videos/*.json`` record this driver recovers the
canonical upstream URL, re-downloads the public media once, verifies that the
observed duration still matches the record, extracts the audio stream to mono
8 kHz PCM, runs ffmpeg's EBU R128 filter for the loudness/peak summary, writes
one audio record atomically, and deletes both the media and the PCM.

The measurement is numeric only: no speech/music separation, no transcription,
no instrument or genre identification, no mix-quality judgement and no
sync-to-picture claim. Media bytes never enter the evidence tree.

Usage:
    PYTHONPATH=src python scripts/audio_census.py --acknowledge-rights \
        --sites shots,promonews,motiondesignawards --sample-stratified 40
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from kumiki_reference_lab.acquisition import (
    DIRECT, HLS, YOUTUBE, build_index, download_media, run_batch, safe_error,
    safe_slug, source_metadata, utc_now, write_json_atomic,
)
from kumiki_reference_lab.acquisition.audio import (
    AUDIO_LIMITS, PCM_SAMPLE_RATE, ebur128_summary, extract_audio,
    has_audio_stream, measure_audio,
)
from kumiki_reference_lab.acquisition.runner import BatchSkip
from kumiki_reference_lab.backends.ffmpeg.probe import probe_media


def _load_census_tools() -> Any:
    """Load the sibling cut-census driver for its shared URL resolution."""
    path = Path(__file__).resolve().with_name("census_video_cuts.py")
    spec = importlib.util.spec_from_file_location(
        "kumiki_audio_census_tools", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("the cut-census driver could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CENSUS = _load_census_tools()
SITE_POLICY: dict[str, dict[str, Any]] = _CENSUS.SITE_POLICY

extract_record_identity = _CENSUS.extract_record_identity
load_catalog_urls = _CENSUS.load_catalog_urls
catalog_paths_for_site = _CENSUS.catalog_paths_for_site
resolve_hls_base = _CENSUS.resolve_hls_base
parse_bytes = _CENSUS.parse_bytes
is_stale_signed_url = _CENSUS.is_stale_signed_url
StaleSignedUrl = _CENSUS.StaleSignedUrl

RIGHTS_BASIS = "user-declared-research-use"
RIGHTS_NOTE = (
    "operator attests public-page research use; the public rendition is "
    "downloaded once, its audio stream is measured numerically, and both the "
    "media and the extracted PCM are deleted without redistribution")
EVIDENCE_STATUS = "full-runtime-audio-numeric-census-not-human-reviewed"
DURATION_TOLERANCE_SECONDS = 1.0


def _delivery_mode(url: str, provider: str | None) -> str:
    name = (provider or "").lower()
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if name == "youtube" or "youtube.com" in host or "youtu.be" in host:
        return YOUTUBE
    path = parsed.path.lower()
    if name in ("hls", "cloudflare-stream", "vimeo") or path.endswith(".m3u8"):
        return HLS
    return DIRECT


def _canonical_url(url: str, delivery: str) -> str:
    if delivery == YOUTUBE:
        return _CENSUS.allowlisted_youtube_url(
            url, allowed_hosts=_CENSUS.DEFAULT_YOUTUBE_HOSTS)
    return url


def stratified_sample(paths: Iterable[Path], sample: int) -> list[Path]:
    """Pick ``sample`` records spread evenly across the ordered record list.

    Selection uses the centre of each equal-width slice, so the first and last
    records are represented and no recent-record bias is introduced. When the
    sample is zero or at least the list size, the whole list is returned.
    """
    ordered = list(paths)
    if sample <= 0 or sample >= len(ordered):
        return ordered
    step = len(ordered) / sample
    indices: list[int] = []
    for position in range(sample):
        index = min(len(ordered) - 1, int((position + 0.5) * step))
        if not indices or index > indices[-1]:
            indices.append(index)
    return [ordered[index] for index in indices]


def load_items(
    root: Path, site: str, *, max_duration_seconds: float, max_file_bytes: int,
    resume: bool, catalog: dict[str, str] | None = None,
    paths: Iterable[Path] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load one site's records into work items plus pre-download skip rows."""
    policy = SITE_POLICY[site]
    catalog = catalog or {}
    videos_dir = root / site / "videos"
    audio_dir = root / site / "audio"
    if paths is None:
        paths = sorted(videos_dir.glob("*.json"))
    work: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []
    for record_path in paths:
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
        output_path = audio_dir / f"{stem}.json"
        if resume and output_path.exists():
            skips.append({**base, "reason": "resume-existing-record"})
            continue
        work.append({
            **base,
            "videoUrl": url,
            "catalogUrl": catalog_url,
            "urlSource": url_source,
            "storedProvider": identity["provider"],
            "delivery": delivery,
            "mediaSha256": identity["mediaSha256"],
            "durationSeconds": duration,
            "hosts": policy["hosts"],
            "allowQuery": policy["allow_query"],
            "outputPath": output_path,
        })
    return work, skips


def _acquire_media(
    item: dict[str, Any], media_dir: Path, options: argparse.Namespace,
) -> tuple[Path, str, str, str]:
    """Download one item, retrying a stale signed URL from its catalog."""

    def acquire(url: str) -> tuple[Path, str]:
        target = url
        if item["delivery"] == HLS:
            target = resolve_hls_base(
                url, allowed_hosts=item["hosts"],
                allow_query=item["allowQuery"])
        return download_media(
            target, item["delivery"], media_dir,
            allowed_hosts=item["hosts"], max_bytes=options.max_file_bytes,
            max_width=1280, max_duration_seconds=options.max_duration_seconds,
            ffmpeg=options.ffmpeg, ffprobe=options.ffprobe,
            yt_dlp=options.yt_dlp, allow_query=item["allowQuery"])

    used_url = item["videoUrl"]
    used_source = item.get("urlSource", "record")
    try:
        path, method = acquire(used_url)
    except Exception as error:
        catalog_url = item.get("catalogUrl")
        signed_4xx = item["allowQuery"] and is_stale_signed_url(error)
        if (signed_4xx and used_source == "record" and catalog_url
                and catalog_url != used_url):
            try:
                path, method = acquire(catalog_url)
            except Exception as fallback_error:
                if (item["allowQuery"]
                        and is_stale_signed_url(fallback_error)):
                    raise StaleSignedUrl(
                        "signed URL rejected with catalog fallback") from None
                raise
            used_url = catalog_url
            used_source = "catalog"
            item["urlSource"] = "catalog"
            item["fallbackApplied"] = True
        elif signed_4xx:
            raise StaleSignedUrl("signed URL rejected") from None
        else:
            raise
    return path, method, used_url, used_source


def run_audio_item(
    item: dict[str, Any], *, site: str, options: argparse.Namespace,
) -> dict[str, Any]:
    """Acquire → verify → extract → measure → write → delete one work item."""
    with tempfile.TemporaryDirectory(prefix="kumiki-audio-") as directory:
        media_dir = Path(directory)
        media_path: Path | None = None
        pcm_path: Path | None = None
        try:
            media_path, method, used_url, used_source = _acquire_media(
                item, media_dir, options)
            probe = probe_media(media_path, ffprobe=options.ffprobe)
            if not has_audio_stream(probe):
                raise BatchSkip("no-audio-stream")
            metadata = source_metadata(media_path, ffprobe=options.ffprobe)
            observed_duration = metadata.get("durationSeconds")
            stored_duration = item.get("durationSeconds")
            if (isinstance(stored_duration, (int, float))
                    and isinstance(observed_duration, (int, float))
                    and abs(float(observed_duration)
                            - float(stored_duration))
                    > DURATION_TOLERANCE_SECONDS):
                raise BatchSkip("duration-mismatch")

            pcm_path = extract_audio(
                media_path, media_dir / "source.pcm",
                ffmpeg=options.ffmpeg, sample_rate=PCM_SAMPLE_RATE,
                timeout_seconds=options.timeout_seconds)
            summary = ebur128_summary(
                media_path, ffmpeg=options.ffmpeg,
                timeout_seconds=options.timeout_seconds)
            measurement = measure_audio(pcm_path, loudness_summary=summary)

            stored_sha = item.get("mediaSha256")
            observed_sha = metadata.get("mediaSha256")
            sha_matches = None
            if stored_sha and observed_sha:
                sha_matches = (str(observed_sha).lower()
                               == str(stored_sha).lower())
            provider = item["storedProvider"] or item["delivery"]

            evidence = {
                "schemaVersion": f"kumiki.{site}-audio-evidence.v1",
                "site": site,
                "record": {
                    "id": item["id"],
                    "slug": item["slug"],
                    "path": item["recordPath"],
                    "storedMediaSha256": stored_sha,
                    "urlSource": used_source,
                },
                "source": {
                    "videoUrl": used_url,
                    "provider": provider,
                    "downloadMethod": method,
                    "mediaSha256Observed": observed_sha,
                    "shaMatchesRecord": sha_matches,
                    "sizeBytes": metadata.get("sizeBytes"),
                    "durationSeconds": observed_duration,
                    "audioCodec": metadata.get("audioCodec"),
                },
                "acquisition": {
                    "provider": provider,
                    "method": method,
                    "mediaRetained": False,
                    "sampleRateHz": PCM_SAMPLE_RATE,
                    "attestation": {
                        "rightsBasis": RIGHTS_BASIS,
                        "note": RIGHTS_NOTE,
                    },
                },
                "audio": measurement,
                "evidenceStatus": EVIDENCE_STATUS,
                "rightsStatus": "review-required",
                "generatedAt": utc_now(),
            }
            write_json_atomic(item["outputPath"], evidence)
        finally:
            for path in (pcm_path, media_path):
                if path is not None:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass

    return {
        "id": item["id"],
        "slug": item["slug"],
        "recordPath": item["recordPath"],
        "audioPath": str(item["outputPath"].relative_to(options.root)),
        "durationSeconds": measurement["durationSeconds"],
        "sourceDurationSeconds": observed_duration,
        "integratedLufs": measurement["integratedLufs"],
        "loudnessRangeLu": measurement["loudnessRangeLu"],
        "truePeakDbfs": measurement["truePeakDbfs"],
        "rmsDbfs": measurement["rmsDbfs"],
        "silenceFraction": measurement["silenceFraction"],
        "onsetCount": measurement["onsetCount"],
        "onsetsPerMinuteOfRuntime": measurement["onsetsPerMinuteOfRuntime"],
        "onsetRateTrend": measurement["onsetRateTrend"],
        "tempoHypothesisBpm": measurement["tempoHypothesisBpm"],
        "shaMatchesRecord": sha_matches,
        "method": method,
        "urlSource": used_source,
    }


def _failure_row(item: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "id": item["id"], "slug": item["slug"],
        "recordPath": item["recordPath"], "reason": reason,
    }


def _skip_row(item: dict[str, Any], reason: str) -> dict[str, Any]:
    return _failure_row(item, reason)


def _error_text(error: Exception) -> str:
    if isinstance(error, StaleSignedUrl):
        return StaleSignedUrl.reason
    return safe_error(error)


def audio_site(
    root: Path, site: str, *, options: argparse.Namespace,
    catalog_paths: Iterable[Path] = (),
) -> Any:
    catalog = load_catalog_urls(catalog_paths)
    videos_dir = root / site / "videos"
    paths = sorted(videos_dir.glob("*.json"))
    if options.sample_stratified:
        paths = stratified_sample(paths, options.sample_stratified)
    work, pre_skips = load_items(
        root, site, max_duration_seconds=options.max_duration_seconds,
        max_file_bytes=options.max_file_bytes, resume=options.resume,
        catalog=catalog, paths=paths)
    if options.limit and options.limit > 0:
        work = work[:options.limit]
    index_path = root / site / "audio-index.json"
    schema = f"kumiki.{site}-audio-index.v1"

    def build(records: list[dict[str, Any]], skips: list[dict[str, Any]],
              failures: list[dict[str, Any]]) -> dict[str, Any]:
        return build_index(
            schema_version=schema, records=records, skips=skips,
            failures=failures, generated_at=utc_now(),
            extra={
                "site": site,
                "sourceRoot": str(videos_dir.relative_to(root)),
                "sampleRateHz": PCM_SAMPLE_RATE,
                "sampleStratified": options.sample_stratified or None,
                "limits": list(AUDIO_LIMITS),
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
        run_one=lambda item: run_audio_item(item, site=site, options=options),
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
    parser.add_argument("--sites", default="",
                        help="comma-separated site directory names")
    parser.add_argument("--limit", type=int, default=0,
                        help="items per site; 0 means all remaining")
    parser.add_argument("--jobs", type=int, default=1, choices=(1, 2))
    parser.add_argument("--delay-seconds", type=float, default=1.2)
    parser.add_argument("--max-duration-seconds", type=float, default=600.0)
    parser.add_argument("--max-file-bytes", type=parse_bytes,
                        default=parse_bytes("400MiB"))
    parser.add_argument("--sample-stratified", type=int, default=0,
                        help="sample N records evenly across each site's "
                             "record list (0 means all)")
    parser.add_argument("--acknowledge-rights", action="store_true",
                        help="required: attest public research use")
    parser.add_argument("--resume", dest="resume", action="store_true",
                        default=True, help="skip existing audio records")
    parser.add_argument("--refresh", dest="resume", action="store_false",
                        help="re-measure existing audio records")
    parser.add_argument("--timeout-seconds", type=float, default=600.0,
                        help="per-ffmpeg-operation timeout")
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
    if options.sample_stratified < 0:
        parser.error("--sample-stratified must be zero or positive")
    if options.jobs not in (1, 2):
        parser.error("--jobs must be 1 or 2")
    root = Path(options.root)
    if not root.is_dir():
        parser.error(f"--root {root} is not a directory")
    sites = list(options.site)
    if options.sites:
        sites.extend(
            name.strip() for name in options.sites.split(",") if name.strip())
    deduped: list[str] = []
    for name in sites:
        if name not in deduped:
            deduped.append(name)
    sites = deduped or [
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
            root, site, (), single_site=single_site)
        audio_site(root, site, options=options, catalog_paths=catalog_paths)
    return 0


if __name__ == "__main__":
    sys.exit(main())
