"""Offline source-PTS-verified visual QA for experimental sparse image motion."""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import struct
import tempfile
import zlib
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames
from kumiki_reference_lab.contracts.analysis import SPARSE_FLOW_REVIEW_VERSION, SPARSE_FLOW_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.analyze import _file_records


RENDER_REVISION = "source-pts-overlay-v1"
COLORS = ("#8be9cf", "#f9bc80", "#98b8ff", "#e3a6eb", "#ebdc8b",
          "#91e2f8", "#ff9fba", "#a8e0a0", "#cec2ff", "#f5aa81")


def _serialized(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _png_rgb(raw: bytes, width: int, height: int) -> bytes:
    """Lossless 8-bit RGB PNG using only bounded standard-library encoding."""
    stride = width * 3
    if len(raw) != stride * height:
        raise ValueError("motion review frame has invalid RGB buffer length")
    scanlines = b"".join(b"\0" + raw[i * stride:(i + 1) * stride]
                         for i in range(height))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload +
                struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))

    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(scanlines, level=6)) +
            chunk(b"IEND", b""))


def _number(value: Any, *, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"motion review {label} must be finite numeric evidence")
    return float(value)


def _validate(report: dict[str, Any]) -> tuple[
    int, int, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]],
]:
    if (report.get("schemaVersion") != SPARSE_FLOW_VERSION or
            not isinstance(report.get("sourceSha256"), str) or
            re.fullmatch(r"[a-f0-9]{64}", report["sourceSha256"]) is None):
        raise ValueError("motion review requires a sparse-flow v1 source hash")
    analyzer = report.get("analyzer")
    resolution = analyzer.get("resolution") if isinstance(analyzer, dict) else None
    if not isinstance(resolution, dict):
        raise ValueError("motion review lacks image resolution")
    width, height = resolution.get("width"), resolution.get("height")
    if (type(width) is not int or not 64 <= width <= 240 or
            type(height) is not int or not 36 <= height <= 135):
        raise ValueError("motion review has invalid bounded analysis resolution")
    samples, pairs = report.get("samples"), report.get("pairs")
    if (not isinstance(samples, list) or not 2 <= len(samples) <= 40 or
            not isinstance(pairs, list) or len(pairs) != len(samples) - 1):
        raise ValueError("motion review has invalid sample/pair count")
    previous_pts, previous_ordinal = None, None
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("motion review sample must be an object")
        pts, ordinal = sample.get("sourcePts"), sample.get("sampleOrdinal")
        if (type(pts) is not int or type(ordinal) is not int or ordinal < 0 or
                (previous_pts is not None and pts <= previous_pts) or
                (previous_ordinal is not None and ordinal <= previous_ordinal)):
            raise ValueError("motion review sample PTS or ordinal is not increasing")
        previous_pts, previous_ordinal = pts, ordinal
    for index, pair in enumerate(pairs):
        if (not isinstance(pair, dict) or
                pair.get("startPts") != samples[index]["sourcePts"] or
                pair.get("endPts") != samples[index + 1]["sourcePts"] or
                not isinstance(pair.get("vectors"), list) or len(pair["vectors"]) > 64):
            raise ValueError("motion review pair contradicts sampled source PTS")
        if pair.get("status") == "cut-boundary" and pair["vectors"]:
            raise ValueError("motion review cannot show vectors across a hard cut")
        for vector in pair["vectors"]:
            if not isinstance(vector, dict):
                raise ValueError("motion review vector must be an object")
            x = _number(vector.get("x"), label="point x")
            y = _number(vector.get("y"), label="point y")
            dx = _number(vector.get("dx"), label="vector dx")
            dy = _number(vector.get("dy"), label="vector dy")
            if not (0 <= x < width and 0 <= y < height and
                    0 <= x + dx < width and 0 <= y + dy < height):
                raise ValueError("motion review vector leaves the analyzed image")
    temporal = report.get("temporalTracklets")
    if not isinstance(temporal, dict) or not isinstance(temporal.get("tracklets"), list):
        raise ValueError("motion review requires temporal tracklet evidence")
    tracklets = temporal["tracklets"]
    if len(tracklets) > 2496:
        raise ValueError("motion review tracklet count exceeds budget")
    seen: set[str] = set()
    claimed_vectors: set[tuple[int, int]] = set()
    for track in tracklets:
        if not isinstance(track, dict):
            raise ValueError("motion review tracklet must be an object")
        track_id, observations = track.get("id"), track.get("observations")
        if (not isinstance(track_id, str) or
                re.fullmatch(r"tracklet-[0-9]{4,}", track_id) is None or
                track_id in seen or not isinstance(observations, list) or
                not 2 <= len(observations) <= len(pairs) or
                track.get("pairCount") != len(observations)):
            raise ValueError("motion review tracklet has invalid identity or observations")
        seen.add(track_id)
        last_pair_index = -1
        for obs in observations:
            if not isinstance(obs, dict):
                raise ValueError("motion review observation must be an object")
            pi, vi = obs.get("pairIndex"), obs.get("vectorIndex")
            if (type(pi) is not int or type(vi) is not int or
                    not 0 <= pi < len(pairs) or
                    not 0 <= vi < len(pairs[pi]["vectors"]) or
                    (last_pair_index >= 0 and pi != last_pair_index + 1)):
                raise ValueError("motion review tracklet references nonadjacent evidence")
            if (pi, vi) in claimed_vectors:
                raise ValueError("motion review vector is claimed by multiple tracklets")
            claimed_vectors.add((pi, vi))
            pair, vector = pairs[pi], pairs[pi]["vectors"][vi]
            start, end = obs.get("startPixels"), obs.get("endPixels")
            if (not isinstance(start, dict) or not isinstance(end, dict) or
                    obs.get("startPts") != pair["startPts"] or
                    obs.get("endPts") != pair["endPts"] or
                    start != {"x": vector["x"], "y": vector["y"]} or
                    end != {"x": vector["x"] + vector["dx"],
                            "y": vector["y"] + vector["dy"]}):
                raise ValueError("motion review tracklet observation differs from source pair")
            last_pair_index = pi
    return width, height, samples, pairs, tracklets


def _selection(count: int, tracks: list[dict[str, Any]], limit: int,
               *, cut_pair_indices: list[int] | None = None) -> list[int]:
    priorities = [0, count - 1]
    for index in cut_pair_indices or []:
        priorities.extend((index, index + 1))
    for track in tracks:
        observations = track["observations"]
        priorities.extend((observations[0]["pairIndex"],
                           observations[-1]["pairIndex"] + 1))
    priorities.extend(round(index * (count - 1) / (limit - 1))
                      for index in range(limit))
    selected = []
    for index in priorities:
        if index not in selected and len(selected) < limit:
            selected.append(index)
    return sorted(selected)


def _render_html(
    source_name: str, report: dict[str, Any], frames: list[dict[str, Any]],
    tracks: list[dict[str, Any]], width: int, height: int, total_tracks: int,
) -> str:
    def h(value: object) -> str:
        return html.escape(str(value), quote=True)

    track_color = {track["id"]: COLORS[i % len(COLORS)]
                   for i, track in enumerate(tracks)}
    figures = []
    pairs = report["pairs"]
    for frame in frames:
        sample_index = frame["sampleIndex"]
        pair_index = sample_index - 1
        arrows = []
        linked_count = 0
        if pair_index >= 0:
            for track in tracks:
                for observation in track["observations"]:
                    if observation["pairIndex"] != pair_index:
                        continue
                    start, end = observation["startPixels"], observation["endPixels"]
                    color = track_color[track["id"]]
                    arrows.append(
                        f'<line x1="{start["x"]:.2f}" y1="{start["y"]:.2f}" '
                        f'x2="{end["x"]:.2f}" y2="{end["y"]:.2f}" '
                        f'stroke="{color}" stroke-width="1.1" stroke-linecap="round"/>'
                        f'<circle cx="{end["x"]:.2f}" cy="{end["y"]:.2f}" '
                        f'r="1.5" fill="{color}" stroke="#08101b" stroke-width=".45"/>')
                    linked_count += 1
            if not tracks:
                for vector in pairs[pair_index]["vectors"][:24]:
                    x, y = vector["x"], vector["y"]
                    arrows.append(
                        f'<line x1="{x:.2f}" y1="{y:.2f}" '
                        f'x2="{x+vector["dx"]:.2f}" y2="{y+vector["dy"]:.2f}" '
                        'stroke="#92b4d5" stroke-width=".9"/>')
        point_summary = ("No preceding motion pair" if pair_index < 0 else
                         f'{len(pairs[pair_index]["vectors"])} accepted pair vectors'
                         f' · {linked_count} selected tracklet segments')
        figures.append(
            '<figure><div class="viewport">'
            f'<img loading="lazy" src="{h(frame["path"])}" '
            f'alt="Original source frame at PTS {frame["sourcePts"]}">'
            f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
            'aria-hidden="true">' + "".join(arrows) + '</svg></div>'
            f'<figcaption><strong>Sample {sample_index + 1}</strong>'
            f'<span>PTS {frame["sourcePts"]} · {frame["seconds"]:.3f}s</span>'
            f'<small>{h(point_summary)}</small></figcaption></figure>')

    rows = []
    timebase = Fraction(**report["sourceTimebase"])
    for track in tracks:
        observations = track["observations"]
        elapsed = ((observations[-1]["endPts"] - observations[0]["startPts"]) *
                   timebase)
        distance = sum(math.hypot(o["endPixels"]["x"] - o["startPixels"]["x"],
                                  o["endPixels"]["y"] - o["startPixels"]["y"])
                       for o in observations)
        # Report times can originate from untrusted JSON. Source metadata and
        # decoded PTS are checked as well, but formatting must not overflow.
        try:
            duration_seconds = float(elapsed)
        except OverflowError as exc:
            raise ValueError("motion review tracklet duration is out of range") from exc
        if not math.isfinite(duration_seconds) or duration_seconds <= 0:
            raise ValueError("motion review tracklet duration is invalid")
        duration_text = f"{duration_seconds:.3f}s"
        speed_text = f"{distance / duration_seconds:.2f} px/s"
        rows.append(
            f'<tr><th scope="row"><span class="swatch" '
            f'style="background:{track_color[track["id"]]}"></span>{h(track["id"])}</th>'
            f'<td>{track["pairCount"]}</td><td>{h(duration_text)}</td>'
            f'<td>{h(speed_text)}</td><td>{h(track.get("endReason", "unknown"))}</td></tr>')
    if not rows:
        rows = ['<tr><td colspan="5">No supported multi-pair tracklets. '
                'Individual pair vectors may still be shown on the frames.</td></tr>']
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Kumiki sparse motion QA</title><style>'
        ':root{color-scheme:dark;font-family:system-ui,-apple-system,sans-serif}'
        'body{background:#090f19;color:#eef5ff;margin:0;padding:clamp(16px,3vw,40px)}'
        'main,header{max-width:1320px;margin:auto}h1{font-size:clamp(28px,4vw,42px);margin-bottom:8px}'
        'p{color:#b8c9db;max-width:1050px;line-height:1.6}.badge{display:inline-block;'
        'padding:5px 10px;border:1px solid #476378;border-radius:999px;color:#b7dbeb}'
        '.frames{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;'
        'margin:24px 0 35px}figure{margin:0;background:#142030;border:1px solid #32485e;'
        'border-radius:14px;overflow:hidden}.viewport{position:relative;aspect-ratio:'
        f'{width}/{height};'
        'background:#101822}.viewport img,.viewport svg{position:absolute;inset:0;'
        'width:100%;height:100%;display:block}.viewport img{object-fit:fill}'
        'figcaption{display:flex;flex-wrap:wrap;gap:7px 16px;align-items:center;padding:13px}'
        'figcaption span{font-variant-numeric:tabular-nums;color:#c7d7e6}'
        'figcaption small{width:100%;color:#95abc2}.swatch{display:inline-block;'
        'width:9px;height:9px;border-radius:50%;margin-right:8px}'
        'table{border-collapse:collapse;width:100%;font-size:14px;margin:16px 0}'
        'th,td{border-bottom:1px solid #26394c;padding:12px;text-align:left}'
        'thead th{color:#a8c5dc;font-weight:600}tbody th{font-weight:600}'
        '@media(max-width:780px){.frames{grid-template-columns:1fr}}'
        '</style></head><body><header>'
        '<span class="badge">Source-linked candidate observations · not an artistic grade</span>'
        '<h1>Motion paths on source frames</h1><p>' + h(source_name) + ' · ' +
        str(len(frames)) + ' decoded frames · ' + str(len(tracks)) + ' of ' +
        str(total_tracks) + ' candidate tracklets shown. Each arrow is an '
        'observed sampled-pair displacement projected onto its end frame, not '
        'a recovered physical trajectory. Image-plane motion does not verify '
        'camera movement, object identity, occlusion recovery, 3D geometry or '
        'artistic quality.</p></header><main><section class="frames">' +
        "".join(figures) + '</section><section><h2>Tracklet evidence</h2><table>'
        '<thead><tr><th>Candidate</th><th>Pair observations</th><th>Duration</th>'
        '<th>Mean image speed</th><th>Stopped because</th></tr></thead><tbody>' +
        "".join(rows) + '</tbody></table></section></main></body></html>\n')


def _verify_existing(destination: Path, settings: dict[str, Any]) -> Path:
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError("motion review output is not a regular directory")
    manifest = _json_file(destination / "sparse-flow-review.json", limit=262_144)
    records = manifest.get("files")
    actual = [item for item in _file_records(destination)
              if item["path"] != "sparse-flow-review.json"]
    expected_paths = {"index.html", "sparse-flow.json"} | {
        item["path"] for item in settings["selectedFrames"]}
    if (manifest.get("schemaVersion") != SPARSE_FLOW_REVIEW_VERSION or
            manifest.get("settings") != settings or
            manifest.get("humanReviewStatus") != "unreviewed" or
            manifest.get("qualityVerdict") != "not-performed" or
            records != actual or expected_paths != {item["path"] for item in actual} or
            sha256_file(destination / "sparse-flow.json") != settings["reportSha256"]):
        raise ValueError("motion review output is incomplete or modified")
    return destination / "index.html"


def build_sparse_flow_review(
    source: Path, report_path: Path, output: Path, *, max_frames: int = 8,
    max_tracklets: int = 12, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> Path:
    if type(max_frames) is not int or not 2 <= max_frames <= 12:
        raise ValueError("motion review max_frames must be 2..12")
    if type(max_tracklets) is not int or not 1 <= max_tracklets <= 16:
        raise ValueError("motion review max_tracklets must be 1..16")
    source_signature = file_signature(source)
    report_signature = file_signature(report_path)
    report = _json_file(report_path, limit=8_388_608)
    width, height, samples, _, all_tracks = _validate(report)
    metadata = inspect_source(source, ffprobe=ffprobe)
    if (metadata["source"]["sha256"] != report["sourceSha256"] or
            metadata["video"]["streamIndex"] != report.get("sourceStreamIndex") or
            metadata["video"]["sourceTimebase"] != report.get("sourceTimebase")):
        raise ValueError("motion review source does not match sparse-flow evidence")
    timebase = Fraction(**report["sourceTimebase"])
    seconds = report.get("scanWindowSeconds")
    if type(seconds) is not int or not 1 <= seconds <= 20:
        raise ValueError("motion review scan window is out of bounds")
    ranked = sorted(all_tracks, key=lambda t: (-t["pairCount"], t["id"]))
    top = ranked[:max_tracklets]
    selected = _selection(
        len(samples), top, min(max_frames, len(samples)),
        cut_pair_indices=[i for i, pair in enumerate(report["pairs"])
                          if pair["status"] == "cut-boundary"])
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
        "selectedFrames": frame_settings,
        "maxFrames": max_frames, "maxTracklets": max_tracklets,
        "analysisResolution": {"width": width, "height": height},
        "ffmpeg": ffmpeg, "ffprobe": ffprobe,
        "renderRevision": RENDER_REVISION,
    }
    digest = hashlib.sha256(_serialized(settings)).hexdigest()[:16]
    destination = output / f"sparse-flow-review-{report['sourceSha256'][:12]}-{digest}"
    output.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        require_unchanged(source, source_signature)
        return _verify_existing(destination, settings)
    decoded = read_rgb_frames(
        source, report["sourceStreamIndex"],
        [samples[index]["sampleOrdinal"] for index in selected],
        [samples[index]["sourcePts"] for index in selected],
        timebase=timebase, seconds=seconds, width=width, height=height,
        ffmpeg=ffmpeg,
    )
    require_unchanged(source, source_signature)
    require_unchanged(report_path, report_signature)
    with tempfile.TemporaryDirectory(prefix=".sparse-flow-review-", dir=output) as temp:
        staging = Path(temp)
        (staging / "frames").mkdir()
        for frame, pixels in zip(frame_settings, decoded, strict=True):
            (staging / frame["path"]).write_bytes(_png_rgb(pixels, width, height))
        display_frames = [{**frame, "seconds": float(frame["sourcePts"] * timebase)}
                          for frame in frame_settings]
        (staging / "index.html").write_text(
            _render_html(metadata["source"]["fileName"], report, display_frames,
                         top, width, height, len(all_tracks)), encoding="utf-8")
        (staging / "sparse-flow.json").write_bytes(report_bytes)
        (staging / "sparse-flow-review.json").write_bytes(_serialized({
            "schemaVersion": SPARSE_FLOW_REVIEW_VERSION, "settings": settings,
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
