# Deterministic technique review cues

The `propose-techniques` command connects measured visual changes with **possible techniques worth studying**, without asserting how a reference video was made. It works offline and does not call AI. Every result is a *hypothesis for a reviewer*; no result certifies cinematic quality or sets a catalog entry to `verified`.

## Usage

```bash
# Source clips remain local. At least one optional measurement stage is needed
# for a nonempty proposal result.
kumiki-ref analyze reference.mp4 --max-seconds 10 --sparse-flow --appearance --out runs/
kumiki-ref propose-techniques runs/analysis-<source>-<settings>/analysis-run.json \
  --catalog-root catalog/entries --out runs/technique-review-r001/
```

The second command writes `technique-proposals.json`. It can also print JSON to stdout without `--out`. Reuse with the same output is idempotent; different content cannot overwrite an existing artifact. It **never changes** the source `analysis-run.json`, its checksum inventory, catalog entries, or external Kumiki repositories. It first validates the analysis run's complete file inventory and all file hashes. Each candidate refers to the exact original source PTS and the catalog entry's revision and SHA-256; the report itself includes the source, run and catalog provenance. All absent optional stages remain absent: no inferred zeroes or imagined observations.

## Currently implemented, strictly conservative rules

| Catalog candidate | Measured gate | What it does **not** prove |
| --- | --- | --- |
| `camera.motivated-macro-dolly` | At least two adjacent, cut-free sparse-flow pairs with robust affine fits; each has image-plane scale from 1.018 to 1.30, at least 60% affine inliers, anisotropy at most 1.12, rotation at most 5°, and at least 30% spatial support in each dimension | No proof of camera dolly, lens change, parallax, physical distance, close-up intent, or a story-relevant hero detail. Digital crop, animated object scale, or 2.5D layers can explain the pixels. |
| `lighting.softbox-curvature-reveal` | At least three consecutive, cut-free appearance samples with a bright-pixel centroid moving at least 0.08 of the normalized frame, while global display luma range is at most 0.10 and bright-pixel fraction range at most 0.12 | No physical light source, softbox, reflection identity, source direction, brightness, surface curvature, or deliberate lighting intent. A bright subject, texture change, compositing, or moving camera can mimic the cue. |

These are **review gates, not calibrated likelihoods**. Thresholds are initial authored heuristics, included verbatim in the output and subject to future validation against labeled synthetic and real footage. A missing candidate is not evidence that the technique is absent. Since the pipeline starts with only a bounded source window, it may miss later shots. A single cut does not suggest `editing.match-on-action`: that requires action continuity and a semantic subject match that the current analyzers cannot establish.

## Output and review contract

See [`schemas/v1/technique-proposals.schema.json`](../schemas/v1/technique-proposals.schema.json).

- `schemaVersion`, `status`, `method`: versioned provenance of the *heuristic* and explicit `hasSemanticUnderstanding: false`, `humanApprovalRequired: true`.
- `source`, `provenance`: source SHA-256, original stream timebase, source run manifest SHA-256, catalog technique revisions and hashes.
- `availableEvidence`: which measured stages actually exist in the verified run.
- `candidates[].techniqueId`: a real, validated **catalog** technique ID, never a fabricated Kumiki UI component ID.
- `candidates[].sourcePtsRange` and `.evidence`: measured start/end integer PTS, artifact path and quantitative sample statistics. Convert PTS to seconds with the source timebase, not an assumed FPS.
- `candidates[].plausibleAlternatives`: competing explanations that the measurements cannot disambiguate.
- `candidates[].reviewQuestions`: specific checks for an editor, motion designer, cinematographer or optional vision model.
- `candidates[].interpretationStatus`: always `review-required-not-verified`. There is no automatic promotion or grade.

### How a coding agent should use this

1. Verify the JSON and its run/catalog hashes. Load the referenced source frames/contact-sheet at the exact PTS to see what the measurements describe.
2. Decide whether the actual visual content supports the named technique. State *observation*, *hypothesis*, *story purpose* and *authored implementation choice* separately. Do not convert image-plane scale directly into CC1 camera travel or a bright pixel centroid into a 3D light path.
3. If a technique is relevant, read its canonical catalog entry's `intent`, `mechanism`, `recipe`, `parameters` and `qa`. Resolve actual Kumiki UI capabilities from its current repository before authoring an adapter/treatment.
4. Implement an original render in Kumiki. Compare the render with the source using `compare-frames` and optionally `compare-appearance`, with manually verified time anchors. Review at full motion, not just a single image.
5. Keep the source research proposal immutable. Record human review, actual render evidence and production-ready status via the catalog's separate promotion process.

## Scope of future work

- Replace hard-coded cue-rule mapping with a versioned, reviewable rule registry, preserving numeric thresholds and synthetic ground truth tests.
- Shot segmentation, optional subject identity, localized highlight tracks and image-motion stabilization are needed before more specific camera and lighting candidates can be responsibly proposed.
- Learn from accepted/rejected reviewer labels, while retaining deterministic reproducibility and marking model-based uncertainty separately.
- Future techniques such as match-on-action, anticipation/impact/settle, visual metaphors and comprehension pacing require temporal/semantic evidence beyond these simple 2D descriptors.
