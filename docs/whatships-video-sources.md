# YouTube and What Ships as reference-video sources

Kumiki Reference Lab's `video-sources` command provides a **provider-neutral, metadata-only discovery interface** for YouTube and [What Ships](https://whatships.com/). It does not download, stream, transcode, or inspect third-party video assets.

## Usage

From the repository root:

```bash
PYTHONPATH=src python -m kumiki_reference_lab video-sources validate
PYTHONPATH=src python -m kumiki_reference_lab video-sources list --provider whatships --min-views 1000000
PYTHONPATH=src python -m kumiki_reference_lab video-sources search "paper motion" --provider whatships
PYTHONPATH=src python -m kumiki_reference_lab video-sources show whatships:figma-3980
```

All outputs are JSON. `show` returns a **browser page** in `watchUrl` and the original X URL in `originalUrl`, when the What Ships detail record provides one. For YouTube references, both URLs point to the canonical YouTube video. IDs are provider-qualified (`youtube:<video-id>`, `whatships:<slug>`) to avoid cross-provider collisions.

The default [`research/whatships-index-2026-11-10.json`](../research/whatships-index-2026-11-10.json) is a frozen snapshot of **2,861 indexed videos** across eight categories, of which **419** have rich detail metadata (including historical view counts for 418). The smaller [`research/whatships-motion-2026-11-10.json`](../research/whatships-motion-2026-11-10.json) is a **69-film Motion cohort** in which all entries have detail. Sources: the site's [public index](https://whatships.com/search-index.json) and read-only [MCP tools](https://whatships.com/developers/) `search_videos` and `get_video`, retrieved November 10, 2026. To use a newer local snapshot:

The [browser-observed motion notes](whatships-observed-motion.md) record directly seen moments in several playable clips, clearly separated from metadata and unmeasured production hypotheses.

```bash
PYTHONPATH=src python -m kumiki_reference_lab video-sources list \
  --whatships path/to/newer-whatships-metadata.json --provider whatships
```

Index counts by category: AI 1,122, Developer tools 603, Other 335, Design 310, Productivity 165, Consumer 161, Hardware 96, Motion 69. In the seven non-Motion categories, 50 entries per category have rich details; other entries remain index-only. The source index is a directory of curated submissions, not a random sample of launches.

Missing detail records stay `evidenceStatus: index-only`: views, publish date, duration, and original X URL remain `null` rather than guessed. Details are `detail-snapshot`. View counts are frozen observations at `viewsCapturedAt`, not live counts, unique viewers, engagement, retention, or evidence of creative effectiveness. Sorting on known views does not correct for age, audience size, topic, or paid distribution.

## Extensibility and safe analysis

The normalized interface in `catalog/video_sources.py` separates a provider's URL and provenance from the numerical analysis source. A new provider adds a validating adapter that outputs the same fields without changing the legacy YouTube-only `video-references` contract. Never feed a `watchUrl` to FFmpeg as though it were a video file. What Ships explicitly describes its player as viewing access, **not a download CDN**; the original creators retain content rights. The presence of a playable video does not grant redistribution permission.

For actually measured cinematography, use the browser to form *review questions*, then obtain a separately authorized local media file and use `study-reference`, `visual-events` or `visual-style-review` with source timestamps and hashes. Record visual style, camera movement, lighting and cut frequency **only** from actually reviewed footage; titles, tags, posters and motion-category labels are not visual measurements. See [reference-study](reference-study.md) and [timecoded visual style reviews](timecoded-visual-style-review.md).
