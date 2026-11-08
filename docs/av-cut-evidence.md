# Audio contrast around video cut candidates

`av-cut-evidence` links **measured** audio-frame levels to **candidate** video edit boundaries from an independently validated `analyze` bundle. It helps a reviewer find a transition where the original audio appears to get quieter or louder. It does **not** identify a sound effect, narration pause, musical beat, deliberate edit, or the intended emotional effect.

## Run it

Install FFmpeg and FFprobe, then create a verified video analysis bundle:

```bash
PYTHONPATH=src python -m kumiki_reference_lab analyze ./reference.mp4 \
  --max-seconds 10 --out ./runs

PYTHONPATH=src python -m kumiki_reference_lab av-cut-evidence ./reference.mp4 \
  ./runs/analysis-.../analysis-run.json \
  --window-ms 400 --max-audio-frames 4096 --out ./runs/audio-cuts
```

The first command prints the actual location of `analysis-run.json` (substitute it in the second command). The latter emits `av-cut-evidence.json`. Without `--out`, it prints JSON. `--window-ms` accepts 100–2,000; `--max-audio-frames` accepts 1–10,000. Analysis is limited to the run's first 1–30 seconds, and the audio-frame budget can reject an otherwise valid longer file.

The versioned format is [`schemas/v1/av-cut-evidence.schema.json`](../schemas/v1/av-cut-evidence.schema.json). See [`docs/audio-timeline.md`](audio-timeline.md), [`docs/audio-levels.md`](audio-levels.md), and [`docs/shot-evidence.md`](shot-evidence.md) for the underlying clocks, level measurements, and cut candidates.

## Precisely what is measured

1. Verify the existing video analysis bundle and its complete artifact inventory; recover original video frame PTS, timebase, and hard-cut *candidates*.
2. Independently decode original audio-frame timestamps and per-frame sample counts; measure FFmpeg `astats` RMS/peak dBFS; cross-check filter timestamps and decoded sample counts against the source stream. Reject mismatches.
3. Verify both analyses refer to the *same file bytes* by SHA-256. Source identity does not independently verify cross-stream synchronization.
4. For each boundary after the first video region, convert the original video and audio timestamps to **rational presentation seconds** using each stream's own timebase. Collect audio frames wholly inside the chosen time window immediately **before** and **after** the video boundary; exclude any frame straddling that boundary.
5. For each side, report decoded-frame count, quiet-frame count and fraction, median finite RMS, maximum finite peak, and first/last original audio PTS. A quiet-frame **candidate** has RMS below -45 dBFS or is below the measurement floor (negative infinity).
6. Mark a **candidate quiet-level contrast** only when both sides have at least two wholly contained decoded audio frames and quiet-frame fractions differ by at least 0.5. Otherwise report insufficient frames or no strong contrast. This is a deterministic discovery heuristic, not a confidence score, acoustic classifier, artistic judgment, or statistical significance result.

Example excerpt (values are illustrative, **not** from an actual source):

```json
{
  "status": "candidate-cross-stream-pts-association",
  "clockRelation": "candidate-same-container-source-presentation-seconds-no-independent-sync-verification",
  "videoCutCandidateCount": 1,
  "qualityVerdict": "not-performed",
  "cutCandidates": [
    {
      "videoRegionId": "region-002",
      "status": "candidate-quiet-level-contrast",
      "before": { "frameCount": 3, "quietFrameFraction": 0.0 },
      "after": { "frameCount": 3, "quietFrameFraction": 1.0 },
      "interpretationStatus": "not-verified"
    }
  ]
}
```

The actual schema requires all fields, including exact rational cut positions and audio PTS. The excerpt deliberately omits them for readability.

## Limits and reviewer checklist

- **Source-clock hypothesis:** Original stream PTS expressed in seconds are tentatively compared in the same media container. They may still have offsets from priming, edit lists, discontinuities, timestamp resets, transcoding, or decoder differences. This tool neither independently recovers a physical common clock nor calibrates synchronization. A source hash proves identity, **not** sync. Comparisons must remain hypotheses until separately verified.
- **Short bounded scan:** The input may be longer than the analyzed first seconds. The analysis window is not the film's complete structure; cuts near either end may have insufficient measured audio coverage.
- **Audio signal vs semantics:** A quiet reading may be ambience, soft speech, music, a fade, a silent soundbed, or decoding behavior. A loud reading does not establish a sound effect or narrative emphasis. Quiet fractions weight **decoded frames**, not time; frames can have different sample counts.
- **Cut candidates:** Abrupt visual changes can be motion or flashes, and missed edits remain possible. This tool does not prove a real cut or causal audio/video relationship.
- **No playback certification:** Quality, emotional clarity, and production-level craft require listening and watching the source at actual speed. The report is evidence to guide the reviewer.
- **No rights expansion:** Do not redistribute or recreate source audiovisual content merely because a reference report exists.

The coding agent should not upgrade a candidate into a `verified`, `synchronized`, `intentional`, or `premium` claim without new independent evidence and an explicit review step. Do not send the expensive FFmpeg integration suite to hosted CI; run locally (`PYTHONPATH=src python -m unittest discover -s tests -q`) while the hosted workflow stays a small smoke suite.
