"""Offline tests for measured artistic components.

Every fixture is synthetic: no research record, media, network, ffmpeg or real
corpus file is touched. The tests pin the arithmetic that the documentation
relies on — robust standardization fallbacks, silhouette ordering, deterministic
clustering, strobe separation, missing-feature coverage, recipe arithmetic and
the naming vocabulary — rather than any particular corpus result.
"""

from __future__ import annotations

import importlib.util
import random
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "derive_artistic_components", ROOT / "scripts" / "derive_artistic_components.py")
driver = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(driver)

from kumiki_reference_lab.acquisition.components import (  # noqa: E402
    CLUSTER_FEATURES,
    FEATURE_SPECS,
    FORBIDDEN_NAME_TERMS,
    agglomerative,
    choose_k,
    component_profile,
    extract_features,
    feature_coverage,
    name_component,
    name_components,
    reuse_recipe,
    robust_standardize,
    silhouette_score,
)


def _row(identifier: str, *, rate: float, shot: float, burst: float = 0.0,
         short: float = 0.0, drift: float = 1.0, flicker: float = 0.02,
         site: str = "fixture", strobe: bool = False,
         evidence: str = "full-film") -> dict:
    return {
        "site": site,
        "id": identifier,
        "slug": f"slug-{identifier}",
        "evidenceLevel": evidence,
        "strobe": strobe,
        "cutsPerMinute": rate,
        "medianShotSeconds": shot,
        "burstFraction": burst,
        "shotsUnderHalfSecondPct": short,
        "paceDriftRatio": drift,
        "flickerLumaPerSecond": flicker,
    }


def _blob_rows() -> list[dict]:
    """Two well-separated blobs with deterministic jitter."""
    generator = random.Random(7)
    rows: list[dict] = []
    for index in range(60):
        rows.append(_row(
            f"slow-{index:03d}",
            rate=3.0 + generator.uniform(-0.2, 0.2),
            shot=20.0 + generator.uniform(-0.4, 0.4),
            burst=0.01 + generator.uniform(0.0, 0.01),
            short=0.5 + generator.uniform(0.0, 0.2),
            drift=1.0 + generator.uniform(-0.05, 0.05),
            flicker=0.008 + generator.uniform(0.0, 0.001),
        ))
    for index in range(60):
        rows.append(_row(
            f"fast-{index:03d}",
            rate=65.0 + generator.uniform(-0.5, 0.5),
            shot=0.9 + generator.uniform(-0.02, 0.02),
            burst=0.40 + generator.uniform(0.0, 0.01),
            short=30.0 + generator.uniform(0.0, 0.5),
            drift=1.0 + generator.uniform(-0.05, 0.05),
            flicker=0.060 + generator.uniform(0.0, 0.002),
        ))
    return rows


class RobustStandardizeTests(unittest.TestCase):
    def test_zero_iqr_falls_back_and_keeps_order(self):
        values = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 9.0]
        standardized, info = robust_standardize(values)
        self.assertEqual(info["iqr"], 0.0)
        self.assertIn(info["fallback"], {"mad", "unit"})
        self.assertEqual(info["missing"], 0)
        # Five equal values sit at the median; the outlier is clipped, not
        # allowed to dominate a Euclidean distance.
        self.assertEqual(standardized[:6], [0.0] * 6)
        self.assertEqual(standardized[6], 4.0)

    def test_all_equal_is_all_zero(self):
        standardized, info = robust_standardize([2.0, 2.0, 2.0])
        self.assertEqual(standardized, [0.0, 0.0, 0.0])
        self.assertEqual(info["fallback"], "unit")
        self.assertEqual(info["scale"], 1.0)

    def test_missing_values_are_counted_not_dropped(self):
        standardized, info = robust_standardize([1.0, 2.0, 3.0, None, float("nan")])
        self.assertEqual(len(standardized), 5)
        self.assertEqual(info["missing"], 2)
        self.assertEqual(standardized[3], 0.0)
        self.assertEqual(standardized[4], 0.0)

    def test_median_and_iqr_are_not_mean_and_sd(self):
        # One huge outlier moves the mean but not the median/IQR scale.
        values = [1.0, 2.0, 3.0, 4.0, 1000.0]
        _, info = robust_standardize(values)
        self.assertEqual(info["median"], 3.0)
        self.assertLess(info["iqr"], 3.0)


class SilhouetteTests(unittest.TestCase):
    def test_separable_two_clusters_beat_three(self):
        rows = _blob_rows()
        two = [0] * 60 + [1] * 60
        three = [0] * 30 + [1] * 30 + [2] * 60
        self.assertGreater(silhouette_score(rows, two),
                           silhouette_score(rows, three))

    def test_choose_k_prefers_the_separated_k(self):
        rows = _blob_rows()
        chosen, info = choose_k(rows, candidates=(2, 3, 4))
        self.assertEqual(chosen, 2)
        self.assertGreater(info["silhouette"], 0.5)
        self.assertEqual(len(info["labels"]), len(rows))

    def test_singleton_cluster_scores_zero(self):
        rows = _blob_rows()[:10]
        labels = [0] * 9 + [1]
        self.assertLess(silhouette_score(rows, labels), 1.0)


class DeterminismTests(unittest.TestCase):
    def test_two_runs_identical_with_stable_input_order(self):
        rows = _blob_rows()
        random.Random(11).shuffle(rows)  # one fixed shuffle, then stable order
        first = agglomerative(rows, k=2)
        second = agglomerative(rows, k=2)
        self.assertEqual(first, second)
        first_k, first_info = choose_k(rows, candidates=(2, 3, 4))
        second_k, second_info = choose_k(rows, candidates=(2, 3, 4))
        self.assertEqual(first_k, second_k)
        self.assertEqual(first_info["labels"], second_info["labels"])
        self.assertEqual(first_info["candidateSilhouette"],
                         second_info["candidateSilhouette"])

    def test_cluster_members_are_sorted_and_ordered_by_first_member(self):
        rows = _blob_rows()
        clusters = agglomerative(rows, k=2)
        self.assertEqual(clusters, sorted(clusters, key=lambda part: part[0]))
        for part in clusters:
            self.assertEqual(part, sorted(part))


class StrobeSeparationTests(unittest.TestCase):
    def test_strobe_records_never_join_cut_rate_clusters(self):
        rows: list[dict] = []
        for index in range(60):
            rows.append(_row(f"slow-{index:03d}", rate=3.0, shot=20.0))
        for index in range(60):
            rows.append(_row(f"fast-{index:03d}", rate=60.0, shot=1.0,
                             burst=0.35, short=25.0))
        for index in range(30):
            rows.append(_row(f"strobe-{index:03d}", rate=90.0, shot=0.2,
                             burst=0.8, short=70.0, flicker=0.2,
                             strobe=True))
        built = driver.build_components(
            rows, max_k=6, min_cluster_size=5, top_exemplars=4)
        names = [component["name"] for component in built["components"]]
        self.assertIn("strobe-textured", names)
        strobe = next(component for component in built["components"]
                      if component["name"] == "strobe-textured")
        self.assertEqual(strobe["n"], 30)
        self.assertEqual(strobe["sites"], {"fixture": 30})
        for component in built["components"]:
            if component["name"] == "strobe-textured":
                continue
            self.assertNotEqual(component["sites"].get("fixture"), 30)
        self.assertEqual(sum(component["n"] for component in built["components"]),
                         len(rows))
        # Every strobe record maps to the strobe component, not to a rate band.
        self.assertEqual(len(built["strobeRows"]), 30)
        self.assertTrue(all(row["strobe"] is True for row in built["strobeRows"]))


class MissingFeatureTests(unittest.TestCase):
    def test_absent_feature_does_not_drop_the_record(self):
        rows = [_row(f"full-{index}", rate=10.0, shot=3.0)
                for index in range(10)]
        for index in range(5):
            row = _row(f"sparse-{index}", rate=12.0, shot=2.5)
            row["paceDriftRatio"] = None
            row["flickerLumaPerSecond"] = None
            rows.append(row)
        profile = component_profile(list(range(len(rows))), rows)
        self.assertEqual(profile["n"], 15)
        self.assertEqual(profile["features"]["paceDriftRatio"]["coverage"], 10)
        self.assertEqual(profile["features"]["paceDriftRatio"]["missing"], 5)
        self.assertEqual(profile["features"]["cutsPerMinute"]["coverage"], 15)
        coverage = feature_coverage(rows)
        self.assertEqual(coverage["cutsPerMinute"]["fraction"], 1.0)
        self.assertLess(coverage["paceDriftRatio"]["fraction"], 1.0)
        clusters = agglomerative(rows, k=2)
        self.assertEqual(sum(len(cluster) for cluster in clusters), 15)
        # Missing values are imputed at the median of the present values; they
        # must not enter the median/IQR calculation as real zeros.
        _k, info = choose_k(rows, candidates=(2,))
        self.assertEqual(info["standardization"]["paceDriftRatio"]["missing"], 5)
        self.assertAlmostEqual(
            info["standardization"]["paceDriftRatio"]["median"], 1.0)

    def test_windowed_record_extracts_without_editorial(self):
        windowed = {
            "site": "fixture",
            "source": {"durationSeconds": 42.0},
            "summary": {
                "cutCandidateRatePerMinute": 12.5,
                "medianCutGapSeconds": 4.0,
                "burstFraction": 0.0,
                "meanDisplayLuma": 0.3,
                "meanSaturation": 0.2,
            },
        }
        row = extract_features(windowed, site="fixture")
        self.assertEqual(row["evidenceLevel"], "windowed")
        self.assertIsNone(row["strobe"])
        self.assertAlmostEqual(row["cutsPerMinute"], 12.5)
        self.assertAlmostEqual(row["medianShotSeconds"], 4.0)
        self.assertIsNone(row["paceDriftRatio"])
        self.assertIsNone(row["integratedLufs"])


class RecipeTests(unittest.TestCase):
    def test_cuts_scale_with_duration(self):
        rows = [_row(f"r-{index}", rate=20.0, shot=3.0) for index in range(20)]
        profile = component_profile(list(range(len(rows))), rows)
        recipe = reuse_recipe(profile)
        self.assertEqual(recipe["targetCuts"]["15s"]["cuts"], 5)
        self.assertEqual(recipe["targetCuts"]["30s"]["cuts"], 10)
        self.assertEqual(recipe["targetCuts"]["60s"]["cuts"], 20)
        self.assertEqual(recipe["targetCuts"]["90s"]["cuts"], 30)
        self.assertEqual(recipe["derivedFrom"], 20)
        self.assertAlmostEqual(recipe["shotSeconds"]["medianSeconds"], 3.0)

    def test_odd_rate_rounds_to_nearest_cut(self):
        rows = [_row(f"r-{index}", rate=13.0, shot=4.6) for index in range(10)]
        profile = component_profile(list(range(len(rows))), rows)
        recipe = reuse_recipe(profile)
        # 13 * 30 / 60 = 6.5 -> round() is 6 (banker's rounding); the
        # documented formula is round(rate * seconds / 60).
        self.assertEqual(recipe["targetCuts"]["30s"]["cuts"], 6)
        self.assertEqual(recipe["targetCuts"]["60s"]["cuts"], 13)

    def test_missing_rate_yields_no_cut_targets(self):
        rows = [_row(f"r-{index}", rate=10.0, shot=2.0) for index in range(5)]
        for row in rows:
            row["cutsPerMinute"] = None
        profile = component_profile(list(range(len(rows))), rows)
        recipe = reuse_recipe(profile)
        self.assertIsNone(recipe["targetCuts"]["30s"]["cuts"])
        self.assertIsNone(recipe["targetCuts"]["60s"]["cuts"])


class NamingTests(unittest.TestCase):
    def _profile(self, **values):
        rows = [_row(f"r-{index}", rate=values.get("rate", 10.0),
                     shot=values.get("shot", 3.0),
                     burst=values.get("burst", 0.0),
                     drift=values.get("drift", 1.0)) for index in range(5)]
        return component_profile(list(range(len(rows))), rows)

    def test_names_come_from_the_timing_vocabulary(self):
        cases = [
            ({"rate": 80.0, "shot": 0.5, "burst": 0.4}, "bursty-rapid-cut"),
            ({"rate": 40.0, "shot": 1.2}, "fast-cut"),
            ({"rate": 25.0, "shot": 2.0}, "quick-cut"),
            ({"rate": 15.0, "shot": 3.0}, "steady-cut"),
            ({"rate": 3.0, "shot": 15.0, "drift": 0.3},
             "decelerating-long-take"),
            ({"rate": 3.0, "shot": 6.0, "drift": 1.0}, "steady-slow-burn"),
        ]
        for values, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(name_component(self._profile(**values)), expected)

    def test_no_name_asserts_a_forbidden_term(self):
        profiles = [
            self._profile(rate=rate, shot=shot, burst=burst, drift=drift)
            for rate, shot, burst, drift in (
                (1.0, 60.0, 0.0, 0.5),
                (5.0, 9.0, 0.0, 1.0),
                (15.0, 3.0, 0.1, 1.0),
                (25.0, 2.0, 0.2, 2.0),
                (40.0, 1.2, 0.3, 1.0),
                (80.0, 0.4, 0.5, 1.0),
                (120.0, 0.2, 0.9, 0.3),
            )
        ]
        names = name_components(profiles)
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            lowered = name.lower()
            for term in FORBIDDEN_NAME_TERMS:
                self.assertNotIn(term, lowered)
            self.assertNotIn("—", name)

    def test_collisions_are_disambiguated_deterministically(self):
        profiles = [self._profile(rate=25.0, shot=2.0) for _ in range(3)]
        names = name_components(profiles)
        self.assertEqual(names[0], "quick-cut")
        self.assertEqual(names[1], "quick-cut-variant-2")
        self.assertEqual(names[2], "quick-cut-variant-3")


class FeatureSpecTests(unittest.TestCase):
    def test_every_spec_has_a_getter_unit_and_meaning(self):
        for name, spec in FEATURE_SPECS.items():
            self.assertTrue(callable(spec["getter"]), name)
            self.assertIsInstance(spec["unit"], str, name)
            self.assertIsInstance(spec["meaning"], str, name)
            self.assertNotIn("beautiful", spec["meaning"].lower())

    def test_cluster_features_are_declared_specs(self):
        self.assertEqual(set(CLUSTER_FEATURES) - set(FEATURE_SPECS), set())


if __name__ == "__main__":
    unittest.main()
