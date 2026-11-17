# Measured artistic components

These are **measurement clusters** of decoded reference renditions. Each component groups records whose measured timing/texture values are close after median/IQR standardization and complete-linkage agglomeration. A component is a place on a measured scale, not a genre, a style verdict, a mood or a quality tier. The names below are assembled from a fixed timing vocabulary by explicit thresholds.

The chosen k scored a mean silhouette of 0.401 at or above the 0.25 threshold used here. That is a moderate separation at best; it does not turn the clusters into natural categories, and records near a boundary remain close to their neighbouring component.

> **k is not stable.** In deterministic 80 % resamples the winning k changed (k=3 in 3 fold(s), k=4 in 1 fold(s), k=7 in 1 fold(s)). At the chosen k the fold silhouette ranged 0.328–0.369. The component count below is one defensible cut-point on a continuum, not a discovered number of types.

## At a glance

- Clustered records: **2,197** full-film records with `strobe == false`; **2,472** full-film records total.
- Windowed records not clustered (full-runtime strobe status unknown): **908**.
- Strobe-flagged records, reported separately: **275**.
- k selected by best mean silhouette over 3..8: **4** (silhouette 0.401).
- Candidate silhouettes: k=3: 0.381, k=4: 0.401, k=5: 0.380, k=6: 0.368, k=7: 0.212, k=8: 0.208. Nearby scores mean the k choice is not decisive.
- k stability across 5 deterministic 80 % stride folds: k=3: 3 fold(s), k=4: 1 fold(s), k=7: 1 fold(s). The winning k is not stable across folds, so the component count is a measurement choice, not a property of the corpus.
- Audio-measured records used for loudness/onset bands: see per-feature coverage below.

| component | n | share | median cut rate (cuts/min) | median shot (s) | sites |
|---|---:|---:|---:|---:|---|
| `steady-cut` | 1,695 | 68.6% | 20.73 | 1.88 | aicp (552), directorslibrary (106), motiondesignawards (223), promonews (239), shots (575) |
| `strobe-textured` | 275 | 11.1% | 48.66 | 0.24 | aicp (46), directorslibrary (9), motiondesignawards (104), promonews (40), shots (76) |
| `decelerating-long-take` | 229 | 9.3% | 1.67 | 16.79 | aicp (29), directorslibrary (7), motiondesignawards (111), promonews (18), shots (64) |
| `rapid-cut` | 208 | 8.4% | 52.95 | 0.77 | aicp (58), directorslibrary (8), motiondesignawards (44), promonews (19), shots (79) |
| `accelerating-steady-cut` | 65 | 2.6% | 16.66 | 1.69 | aicp (18), directorslibrary (12), motiondesignawards (9), promonews (15), shots (11) |

## Method

1. **Join.** Each video record is matched to its full-runtime census record by record id, with a media SHA-256 fallback. Census is preferred; a video without a census record falls back to its windowed summary and is marked `windowed`. Audio and catalog metadata are joined when present.
2. **Features.** Clustering uses only measured timing/texture: `cutsPerMinute`, `medianShotSeconds`, `burstFraction`, `shotsUnderHalfSecondPct`, `paceDriftRatio`, `flickerLumaPerSecond`. Palette and audio features are reported per component but do not decide membership.
3. **Robust standardization.** Each feature is centred on the corpus median and scaled by its interquartile range. When the IQR is 0 the scale falls back to 1.4826 × median absolute deviation, then to 1.0; missing values are imputed at the median of the present values (standardized 0) and counted per feature; values are clipped at ±4.
4. **Complete-linkage agglomeration.** Euclidean distance between standardized vectors; merge cost is the maximum pairwise distance between clusters. Ties break on the smaller row index, so input order fully determines the dendrogram.
5. **k selection.** Mean silhouette is computed for k = 3..8; the best score wins and a tie goes to the smaller k. Above 2,000 rows the silhouette uses a fixed-stride sample of at most 2,000 rows (no randomness).
6. **Strobe separation.** Records whose census carries `strobe == true` never enter the cut-rate clustering; they form one `strobe-textured` component with its own profile and recipe.

## What a component is not

- Not a genre, format, market or audience category.
- Not a style verdict, a quality ranking or an award signal.
- Not a claim about intent, authorship, budget or influence.
- Not a natural kind: it is a cut through a measured distribution, and its edge cases are arbitrary.
- Not a licence to copy a specific work; it is a set of aggregate measured numbers.

## Known confounds

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

## How to use a component in practice

1. Pick the target duration first (15/30/60/90 s) and the intended pace band second: choose a component whose median cut rate and median shot length bracket the pace you want.
2. Read the reuse recipe as a starting mid-point. Place your own planned cuts on the same measured scale; if you diverge, you are deliberately leaving the measured cluster, not failing it.
3. Use the loudness, onset and palette bands as measured context, not as delivery specifications; they come from a subset and describe renditions, not masters.
4. State the component and the evidence level (`full-film` or `windowed`) whenever you cite it, and never cite a component as evidence of quality or intent.

## Components

### `steady-cut`

**n = 1,695** (68.6% of the 2,472 full-film records). Sites: aicp (552), directorslibrary (106), motiondesignawards (223), promonews (239), shots (575). Exemplar ranking: highest per-record silhouette, tie-break by id.

Measured signature

| feature | p10 | median | p90 | unit | measured on |
|---|---:|---:|---:|---|---:|
| `cutsPerMinute` | 7.640 | 20.729 | 36.736 | cuts/min | 1695/1695 |
| `medianShotSeconds` | 1.034 | 1.880 | 3.990 | s | 1656/1695 |
| `p10ShotSeconds` | 0.133 | 0.815 | 1.841 | s | 1656/1695 |
| `p90ShotSeconds` | 3.014 | 5.361 | 13.218 | s | 984/1695 |
| `burstFraction` | 0.000 | 0.000 | 0.281 | fraction | 1643/1695 |
| `shotsUnderHalfSecondPct` | 0.000 | 3.448 | 26.159 | % | 984/1695 |
| `paceDriftRatio` | 0.267 | 0.875 | 1.781 | ratio | 935/1695 |
| `flickerLumaPerSecond` | 0.006 | 0.019 | 0.042 | luma/s | 984/1695 |
| `durationSeconds` | 30.059 | 92.992 | 232.367 | s | 1695/1695 |
| `meanLuma` | 0.147 | 0.267 | 0.488 | 0-1 | 1695/1695 |
| `meanSaturation` | 0.148 | 0.309 | 0.477 | 0-1 | 1695/1695 |
| `integratedLufs` | -22.500 | -14.400 | -8.600 | LUFS | 1418/1695 |
| `onsetPerMinute` | 205.512 | 285.899 | 337.175 | onsets/min | 1418/1695 |

Exemplars

| site | record id | slug | title | duration (s) |
|---|---|---|---|---:|
| shots | `40539` | `inflatables` | Inflatables | 30.1 |
| shots | `40497` | `see-yourself-in-canada-prince-edward-island` | See Yourself in Canada - Prince Edward Island | 30.1 |
| shots | `40819` | `common-ground` | Common Ground | 120.0 |
| promonews | `85453` | `thomas-de-pourquery-rhythm-changed-ludovic-gontrand` | Thomas De Pourquery 'The Rhythm Changed' by Ludovic Gontrand | 244.9 |
| shots | `36503` | `power-struggle` | Power Struggle | 60.1 |
| aicp | `811382` | `5-missing-menu-meal-tik-tok` | $5 Missing Menu Meal-Tik Tok | 122.3 |

Reuse recipe

```text
target cuts at the component's measured rate
  15 s: 5 cuts   (3.00 s median interval)
  30 s: 10 cuts   (3.00 s median interval)
  60 s: 21 cuts   (2.86 s median interval)
  90 s: 31 cuts   (2.90 s median interval)

measured shot durations
  p10 1.03 s | median 1.88 s | p90 3.99 s

expected pace trajectory
  near-flat | last-third ÷ first-third drift 0.88 | first third 19.5 cuts/min (984 records) | last third 17.4 cuts/min (984 records)
  (each pace figure is a per-record median; they need not reconcile arithmetically)

measured loudness band (audio-measured subset)
  integrated -22.5 to -8.6 LUFS (median -14.4) | LRA median 7.0 LU | true peak median -0.8 dBFS

measured onset band
  205.5 to 337.2 onsets/min (median 285.9)

measured palette band
  mean luma 0.15-0.49 | mean saturation 0.15-0.48
  derived from 1695 records (loudness from 1418, onset from 1418, palette from 1695)
```

These are measured mid-points, not prescriptions. The arithmetic is `cuts = round(median cut rate × target seconds / 60)` over this component's 1695 records; it says where the cluster sits, not what a new piece should do.

What this does not establish

- This component does not establish that these works share a genre, a market, a mood, a budget, an intent or a quality level. It establishes that their measured timing/texture values sit near each other.
- The cluster does not establish that a cut here is an edit: candidates include flashes, fast motion, dissolves and compression artefacts.
- Membership does not establish authorship, studio practice or influence; the feature space contains no names, credits or dates.

### `strobe-textured`

**n = 275** (11.1% of the 2,472 full-film records). Sites: aicp (46), directorslibrary (9), motiondesignawards (104), promonews (40), shots (76). Exemplar ranking: closest to the component centroid.

Measured signature

| feature | p10 | median | p90 | unit | measured on |
|---|---:|---:|---:|---|---:|
| `cutsPerMinute` | 15.751 | 48.655 | 132.941 | cuts/min | 275/275 |
| `medianShotSeconds` | 0.083 | 0.240 | 1.042 | s | 275/275 |
| `p10ShotSeconds` | 0.040 | 0.080 | 0.133 | s | 275/275 |
| `p90ShotSeconds` | 0.975 | 3.210 | 9.492 | s | 188/275 |
| `burstFraction` | 0.546 | 0.707 | 0.950 | fraction | 275/275 |
| `shotsUnderHalfSecondPct` | 39.247 | 60.159 | 80.153 | % | 188/275 |
| `paceDriftRatio` | 0.057 | 0.933 | 3.467 | ratio | 170/275 |
| `flickerLumaPerSecond` | 0.009 | 0.030 | 0.085 | luma/s | 188/275 |
| `durationSeconds` | 17.920 | 64.298 | 235.465 | s | 275/275 |
| `meanLuma` | 0.134 | 0.290 | 0.599 | 0-1 | 275/275 |
| `meanSaturation` | 0.087 | 0.360 | 0.614 | 0-1 | 275/275 |
| `integratedLufs` | -20.900 | -13.900 | -8.100 | LUFS | 246/275 |
| `onsetPerMinute` | 210.764 | 292.856 | 338.024 | onsets/min | 246/275 |

Exemplars

| site | record id | slug | title | duration (s) |
|---|---|---|---|---:|
| motiondesignawards | `113` | `wolverine-hellcat` | Wolverine: Hellcat | 30.0 |
| motiondesignawards | `2648` | `rechannel` | Rechannel | 51.4 |
| shots | `41246` | `100-real-with-pamela-anderson` | 100% Real with Pamela Anderson | 60.1 |
| motiondesignawards | `2723` | `sevilla-design-walk-26-main-titles` | Sevilla Design Walk 26 - Main Titles | 35.9 |
| aicp | `1173959` | `gatorade-cool-seats` | Gatorade – Cool Seats | 116.9 |
| motiondesignawards | `189` | `mission-m101` | Mission M101 | 212.8 |

Reuse recipe

```text
target cuts at the component's measured rate
  15 s: 12 cuts   (1.25 s median interval)
  30 s: 24 cuts   (1.25 s median interval)
  60 s: 49 cuts   (1.22 s median interval)
  90 s: 73 cuts   (1.23 s median interval)

measured shot durations
  p10 0.08 s | median 0.24 s | p90 1.04 s

expected pace trajectory
  near-flat | last-third ÷ first-third drift 0.93 | first third 36.4 cuts/min (188 records) | last third 38.2 cuts/min (188 records)
  (each pace figure is a per-record median; they need not reconcile arithmetically)

measured loudness band (audio-measured subset)
  integrated -20.9 to -8.1 LUFS (median -13.9) | LRA median 5.8 LU | true peak median -0.2 dBFS

measured onset band
  210.8 to 338.0 onsets/min (median 292.9)

measured palette band
  mean luma 0.13-0.60 | mean saturation 0.09-0.61
  derived from 275 records (loudness from 246, onset from 246, palette from 275)
```

These are measured mid-points, not prescriptions. The arithmetic is `cuts = round(median cut rate × target seconds / 60)` over this component's 275 records; it says where the cluster sits, not what a new piece should do.

What this does not establish

- The cluster does not establish that a cut here is an edit: candidates include flashes, fast motion, dissolves and compression artefacts.
- The profile does not establish a target or a recommendation. The recipe reports mid-points so a new piece can be placed on the same measured scale, not told what to become.
- A record near a boundary could move to a neighbouring component at a different k or a different feature set; component edges are measurement cut-points, not natural kinds.

### `decelerating-long-take`

**n = 229** (9.3% of the 2,472 full-film records). Sites: aicp (29), directorslibrary (7), motiondesignawards (111), promonews (18), shots (64). Exemplar ranking: highest per-record silhouette, tie-break by id.

Measured signature

| feature | p10 | median | p90 | unit | measured on |
|---|---:|---:|---:|---|---:|
| `cutsPerMinute` | 0.000 | 1.671 | 5.293 | cuts/min | 229/229 |
| `medianShotSeconds` | 8.001 | 16.792 | 66.743 | s | 229/229 |
| `p10ShotSeconds` | 2.103 | 9.394 | 62.515 | s | 229/229 |
| `p90ShotSeconds` | 13.083 | 27.802 | 93.715 | s | 200/229 |
| `burstFraction` | 0.000 | 0.000 | 0.067 | fraction | 106/229 |
| `shotsUnderHalfSecondPct` | 0.000 | 0.000 | 0.000 | % | 200/229 |
| `paceDriftRatio` | 0.000 | 0.000 | 1.000 | ratio | 78/229 |
| `flickerLumaPerSecond` | 0.001 | 0.009 | 0.031 | luma/s | 200/229 |
| `durationSeconds` | 17.907 | 51.051 | 179.277 | s | 229/229 |
| `meanLuma` | 0.084 | 0.231 | 0.718 | 0-1 | 229/229 |
| `meanSaturation` | 0.085 | 0.301 | 0.595 | 0-1 | 229/229 |
| `integratedLufs` | -23.100 | -15.000 | -10.200 | LUFS | 221/229 |
| `onsetPerMinute` | 173.090 | 281.731 | 333.296 | onsets/min | 221/229 |

Exemplars

| site | record id | slug | title | duration (s) |
|---|---|---|---|---:|
| motiondesignawards | `2005` | `flodesk-case-study` | FloDesk Case Study | 56.6 |
| motiondesignawards | `2653` | `the-palace-of-illusions` | The Palace of Illusions | 49.7 |
| directorslibrary | `76390` | `chanel-25-handbag-chanel` | ‘Chanel 25 Handbag’ Chanel | 53.1 |
| motiondesignawards | `778` | `astro-man` | ASTRO - MAN | 31.7 |
| shots | `41316` | `twas-the-season` | Twas the Season | 96.4 |
| shots | `41150` | `behind-the-scenes-of-wear-your-best-life` | Behind the Scenes of Wear Your Best Life | 33.7 |

Reuse recipe

```text
target cuts at the component's measured rate
  15 s: 0 cuts   (— median interval)
  30 s: 1 cut   (30.00 s median interval)
  60 s: 2 cuts   (30.00 s median interval)
  90 s: 3 cuts   (30.00 s median interval)

measured shot durations
  p10 8.00 s | median 16.79 s | p90 66.74 s

expected pace trajectory
  decelerating | last-third ÷ first-third drift 0.00 | first third 0.0 cuts/min (200 records) | last third 0.0 cuts/min (200 records)
  (each pace figure is a per-record median; they need not reconcile arithmetically)

measured loudness band (audio-measured subset)
  integrated -23.1 to -10.2 LUFS (median -15.0) | LRA median 7.4 LU | true peak median -0.9 dBFS

measured onset band
  173.1 to 333.3 onsets/min (median 281.7)

measured palette band
  mean luma 0.08-0.72 | mean saturation 0.08-0.60
  derived from 229 records (loudness from 221, onset from 221, palette from 229)
```

These are measured mid-points, not prescriptions. The arithmetic is `cuts = round(median cut rate × target seconds / 60)` over this component's 229 records; it says where the cluster sits, not what a new piece should do.

A 0-cut target at a short duration is the arithmetic result of a very low measured rate, not a recommendation for an empty film; at that duration the shot-duration band is the more useful number.

What this does not establish

- The profile does not establish a target or a recommendation. The recipe reports mid-points so a new piece can be placed on the same measured scale, not told what to become.
- Membership does not establish authorship, studio practice or influence; the feature space contains no names, credits or dates.
- This component does not establish that these works share a genre, a market, a mood, a budget, an intent or a quality level. It establishes that their measured timing/texture values sit near each other.

### `rapid-cut`

**n = 208** (8.4% of the 2,472 full-film records). Sites: aicp (58), directorslibrary (8), motiondesignawards (44), promonews (19), shots (79). Exemplar ranking: highest per-record silhouette, tie-break by id.

Measured signature

| feature | p10 | median | p90 | unit | measured on |
|---|---:|---:|---:|---|---:|
| `cutsPerMinute` | 33.482 | 52.955 | 77.133 | cuts/min | 208/208 |
| `medianShotSeconds` | 0.500 | 0.767 | 1.256 | s | 208/208 |
| `p10ShotSeconds` | 0.067 | 0.171 | 0.528 | s | 208/208 |
| `p90ShotSeconds` | 1.460 | 2.352 | 3.830 | s | 133/208 |
| `burstFraction` | 0.042 | 0.246 | 0.466 | fraction | 208/208 |
| `shotsUnderHalfSecondPct` | 8.182 | 25.676 | 49.520 | % | 133/208 |
| `paceDriftRatio` | 0.400 | 0.925 | 1.851 | ratio | 132/208 |
| `flickerLumaPerSecond` | 0.043 | 0.067 | 0.114 | luma/s | 133/208 |
| `durationSeconds` | 30.059 | 62.101 | 164.441 | s | 208/208 |
| `meanLuma` | 0.202 | 0.320 | 0.470 | 0-1 | 208/208 |
| `meanSaturation` | 0.127 | 0.306 | 0.471 | 0-1 | 208/208 |
| `integratedLufs` | -21.400 | -14.100 | -8.050 | LUFS | 176/208 |
| `onsetPerMinute` | 225.352 | 295.445 | 340.120 | onsets/min | 176/208 |

Exemplars

| site | record id | slug | title | duration (s) |
|---|---|---|---|---:|
| shots | `40915` | `freaknik-the-wildest-party-never-told-trailer` | Freaknik: The Wildest Party Never Told - Trailer | 116.0 |
| aicp | `858158` | `hacking-google` | Hacking Google | 111.7 |
| aicp | `863315` | `diamonds` | Diamonds | 49.9 |
| motiondesignawards | `2405` | `styleframe-showreel-2025` | Styleframe Showreel 2025 | 80.0 |
| shots | `41376` | `celebrate-being-human` | Celebrate Being Human | 60.1 |
| aicp | `1143293` | `goodyear` | Still. Always. Forever | 62.1 |

Reuse recipe

```text
target cuts at the component's measured rate
  15 s: 13 cuts   (1.15 s median interval)
  30 s: 26 cuts   (1.15 s median interval)
  60 s: 53 cuts   (1.13 s median interval)
  90 s: 79 cuts   (1.14 s median interval)

measured shot durations
  p10 0.50 s | median 0.77 s | p90 1.26 s

expected pace trajectory
  near-flat | last-third ÷ first-third drift 0.93 | first third 46.3 cuts/min (133 records) | last third 41.9 cuts/min (133 records)
  (each pace figure is a per-record median; they need not reconcile arithmetically)

measured loudness band (audio-measured subset)
  integrated -21.4 to -8.1 LUFS (median -14.1) | LRA median 6.0 LU | true peak median -0.6 dBFS

measured onset band
  225.4 to 340.1 onsets/min (median 295.4)

measured palette band
  mean luma 0.20-0.47 | mean saturation 0.13-0.47
  derived from 208 records (loudness from 176, onset from 176, palette from 208)
```

These are measured mid-points, not prescriptions. The arithmetic is `cuts = round(median cut rate × target seconds / 60)` over this component's 208 records; it says where the cluster sits, not what a new piece should do.

What this does not establish

- Membership does not establish authorship, studio practice or influence; the feature space contains no names, credits or dates.
- A record near a boundary could move to a neighbouring component at a different k or a different feature set; component edges are measurement cut-points, not natural kinds.
- The cluster does not establish that a cut here is an edit: candidates include flashes, fast motion, dissolves and compression artefacts.

### `accelerating-steady-cut`

**n = 65** (2.6% of the 2,472 full-film records). Sites: aicp (18), directorslibrary (12), motiondesignawards (9), promonews (15), shots (11). Exemplar ranking: highest per-record silhouette, tie-break by id.

Measured signature

| feature | p10 | median | p90 | unit | measured on |
|---|---:|---:|---:|---|---:|
| `cutsPerMinute` | 6.758 | 16.658 | 30.587 | cuts/min | 65/65 |
| `medianShotSeconds` | 0.816 | 1.685 | 3.294 | s | 65/65 |
| `p10ShotSeconds` | 0.130 | 0.446 | 1.320 | s | 65/65 |
| `p90ShotSeconds` | 4.229 | 6.982 | 20.495 | s | 65/65 |
| `burstFraction` | 0.000 | 0.058 | 0.369 | fraction | 65/65 |
| `shotsUnderHalfSecondPct` | 0.000 | 11.765 | 35.176 | % | 65/65 |
| `paceDriftRatio` | 2.667 | 4.000 | 9.000 | ratio | 65/65 |
| `flickerLumaPerSecond` | 0.005 | 0.015 | 0.034 | luma/s | 65/65 |
| `durationSeconds` | 45.069 | 138.773 | 260.149 | s | 65/65 |
| `meanLuma` | 0.116 | 0.217 | 0.460 | 0-1 | 65/65 |
| `meanSaturation` | 0.195 | 0.338 | 0.604 | 0-1 | 65/65 |
| `integratedLufs` | -20.020 | -12.600 | -7.940 | LUFS | 65/65 |
| `onsetPerMinute` | 204.389 | 280.967 | 315.671 | onsets/min | 65/65 |

Exemplars

| site | record id | slug | title | duration (s) |
|---|---|---|---|---:|
| aicp | `1028143` | `giants-make-us-tall` | Giants Make Us Tall | 227.9 |
| directorslibrary | `76867` | `youre-not-like-that-the-rapants` | ‘You’re Not Like That’ The Rapants | 321.0 |
| promonews | `96173` | `anotr-it-alice-kong` | ANOTR 'Like It' by Alice Kong | 268.5 |
| promonews | `96313` | `eliza-rose-undercover-lover-jade-ang-jackman` | Eliza Rose 'Undercover Lover' by Jade Ang Jackman | 237.8 |
| aicp | `1132185` | `kyiv` | Kyiv | 181.7 |
| promonews | `96830` | `chloe-qisha-he-likes-boys-bedroom` | Chloe Qisha 'He Likes Boys' by Bedroom | 214.5 |

Reuse recipe

```text
target cuts at the component's measured rate
  15 s: 4 cuts   (3.75 s median interval)
  30 s: 8 cuts   (3.75 s median interval)
  60 s: 17 cuts   (3.53 s median interval)
  90 s: 25 cuts   (3.60 s median interval)

measured shot durations
  p10 0.82 s | median 1.69 s | p90 3.29 s

expected pace trajectory
  accelerating | last-third ÷ first-third drift 4.00 | first third 5.6 cuts/min (65 records) | last third 25.2 cuts/min (65 records)
  (each pace figure is a per-record median; they need not reconcile arithmetically)

measured loudness band (audio-measured subset)
  integrated -20.0 to -7.9 LUFS (median -12.6) | LRA median 9.3 LU | true peak median -0.0 dBFS

measured onset band
  204.4 to 315.7 onsets/min (median 281.0)

measured palette band
  mean luma 0.12-0.46 | mean saturation 0.20-0.60
  derived from 65 records (loudness from 65, onset from 65, palette from 65)
```

These are measured mid-points, not prescriptions. The arithmetic is `cuts = round(median cut rate × target seconds / 60)` over this component's 65 records; it says where the cluster sits, not what a new piece should do.

What this does not establish

- A record near a boundary could move to a neighbouring component at a different k or a different feature set; component edges are measurement cut-points, not natural kinds.
- This component does not establish that these works share a genre, a market, a mood, a budget, an intent or a quality level. It establishes that their measured timing/texture values sit near each other.
- The profile does not establish a target or a recommendation. The recipe reports mid-points so a new piece can be placed on the same measured scale, not told what to become.

## Stills-only site (no clustering)

STASH publishes poster images, not measured video renditions. Its stills are reported here as a palette-only measurement and are never clustered with the video components.

### `stash` — 5,277 stills

| feature | p10 | median | p90 | measured on |
|---|---:|---:|---:|---:|
| mean display luma (0–1) | 0.209 | 0.466 | 0.746 | 5,277 |
| mean saturation (0–1) | 0.093 | 0.342 | 0.651 | 5,277 |
| display luma std-dev | 0.134 | 0.216 | 0.300 | 5,277 |
| edge-density proxy | 0.019 | 0.039 | 0.068 | 5,277 |

Dominant hue families: blue (678), cyan (186), green (207), magenta (282), neutral (1,656), orange (1,257).

- Stills are published poster images, not video frames: there is no cut, pacing, motion or audio measurement and no clustering.
- One published still per record describes the chosen frame, not the film's palette over time.

## Feature coverage

| feature | present | total | fraction | unit |
|---|---:|---:|---:|---|
| `cutsPerMinute` | 3,380 | 3,380 | 100.0% | cuts/min |
| `medianShotSeconds` | 3,285 | 3,380 | 97.2% | s |
| `p10ShotSeconds` | 2,433 | 3,380 | 72.0% | s |
| `p90ShotSeconds` | 1,570 | 3,380 | 46.4% | s |
| `burstFraction` | 3,149 | 3,380 | 93.2% | fraction |
| `shotsUnderHalfSecondPct` | 1,570 | 3,380 | 46.4% | % |
| `paceDriftRatio` | 1,380 | 3,380 | 40.8% | ratio |
| `paceTrendCode` | 1,380 | 3,380 | 40.8% | code |
| `paceFirstThirdCutsPerMinute` | 1,570 | 3,380 | 46.4% | cuts/min |
| `paceLastThirdCutsPerMinute` | 1,570 | 3,380 | 46.4% | cuts/min |
| `flickerLumaPerSecond` | 1,570 | 3,380 | 46.4% | luma/s |
| `staticFraction` | 1,570 | 3,380 | 46.4% | fraction |
| `meanLuma` | 3,380 | 3,380 | 100.0% | 0-1 |
| `meanSaturation` | 3,380 | 3,380 | 100.0% | 0-1 |
| `durationSeconds` | 3,380 | 3,380 | 100.0% | s |
| `integratedLufs` | 2,812 | 3,380 | 83.2% | LUFS |
| `loudnessRangeLu` | 2,812 | 3,380 | 83.2% | LU |
| `truePeakDbfs` | 2,808 | 3,380 | 83.1% | dBFS |
| `silenceFraction` | 2,812 | 3,380 | 83.2% | fraction |
| `onsetPerMinute` | 2,812 | 3,380 | 83.2% | onsets/min |
| `onsetTrendCode` | 2,812 | 3,380 | 83.2% | code |
| `tempoHypothesisBpm` | 690 | 3,380 | 20.4% | BPM |

## Provenance

Generated by `scripts/derive_artistic_components.py` from `research/analysis`. Schema `kumiki.artistic-components.v1`. The JSON companion is `research/analysis/artistic-components.json`; per-site record-to-component maps are `research/analysis/<site>/components.json`.
