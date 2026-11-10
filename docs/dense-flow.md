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
- The small synthetic fixture suite calibrates basic translation, competing
  moving layers, occlusion, VFR and cut abstention. It is not real-world
  accuracy evaluation, professional quality approval or trained confidence.

Recommended next step: compare this field with known, independently generated
2.5D parallax, blur and deforming-subject footage, then add explicit temporal
occlusion diagnostics before allowing learned re-identification.
