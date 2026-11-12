# Promonews — catalogue + poster-stills research

`scripts/research_promonews.py` enumerates the full Promonews catalogue and
measures exactly **one published poster still per item**. There is **no video
lane**: every Promonews video reference is a YouTube or Vimeo embed, and the
site publishes no progressive MP4/HLS file. Those providers are recorded as
unsupported and never attempted. The deliverable is therefore catalogue
coverage plus still-only, numeric evidence, clearly labelled as such.

It is a site adapter over `kumiki_reference_lab.acquisition`; the engine owns
allowlisting, bounded retrieval, still measurement, evidence assembly, atomic
writes, resume checks, index assembly, and the pooled batch loop.

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

## Why there is no video lane

- Observed `videos[].filemime` is `video/youtube` (19/20 sample) or
  `video/vimeo` (1/20).
- Neither platform serves a progressive file that this repository may acquire.
  No cookies, logins, player-API tricks, embed probing, or DRM circumvention
  are used.
- Each row records `provider` (`youtube` / `vimeo` / `other` / `null`) and
  `unsupportedReason` (`unsupported-youtube` / `unsupported-vimeo`). Nothing is
  ever attempted.
- There is **no duration field anywhere** in the row shape. `durationSeconds`
  is stored as `null`; it is never guessed from a YouTube/Vimeo id.
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

# 2. One poster still per row (limit 0 = every remaining row)
PYTHONPATH=src python scripts/research_promonews.py stills \
  --catalog research/analysis/promonews/catalog.json \
  --out-dir research/analysis/promonews \
  --resume --jobs 2 --delay-seconds 0.6 --max-image-bytes 16777216

# 3. Deterministic, read-only report
PYTHONPATH=src python scripts/research_promonews.py report \
  --out-dir research/analysis/promonews --top 20
```

`--resume` (default) only reads existing records; their bytes and mtimes are
left untouched. `--refresh` re-measures. `--limit N` on `stills` measures the
first N pending rows; `--limit 0` means all remaining and terminates cleanly
once nothing is left. Rows with no usable image get an explicit
`no-usable-poster` skip row, never a crash.

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

## Report

`report.md` + `aggregate.json` are written from the committed records only and
are byte-identical across repeated runs on unchanged inputs. The report gives:

- provenance: catalogue collected vs `hits.total`, stills measured,
  skipped-no-image, failed, unreadable, and provider split;
- the exact reproduce commands;
- a table of measured stills with luma/saturation/hue/edge density;
- distributions by genre and category;
- a “why there is no motion evidence” section naming YouTube and Vimeo;
- explicit non-claims.

## Non-claims

- A published poster still is **not** a video frame; no motion, cut, pacing,
  timing, sequence, or edit-rhythm evidence is claimed.
- No style, aesthetic quality, mood, lighting, camera/lens, editorial intent,
  authorship, identity, or creative-origin inference is made from the numbers.
- The poster is prepared by Promonews/the CMS, not necessarily by the author.
- No duration was derived from a YouTube/Vimeo id; `durationSeconds` is null.
- Public availability is not a licence: `rightsStatus` remains
  `review-required`.
- YouTube/Vimeo embeds were never acquired or probed.
- Catalogue metadata is self-reported by Promonews and is not independently
  verified.
- Downloaded images are never retained.

## Verification

```bash
python -m py_compile scripts/research_promonews.py
PYTHONPATH=src python -m unittest tests.test_promonews_research tests.test_public_acquisition -q
```
