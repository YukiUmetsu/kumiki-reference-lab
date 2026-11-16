# aicp — measured evidence dataset

This directory is the compressed, committable form of the raw evidence trees
under `research/analysis/aicp/`. `report.md` stays plain beside it as the
human-readable deliverable; `aggregate.json` is packaged compressed.

## Counts and schemas

| family | records | schema(s) | record `generatedAt` window (UTC) |
|---|---:|---|---|
| videos | 294 | `kumiki.aicp-video-evidence.v1` × 294 | `2026-11-12T04:55:41.732621Z` .. `2026-11-12T14:35:25.091098Z` |
| stills | 0 | — | — |
| census | 294 | `kumiki.aicp-census-evidence.v1` × 294 | `2026-11-15T14:47:24.522295Z` .. `2026-11-15T15:23:22.933702Z` |

Total records: **588**.

- Source catalog: https://aicpawards.com/api
- Catalog schema: `kumiki.aicp-catalog.v1`; retrieved `2026-11-15T14:45:01.695341Z`.
- Overall record acquisition window (`generatedAt`, UTC): `2026-11-12T04:55:41.732621Z` .. `2026-11-15T15:23:22.933702Z`.

## What is retained

Every downloaded media file — each video rendition and each published poster
image — was measured in a temporary directory and then deleted. Only numeric
measurements, catalog metadata and SHA-256 hashes are retained. No video,
frame, thumbnail, audio, image or other media is included in this package or
redistributed. The record trees are archived verbatim; `catalog.json.gz` and the
`*-index.json.gz` files are the same JSON documents gzip-compressed.

## Unpack

```sh
cd research/analysis/aicp
tar -xzf dataset/videos.tar.gz
tar -xzf dataset/stills.tar.gz
tar -xzf dataset/census.tar.gz
gzip -dk dataset/catalog.json.gz
gzip -dk dataset/index.json.gz
gzip -dk dataset/census-index.json.gz
gzip -dk dataset/aggregate.json.gz
```

The archives restore `videos/`, `stills/` and `census/` under the current
directory; `gzip -dk` writes each JSON beside its `.gz`. An empty family is an
empty archive. Rebuild the indexes with
`PYTHONPATH=src python scripts/rebuild_evidence_indexes.py --root research/analysis --site aicp`,
and repack this directory with
`PYTHONPATH=src python scripts/package_research_dataset.py --root research/analysis --site aicp`.

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
