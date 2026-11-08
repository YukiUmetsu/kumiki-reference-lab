# Candidate edit rhythm: measured cut-to-cut timing

Film pacing is about **when and why information changes**, but a deterministic program can initially measure only edit timing candidates. The `edit-rhythm` command produces exact source-clock intervals between *successive candidate hard cuts* from a verified analysis run. It never asserts story beats, excitement, scene quality, or an author's editing intention.

## Command

```bash
kumiki-ref analyze ./reference.mp4 --max-seconds 10 --out ./runs
kumiki-ref edit-rhythm ./runs/analysis-.../analysis-run.json \
  --out ./runs/rhythm-review
```

Substitute the actual analysis-run path printed by the first command. The second writes an immutable `edit-rhythm.json`; omit `--out` to print JSON to stdout. Its schema is [`schemas/v1/edit-rhythm.schema.json`](../schemas/v1/edit-rhythm.schema.json).

## Contract and exact methodology

1. Validate the entire original `analysis` artifact inventory (source SHA, original source stream timebase, cut report and decoded frame PTS). Refuse to calculate if any original frame timestamp is unreliable.
2. Candidate cut positions are the starts of every region **after** the initial region. Let them be `c1, c2, …, cn`, in exact rational presentation seconds; they must strictly increase.
3. Measure only `c2-c1`, `c3-c2`, etc. Store every duration as a reduced `{numerator, denominator}` ratio in seconds, with original bounding candidate PTS and region ID. This yields `max(0, candidateCutCount - 1)` observed interior intervals.
4. The initial span from **bounded scan start** to `c1` is *left-censored*: the first sample need not be a complete shot start. The final span from `cn` to **bounded scan end** is *right-censored*: the last region has no verified next edit or end PTS. **Neither contributes to duration statistics.**
5. For two or more interior intervals, compare each later interval's duration to the previous one's exact duration. Emit `shorter`, `longer`, or `same`, plus the exact positive ratio. The first interval has a null ratio and `not-applicable-first-interval` change.
6. Report exact minimum, median, and maximum of measured interior intervals. Empty intervals produce null aggregates, not invented zeros. Every result retains source and analysis-run hashes, `algorithmic-hard-cut-candidates-not-verified-edits`, and `qualityVerdict: not-performed`.

Example: observed candidate edits at 1s, 3s, and 4s produce two inter-cut gaps, 2s and 1s. The latter has ratio 1/2 and `shorter`. This is *one measurable local duration change*, **not** a verified pacing acceleration or emotional interpretation.

## What an AI coding agent may do next

- Present exact interval timestamps alongside the candidate-cut storyboard so an editor can confirm or reject each cut by watching the original clip.
- Attach human notes about intended attention, editorial punctuation, narration/action continuity and sound relationships as **separate hypotheses**, never by rewriting measured interval artifacts.
- Compare confirmed edit sequences across references, explicitly matching sample ranges and censored boundaries before computing relative pacing patterns.
- After review, propose pacing parameters to Kumiki UI through its **existing** timing contracts, then render and conduct a full-speed evaluation. Never invent a Kumiki importer/animation capability.

The algorithm cannot infer dissolves, crossfades, montage intent, speech segmentation, film grammar, music synchronization or total video length from a bounded hard-cut scan. There is no AI runtime or internet requirement. Keep the FFmpeg integration tests local to avoid expanding the lightweight hosted CI workflow.
