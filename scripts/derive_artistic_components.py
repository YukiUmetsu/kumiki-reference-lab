#!/usr/bin/env python3
"""Derive a documented library of measured artistic components.

The driver joins the stored evidence for five video sites:

- a full-runtime census record (preferred: film-level cuts, editorial timing,
  appearance series) or the windowed video summary as a fallback;
- the audio record when one exists;
- catalog metadata (title, studio, category) when it exists.

It then clusters the full-film, non-strobe records on measured timing/texture
features, reports strobe-flagged records as their own ``strobe-textured``
component, and writes concrete per-component numbers plus a reuse recipe.

The measurement trees are read-only. Only these files are written:

- ``research/analysis/artistic-components.json``
- ``research/analysis/artistic-components.md``
- ``research/analysis/<site>/components.json``
- ``docs/artistic-components.md``

Nothing is written into ``videos/``, ``census/``, ``audio/`` or ``stills/``, and
no ``index.json`` is touched. STASH is stills-only and is reported in its own
section without clustering.

Usage::

    PYTHONPATH=src python scripts/derive_artistic_components.py \
        [--root research/analysis] [--sites motiondesignawards shots ...] \
        [--min-cluster-size 25] [--max-k 8] [--top-exemplars 6] \
        [--dry-run] [--json-out research/analysis/artistic-components.json]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from kumiki_reference_lab.acquisition.components import (  # noqa: E402
    CLUSTER_FEATURES,
    FEATURE_SPECS,
    SCHEMA_VERSION,
    build_component_evidence,
    choose_k,
    component_profile,
    extract_features,
    feature_coverage,
    feature_value,
    name_components,
    reuse_recipe,
)

DEFAULT_SITES = (
    "motiondesignawards",
    "shots",
    "aicp",
    "promonews",
    "directorslibrary",
)
STILLS_ONLY_SITES = ("stash",)
CATALOG_LIST_KEYS = ("projects", "clips", "entries", "videos", "items")
CATALOG_ID_KEYS = ("projectId", "clipId", "id", "nid", "postId")
LIMITS = [
    "Cut candidates are not verified edits: an ffmpeg scene-score exceedance "
    "is also produced by fast motion, flashes, dissolves and compression.",
    "A component is a measurement cluster, not a genre, a style verdict or a "
    "quality ranking; the names summarise measured timing only.",
    "Strobe detection is a fixed threshold on sampled luma instability, not a "
    "ground-truth photic-safety or flash-rate measurement.",
    "Rendition and bitrate affect both cut detection and luma/saturation "
    "proxies; the same work at another bitrate can move between components.",
    "Sampling coverage is uneven: promonews and directorslibrary contribute "
    "mostly windowed records, and windowed records are not clustered because "
    "their full-runtime strobe status is unknown.",
    "Windowed evidence covers at most 40 s spread across a runtime, so long "
    "films are under-sampled and short clips are over-represented in that "
    "share; windowed records never enter the component fit.",
    "Audio exists on a subset of records, so loudness and onset bands are "
    "derived from that subset only; per-feature coverage is reported.",
    "Component profiles are descriptive quantiles over observed records; they "
    "do not establish a target, a recommendation or a causal edit effect.",
    "No expert or human review was performed; every number is an automated "
    "proxy over decoded renditions.",
    "The evidence trees were still being written by harvest lanes during "
    "derivation: this is a snapshot of the counts in `generatedFrom`, and a "
    "later run can produce different counts and, at the margin, a different k.",
]
DISTINCTNESS_THRESHOLD = 0.25


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _records(directory: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    unreadable = 0
    if not directory.is_dir():
        return rows, unreadable
    for path in sorted(directory.glob("*.json")):
        payload = _read_json(path)
        if payload is None:
            unreadable += 1
            continue
        payload.setdefault("_sourcePath", path.name)
        rows.append(payload)
    return rows, unreadable


def _video_id(record: Mapping[str, Any]) -> str | None:
    for key in ("id", "clipId", "projectId", "nid", "postId"):
        value = record.get(key)
        if value is not None:
            return str(value)
    return None


def _census_id(record: Mapping[str, Any]) -> str | None:
    block = record.get("record")
    if isinstance(block, Mapping) and block.get("id") is not None:
        return str(block["id"])
    return _video_id(record)


def _sha(record: Mapping[str, Any]) -> str | None:
    source = record.get("source")
    if not isinstance(source, Mapping):
        return None
    for key in ("mediaSha256", "mediaSha256Observed", "storedMediaSha256"):
        value = source.get(key)
        if isinstance(value, str):
            return value
    return None


def _catalog_entries(payload: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return {}
    for key in CATALOG_LIST_KEYS:
        items = payload.get(key)
        if isinstance(items, list):
            index: dict[str, dict[str, Any]] = {}
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                identifier = next(
                    (str(item[field]) for field in CATALOG_ID_KEYS
                     if item.get(field) is not None), None)
                if identifier is not None:
                    index[identifier] = dict(item)
            return index
    return {}


def _site_paths(root: Path, site: str) -> dict[str, Path]:
    base = root / site
    return {
        "videos": base / "videos",
        "census": base / "census",
        "audio": base / "audio",
        "stills": base / "stills",
        "catalog": base / "catalog.json",
    }


def load_site(root: Path, site: str) -> dict[str, Any]:
    paths = _site_paths(root, site)
    videos, video_unreadable = _records(paths["videos"])
    census, census_unreadable = _records(paths["census"])
    audio, audio_unreadable = _records(paths["audio"])
    catalog = _catalog_entries(_read_json(paths["catalog"]))
    return {
        "site": site,
        "videos": videos,
        "census": census,
        "audio": audio,
        "catalog": catalog,
        "unreadable": {
            "videos": video_unreadable,
            "census": census_unreadable,
            "audio": audio_unreadable,
        },
    }


def join_site(bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Join one site's records, one joined record per video/census identity."""
    site = str(bundle["site"])
    catalogue: Mapping[str, Mapping[str, Any]] = bundle["catalog"]
    census_by_id: dict[str, dict[str, Any]] = {}
    census_by_sha: dict[str, dict[str, Any]] = {}
    for record in bundle["census"]:
        identifier = _census_id(record)
        if identifier is not None:
            census_by_id.setdefault(identifier, record)
        sha = _sha(record)
        if sha:
            census_by_sha.setdefault(sha, record)
    audio_by_id: dict[str, dict[str, Any]] = {}
    audio_by_sha: dict[str, dict[str, Any]] = {}
    for record in bundle["audio"]:
        identifier = _census_id(record)
        if identifier is not None:
            audio_by_id.setdefault(identifier, record)
        block = record.get("record")
        sha = block.get("storedMediaSha256") if isinstance(block, Mapping) else None
        sha = sha or _sha(record)
        if isinstance(sha, str):
            audio_by_sha.setdefault(sha, record)

    joined: list[dict[str, Any]] = []
    seen: set[str] = set()
    used_census: set[int] = set()

    def pick_census(identifier: str,
                    sha: str | None) -> dict[str, Any] | None:
        candidate = census_by_id.get(identifier)
        if candidate is None and sha:
            candidate = census_by_sha.get(sha)
        if candidate is None or id(candidate) in used_census:
            return None
        used_census.add(id(candidate))
        return candidate

    def make(video: Mapping[str, Any] | None,
             census_record: Mapping[str, Any] | None,
             identifier: str) -> dict[str, Any]:
        sha = _sha(video or {}) or _sha(census_record or {})
        audio_record = audio_by_id.get(identifier)
        if audio_record is None and sha:
            audio_record = audio_by_sha.get(sha)
        metadata = dict(catalogue.get(identifier) or {})
        if not metadata and video is not None:
            for source in (video.get("catalog"), video.get("clip")):
                if isinstance(source, Mapping):
                    metadata = dict(source)
                    break
        if not metadata and census_record is not None:
            block = census_record.get("record")
            if isinstance(block, Mapping):
                metadata = dict(block)
        title = None
        for key in ("title", "name"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                title = value
                break
        if title is None and video is not None:
            value = video.get("title")
            title = value if isinstance(value, str) else None
        return {
            "site": site,
            "id": identifier,
            "slug": (metadata.get("slug")
                     or (video or {}).get("slug")
                     or ((census_record or {}).get("record") or {}).get("slug")),
            "title": title,
            "catalog": metadata,
            "videoRecord": video,
            "censusRecord": census_record,
            "audioRecord": audio_record,
        }

    for video in bundle["videos"]:
        identifier = _video_id(video)
        if identifier is None:
            continue
        sha = _sha(video)
        census_record = pick_census(identifier, sha)
        if identifier in seen and census_record is None:
            continue
        joined.append(make(video, census_record, identifier))
        seen.add(identifier)
    for census_record in bundle["census"]:
        if id(census_record) in used_census:
            continue
        identifier = _census_id(census_record)
        if identifier is None or identifier in seen:
            continue
        used_census.add(id(census_record))
        joined.append(make(None, census_record, identifier))
        seen.add(identifier)
    joined.sort(key=lambda item: item["id"])
    return joined


# ---------------------------------------------------------------------------
# component assembly
# ---------------------------------------------------------------------------


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def _features_map(row: Mapping[str, Any]) -> dict[str, Any]:
    return {name: _round(feature_value(row, name)) for name in FEATURE_SPECS}


def _vector(row: Mapping[str, Any], stats: Mapping[str, Mapping[str, Any]]) -> list[float]:
    vector: list[float] = []
    for name in CLUSTER_FEATURES:
        value = feature_value(row, name)
        information = stats.get(name) or {}
        median = information.get("median")
        scale = information.get("scale")
        if value is None or median is None or not scale:
            vector.append(0.0)
            continue
        z = (value - median) / scale
        vector.append(max(-4.0, min(4.0, z)))
    return vector


def _centroid_distances(rows: list[Mapping[str, Any]],
                        stats: Mapping[str, Mapping[str, Any]]) -> list[float]:
    vectors = [_vector(row, stats) for row in rows]
    if not vectors:
        return []
    dimension = len(vectors[0])
    centroid = [
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(dimension)
    ]
    distances: list[float] = []
    for vector in vectors:
        total = sum((left - right) ** 2
                    for left, right in zip(vector, centroid))
        distances.append(math.sqrt(total))
    return distances


def _exemplars(rows: list[dict[str, Any]],
               scores: list[float] | None,
               *,
               top: int,
               score_key: str = "silhouette",
               higher_is_better: bool = True) -> list[dict[str, Any]]:
    ranked = list(range(len(rows)))
    if scores is None:
        ranked.sort(key=lambda index: ((rows[index]["id"] or ""),
                                       rows[index]["site"] or ""))
    elif higher_is_better:
        ranked.sort(key=lambda index: (-scores[index],
                                       rows[index]["id"] or "",
                                       rows[index]["site"] or ""))
    else:
        ranked.sort(key=lambda index: (scores[index],
                                       rows[index]["id"] or "",
                                       rows[index]["site"] or ""))
    selected: list[dict[str, Any]] = []
    for index in ranked[:top]:
        row = rows[index]
        selected.append({
            "site": row["site"],
            "id": row["id"],
            "slug": row.get("slug"),
            "title": row.get("title"),
            "durationSeconds": _round(feature_value(row, "durationSeconds"), 3),
            score_key: _round(scores[index], 4) if scores else None,
        })
    return selected


def _component_block(name: str,
                     rows: list[dict[str, Any]],
                     all_rows: list[dict[str, Any]],
                     corpus_size: int,
                     *,
                     scores: list[float] | None,
                     top_exemplars: int,
                     extra: Mapping[str, Any] | None = None,
                     score_key: str = "silhouette",
                     higher_is_better: bool = True) -> dict[str, Any]:
    profile = component_profile(rows, all_rows, corpus_size=corpus_size)
    return {
        "name": name,
        "n": profile["n"],
        "share": _round(profile["share"], 6),
        "sites": profile["sites"],
        "evidenceLevels": profile["evidenceLevels"],
        "profile": profile,
        "recipe": reuse_recipe(profile),
        "exemplars": _exemplars(rows, scores, top=top_exemplars,
                                score_key=score_key,
                                higher_is_better=higher_is_better),
        **dict(extra or {}),
    }


def _stability(rows: list[dict[str, Any]], max_k: int,
               folds: int = 5) -> dict[str, Any]:
    """Deterministic 80 % stride folds: how often does each k win?"""
    wins: Counter[int] = Counter()
    scores: dict[int, list[float]] = {}
    if folds <= 0:
        return {"folds": 0, "winningK": {}, "stable": None,
                "foldDesign": "disabled", "candidateSilhouetteRange": {}}
    for fold in range(folds):
        subset = [row for index, row in enumerate(rows) if index % folds != fold]
        if len(subset) < 12:
            continue
        chosen, info = choose_k(subset, candidates=range(3, max_k + 1))
        wins[chosen] += 1
        for candidate, score in info["candidateSilhouette"].items():
            scores.setdefault(candidate, []).append(score)
    total = sum(wins.values())
    return {
        "folds": total,
        "foldDesign": f"{folds} deterministic 80 % stride folds "
                      "(index % folds != fold)",
        "winningK": {str(key): value for key, value in sorted(wins.items())},
        "stable": len(wins) == 1,
        "candidateSilhouetteRange": {
            str(key): [_round(min(values), 4), _round(max(values), 4)]
            for key, values in sorted(scores.items())
        },
    }


def build_components(rows: list[dict[str, Any]], *,
                     max_k: int,
                     min_cluster_size: int,
                     top_exemplars: int,
                     stability_folds: int = 5) -> dict[str, Any]:
    clustered_rows = [row for row in rows
                      if row["evidenceLevel"] == "full-film" and row["strobe"] is False]
    strobe_rows = [row for row in rows if row["strobe"] is True]
    full_film = len(clustered_rows) + len(strobe_rows)
    windowed = [row for row in rows if row["evidenceLevel"] == "windowed"]

    k, info = choose_k(clustered_rows, candidates=range(3, max_k + 1))
    stats = info.get("standardization") or {}
    labels = info.get("labels") or []
    sil_by_point = info.get("pointSilhouettes") or [0.0] * len(clustered_rows)
    stability = _stability(clustered_rows, max_k, folds=stability_folds)

    raw_clusters: list[tuple[list[int], str]] = []
    for label in sorted(set(labels)):
        indices = [index for index, value in enumerate(labels) if value == label]
        if len(indices) < min_cluster_size:
            continue
        raw_clusters.append((indices, ""))
    profiles = [component_profile(indices, clustered_rows)
                for indices, _ in raw_clusters]
    names = name_components(profiles)

    components: list[dict[str, Any]] = []
    label_names: dict[int, str] = {}
    for (indices, _), name, profile in zip(raw_clusters, names, profiles):
        component_rows = [clustered_rows[index] for index in indices]
        scores = [sil_by_point[index] for index in indices]
        label = labels[indices[0]]
        label_names[label] = name
        components.append(_component_block(
            name, component_rows, clustered_rows, full_film or len(clustered_rows),
            scores=scores, top_exemplars=top_exemplars,
            extra={
                "clusterK": k,
                "silhouette": _round(info.get("silhouette"), 4),
                "medianSilhouette": _round(
                    sum(scores) / len(scores) if scores else None, 4),
            },
        ))

    if strobe_rows:
        distances = _centroid_distances(strobe_rows, stats)
        profile = component_profile(strobe_rows, rows, corpus_size=full_film)
        components.append(_component_block(
            "strobe-textured", strobe_rows, rows, full_film,
            scores=distances, top_exemplars=top_exemplars,
            extra={
                "clusterK": None,
                "silhouette": None,
                "medianSilhouette": None,
                "selection": "closest-to-centroid",
            },
            score_key="centroidDistance",
            higher_is_better=False,
        ))

    components.sort(key=lambda item: (-item["n"], item["name"]))
    return {
        "components": components,
        "k": k,
        "silhouette": info.get("silhouette"),
        "candidateSilhouette": info.get("candidateSilhouette", {}),
        "standardization": stats,
        "clusteredRows": clustered_rows,
        "strobeRows": strobe_rows,
        "windowedRows": windowed,
        "fullFilm": full_film,
        "labels": labels,
        "labelNames": label_names,
        "stability": stability,
        "distinct": (info.get("silhouette") or 0.0) >= DISTINCTNESS_THRESHOLD,
    }


# ---------------------------------------------------------------------------
# stills
# ---------------------------------------------------------------------------


def build_stills_section(root: Path) -> dict[str, Any] | None:
    sections: list[dict[str, Any]] = []
    for site in STILLS_ONLY_SITES:
        directory = root / site / "stills"
        records, unreadable = _records(directory)
        if not records:
            continue
        luma: list[float] = []
        saturation: list[float] = []
        luma_std: list[float] = []
        edge: list[float] = []
        hues: Counter[str] = Counter()
        widths: Counter[int] = Counter()
        for record in records:
            still = record.get("still")
            if not isinstance(still, Mapping):
                continue
            metrics = still.get("metrics")
            if not isinstance(metrics, Mapping):
                continue
            for key, target in (
                ("meanDisplayLumaProxy", luma),
                ("meanSaturationProxy", saturation),
                ("displayLumaStdDev", luma_std),
                ("edgeDensityProxy", edge),
            ):
                value = metrics.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    target.append(float(value))
            hue = metrics.get("dominantHueFamily")
            if isinstance(hue, str):
                hues[hue] += 1
            width = still.get("imageWidth")
            if isinstance(width, int):
                widths[width] += 1

        def band(values: list[float]) -> dict[str, Any]:
            if not values:
                return {"p10": None, "median": None, "p90": None, "coverage": 0}
            ordered = sorted(values)
            return {
                "p10": _round(_quantile(ordered, 0.10), 6),
                "median": _round(_quantile(ordered, 0.50), 6),
                "p90": _round(_quantile(ordered, 0.90), 6),
                "coverage": len(ordered),
            }

        sections.append({
            "site": site,
            "n": len(records),
            "unreadable": unreadable,
            "palette": {
                "meanLuma": band(luma),
                "meanSaturation": band(saturation),
                "lumaStdDev": band(luma_std),
                "edgeDensity": band(edge),
            },
            "dominantHueFamilies": dict(sorted(hues.items())),
            "topWidths": {str(key): value
                          for key, value in widths.most_common(5)},
            "limits": [
                "Stills are published poster images, not video frames: there is "
                "no cut, pacing, motion or audio measurement and no clustering.",
                "One published still per record describes the chosen frame, not "
                "the film's palette over time.",
            ],
        })
    if not sections:
        return None
    return {
        "n": sum(section["n"] for section in sections),
        "sites": sections,
        "note": (
            "Stills-only site(s) are reported as measured palette bands and are "
            "never clustered with video components."
        ),
    }


def _quantile(values: list[float], fraction: float) -> float:
    if len(values) == 1:
        return values[0]
    position = fraction * (len(values) - 1)
    lower = int(math.floor(position))
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


# ---------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------


def _fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{float(value):.{digits}f}{suffix}"
    return str(value)


def _component_table(components: list[dict[str, Any]]) -> str:
    lines = [
        "| component | n | share | median cut rate (cuts/min) | median shot (s) | sites |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for component in components:
        features = component["profile"]["features"]
        lines.append(
            "| `{name}` | {n:,} | {share:.1%} | {rate} | {shot} | {sites} |".format(
                name=component["name"],
                n=component["n"],
                share=component["share"],
                rate=_fmt(features["cutsPerMinute"]["median"]),
                shot=_fmt(features["medianShotSeconds"]["median"]),
                sites=", ".join(f"{site} ({count})" for site, count
                                in component["sites"].items()),
            )
        )
    return "\n".join(lines)


SIGNATURE_FEATURES = (
    "cutsPerMinute",
    "medianShotSeconds",
    "p10ShotSeconds",
    "p90ShotSeconds",
    "burstFraction",
    "shotsUnderHalfSecondPct",
    "paceDriftRatio",
    "flickerLumaPerSecond",
    "durationSeconds",
    "meanLuma",
    "meanSaturation",
    "integratedLufs",
    "onsetPerMinute",
)

NOT_ESTABLISHED = (
    "This component does not establish that these works share a genre, a "
    "market, a mood, a budget, an intent or a quality level. It establishes "
    "that their measured timing/texture values sit near each other.",
    "The cluster does not establish that a cut here is an edit: candidates "
    "include flashes, fast motion, dissolves and compression artefacts.",
    "The profile does not establish a target or a recommendation. The recipe "
    "reports mid-points so a new piece can be placed on the same measured "
    "scale, not told what to become.",
    "Membership does not establish authorship, studio practice or influence; "
    "the feature space contains no names, credits or dates.",
    "A record near a boundary could move to a neighbouring component at a "
    "different k or a different feature set; component edges are measurement "
    "cut-points, not natural kinds.",
)


def _signature_table(profile: Mapping[str, Any]) -> str:
    lines = [
        "| feature | p10 | median | p90 | unit | measured on |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for name in SIGNATURE_FEATURES:
        feature = profile["features"][name]
        if all(feature[stat] is None for stat in ("p10", "median", "p90")):
            continue
        lines.append(
            f"| `{name}` | {_fmt(feature['p10'], 3)} | "
            f"{_fmt(feature['median'], 3)} | {_fmt(feature['p90'], 3)} | "
            f"{feature['unit']} | {feature['coverage']}/{profile['n']} |"
        )
    return "\n".join(lines)


def _recipe_block(recipe: Mapping[str, Any]) -> str:
    targets = recipe["targetCuts"]

    def cut_word(count: Any) -> str:
        if count is None:
            return "not measured"
        return f"{count} cut" if count == 1 else f"{count} cuts"

    def interval(value: Any) -> str:
        return "—" if value is None else f"{_fmt(value, 2)} s"

    lines = [
        "```text",
        "target cuts at the component's measured rate",
        f"  15 s: {cut_word(targets['15s']['cuts'])}   "
        f"({interval(targets['15s']['medianShotSeconds'])} median interval)",
        f"  30 s: {cut_word(targets['30s']['cuts'])}   "
        f"({interval(targets['30s']['medianShotSeconds'])} median interval)",
        f"  60 s: {cut_word(targets['60s']['cuts'])}   "
        f"({interval(targets['60s']['medianShotSeconds'])} median interval)",
        f"  90 s: {cut_word(targets['90s']['cuts'])}   "
        f"({interval(targets['90s']['medianShotSeconds'])} median interval)",
        "",
        "measured shot durations",
        f"  p10 {_fmt(recipe['shotSeconds']['p10Seconds'], 2)} s | "
        f"median {_fmt(recipe['shotSeconds']['medianSeconds'], 2)} s | "
        f"p90 {_fmt(recipe['shotSeconds']['p90Seconds'], 2)} s",
        "",
        "expected pace trajectory",
        f"  {recipe['pace']['trend']} | last-third ÷ first-third drift "
        f"{_fmt(recipe['pace']['driftRatio'], 2)} | "
        f"first third {_fmt(recipe['pace']['firstThirdCutsPerMinute'], 1)} "
        f"cuts/min ({recipe['pace']['firstThirdCoverage']} records) | "
        f"last third {_fmt(recipe['pace']['lastThirdCutsPerMinute'], 1)} "
        f"cuts/min ({recipe['pace']['lastThirdCoverage']} records)",
        "  (each pace figure is a per-record median; they need not reconcile "
        "arithmetically)",
        "",
        "measured loudness band (audio-measured subset)",
        f"  integrated {_fmt(recipe['loudness']['integratedLufs']['p10'], 1)} "
        f"to {_fmt(recipe['loudness']['integratedLufs']['p90'], 1)} LUFS "
        f"(median {_fmt(recipe['loudness']['integratedLufs']['median'], 1)}) | "
        f"LRA median {_fmt(recipe['loudness']['loudnessRangeLu']['median'], 1)} LU | "
        f"true peak median "
        f"{_fmt(recipe['loudness']['truePeakDbfs']['median'], 1)} dBFS",
        "",
        "measured onset band",
        f"  {_fmt(recipe['onset']['onsetsPerMinute']['p10'], 1)} to "
        f"{_fmt(recipe['onset']['onsetsPerMinute']['p90'], 1)} onsets/min "
        f"(median {_fmt(recipe['onset']['onsetsPerMinute']['median'], 1)})",
        "",
        "measured palette band",
        f"  mean luma {_fmt(recipe['palette']['meanLuma']['p10'], 2)}-"
        f"{_fmt(recipe['palette']['meanLuma']['p90'], 2)} | "
        f"mean saturation {_fmt(recipe['palette']['meanSaturation']['p10'], 2)}-"
        f"{_fmt(recipe['palette']['meanSaturation']['p90'], 2)}",
        f"  derived from {recipe['derivedFrom']} records "
        f"(loudness from {recipe['loudness']['integratedLufs']['derivedFrom']}, "
        f"onset from {recipe['onset']['onsetsPerMinute']['derivedFrom']}, "
        f"palette from {recipe['palette']['meanLuma']['derivedFrom']})",
        "```",
    ]
    return "\n".join(lines)


def _exemplar_table(exemplars: list[dict[str, Any]]) -> str:
    lines = [
        "| site | record id | slug | title | duration (s) |",
        "|---|---|---|---|---:|",
    ]
    for exemplar in exemplars:
        lines.append(
            "| {site} | `{id}` | `{slug}` | {title} | {duration} |".format(
                site=exemplar["site"],
                id=exemplar["id"],
                slug=exemplar["slug"] or "—",
                title=(exemplar["title"] or "—").replace("|", "\\|"),
                duration=_fmt(exemplar["durationSeconds"], 1),
            )
        )
    return "\n".join(lines)


def render_docs(evidence: Mapping[str, Any], *, root: Path) -> str:
    components = evidence["components"]
    method = evidence["method"]
    clustered = method["clusteredRecords"]
    full_film = method["fullFilmRecords"]
    silhouette = method.get("silhouette")
    distinct = evidence.get("distinctness", {})
    lines: list[str] = []
    lines.append("# Measured artistic components")
    lines.append("")
    lines.append(
        "These are **measurement clusters** of decoded reference renditions. "
        "Each component groups records whose measured timing/texture values are "
        "close after median/IQR standardization and complete-linkage "
        "agglomeration. A component is a place on a measured scale, not a "
        "genre, a style verdict, a mood or a quality tier. The names below are "
        "assembled from a fixed timing vocabulary by explicit thresholds."
    )
    lines.append("")
    if not distinct:
        lines.append(
            "> **Distinctness warning.** The chosen k scored a mean silhouette "
            f"of {_fmt(silhouette, 3)}, below {DISTINCTNESS_THRESHOLD:.2f}. "
            "Read the components as bands cut through a mostly continuous "
            "distribution, not as well-separated archetypes. The boundaries "
            "are measurement cut-points and neighbouring records are similar."
        )
    elif silhouette is not None and silhouette < 0.35:
        lines.append(
            "> **Weak-separation caveat.** The chosen k scored a mean "
            f"silhouette of {_fmt(silhouette, 3)}, only modestly above the "
            f"{DISTINCTNESS_THRESHOLD:.2f} floor used here. The clusters are "
            "measurably different in their feature medians, but they are not "
            "well-separated archetypes: several components sit on a continuum "
            "of cut rate, and records near a boundary are close to their "
            "neighbours. Treat the names as measurement labels, not types."
        )
    else:
        lines.append(
            f"The chosen k scored a mean silhouette of {_fmt(silhouette, 3)} "
            f"at or above the {DISTINCTNESS_THRESHOLD:.2f} threshold used here. "
            "That is a moderate separation at best; it does not turn the "
            "clusters into natural categories, and records near a boundary "
            "remain close to their neighbouring component."
        )
    lines.append("")
    stability = (method.get("kStability") or {})
    if stability.get("folds") and not stability.get("stable"):
        wins = ", ".join(f"k={key} in {value} fold(s)"
                         for key, value in stability["winningK"].items())
        fold_range = (stability.get("candidateSilhouetteRange") or {}).get(
            str(method.get("k")))
        range_text = ""
        if fold_range:
            range_text = (f" At the chosen k the fold silhouette ranged "
                          f"{_fmt(fold_range[0], 3)}–{_fmt(fold_range[1], 3)}.")
        lines.append(
            "> **k is not stable.** In deterministic 80 % resamples the winning "
            f"k changed ({wins}).{range_text} The component count below is one "
            "defensible cut-point on a continuum, not a discovered number of "
            "types."
        )
        lines.append("")
    lines.append("## At a glance")
    lines.append("")
    lines.append(f"- Clustered records: **{clustered:,}** full-film records with "
                 f"`strobe == false`; **{full_film:,}** full-film records total.")
    lines.append(f"- Windowed records not clustered (full-runtime strobe status "
                 f"unknown): **{method['windowedRecords']:,}**.")
    lines.append(f"- Strobe-flagged records, reported separately: "
                 f"**{method['strobeRecords']:,}**.")
    lines.append(f"- k selected by best mean silhouette over "
                 f"{method['candidateRange']}: **{method['k']}** "
                 f"(silhouette {_fmt(silhouette, 3)}).")
    scores = method.get("candidateSilhouette") or {}
    if scores:
        lines.append(
            "- Candidate silhouettes: "
            + ", ".join(f"k={key}: {_fmt(value, 3)}"
                        for key, value in scores.items())
            + ". Nearby scores mean the k choice is not decisive."
        )
    stability = method.get("kStability") or {}
    if stability.get("folds"):
        wins = ", ".join(f"k={key}: {value} fold(s)"
                         for key, value in stability["winningK"].items())
        lines.append(
            f"- k stability across {stability['folds']} deterministic 80 % "
            f"stride folds: {wins}."
            + ("" if stability.get("stable") else
               " The winning k is not stable across folds, so the component "
               "count is a measurement choice, not a property of the corpus.")
        )
    lines.append(f"- Audio-measured records used for loudness/onset bands: "
                 f"see per-feature coverage below.")
    lines.append("")
    lines.append(_component_table(components))
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        "1. **Join.** Each video record is matched to its full-runtime census "
        "record by record id, with a media SHA-256 fallback. Census is "
        "preferred; a video without a census record falls back to its windowed "
        "summary and is marked `windowed`. Audio and catalog metadata are "
        "joined when present."
    )
    lines.append(
        "2. **Features.** Clustering uses only measured timing/texture: "
        + ", ".join(f"`{name}`" for name in CLUSTER_FEATURES)
        + ". Palette and audio features are reported per component but do not "
        "decide membership."
    )
    lines.append(
        "3. **Robust standardization.** Each feature is centred on the corpus "
        "median and scaled by its interquartile range. When the IQR is 0 the "
        "scale falls back to 1.4826 × median absolute deviation, then to 1.0; "
        "missing values are imputed at the median of the present values "
        "(standardized 0) and counted per feature; values are clipped at ±4."
    )
    lines.append(
        "4. **Complete-linkage agglomeration.** Euclidean distance between "
        "standardized vectors; merge cost is the maximum pairwise distance "
        "between clusters. Ties break on the smaller row index, so input order "
        "fully determines the dendrogram."
    )
    lines.append(
        "5. **k selection.** Mean silhouette is computed for k = "
        f"{method['candidateRange']}; the best score wins and a tie goes to "
        "the smaller k. Above 2,000 rows the silhouette uses a fixed-stride "
        "sample of at most 2,000 rows (no randomness)."
    )
    lines.append(
        "6. **Strobe separation.** Records whose census carries "
        "`strobe == true` never enter the cut-rate clustering; they form one "
        "`strobe-textured` component with its own profile and recipe."
    )
    lines.append("")
    lines.append("## What a component is not")
    lines.append("")
    lines.append("- Not a genre, format, market or audience category.")
    lines.append("- Not a style verdict, a quality ranking or an award signal.")
    lines.append("- Not a claim about intent, authorship, budget or influence.")
    lines.append("- Not a natural kind: it is a cut through a measured "
                 "distribution, and its edge cases are arbitrary.")
    lines.append("- Not a licence to copy a specific work; it is a set of "
                 "aggregate measured numbers.")
    lines.append("")
    lines.append("## Known confounds")
    lines.append("")
    for limit in evidence["limits"]:
        lines.append(f"- {limit}")
    lines.append("")
    lines.append("## How to use a component in practice")
    lines.append("")
    lines.append(
        "1. Pick the target duration first (15/30/60/90 s) and the intended "
        "pace band second: choose a component whose median cut rate and median "
        "shot length bracket the pace you want."
    )
    lines.append(
        "2. Read the reuse recipe as a starting mid-point. Place your own "
        "planned cuts on the same measured scale; if you diverge, you are "
        "deliberately leaving the measured cluster, not failing it."
    )
    lines.append(
        "3. Use the loudness, onset and palette bands as measured context, not "
        "as delivery specifications; they come from a subset and describe "
        "renditions, not masters."
    )
    lines.append(
        "4. State the component and the evidence level (`full-film` or "
        "`windowed`) whenever you cite it, and never cite a component as "
        "evidence of quality or intent."
    )
    lines.append("")
    lines.append("## Components")
    lines.append("")
    for index, component in enumerate(components):
        lines.append(f"### `{component['name']}`")
        lines.append("")
        sites = ", ".join(f"{site} ({count})" for site, count
                         in component["sites"].items()) or "—"
        lines.append(
            f"**n = {component['n']:,}** ({component['share']:.1%} of the "
            f"{full_film:,} full-film records). Sites: {sites}. "
            f"Exemplar ranking: "
            + ("closest to the component centroid."
               if component.get("selection") == "closest-to-centroid"
               else "highest per-record silhouette, tie-break by id.")
        )
        lines.append("")
        lines.append("Measured signature")
        lines.append("")
        lines.append(_signature_table(component["profile"]))
        lines.append("")
        lines.append("Exemplars")
        lines.append("")
        lines.append(_exemplar_table(component["exemplars"]))
        lines.append("")
        lines.append("Reuse recipe")
        lines.append("")
        lines.append(_recipe_block(component["recipe"]))
        lines.append("")
        lines.append(
            "These are measured mid-points, not prescriptions. The arithmetic "
            "is `cuts = round(median cut rate × target seconds / 60)` over "
            f"this component's {component['n']} records; it says where the "
            "cluster sits, not what a new piece should do."
        )
        if any(target["cuts"] == 0 for target in
               component["recipe"]["targetCuts"].values()):
            lines.append("")
            lines.append(
                "A 0-cut target at a short duration is the arithmetic result "
                "of a very low measured rate, not a recommendation for an "
                "empty film; at that duration the shot-duration band is the "
                "more useful number."
            )
        lines.append("")
        lines.append("What this does not establish")
        lines.append("")
        lines.append("- " + NOT_ESTABLISHED[index % len(NOT_ESTABLISHED)])
        lines.append("- " + NOT_ESTABLISHED[(index + 1) % len(NOT_ESTABLISHED)])
        lines.append("- " + NOT_ESTABLISHED[(index + 3) % len(NOT_ESTABLISHED)])
        lines.append("")
    stills = evidence.get("stillsOnly")
    if stills:
        lines.append("## Stills-only site (no clustering)")
        lines.append("")
        lines.append(
            "STASH publishes poster images, not measured video renditions. Its "
            "stills are reported here as a palette-only measurement and are "
            "never clustered with the video components."
        )
        lines.append("")
        for section in stills["sites"]:
            palette = section["palette"]
            lines.append(f"### `{section['site']}` — {section['n']:,} stills")
            lines.append("")
            lines.append("| feature | p10 | median | p90 | measured on |")
            lines.append("|---|---:|---:|---:|---:|")
            for key, label in (
                ("meanLuma", "mean display luma (0–1)"),
                ("meanSaturation", "mean saturation (0–1)"),
                ("lumaStdDev", "display luma std-dev"),
                ("edgeDensity", "edge-density proxy"),
            ):
                band = palette[key]
                lines.append(
                    f"| {label} | {_fmt(band['p10'], 3)} | "
                    f"{_fmt(band['median'], 3)} | {_fmt(band['p90'], 3)} | "
                    f"{band['coverage']:,} |"
                )
            if section["dominantHueFamilies"]:
                hues = ", ".join(
                    f"{name} ({count:,})" for name, count
                    in list(section["dominantHueFamilies"].items())[:6])
                lines.append("")
                lines.append(f"Dominant hue families: {hues}.")
            lines.append("")
            for limit in section["limits"]:
                lines.append(f"- {limit}")
            lines.append("")
    lines.append("## Feature coverage")
    lines.append("")
    lines.append("| feature | present | total | fraction | unit |")
    lines.append("|---|---:|---:|---:|---|")
    for name, coverage in evidence["featureCoverage"].items():
        lines.append(
            f"| `{name}` | {coverage['present']:,} | {coverage['total']:,} | "
            f"{coverage['fraction']:.1%} | {coverage['unit']} |"
        )
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    lines.append(
        "Generated by `scripts/derive_artistic_components.py` from "
        f"`{root}`. Schema `{SCHEMA_VERSION}`. The JSON companion is "
        "`research/analysis/artistic-components.json`; per-site record-to-"
        "component maps are `research/analysis/<site>/components.json`."
    )
    lines.append("")
    return "\n".join(lines)


def render_analysis_markdown(evidence: Mapping[str, Any]) -> str:
    components = evidence["components"]
    method = evidence["method"]
    lines = [
        "# Measured artistic components",
        "",
        "Generated evidence companion. The full documentation, exemplars and "
        "reuse recipes live in [`docs/artistic-components.md`](../../docs/"
        "artistic-components.md).",
        "",
        f"- Schema: `{SCHEMA_VERSION}`",
        f"- Clustered full-film, non-strobe records: **{method['clusteredRecords']:,}**",
        f"- Full-film records (clustered + strobe): **{method['fullFilmRecords']:,}**",
        f"- Windowed records (not clustered): **{method['windowedRecords']:,}**",
        f"- Chosen k: **{method['k']}**, mean silhouette "
        f"**{_fmt(method.get('silhouette'), 3)}**",
        f"- Distinctness: "
        + ("threshold met" if evidence.get("distinctness", {}).get("distinct")
           else "below threshold; read as bands of a continuum")
        + ("" if method.get("kStability", {}).get("stable", True)
           else f"; k unstable across folds "
                f"({method['kStability'].get('winningK')})"),
        "",
        _component_table(components),
        "",
        "## Method",
        "",
        f"- Linkage: {method['linkage']}",
        f"- Standardization: {method['standardization']}",
        f"- Distance: {method['distance']}",
        f"- k selection: {method['kSelection']}",
        f"- Silhouette sampling: {method['silhouetteSampling']}",
        f"- k stability: {method.get('kStability', {}).get('winningK', {})} "
        f"over {method.get('kStability', {}).get('folds', 0)} folds",
        f"- Cluster features: {', '.join(f'`{name}`' for name in CLUSTER_FEATURES)}",
        "",
        "## Limits",
        "",
    ]
    for limit in evidence["limits"]:
        lines.append(f"- {limit}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------


def run(root: Path, *,
        sites: list[str] | None = None,
        max_k: int = 8,
        min_cluster_size: int = 25,
        top_exemplars: int = 6,
        stability_folds: int = 5,
        dry_run: bool = False,
        json_out: Path | None = None,
        docs_out: Path | None = None) -> dict[str, Any]:
    wanted = list(sites or DEFAULT_SITES)
    joined: list[dict[str, Any]] = []
    site_counts: dict[str, Any] = {}
    unreadable: dict[str, Any] = {}
    for site in wanted:
        bundle = load_site(root, site)
        rows = join_site(bundle)
        joined.extend(rows)
        site_counts[site] = {
            "videoRecords": len(bundle["videos"]),
            "censusRecords": len(bundle["census"]),
            "audioRecords": len(bundle["audio"]),
            "joinedRecords": len(rows),
            "withCensus": sum(1 for row in rows if row["censusRecord"]),
            "withAudio": sum(1 for row in rows if row["audioRecord"]),
        }
        unreadable[site] = bundle["unreadable"]

    joined.sort(key=lambda row: (row["site"], row["id"]))
    features = [extract_features(record, site=record["site"]) for record in joined]
    for row, record in zip(features, joined):
        row["title"] = record.get("title")
        row["catalog"] = record.get("catalog")
    coverage = feature_coverage(features)
    built = build_components(
        features,
        max_k=max_k,
        min_cluster_size=min_cluster_size,
        top_exemplars=top_exemplars,
        stability_folds=stability_folds,
    )
    stills = build_stills_section(root)

    method = {
        "linkage": "complete-linkage agglomerative",
        "standardization": "median/IQR; fallback 1.4826*MAD, then unit scale; "
                           "missing values imputed at the median and clipped at ±4",
        "distance": "Euclidean on robust-standardized features",
        "kSelection": "best mean silhouette over candidates; ties to smaller k",
        "silhouetteSampling": "fixed stride, at most 2000 rows",
        "clusterFeatures": list(CLUSTER_FEATURES),
        "excludedFromClustering": [
            "records whose census strobe flag is true",
            "records with no full-runtime census (windowed fallback)",
        ],
        "clusteredRecords": len(built["clusteredRows"]),
        "fullFilmRecords": built["fullFilm"],
        "strobeRecords": len(built["strobeRows"]),
        "windowedRecords": len(built["windowedRows"]),
        "k": built["k"],
        "candidateRange": f"3..{max_k}",
        "silhouette": built["silhouette"],
        "candidateSilhouette": {
            str(key): _round(value, 4)
            for key, value in sorted(built["candidateSilhouette"].items())
        },
        "kStability": built["stability"],
        "standardizationStats": {
            name: {
                "median": _round(info.get("median")),
                "iqr": _round(info.get("iqr")),
                "scale": _round(info.get("scale")),
                "fallback": info.get("fallback"),
            }
            for name, info in built["standardization"].items()
        },
        "minClusterSize": min_cluster_size,
    }
    generated_from = {
        "sites": site_counts,
        "unreadableRecords": unreadable,
        "totalVideoRecords": sum(item["videoRecords"]
                                 for item in site_counts.values()),
        "totalCensusRecords": sum(item["censusRecords"]
                                  for item in site_counts.values()),
        "totalAudioRecords": sum(item["audioRecords"]
                                 for item in site_counts.values()),
        "totalJoinedRecords": len(joined),
        "stillsOnlyRecords": (stills or {}).get("n", 0),
    }
    evidence = build_component_evidence(
        built["components"],
        corpus_size=len(features),
        generated_from=generated_from,
        coverage=coverage,
        method=method,
        limits=LIMITS,
        stills_only=stills,
    )
    evidence["distinctness"] = {
        "threshold": DISTINCTNESS_THRESHOLD,
        "distinct": built["distinct"],
        "silhouette": _round(built["silhouette"], 4),
    }

    analysis_markdown = render_analysis_markdown(evidence)
    docs_markdown = render_docs(evidence, root=root)
    json_path = json_out or (root / "artistic-components.json")
    analysis_path = root / "artistic-components.md"
    docs_path = docs_out or (ROOT / "docs" / "artistic-components.md")

    by_site: dict[str, list[dict[str, Any]]] = {site: [] for site in wanted}
    for row in features:
        by_site.setdefault(row["site"], []).append(row)
    component_of: dict[tuple[str, str], dict[str, Any]] = {}
    # Map each clustered row back to its label and component name.
    index_by_key = {(row["site"], row["id"]): index
                    for index, row in enumerate(built["clusteredRows"])}
    labels = built["labels"]
    label_names = built["labelNames"]

    for row in features:
        key = (row["site"], row["id"])
        if row["strobe"] is True:
            component_of[key] = {
                "component": "strobe-textured",
                "evidenceLevel": row["evidenceLevel"],
                "assigned": True,
                "reason": "strobe flag true",
            }
        elif row["evidenceLevel"] == "full-film" and row["strobe"] is False:
            index = index_by_key.get(key)
            label = labels[index] if index is not None else None
            name = label_names.get(label) if label is not None else None
            component_of[key] = {
                "component": name,
                "evidenceLevel": row["evidenceLevel"],
                "assigned": name is not None,
                "reason": (None if name is not None
                           else "cluster below min-cluster-size"),
            }
        else:
            component_of[key] = {
                "component": None,
                "evidenceLevel": row["evidenceLevel"],
                "assigned": False,
                "reason": "windowed record: full-runtime strobe status unknown",
            }

    site_documents: dict[str, dict[str, Any]] = {}
    for site in wanted:
        records: dict[str, Any] = {}
        for row in sorted(by_site.get(site, []), key=lambda item: item["id"]):
            assignment = component_of.get((site, row["id"]), {})
            records[row["id"]] = {
                "component": assignment.get("component"),
                "evidenceLevel": row["evidenceLevel"],
                "assigned": bool(assignment.get("assigned")),
                "reason": assignment.get("reason"),
                "slug": row.get("slug"),
                "title": row.get("title"),
                "features": _features_map(row),
            }
        counts = Counter(
            entry["component"] for entry in records.values()
            if entry["component"])
        site_documents[site] = {
            "schemaVersion": "kumiki.site-components.v1",
            "site": site,
            "componentCounts": dict(sorted(counts.items())),
            "records": records,
        }

    outputs = {
        "json": json_path,
        "analysisMarkdown": analysis_path,
        "docs": docs_path,
        "sites": {site: root / site / "components.json" for site in wanted},
    }
    if not dry_run:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=False) + "\n",
            encoding="utf-8")
        analysis_path.write_text(analysis_markdown, encoding="utf-8")
        docs_path.parent.mkdir(parents=True, exist_ok=True)
        docs_path.write_text(docs_markdown, encoding="utf-8")
        for site, document in site_documents.items():
            path = outputs["sites"][site]
            path.write_text(
                json.dumps(document, indent=1, sort_keys=False) + "\n",
                encoding="utf-8")

    return {
        "evidence": evidence,
        "built": built,
        "outputs": outputs,
        "siteDocuments": site_documents,
        "sizes": {
            "json": len(json.dumps(evidence, indent=2) + "\n"),
            "analysisMarkdown": len(analysis_markdown),
            "docs": len(docs_markdown),
        },
        "dryRun": dry_run,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="research/analysis",
                        help="evidence root containing <site>/ trees")
    parser.add_argument("--sites", nargs="+", default=list(DEFAULT_SITES),
                        help="video sites to join and cluster")
    parser.add_argument("--min-cluster-size", type=int, default=25,
                        help="components smaller than this are not reported")
    parser.add_argument("--max-k", type=int, default=8,
                        help="largest k considered (candidates are 3..max-k)")
    parser.add_argument("--top-exemplars", type=int, default=6,
                        help="exemplars listed per component")
    parser.add_argument("--stability-folds", type=int, default=5,
                        help="deterministic 80 percent folds used to test k stability")
    parser.add_argument("--dry-run", action="store_true",
                        help="compute and print, write nothing")
    parser.add_argument("--json-out", type=Path, default=None,
                        help="path for the component JSON (default: <root>/"
                             "artistic-components.json)")
    parser.add_argument("--docs-out", type=Path, default=None,
                        help="path for the full documentation markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    options = build_parser().parse_args(argv)
    result = run(
        Path(options.root),
        sites=list(options.sites),
        max_k=options.max_k,
        min_cluster_size=options.min_cluster_size,
        top_exemplars=options.top_exemplars,
        stability_folds=options.stability_folds,
        dry_run=options.dry_run,
        json_out=options.json_out,
        docs_out=options.docs_out,
    )
    evidence = result["evidence"]
    method = evidence["method"]
    built = result["built"]
    print(f"clustered: {method['clusteredRecords']:,} full-film non-strobe; "
          f"full-film {method['fullFilmRecords']:,}; "
          f"windowed {method['windowedRecords']:,}; "
          f"strobe {method['strobeRecords']:,}")
    print(f"k={built['k']} silhouette={_fmt(built['silhouette'], 4)} "
          f"distinct={built['distinct']}")
    print(f"candidate silhouettes: "
          + ", ".join(f"k={key}:{_fmt(value, 3)}" for key, value
                      in sorted(built["candidateSilhouette"].items())))
    for component in evidence["components"]:
        features = component["profile"]["features"]
        print(f"  {component['name']:32} n={component['n']:5,} "
              f"share={component['share']:6.1%} "
              f"cut/min={_fmt(features['cutsPerMinute']['median'], 2):>6} "
              f"shot={_fmt(features['medianShotSeconds']['median'], 2):>6}s")
    print(f"docs bytes: {result['sizes']['docs']:,}; "
          f"analysis markdown bytes: {result['sizes']['analysisMarkdown']:,}; "
          f"json bytes: {result['sizes']['json']:,}")
    if method["silhouette"] is not None and method["silhouette"] < DISTINCTNESS_THRESHOLD:
        print("WARNING: silhouette below 0.25 — components are bands of a "
              "continuum, not well-separated archetypes.")
    if result["dryRun"]:
        print("dry run: no files written")
    else:
        for name, path in result["outputs"].items():
            if name == "sites":
                for site, site_path in path.items():
                    print(f"wrote {site_path} "
                          f"({site_path.stat().st_size:,} bytes)")
            else:
                print(f"wrote {path} ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
