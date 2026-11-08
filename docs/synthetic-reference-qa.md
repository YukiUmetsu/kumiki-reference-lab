# Procedural reference-video validation

The end-to-end fixtures in `tests/test_technique_end_to_end.py` use original, deterministic RGB frame sequences encoded with FFmpeg's lossless FFV1 codec. They are generated in a temporary directory for each test; no third-party footage, learned model, or paid API is used. The second GitHub Actions job installs the optional NumPy analysis extra and explicitly requires FFmpeg/FFprobe before running these tests, so they cannot silently pass as skipped due to absent dependencies.

Run locally:

```bash
python -m pip install -e '.[motion]'
PYTHONPATH=src python -m unittest tests.test_technique_end_to_end -v
```

| Synthetic source | Known construction | Pipeline expectations | Why it matters |
| --- | --- | --- | --- |
| Translating 16×16 bright square on a fixed dark background | Object translated horizontally, global brightness remains nearly fixed; **no actual moving light** | `analyze --appearance` produces source-PTS-tracked RGB evidence; `propose-techniques` may suggest a highlight-sweep *review cue* and explicitly lists a bright moving object as an alternative; `review-techniques` extracts three verified JPEGs; `shot-evidence` retains source time and frame count | Ensures numerical cues do not become unsupported physical lighting claims |
| Smooth digital enlargement of a procedurally textured field | Digital resampling, **no virtual 3D camera travel** | Sparse motion produces repeated affine scale observations; proposals link to the macro-dolly catalog *candidate* while explicitly including digital crop as an alternative | Prevents assuming 2D magnification proves physical camera motion |
| Two flat color blocks separated by a single hard edit | Five frames of one color followed by five of another | FFmpeg cut candidate and per-region aggregator identify the boundary in actual source PTS, with two five-frame regions, accurate exclusive boundary and no invented final end timestamp | Verifies timestamp alignment and candidate edit-group correctness on real encoded footage |

These are **calibration and regression fixtures**, not proof that the algorithms recognize all professional filmmaking. They cannot establish audience comprehension, material realism, lighting physics, camera recovery, cinematic taste or production-quality animation. Add counterexamples (moving subjects, camera parallax, fades, occlusion, motion blur, dynamic lighting, frame-rate changes, color grading) before expanding automatic technique inference. Future changes must retain explicit uncertainty rather than claiming hidden source rigs.
