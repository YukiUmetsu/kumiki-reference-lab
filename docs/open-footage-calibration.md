# First real-footage calibration (four openly licensed references)

Unlike synthetic integration fixtures and the **unwatched** high-view-count inspiration catalog, these four files were actually downloaded and analyzed on **2026-11-10**. Their bytes were hashed, FFprobe recorded media metadata and source timebase, and the 2D image-motion and display-luma analyzers processed **11 ten-second windows across the four films**, preserving the original source PTS and media SHA-256. One-frame-per-second contact sheets were inspected to label each window's visual role. **The films were not watched in motion at full speed**, and there has been no independent style classification, camera-rig recovery, lighting-rig recovery or popularity verification for these four files.

The data are stored without footage or copied frames in [`research/open-footage-calibration.v1.json`](../research/open-footage-calibration.v1.json).

## Sources and attribution

| Reference and original Commons file | Attributed creator | File license |
| --- | --- | --- |
| [Night - Paper stop motion](https://commons.wikimedia.org/wiki/File:Night_-_Paper_stop_motion.webm) | DRabbitz Drtz | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |
| [Trick or Treat - Kinetic Typography](https://commons.wikimedia.org/wiki/File:%27Trick_or_Treat%27_-_Kinetic_Typography.webm) | Conanda Sixteinliesena | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |
| [Sintel webm extract](https://commons.wikimedia.org/wiki/File:Sintel_webm_extract.webm) | Durian Open Movie project / Blender Foundation | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) |
| [MotionGraphicsAnimation](https://commons.wikimedia.org/wiki/File:MotionGraphicsAnimation.webm) | Wiki Learning Tec de Monterrey students; individual credits in film | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |

The Commons file-description pages document the licenses and authorship. Follow the applicable attribution and, for ShareAlike, derivative-sharing requirements if using footage outside this private analysis. The repo stores **only metadata and human-written observations**, not copyrighted video, audio, frames or textures. These references are not the same population as the 40 popular video inspirations or 300 recent-upload source rows; do not join their measured visual proxies to other videos' audience counts.

## What the ten-second sample actually measured

The numerical columns below are **counts in each sampled opening interval**, not per-minute values, whole-video frequencies, or physical moves. Image-plane translation is measured by global phase correlation at 30 source-PTS-spaced samples; the display-brightness proxy uses 24 samples. Cut candidates are detector output, not confirmed edits. `active` is the proportion of *measurable pair duration*, not the fraction of total film runtime.

| Source (first 10s) | Image translation runs | Image active share | Image measurable share | Luma-change runs | Luma active share | Cut candidates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Night - Paper stop motion | 0 | 0.0% | 51.0% | 0 | 0.0% | 0 |
| Trick or Treat | 6 | 53.4% | 89.6% | 5 | 52.4% | 3 |
| Sintel extract | 2 | 50.4% | 96.2% | 0 | 0.0% | 1 |
| MotionGraphicsAnimation | 5 | 59.3% | 76.5% | 4 | 17.7% | 0 |

**Key false-negative trap:** The opening 10s of *Night - Paper stop motion* show mostly black title cards, although later sparse contact-sheet samples (approximately 25–35s and 55–65s) show flat illustrated cutouts, bedrooms and night scenes. Its zero opening-window motion result is **not** evidence that paper-cut animation rarely moves or has no camera work. We tested that directly with the new `--start-seconds` option, without creating a time-rebased transcode:

| Paper-film source window | Image translation runs | Image active share | Luma-change runs | Cut candidates |
| --- | ---: | ---: | ---: | ---: |
| 0–10s: title cards | 0 | 0.0% | 0 | 0 |
| 25–35s: character/bedroom/night transition | 3 | 48.9% | 2 | 2 |
| 55–65s: dim bedroom and character scene | 4 | 72.6% | 4 | 0 |
| 85–95s: ending title to credits | 0 | 0.0% | 3 | 0 |

Global image motion and average display brightness still miss character/shape deformation, internal object animation, color-independent motion, spatial light changes and some edits. The 10s Sintel sample contains a firelit interior, but its zero luma-change runs do not prove that the lighting rig is static. The four windows describe only 40 **non-contiguous** seconds of a 112-second paper film, not its whole runtime.

### Additional source windows and content-aware comparison

We sampled a wider range of body content and endings. Each later-window `visualContext` comes from a sparse still-frame contact sheet and is **distinct from** numerical motion/luma detection:

| Video | Source window | Reviewed visual role | Image translation runs | Luma-change runs | Cut candidates |
| --- | --- | --- | ---: | ---: | ---: |
| Sintel extract | 20–30s | City establishing image after dark transition | 1 | 1 | 1 |
| Sintel extract | 50–60s | Character and dragon rooftop action | 5 | 1 | 5 |
| MotionGraphicsAnimation | 15–25s | Spanish typography, illustrated fox and shapes | 2 | 3 | 3 |
| MotionGraphicsAnimation | 35–45s | Dollar/clock graphics transitioning into credits | 3 | 2 | 0 |

The 85–95s paper-film window also transitions to ending credits. **Credits and title sequences must be separated from main-content footage** before comparing motion cadence; otherwise, a video with longer credits can appear artificially calmer or busier. Run `open-footage summarize` to produce a per-video breakdown grouped by reviewed role with time-weighted measurable-pair fractions. This reports only the selected windows, not a whole-film frequency estimate.

The sample also shows a precision limit: a high-contrast kinetic-typography clip yields 6 motion runs in ~10s, whereas the motion-graphics film yields 5 in its opening ~10s. These are *threshold-specific detected episodes*, not six or five deliberate camera moves. With only four deliberately diverse sources and eleven sampled windows, **there is no defensible statistical relationship with view counts, retention, aesthetic quality or a recommended camera-movement frequency**.

## Reproduce without a subscription

Download each **original file** by following `media.downloadUrl` in the dataset and save it under `media.localName`, for example into `workspace/open-media/` (gitignored). Hash verification is exact: if a host replaces or transcodes a file, the check rejects it until independently re-reviewed. No network call occurs during validation or verification.

```bash
PYTHONPATH=src python -m kumiki_reference_lab open-footage validate
PYTHONPATH=src python -m kumiki_reference_lab open-footage list
PYTHONPATH=src python -m kumiki_reference_lab open-footage summarize
PYTHONPATH=src python -m kumiki_reference_lab open-footage verify-local \
  --media-root workspace/open-media

PYTHONPATH=src python -m kumiki_reference_lab analyze \
  workspace/open-media/kinetic-typography.webm \
  --max-seconds 10 --thumbnails 8 --max-samples 30 \
  --motion --appearance --sparse-flow --sparse-samples 18 --sparse-points 30 \
  --out runs/open-benchmark-kinetic-typography

# Point these paths to image-motion.json and appearance.json in that immutable run.
PYTHONPATH=src python -m kumiki_reference_lab visual-cadence \
  runs/open-benchmark-kinetic-typography/analysis-*/image-motion.json \
  runs/open-benchmark-kinetic-typography/analysis-*/appearance.json

# Directly measure a later window with original source PTS (no derivative clip).
PYTHONPATH=src python -m kumiki_reference_lab motion \
  workspace/open-media/paper-stop-motion.webm \
  --start-seconds 25 --max-seconds 10 --max-samples 30 \
  --out runs/paper-window-25/motion
PYTHONPATH=src python -m kumiki_reference_lab appearance \
  workspace/open-media/paper-stop-motion.webm \
  --start-seconds 25 --max-seconds 10 --max-samples 24 \
  --out runs/paper-window-25/appearance
PYTHONPATH=src python -m kumiki_reference_lab visual-cadence \
  runs/paper-window-25/motion/image-motion.json \
  runs/paper-window-25/appearance/appearance.json
```

The run's `sourceSha256` and `sourceTimebase` are checked. Numerical measurements were captured with NumPy 2.3.5 and FFmpeg 7.1.5, using image-motion threshold 0.01 normalized units/s and display-luma threshold 0.05/s. `open-footage verify-local` checks actual SHA-256, byte size, duration, resolution, stream and timebase; it does **not** confirm the rights statement from the external website, measure the style or verify that a reviewer watched the whole clip. A failed hash means stop and investigate, not automatically update the expected hash.

## Next research milestone

1. Extend the new **source-PTS-preserving start offsets** from `motion`/`appearance` to `analyze` and other bounded stages. The multi-stage pipeline still begins at zero; the currently supported later-window commands scan a bounded prefix (up to 120s) to retain original decoded frame ordinals and PTS without seeking to a keyframe or making a derivative clip.
2. Inspect representative sections at normal playback speed with and without sound. Annotate discrete shots and deliberately separated styles, including titles vs. core animation, with abstention for ambiguous light/camera interpretation.
3. Add more genre-balanced, age/length/channel-matched samples and real audience snapshots for **those exact IDs**. Measure within-film variation and reviewer agreement before testing style/cadence differences; observational differences are not causal drivers of views.

Run the local regression suite before merging: `PYTHONPATH=src python -m unittest discover -s tests -q`. Keep high-cost multimedia tests out of hosted CI, but do not remove them.
