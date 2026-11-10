# Widely watched explainer films: evidence-linked study collection

This is an **editorial shortlist of animation references** for the Kumiki ecosystem, not a chart of the best videos or a verified account of their underlying production processes. The first cohort deliberately spans eight creators and techniques ranging from typography and 2D illustration to mathematical diagrams and 3D engineering. Each selection has a direct watch URL and a named public source reporting its video view count.

**Research retrieval: November 10, 2026.** Counts are **video views / plays, not unique viewers**, and must not be used as proof of audience retention, engagement, visual quality, commercial rights, or causal efficacy. Search-indexed counts and third-party analytics can lag YouTube. The `~` sign means the evidence source rounded the count; unmarked numbers are exact *reported figures*, not guarantees of live counts. Where available, the third-party source snapshot date is noted separately from retrieval. Titles can be changed by their creators: the **video ID**, not the title, is the durable identity.

| Reference film / creator | Reported views | Evidence for the count | Film language / primary research question |
| --- | ---: | --- | --- |
| [history of the entire world, i guess](https://www.youtube.com/watch?v=xuCn8ux2gbs) · bill wurtz | 184,476,351 | [Indexed YouTube listing](https://www.youtube.com/watch?v=xuCn8ux2gbs) | Kinetic type, extreme information density and music-aligned historical editing |
| [WW2 - OverSimplified (Part 1)](https://www.youtube.com/watch?v=_uk_6vfqwTA) · OverSimplified | ~105,800,000 | [Viewstats video statistics](https://www.viewstats.com/%40oversimplified/videos/_uk_6vfqwTA) | Geography, cartoon character blocking and comedic storytelling |
| [The Immune System Explained I – Bacteria Infection](https://www.youtube.com/watch?v=zQGOcOUBi6s) · Kurzgesagt | 54,599,970 | [Indexed YouTube listing](https://www.youtube.com/watch?v=zQGOcOUBi6s) | Color-coded actors and explanatory metaphors for biological systems |
| [The Simple Solution to Traffic](https://www.youtube.com/watch?v=iHzzSao6ypE) · CGP Grey, subsequently retitled | 44,607,061 | [Digital Creators channel statistics](https://digitalcreators.jp/en/channel/en/UC2C_jShtL725hvbm1arSV9w/popular-videos/) (page dated 2026-11-01) | Agent-based traffic simulation and visually explicit cause–effect |
| [The Egg - A Short Story](https://www.youtube.com/watch?v=h6fcK_fRYaI) · Kurzgesagt | 36,220,464 | [Indexed YouTube listing](https://www.youtube.com/watch?v=h6fcK_fRYaI) | Emotional character narrative and illustrative scene continuity |
| [The Largest Star in the Universe – Size Comparison](https://www.youtube.com/watch?v=3mnSDifDSxQ) · Kurzgesagt | 35,816,117 | [GraphStats channel statistics](https://graphstats.app/channel/kurzgesagt) | Legible scale comparisons, camera paths and reference anchors |
| [The Rules for Rulers](https://www.youtube.com/watch?v=rStL7niR7gs) · CGP Grey, subsequently retitled | 25,468,165 | [Indexed YouTube listing](https://www.youtube.com/watch?v=rStL7niR7gs) | Diagrammatic political systems and repeating visual role tokens |
| [But what is a neural network?](https://www.youtube.com/watch?v=aircAruvnKk) · 3Blue1Brown | 24,354,709 | [Indexed YouTube listing](https://www.youtube.com/watch?v=aircAruvnKk) | Progressive mathematical disclosure and animated data-flow diagrams |
| [The Map of Mathematics](https://www.youtube.com/watch?v=OmJ-4B-mS-Y) · Domain of Science | 16,124,077 | [Indexed YouTube listing](https://www.youtube.com/watch?v=OmJ-4B-mS-Y) | Mapping an abstract field; motivated movement between labeled territories |
| [What would happen if you didn’t sleep?](https://www.youtube.com/watch?v=dqONk48l5vY) · TED-Ed | 14,972,115 | [Indexed YouTube listing](https://www.youtube.com/watch?v=dqONk48l5vY) | Narrative-aligned 2D biological illustration |
| [The myth of Sisyphus](https://www.youtube.com/watch?v=q4pDUxth5fQ) · TED-Ed | 8,840,646 | [Indexed YouTube listing](https://www.youtube.com/watch?v=q4pDUxth5fQ) | Atmospheric illustrated myth, dramatic staging and parallax candidates |
| [How do Graphics Cards Work? Exploring GPU Architecture](https://www.youtube.com/watch?v=h9Z4oGN89MU) · Branch Education | 7,526,376 | [Indexed YouTube listing](https://www.youtube.com/watch?v=h9Z4oGN89MU) | High-detail 3D assembly, mechanism reveals and explanatory camera work |

These **12 video entries have a combined ~558.8 million reported plays** as recorded in the source snapshots. This aggregate is illustrative, not an audience size: one person may watch multiple times or watch multiple entries. Popularity figures have not been normalized for age, channel size, promotion, or topic demand. **None of these videos has yet passed Reference Lab's decoded-frame motion/quality review**; the suggested technique descriptions are study hypotheses.

## What to study first for Kumiki

1. **Branch Education — GPU architecture:** prioritize component craftsmanship, 3D material fidelity, explanatory exploded views and camera continuity. Study how each camera move answers a mechanical question. Translate accepted findings into Kumiki Blender assets and Kumiki UI camera/lighting contracts.
2. **Kurzgesagt — largest star:** prioritize consistent scale anchors, visual orientation and transitions between size regimes. Prototype a separate, original scale-comparison recipe; verify the result's legibility at full speed.
3. **3Blue1Brown — neural networks:** prioritize progressive disclosure and stable 2D/3D information layout. Measure the time spent introducing each abstraction versus the amount already on screen.
4. **CGP Grey — traffic:** prioritize explicit cause-and-effect, repeated agents and scenario changes. A useful synthetic fixture for Kumiki would have auditable traffic states and intentionally varied visual explanations.
5. **OverSimplified — WW2:** prioritize geography, character-to-character story continuity and comedic pauses. Use original illustrations, not traced animation.

After those, investigate TED-Ed for illustrated cinematic staging, Domain of Science for navigating conceptual maps, and bill wurtz for unusually dense rhythmic pacing. These priorities reflect **the current goals of Kumiki**, not a claim that one creator has objectively higher production quality.

## Reuse and evidence workflow

The versioned, machine-readable records are in [`research/popular-explainer-videos.v1.json`](../research/popular-explainer-videos.v1.json), with the contract in [`schemas/v1/popular-reference-videos.schema.json`](../schemas/v1/popular-reference-videos.schema.json). Each record includes a stable video ID, reported view count, source type and URL, source snapshot date if known, technique tags, an actionable study question and explicit rights status.

```bash
PYTHONPATH=src python -m kumiki_reference_lab video-references validate
PYTHONPATH=src python -m kumiki_reference_lab video-references list --min-views 20000000
PYTHONPATH=src python -m kumiki_reference_lab video-references search "camera scale"
PYTHONPATH=src python -m kumiki_reference_lab video-references search "system diagram" --limit 5
```

All commands operate on **local metadata only** and never download or embed a video, call a video service, or imply authorization. Pass `--root /path/to/catalog.json` when running outside this repository. Both `list` and `search` sort deterministically and are suitable for agent lookup. A view count is only an **evidence-backed popularity signal**; it is never a recommendation algorithm or a verified production metric.

To progress an item from popularity-supported *study candidate* to a **measured** technique:

1. Obtain legitimate access to the media and confirm the intended local analysis is authorized. A publicly playable URL is **not a license** to copy frames, audio, code, textures or style assets into a commercial product.
2. Use `study-reference` on an authorized local copy; record its SHA-256, exact source PTS, candidate edits, measured motion/color/audio and uncertainty.
3. Perform human visual review of real, timecoded source frames and full-speed motion. Separate observations from hypotheses about camera, light, software or narrative intent.
4. Implement an **original** technique in Kumiki UI (or independent 3D assets in Kumiki Blender); align authored output with source timing and use `review-film-map` and `film-feedback` to verify craft. Only promote a technique entry after the existing evidence and approval gates pass.

### Provenance caveats

- `youtube-search-index` identifies a view figure in a search-indexed listing for the original YouTube URL. It is not a YouTube Data API measurement and has no independent historical snapshot timestamp. The original URL is the best durable reference, but the currently displayed view number may differ.
- `third-party-video-statistics` names an outside page displaying video-specific or channel video statistics; it is independently browsable and may itself be cached or rounded. A channel statistics page can change which entries it lists over time.
- `retrievedOn` is the date the research sources were checked, **not** a claim that all counts were freshly recomputed by YouTube on that date. `sourceSnapshotOn: null` means no trustworthy source snapshot date was established.
- This collection is curated for **production techniques relevant to explainers**; it is not a random sample of YouTube, an assessment of original video quality, or a basis for statistical claims about what makes videos go viral.
