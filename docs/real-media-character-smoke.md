# Real-media FFmpeg character pipeline smoke

The foundation test `tests/test_real_ffmpeg_character_study.py` exercises the **actual** FFmpeg/FFprobe source-PTS pipeline rather than mocking the video decoder.

It synthesizes a **two-second, completely original** 160×90 MPEG-4 film locally with two colored geometric subjects, using FFmpeg's built-in lavfi sources. It does not download or commit external media. It then calls the full `character-study-local` orchestration (detector JSON, source-verified tracklets, individual character description, two-subject interaction abstention and **all three** actual-frame QA galleries).

Only the Ollama **model responses** are mocked; actual source inspection, decoding, cut scan, PNG generation, source SHA checks, original PTS, JSON validation, cross-stage handoff and atomic publication execute as real code.

```bash
PYTHONPATH=src python -m unittest tests.test_real_ffmpeg_character_study -v
```

Requires `ffmpeg` and `ffprobe` in PATH. It is inexpensive and added to the repository's existing short Python foundation workflow. On machines without either executable, the tests skip rather than failing a minimal installation. For full confidence, run with FFmpeg available, and inspect the test's result in GitHub CI.

## Assertions

- Original decoded frame PTS and stream timebase remain intact through model-proposed detection and source-verified tracking. No FPS-based timestamp fabrication.
- Two model-proposed subjects, five sampled frames, and ten provisional appearance events reach the character scene, without inventing speech or real identities.
- A local model abstention creates **no directed interaction**. All original-frame review galleries and their PNG/feedback artifacts are generated.
- Each review starts with **pending** human verdicts; no model output is automatically approved.
- If local model inference fails after earlier stages have completed inside staging, the final output directory is **not published**.

## What this does not verify

This is a software integration smoke with an **original static synthetic film**. It does **not** establish that a real vision model detects its subjects correctly, that an Apple Silicon/macOS framework executes natively, or that any predicted character action matches human ground truth. Full photorealistic and animated character tracking benchmarks still need source rights, reviewed sample clips and actual model evaluation.

The fixture's artificial shape/type labels are simply deliberate synthetic VLM output. No real person or sensitive traits are recognized.
