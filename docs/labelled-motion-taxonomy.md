# Labelled motion-component taxonomy

This file describes a **versioned, machine-applied taxonomy** — measured predicates, not a creative archetype. A label such as `rapid-montage` is shorthand for a test over named stored fields with fixed thresholds; it is not a claim that a work is fast, exciting, well edited or intended to feel a certain way. Every label in `catalog/taxonomy/motion-components.v1.json` carries its definition, positive predicate, exclusions, required fields, evidence tier, confidence rule, corpus exemplars, a reuse note and explicit non-claims.

The taxonomy is deliberately partial. Layer A (pacing), layer B (sampled appearance), layer C (audio energy) and layer E (strict composites) are computable from what is already on disk. Layer D (transition and global motion) is fully specified against the real `motionProfile.*` vocabulary but **cannot be assigned today**, because no stored census record contains that block. Layer F names what the taxonomy refuses to claim. No media was re-scanned, downloaded or decoded to produce this version.

**Known limits, stated before any number:**

- Cut candidates are ffmpeg scene-score exceedances, not verified edits. Fast motion, flashes, strobe, dissolves and compression can create candidates.
- Layer B and the appearance component of layer E come from the stored 1 Hz appearance series. They are sampled proxies; the series aliases content above roughly 1 Hz.
- The editorial block exists on 1,570 of 3,161 records (49.7%). Layer B and most of layer E are therefore unavailable for about half the corpus.
- Audio joins exist for 2,841 of 3,161 records (89.9%). 320 records have no audio evidence and receive no layer-C label.
- Four audio records sit at or below the −70 LUFS absolute gate. They are reported as `integrated-at-or-below-gate`, never as a measured quiet level.
- Identity is `strict-sha` for 374 records, `duration+resolution+codec` for 1,188 and absent for 1,599. High confidence is deliberately rare.
- There is no human review, transition ground truth, effect recognition, camera inference, genre, quality or intent evidence anywhere in the inputs. The taxonomy does not rank, score or judge the works.

## Corpus this version was applied to

The run is deterministic and offline over `research/analysis/**`.

| quantity | value |
|---|---:|
| census records | 3,161 |
| sites with census records | 5 |
| records with an `editorial` block | 1,570 |
| records with a joined audio record | 2,841 |
| records with a joined video record | 3,161 |
| records with a joined catalog entry | 3,161 |
| records with no audio record | 320 |
| audio records at or below the −70 LUFS gate | 4 |
| records with a `motionProfile` block | 0 |
| records with at least one assigned label | 3,054 (96.6%) |
| assigned label instances | 10,143 |
| of which high confidence | 318 |
| of which medium confidence | 3,301 |
| of which low confidence | 6,524 |

Site totals: aicp 703 records (658 with a label), directorslibrary 354 (352), motiondesignawards 491 (477), promonews 808 (808), shots 805 (759).

## Versioning and application

- Taxonomy schema: `kumiki.motion-component-taxonomy.v1`, version `1`.
- Apply with `PYTHONPATH=src python scripts/label_taxonomy.py --root research/analysis`. The command writes `<site>/taxonomy-labels.json` for each site plus `research/analysis/taxonomy-assignments.{json,md}`.
- The applier is stdlib-only, joins census to audio/video/catalog by the existing id keys (`id`, `clipId`, `projectId`, `nid`, `postId`) with a slug fallback, and never writes into `videos/`, `census/`, `audio/`, `stills/` or `dataset/`.
- Writes are atomic and skip a file whose bytes are unchanged, so repeated runs are byte-idempotent. Output is sorted; the only timestamp is `derivedFrom.latestInputMtime`, taken from the newest input mtime.
- Change a threshold, a predicate, a definition or the label set only by publishing a new taxonomy version. Assignments name the taxonomy version they used; the applier rejects an unknown schema rather than guessing.

## Fixed threshold register

These are design parameters, not measurements. Each predicate references one of these names; no predicate embeds a second copy of the number.

| threshold | value | used for |
|---|---:|---|
| `noCutCount` | 0 | zero-candidate boundary |
| `rapidCutsPerMinute` | 40.0 | rapid-montage floor |
| `steadyCutMinCutsPerMinute` | 8.0 | steady-cut lower bound |
| `longTakeMaxCutsPerMinute` | 8.0 | long-take ceiling |
| `minimumCutsForPacingLabel` | 20 | eligibility floor for rate and trend labels |
| `minimumCutsForMotionLabel` | 20 | eligibility floor for layer-D transition labels |
| `highConfidenceCutCount` | 60 | high-confidence rule |
| `lowConfidenceCutCount` | 20 | low-confidence rule |
| `highConfidenceDurationSeconds` | 30.0 | single-shot high-confidence rule |
| `lowConfidenceDurationSeconds` | 10.0 | minimum duration for single-shot |
| `minimumEditorialSeriesSamples` | 30 | minimum appearance samples |
| `highConfidenceSeriesSamples` | 100 | appearance high-confidence rule |
| `lowConfidenceSeriesSamples` | 40 | appearance low-confidence rule |
| `minimumAudioDurationSeconds` | 10.0 | minimum audio duration |
| `highConfidenceAudioDurationSeconds` | 60.0 | audio high-confidence rule |
| `lowConfidenceAudioDurationSeconds` | 30.0 | audio low-confidence rule |
| `acceleratingDriftRatioAtLeast` | 1.15 | accelerating drift floor |
| `deceleratingDriftRatioAtMost` | 0.85 | decelerating drift ceiling |
| `frontLoadDriftRatioAtMost` | 0.75 | front-loaded drift ceiling |
| `frontLoadEarlyCutsPerMinuteAtLeast` | 30.0 | front-loaded early-rate floor |
| `burstFractionAtLeast` | 0.5 | burst-texture floor |
| `flickerHighAtLeast` | 0.05 | flicker-high floor |
| `flickerLowAtMost` | 0.01 | flicker-low ceiling |
| `staticFrameHighAtLeast` | 0.5 | static-frame-dominant floor |
| `lumaDriftSlopeAtLeast` | 0.05 | luma drift magnitude |
| `lumaDriftR2AtLeast` | 0.25 | luma drift fit floor |
| `audioGateLufs` | −70.0 | absolute loudness gate |
| `loudMixAtLeastLufs` | −14.0 | loud band floor |
| `quietMixAtMostLufs` | −20.0 | quiet band ceiling |
| `wideLraAtLeastLu` | 12.0 | wide LRA floor |
| `narrowLraAtMostLu` | 4.0 | narrow LRA ceiling |
| `onsetDenseAtLeastPerMinute` | 320.0 | dense onset floor |
| `onsetSparseAtMostPerMinute` | 200.0 | sparse onset ceiling |
| `silentTailAtLeastSeconds` | 1.5 | silent-tail floor |
| `loudnessSlopeAtLeastLuPerMinute` | 2.0 | loudness drift magnitude |
| `loudnessSlopeR2AtLeast` | 0.3 | loudness drift fit floor |
| `hardCutShareAtLeast` | 0.6 | hard-cut-dominant floor |
| `dissolveShareAtLeast` | 0.2 | dissolve-using floor |
| `fadeShareAtLeast` | 0.1 | fade-using floor |
| `panFractionAtLeast` | 0.5 | pan-dominant floor |
| `staticCameraFractionAtLeast` | 0.6 | static-camera floor |
| `centreShareAtLeast` | 0.2 | centre-weighted-motion floor |
| `overlayActivityAtLeast` | 0.3 | overlay-active floor |
| `minimumMotionPairs` | 10 | layer-D eligibility floor |

## Layer A — pacing and timing

Fields live under `census.*` and `editorial.*`. The three rate bands are mutually exclusive by construction; trend labels (`accelerating`, `decelerating`) and texture labels (`strobe-texture`, `burst-texture`) are orthogonal to the bands. Every rate label requires present cut fields, and every trend label additionally requires the editorial block. `a.strobe-texture` is the one sampled label in this layer: the stored strobe flag is derived from the 1 Hz appearance series, while the cut-rate and burst labels use the full-runtime cut scan.

| label | predicate (thresholds by name) | tier | assigned | share |
|---|---|---|---:|---:|
| `a.single-shot` | `census.cutCount <= noCutCount`, duration >= 10 s | measured-full-runtime | 94 | 3.0% |
| `a.long-take` | `census.cutsPerMinute < longTakeMaxCutsPerMinute`; exclusion `cutCount <= noCutCount` | measured-full-runtime | 430 | 13.6% |
| `a.steady-cut` | `steadyCutMinCutsPerMinute <= cutsPerMinute < rapidCutsPerMinute`; `cutCount >= 20` | measured-full-runtime | 1,565 | 49.5% |
| `a.rapid-montage` | `cutsPerMinute >= rapidCutsPerMinute`; `cutCount >= 20` | measured-full-runtime | 521 | 16.5% |
| `a.accelerating` | `paceTrend == accelerating` and `paceDriftRatio >= 1.15`; cuts >= 20 and series >= 30 | measured-full-runtime | 355 | 11.2% |
| `a.decelerating` | `paceTrend == decelerating` and `paceDriftRatio <= 0.85`; cuts >= 20 and series >= 30 | measured-full-runtime | 372 | 11.8% |
| `a.strobe-texture` | `census.strobe == true` | measured-sampled | 345 | 10.9% |
| `a.burst-texture` | `census.burstFraction >= 0.5`; cuts >= 20 | measured-full-runtime | 299 | 9.5% |

Definitions and non-claims:

- `a.single-shot` — no scene-score exceedance in the full-runtime scan. Does not prove one shot, camera stillness or an unbroken take.
- `a.long-take` — detected event rate below 8 cuts/min with at least one candidate. Does not establish a verified take length or camera behaviour.
- `a.steady-cut` — middle rate band. Does not describe rhythm, beat alignment or editorial philosophy.
- `a.rapid-montage` — rate at or above 40 cuts/min. Fast motion and strobe can inflate the candidate count; it is not proof of rapid editing.
- `a.accelerating` / `a.decelerating` — direction of the first-to-last third rate ratio. Sensitive to where candidates fall; not a smooth ramp or a musical build.
- `a.strobe-texture` — the stored sampled-luma instability flag. It is a photic-texture caution, not an edit, not a flash-rate measurement and not a safety verdict.
- `a.burst-texture` — at least half the detected gaps are short. Does not establish a montage, chase, stinger or narrative function.

The most common layer-A jointly assigned pairs are `strobe-texture` + `burst-texture` (286 records), `steady-cut` + `decelerating` (271), `steady-cut` + `accelerating` (262), `rapid-montage` + `burst-texture` (206) and `rapid-montage` + `strobe-texture` (196). The full matrix is in `taxonomy-assignments.json`.

## Layer B — temporal appearance

All fields come from the top-level `editorial` block, which is a function of the stored 1 Hz `series`. Present on 1,570 records; 1,385 of those meet the 30-sample floor.

| label | predicate | tier | assigned | share |
|---|---|---|---:|---:|
| `b.flicker-high` | `flickerLumaPerSecond >= 0.05` | measured-sampled | 165 | 5.2% |
| `b.flicker-low` | `flickerLumaPerSecond <= 0.01` | measured-sampled | 334 | 10.6% |
| `b.static-frame-dominant` | `staticFraction >= 0.5` | measured-sampled | 287 | 9.1% |
| `b.luma-rise` | `lumaSlopePerMinute >= 0.05` and `lumaSlopeR2 >= 0.25` | measured-sampled | 80 | 2.5% |
| `b.luma-fall` | `lumaSlopePerMinute <= −0.05` and `lumaSlopeR2 >= 0.25` | measured-sampled | 102 | 3.2% |

Non-claims: these are sampled-appearance proxies. `flicker-*` is not a flicker frequency; the 1 Hz series aliases content above roughly 1 Hz. `static-frame-dominant` is not a static camera or a freeze. Luma drift labels are fitted slopes with a fit-quality gate; they do not establish a reveal, fade, tonal arc or intent.

## Layer C — audio energy

Assigned only where `audio/*.json` is joined (2,841 records; 2,837 also carry the slope/R² fields).

| label | predicate | tier | assigned | share |
|---|---|---|---:|---:|
| `c.loud-mix` | `integratedLufs >= −14` and above the gate | measured-full-runtime | 1,453 | 46.0% |
| `c.quiet-mix` | `integratedLufs <= −20` and above the gate | measured-full-runtime | 370 | 11.7% |
| `c.wide-lra` | `loudnessRangeLu >= 12` | measured-full-runtime | 502 | 15.9% |
| `c.narrow-lra` | `loudnessRangeLu <= 4` | measured-full-runtime | 524 | 16.6% |
| `c.onset-dense` | `onsetsPerMinuteOfRuntime >= 320` | measured-full-runtime | 566 | 17.9% |
| `c.onset-sparse` | `onsetsPerMinuteOfRuntime <= 200` | measured-full-runtime | 291 | 9.2% |
| `c.silent-tail` | `tailSilenceSeconds >= 1.5` | measured-full-runtime | 1,017 | 32.2% |
| `c.loudness-rise` | `loudnessSlopeLuPerMinute >= 2` and `loudnessSlopeR2 >= 0.3` | measured-full-runtime | 50 | 1.6% |
| `c.loudness-fall` | `loudnessSlopeLuPerMinute <= −2` and `loudnessSlopeR2 >= 0.3` | measured-full-runtime | 102 | 3.2% |

**Gate handling.** `c.loud-mix`, `c.quiet-mix`, `c.loudness-rise` and `c.loudness-fall` check `audio.integratedLufs <= audioGateLufs` before their predicate. A record at or below −70 LUFS is refused with `integrated-at-or-below-gate` and is **not** reported as quiet, flat or decaying. Four corpus records take this path; the doc never calls the gate value a measurement.

**Gate-adjacent counts.** `c.loud-mix` and `c.quiet-mix` each have 1,367 and 2,450 predicate-false records respectively. `c.loud-mix` + `c.silent-tail` co-occur on 640 records; `c.loud-mix` + `c.narrow-lra` on 268; `c.loud-mix` + `c.wide-lra` on 225. Full matrix in the JSON summary.

Non-claims: a loud or quiet integrated level is not a quality, compliance or dynamics judgement. LRA is a statistical spread, not a style. Onsets are amplitude-envelope rises, not beats, cuts or speech events. Tail silence can be an encode or rendition artefact. Loudness slopes are fitted trends with a fit gate, not builds or releases.

## Layer D — transition and global motion (specified, unmeasured)

**None of these labels can be assigned today.** The corpus scan ran before `acquisition/motion_profile.py` existed, and 0 of the 3,161 census records carry a `motionProfile` block. The applier reports `missing-motion-profile` for every layer-D label. Exemplar lists are empty because no real exemplar can be computed.

The predicates use the vocabulary and field names in `acquisition/motion_profile.py`:

| label | predicate over future `motionProfile.*` | required fields |
|---|---|---|
| `d.hard-cut-dominant` | `transitions.shares.hard-cut >= 0.6` | `transitions.shares.hard-cut`, `transitions.transitionCount` |
| `d.dissolve-using` | `shares.short-dissolve + shares.long-dissolve >= 0.2` | both shares, `transitions.transitionCount` |
| `d.fade-using` | `shares.fade-through-black + shares.fade-through-white >= 0.1` | both shares, `transitions.transitionCount` |
| `d.pan-dominant` | `globalMotion.panFraction >= 0.5` | `globalMotion.panFraction`, `globalMotion.observablePairs` |
| `d.static-camera` | `globalMotion.staticFraction >= 0.6` | `globalMotion.staticFraction`, `globalMotion.observablePairs` |
| `d.centre-weighted-motion` | `localMotion.centreShare >= 0.2` | `localMotion.centreShare` |
| `d.overlay-active` | `max(upperThirdActivity, lowerThirdActivity) >= 0.3` | both `overlayActivity.*` fields |

What would be needed: a new pass that runs `motion_signature` / `classify_transitions` over decoded frames and writes the resulting `motionProfile` block into each record, then re-running the applier. That is a media re-scan and is **out of scope for this task**. Even with the block, these labels would remain fixed-vocabulary proxies: `hard-cut`/dissolve/fade are window-based classes, `panFraction` is an image-plane translation hypothesis, `centreShare` is a 3×3 change distribution and `overlayActivity` is a high-frequency luma volatility proxy. None is transition ground truth, camera inference, effect identity or text/logo detection.

## Layer E — editorial-behaviour composites

A composite is assigned only when every component is measured. Missing audio or missing editorial means the composite is refused, even when the remaining components point toward it.

| label | predicate | required components | assigned | share |
|---|---|---|---:|---:|
| `e.front-loaded` | `paceTrend == decelerating`, `paceDriftRatio <= 0.75`, `paceFirstThird >= 30` | editorial pace block, cuts >= 20 | 169 | 5.3% |
| `e.building` | `paceTrend == accelerating` and (`lumaSlopePerMinute >= 0.05` with `lumaSlopeR2 >= 0.25`, or `loudnessSlopeLuPerMinute >= 2` with `loudnessSlopeR2 >= 0.3`) | editorial pace + luma slope/R², audio slope/R², integrated loudness above gate, cuts >= 20, audio >= 10 s | 28 | 0.9% |
| `e.flat-steady` | `paceTrend == steady`, `abs(lumaSlopePerMinute) <= 0.05`, `lumaSlopeR2 <= 0.25` | editorial pace + luma slope/R², cuts >= 20 | 122 | 3.9% |

Layer E is the weakest tier: `e.front-loaded` is full-runtime pace arithmetic, while `e.building` and `e.flat-steady` inherit the 1 Hz sampling of the appearance component. Non-claims: front-loaded is not a hook or trailer structure; building is not a crescendo or rising action; flat-steady is not calm, neutral or monotonous.

`e.building` is refused on 4 records that have editorial and luma fields but no audio record, on 1,781 with no editorial block, on 461 with fewer than 20 detected cuts, on 886 whose measured components do not reach the predicate, and on 1 audio record shorter than 10 s. These refusals are the intended behaviour, not a ranking of the works.

## Layer F — explicitly out of scope

These names exist so that no consumer mistakes an adjacent numeric label for a claim the evidence cannot support. They are non-assignable by construction and have zero assignments.

| label | why it is out of scope | evidence that would be required |
|---|---|---|
| `f.animation-style` | no stored field measures technique or medium | labelled frames or a validated classifier with error rates |
| `f.vfx-effect-identity` | no stored field measures effect identity | an effect-labelled dataset and a detector with a confusion matrix |
| `f.transition-ground-truth` | candidates and transition windows are proxies | frame-accurate human annotation with inter-annotator agreement |
| `f.video-template-detection` | no stored field measures package or template membership | a template library and a matcher with a measured false-positive rate |
| `f.camera-rig-inference` | no stored field measures camera or rig identity | EXIF/rig metadata or a calibrated camera-motion model |
| `f.genre` | no stored field measures genre | a labelled genre corpus or catalog categories used as a separate field |
| `f.quality` | no stored field measures quality | a defined rubric, trained raters and inter-rater reliability |
| `f.intent` | no stored field measures intent | briefs, interviews or a labelled intent study |
| `f.authorship` | no stored field measures authorship | provenance metadata or a validated attribution method |

## Evidence availability

`all layer fields` means every path required by any label in that layer is present. `any label requires` means at least one label's requirements are present. The difference is the cost of conjunctions: layer A's strict union includes the editorial pace fields, while its rate bands need only the census.

| layer | labels | all layer fields | any label requires | records with a label |
|---|---:|---:|---:|---:|
| A-pacing | 8 | 1,363 | 3,161 | 2,653 |
| B-temporal-appearance | 5 | 1,570 | 1,570 | 619 |
| C-audio-energy | 9 | 2,837 | 2,841 | 2,562 |
| D-transition-motion | 7 | 0 | 0 | 0 |
| E-editorial-composites | 3 | 1,376 | 1,380 | 319 |
| F-out-of-scope | 9 | 0 | 0 | 0 |

Layer A's `all fields` figure (1,363) is lower than its `any requires` figure (3,161) because 1,781 records have no editorial block, 190 of the 1,570 that do have a null `paceTrend` (no cuts in the first third), and a further 17 lack a `burstFraction` value. The rate bands still apply to those records; the trend labels do not.

## Per-site label counts

Counts are records, not label instances. A record may carry several labels.

| label | aicp | directorslibrary | motiondesignawards | promonews | shots | total |
|---|---:|---:|---:|---:|---:|---:|
| `a.accelerating` | 91 | 60 | 57 | 83 | 64 | 355 |
| `a.burst-texture` | 43 | 10 | 79 | 103 | 64 | 299 |
| `a.decelerating` | 85 | 37 | 85 | 65 | 100 | 372 |
| `a.long-take` | 65 | 28 | 112 | 127 | 98 | 430 |
| `a.rapid-montage` | 110 | 28 | 74 | 145 | 164 | 521 |
| `a.single-shot` | 13 | 3 | 43 | 4 | 31 | 94 |
| `a.steady-cut` | 411 | 272 | 96 | 530 | 256 | 1,565 |
| `a.strobe-texture` | 46 | 12 | 104 | 107 | 76 | 345 |
| `b.flicker-high` | 30 | 10 | 69 | 13 | 43 | 165 |
| `b.flicker-low` | 80 | 40 | 83 | 44 | 87 | 334 |
| `b.luma-fall` | 14 | 9 | 32 | 9 | 38 | 102 |
| `b.luma-rise` | 17 | 0 | 23 | 5 | 35 | 80 |
| `b.static-frame-dominant` | 71 | 36 | 67 | 35 | 78 | 287 |
| `c.loud-mix` | 143 | 137 | 248 | 689 | 236 | 1,453 |
| `c.loudness-fall` | 4 | 13 | 38 | 9 | 38 | 102 |
| `c.loudness-rise` | 16 | 2 | 7 | 4 | 21 | 50 |
| `c.narrow-lra` | 67 | 15 | 137 | 120 | 185 | 524 |
| `c.onset-dense` | 134 | 41 | 121 | 59 | 211 | 566 |
| `c.onset-sparse` | 33 | 29 | 66 | 113 | 50 | 291 |
| `c.quiet-mix` | 96 | 67 | 55 | 10 | 142 | 370 |
| `c.silent-tail` | 112 | 181 | 166 | 467 | 91 | 1,017 |
| `c.wide-lra` | 103 | 99 | 66 | 115 | 119 | 502 |
| `e.building` | 12 | 1 | 3 | 3 | 9 | 28 |
| `e.flat-steady` | 36 | 19 | 9 | 35 | 23 | 122 |
| `e.front-loaded` | 33 | 7 | 51 | 21 | 57 | 169 |

The distribution is not uniform across sites: promonews carries 47.4% of all `c.loud-mix` assignments and 45.9% of `c.silent-tail`. aicp (703 records) and directorslibrary (354 records) contribute fewer label instances in most rows. These are properties of which records were scanned at all, not of the sites' output.

## Which labels are computable, and which are not

Computable today, with at least one assigned record:

`a.single-shot`, `a.long-take`, `a.steady-cut`, `a.rapid-montage`, `a.accelerating`, `a.decelerating`, `a.strobe-texture`, `a.burst-texture`, all five layer-B labels, all nine layer-C labels, and all three layer-E labels. That is 25 of 41 labels.

Specified but unassignable today: all seven layer-D labels, because `motionProfile.*` is absent. Permanently out of scope for this taxonomy: all nine layer-F names. Those 16 labels are reported with `assigned: 0` in `taxonomy-assignments.json`.

No label in this taxonomy is a quality, genre, intent, authorship, effect-identity, template, camera or transition-ground-truth claim.

## Files

- `catalog/taxonomy/motion-components.v1.json` — the taxonomy: schema, thresholds, labels, predicates, non-claims and exemplars.
- `scripts/label_taxonomy.py` — the stdlib-only applier.
- `tests/test_labelled_taxonomy.py` — offline contract tests.
- `research/analysis/<site>/taxonomy-labels.json` — per-record assignments, confidence and layer status.
- `research/analysis/taxonomy-assignments.json` — corpus summary: label counts and shares, co-occurrence matrices, per-site breakdown, evidence availability, unmeasured labels and unassigned-reason counts.
- `research/analysis/taxonomy-assignments.md` — the same summary as tables.

## Reproduce

```bash
PYTHONPATH=src python -m unittest tests.test_labelled_taxonomy -q
PYTHONPATH=src python scripts/label_taxonomy.py --root research/analysis
```

No network, no downloads, no media re-scan. The run reads JSON already under `research/analysis/**` and the taxonomy file, and writes only the declared outputs.
