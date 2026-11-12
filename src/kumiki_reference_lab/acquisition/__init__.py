"""Site-agnostic, ephemeral acquisition and numeric measurement of public media.

Safety contract, enforced by every public entry point here:

- HTTPS only, and only hosts the caller passes in an explicit allowlist; no
  credentials, custom ports, fragments, IP literals, or loopback/private names.
  Query strings are refused by default; `allow_query=True` opts one call into
  signed, cookie-free CDN URLs, and redirects are re-validated with the same
  setting.
- Downloads are byte-capped and land only in a directory the caller owns.
  Every byte (media, frames, stills, audio) is ephemeral: this package never
  deletes your files for you, it never keeps bytes, and it never writes media
  into the evidence tree.
- No cookies, logins, tokens, DRM circumvention, or access-control bypass.
  Public availability is not a licence; callers supply their own rights basis
  and attestation text. YouTube acquisition is yt-dlp-mediated but still
  cookie-free and login-free: no `--cookies-from-browser`, no `--netrc`, no
  DRM/PO-token/nsig workaround beyond stock yt-dlp, and a provider refusal
  (403, login-only, unsupported client) is never retried. Media is always
  ephemeral, and a current `yt-dlp` (>= 2026.10) is required because older
  builds return HTTP 403 on public YouTube videos.
- Only numeric measurements and hashes leave this package. Builders return
  neutral evidence payloads; the caller supplies schemas, limits, and subject
  identity fields, and prints its own progress.

Modules: :mod:`media` (allowlisting, bounded fetch, download, HLS),
:mod:`ytdlp` (bounded, cookie-free YouTube acquisition), :mod:`probe` (ffprobe
adapters), :mod:`windows` (window planning and evidence), :mod:`stills` (still
measurement), :mod:`store` (atomic writes, indexes), :mod:`runner` (generic
batch loop). Nothing here needs ffmpeg at import time.
"""

from __future__ import annotations

from .media import (
    DEFAULT_TEXT_LIMIT, DIRECT, HLS, IMAGE_SUFFIXES, METHOD_HLS_REMUX,
    METHOD_HTTP_DOWNLOAD, USER_AGENT, VIDEO_SUFFIXES, allowlisted_image_url,
    allowlisted_url, allowlisted_video_url, check_downloaded, download_http,
    download_media, fetch_bytes, fetch_text, image_target, media_target,
    plan_hls_download,
)
from .probe import (
    ANALYZER_RIGHTS_STATUS, MAX_RANGED_PROBE_BYTES, RANGED_PROBE_BYTES, as_int,
    as_text, ffprobe_remote_json, finite_float, metadata_from_probe,
    probe_image_dimensions, ranged_source_metadata, remote_source_metadata,
    run_ffprobe_json, source_metadata,
)
from .runner import BatchOutcome, run_batch, safe_error
from .stills import (
    STILL_DECODE_HEIGHT, STILL_DECODE_WIDTH, STILL_MAX_BYTES, STILL_METHOD,
    build_still_evidence, compute_still_metrics, decode_still_rgb,
    dominant_hue_family, infer_decoded_dimensions, measure_still,
    still_image_format,
)
from .store import build_index, resume_matches, safe_slug, utc_now, write_json_atomic
from .windows import (
    MAX_WINDOWS, MAX_WINDOW_SECONDS, build_video_evidence, measure_windows,
    plan_windows, summarize_probes,
)
from .ytdlp import (
    DEFAULT_YOUTUBE_HOSTS, METHOD_YTDLP_MERGE, YOUTUBE, YtDlpError,
    YtDlpRefusedError, allowlisted_youtube_url, classify_ytdlp_failure,
    download_via_ytdlp, youtube_source_metadata,
)

__all__ = [
    # media
    "DEFAULT_TEXT_LIMIT", "DIRECT", "HLS", "IMAGE_SUFFIXES",
    "METHOD_HLS_REMUX", "METHOD_HTTP_DOWNLOAD", "USER_AGENT", "VIDEO_SUFFIXES",
    "allowlisted_image_url", "allowlisted_url", "allowlisted_video_url",
    "check_downloaded", "download_http", "download_media", "fetch_bytes",
    "fetch_text", "image_target", "media_target", "plan_hls_download",
    # probe
    "ANALYZER_RIGHTS_STATUS", "MAX_RANGED_PROBE_BYTES", "RANGED_PROBE_BYTES",
    "as_int", "as_text", "ffprobe_remote_json", "finite_float",
    "metadata_from_probe", "probe_image_dimensions", "ranged_source_metadata",
    "remote_source_metadata", "run_ffprobe_json", "source_metadata",
    # stills
    "STILL_DECODE_HEIGHT", "STILL_DECODE_WIDTH", "STILL_MAX_BYTES",
    "STILL_METHOD", "build_still_evidence", "compute_still_metrics",
    "decode_still_rgb", "dominant_hue_family", "infer_decoded_dimensions",
    "measure_still", "still_image_format",
    # store
    "build_index", "resume_matches", "safe_slug", "utc_now",
    "write_json_atomic",
    # runner
    "BatchOutcome", "run_batch", "safe_error",
    # windows
    "MAX_WINDOWS", "MAX_WINDOW_SECONDS", "build_video_evidence",
    "measure_windows", "plan_windows", "summarize_probes",
    # ytdlp
    "DEFAULT_YOUTUBE_HOSTS", "METHOD_YTDLP_MERGE", "YOUTUBE", "YtDlpError",
    "YtDlpRefusedError", "allowlisted_youtube_url", "classify_ytdlp_failure",
    "download_via_ytdlp", "youtube_source_metadata",
]
