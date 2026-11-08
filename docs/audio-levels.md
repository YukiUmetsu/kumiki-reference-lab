# Original-audio-anchored level measurements

`audio-levels` is a local, subscription-free next step beyond [audio frame timing](audio-timeline.md). It uses FFmpeg's `astats` metadata to measure each **decoded audio frame's** root-mean-square (RMS) and peak signal level, then independently checks that frame against FFprobe's original audio PTS **and decoded sample count**.

```bash
kumiki-ref audio-levels reference.mp4 --max-seconds 10 \
  --max-frames 4096 --out runs/audio-levels/
```

The [versioned JSON report](../schemas/v1/audio-levels.schema.json) includes:

| Field | Meaning |
| --- | --- |
| `sourcePts`, `sourceSeconds` | FFprobe source audio PTS and its exact rational stream timebase |
| `decodedSampleCount`, `decodedDurationSeconds` | Decoded samples and their duration at the stream sample rate |
| `rmsDbFs` | Per-frame RMS energy in decibels relative to decoded audio full scale; `null` for negative infinity |
| `peakDbFs` | Largest sample peak in the frame, in decoded dBFS; `null` for negative infinity |
| `belowMeasurementFloor` | No finite RMS level reported by FFmpeg |
| `quietFrameCandidate` | Per-frame RMS is at or below −45 dBFS (or below the measurable floor), **not a confirmed silent passage** |

The analysis is at native decoded audio frame intervals, not a fixed 10-ms/50-ms loudness window. It does not recover LUFS, perceived loudness, spectral instruments, beats, silence segmentation, dialogue meaning, sound effect identity, quality or camera/edit intent.

## Why the clock check matters

FFmpeg's filter may use a different timebase from the source container. The program compares each reported filter presentation **time in seconds** with the FFprobe original-audio timestamp (tolerance: one decoded sample) and requires exact matching sample counts in strict frame order. If the filter introduces/reorders frames, resamples, drops packets or changes timing enough to break this relationship, the command **fails instead of manufacturing source-aligned results**. Encoder delay, priming and container offsets are retained in the source clock, not guessed from the video frame rate.

For video without audio, `status: no-audio-stream` and empty observations are returned. Negative-infinity levels are represented as JSON `null`, never `NaN` or `Infinity`. Inputs are limited to 30 seconds, 10,000 frames, bounded logs and timeouts.

## How to use this in cinematic study

- Plot RMS/peak alongside independently verified video cut candidates **only after** establishing the audio↔video timebase/offset mapping.
- Look for possible quiet holds, contrast jumps and impact neighborhoods. A low RMS value can represent sparse content, very quiet material or digital silence; it is not enough to label a narrator pause.
- Before recreating an effect in Kumiki UI, inspect audio at playback speed and add separate evidence-linked interpretation. Do not add SFX merely because an arbitrary amplitude threshold was crossed.
- Future work: multi-channel selection, explicit cross-stream presentation alignment, short-time envelope aggregation, onset and beat candidates, voice/speaker alignment and audiovisual contrast QA.

See [FFmpeg astats and metadata filter documentation](https://ffmpeg.org/ffmpeg-filters.html) for the measurement definitions. Review notes, not raw levels, will ultimately capture story or editing purpose.
