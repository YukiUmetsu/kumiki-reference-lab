# Platform-neutral online video studies for agents

The `kumiki-watch` command accepts an **HTTPS video URL on any public website**
(YouTube, TikTok, Vimeo, PeerTube, X, a studio site, or a new host).
There is **no website or provider allowlist**. The external `yt-dlp` extractor
determines whether each host can actually deliver a video without credentials.
A URL that plays in your browser is not necessarily extractable.

## Installation

```bash
python -m pip install -e .
brew install ffmpeg yt-dlp        # macOS; use equivalent system packages elsewhere
# Optional: start a local Ollama server with a vision-capable model.
```

The workflow uses only Python's standard library plus the repository's
existing FFmpeg/Ollama adapters. `yt-dlp` is an external command, not an
embedded Python dependency. A local vision-capable model is needed for
characters, text treatments and stylistic hypotheses; numeric measurements
do not require AI.

## Analyze one reference

```bash
kumiki-watch 'https://example.com/watch/demo' \
  --repo . \
  --rights-basis written-permission \
  --rights-note 'The rights owner authorized downloading this video for analysis.' \
  --acknowledge-rights \
  --model 'YOUR_LOCAL_VISION_MODEL' \
  --max-seconds 180 \
  --max-frames 10800 \
  --semantic-stride 24 \
  --max-semantic-frames 24

# Also available without installing console entrypoints:
PYTHONPATH=src python -m kumiki_reference_lab.pipeline.online_study \
  'https://example.com/watch/demo' \
  --rights-basis permissive-license \
  --rights-note 'Publisher distributes this video under a permissive license.' \
  --acknowledge-rights
```

`--model` is optional. Omit it to collect numerical frame evidence only.
`--overwrite` intentionally replaces a previous record for the same URL.
Source changes can be detected by comparing source SHA-256. Use a vision model
capable of understanding images. `--port` selects local Ollama's port.

To inspect more video, raise `--max-seconds` (up to 3600) and
`--max-frames` (up to 108000). These are **hard analysis budgets**, not a
guarantee the full video is captured. The report records duration and
`completeVideo`; consult these before describing an entire video.
To sample every frame semantically in a short sequence, set
`--semantic-stride 1` and raise `--max-semantic-frames` within the configured
bound. Ollama inference can be substantially slower than frame decoding.

## Data retained in Git

```text
research/analysis/online-videos/
  youtube-com-<url-hash>.json
  example-com-<url-hash>.json
```

The JSON schema `kumiki.online-video-reference.v1` contains:

- `source`: watch URL, content SHA-256, source metadata, declared rights basis.
- `numericEvidence.frames[]`: **every decoded frame within the budgets**,
  sequential index, FFmpeg decoder presentation timestamp, display RGB,
  luminance/saturation, change from previous frame, edit candidate.
- `numericEvidence.analysisWindow`: frame count, reporting duration and
  incomplete-coverage flag. Decoder timestamps are **not** independently
  source-PTS-verified.
- `semanticObservations[]`: local model hypotheses at bounded sample frame
  indices. Each proposal describes visible character appearance and action
  hypotheses, likely animation treatments (paper-cut, kinetic typography,
  morph, etc.), typography anatomy (serif/sans, weight and layout), lighting,
  composition and camera-image observations. The model is not a font
  recognition engine, motion-capture system, calibrated lighting analyzer,
  guaranteed OCR engine or speaker transcription system.
- `creativeReference`: searchable lists of animation terms, type treatments,
  style and visible character-description cues for a later video agent.

All model observations are **unreviewed hypotheses**. Font family, physical
camera trajectory, real-world character identity, genuine production technique
and authorial intent cannot be proven from a handful of sampled frames.

The architecture is split into reusable agents/services:

| Module | Responsibility |
| --- | --- |
| `acquisition/online_video.py` | Generic HTTPS watch-URL validation, public DNS check and ephemeral `yt-dlp` acquisition |
| `pipeline/online_frames.py` | FFmpeg sequential decoder; per-frame measurements and bounded PNG samples |
| `pipeline/online_semantics.py` | Strict-schema proposals through local Ollama |
| `pipeline/online_study.py` | Orchestration, provenance, JSON summaries, atomic write, CLI |

The runner uses a `TemporaryDirectory` around acquisition and every
subsequent analysis stage. **No downloaded video, audio, original frames,
screenshots, captions or model prompts enter Git.** Local PNGs are created in
memory only to reach the loopback vision model; only evidence JSON remains.
The rights note is not committed.

## Security and rights

An arbitrary public website is different from an arbitrary safe execution
environment. The URL validator rejects non-HTTPS, embedded credentials, private
hostnames, IP-literal source addresses and common signed/auth query keys.
The DNS preflight rejects private and reserved address answers. However, a
third-party extractor may follow its own redirects and perform other network
requests. **DNS preflight is not full SSRF defense.** For agent-submitted or
otherwise untrusted URLs, run this command in a nonprivileged container with
network policy preventing access to loopback, cloud metadata endpoints, private
ranges and internal services. Never give an online extractor cloud credentials
or privileged local network access. Source hosts may block extraction, require
login or use DRM; the workflow does not attempt to bypass any of those controls.

The command requires an explicit rights basis and acknowledgment; declaring
one does not establish legal permission. Public availability, a planned private
repository and noncommercial purposes do not by themselves establish rights
to download someone else's film. Do not publish or redistribute source
footage, stills or the soundtrack without proper authorization. Respect
host terms, applicable law and rate limits.

## Quality boundaries and next research extensions

- **Implemented:** provider-neutral URL intake, reproducible source fingerprint,
  sequential every-frame measurements, cut/change proxies, sampled semantic
  review, JSON persistence, cleanup, isolated failures.
- **Not implemented:** guaranteed extraction of every hosted player, browser
  login/session reuse, DRM circumvention, independently verified source PTS,
  dense foreground/background motion separation, persistent character IDs
  across shots, exact font recognition or full-video speech/character tracking.
- **Future integration points:** combine existing
  `source-visual-probe`, `character-vision-review`,
  `speech-transcribe`, and `local-character-interactions` modules for
  stronger timecoded evidence; add shot-aware frame selection and manually
  confirmed technique labels. Do not upgrade model guesses into verified
  evidence without additional validation.

## Tests

```bash
PYTHONPATH=src python -m unittest tests.test_online_video_study -v
```

The tests cover unseen hosts, public DNS checks, no-auth acquisition,
synthetic-video FFmpeg decoding with PTS, structured semantic validation,
Git output and deletion on both success and failure.
