# Original-PTS verified random-access video seek

**Implemented backend:** `backends.ffmpeg.source_seek` can inspect and decode a bounded interval **far beyond the first 120 seconds** without decoding the entire preceding video. This is a reusable lower-level decoder for future character analysis and video-reference coverage.

## API

```python
from fractions import Fraction
from pathlib import Path

from kumiki_reference_lab.backends.ffmpeg.source_seek import (
    probe_source_window,
    decode_rgb_source_pts_seek,
    detect_source_window_cuts_seek,
)

source = Path("./authorized-long-video.mp4")
window = probe_source_window(
    source, stream_index=0, timebase=Fraction(1, 10240),
    start_seconds=125, seconds=3,
)
chosen_pts = [window.frames[0].pts, window.frames[-1].pts]
rgb = decode_rgb_source_pts_seek(
    source, stream_index=0, expected_pts=chosen_pts,
    window=window, width=160, height=90,
)
cuts = detect_source_window_cuts_seek(source, 0, window=window)
```

The timebase and stream index in this example are **specific to one synthetic test clip**. Real callers must obtain them from `inspect_source` rather than guessing.

## Design

- FFprobe seeks near the requested start and inventories original decoded frame PTS in that range. Since keyframe-aligned seeking may start earlier, the window filter uses `(pts - first_opening_pts) × source_timebase` (exact rational arithmetic), not nominal FPS or approximate timestamp guesses. The probe interval includes a bounded guard for earlier keyframes.
- FFmpeg receives **input-side** `-ss start -copyts -t duration`, preserving the original stream PTS. A `select` filter chooses exact `pts` values and `showinfo` reports the actual decoded timestamp and timebase. The decoder **requires an exact match** to all expected FFprobe PTS and the source rational timebase; otherwise it fails closed. It never silently substitutes a nearby frame.
- Supports a requested 1–30-second window ending within the first **3600 seconds (1 hour)** of a video, with selected original timestamps, a max 24 output frames and up to 320×180 8-bit RGB data.
- A companion seek-based cut scanner exposes *candidate* hard-cut original PTS in the same window/timebase. A cut candidate is not a narrative truth.
- None of these functions downloads a model, transfers video, recognizes an individual or claims local VLM semantic quality.

## Constraints

- This is an **initial reusable backend**, not yet a change to `character-study-local` or `character-study-batch`. Those higher-level commands still use the verified source-prefix decoder and are currently capped at 120 seconds. Callers will migrate only after actual end-to-end tests pass.
- FFprobe's seek start depends on keyframe placement, and the bounded inventory may be incomplete on unusually long GOPs. The backend never claims exhaustive frame coverage. It fails if it cannot identify requested original timestamps.
- Stream-relative PTS is anchored to the *actual first decoded source frame*; it is not assumed to begin at zero.
- `-copyts` and decoded `showinfo` are essential to prevent timestamp renumbering. Input windows with nonmonotonic PTS, duplicate candidate timestamps or unrepresentable selected timestamps are refused.
- Selection, cut scanning and RGB frame verification are tested against a real **150-second, locally generated** MPEG4 clip. The test is synthetic, rights-free and low-cost; it does not prove behaviour for every codec, weird edit-list timestamp, audio desynchronization, HDR color pipeline or corrupted media.

## Verification

```bash
PYTHONPATH=src python -m unittest tests.test_source_pts_seek -v
```

The test generates an original tiny 150-second video via FFmpeg, accesses a **125–128-second window** without full-prefix decoding and verifies exact original PTS/timebase, decoded RGB buffers, absence of invented cuts, and failure on near-match timestamps. A later 141–143-second window is also inspected.

Next: wire this seek backend into selected-window character detection and every QA stage, retaining the existing prefix path as the conservative fallback.
