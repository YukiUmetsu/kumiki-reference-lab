# Manual ROI restarts after occlusion

The existing `track-roi` tracker deliberately stops when a textured patch
disappears, becomes ambiguous, or crosses a hard cut. To review footage where
the patch later reappears, supply **explicit** additional rectangles at exact
source presentation timestamps (PTS). This is manual observation segmentation,
**not automatic re-identification, semantic tracking, or inferred motion through
an occlusion**.

## Workflow

1. Run an initial `track-roi` analysis with `--max-samples` and `--max-seconds`
   chosen for your source. Inspect the `sourcePts` values in `roi-track.json`.
2. Choose an observation with a visible textured patch and note its **exact**
   integer `sourcePts`; `sampleOrdinal`, seconds, and nominal FPS are not PTS.
3. Write a JSON list such as:

   ```json
   [
     {"sourcePts": 700, "box": [0.275, 0.3, 0.15, 0.2]},
     {"sourcePts": 1100, "box": [0.32, 0.33, 0.15, 0.2]}
   ]
   ```

   Replace the example timestamps and rectangles with those for your source.
   The values are normalized `x, y, width, height` on each *reseeded frame*.
4. Rerun with identical time/sample/resolution settings:

   ```bash
   kumiki-ref track-roi reference.mp4 --box 0.19 0.22 0.15 0.20 \
     --max-seconds 10 --max-samples 48 --reseeds roi-reseeds.json \
     --out ./runs/roi-reseed
   ```

   To include this in a checksum-verified analysis bundle:

   ```bash
   kumiki-ref analyze reference.mp4 --out ./runs --box 0.19 0.22 0.15 0.20 \
     --max-seconds 10 --max-samples 48 --roi-reseeds roi-reseeds.json
   ```

The file must be UTF-8 JSON, at most 32 KiB, with 1–16 anchors in strictly
increasing PTS order. Each timestamp must exactly match a **selected** frame
after the first sample. A timestamp from an unsampled frame is rejected: change
`--max-samples`, inspect new PTS, and update the anchors. Boxes must meet the
usual normalized/grid-size/compute limits and contain measurable texture;
invalid anchors fail the whole run before output publication.

## How to read the evidence

- `seeded` indicates the first segment; `manual-reseed` indicates the start
  of each subsequent one, with `segmentIndex` 0, 1, 2, etc.
- Positions and displacement are reported only on verified observations.
  Lost/hidden observations retain `boxPixels: null`, `segmentIndex: null`;
  no invisible path is interpolated.
- `displacementPixels` restarts at `(0, 0)` for each new segment. A changed
  rectangle or patch cannot be compared to the previous segment as a
  continuous displacement.
- `analyzer.manualReseeds` records the exact user-supplied anchors, and
  `identityLinkStatus: not-established` explicitly denies cross-segment
  identity verification. Reviewers can hypothesize a shared identity but
  this artifact does not establish one.
- Without `--reseeds`, the strict v1 artifact shape and analysis-run identity
  are unchanged. With reseeds, the tracker reports `kumiki.roi-track.v2` and
  the analysis bundle reports `kumiki.analysis-run.v2`, using schemas in
  `schemas/v2/`. Immutable run settings include the anchors; changing an
  anchor creates a distinct run rather than reusing older data. Older strict
  v1 validators continue to accept default outputs without modification.

Limitations: repeated textures, rotation, shape changes, low resolution and
partial occlusion can fool or stop template correlation. This feature does not
segment visible object parts or establish that two separate patches belong
to the same subject. No source media or model weights are downloaded.
