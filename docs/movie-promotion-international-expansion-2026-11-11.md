# Movie-promotion research expansion: international animation and contrasting genres

**Source research:** November 11, 2026  
**Data:** [26-source study queue](../research/analysis/movie-promotions/study-queue.v1.json)  
**Already measured:** [13-source, 39-window index](../research/analysis/movie-promotions/index.json)  
**Status of this wave:** Source/link/popularity research only. **No movie media, original PTS or new video measurements were acquired or produced in this wave.**

## Why this second cohort matters

The measured 13-film corpus is dominated by Disney public-player trailers and Apple iTunes retail previews, which are **not necessarily the exact YouTube edits** recorded by the popularity catalog. The queue now adds 13 more source-identified official promotions with publisher attribution. We intentionally broaden **animation technique**, **national production/distribution** and **genre**, rather than simply adding sequels of similar franchise trailers.

| Newly queued film and uploader | Reported lifetime views (source snapshot) | Why study it |
| --- | ---: | --- |
| [How to Train Your Dragon (2025), Universal](https://www.youtube.com/watch?v=22w7z_lT6YM) | 46,548,775 | Candidate comparison of live-action creature staging against stylized animation |
| [Kung Fu Panda 4, Universal](https://www.youtube.com/watch?v=_inKs4eeHiI) | 39,458,514 | Candidate tests for comic reactions, action pacing and ensemble legibility |
| [Sinners, Warner Bros.](https://www.youtube.com/watch?v=7joulECTx_U) | 33,004,799 | Candidate horror pacing, sound emphasis and low-key display contrast |
| [KPop Demon Hunters, Netflix](https://www.youtube.com/watch?v=AzCAwdp1uIQ) | 27,354,543 | Candidate relationship between animation, choreography, song and cuts |
| [F1 The Movie, Warner Bros.](https://www.youtube.com/watch?v=8yh9BPUBbbQ) | 24,194,371 | Candidate image-plane vehicle motion and sound/edit timing |
| [Transformers One, Paramount](https://www.youtube.com/watch?v=5a09yJU-mCI) | 19,371,011 | Candidate transforming silhouettes, articulated parts and readable action |
| [Godzilla Minus One, TOHO](https://www.youtube.com/watch?v=VvSrHIX5a-0) | 18,896,968 | Candidate creature-versus-human scale reveals and destructive visual effects |
| [TMNT: Mutant Mayhem, Paramount](https://www.youtube.com/watch?v=IHvzw4Ibuho) | 18,206,728 | Candidate sketch-like texture and multi-character staging |
| [The Bad Guys 2, Universal](https://www.youtube.com/watch?v=TY1lWh20VSw) | 18,161,480 | Candidate heist animation and character-group action continuity |
| [Godzilla Minus Zero, TOHO](https://www.youtube.com/watch?v=Pu0pH5BuCPM) | 8,236,784 | A recent 2026 release to compare against the earlier TOHO campaign |
| [Wolfwalkers, Apple TV](https://www.youtube.com/watch?v=d_Z_tybgPgg) | 6,068,151 | Candidate hand-drawn, shape-driven 2D animation and forest composition |
| [Ne Zha 2, CMC Pictures](https://www.youtube.com/watch?v=nsXQijb0F4I) | 4,198,770 | Chinese CG-animation and mythological action staging |
| [Demon Slayer: Infinity Castle, Aniplex USA](https://www.youtube.com/watch?v=9kb7vK11_Rw) | 607,708 | Anime-specific candidate tests for 2D actors in three-dimensional environments |

**View-count provenance:** The corresponding `viewEvidence.sourceUrl` in the queue identifies the source for each film-specific figure. Most counts came from indexed official YouTube uploads observed November 11; the 2026 TOHO figure comes from a dated **ChartsList** per-video snapshot. They are *not synchronized lifetime view measurements* in the same analytics system, not unique viewers, and do not measure retention or performance of any particular shot. A relatively small YouTube upload (such as Aniplex USA's trailer) may still represent an important visual study; source selection is not a ranking of the films' total popularity.

## Five focused research experiments

| Research experiment | Films to compare when exact source editions are available | Automatic evidence first | Requires human or separately validated model review |
| --- | --- | --- | --- |
| **Stylized character clarity** | *KPop Demon Hunters*, *TMNT: Mutant Mayhem*, *The Bad Guys 2*, *Kung Fu Panda 4* | Candidate shot timing, image-plane flow support, color changes | Which characters act or speak; silhouette/pose readability; attention target |
| **2D/CG compositing vocabularies** | *Wolfwalkers*, *Demon Slayer*, *Ne Zha 2*, existing *Spider-Verse* queue | Color/contrast and 2D motion measurements | Hand-drawn, paint/line-art, 2.5D and 3D classifications from timecoded frames |
| **Creature versus environment scale** | *Godzilla Minus One*, *Godzilla Minus Zero*, existing *Jurassic World Rebirth*, *How to Train Your Dragon* | Shot-change sensitivity and image-plane motion/appearance | Creature visibility, focal hierarchy, human/creature screen occupancy and scale reveals |
| **Musically motivated promotion** | *Sinners*, *KPop Demon Hunters*, *F1 The Movie*, existing *Wicked* | Audio level attacks, cut-to-audio distances and candidate gap distribution | Actual music beats, dialogue, effects, dramatic intent and sync confirmation |
| **Mechanical transformation and action** | *Transformers One*, existing *Top Gun: Maverick*, existing *John Wick 4* | Optical-flow and edit-region timing evidence | Whether motion comes from body rig, vehicle, moving camera or edit; screen geography |

These are **planned experimental contrasts, not observations of viewed or decoded footage**. They deliberately separate descriptive pixel/audio measurements from uncertain cinematographic and semantic labels. Do not generalize results from three selected 20-second windows to a whole film.

## What to measure next

For each newly acquired authorized edition, preserve the original SHA-256, platform URL, codec, dimensions, rational PTS/timebase, scan-window offsets, media rights status and source-edition identity. Run the existing `study-reference` and numeric exporter on three bounded windows. Before making claims about recurring pacing or full-film frequency, fill remaining gaps and manually adjudicate edits, shot boundaries and source-to-window mappings.

High-value animation techniques for possible future **kumiki-ui** evaluation are: editable hand-drawn stroke/shape treatments, multi-character blocking and gaze/turn handoffs, coordinated music/dance phrase timing, readable mechanical part-to-part transformations, environmental scale staging, and stylized destruction/particle reveal effects. **These are component hypotheses only**: they are not yet proven gaps in the live Kumiki UI registry or proven techniques used by specific source trailers.

## Verification and data ownership

The [queue auditor](../scripts/audit_movie_promo_study_queue.py) checks exact YouTube IDs, duplicate uploads against the measured popularity catalog, publisher links, attributable view evidence, rights status and explicit **not-performed** analysis status. It has regression tests. Do not move an entry into the measured `index.json` until the underlying actual video has been downloaded lawfully, processed with exact hashes/PTS and exported as per-window numeric evidence. No reference footage, frames, audio, transcripts, signed URLs or imagined metrics belong in Git.
