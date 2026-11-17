# Full-film census: whole-runtime cuts and fixed-cadence appearance

Windowed evidence samples four 10 s windows per video. That is enough for a
probe, but `cutsPerMinute` then describes the windows, not the film. The bias is
not small: a 300 s film leaves roughly 76 s unobserved between windows, and an
identical 10 s montage is hit 100% of the time inside a 30 s clip but missed
63% of the time inside a 300 s film. A window rate therefore cannot be compared
across runtimes.

The census is the same measurement over the whole runtime. The engine already
downloads each clip and already owns the ffmpeg scene filter, so the extra cost
is one more decode pass — not a new acquisition pipeline.

## What it fixes

- Every cut candidate in the file is counted, with its original source PTS.
- `cutsPerMinute` has the full runtime as its denominator, so a 30 s clip and a
  300 s film are on the same basis.
- `medianCutGapFrames` and `burstFraction` expose strobe-like candidate
  density instead of reporting it as an edit rate.
- Appearance is still sampled, but at a fixed 1 s cadence over the entire file,
  then time-weighted, so `decodeCoverageFraction` is exactly `1.0` rather than
  a window fraction.

## The scan passes

`scan_full_runtime(path, ...)` runs two whole-file ffmpeg passes plus one bounded
cut-window pass:

1. **Scene candidates.** `select='gt(scene,0.25)',showinfo` over the whole
   file, mapped to the chosen video stream. The `showinfo` timebase and PTS are
   parsed with the same semantics as `backends/ffmpeg/scene.py`; the filter
   string and PTS rules are not re-derived. Every selected PTS is kept.
2. **Fixed-cadence appearance.** A `select` expression keeps one frame per
   `sample_seconds`, scales it to `160×90` (bicubic, `rgb24`), and `showinfo`
   reports the original PTS. Each kept frame is passed through the existing
   `_frame_metrics` from `analyzers/appearance/source_visual_probe.py`, so
   `meanRgb`, `meanDisplayLumaProxy`, `meanSaturationProxy`,
   `shadowPixelFraction` and `brightPixelFraction` stay comparable with the
   windowed records.
3. **Transition windows.** For cut candidates only, one `select` pass keeps the
   merged ±0.4 s neighbourhoods at about 12 fps, scales them to `96×54`
   (`rgb24`), and writes the raw frames to a temporary file. The scan reads that
   bounded selected buffer back (about 11 MB per runtime minute), classifies one
   cut window at a time, and deletes the file with the temporary directory.

`ffprobe` supplies duration, source resolution, frame rate and timebase. It is
not a decode pass.

## Schema

The scan block (`CENSUS_SCHEMA = "kumiki.video-census.v1"`, overridable by the
caller) carries:

| field | meaning |
| --- | --- |
| `durationSeconds` | ffprobe-reported runtime |
| `timebase`, `fps`, `resolution` | rational source timebase, rational frame rate, source pixels |
| `cutPts[]`, `cutCount` | every scene-score exceedance, in original PTS order |
| `cutsPerMinute` | `cutCount × 60 / durationSeconds` |
| `medianCutGapSeconds`, `medianCutGapFrames` | median consecutive-candidate gap |
| `minCutGapSeconds`, `p10CutGapSeconds` | smallest and 10th-percentile gaps |
| `burstFraction` | share of candidates whose nearest neighbour is < 0.25 s |
| `strobe` | `medianCutGapFrames < 3` or `burstFraction > 0.5` |
| `series[]` | one row per cadence sample: PTS, seconds, RGB mean, luma/saturation/shadow/bright proxies |
| `seriesSummary` | time-weighted mean luma and saturation, `sampledSeconds`, `decodeCoverageFraction`, `samples` |
| `motionProfile` | measured transition, global-motion, local-motion and overlay proxies (see below) |
| `scanSeconds` | wall time of the passes |
| `fullRuntimeDecoded` | always `true` |

`build_census_evidence(...)` wraps that block with the neutral source identity,
acquisition provider/method, `coverage.fullFilmDecoded: true`, rights
attestation, `rightsStatus: review-required`, limits and generation time. It
writes no files and retains no media.

The census record also carries one top-level `identityVerification` block (see
below). No other key changes; the rest of the schema is unchanged.

## Motion and transition profile

`census.motionProfile` is additive and comes from
`acquisition/motion_profile.py`. It is measured, not interpreted:

- `transitions`: every scene candidate is classified into the fixed vocabulary
  `hard-cut`, `short-dissolve` (<0.25 s graded change), `long-dissolve`
  (0.25–0.8 s), `fade-through-black` (luma ≤0.10 then recovers),
  `fade-through-white` (luma ≥0.90 then recovers) or `unknown`. The block
  reports `counts`, `shares`, `transitionRatePerMinute`, `classifiedShare` and
  one `cuts[]` row per candidate with its `sourceSeconds`. A fade test runs
  before the cut/dissolve tests; a hard cut needs one dominant single-frame
  delta spike.
- `globalMotion`: phase-correlation translation on the 1 Hz series, using the
  existing `analyzers/motion/phase.py::measure_image_shift` rather than a
  reimplementation. It reports median absolute dx/dy in pixels per second,
  `panFraction` (pairs above 1.0 px/s), `staticFraction` (pairs at or below
  0.5 px/s) and `zoomProxy` (median edge-density ratio between consecutive
  frames). Both thresholds and the proxy method are stated in the block.
- `localMotion`: mean absolute RGB delta per cell of a 3x3 grid, normalized to
  `cellShares` summing to 1, plus `centreShare`, `motionCoverage` (cells at or
  above 1/20 of the largest cell) and `dominantCell`.
- `overlayActivity`: a text/graphic-overlay proxy. A 3x3 Laplacian luma
  high-pass is taken per frame; the mean absolute frame-to-frame change of that
  high-pass in the top and bottom thirds is reported as `upperThirdActivity`
  and `lowerThirdActivity`, saturated at 0.02 luma units.
- `limits`: denies effect recognition, template detection, camera/rig
  inference, animation-technique identification and transition ground truth.

The cut-window pass can degrade gracefully: if it cannot be decoded the
`transitions` block carries `status: "unavailable"` and a bounded `note`, while
the other three blocks are still measured. `motionProfile` is a proxy
measurement at a reduced decode scale; it is comparable within this corpus, not
to source-pixel motion or to a human edit log.

## Identity is delivery-dependent

The census re-downloads media, but a second download of the same work is not
always byte-identical. `identityVerification` in every census record states
which rule ran:

- **Byte-stable direct HTTP/MP4** (`method: "http-download"`, direct provider):
  strict SHA-256 equality with `source.mediaSha256`. A mismatch is a
  `media-changed` failure and the item is not measured.
- **Remuxed HLS** (the observed method contains `hls`, the record's
  `acquisition.method` is an HLS remux, or the provider is a streaming
  manifest): content identity instead of byte identity —
  `durationSeconds` within 0.5 s, resolution equal, and container/codec family
  equal. The block records
  `{"kind": "duration+resolution+codec", "shaMatched": false,
  "durationDeltaSeconds": 0.16, "resolutionMatched": true,
  "containerMatched": true, "codecMatched": true}`.
- **yt-dlp/YouTube** (`method: "ytdlp-merge"`): the same duration, resolution
  and container rule, but the codec family may differ between renditions. That
  is recorded as `codecMatched: false`, not a failure.

Anything outside those tolerances is still a `media-changed` failure with the
specific reason (for example `duration delta 1.234s exceeds 0.5s`), and the
failure row carries it in `detail`. **Byte identity is not asserted for remuxed
or platform-transcoded sources**: the stored SHA-256 describes the bytes
captured at evidence time, while `identityVerification` is the identity
statement for the census. A SHA that happens to match is still reported only as
`shaMatched: true` inside the content-identity block, never as a byte-identity
claim.

Two flags override the per-delivery default:

- `--strict-identity` forces SHA-256 equality for every method, including HLS
  and YouTube (the old behaviour).
- `--allow-media-change` measures a record whose identity could not be
  established and records `{"kind": "forced", "shaMatched": false,
  "reason": ...}`. Forced rows remain visible in the census record and index
  and are counted separately.

The index carries `identityCounts: {"strict-sha": n, "tolerant": n,
"forced": n}`, each measured record repeats its `identityVerification` block,
and the run summary prints the same three counts.

## Commands

`--ids-file PATH` restricts each site to an explicit id list (JSON list,
`{"ids": [...]}`, or newline ids); `--limit` then applies to that selection.

```bash
# Two records into a temporary tree (the only live smoke).
PYTHONPATH=src python scripts/census_video_cuts.py \
  --root "$TMP/analysis" --site promonews --limit 2 \
  --acknowledge-rights --yt-dlp /path/to/yt-dlp

# All remaining records for one site in the evidence tree.
PYTHONPATH=src python scripts/census_video_cuts.py \
  --site motiondesignawards --acknowledge-rights --yt-dlp /path/to/yt-dlp

# Refresh existing census records.
PYTHONPATH=src python scripts/census_video_cuts.py \
  --site shots --refresh --acknowledge-rights

# Force the byte-identity gate everywhere (pre-tolerance behaviour).
PYTHONPATH=src python scripts/census_video_cuts.py \
  --site aicp --strict-identity --acknowledge-rights

# Measure despite an unestablished identity; rows are marked forced.
PYTHONPATH=src python scripts/census_video_cuts.py \
  --site aicp --allow-media-change --acknowledge-rights
```

## Expired signed URLs and catalog fallback

Some lanes (AICP, shots) store signed CDN URLs. Their signature is valid for
about an hour, so the URL captured when the evidence record was written may be
expired by census time. The driver therefore resolves each record's media URL in
this order:

1. The URL stored in the record (`urlSource: "record"`).
2. The URL for the same record id in the site catalog
   (`urlSource: "catalog"`), used when the stored URL is absent or when the
   download/probe fails with a 4xx that signed media uses for expiry
   (400/401/403/404/410).

Catalogs are loaded once per site. `--catalog PATH` is repeatable; when it is
omitted the driver auto-discovers `<root>/<site>/catalog.json`. Rows are indexed
by every adapter id key (`id`, `nid`, `projectId`, `catalogId`, and the aliases
the catalogs use), and the catalog's row container is discovered from
`entries`, `videos`, `projects`, `clips`, `items`, or `records`. A catalog that
is itself expired must be refetched first (see the AICP command below).

AICP's signed entry is a Vimeo `player.vimeo.com/external/<id>.m3u8` URL that
redirects to a `vod-adaptive-*.vimeocdn.com` master with **relative** variant
URIs. The driver follows that redirect chain under the same host allowlist and
query opt-in before handing the final master URL to the playback planner;
otherwise the relative variant resolves against the pre-redirect host and
404s.

When the fallback succeeds the progress line carries `url-from-catalog`, the
census record stores `acquisition.urlSource: "catalog"` and
`record.urlSource: "catalog"`, and the measured index row carries the same
field. When the catalog URL also returns the expiry 4xx the item is a
`stale-signed-url` failure rather than an opaque `ValueError`. The stored media
identity is still verified after a fallback: a byte-stable delivery must match
the stored SHA-256, while a remuxed HLS delivery is re-checked on duration,
resolution and container/codec family (see above). A fresh URL whose media
fails those rules remains a `media-changed` failure, never a measurement.

```bash
# Refetch the AICP catalog first: its rows hold the same expiring signatures.
PYTHONPATH=src python scripts/research_aicp.py catalog \
  --out research/analysis/aicp/catalog.json

# Re-run AICP with the fresh catalog; then the census fallback can re-resolve.
PYTHONPATH=src python -u scripts/census_video_cuts.py \
  --root research/analysis --site aicp \
  --catalog research/analysis/aicp/catalog.json \
  --acknowledge-rights --jobs 2 --delay-seconds 1.0 \
  > /tmp/census_aicp.log 2>&1
```

The driver reads `<root>/<site>/videos/*.json`, recovers the canonical upstream
URL, provider and stored `source.mediaSha256` across adapter shapes, downloads
into a `TemporaryDirectory`, verifies the stored identity with the rule for its
delivery method (strict SHA for byte-stable files, duration/resolution/
container+codec for remuxed HLS and YouTube), scans, writes
`<root>/<site>/census/<id>-<slug>.json` atomically, and deletes the media in a
`finally` block. If the identity gate fails the item is **not measured**: it
lands in the index as a `media-changed` failure with a specific `detail`.
Missing URLs are `missing-url` skips; existing output is skipped under
`--resume` and re-measured under `--refresh`.

Per-site host allowlists come from the recorded URLs. `allow_query=True` is
enabled only for the lanes whose recorded URLs carry a signature (shots,
AICP); YouTube stays yt-dlp-mediated, cookie-free and login-free.

## Census in reports

Every adapter report (`shots`, `motiondesignawards`, `aicp`, `promonews`,
`directorslibrary`, `stash`) reads `<out-dir>/census/*.json` and
`<out-dir>/census-index.json` read-only when they exist. The report gains:

- two per-video columns: `full_cuts_per_min` (film-level, `—` when the record
  has no census) and `full_vs_window` (the window sample relative to the film
  rate, rendered as `+12%`/`-8%`; `—` when either side is missing);
- `## Full-film census`: coverage (`n` census records of `m` video-measured
  records), the distribution of non-strobe `full_cuts_per_min`, the strobe
  records listed separately by id with their own range, and the
  `decodeCoverageFraction` statement;
- `## Census reconciliation`: per-record relative error
  `(window_rate - full_rate) / full_rate`, its median/p90/max absolute value,
  the count off by more than 25%, and the records whose ordering changes by more
  than five positions when ranked by each rate.

The prose states the two bases explicitly: census values are film-level, window
values are samples, census cut candidates are still ffmpeg scene-score
exceedances rather than verified edits, and a `strobe` record's rate is **not**
comparable to a cut rate. Strobe and non-strobe rates are never pooled in one
range. When no census record exists (for example a stills-only tree), the report
keeps its window-only sections and prints `census: not present` rather than
silently implying film-level evidence. Reports stay deterministic: two runs over
the same tree are byte-identical.

The helpers live in `acquisition/reporting.py`:
`census_columns`, `census_reconciliation`, `census_aggregate`, plus the small
lookup/formatting helpers the adapters share.

### How identity is reported

Every census section repeats the identity basis of the records behind it, so a
film-level number is never read without knowing how its media was reacquired.

- One paragraph states the mode breakdown in the census vocabulary:
  `strict-sha: N, tolerant: N (duration+resolution+codec), forced: N,
  unrecorded: N`, followed by the delivery split the table uses
  (`byte`, `remux`, `youtube`, `forced`).
- One sentence states the policy: byte identity is asserted only for
  direct-file sources; remuxed and platform-transcoded sources are matched on
  duration ±0.5 s, resolution and codec family (`identityVerification`).
- The per-video table gains an `identity` column (`byte`, `remux`, `youtube`,
  `forced`, `—`). `—` means no identity statement exists for that row: it has
  no census record, or its census record carries no `identityVerification`
  block (the latter are the `unrecorded` count above). A mode is never
  inferred from the URL or the method alone.
- A `forced` record (identity gate waived) is **excluded** from the census
  aggregates and from the reconciliation, named in the section with its reason,
  and listed under `censusIdentity.forced` in `aggregate.json`. The same block
  carries `counts` (index vocabulary), `modes` (delivery vocabulary),
  `unrecorded` and `toleranceSeconds: 0.5`.

The census index carries the same statement: `identityCounts: {"strict-sha": n,
"tolerant": n, "forced": n}` plus each measured row's `identityVerification`.
`scripts/rebuild_evidence_indexes.py` re-projects the block and recomputes
`identityCounts` from the records on disk, so a rebuilt index cannot disagree
with them.

## Published dataset

The measured census and window records for all six sites are published in
`research/analysis/<site>/dataset/` (about 75 MiB total). Each directory holds
deterministic `videos.tar.gz`, `stills.tar.gz` and `census.tar.gz` trees plus
gzip-compressed `catalog.json`, `index.json`, `stills-index.json` and
`census-index.json`; its `DATASET.md` records the counts, catalog URL,
acquisition window and non-claims, and `research/analysis/README.md` summarises
all sites. Rebuild the package with
`PYTHONPATH=src python scripts/package_research_dataset.py --root research/analysis`
and unpack one site with `cd research/analysis/<site> && tar -xzf dataset/census.tar.gz`
(use `gzip -dk dataset/census-index.json.gz` for the index). The raw 646 MiB
record trees stay untracked; only the compressed copy and the plain
`report.md` / `aggregate.json` deliverables are committed.

## Cost and non-claims

- **Cost:** one re-download plus whole-file scene/appearance decodes per clip
  and one bounded cut-window decode. A 10-minute clip at 160×90 is roughly 600
  metric rows; the transition buffer is 96×54 at about 12 fps and is deleted.
  Media is deleted, so storage cost is only the JSON.
- **No new acquisition:** the host allowlist, bounded download, probe, store,
  runner and scene filter are the existing engine primitives.
- **Candidates are not edits.** Fast motion, flashes, transitions and
  compression can exceed the scene threshold. `strobe` is a measured density
  flag, never a style judgement.
- **Appearance is a proxy.** Display-RGB luma and saturation at 160×90 are not
  scene-linear light, calibrated colour, or a subject/authorship/quality claim.
- **No expert review.** The record is an automated numeric census; a human
  review lane, if any, is separate and must say so.
- **No ranking gate yet.** A census record states its own `strobe` and burst
  numbers; consumers decide whether a row is comparable.
