# What Ships: browser-observed launch film references (November 10, 2026)

These are **qualitative browser-playback spot checks**, not automatically decoded or timecoded video analyses. The site was opened and the public player was used; no media files were downloaded. Only the visible moments named below were observed. View counts and durations are **separate, historical site metadata** from [`research/whatships-motion-2026-11-10.json`](../research/whatships-motion-2026-11-10.json); they are not measurement of the playback or proof that a visual technique caused popularity.

| Film / source | Site-attributed X views | Duration | Directly visible moments during the spot check | Plausible Kumiki technique to study, **not yet independently measured** |
| --- | ---: | ---: | --- | --- |
| [Claude Motion Reel](https://whatships.com/videos/claude-motion-reel/) (Stephan Livera; [original X post](https://x.com/stephanlivera/status/2103315922098470926)) | 1,694,542 | 15 s | Around the opening, six easing-curve examples show colored dots moving on tracks; another visible segment uses repeated oversized black `NEVER` lettering on fluorescent yellow; the ending is a coral/orange branded card with a floral mark. | Show motion principles *through* motion, then use an abrupt, constrained palette and large kinetic text. Review exact shot boundaries and easing curves against authorized footage before implementing a recipe. |
| [Paper Mono launch making-of](https://whatships.com/videos/paper-mono-code/) (Agu Seguí; [original X post](https://x.com/agusegui/status/2108251509830140401)) | 189,170 | 61 s | An editor-like split screen shows code, layer/timeline panels and rendered animated lettering. In another observed moment, overlapping sheets and typographic panels appear to fold/slide in a 3D-like collage. | Layered editorial/print collage; synchronize reusable paper/card transforms with a compositing timeline. No claim that the imagery uses physical paper. |
| [Applied Electrodynamics](https://whatships.com/videos/applied-electrodynamics/) (Bilgehan Avser; [original X post](https://x.com/bavser/status/2082868602240385526)) | 1,059,995 | 87 s | A low-key, dark scene features a warmly lit retro computer and terse white type. Later visible moments switch to real-world electronics workbench footage and a monochrome patent-style line drawing on white. | Documentary-style alternation among atmospheric product 3D, live footage and technical illustration. Investigate clarity and visual contrast at those transitions. |
| [Grok Bot icon animated in code](https://whatships.com/videos/grok-bot-icon-in-code/) (xAI; [original X post](https://x.com/benjitaylor/status/2087227155076046995)) | 1,567,897 | 31 s | A visible end frame presents a near-black round face with two elongated white eyes on pale gray. | A character/icon state machine with shape-preserving morphs is suggested by the site's description, **not confirmed from this end-frame spot check**. |
| [Figma — Made in Figma 2025 reel](https://whatships.com/videos/figma-3980/) (Figma; [original X post](https://x.com/figma/status/2001715747505233980)) | 35,986,684 | 38 s | A sampled frame features translucent, refractive sphere-like treatment over bold `Liquid` lettering within a design-interface composition. Other parts of the reel were viewed in the initial collection pass but were not timecoded here. | Refractive/transparent logo accents integrated with product UI; the underlying implementation and shader are unknown. |

## Cross-category browser playback spot checks

The following additional films were sampled from outside the Motion category. Their different visual priorities are a useful counterweight to studying reels alone.

| Film / source | Category; X views | Duration | Directly visible moments | Production question to test |
| --- | --- | ---: | --- | --- |
| [Canva Craft](https://whatships.com/videos/canva-craft/) (Canva; [original X post](https://x.com/canva/status/2113348707223753165)) | Design; 1,858,611 | 35 s | Warm orange dunes with sparse white title; a purple-to-cyan branded ranking chart; pastel prompt interface; a blue chair on reflective pink terrain presented as an output. | How does alternating atmosphere → proof graphic → interaction → result affect comprehension? The chart's underlying factual claims were **not checked**. |
| [GPT-6.1 Terra](https://whatships.com/videos/gpt-6-1-terra/) (OpenAI; [original X post](https://x.com/OpenAI/status/2114780711664398349)) | AI; 4,620,309 | 31 s | Globe-backed opening title; an aerial view of buildings and tram; a prompt card containing an image and 3D-model request; then a Blender viewport displaying a tram model. | Can a short film bridge cinematic context to a concrete application result without losing the narrative thread? Product behavior was **not independently verified**. |
| [Subvocal](https://whatships.com/videos/subvocal/) (Subvocal; [original X post](https://x.com/AarushYadav47/status/2116198463847408066)) | Hardware; 11,889,031 | 77 s | Two people in interview chairs with changing text behind them, a presenter addressing the camera with captions, everyday office footage, and a poster/end-card drawing of glasses. | When is a grounded human demonstration preferable to elaborate animation for explaining new hardware? |
| [agent-desktop](https://whatships.com/videos/agent-desktop/) (agent-desktop; [original X post](https://x.com/ctatedev/status/2116323148706771302)) | Developer tools; 1,434,045 | 20 s | A terminal next to a small trip-planning UI; desktop windows, floating cursors with labels, a calculator, and native menus in later sampled moments. | Can labeled, minimally edited multi-window screen recordings establish credibility more quickly than a motion-heavy feature list? |

**Working synthesis:** These samples do *not* support one universal visual style. The Design film mixes environmental imagery, benchmark-like proof and product UI; the AI film connects a visual setup to a shown modeling task; Hardware emphasizes human context; Developer tools relies on directly observable interactions. This is a hypothesis-generating observation from **four selected films**, not a category-level finding.

## Corpus context, not a causal ranking

The bundled **69 Motion entries** each have a duration and a historical site-attributed X view number. In this *curated* sample:

- Median duration is **38 seconds**; **40/69** entries last at most 60 seconds, and **27/69** last under 30 seconds.
- Median observed views are **58,662**; **7/69** entries exceed 1 million observed views. Counts include a high outlier (the Figma reel: 35,986,684).
- Among the **40 clips at most one minute long**, median views are **36,099**. Among the **29 longer clips**, they are **85,116**. The longer subset's higher median is a *descriptive property of this selected directory*, not evidence that longer videos perform better.
- The archive is not a random sample of uploads: 68 films are labeled 2026 and one 2025, view snapshots were taken on different dates, and account reach, paid impressions, subject matter and publication age are uncontrolled.

## Next evidence pass

1. Use the catalog to select **paired** films with similar duration, publication age, topic and distribution/account reach where possible; do not compare raw view totals without these covariates.
2. On playback, record actual elapsed-video timestamps for shot boundaries, movement categories, text density, light/shadow style and camera vs object movement. A screenshot or the site's textual description alone is insufficient.
3. If authorized media is obtained separately, run `study-reference`, `visual-events` and `visual-style-review` against its local file with immutable source hashes/PTS. Until then, these are **selected browser observations**, not frequency metrics.

Practical idea for Kumiki-UI: prioritize an original **paper/editorial collage reveal** and **teaching-through-easing demonstration** as two *testable* recipes. Their appeal is visual specificity and educational clarity, not a claimed statistically proven virality advantage.
