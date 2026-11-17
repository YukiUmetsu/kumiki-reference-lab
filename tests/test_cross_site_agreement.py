"""Offline tests for the cross-site agreement analysis.

Every fixture is a small synthetic ``research/analysis`` tree: catalogs for
identity, census and audio records for measurement. No media, network, ffmpeg
or real corpus record is touched. The tests assert the arithmetic directly
(normalisation, Spearman with ties, an exact 3-work x 2-site ICC) and then the
pipeline behaviour (pairing, duration splits, strobe exclusion, partial lanes,
declared work lists, determinism, missing files).
"""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_cross_site_agreement",
    ROOT / "scripts" / "analyze_cross_site_agreement.py")
analysis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(analysis)

FIXED_MTIME = 1_700_000_000  # 2023-11-14T22:13:20Z
FIXED_STAMP = "2023-11-14T22:13:20.000000Z"


# --------------------------------------------------------------------------- #
# Fixture builders
# --------------------------------------------------------------------------- #


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _census(root: Path, site: str, ident: str, slug: str, *,
            duration: float = 30.0, cpm: float = 30.0, luma: float = 0.2,
            saturation: float = 0.3, median_shot: float = 2.0,
            strobe: bool = False, resolution=(1280, 720)) -> None:
    _write_json(root / site / "census" / f"{ident}-{slug}.json", {
        "schemaVersion": f"kumiki.{site}-census-evidence.v1",
        "source": {
            "durationSeconds": duration,
            "resolution": list(resolution),
        },
        "census": {
            "durationSeconds": duration,
            "resolution": list(resolution),
            "cutsPerMinute": cpm,
            "strobe": strobe,
            "seriesSummary": {
                "meanDisplayLuma": luma,
                "meanSaturation": saturation,
            },
        },
        "editorial": {"medianShotSeconds": median_shot, "paceTrend": "steady"},
        "record": {"id": ident, "slug": slug},
    })


def _audio(root: Path, site: str, ident: str, slug: str, *,
           duration: float = 30.0, lufs: float = -16.0, lra: float = 8.0,
           onset: float = 240.0) -> None:
    _write_json(root / site / "audio" / f"{ident}-{slug}.json", {
        "schemaVersion": f"kumiki.{site}-audio-evidence.v1",
        "source": {"durationSeconds": duration, "resolution": [1280, 720]},
        "audio": {
            "durationSeconds": duration,
            "integratedLufs": lufs,
            "loudnessRangeLu": lra,
            "onsetsPerMinuteOfRuntime": onset,
        },
        "record": {"id": ident, "slug": slug},
    })


def _catalog(root: Path, site: str, items: list[dict], key: str) -> None:
    _write_json(root / site / "catalog.json", {"schemaVersion": "test", key: items})


def _main_fixture(root: Path) -> None:
    """Five works: clean pair, duration mismatch, partial lane, strobe."""
    _catalog(root, "aicp", [
        {"id": "1", "title": "Alpha Spot", "company": "Acme"},
        {"id": "2", "title": "Beta Film", "company": "Beta Co"},
        {"id": "3", "title": "Gamma Cut", "company": "Gamma Ltd"},
        {"id": "4", "title": "Delta Partial", "company": "Delta Inc"},
        {"id": "5", "title": "Epsilon Strobe", "company": "Eps Co"},
        {"id": "6", "title": "Zeta Runtime", "company": "Zeta Co"},
    ], "entries")
    _catalog(root, "shots", [
        {"id": 101, "title": "Alpha Spot", "clientName": "Acme"},
        {"id": 102, "title": "Beta Film", "clientName": "Beta Co"},
        {"id": 103, "title": "Gamma Cut", "clientName": "Gamma Ltd"},
        {"id": 104, "title": "Delta Partial", "clientName": "Delta Inc"},
        {"id": 105, "title": "Epsilon Strobe", "clientName": "Eps Co"},
        {"id": 106, "title": "Zeta Runtime", "clientName": "Zeta Co"},
    ], "clips")

    # 1: clean, near-identical delivery.
    _census(root, "aicp", "1", "alpha", cpm=30, luma=0.20, saturation=0.30,
            median_shot=2.0)
    _census(root, "shots", "101", "alpha", cpm=33, luma=0.22, saturation=0.33,
            median_shot=2.2)
    _audio(root, "aicp", "1", "alpha", lufs=-16.0, lra=8.0, onset=240.0)
    _audio(root, "shots", "101", "alpha", lufs=-15.5, lra=8.5, onset=250.0)

    # 2: clean.
    _census(root, "aicp", "2", "beta", cpm=40, luma=0.40, saturation=0.40,
            median_shot=1.0)
    _census(root, "shots", "102", "beta", cpm=42, luma=0.42, saturation=0.42,
            median_shot=1.1)
    _audio(root, "aicp", "2", "beta", lufs=-18.0, lra=6.0, onset=200.0)
    _audio(root, "shots", "102", "beta", lufs=-18.2, lra=6.1, onset=205.0)

    # 3: same duration but a >50% cut-rate divergence (a retimed edit).
    _census(root, "aicp", "3", "gamma", duration=30.0, cpm=18, luma=0.60,
            saturation=0.50, median_shot=3.0)
    _census(root, "shots", "103", "gamma", duration=30.0, cpm=40, luma=0.62,
            saturation=0.52, median_shot=3.1)
    _audio(root, "aicp", "3", "gamma", duration=30.0, lufs=-14.0, lra=9.0,
           onset=180.0)
    _audio(root, "shots", "103", "gamma", duration=30.0, lufs=-13.0, lra=8.0,
           onset=190.0)

    # 4: census + audio on aicp, audio only on shots -> partial.
    _census(root, "aicp", "4", "delta", cpm=10, luma=0.10, saturation=0.10,
            median_shot=5.0)
    _audio(root, "aicp", "4", "delta", lufs=-20.0, lra=5.0, onset=100.0)
    _audio(root, "shots", "104", "delta", lufs=-19.5, lra=5.5, onset=110.0)

    # 6: duration mismatch only (60 s vs 30 s), same cut rate.
    _census(root, "aicp", "6", "zeta", duration=60.0, cpm=30, luma=0.70,
            saturation=0.60, median_shot=2.5)
    _census(root, "shots", "106", "zeta", duration=30.0, cpm=31, luma=0.72,
            saturation=0.62, median_shot=2.6)
    _audio(root, "aicp", "6", "zeta", duration=60.0, lufs=-15.0, lra=10.0,
           onset=260.0)
    _audio(root, "shots", "106", "zeta", duration=30.0, lufs=-14.8, lra=9.8,
           onset=265.0)

    # 5: aicp census is strobe-flagged; its cut rate must never be pooled.
    _census(root, "aicp", "5", "epsilon", cpm=99, luma=0.90, saturation=0.90,
            median_shot=0.5, strobe=True)
    _census(root, "shots", "105", "epsilon", cpm=20, luma=0.92, saturation=0.92,
            median_shot=0.6)
    _audio(root, "aicp", "5", "epsilon", lufs=-12.0, lra=12.0, onset=300.0)
    _audio(root, "shots", "105", "epsilon", lufs=-12.5, lra=11.5, onset=310.0)


def _set_mtimes(root: Path, stamp: int = FIXED_MTIME) -> None:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            os.utime(path, (stamp, stamp))


def _pairs_by_work(payload: dict) -> dict[int, dict]:
    return {pair["workNumber"]: pair for pair in payload["pairs"]}


# --------------------------------------------------------------------------- #
# Normalisation and identity
# --------------------------------------------------------------------------- #


class NormalisationTests(unittest.TestCase):
    def test_normalise_text_folds_case_punctuation_and_ampersand(self):
        # ASCII folding drops U+2019 rather than turning it into a space.
        self.assertEqual(analysis.normalise_text("Don’t Stop & Go!"),
                         "dont stop and go")
        self.assertEqual(analysis.normalise_text("Kraftwerk & Co."),
                         "kraftwerk and co")
        self.assertEqual(analysis.normalise_text("Chloé"), "chloe")
        self.assertEqual(analysis.normalise_text(None), "")

    def test_promonews_suffix_is_stripped_only_when_a_title_remains(self):
        self.assertEqual(
            analysis.strip_promonews_suffix(
                "The Prodigy 'Timebomb Zone' by Paco Raterta"),
            "The Prodigy 'Timebomb Zone'")
        # Mirrors select_quality_clips: any " by " suffix is dropped, so this
        # real title loses its tail. Kept for cross-tree consistency.
        self.assertEqual(analysis.strip_promonews_suffix("Stand by Me"),
                         "Stand")
        self.assertEqual(analysis.normalise_title("Shape of Dreams"),
                         "shape of dreams")

    def test_title_plus_company_joins_across_sites(self):
        identities = {
            ("aicp", "1"): {"title": "Polar Bears", "companies": ["coca cola"],
                            "directors": []},
            ("shots", "101"): {"title": "POLAR BEARS", "companies": ["coca cola"],
                               "directors": []},
            ("shots", "102"): {"title": "Polar Bears", "companies": ["other"],
                               "directors": []},
        }
        components = analysis.compute_components(identities)
        multi = [nodes for nodes in components
                 if len({site for site, _ in nodes}) > 1]
        self.assertEqual(multi, [[("aicp", "1"), ("shots", "101")]])

    def test_title_plus_director_joins_promonews_to_shots(self):
        identities = {
            ("promonews", "9"): {"title": "Northside Needs Me",
                                 "companies": [], "directors": ["mau morgo"]},
            ("shots", "909"): {"title": "Northside Needs Me",
                               "companies": [], "directors": ["mau morgo"]},
        }
        components = analysis.compute_components(identities)
        self.assertIn([("promonews", "9"), ("shots", "909")], components)

    def test_empty_title_never_joins(self):
        identities = {
            ("aicp", "1"): {"title": "", "companies": ["acme"], "directors": []},
            ("shots", "101"): {"title": "", "companies": ["acme"], "directors": []},
        }
        components = analysis.compute_components(identities)
        self.assertEqual([nodes for nodes in components if len(nodes) > 1], [])


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #


class StatisticTests(unittest.TestCase):
    def test_spearman_with_ties(self):
        # ranks x = [1, 2.5, 2.5, 4], ranks y = [1, 2, 3, 4]; Pearson on ranks
        # = 4.5 / sqrt(4.5 * 5.0) = sqrt(0.9) = 0.948683...
        self.assertAlmostEqual(
            analysis.spearman([1, 2, 2, 3], [1, 3, 2, 4]),
            0.9 ** 0.5, places=12)

    def test_spearman_undefined_for_constant_series(self):
        self.assertIsNone(analysis.spearman([1, 1, 1], [1, 2, 3]))
        self.assertIsNone(analysis.spearman([1], [1]))

    def test_icc_exact_on_three_works_by_two_sites(self):
        # means 1.5/3.5/5.5, grand 3.5, MSB=8, MSW=0.5 -> 7.5/8.5 = 15/17
        detail = analysis.icc_oneway([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        self.assertIsNotNone(detail)
        self.assertAlmostEqual(detail["icc"], 15.0 / 17.0, places=12)
        self.assertEqual(detail["works"], 3)
        self.assertEqual(detail["values"], 6)
        self.assertAlmostEqual(detail["meanValuesPerWork"], 2.0, places=12)

    def test_icc_undefined_with_one_work(self):
        self.assertIsNone(analysis.icc_oneway([[1.0, 2.0]]))

    def test_relative_difference_never_divides_by_zero(self):
        self.assertEqual(analysis.relative_difference(4.0, 2.0), 0.5)
        self.assertEqual(analysis.relative_difference(2.0, 4.0), -0.5)
        self.assertIsNone(analysis.relative_difference(0.0, 0.0))


# --------------------------------------------------------------------------- #
# Pairing behaviour
# --------------------------------------------------------------------------- #


class PairingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "analysis"
        _main_fixture(self.root)
        self.payload = analysis.analyze(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_work_is_paired_across_the_two_sites(self):
        self.assertEqual(self.payload["counts"]["pairs"], 6)
        self.assertEqual(self.payload["counts"]["worksPaired"], 6)
        for pair in self.payload["pairs"]:
            self.assertEqual((pair["siteA"], pair["siteB"]), ("aicp", "shots"))

    def test_pair_row_carries_both_ids_slugs_durations_and_resolutions(self):
        alpha, = [pair for pair in self.payload["pairs"]
                  if pair["title"] == "Alpha Spot"]
        self.assertEqual(alpha["a"]["id"], "1")
        self.assertEqual(alpha["b"]["id"], "101")
        self.assertEqual(alpha["a"]["slug"], "alpha")
        self.assertEqual(alpha["b"]["slug"], "alpha")
        self.assertEqual(alpha["a"]["durationSeconds"], 30.0)
        self.assertEqual(alpha["b"]["resolution"], [1280, 720])
        self.assertEqual(alpha["values"]["cutsPerMinute"], [30.0, 33.0])
        self.assertAlmostEqual(alpha["delta"]["cutsPerMinute"], -3.0)
        self.assertAlmostEqual(alpha["relativeDelta"]["cutsPerMinute"],
                               -3.0 / 33.0, places=6)

    def test_duration_mismatch_is_flagged_and_split_out(self):
        self.assertEqual(self.payload["counts"]["durationMismatchPairs"], 1)
        zeta, = [pair for pair in self.payload["pairs"]
                 if pair["title"] == "Zeta Runtime"]
        self.assertTrue(zeta["durationMismatch"])
        self.assertAlmostEqual(zeta["durationDeltaFraction"], 0.5)
        stats = self.payload["statistics"]["cutsPerMinute"]
        self.assertEqual(stats["all"]["n_pairs"], 4)
        self.assertEqual(stats["durationMatched"]["n_pairs"], 3)

    def test_duration_delta_distribution_is_summarised(self):
        distribution = self.payload["durationDeltaDistribution"]
        self.assertEqual(distribution["n"], 6)
        self.assertEqual(distribution["mismatchCount"], 1)
        self.assertAlmostEqual(distribution["max"], 0.5)
        self.assertEqual(sum(distribution["buckets"].values()), 6)
        self.assertEqual(distribution["buckets"]["10-50%"], 1)

    def test_cut_rate_divergence_is_flagged_and_split_out(self):
        self.assertEqual(self.payload["counts"]["cutRateDivergentPairs"], 1)
        gamma, = [pair for pair in self.payload["pairs"]
                  if pair["title"] == "Gamma Cut"]
        self.assertTrue(gamma["cutRateDivergence"])
        self.assertFalse(gamma["durationMismatch"])
        stats = self.payload["statistics"]["cutsPerMinute"]
        self.assertEqual(stats["cutRateConsistent"]["n_pairs"], 3)

    def test_strobe_is_never_pooled_with_non_strobe(self):
        stats = self.payload["statistics"]["cutsPerMinute"]
        self.assertEqual(stats["excludedStrobePairs"], 1)
        # 6 works, one missing census (delta), one strobe (epsilon) -> 4 pairs
        self.assertEqual(stats["all"]["n_pairs"], 4)
        epsilon, = [pair for pair in self.payload["pairs"]
                    if pair["title"] == "Epsilon Strobe"]
        self.assertEqual(epsilon["values"]["cutsPerMinute"], [99.0, 20.0])
        # The same pair still contributes the non-cut census metrics.
        self.assertEqual(self.payload["statistics"]["meanLuma"]["all"]["n_pairs"], 5)

    def test_partial_pair_is_counted_not_averaged_into_missing_lanes(self):
        self.assertEqual(self.payload["counts"]["partialPairs"], 1)
        delta, = [pair for pair in self.payload["pairs"]
                  if pair["title"] == "Delta Partial"]
        self.assertTrue(delta["partial"])
        self.assertEqual(delta["values"]["cutsPerMinute"], [10.0, None])
        self.assertEqual(delta["availableMetrics"],
                         ["integratedLufs", "lra", "onsetRate"])
        self.assertEqual(self.payload["statistics"]["cutsPerMinute"]["all"]["n_pairs"], 4)

    def test_audio_metrics_pair_on_every_work(self):
        for key in ("integratedLufs", "lra", "onsetRate"):
            self.assertEqual(self.payload["statistics"][key]["all"]["n_pairs"], 6,
                             key)
            self.assertEqual(
                self.payload["statistics"][key]["all"]["n_works"], 6, key)

    def test_duration_matched_audio_excludes_the_mismatch(self):
        self.assertEqual(
            self.payload["statistics"]["integratedLufs"]["durationMatched"]["n_pairs"],
            5)

    def test_sparse_metric_is_labelled_and_has_no_icc(self):
        block = self.payload["statistics"]["cutsPerMinute"]
        self.assertFalse(block["sparse"])  # 3 pairs meets the threshold
        # A metric with no pairs at all is sparse and explicit about it.
        empty = analysis.analyze(self._without_audio())
        lufs = empty["statistics"]["integratedLufs"]
        self.assertTrue(lufs["sparse"])
        self.assertIsNone(lufs["all"]["icc"])
        self.assertIn("no work has this metric", lufs["notes"][0])

    def _without_audio(self) -> Path:
        root = Path(self.tmp.name) / "audio-free"
        _catalog(root, "aicp", [{"id": "1", "title": "Alpha", "company": "Acme"}],
                 "entries")
        _catalog(root, "shots", [{"id": 101, "title": "Alpha", "clientName": "Acme"}],
                 "clips")
        _census(root, "aicp", "1", "alpha")
        _census(root, "shots", "101", "alpha")
        return root


class IccPipelineTests(unittest.TestCase):
    def test_pipeline_icc_matches_the_hand_computable_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "analysis"
            _catalog(root, "aicp", [
                {"id": "1", "title": "One", "company": "A"},
                {"id": "2", "title": "Two", "company": "B"},
                {"id": "3", "title": "Three", "company": "C"},
            ], "entries")
            _catalog(root, "shots", [
                {"id": 101, "title": "One", "clientName": "A"},
                {"id": 102, "title": "Two", "clientName": "B"},
                {"id": 103, "title": "Three", "clientName": "C"},
            ], "clips")
            for source, target, value in (("1", "101", 1.0), ("2", "102", 3.0),
                                          ("3", "103", 5.0)):
                _census(root, "aicp", source, "w", median_shot=value)
                _census(root, "shots", target, "w", median_shot=value + 1.0)
            payload = analysis.analyze(root)
            stats = payload["statistics"]["medianShotSeconds"]["all"]
            self.assertEqual(stats["n_pairs"], 3)
            self.assertEqual(stats["n_works"], 3)
            self.assertAlmostEqual(stats["icc"], 15.0 / 17.0, places=6)
            self.assertEqual(stats["iccDetail"]["works"], 3)
            self.assertEqual(stats["iccDetail"]["values"], 6)
            self.assertAlmostEqual(stats["iccDetail"]["meanValuesPerWork"], 2.0)
            self.assertAlmostEqual(stats["spearman"], 1.0, places=9)


# --------------------------------------------------------------------------- #
# Determinism, declared work lists and missing files
# --------------------------------------------------------------------------- #


class OutputTests(unittest.TestCase):
    def test_two_runs_are_byte_identical_and_timestamp_is_from_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "analysis"
            _main_fixture(root)
            _set_mtimes(root)
            first = analysis.analyze(root)
            second = analysis.analyze(root)
            self.assertEqual(first["derivedAt"], FIXED_STAMP)
            self.assertEqual(json.dumps(first, indent=2), json.dumps(second, indent=2))

            out_a = Path(tmp) / "a"
            out_b = Path(tmp) / "b"
            analysis.write_outputs(first, out_a)
            analysis.write_outputs(second, out_b)
            for name in ("cross-site-agreement.json", "cross-site-agreement.md"):
                self.assertEqual((out_a / name).read_bytes(),
                                 (out_b / name).read_bytes(), name)

    def test_markdown_states_the_coverage_gap_plainly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "analysis"
            _catalog(root, "aicp", [{"id": "1", "title": "Alpha",
                                     "company": "Acme"}], "entries")
            _catalog(root, "shots", [{"id": 101, "title": "Alpha",
                                      "clientName": "Acme"}], "clips")
            _census(root, "aicp", "1", "alpha")
            payload = analysis.analyze(root)
            markdown = analysis.render_markdown(payload)
            self.assertIn("cannot answer the cross-site question", markdown)
            self.assertIn("pairs: **0**", markdown)
            self.assertIn("This is a coverage fact, not a null result.", markdown)

    def test_missing_root_is_tolerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "does-not-exist"
            payload = analysis.analyze(root)
            self.assertEqual(payload["sites"], [])
            self.assertEqual(payload["counts"]["pairs"], 0)
            self.assertIsNone(payload["derivedAt"])
            out = Path(tmp) / "out"
            json_path, markdown_path = analysis.write_outputs(payload, out)
            self.assertTrue(json_path.is_file())
            self.assertTrue(markdown_path.is_file())

    def test_declared_work_list_wins_and_tolerates_missing_catalogs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "analysis"
            _write_json(root / "quality-selection.json", {
                "crossSiteWorks": [{
                    "key": "shared",
                    "title": "Shared Work",
                    "members": [
                        {"site": "aicp", "id": "7"},
                        {"site": "shots", "id": "77"},
                    ],
                }],
            })
            _census(root, "aicp", "7", "shared", cpm=24, luma=0.3)
            _audio(root, "aicp", "7", "shared", lufs=-17.0, lra=7.0, onset=220.0)
            _audio(root, "shots", "77", "shared", lufs=-16.0, lra=8.0, onset=230.0)
            payload = analysis.analyze(root)
            self.assertEqual(payload["counts"]["pairs"], 1)
            pair = payload["pairs"][0]
            self.assertEqual((pair["siteA"], pair["siteB"]), ("aicp", "shots"))
            self.assertTrue(pair["partial"])
            self.assertEqual(payload["statistics"]["integratedLufs"]["all"]["n_pairs"], 1)
            self.assertEqual(payload["statistics"]["cutsPerMinute"]["all"]["n_pairs"], 0)

    def test_without_declared_list_slug_fallback_still_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "analysis"
            _census(root, "aicp", "7", "shared-work", luma=0.3)
            _census(root, "shots", "77", "shared-work", luma=0.4)
            payload = analysis.analyze(root)
            self.assertEqual(payload["counts"]["pairs"], 1)
            self.assertEqual(payload["statistics"]["meanLuma"]["all"]["n_pairs"], 1)

    def test_quality_selection_rows_supply_identity_when_catalog_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "analysis"
            _write_json(root / "aicp" / "quality-selection.json", {
                "rows": [{"id": "1", "slug": "alpha", "title": "Alpha Spot",
                          "qualitySignals": {"company": "Acme"}}],
            })
            _write_json(root / "shots" / "quality-selection.json", {
                "rows": [{"id": "101", "slug": "alpha", "title": "Alpha Spot",
                          "qualitySignals": {"clientName": "Acme"}}],
            })
            _census(root, "aicp", "1", "alpha")
            _census(root, "shots", "101", "alpha")
            payload = analysis.analyze(root)
            self.assertEqual(payload["counts"]["pairs"], 1)
            self.assertEqual(payload["pairs"][0]["title"], "Alpha Spot")

    def test_json_schema_and_thresholds_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "analysis"
            _main_fixture(root)
            payload = analysis.analyze(root)
            self.assertEqual(payload["schemaVersion"],
                             "kumiki.cross-site-agreement.v1")
            self.assertEqual(payload["thresholds"]["durationMismatchFraction"], 0.1)
            self.assertEqual(payload["thresholds"]["cutRateDivergenceFraction"], 0.5)
            self.assertEqual(len(payload["limitations"]), 7)
            self.assertEqual(payload["metrics"],
                             ["cutsPerMinute", "medianShotSeconds", "meanLuma",
                              "meanSaturation", "integratedLufs", "lra",
                              "onsetRate"])


if __name__ == "__main__":
    unittest.main()
