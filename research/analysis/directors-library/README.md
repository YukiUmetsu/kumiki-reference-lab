# Directors' Library reference pages

Two November 11, 2026 **metadata-only** snapshots:

| File | Latest archive pages | Video pages visited | Vimeo / YouTube embeds |
| --- | ---: | ---: | ---: |
| `index-2026-11-11.json` | 1–2 | 30 | 16 / 14 |
| `index-2026-11-11-pages5.json` | 1–5 | 75 | 40 / 35 |

The larger snapshot includes the first 30 film identities unchanged.
Each record preserves its public Directors' Library URL, site publication
date, category, director names and sanitized player reference. The page
metadata is not a substitute for reviewing original footage.

**No film was downloaded, decoded or measured.** All `durationSeconds` and
`viewCount` values are unknown, `videoAnalysisStatus` is `not-performed`,
and `rightsStatus` is `permission-required`. There are no frame-level camera,
lighting, cut, dialogue, sound or animation observations in these files.

To validate, report and search:

```bash
PYTHONPATH=src python -m kumiki_reference_lab directors-library validate
PYTHONPATH=src python -m kumiki_reference_lab directors-library report
PYTHONPATH=src python -m kumiki_reference_lab video-sources search "asics" \
  --provider directors-library \
  --directors-library research/analysis/directors-library/index-2026-11-11-pages5.json
```

See [the collection and rights methodology](../../../docs/directors-library-research.md)
for instructions on processing a separately authorized original source.
