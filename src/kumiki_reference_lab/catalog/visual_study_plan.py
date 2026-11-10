"""Auditable selection of contrasting recent uploads for future visual coding.

Only original source-table rows are known here. There are no YouTube IDs,
decoded frames, style labels, camera labels, or causal outcome estimates.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from kumiki_reference_lab.catalog.audience_benchmarks import validate_audience_benchmarks


SCHEMA_VERSION = "kumiki.visual-study-plan.v1"
_DURATION_GROUPS = (
    ("under-1-minute", 1, 60),
    ("1-to-3-minutes", 60, 180),
    ("3-to-10-minutes", 180, 600),
    ("10-to-30-minutes", 600, 1800),
    ("30-to-60-minutes", 1800, 3601),
)


def _fingerprint(channel_id: str, snapshot: str, ordinal: int,
                 row: dict[str, Any]) -> str:
    """Hash the *table row and position*, not an asserted video identity."""
    blob = json.dumps({"channelId": channel_id, "snapshot": snapshot,
                       "rowIndex": ordinal, "row": row},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _duration_band(seconds: int) -> str:
    for name, start, end in _DURATION_GROUPS:
        if start <= seconds < end:
            return name
    raise ValueError("study duration must fit a declared group")


def _row_summary(channel: dict[str, Any], index: int,
                 identity_lookup: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    row = channel["videos"][index]
    snapshot = channel["sourceLastUpdatedOn"]
    candidate = identity_lookup.get((channel["id"], index))
    return {
        "rowIndex": index,
        "sourceRowSha256": _fingerprint(channel["id"], snapshot, index, row),
        "title": row["title"], "publishedOn": row["publishedOn"],
        "durationSeconds": row["durationSeconds"], "views": row["views"],
        "sourceUrl": channel["sourceUrl"],
        "videoIdentityStatus": ("index-corroborated-watch-page-not-opened" if candidate
                                else "unresolved-no-youtube-id-in-source"),
        "videoIdentityCandidate": ({"youtubeId": candidate["youtubeId"],
                                    "videoUrl": candidate["videoUrl"],
                                    "indexedOn": candidate["indexedOn"]}
                                   if candidate else None),
        "visualReviewStatus": "not-performed",
    }


def build_visual_study_plan(data: dict[str, Any], *, pairs_per_channel: int = 3,
                            max_age_gap_days: int = 45,
                            max_duration_ratio: float = 1.75,
                            min_view_ratio: float = 2.0,
                            identity_candidates: dict[str, Any] | None = None) -> dict[str, Any]:
    """Prioritize diverse comparable runtimes and publish-date proximity.

    The algorithm *selects on outcome contrast*, intentionally, for manual
    research follow-up. It is not a balanced representative statistical sample.
    The pair is only a lead until both original YouTube video IDs are verified.
    """
    validate_audience_benchmarks(data)
    if type(pairs_per_channel) is not int or not 1 <= pairs_per_channel <= 10:
        raise ValueError("pairs per channel must be between 1 and 10")
    if type(max_age_gap_days) is not int or not 0 <= max_age_gap_days <= 365:
        raise ValueError("maximum source-age gap must be 0..365 days")
    if (type(max_duration_ratio) not in (float, int) or
            not 1 <= max_duration_ratio <= 5 or not math.isfinite(max_duration_ratio)):
        raise ValueError("maximum runtime ratio must be a finite number between 1 and 5")
    if (type(min_view_ratio) not in (float, int) or
            not 1 < min_view_ratio <= 100 or not math.isfinite(min_view_ratio)):
        raise ValueError("minimum view-count ratio must be a finite number above 1 and at most 100")
    identity_lookup: dict[tuple[str, int], dict[str, Any]] = {}
    if identity_candidates is not None:
        # Lazy import avoids a cycle: the ID validator recomputes source-row hashes.
        from kumiki_reference_lab.catalog.video_id_candidates import validate_video_id_candidates
        validate_video_id_candidates(identity_candidates, data)
        identity_lookup = {(entry["channelId"], entry["rowIndex"]):
                           {**entry, "indexedOn": identity_candidates["indexedOn"]}
                           for entry in identity_candidates["entries"]}

    channel_plans = []
    for channel in data["channels"]:
        rows = channel["videos"]
        grouped_titles: dict[tuple[str, str], list[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            grouped_titles[(row["title"].strip().casefold(), row["publishedOn"])].append(index)
        collisions = [indices for indices in grouped_titles.values() if len(indices) > 1]
        uncertain_indexes = {index for collision in collisions for index in collision}
        duplicate_groups = [{"rowIndices": list(indices),
                             "sharedTitle": rows[indices[0]]["title"],
                             "publishedOn": rows[indices[0]]["publishedOn"],
                             "reason": "same-channel-title-date-not-safe-to-identify-by-title"}
                            for indices in sorted(collisions, key=lambda items: items[0])]

        skipped = Counter()
        candidates_by_band: dict[str, list[tuple[tuple, dict[str, Any]]]] = defaultdict(list)
        eligible: list[tuple[int, dict[str, Any], int, str]] = []
        snapshot = date.fromisoformat(channel["sourceLastUpdatedOn"])
        for index, row in enumerate(rows):
            runtime = row["durationSeconds"]
            if index in uncertain_indexes:
                skipped["ambiguous-title-date"] += 1
                continue
            if runtime is None:
                skipped["unknown-runtime"] += 1
                continue
            if runtime > 3600:
                skipped["over-60-minutes"] += 1
                continue
            age_days = (snapshot - date.fromisoformat(row["publishedOn"])).days
            eligible.append((index, row, age_days, _duration_band(runtime)))

        for left in range(len(eligible)):
            li, a, a_age, a_band = eligible[left]
            for right in range(left + 1, len(eligible)):
                ri, b, b_age, b_band = eligible[right]
                if a_band != b_band or abs(a_age - b_age) > max_age_gap_days:
                    continue
                ratio_duration = max(a["durationSeconds"], b["durationSeconds"]) / min(
                    a["durationSeconds"], b["durationSeconds"])
                if ratio_duration > max_duration_ratio:
                    continue
                higher_index, lower_index = (li, ri) if a["views"] >= b["views"] else (ri, li)
                higher, lower = rows[higher_index], rows[lower_index]
                view_ratio = higher["views"] / lower["views"]
                if view_ratio < min_view_ratio:
                    continue
                age_gap = abs(a_age - b_age)
                # Prefer more comparable pairs before selecting stronger outcome contrast.
                ranking = (age_gap, round(ratio_duration, 8), -view_ratio,
                           min(li, ri), max(li, ri))
                pair = {
                    "id": f"{channel['id']}-{higher_index:02d}-{lower_index:02d}",
                    "durationBand": a_band,
                    "sourceAgeGapDays": age_gap,
                    "durationRatio": round(ratio_duration, 4),
                    "reportedViewsRatio": round(view_ratio, 4),
                    "higherViewedRow": _row_summary(channel, higher_index, identity_lookup),
                    "lowerViewedRow": _row_summary(channel, lower_index, identity_lookup),
                    "relationship": "same-channel-source-age-and-runtime-contrast-lead-not-verified-video-pair",
                }
                candidates_by_band[a_band].append((ranking, pair))

        for pairs in candidates_by_band.values():
            pairs.sort(key=lambda item: item[0])
        # Round-robin duration families prevents a short-form-heavy channel from
        # monopolizing the selected queue with nearly identical runtimes.
        used: set[int] = set()
        chosen: list[dict[str, Any]] = []
        band_order = [band for band, *_ in _DURATION_GROUPS]
        while len(chosen) < pairs_per_channel:
            progress = False
            for band in band_order:
                if len(chosen) >= pairs_per_channel:
                    break
                for _, pair in candidates_by_band[band]:
                    a = pair["higherViewedRow"]["rowIndex"]
                    b = pair["lowerViewedRow"]["rowIndex"]
                    if a not in used and b not in used:
                        chosen.append(pair)
                        used.update((a, b))
                        progress = True
                        break
            if not progress:
                break

        channel_plans.append({
            "channelId": channel["id"], "channelName": channel["name"],
            "sourceUrl": channel["sourceUrl"],
            "sourceLastUpdatedOn": channel["sourceLastUpdatedOn"],
            "sourceRowCount": len(rows), "eligibleRowCount": len(eligible),
            "excludedRowCounts": dict(sorted(skipped.items())),
            "ambiguousIdentityGroups": duplicate_groups,
            "qualifyingCandidatePairCount": sum(len(pairs) for pairs in candidates_by_band.values()),
            "selectedPairs": chosen,
        })

    selected_identity_count = sum(
        row["videoIdentityCandidate"] is not None
        for channel in channel_plans for pair in channel["selectedPairs"]
        for row in (pair["higherViewedRow"], pair["lowerViewedRow"]))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "inputSchemaVersion": data["schemaVersion"],
        "retrievedOn": data["retrievedOn"],
        "selection": {
            "pairsPerChannel": pairs_per_channel,
            "maxSourceAgeGapDays": max_age_gap_days,
            "maxRuntimeRatio": float(max_duration_ratio),
            "minReportedViewsRatio": float(min_view_ratio),
            "maximumEligibleRuntimeSeconds": 3600,
            "basis": "within-channel-matched-source-age-and-runtime-outcome-contrast-not-random",
        },
        "sourceRowCount": sum(plan["sourceRowCount"] for plan in channel_plans),
        "eligibleRowCount": sum(plan["eligibleRowCount"] for plan in channel_plans),
        "selectedPairCount": sum(len(plan["selectedPairs"]) for plan in channel_plans),
        "selectedRowsWithIndexedIdCandidates": selected_identity_count,
        "channels": channel_plans,
        "evidenceStatus": "candidate-row-comparisons-no-verified-video-ids-no-frame-review",
        "nextCollectionSteps": [
            "Resolve both exact YouTube video IDs from independent creator/channel evidence; never infer identity from title alone.",
            "Obtain permission for local analysis where needed and record source media hashes and original PTS.",
            "Review both films using identical style, camera, lighting, edit, sound and narrative annotation instructions.",
            "After independent coding, compare within controlled cohorts and report uncertainty, confounders and sample sizes.",
        ],
        "warnings": [
            "The 300 snapshot entries are rows, not verified distinct video IDs; duplicate title/date groups are excluded.",
            "Selection intentionally conditions on a view-count contrast and therefore cannot estimate prevalence or causal effects.",
            "Channel, source-age and runtime matching does not control topics, promotion, Shorts distribution, impressions or recommendation exposure.",
            "Different channels and snapshot dates must not be pooled as if they share one exposure denominator.",
            "Camera, lighting and style remain unreviewed for every selected source row until separately linked visual evidence exists.",
        ],
    }
