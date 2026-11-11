# Benchmark character detection against annotated source frames

The new `evaluate-character-detections` CLI computes **sampled-frame bounding-box precision, recall and F1** against explicitly completed human annotations. This fills an important gap in visual QA: checking only the boxes a model proposed cannot reveal **characters it missed**.

This is a repeatable **local benchmark**, not a claim that the model is accurate on arbitrary media. It does not identify people or measure actions, dialogue, identity tracking through cuts, or full-film coverage.

## Create ground truth

Use an authorized local video and previously generated `subject-detections.json`, then inspect the actual source frames in `review-subject-tracklets`:

```bash
PYTHONPATH=src python -m kumiki_reference_lab character-labels-template \
  ./runs/study/subject-detections.json \
  --out ./runs/study/human-box-labels.json
```

The generated JSON starts **not approved**, with `"reviewer":{"kind":"human","id":"unassigned"}`, `"coverageDeclaration":"pending-review"` and an empty `subjects` array for each exact source-PTS sample. **An empty array in this pending template does not mean the frame has no characters.**

Review each sampled frame against source video. Include **all visibly supported subjects in the chosen categories** on that frame, including subjects the model missed. For each human-labeled subject, add:

```json
{"category": "animated-character", "box": [0.10, 0.15, 0.25, 0.60]}
```

Coordinates are normalized top-left `[x,y,width,height]` in [0,1]. Supported categories: `person`, `animated-character`, `animal`, `anthropomorphic`, and `other-subject`. Each frame can contain up to 20 labeled objects. The reviewer should not duplicate one subject across overlapping boxes. When all sampled frames have been annotated, replace `reviewer.id` with an explicit human review ID and replace `coverageDeclaration` with:

```text
all-visibly-supported-subjects-on-each-listed-sampled-frame
```

This coverage declaration is a **human assertion**, not independently verified truth. If annotations are incomplete, keep `pending-review` and do not use the metrics as recall evidence.

## Evaluate

```bash
PYTHONPATH=src python -m kumiki_reference_lab evaluate-character-detections \
  ./authorized-video.mp4 \
  ./runs/study/subject-detections.json \
  ./runs/study/human-box-labels.json \
  --min-iou 0.50 --out ./runs/study/detection-benchmark
```

Read `detection-benchmark/subject-detection-benchmark.json`. The report includes overall and per-category matched true positives, unmatched model proposals (false positives), missed human subjects (false negatives), precision, recall, F1, per-frame matched IoUs, and unmatched box indices.

## Method and limitations

- **Source provenance:** both label and prediction JSON must contain the same SHA-256, video stream, rational source timebase and identical, chronologically sorted sampled PTS frames; the original local source media must match via FFprobe and SHA. Source and input files are checked for modification before atomic publication.
- **Matching:** predictions only match ground-truth boxes of the same subject category with bounding-box IoU at least the configured threshold (0.25–0.9). Deterministic bipartite matching maximizes the number of valid matches, avoiding the classic greedy-assignment error when two boxes compete for one label. It does **not** optimize the summed matched IoU.
- **No confidence calibration:** local VLM subject boxes carry a uniform **0.5 compatibility score**; this is not estimated detection certainty. Report quality from actual human reviews, not model-supplied scores.
- **No automatic perfection:** if a frame contains neither predicted nor labeled boxes, its precision and recall are **null**, not 100%. The report does not extrapolate beyond sampled timestamps.
- **Bias and coverage:** the manual labels may be incomplete or inconsistent; even completed labels are self-declared. The frame selection and original videos may not represent the range of styles you ultimately care about.
- **No identity or action metrics:** this does not check that a subject keeps the same ID across shots, the actor targeted the correct subject, a gesture was real, or the speech belonged to that character. Those require separately reviewed temporal evidence.
- **Local only:** no inference, network requests, third-party video downloads or image uploads are performed by the benchmark. This command uses local video metadata and human-supplied boxes.

Use this first on a few representative short clips (2D animation, 3D character animation, real filmed people, crowded/multi-character scenes). False negatives and category confusion are more important to resolve before feeding generated character descriptions and actions into a production Kumiki video.
