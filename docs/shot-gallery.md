# Shot-region visual storyboard

Use **`review-shots`** to look at the source's chronological editing and visual story structure **even when no measured lighting or camera technique cue is detected**. It renders a browsable HTML gallery of genuine source frames grouped by the existing `shot-evidence` candidate edit regions.

```bash
kumiki-ref analyze reference.mp4 --max-seconds 10 --out runs/
kumiki-ref review-shots reference.mp4 \
  runs/analysis-<source>-<settings>/analysis-run.json \
  --max-regions 8 --region-offset 0 --width 480 --out runs/
```

Open the printed `shot-gallery-.../index.html` file. Each region shows its first, nearest-middle, and **last actually observed** frame, with original source PTS and exact source-timebase seconds. Regions containing only one or two frames display those only. Up to eight candidate regions and 24 decoded JPEGs are permitted per output; use `--region-offset 8` for later pages.

Each card includes the unmodified edit-region evidence, possible cut boundaries and review questions:

- What must the viewer understand in this region?
- Where should attention move, and why?
- Is the visual hierarchy clear at playback speed?
- Is a detected hard cut truly an edit, or a fast motion/lighting false positive?
- How do composition, contrast, motion and later audio cues support the intended teaching point?

No prose answer is generated. The report does **not** infer narration, emotions, intent, actual lighting, lens focal length, material type, 3D structure or editorial keyframes. A `shot-evidence` cut is an algorithmic candidate, not a confirmed shot; the final region's exclusive end remains `null`, not a fabricated film end.

The command first verifies the complete source-hashed analysis run. It independently probes the video and extracts original frame PTS. Each region's start, last frame and frame count must agree with the newly decoded stream. The JPEG extractor then checks the output stream clock and selected PTS again. Output is atomically published with a per-file SHA-256 inventory and reused only when intact; modified, absent, additional or symlinked output files are rejected. The [JSON contract](../schemas/v1/shot-gallery.schema.json) records the selected region IDs, source-PTS/image mappings and `qualityVerdict: not-performed`.

This is an **evidence review surface**, not a 3D reconstruction, an AI storyboard or proof of artistic quality. To record confirmed observations, possible storytelling purpose, rejected hypotheses and original Kumiki design suggestions, use the separate [review-notes](review-notes.md) contract with exact source-PTS anchors.

The `study-reference` command now includes this storyboard along with its separate technique-cue gallery and returns a top-level study overview. Use `review-shots` directly when you only need the storyboard or want to page through regions beyond the first eight.
