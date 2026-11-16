# Motion Design Awards — measured reference report

This deliverable tabulates only what the committed evidence records contain: catalog metadata, sampled source-PTS numeric probes, and single-published-still metrics. It makes no aesthetic, stylistic, intentional, or authorship claim.

## Provenance

- Catalog projects: 1919
- Video-measured records: 491
- Unique media after dedupe: 490 (1 extra record(s) in 1 duplicate group(s))
- Still-measured records: 1901
- Still-only records (no matching video record): 1413
- Skipped unsupported (index context): 1418
- Skipped as already-measured (index context): 11
- Failed video acquisitions (index context): 9
- Failed still acquisitions (stills index context): 16
- Unreadable records: 0
- generatedAt: 2026-11-11T22:11:04.718890Z
- Note: index.json reports 481 measured video records while the record directory holds 491; this report reads the record files.
- Note: stills-index.json reports 1902 measured stills while the record directory holds 1901.

Reproduce the inputs and this report with:

```bash
python scripts/research_motiondesignawards.py catalog --out research/analysis/motiondesignawards/catalog.json
python scripts/research_motiondesignawards.py stills --catalog research/analysis/motiondesignawards/catalog.json --out-dir research/analysis/motiondesignawards --resume
python scripts/research_motiondesignawards.py collect --catalog research/analysis/motiondesignawards/catalog.json --out-dir research/analysis/motiondesignawards --acknowledge-rights
python scripts/research_motiondesignawards.py report --out-dir research/analysis/motiondesignawards --catalog research/analysis/motiondesignawards/catalog.json --top 20
```

Sampling caveat: coverage is `windows measured × window seconds ÷ runtime`; every window is a sample, not a full-film review. Across the tabulated records, 14695.0 s of 32151.3 s of runtime were measured (45.7%). Window values are samples; where present, `full_cuts_per_min` is film-level and `full_vs_window` states the difference (see `## Full-film census`).

## Per-video analysis

491 video-measured record(s), ordered by descending `wa_overall` then slug. All columns are numeric record fields; `bitrate_mbps` is derived from `sizeBytes ÷ durationSeconds` and `download_mb` from `sizeBytes ÷ 1,048,576`.

| slug | title | studio | category | awards | wa_overall | provider | runtime_s | resolution | fps | bitrate_mbps | download_mb | windows | coverage_pct | candidates_n | sampled_cut_candidates_per_min | full_cuts_per_min | full_vs_window | ci95 | burst | gap_frames | within_shot_pairs | cut_sep_pairs | delta_basis_pairs | validity | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| one-day-at-a-time | One Day at a Time | Crinimo.tv | SHORT_FILMS | VOTD, VOTM | 9.09 | cloudflare-stream | 62.40 | 1280x720 | 24.000 | 1.02 | 7.6 | 4 | 64.1 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.1048 | 0.8273 | 0.0760 |
| deep-thoughts-bounce | Deep Thoughts Bounce | Media.Monks | EXPERIMENTAL | VOTD, VOTY | 9.08 | direct-mp4 | 105.05 | 1920x1080 | 24.000 | 5.01 | 62.7 | 4 | 38.1 | 31 | 46.50 | 54.26 | -14% | 13.68-89.45 | 0.677 | 2.0 | 30 | 14 | 30 | burst-heavy, non-edit-scene-change | 0.5378 | 0.4288 | 0.0929 |
| styleframe-showreel-2025 | Styleframe Showreel 2025 | Styleframe | SELF_BRANDING | VOTD | 8.68 | cloudflare-stream | 80.04 | 1280x720 | 25.000 | 2.36 | 22.5 | 4 | 50.0 | 49 | 73.50 | 62.97 | +17% | 44.12-109.87 | 0.408 | 13.5 | 16 | 28 | 16 | — | 0.4199 | 0.3758 | 0.1295 |
| xiaomi-love-story | XIAOMI Love Story | KUTUKO STUDIO | ADVERTISING_COMMERCIALS | VOTD | 8.67 | cloudflare-stream | 47.77 | 1280x720 | 25.000 | 1.56 | 8.9 | 4 | 83.7 | 10 | 15.00 | 15.07 | +0% | 7.19-27.59 | 0.000 | 76.0 | 34 | 10 | 34 | — | 0.4662 | 0.5023 | 0.1004 |
| scarpa-ribelle-tech-20 | SCARPA — Ribelle Tech 2.0 | Subdivision Studio | ADVERTISING_CAMPAIGNS | VOTD, VOTM | 8.65 | cloudflare-stream | 32.04 | 1280x720 | 30.000 | 3.78 | 14.5 | 2 | 62.4 | 8 | 24.00 | 22.47 | +7% | 10.36-47.29 | 0.000 | 27.0 | 15 | 7 | 15 | — | 0.1517 | 0.3161 | 0.1323 |
| lumbre-brand-animation | LUMBRE Brand Animation | LUMBRE | SELF_BRANDING | VOTD | 8.58 | direct-mp4 | 20.96 | 1920x1080 | 25.000 | 8.33 | 20.8 | 1 | 47.7 | 3 | 18.00 | 8.59 | +110% | 3.71-52.60 | 0.000 | 75.5 | 8 | 3 | 8 | short-sample | 0.2386 | 0.4883 | 0.1422 |
| pantene-nutrient-blends | Pantene — Nutrient Blends | Ditroit | ADVERTISING_COMMERCIALS | VOTD | 8.58 | cloudflare-stream | 30.02 | 1280x720 | 30.000 | 3.69 | 13.2 | 2 | 66.6 | 9 | 27.00 | 27.98 | -4% | 12.35-51.25 | 0.000 | 41.5 | 14 | 8 | 14 | — | 0.6512 | 0.4217 | 0.1226 |
| how-to-make-sushi | How To Make Sushi | Jonathan Lindgren | SHORT_FILMS | VOTD | 8.57 | direct-mp4 | 139.04 | 1920x1080 | 24.000 | 10.27 | 170.1 | 4 | 28.8 | 8 | 12.00 | 15.10 | -21% | 3.20-27.03 | 0.000 | 65.0 | 36 | 8 | 36 | — | 0.6708 | 0.4787 | 0.0333 |
| gullwing-shortfilm | Gullwing - Shortfilm | Briktop | SHORT_FILMS | VOTD, VOTM | 8.56 | cloudflare-stream | 114.15 | 1084x480 | 25.000 | 1.73 | 23.5 | 4 | 35.0 | 19 | 28.50 | 32.59 | -13% | 8.40-56.86 | 0.263 | 36.5 | 27 | 17 | 27 | — | 0.5879 | 0.1117 | 0.1145 |
| how-countries-fight-their-wars | How Countries Fight Their Wars | MITSI STUDIO | SHORT_FILMS | VOTD, VOTM | 8.54 | cloudflare-stream | 124.05 | 1280x720 | 30.000 | 3.42 | 50.6 | 4 | 32.2 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.2209 | 0.3077 | 0.0846 |
| permission-to-move-three-easy-steps-to-recover-from-chronic-pain | Permission To Move \| Three Easy Steps to Recover from Chronic Pain | Niceshit Studio | ADVERTISING_COMMERCIALS | VOTD, VOTM | 8.53 | cloudflare-stream | 90.03 | 1280x720 | 24.000 | 3.96 | 42.5 | 4 | 44.4 | 12 | 18.00 | 17.33 | +4% | 1.09-44.13 | 0.333 | 50.0 | 36 | 8 | 36 | — | 0.5676 | 0.3594 | 0.0555 |
| bullpadel-vertex-05 | Bullpadel VERTEX 05 | KUTUKO STUDIO | ADVERTISING_COMMERCIALS | VOTD | 8.49 | cloudflare-stream | 31.25 | 1280x720 | 25.000 | 2.09 | 7.8 | 2 | 64.0 | 11 | 33.00 | 38.40 | -14% | 16.47-59.05 | 0.000 | 36.5 | 12 | 10 | 12 | — | 0.3796 | 0.5046 | 0.1662 |
| asphalt | ASPHALT | Albin MERLE | ADVERTISING_COMMERCIALS | VOTD | 8.46 | cloudflare-stream | 51.09 | 1280x720 | 25.000 | 4.17 | 25.4 | 4 | 78.3 | 20 | 30.00 | 27.01 | +11% | 18.32-46.33 | 0.200 | 50.0 | 27 | 17 | 27 | — | 0.2892 | 0.1594 | 0.2230 |
| microsoft-fluent-ui | Microsoft — Fluent UI | Vitaly Grossmann & Vincent Schwenk | LIVE_EVENT_TITLES | VOTD, VOTM, VOTY | 8.45 | cloudflare-stream | 61.46 | 1280x720 | 25.000 | 3.67 | 26.9 | 4 | 65.1 | 16 | 24.00 | 22.45 | +7% | 13.72-38.97 | 0.000 | 46.0 | 28 | 16 | 28 | — | 0.6476 | 0.1491 | 0.0894 |
| the-hidden-life-of-rosa-parks | The Hidden Life of Rosa Parks | Eido | SHORT_FILMS | VOTD | 8.45 | cloudflare-stream | 290.03 | 1280x720 | 24.000 | 3.61 | 124.7 | 4 | 13.8 | 34 | 51.00 | 22.55 | +126% | 15.73-96.59 | 0.912 | 3.0 | 33 | 11 | 33 | burst-heavy, low-coverage | 0.4971 | 0.2949 | 0.1818 |
| bmw-concept-i4-social-stings | BMW Concept i4 - social stings | Aixsponza | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 8.35 | direct-mp4 | 112.04 | 1080x1350 | 25.000 | 3.01 | 40.2 | 4 | 35.7 | 0 | 0.00 | 0.54 | -100% | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.5034 | 0.1439 | 0.1494 |
| hamilton-ventura-edge-skeleton-by-kutuko | Hamilton Ventura Edge Skeleton By Kutuko | KUTUKO STUDIO | ADVERTISING_COMMERCIALS | VOTD | 8.35 | cloudflare-stream | 36.82 | 1280x720 | 25.000 | 2.12 | 9.3 | 3 | 81.5 | 33 | 66.00 | 66.81 | -1% | 38.97-101.08 | 0.697 | 7.0 | 17 | 16 | 17 | burst-heavy | 0.2119 | 0.1122 | 0.1567 |
| mission-m101 | Mission M101 | Feed Me Light | ADVERTISING_CAMPAIGNS | VOTD | 8.35 | cloudflare-stream | 212.76 | 1280x720 | 25.000 | 3.64 | 92.4 | 4 | 18.8 | 22 | 33.00 | 51.33 | -36% | 1.92-75.79 | 0.636 | 14.0 | 29 | 15 | 29 | burst-heavy, low-coverage | 0.2757 | 0.4335 | 0.0729 |
| future-relics-tp-01 | Future Relics - TP_01 | Kinisi | SELF_BRANDING | VOTD, VOTM | 8.34 | cloudflare-stream | 51.05 | 1280x720 | 24.000 | 1.13 | 6.9 | 4 | 78.4 | 3 | 4.50 | 3.53 | +28% | 0.55-14.06 | 0.000 | 372.0 | 41 | 3 | 41 | — | 0.5431 | 0.0377 | 0.0967 |
| very-noise | Very Noise | MEAT DEPT. | MUSIC_VIDEOS | VOTD, VOTM, VOTY | 8.33 | cloudflare-stream | 156.84 | 1280x720 | 25.000 | 3.70 | 69.1 | 4 | 25.5 | 15 | 22.50 | 32.13 | -30% | 9.71-41.36 | 0.000 | 46.0 | 31 | 13 | 31 | — | 0.2661 | 0.1902 | 0.1104 |
| fork | Fork | Optical arts | SHORT_FILMS | VOTD | 8.30 | cloudflare-stream | 163.80 | 1204x480 | 25.000 | 1.75 | 34.1 | 4 | 24.4 | 33 | 49.50 | 23.08 | +114% | 0.00-146.79 | 0.606 | 8.0 | 29 | 15 | 29 | burst-heavy, low-coverage | 0.2040 | 0.4122 | 0.0833 |
| continental-adidas-by-kutuko | CONTINENTAL & ADIDAS - BY KUTUKO | KUTUKO STUDIO | ADVERTISING_COMMERCIALS | VOTD | 8.28 | cloudflare-stream | 36.10 | 1280x720 | 25.000 | 2.51 | 10.8 | 3 | 83.1 | 21 | 42.00 | 38.23 | +10% | 14.28-80.45 | 0.333 | 31.5 | 18 | 15 | 18 | — | 0.2487 | 0.4345 | 0.1777 |
| nike-air-max-95000 | Nike Air Max 95000 | Already Been chewed | ADVERTISING_CAMPAIGNS | VOTD, VOTM | 8.27 | cloudflare-stream | 28.71 | 1280x720 | 24.000 | 3.01 | 10.3 | 2 | 69.7 | 2 | 6.00 | 4.18 | +44% | 0.73-21.67 | 0.000 | 115.0 | 20 | 2 | 20 | — | 0.1073 | 0.1736 | 0.1262 |
| sainsburys-150th-anniversary | Sainsbury's 150th Anniversary | Feed Me Light | ADVERTISING_COMMERCIALS | VOTD | 8.27 | cloudflare-stream | 73.13 | 1280x720 | 29.970 | 4.16 | 36.3 | 4 | 54.7 | 23 | 34.50 | 34.46 | +0% | 21.87-51.77 | 0.000 | 52.5 | 21 | 23 | 21 | — | 0.4786 | 0.2215 | 0.1126 |
| brizo | Brizo - Jason Wu | Carbon | ADVERTISING_COMMERCIALS | VOTD | 8.26 | cloudflare-stream | 45.12 | 1280x720 | 23.976 | 3.60 | 19.4 | 4 | 88.7 | 18 | 27.00 | 23.94 | +13% | 16.00-42.67 | 0.000 | 40.0 | 26 | 18 | 26 | — | 0.2165 | 0.2870 | 0.1301 |
| krockio-manage-better-and-deliver-faster | Krock.io - Manage better and deliver faster | Hound Studio | ADVERTISING_COMMERCIALS | VOTD | 8.26 | cloudflare-stream | 83.03 | 1280x720 | 24.000 | 3.81 | 37.7 | 4 | 48.2 | 19 | 28.50 | 21.68 | +31% | 8.86-56.22 | 0.684 | 2.0 | 36 | 8 | 36 | burst-heavy, non-edit-scene-change | 0.4258 | 0.5912 | 0.0942 |
| select-sector-spdrs-2020 | Select Sector SPDRs ∙ 2020 | PlusOne® | ADVERTISING_CAMPAIGNS | VOTD | 8.26 | cloudflare-stream | 31.17 | 1280x720 | 29.970 | 3.73 | 13.9 | 2 | 64.2 | 22 | 66.00 | 65.45 | +1% | 41.36-99.92 | 0.000 | 22.0 | 4 | 18 | 4 | sparse-delta-basis | 0.6208 | 0.2365 | 0.1552 |
| i-am-intersex | I am intersex | Antimatter | EXPLANATORY_VIDEO | VOTD, VOTM | 8.24 | cloudflare-stream | 92.03 | 1280x720 | 15.000 | 3.27 | 35.9 | 4 | 43.5 | 2 | 3.00 | 7.82 | -62% | 0.36-10.84 | 0.000 | 371.0 | 42 | 2 | 42 | — | 0.5820 | 0.3413 | 0.0968 |
| mate | Mate? | Buda.tv | SHORT_FILMS | VOTD | 8.24 | cloudflare-stream | 140.03 | 1280x720 | 25.000 | 2.93 | 48.8 | 4 | 28.6 | 7 | 10.50 | 18.85 | -44% | 2.39-24.87 | 0.000 | 84.0 | 37 | 7 | 37 | — | 0.3370 | 0.3103 | 0.0791 |
| xiaomi-redmi-note-5-1 | Xiaomi Redmi Note 5 | Yambo Studio | ADVERTISING_COMMERCIALS | VOTD | 8.24 | cloudflare-stream | 60.02 | 1280x720 | 25.000 | 3.71 | 26.5 | 4 | 66.6 | 20 | 30.00 | 30.99 | -3% | 14.63-51.50 | 0.000 | 32.0 | 26 | 18 | 26 | — | 0.2810 | 0.4077 | 0.1202 |
| rawayana-welcome-to-el-sur | Rawayana - Welcome To El Sur | TOTEM.TV | MUSIC_VIDEOS | VOTD | 8.23 | cloudflare-stream | 211.84 | 1280x720 | 24.000 | 1.49 | 37.5 | 4 | 18.9 | 32 | 48.00 | 32.29 | +49% | 0.00-125.59 | 0.812 | 4.0 | 33 | 11 | 33 | burst-heavy, low-coverage | 0.3728 | 0.4042 | 0.1450 |
| re-opening-stargate | Re-Opening “Stargate” | MISTER | TITLE_SEQUENCES | VOTD, VOTY | 8.21 | cloudflare-stream | 59.54 | 1152x480 | 24.000 | 1.92 | 13.6 | 4 | 67.2 | 5 | 7.50 | 8.06 | -7% | 2.44-17.50 | 0.000 | 254.5 | 39 | 5 | 39 | — | 0.1132 | 0.3601 | 0.0465 |
| its-still-being-written | Its Still Being Written | Melanie Gohin | SHORT_FILMS | VOTD | 8.20 | cloudflare-stream | 90.07 | 1280x720 | 24.000 | 3.77 | 40.5 | 4 | 44.4 | 17 | 25.50 | 18.65 | +37% | 0.07-62.11 | 0.706 | 10.0 | 35 | 9 | 35 | burst-heavy | 0.4281 | 0.3598 | 0.0652 |
| the-season-opening-titles | The Season - Opening Titles | Hornet | BROADCAST_SERIES_TITLES | VOTD | 8.20 | cloudflare-stream | 62.10 | 1128x480 | 25.000 | 1.68 | 12.4 | 4 | 64.4 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.2143 | 0.6329 | 0.1819 |
| coto-supertamp | Coto - Supertamp | BUREAU KLAUS ALMAN | ADVERTISING_COMMERCIALS | VOTD | 8.18 | cloudflare-stream | 36.05 | 1280x720 | 25.000 | 3.24 | 13.9 | 3 | 83.2 | 9 | 18.00 | 18.31 | -2% | 8.23-34.17 | 0.000 | 53.0 | 24 | 9 | 24 | — | 0.1324 | 0.1995 | 0.0637 |
| finding-my-faith-1 | Finding my faith | Mabelous | SELF_BRANDING | VOTD | 8.17 | direct-mp4 | 92.54 | 1920x1080 | 24.000 | 11.51 | 126.9 | 4 | 43.2 | 0 | 0.00 | 2.59 | -100% | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.1092 | 0.6455 | 0.0673 |
| glass-by-gaviota | Glass by Gaviota | Promokore | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 8.16 | cloudflare-stream | 82.24 | 1280x720 | 25.000 | 0.48 | 4.7 | 4 | 48.6 | 0 | 0.00 | 0.73 | -100% | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.7500 | 0.0052 | 0.0379 |
| the-fall | The Fall | Vascolo | SHORT_FILMS | VOTD | 8.16 | cloudflare-stream | 148.46 | 1280x720 | 24.000 | 2.98 | 52.8 | 4 | 26.9 | 47 | 70.50 | 55.77 | +26% | 0.00-162.57 | 0.979 | 2.0 | 35 | 9 | 35 | burst-heavy, non-edit-scene-change | 0.1310 | 0.4167 | 0.0274 |
| blow | BLOW | Changhoon Nam | MUSIC_VIDEOS | VOTD | 8.13 | cloudflare-stream | 80.81 | 950x480 | 29.970 | 1.92 | 18.5 | 4 | 49.5 | 8 | 12.00 | 11.88 | +1% | 5.18-23.64 | 0.750 | 7.0 | 40 | 4 | 40 | burst-heavy | 0.2511 | 0.3700 | 0.1546 |
| pick-your-weapon | Pick Your Weapon | vicv.co | EXPERIMENTAL | VOTD | 8.13 | cloudflare-stream | 19.99 | 1280x720 | 24.000 | 1.29 | 3.1 | 1 | 50.0 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.1452 | 0.5011 | 0.0568 |
| the-living-system | The Living System | Valtteri LTD | EXPERIMENTAL | VOTD | 8.12 | cloudflare-stream | 141.87 | 1280x720 | 24.000 | 3.00 | 50.7 | 4 | 28.2 | 12 | 18.00 | 16.07 | +12% | 3.21-40.85 | 0.000 | 47.0 | 32 | 12 | 32 | — | 0.1560 | 0.5255 | 0.0666 |
| mtv-ident-lazy | MTV Ident : Lazy | Laura Sirvent | ADVERTISING_CAMPAIGNS | VOTD | 8.11 | direct-mp4 | 15.00 | 1280x720 | 25.000 | 10.27 | 18.4 | 1 | 66.7 | 3 | 18.00 | 20.00 | -10% | 3.71-52.60 | 0.000 | 39.0 | 8 | 3 | 8 | short-sample | 0.2808 | 0.5109 | 0.1991 |
| cartoon-network-sequencer-id-apple-onion | Cartoon Network - Sequencer ID "Apple & Onion" | LUMBRE | BROADCAST_CHANNEL_BRANDING | VOTD, VOTY | 8.10 | cloudflare-stream | 10.02 | 1280x720 | 25.000 | 3.40 | 4.1 | 1 | 89.8 | 4 | 26.67 | 53.89 | -51% | 7.27-68.28 | 1.000 | 2.0 | 10 | 1 | 10 | burst-heavy, non-edit-scene-change, short-sample | 0.8008 | 0.7709 | 0.0657 |
| mercedes-benz-digital-experience | Mercedes-Benz - Digital Experience | Sehsucht | ADVERTISING_COMMERCIALS | VOTD | 8.10 | cloudflare-stream | 133.76 | 1280x720 | 25.000 | 1.33 | 21.3 | 4 | 29.9 | 0 | 0.00 | 1.35 | -100% | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.8080 | 0.0599 | 0.0530 |
| brushes | Brushes | The DInk | EXPERIMENTAL | VOTD | 8.09 | cloudflare-stream | 80.83 | 1280x720 | 25.000 | 3.54 | 34.1 | 4 | 49.5 | 14 | 21.00 | 17.81 | +18% | 11.48-35.23 | 0.000 | 83.0 | 30 | 14 | 30 | — | 0.2148 | 0.2767 | 0.1120 |
| elan-vital | ÈLAN VITAL | Danny.film | ADVERTISING_COMMERCIALS | VOTD, VOTM | 8.08 | cloudflare-stream | 70.87 | 1130x480 | 25.000 | 1.73 | 14.6 | 4 | 56.4 | 15 | 22.50 | 33.87 | -34% | 0.00-61.64 | 0.333 | 21.5 | 33 | 11 | 33 | — | 0.1228 | 0.6306 | 0.0899 |
| its-about-time | IT'S ABOUT TIME | CLIM STUDIO | EXPERIMENTAL | VOTD | 8.08 | cloudflare-stream | 59.73 | 1280x720 | 24.000 | 3.67 | 26.2 | 4 | 67.0 | 12 | 18.00 | 18.08 | +0% | 9.30-31.44 | 0.000 | 63.0 | 33 | 11 | 33 | — | 0.5107 | 0.4706 | 0.0701 |
| visual-asmr | Visual ASMR | Onesal Studio | EXPERIMENTAL | VOTD | 8.07 | direct-mp4 | 68.37 | 1920x1080 | 30.000 | 15.27 | 124.5 | 4 | 58.5 | 21 | 31.50 | 31.59 | +0% | 17.73-50.61 | 0.000 | 40.0 | 26 | 18 | 26 | — | 0.3330 | 0.3643 | 0.0906 |
| plastic-health-coalition | Plastic health coalition | Antimatter | EXPLANATORY_VIDEO | VOTD | 8.05 | cloudflare-stream | 51.43 | 1280x720 | 15.000 | 3.09 | 19.0 | 4 | 77.8 | 12 | 18.00 | 21.00 | -14% | 9.30-31.44 | 0.000 | 54.0 | 32 | 12 | 32 | — | 0.5689 | 0.6354 | 0.1248 |
| herve-studio-reveal-brand-1 | Hervé Studio - Reveal brand | Hervé Studio | SELF_BRANDING | VOTD | 8.04 | cloudflare-stream | 46.59 | 1280x720 | 30.000 | 1.82 | 10.1 | 4 | 85.9 | 7 | 10.50 | 9.01 | +16% | 3.38-23.12 | 0.000 | 87.0 | 37 | 7 | 37 | — | 0.7050 | 0.2308 | 0.1613 |
| thoughtspot-beyond-2020-conference-open | ThoughtSpot Beyond 2020 Conference Open | leftchannel | LIVE_EVENT_TITLES | VOTD | 8.04 | cloudflare-stream | 38.10 | 1280x720 | 29.970 | 3.60 | 16.4 | 3 | 78.7 | 6 | 12.00 | 9.45 | +27% | 2.70-29.29 | 0.000 | 48.0 | 27 | 6 | 27 | — | 0.2527 | 0.5930 | 0.1203 |
| utopia-1 | Utopia | Optical arts | EXPERIMENTAL | VOTD | 8.04 | direct-mp4 | 113.52 | 3840x2160 | 25.000 | 9.99 | 135.2 | 4 | 35.2 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.4817 | 0.0000 | 0.0254 |
| bullpadel-vertex-04 | BULLPADEL VERTEX 04 | KUTUKO STUDIO | ADVERTISING_COMMERCIALS | — | 8.03 | cloudflare-stream | 31.10 | 1280x720 | 25.000 | 1.98 | 7.3 | 2 | 64.3 | 53 | 159.00 | 115.74 | +37% | 119.10-207.98 | 0.755 | 3.0 | 7 | 15 | 7 | burst-heavy, sparse-delta-basis | 0.5490 | 0.1299 | 0.1698 |
| httpsvimeocom560412242 | A Blue Wave | Studio River | EXPERIMENTAL | VOTD | 8.03 | cloudflare-stream | 93.59 | 1280x720 | 25.000 | 1.93 | 21.5 | 4 | 42.7 | 15 | 22.50 | 17.95 | +25% | 9.71-41.36 | 0.000 | 58.0 | 30 | 14 | 30 | — | 0.3213 | 0.2898 | 0.0962 |
| pause-fest-2020-pause-originals-cyberpunk-shanhaiching | Pause Fest 2020 Pause Originals: Cyberpunk Shanhaiching | Peng Lei (AKA LeiAlucard) | TITLE_SEQUENCES | VOTD | 8.03 | cloudflare-stream | 117.76 | 1146x480 | 25.000 | 1.87 | 26.2 | 4 | 34.0 | 6 | 9.00 | 9.68 | -7% | 0.00-34.94 | 0.333 | 51.0 | 39 | 5 | 39 | — | 0.1046 | 0.6702 | 0.0628 |
| particle-universe-collaboration-with-flank-audio | Particle Universe / Collaboration with Flank Audio | Vladislav Solovjov | SELF_BRANDING | VOTD | 8.00 | cloudflare-stream | 141.82 | 1280x720 | 25.000 | 3.52 | 59.6 | 4 | 28.2 | 17 | 25.50 | 16.50 | +55% | 14.85-40.83 | 0.000 | 46.5 | 27 | 17 | 27 | — | 0.2038 | 0.3484 | 0.1135 |
| plume-of-light | plume of light | plume.tv | SELF_BRANDING | VOTD | 7.98 | cloudflare-stream | 75.03 | 1148x480 | 25.000 | 1.93 | 17.3 | 4 | 53.3 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.2667 | 0.1725 | 0.0553 |
| plusone-cel-animation-reel | PlusOne® Cel Animation Reel | PlusOne® | SELF_BRANDING | VOTD | 7.98 | cloudflare-stream | 60.03 | 1280x720 | 25.000 | 2.33 | 16.7 | 4 | 66.6 | 42 | 63.00 | 51.97 | +21% | 44.99-85.68 | 0.571 | 12.0 | 21 | 23 | 21 | burst-heavy | 0.5209 | 0.4848 | 0.1179 |
| manifesto | MANIFESTO | Studio River | SELF_BRANDING | VOTD | 7.97 | cloudflare-stream | 96.26 | 1280x720 | 25.000 | 3.55 | 40.8 | 4 | 41.6 | 31 | 46.50 | 43.01 | +8% | 28.81-69.65 | 0.516 | 17.5 | 26 | 18 | 26 | burst-heavy | 0.4572 | 0.3849 | 0.0789 |
| refugium | Refugium | Johannes Kammerer | EXPERIMENTAL | VOTD | 7.96 | cloudflare-stream | 370.88 | 1280x720 | 25.000 | 3.66 | 162.0 | 4 | 10.8 | 14 | 21.00 | 27.18 | -23% | 10.41-36.84 | 0.143 | 65.0 | 33 | 11 | 33 | low-coverage | 0.4332 | 0.1298 | 0.1241 |
| birdie | Birdie | Ribbit | ADVERTISING_COMMERCIALS | — | 7.95 | cloudflare-stream | 29.42 | 1280x720 | 24.000 | 1.24 | 4.4 | 2 | 68.0 | 4 | 12.00 | 12.24 | -2% | 3.27-30.72 | 0.000 | 43.0 | 18 | 4 | 18 | — | 0.7703 | 0.1541 | 0.1026 |
| the-mini-vision-urbanaut-vibe | The MINI Vision Urbanaut / Vibe | Aixsponza | ADVERTISING_CAMPAIGNS | VOTD | 7.95 | cloudflare-stream | 58.94 | 1280x720 | 25.000 | 3.63 | 25.5 | 4 | 67.9 | 20 | 30.00 | 28.50 | +5% | 18.32-46.33 | 0.100 | 31.0 | 25 | 19 | 25 | — | 0.3611 | 0.3542 | 0.1747 |
| feed-the-urge | Feed The Urge | Woodwork Amsterdam | SELF_BRANDING | VOTD | 7.94 | direct-mp4 | 25.00 | 1920x1080 | 25.000 | 11.88 | 35.4 | 2 | 80.0 | 2 | 6.00 | 9.60 | -38% | 0.73-21.67 | 0.000 | 204.0 | 20 | 2 | 20 | — | 0.6344 | 0.6550 | 0.0559 |
| university-instructions-for-use | Welcome to University | deepsheep | EXPLANATORY_VIDEO | VOTD | 7.94 | cloudflare-stream | 149.12 | 1280x720 | 24.000 | 1.12 | 19.8 | 4 | 26.8 | 18 | 27.00 | 19.72 | +37% | 13.28-46.55 | 0.778 | 2.0 | 37 | 7 | 37 | burst-heavy, non-edit-scene-change | 0.6008 | 0.3936 | 0.0892 |
| koronapay | KoronaPay | Lenar Singatullov | ADVERTISING_COMMERCIALS | VOTD | 7.93 | cloudflare-stream | 20.02 | 1280x720 | 25.000 | 3.53 | 8.4 | 1 | 49.9 | 4 | 24.00 | 20.98 | +14% | 6.54-61.45 | 0.000 | 29.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.4020 | 0.5786 | 0.2007 |
| a-green-plan-for-our-cities-1 | A green plan for our cities | Rocketpanda | ADVERTISING_CAMPAIGNS | VOTD | 7.90 | cloudflare-stream | 67.11 | 1280x720 | 24.000 | 3.74 | 29.9 | 4 | 59.6 | 3 | 4.50 | 6.26 | -28% | 0.00-19.48 | 0.667 | 21.0 | 42 | 2 | 42 | burst-heavy | 0.4205 | 0.4063 | 0.0691 |
| shape | SHAPE | Fredcolin_ | FILM_GRAPHICS | VOTD, VOTY | 7.90 | cloudflare-stream | 80.13 | 1280x720 | 23.976 | 3.83 | 36.6 | 4 | 49.9 | 14 | 21.00 | 21.72 | -3% | 5.74-43.83 | 0.143 | 28.0 | 32 | 12 | 32 | — | 0.1482 | 0.2593 | 0.0638 |
| gummy-gas-crisis | Gummy Gas Crisis | Blirp studio | GAME_TITLES | VOTD | 7.89 | cloudflare-stream | 204.03 | 1280x720 | 24.000 | 3.30 | 80.3 | 4 | 19.6 | 19 | 28.50 | 21.47 | +33% | 5.08-61.55 | 0.368 | 13.0 | 33 | 11 | 33 | low-coverage | 0.4082 | 0.5960 | 0.1204 |
| kinisi-showreel-2025 | Kinisi \| Reel 2025 | Kinisi | SELF_BRANDING | VOTD | 7.89 | cloudflare-stream | 56.94 | 1280x720 | 24.000 | 1.33 | 9.0 | 4 | 70.3 | 24 | 36.00 | 33.72 | +7% | 20.46-57.11 | 0.167 | 39.0 | 23 | 21 | 23 | — | 0.5390 | 0.2660 | 0.0872 |
| retroys-1 | Ret(r)oys | Tomi Földes | EXPERIMENTAL | VOTD, VOTY | 7.89 | cloudflare-stream | 45.01 | 1080x1080 | 30.000 | 1.35 | 7.2 | 4 | 88.9 | 15 | 22.50 | 19.99 | +13% | 12.59-37.11 | 0.000 | 47.5 | 29 | 15 | 29 | — | 0.7512 | 0.1995 | 0.0827 |
| pop-up-magazine | Pop-Up Magazine | rafael de araujo | LIVE_EVENT_TITLES | VOTD | 7.88 | cloudflare-stream | 68.86 | 1280x720 | 12.000 | 3.60 | 29.6 | 4 | 58.1 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.5131 | 0.2591 | 0.1256 |
| cursor-stalker | Cursor Stalker | Péricles Motion | SHORT_FILMS | VOTD | 7.87 | cloudflare-stream | 32.49 | 1080x1350 | 30.000 | 5.83 | 22.6 | 2 | 61.6 | 0 | 0.00 | 0.00 | — | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.5760 | 0.6268 | 0.1807 |
| disenchanted | DISENCHANTED | Dongbin Kim | SHORT_FILMS | VOTD | 7.87 | cloudflare-stream | 129.22 | 1128x480 | 24.000 | 1.35 | 20.8 | 4 | 31.0 | 20 | 30.00 | 42.25 | -29% | 0.00-80.25 | 0.550 | 17.0 | 34 | 10 | 34 | burst-heavy | 0.1434 | 0.4180 | 0.0420 |
| google-chrome-enterprise | Google Chrome Enterprise | illo | ADVERTISING_CAMPAIGNS | VOTD | 7.87 | cloudflare-stream | 38.08 | 1280x720 | 25.000 | 1.42 | 6.5 | 3 | 78.8 | 6 | 12.00 | 15.76 | -24% | 4.40-26.12 | 0.000 | 53.0 | 27 | 6 | 27 | — | 0.8102 | 0.2964 | 0.1205 |
| lark-feishu-brand-film | LARK / FEISHU Brand Film | MERT KIZILAY | ADVERTISING_COMMERCIALS | VOTD | 7.87 | cloudflare-stream | 95.30 | 1280x720 | 30.000 | 3.81 | 43.2 | 4 | 42.0 | 6 | 9.00 | 11.96 | -25% | 2.99-20.16 | 0.000 | 184.0 | 38 | 6 | 38 | — | 0.5993 | 0.2039 | 0.0660 |
| loewe | LOEWE. | playd.team | ADVERTISING_COMMERCIALS | VOTD | 7.87 | cloudflare-stream | 61.70 | 1280x720 | 30.000 | 3.75 | 27.6 | 4 | 64.8 | 12 | 18.00 | 20.42 | -12% | 9.30-31.44 | 0.000 | 111.0 | 32 | 12 | 32 | — | 0.5008 | 0.2910 | 0.0977 |
| after-all | After All | Rob Norman - Director | EXPERIMENTAL | VOTD | 7.86 | cloudflare-stream | 96.53 | 1280x720 | 24.000 | 3.34 | 38.4 | 4 | 41.4 | 25 | 37.50 | 26.73 | +40% | 24.27-55.36 | 0.080 | 35.0 | 22 | 22 | 22 | — | 0.1504 | 0.2906 | 0.0784 |
| extraordinary | ExtraOrdinary | cgilpeiro | EXPERIMENTAL | VOTD | 7.86 | cloudflare-stream | 27.09 | 1152x720 | 30.000 | 1.91 | 6.2 | 2 | 73.8 | 3 | 9.00 | 6.64 | +35% | 1.86-26.30 | 0.000 | 153.0 | 19 | 3 | 19 | — | 0.4321 | 0.3461 | 0.1725 |
| town-portal-vanitas | Town Portal • Vanitas | Gabriele Calvi | MUSIC_VIDEOS | VOTD | 7.86 | cloudflare-stream | 369.13 | 1128x480 | 12.000 | 1.94 | 85.2 | 4 | 10.8 | 1 | 1.50 | 8.29 | -82% | 0.04-8.36 | — | — | 43 | 1 | 43 | low-coverage | 0.3128 | 0.2600 | 0.1048 |
| artifex-creatura-1 | Artifex Creatura | joanmoreno.tv | SELF_BRANDING | VOTD | 7.84 | cloudflare-stream | 35.46 | 1280x720 | 30.000 | 3.89 | 16.4 | 3 | 84.6 | 40 | 80.00 | 69.38 | +15% | 57.15-108.94 | 0.725 | 7.0 | 14 | 19 | 14 | burst-heavy | 0.3602 | 0.1464 | 0.1300 |
| kanu-the-pulse | Kanu - The Pulse | Gabriele Calvi | EXPERIMENTAL | VOTD | 7.84 | cloudflare-stream | 50.26 | 1280x720 | 24.000 | 0.74 | 4.4 | 4 | 79.6 | 4 | 6.00 | 5.97 | +1% | 0.00-24.72 | 1.000 | 2.0 | 42 | 2 | 42 | burst-heavy, non-edit-scene-change | 0.1960 | 0.1089 | 0.0762 |
| 2020-peace-elite-league-season3-1 | 2020-PEACE-ELITE-LEAGUE-Season3 | SolidStudio | ADVERTISING_COMMERCIALS | VOTD | 7.83 | cloudflare-stream | 95.15 | 1128x480 | 25.000 | 1.81 | 20.6 | 4 | 42.0 | 7 | 10.50 | 20.81 | -50% | 4.22-21.63 | 0.000 | 262.0 | 37 | 7 | 37 | — | 0.3153 | 0.2200 | 0.1210 |
| etos-luchtpost | Etos — Luchtpost | PlusOne® | ADVERTISING_COMMERCIALS | VOTD | 7.83 | cloudflare-stream | 25.02 | 1280x720 | 25.000 | 3.72 | 11.1 | 2 | 79.9 | 11 | 33.00 | 28.77 | +15% | 16.47-59.05 | 0.000 | 42.0 | 11 | 11 | 11 | — | 0.2802 | 0.5586 | 0.1129 |
| opkix-opkixone-launch | Opkix - OPKIXONE “Launch” | Already Been chewed | ADVERTISING_COMMERCIALS | VOTD | 7.82 | direct-mp4 | 23.12 | 1920x1080 | 24.000 | 3.91 | 10.8 | 2 | 86.5 | 5 | 15.00 | 15.57 | -4% | 4.87-35.00 | 0.000 | 68.0 | 17 | 5 | 17 | — | 0.1540 | 0.3962 | 0.1164 |
| 24hmotion | 24hchuyendong | 24hchuyendong | SELF_BRANDING | — | 7.81 | cloudflare-stream | 92.10 | 1280x720 | 25.000 | 2.73 | 29.9 | 4 | 43.4 | 30 | 45.00 | 101.63 | -56% | 0.00-106.38 | 0.500 | 21.0 | 24 | 20 | 24 | — | 0.5448 | 0.3790 | 0.2575 |
| brompton-house-home-of-baking | Brompton House - Home of Baking | Framelight Studio | ADVERTISING_COMMERCIALS | VOTD | 7.81 | cloudflare-stream | 73.34 | 1280x720 | 25.000 | 3.50 | 30.6 | 4 | 54.5 | 77 | 115.50 | 73.63 | +57% | 1.82-250.22 | 0.961 | 2.0 | 31 | 13 | 31 | burst-heavy, non-edit-scene-change | 0.5541 | 0.5066 | 0.0685 |
| lucky-penny | Lucky Penny | Hornet | SHORT_FILMS | VOTD | 7.81 | cloudflare-stream | 30.46 | 1280x720 | 24.000 | 1.25 | 4.6 | 2 | 65.7 | 34 | 102.00 | 76.81 | +33% | 70.64-142.53 | 0.941 | 2.0 | 14 | 8 | 14 | burst-heavy, non-edit-scene-change | 0.5953 | 0.4824 | 0.1131 |
| staypes-5 | StayPes | PES Motion Studio | ADVERTISING_CAMPAIGNS | VOTD | 7.81 | cloudflare-stream | 63.45 | 1280x720 | 24.000 | 4.13 | 31.3 | 4 | 63.0 | 3 | 4.50 | 7.57 | -41% | 0.55-14.06 | 0.667 | 279.5 | 42 | 2 | 42 | burst-heavy | 0.5752 | 0.5235 | 0.1302 |
| motion-design-reel-main-titles | Motion Design Reel \| Main Titles | Laurent Zagury | TITLE_SEQUENCES | HM, VOTY | 7.80 | cloudflare-stream | 66.03 | 1280x720 | 24.000 | 1.33 | 10.5 | 4 | 60.6 | 12 | 18.00 | 29.08 | -38% | 5.70-37.01 | 0.500 | 42.0 | 34 | 10 | 34 | — | 0.1386 | 0.4153 | 0.0607 |
| teflon-reimagined | Teflon - Reimagined | Carbon | ADVERTISING_COMMERCIALS | VOTD | 7.80 | cloudflare-stream | 26.56 | 1280x720 | 23.976 | 3.34 | 10.6 | 2 | 75.3 | 2 | 6.00 | 4.52 | +33% | 0.73-21.67 | 0.000 | 35.0 | 20 | 2 | 20 | — | 0.2264 | 0.3839 | 0.1552 |
| 2020-showreel | 2020 Showreel | fiber.graphics | ADVERTISING_COMMERCIALS | VOTD | 7.79 | cloudflare-stream | 95.06 | 1280x720 | 25.000 | 3.45 | 39.1 | 4 | 42.1 | 25 | 37.50 | 34.71 | +8% | 24.27-55.36 | 0.000 | 28.0 | 21 | 23 | 21 | — | 0.4458 | 0.3370 | 0.0907 |
| nike-jordan-react-dfg | Nike Jordan React DFG | Daniyar Oskenbay | BROADCAST_CHANNEL_BRANDING | VOTD | 7.79 | cloudflare-stream | 60.05 | 1280x720 | 29.970 | 2.99 | 21.4 | 4 | 66.6 | 17 | 25.50 | 21.98 | +16% | 9.51-48.52 | 0.000 | 61.0 | 27 | 17 | 27 | — | 0.2846 | 0.1357 | 0.0887 |
| adidas-zne | Adidas Z.N.E | Sugar Blood / Pedro Allevato | ADVERTISING_COMMERCIALS | VOTD | 7.78 | cloudflare-stream | 30.42 | 1280x720 | 25.000 | 3.37 | 12.2 | 2 | 65.7 | 74 | 222.00 | 207.09 | +7% | 174.32-278.70 | 0.824 | 2.0 | 4 | 18 | 4 | burst-heavy, non-edit-scene-change, sparse-delta-basis | 0.5047 | 0.2243 | 0.1669 |
| eni | Eni+ | PlusOne® | ADVERTISING_CAMPAIGNS | VOTD | 7.78 | direct-mp4 | 30.00 | 1920x1080 | 25.000 | 15.95 | 57.0 | 2 | 66.7 | 5 | 15.00 | 10.00 | +50% | 4.87-35.00 | 1.000 | 2.0 | 21 | 1 | 21 | burst-heavy, non-edit-scene-change | 0.8557 | 0.0854 | 0.0614 |
| adult-behavior | Adult Behavior | Naive | BROADCAST_SERIES_TITLES | VOTD, VOTY | 7.77 | cloudflare-stream | 16.43 | 1280x720 | 25.000 | 0.95 | 1.9 | 1 | 60.9 | 3 | 18.00 | 14.61 | +23% | 3.71-52.60 | 0.000 | 70.5 | 8 | 3 | 8 | short-sample | 0.3906 | 0.6199 | 0.0934 |
| cariuma-catiba-x-berrics-release | Cariuma Catiba x Berrics Release | Already Been chewed | ADVERTISING_CAMPAIGNS | VOTD | 7.77 | cloudflare-stream | 29.99 | 1280x720 | 24.000 | 3.51 | 12.6 | 2 | 66.7 | 3 | 9.00 | 12.00 | -25% | 1.86-26.30 | 0.000 | 223.0 | 19 | 3 | 19 | — | 0.1783 | 0.0785 | 0.1203 |
| christmas-legend | Christmas legend | SHED | ADVERTISING_COMMERCIALS | VOTD | 7.77 | cloudflare-stream | 90.13 | 1280x720 | 23.976 | 1.84 | 19.8 | 4 | 44.4 | 13 | 19.50 | 17.97 | +8% | 10.38-33.35 | 0.000 | 43.5 | 31 | 13 | 31 | — | 0.2442 | 0.3949 | 0.0896 |
| nextatlas | Nextatlas | illo | EXPLANATORY_VIDEO | VOTD | 7.77 | cloudflare-stream | 67.03 | 1280x720 | 25.000 | 3.37 | 26.9 | 4 | 59.7 | 27 | 40.50 | 40.28 | +1% | 17.79-70.80 | 0.926 | 2.0 | 33 | 11 | 33 | burst-heavy, non-edit-scene-change | 0.6441 | 0.2413 | 0.0901 |
| whisk | Launching Whisk with Google Labs | Hook | ADVERTISING_CAMPAIGNS | VOTD | 7.77 | cloudflare-stream | 51.48 | 1280x720 | 30.000 | 1.46 | 8.9 | 4 | 77.7 | 7 | 10.50 | 10.49 | +0% | 4.22-21.63 | 0.000 | 116.0 | 38 | 6 | 38 | — | 0.5828 | 0.5996 | 0.2026 |
| dof-motion-brandbook | DOF • Motion Brandbook | Pool Studio | SELF_BRANDING | VOTD | 7.76 | cloudflare-stream | 31.08 | 1280x720 | 25.000 | 1.59 | 5.9 | 2 | 64.3 | 31 | 93.00 | 65.63 | +42% | 63.19-132.01 | 0.903 | 4.0 | 11 | 11 | 11 | burst-heavy | 0.5318 | 0.0358 | 0.1343 |
| from-the-lucky-summer-of-2020-1 | From the lucky Summer of 2020 | Mauro Mason | EXPLANATORY_VIDEO | VOTD | 7.76 | cloudflare-stream | 69.93 | 1280x720 | 24.000 | 3.71 | 30.9 | 4 | 57.2 | 8 | 12.00 | 11.15 | +8% | 0.00-34.30 | 0.500 | 49.0 | 39 | 5 | 39 | — | 0.5979 | 0.3980 | 0.0401 |
| neo-oven | NEO OVEN SERIE | KUTUKO STUDIO | ADVERTISING_COMMERCIALS | VOTD | 7.76 | cloudflare-stream | 72.41 | 1280x720 | 25.000 | 1.19 | 10.3 | 4 | 55.2 | 7 | 10.50 | 11.60 | -9% | 2.39-24.87 | 0.000 | 77.5 | 37 | 7 | 37 | — | 0.1318 | 0.2287 | 0.0908 |
| dalai-lamas-guide-to-happiness-pt02 | Dalai Lama's guide to happiness pt.02 | kien nt | EXPERIMENTAL | VOTD | 7.75 | direct-mp4 | 80.83 | 1920x1080 | 24.000 | 29.61 | 285.4 | 4 | 49.5 | 2 | 3.00 | 1.48 | +102% | 0.36-10.84 | 0.000 | 373.0 | 42 | 2 | 42 | — | 0.8055 | 0.0305 | 0.0834 |
| moonstone | Moonstone | Artur Gadzhiev | ADVERTISING_COMMERCIALS | VOTD | 7.75 | cloudflare-stream | 49.34 | 1280x720 | 24.000 | 2.96 | 17.4 | 4 | 81.1 | 13 | 19.50 | 15.81 | +23% | 10.38-33.35 | 0.000 | 71.5 | 31 | 13 | 31 | — | 0.7015 | 0.0647 | 0.1011 |
| bioo-3-techs-by-kutuko | Bioo 3 Techs by Kutuko | KUTUKO STUDIO | ADVERTISING_CAMPAIGNS | VOTD | 7.74 | cloudflare-stream | 101.03 | 1280x720 | 25.000 | 2.74 | 33.1 | 4 | 39.6 | 7 | 10.50 | 7.72 | +36% | 4.22-21.63 | 0.000 | 328.0 | 37 | 7 | 37 | — | 0.3154 | 0.4113 | 0.1118 |
| ettoday-9th-id-1 | ETtoday 9th ID | Yen C Chen | BROADCAST_CHANNEL_BRANDING | VOTD | 7.74 | cloudflare-stream | 30.23 | 1280x720 | 30.000 | 3.74 | 13.5 | 2 | 66.2 | 11 | 33.00 | 31.76 | +4% | 16.47-59.05 | 0.000 | 36.5 | 12 | 10 | 12 | — | 0.5212 | 0.3127 | 0.1784 |
| crumb-studio-rebrand | Crumb Studio Rebrand | Crumb Studio | SELF_BRANDING | VOTD, VOTM | 7.73 | cloudflare-stream | 34.05 | 1280x720 | 25.000 | 1.60 | 6.5 | 3 | 88.1 | 11 | 22.00 | 19.38 | +13% | 5.39-48.18 | 0.182 | 52.5 | 23 | 10 | 23 | — | 0.7034 | 0.1806 | 0.1713 |
| mediamonks-animation-reel-intro-1 | Mediamonks Animation Reel Intro | Media.Monks | SELF_BRANDING | VOTD | 7.73 | cloudflare-stream | 16.55 | 1280x720 | 24.000 | 3.86 | 7.6 | 1 | 60.4 | 13 | 78.00 | 47.12 | +66% | 41.53-133.38 | 0.923 | 2.0 | 7 | 4 | 7 | burst-heavy, non-edit-scene-change, short-sample, sparse-delta-basis | 0.1099 | 0.2676 | 0.0351 |
| saint-x-beautiful-sky | Saint X - Beautiful Skies | Ronin161 | MUSIC_VIDEOS | — | 7.73 | cloudflare-stream | 348.51 | 1128x480 | 24.000 | 0.93 | 38.7 | 4 | 11.5 | 3 | 4.50 | 4.30 | +5% | 0.00-19.48 | 0.000 | 103.0 | 41 | 3 | 41 | low-coverage | 0.2719 | 0.3081 | 0.0572 |
| till-this-day | Till This Day | Nako Baev | SHORT_FILMS | VOTD | 7.73 | cloudflare-stream | 29.74 | 1128x480 | 30.000 | 0.76 | 2.7 | 2 | 67.3 | 3 | 9.00 | 10.09 | -11% | 1.86-26.30 | 0.000 | 197.0 | 19 | 3 | 19 | — | 0.0681 | 0.3698 | 0.0399 |
| copenhagen | Copenhagen | Kinisi | SELF_BRANDING | VOTD | 7.72 | cloudflare-stream | 10.56 | 1280x720 | 30.000 | 1.80 | 2.3 | 1 | 85.2 | 5 | 33.33 | 28.41 | +17% | 10.82-77.79 | 0.800 | 15.0 | 7 | 4 | 7 | burst-heavy, short-sample, sparse-delta-basis | 0.7807 | 0.1116 | 0.1619 |
| the-story-of-coffee | The Story of Coffee | Motionlab | EXPLANATORY_VIDEO | VOTD | 7.72 | cloudflare-stream | 58.69 | 1280x720 | 24.000 | 3.51 | 24.5 | 4 | 68.2 | 6 | 9.00 | 9.20 | -2% | 2.99-20.16 | 0.000 | 54.0 | 38 | 6 | 38 | — | 0.3079 | 0.4654 | 0.1158 |
| 2020-foresight-1 | // 2020 FORESIGHT // | Danny Stern | SHORT_FILMS | VOTD | 7.71 | cloudflare-stream | 40.04 | 1280x720 | 25.000 | 3.68 | 17.6 | 3 | 74.9 | 6 | 12.00 | 10.49 | +14% | 1.26-31.97 | 0.500 | 7.0 | 30 | 3 | 30 | — | 0.0780 | 0.0000 | 0.0917 |
| bam-is-back | BAM is BACK | Aixsponza | ADVERTISING_CAMPAIGNS | VOTD | 7.71 | cloudflare-stream | 66.71 | 1280x720 | 25.000 | 3.81 | 30.3 | 4 | 60.0 | 3 | 4.50 | 2.70 | +67% | 0.93-13.15 | 0.000 | 368.5 | 41 | 3 | 41 | — | 0.1072 | 0.2227 | 0.0281 |
| bioshell | Bioshell | Yakoub Gr | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.71 | cloudflare-stream | 21.53 | 1280x720 | 30.000 | 2.97 | 7.6 | 1 | 46.5 | 4 | 24.00 | 22.30 | +8% | 6.54-61.45 | 0.000 | 39.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.3254 | 0.2172 | 0.1245 |
| loewe-ballet-runner | LOEWE  "Ballet Runner" | TAVO STUDIO | ADVERTISING_CAMPAIGNS | VOTD | 7.71 | cloudflare-stream | 37.46 | 1280x720 | 25.000 | 3.30 | 14.7 | 3 | 80.1 | 6 | 12.00 | 14.41 | -17% | 4.40-26.12 | 0.000 | 61.0 | 27 | 6 | 27 | — | 0.6535 | 0.0576 | 0.1102 |
| primordial-abyss | PRIMORDIAL ABYSS | KUTUKO STUDIO | EXPERIMENTAL | — | 7.71 | cloudflare-stream | 34.88 | 1280x720 | 25.000 | 1.53 | 6.4 | 3 | 86.0 | 6 | 12.00 | 10.32 | +16% | 4.40-26.12 | 0.000 | 90.0 | 27 | 6 | 27 | — | 0.3397 | 0.5140 | 0.1051 |
| red-square-anime | RED SQUARE \| anime | tribute CG | ADVERTISING_COMMERCIALS | VOTD | 7.71 | cloudflare-stream | 38.06 | 1280x720 | 24.000 | 2.41 | 10.9 | 3 | 78.8 | 35 | 70.00 | 59.91 | +17% | 29.54-122.10 | 0.600 | 16.0 | 11 | 22 | 11 | burst-heavy | 0.3828 | 0.5214 | 0.1340 |
| inspirational-2020 | INSPIRATIONAL 2020 | MACH STUDIO | TITLE_SEQUENCES | VOTD | 7.70 | cloudflare-stream | 115.54 | 1280x720 | 25.000 | 3.73 | 51.3 | 4 | 34.6 | 8 | 12.00 | 14.54 | -17% | 5.18-23.64 | 0.000 | 89.0 | 36 | 8 | 36 | — | 0.5562 | 0.3382 | 0.0858 |
| jump | JUMP 2.0 | Tonic DNA | EXPERIMENTAL | VOTD | 7.70 | cloudflare-stream | 84.99 | 1280x720 | 24.000 | 2.25 | 22.7 | 4 | 47.1 | 39 | 58.50 | 50.12 | +17% | 0.00-133.28 | 0.667 | 4.0 | 24 | 20 | 24 | burst-heavy | 0.4159 | 0.6609 | 0.1058 |
| kconex | KCONEX | George Hurrell | SELF_BRANDING | VOTD | 7.70 | cloudflare-stream | 104.55 | 1280x720 | 30.000 | 3.77 | 47.0 | 4 | 38.3 | 20 | 30.00 | 45.34 | -34% | 0.00-72.59 | 0.600 | 9.0 | 36 | 8 | 36 | burst-heavy | 0.0731 | 0.6936 | 0.0759 |
| simulacra-trailer | SIMULACRA-TRAILER | Curry Sicong Tian | EXPERIMENTAL | VOTD | 7.70 | cloudflare-stream | 34.54 | 940x480 | 30.000 | 2.07 | 8.5 | 3 | 86.9 | 6 | 12.00 | 13.90 | -14% | 2.70-29.29 | 0.000 | 108.0 | 27 | 6 | 27 | — | 0.0607 | 0.6152 | 0.0541 |
| bbc-world-service-designing-for-global-users | BBC World Service: Designing for Global Users | Buff | EXPLANATORY_VIDEO | VOTD | 7.69 | cloudflare-stream | 143.64 | 1280x720 | 25.000 | 3.80 | 65.1 | 4 | 27.8 | 6 | 9.00 | 16.29 | -45% | 2.99-20.16 | 0.000 | 135.0 | 38 | 6 | 38 | — | 0.4292 | 0.4060 | 0.0480 |
| hellberg-xstream | Hellberg - Xstream | Haymaker | ADVERTISING_COMMERCIALS | VOTD | 7.69 | cloudflare-stream | 42.03 | 1280x720 | 25.000 | 3.37 | 16.9 | 3 | 71.4 | 3 | 6.00 | 5.71 | +5% | 0.00-25.98 | 0.000 | 72.0 | 30 | 3 | 30 | — | 0.0878 | 0.4493 | 0.0640 |
| on-cyclon-2 | On - Cyclon | Roman Kaelin | ADVERTISING_CAMPAIGNS | VOTD | 7.69 | cloudflare-stream | 24.87 | 1280x720 | 30.000 | 2.99 | 8.9 | 2 | 80.4 | 0 | 0.00 | 2.41 | -100% | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.9040 | 0.0096 | 0.0745 |
| quarantine-loops | Quarantine Loops | CLIM STUDIO | SELF_BRANDING | VOTD | 7.69 | cloudflare-stream | 54.36 | 1280x720 | 24.000 | 0.69 | 4.4 | 4 | 73.6 | 9 | 13.50 | 18.76 | -28% | 6.17-25.63 | 0.000 | 124.0 | 35 | 9 | 35 | — | 0.5020 | 0.5973 | 0.0300 |
| akima | Akima | illo | EXPLANATORY_VIDEO | VOTD | 7.68 | direct-mp4 | 175.62 | 1920x1080 | 24.000 | 15.47 | 323.9 | 4 | 22.8 | 17 | 25.50 | 23.57 | +8% | 0.00-69.85 | 0.706 | 4.0 | 35 | 9 | 35 | burst-heavy, low-coverage | 0.6570 | 0.1712 | 0.0665 |
| deadline | Deadline | Kathy Yu | SHORT_FILMS | VOTD | 7.67 | cloudflare-stream | 104.96 | 1280x720 | 24.000 | 1.68 | 21.0 | 4 | 38.1 | 17 | 25.50 | 20.58 | +24% | 10.67-46.86 | 0.118 | 38.5 | 28 | 16 | 28 | — | 0.4078 | 0.4023 | 0.1128 |
| fdl | Fdl | Studio Sentempo | ADVERTISING_CAMPAIGNS | VOTD | 7.67 | cloudflare-stream | 36.39 | 1280x720 | 25.000 | 2.64 | 11.5 | 3 | 82.4 | 5 | 10.00 | 9.89 | +1% | 3.25-23.34 | 0.000 | 163.5 | 28 | 5 | 28 | — | 0.6276 | 0.0534 | 0.0696 |
| httpsvimeocom1066856784sharecopy | Perch Light | Seungpyo Han | ADVERTISING_COMMERCIALS | VOTD | 7.67 | cloudflare-stream | 71.51 | 1280x720 | 24.000 | 0.85 | 7.2 | 4 | 55.9 | 8 | 12.00 | 12.59 | -5% | 5.18-23.64 | 0.000 | 133.0 | 36 | 8 | 36 | — | 0.4432 | 0.4119 | 0.0519 |
| mr-robot-title-design-unofficial | Mr. Robot - Title Design (unofficial) | Danny.film | BROADCAST_SERIES_TITLES | VOTD | 7.67 | direct-mp4 | 72.00 | 1920x810 | 25.000 | 18.16 | 155.9 | 4 | 55.6 | 2 | 3.00 | 1.67 | +80% | 0.00-14.08 | 0.000 | 92.0 | 42 | 2 | 42 | — | 0.0456 | 0.7195 | 0.0395 |
| ardr | Mattr - Ardr | Mattr | EXPERIMENTAL | VOTD | 7.66 | direct-mp4 | 267.00 | 1920x1080 | 25.000 | 6.77 | 215.6 | 4 | 15.0 | 11 | 16.50 | 15.96 | +3% | 4.04-36.13 | 0.273 | 65.5 | 35 | 9 | 35 | low-coverage | 0.2764 | 0.0294 | 0.0689 |
| beamwallet | BeamWallet | Antimatter | EXPLANATORY_VIDEO | VOTD | 7.66 | cloudflare-stream | 71.17 | 1280x720 | 15.000 | 2.88 | 24.5 | 4 | 56.2 | 6 | 9.00 | 9.27 | -3% | 3.30-19.59 | 0.333 | 220.0 | 39 | 5 | 39 | — | 0.6744 | 0.2521 | 0.1624 |
| life | Life | The Beard Hunter | EXPERIMENTAL | VOTD | 7.66 | cloudflare-stream | 114.20 | 1146x480 | 25.000 | 1.87 | 25.5 | 4 | 35.0 | 17 | 25.50 | 21.54 | +18% | 12.59-44.09 | 0.000 | 42.5 | 28 | 16 | 28 | — | 0.1801 | 0.3892 | 0.0478 |
| ray-q-rf-fiber-optics | Ray-Q - RF & Fiber-Optics | SHOOF | EXPLANATORY_VIDEO | — | 7.66 | cloudflare-stream | 101.70 | 1280x720 | 25.000 | 1.72 | 20.9 | 4 | 39.3 | 10 | 15.00 | 13.57 | +11% | 7.19-27.59 | 0.000 | 89.0 | 34 | 10 | 34 | — | 0.5636 | 0.1507 | 0.1258 |
| sweet | Sweet! | Rocket Lab Creative | SHORT_FILMS | VOTD | 7.66 | cloudflare-stream | 16.49 | 1280x720 | 24.000 | 1.82 | 3.6 | 1 | 60.6 | 6 | 36.00 | 25.47 | +41% | 13.21-78.36 | 0.000 | 34.0 | 5 | 6 | 5 | short-sample, sparse-delta-basis | 0.4396 | 0.4232 | 0.1476 |
| landfill-2 | Landfill | Plexus Motion | MUSIC_VIDEOS | VOTD | 7.65 | cloudflare-stream | 195.75 | 608x1080 | 25.000 | 5.33 | 124.4 | 4 | 20.4 | 22 | 33.00 | 26.36 | +25% | 7.09-68.68 | 0.409 | 30.0 | 29 | 15 | 29 | low-coverage | 0.5655 | 0.4072 | 0.1741 |
| serbin-creative-directory-of-illustration | BluBlu Studios: Serbin Creative + Directory of Illustration | BluBlu Studios | EXPLANATORY_VIDEO | VOTD | 7.65 | cloudflare-stream | 83.35 | 1280x720 | 25.000 | 3.68 | 36.5 | 4 | 48.0 | 2 | 3.00 | 2.88 | +4% | 0.36-10.84 | 0.000 | 1054.0 | 42 | 2 | 42 | — | 0.5211 | 0.4137 | 0.1648 |
| gantri-the-seed-of-inspiration | Gantri — The Seed of Inspiration | O0 Design | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.64 | cloudflare-stream | 47.41 | 1280x720 | 30.000 | 2.09 | 11.8 | 4 | 84.4 | 2 | 3.00 | 2.53 | +19% | 0.36-10.84 | 0.000 | 169.0 | 42 | 2 | 42 | — | 0.1430 | 0.1815 | 0.0890 |
| music-unites-herbie-hancock-kamasi-washington-in-conversation | Music Unites: Herbie Hancock & Kamasi Washington in Conversation | Wednesday Studio | SHORT_FILMS | VOTD | 7.64 | direct-mp4 | 106.05 | 1920x1080 | 25.000 | 4.30 | 54.4 | 4 | 37.7 | 65 | 97.50 | 74.68 | +31% | 26.90-182.44 | 0.969 | 2.0 | 29 | 15 | 29 | burst-heavy, non-edit-scene-change | 0.3364 | 0.6730 | 0.1859 |
| mirage | MIRAGE | KimHyunJong | SHORT_FILMS | VOTD | 7.63 | cloudflare-stream | 104.55 | 1136x480 | 24.000 | 0.94 | 11.7 | 4 | 38.3 | 4 | 6.00 | 15.49 | -61% | 0.96-16.81 | 0.000 | 134.0 | 40 | 4 | 40 | — | 0.2573 | 0.3076 | 0.0616 |
| the-heist-motion-design-reel-2025 | The Heist - Motion Design Reel 2025 | The Heist | SELF_BRANDING | VOTD | 7.63 | cloudflare-stream | 53.06 | 1280x720 | 24.000 | 2.90 | 18.3 | 4 | 75.4 | 62 | 93.00 | 94.99 | -2% | 71.30-119.22 | 0.226 | 13.0 | 7 | 37 | 7 | sparse-delta-basis | 0.3490 | 0.5074 | 0.1557 |
| doppl-2 | Doppl | Hook | EXPLANATORY_VIDEO | VOTD | 7.62 | cloudflare-stream | 58.09 | 1280x720 | 30.000 | 1.03 | 7.1 | 4 | 68.9 | 5 | 7.50 | 13.43 | -44% | 0.00-24.44 | 0.800 | 2.0 | 42 | 2 | 42 | burst-heavy, non-edit-scene-change | 0.8002 | 0.0518 | 0.0932 |
| gumball-temporary-tv-channel-identity | Gumball temporary TV Channel Identity | Antimatter | BROADCAST_CHANNEL_BRANDING | VOTD | 7.62 | direct-mp4 | 33.81 | 3840x2160 | 15.000 | 1.84 | 7.4 | 3 | 88.7 | 17 | 34.00 | 30.17 | +13% | 19.81-54.44 | 0.353 | 18.0 | 21 | 12 | 21 | — | 0.3987 | 0.7692 | 0.1490 |
| lian-li-cases-research | LIAN LI cases. Research | Ilya Henok | EXPERIMENTAL | — | 7.62 | cloudflare-stream | 35.04 | 1280x720 | 25.000 | 1.72 | 7.2 | 3 | 85.6 | 2 | 4.00 | 3.42 | +17% | 0.48-14.45 | 0.000 | 298.0 | 31 | 2 | 31 | — | 0.1413 | 0.3541 | 0.1342 |
| z-song | Z song | Melanie Gohin | MUSIC_VIDEOS | VOTD | 7.62 | cloudflare-stream | 73.75 | 1280x720 | 24.000 | 3.80 | 33.4 | 4 | 54.2 | 25 | 37.50 | 26.03 | +44% | 13.29-70.17 | 0.600 | 9.0 | 31 | 13 | 31 | burst-heavy | 0.7717 | 0.0819 | 0.1012 |
| goodtalks | Goodtalks | Nothing | ADVERTISING_CAMPAIGNS | VOTD | 7.61 | cloudflare-stream | 28.03 | 1280x720 | 25.000 | 3.16 | 10.6 | 2 | 71.3 | 4 | 12.00 | 12.84 | -7% | 3.27-30.72 | 0.000 | 96.0 | 18 | 4 | 18 | — | 0.7686 | 0.1575 | 0.0950 |
| manage-customers-from-the-palm-of-your-hand | Manage Customers from the Palm of Your Hand | Click2View | ADVERTISING_CAMPAIGNS | VOTD | 7.61 | cloudflare-stream | 70.04 | 1280x720 | 25.000 | 1.59 | 13.3 | 4 | 57.1 | 5 | 7.50 | 10.28 | -27% | 2.44-17.50 | 0.000 | 319.5 | 39 | 5 | 39 | — | 0.7528 | 0.1845 | 0.1025 |
| sevilla-design-walk-26-main-titles | Sevilla Design Walk 26 - Main Titles | Nacho Velasco | LIVE_EVENT_TITLES | — | 7.61 | cloudflare-stream | 35.88 | 1280x720 | 24.000 | 1.34 | 5.7 | 3 | 83.6 | 24 | 48.00 | 46.82 | +3% | 26.88-76.68 | 0.583 | 10.0 | 21 | 12 | 21 | burst-heavy | 0.5686 | 0.4338 | 0.1364 |
| tom-crate-2026-reel | Tom Crate 2026 Reel | Tom Crate | SELF_BRANDING | VOTD | 7.61 | cloudflare-stream | 87.53 | 1280x720 | 25.000 | 2.53 | 26.4 | 4 | 45.7 | 22 | 33.00 | 41.13 | -20% | 17.24-54.70 | 0.091 | 39.0 | 26 | 18 | 26 | — | 0.2188 | 0.4007 | 0.1761 |
| vacheron-constantin-les-cabinotiers-solaria-ultra-grand-complication | Vacheron Constantin - Les Cabinotiers Solaria Ultra Grand Complication | le truc | ADVERTISING_CAMPAIGNS | VOTD | 7.61 | cloudflare-stream | 108.14 | 1280x720 | 25.000 | 1.94 | 25.0 | 4 | 37.0 | 5 | 7.50 | 9.43 | -20% | 0.70-20.92 | 0.000 | 96.0 | 39 | 5 | 39 | — | 0.2431 | 0.2151 | 0.1317 |
| work-better-with-logitech | Work Better with Logitech | CLIM STUDIO | ADVERTISING_CAMPAIGNS | VOTD | 7.61 | direct-mp4 | 30.67 | 1920x1080 | 24.000 | 9.07 | 33.2 | 2 | 65.2 | 0 | 0.00 | 1.96 | -100% | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.7473 | 0.3991 | 0.0715 |
| i-hear-the-cicadas | I HEAR THE CICADAS | TSAIGKAHH | EXPERIMENTAL | VOTD | 7.60 | cloudflare-stream | 35.29 | 1280x720 | 25.000 | 1.94 | 8.2 | 3 | 85.0 | 39 | 78.00 | 74.82 | +4% | 55.47-106.63 | 0.769 | 3.0 | 20 | 13 | 20 | burst-heavy | 0.3855 | 0.6901 | 0.1074 |
| creative-jobs | Creative Jobs | Moonky | ADVERTISING_CAMPAIGNS | VOTD | 7.59 | cloudflare-stream | 80.87 | 1280x720 | 30.000 | 1.13 | 10.9 | 4 | 49.5 | 5 | 7.50 | 10.39 | -28% | 2.44-17.50 | 0.400 | 320.5 | 40 | 4 | 40 | — | 0.6395 | 0.1718 | 0.1047 |
| get-creative | Get Creative | Hiromu Oka | LIVE_EVENT_TITLES | VOTD | 7.59 | cloudflare-stream | 15.04 | 1280x720 | 30.000 | 3.61 | 6.5 | 1 | 66.5 | 17 | 102.00 | 163.56 | -38% | 59.42-163.31 | 0.882 | 3.0 | 4 | 7 | 4 | burst-heavy, short-sample, sparse-delta-basis | 0.2590 | 0.5329 | 0.1139 |
| new-balance-numeric-nm1010-tiago-lemos-signature-model | New Balance Numeric - NM1010 Tiago Lemos Signature Model | Already Been chewed | ADVERTISING_CAMPAIGNS | VOTD | 7.59 | cloudflare-stream | 36.44 | 1280x720 | 30.000 | 3.55 | 15.4 | 3 | 82.3 | 9 | 18.00 | 16.47 | +9% | 8.23-34.17 | 0.000 | 92.0 | 24 | 9 | 24 | — | 0.4296 | 0.4871 | 0.2193 |
| superloon | Superloon | Workroom | EXPLANATORY_VIDEO | VOTD | 7.59 | direct-mp4 | 120.04 | 1920x1080 | 24.000 | 16.22 | 232.2 | 4 | 33.3 | 0 | 0.00 | 1.00 | -100% | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.4257 | 0.0310 | 0.0550 |
| eat-well-little-child | Eat well little children | Blirp studio | ADVERTISING_CAMPAIGNS | VOTD | 7.58 | cloudflare-stream | 20.47 | 1280x720 | 30.000 | 3.27 | 8.0 | 1 | 48.9 | 38 | 228.00 | 222.80 | +2% | 161.35-312.95 | 1.000 | 2.0 | 3 | 8 | 3 | burst-heavy, non-edit-scene-change, short-sample, sparse-delta-basis | 0.4555 | 0.8302 | 0.2062 |
| from-concept-to-completion | From concept to completion | Jean Ledieu | EXPERIMENTAL | VOTD | 7.58 | cloudflare-stream | 179.67 | 1280x720 | 25.000 | 3.51 | 75.2 | 4 | 22.3 | 2 | 3.00 | 5.34 | -44% | 0.36-10.84 | 0.000 | 1239.0 | 42 | 2 | 42 | low-coverage | 0.2617 | 0.2451 | 0.0719 |
| sythetica-psychoidea | Synthetica Psychoidea | joanmoreno.tv | EXPERIMENTAL | VOTD | 7.58 | cloudflare-stream | 15.06 | 1080x1904 | 30.000 | 2.88 | 5.2 | 1 | 66.4 | 18 | 108.00 | 111.54 | -3% | 64.01-170.69 | 0.778 | 4.0 | 4 | 7 | 4 | burst-heavy, short-sample, sparse-delta-basis | 0.2524 | 0.4016 | 0.1009 |
| hamilton-timing-the-action | HAMILTON TIME THE ACTION | KUTUKO STUDIO | ADVERTISING_COMMERCIALS | VOTD | 7.57 | cloudflare-stream | 59.97 | 1280x720 | 25.000 | 2.12 | 15.2 | 4 | 66.7 | 7 | 10.50 | 12.01 | -13% | 3.38-23.12 | 0.000 | 107.5 | 37 | 7 | 37 | — | 0.3282 | 0.3837 | 0.1267 |
| httpsvimeocom1099854861 | Lightrider E-Max | EFEX GmbH | ADVERTISING_CAMPAIGNS | VOTD | 7.57 | cloudflare-stream | 50.05 | 1280x720 | 25.000 | 2.10 | 12.5 | 4 | 79.9 | 6 | 9.00 | 9.59 | -6% | 0.94-23.98 | 0.333 | 74.0 | 40 | 4 | 40 | — | 0.1511 | 0.5929 | 0.1052 |
| tennis-map-holidays | Tennis Map Holidays | Mellow Studio | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.57 | cloudflare-stream | 50.11 | 1280x720 | 25.000 | 3.56 | 21.3 | 4 | 79.8 | 8 | 12.00 | 10.78 | +11% | 1.58-29.79 | 0.500 | 29.0 | 39 | 5 | 39 | — | 0.4791 | 0.5491 | 0.1744 |
| bullpadel-hack-05-aero | BULLPADEL HACK 05  AERO | KUTUKO STUDIO | ADVERTISING_COMMERCIALS | — | 7.56 | cloudflare-stream | 32.66 | 1280x720 | 25.000 | 2.59 | 10.1 | 2 | 61.2 | 6 | 18.00 | 38.58 | -53% | 6.61-39.18 | 0.000 | 75.0 | 16 | 6 | 16 | — | 0.1486 | 0.5022 | 0.1425 |
| httpsvimeocom655042507 | BLOCKCHAIN DIGITAL ID | Mellow Studio | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.56 | cloudflare-stream | 63.83 | 1280x720 | 25.000 | 1.14 | 8.7 | 4 | 62.7 | 4 | 6.00 | 4.70 | +28% | 0.00-24.72 | 0.000 | 54.0 | 40 | 4 | 40 | — | 0.1916 | 0.8390 | 0.1107 |
| we-love-movies | Fandango, Choose Your Own Adventure | PES Motion Studio | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.56 | cloudflare-stream | 29.99 | 1280x720 | 24.000 | 3.83 | 13.7 | 2 | 66.7 | 18 | 54.00 | 58.01 | -7% | 32.00-85.34 | 0.722 | 3.0 | 12 | 10 | 12 | burst-heavy | 0.2954 | 0.7844 | 0.1539 |
| wolverine-hellcat | Wolverine: Hellcat | Already Been chewed | ADVERTISING_COMMERCIALS | VOTD | 7.56 | cloudflare-stream | 30.02 | 1280x720 | 24.000 | 3.42 | 12.2 | 2 | 66.6 | 17 | 51.00 | 49.96 | +2% | 29.71-81.66 | 0.471 | 11.5 | 12 | 10 | 12 | — | 0.3257 | 0.2855 | 0.1243 |
| anxiety-short-film | Anxiety - Short Film | Komon | EXPERIMENTAL | VOTD | 7.55 | cloudflare-stream | 65.17 | 1136x480 | 24.000 | 1.31 | 10.2 | 4 | 61.4 | 41 | 61.50 | 49.71 | +24% | 41.02-87.36 | 0.683 | 5.5 | 27 | 17 | 27 | burst-heavy | 0.1933 | 0.3154 | 0.1129 |
| edo-xpo-1 | Edo Xpo | Maxime Truchon | LIVE_EVENT_TITLES | VOTD | 7.55 | cloudflare-stream | 34.37 | 1130x480 | 24.000 | 1.63 | 6.7 | 3 | 87.3 | 15 | 30.00 | 26.19 | +15% | 14.37-53.05 | 0.267 | 31.0 | 21 | 12 | 21 | — | 0.2359 | 0.2088 | 0.0825 |
| rsquad-ton-rust-node-1 | Rsquad. TON Rust Node | KOJI | ADVERTISING_COMMERCIALS | VOTD | 7.55 | cloudflare-stream | 351.10 | 1280x720 | 24.000 | 3.55 | 148.7 | 4 | 11.4 | 37 | 55.50 | 45.80 | +21% | 25.48-93.89 | 0.486 | 21.5 | 21 | 23 | 21 | low-coverage | 0.4956 | 0.0270 | 0.2373 |
| supernova-remnant | Supernova Remnant | Artur Gadzhiev | SELF_BRANDING | VOTD | 7.55 | cloudflare-stream | 42.86 | 1280x720 | 24.000 | 1.55 | 7.9 | 3 | 70.0 | 0 | 0.00 | 2.80 | -100% | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.0641 | 0.6358 | 0.0681 |
| mantis-launch-reel | Mantis Launch Reel | Mantis | SELF_BRANDING | — | 7.54 | cloudflare-stream | 31.40 | 1280x720 | 25.000 | 1.34 | 5.0 | 2 | 63.7 | 9 | 27.00 | 22.93 | +18% | 12.35-51.25 | 0.778 | 6.0 | 18 | 4 | 18 | burst-heavy | 0.2500 | 0.2794 | 0.1055 |
| motion-array-epic-holiday-sale | Motion Array Epic Holiday Sale | PES Motion Studio | ADVERTISING_CAMPAIGNS | VOTD | 7.54 | cloudflare-stream | 30.27 | 1280x720 | 24.000 | 3.13 | 11.3 | 2 | 66.1 | 31 | 93.00 | 91.17 | +2% | 63.19-132.01 | 0.419 | 14.0 | 4 | 18 | 4 | sparse-delta-basis | 0.3830 | 0.4773 | 0.1585 |
| broomsticks-on-broadway-1 | Broomsticks on Broadway | Gordon Howie | SHORT_FILMS | — | 7.53 | cloudflare-stream | 312.73 | 1152x480 | 24.000 | 0.93 | 34.8 | 4 | 12.8 | 2 | 3.00 | 14.01 | -79% | 0.00-14.08 | 0.000 | 200.0 | 42 | 2 | 42 | low-coverage | 0.0897 | 0.4874 | 0.0532 |
| christies-luxury-week-3 | Christie's – Luxury Week | CLIM STUDIO | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.53 | cloudflare-stream | 15.04 | 1280x720 | 25.000 | 3.76 | 6.7 | 1 | 66.5 | 3 | 18.00 | 11.97 | +50% | 3.71-52.60 | 0.000 | 75.0 | 8 | 3 | 8 | short-sample | 0.2745 | 0.3890 | 0.0464 |
| martinelliluce-lightforlife | MartinelliLuce - Lightforlife | Diorama | ADVERTISING_COMMERCIALS | VOTD | 7.53 | cloudflare-stream | 138.50 | 1126x480 | 30.000 | 0.84 | 13.8 | 4 | 28.9 | 15 | 22.50 | 25.13 | -10% | 9.05-42.34 | 0.000 | 52.0 | 29 | 15 | 29 | — | 0.2542 | 0.3905 | 0.0821 |
| vice-city | Vice City | Ronin161 | MUSIC_VIDEOS | VOTD | 7.53 | cloudflare-stream | 203.07 | 1280x720 | 25.000 | 3.54 | 85.8 | 4 | 19.7 | 4 | 6.00 | 6.80 | -12% | 1.63-15.36 | 0.000 | 1229.0 | 40 | 4 | 40 | low-coverage | 0.2730 | 0.1910 | 0.0962 |
| the-mini-vision-urbanaut-wanderlust | The MINI Vision Urbanaut / Wanderlust | Aixsponza | ADVERTISING_CAMPAIGNS | VOTD | 7.52 | cloudflare-stream | 59.35 | 1280x720 | 25.000 | 3.84 | 27.2 | 4 | 67.4 | 4 | 6.00 | 4.04 | +48% | 0.00-24.72 | 0.000 | 66.0 | 40 | 4 | 40 | — | 0.4420 | 0.3205 | 0.1913 |
| gemini-ios-app-launch | Gemini iOS App Launch | Hook | EXPLANATORY_VIDEO | VOTD | 7.51 | cloudflare-stream | 37.65 | 1080x1920 | 30.000 | 2.18 | 9.8 | 3 | 79.7 | 5 | 10.00 | 9.56 | +5% | 3.25-23.34 | 0.000 | 129.5 | 28 | 5 | 28 | — | 0.1615 | 0.2652 | 0.1404 |
| persol-universe | Persol: Universe | Already Been chewed | ADVERTISING_CAMPAIGNS | VOTD | 7.51 | cloudflare-stream | 22.31 | 1280x720 | 24.000 | 3.01 | 8.0 | 2 | 89.6 | 6 | 18.00 | 16.13 | +12% | 6.61-39.18 | 0.333 | 39.0 | 17 | 5 | 17 | — | 0.4294 | 0.2078 | 0.1706 |
| till-this-day-trailer | Till This Day - Trailer | Nako Baev | FILM_GRAPHICS | VOTD | 7.51 | cloudflare-stream | 59.97 | 1136x240 | 25.000 | 0.69 | 5.0 | 4 | 66.7 | 13 | 19.50 | 21.01 | -7% | 9.07-35.33 | 0.000 | 40.0 | 32 | 12 | 32 | — | 0.1510 | 0.4117 | 0.0795 |
| future-cube-all-after-effects | IBM Supply Chain Onboarding | Blueteam Studio | ADVERTISING_CAMPAIGNS | HM | 7.50 | cloudflare-stream | 133.08 | 1280x720 | 24.000 | 0.59 | 9.4 | 4 | 30.1 | 1 | 1.50 | 0.45 | +233% | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.3083 | 0.3755 | 0.0983 |
| httpsramonandpedrowetransfercomdownloadsf91e7b36fffad702ab46f80983f7cd84202109141127560ca61e | Roland Garros Opening Sequence 2021 | Ramon+Pedro | LIVE_EVENT_TITLES | HM | 7.50 | cloudflare-stream | 32.38 | 1280x720 | 25.000 | 3.13 | 12.1 | 2 | 61.8 | 9 | 27.00 | 18.53 | +46% | 12.35-51.25 | 0.222 | 13.0 | 16 | 6 | 16 | — | 0.5319 | 0.6220 | 0.2680 |
| van-mooff-s3-aluminum | Van Moof S3 Aluminum | Geert van Hooff | ADVERTISING_CAMPAIGNS | VOTD | 7.50 | cloudflare-stream | 14.06 | 1280x720 | 30.000 | 1.44 | 2.4 | 1 | 71.1 | 6 | 36.00 | 25.61 | +41% | 13.21-78.36 | 0.000 | 34.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.1311 | 0.2059 | 0.0894 |
| aescripts-aeplugins-cyber-monday | aescripts + aeplugins - Cyber Monday! | PES Motion Studio | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.49 | cloudflare-stream | 20.04 | 1280x720 | 29.970 | 3.69 | 8.8 | 1 | 49.9 | 8 | 48.00 | 65.86 | -27% | 20.72-94.58 | 0.375 | 12.0 | 6 | 5 | 6 | short-sample, sparse-delta-basis | 0.5096 | 0.3368 | 0.1155 |
| mabuhay-showreel-2025 | Mabuhay - Showreel 2025 | Chris Sante | SELF_BRANDING | VOTD | 7.49 | cloudflare-stream | 90.22 | 1280x720 | 25.000 | 1.08 | 11.6 | 4 | 44.3 | 22 | 33.00 | 41.23 | -20% | 16.67-55.49 | 0.000 | 21.0 | 26 | 18 | 26 | — | 0.3843 | 0.4626 | 0.0700 |
| showreel-1 | Showreel CGT | CGT — Creative Graphic Tehnologies | FILM_GRAPHICS | — | 7.49 | cloudflare-stream | 96.02 | 1280x720 | 25.000 | 1.80 | 20.6 | 4 | 41.7 | 14 | 21.00 | 17.50 | +20% | 11.48-35.23 | 0.000 | 54.0 | 30 | 14 | 30 | — | 0.2150 | 0.3592 | 0.0930 |
| reframing-forestry-standards-for-people-planet-purpose | Reframing Forestry Standards for People, Planet, Purpose | Future by Design | EXPLANATORY_VIDEO | — | 7.48 | cloudflare-stream | 44.74 | 1280x720 | 29.970 | 0.87 | 4.6 | 4 | 89.4 | 39 | 58.50 | 54.99 | +6% | 37.13-85.64 | 1.000 | 2.0 | 34 | 10 | 34 | burst-heavy, non-edit-scene-change | 0.6397 | 0.3649 | 0.1188 |
| 100-year-meli | A Century of Sweetness - 100 Years of Meli | VAZE.TV | ADVERTISING_COMMERCIALS | VOTD | 7.47 | cloudflare-stream | 32.45 | 1280x720 | 25.000 | 2.26 | 8.7 | 2 | 61.6 | 5 | 15.00 | 14.79 | +1% | 4.87-35.00 | 0.000 | 62.5 | 17 | 5 | 17 | — | 0.5933 | 0.4004 | 0.1464 |
| dark-room | Dark Room | Sugar Blood / Pedro Allevato | SHORT_FILMS | VOTD | 7.47 | cloudflare-stream | 220.03 | 1152x480 | 24.000 | 1.86 | 48.8 | 4 | 18.2 | 5 | 7.50 | 35.72 | -79% | 0.00-29.87 | 0.800 | 2.5 | 42 | 2 | 42 | burst-heavy, low-coverage, non-edit-scene-change | 0.1642 | 0.6692 | 0.0712 |
| haiwei-kids-watch | Huawei Kid's Watch | HELEN HSU | ADVERTISING_COMMERCIALS | VOTD | 7.47 | cloudflare-stream | 28.46 | 1280x720 | 25.000 | 3.48 | 11.8 | 2 | 70.3 | 8 | 24.00 | 21.08 | +14% | 10.36-47.29 | 0.000 | 42.0 | 14 | 8 | 14 | — | 0.6184 | 0.1166 | 0.1791 |
| iris | IRIS | Raphaël Bluzet | MUSIC_VIDEOS | HM | 7.47 | cloudflare-stream | 187.71 | 1280x720 | 25.000 | 3.82 | 85.4 | 4 | 21.3 | 4 | 6.00 | 6.39 | -6% | 1.63-15.36 | 0.000 | 1283.0 | 40 | 4 | 40 | low-coverage | 0.5441 | 0.3363 | 0.1070 |
| netclean | Netclean | Haymaker | ADVERTISING_CAMPAIGNS | VOTD | 7.47 | cloudflare-stream | 70.27 | 1280x720 | 25.000 | 3.58 | 30.0 | 4 | 56.9 | 5 | 7.50 | 6.83 | +10% | 0.70-20.92 | 0.000 | 79.0 | 39 | 5 | 39 | — | 0.6016 | 0.1266 | 0.1362 |
| unleash-your-potential | Unleash Your Potential | Vendredi Society | ADVERTISING_CAMPAIGNS | VOTD | 7.47 | cloudflare-stream | 60.03 | 1280x720 | 30.000 | 1.06 | 7.6 | 4 | 66.6 | 8 | 12.00 | 11.99 | +0% | 5.18-23.64 | 0.250 | 194.0 | 37 | 7 | 37 | — | 0.3968 | 0.4641 | 0.1251 |
| friendly-devices | Friendly Devices | Mihai Serban / izkser | EXPERIMENTAL | VOTD | 7.46 | cloudflare-stream | 4.48 | 1080x1080 | 24.000 | 1.26 | 0.7 | 1 | 89.3 | 0 | 0.00 | 0.00 | — | 0.00-55.34 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.6586 | 0.0237 | 0.1060 |
| nike-air-max-270-animation | Nike Air Max 270 - Animation | Mondlicht Studios | SELF_BRANDING | VOTD | 7.46 | cloudflare-stream | 44.05 | 1152x480 | 25.000 | 1.96 | 10.3 | 3 | 68.1 | 9 | 18.00 | 17.71 | +2% | 3.08-42.70 | 0.222 | 37.0 | 26 | 7 | 26 | — | 0.1970 | 0.4144 | 0.1143 |
| print-magazine-awards | Print Magazine Awards | Julian Lahdesmaki | ADVERTISING_CAMPAIGNS | VOTD | 7.46 | cloudflare-stream | 68.10 | 1280x720 | 24.000 | 1.91 | 15.5 | 4 | 58.7 | 12 | 18.00 | 15.86 | +13% | 3.79-39.95 | 0.000 | 59.0 | 34 | 10 | 34 | — | 0.2793 | 0.4802 | 0.0858 |
| promax-bda-rome-2018-opener | Promax bda rome 2018  -  Opener | Alkanoids | LIVE_EVENT_TITLES | VOTD | 7.46 | direct-mp4 | 146.41 | 1920x1080 | 25.000 | 5.16 | 90.1 | 4 | 27.3 | 11 | 16.50 | 24.18 | -32% | 0.00-59.69 | 0.182 | 19.5 | 36 | 8 | 36 | — | 0.5184 | 0.2639 | 0.0362 |
| reebok-legion-of-fury-1 | Reebok - Legion Of Fury | Haymaker | ADVERTISING_CAMPAIGNS | VOTD | 7.46 | cloudflare-stream | 60.03 | 1280x720 | 24.000 | 3.59 | 25.7 | 4 | 66.6 | 15 | 22.50 | 23.99 | -6% | 12.59-37.11 | 0.000 | 73.0 | 29 | 15 | 29 | — | 0.3035 | 0.4903 | 0.2027 |
| corey-taylor-culture-head-official-music-video | COREY TAYLOR - CULTURE HEAD (OFFICIAL MUSIC VIDEO) | Mellow Studio | MUSIC_VIDEOS | VOTD | 7.45 | direct-mp4 | 239.13 | 1920x1080 | 30.000 | 6.64 | 189.4 | 4 | 16.7 | 1 | 1.50 | 17.31 | -91% | 0.04-8.36 | — | — | 43 | 1 | 43 | low-coverage | 0.0614 | 0.0154 | 0.0575 |
| trip | "Trip" | Plenty | ADVERTISING_COMMERCIALS | VOTD | 7.45 | cloudflare-stream | 14.99 | 1280x720 | 30.000 | 3.60 | 6.4 | 1 | 66.7 | 0 | 0.00 | 4.00 | -100% | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.5835 | 0.4061 | 0.2528 |
| dhl-date | DHL - Date | NEW MOTIVE | ADVERTISING_CAMPAIGNS | VOTD | 7.44 | cloudflare-stream | 32.02 | 1280x720 | 24.000 | 3.30 | 12.6 | 2 | 62.5 | 6 | 18.00 | 13.12 | +37% | 6.61-39.18 | 0.000 | 79.0 | 16 | 6 | 16 | — | 0.6374 | 0.4737 | 0.0847 |
| the-simplest-happiness-3 | The Simplest Happiness | Yen C Chen | BROADCAST_CHANNEL_BRANDING | VOTD | 7.44 | cloudflare-stream | 18.50 | 1280x720 | 30.000 | 3.69 | 8.1 | 1 | 54.1 | 5 | 30.00 | 25.95 | +16% | 9.74-70.01 | 0.400 | 48.0 | 8 | 3 | 8 | short-sample | 0.5136 | 0.4958 | 0.2101 |
| depicted | Depicted | Aamir Hussain Khan | SELF_BRANDING | VOTD | 7.43 | cloudflare-stream | 22.04 | 1280x720 | 25.000 | 1.57 | 4.1 | 1 | 45.4 | 6 | 36.00 | 32.67 | +10% | 13.21-78.36 | 0.000 | 30.0 | 5 | 6 | 5 | short-sample, sparse-delta-basis | 0.3714 | 0.1619 | 0.0614 |
| dopamine-factory | Dopamine Factory | Grigorii Kniagnitskii | SELF_BRANDING | VOTD | 7.43 | cloudflare-stream | 62.98 | 1280x720 | 24.000 | 0.52 | 3.9 | 4 | 63.5 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.3013 | 0.3109 | 0.0074 |
| entropy | ENTROPY | Sylvain gaussens | EXPERIMENTAL | HM | 7.43 | cloudflare-stream | 55.04 | 960x480 | 24.000 | 1.64 | 10.8 | 4 | 72.7 | 1 | 1.50 | 2.18 | -31% | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.0275 | 0.2636 | 0.0357 |
| hard-to-starboard | Hard to Starboard | RENDER Entertainment | SHORT_FILMS | VOTD | 7.43 | cloudflare-stream | 56.71 | 1122x480 | 30.000 | 0.83 | 5.6 | 4 | 70.5 | 11 | 16.50 | 11.64 | +42% | 0.00-59.69 | 0.818 | 5.0 | 39 | 5 | 39 | burst-heavy | 0.0632 | 0.6613 | 0.0337 |
| seo-birdlife-no-harias-esto-you-wouldnt-do-this | SEO Birdlife- No harias esto (you wouldn't do this) | Ivan Miguel | ADVERTISING_COMMERCIALS | VOTD | 7.43 | cloudflare-stream | 45.03 | 1280x720 | 25.000 | 3.87 | 20.8 | 4 | 88.8 | 3 | 4.50 | 5.33 | -16% | 0.93-13.15 | 0.000 | 230.0 | 41 | 3 | 41 | — | 0.6779 | 0.6811 | 0.0202 |
| emerge-what-it-feels-like | Emerge — What It Feels Like | Johana Kroft | EXPLANATORY_VIDEO | VOTD | 7.41 | cloudflare-stream | 66.92 | 1280x720 | 30.000 | 3.41 | 27.2 | 4 | 59.8 | 5 | 7.50 | 8.07 | -7% | 2.44-17.50 | 0.000 | 434.5 | 39 | 5 | 39 | — | 0.5471 | 0.3141 | 0.0520 |
| reel-2026-maido-hollo-1 | Reel 2026 \| Maido Hollo | Maido Hollo | SELF_BRANDING | — | 7.41 | cloudflare-stream | 68.61 | 1280x720 | 25.000 | 3.74 | 30.6 | 4 | 58.3 | 46 | 69.00 | 62.09 | +11% | 44.83-99.13 | 0.217 | 15.0 | 12 | 32 | 12 | — | 0.4577 | 0.2614 | 0.1538 |
| safeguard-kids | Safeguard Kids | Feed Me Light | ADVERTISING_COMMERCIALS | VOTD | 7.41 | cloudflare-stream | 60.05 | 1280x720 | 25.000 | 3.74 | 26.7 | 4 | 66.6 | 12 | 18.00 | 17.98 | +0% | 7.15-34.77 | 0.167 | 60.0 | 33 | 11 | 33 | — | 0.6208 | 0.3916 | 0.1616 |
| studio-i-towards-a-new-museum | Studio I - Towards a New Museum | Studio WIM | EXPLANATORY_VIDEO | VOTD | 7.41 | cloudflare-stream | 103.96 | 1280x720 | 25.000 | 2.54 | 31.5 | 4 | 38.5 | 7 | 10.50 | 25.40 | -59% | 0.72-27.85 | 0.429 | 19.5 | 40 | 4 | 40 | — | 0.7272 | 0.1981 | 0.0694 |
| 10-to-the-64th-power | 10 to the 64th Power | Sobe Okoye | SHORT_FILMS | HM | 7.40 | cloudflare-stream | 211.58 | 1280x720 | 24.000 | 1.64 | 41.5 | 4 | 18.9 | 2 | 3.00 | 5.39 | -44% | 0.00-14.08 | 0.000 | 72.0 | 42 | 2 | 42 | low-coverage | 0.1367 | 0.1332 | 0.0601 |
| funda | "Funda" | Plenty | ADVERTISING_COMMERCIALS | VOTD | 7.40 | cloudflare-stream | 15.04 | 1280x720 | 30.000 | 3.74 | 6.7 | 1 | 66.5 | 7 | 42.00 | 31.91 | +32% | 16.89-86.54 | 0.000 | 23.5 | 5 | 6 | 5 | short-sample, sparse-delta-basis | 0.6200 | 0.4048 | 0.2569 |
| il-supervissuto | Il Supervissuto - Vasco Rossi | CHUNK STUDIO | BROADCAST_SERIES_TITLES | HM | 7.40 | cloudflare-stream | 48.96 | 1280x720 | 25.000 | 2.14 | 12.5 | 4 | 81.7 | 15 | 22.50 | 19.61 | +15% | 12.59-37.11 | 0.467 | 47.0 | 34 | 10 | 34 | — | 0.2402 | 0.3181 | 0.0727 |
| moondog-birds-lament-shani-diluka | Moondog: Bird's Lament - Shani Diluka | The Great Paper Massacre | MUSIC_VIDEOS | VOTD | 7.40 | cloudflare-stream | 129.02 | 1280x720 | 25.000 | 2.72 | 41.9 | 4 | 31.0 | 14 | 21.00 | 16.28 | +29% | 8.89-39.11 | 0.000 | 49.0 | 31 | 13 | 31 | — | 0.3352 | 0.2093 | 0.0566 |
| where-does-an-idea-come-from | Where does an idea come from? | Studio Bunkum | TITLE_SEQUENCES | — | 7.40 | cloudflare-stream | 64.38 | 1280x720 | 24.000 | 1.68 | 12.9 | 4 | 62.1 | 31 | 46.50 | 49.39 | -6% | 12.81-90.58 | 0.839 | 3.5 | 32 | 12 | 32 | burst-heavy | 0.3276 | 0.2629 | 0.1100 |
| nike-mercurial-phantom-series-victory-pack | Nike Mercurial & Phantom Series Victory Pack | Aixsponza | ADVERTISING_CAMPAIGNS | VOTD | 7.39 | cloudflare-stream | 76.18 | 1280x720 | 25.000 | 3.57 | 32.4 | 4 | 52.5 | 22 | 33.00 | 36.23 | -9% | 20.68-49.96 | 0.000 | 44.0 | 22 | 22 | 22 | — | 0.5684 | 0.1858 | 0.1254 |
| on-the-other-side | On the other side | N3 | TITLE_SEQUENCES | VOTD | 7.39 | cloudflare-stream | 20.05 | 1280x720 | 25.000 | 3.20 | 7.6 | 1 | 49.9 | 5 | 30.00 | 26.93 | +11% | 9.74-70.01 | 0.000 | 41.0 | 6 | 5 | 6 | short-sample, sparse-delta-basis | 0.6555 | 0.1323 | 0.2365 |
| pupa-the-larval-form-1 | .P.U.P.A. \| THE LARVAL FORM | Obsedant | EXPERIMENTAL | VOTD | 7.39 | cloudflare-stream | 45.06 | 1280x720 | 30.000 | 3.27 | 17.6 | 4 | 88.8 | 10 | 15.00 | 13.32 | +13% | 7.19-27.59 | 0.000 | 101.0 | 34 | 10 | 34 | — | 0.2294 | 0.5152 | 0.1124 |
| tela-axis | TELA AXIS | Tomaszewicz Studio | SELF_BRANDING | VOTD | 7.39 | cloudflare-stream | 21.27 | 1280x720 | 25.000 | 4.03 | 10.2 | 1 | 47.0 | 4 | 24.00 | 19.75 | +22% | 6.54-61.45 | 0.000 | 51.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.4486 | 0.2760 | 0.1340 |
| the-future-of-dental-care | The Future of Dental Care | Vendredi Society | ADVERTISING_COMMERCIALS | HM | 7.39 | cloudflare-stream | 88.04 | 1280x720 | 25.000 | 0.92 | 9.7 | 4 | 45.4 | 18 | 27.00 | 23.85 | +13% | 16.00-42.67 | 0.000 | 42.0 | 26 | 18 | 26 | — | 0.6852 | 0.0800 | 0.1018 |
| citadelle-zero | Citadelle Zero | TONEVO Paris | ADVERTISING_COMMERCIALS | VOTD | 7.38 | cloudflare-stream | 23.98 | 1280x720 | 25.000 | 1.89 | 5.4 | 2 | 83.4 | 9 | 27.00 | 22.52 | +20% | 12.35-51.25 | 0.000 | 50.5 | 13 | 9 | 13 | — | 0.5647 | 0.2170 | 0.0940 |
| malibu-boats-m220 | Malibu Boats: M220 | Already Been chewed | ADVERTISING_CAMPAIGNS | VOTD | 7.38 | cloudflare-stream | 45.57 | 1280x720 | 24.000 | 3.74 | 20.3 | 4 | 87.8 | 10 | 15.00 | 13.17 | +14% | 7.19-27.59 | 0.200 | 56.0 | 35 | 9 | 35 | — | 0.3448 | 0.3481 | 0.1695 |
| we-love | We love | Neil Verhavert | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.38 | cloudflare-stream | 25.02 | 1280x720 | 24.000 | 3.50 | 10.4 | 2 | 79.9 | 67 | 201.00 | 196.61 | +2% | 155.77-255.26 | 0.985 | 2.0 | 11 | 11 | 11 | burst-heavy, non-edit-scene-change | 0.5895 | 0.4615 | 0.0823 |
| bio-bar-mad-campaign | Bio Bar Mad Campaign | RENDER Entertainment | ADVERTISING_CAMPAIGNS | VOTD | 7.37 | cloudflare-stream | 27.58 | 1136x240 | 30.000 | 0.68 | 2.2 | 2 | 72.5 | 8 | 24.00 | 36.98 | -35% | 10.36-47.29 | 0.000 | 45.0 | 14 | 8 | 14 | — | 0.3521 | 0.1486 | 0.0389 |
| david-guerrero-for-emeerree-part-ii | David Guerrero for Emeerree, Part II | David Guerrero | ADVERTISING_CAMPAIGNS | VOTD | 7.37 | cloudflare-stream | 34.73 | 1280x720 | 24.000 | 2.07 | 8.6 | 3 | 86.4 | 4 | 8.00 | 6.91 | +16% | 2.18-20.48 | 0.000 | 70.0 | 29 | 4 | 29 | — | 0.5023 | 0.0601 | 0.0809 |
| dieline-awards-2025 | Dieline Awards 2025 | Julian Lahdesmaki | SOUND_DESIGN | VOTD, VOTY | 7.37 | cloudflare-stream | 77.67 | 1280x720 | 30.000 | 2.13 | 19.7 | 4 | 51.5 | 8 | 12.00 | 12.36 | -3% | 5.18-23.64 | 0.000 | 102.0 | 36 | 8 | 36 | — | 0.4214 | 0.5076 | 0.1066 |
| nike-air-max-97-evolution-2 | Nike Air Max 97 - Evolution | Mondlicht Studios | SELF_BRANDING | VOTD | 7.37 | cloudflare-stream | 25.90 | 1280x720 | 30.000 | 2.80 | 8.7 | 2 | 77.2 | 8 | 24.00 | 20.85 | +15% | 10.36-47.29 | 0.000 | 54.0 | 14 | 8 | 14 | — | 0.1800 | 0.5993 | 0.1214 |
| baltimore-ravens-uniform-reveal | Baltimore Ravens Uniform Reveal | Already Been chewed | ADVERTISING_CAMPAIGNS | VOTD | 7.36 | cloudflare-stream | 127.64 | 1280x720 | 59.940 | 2.31 | 35.2 | 4 | 31.3 | 27 | 40.50 | 54.06 | -25% | 13.97-75.90 | 0.148 | 52.5 | 23 | 21 | 23 | — | 0.2701 | 0.2967 | 0.1339 |
| bilardo-main-title | Bilardo - Main Title | Molten | TITLE_SEQUENCES | VOTD | 7.36 | cloudflare-stream | 51.75 | 1280x720 | 23.976 | 2.68 | 16.5 | 4 | 77.3 | 15 | 22.50 | 22.03 | +2% | 12.59-37.11 | 0.000 | 49.0 | 29 | 15 | 29 | — | 0.3331 | 0.4247 | 0.1422 |
| dating-games | Dating Games | ane.motion | EXPERIMENTAL | — | 7.36 | cloudflare-stream | 45.18 | 1280x720 | 24.000 | 1.37 | 7.4 | 4 | 88.5 | 10 | 15.00 | 13.28 | +13% | 6.45-28.79 | 0.000 | 91.0 | 34 | 10 | 34 | — | 0.7534 | 0.2728 | 0.1158 |
| every-body-move-together | Every Body Move Together! | ROVE | EXPLANATORY_VIDEO | — | 7.35 | cloudflare-stream | 72.17 | 1280x720 | 23.976 | 1.53 | 13.1 | 4 | 55.4 | 23 | 34.50 | 29.93 | +15% | 13.71-62.93 | 0.000 | 21.0 | 25 | 19 | 25 | — | 0.6913 | 0.3066 | 0.1184 |
| prada-i-americans-cup-1 | Prada I American's Cup | Studio Sentempo | ADVERTISING_CAMPAIGNS | HM | 7.35 | cloudflare-stream | 22.63 | 1280x720 | 25.000 | 1.53 | 4.1 | 2 | 88.4 | 7 | 21.00 | 18.56 | +13% | 8.44-43.27 | 0.000 | 62.0 | 15 | 7 | 15 | — | 0.3026 | 0.1201 | 0.0536 |
| vertebrae-atlas | Vertebrae - Atlas | Martino Prendini | SHORT_FILMS | VOTD | 7.35 | cloudflare-stream | 61.08 | 1280x720 | 24.000 | 3.34 | 24.3 | 4 | 65.5 | 2 | 3.00 | 2.95 | +2% | 0.00-14.08 | 1.000 | 3.0 | 43 | 1 | 43 | burst-heavy | 0.3071 | 0.5086 | 0.1317 |
| hope-rising-intro | HOPE RISING INTRO | Already Been chewed | LIVE_EVENT_TITLES | VOTD | 7.34 | cloudflare-stream | 18.01 | 1280x720 | 30.000 | 3.72 | 8.0 | 1 | 55.5 | 3 | 18.00 | 16.66 | +8% | 3.71-52.60 | 0.000 | 55.0 | 8 | 3 | 8 | short-sample | 0.2450 | 0.4444 | 0.1337 |
| nothing-phone-4a-unofficial-product-commercial | Nothing Phone (4a) — Unofficial Product Commercial | Snoll Visuals | ADVERTISING_COMMERCIALS | VOTD | 7.34 | cloudflare-stream | 24.55 | 1280x720 | 24.000 | 1.56 | 4.6 | 2 | 81.5 | 12 | 36.00 | 34.21 | +5% | 18.60-62.88 | 0.333 | 44.0 | 13 | 9 | 13 | — | 0.3677 | 0.0689 | 0.1276 |
| breaking-rules | Breaking Rules | Brandon Singer | SHORT_FILMS | VOTD | 7.33 | cloudflare-stream | 35.11 | 1080x1080 | 12.000 | 2.83 | 11.9 | 3 | 85.4 | 0 | 0.00 | 1.71 | -100% | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.3905 | 0.3589 | 0.1394 |
| on-the-east-borders | On the east borders | N3 | BROADCAST_PROGRAM_TITLES | HM | 7.33 | cloudflare-stream | 28.80 | 1280x720 | 25.000 | 3.69 | 12.7 | 2 | 69.4 | 7 | 21.00 | 20.83 | +1% | 8.44-43.27 | 0.286 | 41.5 | 16 | 6 | 16 | — | 0.7071 | 0.0881 | 0.1570 |
| httpsvimeocom990284238sharecopy | Spotify Countdown Pages | ROVE | ADVERTISING_CAMPAIGNS | — | 7.31 | cloudflare-stream | 59.11 | 1280x720 | 29.970 | 2.45 | 17.2 | 4 | 67.7 | 42 | 63.00 | 99.47 | -37% | 45.40-85.16 | 1.000 | 3.0 | 33 | 11 | 33 | burst-heavy | 0.2630 | 0.0586 | 0.0844 |
| nantes-sanime-bicycle-trip | NANTES S'ANIME \| Bicycle trip | Jules Couderc | EXPERIMENTAL | — | 7.31 | cloudflare-stream | 41.26 | 1280x720 | 25.000 | 2.50 | 12.3 | 3 | 72.7 | 19 | 38.00 | 33.45 | +14% | 22.88-59.34 | 0.316 | 32.0 | 18 | 15 | 18 | — | 0.3924 | 0.3360 | 0.1627 |
| naturgy-ecoeasy-20-spot | Naturgy  Ecoeasy - 20" Spot | Framelight Studio | ADVERTISING_COMMERCIALS | VOTD | 7.31 | cloudflare-stream | 20.02 | 1280x720 | 24.000 | 3.91 | 9.3 | 1 | 49.9 | 3 | 18.00 | 8.99 | +100% | 3.71-52.60 | 1.000 | 2.0 | 9 | 2 | 9 | burst-heavy, non-edit-scene-change, short-sample | 0.9088 | 0.0830 | 0.0548 |
| mixed-mirrors-1 | Mixed Mirrors | Tigrelab | INSTALLATION_PROJECTION_EXPERIENCE | VOTD, VOTY | 7.30 | cloudflare-stream | 117.74 | 1280x720 | 29.970 | 3.83 | 53.7 | 4 | 34.0 | 9 | 13.50 | 11.21 | +20% | 5.16-27.31 | 0.000 | 77.5 | 35 | 9 | 35 | — | 0.1135 | 0.1175 | 0.0705 |
| mojo | MOJO | Vendredi Society | ADVERTISING_CAMPAIGNS | VOTD | 7.30 | cloudflare-stream | 49.41 | 1280x720 | 30.000 | 1.02 | 6.0 | 4 | 81.0 | 19 | 28.50 | 24.29 | +17% | 15.49-46.86 | 0.105 | 58.0 | 28 | 16 | 28 | — | 0.7826 | 0.1444 | 0.1513 |
| pros-in-your-pocket | Pros In Your Pocket | SKILLR | ADVERTISING_COMMERCIALS | VOTD | 7.30 | cloudflare-stream | 29.85 | 1280x720 | 23.976 | 0.90 | 3.2 | 2 | 67.0 | 3 | 9.00 | 10.05 | -10% | 1.86-26.30 | 0.000 | 229.5 | 19 | 3 | 19 | — | 0.6488 | 0.3232 | 0.1082 |
| magic | MAGIC | P2 Content Creators | SELF_BRANDING | VOTD | 7.29 | cloudflare-stream | 35.03 | 1280x720 | 25.000 | 1.14 | 4.8 | 3 | 85.6 | 0 | 0.00 | 0.00 | — | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.1316 | 0.5298 | 0.0406 |
| miami-music-festival-2020 | MIAMI  Music Festival 2020 | Alkanoids | LIVE_EVENT_TITLES | VOTD | 7.29 | cloudflare-stream | 18.04 | 1280x720 | 25.000 | 3.45 | 7.4 | 1 | 55.4 | 5 | 30.00 | 23.28 | +29% | 9.74-70.01 | 0.000 | 47.0 | 6 | 5 | 6 | short-sample, sparse-delta-basis | 0.3302 | 0.6881 | 0.1101 |
| freerunning-in-the-metaverse-episode-1 | Freerunning in the metaverse! (Episode 1) | Voogie | MUSIC_VIDEOS | VOTD | 7.28 | cloudflare-stream | 40.49 | 608x1080 | 30.000 | 3.12 | 15.1 | 3 | 74.1 | 0 | 0.00 | 1.48 | -100% | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.1605 | 0.5707 | 0.1514 |
| we-hunt-together-title-sequence-uktv-original-bbc-studios | We Hunt Together - Title Sequence (UKTV Original / BBC Studios) | UKTV Creative | BROADCAST_PROGRAM_TITLES | VOTD | 7.28 | cloudflare-stream | 45.08 | 1280x720 | 25.000 | 3.22 | 17.3 | 4 | 88.7 | 7 | 10.50 | 9.32 | +13% | 3.38-23.12 | 0.286 | 83.5 | 38 | 6 | 38 | — | 0.0752 | 0.6325 | 0.0850 |
| iso-extremely-flamable | ISO - Extremely Flamable | fredanyway | EXPERIMENTAL | VOTD | 7.27 | cloudflare-stream | 60.03 | 1080x1920 | 25.000 | 2.47 | 17.7 | 4 | 66.6 | 2 | 3.00 | 2.00 | +50% | 0.36-10.84 | 0.000 | 126.0 | 42 | 2 | 42 | — | 0.5535 | 0.1058 | 0.0391 |
| legend-trade-video | Legend Trade Video | Klipz Studio | ADVERTISING_SOCIAL_MEDIA_ADS | — | 7.27 | cloudflare-stream | 35.61 | 1280x720 | 18.000 | 2.99 | 12.7 | 3 | 84.3 | 59 | 118.00 | 101.11 | +17% | 57.62-191.32 | 0.932 | 2.0 | 16 | 17 | 16 | burst-heavy, non-edit-scene-change | 0.3151 | 0.1394 | 0.1340 |
| puma-push-pack | PUMA - Rush Pack | Inertia Studios | ADVERTISING_CAMPAIGNS | VOTD | 7.27 | cloudflare-stream | 30.04 | 1280x720 | 25.000 | 3.73 | 13.4 | 2 | 66.6 | 24 | 72.00 | 67.92 | +6% | 46.13-107.13 | 0.125 | 19.0 | 5 | 17 | 5 | sparse-delta-basis | 0.5263 | 0.3130 | 0.1094 |
| dodge-charger-srt-hellcat-the-beast-is-having-fun | Dodge Charger SRT Hellcat - The Beast Is Having Fun | Punctum Images | ADVERTISING_SOCIAL_MEDIA_ADS | HM | 7.26 | cloudflare-stream | 31.70 | 1280x720 | 25.000 | 2.33 | 8.8 | 2 | 63.1 | 10 | 30.00 | 28.39 | +6% | 14.39-55.17 | 0.000 | 43.0 | 14 | 8 | 14 | — | 0.5375 | 0.1193 | 0.1089 |
| genesis-vision-2 | Genesis Vision 2 | N3 | ADVERTISING_COMMERCIALS | VOTD | 7.26 | cloudflare-stream | 107.90 | 1280x720 | 25.000 | 3.52 | 45.3 | 4 | 37.1 | 2 | 3.00 | 5.00 | -40% | 0.00-14.08 | 0.000 | 126.0 | 42 | 2 | 42 | — | 0.2705 | 0.4307 | 0.1441 |
| golden-bamboo | Golden Bamboo | Benoit Huguet | SELF_BRANDING | VOTD | 7.26 | cloudflare-stream | 15.70 | 1080x1080 | 30.000 | 1.48 | 2.8 | 1 | 63.7 | 3 | 18.00 | 11.46 | +57% | 3.71-52.60 | 0.000 | 96.0 | 8 | 3 | 8 | short-sample | 0.2436 | 0.3749 | 0.0468 |
| prestashop-day | PrestaShop Day | Vendredi Society | ADVERTISING_CAMPAIGNS | VOTD | 7.26 | cloudflare-stream | 29.91 | 1280x720 | 60.000 | 4.26 | 15.2 | 2 | 66.9 | 0 | 0.00 | 2.01 | -100% | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.4812 | 0.2267 | 0.1960 |
| tripolis-park-imagination | Tripolis-Park™ — Imagination | PlusOne® | EXPLANATORY_VIDEO | VOTD | 7.26 | cloudflare-stream | 92.07 | 1280x720 | 25.000 | 2.26 | 24.8 | 4 | 43.4 | 20 | 30.00 | 29.98 | +0% | 18.32-46.33 | 0.000 | 46.0 | 27 | 17 | 27 | — | 0.4631 | 0.2828 | 0.1130 |
| electricdreams | Electric Dreams | Jonas Rauber | EXPERIMENTAL | HM | 7.25 | direct-mp4 | 116.25 | 2400x1000 | 24.000 | 12.69 | 175.9 | 4 | 34.4 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.0626 | 0.5295 | 0.0272 |
| 100m-race-mowe-studio | 100m Race - MOWE Studio | MOWE STUDIO | SELF_BRANDING | VOTD | 7.24 | cloudflare-stream | 26.54 | 1280x720 | 24.000 | 3.44 | 10.9 | 2 | 75.4 | 16 | 48.00 | 45.22 | +6% | 27.44-77.95 | 0.688 | 6.0 | 15 | 7 | 15 | burst-heavy | 0.3354 | 0.4612 | 0.0645 |
| fritz-kola-founders-story | Fritz-Kola Founder's Story | Kinisi | EXPLANATORY_VIDEO | HM | 7.24 | cloudflare-stream | 67.75 | 1280x720 | 24.000 | 1.76 | 14.2 | 4 | 59.0 | 54 | 81.00 | 61.10 | +33% | 14.36-162.65 | 0.981 | 2.0 | 29 | 15 | 29 | burst-heavy, non-edit-scene-change | 0.7192 | 0.0254 | 0.0615 |
| real-canadian-superstore | Legendary Holidays - Real Canadian Superstore | Tonic DNA | ADVERTISING_COMMERCIALS | HM | 7.24 | cloudflare-stream | 30.08 | 1080x1080 | 23.976 | 3.02 | 10.8 | 2 | 66.5 | 2 | 6.00 | 5.98 | +0% | 0.73-21.67 | 0.000 | 360.0 | 20 | 2 | 20 | — | 0.2928 | 0.5002 | 0.1683 |
| vet-boroschek-spot | Vet boroschek spot | draff studio | ADVERTISING_SOCIAL_MEDIA_ADS | — | 7.24 | cloudflare-stream | 25.34 | 1280x720 | 24.000 | 1.80 | 5.4 | 2 | 78.9 | 12 | 36.00 | 33.14 | +9% | 18.60-62.88 | 0.667 | 4.0 | 16 | 6 | 16 | burst-heavy | 0.5460 | 0.2796 | 0.2415 |
| five | Five | Sebastian Helene | SHORT_FILMS | VOTD | 7.23 | cloudflare-stream | 92.99 | 1280x720 | 25.000 | 3.72 | 41.2 | 4 | 43.0 | 12 | 18.00 | 12.26 | +47% | 7.15-34.77 | 0.000 | 48.0 | 33 | 11 | 33 | — | 0.6301 | 0.3482 | 0.0902 |
| tedeschi-trucks-band-hard-case-music-video | TEDESCHI TRUCKS BAND "Hard Case" Music Video | PorkchopBob Studio | MUSIC_VIDEOS | VOTD | 7.23 | cloudflare-stream | 202.24 | 1280x720 | 23.976 | 3.83 | 92.2 | 4 | 19.8 | 35 | 52.50 | 48.66 | +8% | 16.40-98.98 | 0.886 | 2.0 | 31 | 13 | 31 | burst-heavy, low-coverage, non-edit-scene-change | 0.2950 | 0.2526 | 0.1029 |
| the-idea-guide | The Idea Guide | Lenar Singatullov | SHORT_FILMS | VOTD | 7.23 | direct-mp4 | 45.57 | 1920x1080 | 30.000 | 19.92 | 108.2 | 4 | 87.8 | 17 | 25.50 | 22.38 | +14% | 6.01-53.57 | 0.824 | 6.0 | 34 | 10 | 34 | burst-heavy | 0.2752 | 0.3049 | 0.1518 |
| btv-1 | BTV | N3 | BROADCAST_CHANNEL_BRANDING | VOTD | 7.21 | direct-mp4 | 55.53 | 1920x1080 | 25.000 | 25.55 | 169.2 | 4 | 72.0 | 7 | 10.50 | 8.64 | +21% | 2.39-24.87 | 0.000 | 75.0 | 37 | 7 | 37 | — | 0.5981 | 0.3604 | 0.1650 |
| dracodraco-1 | Dracodraco | P2 Content Creators | MUSIC_VIDEOS | VOTD | 7.21 | cloudflare-stream | 234.03 | 1280x720 | 25.000 | 1.38 | 38.5 | 4 | 17.1 | 2 | 3.00 | 5.13 | -41% | 0.00-14.08 | 0.000 | 106.0 | 42 | 2 | 42 | low-coverage | 0.4091 | 0.4810 | 0.0809 |
| ea-junior-club | EA JUNIOR CLUB | BALANCE | ADVERTISING_COMMERCIALS | VOTD | 7.21 | cloudflare-stream | 48.04 | 1280x720 | 24.000 | 3.38 | 19.3 | 4 | 83.3 | 8 | 12.00 | 12.49 | -4% | 0.00-35.29 | 0.000 | 31.0 | 37 | 7 | 37 | — | 0.5701 | 0.3815 | 0.1928 |
| kinetic-lyrics-to-toy-by-young-father | Kinetic Lyrics Video for Toy by Young Fathers | Reed Sullivan | MUSIC_VIDEOS | VOTD | 7.21 | cloudflare-stream | 103.06 | 1280x720 | 29.970 | 3.73 | 45.8 | 4 | 38.8 | 103 | 154.50 | 133.90 | +15% | 67.30-255.48 | 0.680 | 7.5 | 6 | 38 | 6 | burst-heavy, sparse-delta-basis | 0.1567 | 0.0622 | 0.1308 |
| pay-0 | Ø Pay | .raw | ADVERTISING_CAMPAIGNS | VOTD | 7.21 | cloudflare-stream | 33.32 | 1280x720 | 60.000 | 1.86 | 7.4 | 2 | 60.0 | 0 | 0.00 | 0.00 | — | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.5227 | 0.4245 | 0.1851 |
| alien-jump-loop | Alien Jump Loop | armvisual | EXPERIMENTAL | VOTD | 7.20 | cloudflare-stream | 15.02 | 1280x720 | 24.000 | 1.72 | 3.1 | 1 | 66.6 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.4221 | 0.5390 | 0.3333 |
| dvinum-motion-graphics-3d | Dvinum Motion Graphics 3D | Promokore | ADVERTISING_CAMPAIGNS | VOTD | 7.20 | cloudflare-stream | 32.00 | 1280x720 | 25.000 | 3.40 | 13.0 | 2 | 62.5 | 2 | 6.00 | 5.62 | +7% | 0.73-21.67 | 0.000 | 103.0 | 20 | 2 | 20 | — | 0.3271 | 0.2761 | 0.2202 |
| galeecha | GALEECHA | Geert van Hooff | EXPERIMENTAL | VOTD | 7.20 | cloudflare-stream | 30.06 | 1280x720 | 30.000 | 3.00 | 10.8 | 2 | 66.5 | 3 | 9.00 | 5.99 | +50% | 1.86-26.30 | 0.000 | 53.5 | 19 | 3 | 19 | — | 0.1233 | 0.2495 | 0.0997 |
| illu | ILLU - Cirque du Soleil | ALEJANDRO GIL | ADVERTISING_COMMERCIALS | VOTD | 7.20 | cloudflare-stream | 20.05 | 1280x720 | 25.000 | 3.10 | 7.4 | 1 | 49.9 | 0 | 0.00 | 2.99 | -100% | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.5278 | 0.4775 | 0.2065 |
| lavazza-coffee | Lavazza Coffee | mohamedjozef | ADVERTISING_COMMERCIALS | HM | 7.20 | cloudflare-stream | 20.04 | 1280x720 | 25.000 | 1.88 | 4.5 | 1 | 49.9 | 4 | 24.00 | 20.96 | +15% | 6.54-61.45 | 0.750 | 2.0 | 9 | 2 | 9 | burst-heavy, non-edit-scene-change, short-sample | 0.3433 | 0.3290 | 0.1529 |
| beter-the-original-brush | BETER: The Original Brush | Nacho Velasco | ADVERTISING_COMMERCIALS | VOTD | 7.19 | cloudflare-stream | 17.58 | 1280x720 | 30.000 | 2.12 | 4.4 | 1 | 56.9 | 4 | 24.00 | 17.07 | +41% | 6.54-61.45 | 0.500 | 46.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.7015 | 0.2386 | 0.1514 |
| us-election | US election | Vahid Rasouli | BROADCAST_PROGRAM_TITLES | VOTD | 7.19 | cloudflare-stream | 11.31 | 1280x720 | 25.000 | 2.80 | 3.8 | 1 | 88.4 | 17 | 102.00 | 90.21 | +13% | 59.42-163.31 | 0.706 | 4.0 | 4 | 7 | 4 | burst-heavy, short-sample, sparse-delta-basis | 0.2990 | 0.5591 | 0.1627 |
| all-work-and-no-play-1 | All work and no play | David Baertz | SELF_BRANDING | VOTD | 7.18 | cloudflare-stream | 30.04 | 888x480 | 25.000 | 1.12 | 4.0 | 2 | 66.6 | 0 | 0.00 | 0.00 | — | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.3373 | 0.3338 | 0.1296 |
| sciex-now-software-teaser-video | Sciex Now - Software Teaser Video | Katie Royle | ADVERTISING_SOCIAL_MEDIA_ADS | HM | 7.18 | cloudflare-stream | 44.37 | 1280x720 | 30.000 | 1.30 | 6.9 | 3 | 67.6 | 2 | 4.00 | 4.06 | -1% | 0.00-18.78 | 0.000 | 63.0 | 31 | 2 | 31 | — | 0.8695 | 0.0967 | 0.0967 |
| the-mystery-elevator | The Mystery Elevator | Stephy Fung | SHORT_FILMS | VOTD | 7.18 | cloudflare-stream | 70.27 | 1280x720 | 30.000 | 3.48 | 29.1 | 4 | 56.9 | 9 | 13.50 | 16.22 | -17% | 5.16-27.31 | 0.000 | 108.0 | 35 | 9 | 35 | — | 0.3767 | 0.5009 | 0.0143 |
| wolverine-shift-plus | Wolverine: Shift Plus | Already Been chewed | ADVERTISING_CAMPAIGNS | VOTD | 7.18 | cloudflare-stream | 30.02 | 1280x720 | 24.000 | 3.70 | 13.2 | 2 | 66.6 | 3 | 9.00 | 7.99 | +13% | 1.86-26.30 | 0.000 | 310.5 | 19 | 3 | 19 | — | 0.3221 | 0.2240 | 0.1665 |
| interruption-1 | Interruption | Collin leix | EXPERIMENTAL | VOTD | 7.17 | direct-mp4 | 40.12 | 3840x2160 | 24.000 | 11.77 | 56.3 | 3 | 74.8 | 10 | 20.00 | 22.43 | -11% | 8.13-39.13 | 0.400 | 64.0 | 26 | 7 | 26 | — | 0.4705 | 0.3259 | 0.1602 |
| monster-energy-animation | Monster Energy Drink - Dragon | alanomoxo | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.17 | cloudflare-stream | 10.47 | 1080x1080 | 24.000 | 3.94 | 4.9 | 1 | 85.9 | 24 | 160.00 | 137.47 | +16% | 102.52-238.07 | 1.000 | 2.0 | 5 | 6 | 5 | burst-heavy, non-edit-scene-change, short-sample, sparse-delta-basis | 0.2636 | 0.6441 | 0.2877 |
| moving-up | Moving Up | PES Motion Studio | BROADCAST_CHANNEL_BRANDING | VOTD | 7.17 | direct-mp4 | 8.36 | 1920x1080 | 25.000 | 50.58 | 50.4 | 1 | 83.7 | 3 | 25.71 | 21.53 | +19% | 5.30-75.15 | 0.000 | 41.5 | 8 | 3 | 8 | short-sample | 0.4894 | 0.4946 | 0.2238 |
| roves-8th-birthday | ROVE's Birthday | ROVE | SELF_BRANDING | — | 7.17 | cloudflare-stream | 16.34 | 1280x720 | 24.000 | 1.51 | 2.9 | 1 | 61.2 | 6 | 36.00 | 22.03 | +63% | 13.21-78.36 | 0.833 | 3.0 | 8 | 3 | 8 | burst-heavy, short-sample | 0.3455 | 0.3398 | 0.1185 |
| httpsvimeocom888951550 | Lumana \| 3D Identity for AI Cloud Video Security | Ubunzo | ADVERTISING_COMMERCIALS | HM | 7.16 | cloudflare-stream | 25.15 | 1280x720 | 25.000 | 1.99 | 6.0 | 2 | 79.5 | 4 | 12.00 | 11.93 | +1% | 3.27-30.72 | 0.500 | 84.0 | 19 | 3 | 19 | — | 0.5649 | 0.1535 | 0.1556 |
| semrush-enterprise | Semrush Enterprise | NewTab Studio | EXPLANATORY_VIDEO | VOTD | 7.16 | cloudflare-stream | 100.54 | 1280x720 | 24.000 | 1.08 | 12.9 | 4 | 39.8 | 3 | 4.50 | 7.76 | -42% | 0.55-14.06 | 0.000 | 302.0 | 41 | 3 | 41 | — | 0.2363 | 0.7406 | 0.1190 |
| aj-mitchell-burn-music-video-1 | AJ Mitchell - Burn music video | Framelight Studio | MUSIC_VIDEOS | VOTD | 7.15 | cloudflare-stream | 139.99 | 1280x720 | 24.000 | 3.71 | 61.9 | 4 | 28.6 | 8 | 12.00 | 18.86 | -36% | 5.18-23.64 | 0.250 | 108.0 | 37 | 7 | 37 | — | 0.2299 | 0.1856 | 0.0418 |
| covid-xix-beat-the-virus | Covid XIX | Studio MAD | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.15 | cloudflare-stream | 59.43 | 1280x720 | 25.000 | 3.15 | 22.3 | 4 | 67.3 | 1 | 1.50 | 1.01 | +49% | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.2004 | 0.0016 | 0.1077 |
| oncode-institute | Oncode Institute | Momkai | EXPLANATORY_VIDEO | VOTD | 7.15 | cloudflare-stream | 99.43 | 1280x720 | 30.000 | 3.66 | 43.4 | 4 | 40.2 | 3 | 4.50 | 2.41 | +86% | 0.55-14.06 | 0.000 | 438.0 | 41 | 3 | 41 | — | 0.3157 | 0.7395 | 0.0767 |
| rest-before-the-light-and-breath-to-reach-the-light | Rest before the light, and Breath to reach the light | eden_jeonminho | INSTALLATION_PROJECTION_EXPERIENCE | — | 7.15 | cloudflare-stream | 142.36 | 1120x240 | 30.000 | 0.62 | 10.5 | 4 | 28.1 | 1 | 1.50 | 2.11 | -29% | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.2427 | 0.0838 | 0.0362 |
| cant-beat-me-1 | Can't Beat Me | MOWE STUDIO | SHORT_FILMS | VOTD | 7.14 | direct-mp4 | 78.06 | 1920x1080 | 24.000 | 2.67 | 24.9 | 4 | 51.2 | 31 | 46.50 | 52.27 | -11% | 1.41-105.50 | 0.516 | 6.0 | 30 | 14 | 30 | burst-heavy | 0.2499 | 0.1635 | 0.0523 |
| chantecaille-global-lip-creme-launch-campaign | Chantecaille: Global Lip Crème Launch Campaign | Zilan Lin | ADVERTISING_CAMPAIGNS | VOTD | 7.14 | cloudflare-stream | 30.06 | 1280x720 | 24.000 | 0.94 | 3.4 | 2 | 66.5 | 1 | 3.00 | 7.98 | -62% | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.6840 | 0.1352 | 0.0463 |
| david-guerrero-for-emeerree-part-i | David Guerrero for Emeerree, Part I | David Guerrero | ADVERTISING_CAMPAIGNS | VOTD | 7.14 | cloudflare-stream | 37.57 | 1280x720 | 24.000 | 1.32 | 5.9 | 3 | 79.9 | 8 | 16.00 | 12.78 | +25% | 6.91-31.53 | 0.000 | 75.0 | 25 | 8 | 25 | — | 0.6108 | 0.0401 | 0.0966 |
| anymotion-festival-2019-opening-titles | Anymotion Festival 2019 - Opening Titles | MOWE STUDIO | LIVE_EVENT_TITLES | VOTD | 7.13 | cloudflare-stream | 82.07 | 1280x720 | 24.000 | 4.20 | 41.1 | 4 | 48.7 | 36 | 54.00 | 39.48 | +37% | 16.38-102.27 | 0.611 | 12.0 | 24 | 20 | 24 | burst-heavy | 0.5096 | 0.6568 | 0.1216 |
| rechannel | Rechannel | RENDER Entertainment | ADVERTISING_COMMERCIALS | — | 7.13 | cloudflare-stream | 51.38 | 1280x720 | 30.000 | 1.65 | 10.1 | 4 | 77.9 | 27 | 40.50 | 33.87 | +20% | 10.94-79.93 | 0.630 | 19.5 | 28 | 16 | 28 | burst-heavy | 0.2606 | 0.3622 | 0.0802 |
| uniform-wares-heart-of-quartz | UNIFORM WARES - Heart of Quartz | Savage & Civil | ADVERTISING_CAMPAIGNS | VOTD | 7.13 | cloudflare-stream | 30.04 | 1080x360 | 25.000 | 0.92 | 3.3 | 2 | 66.6 | 2 | 6.00 | 5.99 | +0% | 0.73-21.67 | 0.000 | 226.0 | 20 | 2 | 20 | — | 0.2243 | 0.2713 | 0.1407 |
| cuedays | CUEdays | mr.Preview / Shahryar Namayeshi | ADVERTISING_COMMERCIALS | VOTD | 7.12 | cloudflare-stream | 19.73 | 1280x720 | 25.000 | 0.74 | 1.7 | 1 | 50.7 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.7680 | 0.1333 | 0.0479 |
| drop-dead-signal | Drop Dead Signal | penmouse | SELF_BRANDING | VOTD | 7.12 | cloudflare-stream | 46.38 | 1280x720 | 24.000 | 2.92 | 16.1 | 4 | 86.2 | 16 | 24.00 | 20.70 | +16% | 0.00-60.17 | 0.625 | 8.0 | 36 | 8 | 36 | burst-heavy | 0.2640 | 0.3627 | 0.0774 |
| nobull-journey-2-1 | NOBULL Journey 2 | ROVE | ADVERTISING_CAMPAIGNS | — | 7.12 | cloudflare-stream | 30.04 | 1280x720 | 24.000 | 2.59 | 9.3 | 2 | 66.6 | 2 | 6.00 | 3.99 | +50% | 0.73-21.67 | 0.000 | 319.0 | 20 | 2 | 20 | — | 0.4434 | 0.3727 | 0.1616 |
| yandex-lavka-in-yekaterinburg-1 | Yandex Lavka in Yekaterinburg | ktonado.digital | ADVERTISING_COMMERCIALS | VOTD | 7.12 | cloudflare-stream | 15.02 | 1280x720 | 30.000 | 0.94 | 1.7 | 1 | 66.6 | 2 | 12.00 | 7.99 | +50% | 1.45-43.35 | 0.000 | 104.0 | 9 | 2 | 9 | short-sample | 0.7334 | 0.2402 | 0.0522 |
| an-endless-circle | an endless circle | Jonas Rauber | SELF_BRANDING | HM | 7.11 | cloudflare-stream | 32.66 | 1120x480 | 25.000 | 1.90 | 7.4 | 2 | 61.2 | 3 | 9.00 | 5.51 | +63% | 1.86-26.30 | 0.000 | 205.5 | 19 | 3 | 19 | — | 0.1071 | 0.3757 | 0.0585 |
| hp-tuners-e90-ecm-launch | HP Tuners E90 ECM Launch | Evan Light | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.11 | cloudflare-stream | 34.37 | 1280x720 | 30.000 | 3.42 | 14.0 | 3 | 87.3 | 19 | 38.00 | 33.17 | +15% | 22.88-59.34 | 0.526 | 33.0 | 20 | 13 | 20 | burst-heavy | 0.3231 | 0.3391 | 0.1484 |
| time-1 | TIME | Milush.Design | SELF_BRANDING | VOTD | 7.11 | cloudflare-stream | 22.98 | 1280x720 | 25.000 | 3.35 | 9.2 | 2 | 87.0 | 7 | 21.00 | 20.89 | +1% | 8.44-43.27 | 0.000 | 46.5 | 15 | 7 | 15 | — | 0.2889 | 0.4352 | 0.0977 |
| how-much-emergency-cash-is-enough | DBS - Save better with these tips! | pixeltie | EXPLANATORY_VIDEO | VOTD | 7.10 | cloudflare-stream | 108.03 | 1280x720 | 30.000 | 0.72 | 9.3 | 4 | 37.0 | 0 | 0.00 | 0.56 | -100% | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.8758 | 0.1389 | 0.0702 |
| plan-a-opener-rudaw-media-network | Plan A Opener (Rudaw Media Network) | Didar Dlshad | BROADCAST_CHANNEL_BRANDING | VOTD | 7.10 | cloudflare-stream | 16.45 | 1280x720 | 25.000 | 1.20 | 2.4 | 1 | 60.8 | 1 | 6.00 | 3.65 | +64% | 0.15-33.43 | — | — | 10 | 1 | 10 | short-sample | 0.4926 | 0.5074 | 0.2786 |
| raw-experiment-01 | .raw experiment 01 | .raw | ADVERTISING_CAMPAIGNS | VOTD | 7.10 | cloudflare-stream | 78.57 | 1280x720 | 25.000 | 1.22 | 11.4 | 4 | 50.9 | 29 | 43.50 | 37.42 | +16% | 27.57-64.54 | 0.138 | 22.0 | 22 | 22 | 22 | — | 0.1876 | 0.3229 | 0.0908 |
| biobar | BioBar | RENDER Entertainment | ADVERTISING_COMMERCIALS | — | 7.09 | cloudflare-stream | 22.04 | 1280x720 | 30.000 | 1.32 | 3.5 | 1 | 45.4 | 11 | 66.00 | 65.33 | +1% | 32.95-118.09 | 0.545 | 9.0 | 6 | 5 | 6 | burst-heavy, short-sample, sparse-delta-basis | 0.4465 | 0.2959 | 0.1370 |
| david-bowie-the-man-who-sold-the-world-official-lyric-video | David Bowie - The Man Who Sold The World [Official Lyric Video] | Tabitha Moore | MUSIC_VIDEOS | VOTD | 7.08 | cloudflare-stream | 241.02 | 1280x720 | 25.000 | 3.57 | 102.6 | 4 | 16.6 | 15 | 22.50 | 27.13 | -17% | 4.59-48.91 | 0.933 | 3.0 | 37 | 7 | 37 | burst-heavy, low-coverage | 0.1445 | 0.3944 | 0.0493 |
| vendredi-society | Vendredi Society | Vendredi Society | ADVERTISING_CAMPAIGNS | VOTD | 7.08 | cloudflare-stream | 54.76 | 1280x720 | 30.000 | 1.81 | 11.8 | 4 | 73.0 | 28 | 42.00 | 44.92 | -7% | 26.32-62.81 | 0.143 | 37.0 | 19 | 25 | 19 | — | 0.5295 | 0.2669 | 0.1942 |
| inspired-by-xiaomi-mi-10-pro-1 | INSPIRED BY XIAOMI MI 10 PRO | KUTUKO STUDIO | ADVERTISING_COMMERCIALS | VOTD | 7.07 | cloudflare-stream | 33.24 | 1152x480 | 25.000 | 2.13 | 8.5 | 2 | 60.2 | 4 | 12.00 | 21.66 | -45% | 3.27-30.72 | 0.000 | 85.0 | 18 | 4 | 18 | — | 0.5010 | 0.4164 | 0.0956 |
| airconqueror | airconqueror | Pavel Motorin | ADVERTISING_COMMERCIALS | VOTD | 7.06 | cloudflare-stream | 45.06 | 1280x720 | 30.000 | 2.84 | 15.3 | 4 | 88.8 | 14 | 21.00 | 18.64 | +13% | 11.48-35.23 | 0.000 | 72.0 | 30 | 14 | 30 | — | 0.5216 | 0.3555 | 0.1428 |
| malibu-boats-the-m240 | Malibu Boats: The M240 | Already Been chewed | ADVERTISING_COMMERCIALS | VOTD | 7.06 | direct-mp4 | 72.81 | 1920x1080 | 24.000 | 4.93 | 42.8 | 4 | 54.9 | 10 | 15.00 | 14.83 | +1% | 7.19-27.59 | 0.000 | 75.0 | 34 | 10 | 34 | — | 0.1768 | 0.2700 | 0.1368 |
| thunder-challenge-entry | Thunder Challenge Entry | alanomoxo | ADVERTISING_SOCIAL_MEDIA_ADS | VOTD | 7.06 | cloudflare-stream | 12.84 | 1280x720 | 30.000 | 3.37 | 5.2 | 1 | 77.9 | 5 | 30.00 | 42.05 | -29% | 9.74-70.01 | 1.000 | 2.5 | 8 | 3 | 8 | burst-heavy, non-edit-scene-change, short-sample | 0.1775 | 0.6705 | 0.2522 |
| drive-reach-overland-feature-video | Drive Reach Overland Feature Video | Shrinkwrap studio | ADVERTISING_CAMPAIGNS | HM | 7.05 | cloudflare-stream | 68.22 | 1280x720 | 24.000 | 2.12 | 17.2 | 4 | 58.6 | 12 | 18.00 | 17.59 | +2% | 9.30-31.44 | 0.167 | 51.0 | 33 | 11 | 33 | — | 0.4002 | 0.2858 | 0.1335 |
| httpsvimeocom528258339 | A Grim Bond | Pisuicas | SELF_BRANDING | HM | 7.05 | cloudflare-stream | 101.06 | 1280x720 | 30.000 | 3.81 | 45.9 | 4 | 39.6 | 12 | 18.00 | 7.72 | +133% | 5.70-37.01 | 0.333 | 31.0 | 36 | 8 | 36 | — | 0.1424 | 0.2272 | 0.0348 |
| mellowsoda-vision | mellowsoda CREATIVE VISION | mellowsoda.inc | TITLE_SEQUENCES | VOTD | 7.05 | cloudflare-stream | 31.27 | 1280x720 | 23.976 | 3.54 | 13.2 | 2 | 63.9 | 1 | 3.00 | 1.92 | +56% | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.8817 | 0.0971 | 0.0805 |
| security-me-1 | Security me | @granatowsky_ | EXPLANATORY_VIDEO | VOTD | 7.05 | direct-mp4 | 89.83 | 1920x1080 | 12.000 | 8.89 | 95.2 | 4 | 44.5 | 9 | 13.50 | 12.69 | +6% | 5.16-27.31 | 0.444 | 22.0 | 38 | 6 | 38 | — | 0.6493 | 0.3783 | 0.0561 |
| showreel-2026-motion-design-and-art-direction | Showreel 2026 - Motion design and Art direction | Raphaël Bluzet | INSTALLATION_PROJECTION_EXPERIENCE | — | 7.05 | cloudflare-stream | 67.78 | 1280x720 | 25.000 | 3.01 | 24.4 | 4 | 59.0 | 28 | 42.00 | 39.84 | +5% | 16.64-75.65 | 0.250 | 22.0 | 23 | 21 | 23 | — | 0.4582 | 0.3139 | 0.1232 |
| youth-route | Youth Route | Hound Studio | SHORT_FILMS | VOTD | 7.05 | cloudflare-stream | 132.16 | 1280x720 | 24.000 | 3.86 | 60.8 | 4 | 30.3 | 4 | 6.00 | 4.54 | +32% | 1.63-15.36 | 0.000 | 698.0 | 40 | 4 | 40 | — | 0.8408 | 0.1782 | 0.0315 |
| motion-reel-2020-dont-blink-please | Motion Reel 2020 \| Don't Blink Please | Vincent Renault | SELF_BRANDING | VOTD | 7.04 | cloudflare-stream | 60.00 | 1280x720 | 30.000 | 4.18 | 29.9 | 4 | 66.7 | 18 | 27.00 | 30.00 | -10% | 10.88-49.97 | 0.444 | 41.0 | 30 | 14 | 30 | — | 0.5285 | 0.1409 | 0.2001 |
| perseverance | Perseverance | Ayoub Hadir | FILM_GRAPHICS | HM | 7.04 | cloudflare-stream | 29.80 | 1080x1080 | 24.000 | 1.34 | 4.8 | 2 | 67.1 | 3 | 9.00 | 6.04 | +49% | 1.86-26.30 | 0.000 | 36.5 | 19 | 3 | 19 | — | 0.2399 | 0.5241 | 0.1002 |
| vsgoods | VS/Goods© | Vendredi Society | ADVERTISING_COMMERCIALS | — | 7.04 | cloudflare-stream | 32.13 | 1280x720 | 30.000 | 1.58 | 6.1 | 2 | 62.3 | 26 | 78.00 | 61.63 | +27% | 50.95-114.29 | 0.846 | 5.0 | 13 | 9 | 13 | burst-heavy | 0.3123 | 0.0792 | 0.1195 |
| uktv-how-we-work | UKTV How We Work | UKTV Creative | SELF_BRANDING | HM | 7.03 | cloudflare-stream | 120.04 | 1280x720 | 25.000 | 1.27 | 18.2 | 4 | 33.3 | 8 | 12.00 | 15.49 | -23% | 1.58-29.79 | 0.000 | 62.0 | 36 | 8 | 36 | — | 0.5588 | 0.2685 | 0.1077 |
| 2024-unwrapped | 2024 UNWRAPPED | RENDER Entertainment | ADVERTISING_CAMPAIGNS | HM | 7.02 | cloudflare-stream | 31.04 | 1080x1920 | 30.000 | 2.75 | 10.2 | 2 | 64.4 | 2 | 6.00 | 5.80 | +3% | 0.73-21.67 | 0.000 | 55.0 | 20 | 2 | 20 | — | 0.6226 | 0.1438 | 0.1635 |
| catharsis | Catharsis | KDR | SELF_BRANDING | HM | 7.02 | cloudflare-stream | 17.49 | 1080x1080 | 30.000 | 4.95 | 10.3 | 1 | 57.2 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.0436 | 0.2613 | 0.0737 |
| fully-cg-audi-r8-commercial | Fully CG Audi R8 Commercial | RENDER Entertainment | ADVERTISING_COMMERCIALS | — | 7.02 | cloudflare-stream | 65.04 | 1280x720 | 24.000 | 1.63 | 12.7 | 4 | 61.5 | 4 | 6.00 | 3.69 | +63% | 1.63-15.36 | 0.500 | 403.0 | 41 | 3 | 41 | — | 0.5998 | 0.1347 | 0.1277 |
| movements-space-above-feat-boyboy | Movements - Space Above feat BOYBOY | Anna Chocholi | MUSIC_VIDEOS | VOTD | 7.02 | cloudflare-stream | 254.93 | 1280x720 | 29.970 | 3.70 | 112.4 | 4 | 15.7 | 2 | 3.00 | 9.65 | -69% | 0.36-10.84 | 0.000 | 4289.0 | 42 | 2 | 42 | low-coverage | 0.1847 | 0.1176 | 0.0988 |
| genesis-motion-design-manifesto | Genesis motion design : manifesto | Genesis Motion Design | SELF_BRANDING | VOTD | 7.01 | direct-mp4 | 64.30 | 1920x1080 | 24.000 | 3.75 | 28.7 | 4 | 62.2 | 34 | 51.00 | 57.86 | -12% | 0.00-125.11 | 0.735 | 5.0 | 29 | 15 | 29 | burst-heavy | 0.3567 | 0.6019 | 0.2342 |
| just-dream-it-we-built-that | Just DREAM it, We built that... | mr.Preview / Shahryar Namayeshi | ADVERTISING_COMMERCIALS | HM | 7.01 | cloudflare-stream | 41.90 | 1280x720 | 25.000 | 1.26 | 6.3 | 3 | 71.6 | 4 | 8.00 | 5.73 | +40% | 2.18-20.48 | 0.000 | 199.0 | 29 | 4 | 29 | — | 0.4912 | 0.2265 | 0.0814 |
| get-started-to-voyage | Get started to voyage | Rogério Rolo | EXPERIMENTAL | — | 6.99 | cloudflare-stream | 53.93 | 1280x720 | 29.970 | 1.61 | 10.4 | 4 | 74.2 | 1 | 1.50 | 1.11 | +35% | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.1136 | 0.8503 | 0.1739 |
| httpsdrivegooglecomfiled1ygqwll0zbk-a9ul0mdofrb4qqsokd-t0viewuspsharing | 𝗔𝗡𝗜𝗠𝗔𝗟𝗦 – 𝗧𝗵𝗲 𝗔𝗿𝘁 𝗼𝗳 𝗦𝘁𝗶𝗹𝗹𝗻𝗲𝘀𝘀 | KUTUKO STUDIO | EXPERIMENTAL | — | 6.99 | cloudflare-stream | 95.02 | 1280x720 | 24.000 | 2.22 | 25.2 | 4 | 42.1 | 7 | 10.50 | 12.63 | -17% | 4.22-21.63 | 0.000 | 122.0 | 37 | 7 | 37 | — | 0.4924 | 0.3442 | 0.0960 |
| test-4 | SharePointTemplates - Launch Animation | Jakub Holub | ADVERTISING_COMMERCIALS | — | 6.99 | cloudflare-stream | 44.63 | 1280x720 | 60.000 | 2.01 | 10.7 | 4 | 89.6 | 32 | 48.00 | 44.37 | +8% | 7.16-101.21 | 0.750 | 10.0 | 32 | 12 | 32 | burst-heavy | 0.6027 | 0.2854 | 0.1961 |
| threaten-with-love-pocky-1 | Threaten with Love - Pocky | Khrusha Parekh | ADVERTISING_CAMPAIGNS | — | 6.99 | cloudflare-stream | 6.12 | 1080x1920 | 30.000 | 1.15 | 0.8 | 1 | 81.7 | 20 | 240.00 | 205.79 | +17% | 146.60-370.66 | 0.900 | 3.0 | 2 | 9 | 2 | burst-heavy, short-sample, sparse-delta-basis | 0.5326 | 0.5799 | 0.1709 |
| one-who-steals | One who steals | cg_machine | SHORT_FILMS | — | 6.98 | cloudflare-stream | 17.98 | 1280x720 | 24.000 | 2.30 | 4.9 | 1 | 55.6 | 2 | 12.00 | 6.67 | +80% | 1.45-43.35 | 0.000 | 61.0 | 9 | 2 | 9 | short-sample | 0.1800 | 0.2643 | 0.0761 |
| unkle-psyence-fiction-teaser | UNKLE Psyence Fiction Teaser | Dorcia Studio | MUSIC_VIDEOS | — | 6.98 | direct-mp4 | 51.00 | 1920x1080 | 25.000 | 10.00 | 60.8 | 4 | 78.4 | 260 | 390.00 | 361.18 | +8% | 336.72-448.42 | 0.996 | 3.0 | 1 | 43 | 1 | burst-heavy, sparse-delta-basis | 0.4823 | 0.1315 | 0.1152 |
| moncler-trainers-product-teaser | Moncler Trainers - Product Teaser | Renderologists | ADVERTISING_COMMERCIALS | — | 6.97 | cloudflare-stream | 25.92 | 1080x1920 | 24.000 | 3.91 | 12.1 | 2 | 77.2 | 16 | 48.00 | 57.88 | -17% | 27.44-77.95 | 0.375 | 13.0 | 14 | 8 | 14 | — | 0.2004 | 0.0121 | 0.0962 |
| concept-bureau-talks-broadcast-motion-design | Concept Bureau Talks Broadcast Motion Design | the unicorn | BROADCAST_CHANNEL_BRANDING | — | 6.96 | cloudflare-stream | 28.27 | 1280x720 | 30.000 | 2.86 | 9.6 | 2 | 70.8 | 0 | 0.00 | 0.00 | — | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.5764 | 0.8100 | 0.1654 |
| rechannel-marketing-a-function | Rechannel - Marketing_a function () | RENDER Entertainment | ADVERTISING_COMMERCIALS | — | 6.96 | cloudflare-stream | 26.04 | 1280x720 | 30.000 | 1.10 | 3.4 | 2 | 76.8 | 1 | 3.00 | 2.30 | +30% | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.0781 | 0.1143 | 0.0234 |
| playboy-secret-sessions | Playboy Secret sessions | LUMBRE | BROADCAST_SERIES_TITLES | — | 6.95 | direct-mp4 | 13.93 | 1920x1080 | 23.976 | 8.59 | 14.3 | 1 | 71.8 | 5 | 30.00 | 25.84 | +16% | 9.74-70.01 | 0.000 | 40.0 | 6 | 5 | 6 | short-sample, sparse-delta-basis | 0.5008 | 0.4528 | 0.1741 |
| playboy-uncovered | Playboy uncovered | LUMBRE | BROADCAST_SERIES_TITLES | — | 6.95 | direct-mp4 | 18.02 | 1920x1080 | 23.976 | 9.71 | 20.9 | 1 | 55.5 | 0 | 0.00 | 6.66 | -100% | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.1256 | 0.7042 | 0.0900 |
| creatools-saas-presentation-video | Creatools - Saas Presentation Video | Retnika Studio | ADVERTISING_COMMERCIALS | — | 6.94 | cloudflare-stream | 41.37 | 1280x720 | 59.940 | 1.04 | 5.1 | 3 | 72.5 | 5 | 10.00 | 10.15 | -2% | 3.25-23.34 | 0.000 | 389.5 | 28 | 5 | 28 | — | 0.6236 | 0.1820 | 0.1134 |
| fbi-jobs-the-essentials | FBI - Jobs - the gfx essentials | penmouse | ADVERTISING_COMMERCIALS | — | 6.94 | cloudflare-stream | 41.13 | 1280x720 | 23.976 | 2.56 | 12.5 | 3 | 72.9 | 95 | 190.00 | 194.02 | -2% | 148.05-238.87 | 0.705 | 6.0 | 2 | 31 | 2 | burst-heavy, sparse-delta-basis | 0.2994 | 0.2377 | 0.1997 |
| httpsvimeocom1180878257sharecopyflsvfeci | Openmart Reel | effy lan | SELF_BRANDING | — | 6.94 | cloudflare-stream | 33.39 | 1280x720 | 24.000 | 0.71 | 2.8 | 3 | 89.9 | 12 | 24.00 | 21.57 | +11% | 12.40-41.92 | 0.000 | 42.0 | 21 | 12 | 21 | — | 0.5673 | 0.2746 | 0.0719 |
| sonos-the-future-of-listening | Sonos \| The Future of Listening | ROVE | SELF_BRANDING | — | 6.94 | cloudflare-stream | 15.06 | 1280x720 | 24.000 | 3.71 | 6.7 | 1 | 66.4 | 1 | 6.00 | 7.97 | -25% | 0.15-33.43 | — | — | 10 | 1 | 10 | short-sample | 0.3688 | 0.4410 | 0.2710 |
| franck-muller-fr2nck-muller-vanguard | Franck Muller - #FR2NCK MULLER VANGUARD | le truc | ADVERTISING_CAMPAIGNS | — | 6.93 | cloudflare-stream | 30.06 | 1280x720 | 25.000 | 2.86 | 10.3 | 2 | 66.5 | 12 | 36.00 | 37.93 | -5% | 18.60-62.88 | 0.167 | 34.0 | 12 | 10 | 12 | — | 0.3074 | 0.0761 | 0.2243 |
| i-should-like-to-see-my-drawing | "I should like to see my drawing." | RENDER Entertainment | SHORT_FILMS | — | 6.93 | cloudflare-stream | 34.04 | 1280x720 | 24.000 | 1.10 | 4.5 | 3 | 88.1 | 1 | 2.00 | 1.76 | +13% | 0.05-11.14 | — | — | 32 | 1 | 32 | — | 0.2366 | 0.4586 | 0.0951 |
| korolooove-x-shaghab-jewelry | Korolooove x SHAGHAB JEWELRY | korolooove | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.92 | cloudflare-stream | 10.71 | 606x1080 | 25.000 | 2.56 | 3.3 | 1 | 84.0 | 0 | 0.00 | 0.00 | — | 0.00-24.59 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.1242 | 0.1209 | 0.0448 |
| 2022-breakthrough-junior-challenge-launch-video-1 | 2022 Breakthrough Junior Challenge Launch Video | Bloom Collective | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.91 | cloudflare-stream | 56.43 | 1280x720 | 25.000 | 2.85 | 19.2 | 4 | 70.9 | 25 | 37.50 | 35.09 | +7% | 11.80-72.19 | 0.640 | 15.0 | 31 | 13 | 31 | burst-heavy | 0.4608 | 0.2454 | 0.1148 |
| hybrid-creature | Hybrid Creature | YUAN | EXPERIMENTAL | — | 6.90 | cloudflare-stream | 15.23 | 1278x720 | 15.000 | 2.93 | 5.3 | 1 | 65.7 | 1 | 6.00 | 3.94 | +52% | 0.15-33.43 | — | — | 10 | 1 | 10 | short-sample | 0.0908 | 0.0676 | 0.0780 |
| inspired-by-bauhaus | Inspired by Bauhaus | Artxzen | SELF_BRANDING | — | 6.90 | cloudflare-stream | 22.10 | 1280x720 | 25.000 | 0.95 | 2.5 | 1 | 45.2 | 3 | 18.00 | 8.14 | +121% | 3.71-52.60 | 0.000 | 61.5 | 8 | 3 | 8 | short-sample | 0.4311 | 0.1848 | 0.0912 |
| invisible-bauhaus-dessau-caught-up-by-hatred | Invisible Bauhaus Dessau - Caught Up by Hatred | navos create | ADVERTISING_CAMPAIGNS | — | 6.90 | cloudflare-stream | 105.81 | 1080x1920 | 25.000 | 4.78 | 60.3 | 4 | 37.8 | 2 | 3.00 | 2.27 | +32% | 0.00-14.08 | 0.000 | 204.0 | 42 | 2 | 42 | — | 0.4217 | 0.6625 | 0.0853 |
| home-front-every-day-life-in-1940s | HOME FRONT: EVERY DAY LIFE IN 1940S | PEACE PARK | EXPERIMENTAL | — | 6.89 | cloudflare-stream | 55.59 | 1280x720 | 30.000 | 3.62 | 24.0 | 4 | 71.9 | 10 | 15.00 | 12.95 | +16% | 0.00-41.40 | 0.000 | 64.0 | 34 | 10 | 34 | — | 0.5493 | 0.0172 | 0.1014 |
| lavi-titli-official-music-video | LAVI - Titli (Official Music Video) | Illucus.film | MUSIC_VIDEOS | — | 6.89 | cloudflare-stream | 185.43 | 1280x720 | 25.000 | 1.77 | 39.2 | 4 | 21.6 | 6 | 9.00 | 8.74 | +3% | 2.99-20.16 | 0.000 | 76.0 | 38 | 6 | 38 | low-coverage | 0.1209 | 0.2564 | 0.0609 |
| spotify-for-metalheads | Spotify for Headbangers | Avi | ADVERTISING_COMMERCIALS | — | 6.89 | cloudflare-stream | 75.05 | 1280x720 | 30.000 | 1.13 | 10.1 | 4 | 53.3 | 3 | 4.50 | 7.20 | -37% | 0.55-14.06 | 0.667 | 184.0 | 42 | 2 | 42 | burst-heavy | 0.2249 | 0.2453 | 0.1074 |
| stay-safe-animated-short-film | Stay Safe \| Animated Short Film | AS Design | SHORT_FILMS | — | 6.89 | cloudflare-stream | 120.04 | 1280x720 | 30.000 | 3.39 | 48.6 | 4 | 33.3 | 1 | 1.50 | 1.50 | +0% | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.1852 | 0.4550 | 0.0734 |
| audi-r8-cg-commercial | Audi R8 CG commercial | RENDER Entertainment | ADVERTISING_COMMERCIALS | — | 6.88 | cloudflare-stream | 65.04 | 1280x720 | 24.000 | 1.63 | 12.7 | 4 | 61.5 | 4 | 6.00 | 3.69 | +63% | 1.63-15.36 | 0.500 | 403.0 | 41 | 3 | 41 | — | 0.5998 | 0.1347 | 0.1277 |
| tiffany-co-cgi-cinematic-animation | Tiffany & Co. - CGI Cinematic Animation | Barthes | EXPERIMENTAL | — | 6.88 | cloudflare-stream | 65.92 | 1280x720 | 24.000 | 2.26 | 17.8 | 4 | 60.7 | 1 | 1.50 | 1.82 | -18% | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.0736 | 0.2442 | 0.0777 |
| design-is-a-craft-ai-is-just-a-better-workshop | Design is a Craft. AI is Just a Better Workshop (UXPin Forge Video) | Grzegorz Samson | ADVERTISING_COMMERCIALS | — | 6.87 | cloudflare-stream | 72.94 | 1280x720 | 24.000 | 0.54 | 4.7 | 4 | 54.8 | 12 | 18.00 | 19.74 | -9% | 5.70-37.01 | 0.000 | 42.0 | 33 | 11 | 33 | — | 0.4377 | 0.1475 | 0.0853 |
| vector-become-your-player | Vector Become Your Player | Tonic DNA | ADVERTISING_CAMPAIGNS | — | 6.87 | cloudflare-stream | 46.91 | 1280x720 | 23.976 | 2.36 | 13.2 | 4 | 85.3 | 29 | 43.50 | 39.65 | +10% | 26.42-66.06 | 0.690 | 9.5 | 30 | 14 | 30 | burst-heavy | 0.2261 | 0.6382 | 0.1773 |
| bloom | Cluster bloom | Nicolas Kamel | EXPERIMENTAL | — | 6.86 | cloudflare-stream | 21.61 | 1080x1920 | 30.000 | 5.67 | 14.6 | 1 | 46.3 | 1 | 6.00 | 13.88 | -57% | 0.15-33.43 | — | — | 10 | 1 | 10 | short-sample | 0.6238 | 0.1382 | 0.0936 |
| bureaucracy-monster | Bureaucracy monster | Finom / Valeriia Dadaian | ADVERTISING_CAMPAIGNS | — | 6.86 | cloudflare-stream | 46.53 | 1080x1920 | 30.000 | 1.75 | 9.7 | 4 | 86.0 | 4 | 6.00 | 5.16 | +16% | 1.63-15.36 | 0.000 | 159.0 | 40 | 4 | 40 | — | 0.7471 | 0.0786 | 0.0539 |
| fall-in-love-again-and-again | Fall in Love again and again | RENDER Entertainment | MUSIC_VIDEOS | — | 6.86 | cloudflare-stream | 40.28 | 1280x720 | 29.970 | 0.94 | 4.5 | 3 | 74.5 | 0 | 0.00 | 0.00 | — | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.1142 | 0.1704 | 0.0308 |
| love-yourself | Love Yourself | Muriel Choi | SELF_BRANDING | — | 6.86 | cloudflare-stream | 105.58 | 1280x720 | 24.000 | 2.07 | 26.1 | 4 | 37.9 | 7 | 10.50 | 7.39 | +42% | 3.38-23.12 | 0.000 | 84.5 | 37 | 7 | 37 | — | 0.1428 | 0.4226 | 0.0496 |
| mophie-fabric-knit-case-3d-ad | Mophie - Fabric Knit Case - 3D Video | Animox Studio | ADVERTISING_COMMERCIALS | — | 6.86 | cloudflare-stream | 21.70 | 1280x720 | 30.000 | 1.08 | 2.8 | 1 | 46.1 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.6979 | 0.0097 | 0.1951 |
| new-jersey-devils-third-jersey-rejoin | New Jersey Devils Third Jersey Rejoin | Aaron Kotlan | INSTALLATION_PROJECTION_EXPERIENCE | — | 6.86 | cloudflare-stream | 66.39 | 1080x1350 | 30.000 | 2.87 | 22.7 | 4 | 60.3 | 24 | 36.00 | 41.57 | -13% | 19.30-58.68 | 0.458 | 30.0 | 27 | 17 | 27 | — | 0.2054 | 0.2258 | 0.0888 |
| shrinkwrap-showreel | SHRINKWRAP SHOWREEL | Shrinkwrap studio | SELF_BRANDING | — | 6.86 | cloudflare-stream | 30.46 | 1280x720 | 24.000 | 1.68 | 6.1 | 2 | 65.7 | 30 | 90.00 | 86.66 | +4% | 60.72-128.48 | 0.333 | 15.0 | 4 | 18 | 4 | sparse-delta-basis | 0.4630 | 0.1822 | 0.1236 |
| bourse | Bourse | Vahid Rasouli | BROADCAST_PROGRAM_TITLES | — | 6.85 | cloudflare-stream | 16.04 | 1280x720 | 25.000 | 2.62 | 5.0 | 1 | 62.3 | 16 | 96.00 | 59.84 | +60% | 54.87-155.90 | 0.562 | 9.0 | 2 | 9 | 2 | burst-heavy, short-sample, sparse-delta-basis | 0.6835 | 0.0949 | 0.0927 |
| mashpee | Mashpee | Nana Chen (Yu Jen Chen) | MUSIC_VIDEOS | — | 6.85 | cloudflare-stream | 180.01 | 1280x720 | 29.970 | 1.51 | 32.5 | 4 | 22.2 | 5 | 7.50 | 6.67 | +13% | 2.44-17.50 | 0.000 | 739.5 | 39 | 5 | 39 | low-coverage | 0.2897 | 0.7250 | 0.0779 |
| natgeo-worlds-deadliest-bite | NatGeo World's Deadliest Bite | penmouse | BROADCAST_PROGRAM_TITLES | — | 6.85 | cloudflare-stream | 87.08 | 1280x720 | 30.000 | 4.58 | 47.5 | 4 | 45.9 | 42 | 63.00 | 65.46 | -4% | 42.93-88.28 | 0.476 | 23.0 | 16 | 28 | 16 | — | 0.3458 | 0.4950 | 0.2069 |
| weproc | Weproc | Moonky | ADVERTISING_COMMERCIALS | — | 6.85 | cloudflare-stream | 68.29 | 1280x720 | 30.000 | 1.24 | 10.1 | 4 | 58.6 | 13 | 19.50 | 25.48 | -23% | 10.38-33.35 | 0.154 | 56.5 | 34 | 10 | 34 | — | 0.6277 | 0.2611 | 0.1317 |
| dreams-1 | Dreams | RENDER Entertainment | SHORT_FILMS | — | 6.84 | cloudflare-stream | 34.88 | 1080x1920 | 30.000 | 2.44 | 10.1 | 3 | 86.0 | 0 | 0.00 | 0.00 | — | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.2236 | 0.7179 | 0.0096 |
| freeforms-25-days-of-christmas-1 | Freeform's 25 Days of Christmas | ROVE | BROADCAST_CHANNEL_BRANDING | — | 6.84 | cloudflare-stream | 5.05 | 1280x720 | 23.976 | 1.98 | 1.2 | 1 | 79.2 | 0 | 0.00 | 0.00 | — | 0.00-55.34 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.3870 | 0.5740 | 0.1370 |
| unum-2024-unwrapped | UNUM 2024 Unwrapped | RENDER Entertainment | ADVERTISING_CAMPAIGNS | — | 6.84 | cloudflare-stream | 35.04 | 1080x1920 | 30.000 | 2.42 | 10.1 | 3 | 85.6 | 3 | 6.00 | 6.85 | -12% | 1.24-17.53 | 0.000 | 206.0 | 30 | 3 | 30 | — | 0.6113 | 0.1192 | 0.1474 |
| as-you-go | As-You-Go | Vendredi Society | ADVERTISING_CAMPAIGNS | — | 6.83 | cloudflare-stream | 45.89 | 1280x720 | 30.000 | 1.57 | 8.6 | 4 | 87.2 | 26 | 39.00 | 36.61 | +7% | 25.48-57.14 | 0.231 | 33.0 | 23 | 21 | 23 | — | 0.5837 | 0.3932 | 0.1770 |
| balenciaga-track-1-trainer | Balenciaga - Track 1 Trainer | Renderologists | ADVERTISING_COMMERCIALS | — | 6.83 | cloudflare-stream | 24.71 | 480x858 | 30.000 | 0.82 | 2.4 | 2 | 80.9 | 24 | 72.00 | 75.28 | -4% | 46.13-107.13 | 0.792 | 4.0 | 12 | 10 | 12 | burst-heavy | 0.3197 | 0.4995 | 0.0545 |
| rock-roll-goes-in-circles | nomad. | Aaryan Khakan | MUSIC_VIDEOS | — | 6.83 | cloudflare-stream | 169.15 | 1280x720 | 29.970 | 0.87 | 17.6 | 4 | 23.6 | 13 | 19.50 | 26.96 | -28% | 9.07-35.33 | 0.308 | 70.0 | 34 | 10 | 34 | low-coverage | 0.4218 | 0.3048 | 0.0440 |
| bai-a-complete-product-walkthrough | B.AI Official Complete Guide | TRON | EXPLANATORY_VIDEO | — | 6.82 | cloudflare-stream | 86.08 | 1280x720 | 60.000 | 1.16 | 11.9 | 4 | 46.5 | 10 | 15.00 | 15.33 | -2% | 5.55-30.24 | 0.000 | 134.0 | 35 | 9 | 35 | — | 0.7863 | 0.0852 | 0.0399 |
| breaking-the-chain-a-cinematic-tribute-to-earth-day-2026-1 | Breaking the Chain: Earth Day 2026 Concept | Artily | SELF_BRANDING | — | 6.81 | cloudflare-stream | 67.56 | 1280x720 | 29.970 | 0.29 | 2.3 | 4 | 59.2 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.0197 | 0.0115 | 0.0217 |
| showreel-2 | SHOWREEL | mohamedjozef | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.81 | cloudflare-stream | 70.38 | 1280x720 | 25.000 | 3.08 | 25.8 | 4 | 56.8 | 49 | 73.50 | 75.02 | -2% | 50.16-102.39 | 0.245 | 17.5 | 11 | 33 | 11 | — | 0.4026 | 0.4631 | 0.2207 |
| leader-miljuschka-in-mexico | Leader Miljuschka in Mexico | The Walt Disney Company | BROADCAST_PROGRAM_TITLES | — | 6.80 | cloudflare-stream | 73.64 | 1280x720 | 25.000 | 4.00 | 35.1 | 4 | 54.3 | 34 | 51.00 | 47.26 | +8% | 25.96-83.36 | 0.000 | 23.0 | 13 | 31 | 13 | — | 0.4516 | 0.3490 | 0.1603 |
| sky-sport-redesign-sports-formats | SKY Sport / Redesign Sports Formats | Aixsponza | BROADCAST_CHANNEL_BRANDING | — | 6.80 | cloudflare-stream | 40.02 | 1280x720 | 25.000 | 3.45 | 16.4 | 3 | 75.0 | 11 | 22.00 | 22.49 | -2% | 10.98-39.36 | 0.000 | 62.5 | 22 | 11 | 22 | — | 0.5981 | 0.3982 | 0.2414 |
| cosmo-journey | Cosmic Journey | Ray Chen | SHORT_FILMS | — | 6.79 | cloudflare-stream | 26.43 | 1280x720 | 24.000 | 1.37 | 4.3 | 2 | 75.7 | 3 | 9.00 | 6.81 | +32% | 1.86-26.30 | 0.000 | 218.5 | 19 | 3 | 19 | — | 0.3584 | 0.7393 | 0.1772 |
| teka-built-in-max-series | TEKA Built-in Max Series | KUTUKO STUDIO | ADVERTISING_COMMERCIALS | — | 6.79 | cloudflare-stream | 56.34 | 1280x720 | 25.000 | 1.33 | 8.9 | 4 | 71.0 | 16 | 24.00 | 21.30 | +13% | 13.72-38.97 | 0.000 | 54.0 | 28 | 16 | 28 | — | 0.4756 | 0.2837 | 0.1038 |
| 0800 | 08:00 | Nikeepon | SHORT_FILMS | — | 6.78 | cloudflare-stream | 60.07 | 1080x1080 | 25.000 | 1.65 | 11.8 | 4 | 66.6 | 9 | 13.50 | 11.99 | +13% | 4.25-28.80 | 0.000 | 97.5 | 35 | 9 | 35 | — | 0.2979 | 0.5156 | 0.0474 |
| aphex-twin-4 | Aphex Twin—4 | Elena Pogulyaeva | MUSIC_VIDEOS | — | 6.78 | cloudflare-stream | 122.37 | 1280x720 | 24.000 | 4.73 | 69.0 | 4 | 32.7 | 20 | 30.00 | 51.48 | -42% | 11.91-55.30 | 0.550 | 9.0 | 34 | 10 | 34 | burst-heavy | 0.1935 | 0.2546 | 0.2089 |
| reconnect-through-music-ministry-of-sound-1 | Reconnect Through Music -  Ministry of Sound | Dazzle Ship | ADVERTISING_COMMERCIALS | — | 6.78 | cloudflare-stream | 30.02 | 1280x720 | 25.000 | 3.93 | 14.1 | 2 | 66.6 | 5 | 15.00 | 19.98 | -25% | 4.87-35.00 | 0.400 | 63.0 | 18 | 4 | 18 | — | 0.3794 | 0.5403 | 0.1994 |
| spiritual-birth | Spiritual Birth | Melinda Mouzannar | MUSIC_VIDEOS | — | 6.78 | direct-mp4 | 62.53 | 1920x1080 | 30.000 | 12.48 | 93.0 | 4 | 64.0 | 18 | 27.00 | 26.87 | +0% | 9.80-51.50 | 0.944 | 5.0 | 38 | 6 | 38 | burst-heavy | 0.0154 | 0.0719 | 0.0229 |
| global-workforce | Global WorkForce | RENDER Entertainment | BROADCAST_SERIES_TITLES | — | 6.77 | cloudflare-stream | 32.32 | 1280x720 | 30.000 | 1.42 | 5.5 | 2 | 61.9 | 3 | 9.00 | 7.43 | +21% | 1.86-26.30 | 0.000 | 345.5 | 19 | 3 | 19 | — | 0.0719 | 0.5216 | 0.0364 |
| shangxia-dragon-years-campaign | SHANGXIA Dragon Year's Campaign | clumsy hands | ADVERTISING_CAMPAIGNS | — | 6.77 | cloudflare-stream | 37.33 | 1280x720 | 10.000 | 1.07 | 4.8 | 3 | 80.4 | 0 | 0.00 | 0.00 | — | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.7235 | 0.3114 | 0.0817 |
| the-palace-of-illusions | The Palace of Illusions | Khrusha Parekh | TITLE_SEQUENCES | — | 6.77 | cloudflare-stream | 49.73 | 1280x720 | 29.970 | 0.46 | 2.7 | 4 | 80.4 | 1 | 1.50 | 1.21 | +24% | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.6105 | 0.5679 | 0.0366 |
| augmented-reality-blade-runner-ost-cover | Augmented Reality BLADE RUNNER ost cover | Mauro Mason | INSTALLATION_PROJECTION_EXPERIENCE | — | 6.76 | cloudflare-stream | 56.04 | 1280x720 | 25.000 | 3.63 | 24.3 | 4 | 71.4 | 1 | 1.50 | 2.14 | -30% | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.2568 | 0.4499 | 0.1117 |
| odi-odi | Odi Odi | Mozmene | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.74 | cloudflare-stream | 12.05 | 1280x720 | 24.000 | 3.36 | 4.8 | 1 | 83.0 | 17 | 102.00 | 84.62 | +21% | 59.42-163.31 | 0.765 | 5.0 | 4 | 7 | 4 | burst-heavy, short-sample, sparse-delta-basis | 0.5006 | 0.5325 | 0.0851 |
| washing-machine-cgi-commercial | Washing Machine CGI Product Commercial | Snoll Visuals | ADVERTISING_COMMERCIALS | — | 6.74 | cloudflare-stream | 23.98 | 1280x720 | 30.000 | 3.18 | 9.1 | 2 | 83.4 | 10 | 30.00 | 25.02 | +20% | 14.39-55.17 | 0.400 | 47.0 | 14 | 8 | 14 | — | 0.3957 | 0.2674 | 0.2002 |
| cmykenn-motion-reel-2025 | CMYKenn - Motion Reel 2025 | CMYKenn - John Kenneth Zapata | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.73 | cloudflare-stream | 73.62 | 1280x720 | 23.976 | 2.94 | 25.8 | 4 | 54.3 | 48 | 72.00 | 70.90 | +2% | 50.16-99.09 | 0.208 | 13.0 | 12 | 32 | 12 | — | 0.3879 | 0.4944 | 0.2281 |
| pieces-of-me | Pieces of Me | Susanna Tung | SELF_BRANDING | — | 6.73 | cloudflare-stream | 33.49 | 1280x720 | 29.970 | 3.13 | 12.5 | 3 | 89.6 | 20 | 40.00 | 35.83 | +12% | 0.00-110.23 | 0.850 | 5.0 | 26 | 7 | 26 | burst-heavy | 0.2689 | 0.1883 | 0.1221 |
| the-us-is-missing-out-on-walkable-cities | The US is Missing Out on Walkable Cities | Quang Dao | EXPLANATORY_VIDEO | — | 6.72 | cloudflare-stream | 68.89 | 1280x720 | 30.000 | 1.21 | 9.9 | 4 | 58.1 | 40 | 60.00 | 40.07 | +50% | 0.81-134.97 | 1.000 | 2.0 | 36 | 8 | 36 | burst-heavy, non-edit-scene-change | 0.6307 | 0.4032 | 0.0531 |
| halography-opening-title-sequence | Halography Opening Title Sequence | BALANCE | LIVE_EVENT_TITLES | — | 6.71 | direct-mp4 | 80.00 | 2048x838 | 25.000 | 3.47 | 33.1 | 4 | 50.0 | 10 | 15.00 | 12.75 | +18% | 0.19-38.88 | 0.600 | 10.0 | 38 | 6 | 38 | burst-heavy | 0.1800 | 0.1807 | 0.0463 |
| i-choose-violence | I Choose Violence | ArtofZink | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.71 | cloudflare-stream | 13.97 | 608x1080 | 29.970 | 1.00 | 1.7 | 1 | 71.6 | 25 | 150.00 | 154.58 | -3% | 97.07-221.43 | 0.800 | 3.0 | 2 | 9 | 2 | burst-heavy, short-sample, sparse-delta-basis | 0.2089 | 0.5690 | 0.2629 |
| hnbmg-5-years-anniversary-1 | #HNBMG 5 Years Anniversary | DGRBOX | ADVERTISING_COMMERCIALS | — | 6.70 | cloudflare-stream | 15.02 | 1280x720 | 30.000 | 3.58 | 6.4 | 1 | 66.6 | 4 | 24.00 | 31.95 | -25% | 6.54-61.45 | 0.000 | 66.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.1687 | 0.2856 | 0.0727 |
| japanese-ammo | Japanese Ammo | Mozmene | BROADCAST_PROGRAM_TITLES | — | 6.70 | cloudflare-stream | 9.83 | 1280x720 | 30.000 | 5.99 | 7.0 | 1 | 81.3 | 0 | 0.00 | 0.00 | — | 0.00-27.67 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.7932 | 0.3336 | 0.0913 |
| my-gravity-girls-blank-space | My Gravity Girls - Blank Space | The Beard Hunter | MUSIC_VIDEOS | — | 6.70 | cloudflare-stream | 164.03 | 1146x480 | 24.000 | 1.93 | 37.7 | 4 | 24.4 | 14 | 21.00 | 25.24 | -17% | 5.18-44.66 | 0.000 | 50.0 | 32 | 12 | 32 | low-coverage | 0.6644 | 0.1339 | 0.0565 |
| edpon-app | edpON app | Itsanashow Creative Studio | EXPLANATORY_VIDEO | — | 6.67 | cloudflare-stream | 61.03 | 1280x720 | 25.000 | 3.10 | 22.6 | 4 | 65.5 | 12 | 18.00 | 13.76 | +31% | 9.30-31.44 | 0.000 | 76.0 | 33 | 11 | 33 | — | 0.5341 | 0.2745 | 0.1317 |
| takeone-in-place-motion-mv | TakeOne - In place Motion M/V | UNUSUAL | FILM_GRAPHICS | — | 6.65 | cloudflare-stream | 73.61 | 1280x720 | 29.970 | 3.30 | 28.9 | 4 | 54.3 | 20 | 30.00 | 27.71 | +8% | 13.49-53.10 | 0.300 | 30.0 | 29 | 15 | 29 | — | 0.4239 | 0.1719 | 0.1375 |
| httpsvimeocom748777370 | https://vimeo.com/748777370 | Wonderbloom | EXPLANATORY_VIDEO | — | 6.64 | cloudflare-stream | 113.02 | 1280x720 | 25.000 | 0.79 | 10.6 | 4 | 35.4 | 4 | 6.00 | 4.78 | +26% | 0.00-24.72 | 0.000 | 38.0 | 40 | 4 | 40 | — | 0.7725 | 0.3237 | 0.0879 |
| junge-akademie-1 | Junge Akademie | navos create | ADVERTISING_CAMPAIGNS | — | 6.64 | cloudflare-stream | 42.67 | 1280x720 | 24.000 | 3.77 | 19.2 | 3 | 70.3 | 5 | 10.00 | 16.88 | -41% | 0.00-31.50 | 0.400 | 86.0 | 29 | 4 | 29 | — | 0.6849 | 0.2750 | 0.0989 |
| horizon | Horizon | Miran Kevic | ADVERTISING_COMMERCIALS | — | 6.62 | cloudflare-stream | 55.70 | 1280x720 | 30.000 | 3.73 | 24.8 | 4 | 71.8 | 3 | 4.50 | 3.23 | +39% | 0.55-14.06 | 0.000 | 184.5 | 41 | 3 | 41 | — | 0.1187 | 0.7293 | 0.0788 |
| kuht-er | KUHT-ER | Vorz Lab | ADVERTISING_COMMERCIALS | — | 6.58 | cloudflare-stream | 10.03 | 1280x720 | 24.000 | 3.29 | 3.9 | 1 | 89.8 | 0 | 0.00 | 0.00 | — | 0.00-24.59 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.0901 | 0.3136 | 0.0844 |
| merry-christmas | Merry Christmas | RENDER Entertainment | ADVERTISING_COMMERCIALS | — | 6.57 | cloudflare-stream | 22.94 | 1080x1920 | 30.000 | 1.51 | 4.1 | 2 | 87.2 | 1 | 3.00 | 2.62 | +15% | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.2813 | 0.1355 | 0.0392 |
| samsara | SAṂSĀRA | Sobe Okoye | SHORT_FILMS | — | 6.57 | cloudflare-stream | 231.87 | 1280x720 | 24.000 | 1.68 | 46.5 | 4 | 17.3 | 1 | 1.50 | 3.11 | -52% | 0.04-8.36 | — | — | 43 | 1 | 43 | low-coverage | 0.0426 | 0.5925 | 0.0265 |
| skate-loop-1 | Skate Loop | Elias Velho | EXPERIMENTAL | — | 6.57 | cloudflare-stream | 7.83 | 1280x720 | 24.000 | 2.94 | 2.7 | 1 | 89.4 | 6 | 51.43 | 45.96 | +12% | 18.87-111.94 | 1.000 | 2.0 | 9 | 2 | 9 | burst-heavy, non-edit-scene-change, short-sample | 0.6216 | 0.4486 | 0.0424 |
| invisibles | Invisibles | Suppa! Studio | SHORT_FILMS | — | 6.56 | cloudflare-stream | 177.08 | 1280x720 | 24.000 | 3.46 | 73.0 | 4 | 22.6 | 5 | 7.50 | 7.12 | +5% | 2.44-17.50 | 0.000 | 567.0 | 39 | 5 | 39 | low-coverage | 0.2131 | 0.5668 | 0.0419 |
| di-punto-in-bianco-1 | Di punto in bianco | Davide Morelli | MUSIC_VIDEOS | — | 6.55 | cloudflare-stream | 60.03 | 720x720 | 30.000 | 1.93 | 13.8 | 4 | 66.6 | 6 | 9.00 | 9.00 | +0% | 0.94-23.98 | 0.000 | 42.0 | 39 | 5 | 39 | — | 0.1294 | 0.0000 | 0.0938 |
| toss-money-card | Toss Money Card | N.lee | ADVERTISING_COMMERCIALS | — | 6.55 | cloudflare-stream | 43.11 | 1280x720 | 29.970 | 1.21 | 6.2 | 3 | 69.6 | 4 | 8.00 | 5.57 | +44% | 2.18-20.48 | 0.000 | 66.0 | 29 | 4 | 29 | — | 0.8444 | 0.2017 | 0.0852 |
| kontroll | Kontroll | playerfh | EXPERIMENTAL | — | 6.54 | cloudflare-stream | 261.03 | 1280x720 | 25.000 | 3.49 | 108.7 | 4 | 15.3 | 72 | 108.00 | 65.05 | +66% | 0.00-308.02 | 0.986 | 2.0 | 31 | 13 | 31 | burst-heavy, low-coverage, non-edit-scene-change | 0.3737 | 0.2441 | 0.1213 |
| stay-home | Stay Home | Arnaud LAFFOND | SHORT_FILMS | — | 6.54 | direct-mp4 | 249.92 | 1920x1080 | 25.000 | 9.43 | 280.8 | 4 | 16.0 | 8 | 12.00 | 16.33 | -26% | 5.18-23.64 | 0.000 | 96.0 | 36 | 8 | 36 | low-coverage | 0.4835 | 0.4610 | 0.0315 |
| waves | waves | Azeemu Zaman | EXPERIMENTAL | — | 6.54 | cloudflare-stream | 24.26 | 638x360 | 30.000 | 0.24 | 0.7 | 2 | 82.4 | 0 | 0.00 | 0.00 | — | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.3437 | 0.1440 | 0.0656 |
| ai-text-intro | AI Text Intro | MotionRam | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.52 | cloudflare-stream | 25.09 | 1280x720 | 30.000 | 0.86 | 2.6 | 2 | 79.7 | 6 | 18.00 | 14.35 | +25% | 6.61-39.18 | 0.333 | 61.0 | 16 | 6 | 16 | — | 0.6052 | 0.3629 | 0.0735 |
| comertial-fake-gameplay-for-mobile-game-1 | Commercial fake gameplay for mobile game | Jimbo_Des | GAME_TITLES | — | 6.52 | cloudflare-stream | 29.99 | 1280x720 | 30.000 | 4.48 | 16.0 | 2 | 66.7 | 1 | 3.00 | 10.00 | -70% | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.4457 | 0.3109 | 0.1819 |
| fate | Fate | RENDER Entertainment | BROADCAST_SERIES_TITLES | — | 6.52 | cloudflare-stream | 21.06 | 1080x1920 | 30.000 | 4.18 | 10.5 | 1 | 47.5 | 1 | 6.00 | 11.40 | -47% | 0.15-33.43 | — | — | 10 | 1 | 10 | short-sample | 0.4721 | 0.3475 | 0.1098 |
| porsche-at-road | Porsche at road | alanomoxo | SHORT_FILMS | — | 6.52 | cloudflare-stream | 9.91 | 720x1280 | 24.033 | 1.81 | 2.1 | 1 | 80.7 | 0 | 0.00 | 0.00 | — | 0.00-27.67 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.0949 | 0.6472 | 0.1457 |
| whispering-winds-warring-souls | Whispering Winds, Warring Souls | Jiaxin Wu | SELF_BRANDING | — | 6.52 | cloudflare-stream | 17.60 | 1080x1920 | 25.000 | 1.35 | 2.8 | 1 | 56.8 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.1860 | 0.5944 | 0.0069 |
| flodesk-case-study | FloDesk Case Study | RENDER Entertainment | ADVERTISING_CAMPAIGNS | — | 6.50 | cloudflare-stream | 56.55 | 1080x1920 | 30.000 | 3.60 | 24.3 | 4 | 70.7 | 1 | 1.50 | 1.06 | +41% | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.4858 | 0.3031 | 0.0501 |
| legacy-meets-innovation | Legacy Meets Innovation | Shrinkwrap studio | ADVERTISING_CAMPAIGNS | — | 6.50 | cloudflare-stream | 13.74 | 1196x480 | 23.976 | 0.68 | 1.1 | 1 | 72.8 | 5 | 30.00 | 21.84 | +37% | 9.74-70.01 | 0.000 | 18.0 | 6 | 5 | 6 | short-sample, sparse-delta-basis | 0.5695 | 0.2265 | 0.1022 |
| being-a-crab-emojis | Being a Crab - Emojis | Joseph Lattimer | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.49 | cloudflare-stream | 48.45 | 1080x1080 | 24.000 | 4.96 | 28.7 | 4 | 82.6 | 3 | 4.50 | 3.72 | +21% | 0.55-14.06 | 0.000 | 185.5 | 41 | 3 | 41 | — | 0.3821 | 0.8943 | 0.0790 |
| video-remake-of-the-google-deepmind-veo-v3-explaine | Video Remake of the Google DeepMind Veo3 Explainer | Nazar | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.49 | cloudflare-stream | 25.02 | 1280x720 | 60.000 | 1.64 | 4.9 | 2 | 79.9 | 4 | 12.00 | 14.39 | -17% | 3.27-30.72 | 0.000 | 86.0 | 18 | 4 | 18 | — | 0.2223 | 0.4792 | 0.1381 |
| kaminskyi-brand-elements | Kaminskyi Brand Elements | Peretiatko | BROADCAST_CHANNEL_BRANDING | — | 6.48 | cloudflare-stream | 37.03 | 1280x720 | 24.000 | 3.38 | 14.9 | 3 | 81.0 | 3 | 6.00 | 6.48 | -7% | 1.24-17.53 | 0.000 | 154.0 | 30 | 3 | 30 | — | 0.1401 | 0.3234 | 0.0823 |
| gilbarte-2049 | Gil.Barte — 2049 | Margarita Luchnikova & Evgenia Nikonova | MUSIC_VIDEOS | — | 6.47 | cloudflare-stream | 140.52 | 1280x720 | 30.000 | 2.37 | 39.8 | 4 | 28.5 | 26 | 39.00 | 49.96 | -22% | 14.31-72.13 | 0.769 | 7.0 | 34 | 10 | 34 | burst-heavy | 0.3127 | 0.0000 | 0.1827 |
| iconic-vision-john-parkinson-architect-of-los-angeles-1 | Iconic Vision. John Parkinson, Architect of Los Angeles | Tim Clark | BROADCAST_PROGRAM_TITLES | — | 6.47 | cloudflare-stream | 12.94 | 1280x720 | 25.000 | 1.94 | 3.0 | 1 | 77.3 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.3171 | 0.6078 | 0.1164 |
| moonky | Moonky | Moonky | SELF_BRANDING | — | 6.47 | cloudflare-stream | 68.16 | 1280x720 | 30.000 | 2.01 | 16.3 | 4 | 58.7 | 32 | 48.00 | 49.30 | -3% | 9.83-97.73 | 0.625 | 14.0 | 26 | 18 | 26 | burst-heavy | 0.2405 | 0.4670 | 0.1630 |
| izibox-crash-test | Izibox Crash Test – Pushing the Limits of Protection | Irfane3D | ADVERTISING_COMMERCIALS | — | 6.46 | cloudflare-stream | 45.53 | 1280x720 | 25.000 | 1.99 | 10.8 | 4 | 87.9 | 3 | 4.50 | 3.95 | +14% | 0.55-14.06 | 0.000 | 103.5 | 41 | 3 | 41 | — | 0.3398 | 0.4547 | 0.1843 |
| typo-premium-hard-seltzer-launch-video-1 | Typo - Premium Hard Seltzer Launch Video | Loud Mob Media | ADVERTISING_COMMERCIALS | — | 6.46 | cloudflare-stream | 30.04 | 1280x720 | 30.000 | 1.69 | 6.1 | 2 | 66.6 | 11 | 33.00 | 29.96 | +10% | 16.47-59.05 | 0.000 | 39.5 | 13 | 9 | 13 | — | 0.3479 | 0.6513 | 0.1624 |
| caritas-europa-explained | Caritas Europa explained | Sebastian Temlett | EXPLANATORY_VIDEO | — | 6.45 | cloudflare-stream | 171.03 | 1280x720 | 25.000 | 3.63 | 74.1 | 4 | 23.4 | 0 | 0.00 | 0.35 | -100% | 0.00-5.53 | — | — | 44 | 0 | 44 | low-coverage, no-cuts-observed | 0.8286 | 0.1902 | 0.0615 |
| rockzero-all-in-one-system | Rockzero - Modular All-in-one system | Yellow Umwelt | EXPLANATORY_VIDEO | — | 6.45 | cloudflare-stream | 53.59 | 1280x720 | 30.000 | 0.70 | 4.5 | 4 | 74.6 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.8173 | 0.0479 | 0.0666 |
| be-not-afraid-ezekiel-1 | "Be Not Afraid" ⠀~ Ezekiel 1⠀ | Sage Arts Designs | EXPERIMENTAL | — | 6.44 | cloudflare-stream | 123.58 | 1280x720 | 24.000 | 2.58 | 37.9 | 4 | 32.4 | 4 | 6.00 | 8.25 | -27% | 1.63-15.36 | 0.000 | 707.0 | 40 | 4 | 40 | — | 0.2725 | 0.2606 | 0.1101 |
| coffee-seed | coffee seed | abdalwhab aljabali | ADVERTISING_COMMERCIALS | — | 6.44 | cloudflare-stream | 6.70 | 1280x720 | 24.000 | 0.99 | 0.8 | 1 | 89.6 | 0 | 0.00 | 0.00 | — | 0.00-36.89 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.6867 | 0.1988 | 0.0387 |
| jumpy-cats | Bouncy Cats Union 2020 | Bella Cologlu | SELF_BRANDING | — | 6.44 | cloudflare-stream | 8.38 | 1280x720 | 25.000 | 4.83 | 4.8 | 1 | 83.5 | 3 | 25.71 | 21.47 | +20% | 5.30-75.15 | 0.000 | 36.5 | 8 | 3 | 8 | short-sample | 0.6251 | 0.1903 | 0.3275 |
| wifi-connection-ibiza | Wifi Connection Ibiza | Promokore | ADVERTISING_COMMERCIALS | — | 6.44 | cloudflare-stream | 49.51 | 1280x720 | 25.000 | 3.14 | 18.5 | 4 | 80.8 | 0 | 0.00 | 1.21 | -100% | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.3741 | 0.7766 | 0.0750 |
| dang-lifestyle-richie-rich | Dang Lifestyle - Richie Rich | Hyraki Studios | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.43 | cloudflare-stream | 8.02 | 1280x720 | 24.000 | 2.57 | 2.5 | 1 | 87.3 | 1 | 8.57 | 7.48 | +15% | 0.22-47.76 | — | — | 10 | 1 | 10 | short-sample | 0.8026 | 0.1264 | 0.0868 |
| biokarpet | BIOKARPET | dotmov | ADVERTISING_COMMERCIALS | — | 6.42 | cloudflare-stream | 16.92 | 1280x720 | 25.000 | 2.66 | 5.4 | 1 | 59.1 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.8084 | 0.2120 | 0.0619 |
| coffee-and-contemplation | Coffee and Contemplation | AshishGJ | EXPERIMENTAL | — | 6.42 | cloudflare-stream | 22.07 | 608x1080 | 30.000 | 0.61 | 1.6 | 1 | 45.3 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.5636 | 0.2275 | 0.0167 |
| automotive-animation-in-unreal-engine-5 | Revolution in Motion - Unreal Engine 5 | Nako Baev | ADVERTISING_CAMPAIGNS | — | 6.41 | cloudflare-stream | 48.90 | 1280x720 | 30.000 | 2.80 | 16.3 | 4 | 81.8 | 31 | 46.50 | 41.72 | +11% | 0.00-123.75 | 0.710 | 1.5 | 33 | 11 | 33 | burst-heavy, non-edit-scene-change | 0.2089 | 0.1067 | 0.1474 |
| frank-riggio-tttt | Frank Riggio - TTTT | MERT KIZILAY | EXPERIMENTAL | — | 6.41 | direct-mp4 | 236.35 | 1920x1080 | 23.976 | 3.83 | 108.0 | 4 | 16.9 | 1 | 1.50 | 4.57 | -67% | 0.04-8.36 | — | — | 43 | 1 | 43 | low-coverage | 0.1403 | 0.1109 | 0.1050 |
| springsummer-2030-bikeswear | SPRING/SUMMER 2030 BIKESWEAR | korolooove | EXPERIMENTAL | — | 6.41 | cloudflare-stream | 10.84 | 606x1080 | 25.000 | 3.00 | 3.9 | 1 | 83.0 | 5 | 33.33 | 27.68 | +20% | 10.82-77.79 | 0.800 | 7.5 | 9 | 2 | 9 | burst-heavy, short-sample | 0.2466 | 0.4893 | 0.1793 |
| loujey-zidi-2d-animation-intro | Loujey Zidi - 2D Animation intro | Ahmed Bellagha | BROADCAST_CHANNEL_BRANDING | — | 6.40 | cloudflare-stream | 7.51 | 608x1080 | 30.000 | 4.67 | 4.2 | 1 | 79.9 | 12 | 120.00 | 95.88 | +25% | 62.01-209.62 | 0.333 | 12.0 | 2 | 9 | 2 | short-sample, sparse-delta-basis | 0.3566 | 0.6806 | 0.1150 |
| chinatown | ChinaTown | RENDER Entertainment | SHORT_FILMS | — | 6.39 | cloudflare-stream | 35.03 | 1126x480 | 30.000 | 0.99 | 4.1 | 3 | 85.6 | 1 | 2.00 | 1.71 | +17% | 0.05-11.14 | — | — | 32 | 1 | 32 | — | 0.3961 | 0.1000 | 0.1049 |
| move-until-youre-numbq | Move Until You're Numb | Melinda Mouzannar | MUSIC_VIDEOS | — | 6.39 | cloudflare-stream | 67.73 | 1280x720 | 24.000 | 3.77 | 30.4 | 4 | 59.1 | 0 | 0.00 | 3.54 | -100% | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.2058 | 0.3874 | 0.0874 |
| prada-perfum | Prada Black Perfum | alanomoxo | ADVERTISING_COMMERCIALS | — | 6.39 | cloudflare-stream | 10.85 | 720x1280 | 24.000 | 2.28 | 2.9 | 1 | 83.0 | 12 | 80.00 | 99.58 | -20% | 41.34-139.74 | 0.833 | 3.0 | 6 | 5 | 6 | burst-heavy, short-sample, sparse-delta-basis | 0.3058 | 0.0000 | 0.1530 |
| cyberpunk-2088 | Cyberpunk 2088 | Artanastasio | EXPERIMENTAL | — | 6.38 | cloudflare-stream | 13.90 | 1088x1080 | 30.000 | 6.56 | 10.9 | 1 | 71.9 | 0 | 0.00 | 25.90 | -100% | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.1071 | 0.5831 | 0.0783 |
| kraft-heinz-supply-chain-management-from-styleframes-to-finals | KRAFT HEINZ \| SUPPLY CHAIN MANAGEMENT \| from styleframes to finals | penmouse | EXPLANATORY_VIDEO | — | 6.38 | cloudflare-stream | 75.08 | 1280x720 | 24.000 | 1.35 | 12.1 | 4 | 53.3 | 19 | 28.50 | 27.17 | +5% | 14.81-47.81 | 0.000 | 31.5 | 25 | 19 | 25 | — | 0.7433 | 0.1857 | 0.1356 |
| showreel | Main Title Sequence | Ayan | BROADCAST_SERIES_TITLES | — | 6.38 | cloudflare-stream | 21.46 | 1280x720 | 25.000 | 2.45 | 6.3 | 1 | 46.6 | 3 | 18.00 | 16.77 | +7% | 3.71-52.60 | 0.000 | 90.0 | 8 | 3 | 8 | short-sample | 0.5376 | 0.0916 | 0.0991 |
| mobile-activity-shape-tables | Heavy Duty Activity Shape Tables | National Public Seating | ADVERTISING_CAMPAIGNS | — | 6.36 | cloudflare-stream | 41.94 | 1280x720 | 25.000 | 0.26 | 1.3 | 3 | 71.5 | 0 | 0.00 | 0.00 | — | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.9393 | 0.0476 | 0.0478 |
| sound-world | Sound world | MadebyDebo | ADVERTISING_COMMERCIALS | — | 6.36 | cloudflare-stream | 47.25 | 1280x720 | 24.000 | 2.56 | 14.4 | 4 | 84.7 | 16 | 24.00 | 21.59 | +11% | 11.41-42.34 | 0.125 | 49.0 | 29 | 15 | 29 | — | 0.4080 | 0.4139 | 0.0801 |
| astro-man | ASTRO - MAN | Javich & Co. | SELF_BRANDING | — | 6.34 | cloudflare-stream | 31.70 | 1280x720 | 24.000 | 2.21 | 8.3 | 2 | 63.1 | 0 | 0.00 | 0.00 | — | 0.00-11.07 | — | — | 22 | 0 | 22 | no-cuts-observed | 0.2469 | 0.0760 | 0.0841 |
| emaar-super-cup | Emaar Super Cup | shukoor | BROADCAST_PROGRAM_TITLES | — | 6.33 | cloudflare-stream | 13.10 | 1280x720 | 25.000 | 1.40 | 2.2 | 1 | 76.3 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.1748 | 0.0828 | 0.0525 |
| unfamiliar-landscapes | Unfamiliar Landscapes | J.T.Child | EXPERIMENTAL | — | 6.32 | cloudflare-stream | 139.03 | 1150x480 | 25.000 | 1.72 | 28.6 | 4 | 28.8 | 16 | 24.00 | 23.30 | +3% | 10.08-44.28 | 0.688 | 9.0 | 35 | 9 | 35 | burst-heavy | 0.2026 | 0.6424 | 0.0429 |
| catharsis-2 | CATHARSIS | Barbara Gian | SHORT_FILMS | — | 6.30 | cloudflare-stream | 80.04 | 1280x720 | 30.000 | 0.78 | 7.4 | 4 | 50.0 | 2 | 3.00 | 5.25 | -43% | 0.00-14.08 | 0.000 | 134.0 | 42 | 2 | 42 | — | 0.2355 | 0.6838 | 0.0502 |
| wilson-enterprise-4330 | Wilson Enterprise 4330 | Shrinkwrap studio | ADVERTISING_CAMPAIGNS | — | 6.28 | cloudflare-stream | 19.54 | 1280x720 | 23.976 | 0.39 | 0.9 | 1 | 51.2 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.0280 | 0.1040 | 0.0401 |
| adidas-james-rodriguez | Adidas - James Rodriguez | Sugar Blood / Pedro Allevato | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.27 | cloudflare-stream | 10.67 | 1280x720 | 24.000 | 3.87 | 4.9 | 1 | 84.4 | 11 | 73.33 | 67.50 | +9% | 36.61-131.21 | 0.818 | 2.0 | 6 | 5 | 6 | burst-heavy, non-edit-scene-change, short-sample, sparse-delta-basis | 0.1817 | 0.7088 | 0.1057 |
| vibe-aliens-vr-experience | Vibe Aliens VR Experience | Die-Jay-Cee | INSTALLATION_PROJECTION_EXPERIENCE | — | 6.25 | cloudflare-stream | 34.33 | 1280x720 | 24.000 | 3.82 | 15.6 | 3 | 87.4 | 11 | 22.00 | 19.23 | +14% | 10.02-40.88 | 0.364 | 59.5 | 25 | 8 | 25 | — | 0.3429 | 0.7644 | 0.2295 |
| x-bolt-2-speed | X-bolt 2 Speed | Shrinkwrap studio | ADVERTISING_CAMPAIGNS | — | 6.25 | cloudflare-stream | 32.04 | 1280x720 | 24.000 | 1.30 | 5.0 | 2 | 62.4 | 5 | 15.00 | 11.23 | +34% | 4.87-35.00 | 0.000 | 96.0 | 17 | 5 | 17 | — | 0.3011 | 0.1487 | 0.1345 |
| young-marketers-2 | Young Marketers | DGRBOX | LIVE_EVENT_TITLES | — | 6.25 | cloudflare-stream | 96.66 | 1280x720 | 30.000 | 3.48 | 40.2 | 4 | 41.4 | 10 | 15.00 | 8.07 | +86% | 1.94-36.06 | 0.800 | 3.0 | 37 | 7 | 37 | burst-heavy | 0.1554 | 0.4621 | 0.0577 |
| everyday-waves | Everyday waves | Rogério Rolo | SHORT_FILMS | — | 6.24 | cloudflare-stream | 60.12 | 1280x720 | 29.970 | 0.68 | 4.8 | 4 | 66.5 | 65 | 97.50 | 71.86 | +36% | 48.05-156.99 | 0.954 | 3.0 | 29 | 15 | 29 | burst-heavy | 0.5089 | 0.4976 | 0.1323 |
| dreamdoor | DREAM.DOOR | DGRBOX | ADVERTISING_COMMERCIALS | — | 6.23 | cloudflare-stream | 42.07 | 1280x720 | 30.000 | 2.82 | 14.1 | 3 | 71.3 | 19 | 38.00 | 29.95 | +27% | 22.88-59.34 | 0.316 | 38.0 | 18 | 15 | 18 | — | 0.2330 | 0.1672 | 0.1708 |
| speed-chord | Speedchord | UNI_VERSE | MUSIC_VIDEOS | — | 6.20 | cloudflare-stream | 267.22 | 1280x720 | 30.000 | 2.86 | 91.1 | 4 | 15.0 | 9 | 13.50 | 20.88 | -35% | 0.00-40.21 | 0.778 | 3.0 | 41 | 3 | 41 | burst-heavy, low-coverage | 0.2299 | 0.6277 | 0.1583 |
| threatened-planet | Threatened Planet | Ismail Shaker | EXPERIMENTAL | — | 6.20 | cloudflare-stream | 118.51 | 1280x720 | 25.000 | 1.19 | 16.8 | 4 | 33.8 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.2751 | 0.4154 | 0.0506 |
| no-escape-1 | No Escape | GtotheWALL | EXPERIMENTAL | — | 6.19 | cloudflare-stream | 64.55 | 1280x720 | 29.970 | 4.22 | 32.5 | 4 | 62.0 | 28 | 42.00 | 44.61 | -6% | 13.48-79.85 | 0.536 | 12.0 | 30 | 14 | 30 | burst-heavy | 0.2647 | 0.4728 | 0.1530 |
| freedom | Freedom | Osama Homs | SELF_BRANDING | — | 6.17 | cloudflare-stream | 21.55 | 1280x720 | 30.000 | 3.27 | 8.4 | 1 | 46.4 | 3 | 18.00 | 13.92 | +29% | 3.71-52.60 | 0.000 | 87.5 | 8 | 3 | 8 | short-sample | 0.2897 | 0.6469 | 0.1865 |
| istanbul | İstanbul | Ulaş Erdoğan | EXPERIMENTAL | — | 6.17 | cloudflare-stream | 18.03 | 1080x1080 | 25.000 | 5.16 | 11.1 | 1 | 55.5 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.1802 | 0.3143 | 0.0455 |
| httpsvimeocom316586329 | Dolce life | hugonzalez | ADVERTISING_COMMERCIALS | — | 6.12 | cloudflare-stream | 16.02 | 1280x720 | 25.000 | 1.54 | 2.9 | 1 | 62.4 | 1 | 6.00 | 3.75 | +60% | 0.15-33.43 | — | — | 10 | 1 | 10 | short-sample | 0.1467 | 0.2723 | 0.0555 |
| erklarvideo-laurenzdigital | Erklärvideo laurenzdigital | laurenzdigital | EXPLANATORY_VIDEO | — | 6.08 | cloudflare-stream | 77.70 | 1280x720 | 30.000 | 2.43 | 22.5 | 4 | 51.5 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.8347 | 0.1544 | 0.0365 |
| nobo-loaded-pumpkin | Nobo Loaded Pumpkin | Apetown Art | ADVERTISING_SOCIAL_MEDIA_ADS | — | 6.00 | cloudflare-stream | 15.04 | 1080x1080 | 30.000 | 1.89 | 3.4 | 1 | 66.5 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.2582 | 0.4452 | 0.0819 |
| black-white | Black & White | Nico Schilling | EXPERIMENTAL | — | 5.99 | cloudflare-stream | 14.87 | 1280x720 | 25.000 | 2.15 | 3.8 | 1 | 67.3 | 5 | 30.00 | 24.21 | +24% | 9.74-70.01 | 0.400 | 20.0 | 7 | 4 | 7 | short-sample, sparse-delta-basis | 0.1668 | 0.0000 | 0.0692 |
| wires-1 | WIRES | Andrey Davlikanov | TITLE_SEQUENCES | — | 5.99 | cloudflare-stream | 80.00 | 1280x720 | 30.000 | 3.34 | 31.9 | 4 | 50.0 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.0700 | 0.2676 | 0.0333 |
| 72-and-sunny | 72 and Sunny | Joost Korngold | SELF_BRANDING | — | 5.97 | direct-mp4 | 51.70 | 1080x1080 | 30.000 | 12.09 | 74.5 | 4 | 77.4 | 0 | 0.00 | 0.00 | — | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.7782 | 0.2959 | 0.0126 |
| jera-capital-another-way-into-private-equity | Jera Capital - Another Way Into Private Equity | Yellow Umwelt | ADVERTISING_CAMPAIGNS | — | 5.95 | cloudflare-stream | 140.59 | 1280x720 | 25.000 | 1.53 | 25.6 | 4 | 28.5 | 9 | 13.50 | 15.36 | -12% | 0.65-34.76 | 0.000 | 60.5 | 35 | 9 | 35 | — | 0.4869 | 0.1677 | 0.0567 |
| irnby-brand-in-motion | IRNBY - Brand in motion | Peretiatko | ADVERTISING_SOCIAL_MEDIA_ADS | — | 5.94 | cloudflare-stream | 8.60 | 810x1080 | 30.000 | 3.00 | 3.1 | 1 | 81.4 | 1 | 8.57 | 6.98 | +23% | 0.22-47.76 | — | — | 10 | 1 | 10 | short-sample | 0.5932 | 0.0735 | 0.1130 |
| 4uplayer-mvp-live-intro | 4UPlayer - MVP Live Intro | Victor Soliv. | LIVE_EVENT_TITLES | — | 5.92 | cloudflare-stream | 75.02 | 1280x720 | 30.000 | 1.22 | 10.9 | 4 | 53.3 | 1 | 1.50 | 3.20 | -53% | 0.04-8.36 | — | — | 43 | 1 | 43 | — | 0.1993 | 0.5412 | 0.1115 |
| rollerdeck-associates-lovestaysstrong | Rollerdeck Associates-#LoveStaysStrong | pparnassas | SELF_BRANDING | — | 5.92 | cloudflare-stream | 89.71 | 1280x720 | 25.000 | 3.60 | 38.5 | 4 | 44.6 | 4 | 6.00 | 6.69 | -10% | 0.96-16.81 | 0.000 | 95.0 | 40 | 4 | 40 | — | 0.2712 | 0.3117 | 0.0270 |
| kubriesque | Kubriesque | Nico Speziali | TITLE_SEQUENCES | — | 5.90 | cloudflare-stream | 18.82 | 854x480 | 24.000 | 1.93 | 4.3 | 1 | 53.1 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.2514 | 0.2228 | 0.0819 |
| my-bed-is-calling-me | BMW I8 | Olivier Notot | SHORT_FILMS | — | 5.90 | cloudflare-stream | 33.94 | 1280x720 | 24.000 | 3.64 | 14.7 | 3 | 88.4 | 3 | 6.00 | 5.30 | +13% | 0.00-25.98 | 0.000 | 84.0 | 30 | 3 | 30 | — | 0.1798 | 0.3138 | 0.0737 |
| spec-ad-for-nikec | SPEC AD for NIKE© | CHRISTIAN GONNELLE | SELF_BRANDING | — | 5.90 | direct-mp4 | 32.97 | 1920x1080 | 30.000 | 15.70 | 61.7 | 2 | 60.7 | 1 | 3.00 | 21.84 | -86% | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.1281 | 0.5627 | 0.1349 |
| feel-good | Feel good | Nulteex | GAME_TITLES | — | 5.86 | cloudflare-stream | 205.77 | 1280x720 | 30.000 | 3.52 | 86.3 | 4 | 19.4 | 26 | 39.00 | 37.03 | +5% | 7.03-81.90 | 0.231 | 28.0 | 24 | 20 | 24 | low-coverage | 0.2567 | 0.6194 | 0.1650 |
| holi-animation | Happy Holi | Amit verma | ADVERTISING_SOCIAL_MEDIA_ADS | — | 5.83 | cloudflare-stream | 31.04 | 1280x720 | 29.970 | 0.44 | 1.6 | 2 | 64.4 | 1 | 3.00 | 13.53 | -78% | 0.08-16.71 | — | — | 21 | 1 | 21 | — | 0.8149 | 0.4153 | 0.0373 |
| beatsbydre-ad | BeatsByDre Ad. | Tacomadolo | ADVERTISING_SOCIAL_MEDIA_ADS | — | 5.77 | cloudflare-stream | 39.91 | 1280x720 | 29.970 | 3.08 | 14.7 | 3 | 75.2 | 4 | 8.00 | 6.01 | +33% | 0.00-32.97 | 0.000 | 18.0 | 30 | 3 | 30 | — | 0.1821 | 0.1287 | 0.0765 |
| umami-bee-the-wave | UMAMI Bee - The Wave | UMAMI BEE | EXPERIMENTAL | — | 5.68 | cloudflare-stream | 43.07 | 480x360 | 30.000 | 0.90 | 4.6 | 3 | 69.7 | 14 | 28.00 | 29.26 | -4% | 10.05-54.84 | 0.357 | 27.0 | 23 | 10 | 23 | — | 0.2253 | 0.4541 | 0.0998 |
| play-its-cool | Play, It's cool. | AG Creator | ADVERTISING_COMMERCIALS | — | 5.59 | cloudflare-stream | 32.45 | 608x1080 | 23.976 | 0.59 | 2.3 | 2 | 61.6 | 9 | 27.00 | 18.49 | +46% | 12.35-51.25 | 0.000 | 35.0 | 14 | 8 | 14 | — | 0.3255 | 0.1206 | 0.1338 |
| how-its-made-xbox-series-s | How It's Made: PlayStation 4 Pro | WholesomeAssassin | EXPERIMENTAL | — | 5.43 | cloudflare-stream | 20.00 | 1280x720 | 30.000 | 0.46 | 1.1 | 1 | 50.0 | 0 | 0.00 | 0.00 | — | 0.00-22.13 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.2926 | 0.0876 | 0.0367 |
| blue-stone | Blue Stone | Shugor.design | EXPERIMENTAL | — | 5.40 | cloudflare-stream | 7.59 | 1080x1080 | 30.000 | 4.45 | 4.0 | 1 | 79.0 | 0 | 0.00 | 7.90 | -100% | 0.00-36.89 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.6790 | 0.3492 | 0.2245 |
| dream-on | Dream On | DC CHANG | SHORT_FILMS | — | 5.16 | cloudflare-stream | 40.35 | 1280x720 | 30.000 | 1.11 | 5.3 | 3 | 74.3 | 0 | 0.00 | 0.00 | — | 0.00-7.38 | — | — | 33 | 0 | 33 | no-cuts-observed | 0.1880 | 0.0521 | 0.0099 |
| easy-exit-pack | Easy Exit Pack + Monkey Island Experimental | August L | EXPERIMENTAL | — | 4.49 | cloudflare-stream | 2.00 | 1280x720 | 30.000 | 1.13 | 0.3 | 1 | 50.0 | 0 | 0.00 | 0.00 | — | 0.00-221.34 | — | — | 11 | 0 | 11 | no-cuts-observed, short-sample | 0.5028 | 0.1740 | 0.0486 |

## Per-video detail (top 20 by wa_overall)

### one-day-at-a-time — One Day at a Time

| field | value |
| --- | --- |
| title | One Day at a Time |
| studio | Crinimo.tv |
| category | SHORT_FILMS |
| awards | VOTD, VOTM |
| wa_overall | 9.09 |
| provider | cloudflare-stream |
| runtime_s | 62.40 |
| resolution | 1280x720 |
| fps | 24.000 |
| bitrate_mbps | 1.02 |
| download_mb | 7.6 |
| windows | 4 |
| coverage_pct | 64.1 |
| candidates_n | 0 |
| sampled_cut_candidates_per_min | 0.00 |
| ci95 | 0.00-5.53 |
| burst | — |
| gap_frames | — |
| within_shot_pairs | 44 |
| cut_sep_pairs | 0 |
| delta_basis_pairs | 44 |
| validity | no-cuts-observed |
| mean_luma | 0.1048 |
| mean_sat | 0.8273 |
| delta_per_s | 0.0760 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 0 | 0.0979 | 0.6367 | 0.0705 | 0 |
| 10.00 | 15.00 | 12 | 0 | 0.0386 | 0.9615 | 0.0515 | 0 |
| 10.00 | 30.00 | 12 | 0 | 0.0704 | 0.9210 | 0.0778 | 0 |
| 10.00 | 45.00 | 12 | 0 | 0.2123 | 0.7901 | 0.1041 | 0 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### deep-thoughts-bounce — Deep Thoughts Bounce

| field | value |
| --- | --- |
| title | Deep Thoughts Bounce |
| studio | Media.Monks |
| category | EXPERIMENTAL |
| awards | VOTD, VOTY |
| wa_overall | 9.08 |
| provider | direct-mp4 |
| runtime_s | 105.05 |
| resolution | 1920x1080 |
| fps | 24.000 |
| bitrate_mbps | 5.01 |
| download_mb | 62.7 |
| windows | 4 |
| coverage_pct | 38.1 |
| candidates_n | 31 |
| sampled_cut_candidates_per_min | 46.50 |
| ci95 | 13.68-89.45 |
| burst | 0.677 |
| gap_frames | 2.0 |
| within_shot_pairs | 30 |
| cut_sep_pairs | 14 |
| delta_basis_pairs | 30 |
| validity | burst-heavy, non-edit-scene-change |
| mean_luma | 0.5378 |
| mean_sat | 0.4288 |
| delta_per_s | 0.0929 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 2 | 0.5399 | 0.2128 | 0.1789 | 2 |
| 10.00 | 28.00 | 12 | 3 | 0.4250 | 0.4855 | 0.0648 | 3 |
| 10.00 | 56.00 | 12 | 12 | 0.5436 | 0.5563 | 0.0334 | 6 |
| 10.00 | 84.00 | 12 | 14 | 0.6426 | 0.4606 | 0.0617 | 3 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### styleframe-showreel-2025 — Styleframe Showreel 2025

| field | value |
| --- | --- |
| title | Styleframe Showreel 2025 |
| studio | Styleframe |
| category | SELF_BRANDING |
| awards | VOTD |
| wa_overall | 8.68 |
| provider | cloudflare-stream |
| runtime_s | 80.04 |
| resolution | 1280x720 |
| fps | 25.000 |
| bitrate_mbps | 2.36 |
| download_mb | 22.5 |
| windows | 4 |
| coverage_pct | 50.0 |
| candidates_n | 49 |
| sampled_cut_candidates_per_min | 73.50 |
| ci95 | 44.12-109.87 |
| burst | 0.408 |
| gap_frames | 13.5 |
| within_shot_pairs | 16 |
| cut_sep_pairs | 28 |
| delta_basis_pairs | 16 |
| validity | — |
| mean_luma | 0.4199 |
| mean_sat | 0.3758 |
| delta_per_s | 0.1295 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 13 | 0.3376 | 0.3470 | 0.1556 | 8 |
| 10.00 | 20.00 | 12 | 5 | 0.6452 | 0.2807 | 0.0972 | 4 |
| 10.00 | 40.00 | 12 | 13 | 0.2058 | 0.6534 | 0.1269 | 6 |
| 10.00 | 60.00 | 12 | 18 | 0.4911 | 0.2222 | 0.2910 | 10 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### xiaomi-love-story — XIAOMI Love Story

| field | value |
| --- | --- |
| title | XIAOMI Love Story |
| studio | KUTUKO STUDIO |
| category | ADVERTISING_COMMERCIALS |
| awards | VOTD |
| wa_overall | 8.67 |
| provider | cloudflare-stream |
| runtime_s | 47.77 |
| resolution | 1280x720 |
| fps | 25.000 |
| bitrate_mbps | 1.56 |
| download_mb | 8.9 |
| windows | 4 |
| coverage_pct | 83.7 |
| candidates_n | 10 |
| sampled_cut_candidates_per_min | 15.00 |
| ci95 | 7.19-27.59 |
| burst | 0.000 |
| gap_frames | 76.0 |
| within_shot_pairs | 34 |
| cut_sep_pairs | 10 |
| delta_basis_pairs | 34 |
| validity | — |
| mean_luma | 0.4662 |
| mean_sat | 0.5023 |
| delta_per_s | 0.1004 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 1 | 0.5118 | 0.4662 | 0.1146 | 1 |
| 10.00 | 10.00 | 12 | 2 | 0.4064 | 0.5501 | 0.0979 | 2 |
| 10.00 | 20.00 | 12 | 3 | 0.4488 | 0.5127 | 0.0641 | 3 |
| 10.00 | 30.00 | 12 | 4 | 0.4978 | 0.4801 | 0.1249 | 4 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### scarpa-ribelle-tech-20 — SCARPA — Ribelle Tech 2.0

| field | value |
| --- | --- |
| title | SCARPA — Ribelle Tech 2.0 |
| studio | Subdivision Studio |
| category | ADVERTISING_CAMPAIGNS |
| awards | VOTD, VOTM |
| wa_overall | 8.65 |
| provider | cloudflare-stream |
| runtime_s | 32.04 |
| resolution | 1280x720 |
| fps | 30.000 |
| bitrate_mbps | 3.78 |
| download_mb | 14.5 |
| windows | 2 |
| coverage_pct | 62.4 |
| candidates_n | 8 |
| sampled_cut_candidates_per_min | 24.00 |
| ci95 | 10.36-47.29 |
| burst | 0.000 |
| gap_frames | 27.0 |
| within_shot_pairs | 15 |
| cut_sep_pairs | 7 |
| delta_basis_pairs | 15 |
| validity | — |
| mean_luma | 0.1517 |
| mean_sat | 0.3161 |
| delta_per_s | 0.1323 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 0 | 0.1089 | 0.3390 | 0.1189 | 0 |
| 10.00 | 18.00 | 12 | 8 | 0.1944 | 0.2932 | 0.1690 | 7 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### lumbre-brand-animation — LUMBRE Brand Animation

| field | value |
| --- | --- |
| title | LUMBRE Brand Animation |
| studio | LUMBRE |
| category | SELF_BRANDING |
| awards | VOTD |
| wa_overall | 8.58 |
| provider | direct-mp4 |
| runtime_s | 20.96 |
| resolution | 1920x1080 |
| fps | 25.000 |
| bitrate_mbps | 8.33 |
| download_mb | 20.8 |
| windows | 1 |
| coverage_pct | 47.7 |
| candidates_n | 3 |
| sampled_cut_candidates_per_min | 18.00 |
| ci95 | 3.71-52.60 |
| burst | 0.000 |
| gap_frames | 75.5 |
| within_shot_pairs | 8 |
| cut_sep_pairs | 3 |
| delta_basis_pairs | 8 |
| validity | short-sample |
| mean_luma | 0.2386 |
| mean_sat | 0.4883 |
| delta_per_s | 0.1422 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 3 | 0.2386 | 0.4883 | 0.1422 | 3 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### pantene-nutrient-blends — Pantene — Nutrient Blends

| field | value |
| --- | --- |
| title | Pantene — Nutrient Blends |
| studio | Ditroit |
| category | ADVERTISING_COMMERCIALS |
| awards | VOTD |
| wa_overall | 8.58 |
| provider | cloudflare-stream |
| runtime_s | 30.02 |
| resolution | 1280x720 |
| fps | 30.000 |
| bitrate_mbps | 3.69 |
| download_mb | 13.2 |
| windows | 2 |
| coverage_pct | 66.6 |
| candidates_n | 9 |
| sampled_cut_candidates_per_min | 27.00 |
| ci95 | 12.35-51.25 |
| burst | 0.000 |
| gap_frames | 41.5 |
| within_shot_pairs | 14 |
| cut_sep_pairs | 8 |
| delta_basis_pairs | 14 |
| validity | — |
| mean_luma | 0.6512 |
| mean_sat | 0.4217 |
| delta_per_s | 0.1226 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 3 | 0.7130 | 0.2508 | 0.1332 | 3 |
| 10.00 | 17.00 | 12 | 6 | 0.5893 | 0.5927 | 0.1085 | 5 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### how-to-make-sushi — How To Make Sushi

| field | value |
| --- | --- |
| title | How To Make Sushi |
| studio | Jonathan Lindgren |
| category | SHORT_FILMS |
| awards | VOTD |
| wa_overall | 8.57 |
| provider | direct-mp4 |
| runtime_s | 139.04 |
| resolution | 1920x1080 |
| fps | 24.000 |
| bitrate_mbps | 10.27 |
| download_mb | 170.1 |
| windows | 4 |
| coverage_pct | 28.8 |
| candidates_n | 8 |
| sampled_cut_candidates_per_min | 12.00 |
| ci95 | 3.20-27.03 |
| burst | 0.000 |
| gap_frames | 65.0 |
| within_shot_pairs | 36 |
| cut_sep_pairs | 8 |
| delta_basis_pairs | 36 |
| validity | — |
| mean_luma | 0.6708 |
| mean_sat | 0.4787 |
| delta_per_s | 0.0333 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 1 | 0.7073 | 0.4843 | 0.0355 | 1 |
| 10.00 | 38.00 | 12 | 3 | 0.6540 | 0.5353 | 0.0347 | 3 |
| 10.00 | 76.00 | 12 | 4 | 0.7074 | 0.4481 | 0.0203 | 4 |
| 10.00 | 114.00 | 12 | 0 | 0.6143 | 0.4471 | 0.0386 | 0 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### gullwing-shortfilm — Gullwing - Shortfilm

| field | value |
| --- | --- |
| title | Gullwing - Shortfilm |
| studio | Briktop |
| category | SHORT_FILMS |
| awards | VOTD, VOTM |
| wa_overall | 8.56 |
| provider | cloudflare-stream |
| runtime_s | 114.15 |
| resolution | 1084x480 |
| fps | 25.000 |
| bitrate_mbps | 1.73 |
| download_mb | 23.5 |
| windows | 4 |
| coverage_pct | 35.0 |
| candidates_n | 19 |
| sampled_cut_candidates_per_min | 28.50 |
| ci95 | 8.40-56.86 |
| burst | 0.263 |
| gap_frames | 36.5 |
| within_shot_pairs | 27 |
| cut_sep_pairs | 17 |
| delta_basis_pairs | 27 |
| validity | — |
| mean_luma | 0.5879 |
| mean_sat | 0.1117 |
| delta_per_s | 0.1145 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 1 | 0.7737 | 0.1404 | 0.0525 | 1 |
| 10.00 | 30.00 | 12 | 9 | 0.5897 | 0.1427 | 0.3646 | 7 |
| 10.00 | 60.00 | 12 | 7 | 0.7123 | 0.1222 | 0.1294 | 7 |
| 10.00 | 90.00 | 12 | 2 | 0.2760 | 0.0413 | 0.0656 | 2 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### how-countries-fight-their-wars — How Countries Fight Their Wars

| field | value |
| --- | --- |
| title | How Countries Fight Their Wars |
| studio | MITSI STUDIO |
| category | SHORT_FILMS |
| awards | VOTD, VOTM |
| wa_overall | 8.54 |
| provider | cloudflare-stream |
| runtime_s | 124.05 |
| resolution | 1280x720 |
| fps | 30.000 |
| bitrate_mbps | 3.42 |
| download_mb | 50.6 |
| windows | 4 |
| coverage_pct | 32.2 |
| candidates_n | 0 |
| sampled_cut_candidates_per_min | 0.00 |
| ci95 | 0.00-5.53 |
| burst | — |
| gap_frames | — |
| within_shot_pairs | 44 |
| cut_sep_pairs | 0 |
| delta_basis_pairs | 44 |
| validity | no-cuts-observed |
| mean_luma | 0.2209 |
| mean_sat | 0.3077 |
| delta_per_s | 0.0846 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 0 | 0.1507 | 0.3036 | 0.0639 | 0 |
| 10.00 | 33.00 | 12 | 0 | 0.2362 | 0.3145 | 0.0848 | 0 |
| 10.00 | 66.00 | 12 | 0 | 0.2404 | 0.3065 | 0.0971 | 0 |
| 10.00 | 99.00 | 12 | 0 | 0.2562 | 0.3063 | 0.0925 | 0 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### permission-to-move-three-easy-steps-to-recover-from-chronic-pain — Permission To Move \| Three Easy Steps to Recover from Chronic Pain

| field | value |
| --- | --- |
| title | Permission To Move \| Three Easy Steps to Recover from Chronic Pain |
| studio | Niceshit Studio |
| category | ADVERTISING_COMMERCIALS |
| awards | VOTD, VOTM |
| wa_overall | 8.53 |
| provider | cloudflare-stream |
| runtime_s | 90.03 |
| resolution | 1280x720 |
| fps | 24.000 |
| bitrate_mbps | 3.96 |
| download_mb | 42.5 |
| windows | 4 |
| coverage_pct | 44.4 |
| candidates_n | 12 |
| sampled_cut_candidates_per_min | 18.00 |
| ci95 | 1.09-44.13 |
| burst | 0.333 |
| gap_frames | 50.0 |
| within_shot_pairs | 36 |
| cut_sep_pairs | 8 |
| delta_basis_pairs | 36 |
| validity | — |
| mean_luma | 0.5676 |
| mean_sat | 0.3594 |
| delta_per_s | 0.0555 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 1 | 0.4736 | 0.4740 | 0.0508 | 1 |
| 10.00 | 23.00 | 12 | 1 | 0.7533 | 0.1542 | 0.0394 | 1 |
| 10.00 | 46.00 | 12 | 8 | 0.5935 | 0.4149 | 0.1264 | 4 |
| 10.00 | 69.00 | 12 | 2 | 0.4497 | 0.3944 | 0.0236 | 2 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### bullpadel-vertex-05 — Bullpadel VERTEX 05

| field | value |
| --- | --- |
| title | Bullpadel VERTEX 05 |
| studio | KUTUKO STUDIO |
| category | ADVERTISING_COMMERCIALS |
| awards | VOTD |
| wa_overall | 8.49 |
| provider | cloudflare-stream |
| runtime_s | 31.25 |
| resolution | 1280x720 |
| fps | 25.000 |
| bitrate_mbps | 2.09 |
| download_mb | 7.8 |
| windows | 2 |
| coverage_pct | 64.0 |
| candidates_n | 11 |
| sampled_cut_candidates_per_min | 33.00 |
| ci95 | 16.47-59.05 |
| burst | 0.000 |
| gap_frames | 36.5 |
| within_shot_pairs | 12 |
| cut_sep_pairs | 10 |
| delta_basis_pairs | 12 |
| validity | — |
| mean_luma | 0.3796 |
| mean_sat | 0.5046 |
| delta_per_s | 0.1662 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 6 | 0.3305 | 0.4837 | 0.1602 | 5 |
| 10.00 | 18.00 | 12 | 5 | 0.4288 | 0.5256 | 0.1723 | 5 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### asphalt — ASPHALT

| field | value |
| --- | --- |
| title | ASPHALT |
| studio | Albin MERLE |
| category | ADVERTISING_COMMERCIALS |
| awards | VOTD |
| wa_overall | 8.46 |
| provider | cloudflare-stream |
| runtime_s | 51.09 |
| resolution | 1280x720 |
| fps | 25.000 |
| bitrate_mbps | 4.17 |
| download_mb | 25.4 |
| windows | 4 |
| coverage_pct | 78.3 |
| candidates_n | 20 |
| sampled_cut_candidates_per_min | 30.00 |
| ci95 | 18.32-46.33 |
| burst | 0.200 |
| gap_frames | 50.0 |
| within_shot_pairs | 27 |
| cut_sep_pairs | 17 |
| delta_basis_pairs | 27 |
| validity | — |
| mean_luma | 0.2892 |
| mean_sat | 0.1594 |
| delta_per_s | 0.2230 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 2 | 0.2495 | 0.1303 | 0.1547 | 2 |
| 10.00 | 11.00 | 12 | 6 | 0.2831 | 0.1682 | 0.2649 | 5 |
| 10.00 | 22.00 | 12 | 5 | 0.3601 | 0.1790 | 0.2729 | 5 |
| 10.00 | 33.00 | 12 | 7 | 0.2641 | 0.1603 | 0.2335 | 5 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### microsoft-fluent-ui — Microsoft — Fluent UI

| field | value |
| --- | --- |
| title | Microsoft — Fluent UI |
| studio | Vitaly Grossmann & Vincent Schwenk |
| category | LIVE_EVENT_TITLES |
| awards | VOTD, VOTM, VOTY |
| wa_overall | 8.45 |
| provider | cloudflare-stream |
| runtime_s | 61.46 |
| resolution | 1280x720 |
| fps | 25.000 |
| bitrate_mbps | 3.67 |
| download_mb | 26.9 |
| windows | 4 |
| coverage_pct | 65.1 |
| candidates_n | 16 |
| sampled_cut_candidates_per_min | 24.00 |
| ci95 | 13.72-38.97 |
| burst | 0.000 |
| gap_frames | 46.0 |
| within_shot_pairs | 28 |
| cut_sep_pairs | 16 |
| delta_basis_pairs | 28 |
| validity | — |
| mean_luma | 0.6476 |
| mean_sat | 0.1491 |
| delta_per_s | 0.0894 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 2 | 0.7769 | 0.1422 | 0.1133 | 2 |
| 10.00 | 15.00 | 12 | 3 | 0.6885 | 0.1014 | 0.0568 | 3 |
| 10.00 | 30.00 | 12 | 6 | 0.4556 | 0.1808 | 0.0907 | 6 |
| 10.00 | 45.00 | 12 | 5 | 0.6693 | 0.1720 | 0.0960 | 5 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### the-hidden-life-of-rosa-parks — The Hidden Life of Rosa Parks

| field | value |
| --- | --- |
| title | The Hidden Life of Rosa Parks |
| studio | Eido |
| category | SHORT_FILMS |
| awards | VOTD |
| wa_overall | 8.45 |
| provider | cloudflare-stream |
| runtime_s | 290.03 |
| resolution | 1280x720 |
| fps | 24.000 |
| bitrate_mbps | 3.61 |
| download_mb | 124.7 |
| windows | 4 |
| coverage_pct | 13.8 |
| candidates_n | 34 |
| sampled_cut_candidates_per_min | 51.00 |
| ci95 | 15.73-96.59 |
| burst | 0.912 |
| gap_frames | 3.0 |
| within_shot_pairs | 33 |
| cut_sep_pairs | 11 |
| delta_basis_pairs | 33 |
| validity | burst-heavy, low-coverage |
| mean_luma | 0.4971 |
| mean_sat | 0.2949 |
| delta_per_s | 0.1818 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 14 | 0.5673 | 0.1741 | 0.1319 | 4 |
| 10.00 | 83.00 | 12 | 1 | 0.2491 | 0.5183 | 0.2605 | 1 |
| 10.00 | 166.00 | 12 | 5 | 0.5318 | 0.1668 | 0.1972 | 2 |
| 10.00 | 249.00 | 12 | 14 | 0.6400 | 0.3203 | 0.0996 | 4 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### bmw-concept-i4-social-stings — BMW Concept i4 - social stings

| field | value |
| --- | --- |
| title | BMW Concept i4 - social stings |
| studio | Aixsponza |
| category | ADVERTISING_SOCIAL_MEDIA_ADS |
| awards | VOTD |
| wa_overall | 8.35 |
| provider | direct-mp4 |
| runtime_s | 112.04 |
| resolution | 1080x1350 |
| fps | 25.000 |
| bitrate_mbps | 3.01 |
| download_mb | 40.2 |
| windows | 4 |
| coverage_pct | 35.7 |
| candidates_n | 0 |
| sampled_cut_candidates_per_min | 0.00 |
| ci95 | 0.00-5.53 |
| burst | — |
| gap_frames | — |
| within_shot_pairs | 44 |
| cut_sep_pairs | 0 |
| delta_basis_pairs | 44 |
| validity | no-cuts-observed |
| mean_luma | 0.5034 |
| mean_sat | 0.1439 |
| delta_per_s | 0.1494 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 0 | 0.6497 | 0.1084 | 0.1043 | 0 |
| 10.00 | 30.00 | 12 | 0 | 0.3625 | 0.1772 | 0.1924 | 0 |
| 10.00 | 60.00 | 12 | 0 | 0.4298 | 0.1705 | 0.2289 | 0 |
| 10.00 | 90.00 | 12 | 0 | 0.5717 | 0.1196 | 0.0721 | 0 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### hamilton-ventura-edge-skeleton-by-kutuko — Hamilton Ventura Edge Skeleton By Kutuko

| field | value |
| --- | --- |
| title | Hamilton Ventura Edge Skeleton By Kutuko |
| studio | KUTUKO STUDIO |
| category | ADVERTISING_COMMERCIALS |
| awards | VOTD |
| wa_overall | 8.35 |
| provider | cloudflare-stream |
| runtime_s | 36.82 |
| resolution | 1280x720 |
| fps | 25.000 |
| bitrate_mbps | 2.12 |
| download_mb | 9.3 |
| windows | 3 |
| coverage_pct | 81.5 |
| candidates_n | 33 |
| sampled_cut_candidates_per_min | 66.00 |
| ci95 | 38.97-101.08 |
| burst | 0.697 |
| gap_frames | 7.0 |
| within_shot_pairs | 17 |
| cut_sep_pairs | 16 |
| delta_basis_pairs | 17 |
| validity | burst-heavy |
| mean_luma | 0.2119 |
| mean_sat | 0.1122 |
| delta_per_s | 0.1567 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 6 | 0.1291 | 0.1855 | 0.1321 | 2 |
| 10.00 | 11.00 | 12 | 14 | 0.2525 | 0.0379 | 0.1362 | 7 |
| 10.00 | 22.00 | 12 | 13 | 0.2541 | 0.1131 | 0.2327 | 7 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### mission-m101 — Mission M101

| field | value |
| --- | --- |
| title | Mission M101 |
| studio | Feed Me Light |
| category | ADVERTISING_CAMPAIGNS |
| awards | VOTD |
| wa_overall | 8.35 |
| provider | cloudflare-stream |
| runtime_s | 212.76 |
| resolution | 1280x720 |
| fps | 25.000 |
| bitrate_mbps | 3.64 |
| download_mb | 92.4 |
| windows | 4 |
| coverage_pct | 18.8 |
| candidates_n | 22 |
| sampled_cut_candidates_per_min | 33.00 |
| ci95 | 1.92-75.79 |
| burst | 0.636 |
| gap_frames | 14.0 |
| within_shot_pairs | 29 |
| cut_sep_pairs | 15 |
| delta_basis_pairs | 29 |
| validity | burst-heavy, low-coverage |
| mean_luma | 0.2757 |
| mean_sat | 0.4335 |
| delta_per_s | 0.0729 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 1 | 0.2216 | 0.2548 | 0.0676 | 1 |
| 10.00 | 60.00 | 12 | 14 | 0.2010 | 0.7205 | 0.1129 | 9 |
| 10.00 | 120.00 | 12 | 2 | 0.2875 | 0.3677 | 0.0740 | 2 |
| 10.00 | 180.00 | 12 | 5 | 0.3925 | 0.3910 | 0.0682 | 3 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### future-relics-tp-01 — Future Relics - TP_01

| field | value |
| --- | --- |
| title | Future Relics - TP_01 |
| studio | Kinisi |
| category | SELF_BRANDING |
| awards | VOTD, VOTM |
| wa_overall | 8.34 |
| provider | cloudflare-stream |
| runtime_s | 51.05 |
| resolution | 1280x720 |
| fps | 24.000 |
| bitrate_mbps | 1.13 |
| download_mb | 6.9 |
| windows | 4 |
| coverage_pct | 78.4 |
| candidates_n | 3 |
| sampled_cut_candidates_per_min | 4.50 |
| ci95 | 0.55-14.06 |
| burst | 0.000 |
| gap_frames | 372.0 |
| within_shot_pairs | 41 |
| cut_sep_pairs | 3 |
| delta_basis_pairs | 41 |
| validity | — |
| mean_luma | 0.5431 |
| mean_sat | 0.0377 |
| delta_per_s | 0.0967 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 1 | 0.5651 | 0.0734 | 0.0868 | 1 |
| 10.00 | 11.00 | 12 | 0 | 0.6254 | 0.0351 | 0.1214 | 0 |
| 10.00 | 22.00 | 12 | 0 | 0.5934 | 0.0227 | 0.1211 | 0 |
| 10.00 | 33.00 | 12 | 2 | 0.3885 | 0.0195 | 0.0476 | 2 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

### very-noise — Very Noise

| field | value |
| --- | --- |
| title | Very Noise |
| studio | MEAT DEPT. |
| category | MUSIC_VIDEOS |
| awards | VOTD, VOTM, VOTY |
| wa_overall | 8.33 |
| provider | cloudflare-stream |
| runtime_s | 156.84 |
| resolution | 1280x720 |
| fps | 25.000 |
| bitrate_mbps | 3.70 |
| download_mb | 69.1 |
| windows | 4 |
| coverage_pct | 25.5 |
| candidates_n | 15 |
| sampled_cut_candidates_per_min | 22.50 |
| ci95 | 9.71-41.36 |
| burst | 0.000 |
| gap_frames | 46.0 |
| within_shot_pairs | 31 |
| cut_sep_pairs | 13 |
| delta_basis_pairs | 31 |
| validity | — |
| mean_luma | 0.2661 |
| mean_sat | 0.1902 |
| delta_per_s | 0.1104 |

| window_s | start_s | sampled_frames | cut_candidates | mean_luma | mean_sat | delta_per_s | cut_sep_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.00 | 0.00 | 12 | 3 | 0.1887 | 0.1333 | 0.0797 | 3 |
| 10.00 | 43.00 | 12 | 4 | 0.3456 | 0.2022 | 0.1122 | 4 |
| 10.00 | 86.00 | 12 | 7 | 0.3880 | 0.2332 | 0.1719 | 5 |
| 10.00 | 129.00 | 12 | 1 | 0.1419 | 0.1922 | 0.0968 | 1 |

limits: sampled source-PTS windows only (not full-film review); numeric display-RGB and cut-candidate proxies are not style, quality, lighting, editing-intent, or authorship labels.

## Aggregates (video-measured records only)

Every number in this section is computed ONLY over the video-measured records tabulated above. Published stills, including still-only projects, never enter the motion, cut, luma, or saturation aggregates.

### Counts

| provider | records |
| --- | --- |
| cloudflare-stream | 451 |
| direct-mp4 | 39 |

| category | records |
| --- | --- |
| ADVERTISING_CAMPAIGNS | 72 |
| ADVERTISING_COMMERCIALS | 93 |
| ADVERTISING_SOCIAL_MEDIA_ADS | 33 |
| BROADCAST_CHANNEL_BRANDING | 13 |
| BROADCAST_PROGRAM_TITLES | 9 |
| BROADCAST_SERIES_TITLES | 9 |
| EXPERIMENTAL | 57 |
| EXPLANATORY_VIDEO | 32 |
| FILM_GRAPHICS | 5 |
| GAME_TITLES | 3 |
| INSTALLATION_PROJECTION_EXPERIENCE | 6 |
| LIVE_EVENT_TITLES | 14 |
| MUSIC_VIDEOS | 30 |
| SELF_BRANDING | 58 |
| SHORT_FILMS | 44 |
| SOUND_DESIGN | 1 |
| TITLE_SEQUENCES | 11 |

| award_type | records |
| --- | --- |
| HM | 25 |
| VOTD | 276 |
| VOTM | 12 |
| VOTY | 11 |
| (no award) | 189 |

### Distributions

All minima and maxima are computed over `rankable` records only and name the record id and validity flags.

Unique records before dedupe: 491; after dedupe: 490 (1 duplicate extra record(s) collapsed).

Rankable records: 323 of 490 unique; excluded as non-rankable: 167.

| metric | n | min (record; flags) | median | max (record; flags) |
| --- | --- | --- | --- | --- |
| runtime_s | 323 | 22.31 (persol-universe; —) | 58.69 | 370.88 (refugium; low-coverage) |
| candidates_n | 323 | 0 (72-and-sunny; no-cuts-observed) | 6 | 62 (the-heist-motion-design-reel-2025; sparse-delta-basis) |
| sampled_cut_candidates_per_min | 323 | 0.00 (72-and-sunny; no-cuts-observed) | 12.00 | 93.00 (the-heist-motion-design-reel-2025; sparse-delta-basis) |
| mean_luma | 323 | 0.0197 (breaking-the-chain-a-cinematic-tribute-to-earth-day-2026-1; no-cuts-observed) | 0.3796 | 0.9393 (mobile-activity-shape-tables; no-cuts-observed) |
| mean_sat | 323 | 0.0000 (di-punto-in-bianco-1; —) | 0.3127 | 0.8943 (being-a-crab-emojis; —) |
Excluded as non-rankable (largest first):

| record | sampled_cut_candidates_per_min | validity |
| --- | --- | --- |
| unkle-psyence-fiction-teaser | 390.00 | burst-heavy, sparse-delta-basis |
| threaten-with-love-pocky-1 | 240.00 | burst-heavy, short-sample, sparse-delta-basis |
| eat-well-little-child | 228.00 | burst-heavy, non-edit-scene-change, short-sample, sparse-delta-basis |
| adidas-zne | 222.00 | burst-heavy, non-edit-scene-change, sparse-delta-basis |
| we-love | 201.00 | burst-heavy, non-edit-scene-change |

Coverage-weighted caveat: 14695.0 sampled seconds cover 32151.3 runtime seconds (45.7%). Per-record coverage ranges from 10.8% to 89.9% (median 64.0%). Aggregates describe the sampled windows, not the full films.

## Comparability

- poolable: `false`
- comparable within: same site, same rendition, same runtime band, non-burst, >=25% coverage
- not comparable to: other sites, other renditions, full-film claims derived from window rates

Caveats:

- Motion Design Awards: poolable is false; every number describes this site's measured sample only.
- 491 of 1919 catalogue items were measured (25.586%) by catalog order filtered by public provider availability and a 600 s duration budget.
- Measured rows are not a random sample: availability and recency select them, so cross-site pooling is invalid.
- Provider families are not interchangeable: cloudflare-stream x 451, direct-mp4 x 39.
- Renditions differ by site and record: Cloudflare Stream HLS, keyframes storage, and direct MP4 sources are mixed.
- Measured renditions vary by resolution (1280x720 x 368, 1920x1080 x 30, 1080x1080 x 14, 1080x1920 x 14, 1128x480 x 6, 608x1080 x 6, 1152x480 x 5, 1080x1350 x 3, +34 more), frame rate (25 x 173, 24 x 132, 30 x 121, 29.97 x 25, 23.976 x 20, 15 x 5, 60 x 5, 12 x 4, +4 more) and bitrate (3.7 x 32, 3.6 x 22, 1.9 x 21, 3.8 x 21, 3.5 x 20, 1.3 x 19, 3.4 x 18, 1.1 x 17, +72 more), so the sample is not a controlled transform.
- Window coverage is sampled, not full-film: median 63.97955% per record, p10 28.87062%, p90 85.04181%; 4.897959% of rows are below 20% and 0.0% below 10%; median unobserved gap between windows is 7.0 s. Window rates describe those windows; a full-film census, when present, is reported separately.
- 1 extra record(s) in 1 duplicate group(s) share media; unique media after dedupe is 490.
- Still/video overlap: 1901 still record(s), 1413 still-only, are a separate single-frame lane and never enter these aggregates.

## Coverage

Per-record coverage distribution over the deduped records. The unobserved gap is the median time between consecutive sampled windows, derived from runtime, window count and sampled seconds.

| statistic | coverage_pct |
| --- | --- |
| min | 10.8 |
| p10 | 28.9 |
| median | 64.0 |
| p90 | 85.0 |
| max | 89.9 |
| below 20% | 4.9% |
| below 10% | 0.0% |
| median unobserved gap between windows | 7.0 s |

## Full-film census

Film-level evidence: 491 of 491 video-measured records (100.0%) on Motion Design Awards have a full-runtime census record. Census values are **film-level**: every cut candidate in the file was counted and the appearance series is time-weighted over the whole runtime, so `decodeCoverageFraction` is 1.000000. The `full_cuts_per_min` column is that film-level rate; every `sampled_cut_candidates_per_min` value remains a sample of its windows.

Census cut candidates are still ffmpeg scene-score exceedances, not verified edits; fast movement, flashes, transitions and compression can exceed the threshold. A `strobe` record's rate describes strobe-like candidate density and is **not comparable to a cut rate**, so strobe records are excluded from the range below and reported separately.

| statistic | full_cuts_per_min (non-strobe) |
| --- | --- |
| n | 387 |
| min | 0.00 |
| p10 | 0.00 |
| median | 11.88 |
| p90 | 32.98 |
| max | 95.88 |

Range endpoints: min 0.00 (`72-and-sunny`), max 95.88 (`loujey-zidi-2d-animation-intro`); n counts non-strobe records only.

Strobe block (never pooled with the cut-rate range above): 104 record(s), listed by id below. Its own range is min 2.95, median 46.39, max 361.18.

| strobe id | full_cuts_per_min | median_gap_frames | burst_fraction |
| --- | --- | --- | --- |
| 100m-race-mowe-studio | 45.22 | 6.0 | 0.550 |
| 24hmotion | 101.63 | 5.0 | 0.692 |
| adidas-james-rodriguez | 67.50 | 2.0 | 0.750 |
| adidas-zne | 207.09 | 2.0 | 0.848 |
| aj-mitchell-burn-music-video-1 | 18.86 | 46.0 | 0.523 |
| akima | 23.57 | 4.0 | 0.696 |
| anxiety-short-film | 49.71 | 6.0 | 0.667 |
| aphex-twin-4 | 51.48 | 3.0 | 0.790 |
| artifex-creatura-1 | 69.38 | 7.5 | 0.707 |
| automotive-animation-in-unreal-engine-5 | 41.72 | 2.0 | 0.647 |
| balenciaga-track-1-trainer | 75.28 | 3.0 | 0.839 |
| biobar | 65.33 | 8.0 | 0.750 |
| bourse | 59.84 | 9.0 | 0.562 |
| brompton-house-home-of-baking | 73.63 | 2.0 | 0.911 |
| broomsticks-on-broadway-1 | 14.01 | 16.5 | 0.575 |
| bullpadel-hack-05-aero | 38.58 | 10.5 | 0.571 |
| bullpadel-vertex-04 | 115.74 | 3.0 | 0.667 |
| cartoon-network-sequencer-id-apple-onion | 53.89 | 2.0 | 1.000 |
| chantecaille-global-lip-creme-launch-campaign | 7.98 | 3.0 | 0.750 |
| copenhagen | 28.41 | 15.0 | 0.800 |
| corey-taylor-culture-head-official-music-video | 17.31 | 8.5 | 0.739 |
| cyberpunk-2088 | 25.90 | 3.0 | 1.000 |
| dark-room | 35.72 | 2.0 | 0.847 |
| david-bowie-the-man-who-sold-the-world-official-lyric-video | 27.13 | 4.0 | 0.862 |
| deep-thoughts-bounce | 54.26 | 2.0 | 0.653 |
| disenchanted | 42.25 | 4.0 | 0.736 |
| dof-motion-brandbook | 65.63 | 4.0 | 0.912 |
| doppl-2 | 13.43 | 2.0 | 0.769 |
| drop-dead-signal | 20.70 | 8.0 | 0.625 |
| eat-well-little-child | 222.80 | 2.0 | 0.987 |
| eni | 10.00 | 2.0 | 1.000 |
| everyday-waves | 71.86 | 3.0 | 0.903 |
| fbi-jobs-the-essentials | 194.02 | 4.0 | 0.774 |
| fritz-kola-founders-story | 61.10 | 2.0 | 0.971 |
| genesis-motion-design-manifesto | 57.86 | 4.0 | 0.790 |
| get-creative | 163.56 | 3.0 | 0.902 |
| gilbarte-2049 | 49.96 | 5.0 | 0.846 |
| gummy-gas-crisis | 21.47 | 13.0 | 0.507 |
| hamilton-ventura-edge-skeleton-by-kutuko | 66.81 | 6.5 | 0.756 |
| hard-to-starboard | 11.64 | 5.0 | 0.818 |
| hp-tuners-e90-ecm-launch | 33.17 | 33.0 | 0.526 |
| httpsvimeocom990284238sharecopy | 99.47 | 3.0 | 0.980 |
| i-choose-violence | 154.58 | 3.0 | 0.833 |
| i-hear-the-cicadas | 74.82 | 3.0 | 0.795 |
| its-still-being-written | 18.65 | 2.0 | 0.714 |
| jump | 50.12 | 7.0 | 0.634 |
| kanu-the-pulse | 5.97 | 23.0 | 0.800 |
| kconex | 45.34 | 3.0 | 0.899 |
| kinetic-lyrics-to-toy-by-young-father | 133.90 | 8.0 | 0.687 |
| kontroll | 65.05 | 2.0 | 0.961 |
| krockio-manage-better-and-deliver-faster | 21.68 | 7.0 | 0.600 |
| lavazza-coffee | 20.96 | 15.5 | 0.714 |
| legend-trade-video | 101.11 | 2.0 | 0.917 |
| lucky-penny | 76.81 | 2.0 | 0.821 |
| mantis-launch-reel | 22.93 | 8.0 | 0.583 |
| mediamonks-animation-reel-intro-1 | 47.12 | 2.0 | 0.923 |
| mission-m101 | 51.33 | 9.0 | 0.670 |
| monster-energy-animation | 137.47 | 2.0 | 1.000 |
| moonky | 49.30 | 12.0 | 0.607 |
| motion-design-reel-main-titles | 29.08 | 10.0 | 0.719 |
| music-unites-herbie-hancock-kamasi-washington-in-conversation | 74.68 | 2.0 | 0.902 |
| natgeo-worlds-deadliest-bite | 65.46 | 21.5 | 0.505 |
| naturgy-ecoeasy-20-spot | 8.99 | 2.0 | 1.000 |
| nextatlas | 40.28 | 2.0 | 0.956 |
| no-escape-1 | 44.61 | 9.0 | 0.562 |
| odi-odi | 84.62 | 5.0 | 0.765 |
| pieces-of-me | 35.83 | 5.0 | 0.850 |
| prada-perfum | 99.58 | 5.0 | 0.833 |
| rawayana-welcome-to-el-sur | 32.29 | 9.0 | 0.544 |
| rechannel | 33.87 | 19.5 | 0.621 |
| red-square-anime | 59.91 | 18.0 | 0.553 |
| reframing-forestry-standards-for-people-planet-purpose | 54.99 | 2.0 | 1.000 |
| roves-8th-birthday | 22.03 | 3.0 | 0.833 |
| sevilla-design-walk-26-main-titles | 46.82 | 10.0 | 0.607 |
| skate-loop-1 | 45.96 | 2.0 | 1.000 |
| spec-ad-for-nikec | 21.84 | 3.0 | 0.583 |
| speed-chord | 20.88 | 3.0 | 0.882 |
| spiritual-birth | 26.87 | 4.0 | 0.964 |
| springsummer-2030-bikeswear | 27.68 | 7.5 | 0.800 |
| staypes-5 | 7.57 | 5.0 | 0.750 |
| studio-i-towards-a-new-museum | 25.40 | 2.0 | 0.818 |
| sythetica-psychoidea | 111.54 | 5.0 | 0.786 |
| tedeschi-trucks-band-hard-case-music-video | 48.66 | 2.0 | 0.841 |
| test-4 | 44.37 | 10.5 | 0.727 |
| the-fall | 55.77 | 2.0 | 0.949 |
| the-hidden-life-of-rosa-parks | 22.55 | 3.0 | 0.761 |
| the-idea-guide | 22.38 | 6.0 | 0.824 |
| the-us-is-missing-out-on-walkable-cities | 40.07 | 2.0 | 0.935 |
| threaten-with-love-pocky-1 | 205.79 | 3.0 | 0.857 |
| thunder-challenge-entry | 42.05 | 2.5 | 1.000 |
| unfamiliar-landscapes | 23.30 | 8.0 | 0.704 |
| university-instructions-for-use | 19.72 | 2.0 | 0.714 |
| unkle-psyence-fiction-teaser | 361.18 | 3.0 | 0.997 |
| us-election | 90.21 | 4.0 | 0.706 |
| vector-become-your-player | 39.65 | 14.5 | 0.645 |
| vertebrae-atlas | 2.95 | 47.0 | 0.667 |
| vet-boroschek-spot | 33.14 | 4.0 | 0.714 |
| vsgoods | 61.63 | 5.5 | 0.758 |
| we-love | 196.61 | 2.0 | 0.988 |
| we-love-movies | 58.01 | 3.0 | 0.828 |
| where-does-an-idea-come-from | 49.39 | 3.0 | 0.830 |
| wolverine-hellcat | 49.96 | 9.0 | 0.560 |
| young-marketers-2 | 8.07 | 64.0 | 0.615 |
| youth-route | 4.54 | 106.0 | 0.600 |

## Census reconciliation

Window values are samples of the runtime; census values cover the film. Relative error is `(window_rate - full_rate) / full_rate`, so a positive value means the window sample overestimated the film and a negative value means it underestimated it.

- comparable records: 441; skipped for a zero full-film rate: 49
- median |relative error|: 0.171; p90 |relative error|: 0.645; max |relative error|: 2.327
- window estimate off by more than 25%: 174 of 441 (39.5%); window higher on 270 record(s), lower on 171
- ordering changes beyond five positions when ranked by each rate: 367

| id | window_cuts_per_min | full_cuts_per_min | relative_error | direction |
| --- | --- | --- | --- | --- |
| future-cube-all-after-effects | 1.50 | 0.45 | 2.327 | window higher |
| httpsvimeocom528258339 | 18.00 | 7.72 | 1.332 | window higher |
| the-hidden-life-of-rosa-parks | 51.00 | 22.55 | 1.262 | window higher |
| inspired-by-bauhaus | 18.00 | 8.14 | 1.210 | window higher |
| fork | 49.50 | 23.08 | 1.145 | window higher |
| lumbre-brand-animation | 18.00 | 8.59 | 1.096 | window higher |
| dalai-lamas-guide-to-happiness-pt02 | 3.00 | 1.48 | 1.021 | window higher |
| naturgy-ecoeasy-20-spot | 18.00 | 8.99 | 1.002 | window higher |
| blue-stone | 0.00 | 7.90 | -1.000 | window lower |
| bmw-concept-i4-social-stings | 0.00 | 0.54 | -1.000 | window lower |
| breaking-rules | 0.00 | 1.71 | -1.000 | window lower |
| caritas-europa-explained | 0.00 | 0.35 | -1.000 | window lower |
| cyberpunk-2088 | 0.00 | 25.90 | -1.000 | window lower |
| finding-my-faith-1 | 0.00 | 2.59 | -1.000 | window lower |
| freerunning-in-the-metaverse-episode-1 | 0.00 | 1.48 | -1.000 | window lower |
| glass-by-gaviota | 0.00 | 0.73 | -1.000 | window lower |
| how-much-emergency-cash-is-enough | 0.00 | 0.56 | -1.000 | window lower |
| illu | 0.00 | 2.99 | -1.000 | window lower |
| mercedes-benz-digital-experience | 0.00 | 1.35 | -1.000 | window lower |
| move-until-youre-numbq | 0.00 | 3.54 | -1.000 | window lower |
| on-cyclon-2 | 0.00 | 2.41 | -1.000 | window lower |
| playboy-uncovered | 0.00 | 6.66 | -1.000 | window lower |
| prestashop-day | 0.00 | 2.01 | -1.000 | window lower |
| superloon | 0.00 | 1.00 | -1.000 | window lower |
| supernova-remnant | 0.00 | 2.80 | -1.000 | window lower |
| trip | 0.00 | 4.00 | -1.000 | window lower |
| wifi-connection-ibiza | 0.00 | 1.21 | -1.000 | window lower |
| work-better-with-logitech | 0.00 | 1.96 | -1.000 | window lower |
| corey-taylor-culture-head-official-music-video | 1.50 | 17.31 | -0.913 | window lower |
| oncode-institute | 4.50 | 2.41 | 0.864 | window higher |
| spec-ad-for-nikec | 3.00 | 21.84 | -0.863 | window lower |
| young-marketers-2 | 15.00 | 8.07 | 0.859 | window higher |
| town-portal-vanitas | 1.50 | 8.29 | -0.819 | window lower |
| mr-robot-title-design-unofficial | 3.00 | 1.67 | 0.800 | window higher |
| one-who-steals | 12.00 | 6.67 | 0.798 | window higher |
| dark-room | 7.50 | 35.72 | -0.790 | window lower |
| broomsticks-on-broadway-1 | 3.00 | 14.01 | -0.786 | window lower |
| holi-animation | 3.00 | 13.53 | -0.778 | window lower |
| comertial-fake-gameplay-for-mobile-game-1 | 3.00 | 10.00 | -0.700 | window lower |
| movements-space-above-feat-boyboy | 3.00 | 9.65 | -0.689 | window lower |
| frank-riggio-tttt | 1.50 | 4.57 | -0.672 | window lower |
| bam-is-back | 4.50 | 2.70 | 0.668 | window higher |
| kontroll | 108.00 | 65.05 | 0.660 | window higher |
| mediamonks-animation-reel-intro-1 | 78.00 | 47.12 | 0.655 | window higher |
| plan-a-opener-rudaw-media-network | 6.00 | 3.65 | 0.645 | window higher |
| roves-8th-birthday | 36.00 | 22.03 | 0.634 | window higher |
| an-endless-circle | 9.00 | 5.51 | 0.633 | window higher |
| fully-cg-audi-r8-commercial | 6.00 | 3.69 | 0.626 | window higher |
| chantecaille-global-lip-creme-launch-campaign | 3.00 | 7.98 | -0.624 | window lower |
| i-am-intersex | 3.00 | 7.82 | -0.617 | window lower |
| mirage | 6.00 | 15.49 | -0.613 | window lower |
| bourse | 96.00 | 59.84 | 0.604 | window higher |
| httpsvimeocom316586329 | 6.00 | 3.75 | 0.602 | window higher |
| studio-i-towards-a-new-museum | 10.50 | 25.40 | -0.587 | window lower |
| golden-bamboo | 18.00 | 11.46 | 0.570 | window higher |
| brompton-house-home-of-baking | 115.50 | 73.63 | 0.569 | window higher |
| bloom | 6.00 | 13.88 | -0.568 | window lower |
| mellowsoda-vision | 3.00 | 1.92 | 0.564 | window higher |
| 24hmotion | 45.00 | 101.63 | -0.557 | window lower |
| particle-universe-collaboration-with-flank-audio | 25.50 | 16.50 | 0.546 | window higher |
| bullpadel-hack-05-aero | 18.00 | 38.58 | -0.533 | window lower |
| 4uplayer-mvp-live-intro | 1.50 | 3.20 | -0.531 | window lower |
| hybrid-creature | 6.00 | 3.94 | 0.523 | window higher |
| samsara | 1.50 | 3.11 | -0.517 | window lower |
| cartoon-network-sequencer-id-apple-onion | 26.67 | 53.89 | -0.505 | window lower |
| christies-luxury-week-3 | 18.00 | 11.97 | 0.504 | window higher |
| galeecha | 9.00 | 5.99 | 0.503 | window higher |
| nobull-journey-2-1 | 6.00 | 3.99 | 0.502 | window higher |
| yandex-lavka-in-yekaterinburg-1 | 12.00 | 7.99 | 0.502 | window higher |
| iso-extremely-flamable | 3.00 | 2.00 | 0.501 | window higher |
| eni | 15.00 | 10.00 | 0.500 | window higher |
| the-us-is-missing-out-on-walkable-cities | 60.00 | 40.07 | 0.498 | window higher |
| 2020-peace-elite-league-season3-1 | 10.50 | 20.81 | -0.495 | window lower |
| perseverance | 9.00 | 6.04 | 0.490 | window higher |
| rawayana-welcome-to-el-sur | 48.00 | 32.29 | 0.487 | window higher |
| covid-xix-beat-the-virus | 1.50 | 1.01 | 0.486 | window higher |
| the-mini-vision-urbanaut-wanderlust | 6.00 | 4.04 | 0.484 | window higher |
| fate | 6.00 | 11.40 | -0.474 | window lower |
| five | 18.00 | 12.26 | 0.468 | window higher |
| play-its-cool | 27.00 | 18.49 | 0.460 | window higher |
| httpsramonandpedrowetransfercomdownloadsf91e7b36fffad702ab46f80983f7cd84202109141127560ca61e | 27.00 | 18.53 | 0.457 | window higher |
| bbc-world-service-designing-for-global-users | 9.00 | 16.29 | -0.448 | window lower |
| inspired-by-xiaomi-mi-10-pro-1 | 12.00 | 21.66 | -0.446 | window lower |
| 10-to-the-64th-power | 3.00 | 5.39 | -0.443 | window lower |
| mate | 10.50 | 18.85 | -0.443 | window lower |
| doppl-2 | 7.50 | 13.43 | -0.441 | window lower |
| z-song | 37.50 | 26.03 | 0.440 | window higher |
| from-concept-to-completion | 3.00 | 5.34 | -0.439 | window lower |
| toss-money-card | 8.00 | 5.57 | 0.437 | window higher |
| nike-air-max-95000 | 6.00 | 4.18 | 0.436 | window higher |
| catharsis-2 | 3.00 | 5.25 | -0.428 | window lower |
| love-yourself | 10.50 | 7.39 | 0.421 | window higher |
| semrush-enterprise | 4.50 | 7.76 | -0.420 | window lower |
| hard-to-starboard | 16.50 | 11.64 | 0.418 | window higher |
| aphex-twin-4 | 30.00 | 51.48 | -0.417 | window lower |
| dof-motion-brandbook | 93.00 | 65.63 | 0.417 | window higher |
| dracodraco-1 | 3.00 | 5.13 | -0.415 | window lower |
| flodesk-case-study | 1.50 | 1.06 | 0.414 | window higher |
| sweet | 36.00 | 25.47 | 0.413 | window higher |
| junge-akademie-1 | 10.00 | 16.88 | -0.407 | window lower |
| beter-the-original-brush | 24.00 | 17.07 | 0.406 | window higher |
| van-mooff-s3-aluminum | 36.00 | 25.61 | 0.406 | window higher |
| staypes-5 | 4.50 | 7.57 | -0.405 | window lower |
| after-all | 37.50 | 26.73 | 0.403 | window higher |
| genesis-vision-2 | 3.00 | 5.00 | -0.401 | window lower |
| just-dream-it-we-built-that | 8.00 | 5.73 | 0.397 | window higher |
| horizon | 4.50 | 3.23 | 0.393 | window higher |
| motion-design-reel-main-titles | 18.00 | 29.08 | -0.381 | window lower |
| get-creative | 102.00 | 163.56 | -0.376 | window lower |
| feed-the-urge | 6.00 | 9.60 | -0.375 | window lower |
| spotify-for-metalheads | 4.50 | 7.20 | -0.375 | window lower |
| legacy-meets-innovation | 30.00 | 21.84 | 0.374 | window higher |
| bullpadel-vertex-04 | 159.00 | 115.74 | 0.374 | window higher |
| dhl-date | 18.00 | 13.12 | 0.372 | window higher |
| university-instructions-for-use | 27.00 | 19.72 | 0.369 | window higher |
| anymotion-festival-2019-opening-titles | 54.00 | 39.48 | 0.368 | window higher |
| its-still-being-written | 25.50 | 18.65 | 0.367 | window higher |
| httpsvimeocom990284238sharecopy | 63.00 | 99.47 | -0.367 | window lower |
| aj-mitchell-burn-music-video-1 | 12.00 | 18.86 | -0.364 | window lower |
| bioo-3-techs-by-kutuko | 10.50 | 7.72 | 0.360 | window higher |
| mission-m101 | 33.00 | 51.33 | -0.357 | window lower |
| everyday-waves | 97.50 | 71.86 | 0.357 | window higher |
| extraordinary | 9.00 | 6.64 | 0.355 | window higher |
| speed-chord | 13.50 | 20.88 | -0.353 | window lower |
| bio-bar-mad-campaign | 24.00 | 36.98 | -0.351 | window lower |
| get-started-to-voyage | 1.50 | 1.11 | 0.348 | window higher |
| kconex | 30.00 | 45.34 | -0.338 | window lower |
| elan-vital | 22.50 | 33.87 | -0.336 | window lower |
| x-bolt-2-speed | 15.00 | 11.23 | 0.335 | window higher |
| beatsbydre-ad | 8.00 | 6.01 | 0.330 | window higher |
| teflon-reimagined | 6.00 | 4.52 | 0.328 | window higher |
| lucky-penny | 102.00 | 76.81 | 0.328 | window higher |
| gummy-gas-crisis | 28.50 | 21.47 | 0.328 | window higher |
| fritz-kola-founders-story | 81.00 | 61.10 | 0.326 | window higher |
| invisible-bauhaus-dessau-caught-up-by-hatred | 3.00 | 2.27 | 0.323 | window higher |
| cosmo-journey | 9.00 | 6.81 | 0.322 | window higher |
| youth-route | 6.00 | 4.54 | 0.322 | window higher |
| promax-bda-rome-2018-opener | 16.50 | 24.18 | -0.318 | window lower |
| funda | 42.00 | 31.91 | 0.316 | window higher |
| krockio-manage-better-and-deliver-faster | 28.50 | 21.68 | 0.315 | window higher |
| entropy | 1.50 | 2.18 | -0.312 | window lower |
| edpon-app | 18.00 | 13.76 | 0.308 | window higher |
| music-unites-herbie-hancock-kamasi-washington-in-conversation | 97.50 | 74.68 | 0.305 | window higher |
| rechannel-marketing-a-function | 3.00 | 2.30 | 0.302 | window higher |
| very-noise | 22.50 | 32.13 | -0.300 | window lower |
| augmented-reality-blade-runner-ost-cover | 1.50 | 2.14 | -0.299 | window lower |
| freedom | 18.00 | 13.92 | 0.293 | window higher |
| moondog-birds-lament-shani-diluka | 21.00 | 16.28 | 0.290 | window higher |
| disenchanted | 30.00 | 42.25 | -0.290 | window lower |
| miami-music-festival-2020 | 30.00 | 23.28 | 0.289 | window higher |
| rest-before-the-light-and-breath-to-reach-the-light | 1.50 | 2.11 | -0.288 | window lower |
| thunder-challenge-entry | 30.00 | 42.05 | -0.287 | window lower |
| a-green-plan-for-our-cities-1 | 4.50 | 6.26 | -0.281 | window lower |
| quarantine-loops | 13.50 | 18.76 | -0.281 | window lower |
| creative-jobs | 7.50 | 10.39 | -0.278 | window lower |
| rock-roll-goes-in-circles | 19.50 | 26.96 | -0.277 | window lower |
| httpsvimeocom655042507 | 6.00 | 4.70 | 0.277 | window higher |
| future-relics-tp-01 | 4.50 | 3.53 | 0.276 | window higher |
| be-not-afraid-ezekiel-1 | 6.00 | 8.25 | -0.273 | window lower |
| aescripts-aeplugins-cyber-monday | 48.00 | 65.86 | -0.271 | window lower |
| manage-customers-from-the-palm-of-your-hand | 7.50 | 10.28 | -0.270 | window lower |
| thoughtspot-beyond-2020-conference-open | 12.00 | 9.45 | 0.270 | window higher |
| dreamdoor | 38.00 | 29.95 | 0.269 | window higher |
| vsgoods | 78.00 | 61.63 | 0.266 | window higher |
| stay-home | 12.00 | 16.33 | -0.265 | window lower |
| the-fall | 70.50 | 55.77 | 0.264 | window higher |
| httpsvimeocom748777370 | 6.00 | 4.78 | 0.256 | window higher |
| ai-text-intro | 18.00 | 14.35 | 0.254 | window higher |
| httpsvimeocom560412242 | 22.50 | 17.95 | 0.253 | window higher |
| david-guerrero-for-emeerree-part-i | 16.00 | 12.78 | 0.252 | window higher |
| landfill-2 | 33.00 | 26.36 | 0.252 | window higher |
| loujey-zidi-2d-animation-intro | 120.00 | 95.88 | 0.252 | window higher |
| baltimore-ravens-uniform-reveal | 40.50 | 54.06 | -0.251 | window lower |
| cariuma-catiba-x-berrics-release | 9.00 | 12.00 | -0.250 | window lower |

| id | window_rank | full_rank | position_change | window_cuts_per_min | full_cuts_per_min |
| --- | --- | --- | --- | --- | --- |
| cyberpunk-2088 | 426 | 145 | 281 | 0.00 | 25.90 |
| dark-room | 330 | 98 | 232 | 7.50 | 35.72 |
| spec-ad-for-nikec | 403 | 176 | 227 | 3.00 | 21.84 |
| corey-taylor-culture-head-official-music-video | 409 | 228 | 181 | 1.50 | 17.31 |
| studio-i-towards-a-new-museum | 298 | 150 | 148 | 10.50 | 25.40 |
| holi-animation | 393 | 265 | 128 | 3.00 | 13.53 |
| broomsticks-on-broadway-1 | 384 | 259 | 125 | 3.00 | 14.01 |
| bullpadel-hack-05-aero | 210 | 88 | 122 | 18.00 | 38.58 |
| httpsvimeocom528258339 | 221 | 339 | -118 | 18.00 | 7.72 |
| mirage | 355 | 247 | 108 | 6.00 | 15.49 |
| the-hidden-life-of-rosa-parks | 59 | 165 | -106 | 51.00 | 22.55 |
| inspired-by-bauhaus | 222 | 327 | -105 | 18.00 | 8.14 |
| fork | 61 | 163 | -102 | 49.50 | 23.08 |
| motion-design-reel-main-titles | 226 | 125 | 101 | 18.00 | 29.08 |
| cartoon-network-sequencer-id-apple-onion | 154 | 54 | 100 | 26.67 | 53.89 |
| lumbre-brand-animation | 225 | 324 | -99 | 18.00 | 8.59 |
| inspired-by-xiaomi-mi-10-pro-1 | 277 | 180 | 97 | 12.00 | 21.66 |
| town-portal-vanitas | 421 | 325 | 96 | 1.50 | 8.29 |
| naturgy-ecoeasy-20-spot | 228 | 321 | -93 | 18.00 | 8.99 |
| 2020-peace-elite-league-season3-1 | 289 | 197 | 92 | 10.50 | 20.81 |
| (+347 more rank changes in `aggregate.json`) | | | | | |

## Published-still evidence (single-frame only)

Separate lane. A published poster still is not a video frame: these numbers are single-frame image metrics, carry no motion, cut, pacing, or timing evidence, and are never used in the video aggregates above.

- n: 1901
- decode size: stills are measured at the aspect-preserving `160×90` fit; the source dimensions stay in `img_w×img_h`, so the decode size is derived from the source aspect, not stored per record.

| source_img | decode | stills |
| --- | --- | --- |
| 1920x1080 | 160x90 | 875 |
| 3840x2160 | 160x90 | 133 |
| 2560x1440 | 160x90 | 57 |
| 1080x1080 | 90x90 | 28 |
| 1920x1920 | 90x90 | 24 |
| 1080x1920 | 51x90 | 23 |
| 1318x766 | 155x90 | 21 |
| 1600x900 | 160x90 | 21 |
| 1280x720 | 160x90 | 18 |
| 1080x1350 | 72x90 | 14 |
| 8000x4500 | 160x90 | 12 |
| 1920x800 | 160x67 | 10 |
| 4000x2250 | 160x90 | 10 |
| 1400x788 | 160x90 | 9 |
| 960x540 | 160x90 | 9 |
| 1200x675 | 160x90 | 8 |
| 2000x2000 | 90x90 | 8 |
| 1920x1081 | 160x90 | 6 |
| 1921x1081 | 160x90 | 6 |
| 1080x608 | 160x90 | 5 |
| (+508 more source/decode pairs) | — | — |

- stills carrying no quality flag (used for colour aggregates): 1878
- median meanDisplayLumaProxy: 0.4002

| dominant_hue_family | stills |
| --- | --- |
| blue | 361 |
| cyan | 90 |
| green | 83 |
| magenta | 130 |
| neutral | 526 |
| orange | 351 |
| purple | 83 |
| red | 178 |
| yellow | 76 |

## Unreadable records

None.

## Explicit non-claims

- No style, aesthetic quality, mood, lighting, camera/lens, editorial intent, authorship, identity, or creative-origin inference is made from these numbers.
- Display-RGB luma/saturation and cut candidates are numeric proxies only, not semantic labels.
- Windows are sampled and census values are film-level; a window rate is a sample, not a film rate, and census cut candidates are still scene-score exceedances rather than verified edits.
- Public availability is not a licence: `rightsStatus` remains `review-required`, and reuse needs its own review.
- Vimeo-derived rows are single published poster stills, not video frames, and carry no motion, cut, pacing, or timing evidence.
- Catalog metadata (title, studio, category, awards, scores) is self-reported by the awards site and is not independently verified.
- Downloaded media, frames, thumbnails, and audio are never retained.
