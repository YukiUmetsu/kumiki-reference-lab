# Directors' Library: video-page source catalog

Directors' Library is a curated collection of music videos, campaigns,
shorts, and film/TV projects. This adapter reads **public page metadata**
from [the latest archive](https://directorslibrary.com/videos/latest/) and
its individual video pages, without fetching Vimeo/YouTube playback media.

The canonical snapshot lives in
[`research/analysis/directors-library/`](../research/analysis/directors-library/).
Every record retains a stable site-derived ID, film page, title, director
credits, category, optional subcategory, site publication date, and a sanitized
third-party player URL. It does **not** contain the site's editorial prose,
images, audio, video, view counts, cut statistics, motion, lighting claims,
or inferred visual styles.

## Refresh and validate

From the repository root:

```bash
PYTHONPATH=src python -m kumiki_reference_lab directors-library snapshot \
  --pages 2 --retrieved-on 2026-11-11 \
  --out research/analysis/directors-library/index-2026-11-11.json

PYTHONPATH=src python -m kumiki_reference_lab directors-library validate \
  --snapshot research/analysis/directors-library/index-2026-11-11.json

PYTHONPATH=src python -m kumiki_reference_lab directors-library report \
  --snapshot research/analysis/directors-library/index-2026-11-11.json
```

One archive page contains up to 15 entries. The importer is explicitly
bounded to 1–5 archive pages (at most 75 film-page requests), makes no
requests to Vimeo/YouTube or direct media endpoints, rejects foreign hosts
and redirects, and caps page payloads. The snapshot is immutable: choose a
new dated filename if the contents change. Page ordering and credits are
those observed on the retrieval date, not guaranteed exhaustive coverage.

`sitePublishedOn` is the Directors' Library page date, which may be different
from the video's actual first release. `videoAnalysisStatus: not-performed`, `rightsStatus: permission-required`,
and the zero-measurement totals are intentional. An embed URL means a player
is offered, **not** that the file is licensed for download or that it has
been watched. Unknown view counts and runtimes stay null. Do not count the
metadata rows as cinematographic observations.

## Actual film analysis: permission gate

The site's [January 2026 terms](https://directorslibrary.com/cookies-legal/)
restrict use to lawful, personal, non-commercial purposes, and prohibit
copying content without permission. The site also notes that Vimeo and
YouTube embeds are third-party media. Do not download a player stream just
because it is publicly playable, use login/cookie bypass, or assume
permission from the site to copy a contributor's work.

For a film with rights-holder authorization or an independently licensed
source file, verify that the local file is the exact edition represented
by the catalog page. Existing source-hashed analyzers can then run:

```bash
PYTHONPATH=src python -m kumiki_reference_lab study-reference \
  /path/to/authorized-source.mp4 --out runs/directors-library \
  --max-seconds 20 --rights-status user-declared-authorized
```

Keep the acquired source in an ephemeral folder outside Git, with cleanup
on success and failure. Existing `study-reference` output is local and may
contain source frames; review it before exporting only approved numerical
evidence to the tracked research directory. The current snapshot intentionally
contains **no footage-derived observations**. Future per-film datasets should
record source SHA-256, edition identity, exact original PTS windows, sampling
coverage, provisional cut/motion/color/audio measurements, and human-review
status separately. Never assert a physical camera move, lighting setup,
character identity, or verified creative choice from an automatic proxy.
