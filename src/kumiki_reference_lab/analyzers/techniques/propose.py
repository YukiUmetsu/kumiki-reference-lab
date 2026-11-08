"""Conservative technique review cues from an integrity-checked analysis bundle.

These are image observations linked to authored catalog ideas. They are never
claims about the reference's physical camera, lights, objects, or story intent.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.catalog.store import load_catalog
from kumiki_reference_lab.contracts.analysis import (
    APPEARANCE_VERSION, SPARSE_FLOW_VERSION, TECHNIQUE_PROPOSALS_VERSION,
)
from kumiki_reference_lab.pipeline.analyze import _validate_existing


_SUGGESTIONS = {
    "camera.motivated-macro-dolly": {
        "cue": "Repeated coherent image-plane enlargement",
        "alternatives": [
            "Digital crop or focal-length change", "Camera translation toward scene geometry",
            "Object motion, scaling, or animated 2.5D layers",
        ],
        "questions": [
            "Does near/far parallax support a real approach, or only image magnification?",
            "Is there a story-critical detail that warrants an intentional closer view?",
            "Does the movement ease to a readable hold without cropping essential context?",
        ],
    },
    "lighting.softbox-curvature-reveal": {
        "cue": "Bright-pixel centroid changes position while global luma stays similar",
        "alternatives": [
            "Motion of a bright object or its material", "Changing framing or compositing mask",
            "Animated material or reflection with no physical light movement",
        ],
        "questions": [
            "Is the moving bright region a reflection across an actual material surface?",
            "Do curvature and material detail become clearer, rather than merely brighter?",
            "Is any light rig, light direction, or physically plausible size actually evidenced?",
        ],
    },
}

_GATES = {
    "enlargement": {
        "minimumAdjacentPairs": 2,
        "minimumInlierFraction": 0.60,
        "minimumImageScale": 1.018,
        "maximumImageScale": 1.30,
        "maximumAnisotropy": 1.12,
        "maximumAbsRotationDegrees": 5.0,
        "minimumSpatialSpanFraction": 0.30,
    },
    "brightCentroid": {
        "minimumConsecutiveFrames": 3,
        "minimumBrightPixelFraction": 0.01,
        "maximumBrightPixelFraction": 0.45,
        "minimumCentroidDisplacementNormalized": 0.08,
        "maximumLumaProxyRange": 0.10,
        "maximumBrightFractionRange": 0.12,
    },
}


def _json_file(path: Path, *, limit: int) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
        raise ValueError(f"missing, symbolic or oversized analysis artifact: {path.name}")
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result
    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           object_pairs_hook=reject_duplicate_keys,
                           parse_constant=lambda value: (_ for _ in ()).throw(
                               ValueError(f"non-finite JSON constant {value}")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON in {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"analysis artifact must be an object: {path.name}")
    return value


def _verified_bundle(manifest_path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if manifest_path.name != "analysis-run.json":
        raise ValueError("expected an analysis-run.json file")
    manifest = _json_file(manifest_path, limit=262_144)
    settings = manifest.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("analysis-run.json has invalid settings")
    # Existing run verification checks every file checksum, unlisted files,
    # paths/symlinks, stage metadata and inspected source provenance.
    _validate_existing(manifest_path.parent, settings)
    artifacts = manifest["artifacts"]
    reports = {}
    for key in ("inspect", "cuts", "sparseFlow", "appearance"):
        if key in artifacts:
            reports[key] = _json_file(manifest_path.parent / artifacts[key], limit=4_194_304)
    original = reports["inspect"]
    video = original["video"]
    cut_report = reports["cuts"]
    source_sha = settings["sourceSha256"]
    source_timebase = video["sourceTimebase"]
    stream_index = video["streamIndex"]
    if (cut_report.get("sourceSha256") != source_sha or
            cut_report.get("sourceTimebase") != source_timebase or
            cut_report.get("sourceStreamIndex") != stream_index):
        raise ValueError("cut report provenance does not match analysis run")
    cut_pts = [item["sourcePts"] for item in cut_report["candidates"]]
    if any(type(x) is not int for x in cut_pts) or cut_pts != sorted(set(cut_pts)):
        raise ValueError("cut report does not contain sorted unique source PTS")
    for key, version in (("sparseFlow", SPARSE_FLOW_VERSION),
                         ("appearance", APPEARANCE_VERSION)):
        if key not in reports:
            continue
        report = reports[key]
        if (report.get("schemaVersion") != version or
                report.get("sourceSha256") != source_sha or
                report.get("sourceTimebase") != source_timebase or
                report.get("sourceStreamIndex") != stream_index or
                report.get("cutCandidatePts") != cut_pts):
            raise ValueError(f"{key} evidence is inconsistent with verified run")
    return manifest, reports


def _cue(*, technique_id: str, entry: dict[str, Any], source_sha: str,
         start: int, end: int, artifact: str, measurements: dict[str, Any]) -> dict[str, Any]:
    if type(start) is not int or type(end) is not int or end <= start:
        raise ValueError("technique evidence needs an increasing source PTS range")
    identity = hashlib.sha256(f"{source_sha}:{technique_id}:{start}:{end}".encode()).hexdigest()[:16]
    definition = _SUGGESTIONS[technique_id]
    return {
        "id": f"cue-{identity}", "techniqueId": technique_id,
        "catalogRevision": entry["revision"], "catalogEntrySha256": entry["_entrySha256"],
        "interpretationStatus": "review-required-not-verified",
        "visibleCueHypothesis": definition["cue"],
        "sourcePtsRange": {"startPts": start, "endPts": end},
        "evidence": {"artifact": artifact, "startPts": start,
                     "endPts": end, "measurements": measurements},
        "plausibleAlternatives": definition["alternatives"],
        "reviewQuestions": definition["questions"],
    }


def _expansion_cues(report: dict[str, Any], entry: dict[str, Any],
                    source_sha: str) -> list[dict[str, Any]]:
    gates = _GATES["enlargement"]
    pairs = report["pairs"]
    accepted = []
    for pair in pairs:
        if pair["status"] == "cut-boundary":
            accepted.append(None)
            continue
        geometry = pair.get("geometryHypothesis")
        model = geometry.get("model") if isinstance(geometry, dict) else None
        valid = (geometry is not None and geometry.get("status") ==
                 "affine-image-plane-candidate" and isinstance(model, dict) and
                 model.get("reflectionOrInvalidGeometry") is False and
                 model["inlierFraction"] >= gates["minimumInlierFraction"] and
                 gates["minimumImageScale"] <= model["areaScaleCandidate"] <=
                 gates["maximumImageScale"] and
                 model["anisotropyCandidate"] <= gates["maximumAnisotropy"] and
                 abs(model["rotationDegreesCandidate"]) <= gates["maximumAbsRotationDegrees"] and
                 model["inlierSpanFraction"]["x"] >= gates["minimumSpatialSpanFraction"] and
                 model["inlierSpanFraction"]["y"] >= gates["minimumSpatialSpanFraction"])
        accepted.append(pair if valid else None)
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for pair in accepted + [None]:
        if pair is None or (current and current[-1]["endPts"] != pair["startPts"]):
            if len(current) >= gates["minimumAdjacentPairs"]:
                groups.append(current)
            current = []
        if pair is not None:
            current.append(pair)
    cues = []
    for group in groups:
        details = [item["geometryHypothesis"]["model"] for item in group]
        cues.append(_cue(
            technique_id="camera.motivated-macro-dolly", entry=entry,
            source_sha=source_sha, start=group[0]["startPts"],
            end=group[-1]["endPts"], artifact="sparse-flow.json",
            measurements={
                "sampledPairCount": len(group),
                "areaScaleCandidates": [m["areaScaleCandidate"] for m in details],
                "inlierFractions": [m["inlierFraction"] for m in details],
                "anisotropyCandidates": [m["anisotropyCandidate"] for m in details],
                "units": "dimensionless image-plane affine descriptors",
            }))
    return cues


def _highlight_cues(report: dict[str, Any], entry: dict[str, Any],
                    source_sha: str) -> list[dict[str, Any]]:
    gates = _GATES["brightCentroid"]
    samples = report["samples"]
    changes = report["changes"]
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for index, sample in enumerate(samples):
        appearance = sample["appearance"]
        centroid = appearance["brightPixelCentroid"]
        fraction = appearance["brightPixelFraction"]
        valid = (centroid is not None and
                 gates["minimumBrightPixelFraction"] <= fraction <=
                 gates["maximumBrightPixelFraction"] and
                 all(math.isfinite(centroid[k]) and 0 <= centroid[k] <= 1
                     for k in ("x", "y")))
        continuous = (index > 0 and
                      changes[index - 1]["status"] ==
                      "measured-display-appearance-change" and
                      changes[index - 1]["endPts"] == sample["sourcePts"] and
                      changes[index - 1]["startPts"] == samples[index - 1]["sourcePts"])
        if not valid or (current and not continuous):
            if len(current) >= gates["minimumConsecutiveFrames"]:
                groups.append(current)
            current = []
        if valid:
            current.append(sample)
    if len(current) >= gates["minimumConsecutiveFrames"]:
        groups.append(current)
    cues = []
    for group in groups:
        starts = group[0]["appearance"]["brightPixelCentroid"]
        ends = group[-1]["appearance"]["brightPixelCentroid"]
        dx, dy = ends["x"] - starts["x"], ends["y"] - starts["y"]
        lumas = [item["appearance"]["meanLumaProxy"] for item in group]
        fractions = [item["appearance"]["brightPixelFraction"] for item in group]
        centroid_shift = math.hypot(dx, dy)
        # Contrast/luma continuity reduces—but does not eliminate—bright-object
        # movement, compositing, camera drift and animated texture ambiguity.
        if (centroid_shift < gates["minimumCentroidDisplacementNormalized"] or
                max(lumas) - min(lumas) > gates["maximumLumaProxyRange"] or
                max(fractions) - min(fractions) > gates["maximumBrightFractionRange"]):
            continue
        cues.append(_cue(
            technique_id="lighting.softbox-curvature-reveal", entry=entry,
            source_sha=source_sha, start=group[0]["sourcePts"],
            end=group[-1]["sourcePts"], artifact="appearance.json",
            measurements={
                "sampledFrameCount": len(group),
                "brightCentroidDisplacementNormalized": {"dx": round(dx, 6),
                                                          "dy": round(dy, 6)},
                "brightCentroidDisplacementMagnitudeNormalized": round(centroid_shift, 6),
                "meanLumaProxyRange": round(max(lumas) - min(lumas), 6),
                "brightPixelFractionRange": round(max(fractions) - min(fractions), 6),
                "units": "normalized frame coordinates, display-referred RGB proxy",
            }))
    return cues


def propose_techniques(manifest_path: Path, catalog_root: Path) -> dict[str, Any]:
    """Create independently published *review* cues, never modify the source run."""
    manifest, reports = _verified_bundle(manifest_path)
    entries = {entry["id"]: entry for entry in load_catalog(catalog_root)}
    source_sha = manifest["settings"]["sourceSha256"]
    suggestions = []
    if "sparseFlow" in reports and "camera.motivated-macro-dolly" in entries:
        suggestions.extend(_expansion_cues(reports["sparseFlow"],
                                            entries["camera.motivated-macro-dolly"],
                                            source_sha))
    if "appearance" in reports and "lighting.softbox-curvature-reveal" in entries:
        suggestions.extend(_highlight_cues(reports["appearance"],
                                            entries["lighting.softbox-curvature-reveal"],
                                            source_sha))
    suggestions.sort(key=lambda item: (item["sourcePtsRange"]["startPts"],
                                       item["techniqueId"], item["id"]))
    if len(suggestions) > 32:
        suggestions = suggestions[:32]
    return {
        "schemaVersion": TECHNIQUE_PROPOSALS_VERSION,
        "status": "review-candidates-only",
        "source": {
            "sha256": source_sha,
            "streamIndex": manifest["settings"]["streamIndex"],
            "sourceTimebase": manifest["sourceTimebase"],
            "coverage": manifest["coverage"],
        },
        "provenance": {
            "analysisRunSha256": sha256_file(manifest_path),
            "catalogEntries": [{"id": item["id"], "revision": item["revision"],
                                "entrySha256": item["_entrySha256"]}
                               for item in sorted(entries.values(), key=lambda e: e["id"])],
        },
        "method": {
            "name": "deterministic-conservative-visible-cues-v1",
            "hasSemanticUnderstanding": False,
            "humanApprovalRequired": True,
            "limits": "Proposals are not identified film techniques, verified lights, tracked objects, recovered camera rigs, author keyframes, story purpose or a quality grade. Missing stage data is not negative evidence.",
            "gates": _GATES,
        },
        "availableEvidence": sorted(key for key in reports if key != "inspect"),
        "candidates": suggestions,
    }
