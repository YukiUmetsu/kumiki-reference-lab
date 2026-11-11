# YouTube, What Ships, and optional Directors' Library sources

Kumiki Reference Lab's `video-sources` command provides a **provider-neutral, metadata-only discovery interface** for YouTube, [What Ships](https://whatships.com/), and optional [Directors' Library](https://directorslibrary.com/) records. It does not download, stream, transcode, or inspect third-party video assets.

## Usage

From the repository root:

```bash
PYTHONPATH=src python -m kumiki_reference_lab video-sources validate
PYTHONPATH=src python -m kumiki_reference_lab video-sources report
PYTHONPATH=src python -m kumiki_reference_lab video-sources list --provider whatships --min-views 1000000
PYTHONPATH=src python -m kumiki_reference_lab video-sources search "paper motion" --provider whatships
PYTHONPATH=src python -m kumiki_reference_lab video-sources show whatships:figma-3980
PYTHONPATH=src python -m kumiki_reference_lab video-sources observations --visual-tag editorial-collage

# Opt in to the separate Directors' Library page catalog:
PYTHONPATH=src python -m kumiki_reference_lab video-sources search "distance" \
  --provider directors-library \
  --directors-library research/analysis/directors-library/index-2026-11-11-pages5.json
```

All outputs are JSON. `show` returns a **browser page** in `watchUrl` and the original X URL in `originalUrl`, when the What Ships detail record provides one. For YouTube references, both URLs point to the canonical YouTube video. IDs are provider-qualified (`youtube:<video-id>`, `whatships:<slug>`, `directors-library:<site-path>`) to avoid cross-provider collisions. Directors' Library's `originalUrl` is only a sanitized embedded-player reference, **not a licensed downloadable file**. Its `publishedOn` is the site's post date, not necessarily the film's original release. Unknown views and durations stay `null`.

`report` summarizes source and category coverage, known view snapshots, known durations, and category medians. Missing evidence stays missing; a category with no verified view snapshots has a `null` median. This is a **metadata coverage report**, not a quality, virality, shot-cut frequency, camera or lighting analysis.

The [cross-category coverage analysis](whatships-category-coverage.md) explains the 2,861-entry breakdown and why comparing raw views across curated categories would be misleading.

The default [`research/whatships-index-2026-11-10.json`](../research/whatships-index-2026-11-10.json) is a frozen snapshot of **2,861 indexed videos** across eight categories, of which **419** have rich detail metadata (including historical view counts for 418). The smaller [`research/whatships-motion-2026-11-10.json`](../research/whatships-motion-2026-11-10.json) is a **69-film Motion cohort** in which all entries have detail. Sources: the site's [public index](https://whatships.com/search-index.json) and read-only [MCP tools](https://whatships.com/developers/) `search_videos` and `get_video`, retrieved November 10, 2026. To use a newer local snapshot:

The [browser-observed launch-film notes](whatships-observed-motion.md) record directly seen moments in nine playable clips spanning Motion, Design, AI, Hardware and Developer tools, clearly separated from metadata and unmeasured production hypotheses.

The matching [structured observation dataset](../research/whatships-browser-observations-2026-11-10.json) is linked by provider-qualified ID and can be queried with `video-sources observations --source-id whatships:paper-mono-code` or `--visual-tag screen-recording`. These are **selected browser-player moments**, never complete shot timelines; the separate data schema prohibits unverified cut-frequency, camera, or light measurements. Entries are validated against the currently loaded source catalog so unknown video IDs cannot acquire spurious visual evidence.

```bash
PYTHONPATH=src python -m kumiki_reference_lab video-sources list \
  --whatships path/to/newer-whatships-metadata.json --provider whatships
```

Index counts by category: AI 1,122, Developer tools 603, Other 335, Design 310, Productivity 165, Consumer 161, Hardware 96, Motion 69. In the seven non-Motion categories, 50 entries per category have rich details; other entries remain index-only. The source index is a directory of curated submissions, not a random sample of launches.

Missing detail records stay `evidenceStatus: index-only`: views, publish date, duration, and original X URL remain `null` rather than guessed. Details are `detail-snapshot`. View counts are frozen observations at `viewsCapturedAt`, not live counts, unique viewers, engagement, retention, or evidence of creative effectiveness. Sorting on known views does not correct for age, audience size, topic, or paid distribution.

## Extensibility and safe analysis

The normalized interface in `catalog/video_sources.py` separates a provider's URL and provenance from the numerical analysis source. A new provider adds a validating adapter that outputs the same fields without changing the legacy YouTube-only `video-references` contract. Never feed a `watchUrl` or iframe `originalUrl` to FFmpeg as though it were a licensed source file. What Ships explicitly describes its player as viewing access, **not a download CDN**; the original creators retain content rights. Directors' Library's [terms](https://directorslibrary.com/cookies-legal/) prohibit copying without permission. Vimeo downloads are controlled by individual video owners and cannot be assumed from an embedded player. The presence of a playable video does not grant redistribution permission.

For actually measured cinematography, use the browser to form *review questions*, then obtain a separately authorized local media file and use `study-reference`, `visual-events` or `visual-style-review` with source timestamps and hashes. Record visual style, camera movement, lighting and cut frequency **only** from actually reviewed footage; titles, tags, posters and motion-category labels are not visual measurements. See [reference-study](reference-study.md) and [timecoded visual style reviews](timecoded-visual-style-review.md).
