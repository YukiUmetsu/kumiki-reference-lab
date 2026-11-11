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



def _validate_record(record: Any, sid: str, snapshot_sha: str) -> None:
    """Validate strict public JSON whitelist, source PTS and evidence semantics."""
    if (not isinstance(record,dict) or set(record) != {
            "schemaVersion","sourceId","watchUrl","catalogSnapshotOn",
            "catalogSnapshotSha256","sourceMediaSha256","coverage",
            "evidence","limits"} or
            record["schemaVersion"] != SCHEMA_VERSION or
            record["sourceId"] != sid or
            record["catalogSnapshotSha256"] != snapshot_sha or
            record["watchUrl"] != "https://whatships.com/videos/"+
                                  sid.removeprefix("whatships:")+"/"):
        raise ValueError("repository record source identity or approved fields mismatch")
    if (not isinstance(record["limits"],list) or
            len(record["limits"]) != 5 or
            not all(type(s) is str and 15 <= len(s) <= 180
                    for s in record["limits"])):
        raise ValueError("analysis record limitations must be explicit and bounded")
    evidence = record["evidence"]
    if (not isinstance(evidence,dict) or not evidence or
            not set(evidence) <= {
                "browserSpotCheck","numericVisual","characterStudyStatus"}):
        raise ValueError("unsupported analysis evidence types")
    coverage = record["coverage"]
    if (not isinstance(coverage,dict) or
            coverage != {
                "hasBrowserSpotCheck":"browserSpotCheck" in evidence,
                "hasSampledNumericSourceFrames":"numericVisual" in evidence,
                "hasUnreviewedCharacterJob":"characterStudyStatus" in evidence,
                "fullFilmReviewed":False,
            }):
        raise ValueError("analysis review coverage claims not supported by evidence")
    if "browserSpotCheck" in evidence:
        spot = evidence["browserSpotCheck"]
        if (not isinstance(spot,dict) or set(spot) != {
                "observedOn","method","coverage","visualTags","visibleMoments",
                "techniqueHypotheses","sourcePts","evidenceStatus"} or
                spot["method"] != "browser-player" or
                spot["coverage"] != "selected-moments-only" or
                spot["sourcePts"] is not None or
                spot["evidenceStatus"] !=
                "browser-moments-observed-no-timestamp-or-complete-film-review" or
                type(spot["observedOn"]) is not str):
            raise ValueError("browser observation falsely claims original PTS or full review")
        for key,limit in (("visualTags",40),("visibleMoments",30),
                          ("techniqueHypotheses",30)):
            values = spot[key]
            if (not isinstance(values,list) or len(values)>limit or
                    any(type(s) is not str or not 1 <= len(s) <= 1000 for s in values)):
                raise ValueError("unapproved browser observation text")
    if "characterStudyStatus" in evidence:
        item = evidence["characterStudyStatus"]
        if (not isinstance(item,dict) or set(item) != {"status","detail"} or
                item["status"] != "completed-unreviewed-model-proposals" or
                item["detail"] !=
                "Raw model scenes remain in private local study artifacts; not imported or human certified."):
            raise ValueError("character status must not embed identities, transcripts, or private models")
    numeric = evidence.get("numericVisual")
    if numeric is None:
        if record["sourceMediaSha256"] is not None:
            raise ValueError("non-numeric research record cannot assert video bytes were observed")
        return
    sha = numeric.get("sourceSha256") if isinstance(numeric,dict) else None
    if (not isinstance(sha,str) or not re.fullmatch("[0-9a-f]{64}",sha) or
            sha != record["sourceMediaSha256"] or
            set(numeric) != {"sourceSha256","windows","evidenceStatus"} or
            numeric["evidenceStatus"] !=
            "sampled-original-source-pts-metrics-not-expert-reviewed"):
        raise ValueError("numeric video evidence is not bound to an actual source fingerprint")
    windows = numeric["windows"]
    if not isinstance(windows,list) or not 1 <= len(windows) <= _MAX_WINDOWS:
        raise ValueError("invalid count of source-PTS numeric windows")
    def exact_number(value: Any, name: str, limit: float=1.0) -> None:
        if (type(value) not in (int,float) or not math.isfinite(value) or
                not 0 <= value <= limit):
            raise ValueError("unapproved numeric video metric: "+name)
    def rational(item: Any) -> Fraction:
        if (not isinstance(item,dict) or set(item) != {"numerator","denominator"}
                or type(item["numerator"]) is not int or
                type(item["denominator"]) is not int or item["denominator"] <= 0):
            raise ValueError("source-PTS rational malformed")
        return Fraction(item["numerator"],item["denominator"])
    previous_end = -1
    for window in windows:
        if (not isinstance(window,dict) or set(window) != {
                "startSeconds","endSeconds","scan","cutCandidatePts",
                "sampledFrames","sampledFramePairs","sampledWindowSummary",
                "evidenceStatus"} or
                window["evidenceStatus"] != "source-PTS-RGB-metrics-unreviewed"):
            raise ValueError("numeric window has unsupported contents")
        start,end = window["startSeconds"],window["endSeconds"]
        if (type(start) is not int or type(end) is not int or
                not 0 <= start < end <= 3600 or not 1 <= end-start <= 30 or
                start < previous_end):
            raise ValueError("numeric original source window not ordered/bounded")
        previous_end=end
        scan = window["scan"]
        if (not isinstance(scan,dict) or set(scan) != {
                "sourceStreamIndex","sourceTimebase","sampledSourcePtsCount",
                "decoder","cutThreshold","frameWidth","frameHeight"} or
                type(scan["sourceStreamIndex"]) is not int or
                not 0 <= scan["sourceStreamIndex"] <= 64 or
                scan["decoder"] not in (
                    "verified-seek-original-pts-v1","source-prefix-ordinal-pts-v1")):
            raise ValueError("numeric decoder/source metadata invalid")
        timebase = rational(scan["sourceTimebase"])
        exact_number(scan["cutThreshold"],"cutThreshold")
        for key,minval,maxval in (("frameWidth",64,320),("frameHeight",36,180)):
            if type(scan[key]) is not int or not minval<=scan[key]<=maxval:
                raise ValueError("measured video frame size outside accepted bounds")
        frames = window["sampledFrames"]
        pairs = window["sampledFramePairs"]
        if (not isinstance(frames,list) or not 2 <= len(frames) <= _MAX_SAMPLES or
                scan["sampledSourcePtsCount"] != len(frames) or
                not isinstance(pairs,list) or len(pairs) != len(frames)-1):
            raise ValueError("numeric sampled original-PTS frames/pairs invalid")
        pts=[]
        for frame in frames:
            if (not isinstance(frame,dict) or set(frame) != {
                    "sourcePts","sourceSeconds","appearance"} or
                    type(frame["sourcePts"]) is not int or
                    abs(frame["sourcePts"]) > 2**53 or
                    rational(frame["sourceSeconds"]) != frame["sourcePts"]*timebase):
                raise ValueError("numeric frame source PTS/timing unsupported")
            pts.append(frame["sourcePts"])
            appearance=frame["appearance"]
            fields={"meanRgb","meanDisplayLumaProxy","displayLumaStdDev",
                    "meanSaturationProxy","shadowPixelFraction","brightPixelFraction"}
            if (not isinstance(appearance,dict) or set(appearance) != fields or
                    not isinstance(appearance["meanRgb"],list) or
                    len(appearance["meanRgb"]) != 3):
                raise ValueError("numeric display appearance schema changed")
            for key in fields-{"meanRgb"}:
                exact_number(appearance[key],key)
            for val in appearance["meanRgb"]:
                exact_number(val,"meanRgb")
        if pts != sorted(set(pts)):
            raise ValueError("numeric original-source-PTS order invalid")
        cuts=window["cutCandidatePts"]
        if (not isinstance(cuts,list) or cuts!=sorted(set(cuts)) or
                any(type(p) is not int or not pts[0]<=p<=pts[-1] for p in cuts)):
            raise ValueError("numeric cut candidate source PTS invalid")
        for i,pair in enumerate(pairs):
            if (not isinstance(pair,dict) or set(pair) != {
                    "startPts","endPts","sourceDeltaSeconds","status",
                    "meanAbsoluteDisplayRgbDelta",
                    "meanAbsoluteDisplayRgbDeltaPerSecond"} or
                    pair["startPts"] != pts[i] or pair["endPts"] != pts[i+1] or
                    rational(pair["sourceDeltaSeconds"]) != (pts[i+1]-pts[i])*timebase):
                raise ValueError("numeric frame pair is not bound to original source PTS")
            if pair["status"] == "cut-candidate-between-samples":
                if (pair["meanAbsoluteDisplayRgbDelta"] is not None or
                        pair["meanAbsoluteDisplayRgbDeltaPerSecond"] is not None):
                    raise ValueError("cut-spanning pair must abstain")
            elif pair["status"] == "rgb-image-difference-proxy":
                exact_number(pair["meanAbsoluteDisplayRgbDelta"],"image delta")
                exact_number(pair["meanAbsoluteDisplayRgbDeltaPerSecond"],"rate",100000)
            else:
                raise ValueError("unapproved camera/motion interpretation")
        summary=window["sampledWindowSummary"]
        expected={"cutCandidateCountBetweenFirstAndLastSample",
                  "cutCandidateRatePerRequestedMinute",
                  "meanSampledDisplayLumaProxy","meanSampledSaturationProxy",
                  "meanWithinShotDisplayRgbDelta","withinShotComparedPairs",
                  "cutSeparatedPairs"}
        if not isinstance(summary,dict) or set(summary)!=expected:
            raise ValueError("numeric sampled-window summary unsupported")
        for key,high in (("cutCandidateCountBetweenFirstAndLastSample",10000),
                         ("withinShotComparedPairs",24),("cutSeparatedPairs",24)):
            v=summary[key]
            if type(v) is not int or not 0<=v<=high:
                raise ValueError("sampled-window count invalid")
        if (summary["cutCandidateCountBetweenFirstAndLastSample"]!=len(cuts) or
                summary["withinShotComparedPairs"]+summary["cutSeparatedPairs"] !=len(pairs)):
            raise ValueError("numeric summary does not match frame evidence")
        exact_number(summary["cutCandidateRatePerRequestedMinute"],"cut rate",100000)
        exact_number(summary["meanSampledDisplayLumaProxy"],"mean luma")
        exact_number(summary["meanSampledSaturationProxy"],"mean saturation")
        if summary["meanWithinShotDisplayRgbDelta"] is not None:
            exact_number(summary["meanWithinShotDisplayRgbDelta"],"RGB delta")


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
        _validate_record(record,sid,index["catalogSnapshotSha256"])
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


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    """Atomically replace one tracked JSON file without a partial text write."""
    with tempfile.NamedTemporaryFile(
        prefix=".kumiki-merge-",suffix=".json",dir=path.parent,delete=False
    ) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            pass
    try:
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def sync_repository_analysis(
    snapshot_path: Path, incoming: Path, root: Path, *,
    replace_existing: bool = False,
) -> dict[str,Any]:
    """Merge an analyzed export into the Git-tracked canonical corpus.

    Missing new layers are appended; existing evidence is never silently
    replaced/downgraded. Explicit replace is still under Git version control.
    Prevalidates every input before writing; on errors, restores old bytes.
    """
    if type(replace_existing) is not bool or root.resolve() == incoming.resolve():
        raise ValueError("sync requires a distinct incoming directory and explicit replacement policy")
    existing_stats = validate_repository_analysis(root,snapshot_path)
    incoming_stats = validate_repository_analysis(incoming,snapshot_path)
    original_index = _read_json(root/"index.json")
    next_index = _read_json(incoming/"index.json")
    if (original_index["catalogSnapshotSha256"] != next_index["catalogSnapshotSha256"]
            or original_index["catalogSnapshotOn"] != next_index["catalogSnapshotOn"]
            or original_index["catalogVideoCount"] != next_index["catalogVideoCount"]):
        raise ValueError("cannot merge analyses from different catalog snapshots")
    old = {x["sourceId"]:_read_json(root/x["recordPath"])
           for x in original_index["entries"]}
    newer = {x["sourceId"]:_read_json(incoming/x["recordPath"])
             for x in next_index["entries"]}
    merged = dict(old)
    changes = 0
    for sid,new in newer.items():
        if sid not in merged:
            merged[sid] = new
            changes += 1
            continue
        prior = merged[sid]
        if (new["watchUrl"] != prior["watchUrl"]
                or new["catalogSnapshotSha256"] != prior["catalogSnapshotSha256"]):
            raise ValueError("source or catalog identity conflict during analysis sync")
        combined = dict(prior["evidence"])
        for kind,layer in new["evidence"].items():
            if kind in combined and combined[kind] != layer and not replace_existing:
                raise ValueError("existing source analysis evidence differs; explicit --replace-existing required")
            combined[kind] = layer
        numeric = combined.get("numericVisual")
        media_sha = numeric.get("sourceSha256") if numeric is not None else None
        if (prior.get("sourceMediaSha256") is not None and
                media_sha is not None and media_sha != prior["sourceMediaSha256"]
                and not replace_existing):
            raise ValueError("numeric evidence switched to different video bytes")
        new_record = {
            **prior,
            "sourceMediaSha256":media_sha,
            "evidence":combined,
            "coverage":{
                "hasBrowserSpotCheck":"browserSpotCheck" in combined,
                "hasSampledNumericSourceFrames":"numericVisual" in combined,
                "hasUnreviewedCharacterJob":"characterStudyStatus" in combined,
                "fullFilmReviewed":False,
            },
        }
        if new_record != prior:
            merged[sid] = new_record
            changes += 1
    new_index = {
        **original_index,
        "sourceLinkedAnalysisCount":len(merged),
        "browserSpotCheckCount":sum("browserSpotCheck" in r["evidence"] for r in merged.values()),
        "sampledNumericVideoCount":sum("numericVisual" in r["evidence"] for r in merged.values()),
        "unreviewedCharacterJobCount":sum("characterStudyStatus" in r["evidence"] for r in merged.values()),
        "fullFilmReviewedCount":0,
        "entries":[{
            "sourceId":sid,
            "recordPath":sid.removeprefix("whatships:")+".json",
            "evidenceKinds":sorted(merged[sid]["evidence"]),
        } for sid in sorted(merged)],
    }
    # Validate new in-memory records against the same source contracts as
    # standalone export, before touching the tracked working tree.
    for sid,rec in merged.items():
        _validate_record(rec,sid,original_index["catalogSnapshotSha256"])
    source_signature=file_signature(snapshot_path)
    index_signature=file_signature(root/"index.json")
    originals = {
        root/(sid.removeprefix("whatships:")+".json"):
            (root/(sid.removeprefix("whatships:")+".json")).read_bytes()
        for sid in old
    }
    originals[root/"index.json"]=(root/"index.json").read_bytes()
    changed_files=[]
    try:
        for sid,rec in merged.items():
            destination=root/(sid.removeprefix("whatships:")+".json")
            data=_json_bytes(rec)
            if destination.exists() and (
                    destination.is_symlink() or destination.read_bytes()!=originals.get(destination)):
                raise ValueError("analysis source was edited concurrently before sync")
            if originals.get(destination)!=data:
                _atomic_write_bytes(destination,data)
                changed_files.append(destination)
        require_unchanged(snapshot_path,source_signature)
        require_unchanged(root/"index.json",index_signature)
        _atomic_write_bytes(root/"index.json",_json_bytes(new_index))
        changed_files.append(root/"index.json")
        validate_repository_analysis(root,snapshot_path)
    except Exception:
        for file in reversed(changed_files):
            if file in originals:
                _atomic_write_bytes(file,originals[file])
            else:
                file.unlink(missing_ok=True)
        raise
    return {
        "schemaVersion":INDEX_VERSION,
        "previousVideoEvidenceRecords":len(old),
        "incomingVideoEvidenceRecords":len(newer),
        "mergedVideoEvidenceRecords":len(merged),
        "recordsChangedOrAdded":changes,
        "sourceSnapshotSha256":original_index["catalogSnapshotSha256"],
        "humanReviewedFullVideos":0,
        "note":"Working-tree JSON updated; git add/commit is still required to persist changes.",
    }
