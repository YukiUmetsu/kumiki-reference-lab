# Local visual category review and complex-background geometry probes

This feature builds on the anonymous motion-region candidates in the online frame-review workflow.
**It does not recognize a person, a named character, a brand, or the source animation pipeline.**
All category labels are low-confidence observations from a local Magnitude vision model,
and geometric tracking remains independent of the model's predictions.

## 1. Keep the offline baseline

First analyze legally obtained media with `kumiki-watch --review-frames`,
then run:

    kumiki-insights --workspace 'workspace/frame-review/<source-id>' \
      --auto-regions

This remains the default, zero-model-call option. It produces anonymous
`autoRegionProposals` and, on sufficiently uniform backgrounds, can pass
eligible regions into the existing shot-bounded OpenCV tracker.

## 2. Optional small-model region categories

With an *image-capable* model loaded in local Magnitude:

    kumiki-insights --workspace 'workspace/frame-review/<source-id>' \
      --auto-regions --region-model 'LOCAL_VISION_MODEL_ID' \
      --max-region-calls 8 --region-model-port 10100 --overwrite

One call sends two tiny images from the same frame: the whole context frame
and a cropped motion proposal. The service is contacted only on
`127.0.0.1:10100` with a bounded OpenAI-compatible request.
At most two samples (first and last observed region frames) are examined
per proposal. A small model receives **one category question** each time.

The model must emit constrained JSON: `category` and `visualCue`.
Allowed generic categories are animated-character, person, product,
on-screen-text, graphic-or-effect, animal, environment, and unknown.
No names, ages, genders, ethnicities, real-person identities, dialogue,
unseen actions or invisible motion should be inferred. On-screen text
is explicitly untrusted. Unexpected categories, missing JSON, and
unavailable local models abstain.

Results appear under `regionSemanticReview` in the same source-hashed
`research/analysis/online-videos/<source-id>.insights.json`.
A pair of matching labels is only `two-frame-agreement-unverified`.
Conflicts return `unknown`. The original unclassified ROI seeds remain
unchanged regardless of the model output; a model guess cannot authorize
tracking or silently turn a region into an identified character.

Live model compatibility on the user's actual Magnitude build must be tested
locally; CI exercises a mocked loopback-compatible server.

## 3. Opt in to complex-background region tracking probes

    kumiki-insights --workspace 'workspace/frame-review/<source-id>' \
      --auto-regions --probe-complex-regions \
      --max-complex-probes 4 --complex-probe-frames 12 --overwrite

This requires the optional `pip install -e '.[dense]'` (OpenCV and NumPy).
Complex-background difference components are not automatically promoted.
The system runs a small **geometry-only trial** using the existing
operator-seeded Lucas–Kanade ROI tracker, but with anonymous auto-region seeds.

To pass, a candidate must:

- Cover a reasonably large local image area and remain within one candidate shot.
- Produce at least six consecutive frame observations, with six or more
  image features and minimum 0.70 feature inlier fraction on continuing frames.
- Exhibit a minimum normalized image-plane displacement of 0.015.
- Be subject to both the number-of-regions and per-probe frame budgets.

Only passing candidates can be included in the longer existing ROI tracker.
Rejected candidates remain visible as abstentions in `complexRegionProbes`.
Without OpenCV, probes report the missing dependency and pass no complex
candidates into tracking.

**Warning:** A stable moving image region is not necessarily an independently
moving object. Camera motion, parallax, shadows, and textured backgrounds
may still pass short geometric probes. The resulting track always remains
an **unclassified, nonsemantic screen-space candidate**.

The flags `--region-model` and `--probe-complex-regions` can be used together
or independently, but both require `--auto-regions`. Neither is required
for the original manual `--roi-seeds` workflow.

## 4. Verify

    PYTHONPATH=src python -m unittest tests.test_region_semantic_review -q

The tests cover limited localhost-only model requests, exact vocabulary
enforcement, failed/contradictory predictions, preview crop bounds,
source-sha matching, optional complex geometric trials, no-CV2 abstention
and preserving `auto-motion-proposal` identity provenance all the way
to the main insights output.

No video, reference frame, crop, model prompt text, or image blob is
committed to the repository. Reports retain only numerical and small
unverified category descriptions.
