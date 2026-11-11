# One-command local character study

`character-study-local` runs the existing local detection, provisional tracking, appearance/action VLM, directed interactions and source-frame QA stages **as one atomic workflow**. It is the simplest starting point for studying human and fictional characters in a short video, including animated, animal and anthropomorphic subjects.

**Status:** the orchestration is implemented, but model outputs remain **low-confidence, unreviewed hypotheses**. A successful study means the local tools completed, not that any detected character, appearance, action or interaction is accurate.

## Usage

On macOS, install FFmpeg/FFprobe, a recent Python and an already downloaded, vision-capable Ollama model. The tool never automatically downloads model weights or media. `qwen3-vl:8b` below is an **example tag**; check `ollama list` before running it.

```bash
PYTHONPATH=src python -m kumiki_reference_lab character-study-local \
  ./authorized-reference.mp4 --model qwen3-vl:8b \
  --detector ollama --max-seconds 10 --max-samples 8 \
  --max-calls 12 --max-pairs 6 \
  --out ./runs/character-study-001
```

The same command can use `--detector apple-vision` for macOS live-action human regions. Both modes use the local Ollama model for subject appearance and optional actor-target interaction analysis. For stylized/animated/anthropomorphic characters, prefer the Ollama detector until a dedicated animated-subject model is evaluated.

To reduce expensive local inference on a longer experiment, specify `--skip-interactions` or `--skip-qa`. The latter only skips creating offline image galleries, **not** provenance checks or model inference.

## Study structure

The command writes one new output directory (only after every requested stage succeeds):

- `study-manifest.json`: source SHA, stream/timebase, selected local detector/model, coverage budgets, provisional counts, explicit unverified status, and relative artifact paths.
- `subject-detections.json`: source-PTS-bound bounding boxes proposed by local Ollama VLM or Apple Vision.
- `tracklets/subject-tracklets.json`: cut-bounded local tracklet associations, still not individual identities.
- `tracklet-qa/index.html`: actual local video frames with provisional subject boxes.
- `character-vision/character-scene.json` and `character-vision/character-vision.json`: low-confidence appearance, clothing/shape and two-frame action hypotheses.
- `character-qa/index.html`: original frames/crops beside visual appearance/action claims, with all review verdicts initially pending.
- `character-interactions/character-scene.json` and `character-interactions/character-interactions.json`: two-subject directed action hypotheses (only when at least two provisional characters were seen).
- `interaction-qa/index.html`: side-by-side red/cyan original frames for human assessment of every proposed interaction/abstention.

Generated QA directories also contain their image files, manifests and editable human review feedback JSON. No HTTP server, third-party account or paid API is necessary to open the galleries.

## Evidence policy and limits

- Model calls use literal `127.0.0.1`. The source file must be an authorized local video, not a browser watch-page URL.
- Each stage checks source hashes/original presentation timestamps, stream and timebase. The entire workflow uses a staging directory; failure causes **no partially published final study**.
- In the character model's JSON, demographics, real personal identities, emotions and dialogue are intentionally not inferred. You can pair a separate `speech-transcribe`, `speech-associate` and `speech-link-characters` workflow later, using actual voice/lip evidence.
- Study coverage is an initial video prefix, bounded by default to ten seconds and eight sampled frames. Each local model call has a timeout and the pipeline does not silently extrapolate missing frames/characters to the remainder of a video.
- Detection boxes, local tracklet continuity, visible traits and actor-target interactions may be wrong, especially in cartoon scenes, shots with camera movement or characters occluded by other objects. The model's self-reported boxes are **not** verified until reviewed against the original source.
- Even when zero characters or interactions were proposed, that does not prove the video contains none. For zero appearance observations, the character QA gallery is omitted; for fewer than two characters, the interaction stage is omitted.
- Generated QA galleries include actual video frames and subject crops. Retain them locally and do not upload third-party footage or recognizable people without appropriate rights.
- A valid reviewer must explicitly approve/reject model proposals via `character-vision-feedback` and `character-interaction-feedback` before reporting quality metrics. A completed report does **not** measure correctness on its own.
- The repository's lightweight tests mock the decoder and local model calls. **Native Apple Silicon end-to-end execution and actual accuracy on real What Ships video footage remain unverified.**

## Suggested real-world test

Use one short local animated clip and one live-action clip that you have permission to process. Inspect `tracklet-qa` first, then `character-qa` and `interaction-qa`. Record missed boxes, wrong clothing, false gestures and incorrectly attributed actor/target pairs. Those findings provide evidence for improving model choice, prompt, resolution, or tracking before connecting this data to Kumiki UI choreography.
