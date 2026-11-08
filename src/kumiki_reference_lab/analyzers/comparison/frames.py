"""Immutable time-aligned side-by-side frame evidence from two local videos."""

from __future__ import annotations

import hashlib
import html
import json
import os
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.comparison.timing import align_source_times
from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.motion.analyze import select_motion_samples
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.thumbnails import extract_thumbnails
from kumiki_reference_lab.contracts.analysis import FRAME_COMPARISON_VERSION
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict


def _side_by_side_html(reference_name: str, candidate_name: str,
                       pairs: list[dict[str, Any]]) -> str:
    title_ref = html.escape(reference_name, quote=True)
    title_cand = html.escape(candidate_name, quote=True)
    cards = []
    for index, pair in enumerate(pairs):
        ref_seconds = Fraction(**pair["referenceSeconds"])
        cand_seconds = Fraction(**pair["candidateSeconds"])
        cards.append(
            '<section><h2>Aligned pair ' + str(index + 1) + '</h2><div class="pair">'
            '<figure><img loading="lazy" src="' + html.escape(pair["referenceImage"], quote=True) +
            '" alt="Reference frame"><figcaption>Reference · ' +
            f'{float(ref_seconds):.3f}s · PTS {pair["referencePts"]}</figcaption></figure>'
            '<figure><img loading="lazy" src="' + html.escape(pair["candidateImage"], quote=True) +
            '" alt="Candidate render frame"><figcaption>Render · ' +
            f'{float(cand_seconds):.3f}s · PTS {pair["candidatePts"]}</figcaption></figure>'
            '</div></section>'
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Kumiki aligned frame review</title><style>'
        ':root{color-scheme:dark;font-family:ui-sans-serif,system-ui,sans-serif}'
        'body{background:#0b1018;color:#ebeff6;margin:0;padding:clamp(16px,4vw,42px)}'
        'header,main{max-width:1400px;margin:auto}h1{font-size:clamp(24px,3vw,38px)}'
        'p{color:#acb8cd;line-height:1.5}section{padding:18px 0;border-top:1px solid #29364a}'
        'h2{font-size:18px;color:#dde8f8} .pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}'
        'figure{margin:0;background:#172231;border:1px solid #2e4055;border-radius:12px;overflow:hidden}'
        'img{display:block;width:100%;height:auto;object-fit:contain;background:black}'
        'figcaption{padding:12px;font-size:14px;color:#c4d0df;font-variant-numeric:tabular-nums}'
        '@media(max-width:740px){.pair{grid-template-columns:1fr}}'
        '</style></head><body><header><h1>Aligned reference and render frames</h1>'
        '<p>Reference: ' + title_ref + ' · Render: ' + title_cand +
        '. Explicitly paired source timestamps; inspect mismatches manually. '
        'No artistic quality grade is implied.</p></header><main>' +
        ''.join(cards) + '</main></body></html>\n'
    )


def _verify_existing(destination: Path, settings: dict[str, Any]) -> Path:
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("frame comparison destination is not a regular directory")
    report_path = destination / "frame-comparison.json"
    if not report_path.is_file() or report_path.is_symlink() or report_path.stat().st_size > 1_000_000:
        raise ValueError("frame comparison has no valid manifest")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("frame comparison manifest is unreadable") from exc
    if (not isinstance(report, dict) or report.get("schemaVersion") != FRAME_COMPARISON_VERSION or
            report.get("settings") != settings):
        raise ValueError("frame comparison has mismatched settings")
    pairs = report.get("pairs")
    if (not isinstance(pairs, list) or not 1 <= len(pairs) <= 12 or
            len(pairs) != len(settings["matchedSampleIdentity"])):
        raise ValueError("frame comparison has invalid evidence pairs")
    if (report.get("status") != "time-aligned-frame-evidence" or
            report.get("matchedPairs") != len(pairs) or
            report.get("unmatchedReferenceSamples") != settings["selectedReferenceCount"] - len(pairs) or
            report.get("unmatchedCandidateSamples") != settings["selectedCandidateCount"] - len(pairs) or
            report.get("qualityVerdict") != "not-performed"):
        raise ValueError("frame comparison has altered review metadata")
    expected = {"index.html"}
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise ValueError("frame comparison contains invalid pair metadata")
        identity = settings["matchedSampleIdentity"][index]
        if any(pair.get(key) != identity[key] for key in identity):
            raise ValueError("frame comparison PTS evidence does not match source selection")
        for folder, key in (("reference", "referenceImage"), ("candidate", "candidateImage")):
            target = f"{folder}/frame-{index:03d}.jpg"
            if pair.get(key) != target:
                raise ValueError("frame comparison contains unsafe image path")
            expected.add(target)
    records = report.get("files")
    if (not isinstance(records, list) or len(records) != len(expected) or
            any(not isinstance(r, dict) or not isinstance(r.get("path"), str)
                for r in records) or
            {r["path"] for r in records} != expected):
        raise ValueError("frame comparison has inconsistent file inventory")
    actual = set()
    for file in destination.rglob("*"):
        if file.is_symlink():
            raise ValueError("frame comparison contains a symbolic link")
        if file.is_file():
            actual.add(file.relative_to(destination).as_posix())
    if actual != expected | {"frame-comparison.json"}:
        raise ValueError("frame comparison contains unexpected or missing files")
    for record in records:
        target = destination / record["path"]
        if not target.is_file() or sha256_file(target) != record.get("sha256"):
            raise ValueError("frame comparison image or HTML was modified")
    return destination / "index.html"


def build_frame_comparison(
    reference: Path, candidate: Path, output: Path, *,
    reference_anchor_ms: int, candidate_anchor_ms: int,
    tolerance_ms: int = 150, time_scale: str = "1",
    seconds: int = 10, samples: int = 10, width: int = 480,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    rights_status: str = "review-required",
) -> Path:
    if type(seconds) is not int or not 1 <= seconds <= 20:
        raise ValueError("frame comparison seconds must be 1..20")
    if type(samples) is not int or not 5 <= samples <= 12:
        raise ValueError("frame comparison sample limit must be 5..12")
    if type(width) is not int or not 128 <= width <= 800:
        raise ValueError("frame comparison thumbnail width must be 128..800")
    signatures = (file_signature(reference), file_signature(candidate))
    manifests = (inspect_source(reference, ffprobe=ffprobe, rights_status=rights_status),
                 inspect_source(candidate, ffprobe=ffprobe, rights_status=rights_status))
    source_frames = []
    timebases = []
    for path, report in zip((reference, candidate), manifests, strict=True):
        video = report["video"]
        tb = video["sourceTimebase"]
        timebase = Fraction(tb["numerator"], tb["denominator"])
        timebases.append(timebase)
        frames = read_frame_pts(path, video["streamIndex"], seconds=seconds, ffprobe=ffprobe)
        source_frames.append(select_motion_samples(frames, samples))
    alignment, matched = align_source_times(
        [int(f.pts) * timebases[0] for f in source_frames[0]],
        [int(f.pts) * timebases[1] for f in source_frames[1]],
        reference_anchor_ms=reference_anchor_ms,
        candidate_anchor_ms=candidate_anchor_ms,
        tolerance_ms=tolerance_ms, time_scale=time_scale,
    )
    if not matched:
        raise ValueError("no frames fall within explicit comparison time tolerance")
    for path, signature in zip((reference, candidate), signatures, strict=True):
        require_unchanged(path, signature)

    settings = {
        "referenceSha256": manifests[0]["source"]["sha256"],
        "candidateSha256": manifests[1]["source"]["sha256"],
        "referenceStreamIndex": manifests[0]["video"]["streamIndex"],
        "candidateStreamIndex": manifests[1]["video"]["streamIndex"],
        "referenceTimebase": manifests[0]["video"]["sourceTimebase"],
        "candidateTimebase": manifests[1]["video"]["sourceTimebase"],
        "seconds": seconds, "samples": samples, "width": width,
        "ffmpeg": ffmpeg, "ffprobe": ffprobe,
        "rightsStatus": rights_status,
        "referenceAnchorSeconds": as_rational_dict(alignment["referenceAnchor"]),
        "candidateAnchorSeconds": as_rational_dict(alignment["candidateAnchor"]),
        "timeScale": as_rational_dict(alignment["scale"]),
        "toleranceSeconds": as_rational_dict(alignment["tolerance"]),
        "alignmentMethod": "explicit-two-anchor-max-cardinality-min-error-monotonic-pts-v1",
        "samplingMethod": "uniform-original-pts-nearest-frame",
        "selectedReferenceCount": len(source_frames[0]),
        "selectedCandidateCount": len(source_frames[1]),
        "matchedSampleIdentity": [{
            "referenceOrdinal": source_frames[0][ri].ordinal,
            "referencePts": int(source_frames[0][ri].pts),
            "referenceSeconds": as_rational_dict(int(source_frames[0][ri].pts) * timebases[0]),
            "candidateOrdinal": source_frames[1][ci].ordinal,
            "candidatePts": int(source_frames[1][ci].pts),
            "candidateSeconds": as_rational_dict(int(source_frames[1][ci].pts) * timebases[1]),
            "signedAlignmentErrorSeconds": as_rational_dict(error),
        } for ci, ri, error in matched],
    }
    digest = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:16]
    destination = output / f"frame-compare-{settings['referenceSha256'][:8]}-{settings['candidateSha256'][:8]}-{digest}"
    output.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        return _verify_existing(destination, settings)

    with tempfile.TemporaryDirectory(prefix=".frame-compare-", dir=output) as name:
        staging = Path(name)
        image_groups = []
        selected_indices = [[ri for ci, ri, error in matched],
                            [ci for ci, ri, error in matched]]
        for channel, (path, report, frames, tb, indices) in enumerate(zip(
                (reference, candidate), manifests, source_frames, timebases,
                selected_indices, strict=True)):
            subfolder = staging / ("reference" if channel == 0 else "candidate")
            subfolder.mkdir()
            selected = [frames[i] for i in indices]
            images = extract_thumbnails(
                path, subfolder, report["video"]["streamIndex"],
                [f.ordinal for f in selected], seconds=seconds, width=width,
                expected_timebase=tb, expected_pts=[int(f.pts) for f in selected],
                ffmpeg=ffmpeg,
            )
            image_groups.append(images)
        for path, signature in zip((reference, candidate), signatures, strict=True):
            require_unchanged(path, signature)
        records = []
        pairs = []
        for pair_index, (ci, ri, error) in enumerate(matched):
            a, b = source_frames[0][ri], source_frames[1][ci]
            image_ref, image_cand = image_groups[0][pair_index], image_groups[1][pair_index]
            relative_ref = image_ref.relative_to(staging).as_posix()
            relative_cand = image_cand.relative_to(staging).as_posix()
            pairs.append({
                "referenceOrdinal": a.ordinal, "referencePts": int(a.pts),
                "referenceSeconds": as_rational_dict(int(a.pts) * timebases[0]),
                "candidateOrdinal": b.ordinal, "candidatePts": int(b.pts),
                "candidateSeconds": as_rational_dict(int(b.pts) * timebases[1]),
                "signedAlignmentErrorSeconds": as_rational_dict(error),
                "referenceImage": relative_ref, "candidateImage": relative_cand,
            })
            records.append({"path": relative_ref, "sha256": sha256_file(image_ref)})
            records.append({"path": relative_cand, "sha256": sha256_file(image_cand)})
        index = staging / "index.html"
        index.write_text(_side_by_side_html(manifests[0]["source"]["fileName"],
                                             manifests[1]["source"]["fileName"], pairs),
                         encoding="utf-8")
        records.append({"path": "index.html", "sha256": sha256_file(index)})
        manifest = {"schemaVersion": FRAME_COMPARISON_VERSION,
                    "settings": settings,
                    "status": "time-aligned-frame-evidence",
                    "qualityVerdict": "not-performed",
                    "matchedPairs": len(pairs),
                    "unmatchedReferenceSamples": len(source_frames[0]) - len(pairs),
                    "unmatchedCandidateSamples": len(source_frames[1]) - len(pairs),
                    "pairs": pairs, "files": sorted(records, key=lambda item: item["path"])}
        (staging / "frame-comparison.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if destination.exists() or destination.is_symlink():
            return _verify_existing(destination, settings)
        try:
            os.rename(staging, destination)
        except FileExistsError:
            return _verify_existing(destination, settings)
    return destination / "index.html"
