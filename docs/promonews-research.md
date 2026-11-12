# Promonews — catalogue + poster-stills research

`scripts/research_promonews.py` enumerates the full Promonews catalogue, measures
YouTube entries through the acquisition engine's cookie-free yt-dlp provider,
and measures exactly **one published poster still per item**. Vimeo references
are recorded as `unsupported-vimeo` and never attempted: the site publishes no
progressive MP4/HLS file, and the only supported video route is YouTube.

The two evidence classes stay separate. `report` distinguishes video-measured,
still-measured, and still-only rows, and still-only evidence never enters the
motion/cut/luma aggregates.

It is a site adapter over `kumiki_reference_lab.acquisition`; the engine owns
allowlisting, bounded retrieval, yt-dlp acquisition, window/still measurement,
evidence assembly, atomic writes, resume checks, and index assembly.

## Catalogue endpoint

```
POST https://www.promonews.tv/api/content/video/_search
Content-Type: application/json
```

The endpoint is an Elasticsearch 6 proxy with **no auth**. It returns
`application/json` in the ES-6 shape: `hits.total` is a number and documents
live in `hits.hits[]._source`.

```bash
PYTHONPATH=src python scripts/research_promonews.py catalog \
  --out research/analysis/promonews/catalog.json
```

### Keep the DSL minimal

The working body is exactly:

```json
{"size":100,"from":0,"query":{"match_all":{}},"sort":[{"created":{"order":"desc"}}]}
```

`track_total_hits`, `bool`, and term filters each made this proxy answer
`HTTP 500 {"message":"Request failed with status code 400"}`. Do not add them.
Client-side filtering is used instead where needed.

A **500 from this endpoint is usually a bad query, not a transient fault**.
The adapter never retries an HTTP status error; it retries only transport and
timeout failures, with bounded backoff. If you see a 500, validate the DSL
before assuming the site is down.

### The 10,000 result-window trap

`size + from` must stay below the ES result window: `from=10000` returns
**HTTP 500**, so naive offset paging silently ends at 10,000 of the 17,805
videos. The adapter continues by sharding on `created` (epoch seconds,
descending). After the last page inside the window it replaces the query with a
bare range and restarts `from` at 0:

```json
{"size":100,"from":0,
 "query":{"range":{"created":{"lt":1699999999}}},
 "sort":[{"created":{"order":"desc"}}]}
```

Range is never wrapped in `bool` (that 500s). Each boundary is logged:

```
catalog shard 1: created < 1699999999, from reset to 0
```

`counts.pagesFetched`, `counts.shards`, `counts.createdBoundaries`, and
`counts.exhausted` record what happened. `/videos` server-rendered HTML and
`__NEXT_DATA__` expose only 14 items and are never used for enumeration.

The boundary is strict (`lt`). If more than one full page of videos shared the
exact boundary second, ties at that second could be dropped; observed rows have
per-video `created` values, and duplicate `nid`s are suppressed defensively.

`POST` bodies are validated against the `www.promonews.tv` allowlist before
sending; there is no generic POST client in the acquisition package, so this
adapter performs the one request itself, like the Motion Design Awards adapter.

## Image policy

Poster derivatives live on the CMS host, not the public host:

```
https://admin.promonews.tv/sites/default/files/...png?itok=<drupal-token>
```

- `admin.promonews.tv` is the **only** image host allowed, and it is the only
  place `allow_query=True` is enabled — Drupal's `?itok=` is a public
  derivative token, not a credential.
- Every other host (including `www.promonews.tv`), `http://`, credentials,
  custom ports, and fragments are refused by the engine.
- Preference is `images[0].thumb`, then `full`, then `original`. Width/height
  come from `images[0].info`.
- `admin.promonews.tv/robots.txt` allows `/sites/default/files` and disallows
  the rest; its API is never touched.
- Downloads are capped at `--max-image-bytes` (default 16 MiB). Bytes are
  deleted in a `finally` block; only hashes and numbers survive.

## Video lane (YouTube only)

Observed `videos[].filemime` is `video/youtube` (19/20 sample) or `video/vimeo`
(1/20).

- A row may declare several embeds. The lane takes the **first YouTube entry**;
  if a row has no YouTube entry it is skipped with `unsupported-vimeo` (Vimeo)
  or `no-video-reference`, and nothing is requested.
- YouTube uses the engine's `YOUTUBE` provider: `allowlisted_youtube_url`, a
  metadata pre-check (`youtube_source_metadata`), then a bounded, cookie-free
  local `yt-dlp` download (`download_via_ytdlp`, `--merge-output-format mp4`,
  H.264/AAC at `height <= 720` preferred, hard byte cap). No cookies, logins,
  browser profiles, `--netrc`, remote components, or DRM/PO-token/nsig
  workaround are used.
- `yt-dlp >= 2026.10` is required; pass an explicit binary with `--yt-dlp`.
- A `YtDlpRefusedError` (`provider-refused`: 403, login-only, unsupported
  client) is a **skip** with reason `provider-refused` and is never retried. A
  transient `YtDlpError` is a **failure** row.
- The whole download → probe → measure cycle runs inside the engine's
  `TemporaryDirectory`; media is deleted even when measurement fails. Records
  assert `mediaRetained: false`.
- `--limit` (default 250) counts **attempted** rows only. Static skips and
  resume skips do not consume it. Rows are processed newest-first by `created`.
- Measurement reuses the engine exactly: `source_metadata` →
  `measure_windows` (which calls `plan_windows`) → `build_video_evidence`.
  The record names `provider`, the canonical `videoUrl` watch URL, and
  `downloadMethod` (`ytdlp-merge`).
- A provider refusal is recorded in the video index as a skip row; only skips
  and numeric evidence are retained.

## Vimeo is never attempted

- Vimeo serves no progressive file that this repository may acquire. No
  cookies, logins, player-API tricks, embed probing, or DRM circumvention are
  used.
- Each catalog row still records `provider` (`youtube` / `vimeo` / `other` /
  `null`) and `unsupportedReason` (`unsupported-youtube` / `unsupported-vimeo`)
  for the stills context. The video lane ignores a Vimeo URL entirely.
- There is **no duration field anywhere** in the catalogue row shape. The
  stills lane stores `durationSeconds` as `null`; the video lane records the
  measured local source duration under `source.durationSeconds`, never a guess
  from a YouTube/Vimeo id.
- There is no Brand/Agency credit role. `credits` is carried as a
  `role → name` list (`{"role": ..., "name": ...}`), with explicit nulls
  preserved rather than invented fields.

## Catalogue row shape

`kumiki.promonews-catalog.v1`:

```
nid, slug, title, publishedDate, createdEpoch, publicUrl, cmsUrl,
provider, unsupportedReason, posterUrl, posterWidth, posterHeight,
durationSeconds, categories[], genres[], tags[], countries[], credits[],
videoUrl
```

`link` points at `https://admin.promonews.tv/videos/YYYY/MM/DD/<slug>`. Both
URLs are stored: `cmsUrl` (CMS host) and `publicUrl`
(`https://www.promonews.tv/videos/YYYY/MM/DD/<slug>`), derived from `link` (or
from `created` + title when the link is absent).

The document also carries a `counts` block: collected rows vs
`counts.reportedTotal` (`hits.total`), `counts.complete`, provider split,
pages/shards/boundaries, and the top 20 genres.

## Commands

All commands assume `PYTHONPATH=src` from the repository root.

```bash
# 1. Full catalogue (17,805 videos; shards past the 10k window)
PYTHONPATH=src python scripts/research_promonews.py catalog \
  --out research/analysis/promonews/catalog.json --delay-seconds 1.0

# 2. YouTube video measurement lane (Vimeo rows are skipped, never attempted)
PYTHONPATH=src python scripts/research_promonews.py collect \
  --catalog research/analysis/promonews/catalog.json \
  --out-dir research/analysis/promonews \
  --acknowledge-rights --resume --jobs 2 --delay-seconds 1.2 \
  --window-count 4 --window-seconds 10 --max-duration-seconds 600 \
  --max-file-bytes 250MiB --yt-dlp /tmp/ytdlp-venv/bin/yt-dlp

# 3. One poster still per row (limit 0 = every remaining row)
PYTHONPATH=src python scripts/research_promonews.py stills \
  --catalog research/analysis/promonews/catalog.json \
  --out-dir research/analysis/promonews \
  --resume --jobs 2 --delay-seconds 0.6 --max-image-bytes 16777216

# 4. Deterministic, read-only report
PYTHONPATH=src python scripts/research_promonews.py report \
  --out-dir research/analysis/promonews --top 20
```

`collect` refuses to run without `--acknowledge-rights`. `--limit` defaults to
250 and counts only attempted rows: Vimeo, no-reference, and resume skips do
not consume it; rows are taken newest-first by `created`. `--limit 0` means all
remaining. `--resume` (default) only reads existing video records; `--refresh`
re-measures.

`--resume` (default) on `stills` also only reads existing records; bytes and
mtimes are left untouched. `--limit N` on `stills` measures the first N pending
rows; `--limit 0` means all remaining. Rows with no usable image get an
explicit `no-usable-poster` skip row, never a crash.

## Evidence rules

`stills/<nid>-<slug>.json`, schema
`kumiki.promonews-still-evidence.v1`:

- `evidenceStatus: "single-published-still-metrics-not-video-measurement"`
- `coverage.isSourceVideoFrame: false`
- `acquisition.method: "poster-still-http"`
- `acquisition.imageRetained: false`
- `limits` deny motion, cut, pacing, timing, sequence, edit-rhythm, aesthetic,
  style, authorship, and quality claims.
- Metrics are measured once at 160×90 RGB by `acquisition.stills.measure_still`:
  mean display luma, saturation, luma histogram, dominant hue family, and edge
  density proxy.

`stills-index.json` (schema `kumiki.promonews-stills-index.v1`) is written
atomically by `run_batch`; it carries `counts.measured/skipped/failed`, the
retained records, skip rows, failures, and the catalogue SHA-256.

`videos/<nid>-<slug>.json`, schema
`kumiki.promonews-video-evidence.v1`:

- `evidenceStatus: "sampled-original-source-pts-metrics-not-expert-reviewed"`.
- `provider: "youtube"`, `videoUrl` is the canonical
  `https://www.youtube.com/watch?v=<id>` form, and `downloadMethod` is
  `ytdlp-merge`.
- `mediaRetained: false` (also `acquisition.mediaRetained: false`).
- `renditionNote` states the source is a platform-encoded YouTube rendition,
  not the work's delivered master.
- `limits` repeat that rendition caveat, deny full-film review, and state that
  the media was deleted and that a provider refusal is never retried.
- `source`, `coverage`, `windows`, and `summary` come straight from
  `source_metadata`, `measure_windows`, and `build_video_evidence`.

`index.json` (schema `kumiki.promonews-index.v1`) is the separate video index.
It carries `counts.measured/skipped/failed`, summary rows, skip rows (including
`unsupported-vimeo`, `resume-existing-record`, and `provider-refused`), failure
rows, and the catalogue SHA-256. It is distinct from `stills-index.json`.

## Report

`report.md` + `aggregate.json` are written from the committed records only and
are byte-identical across repeated runs on unchanged inputs. The report gives:

- provenance: catalogue collected vs `hits.total`, video-measured,
  still-measured, still-only, skipped-no-image, failed, unreadable, and
  provider splits;
- the exact reproduce commands;
- a per-video table derived only from video records (duration, resolution,
  windows, coverage, cuts, luma, saturation, deltas, download method and URL);
- a video-only aggregates section: distributions and coverage computed ONLY
  over video-measured rows; published stills and still-only rows never enter
  motion, cut, luma, or saturation aggregates;
- a table of measured stills with luma/saturation/hue/edge density;
- distributions by genre and category (stills only);
- an explicit “what was measured, and what was not” section (or “why there is
  no motion evidence” when no video records exist);
- explicit non-claims.

## Non-claims

- A published poster still is **not** a video frame; no motion, cut, pacing,
  timing, sequence, or edit-rhythm evidence is claimed from stills.
- A video record measures a platform-encoded YouTube rendition, **not** the
  work's delivered master; every video number describes that rendition only.
- No style, aesthetic quality, mood, lighting, camera/lens, editorial intent,
  authorship, identity, or creative-origin inference is made from the numbers.
- The poster is prepared by Promonews/the CMS, not necessarily by the author.
- No duration was derived from a YouTube/Vimeo id; the catalogue
  `durationSeconds` stays null. Measured durations come only from the acquired
  local source.
- Public availability is not a licence: `rightsStatus` remains
  `review-required`.
- Vimeo embeds were never acquired or probed; YouTube acquisition used a
  cookie-free local `yt-dlp` with no login, cookies, remote components, or
  DRM/PO-token bypass, and provider refusals were never retried.
- Catalogue metadata is self-reported by Promonews and is not independently
  verified.
- Downloaded media and images are never retained: only hashes and numbers
  remain.

## Verification

```bash
python -m py_compile scripts/research_promonews.py
PYTHONPATH=src python -m unittest tests.test_promonews_research tests.test_public_acquisition -q
```
