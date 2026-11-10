# Multi-character screen-space tracking

**Status:** The system now tracks multiple image patches from manually supplied seeds. This is not automatic person/character detection, identity recognition, demographic inference, 3D distance estimation or semantic action recognition.

The `character-motion` command runs the existing source-PTS-aware ROI tracker for 2–6 seeded subjects and combines aligned frame observations. It reports where subjects appear, where their boxes overlap and whether image-center separation changes. Those are **screen-space measurements**, not proof that characters physically approach, speak or interact.

## Usage

Review the first sampled video frame and supply normalized boxes (x, y, width, height). The [seed example](../examples/multi-character-seeds.example.json) is **synthetic** and must be replaced for a real video.

```bash
python -m pip install -e '.[motion]'
PYTHONPATH=src python -m kumiki_reference_lab character-motion \
  ./authorized-reference.mp4 examples/multi-character-seeds.example.json \
  --max-seconds 10 --max-samples 40 --out ./runs/characters-01

PYTHONPATH=src python -m kumiki_reference_lab character-scene report \
  ./runs/characters-01/character-scene.json
```

Outputs are published atomically to a **new directory**:

- `character-motion.json`: PTS-aligned screen positions, visibility flags, co-visibility, normalized image-center distance, box overlap IoU and horizontal ordering.
- `character-scene.json`: schema-valid reviewer-supplied character roster and **single-frame sampled** low-confidence appearances; **no fabricated actions, dialogue or identities**.
- `roi-tracks/<id>.json`: each original tracked ROI, with cut boundaries, loss and optional manual reseeding.

The aggregate report records source hash, source timebase, stream, seed JSON hash, rights status, evidence limits and analyzer method. Neither network retrieval nor model downloads are performed.

## Interpretation

- Tracked statuses are `seeded`, `manual-reseed` and `matched-template`. Lost, cut or ambiguous frames have no asserted box; no interpolation is performed.
- Image-center trends are `image-centers-closer`, `image-centers-farther`, `stable-within-tolerance`, or `not-comparable`. Continuity stops at a cut, loss or independent manual reseed.
- Relative screen-space motion can arise from camera, 3D depth, animation or compositing. It is **not** a physically grounded interaction or an inferred emotion/gesture.
- The character scene creates one-source-tick appearance intervals at sampled source frames. That **does not** establish continuous visibility between samples. User-supplied descriptions are not verified by the tracker.
- ROI patch correlations are not calibrated confidence in character identity; similarly textured regions can drift. No identity is carried across a reseed.
- Current implementation decodes the video **once per seeded character**, rather than sharing decoded frames; six-character and 120-sample budgets keep costs bounded.
- The existing tracker needs textured seed boxes 8 pixels to half-frame size at analysis resolution. It is not reliable for precise lips, subtle expressions or fast animation.

## Next priorities

Add a provider-neutral local **detector/segmentation observation adapter**, association of uncertain detections into temporal tracklets, and visual evidence for gestures/gaze/face actions. Only then use optional audio/visual alignment to propose which character says each line. Do not infer age, ethnicity or gender identity from looks, and do not reinterpret an index-only What Ships listing as analyzed frames.
