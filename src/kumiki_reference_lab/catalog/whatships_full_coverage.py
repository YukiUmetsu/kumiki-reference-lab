"""Exhaustive What Ships *catalog* discovery, versioned refresh and backlog ledger.

One explicitly requested GET of the public read-only search index; no page
crawling, downloads, X API, playback stream access, or model inference.
Metadata presence must never be confused with reviewing the video itself.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from kumiki_reference_lab.catalog.video_sources import (
    WHATSHIPS_SCHEMA, _CATEGORIES, _SLUG, _from_whatships, _load_snapshot,
    _unique_keys,
)
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged

INDEX_URL = "https://whatships.com/search-index.json"
_CATEGORIES_BY_ID = {value: key for key, value in _CATEGORIES.items()}
_MAX_BYTES = 8 * 1024 * 1024
_MAX_ROWS = 16000
_MANIFEST_VERSION = "kumiki.whatships-comprehensive-coverage.v1"
_BACKLOG_VERSION = "kumiki.whatships-all-video-backlog.v1"
_ALLOWED_KINDS = frozenset({"video", "tool", "studio"})
_POSTER = re.compile(r"/posters/[a-z0-9-]+-960\.webp\Z")


class _RefuseRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("What Ships index redirected away from its documented endpoint")


def _parse_json_bytes(payload: bytes) -> Any:
    if len(payload) > _MAX_BYTES:
        raise ValueError("What Ships index exceeds the 8 MiB metadata budget")
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError("non-finite JSON metadata")),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("What Ships index must contain valid UTF-8 JSON") from exc


def fetch_public_whatships_index(*, timeout: int = 25) -> list[dict[str, Any]]:
    """Fetch precisely one documented read-only JSON endpoint, without redirects."""
    if type(timeout) is not int or not 5 <= timeout <= 60:
        raise ValueError("index timeout must be 5–60 seconds")
    opener = build_opener(ProxyHandler({}), _RefuseRedirects())
    request = Request(
        INDEX_URL, method="GET", headers={
            "Accept": "application/json",
            "User-Agent": "KumikiReferenceLab/0.1 catalog-metadata-audit",
        },
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError("What Ships public index did not return HTTP 200")
            if "json" not in response.headers.get("Content-Type", ""):
                raise ValueError("What Ships public index was not served as JSON")
            payload = response.read(_MAX_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise ValueError("Could not access What Ships official public index") from exc
    raw = _parse_json_bytes(payload)
    validate_raw_whatships_index(raw)
    return raw


def validate_raw_whatships_index(raw: Any) -> list[dict[str, Any]]:
    """Validate all records, including tools/studios, before filtering to videos."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= _MAX_ROWS:
        raise ValueError("What Ships search index must contain 1–16000 records")
    seen_slugs: set[str] = set()
    seen_ids: set[str] = set()
    videos: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or set(item) != {
                "id", "kind", "name", "slug", "href",
                "meta", "poster", "searchText"}:
            raise ValueError(f"index row {i}: unsupported or missing index fields")
        kind, slug, identity = item["kind"], item["slug"], item["id"]
        if kind not in _ALLOWED_KINDS:
            raise ValueError(f"index row {i}: unknown catalog entry kind")
        if (type(identity) is not str or len(identity) > 150 or
                not identity.strip() or identity in seen_ids):
            raise ValueError(f"index row {i}: duplicate/malformed catalog ID")
        seen_ids.add(identity)
        if not all(type(item[key]) is str and 0 < len(item[key]) <= limit
                   for key, limit in (("name", 500), ("slug", 180),
                                      ("href", 260), ("meta", 300),
                                      ("searchText", 4000))):
            raise ValueError(f"index row {i}: malformed/bounded metadata")
        if item["poster"] is not None and (type(item["poster"]) is not str or
                len(item["poster"]) > 260):
            raise ValueError(f"index row {i}: invalid poster path")
        if kind != "video":
            continue
        if (not _SLUG.fullmatch(slug) or slug in seen_slugs or
                item["href"] != f"/videos/{slug}/" or
                not identity.startswith("plv-") or
                not _POSTER.fullmatch(item["poster"] or "")):
            raise ValueError(f"index row {i}: invalid or duplicate video source URL/slug")
        if " · " not in item["meta"]:
            raise ValueError(f"index row {i}: missing category")
        creator, category = item["meta"].rsplit(" · ", 1)
        if not creator.strip() or category not in _CATEGORIES:
            raise ValueError(f"index row {i}: unsupported video category")
        seen_slugs.add(slug)
        videos.append(item)
    if not videos:
        raise ValueError("What Ships index contained no published videos")
    return videos


def reconcile_index(
    raw: list[dict[str, Any]], previous: dict[str, Any], *,
    retrieved_on: str,
    min_retained_fraction: float = 0.90,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Update every indexed video and keep compatible historical detail by slug.

    A sudden site index collapse is considered a failed refresh, never silently
    published as a credible all-video corpus.
    """
    indexed = validate_raw_whatships_index(raw)
    if (type(min_retained_fraction) not in (float, int) or
            not 0 < min_retained_fraction <= 1):
        raise ValueError("retained fraction must be in (0,1]")
    try:
        datetime.strptime(retrieved_on, "%Y-%m-%d")
    except (TypeError, ValueError):
        raise ValueError("retrieved date must be YYYY-MM-DD") from None
    if previous.get("schemaVersion") != WHATSHIPS_SCHEMA:
        raise ValueError("previous snapshot schema invalid")
    # The adapter performs strict previous-snapshot provenance validation.
    _from_whatships(previous)
    previous_by_slug = {v["slug"]: v for v in previous["videos"]}
    previous_slugs, current_slugs = set(previous_by_slug), {v["slug"] for v in indexed}
    kept_count = len(previous_slugs & current_slugs)
    if len(previous_slugs) and kept_count/len(previous_slugs) < min_retained_fraction:
        raise ValueError("What Ships index dropped too many previous videos; refusing unsafe partial refresh")
    additions = sorted(current_slugs - previous_slugs)
    removals = sorted(previous_slugs - current_slugs)
    changed = []
    retained_detail = 0
    old_detail_removed_due_category_change = 0
    videos = []
    for row in indexed:
        slug, title, meta = row["slug"], row["name"], row["meta"]
        old = previous_by_slug.get(slug)
        if old is not None and (
                old["title"] != title or old["indexMetadata"] != meta or
                old.get("posterPath") != row["poster"] or
                old.get("searchText") != row["searchText"]):
            changed.append(slug)
        old_detail = old.get("detail") if old else None
        compatible = bool(
            isinstance(old_detail, dict) and
            old.get("indexMetadata", "").rsplit(" · ", 1)[-1] ==
            meta.rsplit(" · ", 1)[-1]
        )
        if old_detail is not None and not compatible:
            old_detail_removed_due_category_change += 1
        detail = old_detail if compatible else None
        if detail is not None:
            retained_detail += 1
        videos.append({
            "id": row["id"], "slug": slug, "title": title,
            "directoryUrl": INDEX_URL.removesuffix("/search-index.json") +
                            f"/videos/{slug}/",
            "indexMetadata": meta, "posterPath": row["poster"],
            "searchText": row["searchText"], "detail": detail,
        })
    categories = Counter(row["indexMetadata"].rsplit(" · ", 1)[-1] for row in videos)
    total = len(videos)
    snapshot = {
        "schemaVersion": WHATSHIPS_SCHEMA,
        "retrievedOn": retrieved_on,
        "source": {
            "publisher": "What Ships", "indexUrl": INDEX_URL,
            "sourceSpec": "https://whatships.com/openapi.json",
            "citationGuide": "https://whatships.com/llms.txt",
        },
        "methodology": (
            "Complete video-kind export from the single public official search index. "
            "Compatible previously captured detailed records retained by exact slug and category. "
            "Missing detail, media rights, source footage, visual/speech review remain unknown. "
            "No media files were retrieved, decoded, viewed, or redistributed."
        ),
        "totals": {
            "indexed": total, "enriched": retained_detail,
            "withoutDetails": total-retained_detail,
            "byCategory": [
                {"category": category, "count": count}
                for category, count in sorted(categories.items())
            ],
        },
        "videos": videos,
    }
    # Ensure the output is accepted by the existing provider-neutral catalog.
    _from_whatships(snapshot)
    diff = {
        "previousIndexed": len(previous_slugs),
        "currentIndexed": total,
        "retained": kept_count,
        "addedCount": len(additions), "removedCount": len(removals),
        "updatedIndexMetadataCount": len(changed),
        "retainedDetailCount": retained_detail,
        "discardedStaleDetailCount": old_detail_removed_due_category_change,
        "addedSlugs": additions, "removedSlugs": removals,
        "changedIndexSlugs": sorted(changed),
        "warning": (
            "Removed slugs may be delisted or moved. This compares published catalog indexes, "
            "not the existence/availability of the underlying videos."
        ),
    }
    return snapshot, diff


def build_full_coverage(snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Enumerate ALL videos, with explicit gaps instead of fabricated analyses."""
    _from_whatships(snapshot)
    videos = snapshot["videos"]
    by_category: dict[str, dict[str, Any]] = {}
    buckets: dict[str, deque] = {
        category: deque() for category in sorted(_CATEGORIES_BY_ID)
    }
    for row in videos:
        category = _CATEGORIES[row["indexMetadata"].rsplit(" · ", 1)[-1]]
        buckets[category].append(row)
    for category, bucket in buckets.items():
        enriched = sum(row.get("detail") is not None for row in bucket)
        by_category[category] = {
            "indexed": len(bucket), "hasDetailMetadata": enriched,
            "needsDetailMetadata": len(bucket)-enriched,
            "authorizedLocalMediaBound": 0,
            "sourceFrameAnalyzed": 0,
            "humanReviewedWithSourceTimecodes": 0,
        }
    all_entries = []
    # Round-robin, across all eight source categories, avoids starvation by
    # the very large AI category and never excludes lower-view/unknown films.
    while any(buckets.values()):
        for category in sorted(buckets):
            if not buckets[category]:
                continue
            row = buckets[category].popleft()
            slug = row["slug"]
            detail = row.get("detail")
            all_entries.append({
                "id": "whatships:" + slug, "slug": slug,
                "title": row["title"], "category": category,
                "watchUrl": row["directoryUrl"],
                "originalXUrl": detail.get("tweetUrl") if detail else None,
                "indexStatus": "indexed",
                "detailStatus": "detail-snapshot" if detail else "index-only",
                "localAuthorizedMediaStatus": "not-linked",
                "frameAnalysisStatus": "not-recorded",
                "reviewStatus": "not-recorded",
                "nextMetadataTask": "none" if detail else "fetch-read-only-detail",
                "nextVisualTask": "requires-independently-authorized-local-media",
            })
    coverage = {
        "schemaVersion": _MANIFEST_VERSION,
        "retrievedOn": snapshot["retrievedOn"],
        "totalVideoEntries": len(videos),
        "indexedMetadataCoveragePercent": 100.0,
        "detailedMetadataEntries": sum(row.get("detail") is not None for row in videos),
        "detailMissingEntries": sum(row.get("detail") is None for row in videos),
        "authorizedLocalMediaBindingsInThisDataset": 0,
        "frameAnalysisEvidenceInThisDataset": 0,
        "note": (
            "100% means all entries in THIS validated snapshot are enumerated. "
            "It does not mean 100% of the website at a later time, nor that footage "
            "was downloaded, watched, analyzed or approved. External analysis "
            "bindings must be verified separately."
        ),
        "byCategory": by_category,
    }
    backlog = {
        "schemaVersion": _BACKLOG_VERSION,
        "retrievedOn": snapshot["retrievedOn"],
        "strategy": "complete-catalog-category-round-robin",
        "totalTasks": len(all_entries),
        "entries": all_entries,
        "limitations": [
            "Order is a coverage schedule, not creative merit or actual audience ranking.",
            "All entries remain metadata-only until separately sourced rights-appropriate footage is analyzed.",
            "Detailed metadata availability is not evidence that any video frames or audio were reviewed.",
            "X view counts, if present, are historical snapshots, not retention, unique viewers or causal virality.",
        ],
    }
    return coverage, backlog


def _read_bounded_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BYTES:
        raise ValueError("local What Ships input must be a regular JSON file <= 8 MiB")
    return path.read_bytes()


def refresh_full_whatships_catalog(
    previous_path: Path, out: Path, *, index_file: Path | None = None,
    timeout: int = 25, retrieved_on: str | None = None,
) -> Path:
    """Write immutable complete new snapshot, coverage, backlog, and change ledger."""
    if out.exists() or out.is_symlink():
        raise ValueError("What Ships refresh output must be a new directory")
    previous_signature = file_signature(previous_path)
    old = _load_snapshot(previous_path)
    index_signature = file_signature(index_file) if index_file is not None else None
    if index_file is not None:
        raw = _parse_json_bytes(_read_bounded_file(index_file))
    else:
        raw = fetch_public_whatships_index(timeout=timeout)
    snapshot, diff = reconcile_index(
        raw, old, retrieved_on=retrieved_on or datetime.now(timezone.utc).date().isoformat(),
    )
    coverage, backlog = build_full_coverage(snapshot)
    require_unchanged(previous_path, previous_signature)
    if index_signature is not None and index_file is not None:
        require_unchanged(index_file, index_signature)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-whatships-full-", dir=out.parent) as temp:
        staging = Path(temp)
        for filename, value in (
            ("whatships-all-videos.json", snapshot),
            ("coverage.json", coverage),
            ("all-video-backlog.json", backlog),
            ("index-changes.json", diff),
        ):
            (staging / filename).write_text(
                json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        require_unchanged(previous_path, previous_signature)
        if index_signature is not None and index_file is not None:
            require_unchanged(index_file, index_signature)
        if out.exists() or out.is_symlink():
            raise ValueError("What Ships output was occupied before publication")
        os.replace(staging, out)
    return out / "coverage.json"


def summarize_full_snapshot(path: Path) -> dict[str, Any]:
    return build_full_coverage(_load_snapshot(path))[0]


def plan_full_snapshot(path: Path, *, limit: int | None = None,
                       category: str | None = None,
                       missing_detail_only: bool = False) -> dict[str, Any]:
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 10000):
        raise ValueError("requested metadata queue limit must be 1–10000")
    if category is not None and category not in _CATEGORIES_BY_ID:
        raise ValueError("unknown category")
    coverage, backlog = build_full_coverage(_load_snapshot(path))
    selected = [row for row in backlog["entries"]
                if (category is None or row["category"] == category) and
                (not missing_detail_only or row["detailStatus"] == "index-only")]
    return {
        "schemaVersion": _BACKLOG_VERSION,
        "snapshotDate": coverage["retrievedOn"],
        "totalEligible": len(selected),
        "displayedCount": len(selected if limit is None else selected[:limit]),
        "filters": {"category": category, "missingDetailOnly": missing_detail_only},
        "entries": selected if limit is None else selected[:limit],
        "note": "Metadata tasks only; no authorized local media or actual film analysis is implied.",
    }
