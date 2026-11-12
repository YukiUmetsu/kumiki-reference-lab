# Directors' Library video research

Ephemeral, source-hashed measurement of public video entries on
<https://directorslibrary.com/>. The adapter is
`scripts/research_directors_library.py`; it copies the skeleton of
`scripts/research_motiondesignawards.py` and reuses the generic engine in
`src/kumiki_reference_lab/acquisition/` without modifying it. The engine
contains no site names (enforced by a unit test).

## Source

- Catalog: `GET https://directorslibrary.com/wp-json/wp/v2/video` (WordPress REST,
  custom post type `video`), `per_page=100`, paged until `X-WP-TotalPages`.
- The REST `content` field carries no player markup, and `acf` is empty, so each
  entry's public page is fetched once to read its player embed. The embed is an
  `<iframe>` in the page template.
- Requests are serial, paced at least 1.5 s apart with up to 0.5 s of jitter,
  honour `Retry-After`, and stop the run after three consecutive 429/5xx or
  transport failures. No cookies, logins, or tokens are used.

## Classification

Each entry page is searched for `iframe`, `embed`, `object`, `video`, `source`,
and `og:video` references, and each reference is classified by its host:

| provider | rule | status |
| --- | --- | --- |
| `direct-mp4` | `.mp4` on the exact host `directorslibrary.com`, https, no query string | `pending-measure`, then `measured` or `failed` |
| `vimeo` | `vimeo.com` or a subdomain (player embed) | `unsupported-vimeo` (never attempted) |
| `youtube` | `youtube.com`, `youtube-nocookie.com`, `youtu.be` | `unsupported-youtube` (never attempted) |
| `other` | any other host, HLS, or a tokenised MP4 | `unsupported-other` |
| `no-video` | no media reference on the page | `no-video` |

Links such as a channel link in the page footer are not embeds and are ignored.
Provider priority is `direct-mp4` > `vimeo` > `youtube` > `other`.

## Outputs

- `research/analysis/directors-library/catalog.json`: every enumerated entry with
  its WordPress id, slug, title, date, link, provider, `embedTags`, and
  eligibility. An eligible entry also carries its allowlisted `videoUrl`.
- `research/analysis/directors-library/index.json`: one row per entry with a
  single status, plus `counts` and `providerCounts`.
- `research/analysis/directors-library/videos/<slug>.json`: one evidence record
  per measured video. Numeric fields and hashes only, with `mediaRetained: false`
  and `rightsStatus: review-required`.

## Download and delete lifecycle

Per eligible video, serially: `tempfile.TemporaryDirectory` → direct HTTPS GET
under the byte cap (`--max-file-bytes`) and duration cap
(`--max-duration-seconds`) → `source_metadata` → `measure_windows` → atomic
record write. The directory is removed in the context manager's exit, so no
media, frames, thumbnails, or audio survive. Three consecutive HTTP 429 or 5xx
download responses stop the run.

## Commands

```bash
PYTHONPATH=src python3 scripts/research_directors_library.py enumerate            # catalog + index
PYTHONPATH=src python3 scripts/research_directors_library.py measure --acknowledge-rights
PYTHONPATH=src python3 scripts/research_directors_library.py enumerate --limit 5 --out-dir "$SCRATCH"  # trial
```

`--limit` is for trial runs. Pass a scratch `--out-dir` so the real catalog is
not overwritten. Classification is cached in
`<out-dir>/.classify-cache.jsonl` while enumeration is incomplete, so an
interrupted run resumes without refetching pages. The cache is removed after a
full run.

## Results

Enumeration on 2026-11-11 (catalog retrieved `2026-11-12T01:09:21Z`):

| measure | count |
| --- | --- |
| entries enumerated (REST `X-WP-Total`) | 5,412 |
| `unsupported-vimeo` | 2,293 |
| `unsupported-youtube` | 3,089 |
| `no-video` | 30 |
| `unsupported-other` | 0 |
| eligible self-hosted MP4 | 0 |
| `measured` | 0 |
| `failed` | 0 |

- Every entry page returned HTTP 200. No classification failures occurred.
- The REST `content` field contained no `iframe`, `video`, or `embed` tag on any
  entry (`restContentMediaTagCount: 0`), so the player was read from each page.
- Four entries (ids 79531, 72513, 65198, 60117) embed both a Vimeo and a YouTube
  iframe. They are counted as `vimeo` by provider priority. Neither is
  self-hosted, so the measurement outcome is unaffected.
- The 30 `no-video` pages were re-checked for any `video`, `source`, `embed`, or
  `.mp4` / `.m3u8` / `.webm` / `.mov` reference and for any Vimeo or YouTube
  mention. None was found.
- Because no entry is eligible, `measure` downloaded nothing and no
  `videos/<slug>.json` record exists. No media was downloaded.
- Retry-level 429 or 5xx responses are absorbed by the client, which backs off and
  retries. None reached the failure stage, and the client does not log retries.

## Limits

- Numbers are sampled source-PTS windows of a self-hosted MP4 only. They are not
  a full-film review.
- Numeric display-RGB and cut-candidate proxies are not labels for camera,
  lighting, editing intent, style, quality, or authorship.
- Public availability is not a license. Rights basis is `user-declared-research-use`
  with `rightsStatus: review-required`.
- Vimeo and YouTube embeds are recorded as skip rows and are never downloaded.
