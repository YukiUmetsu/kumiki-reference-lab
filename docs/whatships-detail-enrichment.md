# Enrich every What Ships video with detailed metadata (bounded, resumable)

The full catalog ledger now lists **all 2,861 videos in the frozen November 10 snapshot**, but **2,442 need detailed metadata**. The new `whatships-all enrich` command advances this backlog in **small, respectful batches** using the site's documented, read-only Streamable HTTP MCP catalog server (`get_video`). It never downloads video, posters or streams and never contacts X.

This is designed to work toward **100% detailed metadata**, not merely 100% index enumeration. Every successful record must match the exact public slug, category and canonical directory URL. It must provide a timezone-qualified publication timestamp, original X post URL, duration, title, product/company, tags and description. Historical views are included **only if a view snapshot timestamp is also present**; otherwise views stay unknown.

## Command

```bash
# On a computer with Internet access:
PYTHONPATH=src python -m kumiki_reference_lab whatships-all enrich \
  --previous research/whatships-index-2026-11-10.json \
  --max-details 25 --delay-seconds 1.5 \
  --out runs/whatships-details-batch-001

# Continue using the NEW snapshot. Previously successful details are retained.
PYTHONPATH=src python -m kumiki_reference_lab whatships-all enrich \
  --previous runs/whatships-details-batch-001/whatships-all-videos.json \
  --max-details 25 --delay-seconds 1.5 \
  --out runs/whatships-details-batch-002

# If one source record is unavailable, use --start-offset to inspect later
# missing-detail candidates without deleting or fabricating that record.
PYTHONPATH=src python -m kumiki_reference_lab whatships-all enrich \
  --previous runs/whatships-details-batch-002/whatships-all-videos.json \
  --start-offset 1 --max-details 25 \
  --out runs/whatships-details-batch-003
```

A batch performs at most **100 read-only metadata requests**. The default 25 requests with at least a 1.5-second interval avoids flooding the source. It stops early on transport errors or HTTP 429/5xx. On individual invalid or unavailable entries it **leaves that slug index-only** and records a failure reason. No retry storm or silent success.

The output directory contains the updated `whatships-all-videos.json`, `coverage.json` and `detail-enrichment-report.json`, including attempted/successful/failed slugs, missing count and an explicit distinction between live vs fixture mode. Every batch is immutable and atomically published. The next run uses the previous output snapshot; nothing modifies the bundled original.

## Offline test

`--offline-responses` accepts a small, explicit JSON map from slug to an *existing* MCP JSON-RPC response. This mode has **no network access**; it supports deterministic schema/URL validation and regression tests.

```bash
PYTHONPATH=src python -m unittest tests.test_whatships_detail_enrich -v
```

## Important limits

- The site's [developer docs](https://whatships.com/developers/) describe an unauthenticated read-only MCP endpoint and a `get_video` tool. This client implements the documented standard JSON-RPC `tools/call` structure and accepts bounded JSON or a single SSE data response, but **live protocol interoperability has not been confirmed from this environment**, which lacks direct public DNS access. Incompatible responses are recorded as failures, not coerced into details.
- Do not run many consecutive batches if the site is unavailable or asks clients to slow down. This is an **opt-in manual command**, not a scheduled bulk crawler. Rate limiting and service etiquette are intentional.
- Each output is **metadata only**. Even after all 2,861 entries become detailed, video motion, cut frequency, camera and lighting, audio, dialogue, character look and actions are still **unmeasured** unless actual authorized source media is separately analyzed with source timestamps.
- The site is a directory, **not a video download CDN**. Respect the original creators' ownership and cite their X links rather than reuploading.
- The original snapshot is not a live 2026 market sample; details/view counts are source-reported historical observations and selection bias persists.
