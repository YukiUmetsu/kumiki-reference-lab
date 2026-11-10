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

For a stricter experimental gate, additionally pass `--subpixel-reverse-check`
(or `analyze --sparse-subpixel-reverse-check`). This requires the corresponding
subpixel option. After a forward peak estimate passes the original integer
matching gates, the checker samples a small after-frame patch at the estimated
fractional endpoint using bilinear interpolation, matches that patch backward
against the original frame, and requires a valid fractional reverse peak within
0.75px of the source patch origin. If that check cannot be made or fails, it
**retains the already accepted integer vector** and labels a fallback instead
of publishing unverified fractional motion. Passed vectors expose
`subpixelReverseErrorPixels` and `fractional-bilinear-patch-checked`. This
forward-guided cross-check is still not independent calibrated validation,
true optical-flow ground truth, or recovery of object or camera identity.
It adds bounded CPU work and preserves prior output/run identities by default.

## Optional bidirectional Lucas-Kanade refinement

Use `--lk-refinement` with `sparse-flow` or `--sparse-lk-refinement` with
`analyze --sparse-flow`. This is a separate opt-in alternative to the NCC
parabolic `--subpixel-refinement` flag; the two cannot be combined. Each point
must **first pass the original integer forward/backward NCC gates**. The LK
solver then iteratively fits small fractional translations over the same 9×9
grayscale patch, compensating for simple brightness offsets. It checks local
gradient conditioning, allows at most eight iterations and 1.25 pixels of
departure from the accepted integer offset, requires a meaningful reduction
in measured photometric RMS, and independently attempts the fractional
reverse fit. A reverse disagreement over 0.75 pixels discards the refinement.

Every accepted integer vector remains present. `lkStatus`, `lkFailureReason`,
`lkOffsetPixels`, `lkPhotometricRmsGray`, `lkReverseErrorPixels` and
`lkIterations` disclose either a **bidirectional fractional candidate** or
an integer fallback. `--pyramid-levels 2` can supply an initial larger-match
integer location, but LK itself is strictly local and not a full dense or
calibrated optical-flow estimator. Strong perspective/rotation, occlusion,
blur, repeated textures and changing light can still fool or disable it.
Fallback is safer than silently replacing a verified integer observation.
No trained model, GPU, or hosted API is required; the default and its immutable
run identity are unchanged.

## Optional local subpatch support guard

Use `--quadrant-consistency` with `sparse-flow` or
`--sparse-quadrant-consistency` with `analyze --sparse-flow` to make already
forward/backward-verified patch matches pass a *second* appearance test.
The 9×9 source and matched destination patches are split into four overlapping
5×5 local regions. At least three must have measurable texture and
zero-mean normalized correlation of at least 0.65. Otherwise the match is
discarded and counted as `quadrant-inconsistent`. Supported vectors expose
`quadrantSupportCount` and four `quadrantCorrelations` (null for untextured
regions). The option has its own immutable analysis-run identity; all default
vectors, metrics and rejected counters remain unchanged.

This detects **localized appearance disagreement**, not occlusion itself.
Lighting changes, blur, resampling, deforming surfaces and partial foreground
coverage can cause disagreement; some genuine matches will be rejected and
some occluded patches will still pass. The four overlapping tests reuse the
same pixels, so their agreement is not four independent confirmations. The
guard may combine with the coarse pyramid, subpixel peaks or LK, but checks
the original *integer* matched patches before fractional refinement. No
discarded feature is reidentified across an occlusion gap.

## Optional perspective hypothesis

Use `--projective-hypotheses` with `sparse-flow` or
`--sparse-projective-hypotheses` with `analyze --sparse-flow`. This adds a
`projectiveHypothesis` to every pair (`null` on a detected cut) without changing
legacy/default results. Unlike the existing six-parameter affine model, a
homography can describe some projective 2D distortions, but **does not reveal
whether a real camera, flat surface, digital crop, or moving object caused
them**.

The deterministic bounded estimator uses normalized direct linear transforms
from four measured point pairs, searches at most 256 hypotheses and refits
only a sufficiently broad consensus. It requires at least ten total matches,
at least 60% inliers, a 40%-of-frame span on both axes, a non-reflected and
plausible frame-corner warp, and materially lower residual error than an
affine fit on *the same inliers*. Otherwise it reports `affine-sufficient`,
`insufficient-points`, `no-robust-projective-consensus`, or another explicit
rejection. `rmsHomographyPixels` and `rmsAffinePixels` are image-plane fitting
residuals, **not calibrated probabilities**; sparse coverage, mixed independent
motions, blur, depth/parallax and repeated texture can make the result
unreliable. No outside models are downloaded. Opt-in runs have distinct
checksum identities, and the existing source-linked visual review can still
display the underlying point tracks.

## Optional held-out motion-model validation

Use `--model-validation` with `sparse-flow`, or `--sparse-model-validation`
with `analyze --sparse-flow`. This adds `modelValidation` to each pair
(`null` across detected cuts), independently of the existing affine and
projective *in-sample* hypotheses. Default reports and previous immutable run
hashes remain unchanged. The analyzer compares three descriptions of
**observed 2D motion**: translation, affine and projective transforms. It
cannot identify a physical camera or object.

Up to 64 accepted correspondences are divided by an interleaved spatial
checkerboard into three folds. Each model fits two folds and predicts the
third, so every point is evaluated exactly once and never helps train its own
parameters. Each fold must have genuinely two-dimensional point geometry,
not just a large span along one diagonal. The report includes held-out RMS
and a conservative higher-rank 90th-percentile error in
image pixels. A more complex model needs a substantial improvement in
held-out errors over the simpler one to become the numeric candidate.

- Fewer than 18 points, narrow coverage or an unsupported fold yields explicit
  abstention. The preferred model also needs at most 1.5 px held-out RMS and
  3 px 90th-percentile error; otherwise it abstains.
- Competing moving layers, outliers, blur, rolling shutter, depth parallax and
  subject deformation can still undermine prediction. Held-out outliers are
  deliberately *not removed*. Thresholds are initial heuristics, **not
  calibrated confidence**. `holdout-supported` indicates a model of these
  sampled image-plane vectors, not confirmation of a camera rig.

Older strict v1 readers may reject the new optional fields when enabled;
users of that mode must update to the corresponding extended v1 schema.
The default report remains unchanged.

```bash
kumiki-ref sparse-flow reference.mp4 --max-points 64 --model-validation --out ./runs/flow
kumiki-ref analyze reference.mp4 --sparse-flow --sparse-points 64 \
  --sparse-model-validation --out ./runs
```

## Optional motion-consistent tracklet handoffs

Use `--tracklet-motion-consistency` with `sparse-flow` or
`--sparse-tracklet-motion-consistency` with `analyze --sparse-flow` to add a
conservative *linking gate*. The default retains previous behavior and output.
After the existing mutually nearest and unambiguous endpoint test succeeds,
the gate compares the next observed displacement with a constant-velocity
prediction scaled by the **actual adjacent source-PTS durations** (including
variable frame rates). It abstains if the difference exceeds the larger of
2.5 image pixels or 60% of the larger predicted/observed offset. No
geometrically ambiguous match can become accepted just because its motion
looks similar.

`temporalTracklets` reports the method and number of otherwise-safe handoff
candidates rejected by this gate. Each surviving observation records the
image-plane residual and allowance (`null` on a new track's first observation).
The gate cannot detect or repair occlusion; a sudden real acceleration,
reversal, changing perspective, or source-frame gap may break a valid track.
**A linked tracklet remains a candidate, never verified subject identity**.
It never fills missing observations or reconnects across cuts.

## Optional two-hop appearance check

Use `--tracklet-appearance-consistency` with `sparse-flow` or
`--sparse-tracklet-appearance-consistency` with `analyze --sparse-flow`.
For a geometrically unambiguous prospective link, compare the first feature's
9×9 grayscale patch on original sampled frame **A** to the new feature's
endpoint on original sampled frame **C**, skipping over their shared frame B.
This tests appearance *across two measured intervals*, rather than comparing
two locations on the same junction frame. A one-pixel endpoint search
accommodates rounding, and zero-mean correlation must be at least 0.62.
Insufficient texture, a patch leaving the frame, or a poor match breaks the
link without inventing a replacement. The report includes rejected and
unobservable link counts; accepted observations include correlation and the
tiny best-match shift. The original per-pair vectors and timestamps remain
unchanged. This option can be combined with the motion-consistency gate.

Two-hop patches can disagree after genuine rotation, occlusion, resampling or
lighting changes, and similar textures can still belong to different objects.
**This is conservative image evidence, not identity verification or occlusion
recovery.** Omitting the flag preserves existing outputs and run IDs.

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
  The optional fractional reverse check detects some inconsistent peaks but
  shares image interpolation assumptions and can reject good small motion.
- Grouping uses translation only. Affine hypotheses help characterize apparent
  scale/rotation, and optional homography hypotheses can characterize limited
  perspective distortion, but camera movement plus parallax, depth,
  rotating props and deformation require more careful geometric modeling.
- Recommended subsequent work: dense or subpixel multi-scale optical flow,
  stronger multi-view feature appearance validation and re-identification with
  occlusion handling, then *optional* image
  segmentation/semantic classification.

The longer-term research use is to inform **candidate** Kumiki camera/subject
choreography, compare observed timings, and select reproducible effect presets
without mistaking 2D motion for recovered film-production parameters.
