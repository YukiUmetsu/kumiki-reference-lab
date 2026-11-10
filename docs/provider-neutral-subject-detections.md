# Provider-neutral subject detections and provisional tracklets

**Implemented:** `subject-detections` accepts timestamped bounding boxes from a **separately run local detector** and conservatively associates them within consecutive sampled frames. It can handle live-action people, animated characters, animals and other subjects, provided the detector uses the normalized input contract. The command does **not** run a model or automatically download weights.

## Data flow

1. Obtain an authorized local video and run a local detector (for example, an ONNX runtime or vision-language pipeline whose model weights/license you have independently evaluated). Export source-video PTS, category, normalized bounding box and model-proposed score for each sampled frame.
2. Use the [synthetic example](../examples/subject-detections.synthetic.example.json) as a format template. Replace its **all-zero placeholder SHA-256** with the SHA-256 of the *actual* video, plus the actual video stream index, timebase, source PTS, cut candidates and detections. It is not a real film observation.
3. Run the adapter:

```bash
PYTHONPATH=src python -m kumiki_reference_lab subject-detections \
  ./authorized-reference.mp4 ./detections.json \
  --min-iou 0.35 --ambiguity-margin 0.10 --min-score 0.25 \
  --out ./runs/subject-tracklets-01

PYTHONPATH=src python -m kumiki_reference_lab character-scene report \
  ./runs/subject-tracklets-01/character-scene.json
```

Output files: `subject-tracklets.json` (all input/association proposals and uncertainties) and `character-scene.json` (provisional character roster and one-tick sampled appearances, with empty actions/dialogue). Both are published atomically in a new directory.

## Input schema

Required JSON fields: `schemaVersion` (`kumiki.subject-detections.v1`), `sourceSha256`, `sourceStreamIndex`, `sourceTimebase` (`numerator`, `denominator`), `detector` (`name`, nullable `modelSha256`), `cutCandidatePts` and `frames`. Each frame has `sourcePts` and zero to eight `detections` with exact `category`, `score`, and `box` fields. The source has 2–120 monotonically increasing sampled frames covering up to 120 seconds. Categories: `person`, `animated-character`, `animal`, `anthropomorphic`, `other-subject`. Scores and boxes are finite and normalized in [0, 1]. Nearby duplicate same-class boxes must be deduplicated by the detector.

The adapter validates the declared source hash, video stream and rational timebase against an **actual local media file** using the existing `inspect_source` functionality. The output records the detection JSON SHA-256 for provenance. It does not read an X/What Ships/YouTube browser watch URL as video bytes.

## Identity and uncertainty policy

- **Each assigned ID is a tracklet, not a verified individual or character identity.** Local IDs such as `subject_001` identify contiguous image detections, and should not be reinterpreted as a unique person over an entire film.
- Within adjacent frames, association uses mutual-best bounding-box intersection over union (IoU), requiring the strongest candidate to exceed the chosen margin over competitors on **both** sides.
- A missing frame, filtered/absent detection, supplied hard-cut boundary, or ambiguous match breaks continuity. New tracklet IDs explicitly **do not** establish that a new person appeared.
- Cuts are supplied by the caller, not independently confirmed by this stage. A missing cut candidate may allow a false cross-shot match, so pair this adapter with Reference Lab's measured cut-candidate timeline and review uncertain transitions.
- The mapping from detector categories to `character-scene` kinds is **model-proposed**, not independently reviewed. Detector confidence is neither calibrated probability nor evidence of gender/age/ethnicity.
- Outputs **never invent gestures, emotion, gaze, dialogue or identity claims**. Visual descriptions only state that a detector proposed an image region.
- The character scene's appearance intervals span one source-PTS tick at a sampled frame; they are not assertions of continuous onscreen presence or exhaustive coverage.
- The implementation retains no media frames or downloaded models. It is useful for downstream human or model-assisted QA, not yet a finished cinematic character understanding model.

## Next priority

Add an optional local inference plugin with explicit weight provenance, macOS Apple Silicon acceleration where supported, licensed model compatibility and frame/PTS capture. Then calibrate detector quality on both animated and live-action subjects, add scene-cut and occlusion tests, and layer action/gesture hypotheses separately from geometric tracking.
