# Side-by-side source-time frame review

`compare-frames` creates a visual reference-versus-render review sheet from
**two local video files**, not just their appearance metrics. It requires
explicitly chosen time anchors and never invents timestamps from nominal FPS.

```bash
kumiki-ref compare-frames reference.mp4 kumiki-render.mp4 \
  --reference-anchor-ms 3000 --candidate-anchor-ms 2000 \
  --time-scale 1 --tolerance-ms 150 \
  --max-seconds 10 --max-samples 10 --width 480 \
  --out ./runs
```

Use time anchors at corresponding content events. With the example above,
the reference moment at 3.0s is compared with the rendered moment at 2.0s.
The same rational mapping and one-to-one monotonic pairing used by
[`compare-appearance`](appearance-comparison.md) applies. Sample limits
are intentionally small: 5–12 uniformly presentation-time-selected source
frames per input, within a 20-second prefix, JPEGs up to 800px wide.

The command outputs an immutable `frame-compare-*` bundle containing:

- `index.html`: responsive paired source/render JPEGs with exact source PTS
  and timecodes. Open locally to assess story clarity, focus, lighting,
  materials, text placement, animation spacing and visual craft.
- `reference/frame-*.jpg` and `candidate/frame-*.jpg`: independently decoded
  frames with verified PTS, never assigned synthetic frame indices from FPS.
- `frame-comparison.json`: [`kumiki.frame-comparison.v1`](../schemas/v1/frame-comparison.schema.json)
  with input hashes, sampling settings, alignment transform, paired source
  ordinals/timestamps, alignment errors and SHA-256 inventory of every image
  and HTML page.

The bundle is **transactional**. If a decoder fails, an original video changes
while decoding, or there is no pair within the stated tolerance, no partial
review bundle is published. A repeat with identical source bytes and settings
verifies the existing files. Modified outputs are rejected, never silently
overwritten.

This tool gives a reviewer concrete side-by-side evidence, not a machine
verdict. Perspective, lens, color management, temporal sampling, crop and
different source content can make equal-time frames differ for legitimate
reasons. `qualityVerdict` stays `not-performed` until a genuine visual
craftsmanship review is recorded. Full-speed synchronized **video** comparison,
ROI-aware alignment, perceptual metrics and causal scene hypotheses are later
steps.
