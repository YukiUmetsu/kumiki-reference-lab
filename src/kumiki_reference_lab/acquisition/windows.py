"""Window planning, per-window measurement, probe summarisation, evidence assembly."""

from __future__ import annotations

import math
import statistics
from pathlib import Path
from typing import Any, Callable, Iterable

from kumiki_reference_lab.analyzers.appearance.source_visual_probe import (
    analyze_source_visual_window,
)

from .probe import ANALYZER_RIGHTS_STATUS, as_int, finite_float
from .store import utc_now

MAX_WINDOWS = 20
MAX_WINDOW_SECONDS = 30
# Coverage deliberately stops short of the trailing decile of the runtime.
_TRAILING_DECILE = 0.9
_MAX_USABLE_SECONDS = 3600.0


def plan_windows(
    duration_seconds: float, *, count: int, seconds: int,
) -> tuple[int, int, list[int], float]:
    """Plan evenly spread non-overlapping windows, skipping the trailing 10%.

    The first window always starts at 0. Returns ``(window seconds, count,
    starts, sampled fraction of runtime)``.
    """
    if (type(count) is not int or not 1 <= count <= MAX_WINDOWS
            or type(seconds) is not int or not 1 <= seconds <= MAX_WINDOW_SECONDS):
        raise ValueError("window duration/count budgets are out of bounds")
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("source reported invalid/nonpositive duration")
    usable_end = min(duration_seconds * _TRAILING_DECILE, _MAX_USABLE_SECONDS)
    span = min(seconds, int(usable_end))
    if span < 1:
        raise ValueError("source is too short for a measurable window")
    window_count = min(count, max(1, int(usable_end) // span))
    stride = (0 if window_count == 1
              else int((usable_end - span) // (window_count - 1)))
    if window_count > 1 and stride < span:
        raise ValueError("computed media windows would overlap")
    starts = [index * stride for index in range(window_count)]
    if starts and starts[0] != 0:
        raise ValueError("first measurement window must start at zero")
    sampled = span * window_count
    return span, window_count, starts, round(
        min(1.0, sampled / duration_seconds), 6)


def summarize_probes(
    probes: Iterable[dict[str, Any]], *, sampled_seconds: float,
) -> dict[str, Any]:
    """Derive record summary numbers strictly from embedded probe payloads."""
    cuts = 0
    windows_with_cuts = 0
    sampled_frames = 0
    luma: list[float] = []
    saturation: list[float] = []
    deltas_per_second: list[float] = []
    for probe in probes:
        if not isinstance(probe, dict):
            continue
        summary = probe.get("sampledWindowSummary")
        if isinstance(summary, dict):
            cut_count = as_int(
                summary.get("cutCandidateCountBetweenFirstAndLastSample"))
            if cut_count is not None:
                cuts += cut_count
                windows_with_cuts += int(cut_count > 0)
            luma_value = finite_float(summary.get("meanSampledDisplayLumaProxy"))
            if luma_value is not None:
                luma.append(luma_value)
            saturation_value = finite_float(
                summary.get("meanSampledSaturationProxy"))
            if saturation_value is not None:
                saturation.append(saturation_value)
        frames = probe.get("sampledFrames")
        if isinstance(frames, list):
            sampled_frames += len(frames)
        pairs = probe.get("sampledFramePairs")
        if isinstance(pairs, list):
            for pair in pairs:
                if not isinstance(pair, dict):
                    continue
                value = finite_float(
                    pair.get("meanAbsoluteDisplayRgbDeltaPerSecond"))
                if value is not None:
                    deltas_per_second.append(value)
    rate = (round(cuts * 60.0 / sampled_seconds, 6)
            if sampled_seconds > 0 else None)
    return {
        "cutCandidates": cuts,
        "cutCandidateRatePerMinute": rate,
        "meanDisplayLuma": round(statistics.mean(luma), 6) if luma else None,
        "meanSaturation": (round(statistics.mean(saturation), 6)
                           if saturation else None),
        "meanWithinShotRgbDeltaPerSecond": (
            round(statistics.mean(deltas_per_second), 6)
            if deltas_per_second else None),
        "sampledFrames": sampled_frames,
        "windowsWithCuts": windows_with_cuts,
    }


def measure_windows(
    source: Path, *, duration_seconds: float, window_count: int,
    window_seconds: int, image_translation: bool,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = ANALYZER_RIGHTS_STATUS,
    max_samples: int = 12, frame_width: int = 160, frame_height: int = 90,
    analyze: Callable[..., dict[str, Any]] = analyze_source_visual_window,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Measure evenly spread source-PTS windows; return ``(coverage, windows)``.

    ``analyze`` is injectable so an offline caller can substitute the source
    visual probe without touching ffmpeg.
    """
    span, count, starts, fraction = plan_windows(
        duration_seconds, count=window_count, seconds=window_seconds)
    windows: list[dict[str, Any]] = []
    for start in starts:
        probe = analyze(
            source, start_seconds=start, seconds=span, max_samples=max_samples,
            width=frame_width, height=frame_height,
            image_translation=image_translation,
            rights_status=rights_status, ffmpeg=ffmpeg, ffprobe=ffprobe,
        )
        windows.append({
            "startSeconds": start,
            "endSeconds": start + span,
            "probe": probe,
        })
    coverage = {
        "windowsMeasured": count,
        "windowSeconds": span,
        "sampledSeconds": span * count,
        "fractionOfRuntime": fraction,
        "fullRuntimeMeasured": False,
        "note": "evenly spread source-PTS windows, not full-film review",
    }
    return coverage, windows


def build_video_evidence(
    *, source: dict[str, Any], coverage: dict[str, Any],
    windows: list[dict[str, Any]], method: str, provider: str,
    video_url: str | None, rights_basis: str, rights_note: str,
    schema_version: str, evidence_status: str, limits: Iterable[str],
    generated_at: str | None = None, rights_status: str = "review-required",
) -> dict[str, Any]:
    """Assemble the neutral video evidence payload (no subject identity fields).

    The caller merges its own subject fields (catalog identity, URLs, scores)
    around this payload and supplies the schema, evidence-status string, and
    limits list. Media is never retained: ``mediaRetained`` is fixed ``False``
    so a caller cannot accidentally claim otherwise.
    """
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError("evidence schema version must be a non-empty string")
    if not isinstance(evidence_status, str) or not evidence_status.strip():
        raise ValueError("evidence status must be a non-empty string")
    if not isinstance(method, str) or not method.strip():
        raise ValueError("acquisition method must be a non-empty string")
    if not isinstance(provider, str) or not provider.strip():
        raise ValueError("acquisition provider must be a non-empty string")
    if not isinstance(rights_basis, str) or not rights_basis.strip():
        raise ValueError("rights basis must be a non-empty string")
    if not isinstance(rights_note, str) or not rights_note.strip():
        raise ValueError("rights note must be a non-empty string")
    if not isinstance(coverage.get("sampledSeconds"), (int, float)):
        raise ValueError("coverage must report sampled seconds")
    summary = summarize_probes(
        [window["probe"] for window in windows],
        sampled_seconds=float(coverage["sampledSeconds"]),
    )
    return {
        "schemaVersion": schema_version,
        "source": source,
        "acquisition": {
            "provider": provider,
            "videoUrl": video_url,
            "method": method,
            "mediaRetained": False,
            "attestation": {
                "rightsBasis": rights_basis,
                "note": rights_note,
            },
        },
        "coverage": coverage,
        "windows": windows,
        "summary": summary,
        "evidenceStatus": evidence_status,
        "rightsStatus": rights_status,
        "limits": list(limits),
        "generatedAt": generated_at or utc_now(),
    }
