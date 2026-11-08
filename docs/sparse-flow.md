# Sparse image-plane flow (experimental)

`kumiki-ref sparse-flow reference.mp4 --max-seconds 10 --out ./runs` creates
`sparse-flow.json` conforming to
[`schemas/v1/sparse-flow.schema.json`](../schemas/v1/sparse-flow.schema.json).
Install NumPy with `pip install '.[motion]'` before running. The tool needs
FFmpeg and FFprobe in `PATH`; it runs locally without model/API calls.

The same artifact is available inside atomic analysis bundles with
`kumiki-ref analyze reference.mp4 --sparse-flow --sparse-samples 24 --out ./runs`.
`--sparse-points`, `--sparse-radius` and `--sparse-correlation` can tune
the experiment independently of `--max-samples`, which controls the optional
global-motion and ROI stages. Opting in changes the checksum-bound run
identity; legacy runs without sparse flow keep their existing identity.

## Review the actual sampled frames

```bash
kumiki-ref sparse-flow reference.mp4 --out ./runs/sparse
kumiki-ref review-sparse-flow reference.mp4 ./runs/sparse/sparse-flow.json --out ./runs/reviews
```

Open the printed `index.html` locally. The command decodes the **original
source's selected PTS frames** into small lossless RGB PNGs and overlays
accepted image-plane pair displacements as SVG lines and endpoints. It shows
up to eight frames and twelve top multi-pair tracklets by default; use
`--max-frames` (2–12) or `--max-tracklets` (1–16) to tune this bounded review.
Each arrow ends on the frame shown, and starts at its matched point on the
preceding sampled frame. For a pair without selected tracklets, no lines are
shown; if no multi-pair tracklets exist anywhere, the overlay can show up to
24 individual accepted pair vectors instead.

The standalone HTML bundle contains `index.html`, PNG thumbnails, a copied
`sparse-flow.json` and a checksum manifest conforming to
[`sparse-flow-review.schema.json`](../schemas/v1/sparse-flow-review.schema.json).
Source SHA-256, stream index, timebase, decoded frame PTS and tracklet links
are verified. The output directory name is based on the source and settings;
rerunning reuses an intact bundle and refuses a modified one. The input video
is not copied or changed. This is **candidate evidence for human inspection**,
not semantic object tracking, recovered camera movement, a verified physical
trajectory, or a human artistic-quality verdict. It does not use a hosted model.

For larger movement between selected frames, opt in to the bounded **two-level
coarse-to-fine fallback** with `kumiki-ref sparse-flow reference.mp4
--pyramid-levels 2` or `kumiki-ref analyze reference.mp4 --sparse-flow
--sparse-pyramid-levels 2 --out ./runs`. The default level 1 retains the
original behavior and analysis-run identity. Level 2 first attempts the
original full-resolution match; only failed matches are retried using a 2×
averaged grayscale image and then refined within ±2 original pixels.
Reverse matching checks the recovered patch against its source neighborhood.
Each accepted vector carries `searchLevel: 1|2` so reviewers know which
method contributed. This increases reachable displacement to roughly
2× the declared local radius plus 2px refinement; it does **not** guarantee
recovery under blur, occlusion, repeated texture, zoom or camera rotation.

For small motions that fall between full pixels, add `--subpixel-refinement` to
`sparse-flow`, or `--sparse-subpixel-refinement` to `analyze --sparse-flow`.
This optional refinement fits independent three-point parabolas around each
accepted integer normalized-cross-correlation peak. If either axis lacks a
stable concave neighborhood (including at a search edge), the vector keeps
its original integer displacement and reports `integer-fallback`.
Otherwise `dx` and `dy` include the bounded (±0.75px) fractional offsets and
the vector reports `candidate-1d-parabola` plus the original interpolation
offset. The source patch selection, acceptance thresholds and **reverse
consistency check remain at integer patch centers**; fractional offsets have
not been independently backward-verified. They are candidate measurements,
not ground-truth subpixel tracks, calibrated accuracy or camera velocity.
The option works with `--pyramid-levels 2` and produces a distinct analysis
run identity; when omitted, all prior integer outputs and run IDs remain
unchanged. Read the per-vector `subpixelReverseVerification` before interpreting
small changes in trajectory or apparent affine geometry.

## What it actually measures

1. Preserve the source stream's integer presentation timestamps (PTS) and
   rational timebase. Sample up to 24 frames evenly in *presentation time*.
2. Decode small grayscale frames, checking decoder PTS against FFprobe.
3. Detect up to 40 corners via a local minimum-eigenvalue score, with
   nonmaximum-distance suppression and per-cell spatial quotas.
4. Match 9×9 patches in a bounded ±8-pixel neighborhood with zero-mean
   normalized cross-correlation. Reject poor/ambiguous appearance matches.
5. Track the matched patch backward; reject roundtrip error over 1.5 pixels.
   In two-level fallback mode, reverse consistency is measured against the
   original source-patch neighborhood, so it is not an independently
   initialized global backward correspondence.
6. Group accepted integer pixel displacements into up to two translation
   consensuses with 1.5-pixel tolerance, a three-point minimum and a
   2.5-pixel separation requirement. Keep unclassified point vectors.
7. Independently test up to 384 deterministic three-point affine hypotheses
   over all accepted correspondences, requiring at least 55% inliers (and
   at least six), sufficient 2D spatial coverage, and low reprojection error.
   An affine model is only preferred if it substantially reduces RMS error
   relative to translation on the same inliers. Degenerate/reflected/unstable
   estimates receive explicit rejection statuses.
8. Detect hard-cut candidates separately and **never** track across their
   boundaries. A cut pair has no vectors and a null consensus.
9. Conservatively link independent pair vectors into `temporalTracklets`:
   compare each vector's projected endpoint only to the next pair's corner,
   require mutual-nearest agreement within 2 pixels and reject candidates
   with a competing neighbor within 0.5 pixels of the best distance.
   Publish only tracklets spanning at least two consecutive pairs; record
   the original pair/vector indices, PTS, observed endpoints, and handoff
   residuals. Cuts, gaps, missing detections and ambiguous matches break
   continuity; no missing points are interpolated.

Each pair exposes `detectedCorners`, `rejected` counts by reason, `vectors`
with original coordinates, offsets, match correlations and roundtrip error,
and `consensus` containing group support, median residual, spatial coverage,
and bounding coordinates. `status` communicates when no consensus exists or
when similarly supported motion groups make the dominant group ambiguous.
Each non-cut pair also includes `geometryHypothesis` with its own status,
accepted point indices, candidate 2×3 affine matrix, translation/affine RMS,
observed spatial support, apparent area scale, rotation and anisotropy.
These are *estimated image properties*; they are never proof of optical zoom,
camera roll or an object's physical rotation.

`temporalTracklets.status` is `candidate-only` when at least one conservative
multi-pair link survives, otherwise `insufficient-continuity`. Its
`singlePairCandidatesDiscarded` counts tracks that never gained a second
observation. A tracklet is a deterministic short image-plane correspondence
**candidate**, not a persistent verified object identity. Its `group` may
change between pairs. Even a clean multi-pair link can switch between similar
textures, and the method does not recover links after occlusion.

Each surviving tracklet's optional `kinematics` summarizes **observed pair
motions only**. `durationSeconds` is an exact reduced rational computed from
the original source PTS and stream timebase, including unequal VFR intervals.
`summedImageDisplacementPixels` sums each accepted pair's measured displacement;
`observedPathLengthPixels` sums their Euclidean lengths. Mean image velocity
and speed divide those observations by the observed PTS span, not nominal FPS.
These are sampled pixel-space statistics, not recovered 3D speed, camera
velocity, exact object paths, or trajectories filled across lost detections.

## Reading the results honestly

- `dominant` = most-supported observed image translation, **not** "camera" or
  "background". An independently moving foreground could occupy most corners.
- `secondary` = a second translation among tracked pixels, **not** a
  semantically recognized object or a reliable mask.
- `single-image-translation-candidate` = one supported translation model,
  *not* proof of a single physical moving object or pure camera translation.
- `insufficient-consensus` = inadequate accepted vectors; do not fill in a
  guessed movement. A repeated pattern can be rejected as ambiguous.
- `ambiguous-dominant-group` = two similar-support groups; report both, do
  not force a choice.
- Each accepted patch correlation is an appearance score, not a calibrated
  probability or verified identity.
- `affine-image-plane-candidate` = the measured 2D point motions fit an
  affine transform better than translation, under the declared thresholds.
  `translation-sufficient` means affine adds no meaningful evidence.
- Apparent 2D area scale, planar rotation and anisotropy are mathematical
  decompositions of the fitted matrix. Multiple possible 3D mechanisms can
  produce the same screen-space transformation.

The method is a deterministic, short-baseline **image-plane baseline**. It does
not recover lens intrinsics, zoom, roll, depth, parallax, true camera pose,
lighting, silhouettes, object identities or 3D geometry. The tracking radius
must fit motion between **selected** frames; if widely separated frames move
more than the search radius, increase sample density within the bounded cap
or interpret the result as unobservable. Corners are still detected independently
for every pair; tracklet IDs link only short, mutually consistent observations
and are **not** verified identities.

## Limits, performance and next experiments

- Defaults: 160×90 pixels, 10 seconds, 24 sampled frames, 40 feature points,
  ±8px search. Hard limits: 240×135, 20 seconds, 40 frames, 64 points, ±12px.
  Designed for controlled short tests, not a full feature film at 4K.
- Two-level search runs more bounded CPU work on pairs where local matching
  failed. Original level-1 estimates are unchanged; coarse recovery may fail
  under aliasing or downsampling of fine textures, and is only candidate
  evidence, not an automatic correction to physics or film technique labels.
- Patch NCC assumes locally stable texture and modest translations. Rotation,
perspective, rescaling, motion blur, occlusion and crossfades degrade it.
- Fractional peak fitting assumes locally smooth, concave correlation around
  a valid integer match. It can be biased by resampling, noise and patch
  changes; an integer-peak backward gate cannot certify fractional accuracy.
- Grouping uses translation only. Affine hypotheses help characterize apparent
  scale/rotation, but camera movement plus parallax, perspective, depth,
  rotating props and deformation require more careful geometric modeling.
- Recommended subsequent work: dense or subpixel multi-scale optical flow,
  homography versus affine model selection, validated feature
  re-identification with occlusion handling, then *optional* image
  segmentation/semantic classification.

The longer-term research use is to inform **candidate** Kumiki camera/subject
choreography, compare observed timings, and select reproducible effect presets
without mistaking 2D motion for recovered film-production parameters.
