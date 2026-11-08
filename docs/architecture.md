# Architecture and source timebase contract

> **Status:** Milestone 0 foundation, not a completed reference-to-render pipeline. Keep this document aligned with tested source contracts.

## Dependency direction

- `core`: general numeric/timebase, identity, error and provenance primitives; no FFmpeg/OpenCV/Torch imports.
- `contracts`: source/analysis/technique artifact types and version policy. No models or rendering.
- `analyzers`: evidence-producing algorithms consuming typed artifacts and capability ports.
- `backends`: concrete implementations of subprocess, CV and ML ports. Optional ML backends are loaded only when requested.
- `pipeline`: orchestrates existing analyzer stages and transactionally publishes checksum-verified output bundles; future: DAG scheduling, caching and retry. Never owns an algorithm.
- `interpretation` (future): creates proposals/hypotheses, never modifies observations.
- `catalog`: validated canonical technique research metadata, purpose search and exported index; not animation implementations.
- `integrations/kumiki` (future): maps a supported subset of treatment fields into Kumiki-owned executable contracts, without a separate render clock.
- `cli`: thin command dispatch; no algorithm implemented in CLI handlers.

Do not create empty packages for future features. Add the minimum module needed by each verified vertical slice.

## Source timestamps and VFR

The `inspect` command records the selected video's **stream timebase** as a rational pair and its nominal and average frame rates **as reported by FFprobe**. These rates do **not** establish whether the video is constant- or variable-frame-rate. In the *metadata-only manifest*, `timestamps.originalFramePtsExtracted` is explicitly `false`, `frameRateMode` is unknown, and no output frame mapping is claimed. The separate `frames` command extracts actual source PTS in a bounded window and records discontinuities without attempting to infer source frames from FPS.

Future decoded-frame artifacts must preserve:

| Field | Meaning |
| --- | --- |
| `sourceStreamIndex` | Exact selected input stream |
| `sourcePts` | Integer source presentation timestamp; may be negative or nonzero at start |
| `sourceTimebase` | Positive rational seconds per PTS tick |
| `sourceTimestampSeconds` | Exact rational `sourcePts × sourceTimebase`, not floating-point authoritative data |
| `sampleOrdinal` | Observation order; *not* a presentation timestamp |
| `normalizedFrame` | Optional mapping to a declared rational output FPS with named origin/rounding policy |
| `mappingError` | Timing difference caused by quantization to the output grid |

Never assume `sampleOrdinal / fps` represents the presentation time of VFR footage. When the source has missing, repeated or nonmonotonic presentation timestamps, report the anomaly and either reject the affected comparison or make a documented normalization choice. Do not silently fabricate timestamps.

`core.timebase.map_pts_to_frame` provides deterministic half-away-from-zero rounding for a **caller-selected** output FPS and PTS origin; it does not decode or reconstruct frame PTS itself. Preserve the original timestamps when performing shot alignment and metric comparisons.

## Artifact version ownership

- Reference Lab owns `kumiki.source-manifest.v1` and future research observation schemas.
- Kumiki UI owns its executable camera/motion/film contracts. A proposed YAML treatment is not executable until a matching importer and capability validator actually exist.
- Schema changes require a versioned fixture and a compatibility test; never silently reinterpret earlier run artifacts.
- Reports must distinguish observed, inferred and authored values, with method metadata and uncertainty.

## Data and rights

- Only explicit user-selected local files are inspected. Source media isn't committed, duplicated into the repository, or downloaded by the CLI.
- `rightsStatus` is a user declaration; the program cannot automatically prove ownership or redistribution permission.
- Source hashes are computed in bounded chunks; absolute input paths are not serialized in the manifest.
- The CLI refuses to overwrite a different existing manifest in the output directory.
- Advanced analysis should use content-addressed caches and record backend/checkpoint versions. Cache artifacts, private frames and model checkpoints remain outside Git.

## Supported foundation commands

```bash
PYTHONPATH=src python -m kumiki_reference_lab inspect ./reference.mp4 --out ./runs/example
PYTHONPATH=src python -m kumiki_reference_lab frames ./reference.mp4 --max-seconds 60 --out ./runs/example
PYTHONPATH=src python -m kumiki_reference_lab cuts ./reference.mp4 --threshold 0.25 --max-seconds 60 --out ./runs/example
```

Expected outputs: `source-manifest.json` (metadata), `frame-timeline.json` (real bounded source PTS, exact rational timestamps and anomalies), and `shot-candidates.json` (heuristic hard-cut candidates). The last two stages preserve source timebase and never invent confidence scores. The FFmpeg cut filter's own timebase is checked against the probed stream, and mismatches fail explicitly rather than producing false timestamps.

Timecoded visual evidence is also supported:

```bash
PYTHONPATH=src python -m kumiki_reference_lab contact-sheet ./reference.mp4 --max-seconds 30 --max-thumbnails 12 --width 480 --out ./runs/example
```

This creates a self-contained, local HTML review index and versioned JSON manifest with JPEG thumbnails. Sampling prioritizes opening/closing, available hard-cut pairs, then wide gaps between existing samples. Frame choice uses ordinals **only to select decoded pictures**; their authoritative times are original rational source PTS. Both the cut detector and thumbnail decoder must report the same timebase and the selected image PTS must match FFprobe's timeline exactly, or the stage fails. It uses a temporary staging directory and publishes the completed bundle together. On rerun, checksum-verified completed bundles are reused. No full-resolution copies of the source video are written.

## Image motion and easing candidates

Install the optional NumPy dependency with `python -m pip install -e '.[motion]'`. Then:

```bash
kumiki-ref motion ./reference.mp4 --max-seconds 10 --max-samples 48 --out ./runs/motion
```

The `motion` command produces a versioned `image-motion.json`. Sampling targets uniformly spaced **original source PTS**; FFmpeg selects corresponding decoded-frame ordinals and must report identical timestamps/timebase. A bounded grayscale FFT phase-correlation estimator yields relative *global image-plane* pixel shifts and an **uncalibrated** peak-to-sidelobe ratio diagnostic. Uniform and ambiguous pairs have null displacements. Cross-cut comparisons are explicitly skipped. Valid continuous samples build cumulative image-motion paths whose projected progress is fitted against linear, quadratic and smoothstep-family candidates with numeric residuals. Short, reversing, low-motion or poorly fitted paths receive explicit statuses instead of arbitrary easing labels.

Measured global image shift is **not** interchangeable with optical flow, subject tracking or reconstructed camera motion. Planar translation can come from any dominant moving content; panning, dolly, parallax, changing geometry, zoom and multiple independently moving objects are not disentangled. The separate [`sparse-flow` experiment](sparse-flow.md) now detects distributed 2D point translations and up to two motion groups; these still do not establish physical camera motion or semantic identities.

## Seeded image-region tracking

```bash
kumiki-ref track-roi ./reference.mp4 --box 0.19 0.22 0.15 0.20 --max-seconds 10 --out ./runs/roi
```

The four `--box` values are normalized X, Y, width and height **on the first sampled video frame**. The tracker extracts a fixed small grayscale template and searches near its last verified position, using zero-mean normalized cross-correlation (brightness-offset tolerant). It preserves original PTS for each sampled frame. Missing PTS, insufficient texture, low similarity, repetitive ambiguous matches, cut boundaries and frame exits receive explicit statuses. Lost tracks remain stopped until a new user/model seed is provided; continuing to report a guessed identity after occlusion would be misleading.

Compute is bounded by source duration (30 s), sample count (120), resize dimensions, search radius and a per-frame correlation budget. No neural model is required. An ROI track is an appearance path, **not guaranteed to follow a named physical object**; its box can include background, deform or leave view. It can eventually be compared with global image shift as *evidence for differential motion*, but camera-versus-object attribution still requires independent background tracks, geometric checks and explicit uncertainty.

## Transactional analysis bundles

```bash
kumiki-ref analyze ./reference.mp4 --max-seconds 10 --out ./runs
kumiki-ref analyze ./reference.mp4 --max-seconds 10 --motion --box 0.19 0.22 0.15 0.20 --out ./runs
```

`analyze` calls the existing `inspect`, `frames`, `cuts`, and `contact-sheet` analyzers; global motion and seeded ROI are optional and require NumPy. A source/settings hash creates a stable run directory name. All stages run inside a private temporary directory; only a completed set is renamed into place. The `kumiki.analysis-run.v1` manifest records stage artifact paths, SHA-256 of every file, original stream timebase and exact settings. Reruns verify all files before reusing a completed run, reject corruption/unknown artifacts and leave previously published data untouched. A failure in any required stage discards the temporary directory. This is stage-level **atomic publication**, not yet incremental restart, distributed execution or streaming analysis.

No AI inference or technique classification is performed by this command. `catalogProposals` is explicitly empty, `interpretationStatus` is `not-performed`, and the existing catalog candidates remain separate authored research. Future models may propose an interpretation **referencing** this manifest and verified PTS; they must never rewrite the observed measurements or silently promote catalog verification state.

Detection is a **bounded first-stage heuristic**, not comprehensive scene segmentation: it does not classify fades or dissolve transitions, reconstruct frame geometry, or prove that fast image changes are cuts. More robust detectors can later be swapped behind the analyzer interface.

## Planned next slice

Expand the `analyze` run into a restartable stage DAG with shared decoded frames and explicit cancellation; `sparse-flow` is now an opt-in bundle stage with guarded 2D affine hypotheses, while robust homography, longer-lived tracks and physical 3D inference remain separate research problems. Then generate reviewed technique **evidence proposals** for the existing canonical catalog. The catalog validates/indexes authored recipes but does not infer a technique from arbitrary footage. See [catalog guide](catalog.md). Before full-volume processing, add streaming analysis so long inputs never need to be decoded or captured entirely in memory.

## Display-referred appearance measurements

The standalone `appearance` command provides source-timecoded RGB24 frame
statistics and cut-aware color/brightness deltas, with a separate strict
[`kumiki.appearance.v1` schema](../schemas/v1/appearance.schema.json). See
the [method and interpretation guide](appearance.md). A bright-pixel center,
histogram or luma proxy is **not** recovered scene lighting, physical camera
exposure or a material classification. `analyze --appearance` now adds this
stage transactionally with immutable checksums, bounded parameters and the
original source timestamps.
