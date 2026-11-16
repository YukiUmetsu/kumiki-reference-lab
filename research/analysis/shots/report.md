# shots.net — measured reference report

This deliverable tabulates only what the committed evidence records contain: catalog metadata, sampled source-PTS numeric probes, and single-published-still metrics. It makes no aesthetic, stylistic, intentional, authorship, or quality claim.

## Provenance

- Catalog clips: 40908
- Video-measured records: 457
- Unique media after dedupe: 457 (0 extra record(s) in 0 duplicate group(s))
- Still-measured records: 40678
- Still-only records (no matching video record): 40221
- Skipped video items (index context): 563
- Skipped still items (stills index context): 168
- Failed video acquisitions (index context): 2
- Failed still acquisitions (stills index context): 62
- Video skip reasons (index context): pre-download-duration-exceeds-budget x 16, pre-download-size-exceeds-budget x 116, resume-existing-record x 431
- Still skip reasons (stills index context): no-published-thumbnail x 168
- Unreadable records: 0
- generatedAt: 2026-11-16T16:19:24.275433Z

Skip rows and failure rows are different outcomes. A **skip** is a pre-download decision: `no-allowlisted-public-rendition` means no ladder rung (720p web rendition, ready list stream, or signed original) passed the host/query policy, and a `pre-download-*` reason means catalog metadata alone exceeded a budget. A **failure** means a rendition was selected and the attempted acquisition raised. Neither row is a claim about the clip itself.

Reproduce the inputs and this report with:

```bash
python scripts/research_shots.py catalog --out research/analysis/shots/catalog.json --limit 500
python scripts/research_shots.py stills --catalog research/analysis/shots/catalog.json --out-dir research/analysis/shots --resume
python scripts/research_shots.py collect --catalog research/analysis/shots/catalog.json --out-dir research/analysis/shots --limit 500 --acknowledge-rights
python scripts/research_shots.py report --out-dir research/analysis/shots --catalog research/analysis/shots/catalog.json --top 20
```

Sampling caveat: coverage is `windows measured × window seconds ÷ runtime`; every window is a sample, not a full-film review. Across the tabulated records, 13793.0 s of 27255.7 s of runtime were measured (50.6%). Window values below are samples; where a `full_cuts_per_min` column is populated, that value is film-level and the `full_vs_window` column states the difference (see `## Full-film census`).

## Per-video analysis

457 video-measured record(s), ordered by clip id then slug. All columns are numeric record fields; `bitrate_mbps` is derived from `sizeBytes ÷ durationSeconds` and `download_mb` from `sizeBytes ÷ 1,048,576`.

| clip_id | slug | title | brand | rendition | runtime_s | resolution | fps | bitrate_mbps | download_mb | windows | coverage_pct | candidates_n | sampled_cut_candidates_per_min | full_cuts_per_min | full_vs_window | median_shot_s | shots_lt_0_5s_pct | pace_trend | flicker | ci95 | burst | gap_frames | within_shot_pairs | cut_sep_pairs | delta_basis_pairs | validity | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 40839 | happy-internetting-film-compilation | Happy Internetting - Film Compilation | shots | platform-encoded-source | 158.85 | 1920x1080 | 29.970 | 10.44 | 197.6 | 4 | 25.2 | 5 | 7.50 | — | — | — | — | — | — | 0.70-20.92 | 0.000 | 60.5 | 39 | 5 | 39 | — | 0.5063 | 0.5836 | 0.0688 |
| 40856 | boot | Boot | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.41 | 37.3 | 2 | 66.5 | 5 | 15.00 | — | — | — | — | — | — | 4.87-35.00 | 0.000 | 92.5 | 18 | 4 | 18 | — | 0.2859 | 0.2602 | 0.0260 |
| 40857 | chase-4 | Chase | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.40 | 37.3 | 2 | 66.5 | 11 | 33.00 | — | — | — | — | — | — | 16.47-59.05 | 0.818 | 2.5 | 19 | 3 | 19 | burst-heavy, non-edit-scene-change | 0.2774 | 0.2966 | 0.0353 |
| 40861 | change-is-in-our-power | Change Is In Our Power | shots | platform-encoded-source | 60.09 | 1920x1080 | 29.970 | 10.41 | 74.6 | 4 | 66.6 | 46 | 69.00 | — | — | — | — | — | — | 47.89-95.31 | 0.217 | 24.0 | 11 | 33 | 11 | — | 0.2961 | 0.2918 | 0.1382 |
| 40870 | wood-chipper | Wood Chipper | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.43 | 37.4 | 2 | 66.5 | 10 | 30.00 | — | — | — | — | — | — | 14.39-55.17 | 0.300 | 56.0 | 14 | 8 | 14 | — | 0.3920 | 0.4579 | 0.1119 |
| 40871 | no-freezer | No Freezer | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.45 | 37.5 | 2 | 66.5 | 13 | 39.00 | — | — | — | — | — | — | 20.77-66.69 | 0.154 | 35.5 | 11 | 11 | 11 | — | 0.5041 | 0.3151 | 0.1365 |
| 40872 | holder | Holder | shots | platform-encoded-source | 34.52 | 1920x1080 | 29.970 | 10.40 | 42.8 | 3 | 86.9 | 2 | 4.00 | — | — | — | — | — | — | 0.00-18.78 | 0.000 | 43.0 | 31 | 2 | 31 | — | 0.1088 | 0.6207 | 0.1040 |
| 40874 | worry-free-life | Worry Free Life | shots | platform-encoded-source | 78.42 | 1920x1080 | 29.970 | 10.42 | 97.4 | 4 | 51.0 | 16 | 24.00 | — | — | — | — | — | — | 13.72-38.97 | 0.125 | 71.0 | 29 | 15 | 29 | — | 0.2045 | 0.2845 | 0.0961 |
| 40875 | back-to-school-1 | Back to School | shots | platform-encoded-source | 60.52 | 1920x1080 | 29.970 | 10.45 | 75.4 | 4 | 66.1 | 21 | 31.50 | — | — | — | — | — | — | 8.72-63.11 | 0.619 | 27.0 | 29 | 15 | 29 | burst-heavy | 0.3587 | 0.2930 | 0.1293 |
| 40877 | making-eat-the-wild | Making Eat the Wild | shots | platform-encoded-source | 108.16 | 1920x1080 | 29.970 | 10.43 | 134.5 | 4 | 37.0 | 12 | 18.00 | — | — | — | — | — | — | 9.30-31.44 | 0.167 | 61.0 | 33 | 11 | 33 | — | 0.1656 | 0.3583 | 0.0843 |
| 40878 | eat-the-wild | Eat the Wild | shots | platform-encoded-source | 30.10 | 1920x1080 | 29.970 | 10.54 | 37.8 | 2 | 66.4 | 8 | 24.00 | — | — | — | — | — | — | 10.36-47.29 | 0.000 | 67.0 | 14 | 8 | 14 | — | 0.1737 | 0.5297 | 0.1158 |
| 40880 | last-commercial-before-and-after | Last Commercial before and after | shots | 720p-web-rendition | 24.02 | 1280x720 | 29.970 | 0.79 | 2.3 | 2 | 83.3 | 6 | 18.00 | — | — | — | — | — | — | 6.61-39.18 | 0.000 | 90.0 | 16 | 6 | 16 | — | 0.2444 | 0.1542 | 0.0005 |
| 40881 | who-knows-how-far-our-network-will-go | Who Knows How Far Our Network Will Go? | shots | platform-encoded-source | 83.24 | 1920x1080 | 29.970 | 10.43 | 103.5 | 4 | 48.1 | 9 | 13.50 | — | — | — | — | — | — | 6.17-25.63 | 0.000 | 84.5 | 35 | 9 | 35 | — | 0.2043 | 0.1908 | 0.0892 |
| 40882 | new-trick | new trick | shots | platform-encoded-source | 181.18 | 1920x1080 | 29.970 | 10.44 | 225.6 | 4 | 22.1 | 15 | 22.50 | — | — | — | — | — | — | 5.60-47.43 | 0.400 | 42.0 | 33 | 11 | 33 | low-coverage | 0.3498 | 0.3221 | 0.1292 |
| 40883 | for-all-wheelkind | For All Wheelkind | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.40 | 37.3 | 2 | 66.5 | 17 | 51.00 | — | — | — | — | — | — | 29.71-81.66 | 0.118 | 32.0 | 8 | 14 | 8 | — | 0.2824 | 0.3423 | 0.0783 |
| 40884 | the-running-backs-dog | The Running Back's Dog | shots | platform-encoded-source | 30.12 | 1920x1080 | 29.970 | 10.44 | 37.5 | 2 | 66.4 | 4 | 12.00 | — | — | — | — | — | — | 3.27-30.72 | 0.000 | 140.0 | 18 | 4 | 18 | — | 0.2889 | 0.3904 | 0.1304 |
| 40885 | splenda-stevia-freedom-250 | Splenda Stevia Freedom 250 | shots | platform-encoded-source | 29.99 | 1920x1080 | 29.970 | 10.58 | 37.8 | 2 | 66.7 | 10 | 30.00 | — | — | — | — | — | — | 14.39-55.17 | 0.000 | 64.0 | 12 | 10 | 12 | — | 0.3469 | 0.2286 | 0.0505 |
| 40886 | whats-with-the-big-diesel | What’s with the Big Diesel | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.41 | 37.3 | 2 | 66.5 | 15 | 45.00 | — | — | — | — | — | — | 25.19-74.22 | 0.200 | 41.0 | 8 | 14 | 8 | — | 0.2276 | 0.5310 | 0.0699 |
| 40887 | katzs-deli-with-new-york-nico | Katz's Deli with New York Nico! | shots | platform-encoded-source | 179.24 | 1920x1080 | 29.970 | 10.44 | 223.0 | 4 | 22.3 | 17 | 25.50 | — | — | — | — | — | — | 14.85-40.83 | 0.176 | 61.0 | 29 | 15 | 29 | low-coverage | 0.2140 | 0.3427 | 0.0594 |
| 40888 | was-sich-liebt | Was sich liebt | shots | platform-encoded-source | 79.89 | 1920x1080 | 29.970 | 10.42 | 99.3 | 4 | 50.1 | 15 | 22.50 | — | — | — | — | — | — | 11.16-39.23 | 0.000 | 52.5 | 29 | 15 | 29 | — | 0.1624 | 0.3800 | 0.0540 |
| 40889 | lazer-tag | Lazer Tag | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.45 | 37.4 | 2 | 66.5 | 0 | 0.00 | — | — | — | — | — | — | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.1206 | 0.8223 | 0.0582 |
| 40890 | voice-of-an-angel-1 | Voice of an Angel | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.43 | 37.4 | 2 | 66.5 | 0 | 0.00 | — | — | — | — | — | — | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.2467 | 0.3448 | 0.0805 |
| 40891 | mama-dance | Mama Dance | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.58 | 37.9 | 2 | 66.5 | 0 | 0.00 | — | — | — | — | — | — | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.3698 | 0.2037 | 0.1083 |
| 40892 | go-ocean-fund-the-planets-blue-lung | Go Ocean: Fund the planet's blue lung. | shots | platform-encoded-source | 90.05 | 1920x1080 | 29.970 | 10.48 | 112.5 | 4 | 44.4 | 6 | 9.00 | 12.66 | -29% | 3.05 | 10.0 | accelerating | 0.030 | 0.09-25.56 | 0.000 | 62.0 | 38 | 6 | 38 | — | 0.0629 | 0.5811 | 0.0537 |
| 40893 | freestyle-lo | Freestyle Lo | shots | platform-encoded-source | 45.29 | 1920x1080 | 29.970 | 10.46 | 56.5 | 4 | 88.3 | 74 | 111.00 | — | — | — | — | — | — | 36.29-199.84 | 0.703 | 6.0 | 11 | 33 | 11 | burst-heavy | 0.5300 | 0.1904 | 0.1583 |
| 40896 | one-more-1 | One More | shots | platform-encoded-source | 30.46 | 1920x1080 | 29.970 | 10.43 | 37.9 | 2 | 65.7 | 13 | 39.00 | — | — | — | — | — | — | 20.77-66.69 | 0.308 | 18.5 | 13 | 9 | 13 | — | 0.1529 | 0.2607 | 0.0347 |
| 40897 | etfo-kids-perspective-grade-8 | ETFO Kid's Perspective Grade 8 | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.42 | 37.4 | 2 | 66.5 | 7 | 21.00 | 21.94 | -4% | 2.32 | 0.0 | decelerating | 0.016 | 8.44-43.27 | 0.000 | 99.0 | 15 | 7 | 15 | — | 0.2704 | 0.2448 | 0.1207 |
| 40898 | etfo-kids-perspective-grade-6 | ETFO Kid's Perspective Grade 6 | shots | platform-encoded-source | 30.12 | 1920x1080 | 29.970 | 10.39 | 37.3 | 2 | 66.4 | 4 | 12.00 | 13.94 | -14% | 4.20 | 12.5 | accelerating | 0.024 | 3.27-30.72 | 0.000 | 126.0 | 18 | 4 | 18 | — | 0.2473 | 0.2630 | 0.1179 |
| 40899 | etfo-kids-perspective-grade-4 | ETFO Kid's Perspective Grade 4 | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 9 | 27.00 | 23.94 | +13% | 1.94 | 0.0 | decelerating | 0.025 | 12.35-51.25 | 0.000 | 69.5 | 14 | 8 | 14 | — | 0.2668 | 0.2368 | 0.1584 |
| 40900 | master-of-precision | Master of Precision | shots | platform-encoded-source | 60.65 | 1920x1080 | 29.970 | 10.42 | 75.4 | 4 | 66.0 | 36 | 54.00 | 54.41 | -1% | 0.77 | 46.4 | decelerating | 0.056 | 25.13-91.05 | 0.500 | 27.0 | 18 | 26 | 18 | — | 0.2926 | 0.2307 | 0.1874 |
| 40901 | lets-go | Let's Go | shots | platform-encoded-source | 29.99 | 1920x1080 | 29.970 | 10.61 | 37.9 | 2 | 66.7 | 20 | 60.00 | 64.01 | -6% | 0.80 | 33.3 | decelerating | 0.110 | 36.65-92.67 | 0.200 | 32.0 | 5 | 17 | 5 | sparse-delta-basis | 0.2759 | 0.4047 | 0.1813 |
| 40903 | year-of-the-horse | Year of the Horse  | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.56 | 37.8 | 2 | 66.5 | 12 | 36.00 | 35.93 | +0% | 1.20 | 0.0 | accelerating | 0.062 | 18.60-62.88 | 0.000 | 37.0 | 11 | 11 | 11 | — | 0.3107 | 0.3333 | 0.0506 |
| 40904 | the-most-vicious-cycle | The Most Vicious Cycle | shots | platform-encoded-source | 188.74 | 1920x1080 | 29.970 | 10.44 | 234.9 | 4 | 21.2 | 1 | 1.50 | 21.30 | -93% | 0.07 | 77.9 | decelerating | 0.014 | 0.04-8.36 | — | — | 43 | 1 | 43 | low-coverage | 0.2674 | 0.1375 | 0.0969 |
| 40905 | unanimous | Unanimous | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.31 | 18.5 | 1 | 66.4 | 2 | 12.00 | 11.95 | +0% | 3.75 | 0.0 | — | 0.012 | 1.45-43.35 | 0.000 | 120.0 | 9 | 2 | 9 | short-sample | 0.1538 | 0.5597 | 0.1152 |
| 40906 | telenovela | Telenovela | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.38 | 18.6 | 1 | 66.4 | 4 | 24.00 | 27.89 | -14% | 1.85 | 0.0 | accelerating | 0.003 | 6.54-61.45 | 0.000 | 48.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.3939 | 0.4230 | 0.0340 |
| 40907 | scene-of-the-crime | Scene of the Crime | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.44 | 18.7 | 1 | 66.4 | 2 | 12.00 | 15.93 | -25% | 1.77 | 0.0 | accelerating | 0.013 | 1.45-43.35 | 0.000 | 262.0 | 9 | 2 | 9 | short-sample | 0.1159 | 0.4083 | 0.0874 |
| 40909 | its-always-time-for-inhotim | It's Always Time for Inhotim | shots | platform-encoded-source | 90.13 | 1920x1080 | 29.970 | 10.43 | 112.0 | 4 | 44.4 | 18 | 27.00 | 23.96 | +13% | 1.33 | 13.5 | accelerating | 0.027 | 7.83-54.31 | 0.111 | 33.0 | 30 | 14 | 30 | — | 0.1651 | 0.3285 | 0.0662 |
| 40911 | vision | Vision | shots | platform-encoded-source | 75.50 | 1920x1080 | 29.970 | 10.42 | 93.8 | 4 | 53.0 | 8 | 12.00 | 9.54 | +26% | 1.33 | 0.0 | accelerating | 0.004 | 0.00-39.72 | 0.000 | 22.0 | 37 | 7 | 37 | — | 0.1706 | 0.2019 | 0.0258 |
| 40914 | demon | Demon | shots | platform-encoded-source | 170.33 | 1920x1080 | 29.970 | 10.44 | 211.9 | 4 | 23.5 | 6 | 9.00 | 7.40 | +22% | 5.87 | 4.5 | decelerating | 0.001 | 3.30-19.59 | 0.000 | 181.0 | 38 | 6 | 38 | low-coverage | 0.1562 | 0.1766 | 0.0130 |
| 40915 | freaknik-the-wildest-party-never-told-trailer | Freaknik: The Wildest Party Never Told - Trailer | shots | 720p-web-rendition | 115.97 | 1280x720 | 29.970 | 2.59 | 35.8 | 4 | 34.5 | 41 | 61.50 | 69.33 | -11% | 0.73 | 37.8 | accelerating | 0.077 | 44.13-83.43 | 0.244 | 17.5 | 15 | 29 | 15 | — | 0.2250 | 0.3112 | 0.1223 |
| 40916 | slowly-does-it | Slowly Does It | shots | platform-encoded-source | 30.02 | 1920x1080 | 29.970 | 10.42 | 37.3 | 2 | 66.6 | 8 | 24.00 | 27.99 | -14% | 2.04 | 0.0 | steady | 0.032 | 10.36-47.29 | 0.000 | 57.0 | 14 | 8 | 14 | — | 0.3157 | 0.2168 | 0.0514 |
| 40917 | enel | Enel | shots | platform-encoded-source | 59.97 | 1920x1080 | 29.970 | 10.43 | 74.6 | 4 | 66.7 | 5 | 7.50 | 5.00 | +50% | 3.62 | 16.7 | decelerating | 0.013 | 0.00-29.87 | 0.400 | 24.0 | 40 | 4 | 40 | — | 0.2417 | 0.3939 | 0.1580 |
| 40918 | what-ever-comes | What Ever Comes | shots | platform-encoded-source | 80.77 | 1920x1080 | 29.970 | 10.43 | 100.4 | 4 | 49.5 | 17 | 25.50 | 20.80 | +23% | 2.14 | 17.2 | steady | 0.038 | 14.85-40.83 | 0.000 | 59.5 | 30 | 14 | 30 | — | 0.1354 | 0.1648 | 0.0648 |
| 40919 | give-ai-a-break | Give AI a Break | shots | platform-encoded-source | 78.21 | 1920x1080 | 29.970 | 10.42 | 97.2 | 4 | 51.1 | 9 | 13.50 | 15.34 | -12% | 3.17 | 0.0 | decelerating | 0.005 | 6.17-25.63 | 0.000 | 93.0 | 35 | 9 | 35 | — | 0.1267 | 0.2683 | 0.0372 |
| 40920 | a-strangers-house | A Stranger's House | shots | platform-encoded-source | 120.94 | 1920x1080 | 29.970 | 10.43 | 150.4 | 4 | 33.1 | 29 | 43.50 | 42.17 | +3% | 0.38 | 53.5 | accelerating | 0.013 | 23.36-70.10 | 0.552 | 10.0 | 30 | 14 | 30 | burst-heavy | 0.1313 | 0.2772 | 0.0370 |
| 40921 | motomorphosis | MOTOMORPHOSIS | shots | platform-encoded-source | 120.30 | 1920x1080 | 29.970 | 10.48 | 150.2 | 4 | 33.3 | 0 | 0.00 | 0.00 | — | 120.30 | 0.0 | — | 0.019 | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.3306 | 0.2910 | 0.0582 |
| 40922 | the-7th-punch | The 7th Punch | shots | platform-encoded-source | 146.43 | 1920x1080 | 29.970 | 10.43 | 182.1 | 4 | 27.3 | 23 | 34.50 | 38.52 | -10% | 0.83 | 24.2 | decelerating | 0.039 | 21.87-51.77 | 0.087 | 37.5 | 23 | 21 | 23 | — | 0.2342 | 0.2177 | 0.0906 |
| 40923 | the-right-wave | The Right Wave | shots | 720p-web-rendition | 60.03 | 1280x720 | 25.000 | 2.63 | 18.8 | 4 | 66.6 | 27 | 40.50 | 33.98 | +19% | 1.32 | 17.1 | decelerating | 0.058 | 26.69-58.93 | 0.296 | 30.0 | 22 | 22 | 22 | — | 0.4282 | 0.4872 | 0.1193 |
| 40924 | everyones-playing | Everyone's Playing | shots | platform-encoded-source | 94.10 | 1920x1080 | 29.970 | 10.44 | 117.1 | 4 | 42.5 | 44 | 66.00 | 63.12 | +5% | 0.80 | 27.0 | accelerating | 0.059 | 25.53-116.69 | 0.318 | 20.0 | 14 | 30 | 14 | — | 0.2536 | 0.3465 | 0.1029 |
| 40925 | tdr-x-nike | TDR x Nike | shots | platform-encoded-source | 82.43 | 1920x1080 | 29.970 | 10.42 | 102.4 | 4 | 48.5 | 12 | 18.00 | 19.65 | -8% | 2.05 | 35.7 | accelerating | 0.009 | 4.40-39.02 | 0.250 | 64.0 | 35 | 9 | 35 | — | 0.0949 | 0.3706 | 0.0565 |
| 40930 | google-translate-live-translate | Google Translate Live Translate | shots | platform-encoded-source | 85.06 | 1920x1080 | 29.970 | 10.44 | 105.9 | 4 | 47.0 | 15 | 22.50 | 14.81 | +52% | 2.39 | 0.0 | decelerating | 0.007 | 12.59-37.11 | 0.000 | 75.0 | 29 | 15 | 29 | — | 0.2126 | 0.2497 | 0.0418 |
| 40932 | your-brands-best-friend | Your Brands Best Friend | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.44 | 37.4 | 2 | 66.5 | 18 | 54.00 | 47.87 | +13% | 1.17 | 4.0 | steady | 0.047 | 32.00-85.34 | 0.111 | 36.0 | 6 | 16 | 6 | sparse-delta-basis | 0.3275 | 0.4606 | 0.0949 |
| 40933 | craving-real | Craving Real? | shots | platform-encoded-source | 29.97 | 1920x1080 | 29.970 | 10.44 | 37.3 | 2 | 66.7 | 11 | 33.00 | 30.03 | +10% | 1.75 | 0.0 | decelerating | 0.011 | 16.47-59.05 | 0.000 | 54.0 | 11 | 11 | 11 | — | 0.4958 | 0.2388 | 0.0447 |
| 40935 | supreme-leader | Supreme Leader | shots | platform-encoded-source | 90.05 | 1920x1080 | 29.970 | 10.45 | 112.2 | 4 | 44.4 | 18 | 27.00 | 25.99 | +4% | 1.62 | 0.0 | accelerating | 0.010 | 16.00-42.67 | 0.000 | 47.0 | 26 | 18 | 26 | — | 0.2770 | 0.3842 | 0.0551 |
| 40936 | scam-jam | Scam Jam | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.52 | 37.7 | 2 | 66.5 | 11 | 33.00 | 33.93 | -3% | 1.53 | 5.6 | decelerating | 0.012 | 16.47-59.05 | 0.000 | 48.0 | 12 | 10 | 12 | — | 0.2775 | 0.3439 | 0.0130 |
| 40937 | double-brian | Double Brian | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.44 | 37.4 | 2 | 66.5 | 10 | 30.00 | 27.95 | +7% | 1.94 | 6.7 | decelerating | 0.006 | 14.39-55.17 | 0.000 | 58.0 | 12 | 10 | 12 | — | 0.3095 | 0.4324 | 0.0390 |
| 40939 | bees-r-good | BEES R GOOD | shots | platform-encoded-source | 58.50 | 1920x1080 | 29.970 | 10.52 | 73.3 | 4 | 68.4 | 50 | 75.00 | 62.57 | +20% | 0.50 | 48.4 | steady | 0.045 | 32.52-127.46 | 0.460 | 11.0 | 19 | 25 | 19 | — | 0.2515 | 0.2744 | 0.0696 |
| 40940 | secondhand-skins | Secondhand Skins | shots | platform-encoded-source | 40.09 | 1920x1080 | 29.970 | 10.40 | 49.7 | 3 | 74.8 | 17 | 34.00 | 28.44 | +20% | 1.48 | 30.0 | decelerating | 0.012 | 19.81-54.44 | 0.529 | 26.0 | 23 | 10 | 23 | burst-heavy | 0.2193 | 0.5635 | 0.0616 |
| 40941 | meet-the-tread-vision-60 | Meet the Tread Vision (:60) | shots | platform-encoded-source | 60.07 | 1920x1080 | 29.970 | 10.41 | 74.6 | 4 | 66.6 | 34 | 51.00 | 42.95 | +19% | 0.98 | 15.9 | steady | 0.040 | 35.32-71.27 | 0.176 | 26.0 | 18 | 26 | 18 | — | 0.3450 | 0.2598 | 0.1366 |
| 40942 | agreements-make-history | Agreements Make History | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.43 | 74.8 | 4 | 66.5 | 61 | 91.50 | 80.84 | +13% | 0.50 | 47.6 | decelerating | 0.055 | 60.55-128.97 | 0.557 | 10.0 | 15 | 29 | 15 | burst-heavy | 0.1998 | 0.2527 | 0.0644 |
| 40943 | bocata | Bocata | shots | platform-encoded-source | 20.05 | 1920x1080 | 29.970 | 10.39 | 24.8 | 1 | 49.9 | 6 | 36.00 | 29.92 | +20% | 1.87 | 9.1 | decelerating | 0.016 | 13.21-78.36 | 0.000 | 56.0 | 5 | 6 | 5 | short-sample, sparse-delta-basis | 0.2676 | 0.3095 | 0.1598 |
| 40944 | fideua | Fideua | shots | platform-encoded-source | 20.05 | 1920x1080 | 29.970 | 10.41 | 24.9 | 1 | 49.9 | 4 | 24.00 | 23.94 | +0% | 2.04 | 0.0 | steady | 0.025 | 6.54-61.45 | 0.000 | 42.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.2323 | 0.2695 | 0.1027 |
| 40945 | pringa | Pringa | shots | platform-encoded-source | 20.05 | 1920x1080 | 29.970 | 10.40 | 24.9 | 1 | 49.9 | 3 | 18.00 | 23.94 | -25% | 2.24 | 0.0 | accelerating | 0.048 | 3.71-52.60 | 0.000 | 97.0 | 8 | 3 | 8 | short-sample | 0.2118 | 0.4537 | 0.0866 |
| 40946 | pintxos | Pintxos | shots | platform-encoded-source | 20.05 | 1920x1080 | 29.970 | 10.42 | 24.9 | 1 | 49.9 | 3 | 18.00 | 11.97 | +50% | 2.04 | 0.0 | decelerating | 0.020 | 3.71-52.60 | 0.000 | 44.5 | 8 | 3 | 8 | short-sample | 0.2064 | 0.4004 | 0.1242 |
| 40947 | stories-from-the-hive-danielle | Stories from the Hive Danielle | shots | platform-encoded-source | 60.03 | 1920x1080 | 29.970 | 10.44 | 74.7 | 4 | 66.6 | 38 | 57.00 | 46.97 | +21% | 0.17 | 81.2 | decelerating | 0.040 | 0.00-148.84 | 0.921 | 5.0 | 34 | 10 | 34 | burst-heavy | 0.7383 | 0.1436 | 0.1525 |
| 40949 | stories-from-the-hive-sarah | Stories from the Hive Sarah | shots | platform-encoded-source | 60.03 | 1920x1080 | 29.970 | 10.43 | 74.7 | 4 | 66.6 | 26 | 39.00 | 33.98 | +15% | 0.17 | 62.9 | accelerating | 0.039 | 12.13-75.05 | 0.731 | 5.0 | 32 | 12 | 32 | burst-heavy | 0.7661 | 0.1945 | 0.1661 |
| 40950 | volvo-xc60 | Volvo XC60 | shots | platform-encoded-source | 96.81 | 1920x1080 | 29.970 | 10.44 | 120.5 | 4 | 41.3 | 26 | 39.00 | 34.09 | +14% | 1.30 | 5.4 | decelerating | 0.064 | 25.48-57.14 | 0.000 | 38.0 | 18 | 26 | 18 | — | 0.2119 | 0.3007 | 0.0491 |
| 40951 | more-tender-than-ever-tender-boyz-social | More Tender Than Ever / Tender Boyz Social | shots | platform-encoded-source | 11.07 | 1920x1080 | 29.970 | 10.25 | 13.5 | 1 | 81.3 | 0 | 0.00 | 0.00 | — | 11.07 | 0.0 | — | 0.004 | 0.00-24.59 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.0334 | 0.0849 | 0.0129 |
| 40952 | tender-boyz | Tender Boyz | shots | platform-encoded-source | 30.02 | 1920x1080 | 29.970 | 10.38 | 37.1 | 2 | 66.6 | 3 | 9.00 | 8.00 | +13% | 4.07 | 0.0 | decelerating | 0.032 | 1.86-26.30 | 0.000 | 312.5 | 19 | 3 | 19 | — | 0.4143 | 0.4177 | 0.0912 |
| 40953 | crave | Crave | shots | platform-encoded-source | 15.02 | 1920x1080 | 29.970 | 10.33 | 18.5 | 1 | 66.6 | 0 | 0.00 | 0.00 | — | 15.02 | 0.0 | — | 0.051 | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.4354 | 0.5813 | 0.1534 |
| 40954 | the-art-of-free-time | The Art of Free Time | shots | platform-encoded-source | 66.18 | 1920x1080 | 29.970 | 10.44 | 82.4 | 4 | 60.4 | 24 | 36.00 | 35.36 | +2% | 1.55 | 7.5 | decelerating | 0.035 | 23.07-53.57 | 0.000 | 47.0 | 21 | 23 | 21 | — | 0.5366 | 0.4417 | 0.1197 |
| 40955 | garden-1 | Garden | shots | platform-encoded-source | 63.81 | 1920x1080 | 29.970 | 10.42 | 79.2 | 4 | 62.7 | 32 | 48.00 | 40.43 | +19% | 1.08 | 9.1 | accelerating | 0.025 | 29.95-71.52 | 0.219 | 33.0 | 16 | 28 | 16 | — | 0.2195 | 0.3391 | 0.0704 |
| 40956 | office-6 | Office | shots | platform-encoded-source | 67.52 | 1920x1080 | 29.970 | 10.42 | 83.9 | 4 | 59.2 | 29 | 43.50 | 39.99 | +9% | 1.35 | 0.0 | decelerating | 0.041 | 29.13-62.47 | 0.000 | 38.0 | 16 | 28 | 16 | — | 0.3987 | 0.2556 | 0.0858 |
| 40957 | listen-to-jordic | Listen to Jordic | shots | platform-encoded-source | 129.69 | 1920x1080 | 29.970 | 10.43 | 161.3 | 4 | 30.8 | 2 | 3.00 | 4.63 | -35% | 10.64 | 0.0 | accelerating | 0.009 | 0.36-10.84 | 0.000 | 2275.0 | 42 | 2 | 42 | — | 0.1966 | 0.4124 | 0.0650 |
| 40958 | mud-dance | Mud Dance | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.42 | 74.6 | 4 | 66.6 | 19 | 28.50 | 28.97 | -2% | 1.72 | 10.0 | accelerating | 0.027 | 17.16-44.51 | 0.000 | 53.5 | 25 | 19 | 25 | — | 0.2457 | 0.3037 | 0.0518 |
| 40959 | bubblegum | Bubblegum | shots | platform-encoded-source | 10.01 | 1920x1080 | 29.970 | 10.26 | 12.2 | 1 | 90.0 | 1 | 6.67 | 6.00 | +11% | 5.00 | 0.0 | — | 0.009 | 0.17-37.14 | — | — | 10 | 1 | 10 | short-sample | 0.6048 | 0.4315 | 0.0740 |
| 40960 | bouquet | Bouquet | shots | platform-encoded-source | 10.01 | 1920x1080 | 29.970 | 10.26 | 12.2 | 1 | 90.0 | 0 | 0.00 | 0.00 | — | 10.01 | 0.0 | — | 0.003 | 0.00-24.59 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.7431 | 0.2883 | 0.1031 |
| 40961 | no-sleep | No Sleep | shots | platform-encoded-source | 10.01 | 1920x1080 | 29.970 | 10.26 | 12.2 | 1 | 90.0 | 2 | 13.33 | 11.99 | +11% | 3.40 | 0.0 | — | 0.025 | 1.61-48.16 | 0.000 | 102.0 | 9 | 2 | 9 | short-sample | 0.3012 | 0.4390 | 0.0680 |
| 40962 | library-1 | Library | shots | platform-encoded-source | 10.01 | 1920x1080 | 29.970 | 10.26 | 12.2 | 1 | 90.0 | 2 | 13.33 | 11.99 | +11% | 3.77 | 0.0 | — | 0.009 | 1.61-48.16 | 0.000 | 113.0 | 9 | 2 | 9 | short-sample | 0.3439 | 0.6166 | 0.0406 |
| 40963 | pass-the-parcel | Pass The Parcel | shots | platform-encoded-source | 10.01 | 1920x1080 | 29.970 | 10.26 | 12.2 | 1 | 90.0 | 1 | 6.67 | 6.00 | +11% | 5.00 | 0.0 | — | 0.028 | 0.17-37.14 | — | — | 10 | 1 | 10 | short-sample | 0.4115 | 0.5956 | 0.1258 |
| 40964 | card-tower | Card Tower | shots | platform-encoded-source | 10.01 | 1920x1080 | 29.970 | 10.26 | 12.2 | 1 | 90.0 | 2 | 13.33 | 11.99 | +11% | 2.50 | 0.0 | — | 0.002 | 1.61-48.16 | 0.000 | 59.0 | 9 | 2 | 9 | short-sample | 0.3733 | 0.6178 | 0.0299 |
| 40965 | human-nature | Human Nature | shots | platform-encoded-source | 59.97 | 1920x1080 | 29.970 | 10.42 | 74.5 | 4 | 66.7 | 32 | 48.00 | 43.02 | +12% | 1.10 | 6.8 | steady | 0.040 | 32.83-67.76 | 0.000 | 32.0 | 15 | 29 | 15 | — | 0.2495 | 0.3101 | 0.0683 |
| 40967 | relentless | Relentless | shots | platform-encoded-source | 86.85 | 1920x1080 | 29.970 | 10.42 | 107.9 | 4 | 46.1 | 17 | 25.50 | 36.62 | -30% | 0.10 | 74.1 | — | 0.021 | 0.00-65.94 | 0.706 | 5.5 | 35 | 9 | 35 | burst-heavy | 0.5563 | 0.0471 | 0.1140 |
| 40968 | ask-yourself | Ask Yourself | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 18 | 54.00 | 45.88 | +18% | 1.28 | 25.0 | decelerating | 0.099 | 32.00-85.34 | 0.389 | 37.0 | 8 | 14 | 8 | — | 0.3221 | 0.3016 | 0.1203 |
| 40969 | the-next-date | The Next Date | shots | platform-encoded-source | 30.02 | 1920x1080 | 29.970 | 10.38 | 37.1 | 2 | 66.6 | 4 | 12.00 | 13.99 | -14% | 3.17 | 0.0 | decelerating | 0.022 | 3.27-30.72 | 0.000 | 51.0 | 18 | 4 | 18 | — | 0.1214 | 0.3881 | 0.0554 |
| 40970 | the-reunion | The Reunion | shots | platform-encoded-source | 60.01 | 1920x1080 | 29.970 | 10.42 | 74.5 | 4 | 66.7 | 11 | 16.50 | 19.00 | -13% | 2.12 | 0.0 | decelerating | 0.005 | 8.24-29.52 | 0.000 | 124.0 | 33 | 11 | 33 | — | 0.1773 | 0.3330 | 0.0563 |
| 40971 | choose-the-good-dc | Choose the Good (DC) | shots | platform-encoded-source | 164.46 | 1920x1080 | 29.970 | 10.44 | 204.6 | 4 | 24.3 | 21 | 31.50 | 37.58 | -16% | 0.80 | 37.5 | decelerating | 0.026 | 0.00-81.28 | 0.429 | 17.0 | 30 | 14 | 30 | low-coverage | 0.2863 | 0.4139 | 0.0892 |
| 40972 | dont-crack-trailer | Don't Crack Trailer | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.39 | 37.2 | 2 | 66.5 | 16 | 48.00 | 37.93 | +27% | 0.48 | 50.0 | — | 0.014 | 27.44-77.95 | 0.375 | 12.0 | 14 | 8 | 14 | — | 0.1028 | 0.4967 | 0.0886 |
| 40974 | hero-film-4 | Hero Film | shots | platform-encoded-source | 29.99 | 1920x1080 | 29.970 | 10.38 | 37.1 | 2 | 66.7 | 27 | 81.00 | 82.01 | -1% | 0.47 | 50.0 | decelerating | 0.026 | 53.38-117.85 | 0.667 | 10.5 | 8 | 14 | 8 | burst-heavy | 0.5456 | 0.2444 | 0.1291 |
| 40975 | go-beyond-the-grey | Go Beyond the Grey | shots | platform-encoded-source | 30.02 | 1920x1080 | 29.970 | 10.38 | 37.1 | 2 | 66.6 | 24 | 72.00 | 67.96 | +6% | 0.77 | 22.9 | accelerating | 0.058 | 46.13-107.13 | 0.208 | 24.0 | 4 | 18 | 4 | sparse-delta-basis | 0.3702 | 0.1736 | 0.1864 |
| 40976 | the-womens-health-mens-choir | The Women's Health Men's Choir | shots | platform-encoded-source | 71.04 | 1920x1080 | 29.970 | 10.51 | 89.0 | 4 | 56.3 | 18 | 27.00 | 24.49 | +10% | 1.53 | 3.3 | decelerating | 0.010 | 14.66-44.59 | 0.000 | 58.0 | 26 | 18 | 26 | — | 0.3362 | 0.3357 | 0.0427 |
| 40977 | built-for-real-life | Built For Real Life | shots | platform-encoded-source | 59.97 | 1920x1080 | 29.970 | 10.49 | 75.0 | 4 | 66.7 | 29 | 43.50 | 40.02 | +9% | 1.13 | 14.6 | decelerating | 0.060 | 29.13-62.47 | 0.000 | 34.0 | 19 | 25 | 19 | — | 0.2208 | 0.3057 | 0.1052 |
| 40978 | unbox-your-potential | Unbox Your Potential | shots | platform-encoded-source | 25.41 | 1920x1080 | 29.970 | 10.38 | 31.4 | 2 | 78.7 | 9 | 27.00 | 30.70 | -12% | 1.33 | 7.1 | steady | 0.066 | 12.35-51.25 | 0.000 | 40.0 | 13 | 9 | 13 | — | 0.3770 | 0.3193 | 0.1620 |
| 40983 | were-going-to-ikea | We’re going to IKEA | shots | platform-encoded-source | 58.90 | 1920x1080 | 29.970 | 10.41 | 73.1 | 4 | 67.9 | 22 | 33.00 | 32.60 | +1% | 1.40 | 6.1 | steady | 0.014 | 17.84-53.88 | 0.000 | 42.0 | 23 | 21 | 23 | — | 0.2431 | 0.4098 | 0.0684 |
| 40984 | taking-on-akuma | Taking on Akuma | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.42 | 37.4 | 2 | 66.5 | 11 | 33.00 | 47.87 | -31% | 0.83 | 48.0 | steady | 0.034 | 16.47-59.05 | 0.455 | 63.0 | 15 | 7 | 15 | — | 0.3751 | 0.3439 | 0.1057 |
| 40985 | the-ay-ay-ay-ay | The Ay Ay Ay Ay | shots | platform-encoded-source | 62.44 | 1920x1080 | 29.970 | 10.42 | 77.6 | 4 | 64.1 | 13 | 19.50 | 22.10 | -12% | 1.95 | 4.2 | accelerating | 0.027 | 9.07-35.33 | 0.000 | 65.5 | 32 | 12 | 32 | — | 0.2901 | 0.3183 | 0.0888 |
| 40986 | to-the-summit-directors-cut-2-09 | To The Summit (Director's Cut) (2:09) | shots | platform-encoded-source | 129.49 | 1920x1080 | 29.970 | 10.44 | 161.2 | 4 | 30.9 | 7 | 10.50 | 12.97 | -19% | 3.37 | 6.9 | accelerating | 0.006 | 4.22-21.63 | 0.000 | 556.0 | 37 | 7 | 37 | — | 0.2068 | 0.2289 | 0.0332 |
| 40987 | to-the-summit-directors-cut-2-52 | To The Summit (Director's Cut) (2:52) | shots | platform-encoded-source | 172.37 | 1920x1080 | 29.970 | 10.44 | 214.6 | 4 | 23.2 | 8 | 12.00 | 10.79 | +11% | 3.95 | 3.1 | decelerating | 0.003 | 5.18-23.64 | 0.000 | 223.0 | 36 | 8 | 36 | low-coverage | 0.2674 | 0.1718 | 0.0378 |
| 40988 | park-1 | Park | shots | platform-encoded-source | 50.41 | 1920x1080 | 29.970 | 10.41 | 62.6 | 4 | 79.3 | 5 | 7.50 | 8.33 | -10% | 5.79 | 12.5 | accelerating | 0.002 | 2.44-17.50 | 0.000 | 223.0 | 39 | 5 | 39 | — | 0.1772 | 0.2472 | 0.0259 |
| 40989 | bus-stop | Bus Stop | shots | platform-encoded-source | 40.98 | 1920x1080 | 29.970 | 10.40 | 50.8 | 3 | 73.2 | 0 | 0.00 | 0.00 | — | 40.98 | 0.0 | — | 0.000 | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.0941 | 0.4024 | 0.0165 |
| 40990 | the-deals-youve-been-waiting-for | The deals you’ve been waiting for | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.44 | 74.7 | 4 | 66.6 | 13 | 19.50 | 21.98 | -11% | 1.87 | 0.0 | steady | 0.005 | 10.38-33.35 | 0.000 | 77.0 | 31 | 13 | 31 | — | 0.4080 | 0.3225 | 0.0328 |
| 40991 | arrivals-1 | Arrivals | shots | platform-encoded-source | 59.97 | 1920x1080 | 29.970 | 10.46 | 74.8 | 4 | 66.7 | 12 | 18.00 | 18.01 | +0% | 2.57 | 0.0 | decelerating | 0.011 | 9.30-31.44 | 0.000 | 89.0 | 32 | 12 | 32 | — | 0.2503 | 0.4221 | 0.0577 |
| 40992 | pamper-your-cheeks | Pamper Your Cheeks | shots | platform-encoded-source | 43.22 | 1920x1080 | 29.970 | 10.43 | 53.8 | 3 | 69.4 | 15 | 30.00 | 29.15 | +3% | 1.80 | 4.5 | decelerating | 0.030 | 16.79-49.48 | 0.133 | 54.0 | 19 | 14 | 19 | — | 0.5475 | 0.3651 | 0.0711 |
| 40993 | take-your-shot | Take Your Shot | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.52 | 75.3 | 4 | 66.6 | 13 | 19.50 | 19.98 | -2% | 1.74 | 38.1 | accelerating | 0.022 | 8.29-36.53 | 0.538 | 36.0 | 36 | 8 | 36 | burst-heavy | 0.1257 | 0.3526 | 0.0984 |
| 40994 | whats-for-hockey | What's for Hockey? | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.41 | 74.6 | 4 | 66.5 | 13 | 19.50 | 20.96 | -7% | 1.69 | 18.2 | accelerating | 0.026 | 9.93-34.04 | 0.000 | 80.5 | 31 | 13 | 31 | — | 0.1754 | 0.3261 | 0.0839 |
| 40995 | zendaya-in-your-new-favorite-action-movie | Zendaya in your new favorite action movie | shots | platform-encoded-source | 120.66 | 1920x1080 | 29.970 | 10.45 | 150.3 | 4 | 33.2 | 18 | 27.00 | 22.38 | +21% | 2.07 | 0.0 | decelerating | 0.022 | 14.66-44.59 | 0.000 | 47.0 | 27 | 17 | 27 | — | 0.2488 | 0.2209 | 0.0893 |
| 40996 | special-olympics-30 | Special Olympics (:30) | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.40 | 37.3 | 2 | 66.5 | 12 | 36.00 | 33.91 | +6% | 1.40 | 0.0 | accelerating | 0.022 | 18.60-62.88 | 0.000 | 30.0 | 11 | 11 | 11 | — | 0.2004 | 0.3790 | 0.0765 |
| 40999 | the-handmade-series-ep-1-choosing-music-going-nowhere | The Handmade Series Ep 1: Choosing Music, Going Nowhere | shots | platform-encoded-source | 29.78 | 1920x1080 | 29.970 | 10.38 | 36.8 | 2 | 67.2 | 0 | 0.00 | 2.01 | -100% | 14.89 | 0.0 | — | 0.014 | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.3719 | 0.4265 | 0.1109 |
| 41000 | the-handmade-series-ep-2-what-does-premium-sound-like | The Handmade Series Ep 2: What Does Premium Sound Like? | shots | platform-encoded-source | 30.21 | 1920x1080 | 29.970 | 10.38 | 37.4 | 2 | 66.2 | 0 | 0.00 | 1.99 | -100% | 15.10 | 0.0 | — | 0.009 | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.4363 | 0.2960 | 0.0726 |
| 41001 | the-handmade-series-ep-3-whose-taste-wins | The Handmade Series Ep 3: Whose Taste Wins? | shots | platform-encoded-source | 34.22 | 1920x1080 | 29.970 | 10.39 | 42.4 | 3 | 87.7 | 0 | 0.00 | 1.75 | -100% | 17.11 | 0.0 | — | 0.017 | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.4164 | 0.3561 | 0.1279 |
| 41002 | the-handmade-series-ep-4-the-audience-has-entered | The Handmade Series Ep 4: The Audience Has Entered | shots | platform-encoded-source | 32.36 | 1920x1080 | 29.970 | 10.39 | 40.1 | 2 | 61.8 | 0 | 0.00 | 1.85 | -100% | 16.18 | 0.0 | — | 0.005 | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.4213 | 0.3839 | 0.0789 |
| 41003 | tiramisu | Tiramisu | shots | platform-encoded-source | 110.06 | 1920x1080 | 29.970 | 10.43 | 136.8 | 4 | 36.3 | 23 | 34.50 | 29.98 | +15% | 0.78 | 30.4 | accelerating | 0.010 | 1.36-79.80 | 0.000 | 21.0 | 28 | 16 | 28 | — | 0.1709 | 0.0000 | 0.0470 |
| 41004 | 4th-down | 4th Down | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.38 | 18.6 | 1 | 66.4 | 8 | 48.00 | 71.71 | -33% | 0.63 | 47.4 | accelerating | 0.101 | 20.72-94.58 | 0.500 | 33.0 | 5 | 6 | 5 | short-sample, sparse-delta-basis | 0.5395 | 0.2675 | 0.0522 |
| 41005 | gloves | Gloves | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.31 | 18.5 | 1 | 66.4 | 7 | 42.00 | 39.84 | +5% | 1.27 | 9.1 | steady | 0.051 | 16.89-86.54 | 0.286 | 34.5 | 6 | 5 | 6 | short-sample, sparse-delta-basis | 0.5987 | 0.1604 | 0.0941 |
| 41006 | never-know-enough | Never Know Enough | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 15 | 45.00 | 39.89 | +13% | 1.23 | 28.6 | accelerating | 0.040 | 25.19-74.22 | 0.267 | 37.5 | 10 | 12 | 10 | — | 0.5662 | 0.2112 | 0.1484 |
| 41007 | anthem-dc | Anthem (DC) | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.51 | 75.4 | 4 | 66.5 | 21 | 31.50 | 29.94 | +5% | 1.53 | 3.2 | decelerating | 0.015 | 19.50-48.15 | 0.000 | 49.0 | 23 | 21 | 23 | — | 0.2099 | 0.4149 | 0.0465 |
| 41008 | the-right-words | The Right Words | shots | platform-encoded-source | 60.01 | 1920x1080 | 29.970 | 10.42 | 74.5 | 4 | 66.7 | 1 | 1.50 | 2.00 | -25% | 7.46 | 0.0 | steady | 0.006 | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.2934 | 0.4053 | 0.0918 |
| 41009 | the-class | The Class | shots | platform-encoded-source | 70.06 | 1920x1080 | 29.970 | 10.42 | 87.0 | 4 | 57.1 | 4 | 6.00 | 7.71 | -22% | 4.30 | 0.0 | decelerating | 0.008 | 0.00-19.24 | 0.000 | 54.0 | 40 | 4 | 40 | — | 0.3273 | 0.2971 | 0.1154 |
| 41011 | no-place-like-home | No Place Like Home | shots | platform-encoded-source | 83.22 | 1920x1080 | 29.970 | 10.42 | 103.4 | 4 | 48.1 | 20 | 30.00 | 30.28 | -1% | 1.30 | 14.0 | decelerating | 0.034 | 15.23-50.66 | 0.150 | 39.0 | 27 | 17 | 27 | — | 0.1882 | 0.4364 | 0.1116 |
| 41012 | the-last-1 | The Last 1% | shots | platform-encoded-source | 61.53 | 1920x1080 | 29.970 | 10.42 | 76.4 | 4 | 65.0 | 43 | 64.50 | 69.24 | -7% | 0.17 | 68.1 | accelerating | 0.038 | 2.47-142.41 | 0.698 | 5.5 | 27 | 17 | 27 | burst-heavy | 0.1617 | 0.4666 | 0.1123 |
| 41013 | the-race-between-knowledge-and-chaos | The Race Between Knowledge and Chaos | shots | platform-encoded-source | 60.14 | 1920x1080 | 29.970 | 10.53 | 75.5 | 4 | 66.5 | 26 | 39.00 | 36.91 | +6% | 0.38 | 52.6 | decelerating | 0.032 | 11.10-76.43 | 0.654 | 9.0 | 32 | 12 | 32 | burst-heavy | 0.1409 | 0.3128 | 0.0925 |
| 41014 | friendly-intervention | Friendly Intervention | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.41 | 37.3 | 2 | 66.5 | 8 | 24.00 | 21.94 | +9% | 2.36 | 0.0 | accelerating | 0.010 | 10.36-47.29 | 0.000 | 61.0 | 14 | 8 | 14 | — | 0.3108 | 0.2235 | 0.0528 |
| 41015 | bear-6 | Bear | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.40 | 37.3 | 2 | 66.5 | 8 | 24.00 | 21.94 | +9% | 2.67 | 0.0 | steady | 0.012 | 10.36-47.29 | 0.000 | 57.0 | 14 | 8 | 14 | — | 0.2923 | 0.2528 | 0.0633 |
| 41016 | sports-fan | Sports Fan | shots | platform-encoded-source | 29.95 | 1920x1080 | 29.970 | 10.39 | 37.1 | 2 | 66.8 | 11 | 33.00 | 32.05 | +3% | 1.50 | 0.0 | decelerating | 0.014 | 16.47-59.05 | 0.000 | 49.0 | 11 | 11 | 11 | — | 0.3355 | 0.2483 | 0.0936 |
| 41017 | joy-of-driving | Joy of Driving | shots | platform-encoded-source | 90.30 | 1920x1080 | 29.970 | 10.44 | 112.4 | 4 | 44.3 | 36 | 54.00 | 47.17 | +14% | 1.03 | 12.5 | decelerating | 0.051 | 37.82-74.76 | 0.083 | 34.0 | 11 | 33 | 11 | — | 0.2018 | 0.4098 | 0.0980 |
| 41018 | the-real-gusto-italo-americano | The Real Gusto Italo-Americano | shots | platform-encoded-source | 85.10 | 1920x1080 | 29.970 | 10.42 | 105.8 | 4 | 47.0 | 13 | 19.50 | 23.27 | -16% | 1.72 | 2.9 | accelerating | 0.019 | 8.29-36.53 | 0.000 | 49.5 | 31 | 13 | 31 | — | 0.2696 | 0.2968 | 0.0924 |
| 41019 | get-a-nose-job-in-saaristo | Get a Nose Job in Saaristo | shots | platform-encoded-source | 134.02 | 1920x1080 | 29.970 | 10.48 | 167.4 | 4 | 29.8 | 7 | 10.50 | 12.98 | -19% | 2.97 | 0.0 | accelerating | 0.004 | 4.22-21.63 | 0.000 | 108.0 | 37 | 7 | 37 | — | 0.2415 | 0.2299 | 0.0353 |
| 41020 | life-stripped-away | Life Stripped Away | shots | 720p-web-rendition | 94.98 | 1280x720 | 29.970 | 2.52 | 28.5 | 4 | 42.1 | 12 | 18.00 | 18.95 | -5% | 2.37 | 6.5 | steady | 0.024 | 7.15-34.77 | 0.167 | 46.0 | 34 | 10 | 34 | — | 0.1936 | 0.3150 | 0.0845 |
| 41022 | opus-jazz-miami-city-ballet-gapstudio | Opus Jazz: Miami City Ballet & GapStudio | shots | platform-encoded-source | 125.93 | 1920x1080 | 29.970 | 10.43 | 156.6 | 4 | 31.8 | 27 | 40.50 | 34.30 | +18% | 0.77 | 35.6 | decelerating | 0.046 | 1.83-92.09 | 0.556 | 10.0 | 30 | 14 | 30 | burst-heavy | 0.5059 | 0.2144 | 0.1547 |
| 41023 | combo-1 | Combo | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.45 | 37.5 | 2 | 66.5 | 15 | 45.00 | 43.88 | +3% | 1.07 | 17.4 | accelerating | 0.062 | 25.19-74.22 | 0.267 | 35.0 | 9 | 13 | 9 | — | 0.4451 | 0.3104 | 0.2126 |
| 41024 | auto-1 | Auto | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.41 | 37.3 | 2 | 66.5 | 20 | 60.00 | 47.87 | +25% | 1.13 | 12.0 | decelerating | 0.058 | 36.65-92.67 | 0.150 | 26.0 | 7 | 15 | 7 | sparse-delta-basis | 0.3897 | 0.3476 | 0.1862 |
| 41025 | home-3 | Home | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.40 | 37.3 | 2 | 66.5 | 13 | 39.00 | 39.89 | -2% | 1.13 | 9.5 | steady | 0.057 | 20.77-66.69 | 0.154 | 40.0 | 10 | 12 | 10 | — | 0.4013 | 0.3397 | 0.1855 |
| 41027 | your-healths-best-friend | Your Health’s Best Friend | shots | platform-encoded-source | 60.01 | 1920x1080 | 29.970 | 10.45 | 74.7 | 4 | 66.7 | 22 | 33.00 | 31.99 | +3% | 1.37 | 0.0 | decelerating | 0.024 | 20.68-49.96 | 0.000 | 41.0 | 22 | 22 | 22 | — | 0.2642 | 0.1521 | 0.0895 |
| 41028 | swifty-for-mayor | Swifty for Mayor | shots | platform-encoded-source | 145.98 | 1920x1080 | 29.970 | 10.44 | 181.6 | 4 | 27.4 | 25 | 37.50 | 41.51 | -10% | 0.90 | 27.5 | accelerating | 0.022 | 12.53-71.19 | 0.000 | 27.5 | 22 | 22 | 22 | — | 0.4169 | 0.1419 | 0.0763 |
| 41029 | owl | Owl | shots | platform-encoded-source | 29.99 | 1920x1080 | 29.970 | 10.39 | 37.1 | 2 | 66.7 | 8 | 24.00 | 22.00 | +9% | 2.44 | 0.0 | accelerating | 0.008 | 10.36-47.29 | 0.000 | 38.0 | 14 | 8 | 14 | — | 0.3783 | 0.3889 | 0.1091 |
| 41030 | bear-7 | Bear | shots | platform-encoded-source | 29.99 | 1920x1080 | 29.970 | 10.51 | 37.6 | 2 | 66.7 | 8 | 24.00 | 20.00 | +20% | 2.17 | 9.1 | decelerating | 0.025 | 10.36-47.29 | 0.250 | 65.0 | 15 | 7 | 15 | — | 0.2272 | 0.4286 | 0.0835 |
| 41031 | the-aftermath | The Aftermath | shots | platform-encoded-source | 20.05 | 1920x1080 | 29.970 | 10.35 | 24.7 | 1 | 49.9 | 9 | 54.00 | 35.90 | +50% | 0.77 | 38.5 | decelerating | 0.037 | 24.69-102.51 | 0.778 | 12.5 | 6 | 5 | 6 | burst-heavy, short-sample, sparse-delta-basis | 0.1653 | 0.6247 | 0.1244 |
| 41032 | happy-view | Happy View | shots | platform-encoded-source | 71.00 | 1920x1080 | 29.970 | 10.42 | 88.2 | 4 | 56.3 | 26 | 39.00 | 43.95 | -11% | 1.10 | 5.7 | decelerating | 0.050 | 25.48-57.14 | 0.000 | 40.0 | 18 | 26 | 18 | — | 0.4195 | 0.4219 | 0.1671 |
| 41033 | low-fruit | Low Fruit | shots | platform-encoded-source | 163.95 | 1920x1080 | 29.970 | 10.44 | 204.0 | 4 | 24.4 | 11 | 16.50 | 12.81 | +29% | 3.35 | 2.8 | accelerating | 0.014 | 7.99-29.91 | 0.000 | 101.5 | 33 | 11 | 33 | low-coverage | 0.3360 | 0.3831 | 0.0907 |
| 41036 | wear-your-best-life | Wear Your Best Life | shots | 720p-web-rendition | 60.10 | 1280x720 | 23.976 | 2.54 | 18.2 | 4 | 66.6 | 2 | 3.00 | 2.00 | +50% | 22.48 | 0.0 | — | 0.010 | 0.00-14.08 | 0.000 | 71.0 | 42 | 2 | 42 | — | 0.1360 | 0.2941 | 0.0823 |
| 41037 | big-noon-saturday | Big Noon Saturday | shots | platform-encoded-source | 30.12 | 1920x1080 | 29.970 | 10.41 | 37.4 | 2 | 66.4 | 12 | 36.00 | 33.86 | +6% | 1.62 | 5.6 | accelerating | 0.022 | 18.60-62.88 | 0.167 | 37.0 | 11 | 11 | 11 | — | 0.4967 | 0.4052 | 0.1753 |
| 41038 | the-firefighter | The Firefighter | shots | platform-encoded-source | 34.97 | 1920x1080 | 29.970 | 10.41 | 43.4 | 3 | 85.8 | 15 | 30.00 | 25.74 | +17% | 1.80 | 0.0 | steady | 0.034 | 16.79-49.48 | 0.000 | 45.0 | 19 | 14 | 19 | — | 0.2715 | 0.2046 | 0.0657 |
| 41039 | the-pile-1 | The Pile | shots | platform-encoded-source | 44.97 | 1920x1080 | 29.970 | 10.47 | 56.1 | 4 | 88.9 | 8 | 12.00 | 10.67 | +12% | 5.04 | 0.0 | decelerating | 0.010 | 5.18-23.64 | 0.000 | 121.0 | 36 | 8 | 36 | — | 0.4446 | 0.1565 | 0.0734 |
| 41040 | the-elephant | The Elephant | shots | platform-encoded-source | 41.54 | 1920x1080 | 29.970 | 10.57 | 52.4 | 3 | 72.2 | 11 | 22.00 | 20.22 | +9% | 2.00 | 6.7 | accelerating | 0.025 | 7.52-44.82 | 0.000 | 71.5 | 23 | 10 | 23 | — | 0.2629 | 0.3535 | 0.1117 |
| 41041 | the-roll | The Roll | shots | platform-encoded-source | 40.81 | 1920x1080 | 29.970 | 10.45 | 50.8 | 3 | 73.5 | 7 | 14.00 | 11.76 | +19% | 3.00 | 0.0 | decelerating | 0.008 | 5.63-28.85 | 0.000 | 135.5 | 26 | 7 | 26 | — | 0.2865 | 0.2149 | 0.0567 |
| 41042 | the-run-off-moment | The Run Off Moment | shots | platform-encoded-source | 32.73 | 1920x1080 | 29.970 | 10.40 | 40.6 | 2 | 61.1 | 3 | 9.00 | 7.33 | +23% | 4.64 | 40.0 | decelerating | 0.022 | 1.86-26.30 | 1.000 | 4.0 | 21 | 1 | 21 | burst-heavy | 0.3103 | 0.4266 | 0.0657 |
| 41043 | safety-story-trailer | Safety Story - Trailer | shots | platform-encoded-source | 68.37 | 1920x1080 | 29.970 | 10.42 | 84.9 | 4 | 58.5 | 32 | 48.00 | 41.24 | +16% | 1.03 | 22.9 | accelerating | 0.062 | 32.83-67.76 | 0.438 | 39.0 | 21 | 23 | 21 | — | 0.3388 | 0.2228 | 0.0978 |
| 41044 | samba-1 | Samba | shots | platform-encoded-source | 42.30 | 1920x1080 | 29.970 | 10.48 | 52.9 | 3 | 70.9 | 0 | 0.00 | 0.00 | — | 42.30 | 0.0 | — | 0.004 | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.1405 | 0.3977 | 0.0628 |
| 41045 | carnaval | Carnaval | shots | platform-encoded-source | 23.49 | 1920x1080 | 29.970 | 10.43 | 29.2 | 2 | 85.1 | 0 | 0.00 | 0.00 | — | 23.49 | 0.0 | — | 0.008 | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.1354 | 0.4310 | 0.0734 |
| 41046 | novela | Novela | shots | platform-encoded-source | 22.36 | 1920x1080 | 29.970 | 10.41 | 27.8 | 2 | 89.5 | 1 | 3.00 | 2.68 | +12% | 11.18 | 0.0 | decelerating | 0.008 | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.1751 | 0.3954 | 0.0907 |
| 41047 | tacos | Tacos | shots | platform-encoded-source | 19.54 | 1920x1080 | 29.970 | 10.55 | 24.6 | 1 | 51.2 | 0 | 0.00 | 0.00 | — | 19.54 | 0.0 | — | 0.009 | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.1475 | 0.4703 | 0.1105 |
| 41048 | euroleague-distance | EUROLEAGUE DISTANCE | shots | platform-encoded-source | 67.24 | 1920x1080 | 29.970 | 10.44 | 83.7 | 4 | 59.5 | 28 | 42.00 | 36.58 | +15% | 1.18 | 14.3 | steady | 0.025 | 24.07-65.80 | 0.179 | 34.0 | 21 | 23 | 21 | — | 0.2282 | 0.5105 | 0.1146 |
| 41049 | tapped-to-pay-go-watch-them-play-19 | Tapped to Pay. Go Watch Them Play. (:19) | shots | platform-encoded-source | 19.61 | 1920x1080 | 29.970 | 10.36 | 24.2 | 1 | 51.0 | 3 | 18.00 | 21.42 | -16% | 2.05 | 0.0 | accelerating | 0.019 | 3.71-52.60 | 0.000 | 60.5 | 8 | 3 | 8 | short-sample | 0.2109 | 0.4579 | 0.0808 |
| 41050 | tapped-to-pay-go-watch-them-play-20 | Tapped to Pay. Go Watch Them Play. (:20) | shots | platform-encoded-source | 19.93 | 1920x1080 | 29.970 | 10.35 | 24.6 | 1 | 50.2 | 4 | 24.00 | 18.07 | +33% | 2.14 | 0.0 | decelerating | 0.022 | 6.54-61.45 | 0.000 | 60.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.2236 | 0.3583 | 0.1043 |
| 41051 | tapped-to-pay-go-watch-them-play-22 | Tapped to Pay. Go Watch Them Play. (:22) | shots | platform-encoded-source | 22.93 | 1920x1080 | 29.970 | 10.36 | 28.3 | 2 | 87.2 | 4 | 12.00 | 13.08 | -8% | 2.92 | 0.0 | accelerating | 0.018 | 3.27-30.72 | 0.000 | 74.0 | 18 | 4 | 18 | — | 0.1836 | 0.4015 | 0.0940 |
| 41052 | now-is-your-time | Now is Your Time | shots | platform-encoded-source | 60.10 | 1920x1080 | 29.970 | 10.42 | 74.6 | 4 | 66.6 | 37 | 55.50 | 46.92 | +18% | 1.03 | 16.7 | steady | 0.048 | 38.78-76.87 | 0.216 | 28.5 | 13 | 31 | 13 | — | 0.2169 | 0.0661 | 0.0903 |
| 41053 | sugar-on-my-tongue | Sugar On My Tongue | shots | platform-encoded-source | 163.63 | 1920x1080 | 29.970 | 10.44 | 203.6 | 4 | 24.4 | 51 | 76.50 | 39.60 | +93% | 0.47 | 52.3 | accelerating | 0.008 | 13.88-153.67 | 0.549 | 14.0 | 20 | 24 | 20 | burst-heavy, low-coverage | 0.1725 | 0.2346 | 0.0342 |
| 41054 | tubi-or-you-could-fakin-it | Tubi or You Could Fakin It | shots | platform-encoded-source | 30.10 | 1920x1080 | 29.970 | 10.38 | 37.3 | 2 | 66.4 | 11 | 33.00 | 29.90 | +10% | 1.67 | 0.0 | decelerating | 0.008 | 16.47-59.05 | 0.000 | 58.5 | 11 | 11 | 11 | — | 0.2725 | 0.3633 | 0.0158 |
| 41055 | tubi-or-you-could-meet-cute | Tubi or You Could Meet Cute | shots | platform-encoded-source | 30.10 | 1920x1080 | 29.970 | 10.38 | 37.3 | 2 | 66.4 | 10 | 30.00 | 25.91 | +16% | 2.05 | 0.0 | accelerating | 0.018 | 14.39-55.17 | 0.000 | 68.0 | 12 | 10 | 12 | — | 0.4116 | 0.1910 | 0.1049 |
| 41056 | tubi-or-you-could-abduction | Tubi or You Could Abduction | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.39 | 37.2 | 2 | 66.5 | 4 | 12.00 | 9.98 | +20% | 4.47 | 0.0 | decelerating | 0.015 | 3.27-30.72 | 0.000 | 43.0 | 18 | 4 | 18 | — | 0.1565 | 0.5747 | 0.0715 |
| 41057 | kwik-chats | Kwik Chats | shots | platform-encoded-source | 60.01 | 1920x1080 | 29.970 | 10.44 | 74.7 | 4 | 66.7 | 8 | 12.00 | — | — | — | — | — | — | 5.18-23.64 | 0.000 | 116.0 | 36 | 8 | 36 | — | 0.2567 | 0.3281 | 0.0412 |
| 41059 | merino-deep-dive | Merino Deep Dive | shots | platform-encoded-source | 70.06 | 1920x1080 | 29.970 | 10.42 | 87.0 | 4 | 57.1 | 4 | 6.00 | 5.14 | +17% | 9.18 | 0.0 | accelerating | 0.005 | 1.63-15.36 | 0.000 | 306.0 | 40 | 4 | 40 | — | 0.7841 | 0.1387 | 0.0679 |
| 41060 | the-amber-nectar | The Amber Nectar | shots | platform-encoded-source | 20.05 | 1920x1080 | 29.970 | 10.43 | 24.9 | 1 | 49.9 | 2 | 12.00 | 14.96 | -20% | 3.40 | 0.0 | decelerating | 0.006 | 1.45-43.35 | 0.000 | 42.0 | 9 | 2 | 9 | short-sample | 0.6319 | 0.2329 | 0.0390 |
| 41061 | restroom | Restroom | shots | platform-encoded-source | 15.49 | 1920x1080 | 29.970 | 10.32 | 19.1 | 1 | 64.6 | 4 | 24.00 | 27.12 | -11% | 2.19 | 25.0 | accelerating | 0.018 | 6.54-61.45 | 0.000 | 75.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.1941 | 0.2770 | 0.0557 |
| 41062 | kitchen-2 | Kitchen | shots | platform-encoded-source | 15.49 | 1920x1080 | 29.970 | 10.32 | 19.1 | 1 | 64.6 | 3 | 18.00 | 23.24 | -23% | 2.44 | 28.6 | accelerating | 0.020 | 3.71-52.60 | 0.000 | 77.5 | 8 | 3 | 8 | short-sample | 0.1322 | 0.3982 | 0.0763 |
| 41063 | bedtime-1 | Bedtime | shots | platform-encoded-source | 15.49 | 1920x1080 | 29.970 | 10.32 | 19.1 | 1 | 64.6 | 2 | 12.00 | 15.50 | -23% | 3.10 | 40.0 | accelerating | 0.024 | 1.45-43.35 | 0.000 | 225.0 | 9 | 2 | 9 | short-sample | 0.1024 | 0.3163 | 0.0635 |
| 41064 | curiosity | Curiosity | shots | platform-encoded-source | 90.26 | 1920x1080 | 29.970 | 10.50 | 113.0 | 4 | 44.3 | 25 | 37.50 | 35.90 | +4% | 1.27 | 20.0 | decelerating | 0.040 | 21.70-58.83 | 0.240 | 50.0 | 24 | 20 | 24 | — | 0.2031 | 0.3665 | 0.0720 |
| 41066 | josea | Josea | shots | platform-encoded-source | 124.50 | 1920x1080 | 29.970 | 10.44 | 155.0 | 4 | 32.1 | 24 | 36.00 | 46.75 | -23% | 0.93 | 17.3 | decelerating | 0.042 | 20.46-57.11 | 0.167 | 42.0 | 24 | 20 | 24 | — | 0.3324 | 0.3454 | 0.0978 |
| 41067 | shes-got-range-directors-cut | She's Got Range [Director's Cut] | shots | platform-encoded-source | 59.99 | 1920x1080 | 29.970 | 10.42 | 74.5 | 4 | 66.7 | 44 | 66.00 | 69.01 | -4% | 0.42 | 50.0 | accelerating | 0.033 | 29.91-111.20 | 0.636 | 10.0 | 20 | 24 | 20 | burst-heavy | 0.2666 | 0.3941 | 0.1656 |
| 41068 | ziggo-priority | Ziggo Priority | shots | platform-encoded-source | 39.98 | 1920x1080 | 29.970 | 10.40 | 49.6 | 3 | 75.0 | 23 | 46.00 | 54.03 | -15% | 0.83 | 35.1 | decelerating | 0.060 | 29.16-69.02 | 0.130 | 29.0 | 14 | 19 | 14 | — | 0.3144 | 0.4607 | 0.1653 |
| 41069 | behind-the-scenes-of-petbarn-brand-world | Behind the Scenes of Petbarn Brand World | shots | platform-encoded-source | 15.62 | 1920x1080 | 29.970 | 10.71 | 19.9 | 1 | 64.0 | 17 | 102.00 | 80.69 | +26% | 0.43 | 54.5 | decelerating | 0.074 | 59.42-163.31 | 0.706 | 3.0 | 5 | 6 | 5 | burst-heavy, short-sample, sparse-delta-basis | 0.4579 | 0.2631 | 0.0818 |
| 41071 | life-of-scores | Life of Scores | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 3 | 9.00 | 11.97 | -25% | 2.84 | 0.0 | decelerating | 0.018 | 1.86-26.30 | 0.000 | 94.5 | 19 | 3 | 19 | — | 0.1738 | 0.4093 | 0.0499 |
| 41072 | the-beauty-of-sport | The beauty of sport | shots | platform-encoded-source | 90.05 | 1920x1080 | 29.970 | 10.43 | 111.9 | 4 | 44.4 | 15 | 22.50 | 37.31 | -40% | 0.87 | 33.3 | accelerating | 0.039 | 11.16-39.23 | 0.000 | 50.5 | 30 | 14 | 30 | — | 0.2431 | 0.5721 | 0.1000 |
| 41073 | the-link-directors-cut | THE LINK (DIRECTOR'S CUT) | shots | platform-encoded-source | 97.17 | 1920x1080 | 29.970 | 10.44 | 120.9 | 4 | 41.2 | 15 | 22.50 | 25.93 | -13% | 1.90 | 9.3 | steady | 0.018 | 12.59-37.11 | 0.200 | 49.0 | 31 | 13 | 31 | — | 0.1916 | 0.2443 | 0.0665 |
| 41074 | from-vegas-for-vegas-always-vegas-50-year-legacy | From Vegas. For Vegas. Always Vegas. 50 Year Legacy | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.31 | 18.5 | 1 | 66.4 | 16 | 96.00 | 111.54 | -14% | 0.40 | 62.1 | accelerating | 0.074 | 54.87-155.90 | 0.250 | 17.0 | 1 | 10 | 1 | short-sample, sparse-delta-basis | 0.2136 | 0.2761 | 0.1045 |
| 41075 | from-vegas-for-vegas-always-vegas-group-shot | From Vegas. For Vegas. Always Vegas. Group Shot | shots | platform-encoded-source | 20.07 | 1920x1080 | 29.970 | 10.61 | 25.4 | 1 | 49.8 | 6 | 36.00 | 23.91 | +51% | 1.50 | 0.0 | decelerating | 0.022 | 13.21-78.36 | 0.000 | 45.0 | 6 | 5 | 6 | short-sample, sparse-delta-basis | 0.2004 | 0.3062 | 0.1093 |
| 41076 | from-vegas-for-vegas-always-vegas-team-members | From Vegas. For Vegas. Always Vegas. Team Members | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 23 | 69.00 | 57.85 | +19% | 0.70 | 23.3 | decelerating | 0.075 | 43.74-103.53 | 0.130 | 17.5 | 7 | 15 | 7 | sparse-delta-basis | 0.1662 | 0.3285 | 0.0881 |
| 41077 | woo-hoo | Woo Hoo | shots | platform-encoded-source | 59.97 | 1920x1080 | 29.970 | 10.42 | 74.5 | 4 | 66.7 | 22 | 33.00 | 32.02 | +3% | 1.20 | 3.0 | steady | 0.020 | 16.67-55.49 | 0.091 | 31.0 | 25 | 19 | 25 | — | 0.2225 | 0.3112 | 0.0733 |
| 41079 | now-youre-cooking-1 | Now You're Cooking | shots | platform-encoded-source | 90.05 | 1920x1080 | 29.970 | 10.44 | 112.1 | 4 | 44.4 | 26 | 39.00 | 36.65 | +6% | 1.15 | 33.9 | accelerating | 0.026 | 15.88-70.02 | 0.500 | 22.0 | 27 | 17 | 27 | — | 0.4397 | 0.4205 | 0.1209 |
| 41080 | living-planet-report-2026 | Living Planet Report 2026 | shots | platform-encoded-source | 104.55 | 1920x1080 | 29.970 | 10.45 | 130.2 | 4 | 38.3 | 53 | 79.50 | 111.90 | -29% | 0.10 | 74.0 | decelerating | 0.040 | 8.41-166.76 | 0.642 | 5.0 | 23 | 21 | 23 | burst-heavy | 0.4142 | 0.4213 | 0.0443 |
| 41082 | obsession-comes-around | Obsession Comes Around | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.45 | 37.5 | 2 | 66.5 | 8 | 24.00 | 33.91 | -29% | 1.45 | 22.2 | decelerating | 0.031 | 10.36-47.29 | 0.000 | 73.0 | 15 | 7 | 15 | — | 0.1589 | 0.3055 | 0.1071 |
| 41083 | qualia-nad-mind | Qualia NAD Mind | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.50 | 37.6 | 2 | 66.5 | 11 | 33.00 | 29.92 | +10% | 1.80 | 6.2 | decelerating | 0.026 | 16.47-59.05 | 0.000 | 54.0 | 11 | 11 | 11 | — | 0.2138 | 0.2829 | 0.0521 |
| 41084 | qualia-nad | Qualia NAD | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.50 | 37.6 | 2 | 66.5 | 14 | 42.00 | 31.91 | +32% | 1.40 | 5.9 | decelerating | 0.029 | 22.96-70.47 | 0.143 | 38.0 | 9 | 13 | 9 | — | 0.2383 | 0.2676 | 0.0609 |
| 41085 | qualia-nad-master | Qualia NAD Master | shots | platform-encoded-source | 29.99 | 1920x1080 | 29.970 | 10.39 | 37.1 | 2 | 66.7 | 10 | 30.00 | 24.00 | +25% | 1.90 | 0.0 | decelerating | 0.026 | 14.39-55.17 | 0.000 | 54.0 | 12 | 10 | 12 | — | 0.2234 | 0.2731 | 0.0707 |
| 41086 | we-listen | We Listen | shots | platform-encoded-source | 34.86 | 1920x1080 | 29.970 | 10.40 | 43.2 | 3 | 86.1 | 19 | 38.00 | 34.42 | +10% | 1.03 | 9.5 | decelerating | 0.038 | 16.90-67.78 | 0.000 | 31.0 | 15 | 18 | 15 | — | 0.2940 | 0.3319 | 0.0822 |
| 41087 | the-swimmer | The Swimmer | shots | platform-encoded-source | 69.33 | 1920x1080 | 29.970 | 10.42 | 86.1 | 4 | 57.7 | 44 | 66.00 | 66.63 | -1% | 0.60 | 32.1 | accelerating | 0.053 | 41.27-96.98 | 0.227 | 20.0 | 14 | 30 | 14 | — | 0.4637 | 0.4089 | 0.0565 |
| 41089 | selfie-for-all | Selfie For All | shots | platform-encoded-source | 121.13 | 1920x1080 | 29.970 | 10.46 | 151.0 | 4 | 33.0 | 14 | 21.00 | 15.85 | +32% | 2.67 | 0.0 | accelerating | 0.020 | 11.26-35.57 | 0.000 | 73.0 | 30 | 14 | 30 | — | 0.1942 | 0.3413 | 0.1095 |
| 41090 | grandpa-1 | Grandpa | shots | platform-encoded-source | 60.01 | 1920x1080 | 29.970 | 10.53 | 75.4 | 4 | 66.7 | 8 | 12.00 | 10.00 | +20% | 4.19 | 0.0 | accelerating | 0.013 | 5.18-23.64 | 0.000 | 125.0 | 36 | 8 | 36 | — | 0.1536 | 0.3391 | 0.0506 |
| 41091 | lightswitch | Lightswitch | shots | platform-encoded-source | 30.02 | 1920x1080 | 29.970 | 10.65 | 38.1 | 2 | 66.6 | 3 | 9.00 | 11.99 | -25% | 4.04 | 14.3 | — | 0.013 | 1.86-26.30 | 0.000 | 87.5 | 19 | 3 | 19 | — | 0.1237 | 0.4033 | 0.0456 |
| 41092 | tickets | Tickets | shots | platform-encoded-source | 20.01 | 1920x1080 | 29.970 | 10.65 | 25.4 | 1 | 50.0 | 6 | 36.00 | 35.98 | +0% | 1.30 | 0.0 | decelerating | 0.027 | 13.21-78.36 | 0.000 | 41.0 | 5 | 6 | 5 | short-sample, sparse-delta-basis | 0.1780 | 0.3361 | 0.0373 |
| 41093 | drumming-1 | Drumming | shots | platform-encoded-source | 20.01 | 1920x1080 | 29.970 | 10.72 | 25.6 | 1 | 50.0 | 4 | 24.00 | 20.99 | +14% | 2.50 | 0.0 | decelerating | 0.019 | 6.54-61.45 | 0.000 | 59.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.1656 | 0.3893 | 0.0638 |
| 41094 | kiss | Kiss | shots | platform-encoded-source | 20.01 | 1920x1080 | 29.970 | 10.71 | 25.5 | 1 | 50.0 | 0 | 0.00 | 3.00 | -100% | 10.01 | 0.0 | — | 0.006 | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.0695 | 0.4980 | 0.0305 |
| 41095 | mocktail | Mocktail | shots | platform-encoded-source | 19.93 | 1920x1080 | 29.970 | 10.71 | 25.4 | 1 | 50.2 | 6 | 36.00 | 30.11 | +20% | 1.87 | 0.0 | decelerating | 0.037 | 13.21-78.36 | 0.000 | 32.0 | 6 | 5 | 6 | short-sample, sparse-delta-basis | 0.4163 | 0.5399 | 0.0820 |
| 41096 | mule | Mule | shots | platform-encoded-source | 70.38 | 1920x1080 | 29.970 | 10.42 | 87.5 | 4 | 56.8 | 3 | 4.50 | 3.41 | +32% | 12.05 | 0.0 | steady | 0.001 | 0.93-13.15 | 0.000 | 839.5 | 41 | 3 | 41 | — | 0.3813 | 0.1674 | 0.0303 |
| 41097 | attention-to-detail | Attention To Detail | shots | platform-encoded-source | 56.53 | 1920x1080 | 29.970 | 10.44 | 70.4 | 4 | 70.8 | 1 | 1.50 | 2.12 | -29% | 19.83 | 0.0 | — | 0.001 | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.3503 | 0.2028 | 0.0290 |
| 41098 | pinata-2 | Piñata | shots | platform-encoded-source | 37.16 | 1920x1080 | 29.970 | 10.44 | 46.3 | 3 | 80.7 | 10 | 20.00 | 19.37 | +3% | 2.14 | 0.0 | accelerating | 0.006 | 8.13-39.13 | 0.000 | 55.0 | 23 | 10 | 23 | — | 0.2837 | 0.1807 | 0.0225 |
| 41099 | vibes-1 | Vibes | shots | platform-encoded-source | 42.22 | 1920x1080 | 29.970 | 10.40 | 52.3 | 3 | 71.1 | 9 | 18.00 | 15.63 | +15% | 2.00 | 0.0 | decelerating | 0.005 | 8.23-34.17 | 0.000 | 96.5 | 24 | 9 | 24 | — | 0.3215 | 0.1818 | 0.0557 |
| 41100 | i-give-everything-i-have-2-u | I Give Everything I Have 2 U | shots | platform-encoded-source | 113.73 | 1920x1080 | 29.970 | 10.51 | 142.4 | 4 | 35.2 | 1 | 1.50 | 7.91 | -81% | 0.17 | 75.0 | accelerating | 0.012 | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.1046 | 0.4143 | 0.0533 |
| 41101 | anatomi | ANATOMI | shots | platform-encoded-source | 108.22 | 1920x1080 | 29.970 | 10.43 | 134.6 | 4 | 37.0 | 9 | 13.50 | 13.31 | +1% | 1.94 | 16.0 | decelerating | 0.005 | 3.43-30.17 | 0.333 | 55.5 | 37 | 7 | 37 | — | 0.1807 | 0.3461 | 0.0762 |
| 41102 | chemi-kills | Chemi-Kills | shots | platform-encoded-source | 29.95 | 1920x1080 | 29.970 | 10.39 | 37.1 | 2 | 66.8 | 7 | 21.00 | 18.03 | +16% | 2.48 | 0.0 | steady | 0.012 | 8.44-43.27 | 0.000 | 78.0 | 15 | 7 | 15 | — | 0.2664 | 0.3974 | 0.0679 |
| 41103 | wake-up-1 | Wake Up | shots | platform-encoded-source | 29.95 | 1920x1080 | 29.970 | 10.45 | 37.3 | 2 | 66.8 | 11 | 33.00 | 30.05 | +10% | 1.45 | 0.0 | decelerating | 0.029 | 16.47-59.05 | 0.000 | 43.5 | 12 | 10 | 12 | — | 0.2794 | 0.1937 | 0.0591 |
| 41104 | theres-time-for-everything | There’s Time for Everything | shots | platform-encoded-source | 97.13 | 1920x1080 | 29.970 | 10.44 | 120.9 | 4 | 41.2 | 10 | 15.00 | 12.97 | +16% | 3.85 | 0.0 | decelerating | 0.028 | 5.55-30.24 | 0.000 | 114.0 | 34 | 10 | 34 | — | 0.3387 | 0.3339 | 0.0732 |
| 41105 | denial | DENIAL | shots | platform-encoded-source | 88.51 | 1920x1080 | 29.970 | 10.43 | 110.0 | 4 | 45.2 | 18 | 27.00 | 25.08 | +8% | 1.62 | 13.2 | decelerating | 0.006 | 4.40-59.20 | 0.222 | 37.0 | 30 | 14 | 30 | — | 0.3410 | 0.2192 | 0.0700 |
| 41107 | the-boot-room | The Boot Room | shots | platform-encoded-source | 26.28 | 1920x1080 | 29.970 | 10.48 | 32.8 | 2 | 76.1 | 21 | 63.00 | 57.07 | +10% | 0.68 | 46.2 | decelerating | 0.028 | 39.00-96.30 | 0.429 | 20.5 | 8 | 14 | 8 | — | 0.1625 | 0.5966 | 0.1328 |
| 41108 | speed-2 | Speed | shots | platform-encoded-source | 10.22 | 1920x1080 | 29.970 | 10.69 | 13.0 | 1 | 88.1 | 0 | 0.00 | 0.00 | — | 10.22 | 0.0 | — | 0.016 | 0.00-24.59 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.1673 | 0.6737 | 0.1187 |
| 41112 | glorious-coffee | Glorious Coffee | shots | platform-encoded-source | 60.42 | 1920x1080 | 29.970 | 10.42 | 75.1 | 4 | 66.2 | 15 | 22.50 | 19.86 | +13% | 2.00 | 0.0 | accelerating | 0.019 | 12.59-37.11 | 0.000 | 63.5 | 29 | 15 | 29 | — | 0.1744 | 0.3774 | 0.0658 |
| 41113 | for-days-that-run-hot-spec-spot | For Days That Run Hot (Spec Spot) | shots | platform-encoded-source | 60.01 | 1920x1080 | 29.970 | 10.42 | 74.6 | 4 | 66.7 | 33 | 49.50 | 48.99 | +1% | 1.12 | 14.0 | accelerating | 0.041 | 28.76-76.42 | 0.152 | 28.5 | 16 | 28 | 16 | — | 0.2205 | 0.3434 | 0.1412 |
| 41114 | aldi-kids | ALDI Kids | shots | platform-encoded-source | 104.04 | 1920x1080 | 29.970 | 10.43 | 129.4 | 4 | 38.4 | 5 | 7.50 | 8.65 | -13% | 4.84 | 0.0 | decelerating | 0.014 | 2.44-17.50 | 0.000 | 362.5 | 39 | 5 | 39 | — | 0.1490 | 0.2088 | 0.0517 |
| 41116 | the-art-of-entering-the-sea | The Art of Entering the Sea | shots | platform-encoded-source | 130.60 | 1920x1080 | 29.970 | 10.43 | 162.4 | 4 | 30.6 | 6 | 9.00 | 11.03 | -18% | 4.34 | 8.0 | steady | 0.002 | 3.30-19.59 | 0.000 | 891.0 | 38 | 6 | 38 | — | 0.2137 | 0.4075 | 0.0236 |
| 41120 | memories-2 | Memories | shots | platform-encoded-source | 60.10 | 1920x1080 | 29.970 | 10.45 | 74.9 | 4 | 66.6 | 16 | 24.00 | 20.97 | +14% | 2.30 | 0.0 | steady | 0.016 | 13.72-38.97 | 0.000 | 63.0 | 28 | 16 | 28 | — | 0.1991 | 0.3633 | 0.0869 |
| 41121 | marvin-the-villain | Marvin the Villain | shots | platform-encoded-source | 59.97 | 1920x1080 | 29.970 | 10.54 | 75.3 | 4 | 66.7 | 22 | 33.00 | 33.02 | +0% | 1.70 | 11.8 | decelerating | 0.029 | 20.68-49.96 | 0.136 | 45.0 | 25 | 19 | 25 | — | 0.2765 | 0.1693 | 0.0478 |
| 41122 | true-story | True Story | shots | 720p-web-rendition | 106.88 | 1280x720 | 25.000 | 2.55 | 32.5 | 4 | 37.4 | 16 | 24.00 | 28.07 | -14% | 1.32 | 2.0 | decelerating | 0.017 | 7.74-47.68 | 0.000 | 35.0 | 29 | 15 | 29 | — | 0.1597 | 0.4517 | 0.0676 |
| 41123 | spacewalk | Spacewalk | shots | platform-encoded-source | 30.02 | 1920x1080 | 29.970 | 10.51 | 37.6 | 2 | 66.6 | 5 | 15.00 | 15.99 | -6% | 2.44 | 0.0 | decelerating | 0.007 | 4.87-35.00 | 0.000 | 128.5 | 17 | 5 | 17 | — | 0.1802 | 0.2979 | 0.0398 |
| 41124 | human-statue | Human Statue | shots | platform-encoded-source | 40.02 | 1920x1080 | 29.970 | 10.44 | 49.8 | 3 | 75.0 | 18 | 36.00 | 31.48 | +14% | 1.35 | 0.0 | accelerating | 0.019 | 18.04-61.59 | 0.000 | 44.0 | 16 | 17 | 16 | — | 0.2515 | 0.3698 | 0.0763 |
| 41125 | detective | Detective | shots | platform-encoded-source | 60.01 | 1920x1080 | 29.970 | 10.43 | 74.6 | 4 | 66.7 | 0 | 0.00 | 1.00 | -100% | 30.01 | 0.0 | — | 0.004 | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.0674 | 0.3407 | 0.0434 |
| 41126 | everyday-excitement | Everyday Excitement | shots | platform-encoded-source | 45.06 | 1920x1080 | 29.970 | 10.41 | 55.9 | 4 | 88.8 | 21 | 31.50 | 27.97 | +13% | 1.79 | 0.0 | decelerating | 0.015 | 19.50-48.15 | 0.000 | 50.5 | 24 | 20 | 24 | — | 0.3898 | 0.3288 | 0.0643 |
| 41127 | nimm-den-stress-nicht-mit-ins-bett-woman | Nimm den Stress nicht mit ins Bett - Woman | shots | 720p-web-rendition | 42.05 | 1280x720 | 25.000 | 2.55 | 12.8 | 3 | 71.3 | 3 | 6.00 | 5.71 | +5% | 9.24 | 0.0 | decelerating | 0.004 | 1.24-17.53 | 0.000 | 147.5 | 30 | 3 | 30 | — | 0.1112 | 0.4715 | 0.0362 |
| 41128 | nimm-den-stress-nicht-mit-ins-bett-man | Nimm den Stress nicht mit ins Bett - Man | shots | 720p-web-rendition | 42.01 | 1280x720 | 25.000 | 2.50 | 12.5 | 3 | 71.4 | 4 | 8.00 | 7.14 | +12% | 4.84 | 0.0 | — | 0.007 | 2.18-20.48 | 0.000 | 59.0 | 30 | 3 | 30 | — | 0.1120 | 0.4257 | 0.0478 |
| 41129 | in-lock-step | In Lock Step | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 13 | 39.00 | 33.91 | +15% | 1.52 | 0.0 | decelerating | 0.058 | 20.77-66.69 | 0.000 | 35.5 | 9 | 13 | 9 | — | 0.2436 | 0.2634 | 0.1182 |
| 41130 | the-longest-goodbye | The Longest Goodbye | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 9 | 27.00 | 25.93 | +4% | 1.53 | 0.0 | steady | 0.019 | 12.35-51.25 | 0.000 | 53.5 | 13 | 9 | 13 | — | 0.1883 | 0.2821 | 0.0901 |
| 41131 | notification-melody | Notification Melody | shots | platform-encoded-source | 45.10 | 1920x1080 | 29.970 | 10.40 | 55.9 | 4 | 88.7 | 23 | 34.50 | 30.60 | +13% | 1.18 | 4.2 | decelerating | 0.015 | 10.41-67.43 | 0.000 | 33.5 | 22 | 22 | 22 | — | 0.2618 | 0.1588 | 0.0500 |
| 41132 | good-read | Good Read | shots | platform-encoded-source | 45.10 | 1920x1080 | 29.970 | 10.40 | 55.9 | 4 | 88.7 | 15 | 22.50 | 19.96 | +13% | 1.95 | 0.0 | decelerating | 0.009 | 9.71-41.36 | 0.000 | 58.5 | 29 | 15 | 29 | — | 0.3014 | 0.1842 | 0.0507 |
| 41133 | sunbathing-2 | Sunbathing | shots | platform-encoded-source | 45.10 | 1920x1080 | 29.970 | 10.40 | 55.9 | 4 | 88.7 | 13 | 19.50 | 17.30 | +13% | 2.09 | 0.0 | decelerating | 0.002 | 7.55-37.65 | 0.000 | 60.0 | 31 | 13 | 31 | — | 0.2822 | 0.2244 | 0.0273 |
| 41134 | costume-party | Costume Party | shots | platform-encoded-source | 14.98 | 1920x1080 | 29.970 | 10.35 | 18.5 | 1 | 66.8 | 3 | 18.00 | 12.02 | +50% | 1.25 | 0.0 | decelerating | 0.013 | 3.71-52.60 | 0.000 | 37.5 | 8 | 3 | 8 | short-sample | 0.3049 | 0.5126 | 0.1003 |
| 41135 | pastry-shop | Pastry Shop | shots | platform-encoded-source | 14.98 | 1920x1080 | 29.970 | 10.34 | 18.5 | 1 | 66.8 | 1 | 6.00 | 4.01 | +50% | 7.49 | 0.0 | decelerating | 0.009 | 0.15-33.43 | — | — | 10 | 1 | 10 | short-sample | 0.5110 | 0.4815 | 0.0973 |
| 41136 | in-the-train | In The Train | shots | platform-encoded-source | 14.98 | 1920x1080 | 29.970 | 10.32 | 18.4 | 1 | 66.8 | 1 | 6.00 | 4.01 | +50% | 7.49 | 0.0 | decelerating | 0.010 | 0.15-33.43 | — | — | 10 | 1 | 10 | short-sample | 0.4096 | 0.5863 | 0.1051 |
| 41137 | billboard | Billboard | shots | platform-encoded-source | 19.97 | 1920x1080 | 29.970 | 10.73 | 25.5 | 1 | 50.1 | 2 | 12.00 | 27.04 | -56% | 0.17 | 70.0 | accelerating | 0.011 | 1.45-43.35 | 0.000 | 87.0 | 9 | 2 | 9 | short-sample | 0.3464 | 0.6642 | 0.1471 |
| 41138 | cheers-against-prohibition | Cheers Against Prohibition | shots | platform-encoded-source | 64.55 | 1920x1080 | 29.970 | 10.43 | 80.3 | 4 | 62.0 | 0 | 0.00 | 0.00 | — | 64.55 | 0.0 | — | 0.021 | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.3111 | 0.1907 | 0.1017 |
| 41139 | every-cat-is-an-individual | Every Cat Is an Individual | shots | platform-encoded-source | 129.09 | 1920x1080 | 29.970 | 10.45 | 160.8 | 4 | 31.0 | 4 | 6.00 | 8.37 | -28% | 6.11 | 0.0 | accelerating | 0.004 | 1.63-15.36 | 0.000 | 951.0 | 40 | 4 | 40 | — | 0.3616 | 0.2411 | 0.0247 |
| 41140 | sounds-like-a-job-for-british-gas | Sounds Like A Job For British Gas | shots | platform-encoded-source | 30.02 | 1920x1080 | 29.970 | 10.47 | 37.5 | 2 | 66.6 | 15 | 45.00 | 37.98 | +18% | 1.17 | 0.0 | decelerating | 0.046 | 25.19-74.22 | 0.000 | 35.0 | 8 | 14 | 8 | — | 0.3276 | 0.2814 | 0.1515 |
| 41142 | make-it-possible | Make it Possible | shots | platform-encoded-source | 59.99 | 1920x1080 | 29.970 | 10.43 | 74.6 | 4 | 66.7 | 31 | 46.50 | 47.01 | -1% | 0.98 | 14.6 | decelerating | 0.054 | 25.82-73.56 | 0.065 | 29.0 | 18 | 26 | 18 | — | 0.2237 | 0.5263 | 0.1319 |
| 41143 | make-it-possible-behind-the-scenes | Make it Possible Behind the Scenes | shots | platform-encoded-source | 166.10 | 1920x1080 | 29.970 | 10.47 | 207.2 | 4 | 24.1 | 6 | 9.00 | 10.11 | -11% | 5.31 | 0.0 | decelerating | 0.007 | 3.30-19.59 | 0.000 | 1229.0 | 38 | 6 | 38 | low-coverage | 0.3243 | 0.2343 | 0.0807 |
| 41144 | pubscription | Pubscription | shots | platform-encoded-source | 56.30 | 1920x1080 | 29.970 | 10.41 | 69.9 | 4 | 71.0 | 10 | 15.00 | 20.25 | -26% | 1.63 | 30.0 | accelerating | 0.017 | 1.94-36.06 | 0.200 | 52.0 | 36 | 8 | 36 | — | 0.1250 | 0.5648 | 0.0756 |
| 41147 | personas | Personas | shots | platform-encoded-source | 67.24 | 1920x1080 | 29.970 | 10.42 | 83.5 | 4 | 59.5 | 40 | 60.00 | 56.21 | +7% | 0.88 | 6.2 | decelerating | 0.069 | 42.86-81.70 | 0.000 | 29.0 | 10 | 34 | 10 | — | 0.2988 | 0.2461 | 0.1218 |
| 41149 | fight-cancer | Fight Cancer | shots | platform-encoded-source | 37.97 | 1920x1080 | 29.970 | 10.40 | 47.1 | 3 | 79.0 | 3 | 6.00 | 4.74 | +27% | 8.32 | 0.0 | decelerating | 0.011 | 0.00-25.98 | 0.000 | 96.0 | 30 | 3 | 30 | — | 0.0975 | 0.3691 | 0.0637 |
| 41150 | behind-the-scenes-of-wear-your-best-life | Behind the Scenes of Wear Your Best Life | shots | platform-encoded-source | 33.69 | 1920x1080 | 29.970 | 10.41 | 41.8 | 3 | 89.1 | 0 | 0.00 | 0.00 | — | 33.69 | 0.0 | — | 0.009 | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.0917 | 0.0966 | 0.0533 |
| 41151 | mother-of-all-mammograms-breast-friends | Mother of All Mammograms - Breast Friends | shots | platform-encoded-source | 18.03 | 1920x1080 | 29.970 | 10.48 | 22.5 | 1 | 55.5 | 1 | 6.00 | 6.66 | -10% | 2.94 | 33.3 | steady | 0.002 | 0.15-33.43 | — | — | 10 | 1 | 10 | short-sample | 0.4298 | 0.3512 | 0.0164 |
| 41152 | mother-of-all-mammograms-advanced-tech | Mother of All Mammograms - Advanced Tech | shots | platform-encoded-source | 25.45 | 1920x1080 | 29.970 | 10.56 | 32.1 | 2 | 78.6 | 1 | 3.00 | 2.36 | +27% | 12.73 | 0.0 | decelerating | 0.001 | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.3870 | 0.3960 | 0.0182 |
| 41153 | mother-of-all-mammograms | Mother of All Mammograms | shots | platform-encoded-source | 33.26 | 1920x1080 | 29.970 | 10.52 | 41.7 | 2 | 60.1 | 1 | 3.00 | 1.80 | +66% | 16.63 | 0.0 | decelerating | 0.001 | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.3807 | 0.4084 | 0.0164 |
| 41154 | mother-of-all-mammograms-comfort | Mother of All Mammograms - Comfort | shots | platform-encoded-source | 17.98 | 1920x1080 | 29.970 | 10.54 | 22.6 | 1 | 55.6 | 1 | 6.00 | 3.34 | +80% | 8.99 | 0.0 | decelerating | 0.001 | 0.15-33.43 | — | — | 10 | 1 | 10 | short-sample | 0.4280 | 0.3313 | 0.0118 |
| 41155 | one-journey-of-many | One Journey of Many | shots | platform-encoded-source | 139.09 | 1920x1080 | 29.970 | 10.44 | 173.2 | 4 | 28.8 | 16 | 24.00 | 24.16 | -1% | 1.43 | 3.5 | decelerating | 0.016 | 8.87-46.04 | 0.000 | 43.0 | 28 | 16 | 28 | — | 0.2707 | 0.4036 | 0.0589 |
| 41156 | hockey-1 | Hockey | shots | platform-encoded-source | 30.21 | 1920x1080 | 29.970 | 10.38 | 37.4 | 2 | 66.2 | 33 | 99.00 | 83.42 | +19% | 0.53 | 39.5 | decelerating | 0.049 | 68.15-139.03 | 0.364 | 16.0 | 3 | 19 | 3 | sparse-delta-basis | 0.3461 | 0.2322 | 0.0898 |
| 41157 | come-back-louder | Come Back Louder | shots | platform-encoded-source | 29.99 | 1920x1080 | 29.970 | 10.38 | 37.1 | 2 | 66.7 | 31 | 93.00 | 112.02 | -17% | 0.40 | 59.6 | accelerating | 0.081 | 63.19-132.01 | 0.226 | 14.5 | 5 | 17 | 5 | sparse-delta-basis | 0.2448 | 0.5217 | 0.1618 |
| 41158 | climber | Climber | shots | platform-encoded-source | 59.97 | 1920x1080 | 29.970 | 10.42 | 74.5 | 4 | 66.7 | 13 | 19.50 | 23.01 | -15% | 1.84 | 20.8 | accelerating | 0.027 | 10.38-33.35 | 0.154 | 100.0 | 32 | 12 | 32 | — | 0.1800 | 0.3333 | 0.0836 |
| 41159 | good-move-bumpers | Good Move - Bumpers | shots | platform-encoded-source | 60.25 | 1920x1080 | 29.970 | 10.42 | 74.8 | 4 | 66.4 | 4 | 6.00 | 7.97 | -25% | 6.27 | 0.0 | decelerating | 0.004 | 1.63-15.36 | 0.000 | 437.0 | 40 | 4 | 40 | — | 0.1434 | 0.4307 | 0.0397 |
| 41160 | making-air-free | Making Air Free | shots | platform-encoded-source | 78.02 | 1920x1080 | 29.970 | 10.42 | 96.9 | 4 | 51.3 | 14 | 21.00 | 36.15 | -42% | 1.10 | 31.2 | accelerating | 0.029 | 11.48-35.23 | 0.000 | 55.0 | 30 | 14 | 30 | — | 0.2042 | 0.4632 | 0.1054 |
| 41161 | points-of-inspiration | Points of Inspiration | shots | platform-encoded-source | 122.73 | 1920x1080 | 29.970 | 10.43 | 152.6 | 4 | 32.6 | 24 | 36.00 | 37.64 | -4% | 1.47 | 5.1 | steady | 0.044 | 23.07-53.57 | 0.000 | 46.0 | 22 | 22 | 22 | — | 0.4156 | 0.2204 | 0.0893 |
| 41162 | sweat | Sweat | shots | platform-encoded-source | 144.68 | 1920x1080 | 29.970 | 10.46 | 180.3 | 4 | 27.6 | 15 | 22.50 | 25.30 | -11% | 1.20 | 9.7 | decelerating | 0.022 | 12.59-37.11 | 0.000 | 44.0 | 29 | 15 | 29 | — | 0.1282 | 0.1190 | 0.0779 |
| 41163 | both-sides | Both Sides | shots | platform-encoded-source | 90.05 | 1920x1080 | 29.970 | 10.44 | 112.1 | 4 | 44.4 | 14 | 21.00 | 21.32 | -2% | 2.40 | 0.0 | decelerating | 0.020 | 11.48-35.23 | 0.000 | 72.0 | 30 | 14 | 30 | — | 0.2209 | 0.2980 | 0.0938 |
| 41164 | adminvasion | ADMINVASION | shots | platform-encoded-source | 74.69 | 1920x1080 | 29.970 | 10.42 | 92.8 | 4 | 53.6 | 14 | 21.00 | 24.90 | -16% | 1.38 | 6.2 | accelerating | 0.044 | 8.89-39.11 | 0.000 | 85.0 | 31 | 13 | 31 | — | 0.3725 | 0.3133 | 0.1069 |
| 41165 | nike-x-cortiez | Nike X Cortiez | shots | platform-encoded-source | 138.77 | 1920x1080 | 29.970 | 10.43 | 172.6 | 4 | 28.8 | 27 | 40.50 | 31.99 | +27% | 0.47 | 50.7 | accelerating | 0.015 | 0.00-100.78 | 0.741 | 5.5 | 33 | 11 | 33 | burst-heavy | 0.3084 | 0.1965 | 0.0542 |
| 41166 | more-starts-here | More Starts Here | shots | platform-encoded-source | 46.14 | 1920x1080 | 29.970 | 10.45 | 57.5 | 4 | 86.7 | 18 | 27.00 | 26.01 | +4% | 2.04 | 0.0 | steady | 0.021 | 16.00-42.67 | 0.000 | 51.0 | 26 | 18 | 26 | — | 0.2491 | 0.3286 | 0.0993 |
| 41167 | designed-for-artistic-exploration | Designed for Artistic Exploration | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.60 | 38.0 | 2 | 66.5 | 26 | 78.00 | 77.79 | +0% | 0.70 | 35.0 | steady | 0.077 | 50.95-114.29 | 0.077 | 22.0 | 3 | 19 | 3 | sparse-delta-basis | 0.3659 | 0.2635 | 0.0821 |
| 41168 | drop-the-robot | Drop the Robot | shots | platform-encoded-source | 40.04 | 1920x1080 | 29.970 | 10.45 | 49.9 | 3 | 74.9 | 20 | 40.00 | 50.95 | -21% | 1.07 | 22.9 | decelerating | 0.037 | 24.43-61.78 | 0.000 | 41.0 | 14 | 19 | 14 | — | 0.3380 | 0.3742 | 0.1057 |
| 41169 | apple-music-rebrand | Apple Music Rebrand | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.31 | 18.5 | 1 | 66.4 | 4 | 24.00 | 23.90 | +0% | 1.84 | 14.3 | steady | 0.055 | 6.54-61.45 | 0.000 | 55.0 | 8 | 3 | 8 | short-sample | 0.1194 | 0.5367 | 0.1053 |
| 41170 | apple-music-rebrand-behind-the-scenes | Apple Music Rebrand Behind the Scenes | shots | platform-encoded-source | 73.30 | 1920x1080 | 29.970 | 10.42 | 91.0 | 4 | 54.6 | 16 | 24.00 | 23.74 | +1% | 2.09 | 0.0 | steady | 0.035 | 13.72-38.97 | 0.000 | 67.0 | 28 | 16 | 28 | — | 0.3097 | 0.4559 | 0.0942 |
| 41171 | joe-cool | Joe Cool | shots | platform-encoded-source | 15.19 | 1920x1080 | 29.970 | 10.39 | 18.8 | 1 | 65.8 | 2 | 12.00 | 7.90 | +52% | 3.44 | 33.3 | decelerating | 0.011 | 1.45-43.35 | 0.000 | 103.0 | 9 | 2 | 9 | short-sample | 0.2408 | 0.1240 | 0.0509 |
| 41172 | for-days-that-dont-slow-down | For Days That Don't Slow Down | shots | platform-encoded-source | 15.19 | 1920x1080 | 29.970 | 10.32 | 18.7 | 1 | 65.8 | 6 | 36.00 | 39.50 | -9% | 1.13 | 18.2 | accelerating | 0.119 | 13.21-78.36 | 0.000 | 57.0 | 5 | 6 | 5 | short-sample, sparse-delta-basis | 0.3937 | 0.4706 | 0.1531 |
| 41173 | the-one-feat-nia-long | The One feat. Nia Long | shots | platform-encoded-source | 41.86 | 1920x1080 | 29.970 | 10.40 | 51.9 | 3 | 71.7 | 1 | 2.00 | 1.43 | +40% | 20.93 | 50.0 | decelerating | 0.004 | 0.05-11.14 | — | — | 32 | 1 | 32 | — | 0.0956 | 0.1248 | 0.0365 |
| 41174 | power-your-legacy | Power Your Legacy | shots | platform-encoded-source | 30.21 | 1920x1080 | 29.970 | 10.49 | 37.8 | 2 | 66.2 | 20 | 60.00 | 53.63 | +12% | 0.90 | 25.0 | steady | 0.062 | 36.65-92.67 | 0.350 | 25.0 | 8 | 14 | 8 | — | 0.3172 | 0.2885 | 0.1328 |
| 41175 | episode-1-john-stamos-is-pantenes-ultimate-ambassador | Episode 1: John Stamos Is Pantene's Ultimate Ambassador? | shots | platform-encoded-source | 145.02 | 1920x1080 | 29.970 | 10.44 | 180.5 | 4 | 27.6 | 13 | 19.50 | 26.06 | -25% | 1.79 | 4.7 | steady | 0.011 | 6.20-39.70 | 0.000 | 60.0 | 31 | 13 | 31 | — | 0.4630 | 0.2604 | 0.1319 |
| 41176 | the-bend | The Bend | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.57 | 37.9 | 2 | 66.5 | 5 | 15.00 | 11.98 | +25% | 2.03 | 0.0 | steady | 0.032 | 4.87-35.00 | 0.000 | 48.5 | 17 | 5 | 17 | — | 0.0795 | 0.3214 | 0.0750 |
| 41177 | new-exxon-el-nino-commercial | New Exxon El Nino Commercial | shots | platform-encoded-source | 179.61 | 1920x1080 | 29.970 | 10.44 | 223.5 | 4 | 22.3 | 21 | 31.50 | 45.43 | -31% | 0.97 | 24.1 | decelerating | 0.046 | 19.50-48.15 | 0.095 | 37.0 | 24 | 20 | 24 | low-coverage | 0.3608 | 0.3430 | 0.1182 |
| 41179 | asian-paints-taoyyari-shuru-tyohaar-shuru | ASIAN PAINTS - TAOYYARI SHURU, TYOHAAR SHURU | shots | platform-encoded-source | 94.06 | 1920x1080 | 29.970 | 10.44 | 117.0 | 4 | 42.5 | 14 | 21.00 | 14.67 | +43% | 1.80 | 4.2 | steady | 0.029 | 3.13-47.72 | 0.143 | 47.0 | 31 | 13 | 31 | — | 0.3597 | 0.3658 | 0.1649 |
| 41181 | when-i-grow-up | When I Grow Up | shots | platform-encoded-source | 60.01 | 1920x1080 | 29.970 | 10.44 | 74.7 | 4 | 66.7 | 9 | 13.50 | 13.00 | +4% | 3.04 | 28.6 | decelerating | 0.003 | 6.17-25.63 | 0.222 | 147.5 | 36 | 8 | 36 | — | 0.1762 | 0.3065 | 0.0403 |
| 41182 | kids-room-casino | Kids’ Room Casino. | shots | platform-encoded-source | 29.97 | 1920x1080 | 29.970 | 10.43 | 37.3 | 2 | 66.7 | 12 | 36.00 | 28.02 | +28% | 0.47 | 53.3 | decelerating | 0.010 | 18.60-62.88 | 0.667 | 8.0 | 16 | 6 | 16 | burst-heavy | 0.2910 | 0.3289 | 0.0345 |
| 41184 | ross | Ross | shots | platform-encoded-source | 53.35 | 1920x1080 | 29.970 | 10.41 | 66.2 | 4 | 75.0 | 12 | 18.00 | 19.12 | -6% | 2.20 | 5.6 | decelerating | 0.020 | 8.83-32.17 | 0.000 | 73.0 | 32 | 12 | 32 | — | 0.4269 | 0.2408 | 0.0889 |
| 41185 | andrew | Andrew | shots | platform-encoded-source | 62.08 | 1920x1080 | 29.970 | 10.42 | 77.1 | 4 | 64.4 | 8 | 12.00 | 16.43 | -27% | 2.74 | 11.1 | accelerating | 0.007 | 5.18-23.64 | 0.000 | 180.0 | 36 | 8 | 36 | — | 0.1897 | 0.3481 | 0.0552 |
| 41186 | zubin | Zubin | shots | platform-encoded-source | 57.94 | 1920x1080 | 29.970 | 10.41 | 71.9 | 4 | 69.0 | 15 | 22.50 | 25.89 | -13% | 1.89 | 0.0 | accelerating | 0.020 | 12.59-37.11 | 0.000 | 63.5 | 29 | 15 | 29 | — | 0.4463 | 0.4962 | 0.0845 |
| 41187 | rob | Rob | shots | platform-encoded-source | 119.42 | 1920x1080 | 29.970 | 10.43 | 148.5 | 4 | 33.5 | 16 | 24.00 | 22.11 | +9% | 2.07 | 2.2 | steady | 0.027 | 13.72-38.97 | 0.000 | 111.0 | 28 | 16 | 28 | — | 0.3431 | 0.4293 | 0.0858 |
| 41190 | a-who-knew-carol | A Who Knew Carol | shots | platform-encoded-source | 138.77 | 1920x1080 | 29.970 | 10.44 | 172.6 | 4 | 28.8 | 1 | 1.50 | 0.86 | +73% | 55.56 | 0.0 | — | 0.006 | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.1506 | 0.3208 | 0.0969 |
| 41191 | favorite-tia | Favorite Tía | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 4 | 12.00 | 13.96 | -14% | 3.70 | 0.0 | accelerating | 0.006 | 3.27-30.72 | 0.000 | 140.0 | 18 | 4 | 18 | — | 0.1733 | 0.3039 | 0.0623 |
| 41192 | dead-island-cinematic-debut-trailer | Dead Island Cinematic Debut Trailer | shots | 720p-web-rendition | 182.63 | 1280x720 | 30.000 | 2.52 | 54.8 | 4 | 21.9 | 8 | 12.00 | 14.78 | -19% | 2.28 | 4.3 | decelerating | 0.029 | 0.86-31.02 | 0.000 | 68.0 | 36 | 8 | 36 | low-coverage | 0.1499 | 0.3009 | 0.1138 |
| 41193 | car-4 | Car | shots | platform-encoded-source | 21.35 | 1280x720 | 29.970 | 3.11 | 7.9 | 1 | 46.8 | 1 | 6.00 | 8.43 | -29% | 5.17 | 25.0 | accelerating | 0.020 | 0.15-33.43 | — | — | 10 | 1 | 10 | short-sample | 0.1971 | 0.4423 | 0.0781 |
| 41194 | monsters | Monsters | shots | platform-encoded-source | 61.59 | 1280x720 | 29.970 | 3.00 | 22.0 | 4 | 64.9 | 13 | 19.50 | 19.48 | +0% | 1.94 | 4.8 | decelerating | 0.005 | 10.38-33.35 | 0.000 | 73.0 | 31 | 13 | 31 | — | 0.3429 | 0.1813 | 0.0585 |
| 41195 | cartoon | Cartoon | shots | platform-encoded-source | 60.16 | 1280x720 | 29.970 | 3.12 | 22.4 | 4 | 66.5 | 22 | 33.00 | 33.91 | -3% | 1.33 | 8.6 | decelerating | 0.016 | 20.50-50.22 | 0.136 | 51.0 | 25 | 19 | 25 | — | 0.3366 | 0.2183 | 0.0973 |
| 41196 | snowy-roads-are-scary-ghost | Snowy Roads Are Scary / Ghost | shots | platform-encoded-source | 41.13 | 1920x1080 | 29.970 | 10.40 | 51.0 | 3 | 72.9 | 3 | 6.00 | 4.38 | +37% | 11.42 | 0.0 | steady | 0.006 | 1.24-17.53 | 0.000 | 372.0 | 30 | 3 | 30 | — | 0.0764 | 0.0816 | 0.0538 |
| 41197 | baby-doll | Baby Doll | shots | platform-encoded-source | 31.13 | 1280x720 | 29.970 | 3.09 | 11.5 | 2 | 64.2 | 8 | 24.00 | 23.13 | +4% | 2.20 | 0.0 | decelerating | 0.015 | 10.36-47.29 | 0.000 | 68.0 | 14 | 8 | 14 | — | 0.5192 | 0.1947 | 0.0452 |
| 41199 | the-spirit-of-dark-and-lonely-water | The Spirit of Dark and Lonely Water | shots | platform-encoded-source | 88.94 | 1920x1080 | 29.970 | 10.43 | 110.5 | 4 | 45.0 | 3 | 4.50 | 8.10 | -44% | 4.50 | 0.0 | decelerating | 0.026 | 0.55-14.06 | 0.000 | 346.5 | 41 | 3 | 41 | — | 0.3011 | 0.2104 | 0.1138 |
| 41202 | come-back-to-firefox | Come Back to Firefox | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.44 | 74.8 | 4 | 66.5 | 24 | 36.00 | 31.94 | +13% | 1.23 | 12.1 | accelerating | 0.028 | 18.22-60.14 | 0.250 | 37.0 | 25 | 19 | 25 | — | 0.4543 | 0.3696 | 0.1259 |
| 41204 | hara-and-the-hare | Hara and the Hare | shots | platform-encoded-source | 137.69 | 1920x1080 | 29.970 | 10.45 | 171.5 | 4 | 29.1 | 7 | 10.50 | 11.33 | -7% | 1.43 | 7.4 | decelerating | 0.005 | 2.39-24.87 | 0.000 | 144.5 | 37 | 7 | 37 | — | 0.1477 | 0.5255 | 0.0360 |
| 41205 | jen-beatties-story-to-screen-for-breast-cancer-awareness | Jen Beattie’s Story to Screen for Breast Cancer Awareness | shots | platform-encoded-source | 39.64 | 1920x1080 | 29.970 | 10.40 | 49.1 | 3 | 75.7 | 45 | 90.00 | 78.71 | +14% | 0.43 | 50.9 | decelerating | 0.060 | 62.59-124.24 | 0.622 | 16.5 | 9 | 24 | 9 | burst-heavy | 0.3370 | 0.2011 | 0.1025 |
| 41206 | hear-it-to-believe-it | Hear It To Believe It | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.41 | 37.3 | 2 | 66.5 | 23 | 69.00 | 65.82 | +5% | 0.78 | 11.8 | accelerating | 0.031 | 43.74-103.53 | 0.087 | 23.5 | 4 | 18 | 4 | sparse-delta-basis | 0.3291 | 0.2981 | 0.1686 |
| 41207 | its-all-in-the-delivery | It's All In The Delivery | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.41 | 37.3 | 2 | 66.5 | 10 | 30.00 | 29.92 | +0% | 1.84 | 0.0 | decelerating | 0.052 | 14.39-55.17 | 0.000 | 50.0 | 12 | 10 | 12 | — | 0.2600 | 0.3796 | 0.1518 |
| 41208 | at-americas-table-since-1917 | At America’s Table Since 1917 | shots | platform-encoded-source | 120.17 | 1920x1080 | 29.970 | 10.43 | 149.5 | 4 | 33.3 | 15 | 22.50 | 22.97 | -2% | 2.10 | 2.1 | steady | 0.019 | 11.16-39.23 | 0.000 | 62.0 | 30 | 14 | 30 | — | 0.2708 | 0.4879 | 0.0998 |
| 41209 | beds-1 | Beds | shots | platform-encoded-source | 90.12 | 1280x720 | 29.970 | 3.14 | 33.7 | 4 | 44.4 | 28 | 42.00 | 44.61 | -6% | 1.25 | 7.4 | steady | 0.083 | 27.91-60.70 | 0.000 | 46.0 | 18 | 26 | 18 | — | 0.4661 | 0.2377 | 0.0602 |
| 41213 | group-hangouts | Group Hangouts | shots | platform-encoded-source | 82.75 | 1920x1080 | 29.970 | 10.43 | 102.9 | 4 | 48.3 | 23 | 34.50 | 29.73 | +16% | 1.42 | 9.5 | decelerating | 0.019 | 21.87-51.77 | 0.087 | 37.0 | 24 | 20 | 24 | — | 0.3206 | 0.3483 | 0.1447 |
| 41214 | the-best-part-of-tinder-isnt-on-tinder | The best part of Tinder isn’t on Tinder | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.42 | 37.4 | 2 | 66.5 | 51 | 153.00 | 175.53 | -13% | 0.17 | 71.9 | decelerating | 0.077 | 113.92-201.17 | 0.608 | 7.0 | 0 | 22 | 0 | burst-heavy, no-delta-basis, sparse-delta-basis | 0.3102 | 0.4686 | — |
| 41215 | tinder-irl-events-video | Tinder IRL Events Video | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.52 | 75.3 | 4 | 66.6 | 31 | 46.50 | 49.96 | -7% | 0.70 | 37.3 | accelerating | 0.030 | 31.12-66.62 | 0.290 | 31.0 | 21 | 23 | 21 | — | 0.1387 | 0.5079 | 0.0784 |
| 41216 | pencil | Pencil | shots | platform-encoded-source | 40.64 | 1920x1080 | 29.970 | 10.40 | 50.4 | 3 | 73.8 | 0 | 0.00 | 0.00 | — | 40.64 | 0.0 | — | 0.001 | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.3850 | 0.3372 | 0.0260 |
| 41217 | lumi-meet-lumi | Lumi Meet Lumi | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.42 | 74.6 | 4 | 66.6 | 12 | 18.00 | 16.98 | +6% | 3.09 | 0.0 | accelerating | 0.012 | 9.30-31.44 | 0.000 | 115.0 | 32 | 12 | 32 | — | 0.2391 | 0.4037 | 0.0750 |
| 41218 | miami-beach-lost-found | Miami Beach: Lost & Found | shots | platform-encoded-source | 130.18 | 1920x1080 | 29.970 | 10.43 | 161.9 | 4 | 30.7 | 22 | 33.00 | 28.12 | +17% | 1.80 | 16.1 | accelerating | 0.025 | 16.67-55.49 | 0.318 | 54.0 | 27 | 17 | 27 | — | 0.5358 | 0.3045 | 0.0789 |
| 41219 | the-agency | The Agency | shots | platform-encoded-source | 113.92 | 1920x1080 | 29.970 | 10.47 | 142.2 | 4 | 35.1 | 18 | 27.00 | 27.39 | -1% | 1.80 | 5.7 | steady | 0.028 | 5.62-57.46 | 0.000 | 38.0 | 28 | 16 | 28 | — | 0.3632 | 0.2694 | 0.1482 |
| 41220 | maison-margiela-x-gentle-monster | Maison Margiela x Gentle Monster | shots | platform-encoded-source | 82.05 | 1920x1080 | 29.970 | 10.43 | 102.0 | 4 | 48.8 | 26 | 39.00 | 46.07 | -15% | 0.78 | 26.6 | decelerating | 0.057 | 15.08-71.09 | 0.000 | 24.0 | 23 | 21 | 23 | — | 0.3158 | 0.3262 | 0.1087 |
| 41221 | family-4 | Family | shots | platform-encoded-source | 128.45 | 1920x1080 | 29.970 | 10.47 | 160.3 | 4 | 31.1 | 8 | 12.00 | 16.35 | -27% | 2.72 | 0.0 | decelerating | 0.015 | 5.18-23.64 | 0.000 | 219.0 | 36 | 8 | 36 | — | 0.1859 | 0.3966 | 0.0926 |
| 41222 | it-gets-worse | It Gets Worse | shots | platform-encoded-source | 165.46 | 1920x1080 | 29.970 | 10.44 | 205.9 | 4 | 24.2 | 9 | 13.50 | 23.57 | -43% | 1.10 | 30.3 | accelerating | 0.017 | 6.17-25.63 | 0.000 | 127.5 | 36 | 8 | 36 | low-coverage | 0.2127 | 0.4705 | 0.0977 |
| 41223 | love-is-a-gift-you-me | Love is a Gift - You & Me | shots | platform-encoded-source | 121.64 | 1920x1080 | 29.970 | 10.45 | 151.5 | 4 | 32.9 | 22 | 33.00 | 20.22 | +63% | 1.69 | 14.3 | accelerating | 0.027 | 13.58-59.74 | 0.273 | 38.0 | 27 | 17 | 27 | — | 0.2239 | 0.3615 | 0.1263 |
| 41224 | mazda | Mazda | shots | platform-encoded-source | 43.61 | 1920x1080 | 29.970 | 10.55 | 54.9 | 3 | 68.8 | 20 | 40.00 | 33.02 | +21% | 1.13 | 12.0 | decelerating | 0.026 | 24.43-61.78 | 0.150 | 33.0 | 17 | 16 | 17 | — | 0.2375 | 0.3256 | 0.1580 |
| 41226 | whos-afraid-of-their-credit-score | Who’s Afraid of Their Credit Score? | shots | platform-encoded-source | 60.18 | 1920x1080 | 29.970 | 10.46 | 75.0 | 4 | 66.5 | 12 | 18.00 | 18.94 | -5% | 2.27 | 15.0 | accelerating | 0.026 | 7.15-34.77 | 0.167 | 85.0 | 33 | 11 | 33 | — | 0.1456 | 0.4387 | 0.1071 |
| 41227 | dance-video | Dance Video | shots | platform-encoded-source | 185.22 | 1920x1080 | 29.970 | 10.45 | 230.6 | 4 | 21.6 | 33 | 49.50 | 39.85 | +24% | 1.17 | 11.3 | steady | 0.030 | 28.30-77.01 | 0.364 | 34.5 | 18 | 26 | 18 | low-coverage | 0.3712 | 0.3455 | 0.1556 |
| 41229 | drawing-prada | Drawing Prada | shots | platform-encoded-source | 54.46 | 1920x1080 | 29.970 | 10.41 | 67.6 | 4 | 73.4 | 22 | 33.00 | 30.85 | +7% | 1.67 | 0.0 | decelerating | 0.016 | 20.68-49.96 | 0.000 | 50.0 | 22 | 22 | 22 | — | 0.4069 | 0.3070 | 0.0850 |
| 41231 | a-time-to-embrace | A Time To Embrace | shots | platform-encoded-source | 58.11 | 1920x1080 | 29.970 | 10.42 | 72.2 | 4 | 68.8 | 23 | 34.50 | 27.88 | +24% | 1.72 | 14.3 | steady | 0.014 | 21.87-51.77 | 0.130 | 54.5 | 24 | 20 | 24 | — | 0.3246 | 0.2460 | 0.0955 |
| 41234 | church-of-sound | Church Of Sound | shots | platform-encoded-source | 185.02 | 1920x1080 | 29.970 | 10.44 | 230.2 | 4 | 21.6 | 27 | 40.50 | 33.40 | +21% | 1.17 | 28.8 | steady | 0.016 | 20.43-67.27 | 0.222 | 25.5 | 25 | 19 | 25 | low-coverage | 0.2891 | 0.3596 | 0.0634 |
| 41236 | you-will-die | You Will Die | shots | platform-encoded-source | 84.48 | 1920x1080 | 29.970 | 10.42 | 105.0 | 4 | 47.3 | 5 | 7.50 | 12.07 | -38% | 2.90 | 0.0 | steady | 0.007 | 0.70-20.92 | 0.000 | 68.0 | 39 | 5 | 39 | — | 0.2210 | 0.3830 | 0.0463 |
| 41237 | i-wish-i-was-you | I Wish I Was You | shots | platform-encoded-source | 90.05 | 1920x1080 | 29.970 | 10.43 | 111.9 | 4 | 44.4 | 15 | 22.50 | 21.32 | +6% | 2.67 | 0.0 | accelerating | 0.008 | 12.59-37.11 | 0.000 | 74.0 | 29 | 15 | 29 | — | 0.2812 | 0.2519 | 0.0412 |
| 41240 | mission-assist-auto-check | Mission Assist: Auto Check | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.31 | 18.5 | 1 | 66.4 | 3 | 18.00 | 15.93 | +13% | 2.95 | 0.0 | steady | 0.003 | 3.71-52.60 | 0.000 | 60.0 | 8 | 3 | 8 | short-sample | 0.3632 | 0.2495 | 0.0334 |
| 41241 | mission-assist-auto-30 | Mission Assist: Auto (:30) | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 6 | 18.00 | 27.93 | -36% | 1.37 | 0.0 | decelerating | 0.007 | 6.61-39.18 | 0.000 | 80.0 | 16 | 6 | 16 | — | 0.3466 | 0.2640 | 0.0207 |
| 41242 | unexpected-guests | Unexpected Guests | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.39 | 37.2 | 2 | 66.5 | 12 | 36.00 | 29.94 | +20% | 1.87 | 18.8 | decelerating | 0.012 | 18.60-62.88 | 0.333 | 53.0 | 13 | 9 | 13 | — | 0.3005 | 0.4680 | 0.0892 |
| 41243 | ignored-to-adored | Ignored to Adored | shots | platform-encoded-source | 111.08 | 1920x1080 | 29.970 | 10.44 | 138.3 | 4 | 36.0 | 10 | 15.00 | 16.20 | -7% | 2.07 | 0.0 | decelerating | 0.018 | 0.00-41.40 | 0.000 | 35.0 | 34 | 10 | 34 | — | 0.1548 | 0.1208 | 0.0694 |
| 41244 | is-your-door-in-the-draw | Is your door in the draw? | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.43 | 74.7 | 4 | 66.6 | 12 | 18.00 | 15.99 | +13% | 2.47 | 5.9 | decelerating | 0.018 | 9.30-31.44 | 0.167 | 74.0 | 33 | 11 | 33 | — | 0.4147 | 0.3842 | 0.1466 |
| 41245 | meet-hamface | Meet Hamface | shots | platform-encoded-source | 77.97 | 1920x1080 | 29.970 | 10.49 | 97.5 | 4 | 51.3 | 12 | 18.00 | 17.70 | +2% | 3.17 | 0.0 | steady | 0.006 | 9.30-31.44 | 0.000 | 105.0 | 33 | 11 | 33 | — | 0.1376 | 0.5253 | 0.0442 |
| 41246 | 100-real-with-pamela-anderson | 100% Real with Pamela Anderson | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.41 | 74.6 | 4 | 66.5 | 24 | 36.00 | 41.92 | -14% | 0.57 | 46.5 | — | 0.022 | 0.00-86.03 | 0.500 | 24.0 | 29 | 15 | 29 | — | 0.7255 | 0.1472 | 0.0837 |
| 41247 | the-wrong-address | The Wrong Address | shots | platform-encoded-source | 180.05 | 1920x1080 | 29.970 | 10.44 | 224.1 | 4 | 22.2 | 11 | 16.50 | 16.66 | -1% | 1.80 | 0.0 | decelerating | 0.013 | 0.00-43.23 | 0.000 | 42.5 | 33 | 11 | 33 | low-coverage | 0.1759 | 0.3919 | 0.0591 |
| 41248 | helping-christmas-feel-magic | Helping Christmas Feel Magic | shots | platform-encoded-source | 90.09 | 1920x1080 | 29.970 | 10.43 | 112.0 | 4 | 44.4 | 24 | 36.00 | 33.97 | +6% | 1.47 | 3.8 | steady | 0.035 | 21.70-55.42 | 0.083 | 45.0 | 20 | 24 | 20 | — | 0.1994 | 0.5450 | 0.0598 |
| 41249 | tales-of-argos-past | Tales of Argos Past | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.42 | 74.6 | 4 | 66.6 | 21 | 31.50 | 32.97 | -4% | 1.35 | 17.6 | accelerating | 0.031 | 14.19-55.51 | 0.238 | 36.5 | 27 | 17 | 27 | — | 0.2976 | 0.3678 | 0.0937 |
| 41250 | big-delivery | Big Delivery | shots | platform-encoded-source | 120.04 | 1920x1080 | 29.970 | 10.44 | 149.4 | 4 | 33.3 | 14 | 21.00 | 29.49 | -29% | 1.70 | 11.7 | accelerating | 0.026 | 11.26-35.57 | 0.143 | 65.0 | 31 | 13 | 31 | — | 0.2620 | 0.3655 | 0.1071 |
| 41253 | skimmed | Skimmed | shots | platform-encoded-source | 36.52 | 1920x1080 | 29.970 | 10.43 | 45.4 | 3 | 82.1 | 16 | 32.00 | 29.57 | +8% | 1.03 | 0.0 | accelerating | 0.020 | 13.86-58.41 | 0.000 | 30.0 | 20 | 13 | 20 | — | 0.4925 | 0.3514 | 0.0832 |
| 41254 | we-are | WE ARE | shots | platform-encoded-source | 45.06 | 1920x1080 | 29.970 | 10.45 | 56.1 | 4 | 88.8 | 69 | 103.50 | 95.88 | +8% | 0.33 | 56.2 | steady | 0.119 | 56.27-160.01 | 0.565 | 10.0 | 8 | 36 | 8 | burst-heavy | 0.4398 | 0.4290 | 0.0748 |
| 41255 | judger-in-law | Judger In Law | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 12 | 36.00 | 31.91 | +13% | 1.70 | 0.0 | accelerating | 0.019 | 18.60-62.88 | 0.000 | 39.0 | 10 | 12 | 10 | — | 0.1803 | 0.5149 | 0.0340 |
| 41256 | together-1 | Together | shots | platform-encoded-source | 90.05 | 1920x1080 | 29.970 | 10.43 | 111.9 | 4 | 44.4 | 19 | 28.50 | 27.99 | +2% | 1.80 | 2.3 | accelerating | 0.014 | 17.16-44.51 | 0.000 | 54.5 | 25 | 19 | 25 | — | 0.3047 | 0.2658 | 0.0780 |
| 41257 | lets-dance-holiday | Let's Dance Holiday | shots | platform-encoded-source | 71.47 | 1920x1080 | 29.970 | 10.42 | 88.8 | 4 | 56.0 | 26 | 39.00 | 30.22 | +29% | 1.77 | 16.2 | accelerating | 0.028 | 25.48-57.14 | 0.269 | 38.0 | 23 | 21 | 23 | — | 0.2524 | 0.5066 | 0.1143 |
| 41258 | saudi-national-day-96 | Saudi National Day 96 | shots | platform-encoded-source | 125.48 | 1920x1080 | 29.970 | 10.43 | 156.1 | 4 | 31.9 | 29 | 43.50 | 41.60 | +5% | 0.87 | 30.7 | accelerating | 0.037 | 19.10-75.73 | 0.172 | 26.0 | 21 | 23 | 21 | — | 0.1977 | 0.3514 | 0.0673 |
| 41259 | always-been-here | Always Been Here | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.43 | 37.4 | 2 | 66.5 | 8 | 24.00 | 21.94 | +9% | 1.80 | 33.3 | accelerating | 0.051 | 10.36-47.29 | 0.500 | 35.0 | 17 | 5 | 17 | — | 0.2129 | 0.3421 | 0.1712 |
| 41260 | megan-thee-stallion-hottieween-trailer | Megan Thee Stallion Hottieween Trailer | shots | platform-encoded-source | 152.87 | 1920x1080 | 29.970 | 10.46 | 190.6 | 4 | 26.2 | 4 | 6.00 | 26.30 | -77% | 0.97 | 32.4 | accelerating | 0.021 | 0.00-19.24 | 0.000 | 95.0 | 40 | 4 | 40 | — | 0.1134 | 0.0000 | 0.0572 |
| 41261 | gloria-and-pickles | Gloria and Pickles | shots | 720p-web-rendition | 180.05 | 1280x720 | 25.000 | 2.76 | 59.3 | 4 | 22.2 | 16 | 24.00 | 27.66 | -13% | 1.52 | 2.4 | decelerating | 0.029 | 13.72-38.97 | 0.000 | 42.0 | 28 | 16 | 28 | low-coverage | 0.1782 | 0.4161 | 0.0908 |
| 41263 | in-the-way | In the Way | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.44 | 37.5 | 2 | 66.5 | 13 | 39.00 | 33.91 | +15% | 1.28 | 0.0 | decelerating | 0.018 | 20.77-66.69 | 0.000 | 38.5 | 9 | 13 | 9 | — | 0.2718 | 0.3020 | 0.0592 |
| 41264 | ahem | Ahem | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.53 | 37.8 | 2 | 66.5 | 5 | 15.00 | 13.96 | +7% | 3.44 | 0.0 | decelerating | 0.003 | 4.87-35.00 | 0.000 | 131.5 | 17 | 5 | 17 | — | 0.2650 | 0.3495 | 0.0713 |
| 41265 | its-about-time-1 | It's About Time | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.40 | 37.3 | 2 | 66.5 | 3 | 9.00 | 9.98 | -10% | 4.94 | 0.0 | accelerating | 0.017 | 1.86-26.30 | 0.000 | 290.0 | 19 | 3 | 19 | — | 0.3005 | 0.3554 | 0.1378 |
| 41266 | the-king-of-clay | The King of Clay | shots | platform-encoded-source | 42.77 | 1920x1080 | 29.970 | 10.40 | 53.1 | 3 | 70.1 | 24 | 48.00 | 40.68 | +18% | 1.12 | 13.3 | decelerating | 0.062 | 30.75-71.42 | 0.167 | 30.0 | 13 | 20 | 13 | — | 0.3462 | 0.5013 | 0.0613 |
| 41267 | the-making-of-lets-get-fuzzy | The Making of Let's Get Fuzzy | shots | platform-encoded-source | 30.93 | 1920x1080 | 29.970 | 10.44 | 38.5 | 2 | 64.7 | 28 | 84.00 | 79.53 | +6% | 0.62 | 11.9 | decelerating | 0.094 | 55.82-121.40 | 0.071 | 18.0 | 2 | 20 | 2 | sparse-delta-basis | 0.3400 | 0.3252 | 0.0736 |
| 41268 | lets-get-fuzzy | Let's Get Fuzzy | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.43 | 74.7 | 4 | 66.5 | 15 | 22.50 | 18.96 | +19% | 2.02 | 0.0 | decelerating | 0.018 | 12.59-37.11 | 0.000 | 70.0 | 29 | 15 | 29 | — | 0.1989 | 0.5741 | 0.0923 |
| 41269 | spiris-pet-store | Spiris - Pet Store | shots | platform-encoded-source | 29.97 | 1920x1080 | 29.970 | 10.40 | 37.1 | 2 | 66.7 | 9 | 27.00 | 24.02 | +12% | 1.80 | 0.0 | decelerating | 0.014 | 12.35-51.25 | 0.000 | 76.5 | 13 | 9 | 13 | — | 0.2885 | 0.4000 | 0.0383 |
| 41270 | spiris-climber | Spiris - Climber | shots | platform-encoded-source | 29.97 | 1920x1080 | 29.970 | 10.38 | 37.1 | 2 | 66.7 | 8 | 24.00 | 18.02 | +33% | 2.89 | 0.0 | steady | 0.011 | 10.36-47.29 | 0.000 | 44.0 | 14 | 8 | 14 | — | 0.2996 | 0.2796 | 0.0329 |
| 41271 | unwrap-potential | Unwrap Potential | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.44 | 74.7 | 4 | 66.6 | 15 | 22.50 | 21.98 | +2% | 2.27 | 4.3 | accelerating | 0.018 | 11.16-39.23 | 0.000 | 54.5 | 29 | 15 | 29 | — | 0.1957 | 0.3825 | 0.0898 |
| 41272 | saving-tasting-time | Saving Tasting Time | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.39 | 37.2 | 2 | 66.5 | 5 | 15.00 | 15.97 | -6% | 2.64 | 11.1 | accelerating | 0.011 | 4.87-35.00 | 0.400 | 74.0 | 18 | 4 | 18 | — | 0.5254 | 0.2126 | 0.0829 |
| 41273 | holiday-gifting | Holiday Gifting | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.40 | 37.3 | 2 | 66.5 | 13 | 39.00 | 39.89 | -2% | 0.50 | 47.6 | decelerating | 0.016 | 20.77-66.69 | 0.615 | 8.5 | 15 | 7 | 15 | burst-heavy | 0.3250 | 0.4480 | 0.0891 |
| 41274 | a-warehouse-christmas | A Warehouse Christmas | shots | platform-encoded-source | 70.06 | 1920x1080 | 29.970 | 10.45 | 87.3 | 4 | 57.1 | 3 | 4.50 | 7.71 | -42% | 6.22 | 0.0 | accelerating | 0.011 | 0.55-14.06 | 0.000 | 488.0 | 41 | 3 | 41 | — | 0.3012 | 0.3560 | 0.1090 |
| 41275 | kira-needs-a-family | Kira Needs A Family | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.47 | 74.9 | 4 | 66.6 | 11 | 16.50 | 14.99 | +10% | 1.70 | 0.0 | decelerating | 0.006 | 0.00-43.23 | 0.000 | 48.0 | 34 | 10 | 34 | — | 0.1644 | 0.3083 | 0.0609 |
| 41276 | incredibly-generous-ice-cream | Incredibly Generous Ice Cream | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.41 | 74.6 | 4 | 66.5 | 1 | 1.50 | 1.00 | +50% | 30.06 | 0.0 | — | 0.002 | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.4194 | 0.2386 | 0.0390 |
| 41277 | mountain-3 | Mountain | shots | platform-encoded-source | 30.25 | 1920x1080 | 29.970 | 10.47 | 37.8 | 2 | 66.1 | 7 | 21.00 | 17.85 | +18% | 3.27 | 10.0 | decelerating | 0.004 | 8.44-43.27 | 0.000 | 105.0 | 15 | 7 | 15 | — | 0.4096 | 0.2486 | 0.0364 |
| 41278 | capy-cake | Capy Cake | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.67 | 19.2 | 1 | 66.4 | 0 | 0.00 | 0.00 | — | 15.06 | 0.0 | — | 0.001 | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.2399 | 0.5985 | 0.0178 |
| 41279 | flour-fail | Flour Fail | shots | platform-encoded-source | 5.06 | 1920x1080 | 29.970 | 10.86 | 6.5 | 1 | 79.1 | 0 | 0.00 | 0.00 | — | 5.06 | 0.0 | — | 0.004 | 0.00-55.34 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.3577 | 0.5438 | 0.0355 |
| 41280 | smoke-alarm | Smoke Alarm | shots | platform-encoded-source | 5.06 | 1920x1080 | 29.970 | 10.58 | 6.4 | 1 | 79.1 | 0 | 0.00 | 0.00 | — | 5.06 | 0.0 | — | 0.010 | 0.00-55.34 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.3165 | 0.5383 | 0.1078 |
| 41281 | burnt-bits | Burnt Bits | shots | platform-encoded-source | 10.05 | 1920x1080 | 29.970 | 10.41 | 12.5 | 1 | 89.6 | 0 | 0.00 | 0.00 | — | 10.05 | 0.0 | — | 0.001 | 0.00-24.59 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.3227 | 0.5500 | 0.0082 |
| 41282 | tin-troubles | Tin Troubles | shots | platform-encoded-source | 5.06 | 1920x1080 | 29.970 | 10.49 | 6.3 | 1 | 79.1 | 0 | 0.00 | 0.00 | — | 5.06 | 0.0 | — | 0.001 | 0.00-55.34 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.3113 | 0.5865 | 0.0222 |
| 41283 | the-prize | The Prize | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.41 | 74.6 | 4 | 66.5 | 24 | 36.00 | 32.94 | +9% | 1.42 | 2.9 | decelerating | 0.051 | 23.07-53.57 | 0.000 | 45.0 | 20 | 24 | 20 | — | 0.4601 | 0.2967 | 0.0952 |
| 41284 | all-of-christmas-at-asda-price-boom-decorating | All of Christmas at Asda Price. Boom. - Decorating | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.53 | 37.7 | 2 | 66.5 | 15 | 45.00 | 41.92 | +7% | 0.77 | 36.4 | accelerating | 0.047 | 25.19-74.22 | 0.333 | 25.0 | 12 | 10 | 12 | — | 0.2587 | 0.4171 | 0.1443 |
| 41285 | all-of-christmas-at-asda-price-boom-dinner-table | All of Christmas at Asda Price. Boom. - Dinner Table | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.43 | 37.4 | 2 | 66.5 | 9 | 27.00 | 17.96 | +50% | 1.77 | 10.0 | accelerating | 0.025 | 12.35-51.25 | 0.222 | 53.0 | 14 | 8 | 14 | — | 0.2144 | 0.4878 | 0.1153 |
| 41286 | no-pet-beauty-standard | No Pet Beauty Standard | shots | platform-encoded-source | 173.65 | 1920x1080 | 29.970 | 10.44 | 216.1 | 4 | 23.0 | 12 | 18.00 | 20.39 | -12% | 2.64 | 0.0 | accelerating | 0.011 | 9.30-31.44 | 0.000 | 88.0 | 32 | 12 | 32 | low-coverage | 0.3760 | 0.2619 | 0.0424 |
| 41287 | for-gifts-theyll-really-love | For Gifts They'll Really Love | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.48 | 75.0 | 4 | 66.6 | 18 | 27.00 | 27.98 | -3% | 1.74 | 6.9 | accelerating | 0.019 | 10.88-49.97 | 0.000 | 52.0 | 27 | 17 | 27 | — | 0.2292 | 0.4826 | 0.1027 |
| 41289 | kfc-x-marvel-studios-avengers-doomsday | KFC x Marvel Studios’ “Avengers: Doomsday” | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.42 | 74.6 | 4 | 66.6 | 5 | 7.50 | 8.99 | -17% | 4.32 | 0.0 | accelerating | 0.011 | 0.70-20.92 | 0.000 | 145.0 | 39 | 5 | 39 | — | 0.2175 | 0.1576 | 0.0823 |
| 41290 | holiday-front-yards | Holiday Front Yards | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.39 | 37.3 | 2 | 66.5 | 13 | 39.00 | 39.89 | -2% | 1.30 | 0.0 | decelerating | 0.026 | 20.77-66.69 | 0.000 | 38.5 | 9 | 13 | 9 | — | 0.3666 | 0.3089 | 0.0995 |
| 41291 | wrapped-in-burberry | Wrapped in Burberry | shots | platform-encoded-source | 90.05 | 1920x1080 | 29.970 | 10.44 | 112.1 | 4 | 44.4 | 33 | 49.50 | 45.98 | +8% | 1.03 | 20.0 | decelerating | 0.043 | 33.46-70.31 | 0.242 | 32.0 | 20 | 24 | 20 | — | 0.2071 | 0.3946 | 0.0998 |
| 41292 | here-for-all-of-it | Here for All of It | shots | platform-encoded-source | 94.14 | 1920x1080 | 29.970 | 10.44 | 117.1 | 4 | 42.5 | 13 | 19.50 | 19.12 | +2% | 1.00 | 41.9 | decelerating | 0.032 | 5.57-40.65 | 0.615 | 22.5 | 37 | 7 | 37 | burst-heavy | 0.2503 | 0.4359 | 0.1707 |
| 41293 | here-for-all-of-it-behind-the-scenes | Here for All of It (Behind the Scenes) | shots | platform-encoded-source | 55.21 | 1920x1080 | 29.970 | 10.44 | 68.7 | 4 | 72.4 | 35 | 52.50 | 42.38 | +24% | 1.12 | 17.5 | decelerating | 0.053 | 36.57-73.01 | 0.229 | 33.5 | 17 | 27 | 17 | — | 0.2800 | 0.4096 | 0.1730 |
| 41294 | bold-tastes-of-tokyo | Bold Tastes Of Tokyo | shots | platform-encoded-source | 90.60 | 1920x1080 | 29.970 | 10.43 | 112.6 | 4 | 44.1 | 24 | 36.00 | 82.78 | -57% | 0.18 | 71.4 | accelerating | 0.061 | 9.42-72.09 | 0.500 | 17.0 | 27 | 17 | 27 | — | 0.2864 | 0.4742 | 0.1417 |
| 41295 | warm-wishes | Warm Wishes | shots | platform-encoded-source | 90.09 | 1920x1080 | 29.970 | 10.46 | 112.4 | 4 | 44.4 | 17 | 25.50 | 24.64 | +3% | 1.82 | 5.3 | decelerating | 0.013 | 10.08-47.70 | 0.000 | 57.5 | 28 | 16 | 28 | — | 0.3538 | 0.3529 | 0.0726 |
| 41296 | so-much-choice-one-way-to-pay | So Much Choice, One Way to Pay | shots | platform-encoded-source | 39.89 | 1920x1080 | 29.970 | 10.40 | 49.5 | 3 | 75.2 | 23 | 46.00 | 42.11 | +9% | 1.07 | 3.4 | decelerating | 0.022 | 29.16-69.02 | 0.000 | 32.5 | 13 | 20 | 13 | — | 0.2576 | 0.3121 | 0.0476 |
| 41297 | the-lego-holiday-workshop-2026 | The LEGO Holiday Workshop 2026 | shots | platform-encoded-source | 74.05 | 1920x1080 | 29.970 | 10.42 | 92.0 | 4 | 54.0 | 47 | 70.50 | 64.01 | +10% | 0.20 | 56.2 | decelerating | 0.041 | 32.35-117.94 | 0.681 | 6.5 | 19 | 25 | 19 | burst-heavy | 0.3028 | 0.4993 | 0.1966 |
| 41299 | whats-new-anyway | What's New, Anyway? | shots | platform-encoded-source | 132.71 | 1920x1080 | 29.970 | 10.44 | 165.1 | 4 | 30.1 | 14 | 21.00 | 19.44 | +8% | 2.32 | 0.0 | decelerating | 0.008 | 8.20-40.15 | 0.000 | 67.0 | 30 | 14 | 30 | — | 0.2393 | 0.3061 | 0.0624 |
| 41300 | change-me | Change Me | shots | platform-encoded-source | 150.25 | 1920x1080 | 29.970 | 10.44 | 186.9 | 4 | 26.6 | 5 | 7.50 | 12.78 | -41% | 2.84 | 0.0 | steady | 0.012 | 2.44-17.50 | 0.000 | 658.0 | 39 | 5 | 39 | — | 0.1397 | 0.2982 | 0.0461 |
| 41301 | workshops | Workshops | shots | platform-encoded-source | 57.05 | 1920x1080 | 29.970 | 10.44 | 71.0 | 4 | 70.1 | 23 | 34.50 | 36.81 | -6% | 1.28 | 0.0 | steady | 0.013 | 17.10-58.29 | 0.000 | 45.5 | 21 | 23 | 21 | — | 0.2429 | 0.4814 | 0.0456 |
| 41302 | december-to-remember-childs-eyes | December to Remember - Child's Eyes | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.41 | 74.6 | 4 | 66.5 | 17 | 25.50 | 25.95 | -2% | 1.84 | 3.7 | steady | 0.029 | 14.85-40.83 | 0.000 | 53.0 | 27 | 17 | 27 | — | 0.1907 | 0.3330 | 0.0924 |
| 41303 | december-to-remember-snowball | December to Remember - Snowball | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.31 | 18.5 | 1 | 66.4 | 7 | 42.00 | 35.85 | +17% | 1.27 | 0.0 | decelerating | 0.035 | 16.89-86.54 | 0.000 | 30.5 | 5 | 6 | 5 | short-sample, sparse-delta-basis | 0.2184 | 0.3277 | 0.1030 |
| 41304 | play-it-smart | Play it smart | shots | platform-encoded-source | 25.09 | 1920x1080 | 29.970 | 10.37 | 31.0 | 2 | 79.7 | 8 | 24.00 | 23.92 | +0% | 2.30 | 0.0 | steady | 0.013 | 10.36-47.29 | 0.000 | 69.0 | 14 | 8 | 14 | — | 0.2664 | 0.3115 | 0.0239 |
| 41305 | its-all-you-can-drink-about | It's All You Can Drink About | shots | platform-encoded-source | 60.01 | 1920x1080 | 29.970 | 10.44 | 74.7 | 4 | 66.7 | 34 | 51.00 | 41.99 | +21% | 0.40 | 62.8 | decelerating | 0.038 | 1.22-115.34 | 0.500 | 9.0 | 29 | 15 | 29 | — | 0.5047 | 0.4953 | 0.0817 |
| 41306 | the-greatest-2 | The Greatest | shots | platform-encoded-source | 78.12 | 1920x1080 | 29.970 | 10.42 | 97.1 | 4 | 51.2 | 29 | 43.50 | 26.88 | +62% | 0.10 | 69.4 | decelerating | 0.012 | 0.00-127.15 | 0.862 | 3.0 | 37 | 7 | 37 | burst-heavy | 0.0843 | 0.3063 | 0.0501 |
| 41308 | xbox-series-x-bite | XBOX Series X-Bite | shots | platform-encoded-source | 40.73 | 1920x1080 | 29.970 | 10.41 | 50.5 | 3 | 73.7 | 5 | 10.00 | 11.79 | -15% | 3.97 | 0.0 | accelerating | 0.012 | 3.25-23.34 | 0.000 | 112.0 | 28 | 5 | 28 | — | 0.0956 | 0.5835 | 0.0523 |
| 41309 | xbox-series-x-bite-behind-the-scenes | XBOX Series X-Bite - Behind The Scenes | shots | 720p-web-rendition | 50.94 | 1280x720 | 25.000 | 2.62 | 15.9 | 4 | 78.5 | 42 | 63.00 | 53.00 | +19% | 0.80 | 4.3 | decelerating | 0.089 | 45.40-85.16 | 0.048 | 20.0 | 7 | 37 | 7 | sparse-delta-basis | 0.3652 | 0.3346 | 0.0820 |
| 41311 | joy-delivered | Joy Delivered | shots | platform-encoded-source | 150.76 | 1920x1080 | 29.970 | 10.44 | 187.6 | 4 | 26.5 | 20 | 30.00 | 28.65 | +5% | 1.70 | 1.4 | decelerating | 0.018 | 18.32-46.33 | 0.100 | 46.0 | 25 | 19 | 25 | — | 0.2665 | 0.2621 | 0.0983 |
| 41314 | powered-by-terry | Powered By Terry | shots | platform-encoded-source | 98.73 | 1920x1080 | 29.970 | 10.44 | 122.8 | 4 | 40.5 | 13 | 19.50 | 34.64 | -44% | 0.17 | 65.5 | accelerating | 0.031 | 0.41-48.49 | 0.615 | 6.5 | 38 | 6 | 38 | burst-heavy | 0.1816 | 0.2329 | 0.1124 |
| 41315 | the-home-of-christmas | The Home of Christmas | shots | platform-encoded-source | 180.05 | 1920x1080 | 29.970 | 10.44 | 224.2 | 4 | 22.2 | 14 | 21.00 | 21.66 | -3% | 1.95 | 0.0 | accelerating | 0.009 | 11.26-35.57 | 0.000 | 53.0 | 30 | 14 | 30 | low-coverage | 0.1823 | 0.5705 | 0.0667 |
| 41316 | twas-the-season | Twas the Season | shots | platform-encoded-source | 96.41 | 1920x1080 | 29.970 | 10.43 | 119.8 | 4 | 41.5 | 0 | 0.00 | 0.00 | — | 96.41 | 0.0 | — | 0.009 | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.1283 | 0.3443 | 0.0758 |
| 41317 | thats-christmas-sorted | That's Christmas Sorted | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.42 | 74.6 | 4 | 66.6 | 11 | 16.50 | 14.99 | +10% | 3.35 | 0.0 | steady | 0.015 | 8.24-29.52 | 0.000 | 116.5 | 33 | 11 | 33 | — | 0.2857 | 0.3112 | 0.1390 |
| 41318 | from-crisis-to-home | From Crisis to Home | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.44 | 74.8 | 4 | 66.6 | 14 | 21.00 | 18.98 | +11% | 2.20 | 5.0 | decelerating | 0.023 | 11.48-35.23 | 0.000 | 68.0 | 31 | 13 | 31 | — | 0.3043 | 0.3098 | 0.1302 |
| 41319 | festive-crossing | Festive Crossing | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.45 | 74.8 | 4 | 66.6 | 20 | 30.00 | 27.98 | +7% | 1.80 | 0.0 | decelerating | 0.013 | 18.32-46.33 | 0.000 | 57.0 | 25 | 19 | 25 | — | 0.2876 | 0.3232 | 0.0586 |
| 41320 | create-the-new | Create the New | shots | platform-encoded-source | 116.05 | 1920x1080 | 29.970 | 10.44 | 144.5 | 4 | 34.5 | 33 | 49.50 | 58.42 | -15% | 0.55 | 45.6 | steady | 0.058 | 34.07-69.52 | 0.424 | 19.5 | 24 | 20 | 24 | — | 0.1318 | 0.4252 | 0.0953 |
| 41321 | its-that-simple | It's That Simple | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 5 | 15.00 | 13.96 | +7% | 2.65 | 0.0 | decelerating | 0.012 | 4.87-35.00 | 0.000 | 30.0 | 17 | 5 | 17 | — | 0.2467 | 0.4057 | 0.1775 |
| 41322 | the-art-of-arrival-henrik-lundqvist | The Art of Arrival (Henrik Lundqvist) | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 21 | 63.00 | 61.84 | +2% | 0.67 | 37.5 | decelerating | 0.037 | 39.00-96.30 | 0.524 | 19.5 | 10 | 12 | 10 | burst-heavy | 0.3619 | 0.0105 | 0.1454 |
| 41323 | the-art-of-arrival-sai-de-silva | The Art of Arrival (Sai De Silva) | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.56 | 37.9 | 2 | 66.5 | 17 | 51.00 | 47.87 | +7% | 0.57 | 44.0 | accelerating | 0.046 | 29.71-81.66 | 0.412 | 23.5 | 11 | 11 | 11 | — | 0.3239 | 0.0108 | 0.1565 |
| 41324 | the-art-of-arrival-roze-traore | The Art of Arrival (Roze Traore) | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.45 | 37.5 | 2 | 66.5 | 20 | 60.00 | 51.86 | +16% | 0.67 | 25.9 | decelerating | 0.050 | 36.65-92.67 | 0.250 | 16.0 | 9 | 13 | 9 | — | 0.3531 | 0.0113 | 0.1348 |
| 41325 | tronen | Tronen | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.39 | 37.2 | 2 | 66.5 | 1 | 3.00 | 2.00 | +50% | 15.03 | 0.0 | decelerating | 0.003 | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.1179 | 0.3180 | 0.0487 |
| 41326 | the-christmas-wish | The Christmas Wish | shots | platform-encoded-source | 50.05 | 1920x1080 | 29.970 | 10.49 | 62.6 | 4 | 79.9 | 15 | 22.50 | 19.18 | +17% | 2.27 | 0.0 | decelerating | 0.011 | 12.59-37.11 | 0.000 | 58.0 | 29 | 15 | 29 | — | 0.2201 | 0.6103 | 0.0774 |
| 41327 | christmas-made-just-right | Christmas Made Just Right | shots | platform-encoded-source | 90.05 | 1920x1080 | 29.970 | 10.48 | 112.5 | 4 | 44.4 | 23 | 34.50 | 32.65 | +6% | 1.40 | 4.0 | decelerating | 0.019 | 15.09-61.04 | 0.000 | 39.5 | 23 | 21 | 23 | — | 0.2189 | 0.2828 | 0.0740 |
| 41328 | the-fabric-of-your-town-unlocked | The Fabric of Your Town, Unlocked | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.41 | 74.6 | 4 | 66.5 | 15 | 22.50 | 21.96 | +2% | 1.70 | 13.0 | decelerating | 0.016 | 9.71-41.36 | 0.133 | 50.5 | 31 | 13 | 31 | — | 0.1874 | 0.2684 | 0.0809 |
| 41329 | time-to-shine | Time To Shine | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.52 | 75.3 | 4 | 66.6 | 26 | 39.00 | 40.96 | -5% | 1.33 | 4.8 | accelerating | 0.024 | 25.48-57.14 | 0.000 | 41.0 | 19 | 25 | 19 | — | 0.3533 | 0.3219 | 0.1062 |
| 41330 | park-2 | Park | shots | platform-encoded-source | 20.10 | 1920x1080 | 29.970 | 10.35 | 24.8 | 1 | 49.8 | 0 | 0.00 | 2.99 | -100% | 10.05 | 0.0 | — | 0.000 | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.3721 | 0.2059 | 0.0041 |
| 41331 | library-2 | Library | shots | platform-encoded-source | 23.08 | 1920x1080 | 29.970 | 10.37 | 28.5 | 2 | 86.6 | 1 | 3.00 | 2.60 | +15% | 11.54 | 0.0 | — | 0.000 | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.3370 | 0.1616 | 0.0066 |
| 41333 | the-foundation | THE FOUNDATION | shots | platform-encoded-source | 53.10 | 1920x1080 | 29.970 | 10.41 | 65.9 | 4 | 75.3 | 30 | 45.00 | 53.11 | -15% | 0.83 | 29.2 | accelerating | 0.041 | 25.24-70.97 | 0.167 | 30.0 | 20 | 24 | 20 | — | 0.3681 | 0.3028 | 0.0619 |
| 41335 | this-christmas-it-could-be-you | This Christmas It Could Be You | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.50 | 75.2 | 4 | 66.6 | 20 | 30.00 | 29.97 | +0% | 1.77 | 6.5 | steady | 0.020 | 18.32-46.33 | 0.100 | 53.0 | 26 | 18 | 26 | — | 0.4256 | 0.1817 | 0.0790 |
| 41336 | helvetet | Helvetet | shots | platform-encoded-source | 29.89 | 1920x1080 | 29.970 | 10.59 | 37.7 | 2 | 66.9 | 9 | 27.00 | 26.10 | +3% | 2.10 | 0.0 | steady | 0.033 | 12.35-51.25 | 0.000 | 75.5 | 13 | 9 | 13 | — | 0.1750 | 0.6481 | 0.0701 |
| 41337 | tidsresenaren | Tidsresenären | shots | platform-encoded-source | 29.95 | 1920x1080 | 29.970 | 10.44 | 37.3 | 2 | 66.8 | 2 | 6.00 | 6.01 | +0% | 3.15 | 0.0 | — | 0.016 | 0.73-21.67 | 0.000 | 75.0 | 20 | 2 | 20 | — | 0.1203 | 0.5699 | 0.0815 |
| 41339 | wwf-takes-you-on-a-speed-run-of-the-arctic-before-its-too-late | WWF takes you on a speed-run of the Arctic, before it’s too late. | shots | platform-encoded-source | 59.97 | 1920x1080 | 29.970 | 10.49 | 75.0 | 4 | 66.7 | 22 | 33.00 | 32.02 | +3% | 1.30 | 6.1 | decelerating | 0.031 | 16.67-55.49 | 0.000 | 44.0 | 23 | 21 | 23 | — | 0.4317 | 0.2293 | 0.0835 |
| 41340 | hypersleep | Hypersleep | shots | platform-encoded-source | 90.26 | 1920x1080 | 29.970 | 10.43 | 112.2 | 4 | 44.3 | 3 | 4.50 | 7.98 | -44% | 3.44 | 0.0 | accelerating | 0.009 | 0.55-14.06 | 0.000 | 272.0 | 41 | 3 | 41 | — | 0.1245 | 0.1812 | 0.0651 |
| 41341 | axolotl | Axolotl | shots | platform-encoded-source | 77.85 | 1920x1080 | 29.970 | 10.42 | 96.7 | 4 | 51.4 | 16 | 24.00 | 22.35 | +7% | 1.90 | 3.3 | decelerating | 0.036 | 13.72-38.97 | 0.000 | 54.0 | 28 | 16 | 28 | — | 0.2126 | 0.4148 | 0.0780 |
| 41342 | dawn-1 | Dawn | shots | platform-encoded-source | 82.97 | 1920x1080 | 29.970 | 10.43 | 103.1 | 4 | 48.2 | 5 | 7.50 | 7.23 | +4% | 3.60 | 0.0 | decelerating | 0.011 | 0.70-20.92 | 0.000 | 123.5 | 39 | 5 | 39 | — | 0.1554 | 0.2082 | 0.0471 |
| 41343 | dtm | DTM | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.56 | 37.8 | 2 | 66.5 | 8 | 24.00 | 23.94 | +0% | 1.77 | 0.0 | accelerating | 0.011 | 10.36-47.29 | 0.000 | 42.0 | 14 | 8 | 14 | — | 0.3749 | 0.2437 | 0.0371 |
| 41344 | choked-up | Choked Up | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.60 | 38.0 | 2 | 66.5 | 9 | 27.00 | 23.94 | +13% | 2.04 | 0.0 | decelerating | 0.010 | 12.35-51.25 | 0.000 | 59.5 | 13 | 9 | 13 | — | 0.3764 | 0.2142 | 0.0464 |
| 41345 | i-love-meetings | I Love Meetings | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.59 | 38.0 | 2 | 66.5 | 9 | 27.00 | 25.93 | +4% | 1.72 | 0.0 | accelerating | 0.008 | 12.35-51.25 | 0.000 | 48.5 | 13 | 9 | 13 | — | 0.3839 | 0.2390 | 0.0423 |
| 41346 | back-to-back | Back to Back | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.58 | 37.9 | 2 | 66.5 | 9 | 27.00 | 23.94 | +13% | 1.77 | 0.0 | accelerating | 0.011 | 12.35-51.25 | 0.000 | 43.0 | 13 | 9 | 13 | — | 0.3529 | 0.2756 | 0.0707 |
| 41347 | miss-it-already | Miss it Already | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.56 | 37.9 | 2 | 66.5 | 8 | 24.00 | 21.94 | +9% | 1.80 | 0.0 | accelerating | 0.004 | 10.36-47.29 | 0.000 | 53.0 | 14 | 8 | 14 | — | 0.3467 | 0.2060 | 0.0256 |
| 41348 | the-12-days-of-leftovers | The 12 Days of Leftovers | shots | platform-encoded-source | 61.61 | 1920x1080 | 29.970 | 10.43 | 76.6 | 4 | 64.9 | 13 | 19.50 | 17.53 | +11% | 1.90 | 0.0 | accelerating | 0.008 | 10.38-33.35 | 0.000 | 70.5 | 31 | 13 | 31 | — | 0.2649 | 0.4980 | 0.0931 |
| 41349 | confetti | Confetti | shots | platform-encoded-source | 29.87 | 1920x1080 | 29.970 | 10.40 | 37.0 | 2 | 67.0 | 5 | 15.00 | 16.07 | -7% | 2.64 | 0.0 | steady | 0.008 | 4.87-35.00 | 0.000 | 130.5 | 17 | 5 | 17 | — | 0.3695 | 0.6631 | 0.0750 |
| 41350 | inflatables-1 | Inflatables | shots | platform-encoded-source | 29.87 | 1920x1080 | 29.970 | 10.38 | 37.0 | 2 | 67.0 | 9 | 27.00 | 22.10 | +22% | 2.04 | 8.3 | steady | 0.011 | 12.35-51.25 | 0.000 | 45.5 | 14 | 8 | 14 | — | 0.3361 | 0.5723 | 0.1264 |
| 41351 | its-kinda-unreal-winter | It's Kinda Unreal, Winter | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.45 | 37.5 | 2 | 66.5 | 15 | 45.00 | 33.91 | +33% | 1.47 | 22.2 | decelerating | 0.028 | 25.19-74.22 | 0.333 | 37.5 | 12 | 10 | 12 | — | 0.3418 | 0.4667 | 0.0957 |
| 41352 | hosting-1 | Hosting | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.47 | 37.5 | 2 | 66.5 | 8 | 24.00 | 23.94 | +0% | 1.65 | 0.0 | accelerating | 0.028 | 10.36-47.29 | 0.000 | 43.0 | 14 | 8 | 14 | — | 0.4077 | 0.3822 | 0.1107 |
| 41353 | something-special | Something Special | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.48 | 37.6 | 2 | 66.5 | 7 | 21.00 | 23.94 | -12% | 1.74 | 0.0 | accelerating | 0.026 | 8.44-43.27 | 0.000 | 48.5 | 15 | 7 | 15 | — | 0.2791 | 0.3799 | 0.1183 |
| 41354 | save-jeanie | Save Jeanie | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.47 | 75.0 | 4 | 66.5 | 21 | 31.50 | 27.95 | +13% | 1.53 | 0.0 | decelerating | 0.008 | 19.50-48.15 | 0.000 | 46.0 | 25 | 19 | 25 | — | 0.2350 | 0.3417 | 0.0368 |
| 41355 | step-into-the-light | Step Into the Light | shots | platform-encoded-source | 98.92 | 1920x1080 | 29.970 | 10.43 | 123.0 | 4 | 40.4 | 14 | 21.00 | 19.41 | +8% | 2.17 | 0.0 | decelerating | 0.011 | 11.48-35.23 | 0.000 | 106.0 | 30 | 14 | 30 | — | 0.2386 | 0.6393 | 0.0861 |
| 41356 | do-not-accept | Do Not Accept | shots | platform-encoded-source | 90.28 | 1920x1080 | 29.970 | 10.43 | 112.2 | 4 | 44.3 | 42 | 63.00 | 69.12 | -9% | 0.53 | 49.5 | decelerating | 0.057 | 17.25-120.62 | 0.476 | 13.0 | 20 | 24 | 20 | — | 0.2867 | 0.2782 | 0.0672 |
| 41357 | thats-proper-chels-ellie-alyssa | That’s Proper Chels - Ellie & Alyssa | shots | platform-encoded-source | 26.01 | 1920x1080 | 29.970 | 10.51 | 32.6 | 2 | 76.9 | 7 | 21.00 | 25.38 | -17% | 1.13 | 41.7 | accelerating | 0.017 | 8.44-43.27 | 0.286 | 42.0 | 16 | 6 | 16 | — | 0.2067 | 0.5593 | 0.1303 |
| 41358 | the-jingle-jet | The Jingle Jet | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.42 | 74.7 | 4 | 66.5 | 17 | 25.50 | 21.96 | +16% | 2.27 | 0.0 | decelerating | 0.013 | 14.85-40.83 | 0.000 | 81.5 | 27 | 17 | 27 | — | 0.3653 | 0.4496 | 0.0977 |
| 41359 | give-your-gift | Give Your Gift | shots | platform-encoded-source | 110.25 | 1920x1080 | 29.970 | 10.43 | 137.1 | 4 | 36.3 | 6 | 9.00 | 5.99 | +50% | 5.84 | 0.0 | — | 0.028 | 0.09-25.56 | 0.000 | 102.0 | 38 | 6 | 38 | — | 0.5922 | 0.2067 | 0.2119 |
| 41361 | take-me-home-4-christmas | Take Me Home (4 Christmas) | shots | platform-encoded-source | 187.75 | 1920x1080 | 29.970 | 10.44 | 233.6 | 4 | 21.3 | 25 | 37.50 | 25.25 | +49% | 1.74 | 13.8 | accelerating | 0.011 | 23.58-56.29 | 0.160 | 37.0 | 23 | 21 | 23 | low-coverage | 0.2076 | 0.3066 | 0.0552 |
| 41362 | the-list | The List | shots | platform-encoded-source | 90.05 | 1920x1080 | 29.970 | 10.48 | 112.5 | 4 | 44.4 | 15 | 22.50 | 20.66 | +9% | 1.74 | 0.0 | decelerating | 0.016 | 9.71-41.36 | 0.000 | 51.5 | 29 | 15 | 29 | — | 0.2118 | 0.4118 | 0.0544 |
| 41363 | hot-holidays | Hot Holidays | shots | platform-encoded-source | 41.92 | 1920x1080 | 29.970 | 10.57 | 52.8 | 3 | 71.6 | 22 | 44.00 | 41.51 | +6% | 1.05 | 6.7 | decelerating | 0.022 | 24.50-70.85 | 0.091 | 36.0 | 13 | 20 | 13 | — | 0.5181 | 0.4000 | 0.1443 |
| 41364 | dos-vidas-un-destino | Dos Vidas, Un Destino | shots | platform-encoded-source | 61.12 | 1920x1080 | 29.970 | 10.51 | 76.6 | 4 | 65.4 | 14 | 21.00 | 20.62 | +2% | 2.27 | 0.0 | decelerating | 0.010 | 11.48-35.23 | 0.000 | 65.0 | 30 | 14 | 30 | — | 0.1767 | 0.6032 | 0.0491 |
| 41365 | holiday-workshop | Holiday Workshop | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.51 | 75.3 | 4 | 66.5 | 21 | 31.50 | 28.94 | +9% | 1.74 | 0.0 | steady | 0.014 | 19.50-48.15 | 0.000 | 52.0 | 23 | 21 | 23 | — | 0.2928 | 0.5183 | 0.1122 |
| 41366 | new-iphone-18-pro | New iPhone 18 Pro | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.57 | 37.9 | 2 | 66.5 | 9 | 27.00 | 29.92 | -10% | 1.41 | 0.0 | steady | 0.031 | 12.35-51.25 | 0.000 | 43.0 | 13 | 9 | 13 | — | 0.3233 | 0.5104 | 0.0845 |
| 41367 | switch-to-fios | Switch to Fios | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.59 | 38.0 | 2 | 66.5 | 10 | 30.00 | 33.91 | -12% | 1.57 | 0.0 | decelerating | 0.010 | 14.39-55.17 | 0.000 | 49.0 | 12 | 10 | 12 | — | 0.2688 | 0.5515 | 0.0290 |
| 41368 | take-the-credit | Take The Credit | shots | platform-encoded-source | 90.01 | 1920x1080 | 29.970 | 10.43 | 111.9 | 4 | 44.4 | 19 | 28.50 | 24.67 | +16% | 1.65 | 0.0 | steady | 0.008 | 17.16-44.51 | 0.000 | 49.0 | 25 | 19 | 25 | — | 0.2513 | 0.2432 | 0.0423 |
| 41369 | the-most-playful-christmas-ever | The Most Playful Christmas Ever | shots | platform-encoded-source | 47.30 | 1920x1080 | 29.970 | 10.40 | 58.7 | 4 | 84.6 | 29 | 43.50 | 40.60 | +7% | 1.20 | 6.1 | steady | 0.034 | 28.17-63.74 | 0.069 | 34.5 | 19 | 25 | 19 | — | 0.2986 | 0.4272 | 0.1463 |
| 41371 | a-holiday-of-treats | A Holiday Of Treats | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.31 | 18.5 | 1 | 66.4 | 16 | 96.00 | 71.71 | +34% | 0.10 | 57.9 | decelerating | 0.046 | 54.87-155.90 | 0.812 | 3.0 | 5 | 6 | 5 | burst-heavy, short-sample, sparse-delta-basis | 0.5363 | 0.3409 | 0.1453 |
| 41372 | a-holiday-at-home-chewy-claus | A Holiday at Home, Chewy Claus | shots | platform-encoded-source | 15.06 | 1920x1080 | 29.970 | 10.39 | 18.7 | 1 | 66.4 | 4 | 24.00 | 19.92 | +20% | 2.37 | 0.0 | decelerating | 0.015 | 6.54-61.45 | 0.000 | 39.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.3554 | 0.4014 | 0.1406 |
| 41373 | a-holiday-dream | A Holiday Dream | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 12 | 36.00 | 35.90 | +0% | 1.43 | 15.8 | accelerating | 0.019 | 18.60-62.88 | 0.250 | 55.0 | 12 | 10 | 12 | — | 0.4393 | 0.4038 | 0.0827 |
| 41374 | long-live-joy | Long Live Joy | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.41 | 74.6 | 4 | 66.5 | 9 | 13.50 | 19.96 | -32% | 1.80 | 0.0 | decelerating | 0.030 | 2.67-31.43 | 0.000 | 77.5 | 35 | 9 | 35 | — | 0.3299 | 0.4742 | 0.1404 |
| 41375 | house-of-burl-holiday | House of Burl Holiday | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.60 | 38.0 | 2 | 66.5 | 10 | 30.00 | 33.91 | -12% | 1.45 | 11.1 | accelerating | 0.016 | 14.39-55.17 | 0.000 | 30.0 | 13 | 9 | 13 | — | 0.2200 | 0.3848 | 0.1035 |
| 41376 | celebrate-being-human | Celebrate Being Human | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.41 | 74.6 | 4 | 66.5 | 46 | 69.00 | 76.85 | -10% | 0.67 | 26.9 | accelerating | 0.084 | 50.52-92.04 | 0.065 | 23.0 | 7 | 37 | 7 | sparse-delta-basis | 0.3757 | 0.3582 | 0.1685 |
| 41377 | workshops-us | Workshops US | shots | platform-encoded-source | 57.11 | 1920x1080 | 29.970 | 10.44 | 71.1 | 4 | 70.0 | 23 | 34.50 | 36.77 | -6% | 1.27 | 0.0 | steady | 0.017 | 17.10-58.29 | 0.000 | 45.5 | 21 | 23 | 21 | — | 0.2431 | 0.4807 | 0.0452 |
| 41378 | thats-proper-chels-ask-joao | That’s Proper Chels - Ask Joao | shots | platform-encoded-source | 41.64 | 1920x1080 | 29.970 | 10.48 | 52.0 | 3 | 72.0 | 2 | 4.00 | 10.09 | -60% | 3.82 | 37.5 | accelerating | 0.022 | 0.48-14.45 | 0.000 | 744.0 | 31 | 2 | 31 | — | 0.1810 | 0.3190 | 0.0868 |
| 41379 | thats-proper-chels-intro | That’s Proper Chels - Intro | shots | platform-encoded-source | 27.73 | 1920x1080 | 29.970 | 10.38 | 34.3 | 2 | 72.1 | 0 | 0.00 | 4.33 | -100% | 0.51 | 33.3 | — | 0.011 | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.0651 | 0.1892 | 0.0473 |
| 41380 | thats-proper-chels-cole-morgan | That’s Proper Chels - Cole & Morgan | shots | platform-encoded-source | 29.89 | 1920x1080 | 29.970 | 10.50 | 37.4 | 2 | 66.9 | 4 | 12.00 | 18.07 | -34% | 2.44 | 30.0 | accelerating | 0.016 | 3.27-30.72 | 0.000 | 128.0 | 18 | 4 | 18 | — | 0.1334 | 0.7099 | 0.0987 |
| 41381 | forgive-but-never-forget | Forgive But Never Forget | shots | platform-encoded-source | 39.08 | 1920x1080 | 29.970 | 10.41 | 48.5 | 3 | 76.8 | 0 | 0.00 | 0.00 | — | 39.08 | 0.0 | — | 0.003 | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.0778 | 0.1658 | 0.0349 |
| 41382 | feeling-the-breeze | Feeling The Breeze | shots | platform-encoded-source | 47.36 | 1920x1080 | 29.970 | 10.41 | 58.8 | 4 | 84.5 | 0 | 0.00 | 0.00 | — | 47.36 | 0.0 | — | 0.007 | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.0842 | 0.1695 | 0.0466 |
| 41383 | dinner-is-served | Dinner Is Served | shots | platform-encoded-source | 50.22 | 1920x1080 | 29.970 | 10.47 | 62.7 | 4 | 79.7 | 2 | 3.00 | 2.39 | +26% | 16.95 | 0.0 | decelerating | 0.007 | 0.36-10.84 | 0.000 | 779.0 | 42 | 2 | 42 | — | 0.1433 | 0.0965 | 0.0430 |
| 41384 | some-really-good-sheet | Some Really Good Sheet | shots | platform-encoded-source | 51.39 | 1920x1080 | 29.970 | 10.41 | 63.8 | 4 | 77.8 | 1 | 1.50 | 1.17 | +28% | 25.70 | 0.0 | decelerating | 0.007 | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.1389 | 0.1084 | 0.0548 |
| 41385 | whats-green-and-looks-like-a-sock | What’s Green And Looks Like A Sock | shots | platform-encoded-source | 52.61 | 1920x1080 | 29.970 | 10.49 | 65.8 | 4 | 76.0 | 1 | 1.50 | 1.14 | +32% | 26.30 | 0.0 | — | 0.004 | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.1269 | 0.1225 | 0.0488 |
| 41386 | pillow-talk | Pillow Talk | shots | platform-encoded-source | 52.44 | 1920x1080 | 29.970 | 10.41 | 65.1 | 4 | 76.3 | 2 | 3.00 | 2.29 | +31% | 19.19 | 0.0 | decelerating | 0.005 | 0.36-10.84 | 0.000 | 575.0 | 42 | 2 | 42 | — | 0.1264 | 0.1169 | 0.0511 |
| 41387 | the-ten-month-nap | The Ten-Month Nap | shots | platform-encoded-source | 44.61 | 1920x1080 | 29.970 | 10.40 | 55.3 | 4 | 89.7 | 3 | 4.50 | 4.04 | +12% | 9.72 | 0.0 | decelerating | 0.004 | 0.55-14.06 | 0.000 | 384.0 | 41 | 3 | 41 | — | 0.1573 | 0.0844 | 0.0516 |
| 41388 | take-time-to-connect | Take Time to Connect | shots | platform-encoded-source | 60.05 | 1920x1080 | 29.970 | 10.42 | 74.6 | 4 | 66.6 | 24 | 36.00 | 30.97 | +16% | 1.47 | 0.0 | decelerating | 0.025 | 23.07-53.57 | 0.000 | 44.0 | 21 | 23 | 21 | — | 0.3218 | 0.3923 | 0.1278 |
| 41389 | this-is-not-a-christmas-ad | This Is Not A Christmas Ad | shots | platform-encoded-source | 127.17 | 1920x1080 | 29.970 | 10.43 | 158.2 | 4 | 31.5 | 3 | 4.50 | 4.25 | +6% | 7.61 | 0.0 | — | 0.004 | 0.55-14.06 | 0.000 | 508.5 | 41 | 3 | 41 | — | 0.1275 | 0.2979 | 0.0674 |
| 41390 | the-wonder-of-gifting-necklace | The Wonder of Gifting - Necklace | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.41 | 37.3 | 2 | 66.5 | 10 | 30.00 | 31.94 | -6% | 1.57 | 0.0 | decelerating | 0.027 | 14.39-55.17 | 0.000 | 52.0 | 12 | 10 | 12 | — | 0.3518 | 0.3880 | 0.0890 |
| 41391 | the-wonder-of-gifting-bangle | The Wonder of Gifting - Bangle | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.62 | 38.1 | 2 | 66.5 | 10 | 30.00 | 31.94 | -6% | 1.37 | 0.0 | decelerating | 0.042 | 14.39-55.17 | 0.000 | 41.0 | 12 | 10 | 12 | — | 0.3360 | 0.4102 | 0.0996 |
| 41392 | go-nutso | Go Nutso | shots | platform-encoded-source | 60.14 | 1920x1080 | 29.970 | 10.42 | 74.7 | 4 | 66.5 | 30 | 45.00 | 42.90 | +5% | 0.85 | 15.9 | accelerating | 0.029 | 30.36-64.24 | 0.267 | 24.0 | 22 | 22 | 22 | — | 0.3035 | 0.3827 | 0.1708 |
| 41393 | let-love-last | Let Love Last | shots | platform-encoded-source | 95.57 | 1920x1080 | 29.970 | 10.43 | 118.8 | 4 | 41.9 | 13 | 19.50 | 20.09 | -3% | 2.20 | 0.0 | steady | 0.015 | 9.07-35.33 | 0.000 | 64.0 | 32 | 12 | 32 | — | 0.2192 | 0.0000 | 0.0846 |
| 41395 | the-most-dangerous-time-of-year-1 | The Most Dangerous Time of Year | shots | platform-encoded-source | 59.86 | 1920x1080 | 29.970 | 10.51 | 75.0 | 4 | 66.8 | 1 | 1.50 | 4.01 | -63% | 10.21 | 0.0 | — | 0.009 | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.0945 | 0.2486 | 0.0566 |
| 41396 | stories-movies-are-made-of | Stories Movies Are Made Of | shots | platform-encoded-source | 30.06 | 1920x1080 | 29.970 | 10.39 | 37.2 | 2 | 66.5 | 0 | 0.00 | 0.00 | — | 30.06 | 0.0 | — | 0.001 | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.1573 | 0.5212 | 0.0251 |
| 41397 | classic-fm-christmas-aled-jones-defrosts | Classic FM Christmas Aled Jones Defrosts | shots | platform-encoded-source | 54.93 | 1920x1080 | 29.970 | 10.41 | 68.2 | 4 | 72.8 | 6 | 9.00 | 8.74 | +3% | 3.00 | 0.0 | decelerating | 0.002 | 2.99-20.16 | 0.000 | 120.0 | 39 | 5 | 39 | — | 0.4997 | 0.4579 | 0.0322 |
| 41398 | share-the-warmth-heatball-fight | Share the Warmth - Heatball Fight | shots | platform-encoded-source | 84.37 | 1920x1080 | 29.970 | 10.43 | 104.9 | 4 | 47.4 | 4 | 6.00 | 8.53 | -30% | 4.47 | 0.0 | decelerating | 0.025 | 1.63-15.36 | 0.000 | 392.0 | 40 | 4 | 40 | — | 0.1723 | 0.3440 | 0.0798 |
| 41399 | get-ahead | Get Ahead | shots | platform-encoded-source | 47.49 | 1920x1080 | 29.970 | 10.42 | 59.0 | 4 | 84.2 | 0 | 0.00 | 2.53 | -100% | 3.71 | 0.0 | — | 0.030 | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.2218 | 0.3646 | 0.1314 |
| 41400 | relx-wind | RELX WIND | shots | platform-encoded-source | 60.03 | 1920x1080 | 29.970 | 10.48 | 75.0 | 4 | 66.6 | 47 | 70.50 | 61.97 | +14% | 0.83 | 22.2 | steady | 0.063 | 51.80-93.75 | 0.106 | 24.5 | 11 | 33 | 11 | — | 0.2645 | 0.3244 | 0.0754 |
| 41402 | fancy-pants | Fancy Pants | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 5 | 15.00 | 17.95 | -16% | 2.90 | 0.0 | steady | 0.017 | 4.87-35.00 | 0.000 | 107.5 | 17 | 5 | 17 | — | 0.2877 | 0.3985 | 0.1086 |
| 41403 | starbucks-perfect-harmony | Starbucks  - Perfect Harmony | shots | platform-encoded-source | 60.12 | 1920x1080 | 29.970 | 10.49 | 75.2 | 4 | 66.5 | 23 | 34.50 | 34.93 | -1% | 1.22 | 11.1 | decelerating | 0.040 | 21.87-51.77 | 0.087 | 36.5 | 24 | 20 | 24 | — | 0.2514 | 0.3990 | 0.1323 |
| 41404 | cruise-2026-27-collection | Cruise 2026/27 Collection | shots | platform-encoded-source | 48.26 | 1920x1080 | 29.970 | 10.41 | 59.9 | 4 | 82.9 | 44 | 66.00 | 59.68 | +11% | 0.97 | 20.4 | decelerating | 0.056 | 47.96-88.60 | 0.068 | 28.0 | 10 | 34 | 10 | — | 0.4000 | 0.1801 | 0.1261 |
| 41405 | forever-3 | Forever | shots | platform-encoded-source | 176.41 | 1920x1080 | 29.970 | 10.44 | 219.5 | 4 | 22.7 | 6 | 9.00 | 24.49 | -63% | 0.47 | 58.9 | decelerating | 0.035 | 0.94-23.98 | 0.000 | 102.0 | 38 | 6 | 38 | low-coverage | 0.3057 | 0.3033 | 0.1851 |
| 41406 | film-study | Film Study | shots | platform-encoded-source | 30.08 | 1920x1080 | 29.970 | 10.38 | 37.2 | 2 | 66.5 | 6 | 18.00 | 25.93 | -31% | 1.09 | 28.6 | — | 0.017 | 6.61-39.18 | 0.333 | 32.0 | 17 | 5 | 17 | — | 0.2082 | 0.4358 | 0.0754 |
| 41407 | lego-header-1 | Lego header | shots | 720p-web-rendition | 28.03 | 1280x720 | 29.970 | 2.64 | 8.8 | 2 | 71.4 | 32 | 96.00 | 87.76 | +9% | 0.57 | 42.9 | steady | 0.046 | 65.66-135.52 | 0.656 | 17.0 | 4 | 18 | 4 | burst-heavy, sparse-delta-basis | 0.4049 | 0.4467 | 0.1799 |

## Per-video detail (first 20 by clip id)

### happy-internetting-film-compilation — Happy Internetting - Film Compilation

| field | value |
| --- | --- |
| clip_id | 40839 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 158.85 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.44 |
| download_mb | 197.6 |
| windows | 4 |
| coverage_pct | 25.2 |
| candidates_n | 5 |
| sampled_cut_candidates_per_min | 7.50 |
| ci95 | 0.70-20.92 |
| burst | 0.000 |
| gap_frames | 60.5 |
| within_shot_pairs | 39 |
| cut_sep_pairs | 5 |
| delta_basis_pairs | 39 |
| validity | — |
| mean_luma | 0.5063 |
| mean_sat | 0.5836 |
| delta_per_s | 0.0688 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 0 | 0.5166 | 0.5692 | 0.0689 |
| 10.00 | 44.00 | 12 | 2 | 0.4833 | 0.5681 | 0.0716 |
| 10.00 | 88.00 | 12 | 3 | 0.4771 | 0.5798 | 0.0720 |
| 10.00 | 132.00 | 12 | 0 | 0.5483 | 0.6174 | 0.0642 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### boot — Boot

| field | value |
| --- | --- |
| clip_id | 40856 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 30.06 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.41 |
| download_mb | 37.3 |
| windows | 2 |
| coverage_pct | 66.5 |
| candidates_n | 5 |
| sampled_cut_candidates_per_min | 15.00 |
| ci95 | 4.87-35.00 |
| burst | 0.000 |
| gap_frames | 92.5 |
| within_shot_pairs | 18 |
| cut_sep_pairs | 4 |
| delta_basis_pairs | 18 |
| validity | — |
| mean_luma | 0.2859 |
| mean_sat | 0.2602 |
| delta_per_s | 0.0260 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 2 | 0.3159 | 0.2106 | 0.0187 |
| 10.00 | 17.00 | 12 | 3 | 0.2559 | 0.3098 | 0.0351 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### chase-4 — Chase

| field | value |
| --- | --- |
| clip_id | 40857 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 30.06 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.40 |
| download_mb | 37.3 |
| windows | 2 |
| coverage_pct | 66.5 |
| candidates_n | 11 |
| sampled_cut_candidates_per_min | 33.00 |
| ci95 | 16.47-59.05 |
| burst | 0.818 |
| gap_frames | 2.5 |
| within_shot_pairs | 19 |
| cut_sep_pairs | 3 |
| delta_basis_pairs | 19 |
| validity | burst-heavy, non-edit-scene-change |
| mean_luma | 0.2774 |
| mean_sat | 0.2966 |
| delta_per_s | 0.0353 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 9 | 0.2638 | 0.2814 | 0.0253 |
| 10.00 | 17.00 | 12 | 2 | 0.2910 | 0.3118 | 0.0463 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### change-is-in-our-power — Change Is In Our Power

| field | value |
| --- | --- |
| clip_id | 40861 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 60.09 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.41 |
| download_mb | 74.6 |
| windows | 4 |
| coverage_pct | 66.6 |
| candidates_n | 46 |
| sampled_cut_candidates_per_min | 69.00 |
| ci95 | 47.89-95.31 |
| burst | 0.217 |
| gap_frames | 24.0 |
| within_shot_pairs | 11 |
| cut_sep_pairs | 33 |
| delta_basis_pairs | 11 |
| validity | — |
| mean_luma | 0.2961 |
| mean_sat | 0.2918 |
| delta_per_s | 0.1382 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 8 | 0.2573 | 0.2729 | 0.0560 |
| 10.00 | 14.00 | 12 | 17 | 0.2546 | 0.3716 | 0.2351 |
| 10.00 | 28.00 | 12 | 10 | 0.3238 | 0.2799 | 0.0914 |
| 10.00 | 42.00 | 12 | 11 | 0.3486 | 0.2429 | 0.1548 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### wood-chipper — Wood Chipper

| field | value |
| --- | --- |
| clip_id | 40870 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 30.08 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.43 |
| download_mb | 37.4 |
| windows | 2 |
| coverage_pct | 66.5 |
| candidates_n | 10 |
| sampled_cut_candidates_per_min | 30.00 |
| ci95 | 14.39-55.17 |
| burst | 0.300 |
| gap_frames | 56.0 |
| within_shot_pairs | 14 |
| cut_sep_pairs | 8 |
| delta_basis_pairs | 14 |
| validity | — |
| mean_luma | 0.3920 |
| mean_sat | 0.4579 |
| delta_per_s | 0.1119 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 5 | 0.3993 | 0.3654 | 0.1122 |
| 10.00 | 17.00 | 12 | 5 | 0.3848 | 0.5504 | 0.1115 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### no-freezer — No Freezer

| field | value |
| --- | --- |
| clip_id | 40871 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 30.08 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.45 |
| download_mb | 37.5 |
| windows | 2 |
| coverage_pct | 66.5 |
| candidates_n | 13 |
| sampled_cut_candidates_per_min | 39.00 |
| ci95 | 20.77-66.69 |
| burst | 0.154 |
| gap_frames | 35.5 |
| within_shot_pairs | 11 |
| cut_sep_pairs | 11 |
| delta_basis_pairs | 11 |
| validity | — |
| mean_luma | 0.5041 |
| mean_sat | 0.3151 |
| delta_per_s | 0.1365 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 8 | 0.5540 | 0.1853 | 0.1179 |
| 10.00 | 17.00 | 12 | 5 | 0.4543 | 0.4449 | 0.1519 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### holder — Holder

| field | value |
| --- | --- |
| clip_id | 40872 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 34.52 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.40 |
| download_mb | 42.8 |
| windows | 3 |
| coverage_pct | 86.9 |
| candidates_n | 2 |
| sampled_cut_candidates_per_min | 4.00 |
| ci95 | 0.00-18.78 |
| burst | 0.000 |
| gap_frames | 43.0 |
| within_shot_pairs | 31 |
| cut_sep_pairs | 2 |
| delta_basis_pairs | 31 |
| validity | — |
| mean_luma | 0.1088 |
| mean_sat | 0.6207 |
| delta_per_s | 0.1040 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 2 | 0.1083 | 0.7088 | 0.1196 |
| 10.00 | 10.00 | 12 | 0 | 0.0850 | 0.5975 | 0.0777 |
| 10.00 | 20.00 | 12 | 0 | 0.1330 | 0.5557 | 0.1175 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### worry-free-life — Worry Free Life

| field | value |
| --- | --- |
| clip_id | 40874 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 78.42 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.42 |
| download_mb | 97.4 |
| windows | 4 |
| coverage_pct | 51.0 |
| candidates_n | 16 |
| sampled_cut_candidates_per_min | 24.00 |
| ci95 | 13.72-38.97 |
| burst | 0.125 |
| gap_frames | 71.0 |
| within_shot_pairs | 29 |
| cut_sep_pairs | 15 |
| delta_basis_pairs | 29 |
| validity | — |
| mean_luma | 0.2045 |
| mean_sat | 0.2845 |
| delta_per_s | 0.0961 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 3 | 0.2029 | 0.4083 | 0.1257 |
| 10.00 | 20.00 | 12 | 3 | 0.2192 | 0.2395 | 0.0700 |
| 10.00 | 40.00 | 12 | 6 | 0.1412 | 0.2511 | 0.0938 |
| 10.00 | 60.00 | 12 | 4 | 0.2548 | 0.2390 | 0.0897 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### back-to-school-1 — Back to School

| field | value |
| --- | --- |
| clip_id | 40875 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 60.52 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.45 |
| download_mb | 75.4 |
| windows | 4 |
| coverage_pct | 66.1 |
| candidates_n | 21 |
| sampled_cut_candidates_per_min | 31.50 |
| ci95 | 8.72-63.11 |
| burst | 0.619 |
| gap_frames | 27.0 |
| within_shot_pairs | 29 |
| cut_sep_pairs | 15 |
| delta_basis_pairs | 29 |
| validity | burst-heavy |
| mean_luma | 0.3587 |
| mean_sat | 0.2930 |
| delta_per_s | 0.1293 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 9 | 0.3716 | 0.2603 | 0.1003 |
| 10.00 | 14.00 | 12 | 1 | 0.3557 | 0.3927 | 0.1446 |
| 10.00 | 28.00 | 12 | 2 | 0.3489 | 0.2867 | 0.1674 |
| 10.00 | 42.00 | 12 | 9 | 0.3586 | 0.2325 | 0.0487 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### making-eat-the-wild — Making Eat the Wild

| field | value |
| --- | --- |
| clip_id | 40877 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 108.16 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.43 |
| download_mb | 134.5 |
| windows | 4 |
| coverage_pct | 37.0 |
| candidates_n | 12 |
| sampled_cut_candidates_per_min | 18.00 |
| ci95 | 9.30-31.44 |
| burst | 0.167 |
| gap_frames | 61.0 |
| within_shot_pairs | 33 |
| cut_sep_pairs | 11 |
| delta_basis_pairs | 33 |
| validity | — |
| mean_luma | 0.1656 |
| mean_sat | 0.3583 |
| delta_per_s | 0.0843 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 2 | 0.0959 | 0.3069 | 0.0655 |
| 10.00 | 29.00 | 12 | 2 | 0.2154 | 0.4375 | 0.0843 |
| 10.00 | 58.00 | 12 | 5 | 0.1891 | 0.3525 | 0.0560 |
| 10.00 | 87.00 | 12 | 3 | 0.1620 | 0.3362 | 0.1303 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### eat-the-wild — Eat the Wild

| field | value |
| --- | --- |
| clip_id | 40878 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 30.10 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.54 |
| download_mb | 37.8 |
| windows | 2 |
| coverage_pct | 66.4 |
| candidates_n | 8 |
| sampled_cut_candidates_per_min | 24.00 |
| ci95 | 10.36-47.29 |
| burst | 0.000 |
| gap_frames | 67.0 |
| within_shot_pairs | 14 |
| cut_sep_pairs | 8 |
| delta_basis_pairs | 14 |
| validity | — |
| mean_luma | 0.1737 |
| mean_sat | 0.5297 |
| delta_per_s | 0.1158 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 4 | 0.1651 | 0.5489 | 0.1084 |
| 10.00 | 17.00 | 12 | 4 | 0.1824 | 0.5105 | 0.1231 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### last-commercial-before-and-after — Last Commercial before and after

| field | value |
| --- | --- |
| clip_id | 40880 |
| brand | shots |
| rendition | 720p-web-rendition |
| runtime_s | 24.02 |
| resolution | 1280x720 |
| fps | 29.970 |
| bitrate_mbps | 0.79 |
| download_mb | 2.3 |
| windows | 2 |
| coverage_pct | 83.3 |
| candidates_n | 6 |
| sampled_cut_candidates_per_min | 18.00 |
| ci95 | 6.61-39.18 |
| burst | 0.000 |
| gap_frames | 90.0 |
| within_shot_pairs | 16 |
| cut_sep_pairs | 6 |
| delta_basis_pairs | 16 |
| validity | — |
| mean_luma | 0.2444 |
| mean_sat | 0.1542 |
| delta_per_s | 0.0005 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 3 | 0.2444 | 0.1542 | 0.0006 |
| 10.00 | 11.00 | 12 | 3 | 0.2444 | 0.1542 | 0.0004 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### who-knows-how-far-our-network-will-go — Who Knows How Far Our Network Will Go?

| field | value |
| --- | --- |
| clip_id | 40881 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 83.24 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.43 |
| download_mb | 103.5 |
| windows | 4 |
| coverage_pct | 48.1 |
| candidates_n | 9 |
| sampled_cut_candidates_per_min | 13.50 |
| ci95 | 6.17-25.63 |
| burst | 0.000 |
| gap_frames | 84.5 |
| within_shot_pairs | 35 |
| cut_sep_pairs | 9 |
| delta_basis_pairs | 35 |
| validity | — |
| mean_luma | 0.2043 |
| mean_sat | 0.1908 |
| delta_per_s | 0.0892 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 3 | 0.1196 | 0.2441 | 0.0515 |
| 10.00 | 21.00 | 12 | 1 | 0.3261 | 0.1221 | 0.1207 |
| 10.00 | 42.00 | 12 | 1 | 0.1727 | 0.1682 | 0.1037 |
| 10.00 | 63.00 | 12 | 4 | 0.1986 | 0.2287 | 0.0663 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### new-trick — new trick

| field | value |
| --- | --- |
| clip_id | 40882 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 181.18 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.44 |
| download_mb | 225.6 |
| windows | 4 |
| coverage_pct | 22.1 |
| candidates_n | 15 |
| sampled_cut_candidates_per_min | 22.50 |
| ci95 | 5.60-47.43 |
| burst | 0.400 |
| gap_frames | 42.0 |
| within_shot_pairs | 33 |
| cut_sep_pairs | 11 |
| delta_basis_pairs | 33 |
| validity | low-coverage |
| mean_luma | 0.3498 |
| mean_sat | 0.3221 |
| delta_per_s | 0.1292 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 8 | 0.4203 | 0.3034 | 0.1579 |
| 10.00 | 51.00 | 12 | 4 | 0.3488 | 0.3265 | 0.1589 |
| 10.00 | 102.00 | 12 | 0 | 0.4192 | 0.2312 | 0.1558 |
| 10.00 | 153.00 | 12 | 3 | 0.2107 | 0.4272 | 0.0414 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### for-all-wheelkind — For All Wheelkind

| field | value |
| --- | --- |
| clip_id | 40883 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 30.06 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.40 |
| download_mb | 37.3 |
| windows | 2 |
| coverage_pct | 66.5 |
| candidates_n | 17 |
| sampled_cut_candidates_per_min | 51.00 |
| ci95 | 29.71-81.66 |
| burst | 0.118 |
| gap_frames | 32.0 |
| within_shot_pairs | 8 |
| cut_sep_pairs | 14 |
| delta_basis_pairs | 8 |
| validity | — |
| mean_luma | 0.2824 |
| mean_sat | 0.3423 |
| delta_per_s | 0.0783 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 7 | 0.2631 | 0.4588 | 0.0885 |
| 10.00 | 17.00 | 12 | 10 | 0.3018 | 0.2257 | 0.0477 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### the-running-backs-dog — The Running Back's Dog

| field | value |
| --- | --- |
| clip_id | 40884 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 30.12 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.44 |
| download_mb | 37.5 |
| windows | 2 |
| coverage_pct | 66.4 |
| candidates_n | 4 |
| sampled_cut_candidates_per_min | 12.00 |
| ci95 | 3.27-30.72 |
| burst | 0.000 |
| gap_frames | 140.0 |
| within_shot_pairs | 18 |
| cut_sep_pairs | 4 |
| delta_basis_pairs | 18 |
| validity | — |
| mean_luma | 0.2889 |
| mean_sat | 0.3904 |
| delta_per_s | 0.1304 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 1 | 0.3496 | 0.3723 | 0.1178 |
| 10.00 | 17.00 | 12 | 3 | 0.2283 | 0.4086 | 0.1461 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### splenda-stevia-freedom-250 — Splenda Stevia Freedom 250

| field | value |
| --- | --- |
| clip_id | 40885 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 29.99 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.58 |
| download_mb | 37.8 |
| windows | 2 |
| coverage_pct | 66.7 |
| candidates_n | 10 |
| sampled_cut_candidates_per_min | 30.00 |
| ci95 | 14.39-55.17 |
| burst | 0.000 |
| gap_frames | 64.0 |
| within_shot_pairs | 12 |
| cut_sep_pairs | 10 |
| delta_basis_pairs | 12 |
| validity | — |
| mean_luma | 0.3469 |
| mean_sat | 0.2286 |
| delta_per_s | 0.0505 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 6 | 0.2930 | 0.2246 | 0.0585 |
| 10.00 | 16.00 | 12 | 4 | 0.4007 | 0.2327 | 0.0448 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### whats-with-the-big-diesel — What’s with the Big Diesel

| field | value |
| --- | --- |
| clip_id | 40886 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 30.08 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.41 |
| download_mb | 37.3 |
| windows | 2 |
| coverage_pct | 66.5 |
| candidates_n | 15 |
| sampled_cut_candidates_per_min | 45.00 |
| ci95 | 25.19-74.22 |
| burst | 0.200 |
| gap_frames | 41.0 |
| within_shot_pairs | 8 |
| cut_sep_pairs | 14 |
| delta_basis_pairs | 8 |
| validity | — |
| mean_luma | 0.2276 |
| mean_sat | 0.5310 |
| delta_per_s | 0.0699 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 9 | 0.1862 | 0.4924 | 0.1173 |
| 10.00 | 17.00 | 12 | 6 | 0.2691 | 0.5697 | 0.0415 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### katzs-deli-with-new-york-nico — Katz's Deli with New York Nico!

| field | value |
| --- | --- |
| clip_id | 40887 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 179.24 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.44 |
| download_mb | 223.0 |
| windows | 4 |
| coverage_pct | 22.3 |
| candidates_n | 17 |
| sampled_cut_candidates_per_min | 25.50 |
| ci95 | 14.85-40.83 |
| burst | 0.176 |
| gap_frames | 61.0 |
| within_shot_pairs | 29 |
| cut_sep_pairs | 15 |
| delta_basis_pairs | 29 |
| validity | low-coverage |
| mean_luma | 0.2140 |
| mean_sat | 0.3427 |
| delta_per_s | 0.0594 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 2 | 0.2140 | 0.3720 | 0.0434 |
| 10.00 | 50.00 | 12 | 3 | 0.2089 | 0.3324 | 0.0376 |
| 10.00 | 100.00 | 12 | 6 | 0.2014 | 0.3445 | 0.1102 |
| 10.00 | 150.00 | 12 | 6 | 0.2316 | 0.3219 | 0.0523 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### was-sich-liebt — Was sich liebt

| field | value |
| --- | --- |
| clip_id | 40888 |
| brand | shots |
| rendition | platform-encoded-source |
| runtime_s | 79.89 |
| resolution | 1920x1080 |
| fps | 29.970 |
| bitrate_mbps | 10.42 |
| download_mb | 99.3 |
| windows | 4 |
| coverage_pct | 50.1 |
| candidates_n | 15 |
| sampled_cut_candidates_per_min | 22.50 |
| ci95 | 11.16-39.23 |
| burst | 0.000 |
| gap_frames | 52.5 |
| within_shot_pairs | 29 |
| cut_sep_pairs | 15 |
| delta_basis_pairs | 29 |
| validity | — |
| mean_luma | 0.1624 |
| mean_sat | 0.3800 |
| delta_per_s | 0.0540 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 5 | 0.2484 | 0.4006 | 0.0791 |
| 10.00 | 20.00 | 12 | 6 | 0.2178 | 0.4265 | 0.0472 |
| 10.00 | 40.00 | 12 | 3 | 0.1336 | 0.3833 | 0.0601 |
| 10.00 | 60.00 | 12 | 1 | 0.0496 | 0.3098 | 0.0373 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

## Aggregates (video-measured records only)

Every number in this section is computed ONLY over the video-measured records tabulated above. Published stills, including still-only clips, never enter the motion, cut, luma, or saturation aggregates.

### Counts

| rendition | records |
| --- | --- |
| 720p-web-rendition | 12 |
| platform-encoded-source | 445 |

| brand | records |
| --- | --- |
| shots | 457 |

### Distributions

All minima and maxima are computed over `rankable` records only and name the record id and validity flags.

Unique records before dedupe: 457; after dedupe: 457 (0 duplicate extra record(s) collapsed).

Rankable records: 374 of 457 unique; excluded as non-rankable: 83.

| metric | n | min (record; flags) | median | max (record; flags) |
| --- | --- | --- | --- | --- |
| runtime_s | 374 | 22.36 (novela; —) | 59.97 | 188.74 (the-most-vicious-cycle; low-coverage) |
| candidates_n | 374 | 0 (behind-the-scenes-of-wear-your-best-life; no-cuts-observed) | 12 | 50 (bees-r-good; —) |
| sampled_cut_candidates_per_min | 374 | 0.00 (behind-the-scenes-of-wear-your-best-life; no-cuts-observed) | 24.00 | 99.00 (hockey-1; sparse-delta-basis) |
| mean_luma | 374 | 0.0629 (go-ocean-fund-the-planets-blue-lung; —) | 0.2649 | 0.7841 (merino-deep-dive; —) |
| mean_sat | 374 | 0.0000 (let-love-last; —) | 0.3333 | 0.8223 (lazer-tag; no-cuts-observed) |
Excluded as non-rankable (largest first):

| record | sampled_cut_candidates_per_min | validity |
| --- | --- | --- |
| the-best-part-of-tinder-isnt-on-tinder | 153.00 | burst-heavy, no-delta-basis, sparse-delta-basis |
| freestyle-lo | 111.00 | burst-heavy |
| we-are | 103.50 | burst-heavy |
| behind-the-scenes-of-petbarn-brand-world | 102.00 | burst-heavy, short-sample, sparse-delta-basis |
| a-holiday-of-treats | 96.00 | burst-heavy, short-sample, sparse-delta-basis |

Coverage-weighted caveat: 13793.0 sampled seconds cover 27255.7 runtime seconds (50.6%). Aggregates describe the sampled windows, not the full clips.

## Comparability

- poolable: `false`
- comparable within: same site, same rendition, same runtime band, non-burst, >=25% coverage
- not comparable to: other sites, other renditions, full-film claims derived from window rates

Caveats:

- shots.net: poolable is false; every number describes this site's measured sample only.
- 457 of 40908 catalogue items were measured (1.117%) by allowlisted 720p web rendition, ready list stream, or signed original availability.
- Measured rows are not a random sample: availability and recency select them, so cross-site pooling is invalid.
- Provider families are not interchangeable: platform-encoded-source x 445, 720p-web-rendition x 12.
- Renditions differ by site and record: platform-encoded source renditions only; no ladder rung is the delivered master.
- Measured renditions vary by resolution (1920x1080 x 440, 1280x720 x 17), frame rate (29.97 x 449, 25 x 6, 23.976 x 1, 30 x 1) and bitrate (10.4 x 306, 10.5 x 77, 10.6 x 25, 10.3 x 24, 10.7 x 7, 2.5 x 6, 2.6 x 4, 3.1 x 4, +4 more), so the sample is not a controlled transform.
- Window coverage is sampled, not full-film: median 66.4894% per record, p10 32.9666%, p90 77.27762%; 0.0% of rows are below 20% and 0.0% below 10%; median unobserved gap between windows is 7.0 s. Window rates describe those windows; a full-film census, when present, is reported separately.
- 0 extra record(s) in 0 duplicate group(s) share media; unique media after dedupe is 457.
- Still/video overlap: 40678 still record(s), 40221 still-only, are a separate single-frame lane and never enter these aggregates.

## Coverage

Per-record coverage distribution over the deduped records. The unobserved gap is the median time between consecutive sampled windows, derived from runtime, window count and sampled seconds.

| statistic | coverage_pct |
| --- | --- |
| min | 21.2 |
| p10 | 33.0 |
| median | 66.5 |
| p90 | 77.3 |
| max | 90.0 |
| below 20% | 0.0% |
| below 10% | 0.0% |
| median unobserved gap between windows | 7.0 s |

## Full-film census

Film-level evidence: 431 of 457 video-measured records (94.3%) on shots.net have a full-runtime census record. Census values are **film-level**: every cut candidate in the file was counted and the appearance series is time-weighted over the whole runtime, so `decodeCoverageFraction` is 1.000000. The `full_cuts_per_min` column is that film-level rate; every `sampled_cut_candidates_per_min` value remains a sample of its windows.

Census cut candidates are still ffmpeg scene-score exceedances, not verified edits; fast movement, flashes, transitions and compression can exceed the threshold. A `strobe` record's rate describes strobe-like candidate density and is **not comparable to a cut rate**, so strobe records are excluded from the range below and reported separately.

| statistic | full_cuts_per_min (non-strobe) |
| --- | --- |
| n | 394 |
| min | 0.00 |
| p10 | 2.55 |
| median | 23.42 |
| p90 | 45.95 |
| max | 112.02 |

Range endpoints: min 0.00 (`behind-the-scenes-of-wear-your-best-life`), max 112.02 (`come-back-louder`); n counts non-strobe records only.

Strobe block (never pooled with the cut-rate range above): 37 record(s), listed by id below. Its own range is min 4.33, median 39.60, max 175.53.

| strobe id | full_cuts_per_min | median_gap_frames | burst_fraction |
| --- | --- | --- | --- |
| 100-real-with-pamela-anderson | 41.92 | 15.0 | 0.524 |
| 4th-down | 71.71 | 14.0 | 0.556 |
| a-holiday-of-treats | 71.71 | 3.0 | 0.722 |
| a-strangers-house | 42.17 | 11.0 | 0.565 |
| always-been-here | 21.94 | 27.5 | 0.545 |
| behind-the-scenes-of-petbarn-brand-world | 80.69 | 11.5 | 0.571 |
| billboard | 27.04 | 5.0 | 0.778 |
| bold-tastes-of-tokyo | 82.78 | 5.0 | 0.752 |
| film-study | 25.93 | 24.5 | 0.615 |
| here-for-all-of-it | 19.12 | 24.0 | 0.700 |
| hero-film-4 | 82.01 | 12.5 | 0.585 |
| holiday-gifting | 39.89 | 13.0 | 0.600 |
| i-give-everything-i-have-2-u | 7.91 | 5.5 | 0.800 |
| jen-beatties-story-to-screen-for-breast-cancer-awareness | 78.71 | 13.0 | 0.615 |
| kids-room-casino | 28.02 | 10.0 | 0.571 |
| lego-header-1 | 87.76 | 17.0 | 0.610 |
| living-planet-report-2026 | 111.90 | 3.0 | 0.744 |
| master-of-precision | 54.41 | 21.0 | 0.600 |
| powered-by-terry | 34.64 | 5.0 | 0.719 |
| relentless | 36.62 | 3.0 | 0.868 |
| shes-got-range-directors-cut | 69.01 | 10.0 | 0.623 |
| stories-from-the-hive-danielle | 46.97 | 5.0 | 0.894 |
| stories-from-the-hive-sarah | 33.98 | 5.0 | 0.765 |
| sugar-on-my-tongue | 39.60 | 14.0 | 0.519 |
| take-your-shot | 19.98 | 52.0 | 0.550 |
| thats-proper-chels-ask-joao | 10.09 | 114.5 | 0.571 |
| thats-proper-chels-ellie-alyssa | 25.38 | 34.0 | 0.545 |
| thats-proper-chels-intro | 4.33 | 2.0 | 1.000 |
| the-aftermath | 35.90 | 20.0 | 0.750 |
| the-best-part-of-tinder-isnt-on-tinder | 175.53 | 5.0 | 0.705 |
| the-greatest-2 | 26.88 | 3.0 | 0.714 |
| the-last-1 | 69.24 | 5.0 | 0.761 |
| the-lego-holiday-workshop-2026 | 64.01 | 6.0 | 0.709 |
| the-most-vicious-cycle | 21.30 | 2.0 | 0.955 |
| the-race-between-knowledge-and-chaos | 36.91 | 10.5 | 0.622 |
| the-run-off-moment | 7.33 | 5.0 | 0.750 |
| we-are | 95.88 | 10.0 | 0.542 |

## Census reconciliation

Window values are samples of the runtime; census values cover the film. Relative error is `(window_rate - full_rate) / full_rate`, so a positive value means the window sample overestimated the film and a negative value means it underestimated it.

- comparable records: 410; skipped for a zero full-film rate: 21
- median |relative error|: 0.128; p90 |relative error|: 0.432; max |relative error|: 1.000
- window estimate off by more than 25%: 93 of 410 (22.7%); window higher on 248 record(s), lower on 162
- ordering changes beyond five positions when ranked by each rate: 326

| id | window_cuts_per_min | full_cuts_per_min | relative_error | direction |
| --- | --- | --- | --- | --- |
| detective | 0.00 | 1.00 | -1.000 | window lower |
| get-ahead | 0.00 | 2.53 | -1.000 | window lower |
| kiss | 0.00 | 3.00 | -1.000 | window lower |
| park-2 | 0.00 | 2.99 | -1.000 | window lower |
| thats-proper-chels-intro | 0.00 | 4.33 | -1.000 | window lower |
| the-handmade-series-ep-1-choosing-music-going-nowhere | 0.00 | 2.01 | -1.000 | window lower |
| the-handmade-series-ep-2-what-does-premium-sound-like | 0.00 | 1.99 | -1.000 | window lower |
| the-handmade-series-ep-3-whose-taste-wins | 0.00 | 1.75 | -1.000 | window lower |
| the-handmade-series-ep-4-the-audience-has-entered | 0.00 | 1.85 | -1.000 | window lower |
| sugar-on-my-tongue | 76.50 | 39.60 | 0.932 | window higher |
| the-most-vicious-cycle | 1.50 | 21.30 | -0.930 | window lower |
| i-give-everything-i-have-2-u | 1.50 | 7.91 | -0.810 | window lower |
| mother-of-all-mammograms-comfort | 6.00 | 3.34 | 0.798 | window higher |
| megan-thee-stallion-hottieween-trailer | 6.00 | 26.30 | -0.772 | window lower |
| a-who-knew-carol | 1.50 | 0.86 | 0.735 | window higher |
| mother-of-all-mammograms | 3.00 | 1.80 | 0.663 | window higher |
| forever-3 | 9.00 | 24.49 | -0.632 | window lower |
| love-is-a-gift-you-me | 33.00 | 20.22 | 0.632 | window higher |
| the-most-dangerous-time-of-year-1 | 1.50 | 4.01 | -0.626 | window lower |
| the-greatest-2 | 43.50 | 26.88 | 0.618 | window higher |
| thats-proper-chels-ask-joao | 4.00 | 10.09 | -0.603 | window lower |
| bold-tastes-of-tokyo | 36.00 | 82.78 | -0.565 | window lower |
| billboard | 12.00 | 27.04 | -0.556 | window lower |
| joe-cool | 12.00 | 7.90 | 0.519 | window higher |
| google-translate-live-translate | 22.50 | 14.81 | 0.519 | window higher |
| from-vegas-for-vegas-always-vegas-group-shot | 36.00 | 23.91 | 0.506 | window higher |
| pintxos | 18.00 | 11.97 | 0.504 | window higher |
| the-aftermath | 54.00 | 35.90 | 0.504 | window higher |
| give-your-gift | 9.00 | 5.99 | 0.503 | window higher |
| incredibly-generous-ice-cream | 1.50 | 1.00 | 0.503 | window higher |
| all-of-christmas-at-asda-price-boom-dinner-table | 27.00 | 17.96 | 0.503 | window higher |
| tronen | 3.00 | 2.00 | 0.503 | window higher |
| wear-your-best-life | 3.00 | 2.00 | 0.502 | window higher |
| enel | 7.50 | 5.00 | 0.499 | window higher |
| costume-party | 18.00 | 12.02 | 0.498 | window higher |
| in-the-train | 6.00 | 4.01 | 0.498 | window higher |
| pastry-shop | 6.00 | 4.01 | 0.498 | window higher |
| take-me-home-4-christmas | 37.50 | 25.25 | 0.485 | window higher |
| the-spirit-of-dark-and-lonely-water | 4.50 | 8.10 | -0.444 | window lower |
| powered-by-terry | 19.50 | 34.64 | -0.437 | window lower |
| hypersleep | 4.50 | 7.98 | -0.436 | window lower |
| asian-paints-taoyyari-shuru-tyohaar-shuru | 21.00 | 14.67 | 0.431 | window higher |
| it-gets-worse | 13.50 | 23.57 | -0.427 | window lower |
| making-air-free | 21.00 | 36.15 | -0.419 | window lower |
| a-warehouse-christmas | 4.50 | 7.71 | -0.416 | window lower |
| change-me | 7.50 | 12.78 | -0.413 | window lower |
| the-beauty-of-sport | 22.50 | 37.31 | -0.397 | window lower |
| the-one-feat-nia-long | 2.00 | 1.43 | 0.395 | window higher |
| you-will-die | 7.50 | 12.07 | -0.379 | window lower |
| snowy-roads-are-scary-ghost | 6.00 | 4.38 | 0.371 | window higher |
| mission-assist-auto-30 | 18.00 | 27.93 | -0.355 | window lower |
| listen-to-jordic | 3.00 | 4.63 | -0.352 | window lower |
| a-holiday-of-treats | 96.00 | 71.71 | 0.339 | window higher |
| thats-proper-chels-cole-morgan | 12.00 | 18.07 | -0.336 | window lower |
| spiris-climber | 24.00 | 18.02 | 0.332 | window higher |
| 4th-down | 48.00 | 71.71 | -0.331 | window lower |
| tapped-to-pay-go-watch-them-play-20 | 24.00 | 18.07 | 0.328 | window higher |
| its-kinda-unreal-winter | 45.00 | 33.91 | 0.327 | window higher |
| selfie-for-all | 21.00 | 15.85 | 0.325 | window higher |
| long-live-joy | 13.50 | 19.96 | -0.324 | window lower |
| mule | 4.50 | 3.41 | 0.320 | window higher |
| qualia-nad | 42.00 | 31.91 | 0.316 | window higher |
| whats-green-and-looks-like-a-sock | 1.50 | 1.14 | 0.315 | window higher |
| pillow-talk | 3.00 | 2.29 | 0.311 | window higher |
| taking-on-akuma | 33.00 | 47.87 | -0.311 | window lower |
| new-exxon-el-nino-commercial | 31.50 | 45.43 | -0.307 | window lower |
| film-study | 18.00 | 25.93 | -0.306 | window lower |
| relentless | 25.50 | 36.62 | -0.304 | window lower |
| share-the-warmth-heatball-fight | 6.00 | 8.53 | -0.297 | window lower |
| attention-to-detail | 1.50 | 2.12 | -0.293 | window lower |
| obsession-comes-around | 24.00 | 33.91 | -0.292 | window lower |
| lets-dance-holiday | 39.00 | 30.22 | 0.290 | window higher |
| living-planet-report-2026 | 79.50 | 111.90 | -0.290 | window lower |
| go-ocean-fund-the-planets-blue-lung | 9.00 | 12.66 | -0.289 | window lower |
| car-4 | 6.00 | 8.43 | -0.288 | window lower |
| low-fruit | 16.50 | 12.81 | 0.288 | window higher |
| big-delivery | 21.00 | 29.49 | -0.288 | window lower |
| some-really-good-sheet | 1.50 | 1.17 | 0.285 | window higher |
| kids-room-casino | 36.00 | 28.02 | 0.285 | window higher |
| every-cat-is-an-individual | 6.00 | 8.37 | -0.283 | window lower |
| mother-of-all-mammograms-advanced-tech | 3.00 | 2.36 | 0.273 | window higher |
| andrew | 12.00 | 16.43 | -0.270 | window lower |
| family-4 | 12.00 | 16.35 | -0.266 | window lower |
| nike-x-cortiez | 40.50 | 31.99 | 0.266 | window higher |
| fight-cancer | 6.00 | 4.74 | 0.266 | window higher |
| dont-crack-trailer | 48.00 | 37.93 | 0.266 | window higher |
| behind-the-scenes-of-petbarn-brand-world | 102.00 | 80.69 | 0.264 | window higher |
| pubscription | 15.00 | 20.25 | -0.259 | window lower |
| vision | 12.00 | 9.54 | 0.258 | window higher |
| dinner-is-served | 3.00 | 2.39 | 0.255 | window higher |
| auto-1 | 60.00 | 47.87 | 0.253 | window higher |
| the-bend | 15.00 | 11.98 | 0.252 | window higher |
| episode-1-john-stamos-is-pantenes-ultimate-ambassador | 19.50 | 26.06 | -0.252 | window lower |

| id | window_rank | full_rank | position_change | window_cuts_per_min | full_cuts_per_min |
| --- | --- | --- | --- | --- | --- |
| megan-thee-stallion-hottieween-trailer | 366 | 188 | 178 | 6.00 | 26.30 |
| powered-by-terry | 266 | 109 | 157 | 19.50 | 34.64 |
| making-air-free | 252 | 100 | 152 | 21.00 | 36.15 |
| the-most-vicious-cycle | 399 | 251 | 148 | 1.50 | 21.30 |
| the-beauty-of-sport | 236 | 93 | 143 | 22.50 | 37.31 |
| billboard | 318 | 186 | 132 | 12.00 | 27.04 |
| forever-3 | 341 | 209 | 132 | 9.00 | 24.49 |
| love-is-a-gift-you-me | 140 | 261 | -121 | 33.00 | 20.22 |
| the-greatest-2 | 75 | 187 | -112 | 43.50 | 26.88 |
| from-vegas-for-vegas-always-vegas-group-shot | 112 | 223 | -111 | 36.00 | 23.91 |
| all-of-christmas-at-asda-price-boom-dinner-table | 178 | 287 | -109 | 27.00 | 17.96 |
| mission-assist-auto-30 | 282 | 180 | 102 | 18.00 | 27.93 |
| bold-tastes-of-tokyo | 109 | 8 | 101 | 36.00 | 82.78 |
| new-exxon-el-nino-commercial | 158 | 57 | 101 | 31.50 | 45.43 |
| relentless | 198 | 98 | 100 | 25.50 | 36.62 |
| taking-on-akuma | 146 | 46 | 100 | 33.00 | 47.87 |
| take-me-home-4-christmas | 104 | 203 | -99 | 37.50 | 25.25 |
| obsession-comes-around | 218 | 121 | 97 | 24.00 | 33.91 |
| it-gets-worse | 310 | 226 | 84 | 13.50 | 23.57 |
| big-delivery | 246 | 164 | 82 | 21.00 | 29.49 |
| (+306 more rank changes in `aggregate.json`) | | | | | |

## Editorial structure

Derived offline from each record's stored census cut candidates and 1 Hz appearance series (pure function, no media re-decode). A `shot` is the interval between consecutive detected scene changes, a lower bound on edits; `shotCount` is always candidates + 1.

Shot-length distribution across 394 non-strobe clip(s), using each clip's median shot length. Strobe records are excluded because their candidate intervals are frame-scale.

| statistic | median_shot_s |
| --- | --- |
| n | 394 |
| min | 0.40 |
| p10 | 0.87 |
| median | 1.87 |
| p90 | 10.05 |
| max | 120.30 |

Median cut rate (non-strobe): 23.42 cuts/min. Shot counts across clips: 1–137.

Pace trend, last third ÷ first third with a ±15% band: accelerating 121, steady 69, decelerating 189, unclassified 52 (unclassified means no cut candidate in the first third, so no ratio exists).

Clips whose last third is >2× their first third (>2×; non-strobe):

| id | pace_drift_ratio | median_shot_s |
| --- | --- | --- |
| all-of-christmas-at-asda-price-boom-decorating | 12.00 | 0.77 |
| nike-x-cortiez | 7.12 | 0.47 |
| whats-for-hockey | 4.67 | 1.69 |
| tiramisu | 4.50 | 0.78 |
| vision | 4.50 | 1.33 |
| favorite-tia | 4.00 | 3.70 |
| pubscription | 4.00 | 1.63 |
| now-youre-cooking-1 | 3.75 | 1.15 |
| hypersleep | 3.50 | 3.44 |
| telenovela | 3.00 | 1.85 |
| love-is-a-gift-you-me | 2.67 | 1.69 |
| special-olympics-30 | 2.67 | 1.40 |
| thats-proper-chels-cole-morgan | 2.50 | 2.44 |
| the-beauty-of-sport | 2.50 | 0.87 |
| the-elephant | 2.50 | 2.00 |
| making-air-free | 2.44 | 1.10 |
| tales-of-argos-past | 2.40 | 1.35 |
| the-real-gusto-italo-americano | 2.40 | 1.72 |
| skimmed | 2.33 | 1.03 |
| zubin | 2.25 | 1.89 |
| for-gifts-theyll-really-love | 2.17 | 1.74 |
| andrew | 2.00 | 2.74 |
| bedtime-1 | 2.00 | 3.10 |
| car-4 | 2.00 | 5.17 |
| hosting-1 | 2.00 | 1.65 |
| its-about-time-1 | 2.00 | 4.94 |
| kfc-x-marvel-studios-avengers-doomsday | 2.00 | 4.32 |
| miss-it-already | 2.00 | 1.80 |
| park-1 | 2.00 | 5.79 |
| pringa | 2.00 | 2.24 |
| scene-of-the-crime | 2.00 | 1.77 |
| tapped-to-pay-go-watch-them-play-19 | 2.00 | 2.05 |
| tapped-to-pay-go-watch-them-play-22 | 2.00 | 2.92 |
| the-ay-ay-ay-ay | 2.00 | 1.95 |
| xbox-series-x-bite | 2.00 | 3.97 |

Clips whose last third is <0.5× their first third (<0.5×; non-strobe):

| id | pace_drift_ratio | median_shot_s |
| --- | --- | --- |
| classic-fm-christmas-aled-jones-defrosts | 0.00 | 3.00 |
| costume-party | 0.00 | 1.25 |
| dinner-is-served | 0.00 | 16.95 |
| enel | 0.00 | 3.62 |
| fight-cancer | 0.00 | 8.32 |
| good-read | 0.00 | 1.95 |
| hara-and-the-hare | 0.00 | 1.43 |
| in-the-train | 0.00 | 7.49 |
| its-that-simple | 0.00 | 2.65 |
| joe-cool | 0.00 | 3.44 |
| life-of-scores | 0.00 | 2.84 |
| mother-of-all-mammograms | 0.00 | 16.63 |
| mother-of-all-mammograms-advanced-tech | 0.00 | 12.73 |
| mother-of-all-mammograms-comfort | 0.00 | 8.99 |
| nimm-den-stress-nicht-mit-ins-bett-woman | 0.00 | 9.24 |
| notification-melody | 0.00 | 1.18 |
| novela | 0.00 | 11.18 |
| pastry-shop | 0.00 | 7.49 |
| pillow-talk | 0.00 | 19.19 |
| some-really-good-sheet | 0.00 | 25.70 |
| sunbathing-2 | 0.00 | 2.09 |
| the-one-feat-nia-long | 0.00 | 20.93 |
| the-ten-month-nap | 0.00 | 9.72 |
| the-wrong-address | 0.00 | 1.80 |
| tronen | 0.00 | 15.03 |
| opus-jazz-miami-city-ballet-gapstudio | 0.04 | 0.77 |
| its-all-you-can-drink-about | 0.18 | 0.40 |
| one-journey-of-many | 0.19 | 1.43 |
| monsters | 0.20 | 1.94 |
| the-class | 0.20 | 4.30 |
| the-pile-1 | 0.25 | 5.04 |
| theres-time-for-everything | 0.25 | 3.85 |
| vibes-1 | 0.25 | 2.00 |
| no-place-like-home | 0.26 | 1.30 |
| google-translate-live-translate | 0.29 | 2.39 |
| we-listen | 0.29 | 1.03 |
| do-not-accept | 0.31 | 0.53 |
| the-prize | 0.31 | 1.42 |
| ahem | 0.33 | 3.44 |
| denial | 0.33 | 1.62 |
| drumming-1 | 0.33 | 2.50 |
| maison-margiela-x-gentle-monster | 0.33 | 0.78 |
| mazda | 0.33 | 1.13 |
| pintxos | 0.33 | 2.04 |
| spacewalk | 0.33 | 2.44 |
| the-next-date | 0.33 | 3.17 |
| tubi-or-you-could-abduction | 0.33 | 4.47 |
| forever-3 | 0.34 | 0.47 |
| drop-the-robot | 0.35 | 1.07 |
| christmas-made-just-right | 0.37 | 1.40 |
| group-hangouts | 0.37 | 1.42 |
| anatomi | 0.38 | 1.94 |
| lets-get-fuzzy | 0.38 | 2.02 |
| the-fabric-of-your-town-unlocked | 0.38 | 1.70 |
| the-womens-health-mens-choir | 0.38 | 1.53 |
| wwf-takes-you-on-a-speed-run-of-the-arctic-before-its-too-late | 0.38 | 1.30 |
| save-jeanie | 0.38 | 1.53 |
| ziggo-priority | 0.38 | 0.83 |
| choked-up | 0.40 | 2.04 |
| december-to-remember-snowball | 0.40 | 1.27 |
| from-vegas-for-vegas-always-vegas-group-shot | 0.40 | 1.50 |
| its-kinda-unreal-winter | 0.40 | 1.47 |
| the-spirit-of-dark-and-lonely-water | 0.40 | 4.50 |
| cartoon | 0.42 | 1.33 |
| from-crisis-to-home | 0.43 | 2.20 |
| hockey-1 | 0.43 | 0.53 |
| in-the-way | 0.43 | 1.28 |
| long-live-joy | 0.43 | 1.80 |
| qualia-nad-mind | 0.43 | 1.80 |
| the-art-of-arrival-henrik-lundqvist | 0.43 | 0.67 |
| josea | 0.44 | 0.93 |
| give-ai-a-break | 0.44 | 3.17 |
| the-making-of-lets-get-fuzzy | 0.47 | 0.62 |
| a-holiday-at-home-chewy-claus | 0.50 | 2.37 |
| arrivals-1 | 0.50 | 2.57 |
| bocata | 0.50 | 1.87 |
| from-vegas-for-vegas-always-vegas-team-members | 0.50 | 0.70 |
| good-move-bumpers | 0.50 | 6.27 |
| holiday-front-yards | 0.50 | 1.30 |
| its-all-in-the-delivery | 0.50 | 1.84 |
| mission-assist-auto-30 | 0.50 | 1.37 |
| mocktail | 0.50 | 1.87 |
| mountain-3 | 0.50 | 3.27 |
| qualia-nad | 0.50 | 1.40 |
| secondhand-skins | 0.50 | 1.48 |
| step-into-the-light | 0.50 | 2.17 |
| tapped-to-pay-go-watch-them-play-20 | 0.50 | 2.14 |
| tender-boyz | 0.50 | 4.07 |
| the-amber-nectar | 0.50 | 3.40 |
| the-christmas-wish | 0.50 | 2.27 |
| the-reunion | 0.50 | 2.12 |
| the-roll | 0.50 | 3.00 |
| tickets | 0.50 | 1.30 |
| to-the-summit-directors-cut-2-52 | 0.50 | 3.95 |
| unexpected-guests | 0.50 | 1.87 |
| wake-up-1 | 0.50 | 1.45 |
| warm-wishes | 0.50 | 1.82 |
| xbox-series-x-bite-behind-the-scenes | 0.50 | 0.80 |

Flicker outliers (median absolute luma delta per second above 0.050; sample instability, not a flicker frequency):

| id | flicker_luma_per_s |
| --- | --- |
| we-are | 0.119 |
| for-days-that-dont-slow-down | 0.119 |
| lets-go | 0.110 |
| 4th-down | 0.101 |
| ask-yourself | 0.099 |
| the-making-of-lets-get-fuzzy | 0.094 |
| xbox-series-x-bite-behind-the-scenes | 0.089 |
| celebrate-being-human | 0.084 |
| beds-1 | 0.083 |
| come-back-louder | 0.081 |
| the-best-part-of-tinder-isnt-on-tinder | 0.077 |
| freaknik-the-wildest-party-never-told-trailer | 0.077 |
| designed-for-artistic-exploration | 0.077 |
| from-vegas-for-vegas-always-vegas-team-members | 0.075 |
| from-vegas-for-vegas-always-vegas-50-year-legacy | 0.074 |
| behind-the-scenes-of-petbarn-brand-world | 0.074 |
| personas | 0.069 |
| unbox-your-potential | 0.066 |
| volvo-xc60 | 0.064 |
| relx-wind | 0.063 |
| safety-story-trailer | 0.062 |
| the-king-of-clay | 0.062 |
| year-of-the-horse | 0.062 |
| power-your-legacy | 0.062 |
| combo-1 | 0.062 |
| bold-tastes-of-tokyo | 0.061 |
| built-for-real-life | 0.060 |
| jen-beatties-story-to-screen-for-breast-cancer-awareness | 0.060 |
| ziggo-priority | 0.060 |
| everyones-playing | 0.059 |
| in-lock-step | 0.058 |
| the-right-wave | 0.058 |
| go-beyond-the-grey | 0.058 |
| auto-1 | 0.058 |
| create-the-new | 0.058 |
| maison-margiela-x-gentle-monster | 0.057 |
| home-3 | 0.057 |
| do-not-accept | 0.057 |
| master-of-precision | 0.056 |
| cruise-2026-27-collection | 0.056 |
| agreements-make-history | 0.055 |
| apple-music-rebrand | 0.055 |
| make-it-possible | 0.054 |
| here-for-all-of-it-behind-the-scenes | 0.053 |
| the-swimmer | 0.053 |
| its-all-in-the-delivery | 0.052 |
| joy-of-driving | 0.051 |
| the-prize | 0.051 |
| gloves | 0.051 |
| always-been-here | 0.051 |
| crave | 0.051 |

Strobe records excluded from the shot-length aggregates: `100-real-with-pamela-anderson`, `4th-down`, `a-holiday-of-treats`, `a-strangers-house`, `always-been-here`, `behind-the-scenes-of-petbarn-brand-world`, `billboard`, `bold-tastes-of-tokyo`, `film-study`, `here-for-all-of-it`, `hero-film-4`, `holiday-gifting`, `i-give-everything-i-have-2-u`, `jen-beatties-story-to-screen-for-breast-cancer-awareness`, `kids-room-casino`, `lego-header-1`, `living-planet-report-2026`, `master-of-precision`, `powered-by-terry`, `relentless`, `shes-got-range-directors-cut`, `stories-from-the-hive-danielle`, `stories-from-the-hive-sarah`, `sugar-on-my-tongue`, `take-your-shot`, `thats-proper-chels-ask-joao`, `thats-proper-chels-ellie-alyssa`, `thats-proper-chels-intro`, `the-aftermath`, `the-best-part-of-tinder-isnt-on-tinder`, `the-greatest-2`, `the-last-1`, `the-lego-holiday-workshop-2026`, `the-most-vicious-cycle`, `the-race-between-knowledge-and-chaos`, `the-run-off-moment`, `we-are`.

## Published-still evidence (single-frame only)

Separate lane. A published poster still is not a video frame: these numbers are single-frame image metrics, carry no motion, cut, pacing, or timing evidence, and are never used in the video aggregates above.

- n: 40678
- decode size: stills are measured at the aspect-preserving `160×90` fit; the source dimensions stay in `img_w×img_h`, so the decode size is derived from the source aspect, not stored per record.

| source_img | decode | stills |
| --- | --- | --- |
| 640x352 | 160x88 | 17564 |
| 1920x1080 | 160x90 | 16290 |
| 640x360 | 160x90 | 1563 |
| 1280x720 | 160x90 | 436 |
| 640x480 | 120x90 | 111 |
| 620x349 | 160x90 | 44 |
| 3840x2160 | 160x90 | 39 |
| 1440x810 | 160x90 | 21 |
| 1080x1920 | 51x90 | 18 |
| 1600x900 | 160x90 | 17 |
| 1398x786 | 160x90 | 16 |
| 1422x800 | 160x90 | 16 |
| 1430x804 | 160x90 | 16 |
| 1408x792 | 160x90 | 15 |
| 1406x790 | 160x90 | 14 |
| 1426x802 | 160x90 | 14 |
| 1200x675 | 160x90 | 13 |
| 1376x774 | 160x90 | 13 |
| 1412x794 | 160x90 | 13 |
| 1420x799 | 160x90 | 13 |
| (+3164 more source/decode pairs) | — | — |

- stills carrying no quality flag (used for colour aggregates): 40046
- median meanDisplayLumaProxy: 0.3052

| dominant_hue_family | stills |
| --- | --- |
| blue | 3875 |
| cyan | 2061 |
| green | 2918 |
| magenta | 767 |
| neutral | 13489 |
| orange | 10924 |
| purple | 334 |
| red | 2307 |
| yellow | 3371 |

### Still quality signals

Quality flags are measurements, not verdicts: the record keeps every number above so a consumer can decide. A still carrying any flag is excluded from this section's colour aggregates and counted separately here.

- flagged stills (excluded from colour aggregates): 632 of 40678

| quality flag | stills |
| --- | --- |
| degenerate-histogram | 579 |
| low-information-resolution | 4 |
| near-black-placeholder | 66 |
| near-uniform | 229 |
| near-white-placeholder | 9 |

## Unreadable records

None.

## Explicit non-claims

- No style, aesthetic quality, mood, lighting, camera/lens, editorial intent, authorship, identity, or creative-origin inference is made from these numbers.
- Display-RGB luma/saturation and cut candidates are numeric proxies only, not semantic labels.
- Windows are sampled and census values are film-level; a window rate is a sample, not a film rate, and census cut candidates are still scene-score exceedances rather than verified edits.
- Public availability is not a licence: `rightsStatus` remains `review-required`, and reuse needs its own review.
- `downloadAllowed` was false on the platform for every sampled clip; that fact is recorded, not worked around.
- Published stills are single images, not video frames, and carry no motion, cut, pacing, sequence, or timing evidence.
- Catalog metadata is self-reported by shots.net and is not independently verified.
- Downloaded media, frames, thumbnails, and audio are never retained.
