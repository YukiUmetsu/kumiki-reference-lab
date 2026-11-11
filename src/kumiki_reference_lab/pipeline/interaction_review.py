"""Source-PTS-verified two-character interaction QA and explicit human feedback.

Source image correctness does not certify a VLM's semantic interaction labels.
"""
from __future__ import annotations

import html
import json
import os
import tempfile
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames
from kumiki_reference_lab.backends.ffmpeg.source_seek import decode_verified_later_source_frames
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.character_vision_review import _load_json, _bound_proposals
from kumiki_reference_lab.pipeline.local_character_interactions import (
    SCHEMA_VERSION as INTERACTION_VERSION, _outline, _parse_response,
)
from kumiki_reference_lab.pipeline.ollama_character_perception import (
    SCHEMA_VERSION as VISION_VERSION,
)
from kumiki_reference_lab.pipeline.subject_detections import _iou
from kumiki_reference_lab.pipeline.subject_tracklet_review import _validate_report
from kumiki_reference_lab.reviews.character_scene import load_character_scene

QA_VERSION = "kumiki.local-interaction-qa.v1"
FEEDBACK_VERSION = "kumiki.local-interaction-feedback.v1"
METRICS_VERSION = "kumiki.local-interaction-review-metrics.v1"
_VERDICTS = frozenset({"pending", "supported", "unsupported", "unclear"})


def _check_inputs(
    tracklets: dict[str, Any], vision: dict[str, Any],
    base: dict[str, Any], interaction: dict[str, Any],
    output_scene: dict[str, Any], report_sha: str, base_sha: str,
) -> list[dict[str, Any]]:
    """Reject any source, clock, cast, action, or pair attribution inconsistency."""
    frames = _validate_report(tracklets)
    # Validate that the underlying character scene itself was constructed
    # from the exact tracklet boxes and corresponding VLM output, not just
    # an arbitrary compatible-looking source hash.
    _bound_proposals(tracklets, vision, base)
    source_sha = tracklets["sourceSha256"]
    timebase = tracklets["sourceTimebase"]
    stream = tracklets["sourceStreamIndex"]
    if (vision.get("schemaVersion") != VISION_VERSION or
            vision.get("trackletReportSha256") != report_sha or
            vision.get("sourceSha256") != source_sha or
            vision.get("sourceTimebase") != timebase or
            interaction.get("schemaVersion") != INTERACTION_VERSION or
            interaction.get("sourceSha256") != source_sha or
            interaction.get("trackletReportSha256") != report_sha or
            interaction.get("baseSceneSha256") != base_sha or
            interaction.get("modelDigestVerified") is not False):
        raise ValueError("interaction QA source or manifest provenance mismatch")
    for scene in (base, output_scene):
        if (scene["sourceSha256"] != source_sha or
                scene["sourceStreamIndex"] != stream or
                scene["sourceTimebase"] != timebase):
            raise ValueError("interaction QA source video clock/stream mismatch")
    for field in ("characters", "appearances", "utterances", "identityClaims", "window"):
        if output_scene[field] != base[field]:
            raise ValueError(f"interaction QA unexpectedly changed original {field}")
    existing = base["actions"]
    appended = output_scene["actions"][len(existing):]
    if output_scene["actions"][:len(existing)] != existing:
        raise ValueError("interaction QA modified previously analyzed actions")
    for key, a, b in (("renderWidth", 64, 320), ("renderHeight", 36, 180),
                      ("scanSeconds", 1, 120), ("maxPairGapSeconds", 1, 5)):
        value = interaction.get(key)
        if type(value) is not int or not a <= value <= b:
            raise ValueError(f"interaction QA requires valid source rendering parameter {key}")
    if interaction.get("pairOrdering") != "sorted-tracklet-ids-first-red-second-cyan":
        raise ValueError("interaction QA requires known red/cyan tracklet ordering")
    seek_start = interaction.get("seekStartSeconds")
    if seek_start is not None and (
            type(seek_start) is not int or seek_start < 0 or
            interaction["scanSeconds"] > 30 or
            seek_start+interaction["scanSeconds"] > 3600):
        raise ValueError("interaction QA cannot replay the declared later seek window")
    decisions = interaction.get("pairDecisions")
    if (not isinstance(decisions, list) or len(decisions) > 12 or
            type(interaction.get("candidatePairs")) is not int or
            interaction["candidatePairs"] != len(decisions) or
            type(interaction.get("actionProposals")) is not int or
            interaction["actionProposals"] != len(appended)):
        raise ValueError("interaction QA pair/action counts mismatch")
    roster = {x["id"] for x in base["characters"] if x["kind"] != "voice-only"}
    frame_by_pts = {row["sourcePts"]: (i, row) for i, row in enumerate(frames)}
    bound = []
    seen = set()
    matched_action_index = 0
    tb = Fraction(**timebase)
    cuts = tracklets["cutCandidatePts"]
    previous_pair_order = None
    for idx, row in enumerate(decisions):
        required = {"startPts", "endPts", "redId", "cyanId", "actorColor",
                    "interaction", "visualEvidence", "status"}
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError(f"interaction QA pair {idx} has malformed evidence")
        start, end, red, cyan = (
            row["startPts"], row["endPts"], row["redId"], row["cyanId"]
        )
        if (type(start) is not int or type(end) is not int or
                type(red) is not str or type(cyan) is not str or
                red >= cyan or red not in roster or cyan not in roster or
                start >= end or start not in frame_by_pts or end not in frame_by_pts):
            raise ValueError(f"interaction QA pair {idx} missing known character frames")
        prior_index, prior = frame_by_pts[start]
        next_index, later = frame_by_pts[end]
        if (next_index != prior_index + 1 or
                not base["window"]["startPts"] <= start < end < base["window"]["endPts"] or
                (end-start)*tb > interaction["maxPairGapSeconds"] or
                any(start < cut <= end for cut in cuts)):
            raise ValueError("interaction QA pair crosses cut, frame gap or source window")
        key = (start, end, red, cyan)
        if key in seen or (previous_pair_order is not None and key < previous_pair_order):
            raise ValueError("interaction QA pair duplicated or out of order")
        seen.add(key)
        previous_pair_order = key
        prior_boxes = {x["trackletId"]: x["box"] for x in prior["proposals"]}
        later_boxes = {x["trackletId"]: x["box"] for x in later["proposals"]}
        if not all(tid in prior_boxes and tid in later_boxes for tid in (red, cyan)):
            raise ValueError("interaction QA lacks source character bounding boxes")
        if max(
            _iou(tuple(prior_boxes[red]), tuple(prior_boxes[cyan])),
            _iou(tuple(later_boxes[red]), tuple(later_boxes[cyan])),
        ) > .65:
            raise ValueError("interaction QA has ambiguous overlapping character boxes")
        if row["status"] != "unreviewed-interaction-hypothesis":
            raise ValueError("interaction QA must not assume model approval")
        parsed = _parse_response({
            "actorColor": row["actorColor"], "interaction": row["interaction"],
            "visualEvidence": row["visualEvidence"],
        })
        if parsed["interaction"] != "none":
            if matched_action_index >= len(appended):
                raise ValueError("interaction QA action absent from character scene")
            action = appended[matched_action_index]
            matched_action_index += 1
            actor = red if parsed["actorColor"] == "red" else cyan
            target = cyan if parsed["actorColor"] == "red" else red
            if (action["actorId"] != actor or action["targetId"] != target or
                    action["action"] != parsed["interaction"] or
                    action["startPts"] != start or action["endPts"] != end+1 or
                    action["anchorPts"] != [start, end] or
                    action["confidence"] != "low" or
                    action["observation"] !=
                    "Unverified local VLM two-frame interaction: " + parsed["visualEvidence"]):
                raise ValueError("interaction QA directed action conflicts with original prediction")
        bound.append({
            **row, "previousRedBox": prior_boxes[red], "previousCyanBox": prior_boxes[cyan],
            "currentRedBox": later_boxes[red], "currentCyanBox": later_boxes[cyan],
        })
    if matched_action_index != len(appended):
        raise ValueError("interaction QA has extra character-scene actions")
    return bound


def _html_gallery(rows: list[dict[str, Any]], source_name: str) -> str:
    cards = []
    for i, row in enumerate(rows):
        action = row["interaction"]
        label = "No proposed interaction" if action == "none" else action
        cards.append(
            '<article><div class="images">'
            f'<img src="frames/pair-{i:03d}-before.png" '
            f'alt="Earlier source PTS {row["startPts"]} with red and cyan boxes">'
            f'<img src="frames/pair-{i:03d}-after.png" '
            f'alt="Later source PTS {row["endPts"]} with red and cyan boxes">'
            '</div><div class="details">'
            f'<h2>Pair {i+1}: {html.escape(row["redId"])} (red) / '
            f'{html.escape(row["cyanId"])} (cyan)</h2>'
            f'<p>Source PTS {row["startPts"]} to {row["endPts"]}</p>'
            f'<p><strong>Proposed action:</strong> {html.escape(label)}</p>'
            f'<p><strong>Proposed actor:</strong> {html.escape(row["actorColor"])}</p>'
            f'<p><strong>Claimed evidence:</strong> {html.escape(row["visualEvidence"])}</p>'
            '<p class="notice">Model hypothesis only. Verify direction, contact, '
            'camera motion and tracklet consistency against both frames.</p>'
            '</div></article>'
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Character interaction QA</title><style>'
        'body{background:#101827;color:#e9f1fc;font:15px system-ui;margin:0;padding:24px}'
        'main{max-width:1150px;margin:auto}article{background:#1b2940;border-radius:12px;'
        'border:1px solid #354760;margin:20px 0;overflow:hidden}'
        '.images{display:flex;gap:8px;padding:12px;align-items:center}'
        '.images img{width:calc(50% - 4px);object-fit:contain;background:#0c1220}'
        '.details{padding:0 16px 16px}p{line-height:1.55;color:#c8d6ee}'
        '.notice{color:#f7cc8d}@media(max-width:600px){.images{flex-wrap:wrap}'
        '.images img{width:100%}}</style></head><body><main>'
        '<h1>Two-character interaction review</h1>'
        f'<p>{html.escape(source_name)}: original PTS frames with the same '
        'red/cyan bounding boxes supplied to the local vision model. '
        'Semantics remain unreviewed until human verdicts are recorded.</p>'
        + ("".join(cards) if cards else
           "<p>No eligible pairwise observations. This does not prove a video lacks interactions.</p>")
        + '</main></body></html>\n'
    )


def build_interaction_review(
    source: Path, report_path: Path, vision_run: Path,
    interaction_run: Path, out: Path, *, ffprobe: str = "ffprobe",
    ffmpeg: str = "ffmpeg",
) -> Path:
    """Replay exact local model frames for manual inspection, without running inference."""
    if out.exists() or out.is_symlink():
        raise ValueError("interaction QA output directory must be new")
    source_files = (
        source, report_path, vision_run / "character-scene.json",
        vision_run / "character-vision.json", interaction_run / "character-scene.json",
        interaction_run / "character-interactions.json",
    )
    signatures = [file_signature(x) for x in source_files]
    tracklets = _json_file(report_path, limit=2_000_000)
    vision = _load_json(source_files[3], limit=262144)
    base = load_character_scene(source_files[2])
    merged = load_character_scene(source_files[4])
    interaction = _load_json(source_files[5], limit=262144)
    bound = _check_inputs(
        tracklets, vision, base, interaction, merged,
        sha256_file(report_path), sha256_file(source_files[2]),
    )
    metadata = inspect_source(source, ffprobe=ffprobe)
    if (metadata["source"]["sha256"] != tracklets["sourceSha256"] or
            metadata["video"]["streamIndex"] != tracklets["sourceStreamIndex"] or
            metadata["video"]["sourceTimebase"] != tracklets["sourceTimebase"]):
        raise ValueError("interaction QA local video does not match source evidence")
    pts = sorted({p for row in bound for p in (row["startPts"], row["endPts"])})
    frame_bytes = {}
    if pts:
        if interaction.get("seekStartSeconds") is not None:
            decoded = decode_verified_later_source_frames(
                source, tracklets["sourceStreamIndex"], pts,
                timebase=Fraction(**tracklets["sourceTimebase"]),
                start_seconds=interaction["seekStartSeconds"],
                seconds=interaction["scanSeconds"],
                width=interaction["renderWidth"], height=interaction["renderHeight"],
                ffprobe=ffprobe, ffmpeg=ffmpeg)
        else:
            records = read_frame_pts(
                source, tracklets["sourceStreamIndex"], seconds=interaction["scanSeconds"],
                ffprobe=ffprobe,
            )
            by_pts: dict[int, list[int]] = {}
            for record in records:
                if record.pts is not None:
                    by_pts.setdefault(record.pts, []).append(record.ordinal)
            ordinals = []
            for p in pts:
                choices = by_pts.get(p, [])
                if len(choices) != 1:
                    raise ValueError("interaction QA source frame PTS missing or ambiguous")
                ordinals.append(choices[0])
            if ordinals != sorted(set(ordinals)):
                raise ValueError("interaction QA original frame ordinals not chronological")
            decoded = read_rgb_frames(
                source, tracklets["sourceStreamIndex"], ordinals, pts,
                timebase=Fraction(**tracklets["sourceTimebase"]),
                seconds=interaction["scanSeconds"], width=interaction["renderWidth"],
                height=interaction["renderHeight"], ffmpeg=ffmpeg,
            )
        frame_bytes = dict(zip(pts, decoded, strict=True))
    for path, signature in zip(source_files, signatures, strict=True):
        require_unchanged(path, signature)
    manifest_hash = sha256_file(source_files[5])
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-interaction-review-", dir=out.parent) as folder:
        staging = Path(folder)
        (staging / "frames").mkdir()
        for i, row in enumerate(bound):
            w, h = interaction["renderWidth"], interaction["renderHeight"]
            for suffix, pts_key, red_key, cyan_key in (
                ("before", "startPts", "previousRedBox", "previousCyanBox"),
                ("after", "endPts", "currentRedBox", "currentCyanBox"),
            ):
                highlighted = _outline(
                    frame_bytes[row[pts_key]], w, h, row[red_key], row[cyan_key],
                )
                (staging / "frames" / f"pair-{i:03d}-{suffix}.png").write_bytes(highlighted)
        (staging / "index.html").write_text(
            _html_gallery(bound, metadata["source"]["fileName"]), encoding="utf-8")
        feedback = {
            "schemaVersion": FEEDBACK_VERSION,
            "sourceSha256": tracklets["sourceSha256"],
            "interactionManifestSha256": manifest_hash,
            "reviewer": {"kind": "human", "id": "unassigned"},
            "pairs": [
                {"index": i, "verdict": "pending", "notes": ""} for i in range(len(bound))
            ],
        }
        (staging / "interaction-feedback.json").write_text(
            json.dumps(feedback, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8")
        (staging / "review-manifest.json").write_text(
            json.dumps({
                "schemaVersion": QA_VERSION,
                "sourceSha256": tracklets["sourceSha256"],
                "interactionManifestSha256": manifest_hash,
                "reviewStatus": "pending-human-review",
                "pairCount": len(bound),
                "sourceFrameEvidence": "original-pts-verified-actual-media-frames",
                "semanticValidity": "not-independently-verified",
            }, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        for path, signature in zip(source_files, signatures, strict=True):
            require_unchanged(path, signature)
        if out.exists() or out.is_symlink():
            raise ValueError("interaction QA output path was occupied during processing")
        os.replace(staging, out)
    return out / "index.html"


def summarize_interaction_feedback(feedback_path: Path,
                                   interaction_manifest_path: Path) -> dict[str, Any]:
    """Compute reviewed-only support rates for predictions and abstentions separately."""
    feedback = _load_json(feedback_path, limit=131072)
    manifest = _load_json(interaction_manifest_path, limit=262144)
    decisions = manifest.get("pairDecisions")
    if (feedback.get("schemaVersion") != FEEDBACK_VERSION or
            manifest.get("schemaVersion") != INTERACTION_VERSION or
            feedback.get("sourceSha256") != manifest.get("sourceSha256") or
            feedback.get("interactionManifestSha256") != sha256_file(interaction_manifest_path) or
            not isinstance(decisions, list) or len(decisions) > 12):
        raise ValueError("interaction feedback source/manifest does not match")
    reviewer = feedback.get("reviewer")
    if (not isinstance(reviewer, dict) or set(reviewer) != {"kind", "id"} or
            reviewer.get("kind") != "human" or
            type(reviewer.get("id")) is not str or
            not 2 <= len(reviewer["id"].strip()) <= 100):
        raise ValueError("interaction feedback reviewer requires human ID")
    rows = feedback.get("pairs")
    if not isinstance(rows, list) or len(rows) != len(decisions):
        raise ValueError("interaction feedback row count mismatch")
    bucket = {"predicted-interaction": Counter(), "abstention": Counter()}
    by_label: dict[str, Counter] = {}
    for i, (row, decision) in enumerate(zip(rows, decisions, strict=True)):
        if (not isinstance(row, dict) or set(row) != {"index", "verdict", "notes"} or
                type(row["index"]) is not int or row["index"] != i or
                type(row["verdict"]) is not str or row["verdict"] not in _VERDICTS or
                type(row["notes"]) is not str or len(row["notes"]) > 500):
            raise ValueError("interaction feedback verdict invalid")
        parsed = _parse_response({
            "actorColor": decision.get("actorColor"),
            "interaction": decision.get("interaction"),
            "visualEvidence": decision.get("visualEvidence"),
        })
        label = parsed["interaction"]
        kind = "abstention" if label == "none" else "predicted-interaction"
        bucket[kind][row["verdict"]] += 1
        by_label.setdefault(label, Counter())[row["verdict"]] += 1
    any_reviewed = any(
        sum(count[x] for x in ("supported", "unsupported", "unclear")) > 0
        for count in bucket.values()
    )
    if reviewer["id"].strip() == "unassigned" and any_reviewed:
        raise ValueError("assign a reviewer before recording semantic verdicts")
    def rate(counter: Counter) -> float | None:
        decided = counter["supported"] + counter["unsupported"]
        return round(counter["supported"]/decided, 6) if decided else None
    def reviewed(counter: Counter) -> int:
        return sum(counter[x] for x in ("supported", "unsupported", "unclear"))
    return {
        "schemaVersion": METRICS_VERSION,
        "sourceSha256": manifest["sourceSha256"],
        "interactionManifestSha256": feedback["interactionManifestSha256"],
        "reviewer": reviewer,
        "pairCount": len(decisions),
        "proposedInteractionCount": sum(x["interaction"] != "none" for x in decisions),
        "abstentionCount": sum(x["interaction"] == "none" for x in decisions),
        "reviewedInteractionCount": reviewed(bucket["predicted-interaction"]),
        "reviewedAbstentionCount": reviewed(bucket["abstention"]),
        "positiveProposalSupportRate": rate(bucket["predicted-interaction"]),
        "abstentionSupportRate": rate(bucket["abstention"]),
        "byActionLabel": [
            {"action": label, "verdicts": dict(sorted(count.items())),
             "decidedSupportRate": rate(count)}
            for label, count in sorted(by_label.items())
        ],
        "hasAnyHumanReview": any_reviewed,
        "methodLimits": [
            "Only manually adjudicated supported/unsupported verdicts contribute to support rates.",
            "Pending/unclear examples are not counted as success or failure.",
            "This is not a population accuracy estimate or ground truth; it cannot measure missed actions elsewhere in the film.",
            "A supported abstention means no interaction was visible in this sampled pair, not that a film has no interaction.",
        ],
    }
