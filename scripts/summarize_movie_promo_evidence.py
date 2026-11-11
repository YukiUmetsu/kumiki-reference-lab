"""Build deterministic comparisons from existing, source-hashed trailer measurements.

No footage is fetched and no physical camera, lighting, or semantic facts are inferred.
Only measured windows contribute. Output is not a full-trailer estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


SCHEMA = "kumiki.movie-promotion-comparison.v1"


def _number(value: object, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{field} must be positive")
    return float(value)


def _count(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _average(windows: list[dict], field: str) -> float:
    weights = [w["appearanceFrameSamples"] for w in windows]
    return round(sum(w[field] * n for w, n in zip(windows, weights)) / sum(weights), 4)


def build_comparison(index: dict, source_git_blob_sha: str) -> dict:
    if index.get("schemaVersion") != "kumiki.movie-promotion-measurements.v1":
        raise ValueError("unexpected source index schema")
    if not isinstance(source_git_blob_sha, str) or len(source_git_blob_sha) != 40 or any(
            ch not in "0123456789abcdef" for ch in source_git_blob_sha):
        raise ValueError("invalid Git blob SHA-1")
    videos = index.get("videos")
    if not isinstance(videos, list) or not videos:
        raise ValueError("empty or invalid source cohort")
    rows = []
    seen_ids = set()
    total_seconds = 0.0
    for video in videos:
        slug = video["id"]
        if not isinstance(slug, str) or not slug or slug in seen_ids:
            raise ValueError("missing or duplicate video id")
        seen_ids.add(slug)
        duration = _number(video["sourceDurationSeconds"], f"{slug}/sourceDurationSeconds", positive=True)
        source_windows = video["windows"]
        if not isinstance(source_windows, list) or not source_windows:
            raise ValueError(f"{slug}: missing windows")
        windows = []
        for raw in source_windows:
            name = raw["window"]
            offset = _number(raw["sourceOffsetSeconds"], f"{slug}/{name}/offset")
            seconds = _number(raw["scanSeconds"], f"{slug}/{name}/seconds", positive=True)
            if offset < 0 or offset + seconds > duration + 0.5:
                raise ValueError(f"{slug}/{name}: window exceeds source bounds")
            frames = _count(raw["appearanceFrameSamples"], f"{slug}/{name}/frames")
            if not frames:
                raise ValueError(f"{slug}/{name}: zero appearance samples")
            normal = _count(raw["cutCandidateCount"], f"{slug}/{name}/cuts")
            sensitive = _count(raw["cutCandidateCountAtThreshold015"], f"{slug}/{name}/sensitiveCuts")
            attacks = _count(raw["audioLevelAttackCandidateCount"], f"{slug}/{name}/attacks")
            if sensitive < normal:
                raise ValueError(f"{slug}/{name}: invalid sensitivity counts")
            luma = _number(raw["meanSampledLumaProxy"], f"{slug}/{name}/luma")
            saturation = _number(raw["meanSampledSaturation"], f"{slug}/{name}/saturation")
            if not (0 <= luma <= 1 and 0 <= saturation <= 1):
                raise ValueError(f"{slug}/{name}: invalid appearance proxy")
            windows.append({
                "window": name, "sourceOffsetSeconds": offset, "scanSeconds": seconds,
                "cutCandidateCount025": normal, "cutCandidateCount015": sensitive,
                "cutCandidatesPerSampledMinute025": round(normal * 60 / seconds, 3),
                "audioLevelAttackCandidateCount": attacks,
                "appearanceFrameSamples": frames,
                "meanSampledLumaProxy": luma, "meanSampledSaturation": saturation,
            })
        ordered = sorted(windows, key=lambda w: w["sourceOffsetSeconds"])
        for prev, next_window in zip(ordered, ordered[1:]):
            if prev["sourceOffsetSeconds"] + prev["scanSeconds"] > next_window["sourceOffsetSeconds"] + 1e-9:
                raise ValueError(f"{slug}: overlapping sampled windows")
        if len(set(w["window"] for w in windows)) != len(windows):
            raise ValueError(f"{slug}: duplicate window name")
        sampled_seconds = sum(w["scanSeconds"] for w in windows)
        total_seconds += sampled_seconds
        normal = sum(w["cutCandidateCount025"] for w in windows)
        sensitive = sum(w["cutCandidateCount015"] for w in windows)
        attacks = sum(w["audioLevelAttackCandidateCount"] for w in windows)
        source_edition = video.get("sourceEdition")
        family = ("apple-itunes-preview" if isinstance(source_edition, str) and "Apple iTunes Store" in source_edition
                  else "disney-public-player" if not source_edition else "other-declared-edition")
        row = {
            "id": slug, "catalogId": video["catalogId"],
            "sourceSha256": video["sourceSha256"],
            "sourceFamily": family, "sourceEdition": source_edition,
            "catalogUploadIdentityMatch": video.get("catalogUploadIdentityMatch", "not-verified"),
            "sourceDurationSeconds": duration,
            "sampledSeconds": sampled_seconds,
            "sampledSourceFraction": round(sampled_seconds / duration, 4),
            "cutCandidateCount025": normal, "cutCandidateCount015": sensitive,
            "cutCandidatesPerSampledMinute025": round(normal * 60 / sampled_seconds, 3),
            "sensitivityExtraCandidates": sensitive - normal,
            "audioLevelAttackCandidateCount": attacks,
            "meanSampledLumaProxy": _average(windows, "meanSampledLumaProxy"),
            "meanSampledSaturation": _average(windows, "meanSampledSaturation"),
            "windows": windows,
        }
        rows.append(row)
    return {
        "schemaVersion": SCHEMA,
        "sourceIndexGitBlobSha": source_git_blob_sha,
        "coverage": {"sourceCount": len(rows), "windowCount": sum(len(v["windows"]) for v in rows),
                     "sampledSeconds": total_seconds},
        "method": "Deterministic aggregation of 20-second source-hashed windows. Cut candidates use FFmpeg scene thresholds 0.25 and 0.15. Appearance proxy averages are weighted by frame samples. Neither cuts/minute nor visual proxies represent unobserved trailer footage.",
        "comparability": "Source families and preview editions differ; Apple retail previews are not established as identical to cataloged YouTube studio trailers. No audience behavior, confirmed edits, real camera/lighting or semantic labels are inferred.",
        "videos": sorted(rows, key=lambda r: r["id"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=Path("research/analysis/movie-promotions/index.json"))
    parser.add_argument("--out", type=Path, default=Path("research/analysis/movie-promotions/derived/comparison.v1.json"))
    parser.add_argument("--verify", action="store_true", help="fail if committed output differs from generated report")
    args = parser.parse_args()
    data = args.index.read_bytes()
    git_blob_sha = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
    report = build_comparison(json.loads(data), git_blob_sha)
    if args.verify:
        if json.loads(args.out.read_text(encoding="utf-8")) != report:
            parser.exit(1, f"derived comparison is stale: {args.out}\n")
        print(f"Verified {len(report['videos'])} source comparison records")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {args.out} ({len(report['videos'])} videos)")


if __name__ == "__main__":
    main()
