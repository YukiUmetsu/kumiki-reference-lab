# Visual reference timeline

`review-timeline` creates a **self-contained, offline HTML report** with five aligned evidence tracks: candidate video regions/cuts, apparent image-plane displacement, measured interior edit intervals, candidate audio quiet-level contrasts, and possible audio level attacks. It also provides accessible data tables for exact values and provenance, rather than relying solely on color or a chart.

The same viewer is included automatically in `study-reference` v5. Open the returned study `index.html` and choose **Evidence timeline**; the standalone command remains available for custom measurement settings.

## Command

```bash
kumiki-ref analyze ./reference.mp4 --max-seconds 10 --motion --appearance --out ./runs
kumiki-ref review-timeline ./reference.mp4 \
  ./runs/analysis-.../analysis-run.json \
  --window-ms 400 --max-audio-frames 4096 \
  --onset-min-rise-db 12 --onset-min-peak-dbfs -40 --onset-cooldown-ms 120 \
  --out ./runs/reviews
```

Replace the sample analysis path with the actual `analysis-run.json` printed by `analyze`. Audio analysis is attempted from the **same original video source bytes**; no subscription or AI service is required. `--motion` and `--appearance` are optional, but make their respective region tracks more informative. FFmpeg and FFprobe are required. The source scan remains bounded by the original analysis-run settings.

The resulting `timeline-<source>-<settings>/` directory contains:

- `index.html`: SVG-aligned timeline, cut-level audio comparison, pacing table, motion/appearance table and provenance.
- `shot-evidence.json`, `edit-rhythm.json`, `av-cut-evidence.json`: source-linked, immutable numeric evidence snapshots.
- `audio-onsets.json`: possible RMS-level attacks, source audio PTS, two-frame support windows and explicit threshold/clock-gap accounting.
- `timeline-review.json`: versioned settings and SHA-256 file inventory; an exact rerun verifies the output and refuses modified/extra files.

The current viewer uses [timeline v2](../schemas/v2/timeline-review.schema.json). Previous [timeline v1](../schemas/v1/timeline-review.schema.json) reports remain preserved in existing v4 study bundles. See [`docs/shot-evidence.md`](shot-evidence.md), [`docs/edit-rhythm.md`](edit-rhythm.md), [`docs/av-cut-evidence.md`](av-cut-evidence.md), and [`docs/audio-onsets.md`](audio-onsets.md).

## Design and interpretation rules for coding agents

| Track | Encoded measurement | Never infer |
| --- | --- | --- |
| Candidate regions | Position from original rational video PTS; next candidate boundary or final observed timestamp | Verified edit or complete last-shot duration |
| Image-plane motion | Mean normalized image displacement per sampled pair, capped for display | Camera velocity, dolly, subject motion, or physical world units |
| Interior cut gaps | Exact elapsed seconds between adjacent algorithmic candidate cuts | Editing intent, confirmed shot duration, pacing quality |
| Audio at cuts | Difference in decoded audio quiet-frame fraction in bounded before/after windows | Speech, music beats, sound effects, causal synchronization |
| Audio level attacks | Framewise RMS increases or return from the measurement floor; anchors use original audio PTS | Sample-accurate onset, instrument, voice, beat, SFX, verified video sync |

This is a **candidate shared source presentation-time axis**, not calibrated audiovisual sync. The video and audio stream clocks were independently read and expressed as rational seconds; the original media's edit lists, priming, offsets or discontinuities may still affect perceived alignment. A source hash proves both measurements came from the same bytes, not that the decoded signals share a verified physical origin.

The first bounded region may start partway through a source shot and the final region has no verified end. The chart deliberately shows only measured interior cut-to-cut intervals. No audio stream shows an explicit empty audio state; no such stream is **not** proof of artistic silence. Missing optional motion/appearance evidence appears as an em dash in the table rather than a zero.

### UI implementation choices

- **Purpose:** let a video editor quickly see what happens near an algorithmic candidate cut and then inspect the corresponding numeric evidence. The chart is a navigation aid, not an editor or a synchronized player.
- **Hierarchy:** source range and cut count first; a five-track chart next; numeric audio-contrast, onset, pacing, and image tables underneath; detailed provenance behind a native `<details>` disclosure.
- **Typography/layout:** system font, 15px main body with 1.5 line height, 1,200px maximum content width, 18–36px responsive gutters, dark navy surfaces and restrained cyan/amber/purple measurement roles. Colors never replace text labels.
- **Accessibility:** semantic headings/tables with column and row headers, chart alternative text, keyboard-focusable horizontal scroll region, strong focus ring, no required hover interaction, no animation, and reduced-motion-safe behavior. At narrow widths the chart and data tables scroll separately without clipping contents.
- **Runtime:** pure HTML/CSS/SVG, no external fonts/assets, script, network request or bundled React/Kumiki runtime. Using the production Kumiki UI scene library here would require extra runtime/dependencies without improving a read-only offline research document.
- **Provenance:** every value remains linked to the verified analysis source/run and the individual versioned reports. The rendered HTML and report snapshots are checksum-inventoried.

### Design sources

The interface adapts general principles rather than copying production editors:

- [Adobe Premiere Pro markers](https://helpx.adobe.com/premiere/desktop/organize-media/apply-labeling/overview-of-markers.html): distinguish time markers from annotated meaning; show source time explicitly.
- [DaVinci Resolve editing interface](https://www.blackmagicdesign.com/products/davinciresolve/edit): align separate kinds of temporal evidence on the same horizontal axis while respecting the distinct meaning of video and audio tracks.
- [Apple HIG charts](https://developer.apple.com/design/human-interface-guidelines/charts): keep data charts legible with clear labels, scale and supporting values.
- [W3C accessibility principles](https://www.w3.org/WAI/fundamentals/accessibility-principles/): preserve keyboard access, useful alternative text, and visible focus.

## Verification

Run `PYTHONPATH=src python -m unittest tests.test_timeline_view -v` for synthetic audiovisual fixture tests, exact provenance checks, HTML escaping, accessible markup, missing-audio behavior, idempotent reuse and tamper rejection. The FFmpeg integration tests remain **local**; hosted CI continues running the small smoke suite without installing video/NumPy dependencies.

Visual QA at normal browser size, high zoom and a narrow viewport is still recommended before expanding this into a creative editing tool. Never certify aesthetic quality from schema or unit-test success alone.
