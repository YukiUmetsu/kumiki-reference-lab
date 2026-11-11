"""Export compact numeric-only trailer study evidence without reference footage.

Run after `study-reference` for each declared 20-second window. The resulting
JSON retains original frame/audio PTS, cut candidates, optical-flow evidence
and sampled color descriptors, but no audiovisual media or extracted images.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kumiki_reference_lab.analyzers.audio.levels import analyze_audio_levels


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _single(parent: Path, pattern: str) -> Path:
    matches = sorted(parent.glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {pattern} under {parent}")
    return matches[0]


def _compact_appearance(report: dict) -> list[dict]:
    fields = ("meanLumaProxy", "meanSaturation", "lumaContrastP90MinusP10",
              "shadowPixelFraction", "brightPixelFraction", "hueHistogram12")
    return [{"sourcePts": row["sourcePts"],
             **{name: row["appearance"][name] for name in fields}}
            for row in report["samples"]]


def build_evidence(video: dict, *, media_root: Path, runs_root: Path) -> dict:
    windows = []
    for planned in video["windows"]:
        name = planned["window"]
        if name not in ("opening", "middle", "ending"):
            raise ValueError("unexpected window name")
        slug = video["id"] + ("" if name == "opening" else "-" + name)
        media = media_root / (slug + ".mp4")
        run = runs_root / slug
        analysis = _single(run / "analysis", "analysis-*")
        study = _single(run, "study-*")
        timeline = _single(study / "visual", "timeline-*")
        cuts = _read(analysis / "shot-candidates.json")
        appearance = _read(analysis / "appearance.json")
        levels = analyze_audio_levels(media, seconds=20, rights_status="review-required")
        if (cuts["sourceSha256"] != planned["windowSourceSha256"] or
                levels["sourceSha256"] != cuts["sourceSha256"]):
            raise ValueError("source SHA mismatch between planned, visual and audio evidence")
        windows.append({
            "window": name,
            "sourceOffsetSeconds": planned["sourceOffsetSeconds"],
            "scanWindowSeconds": 20,
            "windowSourceSha256": cuts["sourceSha256"],
            "sourceVideoTimebase": cuts["sourceTimebase"],
            "sourceAudioTimebase": levels["sourceTimebase"],
            "audioSampleRateHz": levels["sampleRateHz"],
            "shotCutCandidates": cuts["candidates"],
            "defaultCutThreshold": cuts["detector"]["threshold"],
            "sensitivityCutThreshold": 0.15,
            "sensitivityCutCandidateCount": planned["cutCandidateCountAtThreshold015"],
            "appearanceSamples": _compact_appearance(appearance),
            "imageMotion": _read(analysis / "image-motion.json"),
            "sparseFlow": _read(analysis / "sparse-flow.json"),
            "audioLevels": {
                "status": levels["status"],
                "excludedPartialBoundaryFrames": levels.get(
                    "excludedPartialBoundaryFrames", 0),
                "columns": ["sourcePts", "decodedSampleCount", "rmsDbFs", "peakDbFs"],
                "rows": [[row.get("sourcePts"), row.get("decodedSampleCount"),
                          row.get("rmsDbFs"), row.get("peakDbFs")]
                         for row in levels["frames"]],
            },
            "audioOnsets": _read(timeline / "audio-onsets.json"),
            "avCutEvidence": _read(timeline / "av-cut-evidence.json"),
            "editRhythm": _read(study / "edit-rhythm.json"),
            "techniqueProposals": _read(study / "technique-proposals.json"),
        })
    result = {
        "schemaVersion": "kumiki.movie-promotion-window-evidence.v1",
        "catalogId": video["catalogId"],
        "id": video["id"],
        "officialPlayerUrl": video["officialPlayerUrl"],
        "originalSourceSha256": video["sourceSha256"],
        "originalDurationSeconds": video["sourceDurationSeconds"],
        "originalSourceResolution": video["sourceResolution"],
        "rightsStatus": "review-required",
        "coverage": "three-selected-windows-not-full-runtime",
        "timeMapping": "Window source PTS are exact within that file. Middle/end clip times plus sourceOffsetSeconds are approximate original positions because those windows were re-encoded.",
        "limits": "Numerical evidence and conservative candidates, not verified cuts, camera movement, physical lighting, words, speaker identities or semantic actions. Video, audio, extracted frames and temporary signed CDN URLs are intentionally omitted.",
        "windows": windows,
    }
    # A distributor's retail preview can differ from a studio's YouTube upload.
    # Preserve explicit edition identity alongside the source hash, without
    # embedding expiring media URLs or implying upload equivalence.
    for field in ("sourceEdition", "sourceTrackId", "catalogUploadIdentityMatch"):
        if field in video:
            result[field] = video[field]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = _read(args.summary)
    if summary.get("schemaVersion") != "kumiki.movie-promotion-measurements.v1":
        raise ValueError("unsupported summary schema")
    args.out.mkdir(parents=True, exist_ok=True)
    for video in summary["videos"]:
        report = build_evidence(video, media_root=args.media_root, runs_root=args.runs_root)
        target = args.out / (video["id"] + ".json")
        if target.exists():
            raise FileExistsError(f"refusing to overwrite evidence: {target}")
        target.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"{video['id']}: {len(report['windows'])} windows, {target.stat().st_size} bytes")


if __name__ == "__main__":
    main()
