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

## What it actually measures

1. Preserve the source stream's integer presentation timestamps (PTS) and
   rational timebase. Sample up to 24 frames evenly in *presentation time*.
2. Decode small grayscale frames, checking decoder PTS against FFprobe.
3. Detect up to 40 corners via a local minimum-eigenvalue score, with
   nonmaximum-distance suppression and per-cell spatial quotas.
4. Match 9×9 patches in a bounded ±8-pixel neighborhood with zero-mean
   normalized cross-correlation. Reject poor/ambiguous appearance matches.
5. Track the matched patch backward; reject roundtrip error over 1.5 pixels.
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

The method is a deterministic, short-baseline **translation baseline**. It does
not recover lens intrinsics, zoom, roll, depth, parallax, true camera pose,
lighting, silhouettes, object identities or 3D geometry. The tracking radius
must fit motion between **selected** frames; if widely separated frames move
more than the search radius, increase sample density within the bounded cap
or interpret the result as unobservable. The current method detects corners
independently for every pair, so **point IDs do not persist** across time.

## Limits, performance and next experiments

- Defaults: 160×90 pixels, 10 seconds, 24 sampled frames, 40 feature points,
  ±8px search. Hard limits: 240×135, 20 seconds, 40 frames, 64 points, ±12px.
  Designed for controlled short tests, not a full feature film at 4K.
- Patch NCC assumes locally stable texture and modest translations. Rotation,
perspective, rescaling, motion blur, occlusion and crossfades degrade it.
- Grouping uses translation only. Affine hypotheses help characterize apparent
  scale/rotation, but camera movement plus parallax, perspective, depth,
  rotating props and deformation require more careful geometric modeling.
- Recommended subsequent work: multi-scale optical flow, homography versus
  affine model selection, persistent temporal track IDs and occlusion
  handling, then *optional* image segmentation/semantic classification.

The longer-term research use is to inform **candidate** Kumiki camera/subject
choreography, compare observed timings, and select reproducible effect presets
without mistaking 2D motion for recovered film-production parameters.
