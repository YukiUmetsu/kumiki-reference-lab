# Source-linked audio energy research for What Ships

Promotional films are shaped by music, narration, silence, pauses, impact sounds and scene editing. The existing What Ships research schema measured *video pixels* but not the source soundtrack. `whatships-audio-measure` adds a deliberately narrower, verifiable **numeric PCM energy envelope** for operator-authorized local videos.

## Run

Bind one legitimate local video using the [private local media binding workflow](whatships-authorized-local-media.md), then:

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-audio-measure \
  "$HOME/whatships-private/media-bindings.json" \
  whatships:paper-mono-code \
  --window-seconds 10 --window-count 4

PYTHONPATH=src python -m kumiki_reference_lab whatships-all validate-analysis
PYTHONPATH=src python -m kumiki_reference_lab whatships-all research-report
git diff -- research/analysis/whatships
git add research/analysis/whatships
git commit -m "data: add source-linked PCM audio energy observations"
```

The command confirms the exact catalog ID, operator-attested source binding, SHA-256, video stream and rational timebase before decoding. Each requested interval is at most 30 seconds; one invocation processes at most six intervals. No model, transcript, identity, raw PCM or media file is saved. Results are merged into the matching versioned `research/analysis/whatships/<slug>.json` record, preserving prior browser notes and numerical visual measurements. Changing an existing numeric audio result requires explicit `--replace-existing`.

## Stored data

Under `evidence.numericAudio.windows[]`, each interval retains its source-requested start/end seconds, original audio stream index and start PTS/timebase, decoded mono PCM sample count and rate (8 kHz), and per-100 ms decoded PCM energy buckets:

- `rmsDbfs`: raw digital PCM root-mean-square signal energy relative to full scale
- `peakDbfs`: maximum absolute digital sample magnitude relative to full scale
- `nearSilence`: an energy-only heuristic, true when RMS is at most −48 dBFS
- `decodedOffsetMs`: position in the decoded PCM buffer, **not** independently verified original movie presentation timestamp
- Summary RMS, peak, and fraction of near-silence buckets

The repository rejects unsupported properties, transcription text, private paths, wrong source fingerprints, malformed durations, invalid audio window ordering and inconsistent RMS/silence flags. The offline browser and research-report command show **audio-derived numeric evidence separately** from verified original video-frame PTS.

## Interpretation limits

**dBFS is not LUFS** (perceived loudness). Energy changes do not establish a music beat, musical genre, instrument, sound effect, narration, voice, emotional effect, soundtrack source or camera-cut synchronization. In particular, FFmpeg output seeking and audio resampling are **not independently exact A/V source-PTS alignment**. Encoder priming, timing discontinuities and stream start offsets can shift the inferred audio location. The origin and timebase are recorded, but the workflow does not assert sample-accurate synchronization with image cuts.

With no audio stream, the probe fails as unmeasurable. It does **not** label the film silent. A fully silent decoded audio track has nonempty PCM samples and a floor of −120 dBFS. The analyzed intervals remain sparse rather than a full-movie audio review.

## Verification

```bash
PYTHONPATH=src python -m unittest tests.test_whatships_audio_measure -v
```

Tests include a **real locally generated MP4 with AAC sine-wave audio** to exercise FFmpeg/FFprobe extraction and Git corpus validation. Other cases verify pure-silence math, failed fingerprint checks, unknown/private properties, idempotent repeat processing and CLI behavior. These are original synthetic fixtures, not claims about the actual audio of third-party What Ships videos.
