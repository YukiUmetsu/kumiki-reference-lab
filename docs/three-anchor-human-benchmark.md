# Human-reviewed benchmark for three-anchor sequence interpretations

**Current evidence status (November 11, 2026):** The repository contains source-PTS
measurements from 15 movie-promotion sources across 45 selected video
windows. Those are *not* three-anchor visual-recognition ground truth.
No approved human-labeled three-anchor benchmark is currently committed.
Accordingly, **no real-video model accuracy, precision or recall is claimed**.

This tool converts locally generated, source-hashed `kumiki-insights` reports
into a defensible human-reviewed evaluation workflow. It evaluates **visible
change categories** between sampled anchors, not full-body gestures,
character identity, physical contact, emotions, dialogue or real-world intent.

## 1. Gather *real*, authorized source-frame evidence

Use the existing `kumiki-watch --review-frames` workflow on videos for
which you have a legitimate right to analyze the media. On the same
machine, run `kumiki-insights` with a permitted, image-capable local
Magnitude model and either manually seeded regions or `--auto-regions`:

    kumiki-insights --workspace 'workspace/frame-review/<source-id>' \
      --roi-seeds './private/seeds.json' \
      --sequence-model 'LOCAL_VISION_MODEL_ID' \
      --max-sequences 4 --max-sequence-calls 8 --overwrite

The input to the benchmark is the resulting report at
`research/analysis/online-videos/<source-id>.insights.json`, containing
`threeAnchorSequenceReview` and exact frame/time/source provenance.

## 2. Generate a pending *human* labeling template

    kumiki-sequence-benchmark template \
      --insights 'research/analysis/online-videos/<source-id>.insights.json' \
      --out './private/<source-id>.human-phases.json'

The generated template is always `pending-review`; its reviewer ID is
`unassigned`, and **every phase label is null**. It is *not* automatically
labeled from Magnitude's own predictions. The template contains the shot ID,
anonymous source-bound region IDs, actual decoded times, three anchor frame
indices, and two phase slots per sequence.

Open the corresponding authorized local frame previews or source clip,
without consulting the model's guesses first. Review each of the
start→middle and middle→last intervals. Fill `humanCategory` with one
**directly visible** category:

- `no-clear-change`
- `apparent-region-translation`
- `apparent-box-size-change`
- `apparent-pose-or-silhouette-change`
- `apparent-turn`
- `apparent-relative-position-change`
- `not-observable` for ambiguity, missing details, unclear framing,
  or insufficient visual evidence.

Do **not** use `unknown` as a ground-truth category: it is a model abstention.
Likewise, do not invent walking, talking, touching, passing objects,
gaze, emotion or intentions. If the evidence is ambiguous, mark
`not-observable`; it is excluded from accuracy but remains counted.

After labeling **every** phase, set:

    "reviewer": {"kind": "human", "id": "your-reviewer-id"}
    "coverageDeclaration": "all-listed-source-frame-phases-human-reviewed"

This is a self-declared human review. The system cannot prove that a
human really watched each video. Do not mark coverage complete early.

## 3. Evaluate (offline, zero model calls)

    kumiki-sequence-benchmark evaluate \
      --insights 'research/analysis/online-videos/<source-id>.insights.json' \
      --labels './private/<source-id>.human-phases.json' \
      --out 'research/analysis/validation/<source-id>.benchmark.json'

The evaluator refuses stale `insightsFileSha256` values, mismatched
source/video hashes, changed shot/frame anchors or model tags, missing
phase labels and non-human or unassigned reviewers. The output retains
only source-bound categories, confusion counts and metrics; no source
video, preview image, crop, base64 or local file path is persisted.

Read `metrics`:

- **Observable phase count:** eligible human-reviewed phase examples.
- **Coverage:** non-abstained model predictions divided by eligible phases.
- **Accuracy on attempts:** correct predictions divided by attempted ones.
- **Correct fraction of observable:** correct divided by *all* eligible
  phases, penalizing abstentions.
- **Error rate on attempts:** incorrect predictions / attempted predictions.
- **Abstention rate:** unknown, missing or invalid model results / eligible.
- **Confusion matrix and per-class support/precision/recall/F1:** detailed
  incorrect predictions. Classes with no support have undefined metrics.
- **Full-sequence exact accuracy:** both phases correct among fully
  observable sequences; missing or abstained predictions cannot pass.

Unobservable phases are excluded with an explicit count, **not counted
as correct**. An empty eligible set yields `null` accuracy, never 100%.
Each output records its exact input report and human-label file SHA-256.

## 4. Aggregate by *actual model* across independent films

    kumiki-sequence-benchmark aggregate \
      research/analysis/validation/*.benchmark.json \
      --out research/analysis/validation/aggregate.v1.json

Aggregate reports require distinct source/model pairs and recompute
published metrics from phase-level entries. Scores for different model
tags are displayed separately rather than pooled into an attractive but
invalid single accuracy number. Repeated sequences from one video are
**not independent source videos**.

**Recommended exploratory target:** cover at least 15 distinct authorized
videos, with animation, product films, typography-heavy explainers,
and camera-driven/edit-heavy clips represented. Review at least
100 *observable* source-phase examples and report abstention
and confusion alongside accuracy. These are *suggested validation sample
sizes*, not claims of statistical generalizability or achieved quality.
Split evaluation by *source video* when comparing prompt/model revisions.

## Guardrails

- The benchmark is entirely dependency-free, offline and strict-JSON-only.
- Source-provenance and template-file digests prevent silently scoring
  labels copied from an older model output against a changed run.
- Synthetic CI fixtures demonstrate calculations, **not model performance**.
- Accuracy of human labels is not independently audited; uncertain
  labels should be excluded and reviewed separately.
- Never copy source frames into Git. You may commit only sanitized
  metrics after review, respecting the rights and privacy of the source.
- Existing What Ships catalog entries and promotional metadata alone
  do not constitute decoded-frame or visual-category validation data.

## Tests

    PYTHONPATH=src python -m unittest tests.test_sequence_benchmark -q

These exercise pending templates, human approval, source hashes, frame
alignment, taxonomy errors, abstentions, undefined accuracy, class
confusions, duplicate-video protection and the complete local CLI flow.

## Next evaluation-driven improvements

Once real reviewed errors exist, group confusion types and inspect
the hard cases: camera-pan vs subject translation, typography transitions
vs character silhouette changes, occlusions, and two-character overlap.
Only then adjust Magnitude prompts, frame selection or tracking gates.
Re-run held-out videos after changes. Converting model categories into
rigged character actions or production-ready Kumiki scene APIs remains
unsupported by this benchmark.
