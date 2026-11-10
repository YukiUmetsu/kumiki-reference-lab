# What Ships: cross-category metadata coverage

Snapshot: **November 10, 2026**. Source: [What Ships' public video index](https://whatships.com/search-index.json) and its [read-only catalog interfaces](https://whatships.com/developers/). Reproduce the numbers with:

```bash
PYTHONPATH=src python -m kumiki_reference_lab video-sources report
```

The table below covers **What Ships only**; the report also includes a separate 40-film, intentionally popular YouTube reference cohort, which should **not** be compared directly with this catalog.

| Site category | Indexed videos | Detailed records | Historical view counts known | Median duration among detailed records | Median observed X views among records with a count |
| --- | ---: | ---: | ---: | ---: | ---: |
| AI | 1,122 | 50 | 50 | 40 s | 77,585.5 |
| Developer tools | 603 | 50 | 50 | 38.5 s | 47,135.5 |
| Other | 335 | 50 | 50 | 32.5 s | 126,536 |
| Design | 310 | 50 | 50 | 41 s | 25,007.5 |
| Productivity | 165 | 50 | 50 | 52 s | 28,544.5 |
| Consumer | 161 | 50 | 50 | 43 s | 195,269 |
| Hardware | 96 | 50 | 49 | 68 s | 630,452 |
| Motion | 69 | 69 | 69 | 38 s | 58,662 |
| **Total** | **2,861** | **419** | **418** | — | — |

## What can and cannot be inferred

- **Coverage is not uniform.** Every Motion entry has detail; AI has detail for only 50 of 1,122 indexed items. This is a convenience sample from the directory, not exhaustive engagement evidence.
- **Hardware's larger observed median does not prove the hardware category is more viral.** Product/account recognition, paid reach, original post age, distribution, and the directory's curation can dominate raw counts.
- **Unknown does not mean zero.** A detailed Hardware entry lacks a view count; 2,442 indexed entries across categories have no detail. Those are excluded from view medians, not assigned zero views.
- **A view count does not identify a technique.** The metadata says nothing about shot cadence, camera movement, lighting, transitions or the way footage was produced. Those require observation of the actual video, ideally with authorized timecoded local footage.

## Creative takeaways worth testing

Direct [browser playback spot checks](whatships-observed-motion.md) suggest multiple presentation strategies with no single dominant style: kinetic typography; editor-like paper collage; atmospheric mixed media; image prompt → generated result; talking-head evidence; and simultaneous terminal/app demonstration. This is **idea generation** from selected footage, not statistical validation.

For the next controlled study, record timestamps and classify the observable footage separately from claims: `sourceIdentity`, category, post date, source view snapshot date, duration, proportion of directly observed runtime, shot transitions, typography events, apparent camera/object movement, light/style descriptions, audio cues and alternate explanations. Compare similarly aged, similarly long films *within categories* first; when account reach is unknown, explicitly mark confounding unresolved.
