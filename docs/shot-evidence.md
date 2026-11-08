# Candidate edit-region evidence, not automatic storytelling labels

`shot-evidence` combines a verified run's decoded frame PTS, hard-cut *candidates*, and any optional appearance / image-motion / sparse-flow measurements into a compact per-region report for a video editor, cinematic reviewer or future vision model. It is an **offline, deterministic evidence organizer**, not a shot-purpose classifier, story generator or motion director.

```bash
kumiki-ref analyze reference.mp4 --max-seconds 10 --motion --sparse-flow --appearance --out runs/
kumiki-ref shot-evidence runs/analysis-<source>-<settings>/analysis-run.json \
  --out runs/region-report-r001/
```

The result is `shot-evidence.json`, validated against [`schemas/v1/shot-evidence.schema.json`](../schemas/v1/shot-evidence.schema.json). The output names the source SHA-256, stream, original rational timebase, run-manifest hash, detector threshold/limitations and the exact stages present. It reads only the previously verified, checksum-inventoried local bundle. `--out` uses immutable, idempotent JSON artifact publishing; omit it for stdout.

## Boundary semantics

- A `region` is the space between two candidate cut timestamps. A candidate may be a **false positive due to large image movement**; an actual dissolve or quiet cut may be missed. A region is not asserted to be a shot.
- `startPtsInclusive` is the first observed frame at the candidate region's start. `endPtsExclusive` is the next candidate cut's frame PTS, or **null** for the final region. The final region's duration cannot be inferred without a verified next timestamp. `lastObservedFramePts` is always the last actual decoded frame.
- `boundaryBefore` / `boundaryAfter` distinguish `hard-cut-candidate` from `bounded-scan-start` and `bounded-scan-end`.
- Actual frame count and source ordinal ranges are recorded. If any source PTS is missing, repeated, decreasing or flagged anomalous, the stage returns `blocked-unreliable-source-pts` with **no fabricated regions**.
- Cut candidate PTS not present in the decoded frame timeline is an error. Candidates outside the observed frame range are explicitly listed in `ignoredCutCandidatePts`.

## Per-region observation fields

| Field | Contents | Never infer |
| --- | --- | --- |
| `observations.appearance` | Count, source PTS of sampled frames and means of display RGB luma/contrast/saturation/bright-pixel fractions | Light coordinates, dynamic range of the original scene, intentional mood, object materials |
| `observations.motion` | Count of contained sampled pairs, measured/unknown counts, mean magnitude of apparent global displacement **per pair**, normalized to frame dimensions | Physical camera velocity or object path; pair time spacing is not constant |
| `observations.sparseFlow` | Contained pair count, affine-image and translation-sufficient hypothesis counts | Unique camera model, depth, dolly, parallax, lens or semantic object identity |
| `reviewQuestions` | The same prompts for confirming edit boundaries, story purpose and temporal craft | Answers or a claim of viewer comprehension |

An optional stage that was not run appears as `null` in each region. A stage that ran but had no samples in a short region has zero sample count and `null` numeric averages. This distinction is essential when feeding reports into AI or coding agents. Source PTS and original timebase must be used for any cross-stage alignment; do not multiply frame number by nominal FPS.

## Agent review process

1. Identify likely edit regions from `regions[]`; check each boundary visually in the contact sheet/source footage. Do not trust cuts as confirmed edits.
2. Open the underlying appearance, motion and sparse-flow artifacts for precise per-frame data, plus `compare-frames` or `review-techniques` for visual evidence. The summarized averages are *context*, not a replacement for visual review.
3. Add separate semantic notes: what the viewer should learn, focus target, causal action, narration beat, and why the edit or movement matters. These are subjective and cannot be computed from current metrics alone.
4. Reference the Cinematic Techniques Catalog to select an authored recipe. Confirm actual renderer capabilities in Kumiki UI; do not invent component names or use unverified physical light/camera parameters.
5. Render, review at real playback speed, compare against the reference at verified time anchors, and require human approval before any "premium quality" claim or catalog promotion.

Future improvements may add automated audio beat/speech alignment, fade/transition classification, per-subject saliency tracks, reliable shot-boundary verification and optional multimodal semantic interpretation. They should extend versioned artifacts without altering old measurements.
