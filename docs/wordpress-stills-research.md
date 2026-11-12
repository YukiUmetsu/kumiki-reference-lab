# WordPress poster-stills research (Directors' Library, STASH)

`scripts/research_wordpress_stills.py` is one config-driven adapter for two
WordPress sites. It writes a full slim catalogue and measures **one published
poster still** per item. Each still is downloaded once, decoded once at 160x90
RGB, measured numerically, and deleted immediately. Only numeric evidence,
hashes, and catalogue metadata are committed.

This adapter is **stills-only for STASH** and **stills + a YouTube video lane for
Directors' Library**. STASH's every embed is Vimeo, which the repository records
as unsupported, so no STASH row is ever attempted for video. Directors' Library
embeds both Vimeo and YouTube; its YouTube entries are measured through the
engine's cookie-free yt-dlp provider, and its Vimeo-only rows are recorded as
`unsupported-vimeo`. No cookies, logins, player API tricks, or DRM
circumvention are used anywhere.

All retrieval mechanics (allowlisting, bounded downloads, still measurement,
evidence assembly, atomic writes, resume checks, index assembly, pooled batch
loop) come from `src/kumiki_reference_lab/acquisition/`
(see `docs/public-video-acquisition.md`). This document covers only the
WordPress adapter.

## Sites and endpoints

The catalogue is the public, auth-free WordPress REST API. One site entry in
the `SITES` table supplies the base URL, post type, taxonomy list, schema
prefix, catalogue `_fields`, and provider notes.

| site key | host | post type | reported items |
| --- | --- | --- | --- |
| `directorslibrary` | `directorslibrary.com` | `video` | `X-WP-Total: 5412` |
| `stash` | `www.stashmedia.tv` | `posts` | `X-WP-Total: 5399` |

Catalogue request:

```text
GET https://<host>/wp-json/wp/v2/<post-type>
    ?per_page=100&page=<n>&orderby=date&order=desc&_fields=<projection>
```

- `per_page` is capped at 100.
- Paging is sequential and polite: one request at a time, with a 1.0 s pause
  plus equal jitter between pages (configurable with `--delay-seconds`).
- Page overflow returns **HTTP 400 `rest_post_invalid_page_number`**. The
  adapter treats that response as a normal end-of-catalogue signal: it stops
  immediately and does **not** retry. Other 4xx responses are contract errors;
  only 429/5xx and transport failures are retried with bounded backoff.
- The WP REST URL is validated against the site's exact host allowlist (with
  the engine's query opt-in enabled for the API's own `per_page`/`page`/
  `_fields` parameters); redirect targets are re-validated the same way.

Projections:

```text
directorslibrary:
  id,slug,date,link,title,featured_media,categories,tags,location,
  aspect_ratio,agency,record_label,festival,award,format,class_list,
  yoast_head_json

stash:
  id,date,slug,link,title,excerpt,featured_media,categories,author,
  yoast_head_json
```

### Taxonomy names

Every taxonomy value in the catalogue is an array of **term IDs**. The adapter
resolves names with one request per taxonomy that actually appears in the
fetched rows:

```text
GET /wp-json/wp/v2/<taxonomy>?per_page=100&page=<n>&_fields=id,name,slug
```

`X-WP-TotalPages` is followed; the resolved `{id: {name, slug}}` map is cached
in the catalogue document and each row keeps aligned `termIds` and `terms`
(name) arrays. If a taxonomy cannot be read, its IDs remain with `null` names
and the failure is recorded under `counts.termResolutionErrors`.

Directors' Library taxonomies: `categories`, `tags`, `location`,
`aspect_ratio`, `agency`, `record_label`, `festival`, `award`, `format`.
STASH: `categories`.

The Directors' Library REST API does **not** expose ACF, so director, duration,
brand, and agency values do not exist in the catalogue. Those fields are absent,
not invented.

### Posters

The poster is `yoast_head_json.og_image[0]` — a self-hosted, query-free image
URL on the site's own host. No per-item page fetch is needed. Some STASH
installations emit `og:image` as `http://www.stashmedia.tv/...`; for that exact
allowlisted host the adapter upgrades the scheme to HTTPS before policy
validation. No other rewriting occurs (a query string, another host, a port, a
fragment, or credentials are still refused). A row with no `og_image`, or with
a poster on a non-allowlisted host or carrying a query string, keeps
`posterUrl: null` and an explicit `posterStatus`:

- `ok`
- `missing-og-image`
- `poster-host-not-allowlisted`

The stills lane records such a row as a `no-published-poster` skip with a
reason; it never crashes on it.

## Embed discovery, the video lane, and STASH's refusal

```text
<video> -> player.vimeo.com/video/<id>  or  www.youtube.com/embed/<id>
```

The embed URL is **not** in the WP REST payload. It exists only in the rendered
article HTML at `link` (roughly 120 KB): an `<iframe src>` and the same URL in
the page's JSON-LD `VideoObject.embedUrl`. No progressive MP4 or HLS file is
published, and Vimeo's `/config` and player pages return 401/403 to scripted
clients.

`collect` discovers the embed per row in this order:

1. allowlist the row's `link` (exact site host, no query, `allow_query=False`)
   and read it through the engine's bounded text fetch;
2. scan the page for the first YouTube single-video shape —
   `/embed/<11>`, `/watch?v=<11>`, `/shorts/<11>`, `youtu.be/<11>`;
3. when a direct scan finds nothing, parse each `application/ld+json` block and
   retry on its `embedUrl`/`contentUrl`;
4. classify the result:
   - a YouTube id -> canonical `https://www.youtube.com/watch?v=<id>` and measure;
   - only a Vimeo embed -> skip `unsupported-vimeo` (never fetched or probed);
   - no embed -> skip `no-embed-found`.

`stash` has no video lane at all: its embeds are Vimeo-only, so `collect`
writes a clean refusal for **every** row with reason
`site-has-no-downloadable-rendition` and attempts nothing. Counts therefore stay
honest instead of implying a lane that cannot run.

The video lane then measures exactly like the sibling adapters:
`download_media(..., provider=YOUTUBE, yt_dlp=...)` -> `source_metadata` ->
`measure_windows`/`plan_windows` -> `build_video_evidence`. Media lives in one
`TemporaryDirectory` and is deleted before the record is written.

Refusal handling:

- `YtDlpRefusedError` (403/login-only/unsupported client) -> skip row
  `provider-refused`, **never retried**;
- any other `YtDlpError` / download or measurement failure -> failure row with a
  `transient:`/`probe`-style reason;
- article-fetch HTTP 403/429 -> skip row `site-refused`, no retry loop.

The adapter still sets `videoDownloadable: false` and a reason on every
catalogue row: the catalogue itself exposes no file, and that field describes
the REST payload, not the separately-measured article embed. STASH remains a
magazine feed: many posts are image galleries rather than videos, so its
per-row `provider` field is only a downloadability label
(`unsupported-embed` or `null`), not a claim that every post contains a video.

Per-row catalogue provider logic:

- Directors' Library is a WordPress `video` post type, so its rows carry
  `provider: "unsupported-embed"`.
- STASH rows carry `"unsupported-embed"` only when Yoast exposes an
  `og_video` or `og_type` starting with `video`; otherwise `null`.

## Video record (`kumiki.<site>-video-evidence.v1`)

`collect` writes one atomic `videos/<id>-<slug>.json` per measured row and
refreshes `index.json` atomically (`kumiki.<site>-index.v1`, separate from
`stills-index.json`). Identity fields mirror the stills record, plus:

```text
provider: "youtube",
videoUrl: "https://www.youtube.com/watch?v=<id>",
downloadMethod: "ytdlp-merge",
mediaRetained: false,
renditionNote: "platform-encoded YouTube rendition measured, not the work's delivered master",
source{mediaSha256,sizeBytes,durationSeconds,resolution,...},
acquisition{provider,videoUrl,method,mediaRetained:false,attestation},
coverage{windowsMeasured,windowSeconds,sampledSeconds,fractionOfRuntime,...},
windows[], summary{cutCandidates,cutCandidateRatePerMinute,meanDisplayLuma,...},
evidenceStatus:"sampled-original-source-pts-metrics-not-expert-reviewed",
rightsStatus:"review-required", limits[], generatedAt
```

`limits` explicitly state that only sampled source-PTS windows were measured,
that the source is a platform-encoded YouTube rendition rather than a delivered
master, and that no cookies/logins/DRM workarounds were used. Video media is
never retained.

`collect` requires `--acknowledge-rights`. `--limit` (default 250) caps only
**attempted** rows: resume skips and the whole-site STASH refusal do not consume
it. `--resume` (default) reads existing video records and leaves their bytes and
mtimes untouched; `--refresh` re-measures. `--jobs` is bounded to 1..2 and the
default `--delay-seconds 1.4` keeps the Cloudflare-fronted site polite. A
403/429 from the article page is a refusal, not a transient fault.

## Catalogue schema (`kumiki.<site>-catalog.v1`)

```text
schemaVersion, generatedAt, site, sourceHost, postType, endpoints, query,
provider, providerNote, caveat, counts, termCache, items[]
```

Each slim row keeps only:

```text
id, slug, title (HTML-unescaped), publicationDate, articleUrl,
featuredMediaId, posterUrl, posterWidth, posterHeight,
termIds{taxonomy:[int]}, terms{taxonomy:[name|null]},
provider, videoDownloadable (false), videoDownloadableReason
excerptText   (STASH only, tags stripped, entity-unescaped, bounded to 100 chars)
posterStatus  (only present when it is not "ok")
```

Rows are ordered newest-first by publication date, then descending post ID.
Empty taxonomy arrays are omitted. The offline test asserts a typical row stays
under 1 KB; observed live rows are roughly 0.7-0.95 KB. `counts` carries
`catalogItems`, `reportedTotal`, `pagesFetched`, `reachedPageOverflow`,
`withPoster`, `withoutPoster`, `providerCounts`, `termCounts`, and
`termResolutionErrors`.

## Stills record (`kumiki.<site>-still-evidence.v1`)

For each remaining row the lane:

1. allowlists the poster (exact site host, `allow_query=False`);
2. downloads it into a `TemporaryDirectory` with a 16 MiB cap;
3. probes dimensions, decodes once at 160x90 RGB, and computes
   `acquisition.stills.measure_still` metrics (mean RGB, display-luma proxy,
   luma standard deviation, saturation proxy, shadow/bright pixel fractions,
   5-bucket luma histogram, dominant hue family, edge-density proxy);
4. deletes the image in `finally`;
5. writes one atomic `stills/<id>-<slug>.json` and refreshes
   `stills-index.json` atomically.

Record shape:

```text
schemaVersion, site, postId, slug, title, publicationDate, articleUrl,
provider, termIds, terms,
poster{url,width,height},
videoDownloadable: false,
still{imageUrl,imageSha256,imageFormat,imageBytes,imageWidth,imageHeight,metrics},
acquisition{method:"poster-still-http", imageRetained:false},
coverage{isSourceVideoFrame:false, note},
evidenceStatus:"single-published-still-metrics-not-video-measurement",
rights{basis,status:"review-required",note},
limits[], generatedAt
```

`limits` explicitly deny motion, cut, pacing, timing, sequence, edit-rhythm,
aesthetic, style, and authorship claims. Image bytes are never retained.

`--resume` (default) only reads existing records: their bytes and mtimes are
left untouched. `--refresh` re-measures. `--limit 0` (the default) means **all
remaining rows** and terminates cleanly when every row is already measured or
has no poster.

## Report (`kumiki.<site>-aggregate.v1`)

`report` is read-only and offline. It reads `stills/*.json`,
`videos/*.json`, both indexes (`stills-index.json`, `index.json`), and
`catalog.json`, and derives `generatedAt` from the records/indexes (falling back
to the catalogue) so repeated runs are byte-identical. Sections:

- provenance counts that **separate** video-measured, still-measured, and
  still-only rows, plus skipped/failed counts and skip reasons per index;
- the exact reproduce commands;
- per-video analysis and aggregates computed **only** over video-measured
  records;
- a table of measured stills with luma, saturation, hue, and edge density;
- distributions by taxonomy term (stills only);
- "Why there is no motion evidence" when no video records exist, naming the
  Vimeo/YouTube embeds (STASH) or pointing at the unrun `collect` lane
  (Directors' Library);
- explicit non-claims.

Still-only evidence never enters the motion, cut, luma, or saturation
aggregates. The aggregate carries `evidence` as `still-only`,
`video-measured`, or `video-measured+still-measured`.

## Exact commands

```bash
# Full slim catalogue (all pages; use --limit 5 for a smoke).
PYTHONPATH=src python scripts/research_wordpress_stills.py catalog \
  --site directorslibrary --out /tmp/dl-catalog.json

PYTHONPATH=src python scripts/research_wordpress_stills.py catalog \
  --site stash --out /tmp/stash-catalog.json

# YouTube video lane (Directors' Library only; STASH is refused row by row).
PYTHONPATH=src python scripts/research_wordpress_stills.py collect \
  --site directorslibrary --catalog /tmp/dl-catalog.json \
  --out-dir /tmp/dl-analysis --limit 250 --acknowledge-rights --jobs 1 \
  --yt-dlp /path/to/yt-dlp-venv/bin/yt-dlp

# One measured poster per remaining row (resume-safe, jobs 1..2).
PYTHONPATH=src python scripts/research_wordpress_stills.py stills \
  --site directorslibrary --catalog /tmp/dl-catalog.json \
  --out-dir /tmp/dl-analysis --resume --jobs 1

PYTHONPATH=src python scripts/research_wordpress_stills.py stills \
  --site stash --catalog /tmp/stash-catalog.json \
  --out-dir /tmp/stash-stills --resume --jobs 1

# Read-only report.
PYTHONPATH=src python scripts/research_wordpress_stills.py report \
  --site directorslibrary --out-dir /tmp/dl-analysis --top 50
```

## Output layout

```text
<out-dir>/
  catalog.json                 # kumiki.<site>-catalog.v1 (if placed here)
  stills-index.json            # kumiki.<site>-stills-index.v1
  stills/<id>-<slug>.json      # kumiki.<site>-still-evidence.v1
  index.json                   # kumiki.<site>-index.v1 (video lane)
  videos/<id>-<slug>.json      # kumiki.<site>-video-evidence.v1
  report.md
  aggregate.json               # kumiki.<site>-aggregate.v1
```

Indexes are written atomically and carry `site`, `catalogSha256`, counts,
summary rows, skip rows, and failure rows. The video index is deliberately
separate from `stills-index.json`.

## Explicit non-claims

- A published poster still is **not** a video frame. Single-image colour,
  luminance, histogram, hue, and edge-density numbers carry no motion, cut,
  pacing, timing, sequence, or edit-rhythm evidence.
- No style, aesthetic quality, mood, lighting, camera/lens, editorial intent,
  authorship, identity, or creative-origin inference is made from these
  numbers.
- The poster is prepared by the site/CMS, not necessarily by the work's author;
  on STASH it may be a gallery image rather than a video frame.
- A measured video record is a platform-encoded YouTube rendition, not the
  work's delivered master; only sampled source-PTS windows were measured.
- Vimeo embeds were never acquired or probed. No cookies, logins, tokens,
  player-API tricks, or DRM/PO-token/nsig circumvention were used. A provider
  refusal was never retried.
- Public availability is not a licence. `rightsStatus` remains
  `review-required`, and reuse needs its own review.
- Catalogue metadata is self-reported by the site and is not independently
  verified.
- Downloaded poster images and video media are never retained: only hashes and
  numbers remain.

## Verification

```bash
python -m py_compile scripts/research_wordpress_stills.py
PYTHONPATH=src python -m unittest tests.test_wordpress_stills tests.test_public_acquisition -q
```

The offline suite covers catalogue paging, the HTTP 400 terminal
`rest_post_invalid_page_number` response, `_fields` projection, term-name
resolution and caching, HTML-entity unescaping, the slim-row size bound, poster
host/query allowlisting, stills resume (bytes and mtime untouched), refresh,
atomic index writes, `--limit 0` termination, report determinism and still-only
labelling, and a missing-`og_image` row becoming an explicit skip rather than a
crash. It also covers YouTube embed extraction from an iframe and from JSON-LD,
the Vimeo-only and no-embed skips, the STASH whole-site refusal, the
`--acknowledge-rights` gate, video resume, refusal-versus-transient
classification, the video record shape/labels, and video/still/still-only report
separation and determinism.
