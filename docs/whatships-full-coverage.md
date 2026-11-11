# What Ships: full-catalog coverage rather than a handpicked sample

**Goal:** keep an explicitly auditable entry for **every published What Ships video**, across all eight categories. Track the difference between **indexed metadata**, **detailed metadata**, **authorized local footage**, **source-frame analysis**, **character/action/shot/camera/lighting/speech observations**, and **human-reviewed evidence**. Never convert the existence of a directory listing into a claim that we viewed a film.

What Ships documents a public, read-only [search index](https://whatships.com/search-index.json), [OpenAPI](https://whatships.com/openapi.json), and [developer resources](https://whatships.com/developers/). Its [terms](https://whatships.com/terms/) identify the directory as a catalog, **not a video download CDN**. The site links back to the original X posts and creators retain rights. We use the official catalog metadata only. No public X scraping, stream-proxy extraction or unauthorized media downloads.

## Existing state, November 10, 2026

The bundled frozen snapshot `research/whatships-index-2026-11-10.json` already lists **2,861 videos across eight categories**, covering every *indexed video at that snapshot date*. Only **419 / 2,861 (14.6%)** have detailed metadata. The remaining **2,442 (85.4%)** are index-only, with missing duration/views/original X URL kept unknown.

| Category | Indexed | Detailed | Missing detail |
| --- | ---: | ---: | ---: |
| AI | 1,122 | 50 | 1,072 |
| Developer tools | 603 | 50 | 553 |
| Other | 335 | 50 | 285 |
| Design | 310 | 50 | 260 |
| Productivity | 165 | 50 | 115 |
| Consumer | 161 | 50 | 111 |
| Hardware | 96 | 50 | 46 |
| Motion | 69 | 69 | 0 |
| **Total** | **2,861** | **419** | **2,442** |

This is a historical local snapshot, **not a freshly verified site-wide live count**. The read-only catalog can change. Existing nine browser spot checks are qualitative glimpses, not full timecoded reviews or a measure of video footage coverage.

## New CLI

```bash
# All 2,861 entries, every category; explicit missing-media and missing-detail counts.
PYTHONPATH=src python -m kumiki_reference_lab whatships-all report

# A balanced round-robin queue, not biased toward AI or viral-view metadata.
PYTHONPATH=src python -m kumiki_reference_lab whatships-all queue --limit 50

# See metadata gaps first in Design (example).
PYTHONPATH=src python -m kumiki_reference_lab whatships-all queue \
  --category design --missing-detail-only --limit 100

# Refresh the entire public index exactly once. Requires Internet access.
PYTHONPATH=src python -m kumiki_reference_lab whatships-all refresh \
  --out ./runs/whatships-refresh-2026-11-10

# Or run entirely offline with a local saved copy of official search-index.json.
PYTHONPATH=src python -m kumiki_reference_lab whatships-all refresh \
  --previous research/whatships-index-2026-11-10.json \
  --index-file ./authorized-official-search-index.json \
  --retrieved-on 2026-11-10 \
  --out ./runs/whatships-refresh-offline
```

A successful refresh creates a **new, immutable directory**:

- `whatships-all-videos.json` — complete current metadata snapshot, accepted by existing `video-sources --whatships` commands. Previously captured detailed records are preserved *only* where the exact slug and category remain compatible.
- `coverage.json` — **100% enumeration of this retrieved index**, with per-category detailed-metadata gaps. It explicitly reports **zero authorized local media bindings and zero frame-analysis evidence in this catalog dataset** rather than claiming the original media were measured.
- `all-video-backlog.json` — **every video**, not a limited page or sample. Entries have provider-qualified ID, title, category, canonical watch link, known original X URL, detail status, current (unlinked) media status and pending next stages. Queue entries are interleaved across all categories to avoid starving Motion/Hardware/Consumer as the AI catalog grows.
- `index-changes.json` — counts and exact slugs for newly published entries, updated metadata and delistings. Removed source slugs remain visible in this audit report. A sudden loss of more than 10% of prior slugs makes the refresh **fail closed** rather than silently accepting a partial catalog.

The network operation is one **bounded HTTPS GET** of the site's public index. The client disallows redirects/proxies, accepts only JSON, bounds response size to 8 MiB and does **not** fetch individual video pages, posters, playback content or X API data. No paid API or subscription is required. Repeated full-catalog refreshes should be moderate and respectful of site availability.

## Definition of "cover all"

1. **Directory coverage:** 100% of source `kind=video` records in the latest successful official index refresh, with uniqueness and category audits.
2. **Detail coverage:** independently fetch validated title/company, publication date, duration, original X link, tags and *historical* attributed views where available. A missing detail is tracked, **not estimated**. The original X post remains the citation of record.
3. **Frame coverage:** for videos we separately have rights to analyze and possess as authorized local files, run the local frame/shot/motion/character/audio pipeline at original source PTS. Keep actual analyzed frame/time fraction explicit; even six short sampled intervals do **not** mean an entire film was analyzed.
4. **Cinematic technique coverage:** review camera vs subject movement, lens/angle hypotheses, lighting/shadows, transitions, pacing, typography, composition, 2D/paper-cut/collage/3D treatment, character design, actions, speech and scene interactions, **only from video evidence**. Unsupported observations abstain.
5. **Scientific comparison:** use source date, duration, category, creator/account reach where available; *raw view counts alone do not establish virality causes*.
6. **Continuous index updates:** refresh at an appropriate cadence (e.g., weekly). We provide an explicit command and diff; **no unattended network job or scheduled run has been created** by this change.

## What remains blocked

The full-coverage ledger enumerates and schedules every video. [Rate-limited resumable detail enrichment](whatships-detail-enrichment.md) now exists, but the **2,442 missing records in the frozen snapshot have not yet been fetched live**. [Private source-media bindings](whatships-authorized-local-media.md) now attach explicit, operator-attested local source files to exact catalog IDs and verify their SHA-256. A bounded visual-analysis worker remains the next step; the bindings are not footage analysis. No model or catalog tool can infer cinematographic observations from directory metadata alone. Actual optical/audio observation requires local source bytes; site metadata alone cannot produce camera, lighting or character truth.

The included offline tests validate all-category enumeration, strict public index shapes, benign metadata preservation, added/removed listings, failure on index shrinkage, no-network fixture refresh, fair scheduling, and the complete 2,861-entry snapshot. Live website refresh cannot be exercised from environments without HTTP access; the command will be tested live when run in an Internet-connected environment.
