"""Aggregate measured 2D image-plane movement, preserving geometry abstentions.

Derived solely from source-hashed 13-film numeric studies. Image translation
may reflect moving objects, animation, camera, scrolling, parallax or all of
these; no physical camera moves or editing intent are inferred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

SCHEMA = "kumiki.movie-promotion-image-motion-proxies.v1"
THRESHOLD_FRACTION_PER_SECOND = 0.01


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _rational(value: dict, field: str) -> float:
    if not isinstance(value, dict):
        raise ValueError(f"{field}: expected rational")
    n, d = value.get("numerator"), value.get("denominator")
    if (isinstance(n, bool) or isinstance(d, bool) or not isinstance(n, int)
            or not isinstance(d, int) or n < 0 or d <= 0):
        raise ValueError(f"{field}: invalid rational")
    return n / d


def _valid_coordinate(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field}: invalid measured displacement")
    return float(value)


def build_motion_report(index: dict, details: dict[str, tuple[dict, str]],
                        index_git_blob_sha: str) -> dict:
    if index.get("schemaVersion") != "kumiki.movie-promotion-measurements.v1":
        raise ValueError("invalid measured index")
    source_items = index.get("videos")
    if not isinstance(source_items, list) or not source_items:
        raise ValueError("empty measured index")
    if set(details) != {row["id"] for row in source_items}:
        raise ValueError("detail-index mismatch")
    output = []
    for row in source_items:
        source_id = row["id"]
        detail, blob_sha = details[source_id]
        if (detail.get("id") != source_id
                or detail.get("catalogId") != row["catalogId"]
                or detail.get("originalSourceSha256") != row["sourceSha256"]
                or detail.get("rightsStatus") != "review-required"
                or len(detail["windows"]) != len(row["windows"])):
            raise ValueError(f"{source_id}: source provenance mismatch")
        windows = []
        for short, w in zip(row["windows"], detail["windows"]):
            key = f"{source_id}/{short['window']}"
            src_hash = short["windowSourceSha256"]
            if (w["window"] != short["window"]
                    or w["windowSourceSha256"] != src_hash
                    or w["sourceOffsetSeconds"] != short["sourceOffsetSeconds"]
                    or w["scanWindowSeconds"] != short["scanSeconds"]
                    or w["imageMotion"]["sourceSha256"] != src_hash
                    or w["sparseFlow"]["sourceSha256"] != src_hash):
                raise ValueError(f"{key}: source window fingerprint mismatch")
            tb = _rational(w["sourceVideoTimebase"], f"{key}/timebase")
            statuses: dict[str, int] = {}
            measured_speeds = []
            material_count = 0
            motion_pairs = w["imageMotion"]["pairs"]
            sparse_pairs = w["sparseFlow"]["pairs"]
            for p in motion_pairs:
                kind = p["status"]
                statuses[kind] = statuses.get(kind, 0) + 1
                start, end = p["startPts"], p["endPts"]
                if (isinstance(start, bool) or isinstance(end, bool)
                        or not isinstance(start, int) or not isinstance(end, int)
                        or not 0 <= start < end):
                    raise ValueError(f"{key}: malformed motion PTS")
                dt = _rational(p["deltaTimeSeconds"], f"{key}/deltaTime")
                if dt <= 0 or abs((end - start) * tb - dt) > 1e-6:
                    raise ValueError(f"{key}: image pair PTS/timebase mismatch")
                if kind == "measured-image-translation":
                    dx = _valid_coordinate(p["dxNormalized"], f"{key}/dx")
                    dy = _valid_coordinate(p["dyNormalized"], f"{key}/dy")
                    # This is relative pixel translation per second, not
                    # object velocity or physical camera translation.
                    speed = math.hypot(dx, dy) / dt
                    measured_speeds.append(speed)
                    if speed >= THRESHOLD_FRACTION_PER_SECOND:
                        material_count += 1
            sparse_statuses: dict[str, int] = {}
            for p in sparse_pairs:
                kind = p["status"]
                sparse_statuses[kind] = sparse_statuses.get(kind, 0) + 1
            if sum(statuses.values()) != len(motion_pairs):
                raise ValueError(f"{key}: missing image status")
            windows.append({
                "window": short["window"],
                "windowSourceSha256": src_hash,
                "sourceOffsetSeconds": short["sourceOffsetSeconds"],
                "scanSeconds": short["scanSeconds"],
                "imageMotionPairCount": len(motion_pairs),
                "imageMotionPairStatuses": dict(sorted(statuses.items())),
                "measuredImageTranslationPairs": len(measured_speeds),
                "measuredPairsAboveExploratoryMagnitudeThreshold": material_count,
                "medianFrameNormalizedShiftPerSecondOfMeasuredPairs": (
                    round(statistics.median(measured_speeds), 6) if measured_speeds else None),
                "sparseFlowPairCount": len(sparse_pairs),
                "sparseFlowPairStatuses": dict(sorted(sparse_statuses.items())),
                "calibratedPhysicalCameraConfidence": False,
            })
        output.append({
            "id": source_id, "catalogId": row["catalogId"],
            "originalSourceSha256": row["sourceSha256"],
            "detailGitBlobSha": blob_sha,
            "sourceEdition": detail.get("sourceEdition", "Disney official public-player"),
            "windows": windows,
        })
    all_windows = [window for video in output for window in video["windows"]]
    statuses: dict[str, int] = {}
    sparse: dict[str, int] = {}
    for window in all_windows:
        for status, count in window["imageMotionPairStatuses"].items():
            statuses[status] = statuses.get(status, 0) + count
        for status, count in window["sparseFlowPairStatuses"].items():
            sparse[status] = sparse.get(status, 0) + count
    return {
        "schemaVersion": SCHEMA,
        "sourceIndexGitBlobSha": index_git_blob_sha,
        "method": "Window-level status counts from the prior 160x90 sampled-frame phase-correlation image-motion analyzer and sparse corner-flow review. Exploratory shift threshold: Euclidean norm of dxNormalized and dyNormalized / measured pair duration >= 0.01 frame fraction per second.",
        "limits": "Not camera-motion frequency, optical flow ground truth, subject activity, shot scale or visual style. Measured pairs are algorithmic correlation candidates on sparse time samples; low-texture/cut-boundary/ambiguous pairs abstain. Not all 20 seconds were observed continuously. Windows are selected, not whole-film coverage. Preview editions may differ.",
        "thresholdFractionPerSecond": THRESHOLD_FRACTION_PER_SECOND,
        "coverage": {
            "sourceCount": len(output),
            "windowCount": len(all_windows),
            "sourceWindowSeconds": sum(w["scanSeconds"] for w in all_windows),
            "imageMotionPairCount": sum(w["imageMotionPairCount"] for w in all_windows),
            "imageMotionPairStatuses": dict(sorted(statuses.items())),
            "sparseFlowPairCount": sum(w["sparseFlowPairCount"] for w in all_windows),
            "sparseFlowPairStatuses": dict(sorted(sparse.items())),
            "measuredImageTranslationPairs": sum(
                w["measuredImageTranslationPairs"] for w in all_windows),
            "measuredPairsAboveExploratoryMagnitudeThreshold": sum(
                w["measuredPairsAboveExploratoryMagnitudeThreshold"] for w in all_windows),
        },
        "videos": sorted(output, key=lambda item: item["id"]),
    }


def build_from_folder(root: Path) -> dict:
    raw_index = (root / "index.json").read_bytes()
    index = json.loads(raw_index)
    details = {}
    for video in index["videos"]:
        raw_detail = (root / (video["id"] + ".json")).read_bytes()
        details[video["id"]] = (json.loads(raw_detail), _git_blob_sha(raw_detail))
    return build_motion_report(index, details, _git_blob_sha(raw_index))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("research/analysis/movie-promotions"))
    parser.add_argument("--out", type=Path, default=Path(
        "research/analysis/movie-promotions/derived/image-motion-proxies.v1.json"))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = build_from_folder(args.root)
    if args.verify:
        if json.loads(args.out.read_text(encoding="utf-8")) != output:
            parser.exit(1, "image-plane motion summary is stale\n")
        print(f"Verified {output['coverage']['windowCount']} image-motion windows")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
