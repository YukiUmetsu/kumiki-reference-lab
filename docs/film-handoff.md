# Film authoring handoff: Reference Lab → Kumiki UI

`export-film-handoff` is the first concrete interchange slice toward a **reference → source-linked study → authored Kumiki film → render → comparison** workflow. It creates a verified, deterministic JSON evidence packet for a coding agent or film editor. **It does not generate a playable film, select a recipe, claim to recover a camera rig or assign audio cues.**

## Exact downstream contract audited

Kumiki UI currently implements **FD1 FilmDocument**, a JSON-authored film with `schemaVersion: 1`, rational `{num,den}` FPS, authored scene `recipeId`/`durationFrames`/`content`, and declared output profiles. The contract lives at [`kumiki-ui/registry/video/film-document.schema.json`](https://github.com/YukiUmetsu/kumiki-ui/blob/main/registry/video/film-document.schema.json); its guide is [`docs/component-specs/film-document.md`](https://github.com/YukiUmetsu/kumiki-ui/blob/main/docs/component-specs/film-document.md). This is distinct from Kumiki's MD1/MG1 choreography, CC1 camera, and proposed future composition schemas. Source study measurements are **not** FD1-ready creative scene data.

Before implementing a scene, the coding agent must inspect the **current installed** Kumiki UI repository, run `npm run catalog:find -- --query="<scene purpose>" --format=json` and `npm run catalog:api -- --id=<registered component> --format=json`, then author an independent FD1 document and validate it using `npm run film:check -- <authored-film.json>`. The exported packet intentionally says `installedCapabilitiesVerified: false` until that is done. It cannot be passed directly to `film:render`.

## Use

```bash
kumiki-ref study-reference ./reference.mp4 --out ./runs --max-seconds 10
kumiki-ref export-film-handoff \
  ./runs/study-.../study-manifest.json \
  --fps-num 30000 --fps-den 1001 --out ./handoff
```

Replace `study-...` with the actual study directory. The study and its original analysis bundle must be intact: the command verifies the complete study/analysis source hashes, file inventories, source PTS and versions before exporting. It reads the study's `edit-rhythm.json`, `shot-evidence.json`, `technique-proposals.json` and nested `audio-onsets.json`. No second FFmpeg decode, AI call, video archive, network request or Kumiki UI runtime is needed. The output directory must be **outside** the checksum-protected study and analysis directories.

`film-handoff.json` is idempotent: an identical rerun reuses identical bytes; conflicting existing content is never overwritten. Schema: [`schemas/v1/film-handoff.schema.json`](../schemas/v1/film-handoff.schema.json).

## What each field means

| Packet field | Meaning | What an agent must not assume |
| --- | --- | --- |
| `study.*Sha256` | Provenance of the verified immutable study, original video and analysis | Redistributable source video or human approval |
| `target` | A known authoring contract and command to run after building an **original** film | Installed renderer/recipe availability already verified |
| `timing.suggestedFilmFps` | User-selected rational target FPS | The reference used the same FPS |
| `boundaries.candidateCutCount` | Number of algorithmic source-video cut candidates | Confirmed editorial cuts |
| `interiorWindows[]` | Exact rational source PTS between **adjacent candidate cuts**; optional film-duration suggestion | Complete first/last shot, author-selected film duration or scene content |
| `interiorWindows[].suggestedFilmFrames` | `round_half_up(source_duration × target_fps)` using exact rational arithmetic | An exact temporal match or mandatory output duration |
| `interiorWindows[].roundingErrorSeconds` | `suggestedFrames/fps − exactSourceDuration`, an exact signed rational | Accumulated drift correction already performed |
| `interiorWindows[].renderability` | `requires-authored-retiming` when a source interval rounds to zero frames | Permission to silently force a one-frame shot |
| `audioAttackCandidates[]` | Source-audio PTS anchors and two-decoded-frame windows | Sample-accurate sound starts, beats, speech, SFX or synchronized video events |
| `catalogTechniqueCues[]` | Unverified source-linked *reference-lab catalog* candidates | A matching Kumiki UI implementation ID exists |

The packet's `sceneRecipeId`, `sceneContent`, `implementationId`, and `filmCue` are deliberately `null`. A coding agent must author these only **in a separate FD1 film file after reviewing original footage and validating live Kumiki APIs**. It must not alter the immutable handoff packet to make it masquerade as a verified generated film.

### Pacing boundaries and clock hazards

The first bounded video region may start in the middle of a shot; the last region has no verified shot end. Therefore the packet **excludes both from suggested scene durations**, and only exports cut-to-cut interior windows. If there are fewer than two candidate cuts, `interiorWindows` is an empty array. Zero candidates is a legitimate result, not a failed analysis and not permission to invent cuts.

All video times remain rational original source PTS. Audio candidates retain their **independent source-audio clock**; audio PTS is not mapped to a target film frame. A common container and normalized timestamps do not independently establish audiovisual synchronization because edit lists, priming and stream offsets may matter. Only an editorially verified alignment may become an authored `FilmDocument.audio` cue or lane.

The nearest-half-up rounding rule is an *individual duration suggestion*. When choosing several windows, compute a whole-film frame budget and deliberate pacing independently; rounding each window may accumulate error. Never interpret source timing as the duration of an author's original explanation.

## Expected follow-up workflow

1. Open the v5 study's visual storyboard, evidence timeline and original video; reject wrong cut candidates and label story-critical changes. Add source-PTS-anchored `review-notes.json` separately; never rewrite the analysis bundle.
2. Choose a complete *original* narrative: question, cause, visible mechanism, transformation and payoff, with stable subjects and measured reading holds.
3. Query Kumiki UI's installed catalog for appropriate FD1 `recipeId`, content schema and exported APIs. Use MD1/MG1/CC1 only via the real components, never by inventing props or treating a reference's apparent zoom as a recovered 3D dolly.
4. Write `*.film.json` with authored scenes, duration frames, content, outputs, assets and sound. Validate with `npm run film:check`, review critical frames via `npm run film:review`, and render using `npm run film:render`.
5. Supply the actual render to `compare-frames` or `compare-appearance` with **explicitly chosen** source/render anchors. Inspect the movie at full speed, check readability and obtain human visual approval. Automated hashes and schema success do not certify a cinematic match.

For a reproducible multi-anchor review after authoring, use Kumiki UI's `film:reference-map` to link exact source PTS to FD1 frames, then run Reference Lab's [`review-film-map`](film-map-review.md) against the original source video and rendered MP4. The command verifies encoded timestamps and creates actual paired JPEG evidence; it never claims a finished quality verdict.

Once the paired stills and full-motion render have been inspected, `film-feedback init`/`validate` produces separately authored, evidence-bound correction findings for the next FD1 edit pass. Such feedback remains draft, without automatic aesthetic approval or catalog promotion.

## Quality and CI

Run `PYTHONPATH=src python -m unittest tests.test_film_handoff -v` locally for deterministic frame conversion, provenance checks, excluded scan ends, no implied sound-event import, immutable artifact reuse and tamper detection. The optional FFmpeg/NumPy end-to-end fixture remains local. Hosted GitHub CI continues its small smoke suite; no test files are removed.
