# Public video acquisition and numeric measurement (generic)

`kumiki_reference_lab.acquisition` is the reusable, site-agnostic engine for
"enumerate public videos on a site, acquire them ephemerally, measure them
numerically, keep the evidence and delete the bytes" work.

It contains no knowledge of any particular website: no endpoints, no hostnames,
no provider vocabulary, no schema strings. Those belong to a *site adapter* — a
small script that enumerates candidates and supplies policy. The reference
adapter is `scripts/research_motiondesignawards.py`
(see `docs/motiondesignawards-video-research.md`).

## Safety contract

Enforced once, for every caller:

- HTTPS only, host allowlist passed by the caller. Entries are exact hosts
  (`media.example`), explicit subdomain suffixes (`.cdn.example`), or the
  wildcard `"*"`, which admits any public DNS name. The wildcard is the current
  project-wide policy for research adapters. It relaxes only the host check. No
  credentials, custom ports, fragments, IP literals, loopback or single-label
  names, or implicit subdomains. Query strings are refused by default; a
  caller can opt in per URL-operation with `allow_query=True` for signed,
  cookie-free CDN URLs (see below). Every redirect is re-validated with the
  same allowlist and the same `allow_query` setting.
- Byte- and duration-capped retrieval. Media lands only in a directory the
  caller owns.
- No cookies, logins, tokens, DRM circumvention, or access-control bypass. A
  signed URL is not a token login: it is a public, cryptographically scoped CDN
  grant. Public availability is not a licence: the caller supplies its own
  rights basis and attestation text, and records keep
  `rightsStatus: review-required`.
- The package never deletes your files. Ephemeral deletion is the caller's job
  (`TemporaryDirectory` around the whole acquire → measure → record cycle, so
  partial downloads are removed on failure too).
- Only numeric measurements, hashes and metadata leave the package. Builders
  return neutral payloads; the caller supplies schema versions, limits, and
  subject identity fields.

## API map

| module | what it gives you |
| --- | --- |
| `media` | `allowlisted_url` / `allowlisted_video_url` / `allowlisted_image_url` (all accept `allow_query`), `fetch_bytes`, `fetch_text`, `download_http`, `plan_hls_download`, `download_media` (HLS stream-copy remux or direct GET), `media_target`, `image_target`, `check_downloaded` |
| `probe` | `run_ffprobe_json` (retry/backoff), `remote_source_metadata`, `ranged_source_metadata` (bounded `Range` fallback for flaky hosts), `source_metadata`, `probe_image_dimensions`, `metadata_from_probe`, `finite_float` / `as_int` / `as_text` |
| `windows` | `plan_windows`, `measure_windows`, `summarize_probes`, `build_video_evidence` |
| `stills` | `measure_still`, `compute_still_metrics`, `dominant_hue_family`, `decode_still_rgb`, `infer_decoded_dimensions`, `still_image_format`, `build_still_evidence` |
| `store` | `write_json_atomic`, `safe_slug`, `resume_matches`, `build_index`, `utc_now` |
| `runner` | `run_batch` (sequential or pooled, jittered politeness delay, resume skip, per-item failure isolation, atomic index refresh), `safe_error` |

Provider constants: `HLS`, `DIRECT`; method labels: `METHOD_HLS_REMUX`,
`METHOD_HTTP_DOWNLOAD`.

### Signed URLs: `allow_query`

Generic scraping policy refuses a query string because it often carries
session state or an opaque token that the engine must not replay. Some public
CDNs instead hand out *signed* URLs — CloudFront `AWSAccessKeyId` / `Expires` /
`Signature`, or an origin such as `app.extremereach.com/...?profile=…&useCDN=true`
that 302s to one. Those URLs are cookie-free and cryptographically scoped, so
they are safe to fetch when the caller explicitly opts in:

```python
download_media(url, DIRECT, directory, allowed_hosts=MEDIA_HOSTS,
               max_bytes=..., allow_query=True)
```

The opt-in is per call and defaults to `False`, so existing callers keep the
strict policy byte-for-byte. It is threaded through `allowlisted_url`,
`allowlisted_video_url`, `allowlisted_image_url`, `fetch_bytes`, `fetch_text`,
`download_http`, `plan_hls_download` (master, variant, and audio URLs),
`ffprobe_remote_json`, `remote_source_metadata`, `ranged_source_metadata`, and
`download_media`.

What does **not** change:

- The scheme must still be `https`.
- The host must still match the caller's allowlist exactly, including the
  leading-dot subdomain rule.
- Credentials, custom ports, IP literals, loopback names, leading/trailing-dot
  host tricks, and fragments are still refused.
- Redirects are re-validated against the same allowlist **and** the same
  `allow_query` setting, and the redirect target's query string is preserved.
- A signed URL is never cached across calls; it expires. Error text is
  redacted by `safe_error`, which strips `Signature=`, `AWSAccessKeyId=`, and
  related signing values in addition to full URLs.

Enable it for one adapter's media allowlist only when that host actually
requires signed delivery. Keep it off for poster/image lanes unless a signed
poster is the only published URL.

## Adapter recipe

A new site needs only this:

1. **Enumerate candidates** into neutral dicts with a stable `id`, a page URL, an
   optional media URL, and whatever site metadata you want in the record.
2. **Declare**: media/image host allowlists, delivery mode per candidate
   (`HLS` or `DIRECT`), schema strings, evidence-status strings, `limits` text,
   rights basis/note, and the identity field `--resume` matches on.
3. **Write `run_one(candidate)`** as
   `TemporaryDirectory` → `allowlisted_video_url` (`allow_query=True` only when
   the host requires signed URLs) → `remote_source_metadata` (reject
   duration/size before download) → `download_media(...,
   allow_query=...)` → `source_metadata` → `measure_windows` →
   `build_video_evidence` (+ your identity fields and schema) →
   `write_json_atomic`. Deletion happens in the `finally` of the context
   manager.
4. **Drive the batch** with `run_batch(items, run_one=..., index_path=...,
   build_index=..., summary_row=..., skip_row=..., jobs=..., delay_seconds=...)`.

Prefer a research script (as above) over a new CLI command unless the workflow is
generically useful without a site.

## Rules of evidence

- Report measured quantities only: source PTS, frame counts, cut candidates,
  display-RGB luma/saturation proxies, inter-frame deltas, still-image metrics.
- Never claim style, intent, authorship, quality, or identity from numbers.
- A single published still is **not** a video frame; mark it
  `isSourceVideoFrame: false` and deny motion/cut/timing evidence in `limits`.
- Unsupported providers (e.g. a host that requires login) get an explicit
  `unsupported-*` skip row. Do not attempt a bypass.

## Verification

```bash
PYTHONPATH=src python -m unittest tests.test_public_acquisition -v
grep -rin "motiondesignawards\|keyfram\|cloudflare\|vimeo\|yt-dlp" src/kumiki_reference_lab/acquisition/   # must be empty
PYTHONPATH=src python -c "import kumiki_reference_lab.acquisition as a; print(sorted(a.__all__))"
```

## Known gaps (deliberate)

- No generic HTTP POST/JSON client: catalogue APIs with bespoke auth-free
  GraphQL stay in the site adapter.
- `run_batch`'s progress callback receives no success payload, so adapters keep a
  slug → detail map for operator log lines.
- `build_index` does not seed already-measured rows; adapters pass retained rows
  through their own `build_index` closure.
- `safe_error` redacts only the package's own scratch prefixes; adapters add
  their own patterns via `redact=`.
