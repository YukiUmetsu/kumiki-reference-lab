# Motionographer video research (numeric, ephemeral)

Site adapter: `scripts/research_motionographer.py`. It is built on the generic
`kumiki_reference_lab.acquisition` engine (see `docs/public-video-acquisition.md`).
Evidence lives in `research/analysis/motionographer/`. Media is never kept.

## What is measured

Only direct HTTPS MP4 files that the public post page serves from the exact
allowlisted CDN host (`s35726.pcdn.co`). Each measured item gets one evidence
record with source-PTS windows, numeric display-RGB and cut-candidate proxies,
the SHA-256 of the downloaded source, and `mediaRetained: false`.

Everything else is recorded as a skip row in `index.json` and never attempted:

| status | meaning |
| --- | --- |
| `unsupported-vimeo` | Vimeo player embed (`player.vimeo.com/video/<id>`). Never attempted. |
| `unsupported-youtube` | YouTube embed. Never attempted. |
| `unsupported-other-embed` | other iframe embeds, not measured |
| `unsupported-format` | self-hosted `.mov`, `.webm`, `.m4v`: the adapter is MP4-only |
| `unsupported-url-form` | `http://` (not HTTPS) MP4 URLs; never upgraded |
| `unsupported-host-not-allowlisted` | MP4 on a host outside the exact allowlist |
| `unsupported-query-string` | MP4 with a query other than the `?_=N` cache buster |
| `unsupported-not-served-on-page` | MP4 in the REST content that the public page does not serve |
| `no-video` | post with no media item |
| `measured` / `failed` / `pending` | self-hosted MP4 outcomes |

## Enumeration

1. `GET /wp-json/wp/v2/posts?per_page=100&page=N&_fields=id,slug,link,title,date,content`,
   one page at a time with at least 1.5 s between requests plus jitter. `429` and
   `5xx` responses honour `Retry-After` with bounded backoff. Repeated throttling
   stops the run and reports, with no retry storm.
2. Each post's `content.rendered` is classified per media URL.
3. Confirmation. The REST content can carry origin URLs such as
   `motionographer.com/wp-content/uploads/...mp4`, while the public post page
   serves the same file path from `s35726.pcdn.co`. Posts with an MP4 candidate
   (58 of them) have their public page fetched once. A REST candidate is
   re-classified from the page URL when the page serves the same
   `/wp-content/uploads/` path. An MP4 that the page does not serve is demoted
   to `unsupported-not-served-on-page`.
4. Duplicates are removed on the canonical URL, after the `?_=N` cache-buster
   is dropped (the buster selects the same bytes). Media IDs are renumbered.

Host decisions, recorded so they are reproducible:

- `s35726.pcdn.co` is the only allowlisted host. Public pages serve every
  eligible file from it. It is the CDN host of the site's own uploads.
- `motionograph.wpengine.com` (WP Engine origin alias) is not allowlisted. It is
  a hosting alias, not the public domain, and it carries 17 MP4 candidates.
  These are left as `unsupported-host-not-allowlisted`.
- `motionographer.com` itself is not allowlisted. The one REST-only item on it
  is not served by its public page, so it is `unsupported-not-served-on-page`.
- Third-party MP4 hosts (other studios' sites, `videos.files.wordpress.com`) are
  not site-owned and are not allowlisted.

## Measurement

`measure` processes eligible items strictly sequentially (jobs=1), one at a time
with the engine's politeness delay (1.5 s plus jitter). Each download lands in a
`TemporaryDirectory` that is removed on exit, including on failure. Previously
failed items are skipped unless `--retry-failed` is passed, so a broken item is
not re-downloaded on every batch. `--limit N` selects the first N eligible items
in catalog order, and `--resume` skips items with an existing record.

## Commands

```bash
PYTHONPATH=src python3 scripts/research_motionographer.py enumerate --out-dir research/analysis/motionographer
PYTHONPATH=src python3 scripts/research_motionographer.py measure --out-dir research/analysis/motionographer --limit 5 --acknowledge-rights
PYTHONPATH=src python3 -m unittest tests.test_research_motionographer
```

`enumerate --limit N` is a trial run that fetches at most N pages.

## Limits

- Sampled source-PTS windows only, not full-film review.
- Numeric display-RGB and cut-candidate proxies are not camera, lens, lighting,
  editing-intent, style, quality, or authorship labels.
- `rightsStatus` stays `review-required` (basis `user-declared-research-use`).
- Catalog metadata is self-reported by the publisher site.
