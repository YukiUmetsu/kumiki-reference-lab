# Cinematic Techniques Catalog: authoring and promotion

> **Status:** Five original research candidates; these are implementation recipes, not claims about how an existing studio made a specific video. No technique is yet verified against a reference render.

## Command contract

Run from this repository root, or pass `--root /path/to/catalog/entries` explicitly:

```bash
PYTHONPATH=src python -m kumiki_reference_lab catalog validate
PYTHONPATH=src python -m kumiki_reference_lab catalog search "explain cause and effect"
PYTHONPATH=src python -m kumiki_reference_lab catalog search "reveal material shape" --limit 5
PYTHONPATH=src python -m kumiki_reference_lab catalog index --out ./runs/catalog-r001
```

The canonical entries live in `catalog/entries/<category>/<slug>.json` and must have `id: <category>.<slug>`. Valid categories: `story`, `attention`, `camera`, `lighting`, `motion`, `editing`, `materials`, `typography`, `sound`. Files are sorted by stable ID; unknown fields, invalid numeric ranges, beat gaps/overlaps, duplicates and malformed JSON fail validation. A file larger than 256 KiB or a symlink is rejected.

`catalog index` writes versioned `catalog-index.json`: only ID, revision, category, purpose, name, summary, implementation state, linked Kumiki registry ID and hash of the original entry. This is a metadata interchange artifact. **It does not execute a treatment, download media, copy image frames, or make Kumiki dependent on this repository.** The index is immutable and idempotent within one output directory. To publish a changed index, use a new output directory and review the diff.

## Why each field exists

| Group | Meaning | Do not claim |
| --- | --- | --- |
| `intent` | Audience question, story goals, perceptual result, use/avoid criteria | That the audience actually understood without review |
| `mechanism` | Visible cues and plausible explanations | Exact source light position, camera intrinsics or hidden keyframes |
| `recipe.beats` | Original normalized [0, 1] art-direction progression with exact adjacent boundaries | Measured reference timings until evidence is attached |
| `parameters` | Author-created control ranges, defaults, visual impact and failure signs | That defaults were measured or are physically universal |
| `evidence` | Observed source SHA-256, artifact link, exact source PTS, method, observation | Evidence not produced by an actual frame analysis |
| `kumiki` | Stable implementation registry ID, actual implementation state, bridge notes | Existing components or capabilities not verified in Kumiki UI |
| `qa` | Full-motion acceptance criteria, explicit human approval and comparison | Automatic proof of premium quality |

The JSON Schema is `schemas/v1/cinematic-technique.schema.json`, paired with stdlib-backed runtime validation in `src/kumiki_reference_lab/catalog/validate.py`. The explicit Python validator adds cross-field checks that JSON Schema cannot express portably here: contiguous beat ranges, unique parameter names, in-range authored defaults and status promotion gates. Keep both aligned. Tests should reject malformed candidates without modifying user-authored files.

## Promotion ladder

1. `research-candidate`: Original, reviewable story/cinematography recipe. Evidence may be empty. It does not imply implementation.
2. `implementation-proposed`: A concrete plan maps to actual Kumiki capabilities; registry reference still optional. Visual QA outstanding.
3. `implemented`: Code and a real Storybook/render preview exist. No claim of comparative fidelity or human approval.
4. `verified`: **Requires** source evidence, actual reviewed Kumiki registry entry, reference comparison, and human sign-off. Merely editing the status string must fail validation.

Do not increment status merely because tests pass. Tests validate structure and determinism; they do not evaluate whether the cinematic result looks professional.

## Turning a video into evidence

1. Use `inspect`, `frames`, `cuts`, `contact-sheet`, and `motion` on a reference with known source hash.
2. Human/AI reviewers examine the actual frames (or a locally configured vision model examines those frames) and produce **separate** observations, hypotheses and creative choices. A motion magnitude is an observation; "this must have been a dolly" is only a hypothesis.
3. Attach a precise `evidence[]` record only when it refers to an existing artifact and real source PTS. Include the observed quality, not invented camera/light numbers.
4. Propose and implement a Kumiki scene, inspect render frames and full-motion playback, and compare motion, silhouette, rhythm, exposure and comprehensibility with the original reference.
5. Promote the entry only after its checked implementation and review evidence exist. Registry IDs must be resolved against Kumiki's current catalog; no stale hardcoded assumptions.

## Versioning and extension rules

- `id` is stable; meaningful recipe revisions increment `revision`, not `id`. Breaking schema changes require `v2` schema and an explicit migration.
- New observations go in linked evidence reports; do not embed third-party video frames or model checkpoint blobs in catalog JSON.
- Add parameters for perceptual outcomes and technical tradeoffs, not for every internal renderer knob. Use units and visually testable failure conditions.
- For conflicting implementations (2D, 2.5D, native 3D), keep plausible alternatives in the mechanism and create separate verified Kumiki adapter IDs when capabilities diverge.
- Search ranks story-purpose terms above naming/stylistic similarity. It is deliberately lexical and deterministic today; future AI search must not mutate canonical entries or fabricate evidence.

## First entry set

| ID | Main lesson |
| --- | --- |
| `attention.focus-transfer-reveal` | Show one fact at a time through motivated composition and readable holds |
| `camera.motivated-macro-dolly` | Reveal shape and texture with spatially coherent, collision-checked camera movement |
| `lighting.softbox-curvature-reveal` | Build premium material form through controlled reflections and plausible light |
| `motion.anticipation-impact-settle` | Make causality and weight legible with restrained secondary motion and exact SFX sync |
| `editing.match-on-action` | Preserve geography and mechanism continuity across an information-motivated cut |

The original default numbers are **authored starting values** and should be tuned against real footage, subject scale and rendered output. In particular, the motion analyzer's global phase-correlation shift cannot separate object and camera displacement by itself. The next stages need independently tracked visual regions and per-shot comparison before automatic technique suggestions can be trusted.
