"""Thin CLI for repeatable local analysis without optional neural dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.appearance.analyze import analyze_appearance
from kumiki_reference_lab.analyzers.audio.timeline import analyze_audio_timeline
from kumiki_reference_lab.analyzers.audio.levels import analyze_audio_levels
from kumiki_reference_lab.analyzers.audio.onsets import analyze_audio_onsets
from kumiki_reference_lab.analyzers.audio.av_cuts import build_av_cut_evidence
from kumiki_reference_lab.analyzers.comparison.appearance import compare_appearance
from kumiki_reference_lab.analyzers.comparison.frames import build_frame_comparison
from kumiki_reference_lab.analyzers.techniques.propose import propose_techniques
from kumiki_reference_lab.analyzers.techniques.review import build_technique_review
from kumiki_reference_lab.analyzers.shots.evidence import build_shot_evidence
from kumiki_reference_lab.analyzers.shots.rhythm import build_edit_rhythm
from kumiki_reference_lab.analyzers.shots.timeline_view import build_timeline_view
from kumiki_reference_lab.analyzers.shots.gallery import build_shot_gallery
from kumiki_reference_lab.analyzers.media.contact_sheet import build_contact_sheet
from kumiki_reference_lab.analyzers.motion.analyze import analyze_image_motion
from kumiki_reference_lab.analyzers.motion.dense import analyze_dense_flow
from kumiki_reference_lab.analyzers.motion.sparse import analyze_sparse_flow
from kumiki_reference_lab.analyzers.motion.review import build_sparse_flow_review
from kumiki_reference_lab.analyzers.subjects.roi import analyze_roi_track
from kumiki_reference_lab.analyzers.subjects.review import build_roi_review
from kumiki_reference_lab.analyzers.media.timeline import analyze_frame_timeline
from kumiki_reference_lab.analyzers.shots.detect import analyze_hard_cuts
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.catalog.store import build_catalog_index, load_catalog, search_catalog
from kumiki_reference_lab.contracts.source import RIGHTS_STATUSES
from kumiki_reference_lab.core.artifacts import write_json_artifact
from kumiki_reference_lab.pipeline.analyze import run_analysis
from kumiki_reference_lab.pipeline.study import study_reference
from kumiki_reference_lab.integrations.kumiki.film_handoff import export_film_handoff
from kumiki_reference_lab.integrations.kumiki.film_map_review import build_film_map_review
from kumiki_reference_lab.integrations.kumiki.film_feedback import (
    init_film_feedback, validate_film_feedback,
)
from kumiki_reference_lab.reviews.notes import review_notes_template, validate_review_notes


def _read_roi_reseeds(path: Path | None) -> list[dict] | None:
    if path is None:
        return None
    with path.open("rb") as handle:
        payload = handle.read(32769)
    if len(payload) > 32768:
        raise ValueError("ROI reseed JSON must be at most 32 KiB")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("ROI reseed file is not valid UTF-8 JSON") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kumiki-ref", description="Kumiki Reference Lab")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="inspect a local video, without AI")
    inspect.add_argument("source", type=Path)
    inspect.add_argument("--out", type=Path, help="output directory for source-manifest.json")
    inspect.add_argument("--ffprobe", default="ffprobe", help="ffprobe executable or path")
    inspect.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    frames = commands.add_parser("frames", help="extract bounded source presentation timestamps")
    frames.add_argument("source", type=Path)
    frames.add_argument("--out", type=Path)
    frames.add_argument("--max-seconds", type=int, default=60)
    frames.add_argument("--ffprobe", default="ffprobe")
    frames.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    cuts = commands.add_parser("cuts", help="find bounded hard-cut candidates")
    cuts.add_argument("source", type=Path)
    cuts.add_argument("--out", type=Path)
    cuts.add_argument("--max-seconds", type=int, default=60)
    cuts.add_argument("--threshold", type=float, default=0.25)
    cuts.add_argument("--ffmpeg", default="ffmpeg")
    cuts.add_argument("--ffprobe", default="ffprobe")
    cuts.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    sheet = commands.add_parser("contact-sheet", help="create bounded timecoded JPEG/HTML evidence")
    sheet.add_argument("source", type=Path)
    sheet.add_argument("--out", type=Path, required=True, help="parent directory for immutable bundle")
    sheet.add_argument("--max-seconds", type=int, default=30)
    sheet.add_argument("--max-thumbnails", type=int, default=12)
    sheet.add_argument("--width", type=int, default=480)
    sheet.add_argument("--threshold", type=float, default=0.25)
    sheet.add_argument("--ffmpeg", default="ffmpeg")
    sheet.add_argument("--ffprobe", default="ffprobe")
    sheet.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    motion = commands.add_parser("motion", help="measure sampled global image-plane translation")
    motion.add_argument("source", type=Path)
    motion.add_argument("--out", type=Path)
    motion.add_argument("--max-seconds", type=int, default=10)
    motion.add_argument("--max-samples", type=int, default=48)
    motion.add_argument("--width", type=int, default=160)
    motion.add_argument("--height", type=int, default=90)
    motion.add_argument("--threshold", type=float, default=0.25)
    motion.add_argument("--ffmpeg", default="ffmpeg")
    motion.add_argument("--ffprobe", default="ffprobe")
    motion.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    roi = commands.add_parser("track-roi", help="track a manually seeded textured image region")
    roi.add_argument("source", type=Path)
    roi.add_argument("--box", type=float, nargs=4, required=True,
                     metavar=("X", "Y", "WIDTH", "HEIGHT"),
                     help="normalized bounding box on the first sampled frame")
    roi.add_argument("--reseeds", type=Path,
                     help="JSON array of additional {sourcePts,box} manual anchors")
    roi.add_argument("--out", type=Path)
    roi.add_argument("--max-seconds", type=int, default=10)
    roi.add_argument("--max-samples", type=int, default=48)
    roi.add_argument("--width", type=int, default=160)
    roi.add_argument("--height", type=int, default=90)
    roi.add_argument("--radius", type=int, default=12)
    roi.add_argument("--correlation", type=float, default=0.62)
    roi.add_argument("--threshold", type=float, default=0.25)
    roi.add_argument("--ffmpeg", default="ffmpeg")
    roi.add_argument("--ffprobe", default="ffprobe")
    roi.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    sparse = commands.add_parser("sparse-flow", help="track distributed 2D features and motion groups")
    sparse.add_argument("source", type=Path)
    sparse.add_argument("--out", type=Path)
    sparse.add_argument("--max-seconds", type=int, default=10)
    sparse.add_argument("--max-samples", type=int, default=24)
    sparse.add_argument("--width", type=int, default=160)
    sparse.add_argument("--height", type=int, default=90)
    sparse.add_argument("--max-points", type=int, default=40)
    sparse.add_argument("--radius", type=int, default=8)
    sparse.add_argument("--pyramid-levels", type=int, choices=(1, 2), default=1,
                        help="optional coarse-to-fine recovery for displacement beyond local radius")
    sparse.add_argument("--subpixel-refinement", action="store_true",
                        help="candidate fractional NCC peak offsets; reverse gate stays integer")
    sparse.add_argument("--subpixel-reverse-check", action="store_true",
                        help="also check fractional peaks with reverse bilinear patch matching")
    sparse.add_argument("--lk-refinement", action="store_true",
                        help="optional bounded bidirectional Lucas-Kanade refinement of accepted matches")
    sparse.add_argument("--quadrant-consistency", action="store_true",
                        help="reject matches lacking independent local subpatch appearance support")
    sparse.add_argument("--projective-hypotheses", action="store_true",
                        help="optional bounded projective image-plane fit; never a camera claim")
    sparse.add_argument("--model-validation", action="store_true",
                        help="opt-in held-out spatial prediction test for translation/affine/projective")
    sparse.add_argument("--tracklet-motion-consistency", action="store_true",
                        help="optionally abstain from implausible consecutive PTS-scaled motion links")
    sparse.add_argument("--tracklet-appearance-consistency", action="store_true",
                        help="optionally verify two-hop observed patch agreement before linking")
    sparse.add_argument("--correlation", type=float, default=0.68)
    sparse.add_argument("--threshold", type=float, default=0.25)
    sparse.add_argument("--ffmpeg", default="ffmpeg")
    sparse.add_argument("--ffprobe", default="ffprobe")
    sparse.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    dense = commands.add_parser("dense-flow", help="optional bounded dense 2D optical flow")
    dense.add_argument("source", type=Path)
    dense.add_argument("--out", type=Path)
    dense.add_argument("--max-seconds", type=int, default=10)
    dense.add_argument("--max-samples", type=int, default=24)
    dense.add_argument("--width", type=int, default=160)
    dense.add_argument("--height", type=int, default=90)
    dense.add_argument("--grid-step", type=int, default=12)
    dense.add_argument("--threshold", type=float, default=0.25)
    dense.add_argument("--ffmpeg", default="ffmpeg")
    dense.add_argument("--ffprobe", default="ffprobe")
    dense.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    sparse_review = commands.add_parser(
        "review-sparse-flow", help="inspect source-verified sparse motion on original frames")
    sparse_review.add_argument("source", type=Path)
    sparse_review.add_argument("sparse_report", type=Path)
    sparse_review.add_argument("--out", type=Path, required=True)
    sparse_review.add_argument("--max-frames", type=int, default=8)
    sparse_review.add_argument("--max-tracklets", type=int, default=12)
    sparse_review.add_argument("--ffmpeg", default="ffmpeg")
    sparse_review.add_argument("--ffprobe", default="ffprobe")

    roi_review = commands.add_parser(
        "review-roi", help="view verified ROI boxes and loss on original source frames")
    roi_review.add_argument("source", type=Path)
    roi_review.add_argument("roi_report", type=Path)
    roi_review.add_argument("--out", type=Path, required=True)
    roi_review.add_argument("--max-frames", type=int, default=8)
    roi_review.add_argument("--ffmpeg", default="ffmpeg")
    roi_review.add_argument("--ffprobe", default="ffprobe")

    appearance = commands.add_parser("appearance", help="measure RGB palette, contrast, highlight, and color changes")
    appearance.add_argument("source", type=Path)
    appearance.add_argument("--out", type=Path)
    appearance.add_argument("--max-seconds", type=int, default=10)
    appearance.add_argument("--max-samples", type=int, default=24)
    appearance.add_argument("--width", type=int, default=160)
    appearance.add_argument("--height", type=int, default=90)
    appearance.add_argument("--threshold", type=float, default=0.25)
    appearance.add_argument("--ffmpeg", default="ffmpeg")
    appearance.add_argument("--ffprobe", default="ffprobe")
    appearance.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    audio = commands.add_parser(
        "audio-timeline", help="inspect bounded, original-PTS audio frame timing without AI")
    audio.add_argument("source", type=Path)
    audio.add_argument("--out", type=Path)
    audio.add_argument("--max-seconds", type=int, default=10)
    audio.add_argument("--max-frames", type=int, default=4096)
    audio.add_argument("--ffprobe", default="ffprobe")
    audio.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    levels = commands.add_parser(
        "audio-levels", help="measure source-PTS-checked decoded audio RMS/peak levels")
    levels.add_argument("source", type=Path)
    levels.add_argument("--out", type=Path)
    levels.add_argument("--max-seconds", type=int, default=10)
    levels.add_argument("--max-frames", type=int, default=4096)
    levels.add_argument("--ffmpeg", default="ffmpeg")
    levels.add_argument("--ffprobe", default="ffprobe")
    levels.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    onsets = commands.add_parser(
        "audio-onsets", help="source-PTS-verified candidate audio level attacks (not beats/SFX)")
    onsets.add_argument("source", type=Path)
    onsets.add_argument("--out", type=Path)
    onsets.add_argument("--max-seconds", type=int, default=10)
    onsets.add_argument("--max-frames", type=int, default=4096)
    onsets.add_argument("--min-rise-db", type=float, default=12.0)
    onsets.add_argument("--min-peak-dbfs", type=float, default=-40.0)
    onsets.add_argument("--cooldown-ms", type=int, default=120)
    onsets.add_argument("--ffmpeg", default="ffmpeg")
    onsets.add_argument("--ffprobe", default="ffprobe")
    onsets.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    av = commands.add_parser(
        "av-cut-evidence", help="compare candidate video edits to source-timecoded audio level changes")
    av.add_argument("source", type=Path)
    av.add_argument("analysis_run", type=Path)
    av.add_argument("--out", type=Path)
    av.add_argument("--window-ms", type=int, default=400)
    av.add_argument("--max-audio-frames", type=int, default=4096)
    av.add_argument("--ffmpeg", default="ffmpeg")
    av.add_argument("--ffprobe", default="ffprobe")

    comparison = commands.add_parser("compare-appearance",
                                     help="compare two appearance reports using explicit time anchors")
    comparison.add_argument("reference_report", type=Path)
    comparison.add_argument("candidate_report", type=Path)
    comparison.add_argument("--reference-anchor-ms", type=int, required=True)
    comparison.add_argument("--candidate-anchor-ms", type=int, required=True)
    comparison.add_argument("--tolerance-ms", type=int, default=150)
    comparison.add_argument("--time-scale", default="1")
    comparison.add_argument("--out", type=Path)

    frame_compare = commands.add_parser("compare-frames",
                                        help="create immutable aligned side-by-side video frame evidence")
    frame_compare.add_argument("reference", type=Path)
    frame_compare.add_argument("candidate", type=Path)
    frame_compare.add_argument("--out", type=Path, required=True)
    frame_compare.add_argument("--reference-anchor-ms", type=int, required=True)
    frame_compare.add_argument("--candidate-anchor-ms", type=int, required=True)
    frame_compare.add_argument("--tolerance-ms", type=int, default=150)
    frame_compare.add_argument("--time-scale", default="1")
    frame_compare.add_argument("--max-seconds", type=int, default=10)
    frame_compare.add_argument("--max-samples", type=int, default=10)
    frame_compare.add_argument("--width", type=int, default=480)
    frame_compare.add_argument("--ffmpeg", default="ffmpeg")
    frame_compare.add_argument("--ffprobe", default="ffprobe")
    frame_compare.add_argument("--rights-status", choices=RIGHTS_STATUSES,
                               default="review-required")

    film_map = commands.add_parser(
        "review-film-map", help="extract verified PTS source/FD1 render stills from explicit anchors")
    film_map.add_argument("review_map", type=Path)
    film_map.add_argument("authored_film", type=Path)
    film_map.add_argument("source", type=Path)
    film_map.add_argument("render", type=Path)
    film_map.add_argument("--out", type=Path, required=True)
    film_map.add_argument("--max-seconds", type=int, default=30)
    film_map.add_argument("--width", type=int, default=480)
    film_map.add_argument("--ffmpeg", default="ffmpeg")
    film_map.add_argument("--ffprobe", default="ffprobe")

    feedback = commands.add_parser(
        "film-feedback", help="author or validate source/render evidence-bound revision notes")
    feedback_actions = feedback.add_subparsers(dest="feedback_action", required=True)
    feedback_init = feedback_actions.add_parser("init", help="create an empty film feedback draft")
    feedback_init.add_argument("review_manifest", type=Path)
    feedback_init.add_argument("--out", type=Path, required=True)
    feedback_init.add_argument("--reviewer-kind", choices=("human", "ai"), default="human")
    feedback_init.add_argument("--reviewer-id", required=True)
    feedback_init.add_argument("--model-id")
    feedback_check = feedback_actions.add_parser("validate", help="verify anchors, hashes and notes")
    feedback_check.add_argument("review_manifest", type=Path)
    feedback_check.add_argument("feedback", type=Path)

    technique_proposals = commands.add_parser(
        "propose-techniques", help="derive conservative, source-linked cinematic review cues")
    technique_proposals.add_argument("analysis_run", type=Path,
                                     help="analysis-run.json from an immutable verified run")
    technique_proposals.add_argument("--catalog-root", type=Path,
                                     default=Path("catalog/entries"))
    technique_proposals.add_argument("--out", type=Path)

    technique_review = commands.add_parser(
        "review-techniques", help="render source-verified frames for technique review cues")
    technique_review.add_argument("source", type=Path)
    technique_review.add_argument("analysis_run", type=Path)
    technique_review.add_argument("--out", type=Path, required=True)
    technique_review.add_argument("--catalog-root", type=Path,
                                  default=Path("catalog/entries"))
    technique_review.add_argument("--max-cues", type=int, default=8)
    technique_review.add_argument("--cue-offset", type=int, default=0,
                                  help="zero-based offset into chronological cue results")
    technique_review.add_argument("--width", type=int, default=480)
    technique_review.add_argument("--ffmpeg", default="ffmpeg")
    technique_review.add_argument("--ffprobe", default="ffprobe")

    shot_evidence = commands.add_parser(
        "shot-evidence", help="summarize verified evidence by candidate edit regions")
    shot_evidence.add_argument("analysis_run", type=Path)
    shot_evidence.add_argument("--out", type=Path)

    edit_rhythm = commands.add_parser(
        "edit-rhythm", help="measure exact candidate cut-to-cut intervals and pacing changes")
    edit_rhythm.add_argument("analysis_run", type=Path)
    edit_rhythm.add_argument("--out", type=Path)

    shot_gallery = commands.add_parser(
        "review-shots", help="render original-frame storyboards for candidate edit regions")
    shot_gallery.add_argument("source", type=Path)
    shot_gallery.add_argument("analysis_run", type=Path)
    shot_gallery.add_argument("--out", type=Path, required=True)
    shot_gallery.add_argument("--max-regions", type=int, default=8)
    shot_gallery.add_argument("--region-offset", type=int, default=0)
    shot_gallery.add_argument("--width", type=int, default=480)
    shot_gallery.add_argument("--ffmpeg", default="ffmpeg")
    shot_gallery.add_argument("--ffprobe", default="ffprobe")

    timeline_view = commands.add_parser(
        "review-timeline", help="visual review of aligned candidate cuts, pacing, image motion and audio contrast")
    timeline_view.add_argument("source", type=Path)
    timeline_view.add_argument("analysis_run", type=Path)
    timeline_view.add_argument("--out", type=Path, required=True)
    timeline_view.add_argument("--window-ms", type=int, default=400)
    timeline_view.add_argument("--max-audio-frames", type=int, default=4096)
    timeline_view.add_argument("--onset-min-rise-db", type=float, default=12.0)
    timeline_view.add_argument("--onset-min-peak-dbfs", type=float, default=-40.0)
    timeline_view.add_argument("--onset-cooldown-ms", type=int, default=120)
    timeline_view.add_argument("--ffmpeg", default="ffmpeg")
    timeline_view.add_argument("--ffprobe", default="ffprobe")

    study = commands.add_parser(
        "study-reference", help="one command: analyze, propose, summarize, and render cue review")
    study.add_argument("source", type=Path)
    study.add_argument("--out", type=Path, required=True)
    study.add_argument("--catalog-root", type=Path, default=Path("catalog/entries"))
    study.add_argument("--max-seconds", type=int, default=10)
    study.add_argument("--thumbnails", type=int, default=8)
    study.add_argument("--max-cues", type=int, default=8)
    study.add_argument("--ffmpeg", default="ffmpeg")
    study.add_argument("--ffprobe", default="ffprobe")
    study.add_argument("--rights-status", choices=RIGHTS_STATUSES,
                       default="review-required")

    handoff = commands.add_parser(
        "export-film-handoff",
        help="verified study -> non-executable FD1 authoring evidence packet")
    handoff.add_argument("study_manifest", type=Path,
                         help="study-manifest.json from a verified v5 study")
    handoff.add_argument("--out", type=Path, required=True,
                         help="directory outside immutable study/analysis bundles")
    handoff.add_argument("--fps-num", type=int, default=30)
    handoff.add_argument("--fps-den", type=int, default=1)

    notes = commands.add_parser(
        "review-notes", help="create or validate source-linked, unapproved human/AI notes")
    notes_actions = notes.add_subparsers(dest="review_notes_action", required=True)
    notes_init = notes_actions.add_parser("init", help="create an empty immutable review draft")
    notes_init.add_argument("study_manifest", type=Path)
    notes_init.add_argument("--out", type=Path, required=True)
    notes_init.add_argument("--reviewer-kind", choices=("human", "ai"), default="human")
    notes_init.add_argument("--reviewer-id", required=True)
    notes_init.add_argument("--model-id")
    notes_check = notes_actions.add_parser(
        "validate", help="check full study provenance and exact frame evidence anchors")
    notes_check.add_argument("study_manifest", type=Path)
    notes_check.add_argument("review_notes", type=Path)

    analyze = commands.add_parser("analyze", help="run a bounded, atomic multi-stage reference analysis")
    analyze.add_argument("source", type=Path)
    analyze.add_argument("--out", type=Path, required=True, help="parent directory for immutable run")
    analyze.add_argument("--max-seconds", type=int, default=10)
    analyze.add_argument("--thumbnails", type=int, default=12)
    analyze.add_argument("--motion", action="store_true", help="include optional NumPy motion measurements")
    analyze.add_argument("--sparse-flow", action="store_true",
                         help="include optional multi-feature image motion measurements")
    analyze.add_argument("--sparse-samples", type=int, default=24)
    analyze.add_argument("--sparse-points", type=int, default=40)
    analyze.add_argument("--sparse-radius", type=int, default=8)
    analyze.add_argument("--sparse-pyramid-levels", type=int, choices=(1, 2), default=1)
    analyze.add_argument("--sparse-subpixel-refinement", action="store_true")
    analyze.add_argument("--sparse-subpixel-reverse-check", action="store_true")
    analyze.add_argument("--sparse-lk-refinement", action="store_true")
    analyze.add_argument("--sparse-quadrant-consistency", action="store_true")
    analyze.add_argument("--sparse-projective-hypotheses", action="store_true")
    analyze.add_argument("--sparse-model-validation", action="store_true")
    analyze.add_argument("--sparse-tracklet-motion-consistency", action="store_true")
    analyze.add_argument("--sparse-tracklet-appearance-consistency", action="store_true")
    analyze.add_argument("--dense-flow", action="store_true",
                         help="include optional multiscale dense image-plane flow measurements")
    analyze.add_argument("--dense-samples", type=int, default=24)
    analyze.add_argument("--dense-grid-step", type=int, default=12)
    analyze.add_argument("--sparse-correlation", type=float, default=0.68)
    analyze.add_argument("--appearance", action="store_true",
                         help="include optional timecoded RGB appearance evidence")
    analyze.add_argument("--appearance-samples", type=int, default=24)
    analyze.add_argument("--box", type=float, nargs=4,
                         metavar=("X", "Y", "WIDTH", "HEIGHT"),
                         help="optional seeded ROI in normalized image coordinates")
    analyze.add_argument("--roi-reseeds", type=Path,
                         help="JSON array of manual ROI anchors after the initial box")
    analyze.add_argument("--max-samples", type=int, default=48)
    analyze.add_argument("--width", type=int, default=160)
    analyze.add_argument("--height", type=int, default=90)
    analyze.add_argument("--threshold", type=float, default=0.25)
    analyze.add_argument("--ffmpeg", default="ffmpeg")
    analyze.add_argument("--ffprobe", default="ffprobe")
    analyze.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    catalog = commands.add_parser("catalog", help="search and validate cinematic technique research")
    catalog_actions = catalog.add_subparsers(dest="catalog_action", required=True)
    for action in ("validate", "search", "index"):
        sub = catalog_actions.add_parser(action)
        sub.add_argument("--root", type=Path, default=Path("catalog/entries"),
                         help="canonical technique JSON directory")
        if action == "search":
            sub.add_argument("query", help="free-text intent or visual technique query")
            sub.add_argument("--limit", type=int, default=20)
        elif action == "index":
            sub.add_argument("--out", type=Path, required=True,
                             help="directory for immutable catalog-index.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "film-feedback":
            if args.feedback_action == "init":
                print(init_film_feedback(
                    args.review_manifest, args.out, reviewer_kind=args.reviewer_kind,
                    reviewer_id=args.reviewer_id, model_id=args.model_id))
            else:
                print(json.dumps(validate_film_feedback(args.review_manifest, args.feedback),
                                 indent=2, sort_keys=True))
            return 0
        if args.command == "review-notes":
            if args.review_notes_action == "init":
                print(review_notes_template(
                    args.study_manifest, args.out, reviewer_kind=args.reviewer_kind,
                    reviewer_id=args.reviewer_id, model_id=args.model_id))
            else:
                print(json.dumps(validate_review_notes(
                    args.study_manifest, args.review_notes), indent=2, sort_keys=True))
            return 0
        if args.command == "catalog":
            entries = load_catalog(args.root)
            if args.catalog_action == "validate":
                print(json.dumps({"valid": True, "entryCount": len(entries)}, sort_keys=True))
            elif args.catalog_action == "search":
                print(json.dumps({"query": args.query, "results": search_catalog(
                    entries, args.query, args.limit)}, indent=2, sort_keys=True))
            else:
                destination = write_json_artifact(args.out, "catalog-index.json",
                                                  build_catalog_index(entries))
                print(str(destination))
            return 0
        if args.command == "analyze":
            manifest = run_analysis(
                args.source, args.out, seconds=args.max_seconds, thumbnails=args.thumbnails,
                motion=args.motion, roi=(tuple(args.box) if args.box is not None else None),
                roi_reseeds=_read_roi_reseeds(args.roi_reseeds),
                samples=args.max_samples, width=args.width, height=args.height,
                sparse_flow=args.sparse_flow, sparse_samples=args.sparse_samples,
                sparse_points=args.sparse_points, sparse_radius=args.sparse_radius,
                sparse_correlation=args.sparse_correlation,
                sparse_pyramid_levels=args.sparse_pyramid_levels,
                sparse_subpixel_refinement=args.sparse_subpixel_refinement,
                sparse_subpixel_reverse_check=args.sparse_subpixel_reverse_check,
                sparse_lk_refinement=args.sparse_lk_refinement,
                sparse_quadrant_consistency=args.sparse_quadrant_consistency,
                sparse_projective_hypotheses=args.sparse_projective_hypotheses,
                sparse_model_validation=args.sparse_model_validation,
                sparse_tracklet_motion_consistency=args.sparse_tracklet_motion_consistency,
                sparse_tracklet_appearance_consistency=args.sparse_tracklet_appearance_consistency,
                dense_flow=args.dense_flow, dense_samples=args.dense_samples,
                dense_grid_step=args.dense_grid_step,
                appearance=args.appearance, appearance_samples=args.appearance_samples,
                threshold=args.threshold, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
                rights_status=args.rights_status,
            )
            print(str(manifest))
            return 0
        if args.command == "propose-techniques":
            result = propose_techniques(args.analysis_run, args.catalog_root)
            if args.out is None:
                print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(str(write_json_artifact(args.out, "technique-proposals.json", result)))
            return 0
        if args.command == "review-techniques":
            result = build_technique_review(
                args.source, args.analysis_run, args.out,
                catalog_root=args.catalog_root, max_cues=args.max_cues,
                cue_offset=args.cue_offset,
                width=args.width, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
            )
            print(str(result))
            return 0
        if args.command == "shot-evidence":
            result = build_shot_evidence(args.analysis_run)
            if args.out is None:
                print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(str(write_json_artifact(args.out, "shot-evidence.json", result)))
            return 0
        if args.command == "edit-rhythm":
            result = build_edit_rhythm(args.analysis_run)
            if args.out is None:
                print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(str(write_json_artifact(args.out, "edit-rhythm.json", result)))
            return 0
        if args.command == "av-cut-evidence":
            result = build_av_cut_evidence(
                args.source, args.analysis_run, window_ms=args.window_ms,
                max_audio_frames=args.max_audio_frames, ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe)
            if args.out is None:
                print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(str(write_json_artifact(args.out, "av-cut-evidence.json", result)))
            return 0
        if args.command == "review-shots":
            print(build_shot_gallery(
                args.source, args.analysis_run, args.out,
                max_regions=args.max_regions, region_offset=args.region_offset,
                width=args.width, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe))
            return 0
        if args.command == "review-sparse-flow":
            print(build_sparse_flow_review(
                args.source, args.sparse_report, args.out,
                max_frames=args.max_frames, max_tracklets=args.max_tracklets,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe))
            return 0
        if args.command == "review-roi":
            print(build_roi_review(
                args.source, args.roi_report, args.out,
                max_frames=args.max_frames, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe))
            return 0
        if args.command == "review-timeline":
            print(build_timeline_view(
                args.source, args.analysis_run, args.out,
                window_ms=args.window_ms, max_audio_frames=args.max_audio_frames,
                onset_min_rise_db=args.onset_min_rise_db,
                onset_min_peak_dbfs=args.onset_min_peak_dbfs,
                onset_cooldown_ms=args.onset_cooldown_ms,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe))
            return 0
        if args.command == "study-reference":
            result = study_reference(
                args.source, args.out, catalog_root=args.catalog_root,
                seconds=args.max_seconds, thumbnails=args.thumbnails,
                max_cues=args.max_cues, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
                rights_status=args.rights_status,
            )
            print(str(result))
            return 0
        if args.command == "export-film-handoff":
            print(export_film_handoff(args.study_manifest, args.out,
                                      fps_num=args.fps_num, fps_den=args.fps_den))
            return 0
        if args.command == "compare-appearance":
            comparison = compare_appearance(
                args.reference_report, args.candidate_report,
                reference_anchor_ms=args.reference_anchor_ms,
                candidate_anchor_ms=args.candidate_anchor_ms,
                tolerance_ms=args.tolerance_ms, time_scale=args.time_scale,
            )
            if args.out is None:
                print(json.dumps(comparison, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(str(write_json_artifact(args.out, "appearance-comparison.json",
                                              comparison)))
            return 0
        if args.command == "compare-frames":
            index = build_frame_comparison(
                args.reference, args.candidate, args.out,
                reference_anchor_ms=args.reference_anchor_ms,
                candidate_anchor_ms=args.candidate_anchor_ms,
                tolerance_ms=args.tolerance_ms, time_scale=args.time_scale,
                seconds=args.max_seconds, samples=args.max_samples,
                width=args.width, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
                rights_status=args.rights_status,
            )
            print(str(index))
            return 0
        if args.command == "review-film-map":
            index = build_film_map_review(
                args.review_map, args.authored_film, args.source,
                args.render, args.out, seconds=args.max_seconds,
                width=args.width, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
            print(str(index))
            return 0
        if args.command == "contact-sheet":
            index = build_contact_sheet(
                args.source, args.out, seconds=args.max_seconds,
                limit=args.max_thumbnails, width=args.width, threshold=args.threshold,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, rights_status=args.rights_status,
            )
            print(str(index))
            return 0
        if args.command == "inspect":
            artifact = inspect_source(args.source, ffprobe=args.ffprobe,
                                      rights_status=args.rights_status)
            filename = "source-manifest.json"
        elif args.command == "frames":
            artifact = analyze_frame_timeline(args.source, seconds=args.max_seconds,
                                              ffprobe=args.ffprobe,
                                              rights_status=args.rights_status)
            filename = "frame-timeline.json"
        elif args.command == "motion":
            artifact = analyze_image_motion(
                args.source, seconds=args.max_seconds, max_samples=args.max_samples,
                width=args.width, height=args.height, threshold=args.threshold,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, rights_status=args.rights_status,
            )
            filename = "image-motion.json"
        elif args.command == "track-roi":
            artifact = analyze_roi_track(
                args.source, tuple(args.box), seconds=args.max_seconds,
                max_samples=args.max_samples, width=args.width, height=args.height,
                radius=args.radius, correlation=args.correlation, cut_threshold=args.threshold,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, rights_status=args.rights_status,
                reseeds=_read_roi_reseeds(args.reseeds),
            )
            filename = "roi-track.json"
        elif args.command == "sparse-flow":
            artifact = analyze_sparse_flow(
                args.source, seconds=args.max_seconds, max_samples=args.max_samples,
                width=args.width, height=args.height, max_points=args.max_points,
                radius=args.radius, correlation=args.correlation, threshold=args.threshold,
                pyramid_levels=args.pyramid_levels,
                subpixel_refinement=args.subpixel_refinement,
                subpixel_reverse_check=args.subpixel_reverse_check,
                lk_refinement=args.lk_refinement,
                quadrant_consistency=args.quadrant_consistency,
                projective_hypotheses=args.projective_hypotheses,
                model_validation=args.model_validation,
                tracklet_motion_consistency=args.tracklet_motion_consistency,
                tracklet_appearance_consistency=args.tracklet_appearance_consistency,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, rights_status=args.rights_status,
            )
            filename = "sparse-flow.json"
        elif args.command == "dense-flow":
            artifact = analyze_dense_flow(
                args.source, seconds=args.max_seconds, max_samples=args.max_samples,
                width=args.width, height=args.height, grid_step=args.grid_step,
                threshold=args.threshold, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
                rights_status=args.rights_status,
            )
            filename = "dense-flow.json"
        elif args.command == "appearance":
            artifact = analyze_appearance(
                args.source, seconds=args.max_seconds, max_samples=args.max_samples,
                width=args.width, height=args.height, threshold=args.threshold,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, rights_status=args.rights_status,
            )
            filename = "appearance.json"
        elif args.command == "audio-timeline":
            artifact = analyze_audio_timeline(
                args.source, seconds=args.max_seconds, max_frames=args.max_frames,
                ffprobe=args.ffprobe, rights_status=args.rights_status)
            filename = "audio-timeline.json"
        elif args.command == "audio-levels":
            artifact = analyze_audio_levels(
                args.source, seconds=args.max_seconds, max_frames=args.max_frames,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
                rights_status=args.rights_status)
            filename = "audio-levels.json"
        elif args.command == "audio-onsets":
            artifact = analyze_audio_onsets(
                args.source, seconds=args.max_seconds, max_frames=args.max_frames,
                min_rise_db=args.min_rise_db, min_peak_dbfs=args.min_peak_dbfs,
                cooldown_ms=args.cooldown_ms, ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe, rights_status=args.rights_status)
            filename = "audio-onsets.json"
        else:
            artifact = analyze_hard_cuts(args.source, seconds=args.max_seconds,
                                         threshold=args.threshold, ffmpeg=args.ffmpeg,
                                         ffprobe=args.ffprobe, rights_status=args.rights_status)
            filename = "shot-candidates.json"
        payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.out is None:
            sys.stdout.write(payload)
            return 0
        destination = write_json_artifact(args.out, filename, artifact)
        print(str(destination))
        return 0
    except (OSError, ValueError, ProbeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
