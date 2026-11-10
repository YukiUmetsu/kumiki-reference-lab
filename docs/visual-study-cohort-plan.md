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

The optional [`video-id-candidates.v1.json`](../research/video-id-candidates.v1.json) contains **11 exact row-linked YouTube ID leads**, including **five complete two-video comparisons**, corroborated by indexed YouTube titles, uploaders and publication dates. It does not assert that direct watch pages were opened or media visually reviewed; direct web fetches were throttled during research.

| Real Engineering reference | Source-table date / duration | Source-table observed views | Link evidence |
| --- | --- | ---: | --- |
| [How We Built The ISS](https://www.youtube.com/watch?v=j0ZZfIz9R1I) | 2025-12-07 / 36:05 | 1,594,415 | Indexed YouTube listing attributes the video to Real Engineering and dates it 2025-12-06; one-day timezone difference |
| [Solar Farms in Space - Reflect Orbital](https://www.youtube.com/watch?v=Vf_pS0XSTyo) | 2025-12-03 / 31:18 | 546,117 | Indexed YouTube listing with matching creator, title and calendar date |

The source-table view-count contrast is **about 2.92×** with a four-day source-date gap and similar runtimes. That ratio alone says nothing about which cinematic or educational methods are better. Confirm the destination channels and exact video identity before annotation, especially if links or titles change. The numeric counts above remain the **frozen third-party snapshot**, not live YouTube API measurements.

An additional **complete, provisional Kurzgesagt comparison** is linked: [What If You Never Slept?](https://www.youtube.com/watch?v=hiIIGMeMEuE) against [How ADHD Medication Works](https://www.youtube.com/watch?v=NIifnIP_NnQ). Both are short-form animated science videos posted two days apart, and their source-table views differ by about 3.01×. [Real Engineering's NASA telescope film](https://www.youtube.com/watch?v=rCM6dvK2Hjg) is still a one-sided indexed lead in its own selected pair: **do not** treat an unidentified comparison film as verified. The candidate index includes no camera, lighting, or style observations.

### Three more complete source-row comparisons

New YouTube search-index evidence links both sides of these within-channel, similar-runtime contrasts. Public view counts here remain the **frozen third-party source table**, not views re-measured at the indexing date. The direct watch pages were not successfully fetched, so identity is still *provisional*.

| Original-publisher videos (click to inspect) | Source-table dates and lengths | Frozen public views | Observed ratio |
| --- | --- | ---: | ---: |
| Alan Becker: [How To: Open Doors](https://www.youtube.com/watch?v=39BPQh6-ZFI) vs [Allay](https://www.youtube.com/watch?v=xu0mrfxPhbY) | 2025-10-18 (28s) vs 2025-11-01 (44s) | 17,906,332 vs 6,626,980 | 2.70× |
| Alan Becker: [Day & Night](https://www.youtube.com/watch?v=24iVz8k3lrs) vs [Fork vs Spoon](https://www.youtube.com/watch?v=wUsjDnjg2Xw) | 2025-09-20 (39s) vs 2025-08-30 (32s) | 16,466,364 vs 6,792,908 | 2.42× |
| Real Engineering: [The Problem with Geothermal Energy](https://www.youtube.com/watch?v=as9L2q9oYiE) vs [Why Deep Holes are So Expensive](https://www.youtube.com/watch?v=bYkQn2TpF2k) | 2025-09-08 (95s) vs 2025-09-08 (101s) | 4,417,197 vs 130,504 | 33.85× |

For the geothermal film, YouTube's indexed publication date appears one day earlier than the source table, within the explicitly allowed UTC/local-date difference. The striking 33.85× view difference is **not evidence** that its animation technique caused higher reach: topic, promotion, audience targeting, Shorts distribution, thumbnails and other unobserved factors may differ. Neither member of these comparisons has been decoded or visually reviewed.

Run without `--identity-candidates` to obtain an unlinked queue. The ID catalog loader validates source row index, fingerprint, exact canonical watch URL, unique 11-character ID, creator, title, date alignment (at most one day for source timezone differences), and explicit `index-corroborated-watch-page-not-opened` status. A future source refresh invalidates stale fingerprints rather than silently joining changed metrics.

## Next data-collection stage

1. Resolve the remaining selected row IDs using independently checkable original-publisher evidence; do not choose a reaction upload with a similar title.
2. Confirm authorized media access. For a permitted local original, record immutable source hash, PTS and full reviewed window.
3. Use the existing [visual style/camera/lighting taxonomy](visual-style-camera-lighting-methodology.md) to annotate camera kinds, light/look changes, shot/edit boundaries, style, sound, subject and narrative beat. Observe the film at full speed with and without sound; sampled stills alone are insufficient.
4. Require the same rubric for both sides. Keep self-declared review labels distinct from measured motion and brightness proxies (`visual-cadence`) and from source-verified production techniques.
5. Only after both linked films are coded should we compare measured frequencies within their matched cohort, disclose reviewer disagreement and missing data, and test whether any pattern persists across **multiple** cohorts. No observational comparison can by itself prove what causes popularity.

All third-party work remains **inspiration only**. Public watchability or a video ID does not authorize downloading, extracting or redistributing source footage.

## Comparing reviewed camera and lighting frequencies

After obtaining authorized local copies and **personally reviewing** both matching films, use the existing [`visual-events` review schema](visual-style-camera-lighting-methodology.md#3-camera-and-lighting-event-frequency-after-visual-review) to record actual PTS intervals, observation text, uncertainties and reviewed-window coverage. The new `compare-visual` action joins the two review artifacts to the default study-plan pair by the immutable source-row fingerprint, indexed video ID, reviewer-declared local media SHA-256 and stream index.

Prepare a separate local `bindings.json` with this exact shape (the all-zero/one hashes below are **not actual media hashes** and must be replaced with locally measured digests):

```json
{
  "schemaVersion": "kumiki.visual-study-media-bindings.v1",
  "pairId": "kurzgesagt-12-11",
  "evidenceStatus": "self-declared-source-video-to-local-media-not-independently-verified",
  "mediaLinks": {
    "higherViewedRow": {
      "sourceRowSha256": "b704f13981122ed707e7c0db169084ff615d4fb3fbc5b55285492b857a78ced1",
      "youtubeId": "hiIIGMeMEuE",
      "mediaSha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "streamIndex": 0
    },
    "lowerViewedRow": {
      "sourceRowSha256": "b16825a803011ef76d66e124bb942329c88850ba41bbc167f86b1309bbbfd3ff",
      "youtubeId": "NIifnIP_NnQ",
      "mediaSha256": "1111111111111111111111111111111111111111111111111111111111111111",
      "streamIndex": 0
    }
  }
}
```

Compute the SHA-256 of each authorized local file (e.g. `shasum -a 256 permitted-video.mp4` on macOS), copy it into the corresponding media link, and use the same hash and actual source PTS timebase in the two completed review JSON files. Copy [the visual-events example](../examples/visual-events-review.example.json) as a starting point, but **never** use its placeholder review as evidence of an actual viewing.

```bash
PYTHONPATH=src python -m kumiki_reference_lab audience-benchmarks compare-visual \
  --identity-candidates research/video-id-candidates.v1.json \
  --pair-id kurzgesagt-12-11 \
  --bindings ./local/bindings.json \
  --higher-review ./local/higher-visual-events.json \
  --lower-review ./local/lower-visual-events.json \
  --out ./runs/compared-kurzgesagt
```

The output contains per-source reviewer-interpreted event rates and counts. A **higher-minus-lower event-rate difference** is only calculated when **both** reviews declare the entire stated window was inspected, the stated window is within 95–105% of the frozen catalog runtime, and the two reviews declare the **same reviewer identity**. Otherwise the result explicitly abstains with `pairedEventRateDifferencesAvailable: false` and `pairedEventRateDifferences: null`. These checks do not prove the reviewer watched the entire original film or that the source binding is authentic. A number from a locally reviewed pair does not demonstrate a causal relationship with view counts.

This command intentionally does not score paper-cut style, camera movement percentage, editing frequency, soundtrack, or lighting quality from titles or sparse frames. Separate footage-grounded coding is needed for each additional dimension. The included test reviews are **synthetic fixtures**, not measurements of the referenced Kurzgesagt videos.
