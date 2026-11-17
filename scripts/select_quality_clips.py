#!/usr/bin/env python3
"""Turn the stored catalog quality signals into per-site target lists.

The six site catalogs under ``research/analysis/`` were collected by
"newest available" harvests, so the measured corpus over-represents recency.
This tool reads the catalogs (never the media, never the network) and writes a
justified, ordered selection per site plus one cross-site report.

Selection rules (implemented verbatim below; repeated in the report)
---------------------------------------------------------------------
**motiondesignawards** (``projects[]``)

1. ``awards[].type`` intersects ``{VOTM, VOTY, DOTY, SOTY}`` (award of the
   month/year, design of the year, site of the year — jury-style honours, as
   opposed to the daily vote).
2. ``VOTD`` in ``awards[].type`` **and** ``scores.overall >= 8.0``.
3. ``scores.overall >= 8.5``.

Order: tier asc, ``scores.overall`` desc, ``totalVotes`` desc.

**aicp** (``entries[]``)

1. ``categories[]`` intersects ``{Advertising Excellence, Advertising
   Excellence / Campaign, Advertising Excellence / International, Best of
   Region, National Campaign, Integrated Campaign}``.
2. ``categories[]`` non-empty **and** ``year <= 2023`` (the archive years are
   under-represented by the newest-first harvest; this is a *coverage* rule,
   not a quality claim about older work).

Order: tier asc, ``year`` asc, ``title`` asc.

**promonews** (``videos[]``)

1. ``categories[]`` contains a ``UKMVAs <year> winner`` tag.
2. ``categories[]`` contains a ``UKMVAs <year> nominee`` tag.
3. ``categories[]`` contains ``Pick of the Day``.

Order: tier asc, ``publishedDate`` asc.

**directorslibrary** (``items[]``)

1. ``terms.award[]`` non-empty.
2. ``terms.festival[]`` intersects ``{Cannes, Sundance, Venice Biennale,
   Toronto (TIFF), Berlinale, SXSW}``.

Order: tier asc, ``publicationDate`` asc.

**shots** (``clips[]``)

1. ``brandName == "Straight 8"``.
2. ``clientName`` and ``agencyName`` and ``artists[]`` and ``year`` all
   non-empty. This is a **documentation-completeness proxy only**. shots.net
   publishes no editorial or award field (``awards``, ``categories`` and
   ``productionCompanies`` are empty on every row), so this tier says the row
   carries enough metadata to be *interpretable*, not that the work is good.

Order: tier asc, ``year`` desc.

**stash** — no video selection: the catalog has no quality field at all
(``Featured`` is true on 91.9% of rows) and most posts are image galleries.
The exclusion and its reason are recorded in ``stash/quality-selection.json``.

**Cross-site boost (tier 0).** A work that appears on two or more sites is the
strongest signal available here. Matching is on normalised title + company and
normalised title + director: NFKD, ASCII-folded, lowercased, ``&`` -> ``and``,
all other punctuation collapsed to single spaces, and promonews' title suffix
``" by <director>"`` stripped. Works are joined transitively (union-find) over
those keys. A matching row gets ``crossSite: [sites]`` and ``rankTier: 0``; its
``tier`` and ``tierReason`` are left untouched. Tier 0 exists **only in the
ranking order**, so the report can show both the rule tier and the promotion.

What each site uses for matching
--------------------------------
- company: MDA ``studio``; AICP ``company``; promonews ``credits`` role
  ``Production Company``; Directors' Library ``terms.agency[]``; shots
  ``clientName``/``agencyName``.
- director: promonews ``credits`` role ``Director``; shots ``artists[]``
  (they are directors on this site). MDA, AICP and Directors' Library publish
  no director field, so they only take part in company matching.

Rows and cohorts
----------------
Every row carries ``id`` (the catalog's own id, same type: ``projectId`` is a
string, ``nid``/``postId``/shots ``id`` are ints), ``slug``, ``title``,
``tier``, ``rankTier``, ``tierReason`` (the predicate values that matched),
``qualitySignals`` (only signals that exist on that site), ``crossSite``,
``alreadyVideoMeasured``/``alreadyCensusMeasured``/``alreadyAudioMeasured``
(read from ``index.json``, ``census-index.json`` and ``audio-index.json``), and
``missingFrom`` (lanes with no on-disk record). Every row also carries
``cohort`` — the size and already-measured counts of its rule tier — and each
site records ``cohorts`` plus a ``bias`` string naming what its rule
over-samples, so a rate from a 3-row cohort is not read like a rate from a
2,000-row one.

Outputs (all deterministic; two runs are byte-identical)
-------------------------------------------------------
- ``<root>/<site>/quality-selection.json`` — schema
  ``kumiki.<site>-quality-selection.v1``.
- ``<root>/<site>/ids.json`` — ``{"ids": [...]}``, consumable by the harvest
  drivers' ``--ids-file``.
- ``<root>/quality-selection.md`` and ``<root>/quality-selection.json`` — the
  cross-site report and its machine summary (schema
  ``kumiki.quality-selection.v1``).
- ``<root>/all-ids.json`` — ``{"ids": [...], "bySite": {...}}``. Site ids are
  site-local (a shots id and a promonews id can collide numerically), so use
  ``<site>/ids.json`` when driving one site; ``bySite`` is the unambiguous
  form.

Usage::

    PYTHONPATH=src python scripts/select_quality_clips.py \
        --root research/analysis
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

DEFAULT_ROOT = Path("research/analysis")

SITES = ("motiondesignawards", "aicp", "promonews", "directorslibrary", "shots",
         "stash")
SELECTED_SITES = SITES[:-1]
LANES = ("video", "census", "audio")
LANE_FILES = {
    "video": "index.json",
    "census": "census-index.json",
    "audio": "audio-index.json",
}
# Each catalog's own identifier field; ``id`` is echoed with this name's type.
ID_FIELDS = {
    "motiondesignawards": "projectId",
    "aicp": "id",
    "promonews": "nid",
    "directorslibrary": "id",
    "shots": "id",
    "stash": "id",
}
VIDEO_INDEX_ID_KEYS = {
    "motiondesignawards": ("projectId",),
    "aicp": ("id",),
    "promonews": ("nid",),
    "directorslibrary": ("postId",),
    "shots": ("clipId",),
}
CATALOG_ITEMS = {
    "motiondesignawards": "projects",
    "aicp": "entries",
    "promonews": "videos",
    "directorslibrary": "items",
    "shots": "clips",
    "stash": "items",
}

MDA_AWARD_TIER1 = ("DOTY", "SOTY", "VOTM", "VOTY")
MDA_VOTD = "VOTD"
AICP_TIER1_CATEGORIES = (
    "Advertising Excellence",
    "Advertising Excellence / Campaign",
    "Advertising Excellence / International",
    "Best of Region",
    "National Campaign",
    "Integrated Campaign",
)
DL_TIER2_FESTIVALS = ("Cannes", "Sundance", "Venice Biennale",
                      "Toronto (TIFF)", "Berlinale", "SXSW")
PROMONEWS_WINNER = re.compile(r"^UKMVAs \d{4} winner$")
PROMONEWS_NOMINEE = re.compile(r"^UKMVAs \d{4} nominee$")
PROMONEWS_PICK = "Pick of the Day"

BIAS = {
    "motiondesignawards": (
        "Crowd vote, not jury: `scores.overall` is an open audience average and "
        "VOTD/VOTM are daily/monthly vote wins, so tiers 1-2 over-sample work "
        "with an active voting audience. Tiers 2-3 over-sample recent, "
        "high-traffic uploads because the top of the score distribution is thin. "
        "The rule cannot see craft: a well-voted but conventional piece ranks "
        "above an unvoted experimental one."
    ),
    "aicp": (
        "Prize categories favour big-budget, US-agency work ('Advertising "
        "Excellence', 'Best of Region', 'National Campaign'), so tier 1 "
        "over-samples large production companies and award-show entries. Tier 2 "
        "(`year <= 2023`) deliberately over-samples older archive years, whose "
        "categories are sparser and whose downloadable renditions are less "
        "reliable; it is a coverage correction, not a claim that older work is "
        "better. 134 of 2,715 entries carry no category and cannot enter at all."
    ),
    "promonews": (
        "UK-only music video coverage: every selected row is a British promo, so "
        "no non-UK or non-music-video work can enter. Tier 1-2 over-sample "
        "UKMVAs winners/nominees, and the CMS only tags 2018 and 2022-2026, so "
        "the tier is also a recent-years filter. Tier 3 over-samples 2018+ "
        "'Pick of the Day' promos. Festival and long-form work is invisible."
    ),
    "directorslibrary": (
        "Festival films, not music videos: the site is a directors' directory of "
        "shorts, commercials and features, so tiers 1-2 over-sample narrative "
        "shorts that premiered at Cannes/Sundance/Venice/TIFF/Berlinale/SXSW. "
        "The 461 `terms.festival[]` and 69 `terms.award[]` tags are editor-applied "
        "and unevenly maintained across 5,412 items, so absence of a tag is not "
        "absence of quality."
    ),
    "shots": (
        "Tier 1 is the 9 'Straight 8' entries, a sponsor contest rather than a "
        "quality ranking. Tier 2 is explicitly a documentation-completeness "
        "proxy (client + agency + artists[] + year), not a quality claim: it "
        "over-samples recent, fully credited commercial work from large agencies "
        "and excludes 27,701 clips with no year and 15,550 with no agency, "
        "regardless of how good they are. shots.net publishes no editorial or "
        "award signal at all."
    ),
    "stash": (
        "No selection: STASH exposes no quality field (`Featured` is true on "
        "91.9% of rows) and many posts are image galleries rather than videos."
    ),
}

RULES: dict[str, list[dict[str, Any]]] = {
    "motiondesignawards": [
        {"tier": 1,
         "predicate": "awards[].type intersects {DOTY, SOTY, VOTM, VOTY}"},
        {"tier": 2,
         "predicate": "awards[].type contains VOTD and scores.overall >= 8.0"},
        {"tier": 3, "predicate": "scores.overall >= 8.5"},
    ],
    "aicp": [
        {"tier": 1,
         "predicate": "categories[] intersects {Advertising Excellence, "
                      "Advertising Excellence / Campaign, Advertising "
                      "Excellence / International, Best of Region, National "
                      "Campaign, Integrated Campaign}"},
        {"tier": 2,
         "predicate": "categories[] non-empty and year <= 2023"},
    ],
    "promonews": [
        {"tier": 1, "predicate": "categories[] contains 'UKMVAs <year> winner'"},
        {"tier": 2,
         "predicate": "categories[] contains 'UKMVAs <year> nominee'"},
        {"tier": 3, "predicate": "categories[] contains 'Pick of the Day'"},
    ],
    "directorslibrary": [
        {"tier": 1, "predicate": "terms.award[] non-empty"},
        {"tier": 2,
         "predicate": "terms.festival[] intersects {Cannes, Sundance, Venice "
                      "Biennale, Toronto (TIFF), Berlinale, SXSW}"},
    ],
    "shots": [
        {"tier": 1, "predicate": "brandName == 'Straight 8'"},
        {"tier": 2,
         "predicate": "clientName, agencyName, artists[] and year all non-empty "
                      "(documentation-completeness proxy, not a quality claim)"},
    ],
    "stash": [],
}

ORDER = {
    "motiondesignawards": "tier asc, scores.overall desc, totalVotes desc",
    "aicp": "tier asc, year asc, title asc",
    "promonews": "tier asc, publishedDate asc",
    "directorslibrary": "tier asc, publicationDate asc",
    "shots": "tier asc, year desc",
    "stash": "none",
}

STASH_EXCLUSION = (
    "STASH has no quality field: `Featured` is true on 91.9% of 5,399 posts and "
    "the catalog publishes no awards, categories or festival terms. It also "
    "mixes image galleries with videos. Selecting 'featured' rows would rank "
    "the site's own promotion, not work quality, so no video target list is "
    "emitted. STASH still has 5,277 measured stills and can supply poster-level "
    "evidence."
)


# --------------------------------------------------------------------------- #
# Reading and normalising
# --------------------------------------------------------------------------- #


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _norm_id(value: Any) -> str:
    return str(value)


def normalise_text(value: Any) -> str:
    """NFKD, ASCII, lowercase, ``&`` -> ``and``, punctuation -> spaces."""
    if not isinstance(value, str):
        return ""
    folded = unicodedata.normalize("NFKD", value)
    ascii_text = folded.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower().replace("&", " and ")
    tokens = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(tokens.split())


def strip_promonews_suffix(title: Any) -> str:
    """Drop promonews' ``" by <director>"`` title suffix, keeping the rest."""
    if not isinstance(title, str):
        return ""
    if " by " in title:
        head = title.rsplit(" by ", 1)[0]
        if head.strip():
            return head
    return title


def _title_matches(text: Any) -> str:
    """Normalised title used for cross-site matching."""
    return normalise_text(strip_promonews_suffix(text))


def _credits(item: dict[str, Any], role: str) -> list[str]:
    return [str(credit.get("name")) for credit in item.get("credits") or []
            if isinstance(credit, dict) and credit.get("role") == role
            and credit.get("name")]


def _companies(site: str, item: dict[str, Any]) -> list[str]:
    if site == "motiondesignawards":
        return _as_list(item.get("studio"))
    if site == "aicp":
        return _as_list(item.get("company"))
    if site == "promonews":
        return _credits(item, "Production Company")
    if site == "directorslibrary":
        return _as_list((item.get("terms") or {}).get("agency"))
    if site == "shots":
        return [value for value in (item.get("clientName"),
                                    item.get("agencyName")) if value]
    return []


def _directors(site: str, item: dict[str, Any]) -> list[str]:
    if site == "promonews":
        return _credits(item, "Director")
    if site == "shots":
        return _as_list(item.get("artists"))
    return []


# --------------------------------------------------------------------------- #
# Measured lanes
# --------------------------------------------------------------------------- #


@dataclass
class Measured:
    """Ids with an on-disk record, per lane."""

    ids: dict[str, set[str]] = field(
        default_factory=lambda: {lane: set() for lane in LANES})
    available: dict[str, bool] = field(
        default_factory=lambda: {lane: False for lane in LANES})

    def has(self, lane: str, ident: Any) -> bool:
        return _norm_id(ident) in self.ids[lane]

    def count(self, lane: str, rows: Iterable[dict[str, Any]]) -> int:
        return sum(1 for row in rows if self.has(lane, row["id"]))


def _index_ids(site: str, lane: str, records: Any) -> set[str]:
    keys = (VIDEO_INDEX_ID_KEYS[site],) if lane == "video" else ()
    keys = keys + ("id", "projectId", "postId", "clipId", "nid")
    found: set[str] = set()
    for record in records or []:
        if not isinstance(record, dict):
            continue
        for key in keys:
            if record.get(key) is not None:
                found.add(_norm_id(record[key]))
                break
    return found


def load_measured(root: Path, site: str) -> Measured:
    measured = Measured()
    for lane in LANES:
        path = root / site / LANE_FILES[lane]
        if not path.is_file():
            continue
        payload = _read_json(path) or {}
        measured.available[lane] = True
        measured.ids[lane] = _index_ids(site, lane, payload.get("records"))
    return measured


# --------------------------------------------------------------------------- #
# Cross-site matching
# --------------------------------------------------------------------------- #


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[tuple[str, str], tuple[str, str]] = {}

    def find(self, node: tuple[str, str]) -> tuple[str, str]:
        parent = self.parent.setdefault(node, node)
        while parent != node:
            grand = self.parent.setdefault(parent, parent)
            self.parent[node] = grand
            node, parent = parent, grand
        return node

    def union(self, left: tuple[str, str], right: tuple[str, str]) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            # Deterministic: the smaller node key becomes the root.
            if right_root < left_root:
                left_root, right_root = right_root, left_root
            self.parent[right_root] = left_root


def compute_cross_site(
    catalogs: dict[str, list[dict[str, Any]]],
) -> tuple[
    dict[tuple[str, str], list[str]],
    dict[tuple[str, str], int],
    dict[int, list[tuple[str, str]]],
    dict[tuple[str, str], str],
]:
    """Return ``(cross_site, component, components, titles)``.

    ``cross_site`` lists the *other* sites the work also appears on (empty when
    the work is single-site). ``component`` maps each work to a stable
    component number, ``components`` maps that number to all its members
    (selected or not), and ``titles`` keeps each work's display title.
    """
    keyed: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    works: dict[tuple[str, str], tuple[str, list[str], list[str]]] = {}
    titles: dict[tuple[str, str], str] = {}
    for site in SELECTED_SITES:
        for item in catalogs.get(site) or []:
            if not isinstance(item, dict):
                continue
            ident = item.get(ID_FIELDS[site])
            if ident is None:
                continue
            node = (site, _norm_id(ident))
            title = _title_matches(item.get("title"))
            companies = [normalise_text(value)
                         for value in _companies(site, item)]
            directors = [normalise_text(value)
                         for value in _directors(site, item)]
            companies = [value for value in companies if value]
            directors = [value for value in directors if value]
            works[node] = (title, companies, directors)
            titles[node] = str(item.get("title") or "")
            if not title:
                continue
            for kind, values in (("company", companies),
                                 ("director", directors)):
                for value in values:
                    keyed[(kind, title, value)].append(node)

    union = _UnionFind()
    for nodes in keyed.values():
        first = nodes[0]
        union.find(first)
        for node in nodes[1:]:
            union.union(first, node)

    members: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for node in works:
        members[union.find(node)].add(node)

    component_ids: dict[tuple[str, str], int] = {}
    components: dict[int, list[tuple[str, str]]] = {}
    # A stable order: components sorted by their smallest member key.
    roots = sorted(members, key=lambda root: min(members[root]))
    cross_site: dict[tuple[str, str], list[str]] = {}
    for number, root in enumerate(roots, start=1):
        group = members[root]
        components[number] = sorted(group)
        sites = {site for site, _ in group}
        for node in group:
            component_ids[node] = number
            others = sorted(sites - {node[0]})
            if len(sites) > 1:
                cross_site[node] = others
    return cross_site, component_ids, components, titles


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #


def _row(
    ident: Any,
    slug: Any,
    title: Any,
    tier: int,
    reason: str,
    signals: dict[str, Any],
    measured: Measured,
    cross: list[str] | None,
) -> dict[str, Any]:
    flags = {f"already{lane.capitalize()}Measured": measured.has(lane, ident)
             for lane in LANES}
    return {
        "id": ident,
        "slug": slug,
        "title": title,
        "tier": tier,
        "rankTier": 0 if cross else tier,
        "tierReason": reason,
        "qualitySignals": signals,
        "crossSite": cross or [],
        **flags,
        "missingFrom": [lane for lane in LANES
                        if not flags[f"already{lane.capitalize()}Measured"]],
    }


def _matched(values: Iterable[str], allowed: Iterable[str]) -> list[str]:
    allowed_set = set(allowed)
    seen: list[str] = []
    for value in values:
        if value in allowed_set and value not in seen:
            seen.append(value)
    return sorted(seen)


def _select_mda(items, measured, cross):
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = item.get(ID_FIELDS["motiondesignawards"])
        if ident is None:
            continue
        awards = [award.get("type") for award in _as_list(item.get("awards"))
                  if isinstance(award, dict) and award.get("type")]
        overall = (item.get("scores") or {}).get("overall")
        votes = item.get("totalVotes")
        signals: dict[str, Any] = {"awardTypes": sorted(set(awards))}
        if overall is not None:
            signals["overall"] = overall
        if votes is not None:
            signals["totalVotes"] = votes
        if item.get("category"):
            signals["category"] = item["category"]
        if item.get("studio"):
            signals["studio"] = item["studio"]

        honours = _matched(awards, MDA_AWARD_TIER1)
        if honours:
            tier = 1
            reason = (f"awards[].type intersects {list(MDA_AWARD_TIER1)} = "
                      f"{honours}")
        elif MDA_VOTD in awards and overall is not None and overall >= 8.0:
            tier = 2
            reason = (f"awards[].type contains {MDA_VOTD} and scores.overall "
                      f"{overall} >= 8.0")
        elif overall is not None and overall >= 8.5:
            tier = 3
            reason = f"scores.overall {overall} >= 8.5"
        else:
            continue
        node = ("motiondesignawards", _norm_id(ident))
        rows.append(_row(ident, item.get("slug"), item.get("title"), tier,
                         reason, signals, measured, cross.get(node)))
    rows.sort(key=lambda row: (
        row["rankTier"],
        -(row["qualitySignals"].get("overall") or 0.0),
        -(row["qualitySignals"].get("totalVotes") or 0),
        (row["title"] or "").casefold(),
        _norm_id(row["id"]),
    ))
    return rows


def _select_aicp(items, measured, cross):
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = item.get(ID_FIELDS["aicp"])
        if ident is None:
            continue
        categories = [value for value in _as_list(item.get("categories"))
                      if isinstance(value, str)]
        year = item.get("year")
        signals: dict[str, Any] = {"categories": sorted(set(categories))}
        if year is not None:
            signals["year"] = year
        if item.get("company"):
            signals["company"] = item["company"]
        if item.get("videoType"):
            signals["videoType"] = _as_list(item["videoType"])

        honours = _matched(categories, AICP_TIER1_CATEGORIES)
        if honours:
            tier = 1
            reason = (f"categories[] intersects {list(AICP_TIER1_CATEGORIES)} "
                      f"= {honours}")
        elif categories and year is not None and year <= 2023:
            tier = 2
            reason = (f"categories[] non-empty ({len(categories)}) and year "
                      f"{year} <= 2023")
        else:
            continue
        node = ("aicp", _norm_id(ident))
        rows.append(_row(ident, item.get("slug"), item.get("title"), tier,
                         reason, signals, measured, cross.get(node)))
    rows.sort(key=lambda row: (
        row["rankTier"],
        row["qualitySignals"].get("year") is None,
        row["qualitySignals"].get("year") or 0,
        (row["title"] or "").casefold(),
        _norm_id(row["id"]),
    ))
    return rows


def _select_promonews(items, measured, cross):
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = item.get(ID_FIELDS["promonews"])
        if ident is None:
            continue
        categories = [value for value in _as_list(item.get("categories"))
                      if isinstance(value, str)]
        winners = sorted({value for value in categories
                          if PROMONEWS_WINNER.match(value)})
        nominees = sorted({value for value in categories
                           if PROMONEWS_NOMINEE.match(value)})
        picked = PROMONEWS_PICK in categories
        if winners:
            tier, reason = 1, f"categories[] contains {winners}"
        elif nominees:
            tier, reason = 2, f"categories[] contains {nominees}"
        elif picked:
            tier, reason = 3, f"categories[] contains {PROMONEWS_PICK!r}"
        else:
            continue
        cited = sorted(set(winners + nominees
                           + ([PROMONEWS_PICK] if picked else [])))
        signals: dict[str, Any] = {"categories": cited}
        if item.get("publishedDate"):
            signals["publishedDate"] = item["publishedDate"]
        if item.get("genres"):
            signals["genres"] = sorted(set(_as_list(item["genres"])))
        directors = _credits(item, "Director")
        if directors:
            signals["directors"] = sorted(set(directors))
        node = ("promonews", _norm_id(ident))
        rows.append(_row(ident, item.get("slug"), item.get("title"), tier,
                         reason, signals, measured, cross.get(node)))
    rows.sort(key=lambda row: (
        row["rankTier"],
        row["qualitySignals"].get("publishedDate") or "9999-99-99",
        _norm_id(row["id"]),
    ))
    return rows


def _select_directorslibrary(items, measured, cross):
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = item.get(ID_FIELDS["directorslibrary"])
        if ident is None:
            continue
        terms = item.get("terms") or {}
        awards = [value for value in _as_list(terms.get("award"))
                  if isinstance(value, str)]
        festivals = [value for value in _as_list(terms.get("festival"))
                     if isinstance(value, str)]
        if awards:
            tier = 1
            reason = (f"terms.award[] non-empty ({len(awards)}) = "
                      f"{sorted(set(awards))}")
        else:
            honours = _matched(festivals, DL_TIER2_FESTIVALS)
            if not honours:
                continue
            tier = 2
            reason = (f"terms.festival[] intersects {list(DL_TIER2_FESTIVALS)} "
                      f"= {honours}")
        signals: dict[str, Any] = {}
        if awards:
            signals["awards"] = sorted(set(awards))
        if festivals:
            signals["festivals"] = sorted(set(festivals))
        for name in ("categories", "agency", "record_label", "format"):
            values = [value for value in _as_list(terms.get(name))
                      if isinstance(value, str)]
            if values:
                signals[name] = sorted(set(values))
        if item.get("publicationDate"):
            signals["publicationDate"] = item["publicationDate"]
        node = ("directorslibrary", _norm_id(ident))
        rows.append(_row(ident, item.get("slug"), item.get("title"), tier,
                         reason, signals, measured, cross.get(node)))
    rows.sort(key=lambda row: (
        row["rankTier"],
        row["qualitySignals"].get("publicationDate") or "9999-99-99T99",
        _norm_id(row["id"]),
    ))
    return rows


def _select_shots(items, measured, cross):
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = item.get(ID_FIELDS["shots"])
        if ident is None:
            continue
        brand = item.get("brandName")
        complete = bool(item.get("clientName") and item.get("agencyName")
                        and item.get("artists") and item.get("year"))
        if brand == "Straight 8":
            tier = 1
            reason = "brandName == 'Straight 8'"
        elif complete:
            tier = 2
            reason = ("clientName, agencyName, artists[] and year all "
                      "non-empty (documentation-completeness proxy, not a "
                      "quality claim)")
        else:
            continue
        signals: dict[str, Any] = {}
        if brand:
            signals["brandName"] = brand
        if item.get("clientName"):
            signals["clientName"] = item["clientName"]
        if item.get("agencyName"):
            signals["agencyName"] = item["agencyName"]
        artists = [value for value in _as_list(item.get("artists"))
                   if isinstance(value, str)]
        if artists:
            signals["artists"] = sorted(set(artists))
        if item.get("year"):
            signals["year"] = item["year"]
        if item.get("categories"):
            signals["categories"] = sorted(set(_as_list(item["categories"])))
        node = ("shots", _norm_id(ident))
        rows.append(_row(ident, item.get("slug"), item.get("title"), tier,
                         reason, signals, measured, cross.get(node)))
    rows.sort(key=lambda row: (
        row["rankTier"],
        row["qualitySignals"].get("year") is None,
        -(row["qualitySignals"].get("year") or 0),
        (row["title"] or "").casefold(),
        _norm_id(row["id"]),
    ))
    return rows


SELECTORS = {
    "motiondesignawards": _select_mda,
    "aicp": _select_aicp,
    "promonews": _select_promonews,
    "directorslibrary": _select_directorslibrary,
    "shots": _select_shots,
}


def _cohorts(rows: list[dict[str, Any]], measured: Measured) -> dict[str, Any]:
    cohorts: dict[str, Any] = {}
    for tier in sorted({row["tier"] for row in rows}):
        members = [row for row in rows if row["tier"] == tier]
        cohorts[str(tier)] = {
            "size": len(members),
            **{f"already{lane.capitalize()}Measured":
               measured.count(lane, members) for lane in LANES},
        }
    return cohorts


def build_site(
    root: Path,
    site: str,
    catalogs: dict[str, list[dict[str, Any]]],
    cross_site: dict[tuple[str, str], list[str]],
) -> dict[str, Any]:
    items = catalogs.get(site) or []
    measured = load_measured(root, site)
    source = {
        "catalog": f"{site}/catalog.json",
        "catalogSchema": catalogs.get("_schemas", {}).get(site),
        "catalogItems": len(items),
        "indexes": {lane: f"{site}/{LANE_FILES[lane]}"
                    for lane in LANES
                    if (root / site / LANE_FILES[lane]).is_file()},
    }
    payload: dict[str, Any] = {
        "schemaVersion": f"kumiki.{site}-quality-selection.v1",
        "site": site,
        "lanes": list(LANES),
        "order": ORDER[site],
        "rules": RULES[site],
        "bias": BIAS[site],
        "source": source,
    }

    if site == "stash":
        payload.update({
            "selection": "excluded",
            "excluded": {"reason": STASH_EXCLUSION},
            "counts": {"catalogItems": len(items), "selected": 0,
                       "crossSite": 0, "byTier": {}},
            "cohorts": {},
            "rows": [],
        })
        return payload

    rows = SELECTORS[site](items, measured, cross_site)
    cohorts = _cohorts(rows, measured)
    for row in rows:
        row["cohort"] = cohorts[str(row["tier"])]
    by_tier = Counter(str(row["tier"]) for row in rows)
    tier0 = [row for row in rows if row["rankTier"] == 0]
    payload.update({
        "selection": "tiered",
        "counts": {
            "catalogItems": len(items),
            "selected": len(rows),
            "crossSite": len(tier0),
            "byTier": dict(sorted(by_tier.items())),
        },
        "cohorts": cohorts,
        "tier0": {
            "count": len(tier0),
            "originalTiers": dict(sorted(Counter(
                str(row["tier"]) for row in tier0).items())),
        },
        "rows": rows,
    })
    return payload


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def _ids_for(payload: dict[str, Any]) -> list[Any]:
    return [row["id"] for row in payload.get("rows") or []]


def _percent(count: int, size: int) -> str:
    if not size:
        return "—"
    return f"{count} ({100 * count / size:.0f}%)"


def _cohort_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| tier | cohort | video | census | audio |",
        "|---:|---:|---:|---:|---:|",
    ]
    for tier, cohort in payload.get("cohorts", {}).items():
        lines.append(
            f"| {tier} | {cohort['size']} | "
            f"{_percent(cohort['alreadyVideoMeasured'], cohort['size'])} | "
            f"{_percent(cohort['alreadyCensusMeasured'], cohort['size'])} | "
            f"{_percent(cohort['alreadyAudioMeasured'], cohort['size'])} |")
    return lines


def _component_groups(
    payloads: dict[str, dict[str, Any]],
    component: dict[tuple[str, str], int],
    components: dict[int, list[tuple[str, str]]],
    titles: dict[tuple[str, str], str],
) -> tuple[dict[int, dict[str, Any]], int]:
    """Group selected tier-0 rows by cross-site work.

    Returns the groups that contain at least one selected row, plus the total
    number of works that span two or more sites.
    """
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for site, payload in payloads.items():
        for row in payload.get("rows") or []:
            if row["crossSite"]:
                selected[(site, _norm_id(row["id"]))] = row
    grouped: dict[int, dict[str, Any]] = {}
    cross_site_works = 0
    for number, members in components.items():
        if len({site for site, _ in members}) < 2:
            continue
        cross_site_works += 1
        hits = [(node, selected[node]) for node in members if node in selected]
        if not hits:
            continue
        grouped[number] = {
            "title": titles.get(members[0]) or "(untitled)",
            "members": members,
            "selected": hits,
        }
    return grouped, cross_site_works


def build_report(
    payloads: dict[str, dict[str, Any]],
    component: dict[tuple[str, str], int],
    components: dict[int, list[tuple[str, str]]],
    titles: dict[tuple[str, str], str],
    all_ids: dict[str, Any],
) -> str:
    lines: list[str] = [
        "# Quality-first clip selection",
        "",
        "Generated offline by `scripts/select_quality_clips.py` from the stored",
        "catalogs and indexes under `research/analysis/`. No media was fetched and",
        "nothing in `videos/`, `census/` or `audio/` was written.",
        "",
        "The selection is not a claim that these are the best works on the web. It",
        "is a claim that these are the rows the stored catalogs can *justify*, and",
        "each section states what its rule over-samples.",
        "",
        "## Rules",
        "",
        "Applied in tier order; a row enters the first tier it matches, so each",
        "work appears at most once per site.",
        "",
    ]
    for site in SELECTED_SITES:
        lines.append(f"### {site}")
        lines.append("")
        for rule in RULES[site]:
            lines.append(f"{rule['tier']}. `{rule['predicate']}`")
        lines.append("")
        lines.append(f"Order: {ORDER[site]}.")
        lines.append("")
        lines.append(f"**Bias:** {BIAS[site]}")
        lines.append("")
    lines.extend([
        "### stash",
        "",
        "No video selection.",
        "",
        f"{STASH_EXCLUSION}",
        "",
        "## Cross-site works (tier 0)",
        "",
        "A work on two or more sites outranks any single-site tier. Matching is on",
        "normalised title + company and title + director (NFKD, lowercase, `&` ->",
        "`and`, punctuation collapsed, promonews' `\" by <director>\"` suffix",
        "stripped) and is joined transitively. `rankTier` is 0 for these rows while",
        "`tier` keeps the rule that selected them.",
        "",
    ])
    grouped, cross_site_works = _component_groups(payloads, component,
                                                  components, titles)
    tier0_rows = sum(len(group["selected"]) for group in grouped.values())
    lines.append(
        f"{tier0_rows} selected rows come from {len(grouped)} of the "
        f"{cross_site_works} works that appear on two or more sites. A row is "
        "listed even when its partner on the other site was not selected.")
    lines.append("")
    if grouped:
        lines.extend([
            "| work | tier | members (selected rows carry their rule tier) |",
            "|---|---|---|",
        ])
        for number in sorted(grouped):
            group = grouped[number]
            selected = {node: row for node, row in group["selected"]}
            members = ", ".join(
                (f"`{site}` {ident} (tier {selected[(site, ident)]['tier']})"
                 if (site, ident) in selected
                 else f"`{site}` {ident} (not selected)")
                for site, ident in group["members"])
            tiers = "/".join(str(row["tier"]) for _, row in group["selected"])
            lines.append(f"| {group['title']} | {tiers} | {members} |")
        lines.append("")
    for site in SELECTED_SITES:
        payload = payloads[site]
        counts = payload["counts"]
        small = [tier for tier, cohort in payload.get("cohorts", {}).items()
                 if cohort["size"] < 10]
        warning = []
        if small:
            sizes = ", ".join(
                f"tier {tier} has {payload['cohorts'][tier]['size']} row(s)"
                for tier in small)
            warning = [f"Small-cohort warning: {sizes}; read those rates as "
                       "anecdotes, not estimates.", ""]
        lines.extend([
            f"## {site}",
            "",
            f"Catalog rows: {counts['catalogItems']:,}. Selected: "
            f"{counts['selected']:,} "
            f"({', '.join(f'tier {tier}: {size}' for tier, size in counts['byTier'].items())}"
            f"; cross-site tier 0: {counts['crossSite']}).",
            "",
            *_cohort_table(payload),
            "",
            *warning,
            f"`{site}/ids.json`: {len(_ids_for(payload)):,} ids. "
            f"The harvest drivers accept that file via `--ids-file`.",
            "",
            f"**Bias:** {payload['bias']}",
            "",
        ])
        if payload.get("tier0", {}).get("count"):
            lines.append(
                f"Tier-0 promotion keeps the original tier: "
                f"{payload['tier0']['originalTiers']}.")
            lines.append("")
    lines.extend([
        "## Combined file",
        "",
        f"`all-ids.json` lists {len(all_ids['ids']):,} ids in site order, with a",
        "`bySite` map. Site ids are site-local (a shots id and a promonews id can",
        "collide numerically), so drive one site at a time from",
        "`<site>/ids.json`, or read `bySite`.",
        "",
        "## Method notes",
        "",
        "- `already*Measured` is read from the on-disk indexes only: `index.json`",
        "  (video lane), `census-index.json`, `audio-index.json`. A missing index",
        "  file means the lane is unmeasured, not that the lane is unsupported.",
        "- Ids are the catalog's own identifier (`projectId`, `id`, `nid`), with",
        "  the catalog's type preserved, so `ids.json` drops straight into",
        "  `--ids-file`.",
        "- Cohort sizes are printed beside every already-measured count so a rate",
        "  from a 9-row shots tier is not read like a rate from a 2,349-row AICP",
        "  tier.",
        "- Two runs over unchanged catalogs and indexes produce byte-identical",
        "  outputs: no timestamps, no set iteration order, sorted tie-breaks.",
        "",
    ])
    return "\n".join(lines) + "\n"


def build_summary(payloads: dict[str, dict[str, Any]],
                  all_ids: dict[str, Any]) -> dict[str, Any]:
    per_site = {}
    for site in SITES:
        payload = payloads[site]
        per_site[site] = {
            "selection": payload["selection"],
            "counts": payload["counts"],
            "cohorts": payload["cohorts"],
            "bias": payload["bias"],
        }
    return {
        "schemaVersion": "kumiki.quality-selection.v1",
        "rules": RULES,
        "order": ORDER,
        "sites": per_site,
        "stashExclusion": STASH_EXCLUSION,
        "allIds": {site: len(all_ids["bySite"][site]) for site in SELECTED_SITES},
        "allIdsTotal": len(all_ids["ids"]),
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def run(root: Path) -> dict[str, Any]:
    catalogs: dict[str, list[dict[str, Any]]] = {"_schemas": {}}
    for site in SITES:
        payload = _read_json(root / site / "catalog.json")
        items = []
        if isinstance(payload, dict):
            catalogs["_schemas"][site] = payload.get("schemaVersion")
            items = payload.get(CATALOG_ITEMS[site]) or []
        catalogs[site] = items if isinstance(items, list) else []

    cross_site, component, components, titles = compute_cross_site(catalogs)
    payloads = {site: build_site(root, site, catalogs, cross_site)
                for site in SITES}

    by_site: dict[str, list[Any]] = {}
    for site in SITES:
        _write_json(root / site / "quality-selection.json", payloads[site])
    for site in SELECTED_SITES:
        ids = _ids_for(payloads[site])
        by_site[site] = ids
        _write_json(root / site / "ids.json", {"ids": ids})

    all_ids = {
        "ids": [ident for site in SELECTED_SITES for ident in by_site[site]],
        "bySite": by_site,
    }
    _write_json(root / "quality-selection.json", build_summary(payloads,
                                                               all_ids))
    _write_json(root / "all-ids.json", all_ids)
    (root / "quality-selection.md").write_text(
        build_report(payloads, component, components, titles, all_ids),
        encoding="utf-8")
    return {"payloads": payloads, "ids": all_ids}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build per-site quality-signal target lists and a report.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help="research analysis root (default: %(default)s)")
    args = parser.parse_args(argv)
    root: Path = args.root
    if not root.is_dir():
        print(f"no such analysis root: {root}", file=sys.stderr)
        return 2
    result = run(root)
    for site in SELECTED_SITES:
        counts = result["payloads"][site]["counts"]
        print(f"{site:20s} catalog={counts['catalogItems']:6d} "
              f"selected={counts['selected']:5d} "
              f"tier0={counts['crossSite']:4d} "
              f"ids={len(result['ids']['bySite'][site]):5d}")
    print(f"{'stash':20s} excluded (no quality signal)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
