# Public video acquisition and numeric measurement (generic)

`kumiki_reference_lab.acquisition` is the reusable, site-agnostic engine for
"enumerate public videos on a site, acquire them ephemerally, measure them
numerically, keep the evidence and delete the bytes" work.

It contains no knowledge of any particular website: no endpoints, no hostnames,
no provider vocabulary, no schema strings. Those belong to a *site adapter* — a
small script that enumerates candidates and supplies policy. The reference
adapter is `scripts/research_motiondesignawards.py`
(see `docs/motiondesignawards-video-research.md`).

## Safety contract

Enforced once, for every caller:

- HTTPS only, host allowlist passed by the caller. Entries are exact hosts
  (`media.example`), explicit subdomain suffixes (`.cdn.example`), or the
  wildcard `"*"`, which admits any public DNS name. The wildcard is the current
  project-wide policy for research adapters. It relaxes only the host check. No
  credentials, custom ports, fragments, IP literals, loopback or single-label
  names, or implicit subdomains. Query strings are refused by default; a
  caller can opt in per URL-operation with `allow_query=True` for signed,
  cookie-free CDN URLs (see below). Every redirect is re-validated with the
  same allowlist and the same `allow_query` setting.
- Byte- and duration-capped retrieval. Media lands only in a directory the
  caller owns.
- No cookies, logins, tokens, DRM circumvention, or access-control bypass. A
  signed URL is not a token login: it is a public, cryptographically scoped CDN
  grant. Public availability is not a licence: the caller supplies its own
  rights basis and attestation text, and records keep
  `rightsStatus: review-required`.
- YouTube acquisition is yt-dlp-mediated, cookie-free and login-free. No
  `--cookies-from-browser`, no `--netrc`, no credentials, no DRM/PO-token/nsig
  workaround beyond what stock yt-dlp does by itself. A hard provider refusal
  (login-only, private, members-only, bot-check, unsupported client) is
  `provider-refused` and is never retried. The intermittent 403/CDN-data class
  is also `provider-refused`, but gets a bounded retry with backoff (see below).
  Media is always ephemeral. `yt-dlp >= 2026.10` is required: older builds
  return HTTP 403 on public YouTube videos with the stock client.
- The package never deletes your files. Ephemeral deletion is the caller's job
  (`TemporaryDirectory` around the whole acquire → measure → record cycle, so
  partial downloads are removed on failure too).
- Only numeric measurements, hashes and metadata leave the package. Builders
  return neutral payloads; the caller supplies schema versions, limits, and
  subject identity fields.

## API map

| module | what it gives you |
| --- | --- |
| `media` | `allowlisted_url` / `allowlisted_video_url` / `allowlisted_image_url` (all accept `allow_query`), `fetch_bytes`, `fetch_text`, `download_http`, `plan_hls_download`, `download_media` (HLS stream-copy remux, direct GET, or bounded yt-dlp), `media_target`, `image_target`, `check_downloaded` |
| `ytdlp` | `allowlisted_youtube_url` (single-video URL policy), `download_via_ytdlp` (bounded 403 retry), `youtube_source_metadata` (`--dump-single-json --skip-download`), `classify_ytdlp_failure`, `is_retryable_refusal`, `YtDlpError` / `YtDlpRefusedError` |
| `probe` | `run_ffprobe_json` (retry/backoff), `remote_source_metadata`, `ranged_source_metadata` (bounded `Range` fallback for flaky hosts), `source_metadata`, `probe_image_dimensions`, `metadata_from_probe`, `finite_float` / `as_int` / `as_text` |
| `windows` | `plan_windows`, `measure_windows`, `summarize_probes`, `build_video_evidence` |
| `stills` | `measure_still`, `compute_still_metrics`, `dominant_hue_family`, `decode_still_rgb`, `infer_decoded_dimensions`, `still_image_format`, `build_still_evidence` |
| `store` | `write_json_atomic`, `safe_slug`, `resume_matches`, `build_index`, `utc_now` |
| `runner` | `run_batch` (sequential or pooled, jittered politeness delay, resume skip, per-item failure isolation, atomic index refresh), `safe_error` |

Provider constants: `HLS`, `DIRECT`, `YOUTUBE`; method labels:
`METHOD_HLS_REMUX`, `METHOD_HTTP_DOWNLOAD`, `METHOD_YTDLP_MERGE`.

### Signed URLs: `allow_query`

Generic scraping policy refuses a query string because it often carries
session state or an opaque token that the engine must not replay. Some public
CDNs instead hand out *signed* URLs — CloudFront `AWSAccessKeyId` / `Expires` /
`Signature`, or an origin such as `app.extremereach.com/...?profile=…&useCDN=true`
that 302s to one. Those URLs are cookie-free and cryptographically scoped, so
they are safe to fetch when the caller explicitly opts in:

```python
download_media(url, DIRECT, directory, allowed_hosts=MEDIA_HOSTS,
               max_bytes=..., allow_query=True)
```

The opt-in is per call and defaults to `False`, so existing callers keep the
strict policy byte-for-byte. It is threaded through `allowlisted_url`,
`allowlisted_video_url`, `allowlisted_image_url`, `fetch_bytes`, `fetch_text`,
`download_http`, `plan_hls_download` (master, variant, and audio URLs),
`ffprobe_remote_json`, `remote_source_metadata`, `ranged_source_metadata`, and
`download_media`.

What does **not** change:

- The scheme must still be `https`.
- The host must still match the caller's allowlist exactly, including the
  leading-dot subdomain rule.
- Credentials, custom ports, IP literals, loopback names, leading/trailing-dot
  host tricks, and fragments are still refused.
- Redirects are re-validated against the same allowlist **and** the same
  `allow_query` setting, and the redirect target's query string is preserved.
- A signed URL is never cached across calls; it expires. Error text is
  redacted by `safe_error`, which strips `Signature=`, `AWSAccessKeyId=`, and
  related signing values in addition to full URLs.

Enable it for one adapter's media allowlist only when that host actually
requires signed delivery. Keep it off for poster/image lanes unless a signed
poster is the only published URL.

## YouTube acquisition (yt-dlp-mediated)

`YOUTUBE` is a third provider beside `HLS` and `DIRECT`. `download_media`
validates the URL through `allowlisted_youtube_url` (exactly `/watch?v=<11>`,
`/shorts/<11>`, `/embed/<11>`, or `youtu.be/<11>`; playlists, channels and live
URLs are refused), reads metadata first so an over-long source is rejected
before any media byte moves, then calls `download_via_ytdlp` and returns
`(path, METHOD_YTDLP_MERGE)`.

The invocation is stock and bounded:

- one playlist item, one concurrent fragment, one retry, one fragment retry,
  15 s socket timeout, `--merge-output-format mp4`, a byte cap, and
  `--paths <destination> --output source.%(ext)s` into an empty, real
  (non-symlink) directory the caller owns. Those are yt-dlp's own flags; the
  bounded engine-level 403 retry described below is separate and capped at
  three total attempts;
- `--ignore-config --no-plugin-dirs`, so local config and plugins cannot widen
  the run;
- `--format` prefers an H.264/AAC stream at `height <= 720` (the analyzers
  decode frames with ffmpeg; AV1 works but is slower, and the engine must not
  silently prefer it), falling back progressively. `prefer_h264=False` drops
  the codec preference;
- **no cookies, no logins, no `--cookies-from-browser`, no `--netrc`, no
  remote component downloads, no DRM/PO-token/nsig workaround.**

`yt-dlp` stderr is captured only to classify the failure and is never echoed
(it can contain signed URLs and local paths). Two refusal classes are
distinguished internally while keeping the public vocabulary unchanged:

- **Hard refusal** — `sign in` / bot-check, `logged-in` / `login required`,
  `private video`, `members-only`, `requires payment`, `unsupported client`,
  outdated client, `nsig`, PO token. Raises `YtDlpRefusedError`
  (`reason == "provider-refused"`) on the first attempt; **never retried**,
  because the same request will fail identically.
- **Retryable 403/CDN-data class** — `403 forbidden`, `http error 403`, any
  standalone `403`, `unable to download video data`. Also
  `provider-refused` when it ultimately fails, but it is first retried a
  bounded number of times, because YouTube intermittently refuses one stream or
  fragment while the same public URL succeeds moments later.

Everything else is a `YtDlpError` with `reason == "transient"`. Both are
`ValueError` subclasses, so existing adapter error handling keeps working.
`safe_error` also redacts signature-like query material (`expire`, `ip`, `sig`,
`nsig`, `sparams`, `ei`, …) that survives outside a full URL.
`is_retryable_refusal(stderr)` exposes the split for tests and adapters;
`classify_ytdlp_failure(stderr)` still returns only `"provider-refused"` or
`"transient"`.

### Bounded 403 retry policy

```python
download_via_ytdlp(url, directory, ..., attempts=2, backoff_seconds=6.0)
download_media(url, YOUTUBE, directory, ..., attempts=2, backoff_seconds=6.0)
```

- `attempts` includes the first try and is clamped to `1..3`; `attempts=1`
  disables retrying. Both defaults preserve existing adapter call sites: HLS
  and direct downloads ignore these parameters entirely and issue exactly the
  same requests as before.
- Only the 403/CDN-data class retries. Hard refusal markers are raised on the
  first attempt, even if the same stderr also mentions 403.
- Between attempts the engine deletes any partial output from the failed
  attempt, then sleeps `backoff_seconds + uniform(0, backoff_seconds)` (equal
  jitter, the same idea as `run_batch`). `sleeper` is injectable so tests stay
  offline.
- A retry that also fails raises `YtDlpRefusedError` exactly as before; a
  different class on a later attempt raises its own error.

A 403 retry is **not a bypass**. It sends the identical anonymous public
request again after a delay. Nothing is added: no cookies, browser profiles,
logins, API keys, PO tokens, nsig extraction, `--remote-components`, or proxy
rotation. The retry exists because YouTube's own front end intermittently
throttles a single stream under burst load, not to defeat an access control.
If the video is genuinely gated, its stderr carries a hard marker and no retry
happens.

`youtube_source_metadata` returns the neutral ffprobe-shaped dict plus `fps`,
`codec`, `sizeBytes`, `estimatedBytes`, `title` and `formatId`; omitted fields
stay `None` rather than being invented. `download_media` uses its
`durationSeconds` for `max_duration_seconds`; adapters can call it directly to
pre-reject oversize videos too.

**`yt-dlp >= 2026.10` is required.** Older builds (for example the system
2026.03.17) return HTTP 403 on public YouTube videos with the stock client. Use
an explicit path so a stale system binary cannot be picked up by accident:

```bash
python -m venv /tmp/ytdlp-venv && /tmp/ytdlp-venv/bin/pip -q install -U yt-dlp
```

Media remains ephemeral: run the whole acquire → measure → delete cycle inside
one `TemporaryDirectory`, exactly as for HLS and direct downloads.

## Adapter recipe

A new site needs only this:

1. **Enumerate candidates** into neutral dicts with a stable `id`, a page URL, an
   optional media URL, and whatever site metadata you want in the record.
2. **Declare**: media/image host allowlists, delivery mode per candidate
   (`HLS`, `DIRECT`, or `YOUTUBE`), schema strings, evidence-status strings,
   `limits` text, rights basis/note, and the identity field `--resume` matches
   on.
3. **Write `run_one(candidate)`** as
   `TemporaryDirectory` → `allowlisted_video_url` (`allow_query=True` only when
   the host requires signed URLs; YouTube URLs go through
   `allowlisted_youtube_url` instead) → `remote_source_metadata` or
   `youtube_source_metadata` (reject duration/size before download) →
   `download_media(...)` with `allow_query=...` for signed CDNs or
   `yt_dlp="/explicit/path/to/yt-dlp"` for YouTube → `source_metadata` →
   `measure_windows` → `build_video_evidence` (+ your identity fields and
   schema) → `write_json_atomic`. Deletion happens in the `finally` of the
   context manager.
4. **Drive the batch** with `run_batch(items, run_one=..., index_path=...,
   build_index=..., summary_row=..., skip_row=..., jobs=..., delay_seconds=...)`.

Prefer a research script (as above) over a new CLI command unless the workflow is
generically useful without a site.

## Rules of evidence

- Report measured quantities only: source PTS, frame counts, cut candidates,
  display-RGB luma/saturation proxies, inter-frame deltas, still-image metrics.
- Never claim style, intent, authorship, quality, or identity from numbers.
- A single published still is **not** a video frame; mark it
  `isSourceVideoFrame: false` and deny motion/cut/timing evidence in `limits`.
- Unsupported providers (e.g. a host that requires login) get an explicit
  `unsupported-*` skip row. Do not attempt a bypass.

## Verification

```bash
PYTHONPATH=src python -m unittest tests.test_public_acquisition -v
# Site vocabulary stays out of the engine. `yt-dlp` is the sanctioned YouTube
# mechanism and is expected to appear; site names are not.
grep -rin "motiondesignawards\|keyfram\|cloudflare\|vimeo" src/kumiki_reference_lab/acquisition/   # must be empty
PYTHONPATH=src python -c "import kumiki_reference_lab.acquisition as a; print(sorted(a.__all__))"
```

One live YouTube smoke, with an explicit yt-dlp path and ephemeral media:

```bash
PYTHONPATH=src python - <<'PY'
import subprocess, tempfile
from pathlib import Path
from kumiki_reference_lab.acquisition import YOUTUBE, download_media

URL = "https://www.youtube.com/watch?v=ZfJOq_B_XBM"
with tempfile.TemporaryDirectory(prefix="kumiki-youtube-smoke-") as tmp:
    path, method = download_media(
        URL, YOUTUBE, Path(tmp), allowed_hosts=("*",),
        max_bytes=250 * 1024 * 1024, max_height=720,
        yt_dlp="/tmp/ytdlp-venv/bin/yt-dlp")
    print(method, path.name, path.stat().st_size)
    subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                    "format=duration,size,bit_rate:stream=codec_name,width,height",
                    "-of", "json", str(path)], check=True)
# The TemporaryDirectory deletes the video before this script exits.
PY
```

## Known gaps (deliberate)

- No generic HTTP POST/JSON client: catalogue APIs with bespoke auth-free
  GraphQL stay in the site adapter.
- `run_batch`'s progress callback receives no success payload, so adapters keep a
  slug → detail map for operator log lines.
- `build_index` does not seed already-measured rows; adapters pass retained rows
  through their own `build_index` closure.
- `safe_error` redacts only the package's own scratch prefixes; adapters add
  their own patterns via `redact=`.
