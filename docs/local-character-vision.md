# Local character appearance and motion perception (Ollama)

**Status: working optional local vision-language inference adapter, NOT verified automatic character understanding.** It obtains **real source-PTS-checked video frames** and previously detected subject boxes, crops each provisional subject, and asks an already installed local vision-capable Ollama model for visible appearance and two-frame motion hypotheses. It exports a schema-valid `character-scene.json` with low-confidence appearance and action proposals.

Ollama documents base64 images in local `POST /api/chat` messages, `format: "json"` and `stream: false`: [Ollama Vision](https://docs.ollama.com/capabilities/vision) and [API](https://docs.ollama.com/api). **No model download or account login is performed by Reference Lab.** The service is contacted only at `127.0.0.1` (never arbitrary URLs), via an explicit local port.

## Setup on Apple Silicon

Install FFmpeg/FFprobe and Ollama independently; choose an **already available, installed** vision-capable local model. [`qwen3-vl:8b`](https://ollama.com/library/qwen3-vl) is one published model option (approximately 6.2 GB stored weights); its performance on this workflow has **not** been benchmarked on your Mac. Larger models may use much more RAM.

```bash
ollama list
# If you separately choose to install a vision model, for example:
# ollama pull qwen3-vl:8b
# ollama serve   # only if Ollama is not already serving

# Step 1. Create source-matched subject detections (macOS humans example).
PYTHONPATH=src python -m kumiki_reference_lab mac-vision-humans \
  ./local-video.mp4 --out ./runs/people.json

# Step 2. Associate the detections into conservative provisional tracklets.
PYTHONPATH=src python -m kumiki_reference_lab subject-detections \
  ./local-video.mp4 ./runs/people.json --out ./runs/people-tracklets

# Step 3. Infer appearance and two-frame motion using a LOCAL vision model.
PYTHONPATH=src python -m kumiki_reference_lab local-character-vision \
  ./local-video.mp4 ./runs/people-tracklets/subject-tracklets.json \
  --model qwen3-vl:8b --max-frames 6 --max-calls 12 \
  --out ./runs/local-character-vision

# Step 4. Examine provisional results.
PYTHONPATH=src python -m kumiki_reference_lab character-scene report \
  ./runs/local-character-vision/character-scene.json
```

For **animation**, provide `subject-tracklets.json` generated from a suitable external local animated-character detector via `subject-detections`. Apple Vision is a limited *human-region* detector, not an animated character detector. The local VLM can describe animated subject crops if your detector supplies them; accuracy has not been measured.

## What it produces

- `character-scene.json`: provisional tracklet IDs and one-tick appearance observations at actual sampled source PTS, model-generated visual descriptions (clothing, silhouette, hair, colors and props), and action **hypotheses** across two frames of one tracklet when the pair is sufficiently close and no declared cut intervenes. No inferred real identity, demographic attributes, words spoken, emotions or actor-to-actor targets.
- `character-vision.json`: local model tag, selected sample count, actual request count, source and tracklet report fingerprints, explicit model-digest-not-verified flag, each model proposal and caveats. The service never receives the full film, just 1–2 PNG crops per call. Only parsed JSON observations are stored, **not** the crops.
- No files are published if a model call or input-validation step fails. Existing output directories cannot be replaced.

The pipeline bounds the first source window (default 20 seconds; max 120), selected frames (2–12), model calls (1–24), crop/frame resolution (up to 320×180) and response size. Source frame PTS must match FFprobe/FFmpeg verified ordinals; source SHA, video stream and rational timebase must match the detection report. The client sends only to literal `127.0.0.1` on the chosen port, so no remote/Ollama-cloud endpoint is configured. Avoid exposing Ollama as a public server.

## Evaluation boundaries

- **The model is not trusted.** Even though the *image pixels and timestamps* are verified, descriptions and actions remain **low confidence, unreviewed hypotheses**. False positives, scene cuts omitted from the input, camera motion, occlusion and model hallucinations are not automatically resolved. Identity changes across tracklets are never merged.
- First appearances are derived from **one still crop**; an action cannot be output at that point. Action proposals require two source-matched crops of the same provisional tracklet with a maximum 3-second gap and no supplied cut between them.
- The model must use a restricted action vocabulary and include a grounded text observation; observations containing explicit demographics and identity claims are rejected. This is an input/output guard, **not proof of unbiased or error-free classification**.
- No speech, voice attribution, facial emotion, verified human age, ethnicity, gender identity, name or personal identification is produced. Interactions between multiple subjects remain a future stage.
- Output model tag is an operator-provided string; no model weight digest is independently computed. Review the local Ollama model and its license before commercial use.
- Basic regression tests mock local inference and source decoding; **actual model quality on user footage is still untested**. Existing lightweight CI includes these fast, model-free tests.

## Next study

Create a small manually reviewed ground-truth cohort (human and stylized subjects) with source-PTS keyframes, apparel/pose labels, cut boundaries, and movement timing. Evaluate hallucination and recall, calibrate thresholds, improve high-resolution subject crops, and then add paired-scene actor-to-target interactions and active-speaker validation. Real What Ships film data still requires authorized local source bytes; a watch-page URL is reference metadata, not a validated film file.
