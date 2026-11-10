# Optional local speech transcription to character scenes

The `speech-transcribe` command runs a **locally installed** [whisper.cpp](https://github.com/ggml-org/whisper.cpp) CLI model against an **authorized, local video file**. It extracts a bounded mono 16 kHz WAV via FFmpeg, invokes `whisper-cli` with a model file already on disk, and converts whisper.cpp's millisecond segment offsets into the original **video PTS clock**.

This is the first **automatic** semantic data producer for `character-scene`. It transcribes words, **not** who spoke, what anyone looks like, ethnicity, age, actions, gestures or lip-sync. All speaker IDs are `null`, speaker evidence is `unknown`, and confidence is conservatively `low`. The result must be reviewed against source media before creative/identity claims.

## Usage

Install FFmpeg/FFprobe and whisper.cpp separately, and provide your own local whisper.cpp model (no models are downloaded by Reference Lab).

```bash
PYTHONPATH=src python -m kumiki_reference_lab speech-transcribe \
  ./reference.mp4 --model ./models/ggml-small.bin \
  --whisper-cli ./whisper.cpp/build/bin/whisper-cli \
  --max-seconds 60 --language auto \
  --out ./runs/speech-reference-01

PYTHONPATH=src python -m kumiki_reference_lab character-scene report \
  ./runs/speech-reference-01/character-scene.json
```

Outputs are an **atomic, new-only directory** with `character-scene.json` and `speech-manifest.json`. The manifest records media/model SHA-256, audio stream index and start PTS, audio/video source timebases, requested window, **actual decoded PCM sample count**, assumed alignment and number of segments. The scene window ends at the **real extracted audio duration**, rather than assuming a short video yielded the entire requested scan. WAV and raw whisper.cpp JSON are temporary and discarded. Existing output directories are never overwritten.

Bounds: first 1–120 seconds, local video extensions only (`.mp4`, `.m4v`, `.mov`, `.mkv`, `.webm`, `.avi`), a local nonempty model, bounded memory/disk/output JSON and process timeouts. It does not read remote URLs, playlists or X/What Ships video pages. The source and model are checked for modification before the result is published. Tool failure publishes no partial result.

## Exact and uncertain timing

The pipeline reads the original audio stream `start_pts` and `time_base` from FFprobe, and the original video stream timebase from existing `inspect_source`. Whisper.cpp's `offsets.from/to` are **integer milliseconds relative to extracted audio**, which are converted to video timebase ticks using rational arithmetic. This is not a mapping through estimated FPS. An offset cannot be used if original audio stream start PTS is absent.

**Limitation:** The mapping assumes the first decoded audio sample corresponds to FFprobe's audio `start_pts`. Codec priming/encoder delay and media discontinuities are not calibrated. This is a useful candidate A/V clock, **not source-verified lip synchronization**. ASR may hallucinate over music or noise. Silence or an empty transcription does not prove the absence of dialogue; a bounded scan does not certify whole-video coverage.

Real speaker diarization, audio/visual active-speaker association, shot-grounded character tracking, multi-person action recognition and source-media validation remain **not implemented**. The normalized scene output allows those producers to be added separately without changing the CLI consumer.

## Validation

Focused unit tests use synthetic media and stub command outputs to validate source PTS mapping, malformed transcript rejection, no arbitrary network playlists, fail-closed behavior and unknown speaker attribution. An end-to-end locally generated MP4 + simulated whisper-cli JSON integration smoke test validates FFmpeg extraction and container PTS handling, **not model transcription accuracy**. Full ASR model tests require locally installed models and authorized media.