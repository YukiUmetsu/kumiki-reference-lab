# Audio census: numeric sound evidence

The dataset already measures picture. Sound is a separate axis of motion-design
craft, so this lane adds a numeric audio census: for each clip it re-downloads
the public rendition, extracts only the audio stream, measures level, dynamics
and temporal structure, writes the numbers, and deletes both the media and the
extracted PCM.

The engine is `kumiki_reference_lab.acquisition.audio`; the corpus driver is
`scripts/audio_census.py`. The engine knows nothing about any website.

## Pipeline

For each evidence record under `research/analysis/<site>/videos/`:

1. Resolve the upstream URL from the record (falling back to the site catalog
   for stale signed URLs), exactly as the cut census does.
2. Download once into a caller-owned `TemporaryDirectory`, with the same
   byte/duration caps and the same cookie-free yt-dlp path for YouTube.
3. Verify the observed container duration against the record's
   `source.durationSeconds` within **1 second**. A larger difference is a
   `duration-mismatch` skip; the media is deleted either way.
4. Extract the first audio stream to raw mono 8 kHz signed 16-bit
   little-endian PCM (`-vn -ac 1 -ar 8000 -f s16le`).
5. Run `ffmpeg -af ebur128=peak=true -f null -` for the integrated loudness,
   loudness range, true peak and per-100 ms momentary values.
6. Measure the PCM with the standard library.
7. Write `research/analysis/<site>/audio/<id>-<slug>.json` atomically.
8. Delete the downloaded media and the PCM in a `finally` block.

No media bytes enter the evidence tree. `mediaRetained` is always `false`.

## Commands

```bash
# Offline tests
PYTHONPATH=src python -m unittest tests.test_audio tests.test_public_acquisition -q

# Stratified live sample: 40 records from each site
PYTHONPATH=src python -u scripts/audio_census.py \
    --root research/analysis \
    --sample-stratified 40 \
    --sites shots,promonews,motiondesignawards \
    --acknowledge-rights --jobs 2 --delay-seconds 1.0 \
    --yt-dlp /Users/yukiumetsu/.local/share/kumiki-tools/ytdlp-venv/bin/yt-dlp

# Re-measure existing records
PYTHONPATH=src python scripts/audio_census.py --acknowledge-rights \
    --site promonews --refresh
```

`--sites a,b` and the repeatable `--site a --site b` are equivalent.
`--sample-stratified N` picks the centre of each equal-width slice of the
ordered record list, so a sample is spread across the catalogue instead of
taking the newest records. `--limit` caps the work after sampling. `--resume`
is the default; `--refresh` re-measures.

Every record needs `--acknowledge-rights`: public availability is not a licence.
The driver supplies a research-use attestation and records
`rightsStatus: review-required`.

## What is measured

All values are numbers from the audio signal or from ffmpeg's EBU R128 filter.
No field asserts meaning.

### Level

| field | exact definition |
| --- | --- |
| `integratedLufs` | EBU R128 integrated loudness from ffmpeg's summary (`I:`), in LUFS |
| `loudnessRangeLu` | EBU R128 loudness range (`LRA:`), in LU |
| `truePeakDbfs` | EBU R128 true peak (`Peak:`), in dBFS |
| `samplePeakDbfs` | largest absolute PCM sample, `20·log10(peak/32768)`, floored at -120 dBFS |
| `rmsDbfs` | whole-stream RMS, `20·log10(rms/32768)`, floored at -120 dBFS |
| `silenceFraction` | fraction of 20 ms analysis frames whose RMS is below **-50 dBFS** |
| `headSilenceSeconds` | duration of the leading run of silent frames |
| `tailSilenceSeconds` | duration of the trailing run of silent frames |

A clip that is silent throughout reports its full duration for both head and
tail silence, because both statements are true of the signal.

### Dynamics

`shortTermLufsSeries` is one value per whole second: the **last** momentary
loudness (`M:`) ffmpeg reported inside that second, rounded to one decimal. A
second with no momentary report is `null`. ffmpeg's -120.7 LUFS filter floor is
recorded as **-70 LUFS**, the absolute gate, so a silent interval stays
representable without dominating a least-squares fit.

| field | exact definition |
| --- | --- |
| `shortTermRangeLu` | maximum minus minimum of the non-null per-second series |
| `loudnessSlopeLuPerMinute` | least-squares slope of the series (seconds → LUFS), multiplied by 60 |
| `loudnessSlopeR2` | coefficient of determination of that fit; `null` when the series has no variance |
| `firstHalfVsSecondHalfLu` | mean of the second half of reported values minus the first half; signed |

Because the -70 LUFS floor is included, a silent head or tail contributes a
very low value. A clip that fades to silence can therefore show
`shortTermRangeLu` near 60-70 LU and a large negative
`loudnessSlopeLuPerMinute`; both are descriptions of the stored series, not
judgements about a fade.

### Temporal structure

The PCM is cut into consecutive non-overlapping 20 ms frames (160 samples at
8 kHz). Each frame's RMS level in dBFS forms the envelope; the rise at frame
`i` is `level[i] - level[i-1]`.

**Onset definition.** A frame is an onset when

1. its rise **exceeds** a local adaptive threshold — the median of the
   positive rises in the previous ~1 s (50 frames) multiplied by 1.5, with a
   floor of 2 dB — and
2. the next 80 ms (4 frames) contains **no larger** rise. The look-ahead is
   clipped at the end of the clip.

The threshold uses prior frames only, so the detector is causal and
deterministic. It is a novelty detector for the amplitude envelope, not a beat
tracker.

| field | exact definition |
| --- | --- |
| `onsetCount` | number of onsets |
| `onsetTimesSeconds` | onset frame index × 20 ms |
| `onsetsPerMinuteOfRuntime` | `onsetCount × 60 / audioDurationSeconds` |
| `onsetRateSeries` | counts and rates per 5 s bucket (`startSeconds`, `endSeconds`, `onsetCount`, `onsetsPerMinute`) |
| `onsetRateTrend` | first third vs last third of the 5 s buckets: `accelerating` above +15%, `decelerating` below -15%, else `steady` |
| `medianOnsetGapSeconds` | median inter-onset interval; `null` under two onsets |
| `regularityIndex` | `1 - (population SD of inter-onset intervals / mean interval)`, clamped to [0, 1]; `null` under 8 onsets |
| `tempoHypothesisBpm` | periodicity hypothesis from onset-envelope autocorrelation, 60–200 BPM search |
| `tempoConfidence` | normalized autocorrelation coefficient at the reported lag, clamped to [0, 1]; not a probability |

### Tempo caveat

`tempoHypothesisBpm` is a **periodicity hypothesis about the onset envelope**.
It is not a beat grid, not a music-only detector, and not evidence that a clip
has music. The envelope keeps frame rises of at least 2 dB; the search covers
lags corresponding to 60–200 BPM (0.3–1.0 s), and the reported value is the lag
with the highest normalized autocorrelation. When several lags correlate within
0.01 of the peak, the shortest (fastest) is reported, because octave
(half/double tempo) is inherently ambiguous. Speech, ambience and repeated
sound effects can produce a false periodicity; a low `tempoConfidence` means
the periodicity is weak, not that the clip is fast or slow music.

## No numpy

The analysis is stdlib-only (`array`, `math`, `statistics`). The base package
has no numpy dependency and must not gain one. PCM is read with
`array("h").frombytes(...)`; frame RMS, least-squares fits, autocorrelation and
medians are plain Python.

## Retention and hashes

- The downloaded media and the extracted PCM are both deleted in a `finally`
  block; the media lives only inside a `TemporaryDirectory`.
- Every record stores `source.mediaSha256Observed` and
  `shaMatchesRecord` (`true`, `false`, or `null` when the source record had no
  stored hash).
- `false` is **expected, not an error**, for yt-dlp re-encodes and for any
  rendition that differs from the bytes the earlier lane measured. The
  mismatch is recorded as a fact.
- `mediaRetained` is always `false`.

## Schemas and skips

| artefact | schema |
| --- | --- |
| record | `kumiki.<site>-audio-evidence.v1` |
| index | `kumiki.<site>-audio-index.v1` |

Pre-download and post-download skips use these reasons:

- `missing-url` — the record and catalog carry no playable URL
- `unsupported-url` — the URL fails the caller's allowlist policy
- `duration-exceeds-limit` — recorded duration exceeds `--max-duration-seconds`
- `size-exceeds-limit` — recorded size exceeds `--max-file-bytes`
- `no-audio-stream` — the downloaded rendition has no audio stream
- `duration-mismatch` — observed duration differs from the record by more than 1 s
- `unreadable-record` — the evidence JSON cannot be parsed
- `resume-existing-record` — an audio record already exists (`--resume`)

A missing audio stream is a skip, never a zero-valued measurement.

## Non-claims

The audio census does **not**:

- separate speech from music, or report a speech/music ratio;
- transcribe dialogue or recognise speech;
- identify instruments, sound sources, genres or moods;
- judge mix quality, loudness compliance, clarity or aesthetics;
- claim that a sound event is synchronised to a picture event;
- identify the work, its authorship, intent or style from sound.

`limits` on every measurement repeats these non-claims so they travel with the
numbers. A `tempoHypothesisBpm` value is a periodicity hypothesis, not a BPM
claim about the work. Numerical evidence is not a verdict.
