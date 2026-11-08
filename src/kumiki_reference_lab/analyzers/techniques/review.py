"""Immutable, source-PTS-verified HTML evidence for cinematic review cues."""

from __future__ import annotations

import hashlib
import html
import json
import os
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.techniques.propose import propose_techniques
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.thumbnails import extract_thumbnails
from kumiki_reference_lab.contracts.analysis import TECHNIQUE_REVIEW_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict


def _payload(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def _review_html(source_name: str, cues: list[dict[str, Any]],
                 *, total_cues: int) -> str:
    cards = []
    for cue in cues:
        images = []
        for item in cue["images"]:
            ratio = Fraction(**item["sourceSeconds"])
            images.append(
                '<figure><img loading="lazy" src="' + html.escape(item["path"], quote=True) +
                '" alt="Source video sampled frame"><figcaption>' +
                html.escape(item["role"]) + f' · {float(ratio):.3f}s · PTS {item["sourcePts"]}' +
                '</figcaption></figure>'
            )
        record = cue["proposal"]
        alternatives = "".join('<li>' + html.escape(item) + '</li>'
                               for item in record["plausibleAlternatives"])
        questions = "".join('<li>' + html.escape(item) + '</li>'
                            for item in record["reviewQuestions"])
        metrics = html.escape(json.dumps(record["evidence"]["measurements"],
                                         indent=2, sort_keys=True, ensure_ascii=False))
        cards.append(
            '<section><h2>' + html.escape(record["visibleCueHypothesis"]) + '</h2>'
            '<p class="meta">Catalog candidate: <code>' + html.escape(record["techniqueId"]) +
            '</code> · PTS ' + str(record["sourcePtsRange"]["startPts"]) +
            '–' + str(record["sourcePtsRange"]["endPts"]) +
            '</p><div class="frames">' + ''.join(images) +
            '</div><div class="details"><div><h3>Observed numeric evidence</h3><pre>' +
            metrics + '</pre></div><div><h3>Other explanations</h3><ul>' + alternatives +
            '</ul><h3>Check before implementing</h3><ul>' + questions +
            '</ul></div></div></section>'
        )
    if not cards:
        if total_cues:
            cards.append('<section><h2>No cues on this selected page</h2>'
                         '<p>Change --cue-offset to inspect earlier detected cues.</p></section>')
        else:
            cards.append('<section><h2>No review cues passed the current gates</h2>'
                         '<p>Absent cues do not imply a reference lacks cinematic technique. '
                         'Try a run with --sparse-flow and --appearance; inspect the source '
                         'and contact sheet manually.</p></section>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Kumiki cinematic technique review</title><style>'
        ':root{color-scheme:dark;font-family:system-ui,-apple-system,sans-serif}'
        'body{background:#0a1018;color:#e9f1fc;margin:0;padding:clamp(16px,4vw,42px)}'
        'main,header{max-width:1360px;margin:auto}h1{font-size:clamp(24px,4vw,40px)}'
        'p{color:#b5c5d8;line-height:1.55}section{padding:26px 0;border-top:1px solid #344358}'
        'h2{font-size:22px;color:#e6f1ff}.meta{font-size:14px}.frames{display:grid;'
        'grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:20px 0}'
        'figure{margin:0;background:#152233;border:1px solid #34485e;border-radius:10px;overflow:hidden}'
        'img{display:block;width:100%;height:auto;background:black}figcaption{padding:12px;'
        'font-size:13px;color:#c1d4e8;font-variant-numeric:tabular-nums}'
        '.details{display:grid;grid-template-columns:1fr 1fr;gap:18px}li{line-height:1.55;margin:6px 0}'
        'pre{font-size:13px;line-height:1.4;padding:18px;overflow:auto;background:#141d2a;'
        'border-radius:8px;border:1px solid #344358}code{color:#9dcaff}'
        '@media(max-width:820px){.details{grid-template-columns:1fr}.frames{grid-template-columns:1fr}}'
        '</style></head><body><header><h1>Cinematic technique review cues</h1><p>' +
        html.escape(source_name) + ' · showing ' + str(len(cues)) + ' of ' +
        str(total_cues) + ' detected cues. Frames come from this source, with verified '
        'original presentation timestamps. Image-plane measurements are not proof of '
        'camera motion, real lights, semantic intent, or production quality. '
        'All suggestions require independent human review.</p></header><main>' +
        ''.join(cards) + '</main></body></html>\n'
    )


def _verify_existing(destination: Path, settings: dict[str, Any]) -> Path:
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("technique review output is not a regular directory")
    index_path = destination / "technique-review.json"
    if (not index_path.is_file() or index_path.is_symlink() or
            index_path.stat().st_size > 1_000_000):
        raise ValueError("technique review manifest is missing or oversized")
    try:
        report = json.loads(index_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("technique review manifest is invalid JSON") from exc
    if (not isinstance(report, dict) or
            report.get("schemaVersion") != TECHNIQUE_REVIEW_VERSION or
            report.get("settings") != settings or
            report.get("reviewStatus") != "unreviewed" or
            report.get("qualityVerdict") != "not-performed"):
        raise ValueError("technique review settings or verdict were modified")
    cues = report.get("cues")
    saved_path = destination / "technique-proposals.json"
    if (not saved_path.is_file() or saved_path.is_symlink() or
            saved_path.stat().st_size > 4_194_304):
        raise ValueError("technique review proposals are missing or unsafe")
    try:
        saved_proposals = json.loads(saved_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("technique review proposals are unreadable") from exc
    if (not isinstance(saved_proposals, dict) or
            not isinstance(saved_proposals.get("candidates"), list) or
            report.get("totalCandidateCount") != len(saved_proposals["candidates"])):
        raise ValueError("technique review has invalid proposal source")
    expected_cues = saved_proposals["candidates"][settings["cueOffset"]:
                                                  settings["cueOffset"] + settings["maxCues"]]
    if (not isinstance(cues, list) or
            [item.get("id") for item in cues if isinstance(item, dict)] !=
            settings["selectedCueIds"] or len(cues) != len(settings["selectedCueIds"]) or
            [item.get("proposal") for item in cues if isinstance(item, dict)] != expected_cues):
        raise ValueError("technique review has altered cue identities")
    expected = {"index.html", "technique-proposals.json"}
    for cue, selection in zip(cues, settings["imageSelections"], strict=True):
        if cue.get("sourcePtsRange") != selection["sourcePtsRange"]:
            raise ValueError("technique review has altered source cue ranges")
        if (not isinstance(cue.get("images"), list) or
                [[frame.get("sourcePts"), frame.get("path")] for frame in cue["images"]]
                != selection["frames"]):
            raise ValueError("technique review has altered source frame evidence")
        expected.update(frame["path"] for frame in cue["images"])
    records = report.get("files")
    if (not isinstance(records, list) or len(records) != len(expected) or
            any(not isinstance(item, dict) or not isinstance(item.get("path"), str)
                for item in records) or
            {record["path"] for record in records} != expected):
        raise ValueError("technique review file inventory is inconsistent")
    actual = set()
    for path in destination.rglob("*"):
        if path.is_symlink():
            raise ValueError("technique review contains a symbolic link")
        if path.is_file():
            actual.add(path.relative_to(destination).as_posix())
    if actual != expected | {"technique-review.json"}:
        raise ValueError("technique review contains untracked or missing files")
    for record in records:
        path = destination / record["path"]
        if not path.is_file() or sha256_file(path) != record.get("sha256"):
            raise ValueError("technique review file hash changed")
    if sha256_file(destination / "technique-proposals.json") != settings["proposalFileSha256"]:
        raise ValueError("technique proposal evidence changed")
    return destination / "index.html"


def build_technique_review(
    source: Path, analysis_run: Path, output: Path, *, catalog_root: Path,
    max_cues: int = 8, cue_offset: int = 0, width: int = 480, ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> Path:
    if type(max_cues) is not int or not 1 <= max_cues <= 8:
        raise ValueError("technique review max_cues must be 1..8")
    if type(cue_offset) is not int or not 0 <= cue_offset <= 31:
        raise ValueError("technique review cue_offset must be 0..31")
    if type(width) is not int or not 128 <= width <= 800:
        raise ValueError("technique review width must be 128..800")
    signature = file_signature(source)
    proposals = propose_techniques(analysis_run, catalog_root)
    analyzed = json.loads(analysis_run.read_text(encoding="utf-8"))
    inspected = inspect_source(source, ffprobe=ffprobe)
    if (inspected["source"]["sha256"] != proposals["source"]["sha256"] or
            inspected["video"]["streamIndex"] != proposals["source"]["streamIndex"] or
            inspected["video"]["sourceTimebase"] != proposals["source"]["sourceTimebase"]):
        raise ValueError("review source does not match the verified analysis run")
    seconds = analyzed["settings"]["seconds"]
    frame_list = read_frame_pts(source, inspected["video"]["streamIndex"],
                                seconds=seconds, ffprobe=ffprobe)
    by_pts = {frame.pts: frame for frame in frame_list if frame.pts is not None}
    timebase = Fraction(**inspected["video"]["sourceTimebase"])
    selected_cues = proposals["candidates"][cue_offset:cue_offset + max_cues]
    selections: list[list[tuple[str, int]]] = []
    for proposal in selected_cues:
        lower, upper = (proposal["sourcePtsRange"][k] for k in ("startPts", "endPts"))
        if lower not in by_pts or upper not in by_pts:
            raise ValueError("technique evidence PTS not present in decoded source timeline")
        candidates = [pts for pts in by_pts if lower < pts < upper]
        if not candidates:
            raise ValueError("technique cue has no independently decoded middle frame")
        middle = min(candidates, key=lambda x: (abs(2 * x - lower - upper), x))
        selections.append([("start", lower), ("middle", middle), ("end", upper)])
    selected_pts = sorted({pts for selection in selections for _, pts in selection})
    selected_frames = [by_pts[pts] for pts in selected_pts]
    if len(selected_frames) > 24:
        raise ValueError("technique review exceeds 24 decoded source images")
    require_unchanged(source, signature)
    proposal_bytes = json.dumps(proposals, indent=2, sort_keys=True,
                                ensure_ascii=False).encode("utf-8") + b"\n"
    proposal_sha = hashlib.sha256(proposal_bytes).hexdigest()
    identity = {
        "sourceSha256": inspected["source"]["sha256"],
        "sourceStreamIndex": inspected["video"]["streamIndex"],
        "sourceTimebase": inspected["video"]["sourceTimebase"],
        "analysisRunSha256": proposals["provenance"]["analysisRunSha256"],
        "proposalFileSha256": proposal_sha,
        "catalogEntries": proposals["provenance"]["catalogEntries"],
        "selectedCueIds": [cue["id"] for cue in selected_cues],
        "imageSelections": [{"sourcePtsRange": cue["sourcePtsRange"],
                             "frames": [[pts, f"frames/frame-{selected_pts.index(pts):03d}.jpg"]
                                        for _, pts in selection]}
                            for cue, selection in zip(selected_cues, selections, strict=True)],
        "seconds": seconds, "maxCues": max_cues, "cueOffset": cue_offset,
        "width": width,
        "ffmpeg": ffmpeg, "ffprobe": ffprobe,
        "sampling": "source-pts-start-nearest-middle-end-v1",
    }
    digest = hashlib.sha256(_payload(identity)).hexdigest()[:16]
    destination = output / f"technique-review-{identity['sourceSha256'][:12]}-{digest}"
    output.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        return _verify_existing(destination, identity)
    with tempfile.TemporaryDirectory(prefix=".technique-review-", dir=output) as temp:
        staging = Path(temp)
        thumbnails = {}
        if selected_frames:
            images = staging / "frames"
            images.mkdir()
            produced = extract_thumbnails(
                source, images, inspected["video"]["streamIndex"],
                [frame.ordinal for frame in selected_frames],
                seconds=seconds, width=width, expected_timebase=timebase,
                expected_pts=selected_pts, ffmpeg=ffmpeg,
            )
            thumbnails = {pts: path.relative_to(staging).as_posix()
                          for pts, path in zip(selected_pts, produced, strict=True)}
        require_unchanged(source, signature)
        cues = []
        for proposal, selection in zip(selected_cues, selections, strict=True):
            cues.append({
                "id": proposal["id"], "techniqueId": proposal["techniqueId"],
                "sourcePtsRange": proposal["sourcePtsRange"],
                "proposal": proposal,
                "images": [{"role": role, "sourcePts": pts,
                            "sourceSeconds": as_rational_dict(pts * timebase),
                            "path": thumbnails[pts]} for role, pts in selection],
            })
        (staging / "technique-proposals.json").write_bytes(proposal_bytes)
        (staging / "index.html").write_text(
            _review_html(inspected["source"]["fileName"], cues,
                         total_cues=len(proposals["candidates"])), encoding="utf-8")
        records = [{"path": item.relative_to(staging).as_posix(),
                    "sha256": sha256_file(item)}
                   for item in sorted(staging.rglob("*")) if item.is_file()]
        report = {"schemaVersion": TECHNIQUE_REVIEW_VERSION,
                  "settings": identity, "reviewStatus": "unreviewed",
                  "qualityVerdict": "not-performed",
                  "totalCandidateCount": len(proposals["candidates"]),
                  "cues": cues, "files": records}
        (staging / "technique-review.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        if destination.exists() or destination.is_symlink():
            return _verify_existing(destination, identity)
        try:
            os.rename(staging, destination)
        except FileExistsError:
            return _verify_existing(destination, identity)
    return destination / "index.html"
