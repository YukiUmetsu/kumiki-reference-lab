# Directors' Library — measured video and still evidence report

This deliverable tabulates only what the committed evidence records contain: WordPress catalogue metadata, sampled source-PTS numeric probes of the public YouTube rendition, and one measured, published poster still per item where present. It makes no aesthetic, stylistic, intentional, authorship, or quality claim.

## Provenance

- Catalog items: 5412
- Video-measured records: 160
- Unique video media after dedupe: 160 (0 extra record(s) in 0 duplicate group(s))
- Still-measured records: 5348
- Still-only records (no matching video record): 5193
- Skipped rows (stills index context): 0
- Failed acquisitions (stills index context): 64
- Skipped rows (video index context): 211
- Failed acquisitions (video index context): 2
- Catalogue items without a usable poster: 0
- Unreadable records: 0
- generatedAt: 2026-11-16T16:19:55.996249Z
- Skip reasons (video index): resume-existing-record x 143, unsupported-vimeo x 68
- Per-row provider labels: unsupported-embed x 5348
- Provider split (measured videos): youtube x 160
- `--top 50` applied: the first 50 of 160 video-measured rows are tabulated below; `aggregate.json` holds all.
- `--top 50` applied: the first 50 of 5348 measured stills are tabulated below; `aggregate.json` holds all.

The catalogue is the site's WordPress video post type. No ACF director/duration/brand fields are exposed by the REST API, so those fields stay null rather than being invented.

Reproduce the inputs and this report with:

```bash
python scripts/research_wordpress_stills.py catalog --site directorslibrary --out research/analysis/directorslibrary/catalog.json
python scripts/research_wordpress_stills.py collect --site directorslibrary --catalog research/analysis/directorslibrary/catalog.json --out-dir research/analysis/directorslibrary --acknowledge-rights
python scripts/research_wordpress_stills.py stills --site directorslibrary --catalog research/analysis/directorslibrary/catalog.json --out-dir research/analysis/directorslibrary --resume
python scripts/research_wordpress_stills.py report --site directorslibrary --out-dir research/analysis/directorslibrary --top 50
```

## Per-video analysis

160 video-measured record(s), newest catalogue row first. All columns are numeric record fields from the sampled source-PTS windows of the public YouTube rendition; `duration_s` is the decoded local source duration, not a catalogue value.

| post_id | slug | title | provider | published | duration_s | resolution | download_mb | windows | coverage_pct | candidates_n | sampled_cut_candidates_per_min | full_cuts_per_min | full_vs_window | median_shot_s | shots_lt_0_5s_pct | pace_trend | flicker | ci95 | burst | gap_frames | within_shot_pairs | cut_sep_pairs | delta_basis_pairs | validity | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 82133 | tender-loving-care-2 | Tender Loving Care | youtube | 2026-11-05T12:05:25 | 153.27 | 1280x720 | 8.1 | 4 | 26.1 | 10 | 15.00 | 22.31 | -33% | 1.83 | 0.0 | decelerating | 0.012 | 7.19-27.59 | 0.000 | 86.0 | 34 | 10 | 34 | — | 0.1938 | 0.4597 | 0.0599 |
| 81873 | nuisance-bear | Nuisance Bear | youtube | 2026-11-11T04:00:00 | 133.14 | 1280x720 | 8.3 | 4 | 30.0 | 9 | 13.50 | 20.73 | -35% | 2.04 | 0.0 | accelerating | 0.010 | 4.25-28.80 | 0.000 | 74.5 | 35 | 9 | 35 | — | 0.1918 | 0.2079 | 0.0314 |
| 81855 | the-siege-of-paradise | The Siege of Paradise | youtube | 2026-11-08T04:21:00 | 125.16 | 1280x720 | 14.4 | 4 | 32.0 | 35 | 52.50 | 42.19 | +24% | 1.20 | 12.4 | steady | 0.037 | 27.87-84.22 | 0.000 | 23.5 | 14 | 30 | 14 | — | 0.2906 | 0.3631 | 0.0627 |
| 81849 | ah-girl | Ah Girl | youtube | 2026-11-04T04:10:00 | 203.89 | 1280x720 | 17.7 | 4 | 19.6 | 7 | 10.50 | 7.36 | +43% | 6.19 | 0.0 | steady | 0.009 | 4.22-21.63 | 0.000 | 669.0 | 37 | 7 | 37 | low-coverage | 0.1617 | 0.2806 | 0.0406 |
| 81843 | the-quiet-beekeeper | The Quiet Beekeeper | youtube | 2026-11-01T04:00:00 | 91.74 | 1280x720 | 14.7 | 4 | 43.6 | 15 | 22.50 | — | — | — | — | — | — | 12.59-37.11 | 0.133 | 71.0 | 31 | 13 | 31 | — | 0.1749 | 0.4279 | 0.0558 |
| 81810 | tarantino-lisa | ‘Tarantino’ LISA | youtube | 2026-11-05T12:21:17 | 217.04 | 1280x720 | 24.1 | 4 | 18.4 | 9 | 13.50 | — | — | — | — | — | — | 6.17-25.63 | 0.000 | 114.0 | 35 | 9 | 35 | low-coverage | 0.2007 | 0.3283 | 0.0776 |
| 81538 | is-it-that-deep-cat-burns | ‘Is it That Deep?’ Cat Burns | youtube | 2026-10-30T09:00:00 | 172.78 | 1280x720 | 25.2 | 4 | 23.2 | 2 | 3.00 | 1.39 | +116% | 36.52 | 40.0 | steady | 0.013 | 0.36-10.84 | 0.000 | 1398.0 | 42 | 2 | 42 | low-coverage | 0.2877 | 0.3881 | 0.1409 |
| 81536 | gas-bicep | ‘Gas’ Bicep | youtube | 2026-10-29T09:00:00 | 253.31 | 960x720 | 25.2 | 4 | 15.8 | 13 | 19.50 | 18.95 | +3% | 2.20 | 17.3 | accelerating | 0.035 | 10.38-33.35 | 0.000 | 107.5 | 32 | 12 | 32 | low-coverage | 0.2297 | 0.2456 | 0.0997 |
| 81534 | dead-hand-freestyle-irko | ‘Dead Hand Freestyle’ Irko | youtube | 2026-10-26T22:10:31 | 177.63 | 1280x720 | 18.2 | 4 | 22.5 | 19 | 28.50 | 34.79 | -18% | 1.19 | 6.7 | accelerating | 0.021 | 6.27-59.87 | 0.000 | 28.0 | 25 | 19 | 25 | low-coverage | 0.6143 | 0.0266 | 0.0792 |
| 81514 | mexicanamerican | Mexicanamerican | youtube | 2026-10-25T19:16:44 | 127.48 | 1280x720 | 30.6 | 4 | 31.4 | 7 | 10.50 | 11.77 | -11% | 3.34 | 0.0 | accelerating | 0.034 | 2.39-24.87 | 0.000 | 78.0 | 37 | 7 | 37 | — | 0.2310 | 0.2230 | 0.1260 |
| 81344 | coda-dpat | ‘Coda’ Dpat | youtube | 2026-10-21T11:00:00 | 238.52 | 960x720 | 27.0 | 4 | 16.8 | 10 | 15.00 | 24.15 | -38% | 1.38 | 20.6 | decelerating | 0.013 | 7.19-27.59 | 0.300 | 69.0 | 36 | 8 | 36 | low-coverage | 0.2489 | 0.3726 | 0.0256 |
| 81251 | hearing | Hearing | youtube | 2026-10-19T06:43:00 | 146.26 | 1280x720 | 15.8 | 4 | 27.3 | 5 | 7.50 | 5.33 | +41% | 7.92 | 0.0 | accelerating | 0.001 | 1.80-18.76 | 0.000 | 442.0 | 39 | 5 | 39 | — | 0.1347 | 0.3493 | 0.0209 |
| 81244 | i-see-buildings-fall-like-lightning | I See Buildings Fall Like Lightning | youtube | 2026-10-15T18:34:32 | 126.80 | 1280x720 | 15.3 | 4 | 31.5 | 38 | 57.00 | 53.47 | +7% | 0.92 | 9.6 | accelerating | 0.084 | 40.34-78.24 | 0.000 | 16.0 | 15 | 29 | 15 | — | 0.2677 | 0.3466 | 0.1464 |
| 81235 | congo-boy | Congo Boy | youtube | 2026-08-04T16:57:27 | 91.32 | 1280x720 | 18.1 | 4 | 43.8 | 17 | 25.50 | — | — | — | — | — | — | 14.85-40.83 | 0.000 | 51.0 | 27 | 17 | 27 | — | 0.2094 | 0.3753 | 0.0923 |
| 81233 | curiosity-equinor | ‘Curiosity’ Equinor | youtube | 2026-10-19T15:00:33 | 90.09 | 1280x720 | 14.1 | 4 | 44.4 | 25 | 37.50 | 34.63 | +8% | 1.28 | 18.9 | decelerating | 0.029 | 19.49-61.81 | 0.240 | 42.0 | 25 | 19 | 25 | — | 0.2028 | 0.3706 | 0.0727 |
| 81181 | blue-girl-in-red | ‘blue’ girl in red | youtube | 2026-10-16T13:14:13 | 249.78 | 1080x720 | 21.1 | 4 | 16.0 | 15 | 22.50 | 86.96 | -74% | 0.08 | 77.7 | accelerating | 0.018 | 6.12-46.65 | 0.000 | 40.0 | 30 | 14 | 30 | low-coverage | 0.1913 | 0.3615 | 0.0575 |
| 81129 | straight-circle | Straight Circle | youtube | 2026-09-08T23:41:44 | 133.98 | 1280x720 | 9.3 | 4 | 29.9 | 22 | 33.00 | 26.42 | +25% | 1.71 | 3.3 | accelerating | 0.009 | 13.58-59.74 | 0.000 | 29.0 | 26 | 18 | 26 | — | 0.2816 | 0.3732 | 0.0720 |
| 81120 | queen-at-sea | Queen at Sea | youtube | 2026-08-27T23:36:43 | 118.31 | 1280x720 | 12.9 | 4 | 33.8 | 12 | 18.00 | — | — | — | — | — | — | 9.30-31.44 | 0.000 | 106.0 | 32 | 12 | 32 | — | 0.2344 | 0.3587 | 0.0342 |
| 81104 | 9-temples-to-heaven | 9 Temples to Heaven | youtube | 2026-09-05T23:32:07 | 125.53 | 1280x720 | 13.6 | 4 | 31.9 | 14 | 21.00 | 21.99 | -4% | 1.96 | 0.0 | accelerating | 0.010 | 11.26-35.57 | 0.000 | 50.0 | 31 | 13 | 31 | — | 0.3693 | 0.3482 | 0.0260 |
| 81096 | minotaur | Minotaur | youtube | 2026-10-12T05:00:00 | 108.65 | 1280x720 | 7.3 | 4 | 36.8 | 19 | 28.50 | 25.96 | +10% | 1.33 | 4.2 | accelerating | 0.017 | 7.10-58.71 | 0.000 | 27.0 | 28 | 16 | 28 | — | 0.1321 | 0.3413 | 0.0485 |
| 81087 | forever-your-maternal-animal | Forever Your Maternal Animal | youtube | 2026-05-22T22:59:00 | 105.72 | 1280x720 | 15.8 | 4 | 37.8 | 16 | 24.00 | 23.27 | +3% | 2.04 | 2.4 | decelerating | 0.028 | 12.89-40.17 | 0.000 | 49.0 | 28 | 16 | 28 | — | 0.1815 | 0.3172 | 0.1071 |
| 81067 | club-kid | Club Kid | youtube | 2026-08-19T22:40:00 | 131.94 | 1280x720 | 11.8 | 4 | 30.3 | 6 | 9.00 | — | — | — | — | — | — | 2.99-20.16 | 0.000 | 130.0 | 38 | 6 | 38 | — | 0.1557 | 0.4177 | 0.0833 |
| 80878 | paper-tiger | Paper Tiger | youtube | 2026-09-22T18:16:00 | 129.17 | 1280x720 | 7.5 | 4 | 31.0 | 11 | 16.50 | 15.79 | +4% | 1.92 | 0.0 | accelerating | 0.027 | 8.24-29.52 | 0.000 | 80.5 | 34 | 10 | 34 | — | 0.1293 | 0.3187 | 0.0519 |
| 80875 | the-further-mis-adventures-of-cliff-booth | The Further Mis-Adventures of Cliff Booth | youtube | 2026-09-21T18:12:58 | 90.05 | 1280x676 | 7.9 | 4 | 44.4 | 15 | 22.50 | 19.32 | +16% | 1.44 | 26.7 | decelerating | 0.030 | 5.09-48.18 | 0.400 | 27.5 | 34 | 10 | 34 | — | 0.1388 | 0.4602 | 0.0710 |
| 80862 | all-of-a-sudden | All of a Sudden | youtube | 2026-09-10T17:33:00 | 126.43 | 1280x720 | 19.7 | 4 | 31.6 | 21 | 31.50 | 20.41 | +54% | 1.62 | 0.0 | accelerating | 0.014 | 10.82-60.19 | 0.000 | 34.0 | 24 | 20 | 24 | — | 0.2341 | 0.3528 | 0.0356 |
| 80821 | cant-wait-andy | ‘Can’t Wait’ ANDY | youtube | 2026-10-08T06:00:00 | 228.90 | 1280x720 | 26.8 | 4 | 17.5 | 8 | 12.00 | 22.28 | -46% | 1.66 | 10.5 | accelerating | 0.029 | 1.58-29.79 | 0.000 | 53.0 | 36 | 8 | 36 | low-coverage | 0.1596 | 0.3021 | 0.0930 |
| 80790 | small-world-mette | ‘Small World’ METTE | youtube | 2026-10-08T18:00:00 | 174.94 | 960x720 | 23.8 | 4 | 22.9 | 12 | 18.00 | 18.86 | -5% | 1.71 | 3.6 | steady | 0.026 | 3.21-40.85 | 0.167 | 49.0 | 34 | 10 | 34 | low-coverage | 0.2243 | 0.3592 | 0.1073 |
| 80783 | painkiller-joy-crookes | ‘Painkiller’ Joy Crookes | youtube | 2026-10-07T06:00:00 | 253.93 | 1198x720 | 28.3 | 4 | 15.8 | 19 | 28.50 | 28.12 | +1% | 1.61 | 5.0 | decelerating | 0.045 | 16.96-44.78 | 0.000 | 40.5 | 26 | 18 | 26 | low-coverage | 0.2044 | 0.4630 | 0.1198 |
| 80727 | already-gone-orville-peck | ‘Already Gone’ Orville Peck | youtube | 2026-10-10T18:00:00 | 192.73 | 1280x720 | 21.2 | 4 | 20.8 | 25 | 37.50 | 33.00 | +14% | 0.88 | 15.9 | accelerating | 0.019 | 11.08-73.16 | 0.000 | 18.0 | 26 | 18 | 26 | low-coverage | 0.2987 | 0.3089 | 0.0734 |
| 80725 | innocent-smile-skepta | ‘Innocent Smile’ Skepta | youtube | 2026-10-06T18:00:00 | 158.96 | 1200x720 | 19.1 | 4 | 25.2 | 34 | 51.00 | 43.78 | +16% | 0.62 | 39.3 | steady | 0.021 | 35.32-71.27 | 0.176 | 20.0 | 21 | 23 | 21 | — | 0.1507 | 0.3654 | 0.0854 |
| 80692 | air-lemonder-viper-bicep | ‘Air’ ‘Lemonder’ & ‘Viper’ BICEP | youtube | 2026-10-05T06:00:00 | 285.09 | 1280x720 | 32.8 | 4 | 14.0 | 7 | 10.50 | 18.31 | -43% | 0.58 | 44.3 | accelerating | 0.028 | 4.22-21.63 | 0.571 | 108.5 | 39 | 5 | 39 | burst-heavy, low-coverage | 0.1684 | 0.4491 | 0.1151 |
| 80688 | tiramisu-oat-cult | ‘Tiramisù’ Oat Cult | youtube | 2026-10-06T06:00:00 | 110.06 | 960x720 | 10.7 | 4 | 36.3 | 26 | 39.00 | 35.98 | +8% | 0.80 | 28.4 | accelerating | 0.012 | 4.76-84.94 | 0.000 | 19.0 | 25 | 19 | 25 | — | 0.2267 | 0.0000 | 0.0480 |
| 80677 | a24-meets-dior | A24 Meets Dior | youtube | 2026-10-11T18:00:00 | 141.39 | 1280x720 | 15.0 | 4 | 28.3 | 27 | 40.50 | 35.65 | +14% | 0.84 | 35.3 | accelerating | 0.019 | 19.07-69.09 | 0.222 | 20.5 | 24 | 20 | 24 | — | 0.3380 | 0.4489 | 0.0627 |
| 80582 | union-county | Union County | youtube | 2026-07-01T01:38:10 | 147.63 | 1280x720 | 8.4 | 4 | 27.1 | 11 | 16.50 | 16.26 | +1% | 2.21 | 2.4 | decelerating | 0.005 | 4.04-36.13 | 0.182 | 62.5 | 34 | 10 | 34 | — | 0.2104 | 0.2116 | 0.0427 |
| 80572 | american-doctor | American Doctor | youtube | 2026-08-05T01:35:54 | 143.29 | 1280x720 | 28.0 | 4 | 27.9 | 24 | 36.00 | — | — | — | — | — | — | 23.07-53.57 | 0.000 | 36.0 | 22 | 22 | 22 | — | 0.3815 | 0.2718 | 0.0967 |
| 80564 | the-only-living-pickpocket-in-new-york | The Only Living Pickpocket in New York | youtube | 2026-08-06T01:20:10 | 137.56 | 1280x720 | 22.8 | 4 | 29.1 | 27 | 40.50 | — | — | — | — | — | — | 26.69-58.93 | 0.000 | 34.5 | 18 | 26 | 18 | — | 0.2596 | 0.4364 | 0.0651 |
| 80559 | teenage-sex-and-death-at-camp-miasma | Teenage Sex and Death at Camp Miasma | youtube | 2026-05-27T00:51:00 | 130.52 | 1280x720 | 10.5 | 4 | 30.6 | 12 | 18.00 | 17.93 | +0% | 1.62 | 5.0 | accelerating | 0.024 | 7.15-34.77 | 0.167 | 45.0 | 35 | 9 | 35 | — | 0.1380 | 0.4397 | 0.0609 |
| 80548 | parallel-tales | Parallel Tales | youtube | 2026-04-23T00:42:11 | 96.60 | 1280x720 | 12.1 | 4 | 41.4 | 21 | 31.50 | 35.41 | -11% | 1.21 | 5.2 | steady | 0.057 | 17.73-50.61 | 0.000 | 27.0 | 23 | 21 | 23 | — | 0.1607 | 0.3195 | 0.1237 |
| 80539 | fatherland | Fatherland | youtube | 2026-05-28T00:31:05 | 130.05 | 1280x720 | 16.3 | 4 | 30.8 | 9 | 13.50 | 16.61 | -19% | 2.12 | 5.4 | steady | 0.009 | 6.17-25.63 | 0.000 | 107.5 | 35 | 9 | 35 | — | 0.1515 | 0.0000 | 0.0451 |
| 80532 | hope | Hope | youtube | 2026-06-24T00:27:17 | 100.17 | 1280x720 | 10.3 | 4 | 39.9 | 9 | 13.50 | 15.57 | -13% | 2.34 | 0.0 | decelerating | 0.019 | 0.65-34.76 | 0.000 | 45.0 | 35 | 9 | 35 | — | 0.1660 | 0.2482 | 0.0842 |
| 80527 | behemoth | Behemoth! | youtube | 2026-08-14T00:21:05 | 100.17 | 1280x720 | 9.4 | 4 | 39.9 | 7 | 10.50 | — | — | — | — | — | — | 4.22-21.63 | 0.000 | 101.5 | 38 | 6 | 38 | — | 0.1486 | 0.2396 | 0.0650 |
| 80503 | primetime | Primetime | youtube | 2026-08-06T23:54:15 | 136.23 | 1080x720 | 13.2 | 4 | 29.4 | 42 | 63.00 | — | — | — | — | — | — | 26.31-109.21 | 0.429 | 19.0 | 18 | 26 | 18 | — | 0.1744 | 0.5724 | 0.0763 |
| 80501 | digger | Digger | youtube | 2026-07-13T23:50:17 | 158.22 | 1080x720 | 13.1 | 4 | 25.3 | 25 | 37.50 | 45.51 | -18% | 1.00 | 9.1 | accelerating | 0.038 | 23.58-56.29 | 0.000 | 32.5 | 21 | 23 | 21 | — | 0.2208 | 0.3823 | 0.0237 |
| 80494 | fjord | Fjord | youtube | 2026-08-27T23:46:00 | 118.40 | 1280x720 | 9.5 | 4 | 33.8 | 14 | 21.00 | 19.26 | +9% | 2.46 | 0.0 | accelerating | 0.021 | 11.48-35.23 | 0.000 | 48.0 | 30 | 14 | 30 | — | 0.2286 | 0.2819 | 0.0744 |
| 80490 | artificial | Artificial | youtube | 2026-09-08T23:12:25 | 76.86 | 1280x720 | 6.1 | 4 | 52.0 | 15 | 22.50 | 14.83 | +52% | 0.40 | 55.0 | accelerating | 0.010 | 1.05-54.14 | 0.000 | 8.5 | 35 | 9 | 35 | — | 0.1717 | 0.3689 | 0.0898 |
| 80487 | you-can-see-everything | You Can See Everything | youtube | 2026-09-23T23:07:41 | 148.33 | 960x720 | 10.5 | 4 | 27.0 | 16 | 24.00 | 25.48 | -6% | 1.81 | 6.2 | steady | 0.013 | 13.72-38.97 | 0.125 | 57.0 | 28 | 16 | 28 | — | 0.2745 | 0.3970 | 0.0569 |
| 80485 | josephine | Josephine | youtube | 2026-08-11T23:03:00 | 92.07 | 1280x720 | 7.4 | 4 | 43.4 | 19 | 28.50 | — | — | — | — | — | — | 7.10-58.71 | 0.000 | 28.0 | 27 | 17 | 27 | — | 0.2007 | 0.3328 | 0.0543 |
| 80377 | permanence-veritus-miller-ronnie-heard-iii | ‘Permanence’ Veritus Miller & Ronnie Heard III | youtube | 2026-10-01T16:00:00 | 388.40 | 1280x720 | 41.4 | 4 | 10.3 | 6 | 9.00 | 10.66 | -16% | 3.92 | 22.9 | accelerating | 0.005 | 2.99-20.16 | 0.000 | 95.0 | 38 | 6 | 38 | low-coverage | 0.2137 | 0.2830 | 0.0620 |
| 80290 | down-with-heaven-art-feynman | ‘Down With Heaven’ Art Feynman | youtube | 2026-10-02T19:52:04 | 323.66 | 1194x720 | 76.5 | 4 | 12.4 | 0 | 0.00 | 0.00 | — | 323.66 | 0.0 | — | 0.002 | 0.00-5.53 | — | — | 44 | 0 | 44 | low-coverage, no-cuts-observed | 0.0365 | 0.3799 | 0.0228 |
| 80159 | party-troye-sivan | ‘Party’ Troye Sivan | youtube | 2026-09-25T17:29:30 | 244.25 | 960x720 | 24.8 | 4 | 16.4 | 32 | 48.00 | 33.90 | +42% | 1.00 | 5.8 | accelerating | 0.049 | 32.21-68.57 | 0.000 | 25.0 | 14 | 30 | 14 | low-coverage | 0.2189 | 0.3884 | 0.1053 |

| download_method | provider | video_url |
| --- | --- | --- |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=-CDgxJgiQY4 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=dL4lFKY8Cy4 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=HdrkOFVBM70 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=o-LkpJ4ACxk |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=kL9EIAx6EPQ |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=-5ZXrO_lYSA |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=U_k0BHVD4QY |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=ydRyOr3KYD0 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=OlAbqwpKi-E |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=CHhfF-rEliI |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=qsh2di5c-nI |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=YPI8tDWHIAE |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=sk7NF_LWhLs |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=MZIcLNFK4rU |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=FND0AVr_68s |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=p0-pdE1GmUA |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=rv5FRyz3DXE |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=UVyH8QYENxI |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=4ZlZcBX2xiw |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=hTHeFP0mcuk |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=Xmz12Rt2P9U |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=guKEdb_iRXw |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=MLwTyQOhBkw |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=RjEZaUBbUvU |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=2AxtdPvDojA |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=2ZCumy6G294 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=UVrZjPaX7DU |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=lz1R_bQqjiA |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=FCtl_roHr9o |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=H5prIVmeuds |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=xouLR3XcFWQ |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=dI7s0dn4qB4 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=LutBUtHdxKM |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=uA6Fnr2VXkw |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=tDdX1XoJVKA |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=By5Yh0Y_h_M |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=dimCiC_hdoA |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=y3BV9KeJzGM |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=-I2-X9v-ogs |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=bC1Wptb4cT4 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=TrMGdrCJ5Ck |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=5fHXyqQOKL8 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=qORTe1wW3Wg |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=frg59VOungA |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=rDZplZFnbOk |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=HvW_N5p1q44 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=K32NPBLpqZI |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=cOc9sMssvWI |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=HfdomXUgvpc |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=Yvl4QSAyWR4 |

## Aggregates (video-measured records only)

Every number in this section is computed ONLY over the video-measured records tabulated above. Published stills, including still-only rows, never enter the motion, cut, luma, or saturation aggregates.

All minima and maxima are computed over `rankable` records only and name the record id and validity flags.

Unique records before dedupe: 160; after dedupe: 160 (0 duplicate extra record(s) collapsed).

Rankable records: 148 of 160 unique; excluded as non-rankable: 12.

| metric | n | min (record; flags) | median | max (record; flags) |
| --- | --- | --- | --- | --- |
| duration_s | 148 | 40.01 (the-history-of-concrete; —) | 136.34 | 520.89 (lime-tikka-baalti-lapgan; low-coverage) |
| mean_luma | 148 | 0.0365 (down-with-heaven-art-feynman; low-coverage, no-cuts-observed) | 0.2237 | 0.7480 (shape-of-dreams-on; low-coverage) |
| mean_sat | 148 | 0.0000 (big-beautiful-sound-dana-margolin; low-coverage) | 0.3212 | 0.8236 (romance-baalti-lapgan; —) |
| delta_per_s | 148 | 0.0118 (trying-times-james-blake; low-coverage, no-cuts-observed) | 0.0659 | 0.1464 (i-see-buildings-fall-like-lightning; —) |
| candidates_n | 148 | 0 (chanel-25-handbag-chanel; no-cuts-observed) | 13 | 47 (coming-of-age-mette; low-coverage) |
| sampled_cut_candidates_per_min | 148 | 0.00 (chanel-25-handbag-chanel; no-cuts-observed) | 19.50 | 70.50 (coming-of-age-mette; low-coverage) |
Excluded as non-rankable (largest first):

| record | sampled_cut_candidates_per_min | validity |
| --- | --- | --- |
| take-me-home-labat-notinbed | 195.00 | burst-heavy, low-coverage, non-edit-scene-change |
| miama-1000vall | 78.00 | burst-heavy, low-coverage |
| super-nature | 72.00 | burst-heavy |
| freak-is-wild-skuzland-shygirl | 69.00 | burst-heavy, low-coverage |
| 7-bridges-to-burn-knats | 54.00 | burst-heavy, low-coverage |

Coverage-weighted caveat: 6390.0 sampled seconds cover 27638.4 runtime seconds (23.1%). Aggregates describe the sampled windows, not the full films. Where a full-film census record exists, `full_cuts_per_min` is film-level and `full_vs_window` states the difference (see `## Full-film census`).

## Comparability

- poolable: `false`
- comparable within: same site, same rendition, same runtime band, non-burst, >=25% coverage
- not comparable to: other sites, other renditions, full-film claims derived from window rates

Caveats:

- Directors' Library: poolable is false; every number describes this site's measured sample only.
- 160 of 5412 catalogue items were measured (2.956%) by YouTube availability; Vimeo-only rows are skipped as unsupported.
- Measured rows are not a random sample: availability and recency select them, so cross-site pooling is invalid.
- Provider families are not interchangeable: youtube x 160.
- Renditions differ by site and record: platform-encoded YouTube renditions; Vimeo was never fetched or probed.
- Measured renditions vary by resolution (1280x720 x 112, 960x720 x 14, 1080x720 x 8, 1200x720 x 4, 1048x720 x 2, 1190x720 x 2, 1198x720 x 2, 1280x676 x 2, +13 more), frame rate (24 x 65, 25 x 50, 23.976 x 41, 29.97 x 2, 50 x 2) and bitrate (0.9 x 23, 1.0 x 21, 0.7 x 20, 0.4 x 12, 0.8 x 12, 0.6 x 10, 1.1 x 9, 0.5 x 8, +10 more), so the sample is not a controlled transform.
- Window coverage is sampled, not full-film: median 28.70125% per record, p10 13.9206%, p90 44.4711%; 31.875% of rows are below 20% and 2.5% below 10%; median unobserved gap between windows is 28.0 s. Window rates describe those windows; a full-film census, when present, is reported separately.
- 0 extra record(s) in 0 duplicate group(s) share media; unique media after dedupe is 160.
- Still/video overlap: 5348 still record(s), 5193 still-only, are a separate single-frame lane and never enter these aggregates.

## Coverage

Per-record coverage distribution over the deduped records. The unobserved gap is the median time between consecutive sampled windows, derived from runtime, window count and sampled seconds.

| statistic | coverage_pct |
| --- | --- |
| min | 7.7 |
| p10 | 13.9 |
| median | 28.7 |
| p90 | 44.5 |
| max | 75.3 |
| below 20% | 31.9% |
| below 10% | 2.5% |
| median unobserved gap between windows | 28.0 s |

## Full-film census

Film-level evidence: 142 of 160 video-measured records (88.8%) on Directors' Library have a full-runtime census record. Census values are **film-level**: every cut candidate in the file was counted and the appearance series is time-weighted over the whole runtime, so `decodeCoverageFraction` is 1.000000. The `full_cuts_per_min` column is that film-level rate; every `sampled_cut_candidates_per_min` value remains a sample of its windows.

Census cut candidates are still ffmpeg scene-score exceedances, not verified edits; fast movement, flashes, transitions and compression can exceed the threshold. A `strobe` record's rate describes strobe-like candidate density and is **not comparable to a cut rate**, so strobe records are excluded from the range below and reported separately.

| statistic | full_cuts_per_min (non-strobe) |
| --- | --- |
| n | 133 |
| min | 0.00 |
| p10 | 7.31 |
| median | 20.62 |
| p90 | 38.62 |
| max | 66.63 |

Range endpoints: min 0.00 (`down-with-heaven-art-feynman`), max 66.63 (`introducing-the-dyson-camerajet`); n counts non-strobe records only.

Strobe block (never pooled with the cut-rate range above): 9 record(s), listed by id below. Its own range is min 1.09, median 54.75, max 177.12.

| strobe id | full_cuts_per_min | median_gap_frames | burst_fraction |
| --- | --- | --- | --- |
| automatic | 24.61 | 7.0 | 0.667 |
| blue-girl-in-red | 86.96 | 2.0 | 0.793 |
| box-of-god-daisy-maybe | 82.21 | 5.0 | 0.775 |
| freak-is-wild-skuzland-shygirl | 82.31 | 5.0 | 0.578 |
| in-the-night-beck | 1.09 | 1.0 | 1.000 |
| landmarks | 29.26 | 3.5 | 0.607 |
| miama-1000vall | 51.15 | 6.0 | 0.744 |
| super-nature | 54.75 | 17.0 | 0.528 |
| take-me-home-labat-notinbed | 177.12 | 2.0 | 0.724 |

## Census reconciliation

Window values are samples of the runtime; census values cover the film. Relative error is `(window_rate - full_rate) / full_rate`, so a positive value means the window sample overestimated the film and a negative value means it underestimated it.

- comparable records: 139; skipped for a zero full-film rate: 3
- median |relative error|: 0.164; p90 |relative error|: 0.589; max |relative error|: 2.466
- window estimate off by more than 25%: 47 of 139 (33.8%); window higher on 69 record(s), lower on 70
- ordering changes beyond five positions when ranked by each rate: 83

| id | window_cuts_per_min | full_cuts_per_min | relative_error | direction |
| --- | --- | --- | --- | --- |
| the-boy-who-played-the-harp-dave | 21.00 | 6.06 | 2.466 | window higher |
| nino-milo-j | 15.00 | 5.77 | 1.601 | window higher |
| a-love-supreme-pt-i-john-coltrane | 7.50 | 3.23 | 1.320 | window higher |
| is-it-that-deep-cat-burns | 3.00 | 1.39 | 1.160 | window higher |
| chanel-25-handbag-chanel | 0.00 | 1.13 | -1.000 | window lower |
| dead-grandma | 0.00 | 0.74 | -1.000 | window lower |
| in-the-night-beck | 0.00 | 1.09 | -1.000 | window lower |
| generation-gucci | 15.00 | 8.48 | 0.770 | window higher |
| blue-girl-in-red | 22.50 | 86.96 | -0.741 | window lower |
| lime-tikka-baalti-lapgan | 3.00 | 9.10 | -0.670 | window lower |
| landmarks | 10.50 | 29.26 | -0.641 | window lower |
| fever-dream | 13.50 | 8.25 | 0.636 | window higher |
| rock-music-charli-xcx | 19.50 | 47.43 | -0.589 | window lower |
| in-my-head-estelle-chen | 3.00 | 7.30 | -0.589 | window lower |
| jealous-lover-the-rolling-stones | 9.00 | 21.87 | -0.588 | window lower |
| neram-gokul-krishna | 6.00 | 13.54 | -0.557 | window lower |
| the-cure-olivia-rodrigo | 7.50 | 16.61 | -0.548 | window lower |
| all-of-a-sudden | 31.50 | 20.41 | 0.544 | window higher |
| lucha | 6.00 | 12.63 | -0.525 | window lower |
| miama-1000vall | 78.00 | 51.15 | 0.525 | window higher |
| artificial | 22.50 | 14.83 | 0.517 | window higher |
| in-bloom | 40.50 | 26.78 | 0.512 | window higher |
| devils-advocate-pink-siifu | 21.00 | 13.94 | 0.507 | window higher |
| easy-street-queens-of-the-stone-age | 7.50 | 14.97 | -0.499 | window lower |
| your-way-out-coinbase | 19.50 | 13.05 | 0.495 | window higher |
| cant-wait-andy | 12.00 | 22.28 | -0.461 | window lower |
| ah-girl | 10.50 | 7.36 | 0.427 | window higher |
| air-lemonder-viper-bicep | 10.50 | 18.31 | -0.427 | window lower |
| party-troye-sivan | 48.00 | 33.90 | 0.416 | window higher |
| hearing | 7.50 | 5.33 | 0.406 | window higher |
| storm-gener8ion | 10.50 | 17.16 | -0.388 | window lower |
| push-like-youre-pooing-andrex | 34.50 | 24.99 | 0.381 | window higher |
| coda-dpat | 15.00 | 24.15 | -0.379 | window lower |
| box-of-god-daisy-maybe | 52.50 | 82.21 | -0.361 | window lower |
| nuisance-bear | 13.50 | 20.73 | -0.349 | window lower |
| cover-up | 19.50 | 29.66 | -0.343 | window lower |
| coming-of-age-mette | 70.50 | 52.63 | 0.340 | window higher |
| tender-loving-care-2 | 15.00 | 22.31 | -0.328 | window lower |
| odor-enis | 12.00 | 17.67 | -0.321 | window lower |
| super-nature | 72.00 | 54.75 | 0.315 | window higher |
| blknws-terms-conditions | 28.50 | 41.33 | -0.310 | window lower |
| romance-baalti-lapgan | 21.00 | 16.17 | 0.299 | window higher |
| if-this-is-hell-space-afrika | 31.50 | 24.35 | 0.294 | window higher |
| backrooms | 15.00 | 20.89 | -0.282 | window lower |
| discipline-makeshift-art-bar | 22.50 | 31.12 | -0.277 | window lower |
| levitating | 40.50 | 31.76 | 0.275 | window higher |
| rose | 19.50 | 15.52 | 0.256 | window higher |

| id | window_rank | full_rank | position_change | window_cuts_per_min | full_cuts_per_min |
| --- | --- | --- | --- | --- | --- |
| landmarks | 115 | 41 | 74 | 10.50 | 29.26 |
| rock-music-charli-xcx | 76 | 12 | 64 | 19.50 | 47.43 |
| blue-girl-in-red | 61 | 2 | 59 | 22.50 | 86.96 |
| the-boy-who-played-the-harp-dave | 73 | 129 | -56 | 21.00 | 6.06 |
| jealous-lover-the-rolling-stones | 122 | 68 | 54 | 9.00 | 21.87 |
| artificial | 60 | 107 | -47 | 22.50 | 14.83 |
| all-of-a-sudden | 32 | 77 | -45 | 31.50 | 20.41 |
| cant-wait-andy | 108 | 65 | 43 | 12.00 | 22.28 |
| devils-advocate-pink-siifu | 68 | 109 | -41 | 21.00 | 13.94 |
| cover-up | 74 | 39 | 35 | 19.50 | 29.66 |
| nino-milo-j | 97 | 131 | -34 | 15.00 | 5.77 |
| tender-loving-care-2 | 98 | 64 | 34 | 15.00 | 22.31 |
| your-way-out-coinbase | 79 | 113 | -34 | 19.50 | 13.05 |
| coda-dpat | 94 | 61 | 33 | 15.00 | 24.15 |
| the-cure-olivia-rodrigo | 128 | 95 | 33 | 7.50 | 16.61 |
| nuisance-bear | 105 | 74 | 31 | 13.50 | 20.73 |
| generation-gucci | 95 | 124 | -29 | 15.00 | 8.48 |
| in-bloom | 18 | 47 | -29 | 40.50 | 26.78 |
| air-lemonder-viper-bicep | 113 | 85 | 28 | 10.50 | 18.31 |
| discipline-makeshift-art-bar | 63 | 36 | 27 | 22.50 | 31.12 |
| (+63 more rank changes in `aggregate.json`) | | | | | |

## Editorial structure

Derived offline from each record's stored census cut candidates and 1 Hz appearance series (pure function, no media re-decode). A `shot` is the interval between consecutive detected scene changes, a lower bound on edits; `shotCount` is always candidates + 1.

Shot-length distribution across 133 non-strobe clip(s), using each clip's median shot length. Strobe records are excluded because their candidate intervals are frame-scale.

| statistic | median_shot_s |
| --- | --- |
| n | 133 |
| min | 0.40 |
| p10 | 0.92 |
| median | 1.83 |
| p90 | 5.01 |
| max | 323.66 |

Median cut rate (non-strobe): 20.62 cuts/min. Shot counts across clips: 1–219.

Pace trend, last third ÷ first third with a ±15% band: accelerating 63, steady 31, decelerating 42, unclassified 6 (unclassified means no cut candidate in the first third, so no ratio exists).

Clips whose last third is >2× their first third (>2×; non-strobe):

| id | pace_drift_ratio | median_shot_s |
| --- | --- | --- |
| a-personal-appeal-alzheimers-society | 9.00 | 1.88 |
| your-way-out-coinbase | 6.00 | 1.36 |
| youre-not-like-that-the-rapants | 4.55 | 1.64 |
| drop-dead-olivia-rodrigo | 4.00 | 1.94 |
| tiramisu-oat-cult | 3.73 | 0.80 |
| variations-on-a-theme | 3.25 | 2.25 |
| amazomania | 3.00 | 1.94 |
| minotaur | 3.00 | 1.33 |
| mexicanamerican | 2.75 | 3.34 |
| a24-meets-dior | 2.65 | 0.84 |
| artificial | 2.60 | 0.40 |
| all-of-a-sudden | 2.50 | 1.62 |
| odor-enis | 2.40 | 1.84 |
| digger | 2.17 | 1.00 |
| the-cure-olivia-rodrigo | 2.12 | 2.36 |
| air-lemonder-viper-bicep | 2.05 | 0.58 |
| american-girls-harry-styles | 2.00 | 2.35 |
| backrooms | 2.00 | 2.00 |

Clips whose last third is <0.5× their first third (<0.5×; non-strobe):

| id | pace_drift_ratio | median_shot_s |
| --- | --- | --- |
| dead-grandma | 0.00 | 40.46 |
| storm-gener8ion | 0.01 | 1.52 |
| same-sht-isaiah-rashad | 0.10 | 1.96 |
| life-within-rimowa | 0.11 | 2.00 |
| easy-street-queens-of-the-stone-age | 0.11 | 1.92 |
| henna | 0.20 | 2.90 |
| nino-milo-j | 0.25 | 4.72 |
| coda-dpat | 0.28 | 1.38 |
| burn | 0.29 | 1.67 |
| in-my-head-estelle-chen | 0.29 | 4.38 |
| i-see-red-daniela-andrade | 0.36 | 1.08 |
| sound-of-falling-2 | 0.36 | 2.12 |
| dragonfly | 0.40 | 1.83 |
| birds-of-war | 0.44 | 1.40 |
| hope | 0.44 | 2.34 |
| once-again-orelsan-yame | 0.46 | 2.00 |
| union-county | 0.47 | 2.21 |
| romance-baalti-lapgan | 0.50 | 2.08 |

Flicker outliers (median absolute luma delta per second above 0.050; sample instability, not a flicker frequency):

| id | flicker_luma_per_s |
| --- | --- |
| father | 0.085 |
| take-me-home-labat-notinbed | 0.085 |
| i-see-buildings-fall-like-lightning | 0.084 |
| super-nature | 0.063 |
| introducing-the-dyson-camerajet | 0.061 |
| parallel-tales | 0.057 |
| the-beat-aclu | 0.057 |
| cover-up | 0.054 |
| i-only-rest-in-the-storm | 0.054 |
| i-love-boosters | 0.051 |

Strobe records excluded from the shot-length aggregates: `automatic`, `blue-girl-in-red`, `box-of-god-daisy-maybe`, `freak-is-wild-skuzland-shygirl`, `in-the-night-beck`, `landmarks`, `miama-1000vall`, `super-nature`, `take-me-home-labat-notinbed`.

## Measured stills

5348 still-measured record(s), ordered by post id then slug. Every number describes one published image, never a video frame.
Quality-flagged stills excluded from the colour distributions and term aggregates: 21 of 5348.
`decode_w`/`decode_h` are the aspect-preserving `160×90` fit; they are derived from the source `img_w`/`img_h` when a record stores no decode size, which is the case for every current record.

| post_id | slug | title | poster_w | poster_h | img_w | img_h | decode_w | decode_h | img_bytes | mean_luma | mean_sat | hue | edge_density |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 46977 | a-musical-short-vince-staples | ‘A Musical Short’ Vince Staples | 1080 | 454 | 1080 | 454 | 160 | 67 | 70037 | 0.1825 | 0.4216 | orange | 0.0264 |
| 46979 | drone-bomb-me-anohni | ‘Drone Bomb Me’ ANOHNI | 1080 | 530 | 1080 | 530 | 160 | 79 | 66251 | 0.2733 | 0.7258 | blue | 0.0240 |
| 46981 | piss-on-your-grave-travis-scott-kanye-west | ‘Piss on your Grave’ Travis Scott & Kanye West | 1080 | 450 | 1080 | 450 | 160 | 67 | 105154 | 0.2437 | 0.3669 | green | 0.0347 |
| 46983 | give-it-all-foals | ‘Give It All’ Foals | 1080 | 406 | 1080 | 406 | 160 | 60 | 42091 | 0.1558 | 0.5819 | orange | 0.0144 |
| 46985 | captureland | Captureland | 1080 | 458 | 1080 | 458 | 160 | 68 | 40801 | 0.3449 | 0.2140 | neutral | 0.0196 |
| 46987 | hunger-of-the-pine-alt-j | ‘Hunger of the Pine’ Alt-J | 1080 | 456 | 1080 | 456 | 160 | 68 | 49495 | 0.2493 | 0.3148 | yellow | 0.0259 |
| 46989 | two-weeks-fka-twigs | ‘Two Weeks’ FKA Twigs | 1080 | 419 | 1080 | 419 | 160 | 62 | 75160 | 0.3433 | 0.3640 | red | 0.0419 |
| 46991 | the-game-before-the-game-beats-by-dre | ‘The Game Before the Game’ Beats by Dre | 1080 | 397 | 1080 | 397 | 160 | 59 | 77933 | 0.2738 | 0.2575 | orange | 0.0625 |
| 46995 | whyd-you-only-call-me-when-youre-high-arctic-monkeys | ‘Why’d You Only Call Me When You’re High?’ Arctic Monkeys | 1080 | 438 | 1080 | 438 | 160 | 65 | 70670 | 0.2160 | 0.2045 | neutral | 0.0243 |
| 46997 | just-blaze-baauer-jay-z | ‘Just Blaze’ Baauer & Jay Z | 1080 | 624 | 1080 | 624 | 156 | 90 | 96940 | 0.2864 | 0.3003 | orange | 0.0258 |
| 46999 | late-night-foals | ‘Late Night’ Foals | 1080 | 471 | 1080 | 471 | 160 | 70 | 31433 | 0.1773 | 0.4332 | orange | 0.0101 |
| 47001 | overgrown-james-blake | ‘Overgrown’ James Blake | 1080 | 469 | 1080 | 469 | 160 | 69 | 52601 | 0.2676 | 0.3813 | blue | 0.0142 |
| 47003 | 28-the-weeknd | ’28’ The Weeknd | 1080 | 469 | 1080 | 469 | 160 | 69 | 77037 | 0.2837 | 0.2664 | neutral | 0.0345 |
| 47005 | pyramids-frank-ocean | ‘Pyramids’ Frank Ocean | 1080 | 429 | 1080 | 429 | 160 | 64 | 57973 | 0.4654 | 0.2095 | yellow | 0.0248 |
| 47007 | cut-the-world-antony-and-the-johnsons | ‘Cut the World’ Antony and The Johnsons | 1080 | 462 | 1080 | 462 | 160 | 68 | 41943 | 0.3979 | 0.0834 | neutral | 0.0114 |
| 47009 | mercy-kanye-west | ‘Mercy’ Kanye West | 1080 | 456 | 1080 | 456 | 160 | 68 | 48620 | 0.4184 | 0.0000 | neutral | 0.0563 |
| 47011 | swim-good-frank-ocean | ‘Swim Good’ Frank Ocean | 1080 | 414 | 1080 | 414 | 160 | 61 | 71582 | 0.2750 | 0.3167 | orange | 0.0487 |
| 47013 | towers-bon-iver | ‘Towers’ Bon Iver | 1080 | 488 | 1080 | 488 | 160 | 72 | 85096 | 0.5248 | 0.2170 | yellow | 0.0316 |
| 47015 | novacane-frank-ocean | ‘Novacane’ Frank Ocean | 1080 | 621 | 1080 | 621 | 157 | 90 | 70893 | 0.1794 | 0.4608 | yellow | 0.0254 |
| 47017 | holocene-bon-iver | ‘Holocene’ Bon Iver | 1080 | 497 | 1080 | 497 | 160 | 74 | 93767 | 0.1699 | 0.2298 | blue | 0.0289 |
| 47019 | coldest-winter-kanye-west | ‘Coldest Winter’ Kanye West | 1080 | 599 | 1080 | 599 | 160 | 89 | 58431 | 0.1175 | 0.6375 | blue | 0.0211 |
| 47021 | welcome-to-heartbreak-kanye-west | ‘Welcome to Heartbreak’ Kanye West | 1080 | 574 | 1080 | 574 | 160 | 85 | 99565 | 0.3946 | 0.5271 | neutral | 0.0470 |
| 47023 | paranoid-kanye-west-feat-rihanna | ‘Paranoid’ Kanye West feat. Rihanna | 1080 | 544 | 1080 | 544 | 160 | 81 | 64847 | 0.2581 | 0.1328 | neutral | 0.0465 |
| 47025 | revenge | Revenge | 1080 | 606 | 1080 | 606 | 160 | 90 | 24177 | 0.6368 | 0.2768 | magenta | 0.0073 |
| 47027 | chocolate-bunny | Chocolate Bunny | 1080 | 609 | 1080 | 609 | 160 | 90 | 95452 | 0.3540 | 0.6953 | magenta | 0.0331 |
| 47029 | cdefgabc | CDEFGABC | 1080 | 607 | 1080 | 607 | 160 | 90 | 106137 | 0.5202 | 0.2345 | neutral | 0.0457 |
| 47031 | coffin-poser-aux-raus | ‘Coffin Poser’ Aux Raus | 1080 | 606 | 1080 | 606 | 160 | 90 | 44047 | 0.7542 | 0.0745 | neutral | 0.0133 |
| 47033 | elektrotechnique-de-jeugd-van-tegenwoordig | ‘Elektrotechnique’ De Jeugd Van Tegenwoordig | 1080 | 605 | 1080 | 605 | 160 | 90 | 37678 | 0.8777 | 0.0625 | neutral | 0.0098 |
| 47035 | natural-beauty | Natural Beauty | 1080 | 604 | 1080 | 604 | 160 | 89 | 28939 | 0.8074 | 0.0694 | neutral | 0.0100 |
| 47037 | amnesty-international | Amnesty International | 1900 | 1060 | 1900 | 1060 | 160 | 89 | 198453 | 0.4813 | 0.2991 | green | 0.0290 |
| 47039 | handmade | Handmade | 1080 | 603 | 1080 | 603 | 160 | 89 | 81267 | 0.5019 | 0.2048 | orange | 0.0231 |
| 47041 | ss-2016-hermes | ‘SS 2016’ Hermès | 1080 | 635 | 1080 | 635 | 153 | 90 | 47185 | 0.7604 | 0.2058 | yellow | 0.0249 |
| 47043 | knab | Knab | 1080 | 623 | 1080 | 623 | 156 | 90 | 45025 | 0.2926 | 0.2844 | neutral | 0.0124 |
| 47045 | we | We | 1080 | 581 | 1080 | 581 | 160 | 86 | 22132 | 0.4456 | 0.0893 | neutral | 0.0059 |
| 47047 | creamy-blue-castello | ‘Creamy Blue’ Castello | 1080 | 615 | 1080 | 615 | 158 | 90 | 54814 | 0.4879 | 0.2106 | orange | 0.0188 |
| 47049 | the-sound-of-cos | The Sound of COS | 1080 | 605 | 1080 | 605 | 160 | 90 | 46010 | 0.8139 | 0.0554 | neutral | 0.0156 |
| 47051 | manon-de-jeugd-van-tegenwoordig | ‘Manon’ De Jeugd Van Tegenwoordig | 1080 | 607 | 1080 | 607 | 160 | 90 | 32687 | 0.6737 | 0.1610 | red | 0.0123 |
| 47053 | turtle-cam | Turtle Cam | 1080 | 600 | 1080 | 600 | 160 | 89 | 58177 | 0.2339 | 0.1685 | neutral | 0.0325 |
| 47055 | montana-youth-lagoon | ‘Montana’ Youth Lagoon | 1080 | 455 | 1080 | 455 | 160 | 67 | 69030 | 0.4099 | 0.3194 | yellow | 0.0273 |
| 47057 | love-is-a-war-house-of-wolves | ‘Love is a War’ House of Wolves | 1080 | 496 | 1080 | 496 | 160 | 73 | 99113 | 0.4237 | 0.3589 | green | 0.0253 |
| 47059 | july-youth-lagoon | ‘July’ Youth Lagoon | 1080 | 559 | 1080 | 559 | 160 | 83 | 35821 | 0.3296 | 0.2064 | blue | 0.0083 |
| 47061 | curtains-timber-timbre | ‘Curtains?!’ Timber Timbre | 1080 | 580 | 1080 | 580 | 160 | 86 | 67875 | 0.5702 | 0.0000 | neutral | 0.0324 |
| 47063 | all-i-want-dawn-golden | ‘All I Want’ Dawn Golden | 1080 | 445 | 1080 | 445 | 160 | 66 | 44899 | 0.4024 | 0.1912 | orange | 0.0145 |
| 47065 | no-way-out-mathew-lee-cothran | ‘No Way Out’ Mathew Lee Cothran | 1080 | 499 | 1080 | 499 | 160 | 74 | 61572 | 0.4325 | 0.4896 | yellow | 0.0161 |
| 47067 | mute-youth-lagoon | ‘Mute’ Youth Lagoon | 1080 | 526 | 1080 | 526 | 160 | 78 | 96494 | 0.1556 | 0.4403 | blue | 0.0281 |
| 47069 | messages-maston | ‘Messages’ Maston | 1080 | 521 | 1080 | 521 | 160 | 77 | 69557 | 0.3468 | 0.3774 | blue | 0.0162 |
| 47071 | kathryn-my-love-pandit | ‘Kathryn, My Love’ Pandit | 1718 | 896 | 1718 | 896 | 160 | 83 | 110778 | 0.3917 | 0.1194 | neutral | 0.0201 |
| 47073 | believe-the-chemical-brothers | ‘Believe’ The Chemical Brothers | 1080 | 598 | 1080 | 598 | 160 | 89 | 98803 | 0.4704 | 0.1857 | neutral | 0.0511 |
| 47075 | the-salmon-dance-the-chemical-brothers | ‘The Salmon Dance’ The Chemical Brothers | 1080 | 600 | 1080 | 600 | 160 | 89 | 115120 | 0.3780 | 0.4027 | yellow | 0.0456 |
| 47077 | midnight-madness-the-chemical-brothers | ‘Midnight Madness’ The Chemical Brothers | 1080 | 606 | 1080 | 606 | 160 | 90 | 90570 | 0.2357 | 0.3812 | cyan | 0.0292 |

## Distributions by term

Each term row aggregates only the measured stills that carry that term. Term names were resolved from the WordPress taxonomy endpoints and cached in the catalogue. Counts describe this measured sample, not the full catalogue.

### agency

| term | term_id | stills | luma min | luma median | luma max |
| --- | --- | --- | --- | --- | --- |
| Wieden + Kennedy London | 3644 | 8 | 0.1369 | 0.2927 | 0.5278 |
| Droga5 | 47 | 7 | 0.1006 | 0.1824 | 0.3075 |
| Dentsu | 3713 | 6 | 0.0302 | 0.2872 | 0.4132 |
| Saatchi &amp; Saatchi | 3720 | 6 | 0.1357 | 0.2218 | 0.3699 |
| Wieden + Kennedy Portland | 3474 | 6 | 0.1917 | 0.3816 | 0.6204 |
| adam&amp;eveDDB | 3452 | 6 | 0.0810 | 0.2654 | 0.3265 |
| DDB Paris | 3469 | 5 | 0.1020 | 0.2221 | 0.3461 |
| Mother London | 3484 | 5 | 0.1629 | 0.4650 | 0.6114 |
| Wieden+Kennedy | 46 | 5 | 0.2483 | 0.2667 | 0.5358 |
| Wieden+Kennedy Amsterdam | 3712 | 5 | 0.1038 | 0.2151 | 0.6168 |
| 72andSunny | 3461 | 4 | 0.1073 | 0.3222 | 0.4642 |
| BBH | 4453 | 4 | 0.0595 | 0.2938 | 0.3512 |
| BBH London | 3457 | 4 | 0.1005 | 0.4875 | 0.6330 |
| Johannes Leonardo | 3275 | 4 | 0.2197 | 0.2606 | 0.3303 |
| TBWA | 3444 | 4 | 0.2220 | 0.3005 | 0.3302 |
| AMV BBDO | 3707 | 3 | 0.1341 | 0.2315 | 0.5607 |
| American Haiku | 4436 | 3 | 0.1985 | 0.2998 | 0.3806 |
| Anomaly Berlin | 3701 | 3 | 0.1830 | 0.3110 | 0.5430 |
| Anomaly London | 3473 | 3 | 0.2057 | 0.3937 | 0.3945 |
| Antoni | 3992 | 3 | 0.1543 | 0.2499 | 0.5707 |
| BBDO New York | 3977 | 3 | 0.2629 | 0.2780 | 0.4029 |
| Cossette | 3983 | 3 | 0.1681 | 0.2322 | 0.3787 |
| Don’t Panic | 3719 | 3 | 0.1134 | 0.1581 | 0.5463 |
| HeimatTBWA | 3470 | 3 | 0.1027 | 0.1089 | 0.1762 |
| ISLA Agency | 3481 | 3 | 0.0836 | 0.1766 | 0.3610 |
| Lucky Generals | 3450 | 3 | 0.1627 | 0.2563 | 0.3617 |
| Ogilvy | 3273 | 3 | 0.2735 | 0.3240 | 0.4096 |
| Publicis Conseil | 3477 | 3 | 0.2871 | 0.3535 | 0.4936 |
| Squarespace | 3951 | 3 | 0.2513 | 0.2580 | 0.6617 |
| TBWA\Media Arts Lab | 3648 | 3 | 0.2755 | 0.4050 | 0.4934 |
| Uncommon Creative Studio | 3700 | 3 | 0.1370 | 0.1909 | 0.1949 |
| &amp;Co. | 4468 | 2 | 0.2020 | 0.2587 | 0.3155 |
| 1993 Agency | 3446 | 2 | 0.4280 | 0.5346 | 0.6413 |
| AKQA | 3708 | 2 | 0.0974 | 0.1267 | 0.1561 |
| AWGE | 3607 | 2 | 0.1757 | 0.2925 | 0.4094 |
| Accenture Song | 4445 | 2 | 0.1255 | 0.2251 | 0.3248 |
| Anomaly | 3650 | 2 | 0.1532 | 0.1983 | 0.2435 |
| Anorak | 3978 | 2 | 0.2621 | 0.2741 | 0.2861 |
| Broken Heart Love Affair | 3994 | 2 | 0.2434 | 0.2512 | 0.2589 |
| Forsman &amp; Bodenfors | 3704 | 2 | 0.0501 | 0.1813 | 0.3124 |
| Frosty | 3717 | 2 | 0.1858 | 0.2406 | 0.2954 |
| Goodby Silverstein &amp; Partners | 3996 | 2 | 0.2217 | 0.2645 | 0.3073 |
| Isle of Any | 4638 | 2 | 0.3483 | 0.3501 | 0.3519 |
| Joan Creative | 3647 | 2 | 0.1677 | 0.2578 | 0.3479 |
| Joe Public | 4747 | 2 | 0.3080 | 0.3519 | 0.3959 |
| Jung Von Matt | 3979 | 2 | 0.2689 | 0.3181 | 0.3674 |
| La Fourmi | 3709 | 2 | 0.2485 | 0.3166 | 0.3848 |
| Media Trust | 4544 | 2 | 0.1758 | 0.2671 | 0.3585 |
| Mother Berlin | 3608 | 2 | 0.2920 | 0.3744 | 0.4567 |
| Motion Sickness | 4673 | 2 | 0.1795 | 0.3012 | 0.4229 |

### aspect_ratio

| term | term_id | stills | luma min | luma median | luma max |
| --- | --- | --- | --- | --- | --- |
| 1.78:1 (16:9) | 4529 | 155 | 0.0496 | 0.2855 | 0.8284 |
| 1.33:1 (4:3) | 24 | 101 | 0.0345 | 0.2794 | 0.6983 |
| 1.50:1 (3:2) | 4542 | 41 | 0.0672 | 0.2673 | 0.5708 |
| 1.66:1 (Widescreen) | 4531 | 37 | 0.0592 | 0.2655 | 0.9086 |
| 1.85:1 (Flat) | 25 | 10 | 0.1181 | 0.2085 | 0.4877 |
| 2.35:1 (CinemaScope) | 4558 | 9 | 0.1387 | 0.2989 | 0.6463 |
| 2.39:1 (Scope) | 4594 | 8 | 0.1143 | 0.2768 | 0.4010 |
| 1.375:1 (Academy) | 4614 | 6 | 0.0967 | 0.3148 | 0.4523 |
| 1.67:1 (5:3) | 4675 | 3 | 0.3495 | 0.3841 | 0.4115 |
| 2.00:1 (2:1) | 4593 | 3 | 0.1713 | 0.2903 | 0.3551 |
| 1.20:1 (6:5) | 4674 | 2 | 0.0866 | 0.1854 | 0.2842 |
| 1.56:1 (14:9) | 4577 | 2 | 0.3350 | 0.3615 | 0.3880 |
| 0.56:1 (9:16, Vertical) | 4569 | 1 | 0.3179 | 0.3179 | 0.3179 |

### award

| term | term_id | stills | luma min | luma median | luma max |
| --- | --- | --- | --- | --- | --- |
| Grand Jury Prize (Sundance) | 52 | 6 | 0.1908 | 0.3070 | 0.5646 |
| Academy Award | 3379 | 5 | 0.1082 | 0.2542 | 0.3914 |
| Palme d'Or (Cannes) | 3672 | 5 | 0.2470 | 0.3361 | 0.5059 |
| Audience Award (SXSW) | 3363 | 4 | 0.1679 | 0.2950 | 0.3010 |
| Grand Prix (Cannes) | 3380 | 4 | 0.1172 | 0.2966 | 0.4236 |
| Audience Award (Sundance) | 3962 | 3 | 0.2240 | 0.2289 | 0.2305 |
| Best Screenplay (Cannes) | 3968 | 3 | 0.2855 | 0.3332 | 0.4872 |
| Caméra d'Or (Cannes) | 3934 | 3 | 0.1357 | 0.2059 | 0.4606 |
| Directing Award (Sundance) | 3384 | 3 | 0.2861 | 0.4131 | 0.4953 |
| Jury Prize (Cannes) | 3965 | 3 | 0.2029 | 0.3124 | 0.4223 |
| Dramatic Grand Jury Prize (Sundance) | 4692 | 2 | 0.2289 | 0.3409 | 0.4530 |
| Golden Leopard (Locarno) | 4502 | 2 | 0.3380 | 0.4068 | 0.4756 |
| Golden Lion (Venice) | 51 | 2 | 0.1526 | 0.2138 | 0.2749 |
| Jury Award (SXSW) | 3624 | 2 | 0.1679 | 0.2460 | 0.3242 |
| Palm Dog Award (Cannes) | 3959 | 2 | 0.5059 | 0.5578 | 0.6098 |
| Silver Lion (Venice) | 3975 | 2 | 0.1262 | 0.1789 | 0.2316 |
| Tiger Award (IFFR) | 4645 | 2 | 0.2858 | 0.2960 | 0.3061 |
| Un Certain Regard | 3673 | 2 | 0.2810 | 0.5064 | 0.7317 |
| Amplify Voices Award (TIFF) | 3970 | 1 | 0.0965 | 0.0965 | 0.0965 |
| BAFTA | 36 | 1 | 0.5830 | 0.5830 | 0.5830 |
| Best Director (Locarno) | 3957 | 1 | 0.3126 | 0.3126 | 0.3126 |
| Best Director (Un Certain Regard) | 4521 | 1 | 0.4278 | 0.4278 | 0.4278 |
| Changemaker Award (TIFF) | 3306 | 1 | 0.2584 | 0.2584 | 0.2584 |
| Documentary Australia Award (SFF) | 4658 | 1 | 0.3839 | 0.3839 | 0.3839 |
| Documentary Film Award (Berlinale) | 4432 | 1 | 0.5491 | 0.5491 | 0.5491 |
| Documentary Grand Jury Prize (Sundance) | 4437 | 1 | 0.5069 | 0.5069 | 0.5069 |
| F:ACT AWARD (CPH:DOX) | 3678 | 1 | 0.2706 | 0.2706 | 0.2706 |
| FIPRESCI Award (IFFR) | 4646 | 1 | 0.2858 | 0.2858 | 0.2858 |
| Golden Bear (Berlinale) | 3974 | 1 | 0.5322 | 0.5322 | 0.5322 |
| Golden Globe | 3378 | 1 | 0.3914 | 0.3914 | 0.3914 |
| Grand Jury Award (SXSW) | 3625 | 1 | 0.3803 | 0.3803 | 0.3803 |
| Grand Jury Prize (SXSW) | 3362 | 1 | 0.2944 | 0.2944 | 0.2944 |
| Heart of Sarajevo (SFF) | 4660 | 1 | 0.3368 | 0.3368 | 0.3368 |
| Jury Award (Sundance) | 3680 | 1 | 0.4615 | 0.4615 | 0.4615 |
| NEXT:WAVE AWARD | 3351 | 1 | 0.4417 | 0.4417 | 0.4417 |
| Panorama Audience Award (Berlinale) | 4431 | 1 | 0.5491 | 0.5491 | 0.5491 |
| Special Jury Award (SXSW) | 3569 | 1 | 0.5530 | 0.5530 | 0.5530 |
| Special Jury Award (Sundance) | 3960 | 1 | 0.4131 | 0.4131 | 0.4131 |
| Special Jury Prize (IFFR) | 4647 | 1 | 0.1873 | 0.1873 | 0.1873 |
| Special Jury Prize (Venice) | 4607 | 1 | 0.3464 | 0.3464 | 0.3464 |
| Youth Jury Award (IFFR) | 4649 | 1 | 0.4474 | 0.4474 | 0.4474 |

### categories

| term | term_id | stills | luma min | luma median | luma max |
| --- | --- | --- | --- | --- | --- |
| Music Videos | 3241 | 1836 | 0.0109 | 0.3078 | 0.9286 |
| Campaigns | 3242 | 1173 | 0.0302 | 0.3051 | 0.8749 |
| Movies | 3240 | 1039 | 0.0226 | 0.2902 | 0.8306 |
| Creative Shorts | 3243 | 434 | 0.0234 | 0.3126 | 0.9218 |
| Documentary Short | 3246 | 223 | 0.0590 | 0.3199 | 0.7284 |
| Narrative Short | 3252 | 192 | 0.0345 | 0.2517 | 0.6134 |
| Documentary | 3245 | 135 | 0.0965 | 0.3796 | 0.6743 |
| Video Essay | 3248 | 101 | 0.0463 | 0.3167 | 0.7835 |
| Interviews &amp; Talks | 3249 | 83 | 0.0555 | 0.3243 | 0.6987 |
| Shorts | 3244 | 48 | 0.0961 | 0.3073 | 0.8222 |
| Dance Short | 3254 | 45 | 0.0720 | 0.3104 | 0.8055 |
| Visual Essay | 3247 | 45 | 0.1078 | 0.3554 | 0.6919 |
| Film &amp; TV | 3255 | 21 | 0.1509 | 0.3270 | 0.6098 |
| Branded | 4700 | 18 | 0.0589 | 0.2976 | 0.4833 |
| Series | 3251 | 18 | 0.0617 | 0.3174 | 0.6881 |
| Editorial | 3250 | 5 | 0.1955 | 0.2994 | 0.4877 |
| Archive | 3257 | 3 | 0.1540 | 0.2747 | 0.3129 |

### festival

| term | term_id | stills | luma min | luma median | luma max |
| --- | --- | --- | --- | --- | --- |
| Cannes | 42 | 117 | 0.1084 | 0.3133 | 0.7317 |
| Sundance | 3312 | 90 | 0.0812 | 0.3025 | 0.6034 |
| Venice Biennale | 3309 | 66 | 0.0755 | 0.2912 | 0.6618 |
| Toronto (TIFF) | 3377 | 46 | 0.0560 | 0.2624 | 0.6463 |
| Berlinale | 3284 | 30 | 0.0977 | 0.3153 | 0.6218 |
| SXSW | 43 | 25 | 0.1497 | 0.2957 | 0.5530 |
| Telluride (TFF) | 3286 | 24 | 0.0987 | 0.2735 | 0.6463 |
| New York (NYFF) | 4633 | 18 | 0.1172 | 0.2697 | 0.6463 |
| Tribeca | 3387 | 18 | 0.1028 | 0.3044 | 0.5844 |
| BFI London | 3285 | 16 | 0.1054 | 0.2887 | 0.5710 |
| Locarno | 3293 | 14 | 0.0747 | 0.3325 | 0.5513 |
| CPH:DOX | 3353 | 13 | 0.2706 | 0.4135 | 0.6418 |
| Sheffield DocFest | 3360 | 9 | 0.2357 | 0.4739 | 0.6155 |
| San Sebastián | 4552 | 7 | 0.1054 | 0.2170 | 0.3464 |
| Directors' Fortnight | 3961 | 6 | 0.1702 | 0.2458 | 0.2895 |
| Karlovy Vary (KVIFF) | 4539 | 6 | 0.1996 | 0.2882 | 0.4384 |
| Rotterdam (IFFR) | 4644 | 6 | 0.1873 | 0.2863 | 0.4474 |
| Aesthetica | 3696 | 5 | 0.1046 | 0.2669 | 0.4741 |
| Clermont Ferrand | 4635 | 5 | 0.2200 | 0.2980 | 0.4778 |
| DOC NYC | 3947 | 5 | 0.3126 | 0.3804 | 0.5723 |
| Palm Springs ShortFest | 3691 | 5 | 0.2186 | 0.3773 | 0.4384 |
| Slamdance | 4428 | 5 | 0.2614 | 0.3387 | 0.4548 |
| CICLOPE | 4522 | 4 | 0.2235 | 0.4025 | 0.8284 |
| Hong Kong (HKIFF) | 4655 | 4 | 0.1063 | 0.2715 | 0.3804 |
| Melbourne (MIFF) | 4590 | 4 | 0.2148 | 0.2785 | 0.5236 |
| Sarajevo (SFF) | 4659 | 4 | 0.1172 | 0.3510 | 0.3993 |
| Sydney (SFF) | 4657 | 4 | 0.1172 | 0.2464 | 0.3839 |
| IDFA | 4556 | 3 | 0.2500 | 0.5236 | 0.5489 |
| Zurich (ZFF) | 4538 | 3 | 0.2148 | 0.2636 | 0.5236 |
| Brooklyn (BFF) | 3690 | 2 | 0.1408 | 0.1678 | 0.1948 |
| Critics' Week | 4433 | 2 | 0.1331 | 0.1699 | 0.2067 |
| Edinburgh (EIFF) | 4591 | 2 | 0.2000 | 0.2453 | 0.2906 |
| Göteborg (GFF) | 4746 | 2 | 0.1509 | 0.1998 | 0.2486 |
| Hamptons (HIFF) | 4547 | 2 | 0.3001 | 0.4245 | 0.5489 |
| Tokyo (TIFF) | 4694 | 2 | 0.2148 | 0.4114 | 0.6080 |
| Academy Awards | 3684 | 1 | 0.2860 | 0.2860 | 0.2860 |
| Berlin Fashion (BFFF) | 4707 | 1 | 0.1545 | 0.1545 | 0.1545 |
| DC/DOX | 4618 | 1 | 0.1489 | 0.1489 | 0.1489 |
| Durban (DIFF) | 4652 | 1 | 0.3117 | 0.3117 | 0.3117 |
| Hollyshorts | 4598 | 1 | 0.1820 | 0.1820 | 0.1820 |
| Young Arrows | 4545 | 1 | 0.3585 | 0.3585 | 0.3585 |

### format

| term | term_id | stills | luma min | luma median | luma max |
| --- | --- | --- | --- | --- | --- |
| Digital | 4525 | 259 | 0.0302 | 0.2726 | 0.9086 |
| 16mm | 40 | 134 | 0.0465 | 0.2869 | 0.6112 |
| 35mm | 41 | 94 | 0.0287 | 0.2807 | 0.9218 |
| Super8 | 3693 | 11 | 0.1497 | 0.3915 | 0.5870 |
| Super16 | 3737 | 10 | 0.0589 | 0.3696 | 0.9086 |
| AI | 4530 | 5 | 0.1106 | 0.2029 | 0.8188 |
| iPhone | 3729 | 4 | 0.2112 | 0.4253 | 0.6134 |
| 65mm | 3710 | 2 | 0.0926 | 0.2558 | 0.4189 |
| 8mm | 4615 | 2 | 0.2959 | 0.3094 | 0.3230 |
| DV | 4555 | 1 | 0.6764 | 0.6764 | 0.6764 |
| GoPro | 4668 | 1 | 0.4409 | 0.4409 | 0.4409 |
| HDCAM | 4620 | 1 | 0.4741 | 0.4741 | 0.4741 |
| Hi8 | 4559 | 1 | 0.1604 | 0.1604 | 0.1604 |
| IMAX | 4713 | 1 | 0.2164 | 0.2164 | 0.2164 |
| LiDAR | 4775 | 1 | 0.0649 | 0.0649 | 0.0649 |
| RED | 4630 | 1 | 0.3874 | 0.3874 | 0.3874 |

### location

| term | term_id | stills | luma min | luma median | luma max |
| --- | --- | --- | --- | --- | --- |
| United States | 3261 | 1846 | 0.0109 | 0.3051 | 0.9218 |
| United Kingdom | 3267 | 1079 | 0.0123 | 0.3163 | 0.9195 |
| France | 3268 | 431 | 0.0234 | 0.2957 | 0.9086 |
| Germany | 3265 | 139 | 0.0361 | 0.2747 | 0.7317 |
| Canada | 3314 | 127 | 0.0465 | 0.2664 | 0.8377 |
| Spain | 3266 | 120 | 0.0624 | 0.3049 | 0.9086 |
| The Netherlands | 3342 | 81 | 0.0302 | 0.3380 | 0.8656 |
| Italy | 3325 | 62 | 0.0932 | 0.2613 | 0.6442 |
| Australia | 3329 | 59 | 0.0587 | 0.2702 | 0.6813 |
| Denmark | 3318 | 52 | 0.1381 | 0.3005 | 0.6049 |
| Mexico | 3307 | 51 | 0.0836 | 0.2615 | 0.5793 |
| Japan | 3264 | 47 | 0.0982 | 0.3031 | 0.7191 |
| Sweden | 3320 | 47 | 0.0824 | 0.2995 | 0.7317 |
| Brazil | 3308 | 34 | 0.0754 | 0.2561 | 0.6112 |
| Norway | 3322 | 28 | 0.0720 | 0.2516 | 0.4301 |
| Belgium | 3304 | 26 | 0.0629 | 0.2375 | 0.5332 |
| India | 3386 | 24 | 0.0965 | 0.3257 | 0.6983 |
| Ireland | 3376 | 24 | 0.0345 | 0.2106 | 0.5236 |
| Poland | 3357 | 22 | 0.1438 | 0.2818 | 0.5446 |
| China | 3311 | 21 | 0.0681 | 0.2652 | 0.6390 |
| Georgia | 3500 | 20 | 0.0595 | 0.1822 | 0.4118 |
| Czech Republic | 3290 | 19 | 0.0226 | 0.1823 | 0.7284 |
| Russia | 3350 | 19 | 0.1427 | 0.2415 | 0.4417 |
| Argentina | 3332 | 18 | 0.1342 | 0.2385 | 0.5607 |
| South Africa | 3340 | 18 | 0.1017 | 0.3071 | 0.6027 |
| Switzerland | 3335 | 17 | 0.0703 | 0.2569 | 0.8557 |
| Ukraine | 3370 | 17 | 0.0595 | 0.3973 | 0.5069 |
| Morocco | 3632 | 16 | 0.0865 | 0.2140 | 0.6227 |
| Hungary | 3381 | 15 | 0.0849 | 0.2316 | 0.5868 |
| Greece | 3592 | 14 | 0.0851 | 0.2213 | 0.6707 |
| Iceland | 3535 | 14 | 0.1472 | 0.3242 | 0.6098 |
| South Korea | 3967 | 14 | 0.1063 | 0.2505 | 0.5710 |
| Egypt | 3482 | 13 | 0.1432 | 0.2655 | 0.4218 |
| Portugal | 3345 | 11 | 0.1808 | 0.2991 | 0.6866 |
| Qatar | 3698 | 11 | 0.1828 | 0.3061 | 0.6034 |
| Senegal | 3364 | 11 | 0.1195 | 0.4263 | 0.6353 |
| Latvia | 3368 | 10 | 0.1172 | 0.2800 | 0.4643 |
| New Zealand | 3366 | 10 | 0.1262 | 0.2402 | 0.4781 |
| Saudi Arabia | 3587 | 10 | 0.0978 | 0.2958 | 0.5462 |
| Austria | 3375 | 9 | 0.2520 | 0.3168 | 0.5349 |
| Hong Kong | 3685 | 9 | 0.1063 | 0.2682 | 0.5844 |
| Nigeria | 3349 | 9 | 0.1585 | 0.3291 | 0.5830 |
| Palestine | 4430 | 9 | 0.2003 | 0.4273 | 0.5491 |
| Serbia | 3509 | 9 | 0.1661 | 0.3368 | 0.6155 |
| Chile | 3347 | 8 | 0.2539 | 0.3948 | 0.6111 |
| Jamaica | 3483 | 8 | 0.1223 | 0.3547 | 0.5382 |
| Peru | 3633 | 8 | 0.2200 | 0.3013 | 0.4362 |
| Colombia | 3358 | 7 | 0.1046 | 0.1497 | 0.7317 |
| Ghana | 3297 | 7 | 0.1569 | 0.2726 | 0.5831 |
| Iran | 3938 | 7 | 0.2905 | 0.4273 | 0.5322 |

### record_label

| term | term_id | stills | luma min | luma median | luma max |
| --- | --- | --- | --- | --- | --- |
| Sony Music | 48 | 29 | 0.0624 | 0.3017 | 0.6593 |
| Universal Music | 3402 | 28 | 0.1023 | 0.2750 | 0.6796 |
| Interscope Records | 3405 | 21 | 0.0800 | 0.3075 | 0.6410 |
| Columbia Records | 50 | 20 | 0.0924 | 0.2981 | 0.6243 |
| XL Recordings | 3391 | 15 | 0.0988 | 0.3460 | 0.4240 |
| Atlantic Recording | 3486 | 14 | 0.1044 | 0.3121 | 0.4882 |
| AWAL Recordings | 3421 | 13 | 0.0992 | 0.2412 | 0.5799 |
| Polydor Records | 3538 | 13 | 0.0685 | 0.3301 | 0.6796 |
| RCA Records | 3425 | 12 | 0.0878 | 0.2291 | 0.5257 |
| Because Music | 3395 | 11 | 0.0123 | 0.2171 | 0.5914 |
| Top Dawg Entertainment | 3491 | 10 | 0.1499 | 0.1949 | 0.3881 |
| Warner Records | 3414 | 9 | 0.1324 | 0.2764 | 0.6296 |
| UMG Recordings | 3566 | 8 | 0.0429 | 0.1936 | 0.6260 |
| Animal 63 | 3523 | 7 | 0.1195 | 0.2206 | 0.6512 |
| Island Records | 3401 | 7 | 0.1962 | 0.4146 | 0.4643 |
| Capitol Records | 3944 | 6 | 0.1583 | 0.2300 | 0.4458 |
| Def Jam Recordings | 3501 | 6 | 0.1437 | 0.2263 | 0.5367 |
| EMI | 3423 | 6 | 0.1458 | 0.2679 | 0.4458 |
| BMG | 3497 | 5 | 0.1571 | 0.2257 | 0.3792 |
| Domino Records | 3493 | 5 | 0.0382 | 0.2051 | 0.4080 |
| Epic Records | 3433 | 5 | 0.1107 | 0.2760 | 0.5089 |
| Parlophone Records | 3502 | 5 | 0.1611 | 0.2580 | 0.5650 |
| Warp Records | 3427 | 5 | 0.0527 | 0.3241 | 0.5643 |
| Young | 3409 | 5 | 0.1834 | 0.3584 | 0.7975 |
| Aftermath | 3513 | 4 | 0.1948 | 0.2179 | 0.4276 |
| Cactus Jack Records | 3432 | 4 | 0.0190 | 0.0854 | 0.3845 |
| EMPIRE | 3550 | 4 | 0.2504 | 0.3691 | 0.4703 |
| Erskine Records | 3441 | 4 | 0.0798 | 0.3312 | 0.6243 |
| Geffen Records | 3598 | 4 | 0.3109 | 0.3427 | 0.4897 |
| Ninja Tune | 49 | 4 | 0.1182 | 0.2265 | 0.3773 |
| Partisan Records | 3399 | 4 | 0.0748 | 0.1614 | 0.3300 |
| Roc Nation Records | 3670 | 4 | 0.1223 | 0.2383 | 0.3023 |
| Warner Music | 3416 | 4 | 0.1528 | 0.2142 | 0.4655 |
| pgLang | 3522 | 4 | 0.1948 | 0.3327 | 0.5431 |
| A$AP Rocky Recordings | 3440 | 3 | 0.2910 | 0.4094 | 0.4298 |
| Arista Records | 3428 | 3 | 0.2490 | 0.2863 | 0.6593 |
| Atlantic Records | 4678 | 3 | 0.0747 | 0.2869 | 0.4969 |
| Dead Oceans | 3397 | 3 | 0.0933 | 0.2069 | 0.3901 |
| Dirty Hit | 3396 | 3 | 0.2482 | 0.3461 | 0.4510 |
| Fader Label | 4578 | 3 | 0.2141 | 0.3148 | 0.3275 |
| Mercury KX | 3520 | 3 | 0.2341 | 0.3551 | 0.3874 |
| OWSLA | 3487 | 3 | 0.2881 | 0.3361 | 0.3686 |
| Pond Recordings | 4486 | 3 | 0.2568 | 0.3193 | 0.5312 |
| Republic Records | 3578 | 3 | 0.0429 | 0.0685 | 0.2821 |
| Roche Musique | 3641 | 3 | 0.0915 | 0.1640 | 0.2618 |
| Self Help Tapes | 3392 | 3 | 0.1666 | 0.4026 | 0.4196 |
| 5020 Records | 3570 | 2 | 0.1342 | 0.3436 | 0.5530 |
| 88rising | 3549 | 2 | 0.1394 | 0.3113 | 0.4832 |
| Balaclava Records | 3603 | 2 | 0.2493 | 0.2871 | 0.3250 |
| Belting Bronco Records | 3949 | 2 | 0.1563 | 0.2236 | 0.2909 |

## What was measured, and what was not

The video lane measures YouTube entries only:

- Each video-measured row is a sampled source-PTS probe of the public YouTube rendition, obtained by a bounded, cookie-free local yt-dlp; it is not the work's delivered master.
- Vimeo references are recorded as `unsupported-vimeo` and were never fetched, probed, or player-inspected.
- No cookies, logins, browser profiles, remote components, or DRM/PO-token circumvention were used, and a provider refusal was never retried.
- Published poster stills are reported separately and never enter the motion, cut, luma, or saturation aggregates.

## Explicit non-claims

- A published poster still is not a video frame; single-image colour, luminance, histogram, hue, and edge-density numbers carry no motion, cut, pacing, timing, sequence, or edit-rhythm evidence.
- No style, aesthetic quality, mood, lighting, camera/lens, editorial intent, authorship, identity, or creative-origin inference is made from these numbers.
- Window values are samples; a full-film census value is film-level. Census cut candidates are still scene-score exceedances, not verified edits, and a strobe record's rate is not a cut rate.
- The poster is prepared by the site/CMS, not necessarily by the work's author; for STASH it may be a gallery image.
- Public availability is not a licence: `rightsStatus` remains `review-required`, and reuse needs its own review.
- Catalogue metadata is self-reported by the site and is not independently verified.
- The site's REST API exposes no director, duration, brand, or agency values for Directors' Library; those fields are absent, not invented.
- Downloaded poster images are never retained: only hashes and numbers remain.
- The measured source is a platform-encoded YouTube rendition, not the work's delivered master; every video number describes that rendition only.
- Downloaded video media is never retained: only hashes and numbers remain.
