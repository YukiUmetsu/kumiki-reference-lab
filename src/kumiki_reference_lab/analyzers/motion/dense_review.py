"""Immutable visual QA of accepted dense image-plane flow on original PTS frames.

The gallery displays reported motion evidence. It never validates a physical
camera, surface identity, 3D reconstruction, or the quality of an animation.
"""

from __future__ import annotations

import hashlib
import html
import math
import os
import re
import tempfile
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.motion.review import _png_rgb, _serialized
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames
from kumiki_reference_lab.contracts.analysis import DENSE_FLOW_VERSION, DENSE_FLOW_REVIEW_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.analyze import _file_records


RENDER_REVISION = "source-pts-dense-grid-arrows-v1"
_REJECTIONS = {"low-texture", "out-of-frame", "roundtrip-inconsistent",
               "implausible-displacement", "appearance-inconsistent"}
_STATUSES = {"cut-boundary", "unobservable", "insufficient-grid-support", "flow-observed"}


def _finite(value: Any, name: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"dense review {name} must be finite numeric evidence")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"dense review {name} must be finite numeric evidence") from exc
    if not math.isfinite(number):
        raise ValueError(f"dense review {name} must be finite numeric evidence")
    return number


def _rational(value: Any, name: str, *, positive: bool = False) -> Fraction:
    if (not isinstance(value, dict) or set(value) != {"numerator", "denominator"} or
            type(value["numerator"]) is not int or type(value["denominator"]) is not int or
            value["denominator"] <= 0 or (positive and value["numerator"] <= 0)):
        raise ValueError(f"dense review {name} has invalid rational evidence")
    return Fraction(value["numerator"], value["denominator"])


def validate_dense_review_report(report: dict[str, Any]) -> tuple[
    int, int, list[dict[str, Any]], list[dict[str, Any]],
]:
    """Validate only fields used by the reviewer, including their relationships."""
    if (not isinstance(report, dict) or report.get("schemaVersion") != DENSE_FLOW_VERSION or
            not isinstance(report.get("sourceSha256"), str) or
            re.fullmatch(r"[a-f0-9]{64}", report["sourceSha256"]) is None or
            type(report.get("sourceStreamIndex")) is not int or
            report["sourceStreamIndex"] < 0):
        raise ValueError("dense review requires source-hashed dense-flow v1 evidence")
    analyzer = report.get("analyzer")
    resolution = analyzer.get("resolution") if isinstance(analyzer, dict) else None
    if not isinstance(resolution, dict):
        raise ValueError("dense review requires analysis resolution")
    width, height = resolution.get("width"), resolution.get("height")
    step = analyzer.get("gridStepPixels")
    seconds = report.get("scanWindowSeconds")
    if (type(width) is not int or not 64 <= width <= 240 or
            type(height) is not int or not 36 <= height <= 135 or
            type(step) is not int or not 8 <= step <= 24 or
            type(seconds) is not int or not 1 <= seconds <= 20):
        raise ValueError("dense review analysis grid or scan window is invalid")
    timebase = _rational(report.get("sourceTimebase"), "timebase", positive=True)
    samples, pairs = report.get("samples"), report.get("pairs")
    if (not isinstance(samples, list) or not 2 <= len(samples) <= 40 or
            not isinstance(pairs, list) or len(pairs) != len(samples) - 1):
        raise ValueError("dense review sample/pair count is invalid")
    cut_pts = report.get("cutCandidatePts")
    if (not isinstance(cut_pts, list) or len(cut_pts) > 10_000 or
            any(type(pts) is not int for pts in cut_pts) or
            cut_pts != sorted(set(cut_pts))):
        raise ValueError("dense review cut candidates are malformed")
    previous_pts, previous_ordinal = None, None
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("dense review sample is not an object")
        pts, ordinal = sample.get("sourcePts"), sample.get("sampleOrdinal")
        if (type(pts) is not int or type(ordinal) is not int or ordinal < 0 or
                (previous_pts is not None and pts <= previous_pts) or
                (previous_ordinal is not None and ordinal <= previous_ordinal) or
                _rational(sample.get("sourceSeconds"), "sample seconds") != pts * timebase):
            raise ValueError("dense review sample PTS/seconds/ordinal is inconsistent")
        previous_pts, previous_ordinal = pts, ordinal

    candidate_grid = len(range(step // 2, width - step // 2, step)) * len(
        range(step // 2, height - step // 2, step))
    for index, pair in enumerate(pairs):
        if (not isinstance(pair, dict) or
                pair.get("startPts") != samples[index]["sourcePts"] or
                pair.get("endPts") != samples[index + 1]["sourcePts"] or
                _rational(pair.get("deltaTimeSeconds"), "pair delta", positive=True) !=
                (pair["endPts"] - pair["startPts"]) * timebase or
                type(pair.get("status")) is not str or
                pair["status"] not in _STATUSES):
            raise ValueError("dense review pair contradicts source timecodes")
        vectors, rejected, candidates = (pair.get("vectors"), pair.get("rejected"),
                                         pair.get("candidateCount"))
        if (not isinstance(vectors, list) or len(vectors) > 512 or
                not isinstance(rejected, dict) or set(rejected) != _REJECTIONS or
                any(type(count) is not int or count < 0 for count in rejected.values()) or
                type(candidates) is not int or candidates < 0):
            raise ValueError("dense review grid accounting is malformed")
        cut = pair["status"] == "cut-boundary"
        crosses_cut = (bisect_right(cut_pts, pair["startPts"]) <
                       bisect_right(cut_pts, pair["endPts"]))
        if cut != crosses_cut:
            raise ValueError("dense review cut status contradicts cut candidates")
        if (cut and (candidates or vectors or any(rejected.values())) or
                not cut and candidates != candidate_grid or
                candidates != len(vectors) + sum(rejected.values()) or
                abs(_finite(pair.get("acceptedFraction"), "accepted fraction") -
                    (len(vectors) / candidates if candidates else 0.0)) > 0.000011):
            raise ValueError("dense review grid accounting contradicts measured evidence")
        expected_status = ("cut-boundary" if cut else
                           "flow-observed" if len(vectors) >= 5 else
                           "insufficient-grid-support" if vectors else "unobservable")
        if pair["status"] != expected_status:
            raise ValueError("dense review observed status contradicts accepted vectors")
        seen: set[tuple[int, int]] = set()
        for vector in vectors:
            if not isinstance(vector, dict):
                raise ValueError("dense review vector is not an object")
            x, y = vector.get("x"), vector.get("y")
            if (type(x) is not int or type(y) is not int or
                    x not in range(step // 2, width - step // 2, step) or
                    y not in range(step // 2, height - step // 2, step) or
                    (x, y) in seen):
                raise ValueError("dense review vector is not a unique grid observation")
            seen.add((x, y))
            dx, dy = _finite(vector.get("dx"), "dx"), _finite(vector.get("dy"), "dy")
            error = _finite(vector.get("roundtripErrorPixels"), "roundtrip error")
            if (math.hypot(dx, dy) > 24.0001 or not 5 <= x + dx < width - 6 or
                    not 5 <= y + dy < height - 6 or not 0 <= error <= 1.5):
                raise ValueError("dense review vector leaves the trusted image bounds")
    return width, height, samples, pairs


def select_dense_review_frames(samples: list[dict[str, Any]],
                               pairs: list[dict[str, Any]], limit: int) -> list[int]:
    """Prioritize cuts, weak support and high-support evidence; fill with even samples."""
    if type(limit) is not int or not 2 <= limit <= 12 or limit > len(samples):
        raise ValueError("dense review frame selection budget is invalid")
    priorities = [0, len(samples) - 1]
    priorities.extend(index for i, pair in enumerate(pairs)
                      if pair["status"] == "cut-boundary" for index in (i, i + 1))
    if pairs:
        weakest = min(range(len(pairs)), key=lambda i: pairs[i]["acceptedFraction"])
        strongest = max(range(len(pairs)), key=lambda i: pairs[i]["acceptedFraction"])
        priorities.extend((weakest + 1, strongest + 1))
    priorities.extend(round(i * (len(samples) - 1) / (limit - 1)) for i in range(limit))
    selected: list[int] = []
    for index in priorities:
        if index not in selected and len(selected) < limit:
            selected.append(index)
    return sorted(selected)


def render_dense_review_html(source_name: str, report: dict[str, Any],
                             frames: list[dict[str, Any]], width: int, height: int) -> str:
    """A self-contained human inspection surface; SVG uses only validated numbers."""
    h = lambda value: html.escape(str(value), quote=True)
    figures = []
    for frame in frames:
        index = frame["sampleIndex"]
        pair = report["pairs"][index - 1] if index else None
        arrows = []
        if pair and pair["status"] != "cut-boundary":
            for vector in pair["vectors"][:64]:
                x, y, dx, dy = (vector[k] for k in ("x", "y", "dx", "dy"))
                arrows.append(
                    f'<line x1="{x:.2f}" y1="{y:.2f}" '
                    f'x2="{x+dx:.2f}" y2="{y+dy:.2f}" '
                    'stroke="#7be8d1" stroke-width="1.15" stroke-linecap="round"/>'
                    f'<circle cx="{x+dx:.2f}" cy="{y+dy:.2f}" r="1.2" fill="#ffcd83"/>')
        summary = ("Opening sample: no preceding flow pair" if pair is None else
                   f'{pair["status"]} · {len(pair["vectors"])} accepted of '
                   f'{pair["candidateCount"]} grid cells')
        figures.append(
            '<figure><div class="viewport">'
            f'<img loading="lazy" src="{h(frame["path"])}" '
            f'alt="Original source frame at PTS {frame["sourcePts"]}">'
            f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
            'aria-hidden="true">' + ''.join(arrows) + '</svg></div>'
            f'<figcaption><strong>Sample {index + 1}</strong>'
            f'<span>PTS {frame["sourcePts"]} · {frame["seconds"]:.3f}s</span>'
            f'<small>{h(summary)}</small></figcaption></figure>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Kumiki dense flow evidence review</title><style>'
        ':root{color-scheme:dark;font-family:system-ui,-apple-system,sans-serif}'
        'body{background:#0a101b;color:#eef6ff;margin:0;padding:clamp(16px,3vw,40px)}'
        'header,main{max-width:1280px;margin:auto}h1{font-size:clamp(26px,4vw,42px);margin:12px 0}'
        'p{max-width:980px;color:#b9cbdc;line-height:1.6}.badge{color:#a9deeb;'
        'border:1px solid #476578;border-radius:999px;padding:5px 10px}'
        '.frames{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:28px 0}'
        'figure{margin:0;background:#152233;border:1px solid #364b61;border-radius:14px;overflow:hidden}'
        f'.viewport{{position:relative;aspect-ratio:{width}/{height};background:#111a25}}'
        '.viewport img,.viewport svg{position:absolute;inset:0;width:100%;height:100%;display:block}'
        '.viewport img{object-fit:fill}figcaption{display:flex;flex-wrap:wrap;gap:8px 18px;padding:12px}'
        'figcaption span{color:#c4d8e8;font-variant-numeric:tabular-nums}'
        'figcaption small{width:100%;color:#9db6cd}@media(max-width:780px){'
        '.frames{grid-template-columns:1fr}}</style></head><body><header>'
        '<span class="badge">Unreviewed · source-PTS verified</span>'
        '<h1>Dense image-plane motion on source frames</h1><p>' + h(source_name) +
        ' · ' + str(len(frames)) + ' decoded frames. Each teal line is a reported '
        'accepted grid displacement from the preceding sampled frame and ends at '
        'its measured destination on the displayed frame. Cut crossings show no arrows. '
        'These are candidate image-plane movements, not verified camera motion, '
        'surface identity, true occlusion, 3D geometry, or artistic quality.'
        '</p></header><main><section class="frames">' + ''.join(figures) +
        '</section></main></body></html>\n')


def _verify_existing(destination: Path, settings: dict[str, Any]) -> Path:
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError("dense review output is not a regular directory")
    manifest = _json_file(destination / "dense-flow-review.json", limit=262_144)
    actual = [entry for entry in _file_records(destination)
              if entry["path"] != "dense-flow-review.json"]
    expected = {"index.html", "dense-flow.json"} | {
        entry["path"] for entry in settings["selectedFrames"]}
    if (manifest.get("schemaVersion") != DENSE_FLOW_REVIEW_VERSION or
            manifest.get("settings") != settings or
            manifest.get("humanReviewStatus") != "unreviewed" or
            manifest.get("qualityVerdict") != "not-performed" or
            manifest.get("files") != actual or
            expected != {entry["path"] for entry in actual} or
            sha256_file(destination / "dense-flow.json") != settings["reportSha256"]):
        raise ValueError("dense review output is incomplete or modified")
    return destination / "index.html"


def build_dense_flow_review(
    source: Path, report_path: Path, output: Path, *, max_frames: int = 8,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> Path:
    if type(max_frames) is not int or not 2 <= max_frames <= 12:
        raise ValueError("dense review max_frames must be 2..12")
    source_signature, report_signature = file_signature(source), file_signature(report_path)
    report = _json_file(report_path, limit=4_194_304)
    width, height, samples, pairs = validate_dense_review_report(report)
    metadata = inspect_source(source, ffprobe=ffprobe)
    if (metadata["source"]["sha256"] != report["sourceSha256"] or
            metadata["video"]["streamIndex"] != report["sourceStreamIndex"] or
            metadata["video"]["sourceTimebase"] != report["sourceTimebase"]):
        raise ValueError("dense review source does not match report evidence")
    selected = select_dense_review_frames(samples, pairs, min(max_frames, len(samples)))
    frame_settings = [{"sampleIndex": index, "sourcePts": samples[index]["sourcePts"],
                       "path": f"frames/frame-{position:03d}.png"}
                      for position, index in enumerate(selected)]
    report_bytes = report_path.read_bytes()
    require_unchanged(report_path, report_signature)
    settings = {
        "sourceSha256": report["sourceSha256"],
        "reportSha256": hashlib.sha256(report_bytes).hexdigest(),
        "sourceStreamIndex": report["sourceStreamIndex"],
        "sourceTimebase": report["sourceTimebase"],
        "scanWindowSeconds": report["scanWindowSeconds"],
        "selectedFrames": frame_settings, "maxFrames": max_frames,
        "analysisResolution": {"width": width, "height": height},
        "ffmpeg": ffmpeg, "ffprobe": ffprobe, "renderRevision": RENDER_REVISION,
    }
    digest = hashlib.sha256(_serialized(settings)).hexdigest()[:16]
    destination = output / f"dense-flow-review-{report['sourceSha256'][:12]}-{digest}"
    if destination.exists() or destination.is_symlink():
        require_unchanged(source, source_signature)
        return _verify_existing(destination, settings)
    timebase = Fraction(**report["sourceTimebase"])
    decoded = read_rgb_frames(
        source, report["sourceStreamIndex"],
        [samples[index]["sampleOrdinal"] for index in selected],
        [samples[index]["sourcePts"] for index in selected],
        timebase=timebase, seconds=report["scanWindowSeconds"],
        width=width, height=height, ffmpeg=ffmpeg,
    )
    require_unchanged(source, source_signature)
    require_unchanged(report_path, report_signature)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".dense-review-", dir=output) as temporary:
        staging = Path(temporary)
        (staging / "frames").mkdir()
        for item, pixels in zip(frame_settings, decoded, strict=True):
            (staging / item["path"]).write_bytes(_png_rgb(pixels, width, height))
        frames = [{**item, "seconds": float(item["sourcePts"] * timebase)}
                  for item in frame_settings]
        (staging / "index.html").write_text(
            render_dense_review_html(metadata["source"]["fileName"], report,
                                     frames, width, height), encoding="utf-8")
        (staging / "dense-flow.json").write_bytes(report_bytes)
        (staging / "dense-flow-review.json").write_bytes(_serialized({
            "schemaVersion": DENSE_FLOW_REVIEW_VERSION,
            "settings": settings, "humanReviewStatus": "unreviewed",
            "qualityVerdict": "not-performed", "files": _file_records(staging),
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
