# Source-relative windowed character analysis

`character-study-local`, `local-character-detect`, and `mac-vision-humans` now support **`--start-seconds`** to analyze a later segment of a longer authorized local video without treating the second segment as a new movie beginning at PTS zero.

This matters for studying title sequences, mid-film character introductions, interactions or transitions; the original implementation only sampled the beginning of each video.

## Example

```bash
# Analyze seconds 60–80 of a longer local animated character video.
PYTHONPATH=src python -m kumiki_reference_lab character-study-local \
  ./authorized-reference.mp4 --model qwen3-vl:8b \
  --detector ollama --start-seconds 60 --max-seconds 20 \
  --max-samples 8 --out ./runs/characters-60-to-80

# You can scan several nonoverlapping segments independently.
PYTHONPATH=src python -m kumiki_reference_lab character-study-local \
  ./authorized-reference.mp4 --model qwen3-vl:8b \
  --detector ollama --start-seconds 80 --max-seconds 20 \
  --out ./runs/characters-80-to-100
```

Each call writes a separate immutable study and review bundle; no automatic identity is established across windows, including adjacent time segments. An apparent "same character" across studies still needs independently reviewed continuity evidence.

### Boundaries

- The window is `[start_seconds, start_seconds + max_seconds)` in **source-relative presentation time**. `start_seconds` is a nonnegative integer; `max_seconds` remains 1–30 seconds.
- A study window can now end at up to **3600 seconds (one hour)** into the source. Each requested window remains 1–30 seconds. The 120-second boundary switches the underlying decoding strategy, not the source identity or clock.
- Original FFprobe decoded frame ordinals and PTS are preserved. This is not FPS multiplication, timestamp renumbering, or clip re-encoding.
- Windows ending within 120 seconds keep the original prefix/ordinal decoder. Later windows use input-side FFmpeg `-ss` and `-copyts`, independently inventory the original PTS with FFprobe, and **fail if decoded PTS/timebase differ**. No approximate nearest-frame guess is allowed.
- Cut detection, local vision descriptions, actor-target interactions and all QA galleries use the same appropriate prefix or exact-PTS seek strategy. Every selected frame must match the source stream's original rational timebase.
- The output `study-manifest.json` includes `scanStartSeconds`, `sourceWindowEndSeconds`, `sourceDecodeMode`, and `scanPrefixSeconds` (null when seeking rather than decoding the entire source prefix), plus duration/model-call budgets.
- Apple Vision remains a human-region baseline, while local Ollama supports provisional animated/animal/human character boxes. Neither detector's accuracy is established by window support alone.

### Tests

`tests/test_real_ffmpeg_character_study.py` now contains a **real generated video** check for a later window, verifying that the second half of the clip retains its **original nonzero PTS**, distinct source timebase and fully generated review galleries. This prevents regressions where a later segment silently receives fictitious timestamps.

```bash
PYTHONPATH=src python -m unittest tests.test_real_ffmpeg_character_study -v
```

This is an FFmpeg software correctness test. Actual local vision-model detection, identity continuity and interaction semantics still require real-footage human validation.
