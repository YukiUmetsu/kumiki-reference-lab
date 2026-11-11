# Timestamped apparent image motion in real source videos

`whatships-measure --image-translation` extends actual original-source-PTS RGB/cut measurements with a separately labeled **global image-plane translation proxy**. It reuses the existing Kumiki FFT phase-correlation implementation and the exact sampled RGB frames; no additional source-video download or neural API is required.

## Usage

Install the existing optional NumPy motion dependency (`pip install -e '.[motion]'`) before enabling this feature.

```bash
# Numeric source-frame research written directly to Git
PYTHONPATH=src python -m kumiki_reference_lab whatships-measure \
  "$HOME/whatships-private/media-bindings.json" \
  whatships:paper-mono-code \
  --image-translation --window-seconds 10 --window-count 4

# Continue into disjoint, previously unobserved video intervals
PYTHONPATH=src python -m kumiki_reference_lab whatships-measure \
  "$HOME/whatships-private/media-bindings.json" \
  whatships:paper-mono-code --fill-gaps --image-translation

# Apply the same option to a bounded category-balanced cohort
PYTHONPATH=src python -m kumiki_reference_lab whatships-measure-batch \
  "$HOME/whatships-private/media-bindings.json" \
  --max-videos 4 --image-translation

# Measure a single non-What-Ships local video without writing it to the catalog
PYTHONPATH=src python -m kumiki_reference_lab source-visual-probe \
  "$HOME/Videos/authorized/reference.mp4" \
  --image-translation --out "$HOME/research/probe-001"
```

An authorized, publicly accessible original X post may also be studied with `whatships-acquire-measure --image-translation`; that workflow deletes temporary footage and keeps only source-linked, validated numeric results in Git. The original film's access and rights must still be established.

## What the data say

Each supported `evidence.numericVisual.windows[].sampledFramePairs[]` now optionally has an `imageTranslation` object:

- `status`: `measured-image-translation`, `ambiguous-correlation`, `unobservable-low-texture`, or `cut-boundary`
- `dxPixels`, `dyPixels`: relative **image-plane** translation at the bounded decoded resolution, or null when no reliable proxy can be measured
- `peakToSidelobeRatio`: phase-correlation peak diagnostic; **not** a calibrated probability or scientific confidence interval
- `startPts`, `endPts`, `sourceDeltaSeconds`: actual original video-frame presentation timestamps and exact rational elapsed interval, in the enclosing pair

The measured image transform is checked for numeric finiteness and bounded displacement. If an FFmpeg hard-cut candidate lies between sampled frames, the tool stores `cut-boundary` with null displacement rather than calling the motion routine across a cut. Existing RGB/cut/brightness records stay compatible even if they have no image-translation evidence.

The offline What Ships browser shows apparent global shift counts per measured interval; unprobed windows say **not probed**, not zero. The cross-video research rollup separately counts probed windows and source-frame pairs for which a global shift was measured.

## Interpretation boundaries

These data are useful to distinguish *static-looking image intervals* from *intervals with coherent image-plane changes*, but **cannot establish camera pan, tilt, dolly, zoom, parallax, actor/object motion, 3D camera transformation or editorial intent**. Camera motion would require a separately validated scene geometry model or robust foreground/background segmentation. Refractive effects, screen recordings, object animation, transitions and compositing can all produce global image shifts.

Phase correlation assumes approximate global translation and textured scenes. Low texture, cuts, independent moving subjects, zoom and heavy parallax can yield ambiguous or absent results; they do not imply that the original camera was stationary. Motion is measured only between sparse sampled frames and cannot support a whole-film motion-frequency claim unless sampling and uncertainty are independently accounted for.

The implementation stores only source-linked numeric outcomes and uses the already bounded original-video sample pipeline. No video, image, source audio, creator identity or private local file path is included in Git.

## Tests

```bash
PYTHONPATH=src python -m unittest tests.test_source_visual_translation \
  tests.test_whatships_direct_measure -v
```

Tests cover real generated FFmpeg red/blue cut gating, strict numeric source validation and privacy, mocked deterministic shift persistence into Git, and (when optional NumPy is installed) a known synthetic translated textured frame. Real third-party What Ships video analysis is not claimed by these synthetic tests.
