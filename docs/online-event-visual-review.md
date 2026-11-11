# Optional local visual review of measured multi-region events

The online frame-review pipeline derives deterministic screen-space events in
`multiRegionTemporal` without AI. This optional stage asks a small **local**
Magnitude vision model about ONE visible change between two source frames
that already have confirmed, shot-local ROI observations.

## Invocation

Use existing authorized, locally ignored PNG previews and manually seeded
or automatic region tracking. To avoid a model call in every step, the default
`kumiki-insights` pipeline **does not run event visual review**.

To request narrow event review explicitly:

    kumiki-insights --workspace 'workspace/frame-review/<source-id>' \
      --roi-seeds path/to/roi-seeds.json \
      --multi-action-model 'YOUR_MAGNITUDE_VISION_MODEL_ID' \
      --max-multi-action-calls 8 --overwrite

Or, when trying anonymous automatic region tracking:

    kumiki-insights --workspace 'workspace/frame-review/<source-id>' \
      --auto-regions --probe-complex-regions \
      --multi-action-model 'YOUR_MAGNITUDE_VISION_MODEL_ID' \
      --max-multi-action-calls 8 --overwrite

The model must support images on Magnitude's local OpenAI-compatible endpoint.
The default is loopback `127.0.0.1:10100` and a 120-second per-call timeout;
`--multi-action-port` and `--multi-action-timeout` may override those.
Only event review uses the model. Shot grouping, tracking, timing and event
geometry remain deterministic and separate.

## Source-grounded review method

1. Revalidate the media SHA-256, shot, decoded presentation timestamps,
   exact observed frame indices, bounded ROI tracking inliers and seed origins.
2. Match each review task to an **existing measured event signature**, not
   an invented action or user-inserted claim.
3. Select the first and last observed frames from that event's review task.
   No cut or missing frame is filled, and source PNGs remain Git-ignored.
4. Outline region A in **red**, region B (when present) in **cyan**, at their
   *observed* bounding boxes for each source frame. These colors correspond
   to local report IDs, not to known people/characters.
5. Send exactly those two low-resolution outlined PNGs, with one tightly
   scoped question, to the local model. The model response is capped
   at 110 tokens and a small JSON response.
6. Accept only these exact visual-change categories:

   - `no-clear-change`
   - `apparent-region-translation`
   - `apparent-box-size-change`
   - `apparent-pose-or-silhouette-change`
   - `apparent-turn`
   - `apparent-relative-position-change`
   - `unknown`

   Every category is a low-confidence, **unverified hypothesis**.
   The visible-evidence field must be twelve words or fewer. Unexpected
   model output, extra JSON keys, or forbidden action labels abstain.

Model outage/unsupported image API stops further inference rather than
repeating long timeouts. Other invalid responses are retained as unknown
under the configured call budget.

## Output

The same Git-tracked metadata report now includes
`multiRegionVisualReview` with source SHA, decoded frame anchors,
provisional subject IDs, seed provenance, visual change suggestions,
abstentions and number of local calls. Neither screenshots, source video,
base64 images, generated outlines, or inferred identity claims are saved.

**No detected pose or motion establishes walking, touching, conversation,
exchanging objects, intentions, identity, or physical camera movement.**
The actual source clips, subtle body gestures, and camera-relative changes
may remain ambiguous between just two frames. Model output cannot promote
an anonymous seed to a recognized character or create an executable
`kumiki-ui` choreography. Such conclusions require further visual QA.

## Three-anchor phase review

A further optional `--sequence-model LOCAL_VISION_MODEL_ID` mode
compares start/middle and middle/end frames in **two** locally bounded
vision calls per sequence. It groups duplicate geometry event tasks,
and records `threeAnchorSequenceReview` with source timestamps,
visual-change phases, abstentions and uncertain agreement. Unlike a
video model, it never claims to have seen every intermediate moment.
See [three-anchor sequence review](three-anchor-sequence-review.md).

## Tests

    PYTHONPATH=src python -m unittest tests.test_online_event_review -q

Tests use a mocked local Magnitude API; live compatibility with the
user-hosted Magnitude model must still be tested on that machine.
No network service, video, FFmpeg or model download is needed in CI.
