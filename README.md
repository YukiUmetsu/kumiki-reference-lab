# Kumiki Reference Lab

**Reference-video analysis, cinematic technique research, and reproducible motion reconstruction for the Kumiki ecosystem.**

**CI cost policy:** GitHub Actions runs only lightweight compile, schema, timebase, CLI and catalog smoke checks on pull requests (and on manual dispatch). There is no duplicated post-merge push run, FFmpeg installation, NumPy installation or video integration run in hosted CI. **No tests were deleted.** Before merging substantive changes, run the full test suite locally with `PYTHONPATH=src python -m unittest discover -s tests -q` and use `python -m pip install -e '.[motion]'` plus installed FFmpeg/FFprobe for video integration coverage.

> **Project status: early working foundation.** The `study-reference`, `export-film-handoff`, `review-film-map`, `film-feedback`, `review-notes`, `review-shots`, `review-timeline`, `audio-timeline`, `audio-levels`, `audio-onsets`, `av-cut-evidence`, `edit-rhythm`, `inspect`, `frames`, `cuts`, `contact-sheet`, `motion`, `track-roi`, `review-roi`, `sparse-flow`, `dense-flow`, `review-sparse-flow`, `review-dense-flow`, `appearance`, `shot-evidence`, `compare-appearance`, `compare-frames`, `propose-techniques`, `review-techniques`, `analyze`, and `catalog` commands are implemented and tested. Semantic video-to-technique interpretation, full visual matching, and automatic Kumiki film authoring remain planned.

**Implemented foundation:** Python commands read local video metadata, extract real presentation timestamps, detect bounded hard-cut *candidates*, produce timecoded HTML/JPEG contact sheets, optionally measure global image-plane translation and easing candidates, track a seeded image region, and characterize sparse 2D motion with conservative affine hypotheses. The `appearance` command measures display-referred RGB color and contrast; `compare-appearance` compares two reports at **explicitly aligned source times**, while `compare-frames` produces side-by-side timecoded JPEGs for manual visual QA. A versioned `analyze` pipeline combines motion/appearance evidence into immutable runs. `propose-techniques` now generates explicit, machine-readable, non-semantic review cues from such a verified run. A searchable Cinematic Techniques Catalog includes five original research candidates. Semantic interpretation, full-speed visual matching, physical camera/lighting inference and treatment compilation remain planned.

Kumiki Reference Lab studies legally obtained motion-graphics, product-film, documentary, and explainer-video references. It extracts measurable characteristics, identifies reusable filmmaking techniques, and produces evidence-backed reports that can guide implementations in [kumiki-ui](https://github.com/YukiUmetsu/kumiki-ui).

The aim is **not** to copy a film, recover an inaccessible source project, or automatically turn arbitrary footage into perfect 3D. It is to learn *why an animation works*, reconstruct its general techniques with independently created assets, and verify the quality of the resulting animation.

## Why this exists

Professional motion graphics depend on more than shaders and easing presets:

- **Story:** every shot communicates a claim, question, relationship, action, or payoff.
- **Attention:** composition, gaze, contrast, focus, timing, and sound guide what the audience notices.
- **Cinematography:** cameras reveal information and preserve geography rather than moving randomly.
- **Animation:** anticipation, timing, spacing, weight, causality, secondary motion, and settling make actions legible.
- **Lighting and materials:** physically plausible reflections and motivated light establish shape, depth, texture, and mood.
- **Editing and sound:** cuts, holds, transitions, dialogue, music, and effects reinforce one another.
- **Craftsmanship:** full-speed footage, not code structure alone, determines whether the result feels finished.

Reference Lab turns these observations into an auditable analysis pipeline and a reusable **Kumiki Cinematic Techniques Catalog**.

## Ecosystem boundaries

| Repository | Owns | Does not own |
| --- | --- | --- |
| **kumiki-reference-lab** | Video inspection, frame analysis, tracking, technique classification, reference evidence, research catalog, comparison and bounded parameter fitting | Production animation engine or final creative approval |
| **[kumiki-ui](https://github.com/YukiUmetsu/kumiki-ui)** | Executable scene/animation/camera/lighting/film contracts, registry implementations, Storybook previews, final rendering and quality checks | Heavy reference-analysis ML runtime or reference-video archive |
| **[kumiki-blender](https://github.com/YukiUmetsu/kumiki-blender)** | Detailed 3D geometry, Blender models, rigs, materials, reconstruction and asset QA | General film/scene-direction interpretation |
| **[ai-content-generation](https://github.com/YukiUmetsu/ai-content-generation)** | Script, factual evidence, storytelling choices, narration, production orchestration, publishing | Duplicated computer-vision or motion-rendering engines |

Reference Lab is an **offline authoring and research tool**. Neither Kumiki UI nor a published video should need to install this repository or call its services at runtime.

## Design principles

1. **Measure before interpreting.** Extract frame positions, apparent movement, cut timings, luminance, and color numerically when possible. Use AI for object identity, meaning, and ambiguity—not to invent measurements.
2. **Separate observations, hypotheses, and authored decisions.** A highlight traveling across a product might result from a moving light, object, camera, or shader. Report plausible causes, never claim to know an unseen source project.
3. **Evidence for every important conclusion.** Store source hash, sampled timecodes, evidence frame IDs, method/version, uncertainty, and confidence where meaningful.
4. **Reuse Kumiki's existing systems.** Translate accepted treatments into MG1/MD1 motion, CC1 cameras, existing lighting/materials, scene adapters, Film Style Grammar, and FD1 rather than creating a second renderer or clock.
5. **Human approval for artistic quality.** Automated metrics can catch measurable problems, but cannot certify that a film is premium, historically accurate, or effective.
6. **Commercial-use and provenance discipline.** A reference URL is inspiration, not a license to redistribute footage, models, images, music, or extracted textures.
7. **Local-first, optional AI.** Deterministic analysis should work without subscriptions, online APIs, or model downloads. Neural features must be optional, explicit, and separately installable.
8. **Independent reproducibility.** Same source bytes, parameters, model checkpoints, and tool versions should produce equivalent structured measurements; record nondeterministic exceptions.

## Workflow

**One command for the full implemented research workflow:**

```bash
python -m pip install -e '.[motion]'
kumiki-ref study-reference ./reference.mp4 --max-seconds 10 --out ./runs
kumiki-ref export-film-handoff ./runs/study-.../study-manifest.json --fps-num 30000 --fps-den 1001 --out ./handoff
```

This produces a verified analysis bundle, cautious technique proposals, candidate edit-region and cut-to-cut timing summaries, and a local HTML **study overview** linking a five-track audiovisual evidence timeline, a candidate-shot storyboard and a separate technique review gallery. Storyboard frames are available even with zero technique cues. Absent audio is shown explicitly; unreliable audio decoding fails transparently. It never claims to infer the source's actual camera, lights, objects or story purpose. See [one-command study usage](docs/reference-study.md).

**After editing in Kumiki UI:** use `film:reference-map` to explicitly pair source PTS with authored FD1 frames, then run `kumiki-ref review-film-map <reference-film-map.json> <authored.film.json> <reference.mp4> <render.mp4> --out ./review-runs`. This publishes immutable **actual decoded source/render still pairs**, with no implied cinematic quality verdict. Use `film-feedback init`/`validate` to attach evidence-bound correction notes without altering the footage or granting approval. See [film-map review and feedback workflow](docs/film-map-review.md).

To document human observations or optional AI hypotheses in a separate, source-verified draft, use `kumiki-ref review-notes init <study-manifest.json> --reviewer-id NAME --out reviews/`, then `review-notes validate <study-manifest.json> reviews/review-notes.json`. Exact original frame PTS, cue/region identity and study hashes are checked, but no semantic truth or human approval is implied. See [review notes contract](docs/review-notes.md).

For more detailed control, run the individual stages below.

Run the implemented evidence pipeline first:

```bash
PYTHONPATH=src python -m kumiki_reference_lab analyze ./reference.mp4 --max-seconds 10 --out ./runs
# With NumPy installed: --motion, --sparse-flow, --appearance and optionally --box X Y WIDTH HEIGHT
```

The resulting `analysis-<source>-<settings>/analysis-run.json` inventories stage outputs and their SHA-256 checksums. All requested stages must succeed before the bundle is published. Re-running the same source/settings checks the completed output; changed or missing files are rejected. `catalogProposals` stays empty and `interpretationStatus` is `not-performed` until a real interpretation stage exists.

For **cautious, non-semantic technique review cues**, run `analyze` with `--sparse-flow --appearance`, then `kumiki-ref propose-techniques <analysis-run.json> --out ./runs/review`. The separate report links observed enlargement or shifting bright-pixel regions to existing catalog entries and states alternative explanations and reviewer questions. It does **not** establish actual lighting, camera motion, story intent, or source authoring technique. See [technique cue methodology](docs/technique-proposals.md).

Run `kumiki-ref review-techniques ./reference.mp4 <analysis-run.json> --out ./runs` to generate a matching **visual review gallery** with verified start/middle/end frames for each proposed cue. It is an evidence spot-check, not a creative verdict. See [gallery usage and integrity checks](docs/technique-review.md).

Use `kumiki-ref shot-evidence <analysis-run.json> --out ./runs/regions` to summarize motion and appearance within candidate cut regions while preserving exact source PTS. The final region has no invented end timestamp; regions are not confirmed shots or storytelling classifications. See [edit-region evidence](docs/shot-evidence.md).

Use `kumiki-ref review-shots reference.mp4 <analysis-run.json> --out ./runs` to create a separate immutable **shot storyboard** with three original timecoded frames per candidate edit region, measured evidence and story-direction questions. This remains useful even when `propose-techniques` detects nothing. See [shot storyboard guide](docs/shot-gallery.md).

Use `kumiki-ref audio-timeline reference.mp4 --max-seconds 10 --out ./runs/audio` to inspect **original audio frame PTS and decoded sample counts**, independently from video timebase. This is groundwork for future sound, silence, narration and beat analysis, not a sound-event classifier. See [audio clock and limitations](docs/audio-timeline.md).

Use `kumiki-ref audio-levels reference.mp4 --max-seconds 10 --out ./runs/audio-levels` for **per-decoded-frame RMS and peak dBFS**, with the original audio timestamp and sample count independently checked against FFprobe. Quiet frames are candidates, not recognized narration pauses or verified silence, and no A/V synchronization is assumed. See [audio-level measurements](docs/audio-levels.md).

Use `kumiki-ref audio-onsets reference.mp4 --max-seconds 10 --out ./runs/onsets` to find conservative **audio-level attack candidates** from verified decoded-frame RMS rises, with exact source-audio PTS anchors, two-frame support windows and explicit discontinuity/cooldown reporting. It does not identify a musical beat, voice entrance or cinematic SFX. See [audio onset methodology](docs/audio-onsets.md).

Use `kumiki-ref av-cut-evidence reference.mp4 <analysis-run.json> --window-ms 400 --out ./runs/audio-cuts` to examine **quiet-level changes immediately before and after candidate video cuts**, comparing rational source presentation seconds while excluding straddling audio frames. Same-container timing is only a synchronization **hypothesis**; the report cannot establish beats, narration, editing intent, or video quality. See [A/V cut comparison and caveats](docs/av-cut-evidence.md).

Use `kumiki-ref edit-rhythm <analysis-run.json> --out ./runs/rhythm` to measure **exact candidate cut-to-cut durations**, their ratios, and shorter/longer intervals. Only interior candidate-cut gaps count: the first and last bounded regions are deliberately censored. No story or editing quality verdict is generated. See [edit rhythm methodology](docs/edit-rhythm.md).

Use `kumiki-ref review-timeline reference.mp4 <analysis-run.json> --out ./runs/timelines` for a **self-contained audiovisual evidence timeline** with source-timecode cut markers, motion/pacing tracks, audio quiet-level contrasts and onset candidates, and accessible numeric tables. One audio decode serves both audio reports. The timeline checks source/run identity and inventory hashes; it does not prove audio/video sync, identify SFX or establish edit intent. See [visual timeline workflow](docs/timeline-review.md).

```text
Authorized reference video
    ↓
1. Ingest + verify media, timebase, source hash, permissions
    ↓
2. Detect shots + create timecoded contact sheets
    ↓
3. Measure 2D motion, colors, composition, transition behavior
    ↓
4. Track selected subjects (manual prompts or optional segmentation AI)
    ↓
5. Estimate camera/object/lighting hypotheses, with confidence
    ↓
6. Optional vision-language interpretation of story and technique
    ↓
7. Produce versioned analysis report + catalog candidates
    ↓
8. Map candidate into kumiki-ui's validated implementation contracts
    ↓
9. Render → compare → adjust → collect full-motion human verdict
    ↓
10. Publish approved reusable technique metadata and implementation ID
```

**Never conflate 2D motion with unique 3D motion.** Unknown camera intrinsics, lens distortion, occlusion, stylization, motion blur, source editing, and moving objects can make recovered 3D values ambiguous. An estimate should carry its assumptions and limitations.

## Analysis stages and methods

| Stage | First implementation | Optional advanced implementation | Output |
| --- | --- | --- | --- |
| Ingest | FFprobe metadata, source hashing, rational FPS, audio/stream inventory | Variable-frame-rate timeline normalization | Source manifest |
| Editing | PySceneDetect cut/fade candidates, histogram and perceptual differences | Learned transition classifier | Shot intervals and confidence |
| Composition | Subject boxes, saliency heuristics, contrast and negative space | Vision-based semantic focus | Per-shot composition timeline |
| Motion | **Implemented:** optional NumPy FFT global-image translation and candidate easing fits; opt-in spatial held-out comparison of translation, affine and projective models. **Next:** real-footage calibration of competing motion models | Learned correspondence/tracking | Normalized trajectories and fit residuals |
| Sparse/dense motion | **Implemented:** distributed sparse corners, forward/backward patch matching, multi-scale and fractional refinements, image-plane hypotheses, candidate tracklets, and optional OpenCV dense optical flow with a texture-checked, forward/backward-verified grid. **Next:** temporal occlusion diagnostics and independent real-footage calibration | Learned correspondence/tracking | Timecoded image-plane displacements and uncertainty |
| Subject tracking | **Implemented:** manually seeded textured box tracker with match/loss diagnostics and opt-in timecoded manual reseeding as independent segments. **Next:** model-assisted occlusion handling and persistent semantic identity hypotheses | SAM 2 or suitable video segmentation model | Subject-box paths; identity remains a hypothesis |
| Animation curves | **Implemented:** candidate linear, quadratic and smoothstep-family fits on valid translation segments. **Next:** Bézier and spring parameter fitting | Learned motion grouping | Frame-relative motion curves |
| Camera hypotheses | Robustly separate background from foreground movement; estimate translation, scale, roll | Multiview SfM when assumptions hold | Camera-motion *hypotheses* |
| Lighting and look | **Implemented:** RGB palette bins, hue histogram, luma/contrast/bright-region proxies and temporal differences. **Next:** subject-aware look and material/lighting hypotheses | Inverse-rendering/vision models | Display appearance observations, not physical light recovery |
| Audio | Onsets, amplitude envelope, silence, beat candidates | Optional ASR and speaker alignment | Timecoded audio cues |
| Semantics | Reviewer-provided labels | Optional vision-language model | Story purpose and technique suggestions |
| Comparison | Aligned crops, color differences, silhouettes, tracked paths, timing | Perceptual/embedding metrics | Numeric differences plus review sheet |
| Parameter fitting | Bounded grid search/derivative-free optimization | Model-guided proposal generation | Candidate values and optimization trace |

Official starting points: [FFmpeg/FFprobe](https://ffmpeg.org/ffprobe.html), [PySceneDetect](https://www.scenedetect.com/docs/latest/), [OpenCV optical flow](https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html), [SAM 2](https://github.com/facebookresearch/sam2), and [COLMAP](https://colmap.github.io/).

No specific model or library is mandatory. Audit the exact distribution, model weights, runtime, and commercial-use terms before adding a dependency.

## Core artifact contracts

Use **versioned JSON** for machine-to-machine analysis and generated indexes; support YAML for readable creative treatments. JSON is the interchange format, not a new Kumiki animation runtime.

### 1. Source manifest

Records input URI or local reference, immutable SHA-256 of bytes, media streams, rational timebase, rights status, and analysis environment. The input media itself is not committed by default.

### 2. Analysis report

Contains raw measurements and their provenance:

```json
{
  "schemaVersion": "kumiki.reference-analysis.v1.proposed",
  "source": {
    "sha256": "REPLACE_WITH_ACTUAL_HASH",
    "usage": "inspiration-only",
    "rightsStatus": "review-required",
    "fps": { "numerator": 30, "denominator": 1 },
    "width": 1920,
    "height": 1080
  },
  "shots": [
    {
      "id": "shot-001",
      "startFrame": 0,
      "endFrameExclusive": 90,
      "detection": { "method": "content-difference", "confidence": null },
      "observed": {
        "subjectTracks": [],
        "cameraImageMotion": null,
        "palette": [],
        "highlightTracks": [],
        "evidenceFrameIds": []
      },
      "hypotheses": [],
      "storyInterpretation": null
    }
  ],
  "provenance": {
    "toolVersions": {},
    "modelCheckpoints": {},
    "analysisOptions": {}
  }
}
```

All values above are **schema examples**, not real measurements. Never represent estimated or missing quantities as observed facts. Record frame-accurate intervals with inclusive start and exclusive end. For variable frame rate inputs, preserve original timestamps and document any conversion to a rational output frame grid.

**Timebase contract:** preserve each decoded source frame's original integer presentation timestamp (`pts`) together with its stream timebase numerator/denominator. An output frame index must be the result of an explicit, documented mapping from source PTS (including the chosen origin and rounding convention), never `sourceFrameIndex × nominalFPS`. Metadata-only inspection records the source timebase but deliberately reports frame PTS as **not yet extracted**. See [architecture and timebases](docs/architecture.md) and the implemented [source manifest schema](schemas/v1/source-manifest.schema.json).

### 3. Creative treatment

An optional human-editable YAML document proposing a Kumiki implementation. It may contain:

- Intent and visual teaching objective
- Reference evidence and uncertainty
- Subject identities and asset provenance
- Camera framing, projection, paths, lens/FOV hypotheses and keyframes
- Lighting sources, color, exposure, shadows and reflection behavior
- PBR material intent, maps and texture-detail requirements
- Absolute-frame animation, easing, synchronization and contact constraints
- Sound and narration cue alignment
- Output aspects, reframe rules, reduced-motion behavior and safe areas
- Renderer capabilities, fallback behavior and quality acceptance criteria

The treatment is **not executable merely because it parses**. A Kumiki-owned compiler must explicitly map each supported field to an existing contract, reject unknown required features, and report unsupported capabilities. See the detailed [cinematic treatment example](examples/treatments/cinematic-gear-reveal.yaml), which is **an authoring proposal and is not yet runnable**.

### 4. Comparison and review report

Stores:

- Source/render alignment and timestamps
- Reference and candidate image hashes/IDs, without embedding unauthorized footage
- Objective metrics and their limitations
- Camera/object trajectories and timing deltas
- Frame-specific defects and annotated critical frames
- Parameter-search history and compute budget
- Human review status: `needs-revision`, `approved`, or `blocked`

## Kumiki Cinematic Techniques Catalog

The **canonical research catalog lives here**. Kumiki UI owns the executable component or recipe and may consume a **generated, versioned, metadata-only index** without depending on this repository at runtime.

**Implemented:** Strict JSON entry validation, purpose-first lexical search, deterministic index generation and five detailed original research candidates. They are **not yet backed by measured source-video evidence or verified Kumiki implementations**. See the [catalog authoring and promotion guide](docs/catalog.md).

Each catalog entry should answer:

1. **What does the technique communicate?** Story purpose, viewer-attention role, and appropriate circumstances.
2. **What can be measured?** Motion, composition, timing, contrast, light or material cues, and evidence.
3. **How can it be recreated?** A proposed procedure with constraints and alternatives, not a copied asset.
4. **What exists in Kumiki?** Stable registry ID, implementation status, version/capabilities and Storybook link.
5. **Does it work?** Real preview evidence, full-motion review, performance and limitations.

Suggested categories:

- `story/establish-reveal-payoff`
- `attention/focus-transfer`
- `camera/macro-dolly`, `camera/motivated-orbit`, `camera/match-movement`
- `lighting/softbox-curvature-reveal`, `lighting/motivated-light-sweep`
- `materials/brushed-metal`, `materials/glass-transmission`
- `motion/anticipation-settle`, `motion/causal-mechanism`
- `editing/match-on-action`, `editing/eyeline-cut`
- `typography/semantic-data-emphasis`
- `sound/impact-sync`, `sound/transition-bridge`

Search should prioritize **storytelling purpose**, not only visual appearance. An educational sequence should be able to find techniques for *showing cause and effect*, *explaining scale*, or *revealing a hidden mechanism*.

### Example catalog entry (proposed)

```yaml
id: lighting.motivated-light-sweep
revision: 1
name: Motivated Light Sweep
category: lighting
storyPurposes: [reveal-surface-shape, guide-attention]
referenceEvidence: []  # Links to legitimate reports and timestamps
mechanism:
  observation: highlight-travels-along-reflective-surface
  plausibleMethods: [moving-area-light, moving-object, moving-camera]
  originalMethodKnown: false
kumiki:
  registryId: null
  implementationStatus: not-implemented
  minimumVersion: null
  preview: null
quality:
  comparisonStatus: not-run
  humanApproved: false
rights:
  referenceUsage: inspiration-only
  extractedThirdPartyAssetsAllowed: false
```

**Catalog publishing rule:** a technique can exist as a researched candidate without being implemented, but it must not claim to be production-ready until a real Kumiki rendering passes the agreed review gates.

## CLI: implemented versus planned

**Available now (Python 3.11+, FFmpeg and FFprobe installed):**

```bash
PYTHONPATH=src python -m kumiki_reference_lab inspect ./reference.mp4
PYTHONPATH=src python -m kumiki_reference_lab inspect ./reference.mp4 --out ./runs/example
PYTHONPATH=src python -m kumiki_reference_lab frames ./reference.mp4 --max-seconds 60 --out ./runs/example
PYTHONPATH=src python -m kumiki_reference_lab cuts ./reference.mp4 --max-seconds 60 --threshold 0.25 --out ./runs/example
PYTHONPATH=src python -m kumiki_reference_lab contact-sheet ./reference.mp4 --max-seconds 30 --max-thumbnails 12 --width 480 --out ./runs/example
PYTHONPATH=src python -m kumiki_reference_lab catalog validate
PYTHONPATH=src python -m kumiki_reference_lab catalog search "reveal material shape"
PYTHONPATH=src python -m kumiki_reference_lab catalog index --out ./runs/catalog-r001
PYTHONPATH=src python -m kumiki_reference_lab analyze ./reference.mp4 --max-seconds 10 --out ./runs
PYTHONPATH=src python -m kumiki_reference_lab audio-onsets ./reference.mp4 --max-seconds 10 --out ./runs/onsets
PYTHONPATH=src python -m unittest discover -s tests -v
```

**Optional motion analysis:** install NumPy once with `python -m pip install -e '.[motion]'`, then run:

```bash
kumiki-ref motion ./reference.mp4 --max-seconds 10 --max-samples 48 --out ./runs/motion-example
kumiki-ref track-roi ./reference.mp4 --box 0.19 0.22 0.15 0.20 --max-seconds 10 --out ./runs/roi-example
kumiki-ref sparse-flow ./reference.mp4 --max-seconds 10 --max-samples 24 --out ./runs/sparse-example
kumiki-ref appearance ./reference.mp4 --max-seconds 10 --max-samples 24 --out ./runs/appearance-example
kumiki-ref compare-appearance ./runs/reference/appearance.json ./runs/render/appearance.json --reference-anchor-ms 0 --candidate-anchor-ms 0 --out ./runs/comparison
kumiki-ref compare-frames ./reference.mp4 ./render.mp4 --reference-anchor-ms 0 --candidate-anchor-ms 0 --out ./runs
kumiki-ref propose-techniques ./runs/analysis-<source>-<settings>/analysis-run.json --out ./runs/review
kumiki-ref review-techniques ./reference.mp4 ./runs/analysis-<source>-<settings>/analysis-run.json --out ./runs
kumiki-ref shot-evidence ./runs/analysis-<source>-<settings>/analysis-run.json --out ./runs/regions
kumiki-ref study-reference ./reference.mp4 --max-seconds 10 --out ./runs
```

For optional **dense** optical flow, install `python -m pip install -e '.[dense]'`
and run `kumiki-ref dense-flow ./reference.mp4 --max-samples 24 --out ./runs/dense-example`.
It does not change default analysis or hosted CI dependencies.

`inspect` records metadata and SHA-256, while honestly marking frame-by-frame PTS and VFR status as unknown until sampled. `frames` extracts source PTS within a bounded window, preserving exact rational timestamps and reporting missing/nonincreasing values. `cuts` detects **possible hard cuts**, not proven edits; fast subject or camera motion may produce false positives. The optional appearance stage adds conservative global brightness-ramp *candidates* that may resemble fades, without proving an edit type. `contact-sheet` automatically prioritizes frames at opening/closing and around candidate edits, then covers remaining visual gaps. It creates an immutable `contact-sheet-<source>-<settings>/` directory containing `index.html`, `contact-sheet.json`, and up to 24 labeled JPEGs. The JSON records exact rational source timestamps, each evidence image's hash, and the sampling options. Existing bundles are checked for modification, never silently replaced. `--rights-status user-declared-authorized` is an **assertion by the user**, not automated legal verification. No model download or external service is required.

`motion` decodes at most 120 original frames over a 30-second source window into bounded grayscale buffers; every decoded PTS must match FFprobe. It outputs `image-motion.json` containing measured global image translation, explicit ambiguous/unobservable/cut-boundary pairs, normalized displacement, cumulative segments, and residual-ranked candidate easing curves. Curve ranking now abstains when a 2D image path has substantial sideways excursion or a long detour relative to its net displacement; see [easing fit limitations](docs/motion-easing.md). This cannot determine whether the displacement came from the camera, a foreground subject, a background, or a mixture; it also does not measure zoom, rotation, parallax, 3D paths, or separate subjects. Curve fits are observations of rendered motion, **not recovered source keyframes**. The stage uses NumPy only when invoked; the other commands remain dependency-free.

`track-roi` accepts a normalized `x y width height` seed rectangle on the first sampled frame and follows its textured appearance with bounded local normalized cross-correlation. It produces `roi-track.json` with exact source timestamps, per-frame box coordinates, relative displacement and match diagnostics. Uniform templates, ambiguous matches, disappearance and cut boundaries stop the track; the tool does not silently invent positions or automatically re-identify subjects after a cut. This is **not semantic object recognition**: a box containing background may track background, and changing pose, lighting or occlusion can defeat a static patch. The reviewer or a future model must provide meaningful seeds. For manual restart after a gap, use [timecoded ROI reseeding](docs/roi-reseeding.md); every new segment starts with no asserted identity link to earlier segments.

Use `review-roi` to inspect the tracking evidence over actual decoded source frames:

```bash
kumiki-ref review-roi ./reference.mp4 ./runs/roi-example/roi-track.json \
  --out ./runs/roi-reviews --max-frames 8
```

This emits a [source-PTS-verified, checksum-bound HTML review](docs/roi-review.md). Only reported boxes are overlaid; loss and cut frames remain unboxed, and manually reseeded v2 segments (when available) receive independent colors. It is visual QA evidence, not a claim of semantic identity or an artistic-quality verdict.

`sparse-flow` detects distributed grayscale corners, tracks each via forward/backward local patch matching, groups 2D translations into up to two candidate consensuses, and tests a conservative affine image-plane hypothesis for rotation/scale/shear signatures. It emits source-timecoded `sparse-flow.json` with match rejection reasons, point vectors, spatial support, residuals, ambiguity and cut-boundary skips. Optional temporal tracklets join only mutually consistent vectors across consecutive sample pairs, never across cuts or uncertain observations; their sampled kinematics use exact source PTS and rational timebase rather than nominal FPS. The optional `--pyramid-levels 2` (or `analyze --sparse-pyramid-levels 2`) fallback can recover larger image-plane shifts without changing the default matcher; `--subpixel-refinement` estimates bounded fractional NCC peaks, `--subpixel-reverse-check` adds a forward-guided fractional reverse check with integer fallback, and `--lk-refinement` independently iterates and reverse-verifies fractional Lucas-Kanade motion (mutually exclusive with peak refinement). `--projective-hypotheses` tests conservative homography fits against affine on the same inliers, `--tracklet-motion-consistency` rejects abrupt PTS-scaled offset changes, and `--tracklet-appearance-consistency` checks two-hop source-patch agreement during otherwise geometrically safe handoffs. All remain **image-plane candidates**, not calibrated camera velocities. **The largest moving image group is not necessarily the camera or background**, and neither affine, projective fits nor tracklet IDs prove camera zoom, roll or object identity. Opt in with `analyze --sparse-flow`; it uses its own bounded `--sparse-samples` and `--sparse-points` settings. See [method details and limitations](docs/sparse-flow.md).

To visually verify candidate tracks on exact-PTS decoded source frames, use `kumiki-ref review-sparse-flow reference.mp4 ./runs/sparse-example/sparse-flow.json --out ./runs/reviews`. It writes a small offline HTML review with colored motion arrows, tracklet summaries and checksum-protected frame PNGs. No human/semantic validation is inferred; see [visual review details](docs/sparse-flow.md#review-the-actual-sampled-frames).

`dense-flow` optionally estimates multi-scale OpenCV Farneback motion across the bounded grayscale image and exports only a conservative grid of textured, forward/backward-checked vectors. Install `pip install -e '.[dense]'`, then use `kumiki-ref dense-flow reference.mp4 --out ./runs/dense`, or `analyze --dense-flow`. Flat, obstructed and cut-spanning evidence can be withheld without filling in unseen motion. It remains a **2D image-plane estimate**, not camera recovery, segmentation or semantic tracking. See [dense-flow limitations](docs/dense-flow.md).

`review-dense-flow` builds a source-PTS-verified, immutable HTML/PNG gallery of accepted dense grid displacements, prioritizing cuts and changes in grid support. It does not run OpenCV or establish camera/object identity. See [dense-flow review](docs/dense-flow.md#review-the-actual-source-frames).

To test whether translation, affine or perspective-like motion predicts *unseen* matched points, opt in with `sparse-flow --model-validation` or `analyze --sparse-flow --sparse-model-validation`. Each pair then includes spatial held-out prediction errors or an explicit abstention. This does not recover a camera. See [held-out methodology](docs/sparse-flow.md#optional-held-out-motion-model-validation).

`appearance` converts selected frames to bounded 8-bit RGB for measurable color/contrast descriptors. It records mean RGB, non-linear luma proxies, percentile contrast, bright-pixel location, saturation, hue distributions, quantized color bins, and a spatial 3×3 brightness grid at verified source PTS. It also produces conservative global luma-ramp and five-frame linear image-blend *candidates*, neither of which establishes the original edit, compositing method or physical lighting. Use `analyze --appearance --appearance-samples 24` to include it transactionally. See [appearance method and limits](docs/appearance.md).

`compare-appearance` takes two completed appearance reports and requires explicit reference/render time anchors. It selects monotonic one-to-one PTS pairs using bounded tolerance, then records brightness, color and spatial-grid differences. It is a **measurement baseline, not a creative-quality grade**. See [alignment and comparison guide](docs/appearance-comparison.md).

`compare-frames` creates an immutable responsive HTML/JPEG review sheet pairing source/render frames at explicitly aligned original PTS, with verified FFmpeg decoding and hashes. The goal is to inspect actual composition, materials, lighting and story beats at matched moments. It does not automatically assign a "premium" quality score. See [visual review guide](docs/frame-comparison.md).

`propose-techniques` validates the completed analysis bundle and produces a separate immutable versioned report of catalog-linked *review hypotheses*. Currently it proposes only coherent image-plane enlargement and shifting bright-region cues, with source PTS, measurements, competing interpretations and specific human review questions. It does not rely on AI, rewrite the catalog, or pretend its cues are confirmed cinematography. See [heuristic gates and agent workflow](docs/technique-proposals.md).

`review-techniques` independently verifies the same source video and analysis run, then assembles a self-contained source-PTS-verified HTML/JPEG gallery for up to eight of those cues. Each displays three source moments, quantitative evidence, alternative explanations and reviewer questions. Immutable inventory hashes catch modified images and reports on reuse. See [visual cue review](docs/technique-review.md).

`shot-evidence` groups already measured frame data into candidate edit regions, summarizes available appearance/translation/sparse-flow measurements and records explicit uncertainty. It refuses unreliable source timestamp timelines and does not manufacture a final exclusive end PTS. See [shot evidence and semantic limits](docs/shot-evidence.md).

`study-reference` orchestrates `analyze` with bounded optional numeric stages, technique proposal generation, shot-region summaries, censored candidate cut-to-cut intervals, a source-linked audiovisual timeline including possible level attacks, and two source-verified galleries. The derived v5 study is published atomically with checksummed files; v1–v4 studies remain readable, and a successful analysis remains reusable if a later review step fails. See [command contracts and output layout](docs/reference-study.md).

`export-film-handoff` is the first **actual downstream authoring bridge**. It verifies a v5 study and its original analysis, then emits immutable, source-PTS-grounded `film-handoff.json`: only interior candidate cut-to-cut timing, exact rational target-frame rounding/error, audio-level attack hypotheses and catalog technique cue IDs. The packet explicitly leaves scene recipes, content, actual sound cues and Kumiki implementation IDs **unassigned**. It is *not* executable Kumiki FD1 film JSON; a coding agent must inspect the live Kumiki catalog, author an original film, run `npm run film:check`, render and visually review. See [FD1 handoff contract and agent workflow](docs/film-handoff.md).

**Regression evidence:** Three procedurally generated reference-video fixtures exercise the actual FFmpeg → analysis → proposal → HTML gallery / shot-region path with known causes, including misleading visual lookalikes. These and all FFmpeg/NumPy integration tests remain available for **local testing**; the streamlined GitHub CI runs only inexpensive core smoke tests. See [synthetic source validation](docs/synthetic-reference-qa.md).

`analyze` is the transactional orchestration layer: it runs `inspect` + `frames` + `cuts` + `contact-sheet`, with `--motion`, `--sparse-flow`, `--appearance`, and `--box` opt-ins. By default it requires only FFmpeg/FFprobe. Each completed bundle contains JSON artifacts, a local visual contact sheet, and `analysis-run.json` with hashes and immutable input/settings identity. If any required stage fails, the temporary bundle is discarded and no partial run is published. The bounded initial implementation repeats some inexpensive metadata work rather than building an unverified streaming/cache engine.

`catalog` loads canonical research entries from `catalog/entries/` when run from the repository root; provide `--root` when invoked elsewhere. `validate` rejects malformed or improperly promoted entries, `search` ranks story-purpose matches, and `index` emits a versioned metadata-only `catalog-index.json`. Research candidates do not claim verified renderer support or reference-video measurements.

**Planned interfaces (not implemented):**

```bash
# Later: full composition, optical-flow and color analysis
kumiki-ref analyze ./reference.mp4 --features shots,motion,color --out ./runs/example

# Optional subject tracking, with explicit model selection
kumiki-ref track ./reference.mp4 --shot shot-001 --prompt "product" --backend sam2

# Later: AI-assisted semantic interpretation and fully authored executable Kumiki treatment
kumiki-ref interpret ./runs/example/analysis.json --model local
kumiki-ref export kumiki ./runs/example/analysis.json --out ./runs/example/treatment.yaml

# Compare a user-supplied Kumiki render to the authorized reference
kumiki-ref compare ./reference.mp4 ./kumiki-render.mp4 --out ./runs/example/comparison
```

CLI development requirements:

- Clear `--help` and machine-readable `--format json`.
- `inspect` and core `analyze` work without any AI package or model.
- No model auto-download or paid API without explicit configuration.
- Record missing or uncertain usage rights explicitly; require a user declaration before rights-sensitive processing or redistribution. Exit nonzero for unsupported media, invalid schema, or failed required stages. Metadata inspection itself does not prove rights.
- Deterministic output paths, content-addressed caches, restartable stages, and progress logs.
- Support local file inputs first; URL retrieval is out of scope until authorized sourcing and licensing behavior are specified.
- Never execute untrusted scripts found in analysis documents or model responses.

## Modular repository layout and growth plan

```text
kumiki-reference-lab/
├── README.md
├── pyproject.toml                  # Dependency-free inspect foundation
├── src/kumiki_reference_lab/
│   ├── cli/
│   ├── core/                       # Timebase, provenance, errors, capability ports
│   ├── contracts/                  # Versioned artifacts, never renderer logic
│   ├── pipeline/                   # Implemented: atomic bounded analysis run; future: DAG/caches/retry
│   ├── analyzers/
│   │   ├── media/                  # Implemented: inspection, timestamps, contact sheets
│   │   ├── shots/                  # Implemented: bounded cut candidates
│   │   ├── motion/                 # Implemented: translations, sparse affine and easing candidates
│   │   ├── appearance/             # Implemented: sampled display RGB measurements
│   │   ├── comparison/             # Implemented: source-aligned appearance and frame comparison
│   │   ├── techniques/             # Implemented: conservative catalog-linked review cues
│   │   └── subjects/               # Implemented: user-seeded ROI tracking; future: segmentation and identity
│   ├── backends/
│   │   ├── ffmpeg/                 # Implemented: FFprobe and FFmpeg adapters
│   │   ├── opencv/                 # Future: classical CV
│   │   └── segmentation/          # Future: optional ML
│   ├── interpretation/             # Future: story/technique semantics
│   ├── catalog/                    # Implemented: validation, search and metadata index
│   ├── optimization/               # Future: bounded parameter fitting
│   └── integrations/kumiki/       # Future: export; no second renderer
├── schemas/v1/                    # Interchange schemas
├── catalog/entries/               # Implemented: versioned research candidate definitions
├── fixtures/                       # Original or explicitly licensed test videos
├── tests/
├── examples/treatments/
└── docs/architecture.md + catalog.md
```

The tree is a **target layout**, not a list of directories to create immediately. `core` and `contracts` must not import model backends; analyzers use capability interfaces, while the pipeline chooses backends. Keep generated footage, checkpoints, masks and run artifacts out of Git. See [architecture](docs/architecture.md) for ownership and dependency rules.

## Local development and Apple Silicon

Primary target: **macOS on Apple Silicon (M4, 24 GB unified memory)**. Linux CPU is a secondary portable baseline; optional CUDA acceleration may be supported where models allow it.

Recommended implementation language: Python for offline video/CV/ML analysis, with subprocess invocation of installed FFmpeg/FFprobe. Keep API surfaces CLI- and file-based so a TypeScript consumer is not required to embed Python.

Model-backend installation scripts and tested advanced setup commands will be added with their first working release. For now:

- Require a regular local FFmpeg/FFprobe installation, with a doctor/preflight command.
- Pin any future Python dependencies and model versions in lockfiles/configuration.
- Keep baseline CPU analysis independent of PyTorch.
- Make MPS/CPU backend selection explicit with a documented fallback; do not assume every operation accelerates on MPS.
- Bound image sizes, decoded-frame batches, process/thread counts, memory and temporary disk use.
- Cache expensive segmentation/flow results by source hash, algorithm config and checkpoint hash.
- Avoid keeping full-resolution decoded 4K videos in RAM; stream or sample bounded frame windows.
- Maintain a local, offline path for complete core analysis.

## Implementation roadmap

### Milestone 0 — Contracts, sources and reproducibility

- Establish `reference-analysis.v1` JSON Schema plus sample fixtures with correct rational timebase.
- Implement source metadata, hashing, rights manifest, local-path input, errors and doctor.
- Ensure original footage remains outside git; store permitted evidence IDs and reports.
- **Exit:** two identical local runs emit equivalent machine-readable source/shot metadata.

### Milestone 1 — Deterministic analysis (highest priority)

- Detect cuts and fades; export shot intervals and contact sheets.
- Compute optical flow, tracked-point motion, approximate scene motion and basic color/contrast statistics.
- Fit a small, documented easing family to synthetic known curves; report residual and rejected fits.
- **Exit:** recover hard-cut candidates, exact source PTS, and known motion from original, programmatically generated test footage; no AI dependencies. Cut detection and source PTS extraction are the first delivered portions; motion fitting remains.

### Milestone 2 — Subject tracking and technique candidates

- Add manual box/point selection; optional SAM 2 backend with local checkpoints.
- Separate object motion from camera hypotheses where evidence supports it.
- Implement initial searchable catalog records with provenance, confidence and `not-implemented` status.
- **Exit:** tracked identity and timecoded evidence are inspectable; uncertainties are explicit.

### Milestone 3 — Kumiki vertical slice

- With the Kumiki UI repo, agree a minimal interchange/validation contract.
- Convert one simple reference motion into a native Kumiki timeline with existing MG1/MD1 and CC1 contracts.
- Render a complete video, seek frames out of order, and compare measured motion timing/composition.
- Publish only generated metadata and implementation IDs to Kumiki.
- **Exit:** one reproducible **reference → analysis → Kumiki render → comparison** example, with actual files and reviewed defects.

### Milestone 4 — Optional semantics and visual optimization

- Add model adapters for story-purpose interpretation; validate all outputs as untrusted proposals.
- Fit bounded camera/light/material parameters against user-supplied licensed reference frames.
- Add whole-sequence review, failure reporting, repeatable search and human sign-off.
- **Exit:** measurable improvement over baseline plus human-reviewed footage; no unsupported claim of exact source reconstruction.

## Testing and quality gates

Use original procedurally generated fixtures with ground-truth motions, cuts and lighting changes. Never assume third-party footage is freely redistributable.

**Automated checks**

- Rational-FPS and variable-frame-rate handling, exact start/end semantics, shot coverage and no overlaps.
- Known motion curves recovered within declared tolerances and residuals.
- Tracker identity continuity, missing/occluded-object warnings and uncertainty calibration.
- Scene/background movement disambiguation; explicitly report when unidentifiable.
- Stable outputs on random-seek and repeated analysis with fixed versions/options.
- Schema version compatibility and rejection of unknown required capabilities.
- Safe file paths, bounded input decoding, no unauthorized automatic network/model operations.
- Comparison metrics computed at aligned source timestamps, never by blindly matching frame indexes.

**Review artifacts**

- Timecoded source contact sheet and measured trajectories.
- Observed-versus-hypothesized report.
- Proposed implementation treatment and capability diagnostics.
- Actual Kumiki MP4/frames in both relevant aspects.
- Side-by-side comparison with cited timestamps and independently created assets.
- Recorded human verdict, defects, revisions, performance, and license/source manifest.

A screenshot or numerical similarity score alone is **not** artistic approval. Review full-speed output, edit continuity, audio sync, and instructional clarity.

## Rights, privacy and ethical use

- Only ingest locally possessed or explicitly authorized videos. Do not bypass access controls, DRM, paywalls, download restrictions, or account permissions.
- Source attribution and analysis permission do **not** imply permission to redistribute frames, soundtrack, models, or textures.
- Keep original reference media, private screenshots, extracted audio and unlicensed source assets out of git and published catalog packages.
- Catalog entries should store links, metadata and independently authored techniques, not scraped production assets.
- Inspect each dependency, model checkpoint, sample asset and output for its exact commercial-use, redistribution, trademark and attribution restrictions before shipping.
- Allow analyses to be deleted by source hash, and document caching/retention.
- Preserve factual distinctions: observed pixels versus inferred physics, artistic treatment versus original production method, model confidence versus verified evidence.

## First demonstration

Start with a **5–10 second, legally usable, simple 2D/2.5D reference** showing a clear subject movement, ease, hold and one transition. Complex reflective 3D product films are valuable research targets but make poor first accuracy benchmarks because the underlying scene is ambiguous.

Required demonstration outputs:

1. Source hash and media manifest.
2. Detected shot ranges/contact sheet.
3. Tracked subject positions and fitted motion curve with error.
4. Versioned analysis JSON with uncertainty and provenance.
5. Proposed Kumiki treatment, validated against supported operations.
6. Native Kumiki-rendered MP4 and measured reference comparison.
7. Short human review describing successes, mismatches and next iteration.

**Success criterion:** the measured timing and visual communication of one independently recreated technique survive the entire pipeline. Then expand to lighting, 3D motion, sound, and increasingly complex cinematic references.

## Non-goals

- A new animation engine, replacement for Kumiki UI, or second film timeline.
- A general video downloader or third-party asset scraper.
- Exact extraction of hidden proprietary After Effects, Blender, Cinema 4D or studio project settings.
- Automatic recovery of metrically correct 3D geometry from arbitrary edited footage.
- Guaranteed photorealism based only on numeric similarity.
- Subscription-required or cloud-only model inference.
- Publishing catalog items as production-ready without real rendered evidence.

## Contribution expectations

For each feature PR, identify an actual missing capability, add deterministic tests, keep optional ML dependencies isolated, include a real sample report or render, and document uncertainty and licensing. Prefer one verified end-to-end slice over many untested analyzers or technique names.

---

**Vision:** A research-backed, technically reproducible library of cinematic techniques that lets Kumiki create more beautiful, more intentional, and easier-to-understand explainer videos.
