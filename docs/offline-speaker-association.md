# Offline speaker diarization association (RTTM)

**Implemented:** \`speech-associate\` accepts a \`speech-transcribe\` output directory and a **locally obtained RTTM** speaker-diarization file for the *same decoded audio*. It associates ASR utterances with stable voice-cluster IDs when one cluster covers enough of the utterance and competing speakers do not. It does **not** perform diarization itself, identify a real person, recognize a visible character, or determine gender, age, ethnicity or who lip-syncs.

## Workflow

First generate ASR speech observations with a locally installed Whisper.cpp model (see [local speech transcription](local-speech-transcription.md)).

An offline diarization tool such as pyannote.audio can produce RTTM segments, **provided they refer to exactly the audio waveform and time origin extracted by the speech run**. Ensure the diarizer receives the same start-of-audio, channel mix, sample rate and trim; do not assume RTTM generated from a differently trimmed WAV has matching offsets. The previous \`speech-transcribe\` stage discards its temporary WAV for data-minimization, so preserving a matching local input to your diarizer is currently the operator's responsibility. Until a shared-audio export workflow is implemented, independent RTTM must be manually checked.

Example RTTM (synthetic):

\`\`\`text
SPEAKER demo 1 0.00 1.30 <NA> <NA> speaker_A <NA> <NA>
SPEAKER demo 1 1.45 1.60 <NA> <NA> speaker_B <NA> <NA>
\`\`\`

\`\`\`bash
PYTHONPATH=src python -m kumiki_reference_lab speech-associate \
  ./runs/speech-reference-01 ./speaker-output.rttm \
  --out ./runs/speech-with-voices-01

PYTHONPATH=src python -m kumiki_reference_lab character-scene report \
  ./runs/speech-with-voices-01/character-scene.json
\`\`\`

### Evidence policy

- Uses exact rational arithmetic across RTTM decimal seconds, original audio start PTS and source video PTS, without frame-rate guesses.
- Defaults to **at least 80% single-cluster coverage** and **at most 10% competing-cluster coverage** of each transcript segment. Adjust via \`--min-coverage\` and \`--max-competing\`, if you have a validated diarizer.
- Same-speaker interval overlaps are unioned so duplicate diarizer segments cannot inflate coverage. Different speaker overlaps are retained as conflicts.
- Ambiguous or overlapping dialogue remains \`speakerId: null\`, with \`speakerEvidence: unknown\`. The word timing available from segment-level Whisper.cpp ASR cannot split a single segment across multiple speakers.
- Accepted assignments are **\`voice-only\`** characters with local, stable IDs (\`voice_001\`, \`voice_002\`). They are *voice clusters*, not named persons or visual characters.
- The source/model SHA-256, source clocks and actual decoded audio window must match the prior speech run. RTTM content receives its own SHA-256. Invalid input or failures do not publish partial output.
- Writes a new directory with \`character-scene.json\` and \`speaker-association.json\` including per-utterance top and competing coverage and explicit unverified evidence status.
- Requires a previously unattributed ASR scene; never overwrites a human-reviewed or visually annotated character scene.

### Limitations and next priorities

RTTM models can misclassify simultaneous speech, music, dubbing and acoustically similar voices. Numeric overlap is **only a clock-based association**, not proof the underlying speaker clusters are correct. The source-to-audio alignment still inherits the ASR clock caveat (codec delay / timestamp discontinuities).

**Next:** preserve an opt-in exact decoded audio artifact or auditable waveform fingerprint for the diarization pipeline; run local diarization automatically with explicit model provenance; add detected visual characters and active-speaker/lip-motion evidence; join acoustic clusters with visible characters only when video evidence confirms it.

The repository has no rights to download What Ships content or infer actual personal identities from playback alone.