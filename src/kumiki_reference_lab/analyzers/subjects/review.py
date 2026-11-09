"""Immutable, source-verified visual review of bounded seeded ROI observations."""

from __future__ import annotations

import hashlib
import html
import math
import os
import re
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.motion.review import _png_rgb, _serialized
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames
from kumiki_reference_lab.contracts.analysis import ROI_REVIEW_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.analyze import _file_records


_RENDER_REVISION = "observed-roi-box-overlay-v1"
_KNOWN_TRACK_VERSIONS = {"kumiki.roi-track.v1", "kumiki.roi-track.v2"}
_VISIBLE = {"seeded", "manual-reseed", "matched-template"}
_STOPPED = {"lost-low-correlation", "ambiguous-multiple-matches",
            "unobservable-low-texture", "out-of-frame", "cut-boundary",
            "not-tracked-after-loss", "not-tracked-after-cut"}
_COLORS = ("#6be5ce", "#f7c17a", "#b6a7ff", "#f29eba", "#9acaff")


def _bounded_float(value: Any) -> float:
    if type(value) not in (int, float):
        raise ValueError("ROI review box coordinates must be finite numbers")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError("ROI review box coordinates must be finite numbers") from exc
    if not math.isfinite(number):
        raise ValueError("ROI review box coordinates must be finite numbers")
    return number


def _validate_report(report: dict[str, Any]) -> tuple[int, int, list[dict[str, Any]]]:
    version = report.get("schemaVersion")
    if version not in _KNOWN_TRACK_VERSIONS:
        raise ValueError("ROI review requires a supported ROI track report")
    if (not isinstance(report.get("sourceSha256"), str) or
            not re.fullmatch(r"[a-f0-9]{64}", report["sourceSha256"])):
        raise ValueError("ROI review requires a source SHA-256")
    analyzer = report.get("analyzer")
    size = analyzer.get("analysisResolution") if isinstance(analyzer, dict) else None
    if not isinstance(size, dict):
        raise ValueError("ROI review lacks analysis resolution")
    width, height = size.get("width"), size.get("height")
    if (type(width) is not int or type(height) is not int or
            not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("ROI review analysis resolution is invalid")
    radius = analyzer.get("searchRadiusPixels")
    if type(radius) is not int or not 1 <= radius <= 48:
        raise ValueError("ROI review search radius is invalid")
    seconds = report.get("scanWindowSeconds")
    if type(seconds) is not int or not 1 <= seconds <= 30:
        raise ValueError("ROI review scan window is invalid")
    observations = report.get("observations")
    if not isinstance(observations, list) or not 2 <= len(observations) <= 120:
        raise ValueError("ROI review observations are missing or out of bounds")
    rational = report.get("sourceTimebase")
    if (not isinstance(rational, dict) or
            set(rational) != {"numerator", "denominator"} or
            type(rational.get("numerator")) is not int or
            type(rational.get("denominator")) is not int or
            rational["numerator"] <= 0 or rational["denominator"] <= 0):
        raise ValueError("ROI review source timebase is invalid")
    timebase = Fraction(**rational)
    if type(report.get("sourceStreamIndex")) is not int or report["sourceStreamIndex"] < 0:
        raise ValueError("ROI review source stream index is invalid")
    v2 = version == "kumiki.roi-track.v2"
    anchors: list[int] = []
    specs: list[dict[str, Any]] = []
    if v2:
        specs = analyzer.get("manualReseeds")
        if (not isinstance(specs, list) or not 1 <= len(specs) <= 16 or
                analyzer.get("identityLinkStatus") != "not-established"):
            raise ValueError("ROI review v2 requires explicit independent manual segments")
        if any(not isinstance(item, dict) or type(item.get("sourcePts")) is not int
               for item in specs):
            raise ValueError("ROI review v2 manual reseeds are invalid")
        anchors = [item["sourcePts"] for item in specs]
        if anchors != sorted(set(anchors)):
            raise ValueError("ROI review v2 manual PTS anchors are not increasing")
    previous_pts = previous_ordinal = None
    segment = 0
    observed_anchors: list[int] = []
    origin: tuple[int, int] | None = None
    previous_position: tuple[int, int, int, int] | None = None
    for index, obs in enumerate(observations):
        if not isinstance(obs, dict):
            raise ValueError("ROI review observation is not an object")
        pts, ordinal, status = obs.get("sourcePts"), obs.get("sampleOrdinal"), obs.get("status")
        if (type(pts) is not int or type(ordinal) is not int or ordinal < 0 or
                (previous_pts is not None and pts <= previous_pts) or
                (previous_ordinal is not None and ordinal <= previous_ordinal)):
            raise ValueError("ROI review source PTS or ordinal is nonmonotonic")
        previous_pts, previous_ordinal = pts, ordinal
        source_seconds = obs.get("sourceSeconds")
        if (not isinstance(source_seconds, dict) or
                set(source_seconds) != {"numerator", "denominator"} or
                type(source_seconds.get("numerator")) is not int or
                type(source_seconds.get("denominator")) is not int or
                source_seconds["denominator"] <= 0 or
                Fraction(**source_seconds) != pts * timebase):
            raise ValueError("ROI review observation seconds disagree with source PTS")
        if status not in _VISIBLE | _STOPPED:
            raise ValueError("ROI review observation status is not recognized")
        if not v2 and (status == "manual-reseed" or "segmentIndex" in obs):
            raise ValueError("ROI review v1 cannot contain manual segments")
        if (index == 0 and status != "seeded") or (index > 0 and status == "seeded"):
            raise ValueError("ROI review has an invalid initial seed sequence")
        has_position = status in _VISIBLE
        if ((obs.get("boxPixels") is None) != (not has_position) or
                (obs.get("boxNormalized") is None) != (not has_position)):
            raise ValueError("ROI review observation has an unverified position")
        if has_position:
            pix, norm = obs["boxPixels"], obs["boxNormalized"]
            if (not isinstance(pix, dict) or not isinstance(norm, dict) or
                    set(pix) != {"x", "y", "width", "height"} or
                    set(norm) != {"x", "y", "width", "height"} or
                    any(type(pix[key]) is not int for key in pix)):
                raise ValueError("ROI review visible box is malformed")
            x, y, w, h = (pix[key] for key in ("x", "y", "width", "height"))
            if not (0 <= x < width and 0 <= y < height and 1 <= w <= width - x
                    and 1 <= h <= height - y):
                raise ValueError("ROI review box leaves the analysis image")
            for key, expected in (("x", x/width), ("y", y/height),
                                  ("width", w/width), ("height", h/height)):
                if abs(_bounded_float(norm.get(key)) - expected) > 0.000001:
                    raise ValueError("ROI review normalized box contradicts image pixels")
            if status in {"seeded", "manual-reseed"}:
                declared = (analyzer.get("seedBoxNormalized") if status == "seeded" else
                            next((item.get("box") for item in specs
                                  if item["sourcePts"] == pts), None))
                if (not isinstance(declared, list) or len(declared) != 4 or
                        any(not 0 <= _bounded_float(v) <= 1 for v in declared) or
                        [round(declared[0] * width), round(declared[1] * height),
                         round(declared[2] * width), round(declared[3] * height)] !=
                        [x, y, w, h]):
                    raise ValueError("ROI review manual seed box disagrees with observed pixels")
                origin = x, y
            elif (previous_position is None or
                  abs(x - previous_position[0]) > radius or
                  abs(y - previous_position[1]) > radius or
                  (w, h) != previous_position[2:]):
                raise ValueError("ROI review matched box violates local search radius or track continuity")
            displacement = obs.get("displacementPixels")
            if (not isinstance(displacement, dict) or origin is None or
                    displacement != {"dx": x - origin[0], "dy": y - origin[1]}):
                raise ValueError("ROI review displacement contradicts observed box")
            previous_position = x, y, w, h
        else:
            if obs.get("displacementPixels") is not None:
                raise ValueError("ROI review hidden observation invents displacement")
            previous_position = None
        if v2:
            if index == 0 and status != "seeded":
                raise ValueError("ROI review v2 must start with segment zero")
            if status == "manual-reseed":
                segment += 1
                observed_anchors.append(pts)
            expected_segment = segment if has_position else None
            actual_segment = obs.get("segmentIndex")
            if ("segmentIndex" not in obs or
                    (has_position and type(actual_segment) is not int) or
                    actual_segment != expected_segment):
                raise ValueError("ROI review segment index contradicts visible evidence")
    if v2 and observed_anchors != anchors:
        raise ValueError("ROI review manual seed PTS disagree with observations")
    return width, height, observations


def _pick_frames(observations: list[dict[str, Any]], limit: int) -> list[int]:
    count = len(observations)
    priorities = [0, count - 1]
    for index, obs in enumerate(observations):
        if obs["status"] in (_VISIBLE | _STOPPED) - {"matched-template", "not-tracked-after-loss",
                                                       "not-tracked-after-cut"}:
            priorities.extend((max(0, index - 1), index, min(count - 1, index + 1)))
    priorities.extend(round(i * (count - 1) / (min(limit, count) - 1))
                      for i in range(min(limit, count)))
    selected = []
    for index in priorities:
        if index not in selected and len(selected) < limit:
            selected.append(index)
    return sorted(selected)


def _html_view(source_name: str, frames: list[dict[str, Any]],
               width: int, height: int, *, v2: bool) -> str:
    figures = []
    for item in frames:
        obs = item["observation"]
        status = obs["status"]
        segment = obs.get("segmentIndex", 0)
        color = _COLORS[(segment or 0) % len(_COLORS)]
        box = obs["boxPixels"]
        overlay = (f'<rect x="{box["x"]:.2f}" y="{box["y"]:.2f}" '
                   f'width="{box["width"]:.2f}" height="{box["height"]:.2f}" '
                   f'stroke="{color}" fill="{color}" fill-opacity="0.09" '
                   'stroke-width="1.6" vector-effect="non-scaling-stroke"/>') if box else ""
        status_text = html.escape(status, quote=True)
        secondary = (f'segment {segment} · reported box' if box and v2 else
                     'reported box' if box else 'no reported box')
        figures.append(
            '<figure><div class="viewport">'
            f'<img loading="lazy" src="{html.escape(item["path"], quote=True)}" '
            f'alt="Source frame at PTS {obs["sourcePts"]}">'
            f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
            f'aria-hidden="true">{overlay}</svg></div>'
            f'<figcaption><strong>Sample {item["sampleIndex"] + 1}</strong>'
            f'<span>PTS {obs["sourcePts"]} · {item["seconds"]:.3f}s</span>'
            f'<small>{status_text} · {secondary}</small></figcaption></figure>')
    claim = ('Manual segments are not verified as the same physical object.' if v2 else
             'A seeded region is not a verified physical object identity.')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Kumiki ROI visual review</title><style>'
        ':root{color-scheme:dark;font-family:system-ui,-apple-system,sans-serif}'
        'body{background:#090f19;color:#edf6ff;margin:0;padding:clamp(16px,3vw,40px)}'
        'header,main{max-width:1260px;margin:auto}h1{font-size:clamp(28px,4vw,44px);margin:9px 0}'
        'p{color:#b9cadd;max-width:940px;line-height:1.6}.badge{display:inline-block;'
        'color:#b9e5ef;border:1px solid #486478;border-radius:999px;padding:5px 10px}'
        '.frames{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;'
        'margin:25px 0}figure{margin:0;background:#142030;border:1px solid #344b61;'
        'border-radius:13px;overflow:hidden}.viewport{position:relative;'
        f'aspect-ratio:{width}/{height};background:#111a25}}'
        '.viewport img,.viewport svg{position:absolute;inset:0;width:100%;height:100%;display:block}'
        '.viewport img{object-fit:fill}figcaption{display:flex;flex-wrap:wrap;gap:7px 17px;'
        'align-items:center;padding:12px 14px}figcaption span{color:#b9cadb;font-variant-numeric:tabular-nums}'
        'figcaption small{color:#9eb6cd;width:100%}@media(max-width:780px){'
        '.frames{grid-template-columns:1fr}}</style></head><body><header>'
        '<span class="badge">Unreviewed · source PTS verified</span>'
        '<h1>ROI observations on original frames</h1><p>' +
        html.escape(source_name, quote=True) + ' · ' + str(len(frames)) +
        ' decoded frames. Colored rectangles indicate tracker-reported image regions, '
        'not independently verified matches or reconstructed geometry. '
        'Missing or occluded regions have no boxes. ' +
        html.escape(claim) + ' No artistic approval or automatic re-identification.'
        '</p></header><main><section class="frames">' + ''.join(figures) +
        '</section></main></body></html>\n')


def _verify_existing(destination: Path, settings: dict[str, Any]) -> Path:
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError("ROI review destination is not a regular directory")
    manifest = _json_file(destination / "roi-review.json", limit=262_144)
    recorded = manifest.get("files")
    actual = [entry for entry in _file_records(destination) if entry["path"] != "roi-review.json"]
    expected = {"index.html", "roi-track.json"} | {
        entry["path"] for entry in settings["selectedFrames"]}
    if (manifest.get("schemaVersion") != ROI_REVIEW_VERSION or
            manifest.get("settings") != settings or
            manifest.get("humanReviewStatus") != "unreviewed" or
            manifest.get("qualityVerdict") != "not-performed" or
            actual != recorded or expected != {item["path"] for item in actual} or
            sha256_file(destination / "roi-track.json") != settings["reportSha256"]):
        raise ValueError("ROI review destination is incomplete or modified")
    return destination / "index.html"


def build_roi_review(
    source: Path, report_path: Path, output: Path, *, max_frames: int = 8,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> Path:
    """Publish an immutable offline review; never link boxes across missing frames."""
    if type(max_frames) is not int or not 2 <= max_frames <= 12:
        raise ValueError("ROI review max_frames must be 2..12")
    source_signature, report_signature = file_signature(source), file_signature(report_path)
    report = _json_file(report_path, limit=1_048_576)
    width, height, observations = _validate_report(report)
    metadata = inspect_source(source, ffprobe=ffprobe)
    if (metadata["source"]["sha256"] != report["sourceSha256"] or
            metadata["video"]["streamIndex"] != report.get("sourceStreamIndex") or
            metadata["video"]["sourceTimebase"] != report.get("sourceTimebase")):
        raise ValueError("ROI review source does not match ROI track evidence")
    selected = _pick_frames(observations, min(max_frames, len(observations)))
    frame_settings = [{"sampleIndex": index, "sourcePts": observations[index]["sourcePts"],
                       "path": f"frames/frame-{position:03d}.png"}
                      for position, index in enumerate(selected)]
    report_bytes = report_path.read_bytes()
    require_unchanged(report_path, report_signature)
    settings = {
        "sourceSha256": report["sourceSha256"],
        "reportSha256": hashlib.sha256(report_bytes).hexdigest(),
        "sourceStreamIndex": report["sourceStreamIndex"],
        "sourceTimebase": report["sourceTimebase"],
        "sourceTrackVersion": report["schemaVersion"],
        "scanWindowSeconds": report["scanWindowSeconds"],
        "selectedFrames": frame_settings, "maxFrames": max_frames,
        "analysisResolution": {"width": width, "height": height},
        "ffmpeg": ffmpeg, "ffprobe": ffprobe,
        "renderRevision": _RENDER_REVISION,
    }
    destination_hash = hashlib.sha256(_serialized(settings)).hexdigest()[:16]
    destination = output / f"roi-review-{report['sourceSha256'][:12]}-{destination_hash}"
    if destination.exists() or destination.is_symlink():
        require_unchanged(source, source_signature)
        return _verify_existing(destination, settings)
    timebase = Fraction(**report["sourceTimebase"])
    decoded = read_rgb_frames(
        source, report["sourceStreamIndex"],
        [observations[index]["sampleOrdinal"] for index in selected],
        [observations[index]["sourcePts"] for index in selected],
        timebase=timebase, seconds=report["scanWindowSeconds"],
        width=width, height=height, ffmpeg=ffmpeg,
    )
    require_unchanged(source, source_signature)
    require_unchanged(report_path, report_signature)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".roi-review-", dir=output) as temporary:
        staging = Path(temporary)
        (staging / "frames").mkdir()
        for item, pixels in zip(frame_settings, decoded, strict=True):
            (staging / item["path"]).write_bytes(_png_rgb(pixels, width, height))
        view_frames = [
            {**item, "observation": observations[item["sampleIndex"]],
             "seconds": float(item["sourcePts"] * timebase)}
            for item in frame_settings]
        (staging / "index.html").write_text(
            _html_view(metadata["source"]["fileName"], view_frames, width, height,
                       v2=report["schemaVersion"] == "kumiki.roi-track.v2"), encoding="utf-8")
        (staging / "roi-track.json").write_bytes(report_bytes)
        (staging / "roi-review.json").write_bytes(_serialized({
            "schemaVersion": ROI_REVIEW_VERSION, "settings": settings,
            "humanReviewStatus": "unreviewed", "qualityVerdict": "not-performed",
            "files": _file_records(staging),
        }))
        require_unchanged(source, source_signature)
        require_unchanged(report_path, report_signature)
        if destination.exists() or destination.is_symlink():
            return _verify_existing(destination, settings)
        try:
            os.rename(staging, destination)
        except FileExistsError:
            return _verify_existing(destination, settings)
    return destination / "index.html"
