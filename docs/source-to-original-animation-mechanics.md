# Source-grounded original motion mechanics for Kumiki

This layer bridges measured image-plane movement in `kumiki-reference-lab`
to **specific original animation ideas** worth authoring in `kumiki-ui`.
It does **not** reconstruct a source film's animation project, infer
unknown characters or physical camera motion, or claim that a matching
production component is missing from the registry.

## Output

After generating an online frame-review workspace and running
`kumiki-insights --roi-seeds ...` or `--auto-regions` with supported
OpenCV tracking, the normal source-hashed report now includes
`originalMotionMechanicIdeas`. It is computed entirely from the
existing `multiRegionTemporal.events`, without additional video
downloads, Magnitude calls, OCR or image storage.

```bash
kumiki-insights --workspace 'workspace/frame-review/<source-id>' \
  --roi-seeds ./private/source-region-seeds.json \
  --max-mechanic-ideas 24 --overwrite
```

The result resides in the existing
`research/analysis/online-videos/<source-id>.insights.json` metadata file.
If no supported tracks/events exist, it explicitly returns **zero**
ideas; it never invents an inferred technique from titles or metadata.

## Seven specific reusable animation candidates

| Measured screen-space event | Original animation recipe | Concrete motion to build |
|---|---|---|
| Image-plane translation | `directed-screen-travel` | An original icon/asset anticipates, travels along an authored 2D path, then settles |
| Apparent ROI area change | `apparent-scale-focus` | A foreground element scales toward a focal anchor with independent framing and a readable hold |
| Two centers move closer | `paired-convergence` | Two independently paced objects converge toward a common on-screen anchor without assuming touch |
| Two centers separate | `paired-divergence` | A shared composition separates into two clear comparison zones |
| Box overlap begins | `layered-crossing-reveal` | Authored layers intersect under a deliberate z-order or mask, then resolve cleanly |
| Left-to-right order reverses | `two-lane-swap` | Two elements exchange screen lanes on authored paths with safe spacing and a staggered hold |
| Two centers share translation | `shared-shift-with-optional-parallax` | A coordinated visual ensemble translates, optionally adding **newly authored** parallax layers |

Each candidate includes a **specific choreography stage sequence**
(establish → move/transform → settle), proposed control names,
required original assets, source hash, shot ID, frame and decoder
time ranges, provisional ROI IDs, source measurements, and alternative
interpretations that the pixels do **not** prove. These are design
proposals, **not executable scene definitions or exact source keyframes**.

## Existing Kumiki primitives inspected

The suggested source modules existed in
[kumiki-ui](https://github.com/YukiUmetsu/kumiki-ui) at
revision `ac5bf3988d4e5a74d792c2b36418512102d7b1b3`:

- `registry/motion/paths.ts` — authorable 2D paths and anchors
- `registry/motion/presets.ts` — constructive and serializable motion presets
- `registry/motion/shared-element.ts` — shared-element transitions
- `registry/motion/masks.ts` — graphical masks
- `registry/motion/motion-director.ts` — authored timeline compilation
- `registry/motion/transformation-recipes.ts` — transform recipes
- `registry/motion/camera-stage.tsx` — camera/stage rendering
- `registry/visual/comparison-stage-react.tsx` — comparison presentation

Their existence is **not** proof that a particular seven-step recipe
already exists, that its props/API are compatible, or that it is visually
polished. `registryApiVerifiedForThisRecipe` deliberately stays `false`.
Before implementing, inspect the latest component source, registry IDs,
Storybook previews and current documentation. Prefer composing existing
primitives where possible rather than introducing redundant components.

## First merged implementation: Two-Lane Swap

As of the merged
[kumiki-ui PR #128](https://github.com/YukiUmetsu/kumiki-ui/pull/128),
the original **two-lane-swap** animation is an actual, installable
registry pack at kumiki-ui commit
`662f60704851c01c0e6ef58244132fe9f29896ac`.

The directly implemented entrypoints are:

- `registry/motion/two-lane-swap.ts`:
  `compileTwoLaneSwap`, `evaluateTwoLaneSwap`
- `registry/motion/two-lane-swap-react.tsx`:
  `TwoLaneSwapSvg`

`originalMotionMechanicIdeas` now adds
`availableOriginalImplementation` to **only** the
`horizontal-image-order-reversal` / `two-lane-swap` proposal.
It pins that Git commit and registry name, and records that
compiler/renderer structural CI passed. The other six ideas remain
unimplemented proposal concepts in this cross-repository bridge.

**This is not an automatic reference-video-to-animation adapter.**
The published component requires original artwork, a designed stage,
subject bounding radii, screen lane positions and newly authored
frame timing. Source-video normalized bounding boxes cannot be
passed directly into the compiler to recreate the source footage.
The original research field still marks
`registryApiVerifiedForThisRecipe=false` because no automatic
mapping from image measurements to a valid authored scene API exists.

The library validates source-independent, frame-by-frame subject
clearance and viewport boundaries. TypeScript, focused unit tests and
registry validation passed, while **independent human visual approval
and browser screenshots remain pending**, not certified.

## Second merged implementation: Paired Focus

[kumiki-ui PR #129](https://github.com/YukiUmetsu/kumiki-ui/pull/129)
adds the independent **paired-focus** registry pack at pinned commit
`71ab08fcb014959016304c2eb158acf6ddb70283`.

- `registry/motion/paired-focus.ts`: `compilePairedFocus` and
  `evaluatePairedFocus`
- `registry/motion/paired-focus-react.tsx`: `PairedFocusSvg`

One reusable authored component implements three modes:
`converge`, `diverge`, and `converge-then-diverge`.
The `screen-centers-closer` / `paired-convergence` research idea
now links to authored mode `converge`;
`screen-centers-farther` / `paired-divergence` links to
authored mode `diverge`. A focal hold/release is optional original
choreography and must **not** be inferred from sparse image evidence.

`availableOriginalImplementation` identifies the exact shipped
registry pack, pinned commit, exported compiler/render functions and
per-idea authored mode. The screen-geometry measurements are
**not valid executable input**: the component still requires original
assets, independent bounding radii, a focal anchor, stage and timing.
There is no source-to-component conversion adapter, no recovered
source animation, and no character/physical contact inference.
`registryApiVerifiedForThisRecipe` stays `false` because a
measurement-to-authoring mapping has not been verified.

Typecheck, frame-based geometry tests and registry validation passed
on the merged UI PR. The dedicated manual Storybook screenshots and
human visual craft approval remain **pending**.

## Craft and animation-quality gates

For each approved new template:

1. Choose independent authored assets, camera, layout, lighting and
   timing that communicate the intended explanation. Do not duplicate
   source artwork or motion frame-for-frame.
2. Separate movement of elements from the background. Shared movement
   can be caused by an edit, camera move, parallax or compositing;
   it does **not** establish physical tracking or depth.
3. Make the temporal performance deliberate: anticipation, continuity
   and physical plausibility where applicable, easing, motion pauses,
   non-overlapping text, and a final readable settle.
4. For overlaps and swaps, validate occlusion and mask order instead
   of inferring real contact or a hidden third-dimensional path.
5. Render at least start/middle/end and key crossing/settling frames.
   Evaluate in multiple aspect ratios and check boundaries, camera
   cuts, and visual hierarchy. Review the actual rendered output.
6. Retain deterministic frame-time evaluation and serializable presets
   compatible with the existing `kumiki-ui` motion director.

Do not promote measured image overlap into physical contact, infer
who is speaking, estimate actor age/gender/ethnicity, recover exact
poses/rigging, or claim a camera pan from shared pixel translation.
The existing UI `interaction-choreography` module handles real
declared 3D contact *only when intentionally authored*; no image
proximity measurement can authorize an automatic `grasp` or `place`.

## Scope, provenance and tests

`originalMotionMechanicIdeas` is a schema-versioned, bounded research
field, not a registry installer. The source SHA, region-seed provenance
and exact measured event range must match. Each idea explicitly records
the registry revision whose related file paths were inspected,
and preserves `registryApiVerifiedForThisRecipe=false`.

```bash
PYTHONPATH=src python -m unittest tests.test_motion_mechanic_ideas -q
```

Synthetic tests validate event-to-recipe mapping, actual measurement
requirements, camera-like shared movement caveats, safety budgets,
duplicate/tampered geometry rejection and `kumiki-insights` integration.
Only source media reviewed with appropriate rights can establish the
practical value of a candidate; CI does not judge visual craftsmanship.
