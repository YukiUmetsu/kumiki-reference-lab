"""Thin CLI for repeatable local analysis without optional neural dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.analyzers.appearance.analyze import analyze_appearance
from kumiki_reference_lab.analyzers.appearance.source_visual_probe import write_source_visual_probe
from kumiki_reference_lab.analyzers.audio.timeline import analyze_audio_timeline
from kumiki_reference_lab.analyzers.audio.levels import analyze_audio_levels
from kumiki_reference_lab.analyzers.audio.onsets import analyze_audio_onsets
from kumiki_reference_lab.analyzers.audio.av_cuts import build_av_cut_evidence
from kumiki_reference_lab.analyzers.comparison.appearance import compare_appearance
from kumiki_reference_lab.analyzers.comparison.dense_flow import compare_dense_flow_files
from kumiki_reference_lab.analyzers.comparison.frames import build_frame_comparison
from kumiki_reference_lab.analyzers.comparison.visual_cadence import (
    load_cadence_input, summarize_visual_cadence,
)
from kumiki_reference_lab.analyzers.techniques.propose import propose_techniques
from kumiki_reference_lab.analyzers.techniques.review import build_technique_review
from kumiki_reference_lab.analyzers.shots.evidence import build_shot_evidence
from kumiki_reference_lab.analyzers.shots.rhythm import build_edit_rhythm
from kumiki_reference_lab.analyzers.shots.timeline_view import build_timeline_view
from kumiki_reference_lab.analyzers.shots.gallery import build_shot_gallery
from kumiki_reference_lab.analyzers.media.contact_sheet import build_contact_sheet
from kumiki_reference_lab.analyzers.motion.analyze import analyze_image_motion
from kumiki_reference_lab.analyzers.motion.dense import analyze_dense_flow
from kumiki_reference_lab.analyzers.motion.dense_review import build_dense_flow_review
from kumiki_reference_lab.analyzers.motion.temporal_support import analyze_dense_temporal_support_file
from kumiki_reference_lab.analyzers.motion.annotation_evaluation import evaluate_dense_flow_annotations_files
from kumiki_reference_lab.analyzers.motion.sparse import analyze_sparse_flow
from kumiki_reference_lab.analyzers.motion.review import build_sparse_flow_review
from kumiki_reference_lab.analyzers.subjects.roi import analyze_roi_track
from kumiki_reference_lab.analyzers.subjects.review import build_roi_review
from kumiki_reference_lab.analyzers.media.timeline import analyze_frame_timeline
from kumiki_reference_lab.analyzers.shots.detect import analyze_hard_cuts
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.catalog.store import build_catalog_index, load_catalog, search_catalog
from kumiki_reference_lab.catalog.browser_observations import (
    load_browser_observations, search_browser_observations,
)
from kumiki_reference_lab.catalog.popular_videos import load_popular_videos, search_popular_videos
from kumiki_reference_lab.catalog.whatships_detail_enrich import enrich_whatships_details
from kumiki_reference_lab.pipeline.whatships_local_worker import run_whatships_local_analysis
from kumiki_reference_lab.pipeline.whatships_visual_backfill import backfill_whatships_visual_probes
from kumiki_reference_lab.catalog.whatships_media_bindings import (
    register_local_media, media_coverage, eligible_bound_media,
)
from kumiki_reference_lab.catalog.whatships_data_dashboard import write_whatships_browser
from kumiki_reference_lab.catalog.whatships_direct_measure import measure_whatships_to_repository
from kumiki_reference_lab.catalog.whatships_audio_measure import measure_whatships_audio_to_repository
from kumiki_reference_lab.catalog.whatships_ephemeral_acquire import acquire_and_measure_x_video
from kumiki_reference_lab.catalog.whatships_direct_measure_batch import measure_whatships_batch
from kumiki_reference_lab.catalog.whatships_research_summary import summarize_tracked_whatships_observations
from kumiki_reference_lab.catalog.whatships_analysis_store import (
    export_repository_analysis, validate_repository_analysis,
    sync_repository_analysis,
)
from kumiki_reference_lab.catalog.whatships_full_coverage import (
    refresh_full_whatships_catalog, summarize_full_snapshot, plan_full_snapshot,
)
from kumiki_reference_lab.catalog.video_sources import (
    get_source_reference, load_source_references, search_source_references,
    summarize_source_references,
)
from kumiki_reference_lab.catalog.directors_library import (
    collect_latest as collect_directors_library, fetch_public_page,
    load_snapshot as load_directors_snapshot, summarize_snapshot as summarize_directors_snapshot,
)
from kumiki_reference_lab.catalog.visual_styles import (
    load_visual_styles, search_visual_styles, style_family_counts,
)
from kumiki_reference_lab.catalog.open_footage import (
    load_open_footage, summarize_open_footage, verify_open_footage_media,
)
from kumiki_reference_lab.catalog.audience_benchmarks import (
    build_audience_insights, load_audience_benchmarks,
)
from kumiki_reference_lab.catalog.visual_study_plan import build_visual_study_plan
from kumiki_reference_lab.catalog.video_id_candidates import load_video_id_candidates
from kumiki_reference_lab.catalog.paired_visual_review import (
    compare_paired_visual_reviews, load_visual_study_bindings,
)
from kumiki_reference_lab.contracts.source import RIGHTS_STATUSES
from kumiki_reference_lab.core.artifacts import write_json_artifact
from kumiki_reference_lab.pipeline.analyze import run_analysis
from kumiki_reference_lab.pipeline.study import study_reference
from kumiki_reference_lab.pipeline.speech_transcribe import transcribe_local_video
from kumiki_reference_lab.pipeline.character_motion import run_character_motion
from kumiki_reference_lab.pipeline.subject_detections import run_subject_detections
from kumiki_reference_lab.pipeline.subject_tracklet_review import build_subject_tracklet_review
from kumiki_reference_lab.pipeline.ollama_character_perception import describe_local_characters
from kumiki_reference_lab.pipeline.ollama_subject_detection import detect_local_ollama_subjects
from kumiki_reference_lab.pipeline.local_character_study import run_local_character_study
from kumiki_reference_lab.pipeline.character_study_batch import run_character_study_batch
from kumiki_reference_lab.pipeline.subject_detection_benchmark import (
    run_subject_box_benchmark, create_subject_box_label_template,
)
from kumiki_reference_lab.pipeline.local_character_interactions import analyze_local_interactions
from kumiki_reference_lab.pipeline.interaction_review import (
    build_interaction_review, summarize_interaction_feedback,
)
from kumiki_reference_lab.pipeline.character_vision_review import (
    build_character_vision_review, summarize_character_vision_feedback,
)
from kumiki_reference_lab.pipeline.mac_vision_detection import detect_mac_vision_people
from kumiki_reference_lab.pipeline.speaker_association import associate_speakers
from kumiki_reference_lab.pipeline.character_speech_link import link_characters_to_speech
from kumiki_reference_lab.integrations.kumiki.film_handoff import export_film_handoff
from kumiki_reference_lab.integrations.kumiki.film_map_review import build_film_map_review
from kumiki_reference_lab.integrations.kumiki.film_feedback import (
    init_film_feedback, validate_film_feedback,
)
from kumiki_reference_lab.reviews.notes import review_notes_template, validate_review_notes
from kumiki_reference_lab.reviews.visual_events import load_visual_events, summarize_visual_events
from kumiki_reference_lab.reviews.character_scene import load_character_scene, summarize_character_scene
from kumiki_reference_lab.reviews.visual_style_timeline import (
    load_visual_style_timeline, summarize_visual_style_timeline,
)


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
    motion.add_argument("--start-seconds", type=int, default=0,
                        help="source-relative start offset; preserves original PTS, total prefix <= 120s")
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

    dense_review = commands.add_parser(
        "review-dense-flow", help="view source-PTS-verified dense grid motion evidence")
    dense_review.add_argument("source", type=Path)
    dense_review.add_argument("dense_report", type=Path)
    dense_review.add_argument("--out", type=Path, required=True)
    dense_review.add_argument("--max-frames", type=int, default=8)
    dense_review.add_argument("--ffmpeg", default="ffmpeg")
    dense_review.add_argument("--ffprobe", default="ffprobe")

    dense_support = commands.add_parser(
        "dense-temporal-support", help="inspect fixed-grid dense flow support changes, not occlusion")
    dense_support.add_argument("dense_report", type=Path)
    dense_support.add_argument("--out", type=Path,
                               help="write immutable dense-temporal-support.json to this directory")

    dense_evaluate = commands.add_parser(
        "evaluate-dense-flow", help="compare dense vectors to declared source-PTS grid annotations")
    dense_evaluate.add_argument("dense_report", type=Path)
    dense_evaluate.add_argument("annotations", type=Path)
    dense_evaluate.add_argument("--out", type=Path,
                                help="write immutable dense-flow-evaluation.json to this directory")

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
    appearance.add_argument("--start-seconds", type=int, default=0,
                            help="source-relative start offset; preserves original PTS, total prefix <= 120s")
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

    dense_comparison = commands.add_parser(
        "compare-dense-flow", help="compare two source-PTS-anchored image-plane flow reports")
    dense_comparison.add_argument("reference_report", type=Path)
    dense_comparison.add_argument("candidate_report", type=Path)
    dense_comparison.add_argument("--reference-anchor-ms", type=int, required=True)
    dense_comparison.add_argument("--candidate-anchor-ms", type=int, required=True)
    dense_comparison.add_argument("--tolerance-ms", type=int, default=150)
    dense_comparison.add_argument("--time-scale", default="1")
    dense_comparison.add_argument("--out", type=Path)

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

    popular = commands.add_parser("video-references", help="browse evidence-linked popular films across research cohorts")
    popular_actions = popular.add_subparsers(dest="popular_action", required=True)
    for action in ("validate", "list", "search"):
        sub = popular_actions.add_parser(action)
        sub.add_argument("--root", type=Path, default=Path("research"),
                         help="research cohort directory or one versioned metadata JSON file")
        if action in ("list", "search"):
            sub.add_argument("--min-views", type=int, default=0)
            sub.add_argument("--limit", type=int, default=20)
        if action == "search":
            sub.add_argument("query", help="technique, story goal, title or creator")
    backfill_ws = commands.add_parser(
        "whatships-visual-backfill",
        help="checkpoint real source-PTS RGB/cut probes for completed private What Ships character studies")
    backfill_ws.add_argument("bindings", type=Path, help="PRIVATE media-bindings.json")
    backfill_ws.add_argument("analysis_index", type=Path, help="PRIVATE prior character analysis-index.json")
    backfill_ws.add_argument("--snapshot", type=Path,
                             default=Path("research/whatships-index-2026-11-10.json"))
    backfill_ws.add_argument("--out", type=Path, required=True,
                             help="new private visual probe run directory")
    backfill_ws.add_argument("--previous-index", type=Path,
                             help="prior PRIVATE visual-index.json for resuming")
    backfill_ws.add_argument("--max-videos", type=int, default=1)
    backfill_ws.add_argument("--start-offset", type=int, default=0)
    backfill_ws.add_argument("--max-samples", type=int, default=12)
    backfill_ws.add_argument("--width", type=int, default=160)
    backfill_ws.add_argument("--height", type=int, default=90)
    backfill_ws.add_argument("--cut-threshold", type=float, default=0.25)
    backfill_ws.add_argument("--ffmpeg", default="ffmpeg")
    backfill_ws.add_argument("--ffprobe", default="ffprobe")

    visual_probe = commands.add_parser(
        "source-visual-probe",
        help="measure source-PTS cut, display brightness/color and frame-change proxies on local video")
    visual_probe.add_argument("source", type=Path, help="authorized local video")
    visual_probe.add_argument("--out", type=Path, required=True)
    visual_probe.add_argument("--start-seconds", type=int, default=0)
    visual_probe.add_argument("--max-seconds", type=int, default=10)
    visual_probe.add_argument("--max-samples", type=int, default=12)
    visual_probe.add_argument("--width", type=int, default=160)
    visual_probe.add_argument("--height", type=int, default=90)
    visual_probe.add_argument("--cut-threshold", type=float, default=0.25)
    visual_probe.add_argument("--image-translation", action="store_true",
                              help="optional NumPy FFT image-plane shift proxy (not camera motion)")
    visual_probe.add_argument("--ffmpeg", default="ffmpeg")
    visual_probe.add_argument("--ffprobe", default="ffprobe")
    visual_probe.add_argument("--rights-status", choices=RIGHTS_STATUSES,
                              default="review-required")

    batch_measure = commands.add_parser(
        "whatships-measure-batch",
        help="measure several operator-bound videos, checkpointing real original-PTS results in Git")
    batch_measure.add_argument("bindings", type=Path, help="private authorized media-bindings.json")
    batch_measure.add_argument("--snapshot", type=Path,
        default=Path("research/whatships-index-2026-11-10.json"))
    batch_measure.add_argument("--repository-root", type=Path,
        default=Path("research/analysis/whatships"))
    batch_measure.add_argument("--max-videos", type=int, default=2)
    batch_measure.add_argument("--start-offset", type=int, default=0)
    batch_measure.add_argument("--category", choices=(
        "ai","developer-tools","design","motion","productivity",
        "consumer","hardware","other"))
    batch_measure.add_argument("--window-seconds", type=int, default=10)
    batch_measure.add_argument("--window-count", type=int, default=4)
    batch_measure.add_argument("--max-samples", type=int, default=12)
    batch_measure.add_argument("--width", type=int, default=160)
    batch_measure.add_argument("--height", type=int, default=90)
    batch_measure.add_argument("--cut-threshold", type=float, default=.25)
    batch_measure.add_argument("--image-translation", action="store_true",
                              help="optional NumPy FFT apparent image-plane motion")
    batch_measure.add_argument("--ffmpeg", default="ffmpeg")
    batch_measure.add_argument("--ffprobe", default="ffprobe")
    acquire_ws = commands.add_parser(
        "whatships-acquire-measure",
        help="opt-in ephemeral public X original-video acquisition and source-PTS research persistence")
    acquire_ws.add_argument("source_id", help="What Ships source ID with enriched original X post")
    acquire_ws.add_argument("--snapshot", type=Path,
        default=Path("research/whatships-index-2026-11-10.json"))
    acquire_ws.add_argument("--repository-root", type=Path,
        default=Path("research/analysis/whatships"))
    acquire_ws.add_argument("--rights-basis", required=True,
        choices=("own-original-work","written-permission",
                 "permissive-license","other-lawful-authorization"))
    acquire_ws.add_argument("--rights-note", required=True,
        help="specific legal basis, kept temporarily and never committed to Git")
    acquire_ws.add_argument("--identity-note", required=True,
        help="operator evidence the original X video matches this exact catalog entry")
    acquire_ws.add_argument("--acknowledge-rights", action="store_true")
    acquire_ws.add_argument("--yt-dlp", default="yt-dlp")
    acquire_ws.add_argument("--timeout-seconds", type=int, default=240)
    acquire_ws.add_argument("--window-seconds", type=int, default=10)
    acquire_ws.add_argument("--window-count", type=int, default=4)
    acquire_ws.add_argument("--max-samples", type=int, default=12)
    acquire_ws.add_argument("--image-translation", action="store_true",
                            help="optional NumPy FFT apparent image-plane motion")
    acquire_ws.add_argument("--ffmpeg", default="ffmpeg")
    acquire_ws.add_argument("--ffprobe", default="ffprobe")

    audio_ws = commands.add_parser(
        "whatships-audio-measure",
        help="measure bounded local video PCM energy/silence and save numeric evidence in Git")
    audio_ws.add_argument("bindings", type=Path, help="PRIVATE authorized media binding ledger")
    audio_ws.add_argument("source_id", help="exact whatships:slug")
    audio_ws.add_argument("--snapshot", type=Path,
        default=Path("research/whatships-index-2026-11-10.json"))
    audio_ws.add_argument("--repository-root", type=Path,
        default=Path("research/analysis/whatships"))
    audio_ws.add_argument("--window-seconds", type=int, default=10)
    audio_ws.add_argument("--window-count", type=int, default=4)
    audio_ws.add_argument("--replace-existing", action="store_true")
    audio_ws.add_argument("--ffmpeg", default="ffmpeg")
    audio_ws.add_argument("--ffprobe", default="ffprobe")

    measure_ws = commands.add_parser(
        "whatships-measure",
        help="measure bound local source frames and sync actual PTS observations straight to Git research JSON")
    measure_ws.add_argument("bindings", type=Path, help="private authorized media-bindings.json")
    measure_ws.add_argument("source_id", help="one exact whatships:slug")
    measure_ws.add_argument("--snapshot", type=Path,
        default=Path("research/whatships-index-2026-11-10.json"))
    measure_ws.add_argument("--repository-root", type=Path,
        default=Path("research/analysis/whatships"),
        help="version-controlled canonical per-video research data directory")
    measure_ws.add_argument("--window-seconds", type=int, default=10)
    measure_ws.add_argument("--window-count", type=int, default=4)
    measure_ws.add_argument("--max-samples", type=int, default=12)
    measure_ws.add_argument("--width", type=int, default=160)
    measure_ws.add_argument("--height", type=int, default=90)
    measure_ws.add_argument("--cut-threshold", type=float, default=.25)
    measure_ws.add_argument("--image-translation", action="store_true",
                            help="measure original-PTS apparent global image translation with optional NumPy")
    measure_ws.add_argument("--replace-existing", action="store_true",
        help="explicitly replace prior numeric video evidence for this source")
    measure_ws.add_argument("--fill-gaps", action="store_true",
        help="sample previously unmeasured source-time windows and append to existing numeric evidence")
    measure_ws.add_argument("--ffmpeg", default="ffmpeg")
    measure_ws.add_argument("--ffprobe", default="ffprobe")

    analyze_ws = commands.add_parser(
        "whatships-analyze",
        help="checkpoint a bounded, source-SHA-verified local analysis batch for bound What Ships videos")
    analyze_ws.add_argument("bindings", type=Path, help="private media-bindings.json")
    analyze_ws.add_argument("--snapshot", type=Path,
                            default=Path("research/whatships-index-2026-11-10.json"))
    analyze_ws.add_argument("--out", type=Path, required=True,
                            help="new private output directory with per-video checkpoints")
    analyze_ws.add_argument("--model", required=True, help="installed local Ollama vision model tag")
    analyze_ws.add_argument("--previous-index", type=Path,
                            help="previous PRIVATE analysis-index.json for cross-batch resumption")
    analyze_ws.add_argument("--source-id", help="optional exact whatships:slug to process")
    analyze_ws.add_argument("--max-videos", type=int, default=1)
    analyze_ws.add_argument("--start-offset", type=int, default=0)
    analyze_ws.add_argument("--detector", choices=("ollama", "apple-vision"), default="ollama")
    analyze_ws.add_argument("--window-seconds", type=int, default=10)
    analyze_ws.add_argument("--window-count", type=int, default=2)
    analyze_ws.add_argument("--max-samples", type=int, default=6)
    analyze_ws.add_argument("--max-calls", type=int, default=6)
    analyze_ws.add_argument("--max-pairs", type=int, default=2)
    analyze_ws.add_argument("--width", type=int, default=320)
    analyze_ws.add_argument("--height", type=int, default=180)
    analyze_ws.add_argument("--port", type=int, default=11434)
    analyze_ws.add_argument("--timeout-seconds", type=int, default=180)
    analyze_ws.add_argument("--skip-qa", action="store_true")
    analyze_ws.add_argument("--skip-interactions", action="store_true")
    analyze_ws.add_argument("--ffmpeg", default="ffmpeg")
    analyze_ws.add_argument("--ffprobe", default="ffprobe")

    media_ws = commands.add_parser(
        "whatships-media",
        help="privately bind authorized local footage to exact What Ships catalog identities")
    media_actions = media_ws.add_subparsers(dest="media_action", required=True)
    bind = media_actions.add_parser(
        "bind", help="operator-attest one exact What Ships entry and one hashed local video")
    bind.add_argument("source_id", help="exact ID such as whatships:paper-mono-code")
    bind.add_argument("video", type=Path, help="already authorized local video, never a watch URL")
    bind.add_argument("--snapshot", type=Path,
                      default=Path("research/whatships-index-2026-11-10.json"))
    bind.add_argument("--previous", type=Path,
                      help="existing PRIVATE bindings JSON; immutable copy-on-write")
    bind.add_argument("--rights-basis", required=True, choices=(
        "own-original-work", "written-permission",
        "permissive-license", "other-lawful-authorization"))
    bind.add_argument("--rights-note", required=True,
                      help="rights provenance: license, permission or original work")
    bind.add_argument("--identity-note", required=True,
                      help="why this exact local video matches the catalog watch page")
    bind.add_argument("--acknowledge-rights", action="store_true",
                      help="affirm rights and source identity are operator-asserted, not independently verified")
    bind.add_argument("--out", type=Path, required=True,
                      help="new private directory; never commit media-bindings.json")
    bind.add_argument("--ffprobe", default="ffprobe")

    media_report = media_actions.add_parser("report",
        help="redacted count of source-linked local footage and analysis gaps")
    media_report.add_argument("--snapshot", type=Path,
                              default=Path("research/whatships-index-2026-11-10.json"))
    media_report.add_argument("bindings", type=Path, help="private media-bindings.json")
    media_report.add_argument("--verify-files", action="store_true",
                              help="rehash all bound files (can be expensive)")

    media_queue = media_actions.add_parser("queue",
        help="SHA-verify the private local-media ledger and print a path-redacted eligible queue")
    media_queue.add_argument("bindings", type=Path, help="private media-bindings.json")
    media_queue.add_argument("--snapshot", type=Path,
                             default=Path("research/whatships-index-2026-11-10.json"))
    media_queue.add_argument("--limit", type=int, default=20)

    full_ws = commands.add_parser(
        "whatships-all",
        help="maintain all What Ships video metadata, audit gaps and plan a fair backlog")
    full_actions = full_ws.add_subparsers(dest="whatships_action", required=True)
    refresh = full_actions.add_parser(
        "refresh", help="fetch the official public index once and create an immutable full snapshot")
    refresh.add_argument("--previous", type=Path,
                         default=Path("research/whatships-index-2026-11-10.json"))
    refresh.add_argument("--index-file", type=Path,
                         help="optional locally supplied official index JSON, for offline refresh")
    refresh.add_argument("--out", type=Path, required=True, help="new output directory")
    refresh.add_argument("--timeout", type=int, default=25)
    refresh.add_argument("--retrieved-on", help="explicit ISO snapshot date (for deterministic offline runs)")

    enrich = full_actions.add_parser(
        "enrich", help="resumable bounded missing-detail enrichment using official read-only MCP")
    enrich.add_argument("--previous", type=Path,
                        default=Path("research/whatships-index-2026-11-10.json"))
    enrich.add_argument("--out", type=Path, required=True, help="new immutable output directory")
    enrich.add_argument("--max-details", type=int, default=25)
    enrich.add_argument("--start-offset", type=int, default=0,
                        help="skip failed metadata queue entries without dropping them")
    enrich.add_argument("--delay-seconds", type=float, default=1.5,
                        help="minimum delay between live metadata calls")
    enrich.add_argument("--timeout", type=int, default=25)
    enrich.add_argument("--offline-responses", type=Path,
                        help="optional offline exact slug-to-MCP-response fixture JSON")
    research = full_actions.add_parser(
        "research-report", help="summarize only Git-tracked video observations and numeric source frames")
    research.add_argument("--snapshot", type=Path,
        default=Path("research/whatships-index-2026-11-10.json"))
    research.add_argument("--root", type=Path,
        default=Path("research/analysis/whatships"))
    browse = full_actions.add_parser(
        "browse", help="generate offline searchable HTML, CSV and JSON for all indexed videos")
    browse.add_argument("--snapshot", type=Path,
                        default=Path("research/whatships-index-2026-11-10.json"))
    browse.add_argument("--out", type=Path, required=True, help="new output directory")
    browse.add_argument("--bindings", type=Path,
                        help="optional private source bindings for operator-asserted coverage")
    browse.add_argument("--analysis-index", type=Path,
                        help="optional private verified character study index (requires bindings)")
    browse.add_argument("--visual-index", type=Path,
                        help="optional private verified RGB/cut index (requires analysis index)")
    browse.add_argument("--repository-analysis", type=Path,
                        default=Path("research/analysis/whatships"),
                        help="Git-tracked per-video evidence records (default canonical research corpus)")
    browse.add_argument("--no-repository-analysis", action="store_true",
                        help="show only catalog/private local analysis, without committed research notes")

    analysis_export = full_actions.add_parser(
        "export-analysis",
        help="export actual observations and source-PTS numerical timelines as Git-trackable per-video JSON")
    analysis_export.add_argument("--snapshot", type=Path,
                        default=Path("research/whatships-index-2026-11-10.json"))
    analysis_export.add_argument("--observations", type=Path,
                        help="optional existing browser spot checks JSON, including un-timed visual notes")
    analysis_export.add_argument("--bindings", type=Path,
                        help="optional PRIVATE media bindings (never included in exported files)")
    analysis_export.add_argument("--analysis-index", type=Path,
                        help="optional PRIVATE character model study index")
    analysis_export.add_argument("--visual-index", type=Path,
                        help="optional PRIVATE source-PTS numeric visual index")
    analysis_export.add_argument("--out", type=Path, required=True,
                        help="new git-ready directory, e.g. research/analysis/whatships-next")
    analysis_sync = full_actions.add_parser(
        "sync-analysis",
        help="merge a verified export into the tracked per-video research corpus without deleting existing evidence")
    analysis_sync.add_argument("--snapshot", type=Path,
        default=Path("research/whatships-index-2026-11-10.json"))
    analysis_sync.add_argument("--incoming", type=Path, required=True,
        help="new Git-ready export-analysis directory")
    analysis_sync.add_argument("--root", type=Path,
        default=Path("research/analysis/whatships"),
        help="tracked per-video analysis dataset to update in this Git worktree")
    analysis_sync.add_argument("--replace-existing", action="store_true",
        help="explicitly replace conflicting evidence; Git history retains prior revisions")
    analysis_sync.add_argument("--append-numeric-windows", action="store_true",
        help="merge nonoverlapping source-PTS sample windows; incompatible with --replace-existing")
    analysis_validate = full_actions.add_parser(
        "validate-analysis",
        help="verify committed per-video analysis dataset against its source snapshot")
    analysis_validate.add_argument("--snapshot", type=Path,
                        default=Path("research/whatships-index-2026-11-10.json"))
    analysis_validate.add_argument("--root", type=Path,
                        default=Path("research/analysis/whatships"))
    report = full_actions.add_parser("report", help="count all indexed videos and evidence gaps")
    report.add_argument("--snapshot", type=Path,
                        default=Path("research/whatships-index-2026-11-10.json"))

    queue = full_actions.add_parser("queue", help="list all remaining metadata and media-source needs")
    queue.add_argument("--snapshot", type=Path,
                       default=Path("research/whatships-index-2026-11-10.json"))
    queue.add_argument("--limit", type=int, default=50,
                       help="maximum visible rows; 10000 to request complete queue")
    queue.add_argument("--category",
                       choices=("ai", "developer-tools", "design", "motion",
                                "productivity", "consumer", "hardware", "other"))
    queue.add_argument("--missing-detail-only", action="store_true")
    directors = commands.add_parser(
        "directors-library", help="index Directors' Library film-page metadata without downloading media")
    directors_actions = directors.add_subparsers(dest="directors_action", required=True)
    directors_snapshot = directors_actions.add_parser("snapshot")
    directors_snapshot.add_argument("--pages", type=int, default=2,
                                    help="bounded number of latest-archive pages, 1–5")
    directors_snapshot.add_argument("--retrieved-on", default=None,
                                    help="explicit ISO snapshot date, default today (UTC)")
    directors_snapshot.add_argument("--out", type=Path, required=True,
                                    help="new immutable .json file under research/analysis/")
    for action in ("validate", "report"):
        sub = directors_actions.add_parser(action)
        sub.add_argument("--snapshot", type=Path,
                         default=Path("research/analysis/directors-library/index-2026-11-11.json"))
    sources = commands.add_parser(
        "video-sources", help="browse normalized YouTube and What Ships references without media downloads")
    source_actions = sources.add_subparsers(dest="source_action", required=True)
    for action in ("validate", "list", "search", "show", "report", "observations"):
        sub = source_actions.add_parser(action)
        sub.add_argument("--youtube-root", type=Path, default=Path("research"))
        sub.add_argument("--whatships", type=Path,
                         default=Path("research/whatships-index-2026-11-10.json"))
        if action in ("list", "search"):
            sub.add_argument("--provider", choices=("all", "youtube", "whatships"), default="all")
            sub.add_argument("--min-views", type=int, default=0)
            sub.add_argument("--limit", type=int, default=20)
        if action == "search":
            sub.add_argument("query", help="title, creator, category, tags, or source description")
        if action == "show":
            sub.add_argument("identity", help="provider-qualified ID, e.g. whatships:figma-3980")
        if action == "observations":
            sub.add_argument("--observations", type=Path,
                             default=Path("research/whatships-browser-observations-2026-11-10.json"))
            sub.add_argument("--source-id", default="", help="optional provider-qualified video ID")
            sub.add_argument("--visual-tag", default="", help="observed style or presentation tag")
    audience = commands.add_parser("audience-benchmarks", help="analyze recent-upload audience metadata without video downloads")
    audience_actions = audience.add_subparsers(dest="audience_action", required=True)
    for action in ("validate", "report", "study-plan", "compare-visual"):
        sub = audience_actions.add_parser(action)
        sub.add_argument("--root", type=Path, default=Path("research/audience-recent-uploads.v1.json"),
                         help="versioned local recent-upload audience snapshot")
        if action == "report":
            sub.add_argument("--min-comparison-count", type=int, default=5,
                             help="minimum observations per side of an age-matched duration contrast")
        if action == "study-plan":
            sub.add_argument("--out", type=Path, help="optional immutable study-plan artifact directory")
            sub.add_argument("--pairs-per-channel", type=int, default=3)
            sub.add_argument("--max-source-age-gap-days", type=int, default=45)
            sub.add_argument("--max-runtime-ratio", type=float, default=1.75)
            sub.add_argument("--min-view-ratio", type=float, default=2.0)
            sub.add_argument("--identity-candidates", type=Path,
                             help="optional audited exact-row YouTube index candidates, never inferred by title")
        if action == "compare-visual":
            sub.add_argument("--identity-candidates", type=Path, required=True)
            sub.add_argument("--pair-id", required=True)
            sub.add_argument("--bindings", type=Path, required=True,
                             help="self-declared source-row/YouTube-ID/local-media SHA bindings")
            sub.add_argument("--higher-review", type=Path, required=True)
            sub.add_argument("--lower-review", type=Path, required=True)
            sub.add_argument("--out", type=Path,
                             help="optional directory for immutable paired-visual-review.json")
    cadence = commands.add_parser(
        "visual-cadence", help="summarize sampled image-motion, cut and display-luma proxy rates")
    cadence.add_argument("motion_report", type=Path)
    cadence.add_argument("appearance_report", type=Path)
    cadence.add_argument("--image-motion-threshold", type=float, default=0.01,
                         help="normalized image displacement per second (not camera velocity)")
    cadence.add_argument("--luma-change-threshold", type=float, default=0.05,
                         help="absolute display Y-prime proxy change per second (not lighting)")
    styles = commands.add_parser("visual-styles", help="search source-attributed styles and camera/lighting study questions")
    style_actions = styles.add_subparsers(dest="style_action", required=True)
    for action in ("validate", "list", "search"):
        sub = style_actions.add_parser(action)
        sub.add_argument("--root", type=Path, default=Path("research/visual-styles.v1.json"))
        if action != "validate":
            sub.add_argument("--family", help="exact visual style family, e.g. paper-and-collage")
            sub.add_argument("--limit", type=int, default=20)
        if action == "search":
            sub.add_argument("query")
    open_media = commands.add_parser(
        "open-footage", help="validate and locally verify source-hashed real reference video samples")
    open_media_actions = open_media.add_subparsers(dest="open_footage_action", required=True)
    for action in ("validate", "list", "summarize", "verify-local"):
        sub = open_media_actions.add_parser(action)
        sub.add_argument("--root", type=Path,
                         default=Path("research/open-footage-calibration.v1.json"))
        if action == "verify-local":
            sub.add_argument("--media-root", type=Path, required=True)
            sub.add_argument("--id", help="optionally check only one reference ID")
            sub.add_argument("--ffprobe", default="ffprobe")
    events = commands.add_parser("visual-events", help="summarize explicitly reviewed camera and lighting events")
    event_actions = events.add_subparsers(dest="event_action", required=True)
    for action in ("validate", "report"):
        sub = event_actions.add_parser(action)
        sub.add_argument("review_file", type=Path)
    style_timeline = commands.add_parser(
        "visual-style-review", help="validate or summarize footage-grounded visual style intervals")
    style_review_actions = style_timeline.add_subparsers(dest="style_review_action", required=True)
    for action in ("validate", "report"):
        sub = style_review_actions.add_parser(action)
        sub.add_argument("review_file", type=Path)
    character_speaker = commands.add_parser(
        "speech-link-characters",
        help="link individual utterances to visible characters only with explicit PTS lip-motion evidence")
    character_speaker.add_argument("speech_scene", type=Path)
    character_speaker.add_argument("visual_scene", type=Path)
    character_speaker.add_argument("link_review", type=Path)
    character_speaker.add_argument("--out", type=Path, required=True)
    speaker_join = commands.add_parser(
        "speech-associate", help="offline join of diarization RTTM voice clusters to local ASR segments")
    speaker_join.add_argument("speech_run", type=Path,
                              help="output directory from speech-transcribe")
    speaker_join.add_argument("rttm", type=Path,
                              help="RTTM from a separately run local diarizer on the same audio")
    speaker_join.add_argument("--out", type=Path, required=True)
    speaker_join.add_argument("--min-coverage", type=float, default=0.80)
    speaker_join.add_argument("--max-competing", type=float, default=0.10)
    asr = commands.add_parser(
        "speech-transcribe", help="optional local whisper.cpp ASR to unattributed character-scene dialogue")
    asr.add_argument("source", type=Path, help="authorized local video file")
    asr.add_argument("--model", type=Path, required=True, help="existing local whisper.cpp model file")
    asr.add_argument("--out", type=Path, required=True, help="new directory for source-bound JSON")
    asr.add_argument("--whisper-cli", default="whisper-cli")
    asr.add_argument("--ffmpeg", default="ffmpeg")
    asr.add_argument("--ffprobe", default="ffprobe")
    asr.add_argument("--max-seconds", type=int, default=30)
    asr.add_argument("--timeout-seconds", type=int, default=600)
    asr.add_argument("--language", default="auto")
    asr.add_argument("--retain-audio", action="store_true",
                     help="retain hashed decoded WAV so an offline diarizer can use identical audio")
    asr.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")
    character_qa = commands.add_parser(
        "review-character-vision",
        help="render actual frames and subject crops for human QA of local VLM proposals")
    character_qa.add_argument("source", type=Path)
    character_qa.add_argument("report", type=Path, help="subject-tracklets.json")
    character_qa.add_argument("vision_run", type=Path, help="local-character-vision output directory")
    character_qa.add_argument("--out", type=Path, required=True, help="new review gallery directory")
    character_qa.add_argument("--scan-seconds", type=int, default=20)
    character_qa.add_argument("--width", type=int, default=320)
    character_qa.add_argument("--height", type=int, default=180)
    character_qa.add_argument("--ffmpeg", default="ffmpeg")
    character_qa.add_argument("--ffprobe", default="ffprobe")

    character_feedback = commands.add_parser(
        "character-vision-feedback",
        help="report human support/rejection verdicts on a source-bound VLM review")
    character_feedback.add_argument("feedback", type=Path, help="filled review-feedback.json")
    character_feedback.add_argument("vision_manifest", type=Path, help="original character-vision.json")
    interaction_qa = commands.add_parser(
        "review-character-interactions",
        help="replay original source PTS frames and red/cyan pair boxes for human interaction review")
    interaction_qa.add_argument("source", type=Path)
    interaction_qa.add_argument("report", type=Path, help="subject-tracklets.json")
    interaction_qa.add_argument("vision_run", type=Path, help="local-character-vision output")
    interaction_qa.add_argument("interaction_run", type=Path, help="local-character-interactions output")
    interaction_qa.add_argument("--out", type=Path, required=True, help="new offline gallery")
    interaction_qa.add_argument("--ffprobe", default="ffprobe")
    interaction_qa.add_argument("--ffmpeg", default="ffmpeg")

    interaction_feedback = commands.add_parser(
        "character-interaction-feedback",
        help="summarize explicit human verdicts on local model pairwise interactions")
    interaction_feedback.add_argument("feedback", type=Path, help="interaction-feedback.json")
    interaction_feedback.add_argument("interaction_manifest", type=Path, help="character-interactions.json")
    interactions = commands.add_parser(
        "local-character-interactions",
        help="propose uncertain actor-target motion from two source-PTS-verified frames with local Ollama")
    interactions.add_argument("source", type=Path)
    interactions.add_argument("report", type=Path, help="subject-tracklets.json")
    interactions.add_argument("vision_run", type=Path, help="local-character-vision output directory")
    interactions.add_argument("--out", type=Path, required=True, help="new output directory")
    interactions.add_argument("--model", required=True, help="already installed local Ollama vision model")
    interactions.add_argument("--port", type=int, default=11434)
    interactions.add_argument("--max-pairs", type=int, default=6)
    interactions.add_argument("--gap-seconds", type=int, default=3)
    interactions.add_argument("--scan-seconds", type=int, default=20)
    interactions.add_argument("--timeout-seconds", type=int, default=180)
    interactions.add_argument("--width", type=int, default=320)
    interactions.add_argument("--height", type=int, default=180)
    interactions.add_argument("--ffmpeg", default="ffmpeg")
    interactions.add_argument("--ffprobe", default="ffprobe")
    label_template = commands.add_parser(
        "character-labels-template",
        help="create an unapproved exhaustive human-labeling skeleton for sampled detections")
    label_template.add_argument("detections", type=Path)
    label_template.add_argument("--out", type=Path, required=True, help="new pending label JSON")
    box_benchmark = commands.add_parser(
        "evaluate-character-detections",
        help="compare source-PTS character boxes with exhaustive human-labeled sample frames")
    box_benchmark.add_argument("source", type=Path)
    box_benchmark.add_argument("detections", type=Path, help="subject-detections JSON")
    box_benchmark.add_argument("ground_truth", type=Path, help="human-labeled source-PTS JSON")
    box_benchmark.add_argument("--out", type=Path, required=True)
    box_benchmark.add_argument("--min-iou", type=float, default=0.5)
    box_benchmark.add_argument("--ffprobe", default="ffprobe")
    study_batch = commands.add_parser(
        "character-study-batch",
        help="independently analyze 1–6 original-PTS video windows in an atomic local batch")
    study_batch.add_argument("source", type=Path, help="authorized local reference video")
    study_batch.add_argument("--out", type=Path, required=True, help="new immutable batch directory")
    study_batch.add_argument("--model", required=True, help="installed local Ollama vision model")
    study_batch.add_argument("--detector", choices=("ollama", "apple-vision"), default="ollama")
    study_batch.add_argument("--start-seconds", type=int, default=0)
    study_batch.add_argument("--window-seconds", type=int, default=10)
    study_batch.add_argument("--stride-seconds", type=int,
                             help="interval between window starts, at least window duration")
    study_batch.add_argument("--window-count", type=int, default=3)
    study_batch.add_argument("--max-samples", type=int, default=8)
    study_batch.add_argument("--max-calls", type=int, default=8)
    study_batch.add_argument("--max-pairs", type=int, default=3)
    study_batch.add_argument("--port", type=int, default=11434)
    study_batch.add_argument("--timeout-seconds", type=int, default=180)
    study_batch.add_argument("--width", type=int, default=320)
    study_batch.add_argument("--height", type=int, default=180)
    study_batch.add_argument("--skip-qa", action="store_true")
    study_batch.add_argument("--skip-interactions", action="store_true")
    study_batch.add_argument("--ffmpeg", default="ffmpeg")
    study_batch.add_argument("--ffprobe", default="ffprobe")
    study_batch.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")

    study_local = commands.add_parser(
        "character-study-local",
        help="one-command bounded local character detection, tracking, VLM observations and QA")
    study_local.add_argument("source", type=Path, help="authorized local video")
    study_local.add_argument("--out", type=Path, required=True, help="new immutable study directory")
    study_local.add_argument("--model", required=True, help="already installed local Ollama vision model")
    study_local.add_argument("--detector", choices=("ollama", "apple-vision"), default="ollama")
    study_local.add_argument("--port", type=int, default=11434)
    study_local.add_argument("--max-seconds", type=int, default=10)
    study_local.add_argument("--start-seconds", type=int, default=0,
                              help="source-relative window offset (prefix must stay <= 120s)")
    study_local.add_argument("--max-samples", type=int, default=8)
    study_local.add_argument("--max-calls", type=int, default=12)
    study_local.add_argument("--max-pairs", type=int, default=6)
    study_local.add_argument("--timeout-seconds", type=int, default=180)
    study_local.add_argument("--width", type=int, default=320)
    study_local.add_argument("--height", type=int, default=180)
    study_local.add_argument("--skip-qa", action="store_true")
    study_local.add_argument("--skip-interactions", action="store_true")
    study_local.add_argument("--ffmpeg", default="ffmpeg")
    study_local.add_argument("--ffprobe", default="ffprobe")
    study_local.add_argument("--rights-status", choices=RIGHTS_STATUSES, default="review-required")
    local_subjects = commands.add_parser(
        "local-character-detect",
        help="propose human, animated and animal subject boxes with already installed local Ollama vision model")
    local_subjects.add_argument("source", type=Path, help="authorized local reference video")
    local_subjects.add_argument("--out", type=Path, required=True, help="new subject detection JSON")
    local_subjects.add_argument("--model", required=True, help="locally installed Ollama vision model")
    local_subjects.add_argument("--port", type=int, default=11434)
    local_subjects.add_argument("--max-seconds", type=int, default=10)
    local_subjects.add_argument("--start-seconds", type=int, default=0,
                              help="source-relative window offset (prefix must stay <= 120s)")
    local_subjects.add_argument("--max-samples", type=int, default=8)
    local_subjects.add_argument("--width", type=int, default=320)
    local_subjects.add_argument("--height", type=int, default=180)
    local_subjects.add_argument("--threshold", type=float, default=0.25)
    local_subjects.add_argument("--timeout-seconds", type=int, default=180)
    local_subjects.add_argument("--ffmpeg", default="ffmpeg")
    local_subjects.add_argument("--ffprobe", default="ffprobe")
    local_subjects.add_argument("--rights-status", choices=RIGHTS_STATUSES,
                                default="review-required")
    local_vision = commands.add_parser(
        "local-character-vision",
        help="describe visual subject crops and two-frame motion using a local Ollama vision model")
    local_vision.add_argument("source", type=Path, help="authorized local video")
    local_vision.add_argument("report", type=Path, help="subject-tracklets.json")
    local_vision.add_argument("--out", type=Path, required=True, help="new output directory")
    local_vision.add_argument("--model", required=True, help="already installed Ollama vision model")
    local_vision.add_argument("--port", type=int, default=11434,
                              help="local 127.0.0.1 Ollama port (no remote endpoint)")
    local_vision.add_argument("--max-frames", type=int, default=6)
    local_vision.add_argument("--max-calls", type=int, default=12)
    local_vision.add_argument("--scan-seconds", type=int, default=20)
    local_vision.add_argument("--max-pair-gap-seconds", type=int, default=3)
    local_vision.add_argument("--timeout-seconds", type=int, default=180)
    local_vision.add_argument("--width", type=int, default=320)
    local_vision.add_argument("--height", type=int, default=180)
    local_vision.add_argument("--ffmpeg", default="ffmpeg")
    local_vision.add_argument("--ffprobe", default="ffprobe")
    mac_humans = commands.add_parser(
        "mac-vision-humans",
        help="macOS Vision local human rectangles to provider-neutral detection JSON")
    mac_humans.add_argument("source", type=Path, help="authorized local video file")
    mac_humans.add_argument("--out", type=Path, required=True, help="new detection JSON file")
    mac_humans.add_argument("--max-seconds", type=int, default=10)
    mac_humans.add_argument("--start-seconds", type=int, default=0,
                              help="source-relative window offset (prefix must stay <= 120s)")
    mac_humans.add_argument("--max-samples", type=int, default=12)
    mac_humans.add_argument("--width", type=int, default=320)
    mac_humans.add_argument("--height", type=int, default=180)
    mac_humans.add_argument("--threshold", type=float, default=0.25)
    mac_humans.add_argument("--ffmpeg", default="ffmpeg")
    mac_humans.add_argument("--ffprobe", default="ffprobe")
    mac_humans.add_argument("--rights-status", choices=RIGHTS_STATUSES,
                            default="review-required")
    subject_review = commands.add_parser(
        "review-subject-tracklets",
        help="decode source-PTS frames and show external detector tracklet boxes for visual QA")
    subject_review.add_argument("source", type=Path)
    subject_review.add_argument("report", type=Path, help="subject-tracklets.json")
    subject_review.add_argument("--out", type=Path, required=True, help="new output gallery directory")
    subject_review.add_argument("--max-frames", type=int, default=8)
    subject_review.add_argument("--scan-seconds", type=int, default=20)
    subject_review.add_argument("--width", type=int, default=320)
    subject_review.add_argument("--height", type=int, default=180)
    subject_review.add_argument("--ffmpeg", default="ffmpeg")
    subject_review.add_argument("--ffprobe", default="ffprobe")
    subject_proposals = commands.add_parser(
        "subject-detections",
        help="validate external local detector boxes and form source-verified, cut-bounded tracklets")
    subject_proposals.add_argument("source", type=Path, help="authorized local video")
    subject_proposals.add_argument("detections", type=Path, help="local source-PTS detection JSON")
    subject_proposals.add_argument("--out", type=Path, required=True, help="new output directory")
    subject_proposals.add_argument("--min-iou", type=float, default=0.35)
    subject_proposals.add_argument("--ambiguity-margin", type=float, default=0.10)
    subject_proposals.add_argument("--min-score", type=float, default=0.25)
    subject_proposals.add_argument("--ffprobe", default="ffprobe")
    subject_proposals.add_argument("--rights-status", choices=RIGHTS_STATUSES,
                                   default="review-required")
    character_motion = commands.add_parser(
        "character-motion", help="track 2–6 manually seeded characters and measure screen-space motion")
    character_motion.add_argument("source", type=Path, help="authorized local reference video")
    character_motion.add_argument("seeds", type=Path, help="JSON character seed roster and ROI boxes")
    character_motion.add_argument("--out", type=Path, required=True, help="new immutable output directory")
    character_motion.add_argument("--max-seconds", type=int, default=10)
    character_motion.add_argument("--max-samples", type=int, default=40)
    character_motion.add_argument("--width", type=int, default=160)
    character_motion.add_argument("--height", type=int, default=90)
    character_motion.add_argument("--radius", type=int, default=12)
    character_motion.add_argument("--correlation", type=float, default=0.62)
    character_motion.add_argument("--threshold", type=float, default=0.25)
    character_motion.add_argument("--ffmpeg", default="ffmpeg")
    character_motion.add_argument("--ffprobe", default="ffprobe")
    character_motion.add_argument("--rights-status", choices=RIGHTS_STATUSES,
                                  default="review-required")
    character_review = commands.add_parser(
        "character-scene", help="validate or summarize timecoded character and dialogue review declarations")
    character_actions = character_review.add_subparsers(dest="character_action", required=True)
    for action in ("validate", "report"):
        sub = character_actions.add_parser(action)
        sub.add_argument("review_file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "directors-library":
            if args.directors_action == "snapshot":
                from datetime import datetime, timezone

                retrieved_on = args.retrieved_on or datetime.now(timezone.utc).date().isoformat()
                snapshot = collect_directors_library(
                    fetch_public_page, pages=args.pages, retrieved_on=retrieved_on)
                destination = write_json_artifact(args.out.parent, args.out.name, snapshot)
                print(json.dumps({"snapshot": str(destination), **summarize_directors_snapshot(snapshot)},
                                 indent=2, sort_keys=True))
            else:
                snapshot = load_directors_snapshot(args.snapshot)
                print(json.dumps(summarize_directors_snapshot(snapshot), indent=2, sort_keys=True))
            return 0
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
        if args.command == "video-references":
            collection = load_popular_videos(args.root)
            if args.popular_action == "validate":
                print(json.dumps({"valid": True, "entryCount": len(collection["entries"]),
                                  "retrievedOn": collection["retrievedOn"]}, sort_keys=True))
            else:
                query = args.query if args.popular_action == "search" else ""
                results = search_popular_videos(collection, query, min_views=args.min_views,
                                                limit=args.limit)
                print(json.dumps({"query": query, "results": results, "count": len(results),
                                  "retrievedOn": collection["retrievedOn"]}, indent=2, sort_keys=True))
            return 0
        if args.command == "whatships-visual-backfill":
            print(backfill_whatships_visual_probes(
                args.snapshot, args.bindings, args.analysis_index, args.out,
                previous_index=args.previous_index, max_videos=args.max_videos,
                start_offset=args.start_offset, max_samples=args.max_samples,
                width=args.width, height=args.height,
                cut_threshold=args.cut_threshold,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe))
            return 0
        if args.command == "source-visual-probe":
            print(write_source_visual_probe(
                args.source, args.out, start_seconds=args.start_seconds,
                seconds=args.max_seconds, max_samples=args.max_samples,
                width=args.width, height=args.height,
                cut_threshold=args.cut_threshold, ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe, rights_status=args.rights_status,
                **({"image_translation":True} if args.image_translation else {})))
            return 0
        if args.command == "whatships-measure-batch":
            print(json.dumps(measure_whatships_batch(
                args.snapshot,args.bindings,args.repository_root,
                max_videos=args.max_videos,start_offset=args.start_offset,
                category=args.category,window_seconds=args.window_seconds,
                window_count=args.window_count,max_samples=args.max_samples,
                width=args.width,height=args.height,
                cut_threshold=args.cut_threshold,ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe,image_translation=args.image_translation),
                indent=2,sort_keys=True,ensure_ascii=False))
            return 0
        if args.command == "whatships-acquire-measure":
            print(json.dumps(acquire_and_measure_x_video(
                args.snapshot,args.source_id,args.repository_root,
                rights_basis=args.rights_basis,rights_note=args.rights_note,
                identity_note=args.identity_note,
                acknowledge_rights=args.acknowledge_rights,
                yt_dlp=args.yt_dlp,timeout_seconds=args.timeout_seconds,
                window_seconds=args.window_seconds,
                window_count=args.window_count,max_samples=args.max_samples,
                image_translation=args.image_translation,
                ffmpeg=args.ffmpeg,ffprobe=args.ffprobe),
                indent=2,sort_keys=True,ensure_ascii=False))
            return 0
        if args.command == "whatships-audio-measure":
            print(json.dumps(measure_whatships_audio_to_repository(
                args.snapshot, args.bindings, args.source_id,
                args.repository_root, window_seconds=args.window_seconds,
                window_count=args.window_count,
                replace_existing=args.replace_existing,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe),
                indent=2, sort_keys=True, ensure_ascii=False))
            return 0
        if args.command == "whatships-measure":
            print(json.dumps(measure_whatships_to_repository(
                args.snapshot, args.bindings, args.source_id,
                args.repository_root, window_seconds=args.window_seconds,
                window_count=args.window_count, max_samples=args.max_samples,
                width=args.width, height=args.height,
                cut_threshold=args.cut_threshold,
                replace_existing=args.replace_existing,
                fill_gaps=args.fill_gaps, image_translation=args.image_translation,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe),
                indent=2, sort_keys=True, ensure_ascii=False))
            return 0
        if args.command == "whatships-analyze":
            print(run_whatships_local_analysis(
                args.snapshot, args.bindings, args.out,
                model=args.model, previous_index=args.previous_index,
                source_id=args.source_id, max_videos=args.max_videos,
                start_offset=args.start_offset, detector=args.detector,
                window_seconds=args.window_seconds, window_count=args.window_count,
                max_samples=args.max_samples, max_calls=args.max_calls,
                max_pairs=args.max_pairs, width=args.width, height=args.height,
                port=args.port, timeout_seconds=args.timeout_seconds,
                review=not args.skip_qa, interactions=not args.skip_interactions,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe))
            return 0
        if args.command == "whatships-media":
            if args.media_action == "bind":
                print(register_local_media(
                    args.snapshot, args.video, args.source_id, args.out,
                    rights_basis=args.rights_basis, rights_note=args.rights_note,
                    identity_note=args.identity_note,
                    acknowledge_rights=args.acknowledge_rights,
                    previous=args.previous, ffprobe=args.ffprobe))
            elif args.media_action == "report":
                print(json.dumps(media_coverage(
                    args.snapshot, args.bindings, verify_files=args.verify_files),
                    indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(json.dumps(eligible_bound_media(
                    args.snapshot, args.bindings, limit=args.limit),
                    indent=2, sort_keys=True, ensure_ascii=False))
            return 0
        if args.command == "whatships-all":
            if args.whatships_action == "export-analysis":
                print(export_repository_analysis(
                    args.snapshot, args.out, observations_path=args.observations,
                    bindings_path=args.bindings, analysis_path=args.analysis_index,
                    visual_path=args.visual_index))
            elif args.whatships_action == "sync-analysis":
                print(json.dumps(sync_repository_analysis(
                    args.snapshot, args.incoming, args.root,
                    replace_existing=args.replace_existing,
                    append_numeric_windows=args.append_numeric_windows),
                    indent=2, sort_keys=True, ensure_ascii=False))
            elif args.whatships_action == "validate-analysis":
                print(json.dumps(validate_repository_analysis(args.root, args.snapshot),
                                 indent=2, sort_keys=True, ensure_ascii=False))
            elif args.whatships_action == "research-report":
                print(json.dumps(summarize_tracked_whatships_observations(
                    args.snapshot, args.root), indent=2, sort_keys=True,
                    ensure_ascii=False))
            elif args.whatships_action == "browse":
                print(write_whatships_browser(
                    args.snapshot, args.out, bindings_path=args.bindings,
                    analysis_path=args.analysis_index, numeric_path=args.visual_index,
                    repository_root=(None if args.no_repository_analysis else args.repository_analysis)))
            elif args.whatships_action == "enrich":
                print(enrich_whatships_details(
                    args.previous, args.out, max_details=args.max_details,
                    delay_seconds=args.delay_seconds, timeout=args.timeout,
                    start_offset=args.start_offset,
                    offline_responses=args.offline_responses))
            elif args.whatships_action == "refresh":
                print(refresh_full_whatships_catalog(
                    args.previous, args.out, index_file=args.index_file,
                    timeout=args.timeout, retrieved_on=args.retrieved_on))
            elif args.whatships_action == "report":
                print(json.dumps(summarize_full_snapshot(args.snapshot),
                                 indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(json.dumps(plan_full_snapshot(
                    args.snapshot, limit=args.limit, category=args.category,
                    missing_detail_only=args.missing_detail_only),
                    indent=2, sort_keys=True, ensure_ascii=False))
            return 0
        if args.command == "video-sources":
            collection = load_source_references(args.youtube_root, args.whatships)
            if args.source_action == "validate":
                by_provider = {provider: sum(item["provider"] == provider for item in collection["entries"])
                               for provider in ("youtube", "whatships")}
                response = {"valid": True, "entryCount": len(collection["entries"]),
                            "byProvider": by_provider, "retrievedOn": collection["retrievedOn"]}
            elif args.source_action == "show":
                response = {"reference": get_source_reference(collection, args.identity)}
            elif args.source_action == "report":
                response = summarize_source_references(collection)
            elif args.source_action == "observations":
                notes = load_browser_observations(collection, args.observations)
                matches = search_browser_observations(notes, source_id=args.source_id,
                                                     visual_tag=args.visual_tag)
                response = {"count": len(matches), "reviewedOn": notes["reviewedOn"],
                            "methodology": notes["methodology"], "observations": matches}
            else:
                query = args.query if args.source_action == "search" else ""
                results = search_source_references(collection, query, provider=args.provider,
                                                   min_views=args.min_views, limit=args.limit)
                response = {"query": query, "provider": args.provider,
                            "results": results, "count": len(results),
                            "retrievedOn": collection["retrievedOn"]}
            print(json.dumps(response, indent=2, sort_keys=True, ensure_ascii=False))
            return 0
        if args.command == "audience-benchmarks":
            collection = load_audience_benchmarks(args.root)
            if args.audience_action == "validate":
                print(json.dumps({"valid": True, "channelCount": len(collection["channels"]),
                                  "sampleCount": sum(len(c["videos"]) for c in collection["channels"]),
                                  "retrievedOn": collection["retrievedOn"]}, sort_keys=True))
            elif args.audience_action == "report":
                print(json.dumps(build_audience_insights(
                    collection, minimum_comparison_count=args.min_comparison_count),
                    indent=2, sort_keys=True, ensure_ascii=False))
            elif args.audience_action == "study-plan":
                identities = (load_video_id_candidates(args.identity_candidates, collection)
                              if args.identity_candidates is not None else None)
                plan = build_visual_study_plan(
                    collection, pairs_per_channel=args.pairs_per_channel,
                    max_age_gap_days=args.max_source_age_gap_days,
                    max_duration_ratio=args.max_runtime_ratio,
                    min_view_ratio=args.min_view_ratio, identity_candidates=identities)
                if args.out is None:
                    print(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False))
                else:
                    print(write_json_artifact(args.out, "visual-study-plan.json", plan))
            else:
                identities = load_video_id_candidates(args.identity_candidates, collection)
                comparison = compare_paired_visual_reviews(
                    collection, identities, pair_id=args.pair_id,
                    bindings=load_visual_study_bindings(args.bindings),
                    higher_review=load_visual_events(args.higher_review),
                    lower_review=load_visual_events(args.lower_review))
                if args.out is None:
                    print(json.dumps(comparison, indent=2, sort_keys=True, ensure_ascii=False))
                else:
                    print(write_json_artifact(args.out, "paired-visual-review.json", comparison))
            return 0
        if args.command == "visual-cadence":
            print(json.dumps(summarize_visual_cadence(
                load_cadence_input(args.motion_report),
                load_cadence_input(args.appearance_report),
                image_motion_threshold=args.image_motion_threshold,
                luma_change_threshold=args.luma_change_threshold), indent=2, sort_keys=True))
            return 0
        if args.command == "visual-styles":
            catalog = load_visual_styles(args.root)
            if args.style_action == "validate":
                print(json.dumps({"valid": True, "entryCount": len(catalog["entries"]),
                                  "families": style_family_counts(catalog)}, sort_keys=True))
            else:
                query = args.query if args.style_action == "search" else ""
                result = search_visual_styles(catalog, query, family=args.family, limit=args.limit)
                print(json.dumps({"query": query, "count": len(result), "results": result},
                                 indent=2, sort_keys=True))
            return 0
        if args.command == "open-footage":
            collection = load_open_footage(args.root)
            if args.open_footage_action == "validate":
                result = {"valid": True, "entryCount": len(collection["entries"])}
            elif args.open_footage_action == "list":
                result = {"count": len(collection["entries"]), "entries": [
                    {"id": item["id"], "title": item["title"],
                     "commonsPage": item["rights"]["commonsPage"],
                     "license": item["rights"]["license"],
                     "reviewMode": item["frameObservations"]["reviewMode"]}
                    for item in collection["entries"]]}
            elif args.open_footage_action == "summarize":
                result = summarize_open_footage(collection)
            else:
                result = verify_open_footage_media(
                    collection, args.media_root, ffprobe=args.ffprobe,
                    reference_id=args.id)
            print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
            return 0
        if args.command == "visual-events":
            review = load_visual_events(args.review_file)
            report = ({"valid": True, "eventCount": len(review["events"])}
                      if args.event_action == "validate" else summarize_visual_events(review))
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        if args.command == "speech-link-characters":
            print(link_characters_to_speech(args.speech_scene, args.visual_scene,
                                            args.link_review, args.out))
            return 0
        if args.command == "speech-associate":
            print(associate_speakers(args.speech_run, args.rttm, args.out,
                                     min_coverage=args.min_coverage,
                                     max_competing=args.max_competing))
            return 0
        if args.command == "speech-transcribe":
            print(transcribe_local_video(
                args.source, args.out, model=args.model, whisper_cli=args.whisper_cli,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
                max_seconds=args.max_seconds, timeout_seconds=args.timeout_seconds,
                language=args.language, rights_status=args.rights_status,
                retain_audio=args.retain_audio))
            return 0
        if args.command == "review-character-vision":
            print(build_character_vision_review(
                args.source, args.report, args.vision_run, args.out,
                scan_seconds=args.scan_seconds, width=args.width, height=args.height,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe))
            return 0
        if args.command == "character-vision-feedback":
            print(json.dumps(summarize_character_vision_feedback(
                args.feedback, args.vision_manifest), ensure_ascii=False,
                indent=2, sort_keys=True))
            return 0
        if args.command == "review-character-interactions":
            print(build_interaction_review(
                args.source, args.report, args.vision_run, args.interaction_run,
                args.out, ffprobe=args.ffprobe, ffmpeg=args.ffmpeg))
            return 0
        if args.command == "character-interaction-feedback":
            print(json.dumps(summarize_interaction_feedback(
                args.feedback, args.interaction_manifest), ensure_ascii=False,
                indent=2, sort_keys=True))
            return 0
        if args.command == "local-character-interactions":
            print(analyze_local_interactions(
                args.source, args.report, args.vision_run, args.out, model=args.model,
                port=args.port, max_pairs=args.max_pairs, gap_seconds=args.gap_seconds,
                scan_seconds=args.scan_seconds, timeout_seconds=args.timeout_seconds,
                width=args.width, height=args.height, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe))
            return 0
        if args.command == "character-labels-template":
            print(create_subject_box_label_template(args.detections, args.out))
            return 0
        if args.command == "evaluate-character-detections":
            print(run_subject_box_benchmark(
                args.source, args.detections, args.ground_truth, args.out,
                min_iou=args.min_iou, ffprobe=args.ffprobe))
            return 0
        if args.command == "character-study-batch":
            print(run_character_study_batch(
                args.source, args.out, model=args.model, detector=args.detector,
                start_seconds=args.start_seconds, window_seconds=args.window_seconds,
                stride_seconds=args.stride_seconds, window_count=args.window_count,
                max_samples=args.max_samples, max_calls=args.max_calls,
                max_pairs=args.max_pairs, width=args.width, height=args.height,
                port=args.port, timeout_seconds=args.timeout_seconds,
                review=not args.skip_qa, interactions=not args.skip_interactions,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
                rights_status=args.rights_status))
            return 0
        if args.command == "character-study-local":
            print(run_local_character_study(
                args.source, args.out, model=args.model, detector=args.detector,
                max_seconds=args.max_seconds, start_seconds=args.start_seconds,
                max_samples=args.max_samples,
                max_calls=args.max_calls, max_pairs=args.max_pairs,
                width=args.width, height=args.height, port=args.port,
                timeout_seconds=args.timeout_seconds,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
                rights_status=args.rights_status,
                review=not args.skip_qa, interactions=not args.skip_interactions))
            return 0
        if args.command == "local-character-detect":
            print(detect_local_ollama_subjects(
                args.source, args.out, model=args.model, port=args.port,
                seconds=args.max_seconds, max_samples=args.max_samples,
                start_seconds=args.start_seconds,
                width=args.width, height=args.height, cut_threshold=args.threshold,
                timeout_seconds=args.timeout_seconds, ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe, rights_status=args.rights_status))
            return 0
        if args.command == "local-character-vision":
            print(describe_local_characters(
                args.source, args.report, args.out, model=args.model, port=args.port,
                max_frames=args.max_frames, max_calls=args.max_calls,
                scan_seconds=args.scan_seconds,
                max_pair_gap_seconds=args.max_pair_gap_seconds,
                timeout_seconds=args.timeout_seconds, width=args.width,
                height=args.height, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe))
            return 0
        if args.command == "mac-vision-humans":
            print(detect_mac_vision_people(
                args.source, args.out, seconds=args.max_seconds, max_samples=args.max_samples,
                start_seconds=args.start_seconds,
                width=args.width, height=args.height, cut_threshold=args.threshold,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, rights_status=args.rights_status))
            return 0
        if args.command == "review-subject-tracklets":
            print(build_subject_tracklet_review(
                args.source, args.report, args.out, max_frames=args.max_frames,
                scan_seconds=args.scan_seconds, width=args.width, height=args.height,
                ffmpeg=args.ffmpeg, ffprobe=args.ffprobe))
            return 0
        if args.command == "subject-detections":
            print(run_subject_detections(
                args.source, args.detections, args.out, min_iou=args.min_iou,
                ambiguity_margin=args.ambiguity_margin, min_score=args.min_score,
                ffprobe=args.ffprobe, rights_status=args.rights_status))
            return 0
        if args.command == "character-motion":
            print(run_character_motion(
                args.source, args.seeds, args.out, seconds=args.max_seconds,
                max_samples=args.max_samples, width=args.width, height=args.height,
                radius=args.radius, correlation=args.correlation,
                cut_threshold=args.threshold, ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe, rights_status=args.rights_status))
            return 0
        if args.command == "character-scene":
            review = load_character_scene(args.review_file)
            report = ({"valid": True, "characterCount": len(review["characters"])}
                      if args.character_action == "validate" else
                      summarize_character_scene(review))
            print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
            return 0
        if args.command == "visual-style-review":
            review = load_visual_style_timeline(args.review_file)
            report = ({"valid": True, "segmentCount": len(review["segments"])}
                      if args.style_review_action == "validate" else
                      summarize_visual_style_timeline(review))
            print(json.dumps(report, indent=2, sort_keys=True))
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
        if args.command == "review-dense-flow":
            print(build_dense_flow_review(
                args.source, args.dense_report, args.out,
                max_frames=args.max_frames, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe))
            return 0
        if args.command == "dense-temporal-support":
            result = analyze_dense_temporal_support_file(args.dense_report)
            if args.out is None:
                print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(str(write_json_artifact(args.out, "dense-temporal-support.json", result)))
            return 0
        if args.command == "evaluate-dense-flow":
            result = evaluate_dense_flow_annotations_files(args.dense_report, args.annotations)
            if args.out is None:
                print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(str(write_json_artifact(args.out, "dense-flow-evaluation.json", result)))
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
        if args.command == "compare-dense-flow":
            result = compare_dense_flow_files(
                args.reference_report, args.candidate_report,
                reference_anchor_ms=args.reference_anchor_ms,
                candidate_anchor_ms=args.candidate_anchor_ms,
                tolerance_ms=args.tolerance_ms, time_scale=args.time_scale,
            )
            if args.out is None:
                print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                print(str(write_json_artifact(args.out, "dense-flow-comparison.json", result)))
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
                start_seconds=args.start_seconds,
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
                start_seconds=args.start_seconds,
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
