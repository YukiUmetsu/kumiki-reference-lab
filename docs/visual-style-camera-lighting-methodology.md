# Visual styles, camera work, lighting and movement frequency

**New:** [Timecoded visual-style reviews](timecoded-visual-style-review.md) can record reviewer-observed media, paper-cut/collage/stop-motion/3D treatments, lighting looks and shot scales over exact source PTS intervals. This is an annotation/reporting capability, not evidence that the popular reference videos were watched or styled automatically.

This extends the [audience benchmark](audience-benchmark-methodology.md) with **a separate creative vocabulary**. An often-watched video is not automatically a good example of a style, and an artist's case study is not proof that a technique causes views. Do not join these sources statistically until the *same video ID* has both source-attributed audience evidence and reviewed visual observations. The [first actual licensed-file calibration](open-footage-calibration.md) demonstrates why introductory titles can bias a short visual sample.

## 1. Source-attributed style catalog

`research/visual-styles.v1.json` contains **12 studio-documented exemplars in six families**. Each item includes a source page, the studio's described production approach, editorial visual signals, and three review questions: camera, lighting and cadence. `sourceClaim` is a short paraphrase of studio material; the style signals/questions are **our prompts for future frame review**. The catalog is not yet a frame-coded or audience-measured style dataset.

| Family | Exemplars | What it teaches |
| --- | --- | --- |
| Paper and collage | [BUCK's Riot Games Lunar New Year](https://buck.co/work/riot-games-lunar-new-year); [We the People: Stronger](https://buck.co/work/we-the-people-stronger) | Layered cutouts vs. 3D geometry with a paper-cut finish |
| Hand-drawn | [Giant Ant's TVFCU campaign](https://www.giantant.ca/tvfcu-sharing-the-magic) | Traditional drawn animation is distinct from physical-paper animation |
| Physical animation | [Aardman's stop-motion production](https://www.aardman.com/latest-news/2025/june/behind-the-craft-wallace-gromit-shot-on-iphone/); [BUCK's wood-carved frames](https://buck.co/work/buck-holiday-gift) | Material tactility, handmade timing and frame artifacts |
| Stylized 3D | [Sony Imageworks' Spider-Verse](https://www.imageworks.com/our-craft/feature-animation/movies/spider-man-spider-verse); [Fortiche's Arcane](https://forticheprod.com/blog/arcane-by-fortiche/); [Giant Ant's Duolingo spots](https://www.giantant.ca/duolingo-misunderstood) | Halftone/shading systems, painterly 2D/3D and low-frame character motion |
| Print and collage | [BUCK Instagram Pride](https://buck.co/work/instagram-pride); [Identity Digital](https://buck.co/work/identity-digital-dot-new-domain); [Facebook IWD](https://buck.co/work/facebook-iwd) | Faux stop-motion, print texture with 2.5D camera, photo/cel/type mixes |
| Abstract motion | [Ordinary Folk TED intro](https://www.ordinaryfolk.co/project/ted-intro-animation) | Compressed shape-led branded storytelling |

```bash
PYTHONPATH=src python -m kumiki_reference_lab visual-styles validate
PYTHONPATH=src python -m kumiki_reference_lab visual-styles list --family paper-and-collage
PYTHONPATH=src python -m kumiki_reference_lab visual-styles search "2.5D camera"
```

Only metadata and source URLs are stored, not the third-party film, frames, audio, textures, or reusable design assets. Each film remains **inspiration only** without a separately confirmed license. Studio examples here **do not currently have view-count evidence**; do not imply otherwise.

## 2. Measured visual cadence from authorized local footage

Run both existing frame analyzers against **the same local video** and comparable scan bounds. Their sample PTS can differ; the cadence report computes each independently.

```bash
PYTHONPATH=src python -m kumiki_reference_lab motion ./licensed-film.mp4 \
  --max-seconds 10 --max-samples 48 --out ./runs/motion
PYTHONPATH=src python -m kumiki_reference_lab appearance ./licensed-film.mp4 \
  --max-seconds 10 --max-samples 24 --out ./runs/appearance
PYTHONPATH=src python -m kumiki_reference_lab visual-cadence \
  ./runs/motion/image-motion.json ./runs/appearance/appearance.json
```

Check the artifact filenames produced by your installed version if they differ. `visual-cadence` never downloads media. It validates same source SHA-256 and video stream, original source timebase, monotonic sample PTS, cut boundaries, valid speeds, and finite thresholds. It rejects contradictory input instead of inventing a continuous motion path.

| Report field | What is measured | What it **cannot** establish |
| --- | --- | --- |
| `imagePlaneMotion.activeRunsPerSampledMinute` | Contiguous above-threshold *sampled translation* runs per observed minute | Frequency of physical pan, orbit, dolly or character animation |
| `imagePlaneMotion.activeTimeFractionOfMeasured` | Portion of successfully measured pair-duration with apparent translation | Percentage of the whole film that has camera movement |
| `displayLumaChange.activeRunsPerSampledMinute` | Contiguous above-threshold changes in mean display RGB luma proxy | Real lights moving, changing power, or intentional illumination events |
| `cutCandidatesPerSampledMinute` | Candidate cuts within each analyzer's sampled span | Human-confirmed edits or full-film cut rate |
| `measuredPairFraction` | How much of sampled time has usable non-cut evidence | Confidence calibration or frame-by-frame motion coverage |

`activeRunsPerSampledMinute` is **threshold-dependent** and may overcount or miss brief actions due to sparse sampling. Invalid/missing motion pairs are excluded from measured duration; all-unobservable input yields `null` cadence, not a fabricated zero. The cut-rate denominator is the **sampled time span**, while active-time fraction uses **usable pair duration**. Neither extrapolates to the unseen rest of the film. Image translation and luma change are not jointly synchronized by this command.

## 3. Camera and lighting event frequency after visual review

To track interpreted **camera-work frequency**, reviewers can annotate explicit PTS intervals, technique kinds, alternative explanations, and whether the classification is a working hypothesis. Copy [`examples/visual-events-review.example.json`](../examples/visual-events-review.example.json), replace the all-zero placeholder hash with the media SHA-256, source stream/timebase and real PTS. Reviewers should use the full-speed video, not just stills, and inspect multiple timecoded frames before labeling. Supported kinds:

- Camera: `pan`, `tilt`, `dolly-in`, `dolly-out`, `truck`, `crane`, `orbit`, `roll`, `optical-zoom`, `handheld`, `virtual-parallax`, `other-camera-motion`.
- Lighting: `light-sweep`, `intensity-ramp`, `color-temperature-shift`, `hardness-transition`, `backlight-reveal`, `shadow-motion`, `other-lighting-change`.

```bash
PYTHONPATH=src python -m kumiki_reference_lab visual-events validate ./my-review.json
PYTHONPATH=src python -m kumiki_reference_lab visual-events report ./my-review.json
```

The output reports event counts by type and `cameraMovementEventsPerReviewedMinute` / `lightingChangeEventsPerReviewedMinute` from the exact reviewed interval. **Only** `full-window-visual-review` produces a rate; `partial-window-visual-review` produces counts and `null` rates. `unresolved-hypothesis` events are disclosed separately, never promoted to interpreted frequency. Counts can include overlapping events of different kinds. The reviewer ID and coverage are **self-declared, not externally verified**; a visually labeled dolly or light sweep is still an interpretation, not a recovered real-world camera or light rig.

## 4. Better cross-video evidence next

1. Obtain media with permission and annotate verified PTS intervals for every full comparison film. Capture shot goal, style, subject, camera work, lighting/look, effect, motion cadence, sound cue and reviewer disagreements.
2. Keep real-world camera/lamp hypotheses distinct from scene edits, 2D virtual parallax, graphics animation and color grading; capture temporal start/end and alternative explanations.
3. Link a style/shot annotation to the **exact video ID** and *independently measured, date-stamped* audience data. Compare within genre, duration, channel, release age and format, including ordinary performers.
4. Report sample sizes and uncertainty before any frequency relationship with audience metrics. No causal claim without stronger experimental evidence.

Do not copy other studios' animations or assume the right to redistribute their videos. Build original Kumiki recipes based on general techniques and manually reviewed abstractions.
