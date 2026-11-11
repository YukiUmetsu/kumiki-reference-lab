"""Evidence-first, dependency-free timing analysis for operator-seeded ROI tracks.

Derives progress and simple curve-fit candidates from consecutively observed
screen-space boxes. Does NOT infer original animation keys, physical dynamics,
character identity, missing frames or a production tool's easing parameters.
"""
from __future__ import annotations

import math
import statistics
from typing import Any

SCHEMA_VERSION = "kumiki.screen-motion-timing.v1"
_ALLOWED_STATUS = {
    "operator-provided-seed", "auto-proposed-region",
    "tracked-screen-region-candidate",
}


def _finite(value: Any, field: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"timing {field} must be a finite number")
    return float(value)


def _curves(t: float) -> dict[str, float]:
    return {
        "linear": t,
        "ease-in-quadratic": t * t,
        "ease-out-quadratic": 1.0 - (1.0 - t) ** 2,
        "ease-in-out-smoothstep": 3.0 * t * t - 2.0 * t ** 3,
    }


def _samples(observations: Any) -> list[dict[str, Any]]:
    if not isinstance(observations, list) or not 1 <= len(observations) <= 900:
        raise ValueError("timing track must have 1..900 bounded observations")
    validated: list[dict[str, Any]] = []
    for i, row in enumerate(observations):
        if not isinstance(row, dict) or row.get("status") not in _ALLOWED_STATUS:
            raise ValueError("timing requires operator-seeded image observations")
        index = row.get("frameIndex")
        if type(index) is not int or index < 0:
            raise ValueError("timing observed frame index invalid")
        seconds = _finite(row.get("decodedSeconds"), "decodedSeconds")
        box = row.get("boxNormalized")
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError("timing requires a normalized track box")
        x, y, w, h = [_finite(v, "boxNormalized") for v in box]
        if (x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1.00001
                or y + h > 1.00001):
            raise ValueError("timing bounding box outside the image")
        rotation = _finite(row.get("screenRotationDegreesFromSeed"), "rotation")
        scale = _finite(row.get("screenScaleRatioFromSeed"), "scale")
        if scale <= 0 or scale > 100:
            raise ValueError("invalid tracked scale")
        if i == 0 and row["status"] not in (
                "operator-provided-seed", "auto-proposed-region"):
            raise ValueError("timing first observation must be a stated seed")
        if i:
            previous = validated[-1]
            if index != previous["index"] + 1 or seconds <= previous["seconds"]:
                raise ValueError("timing does not fill missing or unordered frames")
            if row["status"] != "tracked-screen-region-candidate":
                raise ValueError("only the first timing observation may be a seed")
            if (type(row.get("supportFeatureCount")) is not int
                    or row["supportFeatureCount"] < 4
                    or not .6 <= _finite(row.get("inlierFraction"), "inlierFraction") <= 1):
                raise ValueError("timing observation lacks supported local tracking")
        validated.append({
            "index": index, "seconds": seconds, "center": (x + w / 2, y + h / 2),
            "box": [x, y, w, h], "rotation": rotation, "scale": scale,
            "support": row.get("supportFeatureCount"),
        })
    return validated


def _keyframe_samples(samples: list[dict[str, Any]], progress: list[float],
                      *, cap: int = 24) -> list[dict[str, Any]]:
    if len(samples) <= cap:
        pick = list(range(len(samples)))
    else:
        pick = sorted({round(i * (len(samples) - 1) / (cap - 1))
                       for i in range(cap)})
    start_t = samples[0]["seconds"]
    duration = samples[-1]["seconds"] - start_t
    return [{
        "frameIndex": samples[i]["index"],
        "decodedSeconds": round(samples[i]["seconds"], 6),
        "normalizedTime": round((samples[i]["seconds"] - start_t) / duration, 5),
        "boxNormalized": [round(x, 5) for x in samples[i]["box"]],
        "screenRotationDegreesFromSeed": round(samples[i]["rotation"], 4),
        "screenScaleRatioFromSeed": round(samples[i]["scale"], 5),
        "projectedProgress": round(progress[i], 5),
    } for i in pick]


def _abstain(track: dict[str, Any], reason: str, *, valid_count: int) -> dict[str, Any]:
    return {
        "subjectId": track["id"], "shotId": track["shotId"],
        "kind": track["kind"], "identityProvenance": track["identityProvenance"],
        "status": reason, "observedFrameCount": valid_count,
        "easingCandidate": None, "keyframeSamples": [],
        "interpretation": "insufficient-evidence-for-timing-curve",
    }


def analyze_seeded_track(track: dict[str, Any], *,
                         min_observations: int = 8,
                         min_net_displacement: float = .025,
                         min_straightness: float = .85) -> dict[str, Any]:
    """Extract observed screen-space timing and optional simple easing candidate.

    The curve is a model fit to measured BOX CENTER progression, not recovered
    original keyframes. A track that reverses, jumps or leaves gaps abstains.
    """
    if (type(min_observations) is not int or not 6 <= min_observations <= 50
            or type(min_net_displacement) not in (float, int)
            or not .001 <= min_net_displacement <= .5
            or type(min_straightness) not in (float, int)
            or not .5 <= min_straightness <= 1):
        raise ValueError("invalid timing inference budgets")
    if (not isinstance(track, dict)
            or type(track.get("id")) is not str or not track["id"]
            or type(track.get("shotId")) is not str or not track["shotId"]
            or track.get("kind") not in (
                "animated-character", "person", "product", "text", "prop", "other")
            or track.get("identityProvenance") not in (
                "operator-seeded-not-model-recognized",
                "auto-motion-proposal-not-semantic-identity")):
        raise ValueError("timing input has invalid track identity or provenance")
    observations = _samples(track.get("observations"))
    auto = track["identityProvenance"] == "auto-motion-proposal-not-semantic-identity"
    if (observations[0]["index"] != track.get("startFrameIndex")
            or (auto and track["observations"][0]["status"] != "auto-proposed-region")
            or (not auto and track["observations"][0]["status"] != "operator-provided-seed")):
        raise ValueError("timing seed provenance and first frame disagree")
    if len(observations) < min_observations:
        return _abstain(track, "abstain-too-few-supported-observations",
                        valid_count=len(observations))
    t0 = observations[0]["seconds"]
    duration = observations[-1]["seconds"] - t0
    if duration < .15:
        return _abstain(track, "abstain-insufficient-observed-duration",
                        valid_count=len(observations))
    xy = [o["center"] for o in observations]
    direction = (xy[-1][0] - xy[0][0], xy[-1][1] - xy[0][1])
    net = math.hypot(*direction)
    if net < min_net_displacement:
        return _abstain(track, "abstain-insufficient-net-translation",
                        valid_count=len(observations))
    steps = [math.dist(a, b) for a, b in zip(xy, xy[1:])]
    path = sum(steps)
    if path <= 0 or net / path < min_straightness:
        return _abstain(track, "abstain-curved-reversing-or-unstable-path",
                        valid_count=len(observations))
    intervals = [
        b["seconds"] - a["seconds"]
        for a, b in zip(observations, observations[1:])
    ]
    median_interval = statistics.median(intervals)
    if max(intervals) > max(.25, median_interval * 2.5):
        return _abstain(track, "abstain-uneven-sampling",
                        valid_count=len(observations))
    if (max(steps) > max(.16, 5 * statistics.median(steps) + .035)):
        return _abstain(track, "abstain-large-screen-position-jump",
                        valid_count=len(observations))
    # Signed scalar projection onto the observed start/end direction; preserves
    # time-varying movement rather than interpolating original animation keys.
    progress = [
        ((p[0] - xy[0][0]) * direction[0]
         + (p[1] - xy[0][1]) * direction[1]) / net ** 2 for p in xy
    ]
    increments = [b - a for a, b in zip(progress, progress[1:])]
    if (min(increments) < -.035 or min(progress) < -.055
            or max(progress) > 1.055):
        return _abstain(track, "abstain-nonmonotonic-or-overshooting-progress",
                        valid_count=len(observations))
    ts = [(o["seconds"] - t0) / duration for o in observations]
    fit = sorted((
        (math.sqrt(sum((p - values[name]) ** 2
                       for p, values in zip(progress, map(_curves, ts))) / len(ts)),
         name)
        for name in _curves(0.5)
    ))
    best_error, best_name = fit[0]
    next_error = fit[1][0]
    supported = best_error <= .07 and next_error - best_error >= .012
    candidate: dict[str, Any] | None = ({
        "family": best_name,
        "normalizedRootMeanSquareError": round(best_error, 5),
        "nextBestError": round(next_error, 5),
        "status": "simple-progress-curve-fit-not-original-easing",
    } if supported else None)
    speeds = [step / dt for step, dt in zip(steps, intervals)]
    def hold_fraction(*, beginning: bool) -> float:
        if beginning:
            hit = next((i for i, p in enumerate(progress) if p > .05),
                       len(progress) - 1)
            return (observations[hit]["seconds"] - t0) / duration
        hit = next((i for i in range(len(progress) - 1, -1, -1)
                    if progress[i] < .95), 0)
        return (observations[-1]["seconds"] - observations[hit]["seconds"]) / duration

    return {
        "subjectId": track["id"], "shotId": track["shotId"],
        "kind": track["kind"],
        "identityProvenance": track["identityProvenance"],
        "status": ("timing-shape-candidate-unverified-auto-region" if supported and auto
                   else "timing-shape-candidate" if supported
                   else "measured-progress-easing-ambiguous"),
        "observedFrameCount": len(observations),
        "startFrameIndex": observations[0]["index"],
        "endFrameIndex": observations[-1]["index"],
        "startSeconds": round(t0, 6),
        "endSeconds": round(observations[-1]["seconds"], 6),
        "durationSeconds": round(duration, 6),
        "screenSpace": {
            "startCenterNormalized": [round(v, 5) for v in xy[0]],
            "endCenterNormalized": [round(v, 5) for v in xy[-1]],
            "netTranslationNormalized": [round(v, 5) for v in direction],
            "netDistanceNormalized": round(net, 5),
            "observedPathDistanceNormalized": round(path, 5),
            "straightness": round(net / path, 5),
            "peakSpeedNormalizedUnitsPerSecond": round(max(speeds), 5),
            "medianSpeedNormalizedUnitsPerSecond": round(statistics.median(speeds), 5),
            "startHoldFractionProxy": round(hold_fraction(beginning=True), 5),
            "endHoldFractionProxy": round(hold_fraction(beginning=False), 5),
            "rotationChangeDegreesFromSeed": round(
                observations[-1]["rotation"] - observations[0]["rotation"], 4),
            "scaleRatioChangeFromSeed": round(
                observations[-1]["scale"] / observations[0]["scale"], 5),
        },
        "easingCandidate": candidate,
        "curveAlternatives": [
            {"family": name, "normalizedRootMeanSquareError": round(rmse, 5)}
            for rmse, name in fit
        ],
        "keyframeSamples": _keyframe_samples(observations, progress),
        "interpretation": (
            "sampled-screen-box-progress-not-original-keyframes-or-camera-trajectory"
        ),
    }


def build_seeded_motion_timing(
    seeded_tracks: dict[str, Any], *, min_observations: int = 8,
    max_tracks: int = 8, numeric: dict[str, Any] | None = None,
    shot_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert existing ROI track observations to bounded timing proposals."""
    if type(max_tracks) is not int or not 1 <= max_tracks <= 8:
        raise ValueError("timing track budget must be 1..8")
    if not isinstance(seeded_tracks, dict):
        raise ValueError("timing needs seeded ROI tracking evidence")
    status = seeded_tracks.get("status")
    source_sha = seeded_tracks.get("sourceSha256")
    if status in ("not-requested", "not-run-install-pip-extra-dense"):
        # No ROI evidence must not erase source identity. The rest of the
        # cinematic report remains source-hashed, including abstention states.
        if numeric is not None:
            supplied_sha = numeric.get("sourceSha256")
            if (type(supplied_sha) is not str or len(supplied_sha) != 64 or
                    (source_sha is not None and source_sha != supplied_sha)):
                raise ValueError("unmeasured timing/source identity mismatch")
            source_sha = supplied_sha
        return {
            "schemaVersion": SCHEMA_VERSION,
            "status": "not-measured-no-supported-seeded-tracks",
            "sourceSha256": source_sha,
            "trackCount": 0, "supportedCurveCount": 0,
            "tracks": [], "limits": _limitations(),
        }
    if (status not in ("seeded-2d-region-motion-candidates",
                       "auto-seeded-2d-region-motion-candidates")
            or type(source_sha) is not str or len(source_sha) != 64
            or any(c not in "0123456789abcdef" for c in source_sha)):
        raise ValueError("unsupported timing track source or provenance")
    tracks = seeded_tracks.get("tracks")
    if not isinstance(tracks, list) or len(tracks) > max_tracks:
        raise ValueError("timing tracks exceed maximum budget")
    frames = None
    if numeric is not None:
        if (not isinstance(numeric, dict)
                or numeric.get("sourceSha256") != source_sha
                or not isinstance(numeric.get("frames"), list)
                or numeric.get("frameCount") != len(numeric["frames"])):
            raise ValueError("timing source-hash or frame evidence mismatch")
        frames = numeric["frames"]
    shots = None
    if shot_plan is not None:
        if (not isinstance(shot_plan, dict)
                or shot_plan.get("sourceSha256") != source_sha
                or not isinstance(shot_plan.get("shots"), list)):
            raise ValueError("timing shot plan and seed source mismatch")
        shots = {s["shotId"]: s for s in shot_plan["shots"]}
    seen: set[str] = set()
    results = []
    for track in tracks:
        if not isinstance(track, dict) or track.get("id") in seen:
            raise ValueError("duplicate or invalid seed track")
        seen.add(track.get("id"))
        observations = track.get("observations")
        if not isinstance(observations, list):
            raise ValueError("timing track has no observations")
        if shots is not None:
            shot = shots.get(track.get("shotId"))
            if shot is None or any(
                    not shot["startFrameIndex"] <= row.get("frameIndex", -1) <
                    shot["endFrameIndexExclusive"] for row in observations):
                raise ValueError("timing track crosses or lacks its source shot")
        if frames is not None:
            for row in observations:
                index = row.get("frameIndex")
                if (type(index) is not int or not 0 <= index < len(frames)
                        or frames[index]["frameIndex"] != index
                        or abs(_finite(row.get("decodedSeconds"), "sample time")
                               - _finite(frames[index].get("decodedSeconds"),
                                         "source frame time")) > 0.00001):
                    raise ValueError("timing seed observation/source time mismatch")
        results.append(analyze_seeded_track(
            track, min_observations=min_observations))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": source_sha,
        "status": ("screen-space-timing-proxies" if results else
                   "no-tracks-available"),
        "trackCount": len(results),
        "supportedCurveCount": sum(
            t["easingCandidate"] is not None for t in results),
        "tracks": results, "limits": _limitations(),
    }


def _limitations() -> list[str]:
    return [
        "Easing families are fits to observed ROI box centers, NOT original easing settings.",
        "Does not reconstruct character poses, joint motion, text glyph animation or deformation.",
        "Only shot-local contiguous feature-supported tracks qualify; automatic seeds remain unclassified proposals.",
        "Scale and rotation are screen-space affine proxies, not depth or physical rotation.",
        "Held progress may be caused by tracking jitter or subject/image composition.",
        "Abstains on unsupported, short, reversing, outlying or discontinuous trajectories.",
        "No model inference or frame interpretation is involved.",
    ]



def propose_original_timing_recipes(
    timing: dict[str, Any], *, max_recipes: int = 8,
) -> list[dict[str, Any]]:
    """Reusable timing *families* without copying observed paths or assets.

    These are non-executable neutral starting points for user-created Kumiki
    components. No claim about the true source animation curve is made.
    """
    if type(max_recipes) is not int or not 1 <= max_recipes <= 8:
        raise ValueError("timing recipe count must be bounded")
    if timing.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("timing recipe source version invalid")
    recipes = []
    for track in timing.get("tracks", []):
        candidate = track.get("easingCandidate")
        if not isinstance(candidate, dict):
            continue
        recipes.append({
            "purpose": "original-animation-timing-inspiration",
            "sourceSubjectSeedId": track["subjectId"],
            "sourceShotId": track["shotId"],
            "sourceSha256": timing["sourceSha256"],
            "identityProvenance": track["identityProvenance"],
            "timingFamilyHypothesis": candidate["family"],
            "sourceDurationSecondsObserved": track["durationSeconds"],
            "targetDurationSeconds": None,
            "targetStartPosition": None,
            "targetEndPosition": None,
            "targetComponentApiVerified": False,
            "originalArtworkRequired": True,
            "reviewStatus": "non-executable-unverified-timing-proposal",
        })
        if len(recipes) >= max_recipes:
            break
    return recipes
