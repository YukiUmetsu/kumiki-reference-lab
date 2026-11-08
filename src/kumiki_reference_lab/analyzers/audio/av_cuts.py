"""Candidate audio-level contrast near independently measured video cuts.

Both original stream clocks are converted to rational presentation seconds,
but a shared physical synchronization origin is NOT independently recovered.
The resulting associations are review hypotheses, not confirmed edit intent.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.audio.levels import analyze_audio_levels
from kumiki_reference_lab.analyzers.shots.evidence import build_shot_evidence
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.contracts.analysis import AV_CUT_EVIDENCE_VERSION
from kumiki_reference_lab.core.timebase import as_rational_dict


def _rational(value: dict[str, int]) -> Fraction:
    return Fraction(value["numerator"], value["denominator"])


def _summary(frames: list[dict[str, Any]]) -> dict[str, Any]:
    finite_rms = [f["rmsDbFs"] for f in frames if f["rmsDbFs"] is not None]
    finite_peaks = [f["peakDbFs"] for f in frames if f["peakDbFs"] is not None]
    return {
        "frameCount": len(frames),
        "quietFrameCount": sum(f["quietFrameCandidate"] for f in frames),
        "quietFrameFraction": (
            round(sum(f["quietFrameCandidate"] for f in frames) / len(frames), 6)
            if frames else None),
        "medianFiniteRmsDbFs": (
            round(statistics.median(finite_rms), 6) if finite_rms else None),
        "maximumFinitePeakDbFs": max(finite_peaks) if finite_peaks else None,
        "firstAudioSourcePts": frames[0]["sourcePts"] if frames else None,
        "lastAudioSourcePts": frames[-1]["sourcePts"] if frames else None,
    }


def summarize_cut_audio(
    regions: list[dict[str, Any]], levels: list[dict[str, Any]], *,
    window_ms: int,
) -> list[dict[str, Any]]:
    """Aggregate only audio frames wholly before/after a candidate boundary."""
    if type(window_ms) is not int or not 100 <= window_ms <= 2000:
        raise ValueError("audio-video window_ms must be 100..2000")
    window = Fraction(window_ms, 1000)
    rows = []
    for region in regions[1:]:
        cut_time = _rational(region["startSeconds"])
        before, after = [], []
        for frame in levels:
            start = _rational(frame["sourceSeconds"])
            end = start + _rational(frame["decodedDurationSeconds"])
            # Exclude straddling frames: their RMS might mix both sides.
            if cut_time - window <= start and end <= cut_time:
                before.append(frame)
            elif cut_time <= start and end <= cut_time + window:
                after.append(frame)
        before_summary, after_summary = _summary(before), _summary(after)
        prior, following = (before_summary["quietFrameFraction"],
                            after_summary["quietFrameFraction"])
        if prior is None or following is None or len(before) < 2 or len(after) < 2:
            signal = "insufficient-fully-contained-audio-frames"
        elif abs(following - prior) >= 0.5:
            signal = "candidate-quiet-level-contrast"
        else:
            signal = "no-strong-quiet-level-contrast"
        rows.append({
            "videoRegionId": region["id"],
            "videoCutCandidatePts": region["startPtsInclusive"],
            "videoCutCandidateSeconds": region["startSeconds"],
            "windowSeconds": as_rational_dict(window),
            "before": before_summary,
            "after": after_summary,
            "status": signal,
            "interpretationStatus": "not-verified",
        })
    return rows


def build_av_cut_evidence(source: Path, analysis_run: Path, *,
                          window_ms: int = 400,
                          max_audio_frames: int = 4096,
                          ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> dict[str, Any]:
    """Measure possible audio contrast against candidate cuts in one original file."""
    if type(window_ms) is not int or not 100 <= window_ms <= 2000:
        raise ValueError("audio-video window_ms must be 100..2000")
    if type(max_audio_frames) is not int or not 1 <= max_audio_frames <= 10000:
        raise ValueError("max_audio_frames must be 1..10000")
    evidence = build_shot_evidence(analysis_run)
    if evidence["status"] != "candidate-edit-regions":
        raise ValueError("video original PTS are not reliable enough for A/V candidates")
    run = _json_file(analysis_run, limit=262_144)
    seconds = run["settings"]["seconds"]
    audio = analyze_audio_levels(
        source, seconds=seconds, max_frames=max_audio_frames,
        ffmpeg=ffmpeg, ffprobe=ffprobe,
        rights_status=run["settings"]["rightsStatus"])
    if audio["sourceSha256"] != evidence["sourceSha256"]:
        raise ValueError("audio and video evidence refer to different source bytes")
    if audio["status"] == "no-audio-stream":
        status, cuts = "no-audio-stream", []
    elif audio["status"] == "source-pts-aligned-level-observations":
        status = "candidate-cross-stream-pts-association"
        cuts = summarize_cut_audio(evidence["regions"], audio["frames"],
                                   window_ms=window_ms)
    else:
        raise ValueError("audio level evidence is incomplete")
    audio_identity = hashlib.sha256(
        (json.dumps(audio, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                    allow_nan=False) + "\n").encode("utf-8")).hexdigest()
    return {
        "schemaVersion": AV_CUT_EVIDENCE_VERSION,
        "sourceSha256": evidence["sourceSha256"],
        "analysisRunSha256": evidence["analysisRunSha256"],
        "audioLevelEvidenceSha256": audio_identity,
        "videoSourceTimebase": evidence["sourceTimebase"],
        "audioSourceTimebase": audio["sourceTimebase"],
        "videoStreamIndex": evidence["sourceStreamIndex"],
        "audioStreamIndex": audio["audioStreamIndex"],
        "scanWindowSeconds": seconds,
        "comparisonWindowMs": window_ms,
        "status": status,
        "clockRelation": "candidate-same-container-source-presentation-seconds-no-independent-sync-verification",
        "videoCutStatus": "algorithmic-candidates-not-confirmed-edits",
        "videoCutCandidateCount": max(0, len(evidence["regions"]) - 1),
        "audioLevelStatus": "decoded-signal-measurements-not-semantic-audio-events",
        "qualityVerdict": "not-performed",
        "cutCandidates": cuts,
        "limits": "Shared source bytes alone do not prove synchronized clocks, absence of priming/edit lists, musical beats, narration intent, causality or edit accuracy. Only fully contained audio frames are compared; a straddling frame is excluded.",
    }
