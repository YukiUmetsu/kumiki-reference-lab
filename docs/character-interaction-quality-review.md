# Review character-to-character interaction proposals

`review-character-interactions` creates a local, offline HTML gallery showing **the two original video frames, with the same red/cyan subject outlines that were supplied to the local vision model**, for every proposed actor–target interaction or abstention. A companion `character-interaction-feedback` command reports human adjudication.

These are evidence-review tools. Source-frame and timestamp verification is **not proof** that the model correctly interpreted an interaction.

## Usage

First run the existing `subject-detections`, `local-character-vision`, and `local-character-interactions` workflow on an authorized local source. New interaction runs contain additional source-render dimensions, maximum pair gap, and original scan-window metadata to enable faithful replay.

```bash
PYTHONPATH=src python -m kumiki_reference_lab review-character-interactions \
  ./reference.mp4 \
  ./runs/subject-tracklets/subject-tracklets.json \
  ./runs/character-vision \
  ./runs/character-interactions \
  --out ./runs/interaction-qa

# Open ./runs/interaction-qa/index.html and compare both source frames.
# In ./runs/interaction-qa/interaction-feedback.json, replace
# reviewer.id="unassigned" with your reviewer ID.
#
# For each numbered pair, choose:
#   supported / unsupported / unclear / pending
# A "supported" abstention means no interaction was apparent in that pair.
#
PYTHONPATH=src python -m kumiki_reference_lab character-interaction-feedback \
  ./runs/interaction-qa/interaction-feedback.json \
  ./runs/character-interactions/character-interactions.json
```

The output is an immutable **new directory**, containing `index.html`, 2 highlighted PNG frames per candidate pair, `interaction-feedback.json` (all verdicts initially **pending**), and `review-manifest.json` with source and manifest hashes. If there were zero eligible pairs, the gallery explains the abstention rather than calling it "no character interactions in this video."

## Evidence and safety

- Original source SHA-256, video stream index and rational timebase must match the detection tracklets, original appearance/action scene and merged directed-interaction scene.
- The interaction manifest must reference the exact tracklet report and base character-scene **file fingerprints**. The original local vision manifest must also match its tracklet boxes, appearance descriptions, action timestamps and counts.
- Each directed action must correspond exactly to a source-PTS pair with both character boxes present in adjacent sampled frames, no intervening reported cut, bounded time gap, and no ambiguous heavy overlap. Actor and target are checked against the red/cyan color markers; a prediction of `none` cannot produce an action.
- Source PTS are individually verified against FFprobe's decoded frame inventory and extracted through the existing PTS-verifying FFmpeg backend. Missing or ambiguous frame timestamps fail, never guessing the nearest frame.
- Images are **created only in this review artifact**, which should remain private if subjects or footage have privacy/copyright restrictions. The original inference pipeline does not save image frames.
- All model-generated evidence text is HTML escaped before displaying it. Source/manifests are checked for changes before publishing the output atomically.
- No credentials, external pages, cloud API, model downloads or paid subscriptions are required. The review stage only reads local data.
- Reports contain **no demographic classification** and do not identify real individuals.

## How to interpret review metrics

The feedback reporter separates **positive interaction proposals** from **model abstentions**, and gives a *decided-only* support rate for each category. Only explicit `supported` or `unsupported` human judgments enter the denominator. `pending` and `unclear` are counted as reviewed/unreviewed metadata, not successes or failures.

A positive support rate is **not precision** on the entire film: candidates were selected non-randomly, there may be hallucinations or missed actions outside those pairs, and human labels are self-declared. An abstention judged supported only says no clear interaction was present in those **sampled frames**. Model performance still needs reviewed live-action and animated clips across multiple camera styles, occlusions, and hard cuts.

The previous `character-vision-feedback` command remains available for individual appearance and single-character action review. Combine its results with this pairwise QA to prioritize improving local prompts/detectors before exporting scenes into Kumiki UI.
