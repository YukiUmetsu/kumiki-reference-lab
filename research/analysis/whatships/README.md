# Versioned What Ships video analysis data

**This directory is the canonical Git-tracked analysis dataset.** It contains one structured JSON record per video with observed evidence. It is separate from the all-video catalog, the footage itself and private local model/FFmpeg run artifacts.

- **[index.json](index.json)**: machine-readable list of all committed evidence records, the dated catalog snapshot SHA-256 and counts by evidence type
- **[claude-motion-reel.json](claude-motion-reel.json)**, **[paper-mono-code.json](paper-mono-code.json)**, **[figma-3980.json](figma-3980.json)**, etc.: source-linked observations and hypotheses for a single video
- **[../../whatships-index-2026-11-10.json](../../whatships-index-2026-11-10.json)**: directory metadata for all 2,861 catalog videos, including unobserved videos
- **[../../whatships-browser-observations-2026-11-10.json](../../whatships-browser-observations-2026-11-10.json)**: original historical nine-film browser spot-check source; the per-video files here preserve those observations and provenance

The first **nine files** were migrated from the November 10 browser observation cohort. They contain selected visible moments and visual technique hypotheses, **not measured original timestamps** or full-video reviews. At the time of initial publication, **zero** real What Ships third-party video files had been successfully analyzed by the local source-PTS pixel pipeline in this dataset.

## How future local runs become repository data

Use the private rights-attested media bindings, the completed local character studies, and the optional visual backfill described in [What Ships analysis workflows](../../../docs/whatships-resumable-local-analysis.md) and [numeric visual backfill](../../../docs/whatships-visual-backfill.md).

After processing authorized local video, export **sanitized, complete frame-level numeric evidence** to a new Git-ready directory:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-all export-analysis \
  --snapshot research/whatships-index-2026-11-10.json \
  --observations research/whatships-browser-observations-2026-11-10.json \
  --bindings "$HOME/whatships-private/bindings-002/media-bindings.json" \
  --analysis-index "$HOME/whatships-private/analysis-run-002/analysis-index.json" \
  --visual-index "$HOME/whatships-private/visual-backfill-002/visual-index.json" \
  --out research/analysis/whatships-next
```

Review the generated JSON for privacy/permission before committing. Then **merge verified new layers into the tracked directory** without erasing existing browser evidence:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-all sync-analysis \
  --snapshot research/whatships-index-2026-11-10.json \
  --incoming research/analysis/whatships-next \
  --root research/analysis/whatships

git add research/analysis/whatships
git commit -m "data: add verified What Ships source-PTS observations"
```

`sync-analysis` merges by exact source ID and evidence type. Conflicting existing data is rejected unless `--replace-existing` is explicitly provided; Git history preserves prior versions. It checks the catalog snapshot, every source-PTS frame/pair and the typed metric schema. A failed update rolls back altered JSON files. This updates your local Git worktree, but does not commit/push on your behalf.

Use `whatships-all validate-analysis` to verify the published corpus before pushing:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-all validate-analysis \
  --snapshot research/whatships-index-2026-11-10.json \
  --root research/analysis/whatships
```

**Important:** never commit the private `media-bindings.json`, `analysis-index.json`, `visual-index.json`, original footage, source thumbnails, personal system paths, access tokens or full browser session data. The exporter reads those local files only to confirm the original SHA/PTS lineage, and exports a strict whitelist of derived data without local paths.

### What each JSON record preserves

| Field | Meaning |
|---|---|
| `sourceId`, `watchUrl` | Exact catalog ID and creator/source watch page |
| `catalogSnapshotSha256` | SHA-256 binding to the dated directory metadata snapshot |
| `sourceMediaSha256` | SHA-256 of the actual local video bytes when numeric evidence is available; absent for browser-only notes |
| `evidence.browserSpotCheck` | Partial original visible moments, source tag, style hypotheses and explicit unknown PTS |
| `evidence.numericVisual.windows[].sampledFrames` | Actual original source PTS and display-referred RGB brightness/color per sampled decoded frame |
| `evidence.numericVisual.windows[].sampledFramePairs` | Exact PTS-anchored image-change measurements, abstaining when a possible cut is crossed |
| `evidence.numericVisual.windows[].cutCandidatePts` | Timestamped FFmpeg scene-change candidates |
| `evidence.characterStudyStatus` | A completed local model job **without** publishing identities, transcripts, private file paths, or implying review |

The exporter does **not** automatically publish detailed character identities, extracted speech, facial attributes, copyrighted images/audio, model prompts or full video copies. Those require an independently reviewed schema and opt-in policy before Git publication. For current research, per-frame numeric data and partial human observations are immediately machine-readable and reusable across future experiments.

## Data interpretation

**A catalog entry is not a viewed video.** The index counts source-linked analysis records only where evidence exists. A few frames, two ten-second windows, or an unverified model output are **not a complete film review**. An image-difference metric does not prove a camera move; average pixel brightness does not establish physical lighting design. Historical view counts do not establish causality between film style and popularity.

The store is intended for future category-level statistics, engineering regressions, cross-video motion/style research and prototype design decisions, with evidence type and uncertainty preserved rather than silently filled in.

## Analyze the saved cohort without private footage

Use `whatships-all research-report` to count and group *actual committed observations*, visual tags and later original-PTS measurements. `whatships-all browse --out runs/whatships-catalog` builds an offline HTML table from the full dated catalog and overlays this verified `research/analysis/whatships/` dataset by default. Select **Saved visual observations** to see films with observed moments; open Details to read the observations and explicitly labeled technique hypotheses. This does not turn metadata-only entries into analyzed videos.

## Committed cross-video technique summary

The dated [source-observation technique rollup](../whatships-observed-techniques-2026-11-10.json) reports per-tag frequencies for the nine partially observed videos, per-category counts, and the total 2,861-video catalog denominator. These counts describe **only explicitly recorded visual observations**, not all the indexed films, and cannot support claims about causal virality, lighting frequencies or camera movements. The lightweight GitHub CI recomputes the report from the canonical source records, so editing/adding research observations requires updating this summary in the same commit.

## Direct numeric analysis, without a character VLM

[whatships-measure](../../../docs/whatships-direct-research.md) uses an already bound authorized local video and records actual original-source-PTS frames and numeric motion/color/cut measurements **directly in this Git directory**. It does not require a character model, an intermediate private study index or a backfill. It preserves existing partial browser notes; explicit `--replace-existing` is required for changed numeric measurements. Review `git diff`, then commit ordinary source-linked research JSON.

## Source-PTS frame inventory denominators

Newly measured records store `scan.sourcePtsFramesSeenInInventory` for each sampled window, in addition to every frame's original source PTS. The validated research report aggregates **sampled frames / inventoried frames in those same requested windows**; it does *not* divide by estimated full-video FPS, nor claim continuous footage was examined. Legacy research records without an independently verified inventory omit this denominator, and their fractions remain unknown. Every sample's rational PTS must fall within its declared source window. The catalog-wide number of analyzed videos remains evidence-based, not imputed from metadata.

## Run a bounded category-balanced analysis batch

Use [`whatships-measure-batch`](../../../docs/whatships-direct-batch.md) with the private authorized media-binding ledger to analyze up to four unmeasured source videos, automatically skipping completed SHA-identical records and preserving each successful per-video JSON in this Git directory. One failed video does not discard earlier measured results. Inspect the resulting `git diff` before committing; no raw video or private path is stored here.

## Incrementally fill the remaining timeline gaps

A film's first analysis contains sparse windows, not continuous coverage. Repeat the original-source-PTS measurement with `--fill-gaps` to add disjoint intervals to the **same** versioned source record:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-measure \
  "$HOME/whatships-private/bindings-002/media-bindings.json" \
  whatships:paper-mono-code --fill-gaps \
  --window-seconds 10 --window-count 6 --max-samples 12
```

The planner uses the already saved `[startSeconds,endSeconds)` intervals, selects the largest uncovered gaps, and processes up to six new windows per invocation. It permits short final windows and does not repeat existing windows. Additions must be source-SHA-identical and **strictly nonoverlapping**. Any conflicting or overlapping measurements fail rather than replacing prior evidence. Source records can currently contain up to 64 measured windows; source-relative video time after one hour remains unsupported by the decoder.

When all supported whole-second intervals have been assigned a sampled window, the command reports `no-remaining-whole-second-gaps-within-supported-timeline` without altering the Git worktree. **This does not imply that all frames within those intervals were decoded, or that the film was human reviewed.** Source-PTS inventory counts still distinguish sampled frames from available frames within each interval.

For previous batch exports, `whatships-all sync-analysis --append-numeric-windows --incoming ...` offers the same nonoverlapping merge policy. Do not combine it with `--replace-existing`. Subsequent `git add` and `git commit` remain explicit.

## Optional ephemeral source acquisition

If you have permission to study the original public X video associated with a What Ships record, [`whatships-acquire-measure`](../../../docs/whatships-ephemeral-acquisition.md) offers a single authorized acquisition → source-PTS numerical analysis → versioned JSON update workflow. Its public X downloader runs without authentication/cookies and deletes the downloaded media and private binding ledger on success or failure. Only actual frame-derived numeric evidence remains in the Git worktree; source identity and rights must be separately attested.

## Soundtrack energy observations

[`whatships-audio-measure`](../../../docs/whatships-audio-energy-research.md) writes a separate `evidence.numericAudio.windows[]` layer of 100 ms decoded PCM RMS/peak digital amplitude and near-silence heuristics, using an authorized local video file. Source media SHA is verified, and only numeric data reach Git. **Audio bucket positions are decoder offsets, not independently verified original video PTS.** This is not beat detection, narrated text, audio-visual synchronization, LUFS, or human-reviewed sound design. The browser and research report show these data separately.

## Optional original-PTS apparent image-plane movement

Use [`whatships-measure --image-translation`](../../../docs/whatships-source-pts-image-translation.md) (or the bounded batch/ephemeral public-source workflow) to append source-PTS paired **FFT phase-correlation global image translation hypotheses** to committed `numericVisual` observations. The optional NumPy motion extra is required. Cut candidates force abstention; missing/ambiguous results are not zero camera movement. These displacement metrics are **not** verified camera pan, tilt, zoom, dolly, independent subject motion or production style. Existing records without this probe remain valid.
