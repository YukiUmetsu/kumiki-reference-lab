# Source-PTS visual measurements for What Ships footage

`source-visual-probe` measures **actual decoded video pixels** and candidate shot boundaries in a bounded interval of a locally available, authorized video. It works for live-action, stylized 2D, paper-cut, UI/screen recordings, 3D animation, and other formats because it does not depend on subject or character detection.

This adds a useful **objective baseline** alongside the local vision-language character analysis. However, it is not automatically a verified cinematography annotation: apparent image motion is **not proof of camera movement**; display brightness is **not physical scene lighting**, and FFmpeg cut detections are hypotheses that need review.

## Run on any authorized video

```bash
# Early part of a short reference clip
PYTHONPATH=src python -m kumiki_reference_lab source-visual-probe \
  "$HOME/Videos/authorized/launch.mp4" \
  --start-seconds 0 --max-seconds 10 --max-samples 12 \
  --out "$HOME/whatships-private/probes/opening"

# A later scene, without reading the preceding 125 seconds
PYTHONPATH=src python -m kumiki_reference_lab source-visual-probe \
  "$HOME/Videos/authorized/launch.mp4" \
  --start-seconds 125 --max-seconds 10 --max-samples 12 \
  --out "$HOME/whatships-private/probes/later"
```

Use `--rights-status user-declared-authorized` only for footage you are permitted to study. This is an explicit declaration, not independent legal verification.

The output `visual-probe.json` records:

- Exact original video bytes SHA-256, video stream index and rational source timebase. Every sampled PTS is FFprobe-derived and the decoded frame's timestamp is independently verified by FFmpeg.
- Candidate cut PTS from FFmpeg's scene-difference filter. Counts per **requested sample window**, not an asserted whole-film editing frequency.
- Per-frame normalized display RGB mean, Y-prime display luma proxy, luma spatial standard deviation, RGB-derived saturation, fraction of shadow-ish display pixels and very bright display pixels.
- Per-adjacent-sampled-frame mean absolute display RGB change, including delta per original source time. Comparisons spanning a cut candidate explicitly abstain rather than treating the editing transition as smooth motion.
- Honest window metadata: starting source seconds, requested seconds, actual sampled PTS count, selected decoder, original timebase and the sampled-frame span.

## Technical limits

- The analysis processes **real 8-bit RGB frames**, scaled to at most 320×180, and uses a maximum of 24 timestamps per window. Frame metrics are computed from every decoded pixel at that resolution with standard-library Python; no neural API, NumPy dependency, subscription or media upload is required.
- Windows ending in the first 120 seconds use exact source-PTS prefix+ordinal decoding. Later windows use input-side seek with `-copyts` and exact FFprobe/FFmpeg PTS matching, up to a 3600-second source-relative endpoint.
- RGB pixels are display-referred conversions, not calibrated scene-linear luminance, true exposure or captured physical brightness. An increase in mean display luma could be an edit, flash, content change, animation effect or color-grade adjustment, not necessarily a light moving.
- Mean RGB difference is **not optical flow**: it does not establish camera pan, camera zoom, dolly, actor movement, parallax or object motion. Highly animated graphics, a changing screen recording, cuts, or a fade can all elevate it.
- Candidate cut frequency is **not** a verified film-wide average; there may be unobserved edits, stylized transitions, keyframe/seek omissions or threshold false positives.
- Camera height, angle, lens, lighting fixture, paper-cut construction, actual 3D geometry, narration and dialogue are **not inferred** by this numeric tool. They require image/media grounded visual interpretation or human-coded evidence.
- A sparse frame sample cannot establish full video coverage or professional-quality production technique by itself. The separate What Ships [full catalog](whatships-full-coverage.md), [local media binding](whatships-authorized-local-media.md) and [character worker](whatships-resumable-local-analysis.md) record distinct stages and evidence.

## Tests

```bash
PYTHONPATH=src python -m unittest tests.test_source_visual_probe tests.test_source_pts_seek -v
```

The tests generate original FFmpeg synthetic red/blue frames and verify that a true color change, cut candidates, source PTS and dark/bright pixel statistics flow into the report. The shared **150-second generated video** validates a real later 125–128-second seek and original PTS precision.

Next: integrate each verified local What Ships character-study window with this source-timecoded numeric probe and aggregate only metadata supported by actual pixels, leaving camera/light/art-direction interpretation for the reviewed technique timeline.
