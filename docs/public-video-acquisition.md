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
| `windows` | `plan_windows`, `measure_windows`, `summarize_probes`, `cut_validity`, `build_video_evidence` |
| `census` | `scan_full_runtime` (two whole-file ffmpeg passes: scene candidates with source PTS, then a fixed-cadence 160×90 appearance series), `build_census_evidence`, `CENSUS_SCHEMA` (see `docs/full-film-census.md`) |
| `reporting` | `cut_columns`, `coverage_distribution`, `comparability_block`, `duplicate_summary`, `unique_media_rows`, `aggregate_extremes`, `still_decode_dimensions` |
| `stills` | `measure_still`, `compute_still_metrics`, `dominant_hue_family`, `decode_still_rgb`, `infer_decoded_dimensions`, `still_image_format`, `build_still_evidence`, `still_quality_flags` (plus `still_record_flags` / `still_has_quality_flags` / `still_quality_counts` / `still_quality_summary` for report consumers) |
| `store` | `write_json_atomic`, `safe_slug`, `resume_matches`, `build_index`, `utc_now` |
| `runner` | `run_batch` (sequential or pooled, jittered politeness delay, resume skip, per-item failure isolation, atomic index refresh), `BatchSkip` (raise from `run_one` to record a skip row instead of a failure), `safe_error` |

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

## Interpreting cut candidates

A `cutCandidatePts` entry is an **ffmpeg scene-score exceedance** inside one
sampled window. It is a *candidate*, not an edit: fast movement, flashes,
strobe lighting, transitions, and compression can all exceed the threshold.
Consequently `cutCandidateRatePerMinute` (and the older `cutCandidates` count)
describe candidate density in sampled windows, not an edit rate for the film.
A record whose `validityFlags` is non-empty **must not enter a ranking**; the
flag says the candidate count is not measuring cuts, not that the film is
poorly edited.

`cut_validity(probes, *, sampled_seconds, fps=None, timebase=None,
sampled_fraction=None)` is the pure derivation and `summarize_probes` calls it.
Because it reads only the probe payloads (`cutCandidatePts`,
`sampledWindowSummary`, `sampledFramePairs`), an audit can recompute the same
numbers offline from a stored record. `fps` accepts a number or a
`{"numerator", "denominator"}` rational; `timebase` accepts a seconds-per-tick
number or the rational dict stored on each probe. When `timebase` is omitted
the first probe's `sourceTimebase` is used.

| field | exact definition |
| --- | --- |
| `cutCandidateCount` | size of the sorted, de-duplicated union of `cutCandidatePts` across windows |
| `medianCutGapSeconds` | median gap between consecutive union candidates in source seconds (`null` with < 2 candidates or no timebase) |
| `medianCutGapFrames` | raw median gap in seconds × fps, rounded to 6 decimals, when fps is available; else `null` |
| `minCutGapSeconds` | smallest consecutive gap in source seconds |
| `burstFraction` | fraction of candidates whose nearest neighbour is < 0.25 s; `null` with < 2 candidates |
| `withinShotPairs` | sum of each window's `sampledWindowSummary.withinShotComparedPairs` |
| `cutSeparatedPairs` | sum of each window's `sampledWindowSummary.cutSeparatedPairs` |
| `deltaBasisPairs` | number of `sampledFramePairs` entries with a finite `meanAbsoluteDisplayRgbDeltaPerSecond` (the actual basis for the mean delta) |
| `cutsPerMinuteCi95` | `[low, high]` Poisson 95% interval on candidates per sampled minute |
| `validityFlags` | sorted list of the flags below (always present, `[]` when clean) |

`cutsPerMinuteCi95` uses the exact Garwood count interval
(`P(X ≤ n-1 \| low) = 0.975`, `P(X ≤ n \| high) = 0.025`) divided by sampled
minutes. When at least three windows exist and the mean window count is
positive, each half-width is widened by `sqrt(designEffect)` with
`designEffect = max(1.0, sampleVariance(windowCounts) / mean(windowCounts))`.
With zero observed candidates the interval is exactly
`[0, 3.689 / sampledMinutes]`.

| flag | measured condition |
| --- | --- |
| `non-edit-scene-change` | `medianCutGapFrames < 3` or `medianCutGapSeconds < 0.10` |
| `burst-heavy` | `burstFraction > 0.5` |
| `sparse-delta-basis` | `deltaBasisPairs < 8` |
| `no-delta-basis` | `deltaBasisPairs == 0` |
| `low-coverage` | supplied `sampled_fraction` < 0.25 |
| `short-sample` | `sampled_seconds < 20` |
| `no-cuts-observed` | `cutCandidateCount == 0` |

These are **flags, not verdicts**: the record keeps every measured number and
the flags travel with it so a report can exclude the row or qualify the rate.

## Reporting contract

Every adapter's `report` command assembles its tables from
:mod:`kumiki_reference_lab.acquisition.reporting`, so the same four rules apply
everywhere:

- **Rankability gate.** `cut_columns(record)` returns `rankable: false` when
  any of `non-edit-scene-change`, `burst-heavy`, `no-delta-basis`, or
  `short-sample` is present. Cut-candidate minima/maxima are computed only over
  rankable records; the excluded count is stated next to the aggregate. A
  reported maximum always names its record id and its `validityFlags`, so a
  strobe (for example a 60 fps record whose median candidate gap is 3 frames)
  can no longer surface as the fastest-cut work.
- **Dedupe.** Video aggregates dedupe by media hash with
  `duplicate_summary(records, "source.mediaSha256")` and report `n` before and
  after dedupe, plus the number of duplicate groups. A catalogue that lists the
  same upload twice therefore states its unique-work count.
- **Comparability block.** `comparability_block(...)` always returns
  `poolable: false`, the fixed `comparableWithin` / `notComparableTo` lists,
  the echoed inputs (catalogue size, measured count, provider/rendition/
  resolution/fps/bitrate counts, coverage, duplicate groups, still overlap) and
  a plain-sentence `caveats` list. Cross-site pooling is never implied.
- **Coverage block.** `coverage_distribution(rows)` reports min/p10/median/
  p90/max coverage, the below-20% and below-10% shares, and the median
  unobserved gap between sampled windows. A pooled "18% of runtime" line is
  therefore accompanied by the distribution that produced it.

Still tables show the source `img_w×img_h` beside the `decode_w×decode_h` the
still was actually measured at; when the record stores no decode size it is
derived from the aspect-preserving `160×90` rule and labelled as derived.

## Still quality flags

`still_quality_flags(metrics, *, width=None, height=None)` returns a sorted list
of zero or more documented flags from a still's stored metrics:

| flag | measured condition |
| --- | --- |
| `near-black-placeholder` | mean luma < 0.05 and saturation < 0.02 |
| `near-white-placeholder` | mean luma > 0.97 and saturation < 0.02 |
| `near-uniform` | `displayLumaStdDev` < 0.01 |
| `degenerate-histogram` | one `lumaHistogram` bucket holds > 0.99 of pixels |
| `low-information-resolution` | source `width × height` < 100,000 (both given) |

These are **flags, not verdicts**: the record keeps every measured number and
each consumer decides what a flag means for its use. `build_still_evidence`
writes them to `still.qualityFlags` (always present; `[]` when clean). A lane
that treats a flag as non-evidence raises `BatchSkip(reason)` from `run_one`, so
the item lands in the index's `skips` list rather than `records` or `failures`.

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
