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

\`\`\`bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-all export-analysis \
  --snapshot research/whatships-index-2026-11-10.json \
  --observations research/whatships-browser-observations-2026-11-10.json \
  --bindings "$HOME/whatships-private/bindings-002/media-bindings.json" \
  --analysis-index "$HOME/whatships-private/analysis-run-002/analysis-index.json" \
  --visual-index "$HOME/whatships-private/visual-backfill-002/visual-index.json" \
  --out research/analysis/whatships-next
\`\`\`

Review the generated JSON for privacy/permission before committing. When you are satisfied with the source attribution, replace or merge the corresponding per-video files into this canonical directory, update \`index.json\`, and commit them in the same Git change. Use \`whatships-all validate-analysis\` to validate the published corpus before pushing:

\`\`\`bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-all validate-analysis \
  --snapshot research/whatships-index-2026-11-10.json \
  --root research/analysis/whatships
\`\`\`

**Important:** never commit the private \`media-bindings.json\`, \`analysis-index.json\`, \`visual-index.json\`, original footage, source thumbnails, personal system paths, access tokens or full browser session data. The exporter reads those local files only to confirm the original SHA/PTS lineage, and exports a strict whitelist of derived data without local paths.

### What each JSON record preserves

| Field | Meaning |
|---|---|
| \`sourceId\`, \`watchUrl\` | Exact catalog ID and creator/source watch page |
| \`catalogSnapshotSha256\` | SHA-256 binding to the dated directory metadata snapshot |
| \`sourceMediaSha256\` | SHA-256 of the actual local video bytes when numeric evidence is available; absent for browser-only notes |
| \`evidence.browserSpotCheck\` | Partial original visible moments, source tag, style hypotheses and explicit unknown PTS |
| \`evidence.numericVisual.windows[].sampledFrames\` | Actual original source PTS and display-referred RGB brightness/color per sampled decoded frame |
| \`evidence.numericVisual.windows[].sampledFramePairs\` | Exact PTS-anchored image-change measurements, abstaining when a possible cut is crossed |
| \`evidence.numericVisual.windows[].cutCandidatePts\` | Timestamped FFmpeg scene-change candidates |
| \`evidence.characterStudyStatus\` | A completed local model job **without** publishing identities, transcripts, private file paths, or implying review |

The exporter does **not** automatically publish detailed character identities, extracted speech, facial attributes, copyrighted images/audio, model prompts or full video copies. Those require an independently reviewed schema and opt-in policy before Git publication. For current research, per-frame numeric data and partial human observations are immediately machine-readable and reusable across future experiments.

## Data interpretation

**A catalog entry is not a viewed video.** The index counts source-linked analysis records only where evidence exists. A few frames, two ten-second windows, or an unverified model output are **not a complete film review**. An image-difference metric does not prove a camera move; average pixel brightness does not establish physical lighting design. Historical view counts do not establish causality between film style and popularity.

The store is intended for future category-level statistics, engineering regressions, cross-video motion/style research and prototype design decisions, with evidence type and uncertainty preserved rather than silently filled in.
