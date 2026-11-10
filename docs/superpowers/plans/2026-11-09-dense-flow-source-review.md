# Dense-flow source review implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Each task uses RED → GREEN checks.

**Goal:** Review dense-flow grid evidence on exact decoded source-PTS frames in an immutable offline gallery.

**Architecture:** A standalone `review-dense-flow` stage validates an existing `kumiki.dense-flow.v1` report and source identity, selects at most twelve frames, overlays only accepted vectors on corresponding endpoint frames, and atomically publishes PNG/HTML/JSON with a SHA-256 file inventory. No changes to dense-flow measurement or default `analyze` behavior.

**Tech Stack:** Python 3.11+, FFmpeg/FFprobe, standard-library HTML/SVG/PNG/JSON, unittest, optional jsonschema in tests.

**Spec:** `docs/dense-flow.md`; this plan adds the review workflow and does not claim camera, depth, identity, or artistic verification.

## Global Constraints

- Original source stream, SHA-256, timebase, sample ordinal and PTS must agree; never synthesize timestamps.
- Bound input JSON, frames, vectors and decoded image resolution; avoid AI, network and optional OpenCV dependencies in the reviewer.
- Preserve all existing commands, schemas, and cheap hosted CI unchanged.
- Review artifacts remain `unreviewed` / `not-performed`, and modified bundles must be rejected on repeat.

## Review Focus

- Forged pair PTS or inconsistent source-second fractions must fail before output.
- Forged out-of-frame vectors, invented cut-spanning vectors, and inconsistent accepted/rejected counts must fail.
- A missing or altered source/report/bundle must not silently produce verified-looking evidence.
- VFR frames must be decoded at their recorded PTS, not nominal FPS.
- Source filenames and untrusted report data must not inject markup into the offline gallery.

---

### Task 1: Evidence validator and frame selection

**Files:** Create `tests/test_dense_review.py`, `src/kumiki_reference_lab/analyzers/motion/dense_review.py`.

**Interfaces:** `validate_dense_review_report(report: dict) -> (width, height, samples, pairs)` and `select_dense_review_frames(samples, pairs, limit) -> list[int]`.

- [x] Write malformed, cut, PTS/rational, budget and selection tests; run `PYTHONPATH=src python -m unittest discover -s tests -p 'test_dense_review.py' -v` to see expected failure.
- [x] Implement bounded validation and deterministic selection with no measurement-side imports; rerun the focused tests green.

### Task 2: Immutable gallery and CLI

**Files:** Modify `tests/test_dense_review.py`, `tests/test_cli.py`, `src/kumiki_reference_lab/analyzers/motion/dense_review.py`, `src/kumiki_reference_lab/cli/app.py`, `src/kumiki_reference_lab/contracts/analysis.py`, `tests/test_schema.py`, `README.md`, `docs/dense-flow.md`; create `schemas/v1/dense-flow-review.schema.json`.

**Interfaces:** `build_dense_flow_review(source: Path, report_path: Path, output: Path, *, max_frames: int = 8, ffmpeg: str = 'ffmpeg', ffprobe: str = 'ffprobe') -> Path`; CLI `review-dense-flow SOURCE dense-flow.json --out DIR`.

- [x] Add FFV1 source/report, tampering/reuse, CLI and JSON schema tests; confirm they fail before implementation.
- [x] Implement source-verified bounded decode, SVG arrows, safe HTML, atomic immutable review and CLI wiring.
- [x] Run `PYTHONPATH=src python -m unittest discover -s tests -p 'test_dense_review.py' -v`; then the full `PYTHONPATH=src python -m unittest discover -s tests -q`, `python -m compileall -q src`, and `git diff --check`.
- [x] Review every changed file and the new end-to-end provenance boundary before opening a PR.
