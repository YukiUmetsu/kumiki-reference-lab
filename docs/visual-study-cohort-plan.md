# A reproducible study queue for camera, lighting, editing and visual style

The previous [300-row audience sample](audience-benchmark-methodology.md) contains public reach and runtime data, but **not YouTube video IDs** or real visual observations. It cannot tell us whether paper-cut animation, camera moves, lighting or shot rhythm correlate with view counts. Before comparing visual styles we need to select both stronger- and ordinary-performing uploads, resolve their identity, inspect real footage, and annotate the **same visual questions** for both sides.

## Current selection results

Run the offline selection against the frozen source snapshot:

```bash
PYTHONPATH=src python -m kumiki_reference_lab audience-benchmarks study-plan \
  --identity-candidates research/video-id-candidates.v1.json \
  --out ./runs/study-queue
```

With default parameters on the November 10, 2026 source snapshot:

| Selected channel | Candidate contrast pairs | What makes the cohort useful |
| --- | ---: | --- |
| Alan Becker | 2 | Short-form 2D/character motion |
| Kurzgesagt | 3 | Stylized 2D explanation, short and long formats |
| League of Legends | 3 | Cinematic music, game trailers and short promos |
| Real Engineering | 3 | Technical 3D explanation, fast shorts and longer documentary |
| GH'S | 3 | Character-driven animated short-form and compilations |
| Daily Dose of Internet | 3 | Live-action montage and editorial pacing |
| **Total** | **17** | **34 row slots, not 34 independently verified videos** |

**283/300 rows are eligible** with stated runtime of at most 60 minutes; ten over-one-hour, three runtime-unknown, and four title/date-ambiguous rows are excluded. Two ambiguous duplicate-title/date groups are flagged explicitly:

- League of Legends, `HEARTSTEEL Live My Life | Skins Trailer - League of Legends`, September 23, 2026, appears twice with different duration and metrics.
- GH'S, `LOSTEN & SOLIA - EMOTIA ESCAPE | ROBLOX`, November 5, 2026, appears twice with different reported views despite identical duration.

Those might be real separate uploads or an artifact of a listing; without unique IDs, this dataset does **not** decide which. The plan excludes all four rather than counting them as independently identified films.

## Selection protocol and limits

1. Within each channel, retain rows with stated runtime between one second and one hour. Reject ambiguous same-channel/title/publication-date groups; preserve all other source-table rows intact.
2. Group by runtime: under 1 minute, 1–3 minutes, 3–10 minutes, 10–30 minutes, 30–60 minutes. This is **runtime**, not proof of YouTube Shorts distribution.
3. Identify candidate contrasts where both videos are in the **same channel and runtime family**, publication dates are at most 45 days apart, runtime ratio at most 1.75, and observed view-count ratio at least 2.
4. Prefer smaller source-age gap, then more similar runtime; use view-count contrast only as a final tie-breaker. Choose at most three disjoint pairs per channel, cycling runtime families for diversity.
5. Report every source-table ordinal and SHA-256 fingerprint so a refreshed snapshot, duplicate, or mutated metric cannot silently bind the wrong film. Rows remain **not frame reviewed**.

Default results are **purposefully outcome-selected leads**, not a random sample or a causal effect estimate. The ratio means *these two observed view counts differ*; it does not mean that style, lighting, a camera move, or even duration caused the difference. Matching does not control topic, promotion, recommendation exposure, thumbnail/CTR, unique viewers, audience retention, format, or time-of-day differences. Different channel sizes and snapshots must not be pooled as comparable denominators.

Change the predeclared bounds when necessary and record them alongside results:

```bash
PYTHONPATH=src python -m kumiki_reference_lab audience-benchmarks study-plan \
  --pairs-per-channel 2 --max-source-age-gap-days 14 \
  --max-runtime-ratio 1.5 --min-view-ratio 3
```

The plan may return **fewer** pairs when there is no qualifying contrast. It never fills a quota using unsupported matches.

## First clickable research pair

The optional [`video-id-candidates.v1.json`](../research/video-id-candidates.v1.json) contains **two exact row-linked YouTube ID leads** corroborated by YouTube-indexed title, uploader, and publication date. It does not assert that the direct watch pages were opened or media visually reviewed; direct web fetches were throttled during research.

| Real Engineering reference | Source-table date / duration | Source-table observed views | Link evidence |
| --- | --- | ---: | --- |
| [How We Built The ISS](https://www.youtube.com/watch?v=j0ZZfIz9R1I) | 2025-12-07 / 36:05 | 1,594,415 | Indexed YouTube listing attributes the video to Real Engineering and dates it 2025-12-06; one-day timezone difference |
| [Solar Farms in Space - Reflect Orbital](https://www.youtube.com/watch?v=Vf_pS0XSTyo) | 2025-12-03 / 31:18 | 546,117 | Indexed YouTube listing with matching creator, title and calendar date |

The source-table view-count contrast is **about 2.92×** with a four-day source-date gap and similar runtimes. That ratio alone says nothing about which cinematic or educational methods are better. Confirm the destination channels and exact video identity before annotation, especially if links or titles change. The numeric counts above remain the **frozen third-party snapshot**, not live YouTube API measurements.

Run without `--identity-candidates` to obtain an unlinked queue. The ID catalog loader validates source row index, fingerprint, exact canonical watch URL, unique 11-character ID, creator, title, date alignment (at most one day for source timezone differences), and explicit `index-corroborated-watch-page-not-opened` status. A future source refresh invalidates stale fingerprints rather than silently joining changed metrics.

## Next data-collection stage

1. Resolve the remaining selected row IDs using independently checkable original-publisher evidence; do not choose a reaction upload with a similar title.
2. Confirm authorized media access. For a permitted local original, record immutable source hash, PTS and full reviewed window.
3. Use the existing [visual style/camera/lighting taxonomy](visual-style-camera-lighting-methodology.md) to annotate camera kinds, light/look changes, shot/edit boundaries, style, sound, subject and narrative beat. Observe the film at full speed with and without sound; sampled stills alone are insufficient.
4. Require the same rubric for both sides. Keep self-declared review labels distinct from measured motion and brightness proxies (`visual-cadence`) and from source-verified production techniques.
5. Only after both linked films are coded should we compare measured frequencies within their matched cohort, disclose reviewer disagreement and missing data, and test whether any pattern persists across **multiple** cohorts. No observational comparison can by itself prove what causes popularity.

All third-party work remains **inspiration only**. Public watchability or a video ID does not authorize downloading, extracting or redistributing source footage.
