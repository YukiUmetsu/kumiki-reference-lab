# Research evidence: measured public video and poster datasets

This tree holds the numerical evidence behind the acquisition and census work.
Every record is a measurement of a **publicly reachable** video rendition or a
**single published poster still**, made in a temporary directory whose media was
deleted as soon as the numbers and hashes were written. Nothing here contains
video, frames, thumbnails, audio or images.

## What is committed

| site | videos | stills | census | `dataset/` size |
|---|---:|---:|---:|---:|
| `motiondesignawards` | 491 | 1,901 | 491 | 6.23 MiB |
| `shots` | 431 | 40,678 | 431 | 32.36 MiB |
| `aicp` | 294 | 0 | 294 | 4.95 MiB |
| `promonews` | 213 | 16,908 | 212 | 21.51 MiB |
| `directorslibrary` | 143 | 5,348 | 142 | 5.82 MiB |
| `stash` | 0 | 5,277 | 0 | 4.16 MiB |
| **total** | **1,572** | **70,112** | **1,570** | **82.06 MiB** |

Each site keeps `report.md` plain as its human-readable deliverable; the
machine-readable `aggregate.json` is shipped compressed as
`<site>/dataset/aggregate.json.gz`, and this README summarises all six sites. The raw record trees
(`videos/`, `stills/`, `census/`, `catalog.json`, `*-index.json`, `aggregate.json`) stay local and
untracked; their compressed, deterministic copy lives in `<site>/dataset/` and
**is** committed. See each `<site>/dataset/DATASET.md` for that site's exact
counts, catalog URL, acquisition window and unpack commands.

The six measured sites are the snapshot trees added for this dataset. The older
`whatships/` and `movie-promotions/` trees are pre-existing tracked studies and
are unaffected by the evidence packaging rules.

## Record families and schemas

Every document carries a `schemaVersion`; family names are stable across sites.

| family | schema | meaning |
|---|---|---|
| catalog | `kumiki.<site>-catalog.v1` | The site's public catalog projection: identity, title, date, provider, source URLs and scores where published. No media. |
| video evidence | `kumiki.<site>-video-evidence.v1` | One downloaded public rendition, probed and measured over bounded source-PTS windows. Holds source hash, duration, resolution, codec/timebase, per-window display-RGB proxy numbers and cut-candidate counts. The media was deleted after measurement. |
| still evidence | `kumiki.<site>-still-evidence.v1` | One published poster image per item: image hash, format, bytes, dimensions and display-RGB/hue/edge proxies. A still is not a video frame and carries no motion or timing evidence. |
| census evidence | `kumiki.<site>-census-evidence.v1` | A full-runtime decode of the same rendition: scene-score cut candidates, cut-gap statistics, a `strobe` density flag and fixed-cadence appearance samples. Film-level values, not window samples. |
| video index | `kumiki.<site>-index.v1` | Projection of `videos/`: measured rows, skip rows (policy/resume refusals) and failure rows. `counts.measured` must equal the number of `videos/*.json`. |
| stills index | `kumiki.<site>-stills-index.v1` | Projection of `stills/`, same contract. |
| census index | `kumiki.<site>-census-index.v1` | Projection of `census/`: one row per full-runtime record. |
| aggregate | `kumiki.<site>-aggregate.v1` | Derived, deterministic roll-up of the records and index counts used by `report.md`. |

`<site>` is one of `motiondesignawards`, `shots`, `aicp`, `promonews`,
`directorslibrary`, `stash`. Not every site has every family: AICP publishes no
poster lane, STASH has no downloadable video lane, and therefore no census.

## Reproduce

The adapters live in `scripts/research_*.py`; the full-runtime census driver is
`scripts/census_video_cuts.py`. Each site follows the same pattern (example for
`shots`):

```sh
export PYTHONPATH=src
SITE=shots
OUT=research/analysis/$SITE

# 1. Enumerate the public catalog (network).
python scripts/research_$SITE.py catalog --out $OUT/catalog.json

# 2. Measure bounded windows; media is deleted inside the job.
python scripts/research_$SITE.py collect --catalog $OUT/catalog.json \
    --out-dir $OUT --acknowledge-rights

# 3. Measure one published poster still per item (where the site has one).
python scripts/research_$SITE.py stills --catalog $OUT/catalog.json \
    --out-dir $OUT

# 4. Full-runtime census over the video records.
python scripts/census_video_cuts.py --root research/analysis --site $SITE \
    --acknowledge-rights

# 5. Deterministic human report and aggregate (offline, read-only).
python scripts/research_$SITE.py report --out-dir $OUT
```

`research_wordpress_stills.py` covers both `directorslibrary` and `stash`; add
`--site directorslibrary` or `--site stash` to its subcommands. The other
adapters take the site from the script name.

Then verify and package:

```sh
# Zero errors are required. Duplicate-media warnings are expected: public
# catalogs repeat the same work under several categories, and a video record
# plus its poster record intentionally share work identity, not bytes.
python scripts/audit_research_evidence.py --root research/analysis

# Re-derive every index from the records on disk (skips/failures preserved).
python scripts/rebuild_evidence_indexes.py --root research/analysis

# Write deterministic dataset/ trees and print their size.
python scripts/package_research_dataset.py --root research/analysis
```

Both helpers are idempotent: a second run reports `unchanged` / produces
byte-identical archives. The package uses gzip level 1 with zeroed timestamps
and metadata, sorted archive members, and no OS-specific fields.

## Duplicate warnings are expected, not errors

The auditor's 1,643 warnings are all duplicate media groups:

- **Cross-family (1,270):** a work's video record and its poster-still record
  describe the same work but never share bytes; the pattern is reported for
  transparency.
- **Source SHA-256 (373):** the same public file is catalogued under multiple
  entries (categories, re-posts, sibling films). This is a property of the
  source catalogues, not a collection error.

Run with `--strict-duplicates` only for an integrity gate that intentionally
treats repeated published media as a failure.

## Non-claims

- Cut candidates are ffmpeg scene-score exceedances, **not verified edits**.
- Stills are single published posters, **not decoded video frames**.
- Window values are samples of the runtime; census values are film-level.
- Numbers are display-RGB proxies, not scene-linear light, calibrated colour,
  style, quality, intent, identity or authorship.
- Public availability is not a license; rights remain `review-required`.
- No human or expert review was performed.
