"""Offline tests for the quality-signal selector.

Every fixture is a tiny synthetic catalog tree under a temporary root; no
network, no media, and no real ``research/analysis`` data is touched.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.select_quality_clips import (
    main,
    normalise_text,
    run,
    strip_promonews_suffix,
)

ITEMS_KEY = {
    "motiondesignawards": "projects",
    "aicp": "entries",
    "promonews": "videos",
    "directorslibrary": "items",
    "shots": "clips",
    "stash": "items",
}
SCHEMAS = {
    site: f"kumiki.{site}-catalog.v1" for site in ITEMS_KEY
}


def _project(ident, title, *, awards=(), overall=None, votes=1,
             studio=None):
    return {
        "projectId": ident,
        "slug": title.lower().replace(" ", "-"),
        "title": title,
        "scores": {"overall": overall},
        "totalVotes": votes,
        "awards": [{"type": value} for value in awards],
        "studio": studio,
        "category": "ADVERTISING_COMMERCIALS",
        "createdAt": "2024-01-01",
    }


def _entry(ident, title, *, year, categories=(), company=None):
    return {
        "id": ident,
        "slug": title.lower().replace(" ", "-"),
        "title": title,
        "year": year,
        "company": company,
        "categories": list(categories),
        "videoType": ["Commercial"],
    }


def _video(nid, title, *, published, categories=(), company=None,
           director=None):
    credits = []
    if director:
        credits.append({"role": "Director", "name": director})
    if company:
        credits.append({"role": "Production Company", "name": company})
    return {
        "nid": nid,
        "slug": title.lower().replace(" ", "-"),
        "title": title,
        "publishedDate": published,
        "categories": list(categories),
        "genres": ["Rap"],
        "credits": credits,
    }


def _item(ident, title, *, published, award=(), festival=(), agency=None):
    terms = {}
    if award:
        terms["award"] = list(award)
    if festival:
        terms["festival"] = list(festival)
    if agency:
        terms["agency"] = list(agency)
    return {
        "id": ident,
        "slug": title.lower().replace(" ", "-"),
        "title": title,
        "publicationDate": published,
        "terms": terms,
        "provider": "unsupported-embed",
    }


def _clip(ident, title, *, brand="shots", client=None, agency=None,
          artists=(), year=None):
    return {
        "id": ident,
        "slug": title.lower().replace(" ", "-"),
        "title": title,
        "publicationDate": "2024-01-01T00:00:00+00:00",
        "brandName": brand,
        "clientName": client,
        "agencyName": agency,
        "productionCompanies": [],
        "artists": list(artists),
        "categories": [],
        "awards": [],
        "year": year,
    }


def _write_index(path: Path, records) -> None:
    path.write_text(json.dumps({"schemaVersion": "test-index", "records": records}),
                    encoding="utf-8")


def build_root(root: Path, *, mda=(), aicp=(), promonews=(), directorslibrary=(),
               shots=(), stash=(), video_index=None, census_index=None,
               audio_index=None) -> None:
    payloads = {
        "motiondesignawards": mda,
        "aicp": aicp,
        "promonews": promonews,
        "directorslibrary": directorslibrary,
        "shots": shots,
        "stash": stash,
    }
    for site, items in payloads.items():
        folder = root / site
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "catalog.json").write_text(
            json.dumps({
                "schemaVersion": SCHEMAS[site],
                ITEMS_KEY[site]: list(items),
            }),
            encoding="utf-8")
    for name, records in (("index.json", video_index),
                          ("census-index.json", census_index),
                          ("audio-index.json", audio_index)):
        if records is None:
            continue
        for site, value in records.items():
            _write_index(root / site / name, value)


def _site(root: Path, site: str) -> dict:
    return json.loads((root / site / "quality-selection.json").read_text())


def _rows(root: Path, site: str) -> list[dict]:
    return _site(root, site)["rows"]


def _ids(root: Path, site: str) -> list:
    return [row["id"] for row in _rows(root, site)]


class SelectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, **kwargs) -> None:
        build_root(self.root, **kwargs)

    def run_all(self) -> dict:
        return run(self.root)

    # ------------------------------------------------------------------ #
    # Per-site tiers and ordering
    # ------------------------------------------------------------------ #

    def test_motiondesignawards_tiers_and_order(self) -> None:
        self.write(mda=[
            _project("100", "Alpha", awards=["VOTY"], overall=6.0),
            _project("200", "Bravo", awards=["VOTD"], overall=8.2, votes=10),
            _project("300", "Charlie", overall=8.6, votes=2),
            _project("400", "Delta", awards=["VOTD"], overall=7.9),
            _project("500", "Echo", overall=9.0, votes=500),
            _project("600", "Foxtrot", overall=8.6, votes=60),
        ])
        self.run_all()
        rows = _rows(self.root, "motiondesignawards")
        self.assertEqual([row["id"] for row in rows],
                         ["100", "200", "500", "600", "300"])
        self.assertEqual([row["tier"] for row in rows], [1, 2, 3, 3, 3])
        self.assertEqual(rows[0]["tierReason"],
                         "awards[].type intersects "
                         "['DOTY', 'SOTY', 'VOTM', 'VOTY'] = ['VOTY']")
        self.assertIn("8.2 >= 8.0", rows[1]["tierReason"])
        self.assertIn("9.0 >= 8.5", rows[2]["tierReason"])
        # projectId is a string in this catalog and stays a string.
        self.assertTrue(all(isinstance(row["id"], str) for row in rows))

    def test_aicp_tiers_order_and_id_key(self) -> None:
        self.write(aicp=[
            _entry("1", "Zed", year=2024, categories=["Best of Region"]),
            _entry("2", "Able", year=2020, categories=["Humor"]),
            _entry("3", "Baker", year=2019, categories=["Editorial"]),
            _entry("4", "Cain", year=2024, categories=["Animation"]),
            _entry("5", "Dora", year=None, categories=["Humor"]),
        ])
        self.run_all()
        rows = _rows(self.root, "aicp")
        self.assertEqual([row["id"] for row in rows], ["1", "3", "2"])
        self.assertEqual([row["tier"] for row in rows], [1, 2, 2])
        self.assertIn("year 2019 <= 2023", rows[1]["tierReason"])
        self.assertTrue(all(isinstance(row["id"], str) for row in rows))

    def test_promonews_tiers_and_order(self) -> None:
        self.write(promonews=[
            _video(60, "Song A", published="2020-01-01",
                   categories=["UKMVAs 2023 winner"]),
            _video(70, "Song B", published="2019-01-01",
                   categories=["UKMVAs 2023 nominee"]),
            _video(80, "Song C", published="2024-01-01",
                   categories=["Pick of the Day"]),
            _video(90, "Song D", published="2018-01-01",
                   categories=["Promos"]),
        ])
        self.run_all()
        rows = _rows(self.root, "promonews")
        self.assertEqual([row["id"] for row in rows], [60, 70, 80])
        self.assertEqual([row["tier"] for row in rows], [1, 2, 3])
        self.assertEqual(rows[0]["qualitySignals"]["categories"],
                         ["UKMVAs 2023 winner"])
        self.assertTrue(all(isinstance(row["id"], int) for row in rows))

    def test_directorslibrary_tiers_and_id_key(self) -> None:
        self.write(directorslibrary=[
            _item(1001, "Film One", published="2020-01-01",
                  award=["Palme d'Or (Cannes)"]),
            _item(1002, "Film Two", published="2019-01-01",
                  festival=["Cannes"]),
            _item(1003, "Film Three", published="2018-01-01",
                  festival=["Tribeca"]),
        ])
        self.run_all()
        rows = _rows(self.root, "directorslibrary")
        self.assertEqual([row["id"] for row in rows], [1001, 1002])
        self.assertEqual([row["tier"] for row in rows], [1, 2])
        self.assertEqual(rows[0]["qualitySignals"]["awards"],
                         ["Palme d'Or (Cannes)"])
        self.assertTrue(all(isinstance(row["id"], int) for row in rows))

    def test_shots_tiers_year_desc_and_completeness(self) -> None:
        self.write(shots=[
            _clip(501, "Eight", brand="Straight 8", year=2010),
            _clip(502, "Complete A", client="Acme", agency="Agency",
                  artists=["Dir"], year=2022),
            _clip(503, "Complete B", client="Acme", agency="Agency",
                  artists=["Dir"], year=2024),
            _clip(504, "Incomplete", client="Acme", artists=[], year=2023),
        ])
        self.run_all()
        rows = _rows(self.root, "shots")
        self.assertEqual([row["id"] for row in rows], [501, 503, 502])
        self.assertEqual([row["tier"] for row in rows], [1, 2, 2])
        self.assertIn("documentation-completeness proxy",
                      rows[1]["tierReason"])
        self.assertTrue(all(isinstance(row["id"], int) for row in rows))

    def test_stash_is_excluded_with_a_reason(self) -> None:
        self.write(stash=[{"id": 1, "title": "Gallery", "terms": {}}])
        payload = self.run_all()["payloads"]["stash"]
        self.assertEqual(payload["selection"], "excluded")
        self.assertEqual(payload["rows"], [])
        self.assertIn("no quality field", payload["excluded"]["reason"])
        self.assertFalse((self.root / "stash" / "ids.json").exists())
        report = (self.root / "quality-selection.md").read_text()
        self.assertIn("No video selection", report)

    # ------------------------------------------------------------------ #
    # Cross-site matching
    # ------------------------------------------------------------------ #

    def test_normalisation(self) -> None:
        self.assertEqual(normalise_text("Thank U, Next"), "thank u next")
        self.assertEqual(normalise_text("Piñata"), "pinata")
        self.assertEqual(normalise_text("X & Y"), normalise_text("X and Y"))
        self.assertEqual(normalise_text("  A -- B!! "), "a b")
        self.assertEqual(strip_promonews_suffix("Thank U, Next by Director"),
                         "Thank U, Next")
        self.assertEqual(strip_promonews_suffix("A Song"), "A Song")
        self.assertEqual(strip_promonews_suffix(" by Director"), " by Director")

    def test_cross_site_promotion_keeps_original_tier(self) -> None:
        self.write(
            mda=[_project("100", "Shared Spot", awards=["VOTD"], overall=8.2,
                          studio="Acme"),
                 _project("200", "Solo", awards=["VOTY"], overall=6.0)],
            shots=[_clip(501, "Shared Spot", client="Acme", agency="Agency",
                         artists=["Dir"], year=2024)],
        )
        self.run_all()
        mda_rows = _rows(self.root, "motiondesignawards")
        self.assertEqual(mda_rows[0]["id"], "100")
        promoted = mda_rows[0]
        self.assertEqual(promoted["tier"], 2)
        self.assertEqual(promoted["rankTier"], 0)
        self.assertEqual(promoted["crossSite"], ["shots"])
        self.assertIn("8.2 >= 8.0", promoted["tierReason"])
        shots_row = _rows(self.root, "shots")[0]
        self.assertEqual(shots_row["rankTier"], 0)
        self.assertEqual(shots_row["tier"], 2)
        self.assertEqual(shots_row["crossSite"], ["motiondesignawards"])
        # The other MDA row keeps its tier and its place behind tier 0.
        self.assertEqual((mda_rows[1]["tier"], mda_rows[1]["rankTier"]),
                         (1, 1))

    def test_cross_site_matches_stripped_title_and_director(self) -> None:
        self.write(
            promonews=[_video(60, "Thank U, Next by Jane Doe",
                              published="2020-01-01",
                              categories=["Pick of the Day"],
                              director="Jane Doe")],
            shots=[_clip(501, "Thank U, Next", client="Acme",
                         agency="Agency", artists=["Jane Doe"], year=2024)],
        )
        self.run_all()
        promonews_row = _rows(self.root, "promonews")[0]
        self.assertEqual(promonews_row["crossSite"], ["shots"])
        shots_row = _rows(self.root, "shots")[0]
        self.assertEqual(shots_row["crossSite"], ["promonews"])

    def test_cross_site_requires_a_shared_company_or_director(self) -> None:
        self.write(
            mda=[_project("100", "Shared Title", awards=["VOTY"],
                          studio="Acme")],
            shots=[_clip(501, "Shared Title", client="Other",
                         agency="Agency", artists=["Dir"], year=2024)],
        )
        self.run_all()
        self.assertEqual(_rows(self.root, "motiondesignawards")[0]["crossSite"],
                         [])
        self.assertEqual(_rows(self.root, "shots")[0]["crossSite"], [])

    def test_ampersand_matches_and(self) -> None:
        self.write(
            mda=[_project("100", "Salt & Pepper", awards=["VOTY"],
                          studio="Acme & Co")],
            aicp=[_entry("1", "Salt and Pepper", year=2024,
                         categories=["Best of Region"],
                         company="Acme and Co")],
        )
        self.run_all()
        self.assertEqual(
            _rows(self.root, "motiondesignawards")[0]["crossSite"], ["aicp"])
        self.assertEqual(_rows(self.root, "aicp")[0]["crossSite"],
                         ["motiondesignawards"])

    # ------------------------------------------------------------------ #
    # Index-based measurement flags
    # ------------------------------------------------------------------ #

    def test_already_measured_flags_come_from_the_indexes(self) -> None:
        self.write(
            mda=[_project("100", "Measured", awards=["VOTY"], overall=6.0),
                 _project("200", "Unmeasured", awards=["VOTY"], overall=6.0)],
            video_index={"motiondesignawards": [{"projectId": "100"}]},
            census_index={"motiondesignawards": [{"id": "100"}]},
            audio_index={"motiondesignawards": [{"id": "100"}]},
        )
        self.run_all()
        rows = {row["id"]: row for row in _rows(self.root,
                                                "motiondesignawards")}
        self.assertTrue(rows["100"]["alreadyVideoMeasured"])
        self.assertTrue(rows["100"]["alreadyCensusMeasured"])
        self.assertTrue(rows["100"]["alreadyAudioMeasured"])
        self.assertEqual(rows["100"]["missingFrom"], [])
        self.assertFalse(rows["200"]["alreadyVideoMeasured"])
        self.assertFalse(rows["200"]["alreadyCensusMeasured"])
        self.assertFalse(rows["200"]["alreadyAudioMeasured"])
        self.assertEqual(rows["200"]["missingFrom"],
                         ["video", "census", "audio"])

    def test_lane_ids_use_each_catalogs_key(self) -> None:
        self.write(
            promonews=[_video(70, "Song", published="2019-01-01",
                              categories=["UKMVAs 2023 nominee"])],
            shots=[_clip(501, "Eight", brand="Straight 8", year=2010)],
            aicp=[_entry("1", "Zed", year=2024,
                         categories=["Best of Region"])],
            video_index={
                "promonews": [{"nid": 70}],
                "shots": [{"clipId": 501}],
                "aicp": [{"id": "1"}],
            },
            census_index={"promonews": [{"id": "70"}],
                          "shots": [{"id": "501"}],
                          "aicp": [{"id": "1"}]},
        )
        self.run_all()
        self.assertTrue(_rows(self.root, "promonews")[0]["alreadyVideoMeasured"])
        self.assertTrue(_rows(self.root, "promonews")[0]["alreadyCensusMeasured"])
        self.assertTrue(_rows(self.root, "shots")[0]["alreadyVideoMeasured"])
        self.assertTrue(_rows(self.root, "aicp")[0]["alreadyVideoMeasured"])

    def test_cohorts_count_the_measured_lanes(self) -> None:
        self.write(
            mda=[_project("100", "A", awards=["VOTY"], overall=6.0),
                 _project("200", "B", awards=["VOTY"], overall=6.0),
                 _project("300", "C", overall=8.6)],
            video_index={"motiondesignawards": [{"projectId": "100"}]},
            census_index={"motiondesignawards": [{"id": "100"}]},
            audio_index={"motiondesignawards": []},
        )
        self.run_all()
        payload = _site(self.root, "motiondesignawards")
        self.assertEqual(payload["cohorts"]["1"],
                         {"size": 2, "alreadyVideoMeasured": 1,
                          "alreadyCensusMeasured": 1,
                          "alreadyAudioMeasured": 0})
        self.assertEqual(payload["cohorts"]["3"]["size"], 1)
        self.assertEqual(payload["tier0"]["count"], 0)

    # ------------------------------------------------------------------ #
    # Output shape and determinism
    # ------------------------------------------------------------------ #

    def test_ids_files_shape(self) -> None:
        self.write(
            mda=[_project("100", "Alpha", awards=["VOTY"], overall=6.0)],
            aicp=[_entry("1", "Zed", year=2024,
                         categories=["Best of Region"])],
        )
        self.run_all()
        self.assertEqual(
            json.loads((self.root / "motiondesignawards" /
                        "ids.json").read_text()),
            {"ids": ["100"]})
        self.assertEqual(json.loads((self.root / "aicp" / "ids.json").read_text()),
                         {"ids": ["1"]})
        combined = json.loads((self.root / "all-ids.json").read_text())
        self.assertEqual(combined["ids"], ["100", "1"])
        self.assertEqual(combined["bySite"],
                         {"motiondesignawards": ["100"], "aicp": ["1"],
                          "promonews": [], "directorslibrary": [],
                          "shots": []})
        self.assertTrue((self.root / "quality-selection.json").is_file())
        summary = json.loads((self.root / "quality-selection.json").read_text())
        self.assertEqual(summary["schemaVersion"],
                         "kumiki.quality-selection.v1")

    def test_site_schema_versions_and_selection_shape(self) -> None:
        self.write(mda=[_project("100", "Alpha", awards=["VOTY"], overall=6.0)])
        self.run_all()
        payload = _site(self.root, "motiondesignawards")
        self.assertEqual(payload["schemaVersion"],
                         "kumiki.motiondesignawards-quality-selection.v1")
        row = payload["rows"][0]
        for field in ("id", "slug", "title", "tier", "rankTier", "tierReason",
                      "qualitySignals", "crossSite", "alreadyVideoMeasured",
                      "alreadyCensusMeasured", "alreadyAudioMeasured",
                      "missingFrom", "cohort"):
            self.assertIn(field, row)
        self.assertEqual(row["cohort"]["size"], 1)
        self.assertEqual(payload["cohorts"]["1"]["size"], 1)
        self.assertIn("bias", payload)

    def test_two_runs_are_byte_identical(self) -> None:
        self.write(
            mda=[_project("100", "Alpha", awards=["VOTY"], overall=6.0,
                          studio="Acme"),
                 _project("200", "Bravo", awards=["VOTD"], overall=8.2),
                 _project("300", "Charlie", overall=9.1)],
            aicp=[_entry("1", "Zed", year=2024,
                         categories=["Best of Region"], company="Acme"),
                  _entry("2", "Able", year=2019, categories=["Humor"])],
            promonews=[_video(70, "Alpha by Jane", published="2019-01-01",
                              categories=["Pick of the Day"],
                              director="Jane",
                              company="Acme")],
            directorslibrary=[_item(1001, "Film", published="2020-01-01",
                                    festival=["Cannes"])],
            shots=[_clip(501, "Alpha", client="Acme", agency="Agency",
                         artists=["Jane"], year=2024)],
        )
        self.run_all()
        outputs = [
            "quality-selection.md", "quality-selection.json", "all-ids.json",
            "motiondesignawards/quality-selection.json",
            "motiondesignawards/ids.json",
            "aicp/quality-selection.json", "aicp/ids.json",
            "promonews/quality-selection.json", "promonews/ids.json",
            "directorslibrary/quality-selection.json",
            "directorslibrary/ids.json",
            "shots/quality-selection.json", "shots/ids.json",
            "stash/quality-selection.json",
        ]
        first = {name: (self.root / name).read_bytes() for name in outputs}
        self.run_all()
        second = {name: (self.root / name).read_bytes() for name in outputs}
        self.assertEqual(first, second)

    def test_cli_writes_the_same_outputs(self) -> None:
        self.write(mda=[_project("100", "Alpha", awards=["VOTY"], overall=6.0)])
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(main(["--root", str(self.root)]), 0)
        self.assertIn("motiondesignawards", buffer.getvalue())
        self.assertIn("stash", buffer.getvalue())
        self.assertTrue((self.root / "motiondesignawards" /
                         "quality-selection.json").is_file())


if __name__ == "__main__":
    unittest.main()
