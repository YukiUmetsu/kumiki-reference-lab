# Motion Design Awards video research

Ephemeral, source-hashed measurement of publicly listed Motion Design Awards
(MDA) video entries. The collector is
`scripts/research_motiondesignawards.py`; it is the only MDA component that
touches the network or downloads media.

## Generic acquisition package and the adapter contract

All mechanics live in `src/kumiki_reference_lab/acquisition/`; the MDA script is
a thin, site-specific adapter over it.

| module | responsibility |
| --- | --- |
| `media.py` | URL allowlisting, bounded fetch/download, HLS planning + stream-copy remux |
| `probe.py` | bounded ffprobe adapters (remote, ranged, local source identity) |
| `windows.py` | window planning, per-window measurement, evidence assembly |
| `stills.py` | still probing/decoding/metrics, still evidence assembly |
| `store.py` | atomic JSON writes, safe slugs, resume matching, index assembly |
| `runner.py` | generic sequential/pooled batch loop, per-item failure isolation |

The package enforces the safety posture once, for every site: HTTPS only against
a caller-supplied host allowlist (no credentials, custom ports, query strings,
fragments, IP literals, or implicit subdomains), byte- and duration-capped
downloads, no cookies/logins/DRM bypass, ephemeral bytes only, and numeric
payloads with no subject identity. Callers supply their own rights basis,
schemas, limits, and attestation text.

The MDA adapter supplies only:

- the GraphQL endpoint, project URL template, catalog query, and
  `parse_project_node` catalog enumerator (neutral candidate rows with a stable
  `projectId`);
- the media and image host allowlists (`videodelivery.net`,
  `storage-01-mda.keyfram.es`, `*.cloudflarestream.com`) and the site provider
  vocabulary mapped onto the package's generic `HLS`/`DIRECT` delivery modes;
- award types, selection/ordering rules (`--order best|latest|awards-first`),
  and the `projectId` identity used by `--resume`;
- the MDA schema strings, evidence-status strings, limits text, rights basis,
  index row shapes, and progress-line wording.

Adapting another site means copying that skeleton: a catalog enumerator, host
allowlists, schema/rights constants, an identity field, selection rules, and a
CLI. No allowlisting, fetching, probing, downloading, measuring, evidence,
atomic-write, resume, index, or batch-loop code should be reimplemented in the
adapter. The offline test suite includes a parity test that rebuilds a committed
video and still record from the catalog row plus embedded measurements and
asserts byte equality, so record schemas cannot drift silently.

## Source

- Catalog: `POST https://www.motiondesignawards.com/api/graphql`, public
  `allProjects` field with `first: 100` pagination ordered by
  `VOTING_STARTED_AT DESC`. No authentication, no cookies.
- Project pages: `https://www.motiondesignawards.com/project/<id>/<slug>`.
- All catalog metadata (title, studio, category, weighted scores, votes, awards,
  tags, dates) is self-reported by the awards site and is not independently
  verified.
- Each catalog row also carries `posterUrl`: the `original` URL of the project's
  hosted 640 px poster
  (`thumbnail(renditions: [{width: 640}]) { original }`). The inline base64
  `src` LQIP is deliberately ignored. Older catalogs without `posterUrl` are
  tolerated; the field is treated as `null` and those rows are simply not part
  of the `stills` lane.

## Provider coverage

| provider | observed count | handling |
| --- | --- | --- |
| Vimeo | 1418 | **excluded**: `unsupported-vimeo` skip row, never attempted |
| Cloudflare Stream | 454 | HLS master playlist, `ffmpeg` stream-copy remux |
| `videodelivery.net` | 2 | same Cloudflare Stream HLS path |
| direct MP4 | 47 | `https://storage-01-mda.keyfram.es/...mp4` over HTTPS |

Vimeo is excluded by design: its progressive files require login/bot
verification, and this project never reads browser cookies, logs in, or bypasses
access control. Cloudflare Stream and direct MP4 URLs are the only hosts
allowlisted for download (exact `videodelivery.net`, `*.cloudflarestream.com`,
and `storage-01-mda.keyfram.es`). Every URL must be `https` with no credentials,
custom port, or fragment; redirect targets are re-validated for HTTP downloads.

## Download/delete lifecycle

Per video:

1. `tempfile.mkdtemp(prefix="kumiki-mda-")` creates a private scratch directory.
2. The allowlisted public video is downloaded into `<scratch>/media`
   (Cloudflare HLS uses
   `ffmpeg -hide_banner -v error -y -i <master.m3u8> -map 0:v:0 -map 0:a:0? -c copy <out.mp4>`).
3. Size (`--max-file-bytes`) and duration (`--max-duration-seconds`) budgets are
   enforced; `inspect_source(...)` supplies the canonical SHA-256, duration,
   resolution, frame rate, and source timebase.
4. Bounded source-PTS windows are measured.
5. The per-video JSON record is written atomically.
6. `finally:` removes the entire scratch directory. No media, frames,
   thumbnails, or audio are retained.

`acquisition.mediaRetained` is always `false`. A failed download or measurement
leaves no record and no media behind.

Direct-MP4 sources are first characterised with a remote `ffprobe`. Large HTTP
files (for example the 373 MB / 60 s / 49.8 Mbps `plusone-manifesto` entry) are
read with range requests, so the probe uses a 30 s socket I/O timeout and, if it
still fails after retries, falls back to a bounded `Range: bytes=0-<2 MiB>` read
that is probed locally and deleted immediately. A source that cannot be
characterised at all is recorded as a failure carrying both probe reasons. If
the estimated byte size still exceeds `--max-file-bytes`, the source is streamed
and aborted at the cap with `source exceeds the bounded local size cap` rather
than surfacing a probe error.

## Published-still lane (`stills`)

The `stills` subcommand gives every catalog project with a hosted poster — most
importantly the 1418 Vimeo entries that cannot be downloaded — one real,
source-hosted image measured numerically, without watching or downloading video.
Each poster is fetched over HTTPS from an allowlisted image host
(`storage-01-mda.keyfram.es`, plus the video hosts), measured inside a
`TemporaryDirectory`, and deleted in a `finally` block; only its SHA-256 and
numbers are retained. The image allowlist is separate from
`allowlisted_video_url` and does not loosen any video rule.

Measurement uses ffmpeg only: the still is decoded to
`scale=160:90:force_original_aspect_ratio=decrease,format=rgb24` raw pixels.
The six base metrics (`meanRgb`, `meanDisplayLumaProxy`, `displayLumaStdDev`,
`meanSaturationProxy`, `shadowPixelFraction`, `brightPixelFraction`) reuse the
repository's canonical `_frame_metrics` from
`kumiki_reference_lab/analyzers/appearance/source_visual_probe.py`, so stills
and decoded video frames are measured with identical formulas. Three extras are
still-specific:

- `lumaHistogram`: five equal luminance buckets, stored as pixel fractions.
- `dominantHueFamily`: coarse HSV hue of the mean RGB — one of `neutral`, `red`,
  `orange`, `yellow`, `green`, `cyan`, `blue`, `purple`, `magenta`.
- `edgeDensityProxy`: mean absolute horizontal+vertical neighbour luma
  difference (0..1), a detail/texture indicator, not a sharpness score.

The source image's own pixel dimensions come from ffprobe, and its SHA-256 is
recorded (`imageSha256`), but the bytes are never kept
(`acquisition.imageRetained = false`).

### Poster still vs decoded video frame

A poster still is **not** a video frame. It is a single editorial image the
awards site prepared, so the record states
`coverage.isSourceVideoFrame = false` and
`evidenceStatus = "single-published-still-metrics-not-video-measurement"`. It
carries no motion, cut, pacing, or timing evidence, and its colour/luminance
reflects the site's image preparation rather than the entrant's grade. It says
nothing about runtime behaviour. It is still useful as a cheap, uniform visual
sample of every project, including ones whose video can never be acquired
legitimately.

```
python scripts/research_motiondesignawards.py stills \
  --catalog research/analysis/motiondesignawards/catalog.json \
  --out-dir research/analysis/motiondesignawards \
  [--limit N] [--delay-seconds 1.0] [--resume|--refresh] [--jobs 1]
```

Each `stills/<slug>.json` uses schema
`kumiki.motiondesignawards-still-evidence.v1`;
`<out-dir>/stills-index.json` uses
`kumiki.motiondesignawards-stills-index.v1` and is rewritten atomically after
every success or failure. `--resume` (default) skips records whose `projectId`
already matches, `--refresh` re-measures. A per-project failure is recorded and
the run continues; one line is printed per project:
`[12/1418] ok <slug> 1280x720 luma=0.42 hue=blue`. The lane never fetches
video, never attempts Vimeo playback, and never uses cookies or logins.

## What is measured

Up to `--windows` (default 4) non-overlapping `--window-seconds` (default 10)
windows, spread evenly across the runtime. The first window starts at 0 and the
trailing 10% is skipped to avoid end cards and black frames. Each window calls
the existing `analyze_source_visual_window`, and its returned payload is embedded
verbatim under `windows[].probe`:

- sampled source PTS and sampled display RGB statistics (mean luma proxy,
  saturation proxy),
- cut candidates between the first and last sample,
- within-shot inter-frame RGB delta per second (optionally FFT image-shift
  hypotheses with `--image-translation`).

The record `summary` is derived only from those embedded probes: total cut
candidates, cut-candidate rate per minute, mean luma, mean saturation, mean
within-shot RGB delta per second, sampled frame count, and the number of windows
with cut candidates. Missing probe fields become `null` rather than invented
values.

## What is explicitly NOT claimed

- No camera, lens, lighting, editing-intent, mood, visual-style, or quality
  inference. Display-RGB and cut candidates are numerical proxies only.
- No full-film review. `coverage.fullRuntimeMeasured` is `false`; only a small
  fraction of each runtime is sampled, and `coverage.fractionOfRuntime` states
  how much was requested.
- No identity, authorship, or creative-origin verification beyond the catalog's
  self-reported studio/title metadata.
- Public availability is not a license. `rightsStatus` stays
  `review-required`, and the operator must pass `--acknowledge-rights` attesting
  research use. The attestation is recorded as
  `acquisition.attestation.rightsBasis = "user-declared-research-use"`.
- Sampled numbers are not expert-reviewed (`evidenceStatus =
  "sampled-original-source-pts-metrics-not-expert-reviewed"`).

## Resume and atomicity

- Writes go to a sibling temp file and are committed with `os.replace`; a crash
  never leaves a partial JSON file.
- `<out-dir>/index.json` is rewritten atomically after every success (and after
  every failure) so counts and rows always match the records on disk.
- `--resume` (default) skips a video when
  `<out-dir>/videos/<slug>.json` exists with the same `projectId`. `--refresh`
  re-measures instead.
- `--jobs N` (1–3) gives each worker its own scratch directory; record/index
  writes are serialized.
- The process exits non-zero only when every attempted video failed. Partial
  failures are reported and the run continues.

## Commands

```bash
# 1. Fetch and classify the full public catalog (1919 projects).
#    Re-run this after pulling a collector that adds posterUrl; schema version
#    is unchanged, but the hosted poster URLs only appear in a fresh fetch.
python scripts/research_motiondesignawards.py catalog \
  --out research/analysis/motiondesignawards/catalog.json

# 2. Measure one hosted poster still for every project that has one.
python scripts/research_motiondesignawards.py stills \
  --catalog research/analysis/motiondesignawards/catalog.json \
  --out-dir research/analysis/motiondesignawards \
  --delay-seconds 1.0

# Smoke-test the stills lane on a few projects first.
python scripts/research_motiondesignawards.py stills \
  --catalog research/analysis/motiondesignawards/catalog.json \
  --out-dir research/analysis/motiondesignawards --limit 5

# Re-measure stills instead of resuming; a faster politeness pause.
python scripts/research_motiondesignawards.py stills \
  --catalog research/analysis/motiondesignawards/catalog.json \
  --out-dir research/analysis/motiondesignawards --limit 20 --refresh \
  --delay-seconds 0.5

# 3. Measure the 20 best-scoring downloadable entries, acknowledging research use.
python scripts/research_motiondesignawards.py collect \
  --catalog research/analysis/motiondesignawards/catalog.json \
  --out-dir research/analysis/motiondesignawards \
  --limit 20 --order best --windows 4 --window-seconds 10 \
  --max-duration-seconds 600 --max-file-bytes 419430400 \
  --acknowledge-rights

# Alternative orderings / concurrency.
python scripts/research_motiondesignawards.py collect \
  --catalog research/analysis/motiondesignawards/catalog.json \
  --out-dir research/analysis/motiondesignawards \
  --order awards-first --limit 40 --jobs 2 --no-image-translation \
  --acknowledge-rights

# Re-measure existing slugs instead of resuming.
python scripts/research_motiondesignawards.py collect \
  --catalog research/analysis/motiondesignawards/catalog.json \
  --out-dir research/analysis/motiondesignawards \
  --limit 5 --refresh --acknowledge-rights

# Offline tests (no network, no ffmpeg).
PYTHONPATH=src python -m unittest tests.test_motiondesignawards_research -v
```

Output layout:

```
<out-dir>/
  index.json                 # video index schema v1, catalog SHA + counts + rows
  videos/<slug>.json         # per-video evidence schema v1
  stills-index.json          # stills index schema v1, catalog SHA + counts + rows
  stills/<slug>.json         # per-still evidence schema v1
```

Each `videos/*.json` records the source SHA-256, resolution, frame rate,
timebase, provider URL, acquisition method, coverage, verbatim probes, derived
summary, boundaries, and rights attestation. No media is stored in the
repository. Each `stills/*.json` records the poster URL, image SHA-256, size,
source pixel dimensions, still metrics, and the explicit
poster-vs-video-frame limits; the image itself is deleted before the record is
written.
