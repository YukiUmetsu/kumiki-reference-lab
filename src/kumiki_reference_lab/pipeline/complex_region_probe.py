"""Opt-in geometry-only short probes for complex-background ROI candidates.

A regional motion mask is not an object detection. This runs the existing
feature-supported local tracker for a short trial, accepts only stable screen
geometry, and NEVER changes the region's anonymous identity provenance.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from kumiki_reference_lab.pipeline.seeded_subjects import (
    build_seeded_region_tracks, validate_region_seeds,
)

VERSION = "kumiki.complex-region-geometry-probe.v1"
_SEEDS = "kumiki.online-region-seeds.v1"


def _screen_displacement(observations: list[dict[str, Any]]) -> float:
    def middle(box: list[float]) -> tuple[float, float]:
        return box[0] + box[2] / 2, box[1] + box[3] / 2
    a = middle(observations[0]["boxNormalized"])
    b = middle(observations[-1]["boxNormalized"])
    return math.dist(a, b)


def probe_complex_regions(
    workspace: Path, shots: dict[str, Any],
    discovery: dict[str, Any], *,
    max_probes: int = 4, probe_frames: int = 12,
    min_supported_frames: int = 6,
) -> dict[str, Any]:
    """Select feature-stable *geometry*; no semantic/identity verification."""
    from kumiki_reference_lab.pipeline.agent_frame_review import load_workspace
    if (type(max_probes) is not int or not 1 <= max_probes <= 8
            or type(probe_frames) is not int or not 8 <= probe_frames <= 30
            or type(min_supported_frames) is not int
            or not 5 <= min_supported_frames <= probe_frames):
        raise ValueError("complex geometry probe budget invalid")
    manifest, numeric, _ = load_workspace(workspace)
    if (not isinstance(shots, dict) or
            shots.get("sourceSha256") != manifest["sourceSha256"] or
            shots.get("frameCount") != manifest["frameCount"] or
            not isinstance(discovery, dict) or
            discovery.get("sourceSha256") != manifest["sourceSha256"] or
            discovery.get("frameCount") != manifest["frameCount"] or
            not isinstance(discovery.get("proposals"), list)):
        raise ValueError("complex ROI source/shot provenance mismatch")
    by_shot = {s["shotId"]: s for s in shots["shots"]}
    selected = []
    for proposal in discovery["proposals"]:
        if len(selected) >= max_probes:
            break
        if (proposal.get("eligibleForAutomaticTracking") is not False
                or proposal.get("regionDiscoveryMethod") !=
                "temporal-change-only-unverified-shape"):
            continue
        shot = by_shot.get(proposal.get("shotId"))
        index = proposal.get("startFrameIndex")
        box = proposal.get("boxNormalized")
        if (shot is None or type(index) is not int
                or not shot["startFrameIndex"] <= index
                or index + min_supported_frames >
                shot["endFrameIndexExclusive"]):
            continue
        # Avoid tiny change fragments: spatial support has to be large enough
        # to support independent local features, not a single moving edge.
        if (not isinstance(box, list) or len(box) != 4
                or box[2] * manifest["width"] < 24
                or box[3] * manifest["height"] < 20
                or box[2] * box[3] > .40):
            continue
        selected.append(proposal)
    seeds = {
        "schemaVersion": _SEEDS,
        "seedOrigin": "auto-motion-proposal",
        "sourceSha256": manifest["sourceSha256"],
        "subjects": [{
            "id": item["id"], "kind": "other",
            "label": item["label"], "startFrameIndex": item["startFrameIndex"],
            "boxNormalized": item["boxNormalized"],
        } for item in selected],
    }
    if seeds["subjects"]:
        validate_region_seeds(
            seeds, source_sha=manifest["sourceSha256"],
            frame_count=manifest["frameCount"])
        result = build_seeded_region_tracks(
            workspace, shots, seeds_document=seeds,
            max_frames_per_subject=probe_frames)
    else:
        result = {"status": "no-eligible-complex-candidates", "tracks": []}
    accepted: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for item in selected:
        track = next((t for t in result.get("tracks", [])
                      if t["id"] == item["id"]), None)
        observation = track.get("observations", []) if track else []
        supported = [
            p for p in observation[1:]
            if p.get("status") == "tracked-screen-region-candidate"
            and type(p.get("supportFeatureCount")) is int
            and p["supportFeatureCount"] >= 6
            and type(p.get("inlierFraction")) in (int, float)
            and math.isfinite(p["inlierFraction"])
            and p["inlierFraction"] >= .7
        ]
        # Only count a consecutive prefix, never isolated feature successes.
        contiguous = 1
        for p in observation[1:]:
            if (p.get("frameIndex") != item["startFrameIndex"] + contiguous
                    or p not in supported):
                break
            contiguous += 1
        valid = (contiguous >= min_supported_frames and
                 len(supported) >= min_supported_frames - 1 and
                 _screen_displacement(observation[:contiguous]) >= .015)
        decisions.append({
            "proposalId": item["id"], "shotId": item["shotId"],
            "trialObservationCount": len(observation),
            "consecutiveSupportedFrameCount": contiguous,
            "trialEndStatus": track["endStatus"] if track else result["status"],
            "status": ("geometry-supported-anonymous-screen-track"
                       if valid else "abstain-insufficient-local-geometry"),
            "semanticIdentityVerified": False,
        })
        if valid:
            accepted.append(next(s for s in seeds["subjects"]
                                 if s["id"] == item["id"]))
    return {
        "schemaVersion": VERSION, "sourceSha256": manifest["sourceSha256"],
        "frameCount": manifest["frameCount"],
        "maxProbes": max_probes, "probeFrames": probe_frames,
        "attemptedCount": len(selected), "supportedSeedCount": len(accepted),
        "probeDependencyStatus": result["status"],
        "decisions": decisions,
        "acceptedSeeds": {
            "schemaVersion": _SEEDS,
            "seedOrigin": "auto-motion-proposal",
            "sourceSha256": manifest["sourceSha256"],
            "subjects": accepted,
        },
        "status": ("geometry-only-probe-complete" if selected
                   else "no-eligible-complex-proposals"),
        "limitations": [
            "Short-term feature geometry does not establish a person or object class.",
            "A moving textured background or camera can pass this test.",
            "The short probe is not persistent identity or cross-cut tracking.",
            "Failed probes and missing optional CV2 are explicit abstentions.",
            "Only existing ignored previews and local geometric measurements are used.",
        ],
    }
