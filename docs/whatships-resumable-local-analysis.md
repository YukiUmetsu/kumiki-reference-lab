# Resumable local analysis of authorized What Ships videos

**New:** `whatships-analyze` consumes the private [authorized-media bindings](whatships-authorized-local-media.md), independently checks the video SHA-256, stream and rational timebase, and runs the existing original-PTS `character-study-batch` pipeline on selected video windows.

The worker is intended to turn a full What Ships **metadata catalog** into a growing collection of **actual local-frame observations**, without downloading protected media or mislabeling model hypotheses as human-reviewed facts.

## Analyze the next bound video

Once you have an already installed local Ollama vision model and a private `media-bindings.json`:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-analyze \
  "$HOME/whatships-private/bindings-002/media-bindings.json" \
  --snapshot research/whatships-index-2026-11-10.json \
  --model qwen3-vl:8b \
  --max-videos 1 --window-seconds 10 --window-count 2 \
  --max-samples 6 --max-calls 6 --max-pairs 2 \
  --out "$HOME/whatships-private/analysis-run-001"

# Resume without rerunning already completed source/media/model combinations.
PYTHONPATH=src python -m kumiki_reference_lab whatships-analyze \
  "$HOME/whatships-private/bindings-002/media-bindings.json" \
  --previous-index "$HOME/whatships-private/analysis-run-001/analysis-index.json" \
  --model qwen3-vl:8b --max-videos 1 \
  --out "$HOME/whatships-private/analysis-run-002"
```

The output holds one private `analysis-index.json` and a path-redacted `coverage.json`. For each successfully analyzed source it also includes a `runs/<slug>/` directory with the completed `character-study-batch` evidence, source-PTS character descriptions, provisional tracklets, possible interactions, and optional actual-frame QA galleries.

The default is **one film per invocation**, to limit local inference costs. At most four films and six nonoverlapping windows per film can run per invocation. Use `--skip-interactions` to reduce model calls and `--skip-qa` to avoid generating still-frame galleries. This is opt-in local CPU/GPU work, not a background worker or hosted service.

## Source and privacy guarantees

- The exact What Ships `sourceId` and watch URL come **only** from the validated official catalog snapshot; the local media path comes **only** from the private, user-attested binding ledger.
- A binding must declare its lawful-use basis and source identity. The worker **recomputes the local file SHA256**, rechecks FFprobe source stream and timebase against registration, and validates the final analysis manifest against the expected source/model/window count. It refuses a replaced or moved source.
- If a late film fails, its failure is recorded as `failed-preserved-for-retry`, with an error in the **private** `analysis-index.json`; earlier successful film directories and results remain untouched.
- `--previous-index` reuses successful results **only if** their analysis configuration, exact bound media SHA and saved study-manifest SHA still agree. Previously failed films can be retried. Changing model settings requires a fresh index, not pretending prior evidence was collected by the new model.
- The **shareable** `coverage.json` lists indexed/bound/completed/failed counts by category and per-source non-sensitive status. It contains **no local absolute file paths, private rights notes or error messages**.
- The private `analysis-index.json` contains absolute result paths. Do not upload this private index, media-binding ledger, or frame galleries to GitHub or a public bucket. No analysis phase uploads the source video or contacts anything other than the explicitly selected local Ollama daemon.

## Duration-aware sampling

For each source, the worker obtains FFprobe's **reported duration**. It schedules evenly distributed, nonoverlapping windows of at most 30 seconds, constrained to the first hour because the exact-PTS decoder currently caps its source-relative endpoint at 3600 seconds. Shorter films use fewer/shorter windows automatically.

The progress report distinguishes `requestedWindowSpanFraction` from true analysis coverage. For instance, two 10-second windows in an 85-second video represent 20/85 = 23.5% of the film's nominal time **requested for sampling**. But the actual VLM reads only a handful of original PTS frames within those windows: **this is NOT 23.5% frame analysis, narrative/shot coverage, or human-reviewed film coverage**. End-to-end character identities across those windows are also unverified.

This worker currently executes the character and pair-interaction video pipeline. It does **not** produce authenticated camera/lens movement, real-world lighting setup, soundtrack classifications or detailed cinematography summaries. Those require separate timestamped visual/audio evidence and explicit review.

The [separate numeric visual backfill](whatships-visual-backfill.md) can now revisit every completed source's original time windows without rerunning the character VLM, retaining measured cut/color/image-change evidence in a distinct source-hashed progress ledger. Those visual proxies remain unreviewed, not actual camera/light classifications.

## Progress toward all What Ships videos

The November 10 catalog indexes 2,861 videos, but the site is a directory, not an authorized source-video CDN. The worker can analyze only those whose media is separately available with permission and bound privately. The backlog remains explicit for unbound films; no amount of metadata enrichment can replace actually observing their footage.

Useful future work: add optional independent verified audio and numeric motion/cut summaries per source, reviewed-video coverage metrics using all actual PTS samples, automatic source rights inventory, local workload budgeting, and a controlled evaluation cohort across 2D animation, 3D renders, interface motion and live action.

## Test

```bash
PYTHONPATH=src python -m unittest tests.test_whatships_local_worker -v
```

Focused tests cover SHA replacement, source stream mismatch, source-aware duration sampling, per-film persistence, cross-batch resume, missing authorized files, redacted results, model failures and CLI. All model executions in these tests are mocked; the worker reuses the already-tested real FFmpeg source-PTS pipeline from `character-study-batch`.
