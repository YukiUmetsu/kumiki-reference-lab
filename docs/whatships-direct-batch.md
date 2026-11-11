# Bounded direct video analysis across the What Ships catalog

Use `whatships-measure-batch` to process several **operator-authorized, locally bound** What Ships videos and immediately save each successful source's original-PTS numerical evidence into `research/analysis/whatships/<slug>.json`. It requires no Ollama model, no prior character-study pipeline and no video download from the What Ships directory.

## Analyze several sources without waiting for manual feedback

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-measure-batch \
  "$HOME/whatships-private/bindings-002/media-bindings.json" \
  --max-videos 4 --window-seconds 10 --window-count 4 --max-samples 12

# Optionally restrict to motion videos
PYTHONPATH=src python -m kumiki_reference_lab whatships-measure-batch \
  "$HOME/whatships-private/bindings-002/media-bindings.json" \
  --category motion --max-videos 4

# If one inaccessible clip repeatedly fails, skip the first pending candidate
PYTHONPATH=src python -m kumiki_reference_lab whatships-measure-batch \
  "$HOME/whatships-private/bindings-002/media-bindings.json" \
  --start-offset 1 --max-videos 4
```

The queue interleaves all eight categories rather than prioritizing only high-view/AI entries. It skips previously measured sources when their committed numeric evidence matches the current authorized video SHA-256, while visibly flagging stale prior source fingerprints instead of silently overwriting them.

Each source is processed using the [direct source-frame measurement](whatships-direct-research.md) CLI engine, which validates the underlying media SHA-256, video stream, rational source timebase, measured frame timestamps and numeric data. Each successful video's JSON is synced into Git *before* the next video starts. A later failed video cannot erase earlier successful analysis results. Failed videos remain eligible on a future run; errors appear as types only to prevent private paths leaking into shared progress reports.

Output states the numbers of source-bound videos, measured videos already in Git, attempted/successful/failed films, stale bindings, and sampled-frame inventories for each newly measured source. It reports **zero full human-reviewed films** unless a separate reviewed-evidence pipeline is developed. Time windows and pixel measurements must never be mistaken for full film coverage, actual lens/camera movement, physical lights or causal style popularity.

After each invocation, inspect and commit the changed source-linked JSON in the normal way:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-all validate-analysis
git diff -- research/analysis/whatships
git add research/analysis/whatships
git commit -m "data: measure next What Ships reference videos"
```

The command does not commit/push, run indefinitely or schedule a background job. It cannot cover unbound videos until authorized source bytes become available. The November 10 catalog has 2,861 indexed entries; existing initial browser observations remain partial. No whole-video numeric analysis is fabricated for media we cannot inspect.

## Test

```bash
PYTHONPATH=src python -m unittest tests.test_whatships_direct_measure_batch -v
```

The tests exercise Git-backed checkpoints, category-balanced selection, repeat-run skips, failed-source recovery, fingerprint drift, and path-redacted progress with synthetic source media and mocked FFmpeg decoding. The underlying source-PTS reader has independent real FFmpeg tests.
