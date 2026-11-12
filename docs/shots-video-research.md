# shots.net video and still research

Ephemeral, source-hashed measurement of publicly listed shots.net clips and
their published poster stills. The collector is
`scripts/research_shots.py`; it is the only shots.net component that touches the
network or downloads media. Every downloaded byte lives in a temporary
directory deleted in a `finally` block, so only numeric evidence, hashes, and
catalog metadata are committed.

All mechanics come from `src/kumiki_reference_lab/acquisition/`
(see `docs/public-video-acquisition.md`). This document covers only the
shots.net adapter.

## Source

- Search/catalog: `GET https://shots.net/search`, public JSON, no auth, no
  cookies, no bot challenge.
- Query used for every page:

  ```text
  /search?types[0]=clip&as_json=1&limit=100&offset=<n>&sort=newestFirst
  ```

  `limit` is kept at or below 100. `hits` is the total clip count (observed:
  **40,908**). `pagination.next` is present but the adapter advances `offset`
  itself.
- Clip page: `https://shots.net/work/<urlname>` (the raw `__url`).
- Recorded project URL: `https://shots.net/news/view/<urlname>`.
- Embed URL: `https://shots.net/embed/clip/<id>`.
- Requests are spaced by at least 0.6 s plus equal jitter; the video lane
  defaults to 1.2 s and the stills lane to 0.5 s. `--jobs 1` is the default.

### Observed request/response shapes

`streams` has two shapes:

```jsonc
// dict: a 1280x720 web rendition (~9 MB / 28 s); observed on a minority
"streams": {
  "1": {
    "status": 3,
    "file": {
      "remote_address": "https://d1ko11x0ybxl0h.cloudfront.net/...-1280x720.2500.mp4",
      "size": 9249657,
      "mediaInfo": {"Duration": "28.098", "FrameRate": "29.970"}
    }
  }
}

// list: one higher-bitrate platform-encoded source (40-80 MB)
"streams": [
  {
    "status": 3,
    "file": {
      "remote_address": "https://proxy.slatecdn.net/media/.../<uuid>.mp4",
      "size": 39000000,
      "mediaInfo": {"Duration": "60.0"}
    }
  }
]
```

When neither rendition exists, `original_file.remote_address` is usually a
signed `https://app.extremereach.com/Media/Download/<UUID>?profile=…&useCDN=true`
URL. It 302-redirects to a signed CloudFront URL on
`d2290ppie00mze.cloudfront.net` (`AWSAccessKeyId` / `Expires` / `Signature`,
`response-content-disposition=attachment`). That file is the original
1920x1080, 40-80 MB. Some `original_file` values point directly at
`d1ko11x0ybxl0h.cloudfront.net` with no query string.

Catalog metadata is self-reported by shots.net and is not independently
verified.

## Rendition ladder

The adapter picks the first usable candidate in this fixed order and never
rewrites a URL to guess another variant:

| order | `rendition` | source |
| --- | --- | --- |
| 1 | `720p-web-rendition` | `streams["1"].file` when `status == 3` |
| 2 | `platform-encoded-source` | first `streams[]` entry with `status == 3` and an allowlisted file host |
| 3 | `original-download` | `original_file` (signed `app.extremereach.com` or signed/unsigned CloudFront) |

A candidate is *usable* only when it is ready and its URL passes the engine's
allowlist policy. The shots media lane enables the engine's `allow_query`
opt-in for its host list, so a signed `?profile=…&useCDN=true` original and its
signed CloudFront redirect are both first-class candidates. A signed original
is now a real `videoUrl` instead of `null`. Every observed candidate is
retained in the catalog's `candidates` list as
`{"url", "host", "bytes", "kind"}`, and the chosen one is projected into
`videoUrl`, `videoBytes`, and `videoRendition`. The video record also keeps the
chosen candidate and the full candidate list under `media`.

Allowlisted media hosts:

```text
d1ko11x0ybxl0h.cloudfront.net
proxy.slatecdn.net
app.extremereach.com
d2290ppie00mze.cloudfront.net
```

The redirect host is passed explicitly so the engine re-validates every
redirect. A redirect to any other host is refused.

### Signed originals and redirects

The engine defaults to refusing query strings. This adapter opts in only for
the media host list above (`allowlisted_video_url(..., allow_query=True)` and
`download_media(..., allow_query=True)`), because the original download path is
a public, cookie-free, cryptographically scoped pair:

```text
app.extremereach.com/Media/Download/<UUID>?profile=…&useCDN=true
  -> 302 -> d2290ppie00mze.cloudfront.net/...?AWSAccessKeyId=…&Expires=…&Signature=…
```

Allowlisting and redirect re-validation still apply with the same opt-in: a
signed redirect is followed with its query string intact, but a redirect to any
host outside the list is refused. The adapter does not strip the query, forge a
signature, cache a signed URL, or rewrite the URL. Images stay on the stricter
default (`allow_query=False`): the observed poster URLs are unsigned, so the
stills lane refuses query strings unchanged.

When no ladder rung is usable, `videoUrl` is `null` and the collect lane records
a `no-allowlisted-public-rendition` skip. That is a pre-download selection
outcome, distinct from a failure row, which means a rendition was chosen and the
attempted acquisition raised.

## Catalog: slim normalized projection

`catalog` writes `kumiki.shots-catalog.v1` with `retrievedOn`, `sourceHost`,
`endpoint`, the query, `totalReportedHits`, `clipCount`, and one row per clip.
Rows are deterministic (publication date descending, then clip id descending)
and deliberately slim — no raw API object, no `brand.logo`, no `mediaInfo`
blobs, no `encoding_media_info`, no `streams`/`thumbnails` trees.

Each row keeps only:

```text
id, slug, title, publicationDate, durationSeconds, originalWidth,
originalHeight, aspectRatio, brandName, clientName, agencyName,
productionCompanies[], artists[], categories[], contentTypes[], awards[],
downloadAllowed, embedUrl, articleUrl, thumbnailUrl, videoUrl, videoBytes,
videoRendition, year, candidates[{url,host,bytes,kind}]
```

This is roughly 0.7-1.3 KB per row for the observed URL lengths (the offline
test asserts a per-row ceiling), so a 40,908-row catalog is tens of megabytes,
not the raw multi-hundred-megabyte API payload.

`thumbnailUrl` prefers the primary `thumbnail` file, then the first
`thumbnails[]` entry, then an allowlisted `image_player_url`. Non-allowlisted
posters are dropped. `videoUrl` is `null` when no ladder candidate is usable.

## Video lane (`collect`)

For each clip in the requested catalog slice:

1. Reject from catalog metadata before any bytes move when
   `durationSeconds > --max-duration-seconds` (default 600) or
   `videoBytes > --max-file-bytes` (default 250 MiB). These become skip rows.
2. `TemporaryDirectory` → `download_media(..., provider=DIRECT,
   allowed_hosts=MEDIA_HOSTS, allow_query=True, ...)`; the engine re-validates
   redirects, caps the byte stream, and enforces the duration budget. Signed
   originals are large (40-80 MB and up); `--max-file-bytes 250MiB` and
   `--max-duration-seconds 600` still reject from catalog metadata first, and
   the `size` field in `original_file` feeds that pre-download estimate.
3. `source_metadata` + `inspect_source` on the local file for sha256, size,
   stream index, average/nominal frame rate, timebase, codec, resolution.
4. `plan_windows` + `measure_windows`: `--windows 4`,
   `--window-seconds 10`, `--max-samples 12`, 160x90 RGB,
   `--image-translation` off by default.
5. `build_video_evidence` plus clip identity, then one atomic
   `videos/<id>-<slug>.json`.
6. The `TemporaryDirectory` is deleted in `finally` on success and failure.

Record schema: `kumiki.shots-video-evidence.v1`.

```text
schemaVersion, clipId, slug, clip{...}, media{chosen, candidates},
source{...}, acquisition{provider, method, rendition, url, bytes, ...},
coverage, windows, summary, evidenceStatus, rightsStatus, rights{basis,status,note},
limits, generatedAt
```

`acquisition.provider` is `direct-mp4`; `method` is the engine label
(`http-download`); `acquisition.mediaRetained` is always false.

## Stills lane (`stills`)

For every remaining clip in the local catalog file:

1. Choose one allowlisted poster (`d1ko11x0ybxl0h.cloudfront.net` or
   `images.slatecdn.net`). No video is fetched.
2. `download_http` into a `TemporaryDirectory`, probe dimensions, decode once
   at 160x90 RGB, compute canonical `acquisition.stills.measure_still` metrics,
   delete the image in `finally`.
3. Write one atomic `stills/<id>-<slug>.json`.

Record schema: `kumiki.shots-still-evidence.v1`, with
`evidenceStatus: "single-published-still-metrics-not-video-measurement"`,
`coverage.isSourceVideoFrame: false`,
`acquisition.method: "poster-still-http"`, `imageRetained: false`, the same
`clip` identity block as video records, and limits that deny motion, cut,
pacing, sequence, and timing claims.

`stills` reads only the catalog file; it never re-queries the search endpoint.
`--limit 0` (the default) means **all remaining** clips, paging the catalog
locally and terminating when a page is empty. Use `--resume` to skip existing
records; `--refresh` re-measures.

## Output layout

```text
research/analysis/shots/
  catalog.json                 # kumiki.shots-catalog.v1 (slim rows)
  index.json                   # kumiki.shots-index.v1 (video lane)
  stills-index.json            # kumiki.shots-stills-index.v1 (stills lane)
  videos/<id>-<slug>.json      # kumiki.shots-video-evidence.v1
  stills/<id>-<slug>.json      # kumiki.shots-still-evidence.v1
  report.md                    # read-only report
  aggregate.json               # kumiki.shots-aggregate.v1
```

Indexes are written atomically and carry `catalogSha256`, counts, summary rows,
skip rows, and failure rows.

## Measured quantities

Video records report only source-PTS numeric evidence from sampled windows:
cut candidates and cuts per minute, mean display-RGB luma and saturation
proxies, mean within-shot RGB delta per second, sampled frame counts, coverage
fraction, source identity (sha256, bytes, stream index, fps, timebase, codec,
resolution), and the acquisition/rendition identity.

Still records report one image's dimensions, sha256, bytes, display-RGB
luma/saturation proxies, luma histogram, dominant hue family, and edge-density
proxy.

## Explicit non-claims

- Windows are sampled, not a full-clip review; `fullRuntimeMeasured` is false
  for every video record.
- Numbers describe the platform's published web rendition (or the
  platform-encoded source / original download), not the site's masters.
- Display-RGB luma/saturation, cut candidates, and edge density are numeric
  proxies, not style, mood, quality, lighting, camera/lens, editing-intent,
  authorship, identity, or creative-origin labels.
- A published poster still is not a video frame. Stills carry no motion, cut,
  pacing, sequence, timing, or edit-rhythm evidence and never enter the video
  aggregates.
- Catalog metadata is self-reported by shots.net and is not independently
  verified.
- Public availability is not a licence. `rightsStatus` remains
  `review-required`.
- **`download_allowed` was false for every observed clip. The adapter records
  that fact; it does not treat public reachability as a redistribution grant,
  and it does not work around the flag.**
- No cookies, logins, tokens, or DRM circumvention were used.
- Downloaded media, frames, thumbnails, and audio are never retained.

## Exact commands

```bash
# Slim catalog (500 newest clips by default).
PYTHONPATH=src python scripts/research_shots.py catalog \
  --out research/analysis/shots/catalog.json \
  --limit 500 --offset 0

# Filter by publication date while paging newest-first.
PYTHONPATH=src python scripts/research_shots.py catalog \
  --out research/analysis/shots/catalog.json \
  --limit 500 --since 2026-09-01

# One pageable slice of video measurement.
PYTHONPATH=src python scripts/research_shots.py collect \
  --catalog research/analysis/shots/catalog.json \
  --out-dir research/analysis/shots \
  --limit 25 --offset 0 --acknowledge-rights

# Stills for every remaining clip (resume-safe).
PYTHONPATH=src python scripts/research_shots.py stills \
  --catalog research/analysis/shots/catalog.json \
  --out-dir research/analysis/shots --resume

# Read-only report.
PYTHONPATH=src python scripts/research_shots.py report \
  --out-dir research/analysis/shots \
  --catalog research/analysis/shots/catalog.json

# Offline no-op (writes only the empty index to the chosen out-dir).
PYTHONPATH=src python scripts/research_shots.py collect \
  --out-dir /tmp/shots-dry --limit 0 --acknowledge-rights
```

`collect --limit 0` is a valid offline no-op. `stills --limit 0` is the
opposite by design: it means all remaining clips.

## Verification

```bash
python -m py_compile scripts/research_shots.py
PYTHONPATH=src python -m unittest tests.test_shots_research tests.test_public_acquisition -v
```

The offline suite covers catalog paging/normalization, the rendition ladder for
dict/list/original shapes, signed-original selection, rejection of non-ready and
non-allowlisted streams, deterministic record rebuilds, resume/refresh, failure
cleanup, atomic indexes, report determinism and still/video separation,
`--limit 0` semantics, the rights gate, signed-URL opt-in, and redirect refusal.
