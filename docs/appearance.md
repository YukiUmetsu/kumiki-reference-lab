# Measured video appearance: color, contrast and highlight proxies

Run with optional NumPy and installed FFmpeg/FFprobe:

```bash
kumiki-ref appearance reference.mp4 --max-seconds 10 --max-samples 24 --out ./runs/appearance
```

The output `appearance.json` uses the strict
[`kumiki.appearance.v1` schema](../schemas/v1/appearance.schema.json).
Its RGB evidence comes from selected frames with original source PTS verified
by both FFprobe and FFmpeg. Sampling is uniform in presentation time,
not nominal FPS; pairs crossing cut *candidates* have null change metrics.

To include appearance in a checksum-verified atomic bundle, run
`kumiki-ref analyze reference.mp4 --appearance --appearance-samples 24 --out ./runs`.
Opting in changes the run's settings hash and includes a versioned artifact
record. Existing runs without this option retain their original identity.

## Measurements at each source timestamp

| Field | Meaning | What it does **not** establish |
| --- | --- | --- |
| `meanRgb` | Mean RGB' channel levels normalized to [0,1] | Color-managed display accuracy or scene illumination |
| `meanLumaProxy`, `medianLumaProxy`, `lumaP10`, `lumaP90` | Non-linear Rec.709-weighted RGB' brightness proxies | Physical luminance, exposure stops, or HDR peak nits |
| `lumaContrastP90MinusP10` | Difference between 90th and 10th percentile brightness proxies | True scene dynamic range |
| `shadowPixelFraction`, `brightPixelFraction` | Pixels below 0.15 or above 0.85 brightness-proxy thresholds | Shadow/light sources or clipping without source color management |
| `brightPixelCentroid` | Spatial center of at least ten bright pixels | Actual light position, reflection cause, or subject identity |
| `meanSaturation`, `chromaticPixelFraction` | RGB max/min saturation proxy; visibly colored pixel fraction | Camera white balance or material pigment |
| `hueHistogram12` | 12 hue bands among chromatic pixels, sum approx. 1 when present | A perceptually uniform color space or semantic palette |
| `dominantRgbBins` | Top five coarse 6×6×6 RGB code-value bins with pixel fractions | A professionally curated palette |
| `spatialGrid3x3` | Coarse spatial luma mean, variation and bright coverage | Segmentation, depth or actual lighting design |

Pairwise `changes` expose consecutive-source-time deltas for mean RGB, mean
brightness proxy and hue histogram total variation. Edits are never blended
into a purported continuous lighting animation; `cut-boundary` means no
change is estimated across the cut candidate.

## Global brightness ramps and possible fades

`lumaRampCandidates` is an additional, *review-only* timeline of sampled
brightness transitions. It requires at least four consecutive observations,
each step moving mean luma by at least 0.025 in one direction, with at least
eight of nine spatial grid cells changing by 0.012 in the same direction.
The observed total luma change must reach 0.20 over at least 0.2 seconds.
Runs stop at cut candidates,
reversals or unsupported intervals; timestamps and durations come directly
from original source PTS.

- `fade-to-black-candidate`: coherent darkening ending at or below 0.12 luma.
- `fade-from-black-candidate`: coherent brightening starting at or below 0.12.
- `global-brightness-ramp-candidate`: coherent darkening/brightening without
  evidence of a black endpoint.

These are **global pixel-change patterns, not verified edit effects**. A camera
exposure adjustment, lighting cue, animated opacity, color grade, or even a
large moving subject can reproduce them. Sampled start/end PTS do not prove
where a transition began or ended between samples. Moving highlights that
affect only a few spatial cells and one-frame brightness jumps are not
automatically called fades. This stage does not classify dissolves or match
underlying shots.

## Five-frame linear image-blend candidates

`imageBlendCandidates` describes sampled windows where three intermediate RGB
frames closely resemble a **time-weighted linear mix of two distinct endpoint
images**. The model uses the five frames' actual source PTS to choose blend
weights, never nominal frame indices. It requires at least 0.2 seconds of
observed duration; textured and substantially different endpoints (RGB RMS
difference at least 30 code values, mean of per-channel spatial standard
deviations at least 18, endpoint correlation no greater than 0.8); and intermediate
prediction error at most 8 RGB code values RMS and 16% of the endpoint
difference. No candidate may cross a hard-cut candidate. Overlapping windows
are reduced to the lowest-residual evidence window without reusing frames.

`linear-image-blend-candidate` is **not proof of an editorial dissolve**.
Animated opacity, layered graphics, a digital overlay, and color/compositing
effects can produce the same pixels. It specifically does not recover the
source layers or exact transition endpoints. Nonlinear blends, moving
underlying shots, a camera pan, fades to black and short or sparsely sampled
transitions may be rejected or missed. Residual metrics are deterministic
image-code differences, not perceptual quality scores or confidence
probabilities. Review the actual sampled frames before inferring anything.

### Example: design analysis, not inverse-rendering

An increasing `brightPixelFraction` with a moving `brightPixelCentroid`
could suggest a highlight sweep. It could equally be a moving white graphic,
subject, light, camera, exposure adjustment, or multiple visual elements.
Treat it as a useful **research cue**, not a confirmed cinematic technique.
Compare contact-sheet frames, write hypotheses with source timecodes, and
validate the proposed mechanism in a new Kumiki scene.

## Reproducibility and limitations

- The 8-bit `rgb24` planes are converted by FFmpeg; the method does not
  establish camera primaries, transfer functions, mastering metadata, scene
  linear light, HDR signals or physical scene photometry. `luma` fields
  approximate display-referred RGB' brightness.
- Hue bins and palette buckets are code-value descriptors, not perceptually
  uniform palette matching; compression and display transforms affect them.
- No image or source video is committed; the report includes source hash,
  stream index, rational timebase, binary names and a method version.
- Default compute cap: 24 samples at 160×90 within 10 seconds; hard limits:
  40 samples, 240×135 pixels and a 20-second video prefix.
- Next: align appearance observations with tracked subjects, detected shots,
  audio beats and human-reviewed lighting/mood hypotheses. Only after that
  should a creative treatment propose area lights, environment maps, effects,
  grading, or color keyframes for `kumiki-ui`.
