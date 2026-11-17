# Quality-first clip selection

Generated offline by `scripts/select_quality_clips.py` from the stored
catalogs and indexes under `research/analysis/`. No media was fetched and
nothing in `videos/`, `census/` or `audio/` was written.

The selection is not a claim that these are the best works on the web. It
is a claim that these are the rows the stored catalogs can *justify*, and
each section states what its rule over-samples.

## Rules

Applied in tier order; a row enters the first tier it matches, so each
work appears at most once per site.

### motiondesignawards

1. `awards[].type intersects {DOTY, SOTY, VOTM, VOTY}`
2. `awards[].type contains VOTD and scores.overall >= 8.0`
3. `scores.overall >= 8.5`

Order: tier asc, scores.overall desc, totalVotes desc.

**Bias:** Crowd vote, not jury: `scores.overall` is an open audience average and VOTD/VOTM are daily/monthly vote wins, so tiers 1-2 over-sample work with an active voting audience. Tiers 2-3 over-sample recent, high-traffic uploads because the top of the score distribution is thin. The rule cannot see craft: a well-voted but conventional piece ranks above an unvoted experimental one.

### aicp

1. `categories[] intersects {Advertising Excellence, Advertising Excellence / Campaign, Advertising Excellence / International, Best of Region, National Campaign, Integrated Campaign}`
2. `categories[] non-empty and year <= 2023`

Order: tier asc, year asc, title asc.

**Bias:** Prize categories favour big-budget, US-agency work ('Advertising Excellence', 'Best of Region', 'National Campaign'), so tier 1 over-samples large production companies and award-show entries. Tier 2 (`year <= 2023`) deliberately over-samples older archive years, whose categories are sparser and whose downloadable renditions are less reliable; it is a coverage correction, not a claim that older work is better. 134 of 2,715 entries carry no category and cannot enter at all.

### promonews

1. `categories[] contains 'UKMVAs <year> winner'`
2. `categories[] contains 'UKMVAs <year> nominee'`
3. `categories[] contains 'Pick of the Day'`

Order: tier asc, publishedDate asc.

**Bias:** UK-only music video coverage: every selected row is a British promo, so no non-UK or non-music-video work can enter. Tier 1-2 over-sample UKMVAs winners/nominees, and the CMS only tags 2018 and 2022-2026, so the tier is also a recent-years filter. Tier 3 over-samples 2018+ 'Pick of the Day' promos. Festival and long-form work is invisible.

### directorslibrary

1. `terms.award[] non-empty`
2. `terms.festival[] intersects {Cannes, Sundance, Venice Biennale, Toronto (TIFF), Berlinale, SXSW}`

Order: tier asc, publicationDate asc.

**Bias:** Festival films, not music videos: the site is a directors' directory of shorts, commercials and features, so tiers 1-2 over-sample narrative shorts that premiered at Cannes/Sundance/Venice/TIFF/Berlinale/SXSW. The 461 `terms.festival[]` and 69 `terms.award[]` tags are editor-applied and unevenly maintained across 5,412 items, so absence of a tag is not absence of quality.

### shots

1. `brandName == 'Straight 8'`
2. `clientName, agencyName, artists[] and year all non-empty (documentation-completeness proxy, not a quality claim)`

Order: tier asc, year desc.

**Bias:** Tier 1 is the 9 'Straight 8' entries, a sponsor contest rather than a quality ranking. Tier 2 is explicitly a documentation-completeness proxy (client + agency + artists[] + year), not a quality claim: it over-samples recent, fully credited commercial work from large agencies and excludes 27,701 clips with no year and 15,550 with no agency, regardless of how good they are. shots.net publishes no editorial or award signal at all.

### stash

No video selection.

STASH has no quality field: `Featured` is true on 91.9% of 5,399 posts and the catalog publishes no awards, categories or festival terms. It also mixes image galleries with videos. Selecting 'featured' rows would rank the site's own promotion, not work quality, so no video target list is emitted. STASH still has 5,277 measured stills and can supply poster-level evidence.

## Cross-site works (tier 0)

A work on two or more sites outranks any single-site tier. Matching is on
normalised title + company and title + director (NFKD, lowercase, `&` ->
`and`, punctuation collapsed, promonews' `" by <director>"` suffix
stripped) and is joined transitively. `rankTier` is 0 for these rows while
`tier` keeps the rule that selected them.

294 selected rows come from 219 of the 248 works that appear on two or more sites. A row is listed even when its partner on the other site was not selected.

| work | tier | members (selected rows carry their rule tier) |
|---|---|---|
| Flock | 1/2 | `aicp` 1016304 (tier 1), `aicp` 1026335 (not selected), `shots` 34173 (tier 2) |
| Listen To Your Heart | 2 | `aicp` 1021479 (not selected), `shots` 35751 (tier 2) |
| Ticket to Dream | 2 | `aicp` 1029112 (not selected), `shots` 34185 (tier 2) |
| Dream Job | 2 | `aicp` 1031163 (not selected), `shots` 35728 (tier 2) |
| Coffin | 1/2 | `aicp` 1032167 (tier 1), `shots` 34938 (tier 2) |
| Coat | 1/2 | `aicp` 1032505 (tier 1), `shots` 34937 (tier 2) |
| Curfew | 1/2 | `aicp` 1032531 (tier 1), `shots` 34939 (tier 2) |
| Gonna Dance | 2 | `aicp` 1033321 (not selected), `shots` 36230 (tier 2) |
| Assume That I Can | 2 | `aicp` 1034758 (not selected), `aicp` 1083932 (not selected), `shots` 33036 (tier 2) |
| Kilometers of Love | 2 | `aicp` 1071746 (not selected), `shots` 36841 (tier 2) |
| Capture | 2 | `aicp` 1072208 (not selected), `shots` 34765 (tier 2) |
| Don’t Let Me Go | 2 | `aicp` 1075514 (not selected), `shots` 33964 (tier 2) |
| Good vs Evil | 2/2 | `aicp` 107993 (tier 2), `shots` 40341 (tier 2) |
| Brian Cox Goes To College | 2 | `aicp` 1080887 (not selected), `shots` 36304 (tier 2) |
| Everything or Nothing | 2 | `aicp` 1085510 (not selected), `shots` 34172 (tier 2) |
| Heartstrings | 2 | `aicp` 1086834 (not selected), `shots` 35236 (tier 2) |
| Your Door to More | 2/2 | `aicp` 1088311 (not selected), `shots` 35853 (tier 2), `shots` 35858 (tier 2) |
| Sicker Than the Patients | 2 | `aicp` 1089088 (not selected), `shots` 33267 (tier 2) |
| Your Way Out | 2 | `aicp` 1100016 (not selected), `shots` 39091 (tier 2) |
| Unavailable | 2 | `aicp` 1100781 (not selected), `shots` 38642 (tier 2) |
| For Papa! | 2 | `aicp` 1103416 (not selected), `shots` 38635 (tier 2) |
| Tableau | 2 | `aicp` 1106443 (not selected), `shots` 37398 (tier 2) |
| Dress Yourself | 2 | `aicp` 1107045 (not selected), `shots` 37539 (tier 2) |
| Shape of Dreams | 2 | `aicp` 1113509 (not selected), `shots` 39319 (tier 2) |
| I Think of You (Dying) | 2 | `aicp` 1114119 (not selected), `shots` 36416 (tier 2) |
| No Project Without Drama | 2 | `aicp` 1114884 (not selected), `shots` 37317 (tier 2) |
| 18 Months | 2 | `aicp` 1121168 (not selected), `shots` 36848 (tier 2) |
| Apple TV Rebrand | 2 | `aicp` 1122818 (not selected), `shots` 40169 (tier 2) |
| A Critter Carol | 2 | `aicp` 1123043 (not selected), `shots` 38190 (tier 2) |
| In Good Time | 2 | `aicp` 1124262 (not selected), `shots` 37685 (tier 2) |
| Conquer the First School Poo | 2 | `aicp` 1124550 (not selected), `shots` 36519 (tier 2) |
| Believe Part 2: All Hail Gravy | 2 | `aicp` 1125092 (not selected), `shots` 36012 (tier 2) |
| The Count | 2/2 | `aicp` 1132614 (not selected), `aicp` 1146412 (not selected), `shots` 36189 (tier 2), `shots` 39879 (tier 2) |
| Obsession | 2 | `aicp` 1135445 (not selected), `shots` 37074 (tier 2) |
| Travel Changed Me | 2 | `aicp` 1136043 (not selected), `shots` 36237 (tier 2) |
| Power Struggle | 2 | `aicp` 1137677 (not selected), `shots` 36503 (tier 2) |
| Close | 2 | `aicp` 1140282 (not selected), `shots` 38145 (tier 2) |
| FruitHead | 2 | `aicp` 1160902 (not selected), `shots` 37726 (tier 2) |
| Write the Future | 1/1 | `aicp` 172258 (tier 1), `aicp` 802235 (tier 1), `shots` 9136 (not selected) |
| Scorsese | 2 | `aicp` 195187 (tier 2), `shots` 21337 (not selected) |
| Speed Chain | 2/2 | `aicp` 198809 (tier 2), `shots` 35142 (tier 2) |
| Parallels | 2/2 | `aicp` 202637 (tier 2), `shots` 35030 (tier 2) |
| Questions | 2 | `aicp` 205678 (tier 2), `shots` 18095 (not selected) |
| The Force | 1/1/2 | `aicp` 214411 (tier 1), `aicp` 667470 (tier 1), `shots` 32741 (tier 2) |
| Barbershop Sextet | 2/2 | `aicp` 235432 (tier 2), `shots` 30583 (tier 2) |
| Detectives | 2 | `aicp` 249322 (tier 2), `shots` 26946 (not selected) |
| Love, Lawyers, and The Government | 2 | `aicp` 252408 (tier 2), `shots` 25604 (not selected) |
| Luck is Alive | 2 | `aicp` 252883 (tier 2), `shots` 27637 (not selected) |
| Open Spaces | 2/2 | `aicp` 254212 (tier 2), `shots` 26242 (tier 2) |
| Parisian Love | 2 | `aicp` 271183 (tier 2), `shots` 20169 (not selected) |
| Road Trip | 2/2 | `aicp` 273273 (tier 2), `shots` 30572 (tier 2) |
| Point and Kill | 2 | `aicp` 282274 (tier 2), `shots` 25876 (not selected), `shots` 28181 (not selected) |
| Step-Grandma | 2/1 | `aicp` 284738 (tier 2), `aicp` 697 (tier 1), `shots` 25557 (not selected) |
| Super. Human. | 1/2 | `aicp` 285105 (tier 1), `shots` 25538 (tier 2) |
| Teenage Dream | 2/2 | `aicp` 289930 (tier 2), `shots` 25961 (tier 2) |
| Room With a View | 2 | `aicp` 3091 (tier 2), `shots` 25769 (not selected) |
| Piñata | 1 | `aicp` 321335 (tier 1), `shots` 2908 (not selected) |
| Juju | 2 | `aicp` 325020 (tier 2), `shots` 804 (not selected) |
| Bus Station | 2/2 | `aicp` 364547 (tier 2), `shots` 36543 (tier 2) |
| Tag | 2 | `aicp` 404880 (tier 2), `shots` 7580 (not selected) |
| Freestyle | 1/2 | `aicp` 407515 (tier 1), `shots` 40425 (tier 2) |
| Beach | 2/2/2 | `aicp` 414422 (tier 2), `aicp` 819766 (tier 2), `shots` 36940 (tier 2) |
| Best Job | 1 | `aicp` 415239 (tier 1), `shots` 10812 (not selected) |
| Back to the Start | 1 | `aicp` 417495 (tier 1), `shots` 21810 (not selected) |
| Greatness | 2/2 | `aicp` 426429 (tier 2), `shots` 35188 (tier 2) |
| Susan Glenn | 2/1/2 | `aicp` 434601 (tier 2), `aicp` 792667 (tier 1), `shots` 35806 (tier 2) |
| The Bear | 1/2 | `aicp` 448614 (tier 1), `shots` 118 (tier 2) |
| The Long Wait | 1/2 | `aicp` 450361 (tier 1), `shots` 156 (tier 2) |
| Love | 2 | `aicp` 456708 (tier 2), `shots` 23145 (not selected) |
| Superstar | 2/1/2/2 | `aicp` 461654 (tier 2), `aicp` 650496 (tier 1), `shots` 21276 (not selected), `shots` 31663 (tier 2), `shots` 39014 (tier 2) |
| Misunderstood | 2 | `aicp` 469647 (tier 2), `shots` 26555 (not selected) |
| Ship My Pants | 2 | `aicp` 473511 (tier 2), `shots` 22319 (not selected) |
| The Bear & The Hare | 2 | `aicp` 474453 (tier 2), `shots` 18593 (not selected), `shots` 20205 (not selected) |
| Paper | 2/2 | `aicp` 494880 (tier 2), `aicp` 667628 (tier 2), `shots` 18398 (not selected) |
| 5B | 2/2 | `aicp` 505387 (tier 2), `aicp` 696717 (tier 2), `shots` 18988 (not selected) |
| Back to School Essentials | 2/2 | `aicp` 505697 (tier 2), `shots` 19722 (tier 2) |
| Cellophane | 2 | `aicp` 508598 (tier 2), `shots` 18601 (not selected) |
| Creativity for All | 2 | `aicp` 509547 (tier 2), `shots` 20909 (not selected) |
| I Want You to Panic | 2 | `aicp` 513532 (tier 2), `shots` 19396 (not selected) |
| Infamous Since 1864 | 2/2/2 | `aicp` 513777 (tier 2), `aicp` 636761 (tier 2), `aicp` 699163 (tier 2), `shots` 19893 (not selected) |
| Journey to Independence | 2 | `aicp` 514921 (tier 2), `shots` 18560 (not selected) |
| Let the Song Play | 2 | `aicp` 515351 (tier 2), `shots` 19577 (not selected) |
| Next Episode | 1 | `aicp` 516914 (tier 1), `shots` 19335 (not selected) |
| Barbers | 2/2 | `aicp` 516931 (tier 2), `shots` 38851 (tier 2) |
| Only Slightly More Exaggerated | 2 | `aicp` 518095 (tier 2), `shots` 18432 (not selected), `shots` 18445 (not selected) |
| Rebuild the World | 2 | `aicp` 519392 (tier 2), `shots` 19694 (not selected) |
| Silence The Critics | 2/2 | `aicp` 521190 (tier 2), `aicp` 689206 (tier 2), `shots` 20149 (not selected) |
| The Underdogs | 2 | `aicp` 523869 (tier 2), `shots` 18406 (not selected) |
| Wait | 2 | `aicp` 524463 (tier 2), `shots` 20337 (not selected) |
| Wake Up | 2 | `aicp` 524789 (tier 2), `shots` 20708 (not selected) |
| A Little Company | 2 | `aicp` 526874 (tier 2), `shots` 16872 (not selected) |
| Duel | 2 | `aicp` 527775 (tier 2), `shots` 26488 (not selected) |
| Gosh | 2 | `aicp` 529188 (tier 2), `shots` 20162 (not selected) |
| My Mutant Brain | 2/1/2 | `aicp` 530167 (tier 2), `aicp` 679230 (tier 1), `shots` 33158 (tier 2) |
| Advertising Ruins Everything | 2/2 | `aicp` 531352 (tier 2), `shots` 159 (tier 2), `shots` 87 (not selected) |
| Color Flood | 2 | `aicp` 533968 (tier 2), `shots` 73 (not selected) |
| Dream Crazier | 1/2 | `aicp` 535229 (tier 1), `shots` 18420 (not selected), `shots` 18421 (tier 2), `shots` 19760 (not selected) |
| FUN! | 2 | `aicp` 535574 (tier 2), `shots` 19016 (not selected) |
| Mama Said Knock You Out | 2 | `aicp` 538199 (tier 2), `shots` 16208 (not selected) |
| Only Slightly Exaggerated | 2/2 | `aicp` 539113 (tier 2), `shots` 38341 (tier 2) |
| Share Your Gifts | 2 | `aicp` 541455 (tier 2), `shots` 14796 (not selected) |
| Polar Bears | 2 | `aicp` 54345 (tier 2), `shots` 18501 (not selected) |
| The Face of Distracted Driving: Forrest | 2 | `aicp` 548585 (tier 2), `shots` 20365 (not selected) |
| The New Normal | 2 | `aicp` 550930 (tier 2), `shots` 21313 (not selected) |
| Lost Panda | 2 | `aicp` 550942 (tier 2), `shots` 22548 (not selected) |
| The Seven Worlds | 2 | `aicp` 551756 (tier 2), `shots` 17790 (not selected) |
| The Shot | 2 | `aicp` 552048 (tier 2), `shots` 14795 (not selected) |
| The Truth Is Worth It: Rigor | 1 | `aicp` 553521 (tier 1), `shots` 19028 (not selected) |
| Therapist | 2/2 | `aicp` 553912 (tier 2), `shots` 158 (tier 2) |
| This is America | 2 | `aicp` 554979 (tier 2), `shots` 18989 (not selected), `shots` 20705 (not selected) |
| Unlock | 2 | `aicp` 555287 (tier 2), `shots` 154 (not selected) |
| Welcome to the Global Girls Alliance | 2 | `aicp` 556249 (tier 2), `shots` 34986 (not selected) |
| Smile | 2 | `aicp` 559311 (tier 2), `shots` 31457 (not selected) |
| Welcome Home | 2 | `aicp` 561806 (tier 2), `shots` 22790 (not selected) |
| Up&Up | 2 | `aicp` 570797 (tier 2), `shots` 21992 (not selected) |
| Fantastic Voyage | 2 | `aicp` 576346 (tier 2), `shots` 22588 (not selected), `shots` 25051 (not selected) |
| Launch It | 2 | `aicp` 585116 (tier 2), `shots` 22705 (not selected) |
| Never Lost | 2 | `aicp` 587172 (tier 2), `shots` 23566 (not selected) |
| REVIVED | 2 | `aicp` 588159 (tier 2), `shots` 26839 (not selected) |
| sad day | 2 | `aicp` 588988 (tier 2), `shots` 22587 (not selected) |
| Save Ralph | 2/1 | `aicp` 589544 (tier 2), `aicp` 790744 (tier 1), `shots` 24568 (not selected) |
| The Journey | 2/2 | `aicp` 593589 (tier 2), `aicp` 684345 (tier 2), `shots` 24607 (not selected) |
| The Whole Working-From-Home Thing | 2 | `aicp` 596963 (tier 2), `shots` 22244 (not selected) |
| Unboxing | 2 | `aicp` 597528 (tier 2), `shots` 23913 (not selected) |
| You Can't Stop Us | 2/2 | `aicp` 600823 (tier 2), `aicp` 708923 (tier 2), `shots` 21911 (not selected), `shots` 22379 (not selected) |
| You Love Me | 2 | `aicp` 622847 (tier 2), `shots` 23319 (not selected) |
| The Marketplace | 2 | `aicp` 633991 (tier 2), `shots` 26897 (not selected) |
| The Reset | 2/1 | `aicp` 638345 (tier 2), `aicp` 677616 (tier 1), `shots` 24837 (not selected) |
| The Spider and the Window | 2 | `aicp` 639524 (tier 2), `shots` 27166 (not selected) |
| The Truth Takes a Journalist | 2 | `aicp` 640443 (tier 2), `shots` 25960 (not selected) |
| This is Not America | 2 | `aicp` 641940 (tier 2), `shots` 27456 (not selected) |
| Tracked | 2/2 | `aicp` 643626 (tier 2), `shots` 27948 (tier 2) |
| Welcome to Irish Spring | 2 | `aicp` 646428 (tier 2), `shots` 27115 (not selected) |
| Whopper Freakout | 2/2 | `aicp` 654379 (tier 2), `shots` 32997 (tier 2) |
| Touch | 2/2 | `aicp` 657439 (tier 2), `shots` 8048 (tier 2) |
| Groundhog Day | 1 | `aicp` 666364 (tier 1), `shots` 20800 (not selected) |
| Born In Quarantine | 1 | `aicp` 678144 (tier 1), `shots` 26449 (not selected) |
| The Small Escape | 1 | `aicp` 678788 (tier 1), `shots` 19901 (not selected) |
| Five & The Missing Jewels | 2 | `aicp` 687566 (tier 2), `shots` 18359 (not selected) |
| Nobody is Normal | 2 | `aicp` 688551 (tier 2), `shots` 23252 (not selected) |
| Just Another Day | 1 | `aicp` 688861 (tier 1), `shots` 26942 (not selected) |
| Aria | 2 | `aicp` 695631 (tier 2), `shots` 26028 (not selected) |
| Sapeurs | 2 | `aicp` 700229 (tier 2), `shots` 20562 (not selected) |
| Feel It Still | 2/2 | `aicp` 701185 (tier 2), `aicp` 727552 (tier 2), `shots` 18722 (not selected) |
| Not Everything Makes the Cut | 2 | `aicp` 703433 (tier 2), `shots` 107 (not selected) |
| This is our BBC | 2/2 | `aicp` 708628 (tier 2), `shots` 37172 (tier 2) |
| Voice of Belief | 1 | `aicp` 709510 (tier 1), `shots` 14576 (not selected) |
| Lo and Behold: Reveries of the Connected World | 2 | `aicp` 710184 (tier 2), `shots` 22092 (not selected) |
| Get Smoooth Again | 2 | `aicp` 725131 (tier 2), `shots` 25298 (not selected) |
| It's Halftime in America | 2/2 | `aicp` 725619 (tier 2), `shots` 29957 (tier 2) |
| Space Station | 2 | `aicp` 726525 (tier 2), `shots` 16257 (not selected) |
| Adventure Awaits | 2/2 | `aicp` 731416 (tier 2), `shots` 40032 (tier 2) |
| Michelob ULTRA Courtside | 2 | `aicp` 738558 (tier 2), `shots` 25158 (not selected) |
| Swipe Night | 1/2/1 | `aicp` 738913 (tier 1), `aicp` 772809 (tier 2), `aicp` 792895 (tier 1), `shots` 20643 (not selected) |
| Tinder Swipe Night: Killer Weekend | 2/2 | `aicp` 739296 (tier 2), `shots` 28140 (tier 2) |
| Formation | 2 | `aicp` 740214 (tier 2), `shots` 18701 (not selected) |
| Humble | 2 | `aicp` 745622 (tier 2), `shots` 28458 (not selected) |
| Will Finds a Way – Dennis Smith Jr. | 2 | `aicp` 748325 (tier 2), `shots` 19172 (not selected) |
| Will Finds a Way – Natasha Hastings | 2 | `aicp` 749462 (tier 2), `shots` 19170 (not selected) |
| Will Finds a Way – Teddy Riner | 2 | `aicp` 749498 (tier 2), `shots` 19171 (not selected) |
| Google Home of The Whopper | 2 | `aicp` 751026 (tier 2), `shots` 21037 (not selected) |
| Grow Your Fortune | 2 | `aicp` 757343 (tier 2), `shots` 21415 (not selected) |
| True Name | 2 | `aicp` 771922 (tier 2), `shots` 25159 (not selected), `shots` 31779 (not selected) |
| Oh My God | 2 | `aicp` 772464 (tier 2), `shots` 26879 (not selected) |
| Farewell, Work Holiday Parties | 1 | `aicp` 778862 (tier 1), `shots` 23425 (not selected) |
| HBO Imagine | 1 | `aicp` 779163 (tier 1), `shots` 669 (not selected) |
| Pompeii | 1 | `aicp` 782080 (tier 1), `shots` 24710 (not selected), `shots` 24718 (not selected) |
| Nike+FuelBand | 1 | `aicp` 783533 (tier 1), `shots` 33965 (not selected) |
| Rule Yourself - Michael Phelps | 1 | `aicp` 788257 (tier 1), `shots` 19180 (not selected) |
| Rule Yourself - USA Women's Gymnastics | 1 | `aicp` 788274 (tier 1), `shots` 19181 (not selected) |
| New Girl | 2/2 | `aicp` 790580 (tier 2), `shots` 25580 (tier 2) |
| The Displaced | 2/2 | `aicp` 806867 (tier 2), `shots` 28158 (tier 2) |
| Generation Lockdown | 2 | `aicp` 813041 (tier 2), `shots` 18627 (not selected) |
| Superb Owl | 2 | `aicp` 818111 (tier 2), `shots` 25306 (not selected) |
| Volvo Twister | 2 | `aicp` 82525 (tier 2), `shots` 8064 (not selected), `shots` 8067 (not selected) |
| Daughter | 2 | `aicp` 828636 (tier 2), `shots` 20603 (not selected) |
| Liberty Fields | 2 | `aicp` 829376 (tier 2), `shots` 19484 (not selected) |
| The Singularity | 2/2 | `aicp` 844786 (tier 2), `shots` 29960 (tier 2) |
| Share The Joy | 2/2 | `aicp` 846687 (tier 2), `shots` 29457 (tier 2) |
| Flip | 2/2 | `aicp` 847762 (tier 2), `shots` 27732 (tier 2) |
| The Greatest | 1/2 | `aicp` 848010 (tier 1), `shots` 29563 (tier 2) |
| Rocky | 2/2 | `aicp` 856489 (tier 2), `shots` 28596 (tier 2) |
| Highland Rider | 2/2 | `aicp` 856976 (tier 2), `shots` 29030 (tier 2) |
| The Rift | 2/2 | `aicp` 859538 (tier 2), `shots` 29389 (tier 2) |
| Summer Never Sleeps | 2/2 | `aicp` 860633 (tier 2), `shots` 28946 (tier 2) |
| Music For A Sushi Restaurant | 2 | `aicp` 863060 (tier 2), `shots` 29271 (not selected) |
| Mrs. Hayes | 2/2 | `aicp` 885127 (tier 2), `shots` 29504 (tier 2) |
| Save the Survivors | 2/2 | `aicp` 886237 (tier 2), `shots` 29311 (tier 2) |
| Remember the Why | 2/2 | `aicp` 886712 (tier 2), `shots` 30767 (tier 2) |
| Trust Is Earned | 2/2/2 | `aicp` 889740 (tier 2), `shots` 28969 (tier 2), `shots` 34707 (tier 2) |
| The Land of The Unfree | 2/2 | `aicp` 889870 (tier 2), `shots` 28217 (tier 2) |
| The Great Escape | 2 | `aicp` 915979 (not selected), `shots` 31008 (tier 2) |
| Jumping Through Hoops | 2 | `aicp` 921473 (not selected), `shots` 30329 (tier 2) |
| Fuzzy Feelings | 2 | `aicp` 925179 (not selected), `aicp` 986197 (not selected), `shots` 32271 (tier 2) |
| Me, My Autism & I | 2 | `aicp` 934491 (not selected), `shots` 30402 (tier 2) |
| Find Your Summer | 2 | `aicp` 940038 (not selected), `shots` 32822 (tier 2) |
| Up In Smoke | 2 | `aicp` 940220 (not selected), `shots` 32316 (tier 2) |
| Museum-Worthy | 2 | `aicp` 941735 (not selected), `shots` 32969 (tier 2) |
| Javier In Frame | 2 | `aicp` 942340 (not selected), `shots` 32685 (tier 2) |
| Short Life Stories | 2 | `aicp` 944933 (not selected), `shots` 32185 (tier 2) |
| Play It Safe | 2 | `aicp` 951121 (not selected), `shots` 31955 (tier 2) |
| Goat Glider | 2 | `aicp` 953081 (not selected), `shots` 31140 (tier 2) |
| Album Cover | 2 | `aicp` 958965 (not selected), `shots` 33953 (tier 2) |
| Just Joking | 2 | `aicp` 960005 (not selected), `shots` 31780 (tier 2) |
| What the Football | 2 | `aicp` 968166 (not selected), `shots` 31214 (tier 2) |
| One More | 1/2 | `aicp` 981111 (tier 1), `shots` 32567 (tier 2) |
| New Driver | 1/2 | `aicp` 981509 (tier 1), `shots` 32568 (tier 2) |
| The Myth | 2 | `directorslibrary` 59256 (not selected), `shots` 27913 (tier 2) |
| Life is the Greatest Odyssey | 2 | `directorslibrary` 60225 (not selected), `shots` 31390 (tier 2) |
| Gatorade vs. Water | 2 | `directorslibrary` 67324 (not selected), `shots` 34562 (tier 2) |
| TDR x Nike | 2 | `directorslibrary` 80405 (not selected), `shots` 40925 (tier 2) |
| Brushes | 2 | `motiondesignawards` 158 (tier 2), `shots` 22438 (not selected) |
| How To Make Sushi | 2 | `motiondesignawards` 24 (tier 2), `shots` 19549 (not selected) |
| The Prodigy 'Timebomb Zone' by Paco Raterta | 3 | `promonews` 56496 (tier 3), `shots` 16888 (not selected) |
| Jeshi 'Generation' by Brock Neal Roberts | 3 | `promonews` 74151 (tier 3), `shots` 27423 (not selected) |
| Alaskan Tapes 'Holocene' by Andrew De Zen | 2 | `promonews` 93994 (tier 2), `shots` 38674 (not selected) |
| Cassius 'Dance On' by Mrzyk & Moriceau | 2 | `promonews` 95229 (tier 2), `shots` 39956 (not selected) |
| Makeshift Art Bar 'Discipline' by Colin Peppard | 1 | `promonews` 95269 (tier 1), `shots` 40084 (not selected) |
| Last Sun 'Care 4 U' by Callum Lloyd-James | 3 | `promonews` 95834 (tier 3), `shots` 40475 (not selected) |

## motiondesignawards

Catalog rows: 1,919. Selected: 324 (tier 1: 131, tier 2: 192, tier 3: 1; cross-site tier 0: 2).

| tier | cohort | video | census | audio |
|---:|---:|---:|---:|---:|
| 1 | 131 | 22 (17%) | 21 (16%) | 1 (1%) |
| 2 | 192 | 41 (21%) | 41 (21%) | 2 (1%) |
| 3 | 1 | 0 (0%) | 0 (0%) | 0 (0%) |

Small-cohort warning: tier 3 has 1 row(s); read those rates as anecdotes, not estimates.

`motiondesignawards/ids.json`: 324 ids. The harvest drivers accept that file via `--ids-file`.

**Bias:** Crowd vote, not jury: `scores.overall` is an open audience average and VOTD/VOTM are daily/monthly vote wins, so tiers 1-2 over-sample work with an active voting audience. Tiers 2-3 over-sample recent, high-traffic uploads because the top of the score distribution is thin. The rule cannot see craft: a well-voted but conventional piece ranks above an unvoted experimental one.

Tier-0 promotion keeps the original tier: {'2': 2}.

## aicp

Catalog rows: 2,715. Selected: 2,372 (tier 1: 528, tier 2: 1844; cross-site tier 0: 179).

| tier | cohort | video | census | audio |
|---:|---:|---:|---:|---:|
| 1 | 528 | 51 (10%) | 34 (6%) | 0 (0%) |
| 2 | 1844 | 185 (10%) | 64 (3%) | 0 (0%) |

`aicp/ids.json`: 2,372 ids. The harvest drivers accept that file via `--ids-file`.

**Bias:** Prize categories favour big-budget, US-agency work ('Advertising Excellence', 'Best of Region', 'National Campaign'), so tier 1 over-samples large production companies and award-show entries. Tier 2 (`year <= 2023`) deliberately over-samples older archive years, whose categories are sparser and whose downloadable renditions are less reliable; it is a coverage correction, not a claim that older work is better. 134 of 2,715 entries carry no category and cannot enter at all.

Tier-0 promotion keeps the original tier: {'1': 40, '2': 139}.

## promonews

Catalog rows: 17,805. Selected: 1,198 (tier 1: 63, tier 2: 202, tier 3: 933; cross-site tier 0: 6).

| tier | cohort | video | census | audio |
|---:|---:|---:|---:|---:|
| 1 | 63 | 14 (22%) | 6 (10%) | 0 (0%) |
| 2 | 202 | 54 (27%) | 11 (5%) | 3 (1%) |
| 3 | 933 | 148 (16%) | 57 (6%) | 12 (1%) |

`promonews/ids.json`: 1,198 ids. The harvest drivers accept that file via `--ids-file`.

**Bias:** UK-only music video coverage: every selected row is a British promo, so no non-UK or non-music-video work can enter. Tier 1-2 over-sample UKMVAs winners/nominees, and the CMS only tags 2018 and 2022-2026, so the tier is also a recent-years filter. Tier 3 over-samples 2018+ 'Pick of the Day' promos. Festival and long-form work is invisible.

Tier-0 promotion keeps the original tier: {'1': 1, '2': 2, '3': 3}.

## directorslibrary

Catalog rows: 5,412. Selected: 358 (tier 1: 69, tier 2: 289; cross-site tier 0: 0).

| tier | cohort | video | census | audio |
|---:|---:|---:|---:|---:|
| 1 | 69 | 16 (23%) | 5 (7%) | 0 (0%) |
| 2 | 289 | 70 (24%) | 41 (14%) | 0 (0%) |

`directorslibrary/ids.json`: 358 ids. The harvest drivers accept that file via `--ids-file`.

**Bias:** Festival films, not music videos: the site is a directors' directory of shorts, commercials and features, so tiers 1-2 over-sample narrative shorts that premiered at Cannes/Sundance/Venice/TIFF/Berlinale/SXSW. The 461 `terms.festival[]` and 69 `terms.award[]` tags are editor-applied and unevenly maintained across 5,412 items, so absence of a tag is not absence of quality.

## shots

Catalog rows: 40,908. Selected: 8,748 (tier 1: 9, tier 2: 8739; cross-site tier 0: 107).

| tier | cohort | video | census | audio |
|---:|---:|---:|---:|---:|
| 1 | 9 | 0 (0%) | 0 (0%) | 0 (0%) |
| 2 | 8739 | 560 (6%) | 323 (4%) | 116 (1%) |

Small-cohort warning: tier 1 has 9 row(s); read those rates as anecdotes, not estimates.

`shots/ids.json`: 8,748 ids. The harvest drivers accept that file via `--ids-file`.

**Bias:** Tier 1 is the 9 'Straight 8' entries, a sponsor contest rather than a quality ranking. Tier 2 is explicitly a documentation-completeness proxy (client + agency + artists[] + year), not a quality claim: it over-samples recent, fully credited commercial work from large agencies and excludes 27,701 clips with no year and 15,550 with no agency, regardless of how good they are. shots.net publishes no editorial or award signal at all.

Tier-0 promotion keeps the original tier: {'2': 107}.

## Combined file

`all-ids.json` lists 13,000 ids in site order, with a
`bySite` map. Site ids are site-local (a shots id and a promonews id can
collide numerically), so drive one site at a time from
`<site>/ids.json`, or read `bySite`.

## Method notes

- `already*Measured` is read from the on-disk indexes only: `index.json`
  (video lane), `census-index.json`, `audio-index.json`. A missing index
  file means the lane is unmeasured, not that the lane is unsupported.
- Ids are the catalog's own identifier (`projectId`, `id`, `nid`), with
  the catalog's type preserved, so `ids.json` drops straight into
  `--ids-file`.
- Cohort sizes are printed beside every already-measured count so a rate
  from a 9-row shots tier is not read like a rate from a 2,349-row AICP
  tier.
- Two runs over unchanged catalogs and indexes produce byte-identical
  outputs: no timestamps, no set iteration order, sorted tie-breaks.

