# Measured movie-promotion analysis

This is the **canonical, Git-tracked numerical evidence dataset** for official movie trailers. It is separate from [the 13-video popularity catalog](../../popular-movie-videos.v1.json), original footage and disposable analysis galleries.

| File | Contents |
| --- | --- |
| [`index.json`](index.json) | One summary entry per actually processed video, with three bounded windows, original and clip SHA-256s, source offsets, scene-difference cut sensitivity, audio attack counts, sampled display appearance and image-motion availability |
| `<film-slug>.json` | Detailed source-PTS cut candidates, image motion, sparse flow, sampled image color/hue, per-decoded-frame audio RMS/peak levels, audio-onset candidates and AV/edit rhythm evidence; includes `overgrown-blender-teaser.json` |

The dataset contains **14 measured promotional editions, 42 selected 20-second windows, and 840 seconds of machine-measured evidence**. The original 13-film popularity catalog still has seven Disney-player trailers (*Inside Out 2*, *Frozen 2*, *Moana 2*, *Avengers: Infinity War*, *Avengers: Endgame*, *Zootopia 2*, *Star Wars: The Force Awakens*) and six Apple iTunes Store movie previews (*Barbie*, *Oppenheimer*, *Spider-Man: No Way Home*, *Dune: Part Two*, *The Super Mario Bros. Movie*, *Deadpool & Wolverine*). The fourteenth source is **[OVERGROWN](overgrown-blender-teaser.json)**, Blender Studio's public PeerTube feature-film teaser, independently source-hashed and analyzed on its own publisher service. That film is **not** in the 13-video popularity catalog and must not be counted as a verified edition of a YouTube upload. Its source SHA-256 is `0c49e856a034e8de9695c96d86a048a34aa7f60286c0414069a1bcf35dab8f91`, its original duration 81.088 seconds, and its three sample offsets 0, 30 and 60 seconds. The source media and temporary analysis galleries were deleted after export. None of these 14 records has complete full-runtime human-certified coverage. New films should extend the same index and add their own per-video files; never overwrite an earlier source SHA or segment silently.

## Keep every derived report synchronized

Whenever a *new verified film measurement* changes `index.json` or
a per-film detail JSON, **all three** derived reports must be updated
in the same PR: `derived/comparison.v1.json`,
`derived/timed-events.v1.json` and `derived/image-motion-proxies.v1.json`.
Otherwise the source Git blob hashes and cross-file indexes are stale.

```bash
# After numeric-only source evidence is exported and audited:
python scripts/audit_movie_promo_evidence.py
python -m scripts.rebuild_movie_promo_derived

# Before committing, verify all three against the measured source files:
python -m scripts.rebuild_movie_promo_derived --verify
PYTHONPATH=. python -m unittest tests.test_movie_promo_derivation_pipeline -q
```

This command performs **no network requests, downloads or video decoding**.
It validates source-vs-detail identities, prepares all three JSON reports in
a temporary directory, and replaces them only after successful generation.
It does not edit the original measurement files. Its `--verify` mode
rejects missing, stale or unexpectedly added derived JSON. Keep this step
**after any temporary source footage has been deleted**, and stage only the
three derived JSON files alongside the original numeric evidence.

## How to inspect or extend it

```bash
jq '.videos[] | {id, sourceDurationSeconds, windows: [.windows[] | {window, sourceOffsetSeconds, cutCandidateCount, cutCandidateCountAtThreshold015}]}' research/analysis/movie-promotions/index.json

jq '{id, source: .originalSourceSha256, windows: [.windows[] | {window, cutCandidates: (.shotCutCandidates | length), audioFrames: (.audioLevels.rows | length)}]}' research/analysis/movie-promotions/inside-out-2.json
```

After running `study-reference` on a freshly acquired, temporary media set, [`scripts/export_movie_promo_evidence.py`](../../../scripts/export_movie_promo_evidence.py) can export an additional source-verified JSON set to a **new empty output directory**. Its inputs are the aggregate window plan, private MP4 files and temporary `study-reference` runs. Diff source hashes and coverage first; integrate new results into this tracked folder with tests before committing.

All entries retain `review-required` rights status, and the source MP4s, extracted audio, JPEG/HTML galleries, transcripts and CDN access tokens are excluded. The Apple preview records explicitly preserve `sourceEdition`, `sourceTrackId` and `catalogUploadIdentityMatch: not-verified`: they are **not claimed to be the exact YouTube upload versions** in the popularity catalog, and one Sony preview is for the *Extended Version* of the film. A scene-difference candidate is **not a confirmed editorial cut**; image motion is **not a proven camera movement**; brightness is **not a physical lighting rig**; audio-level changes are **not identified words or sound effects**. Middle/end clips were re-encoded and have an approximate original position via their declared offset. Any partial AAC frame trimmed at a scan boundary is excluded from RMS/peak evidence and counted explicitly.

## Expansion queue: new studio and movie types

[study-queue.v1.json](study-queue.v1.json) now holds **26 additional official
YouTube trailer uploads** across Warner Bros., Sony, Netflix, Universal/DreamWorks,
Paramount, Lionsgate, Marvel, 20th Century, A24, Toho, Aniplex, CMC Pictures,
Cartoon Saloon/Apple TV and others. See [the international animation and genre
expansion study](../../../docs/movie-promotion-international-expansion-2026-11-11.md).
They are **not yet analyzed footage** and do **not** appear in `index.json`
or the derived measured comparison. Each entry preserves a specific YouTube
upload ID, publisher, publication date, an attributed view-count observation,
a candidate research question, and rights/measurement status.

The cohort deliberately spans action geography (*John Wick: Chapter 4*,
*Mission: Impossible – Fallout*), stylized animation (*Spider-Verse*,
*The Wild Robot*, *Puss in Boots*), epic environmental scale (*Avatar*,
*Jurassic World*), stylized genre changes (*Everything Everywhere All at
Once*), musical storytelling (*Wicked*) and blockbuster/game worlds
(*A Minecraft Movie*, *Guardians of the Galaxy Vol. 3*). These are
**investigation topics**, not claims about unviewed frames.

```bash
python scripts/audit_movie_promo_study_queue.py
PYTHONPATH=. python -m unittest tests.test_movie_promo_study_queue -v
jq -r '.entries[] | [.proposedAcquisitionPriority, .filmStudio, .title, .youtubeId] | @tsv' research/analysis/movie-promotions/study-queue.v1.json
```

When authorized access to a specific public publisher video is possible,
download it temporarily, capture an original SHA-256 and edition identity,
run a source-PTS-verified study, export numeric-only evidence, verify the
index/detail cross-checks, and remove the downloaded media before publishing
a measurement PR. If access is unavailable, keep the entry metadata-only
rather than inventing cuts, color, character actions, audio, or timestamps.

## Sampled image-motion evidence and abstentions

[Image-plane motion summaries](derived/image-motion-proxies.v1.json)
derive **897 sampled image-motion pairs** from the same 39 video windows.
Of these, **522** have measurable 2D image-translation candidates,
**246** cross detected cut boundaries, **105** are unobservable because
of low texture, and **24** are ambiguous correlations. A separate sparse
optical-flow pass has **429 sampled pairs**: 64 single-translation
candidates, 12 multiple-translation candidates, 159 insufficient-consensus
pairs, 187 cut-boundary pairs and 7 ambiguous dominant groups.

The derived output also records an **exploratory, scale-normalized
displacement threshold** of 0.01 frame fraction per second. Of the 522
measurable translation pairs, **303** meet the threshold. This is only
the Euclidean magnitude of normalized *image-plane displacement over
sampled time*, **not** a physical camera movement, an actual camera
rotation, zoom, moving actor or independently verified motion type.
Window-level median values condition on measurable pairs; a null means
no measurable pairs, **not** a stationary shot.

```bash
python scripts/derive_movie_promo_motion_proxies.py --verify
PYTHONPATH=. python -m unittest tests.test_movie_promo_motion_proxies -v
jq '.videos[] | {id, windows: [.windows[] | {window, imageMotionPairStatuses, sparseFlowPairStatuses}]}' \
  research/analysis/movie-promotions/derived/image-motion-proxies.v1.json
```

The generator verifies per-window source hashes, measured PTS intervals
and source-index provenance, and it stores each detail file's Git blob
fingerprint. A source edit requires regeneration, with committed-output
equivalence enforced in lightweight CI.

## Timecoded candidate-edit and audio-attack timelines

The reproducible [timed-event dataset](derived/timed-events.v1.json) adds
**source-PTS-backed candidate timelines** for the 13 already measured
promotional editions. It is derived from the existing source-hashed detail
files, not from newly downloaded footage. The generator retains each
original clip SHA-256, detail Git blob SHA, rational video and audio
timebases, original clip-local PTS and the **approximate** source offset
for re-encoded middle/ending windows.

The 39 selected 20-second windows have **268 cut candidates** (scene
detector threshold 0.25) and **109 audio RMS-rise candidates**. Exactly
**25 of the 268** cut candidates have at least one audio attack candidate
within ±250 ms. The dataset includes the signed nearest attack offset for
each candidate cut; a null offset explicitly means no detected attack in
that clip. Each window also has four non-overlapping five-second cut-count
bins and an observed *interior* candidate-gap median (null if fewer than
two cuts). No timing measurements from the unmeasured 26-trailer queue
are included.

**Do not equate proximity with audio sync or editorial intent.** A cut
candidate may represent a flash or image-content change; a level rise
may be unrelated to music beats, dialogue or sound effects. The 250 ms
rule is a descriptive query, not a statistical significance test.
Unobserved film sections and censored window boundaries are excluded,
and the output does not identify camera motion, character actions,
lighting setups or creative causation.

```bash
python scripts/derive_movie_promo_timed_events.py --verify
PYTHONPATH=. python -m unittest tests.test_movie_promo_timed_events -v
jq '.videos[] | {id, windows: [.windows[] | {window, cutCandidateCountsByFiveSecondBin, cutCandidatesWithin250MsOfAudioAttack}]}' \
  research/analysis/movie-promotions/derived/timed-events.v1.json
```

Regenerate using `python scripts/derive_movie_promo_timed_events.py` only
when the upstream original index/detail files change. `--verify` and the
focused regression tests fail on a stale or inconsistent committed report,
without installing FFmpeg or fetching copyrighted media.

## Blender Studio *OVERGROWN* teaser measurements

The publisher's [official PeerTube player](https://video.blender.org/videos/watch/7ad3cbee-fe5f-41c2-93ea-b108986939f4) provided a public, 81.088-second, 1146×480 film teaser. An isolated one-time hosted research run downloaded and SHA-256-hashed that media, ran `study-reference` on three non-overlapping 20-second windows, committed only numerical source-PTS evidence, and deleted temporary video, audio, and frames. At scene-change threshold 0.25 it measured **2 / 7 / 2 cut candidates** in opening/middle/ending samples, versus **2 / 8 / 3** at threshold 0.15. These are automated scene-change candidates, not verified editing decisions. The three windows contain 36 sampled appearance frames, 69 image-motion pair comparisons, and 2,811 decoded-audio level frame rows.

This expands edition diversity (Blender Studio public PeerTube vs Disney player vs Apple retail preview); it **does not** establish a causal style or studio-effect comparison. The project may not treat Blender's feature-film teaser as equivalent to a Warner, Sony, or DreamWorks campaign. Reproduce the original bounded research procedure using [`scripts/research_movie_promo_overgrown.py`](../../../scripts/research_movie_promo_overgrown.py) on a legitimate public source, but do not rerun it against committed data or overwrite source editions. Keep derivative comparison manifests synchronized after adding new evidence.

## Reproducible comparisons

The [derived comparison](derived/comparison.v1.json) is computed solely from the
source-hashed numeric index. It reports **per-sampled-minute** edit-candidate
rates at thresholds 0.25 and 0.15, exact sampled-window coverage, phase-level
counts, audio-level attack candidates, and frame-sample-weighted display-luma
and saturation proxies. These descriptive values **do not estimate the unseen
portions of any trailer** and do not measure human-confirmed cuts, real camera
moves, lighting rigs, or marketing performance.

It also preserves the distinction between Disney public-player files and
Apple iTunes Store retail preview editions. **Do not** interpret different
edition cuts as studio-specific cinematography or as identical YouTube uploads.

```bash
python scripts/summarize_movie_promo_evidence.py --verify
# Regenerate only after changing the canonical index:
python scripts/summarize_movie_promo_evidence.py
PYTHONPATH=. python -m unittest tests.test_movie_promo_comparison -v
```

The generated report contains the source index's *Git blob SHA-1*. Verification
fails if the committed comparison becomes stale or source values change. The
original per-window measurements remain authoritative.

See the [study and interpretation notes](../../../docs/movie-promotion-video-research.md) for the comparison and its limitations.
