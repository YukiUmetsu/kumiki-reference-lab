"""Visual QA gallery of externally proposed subject tracklets on verified source frames.

Not a detector, identity validator, or source-license verification.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.subject_detections import OUTPUT_VERSION, _check_box

REVIEW_VERSION = "kumiki.subject-tracklet-visual-review.v1"
_TRACKLET = re.compile(r"subject_[0-9]{3}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COLORS = ("#67e8f9", "#f9ab8a", "#c3b7ff", "#b5e08a",
           "#ffb3d5", "#f4dc82", "#92d0ff", "#dcb5a4")


def _validate_report(report: Any) -> list[dict[str, Any]]:
    if not isinstance(report, dict) or report.get("schemaVersion") != OUTPUT_VERSION:
        raise ValueError("visual QA requires a subject-tracklets v1 report")
    if type(report.get("sourceSha256")) is not str or not _SHA.fullmatch(report["sourceSha256"]):
        raise ValueError("visual QA requires source SHA-256")
    if type(report.get("sourceStreamIndex")) is not int or not 0 <= report["sourceStreamIndex"] <= 64:
        raise ValueError("visual QA requires a valid video stream index")
    tb = report.get("sourceTimebase")
    if (not isinstance(tb, dict) or set(tb) != {"numerator", "denominator"} or
            type(tb.get("numerator")) is not int or
            type(tb.get("denominator")) is not int or not
            1 <= tb["numerator"] <= tb["denominator"] <= 10**12):
        raise ValueError("visual QA needs valid rational source timebase")
    frames = report.get("frames")
    if not isinstance(frames, list) or not 2 <= len(frames) <= 120 or report.get("frameCount") != len(frames):
        raise ValueError("visual QA source frame count mismatch")
    roster = report.get("tracklets")
    if not isinstance(roster, list) or len(roster) > 100:
        raise ValueError("visual QA needs bounded tracklet roster")
    roster_ids = set()
    counts = {}
    for item in roster:
        if not isinstance(item, dict) or set(item) != {"id", "observedFrameCount"}:
            raise ValueError("visual QA tracklet roster malformed")
        tid, count = item["id"], item["observedFrameCount"]
        if (type(tid) is not str or not _TRACKLET.fullmatch(tid) or tid in roster_ids or
                type(count) is not int or count < 1):
            raise ValueError("visual QA tracklet roster has invalid or duplicate IDs")
        roster_ids.add(tid)
        counts[tid] = 0
    if report.get("trackletCount") != len(roster):
        raise ValueError("visual QA tracklet count mismatch")
    prior_pts = None
    proposals_total = 0
    for i, frame in enumerate(frames):
        if not isinstance(frame, dict) or set(frame) != {
            "sourcePts", "proposals", "rejectedLowScore"
        }:
            raise ValueError(f"visual QA frame {i} fields invalid")
        pts, proposals = frame["sourcePts"], frame["proposals"]
        if (type(pts) is not int or not -(2**63) < pts < 2**63 or
                (prior_pts is not None and pts <= prior_pts) or
                not isinstance(proposals, list) or len(proposals) > 8 or
                type(frame["rejectedLowScore"]) is not int or frame["rejectedLowScore"] < 0):
            raise ValueError(f"visual QA frame {i} PTS/count invalid")
        prior_pts = pts
        seen = set()
        for row in proposals:
            if not isinstance(row, dict) or set(row) != {
                "trackletId", "category", "box", "detectorScore",
                "association", "crossedCutBeforeFrame",
            }:
                raise ValueError("visual QA proposal malformed")
            tid = row["trackletId"]
            if type(tid) is not str or tid not in roster_ids or tid in seen:
                raise ValueError("visual QA references unknown or duplicate frame tracklet")
            seen.add(tid)
            _check_box(row["box"], "visual QA box")
            score = row["detectorScore"]
            if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("visual QA detector score invalid")
            if row["association"] not in ("mutual-iou-match", "new-unverified-tracklet"):
                raise ValueError("visual QA association unsupported")
            if type(row["crossedCutBeforeFrame"]) is not bool:
                raise ValueError("visual QA cut indicator invalid")
            category = row["category"]
            if type(category) is not str or category not in {
                "person", "animated-character", "animal", "anthropomorphic", "other-subject"
            }:
                raise ValueError("visual QA proposal category invalid")
            counts[tid] += 1
            proposals_total += 1
    if report.get("proposalCount") != proposals_total or any(
            counts[item["id"]] != item["observedFrameCount"] for item in roster):
        raise ValueError("visual QA proposal counts contradict roster")
    return frames


def _select_indices(total: int, max_frames: int) -> list[int]:
    count = min(total, max_frames)
    if count == 1:
        return [0]
    # Include first/last and spread the remaining frames evenly, without duplicates.
    indices = {round(i * (total - 1) / (count - 1)) for i in range(count)}
    return sorted(indices)


def _page(rows: list[dict[str, Any]], width: int, height: int, source_name: str) -> str:
    figures = []
    for row in rows:
        rects = []
        for index, box_info in enumerate(row["proposals"]):
            x, y, w, h = [float(z) for z in box_info["box"]]
            color = _COLORS[(int(box_info["trackletId"].rsplit("_", 1)[1])-1) % len(_COLORS)]
            label = html.escape(box_info["trackletId"], quote=True)
            rects.append(
                f'<rect x="{x * width:.3f}" y="{y * height:.3f}" '
                f'width="{w * width:.3f}" height="{h * height:.3f}" '
                f'stroke="{color}" fill="{color}" fill-opacity="0.09" stroke-width="1.5"/>'
                f'<text x="{x * width + 2:.3f}" y="{max(10, y * height - 3):.3f}" '
                f'fill="{color}" font-size="10">{label}</text>'
            )
        escaped_path = html.escape(row["path"], quote=True)
        figures.append(
            '<figure><div class="viewport">'
            f'<img src="{escaped_path}" alt="Actual source frame at PTS {row["sourcePts"]}" loading="lazy">'
            f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" aria-hidden="true">'
            + "".join(rects) +
            '</svg></div>'
            f'<figcaption>Source PTS {row["sourcePts"]} · '
            f'{row["timeSeconds"]:.3f}s · {len(row["proposals"])} detector-proposed boxes</figcaption>'
            '</figure>'
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Subject tracklet visual QA</title><style>'
        ':root{color-scheme:dark;font-family:system-ui,sans-serif}'
        'body{margin:0;padding:22px;background:#0b1020;color:#ecf2ff}'
        'header,main{max-width:1180px;margin:auto}.grid{display:grid;'
        'grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}'
        'figure{margin:0;background:#141f31;border:1px solid #324057;border-radius:11px;overflow:hidden}'
        f'.viewport{{position:relative;aspect-ratio:{width}/{height};background:#080c13}}'
        '.viewport img,.viewport svg{position:absolute;inset:0;width:100%;height:100%}'
        'figcaption{padding:12px;color:#c8d3e7;font-size:13px}'
        'p{line-height:1.5;max-width:950px;color:#c3cde0}'
        '@media(max-width:750px){.grid{grid-template-columns:1fr}}</style></head><body>'
        '<header><h1>Timecoded subject-tracklet review</h1><p>'
        + html.escape(source_name, quote=True) +
        '. These frames were decoded from the local source and their original PTS verified. '
        'Rectangles and IDs are unverified **detector proposals**, not confirmed persons '
        'or approved character identities. Review drift, occlusion, cuts and missing boxes '
        'before interpreting actions or relationships.</p></header>'
        '<main><section class="grid">' + "".join(figures) +
        '</section></main></body></html>\n'
    )


def build_subject_tracklet_review(
    source: Path, report_path: Path, out: Path, *, max_frames: int = 8,
    scan_seconds: int = 20, width: int = 320, height: int = 180,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> Path:
    """Decode actual local frames and render detector boxes for unapproved QA."""
    if (type(max_frames) is not int or not 2 <= max_frames <= 12 or
            type(scan_seconds) is not int or not 1 <= scan_seconds <= 120 or
            type(width) is not int or type(height) is not int or
            not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("subject review frame/count/scan resolution bounds invalid")
    if out.exists() or out.is_symlink():
        raise ValueError("subject review output must be a new directory")
    source_signature = file_signature(source)
    report_signature = file_signature(report_path)
    report = _json_file(report_path, limit=2_000_000)
    frames = _validate_report(report)
    metadata = inspect_source(source, ffprobe=ffprobe)
    if (metadata["source"]["sha256"] != report["sourceSha256"] or
            metadata["video"]["streamIndex"] != report["sourceStreamIndex"] or
            metadata["video"]["sourceTimebase"] != report["sourceTimebase"]):
        raise ValueError("subject review report source hash/clock differs from local film")
    idx = _select_indices(len(frames), max_frames)
    chosen = [frames[i] for i in idx]
    timebase = Fraction(**report["sourceTimebase"])
    frame_records = read_frame_pts(
        source, report["sourceStreamIndex"], seconds=scan_seconds, ffprobe=ffprobe)
    found: dict[int, list[int]] = {}
    for record in frame_records:
        if record.pts is not None:
            found.setdefault(record.pts, []).append(record.ordinal)
    ordinals = []
    for frame in chosen:
        candidates = found.get(frame["sourcePts"], [])
        if len(candidates) != 1:
            raise ValueError("source frame PTS missing or ambiguous; increase --scan-seconds or review source")
        ordinals.append(candidates[0])
    if ordinals != sorted(set(ordinals)):
        raise ValueError("source PTS selection is not in unique increasing decode order")
    rgb = read_rgb_frames(
        source, report["sourceStreamIndex"], ordinals,
        [frame["sourcePts"] for frame in chosen], timebase=timebase,
        seconds=scan_seconds, width=width, height=height, ffmpeg=ffmpeg)
    require_unchanged(source, source_signature)
    require_unchanged(report_path, report_signature)
    image_rows = [
        {**frame, "path": f"frames/actual-frame-{i:03d}.png",
         "timeSeconds": float(frame["sourcePts"] * timebase)}
        for i, frame in enumerate(chosen)
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-tracklet-qa-", dir=out.parent) as directory:
        staging = Path(directory)
        (staging / "frames").mkdir()
        for row, pixels in zip(image_rows, rgb, strict=True):
            (staging / row["path"]).write_bytes(_png_rgb(pixels, width, height))
        (staging / "index.html").write_text(
            _page(image_rows, width, height, metadata["source"]["fileName"]), encoding="utf-8")
        manifest = {
            "schemaVersion": REVIEW_VERSION,
            "sourceSha256": report["sourceSha256"],
            "sourceStreamIndex": report["sourceStreamIndex"],
            "sourceTimebase": report["sourceTimebase"],
            "inputReportSha256": sha256_file(report_path),
            "frames": [{"sourcePts": row["sourcePts"], "path": row["path"]}
                       for row in image_rows],
            "renderResolution": {"width": width, "height": height},
            "reviewStatus": "not-reviewed",
            "evidenceStatus": "decoded-source-pts-verified-boxes-externally-proposed",
            "limits": "No detector accuracy, person identity, character continuity, lip motion, or artistic quality verified.",
        }
        (staging / "subject-visual-review.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        require_unchanged(source, source_signature)
        require_unchanged(report_path, report_signature)
        os.replace(staging, out)
    return out / "index.html"
