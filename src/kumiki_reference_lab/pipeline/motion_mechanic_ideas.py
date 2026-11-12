"""Propose original reusable animation mechanics from conservative ROI events.

This is *design ideation grounded in screen geometry*, not reverse-engineering
original keyframes, semantics, physical camera motion or actual Kumiki API
compatibility. It produces no executable animation and never calls a model.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

SCHEMA_VERSION = "kumiki.source-motion-mechanic-ideas.v1"
_TEMPORAL = "kumiki.online-multi-region-temporal.v1"
_UI_AUDIT_SHA = "ac5bf3988d4e5a74d792c2b36418512102d7b1b3"
_SHIPPED_SWAP_SHA = "662f60704851c01c0e6ef58244132fe9f29896ac"

# This is a pinned research-to-library bridge, not a source reconstruction.
# The implementation accepts newly authored pixel-space stage/assets/timing;
# source ROI boxes cannot be pasted directly into its validated public API.
_SHIPPED_SWAP = {
    "registryItem": "two-lane-swap",
    "repository": "YukiUmetsu/kumiki-ui",
    "commitSha": _SHIPPED_SWAP_SHA,
    "modules": [
        "registry/motion/two-lane-swap.ts",
        "registry/motion/two-lane-swap-react.tsx",
    ],
    "publicExports": [
        "compileTwoLaneSwap", "evaluateTwoLaneSwap", "TwoLaneSwapSvg",
    ],
    "status": "merged-and-structural-ci-passed-visual-review-pending",
    "sourceGeometryCanBeUsedAsExecutableSpec": False,
    "requiresOriginalAssetsAndAuthoredLayout": True,
    "requiresIndependentRenderedVisualApproval": True,
}
_ORIGINS = {
    "operator-seeded-not-model-recognized",
    "auto-motion-proposal-not-semantic-identity",
}

# These files were observed in kumiki-ui at _UI_AUDIT_SHA. Their mere
# existence is not proof that a ready-to-use scene recipe API exists.
_MECHANICS: dict[str, dict[str, Any]] = {
    "region-image-plane-translation": {
        "originalRecipe": "directed-screen-travel",
        "visualMechanic": "one element travels to a new image-plane anchor",
        "stages": ["establish an original visual subject",
                   "anticipate direction with a small counter-motion",
                   "follow an authored 2D path",
                   "ease into a clean resting position"],
        "controls": ["targetId", "startFrame", "durationFrames",
                     "pathAnchors", "easing", "overshootFraction"],
        "potentialRegistryModules": [
            "registry/motion/paths.ts", "registry/motion/presets.ts"],
        "notInferred": ["walking gait", "physical camera pan", "true scene depth"],
        "measurementKeys": ["deltaCenterNormalized", "netDistanceNormalized",
                            "pathDistanceNormalized", "direction"],
    },
    "region-apparent-box-area-change": {
        "originalRecipe": "apparent-scale-focus",
        "visualMechanic": "one element appears to grow or recede in a designed shot",
        "stages": ["place an original foreground asset",
                   "animate an authored visual scale progression",
                   "adjust focus and framing as a separate creative choice",
                   "settle and hold for readability"],
        "controls": ["targetId", "startFrame", "durationFrames",
                     "fromScale", "toScale", "focalAnchor", "easing"],
        "potentialRegistryModules": [
            "registry/motion/presets.ts",
            "registry/motion/transformation-recipes.ts"],
        "notInferred": ["physical dolly", "true depth", "object growth"],
        "measurementKeys": ["endToStartBoxAreaRatio", "appearance"],
    },
    "screen-centers-closer": {
        "originalRecipe": "paired-convergence",
        "visualMechanic": "two independent assets move toward a shared visual focus",
        "stages": ["establish separate authored anchors",
                   "lead attention toward a shared focal zone",
                   "converge with independently controlled easing",
                   "hold enough space to preserve visual identities"],
        "controls": ["targetA", "targetB", "startFrame", "durationFrames",
                     "convergencePoint", "staggerFrames", "easing"],
        "potentialRegistryModules": [
            "registry/motion/shared-element.ts",
            "registry/motion/motion-director.ts"],
        "notInferred": ["contact", "conversation", "one actor pursuing another"],
        "measurementKeys": ["distanceChangeNormalized",
                            "startDistanceNormalized", "endDistanceNormalized"],
    },
    "screen-centers-farther": {
        "originalRecipe": "paired-divergence",
        "visualMechanic": "two assets separate to create a comparison composition",
        "stages": ["establish a shared initial composition",
                   "part assets into independent screen regions",
                   "reveal separately authored context around each",
                   "land on stable comparison framing"],
        "controls": ["targetA", "targetB", "startFrame", "durationFrames",
                     "leftAnchor", "rightAnchor", "easing"],
        "potentialRegistryModules": [
            "registry/motion/motion-director.ts",
            "registry/visual/comparison-stage-react.tsx"],
        "notInferred": ["physical separation", "emotional disagreement"],
        "measurementKeys": ["distanceChangeNormalized",
                            "startDistanceNormalized", "endDistanceNormalized"],
    },
    "screen-box-overlap-onset": {
        "originalRecipe": "layered-crossing-reveal",
        "visualMechanic": "two authored layers intersect and reveal a controlled mask",
        "stages": ["stage independent layers at different compositing depths",
                   "animate a controlled overlapping interval",
                   "reveal an original texture or graphic through an authored mask",
                   "resolve layers to an uncluttered hold"],
        "controls": ["targetA", "targetB", "startFrame", "durationFrames",
                     "layerOrder", "maskShape", "overlapHoldFrames"],
        "potentialRegistryModules": [
            "registry/motion/masks.ts",
            "registry/motion/shared-element.ts"],
        "notInferred": ["physical contact", "which object occluded another"],
        "measurementKeys": ["firstObservedOverlapFrameIndex", "endBoxIoU"],
    },
    "horizontal-image-order-reversal": {
        "originalRecipe": "two-lane-swap",
        "visualMechanic": "two designed elements exchange left/right screen positions",
        "stages": ["declare two clear screen lanes",
                   "offset curved paths to avoid a visual collision",
                   "swap horizontal image order",
                   "settle labels and establish a new reading order"],
        "controls": ["targetA", "targetB", "startFrame", "durationFrames",
                     "pathA", "pathB", "laneGap", "staggerFrames"],
        "potentialRegistryModules": [
            "registry/motion/two-lane-swap.ts",
            "registry/motion/two-lane-swap-react.tsx",
            "registry/motion/paths.ts",
            "registry/motion/motion-director.ts"],
        "notInferred": ["actor identity crossing", "physical collision", "3D depth"],
        "measurementKeys": ["firstAminusBCenterX", "lastAminusBCenterX"],
    },
    "shared-image-plane-displacement": {
        "originalRecipe": "shared-shift-with-optional-parallax",
        "visualMechanic": "an original ensemble translates in one coordinated shot",
        "stages": ["compose separate background and foreground layers",
                   "animate a shared authored translation",
                   "optionally offset decorative layers to create depth",
                   "end on a clean fixed composition"],
        "controls": ["targetIds", "startFrame", "durationFrames",
                     "sharedDelta", "layerParallaxFactors", "easing"],
        "potentialRegistryModules": [
            "registry/motion/motion-director.ts",
            "registry/motion/camera-stage.tsx"],
        "notInferred": ["physical camera movement", "same physical object",
                        "actual measured parallax"],
        "measurementKeys": ["aDeltaCenterNormalized", "bDeltaCenterNormalized"],
    },
}


def _bounded_measurements(source: dict[str, Any],
                          keys: list[str]) -> dict[str, Any]:
    if not isinstance(source, dict) or len(source) > 16:
        raise ValueError("motion recipe evidence lacks bounded measurements")
    # Validate the entire upstream source event, even fields not copied into
    # this animation idea. Otherwise NaN or fabricated nested values could
    # hide in unselected metrics and pass a seemingly source-verified report.
    for field, value in source.items():
        if type(field) is not str or not 1 <= len(field) <= 64:
            raise ValueError("invalid source metric name")
        if type(value) in (int, float):
            if not math.isfinite(value):
                raise ValueError("nonfinite source metric")
        elif value is None:
            if field != "straightnessProxy":
                raise ValueError("unsupported empty source metric")
        elif type(value) is str:
            if not 1 <= len(value) <= 120:
                raise ValueError("invalid source metric description")
        elif isinstance(value, list):
            if field == "possibleAlternatives":
                if (len(value) > 8 or any(
                        type(v) is not str or not 1 <= len(v) <= 120
                        for v in value)):
                    raise ValueError("invalid alternative explanation")
            elif (len(value) != 2 or any(
                    type(v) not in (int, float) or not math.isfinite(v)
                    for v in value)):
                raise ValueError("nonfinite or invalid source vector metric")
        else:
            raise ValueError("unsupported source metric value")
    if ("direction" in source and source["direction"] not in {
            "right-in-image", "left-in-image", "up-in-image",
            "down-in-image", "diagonal-in-image"}):
        raise ValueError("unsupported source direction evidence")
    if ("appearance" in source and source["appearance"] not in {
            "larger-in-image", "smaller-in-image"}):
        raise ValueError("unsupported source appearance evidence")
    picked = {}
    for key in keys:
        if key not in source:
            raise ValueError("motion recipe is missing a required measured field")
        value = source[key]
        if type(value) in (int, float):
            if not math.isfinite(value):
                raise ValueError("nonfinite source metric")
        elif isinstance(value, list):
            if (len(value) != 2
                    or any(type(v) not in (int, float) or not math.isfinite(v)
                           for v in value)):
                raise ValueError("invalid source vector metric")
        elif type(value) is str:
            if not 1 <= len(value) <= 48:
                raise ValueError("invalid source metric description")
        else:
            raise ValueError("unsupported source metric value")
        picked[key] = value
    return picked


def propose_motion_mechanics(
    temporal: dict[str, Any], *,
    max_candidates: int = 24, max_per_mechanic: int = 3,
) -> dict[str, Any]:
    """Return bounded, grounded *original design proposals* from screen boxes."""
    if (type(max_candidates) is not int or not 1 <= max_candidates <= 40
            or type(max_per_mechanic) is not int
            or not 1 <= max_per_mechanic <= 6):
        raise ValueError("motion mechanic proposal budgets invalid")
    if (not isinstance(temporal, dict)
            or temporal.get("schemaVersion") != _TEMPORAL
            or type(temporal.get("sourceSha256")) is not str
            or len(temporal["sourceSha256"]) != 64
            or any(c not in "0123456789abcdef"
                   for c in temporal["sourceSha256"])
            or type(temporal.get("frameCount")) is not int
            or not 1 <= temporal["frameCount"] <= 108000
            or not isinstance(temporal.get("events"), list)
            or len(temporal["events"]) > 200):
        raise ValueError("motion mechanic input has invalid source evidence")
    source_sha = temporal["sourceSha256"]
    measured_pairs = temporal.get("pairMetrics", [])
    if not isinstance(measured_pairs, list) or len(measured_pairs) > 28:
        raise ValueError("motion mechanic source pair evidence exceeds bounds")
    pair_signatures = set()
    for pair in measured_pairs:
        if (not isinstance(pair, dict)
                or pair.get("status") !=
                "pairwise-screen-measurement-not-physical-interaction"
                or type(pair.get("shotId")) is not str
                or type(pair.get("subjectA")) is not str
                or type(pair.get("subjectB")) is not str
                or pair["subjectA"] == pair["subjectB"]
                or type(pair.get("startFrameIndex")) is not int
                or type(pair.get("endFrameIndex")) is not int
                or not 0 <= pair["startFrameIndex"] <
                pair["endFrameIndex"] < temporal["frameCount"]
                or not isinstance(pair.get("identityProvenance"), list)
                or len(pair["identityProvenance"]) != 2
                or any(origin not in _ORIGINS
                       for origin in pair["identityProvenance"])):
            raise ValueError("motion mechanic pair identity evidence malformed")
        key = (
            pair["shotId"], pair["subjectA"], pair["subjectB"],
            pair["startFrameIndex"], pair["endFrameIndex"],
            tuple(pair["identityProvenance"]),
        )
        if key in pair_signatures:
            raise ValueError("duplicate pairwise screen evidence")
        pair_signatures.add(key)
    seen = set()
    counts: dict[str, int] = {}
    proposals = []
    for event in temporal["events"]:
        if not isinstance(event, dict):
            raise ValueError("motion mechanic event must be an object")
        name = event.get("eventType")
        if name not in _MECHANICS:
            raise ValueError("unsupported source screen-geometry event")
        spec = _MECHANICS[name]
        a, b = event.get("subjectA"), event.get("subjectB")
        start, end = event.get("startFrameIndex"), event.get("endFrameIndex")
        seconds_start, seconds_end = event.get("startSeconds"), event.get("endSeconds")
        identities = event.get("identityProvenance")
        if (event.get("status") != "measured-screen-geometry-not-semantic-action"
                or type(a) is not str or not 1 <= len(a) <= 48
                or (b is not None and (type(b) is not str
                                       or not 1 <= len(b) <= 48 or b == a))
                or (name.startswith("region-") != (b is None))
                or type(event.get("shotId")) is not str
                or not 1 <= len(event["shotId"]) <= 100
                or type(start) is not int or type(end) is not int
                or not 0 <= start < end < temporal["frameCount"]
                or type(seconds_start) not in (int, float)
                or type(seconds_end) not in (int, float)
                or not math.isfinite(seconds_start)
                or not math.isfinite(seconds_end)
                or seconds_end <= seconds_start
                or not isinstance(identities, list)
                or len(identities) != (1 if b is None else 2)
                or any(identity not in _ORIGINS for identity in identities)):
            raise ValueError("motion mechanic event identity, shot or time invalid")
        if b is not None and (
                event["shotId"], a, b, start, end,
                tuple(identities)) not in pair_signatures:
            raise ValueError("motion mechanic pair identity lacks matching measured pair")
        measurements = _bounded_measurements(
            event.get("measurements"), spec["measurementKeys"])
        signature = (name, event["shotId"], a, b, start, end)
        if signature in seen:
            raise ValueError("duplicate source event would double count a mechanic")
        seen.add(signature)
        counts[name] = counts.get(name, 0) + 1
        if (counts[name] > max_per_mechanic or
                len(proposals) >= max_candidates):
            continue
        digest = hashlib.sha256(json.dumps(
            [source_sha, *signature],
            separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()[:16]
        proposals.append({
            "id": "mechanic-idea-" + digest,
            "originalRecipe": spec["originalRecipe"],
            "animationMechanic": spec["visualMechanic"],
            "sourceEvidence": {
                "sourceSha256": source_sha,
                "shotId": event["shotId"],
                "frameRange": [start, end],
                "decodedTimeRangeSeconds": [seconds_start, seconds_end],
                "measuredEventType": name,
                "trackedRegionIds": [a] + ([b] if b is not None else []),
                "identityProvenance": identities,
                "screenGeometryMeasurements": measurements,
            },
            "originalChoreographyStages": spec["stages"],
            "authoringControlNames": spec["controls"],
            "candidateRegistryModuleFiles": spec["potentialRegistryModules"],
            "registryApiVerifiedForThisRecipe": False,
            # A tested, installable implementation exists only for the lane
            # swap. There is still no direct source-metrics-to-animation
            # adapter, so the per-recipe API mapping remains unverified.
            "availableOriginalImplementation": (
                {
                    **_SHIPPED_SWAP,
                    "modules": list(_SHIPPED_SWAP["modules"]),
                    "publicExports": list(_SHIPPED_SWAP["publicExports"]),
                }
                if name == "horizontal-image-order-reversal" else None
            ),
            "sourceDoesNotProve": spec["notInferred"],
            "requiresOriginalArtAssets": True,
            "status": "unreviewed-original-animation-mechanic-proposal",
            "reviewGates": [
                "Inspect the actual source frames before trusting this motion proxy.",
                "Author distinct visual assets, staging and timing; do not reproduce source frames.",
                "Inspect current kumiki-ui APIs and test an independently rendered preview.",
                "Validate readable text, intentional pacing and explicit cross-object layering.",
            ],
        })
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": source_sha,
        "frameCount": temporal["frameCount"],
        "uiRegistryFileAudit": {
            "repository": "YukiUmetsu/kumiki-ui",
            "commitSha": _UI_AUDIT_SHA,
            "meaning": "related primitive source files existed; API compatibility was not verified",
        },
        "measuredEventCount": len(temporal["events"]),
        "proposedMechanicCount": len(proposals),
        "proposals": proposals,
        "status": ("unreviewed-original-animation-ideas"
                   if proposals else "no-supported-geometry-for-new-recipe-ideas"),
        "limitations": [
            "All recipes are original creative design suggestions, never recovered source animation.",
            "Screen-region geometry does not prove contact, pose, intent or a real camera move.",
            "Related old primitives existed at the audit commit; source-metric API mapping remains unverified.",
            "A shipped two-lane-swap implementation is listed separately from all other research ideas.",
            "The system does not assume any component is missing from kumiki-ui.",
            "No executable animation specification, exact source keyframes, original artwork or video is emitted.",
            "Review generated visual work against high-quality references with independent assets.",
        ],
    }
