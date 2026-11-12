# WordPress poster-stills research (Directors' Library, STASH)

`scripts/research_wordpress_stills.py` is one config-driven adapter for two
WordPress sites. It writes a full slim catalogue and measures **one published
poster still** per item. Each still is downloaded once, decoded once at 160x90
RGB, measured numerically, and deleted immediately. Only numeric evidence,
hashes, and catalogue metadata are committed.

This adapter is **still-only by design**. Every video on both sites is a
third-party Vimeo or YouTube embed. Neither site publishes a progressive
MP4/HLS file, and Vimeo's player and `/config` endpoints return 401/403 to
scripted clients. Per repository policy those providers are recorded as
unsupported and are never attempted: no cookies, no auth, no player API, no
DRM circumvention. There is no video lane.

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

## Why video measurement is impossible

```text
<video> -> player.vimeo.com/video/<id>  or  www.youtube.com/embed/<id>
```

- No progressive MP4 or HLS URL is published on either site.
- Vimeo's `/config` and player pages return 401/403 to scripted clients.
- No direct CDN file exists.

The adapter therefore sets `videoDownloadable: false` and a reason on every
row, and the report includes an explicit "Why there is no motion evidence"
section naming Vimeo/YouTube. STASH is a magazine feed: many posts are image
galleries rather than videos, so the per-row `provider` field is only a
downloadability label (`unsupported-embed` or `null`), not a claim that every
post contains a video. No video-coverage claim is made.

Per-row provider logic:

- Directors' Library is a WordPress `video` post type, so its rows carry
  `provider: "unsupported-embed"`.
- STASH rows carry `"unsupported-embed"` only when Yoast exposes an
  `og_video` or `og_type` starting with `video`; otherwise `null`.

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
`stills-index.json`, and `catalog.json`, and derives `generatedAt` from the
records (falling back to the catalogue) so repeated runs are byte-identical.
Sections:

- provenance counts: catalogue items, video-measured (always 0), stills
  measured, skipped, failed, items without a poster, unreadable records;
- the exact reproduce commands;
- a table of measured stills with luma, saturation, hue, and edge density;
- distributions by taxonomy term;
- "Why there is no motion evidence", naming the Vimeo/YouTube embeds;
- explicit non-claims.

## Exact commands

```bash
# Full slim catalogue (all pages; use --limit 5 for a smoke).
PYTHONPATH=src python scripts/research_wordpress_stills.py catalog \
  --site directorslibrary --out /tmp/dl-catalog.json

PYTHONPATH=src python scripts/research_wordpress_stills.py catalog \
  --site stash --out /tmp/stash-catalog.json

# One measured poster per remaining row (resume-safe, jobs 1..2).
PYTHONPATH=src python scripts/research_wordpress_stills.py stills \
  --site directorslibrary --catalog /tmp/dl-catalog.json \
  --out-dir /tmp/dl-stills --resume --jobs 1

PYTHONPATH=src python scripts/research_wordpress_stills.py stills \
  --site stash --catalog /tmp/stash-catalog.json \
  --out-dir /tmp/stash-stills --resume --jobs 1

# Read-only report.
PYTHONPATH=src python scripts/research_wordpress_stills.py report \
  --site directorslibrary --out-dir /tmp/dl-stills --top 50
```

## Output layout

```text
<out-dir>/
  catalog.json                 # kumiki.<site>-catalog.v1 (if placed here)
  stills-index.json            # kumiki.<site>-stills-index.v1
  stills/<id>-<slug>.json      # kumiki.<site>-still-evidence.v1
  report.md
  aggregate.json               # kumiki.<site>-aggregate.v1
```

Indexes are written atomically and carry `site`, `catalogSha256`, counts,
summary rows, skip rows, and failure rows.

## Explicit non-claims

- A published poster still is **not** a video frame. Single-image colour,
  luminance, histogram, hue, and edge-density numbers carry no motion, cut,
  pacing, timing, sequence, or edit-rhythm evidence.
- No style, aesthetic quality, mood, lighting, camera/lens, editorial intent,
  authorship, identity, or creative-origin inference is made from these
  numbers.
- The poster is prepared by the site/CMS, not necessarily by the work's author;
  on STASH it may be a gallery image rather than a video frame.
- Public availability is not a licence. `rightsStatus` remains
  `review-required`, and reuse needs its own review.
- Vimeo/YouTube embeds were never acquired or probed. No cookies, logins,
  tokens, player-API tricks, or DRM circumvention were used.
- Catalogue metadata is self-reported by the site and is not independently
  verified.
- Downloaded poster images are never retained: only hashes and numbers remain.

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
crash.
