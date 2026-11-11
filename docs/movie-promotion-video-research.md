# Movie-promotion reference study: Disney, Marvel, and other major studios

**Research checked:** November 10, 2026  
**Machine-readable cohort:** [`research/popular-movie-videos.v1.json`](../research/popular-movie-videos.v1.json)  
**Evidence level:** 13 official YouTube uploads with attributable popularity observations; 5 trailers partially viewed using Disney's public video player; **0 copyrighted trailer files locally analyzed**.

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

This is a **small, selective visual review** of publicly displayed frames, *not* output from `study-reference`, `visual-events`, `character-scene`, optical flow, cut detection, audio analysis or a source-hashed annotation contract. Browser-player time readouts can be off by a fraction of a second after seeking. We did not download, fingerprint, redistribute or frame-decode the copyrighted videos. There are no verified per-minute frequencies, cut counts, physical camera moves, lighting-rig estimates, or claims of full-runtime review.

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

## Cross-studio comparison questions

| Pair | Controlled question for future source-verified analysis | Why this matters to Kumiki |
| --- | --- | --- |
| *Infinity War* vs. *Endgame* | Does a more retrospective/emotional trailer use longer quiet holds before late action/cut acceleration? | Different timing recipes for emotional setup and payoff |
| *Inside Out 2* vs. *Zootopia 2* | How often do readable two- or multi-character scenes rely on pose/color versus moving camera? | Character-blocking and expressive-pose templates |
| *Barbie* vs. *Dune: Part Two* | How do both maintain brand identity with opposing saturated vs. restrained palettes? | Color/lighting look systems with repeatable contrast rules |
| *Oppenheimer* vs. *Deadpool & Wolverine* | How do audio attacks, joke pauses and dialogue windows relate to cut candidates? | Distinct suspense and comedy pacing presets |
| *Moana 2* vs. *The Super Mario Bros. Movie* | How is character attention preserved through fast-moving environments and effects? | Subject-aware composition, motion budgets and scale changes |
| *Star Wars: The Force Awakens* vs. *Spider-Man: No Way Home* | When are recognizable characters, antagonists or franchise props revealed relative to the title? | Evidence-based reveal-timing recipes |

None of these comparisons has measured paired edit rates, character traits, camera frequency or lighting frequency. The tags in the dataset are hypothesis/search labels only.

## Rigorous follow-up with authorized local media

1. **Acquire media legitimately and record provenance.** Use an authorized local promotional video, not merely a browser playback URL. Keep source files private and external to git. Log exact upload ID, trailer version, release date, SHA-256, codec, FPS/timebase and duration. Never assume a teaser and full trailer are interchangeable.
2. **Run actual `study-reference`** on a bounded representative 20-second window per trailer, and use `analyze --start-seconds` for additional windows. The `study-reference` command only accepts `--max-seconds` up to 20; do not present its default 10 seconds as an analysis of a two-minute movie trailer.
3. **Collect shot, motion, appearance and audio reports** using the repository's existing `review-timeline`, `edit-rhythm`, `shot-evidence`, `audio-onsets`, `visual-cadence` and `visual-style-review` contracts. Report cut candidates separately from confirmed edits, 2D image motion separately from camera motion, and display luminance separately from actual lights.
4. **Annotate characters and interactions.** Use the optional `character-study-local` / `character-scene` pipeline for reviewer-confirmed appearances, actions and dialogue. Its model hypotheses cannot certify age, gender, ethnicity, speaker identity, a particular character's continuity across cuts, or lip synchronization.
5. **Review at full speed and blind-label a comparison set.** For each relevant shot, record attention target, camera scale, dominant composition, story function, practical-vs-CGI uncertainty, transition type, and where dialogue/music/SFX affect the edit. Resolve disagreements by human review.
6. **Compare matched windows and keep controls.** Compare trailers within approximately similar runtime/release cohorts, plus multiple videos per studio. Treat view totals as descriptive context; account for audience and promotion budget differences before making any efficacy claim.
7. **Translate principles, not copyrighted imagery.** Create original camera, lighting, pacing and character-interaction templates for `kumiki-ui`; validate with `review-film-map` and `film-feedback` against original renders.

### Suggested first measurements

Start with **three full 20-second windows per video** (opening, middle, final section), then fill all gaps before publishing whole-runtime rates. For each window capture candidate cuts/minute, interior cut-gap distribution, audio-onset-to-cut offset, motion-vector confidence, look/palette shifts, rough shot scale, camera-motion *hypotheses*, verified character visibility/gestures, and manual story-intent labels. Do not compare partial windows as if they cover entire trailers. A 13-video cohort gives a useful first taxonomy; it is not yet large enough to make causal marketing claims.

## Copyright and review status

The catalog contains source links and independently written questions. It does not contain media files, extracted copyrighted frames, music, transcripts, meshes, character designs or thumbnails, and does not assert rights to download, redistribute or train on any source. All 13 records deliberately use the strict `editorial-candidate-not-frame-reviewed` status required by the existing schema; the separate browser observations do **not** promote those records to verified technical analysis.
