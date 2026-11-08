"""Human- or model-authored, evidence-bound correction notes for FD1 films.

The code checks provenance and annotation structure only. It cannot certify an
artistic judgment, and it never modifies the underlying reference or render.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.core.artifacts import write_json_artifact
from kumiki_reference_lab.integrations.kumiki.film_map_review import _verify_existing


VERSION = "kumiki.film-map-feedback.v1"
_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$")
_FINDING_ID = re.compile(r"^finding-[a-z0-9][a-z0-9-]{0,63}$")
_CATEGORIES = frozenset({
    "composition", "camera", "lighting", "material", "animation", "readability",
    "story-clarity", "attention", "continuity", "timing", "sound", "other",
})
_SEVERITIES = frozenset({"blocking", "significant", "polish", "observation"})


def _bounded_json(path: Path, limit: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("expected a bounded, regular review JSON file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _evidence(review_manifest: Path) -> dict[str, Any]:
    if review_manifest.name != "film-map-review.json":
        raise ValueError("expected film-map-review.json")
    report = _bounded_json(review_manifest, 1_000_000)
    settings = report.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("invalid film-map review settings")
    # Verify the complete immutable directory, not just a self-reported hash.
    _verify_existing(review_manifest.parent, settings)
    files = {entry["path"]: entry["sha256"] for entry in report["files"]}
    anchors = []
    seen = set()
    for ordinal, pair in enumerate(report["pairs"]):
        if not isinstance(pair, dict):
            raise ValueError("invalid paired review anchor")
        anchor_id = pair.get("id")
        source = pair.get("source")
        film = pair.get("film")
        src_image, film_image = f"source/frame-{ordinal:03d}.jpg", f"film/frame-{ordinal:03d}.jpg"
        if (not isinstance(anchor_id, str) or not _ID.fullmatch(anchor_id) or
                anchor_id in seen or not isinstance(source, dict) or
                not isinstance(film, dict) or
                source.get("image") != src_image or film.get("image") != film_image or
                type(source.get("pts")) is not int or type(film.get("frame")) is not int or
                film["frame"] < 0):
            raise ValueError("film-map review has invalid or ambiguous anchor identities")
        seen.add(anchor_id)
        anchors.append({
            "id": anchor_id, "sourcePts": source["pts"], "filmFrame": film["frame"],
            "sourceImage": src_image, "sourceImageSha256": files[src_image],
            "filmImage": film_image, "filmImageSha256": files[film_image],
        })
    return {
        "reviewManifestSha256": sha256_file(review_manifest),
        "referenceVideoSha256": settings["referenceVideoSha256"],
        "renderVideoSha256": settings["renderVideoSha256"],
        "anchors": anchors,
    }


def _reviewer(kind: str, reviewer_id: str, model_id: str | None) -> dict[str, Any]:
    if kind not in ("human", "ai") or not isinstance(reviewer_id, str) or not _ID.fullmatch(reviewer_id):
        raise ValueError("reviewer kind/id must identify a human or AI author")
    if kind == "ai":
        if not isinstance(model_id, str) or not 1 <= len(model_id) <= 256:
            raise ValueError("AI reviewer requires a bounded model id")
    elif model_id is not None:
        raise ValueError("human reviewer must not declare a model id")
    return {"kind": kind, "id": reviewer_id, "modelId": model_id}


def init_film_feedback(
    review_manifest: Path, output: Path, *, reviewer_kind: str,
    reviewer_id: str, model_id: str | None = None,
) -> Path:
    """Create an empty draft outside the immutable evidence directory."""
    evidence = _evidence(review_manifest)
    if output.resolve().is_relative_to(review_manifest.parent.resolve()):
        raise ValueError("feedback drafts must be outside the immutable frame review bundle")
    draft = {
        "schemaVersion": VERSION, "evidence": evidence,
        "reviewer": _reviewer(reviewer_kind, reviewer_id, model_id),
        "reviewStatus": "draft", "findings": [],
    }
    return write_json_artifact(output, "film-map-feedback.json", draft)


def _text(value: Any, name: str, maximum: int = 2000) -> None:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise ValueError(f"{name} requires 1..{maximum} non-blank characters")


def validate_film_feedback(review_manifest: Path, feedback_path: Path) -> dict[str, Any]:
    """Validate exact evidence links and bounded actionable correction notes."""
    evidence = _evidence(review_manifest)
    if feedback_path.name != "film-map-feedback.json":
        raise ValueError("expected film-map-feedback.json")
    feedback = _bounded_json(feedback_path, 1_048_576)
    if set(feedback) != {"schemaVersion", "evidence", "reviewer", "reviewStatus", "findings"}:
        raise ValueError("film feedback has unexpected or missing fields")
    if feedback["schemaVersion"] != VERSION or feedback["evidence"] != evidence:
        raise ValueError("film feedback is stale or references different frame evidence")
    if feedback["reviewStatus"] != "draft":
        raise ValueError("structural review does not grant artistic quality approval")
    author = feedback["reviewer"]
    if not isinstance(author, dict) or set(author) != {"kind", "id", "modelId"}:
        raise ValueError("invalid review author")
    _reviewer(author["kind"], author["id"], author["modelId"])
    findings = feedback["findings"]
    if not isinstance(findings, list) or len(findings) > 48:
        raise ValueError("film feedback is limited to 48 findings")
    valid_anchors = {item["id"] for item in evidence["anchors"]}
    seen = set()
    severity_count = {name: 0 for name in sorted(_SEVERITIES)}
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {
                "id", "anchorId", "category", "severity", "observation", "suggestedChange"}:
            raise ValueError("invalid film feedback finding fields")
        identifier = finding["id"]
        if (not isinstance(identifier, str) or not _FINDING_ID.fullmatch(identifier) or
                identifier in seen):
            raise ValueError("film feedback finding ids must be unique finding-<slug>")
        seen.add(identifier)
        if not isinstance(finding["anchorId"], str) or finding["anchorId"] not in valid_anchors:
            raise ValueError("film feedback finding points outside the verified frame anchors")
        if (not isinstance(finding["category"], str) or
                not isinstance(finding["severity"], str) or
                finding["category"] not in _CATEGORIES or finding["severity"] not in _SEVERITIES):
            raise ValueError("invalid film feedback category or severity")
        _text(finding["observation"], "observed visual problem")
        if finding["severity"] == "observation":
            if finding["suggestedChange"] is not None:
                _text(finding["suggestedChange"], "optional suggestion")
        else:
            _text(finding["suggestedChange"], "actionable correction")
        severity_count[finding["severity"]] += 1
    return {
        "schemaVersion": VERSION, "status": "structure-and-evidence-verified-only",
        "artisticApproval": "not-granted", "evidenceSha256": evidence["reviewManifestSha256"],
        "reviewerKind": author["kind"], "findingCount": len(findings),
        "severityCounts": severity_count,
    }
