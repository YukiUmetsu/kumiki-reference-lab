# Architecture and source timebase contract

> **Status:** Milestone 0 foundation, not a completed reference-to-render pipeline. Keep this document aligned with tested source contracts.

## Dependency direction

- `core`: general numeric/timebase, identity, error and provenance primitives; no FFmpeg/OpenCV/Torch imports.
- `contracts`: source/analysis/technique artifact types and version policy. No models or rendering.
- `analyzers`: evidence-producing algorithms consuming typed artifacts and capability ports.
- `backends`: concrete implementations of subprocess, CV and ML ports. Optional ML backends are loaded only when requested.
- `pipeline` (future): orchestrates analyzer stages, caching, retry and outputs; never owns an algorithm.
- `interpretation` (future): creates proposals/hypotheses, never modifies observations.
- `catalog` (future): canonical technique research metadata, not animation implementations.
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

Detection is a **bounded first-stage heuristic**, not comprehensive scene segmentation: it does not classify fades or dissolve transitions, reconstruct frame geometry, or prove that fast image changes are cuts. More robust detectors can later be swapped behind the analyzer interface.

## Planned next slice

Complete an interoperable `analyze` pipeline: join reviewed shot candidates with source-frame PTS, add deterministic optical-flow/easing estimation with synthetic fixtures, and produce draft technique-catalog evidence records. Before full-volume processing, add streaming analysis and explicit cancellation so long inputs never need to be decoded or captured entirely in memory.
