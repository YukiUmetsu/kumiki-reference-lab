# Temporal cinematic intelligence: shot, motion, typography, AV, recipes

The **kumiki-insights** and **kumiki-catalog** commands extend the low-resource
Magnitude frame-by-frame review workflow. The software measures visible
evidence first and asks a local vision model only narrowly scoped questions.

No new cloud inference, subscription, or website restriction is introduced.
This pipeline proposes *original* animation techniques, never reproduces
copyrighted source frames or asserts hidden production details.

## Install

Python 3.11+, FFmpeg/FFprobe, yt-dlp and repository installation:

    pip install -e .

To enable sampled optical flow on your Apple Silicon Mac or another CPU:

    pip install -e '.[dense]'

OpenCV is OPTIONAL. Without OpenCV or NumPy, the motion stage uses a bounded,
standard-library-only RGB block-matching fallback to report approximate
image-plane displacements. It does **not** produce optical-flow feature tracks,
robust affine camera proxies or verified object motion. For finer motion evidence,
install the optional dense extra.

Install Tesseract locally only if you want OCR-based text-line boxes and
possible position-change hints. OCR is opt-in and runs on small previews.
For small typography, use a larger preview (e.g. 320x180); this remains an
approximation and cannot verify an exact font family.

## 1. Prepare authorized video and its numerical/audio evidence

    kumiki-watch 'https://creator.example/watch/reference' \
      --repo . \
      --rights-basis written-permission \
      --rights-note 'Source owner authorized this study.' \
      --acknowledge-rights \
      --review-frames --audio-cues \
      --max-seconds 180 --max-frames 10800

Video downloads are temporary and deleted whether the pipeline succeeds or
fails. All video frame previews remain only in the Git-ignored local
workspace/frame-review/<source-id>/ until explicit cleanup.

--audio-cues computes mono PCM RMS/peak levels and candidate energy attacks
before the source is deleted. The JSON contains *audioEvidence*, including
unverified candidate transients. These are NOT certified musical beats,
sound effects or dialogue. Audio/video clock alignment remains unverified.

The source report is retained at
research/analysis/online-videos/<source-id>.json.

## 2. Optional: use a small Magnitude vision model for named techniques

    REVIEW='workspace/frame-review/<source-id>'

    kumiki-frames next --workspace "$REVIEW" --mode shots

    kumiki-frames scan \
      --workspace "$REVIEW" --mode shots \
      --model 'YOUR_LOCAL_MAGNITUDE_VISION_MODEL_ID' \
      --categories animation,typography,visual-style \
      --max-calls 24 --max-failures 3

--mode shots selects shot-start and representative frames from deterministic
shot-change grouping. It is a complementary mode to changed, cuts, every and
interval. It spreads model attention across candidate shots.

Magnitude is only asked about ONE category, one frame (or short adjacent
pair) at a time. The scan is bounded and resumable. The result is exported to
research/analysis/online-videos/<source-id>.frame-notes.json.

Without Magnitude, all the measured shot/image-flow/audio work still runs.

## 3. Analyze temporal structure and original animation opportunities

    kumiki-insights --workspace "$REVIEW" --max-motion-pairs 120

Optional:

    kumiki-insights --workspace "$REVIEW" \
      --ocr --max-ocr-frames 48 \
      --max-motion-pairs 120 --max-plan-frames 48 --overwrite

Or, for a machine with very low compute or no OpenCV:

    kumiki-insights --workspace "$REVIEW" --no-motion

The output is:
research/analysis/online-videos/<source-id>.insights.json

### What this measures

- shotIntelligence: change-derived provisional shots, start/end frame,
  approximate timing, rhythm and mean display RGB/luma/saturation.
- shotAwareAgentPlan: bounded, representative frame IDs distributed across
  all detected shots to support small local AI.
- temporalMotion: optional OpenCV Lucas–Kanade short image-feature tracklets,
  robust global-image affine candidates, and local residual-motion tiles.
  This is NOT semantic person/object tracking or a physically recovered camera.
  Each sample burst is finite and cannot imply motion in unobserved gaps.
- screenText: optional local Tesseract OCR text snippets and screen-space
  boxes plus possible location changes. This does not identify font families.
- audioVisualCues: possible decoded energy attacks near provisional cut
  times. Temporal alignment is not independently verified.
- techniqueHypotheses: traceable hypotheses such as probable cut, global
  translation/zoom in image coordinates, typography position change, and
  techniques named in an agent's *unreviewed* visual annotations.
- kumikiRecipeProposals: design-time descriptions of timing, palette,
  source-evidence frames, component families and human QA gates.
  No executable Kumiki FilmDocument or actual component ID is fabricated.

The analyzer **will not** claim a paper-cut/masked-reveal effect from color
or motion alone. To propose such a technique, there must be an annotation
containing that visual description (from a human or low-confidence model).
A model observation still requires independent visual review.

### Tracking precision limits

The source frame index, decoder time and sampled feature coordinate are
measured/traceable. The labels "camera", "character", "animation technique",
"lighting rig" and "object identity" require stronger evidence than a
single feature track. The output deliberately keeps alternatives and
unverified statuses rather than fabricating confidence scores.

For actual character/person box tracking, this repository already supports
its separate seeded ROI and optional macOS Apple Vision workflows. There is
no automatically established named-character identity in these new reports.

## Optional: follow known products, characters or text across a shot

The generic optical-flow stage tracks *anonymous image features*. To follow a
particular visible subject, create a very small local seed JSON yourself or
with an image-capable agent, after inspecting the specific source frame.
This makes the hard semantic decision once, not on every frame.

    {
      "schemaVersion": "kumiki.online-region-seeds.v1",
      "sourceSha256": "<SHA-256 from source JSON>",
      "subjects": [
        {
          "id": "hero",
          "kind": "animated-character",
          "label": "Red-jacket hero",
          "startFrameIndex": 10,
          "boxNormalized": [0.2, 0.2, 0.3, 0.5]
        },
        {
          "id": "product",
          "kind": "product",
          "label": "Main product",
          "startFrameIndex": 10,
          "boxNormalized": [0.65, 0.3, 0.2, 0.35]
        }
      ]
    }

The example boxes are placeholders: measure them on real frame images
before running the tracker. Coordinates are [left, top, width, height]
normalized 0..1 with image origin at the upper left. Use a verified source
SHA-256 copied from the analyzed JSON's `source.sourceSha256`.

    kumiki-insights --workspace "$REVIEW" --roi-seeds /path/to/seeds.json       --max-roi-frames 240 --overwrite

Requires `pip install -e '.[dense]'`. At most eight seeded regions are
accepted. Each tracker follows LK image features within its original box
and estimates bounded screen translation, apparent rotation and scale.
Tracks stop at a cut, tracking failure, image boundary, or the chosen
frame budget. No automatic cross-cut re-identification occurs.

The report's `seededSubjectTracks` contains each source-seeded box
trajectory, tracking status, and **screenRelationshipProxies** for pairs
of simultaneously tracked subjects: screen overlap or apparent closeness.
Those proxies do **not** establish a conversation, emotion, social action,
or actual human/character interaction. Stronger evidence must come from
reviewed visual sequences and verified character identities.

This method is especially useful for a small local agent: it only needs
to label and box one or two keyframes, then deterministic code handles
the subsequent image-plane tracking.

## Automatic motion-region discovery (no manual boxes)

Run `kumiki-insights --workspace "$REVIEW" --auto-regions` to propose
unclassified moving screen regions from the existing locally ignored
frame previews. No Magnitude inference or OpenCV is necessary to propose
regions; OpenCV is needed to **track** eligible candidate regions.
Complex backgrounds, flashes and unsupported changes abstain rather
than being classified as characters or objects. This mode is mutually
exclusive with `--roi-seeds`. See
[automatic motion-region discovery](auto-motion-region-discovery.md)
for exact limits and tests.

## 4. Compare references and search the learned patterns

Build a searchable cross-video catalog:

    kumiki-catalog build --root research/analysis/online-videos

Search by technique:

    kumiki-catalog search \
      --root research/analysis/online-videos \
      --query 'masked reveal'

To rebuild after studying more source videos:

    kumiki-catalog build --root research/analysis/online-videos --overwrite

The output is:
research/analysis/online-videos/cinematic-technique-catalog.json

Each hit gives exact source SHA-256, source video report ID, shot ID and
frame range. The index deduplicates by downloaded **source-content hash**,
not by URL. Counts measure only YOUR analyzed corpus, not internet views,
popularity, verified techniques or success rates.

## 5. Reuse in Kumiki

Use kumikiRecipeProposals as an inspiration backlog. Each proposal:

1. names a generic potential component family, not a copied design;
2. provides the source video hash and frame anchors for rechecking;
3. attaches measured color, shot duration and timing as reference cues;
4. leaves original content, implementation ID and actual kumiki-ui API unset;
5. requires independent assets, visual QA and a verified kumiki-ui registry.

Do not describe proposed recipes as components already implemented in
kumiki-ui. Component creation and validated rendering remain separate work.

## 6. Remove previews

After saving annotations and insights:

    kumiki-frames cleanup --workspace "$REVIEW"

This removes the local ignored frame PNGs and viewer, while all JSON results
remain. Data can then be searched without retaining downloaded footage.

## Validation

Fast deterministic unit tests run in GitHub CI:

    PYTHONPATH=src python -m unittest tests.test_cinematic_intelligence -q

For actual OpenCV/FFmpeg/Tesseract/Magnitude integration tests, run on your
local Mac with those installed. CI deliberately does not install heavy
native dependencies. Source PTS are FFmpeg decoder observations, not
independently verified original packet timestamps.
