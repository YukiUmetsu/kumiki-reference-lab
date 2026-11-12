# Evidence integrity audit

`scripts/audit_research_evidence.py` is an offline, standard-library-only audit
of the on-disk research records under `research/analysis/`. It walks each site
tree (`videos/` and `stills/`), detects the record family from its
`schemaVersion`, and validates the evidence without downloading anything.

```sh
python scripts/audit_research_evidence.py --root research/analysis \
    [--json-out PATH] [--site SLUG] [--strict-duplicates]
```

## Rule families

| Family | Examples | Default severity |
| --- | --- | --- |
| Schema | `schema.missing`, `schema.unknown`, `schema.missing-keys`, `schema.missing-identity` | error |
| Identity | `identity.source-sha256`, `identity.duration`, `identity.resolution`, `identity.media-retained`, `identity.media-path`, `identity.image-retained` | error |
| Window arithmetic | `arithmetic.window-luma`, `arithmetic.window-delta`, `arithmetic.window-span`, `arithmetic.record-summary`, `arithmetic.coverage-fraction` | error |
| Consistency | `consistency.window-bounds`, `consistency.window-overlap`, `consistency.cut-pts-bounds`, `consistency.appearance-range`, `consistency.pair-status` | error |
| Still quality | `still.histogram-shape`, `still.histogram-sum`, `still.metric-range`, `still.hue-family`, `still.image-bytes-range` | error |
| Index | `index.unreadable`, `index.count-mismatch` | warning |
| Duplicates | `duplicate.source-sha256`, `duplicate.media-cross-family` | warning |
| Identity reuse | `duplicate.identity` (one site+family claiming an id twice) | error |

Errors are integrity violations of a single record or of the tree. Warnings are
conditions that need review but cannot be resolved by editing one record.

## Duplicate media policy

Duplicate media is expected in these catalogues:

- the same work is listed under several award categories or festival editions,
  so one site may hold several records with the same bytes;
- two reference sites may cover the same work, so the same bytes appear in two
  site trees;
- each work is expected to have both a video record and a still record; the
  bytes differ by design (video vs. poster/frame), so this pairing is an
  intentional cross-family group, not a byte duplicate.

Findings are therefore one per duplicate **group**, not one per pair, and carry
a machine-readable classification and the full member list:

- `same-media-same-site-same-family` — same sha256 used by several records in
  one site and family. Usually one work repeated across categories/editions.
- `same-media-cross-site` — same sha256 used by records in more than one site.
  Usually one work covered by two catalogues.
- `same-media-cross-family` — one work (same site and identity) with both video
  and still evidence. Always expected.

Every finding includes:

```json
{
  "rule": "duplicate.source-sha256",
  "severity": "warning",
  "path": "aicp/videos/907458-cost-of-beauty.json",
  "detail": "sha256 eb3e667605b1... shared by 3 video records across aicp",
  "class": "same-media-same-site-same-family",
  "group": [
    {"site": "aicp", "family": "video", "id": 907458, "path": "aicp/..."},
    {"site": "aicp", "family": "video", "id": 945549, "path": "aicp/..."},
    {"site": "aicp", "family": "video", "id": 990805, "path": "aicp/..."}
  ]
}
```

`same-media-cross-family` uses the rule `duplicate.media-cross-family` and is
counted separately in the summary because the count is large and expected. The
same-site and cross-site byte-identical counts are the review-worthy ones. A
large same-site byte-identical group (dozens of unrelated works sharing one
407-byte-class image) usually indicates a placeholder/fallback asset rather
than a record bug; the audit still reports it once per group so the asset can
be identified.

## Exit codes

- `0` — no errors (warnings, including duplicate media, are allowed).
- `1` — at least one error.
- `--strict-duplicates` — promote duplicate-media warnings back to errors;
  useful for a future integrity push. Index warnings stay warnings.
