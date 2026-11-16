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

## The two passes

`scan_full_runtime(path, ...)` runs exactly two ffmpeg passes over the file:

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
| `scanSeconds` | wall time of the two passes |
| `fullRuntimeDecoded` | always `true` |

`build_census_evidence(...)` wraps that block with the neutral source identity,
acquisition provider/method, `coverage.fullFilmDecoded: true`, rights
attestation, `rightsStatus: review-required`, limits and generation time. It
writes no files and retains no media.

## Commands

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
`stale-signed-url` failure rather than an opaque `ValueError`. The stored
media SHA-256 is still verified after a fallback: if the fresh URL yields a
different file, the item remains a `media-changed` failure (the platform
re-encoded the asset), never a measurement.

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
into a `TemporaryDirectory`, verifies the SHA-256, scans, writes
`<root>/<site>/census/<id>-<slug>.json` atomically, and deletes the media in a
`finally` block. If the re-downloaded hash differs from the stored hash the
item is **not measured**: it lands in the index as a `media-changed` failure.
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

## Cost and non-claims

- **Cost:** one re-download plus one full decode per clip (the two ffmpeg
  passes share the decoded file; the second pass is the extra decode). A
  10-minute clip at 160×90 is roughly 600 metric rows. Media is deleted, so
  storage cost is only the JSON.
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
