"""Searchable, provenance-preserving cross-video catalog of cinematic techniques.

Catalog frequencies are counts of analyzed *reference videos*, never audience
views, popularity, virality or independently confirmed animation methods.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import statistics
from pathlib import Path
from typing import Any

from kumiki_reference_lab.pipeline.agent_frame_review import _write_json_atomic

SCHEMA_VERSION = "kumiki.cinematic-technique-catalog.v1"


def build_cinematic_catalog(root: Path, *,
                            max_reports: int = 500,
                            overwrite: bool = False) -> Path:
    if type(max_reports) is not int or not 1 <= max_reports <= 1000:
        raise ValueError("catalog report budget invalid")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("catalog root must be a regular directory")
    destination = root / "cinematic-technique-catalog.json"
    if (destination.exists() or destination.is_symlink()) and not overwrite:
        raise ValueError("catalog exists; pass --overwrite")
    files = sorted(root.glob("*.insights.json"))
    if len(files) > max_reports:
        raise ValueError("insight files exceed catalog report budget")
    grouped: dict[str, list[dict[str, Any]]] = {}
    source_summary = {}
    technique_sources: dict[str, set[str]] = collections.defaultdict(set)
    duration = []
    total_bytes = 0
    for path in files:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8_000_000:
            raise ValueError("unsafe or oversized insights file")
        total_bytes += path.stat().st_size
        if total_bytes > 128 * 1024 * 1024:
            raise ValueError("catalog input exceeds total JSON read budget")
        item = json.loads(path.read_text(encoding="utf-8"))
        if item.get("schemaVersion") != "kumiki.online-cinematic-insights.v1":
            raise ValueError("unexpected insights schema")
        identity = item["source"]["sourceSha256"]
        if (not re.fullmatch(r"[a-f0-9]{64}", identity) or
                not path.name.startswith(item["id"]) or
                len(item["techniqueHypotheses"]) > 500):
            raise ValueError("catalog source identity mismatch")
        if identity in source_summary:
            # Same video accessible from multiple URLs must not inflate the
            # frequency that a technique is observed in distinct references.
            raise ValueError("duplicate source SHA-256; consolidate duplicate analyses")
        source_summary[identity] = {
            "id": item["id"], "reference": item["source"]["numericReferenceFile"],
            "insights": path.name,
            "frameCount": item["source"]["frameCount"],
            "shotCount": item["shotIntelligence"]["shotCount"],
        }
        for shot in item["shotIntelligence"]["shots"]:
            duration.append(shot["durationSecondsEstimate"])
        for cue in item["techniqueHypotheses"]:
            family = cue["techniqueId"]
            technique_sources[family].add(identity)
            grouped.setdefault(family, []).append({
                "sourceSha256": identity, "videoId": item["id"],
                "shotId": cue["shotId"],
                "startFrameIndex": cue["startFrameIndex"],
                "endFrameIndex": cue["endFrameIndex"],
                "sourceCueId": cue["id"],
                "grounding": cue["grounding"],
                "insightsFile": path.name,
                "reviewStatus": cue["reviewStatus"],
            })
    techniques = []
    for technique, references in grouped.items():
        references.sort(key=lambda x: (
            x["videoId"], x["startFrameIndex"], x["shotId"]))
        techniques.append({
            "techniqueId": technique,
            "distinctAnalyzedReferenceCount": len(technique_sources[technique]),
            "candidateOccurrenceCount": len(references),
            "references": references[:250],
            "status": "candidate-observations-not-verified-technique-frequency",
        })
    techniques.sort(key=lambda x: (
        -x["distinctAnalyzedReferenceCount"], x["techniqueId"]))
    doc = {
        "schemaVersion": SCHEMA_VERSION,
        "analyzedVideoCount": len(source_summary),
        "sourceCountBasis": "unique-source-sha256-not-website-url",
        "sources": sorted(source_summary.values(), key=lambda x: x["id"]),
        "techniques": techniques,
        "aggregate": {
            "shotCount": sum(v["shotCount"] for v in source_summary.values()),
            "medianProvisionalShotDurationSeconds": (
                round(statistics.median(duration), 6) if duration else None),
        },
        "limits": [
            "Counts reflect the analyzed corpus, not popularity or actual video view counts.",
            "Every technique occurrence is a candidate needing manual validation.",
            "No copyrighted frames, audio or video are retained in this index.",
        ],
    }
    _write_json_atomic(destination, doc)
    return destination


def search_cinematic_catalog(catalog: Path, *,
                             query: str, max_results: int = 20) -> dict[str, Any]:
    if (catalog.is_symlink() or not catalog.is_file()
            or catalog.stat().st_size > 8_000_000
            or type(query) is not str or not 2 <= len(query.strip()) <= 100
            or type(max_results) is not int or not 1 <= max_results <= 100):
        raise ValueError("invalid catalog search")
    doc = json.loads(catalog.read_text(encoding="utf-8"))
    if doc.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("unrecognized cinematic catalog")
    words = re.findall(r"[a-z0-9]+", query.casefold())
    matches = []
    for entry in doc["techniques"]:
        haystack = entry["techniqueId"].casefold()
        score = sum(word in haystack for word in words)
        if score:
            matches.append((score, entry))
    matches.sort(key=lambda e: (-e[0],
                                -e[1]["distinctAnalyzedReferenceCount"],
                                e[1]["techniqueId"]))
    return {
        "schemaVersion": "kumiki.cinematic-catalog-search.v1",
        "query": query,
        "matchedTechniqueCount": len(matches),
        "techniques": [e for _, e in matches[:max_results]],
        "status": "candidate-research-hits-not-verified-reproduction-guidance",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index and search measured cinematic hypotheses")
    parser.add_argument("action", choices=["build", "search"])
    parser.add_argument("--root", type=Path,
                        default=Path("research/analysis/online-videos"))
    parser.add_argument("--query")
    parser.add_argument("--max-reports", type=int, default=500)
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "build":
            result = {"savedTo": str(build_cinematic_catalog(
                args.root, max_reports=args.max_reports, overwrite=args.overwrite))}
        else:
            if not args.query:
                raise ValueError("search needs --query")
            result = search_cinematic_catalog(
                args.root / "cinematic-technique-catalog.json",
                query=args.query, max_results=args.max_results)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"cinematic catalog failed: {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
