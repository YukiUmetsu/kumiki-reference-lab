# Generalized video reference sources

## Intent

Let researchers discover and open original launch films from What Ships alongside the existing YouTube reference cohorts. Preserve immutable provenance, explicitly distinguish indexed metadata from directly sourced detail, and never mistake public playback for the right to download or redistribute footage.

## Scope

- Normalize YouTube and What Ships metadata into one **offline reference** interface with `provider`, stable provider-qualified `id`, `watchUrl`, `originalUrl` (when known), title, creator, category, date, duration, source-attributed views, tags, and a metadata-only review status.
- Accept a bounded, versioned What Ships snapshot produced from its official public index and read-only MCP detail records. Include all entries in the snapshot, including index-only records with unknown views/original URL.
- Add `video-sources validate|list|search|show` without changing the existing `video-references` schema or CLI behavior. Ship the complete November 10 metadata-only site index (2,861 entries; 419 detailed) and a concise 69-film Motion cohort; **neither** contains video assets.
- Output view snapshot dates and the original X post link when known. Search and ranking are metadata tools, not claims about film quality.
- Leave `inspect`, `study-reference`, decoded-frame visual events and their local-path-only source contracts intact. The user supplies an authorized local media file to run numeric analysis; `watchUrl` is a browser page, not an FFmpeg input.

## Non-goals and anti-goals

- No downloading, stream ripping, caching, rehosting, or automatic analysis of copyrighted videos from What Ships' playback proxy. The site describes itself as a browsing and citation directory, not a download CDN.
- No inferred production style, camera movement, retention, engagement, or lighting frequency from title/category/poster metadata.
- No hard-coded YouTube ID assumptions in the new normalized catalog; no weakening of the existing YouTube-only v1 validation.

## Approaches considered

1. Extend `popular-video-references.v1` with optional X IDs: smallest diff, but breaks its precise YouTube-only contract and semantics.
2. **Separate provider adapters and a normalized read-only interface (chosen):** preserves v1 and makes future sources possible at the cost of a small parallel CLI and schema.
3. General-purpose URL downloader feeding FFmpeg: unsuitable because access, rights and PTS are not equivalent across remote video hosts.

## Constraints and safety

Python standard library only; no new paid API or runtime dependency. Treat fetched/saved metadata as untrusted JSON: size cap, duplicate-key rejection, slug/URL validation, exact provider origins, safe handling of missing view evidence, no network operations from list/search/show. Keep imported data provenance and rights flags explicit. CLI error exit code 2 on invalid source data.

## Verification

Test two providers, mixed ranked searches, complete and partial What Ships records, duplicates, invalid origins, malformed/oversized/symlink input, missing view snapshots and CLI output. Verify the existing popular-video regression suite and full project test suite unchanged. The Motion snapshot is source-attributed and may become stale; users can supply a newer snapshot.
