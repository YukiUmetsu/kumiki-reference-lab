# Reference site viability for measured video evidence

Which public motion-design / advertising reference libraries can actually be
measured by this lab's acquisition engine, and why the others cannot.

Verdicts below come from bounded, read-only reconnaissance (a handful of
requests per site, real browser user agent, no logins, no cookies, no
paywall or player-token workarounds). They are recorded here so the same
ground is not re-explored every time a new site is proposed.

## Summary

| site | catalog | video bytes | verdict |
| --- | --- | --- | --- |
| Motion Design Awards | public GraphQL, 1,919 projects | Cloudflare Stream HLS + direct MP4 on 501 | **video lane shipped** (`scripts/research_motiondesignawards.py`) |
| shots.net | public JSON search, 40,908 clips | CloudFront 720p renderings, S3/CloudFront signed originals | **video lane shipped** (`scripts/research_shots.py`) |
| AICP Awards (`aicpawards.com`) | GraphQL POST, 2,715 entries | signed Vimeo HLS on `*.vimeocdn.com` | **video lane shipped** (`scripts/research_aicp.py`) |
| Promonews | Elasticsearch POST, 17,805 videos | YouTube 19/20, Vimeo 1/20 — nothing fetchable | catalog + poster stills (`scripts/research_promonews.py`) |
| Directors' Library | WordPress REST, 5,412 videos | Vimeo / YouTube iframes only | catalog + poster stills (`scripts/research_wordpress_stills.py`) |
| STASH | WordPress REST, 5,399 posts | Vimeo iframes only; player API `403 x-banned-ip` | catalog + poster stills (`scripts/research_wordpress_stills.py`) |
| Ads of the World | Rails HTML, ~30,360 film campaigns | ~25 % have direct MP4 on `video.adsoftheworld.com` | **blocked by robots**: the only pagination form is `Disallow: /*?page=`, and the robots-clean `/page/N` path 404s |
| Clio Awards | React SPA over WordPress `winners-api/v1` | none observed | **blocked**: every dynamic route returns a byte-identical 403 from WP Engine/Cloudflare; only stale cache hits are 200 |
| Little Black Book | unknown (challenge) | unknown | **blocked**: Cloudflare managed challenge on both `/work` and `sitemap.xml`; `/api/` disallowed by robots |
| Vimeo Staff Picks | Vimeo | Vimeo | **blocked by design**: player `/config` needs a logged-in web client; session/cookie replay is out of policy |
| FrameThrower | bearer-token API, credit metered | no public bytes | **out of scope**: terms prohibit scraping, mirroring, bulk download and automated pipelines |
| FilmDraft | public page, 52 of 2,861 tiles visible | YouTube only | narrow stills-only curiosity; no full catalog endpoint and nothing to measure beyond a poster |

## What "video lane" requires

1. A **public, unauthenticated catalog endpoint** that enumerates the whole
   library without HTML pagination (query-string pagination is frequently
   robots-disallowed, and HTML paging is quadratic on cumulative feeds).
2. A **media URL that resolves without cookies or a player token**, on a host
   that can be pinned in an exact-host allowlist. Signed CDN URLs are fine:
   `allow_query=True` exists for exactly that case, and redirect targets are
   re-validated under the same allowlist.
3. Media that **tolerates byte ranges and a plain HTTP client**. Vimeo and
   YouTube embeds fail this: their renditions are reachable only through a
   player that requires a logged-in web client or a signature exchange, which
   this repo deliberately does not implement.

A site failing (2) but passing (1) still yields honest evidence: a complete
catalog plus one measured published poster per item, with records that state
`isSourceVideoFrame: false` and deny any motion, cut, timing, sequence or
aesthetic claim. That is what the stills lanes deliver for Promonews,
Directors' Library and STASH, and for the 1,418 Vimeo-hosted Motion Design
Awards entries.

## Rules applied during recon

- No logins, cookies, paywall or DRM bypass, and no player-token harvesting.
- Media bytes were never retained; size and codec facts came from `HEAD` or
  `Range: 0-1048575` probes.
- Politeness: a handful of requests per site, human-paced, stopping at the
  first hard block instead of retrying.
- A 403 that appears on several dynamic routes while cached routes return 200
  is a hard deny, not a transient fault worth retrying.
- Respecting `robots.txt` decides the case even when the bytes are reachable —
  Ads of the World is the example.
