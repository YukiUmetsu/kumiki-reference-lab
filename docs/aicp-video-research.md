# AICP Awards video research

Ephemeral, source-PTS measurement of the public AICP Awards commercial archive.
The collector is `scripts/research_aicp.py`; it is the only AICP component that
touches the network or downloads media. Every mechanic — allowlisting,
retrieval, HLS planning/remux, probing, window/still measurement, evidence
assembly, atomic writes, resume checks, index assembly, and the pooled batch
loop — comes from `src/kumiki_reference_lab/acquisition/`.

## Source: one brochure page, one GraphQL door

`https://aicp.com/aicp-awards/aicp-awards-archive` is a brochure page that only
links to the real archive at `https://aicpawards.com` (a 789-byte Vite SPA
shell). The SPA has no server-rendered catalog; its only data door is:

```
POST https://aicpawards.com/api
Content-Type: application/json

{"rows":{"query":"{ commercialsEntries(limit: 100, offset: 0) {
   ... on commercials_commercial_Entry {
     id slug title year company duration video
     videoType { title }
     showCategory { title } postCategory { title } nextCategory { title }
     screenshot { url width height }
   } } }"}
```

There is no authentication, cookie, or token. `robots.txt` returns HTTP 404 at
the time of writing (no rules published); this adapter still fetches only the
catalog API, one HLS file per explicitly requested entry, and one published
screenshot per explicitly requested still.

### Response envelope and the HTTP-200 trap

The response is keyed by the request alias:

```json
{"rows": {"data": {"commercialsEntries": [ ... ]}}}
```

A GraphQL failure comes back as **HTTP 200** with the error inside the alias:

```json
{"rows": {"errors": [{"message": "Cannot query field ..."}]}}
```

A naive `raise_for_status()` records that as success. `_post_graphql` checks the
alias block explicitly, raises on `errors` at either the top level or inside the
alias, and refuses a response without the expected `data` object.

### Counting and pagination

```
{"c":{"query":"{ entryCount(section: \"commercials\") }"}}      -> 2715
{"c":{"query":"{ entryCount(section: \"commercials\", year: 2025) }"}} -> 84
```

The argument is `section:`, not `collection:`. Paging is
`commercialsEntries(limit: 100, offset: N)` newest-first; the collector loops
`offset += len(rows)` until a short or empty page (28 pages at the current
count), with a hard page budget. `--limit N` caps collected rows and requests a
smaller first page when possible; `--limit 0` means all remaining.

### Field quirks the adapter handles

| field | quirk |
| --- | --- |
| `id` | a **string** (`"1185644"`), kept as `str` so `--resume` matches |
| `duration` | `"MM:SS"` or `"H:MM:SS"` (`"1:31:34"`); parsed explicitly, never `float()` |
| `screenshot` | relative to `https://aicpawards.com`; `urljoin`, tolerating list/single node |
| `company` | the only populated credit field, and often null; agency/director live in an empty `credits` relation and are never invented |
| award level | no award-level field exists (no gold/silver/bronze); membership in `commercialsEntries` is the honoree signal |
| `videoType` | observed `Full Show Reel`, `Full Post Show Reel`, `Sponsor Reel`, `NEXT Premiere Show`, `Opening Title` |

Because `duration` uses colons, a plain `float()` returns `None` and silently
disables the duration guard. `parse_duration_text` returns integer seconds for
valid `MM:SS`/`H:MM:SS`, and `None` for garbage, so an unparseable duration is
recorded as `null` (and the post-download probe remains the backstop) rather
than being treated as zero.

## Media chain: Vimeo external → signed vod-adaptive HLS

`video` is

```
https://player.vimeo.com/external/<id>.m3u8?s=...&logging=false
```

which **302s** to a signed origin:

```
https://vod-adaptive-ak.vimeocdn.com/exp=...~hmac=.../.../playlist.m3u8?pathsig=...
```

The signed target expires in roughly an hour, needs no cookies and no
`Referer`, and supports byte ranges. The adapter:

1. allowlists `player.vimeo.com` and `*.vimeocdn.com` with `allow_query=True`;
2. follows the 302 chain itself, re-validating **every** hop with the same
   allowlist and query opt-in;
3. hands the final signed master to `download_media(..., HLS,
   allow_query=True)` immediately, and never persists the signed target.

Step 2 is required: the signed master declares its variant and audio URIs
*relative* (`../../../../../d466137d/avf/.../media.m3u8?pathsig=...`). Resolving
those against the pre-redirect `player.vimeo.com` URL produces HTTP 404s.
Resolving against the post-redirect CDN URL produces the working rendition:

```
player.vimeo.com/external/1198204326.m3u8?s=...
  -> 302 -> vod-adaptive-ak.vimeocdn.com/exp=...~hmac=.../.../playlist.m3u8
  -> variant https://vod-adaptive-ak.vimeocdn.com/exp=.../.../v2/playlist/av/...
```

`acquisition.videoUrl` records the catalog's public HLS entry URL, not the
short-lived signed redirect target. `acquisition.mediaRetained` is always
`false`, and no media, frame, thumbnail, or audio byte enters the evidence tree.

Posters stay on the award site itself (`aicpawards.com`) through
`allowlisted_image_url` with the strict default policy (`allow_query=False`).

## Filters and explicit skip reasons

Catalog rows carry `downloadable` and `downloadReason`. Collection additionally
pre-rejects before any download, and every skip row states its reason:

| reason | meaning |
| --- | --- |
| `unsupported-long-form` | any `videoType` names a full show/program (`Full Show Reel`, `Full Post Show Reel`, `NEXT Premiere Show`) |
| `duration-over-cap` | parsed catalog duration exceeds `--max-duration-seconds` |
| `no-video-url` | the entry has no `video` field |
| `unsupported-provider` | the `video` URL is not an HLS rendition |
| `no-poster` | the entry has no screenshot (stills lane only) |

Post-download failures are recorded as `download-failed: ...` (transport,
signed-URL expiry, byte cap, ffmpeg remux) or `probe-failed: ...` (local
characterisation, duration re-check, or window measurement). The default caps
are `--max-duration-seconds 600` and `--max-file-bytes 250MiB`; the HLS rendition
is bounded to 1280 px wide by the engine.

## Commands

```bash
# 1. Enumerate the whole archive (28 pages at 100/page; reports 2,715 entries).
python scripts/research_aicp.py catalog \
  --out research/analysis/aicp/catalog.json

# Smoke the catalog on a few entries only.
python scripts/research_aicp.py catalog \
  --out /tmp/aicp-catalog.json --limit 5 --delay-seconds 1.0

# 2. Measure eligible entries (download -> probe -> windows -> delete).
python scripts/research_aicp.py collect \
  --catalog research/analysis/aicp/catalog.json \
  --out-dir research/analysis/aicp \
  --acknowledge-rights --windows 4 --window-seconds 10 \
  --max-duration-seconds 600 --max-file-bytes 250MiB

# Resume is the default; --refresh re-measures. --limit 0 means all remaining.
python scripts/research_aicp.py collect \
  --catalog research/analysis/aicp/catalog.json \
  --out-dir research/analysis/aicp --limit 0 --jobs 2 --acknowledge-rights

# 3. One published screenshot per entry (never fetches video).
python scripts/research_aicp.py stills \
  --catalog research/analysis/aicp/catalog.json \
  --out-dir research/analysis/aicp --resume --delay-seconds 0.8

# 4. Offline, deterministic report from the committed records.
python scripts/research_aicp.py report \
  --out-dir research/analysis/aicp --top 20

# Offline tests (no network, no ffmpeg).
PYTHONPATH=src python -m unittest tests.test_aicp_research -v
```

`--resume` (default) skips a record whose `id` already matches and leaves the
file byte- and mtime-identical. `--refresh` re-measures. `--jobs` is 1–2 for
video and 1–3 for stills. `--limit 0` is not an offline no-op: it means “all
remaining”, and the run terminates on the natural end of the catalog.

Output layout:

```
<out-dir>/
  catalog.json                 # kumiki.aicp-catalog.v1 (+ counts/provenance)
  index.json                   # kumiki.aicp-index.v1
  videos/<id>-<slug>.json      # kumiki.aicp-video-evidence.v1
  stills-index.json            # kumiki.aicp-stills-index.v1
  stills/<id>-<slug>.json      # kumiki.aicp-still-evidence.v1
  report.md                    # rendered, read-only report
  aggregate.json               # kumiki.aicp-aggregate.v1
```

## What is measured

Up to `--windows` (default 4) non-overlapping `--window-seconds` (default 10)
windows, spread evenly across the runtime. The first starts at 0 and the trailing
10% is skipped. Each window embeds the verbatim payload from
`analyze_source_visual_window`: sampled source PTS, display-RGB luma/saturation
proxies, cut candidates between first and last sample, and within-shot
inter-frame RGB delta per second. `summary` is derived only from those embedded
probes; missing fields become `null`.

The report tabulates year, title, company, video type, catalog duration text and
decoded duration, resolution, fps, derived bitrate (`sizeBytes × 8 ÷ duration`),
windows, coverage, cuts, cuts/minute, mean luma, mean saturation, and
within-shot delta/s, plus per-window detail for the top N and year/type
distributions. `generatedAt` is derived from the newest record timestamp (or the
catalog's `retrievedAt`), so repeated report runs are byte-identical.

## Evidence rules

- Only numeric measurements, hashes, and catalog metadata leave the run.
- A screenshot is **not** a video frame. Its record states
  `coverage.isSourceVideoFrame: false`,
  `evidenceStatus: "single-published-still-metrics-not-video-measurement"`, and
  `acquisition.imageRetained: false`; it never enters motion aggregates.
- Video records state
  `evidenceStatus: "sampled-original-source-pts-metrics-not-expert-reviewed"`
  and `rightsStatus: "review-required"`.
- Public availability is not a licence. `collect` requires an explicit
  `--acknowledge-rights` attestation, recorded as
  `acquisition.attestation.rightsBasis = "user-declared-research-use"`.
- Media and images land in a private scratch directory and are deleted in a
  `finally` block; a failed download or measurement leaves no record and no
  bytes.

## Explicit non-claims

- No style, aesthetic quality, mood, lighting, camera/lens, editing-intent,
  authorship, identity, or creative-origin inference from numbers.
- No award level. The archive exposes no gold/silver/bronze field; membership in
  `commercialsEntries` is the only honoree signal.
- No invented credits. `company` appears only where the archive populates it;
  agency/director are absent on montages and are reported as `null`.
- No full-film review. `coverage.fullRuntimeMeasured` is `false`; only sampled
  windows were measured.
- Display-RGB luma/saturation and cut candidates are numeric proxies, not
  semantic labels or expert judgments.
- Catalog metadata (title, year, company, video type, categories) is
  self-reported by aicpawards.com and not independently verified.
- No cookies, login, token, DRM circumvention, or access-control bypass. The
  signed CDN redirect target is never persisted or reused.

## Reporting

`report.md` and `aggregate.json` are generated by
`kumiki_reference_lab.acquisition.reporting` (rankability gate, media dedupe,
comparability and coverage blocks). Video aggregates dedupe by media SHA-256
and state `n` before and after dedupe, so duplicate catalogue works are visible.
