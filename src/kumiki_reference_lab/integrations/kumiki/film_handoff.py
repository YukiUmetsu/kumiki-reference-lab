"""Immutable, evidence-only drafting packet for Kumiki UI's existing FD1 film.

This intentionally does not emit executable FilmDocument JSON. Reference cut
candidates and level changes are not authored scenes, beats or sound effects.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.media.inspect import sha256_file
from kumiki_reference_lab.analyzers.techniques.propose import _json_file
from kumiki_reference_lab.contracts.analysis import (
    AUDIO_ONSETS_VERSION, EDIT_RHYTHM_VERSION, REFERENCE_STUDY_VERSION,
    SHOT_EVIDENCE_VERSION, TECHNIQUE_PROPOSALS_VERSION,
)
from kumiki_reference_lab.core.artifacts import write_json_artifact
from kumiki_reference_lab.core.timebase import as_rational_dict
from kumiki_reference_lab.reviews.notes import _study_context


FILM_HANDOFF_VERSION = "kumiki.film-handoff.v1"


def _fraction(value: Any) -> Fraction:
    if (not isinstance(value, dict) or
            type(value.get("numerator")) is not int or
            type(value.get("denominator")) is not int or
            value["denominator"] <= 0):
        raise ValueError("handoff requires valid rational source timestamps")
    return Fraction(value["numerator"], value["denominator"])


def _frame_count(duration: Fraction, fps: Fraction) -> tuple[int, Fraction]:
    """Nearest integer, halves away from zero, computed without float drift."""
    scaled = duration * fps
    if scaled <= 0:
        raise ValueError("interior source interval must have positive duration")
    frames = (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)
    return frames, Fraction(frames, 1) / fps - duration


def film_handoff_from_reports(
    study: dict[str, Any], evidence: dict[str, Any], rhythm: dict[str, Any],
    onsets: dict[str, Any], proposals: dict[str, Any], *,
    manifest_sha256: str, fps_num: int, fps_den: int,
) -> dict[str, Any]:
    """Pure bounded projection; never assign film recipes, SFX or camera motion."""
    if (type(fps_num) is not int or type(fps_den) is not int or
            not 1 <= fps_num <= 240000 or not 1 <= fps_den <= 1001 or
            not 1 <= Fraction(fps_num, fps_den) <= 240):
        raise ValueError("film handoff FPS must be positive, rational, and 1..240")
    settings = study["settings"]
    source_sha = settings["sourceSha256"]
    analysis_sha = settings["analysisRunSha256"]
    if study["schemaVersion"] != REFERENCE_STUDY_VERSION:
        raise ValueError("film handoff needs a verified v5 reference study")
    if (evidence.get("schemaVersion") != SHOT_EVIDENCE_VERSION or
            rhythm.get("schemaVersion") != EDIT_RHYTHM_VERSION or
            onsets.get("schemaVersion") != AUDIO_ONSETS_VERSION or
            proposals.get("schemaVersion") != TECHNIQUE_PROPOSALS_VERSION or
            evidence["sourceSha256"] != source_sha or
            evidence["analysisRunSha256"] != analysis_sha or
            rhythm["sourceSha256"] != source_sha or
            rhythm["analysisRunSha256"] != analysis_sha or
            rhythm["sourceTimebase"] != evidence["sourceTimebase"] or
            rhythm["sourceStreamIndex"] != evidence["sourceStreamIndex"] or
            rhythm["videoCutCandidateCount"] != len(evidence["regions"]) - 1 or
            proposals["source"]["sha256"] != source_sha or
            proposals["provenance"]["analysisRunSha256"] != analysis_sha or
            onsets["sourceSha256"] != source_sha or
            onsets["scanWindowSeconds"] != settings["seconds"] or
            onsets["status"] not in ("no-audio-stream",
                                     "source-pts-aligned-level-attack-candidates") or
            (onsets["status"] == "no-audio-stream" and onsets["candidates"])):
        raise ValueError("film handoff evidence sources or analysis identities disagree")
    fps = Fraction(fps_num, fps_den)
    expected = evidence["regions"][1:]
    if rhythm["observedInterCutIntervalCount"] != len(expected) - 1 and expected:
        raise ValueError("film handoff interval count disagrees with source cuts")
    if not expected and rhythm["observedInterCutIntervalCount"] != 0:
        raise ValueError("film handoff has intervals without candidate boundaries")
    if len(rhythm["intervals"]) != max(0, len(expected) - 1):
        raise ValueError("film handoff has missing interior interval records")
    windows = []
    for i, (item, a, b) in enumerate(zip(rhythm["intervals"], expected, expected[1:]), 1):
        start, end = _fraction(a["startSeconds"]), _fraction(b["startSeconds"])
        if (item["regionId"] != a["id"] or
                item["fromVideoCutCandidatePts"] != a["startPtsInclusive"] or
                item["toVideoCutCandidatePts"] != b["startPtsInclusive"] or
                _fraction(item["fromSeconds"]) != start or
                _fraction(item["toSeconds"]) != end or
                _fraction(item["durationSeconds"]) != end - start):
            raise ValueError("film handoff interval is not grounded in adjacent cuts")
        frames, error = _frame_count(end - start, fps)
        windows.append({
            "id": f"candidate-interval-{i:03d}",
            "sourceRegionId": a["id"],
            "startCutCandidatePts": a["startPtsInclusive"],
            "endCutCandidatePts": b["startPtsInclusive"],
            "sourceStartSeconds": a["startSeconds"],
            "sourceEndSeconds": b["startSeconds"],
            "sourceDurationSeconds": item["durationSeconds"],
            "suggestedFilmFrames": frames,
            "roundingErrorSeconds": as_rational_dict(error),
            "renderability": "candidate-duration" if frames else "requires-authored-retiming",
            "sceneRecipeId": None,
            "sceneContent": None,
            "reviewStatus": "not-reviewed",
        })
    attacks = []
    for item in onsets["candidates"]:
        audio_timebase = _fraction(onsets["sourceTimebase"])
        if (type(item["anchorSourcePts"]) is not int or
                _fraction(item["anchorSourceSeconds"]) !=
                item["anchorSourcePts"] * audio_timebase or
                _fraction(item["supportWindow"]["startSeconds"]) >
                _fraction(item["anchorSourceSeconds"]) or
                _fraction(item["supportWindow"]["endSeconds"]) <=
                _fraction(item["anchorSourceSeconds"])):
            raise ValueError("film handoff audio attack has invalid source PTS support")
        # Deliberately no film-frame projection or cut association: source
        # audio/video clock synchronization has not been established.
        attacks.append({
            "id": item["id"], "audioSourcePts": item["anchorSourcePts"],
            "audioSourceSeconds": item["anchorSourceSeconds"],
            "supportWindow": item["supportWindow"],
            "signal": item["signal"],
            "filmCue": None,
        })
    technique_cues = [
        {"id": cue["id"], "catalogTechniqueId": cue["techniqueId"],
         "sourcePtsRange": cue["sourcePtsRange"], "implementationId": None}
        for cue in proposals["candidates"]
    ]
    return {
        "schemaVersion": FILM_HANDOFF_VERSION,
        "status": "candidate-drafting-evidence-not-an-executable-film",
        "study": {"manifestSha256": manifest_sha256, "sourceSha256": source_sha,
                  "analysisRunSha256": analysis_sha},
        "target": {"repository": "YukiUmetsu/kumiki-ui",
                   "contract": "FD1 FilmDocument schemaVersion 1",
                   "schemaPath": "registry/video/film-document.schema.json",
                   "validationCommand": "npm run film:check -- <authored-film.json>",
                   "executableDocument": False,
                   "installedCapabilitiesVerified": False},
        "timing": {"videoSourceTimebase": evidence["sourceTimebase"],
                   "suggestedFilmFps": {"num": fps_num, "den": fps_den},
                   "rounding": "nearest-half-up-for-positive-durations",
                   "audioVideoClockRelation": "not-independently-synchronized"},
        "boundaries": {"candidateCutCount": len(expected),
                       "censoring": "scan-start-and-final-observed-region-excluded"},
        "interiorWindows": windows,
        "audioAttackCandidates": attacks,
        "catalogTechniqueCues": technique_cues,
        "authoringGates": [
            "Inspect original source frames and full-speed video; verify candidate cuts.",
            "Choose an original teaching purpose, scene recipe, content, subject and visuals.",
            "Resolve live Kumiki catalog APIs and validate authored FD1 film JSON.",
            "Do not turn level attacks into beats, speech or sound effects without review.",
            "Render, compare explicit source/film anchors, then obtain human visual approval.",
        ],
    }


def export_film_handoff(study_manifest: Path, output: Path, *,
                        fps_num: int = 30, fps_den: int = 1) -> Path:
    """Verify complete study + analysis, then write an independent draft packet."""
    study, proposals, evidence, _ = _study_context(study_manifest)
    if study["schemaVersion"] != REFERENCE_STUDY_VERSION:
        raise ValueError("film handoff needs a verified v5 reference study")
    root = study_manifest.parent.resolve()
    analysis = (root.parent / "analysis" /
                study["settings"]["analysisRunDirectory"]).resolve()
    destination = output.resolve()
    if (destination.is_relative_to(root) or destination.is_relative_to(analysis) or
            any((parent / marker).exists() for parent in
                (destination, *destination.parents)
                for marker in ("study-manifest.json", "analysis-run.json"))):
        raise ValueError("film handoff output must remain outside immutable bundles")
    rhythm = _json_file(root / "edit-rhythm.json", limit=4_194_304)
    timeline_path = root / study["artifacts"]["timelineView"]
    onsets = _json_file(timeline_path.parent / "audio-onsets.json", limit=4_194_304)
    packet = film_handoff_from_reports(
        study, evidence, rhythm, onsets, proposals,
        manifest_sha256=sha256_file(study_manifest),
        fps_num=fps_num, fps_den=fps_den,
    )
    return write_json_artifact(output, "film-handoff.json", packet)
