# Character scene and dialogue review (v1)

**Status: reviewer/model annotation contract, not automatic character recognition.**

The new character-scene command can validate and summarize timecoded observations of multiple characters, appearances, actions, directed interactions and dialogue, while retaining confidence and provenance.

## CLI

    PYTHONPATH=src python -m kumiki_reference_lab character-scene validate examples/character-scene.synthetic.example.json
    PYTHONPATH=src python -m kumiki_reference_lab character-scene report examples/character-scene.synthetic.example.json

The sample has entirely **invented** characters, actions and dialogue and an all-zero placeholder SHA-256. It is a schema demonstration, not a video analysis.

## Contract and interpretation

- The source is described by SHA-256, video stream index, rational source PTS timebase and declared review window. Structural validation is implemented, but this module **does not independently verify media bytes, diarization or semantics**.
- Each character receives an ID scoped to its source. Human, animated-human, animal, anthropomorphic, other and voice-only characters are supported. A name/label can be provisional. Visible descriptions record clothing, hair, shape, colors and distinguishing marks, not a person's real identity. Voice-only speakers cannot be assigned a visual appearance.
- Appearance intervals store one or more PTS anchors, visible attributes and an optional normalized bounding box [x,y,width,height]. These are annotation anchors, not automatic object tracks.
- Actions link a character to an optional second character; record an action label, time interval, anchors, observation and uncertainty. Actors and targets must belong to the film roster.
- Utterances include attributed or unknown speaker, transcribed words, language, time interval, transcript evidence and speaker-attribution evidence. Overlapping speech is supported; unlinked speech stays unattributed instead of being guessed.
- Names, age, gender identity and ethnicity are not deduced from looks. An identity claim needs an explicit spoken or on-screen statement or creator metadata, with time anchor, quoted/source evidence and uncertainty. These claims remain evidence-bearing assertions, **not verified personal facts**.
- Counts are of submitted annotations, not whole-film detection or exhaustive narration, even when the review declares a full window. A full-window flag does not independently verify coverage.
- The report also returns character profile/visible-trait summaries, actor-to-target interaction pairs, timecoded action and dialogue events and identity claims labeled as sourced assertions, so the output can answer concrete questions about **what was annotated**.
- Reviewer kind can be human or model. Model-proposed labels must remain hypotheses until source-media QA.

## Next engineering stages

1. Authorize and hash a local video; reuse the existing study-reference shot/PTS evidence.
2. Add optional per-frame person/animal/animated-subject detection and track association across shots; retain unknown/occluded IDs.
3. Add offline ASR, word-level timestamps and audio diarization; separately check lip motion and audio/video synchronization before assigning speech to a visible character.
4. Add timecoded VLM descriptions of visible actions, attributes and character-to-character interactions; validate frame support and confidence.
5. Normalize predictions into this character-scene schema, then produce candidate character blocking, gestures, gaze, lip-sync and dialogue beats for Kumiki UI. Render and independently review output.
6. Review known failure modes: multiple people in one shot, narration over product UI, offscreen voices, overlapping speech, hard cuts, occlusions, avatars and stylized transformations.

What Ships watch URLs are not media file paths. This command does not retrieve or redistribute What Ships or YouTube footage.
