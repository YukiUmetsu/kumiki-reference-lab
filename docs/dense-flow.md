# Bounded dense optical flow (optional)

`dense-flow` is a local, CPU-oriented experiment for studying image-plane
motion in reference videos. Unlike the existing corner-based `sparse-flow`,
OpenCV's multi-scale Farneback method first estimates a displacement for
**every pixel**, then exports a small, spatially distributed set of verified
grid observations. It is deliberately not a camera tracker, person tracker,
scene reconstruction method or renderer.

## Install and run

```bash
python -m pip install -e '.[dense]'
kumiki-ref dense-flow reference.mp4 --max-seconds 10 --max-samples 24 \
  --grid-step 12 --out ./runs/dense
kumiki-ref analyze reference.mp4 --dense-flow --dense-samples 24 \
  --dense-grid-step 12 --out ./runs
```

OpenCV is optional and loaded only when the dense stage is requested. It
requires no account, model weights, GPU, service or external network access.
The `opencv-python-headless` wheel includes a CPU implementation suitable for
Apple Silicon macOS as well as Linux. These calculations do not use MPS/GPU.

## Measurements and rejection gates

1. The same FFprobe/FFmpeg timebase contract as `sparse-flow` selects no more
   than 40 decoded source frames within a 20-second window. Original integer
   source PTS and rational delta times are preserved. A detected hard-cut
   *candidate* makes its crossing pair `cut-boundary`, with no optical flow.
2. Three-level Farneback flow (half-resolution pyramids, 15-pixel window)
   estimates forward and backward dense 2D displacements on 8-bit grayscale.
3. Export only grid points (8–24 px spacing). The source and destination both
   need 9×9 local grayscale standard deviation of at least 8. The endpoint
   must lie safely in frame, the vector must be at most 24 px, and the
   forward/backward round trip must stay within 1.5 px. A second, independent
   appearance check requires at least 0.62 zero-mean normalized correlation
   between the source and warped-destination 9×9 patches. This catches many
   unrelated textured images that reverse-flow checks alone would accept.
4. The report includes accepted `{x,y,dx,dy}` candidates with roundtrip errors,
   rejected counts by reason, and the accepted fraction. `flow-observed`
   requires at least five accepted grid points. One to four vectors yield
   `insufficient-grid-support`, while zero is `unobservable`. The distinction
   prevents a small but valid grid from being reported as no observation.
   These statuses do **not** mean a complete dense field is reliable or that
   a particular camera/object moved.

The output follows [`kumiki.dense-flow.v1`](../schemas/v1/dense-flow.schema.json)
and may also be published inside an immutable analysis run. Its settings and
library versions are recorded; opt-in run identity differs from the default.
Old/default reports are unchanged. Stage artifacts are rechecked by the
analysis-run checksum inventory on reuse.

## What the evidence cannot establish

- Two independent layers can move in opposite directions. No majority-vector
  rule here attributes either motion to a camera or background.
- The local texture, appearance and reverse-flow checks **do not detect true occlusion
  boundaries or recover an identity**. They only abstain in some unreliable
  image regions. Thin features, repeated patterns, motion blur, crossfades,
  rolling shutter, saturation and changing light can still fool them.
- The source is resized to a bounded analysis resolution (default 160×90), so
  pixel displacement and thresholds apply to that image plane, not 4K source
  pixels, 3D meters, focal lengths or camera velocities. Pair durations come
  from actual source PTS, never nominal frame index.
- The synthetic fixture suite covers basic translation, competing 2.5D-like
  depth layers, a directional exposure-blur interval, obstruction, VFR and
  cut abstention. It is not calibrated real-world accuracy evaluation,
  professional quality approval or trained confidence.

Recommended next step: validate on independently measured real footage with
depth, lens variation and deforming subjects before permitting any learned
re-identification or camera-motion claim.

## Diagnose changes in temporal observation support

```bash
kumiki-ref dense-temporal-support ./runs/dense/dense-flow.json \
  --out ./runs/temporal-support
```

The offline [`kumiki.dense-temporal-support.v1`](../schemas/v1/dense-temporal-support.schema.json)
report compares **accepted grid coordinates** in successive dense-flow pairs.
It records which fixed positions retain, lose or gain measured vector support,
alongside original source PTS and rejection counts. At least ten previously
supported points followed by a reduction to half or less produces a
`support-drop-candidate`; the reverse produces a `support-rise-candidate`.
Other transitions are `no-large-aggregate-change`. A cut suppresses the
comparison and also resets the following pair. No support is interpolated
across a missing or cut observation.

This is deliberately **not optical-flow tracking across time**. The same
fixed (x, y) is a different physical surface point after the image moves.
Support may change because of motion, blur, illumination, poor texture or
occlusion; the diagnostic does not distinguish those causes. `sourceVerified`
is `false` because this JSON-only command validates a bounded dense report but
does **not** reopen or decode the original video. To verify the source bytes
and observe actual frames, separately run `review-dense-flow` below. A
canonical SHA-256 binds the diagnostic to the input report's JSON content;
the output is an idempotent no-overwrite artifact, and can be regenerated
without OpenCV. It never asserts semantic occlusion, subject identity,
physical camera or calibrated probabilities.

## Review the actual source frames

```bash
kumiki-ref dense-flow reference.mp4 --out ./runs/dense
kumiki-ref review-dense-flow reference.mp4 ./runs/dense/dense-flow.json \
  --out ./runs/reviews --max-frames 8
```

The returned offline `index.html` shows at most twelve lossless decoded source
frames at **exact original presentation timestamps**, with arrows for accepted
grid vectors from each preceding sampled pair. Cuts display no extrapolated
arrows. Opening/closing, cut-adjacent, weak and strong grid-support moments are
prioritized. The report is verified against source SHA-256, stream, timebase,
sample ordinals, PTS, grid geometry, accepted/rejected counts and image bounds.

The immutable `kumiki.dense-flow-review.v1` bundle includes frame PNGs, copied
`dense-flow.json`, the HTML gallery and a checksum manifest. Identical requests
reuse an intact bundle; tampering stops reuse. This reviewer itself uses no
OpenCV or neural models, only FFmpeg and Python's standard library. The arrows
are **unreviewed image-plane evidence**, not validated object identities,
occlusion segmentation, 3D depth, camera recovery or artistic approval.
