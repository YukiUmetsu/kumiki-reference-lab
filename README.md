# Kumiki Reference Lab

**Reference-video analysis, cinematic technique research, and reproducible motion reconstruction for the Kumiki ecosystem.**

> **Project status: proposed.** This README is an implementation brief for a new repository, not documentation of an already-working CLI. Commands, package paths, schemas, and features marked *planned* must be implemented and verified before they are advertised as available.

**Implemented foundation:** the dependency-free Python `inspect` command reads a local video with FFprobe and writes a source manifest. Shot detection, tracking, semantic analysis, treatment compilation, and reference comparison remain planned.

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
| Motion | OpenCV optical flow, keypoint tracking, affine/homography fitting | Learned correspondence/tracking | Normalized trajectories and fit residuals |
| Subject tracking | Manually seeded masks/boxes and classical tracking | SAM 2 or suitable video segmentation model | Subject masks, identities and confidence |
| Animation curves | Normalize tracks, fit linear/Bézier/spring candidate curves, compare residuals | Learned motion grouping | Frame-relative motion curves |
| Camera hypotheses | Robustly separate background from foreground movement; estimate translation, scale, roll | Multiview SfM when assumptions hold | Camera-motion *hypotheses* |
| Lighting and look | Color histograms, exposure, highlights, shadows, key/fill contrast proxies | Inverse-rendering/vision models | Appearance observations and hypotheses |
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

**Available now (Python 3.11+, FFprobe installed):**

```bash
PYTHONPATH=src python -m kumiki_reference_lab inspect ./reference.mp4
PYTHONPATH=src python -m kumiki_reference_lab inspect ./reference.mp4 --out ./runs/example
PYTHONPATH=src python -m unittest discover -s tests -v
```

The manifest records metadata and SHA-256, while honestly marking frame-by-frame PTS and VFR status as unknown until sampled. `--rights-status user-declared-authorized` is an **assertion by the user**, not automated legal verification. The command does not copy media or download models.

**Planned interfaces (not implemented):**

```bash
# Identify cuts and produce evidence/contact sheets
kumiki-ref analyze ./reference.mp4 --features shots,motion,color --out ./runs/example

# Optional subject tracking, with explicit model selection
kumiki-ref track ./reference.mp4 --shot shot-001 --prompt "product" --backend sam2

# Optional semantic interpretation; may use a local configured model
kumiki-ref interpret ./runs/example/analysis.json --model local

# Propose reusable techniques and a typed Kumiki treatment
kumiki-ref catalog suggest ./runs/example/analysis.json
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
│   ├── pipeline/                   # Stage DAG, restart/cache, results (future)
│   ├── analyzers/
│   │   ├── media/                  # Implemented: FFprobe source inspection
│   │   ├── shots/                  # Future: edit detection
│   │   ├── motion/                 # Future: optical flow and easing fits
│   │   └── subjects/              # Future: segmentation and identity
│   ├── backends/
│   │   ├── ffmpeg/                 # Implemented: FFprobe adapter
│   │   ├── opencv/                 # Future: classical CV
│   │   └── segmentation/          # Future: optional ML
│   ├── interpretation/             # Future: story/technique semantics
│   ├── catalog/                    # Future: search, ranking and publication
│   ├── comparison/                 # Future: aligned render metrics
│   ├── optimization/               # Future: bounded parameter fitting
│   └── integrations/kumiki/       # Future: export; no second renderer
├── schemas/v1/                    # Interchange schemas
├── catalog/entries/               # Future: approved research metadata only
├── fixtures/                       # Original or explicitly licensed test videos
├── tests/
├── examples/treatments/
└── docs/architecture.md
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
- **Exit:** accurately recover cuts and known motion from original, programmatically generated test footage; no AI dependencies.

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
