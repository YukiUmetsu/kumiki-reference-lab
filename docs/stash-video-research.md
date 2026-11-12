# STASH public video research

Numeric, ephemeral measurement of public STASH (https://www.stashmedia.tv/)
post videos. The adapter is `scripts/research_stash.py`; it is the only STASH
component that touches the network. All mechanics come from
`src/kumiki_reference_lab/acquisition/`, as in `docs/public-video-acquisition.md`.

## Outputs

| path | content |
| --- | --- |
| `research/analysis/stash/catalog.json` | every enumerated post: WP id, slug, title, date, link, classified provider, eligibility |
| `research/analysis/stash/index.json` | one row per post with status, provider counts, catalog SHA-256 |
| `research/analysis/stash/videos/<slug>.json` | one numeric evidence record per measured video (none so far, see results) |

## Commands

```bash
PYTHONPATH=src python3 scripts/research_stash.py enumerate [--confirm-links]
PYTHONPATH=src python3 scripts/research_stash.py measure --acknowledge-rights [--limit N]
```

- `enumerate` reads `GET /wp-json/wp/v2/posts?per_page=100&page=N&_fields=id,link,title,date,content`
  sequentially, with at least 1.5 s between requests plus jitter. It honours
  `Retry-After` on 429 and retries 5xx with backoff. `--confirm-links` also reads
  each `none`/`gated` post's own page (see below). It is resumable.
- `measure` handles only rows marked eligible. It runs one video at a time with
  the same delay, and `--resume` (default) skips existing records. `--limit N`
  is for trial runs.
- `--acknowledge-rights` is required. Rights basis is `user-declared-research-use`
  and `rightsStatus` is always `review-required`.

## Classification

Per post, markup is checked in this precedence order:

1. Any Vimeo host (`player.vimeo.com`, `vimeo.com`, or `vimeocdn.com`, including
   signed playback URLs) gives `vimeo`, which is `unsupported-vimeo`.
2. Any YouTube host gives `youtube`, which is `unsupported-youtube`.
3. A direct `.mp4` on the exact host `www.stashmedia.tv`, with no query or
   fragment, gives `direct-mp4`, which is eligible. Other self-hosted media
   (`.webm`, `.m3u8`, `.mov`, or a non-allowlisted or `http` host) gives
   `self-hosted-other`, which is `unsupported-host`.
4. A subscribe, login, trial, or membership link on the site without an embed
   gives `gated`, which is `unsupported-gated`. This is a marker only; the page
   is not behind a verified paywall check.
5. Anything else gives `none`, which is `no-video`.

Vimeo and YouTube URLs are never requested. Markup that the URL parser rejects is ignored.

### Why link pages are read

The REST `content.rendered` field does not include every post's main player.
Some posts render it in a `postvid_single` container, which REST does not
expose (`acf` is empty). A sample of 15 link pages found a Vimeo embed in that
container for 12 posts that REST had classified as `none`. `--confirm-links`
therefore reads only that container on each `none` and `gated` post's own page.
It never reads site navigation or related-post regions, and it never requests
Vimeo or YouTube media.

## Politeness and limits

- One request at a time. At least 1.5 s plus jitter between requests.
- Repeated 429 or 5xx responses trip a breaker after 3 consecutive attempts. The
  run stops and can be resumed.
- No login, cookies, trial, or subscription. No `vimeocdn.com` URLs are used.
- Media is downloaded to a `TemporaryDirectory`, measured, and deleted in a
  `finally`. `acquisition.mediaRetained` is always `false`.
- Measurements are sampled source-PTS windows only, not full-film review. They
  are numeric proxies, not style, quality, or authorship claims.

## Results

Run on 2026-11-11 against the live site, one request at a time.

| step | outcome |
| --- | --- |
| REST enumeration | 54 pages, 5,399 posts, no 429 or 5xx failure surfaced |
| REST-only classification | vimeo 1060, youtube 257, gated 39, self-hosted-other 1, none 4042 |
| link-page confirmation (`none`/`gated`, 4,081 pages, 0 errors) | 3,684 pages had a main video block; final provider vimeo 3880, youtube 988, none 530, self-hosted-other 1 |
| eligible direct MP4 on the exact host | **0** |
| measured / failed | **0 / 0**; no media was downloaded |

Final `index.json` `statusCounts`: `unsupported-vimeo` 3880,
`unsupported-youtube` 988, `unsupported-host` 1, `no-video` 530. The 39
`gated`-flagged posts all have a Vimeo main block, so the subscription marker
does not appear as a final provider.

The confirmation pass was interrupted once at the background time limit and
resumed from its checkpoint. Progress is checkpointed every 25 posts, so a
re-run continues without re-fetching confirmed posts.
