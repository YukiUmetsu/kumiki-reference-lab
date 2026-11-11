# Video-sequence validation dataset

This directory is reserved for **human-reviewed source-video benchmark
outputs**, not raw copyrighted video, frame previews, speculative AI
annotations, generic video catalog metadata, or synthetic test fixtures.

## Evidence inventory at the November 11, 2026 baseline

- Movie-promotion studies: 15 media sources and 45 sampled source-PTS
  windows in `../movie-promotions/derived/timed-events.v1.json`.
  These record source-PTS cut candidates and audio-level attacks, **not**
  human-reviewed three-anchor visual-change categories.
- What Ships: nine selected browser-observation records in
  `../whatships/`; those are incomplete visual spot checks, **not**
  source-verified full video sequence benchmarks.
- The Git-tracked baseline has **zero approved human-reviewed
  three-anchor phase-label benchmark files** and no documented
  real-video recognition accuracy for the new local sequence module.

Do not treat the 15/45 promotion counts, 2,861 indexed What Ships
entries, or local CI synthetic fixtures as visual recognition accuracy.
These datasets are useful for prioritizing real evaluation candidates,
not substituting for an actual human-reviewed source clip.

## Adding validated video evidence

1. Acquire/prepare authorized source video previews on the local machine.
2. Produce `kumiki-insights --sequence-model ...` reports using the
   chosen local image-capable model and source-bound ROI tracks.
3. Generate the **pending** annotation template with
   `kumiki-sequence-benchmark template`, independently inspect the
   frames, assign every phase category or `not-observable` and approve
   the explicit human coverage declaration.
4. Run `kumiki-sequence-benchmark evaluate` to produce a source-bound
   `.benchmark.json` file and inspect confusion/error/abstention counts.
5. After human verification and source-rights/privacy review, commit
   sanitized benchmark JSON (no screenshots or media) here. Keep
   original media and locally ignored preview PNGs outside Git.
6. Run `kumiki-sequence-benchmark aggregate` over reviewed source
   reports for comparisons that do not pool different models or duplicate
   the same video.

See [the detailed methodology](../../../docs/three-anchor-human-benchmark.md).

## Reporting standard

Always report: independently reviewed source count, observable phases,
excluded/not-observable phases, model coverage, abstention rate, accuracy
on attempted predictions, correct fraction of observable phases,
error categories, full-sequence exact accuracy, and model identity.
Zero scored/observable phases mean accuracy is **undefined**, not 100%.

Visual change labels are not skeletal actions, identity, dialogue,
true camera movements, social interaction or physical object transfers.
