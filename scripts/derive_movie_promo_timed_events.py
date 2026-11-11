"""Derive source-PTS cut and audio-rise timelines from measured movie evidence.

No video is downloaded. Only existing tracked evidence contributes. Candidate
edits, audio level rises and their temporal proximity are not human-confirmed
cuts, music beats, sound effects, or evidence of deliberate synchronization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

SCHEMA = "kumiki.movie-promotion-timed-events.v1"
INDEX_SCHEMA = "kumiki.movie-promotion-measurements.v1"
DETAIL_SCHEMA = "kumiki.movie-promotion-window-evidence.v1"
PROXIMITY_SECONDS = 0.25
BIN_SECONDS = 5


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _sha(value: object, where: str) -> str:
    if (not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)):
        raise ValueError(f"{where}: invalid SHA-256")
    return value


def _nonnegative_number(value: object, where: str, *, allow_zero: bool = True) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 or (not allow_zero and value == 0)):
        raise ValueError(f"{where}: invalid finite number")
    return float(value)


def _fraction(value: dict, where: str) -> float:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: missing rational seconds/timebase")
    num, den = value.get("numerator"), value.get("denominator")
    if (isinstance(num, bool) or isinstance(den, bool)
            or not isinstance(num, int) or not isinstance(den, int)
            or num < 0 or den <= 0):
        raise ValueError(f"{where}: invalid rational seconds/timebase")
    return num / den


def _timeline_event(event: dict, where: str, *, pts_key: str, seconds_key: str,
                    timebase: dict, scan_seconds: float) -> tuple[int, float]:
    pts = event.get(pts_key)
    if isinstance(pts, bool) or not isinstance(pts, int) or pts < 0:
        raise ValueError(f"{where}: invalid source PTS")
    timestamp = _fraction(event.get(seconds_key), where)
    calculated = pts * _fraction(timebase, where + "/timebase")
    if abs(timestamp - calculated) > 1e-6:
        raise ValueError(f"{where}: PTS/timebase mismatch")
    if not 0 <= timestamp < scan_seconds:
        raise ValueError(f"{where}: timestamp outside measured window")
    return pts, timestamp


def derive_timed_events(index: dict, details: dict[str, tuple[dict, str]],
                        index_git_sha: str) -> dict:
    if index.get("schemaVersion") != INDEX_SCHEMA:
        raise ValueError("unsupported source index schema")
    if not isinstance(index_git_sha, str) or len(index_git_sha) != 40:
        raise ValueError("invalid index blob SHA")
    videos = index.get("videos")
    if not isinstance(videos, list) or not videos:
        raise ValueError("missing measured videos")
    if set(details) != {video["id"] for video in videos}:
        raise ValueError("missing or unindexed detail files")
    results = []
    for summary in videos:
        film_id = summary["id"]
        report, detail_git_sha = details[film_id]
        _sha(summary["sourceSha256"], film_id)
        if (report.get("schemaVersion") != DETAIL_SCHEMA
                or report.get("id") != film_id
                or report.get("originalSourceSha256") != summary["sourceSha256"]
                or report.get("originalDurationSeconds") != summary["sourceDurationSeconds"]
                or report.get("catalogId") != summary["catalogId"]
                or report.get("rightsStatus") != "review-required"):
            raise ValueError(f"{film_id}: index/detail provenance mismatch")
        if len(summary["windows"]) != len(report["windows"]):
            raise ValueError(f"{film_id}: number of windows differs")
        windows = []
        for compact, window in zip(summary["windows"], report["windows"]):
            phase = compact["window"]
            where = f"{film_id}/{phase}"
            source_sha = _sha(compact["windowSourceSha256"], where)
            if (window["window"] != phase
                    or window["windowSourceSha256"] != source_sha
                    or window["sourceOffsetSeconds"] != compact["sourceOffsetSeconds"]
                    or window["scanWindowSeconds"] != compact["scanSeconds"]
                    or window["audioOnsets"]["sourceSha256"] != source_sha):
                raise ValueError(f"{where}: indexed and detailed window mismatch")
            seconds = _nonnegative_number(compact["scanSeconds"], where + "/scan", allow_zero=False)
            offset = _nonnegative_number(compact["sourceOffsetSeconds"], where + "/offset")
            if seconds != 20 or offset + seconds > summary["sourceDurationSeconds"] + 0.5:
                raise ValueError(f"{where}: unsupported scan bounds")
            if not isinstance(window["shotCutCandidates"], list) or not isinstance(
                    window["audioOnsets"]["candidates"], list):
                raise ValueError(f"{where}: missing cut/audio candidate list")
            cuts = [_timeline_event(c, where + "/cut", pts_key="sourcePts",
                                    seconds_key="sourceSeconds",
                                    timebase=window["sourceVideoTimebase"],
                                    scan_seconds=seconds)
                    for c in window["shotCutCandidates"]]
            attacks = [_timeline_event(a, where + "/audio", pts_key="anchorSourcePts",
                                       seconds_key="anchorSourceSeconds",
                                       timebase=window["sourceAudioTimebase"],
                                       scan_seconds=seconds)
                       for a in window["audioOnsets"]["candidates"]]
            if (any(now[1] <= before[1] for before, now in zip(cuts, cuts[1:]))
                    or any(now[1] <= before[1] for before, now in zip(attacks, attacks[1:]))):
                raise ValueError(f"{where}: nonmonotonic candidate timestamps")
            if (len(cuts) != compact["cutCandidateCount"]
                    or len(attacks) != compact["audioLevelAttackCandidateCount"]):
                raise ValueError(f"{where}: candidate-count mismatch")
            cut_bins = [0, 0, 0, 0]
            cut_events = []
            near_count = 0
            for pts, second in cuts:
                cut_bins[min(3, int(second // BIN_SECONDS))] += 1
                nearest = (min(attacks, key=lambda row: (abs(row[1] - second), row[1]))
                           if attacks else None)
                signed_ms = round((nearest[1] - second) * 1000) if nearest else None
                near = nearest is not None and abs(nearest[1] - second) <= PROXIMITY_SECONDS
                near_count += int(near)
                cut_events.append({
                    "sourceVideoPts": pts,
                    "localSeconds": round(second, 6),
                    "nearestAudioAttackDeltaMs": signed_ms,
                    "audioAttackWithin250Ms": near,
                })
            rise_events = []
            for (pts, second), attack in zip(attacks, window["audioOnsets"]["candidates"]):
                rise = _nonnegative_number(attack["measuredRmsRiseDb"],
                                           where + "/rms-rise")
                rise_events.append({
                    "sourceAudioPts": pts,
                    "localSeconds": round(second, 6),
                    "measuredRmsRiseDb": round(rise, 4),
                })
            intervals = [right[1] - left[1] for left, right in zip(cuts, cuts[1:])]
            windows.append({
                "window": phase,
                "windowSourceSha256": source_sha,
                "sourceOffsetSeconds": offset,
                "scanSeconds": seconds,
                "sourceVideoTimebase": window["sourceVideoTimebase"],
                "sourceAudioTimebase": window["sourceAudioTimebase"],
                "sourceOffsetPrecision": "exact-opening" if offset == 0 else "approximate-reencoded-window",
                "cutCandidateCount025": len(cuts),
                "audioLevelAttackCandidateCount": len(attacks),
                "cutCandidatesWithin250MsOfAudioAttack": near_count,
                "cutCandidateCountsByFiveSecondBin": cut_bins,
                "medianInteriorCandidateGapSeconds": round(statistics.median(intervals), 6)
                    if intervals else None,
                "cutEvents": cut_events,
                "audioAttackEvents": rise_events,
            })
        results.append({
            "id": film_id, "catalogId": summary["catalogId"],
            "originalSourceSha256": summary["sourceSha256"],
            "detailGitBlobSha": detail_git_sha,
            "sourceEdition": report.get("sourceEdition", "Disney official public-player"),
            "catalogUploadIdentityMatch": report.get("catalogUploadIdentityMatch", "not-verified"),
            "windows": windows,
        })
    all_windows = [w for film in results for w in film["windows"]]
    return {
        "schemaVersion": SCHEMA,
        "sourceIndexGitBlobSha": index_git_sha,
        "method": "Source-PTS rational cut and audio RMS-rise candidates from source-hashed local study windows. Cut candidates use detector 0.25; audio attacks use the original pre-existing level-rise detector. Cut bins are [0,5), [5,10), [10,15), [15,20) seconds per selected clip. Nearest audio attack is signed audio-minus-video milliseconds, with 250ms inclusive proximity.",
        "limitations": "Only three selected 20-second windows per source, not entire trailer. Cut candidates can be flashes/changes, audio RMS rises are not validated music beats, dialogue, or effects; nearness is not causality or creative synchronization. Reencoded middle/end clips have approximate original offsets. No copied media, visual scene tags or physical-camera inferences.",
        "coverage": {
            "sourceCount": len(results),
            "windowCount": len(all_windows),
            "sampledSeconds": sum(w["scanSeconds"] for w in all_windows),
            "cutCandidateCount025": sum(w["cutCandidateCount025"] for w in all_windows),
            "audioLevelAttackCandidateCount": sum(w["audioLevelAttackCandidateCount"] for w in all_windows),
            "cutCandidatesWithin250MsOfAudioAttack": sum(
                w["cutCandidatesWithin250MsOfAudioAttack"] for w in all_windows),
        },
        "videos": sorted(results, key=lambda item: item["id"]),
    }


def derive_from_folder(root: Path) -> dict:
    index_bytes = (root / "index.json").read_bytes()
    index = json.loads(index_bytes)
    details = {}
    for video in index["videos"]:
        path = root / (video["id"] + ".json")
        data = path.read_bytes()
        details[video["id"]] = (json.loads(data), _git_blob_sha(data))
    return derive_timed_events(index, details, _git_blob_sha(index_bytes))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("research/analysis/movie-promotions"))
    parser.add_argument("--out", type=Path, default=Path(
        "research/analysis/movie-promotions/derived/timed-events.v1.json"))
    parser.add_argument("--verify", action="store_true", help="fail if generated data differs from committed file")
    args = parser.parse_args()
    result = derive_from_folder(args.root)
    if args.verify:
        if json.loads(args.out.read_text(encoding="utf-8")) != result:
            parser.exit(1, "movie-promotion timed events are stale\n")
        print(f"Verified timed evidence from {result['coverage']['sourceCount']} sources")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
