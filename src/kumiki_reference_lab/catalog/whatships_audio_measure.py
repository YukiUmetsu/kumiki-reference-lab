"""Store source-hashed PCM energy timelines in the Git-tracked What Ships corpus."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from kumiki_reference_lab.analyzers.audio.source_audio_probe import (
    SCHEMA_VERSION as AUDIO_PROBE_SCHEMA, analyze_source_audio_window,
)
from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.catalog.video_sources import _load_snapshot
from kumiki_reference_lab.catalog.whatships_analysis_store import (
    INDEX_VERSION, SCHEMA_VERSION, _json_bytes, _validate_record,
    sync_repository_analysis, validate_repository_analysis,
)
from kumiki_reference_lab.catalog.whatships_direct_measure import _duration_windows
from kumiki_reference_lab.catalog.whatships_media_bindings import (
    _media_path, _video_identity_map, load_media_bindings,
)
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged

_LIMITATIONS=[
    "No record should be interpreted as verified full-video coverage.",
    "Observed browser moments lack original PTS unless separately analyzed.",
    "RGB/cut metrics are source-frame numerical proxies, not camera/lighting/style truth.",
    "Model-generated character observations have not been human-reviewed.",
    "No local paths, original media, private notes or source-video frames are included.",
]


def _checked_audio_window(
    report: dict[str, Any], *, sha: str,
    video_stream: int, video_timebase: dict[str,int],
    start: int, end: int,
) -> dict[str, Any]:
    if (not isinstance(report,dict) or
            report.get("schemaVersion") != AUDIO_PROBE_SCHEMA or
            report.get("sourceSha256") != sha or
            report.get("videoStreamIndex") != video_stream or
            report.get("videoSourceTimebase") != video_timebase or
            report.get("requestedStartSeconds") != start or
            report.get("requestedSeconds") != end-start or
            report.get("decodedPcmSampleRate") != 8000 or
            report.get("evidenceStatus") !=
            "sampled-pcm-energy-not-original-pts-aligned-or-human-reviewed"):
        raise ValueError("audio energy output did not match expected original source video")
    for key in (
        "audioStreamIndex","audioSourceTimebase","audioStreamStartPts",
        "decodedPcmSampleCount","decodedDurationSecondsApprox",
        "decodedFrames","summary",
    ):
        if key not in report:
            raise ValueError("audio energy source report missing measured sample evidence")
    return {
        "startSeconds":start,"endSeconds":end,
        "audioStreamIndex":report["audioStreamIndex"],
        "audioSourceTimebase":report["audioSourceTimebase"],
        "audioStreamStartPts":report["audioStreamStartPts"],
        "decodedPcmSampleRate":8000,
        "decodedPcmSampleCount":report["decodedPcmSampleCount"],
        "decodedDurationSecondsApprox":report["decodedDurationSecondsApprox"],
        "decodedFrames":report["decodedFrames"],
        "summary":report["summary"],
        "audioClockStatus":"ffmpeg-output-seek-not-original-source-pts-verified",
    }


def measure_whatships_audio_to_repository(
    snapshot_path: Path, binding_path: Path, source_id: str,
    repository_root: Path, *, window_seconds: int=10, window_count: int=4,
    replace_existing: bool=False, ffmpeg: str="ffmpeg",
    ffprobe: str="ffprobe",
) -> dict[str, Any]:
    """Measure sparse local video audio energy and sync safe numeric facts into Git."""
    if (type(source_id) is not str or not source_id.startswith("whatships:") or
            type(window_seconds) is not int or not 1 <= window_seconds <= 30 or
            type(window_count) is not int or not 1 <= window_count <= 6 or
            type(replace_existing) is not bool):
        raise ValueError("audio measurement requires exact catalog ID and bounded window budgets")
    validate_repository_analysis(repository_root,snapshot_path)
    snap_sig=file_signature(snapshot_path)
    bind_sig=file_signature(binding_path)
    snapshot=_load_snapshot(snapshot_path)
    entries=_video_identity_map(snapshot)
    if source_id not in entries:
        raise ValueError("audio source not indexed by the official What Ships catalog")
    ledger=load_media_bindings(binding_path,snapshot,verify_files=False)
    bound={row["sourceId"]:row for row in ledger["bindings"]}
    if source_id not in bound:
        raise ValueError("audio source lacks operator-authorized local media binding")
    row=bound[source_id]
    video=_media_path(row["localPath"])
    vid_sig=file_signature(video)
    if vid_sig[0] != row["mediaSizeBytes"] or sha256_file(video) != row["mediaSha256"]:
        raise ValueError("video source fingerprint changed from registered media identity")
    inspected=inspect_source(video,ffprobe=ffprobe,rights_status="user-declared-authorized")
    if (inspected["source"]["sha256"] != row["mediaSha256"] or
            inspected["video"]["streamIndex"] != row["sourceStreamIndex"] or
            inspected["video"]["sourceTimebase"] != row["sourceTimebase"]):
        raise ValueError("video source bytes, stream index or original timebase changed")
    windows,requested_fraction=_duration_windows(
        inspected["video"]["durationSecondsReported"],
        window_seconds=window_seconds,window_count=window_count)
    energy=[]
    decoded_count=0
    for start,end in windows:
        report=analyze_source_audio_window(
            video,start_seconds=start,seconds=end-start,
            rights_status="user-declared-authorized",
            ffmpeg=ffmpeg,ffprobe=ffprobe)
        energy.append(_checked_audio_window(
            report,sha=row["mediaSha256"],
            video_stream=row["sourceStreamIndex"],
            video_timebase=row["sourceTimebase"],
            start=start,end=end))
        decoded_count+=report["decodedPcmSampleCount"]
    record={
        "schemaVersion":SCHEMA_VERSION,
        "sourceId":source_id,
        "watchUrl":entries[source_id]["directoryUrl"],
        "catalogSnapshotOn":snapshot["retrievedOn"],
        "catalogSnapshotSha256":sha256_file(snapshot_path),
        "sourceMediaSha256":row["mediaSha256"],
        "coverage":{
            "hasBrowserSpotCheck":False,
            "hasSampledNumericSourceFrames":False,
            "hasUnreviewedCharacterJob":False,
            "fullFilmReviewed":False,
            "hasSampledAudioEnergy":True,
        },
        "evidence":{
            "numericAudio":{
                "sourceSha256":row["mediaSha256"],
                "windows":energy,
                "evidenceStatus":"pcm-energy-audio-clock-approximate-not-human-reviewed",
            },
        },
        "limits":_LIMITATIONS,
    }
    _validate_record(record,source_id,record["catalogSnapshotSha256"])
    require_unchanged(video,vid_sig)
    if sha256_file(video) != row["mediaSha256"]:
        raise ValueError("video changed during PCM audio envelope measurement")
    require_unchanged(snapshot_path,snap_sig)
    require_unchanged(binding_path,bind_sig)
    incoming_index={
        "schemaVersion":INDEX_VERSION,
        "catalogSnapshotOn":snapshot["retrievedOn"],
        "catalogSnapshotSha256":record["catalogSnapshotSha256"],
        "catalogVideoCount":len(entries),
        "sourceLinkedAnalysisCount":1,
        "browserSpotCheckCount":0,
        "sampledNumericVideoCount":0,
        "sampledAudioVideoCount":1,
        "unreviewedCharacterJobCount":0,
        "fullFilmReviewedCount":0,
        "entries":[{
            "sourceId":source_id,
            "recordPath":source_id.removeprefix("whatships:")+".json",
            "evidenceKinds":["numericAudio"],
        }],
        "limits":[
            "Only records with actual observational evidence are stored here.",
            "Metadata-only catalog entries stay in research/whatships-index-2026-11-10.json.",
            "Do not equate a model completion or numeric frame sample with expert review.",
        ],
    }
    with tempfile.TemporaryDirectory(
            prefix=".kumiki-whatships-audio-",dir=repository_root.parent) as temp:
        folder=Path(temp)
        (folder/"index.json").write_bytes(_json_bytes(incoming_index))
        (folder/(source_id.removeprefix("whatships:")+".json")).write_bytes(
            _json_bytes(record))
        validate_repository_analysis(folder,snapshot_path)
        sync=sync_repository_analysis(
            snapshot_path,folder,repository_root,replace_existing=replace_existing)
    return {
        "schemaVersion":"kumiki.whatships-direct-audio-energy-study.v1",
        "sourceId":source_id,
        "sourceMediaSha256":row["mediaSha256"],
        "measuredAudioWindows":len(energy),
        "decodedPcmSamples":decoded_count,
        "requestedWindowTimeFractionOfReportedFilmDuration":requested_fraction,
        "synchronizationStatus":"audio-video-clock-not-independently-verified",
        "humanReviewed":False,
        "gitWorkingTreeUpdated":bool(sync["recordsChangedOrAdded"]),
        "status":"numeric-pcm-energy-source-linked-not-speech-or-music-inference",
    }
