"""Render PTS-grounded still pairs from an authored Kumiki FD1 review map.

The map supplies the editorial pairings; neither timing nor visual similarity
is inferred. Decode from the real streams and verify the actual PTS of each
image before publishing immutable evidence.
"""

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
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.thumbnails import extract_thumbnails
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.core.timebase import as_rational_dict


VERSION = "kumiki.film-map-review.v1"


def _rational(value: Any, field: str) -> Fraction:
    if (not isinstance(value, dict) or set(value) != {"numerator", "denominator"} or
            type(value["numerator"]) is not int or
            type(value["denominator"]) is not int or value["denominator"] <= 0):
        raise ValueError(f"{field} must be a rational timestamp")
    return Fraction(value["numerator"], value["denominator"])


def _read_map(path: Path) -> tuple[dict[str, Any], str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 3_000_000:
        raise ValueError("film review map must be a bounded regular file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schemaVersion") !=
            "kumiki.reference-film-map.v1" or
            data.get("status") != "editorial-anchor-plan-not-a-visual-match" or
            not isinstance(data.get("provenance"), dict) or
            not isinstance(data.get("film"), dict) or
            not isinstance(data.get("anchors"), list) or
            not 1 <= len(data["anchors"]) <= 12):
        raise ValueError("expected a bounded, unapproved reference-film map v1")
    provenance = data["provenance"]
    if any(not isinstance(provenance.get(key), str) or
           len(provenance[key]) != 64 or
           any(c not in "0123456789abcdef" for c in provenance[key])
           for key in ("referenceVideoSha256", "authoredFilmSha256", "handoffSha256")):
        raise ValueError("review map has invalid provenance hashes")
    return data, sha256_file(path)


def _validate_authored_film(mapping: dict[str, Any], path: Path) -> None:
    """Cross-check an editor map against the immutable authored film's scene clock.

    Full FD1 compilation belongs to kumiki-ui. This boundary rejects a map
    whose declared scene, absolute frame, or FPS no longer describes the film.
    """
    film = json.loads(path.read_text(encoding="utf-8"))
    fps = film.get("fps") if isinstance(film, dict) else None
    declaration = mapping["film"]
    if (not isinstance(film, dict) or type(film.get("schemaVersion")) is not int or
            film["schemaVersion"] != 1 or not isinstance(declaration, dict) or
            not isinstance(fps, dict) or
            any(type(fps.get(key)) is not int or fps[key] <= 0 for key in ("num", "den")) or
            film.get("id") != declaration.get("id") or fps != declaration.get("fps") or
            not isinstance(film.get("scenes"), list) or not film["scenes"]):
        raise ValueError("reference map film identity/FPS differs from authored FD1 document")
    scenes: dict[str, tuple[int, int]] = {}
    total = 0
    for scene in film["scenes"]:
        if (not isinstance(scene, dict) or not isinstance(scene.get("id"), str) or
                not scene["id"] or scene["id"] in scenes or
                type(scene.get("durationFrames")) is not int or scene["durationFrames"] <= 0):
            raise ValueError("authored FD1 scenes are invalid or duplicated")
        scenes[scene["id"]] = (total, scene["durationFrames"])
        total += scene["durationFrames"]
    if total != declaration.get("durationFrames"):
        raise ValueError("reference map total frame count differs from authored FD1 film")
    for anchor in mapping["anchors"]:
        if not isinstance(anchor, dict) or not isinstance(anchor.get("film"), dict):
            raise ValueError("reference map is missing a film frame anchor")
        target = anchor["film"]
        scene = scenes.get(target.get("sceneId"))
        offset = target.get("frameOffset")
        frame = target.get("frame")
        if (scene is None or type(offset) is not int or type(frame) is not int or
                not 0 <= offset < scene[1] or frame != scene[0] + offset or
                _rational(target.get("seconds"), "film anchor time") !=
                Fraction(frame * fps["den"], fps["num"])):
            raise ValueError("reference map film anchor disagrees with authored FD1 scene clock")


def _html_page(reference: str, render: str, pairs: list[dict[str, Any]]) -> str:
    panels = []
    for pair in pairs:
        source, film = pair["source"], pair["film"]
        relationship = html.escape(pair["relationship"], quote=True)
        note = html.escape(pair["note"], quote=True)
        panels.append(
            '<section><h2>' + html.escape(pair["id"], quote=True) +
            '</h2><p><strong>' + relationship + '</strong>: ' + note + '</p>'
            '<div class="pair"><figure><img loading="lazy" src="' + source["image"] +
            '" alt="Source reference frame"><figcaption>Source · ' +
            f'{float(_rational(source["seconds"], "source")):.3f}s · PTS {source["pts"]}' +
            '</figcaption></figure><figure><img loading="lazy" src="' + film["image"] +
            '" alt="Authored film frame"><figcaption>Film · ' +
            f'{float(_rational(film["seconds"], "film")):.3f}s · frame {film["frame"]}' +
            '</figcaption></figure></div></section>'
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>FD1 reference-to-film visual review</title><style>'
        ':root{color-scheme:dark;font-family:ui-sans-serif,system-ui,sans-serif}'
        'body{background:#10151f;color:#f2f5fa;margin:0;padding:clamp(16px,4vw,44px)}'
        'header,main{max-width:1440px;margin:auto}section{border-top:1px solid #344255;padding:22px 0}'
        'p{color:#bac6d7;line-height:1.55}h2{font-size:20px}'
        '.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}'
        'figure{margin:0;border:1px solid #344255;border-radius:12px;overflow:hidden}'
        'img{display:block;width:100%;height:auto;background:#05070b}'
        'figcaption{padding:12px;color:#b7c6d9;font-size:13px}'
        '@media(max-width:740px){.pair{grid-template-columns:1fr}}'
        '</style></head><body><header><h1>Source ↔ authored film</h1><p>' +
        html.escape(reference, quote=True) + ' versus ' +
        html.escape(render, quote=True) +
        '. PTS-confirmed frames, deliberately paired by an author. '
        'No pixel match, audio sync or quality approval is implied.</p></header><main>' +
        ''.join(panels) + '</main></body></html>\n'
    )


def _verify_existing(destination: Path, settings: dict[str, Any]) -> Path:
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("film review destination is not a regular directory")
    manifest = destination / "film-map-review.json"
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 1_000_000:
        raise ValueError("film review manifest missing or oversized")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schemaVersion") != VERSION or
            data.get("settings") != settings or
            data.get("status") != "verified-pts-paired-stills" or
            data.get("qualityVerdict") != "not-performed" or
            data.get("pairs") != settings["pairedIdentities"]):
        raise ValueError("film review existing metadata disagrees")
    files = data.get("files")
    expected = {"index.html"}
    for group in ("source", "film"):
        expected.update(f"{group}/frame-{i:03d}.jpg" for i in range(len(settings["pairedIdentities"])))
    if (not isinstance(files, list) or len(files) != len(expected) or
            any(not isinstance(item, dict) or item.get("path") not in expected or
                not isinstance(item.get("sha256"), str) for item in files) or
            {item["path"] for item in files} != expected):
        raise ValueError("film review has an invalid file inventory")
    actual = set()
    for item in destination.rglob("*"):
        if item.is_symlink():
            raise ValueError("film review contains an unsafe symlink")
        if item.is_file():
            actual.add(item.relative_to(destination).as_posix())
    if actual != expected | {"film-map-review.json"}:
        raise ValueError("film review has unexpected or missing files")
    for record in files:
        if sha256_file(destination / record["path"]) != record["sha256"]:
            raise ValueError("film review stills or page were modified")
    return destination / "index.html"


def build_film_map_review(
    review_map: Path, film_document: Path, source: Path, render: Path,
    output: Path, *, seconds: int = 30, width: int = 480,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> Path:
    if type(seconds) is not int or not 1 <= seconds <= 120:
        raise ValueError("review must scan a bounded 1..120 second prefix")
    if type(width) is not int or not 128 <= width <= 800:
        raise ValueError("review JPEG width must be 128..800")
    map_signature = file_signature(review_map)
    mapping, map_hash = _read_map(review_map)
    if film_document.is_symlink() or not film_document.is_file() or film_document.stat().st_size > 8_388_608:
        raise ValueError("authored film must be a bounded regular JSON file")
    film_signature = file_signature(film_document)
    if sha256_file(film_document) != mapping["provenance"]["authoredFilmSha256"]:
        raise ValueError("film map is stale: authored FD1 film bytes changed")
    _validate_authored_film(mapping, film_document)
    signatures = (file_signature(source), file_signature(render))
    inspected = (inspect_source(source, ffprobe=ffprobe), inspect_source(render, ffprobe=ffprobe))
    if inspected[0]["source"]["sha256"] != mapping["provenance"]["referenceVideoSha256"]:
        raise ValueError("reference source bytes do not match the approved mapping input")
    timebases = [_rational(item["video"]["sourceTimebase"], "video timebase") for item in inspected]
    timeline = [read_frame_pts(path, item["video"]["streamIndex"], seconds=seconds, ffprobe=ffprobe)
                for path, item in zip((source, render), inspected, strict=True)]
    source_by_pts = {frame.pts: frame for frame in timeline[0] if frame.pts is not None}
    film_by_ordinal = {frame.ordinal: frame for frame in timeline[1] if frame.pts is not None}
    # One PTS must identify one decoded source image, or the authored mapping
    # is ambiguous even though both possible images report the same time.
    if len(source_by_pts) != sum(frame.pts is not None for frame in timeline[0]):
        raise ValueError("source has duplicate presentation timestamps; cannot select unique PTS")
    identities = []
    source_ordinals, film_ordinals = [], []
    seen_ids = set()
    for anchor in mapping["anchors"]:
        if (not isinstance(anchor, dict) or not isinstance(anchor.get("id"), str) or
                not 1 <= len(anchor["id"]) <= 120 or anchor["id"] in seen_ids or
                not isinstance(anchor.get("source"), dict) or
                not isinstance(anchor.get("film"), dict) or
                anchor.get("reviewStatus") != "not-reviewed" or
                anchor.get("relationship") not in ("inspired-by", "visual-analogy", "intended-match") or
                not isinstance(anchor.get("note"), str) or
                not 8 <= len(anchor["note"].strip()) <= 2_000):
            raise ValueError("film map has invalid editorial anchors")
        seen_ids.add(anchor["id"])
        a, b = anchor["source"], anchor["film"]
        if type(a.get("sourcePts")) is not int or type(b.get("frame")) is not int:
            raise ValueError("film map requires integer source PTS and film frame")
        source_frame, film_frame = source_by_pts.get(a["sourcePts"]), film_by_ordinal.get(b["frame"])
        if source_frame is None or film_frame is None:
            raise ValueError("selected source PTS or film ordinal is absent from decoded prefix")
        source_time = source_frame.pts * timebases[0]
        film_time = film_frame.pts * timebases[1]
        if (source_time != _rational(a.get("seconds"), "source time") or
                film_time != _rational(b.get("seconds"), "film time")):
            raise ValueError("mapped PTS/frame time disagrees with the real encoded stream")
        source_ordinals.append(source_frame.ordinal)
        film_ordinals.append(film_frame.ordinal)
        identities.append({
            "id": anchor["id"], "relationship": anchor["relationship"],
            "note": anchor["note"].strip(),
            "source": {"pts": source_frame.pts, "seconds": as_rational_dict(source_time),
                       "image": f"source/frame-{len(identities):03d}.jpg"},
            "film": {"frame": film_frame.ordinal, "pts": film_frame.pts,
                     "seconds": as_rational_dict(film_time),
                     "image": f"film/frame-{len(identities):03d}.jpg"},
        })
    if (source_ordinals != sorted(set(source_ordinals)) or
            film_ordinals != sorted(set(film_ordinals))):
        raise ValueError("anchors must be unique and monotonically ordered on both video timelines")
    for path, signature in zip((source, render), signatures, strict=True):
        require_unchanged(path, signature)
    require_unchanged(review_map, map_signature)
    require_unchanged(film_document, film_signature)
    settings = {
        "reviewMapSha256": map_hash,
        "filmDocumentSha256": mapping["provenance"]["authoredFilmSha256"],
        "referenceVideoSha256": inspected[0]["source"]["sha256"],
        "renderVideoSha256": inspected[1]["source"]["sha256"],
        "sourceStreamIndex": inspected[0]["video"]["streamIndex"],
        "renderStreamIndex": inspected[1]["video"]["streamIndex"],
        "seconds": seconds, "width": width, "ffmpeg": ffmpeg, "ffprobe": ffprobe,
        "pairedIdentities": identities,
        "method": "exact-source-pts-and-render-ordinal-with-encoded-pts-assertion-v1",
    }
    digest = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:16]
    destination = output / f"film-map-review-{settings['referenceVideoSha256'][:8]}-{settings['renderVideoSha256'][:8]}-{digest}"
    if destination.exists() or destination.is_symlink():
        return _verify_existing(destination, settings)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".film-map-review-", dir=output) as name:
        staging = Path(name)
        for folder, path, record, ordinals, pts, tb in (
            ("source", source, inspected[0], source_ordinals,
             [p["source"]["pts"] for p in identities], timebases[0]),
            ("film", render, inspected[1], film_ordinals,
             [p["film"]["pts"] for p in identities], timebases[1]),
        ):
            (staging / folder).mkdir()
            extract_thumbnails(path, staging / folder, record["video"]["streamIndex"],
                               ordinals, seconds=seconds, width=width,
                               expected_timebase=tb, expected_pts=pts, ffmpeg=ffmpeg)
        for path, signature in zip((source, render), signatures, strict=True):
            require_unchanged(path, signature)
        require_unchanged(review_map, map_signature)
        require_unchanged(film_document, film_signature)
        index = staging / "index.html"
        index.write_text(_html_page(source.name, render.name, identities), encoding="utf-8")
        files = []
        for file in sorted(staging.rglob("*")):
            if file.is_file():
                files.append({"path": file.relative_to(staging).as_posix(),
                              "sha256": sha256_file(file)})
        report = {"schemaVersion": VERSION, "status": "verified-pts-paired-stills",
                  "qualityVerdict": "not-performed", "settings": settings,
                  "pairs": identities, "files": files}
        (staging / "film-map-review.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if destination.exists() or destination.is_symlink():
            return _verify_existing(destination, settings)
        try:
            os.rename(staging, destination)
        except OSError:
            if destination.exists() or destination.is_symlink():
                return _verify_existing(destination, settings)
            raise
    return destination / "index.html"
