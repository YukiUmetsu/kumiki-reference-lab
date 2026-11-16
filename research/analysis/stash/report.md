# STASH — published-still evidence (still-only) report

This deliverable tabulates only what the committed evidence records contain: WordPress catalogue metadata and one measured, published poster still per item. It is **still-only**: it makes no motion, cut, pacing, timing, sequence, edit-rhythm, aesthetic, style, authorship, or quality claim.

## Provenance

- Catalog items: 5399
- Video-measured records: 0
- Unique video media after dedupe: 0 (0 extra record(s) in 0 duplicate group(s))
- Still-measured records: 5277
- Still-only records (no matching video record): 5277
- Skipped rows (stills index context): 5377
- Failed acquisitions (stills index context): 0
- Skipped rows (video index context): 0
- Failed acquisitions (video index context): 0
- Catalogue items without a usable poster: 122
- Unreadable records: 0
- generatedAt: 2026-11-12T18:40:02.475812Z
- Skip reasons (stills index): no-published-poster x 122, resume-existing-record x 5255
- Per-row provider labels: unknown x 5277
- `--top 50` applied: the first 50 of 5277 measured stills are tabulated below; `aggregate.json` holds all.

STASH is a magazine feed: many posts are image galleries and not videos at all. A per-row `provider` value is only a downloadability label; it does not claim every post contains a video, and this adapter makes no video-coverage claim.

Reproduce the inputs and this report with:

```bash
python scripts/research_wordpress_stills.py catalog --site stash --out research/analysis/stash/catalog.json
python scripts/research_wordpress_stills.py collect --site stash --catalog research/analysis/stash/catalog.json --out-dir research/analysis/stash --acknowledge-rights
python scripts/research_wordpress_stills.py stills --site stash --catalog research/analysis/stash/catalog.json --out-dir research/analysis/stash --resume
python scripts/research_wordpress_stills.py report --site stash --out-dir research/analysis/stash --top 50
```

## Measured stills

5277 still-measured record(s), ordered by post id then slug. Every number describes one published image, never a video frame.
Quality-flagged stills excluded from the colour distributions and term aggregates: 13 of 5277.
`decode_w`/`decode_h` are the aspect-preserving `160×90` fit; they are derived from the source `img_w`/`img_h` when a record stores no decode size, which is the case for every current record.

| post_id | slug | title | poster_w | poster_h | img_w | img_h | decode_w | decode_h | img_bytes | mean_luma | mean_sat | hue | edge_density |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 18913 | stash-2013 | BEST OF STASH 2013! | 960 | 540 | 960 | 540 | 160 | 90 | 574511 | 0.4834 | 0.3595 | orange | 0.0775 |
| 18939 | frames-abstract-rebrand-tv3-puls | Beautiful Abstraction: Frame Rebrands TV3 Puls | 1920 | 1080 | 1920 | 1080 | 160 | 90 | 1293557 | 0.6850 | 0.3334 | cyan | 0.0178 |
| 18948 | bruner-brings-passion-billion-rising | Bruner Brings Passion to One Billion Rising | 960 | 540 | 960 | 540 | 160 | 90 | 278859 | 0.0747 | 0.0393 | neutral | 0.0234 |
| 18953 | buck-pimps-santas-ride-honda | Buck Pimps Santa’s Ride for Honda | 960 | 540 | 960 | 540 | 160 | 90 | 801677 | 0.8707 | 0.0808 | neutral | 0.0127 |
| 18965 | renato-marques-human-rights-ak-47s | Renato Marques: Of Human Rights and AK-47s | 960 | 540 | 960 | 540 | 160 | 90 | 354188 | 0.5768 | 0.0433 | neutral | 0.0115 |
| 18973 | patrick-clair-cracks-true-detective-hbo | Patrick Clair Cracks “True Detective” for HBO | 960 | 540 | 960 | 540 | 160 | 90 | 389047 | 0.1069 | 0.4341 | purple | 0.0135 |
| 19011 | argentina-tackles-world-stage-foosball | Argentina Tackles the World Stage with “FOOSBALL” | 959 | 538 | 959 | 538 | 160 | 90 | 944161 | 0.3708 | 0.5639 | orange | 0.0578 |
| 19027 | 19027 | Takashi Ohashi Wants to “Pari Pari Pari” | — | — | 640 | 214 | 160 | 54 | 79430 | 0.8494 | 0.0169 | neutral | 0.0393 |
| 19030 | donato-sansone-unleashes-portrait | Donato Sansone Unleashes “Portrait” | 960 | 540 | 960 | 540 | 160 | 90 | 230950 | 0.1272 | 0.3415 | red | 0.0173 |
| 19035 | 1500-slices-cheese-later | 1500 Slices of Cheese Later… | 960 | 540 | 960 | 540 | 160 | 90 | 537758 | 0.6021 | 0.5484 | blue | 0.0088 |
| 19038 | online-premiere-richard-hickey-francis | Online Premiere: Richard Hickey ‘Francis’ | 960 | 540 | 960 | 540 | 160 | 90 | 162346 | 0.1214 | 0.2648 | orange | 0.0216 |
| 19042 | deep-uncanny-valley-shynola-2 | Deep in the Uncanny Valley with Shynola | 960 | 540 | 960 | 540 | 160 | 90 | 483610 | 0.1547 | 0.6526 | green | 0.0215 |
| 19067 | battling-olympics-norwegian-style | Battling Toward the Olympics, Norwegian-Style | 960 | 540 | 960 | 540 | 160 | 90 | 355793 | 0.5315 | 0.4064 | cyan | 0.0450 |
| 19072 | buck-takes-schnauzers-origami-giant-trout | Buck Takes on Schnauzers, Origami and Giant Trout | 960 | 540 | 960 | 540 | 160 | 90 | 206791 | 0.9726 | 0.0459 | neutral | 0.0169 |
| 19080 | infographic-shutterstocks-global-design-trends-2014 | Infographic: Shutterstock’s Global Design Trends 2014 | 960 | 540 | 960 | 540 | 160 | 90 | 377341 | 0.5313 | 0.4017 | orange | 0.0389 |
| 19086 | imaginary-forces-hoists-black-sails | Imaginary Forces Hoists “Black Sails” | 960 | 540 | 960 | 540 | 160 | 90 | 348724 | 0.1561 | 0.3089 | yellow | 0.0461 |
| 19091 | cluster-studo-busts-nissan-juke | Cluster Studio Busts Out the Nissan Juke | 960 | 540 | 960 | 540 | 160 | 90 | 989860 | 0.2302 | 0.6604 | orange | 0.0568 |
| 19100 | manvsmachine-air-max-90 | ManvsMachine: Nike Air Max 90 | 960 | 540 | 960 | 540 | 160 | 90 | 939100 | 0.6121 | 0.1891 | magenta | 0.0296 |
| 19109 | time-based-arts-jumps-sharkbuffalorocket-vodafone | Time Based Arts Jumps the Shark/Buffalo/Rocket for Vodafone | 960 | 540 | 960 | 540 | 160 | 90 | 770180 | 0.4838 | 0.3926 | yellow | 0.0449 |
| 19117 | super-bowl-winner-audi-doberhuahau | Super Bowl Winner: Audi “Doberhuahau” | 960 | 540 | 960 | 540 | 160 | 90 | 263294 | 0.3555 | 0.4140 | blue | 0.0456 |
| 19132 | universal-everything-walking-city | Universal Everything: “Walking City” | 960 | 540 | 960 | 540 | 160 | 90 | 243648 | 0.8399 | 0.0587 | neutral | 0.0086 |
| 19145 | zeitguised-mouse-mars-cream-theme | Zeitguised: Mouse on Mars “Cream Theme” | 960 | 540 | 960 | 540 | 160 | 90 | 246467 | 0.5259 | 0.6027 | magenta | 0.0307 |
| 19153 | method-reveal-childlike-imagination-ge | Method Reveal Their “Childlike Imagination” for GE | 960 | 540 | 960 | 540 | 160 | 90 | 213462 | 0.4452 | 0.0852 | neutral | 0.0344 |
| 19159 | weareseventeen-launch-tv6 | weareseventeen Launch TV6 | 960 | 540 | 960 | 540 | 160 | 90 | 493974 | 0.4863 | 0.3302 | blue | 0.0186 |
| 19164 | quick-flix-trip-pier-paolos-cinematics | Quick Flix Trip with Pier Paolo’s “Cinematics” | 1370 | 770 | 1370 | 770 | 160 | 90 | 82743 | 0.4985 | 0.6114 | cyan | 0.0037 |
| 19178 | lumbre-tyc-sportia-2014-rebrand | Lumbre TYC “SPORTIA 2014” Rebrand | 960 | 540 | 960 | 540 | 160 | 90 | 1050704 | 0.3322 | 0.3066 | red | 0.0681 |
| 19188 | happy-v-day-supinfocom-arles-a-la-franaaise | Happy V-Day from Supinfocom Arles: “A la Française” | 960 | 540 | 960 | 540 | 160 | 90 | 1005133 | 0.4103 | 0.4690 | orange | 0.0622 |
| 19194 | kris-mercado-griswolds-red-tuxedo | Kris Mercado: The Griswolds “Red Tuxedo” | 1902 | 1070 | 1902 | 1070 | 160 | 90 | 965079 | 0.8538 | 0.0455 | neutral | 0.0979 |
| 19208 | florismennomysterysurrealism-shortcutz | Floris+Menno+Mystery+Surrealism = Shortcutz | 960 | 540 | 960 | 540 | 160 | 90 | 279799 | 0.2055 | 0.1031 | neutral | 0.0560 |
| 19217 | worlds-beautiful-toilet-paper-spot | Is this the World’s Most Beautiful Toilet Paper Spot? | 960 | 540 | 960 | 540 | 160 | 90 | 189406 | 0.8269 | 0.0382 | neutral | 0.0173 |
| 20463 | modern-love-york-times | Modern Love and The New York Times | 960 | 540 | 960 | 540 | 160 | 90 | 348818 | 0.8223 | 0.2275 | orange | 0.0167 |
| 20473 | noah-harris-julio-bashmore-peppermint | Noah Harris: Julio Bashmore “Peppermint” | 960 | 540 | 960 | 540 | 160 | 90 | 279319 | 0.1881 | 0.2129 | green | 0.0146 |
| 20494 | virgin-atlantic-departure-art-graft | Virgin Atlantic “Trip” with Art&Graft | 960 | 540 | 960 | 540 | 160 | 90 | 635393 | 0.5536 | 0.2478 | neutral | 0.0214 |
| 20504 | platige-fights-fate-vikings | Platige Fights Fate with “Vikings” | 960 | 540 | 960 | 540 | 160 | 90 | 1058719 | 0.4695 | 0.2751 | blue | 0.0598 |
| 20509 | floira-sigismondi-captures-theirry-muglers-alien | Floria Sigismondi Captures Thierry Mugler’s Alien | 960 | 540 | 960 | 540 | 160 | 90 | 579138 | 0.2276 | 0.5012 | yellow | 0.0449 |
| 20523 | supamonks-wreak-havoc-holypop | Supamonks Wreak Havoc for “Holypop” | 960 | 540 | 960 | 540 | 160 | 90 | 921905 | 0.3587 | 0.5519 | orange | 0.0452 |
| 20530 | mpc-plays-dominoes-nbcs-blacklist | MPC Plays Dominoes with NBC’s “Blacklist” | 960 | 540 | 960 | 540 | 160 | 90 | 1117086 | 0.1847 | 0.4178 | blue | 0.1119 |
| 20536 | andy-martin-selfie-short-pictoplasma | Andy Martin “Selfie” Short for Pictoplasma | 960 | 540 | 960 | 540 | 160 | 90 | 394037 | 0.7389 | 0.3615 | green | 0.0306 |
| 20544 | job-joris-marieke-march-the-daily-drumbeat | Job, Joris & Marieke March to “The Daily Drumbeat” | 960 | 540 | 960 | 540 | 160 | 90 | 83668 | 0.5256 | 0.0000 | neutral | 0.0560 |
| 20554 | franck-dion-monsieur-cok | Franck Dion “Monsieur COK” | 960 | 540 | 960 | 540 | 160 | 90 | 882603 | 0.5039 | 0.2457 | orange | 0.0304 |
| 20560 | le-couch-gag-dans-francais-par-sylvain-chomet | Le Couch Gag dans Francais par Sylvain Chomet | 960 | 540 | 960 | 540 | 160 | 90 | 322796 | 0.3303 | 0.2742 | orange | 0.0551 |
| 20568 | totuma-view-venezuala | Death and Danger In Venezuela | — | — | 640 | 908 | 63 | 90 | 200190 | 0.3469 | 0.7261 | red | 0.0615 |
| 20578 | darkly-dark-darkness-dark-souls-ii | The Darkly Dark Darkness of Dark Souls II | 960 | 540 | 960 | 540 | 160 | 90 | 345804 | 0.2231 | 0.2006 | orange | 0.0210 |
| 20592 | michael-fragstein-happiness-hole | Michael Fragstein: “Happiness Has A Hole” | 960 | 540 | 960 | 540 | 160 | 90 | 465014 | 0.6874 | 0.0897 | neutral | 0.0280 |
| 20601 | titanfall-intro-sequence-spov | Titanfall intro sequence from Spov | 960 | 540 | 960 | 540 | 160 | 90 | 708388 | 0.3025 | 0.2051 | neutral | 0.0369 |
| 20613 | chezeddy-concorde-sons | ChezEddy for CONCORDE “Sons” | 960 | 540 | 960 | 540 | 160 | 90 | 439770 | 0.7221 | 0.0000 | neutral | 0.0979 |
| 20648 | mill-titanfall | The Mill: Titanfall “Shadow” | 960 | 540 | 960 | 540 | 160 | 90 | 1055924 | 0.4859 | 0.3440 | green | 0.0946 |
| 20656 | rafael-mayrhofer-kangaroos-jump-backwards | Rafael Mayrhofer: “Kangaroos Can’t Jump Backwards” | 960 | 540 | 960 | 540 | 160 | 90 | 737209 | 0.4237 | 0.3915 | orange | 0.0490 |
| 20667 | bbdg-open-carl-sagans-cosmos-fox | BBDG Open Carl Sagan’s “Cosmos” for FOX | 960 | 540 | 960 | 540 | 160 | 90 | 372000 | 0.1971 | 0.3691 | neutral | 0.0287 |
| 20675 | rushes-tiny-worlds-trilogy | Rushes’ “Tiny Worlds” Trilogy | 1281 | 719 | 1281 | 719 | 160 | 90 | 1084686 | 0.4350 | 0.1373 | neutral | 0.0423 |

## Distributions by term

Each term row aggregates only the measured stills that carry that term. Term names were resolved from the WordPress taxonomy endpoints and cached in the catalogue. Counts describe this measured sample, not the full catalogue.

### categories

| term | term_id | stills | luma min | luma median | luma max |
| --- | --- | --- | --- | --- | --- |
| Featured | 69 | 4918 | 0.0277 | 0.4707 | 0.9754 |
| Animation | 42 | 2703 | 0.0277 | 0.5044 | 0.9754 |
| CG | 30 | 2590 | 0.0366 | 0.4397 | 0.9609 |
| Character Animation | 16 | 2520 | 0.0277 | 0.4984 | 0.9754 |
| Advertising | 14 | 1688 | 0.0400 | 0.4658 | 0.9726 |
| Motion Design | 12 | 1635 | 0.0296 | 0.4895 | 0.9687 |
| Short Films | 18 | 1126 | 0.0296 | 0.4926 | 0.9754 |
| Brand film | 2673 | 1027 | 0.0524 | 0.5112 | 0.9639 |
| 3D Style | 4251 | 936 | 0.0592 | 0.4823 | 0.9369 |
| VFX | 17 | 904 | 0.0473 | 0.3905 | 0.9303 |
| Music Video | 13 | 577 | 0.0473 | 0.4613 | 0.9187 |
| Broadcast Design | 15 | 439 | 0.0541 | 0.4459 | 0.9263 |
| Illustration | 2067 | 315 | 0.0524 | 0.5634 | 0.9639 |
| Games | 21 | 276 | 0.0277 | 0.4018 | 0.9754 |
| Titles | 2193 | 258 | 0.0366 | 0.4404 | 0.8084 |
| Stop Motion | 34 | 250 | 0.0466 | 0.4906 | 0.9208 |
| Feed | 4 | 226 | 0.0524 | 0.4272 | 0.9222 |
| Student Work | 29 | 195 | 0.0711 | 0.4985 | 0.9454 |
| Explainer | 3030 | 192 | 0.1460 | 0.5386 | 0.9639 |
| Branded Content | 1994 | 174 | 0.1289 | 0.5060 | 0.9037 |
| AI | 8368 | 136 | 0.0718 | 0.4367 | 0.9043 |
| Events | 22 | 123 | 0.0439 | 0.4531 | 0.8658 |
| Typography | 2557 | 113 | 0.0833 | 0.5055 | 0.9459 |
| Graphic Design | 24 | 111 | 0.0747 | 0.5055 | 0.9609 |
| Partner Events | 10756 | 109 | 0.0717 | 0.4129 | 0.9597 |
| Self-promotion | 43 | 79 | 0.1440 | 0.5192 | 0.9568 |
| Motion Capture | 2134 | 76 | 0.0869 | 0.4208 | 0.8063 |
| BTS | 344 | 69 | 0.2062 | 0.5027 | 0.9032 |
| BTS | 343 | 62 | 0.1306 | 0.4926 | 0.6993 |
| Spec work | 2149 | 58 | 0.0891 | 0.4233 | 0.7959 |
| Installation | 79 | 48 | 0.1109 | 0.4689 | 0.9274 |
| Realtime | 4156 | 41 | 0.0869 | 0.4268 | 0.8373 |
| Guest Editorial | 12730 | 33 | 0.2081 | 0.3757 | 0.6876 |
| photoreal | 4110 | 33 | 0.1037 | 0.4795 | 0.8725 |
| Rotoscope | 2816 | 31 | 0.1232 | 0.4530 | 0.7739 |
| Feature Film | 19 | 28 | 0.1005 | 0.4106 | 0.7406 |
| Branding | 2159 | 23 | 0.2000 | 0.5130 | 0.9687 |
| Anime | 7384 | 22 | 0.1447 | 0.4956 | 0.6941 |
| Experiential | 2527 | 22 | 0.0812 | 0.4188 | 0.9274 |
| Miniatures | 2666 | 22 | 0.2349 | 0.3981 | 0.6952 |
| Collage | 9347 | 21 | 0.3367 | 0.5783 | 0.8001 |
| Puppets | 2305 | 20 | 0.1740 | 0.4779 | 0.7028 |
| Architecture | 4080 | 18 | 0.1561 | 0.5091 | 0.7902 |
| Processing | 2129 | 18 | 0.1499 | 0.3814 | 0.6595 |
| Style Frames | 48 | 18 | 0.1733 | 0.5392 | 0.7880 |
| Demo Reel | 4234 | 16 | 0.2343 | 0.5139 | 0.9123 |
| Compositing | 3783 | 14 | 0.3584 | 0.4866 | 0.5626 |
| Zoetrope | 2071 | 13 | 0.2266 | 0.3527 | 0.7851 |
| Glitch | 4095 | 12 | 0.1929 | 0.4306 | 0.7352 |
| Projection | 1979 | 12 | 0.1109 | 0.2661 | 0.6697 |

## Why there is no motion evidence

There is no video lane for this site, by design:

- Every video is a third-party Vimeo/YouTube embed (`player.vimeo.com/video/<id>` or `www.youtube.com/embed/<id>`); no progressive MP4/HLS file is published.
- This site's embeds are Vimeo-only, and the repository records Vimeo as unsupported.
- No cookies, auth, player-API tricks, or DRM circumvention were used, and no embed was probed.
- Therefore this report cannot and does not measure motion, cuts, pacing, timing, sequences, or edit rhythm. A poster still is not a video frame.
- STASH is a magazine feed: many posts are image galleries, not videos, so even the per-row provider label is not a video-coverage claim.

## Comparability

- poolable: `false`
- comparable within: same site, same rendition, same runtime band, non-burst, >=25% coverage
- not comparable to: other sites, other renditions, full-film claims derived from window rates

Caveats:

- STASH: poolable is false; every number describes this site's measured sample only.
- 5277 of 5399 catalogue items were measured (97.74%) by published poster-still availability.
- Measured rows are not a random sample: availability and recency select them, so cross-site pooling is invalid.
- Provider families are not interchangeable: unknown x 5277.
- Renditions differ by site and record: one published poster still per item; a still is not a decoded video frame.
- Measured renditions vary by resolution (1920x1080 x 1869, 960x540 x 1289, 2000x1125 x 152, 640x360 x 152, 2389x1344 x 124, 1080x608 x 93, 2560x1440 x 80, 1280x720 x 50, +717 more), frame rate (none recorded) and bitrate (none recorded), so the sample is not a controlled transform.
- Coverage is not applicable: this lane measures no video runtime, so no sampled fraction or window gap exists.
- 24 extra record(s) in 10 duplicate group(s) share media; unique media after dedupe is 5253.
- Still/video overlap: 5277 still record(s); this report has no video-measured records, so no video number is pooled with stills.

## Coverage

No video runtime was measured in this still-only report, so the coverage distribution is empty by construction; the measured-stills table carries each source `img_w×img_h` and derived `decode_w×decode_h`.

| statistic | coverage_pct |
| --- | --- |
| min | — |
| p10 | — |
| median | — |
| p90 | — |
| max | — |
| below 20% | —% |
| below 10% | —% |
| median unobserved gap between windows | — s |

## Full-film census

census: not present (0 of 0 video-measured records have a census record).

## Census reconciliation

census: not present (reconciliation needs at least one full-film census record).

## Explicit non-claims

- A published poster still is not a video frame; single-image colour, luminance, histogram, hue, and edge-density numbers carry no motion, cut, pacing, timing, sequence, or edit-rhythm evidence.
- No style, aesthetic quality, mood, lighting, camera/lens, editorial intent, authorship, identity, or creative-origin inference is made from these numbers.
- Window values are samples; a full-film census value is film-level. Census cut candidates are still scene-score exceedances, not verified edits, and a strobe record's rate is not a cut rate.
- The poster is prepared by the site/CMS, not necessarily by the work's author; for STASH it may be a gallery image.
- Public availability is not a licence: `rightsStatus` remains `review-required`, and reuse needs its own review.
- Catalogue metadata is self-reported by the site and is not independently verified.
- The site's REST API exposes no director, duration, brand, or agency values for Directors' Library; those fields are absent, not invented.
- Downloaded poster images are never retained: only hashes and numbers remain.
- Vimeo/YouTube embeds were never acquired or probed.
