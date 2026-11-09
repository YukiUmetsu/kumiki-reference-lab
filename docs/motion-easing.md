# Global image-motion easing candidates

The `motion` analyzer measures image-plane translations between sampled source
frames and sums them into bounded, cut-separated paths. `fit_easing_candidates`
then tests five authored one-dimensional progress curves: linear, quadratic
ease-in/out and cubic/quintic ease-in-out. Time is normalized using **actual
source PTS**, not nominal frame indices.

These fits describe how a measured **2D image displacement** progresses along
its start-to-end direction. They do not recover an editor's animation keys,
camera rig, foreground object identity or intention.

## Geometry guard

Projecting a bent trajectory onto a straight start-to-end line can produce a
numerically perfect `linear` curve even when the visible motion takes a large
detour. Before ranking curves, the fitter now reports:

- `maxLateralDeviationPixels`: largest perpendicular distance to the straight
  start-to-end line, measured at original observed samples.
- `pathLengthRatio`: sum of all observed pair displacement lengths divided by
  the start-to-end displacement. A straight, monotone path has ratio 1.

The fitter returns `nonlinear-image-path` with **no winner or candidates** if
the sideways excursion exceeds both the tolerance implied by a 2 px floor
and 15% of net distance, or the observed path exceeds the greater of net
distance + 3 px and 120% of net distance. Small sampling jitter is tolerated.
The fit still rejects insufficient movement, nonmonotone projected progress,
short runs and poor/ambiguous curve families as before. Nonfinite observations
return `invalid-observations` rather than producing non-JSON numbers.

Both thresholds are fixed, deliberately conservative *heuristics*, not
calibrated probabilities. The filter does **not** fit curved motion or infer
depth; future analysis may fit 2D splines separately with source-based QA.
The [synthetic image-motion tests](../tests/test_image_motion.py) exercise a
straight diagonal, a sideways arc, repeated short detours and nonfinite input.
