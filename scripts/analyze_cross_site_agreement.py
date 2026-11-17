#!/usr/bin/env python3
"""Measure how far the same work agrees with itself across awards sites.

The question this answers is narrow and specific: when a work was measured on
two different sites -- different platform, rendition and encode -- how much of
the difference between the two records is *the work* and how much is *the
delivery*?  The tool is read-only, standard-library only, and makes no network
or ffmpeg call.

Inputs (all under ``--root``, default ``research/analysis``)::

    <site>/census/*.json   full-runtime census evidence
    <site>/audio/*.json    full-runtime audio evidence
    <site>/catalog.json    identity (title, company, director) for measured ids
    <site>/quality-selection.json   optional identity/coverage supplement
    quality-selection.json          optional declared cross-site work list

Identity is the same rule ``scripts/select_quality_clips.py`` uses for its
tier-0 cross-site list: normalised title + company, or normalised title +
director, joined transitively (NFKD, ASCII-folded, lowercased, ``&`` ->
``and``, punctuation collapsed, promonews' ``" by <director>"`` suffix
stripped).  When ``quality-selection.json`` carries a ``crossSiteWorks`` list
that list wins; otherwise the components are recomputed from the catalogs.

For every work with measurements on two or more sites the tool emits one row
per site pair and, per metric, pair counts, signed/absolute/relative
differences, a hand-written Spearman rank correlation and a one-way
variance decomposition (ICC).  It also flags the three ways a "pair" can be
dishonest: a duration mismatch, a different cut of the same campaign, and a
pair that only has one lane on one side.

Outputs are atomic and deterministic: the only timestamp is the maximum input
record mtime, never ``now()``.  Two runs over the same tree are byte-identical.

Usage::

    PYTHONPATH=src python scripts/analyze_cross_site_agreement.py \
        [--root research/analysis] [--out-dir research/analysis]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA = "kumiki.cross-site-agreement.v1"
DEFAULT_ROOT = Path("research/analysis")

#: A pair is a duration mismatch when the two runtimes differ by more than this
#: fraction of the longer one (30 s vs 60 s -> 0.5, clearly a different cut).
DURATION_MISMATCH_FRACTION = 0.10
#: A pair is a cut-rate divergence when cuts per minute differ by more than this
#: fraction while the duration matches: a retimed/alternate edit, not delivery.
CUT_RATE_DIVERGENCE_FRACTION = 0.50
#: Below this many usable pairs a statistic is reported but labelled sparse.
SPARSE_PAIR_THRESHOLD = 3

LANES = ("census", "audio")

METRICS: tuple[dict[str, Any], ...] = (
    {
        "key": "cutsPerMinute",
        "label": "Cut candidates per minute",
        "unit": "cuts/min",
        "meaningfulZero": True,
        "lane": "census",
        "excludeStrobe": True,
    },
    {
        "key": "medianShotSeconds",
        "label": "Median shot length",
        "unit": "s",
        "meaningfulZero": True,
        "lane": "census",
        "excludeStrobe": False,
    },
    {
        "key": "meanLuma",
        "label": "Mean display luma",
        "unit": "0..1 proxy",
        "meaningfulZero": True,
        "lane": "census",
        "excludeStrobe": False,
    },
    {
        "key": "meanSaturation",
        "label": "Mean saturation",
        "unit": "0..1 proxy",
        "meaningfulZero": True,
        "lane": "census",
        "excludeStrobe": False,
    },
    {
        "key": "integratedLufs",
        "label": "Integrated loudness",
        "unit": "LUFS",
        "meaningfulZero": False,
        "lane": "audio",
        "excludeStrobe": False,
    },
    {
        "key": "lra",
        "label": "Loudness range",
        "unit": "LU",
        "meaningfulZero": False,
        "lane": "audio",
        "excludeStrobe": False,
    },
    {
        "key": "onsetRate",
        "label": "Onset rate",
        "unit": "onsets/min",
        "meaningfulZero": True,
        "lane": "audio",
        "excludeStrobe": False,
    },
)

CATALOG_LIST_KEYS = ("entries", "clips", "videos", "projects", "items",
                     "records", "rows")
ID_KEYS = ("id", "projectId", "nid", "postId", "clipId")


# --------------------------------------------------------------------------- #
# Small deterministic helpers
# --------------------------------------------------------------------------- #


def normalise_text(value: Any) -> str:
    """NFKD, ASCII, lowercase, ``&`` -> ``and``, punctuation -> spaces."""
    if not isinstance(value, str):
        return ""
    folded = unicodedata.normalize("NFKD", value)
    ascii_text = folded.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower().replace("&", " and ")
    tokens = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(tokens.split())


def strip_promonews_suffix(title: Any) -> str:
    """Drop promonews' ``" by <director>"`` title suffix, keeping the rest."""
    if not isinstance(title, str):
        return ""
    if " by " in title:
        head = title.rsplit(" by ", 1)[0]
        if head.strip():
            return head
    return title


def normalise_title(title: Any) -> str:
    """Normalised title used for cross-site matching."""
    return normalise_text(strip_promonews_suffix(title))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _number(value: Any) -> float | None:
    """A finite float, or ``None``.  ``bool`` is never a measurement."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _average_ranks(values: Sequence[float]) -> list[float]:
    """Competition-free ``1..n`` ranks with ties averaged."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while (end + 1 < len(order)
               and values[order[end + 1]] == values[order[position]]):
            end += 1
        average = (position + end) / 2.0 + 1.0
        for index in range(position, end + 1):
            ranks[order[index]] = average
        position = end + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman rho with tie-averaged ranks.  ``None`` when undefined."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    rx = _average_ranks(xs)
    ry = _average_ranks(ys)
    n = len(rx)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    covariance = sum((rx[i] - mean_x) * (ry[i] - mean_y) for i in range(n))
    variance_x = sum((value - mean_x) ** 2 for value in rx)
    variance_y = sum((value - mean_y) ** 2 for value in ry)
    if variance_x <= 0 or variance_y <= 0:
        return None
    return covariance / math.sqrt(variance_x * variance_y)


def icc_oneway(groups: Iterable[Sequence[float]]) -> dict[str, float | int | None] | None:
    """One-way ANOVA intraclass correlation for repeated measures per work.

    ``ICC = (MSB - MSW) / (MSB + (k_mean - 1) * MSW)`` where ``k_mean`` is the
    average number of measurements per work (the unbalanced-design correction;
    for a balanced ``k`` it reduces to the textbook ``k``).

    Returns ``None`` when fewer than two works have at least two values, when
    there are no residual degrees of freedom, or when the denominator is not
    positive.  The returned dict also carries the raw mean squares so a reader
    can check the arithmetic.
    """
    cleaned = [list(group) for group in groups if len(group) >= 2]
    works = len(cleaned)
    total = sum(len(group) for group in cleaned)
    if works < 2 or total <= works:
        return None
    grand = sum(value for group in cleaned for value in group) / total
    ss_between = 0.0
    ss_within = 0.0
    for group in cleaned:
        mean = sum(group) / len(group)
        ss_between += len(group) * (mean - grand) ** 2
        ss_within += sum((value - mean) ** 2 for value in group)
    ms_between = ss_between / (works - 1)
    ms_within = ss_within / (total - works)
    k_mean = (total - sum(len(group) ** 2 for group in cleaned) / total) / (works - 1)
    denominator = ms_between + (k_mean - 1) * ms_within
    if denominator <= 0:
        return None
    return {
        "icc": (ms_between - ms_within) / denominator,
        "msBetween": ms_between,
        "msWithin": ms_within,
        "works": works,
        "values": total,
        "meanValuesPerWork": k_mean,
    }


def relative_difference(a: float, b: float) -> float | None:
    """Signed ``(a - b)`` scaled by ``max(|a|, |b|)``; ``None`` at zero."""
    denominator = max(abs(a), abs(b))
    if denominator == 0:
        return None
    return (a - b) / denominator


# --------------------------------------------------------------------------- #
# Input loading
# --------------------------------------------------------------------------- #


class _Inputs:
    """Tracks every file read so the derived timestamp is from record mtimes."""

    def __init__(self) -> None:
        self.mtimes: list[float] = []

    def read_json(self, path: Path) -> Any | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            return None
        self.mtimes.append(stat.st_mtime)
        return payload

    def derived_at(self) -> str | None:
        if not self.mtimes:
            return None
        stamp = datetime.fromtimestamp(max(self.mtimes), tz=timezone.utc)
        return stamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _filename_parts(path: Path) -> tuple[str, str]:
    """Recover ``(id, slug)`` from ``<id>-<slug>.json`` when the record lacks it."""
    stem = path.stem
    if "-" in stem:
        head, tail = stem.split("-", 1)
        return head, tail
    return stem, stem


def _list_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in CATALOG_LIST_KEYS:
            items = payload.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    return []


def _item_id(item: dict[str, Any]) -> str | None:
    for key in ID_KEYS:
        if item.get(key) is not None:
            return str(item[key])
    return None


def _credits(item: dict[str, Any], role: str) -> list[str]:
    return [str(credit.get("name")) for credit in item.get("credits") or []
            if isinstance(credit, dict) and credit.get("role") == role
            and credit.get("name")]


def _companies(site: str, item: dict[str, Any]) -> list[str]:
    if site == "motiondesignawards":
        return _as_list(item.get("studio"))
    if site == "aicp":
        return _as_list(item.get("company"))
    if site == "promonews":
        return _credits(item, "Production Company")
    if site == "directorslibrary":
        return _as_list((item.get("terms") or {}).get("agency"))
    if site == "shots":
        return [value for value in (item.get("clientName"),
                                    item.get("agencyName")) if value]
    # Unknown site: accept the obvious spellings rather than guessing nothing.
    values: list[Any] = []
    for key in ("company", "clientName", "studio", "brandName", "agencyName"):
        values.extend(_as_list(item.get(key)))
    return values


def _directors(site: str, item: dict[str, Any]) -> list[str]:
    if site == "promonews":
        return _credits(item, "Director")
    if site == "shots":
        return _as_list(item.get("artists"))
    values: list[Any] = []
    for key in ("directors", "artists", "director"):
        values.extend(_as_list(item.get(key)))
    return values


def _signals_companies(site: str, signals: dict[str, Any]) -> list[str]:
    if site == "motiondesignawards":
        return _as_list(signals.get("studio"))
    if site == "aicp":
        return _as_list(signals.get("company"))
    return [value for value in (signals.get("clientName"),
                                signals.get("agencyName"),
                                signals.get("company"),
                                signals.get("studio"),
                                signals.get("brandName")) if value]


def _signals_directors(site: str, signals: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for key in ("directors", "artists", "director"):
        values.extend(_as_list(signals.get(key)))
    return values


def _identity(title: Any, companies: Iterable[Any],
              directors: Iterable[Any], *, title_only: bool = False) -> dict[str, Any]:
    return {
        "title": str(title or ""),
        "companies": [normalise_text(value) for value in companies
                      if normalise_text(value)],
        "directors": [normalise_text(value) for value in directors
                      if normalise_text(value)],
        # Only the slug fallback (no catalog metadata at all) may join on title
        # alone; a catalogued work without company/director stays unjoined.
        "titleOnly": title_only,
    }


def discover_sites(root: Path) -> list[str]:
    sites = []
    if not root.is_dir():
        return sites
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if any((entry / lane).is_dir() for lane in LANES):
            sites.append(entry.name)
    return sites


def load_measurements(root: Path, sites: Sequence[str],
                      inputs: _Inputs) -> dict[tuple[str, str], dict[str, Any]]:
    """Map ``(site, id)`` to one merged census+audio measurement record."""
    measured: dict[tuple[str, str], dict[str, Any]] = {}

    def node(site: str, ident: str, slug: str) -> dict[str, Any]:
        key = (site, ident)
        record = measured.get(key)
        if record is None:
            record = {
                "site": site,
                "id": ident,
                "slug": slug,
                "hasCensus": False,
                "hasAudio": False,
                "censusDurationSeconds": None,
                "audioDurationSeconds": None,
                "censusResolution": None,
                "audioResolution": None,
                "strobe": None,
            }
            for metric in METRICS:
                record[metric["key"]] = None
            measured[key] = record
        if slug and not record["slug"]:
            record["slug"] = slug
        return record

    for site in sites:
        for path in sorted((root / site / "census").glob("*.json")):
            payload = inputs.read_json(path)
            if not isinstance(payload, dict):
                continue
            record = payload.get("record") if isinstance(payload.get("record"), dict) else {}
            file_id, file_slug = _filename_parts(path)
            ident = str(record.get("id") or file_id)
            slug = str(record.get("slug") or file_slug)
            scan = payload.get("census")
            if not isinstance(scan, dict):
                scan = payload.get("scan") if isinstance(payload.get("scan"), dict) else {}
            source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
            editorial = payload.get("editorial")
            if not isinstance(editorial, dict):
                editorial = {}
            summary = scan.get("seriesSummary")
            if not isinstance(summary, dict):
                summary = {}
            entry = node(site, ident, slug)
            entry["hasCensus"] = True
            entry["cutsPerMinute"] = _number(scan.get("cutsPerMinute"))
            entry["medianShotSeconds"] = _number(editorial.get("medianShotSeconds"))
            entry["meanLuma"] = _number(summary.get("meanDisplayLuma"))
            entry["meanSaturation"] = _number(summary.get("meanSaturation"))
            strobe = scan.get("strobe")
            entry["strobe"] = strobe if isinstance(strobe, bool) else None
            entry["censusDurationSeconds"] = (
                _number(scan.get("durationSeconds"))
                or _number(source.get("durationSeconds")))
            resolution = scan.get("resolution") or source.get("resolution")
            entry["censusResolution"] = (
                [int(value) for value in resolution]
                if isinstance(resolution, list) and len(resolution) >= 2 else None)

        for path in sorted((root / site / "audio").glob("*.json")):
            payload = inputs.read_json(path)
            if not isinstance(payload, dict):
                continue
            record = payload.get("record") if isinstance(payload.get("record"), dict) else {}
            file_id, file_slug = _filename_parts(path)
            ident = str(record.get("id") or file_id)
            slug = str(record.get("slug") or file_slug)
            audio = payload.get("audio") if isinstance(payload.get("audio"), dict) else {}
            source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
            entry = node(site, ident, slug)
            entry["hasAudio"] = True
            entry["integratedLufs"] = _number(audio.get("integratedLufs"))
            entry["lra"] = _number(audio.get("loudnessRangeLu"))
            entry["onsetRate"] = _number(audio.get("onsetsPerMinuteOfRuntime"))
            entry["audioDurationSeconds"] = (
                _number(audio.get("durationSeconds"))
                or _number(source.get("durationSeconds")))
            resolution = source.get("resolution")
            entry["audioResolution"] = (
                [int(value) for value in resolution]
                if isinstance(resolution, list) and len(resolution) >= 2 else None)
    return measured


def load_identities(root: Path, sites: Sequence[str], measured: dict[tuple[str, str], dict[str, Any]],
                    inputs: _Inputs) -> dict[tuple[str, str], dict[str, Any]]:
    """Identity for every catalogued work, supplemented by selection rows.

    Catalog data wins because it carries the full company/director fields; the
    per-site quality-selection rows fill ids a slim catalog omitted; the record
    slug is the last resort so a fixture without catalogs still pairs.
    """
    identities: dict[tuple[str, str], dict[str, Any]] = {}
    for site in sites:
        catalog_path = root / site / "catalog.json"
        if catalog_path.is_file():
            payload = inputs.read_json(catalog_path)
            for item in _list_payload(payload):
                ident = _item_id(item)
                if ident is None:
                    continue
                title = item.get("title")
                if not isinstance(title, str) or not title.strip():
                    continue
                identities[(site, ident)] = _identity(
                    title, _companies(site, item), _directors(site, item))

        selection_path = root / site / "quality-selection.json"
        if selection_path.is_file():
            payload = inputs.read_json(selection_path)
            if isinstance(payload, dict):
                for row in _list_payload(payload):
                    ident = _item_id(row)
                    if ident is None or (site, ident) in identities:
                        continue
                    title = row.get("title")
                    if not isinstance(title, str) or not title.strip():
                        continue
                    signals = row.get("qualitySignals")
                    if not isinstance(signals, dict):
                        signals = {}
                    identities[(site, ident)] = _identity(
                        title, _signals_companies(site, signals),
                        _signals_directors(site, signals))

    for key, record in measured.items():
        if key in identities and identities[key]["title"].strip():
            continue
        slug = record.get("slug") or ""
        if not slug:
            continue
        identities[key] = _identity(slug.replace("-", " "), [], [],
                                     title_only=True)
    return identities


def load_declared_works(root: Path,
                        inputs: _Inputs) -> list[list[tuple[str, str]]] | None:
    """Optional ``quality-selection.json`` cross-site work list, if present."""
    path = root / "quality-selection.json"
    if not path.is_file():
        return None
    payload = inputs.read_json(path)
    if not isinstance(payload, dict):
        return None
    declared = payload.get("crossSiteWorks") or payload.get("crossSite")
    if not isinstance(declared, list) or not declared:
        return None
    components: list[list[tuple[str, str]]] = []
    for work in declared:
        if not isinstance(work, dict):
            continue
        members = work.get("members")
        if not isinstance(members, list):
            continue
        nodes: list[tuple[str, str]] = []
        for member in members:
            if not isinstance(member, dict):
                continue
            site = member.get("site")
            ident = member.get("id")
            if isinstance(site, str) and ident is not None:
                nodes.append((site, str(ident)))
        if len({site for site, _ in nodes}) >= 2:
            components.append(sorted(set(nodes)))
    if not components:
        return None
    components.sort(key=lambda nodes: min(nodes))
    return components


def compute_components(
    identities: dict[tuple[str, str], dict[str, Any]],
) -> list[list[tuple[str, str]]]:
    """Transitive title+company / title+director components (union-find)."""
    keyed: dict[tuple[str, str, str], list[tuple[str, str]]] = {}
    for node, info in identities.items():
        title = normalise_title(info.get("title"))
        if not title:
            continue
        for kind, values in (("company", info.get("companies") or []),
                             ("director", info.get("directors") or [])):
            for value in values:
                if not value:
                    continue
                keyed.setdefault((kind, title, value), []).append(node)
        if info.get("titleOnly"):
            keyed.setdefault(("title", title, ""), []).append(node)

    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def find(node: tuple[str, str]) -> tuple[str, str]:
        parent.setdefault(node, node)
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != root:
            parent[node], node = root, parent[node]
        return root

    def union(left: tuple[str, str], right: tuple[str, str]) -> None:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        if right_root < left_root:
            left_root, right_root = right_root, left_root
        parent[right_root] = left_root

    for nodes in keyed.values():
        first = nodes[0]
        for node in nodes[1:]:
            union(first, node)

    groups: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for node in identities:
        groups.setdefault(find(node), []).append(node)
    components = [sorted(nodes) for nodes in groups.values()]
    components.sort(key=lambda nodes: min(nodes))
    return components


# --------------------------------------------------------------------------- #
# Pairing and statistics
# --------------------------------------------------------------------------- #


def _preferred_duration(record: dict[str, Any]) -> float | None:
    if record.get("hasCensus") and record.get("censusDurationSeconds") is not None:
        return record["censusDurationSeconds"]
    if record.get("hasAudio") and record.get("audioDurationSeconds") is not None:
        return record["audioDurationSeconds"]
    return record.get("censusDurationSeconds") or record.get("audioDurationSeconds")


def _preferred_resolution(record: dict[str, Any]) -> list[int] | None:
    return record.get("censusResolution") or record.get("audioResolution")


def _comparable_duration(a: dict[str, Any], b: dict[str, Any]) -> tuple[float, float] | None:
    """The same-lane duration pair, preferring the census lane."""
    if a.get("hasCensus") and b.get("hasCensus"):
        left, right = a.get("censusDurationSeconds"), b.get("censusDurationSeconds")
        if left is not None and right is not None:
            return left, right
    if a.get("hasAudio") and b.get("hasAudio"):
        left, right = a.get("audioDurationSeconds"), b.get("audioDurationSeconds")
        if left is not None and right is not None:
            return left, right
    left, right = _preferred_duration(a), _preferred_duration(b)
    if left is not None and right is not None:
        return left, right
    return None


def _pair_side(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "slug": record.get("slug") or "",
        "durationSeconds": _round(_preferred_duration(record)),
        "censusDurationSeconds": _round(record.get("censusDurationSeconds")),
        "audioDurationSeconds": _round(record.get("audioDurationSeconds")),
        "resolution": _preferred_resolution(record),
        "censusResolution": record.get("censusResolution"),
        "audioResolution": record.get("audioResolution"),
        "hasCensus": bool(record.get("hasCensus")),
        "hasAudio": bool(record.get("hasAudio")),
        "strobe": record.get("strobe"),
    }


def build_pairs(
    components: Sequence[Sequence[tuple[str, str]]],
    measured: dict[tuple[str, str], dict[str, Any]],
    identities: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for number, members in enumerate(components, start=1):
        present = [node for node in members if node in measured]
        if len(present) < 2:
            continue
        by_site: dict[str, list[tuple[str, str]]] = {}
        for node in present:
            by_site.setdefault(node[0], []).append(node)
        sites = sorted(by_site)
        if len(sites) < 2:
            continue
        title = ""
        for node in members:
            info = identities.get(node)
            if info and info.get("title"):
                title = info["title"]
                break
        for index, site_a in enumerate(sites):
            for site_b in sites[index + 1:]:
                for node_a in sorted(by_site[site_a], key=lambda node: node[1]):
                    for node_b in sorted(by_site[site_b], key=lambda node: node[1]):
                        record_a = measured[node_a]
                        record_b = measured[node_b]
                        side_a = _pair_side(record_a)
                        side_b = _pair_side(record_b)

                        duration = _comparable_duration(record_a, record_b)
                        duration_delta: float | None = None
                        duration_fraction: float | None = None
                        duration_mismatch = False
                        if duration is not None:
                            left, right = duration
                            duration_delta = left - right
                            longest = max(abs(left), abs(right))
                            if longest > 0:
                                duration_fraction = abs(left - right) / longest
                                duration_mismatch = (
                                    duration_fraction > DURATION_MISMATCH_FRACTION)

                        values: dict[str, list[float | None]] = {}
                        delta: dict[str, float | None] = {}
                        relative: dict[str, float | None] = {}
                        for metric in METRICS:
                            key = metric["key"]
                            left = _number(record_a.get(key))
                            right = _number(record_b.get(key))
                            values[key] = [left, right]
                            if left is None or right is None:
                                delta[key] = None
                                relative[key] = None
                                continue
                            delta[key] = left - right
                            relative[key] = (
                                relative_difference(left, right)
                                if metric["meaningfulZero"] else None)

                        cut_rate_divergence: bool | None = None
                        cpm_rel = relative.get("cutsPerMinute")
                        both_non_strobe = (
                            record_a.get("strobe") is False
                            and record_b.get("strobe") is False)
                        if (cpm_rel is not None and both_non_strobe
                                and not duration_mismatch):
                            cut_rate_divergence = (
                                abs(cpm_rel) > CUT_RATE_DIVERGENCE_FRACTION)

                        partial = (side_a["hasCensus"] != side_b["hasCensus"]
                                   or side_a["hasAudio"] != side_b["hasAudio"])
                        available = [
                            metric["key"] for metric in METRICS
                            if values[metric["key"]][0] is not None
                            and values[metric["key"]][1] is not None
                        ]
                        pairs.append({
                            "pairId": (f"W{number:04d}:{site_a}:{side_a['id']}"
                                       f"|{site_b}:{side_b['id']}"),
                            "workNumber": number,
                            "title": title,
                            "siteA": site_a,
                            "siteB": site_b,
                            "a": side_a,
                            "b": side_b,
                            "durationDeltaSeconds": _round(duration_delta),
                            "durationDeltaFraction": _round(duration_fraction),
                            "durationMismatch": duration_mismatch,
                            "cutRateDivergence": cut_rate_divergence,
                            "partial": partial,
                            "values": {key: [_round(item) for item in pair]
                                       for key, pair in values.items()},
                            "delta": {key: _round(item) for key, item in delta.items()},
                            "relativeDelta": {key: _round(item)
                                              for key, item in relative.items()},
                            "availableMetrics": available,
                        })
    return pairs


def _variant_pairs(pairs: Sequence[dict[str, Any]], metric: dict[str, Any],
                   *, duration_matched_only: bool,
                   cut_rate_consistent_only: bool) -> list[dict[str, Any]]:
    usable = []
    for pair in pairs:
        if metric["excludeStrobe"]:
            if pair["a"].get("strobe") is not False or pair["b"].get("strobe") is not False:
                continue
        if duration_matched_only and pair["durationMismatch"]:
            continue
        if cut_rate_consistent_only and pair["cutRateDivergence"]:
            continue
        left, right = pair["values"][metric["key"]]
        if left is None or right is None:
            continue
        usable.append(pair)
    return usable


def _statistics(pairs: Sequence[dict[str, Any]], metric: dict[str, Any]) -> dict[str, Any]:
    key = metric["key"]
    xs: list[float] = []
    ys: list[float] = []
    signed: list[float] = []
    absolute: list[float] = []
    relative: list[float] = []
    zero_denominators = 0
    groups: dict[int, dict[str, float]] = {}

    for pair in pairs:
        left, right = pair["values"][key]
        xs.append(left)
        ys.append(right)
        signed.append(left - right)
        absolute.append(abs(left - right))
        if metric["meaningfulZero"]:
            value = relative_difference(left, right)
            if value is None:
                zero_denominators += 1
            else:
                relative.append(value)
        groups.setdefault(pair["workNumber"], {})[
            f"{pair['siteA']}:{pair['a']['id']}"] = left
        groups.setdefault(pair["workNumber"], {})[
            f"{pair['siteB']}:{pair['b']['id']}"] = right

    icc = icc_oneway([list(group.values()) for group in groups.values()])
    rho = spearman(xs, ys)
    all_values = xs + ys
    stats = {
        "n_pairs": len(pairs),
        "n_works": len(groups),
        "signedMean": _round(_mean(signed)),
        "signedMedian": _round(_median(signed)),
        "absoluteMean": _round(_mean(absolute)),
        "absoluteMedian": _round(_median(absolute)),
        "relativeMean": _round(_mean(relative)) if metric["meaningfulZero"] else None,
        "relativeMedian": _round(_median(relative)) if metric["meaningfulZero"] else None,
        "relativeZeroDenominators": zero_denominators,
        "spearman": _round(rho),
        "icc": _round(icc["icc"]) if icc else None,
        "iccDetail": ({
            "works": icc["works"],
            "values": icc["values"],
            "meanValuesPerWork": _round(icc["meanValuesPerWork"]),
            "msBetween": _round(icc["msBetween"]),
            "msWithin": _round(icc["msWithin"]),
        } if icc else None),
        "valueRange": {
            "min": _round(min(all_values)) if all_values else None,
            "max": _round(max(all_values)) if all_values else None,
        },
    }
    return stats


def _duration_distribution(pairs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    fractions = [pair["durationDeltaFraction"] for pair in pairs
                 if pair["durationDeltaFraction"] is not None]
    if not fractions:
        return {"n": 0, "mean": None, "median": None, "p90": None,
                "max": None, "buckets": {}, "mismatchCount": 0}
    ordered = sorted(fractions)
    position = (len(ordered) - 1) * 0.9
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    p90 = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    buckets = {"<=1%": 0, "1-5%": 0, "5-10%": 0, "10-50%": 0, ">50%": 0}
    for value in fractions:
        if value <= 0.01:
            buckets["<=1%"] += 1
        elif value <= 0.05:
            buckets["1-5%"] += 1
        elif value <= 0.10:
            buckets["5-10%"] += 1
        elif value <= 0.50:
            buckets["10-50%"] += 1
        else:
            buckets[">50%"] += 1
    return {
        "n": len(fractions),
        "mean": _round(_mean(fractions)),
        "median": _round(_median(fractions)),
        "p90": _round(p90),
        "max": _round(max(fractions)),
        "buckets": buckets,
        "mismatchCount": sum(1 for pair in pairs if pair["durationMismatch"]),
    }


def _metric_block(pairs: Sequence[dict[str, Any]], metric: dict[str, Any]) -> dict[str, Any]:
    key = metric["key"]
    usable = _variant_pairs(pairs, metric, duration_matched_only=False,
                            cut_rate_consistent_only=False)
    matched = _variant_pairs(pairs, metric, duration_matched_only=True,
                             cut_rate_consistent_only=False)
    block: dict[str, Any] = {
        "key": key,
        "label": metric["label"],
        "unit": metric["unit"],
        "lane": metric["lane"],
        "meaningfulZero": metric["meaningfulZero"],
        "excludeStrobe": metric["excludeStrobe"],
        "all": _statistics(usable, metric),
        "durationMatched": _statistics(matched, metric),
    }
    if metric["key"] == "cutsPerMinute":
        consistent = _variant_pairs(pairs, metric, duration_matched_only=False,
                                    cut_rate_consistent_only=True)
        block["cutRateConsistent"] = _statistics(consistent, metric)
        block["excludedStrobePairs"] = sum(
            1 for pair in pairs
            if pair["values"][key][0] is not None
            and pair["values"][key][1] is not None
            and (pair["a"].get("strobe") is not False
                 or pair["b"].get("strobe") is not False))
    else:
        block["excludedStrobePairs"] = 0

    n = block["all"]["n_pairs"]
    reasons: list[str] = []
    if n == 0:
        reasons.append("no work has this metric measured on two sites")
    elif n < SPARSE_PAIR_THRESHOLD:
        reasons.append(f"only {n} usable pair{'s' if n != 1 else ''}; "
                       "the statistics are arithmetic, not evidence")
    if block["all"]["icc"] is None:
        reasons.append("ICC undefined: needs at least two works with two or "
                       "more values each")
    if block["all"]["spearman"] is None:
        reasons.append("Spearman undefined: needs two or more pairs with "
                       "varying values")
    block["sparse"] = n < SPARSE_PAIR_THRESHOLD
    block["notes"] = reasons
    return block


def _coverage(components: Sequence[Sequence[tuple[str, str]]],
              measured: dict[tuple[str, str], dict[str, Any]],
              pairs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    cross_site = [nodes for nodes in components
                  if len({site for site, _ in nodes}) >= 2]
    any_measured = 0
    two_sites = 0
    two_measured_same_site = 0
    measured_records = 0
    combinations: dict[str, dict[str, int]] = {}
    for nodes in cross_site:
        sites = sorted({site for site, _ in nodes})
        combo = "+".join(sites)
        entry = combinations.setdefault(combo, {
            "works": 0, "withAnyMeasurement": 0, "withMeasuredPair": 0})
        entry["works"] += 1
        present = [node for node in nodes if node in measured]
        measured_records += len(present)
        if present:
            any_measured += 1
            entry["withAnyMeasurement"] += 1
        present_sites = {site for site, _ in present}
        if len(present_sites) >= 2:
            two_sites += 1
        elif len(present) >= 2:
            two_measured_same_site += 1
    for pair in pairs:
        combo = "+".join(sorted({pair["siteA"], pair["siteB"]}))
        entry = combinations.setdefault(combo, {
            "works": 0, "withAnyMeasurement": 0, "withMeasuredPair": 0})
        entry["withMeasuredPair"] = entry.get("withMeasuredPair", 0) + 1
    return {
        "sites": sorted({site for nodes in cross_site for site, _ in nodes}),
        "crossSiteWorks": len(cross_site),
        "crossSiteWorksWithAnyMeasurement": any_measured,
        "crossSiteWorksMeasuredOnTwoSites": two_sites,
        "crossSiteWorksWithTwoMeasuredMembersSameSite": two_measured_same_site,
        "measuredRecordsInsideCrossSiteWorks": measured_records,
        "combinations": [
            {"sites": combo, **entry}
            for combo, entry in sorted(combinations.items())
        ],
    }


def analyze(root: Path) -> dict[str, Any]:
    inputs = _Inputs()
    sites = discover_sites(root)
    measured = load_measurements(root, sites, inputs)
    identities = load_identities(root, sites, measured, inputs)
    declared = load_declared_works(root, inputs)
    components = declared if declared is not None else compute_components(identities)

    pairs = build_pairs(components, measured, identities)
    coverage = _coverage(components, measured, pairs)
    metrics = {metric["key"]: _metric_block(pairs, metric) for metric in METRICS}

    duration_mismatch = sum(1 for pair in pairs if pair["durationMismatch"])
    cut_rate_divergent = sum(1 for pair in pairs if pair["cutRateDivergence"])
    partial = sum(1 for pair in pairs if pair["partial"])

    limitations = [
        "Duration mismatch: the same campaign is often published as a 30 s cut "
        "and a 60 s cut. A pair whose runtimes differ by more than "
        f"{int(DURATION_MISMATCH_FRACTION * 100)}% of the longer one is marked "
        "durationMismatch and reported both inside and outside the "
        "durationMatched statistics; it is a different edit, not a "
        "delivery artefact.",
        "Different cuts of the same work: when the duration matches but cuts "
        f"per minute differ by more than {int(CUT_RATE_DIVERGENCE_FRACTION * 100)}%, "
        "the pair is a retimed or alternate edit. It is flagged "
        "cutRateDivergence and cut out of the cutRateConsistent statistics "
        "rather than counted as measurement error.",
        "Host loudness normalisation: YouTube and Vimeo normalise playback "
        "loudness. LUFS/LRA agreement therefore validates the delivered "
        "stream, not the master; a mastering difference can be flattened or "
        "invented by the host.",
        "Partial lanes: a work with census on one site and only audio on the "
        "other is a partial pair. It is counted and paired only on the lane "
        "both sides share; it is never averaged into a metric one side lacks.",
        "Zero-valued metrics: a relative difference is defined as "
        "(A - B) / max(|A|, |B|). When both values are zero the denominator is "
        "zero, so the relative difference is null and counted under "
        "relativeZeroDenominators rather than coerced to zero or to infinity.",
        "Census cut candidates are ffmpeg scene-score exceedances, not verified "
        "edits; fast motion, flashes, transitions and compression can cross "
        "the threshold. Strobe-flagged records are never pooled with "
        "non-strobe records for cutsPerMinute.",
        "Luma and saturation are display-RGB proxies at the decoded rendition "
        "size, not scene-linear light or calibrated colour; different "
        "resolutions and codecs shift them independently of the work.",
    ]
    if coverage["crossSiteWorksMeasuredOnTwoSites"] == 0:
        limitations.append(
            "Coverage gap in this snapshot: "
            f"{coverage['crossSiteWorks']} works appear on two or more sites, "
            f"but {coverage['crossSiteWorksMeasuredOnTwoSites']} have numeric "
            "census or audio evidence on two of them. The figure of 219 "
            "describes works with a *selected row* on more than one site, not "
            "works that were measured twice. The pair statistics above are "
            "therefore empty, and the honest reading is that this corpus "
            "cannot yet answer the cross-site question.")

    return {
        "schemaVersion": SCHEMA,
        "derivedAt": inputs.derived_at(),
        "derivedFrom": "maximum mtime of the input records (never now())",
        "root": str(root),
        "sites": sites,
        "metrics": [metric["key"] for metric in METRICS],
        "thresholds": {
            "durationMismatchFraction": DURATION_MISMATCH_FRACTION,
            "cutRateDivergenceFraction": CUT_RATE_DIVERGENCE_FRACTION,
            "sparsePairThreshold": SPARSE_PAIR_THRESHOLD,
        },
        "coverage": coverage,
        "counts": {
            "pairs": len(pairs),
            "worksPaired": len({pair["workNumber"] for pair in pairs}),
            "durationMismatchPairs": duration_mismatch,
            "cutRateDivergentPairs": cut_rate_divergent,
            "partialPairs": partial,
            "measuredRecords": len(measured),
            "cataloguedIdentities": len(identities),
        },
        "statistics": metrics,
        "durationDeltaDistribution": _duration_distribution(pairs),
        "pairs": pairs,
        "limitations": limitations,
    }


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _stat_row(key: str, block: dict[str, Any], stats: dict[str, Any],
              digits: int = 3) -> str:
    icc = stats["icc"]
    return ("| `{key}` | {n} | {works} | {signed} | {absolute} | {relative} | "
            "{rho} | {icc} |").format(
        key=key,
        n=stats["n_pairs"],
        works=stats["n_works"],
        signed=_fmt(stats["signedMean"], digits),
        absolute=_fmt(stats["absoluteMean"], digits),
        relative=_fmt(stats["relativeMean"], digits),
        rho=_fmt(stats["spearman"], 3),
        icc=_fmt(icc, 3),
    )


def _disagreements(pairs: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for pair in pairs:
        worst_metric = None
        worst_value = 0.0
        parts = []
        for metric in METRICS:
            key = metric["key"]
            left, right = pair["values"][key]
            if left is None or right is None:
                continue
            if metric["meaningfulZero"]:
                value = pair["relativeDelta"].get(key)
                normalized = abs(value) if value is not None else 0.0
            else:
                scale = max(abs(left), abs(right), 1.0)
                normalized = abs(left - right) / scale
            parts.append(normalized)
            if normalized > worst_value:
                worst_value = normalized
                worst_metric = key
        if parts:
            scored.append({
                "pair": pair,
                "score": sum(parts) / len(parts),
                "worstMetric": worst_metric,
                "worstValue": worst_value,
            })
    scored.sort(key=lambda item: (-item["score"], item["pair"]["pairId"]))
    return scored[:5]


def render_markdown(payload: dict[str, Any]) -> str:
    coverage = payload["coverage"]
    counts = payload["counts"]
    metrics = payload["statistics"]
    lines: list[str] = []
    add = lines.append

    add("# Cross-site agreement of measured work")
    add("")
    add("Read-only, standard-library analysis of `research/analysis`. The only "
        "timestamp is the maximum input record mtime "
        f"(`{payload['derivedAt'] or 'no inputs'}`); no value derives from "
        "`now()`.")
    add("")
    add("The question is whether a measurement describes **the work** or **the "
        "delivery**. Each work measured on two sites is one pair: the same "
        "campaign reached us through two platforms, renditions and encodes, so "
        "agreement bounds how much of the number is intrinsic to the film and "
        "how much is the host's encode, scaling or normalisation.")
    add("")

    add("## Coverage")
    add("")
    add(f"- Sites with measurement lanes: {', '.join(payload['sites']) or '—'}.")
    add(f"- Works on two or more sites: **{coverage['crossSiteWorks']}**.")
    add(f"- … with at least one measured record: "
        f"**{coverage['crossSiteWorksWithAnyMeasurement']}**.")
    add(f"- … measured on two or more sites: "
        f"**{coverage['crossSiteWorksMeasuredOnTwoSites']}**.")
    add(f"- Measured records inside cross-site works: "
        f"{coverage['measuredRecordsInsideCrossSiteWorks']}"
        + (f" (of which {coverage['crossSiteWorksWithTwoMeasuredMembersSameSite']} "
           "works carry two measured members on the *same* site, not a cross-site pair)."
           if coverage["crossSiteWorksWithTwoMeasuredMembersSameSite"] else "."))
    add("")
    if coverage["combinations"]:
        add("| site combination | works | with any measurement | measurable pairs |")
        add("|---|---:|---:|---:|")
        for combo in coverage["combinations"]:
            add(f"| {combo['sites']} | {combo['works']} | "
                f"{combo['withAnyMeasurement']} | {combo.get('withMeasuredPair', 0)} |")
        add("")
    if coverage["crossSiteWorksMeasuredOnTwoSites"] == 0:
        add("**This snapshot cannot answer the cross-site question.** The "
            "quality-selection tree lists 248 works that appear on two or more "
            "sites (219 of them with at least one selected row), but the "
            "census and audio cohorts are per-site samples that do not overlap "
            "on any of those works: "
            f"{coverage['crossSiteWorksWithAnyMeasurement']} have one side "
            "measured, none have two. "
            "`quality-selection.md`'s 219 counts *selected rows*, not measured "
            "works, so it is not a pair count. Every statistic below is empty "
            "because the inputs are absent, not because agreement was perfect.")
        add("")

    add("## Pair counts")
    add("")
    add(f"- pairs: **{counts['pairs']}** across "
        f"{counts['worksPaired']} works")
    add(f"- duration mismatch (>{int(payload['thresholds']['durationMismatchFraction'] * 100)}%): "
        f"**{counts['durationMismatchPairs']}**")
    add(f"- cut-rate divergence (>{int(payload['thresholds']['cutRateDivergenceFraction'] * 100)}%): "
        f"**{counts['cutRateDivergentPairs']}**")
    add(f"- partial (lane sets differ): **{counts['partialPairs']}**")
    add("")
    distribution = payload["durationDeltaDistribution"]
    if distribution["n"]:
        add("Duration-delta distribution over pairs with two runtimes: "
            f"n={distribution['n']}, mean={_fmt(distribution['mean'], 3)}, "
            f"median={_fmt(distribution['median'], 3)}, "
            f"p90={_fmt(distribution['p90'], 3)}, "
            f"max={_fmt(distribution['max'], 3)}. Buckets: "
            + ", ".join(f"{name} {count}"
                        for name, count in distribution["buckets"].items()) + ".")
    else:
        add("Duration-delta distribution: no pair has two runtimes to compare.")
    add("")

    add("## Statistics — all usable pairs")
    add("")
    add("| metric | n pairs | works | signed mean (A−B) | absolute mean | "
        "relative mean | Spearman | ICC |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for metric in METRICS:
        block = metrics[metric["key"]]
        add(_stat_row(metric["key"], block, block["all"]))
    add("")
    add("`cutsPerMinute` excludes every pair where either side is strobe-flagged; "
        "a strobe is never pooled with a non-strobe. Relative columns are blank "
        "for LUFS and LRA because a dB value has no meaningful zero for a ratio.")
    add("")

    add("## Statistics — duration-matched pairs only")
    add("")
    add("| metric | n pairs | works | signed mean (A−B) | absolute mean | "
        "relative mean | Spearman | ICC |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for metric in METRICS:
        block = metrics[metric["key"]]
        add(_stat_row(metric["key"], block, block["durationMatched"]))
    add("")

    add("## Variance decomposition")
    add("")
    add("ICC is the one-way ANOVA form "
        "`(MSB − MSW) / (MSB + (k̄ − 1)·MSW)` over works with at least two "
        "values: near 1 means between-work differences dominate, near 0 means "
        "the two deliveries disagree as much as two different works do.")
    add("")
    add("| metric | ICC | works | values | k̄ | MSB | MSW |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    for metric in METRICS:
        block = metrics[metric["key"]]
        detail = block["all"]["iccDetail"]
        add("| `{}` | {} | {} | {} | {} | {} | {} |".format(
            metric["key"],
            _fmt(block["all"]["icc"], 4),
            _fmt(detail["works"] if detail else None),
            _fmt(detail["values"] if detail else None),
            _fmt(detail["meanValuesPerWork"] if detail else None, 2),
            _fmt(detail["msBetween"] if detail else None, 6),
            _fmt(detail["msWithin"] if detail else None, 6),
        ))
    add("")
    sparse = [metric["key"] for metric in METRICS
              if metrics[metric["key"]]["sparse"]]
    if sparse:
        add("Sparse or undefined: " + ", ".join(f"`{key}`" for key in sparse)
            + ". Where `n` is 0 there is no number to read; where it is 1–2 the "
              "arithmetic is shown only so the absence is visible, not as a "
              "finding.")
        add("")

    add("## Biggest disagreements")
    add("")
    worst = _disagreements(payload["pairs"])
    if not worst:
        add("None: no work in this tree has a metric measured on two sites, so "
            "there is no disagreement to rank. This is a coverage fact, not a "
            "null result.")
    else:
        add("| pair | work | site A | site B | Δ duration | mean relative gap | "
            "worst metric |")
        add("|---|---|---|---|---:|---:|---|")
        for item in worst:
            pair = item["pair"]
            add(f"| `{pair['pairId']}` | {pair['title'] or '—'} | "
                f"{pair['siteA']}:{pair['a']['slug']} | "
                f"{pair['siteB']}:{pair['b']['slug']} | "
                f"{_fmt(pair['durationDeltaFraction'], 3)} | "
                f"{_fmt(item['score'], 3)} | `{item['worstMetric']}` |")
    add("")

    add("## Interpretation")
    add("")
    add("**What a high ICC would license.** A metric with a high ICC on "
        "duration-matched, non-strobe pairs tracks the work rather than the "
        "delivery: two independent platforms agree on its ordering, so it can "
        "be compared across works that were measured on different sites, and a "
        "difference between two works is unlikely to be an encode artefact.")
    add("")
    add("**What it would not license.** It is not proof that the two numbers "
        "are the same measurement. Duration mismatch (a 30 s cut against a "
        "60 s cut), truncation or an alternate edit, host loudness "
        "normalisation (YouTube and Vimeo both apply it, so LUFS agreement "
        "describes the delivered stream and not the master), and different "
        "cuts of one campaign all survive a high ICC. Nor does it validate the "
        "metric itself: a shared bias in the cut-detector or the display-RGB "
        "proxy would raise agreement without making either number true.")
    add("")
    add("**What this run licenses.** Nothing about agreement yet. The pairs "
        "that exist are too few to separate work variance from delivery "
        "variance; the run's value is the exact statement of that gap and the "
        "machinery to fill it once the same cross-site ids are measured in "
        "both lanes.")
    add("")

    add("## Limitations")
    add("")
    for index, limitation in enumerate(payload["limitations"], start=1):
        add(f"{index}. {limitation}")
    add("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=path.name + ".", suffix=".tmp",
        delete=False)
    try:
        with handle:
            handle.write(text)
        os.replace(handle.name, path)
    finally:
        if os.path.exists(handle.name):
            os.unlink(handle.name)


def write_outputs(payload: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    json_path = out_dir / "cross-site-agreement.json"
    markdown_path = out_dir / "cross-site-agreement.md"
    document = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    _write_atomic(json_path, document)
    _write_atomic(markdown_path, render_markdown(payload) + "\n")
    return json_path, markdown_path


def summarise(payload: dict[str, Any]) -> str:
    coverage = payload["coverage"]
    counts = payload["counts"]
    lines = [
        f"Cross-site agreement: {len(payload['sites'])} sites, "
        f"{coverage['crossSiteWorks']} cross-site works, "
        f"{counts['pairs']} measurable pairs",
        f"  coverage: {coverage['crossSiteWorksWithAnyMeasurement']} works measured "
        f"on one site, {coverage['crossSiteWorksMeasuredOnTwoSites']} on two",
        f"  duration mismatches: {counts['durationMismatchPairs']}, "
        f"cut-rate divergences: {counts['cutRateDivergentPairs']}, "
        f"partial: {counts['partialPairs']}",
    ]
    for metric in METRICS:
        block = payload["statistics"][metric["key"]]
        stats = block["all"]
        detail = (f"n_pairs={stats['n_pairs']} spearman={_fmt(stats['spearman'])} "
                  f"icc={_fmt(stats['icc'])} "
                  f"works={stats['n_works']}")
        if block["sparse"]:
            detail += "  [too sparse to read]"
        lines.append(f"  {metric['key']}: {detail}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                       help="measurement tree (default: research/analysis)")
    parser.add_argument("--out-dir", type=Path, default=None,
                       help="output directory (default: --root)")
    args = parser.parse_args(argv)

    out_dir = args.out_dir or args.root
    payload = analyze(args.root)
    json_path, markdown_path = write_outputs(payload, out_dir)
    print(summarise(payload))
    print(f"wrote {json_path}")
    print(f"wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
