# Offline three-frame human labeling workbench

The offline review workbench reduces the labor of validating small local
Magnitude models against **actual source frames**. It never treats a model
guess as human ground truth. Its browser UI links to existing ignored
low-resolution PNG previews; it does **not** download, copy, embed or
upload video content.

## Preconditions

You must already have an authorized source-video study and a local frame
workspace created using the documented `kumiki-watch --review-frames`
workflow. In that same repository clone, run `kumiki-insights` with
`--sequence-model LOCAL_MODEL_ID` and either `--roi-seeds` or `--auto-regions`
to produce a source-hashed `.insights.json` report with tracked regions and
three-anchor reviews. The workbench does not call Magnitude itself.

## Build the local review page

```bash
kumiki-sequence-benchmark review-pack \
  --workspace 'workspace/frame-review/<source-id>' \
  --insights 'research/analysis/online-videos/<source-id>.insights.json'
```

Open `workspace/frame-review/<source-id>/review-sequences.html` in a local
browser (using the `file://` URL). The page is created **inside the same
Git-ignored workspace** so it can load its original `frames/frame-000001.png`
references with relative paths. You can pass `--out` to use another
**new** `.html` filename inside that directory; it never overwrites a prior
review pack or creates a copy elsewhere.

## Label without seeing model predictions

Each sequence shows three actual saved source previews: start, middle,
and end, with the existing tracked image-region boxes outlined in red
for ROI A and cyan for ROI B. Their opaque IDs are for bookkeeping;
they are not a person's identity or a verified character classification.

Choose a category independently for each pair:

- `no-clear-change`
- `apparent-region-translation`
- `apparent-box-size-change`
- `apparent-pose-or-silhouette-change`
- `apparent-turn`
- `apparent-relative-position-change`
- `not-observable` (insufficient evidence / ambiguous images)

Review the frames yourself. If two stills do not support a category,
choose `not-observable`; **do not infer walking, touching, talking, intent,
character name, a physical camera movement or unobserved frames**.

The page deliberately **does not display the model's category predictions**
or its reasoning. It only embeds a pending human-label template, with
every category initially `null` and coverage `pending-review`.

## Save, resume and approve locally

Use **Export pending draft** at any time. It downloads a JSON document
with incomplete labels allowed and `coverageDeclaration: pending-review`.
To resume, open the same HTML page and select the downloaded JSON using
**Resume draft**. The browser validates the source and insights-file hashes,
model tag, sequence IDs, frame indices, timestamps and category vocabulary
before accepting it; resuming never marks a draft approved.

Once both phases of **every** listed sequence have been labeled and a human
reviewer ID has been entered, **Export reviewed labels** becomes enabled.
The downloaded JSON contains
`coverageDeclaration: all-listed-source-frame-phases-human-reviewed`.
This is a human's explicit assertion; the software does not pretend to
verify who inspected the frames.

Do not commit original videos, PNG frames, review HTML or private
unapproved drafts. All browser functionality is standalone and runs
offline without API access, internet assets, remote fonts or analytics.
Browsers can differ in how local `file://` image access/downloads work;
if the images fail to render, use the preexisting offline frame viewer
to inspect the same frame indices before labeling.

## Score and save the audited results

```bash
kumiki-sequence-benchmark evaluate \
  --insights 'research/analysis/online-videos/<source-id>.insights.json' \
  --labels '/path/to/human-phase-labels.reviewed.json' \
  --out 'research/analysis/validation/<source-id>.benchmark.json'
```

The evaluator independently checks the full label roster, original
report digest, human approval, categories and frame anchors, then
reports source-bound accuracy, errors and abstentions. A workbench HTML
page or a pending draft cannot be used as ground truth.

## Guardrails and limitations

- `review-pack` validates the workspace's source SHA, each sequence's
  exact decoder timestamps, tracked ROI origin, shot and observed frame.
- Every PNG used by the page must be an existing nonsymlinked, correctly
  decoded low-resolution frame of the expected dimensions.
- A broken or missing image, mismatched source or unsupported track
  causes an explicit error **before** writing the review page.
- Unsafe HTML in external IDs is escaped; the embedded JSON template
  escapes tag-delimiter characters. A restrictive CSP blocks network
  requests, and no external dependencies are loaded.
- Output is bounded and atomic create-only, entirely within the ignored
  `workspace/frame-review/<source-id>` directory.
- This is a human visual-review tool, not a model validation set by
  itself. Synthetic regression tests are **not real-video accuracy**.

## Test

```bash
PYTHONPATH=src python -m unittest tests.test_sequence_review_workbench -q
```

Tests cover valid source clips, exact frame references, ROI overlays,
model-blind labeling, basic HTML injection prevention, unchanged PNG
bytes, source/time mismatches, malformed previews, unsafe output
destinations, no-overwrite behavior and the CLI entrypoint.
