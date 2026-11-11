# Three-anchor local visual sequence review

This is an optional, **low-compute** extension to the online cinematic
insights workflow. It compares changes over a short, validated sequence
using two independent **two-image Magnitude calls**, not a high-frame-rate
video model or a long multimodal context.

## Use

First obtain reference video data and ignored low-resolution preview PNGs
using the existing authorized `kumiki-watch --review-frames` workflow.
Provide a verified ROI seed JSON, or enable anonymous automatic regions.
Then run:

    kumiki-insights \
      --workspace 'workspace/frame-review/<source-id>' \
      --roi-seeds path/to/roi-seeds.json \
      --sequence-model YOUR_LOCAL_MAGNITUDE_VISION_MODEL_ID \
      --max-sequences 4 --max-sequence-calls 8 --overwrite

For automated anonymous regions, replace `--roi-seeds` with
`--auto-regions`; optionally add `--probe-complex-regions` when the
OpenCV/NumPy extra is installed. The existing two-frame
`--multi-action-model` mode remains separately available.

Without `--sequence-model`, this stage makes **zero model calls** and
the output marks `threeAnchorSequenceReview.status` as `not-requested`.
Model requests always use the local Magnitude loopback endpoint
`127.0.0.1:10100` unless `--sequence-port` changes the port.
`--sequence-timeout` adjusts the per-call timeout.

## What happens

1. Revalidate each ROI's source hash, candidate shot, exact decoded
   timestamps, frame ordering, and locally supported tracking observations.
2. Read measured `multiRegionTemporal.reviewTasks`, each backed by an
   actual source-bound geometry event, and select three distinct frames:
   start, middle, and end. There is no interpolation of missing frames.
3. Group redundant event tasks that use the same provisional ROI subject
   IDs, source shot, and three anchor frames. Pairwise events are
   prioritized over redundant single-region motion where useful.
4. Generate red (region A) and cyan (region B) local outline overlays
   separately for each frame. They are memory-only and never committed.
5. Ask a tiny local vision model about one visible change from **start
   to middle**, then **middle to end** in two calls. Each call uses at
   most two bounded low-resolution PNGs and 110 response tokens.
6. Combine the two resulting category *guesses* as one of:

   - `repeated-visual-change-unverified`
   - `different-visible-phases-unverified`
   - `consistent-no-clear-change-unverified`
   - `insufficient-consistent-visual-evidence`

Two agreeing answers do not prove a gesture. The model is constrained
to existing categories like apparent translation, silhouette change,
turn, or relative-position change. Invalid or overlong responses
abstain. A connection failure ends the review immediately.

## Data and resource limits

The existing Git-tracked report
`research/analysis/online-videos/<source-id>.insights.json` receives
`threeAnchorSequenceReview`, including:

- Source SHA-256, shot IDs, stable opaque sequence IDs, provisional
  tracking-region IDs and manual/automatic seed provenance.
- Exact source frame indices and decoder timestamps for three anchors.
- Which measured, source-grounded event types informed the review.
- Both phase category guesses, short visual evidence and abstentions.
- An explicitly unverified consistency summary, requested/used call
  budgets and remaining candidates.

Default budgets are **4 unique sequences** and **8 model calls**.
At most 12 sequences or 24 model calls are permitted in one run.
Each fully reviewed sequence costs exactly two calls, even when
several geometry events share its three anchors.

No source movie, image frame, crop, base64 payload, or model input is
written to the repository. Only the source-hashed research metadata
and short unverified model outputs are persisted.

## Quality and interpretation limits

- Three sampled frames do not establish uninterrupted motion; models
  only see the two endpoints of each successive phase.
- Consistent guesses may be consistently **wrong**. No measured
  recognition accuracy or confidence calibration is claimed.
- Screen-space center distance cannot establish physical contact,
  transfer of objects, emotion, intent, speech, depth or causal action.
- A perceived turn does not recover a rig, joints, muscles or a
  verified skeletal pose sequence.
- Camera motion, parallax and compositing can mimic subject motion.
- No recognition or re-identification of people or characters
  across cuts is performed.
- Sequence review never updates seeded subject identity or creates
  executable `kumiki-ui` animation templates.

The existing `character-motion` and `local-character-interactions`
tools operate on a different source-PTS workflow. This stage is a
lightweight adapter for already acquired online frame-review data, not
a replacement for those implementations.

## Test

    PYTHONPATH=src python -m unittest tests.test_three_anchor_sequence_review -q

Unit tests use synthetic source-verified PNG previews and a mocked
Magnitude endpoint, with no real model or new media download.
Live visual quality still needs validation against diverse real
reference clips and the user's local Magnitude version.
