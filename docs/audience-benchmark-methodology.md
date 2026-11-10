# Audience comparison benchmark: recent uploads, not only viral hits

The [40 evidence-linked cinematic/explainer references](cinematic-reference-videos.md) were selected **because they were popular**. Analyzing only those cannot distinguish a popular technique from something almost everyone does. To establish an exploratory comparison set, `research/audience-recent-uploads.v1.json` records **300 latest-upload table rows (50 from each of six channels)**, including ordinary performers alongside breakout videos, plus their runtime, published date, public views, likes and comments. These are **source observations, not 300 newly verified unique video IDs**; some may overlap the earlier 40-film collection.

**Research retrieval: 2026-11-10.** All observations came from the *Latest Videos* table on the linked public [Digital Creators](https://digitalcreators.jp/en) pages. They are **not live API readings**, and each page has its own last-updated date. This independent source states that its data originates from the YouTube API, but this repository did not call YouTube or download video. A `00:00:00` reported runtime is stored as `null` (unknown), not silently treated as a genuine zero-second film. Channel pages may include livestreams, Shorts, compilations, commercials and clips. Video titles are source-table labels; we do **not** assert video IDs or original URLs without verification.

## Sampling audit

| Selected source channel | Latest uploads | Source last updated | Median public views | Median likes per 1,000 views |
| --- | ---: | --- | ---: | ---: |
| [Alan Becker](https://digitalcreators.jp/en/channel/en/UCbKWv2x9t6u8yZoB3KcPtnw/videos/) | 50 | 2026-10-24 | 11,041,486 | 24.589 |
| [Kurzgesagt](https://digitalcreators.jp/en/channel/en/UCsXVk37bltHxD1rDPwtNM8Q/videos/) | 50 | 2026-11-09 | 1,884,154 | 41.972 |
| [League of Legends](https://digitalcreators.jp/en/channel/en/UC2t5bjwHdUX4vM2g8TRDq5g/videos/) | 50 | 2026-10-20 | 139,461.5 | 18.562 |
| [Real Engineering](https://digitalcreators.jp/en/channel/en/UCR1IuLEqb6UEA_zQ81kwXfg/videos/) | 50 | 2026-11-07 | 972,476 | 32.480 |
| [GH'S](https://digitalcreators.jp/en/channel/en/UCdrBnBNLsN4_cH32HWbr9qg/videos/) | 50 | 2026-11-08 | 5,402,956.5 | 13.765 |
| [Daily Dose Of Internet](https://digitalcreators.jp/en/channel/en/UCdC0An4ZPNr_YiFiYoVbwaw/videos/) | 50 | 2026-11-09 | 1,648,703.5 | 18.256 |

**Do not rank channels by this table.** Each channel has a different audience, upload cadence, content mix and snapshot period. A median across the 50 latest uploads is descriptive of *these rows*, not an estimate of the channel's full historical performance or creative quality. The likes/views fraction is **not** average watch time, retention or audience satisfaction.

## Early exploratory contrasts

The CLI groups each channel's videos by **age as of that source's own snapshot** (0–29, 30–89, 90–179, 180–364, or 365+ days), then compares cumulative median views for two duration bands: **under 3 minutes** vs **3 minutes or longer**. It only emits a contrast when **each side contains at least five uploads**. This is a rough guard against tiny cells, **not statistical significance**. The bands refer to runtime, *not* confirmed YouTube Shorts status.

| Within-channel comparison | Under 3 min | At least 3 min | Ratio of median views, short / long |
| --- | ---: | ---: | ---: |
| Alan Becker, 180–364 days old | 7 | 8 | 1.413 |
| Alan Becker, 365+ days old | 17 | 12 | 0.992 |
| Kurzgesagt, 90–179 days old | 12 | 5 | 0.295 |
| Real Engineering, 180–364 days old | 7 | 6 | 0.294 |
| Real Engineering, 365+ days old | 15 | 10 | 0.579 |
| Daily Dose Of Internet, 30–89 days old | 14 | 22 | 0.427 |

**Interpretation:** there is no universal relationship in this sample saying that a shorter video attracts more total views. Alan Becker's two age windows differ; on three other channels, the shorter group has a lower median in the listed windows. That **does not** establish that length causes an outcome: each group also changes topic, format, hook, release timing, audience intent, cross-promotion and likely recommendation exposure. These are hypotheses for better matching, *not* design mandates. League of Legends and GH'S lack a qualifying two-sided contrast and correctly show none, rather than manufacturing a ratio.

## Reproducible commands

```bash
PYTHONPATH=src python -m kumiki_reference_lab audience-benchmarks validate
PYTHONPATH=src python -m kumiki_reference_lab audience-benchmarks report
PYTHONPATH=src python -m kumiki_reference_lab audience-benchmarks report --min-comparison-count 8
```

The report includes the underlying six channel-specific medians, duration buckets, source-age buckets, qualifying comparisons, source URLs/dates and warnings. It works **offline from versioned local JSON** and performs no requests or media decoding. See [`schemas/v1/audience-recent-uploads.schema.json`](../schemas/v1/audience-recent-uploads.schema.json) and [`research/audience-recent-uploads.v1.json`](../research/audience-recent-uploads.v1.json).

## What data would actually improve creative decisions next?

1. **Comparable releases rather than arbitrary winners:** collect matched release-period and format controls from more channels, especially actual motion-design studios and lower-view videos. Document sponsored distribution and whether a video was short-form *by platform*, not just its runtime. If a source cannot establish those fields, leave them unknown.
2. **Longitudinal growth rather than lifetime-average velocity:** capture multiple dated view snapshots for each stable video ID. Never treat `cumulative_views / age_days` as current view velocity; launch spikes, delayed discoveries and view decay break that inference.
3. **Real creative features:** from authorized copies, record shot count, PTS-based cut rhythm, deliberate holds, scene composition, color contrast, onsets/SFX, subject movement, camera behavior and title/hook timing with exact evidence. Metadata cannot identify these properties.
4. **Viewer response/causality limits:** public likes and comments are incomplete proxies. True audience retention, impressions/CTR, watch time, traffic sources and unique viewers often require channel-owner Analytics access. An independent observational sample cannot prove that a cinematic effect caused reach. See [YouTube's Analytics overview](https://support.google.com/youtube/answer/9002587) for the types of owner-side measurements.
5. **Production relevance:** compare a candidate technique against visual clarity, character readability, time-to-understanding and craft in Kumiki's own original renders, not simply against popularity. Use Reference Lab's existing timecoded reference-study and review workflows.

**Rights:** this is publicly reported metadata only; linked third-party films remain **inspiration only**. No videos or frames were downloaded or licensed by this research. More metadata improves where to look, but it does not by itself validate an animation technique.
