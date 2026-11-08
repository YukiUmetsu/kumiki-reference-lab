# Grounded cinematic review notes

The **`review-notes`** command provides a versioned, separate annotation file for what a human sees in a reference or what an optional vision-language model *claims* to see. It is the first step toward semantic film study, not a video-understanding model, automatic technique verifier or quality certificate.

## Workflow

```bash
kumiki-ref study-reference reference.mp4 --out runs/

# Use the concrete path of the finished study-manifest.json:
kumiki-ref review-notes init runs/study-.../study-manifest.json \
  --reviewer-kind human --reviewer-id yuki --out reviews/reference-001/

# For a locally run model, identify it explicitly:
kumiki-ref review-notes init runs/study-.../study-manifest.json \
  --reviewer-kind ai --reviewer-id local-vision-agent \
  --model-id local-vlm-name-and-version --out reviews/ai-001/

# Edit the separate review-notes.json using a human or optional VLM.
kumiki-ref review-notes validate runs/study-.../study-manifest.json \
  reviews/reference-001/review-notes.json
```

The `init` command writes a draft with **zero invented annotations**. It never calls AI, never extracts new footage and will not overwrite a different draft. To revise notes, edit the output outside the immutable study folder. Multiple reviewers use separate folders; the same `study-manifest.json` anchors all their drafts.

## Example authored annotation

Add an element to the `annotations` array:

```json
{
  "id": "note-001",
  "target": {"kind": "cue", "id": "cue-REPLACE-WITH-A-REAL-ID"},
  "category": "lighting",
  "layer": "visual-hypothesis",
  "statement": "The bright region may be a graphic moving independently of the material.",
  "confidence": "medium",
  "assessment": "contradicts",
  "evidenceFrames": [
    {
      "sourcePts": 0,
      "description": "REPLACE with what is visibly in a verified frame",
      "normalizedBox": [0.1, 0.2, 0.3, 0.25]
    }
  ],
  "uncertainties": [
    "A moving light and animated material can generate similar screen-space changes."
  ]
}
```

Replace **both** the cue ID and the PTS with values from the actual study. An invalid cue ID, an absent original PTS, or a PTS outside the cue's interval is rejected. `normalizedBox` uses top-left-origin normalized image coordinates `[x, y, width, height]` and must remain entirely inside the source frame; omit it when you cannot accurately localize the evidence.

For `region` targets, use a `region-001`-style ID from `shot-evidence.json` and `assessment: "not-applicable"`. A region's allowed anchors run from `startPtsInclusive` through `lastObservedFramePts`, **not** a guessed terminal frame; the last region has no implied end PTS. For `cue` targets, use `supports`, `contradicts` or `unresolved`. Thus a false-positive lighting or dolly suggestion can be recorded rather than silently promoted.

## Required distinctions

| Field | Purpose | Guardrail |
| --- | --- | --- |
| `layer: visible-observation` | Description of pixels, composition, readable text, motion appearance | Does **not** establish how the source was built |
| `layer: visual-hypothesis` | Tentative explanation: camera, reflection, animated mask, etc. | Must list uncertainties; alternatives remain possible |
| `layer: story-interpretation` | What a viewer may be meant to notice, understand or feel | Must list uncertainties; interpretation is not a factual claim about creator intent |
| `layer: implementation-suggestion` | A possible original Kumiki technique, timing or visual treatment | Must list uncertainties; implement against Kumiki UI contracts after independent review |
| `category` | Story, attention, composition, camera, lighting, materials, animation, editing, sound, other | A taxonomy tag, not a classifier's measured outcome |
| `assessment` | Cue support, contradiction or unresolved ambiguity; N/A for regions | Cannot change the authored catalog or measured cue |
| `evidenceFrames` | One to eight original decoded frame PTS with textual descriptions | Must refer to exact source PTS inside the referenced cue/region |
| `reviewer` | Named human or named AI with nonempty model ID | An AI cannot masquerade as a human approval |

All inputs are bounded: at most 64 annotations, eight frame anchors per annotation and small text fields. JSON rejects unknown keys, duplicate JSON keys, unbounded files, stale source hashes, broken study inventories, nonexistent targets, duplicate annotation IDs, non-original PTS and malformed boxes. The CLI performs checks beyond [the JSON schema](../schemas/v1/review-notes.schema.json), including the integrity of the **full original analysis run**.

The successful validation report deliberately says `structureStatus: source-anchors-verified`, `semanticStatus: not-verified` and `artisticApproval: not-granted`. It cannot verify whether the text correctly describes the video, whether a shot is effective, whether a physical light was present or whether a proposed animation is production-ready. Such decisions require a human to watch the **full source and rendered Kumiki output** at speed, judge the story and craft, and provide separate approval.

## For coding agents

1. Read [reference-study](reference-study.md) and open the source gallery and shot evidence. Review original playback, not only extracted JPEGs.
2. Choose a real target ID. For every significant statement, cite source PTS from `frame-timeline.json`; any local crop should use a normalized box.
3. Record uncertain interpretation as `story-interpretation` or `visual-hypothesis` and state plausible counter-explanations in `uncertainties`.
4. A `contradicts` note is evidence **against** blindly implementing that catalog candidate. Retain both the original candidate and the reviewer objection for audit.
5. Run `review-notes validate`. Do not rewrite `study-manifest.json`, `technique-proposals.json`, `shot-evidence.json`, existing catalog revisions or source images to manufacture a pass.
6. Treat any implementation suggestion as a design brief for an **original** scene. Resolve existing Kumiki UI APIs, render movement at full frame rate, compare at explicit reference/render anchors, and get a separate human visual verdict.

### Future optional AI adapter

An optional, explicitly invoked AI module can consume a bounded selection of verified source frames/audio, produce this same JSON schema, preserve model identity/parameters, and run the same validator. Its captions, story guesses and labels must remain `semanticStatus: not-verified`. A model call never writes into a checksum-verified analysis bundle or grants technique/catalog approval. Audio cue analysis and human-verified story-beat timing should become separate measured/review layers, not be fabricated from still frames.
