# Shot-local multi-region temporal evidence

This analysis extends the online frame-review pipeline, not the separate
`character-motion` source-PTS pipeline. It uses **already tracked ROI boxes**
to measure screen-space action *proxies* and contemporaneous relationships
between up to eight provisional regions. It runs entirely in Python without
Magnitude OpenCV, OCR, new video downloads, or any additional image pixels.

## Workflow

First create an authorized frame-review workspace using the existing
`kumiki-watch --review-frames` workflow. Next, provide a local seeded-region
JSON or opt in to anonymous auto-region discovery with the existing optional
OpenCV tracker (see docs/seeded-motion-timing.md and
docs/auto-motion-region-discovery.md):

    kumiki-insights --workspace 'workspace/frame-review/<source-id>' \
      --roi-seeds path/to/reviewed-seeds.json \
      --max-roi-frames 240 --max-multi-events 80 \
      --max-multi-review-tasks 24

Or:

    kumiki-insights --workspace 'workspace/frame-review/<source-id>' \
      --auto-regions --probe-complex-regions \
      --max-multi-events 80

The insights report at
`research/analysis/online-videos/<source-id>.insights.json` now contains
`multiRegionTemporal` alongside the earlier `seededSubjectTracks`,
`seededMotionTiming`, `autoRegionProposals`, and `regionSemanticReview`.

## Measured per-region screen-space events

- `region-image-plane-translation`: observed center displacement, direction
  relative to the preview frame, net/path distance, and average net speed.
- `region-apparent-box-area-change`: changed bounding-box area, which does
  **not** demonstrate physical zoom, scale, or depth movement.

## Measured pairwise events

- `screen-centers-closer` or `screen-centers-farther`: center-distance trends
  between two **concurrently** observed regions.
- `screen-box-overlap-onset`: observed normalized bounding-box overlap
  appearing where it was not previously present.
- `horizontal-image-order-reversal`: changed left-to-right center ordering.
- `shared-image-plane-displacement`: both regions have similar overall
  displacement. This is **not** following; camera motion, parallax or
  compositing can produce similar measurements.

`pairMetrics` retains the contiguous common-frame count, start/end and
closest normalized center distances, overlapping-frame count, maximum box
IoU, shot/source identity, and seed provenance. It does not claim that
characters touched, talked, exchanged objects or even belong to the same
physical scene. These actions need separate review of actual pixels, pose
and audio.

## Review plan for small local agents

`reviewTasks` lists at most 24 event-based inspection tasks (configurable)
with start/mid/end **source frame indices**, shot ID and anonymous region IDs.
No Magnitude calls are made here. A future small-model agent can examine
those frames individually; review tasks are not semantic action detections.
Source timestamps are from the original numeric decoder evidence, not an
estimated generic FPS.

## Quality gates and abstentions

- Every observation must match source SHA-256, the exact source frame index
  and decoded timestamp, and a single candidate shot.
- Each track must begin at an operator seed or anonymous auto-region
  proposal, then contain **consecutive feature-supported frames**, minimum
  four feature inliers and 0.60 inlier fraction. Missing frames, out-of-bounds
  boxes, mismatched origin, or invalid timestamps raise an error.
- Default event threshold is six consecutive observations and at least
  0.2 seconds; small geometric variations are not labeled actions.
- Pair analysis requires synchronized, continuous co-visibility within
  the same shot. No pair association is made across a cut or missing frame.
- No identity recognition, demographics, semantic gestures, skeletal motion,
  mouth shapes, dialogue or social intent is inferred.
- Maximum eight tracks, twenty-eight possible pairs, eighty events, and
  twenty-four review tasks by default; outputs remain bounded and source-bound.
- Without feature-supported ROI tracks, the result explicitly records
  `not-measured-no-supported-roi-tracks` instead of inventing interactions.

## Optional low-call local visual validation

Pass `--multi-action-model YOUR_MAGNITUDE_VISION_MODEL_ID
--max-multi-action-calls 8` with seeded or automatically proposed ROIs to
inspect two color-outlined event anchor frames per bounded local model call.
The output `multiRegionVisualReview` is separate from deterministic
`multiRegionTemporal` geometry. Visual labels remain low-confidence
hypotheses, never confirmed gestures, contact, identity or dialogue.
Without the flag, this stage makes zero model calls.
See [event visual review](online-event-visual-review.md).

## Test

    PYTHONPATH=src python -m unittest tests.test_multi_region_temporal -q

Tests include crossing subjects, parallel camera-like translation, apparent
size changes, different-shot tracks, short or unsupported observations,
source mismatches, provenance integrity, output budgets, and integration
with the online cinematic-insights report.

These measurements may inspire new Kumiki animations, but converting them
into verified character actions or executable scene choreography remains
future work. Do not copy source artwork or treat a geometric proxy as an
original source animation keyframe.
