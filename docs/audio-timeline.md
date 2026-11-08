# Original audio clock and frame timing

Premium motion graphics are designed with narration, music, transitions and sound effects. Before detecting beats, dialogue pauses or impacts, we must know what the source audio stream actually timestamps. The local-only `audio-timeline` command provides that measurement without guessing alignment from video FPS.

```bash
kumiki-ref audio-timeline reference.mp4 --max-seconds 10 --max-frames 4096 \
  --out runs/audio-reference/
```

The output is `audio-timeline.json`, validated by [`schemas/v1/audio-timeline.schema.json`](../schemas/v1/audio-timeline.schema.json). It records the input's source SHA-256, chosen original audio stream index, stream timebase, sample rate, channel count, bounded decoded audio frame PTS, and the actual sample count reported for each decoded frame.

For each frame:

- `sourcePts` is the **decoded audio stream's original PTS**, from FFprobe's best-effort timestamp (with an explicit fallback). It is *not* a video-frame number or a guessed wall clock.
- `sourceSeconds` multiplies that PTS by the audio stream's rational timebase.
- `decodedSampleCount` and `decodedDurationSeconds` use sample count and sample rate; they do **not** imply an uninterrupted interval through the next audio frame or prove there was audible sound.
- `ptsAnomalies` explicitly records missing or non-increasing source PTS and missing sample count.

The first selected audio stream is used. A file with no audio returns `status: no-audio-stream` and empty frame evidence rather than fabricated silence. Files with malformed audio clock metadata fail with a clear error. Scanning is limited to 1–30 seconds and up to 10,000 decoded frames; output and subprocess time are bounded.

## What it does *not* measure yet

This command does **not** detect sound intensity, musical beats, speech, pauses, silence, speakers, SFX events, acoustic quality or sync to a visual cut. Audio and video streams may have different timebases and start offsets; do not substitute audio PTS into video PTS or claim frame-accurate alignment without an explicit clock transform. Real-world containers can have encoder delay, priming, discontinuities and missing timestamps. A future RMS/onset/silence analyzer should first link its decoded sample positions to this verified original audio clock, preserve ambiguous gaps, and test against known synthetic A/V delays.

The technique and shot galleries remain visual evidence only. Audio interpretation should be a separate auditable stage before using perceived musical emphasis or silence to explain a story beat. FFprobe's [official frame and stream selection documentation](https://www.ffmpeg.org/ffprobe.html) is the reference for the underlying timestamp query.
