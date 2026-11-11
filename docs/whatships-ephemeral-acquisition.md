# Optional ephemeral acquisition of original What Ships X videos

Many What Ships watch pages link to an original X status containing an embedded video. That link is **not a video file** and public availability is not guaranteed. For supported public posts, `whatships-acquire-measure` can download one short-lived video into a private temporary folder, analyze original source frames with FFmpeg, save the numeric research evidence in `research/analysis/whatships/<slug>.json`, and delete all downloaded media and private binding files on completion or failure.

This workflow is opt-in. **A public video is not automatically licensed for download or research reuse.** Only use it where you have a concrete lawful basis. You must declare that basis, explain it, and attest that the original X post actually matches the What Ships watch page. Neither the CLI nor its generated evidence claims to verify copyright authorization or video identity independently.

## Requirements

Install FFmpeg and a current [yt-dlp](https://github.com/yt-dlp/yt-dlp) locally. It is a one-time tool installation, not a paid subscription. No credentials, browser cookies, login sessions, DRM bypass or service APIs are used. Original X posts may fail extraction when public guest access changes; these are skipped or reported as errors rather than working around site access restrictions.

Only enriched What Ships catalog entries with a verified-shaped `https://x.com/<handle>/status/<number>` origin are eligible. Entries with only index metadata need a legitimate original-post link before acquisition. The downloader **never accepts an arbitrary untrusted URL** as its source.

## Usage

```bash
PYTHONPATH=src python -m kumiki_reference_lab whatships-acquire-measure \
  whatships:paper-mono-code \
  --rights-basis written-permission \
  --rights-note "The creator granted explicit permission for this local video study." \
  --identity-note "I verified this exact original post matches the selected What Ships clip." \
  --acknowledge-rights \
  --window-seconds 10 --window-count 4 --max-samples 12

PYTHONPATH=src python -m kumiki_reference_lab whatships-all validate-analysis
git diff -- research/analysis/whatships
git add research/analysis/whatships
git commit -m "data: add source-PTS observations from authorized original video"
```

The command uses the catalog snapshot's exact X URL and `yt-dlp` with ignored local configuration and disabled plugins, no cookies, a single-post/single-video restriction, a 150 MB source cap, bounded retries, and a maximum 300-second download timeout. It does not bypass logins or paywalls. The local source is SHA256-hashed and FFprobe-stream/timebase checked before analysis. The same safe additive window merge is used as `whatships-measure --fill-gaps`, so repeat invocations can extend observations without overwriting earlier windows.

**Only sanitized, source-linked numeric facts are retained in Git:** original PTS frame timings, image brightness/color, candidate cuts, frame-change proxies and source hash. No downloaded video, thumbnail, soundtrack, dialogue, private permission text, cookie, temporary path or real-person identity is committed. Temporary files are deleted on success or errors.

## Verification and limitations

```bash
PYTHONPATH=src python -m unittest tests.test_whatships_ephemeral_acquire -v
```

Tests use an original locally generated red-to-blue clip and the real FFprobe/FFmpeg source-frame analyzer. The network-downloader step is mocked to verify its public-URL allowlist, security flags, exact-source handoff, failure handling and cleanup. **The tests do not claim to have analyzed any actual third-party What Ships video**, nor do they establish that a specific X post can currently be downloaded without authentication.

Measured frames inside time windows remain sparse. Numeric color and image changes do not establish scene lighting rigs, actual camera/lens trajectories, animation methods, identities, or full-film human review. You can run full analysis only on lawfully accessible originals; avoid unsupported video formats and original posts that have multiple or ambiguous attachments.
