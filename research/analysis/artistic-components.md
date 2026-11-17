# Measured artistic components

Generated evidence companion. The full documentation, exemplars and reuse recipes live in [`docs/artistic-components.md`](../../docs/artistic-components.md).

- Schema: `kumiki.artistic-components.v1`
- Clustered full-film, non-strobe records: **2,197**
- Full-film records (clustered + strobe): **2,472**
- Windowed records (not clustered): **908**
- Chosen k: **4**, mean silhouette **0.401**
- Distinctness: threshold met; k unstable across folds ({'3': 3, '4': 1, '7': 1})

| component | n | share | median cut rate (cuts/min) | median shot (s) | sites |
|---|---:|---:|---:|---:|---|
| `steady-cut` | 1,695 | 68.6% | 20.73 | 1.88 | aicp (552), directorslibrary (106), motiondesignawards (223), promonews (239), shots (575) |
| `strobe-textured` | 275 | 11.1% | 48.66 | 0.24 | aicp (46), directorslibrary (9), motiondesignawards (104), promonews (40), shots (76) |
| `decelerating-long-take` | 229 | 9.3% | 1.67 | 16.79 | aicp (29), directorslibrary (7), motiondesignawards (111), promonews (18), shots (64) |
| `rapid-cut` | 208 | 8.4% | 52.95 | 0.77 | aicp (58), directorslibrary (8), motiondesignawards (44), promonews (19), shots (79) |
| `accelerating-steady-cut` | 65 | 2.6% | 16.66 | 1.69 | aicp (18), directorslibrary (12), motiondesignawards (9), promonews (15), shots (11) |

## Method

- Linkage: complete-linkage agglomerative
- Standardization: median/IQR; fallback 1.4826*MAD, then unit scale; missing values imputed at the median and clipped at ±4
- Distance: Euclidean on robust-standardized features
- k selection: best mean silhouette over candidates; ties to smaller k
- Silhouette sampling: fixed stride, at most 2000 rows
- k stability: {'3': 3, '4': 1, '7': 1} over 5 folds
- Cluster features: `cutsPerMinute`, `medianShotSeconds`, `burstFraction`, `shotsUnderHalfSecondPct`, `paceDriftRatio`, `flickerLumaPerSecond`

## Limits

- Cut candidates are not verified edits: an ffmpeg scene-score exceedance is also produced by fast motion, flashes, dissolves and compression.
- A component is a measurement cluster, not a genre, a style verdict or a quality ranking; the names summarise measured timing only.
- Strobe detection is a fixed threshold on sampled luma instability, not a ground-truth photic-safety or flash-rate measurement.
- Rendition and bitrate affect both cut detection and luma/saturation proxies; the same work at another bitrate can move between components.
- Sampling coverage is uneven: promonews and directorslibrary contribute mostly windowed records, and windowed records are not clustered because their full-runtime strobe status is unknown.
- Windowed evidence covers at most 40 s spread across a runtime, so long films are under-sampled and short clips are over-represented in that share; windowed records never enter the component fit.
- Audio exists on a subset of records, so loudness and onset bands are derived from that subset only; per-feature coverage is reported.
- Component profiles are descriptive quantiles over observed records; they do not establish a target, a recommendation or a causal edit effect.
- No expert or human review was performed; every number is an automated proxy over decoded renditions.
- The evidence trees were still being written by harvest lanes during derivation: this is a snapshot of the counts in `generatedFrom`, and a later run can produce different counts and, at the margin, a different k.
