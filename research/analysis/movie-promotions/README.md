# Measured movie-promotion analysis

This is the **canonical, Git-tracked numerical evidence dataset** for official movie trailers. It is separate from [the 13-video popularity catalog](../../popular-movie-videos.v1.json), original footage and disposable analysis galleries.

| File | Contents |
| --- | --- |
| [`index.json`](index.json) | One summary entry per actually processed video, with three bounded windows, original and clip SHA-256s, source offsets, scene-difference cut sensitivity, audio attack counts, sampled display appearance and image-motion availability |
| `<film-slug>.json` | Detailed source-PTS cut candidates, image motion, sparse flow, sampled image color/hue, per-decoded-frame audio RMS/peak levels, audio-onset candidates and AV/edit rhythm evidence |

The current cohort covers **all 13 films in the popularity catalog**: seven Disney-player trailers (*Inside Out 2*, *Frozen 2*, *Moana 2*, *Avengers: Infinity War*, *Avengers: Endgame*, *Zootopia 2*, *Star Wars: The Force Awakens*) and six Apple iTunes Store movie previews (*Barbie*, *Oppenheimer*, *Spider-Man: No Way Home*, *Dune: Part Two*, *The Super Mario Bros. Movie*, *Deadpool & Wolverine*). Each has three selected 20-second windows, preserving **780 seconds of machine-measured evidence**, not verified full trailers. Additional films should extend the same index and add their own per-video files; never overwrite an earlier source SHA or segment silently.

## How to inspect or extend it

```bash
jq '.videos[] | {id, sourceDurationSeconds, windows: [.windows[] | {window, sourceOffsetSeconds, cutCandidateCount, cutCandidateCountAtThreshold015}]}' research/analysis/movie-promotions/index.json

jq '{id, source: .originalSourceSha256, windows: [.windows[] | {window, cutCandidates: (.shotCutCandidates | length), audioFrames: (.audioLevels.rows | length)}]}' research/analysis/movie-promotions/inside-out-2.json
```

After running `study-reference` on a freshly acquired, temporary media set, [`scripts/export_movie_promo_evidence.py`](../../../scripts/export_movie_promo_evidence.py) can export an additional source-verified JSON set to a **new empty output directory**. Its inputs are the aggregate window plan, private MP4 files and temporary `study-reference` runs. Diff source hashes and coverage first; integrate new results into this tracked folder with tests before committing.

All entries retain `review-required` rights status, and the source MP4s, extracted audio, JPEG/HTML galleries, transcripts and CDN access tokens are excluded. The Apple preview records explicitly preserve `sourceEdition`, `sourceTrackId` and `catalogUploadIdentityMatch: not-verified`: they are **not claimed to be the exact YouTube upload versions** in the popularity catalog, and one Sony preview is for the *Extended Version* of the film. A scene-difference candidate is **not a confirmed editorial cut**; image motion is **not a proven camera movement**; brightness is **not a physical lighting rig**; audio-level changes are **not identified words or sound effects**. Middle/end clips were re-encoded and have an approximate original position via their declared offset. Any partial AAC frame trimmed at a scan boundary is excluded from RMS/peak evidence and counted explicitly.

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
