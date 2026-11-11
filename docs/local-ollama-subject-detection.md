# Automatic provisional subject localization with local Ollama

**New:** `local-character-detect` proposes bounding boxes for stylized 2D/3D characters, anthropomorphic characters, animals, or live-action people from **actual local video frames** using a previously installed Ollama vision-capable model. The output is the existing `kumiki.subject-detections.v1` schema, so `subject-detections`, `review-subject-tracklets`, and `local-character-vision` work without manual bounding boxes or a new downstream data format.

**This is model-proposed localization, not measured detection accuracy.** Vision-language model boxes may be substantially worse than a dedicated detector, particularly for small subjects, motion blur, occlusion, and stylized or partially cropped characters. Always inspect the QA frames.

## Workflow on your Mac

Install FFmpeg/FFprobe, run Ollama locally, and select a **vision-capable model that is already installed**. The repository does not download model weights or use Ollama Cloud. `qwen3-vl:8b` is one possible local model tag; its character localization performance has not been verified.

```bash
ollama list

# 1. Propose actual character boxes, including animated and anthropomorphic.
PYTHONPATH=src python -m kumiki_reference_lab local-character-detect \
  ./authorized-video.mp4 --model qwen3-vl:8b \
  --max-seconds 10 --max-samples 8 \
  --out ./runs/local-subject-boxes.json

# 2. Associate adjacent boxes into cautious, provisional subject tracklets.
PYTHONPATH=src python -m kumiki_reference_lab subject-detections \
  ./authorized-video.mp4 ./runs/local-subject-boxes.json \
  --out ./runs/local-tracklets

# 3. Review bounding boxes against actual source frame PTS.
PYTHONPATH=src python -m kumiki_reference_lab review-subject-tracklets \
  ./authorized-video.mp4 ./runs/local-tracklets/subject-tracklets.json \
  --out ./runs/local-subject-qa

# 4. Generate unverified clothing, look, and two-frame action descriptions.
PYTHONPATH=src python -m kumiki_reference_lab local-character-vision \
  ./authorized-video.mp4 ./runs/local-tracklets/subject-tracklets.json \
  --model qwen3-vl:8b --out ./runs/local-character-vision

# 5. Optionally propose directed interactions between pairs of subjects.
PYTHONPATH=src python -m kumiki_reference_lab local-character-interactions \
  ./authorized-video.mp4 ./runs/local-tracklets/subject-tracklets.json \
  ./runs/local-character-vision --model qwen3-vl:8b \
  --out ./runs/local-interactions
```

For a supported macOS human-region baseline you can still use `mac-vision-humans`; for higher-quality animation detection you can also import local ONNX/detector outputs through `subject-detections`.

## Input/output and uncertainty

- Source frames are selected uniformly over **original video PTS**, not estimated FPS. FFprobe source frame ordinals and FFmpeg-decoded frame PTS must match. The scan is bounded to the first 1–30 seconds, 5–12 selected frames, and up to 320×180 pixels per frame.
- Each sampled PNG is passed to Ollama **only through literal localhost `127.0.0.1`**, using an existing model. No remote URLs, cloud services, media downloads, personal identity recognition, or stored frame images are involved.
- Each model response must be exact JSON `{"subjects":[{"category":"animated-character","box":[0.1,0.2,0.3,0.5]}]}`. Allowed categories are `person`, `animated-character`, `animal`, `anthropomorphic`, `other-subject`. Coordinates are normalized top-left `[x,y,width,height]`, and each box must fit the image. At most eight nonduplicate boxes are accepted per sampled frame. Invalid/ambiguous output fails without writing incomplete results.
- Each output detection receives **score 0.5**, a deliberately *neutral compatibility sentinel*, **not a detector confidence or probability**. The existing tracklet association can use the score for filtering, but must not interpret its numerical value as model accuracy or trustworthy identity.
- The output detector name records the operator-specified local model tag; `modelSha256: null` means the actual model weight digest was not independently verified.
- FFmpeg cut candidates are recorded so the downstream tracker does not blindly re-identify a character after a scene cut. However cut detection is also fallible, and sequential box overlap is not guaranteed identity.
- A video with zero proposed characters is still a valid input. That means **no subjects were confidently localized by this model on the sampled frames**, not that the video contains no characters.
- The model does not provide real names, ages, ethnicity, gender identity, dialogue, actor-target relationships, gestural meaning or emotion. Those are handled separately and must remain evidence-bound or unknown.

## Validation and next steps

Cross-platform mocked regression tests cover animated and anthropomorphic boxes, cut handling, schema/PTS conversion, invalid/out-of-frame boxes, duplicate cross-category detections, no-character abstention, and failed model inference. Native Ollama inference accuracy has **not** been evaluated on real animated What Ships videos.

A meaningful next evaluation is to select a small licensed, varied set of 2D, 3D and live-action clips and manually count matching boxes, missed subjects, false positives, drift across frames and action hallucinations. Prioritize fixing low-resolution localization failures before expecting production-ready multi-character scenes.
