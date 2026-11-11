# Lightweight frame-by-frame agent review with Magnitude

This workflow is designed for **small local vision models** and text-only coding
agents. Video retrieval uses the existing generic public-HTTPS extractor, with
no website/provider allowlist; unsupported or protected sites may still fail.
Use only media you are authorized to download and analyze.

## Architecture

1. **No AI needed for measurement.** FFmpeg scans every decoded frame within
   configured time/frame budgets, recording timestamp, luminance, color, change,
   and probable cut evidence. Optionally, a low-resolution PNG is produced for
   EACH frame and saved in local ignored workspace.
2. **Tiny visual tasks.** Magnitude receives only one frame or an adjacent pair,
   and one short prompt focused on ONE category. Outputs are capped at 180 tokens,
   and plain-text answers are accepted as low-confidence proposals. This is much
   easier for smaller models than asking for whole-video semantic descriptions.
3. **Evidence export.** Every successful proposal is timecoded, stored locally,
   and exported as JSON to Git. Images and the downloaded video never enter Git.

Magnitude uses the local OpenAI-compatible endpoint
http://127.0.0.1:10100/inference/v1/chat/completions.
Load an image-capable model in Magnitude; text-only models cannot inspect pixels.
No hosted source URL is passed to the local model.

## Prepare all decoded frames

From the repository root (install FFmpeg and yt-dlp first):

    pip install -e .
    kumiki-watch 'https://creator.example/watch/reference' \
      --repo . \
      --rights-basis written-permission \
      --rights-note 'Owner explicitly authorized downloading for this study.' \
      --acknowledge-rights \
      --review-frames \
      --max-seconds 180 --max-frames 10800 \
      --width 192 --height 108

The command deletes downloaded video bytes on success AND failure, writing
numeric data under research/analysis/online-videos/<source-id>.json.
It creates locally retained, Git-ignored previews at:

    workspace/frame-review/<source-id>/
      index.html
      manifest.json
      frames/frame-000000.png
      frames/frame-000001.png
      ...
      annotations.json                # appears after annotation

The default preview disk budget is 256 MiB (override with
--max-review-bytes). Frames stay on the local computer until cleanup.
Do not add workspace/ to Git. The source-id is the JSON filename stem
printed by kumiki-watch.

## Look at one frame at a time

    REVIEW='workspace/frame-review/<source-id>'

    kumiki-frames show --workspace "$REVIEW" --index 0
    kumiki-frames next --workspace "$REVIEW" --after 0 --mode every
    kumiki-frames next --workspace "$REVIEW" --after 0 --mode changed --min-change 0.08
    kumiki-frames next --workspace "$REVIEW" --after 0 --mode cuts
    kumiki-frames next --workspace "$REVIEW" --after 0 --mode interval --interval 24

Each short JSON response includes imagePath, previousImagePath,
nextImagePath, timestamp, color and change evidence, and cut-candidate status.
An image-capable coding agent can open that exact imagePath with its image
tool. A text-only agent can navigate numeric evidence but cannot reliably
classify visual characters or fonts.

For human checking, open workspace/frame-review/<source-id>/index.html locally
and use the arrow keys or slider for frame-by-frame viewing.

## Run one small Magnitude request

Confirm the active Magnitude model ID in the app or API:

    curl -s http://127.0.0.1:10100/inference/v1/models

    kumiki-frames infer \
      --workspace "$REVIEW" --index 120 \
      --category typography \
      --model 'MAGNITUDE_VISION_MODEL_ID'

    kumiki-frames infer \
      --workspace "$REVIEW" --index 121 \
      --category animation \
      --model 'MAGNITUDE_VISION_MODEL_ID'

Supported categories: animation, typography, character, camera, lighting,
composition, visual-style, transition, material and other. One call asks
one short visual question; motion tasks pair only adjacent frames and do not
compare across candidate cuts. --no-save returns an uncommitted preview.

## Shot-aware review and original Kumiki technique proposals

The `--mode shots` option uses deterministic provisional shot grouping to
select representative frames rather than spending the whole model budget
on opening frames. The `kumiki-insights` and `kumiki-catalog` commands
combine evidence with draft animation recipes and cross-video search.
See [temporal cinematic intelligence](temporal-cinematic-intelligence.md).

## Automatically run a bounded scan

    kumiki-frames scan \
      --workspace "$REVIEW" \
      --model 'MAGNITUDE_VISION_MODEL_ID' \
      --categories animation,typography,character,visual-style \
      --mode changed --min-change 0.08 \
      --max-calls 24 --max-failures 3

The scanner prioritizes changed frames, sends narrow prompts one by one,
saves each successful annotation, skips already annotated frame/category
pairs, and stops at the defined budget. It exports timecoded JSON automatically.
Repeat the command to continue. Use --after N, --mode cuts, or --mode interval
to explore different sections. Not every movement needs a model call.

Static but visually important scenes might be missed in changed-only mode,
so use an interval pass as well.

## Annotate without a model, export, clean

Image-capable agents can also describe frames themselves:

    kumiki-frames annotate \
      --workspace "$REVIEW" --index 95 --end 100 \
      --category animation \
      --description 'White title slides left to center.' \
      --evidence 'Visible movement between frame 95 and 100.'

    kumiki-frames export --workspace "$REVIEW"
    kumiki-frames cleanup --workspace "$REVIEW"

The export lives in
research/analysis/online-videos/<source-id>.frame-notes.json.
Only source hashes, timecoded annotations, categories, evidence and
explicit unreviewed statuses enter Git, never video/still bytes.

Cleanup deletes only that validated Git-ignored preview workspace, not
the original numeric evidence or exported notes.

## Research quality limits

- All style and character descriptions are unreviewed local-model hypotheses.
  Low confidence is not a calibrated reliability score.
- Exact font names, physical cameras and lights, production techniques,
  personal identities, dialogue and precise character trajectories are not
  established by these small-model frame observations.
- Downsampled previews are cheap but can obscure small lettering and details.
  The local decoder supports increased dimensions within its safety limits.
- Frame timestamp fields are FFmpeg decoder PTS, not independently verified
  original source packet PTS.
- Resource limits still bound the number of decoded frames and video duration.
- Magnitude requires an image-capable model that supports OpenAI-compatible
  image inputs on your installed version; compatibility should be smoke-tested
  with one frame before large scans.
