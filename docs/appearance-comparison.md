# Reference versus Kumiki render: appearance comparison baseline

The `compare-appearance` command compares **two measured appearance reports**,
not the original pixel frames or subjective film craftsmanship. Use it to
find measurable mismatches and identify timecodes that deserve visual review.

```bash
kumiki-ref appearance reference.mp4 --max-samples 24 --out ./runs/reference
kumiki-ref appearance kumiki-render.mp4 --max-samples 24 --out ./runs/render
kumiki-ref compare-appearance \
  ./runs/reference/appearance.json ./runs/render/appearance.json \
  --reference-anchor-ms 0 --candidate-anchor-ms 0 \
  --time-scale 1 --tolerance-ms 150 \
  --out ./runs/comparison
```

Choose the two anchor times by inspecting the reference and generated
contact sheets. For instance, if the corresponding reveal starts 3,000 ms
into the reference and 2,000 ms into the render, supply those values as the
reference and candidate anchors. `--time-scale 1` means equal playback speed;
`--time-scale 5/4` maps one second of candidate footage to 1.25 seconds of
reference time. Do **not** assume two arbitrary videos are synchronized.

The exact mapping is:

`referenceTime = referenceAnchor + (candidateTime - candidateAnchor) × scale`

The comparator uses exact rational source timestamps and a bounded user-set
tolerance; dynamic programming maximizes the number of **monotonic one-to-one**
frame matches, then minimizes absolute timestamp error. Unmatched samples are
counted and preserved, not interpolated or reused.

## Output and interpretation

`appearance-comparison.json` follows the strict
[`kumiki.appearance-comparison.v1` schema](../schemas/v1/appearance-comparison.schema.json).

For each matched reference/render source PTS pair, it records:

| Field | Interpretation |
| --- | --- |
| `signedAlignmentErrorSeconds` | Exact rational alignment error, including direction |
| `meanLumaProxyDelta` | Change in display-referred brightness proxy |
| `meanRgbDistance` | RMS normalized difference of average encoded RGB channels |
| `spatialGridLumaMae` | Mean absolute brightness-proxy difference across nine 3×3 regions |
| `hueHistogramTotalVariation` | Half the L1 distance between measured hue-bin fractions |
| `meanSaturationDelta` | Difference in mean encoded-RGB saturation proxy |
| `brightPixelFractionDelta` | Difference in proportion of bright pixels |
| `chromaticPixelFractionDelta` | Difference in proportion of chromatic pixels |

The summary is descriptive: average absolute luma difference, average RGB
distance, median 3×3 spatial luma difference and average hue difference.
`qualityVerdict` is intentionally `not-performed` because **numerical color
similarity cannot establish premium composition, story clarity, cinematic
craftsmanship, material accuracy or licensed content equivalence**. A perfect
match of global histograms could still conceal completely different images.

Both report SHA-256 hashes and the source hashes **declared in those reports**
are recorded. Comparison does not independently re-open the original videos.
Malformed/nonfinite measurements, inconsistent source PTS, invalid alignment
scales and oversized inputs are rejected. If no pair aligns within tolerance,
the output explicitly reports `no-aligned-pairs` and has a null summary.

## Next comparison layers

1. Render aligned side-by-side frame sheets, with reviewer-selected crops.
2. Compare **tracked** subject or region trajectories at aligned times.
3. Add composition, foreground masks, edge and perceptual difference metrics
   after clarifying reference/resizing/color-space assumptions.
4. Associate each defect with a catalog technique and a specific Kumiki
   implementation parameter, then optimize within bounded budgets.
5. Record full-motion human review before promoting a technique as production-ready.
