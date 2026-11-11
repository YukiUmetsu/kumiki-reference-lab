# Shot-aware temporal study and motion proxies

This feature builds **new evidence from existing online frame-review workspaces**.
It never downloads another video and does not require Magnitude, NumPy or
OpenCV. The input remains the source-hashed numerical report plus the optional
Git-ignored low-resolution PNG previews created by kumiki-watch.

## 1. Acquire authorized media and preserve temporary review previews

From the repository root, with ffmpeg and yt-dlp installed:

    kumiki-watch 'https://creator.example/reference' \
      --rights-basis written-permission \
      --rights-note 'Permission supplied by owner.' \
      --acknowledge-rights --review-frames \
      --max-seconds 180 --width 192 --height 108

The downloaded **source video is deleted automatically**. The stored
reference remains research/analysis/online-videos/<source-id>.json, and
the small preview images remain in ignored
workspace/frame-review/<source-id>/ until explicit cleanup.

    REVIEW='workspace/frame-review/<source-id>'

## 2. Inspect candidate shots

    kumiki-frames shots --workspace "$REVIEW" --shot-limit 12
    kumiki-frames shots --workspace "$REVIEW" --shot-after 11 --shot-limit 12

Each page returns shot-candidate time spans, incoming cut boundary, local
frame indices, measured brightness and temporal-difference statistics, a
stable-ish appearance sample, a motion peak, and a short list of suggested
review frames. This **does not establish** true semantic scenes or verified
editorial cuts: flash frames, rapid foreground motion and dissolves can
produce incorrect boundaries.

Navigate straight to the next useful frame:

    kumiki-frames next --workspace "$REVIEW" --mode shots --after 0

## 3. Reconstruct sparse image-plane motion from local frames

    kumiki-frames motion --workspace "$REVIEW" \
      --max-motion-pairs 96 \
      --motion-stride 8 \
      --search-radius 3

This produces *only structured evidence JSON* at:

    research/analysis/online-videos/<source-id>.temporal.json

It contains:
- Source SHA-256, decoded frame count and grouped cut boundaries.
- For each shot: start/end frame and decoded time, mean/peak frame difference,
  low-change and high-change fractions, luminance and review frame indices.
- For each sampled adjacent frame pair: block-matched dominant image-plane
  displacement in **original preview pixels**, region texture/error/gain
  proxies, coherence, exceptional regional residuals, and velocity proxy
  when the displacement is sufficiently coherent.
- Explicit limitations separating measurable image-plane motion from inferred
  camera movement, identity tracking or physical production technique.

The processor uses a fixed 4x3 spatial grid, 5x5 grayscale patches, bounded
pixel search and median vector consensus. Regions with inadequate texture
abstain; strongly disagreeing regions are exposed as residual evidence.
This is deliberately inexpensive and auditable, not a learned optical-flow
model or a complete trajectory solver.

**Important:** Pixel velocity is between *adjacent decoded frames at sampled
positions*. It cannot be integrated into continuous object trajectories, and
the program never labels dominant motion as a verified dolly, pan or camera move.
To study more motion detail, raise --max-motion-pairs, lower --motion-stride,
and increase preview resolution in the initial capture. This increases CPU and
I/O. The default budget is just 96 pairs.

## 4. Focus small Magnitude models on shots, not arbitrary frames

    kumiki-frames scan --workspace "$REVIEW" \
      --mode shots \
      --categories animation,typography,visual-style \
      --model 'MAGNITUDE_VISION_MODEL_ID' \
      --max-calls 24 --max-failures 3

The scan uses stable and high-change frames suggested by the shot plan. Each
call still asks Magnitude only ONE short question using at most two adjacent
frames. Re-run the command to resume unannotated frame/category pairs.
The original --mode changed, --mode cuts and --mode interval continue working;
use interval review for visually rich static sections.

## 5. Save descriptions and remove previews

    kumiki-frames export --workspace "$REVIEW"
    kumiki-frames cleanup --workspace "$REVIEW"

Exported annotations and temporal estimates stay in research/analysis/
online-videos/. The cleaned local PNG files do not. Analysis provenance is
always tied to the media content SHA-256, not just the mutable watch URL.

## Limitations and quality checks

- No claim of persistent character IDs, object masks, deformable tracking,
  rotation, optical flow or animation-curve reconstruction from this evidence.
- Camera motion, foreground motion, zoom and scene edits are NOT reliably
  disentangled using block matching alone. Coherent translation is only
  an image-plane statistic; residuals suggest where independent motion
  *might* be worth investigating.
- Shot boundaries are grouped candidate cuts, not independent ground truth.
- Motion estimates are low-resolution and limited to a local search radius.
  Faster movement, repeated patterns, low texture and camera shake can cause
  incorrect estimates or abstention.
- Sampled pairs are not full-speed optical flow. Easing inference needs
  longer continuous validated tracks and should not be claimed from this data.
- PTS is FFmpeg's decoder timestamp, not independently source-verified PTS.
- Screenshots and reference footage remain uncommitted. Never redistribute
  source media or infer that public visibility grants download permission.

The next layer can use the shot plan to drive persistent original-asset
tracking, OCR, richer motion/easing estimation and Kumiki animation recipes.
Those are not implemented by this module.
