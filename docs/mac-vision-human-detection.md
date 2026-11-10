# Local macOS Vision human-region detection

**Status:** optional Apple Vision people-rectangle detector for **live-action human regions** in authorized local video. It uses the built-in `VNDetectHumanRectanglesRequest` framework through PyObjC, with no downloaded model or remote API. It does **not** identify the person, infer age/gender/ethnicity, recognize fictional character continuity or reliably support illustrated/animated characters. This is a **provisional detector input**, not a complete character understanding model.

Apple documents [VNDetectHumanRectanglesRequest](https://developer.apple.com/documentation/vision/vndetecthumanrectanglesrequest) for finding person rectangles and [VNImageRequestHandler](https://developer.apple.com/documentation/vision/vnimagerequesthandler/init%28data%3Aoptions%3A%29?language=objc) for processing local image data.

## Setup on Apple Silicon macOS

Install FFmpeg and FFprobe in PATH, plus PyObjC framework bindings in the same Python environment running Reference Lab:

```bash
python3 -m pip install -e '.[motion]'
python3 -m pip install pyobjc-framework-Vision

PYTHONPATH=src python -m kumiki_reference_lab mac-vision-humans \
  ./authorized-live-action.mp4 --max-seconds 10 --max-samples 12 \
  --out ./runs/apple-human-detections.json

PYTHONPATH=src python -m kumiki_reference_lab subject-detections \
  ./authorized-live-action.mp4 ./runs/apple-human-detections.json \
  --out ./runs/apple-human-tracklets

PYTHONPATH=src python -m kumiki_reference_lab review-subject-tracklets \
  ./authorized-live-action.mp4 ./runs/apple-human-tracklets/subject-tracklets.json \
  --out ./runs/apple-human-review
```

Open `./runs/apple-human-review/index.html` locally and inspect every proposed rectangle against the source frames. The gallery/tracklet output is **unreviewed**, and missing people or false detections should be noted rather than silently treating scores as truth.

## What this backend actually does

- FFprobe supplies original frame PTS and stream timebase; frames are sampled **uniformly by presentation time**, not nominal FPS.
- FFmpeg decodes the exact requested frame ordinals, and the decoded PTS must match FFprobe. Up to 24 frames from the first 30 seconds are processed at up to 320×180 resolution.
- Apple Vision receives in-memory PNG image data and returns people rectangles. Native bottom-left normalized bounding boxes are converted to top-left normalized coordinates.
- Results are deduplicated and capped at 8 proposed people per sampled frame; each output includes an uncalibrated Vision confidence.
- The source SHA, stream/timebase, provider name and FFmpeg cut candidates are recorded in the existing `kumiki.subject-detections.v1` format. `modelSha256` is null because Apple's system model is not supplied as a local weight file.
- No input frame, model weight, transcript, voice print or original video is saved by this detector. It writes only a new local detection JSON file.
- The next two commands apply conservative within-shot IoU association and produce a source-PTS-verified visual QA gallery.

## Limitations

- Apple Vision only provides **people-region proposals** here, not identity, pose, gestures, speech, mouth movement, facial expression or narrative action.
- It may fail on very small, cropped, stylized, animated, anthropomorphic or heavily occluded subjects, especially at the bounded 320×180 scan resolution.
- The framework version/model behavior can vary with macOS. No actual live Mac/Apple Vision execution or detector accuracy benchmark was possible from the Linux development environment; mocked binding tests do **not** prove real-world success.
- The model runs locally when macOS permits Vision processing. Sandbox restrictions can cause Vision failures on some systems. Run from your normal local Terminal if a sandboxed coding agent cannot access Vision resources.
- Apple Vision confidence is not a probability of true character identity, and box association from adjacent frames is not re-identification across cuts.
- The file must be an authorized local video; the tool does not fetch media from What Ships, YouTube or X.

### Recommended next steps

Run on a few short authorized live-action films and evaluate false-positive/false-negative rates and tracklet ID switches against reviewed labels. Then integrate a commercially appropriate local model trained for **animated characters** and add evidence-backed temporal action/gesture analysis. Treat all inferred demographic or personal details as unknown unless explicitly supported by a credible source.
