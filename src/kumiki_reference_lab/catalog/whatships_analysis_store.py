"""Export source-linked, repeatable What Ships analysis data into a Git repository.

Source video/media paths and private rights notes stay in local run directories.
This code intentionally persists only whitelisted metadata, earlier browser
spot checks and independently checked original-source-PTS numeric observations.
No automatic human-review certification or inferred camera/lighting labels.
"""
from __future__ import annotations

import json
import math
import os
import re
from fractions import Fraction
import tempfile
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.catalog.video_sources import _load_snapshot, _from_whatships
from kumiki_reference_lab.catalog.whatships_data_dashboard import build_whatships_browser
from kumiki_reference_lab.catalog.whatships_media_bindings import _read_json
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged

SCHEMA_VERSION = "kumiki.whatships-repository-analysis.v1"
INDEX_VERSION = "kumiki.whatships-repository-analysis-index.v1"
_BASENAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_MAX_NOTES = 200
_MAX_WINDOWS = 6
_MAX_SAMPLES = 24


def _load_spotchecks(path: Path, valid_ids: set[str]) -> dict[str, dict[str, Any]]:
    doc = _read_json(path)
    if (not isinstance(doc, dict) or
            doc.get("schemaVersion") != "kumiki.browser-video-observations.v1" or
            not isinstance(doc.get("observations"), list) or
            len(doc["observations"]) > _MAX_NOTES):
        raise ValueError("unsupported browser observation source schema")
    result = {}
    for row in doc["observations"]:
        if not isinstance(row, dict) or set(row) != {
                "sourceId", "reviewedOn", "method", "coverage",
                "visualTags", "visibleMoments", "techniqueHypotheses"}:
            raise ValueError("browser spotcheck has unexpected fields")
        sid = row["sourceId"]
        if (type(sid) is not str or sid not in valid_ids or sid in result or
                row["method"] != "browser-player" or
                row["coverage"] != "selected-moments-only"):
            raise ValueError("browser observation must reference one catalog entry with partial coverage")
        if not all(isinstance(row[key], list) and len(row[key]) <= limit
                   for key, limit in (("visualTags",40),("visibleMoments",30),
                                      ("techniqueHypotheses",30))):
            raise ValueError("browser observation arrays are malformed")
        if not all(type(value) is str and 1 <= len(value) <= 1000 for key in
                   ("visualTags","visibleMoments","techniqueHypotheses")
                   for value in row[key]):
            raise ValueError("browser observation text is malformed")
        result[sid] = {
            "observedOn": row["reviewedOn"], "method": "browser-player",
            "coverage": "selected-moments-only",
            "visualTags": row["visualTags"],
            "visibleMoments": row["visibleMoments"],
            "techniqueHypotheses": row["techniqueHypotheses"],
            "sourcePts": None,
            "evidenceStatus": "browser-moments-observed-no-timestamp-or-complete-film-review",
        }
    return result


def _read_verified_visual_data(
    visual_index: Path, expected_sha: dict[str,str],
) -> dict[str,dict[str,Any]]:
    """Whitelist actual PTS frame-level metrics, never local paths or private text."""
    raw = _read_json(visual_index)
    if not isinstance(raw,dict) or not isinstance(raw.get("entries"),list):
        raise ValueError("invalid private visual index")
    output = {}
    for entry in raw["entries"]:
        if entry.get("status") != "measured-numeric-proxies-unreviewed":
            continue
        sid = entry["sourceId"]
        if sid not in expected_sha or entry["mediaSha256"] != expected_sha[sid]:
            raise ValueError("visual evidence is not linked to the expected source media")
        windows = []
        for item in entry["probeArtifacts"]:
            doc = _read_json(Path(item["path"]))
            scan = doc.get("scan")
            summary = doc.get("sampledWindowSummary")
            if (doc.get("schemaVersion") != "kumiki.source-pts-visual-probe.v1" or
                    doc.get("sourceSha256") != expected_sha[sid] or
                    not isinstance(scan,dict) or not isinstance(summary,dict) or
                    scan.get("startSeconds") != item["startSeconds"] or
                    scan.get("sourceWindowEndSeconds") != item["endSeconds"] or
                    scan.get("sampledSourcePtsCount") != item["sampledFrameCount"] or
                    doc.get("evidenceStatus") !=
                    "original-source-pts-sampled-numeric-proxies-not-human-reviewed"):
                raise ValueError("visual report mismatches verified original-PTS source evidence")
            sampled = doc.get("sampledFrames")
            pairs = doc.get("sampledFramePairs")
            cuts = doc.get("cutCandidatePts")
            if (not isinstance(sampled,list) or not 2 <= len(sampled) <= _MAX_SAMPLES
                    or not isinstance(pairs,list) or len(pairs) != len(sampled)-1
                    or not isinstance(cuts,list) or cuts != sorted(set(cuts))
                    or len(cuts) > 10000):
                raise ValueError("visual original-PTS frame timeline is malformed")
            # Whitelist every nested numeric field, not just top-level JSON,
            # because private report files must NEVER leak local paths or notes.
            tb = doc.get("sourceTimebase")
            if (not isinstance(tb,dict) or set(tb) != {"numerator","denominator"} or
                    any(type(tb.get(k)) is not int or tb[k] <= 0
                        for k in ("numerator","denominator"))):
                raise ValueError("visual source timebase invalid")
            timebase = Fraction(tb["numerator"],tb["denominator"])
            def rational(value: Any) -> Fraction:
                if (not isinstance(value,dict) or set(value) != {"numerator","denominator"}
                        or any(type(value.get(k)) is not int for k in
                               ("numerator","denominator"))
                        or value["denominator"] <= 0):
                    raise ValueError("original PTS time rational malformed")
                return Fraction(value["numerator"],value["denominator"])
            def fraction(value: Any, name: str, *, ceiling: float = 1) -> float:
                if (type(value) not in (float,int) or not math.isfinite(value)
                        or not 0 <= value <= ceiling):
                    raise ValueError("unapproved/nonfinite metric: "+name)
                return value
            frame_rows = []
            for frame in sampled:
                if not isinstance(frame,dict) or set(frame) != {
                    "sourcePts","sourceSeconds","appearance"}:
                    raise ValueError("visual frame carries unapproved data")
                pts = frame["sourcePts"]
                if type(pts) is not int or abs(pts) > 2**53 or (
                    frame_rows and pts <= frame_rows[-1]["sourcePts"]):
                    raise ValueError("visual source PTS missing, duplicate or nonmonotonic")
                if rational(frame["sourceSeconds"]) != pts*timebase:
                    raise ValueError("visual frame time does not match original PTS/timebase")
                appearance = frame["appearance"]
                keys = (
                    "meanDisplayLumaProxy","displayLumaStdDev",
                    "meanSaturationProxy","shadowPixelFraction","brightPixelFraction")
                if (not isinstance(appearance,dict) or
                        set(appearance) != set(keys)|{"meanRgb"} or
                        not isinstance(appearance["meanRgb"],list) or
                        len(appearance["meanRgb"]) != 3):
                    raise ValueError("visual frame appearance keys changed")
                meters = {k:fraction(appearance[k],k) for k in keys}
                meters["meanRgb"] = [fraction(v,"meanRgb") for v in appearance["meanRgb"]]
                frame_rows.append({
                    "sourcePts":pts,
                    "sourceSeconds":frame["sourceSeconds"],
                    "appearance":meters,
                })
            pair_rows = []
            for i,pair in enumerate(pairs):
                if (not isinstance(pair,dict) or set(pair) != {
                    "startPts","endPts","sourceDeltaSeconds","status",
                    "meanAbsoluteDisplayRgbDelta",
                    "meanAbsoluteDisplayRgbDeltaPerSecond"} or
                    type(pair["startPts"]) is not int or
                    type(pair["endPts"]) is not int or
                    pair["startPts"] != frame_rows[i]["sourcePts"] or
                    pair["endPts"] != frame_rows[i+1]["sourcePts"] or
                    rational(pair["sourceDeltaSeconds"]) !=
                    (pair["endPts"]-pair["startPts"])*timebase):
                    raise ValueError("frame change not anchored to original source PTS")
                status = pair["status"]
                delta = pair["meanAbsoluteDisplayRgbDelta"]
                rate = pair["meanAbsoluteDisplayRgbDeltaPerSecond"]
                if status == "cut-candidate-between-samples":
                    if delta is not None or rate is not None:
                        raise ValueError("cut-spanning pair must abstain from image motion")
                elif status == "rgb-image-difference-proxy":
                    fraction(delta,"meanAbsoluteDisplayRgbDelta")
                    fraction(rate,"meanAbsoluteDisplayRgbDeltaPerSecond",ceiling=100000)
                else:
                    raise ValueError("unapproved RGB pair interpretation")
                pair_rows.append({k:pair[k] for k in (
                    "startPts","endPts","sourceDeltaSeconds","status",
                    "meanAbsoluteDisplayRgbDelta",
                    "meanAbsoluteDisplayRgbDeltaPerSecond")})
            if (len(cuts) != summary["cutCandidateCountBetweenFirstAndLastSample"] or
                    any(type(p) is not int for p in cuts) or
                    any(p < frame_rows[0]["sourcePts"] or
                        p > frame_rows[-1]["sourcePts"] for p in cuts)):
                raise ValueError("visual cut PTS not anchored to sampled original frames")
            if (summary["withinShotComparedPairs"]+summary["cutSeparatedPairs"]
                    != len(pair_rows)):
                raise ValueError("visual comparisons do not cover sampled-frame pairs")
            windows.append({
                "startSeconds": item["startSeconds"], "endSeconds": item["endSeconds"],
                "scan": {
                    "sourceStreamIndex": doc["sourceStreamIndex"],
                    "sourceTimebase": doc["sourceTimebase"],
                    "sampledSourcePtsCount": scan["sampledSourcePtsCount"],
                    "decoder": scan["decoder"],
                    "cutThreshold": scan["cutThreshold"],
                    "frameWidth": scan["frameWidth"], "frameHeight": scan["frameHeight"],
                },
                "cutCandidatePts": cuts,
                "sampledFrames": frame_rows,
                "sampledFramePairs": pair_rows,
                "sampledWindowSummary": {
                    key:summary[key] for key in (
                        "cutCandidateCountBetweenFirstAndLastSample",
                        "cutCandidateRatePerRequestedMinute",
                        "meanSampledDisplayLumaProxy","meanSampledSaturationProxy",
                        "meanWithinShotDisplayRgbDelta","withinShotComparedPairs",
                        "cutSeparatedPairs")
                },
                "evidenceStatus": "source-PTS-RGB-metrics-unreviewed",
            })
        if len(windows) != entry["windowCount"] or not 1 <= len(windows) <= _MAX_WINDOWS:
            raise ValueError("visual entry missing source windows")
        output[sid] = {
            "sourceSha256": expected_sha[sid],
            "windows": windows,
            "evidenceStatus": "sampled-original-source-pts-metrics-not-expert-reviewed",
        }
    return output


def build_repository_analysis(
    snapshot_path: Path, *, observations_path: Path | None = None,
    bindings_path: Path | None = None, analysis_path: Path | None = None,
    visual_path: Path | None = None,
) -> tuple[dict[str,Any],dict[str,dict[str,Any]]]:
    """Make source-keyed derived records; absent evidence creates NO fake record."""
    dashboard = build_whatships_browser(
        snapshot_path, bindings_path=bindings_path,
        analysis_path=analysis_path, numeric_path=visual_path)
    catalog = {row["sourceId"]:row for row in dashboard["entries"]}
    checks = _load_spotchecks(observations_path,set(catalog)) if observations_path else {}
    source_sha = {}
    if bindings_path is not None:
        # The parent dashboard has verified source identity/analysis chain; this
        # reads only the hash, never exports sensitive absolute paths/notes.
        from kumiki_reference_lab.catalog.whatships_media_bindings import load_media_bindings
        snapshot = _load_snapshot(snapshot_path)
        bindings = load_media_bindings(bindings_path,snapshot,verify_files=False)
        source_sha = {row["sourceId"]:row["mediaSha256"] for row in bindings["bindings"]}
    numeric = (_read_verified_visual_data(visual_path,source_sha)
               if visual_path is not None else {})
    records = {}
    for sid,row in catalog.items():
        spot = checks.get(sid)
        sample = numeric.get(sid)
        if spot is None and sample is None and row["characterStatus"] != "completed-unreviewed":
            continue
        layers = {}
        if spot is not None:
            layers["browserSpotCheck"] = spot
        if sample is not None:
            layers["numericVisual"] = sample
        if row["characterStatus"] == "completed-unreviewed":
            layers["characterStudyStatus"] = {
                "status": "completed-unreviewed-model-proposals",
                "detail": "Raw model scenes remain in private local study artifacts; not imported or human certified.",
            }
        records[sid] = {
            "schemaVersion": SCHEMA_VERSION,
            "sourceId": sid,
            "watchUrl": row["watchUrl"],
            "catalogSnapshotOn": dashboard["retrievedOn"],
            "catalogSnapshotSha256": dashboard["snapshotSha256"],
            "sourceMediaSha256": source_sha.get(sid) if sample else None,
            "coverage": {
                "hasBrowserSpotCheck": spot is not None,
                "hasSampledNumericSourceFrames": sample is not None,
                "hasUnreviewedCharacterJob": row["characterStatus"] == "completed-unreviewed",
                "fullFilmReviewed": False,
            },
            "evidence": layers,
            "limits": [
                "No record should be interpreted as verified full-video coverage.",
                "Observed browser moments lack original PTS unless separately analyzed.",
                "RGB/cut metrics are source-frame numerical proxies, not camera/lighting/style truth.",
                "Model-generated character observations have not been human-reviewed.",
                "No local paths, original media, private notes or source-video frames are included.",
            ],
        }
    index = {
        "schemaVersion": INDEX_VERSION,
        "catalogSnapshotOn": dashboard["retrievedOn"],
        "catalogSnapshotSha256": dashboard["snapshotSha256"],
        "catalogVideoCount": dashboard["totalVideos"],
        "sourceLinkedAnalysisCount": len(records),
        "browserSpotCheckCount": len(checks),
        "sampledNumericVideoCount": len(numeric),
        "unreviewedCharacterJobCount": sum(
            row["characterStatus"] == "completed-unreviewed" for row in catalog.values()),
        "fullFilmReviewedCount": 0,
        "entries": [{
            "sourceId": sid,
            "recordPath": sid.removeprefix("whatships:") + ".json",
            "evidenceKinds": sorted(records[sid]["evidence"]),
        } for sid in sorted(records)],
        "limits": [
            "Only records with actual observational evidence are stored here.",
            "Metadata-only catalog entries stay in research/whatships-index-2026-11-10.json.",
            "Do not equate a model completion or numeric frame sample with expert review.",
        ],
    }
    return index,records


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,
                       indent=2,allow_nan=False)+"\n").encode("utf-8")


def export_repository_analysis(
    snapshot_path: Path, out: Path, *, observations_path: Path | None = None,
    bindings_path: Path | None = None, analysis_path: Path | None = None,
    visual_path: Path | None = None,
) -> Path:
    """Write Git-ready, immutable per-video JSON plus index in a new directory."""
    if out.exists() or out.is_symlink():
        raise ValueError("repository analysis output must be a new directory")
    paths = [p for p in (snapshot_path,observations_path,bindings_path,
                        analysis_path,visual_path) if p is not None]
    signatures = [(p,file_signature(p)) for p in paths]
    index,records = build_repository_analysis(
        snapshot_path, observations_path=observations_path,
        bindings_path=bindings_path, analysis_path=analysis_path,
        visual_path=visual_path)
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-analysis-export-",
                                     dir=out.parent) as directory:
        stage = Path(directory)
        (stage/"index.json").write_bytes(_json_bytes(index))
        for sid, record in records.items():
            slug = sid.removeprefix("whatships:")
            if not _BASENAME.fullmatch(slug):
                raise ValueError("analysis record slug is not a safe filename")
            (stage/(slug+".json")).write_bytes(_json_bytes(record))
        for path,signature in signatures:
            require_unchanged(path,signature)
        if out.exists() or out.is_symlink():
            raise ValueError("analysis export path became occupied before publication")
        os.replace(stage,out)
    return out/"index.json"


def validate_repository_analysis(path: Path, snapshot_path: Path) -> dict[str,Any]:
    """Validate Git-tracked analysis index and source keyed per-video files."""
    if path.is_symlink() or not path.is_dir():
        raise ValueError("analysis repository directory must be regular")
    index = _read_json(path/"index.json")
    snapshot = _load_snapshot(snapshot_path)
    source_ids = {x["id"] for x in _from_whatships(snapshot)}
    if (index.get("schemaVersion") != INDEX_VERSION or
            index.get("catalogSnapshotOn") != snapshot["retrievedOn"] or
            index.get("catalogVideoCount") != len(source_ids) or
            not isinstance(index.get("entries"),list) or
            index.get("sourceLinkedAnalysisCount") != len(index["entries"])):
        raise ValueError("repository analysis index version/count/source mismatch")
    seen = set()
    browser_count = numeric_count = 0
    for item in index["entries"]:
        if (not isinstance(item,dict) or set(item) != {
                "sourceId","recordPath","evidenceKinds"}):
            raise ValueError("analysis index entry must carry exact fields")
        sid = item["sourceId"]
        if (type(sid) is not str or sid not in source_ids or sid in seen or
                item["recordPath"] != sid.removeprefix("whatships:")+".json"):
            raise ValueError("analysis index duplicate, unknown ID, or unsafe path")
        seen.add(sid)
        record = _read_json(path/item["recordPath"])
        if (record.get("schemaVersion") != SCHEMA_VERSION or
                record.get("sourceId") != sid or
                record.get("catalogSnapshotOn") != index["catalogSnapshotOn"] or
                record.get("catalogSnapshotSha256") != index["catalogSnapshotSha256"] or
                not isinstance(record.get("evidence"),dict) or
                sorted(record["evidence"]) != item["evidenceKinds"]):
            raise ValueError("analysis record schema/source provenance mismatch")
        browser_count += "browserSpotCheck" in record["evidence"]
        numeric_count += "numericVisual" in record["evidence"]
        numeric = record["evidence"].get("numericVisual")
        if numeric is not None:
            if (numeric.get("sourceSha256") != record["sourceMediaSha256"] or
                    not isinstance(numeric.get("windows"),list) or
                    not 1 <= len(numeric["windows"]) <= _MAX_WINDOWS):
                raise ValueError("repository numeric source fingerprint/windows malformed")
    if index.get("catalogSnapshotSha256") != sha256_file(snapshot_path):
        raise ValueError("repository catalog snapshot SHA does not match source file")
    if (index.get("browserSpotCheckCount") != browser_count or
            index.get("sampledNumericVideoCount") != numeric_count or
            index.get("fullFilmReviewedCount") != 0):
        raise ValueError("repository index misstates observation coverage")
    # Exporter never writes image/media or absolute file paths.
    permitted = {"index.json"}|{sid.removeprefix("whatships:")+".json" for sid in seen}
    all_json = {x.name for x in path.iterdir() if x.suffix == ".json"}
    if all_json != permitted:
        raise ValueError("analysis repository has unindexed JSON files")
    return {
        "schemaVersion": INDEX_VERSION,
        "indexedCatalogVideos": index["catalogVideoCount"],
        "sourceLinkedAnalysisRecords":len(seen),
        "browserSpotChecks":browser_count,
        "numericSampledVideos":numeric_count,
        "humanReviewedFullVideos":0,
    }
