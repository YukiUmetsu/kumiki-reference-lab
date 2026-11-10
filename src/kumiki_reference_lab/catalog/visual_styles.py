"""Creator-attributed visual style exemplars; not automatically verified film labels."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


SCHEMA_VERSION = "kumiki.visual-style-references.v1"
_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_FAMILIES = {"paper-and-collage", "hand-drawn", "physical-animation", "stylized-3d",
             "print-and-collage", "abstract-motion"}
_SOURCE_TYPES = {"studio-production-description", "studio-behind-the-scenes",
                 "creator-interview", "film-archive"}


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate visual-style JSON property: {key}")
        result[key] = value
    return result


def validate_visual_styles(document: Any) -> list[str]:
    errors: list[str] = []

    def keys(value: Any, required: set[str], prefix: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            errors.append(f"{prefix} must be an object")
            return {}
        for key in sorted(required - value.keys()):
            errors.append(f"{prefix}.{key} missing")
        for key in sorted(value.keys() - required):
            errors.append(f"{prefix}.{key} unexpected")
        return value

    def meaningful(value: Any, prefix: str) -> None:
        if not isinstance(value, str) or not 4 <= len(value.strip()) <= 1000:
            errors.append(f"{prefix} must be meaningful bounded text")

    root = keys(document, {"schemaVersion", "retrievedOn", "methodology", "entries"}, "collection")
    if root.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("collection.schemaVersion unsupported")
    try:
        if (type(root.get("retrievedOn")) is not str or
                not re.fullmatch(r"\d{4}-\d{2}-\d{2}", root["retrievedOn"])):
            raise ValueError
        date.fromisoformat(root["retrievedOn"])
    except (ValueError, TypeError, KeyError):
        errors.append("collection.retrievedOn must be an ISO date")
    meaningful(root.get("methodology"), "collection.methodology")
    entries = root.get("entries")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 200:
        errors.append("collection.entries must contain 1–200 items")
        return errors
    ids: set[str] = set()
    for i, raw in enumerate(entries):
        prefix = f"entries[{i}]"
        item = keys(raw, {"id", "name", "family", "styleSignals", "studyQuestions",
                          "creatorSource", "reviewStatus", "audienceStatus", "rights"}, prefix)
        identifier = item.get("id")
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
            errors.append(f"{prefix}.id malformed")
        elif identifier in ids:
            errors.append(f"{prefix}.id duplicated")
        else:
            ids.add(identifier)
        meaningful(item.get("name"), f"{prefix}.name")
        if not isinstance(item.get("family"), str) or item["family"] not in _FAMILIES:
            errors.append(f"{prefix}.family unsupported")
        signals = item.get("styleSignals")
        if (not isinstance(signals, list) or not 2 <= len(signals) <= 8
                or any(not isinstance(s, str) or not 4 <= len(s.strip()) <= 160 for s in signals)
                or len(set(signals)) != len(signals)):
            errors.append(f"{prefix}.styleSignals invalid")
        questions = keys(item.get("studyQuestions"), {"camera", "lighting", "cadence"},
                         f"{prefix}.studyQuestions")
        for kind in ("camera", "lighting", "cadence"):
            meaningful(questions.get(kind), f"{prefix}.studyQuestions.{kind}")
        source = keys(item.get("creatorSource"),
                      {"creator", "work", "url", "sourceType", "sourceClaim"},
                      f"{prefix}.creatorSource")
        for name in ("creator", "work", "sourceClaim"):
            meaningful(source.get(name), f"{prefix}.creatorSource.{name}")
        if not isinstance(source.get("sourceType"), str) or source["sourceType"] not in _SOURCE_TYPES:
            errors.append(f"{prefix}.creatorSource.sourceType unsupported")
        url = source.get("url")
        try:
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or not parsed.hostname or
                    parsed.username is not None or parsed.password is not None or
                    parsed.port not in (None, 443) or parsed.fragment):
                raise ValueError
        except (TypeError, ValueError, AttributeError):
            errors.append(f"{prefix}.creatorSource.url must be HTTPS with no credentials")
        if item.get("reviewStatus") != "source-described-not-frame-reviewed":
            errors.append(f"{prefix}.reviewStatus cannot imply a frame review")
        if item.get("audienceStatus") != "not-measured-for-this-work":
            errors.append(f"{prefix}.audienceStatus cannot imply popularity evidence")
        if item.get("rights") != "inspiration-only":
            errors.append(f"{prefix}.rights cannot imply reuse permission")
    return errors


def load_visual_styles(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 262_144:
        raise ValueError(f"visual styles must be regular JSON of at most 256 KiB: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError(f"invalid visual styles JSON: {exc}") from exc
    errors = validate_visual_styles(data)
    if errors:
        raise ValueError("invalid visual styles catalog:\n" + "\n".join(errors))
    return data


def search_visual_styles(document: dict[str, Any], query: str = "", *,
                         family: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    if family and family not in _FAMILIES:
        raise ValueError("unsupported visual style family")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("visual style result limit must be 1..100")
    tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    matched = []
    for item in document["entries"]:
        if family and item["family"] != family:
            continue
        haystack = " ".join((item["id"], item["name"], item["family"],
                              *item["styleSignals"], item["creatorSource"]["creator"],
                              item["creatorSource"]["work"],
                              item["creatorSource"]["sourceClaim"])).lower()
        if tokens and not all(token in haystack for token in tokens):
            continue
        matched.append(item)
    return sorted(matched, key=lambda item: item["id"])[:limit]


def style_family_counts(document: dict[str, Any]) -> dict[str, int]:
    return dict(sorted(Counter(entry["family"] for entry in document["entries"]).items()))
