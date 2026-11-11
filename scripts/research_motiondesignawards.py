"""Ephemeral, source-hashed measurement of public Motion Design Awards entries.

Catalog metadata comes from the site's own public GraphQL endpoint. Only public,
unauthenticated video files on allowlisted delivery hosts are downloaded, and
every downloaded byte lives in a ``TemporaryDirectory`` deleted in a ``finally``
block; only numeric source-PTS evidence and catalog metadata are committed. A
second ``stills`` lane measures each project's hosted poster image the same way.
Vimeo entries are recorded as unsupported for video and never attempted (no
cookies, no login, no access-control bypass); their posters can still be
measured by ``stills``.

This is a *site adapter*: every mechanic (allowlisting, retrieval, HLS
planning/remux, probing, window and still measurement, evidence assembly, atomic
writes, resume checks, index assembly, pooled batch loop) comes from
:mod:`kumiki_reference_lab.acquisition`. To adapt another site, supply only a
catalog enumerator returning neutral rows with a stable identity field,
media/image host allowlists, schema/evidence/limits/rights strings, the resume
identity field, progress wording, and selection rules.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
from functools import partial
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition import (  # noqa: E402
    DIRECT, HLS, MAX_WINDOWS, MAX_WINDOW_SECONDS, STILL_MAX_BYTES, USER_AGENT,
    VIDEO_SUFFIXES, allowlisted_image_url, allowlisted_video_url, as_int,
    as_text, build_index, build_still_evidence, build_video_evidence,
    download_http, download_media, finite_float, image_target, measure_still,
    measure_windows, resume_matches as _resume_matches, run_batch, safe_error,
    safe_slug, source_metadata, still_image_format, utc_now, write_json_atomic,
)
from kumiki_reference_lab.analyzers.media.inspect import sha256_file  # noqa: E402

ENDPOINT = "https://www.motiondesignawards.com/api/graphql"
PROJECT_URL = "https://www.motiondesignawards.com/project/{project_id}/{slug}"
CATALOG_SCHEMA = "kumiki.motiondesignawards-catalog.v1"
INDEX_SCHEMA = "kumiki.motiondesignawards-index.v1"
VIDEO_SCHEMA = "kumiki.motiondesignawards-video-evidence.v1"
STILL_SCHEMA = "kumiki.motiondesignawards-still-evidence.v1"
STILLS_INDEX_SCHEMA = "kumiki.motiondesignawards-stills-index.v1"
EVIDENCE_STATUS = "sampled-original-source-pts-metrics-not-expert-reviewed"
STILL_EVIDENCE_STATUS = "single-published-still-metrics-not-video-measurement"
RIGHTS_BASIS = "user-declared-research-use"
RIGHTS_STATUS = "review-required"
DEFAULT_RIGHTS_NOTE = (
    "operator attests public-page research use; downloaded media is deleted "
    "after numeric source-PTS measurement and is not redistributed")

# Delivery hosts observed in this catalog. A leading dot admits subdomains
# explicitly; video and stills keep separate allowlists.
VIDEO_HOSTS = ("videodelivery.net", "storage-01-mda.keyfram.es", ".cloudflarestream.com")
IMAGE_HOSTS = ("videodelivery.net", "storage-01-mda.keyfram.es", ".cloudflarestream.com")
SUPPORTED_PROVIDERS = ("cloudflare-stream", "direct-mp4")
PROVIDER_DELIVERY = {"cloudflare-stream": HLS, "direct-mp4": DIRECT}
AWARD_TYPES = ("VOTD", "HM", "VOTM", "VOTY", "DOTY", "SOTY")

LIMITS = [
    "Sampled source-PTS windows only; this is not full-film review.",
    "Numeric display-RGB and cut-candidate proxies are not camera, lens, lighting, editing-intent, or style labels.",
    "No visual style, aesthetic quality, authorship, identity, or creative intent is inferred.",
    "Public availability is not a license; rightsStatus remains review-required.",
    "Downloaded media, frames, thumbnails, and audio are never retained.",
    "Catalog metadata is self-reported by the awards site and is not independently verified.",
]
STILL_LIMITS = [
    "A poster still is not a video frame: no motion, cut, pacing, or timing evidence.",
    "Colour and luminance are measured on the published still, which the site (not the entrant) prepared.",
    "Presence of a still says nothing about the work's runtime behaviour.",
]
STILL_COVERAGE_NOTE = (
    "single editorial poster still published by the awards site; not a decoded "
    "video frame, no motion/time evidence")

CATALOG_QUERY = """
query AllProjects($first: Int!, $page: Int!) {
  allProjects(first: $first, page: $page, orderBy: {column: VOTING_STARTED_AT, order: DESC}) {
    paginatorInfo { total hasMorePages currentPage }
    data {
      id slug title video video_provider
      thumbnail(renditions: [{width: 640}]) { original }
      wa_overall wa_concept wa_design wa_motion wa_sound total_votes
      category status is_nominee is_incubating created_at voting_closed_at
      project_website credits profile { id company }
      awards { id type date }
      tags { id title }
    }
  }
}
"""
_MAX_PAGES = 200
_MAX_RESPONSE_BYTES = 8_000_000


def classify_provider(video_url: object) -> str:
    """Classify a catalog video URL by delivery host/path, never by provider name."""
    if not isinstance(video_url, str) or not video_url.strip():
        return "other"
    try:
        parsed = urlsplit(video_url)
    except ValueError:
        return "other"
    host, path = (parsed.hostname or "").lower(), parsed.path.lower()
    if (host == "videodelivery.net" or host.endswith(".videodelivery.net")
            or host.endswith(".cloudflarestream.com")):
        return "cloudflare-stream"
    if path.endswith(VIDEO_SUFFIXES):
        return "direct-mp4"
    if host == "vimeo.com" or host.endswith(".vimeo.com"):
        return "vimeo"
    return "other"


def _credit_size(credits: object, keys: tuple[str, ...]) -> str | None:
    if not isinstance(credits, dict):
        return None
    values = (as_text(credits.get(key)) for key in keys)
    return next((value for value in values if value), None)


def parse_project_node(node: object) -> dict[str, Any]:
    """Map one GraphQL ``allProjects.data`` node to the catalog project schema."""
    if not isinstance(node, dict):
        raise ValueError("catalog project node must be an object")
    project_id = as_int(node.get("id"))
    if project_id is None:
        raise ValueError("catalog project node has no numeric id")
    slug, video_url = as_text(node.get("slug")) or "", as_text(node.get("video"))
    provider = classify_provider(video_url)
    credits, profile = node.get("credits"), node.get("profile")
    studio = as_text(profile.get("company")) if isinstance(profile, dict) else None
    studio = studio or _credit_size(credits, ("studio", "company", "company_name"))
    if studio is None and isinstance(credits, str):
        studio = as_text(credits)
    awards = [{"type": str(award["type"]), "date": as_text(award.get("date"))}
              for award in node.get("awards") or ()
              if isinstance(award, dict) and as_text(award.get("type"))]
    tags = [str(tag["title"]) for tag in (node.get("tags") or ())
            if isinstance(tag, dict) and as_text(tag.get("title"))]
    thumbnail = node.get("thumbnail")
    poster_url = (as_text(thumbnail.get("original"))
                  if isinstance(thumbnail, dict) else None)
    return {
        "projectId": str(project_id), "slug": slug, "provider": provider,
        "projectUrl": PROJECT_URL.format(
            project_id=project_id, slug=quote(slug, safe="-._~")),
        "title": as_text(node.get("title")) or "", "videoUrl": video_url,
        "posterUrl": poster_url, "category": as_text(node.get("category")),
        "scores": {key: finite_float(node.get(f"wa_{key}")) for key in
                   ("overall", "concept", "design", "motion", "sound")},
        "totalVotes": as_int(node.get("total_votes")) or 0, "awards": awards,
        "tags": tags, "studio": studio,
        "teamSize": _credit_size(credits, ("teamSize", "team_size", "team")),
        "budgetSize": _credit_size(credits, ("budgetSize", "budget_size", "budget")),
        "createdAt": as_text(node.get("created_at")),
        "votingClosedAt": as_text(node.get("voting_closed_at")),
        "projectWebsite": as_text(node.get("project_website")),
        "downloadable": provider in SUPPORTED_PROVIDERS and bool(video_url)}


def _post_graphql(
    query: str, variables: dict[str, Any], *, endpoint: str = ENDPOINT,
    timeout: float = 45.0, retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """POST one GraphQL request with bounded retries on transport/5xx responses."""
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(retries):
        request = Request(endpoint, data=body, method="POST", headers={
            "Accept": "application/json", "Content-Type": "application/json",
            "User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise ValueError(
                    f"catalog endpoint rejected the request (HTTP {error.code})") from None
            last_error = error
        except (URLError, TimeoutError, OSError) as error:
            last_error = error
        else:
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise ValueError("catalog response exceeded the expected size limit")
            try:
                payload = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise ValueError("catalog response was not valid JSON") from None
            if not isinstance(payload, dict) or payload.get("errors"):
                raise ValueError("catalog response was not a usable JSON object")
            return payload
        if attempt + 1 < retries:
            sleep(2 ** attempt)
    raise RuntimeError("catalog request failed after bounded retries") from last_error


def fetch_all_projects(
    *, post: Callable[[str, dict[str, Any]], dict[str, Any]] = _post_graphql,
    page_size: int = 100, log: Callable[[str], None] = print,
) -> tuple[list[dict[str, Any]], int | None]:
    """Fetch every ``allProjects`` page until the paginator reports no more pages."""
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ValueError("catalog page size must be between 1 and 100")
    projects: list[dict[str, Any]] = []
    total: int | None = None
    page = 1
    while page <= _MAX_PAGES:
        payload = post(CATALOG_QUERY, {"first": page_size, "page": page})
        block = (payload.get("data") or {}).get("allProjects") if isinstance(
            payload, dict) else None
        if not isinstance(block, dict):
            raise ValueError("catalog response has no allProjects block")
        data, info = block.get("data"), block.get("paginatorInfo")
        if not isinstance(data, list) or not isinstance(info, dict):
            raise ValueError("catalog allProjects block has no data/paginatorInfo")
        projects.extend(parse_project_node(node) for node in data)
        reported_total = as_int(info.get("total"))
        total = reported_total if reported_total is not None else total
        log(f"catalog page {page}: {len(data)} projects (total so far {len(projects)})")
        if info.get("hasMorePages") is not True:
            return projects, total
        if not data:
            raise ValueError("catalog paginator promised more pages but returned none")
        page += 1
    raise ValueError("catalog pagination exceeded the safety page budget")


def build_catalog(
    projects: Iterable[dict[str, Any]], total: int | None, *,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    rows = list(projects)
    counts = {provider: 0 for provider in ("vimeo", "cloudflare-stream",
                                          "direct-mp4", "other")}
    for project in rows:
        provider = project.get("provider")
        counts[str(provider if provider in counts else "other")] += 1
    return {"schemaVersion": CATALOG_SCHEMA, "retrievedAt": retrieved_at or utc_now(),
            "endpoint": ENDPOINT,
            "totalProjects": total if total is not None else len(rows),
            "providerCounts": {key: value for key, value in counts.items() if value},
            "projects": rows}


def _load_catalog(path: Path) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or catalog.get("schemaVersion") != CATALOG_SCHEMA:
        raise ValueError("unsupported catalog schema")
    if not isinstance(catalog.get("projects"), list):
        raise ValueError("catalog has no project list")
    return catalog


def selection_key(project: dict[str, Any], order: str) -> tuple[Any, ...]:
    text = str(project.get("projectId") or "")
    project_id = int(text) if text.isdigit() else -1
    scores = project.get("scores") if isinstance(project.get("scores"), dict) else {}
    score = finite_float(scores.get("overall"))
    if order == "best":
        return (score is not None, score or 0.0, project_id)
    if order == "latest":
        created = project.get("createdAt")
        return (created is not None, str(created or ""), project_id)
    if order == "awards-first":
        awards = project.get("awards")
        awarded = isinstance(awards, list) and any(
            isinstance(award, dict) and award.get("type") in AWARD_TYPES
            for award in awards)
        return (awarded, score is not None, score or 0.0, project_id)
    raise ValueError("unknown selection order")


def select_projects(
    projects: Iterable[dict[str, Any]], *, order: str = "best",
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (eligible chosen, unsupported skip rows), deterministically ordered.

    Supported providers enter the work list; Vimeo entries are carried here only
    so their explicit ``unsupported-vimeo`` skip reason is recorded in the index.
    They are never attempted. ``limit`` counts eligible projects, not skips; it
    may be ``0`` to select nothing (an offline smoke run).
    """
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a non-negative integer")
    if limit == 0:
        return [], []
    candidates = [project for project in projects if project.get("downloadable") is True
                  or (project.get("provider") == "vimeo" and project.get("videoUrl"))]
    ranked = sorted(candidates, key=lambda p: selection_key(p, order), reverse=True)
    chosen: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []
    for project in ranked:
        provider = project.get("provider")
        if provider in SUPPORTED_PROVIDERS:
            chosen.append(project)
        else:
            skips.append(_skip_row(project, "unsupported-vimeo" if provider == "vimeo"
                                   else f"unsupported-provider-{provider}"))
        if limit is not None and len(chosen) >= limit:
            break
    return chosen, skips


_policy_video_url = partial(allowlisted_video_url, allowed_hosts=VIDEO_HOSTS)
_policy_image_url = partial(allowlisted_image_url, allowed_hosts=IMAGE_HOSTS)


def resume_matches(record_path: Path, project_id: object) -> bool:
    """A record is complete when it carries the same catalog ``projectId``."""
    return _resume_matches(record_path, project_id, field="projectId")


def _skip_row(project: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"slug": project.get("slug"), "projectId": project.get("projectId"),
            "provider": project.get("provider"), "reason": reason}


def build_video_record(
    project: dict[str, Any], *, source: dict[str, Any],
    coverage: dict[str, Any], windows: list[dict[str, Any]], method: str,
    rights_note: str, generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge MDA subject identity around the package's neutral evidence payload."""
    scores = project.get("scores") if isinstance(project.get("scores"), dict) else {}
    catalog = {"title": project.get("title"), "studio": project.get("studio"),
               "category": project.get("category"), "scores": scores,
               "totalVotes": project.get("totalVotes"),
               "awards": project.get("awards") or [], "tags": project.get("tags") or [],
               "createdAt": project.get("createdAt"),
               "votingClosedAt": project.get("votingClosedAt"),
               "projectWebsite": project.get("projectWebsite")}
    evidence = build_video_evidence(
        source=source, coverage=coverage, windows=windows, method=method,
        provider=str(project.get("provider")), video_url=project.get("videoUrl"),
        rights_basis=RIGHTS_BASIS, rights_note=rights_note,
        schema_version=VIDEO_SCHEMA, evidence_status=EVIDENCE_STATUS,
        limits=LIMITS, generated_at=generated_at, rights_status=RIGHTS_STATUS)
    return {"schemaVersion": VIDEO_SCHEMA,
            "projectId": str(project.get("projectId")), "slug": project.get("slug"),
            "projectUrl": project.get("projectUrl"), "catalog": catalog, **evidence}


def build_still_record(
    project: dict[str, Any], *, still: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge MDA subject identity around the package's neutral still payload."""
    evidence = build_still_evidence(
        still=still, schema_version=STILL_SCHEMA,
        evidence_status=STILL_EVIDENCE_STATUS, limits=STILL_LIMITS,
        coverage_note=STILL_COVERAGE_NOTE, generated_at=generated_at)
    scores = project.get("scores") if isinstance(project.get("scores"), dict) else {}
    return {"schemaVersion": STILL_SCHEMA,
            "projectId": str(project.get("projectId")), "slug": project.get("slug"),
            "projectUrl": project.get("projectUrl"),
            "provider": project.get("provider"), "title": project.get("title"),
            "studio": project.get("studio"), "category": project.get("category"),
            "awards": project.get("awards") or [],
            "overallScore": finite_float(scores.get("overall")), **evidence}


def _video_summary_row(record: dict[str, Any]) -> dict[str, Any]:
    summary, source = record.get("summary") or {}, record.get("source") or {}
    catalog = record.get("catalog") or {}
    scores = catalog.get("scores") if isinstance(catalog.get("scores"), dict) else {}
    return {
        "slug": record.get("slug"), "projectId": record.get("projectId"),
        "title": catalog.get("title"), "studio": catalog.get("studio"),
        "provider": (record.get("acquisition") or {}).get("provider"),
        "category": catalog.get("category"), "overall": scores.get("overall"),
        "awards": catalog.get("awards") or [],
        "durationSeconds": source.get("durationSeconds"),
        "resolution": source.get("resolution"), "sourceSha256": source.get("mediaSha256"),
        "windowCount": (record.get("coverage") or {}).get("windowsMeasured"),
        "meanCutCandidateRate": summary.get("cutCandidateRatePerMinute"),
        "meanLuma": summary.get("meanDisplayLuma"),
        "meanSaturation": summary.get("meanSaturation"),
        "recordPath": (Path("videos") / f"{safe_slug(record.get('slug'))}.json").as_posix()}


def _still_summary_row(record: dict[str, Any], record_path: Path) -> dict[str, Any]:
    still = record.get("still") or {}
    metrics = still.get("metrics") or {}
    return {
        "slug": record.get("slug"), "projectId": record.get("projectId"),
        "title": record.get("title"), "provider": record.get("provider"),
        "studio": record.get("studio"), "category": record.get("category"),
        "overall": record.get("overallScore"), "awards": record.get("awards") or [],
        "imageUrl": still.get("imageUrl"), "imageSha256": still.get("imageSha256"),
        "imageBytes": still.get("imageBytes"), "imageWidth": still.get("imageWidth"),
        "imageHeight": still.get("imageHeight"),
        "meanDisplayLumaProxy": metrics.get("meanDisplayLumaProxy"),
        "dominantHueFamily": metrics.get("dominantHueFamily"),
        "edgeDensityProxy": metrics.get("edgeDensityProxy"),
        "recordPath": record_path.as_posix()}


def _detail(record: dict[str, Any], *, still: bool) -> str:
    """One progress-line detail string: still metrics or video sample numbers."""
    if still:
        item = record.get("still") or {}
        metrics = item.get("metrics") or {}
        return (f"{item.get('imageWidth')}x{item.get('imageHeight')} "
                f"luma={metrics.get('meanDisplayLumaProxy')} "
                f"hue={metrics.get('dominantHueFamily')}")
    source, summary = record.get("source") or {}, record.get("summary") or {}
    width, height = source.get("resolution") or (0, 0)
    return (f"{width}x{height} {source.get('durationSeconds', 0):.1f}s "
            f"{(source.get('sizeBytes') or 0) / (1024 * 1024):.1f}MB "
            f"cuts={summary.get('cutCandidates', 0)}")


def _run_lane(
    items: Iterable[dict[str, Any]], *, out_dir: Path, folder: str,
    index_name: str, schema: str, catalog_sha: str,
    run_one: Callable[[dict[str, Any]], dict[str, Any]],
    summary_row: Callable[[dict[str, Any]], dict[str, Any]],
    detail: Callable[[dict[str, Any]], str], label: str, final_note: str,
    initial_skips: Iterable[dict[str, Any]] = (),
    retained: list[dict[str, Any]] | None = None, progress_total: int | None = None,
    resume: bool = True, jobs: int = 1, delay_seconds: float = 0.0,
    log: Callable[[str], None] = print,
) -> int:
    """Run one lane: resume predicate, atomic index, progress, outcome counts."""
    if type(jobs) is not int or not 1 <= jobs <= 3:
        raise ValueError("jobs must be between 1 and 3")
    if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
        raise ValueError("delay_seconds must be a non-negative number")
    retained = retained or []
    (out_dir / folder).mkdir(parents=True, exist_ok=True)
    index_path, details = out_dir / index_name, {}

    def tracked(project: dict[str, Any]) -> dict[str, Any]:
        record = run_one(project)
        details[str(project.get("slug"))] = detail(record)
        return record

    def index_for(records: list[dict[str, Any]], skips: list[dict[str, Any]],
                  failures: list[dict[str, Any]]) -> dict[str, Any]:
        return build_index(schema_version=schema, records=[*retained, *records],
                           skips=skips, failures=failures, generated_at=utc_now(),
                           extra={"catalogSha256": catalog_sha})

    def skip_reason(project: dict[str, Any]) -> str | None:
        try:
            slug = safe_slug(project.get("slug"))
        except ValueError as error:
            return f"unsafe-slug: {error}"
        if not resume:
            return None
        record_path = out_dir / folder / f"{slug}.json"
        return ("resume-existing-record" if resume_matches(
            record_path, project.get("projectId")) else None)

    def report(position: int, total: int, status: str, label_text: str,
               text: str) -> None:
        print(f"[{position}/{progress_total or total}] {status} {label_text} "
              f"{text or details.pop(label_text, '')}", flush=True)

    outcome = run_batch(
        items, run_one=tracked, index_path=index_path, build_index=index_for,
        summary_row=summary_row, skip_row=_skip_row,
        describe=lambda project: str(project.get("slug")),
        skip_reason=skip_reason, initial_skips=initial_skips,
        error_text=lambda error: re.sub(
            r"/[^\s:'\"]*kumiki-mda-[^\s:'\"]*", "[scratch]",
            safe_error(error, redact=(str(out_dir),))),
        progress=report, jobs=jobs, delay_seconds=delay_seconds)
    log(f"{label}={len(retained) + outcome.measured} skipped={outcome.skipped} "
        f"failed={outcome.failed} attempted={outcome.attempted} "
        f"elapsed={outcome.elapsed_seconds:.1f}s index={index_path}")
    log(final_note)
    return 1 if outcome.attempted and not (retained or outcome.measured) else 0


def collect_one(
    project: dict[str, Any], out_dir: Path, *, windows: int = 4,
    window_seconds: int = 10, max_duration_seconds: float = 600.0,
    max_file_bytes: int = 400 * 1024 * 1024, image_translation: bool = False,
    rights_note: str = DEFAULT_RIGHTS_NOTE, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe", download_timeout: float = 360.0,
) -> dict[str, Any]:
    """Download -> validate -> measure -> write record -> always delete media."""
    if (type(windows) is not int or not 1 <= windows <= MAX_WINDOWS
            or type(window_seconds) is not int
            or not 1 <= window_seconds <= MAX_WINDOW_SECONDS):
        raise ValueError("window budgets are out of bounds")
    if (not finite_float(max_duration_seconds) or max_duration_seconds <= 0
            or type(max_file_bytes) is not int or max_file_bytes <= 0
            or type(image_translation) is not bool):
        raise ValueError("collection budgets are out of bounds")
    if not isinstance(rights_note, str) or not rights_note.strip():
        raise ValueError("rights note must be non-empty")
    slug, url = safe_slug(project.get("slug")), _policy_video_url(project.get("videoUrl"))
    provider = project.get("provider")
    delivery = PROVIDER_DELIVERY.get(provider) if isinstance(provider, str) else None
    if delivery is None:
        raise ValueError("provider is not downloadable by design")
    record_path = out_dir / "videos" / f"{slug}.json"
    scratch = Path(tempfile.mkdtemp(prefix="kumiki-mda-"))
    try:
        media_dir = scratch / "media"
        media_dir.mkdir()
        path, method = download_media(
            url, delivery, media_dir, allowed_hosts=VIDEO_HOSTS,
            max_bytes=max_file_bytes, ffmpeg=ffmpeg, ffprobe=ffprobe,
            timeout=download_timeout, max_duration_seconds=max_duration_seconds)
        source = source_metadata(path, ffprobe=ffprobe)
        if source["durationSeconds"] > max_duration_seconds:
            raise ValueError("source exceeds the bounded duration budget")
        coverage, measured = measure_windows(
            path, duration_seconds=source["durationSeconds"],
            window_count=windows, window_seconds=window_seconds,
            image_translation=image_translation, ffmpeg=ffmpeg, ffprobe=ffprobe)
        record = build_video_record(
            project, source=source, coverage=coverage, windows=measured,
            method=method, rights_note=rights_note)
        write_json_atomic(record_path, record)
        return record
    finally:
        # Hard guarantee: no media, frames, thumbnails, or audio survive the job.
        shutil.rmtree(scratch, ignore_errors=True)


def collect_still_one(
    project: dict[str, Any], out_dir: Path, *, max_bytes: int = STILL_MAX_BYTES,
    download_timeout: float = 60.0, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Download -> probe -> decode -> measure -> write record; retain no image."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("still image byte cap must be positive")
    if not finite_float(download_timeout) or download_timeout <= 0:
        raise ValueError("still image timeout must be positive")
    slug, url = safe_slug(project.get("slug")), _policy_image_url(project.get("posterUrl"))
    record_path = out_dir / "stills" / f"{slug}.json"
    with tempfile.TemporaryDirectory(prefix="kumiki-mda-still-") as directory:
        target = image_target(Path(directory), url)
        try:
            download_http(
                url, target, allowed_hosts=IMAGE_HOSTS, max_bytes=max_bytes,
                timeout=download_timeout, accept="image/*", label="still image")
            image_bytes = target.stat().st_size
            digest = sha256_file(target)
            measured = measure_still(target, ffmpeg=ffmpeg, ffprobe=ffprobe)
        finally:
            # Guarantee: even a failed decode/measurement leaves no image bytes.
            target.unlink(missing_ok=True)
    record = build_still_record(project, still={
        "imageUrl": url, "imageSha256": digest,
        "imageFormat": still_image_format(url, measured.pop("imageCodec", None)),
        "imageBytes": image_bytes, **measured})
    write_json_atomic(record_path, record)
    return record


def run_collect(
    catalog_path: Path, *, out_dir: Path, limit: int | None = None,
    order: str = "best", resume: bool = True, jobs: int = 1,
    acknowledge_rights: bool = False, delay_seconds: float = 1.5,
    log: Callable[[str], None] = print, **video_options: Any,
) -> int:
    if acknowledge_rights is not True:
        raise ValueError(
            "explicit --acknowledge-rights attestation is required: public "
            "availability is not a license, and each downloaded file is "
            "deleted after numeric measurement")
    catalog_sha = sha256_file(Path(catalog_path))
    projects = _load_catalog(Path(catalog_path))["projects"]
    out_dir = Path(out_dir)
    chosen, unsupported = select_projects(projects, order=order, limit=limit)
    return _run_lane(
        chosen, out_dir=out_dir, folder="videos", index_name="index.json",
        schema=INDEX_SCHEMA, catalog_sha=catalog_sha,
        run_one=lambda project: collect_one(project, out_dir, **video_options),
        summary_row=_video_summary_row, detail=partial(_detail, still=False),
        label="measured", final_note="all downloaded media was deleted; "
                                     "only numeric evidence and metadata remain",
        initial_skips=unsupported, resume=resume, jobs=jobs,
        delay_seconds=delay_seconds, log=log)


def run_stills(
    catalog_path: Path, *, out_dir: Path, limit: int | None = None,
    resume: bool = True, jobs: int = 1, delay_seconds: float = 1.0,
    log: Callable[[str], None] = print, **still_options: Any,
) -> int:
    """Measure one published poster still per project; never fetch video."""
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError("limit must be a non-negative integer")
    catalog_sha = sha256_file(Path(catalog_path))
    projects = _load_catalog(Path(catalog_path))["projects"]
    out_dir = Path(out_dir)
    eligible = [project for project in projects
                if isinstance(project.get("posterUrl"), str)
                and project["posterUrl"].strip()]
    if limit is not None:
        eligible = eligible[:limit]
    retained: list[dict[str, Any]] = []
    if resume:
        for existing in sorted((out_dir / "stills").glob("*.json")):
            try:
                payload = json.loads(existing.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(payload, dict) and payload.get("schemaVersion") == STILL_SCHEMA:
                retained.append(_still_summary_row(
                    payload, existing.relative_to(out_dir)))
    return _run_lane(
        eligible, out_dir=out_dir, folder="stills",
        index_name="stills-index.json", schema=STILLS_INDEX_SCHEMA,
        catalog_sha=catalog_sha,
        run_one=lambda project: collect_still_one(project, out_dir, **still_options),
        summary_row=lambda record: _still_summary_row(
            record, Path("stills") / f"{safe_slug(record.get('slug'))}.json"),
        detail=partial(_detail, still=True), label="still-measured",
        final_note="all downloaded still images were deleted; "
                   "only hashes and numbers remain",
        retained=retained, progress_total=len(eligible), resume=resume,
        jobs=jobs, delay_seconds=delay_seconds, log=log)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ephemeral Motion Design Awards video research collector")
    sub = parser.add_subparsers(dest="command", required=True)
    catalog = sub.add_parser("catalog", help="fetch and classify the full project catalog")
    catalog.add_argument("--out", type=Path, required=True,
                         help="path for the versioned catalog JSON")
    collect = sub.add_parser("collect", help="download, measure, and delete public videos")
    collect.add_argument("--catalog", type=Path, required=True)
    collect.add_argument("--out-dir", type=Path, required=True)
    collect.add_argument("--limit", type=int, default=None)
    collect.add_argument("--order", choices=("best", "latest", "awards-first"),
                         default="best")
    collect.add_argument("--windows", type=int, default=4)
    collect.add_argument("--window-seconds", type=int, default=10)
    collect.add_argument("--max-duration-seconds", type=float, default=600.0)
    collect.add_argument("--max-file-bytes", type=int, default=400 * 1024 * 1024)
    collect.add_argument("--image-translation",
                         action=argparse.BooleanOptionalAction, default=False)
    collect.add_argument("--acknowledge-rights", action="store_true")
    collect.add_argument("--rights-note", default=DEFAULT_RIGHTS_NOTE)
    group = collect.add_mutually_exclusive_group()
    group.add_argument("--resume", dest="resume", action="store_true", default=True)
    group.add_argument("--refresh", dest="resume", action="store_false")
    collect.add_argument("--jobs", type=int, default=1)
    collect.add_argument("--delay-seconds", type=float, default=1.5,
                         help="politeness pause (plus equal jitter) between videos")
    collect.add_argument("--ffmpeg", default="ffmpeg")
    collect.add_argument("--ffprobe", default="ffprobe")
    stills = sub.add_parser(
        "stills", help="measure one hosted poster still per catalog project")
    stills.add_argument("--catalog", type=Path, required=True)
    stills.add_argument("--out-dir", type=Path, required=True)
    stills.add_argument("--limit", type=int, default=None)
    still_group = stills.add_mutually_exclusive_group()
    still_group.add_argument("--resume", dest="resume", action="store_true",
                             default=True)
    still_group.add_argument("--refresh", dest="resume", action="store_false")
    stills.add_argument("--delay-seconds", type=float, default=1.0,
                        help="politeness pause (plus equal jitter) between stills")
    stills.add_argument("--jobs", type=int, default=1)
    stills.add_argument("--max-image-bytes", type=int, default=STILL_MAX_BYTES)
    stills.add_argument("--ffmpeg", default="ffmpeg")
    stills.add_argument("--ffprobe", default="ffprobe")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            projects, total = fetch_all_projects()
            catalog = build_catalog(projects, total)
            write_json_atomic(args.out, catalog)
            print(f"catalog: {catalog['totalProjects']} projects -> {args.out}",
                  flush=True)
            return 0
        if args.command == "stills":
            return run_stills(
                args.catalog, out_dir=args.out_dir, limit=args.limit,
                resume=args.resume, jobs=args.jobs,
                delay_seconds=args.delay_seconds, max_bytes=args.max_image_bytes,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
        if not args.acknowledge_rights:
            parser.error(
                "--acknowledge-rights is required: public availability is not a "
                "license and downloaded media is deleted after measurement")
        return run_collect(
            args.catalog, out_dir=args.out_dir, limit=args.limit,
            order=args.order, resume=args.resume, jobs=args.jobs,
            acknowledge_rights=args.acknowledge_rights,
            delay_seconds=args.delay_seconds, windows=args.windows,
            window_seconds=args.window_seconds,
            max_duration_seconds=args.max_duration_seconds,
            max_file_bytes=args.max_file_bytes,
            image_translation=args.image_translation,
            rights_note=args.rights_note, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    except ValueError as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    sys.exit(main())
