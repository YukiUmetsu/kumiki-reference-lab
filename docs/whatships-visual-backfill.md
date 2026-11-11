# Backfill actual-frame visual measurements across the What Ships corpus

`whatships-visual-backfill` is a separate, resumable numerical-analysis pass over films already processed by the [private authorized-media character worker](whatships-resumable-local-analysis.md). It **does not rerun expensive local Ollama inference**. Instead, it verifies the original source and prior study artifacts, reads the *same originally requested video time windows*, then runs [source-PTS visual probes](source-pts-visual-probes.md) for each segment.

This is useful when growing a large What Ships reference corpus over weeks: you can upgrade earlier character studies with independent pixel/cut evidence without invalidating the existing model reviews or overwriting expensive VLM results.

## Use

First register media, run `whatships-analyze`, and retain its private `analysis-index.json`. Then:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-visual-backfill \
  "$HOME/whatships-private/bindings-002/media-bindings.json" \
  "$HOME/whatships-private/analysis-run-001/analysis-index.json" \
  --snapshot research/whatships-index-2026-11-10.json \
  --max-videos 1 --max-samples 12 \
  --out "$HOME/whatships-private/visual-backfill-001"

# Resume by pointing at the new immutable visual-index.json.
PYTHONPATH=src python -m kumiki_reference_lab whatships-visual-backfill \
  "$HOME/whatships-private/bindings-002/media-bindings.json" \
  "$HOME/whatships-private/analysis-run-002/analysis-index.json" \
  --previous-index "$HOME/whatships-private/visual-backfill-001/visual-index.json" \
  --max-videos 1 --out "$HOME/whatships-private/visual-backfill-002"
```

The original character-analysis index you supply on a resumed run must still include the already analyzed files, unchanged source hashes and valid study manifests. For consistent coverage, use the latest cumulative character-study index. Missing files and modified source media fail closed rather than being silently counted as processed.

## Files and data lineage

The new private run contains `visual-index.json`, a path-redacted `coverage.json`, and per-video outputs under `runs/<slug>/window-000.json`, `window-001.json`, etc. Each window is bound to:

- The exact original What Ships `whatships:slug`, operator-declared rights and the authorized media's SHA-256, video stream and rational source timebase.
- The original `character-study-batch` manifest and each independently preserved child window manifest. Window indices, precise start/end seconds and source SHA must all agree.
- The actual source-PTS frames decoded and verified by FFprobe/FFmpeg, and their sampled pixel/cut measurements. Every output JSON is source-hashed.
- A resumable, private progress ledger that refuses reusing altered visual evidence; it can retry failed videos without repeating completed ones.

The **shareable `coverage.json`** reports source catalog count, operator-bound videos, numerically probed video count, measured windows, per-category status and an explicit **zero human-reviewed measurement count**. It excludes local file paths and private error details. The private `visual-index.json` includes absolute paths to results and must not be committed.

## Scientific boundaries

The numeric fields describe observed display RGB pixel brightness/contrast/saturation, per-frame image differences, and FFmpeg candidate hard cuts. They **do not** prove a camera move, camera motion frequency, zoom, film lighting equipment, art direction, paper-cut layering, 3D rendering, or animation style. Those interpretations need separately sourced visual evidence and review.

`measuredOriginalSourceWindows` counts bounded intervals that had source-PTS numerical measurements. It is **not** a percentage of entire videos or footage frames. Each source window was sparsely sampled; unsampled moments remain unmeasured. Historical X view counts are metadata and have no relationship to measured pixels unless explicitly analyzed with appropriate confounders.

A failure while probing a later window discards **that video's** incomplete probe set but preserves prior completed videos and their original character-study artifacts. The backfill stores no footage itself, downloads no video or model weights and does not contact external services.

## Test

```bash
PYTHONPATH=src python -m unittest tests.test_whatships_visual_backfill tests.test_source_visual_probe -v
```

The backfill's unit tests exercise provenance, child PTS windows, multi-film scheduling, resume, tampering, per-film rollback, missing authorized media and path redaction with mocked decoders. The independent `source-visual-probe` tests use real locally generated FFmpeg video and a 125-second original-PTS seek.

**What remains:** actual source acquisition with appropriate rights, local Mac model inference, expert visual judgments about camera/lighting/styles, and large-scale category-balanced data accumulation. No What Ships third-party videos have been downloaded or analyzed in these tests.
