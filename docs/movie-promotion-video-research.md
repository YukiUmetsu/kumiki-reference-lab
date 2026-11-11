# Movie-promotion reference study: Disney, Marvel, and other major studios

**Research checked:** November 11, 2026
**Machine-readable cohort:** [`research/popular-movie-videos.v1.json`](../research/popular-movie-videos.v1.json)  
**Evidence level:** 13 official YouTube uploads with attributable popularity observations; **13 corresponding film-promotion sources actually processed** (seven Disney-hosted trailers and six Apple iTunes Store movie previews) in 39 non-overlapping 20-second windows (780 seconds total), plus separate limited manual visual observations of the original five. Apple retail previews are **not verified identical** to the catalog's YouTube uploads. Extracted numerical evidence is committed; video, audio and image files are not.

**Measured data:** the canonical [`research/analysis/movie-promotions/`](../research/analysis/movie-promotions/) folder holds [`index.json`](../research/analysis/movie-promotions/index.json) and one granular JSON file per analyzed trailer. It retains per-window source PTS, cut-candidate positions, two-dimensional motion results, sampled image appearance, decoded audio RMS/peak trajectories, onset candidates, edit rhythms and AV-cut comparisons. No source videos, frame images, signed CDN URLs or dialogue transcripts are committed.

## Scope and what the numbers do not mean

The cohort includes 13 distinct official uploads from Disney Animation, Pixar, Marvel, Lucasfilm/Star Wars, Warner Bros., Universal/Illumination, and Sony. It is an *editorial, nonrandom comparison set* spanning animated family films, action franchises, a historical thriller, and contrasting stylized worlds. The original 40-item explainer/cinematic selection remains separately versioned.

Playback counts are YouTube video-specific cumulative snapshots or attributed third-party figures, not all-platform launch numbers. They are **not** unique people, average watch time, completed views, organic impressions, box-office conversion, or causal evidence that a film technique led to high engagement. Release dates and campaign distribution differ substantially. The current counts may not match the cited listings when revisited.

The 13 records are searchable alongside existing records:

```bash
PYTHONPATH=src python -m kumiki_reference_lab video-references validate
PYTHONPATH=src python -m kumiki_reference_lab video-references search "franchise"
PYTHONPATH=src python -m kumiki_reference_lab video-references search "character ensemble"
PYTHONPATH=src python -m kumiki_reference_lab video-references list --root research/popular-movie-videos.v1.json --min-views 30000000
```

## Visual observations: five browser-sampled Disney-hosted players

This section is a **small, selective manual visual review** of publicly displayed frames, separate from the subsequent machine-generated numerical data below. Browser-player time readouts can be off by a fraction of a second after seeking. The later temporary-file studies did decode source video/audio but have **not** validated the human scene descriptions here or established actual physical camera moves, lighting rigs, character identities or full-runtime behavior.

### Disney/Pixar: Inside Out 2 | Official Trailer

Original official player: https://video.disney.com/watch/inside-out-2-official-trailer-61315e19985f9ebd6b4f2a72  
Official YouTube upload: https://www.youtube.com/watch?v=LEjhY15eCx0  
Player duration observed: approximately 2:24.

| Approximate player time | Visible in the sampled frame | Potential teaching value (interpretation, not a metric) |
| --- | --- | --- |
| 0:02 | Joy alone near the control console; multicolored lights in a violet interior | Saturated location coding gives a compact spatial identity without text |
| 0:11 | Riley and parents gathered around a birthday cake in a domestic room | Strong setting contrast: an ordinary relatable human scene after an abstract inner-world image |
| 0:51 | A long-haired, slouched character sprawled across a red couch against a multicolored control-room background | Shape and posture can communicate a personality with little complex movement |
| 1:25 | Riley carries a sports bag through a doorway; another person occupies the foreground | Foreground obstruction and doorway staging establish a close personal interaction |
| ~1:54 | Several emotion characters sit together behind a desk against a purple-curtained background | Ensemble staging supports a quick read of contrasting expressions and colors |
| ~2:13 | Small character figures appear across a broad purple structure with a large construction machine in the foreground | Scale contrast and environmental props support a new story beat |

These samples suggest a useful **hypothesis** for Kumiki: expressive pose and consistent character palettes may carry more information per second than constant camera movement. Testing requires full-speed review and shot/character labels, not just snapshots.

### Marvel Studios: Avengers: Infinity War Official Trailer

Original official player: https://video.disney.com/watch/marvel-studios-avengers-infinity-war-official-trailer-55f1f6dd0285c80766ffcd1e  
Official YouTube upload: https://www.youtube.com/watch?v=6ZfuNTqbHE8  
Player duration observed: approximately 2:24.

| Approximate player time | Visible in the sampled frame | Potential teaching value (interpretation, not a metric) |
| --- | --- | --- |
| Opening | Glowing planetary horizon with strong warm rim light against deep space | Establishes enormous physical scale before showing the heroes |
| 0:25 | Bruce Banner beside a large red armored object, framed in a green outdoor setting | Human-scale character shot and recognizable props/setting contrast with cosmic imagery |
| 1:02 | Tony Stark in a debris-filled city street with distant orange circular effects behind him | Layered foreground/midground/background props build stakes and geography |
| 1:45 | Iron Man's reflective red armor in a dim, warm orange scene | Readable hero silhouette and controlled highlights despite low overall brightness |
| 2:12 | Bronze *Avengers: Infinity War* title appears against a nearly black background | Title/logo as a strong late visual endpoint |

This small sample indicates recurring **scale and light contrasts**, but it cannot establish their frequency, duration, editing order, camera trajectories, actual lighting rigs or audio synchronization. Nor does it establish whether the same pattern holds across trailers or drives popularity.

### Disney Animation: Frozen 2 Official Trailer

Original official player: https://video.disney.com/watch/frozen-2-official-trailer-58b0e63cfe2f4ebd6b4f2a72  
Official YouTube upload: https://www.youtube.com/watch?v=Zi4LMpSDccc  
Player duration observed: approximately 1:53.

| Approximate player time | Visible in the sampled frame | Potential teaching value (interpretation, not a metric) |
| --- | --- | --- |
| 0:54 | Elsa in a close or medium framing, dimly lit against a dark environment | An identifiable face and silhouette can carry a scene despite low-key illumination |
| 1:07 | A small figure in a boat at the base of a massive rock-walled cavern | Extreme environment-to-character scale creates wonder and tension |
| 1:39 | Elsa in profile, one hand raised toward a dark rock surface in blue light | Profile, gesture and colored edge light direct attention to a specific interaction |

**Hypothesis:** A sparse, restricted palette and deliberate subject-to-environment scale changes can convey mystery without a constantly busy frame. These samples do not establish a trailer-wide palette distribution or shot lengths.

### Disney Animation: Moana 2 Official Trailer

Original official player: https://video.disney.com/watch/moana-2-official-trailer-61f4bc35ea7c5dea2c651fcc  
Official YouTube upload: https://www.youtube.com/watch?v=hDZ7y8RP5HE  
Player duration observed: approximately 2:10.

| Approximate player time | Visible in the sampled frame | Potential teaching value (interpretation, not a metric) |
| --- | --- | --- |
| 0:34 | Two figures' bare feet of different sizes stepping in shallow shore water, warm natural light | Framing a relationship through scale, movement and proximity without a dialogue-heavy facial close-up |
| 1:08 | Dark symmetrical, carved interior with a central opening and blue-green highlights | Architectural symmetry and controlled edge color create a clear destination and focal point |
| 1:46 | A crowded lineup of small expressive figures with decorative colored details amid textured wooden/brown props | Repeated character silhouettes and variation in color support a fast ensemble read |

**Hypothesis:** This trailer offers a useful *relationship-to-environment-to-ensemble* composition vocabulary for original animation. A full shot-sequence review would be needed to verify whether those compositions are linked in that order or recur.

### Marvel Studios: Avengers: Endgame Official Trailer

Original official player: https://video.disney.com/watch/marvel-studios-avengers-endgame-official-trailer-5840cf6e5b0ccebd6b4f2a72  
Official YouTube upload: https://www.youtube.com/watch?v=TcMBFSGVi1c  
Player duration observed: approximately 2:26.

| Approximate player time | Visible in the sampled frame | Potential teaching value (interpretation, not a metric) |
| --- | --- | --- |
| Opening | Desaturated, barren landscape with scattered wreckage | Low saturation and environmental emptiness provide a tonal contrast to polished heroic imagery |
| 0:30 | A man viewed from behind in front of a monochrome military-era poster | An over-the-shoulder/back view and nostalgic graphic can suggest recollection without showing an expressive face |
| 1:15 | A small, weathered house surrounded by foliage, in comparatively muted light | An ordinary human-scale location can interrupt franchise-scale spectacle and provide visual quiet |

**Hypothesis:** Compared with the selected *Infinity War* frames, the sampled *Endgame* frames emphasize memory, stillness and aftermath. This is a *qualitative observation of selected moments*, not a validated difference in the two trailers' average pacing or brightness.

## Source-hashed machine measurements

Seven public Disney-player H.264/AAC sources (400–480p, ~113–146 seconds) and six publicly offered Apple iTunes Store movie previews (640-pixel video width, ~92–184 seconds) were downloaded solely for bounded analysis through `study-reference`; the temporary media was deleted after numerical export. Three 20-second windows sampled the opening, approximate middle and ending; middle/ending excerpts were re-encoded temporarily and retain explicit offsets and their own hashes. The Apple records include retail track IDs, source edition labels and `catalogUploadIdentityMatch: not-verified`. In particular, the Sony Store preview is associated with the film's **Extended Version**. No Disney or Apple preview encode is asserted byte-identical to any linked YouTube upload.

| Trailer | Sampled coverage | Cut candidates at default threshold 0.25 | Candidates at sensitivity threshold 0.15 | Audio-level attack candidates | Average sampled display-luma proxy |
| --- | ---: | ---: | ---: | ---: | ---: |
| *Inside Out 2* | 60 / 145 sec | 39 | 48 | 17 | 0.304 |
| *Frozen 2* | 60 / 113 sec | 8 | 16 | 1 | 0.085 |
| *Moana 2* | 60 / 130 sec | 25 | 33 | 6 | 0.282 |
| *Avengers: Infinity War* | 60 / 144 sec | 13 | 19 | 0 | 0.120 |
| *Avengers: Endgame* | 60 / 146 sec | 11 | 14 | 3 | 0.169 |
| *Zootopia 2* | 60 / 141 sec | 22 | 26 | 27 | 0.334 |
| *Star Wars: The Force Awakens* | 60 / 138 sec | 10 | 23 | 5 | 0.176 |
| *Barbie* (Apple preview) | 60 / 161 sec | 30 | 31 | 25 | 0.311 |
| *Oppenheimer* (Apple preview) | 60 / 184 sec | 27 | 40 | 5 | 0.166 |
| *Spider-Man: No Way Home* (Apple Extended Version preview) | 60 / 102 sec | 34 | 45 | 5 | 0.219 |
| *Dune: Part Two* (Apple preview) | 60 / 183 sec | 25 | 30 | 3 | 0.237 |
| *The Super Mario Bros. Movie* (Apple preview) | 60 / 92 sec | 18 | 36 | 0 | 0.287 |
| *Deadpool & Wolverine* (Apple preview) | 60 / 144 sec | 6 | 16 | 12 | 0.193 |

**Interpretation:** At both sensitivity settings, the *Inside Out 2* sample produced more possible hard edits than *Frozen 2*, while *Moana 2* fell between them. *Zootopia 2* showed more cut candidates and onset candidates than *Force Awakens* at the default threshold, though the threshold-sensitive increase for *Force Awakens* demonstrates detector uncertainty. Among Apple preview editions, *Barbie* had a higher sampled luma proxy than *Oppenheimer* (0.311 vs 0.166), and the sampled *Barbie* and *Dune: Part Two* previews each yielded roughly 25–30 default-threshold cut candidates despite contrasting creative directions. These are **screen-image comparisons of selected windows and specific source editions**, not proven director intent or audience-performance explanations.

**Do not treat the table as film-wide cuts/minute.** The FFmpeg scene-difference detector can undercount subtle/dark edits or overcount flashes/rapid action. Its marked events are not human-confirmed cuts. Counts reflect only 60 selected seconds per promotional source and vary with threshold. Audio attacks are strict 12 dB RMS-rise candidates, not counts of dialogue, music beats or SFX. Display luma is measured on encoded sampled frames, including letterboxing and color grading; it cannot infer real lighting intensity or rig changes. Source encodes and trailer cuts differ across Disney and Apple, so even their candidate counts are not rigorously controlled studio comparisons. No automatic speaker/character traits or actions were certified.

### What remains in Git

- The compact **[index.json](../research/analysis/movie-promotions/index.json)** holds named windows, source SHA-256 fingerprints, clip offsets, duration/coverage, candidate counts at both thresholds, sampled appearance summaries, image-translation availability and audio attacks.
- **Granular evidence JSON files** under the same folder, one per trailer, retain timecoded cut positions; sampled color/hue measurements; motion and sparse optical-flow outputs; per-decoded-audio-frame RMS/peak levels; onset candidates; candidate edit intervals; and synchronized AV evidence. Arrays use original *window* PTS. For re-encoded windows, add the declared source offset for an **approximate** position in the full original trailer.
- The exporter [`scripts/export_movie_promo_evidence.py`](../scripts/export_movie_promo_evidence.py) rebuilds the numeric files from temporary studies, requiring `--summary`, `--media-root`, `--runs-root`, and `--out` on a fresh empty destination. It refuses to silently overwrite reports and verifies video/audio SHA consistency.
- Copyrighted MP4s, encoded audio and extracted JPEG/HTML review galleries are **not** part of the repository. The original source URLs and hashes allow provenance checks, but hashes do not make footage reproducible once deleted.

## Reproducible comparisons from the measured windows

The [derived comparison JSON](../research/analysis/movie-promotions/derived/comparison.v1.json)
is generated from the immutable numerical index with
[`scripts/summarize_movie_promo_evidence.py`](../scripts/summarize_movie_promo_evidence.py).
It retains source identities and differences between **Disney public-player
uploads** and **Apple iTunes Store movie preview editions**. All rows below
represent **only three selected 20-second windows**, totaling 60 seconds per
film; they are not full-film edit rates or marketing outcomes.

| Source edition | Candidate edits at 0.25 (sampled 60 s) | Candidates at 0.15 | Opening → ending window candidates (0.25) |
| --- | ---: | ---: | ---: |
| *Inside Out 2* (Disney player) | 39 | 48 | 17 → 10 |
| *Frozen 2* (Disney player) | 8 | 16 | 5 → 1 |
| *Zootopia 2* (Disney player) | 22 | 26 | 9 → 3 |
| *Barbie* (Apple preview) | 30 | See JSON | 7 → 13 |
| *Spider-Man: No Way Home* (Apple preview) | 34 | See JSON | 10 → 12 |
| *Dune: Part Two* (Apple preview) | 25 | See JSON | 11 → 6 |
| *The Force Awakens* (Disney player) | 10 | 23 | 4 → 0 |

The unusually large detection-threshold change for *The Force Awakens*
illustrates that scene-difference thresholds affect comparisons. The selected
*Barbie* and *Spider-Man* Apple preview endings show more candidate events than
their beginnings, while several Disney-player samples show the opposite. This
is a **sampling observation**, not proof of a universal editing formula or
a difference in the studios' creativity. Source editions, source quality,
letterboxing, flashes, cuts and changing screen content can confound counts.

For future Kumiki research, the next statistically useful step is to acquire
and verify **more full-runtime official trailer editions**, then manually
review ambiguous cuts and timecode character-action/lighting hypotheses.
Do not generalize the current selected-window averages to a trailer's unseen
sections or infer viewer retention and conversion from them.

## Cross-studio comparison questions

| Pair | Controlled question for future source-verified analysis | Why this matters to Kumiki |
| --- | --- | --- |
| *Infinity War* vs. *Endgame* | Does a more retrospective/emotional trailer use longer quiet holds before late action/cut acceleration? | Different timing recipes for emotional setup and payoff |
| *Inside Out 2* vs. *Zootopia 2* | How often do readable two- or multi-character scenes rely on pose/color versus moving camera? | Character-blocking and expressive-pose templates |
| *Barbie* vs. *Dune: Part Two* | How do both maintain brand identity with opposing saturated vs. restrained palettes? | Color/lighting look systems with repeatable contrast rules |
| *Oppenheimer* vs. *Deadpool & Wolverine* | How do audio attacks, joke pauses and dialogue windows relate to cut candidates? | Distinct suspense and comedy pacing presets |
| *Moana 2* vs. *The Super Mario Bros. Movie* | How is character attention preserved through fast-moving environments and effects? | Subject-aware composition, motion budgets and scale changes |
| *Star Wars: The Force Awakens* vs. *Spider-Man: No Way Home* | When are recognizable characters, antagonists or franchise props revealed relative to the title? | Evidence-based reveal-timing recipes |

All listed comparison films now have **partial, machine-generated cut/appearance/audio measurements**, but no paired human-reviewed character, camera or scene-label analysis. Apple previews may differ from the linked YouTube videos, so these are exploratory cross-edition comparisons, not controlled matched-trailer experiments. No comparison here establishes character traits, camera frequency or lighting frequency. The tags in the catalog are hypothesis/search labels only.

## Rigorous follow-up with authorized local media

1. **Record provenance and authorization for each additional source.** The 13 processed promotional editions have hashed numeric records but remain `review-required` for any new use. For new videos, keep source files private and external to git. Log exact upload/retail-preview ID, trailer edition, release date, SHA-256, codec, FPS/timebase and duration. Never assume a teaser, retail preview and full trailer are interchangeable.
2. **Run actual `study-reference`** on a bounded representative 20-second window per trailer, and use `analyze --start-seconds` for additional windows. The `study-reference` command only accepts `--max-seconds` up to 20; do not present its default 10 seconds as an analysis of a two-minute movie trailer.
3. **Collect shot, motion, appearance and audio reports** using the repository's existing `review-timeline`, `edit-rhythm`, `shot-evidence`, `audio-onsets`, `visual-cadence` and `visual-style-review` contracts. Report cut candidates separately from confirmed edits, 2D image motion separately from camera motion, and display luminance separately from actual lights.
4. **Annotate characters and interactions.** Use the optional `character-study-local` / `character-scene` pipeline for reviewer-confirmed appearances, actions and dialogue. Its model hypotheses cannot certify age, gender, ethnicity, speaker identity, a particular character's continuity across cuts, or lip synchronization.
5. **Review at full speed and blind-label a comparison set.** For each relevant shot, record attention target, camera scale, dominant composition, story function, practical-vs-CGI uncertainty, transition type, and where dialogue/music/SFX affect the edit. Resolve disagreements by human review.
6. **Compare matched windows and keep controls.** Compare trailers within approximately similar runtime/release cohorts, plus multiple videos per studio. Treat view totals as descriptive context; account for audience and promotion budget differences before making any efficacy claim.
7. **Translate principles, not copyrighted imagery.** Create original camera, lighting, pacing and character-interaction templates for `kumiki-ui`; validate with `review-film-map` and `film-feedback` against original renders.

### Suggested first measurements

Start with **three full 20-second windows per video** (opening, middle, final section), then fill all gaps before publishing whole-runtime rates. For each window capture candidate cuts/minute, interior cut-gap distribution, audio-onset-to-cut offset, motion-vector confidence, look/palette shifts, rough shot scale, camera-motion *hypotheses*, verified character visibility/gestures, and manual story-intent labels. Do not compare partial windows as if they cover entire trailers. A 13-video cohort gives a useful first taxonomy; it is not yet large enough to make causal marketing claims.

## Copyright and review status

The catalog contains source links and independently written questions. The technical evidence contains numeric derivatives, not media files, extracted copyrighted frames, music, transcripts, meshes, character designs or thumbnails, and does not assert redistribution or training rights. All 13 catalog records deliberately retain the strict `editorial-candidate-not-frame-reviewed` status: all 13 films now have separately verified *machine measurement provenance* for a public promotional edition, but none has full-runtime human-certified visual/semantic interpretation. Apple retail previews should not be conflated with the exact catalog YouTube uploads.
