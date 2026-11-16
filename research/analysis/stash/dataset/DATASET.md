# stash — measured evidence dataset

This directory is the compressed, committable form of the raw evidence trees
under `research/analysis/stash/`. `report.md` stays plain beside it as the
human-readable deliverable; `aggregate.json` is packaged compressed.

## Counts and schemas

| family | records | schema(s) | record `generatedAt` window (UTC) |
|---|---:|---|---|
| videos | 0 | — | — |
| stills | 5,277 | `kumiki.stash-still-evidence.v1` × 5277 | `2026-11-12T03:32:47.162358Z` .. `2026-11-12T18:40:02.475812Z` |
| census | 0 | — | — |

Total records: **5,277**.

- Source catalog: https://www.stashmedia.tv/wp-json/wp/v2/posts?per_page=100&page=1&orderby=date&order=desc&_fields=id%2Cdate%2Cslug%2Clink%2Ctitle%2Cexcerpt%2Cfeatured_media%2Ccategories%2Cauthor%2Cyoast_head_json
- Catalog schema: `kumiki.stash-catalog.v1`; retrieved `2026-11-12T03:32:46.476588Z`.
- Overall record acquisition window (`generatedAt`, UTC): `2026-11-12T03:32:47.162358Z` .. `2026-11-12T18:40:02.475812Z`.

## What is retained

Every downloaded media file — each video rendition and each published poster
image — was measured in a temporary directory and then deleted. Only numeric
measurements, catalog metadata and SHA-256 hashes are retained. No video,
frame, thumbnail, audio, image or other media is included in this package or
redistributed. The record trees are archived verbatim; `catalog.json.gz` and the
`*-index.json.gz` files are the same JSON documents gzip-compressed.

## Unpack

```sh
cd research/analysis/stash
tar -xzf dataset/videos.tar.gz
tar -xzf dataset/stills.tar.gz
tar -xzf dataset/census.tar.gz
gzip -dk dataset/catalog.json.gz
gzip -dk dataset/stills-index.json.gz
gzip -dk dataset/aggregate.json.gz
```

The archives restore `videos/`, `stills/` and `census/` under the current
directory; `gzip -dk` writes each JSON beside its `.gz`. An empty family is an
empty archive. Rebuild the indexes with
`PYTHONPATH=src python scripts/rebuild_evidence_indexes.py --root research/analysis --site stash`,
and repack this directory with
`PYTHONPATH=src python scripts/package_research_dataset.py --root research/analysis --site stash`.

## Non-claims

- **Cut candidates are not edits.** Census and window cut candidates are ffmpeg
  scene-score exceedances; fast motion, flashes, transitions and compression can
  exceed the threshold. They are not verified edits.
- **Stills are not video frames.** A still is one published poster image, with
  no motion, cut, pacing or timing evidence.
- **Window values are samples.** They describe bounded source-PTS windows, not
  the whole runtime.
- **Census values are film-level.** They come from a full-runtime decode with a
  fixed-cadence appearance sample; they are not a human review.
- **Numbers are proxies.** Display-RGB luma/saturation at decode size are not
  scene-linear light, calibrated colour, or a style, quality, intent, identity
  or authorship judgement.
- **No expert review.** No human review was performed; these are automated
  numeric measurements.
