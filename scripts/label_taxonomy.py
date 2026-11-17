#!/usr/bin/env python3
"""Apply the labelled motion-component taxonomy to stored evidence.

The applier is a pure, offline join over ``research/analysis/**``. It never
downloads, decodes or re-measures media, and it never writes into ``videos/``,
``census/``, ``audio/``, ``stills/`` or ``dataset/``.

Inputs
------
- ``catalog/taxonomy/motion-components.v1.json``: versioned labels, fixed
  thresholds and machine predicates.
- ``<root>/<site>/census/*.json``: one full-runtime census record per work.
- ``<root>/<site>/audio/*.json``: optional audio record joined by id/slug.
- ``<root>/<site>/videos/*.json``: optional video record joined by id/slug.
- ``<root>/<site>/catalog.json``: optional catalog metadata joined by id/slug.

Outputs
-------
- ``<root>/<site>/taxonomy-labels.json`` (schema
  ``kumiki.<site>-taxonomy-labels.v1``), one entry per census record.
- ``<root>/taxonomy-assignments.json`` and ``.md`` (schema
  ``kumiki.taxonomy-assignments.v1``), corpus summary.

A label is assigned only when every ``requires`` path is present, every
``gate`` and ``eligibility`` condition passes, no exclusion matches, and the
positive predicate is true. Layer-D labels are fully specified against
``motionProfile.*`` paths and are reported as ``missing-motion-profile``
because no stored record carries that block today.

Usage::

    PYTHONPATH=src python scripts/label_taxonomy.py \
        --root research/analysis \
        --taxonomy catalog/taxonomy/motion-components.v1.json \
        [--sites shots aicp] [--dry-run] \
        [--json-out research/analysis/taxonomy-assignments.json] \
        [--md-out research/analysis/taxonomy-assignments.md]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]

SCHEMA_TAXONOMY = "kumiki.motion-component-taxonomy.v1"
SCHEMA_ASSIGNMENTS = "kumiki.taxonomy-assignments.v1"
TAXONOMY_REL = "catalog/taxonomy/motion-components.v1.json"
REQUIRED_LABEL_FIELDS = (
    "id", "layer", "label", "definition", "positive", "exclusions",
    "requires", "evidenceTier", "confidence", "exemplars", "reuseNote",
    "nonClaims",
)
VALID_TIERS = {"measured-full-runtime", "measured-sampled", "unmeasured"}
ID_KEYS = ("clipId", "projectId", "nid", "postId", "id")
CATALOG_LIST_KEYS = ("projects", "clips", "entries", "videos", "items")


class TaxonomyError(ValueError):
    """Raised when the taxonomy file is inconsistent."""


class _Missing:
    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "MISSING"


MISSING = _Missing()


# ---------------------------------------------------------------------------
# JSON and path helpers


def load_json(path: Path) -> tuple[Any, float]:
    """Return ``(data, mtime)`` for one stored JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data, path.stat().st_mtime


def _is_number(value: object) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(float(value)))


def is_present(value: object) -> bool:
    if value is MISSING or value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    return True


def resolve_path(record: object, path: str) -> object:
    """Resolve a dotted path, returning ``MISSING`` when any part is absent."""
    current = record
    for part in path.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                return MISSING
            current = current[part]
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return MISSING
        else:
            return MISSING
    return current


def missing_reason(path: str) -> str:
    if path.startswith("motionProfile"):
        return "missing-motion-profile"
    if path.startswith("audio."):
        return "missing-audio"
    if path.startswith("editorial."):
        return "missing-editorial"
    if path.startswith("census."):
        return "missing-census"
    if path.startswith("identityVerification"):
        return "missing-identity"
    return "missing-field:" + path


def _sort_key(identifier: str) -> tuple[int, object]:
    text = str(identifier)
    if text.isdigit():
        return (0, int(text))
    return (1, text)


# ---------------------------------------------------------------------------
# Taxonomy loading and validation


def load_taxonomy(path: Path) -> dict[str, Any]:
    data, _ = load_json(path)
    validate_taxonomy(data)
    return data


def _iter_conditions(node: object) -> Iterable[Mapping[str, Any]]:
    if isinstance(node, Mapping):
        if "field" in node or "fields" in node or "never" in node:
            yield node
            return
        for key in ("all", "any", "not", "gate", "eligibility", "high", "low"):
            if key in node:
                yield from _iter_conditions(node[key])
        return
    if isinstance(node, list):
        for item in node:
            yield from _iter_conditions(item)


def validate_taxonomy(taxonomy: Mapping[str, Any]) -> None:
    """Validate schema, uniqueness, resolvability and predicate shape."""
    if taxonomy.get("schema") != SCHEMA_TAXONOMY:
        raise TaxonomyError(
            f"expected schema {SCHEMA_TAXONOMY!r}, got {taxonomy.get('schema')!r}")
    thresholds = taxonomy.get("thresholds")
    if not isinstance(thresholds, Mapping) or not thresholds:
        raise TaxonomyError("taxonomy.thresholds must be a non-empty mapping")
    layers = taxonomy.get("layers")
    if not isinstance(layers, list) or not layers:
        raise TaxonomyError("taxonomy.layers must be a non-empty list")
    layer_ids = [layer.get("id") for layer in layers]
    if len(layer_ids) != len(set(layer_ids)):
        raise TaxonomyError("duplicate layer ids")
    labels = taxonomy.get("labels")
    if not isinstance(labels, list) or not labels:
        raise TaxonomyError("taxonomy.labels must be a non-empty list")
    seen: set[str] = set()
    for label in labels:
        where = f"label {label.get('id', '<no-id>')}"
        for field in REQUIRED_LABEL_FIELDS:
            if field not in label:
                raise TaxonomyError(f"{where}: missing field {field!r}")
        label_id = label["id"]
        if not isinstance(label_id, str) or not label_id:
            raise TaxonomyError(f"{where}: id must be a non-empty string")
        if label_id in seen:
            raise TaxonomyError(f"duplicate label id {label_id!r}")
        seen.add(label_id)
        if label["layer"] not in layer_ids:
            raise TaxonomyError(f"{where}: unknown layer {label['layer']!r}")
        if label["evidenceTier"] not in VALID_TIERS:
            raise TaxonomyError(
                f"{where}: invalid evidenceTier {label['evidenceTier']!r}")
        if not isinstance(label["requires"], list):
            raise TaxonomyError(f"{where}: requires must be a list")
        if not isinstance(label["exclusions"], list):
            raise TaxonomyError(f"{where}: exclusions must be a list")
        if not isinstance(label["nonClaims"], list) or not label["nonClaims"]:
            raise TaxonomyError(f"{where}: nonClaims must be a non-empty list")
        if not isinstance(label["positive"], Mapping):
            raise TaxonomyError(f"{where}: positive must be an object")
        confidence = label["confidence"]
        if not isinstance(confidence, Mapping) or "default" not in confidence:
            raise TaxonomyError(f"{where}: confidence needs a default")
        for key in ("positive", "exclusions", "eligibility", "gate",
                    "confidence"):
            if key in label:
                for condition in _iter_conditions(label[key]):
                    if condition.get("never"):
                        continue
                    threshold = condition.get("threshold")
                    if threshold is not None and threshold not in thresholds:
                        raise TaxonomyError(
                            f"{where}: unresolved threshold {threshold!r}")
                    op = condition.get("op")
                    if op not in {"==", "!=", "missing"} and threshold is None:
                        raise TaxonomyError(
                            f"{where}: comparison {op!r} without threshold")
                    value = condition.get("value")
                    if isinstance(value, (int, float)) and not isinstance(
                            value, bool):
                        raise TaxonomyError(
                            f"{where}: numeric literal {value!r}; use a threshold")
        if label["evidenceTier"] == "unmeasured" and label["layer"] == "D-transition-motion":
            if not any(path.startswith("motionProfile.")
                       for path in label["requires"]):
                raise TaxonomyError(
                    f"{where}: unmeasured layer-D label must require motionProfile.*")
        if label.get("assignable", True) is False:
            if label["evidenceTier"] != "unmeasured":
                raise TaxonomyError(
                    f"{where}: non-assignable label must be evidenceTier unmeasured")


def threshold(taxonomy: Mapping[str, Any], name: str) -> float:
    thresholds = taxonomy["thresholds"]
    if name not in thresholds:
        raise TaxonomyError(f"unknown threshold {name!r}")
    return thresholds[name]


# ---------------------------------------------------------------------------
# Predicate evaluation


def _aggregate(values: Sequence[object], agg: str | None) -> object:
    if agg is None:
        return values[0]
    if not all(_is_number(value) for value in values):
        return MISSING
    numbers = [float(value) for value in values]
    if agg == "sum":
        return sum(numbers)
    if agg == "mean":
        return sum(numbers) / len(numbers)
    if agg == "max":
        return max(numbers)
    if agg == "min":
        return min(numbers)
    raise TaxonomyError(f"unknown aggregate {agg!r}")


def evaluate_condition(condition: Mapping[str, Any], record: Mapping[str, Any],
                       taxonomy: Mapping[str, Any]) -> bool:
    """Evaluate one machine predicate against a joined record."""
    if "never" in condition:
        return False
    if "all" in condition:
        return all(evaluate_condition(item, record, taxonomy)
                   for item in condition["all"])
    if "any" in condition:
        return any(evaluate_condition(item, record, taxonomy)
                   for item in condition["any"])
    if "not" in condition:
        return not evaluate_condition(condition["not"], record, taxonomy)

    paths = condition.get("fields")
    if paths is None:
        paths = [condition.get("field")]
    values = [resolve_path(record, str(path)) for path in paths]
    op = condition.get("op")
    if op == "missing":
        return not all(is_present(value) for value in values)
    if not all(is_present(value) for value in values):
        return False

    left = _aggregate(values, condition.get("agg"))
    if left is MISSING:
        return False
    if condition.get("abs") and _is_number(left):
        left = abs(float(left))

    if op in {"==", "!="}:
        target = condition.get("value")
        if condition.get("negate") and _is_number(target):
            target = -target
        equal = left == target
        return equal if op == "==" else not equal

    target = threshold(taxonomy, str(condition["threshold"]))
    if condition.get("negate"):
        target = -target
    if not _is_number(left):
        return False
    value = float(left)
    if op == ">=":
        return value >= target
    if op == ">":
        return value > target
    if op == "<=":
        return value <= target
    if op == "<":
        return value < target
    raise TaxonomyError(f"unknown operator {op!r}")


def confidence_for(label: Mapping[str, Any], record: Mapping[str, Any],
                   taxonomy: Mapping[str, Any]) -> str:
    confidence = label["confidence"]
    default = confidence.get("default", "medium")
    if default == "unmeasured":
        return "unmeasured"
    high = confidence.get("high") or []
    if high and all(evaluate_condition(item, record, taxonomy)
                    for item in high):
        return "high"
    low = confidence.get("low") or []
    if low and any(evaluate_condition(item, record, taxonomy)
                   for item in low):
        return "low"
    return str(default)


def evaluate_label(label: Mapping[str, Any], record: Mapping[str, Any],
                   taxonomy: Mapping[str, Any]) -> tuple[bool, str | None]:
    """Return ``(assigned, reason)`` for one label and one joined record."""
    if label.get("assignable", True) is False:
        return False, "out-of-scope-layer"
    for path in label["requires"]:
        if not is_present(resolve_path(record, path)):
            return False, missing_reason(path)
    for gate in label.get("gate") or []:
        if evaluate_condition(gate, record, taxonomy):
            return False, str(gate.get("reason", "gate"))
    for rule in label.get("eligibility") or []:
        if not evaluate_condition(rule, record, taxonomy):
            return False, str(rule.get("reason", "ineligible"))
    for exclusion in label["exclusions"]:
        if evaluate_condition(exclusion, record, taxonomy):
            return False, "excluded"
    if not evaluate_condition(label["positive"], record, taxonomy):
        return False, "predicate-false"
    return True, None


def assign_record(record: Mapping[str, Any],
                  taxonomy: Mapping[str, Any]) -> dict[str, Any]:
    """Assign every applicable label to one joined record."""
    labels: list[str] = []
    confidence: dict[str, str] = {}
    unassigned: dict[str, str] = {}
    reasons_by_layer: dict[str, list[str]] = {
        layer["id"]: [] for layer in taxonomy["layers"]}
    assigned_by_layer: dict[str, list[str]] = {
        layer["id"]: [] for layer in taxonomy["layers"]}
    missing_tokens: dict[str, list[str]] = {
        layer["id"]: [] for layer in taxonomy["layers"]}

    for label in taxonomy["labels"]:
        assigned, reason = evaluate_label(label, record, taxonomy)
        layer = label["layer"]
        if assigned:
            labels.append(label["id"])
            confidence[label["id"]] = confidence_for(label, record, taxonomy)
            assigned_by_layer[layer].append(label["id"])
        else:
            reasons_by_layer[layer].append(str(reason))
            if str(reason).startswith("missing-"):
                missing_tokens[layer].append(str(reason))
            elif reason != "out-of-scope-layer":
                unassigned[label["id"]] = str(reason)

    layer_status: dict[str, str] = {}
    layer_metadata = {layer["id"]: layer for layer in taxonomy["layers"]}
    for layer, reasons in reasons_by_layer.items():
        if assigned_by_layer[layer]:
            layer_status[layer] = "assigned"
            continue
        if layer_metadata[layer].get("assignable", True) is False:
            layer_status[layer] = "out-of-scope-layer"
            continue
        if not reasons:
            layer_status[layer] = "no-labels"
            continue
        missing = missing_tokens[layer]
        if len(missing) == len(reasons):
            layer_status[layer] = Counter(missing).most_common(1)[0][0]
        elif missing:
            token = Counter(missing).most_common(1)[0][0]
            layer_status[layer] = "partial:" + token
        else:
            layer_status[layer] = "evaluated-no-label"

    return {
        "id": str(record["id"]),
        "slug": record.get("slug"),
        "labels": sorted(labels),
        "confidence": dict(sorted(confidence.items())),
        "layerStatus": dict(sorted(layer_status.items())),
        "unassigned": dict(sorted(unassigned.items())),
    }


# ---------------------------------------------------------------------------
# Corpus loading


def discover_sites(root: Path) -> list[str]:
    sites = []
    if not root.is_dir():
        return sites
    for entry in sorted(root.iterdir()):
        if entry.is_dir() and (entry / "census").is_dir():
            sites.append(entry.name)
    return sites


def _identity_from_record(mapping: Mapping[str, Any]) -> str | None:
    record = mapping.get("record")
    if isinstance(record, Mapping) and record.get("id") is not None:
        return str(record["id"])
    for key in ID_KEYS:
        if mapping.get(key) is not None:
            return str(mapping[key])
    return None


def _slug_from_record(mapping: Mapping[str, Any]) -> str | None:
    record = mapping.get("record")
    if isinstance(record, Mapping) and record.get("slug"):
        return str(record["slug"])
    if mapping.get("slug"):
        return str(mapping["slug"])
    return None


def _catalog_items(catalog: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in CATALOG_LIST_KEYS:
        value = catalog.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _catalog_identity(item: Mapping[str, Any]) -> str | None:
    for key in ("projectId", "clipId", "nid", "postId", "id"):
        if item.get(key) is not None:
            return str(item[key])
    return None


def _index_by_identity(
    records: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    by_slug: dict[str, Mapping[str, Any]] = {}
    for record in records:
        identifier = _identity_from_record(record)
        slug = _slug_from_record(record)
        if identifier is not None and identifier not in by_id:
            by_id[identifier] = record
        if slug and slug not in by_slug:
            by_slug[slug] = record
    return by_id, by_slug


def _join_index(records: Iterable[Mapping[str, Any]]) -> tuple[
        dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    by_slug: dict[str, Mapping[str, Any]] = {}
    for record in records:
        identifier = None
        for key in ID_KEYS:
            if record.get(key) is not None:
                identifier = str(record[key])
                break
        slug = record.get("slug")
        if identifier is not None and identifier not in by_id:
            by_id[identifier] = record
        if slug and str(slug) not in by_slug:
            by_slug[str(slug)] = record
    return by_id, by_slug


def _catalog_index(catalog: Mapping[str, Any]) -> tuple[
        dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    by_slug: dict[str, Mapping[str, Any]] = {}
    for item in _catalog_items(catalog):
        identifier = _catalog_identity(item)
        slug = item.get("slug")
        if identifier is not None and identifier not in by_id:
            by_id[identifier] = item
        if slug and str(slug) not in by_slug:
            by_slug[str(slug)] = item
    return by_id, by_slug


def load_site(root: Path, site: str) -> tuple[list[dict[str, Any]], list[float]]:
    """Join census, audio, video and catalog records for one site."""
    site_dir = root / site
    mtimes: list[float] = []

    census_records: list[Mapping[str, Any]] = []
    for path in sorted((site_dir / "census").glob("*.json")):
        data, mtime = load_json(path)
        mtimes.append(mtime)
        census_records.append(data)

    def _load_dir(name: str) -> list[Mapping[str, Any]]:
        directory = site_dir / name
        if not directory.is_dir():
            return []
        out: list[Mapping[str, Any]] = []
        for path in sorted(directory.glob("*.json")):
            data, mtime = load_json(path)
            mtimes.append(mtime)
            out.append(data)
        return out

    audio_by_id, audio_by_slug = _index_by_identity(_load_dir("audio"))
    video_by_id, video_by_slug = _join_index(_load_dir("videos"))

    catalog_path = site_dir / "catalog.json"
    catalog_by_id: dict[str, Mapping[str, Any]] = {}
    catalog_by_slug: dict[str, Mapping[str, Any]] = {}
    if catalog_path.is_file():
        catalog, mtime = load_json(catalog_path)
        mtimes.append(mtime)
        if isinstance(catalog, Mapping):
            catalog_by_id, catalog_by_slug = _catalog_index(catalog)

    joined: list[dict[str, Any]] = []
    for census in census_records:
        record_block = census.get("record")
        if not isinstance(record_block, Mapping):
            continue
        identifier = record_block.get("id")
        if identifier is None:
            continue
        identifier = str(identifier)
        slug = record_block.get("slug")
        audio_record = audio_by_id.get(identifier)
        if audio_record is None and slug:
            audio_record = audio_by_slug.get(str(slug))
        video_record = video_by_id.get(identifier)
        if video_record is None and slug:
            video_record = video_by_slug.get(str(slug))
        catalog_item = catalog_by_id.get(identifier)
        if catalog_item is None and slug:
            catalog_item = catalog_by_slug.get(str(slug))

        record: dict[str, Any] = {
            "site": site,
            "id": identifier,
            "slug": slug,
            "census": census.get("census"),
            "editorial": census.get("editorial"),
            "identityVerification": census.get("identityVerification"),
        }
        if "motionProfile" in census:
            record["motionProfile"] = census["motionProfile"]
        if audio_record is not None:
            record["audio"] = audio_record.get("audio")
        if video_record is not None:
            record["video"] = video_record
        if catalog_item is not None:
            record["catalog"] = catalog_item
        joined.append(record)
    joined.sort(key=lambda item: _sort_key(item["id"]))
    return joined, mtimes


# ---------------------------------------------------------------------------
# Aggregation


def _layer_labels(taxonomy: Mapping[str, Any], layer_id: str) -> list[Mapping[str, Any]]:
    return [label for label in taxonomy["labels"] if label["layer"] == layer_id]


def _cooccurrence(labels: Sequence[Mapping[str, Any]],
                  assigned: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ids = [label["id"] for label in labels]
    counts = [[0 for _ in ids] for _ in ids]
    record_sets = [set(record["labels"]) for record in assigned]
    for i, left in enumerate(ids):
        for j, right in enumerate(ids):
            counts[i][j] = sum(
                1 for labels_set in record_sets
                if left in labels_set and right in labels_set)
    return {"labels": ids, "counts": counts}


def summarize(taxonomy: Mapping[str, Any], sites: Sequence[str],
              per_site_raw: Mapping[str, Sequence[Mapping[str, Any]]],
              per_site_assigned: Mapping[str, Sequence[Mapping[str, Any]]],
              latest_mtime: float, root: Path,
              taxonomy_path: Path) -> dict[str, Any]:
    record_count = sum(len(records) for records in per_site_raw.values())
    all_records = [record for site in sites for record in per_site_raw[site]]
    all_assigned = [record for site in sites
                    for record in per_site_assigned[site]]
    labels = taxonomy["labels"]
    by_id = {label["id"]: label for label in labels}

    label_counts: Counter[str] = Counter()
    confidence_counts: dict[str, Counter[str]] = {
        label["id"]: Counter() for label in labels}
    for record in all_assigned:
        for label_id in record["labels"]:
            label_counts[label_id] += 1
            confidence_counts[label_id][record["confidence"][label_id]] += 1

    # Per-label eligibility: requires present and every rule passes, ignoring
    # the positive predicate. This is "could satisfy" rather than "did".
    requires_present: dict[str, int] = {label_id: 0 for label_id in by_id}
    eligible_counts: dict[str, int] = {label_id: 0 for label_id in by_id}
    reason_counts: dict[str, Counter[str]] = {
        label_id: Counter() for label_id in by_id}
    for record in all_records:
        for label in labels:
            present = all(is_present(resolve_path(record, path))
                          for path in label["requires"])
            if present and label.get("assignable", True):
                requires_present[label["id"]] += 1
            assigned, reason = evaluate_label(label, record, taxonomy)
            if present and label.get("assignable", True):
                gate_ok = not any(evaluate_condition(gate, record, taxonomy)
                                  for gate in label.get("gate") or [])
                rules_ok = all(evaluate_condition(rule, record, taxonomy)
                               for rule in label.get("eligibility") or [])
                exclusions_ok = not any(
                    evaluate_condition(exclusion, record, taxonomy)
                    for exclusion in label["exclusions"])
                if gate_ok and rules_ok and exclusions_ok:
                    eligible_counts[label["id"]] += 1
            if assigned:
                continue
            reason_counts[label["id"]][str(reason)] += 1

    label_rows = []
    for label in sorted(labels, key=lambda item: item["id"]):
        count = label_counts[label["id"]]
        eligible = eligible_counts[label["id"]]
        label_rows.append({
            "id": label["id"],
            "label": label["label"],
            "layer": label["layer"],
            "evidenceTier": label["evidenceTier"],
            "assigned": count,
            "shareOfRecords": round(count / record_count, 6) if record_count else 0.0,
            "eligibleRecords": eligible,
            "shareOfEligible": round(count / eligible, 6) if eligible else 0.0,
            "confidence": dict(sorted(confidence_counts[label["id"]].items())),
            "requiresPresent": requires_present[label["id"]],
            "nonClaims": list(label["nonClaims"]),
        })

    layers_summary: dict[str, Any] = {}
    for layer in taxonomy["layers"]:
        layer_id = layer["id"]
        layer_labels = _layer_labels(taxonomy, layer_id)
        union_paths: list[str] = []
        for label in layer_labels:
            for path in label["requires"]:
                if path not in union_paths:
                    union_paths.append(path)
        all_requires = 0
        any_requires = 0
        records_with_label = 0
        instances = 0
        if not layer.get("assignable", True):
            any_requires = 0
            all_requires = 0
        else:
            for record in all_records:
                present = [is_present(resolve_path(record, path))
                           for path in union_paths]
                if union_paths and all(present):
                    all_requires += 1
                if any(
                        all(is_present(resolve_path(record, path))
                            for path in label["requires"])
                        for label in layer_labels):
                    any_requires += 1
        for record in all_assigned:
            assigned_here = [label["id"] for label in layer_labels
                             if label["id"] in record["labels"]]
            if assigned_here:
                records_with_label += 1
                instances += len(assigned_here)
        layers_summary[layer_id] = {
            "name": layer["name"],
            "evidenceTier": layer["evidenceTier"],
            "assignable": bool(layer.get("assignable", True)),
            "labelCount": len(layer_labels),
            "requiredFields": union_paths,
            "recordsWithAllLayerFields": (all_requires
                                          if layer.get("assignable", True)
                                          else 0),
            "recordsWithAnyLabelRequires": any_requires,
            "recordsWithAtLeastOneLabel": records_with_label,
            "assignedLabelInstances": instances,
        }

    cooccurrence = {}
    for layer_id in ("A-pacing", "C-audio-energy"):
        cooccurrence[layer_id] = _cooccurrence(
            _layer_labels(taxonomy, layer_id), all_assigned)
        cooccurrence[layer_id]["recordCount"] = record_count

    per_site: dict[str, Any] = {}
    for site in sites:
        records = per_site_assigned[site]
        counts = Counter(label_id for record in records
                         for label_id in record["labels"])
        per_site[site] = {
            "recordCount": len(records),
            "assignedRecordCount": sum(1 for record in records if record["labels"]),
            "joined": {
                "audio": sum(1 for record in per_site_raw[site]
                             if record.get("audio") is not None),
                "video": sum(1 for record in per_site_raw[site]
                             if record.get("video") is not None),
                "catalog": sum(1 for record in per_site_raw[site]
                               if record.get("catalog") is not None),
            },
            "labels": {label["id"]: counts[label["id"]]
                       for label in sorted(labels, key=lambda item: item["id"])},
        }

    unmeasured = []
    for label in sorted(labels, key=lambda item: item["id"]):
        if label["evidenceTier"] == "unmeasured":
            unmeasured.append({
                "id": label["id"],
                "layer": label["layer"],
                "assigned": label_counts[label["id"]],
                "requires": list(label["requires"]),
                "assignable": bool(label.get("assignable", True)),
            })

    derived = datetime.fromtimestamp(latest_mtime, tz=timezone.utc).isoformat()
    if derived.endswith("+00:00"):
        derived = derived[:-6] + "Z"

    return {
        "schema": SCHEMA_ASSIGNMENTS,
        "taxonomy": {
            "schema": taxonomy.get("schema"),
            "version": taxonomy.get("version"),
            "title": taxonomy.get("title"),
            "path": _relative(taxonomy_path, ROOT),
            "labelCount": len(labels),
            "status": taxonomy.get("status"),
        },
        "derivedFrom": {
            "root": _relative(root, ROOT),
            "sites": list(sites),
            "latestInputMtime": derived,
            "note": "mtime only; no wall-clock timestamp is written",
        },
        "recordCount": record_count,
        "siteCount": len(sites),
        "layers": layers_summary,
        "labels": label_rows,
        "cooccurrence": cooccurrence,
        "perSite": per_site,
        "evidenceAvailability": {
            layer_id: {
                "labelCount": data["labelCount"],
                "recordsWithAllLayerFields": data["recordsWithAllLayerFields"],
                "recordsWithAnyLabelRequires": data["recordsWithAnyLabelRequires"],
                "recordsWithAtLeastOneLabel": data["recordsWithAtLeastOneLabel"],
                "requiredFields": data["requiredFields"],
            }
            for layer_id, data in layers_summary.items()
        },
        "unmeasuredLabels": unmeasured,
        "unassignedReasons": {
            label_id: dict(sorted(counter.items()))
            for label_id, counter in sorted(reason_counts.items())
            if counter
        },
        "notes": [
            "A label is a predicate over stored numeric evidence, not a creative archetype.",
            "Cut candidates are ffmpeg scene-score exceedances; fast motion, flashes and compression can inflate them.",
            "Layer B and the appearance component of layer E come from the 1 Hz stored series, so they are sampled, not full-rate.",
            "Layer D is specified against motionProfile.* but no stored record carries it; nothing in layer D is assigned.",
            "Layer F names are non-assignable by construction and have assigned: 0.",
            "No quality, genre, intent, authorship or effect-identity claim is made anywhere in this file.",
        ],
    }


def _relative(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# Markdown summary


def _md_escape(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Taxonomy assignments",
        "",
        "Generated by `scripts/label_taxonomy.py` from stored evidence only. "
        "This is a machine-applied label summary, not a style, quality or "
        "intent analysis.",
        "",
        f"- Taxonomy: `{summary['taxonomy']['path']}` "
        f"(schema `{summary['taxonomy']['schema']}`, version "
        f"{summary['taxonomy']['version']}, {summary['taxonomy']['labelCount']} labels).",
        f"- Records: **{summary['recordCount']:,}** across "
        f"**{summary['siteCount']}** sites.",
        f"- Latest input mtime: `{summary['derivedFrom']['latestInputMtime']}`.",
        f"- Records with at least one label: "
        f"**{sum(site['assignedRecordCount'] for site in summary['perSite'].values()):,}**.",
        "",
        "## Labels",
        "",
        "`eligible` counts records whose required fields exist and whose gate, "
        "eligibility and exclusion rules pass; `assigned` additionally requires "
        "the positive predicate.",
        "",
        "| label | layer | tier | assigned | share | eligible | high / medium / low |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in summary["labels"]:
        conf = row["confidence"]
        conf_text = " / ".join(str(conf.get(level, 0))
                               for level in ("high", "medium", "low"))
        lines.append(
            f"| `{row['id']}` | {_md_escape(row['layer'])} | "
            f"{row['evidenceTier']} | {row['assigned']:,} | "
            f"{row['shareOfRecords'] * 100:.1f}% | {row['eligibleRecords']:,} | "
            f"{conf_text} |")
    lines.extend([
        "",
        "## Per site",
        "",
        "| site | records | with at least one label |",
        "|---|---:|---:|",
    ])
    for site, data in summary["perSite"].items():
        lines.append(f"| {_md_escape(site)} | {data['recordCount']:,} | "
                     f"{data['assignedRecordCount']:,} |")
    lines.extend([
        "",
        "## Evidence availability",
        "",
        "| layer | labels | all layer fields | any label requires | with a label |",
        "|---|---:|---:|---:|---:|",
    ])
    for layer_id, data in summary["evidenceAvailability"].items():
        lines.append(
            f"| {_md_escape(layer_id)} | {data['labelCount']} | "
            f"{data['recordsWithAllLayerFields']:,} | "
            f"{data['recordsWithAnyLabelRequires']:,} | "
            f"{data['recordsWithAtLeastOneLabel']:,} |")
    lines.extend([
        "",
        "## Specified but unmeasured",
        "",
        "These labels cannot be assigned from the current corpus. Layer D needs "
        "a `motionProfile` block that no stored census record carries; layer F "
        "is out of scope by construction.",
        "",
        "| label | layer | assigned | assignable | required fields |",
        "|---|---|---:|---|---|",
    ])
    for row in summary["unmeasuredLabels"]:
        requires = ", ".join(f"`{path}`" for path in row["requires"]) or "none"
        lines.append(
            f"| `{row['id']}` | {row['layer']} | {row['assigned']} | "
            f"{'yes' if row['assignable'] else 'no'} | {requires} |")
    lines.extend([
        "",
        "## Co-occurrence, layer A",
        "",
        "Cell values are record counts with both row and column labels. The "
        "diagonal is the label's own count.",
        "",
    ])
    lines.extend(_cooccurrence_table(summary["cooccurrence"]["A-pacing"]))
    lines.extend([
        "",
        "## Co-occurrence, layer C",
        "",
    ])
    lines.extend(_cooccurrence_table(summary["cooccurrence"]["C-audio-energy"]))
    lines.append("")
    return "\n".join(lines)


def _cooccurrence_table(block: Mapping[str, Any]) -> list[str]:
    labels = block["labels"]
    counts = block["counts"]
    header = "| label | " + " | ".join(f"`{label}`" for label in labels) + " |"
    separator = "|---|" + "---:|" * len(labels)
    rows = [header, separator]
    for label, row in zip(labels, counts):
        rows.append(f"| `{label}` | " + " | ".join(str(value) for value in row)
                    + " |")
    return rows


# ---------------------------------------------------------------------------
# Output


def dump_json(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_if_changed(path: Path, text: str) -> bool:
    """Atomically write *text* when the existing bytes differ."""
    body = text.encode("utf-8")
    if path.is_file():
        try:
            if path.read_bytes() == body:
                return False
        except OSError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return True


def build_site_output(site: str, records: Sequence[Mapping[str, Any]],
                      taxonomy: Mapping[str, Any],
                      taxonomy_path: Path) -> dict[str, Any]:
    return {
        "schema": f"kumiki.{site}-taxonomy-labels.v1",
        "site": site,
        "taxonomy": {
            "schema": taxonomy.get("schema"),
            "version": taxonomy.get("version"),
            "path": _relative(taxonomy_path, ROOT),
        },
        "recordCount": len(records),
        "records": list(records),
    }


def run(root: Path, sites: Sequence[str], taxonomy_path: Path,
        json_out: Path, md_out: Path, dry_run: bool = False) -> dict[str, Any]:
    taxonomy = load_taxonomy(taxonomy_path)
    per_site_raw: dict[str, list[dict[str, Any]]] = {}
    per_site_records: dict[str, list[dict[str, Any]]] = {}
    mtimes: list[float] = []
    for site in sites:
        records, site_mtimes = load_site(root, site)
        assigned = [assign_record(record, taxonomy) for record in records]
        per_site_raw[site] = records
        per_site_records[site] = assigned
        mtimes.extend(site_mtimes)

    summary = summarize(
        taxonomy, sites, per_site_raw, per_site_records,
        max(mtimes) if mtimes else 0.0, root, taxonomy_path)

    if not dry_run:
        for site in sites:
            output = build_site_output(
                site, per_site_records[site], taxonomy, taxonomy_path)
            write_if_changed(
                root / site / "taxonomy-labels.json", dump_json(output))
        write_if_changed(json_out, dump_json(summary))
        write_if_changed(md_out, render_markdown(summary))
    return summary


def print_summary(summary: Mapping[str, Any]) -> None:
    print(f"records: {summary['recordCount']}")
    for site, data in summary["perSite"].items():
        print(f"  {site}: {data['recordCount']} records, "
              f"{data['assignedRecordCount']} with at least one label")
    print("layers:")
    for layer_id, data in summary["evidenceAvailability"].items():
        print(f"  {layer_id}: all fields {data['recordsWithAllLayerFields']}, "
              f"any requires {data['recordsWithAnyLabelRequires']}, "
              f"with a label {data['recordsWithAtLeastOneLabel']}")
    print("assigned labels:")
    for row in summary["labels"]:
        if row["assigned"]:
            print(f"  {row['id']}: {row['assigned']}")
    print("unmeasured labels:")
    for row in summary["unmeasuredLabels"]:
        print(f"  {row['id']}: assigned {row['assigned']}")


# ---------------------------------------------------------------------------
# CLI


def _split_sites(values: Sequence[str] | None) -> list[str]:
    if not values:
        return []
    sites: list[str] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if part and part not in sites:
                sites.append(part)
    return sites


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply the labelled motion-component taxonomy offline.")
    parser.add_argument("--root", default="research/analysis",
                        help="evidence root (default: research/analysis)")
    parser.add_argument("--sites", nargs="+", default=None,
                        help="sites to process; default: every site with census/")
    parser.add_argument("--taxonomy", default=TAXONOMY_REL,
                        help=f"taxonomy file (default: {TAXONOMY_REL})")
    parser.add_argument("--dry-run", action="store_true",
                        help="compute and print, write nothing")
    parser.add_argument("--json-out",
                        default="research/analysis/taxonomy-assignments.json")
    parser.add_argument("--md-out",
                        default="research/analysis/taxonomy-assignments.md")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_absolute():
        root = (Path.cwd() / root).resolve()
    taxonomy_path = Path(args.taxonomy)
    if not taxonomy_path.is_absolute():
        taxonomy_path = (Path.cwd() / taxonomy_path).resolve()
    json_out = Path(args.json_out)
    if not json_out.is_absolute():
        json_out = (Path.cwd() / json_out).resolve()
    md_out = Path(args.md_out)
    if not md_out.is_absolute():
        md_out = (Path.cwd() / md_out).resolve()

    sites = _split_sites(args.sites) or discover_sites(root)
    if not sites:
        print(f"no sites with census records under {root}", file=sys.stderr)
        return 2
    try:
        summary = run(root, sites, taxonomy_path, json_out, md_out,
                      dry_run=args.dry_run)
    except (TaxonomyError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print_summary(summary)
    if args.dry_run:
        print("dry run: no files written")
    else:
        print(f"wrote {json_out}")
        print(f"wrote {md_out}")
        for site in sites:
            print(f"wrote {root / site / 'taxonomy-labels.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
