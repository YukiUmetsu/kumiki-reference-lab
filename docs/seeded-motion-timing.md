# Seeded motion timing and easing estimates

This stage turns already measured **shot-local, feature-supported** 2D
region tracks into reusable timing hypotheses without using Magnitude or
another AI service.

The ROI tracker needs the existing optional OpenCV and NumPy "dense" extra,
but **deriving timing from its saved observations uses only standard Python**.
Without a supported seeded track, timing is marked as not measured rather
than guessed from unrelated frames.

## Use

1. Run kumiki-watch with the --review-frames option on authorized media.
2. Seed a region bounding box for a visible character, product, prop, or
   title within one shot; use the JSON format in
   docs/temporal-cinematic-intelligence.md.
3. Run cinematic insights:

    kumiki-insights --workspace 'workspace/frame-review/<source-id>' \
      --roi-seeds path/to/roi-seeds.json --max-roi-frames 240

4. Inspect research/analysis/online-videos/<source-id>.insights.json.

The report adds:

- seededMotionTiming: source-hashed deterministic timing measurements,
  abstentions, and conservative progress-curve fit candidates.
- kumikiTimingProposals: non-executable starting points for original
  animation. Target artwork, component API, target positions and duration
  remain unspecified.

## Measurements

For each eligible track:

- Actual decoded timestamp sequence and consecutive frame indices.
- Observed region-box centers, net and path displacement, straightness.
- Image-plane speed estimates, peak and median values.
- Projected progress along the measured start-to-end screen-space direction.
- Approximate start and end slow-progress/hold fractions.
- Screen-space scale and rotation change from the seeded region.
- At most 24 sampled observed region boxes with normalized times.
- Root-mean-square error versus linear, quadratic ease-in, quadratic
  ease-out and cubic smoothstep progress functions.

A simple curve family is proposed only when fit RMSE is at most 0.07 and
the next-best curve is at least 0.012 RMSE worse. Otherwise, timing is
explicitly ambiguous instead of silently inferring a specific easing curve.

## Conservative abstention

No usable curve is claimed for:

- Fewer than eight consecutive tracked observations or less than 0.15
  seconds of observed movement.
- Net displacement below 0.025 normalized image units.
- Curved, reversing, nonmonotonic or overshooting paths.
- Large discontinuities or unexpectedly wide timestamp gaps.
- Insufficient local feature and inlier support.
- Frame indices, timestamps or shot identities that disagree with
  source-hashed numeric evidence.

These are screen-box progression models, NOT recovered source animation keys,
exact original easing controls, persistent reidentification, physical camera
trajectories, or 3D motion. Similarity to smoothstep, for example, does not
prove an animator used smoothstep. Unverified observed paths are not copied
into executable Kumiki assets.

The calculation uses no model call, source video or frame pixels; it consumes
existing measured ROI trajectories. Low-capacity local Magnitude models
remain useful for separate visual classification.

## Test

    PYTHONPATH=src python -m unittest tests.test_motion_timing -q

Regression tests cover linear, ease-in, ease-out and smoothstep timing,
long and static sequences, short/reversing/curved trajectories, tracking
confidence, source SHA and timestamp validation, shot boundaries, and
cine-insights integration without local vision inference.
