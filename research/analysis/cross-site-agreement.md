# Cross-site agreement of measured work

Read-only, standard-library analysis of `research/analysis`. The only timestamp is the maximum input record mtime (`2026-11-17T00:45:45.229504Z`); no value derives from `now()`.

The question is whether a measurement describes **the work** or **the delivery**. Each work measured on two sites is one pair: the same campaign reached us through two platforms, renditions and encodes, so agreement bounds how much of the number is intrinsic to the film and how much is the host's encode, scaling or normalisation.

## Coverage

- Sites with measurement lanes: aicp, directorslibrary, motiondesignawards, promonews, shots.
- Works on two or more sites: **248**.
- … with at least one measured record: **98**.
- … measured on two or more sites: **0**.
- Measured records inside cross-site works: 103 (of which 5 works carry two measured members on the *same* site, not a cross-site pair).

| site combination | works | with any measurement | measurable pairs |
|---|---:|---:|---:|
| aicp+shots | 225 | 93 | 0 |
| directorslibrary+shots | 4 | 1 | 0 |
| motiondesignawards+shots | 3 | 3 | 0 |
| promonews+shots | 16 | 1 | 0 |

**This snapshot cannot answer the cross-site question.** The quality-selection tree lists 248 works that appear on two or more sites (219 of them with at least one selected row), but the census and audio cohorts are per-site samples that do not overlap on any of those works: 98 have one side measured, none have two. `quality-selection.md`'s 219 counts *selected rows*, not measured works, so it is not a pair count. Every statistic below is empty because the inputs are absent, not because agreement was perfect.

## Pair counts

- pairs: **0** across 0 works
- duration mismatch (>10%): **0**
- cut-rate divergence (>50%): **0**
- partial (lane sets differ): **0**

Duration-delta distribution: no pair has two runtimes to compare.

## Statistics — all usable pairs

| metric | n pairs | works | signed mean (A−B) | absolute mean | relative mean | Spearman | ICC |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cutsPerMinute` | 0 | 0 | — | — | — | — | — |
| `medianShotSeconds` | 0 | 0 | — | — | — | — | — |
| `meanLuma` | 0 | 0 | — | — | — | — | — |
| `meanSaturation` | 0 | 0 | — | — | — | — | — |
| `integratedLufs` | 0 | 0 | — | — | — | — | — |
| `lra` | 0 | 0 | — | — | — | — | — |
| `onsetRate` | 0 | 0 | — | — | — | — | — |

`cutsPerMinute` excludes every pair where either side is strobe-flagged; a strobe is never pooled with a non-strobe. Relative columns are blank for LUFS and LRA because a dB value has no meaningful zero for a ratio.

## Statistics — duration-matched pairs only

| metric | n pairs | works | signed mean (A−B) | absolute mean | relative mean | Spearman | ICC |
|---|---:|---:|---:|---:|---:|---:|---:|
| `cutsPerMinute` | 0 | 0 | — | — | — | — | — |
| `medianShotSeconds` | 0 | 0 | — | — | — | — | — |
| `meanLuma` | 0 | 0 | — | — | — | — | — |
| `meanSaturation` | 0 | 0 | — | — | — | — | — |
| `integratedLufs` | 0 | 0 | — | — | — | — | — |
| `lra` | 0 | 0 | — | — | — | — | — |
| `onsetRate` | 0 | 0 | — | — | — | — | — |

## Variance decomposition

ICC is the one-way ANOVA form `(MSB − MSW) / (MSB + (k̄ − 1)·MSW)` over works with at least two values: near 1 means between-work differences dominate, near 0 means the two deliveries disagree as much as two different works do.

| metric | ICC | works | values | k̄ | MSB | MSW |
|---|---:|---:|---:|---:|---:|---:|
| `cutsPerMinute` | — | — | — | — | — | — |
| `medianShotSeconds` | — | — | — | — | — | — |
| `meanLuma` | — | — | — | — | — | — |
| `meanSaturation` | — | — | — | — | — | — |
| `integratedLufs` | — | — | — | — | — | — |
| `lra` | — | — | — | — | — | — |
| `onsetRate` | — | — | — | — | — | — |

Sparse or undefined: `cutsPerMinute`, `medianShotSeconds`, `meanLuma`, `meanSaturation`, `integratedLufs`, `lra`, `onsetRate`. Where `n` is 0 there is no number to read; where it is 1–2 the arithmetic is shown only so the absence is visible, not as a finding.

## Biggest disagreements

None: no work in this tree has a metric measured on two sites, so there is no disagreement to rank. This is a coverage fact, not a null result.

## Interpretation

**What a high ICC would license.** A metric with a high ICC on duration-matched, non-strobe pairs tracks the work rather than the delivery: two independent platforms agree on its ordering, so it can be compared across works that were measured on different sites, and a difference between two works is unlikely to be an encode artefact.

**What it would not license.** It is not proof that the two numbers are the same measurement. Duration mismatch (a 30 s cut against a 60 s cut), truncation or an alternate edit, host loudness normalisation (YouTube and Vimeo both apply it, so LUFS agreement describes the delivered stream and not the master), and different cuts of one campaign all survive a high ICC. Nor does it validate the metric itself: a shared bias in the cut-detector or the display-RGB proxy would raise agreement without making either number true.

**What this run licenses.** Nothing about agreement yet. The pairs that exist are too few to separate work variance from delivery variance; the run's value is the exact statement of that gap and the machinery to fill it once the same cross-site ids are measured in both lanes.

## Limitations

1. Duration mismatch: the same campaign is often published as a 30 s cut and a 60 s cut. A pair whose runtimes differ by more than 10% of the longer one is marked durationMismatch and reported both inside and outside the durationMatched statistics; it is a different edit, not a delivery artefact.
2. Different cuts of the same work: when the duration matches but cuts per minute differ by more than 50%, the pair is a retimed or alternate edit. It is flagged cutRateDivergence and cut out of the cutRateConsistent statistics rather than counted as measurement error.
3. Host loudness normalisation: YouTube and Vimeo normalise playback loudness. LUFS/LRA agreement therefore validates the delivered stream, not the master; a mastering difference can be flattened or invented by the host.
4. Partial lanes: a work with census on one site and only audio on the other is a partial pair. It is counted and paired only on the lane both sides share; it is never averaged into a metric one side lacks.
5. Zero-valued metrics: a relative difference is defined as (A - B) / max(|A|, |B|). When both values are zero the denominator is zero, so the relative difference is null and counted under relativeZeroDenominators rather than coerced to zero or to infinity.
6. Census cut candidates are ffmpeg scene-score exceedances, not verified edits; fast motion, flashes, transitions and compression can cross the threshold. Strobe-flagged records are never pooled with non-strobe records for cutsPerMinute.
7. Luma and saturation are display-RGB proxies at the decoded rendition size, not scene-linear light or calibrated colour; different resolutions and codecs shift them independently of the work.
8. Coverage gap in this snapshot: 248 works appear on two or more sites, but 0 have numeric census or audio evidence on two of them. The figure of 219 describes works with a *selected row* on more than one site, not works that were measured twice. The pair statistics above are therefore empty, and the honest reading is that this corpus cannot yet answer the cross-site question.

