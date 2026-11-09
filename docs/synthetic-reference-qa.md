# Procedural reference-video validation

The end-to-end fixtures in `tests/test_technique_end_to_end.py` use original, deterministic RGB frame sequences encoded with FFmpeg's lossless FFV1 codec. They are generated in a temporary directory for each test; no third-party footage, learned model, or paid API is used. These heavier FFmpeg/NumPy tests run locally; the credit-conscious GitHub Actions workflow executes only selected fast checks. Run the full suite locally with FFmpeg/FFprobe and the NumPy extra installed so optional tests do not skip.

Run locally:

```bash
python -m pip install -e '.[motion]'
PYTHONPATH=src python -m unittest tests.test_technique_end_to_end -v
PYTHONPATH=src python -m unittest tests.test_motion_counterexamples -v
```

| Synthetic source | Known construction | Pipeline expectations | Why it matters |
| --- | --- | --- | --- |
| Translating 16×16 bright square on a fixed dark background | Object translated horizontally, global brightness remains nearly fixed; **no actual moving light** | `analyze --appearance` produces source-PTS-tracked RGB evidence; `propose-techniques` may suggest a highlight-sweep *review cue* and explicitly lists a bright moving object as an alternative; `review-techniques` extracts three verified JPEGs; `shot-evidence` retains source time and frame count | Ensures numerical cues do not become unsupported physical lighting claims |
| Smooth digital enlargement of a procedurally textured field | Digital resampling, **no virtual 3D camera travel** | Sparse motion produces repeated affine scale observations; proposals link to the macro-dolly catalog *candidate* while explicitly including digital crop as an alternative | Prevents assuming 2D magnification proves physical camera motion |
| Two flat color blocks separated by a single hard edit | Five frames of one color followed by five of another | FFmpeg cut candidate and per-region aggregator identify the boundary in actual source PTS, with two five-frame regions, accurate exclusive boundary and no invented final end timestamp | Verifies timestamp alignment and candidate edit-group correctness on real encoded footage |
| Two independently moving image layers | Seeded noisy background translates +2 px/frame while a 46×36 foreground crop translates −5 px/frame, with foreground pixels occluding the background | Lossless FFV1 decoding yields distinct translation groups in multiple frame pairs, even with optional LK refinement. Both remain *unattributed 2D image motion*: neither group is proof of a camera or a particular subject | Tests mixed motion and overlapping content instead of assuming every image feature shares one cause |
| Full-frame opaque obstruction | Three consecutive flat frames hide an otherwise translating textured image, which subsequently reappears | No vectors are invented for flat-to-flat frame pairs; linked tracklets cannot span the invisible interval, even with motion and two-hop appearance gates | Tests honest tracking abstention under complete loss of visibility, without re-identification claims |
| Source-timestamp discontinuity | Same two-layer clip, but FFmpeg source PTS jumps 0.4 s once while surrounding presentation intervals stay 0.1 s | The analyzer preserves actual rational source PTS deltas; motion-consistency gates must not silently treat the clip as uniform 10 fps | Prevents nominal-frame-rate assumptions from contaminating temporal evidence |

These are **calibration and regression fixtures**, not proof that the algorithms recognize all professional filmmaking. The obstruction is deliberately *complete*; it does not validate feature visibility boundaries for partially occluded objects or recover their identities. The two-layer clip exercises image-plane motion but does not simulate calibrated 3D camera parallax. Neither test establishes audience comprehension, material realism, lighting physics, camera recovery, cinematic taste or production-quality animation. Add partial occlusion, true depth parallax, fades, motion blur, dynamic lighting and color-grading counterexamples before expanding automatic technique inference. Future changes must retain explicit uncertainty rather than claiming hidden source rigs.
