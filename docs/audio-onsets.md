# Source-timed audio attack candidates

`audio-onsets` finds **possible sudden level attacks** in already supported FFmpeg RMS/peak measurements. This is a deliberately inexpensive, deterministic step toward understanding when sound may accent a visual transition. It is **not** musical beat tracking, spectral onset analysis, speech recognition, SFX identification, or proof of audiovisual sync.

```bash
kumiki-ref audio-onsets reference.mp4 --max-seconds 10 \
  --min-rise-db 12 --min-peak-dbfs -40 --cooldown-ms 120 \
  --out ./runs/audio-onsets
```

The command verifies the audio frame timestamps and decoded sample counts using the existing [`audio-levels`](audio-levels.md) pipeline. It adds no model download, subscription, network call or new runtime dependency. Inputs remain bounded to 30 seconds / 10,000 decoded frames.

## Detection method

1. Traverse adjacent source-PTS-aligned decoded audio frames in their original order.
2. Require frame continuity to within **one source audio sample**. Skip cross-gap pairs; a timestamp jump is not a detected acoustic attack.
3. Compare the later frame's decoded RMS dBFS against the previous one. By default a positive rise of at least **12 dB** counts only when the later frame's peak is at least **−40 dBFS**.
4. When the previous RMS is negative infinity (reported as `null`), record a distinct `level-return-from-measurement-floor` event. There is **no measured finite dB rise** in that case; `measuredRmsRiseDb` stays `null`.
5. Suppress additional candidates occurring within 120 ms after the last accepted candidate; count suppressed threshold-passing pairs separately.

Thresholds are user-tunable **heuristics**, not calibrated probabilities or classifications. Higher `--min-rise-db` emphasizes abrupt attacks, and a higher `--min-peak-dbfs` rejects quieter candidates. Frame size varies with codecs: one event represents a level change between **two decoded frame envelopes**, and cannot resolve individual samples inside a frame.

## Report contract

See [`schemas/v1/audio-onsets.schema.json`](../schemas/v1/audio-onsets.schema.json). The output `audio-onsets.json` includes:

| Field | Interpretation |
| --- | --- |
| `sourceSha256`, `audioStreamIndex`, `sourceTimebase` | Original media/stream provenance, never a synthetic video frame clock |
| `anchorSourcePts`, `anchorSourceSeconds` | The *later decoded audio frame's start*, not a claim of exact sound onset time |
| `supportWindow.startSeconds/endSeconds` | Conservative two-frame time span containing the measured rise |
| `previousRmsDbFs`, `currentRmsDbFs`, `currentPeakDbFs` | Raw envelope observations used to accept a candidate |
| `measuredRmsRiseDb`, `floorAssisted`, `signal` | Measured positive dB rise versus nonnumeric return from below measurement floor |
| `eligibleAdjacentFramePairs`, `discontinuityRejectedPairs` | Coverage and discarded clock gaps |
| `aboveThresholdPairCount`, `cooldownSuppressedPairCount` | How many pairs met the signal threshold and how many were suppressed |
| `interpretationStatus: not-verified`, `qualityVerdict: not-performed` | No music, SFX, story-purpose or premium-quality verdict |

`status: no-audio-stream` yields **zero candidates**, not a fictional silence event. A source with audio but unreliable timestamps or failed decoding produces an error, never a no-audio fallback.

## Using it in filmmaking research

- Audition the actual audio around each candidate in the original source. Possible explanations include a musical attack, voice entrance, impact, abrupt mix change or recording artifact.
- Compare with candidate video cuts only after reviewing the audio/video presentation-clock relationship. Shared source file hashes alone do not prove physical synchronization.
- Record human/AI interpretations as separate `review-notes` annotations. Never promote an event to a "verified cinematic SFX" from level changes alone.
- When proposing original Kumiki animation or sound design, specify the **intended causal moment**, output render timebase, tolerance and alternative if source event timing remains uncertain.

This technique is intentionally simple and transparent. Future spectral-flux, multiband transients, ASR, beat hypotheses and speaker labels should be added as separately versioned optional analyzers with known synthetic fixtures, not retrofitted into the interpretation of these RMS candidates.

The same audio attack candidates appear on the [offline visual timeline](timeline-review.md) as green diamond markers and an evidence table. The timeline reuses one audio-level measurement for both near-cut quietness and level attacks.

## Verification

`PYTHONPATH=src python -m unittest tests.test_audio_onsets -v` exercises known tone entrances, no-audio files, timestamp gaps, floor transitions, cooldown and strict thresholds. The FFmpeg integration tests remain local; hosted CI continues running only the small smoke suite.
