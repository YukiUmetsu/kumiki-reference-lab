"""Conservative within-channel visual-event comparisons for reviewed source rows.

All video-to-file bindings and event interpretations are reviewer declarations.
This cannot verify original footage, its rights, physical camera rigs, or causality.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from kumiki_reference_lab.catalog.visual_study_plan import build_visual_study_plan
from kumiki_reference_lab.reviews.visual_events import summarize_visual_events, validate_visual_events


SCHEMA_VERSION = "kumiki.paired-visual-review.v1"
_BINDING_VERSION = "kumiki.visual-study-media-bindings.v1"
_DECLARED = "self-declared-source-video-to-local-media-not-independently-verified"
_SHA = re.compile(r"[a-f0-9]{64}")
_ROLES = ("higherViewedRow", "lowerViewedRow")


def load_visual_study_bindings(path: Path) -> dict[str, Any]:
    """Reject oversized, symlinked or ambiguous JSON before validating joins."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16_384:
        raise ValueError("study media bindings must be a regular JSON file of at most 16 KiB")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"duplicate media binding JSON property: {key}")
            obj[key] = value
        return obj

    try:
        result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                            parse_constant=lambda value: (_ for _ in ()).throw(
                                ValueError(f"non-finite JSON value in bindings: {value}")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"invalid media binding JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise ValueError("media bindings must be an object")
    return result


def _validate_bindings(bindings: Any, pair: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if (not isinstance(bindings, dict) or set(bindings) !=
            {"schemaVersion", "pairId", "evidenceStatus", "mediaLinks"} or
            bindings["schemaVersion"] != _BINDING_VERSION or
            bindings["pairId"] != pair["id"] or
            bindings["evidenceStatus"] != _DECLARED):
        raise ValueError("media bindings require exact version, selected pair and declared evidence status")
    links = bindings["mediaLinks"]
    if not isinstance(links, dict) or set(links) != set(_ROLES):
        raise ValueError("media links must identify both higher and lower source rows")
    observed_media: set[str] = set()
    for role in _ROLES:
        entry = links[role]
        original = pair[role]
        candidate = original["videoIdentityCandidate"]
        if candidate is None:
            raise ValueError(f"{role} has no indexed original-video identity candidate")
        if not isinstance(entry, dict) or set(entry) != {
                "sourceRowSha256", "youtubeId", "mediaSha256", "streamIndex"}:
            raise ValueError(f"{role} media link requires exact fields")
        if (entry["sourceRowSha256"] != original["sourceRowSha256"] or
                entry["youtubeId"] != candidate["youtubeId"]):
            raise ValueError(f"{role} media link does not match the current source-table row and indexed ID")
        sha = entry["mediaSha256"]
        if not isinstance(sha, str) or _SHA.fullmatch(sha) is None or sha in observed_media:
            raise ValueError("media hashes must be distinct lowercase SHA-256 digests")
        observed_media.add(sha)
        if type(entry["streamIndex"]) is not int or not 0 <= entry["streamIndex"] <= 64:
            raise ValueError(f"{role} stream index is invalid")
    return links


def compare_paired_visual_reviews(audience: dict[str, Any], candidates: dict[str, Any], *,
                                  pair_id: str, bindings: dict[str, Any],
                                  higher_review: dict[str, Any],
                                  lower_review: dict[str, Any]) -> dict[str, Any]:
    """Compare rates only when both reviewers declare near-whole-film coverage.

    The catalog duration and the binding are *not* verified against the media;
    near-whole-film coverage is merely a consistency check on reviewer claims.
    """
    if not isinstance(pair_id, str) or not 1 <= len(pair_id) <= 160:
        raise ValueError("selected study pair ID must be a bounded string")
    plan = build_visual_study_plan(audience, identity_candidates=candidates)
    matches = [pair for channel in plan["channels"] for pair in channel["selectedPairs"]
               if pair["id"] == pair_id]
    if len(matches) != 1:
        raise ValueError("pair ID does not identify exactly one selected default study pair")
    pair = matches[0]
    links = _validate_bindings(bindings, pair)
    reviews = {"higherViewedRow": higher_review, "lowerViewedRow": lower_review}
    measured: dict[str, dict[str, Any]] = {}
    for role in _ROLES:
        review = reviews[role]
        validate_visual_events(review)
        link = links[role]
        if (review["sourceSha256"] != link["mediaSha256"] or
                review["sourceStreamIndex"] != link["streamIndex"]):
            raise ValueError(f"{role} visual review identifies a different local media source or stream")
        summary = summarize_visual_events(review)
        catalog_duration = pair[role]["durationSeconds"]
        fraction = summary["reviewedWindowSeconds"] / catalog_duration
        # Source runtimes are reported in whole seconds and may be rounded.
        plausible_window = 0.95 <= fraction <= 1.05
        measured[role] = {
            "sourceRowSha256": pair[role]["sourceRowSha256"],
            "indexedYoutubeId": pair[role]["videoIdentityCandidate"]["youtubeId"],
            "mediaSha256": link["mediaSha256"],
            "catalogDurationSeconds": catalog_duration,
            "reviewedWindowFractionOfCatalogDuration": round(fraction, 6),
            "nearWholeRuntimeBySelfDeclaration": plausible_window,
            "review": summary,
        }

    high = measured["higherViewedRow"]
    low = measured["lowerViewedRow"]
    h_review, l_review = higher_review["reviewer"], lower_review["reviewer"]
    same_reviewer = h_review == l_review
    comparison_ready = bool(same_reviewer and all(
        measured[role]["nearWholeRuntimeBySelfDeclaration"] and
        measured[role]["review"]["eventRatesAvailable"] for role in _ROLES))
    differences = None
    if comparison_ready:
        h_summary, l_summary = high["review"], low["review"]
        h_types = {(item["category"], item["kind"]): item for item in h_summary["eventTypeRates"]}
        l_types = {(item["category"], item["kind"]): item for item in l_summary["eventTypeRates"]}
        per_type = []
        for category, kind in sorted(set(h_types) | set(l_types)):
            h = h_types.get((category, kind), {})
            l = l_types.get((category, kind), {})
            h_rate, l_rate = h.get("eventsPerReviewedMinute", 0), l.get("eventsPerReviewedMinute", 0)
            per_type.append({"category": category, "kind": kind,
                             "higherCount": h.get("count", 0), "lowerCount": l.get("count", 0),
                             "higherEventsPerReviewedMinute": h_rate,
                             "lowerEventsPerReviewedMinute": l_rate,
                             "higherMinusLowerEventsPerReviewedMinute": round(h_rate - l_rate, 6)})
        differences = {
            "cameraEventsPerReviewedMinuteHigherMinusLower": round(
                h_summary["cameraMovementEventsPerReviewedMinute"] -
                l_summary["cameraMovementEventsPerReviewedMinute"], 6),
            "lightingEventsPerReviewedMinuteHigherMinusLower": round(
                h_summary["lightingChangeEventsPerReviewedMinute"] -
                l_summary["lightingChangeEventsPerReviewedMinute"], 6),
            "byEventKind": per_type,
        }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "pairId": pair["id"],
        "sourceRetrievedOn": plan["retrievedOn"],
        "reportedViewsRatio": pair["reportedViewsRatio"],
        "sourceAgeGapDays": pair["sourceAgeGapDays"],
        "roles": measured,
        "sameSelfDeclaredReviewer": same_reviewer,
        "pairedEventRateDifferencesAvailable": comparison_ready,
        "pairedEventRateDifferences": differences,
        "evidenceStatus": "self-declared-local-media-join-and-reviewed-events-not-independently-verified",
        "interpretationLimits": [
            "A self-declared SHA binding to an indexed YouTube ID does not establish original media identity, rights, or complete viewing.",
            "Near-whole runtime checks use rounded third-party durations and cannot independently verify full-film coverage.",
            "Camera and light events are subjective annotations, not recovered physical camera or lamp operations.",
            "A non-null difference is descriptive for two reviewer-annotated windows, not a style-popularity effect or causal estimate.",
            "Shot cuts, sound editing and visual styles require separate comparable annotations; they are not inferred here.",
        ],
    }
