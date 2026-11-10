# Generalized Video Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Browse YouTube and What Ships research references through one offline, provenance-aware command.

**Architecture:** Normalize existing YouTube cohort objects and a bounded What Ships snapshot into one provider-qualified in-memory record shape. Keep media inspection local-file-only. A separate CLI exposes validation, search, list and watch-page lookup.

**Tech Stack:** Python 3.11 standard library, `unittest`, JSON.

**Spec:** `docs/superpowers/specs/2026-11-10-generalized-video-sources-design.md`

## Global Constraints

- No media downloading, streaming to FFmpeg, frame extraction from a public website, or invented visual claims.
- Existing `video-references` schema and CLI behavior remain unchanged.
- What Ships official snapshot only; unknown fields stay null; reject malformed and unsafe input.

## Review Focus

- Reject malicious or malformed source URLs, even in otherwise valid-looking metadata.
- Reject duplicate slugs and duplicate JSON keys rather than silently overriding.
- Keep large external snapshots bounded and reject symlinks.
- Missing view evidence must not be ranked as confirmed zero-view films.
- Do not infer an original X post URL from an index-only item.

---

### Task 1: Provider-neutral reference normalization

**Files:**
- Create: `src/kumiki_reference_lab/catalog/video_sources.py`
- Create: `tests/test_video_sources.py`

**Interfaces:**
- `load_source_references(youtube_root: Path, whatships_path: Path) -> dict`: validated combined collection.
- `search_source_references(collection: dict, query: str = "", *, provider: str = "all", min_views: int = 0, limit: int = 20) -> list[dict]`: offline lookup.
- `get_source_reference(collection: dict, identity: str) -> dict`: exact `provider:id` lookup.

- [x] Write tests for known YouTube normalization, complete/partial What Ships metadata, safety constraints, duplicates, searched fields, unknown view sorting, and exact identities.
- [x] Run the focused test discovery and verify it fails because the module is absent.
- [x] Implement the adapter and validation without changing the YouTube schema.
- [x] Re-run the focused tests; all pass.
- [x] Include module and tests in the reviewed feature commit.

### Task 2: CLI and documented research snapshot

**Files:**
- Modify: `src/kumiki_reference_lab/cli/app.py`
- Modify: `README.md`
- Create: `docs/whatships-video-sources.md`
- Create: `research/whatships-motion-2026-11-10.json`
- Modify: `tests/test_video_sources.py`

**Interfaces:**
- CLI `video-sources validate|list|search|show`, `--youtube-root`, `--whatships`, `--provider`, `--min-views`, `--limit` and identity for `show`.
- Default What Ships snapshot is the complete 2,861-entry indexed corpus with 419 detailed, obtained from the official index and read-only API on November 10; a separate 69-entry Motion cohort is also included.

- [x] Write CLI tests asserting provider-qualified results, valid watch/original URLs, empty matches, invalid filters and errors.
- [x] Run focused tests and verify failures caused by the absent CLI.
- [x] Wire CLI to the adapter and document usage and responsible visual-review workflow.
- [x] Include the full 2,861-entry official index snapshot and mechanically selected 69 Motion entries; no media files.
- [x] Re-run focused tests and existing YouTube reference regression tests; all pass.
- [x] Run the full test suite and inspect the diff and data provenance before committing.
