# directorslibrary — measured evidence dataset

This directory is the compressed, committable form of the raw evidence trees
under `research/analysis/directorslibrary/`. `report.md` stays plain beside it as the
human-readable deliverable; `aggregate.json` is packaged compressed.

## Counts and schemas

| family | records | schema(s) | record `generatedAt` window (UTC) |
|---|---:|---|---|
| videos | 143 | `kumiki.directorslibrary-video-evidence.v1` × 143 | `2026-11-12T05:20:59.414476Z` .. `2026-11-12T18:59:38.604785Z` |
| stills | 5,348 | `kumiki.directorslibrary-still-evidence.v1` × 5348 | `2026-11-12T03:33:46.825747Z` .. `2026-11-12T04:20:38.082360Z` |
| census | 142 | `kumiki.directorslibrary-census-evidence.v1` × 142 | `2026-11-13T08:48:02.783396Z` .. `2026-11-13T09:01:57.913742Z` |

Total records: **5,633**.

- Source catalog: https://directorslibrary.com/wp-json/wp/v2/video?per_page=100&page=1&orderby=date&order=desc&_fields=id%2Cslug%2Cdate%2Clink%2Ctitle%2Cfeatured_media%2Ccategories%2Ctags%2Clocation%2Caspect_ratio%2Cagency%2Crecord_label%2Cfestival%2Caward%2Cformat%2Cclass_list%2Cyoast_head_json
- Catalog schema: `kumiki.directorslibrary-catalog.v1`; retrieved `2026-11-12T03:33:46.152463Z`.
- Overall record acquisition window (`generatedAt`, UTC): `2026-11-12T03:33:46.825747Z` .. `2026-11-13T09:01:57.913742Z`.

## What is retained

Every downloaded media file — each video rendition and each published poster
image — was measured in a temporary directory and then deleted. Only numeric
measurements, catalog metadata and SHA-256 hashes are retained. No video,
frame, thumbnail, audio, image or other media is included in this package or
redistributed. The record trees are archived verbatim; `catalog.json.gz` and the
`*-index.json.gz` files are the same JSON documents gzip-compressed.

## Unpack

```sh
cd research/analysis/directorslibrary
tar -xzf dataset/videos.tar.gz
tar -xzf dataset/stills.tar.gz
tar -xzf dataset/census.tar.gz
gzip -dk dataset/catalog.json.gz
gzip -dk dataset/index.json.gz
gzip -dk dataset/stills-index.json.gz
gzip -dk dataset/census-index.json.gz
gzip -dk dataset/aggregate.json.gz
```

The archives restore `videos/`, `stills/` and `census/` under the current
directory; `gzip -dk` writes each JSON beside its `.gz`. An empty family is an
empty archive. Rebuild the indexes with
`PYTHONPATH=src python scripts/rebuild_evidence_indexes.py --root research/analysis --site directorslibrary`,
and repack this directory with
`PYTHONPATH=src python scripts/package_research_dataset.py --root research/analysis --site directorslibrary`.

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
