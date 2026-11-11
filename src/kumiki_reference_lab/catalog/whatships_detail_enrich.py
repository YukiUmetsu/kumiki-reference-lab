"""Resumable, rate-limited What Ships detail metadata enrichment via read-only MCP.

No media, posters, X pages, CDN playback or download links are fetched. A
successful detailed catalog record is still NOT an analyzed video.
"""
from __future__ import annotations

import http.client
import json
import os
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from kumiki_reference_lab.catalog.video_sources import (
    _CATEGORIES, _from_whatships, _iso_timestamp, _load_snapshot,
    _unique_keys, _valid_x_post,
)
from kumiki_reference_lab.catalog.whatships_full_coverage import (
    build_full_coverage, plan_full_snapshot,
)
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged

SCHEMA_VERSION = "kumiki.whatships-detail-enrichment.v1"
_MAX_MCP_RESPONSE = 131072


def _decode_json(data: bytes | str) -> Any:
    try:
        return json.loads(
            data.decode("utf-8") if isinstance(data, bytes) else data,
            object_pairs_hook=_unique_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError("nonfinite What Ships metadata")),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("What Ships read-only MCP returned invalid JSON") from exc


def _extract_mcp_video(raw: Any) -> dict[str, Any]:
    """Accept ordinary MCP structuredContent or JSON text blocks; reject ambiguity."""
    if not isinstance(raw, dict):
        raise ValueError("What Ships MCP response must be an object")
    if "jsonrpc" in raw and raw.get("jsonrpc") != "2.0":
        raise ValueError("invalid MCP JSON-RPC version")
    if raw.get("error") is not None:
        raise ValueError("What Ships MCP returned an error for this catalog slug")
    result = raw.get("result", raw)
    if not isinstance(result, dict) or result.get("isError") is True:
        raise ValueError("What Ships MCP returned no valid video detail")
    data = result.get("structuredContent")
    if data is None:
        content = result.get("content")
        if not isinstance(content, list) or len(content) != 1:
            raise ValueError("MCP video requires exactly one structured/text result")
        block = content[0]
        if not isinstance(block, dict) or block.get("type") != "text":
            raise ValueError("MCP video text content malformed")
        text = block.get("text")
        if type(text) is not str or len(text) > 60000:
            raise ValueError("MCP video detail text exceeds bound")
        data = _decode_json(text)
    if isinstance(data, dict) and set(data) == {"video"}:
        data = data["video"]
    if not isinstance(data, dict):
        raise ValueError("MCP video detail must contain one object")
    return data


def _normalize_detail(slug: str, raw: Any, *, expected_category: str) -> dict[str, Any]:
    """Populate only evidence-supported fields; never invent a views timestamp."""
    video = _extract_mcp_video(raw)
    if type(video.get("slug")) is not str or video["slug"] != slug:
        raise ValueError("MCP detail slug differs from requested public index slug")
    title = video.get("title")
    product = video.get("product")
    company = video.get("company")
    category = video.get("category")
    published = video.get("publishedAt")
    duration = video.get("durationSeconds")
    tags = video.get("tags")
    description = video.get("description")
    tweet_url = video.get("tweetUrl")
    canonical_url = video.get("url")
    if (category != expected_category or
            expected_category not in _CATEGORIES.values()):
        raise ValueError("MCP detail category conflicts with official index")
    if not isinstance(title, str) or not title.strip() or len(title) > 500:
        raise ValueError("MCP detail title invalid")
    if not isinstance(product, str) or len(product) > 500:
        raise ValueError("MCP detail product invalid")
    if not isinstance(company, str) or len(company) > 500:
        raise ValueError("MCP detail company invalid")
    if not _iso_timestamp(published):
        raise ValueError("MCP detail has no verifiable timezone-qualified publication time")
    if type(duration) is not int or not 0 <= duration <= 86400:
        raise ValueError("MCP detail duration invalid")
    if (not isinstance(tags, list) or len(tags) > 50 or
            any(type(tag) is not str or not 1 <= len(tag) <= 100 for tag in tags)):
        raise ValueError("MCP detail tags invalid")
    if not isinstance(description, str) or len(description) > 12000:
        raise ValueError("MCP detail description invalid")
    if not _valid_x_post(tweet_url):
        raise ValueError("MCP detail lacks a safe original X post")
    target = f"https://whatships.com/videos/{slug}/"
    if canonical_url != target:
        raise ValueError("MCP detail canonical page differs from indexed source")
    views = video.get("views")
    captured = video.get("viewsCapturedAt")
    if views is not None and (type(views) is not int or views < 0):
        raise ValueError("MCP detail views invalid")
    if captured is not None and not _iso_timestamp(captured):
        raise ValueError("MCP views snapshot date invalid")
    # No timestamp means we cannot attach an untraceable count to the record.
    if views is not None and captured is None:
        views = None
    return {
        "slug": slug, "title": title,
        "product": product, "company": company,
        "category": category,
        "categoryLabel": next(k for k, v in _CATEGORIES.items() if v == category),
        "publishedAt": published, "durationSeconds": duration,
        "views": views, "viewsCapturedAt": captured,
        "tags": tags, "description": description,
        "url": target, "tweetUrl": tweet_url,
        "authorName": video.get("authorName") if isinstance(video.get("authorName"), str) else "",
        "authorHandle": video.get("authorHandle") if isinstance(video.get("authorHandle"), str) else "",
    }


def _call_mcp_get_video(slug: str, *, timeout: int) -> dict[str, Any]:
    """Exact host, exact read-only method; no redirects, cookies or media URLs."""
    if not 5 <= timeout <= 60:
        raise ValueError("What Ships metadata timeout outside supported range")
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "get_video", "arguments": {"slug": slug}},
    }).encode("utf-8")
    conn = http.client.HTTPSConnection("whatships.com", 443, timeout=timeout)
    try:
        conn.request("POST", "/mcp/", body=payload, headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "KumikiReferenceLab/0.1 read-only-catalog-metadata",
        })
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError(f"What Ships read-only metadata request failed HTTP {response.status}")
        body = response.read(_MAX_MCP_RESPONSE + 1)
        if len(body) > _MAX_MCP_RESPONSE:
            raise ValueError("What Ships MCP metadata response exceeds 128 KiB")
        content_type = response.headers.get("Content-Type", "").lower()
        if "application/json" in content_type:
            return _decode_json(body)
        if "text/event-stream" in content_type:
            messages = []
            for line in body.decode("utf-8").splitlines():
                if line.startswith("data:"):
                    messages.append(line.removeprefix("data:").strip())
            if len(messages) != 1:
                raise ValueError("MCP event stream returned multiple/zero ambiguous data responses")
            return _decode_json(messages[0])
        raise ValueError("What Ships MCP response content type unsupported")
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        raise ValueError("What Ships MCP transport unavailable") from exc
    finally:
        conn.close()


def enrich_whatships_details(
    previous_path: Path, out: Path, *, max_details: int = 25,
    delay_seconds: float = 1.5, timeout: int = 25,
    offline_responses: Path | None = None,
) -> Path:
    """Enrich a bounded batch and atomically retain previous + successful detail.

    Use the resulting new snapshot as --previous on the next invocation.
    Individual failed details remain missing, with their reason in the report.
    """
    if (type(max_details) is not int or not 1 <= max_details <= 100 or
            type(delay_seconds) not in (int, float) or not 1 <= delay_seconds <= 30 or
            type(timeout) is not int or not 5 <= timeout <= 60):
        raise ValueError("enrichment rate/request budgets invalid")
    if out.exists() or out.is_symlink():
        raise ValueError("detail enrichment output must be a new directory")
    source_signature = file_signature(previous_path)
    snapshot = _load_snapshot(previous_path)
    response_signature = (file_signature(offline_responses)
                          if offline_responses is not None else None)
    responses = None
    if offline_responses is not None:
        if (offline_responses.is_symlink() or not offline_responses.is_file() or
                offline_responses.stat().st_size > 2_000_000):
            raise ValueError("offline detail fixtures must be bounded regular JSON")
        responses = _decode_json(offline_responses.read_bytes())
        if not isinstance(responses, dict):
            raise ValueError("offline detail fixtures require a slug-to-response map")

    # The round-robin queue lists only index-only videos, equally considering
    # all categories rather than the fastest-growing AI catalog alone.
    outstanding = plan_full_snapshot(
        previous_path, limit=None, missing_detail_only=True)["entries"]
    todo = outstanding[:max_details]
    by_slug = {row["slug"]: row for row in snapshot["videos"]}
    succeeded, failed = [], []
    for index, entry in enumerate(todo):
        slug = entry["slug"]
        try:
            if responses is not None:
                if slug not in responses:
                    raise ValueError("offline MCP fixture has no record for this slug")
                response = responses[slug]
            else:
                if index:
                    time.sleep(delay_seconds)
                response = _call_mcp_get_video(slug, timeout=timeout)
            detail = _normalize_detail(
                slug, response, expected_category=entry["category"])
            by_slug[slug]["detail"] = detail
            succeeded.append(slug)
        except ValueError as exc:
            failed.append({"slug": slug, "reason": str(exc)[:220]})
            # Repeated network failures should not cause broad request storms.
            if responses is None and (
                    "transport unavailable" in str(exc) or
                    "HTTP 429" in str(exc) or "HTTP 5" in str(exc)):
                break
    enriched = sum(row.get("detail") is not None for row in snapshot["videos"])
    totals = snapshot.get("totals")
    if not isinstance(totals, dict):
        totals = {}
    snapshot["totals"] = {
        "indexed": len(snapshot["videos"]),
        "enriched": enriched,
        "withoutDetails": len(snapshot["videos"])-enriched,
        "byCategory": [
            {"category": cat, "count": sum(
                x["indexMetadata"].endswith(" · "+cat)
                for x in snapshot["videos"])}
            for cat in sorted(_CATEGORIES)
        ],
    }
    snapshot["methodology"] = (
        "Complete previous public index retained; missing detailed metadata was "
        "enriched only from explicitly requested read-only get_video catalog "
        "responses, with slug/category/URL provenance checks. No video was fetched, "
        "played or analyzed. Historical view counts require source capture timestamps."
    )
    _from_whatships(snapshot)
    coverage, _ = build_full_coverage(snapshot)
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSnapshotDate": snapshot["retrievedOn"],
        "inputDetailedRecords": enriched-len(succeeded),
        "attempted": len(succeeded)+len(failed),
        "succeeded": len(succeeded), "failed": len(failed),
        "successfulSlugs": succeeded, "failures": failed,
        "remainingIndexOnly": coverage["detailMissingEntries"],
        "liveNetworkUsed": responses is None,
        "requestedLimit": max_details, "minimumDelaySeconds": delay_seconds,
        "methodLimits": [
            "Read-only metadata enrichment, not footage acquisition or visual analysis.",
            "What Ships may modify its MCP protocol; unavailable/mismatched details remain index-only.",
            "The script makes bounded requests only to the public What Ships catalog.",
            "Operator must respect service availability and creator intellectual-property rights.",
        ],
    }
    require_unchanged(previous_path, source_signature)
    if response_signature is not None and offline_responses is not None:
        require_unchanged(offline_responses, response_signature)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-whatships-details-", dir=out.parent) as folder:
        staging = Path(folder)
        for filename, data in (
            ("whatships-all-videos.json", snapshot),
            ("coverage.json", coverage),
            ("detail-enrichment-report.json", report),
        ):
            (staging/filename).write_text(
                json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)+"\n",
                encoding="utf-8")
        require_unchanged(previous_path, source_signature)
        if response_signature is not None and offline_responses is not None:
            require_unchanged(offline_responses, response_signature)
        if out.exists() or out.is_symlink():
            raise ValueError("detail enrichment output became occupied")
        os.replace(staging, out)
    return out/"detail-enrichment-report.json"
