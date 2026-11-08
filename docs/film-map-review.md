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
