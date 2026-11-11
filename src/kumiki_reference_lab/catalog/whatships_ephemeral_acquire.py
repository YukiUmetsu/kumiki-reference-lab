"""Opt-in, ephemeral original-X-post video acquisition for What Ships research.

No authentication or DRM bypass. Downloaded footage and private rights notes
are discarded after source-SHA/PTS-grounded numeric analysis is committed into
the local Git worktree. This does not certify that X footage matches the
catalog preview; the operator must attest exact source identity and rights.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from kumiki_reference_lab.catalog.video_sources import _load_snapshot, _from_whatships
from kumiki_reference_lab.catalog.whatships_direct_measure import measure_whatships_to_repository
from kumiki_reference_lab.catalog.whatships_media_bindings import register_local_media
from kumiki_reference_lab.core.provenance import file_signature, require_unchanged
from kumiki_reference_lab.pipeline.ollama_character_perception import _VIDEO_EXTENSIONS

SCHEMA_VERSION = "kumiki.whatships-ephemeral-x-acquisition.v1"
_POST = re.compile(r"/[A-Za-z0-9_]{1,20}/status/[0-9]{10,25}/?\Z")
_MEDIA_CAP = 150 * 1024 * 1024


def _x_video_origin(snapshot: dict[str, Any], source_id: str) -> str:
    """Allow only the original post URL from validated catalog detail metadata."""
    entries = {r["id"]:r for r in _from_whatships(snapshot)}
    if source_id not in entries:
        raise ValueError("source ID absent from source-validated What Ships catalog")
    url = entries[source_id]["originalUrl"]
    if not isinstance(url,str):
        raise ValueError("source has no verified X post reference in the dated catalog")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ("x.com","twitter.com")
            or parsed.username or parsed.password or parsed.port is not None
            or parsed.query or parsed.fragment or not _POST.fullmatch(parsed.path)):
        raise ValueError("catalog post URL is not an exact public X status reference")
    return url


def _download_one_public_x_post(
    url: str, destination: Path, *, yt_dlp: str, timeout_seconds: int,
) -> Path:
    """Fetch at most one accessible public video. Never read browser cookies."""
    if (not isinstance(url,str) or type(timeout_seconds) is not int
            or not 30 <= timeout_seconds <= 300 or
            destination.is_symlink() or not destination.is_dir()):
        raise ValueError("unsafe local source acquisition parameters")
    if any(destination.iterdir()):
        raise ValueError("download directory must be empty")
    args = [
        yt_dlp,
        "--ignore-config","--no-plugin-dirs",
        "--no-playlist","--playlist-items","1",
        "--no-mtime","--no-progress","--quiet",
        "--no-continue","--no-part",
        "--max-filesize","150M","--socket-timeout","15",
        "--retries","1","--fragment-retries","1",
        "--concurrent-fragments","1",
        "--merge-output-format","mp4",
        "--paths",str(destination.resolve()),
        "--output","source.%(ext)s",
        "--",url,
    ]
    try:
        result = subprocess.run(
            args, cwd=destination, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ValueError("yt-dlp is not installed locally") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("public X video acquisition exceeded bounded timeout") from exc
    except OSError as exc:
        raise ValueError("yt-dlp process could not start") from exc
    if result.returncode != 0:
        # Do not echo yt-dlp stderr, which can contain URLs or local paths.
        raise ValueError("original public X post did not provide a downloadable video")
    files = list(destination.iterdir())
    videos = [p for p in files if p.name.startswith("source.") and
              p.suffix.lower() in _VIDEO_EXTENSIONS and
              not p.is_symlink() and p.is_file()]
    if len(videos) != 1 or len(files) != 1:
        raise ValueError("X post yielded zero, multiple or unexpected local video files")
    source = videos[0]
    if not 0 < source.stat().st_size <= _MEDIA_CAP:
        raise ValueError("downloaded video exceeded bounded local size")
    return source


def acquire_and_measure_x_video(
    snapshot_path: Path, source_id: str, repository_root: Path, *,
    rights_basis: str, rights_note: str, identity_note: str,
    acknowledge_rights: bool = False, yt_dlp: str = "yt-dlp",
    timeout_seconds: int = 240, window_seconds: int = 10,
    window_count: int = 4, max_samples: int = 12,
    fill_gaps: bool = True,
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Download -> validate -> measure -> retain only derived Git data -> delete.

    The rights declaration and identity explanation are required on every
    invocation; a linked public X post alone is not legal permission.
    """
    if (acknowledge_rights is not True or type(fill_gaps) is not bool
            or type(timeout_seconds) is not int
            or not 30 <= timeout_seconds <= 300):
        raise ValueError("explicit authorized-source rights and bounded download timeout required")
    if (type(rights_basis) is not str or
            rights_basis not in ("own-original-work","written-permission",
                                 "permissive-license","other-lawful-authorization") or
            not isinstance(rights_note,str) or
            not isinstance(identity_note,str) or
            not 12 <= len(rights_note.strip()) <= 500 or
            not 12 <= len(identity_note.strip()) <= 500):
        raise ValueError("rights basis and exact source-identification notes are required")
    from kumiki_reference_lab.catalog.whatships_analysis_store import validate_repository_analysis
    validate_repository_analysis(repository_root,snapshot_path)
    snapshot_sig = file_signature(snapshot_path)
    snapshot = _load_snapshot(snapshot_path)
    url = _x_video_origin(snapshot,source_id)
    require_unchanged(snapshot_path,snapshot_sig)
    with tempfile.TemporaryDirectory(prefix="kumiki-x-original-") as dirname:
        workspace = Path(dirname)
        source_folder = workspace/"video"
        source_folder.mkdir()
        source = _download_one_public_x_post(
            url,source_folder,yt_dlp=yt_dlp,timeout_seconds=timeout_seconds)
        ledger_dir = workspace/"binding"
        ledger = register_local_media(
            snapshot_path,source,source_id,ledger_dir,
            rights_basis=rights_basis,rights_note=rights_note,
            identity_note=identity_note,acknowledge_rights=True,
            ffprobe=ffprobe)
        result = measure_whatships_to_repository(
            snapshot_path,ledger,source_id,repository_root,
            window_seconds=window_seconds,window_count=window_count,
            max_samples=max_samples,fill_gaps=fill_gaps,
            ffmpeg=ffmpeg,ffprobe=ffprobe)
    # Python TemporaryDirectory removes footage, source local bindings and
    # all partial downloads on success or failure. No video bytes are kept.
    return {
        "schemaVersion":SCHEMA_VERSION,
        "sourceId":source_id,
        "sourceProvider":"x-original-public-post",
        "declaredRightsBasis":rights_basis,
        "sourceIdentityStatus":"operator-attested-not-independently-verified",
        "sourceLink":url,
        "temporaryVideoRetained":False,
        "privateMediaLedgerRetained":False,
        "numericEvidenceStatus":result["status"],
        "gitWorkingTreeUpdated":result["gitWorkingTreeUpdated"],
        "newMeasuredWindows":result["measuredOriginalSourceWindows"],
        "newSampledOriginalSourceFrames":result["sampledOriginalSourceFrames"],
        "fullFilmHumanReviewed":False,
        "limitations":[
            "Public X embed availability is not guaranteed; no authentication/cookies or DRM bypass is attempted.",
            "An original post link does not itself prove exact video-content identity or lawful permission.",
            "Only original-PTS numeric observations enter Git; no copied video, speech, private rights notes or person identity.",
            "Sparse PTS frame samples are not equivalent to a human-reviewed complete film.",
        ],
    }
