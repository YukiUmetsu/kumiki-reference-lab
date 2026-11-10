"""Multi-subject screen-space motion evidence from independently seeded ROI tracks.

This does not detect people, identify individuals, link identity across cuts,
recognize gestures, or recover physical distance. Every ROI remains provisional.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from itertools import combinations
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.subjects.roi import (
    _box_grid, analyze_roi_track, validate_roi_reseeds,
)
from kumiki_reference_lab.analyzers.subjects.review import _validate_report
from kumiki_reference_lab.reviews.character_scene import (
    SCHEMA_VERSION as CHARACTER_SCENE_VERSION, validate_character_scene,
)

SCHEMA_VERSION = "kumiki.multi-character-motion.v1"
CONFIG_VERSION = "kumiki.multi-character-seeds.v1"
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
_ALLOWED_KINDS = frozenset({"human", "animated-human", "animal", "anthropomorphic", "other"})
_VISIBLE = frozenset({"seeded", "manual-reseed", "matched-template"})


def _read_config(path: Path, *, width: int, height: int, radius: int) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("character seeds must be regular UTF-8 JSON under 64 KiB")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate character seed property: {key}")
            result[key] = value
        return result

    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                         parse_constant=lambda value: (_ for _ in ()).throw(
                             ValueError(f"non-finite character seed property: {value}")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid character seed JSON") from exc
    if not isinstance(raw, dict) or set(raw) != {"schemaVersion", "characters"} or raw["schemaVersion"] != CONFIG_VERSION:
        raise ValueError("unsupported character seed schema")
    items = raw["characters"]
    if not isinstance(items, list) or not 2 <= len(items) <= 6:
        raise ValueError("character seeds must contain 2–6 subjects")
    ids: set[str] = set()
    for i, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != {
            "id", "kind", "label", "visualDescription", "seedBox", "reseeds"
        }:
            raise ValueError(f"subject {i} requires exact fields")
        cid = item["id"]
        if type(cid) is not str or not _ID.fullmatch(cid) or cid in ids:
            raise ValueError(f"invalid or duplicate subject id: {cid}")
        ids.add(cid)
        if type(item["kind"]) is not str or item["kind"] not in _ALLOWED_KINDS:
            raise ValueError(f"subject {cid} kind unsupported")
        for field, max_length in (("label", 120), ("visualDescription", 800)):
            text = item[field]
            if type(text) is not str or not 1 <= len(text.strip()) <= max_length:
                raise ValueError(f"subject {cid} {field} must be bounded text")
        _box_grid(item["seedBox"], width, height, radius)
        validate_roi_reseeds(item["reseeds"], width=width, height=height, radius=radius)
    return items


def _pixel_box(obs: dict[str, Any]) -> tuple[float, float, float, float] | None:
    pix = obs["boxPixels"]
    if pix is None:
        return None
    return pix["x"], pix["y"], pix["width"], pix["height"]


def _iou(a: tuple[float, float, float, float],
         b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    area = aw * ah + bw * bh - ix * iy
    return ix * iy / area if area else 0.0


def combine_character_tracks(roster: list[dict[str, Any]],
                             tracks: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Combine validated track evidence. No semantic action labels are invented."""
    if not isinstance(roster, list) or not 2 <= len(roster) <= 6:
        raise ValueError("expected 2–6 character seeds")
    if set(tracks) != {item["id"] for item in roster}:
        raise ValueError("track IDs must match character seeds")
    first = tracks[roster[0]["id"]]
    if first.get("schemaVersion") not in ("kumiki.roi-track.v1", "kumiki.roi-track.v2"):
        raise ValueError("unsupported ROI track version")
    width, height, frames = _validate_report(first)
    if not frames or len(frames) > 120:
        raise ValueError("ROI sample count outside supported bounds")
    identifiers = ("sourceSha256", "sourceStreamIndex", "sourceTimebase",
                   "scanWindowSeconds", "cutCandidatePts")
    for item in roster:
        report = tracks[item["id"]]
        if report.get("schemaVersion") not in ("kumiki.roi-track.v1", "kumiki.roi-track.v2"):
            raise ValueError("unsupported ROI track version")
        other_width, other_height, observations = _validate_report(report)
        if (width, height) != (other_width, other_height):
            raise ValueError("ROI tracks use different analysis grids")
        if any(report.get(k) != first.get(k) for k in identifiers):
            raise ValueError("ROI tracks have different source, clocks, cuts or windows")
        if [(x["sourcePts"], x["sampleOrdinal"]) for x in observations] != [
                (x["sourcePts"], x["sampleOrdinal"]) for x in frames]:
            raise ValueError("ROI tracks must use precisely aligned sampled frames")
    tb = first["sourceTimebase"]
    start, end = frames[0]["sourcePts"], frames[-1]["sourcePts"] + 1
    if start >= end:
        raise ValueError("no valid sampled source time window")
    appearances = []
    sample_rows = []
    pair_counts: dict[str, dict[str, int]] = {}
    prior: dict[tuple[str, str], tuple[float, int, int]] = {}
    ordered_ids = [s["id"] for s in roster]
    for i, canonical in enumerate(frames):
        pts = canonical["sourcePts"]
        observed: dict[str, dict[str, Any]] = {}
        for item in roster:
            cid = item["id"]
            obs = tracks[cid]["observations"][i]
            valid = obs["status"] in _VISIBLE
            observed[cid] = {
                "status": obs["status"],
                "boxNormalized": obs["boxNormalized"] if valid else None,
                "appearanceCorrelation": obs.get("appearanceCorrelation"),
                "segmentIndex": obs.get("segmentIndex", 0) if valid else None,
            }
            if valid:
                pix = obs["boxPixels"]
                appearances.append({
                    "characterId": cid,
                    "startPts": pts, "endPts": pts + 1, "anchorPts": [pts],
                    "visibleTraits": [],
                    "anchorBox": [pix["x"] / width, pix["y"] / height,
                                  pix["width"] / width, pix["height"] / height],
                    "observation": ("Seeded ROI patch observed at this source frame. "
                                    "No semantic character identity or continuous visibility verified."),
                    "confidence": "low",
                })
        pairs = []
        for a, b in combinations(ordered_ids, 2):
            left, right = _pixel_box(tracks[a]["observations"][i]), _pixel_box(tracks[b]["observations"][i])
            key = a, b
            if left is None or right is None:
                prior.pop(key, None)
                continue
            ax, ay, aw, ah = left
            bx, by, bw, bh = right
            dist = math.hypot((ax + aw/2 - bx - bw/2) / width,
                              (ay + ah/2 - by - bh/2) / height)
            current_segments = (observed[a]["segmentIndex"], observed[b]["segmentIndex"])
            previous = prior.get(key)
            trend = "not-comparable"
            if previous is not None and previous[1:] == current_segments:
                difference = dist - previous[0]
                trend = ("image-centers-closer" if difference < -0.02 else
                         "image-centers-farther" if difference > 0.02 else
                         "stable-within-tolerance")
            # Across a cut, track-roi suppresses positions until a manual reseed.
            # Even if the manual seed is on the next sampled frame, that discontinuity
            # is not independent evidence of stable character identity.
            if (tracks[a]["observations"][i]["status"] == "manual-reseed" or
                    tracks[b]["observations"][i]["status"] == "manual-reseed"):
                trend = "not-comparable"
            prior[key] = dist, *current_segments
            ident = f"{a}:{b}"
            counts = pair_counts.setdefault(ident, {"coVisibleSamples": 0, "overlapSamples": 0,
                                                      "closerSteps": 0, "fartherSteps": 0})
            counts["coVisibleSamples"] += 1
            intersection = _iou(left, right)
            if intersection > 0:
                counts["overlapSamples"] += 1
            if trend == "image-centers-closer":
                counts["closerSteps"] += 1
            elif trend == "image-centers-farther":
                counts["fartherSteps"] += 1
            pairs.append({
                "subjectA": a, "subjectB": b,
                "centerDistanceNormalized": round(dist, 6),
                "boxOverlapIoU": round(intersection, 6),
                "horizontalOrder": "a-left-of-b" if ax + aw/2 < bx + bw/2
                                   else "b-left-of-a" if bx + bw/2 < ax + aw/2
                                   else "same-image-x-center",
                "changeFromPreviousSample": trend,
                "interpretation": "screen-space-proxy-not-a-physical-interaction",
            })
        sample_rows.append({"sourcePts": pts, "sampleOrdinal": canonical["sampleOrdinal"],
                            "characters": observed, "pairwise": pairs})
    scene = {
        "schemaVersion": CHARACTER_SCENE_VERSION,
        "sourceSha256": first["sourceSha256"],
        "sourceStreamIndex": first["sourceStreamIndex"],
        "sourceTimebase": tb,
        "reviewer": {"kind": "model", "id": "kumiki-seeded-roi-multitracker"},
        "window": {"startPts": start, "endPts": end, "coverage": "partial-window"},
        "characters": [
            {k: item[k] for k in ("id", "kind", "label", "visualDescription")}
            for item in roster
        ],
        "appearances": appearances,
        "actions": [], "utterances": [], "identityClaims": [],
    }
    validate_character_scene(scene)
    report = {
        "schemaVersion": SCHEMA_VERSION, "sourceSha256": first["sourceSha256"],
        "sourceStreamIndex": first["sourceStreamIndex"],
        "sourceTimebase": tb,
        "analysisResolution": {"width": width, "height": height},
        "cutCandidatePts": first["cutCandidatePts"],
        "sampleCount": len(frames), "characterCount": len(roster),
        "visibleCharacterFrameCount": len(appearances),
        "pairSummary": [{"pair": key, **values} for key, values in sorted(pair_counts.items())],
        "samples": sample_rows,
        "identityContinuity": "unverified-after-cut-loss-or-manual-reseed",
        "evidenceStatus": "seeded-image-template-tracking-not-semantic-recognition",
        "limitations": [
            "Character labels and descriptions are reviewer-supplied, not recognized from pixels.",
            "Each appearance is a single source-PTS sample, not proof of continuous onscreen presence.",
            "Image-center movement and bounding-box overlap do not establish character interaction, 3D depth or camera motion.",
            "Template correlations are not calibrated identity confidences; occlusion and cuts terminate automatic tracking.",
            "Independent manual reseeds are not verified same-character identities.",
        ],
    }
    return scene, report


def run_character_motion(source: Path, config: Path, out: Path, *, seconds: int = 10,
                         max_samples: int = 40, width: int = 160, height: int = 90,
                         radius: int = 12, correlation: float = 0.62,
                         cut_threshold: float = 0.25, ffmpeg: str = "ffmpeg",
                         ffprobe: str = "ffprobe",
                         rights_status: str = "review-required") -> Path:
    """Run existing bounded ROI tracker for each seeded subject and publish atomically."""
    if out.exists() or out.is_symlink():
        raise ValueError("output must be a new, nonexisting directory")
    roster = _read_config(config, width=width, height=height, radius=radius)
    tracks = {}
    for item in roster:
        tracks[item["id"]] = analyze_roi_track(
            source, tuple(item["seedBox"]), seconds=seconds, max_samples=max_samples,
            width=width, height=height, radius=radius, correlation=correlation,
            cut_threshold=cut_threshold, ffmpeg=ffmpeg, ffprobe=ffprobe,
            rights_status=rights_status, reseeds=item["reseeds"],
        )
    scene, report = combine_character_tracks(roster, tracks)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-character-motion-", dir=out.parent) as directory:
        temp = Path(directory)
        (temp / "roi-tracks").mkdir()
        for cid, track in tracks.items():
            (temp / "roi-tracks" / f"{cid}.json").write_text(
                json.dumps(track, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (temp / "character-scene.json").write_text(
            json.dumps(scene, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (temp / "character-motion.json").write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, out)
    return out / "character-motion.json"
