# Automatically propose moving regions without a large vision model

Run `kumiki-insights --auto-regions` to discover repeating visual-motion regions from existing, low-resolution, locally ignored frame previews. No image classifier, Magnitude request, OpenCV, NumPy or new download is required **for the discovery step**.

These are **candidate screen regions**, not recognized characters, products, text,
people, faces, or reliably segmented objects. The feature deliberately does
not claim character identities, ages, demographic attributes or actions.

## Use

After acquiring authorized reference media using the existing workflow:

    kumiki-watch 'https://creator.example/video' \
      --rights-basis written-permission \
      --rights-note 'The creator authorized local reference analysis.' \
      --acknowledge-rights --review-frames

Discover and record candidate moving areas:

    kumiki-insights \
      --workspace 'workspace/frame-review/<source-id>' \
      --auto-regions --max-auto-pairs 36 --max-auto-regions 6 \
      --max-roi-frames 240

Use `--overwrite` to rerun an existing insights report.

The output retains source-hashed numeric suggestions in
`research/analysis/online-videos/<source-id>.insights.json`:

- `autoRegionProposals`: discovery method, source shot, frame evidence,
  normalized boxes, eligible-for-tracking flag, or an explicit no-proposals
  status. No frame pixels, downloaded video or raw image crops are included.
- `seededSubjectTracks`: if OpenCV and NumPy are installed, eligible
  proposals can be passed directly to the existing, shot-bounded ROI tracker.
  Without optional tracking dependencies this reports the existing explicit
  not-run status. No separate seed file is required.
- `seededMotionTiming` / `kumikiTimingProposals`: optional **screen-space timing
  hypotheses**, only when a proposed ROI yields enough valid continuous
  feature-supported track observations. Auto-proposed provenance persists;
  there is no human-label or confirmed-original-animation claim.

For higher-quality tracking, install the existing optional dependencies:

    pip install -e '.[dense]'

## How the low-cost detector works

1. Candidate cuts are grouped into local shots by the existing
   deterministic shot planner. Frames are sampled within each shot, leaving
   time for future tracking. The default budget is at most 36 frame pairs.
2. Each preview is decoded using the repository's validated small-RGB-PNG
   reader and sampled on a half-resolution grid.
3. Local 3-frame-apart differences mark changed cells. Pairs with negligible
   change or a large fraction of simultaneously changing pixels abstain.
4. If the four outer corners agree on a simple near-uniform background,
   connected contrasting foreground regions are intersected with observed
   motion and can become automatic *anonymous* ROI candidates.
5. For complex backgrounds, only raw changed-pixel components are proposed
   for review. These are **never automatically promoted to tracker seeds**.
6. Regions must recur at distinct times within the **same shot** and pass
   size, area, motion-support and spatial-consistency checks. At most eight
   regions can be sent to the existing ROI tracker.

Candidate labels are always "Unclassified motion region N", with
kind "other", seed origin "auto-motion-proposal", and explicit nonsemantic
identity provenance. No frame-to-frame correspondence is inferred across
cuts, and visual changes are not treated as recognized subjects.

## When the system abstains

No automatic tracking seed should be created for a static region,
a dark/bright full-frame flash, broad camera movement, little visual
change, complex inconsistent backgrounds, unsupported frame sizes,
unsafe local PNGs, or a region without repeatable motion evidence.

Even an eligible bounding box may capture a shadow, typography transition,
or a product plus surrounding effects rather than one physical object.
Tracking and downstream timing still require feature support. This
stage is a **low-cost region proposal and selection system**, not semantic
detector accuracy equivalent to a trained object segmentation model.

## Separate manual workflow remains supported

`--auto-regions` and `--roi-seeds path/to/seeds.json` are mutually exclusive.
You may keep using manually verified character/product labels when semantic
identity matters. A small Magnitude vision model may help a coding agent
inspect and **propose** labels, but no model text automatically changes
the unclassified provenance of these geometric regions.

## Optional visual categories and complex-background probes

Add `--region-model YOUR_MAGNITUDE_MODEL_ID --max-region-calls 8` to request
bounded, explicitly unverified category hypotheses on localhost. Add
`--probe-complex-regions --complex-probe-frames 12` to test whether
anonymous complex-background components support a short local
feature track before extending it. These flags are independent; neither
changes a proposal into an identified character or product. See
[local region review](local-region-review-and-complex-probes.md).

## Test

    PYTHONPATH=src python -m unittest tests.test_auto_region_discovery -q

The CI test uses synthetic moving rectangles and verifies persistent
selection, normalized region bounds, complex-background abstention,
full-frame flash abstention, static-scene rejection, shot/source hashes,
invalid PNGs, no-OpenCV operation, in-memory tracker handoff and
provenance-preserving timing. All run without an active Magnitude server.
