# One-command reference study

`study-reference` is the local-first entry point for studying a reference clip and generating everything currently possible **without AI**. It deliberately stops at **two complementary evidence review galleries**: cinematic intent, real camera/light rigs, narration strategy and premium quality are not machine-certified.

```bash
python -m pip install -e '.[motion]'
kumiki-ref study-reference ./reference.mp4 \
  --max-seconds 10 --thumbnails 8 --max-cues 8 \
  --catalog-root catalog/entries --out ./runs
```

It returns the path to a browsable local **study overview** `index.html` linking both a chronological shot storyboard and the technique-cue gallery. It composes existing verified stages; it does not implement a second video analyzer, clock or renderer.

| Stage | Material produced |
| --- | --- |
| `analyze` | A source-hashed atomic analysis bundle with original PTS, candidate cuts, contact sheet, global image motion, sparse feature motion and RGB appearance. No AI dependencies. |
| `propose-techniques` | Catalog-linked *hypotheses* with numerical evidence and alternatives, not physical rig recovery. |
| `shot-evidence` | Candidate edit-region summaries with exact source PTS, observed appearance/motion and no invented final end. |
| `review-techniques` | An immutable HTML gallery with three verified source frames per candidate, questions and caveats. |
| `review-shots` | An immutable HTML storyboard showing start/middle/last observed source frames per candidate region, including regions without technique cues. |
| Study manifest | Hashes, versions, selected catalog revision hashes, and a checked inventory of every derived report, HTML document and image. |

Directory example:

```text
runs/
├── analysis/
│   └── analysis-<source>-<settings>/
│       ├── analysis-run.json
│       ├── source-manifest.json, frame-timeline.json, shot-candidates.json
│       ├── image-motion.json, sparse-flow.json, appearance.json
│       └── visual/contact-sheet-.../
└── study-<source>-<settings>/
    ├── study-manifest.json
    ├── index.html  (links to both galleries)
    ├── technique-proposals.json
    ├── shot-evidence.json
    └── visual/
        ├── technique-review-.../
        │   ├── index.html
        │   ├── technique-review.json, technique-proposals.json
        │   └── frames/ (only for matched review cues)
        └── shot-gallery-.../
            ├── index.html, shot-gallery.json, shot-evidence.json
            └── frames/ (up to 24 real source frames)
```

The one-command defaults are intentionally bounded for a typical Apple Silicon M4 with 24 GB unified memory: a maximum 10-second scan, 160×90 measurement frames, 24 global motion samples, 12 sparse/appearance samples, 40 feature points, and up to eight review cues. `--max-seconds` may be 1–20, `--thumbnails` 2–24, and `--max-cues` 1–8. Use the individual commands when you need a larger window, higher resolution or alternative parameters. The study's numeric stages need the optional `motion` extra (NumPy), but **never** auto-download a neural model or call a paid service.

The analysis bundle and derived study are published atomically at their respective boundaries. If a late derived step fails, the completed **valid analysis bundle is reusable**; there is no incomplete published study. Exact repeats verify hashes and reuse the study; missing, additional or modified output files raise an error. Changed sources/settings/catalog entries produce a new identity. The new [v2 study manifest](../schemas/v2/reference-study.schema.json) requires both galleries and the overview. Existing [v1 studies](../schemas/v1/reference-study.schema.json) retain their original identity and remain verifiable, including for separate grounded review notes. Re-running `study-reference` generates the new v2 identity without altering a saved v1 study.

The output is a visual review starting point for a coding agent. It must check actual source frames and story purpose, resolve the currently available Kumiki UI contracts, implement an **original** technique, render full motion, compare at explicit time anchors, and obtain human sign-off before claiming any premium production quality or promoting a catalog entry.

To add source-linked observations, rejected hypotheses, story interpretations and original implementation suggestions **without modifying immutable evidence**, see [grounded review notes](review-notes.md).
