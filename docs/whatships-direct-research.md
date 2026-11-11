# Direct original-frame measurement saved into Git

The goal is to retain actual source-linked visual observations under `research/analysis/whatships/`, not only external metadata or local temporary run artifacts.

`whatships-measure` processes an **already authorized, locally bound** What Ships video using FFmpeg and FFprobe. It requires **no Ollama model, character study, or prior backfill**. It writes actual original-PTS RGB, brightness, saturation, candidate cut, and interframe image-change measurements into the canonical per-video research JSON in the Git working tree.

## Run

First [register an authorized local video](whatships-authorized-local-media.md). Then:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-measure \
  "$HOME/whatships-private/bindings-002/media-bindings.json" \
  whatships:paper-mono-code \
  --window-seconds 10 --window-count 4 --max-samples 12

PYTHONPATH=src python -m kumiki_reference_lab whatships-all validate-analysis \
  --root research/analysis/whatships

git diff -- research/analysis/whatships
git add research/analysis/whatships
git commit -m "data: add verified source-PTS measurements for paper-mono-code"
```

One invocation checks the exact What Ships catalog ID, user-attested rights binding, source SHA256, FFprobe video stream/timebase, and duration. It samples up to six nonoverlapping windows distributed across the first hour of the original video. Every decoded frame retains its **original source presentation timestamp**. It merges one strictly validated numeric evidence layer into the matching source record, preserving prior browser observations. Conflicting numeric evidence requires explicit `--replace-existing`.

A decoding/provenance error leaves the Git research directory unchanged. No video, audio, images, local paths, private permission notes, model prompts or identity attributes are added to Git. The command changes the local Git worktree only; **it does not commit or push**.

## What coverage means

Output reports `sampledOriginalSourceFrames`, `framesInWindowPtsInventories` and `requestedWindowTimeFractionOfReportedFilmDuration`. The sampled frame fraction is **only** of PTS inventories for the requested intervals; the requested time fraction does **not** mean all video frames were examined. FFprobe timings, sampling, or decoder limitations may still leave meaningful gaps. Full human video review remains false.

Average display pixel brightness is not a light source measurement. Pixel differences can result from animation, cuts, camera motion, screen content or compression. Cut candidates are not verified editorial decisions, and this tool does not infer actual camera movement, real light placement, style popularity or causal virality.

## Test

```bash
PYTHONPATH=src python -m unittest tests.test_whatships_direct_measure -v
```

The added tests use synthetic source fingerprints, mocked frame decoding and actual repository JSON validation; separate tests exercise the underlying source-PTS FFmpeg integration. The command has not itself measured third-party footage from What Ships without a lawfully available local source.

## Source-PTS frame inventory denominators

Newly measured records store `scan.sourcePtsFramesSeenInInventory` for each sampled window, in addition to every frame's original source PTS. The validated research report aggregates **sampled frames / inventoried frames in those same requested windows**; it does *not* divide by estimated full-video FPS, nor claim continuous footage was examined. Legacy research records without an independently verified inventory omit this denominator, and their fractions remain unknown. Every sample's rational PTS must fall within its declared source window. The catalog-wide number of analyzed videos remains evidence-based, not imputed from metadata.
