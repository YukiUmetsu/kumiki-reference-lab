# Footage-grounded visual style reviews

The [studio-attributed style catalog](visual-style-camera-lighting-methodology.md) is inspiration research, **not a set of automatically observed labels for the popular-video dataset**. To study paper-cut clips, collage, stop-motion, 2.5D, game cinematics, live action and mixed media quantitatively, reviewers need to annotate *actual video intervals* at source presentation timestamps (PTS). The `visual-style-review` command validates and summarizes those declarations. No original third-party video was reviewed to implement this feature.

## Four independent style axes

| Axis | What to record | Examples |
| --- | --- | --- |
| `medium` | Primary rendered or photographed medium in the interval | `2d-animation`, `2.5d-compositing`, `3d-rendered`, `live-action`, `physical-stop-motion`, `game-engine`, `screen-recording`, `mixed-media`, `unclassified` |
| `treatments` | Zero or more aesthetic signatures visible at the same time | `paper-cut`, `paper-collage`, `cutout-puppet`, `clay`, `hand-drawn`, `cel-shaded`, `painterly`, `photorealistic`, `2.5d-parallax`, `halftone-print`, `kinetic-typography`, `motion-infographic`, `procedural-abstract`, `pixel-art`, `naturalistic-documentary`, `game-cinematic`, `composited-live-action`, `other` |
| `lightingLook` | Observed light appearance, **not physical light-rig recovery** | `high-key`, `low-key`, `soft-diffuse`, `hard-directional`, `backlit`, `flat-graphic`, `mixed`, `unclassified` |
| `shotScale` | Perceived scale of framing, **not focal-length recovery** | `establishing`, `wide`, `medium`, `close-up`, `macro`, `screen-capture`, `mixed`, `unclassified` |

A paper-cut animation with 2.5D camera movement can have medium `2.5d-compositing` and treatments `paper-cut`, `paper-collage`, `2.5d-parallax`. A live-action clip with animated overlays might use medium `mixed-media` and several treatment tags. This separates *how imagery is constructed* from *the aesthetic finish*; it does not assert how the original studio actually built it.

## Review workflow

1. Obtain an authorized local source. Record its **actual** SHA-256, video stream index and source timebase. Public availability alone does not authorize redistributing a film.
2. Watch the source at playback speed, with and without audio. Mark one continuous PTS interval per stable visual treatment. Save 1–5 actual source PTS anchors per interval and a concrete observation and alternative explanation.
3. For a full-window claim, intervals must tile **every moment** of the declared window without overlap or gaps. Use `unclassified` for uncertain moments instead of silently skipping them. For a partial review, gaps are allowed and whole-window style proportions remain unavailable.
4. Preserve reviewer identity and confidence as **self-declared** evidence. A model or reviewer observation is not independent proof of style, camera setup, or cinematic quality.
5. Use the same tagging rubric on the higher- and lower-viewed videos selected by `audience-benchmarks study-plan`. Do not interpret observed view differences as a causal result of a style or lighting look.

Start with [`examples/visual-style-review.example.json`](../examples/visual-style-review.example.json). It is **illustrative only**, using a placeholder source hash, fictional media intervals and a placeholder reviewer. Replace every field using real video evidence before producing an actual dataset.

```bash
PYTHONPATH=src python -m kumiki_reference_lab visual-style-review validate local-reviewed-style.json
PYTHONPATH=src python -m kumiki_reference_lab visual-style-review report local-reviewed-style.json
```

## Interpreting the report

- `labeledFractionOfWindow` is **time-weighted** at the declared source timebase, not the number of labeled intervals divided by the interval count.
- `fractionOfLabeledTime` describes only the portions annotated. Even an apparently useful partial review cannot be extrapolated to the rest of a film.
- `fractionOfEntireReviewedWindow` is provided **only** if the reviewer declares full coverage *and* the labeled intervals exactly tile that window. The claim is not independently verified against the original video.
- `confidence` time shares disclose how much of the annotated window relies on `high`, `medium`, `low`, or `unresolved` reviewer judgments. An `unresolved` interval must carry an explicit `unclassified` medium/lighting/scale and no treatment labels, so uncertainty cannot masquerade as a known style.
- Primary-medium fractions and lighting-look fractions each sum to one for a completely labeled window. Treatment fractions may sum **above one** when several treatments co-occur. `unclassified` is a genuine explicit category, not a discarded or zero-duration span.
- Segment boundaries are **classification intervals**, not necessarily editing cuts or style-change events. No cut rate, camera-movement frequency, actual light motion, audience-retention measure or causal conclusion is inferred from them.

Separate [`visual-events`](visual-style-camera-lighting-methodology.md#3-camera-and-lighting-event-frequency-after-visual-review) reports provide reviewer-interpreted camera/lighting **event frequency**. Separate [`visual-cadence`](visual-style-camera-lighting-methodology.md#2-what-the-cadence-command-really-measures) reports measure sparse image-plane motion and display-brightness proxies. Do not collapse these different observations into one unexplained quality score.
