# Link a What Ships video to an authorized local source file

The [complete 2,861-video catalog](whatships-full-coverage.md) now has a **private media-binding ledger**. This is the step between *metadata discovery* and *actual source-frame analysis*.

The binding stage does not download a What Ships video, inspect an X stream, declare that the operator owns a clip, or automatically identify the pictured launch. It requires an **explicit operator claim** that a specific local file corresponds to the exact `whatships:slug` entry and may lawfully be analyzed. It probes the local video with FFprobe, records its exact bytes SHA-256 and original stream timebase, and preserves a private absolute filesystem path for later analysis.

## One-time registration of each authorized video

```bash
# The file must already be locally available and you must have permission
# for the intended private research use.
PYTHONPATH=src python -m kumiki_reference_lab whatships-media bind \
  whatships:paper-mono-code \
  "$HOME/Videos/authorized/paper-mono-code.mp4" \
  --snapshot research/whatships-index-2026-11-10.json \
  --rights-basis written-permission \
  --rights-note "Original creator granted me permission to analyze this clip locally." \
  --identity-note "Compared local clip frames to the exact source watch page and original creator post." \
  --acknowledge-rights \
  --out "$HOME/whatships-private/bindings-001"

# Append a second source *without overwriting* the prior ledger.
PYTHONPATH=src python -m kumiki_reference_lab whatships-media bind \
  whatships:another-video \
  "$HOME/Videos/authorized/another-video.mp4" \
  --previous "$HOME/whatships-private/bindings-001/media-bindings.json" \
  --rights-basis permissive-license \
  --rights-note "License terms expressly permit this private analysis." \
  --identity-note "Creator, original post and frames match the indexed video." \
  --acknowledge-rights \
  --out "$HOME/whatships-private/bindings-002"
```

Permitted rights-basis declarations: `own-original-work`, `written-permission`, `permissive-license`, or `other-lawful-authorization`. The tool does not make a legal determination. It also does **not** compare the remote hosted video visually or certify the source match; the identity note is a self-declared assertion.

The binding command rejects unknown slugs, duplicate catalog IDs, mapping identical media bytes to unrelated entries, symlinked video files, remote watch-page URLs, blank/short notes, a missing rights acknowledgement and source files that change during probing. Source SHA, stream index and rational timebase are recorded for downstream verification. Each output directory is new and immutable.

## Audit and queue safely

```bash
# Fast count, without rereading all video files.
PYTHONPATH=src python -m kumiki_reference_lab whatships-media report \
  "$HOME/whatships-private/bindings-002/media-bindings.json"

# Rehash all files and fail if a video was modified or moved.
PYTHONPATH=src python -m kumiki_reference_lab whatships-media report \
  "$HOME/whatships-private/bindings-002/media-bindings.json" --verify-files

# List SHA-verified local analysis candidates, without printing local paths.
PYTHONPATH=src python -m kumiki_reference_lab whatships-media queue \
  "$HOME/whatships-private/bindings-002/media-bindings.json" --limit 20
```

The `coverage.json`, `report`, and `queue` results deliberately **omit local paths**. Only the private `media-bindings.json` stores full paths. It also records exact indexed source/watch URL, snapshot metadata, a user-declared rights basis, and source identity notes. Even if all catalog entries become bound, that is still **not proof that any frames have been processed or reviewed**.

**Privacy:** keep `media-bindings.json`, original footage, review galleries and any individual identities outside the Git repository and public file-sharing. The ledger contains absolute file paths and private explanatory notes. Do not attach or commit it publicly.

## Boundary to the next stage

A successfully registered clip is **eligible for local analysis** only after the bytes and declared source relationship are checked. The next worker should consume the private ledger and run `character-study-local` or `character-study-batch` under explicit bounded budgets, preserving provenance and review status. It must not use the site watch URL as an FFmpeg input, silently upload footage, or treat a completed model run as a human-reviewed cinematic measurement.

This PR's offline tests mock FFprobe for small synthetic byte files, test SHA changes, exact catalog IDs and absence of path leakage from reports. **It has not verified the user's ownership of any What Ships video or actually bound real third-party footage.**
