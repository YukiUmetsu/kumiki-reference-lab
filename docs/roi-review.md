# ROI tracking visual review

`review-roi` makes a **read-only offline QA gallery** of tracker-reported ROI rectangles
on actual decoded source frames. It does not run object recognition, infer
hidden positions, validate a named subject's identity, or approve an artistic
render. It accepts either the original `kumiki.roi-track.v1` output or the
opt-in manually reseeded `kumiki.roi-track.v2` output.

```bash
kumiki-ref track-roi reference.mp4 --box 0.19 0.22 0.15 0.20 \
  --out ./runs/roi
kumiki-ref review-roi reference.mp4 ./runs/roi/roi-track.json \
  --out ./runs/review --max-frames 8
```

Open the returned `index.html` locally. The gallery shows up to 12 selected
frames (default 8): first/last, start/loss/cut/reseed transitions, then other
samples for temporal context. Images are actual FFmpeg-decoded RGB frames at
their **original source PTS**, checked against recorded sample ordinals and
the source stream timebase. No re-timing or interpolated boxes are used.

- Teal/colored rectangles indicate a position **reported by the tracker**, not
  an independently reverified appearance match. The review checks internal
  displacement, local search-radius and segment consistency, then displays
  the claimed box on a separately PTS-verified source frame. Missing
  observations intentionally have **no box**.
- For v2 reseeded tracks, colors and `segment N` labels distinguish separate
  manual segments. Different segments are **not verified as the same physical
  object** even if boxes appear visually similar.
- The source file hash, stream, timebase and exact frame PTS must agree with
  the track report. Inconsistent timestamps, forged out-of-frame coordinates
  and altered source media are rejected.
- The review is atomically published as `roi-review-<source>-<settings>` with
  lossless PNGs, a copy of `roi-track.json`, `index.html` and a manifest whose
  inventory checks all file hashes on reuse. Changed settings or reports get a
  new folder. Corrupted review bundles are never silently overwritten.
- The manifest is `kumiki.roi-review.v1`, with `humanReviewStatus: unreviewed`
  and `qualityVerdict: not-performed` until a separate human judgment occurs.

No internet, model downloads, GPU, browser renderer or paid service is needed.
This is a bounded FFmpeg + Python standard-library review stage. The review
does not change source footage or commit any source media to Git.
