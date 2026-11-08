"""Original source-PTS shot/region contact cards independent of technique cues."""

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
from kumiki_reference_lab.analyzers.shots.evidence import build_shot_evidence
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.thumbnails import extract_thumbnails
from kumiki_reference_lab.contracts.analysis import SHOT_GALLERY_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict
from kumiki_reference_lab.pipeline.analyze import _file_records


def _serialized(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _html(source_name: str, pages: list[dict[str, Any]], count: int) -> str:
    cards = []
    for region in pages:
        images = "".join(
            '<figure><img loading="lazy" src="' + html.escape(f["path"], quote=True) +
            '" alt="Original video frame in candidate region">'
            '<figcaption>' + html.escape(f["role"]) + ' · source PTS ' +
            str(f["sourcePts"]) + ' · ' +
            f'{float(Fraction(**f["sourceSeconds"])):.3f}s' +
            '</figcaption></figure>' for f in region["images"])
        observations = html.escape(json.dumps(
            region["evidence"]["observations"], indent=2, ensure_ascii=False,
            sort_keys=True))
        questions = "".join('<li>' + html.escape(q) + '</li>'
                            for q in region["evidence"]["reviewQuestions"])
        after = (str(region["evidence"]["endPtsExclusive"])
                 if region["evidence"]["endPtsExclusive"] is not None else
                 "unknown: bounded scan ended")
        cards.append(
            '<section><h2>' + html.escape(region["id"]) + '</h2><p>'
            'Candidate before: ' + html.escape(region["evidence"]["boundaryBefore"]) +
            ' · candidate after: ' + html.escape(region["evidence"]["boundaryAfter"]) +
            ' · observed frames: ' + str(region["evidence"]["frameCount"]) +
            ' · exclusive end PTS: ' + html.escape(after) +
            '</p><div class="frames">' + images + '</div>'
            '<div class="details"><div><h3>Measured evidence</h3><pre>' +
            observations + '</pre></div><div><h3>Story and edit questions</h3><ul>' +
            questions + '</ul></div></div></section>'
        )
    if not cards:
        cards.append('<section><h2>No regions on this page</h2>'
                     '<p>Check your region offset or verify the frame timeline.</p></section>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Kumiki candidate shot storyboard</title><style>'
        ':root{color-scheme:dark;font-family:system-ui,-apple-system,sans-serif}'
        'body{background:#0b111b;color:#e8f1ff;margin:0;padding:clamp(16px,4vw,42px)}'
        'main,header{max-width:1300px;margin:auto}h1{font-size:clamp(24px,4vw,38px)}'
        'p{color:#c0cedf;line-height:1.55}section{border-top:1px solid #34475f;padding:24px 0}'
        'h2{color:#eef6ff}.frames{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));'
        'gap:12px;margin:18px 0}figure{margin:0;background:#172335;border:1px solid #34485e;'
        'border-radius:10px;overflow:hidden}img{display:block;width:100%;height:auto}'
        'figcaption{padding:12px;font-size:13px;font-variant-numeric:tabular-nums}'
        '.details{display:grid;grid-template-columns:1fr 1fr;gap:18px}'
        'pre{padding:16px;border:1px solid #34485e;background:#141d29;overflow:auto;'
        'font-size:12px;line-height:1.5}li{margin:8px 0;line-height:1.5}'
        '@media(max-width:800px){.frames,.details{grid-template-columns:1fr}}'
        '</style></head><body><header><h1>Candidate shot storyboard</h1><p>' +
        html.escape(source_name) + ' · ' + str(len(pages)) + ' of ' + str(count) +
        ' candidate regions. These verified source frames support human review '
        'of composition, attention and story. Cut candidates may be false positives; '
        'source intent, real camera/light rigs and quality are not established.'
        '</p></header><main>' + "".join(cards) + '</main></body></html>\n'
    )


def _verify_gallery(directory: Path, settings: dict[str, Any]) -> Path:
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("shot gallery output must be a regular directory")
    manifest = _json_file(directory / "shot-gallery.json", limit=1_048_576)
    if (manifest.get("schemaVersion") != SHOT_GALLERY_VERSION or
            manifest.get("settings") != settings or
            manifest.get("humanReviewStatus") != "unreviewed" or
            manifest.get("qualityVerdict") != "not-performed"):
        raise ValueError("shot gallery metadata was modified")
    evidence = _json_file(directory / "shot-evidence.json", limit=4_194_304)
    if sha256_file(directory / "shot-evidence.json") != settings["shotEvidenceSha256"]:
        raise ValueError("shot gallery evidence changed")
    selected = evidence.get("regions", [])[settings["regionOffset"]:
                                          settings["regionOffset"] + settings["maxRegions"]]
    rows = manifest.get("regions")
    if (not isinstance(rows, list) or len(rows) != len(selected) or
            not all(isinstance(row, dict) for row in rows) or
            [row.get("id") for row in rows] !=
            settings["selectedRegionIds"] or
            any(row.get("evidence") != expected
                for row, expected in zip(rows, selected, strict=True))):
        raise ValueError("shot gallery regions were altered")
    expected = {"shot-evidence.json", "index.html"}
    expected_frames = settings["imageSelections"]
    if len(expected_frames) != len(rows):
        raise ValueError("shot gallery image selection mismatch")
    for row, selection in zip(rows, expected_frames, strict=True):
        if (not isinstance(row.get("images"), list) or
                not all(isinstance(im, dict) for im in row["images"]) or
                [[im.get("sourcePts"), im.get("path")] for im in row["images"]]
                != selection):
            raise ValueError("shot gallery source frame links were altered")
        expected.update(im["path"] for im in row["images"])
    records = manifest.get("files")
    actual = [item for item in _file_records(directory)
              if item["path"] != "shot-gallery.json"]
    if (not isinstance(records, list) or records != actual or
            expected != {item["path"] for item in actual}):
        raise ValueError("shot gallery has missing, altered or untracked files")
    return directory / "index.html"


def build_shot_gallery(
    source: Path, analysis_run: Path, output: Path, *, max_regions: int = 8,
    region_offset: int = 0, width: int = 480,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> Path:
    if type(max_regions) is not int or not 1 <= max_regions <= 8:
        raise ValueError("shot gallery max_regions must be 1..8")
    if type(region_offset) is not int or not 0 <= region_offset <= 63:
        raise ValueError("shot gallery region_offset must be 0..63")
    if type(width) is not int or not 128 <= width <= 800:
        raise ValueError("shot gallery width must be 128..800")
    signature = file_signature(source)
    report = build_shot_evidence(analysis_run)
    if report["status"] != "candidate-edit-regions":
        raise ValueError("source timeline is not reliable enough for shot review")
    run = _json_file(analysis_run, limit=262_144)
    inspected = inspect_source(source, ffprobe=ffprobe)
    if (inspected["source"]["sha256"] != report["sourceSha256"] or
            inspected["video"]["streamIndex"] != report["sourceStreamIndex"] or
            inspected["video"]["sourceTimebase"] != report["sourceTimebase"]):
        raise ValueError("shot gallery source differs from verified analysis")
    seconds = run["settings"]["seconds"]
    decoded = read_frame_pts(source, report["sourceStreamIndex"],
                             seconds=seconds, ffprobe=ffprobe)
    pts_values = [f.pts for f in decoded]
    if (not pts_values or any(type(x) is not int for x in pts_values) or
            pts_values != sorted(set(pts_values))):
        raise ValueError("shot gallery source PTS are not monotonically reliable")
    indexed = {f.pts: f for f in decoded}
    selected = report["regions"][region_offset:region_offset + max_regions]
    selections: list[list[tuple[str, int]]] = []
    for region in selected:
        first, last = region["startPtsInclusive"], region["lastObservedFramePts"]
        matching = [pts for pts in pts_values if first <= pts <= last]
        if (not matching or matching[0] != first or matching[-1] != last or
                len(matching) != region["frameCount"]):
            raise ValueError("source frame timeline differs from candidate region evidence")
        if len(matching) < 3:
            frames = [("start" if i == 0 else "end", pts)
                      for i, pts in enumerate(matching)]
        else:
            middle = min(matching[1:-1], key=lambda pts: (abs(2*pts-first-last), pts))
            frames = [("start", first), ("middle", middle), ("end", last)]
        selections.append(frames)
    chosen = sorted({pts for frames in selections for _, pts in frames})
    if len(chosen) > 24:
        raise ValueError("shot gallery frame budget exceeded")
    require_unchanged(source, signature)
    evidence_bytes = json.dumps(report, indent=2, sort_keys=True,
                                ensure_ascii=False).encode("utf-8") + b"\n"
    evidence_hash = hashlib.sha256(evidence_bytes).hexdigest()
    settings = {
        "sourceSha256": report["sourceSha256"],
        "sourceStreamIndex": report["sourceStreamIndex"],
        "sourceTimebase": report["sourceTimebase"],
        "analysisRunSha256": report["analysisRunSha256"],
        "shotEvidenceSha256": evidence_hash,
        "seconds": seconds, "maxRegions": max_regions, "regionOffset": region_offset,
        "width": width, "ffmpeg": ffmpeg, "ffprobe": ffprobe,
        "selectedRegionIds": [region["id"] for region in selected],
        "imageSelections": [[[pts, f"frames/frame-{chosen.index(pts):03d}.jpg"]
                             for _, pts in frames] for frames in selections],
        "sampling": "per-candidate-region-start-middle-last-observed-v1",
    }
    digest = hashlib.sha256(_serialized(settings)).hexdigest()[:16]
    destination = output / f"shot-gallery-{settings['sourceSha256'][:12]}-{digest}"
    output.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        return _verify_gallery(destination, settings)
    with tempfile.TemporaryDirectory(prefix=".shot-gallery-", dir=output) as name:
        staging = Path(name)
        timebase = Fraction(**report["sourceTimebase"])
        filenames: dict[int, str] = {}
        if chosen:
            image_dir = staging / "frames"
            image_dir.mkdir()
            images = extract_thumbnails(
                source, image_dir, report["sourceStreamIndex"],
                [indexed[pts].ordinal for pts in chosen],
                seconds=seconds, width=width, expected_timebase=timebase,
                expected_pts=chosen, ffmpeg=ffmpeg,
            )
            filenames = {pts: path.relative_to(staging).as_posix()
                         for pts, path in zip(chosen, images, strict=True)}
        require_unchanged(source, signature)
        pages = [{
            "id": region["id"], "evidence": region,
            "images": [
                {"role": role, "sourcePts": pts,
                 "sourceSeconds": as_rational_dict(pts * timebase),
                 "path": filenames[pts]}
                for role, pts in frames]
        } for region, frames in zip(selected, selections, strict=True)]
        (staging / "shot-evidence.json").write_bytes(evidence_bytes)
        (staging / "index.html").write_text(
            _html(inspected["source"]["fileName"], pages, len(report["regions"])),
            encoding="utf-8")
        (staging / "shot-gallery.json").write_text(
            json.dumps({
                "schemaVersion": SHOT_GALLERY_VERSION, "settings": settings,
                "regions": pages, "totalRegionCount": len(report["regions"]),
                "humanReviewStatus": "unreviewed", "qualityVerdict": "not-performed",
                "files": _file_records(staging),
            }, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        if destination.exists() or destination.is_symlink():
            return _verify_gallery(destination, settings)
        try:
            os.rename(staging, destination)
        except FileExistsError:
            return _verify_gallery(destination, settings)
    return destination / "index.html"
