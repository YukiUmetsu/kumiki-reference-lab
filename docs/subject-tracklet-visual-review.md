# Visual QA for provisional character tracklets

`review-subject-tracklets` is an **offline, source-PTS-verified gallery** of external detector proposals on actual decoded source video frames. The gallery is meant for **human verification** of bounding boxes, identity drift, occlusion, and cuts. It does **not** certify that the detector identified real people or the correct fictional characters.

## Workflow

1. Run a local detector on authorized video, convert observations to the [provider-neutral format](provider-neutral-subject-detections.md), and run `subject-detections` to generate `subject-tracklets.json`.
2. Render the matching source frames with bounded local FFmpeg/FFprobe:

```bash
PYTHONPATH=src python -m kumiki_reference_lab review-subject-tracklets \
  ./authorized-reference.mp4 ./runs/tracklets-01/subject-tracklets.json \
  --out ./runs/tracklets-visual-01 \
  --max-frames 8 --scan-seconds 20
```

3. Open `./runs/tracklets-visual-01/index.html` locally. Each selected frame shows the source PTS, source-relative display seconds, boxes, and provisional tracklet IDs. No server or subscription is required.

Outputs: `index.html`, `frames/actual-frame-NNN.png`, and `subject-visual-review.json`. The manifest records source SHA, source video stream, rational timebase, input report SHA, original PTS frame anchors, render resolution and explicit **unreviewed** status. The gallery is an evidence artifact, not a quality verdict.

## What is verified

- The **original local media file** is inspected for SHA-256, video stream and source timebase matching `subject-tracklets.json`.
- FFprobe supplies exact original PTS and decoded frame ordinals. Source timestamps must uniquely match selected detections; absent/duplicate PTS cause failure, never a nearest-frame guess.
- FFmpeg extracts the **same ordinal frames** and its decoded output PTS must agree with FFprobe. The resulting PNGs contain actual sampled source pixels.
- Boxes are overlaid in normalized coordinates on the resized frames. They remain **unverified external detector proposals**.
- The selection prioritizes first/last and both sides of supplied cut candidates, then fills remaining slots across the reviewed range.
- Source and report signatures are checked after decode; output is published atomically into a new directory. Invalid source, altered boxes or failed decoder leaves no partial gallery.

## Important limits

- The source reference must be an authorized **local video**, not a What Ships browser page or a YouTube URL.
- The detector model and its predictions are not independently evaluated. Numeric score is not a calibrated identity confidence.
- A matching box across frames is not a verified character identity, even when its IoU is high. A tracklet ending at a cut is not necessarily a new person.
- The gallery renders up to 12 frames at up to 320×180; it is intended for broad position/cut QA, **not facial expression or lip-motion analysis**.
- `--scan-seconds` is a bounded **source prefix** scan (1–120 seconds). Increase it only when a selected source PTS is outside the scanned interval. The tool does not infer frame positions by FPS.
- No automatic visual approval, gesture understanding, physical-camera inference, ethnicity/age classification or speaker-person association is performed.

Next: calibrated local detection models with explicit model licensing/weights, multi-frame subject-action recognition, and active speaker evidence after review of real annotated clips. Link such findings to the character-scene graph as *provisional* evidence until independently confirmed.
