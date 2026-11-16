# Promonews — measured video and still evidence report

This deliverable tabulates only what the committed evidence records contain: Promonews catalogue metadata, sampled source-PTS numeric probes of the public YouTube rendition, and one measured, published poster still per item where present. It makes no aesthetic, stylistic, intentional, authorship, or quality claim.

## Provenance

- Catalog videos collected: 17805
- Catalog `hits.total` reported: 17805
- Catalog complete (all reported hits collected): True
- Video-measured records: 213
- Unique video media after dedupe: 213 (0 extra record(s) in 0 duplicate group(s))
- Still-measured records: 16908
- Still-only records (no matching video record): 16695
- Skipped, no usable image: 585
- Skipped (index context): 17415
- Failed acquisitions (index context): 311
- Unreadable records: 0
- generatedAt: 2026-11-12T19:16:52.961999Z
- Provider split (catalog): none x 498, other x 1673, vimeo x 3448, youtube x 12186
- Provider split (measured stills): none x 331, other x 1537, vimeo x 3204, youtube x 11836
- Provider split (measured videos): youtube x 213
- Skip reasons (stills index): no-usable-poster x 585, resume-existing-record x 16829, unsafe-slug: identifier is not a safe file name x 1
- Skip reasons (video index): no-video-reference x 1, provider-refused x 125, resume-existing-record x 139, unsupported-vimeo x 25
- `--top 20` applied: the first 20 of 213 video-measured rows are tabulated below; `aggregate.json` holds all.
- `--top 20` applied: the first 20 of 16908 measured stills are tabulated below; `aggregate.json` holds all.

Reproduce the inputs and this report with:

```bash
python scripts/research_promonews.py catalog --out research/analysis/promonews/catalog.json
python scripts/research_promonews.py collect --catalog research/analysis/promonews/catalog.json --out-dir research/analysis/promonews --acknowledge-rights
python scripts/research_promonews.py stills --catalog research/analysis/promonews/catalog.json --out-dir research/analysis/promonews --resume
python scripts/research_promonews.py report --out-dir research/analysis/promonews --top 20
```

## Per-video analysis

213 video-measured record(s), newest catalogue row first. All columns are numeric record fields from the sampled source-PTS windows of the public YouTube rendition; `duration_s` is the decoded local source duration, not a catalogue value.

| nid | slug | title | provider | published | duration_s | resolution | download_mb | windows | coverage_pct | candidates_n | sampled_cut_candidates_per_min | full_cuts_per_min | full_vs_window | ci95 | burst | gap_frames | within_shot_pairs | cut_sep_pairs | delta_basis_pairs | validity | mean_luma | mean_sat | delta_per_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 96941 | sports-team-billy-kris-r | Sports Team 'Billy' by Kris R | youtube | 2026-11-11 | 160.50 | 1280x720 | 19.3 | 4 | 24.9 | 19 | 28.50 | 21.68 | +31% | 15.49-46.86 | 0.105 | 29.0 | 28 | 16 | 28 | low-coverage | 0.1722 | 0.3239 | 0.1464 |
| 96852 | these-wicked-rivers-rise-conor-lee-butler | These Wicked Rivers 'Rise' by Conor Lee Butler | youtube | 2026-11-11 | 252.45 | 1280x550 | 25.5 | 4 | 15.8 | 17 | 25.50 | 24.96 | +2% | 11.92-45.05 | 0.000 | 44.5 | 27 | 17 | 27 | low-coverage | 0.2554 | 0.4602 | 0.1227 |
| 96929 | missu-sweat-loys-assal | MISSU 'Sweat' by Loys Assal | youtube | 2026-11-10 | 165.21 | 1280x720 | 22.2 | 4 | 24.2 | 4 | 6.00 | 10.90 | -45% | 0.96-16.81 | 0.000 | 79.0 | 40 | 4 | 40 | low-coverage | 0.1562 | 0.3334 | 0.1166 |
| 96904 | frankie-and-deadbeats-you-are-all-mine-night-lubos-vacke | Frankie And The Deadbeats 'You Are All Mine For The Night' by Lubos Vacke | youtube | 2026-11-10 | 246.06 | 1048x720 | 14.6 | 4 | 16.3 | 0 | 0.00 | 0.49 | -100% | 0.00-5.53 | — | — | 44 | 0 | 44 | low-coverage, no-cuts-observed | 0.0704 | 0.4915 | 0.0295 |
| 96857 | fontaines-dc-japan-luna-carmoon | Fontaines D.C. 'Japan' by Luna Carmoon | youtube | 2026-11-10 | 216.34 | 1280x720 | 19.4 | 4 | 18.5 | 6 | 9.00 | 7.49 | +20% | 2.99-20.16 | 0.000 | 103.0 | 38 | 6 | 38 | low-coverage | 0.1604 | 0.3139 | 0.0859 |
| 96924 | olivia-rodrigo-take-me-home-4-christmas-fiona-jane-burgess | Olivia Rodrigo 'Take Me Home (4 Christmas)' by Fiona Jane Burgess | youtube | 2026-11-09 | 187.76 | 960x720 | 16.5 | 4 | 21.3 | 27 | 40.50 | 31.64 | +28% | 23.48-63.21 | 0.148 | 29.0 | 23 | 21 | 23 | low-coverage | 0.2759 | 0.4152 | 0.0682 |
| 96914 | morrissey-kerching-kerching-lewis-cater | Morrissey 'Kerching Kerching' by Lewis Cater | youtube | 2026-11-09 | 185.46 | 1048x720 | 6.4 | 4 | 21.6 | 4 | 6.00 | 6.15 | -2% | 0.96-16.81 | 0.000 | 175.0 | 40 | 4 | 40 | low-coverage | 0.1162 | 0.2861 | 0.0388 |
| 96890 | dove-rd-fantasy-matt-burns | dove rd 'Fantasy' by Matt Burns | youtube | 2026-11-09 | 194.19 | 1280x720 | 30.4 | 4 | 20.6 | 10 | 15.00 | 21.63 | -31% | 3.25-33.95 | 0.300 | 64.0 | 36 | 8 | 36 | low-coverage | 0.2798 | 0.2679 | 0.0640 |
| 96864 | van%C3%A8s-bad-girl-shy-salma-labib | VANÈS 'Bad Girl Shy' by Salma Labib | youtube | 2026-11-06 | 196.00 | 1280x676 | 23.6 | 4 | 20.4 | 4 | 6.00 | 15.92 | -62% | 0.96-16.81 | 0.000 | 110.0 | 40 | 4 | 40 | low-coverage | 0.1335 | 0.5323 | 0.0683 |
| 96846 | omah-lay-artificial-happiness-nwspk | Omah Lay 'Artificial Happiness' by NWSPK  | youtube | 2026-11-06 | 186.41 | 1048x720 | 16.8 | 4 | 21.5 | 9 | 13.50 | 22.85 | -41% | 3.43-30.17 | 0.000 | 74.0 | 35 | 9 | 35 | low-coverage | 0.2660 | 0.0841 | 0.0911 |
| 96841 | tinashe-pillow-fight-zac-dov-wiesel | Tinashe 'Pillow Fight' by Zac Dov Wiesel | youtube | 2026-11-03 | 151.88 | 1280x720 | 11.8 | 4 | 26.3 | 24 | 36.00 | 28.44 | +27% | 23.07-53.57 | 0.000 | 35.0 | 22 | 22 | 22 | — | 0.2030 | 0.1805 | 0.0885 |
| 96844 | ear-candy-clean-clothes-rob-ulitski | Ear Candy 'Clean Clothes' by Rob Ulitski | youtube | 2026-11-03 | 167.60 | 1280x720 | 35.7 | 4 | 23.9 | 19 | 28.50 | 36.16 | -21% | 16.96-44.78 | 0.263 | 49.5 | 29 | 15 | 29 | low-coverage | 0.4442 | 0.3813 | 0.1273 |
| 96833 | waterbaby-memory-be-blade-felix-scheynius | waterbaby 'Memory Be A Blade' by Felix Scheynius | youtube | 2026-11-03 | 265.10 | 1280x720 | 22.8 | 4 | 15.1 | 5 | 7.50 | 4.07 | +84% | 2.44-17.50 | 0.000 | 1797.5 | 39 | 5 | 39 | low-coverage | 0.2001 | 0.2018 | 0.0673 |
| 96830 | chloe-qisha-he-likes-boys-bedroom | Chloe Qisha 'He Likes Boys' by Bedroom | youtube | 2026-11-02 | 214.53 | 1032x720 | 23.5 | 4 | 18.6 | 5 | 7.50 | 4.47 | +68% | 0.00-29.87 | 0.400 | 35.5 | 40 | 4 | 40 | low-coverage | 0.0628 | 0.5987 | 0.0661 |
| 96822 | them-i-say-you-dont-jim-longden | Them & I 'Say You Don't' by Jim Longden | youtube | 2026-11-02 | 157.38 | 1280x720 | 12.6 | 4 | 25.4 | 0 | 0.00 | 0.76 | -100% | 0.00-5.53 | — | — | 44 | 0 | 44 | no-cuts-observed | 0.0900 | 0.6938 | 0.0550 |
| 96774 | tom-grennan-wrapped-gold-freddie-cattaneo | Tom Grennan 'Wrapped In Gold' by Freddie Cattaneo | youtube | 2026-10-30 | 198.14 | 1080x720 | 18.3 | 4 | 20.2 | 7 | 10.50 | 7.27 | +44% | 4.22-21.63 | 0.000 | 42.0 | 37 | 7 | 37 | low-coverage | 0.1067 | 0.3919 | 0.0651 |
| 96807 | james-blunt-circles-jack-howard | James Blunt 'Circles' by Jack Howard | youtube | 2026-10-30 | 239.37 | 1034x720 | 23.9 | 4 | 16.7 | 8 | 12.00 | 13.28 | -10% | 1.58-29.79 | 0.000 | 70.0 | 36 | 8 | 36 | low-coverage | 0.2412 | 0.3594 | 0.0859 |
| 96811 | telemakus-w-sparklmami-bigboihums-feat-tristan-cappel-hands-rejoice-mackai-sharp | Telemakus w Sparklmami, Bigboihums (feat. Tristan Cappel) 'Hands Rejoice!' by Mackai Sharp | youtube | 2026-10-30 | 124.85 | 1080x720 | 22.2 | 4 | 32.0 | 18 | 27.00 | 35.08 | -23% | 13.95-45.59 | 0.333 | 53.0 | 29 | 15 | 29 | — | 0.2411 | 0.6212 | 0.0920 |
| 96781 | texas-another-way-cry-niall-trask | Texas 'Another Way To Cry' by Niall Trask | youtube | 2026-10-29 | 232.39 | 1280x720 | 29.1 | 4 | 17.2 | 9 | 13.50 | 15.75 | -14% | 4.25-28.80 | 0.000 | 112.5 | 35 | 9 | 35 | low-coverage | 0.3357 | 0.3022 | 0.0702 |
| 96805 | kinlaw-ride-ride-barbara-anastacio | Kinlaw 'Ride The Ride' by Barbara Anastacio | youtube | 2026-10-29 | 232.78 | 960x720 | 32.6 | 4 | 17.2 | 4 | 6.00 | 17.53 | -66% | 1.63-15.36 | 0.000 | 1772.0 | 40 | 4 | 40 | low-coverage | 0.2276 | 0.3051 | 0.0546 |

| download_method | provider | video_url |
| --- | --- | --- |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=XSUIqQsN-xo |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=K-gkgSYAfJo |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=cPAiVP4ULn8 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=uepLE_1k-4o |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=GPNbnromGgk |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=uXymCnWk9LI |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=g0qziBV338c |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=kGlw6QHw0Z4 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=8Vq7VfLzGNU |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=DCyFQHeMqtY |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=6a2g12aE8kI |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=yIpjaCH0jTg |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=OFlA8o7HDV0 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=RsyyuwIL3j4 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=lfA2PPZd608 |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=C5GRwUV3SPQ |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=jQoZl3Yj1hQ |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=j5J1Ln_tgck |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=jIAvWrEYIMA |
| ytdlp-merge | youtube | https://www.youtube.com/watch?v=aX9wjfRyBQg |

## Aggregates (video-measured records only)

Every number in this section is computed ONLY over the video-measured records tabulated above. Published stills, including still-only rows, never enter the motion, cut, luma, or saturation aggregates.

All minima and maxima are computed over `rankable` records only and name the record id and validity flags.

Unique records before dedupe: 213; after dedupe: 213 (0 duplicate extra record(s) collapsed).

Rankable records: 188 of 213 unique; excluded as non-rankable: 25.

| metric | n | min (record; flags) | median | max (record; flags) |
| --- | --- | --- | --- | --- |
| duration_s | 188 | 117.68 (no-na-rollerblade-fa-fon; —) | 214.58 | 576.67 (studio20-live-metalcraft-pedro-takahashi; low-coverage) |
| mean_luma | 188 | 0.0612 (dexter-newsagent-fantasy-iris-luz; —) | 0.2272 | 0.5954 (final-call-life-party-evan-brandow; low-coverage) |
| mean_sat | 188 | 0.0000 (alexis-taylor-colombia-ian-svenonius; low-coverage) | 0.3524 | 0.9718 (lonnie-gunn-taxidermy-swan-lea-otovic; low-coverage) |
| delta_per_s | 188 | 0.0052 (kelsey-lu-portrait-lady-fire-savanah-leaf; low-coverage) | 0.0818 | 0.1965 (fat-dog-cancel-me-im-tired-fat-dog-james-winstanley-lloyd-young; low-coverage) |
| candidates_n | 188 | 0 (do%CC%81ttirx-live-session-voli-whisperintrovert-luigi-calabrese-fil-thorpe; low-coverage, no-cuts-observed) | 11 | 43 (say-now-hot-talking-vasso-vu; low-coverage) |
| sampled_cut_candidates_per_min | 188 | 0.00 (do%CC%81ttirx-live-session-voli-whisperintrovert-luigi-calabrese-fil-thorpe; low-coverage, no-cuts-observed) | 16.50 | 64.50 (say-now-hot-talking-vasso-vu; low-coverage) |
Excluded as non-rankable (largest first):

| record | sampled_cut_candidates_per_min | validity |
| --- | --- | --- |
| liars-ice-pick-kalamazoo-angus-andrew | 639.00 | burst-heavy, low-coverage, non-edit-scene-change |
| u2-silencio-cliqua | 192.00 | burst-heavy, sparse-delta-basis |
| blondie-spectral-eyes-rob-roth | 165.00 | burst-heavy, low-coverage |
| anna-meredith-dusky-ewan-jones-morris | 159.00 | burst-heavy, low-coverage, non-edit-scene-change |
| fortuno-alive-tobi-omola-ja%E2%80%99lisa-arnold | 157.50 | burst-heavy, low-coverage, non-edit-scene-change |

Coverage-weighted caveat: 8520.0 sampled seconds cover 47617.9 runtime seconds (17.9%). Aggregates describe the sampled windows, not the full films. Where a full-film census record exists, `full_cuts_per_min` is film-level and `full_vs_window` states the difference (see `## Full-film census`).

## Comparability

- poolable: `false`
- comparable within: same site, same rendition, same runtime band, non-burst, >=25% coverage
- not comparable to: other sites, other renditions, full-film claims derived from window rates

Caveats:

- Promonews: poolable is false; every number describes this site's measured sample only.
- 213 of 17805 catalogue items were measured (1.196%) by YouTube availability and recency; Vimeo entries are skipped as unsupported.
- Measured rows are not a random sample: availability and recency select them, so cross-site pooling is invalid.
- Provider families are not interchangeable: youtube x 213.
- Renditions differ by site and record: platform-encoded YouTube renditions; Vimeo was never fetched or probed.
- Measured renditions vary by resolution (1280x720 x 121, 960x720 x 31, 1080x720 x 15, 1048x720 x 10, 1190x720 x 4, 1200x720 x 4, 1280x676 x 4, 1034x720 x 2, +19 more), frame rate (25 x 113, 24 x 63, 23.976 x 29, 29.97 x 2, 30 x 2, 23.7644 x 1, 50 x 1, 59.9401 x 1, +1 more) and bitrate (0.9 x 32, 1.0 x 29, 0.8 x 27, 1.1 x 21, 0.7 x 20, 1.2 x 12, 1.3 x 10, 0.5 x 9, +16 more), so the sample is not a controlled transform.
- Window coverage is sampled, not full-film: median 18.6334% per record, p10 13.55514%, p90 25.39226%; 59.15493% of rows are below 20% and 2.347418% below 10%; median unobserved gap between windows is 51.0 s. Window rates describe those windows; a full-film census, when present, is reported separately.
- 0 extra record(s) in 0 duplicate group(s) share media; unique media after dedupe is 213.
- Still/video overlap: 16908 still record(s), 16695 still-only, are a separate single-frame lane and never enter these aggregates.

## Coverage

Per-record coverage distribution over the deduped records. The unobserved gap is the median time between consecutive sampled windows, derived from runtime, window count and sampled seconds.

| statistic | coverage_pct |
| --- | --- |
| min | 6.9 |
| p10 | 13.6 |
| median | 18.6 |
| p90 | 25.4 |
| max | 34.0 |
| below 20% | 59.2% |
| below 10% | 2.3% |
| median unobserved gap between windows | 51.0 s |

## Full-film census

Film-level evidence: 212 of 213 video-measured records (99.5%) on Promonews have a full-runtime census record. Census values are **film-level**: every cut candidate in the file was counted and the appearance series is time-weighted over the whole runtime, so `decodeCoverageFraction` is 1.000000. The `full_cuts_per_min` column is that film-level rate; every `sampled_cut_candidates_per_min` value remains a sample of its windows.

Census cut candidates are still ffmpeg scene-score exceedances, not verified edits; fast movement, flashes, transitions and compression can exceed the threshold. A `strobe` record's rate describes strobe-like candidate density and is **not comparable to a cut rate**, so strobe records are excluded from the range below and reported separately.

| statistic | full_cuts_per_min (non-strobe) |
| --- | --- |
| n | 188 |
| min | 0.00 |
| p10 | 4.93 |
| median | 19.32 |
| p90 | 36.38 |
| max | 66.43 |

Range endpoints: min 0.00 (`do%CC%81ttirx-live-session-voli-whisperintrovert-luigi-calabrese-fil-thorpe`), max 66.43 (`300skullsandcounting-jenny-sparks-ballad-st-nicks-park-callum-hansen-and-hal`); n counts non-strobe records only.

Strobe block (never pooled with the cut-rate range above): 24 record(s), listed by id below. Its own range is min 1.24, median 50.74, max 590.59.

| strobe id | full_cuts_per_min | median_gap_frames | burst_fraction |
| --- | --- | --- | --- |
| anna-meredith-dusky-ewan-jones-morris | 56.84 | 3.0 | 0.953 |
| au-ra-e-motion-andy-mihov | 53.37 | 7.0 | 0.606 |
| blondie-spectral-eyes-rob-roth | 177.53 | 3.0 | 0.874 |
| blue-lab-beats-ft-denzel-himself-hear-it-pop-sergi-fiddes-xammar | 24.46 | 21.0 | 0.588 |
| bricknasty-honey-bee-talia-beale | 27.78 | 9.0 | 0.709 |
| chuck-strangers-g-pack-broken-antenna | 34.93 | 6.5 | 0.589 |
| cikho-fell-again-original-concrete-club | 32.51 | 25.0 | 0.531 |
| daisy-maybe-box-god-thomas-harrington-rawle | 82.21 | 5.0 | 0.775 |
| deep-purple-guilt-trippin-tom-readdy-lucy-dawkins | 44.25 | 4.0 | 0.750 |
| dezzie-x-izzpot-x-clavish-any-means-ted-clarke | 7.00 | 36.0 | 0.526 |
| el-roig-stupid-cowboy-claudia-o-sala | 90.99 | 4.0 | 0.777 |
| feu-chatterton-l%E2%80%99%C3%A9tranger-ernest-bouvier-r%C3%A9my-monti-jordan-le-gal%C3%A8ze | 179.02 | 2.0 | 0.977 |
| fontaines-dc-marianne-dave-meyers-cam-erickson | 98.33 | 3.0 | 0.841 |
| fortuno-alive-tobi-omola-ja%E2%80%99lisa-arnold | 134.90 | 2.0 | 0.695 |
| girl-red-blue-isak-jenssen | 86.96 | 2.0 | 0.793 |
| girl-year-above-wet-paint-dylan-friese-greene | 77.52 | 8.0 | 0.565 |
| gurriers-waiting-fisher-thomas-james | 10.68 | 39.0 | 0.533 |
| joe-khalique-brown-junkspace-george-moore-chadwick | 1.24 | 573.0 | 0.667 |
| kilimanjaro-ft-rahh-stumble-sekou-abineri | 28.70 | 12.0 | 0.609 |
| liars-ice-pick-kalamazoo-angus-andrew | 590.59 | 3.0 | 0.983 |
| muse-ft-ellie-goulding-hush-harry-lindley | 11.96 | 7.5 | 0.638 |
| phoebe-bridgers-i-cant-wait-pablo-rochat-and-chris-maggio | 38.07 | 18.0 | 0.570 |
| rora-and-untamed-savage-white-swan-irene-marco-markus-meedt | 48.11 | 7.0 | 0.672 |
| u2-silencio-cliqua | 143.94 | 6.0 | 0.642 |

## Census reconciliation

Window values are samples of the runtime; census values cover the film. Relative error is `(window_rate - full_rate) / full_rate`, so a positive value means the window sample overestimated the film and a negative value means it underestimated it.

- comparable records: 211; skipped for a zero full-film rate: 1
- median |relative error|: 0.212; p90 |relative error|: 0.676; max |relative error|: 3.216
- window estimate off by more than 25%: 92 of 211 (43.6%); window higher on 94 record(s), lower on 117
- ordering changes beyond five positions when ranked by each rate: 152

| id | window_cuts_per_min | full_cuts_per_min | relative_error | direction |
| --- | --- | --- | --- | --- |
| charlie-jeer-jennifer-douglas-reddan | 1.50 | 0.36 | 3.216 | window higher |
| joe-khalique-brown-junkspace-george-moore-chadwick | 4.50 | 1.24 | 2.618 | window higher |
| kelsey-lu-portrait-lady-fire-savanah-leaf | 1.50 | 0.51 | 1.939 | window higher |
| anna-meredith-dusky-ewan-jones-morris | 159.00 | 56.84 | 1.797 | window higher |
| tamino-raven-thibaut-grevet | 22.50 | 8.09 | 1.780 | window higher |
| julia-jacklin-hardest-thing-danny-cohen | 1.50 | 0.59 | 1.547 | window higher |
| myles-smith-hold-me-dark-myles-smith | 25.50 | 10.49 | 1.432 | window higher |
| sugababes-ghost-thomas-james | 60.00 | 27.18 | 1.208 | window higher |
| gurriers-waiting-fisher-thomas-james | 22.50 | 10.68 | 1.106 | window higher |
| cape-cod-x-jamala-lito-maksym-sikalenko-dasha-deriagina | 33.00 | 15.87 | 1.079 | window higher |
| muse-ft-ellie-goulding-hush-harry-lindley | 24.00 | 11.96 | 1.007 | window higher |
| frankie-and-deadbeats-you-are-all-mine-night-lubos-vacke | 0.00 | 0.49 | -1.000 | window lower |
| luther-vandross-house-not-home-christian-padron | 0.00 | 1.86 | -1.000 | window lower |
| them-i-say-you-dont-jim-longden | 0.00 | 0.76 | -1.000 | window lower |
| waterbaby-memory-be-blade-felix-scheynius | 7.50 | 4.07 | 0.841 | window higher |
| phoebe-bridgers-lost-boys-lance-oppenheim-pablo-rochat | 40.50 | 22.27 | 0.818 | window higher |
| dexter-newsagent-fantasy-iris-luz | 7.50 | 4.24 | 0.770 | window higher |
| leon-bridges-talk-it-over-dy | 6.00 | 3.42 | 0.752 | window higher |
| girl-red-blue-isak-jenssen | 22.50 | 86.96 | -0.741 | window lower |
| dezzie-x-izzpot-x-clavish-any-means-ted-clarke | 12.00 | 7.00 | 0.715 | window higher |
| bonobo-me-and-you-inout | 46.50 | 27.65 | 0.682 | window higher |
| chloe-qisha-he-likes-boys-bedroom | 7.50 | 4.47 | 0.676 | window higher |
| kinlaw-ride-ride-barbara-anastacio | 6.00 | 17.53 | -0.658 | window lower |
| van%C3%A8s-bad-girl-shy-salma-labib | 6.00 | 15.92 | -0.623 | window lower |
| kilimanjaro-ft-rahh-stumble-sekou-abineri | 46.50 | 28.70 | 0.620 | window higher |
| gliiico-dont-eat-dont-sleep-jackson-lee-forsythe | 3.00 | 7.31 | -0.589 | window lower |
| rolling-stones-jealous-lover-chris-barrett-luke-taylor | 9.00 | 21.87 | -0.588 | window lower |
| blondshell-violins-sabra-binder | 9.00 | 21.56 | -0.583 | window lower |
| makeup-unpopular-sophia-del-pizzo-rosie-terry-toogood | 16.50 | 10.46 | 0.578 | window higher |
| charlotte-cardin-take-me-back-vincent-ren%C3%A9-lortie | 7.50 | 17.28 | -0.566 | window lower |
| eliza-rose-undercover-lover-jade-ang-jackman | 9.00 | 20.69 | -0.565 | window lower |
| deep-purple-guilt-trippin-tom-readdy-lucy-dawkins | 19.50 | 44.25 | -0.559 | window lower |
| maisie-peters-questions-georgie-cowan-turner | 12.00 | 25.33 | -0.526 | window lower |
| miss-madeline-trip-moon-ben-cole | 48.00 | 31.69 | 0.515 | window higher |
| cara-delevingne-crazy-baby-bradley-j-calder | 19.50 | 12.90 | 0.512 | window higher |
| pink-siifu-ft-ss-slyver-devil%E2%80%99s-advocate%E2%80%99-ludovic-gontrand | 21.00 | 13.94 | 0.507 | window higher |
| missu-outtasight-anastasja-black | 7.50 | 15.13 | -0.504 | window lower |
| rachel-chinouriri-pretty-girls-dora-paphides | 39.00 | 26.36 | 0.479 | window higher |
| jack-harlow-say-hello-luis-rojo | 28.50 | 19.39 | 0.470 | window higher |
| flo-dont-break-her-heart-troy-roscoe | 19.50 | 36.29 | -0.463 | window lower |
| andy-cant-wait-harry-welsh | 12.00 | 22.28 | -0.461 | window lower |
| nothing-thieves-baby-kool-evelyn-maxim-kelly | 42.00 | 28.77 | 0.460 | window higher |
| oscar-band-china-bird-josh-barnes | 7.50 | 13.70 | -0.452 | window lower |
| missu-sweat-loys-assal | 6.00 | 10.90 | -0.449 | window lower |
| tom-grennan-wrapped-gold-freddie-cattaneo | 10.50 | 7.27 | 0.445 | window higher |
| jorja-smith-price-it-all-kc-locke | 4.50 | 8.09 | -0.444 | window lower |
| bella-poarch-stay-gone-osrin | 10.50 | 18.77 | -0.441 | window lower |
| muse-nightshift-superstar-lado-kvataniya | 16.50 | 11.48 | 0.438 | window higher |
| el-roig-stupid-cowboy-claudia-o-sala | 130.50 | 90.99 | 0.434 | window higher |
| bicep-viper-air-and-lemonder-ryan-doubiago | 10.50 | 18.31 | -0.427 | window lower |
| lil-nas-x-world%E2%80%99s-greatest-phillip-youmans | 21.00 | 36.60 | -0.426 | window lower |
| django-django-dirty-hotel-blues-jim-longden | 25.50 | 17.88 | 0.426 | window higher |
| troye-sivan-party-gordon-von-steiner | 48.00 | 33.90 | 0.416 | window higher |
| final-call-life-party-evan-brandow | 1.50 | 2.55 | -0.411 | window lower |
| omah-lay-artificial-happiness-nwspk | 13.50 | 22.85 | -0.409 | window lower |
| lush-duck-face-god-dimitri-papazachariou | 37.50 | 26.98 | 0.390 | window higher |
| gener8ion-storm-romain-gavras | 10.50 | 17.16 | -0.388 | window lower |
| sam-smith-my-guy-haya-waseem | 9.00 | 6.50 | 0.385 | window higher |
| rolling-stones-mr-charm-henry-scholfield | 6.00 | 9.69 | -0.381 | window lower |
| 300skullsandcounting-jenny-sparks-ballad-st-nicks-park-callum-hansen-and-hal | 42.00 | 66.43 | -0.368 | window lower |
| daisy-maybe-box-god-thomas-harrington-rawle | 52.50 | 82.21 | -0.361 | window lower |
| lonnie-gunn-taxidermy-swan-lea-otovic | 7.50 | 11.65 | -0.356 | window lower |
| hunter-bavaro-do-you-still-make-music-mason-treen | 15.00 | 23.19 | -0.353 | window lower |
| kamal-all-my-favourite-people-are-sad-flora-scott-connie-swift | 13.50 | 20.70 | -0.348 | window lower |
| logic1000-ft-christine-and-queens-only-one-dora-paphides | 13.50 | 20.44 | -0.339 | window lower |
| skye-newman-walk-kc-locke | 39.00 | 29.22 | 0.334 | window higher |
| u2-silencio-cliqua | 192.00 | 143.94 | 0.334 | window higher |
| mnek-reverse-douglas-reddan | 13.50 | 20.09 | -0.328 | window lower |
| sada-nu-ocnebob-sali-nikolaishvili-and-sandro-darakhvelidze | 10.50 | 15.54 | -0.324 | window lower |
| charlotte-cardin-memories-i-ii-vincent-ren%C3%A9-lortie | 3.00 | 4.43 | -0.324 | window lower |
| death-above-1979-private-lives-eva-michon | 13.50 | 19.92 | -0.322 | window lower |
| adela-kgb-rachel-dunkel | 13.50 | 19.78 | -0.317 | window lower |
| sports-team-billy-kris-r | 28.50 | 21.68 | 0.314 | window higher |
| bea-ballet-pumps-maxi-mclachlan | 21.00 | 16.03 | 0.310 | window higher |
| hylo-its-not-about-him-james-humby | 9.00 | 12.99 | -0.307 | window lower |
| dove-rd-fantasy-matt-burns | 15.00 | 21.63 | -0.306 | window lower |
| beabadoobee-sun-has-set-jake-erland | 3.00 | 2.30 | 0.305 | window higher |
| chase-status-ft-debbie-gone-too-far-segraphy-joa-spruijt-robin-van-geemen | 15.00 | 11.52 | 0.302 | window higher |
| fontaines-dc-tongue-john-angus-stewart | 3.00 | 4.26 | -0.295 | window lower |
| space-afrika-ft-deu%C3%A9n-if-hell-pablo-dunkerly | 31.50 | 24.35 | 0.294 | window higher |
| cikho-fell-again-original-concrete-club | 42.00 | 32.51 | 0.292 | window higher |
| jamie-t-waist-36-leg-32-charles-gall | 15.00 | 21.04 | -0.287 | window lower |
| rora-and-untamed-savage-white-swan-irene-marco-markus-meedt | 34.50 | 48.11 | -0.283 | window lower |
| olivia-rodrigo-take-me-home-4-christmas-fiona-jane-burgess | 40.50 | 31.64 | 0.280 | window higher |
| lamia-requiem-dream-lamia | 7.50 | 10.37 | -0.277 | window lower |
| jamie-t-3310-rob-thorogood | 7.50 | 10.24 | -0.268 | window lower |
| tinashe-pillow-fight-zac-dov-wiesel | 36.00 | 28.44 | 0.266 | window higher |
| blue-lab-beats-ft-denzel-himself-hear-it-pop-sergi-fiddes-xammar | 18.00 | 24.46 | -0.264 | window lower |
| paris-paloma-silhouette-hill-georgie-cowan-turner | 10.50 | 14.24 | -0.262 | window lower |
| rachel-chinouriri-one-song-away-crying-dora-paphides | 22.50 | 17.93 | 0.255 | window higher |
| viktor-viktoria-man-pet-i-love-wear-jean-paul-gaultier-thomas-hardiman | 40.50 | 32.32 | 0.253 | window higher |
| say-now-hot-talking-vasso-vu | 64.50 | 51.59 | 0.250 | window higher |

| id | window_rank | full_rank | position_change | window_cuts_per_min | full_cuts_per_min |
| --- | --- | --- | --- | --- | --- |
| myles-smith-hold-me-dark-myles-smith | 79 | 166 | -87 | 25.50 | 10.49 |
| tamino-raven-thibaut-grevet | 94 | 179 | -85 | 22.50 | 8.09 |
| girl-red-blue-isak-jenssen | 89 | 8 | 81 | 22.50 | 86.96 |
| cape-cod-x-jamala-lito-maksym-sikalenko-dasha-deriagina | 54 | 132 | -78 | 33.00 | 15.87 |
| deep-purple-guilt-trippin-tom-readdy-lucy-dawkins | 102 | 25 | 77 | 19.50 | 44.25 |
| gurriers-waiting-fisher-thomas-james | 90 | 165 | -75 | 22.50 | 10.68 |
| rolling-stones-jealous-lover-chris-barrett-luke-taylor | 167 | 94 | 73 | 9.00 | 21.87 |
| muse-ft-ellie-goulding-hush-harry-lindley | 84 | 156 | -72 | 24.00 | 11.96 |
| flo-dont-break-her-heart-troy-roscoe | 103 | 35 | 68 | 19.50 | 36.29 |
| maisie-peters-questions-georgie-cowan-turner | 145 | 79 | 66 | 12.00 | 25.33 |
| blondshell-violins-sabra-binder | 161 | 97 | 64 | 9.00 | 21.56 |
| kinlaw-ride-ride-barbara-anastacio | 187 | 123 | 64 | 6.00 | 17.53 |
| lil-nas-x-world%E2%80%99s-greatest-phillip-youmans | 96 | 34 | 62 | 21.00 | 36.60 |
| van%C3%A8s-bad-girl-shy-salma-labib | 193 | 131 | 62 | 6.00 | 15.92 |
| eliza-rose-undercover-lover-jade-ang-jackman | 162 | 103 | 59 | 9.00 | 20.69 |
| sugababes-ghost-thomas-james | 14 | 73 | -59 | 60.00 | 27.18 |
| phoebe-bridgers-lost-boys-lance-oppenheim-pablo-rochat | 34 | 92 | -58 | 40.50 | 22.27 |
| cara-delevingne-crazy-baby-bradley-j-calder | 101 | 153 | -52 | 19.50 | 12.90 |
| andy-cant-wait-harry-welsh | 141 | 91 | 50 | 12.00 | 22.28 |
| bonobo-me-and-you-inout | 20 | 70 | -50 | 46.50 | 27.65 |
| (+132 more rank changes in `aggregate.json`) | | | | | |

## Measured stills

16908 still-measured record(s), ordered by nid then slug. Every number describes one published image, never a video frame.
Quality-flagged stills excluded from the colour distributions: 78 of 16908.
`decode_w`/`decode_h` are the aspect-preserving `160×90` fit; they are derived from the source `img_w`/`img_h` when a record stores no decode size, which is the case for every current record.

| nid | slug | title | provider | categories | genres | img_w | img_h | decode_w | decode_h | img_bytes | mean_luma | mean_sat | hue | edge_density |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 84 | shotter-shoots-psbs-big-cause-then-goes-through-hoops | Shotter shoots PSBs big cause, then goes through hoops | — | — | — | 510 | 266 | 160 | 83 | 167898 | 0.2177 | 0.3079 | blue | 0.0698 |
| 94 | busy-baldwins-doing-time-remi-and-stoney | Busy Baldwin's doing time with Remi and Stoney | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 116046 | 0.1177 | 0.3264 | orange | 0.0249 |
| 106 | new-kate-nashs-pumpkin-soup-kinga-burza | NEW: Kate Nash's Pumpkin Soup by Kinga Burza | youtube | — | — | 510 | 266 | 160 | 83 | 126145 | 0.6090 | 0.3640 | orange | 0.0258 |
| 108 | ox-tale-demonic-audio-tape-%E2%80%93-no-really | An Ox tale of demonic audio tape – no, really... | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 139375 | 0.1285 | 0.6486 | magenta | 0.0286 |
| 109 | new-mikas-lollipop-bonzom | NEW: Mika's Lollipop by Bonzom | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 226394 | 0.6219 | 0.5098 | orange | 0.0562 |
| 110 | bug-last-one-finished-erotic-golf | BUG: The last one finished with erotic golf... | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 118255 | 0.4247 | 0.2786 | orange | 0.0326 |
| 111 | young-punx-trilogy-han-hoogerbrugge | The Young Punx trilogy by Han Hoogerbrugge | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 118270 | 0.4597 | 0.3209 | yellow | 0.0611 |
| 112 | newvfx-fatima-directs-sugababes-%E2%80%93-help-sm | NEW/VFX: Fatima directs Sugababes – help from S&M | — | New Promos, Post, Promos | — | 510 | 266 | 160 | 83 | 113822 | 0.1540 | 0.3843 | blue | 0.0355 |
| 114 | newvfx-newton-faulkners-teardrop-diamond-dogs | NEW/VFX: Newton Faulkner's Teardrop by Diamond Dogs | — | New Promos, Post, Promos | — | 510 | 266 | 160 | 83 | 142865 | 0.1295 | 0.5309 | orange | 0.0229 |
| 115 | new-annuals-dry-clothes-trunk | NEW: Annuals' Dry Clothes by Trunk | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 173486 | 0.3977 | 0.2177 | neutral | 0.0405 |
| 117 | new-hot-chip-nima-nourizadeh | NEW: Hot Chip by Nima Nourizadeh | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 68912 | 0.0931 | 0.2160 | orange | 0.0251 |
| 118 | barnaby-ropers-ed-harcourt-video | Barnaby Roper's Ed Harcourt video | — | Promos | — | 510 | 266 | 160 | 83 | 183118 | 0.2315 | 0.4421 | yellow | 0.0459 |
| 119 | new-tom-baxter-josh-xander | NEW: Tom Baxter by Josh & Xander | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 23577 | 0.0628 | 0.0556 | neutral | 0.0101 |
| 120 | kanos-feel-free-nez | Kano's Feel Free by Nez | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 85820 | 0.2498 | 0.1693 | neutral | 0.0487 |
| 122 | new-bjork-michel-gondry | NEW: Bjork by Michel Gondry | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 153433 | 0.2040 | 0.4581 | yellow | 0.0601 |
| 123 | its-christmas-%E2%80%93-so-can-we-have-some-cards-please | It's Christmas – so can we have some cards please...?  | — | Christmas | — | 510 | 266 | 160 | 83 | 161586 | 0.4014 | 0.2220 | neutral | 0.0497 |
| 124 | new-black-ghosts-ben-jos | NEW: Black Ghosts by Ben & Jos | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 82362 | 0.3713 | 0.1845 | orange | 0.0255 |
| 125 | new-little-ones-terri-timely | NEW: Little Ones by Terri Timely | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 165144 | 0.3436 | 0.3243 | orange | 0.0464 |
| 128 | new-one-night-only-lindy-heymann | NEW: One Night Only by Lindy Heymann | — | New Promos, Promos | — | 510 | 266 | 160 | 83 | 121995 | 0.2147 | 0.9726 | orange | 0.0109 |
| 129 | new-malcolm-middletons-were-all-gonna-die-tom-haines | NEW: Malcolm Middleton's We're All Gonna Die by Tom Haines | — | Christmas, New Promos, Promos | — | 510 | 266 | 160 | 83 | 162076 | 0.3285 | 0.3425 | orange | 0.0572 |

## Distributions by genre and category

Each row aggregates only the measured stills that carry that genre or category. Counts describe this measured sample, not the full catalogue.

### Genre

| value | stills | luma min | luma median | luma max |
| --- | --- | --- | --- | --- |
| 90s | 1 | 0.3814 | 0.3814 | 0.3814 |
| AOR | 2 | 0.1687 | 0.2422 | 0.3156 |
| Abstract | 1 | 0.1877 | 0.1877 | 0.1877 |
| Acoustic | 19 | 0.1077 | 0.2766 | 0.5235 |
| Acoustic, Indie | 5 | 0.1148 | 0.2537 | 0.3784 |
| Africa | 1 | 0.4635 | 0.4635 | 0.4635 |
| Afro-Beat | 10 | 0.0801 | 0.2969 | 0.4121 |
| Afro-Jazz | 1 | 0.5826 | 0.5826 | 0.5826 |
| Afro-Pop | 7 | 0.1048 | 0.3313 | 0.5340 |
| Afrobeat | 16 | 0.0929 | 0.3321 | 0.5413 |
| Afrobeats | 2 | 0.1991 | 0.3586 | 0.5181 |
| Alt Jungle | 1 | 0.1350 | 0.1350 | 0.1350 |
| Alt Pop | 40 | 0.0794 | 0.3089 | 0.6828 |
| Alt R&B | 1 | 0.2659 | 0.2659 | 0.2659 |
| Alt Rock | 20 | 0.0704 | 0.2322 | 0.5575 |
| Alt Soul | 17 | 0.0391 | 0.3415 | 0.7718 |
| Alt-Pop | 76 | 0.0359 | 0.2698 | 0.7095 |
| Alt-country | 3 | 0.0638 | 0.1961 | 0.2292 |
| Alt-dance | 2 | 0.3187 | 0.3577 | 0.3968 |
| Alt-dance, Dance | 1 | 0.3855 | 0.3855 | 0.3855 |
| Alt-rock | 8 | 0.0660 | 0.2356 | 0.5379 |
| Alt-soul | 2 | 0.4404 | 0.4745 | 0.5085 |
| Alte | 1 | 0.1742 | 0.1742 | 0.1742 |
| Alternate | 2 | 0.2982 | 0.3526 | 0.4070 |
| Alternate Metal | 2 | 0.0333 | 0.1655 | 0.2977 |
| Alternative | 952 | 0.0182 | 0.2729 | 0.8254 |
| Alternative / Indie | 2 | 0.1607 | 0.2239 | 0.2872 |
| Alternative Country | 3 | 0.2276 | 0.3605 | 0.4742 |
| Alternative Folk | 7 | 0.1001 | 0.2766 | 0.6466 |
| Alternative Folk Rock | 1 | 0.3798 | 0.3798 | 0.3798 |
| Alternative Folk, Post Punk | 1 | 0.8242 | 0.8242 | 0.8242 |
| Alternative Hip Hop | 2 | 0.2392 | 0.4815 | 0.7238 |
| Alternative Pop | 75 | 0.0129 | 0.3026 | 0.7441 |
| Alternative Pop, Dance | 7 | 0.1328 | 0.3881 | 0.6742 |
| Alternative Pop, Electronica | 9 | 0.0829 | 0.2374 | 0.6669 |
| Alternative R&B | 22 | 0.0687 | 0.2358 | 0.6363 |
| Alternative R&B, Alternative Pop, Electronica | 1 | 0.4719 | 0.4719 | 0.4719 |
| Alternative Rap | 1 | 0.1998 | 0.1998 | 0.1998 |
| Alternative Rock | 38 | 0.0232 | 0.2693 | 0.6684 |
| Alternative Underground | 1 | 0.1552 | 0.1552 | 0.1552 |
| Alternative, Alt-Pop | 1 | 0.2675 | 0.2675 | 0.2675 |
| Alternative, Alt-soul | 1 | 0.5813 | 0.5813 | 0.5813 |
| Alternative, Alternative Pop, Dance | 1 | 0.1775 | 0.1775 | 0.1775 |
| Alternative, Alternative, Hip Hop | 2 | 0.1042 | 0.2353 | 0.3663 |
| Alternative, Dance | 2 | 0.1079 | 0.1684 | 0.2290 |
| Alternative, Electronica | 26 | 0.0618 | 0.3433 | 0.7891 |
| Alternative, Electronica, Alt-Pop | 1 | 0.3368 | 0.3368 | 0.3368 |
| Alternative, Folk, Indie | 3 | 0.3518 | 0.3940 | 0.4073 |
| Alternative, Hip Hop | 17 | 0.0708 | 0.2746 | 0.4200 |
| Alternative, Indie | 14 | 0.1517 | 0.3352 | 0.5559 |
| Alternative, Indie Rock | 15 | 0.1358 | 0.2354 | 0.5907 |
| Alternative, Rock | 4 | 0.0950 | 0.1941 | 0.5278 |
| Alternative, Singer-songwriter | 6 | 0.0665 | 0.3604 | 0.5020 |
| Alternative, Urban | 1 | 0.2008 | 0.2008 | 0.2008 |
| Alternative/ Indie | 1 | 0.1838 | 0.1838 | 0.1838 |
| Amapiano | 2 | 0.2937 | 0.3627 | 0.4317 |
| Ambient | 12 | 0.0704 | 0.3784 | 0.7995 |
| Ambient Pop | 3 | 0.2129 | 0.2318 | 0.3383 |
| Americana | 3 | 0.2018 | 0.3429 | 0.4420 |
| Analogue | 2 | 0.1651 | 0.1786 | 0.1921 |
| Art Punk | 1 | 0.4585 | 0.4585 | 0.4585 |
| Art Rock | 9 | 0.1625 | 0.3777 | 0.4761 |
| Art-pop | 4 | 0.2006 | 0.3767 | 0.7024 |
| Atmospheric | 2 | 0.1963 | 0.2641 | 0.3319 |
| Avant-Garde | 1 | 0.1952 | 0.1952 | 0.1952 |
| Balearic | 1 | 0.3036 | 0.3036 | 0.3036 |
| Ballad | 16 | 0.1073 | 0.3174 | 0.5977 |
| Baroque | 1 | 0.2006 | 0.2006 | 0.2006 |
| Beatbox | 1 | 0.2845 | 0.2845 | 0.2845 |
| Beats | 4 | 0.2341 | 0.5048 | 0.5638 |
| Bedroom Pop | 5 | 0.1884 | 0.3207 | 0.5339 |
| Bluegrass | 1 | 0.5753 | 0.5753 | 0.5753 |
| Blues | 17 | 0.1260 | 0.2275 | 0.4575 |
| Blues Rock | 4 | 0.1366 | 0.2079 | 0.2706 |
| Boogie | 2 | 0.1712 | 0.2374 | 0.3036 |
| Brass | 1 | 0.3833 | 0.3833 | 0.3833 |
| Brazilian | 1 | 0.2660 | 0.2660 | 0.2660 |
| Breakbeat | 2 | 0.1872 | 0.3917 | 0.5961 |
| Brit Pop | 1 | 0.3819 | 0.3819 | 0.3819 |
| Britpop | 1 | 0.4991 | 0.4991 | 0.4991 |
| Bubblegum Pop | 1 | 0.2973 | 0.2973 | 0.2973 |
| Carnival | 1 | 0.2236 | 0.2236 | 0.2236 |
| Chamber Jazz | 1 | 0.1298 | 0.1298 | 0.1298 |
| Chiptune | 1 | 0.2801 | 0.2801 | 0.2801 |
| Choral | 1 | 0.1239 | 0.1239 | 0.1239 |
| Cinematic | 1 | 0.5142 | 0.5142 | 0.5142 |
| Classic Pop, Soundtrack | 1 | 0.2303 | 0.2303 | 0.2303 |
| Classical | 17 | 0.0622 | 0.3260 | 0.6615 |
| Classical Crossover | 2 | 0.0714 | 0.1615 | 0.2517 |
| Classical, Alternative, Electronica | 1 | 0.0714 | 0.0714 | 0.0714 |
| Club | 2 | 0.3509 | 0.3526 | 0.3543 |
| Coldwave | 1 | 0.2364 | 0.2364 | 0.2364 |
| College Rock | 1 | 0.3619 | 0.3619 | 0.3619 |
| Comedy | 3 | 0.2974 | 0.5350 | 0.6527 |
| Composer | 1 | 0.3260 | 0.3260 | 0.3260 |
| Contemporary Blues | 1 | 0.4280 | 0.4280 | 0.4280 |
| Contemporary Folk | 1 | 0.4763 | 0.4763 | 0.4763 |
| Contemporary Jazz | 1 | 0.2807 | 0.2807 | 0.2807 |
| Contemporary Latin | 2 | 0.1227 | 0.1248 | 0.1269 |
| Contemporary R&B | 28 | 0.0538 | 0.3150 | 0.6124 |
| Contemporary Singer/Songwriter | 1 | 0.2221 | 0.2221 | 0.2221 |
| Country | 30 | 0.0725 | 0.2907 | 0.5617 |
| Country Blues | 2 | 0.1577 | 0.1895 | 0.2213 |
| D&B | 1 | 0.2109 | 0.2109 | 0.2109 |
| DIY Pop | 1 | 0.2819 | 0.2819 | 0.2819 |
| DJ | 4 | 0.1287 | 0.1574 | 0.4664 |
| Dance | 610 | 0.0230 | 0.2959 | 0.8865 |
| Dance, Alternative | 6 | 0.0799 | 0.2542 | 0.4227 |
| Dance, Alternative Pop, Electronica | 1 | 0.5337 | 0.5337 | 0.5337 |
| Dance, Alternative, Electronica | 3 | 0.3560 | 0.3928 | 0.4036 |
| Dance, Alternative, Hip Hop | 1 | 0.1410 | 0.1410 | 0.1410 |
| Dance, Chillout | 2 | 0.0958 | 0.2489 | 0.4021 |
| Dance, Drum & Bass | 2 | 0.2689 | 0.3052 | 0.3416 |
| Dance, EDM | 15 | 0.0722 | 0.3050 | 0.5219 |
| Dance, Electro | 2 | 0.1304 | 0.1427 | 0.1549 |
| Dance, Electronica | 10 | 0.0472 | 0.2102 | 0.6151 |
| Dance, Electronica, Alternative | 7 | 0.0827 | 0.2883 | 0.5887 |
| Dance, Electronica, Pop | 3 | 0.1923 | 0.5116 | 0.6085 |
| Dance, Pop | 21 | 0.1222 | 0.3892 | 0.6090 |
| Dance, Pop, Disco | 2 | 0.2981 | 0.3151 | 0.3320 |
| Dance, Reggae, Dancehall | 2 | 0.3046 | 0.3886 | 0.4726 |
| Dance-pop | 1 | 0.5273 | 0.5273 | 0.5273 |
| Dancehall | 25 | 0.0756 | 0.2560 | 0.5854 |
| Darkwave | 1 | 0.3683 | 0.3683 | 0.3683 |
| Death Metal/Black Metal | 4 | 0.2276 | 0.3575 | 0.5337 |
| Deep House | 4 | 0.1304 | 0.2489 | 0.3846 |
| Denmark | 1 | 0.4806 | 0.4806 | 0.4806 |
| Disco | 15 | 0.0867 | 0.2506 | 0.4423 |
| DnB | 1 | 0.0695 | 0.0695 | 0.0695 |
| Dream Trap | 1 | 0.3742 | 0.3742 | 0.3742 |
| Dream pop | 15 | 0.0442 | 0.3265 | 0.6498 |
| Dream pop, Dance, Electronica | 1 | 0.8741 | 0.8741 | 0.8741 |
| Dream-pop | 2 | 0.2318 | 0.4302 | 0.6286 |
| Drum & Bass | 12 | 0.0980 | 0.3359 | 0.6623 |
| Drum and Bass | 11 | 0.0650 | 0.3803 | 0.6191 |
| Dub | 1 | 0.2651 | 0.2651 | 0.2651 |
| Dubstep | 4 | 0.0415 | 0.3678 | 0.5186 |
| EDM | 26 | 0.0791 | 0.2936 | 0.7809 |
| EDM, Dance | 1 | 0.0717 | 0.0717 | 0.0717 |
| Electro | 8 | 0.0785 | 0.2304 | 0.6399 |
| Electro, Disco | 1 | 0.2009 | 0.2009 | 0.2009 |
| Electro-pop | 20 | 0.1051 | 0.2227 | 0.6780 |
| Electro-pop, Pop, Dance | 2 | 0.3178 | 0.4499 | 0.5820 |
| Electro-rock | 1 | 0.1647 | 0.1647 | 0.1647 |
| Electronic | 303 | 0.0283 | 0.2540 | 0.8544 |
| Electronic Pop | 2 | 0.2040 | 0.2062 | 0.2085 |
| Electronic Rock | 1 | 0.7026 | 0.7026 | 0.7026 |
| Electronica | 165 | 0.0244 | 0.2801 | 0.8199 |
| Electronica, Alternative | 5 | 0.1084 | 0.1841 | 0.5720 |
| Electronica, Dance | 2 | 0.1590 | 0.2425 | 0.3260 |
| Electronica, Progressive Rock | 1 | 0.6586 | 0.6586 | 0.6586 |
| Electropop | 8 | 0.1357 | 0.3885 | 0.5972 |
| Emo | 5 | 0.0887 | 0.4327 | 0.5203 |
| Emo Rap | 1 | 0.2399 | 0.2399 | 0.2399 |
| Experimental | 63 | 0.0427 | 0.2513 | 0.7837 |
| Experimental Folk | 2 | 0.1298 | 0.2403 | 0.3508 |
| Experimental Pop | 9 | 0.1787 | 0.3212 | 0.7803 |
| Experimental Rock | 2 | 0.2502 | 0.4972 | 0.7442 |
| Film music | 1 | 0.5607 | 0.5607 | 0.5607 |
| Flamenco | 5 | 0.1732 | 0.3028 | 0.4899 |
| Folk | 71 | 0.0590 | 0.2898 | 0.7413 |
| Folk Pop | 3 | 0.1945 | 0.3083 | 0.3254 |
| Folk Rock | 6 | 0.1341 | 0.3362 | 0.6931 |
| Folk, Indie | 7 | 0.1980 | 0.2935 | 0.5143 |
| Folk, Indie, Alternative | 3 | 0.2866 | 0.4775 | 0.5874 |
| Folk, Pop | 5 | 0.1892 | 0.3720 | 0.4911 |
| Freestyle | 2 | 0.1551 | 0.2014 | 0.2476 |
| Funk | 21 | 0.0690 | 0.3004 | 0.6180 |
| Funk, Jazz | 1 | 0.2009 | 0.2009 | 0.2009 |
| Gangsta Rap | 1 | 0.3336 | 0.3336 | 0.3336 |
| Garage | 23 | 0.0926 | 0.2321 | 0.6151 |
| Garage Rock | 6 | 0.1061 | 0.3559 | 0.5866 |
| Genre Bending | 1 | 0.2307 | 0.2307 | 0.2307 |
| Glam | 1 | 0.3709 | 0.3709 | 0.3709 |
| Glam Rock | 3 | 0.1625 | 0.2521 | 0.6916 |
| Glitch | 1 | 0.2324 | 0.2324 | 0.2324 |
| Gospel | 5 | 0.1532 | 0.1829 | 0.5041 |
| Goth Rock | 1 | 0.3058 | 0.3058 | 0.3058 |
| Grime | 214 | 0.0487 | 0.2634 | 0.7069 |
| Grime, Hip Hop | 2 | 0.0985 | 0.1842 | 0.2699 |
| Grime, Urban | 5 | 0.0728 | 0.2541 | 0.7437 |
| Groove | 2 | 0.1247 | 0.2269 | 0.3292 |
| Grunge | 6 | 0.2506 | 0.2740 | 0.6056 |
| Hard Rock | 2 | 0.1677 | 0.1942 | 0.2206 |
| Hardcore | 3 | 0.0918 | 0.1043 | 0.4959 |
| Hardcore Punk | 2 | 0.3006 | 0.3982 | 0.4959 |
| Heavy Metal | 19 | 0.0472 | 0.1878 | 0.5381 |
| Highlife | 1 | 0.3306 | 0.3306 | 0.3306 |
| Hip Hop | 644 | 0.0460 | 0.2768 | 0.8615 |
| Hip Hop, Pop | 5 | 0.4655 | 0.5042 | 0.5260 |
| Hip Hop, Rap | 1 | 0.1942 | 0.1942 | 0.1942 |
| Hip Hop, Urban | 19 | 0.0601 | 0.2551 | 0.5357 |
| Hip hop, Alternative | 5 | 0.2549 | 0.4268 | 0.6684 |
| Hip hop, Dance | 1 | 0.0981 | 0.0981 | 0.0981 |
| Hip hop, Grime, Urban | 2 | 0.2102 | 0.2202 | 0.2301 |
| Hip hop, Hip Hop, Urban | 2 | 0.1835 | 0.2613 | 0.3392 |
| Hip hop, Jazz | 1 | 0.0798 | 0.0798 | 0.0798 |
| Hip-Hop | 41 | 0.0798 | 0.2514 | 0.6514 |
| Hip-Hop/Rap | 1 | 0.1246 | 0.1246 | 0.1246 |
| Hispanic | 1 | 0.2927 | 0.2927 | 0.2927 |
| House | 31 | 0.0683 | 0.3126 | 0.5440 |
| House, Dance | 3 | 0.1497 | 0.4348 | 0.7561 |
| Hyper Pop | 1 | 0.4739 | 0.4739 | 0.4739 |
| Hyperpop | 2 | 0.4097 | 0.5013 | 0.5929 |
| Indie | 685 | 0.0240 | 0.3046 | 0.8544 |
| Indie Folk | 11 | 0.0873 | 0.2264 | 0.4527 |
| Indie Rock | 149 | 0.0326 | 0.2861 | 0.6980 |
| Indie Rock, Alternative | 2 | 0.4739 | 0.5104 | 0.5468 |
| Indie pop | 70 | 0.0743 | 0.2831 | 0.7001 |
| Indie pop, Pop, Indie Rock | 3 | 0.2955 | 0.3065 | 0.3985 |
| Indie, Adult Alternative | 1 | 0.0966 | 0.0966 | 0.0966 |
| Indie, Alternative | 21 | 0.1232 | 0.2847 | 0.6891 |
| Indie, Alternative Pop | 2 | 0.3495 | 0.4274 | 0.5053 |
| Indie, Dance | 1 | 0.3019 | 0.3019 | 0.3019 |
| Indie, Indie Rock | 4 | 0.1429 | 0.1869 | 0.2032 |
| Indie, Indie, singer-songwriter | 1 | 0.1631 | 0.1631 | 0.1631 |
| Indie, Indie-pop | 1 | 0.0525 | 0.0525 | 0.0525 |
| Indie, Pop | 8 | 0.2024 | 0.2429 | 0.4929 |
| Indie, Rock | 1 | 0.2535 | 0.2535 | 0.2535 |
| Indie, Rock, Psychedelic, Alternative Rock | 1 | 0.1048 | 0.1048 | 0.1048 |
| Indie, singer-songwriter | 36 | 0.0638 | 0.2880 | 0.8862 |
| Indie-pop | 25 | 0.0830 | 0.3251 | 0.6286 |
| Indigenous Punk | 1 | 0.2537 | 0.2537 | 0.2537 |
| Indonesian Pop | 1 | 0.4217 | 0.4217 | 0.4217 |
| Industrial | 3 | 0.0438 | 0.0859 | 0.2232 |
| Instrumental | 29 | 0.1012 | 0.3204 | 0.5607 |
| Instrumental Rock | 1 | 0.2045 | 0.2045 | 0.2045 |
| J-Pop | 5 | 0.1345 | 0.3779 | 0.4954 |
| Jazz | 66 | 0.0441 | 0.2691 | 0.6091 |
| Jazz House | 1 | 0.1472 | 0.1472 | 0.1472 |
| Jazz, Soul | 2 | 0.4519 | 0.5816 | 0.7114 |
| Jungle/Drum’n'bass | 1 | 0.4348 | 0.4348 | 0.4348 |
| K Pop | 2 | 0.3989 | 0.4160 | 0.4331 |
| K-Pop | 9 | 0.1412 | 0.3057 | 0.5346 |
| Latin | 1 | 0.1807 | 0.1807 | 0.1807 |
| Latin Pop | 3 | 0.1269 | 0.3197 | 0.4390 |
| Left-field | 1 | 0.4524 | 0.4524 | 0.4524 |
| Live | 1 | 0.5035 | 0.5035 | 0.5035 |
| Lo Fi | 1 | 0.4995 | 0.4995 | 0.4995 |
| MC | 1 | 0.6177 | 0.6177 | 0.6177 |
| MPB | 1 | 0.0825 | 0.0825 | 0.0825 |
| Mariachi | 1 | 0.3079 | 0.3079 | 0.3079 |
| Metal | 23 | 0.0918 | 0.1722 | 0.5337 |
| Metal, Rock | 2 | 0.0472 | 0.1278 | 0.2083 |
| Metalcore | 7 | 0.0999 | 0.1380 | 0.4879 |
| Modern Composition | 16 | 0.0468 | 0.2138 | 0.7107 |
| Modern Jazz | 1 | 0.4640 | 0.4640 | 0.4640 |
| Motown | 1 | 0.4134 | 0.4134 | 0.4134 |
| Multi Instrumentalist | 5 | 0.0669 | 0.2688 | 0.6477 |
| Musicals | 1 | 0.2361 | 0.2361 | 0.2361 |
| Musician | 3 | 0.3039 | 0.3300 | 0.4845 |
| Neo Folk | 2 | 0.1551 | 0.2060 | 0.2569 |
| Neo-Soul | 4 | 0.1215 | 0.4390 | 0.7478 |
| Neo-psychedelia | 1 | 0.2132 | 0.2132 | 0.2132 |
| Neoclassical | 1 | 0.2615 | 0.2615 | 0.2615 |
| New Age | 1 | 0.1281 | 0.1281 | 0.1281 |
| New Wave | 4 | 0.0748 | 0.1536 | 0.6558 |
| Noise | 3 | 0.2181 | 0.5334 | 0.6392 |
| Noise Punk | 2 | 0.2185 | 0.3045 | 0.3905 |
| Northern Soul | 2 | 0.2290 | 0.2301 | 0.2311 |
| Opera | 2 | 0.1125 | 0.2260 | 0.3395 |
| Orchestral | 4 | 0.1629 | 0.3293 | 0.5521 |
| Ouija Pop | 1 | 0.2650 | 0.2650 | 0.2650 |
| PBR&B | 1 | 0.2610 | 0.2610 | 0.2610 |
| Performance | 1 | 0.2924 | 0.2924 | 0.2924 |
| Piano | 2 | 0.2371 | 0.2954 | 0.3537 |
| Poetry | 6 | 0.0685 | 0.2630 | 0.6471 |
| Pop | 2560 | 0.0211 | 0.2911 | 0.9615 |
| Pop Rock | 9 | 0.1461 | 0.2918 | 0.5226 |
| Pop, | 5 | 0.2437 | 0.4206 | 0.9105 |
| Pop, Alt Pop | 1 | 0.1589 | 0.1589 | 0.1589 |
| Pop, Alt-Pop | 3 | 0.0931 | 0.3027 | 0.3170 |
| Pop, Alternative | 3 | 0.1760 | 0.4307 | 0.5791 |
| Pop, Beats, Ambient Pop | 1 | 0.1462 | 0.1462 | 0.1462 |
| Pop, Dance | 9 | 0.1038 | 0.3617 | 0.4103 |
| Pop, Dance, EDM | 2 | 0.5537 | 0.6219 | 0.6902 |
| Pop, Dream pop | 1 | 0.6229 | 0.6229 | 0.6229 |
| Pop, Electro-pop | 1 | 0.5694 | 0.5694 | 0.5694 |
| Pop, Electronica | 2 | 0.1925 | 0.3211 | 0.4496 |
| Pop, Funk | 3 | 0.1864 | 0.4099 | 0.4272 |
| Pop, Hip Hop | 5 | 0.0782 | 0.3219 | 0.6705 |
| Pop, Hip-hop | 1 | 0.1223 | 0.1223 | 0.1223 |
| Pop, Indie | 9 | 0.0336 | 0.2658 | 0.4133 |
| Pop, Indie Rock | 2 | 0.0359 | 0.0663 | 0.0967 |
| Pop, Indie pop | 1 | 0.3864 | 0.3864 | 0.3864 |
| Pop, Pop, Singer-songwriter | 1 | 0.7380 | 0.7380 | 0.7380 |
| Pop, Pop, Urban | 1 | 0.2092 | 0.2092 | 0.2092 |
| Pop, R&B | 11 | 0.1704 | 0.3740 | 0.5992 |
| Pop, RnB | 1 | 0.3053 | 0.3053 | 0.3053 |
| Pop, Singer-songwriter | 18 | 0.0686 | 0.2948 | 0.5441 |
| Pop, Singer/Songwriter | 3 | 0.1764 | 0.2287 | 0.3884 |
| Pop, Soul | 5 | 0.0902 | 0.1927 | 0.3566 |
| Pop, Urban | 10 | 0.1035 | 0.3696 | 0.6052 |
| Pop-Rock | 2 | 0.2213 | 0.2680 | 0.3147 |
| Pop-punk | 7 | 0.1461 | 0.2181 | 0.3688 |
| Pop-punk, Punk | 2 | 0.1461 | 0.2125 | 0.2789 |
| Post Rock | 3 | 0.1727 | 0.3170 | 0.4496 |
| Post-Punk | 8 | 0.1481 | 0.3182 | 0.7263 |
| Post-rock | 2 | 0.2045 | 0.3106 | 0.4167 |
| Power Pop | 3 | 0.1514 | 0.3253 | 0.6916 |
| Producer | 1 | 0.4664 | 0.4664 | 0.4664 |
| Prog Rock | 1 | 0.3394 | 0.3394 | 0.3394 |
| Prog rock, jazz rock | 1 | 0.3673 | 0.3673 | 0.3673 |
| Prog-Rock/Art Rock | 2 | 0.1595 | 0.3160 | 0.4725 |
| Progressive | 1 | 0.4293 | 0.4293 | 0.4293 |
| Progressive Art Rock | 1 | 0.3948 | 0.3948 | 0.3948 |
| Progressive Metal | 1 | 0.2335 | 0.2335 | 0.2335 |
| Progressive Rock | 1 | 0.5403 | 0.5403 | 0.5403 |
| Psychedelia | 1 | 0.4835 | 0.4835 | 0.4835 |
| Psychedelic | 5 | 0.1565 | 0.3515 | 0.6111 |
| Psychedelic Rock | 1 | 0.3029 | 0.3029 | 0.3029 |
| Psychedelic, Alternative Rock | 2 | 0.1344 | 0.2299 | 0.3254 |
| Pub Rock | 1 | 0.3004 | 0.3004 | 0.3004 |
| Punk | 31 | 0.0531 | 0.2226 | 0.6215 |
| Punk rock | 11 | 0.0531 | 0.2376 | 0.6569 |
| Punk, Thrash, Rock | 1 | 0.1740 | 0.1740 | 0.1740 |
| R&B | 299 | 0.0290 | 0.2668 | 0.7537 |
| R&B, Hip Hop | 1 | 0.2507 | 0.2507 | 0.2507 |
| R&B, Soul | 9 | 0.1208 | 0.2786 | 0.7478 |
| R&B, Urban | 2 | 0.2326 | 0.5679 | 0.9032 |
| R&B/Soul | 4 | 0.2248 | 0.2855 | 0.4023 |
| Rap | 264 | 0.0230 | 0.2712 | 0.9615 |
| Rapper | 1 | 0.0804 | 0.0804 | 0.0804 |
| Rave | 2 | 0.3335 | 0.4641 | 0.5948 |
| Reggae | 17 | 0.0977 | 0.3446 | 0.8231 |
| Reggae, Hip Hop | 2 | 0.3462 | 0.4189 | 0.4916 |
| Reggaeton y Hip-Hop | 1 | 0.4560 | 0.4560 | 0.4560 |
| Reimagining | 1 | 0.0695 | 0.0695 | 0.0695 |
| Remix | 2 | 0.2967 | 0.3813 | 0.4659 |
| Retro | 1 | 0.2745 | 0.2745 | 0.2745 |
| RnB | 2 | 0.2007 | 0.2272 | 0.2536 |
| Rock | 1053 | 0.0232 | 0.2760 | 0.8681 |
| Rock & Roll | 3 | 0.2071 | 0.3951 | 0.4315 |
| Rock Band | 1 | 0.1049 | 0.1049 | 0.1049 |
| Rock, | 2 | 0.3995 | 0.4324 | 0.4652 |
| Rock, Alt Rock | 1 | 0.0980 | 0.0980 | 0.0980 |
| Rock, Alternative | 2 | 0.1811 | 0.2069 | 0.2327 |
| Rock, Garage, Indie | 3 | 0.1923 | 0.5004 | 0.5054 |
| Rock, Heavy Metal | 3 | 0.2448 | 0.2548 | 0.2620 |
| Rock, Indie | 2 | 0.2764 | 0.4307 | 0.5850 |
| Rock, Indie Rock | 3 | 0.2269 | 0.2414 | 0.3415 |
| Rock, Indie, Alternative | 1 | 0.2396 | 0.2396 | 0.2396 |
| Rock, Indie, Indie Rock | 1 | 0.4080 | 0.4080 | 0.4080 |
| Rock/Pop | 7 | 0.1522 | 0.2664 | 0.6269 |
| Salsa | 3 | 0.2719 | 0.4346 | 0.4586 |
| Sea Shanty | 2 | 0.2038 | 0.2646 | 0.3254 |
| Shoegaze | 2 | 0.1195 | 0.1534 | 0.1873 |
| Singer songwriter | 97 | 0.0211 | 0.2821 | 0.7454 |
| Singer songwriter, Pop | 3 | 0.1922 | 0.2027 | 0.2771 |
| Singer-songwriter | 357 | 0.0163 | 0.2647 | 0.8254 |
| Singer-songwriter, Folk | 1 | 0.1709 | 0.1709 | 0.1709 |
| Singer-songwriter, Indie | 1 | 0.2374 | 0.2374 | 0.2374 |
| Singer-songwriter, Pop | 2 | 0.1193 | 0.1538 | 0.1883 |
| Singer/Songwriter | 2 | 0.2443 | 0.3037 | 0.3632 |
| Ska | 3 | 0.1165 | 0.1795 | 0.3925 |
| Soft Rock | 2 | 0.3156 | 0.3638 | 0.4120 |
| Soul | 249 | 0.0290 | 0.2441 | 0.7680 |
| Soul, Alt Soul | 2 | 0.1399 | 0.1771 | 0.2142 |
| Soul, Alt-Soul | 2 | 0.0559 | 0.1697 | 0.2834 |
| Soul, Hip hop | 1 | 0.2263 | 0.2263 | 0.2263 |
| Soul, Jazz | 1 | 0.2560 | 0.2560 | 0.2560 |
| Soul, Pop | 6 | 0.2333 | 0.4332 | 0.6167 |
| Soul, R&B, Jazz | 1 | 0.5981 | 0.5981 | 0.5981 |
| Soul, Urban | 1 | 0.0936 | 0.0936 | 0.0936 |
| Sound Design | 1 | 0.4422 | 0.4422 | 0.4422 |
| Soundscape | 1 | 0.3514 | 0.3514 | 0.3514 |
| Soundtrack | 4 | 0.1730 | 0.3295 | 0.4802 |
| Space Rock | 1 | 0.2624 | 0.2624 | 0.2624 |
| Spoken Word | 12 | 0.1554 | 0.2966 | 0.4802 |
| Standards | 1 | 0.2361 | 0.2361 | 0.2361 |
| Supergroup | 1 | 0.5339 | 0.5339 | 0.5339 |
| Surf | 1 | 0.1899 | 0.1899 | 0.1899 |
| Symphonic Metal | 1 | 0.2688 | 0.2688 | 0.2688 |
| Synth | 12 | 0.1186 | 0.2641 | 0.4813 |
| Synth Pop | 26 | 0.0735 | 0.2546 | 0.7006 |
| Synth-Pop | 10 | 0.0701 | 0.2999 | 0.7641 |
| Synthpop | 4 | 0.1322 | 0.2392 | 0.3779 |
| Synthwave | 1 | 0.4156 | 0.4156 | 0.4156 |
| Tech House | 1 | 0.3625 | 0.3625 | 0.3625 |
| Techno | 8 | 0.1304 | 0.2374 | 0.7423 |
| Techno House | 1 | 0.1146 | 0.1146 | 0.1146 |
| Techno, Dance | 5 | 0.0120 | 0.2082 | 0.3887 |
| Theatrical | 1 | 0.1983 | 0.1983 | 0.1983 |
| Theme | 1 | 0.2279 | 0.2279 | 0.2279 |
| Trap | 21 | 0.0854 | 0.2635 | 0.7718 |
| Trap Metal | 1 | 0.2840 | 0.2840 | 0.2840 |
| Trapwave | 1 | 0.2250 | 0.2250 | 0.2250 |
| Trip hop | 4 | 0.2517 | 0.4682 | 0.6637 |
| Trip-hop | 3 | 0.1511 | 0.1960 | 0.2186 |
| UK Rap | 8 | 0.0956 | 0.2391 | 0.6389 |
| UKG | 5 | 0.1557 | 0.1873 | 0.4246 |
| Underground | 1 | 0.2126 | 0.2126 | 0.2126 |
| Underground Hip Hop | 1 | 0.5526 | 0.5526 | 0.5526 |
| Urban | 58 | 0.0196 | 0.3107 | 0.8456 |
| Urban Pop | 1 | 0.1597 | 0.1597 | 0.1597 |
| Urban, Alternative | 1 | 0.1031 | 0.1031 | 0.1031 |
| Urban, Pop | 2 | 0.1898 | 0.1984 | 0.2069 |
| Urban, R&B | 1 | 0.2571 | 0.2571 | 0.2571 |
| Urban, R&B, Dance | 1 | 0.5274 | 0.5274 | 0.5274 |
| World | 5 | 0.1570 | 0.2584 | 0.2747 |
| World music | 8 | 0.1339 | 0.4127 | 0.6700 |
| Worldbeat | 1 | 0.0346 | 0.0346 | 0.0346 |
| Yela | 1 | 0.0346 | 0.0346 | 0.0346 |
| acoustic pop | 1 | 0.2197 | 0.2197 | 0.2197 |
| alternate pop | 6 | 0.0521 | 0.3379 | 0.6457 |
| alternative dance | 1 | 0.4373 | 0.4373 | 0.4373 |
| alternative metal | 1 | 0.4488 | 0.4488 | 0.4488 |
| art pop | 5 | 0.1578 | 0.3236 | 0.6763 |
| avant garde | 1 | 0.6887 | 0.6887 | 0.6887 |
| avant garde pop | 1 | 0.4713 | 0.4713 | 0.4713 |
| avant pop | 1 | 0.3683 | 0.3683 | 0.3683 |
| bossa nova | 1 | 0.0825 | 0.0825 | 0.0825 |
| british hip hop | 3 | 0.1041 | 0.3365 | 0.5354 |
| celtic rock | 1 | 0.2161 | 0.2161 | 0.2161 |
| chillout | 1 | 0.4652 | 0.4652 | 0.4652 |
| classic | 2 | 0.2409 | 0.3285 | 0.4160 |
| classical pop | 1 | 0.2796 | 0.2796 | 0.2796 |
| cloud rap | 1 | 0.1464 | 0.1464 | 0.1464 |
| contemporary soul | 1 | 0.6403 | 0.6403 | 0.6403 |
| country pop | 2 | 0.3479 | 0.3996 | 0.4513 |
| dance pop | 1 | 0.3549 | 0.3549 | 0.3549 |
| dark pop | 3 | 0.2219 | 0.4048 | 0.6403 |
| disco funk | 1 | 0.2190 | 0.2190 | 0.2190 |
| drill | 15 | 0.0487 | 0.2176 | 0.5288 |
| electric | 1 | 0.1304 | 0.1304 | 0.1304 |
| future house | 1 | 0.4676 | 0.4676 | 0.4676 |
| grindcore | 1 | 0.5299 | 0.5299 | 0.5299 |
| indie electronic | 2 | 0.1455 | 0.1743 | 0.2031 |
| jungle | 1 | 0.1872 | 0.1872 | 0.1872 |
| kpop | 2 | 0.3576 | 0.4335 | 0.5093 |
| latin trap | 2 | 0.2700 | 0.3008 | 0.3316 |
| melodic | 1 | 0.2796 | 0.2796 | 0.2796 |
| narrative | 1 | 0.5944 | 0.5944 | 0.5944 |
| nu-disco | 1 | 0.1687 | 0.1687 | 0.1687 |
| orchestra | 2 | 0.2513 | 0.2846 | 0.3179 |
| pop punk | 9 | 0.1587 | 0.3424 | 0.4448 |
| post punk | 11 | 0.0240 | 0.2919 | 0.6697 |
| post-grunge | 1 | 0.2506 | 0.2506 | 0.2506 |
| progressive house | 1 | 0.3454 | 0.3454 | 0.3454 |
| psychedelic pop | 1 | 0.3614 | 0.3614 | 0.3614 |
| rap metal | 1 | 0.2235 | 0.2235 | 0.2235 |
| reggaeton | 5 | 0.0558 | 0.2700 | 0.4368 |
| singer | 2 | 0.5413 | 0.5600 | 0.5787 |
| songwriter | 3 | 0.1794 | 0.5413 | 0.5787 |
| space pop | 1 | 0.4835 | 0.4835 | 0.4835 |
| tropical house | 1 | 0.4683 | 0.4683 | 0.4683 |

### Category

| value | stills | luma min | luma median | luma max |
| --- | --- | --- | --- | --- |
| Advertising | 19 | 0.1376 | 0.3081 | 0.7403 |
| After Effects | 75 | 0.0594 | 0.3336 | 0.8375 |
| Album trailer | 7 | 0.1687 | 0.2326 | 0.4886 |
| Alternative | 8 | 0.1173 | 0.2125 | 0.8102 |
| Animation | 888 | 0.0230 | 0.3510 | 0.9615 |
| Apps | 1 | 0.6221 | 0.6221 | 0.6221 |
| Archive | 5 | 0.0814 | 0.2550 | 0.2758 |
| Argentina | 1 | 0.2905 | 0.2905 | 0.2905 |
| Art | 29 | 0.0346 | 0.2631 | 0.7974 |
| Audio-visual | 6 | 0.1022 | 0.4257 | 0.6221 |
| Australia | 1 | 0.4299 | 0.4299 | 0.4299 |
| Awards | 6 | 0.1042 | 0.3349 | 0.4295 |
| Awards nominations | 3 | 0.1042 | 0.1924 | 0.2289 |
| BUG | 168 | 0.0704 | 0.3389 | 0.8847 |
| Behind The Scenes | 1 | 0.0906 | 0.0906 | 0.0906 |
| Behind the scenes | 61 | 0.1170 | 0.3168 | 0.8150 |
| Belgium | 1 | 0.2908 | 0.2908 | 0.2908 |
| Best Of | 3 | 0.1939 | 0.3860 | 0.7718 |
| Blogs | 2 | 0.2872 | 0.3035 | 0.3198 |
| Branded music video | 25 | 0.0637 | 0.2606 | 0.6124 |
| Briefs | 1 | 0.3771 | 0.3771 | 0.3771 |
| CGI | 202 | 0.0276 | 0.3063 | 0.8375 |
| Calls for entry | 3 | 0.3026 | 0.3645 | 0.3875 |
| Canada | 1 | 0.0515 | 0.0515 | 0.0515 |
| Charity appeal | 13 | 0.1246 | 0.3007 | 0.4802 |
| Choreography | 596 | 0.0232 | 0.2875 | 0.8375 |
| Christmas | 47 | 0.0911 | 0.2965 | 0.8327 |
| Classic Video | 2 | 0.0898 | 0.1752 | 0.2606 |
| Classic promos | 11 | 0.1939 | 0.3932 | 0.7718 |
| Comedy | 695 | 0.0562 | 0.3339 | 0.8177 |
| Coming soon | 2 | 0.2936 | 0.3274 | 0.3611 |
| Comment | 1 | 0.4275 | 0.4275 | 0.4275 |
| Commercial Break | 3 | 0.1924 | 0.3254 | 0.3435 |
| Commercials | 31 | 0.1212 | 0.3254 | 0.6813 |
| Concert film | 2 | 0.1460 | 0.2115 | 0.2771 |
| DVD | 2 | 0.2933 | 0.3439 | 0.3944 |
| Dance | 229 | 0.0346 | 0.3114 | 0.8865 |
| Dance film | 6 | 0.0735 | 0.2828 | 0.5456 |
| Denmark | 5 | 0.1639 | 0.3699 | 0.4913 |
| Director's cut | 57 | 0.0573 | 0.2796 | 0.9105 |
| Director's notes | 2590 | 0.0120 | 0.2794 | 0.9501 |
| Directors | 6 | 0.3156 | 0.3310 | 0.4726 |
| Directors to watch | 2 | 0.2316 | 0.5239 | 0.8163 |
| Documentary | 207 | 0.0643 | 0.3244 | 0.7145 |
| Drama | 433 | 0.0217 | 0.2537 | 0.7537 |
| Electronica | 14 | 0.1173 | 0.2880 | 0.5535 |
| Events | 4 | 0.1174 | 0.4104 | 0.8904 |
| Exhibition | 1 | 0.1701 | 0.1701 | 0.1701 |
| Fashion | 18 | 0.0950 | 0.3031 | 0.7205 |
| Fashion promo | 40 | 0.0596 | 0.3437 | 0.8917 |
| Festivals | 8 | 0.0531 | 0.6568 | 0.6896 |
| Film competitions | 4 | 0.2550 | 0.4287 | 0.5835 |
| Football | 1 | 0.5912 | 0.5912 | 0.5912 |
| France | 11 | 0.1253 | 0.2737 | 0.7595 |
| Germany | 1 | 0.6601 | 0.6601 | 0.6601 |
| Guest blog | 2 | 0.0615 | 0.1776 | 0.2936 |
| Guest playlist | 4 | 0.2811 | 0.3919 | 0.6210 |
| Halloween | 3 | 0.1972 | 0.2706 | 0.5737 |
| Hip-Hop | 2 | 0.1397 | 0.2836 | 0.4275 |
| In Production | 4 | 0.1279 | 0.3137 | 0.4830 |
| In-camera FX | 64 | 0.0473 | 0.3173 | 0.8862 |
| Indie | 7 | 0.1213 | 0.3389 | 0.4668 |
| Interactive | 55 | 0.0366 | 0.3235 | 0.8317 |
| Interview/Q&A | 37 | 0.0846 | 0.3320 | 0.5343 |
| Ireland | 1 | 0.0890 | 0.0890 | 0.0890 |
| Israel | 2 | 0.2040 | 0.3295 | 0.4549 |
| Italy | 1 | 0.3595 | 0.3595 | 0.3595 |
| Jazz | 2 | 0.4011 | 0.4307 | 0.4604 |
| Live | 126 | 0.0221 | 0.2165 | 0.7036 |
| Live concert | 23 | 0.0874 | 0.1980 | 0.5929 |
| Live music video | 156 | 0.0221 | 0.2043 | 0.8681 |
| Live visuals | 10 | 0.0366 | 0.2919 | 0.5929 |
| Lyric Video | 67 | 0.0230 | 0.3969 | 0.9495 |
| Making of | 26 | 0.0690 | 0.3002 | 0.5833 |
| Mature - NSFW | 178 | 0.0196 | 0.2671 | 0.8847 |
| Motion control | 30 | 0.0601 | 0.2697 | 0.5502 |
| Motion graphics | 15 | 0.0331 | 0.5093 | 0.8295 |
| Movies | 9 | 0.2936 | 0.3470 | 0.6805 |
| Movies remixed | 2 | 0.1425 | 0.4091 | 0.6758 |
| Muppets | 3 | 0.1923 | 0.2729 | 0.4856 |
| Music video competition | 6 | 0.0938 | 0.3341 | 0.4910 |
| Narrative | 2609 | 0.0120 | 0.2695 | 0.8928 |
| Netherlands | 2 | 0.1754 | 0.2034 | 0.2315 |
| New Director | 1594 | 0.0120 | 0.2808 | 0.9320 |
| New Directors | 232 | 0.0313 | 0.2945 | 0.9615 |
| New Promos | 1427 | 0.0201 | 0.3084 | 0.9466 |
| New company | 7 | 0.1400 | 0.2666 | 0.4767 |
| News | 3 | 0.1842 | 0.4122 | 0.4123 |
| Norway | 3 | 0.1641 | 0.2678 | 0.5382 |
| One shot video | 146 | 0.0410 | 0.2527 | 0.6987 |
| Opera | 1 | 0.0714 | 0.0714 | 0.0714 |
| Performance | 2963 | 0.0187 | 0.2764 | 0.9501 |
| Pick of the Day | 1089 | 0.0276 | 0.2710 | 0.8254 |
| Pick of the year | 3 | 0.1461 | 0.2421 | 0.2995 |
| Playlist | 5 | 0.3198 | 0.4421 | 0.5047 |
| Pop | 30 | 0.0643 | 0.2575 | 0.6852 |
| Post | 11 | 0.0683 | 0.1647 | 0.8327 |
| Premiere | 1 | 0.2356 | 0.2356 | 0.2356 |
| Projection | 20 | 0.0578 | 0.2099 | 0.5537 |
| Promos | 4219 | 0.0118 | 0.3064 | 0.9552 |
| Puppets | 55 | 0.0566 | 0.3115 | 0.7147 |
| Rock | 24 | 0.0515 | 0.3464 | 0.6601 |
| Short films | 59 | 0.0410 | 0.2409 | 0.7538 |
| Signing | 40 | 0.0542 | 0.2233 | 0.7095 |
| South Africa | 1 | 0.2566 | 0.2566 | 0.2566 |
| Spain | 1 | 0.3655 | 0.3655 | 0.3655 |
| Special projects | 288 | 0.0328 | 0.2709 | 0.7520 |
| Sport | 3 | 0.0799 | 0.2567 | 0.4582 |
| Stock footage | 48 | 0.0187 | 0.3101 | 0.7848 |
| Stop motion | 102 | 0.0469 | 0.2945 | 0.7080 |
| Stuff | 9 | 0.1566 | 0.2960 | 0.4706 |
| Surreal | 378 | 0.0129 | 0.2739 | 0.8375 |
| Sweden | 3 | 0.1359 | 0.2755 | 0.3433 |
| TV | 9 | 0.0966 | 0.1830 | 0.7201 |
| Teaser | 10 | 0.1507 | 0.2590 | 0.6852 |
| Telecine | 1 | 0.3163 | 0.3163 | 0.3163 |
| Trailer | 16 | 0.1120 | 0.2937 | 0.6160 |
| Treatments wanted | 2 | 0.2885 | 0.3328 | 0.3771 |
| UK Music Video Awards | 2 | 0.1042 | 0.2149 | 0.3256 |
| UK Music Video Awards 2010 | 1 | 0.1924 | 0.1924 | 0.1924 |
| UK Music Video Awards 2015 | 1 | 0.1042 | 0.1042 | 0.1042 |
| UK Music Video Awards 2020 | 1 | 0.7747 | 0.7747 | 0.7747 |
| UK Music Video Awards 2024 | 1 | 0.2475 | 0.2475 | 0.2475 |
| UK Music Video Awards nominations | 1 | 0.1042 | 0.1042 | 0.1042 |
| UKMVAs 2018 nominee | 1 | 0.3618 | 0.3618 | 0.3618 |
| UKMVAs 2018 winner | 2 | 0.3618 | 0.3860 | 0.4102 |
| UKMVAs 2023 nominee | 89 | 0.0391 | 0.2428 | 0.6933 |
| UKMVAs 2023 winner | 21 | 0.0597 | 0.2954 | 0.6595 |
| UKMVAs 2024 nominee | 84 | 0.0665 | 0.2936 | 0.7591 |
| UKMVAs 2024 winner | 22 | 0.0887 | 0.3395 | 0.6992 |
| UKMVAs 2026 nominee | 87 | 0.0572 | 0.2799 | 0.8254 |
| UKMVAs 2026 winner | 18 | 0.0928 | 0.2763 | 0.6879 |
| Uncategorized | 1 | 0.3803 | 0.3803 | 0.3803 |
| Unofficial | 4 | 0.1847 | 0.3353 | 0.5655 |
| Unsigned band | 12 | 0.0375 | 0.3715 | 0.8242 |
| Unsigned director | 17 | 0.0375 | 0.2894 | 0.5782 |
| Up & Coming | 27 | 0.0687 | 0.3061 | 0.6512 |
| VFX | 1160 | 0.0291 | 0.3041 | 0.9032 |
| Video Feature | 31 | 0.1108 | 0.2808 | 0.6692 |
| Video Mixtape | 6 | 0.2811 | 0.4431 | 0.6210 |
| Video of the day | 67 | 0.0685 | 0.3301 | 0.8847 |
| Videogame trailer | 1 | 0.4623 | 0.4623 | 0.4623 |
| Virals | 15 | 0.0763 | 0.2653 | 0.6758 |

## What was measured, and what was not

The video lane measures YouTube entries only:

- Each video-measured row is a sampled source-PTS probe of the public YouTube rendition, obtained by a bounded, cookie-free local yt-dlp; it is not the work's delivered master.
- Vimeo references are recorded as `unsupported-vimeo` and were never fetched, probed, or player-inspected.
- No cookies, logins, browser profiles, remote components, or DRM/PO-token circumvention were used, and a provider refusal was never retried.
- Published poster stills are reported separately and never enter the motion, cut, luma, or saturation aggregates.
- Catalogue provider split: none x 498, other x 1673, vimeo x 3448, youtube x 12186.

## Explicit non-claims

- A published poster still is not a video frame; single-image colour, luminance, histogram, hue, and edge-density numbers carry no motion, cut, pacing, timing, sequence, or edit-rhythm evidence.
- No style, aesthetic quality, mood, lighting, camera/lens, editorial intent, authorship, identity, or creative-origin inference is made from these numbers.
- Window values are samples; a full-film census value is film-level. Census cut candidates are still scene-score exceedances, not verified edits, and a strobe record's rate is not a cut rate.
- The poster is prepared by Promonews/the CMS, not necessarily by the work's author.
- No duration was derived from a YouTube or Vimeo id; the catalogue `durationSeconds` stays null because it exposes no duration field. Measured durations come only from the acquired local source.
- Public availability is not a licence: `rightsStatus` remains `review-required`, and reuse needs its own review.
- Catalogue metadata is self-reported by Promonews and is not independently verified.
- Downloaded media and poster images are never retained: only hashes and numbers remain.
- The measured source is a platform-encoded YouTube rendition, not the work's delivered master; every video number describes that rendition only.
