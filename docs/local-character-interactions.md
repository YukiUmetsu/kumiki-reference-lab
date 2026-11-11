# Local two-character interaction hypotheses (Ollama)

**Implemented, unverified:** `local-character-interactions` compares two source-PTS-verified frames with visible **red** and **cyan** outlines marking a pair of provisional tracked subjects. An already installed local Ollama vision model may propose a directed visual movement: who appears to reach, point, gesture, approach, touch or pass an object **toward the other tracked subject**.

Every proposal is **low-confidence, not independently verified**, and limited to observable changes across two frames. It is NOT proof of intentional contact, real-world depth, speech, social relationship, age, gender, ethnicity or identity.

## Command

First obtain a source-matched `subject-tracklets.json` and [local-character-vision](local-character-vision.md) output for the same local film:

```bash
PYTHONPATH=src python -m kumiki_reference_lab local-character-interactions \
  ./authorized-video.mp4 \
  ./runs/people-tracklets/subject-tracklets.json \
  ./runs/local-character-vision \
  --model qwen3-vl:8b --max-pairs 6 --gap-seconds 3 \
  --out ./runs/character-interactions

PYTHONPATH=src python -m kumiki_reference_lab character-scene report \
  ./runs/character-interactions/character-scene.json
```

No code path downloads model weights, invokes a cloud API or uses a URL from the video source; only the literal local `127.0.0.1:11434/api/chat` endpoint is used. An Ollama daemon and a vision-capable local model must be installed separately.

## How pairs are chosen

- **Existing local tracklets only.** Both characters must already occur in the supplied local character-scene roster and each must have a source-matched detector bounding box in both adjacent sampled frames. No identity is inferred across shots or camera cuts.
- Only pairs with no supplied cut and at most 3 seconds apart are considered. Heavy box overlap (IoU over 0.65) is skipped as too ambiguous.
- The model sees **two PNG images** of actual source frames, each with red/cyan outlines of the respective tracklets. Two-frame changes may reflect perspective, camera motion, compositing, occlusion or animation; instruct the model to use `none` rather than invent an interaction when uncertain.
- Output is restricted to `none`, `reaching-toward`, `pointing-toward`, `passing-object`, `touching`, `following`, `gesturing-toward`, `moving-toward` or `moving-away`. A non-none prediction must specify the red or cyan actor and a short concrete visual observation. Invalid/conflicting JSON is rejected.
- The result preserves the existing character descriptions, appearance observations, individual actions, dialogue and identity claims, and only appends **low-confidence, timecoded, actor-to-target proposals** when the model finds evidence.
- The separate `character-interactions.json` records all reviewed candidates, abstentions, PTS anchors, local IDs, model tag, source/report hashes, and uncertainty. It does not claim to identify the local model weights by SHA.
- No raw film frames are stored or redistributed by this command. Review results against the authorized source before using them for actual Kumiki choreography.

A zero-candidate result is a **valid abstention**. It may mean only one tracklet was reviewed, detections are missing, a cut interrupted tracking, or the subjects never co-occurred. It is **not** proof that a film contains no interactions.

## Remaining quality needs

Run a real local Ollama vision model on a small human-reviewed set and record false positives/false negatives for pointing, passing an object, physical contact and camera-induced movement. Extend [character vision QA](character-vision-quality-review.md) to review pairwise events with both highlighted frames. Do not treat model words, apparent proximity, or What Ships view counts as ground truth.
