"""Strict lightweight validation of authored cinematic technique JSON entries."""

from __future__ import annotations

import math
import re
from typing import Any


TECHNIQUE_SCHEMA_VERSION = "kumiki.cinematic-technique.v1"
INDEX_SCHEMA_VERSION = "kumiki.cinematic-techniques-index.v1"
CATEGORIES = frozenset({"story", "attention", "camera", "lighting", "motion",
                        "editing", "materials", "typography", "sound"})
STATES = frozenset({"research-candidate", "implementation-proposed", "implemented", "verified"})
IMPLEMENTATION_STATES = frozenset({"not-implemented", "in-progress", "implemented", "reviewed"})
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def validate_technique(data: Any) -> list[str]:
    """Return actionable errors without coercing/repairing authored research."""
    errors: list[str] = []

    def obj(value: Any, path: str, required: set[str], optional: set[str] = frozenset()) -> dict:
        if not isinstance(value, dict):
            errors.append(f"{path} must be an object")
            return {}
        missing = required - value.keys()
        unexpected = value.keys() - required - optional
        for key in sorted(missing):
            errors.append(f"{path}.{key} is required")
        for key in sorted(unexpected):
            errors.append(f"{path}.{key} is unknown")
        return value

    def nonempty(value: Any, path: str) -> None:
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path} must be nonempty text")

    def string_list(value: Any, path: str, *, minimum: int = 0) -> None:
        if not isinstance(value, list) or len(value) < minimum or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            errors.append(f"{path} must be a list of {minimum}+ nonempty strings")
        elif len(set(value)) != len(value):
            errors.append(f"{path} must not contain duplicates")

    def numeric(value: Any, path: str) -> bool:
        try:
            finite = type(value) in (int, float) and math.isfinite(value)
        except (ValueError, OverflowError):
            finite = False
        if not finite:
            errors.append(f"{path} must be a finite number")
            return False
        return True

    data = obj(data, "technique", {"schemaVersion", "id", "revision", "category", "name",
                                     "status", "summary", "intent", "mechanism", "recipe",
                                     "parameters", "evidence", "kumiki", "qa"})
    if data.get("schemaVersion") != TECHNIQUE_SCHEMA_VERSION:
        errors.append("technique.schemaVersion must be the current version")
    identifier = data.get("id")
    if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier):
        errors.append("technique.id must be a lowercase dotted/dashed identifier")
    category = data.get("category")
    if not isinstance(category, str) or category not in CATEGORIES:
        errors.append("technique.category is unsupported")
    if isinstance(identifier, str) and isinstance(category, str) and not identifier.startswith(category + "."):
        errors.append("technique.id must start with category followed by a dot")
    if type(data.get("revision")) is not int or data["revision"] < 1:
        errors.append("technique.revision must be a positive integer")
    if not isinstance(data.get("status"), str) or data["status"] not in STATES:
        errors.append("technique.status is unsupported")
    for name in ("name", "summary"):
        nonempty(data.get(name), "technique." + name)

    intent = obj(data.get("intent"), "intent", {"storyPurposes", "viewerQuestion",
                                                     "desiredPerceptualResult", "avoidWhen"})
    string_list(intent.get("storyPurposes"), "intent.storyPurposes", minimum=1)
    string_list(intent.get("avoidWhen"), "intent.avoidWhen", minimum=1)
    nonempty(intent.get("viewerQuestion"), "intent.viewerQuestion")
    nonempty(intent.get("desiredPerceptualResult"), "intent.desiredPerceptualResult")

    mechanism = obj(data.get("mechanism"), "mechanism", {"visibleCues", "plausibleCauses", "unknowns"})
    for name in ("visibleCues", "plausibleCauses", "unknowns"):
        string_list(mechanism.get(name), "mechanism." + name, minimum=1)

    recipe = obj(data.get("recipe"), "recipe", {"beats", "craftNotes", "fallback"})
    string_list(recipe.get("craftNotes"), "recipe.craftNotes", minimum=2)
    nonempty(recipe.get("fallback"), "recipe.fallback")
    beats = recipe.get("beats")
    if not isinstance(beats, list) or len(beats) < 2:
        errors.append("recipe.beats must contain at least two sequential beats")
    else:
        previous_end = 0.0
        ids: set[str] = set()
        for i, raw in enumerate(beats):
            beat = obj(raw, f"recipe.beats[{i}]", {"id", "start", "end", "direction", "attentionTarget"})
            beat_id = beat.get("id")
            nonempty(beat_id, f"recipe.beats[{i}].id")
            if isinstance(beat_id, str):
                if beat_id in ids:
                    errors.append(f"recipe.beats[{i}].id duplicates another beat")
                ids.add(beat_id)
            nonempty(beat.get("direction"), f"recipe.beats[{i}].direction")
            nonempty(beat.get("attentionTarget"), f"recipe.beats[{i}].attentionTarget")
            start, end = beat.get("start"), beat.get("end")
            if numeric(start, f"recipe.beats[{i}].start") and numeric(end, f"recipe.beats[{i}].end"):
                if not (0 <= start < end <= 1):
                    errors.append(f"recipe.beats[{i}] must have 0 <= start < end <= 1")
                if abs(start - previous_end) > 0.000001:
                    errors.append(f"recipe.beats[{i}] has a gap/overlap from previous beat")
                previous_end = end
        if abs(previous_end - 1) > 0.000001:
            errors.append("recipe.beats must end at normalized time 1")

    parameters = data.get("parameters")
    if not isinstance(parameters, list) or not parameters:
        errors.append("parameters must contain at least one authored control")
    else:
        seen: set[str] = set()
        for i, raw in enumerate(parameters):
            parameter = obj(raw, f"parameters[{i}]", {"name", "unit", "min", "max",
                                                           "authoredDefault", "visualImpact", "failureSigns"})
            nonempty(parameter.get("name"), f"parameters[{i}].name")
            nonempty(parameter.get("unit"), f"parameters[{i}].unit")
            nonempty(parameter.get("visualImpact"), f"parameters[{i}].visualImpact")
            string_list(parameter.get("failureSigns"), f"parameters[{i}].failureSigns", minimum=1)
            if isinstance(parameter.get("name"), str) and parameter["name"] in seen:
                errors.append(f"parameters[{i}].name is duplicated")
            if isinstance(parameter.get("name"), str):
                seen.add(parameter["name"])
            values = (parameter.get("min"), parameter.get("authoredDefault"), parameter.get("max"))
            if all(numeric(value, f"parameters[{i}].{field}") for value, field in
                   zip(values, ("min", "authoredDefault", "max"))):
                if not values[0] <= values[1] <= values[2]:
                    errors.append(f"parameters[{i}] must satisfy min <= authoredDefault <= max")

    evidence = data.get("evidence")
    if not isinstance(evidence, list):
        errors.append("evidence must be a list, possibly empty for research candidates")
    else:
        for i, raw in enumerate(evidence):
            entry = obj(raw, f"evidence[{i}]", {"sourceSha256", "artifact", "sourcePts",
                                                     "observation", "method"})
            if not isinstance(entry.get("sourceSha256"), str) or not _SHA256.fullmatch(entry["sourceSha256"]):
                errors.append(f"evidence[{i}].sourceSha256 must be a full hex SHA-256")
            for name in ("artifact", "observation", "method"):
                nonempty(entry.get(name), f"evidence[{i}].{name}")
            pts = entry.get("sourcePts")
            if not isinstance(pts, list) or not pts or any(type(item) is not int for item in pts):
                errors.append(f"evidence[{i}].sourcePts must list actual integer PTS")

    kumiki = obj(data.get("kumiki"), "kumiki", {"registryId", "implementationStatus", "adapterNotes"})
    if kumiki.get("registryId") is not None:
        nonempty(kumiki.get("registryId"), "kumiki.registryId")
    if (not isinstance(kumiki.get("implementationStatus"), str) or
            kumiki["implementationStatus"] not in IMPLEMENTATION_STATES):
        errors.append("kumiki.implementationStatus is unsupported")
    nonempty(kumiki.get("adapterNotes"), "kumiki.adapterNotes")
    qa = obj(data.get("qa"), "qa", {"acceptanceChecks", "humanApproved", "referenceCompared"})
    string_list(qa.get("acceptanceChecks"), "qa.acceptanceChecks", minimum=2)
    if type(qa.get("humanApproved")) is not bool or type(qa.get("referenceCompared")) is not bool:
        errors.append("qa humanApproved/referenceCompared must be booleans")

    if data.get("status") == "verified" and (
        not evidence or kumiki.get("implementationStatus") != "reviewed" or
        not kumiki.get("registryId") or qa.get("humanApproved") is not True or
        qa.get("referenceCompared") is not True
    ):
        errors.append("verified techniques require evidence, a reviewed registry entry, and human-approved comparison")
    return errors
