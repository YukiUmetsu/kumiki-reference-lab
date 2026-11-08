# Review an authored Kumiki film against its reference video

After the [FD1 evidence handoff](film-handoff.md), a creative editor authors an original film in `kumiki-ui`, validates it with `film:check`, and chooses explicit source-video PTS ↔ film-frame anchors using [Kumiki UI's `film:reference-map`](https://github.com/YukiUmetsu/kumiki-ui/blob/main/docs/component-specs/film-reference-map.md). The result is `reference-film-map.json` (`kumiki.reference-film-map.v1`). Its pairings are editorial decisions, **not** inferred camera paths, synchronized audio cues, or measured visual matches.

Reference Lab can now turn that map into **actual, independently decoded JPEGs** for side-by-side review:

```bash
kumiki-ref review-film-map \
  ./reference-film-map.json \
  ./original.film.json \
  ./reference.mp4 \
  ./dist/film/original/landscape.mp4 \
  --max-seconds 30 --width 480 --out ./review-runs
```

The command:

1. Verifies the original video SHA-256 and the authored FD1 JSON SHA-256 against the map. It also cross-checks film ID, FPS, total scene duration and every mapped scene/frame offset against the actual authored JSON. The generated film's bytes are hashed separately; **the hash alone cannot prove which film source rendered it**.
2. Reads actual source-video PTS and checks that each selected source PTS exists unambiguously. For each render anchor it locates the **absolute decoded frame ordinal** and verifies its encoded PTS against the exact rational film timestamp. A mismatched start offset, frame-rate conversion, reordered source timestamps, or absent frame is a **failure**, not a silent approximate match.
3. Decodes only the selected images, then checks each FFmpeg `showinfo` PTS/timebase against the probed frame stream.
4. Publishes an immutable, SHA-256-inventoried `film-map-review-*` bundle with paired JPEGs, `index.html` and `film-map-review.json`. Identical reruns reuse verified files. Failed decoding, modified originals or altered evidence never produce a published partial result.

Limits: 1–12 unique, monotonically ordered anchors per video; both anchors must fall within the first 1–120 seconds of each input. This first bounded version is deliberately conservative. Non-monotonic story remapping, long-form windowed seeking, 2.5D/3D geometry recovery, full-motion synchronized comparison, source audio alignment, and perceptual scoring are not implemented.

The HTML is an **inspection aid**. Review teaching clarity, causal object continuity, camera intention, composition, typography, surface detail, lighting and actual motion at full speed. `qualityVerdict` remains `not-performed`, even when all technical checks pass. Original frame quality is judged by a human.

Local verification: `PYTHONPATH=src python -m unittest tests.test_film_map_review -v`. Video decoding tests stay out of automatic CI to conserve credits; the test file is retained.

## Turn the comparison into actionable feedback

The paired stills alone do not tell a coding agent what to improve. After inspecting them **and playing the rendered film at full speed**, create a separate, editable draft:

```bash
kumiki-ref film-feedback init \
  ./review-runs/film-map-review-.../film-map-review.json \
  --reviewer-kind human --reviewer-id editor-1 --out ./editor-notes
```

Edit `./editor-notes/film-map-feedback.json` to add findings. For example:

```json
{
  "id": "finding-obscured-subject",
  "anchorId": "focus-01",
  "category": "camera",
  "severity": "significant",
  "observation": "The close camera hides the subject before the explanation finishes.",
  "suggestedChange": "Move the camera back, preserving the subject while the next diagram appears."
}
```

Insert this object into the draft's `findings` array; do not replace the full JSON document. `anchorId` must match an actual reviewed pair. Each draft records the exact SHA-256 of the review report, source/render videos, each pair's JPEG bytes, and original source PTS/film frame number. Validate with:

```bash
kumiki-ref film-feedback validate \
  ./review-runs/film-map-review-.../film-map-review.json \
  ./editor-notes/film-map-feedback.json
```

Corrections can be categorized as `composition`, `camera`, `lighting`, `material`, `animation`, `readability`, `story-clarity`, `attention`, `continuity`, `timing`, `sound` or `other`, with `blocking`, `significant`, `polish`, or `observation` severity. All but `observation` require a suggested change. **Sound annotations must be based on separate listening**, because the paired stills do not prove audio synchronization. The draft may be annotated by a human or an AI model, but author identity is self-declared and must not be treated as authentication.

Validation checks exact evidence identities and annotation structure, not the quality or truth of the feedback. It returns `artisticApproval: not-granted`; no automated validator may promote a film or technique into the catalog as production quality. The schema is [`film-map-feedback.schema.json`](../schemas/v1/film-map-feedback.schema.json). The small FFmpeg-free feedback tests remain part of local test coverage; no additional hosted CI jobs are required.

## Test the complete two-repository boundary locally

With FFmpeg/FFprobe installed and both repos checked out, run:

```bash
python scripts/smoke_cross_repo_fd1_feedback.py --kumiki-ui ../kumiki-ui
```

This optional smoke script creates its own short, synthetic 10 FPS source and 30 FPS render in a temporary directory. It uses **the actual Kumiki UI FD1 checker and reference-map command**, then Reference Lab's encoded-PTS extraction and JPEG-pair verifier, feedback template/validator, and finally Kumiki UI's severity-aware scene edit queue. It checks the final scene/frame identity and that no quality approval was fabricated. The fixture's source cut window is intentionally synthetic and makes no claim about detected editorial cuts or the visual quality of either video.

No generated videos, drafts or images are committed; the test is kept **local-only and off hosted CI** to preserve the low-cost workflow. It fails explicitly if the other repo, FFmpeg or an expected command is unavailable.
