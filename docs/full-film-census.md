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
