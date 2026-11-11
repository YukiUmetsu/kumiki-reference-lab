# Review and evaluate local character vision proposals

**New:** `review-character-vision` regenerates true source-PTS video frame PNGs and the exact detector-proposed character crops used by local visual inference, alongside its unverified descriptions and motion-action hypotheses. The gallery is a local, offline HTML artifact. A separate `character-vision-feedback` command summarizes explicit human assessments. These two stages **never automatically approve** a generated claim.

## Usage

After [local-character-vision](local-character-vision.md) generated `character-scene.json` and `character-vision.json`:

```bash
PYTHONPATH=src python -m kumiki_reference_lab review-character-vision \
  ./authorized-video.mp4 \
  ./runs/people-tracklets/subject-tracklets.json \
  ./runs/local-character-vision \
  --scan-seconds 20 --out ./runs/character-qa

# Open runs/character-qa/index.html locally; review the pictured pixels,
# generated appearance descriptions and 2-frame motion evidence.

# Edit runs/character-qa/review-feedback.json:
# - replace reviewer.id "unassigned" with your review ID
# - for each appearance: pending / supported / unsupported / unclear
# - for action proposals: pending / supported / unsupported / unclear
# - no-action proposals keep actionVerdict "not-applicable"
# - add notes on failures (wrong subject, crop, camera motion, occlusion, etc.)

PYTHONPATH=src python -m kumiki_reference_lab character-vision-feedback \
  ./runs/character-qa/review-feedback.json \
  ./runs/local-character-vision/character-vision.json
```

## Provenance and review semantics

- The vision manifest must match the precise source-bound `subject-tracklets.json` SHA-256; character scene, tracklets, video stream, source timebase, original video SHA and every referenced PTS/box are cross-checked.
- Selected real frame ordinals and source PTS are verified through the existing FFprobe/FFmpeg decoder. Missing or ambiguous source timestamps fail rather than silently selecting a nearby frame.
- One original frame and one subject crop are shown for every model observation. Model text is HTML escaped; no external scripts, network assets or accounts are involved.
- Cropped frames are stored **in this explicitly requested review bundle**, unlike normal `local-character-vision` inference, which discards them. Treat raw video images and potential recognizable people as private and do not commit review PNGs to GitHub without rights.
- The created feedback file starts **all verdicts pending**. For a model report that abstained with `observedAction=none`, action review is `not-applicable`. A real reviewer ID is required before recording verdicts; no unassigned approvals.
- Reported support rates use only explicitly human-marked **supported / unsupported** cases. Pending and unclear labels do not count as success or failure. An empty review yields null rates, not a claim of 0% or 100% accuracy.
- Rates are **not benchmark accuracy**: the sample is not random, reviewer assertions are not independently verified, and the tool does not measure missed characters/actions, detector false negatives or agreement between reviewers.
- No new or changed source files, reviewer judgments, or semantic conclusions are published automatically. Reviewer identity is self-declared, not authenticated.

## What to check visually

For each character/frame: Does the crop depict the intended subject? Are clothing, hair, accessories and character type correctly described? Are claims invented from a blurry or occluded crop? For each action: Does the *two-frame* evidence show the named motion, or could camera movement/compositing explain the difference? Are fast gestures too subtle at 320×180 resolution? Are tracklet IDs mismatched across cuts?

Repeated evaluation on an intentionally varied human-reviewed cohort should guide which local model, crop size, prompt and sampling strategy best support Kumiki production-level storytelling. **Do not equate view counts on What Ships with visual annotation quality or claim to have analyzed its media without source footage.**
