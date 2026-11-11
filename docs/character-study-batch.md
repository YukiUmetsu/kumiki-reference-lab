# Batch multiple independent character-study windows

`character-study-batch` processes **several short, nonoverlapping intervals** from the first 120 seconds of an authorized local video. It invokes the established source-PTS-verified `character-study-local` pipeline for each interval and publishes all studies as **one atomic, immutable batch**.

This is useful when a reference video introduces different characters after its opening title, contains multiple shots, or is longer than a single 10-second analysis window. The batch can be processed without repeatedly constructing manual commands, and retains all per-window review galleries.

## Example

Use an already installed Ollama vision model on your Mac:

```bash
PYTHONPATH=src python -m kumiki_reference_lab character-study-batch \
  ./authorized-reference.mp4 --model qwen3-vl:8b \
  --detector ollama \
  --start-seconds 0 --window-count 4 \
  --window-seconds 15 --stride-seconds 20 \
  --max-samples 8 --max-calls 8 --max-pairs 3 \
  --out ./runs/character-batch-001
```

This samples four disjoint intervals: 0–15, 20–35, 40–55, and 60–75 seconds, with each independent video window keeping **original source PTS** and its own unverified character IDs.

Alternatively, `--detector apple-vision` is available for macOS live-action human-region proposals. Both detector modes still need a locally installed Ollama vision model for appearance and interaction inference.

## Budget and source restrictions

- Total windows: 1–6, duration per window: 1–30 seconds.
- `--stride-seconds` is the distance between window starts and must be **at least** the window duration. Omit it for consecutive nonoverlapping windows.
- The last window must end within the **first 120 source-relative seconds**. The current FFmpeg backend decodes the bounded source prefix to preserve exact frame ordinals and PTS. Long-video sampling after 120 seconds requires a new, independently verified seek implementation.
- Default inference bounds per window: 8 sampled frames, 8 character-VLM calls and 3 candidate pair-interaction calls. An explicit `--skip-interactions` avoids pair inference, and `--skip-qa` avoids generating source-frame galleries. Both reduce cost; source/provenance checks remain enabled.
- No automatic video downloads, remote model inference, unlicensed source extraction or automatic model-weight installation. The Ollama daemon is contacted only through localhost.

## Output

- `batch-manifest.json` lists each window's exact start and end seconds, source SHA, model tag, detector, resource budgets, independent study-manifest path, and summed *provisional* counts.
- `windows/window-000/study-manifest.json`, `windows/window-001/study-manifest.json`, etc. Each window contains its own detection JSON, provisional tracklets, character scenes, interaction hypotheses and (unless skipped) original-frame evidence galleries.
- All windows must pass before any output is published. Failure of the **last** window removes the staging tree, leaving no partially published batch.
- A repeated local tracklet ID like `subject_001` across two windows **does not mean the same individual or character**. No identity linking or unique-character count is invented across windows.
- The batch sums local observations and appearances, **not unique persons**, and does not claim any frames outside the selected intervals were analyzed.
- Every scene insight is a low-confidence model hypothesis until reviewed against actual source images. The program does not infer demographics, real identities, dialogue, or personal attributes.

## Verification

The offline tests check window planning, refusal of overlaps/out-of-budget requests, precise start/end metadata, preservation of independent ID namespaces, source hash checks, atomic rollback after a later window fails, and CLI parsing. The real-media smoke test verifies FFprobe/FFmpeg source PTS through independent windows on a tiny generated original video; Ollama model responses are mocked to keep CI fast.

A stronger evaluation should review subject boxes, character appearance and pairwise actions in each window, then measure recall and false positives using `evaluate-character-detections` and the existing human feedback commands. This batch scheduler does **not** establish real-world semantic accuracy.
