"""Conservative audio level-attack candidates on verified original audio PTS.

This is deliberately frame-envelope based, not spectral onset detection or
recognition of beats, narration, impacts, or sound effects.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.audio.levels import analyze_audio_levels
from kumiki_reference_lab.contracts.analysis import AUDIO_ONSETS_VERSION
from kumiki_reference_lab.core.timebase import as_rational_dict


METHOD = "adjacent-source-audio-frame-rms-rise-v1"
LIMITS = (
    "Attack candidates are differences between decoded-frame RMS envelopes, "
    "not sample-accurate acoustic onsets, beats, speech, music or identifiable SFX. "
    "Source PTS anchor marks the start of the *later* frame; the actual sound "
    "change may occur anywhere in the two-frame support window. A change from "
    "a negative-infinity RMS floor has no measurable dB delta. Frames across "
    "audio timestamp discontinuities are never compared. No independently "
    "verified alignment to video cuts or artistic approval is implied."
)


def _fraction(value: dict[str, int]) -> Fraction:
    return Fraction(value["numerator"], value["denominator"])


def audio_onsets_from_levels(
    levels: dict[str, Any], *, min_rise_db: float = 12.0,
    min_peak_dbfs: float = -40.0, cooldown_ms: int = 120,
) -> dict[str, Any]:
    """Rank no events; return only bounded, source-clock envelope candidates."""
    if (type(min_rise_db) not in (float, int) or
            not 1 <= min_rise_db <= 60):
        raise ValueError("min_rise_db must be 1..60")
    if (type(min_peak_dbfs) not in (float, int) or
            not -100 <= min_peak_dbfs <= 0):
        raise ValueError("min_peak_dbfs must be -100..0")
    if type(cooldown_ms) is not int or not 0 <= cooldown_ms <= 2000:
        raise ValueError("cooldown_ms must be 0..2000")
    if levels["status"] not in ("no-audio-stream", "source-pts-aligned-level-observations"):
        raise ValueError("audio onsets require a verified audio-level report")
    frames = levels["frames"]
    if levels["status"] == "no-audio-stream" and frames:
        raise ValueError("no-audio-stream report cannot contain decoded frames")
    sample_rate = levels["sampleRateHz"]
    if levels["status"] != "no-audio-stream" and (
            type(sample_rate) is not int or sample_rate <= 0):
        raise ValueError("audio onset source sample rate is invalid")

    candidates: list[dict[str, Any]] = []
    eligible, rejected_gaps, above_threshold, suppressed = 0, 0, 0, 0
    last_accepted: Fraction | None = None
    for prev, current in zip(frames, frames[1:]):
        prev_start = _fraction(prev["sourceSeconds"])
        current_start = _fraction(current["sourceSeconds"])
        prev_end = prev_start + _fraction(prev["decodedDurationSeconds"])
        current_end = current_start + _fraction(current["decodedDurationSeconds"])
        if (current_start <= prev_start or current_end <= current_start):
            raise ValueError("audio onset frames lack strictly increasing source PTS")
        if abs(current_start - prev_end) > Fraction(1, sample_rate):
            rejected_gaps += 1
            continue
        eligible += 1
        before = prev["rmsDbFs"]
        after = current["rmsDbFs"]
        peak = current["peakDbFs"]
        if after is None or peak is None or peak < min_peak_dbfs:
            continue
        floor_assisted = before is None
        rise = None if floor_assisted else round(after - before, 6)
        # The return from an unmeasurable floor is a separate kind of cue;
        # never fabricate a numeric dB rise to apply the normal threshold.
        if not floor_assisted and rise < min_rise_db:
            continue
        above_threshold += 1
        if last_accepted is not None and (
                current_start - last_accepted < Fraction(cooldown_ms, 1000)):
            suppressed += 1
            continue
        candidates.append({
            "id": f"onset-{len(candidates)+1:03d}",
            "anchorSourcePts": current["sourcePts"],
            "anchorSourceSeconds": current["sourceSeconds"],
            "supportWindow": {
                "startSeconds": prev["sourceSeconds"],
                "endSeconds": as_rational_dict(current_end),
            },
            "previousFrameSourcePts": prev["sourcePts"],
            "previousRmsDbFs": before,
            "currentRmsDbFs": after,
            "currentPeakDbFs": peak,
            "measuredRmsRiseDb": rise,
            "floorAssisted": floor_assisted,
            "signal": ("level-return-from-measurement-floor" if floor_assisted
                       else "candidate-rms-rise"),
            "interpretationStatus": "not-verified",
        })
        last_accepted = current_start

    return {
        "schemaVersion": AUDIO_ONSETS_VERSION,
        "sourceSha256": levels["sourceSha256"],
        "audioStreamIndex": levels["audioStreamIndex"],
        "sourceTimebase": levels["sourceTimebase"],
        "sampleRateHz": levels["sampleRateHz"],
        "scanWindowSeconds": levels["scanWindowSeconds"],
        "maxFrameBudget": levels["maxFrameBudget"],
        "status": ("no-audio-stream" if levels["status"] == "no-audio-stream"
                   else "source-pts-aligned-level-attack-candidates"),
        "method": METHOD,
        "settings": {"minRiseDb": float(min_rise_db),
                     "minPeakDbFs": float(min_peak_dbfs),
                     "cooldownMs": cooldown_ms},
        "observedFrameCount": len(frames),
        "eligibleAdjacentFramePairs": eligible,
        "discontinuityRejectedPairs": rejected_gaps,
        "aboveThresholdPairCount": above_threshold,
        "cooldownSuppressedPairCount": suppressed,
        "candidates": candidates,
        "qualityVerdict": "not-performed",
        "limits": LIMITS,
    }


def analyze_audio_onsets(source: Path, *, seconds: int = 10,
                         max_frames: int = 4096, min_rise_db: float = 12.0,
                         min_peak_dbfs: float = -40.0, cooldown_ms: int = 120,
                         ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
                         rights_status: str = "review-required") -> dict[str, Any]:
    """Decode source-checked audio frame levels then find conservative attacks."""
    # Validate tuning options before any file access or decoder subprocess.
    if (type(min_rise_db) not in (float, int) or not 1 <= min_rise_db <= 60 or
            type(min_peak_dbfs) not in (float, int) or not -100 <= min_peak_dbfs <= 0 or
            type(cooldown_ms) is not int or not 0 <= cooldown_ms <= 2000):
        raise ValueError("audio onset thresholds must be within documented bounds")
    levels = analyze_audio_levels(source, seconds=seconds, max_frames=max_frames,
                                  ffmpeg=ffmpeg, ffprobe=ffprobe,
                                  rights_status=rights_status)
    return audio_onsets_from_levels(levels, min_rise_db=min_rise_db,
                                    min_peak_dbfs=min_peak_dbfs,
                                    cooldown_ms=cooldown_ms)
