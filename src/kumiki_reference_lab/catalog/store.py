"""Deterministic local catalog loading, purpose-first lookup and index export."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from kumiki_reference_lab.catalog.validate import (
    INDEX_SCHEMA_VERSION, validate_technique,
)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON property: {key}")
        result[key] = value
    return result


def load_catalog(root: Path) -> list[dict[str, Any]]:
    """Load strict authored JSON entries, refusing partial or corrupted catalogs."""
    if not root.is_dir():
        raise ValueError(f"catalog directory does not exist: {root}")
    entries: list[dict[str, Any]] = []
    issues: list[str] = []
    paths = sorted(root.rglob("*.json"))
    if not paths:
        raise ValueError("catalog contains no JSON technique entries")
    seen: set[str] = set()
    for path in paths:
        if path.is_symlink() or not path.is_file():
            issues.append(f"{path}: entry must be a regular file, not a symlink")
            continue
        if path.stat().st_size > 262_144:
            issues.append(f"{path}: entry exceeds 256 KiB")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"),
                                 object_pairs_hook=_reject_duplicate_keys)
        except (ValueError, UnicodeDecodeError) as exc:
            issues.append(f"{path}: invalid JSON ({exc})")
            continue
        validation = validate_technique(payload)
        if validation:
            issues.extend(f"{path}: {message}" for message in validation)
            continue
        identifier = payload["id"]
        if identifier in seen:
            issues.append(f"{path}: duplicate technique id {identifier}")
            continue
        seen.add(identifier)
        expected = Path(payload["category"]) / (identifier.split(".", 1)[1] + ".json")
        if path.relative_to(root) != expected:
            issues.append(f"{path}: expected catalog/entries/{expected}")
            continue
        # File hash identifies this exact human-authored entry, not the video.
        payload = dict(payload)
        payload["_entrySha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(payload)
    if issues:
        raise ValueError("catalog validation failed:\n" + "\n".join(issues))
    return sorted(entries, key=lambda item: item["id"])


def build_catalog_index(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Metadata-only contract; never copies source frames or executable code."""
    return {
        "schemaVersion": INDEX_SCHEMA_VERSION,
        "entries": [{
            "id": entry["id"],
            "revision": entry["revision"],
            "name": entry["name"],
            "category": entry["category"],
            "status": entry["status"],
            "summary": entry["summary"],
            "storyPurposes": entry["intent"]["storyPurposes"],
            "kumikiRegistryId": entry["kumiki"]["registryId"],
            "implementationStatus": entry["kumiki"]["implementationStatus"],
            "entrySha256": entry["_entrySha256"],
        } for entry in sorted(entries, key=lambda e: e["id"])],
    }


def search_catalog(entries: list[dict[str, Any]], query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Purpose-first lexical ranking; no embedding/API or imaginary relevance."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("catalog search limit must be between 1 and 100")
    tokens = {word for word in re.findall(r"[a-z0-9]+", query.lower())
              if word not in {"a", "the", "to", "for", "of", "and", "how", "i", "can", "you", "with"}}
    if not tokens:
        raise ValueError("search query needs at least one meaningful keyword")
    matches = []
    for entry in entries:
        purpose = " ".join(entry["intent"]["storyPurposes"])
        name = entry["name"]
        summary = entry["summary"]
        result = entry["intent"]["desiredPerceptualResult"]
        fields = ((purpose, 6), (name, 4), (result, 3), (summary, 2),
                  (" ".join(entry["mechanism"]["visibleCues"]), 1))
        score = sum(weight * len(tokens.intersection(set(re.findall(r"[a-z0-9]+", text.lower()))))
                    for text, weight in fields)
        if score == 0:
            continue
        matches.append({
            "id": entry["id"], "name": entry["name"], "category": entry["category"],
            "storyPurposes": entry["intent"]["storyPurposes"],
            "implementationStatus": entry["kumiki"]["implementationStatus"],
            "score": score,
        })
    matches.sort(key=lambda item: (-item["score"], item["id"]))
    return matches[:limit]
