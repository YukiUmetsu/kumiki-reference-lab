"""Make a source-hashed, no-server human review workbench for real video phases.

The HTML lives only inside the existing Git-ignored frame workspace. It
references already present low-res PNGs by relative path and generates no
media copies, automatic labels, or model calls. All review labels must be
explicitly exported by the human in the browser.
"""
from __future__ import annotations

from html import escape
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from kumiki_reference_lab.pipeline.agent_frame_review import (
    _frame_path, load_workspace,
)
from kumiki_reference_lab.pipeline.multi_region_temporal import _validate_tracks
from kumiki_reference_lab.pipeline.online_temporal import _decode_review_png
from kumiki_reference_lab.pipeline.sequence_benchmark import (
    _insights_sequences, _load, make_label_template,
)
from kumiki_reference_lab.pipeline.sequence_review_ui import SCRIPT, STYLES

_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,59}[a-z0-9])?\.html\Z")
_CATEGORIES = (
    ("no-clear-change", "No clear visible change"),
    ("apparent-region-translation", "Region moves across the frame"),
    ("apparent-box-size-change", "Region looks larger or smaller"),
    ("apparent-pose-or-silhouette-change", "Visible silhouette or pose changes"),
    ("apparent-turn", "Region appears to turn"),
    ("apparent-relative-position-change", "Relative positions change"),
    ("not-observable", "Cannot tell from available frames"),
)


def _validated_review_rows(
    workspace: Path, manifest: dict[str, Any], numeric: dict[str, Any],
    insights: dict[str, Any], rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seeded = insights.get("seededSubjectTracks")
    shots = insights.get("shotIntelligence")
    if (not isinstance(seeded, dict)
            or seeded.get("sourceSha256") != manifest["sourceSha256"]
            or seeded.get("status") not in (
                "seeded-2d-region-motion-candidates",
                "auto-seeded-2d-region-motion-candidates")
            or not isinstance(shots, dict)
            or (workspace / "frames").is_symlink()):
        raise ValueError("review workbench requires source-matched supported ROI tracks")
    tracks = _validate_tracks(seeded, numeric, shots)
    by_id = {track["id"]: track for track in tracks}
    width, height = manifest["width"], manifest["height"]
    if (type(width) is not int or type(height) is not int
            or not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("review preview resolution is outside safety bounds")
    used = set()
    output = []
    for row in rows:
        anchors = []
        for pos, frame in enumerate(row["frameIndices"]):
            source = numeric["frames"][frame]
            seconds = source.get("decodedSeconds")
            if (source.get("frameIndex") != frame
                    or type(seconds) not in (int, float)
                    or not math.isfinite(seconds)
                    or abs(seconds - row["sourceDecodedSeconds"][pos]) > .00001):
                raise ValueError("review anchors disagree with original decoded times")
            if frame not in used:
                path = _frame_path(workspace, frame)
                if path.stat().st_size > 1_000_000:
                    raise ValueError("review preview exceeds per-frame byte budget")
                _decode_review_png(path, width=width, height=height)
                used.add(frame)
            outlines = []
            for i, ident in enumerate(row["subjectIds"]):
                track = by_id.get(ident)
                if track is None or track["shotId"] != row["shotId"]:
                    raise ValueError("sequence region does not match source shot")
                observation = next(
                    (v for v in track["observations"] if v["frame"] == frame),
                    None,
                )
                if observation is None:
                    raise ValueError("sequence region lacks an observed frame box")
                outlines.append((chr(65 + i), observation["box"]))
            anchors.append({
                "frame": frame, "seconds": seconds, "outlines": outlines,
            })
        output.append({"row": row, "anchors": anchors})
    return output


def _html_sequence(number: int, item: dict[str, Any]) -> str:
    row = item["row"]
    figures = []
    for pos, anchor in enumerate(item["anchors"]):
        outlines = []
        for marker, (x, y, w, h) in anchor["outlines"]:
            style = (f"left:{x*100:.4f}%;top:{y*100:.4f}%;"
                     f"width:{w*100:.4f}%;height:{h*100:.4f}%")
            outlines.append(
                f'<span class="roi roi-{marker}" style="{style}" aria-hidden="true">'
                f'<span class="roi-tag">{marker}</span></span>'
            )
        frame = anchor["frame"]
        figures.append(
            '<figure><div class="frame">'
            f'<img src="frames/frame-{frame:06d}.png" '
            f'alt="Original source video preview {frame}" loading="lazy">'
            + "".join(outlines) + '</div><figcaption>'
            + ("Start", "Middle", "End")[pos]
            + f' · frame {frame} · {anchor["seconds"]:.3f}s'
            + '</figcaption></figure>'
        )
    options = '<option value="">Choose visible change</option>' + "".join(
        '<option value="{value}">{label}</option>'.format(
            value=escape(value, quote=True), label=escape(label))
        for value, label in _CATEGORIES
    )
    labels = "".join(
        '<label class="review-phase"><span>{title}</span>'
        '<select class="phase-select" data-sequence="{seq}" data-phase="{phase}">'
        '{options}</select></label>'.format(
            title="Start → Middle" if phase == 0 else "Middle → End",
            seq=number, phase=phase, options=options)
        for phase in range(2)
    )
    subjects = "; ".join(
        ("A" if j == 0 else "B") + ": " + escape(ident)
        for j, ident in enumerate(row["subjectIds"])
    )
    return (
        f'<section class="sequence" aria-labelledby="seq-{number}">'
        f'<header><h2 id="seq-{number}">Sequence {number+1}</h2>'
        f'<span>{escape(row["shotId"])}</span></header>'
        f'<p class="subjects">{subjects}</p>'
        f'<div class="frames">{"".join(figures)}</div>'
        f'<div class="phases">{labels}</div></section>'
    )


def _embed_json(value: dict[str, Any]) -> str:
    return (json.dumps(value, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False)
            .replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026"))


def _render_html(template: dict[str, Any], rows: list[dict[str, Any]],
                 *, width: int, height: int) -> bytes:
    body = "".join(_html_sequence(i, row) for i, row in enumerate(rows))
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="'
        "default-src 'none'; img-src 'self' file:; "
        "script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "connect-src 'none'; object-src 'none'; base-uri 'none'; "
        "form-action 'none'\">"
        '<title>Kumiki · Offline sequence review</title>'
        f'<style>{STYLES}</style></head>'
        f'<body style="--aspect:{width}/{height}">'
        '<h1>Offline three-frame sequence review</h1>'
        '<p class="note">Inspect each source frame independently from model predictions.'
        ' Region A (red) and region B (cyan) are provisional screen-space'
        ' tracks, not verified character identities or gestures.'
        ' Classify only visible changes; choose Cannot tell when uncertain.</p>'
        '<div class="toolbar">'
        '<label>Human reviewer ID <input id="reviewer" autocomplete="off" '
        'placeholder="reviewer-01" maxlength="100"></label>'
        '<strong id="progress" role="status"></strong>'
        '<button id="draft" type="button">Export pending draft</button>'
        '<button id="complete" type="button" disabled>Export reviewed labels</button>'
        '<label>Resume draft <input id="import" type="file" '
        'accept=".json,application/json"></label>'
        '</div><p id="feedback" role="status" aria-live="polite"></p>'
        f'<main>{body}</main>'
        '<p class="subtle">No frames are uploaded, copied or embedded in this HTML.'
        ' Labels are downloaded only by your action. A completed human review'
        ' is self-declared, and still requires source validation by the evaluator.</p>'
        f'<script id="pending-template" type="application/json">{_embed_json(template)}</script>'
        f'<script>{SCRIPT}</script></body></html>'
    )
    data = page.encode("utf-8")
    if len(data) > 2_000_000:
        raise ValueError("review HTML exceeds 2 MiB size budget")
    return data


def create_review_pack(
    workspace: Path, insights_path: Path, *,
    out: Path | None = None,
) -> Path:
    """Create one review HTML inside a *local ignored* frame workspace."""
    manifest, numeric, _ = load_workspace(workspace)
    workspace = workspace.absolute()
    insights, insights_sha = _load(insights_path)
    source, _, sequences = _insights_sequences(insights)
    if (not sequences or source != manifest["sourceSha256"]
            or insights["source"]["frameCount"] != manifest["frameCount"]
            or numeric.get("sourceSha256") != source
            or numeric.get("frameCount") != manifest["frameCount"]):
        raise ValueError("offline review requires matching nonempty source sequences")
    rows = _validated_review_rows(
        workspace, manifest, numeric, insights, sequences)
    template = make_label_template(insights, insights_sha=insights_sha)
    data = _render_html(
        template, rows, width=manifest["width"], height=manifest["height"])
    target = (out or workspace / "review-sequences.html").absolute()
    if (target.parent != workspace or not _NAME.fullmatch(target.name)
            or target.exists() or target.is_symlink()):
        raise ValueError("HTML output must be a new .html file within the ignored workspace")
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=workspace, prefix=".sequence-review-",
                suffix=".tmp", delete=False) as stream:
            temp = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Publish only if absent: never overwrite another reviewer or race.
        os.link(temp, target)
        temp.unlink()
        temp = None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return target
