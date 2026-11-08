"""Reproducible, timecoded visual evidence sampled from bounded video frames."""

from __future__ import annotations

import hashlib
import html
import json
import os
import tempfile
from bisect import bisect_left
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.backends.ffmpeg.scene import detect_hard_cut_pts
from kumiki_reference_lab.backends.ffmpeg.thumbnails import extract_thumbnails
from kumiki_reference_lab.contracts.analysis import CONTACT_SHEET_VERSION
from kumiki_reference_lab.contracts.frames import FramePts
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict


def select_evidence_indices(
    frames: list[FramePts], cut_pts: tuple[int, ...], limit: int,
) -> dict[int, list[str]]:
    """Prioritize first/last, diverse cut pairs, then widest unsampled gaps."""
    if type(limit) is not int or not 2 <= limit <= 24:
        raise ValueError("thumbnail limit must be between 2 and 24")
    valid = [(frame.ordinal, frame.pts) for frame in frames if frame.pts is not None]
    if not valid:
        raise ProbeError("no frames with valid source PTS in the requested window")

    tagged: dict[int, set[str]] = defaultdict(set)
    tagged[valid[0][0]].add("opening")
    tagged[valid[-1][0]].add("closing")

    # Cut timestamps are source PTS. Do not assume ordinal or nominal FPS.
    pairs: list[tuple[int, int]] = []
    ordered_pts = [value for _, value in valid]
    strictly_increasing = all(a < b for a, b in zip(ordered_pts, ordered_pts[1:]))
    pts_ordinals = {pts: i for i, (_, pts) in enumerate(valid)}
    for pts in sorted(set(cut_pts)):
        # If the decoded presentation timeline is discontinuous/nonmonotonic,
        # only an exact timestamp match provides an unambiguous cut anchor.
        after = (bisect_left(ordered_pts, pts) if strictly_increasing else
                 pts_ordinals.get(pts))
        if after is not None and after > 0:
            if after >= len(valid):
                continue
            pairs.append((valid[after - 1][0], valid[after][0]))
    available_pairs = max(0, (limit - len(tagged)) // 2)
    if len(pairs) > available_pairs:
        # Spread selected cuts over the whole window instead of only early cuts.
        if available_pairs == 1:
            pairs = [pairs[len(pairs) // 2]]
        elif available_pairs == 0:
            pairs = []
        else:
            pairs = [pairs[round(j * (len(pairs) - 1) / (available_pairs - 1))]
                     for j in range(available_pairs)]
    for before, after in pairs:
        if len(tagged | {before: set(), after: set()}) > limit:
            continue
        tagged[before].add("cut-before")
        tagged[after].add("cut-after")

    # Farthest-point selection maximizes coverage of long holds and short clips.
    ordinals = [ordinal for ordinal, _ in valid]
    while len(tagged) < min(limit, len(valid)):
        next_index = max(
            (ordinal for ordinal in ordinals if ordinal not in tagged),
            key=lambda ordinal: (min(abs(ordinal - chosen) for chosen in tagged), -ordinal),
        )
        tagged[next_index].add("overview")
    return {ordinal: sorted(tags) for ordinal, tags in sorted(tagged.items())}


def _html_document(source_name: str, entries: list[dict[str, Any]]) -> str:
    title = html.escape(source_name, quote=True)
    cards = []
    for entry in entries:
        seconds = Fraction(entry["sourceSeconds"]["numerator"],
                           entry["sourceSeconds"]["denominator"])
        safe_path = html.escape(entry["image"], quote=True)
        safe_roles = html.escape(", ".join(entry["roles"]))
        cards.append(
            '<figure><img loading="lazy" src="' + safe_path + '" alt="Reference frame ' +
            str(entry["sampleOrdinal"]) + '"><figcaption><strong>' +
            f'{float(seconds):.3f}s</strong><span>PTS {entry["sourcePts"]} · ' +
            safe_roles + '</span></figcaption></figure>'
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>Reference contact sheet · {title}</title><style>'
        ':root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif}'
        'body{background:#0c1017;color:#e9eef9;margin:0;padding:clamp(16px,4vw,48px)}'
        'header{max-width:1000px;margin:0 auto 28px}h1{font-size:clamp(24px,3vw,38px);margin:0 0 10px}'
        'p{color:#a5b4c8;line-height:1.5}main{display:grid;grid-template-columns:'
        'repeat(auto-fill,minmax(min(100%,340px),1fr));gap:18px;max-width:1600px;margin:auto}'
        'figure{margin:0;background:#17202e;border:1px solid #2a394d;border-radius:13px;overflow:hidden}'
        'img{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:contain;background:black}'
        'figcaption{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px}'
        'span{color:#a5b4c8;font-size:12px;text-align:right}strong{font-variant-numeric:tabular-nums}'
        '</style></head><body><header><h1>Reference contact sheet</h1>'
        f'<p>{title} · Exact source presentation timestamps, sampled frames and possible cut boundaries. '
        'Cut candidates are heuristic; inspect motion before accepting them as edits.</p>'
        '</header><main>' + "".join(cards) + '</main></body></html>\n'
    )


def _verify_existing(destination: Path, settings: dict[str, Any]) -> Path:
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("contact sheet destination exists and is not a regular directory")
    manifest_path = destination / "contact-sheet.json"
    if (not manifest_path.is_file() or manifest_path.is_symlink() or
            manifest_path.stat().st_size > 4_000_000):
        raise ValueError("contact sheet destination exists but has no valid manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("contact sheet destination has an invalid manifest")
    if manifest.get("settings") != settings or manifest.get("schemaVersion") != CONTACT_SHEET_VERSION:
        raise ValueError("contact sheet destination already exists with different settings")
    entries = manifest.get("evidenceFrames")
    if not isinstance(entries, list) or not entries or len(entries) > 24:
        raise ValueError("contact sheet destination has invalid evidence entries")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("contact sheet destination has an invalid evidence entry")
        relative = entry.get("image")
        if not isinstance(relative, str) or not re_full_image(relative):
            raise ValueError("contact sheet destination has an unsafe image path")
        image = destination / relative
        if not image.is_file() or image.is_symlink() or sha256_file(image) != entry.get("sha256"):
            raise ValueError("contact sheet destination contains missing or modified images")
    index = destination / "index.html"
    if (not index.is_file() or index.is_symlink() or
            sha256_file(index) != manifest.get("indexSha256")):
        raise ValueError("contact sheet destination has a missing or modified index")
    return index


def re_full_image(name: str) -> bool:
    """Restrict cached image references to files created by this writer."""
    return (name.startswith("frame-") and name.endswith(".jpg") and
            len(name) == 13 and name[6:9].isdigit())


def build_contact_sheet(
    source: Path, output: Path, *, seconds: int = 30, limit: int = 12,
    width: int = 480, threshold: float = 0.25, ffprobe: str = "ffprobe",
    ffmpeg: str = "ffmpeg", rights_status: str = "review-required",
) -> Path:
    """Write an immutable HTML/JPEG/JSON evidence bundle under `output`."""
    if type(seconds) is not int or not 1 <= seconds <= 120:
        raise ValueError("seconds must be between 1 and 120")
    if type(limit) is not int or not 2 <= limit <= 24:
        raise ValueError("thumbnail limit must be between 2 and 24")
    if type(width) is not int or not 128 <= width <= 800:
        raise ValueError("thumbnail width must be between 128 and 800")
    if not isinstance(threshold, (int, float)) or not 0 < threshold < 1:
        raise ValueError("cut threshold must be finite and between 0 and 1")

    signature = file_signature(source)
    inspected = inspect_source(source, rights_status=rights_status, ffprobe=ffprobe)
    video = inspected["video"]
    rational = video["sourceTimebase"]
    timebase = Fraction(rational["numerator"], rational["denominator"])
    settings = {
        "sourceSha256": inspected["source"]["sha256"],
        "sourceStreamIndex": video["streamIndex"],
        "seconds": seconds, "limit": limit, "width": width,
        "cutThreshold": float(threshold), "ffmpeg": ffmpeg, "ffprobe": ffprobe,
        "samplingAlgorithm": "cut-pairs-and-farthest-ordinals-v1",
    }
    settings_hash = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:16]
    name = f'contact-sheet-{settings["sourceSha256"][:12]}-{settings_hash}'
    output.mkdir(parents=True, exist_ok=True)
    destination = output / name
    if destination.exists() or destination.is_symlink():
        require_unchanged(source, signature)
        return _verify_existing(destination, settings)

    frames = read_frame_pts(source, video["streamIndex"], seconds=seconds, ffprobe=ffprobe)
    cuts = detect_hard_cut_pts(source, video["streamIndex"], seconds=seconds,
                               threshold=threshold, ffmpeg=ffmpeg)
    if cuts.timebase != timebase:
        raise ProbeError("cut detector changed source timebase")
    selection = select_evidence_indices(frames, cuts.pts, limit)
    selected = [frames[ordinal] for ordinal in selection]
    require_unchanged(source, signature)

    # A private staging directory prevents partial bundles from being published.
    with tempfile.TemporaryDirectory(prefix=".contact-", dir=output) as staging_name:
        staging = Path(staging_name)
        images = extract_thumbnails(
            source, staging, video["streamIndex"], list(selection), seconds=seconds,
            width=width, expected_timebase=timebase,
            expected_pts=[int(frame.pts) for frame in selected], ffmpeg=ffmpeg,
        )
        require_unchanged(source, signature)
        evidence: list[dict[str, Any]] = []
        for frame, image in zip(selected, images, strict=True):
            assert frame.pts is not None
            evidence.append({
                "sampleOrdinal": frame.ordinal, "sourcePts": frame.pts,
                "sourceSeconds": as_rational_dict(frame.pts * timebase),
                "roles": selection[frame.ordinal], "image": image.name,
                "sha256": sha256_file(image),
            })
        index = staging / "index.html"
        index.write_text(_html_document(inspected["source"]["fileName"], evidence),
                         encoding="utf-8")
        manifest = {
            "schemaVersion": CONTACT_SHEET_VERSION,
            "settings": settings,
            "sourceTimebase": rational,
            "coverage": "bounded-from-start-not-necessarily-full-video",
            "cutCandidatePts": list(cuts.pts),
            "evidenceFrames": evidence,
            "indexSha256": sha256_file(index),
        }
        (staging / "contact-sheet.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        # Do not overwrite a run another process completed during decoding.
        if destination.exists() or destination.is_symlink():
            return _verify_existing(destination, settings)
        try:
            os.rename(staging, destination)
        except FileExistsError:
            return _verify_existing(destination, settings)
    return destination / "index.html"
