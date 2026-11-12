"""Bounded, cookie-free YouTube acquisition through a local ``yt-dlp``.

This module is the one place in the acquisition engine that shells out to
``yt-dlp``. It is deliberately narrow:

- Only exact single-video YouTube URLs are accepted (``/watch?v=``,
  ``/shorts/``, ``/embed/``, ``youtu.be/``). Playlists, channels, live URLs and
  any other path are refused before a process starts.
- The invocation is bounded: one playlist item, one concurrent fragment, one
  retry, one socket timeout, a merge output format, a byte cap, and a
  ``--paths`` destination that must be an existing, empty, non-symlink
  directory. ``--ignore-config`` and ``--no-plugin-dirs`` keep local config and
  plugins out of the run.
- Browser cookies, logins, ``--cookies-from-browser``, ``--netrc`` and remote
  component downloads are never used. There is no DRM or PO-token bypass: stock
  ``yt-dlp`` behaviour only.
- ``yt-dlp`` stderr is captured solely to classify a failure and is never
  echoed into an exception or a log line. A hard refusal (login-only, private,
  members-only, bot-check, unsupported client) is ``provider-refused`` and is
  never retried. The 403/CDN-data class is also ``provider-refused`` but is
  retried a bounded number of times with backoff, because YouTube intermittently
  returns 403 for a single stream while the same public URL succeeds moments
  later. Retries reuse the identical anonymous request: no cookies, logins,
  PO tokens, nsig extraction, or proxies are introduced.

YouTube acquisition needs a current ``yt-dlp`` (``>= 2026.10``); older builds
return HTTP 403 from YouTube's player even for public videos.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs, urlsplit

from .media import VIDEO_SUFFIXES, allowlisted_url
from .probe import as_int, as_text, finite_float

YOUTUBE = "youtube"
METHOD_YTDLP_MERGE = "ytdlp-merge"

DEFAULT_YOUTUBE_HOSTS = (
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
)

# yt-dlp's own default is "best"; these caps keep the download bounded in both
# resolution and bytes regardless of what the site advertises.
DEFAULT_YTDLP_MAX_BYTES = 250 * 1024 * 1024
DEFAULT_YTDLP_MAX_HEIGHT = 720

_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_ID_PATH = re.compile(r"/(?:shorts|embed)/([A-Za-z0-9_-]{11})")
_METADATA_MAX_STDOUT = 8 * 1024 * 1024
_STDERR_TAIL = 4096

# Failures that mean "the provider refused us for good", not "the network
# wobbled": login/bot-check/private/members-only/unsupported-client. These are
# never retried and surface as ``provider-refused``.
_HARD_REFUSAL_MARKERS = (
    "sign in",
    "sign-in",
    "logged-in",
    "logged in",
    "login required",
    "private video",
    "members-only",
    "members only",
    "requires payment",
    "this video is unavailable",
    "video unavailable",
    "not available in your country",
    "confirm you're not a bot",
    "confirm you are not a bot",
    "unsupported client",
    "client version",
    "upgrade yt-dlp",
    "please update yt-dlp",
    "nsig",
    "po token",
    "po_token",
)

# The 403/CDN-data class: YouTube intermittently throttles or drops one stream
# or fragment. The same public request can succeed moments later, so this class
# is still ``provider-refused`` (public classification is unchanged) but gets a
# bounded retry with backoff.
_THROTTLE_MARKERS = (
    "403 forbidden",
    "http error 403",
    "forbidden",
    "unable to download video data",
)
_THROTTLE_PATTERNS = (re.compile(r"\b403\b"),)

# Bounded retry policy. ``attempts`` includes the first attempt, so 1 disables
# retrying. Both bounds are enforced in code, not just by documentation.
_MIN_ATTEMPTS = 1
_MAX_ATTEMPTS = 3
_MAX_BACKOFF_SECONDS = 60.0


class YtDlpError(ValueError):
    """A bounded yt-dlp invocation failed. Messages never carry stderr text."""

    reason = "transient"


class YtDlpRefusedError(YtDlpError):
    """The provider refused the request (403, login-only, unsupported client).

    Distinct so adapters can record ``provider-refused`` instead of retrying:
    the same request will fail identically until the local yt-dlp is upgraded.
    """

    reason = "provider-refused"


# ---------------------------------------------------------------------------
# URL policy
# ---------------------------------------------------------------------------


def _youtube_video_id(parsed: Any, *, host: str) -> str | None:
    path = parsed.path
    if host == "youtu.be":
        if parsed.query:
            return None
        candidate = path[1:]
        return candidate if _VIDEO_ID.fullmatch(candidate or "") else None
    if path == "/watch":
        parameters = parse_qs(parsed.query, keep_blank_values=True)
        if set(parameters) != {"v"} or len(parameters["v"]) != 1:
            return None
        candidate = parameters["v"][0]
        return candidate if _VIDEO_ID.fullmatch(candidate) else None
    match = _ID_PATH.fullmatch(path)
    if match is not None and not parsed.query:
        return match.group(1)
    return None


def allowlisted_youtube_url(
    url: object, *, allowed_hosts: Iterable[str] = DEFAULT_YOUTUBE_HOSTS,
) -> str:
    """Validate one public single-video YouTube URL.

    Reuses :func:`kumiki_reference_lab.acquisition.media.allowlisted_url` for
    the scheme/credentials/port/fragment/host checks, then admits only the four
    documented single-video path shapes. A ``watch`` query may carry exactly one
    ``v`` parameter and nothing else, so a playlist URL
    (``watch?v=…&list=…``) is refused even when its host is allowlisted.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("YouTube video URL is absent")
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise ValueError("YouTube video URL is not a parsable URL") from None
    # Validate everything except the query string; the query is inspected
    # separately because a watch URL needs exactly one ``v`` parameter.
    bare = parsed._replace(query="").geturl()
    allowlisted_url(bare, allowed_hosts=allowed_hosts,
                    label="YouTube video URL")
    host = (parsed.hostname or "").lower()
    if _youtube_video_id(parsed, host=host) is None:
        raise ValueError(
            "YouTube video URL is not a public single-video reference")
    return url


# ---------------------------------------------------------------------------
# failure classification
# ---------------------------------------------------------------------------


def _stderr_text(stderr: object) -> str:
    if isinstance(stderr, bytes):
        return stderr[-_STDERR_TAIL:].decode("utf-8", "replace")
    if isinstance(stderr, str):
        return stderr[-_STDERR_TAIL:]
    return ""


def classify_ytdlp_failure(stderr: object) -> str:
    """Return ``"provider-refused"`` or ``"transient"`` for a failed run.

    Only used for classification. The text itself is never returned, logged,
    or attached to an exception: it can contain URLs and local paths.

    Both the hard refusal markers and the 403/CDN-data (throttle) markers map
    to ``"provider-refused"``: that public vocabulary is unchanged. The two
    classes differ only in whether a bounded retry is attempted; see
    :func:`is_retryable_refusal`.
    """
    text = _stderr_text(stderr).lower()
    if any(marker in text for marker in _HARD_REFUSAL_MARKERS):
        return "provider-refused"
    if _is_throttle_text(text):
        return "provider-refused"
    return "transient"


def _is_throttle_text(text: str) -> bool:
    if any(marker in text for marker in _THROTTLE_MARKERS):
        return True
    return any(pattern.search(text) for pattern in _THROTTLE_PATTERNS)


def is_retryable_refusal(stderr: object) -> bool:
    """True only for the 403/CDN-data class, never for a hard refusal.

    A hard marker wins even when the same stderr also mentions 403: a
    bot-check, login wall, private or members-only video will fail identically
    on every attempt, so it must not be retried. Purely transient failures
    (connection reset, DNS) are not refusals and are also not "retryable" here;
    the caller's batch layer owns those.
    """
    text = _stderr_text(stderr).lower()
    if any(marker in text for marker in _HARD_REFUSAL_MARKERS):
        return False
    return _is_throttle_text(text)


def _failure(stderr: object, *, label: str) -> YtDlpError:
    if classify_ytdlp_failure(stderr) == "provider-refused":
        return YtDlpRefusedError(
            f"{label} was refused by YouTube (provider-refused); a current "
            "yt-dlp (>= 2026.10) is required for public playback")
    return YtDlpError(
        f"{label} did not complete (transient failure); no bytes were kept")


# ---------------------------------------------------------------------------
# process runners
# ---------------------------------------------------------------------------


def _run_ytdlp(
    args: list[str], *, cwd: Path | None, timeout: float,
    capture_stdout: bool,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            args, cwd=cwd,
            stdout=(subprocess.PIPE if capture_stdout
                    else subprocess.DEVNULL),
            stderr=subprocess.PIPE, timeout=timeout, check=False)
    except FileNotFoundError as error:
        raise YtDlpError("yt-dlp is not installed locally") from error
    except subprocess.TimeoutExpired as error:
        raise YtDlpError("yt-dlp exceeded the bounded timeout") from error
    except OSError as error:
        raise YtDlpError("yt-dlp process could not start") from error


def _checked_budget(max_bytes: object) -> int:
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("download byte budget must be a positive integer")
    return max_bytes


def _checked_timeout(timeout: object, *, lower: float, upper: float) -> float:
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not lower <= float(timeout) <= upper):
        raise ValueError("bounded timeout is out of bounds")
    return float(timeout)


def _checked_attempts(attempts: object) -> int:
    """Clamp the attempt count into the documented ``1..3`` band.

    A non-integer is a contract error. An out-of-range integer is clamped, not
    rejected, so a caller that asks for "more retries" still gets a bounded run
    instead of an unbounded one.
    """
    if isinstance(attempts, bool) or not isinstance(attempts, int):
        raise ValueError("attempts must be an integer")
    return max(_MIN_ATTEMPTS, min(_MAX_ATTEMPTS, attempts))


def _checked_backoff(backoff_seconds: object) -> float:
    if (isinstance(backoff_seconds, bool)
            or not isinstance(backoff_seconds, (int, float))
            or not 0.0 <= float(backoff_seconds) <= _MAX_BACKOFF_SECONDS):
        raise ValueError("retry backoff is out of bounds")
    return float(backoff_seconds)


def _clear_partial_output(destination: Path) -> None:
    """Remove everything a failed attempt may have left behind.

    Only entries inside the caller-owned, engine-empty destination are touched.
    Without this, a retry would see a non-empty directory and the "exactly one
    file" contract after a successful retry would be violated by the leftovers.
    """
    for entry in destination.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            try:
                entry.unlink()
            except FileNotFoundError:
                pass


def _format_selector(max_height: int, *, prefer_h264: bool) -> str:
    """Prefer H.264/AAC at or below ``max_height``, then fall back wider.

    H.264 comes first because the analyzer decodes frames with ffmpeg: AV1/VP9
    play, but are slower, and the engine should not silently prefer them.
    """
    height = f"[height<={max_height}]"
    if prefer_h264:
        return (f"bv*{height}[vcodec^=avc1]+ba[acodec^=mp4a]"
                f"/bv*{height}+ba/b{height}/b")
    return f"bv*{height}+ba/b{height}/b"


# ---------------------------------------------------------------------------
# acquisition
# ---------------------------------------------------------------------------


def download_via_ytdlp(
    url: str, destination: Path, *, yt_dlp: str = "yt-dlp",
    max_bytes: int = DEFAULT_YTDLP_MAX_BYTES,
    max_height: int = DEFAULT_YTDLP_MAX_HEIGHT, timeout_seconds: float = 300,
    prefer_h264: bool = True,
    allowed_hosts: Iterable[str] = DEFAULT_YOUTUBE_HOSTS,
    attempts: int = 2, backoff_seconds: float = 6.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> Path:
    """Download one allowlisted public YouTube video into ``destination``.

    Bounded flags only, no local config, no plugins, no cookies, no login. The
    destination must already exist, be a real (non-symlink) directory, and be
    empty. Exactly one regular video file must appear, with a known suffix and
    a size in ``0 < size <= max_bytes``. Browser state is never read; there is
    no DRM or PO-token workaround.

    ``attempts`` (clamped to ``1..3``) bounds how many identical anonymous
    invocations may run. Only the 403/CDN-data class is retried: a hard refusal
    (login, bot-check, private, members-only, unsupported client) raises on the
    first attempt. Between retries the engine removes partial output and sleeps
    ``backoff_seconds + uniform(0, backoff_seconds)``; ``sleeper`` is injectable
    so tests stay offline and instant.
    """
    validated = allowlisted_youtube_url(url, allowed_hosts=allowed_hosts)
    if not isinstance(yt_dlp, str) or not yt_dlp.strip():
        raise ValueError("yt-dlp executable is absent")
    max_bytes = _checked_budget(max_bytes)
    if type(max_height) is not int or not 144 <= max_height <= 4320:
        raise ValueError("maximum video height is out of bounds")
    timeout = _checked_timeout(timeout_seconds, lower=30.0, upper=900.0)
    if type(prefer_h264) is not bool:
        raise ValueError("prefer_h264 must be a boolean")
    attempts = _checked_attempts(attempts)
    backoff = _checked_backoff(backoff_seconds)
    if not callable(sleeper):
        raise ValueError("sleeper must be callable")
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("download directory is not a real directory")
    if any(destination.iterdir()):
        raise ValueError("download directory must be empty")

    cap_megabytes = max(
        1, (max_bytes + (1024 * 1024 - 1)) // (1024 * 1024))
    # Browser cookies, profiles, logins, netrc credentials, and remote
    # components are never read or downloaded: this run is anonymous.
    args = [
        yt_dlp,
        "--ignore-config", "--no-plugin-dirs",
        "--no-playlist", "--playlist-items", "1",
        "--no-mtime", "--no-progress", "--no-continue", "--no-part",
        "--no-cache-dir", "--no-write-info-json",
        "--socket-timeout", "15",
        "--retries", "1", "--fragment-retries", "1",
        "--concurrent-fragments", "1",
        "--merge-output-format", "mp4",
        "--max-filesize", f"{cap_megabytes}M",
        "--format", _format_selector(max_height, prefer_h264=prefer_h264),
        "--paths", str(destination.resolve()),
        "--output", "source.%(ext)s",
        "--", validated,
    ]

    for attempt in range(attempts):
        result = _run_ytdlp(
            args, cwd=destination, timeout=timeout, capture_stdout=False)
        if result.returncode == 0:
            break
        # stderr is used only to classify; it is never echoed (it can contain
        # signed URLs and local paths).
        error = _failure(result.stderr, label="YouTube download")
        _clear_partial_output(destination)
        retryable = (isinstance(error, YtDlpRefusedError)
                     and is_retryable_refusal(result.stderr))
        if not retryable or attempt + 1 >= attempts:
            raise error
        # Equal jitter, matching runner.run_batch: never a tight retry loop,
        # never a synchronised burst of retries across workers.
        sleeper(backoff + random.uniform(0.0, backoff))

    files = list(destination.iterdir())
    if len(files) != 1:
        raise YtDlpError(
            "yt-dlp produced zero, multiple, or unexpected local files")
    source = files[0]
    if source.is_symlink() or not source.is_file():
        raise YtDlpError("yt-dlp produced no regular local video file")
    if source.suffix.lower() not in VIDEO_SUFFIXES:
        raise YtDlpError("yt-dlp produced an unsupported local container")
    size = source.stat().st_size
    if size <= 0:
        raise YtDlpError("yt-dlp produced an empty local video file")
    if size > max_bytes:
        raise YtDlpError("downloaded video exceeds the bounded local size cap")
    return source


def youtube_source_metadata(
    url: str, *, yt_dlp: str = "yt-dlp",
    allowed_hosts: Iterable[str] = DEFAULT_YOUTUBE_HOSTS,
    timeout_seconds: float = 90,
) -> dict[str, Any]:
    """Read pre-download metadata for one allowlisted YouTube video.

    Uses ``--dump-single-json --skip-download``, so no media bytes are fetched.
    The returned shape mirrors the ffprobe metadata adapters
    (``durationSeconds``, ``width``, ``height``, ``bitRate``) and adds
    ``fps``, ``codec``, ``sizeBytes``, ``estimatedBytes``, ``title`` and
    ``formatId``. A field yt-dlp omits stays ``None``; nothing is invented.
    """
    validated = allowlisted_youtube_url(url, allowed_hosts=allowed_hosts)
    if not isinstance(yt_dlp, str) or not yt_dlp.strip():
        raise ValueError("yt-dlp executable is absent")
    timeout = _checked_timeout(timeout_seconds, lower=10.0, upper=600.0)
    args = [
        yt_dlp,
        "--ignore-config", "--no-plugin-dirs",
        "--no-playlist", "--playlist-items", "1",
        "--no-warnings", "--no-progress", "--no-cache-dir",
        "--socket-timeout", "15", "--retries", "1",
        "--dump-single-json", "--skip-download",
        "--", validated,
    ]
    result = _run_ytdlp(
        args, cwd=None, timeout=timeout, capture_stdout=True)
    if result.returncode != 0:
        raise _failure(result.stderr, label="YouTube metadata read")
    payload = result.stdout or b""
    if len(payload) > _METADATA_MAX_STDOUT:
        raise YtDlpError("YouTube metadata exceeded the bounded read budget")
    try:
        info = json.loads(payload.decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError as error:
        raise YtDlpError("yt-dlp returned unusable metadata JSON") from error
    if not isinstance(info, dict):
        raise YtDlpError("yt-dlp returned unusable metadata JSON")
    return _metadata_from_info(info)


def _positive(value: int | None) -> int | None:
    return value if value is not None and value > 0 else None


def _metadata_from_info(info: dict[str, Any]) -> dict[str, Any]:
    duration = finite_float(info.get("duration"))
    if duration is not None and duration <= 0:
        duration = None
    width = _positive(as_int(info.get("width")))
    height = _positive(as_int(info.get("height")))
    fps = finite_float(info.get("fps"))
    if fps is not None and fps <= 0:
        fps = None
    bit_rate = finite_float(info.get("tbr"))
    if bit_rate is None:
        bit_rate = finite_float(info.get("vbr"))
    bit_rate = bit_rate * 1000 if bit_rate is not None else None
    estimated_bytes = (bit_rate * duration / 8.0
                       if bit_rate is not None and duration is not None
                       else None)
    size_bytes = as_int(info.get("filesize"))
    if size_bytes is None:
        size_bytes = as_int(info.get("filesize_approx"))
    if size_bytes is None:
        size_bytes = estimated_bytes
    return {
        "durationSeconds": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "codec": as_text(info.get("vcodec")),
        "bitRate": bit_rate,
        "sizeBytes": size_bytes,
        "estimatedBytes": estimated_bytes,
        "title": as_text(info.get("title")),
        "formatId": as_text(info.get("format_id")),
    }
