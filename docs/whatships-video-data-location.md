# Where to find the What Ships video data

Kumiki Reference Lab separates **(1) catalog entries**, **(2) actual observed video evidence**, and **(3) private local source footage and model runs**. The directory data is available in the GitHub repository; source videos and private local paths are never automatically committed.

## In the Git repository

| Path | What it holds | Current coverage |
| --- | --- | --- |
| [research/whatships-index-2026-11-10.json](../research/whatships-index-2026-11-10.json) | Title/creator/category/watch URL for every indexed video; some original post/view/duration details | 2,861 catalog records, 419 detailed as of November 10 |
| [research/whatships-motion-2026-11-10.json](../research/whatships-motion-2026-11-10.json) | Full-detail Motion category metadata | 69 videos, metadata only |
| [research/analysis/whatships/](../research/analysis/whatships/) | **Canonical machine-readable per-video analysis records**, indexed in one `index.json` | Nine partial browser-observation records at first import |
| [research/whatships-browser-observations-2026-11-10.json](../research/whatships-browser-observations-2026-11-10.json) | Original partial browser video-viewing notes from which the first nine records were derived | Nine sampled-moment observations |
| [docs/whatships-observed-motion.md](whatships-observed-motion.md) | Readable interpretation and video examples | Partial source visual notes |

There are **no real downloaded What Ships media files** in those Git directories, and no blanket verified camera movement/lighting/animation-style labels. Film files require a separately lawful local source and are intentionally excluded.

## Open a searchable table, instead of scrolling through JSON

Generate a standalone **offline searchable HTML**, JSON export and CSV:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-all browse \
  --out ./runs/whatships-data-browser

open ./runs/whatships-data-browser/whatships-videos.html
```

This lists every entry in the dated snapshot, sortable and filterable by title, creator, category, known historical views, detailed metadata and available analytical evidence. You can click through to the What Ships watch page and see evidence-status fields without downloading footage. The generated browser has no network API or external JavaScript/CSS dependencies, and does not include local video paths. Links to the original hosted videos are opened only when clicked.

For a browser built from your **verified private local analysis runs**:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-all browse \
  --bindings "$HOME/whatships-private/bindings-002/media-bindings.json" \
  --analysis-index "$HOME/whatships-private/analysis-run-002/analysis-index.json" \
  --visual-index "$HOME/whatships-private/visual-backfill-002/visual-index.json" \
  --out ./runs/whatships-data-browser-with-analysis
```

The table then displays evidence-layer status and bounded numeric original-PTS image measurements. The actual private video/source material remains local.

## Persist your measured results in Git

This is an explicit requirement, not an optional notebook cache. The [versioned analysis store](../research/analysis/whatships/README.md) exports verified observation evidence by `whatships:slug` to Git-friendly JSON:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-all export-analysis \
  --observations research/whatships-browser-observations-2026-11-10.json \
  --out research/analysis/whatships-next

PYTHONPATH=src python -m kumiki_reference_lab whatships-all validate-analysis \
  --root research/analysis/whatships
```

The exporter can additionally consume private binding, character study and numeric visual indices (see the store README). Merge the generated records into the canonical tracked corpus:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-all sync-analysis \
  --incoming research/analysis/whatships-next \
  --root research/analysis/whatships

git add research/analysis/whatships && git commit -m "data: extend What Ships analysis corpus"
```

Conflicting evidence requires explicit `--replace-existing` and is then protected by Git history. The command does not silently push or create commits; versioned per-video records support future statistical analysis.

**Current limit:** The nine source-viewing observations are selected-moment qualitative data, without accurate original PTS. Generated source-PTS metrics can be added after authorized footage is processed; they have not been fabricated for the rest of the catalog. Original media, extracted images and unredacted dialogue/identity data remain private unless separately reviewed and authorized.

## Browse committed analysis and report actual research coverage

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-all browse \
  --repository-analysis research/analysis/whatships \
  --out runs/browse-committed-evidence
open runs/browse-committed-evidence/whatships-videos.html

PYTHONPATH=src python -m kumiki_reference_lab whatships-all research-report \
  --root research/analysis/whatships
```

By default `browse` reads the committed evidence corpus, shows observed video moments and their technique hypotheses, and filters by saved observations. `--no-repository-analysis` disables this layer. `research-report` counts only evidence that is in the codebase, not unobserved catalog metadata. The original nine partial browser observations have no original frame timestamps. Tag frequencies are not population estimates.

## Committed cross-video technique summary

The dated [source-observation technique rollup](../research/analysis/whatships-observed-techniques-2026-11-10.json) reports per-tag frequencies for the nine partially observed videos, per-category counts, and the total 2,861-video catalog denominator. These counts describe **only explicitly recorded visual observations**, not all the indexed films, and cannot support claims about causal virality, lighting frequencies or camera movements. The lightweight GitHub CI recomputes the report from the canonical source records, so editing/adding research observations requires updating this summary in the same commit.
