# First real-footage calibration (four openly licensed references)

Unlike synthetic integration fixtures and the **unwatched** high-view-count inspiration catalog, these four files were actually downloaded and analyzed on **2026-11-10**. Their bytes were hashed, FFprobe recorded media metadata and source timebase, and the existing 2D image-motion and display-luma analyzers processed the first ten seconds of each file. One-frame-per-second contact sheets were inspected. **The films were not watched in motion at full speed**, and there has been no independent style classification, camera-rig recovery, lighting-rig recovery or popularity verification for these four files.

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

**Key false-negative trap:** The opening 10s of *Night - Paper stop motion* show mostly black title cards, although later sparse contact-sheet samples (approximately 25–35s and 55–65s) show flat illustrated cutouts, bedrooms and night scenes. Its zero opening-window motion result is **not** evidence that paper-cut animation rarely moves or has no camera work. Likewise, global image motion and average display brightness miss character/shape deformation, internal object animation, color-independent motion, spatial light changes and some edits. The 10s Sintel sample contains a firelit interior, but the zero luma-change runs do not prove that the lighting rig is static.

The sample also shows a precision limit: one high-contrast kinetic-typography video yields 6 motion runs in ~10s, whereas another motion-graphics video yields 5. Those are *threshold-specific detected episodes*, not six or five deliberate camera moves. With only four deliberately diverse sources and one opening segment each, **there is no defensible statistical relationship with view counts, retention, aesthetic quality or a recommended camera-movement frequency**.

## Reproduce without a subscription

Download each **original file** by following `media.downloadUrl` in the dataset and save it under `media.localName`, for example into `workspace/open-media/` (gitignored). Hash verification is exact: if a host replaces or transcodes a file, the check rejects it until independently re-reviewed. No network call occurs during validation or verification.

```bash
PYTHONPATH=src python -m kumiki_reference_lab open-footage validate
PYTHONPATH=src python -m kumiki_reference_lab open-footage list
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
```

The run's `sourceSha256` and `sourceTimebase` are checked. Numerical measurements were captured with NumPy 2.3.5 and FFmpeg 7.1.5, using image-motion threshold 0.01 normalized units/s and display-luma threshold 0.05/s. `open-footage verify-local` checks actual SHA-256, byte size, duration, resolution, stream and timebase; it does **not** confirm the rights statement from the external website, measure the style or verify that a reviewer watched the whole clip. A failed hash means stop and investigate, not automatically update the expected hash.

## Next research milestone

1. Add **source-PTS-preserving arbitrary start windows** to the bounded `analyze` workflow; the current 30-second maximum from zero truncates openings and biases style comparisons. Ensure one source remains one identity, with immutable source bytes and source-anchored times after seeking.
2. Inspect representative sections at normal playback speed with and without sound. Annotate discrete shots and deliberately separated styles, including titles vs. core animation, with abstention for ambiguous light/camera interpretation.
3. Add more genre-balanced, age/length/channel-matched samples and real audience snapshots for **those exact IDs**. Measure within-film variation and reviewer agreement before testing style/cadence differences; observational differences are not causal drivers of views.

Run the local regression suite before merging: `PYTHONPATH=src python -m unittest discover -s tests -q`. Keep high-cost multimedia tests out of hosted CI, but do not remove them.
