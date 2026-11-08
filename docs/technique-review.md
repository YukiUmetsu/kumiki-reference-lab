# Visual review of technique cues

The **`review-techniques`** command generates an immutable, local HTML gallery for conservative camera/lighting *review cues*. It draws start, nearest-middle and end JPEG frames from the actual input video at independently verified original PTS. The gallery places each cue's numeric measurements beside competing explanations and specific cinematography questions. It cannot certify a premium render or infer physical rigs.

## End-to-end workflow

```bash
# 1. Create immutable measured reference artifacts.
kumiki-ref analyze reference.mp4 --max-seconds 10 --sparse-flow --appearance --out runs/

# 2. Optional: export machine-readable hypotheses for coding agents.
kumiki-ref propose-techniques runs/analysis-<source>-<settings>/analysis-run.json \
  --out runs/cue-analysis-r001/

# 3. Render a self-contained HTML/JPEG review gallery.
kumiki-ref review-techniques reference.mp4 \
  runs/analysis-<source>-<settings>/analysis-run.json \
  --catalog-root catalog/entries --max-cues 8 --width 480 --out runs/
```

The last command prints the path to `index.html` in an immutable `technique-review-<source>-<settings>/` directory. Open it locally. `--max-cues` is 1–8. Use `--cue-offset 8` (then `16`, `24`) to review later cues in chronological order. If no cues pass the numerical gates, the gallery explicitly says so, without claiming no techniques exist.

## Integrity and precision

1. The command verifies the complete analysis run checksum inventory, catalog entry hashes and proposed cue provenance **before** decoding images.
2. It independently probes the supplied `reference.mp4` and requires source SHA-256, stream index and timebase to match the analysis. A different source, including visually similar footage, is rejected.
3. For each cue, its start/end must match actual decoded PTS. The middle is chosen from the available decoded frames by smallest PTS distance to the interval's midpoint (ties go earlier). Three timecoded views help evaluate visual change; they are **not** a recovered keyframe sequence.
4. The FFmpeg thumbnail decoder verifies all selected original PTS against FFprobe. Images are bounded: at most 24 distinct JPEGs, 128–800 px wide, from the run's original analysis window.
5. The gallery saves `index.html`, `technique-proposals.json`, `technique-review.json`, and selected JPEGs with per-file hashes. Reuse validates exact settings, manifest data and hashes; corruption or untracked files cause an error. No silent overwrite and no export to Kumiki UI.

The gallery schema is [`schemas/v1/technique-review.schema.json`](../schemas/v1/technique-review.schema.json). Its `reviewStatus: unreviewed` and `qualityVerdict: not-performed` remain unchanged regardless of how many images are decoded. Any approval is a **separate human decision**, after reviewing full-motion footage and the actual implementation.

## Agent handoff

- Open gallery `index.html` and inspect all three frames for each cue. The `techniqueId` is an authored catalog **hypothesis**, not a recovered shot label. Read its linked catalog entry for mechanism, recipe and QA constraints.
- When evidence supports a useful design principle, add human/AI review notes to a **new review artifact**, not to the immutable measured run or generated gallery.
- Compare any newly rendered Kumiki scene with the source using `compare-frames` at explicit reference/render anchors. Quantitative appearance differences from `compare-appearance` can help, but a human must inspect pacing, silhouette, material fidelity, temporal coherence and teaching clarity at playback speed.
- Do not read source frames or timestamps as proof of physical light positions, focal length, camera tracks, character identity, story intention or editor keyframes.

## Scope and later improvements

The current gallery is deliberately a **three-frame spot-check**, not a full storyboard, an optical-flow visualization, or a time-continuous reproduction. More reliable review will eventually add manually verified shot boundaries, moving subject identities, local highlight tracks, audio timing, timeline playback and persistent human review verdicts. None of those are implied by the current output.
