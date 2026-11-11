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
