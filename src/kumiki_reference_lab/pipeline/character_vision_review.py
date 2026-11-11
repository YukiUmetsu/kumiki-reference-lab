"""Source-verified offline QA gallery and human feedback for local VLM proposals.

Reviews are never auto-approved: screenshot provenance and semantic correctness
are separate claims.
"""
from __future__ import annotations

import html
import json
import os
import re
import tempfile
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.ollama_character_perception import (
    SCHEMA_VERSION as LOCAL_VISION_VERSION, _crop_rgb,
)
from kumiki_reference_lab.pipeline.subject_tracklet_review import _validate_report
from kumiki_reference_lab.reviews.character_scene import load_character_scene

REVIEW_VERSION = "kumiki.character-vision-qa.v1"
FEEDBACK_VERSION = "kumiki.character-vision-feedback.v1"
_METRICS_VERSION = "kumiki.character-vision-feedback-report.v1"
_VERDICTS = frozenset({"pending", "supported", "unsupported", "unclear"})
_SHA = re.compile(r"[a-f0-9]{64}\Z")


def _load_json(path: Path, *, limit: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("review JSON must be a bounded regular file")
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate review JSON property: {key}")
            result[key] = value
        return result
    try:
        result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                            parse_constant=lambda v: (_ for _ in ()).throw(
                                ValueError(f"non-finite review JSON: {v}")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid character review JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("character review JSON must be an object")
    return result


def _bound_proposals(
    report: dict[str, Any], vision: dict[str, Any],
    scene: dict[str, Any],
) -> list[dict[str, Any]]:
    """Ensure each inference proposal is uniquely tied to an existing box/PTS."""
    frames = _validate_report(report)
    if (vision.get("schemaVersion") != LOCAL_VISION_VERSION or
            vision.get("sourceSha256") != report["sourceSha256"] or
            vision.get("sourceTimebase") != report["sourceTimebase"] or
            scene["sourceSha256"] != report["sourceSha256"] or
            scene["sourceStreamIndex"] != report["sourceStreamIndex"] or
            scene["sourceTimebase"] != report["sourceTimebase"]):
        raise ValueError("character vision, scene and detector source provenance disagree")
    observations = vision.get("observations")
    if not isinstance(observations, list) or not 0 <= len(observations) <= 24:
        raise ValueError("character vision observations exceed bounded model calls")
    if (vision.get("modelCalls") != len(observations) or
            vision.get("appearanceCount") != len(observations) or
            vision.get("actionProposalCount") != len(scene["actions"]) or
            len(scene["appearances"]) != len(observations)):
        raise ValueError("character vision counts do not match scene annotations")
    proposals = {}
    for frame in frames:
        for item in frame["proposals"]:
            proposals[(frame["sourcePts"], item["trackletId"])] = item
    scene_appearances = {
        (item["startPts"], item["characterId"]): item for item in scene["appearances"]
    }
    if len(scene_appearances) != len(scene["appearances"]):
        raise ValueError("duplicate character appearance at a source PTS")
    actions = {
        (item["endPts"]-1, item["actorId"]): item for item in scene["actions"]
    }
    if len(actions) != len(scene["actions"]):
        raise ValueError("duplicate character motion action at a source PTS")
    bound = []
    claimed = set()
    last_pts = None
    for i, observation in enumerate(observations):
        required = {"trackletId", "sourcePts", "comparisonStartPts", "appearance",
                    "visibleTraits", "action", "motionEvidence", "evidenceStatus"}
        if not isinstance(observation, dict) or set(observation) != required:
            raise ValueError(f"vision observation {i} has malformed fields")
        tid, pts = observation["trackletId"], observation["sourcePts"]
        if type(tid) is not str or type(pts) is not int:
            raise ValueError("vision observation requires a string tracklet ID and integer PTS")
        if (type(observation["appearance"]) is not str or
                not 1 <= len(observation["appearance"]) <= 800 or
                type(observation["motionEvidence"]) is not str or
                len(observation["motionEvidence"]) > 400 or
                not isinstance(observation["visibleTraits"], list) or
                any(type(t) is not str or len(t) > 100
                    for t in observation["visibleTraits"])):
            raise ValueError("unbounded or malformed model observation text")
        key = (pts, tid)
        if key in claimed or key not in proposals or key not in scene_appearances:
            raise ValueError("vision observation lacks unique source tracklet/appearance evidence")
        if last_pts is not None and pts < last_pts:
            raise ValueError("vision observations must be chronological")
        claimed.add(key)
        last_pts = pts
        proposal, appearance = proposals[key], scene_appearances[key]
        if (appearance["anchorBox"] != proposal["box"] or
                appearance["endPts"] != pts+1 or
                appearance["anchorPts"] != [pts] or
                appearance["visibleTraits"] != observation["visibleTraits"] or
                appearance["confidence"] != "low" or
                observation["evidenceStatus"] != "local-model-proposal-not-reviewed"):
            raise ValueError("vision appearance contradicts source box or model evidence")
        action = observation["action"]
        if type(action) is not str:
            raise ValueError("vision action must be a string label")
        prior = observation["comparisonStartPts"]
        if action == "none":
            if prior is not None and type(prior) is not int:
                raise ValueError("vision comparison PTS invalid")
            if key in actions:
                raise ValueError("model reported no action but scene invents one")
        else:
            event = actions.get(key)
            if (event is None or type(prior) is not int or
                    event["action"] != action or event["startPts"] != prior or
                    event["endPts"] != pts+1 or event["targetId"] is not None or
                    event["anchorPts"] != [prior, pts] or event["confidence"] != "low"):
                raise ValueError("vision action contradicts timecoded scene evidence")
        bound.append({**observation, "box": proposal["box"]})
    if len([x for x in bound if x["action"] != "none"]) != len(actions):
        raise ValueError("character scene contains unaudited action events")
    return bound


def _html_page(rows: list[dict[str, Any]], source_name: str) -> str:
    items = []
    for row in rows:
        traits = ", ".join(row["visibleTraits"]) or "(none proposed)"
        action = row["action"] if row["action"] != "none" else "(no motion proposed)"
        items.append(
            '<article><div class="images">'
            f'<img src="{html.escape(row["fullImage"], quote=True)}" '
            f'alt="Original decoded source frame at PTS {row["sourcePts"]}">'
            f'<img src="{html.escape(row["cropImage"], quote=True)}" '
            f'alt="Detector-proposed crop for {html.escape(row["trackletId"], quote=True)}">'
            '</div><div class="content">'
            f'<h2>{html.escape(row["trackletId"])} at PTS {row["sourcePts"]}</h2>'
            f'<p><strong>Appearance proposal:</strong> {html.escape(row["appearance"])}</p>'
            f'<p><strong>Visible traits:</strong> {html.escape(traits)}</p>'
            f'<p><strong>Action proposal:</strong> {html.escape(action)}</p>'
            f'<p><strong>Temporal evidence:</strong> {html.escape(row["motionEvidence"])}</p>'
            '<small>Model inference only. Inspect the source frames before approving claims.</small>'
            '</div></article>'
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Local character vision QA</title><style>'
        ':root{color-scheme:dark;font-family:system-ui,sans-serif}'
        'body{background:#0b1220;color:#eaf1ff;margin:0;padding:25px}'
        'main{max-width:1200px;margin:auto}article{background:#182337;'
        'border:1px solid #344055;border-radius:12px;margin:16px 0;overflow:hidden}'
        '.images{display:flex;gap:10px;padding:12px;flex-wrap:wrap}'
        '.images img{max-width:48%;height:auto;object-fit:contain;background:#0c1422}'
        '.content{padding:0 16px 16px}h1{font-size:26px}h2{font-size:18px}'
        'p{line-height:1.55;color:#cfd9ed}small{color:#f6cc89}'
        '</style></head><body><main><h1>Character vision evidence QA</h1><p>'
        + html.escape(source_name) +
        ' — decoded local frames with model-proposed subject crops. '
        'Images and timing are source-grounded; semantic descriptions and actions '
        'are unverified. No automated approvals.</p>'
        + "".join(items) + '</main></body></html>\n'
    )


def build_character_vision_review(source: Path, report_path: Path,
                                  vision_dir: Path, out: Path, *,
                                  scan_seconds: int = 20,
                                  width: int = 320, height: int = 180,
                                  ffprobe: str = "ffprobe",
                                  ffmpeg: str = "ffmpeg") -> Path:
    """Regenerate actual source frames and crops for manual semantic review."""
    if (type(scan_seconds) is not int or not 1 <= scan_seconds <= 120 or
            type(width) is not int or not 64 <= width <= 320 or
            type(height) is not int or not 36 <= height <= 180):
        raise ValueError("character review scan/resolution out of bounds")
    if out.exists() or out.is_symlink():
        raise ValueError("character review destination must be new")
    signatures = [file_signature(x) for x in
                  (source, report_path, vision_dir / "character-vision.json",
                   vision_dir / "character-scene.json")]
    report = _json_file(report_path, limit=2_000_000)
    scene = load_character_scene(vision_dir / "character-scene.json")
    vision = _load_json(vision_dir / "character-vision.json", limit=262144)
    if vision.get("trackletReportSha256") != sha256_file(report_path):
        raise ValueError("vision manifest is not bound to this tracklet report")
    bound = _bound_proposals(report, vision, scene)
    if not bound:
        raise ValueError("no vision observations to review")
    metadata = inspect_source(source, ffprobe=ffprobe)
    if (metadata["source"]["sha256"] != report["sourceSha256"] or
            metadata["video"]["streamIndex"] != report["sourceStreamIndex"] or
            metadata["video"]["sourceTimebase"] != report["sourceTimebase"]):
        raise ValueError("local source does not match model and tracklet evidence")
    pts = sorted({item["sourcePts"] for item in bound})
    if len(pts) > 12:
        raise ValueError("vision review exceeds 12 distinct decoded frames")
    frame_records = read_frame_pts(source, report["sourceStreamIndex"],
                                   seconds=scan_seconds, ffprobe=ffprobe)
    by_pts: dict[int, list[int]] = {}
    for frame in frame_records:
        if frame.pts is not None:
            by_pts.setdefault(frame.pts, []).append(frame.ordinal)
    ordinals = []
    for point in pts:
        candidates = by_pts.get(point, [])
        if len(candidates) != 1:
            raise ValueError("review source PTS missing or ambiguous")
        ordinals.append(candidates[0])
    if ordinals != sorted(set(ordinals)):
        raise ValueError("review requires unique source frames in decode order")
    timebase = Fraction(**report["sourceTimebase"])
    rgb = read_rgb_frames(
        source, report["sourceStreamIndex"], ordinals, pts, timebase=timebase,
        seconds=scan_seconds, width=width, height=height, ffmpeg=ffmpeg)
    by_frame = dict(zip(pts, rgb, strict=True))
    for path, signature in zip(
        (source, report_path, vision_dir / "character-vision.json",
         vision_dir / "character-scene.json"), signatures, strict=True
    ):
        require_unchanged(path, signature)
    manifest_sha = sha256_file(vision_dir / "character-vision.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".kumiki-character-qa-", dir=out.parent) as folder:
        staging = Path(folder)
        (staging / "frames").mkdir()
        for i, point in enumerate(pts):
            (staging / "frames" / f"frame-{i:03d}.png").write_bytes(
                _png_rgb(by_frame[point], width, height))
        frame_paths = {point: f"frames/frame-{i:03d}.png" for i, point in enumerate(pts)}
        rows = []
        for i, observation in enumerate(bound):
            crop, cw, ch = _crop_rgb(
                by_frame[observation["sourcePts"]], width, height, observation["box"])
            crop_path = f"frames/crop-{i:03d}.png"
            (staging / crop_path).write_bytes(_png_rgb(crop, cw, ch))
            rows.append({**observation, "fullImage": frame_paths[observation["sourcePts"]],
                         "cropImage": crop_path})
        (staging / "index.html").write_text(
            _html_page(rows, metadata["source"]["fileName"]), encoding="utf-8")
        feedback = {
            "schemaVersion": FEEDBACK_VERSION,
            "sourceSha256": report["sourceSha256"],
            "visionManifestSha256": manifest_sha,
            "reviewer": {"kind": "human", "id": "unassigned"},
            "observations": [
                {"index": i, "appearanceVerdict": "pending",
                 "actionVerdict": ("not-applicable" if row["action"] == "none" else "pending"),
                 "notes": ""} for i, row in enumerate(bound)],
        }
        (staging / "review-feedback.json").write_text(
            json.dumps(feedback, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
        (staging / "review-manifest.json").write_text(
            json.dumps({
                "schemaVersion": REVIEW_VERSION, "sourceSha256": report["sourceSha256"],
                "visionManifestSha256": manifest_sha, "observationCount": len(rows),
                "framePts": pts, "reviewStatus": "pending-human-review",
                "sourcePixelEvidence": "verified-frame-pts-cropped-local-video",
                "semanticValidity": "not-reviewed",
            }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        for path, signature in zip(
            (source, report_path, vision_dir / "character-vision.json",
             vision_dir / "character-scene.json"), signatures, strict=True
        ):
            require_unchanged(path, signature)
        os.replace(staging, out)
    return out / "index.html"


def summarize_character_vision_feedback(feedback_path: Path, vision_path: Path) -> dict[str, Any]:
    """Count explicit human review verdicts; never treat pending as a negative."""
    feedback = _load_json(feedback_path, limit=131072)
    vision = _load_json(vision_path, limit=262144)
    if (feedback.get("schemaVersion") != FEEDBACK_VERSION or
            vision.get("schemaVersion") != LOCAL_VISION_VERSION or
            feedback.get("sourceSha256") != vision.get("sourceSha256") or
            feedback.get("visionManifestSha256") != sha256_file(vision_path)):
        raise ValueError("review feedback does not match its source vision manifest")
    reviewer = feedback.get("reviewer")
    if (not isinstance(reviewer, dict) or set(reviewer) != {"kind", "id"} or
            reviewer["kind"] != "human" or
            type(reviewer["id"]) is not str or
            not 2 <= len(reviewer["id"].strip()) <= 100):
        raise ValueError("human feedback reviewer must have a bounded ID")
    actual, expected = feedback.get("observations"), vision.get("observations")
    if not isinstance(actual, list) or not isinstance(expected, list) or len(actual) != len(expected):
        raise ValueError("review feedback observation count mismatch")
    appearance = Counter()
    motion = Counter()
    by_action: dict[str, Counter] = {}
    for i, (row, source) in enumerate(zip(actual, expected, strict=True)):
        if (not isinstance(row, dict) or set(row) !=
                {"index", "appearanceVerdict", "actionVerdict", "notes"} or
                type(row["index"]) is not int or row["index"] != i or
                type(row["appearanceVerdict"]) is not str or
                row["appearanceVerdict"] not in _VERDICTS or
                type(row["actionVerdict"]) is not str or
                type(row["notes"]) is not str or len(row["notes"]) > 500):
            raise ValueError(f"feedback row {i} invalid")
        verdict = row["actionVerdict"]
        if source["action"] == "none":
            if verdict != "not-applicable":
                raise ValueError("no-action observations cannot have an action verdict")
        elif verdict not in _VERDICTS:
            raise ValueError("action verdict invalid for a motion proposal")
        appearance[row["appearanceVerdict"]] += 1
        if source["action"] != "none":
            motion[verdict] += 1
            by_action.setdefault(source["action"], Counter())[verdict] += 1
    decided = sum(appearance[x] for x in ("supported", "unsupported", "unclear"))
    action_decided = sum(motion[x] for x in ("supported", "unsupported", "unclear"))
    if reviewer["id"].strip() == "unassigned" and (decided or action_decided):
        raise ValueError("reviewer must be assigned before submitting any verdict")
    def score(bucket: Counter) -> float | None:
        total = bucket["supported"] + bucket["unsupported"]
        return round(bucket["supported"] / total, 6) if total else None
    return {
        "schemaVersion": _METRICS_VERSION,
        "sourceSha256": vision["sourceSha256"],
        "visionManifestSha256": feedback["visionManifestSha256"],
        "reviewer": reviewer,
        "appearanceTotal": len(actual), "appearanceReviewed": decided,
        "appearanceDecidedSupportRate": score(appearance),
        "appearanceVerdicts": dict(sorted(appearance.items())),
        "actionTotal": sum(row["action"] != "none" for row in expected),
        "actionReviewed": action_decided,
        "actionDecidedSupportRate": score(motion),
        "actionVerdicts": dict(sorted(motion.items())),
        "byActionLabel": [
            {"action": action, "verdicts": dict(sorted(counts.items())),
             "decidedSupportRate": score(counts)}
            for action, counts in sorted(by_action.items())
        ],
        "qualityAssessmentAvailable": bool(decided or action_decided),
        "methodLimits": [
            "Support rates are among explicitly supported/unsupported human judgments, not calibrated population accuracy.",
            "Pending and unclear verdicts are not counted as model successes or failures.",
            "This tool does not verify the human reviewer's identity or independently audit the truth of their labels.",
            "Only visible model proposals are reviewed; detection false negatives and missed actions are not measured.",
        ],
    }
