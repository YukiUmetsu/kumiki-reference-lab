# Evidence-linked character speech attribution

The new `speech-link-characters` command joins a timecoded audio/voice scene to a separately annotated visual-character scene **only when a specific utterance has an explicit visible lip-motion observation**. It does **not** detect lips, perform active-speaker classification, recognize an individual or infer that every utterance by a voice cluster belongs to one visible character. The output is a reviewer-declared attribution, not independently proven lip-sync.

## Workflow

1. Generate `character-scene.json` from `speech-transcribe` and optionally `speech-associate`. Speaker IDs may be `null` or local `voice_###` acoustic clusters.
2. Review the *same authorized local media* to create a second valid `character-scene` containing visible characters, appearance intervals and actions, but **no utterances**. Both scenes must agree on source SHA-256, video stream and rational PTS timebase. The visual window must fit within the speech window.
3. Create a small link review with explicitly observed lip motion:

```json
{
  "schemaVersion": "kumiki.character-speech-link-review.v1",
  "sourceSha256": "REPLACE_WITH_ACTUAL_64_CHARACTER_SHA256",
  "sourceStreamIndex": 0,
  "sourceTimebase": {"numerator": 1, "denominator": 1000},
  "reviewer": {"kind": "human", "id": "visual-reviewer"},
  "links": [
    {
      "utteranceIndex": 0,
      "characterId": "character_a",
      "evidencePts": 700,
      "evidenceType": "visible-lip-motion",
      "observation": "Character A's lips move while the first phrase is audible.",
      "confidence": "medium"
    }
  ]
}
```

This example is a **template**, not a valid study until the source identifiers, visible character ID, original PTS and actual observations have been supplied. The character must be visibly present at `evidencePts`, which must also fall *inside the selected utterance*. The tool checks both intervals, not whether the observation itself is truthful.

```bash
PYTHONPATH=src python -m kumiki_reference_lab speech-link-characters \
  ./runs/speech-with-voices-01/character-scene.json \
  ./reviews/visual-character-scene.json \
  ./reviews/lip-motion-links.json \
  --out ./runs/character-dialogue-01

PYTHONPATH=src python -m kumiki_reference_lab character-scene report \
  ./runs/character-dialogue-01/character-scene.json
```

## Behavior and limits

- Linking is **per utterance**. A linked `voice_001` segment becomes `character_a` for that one segment only. Other segments stay as their original voice-only cluster IDs or `null`.
- A source mismatch, invalid PTS anchor, absent appearance evidence, wrong character ID, duplicate utterance index, unapproved evidence type or unresolved link is rejected.
- Human reviewer confidence remains an *assertion*. Model-generated links are kept at **low confidence** regardless of the model's requested rating.
- Preserves visual characteristics and actions. Does not infer age, ethnicity, gender identity, character relationship or unreviewed behavior.
- New output directories contain a combined `character-scene.json` and an explicit `character-speech-links.json` provenance report, including original voice IDs. Neither source review is modified.
- No arbitrary video downloads or external API calls are performed. The actual model/human observation is a separate step.

**Next engineering priority:** optional, well-calibrated local visual-person/character tracking and audiovisual active-speaker detection. The present stage builds the evidence gate so that future models cannot silently fabricate who spoke.