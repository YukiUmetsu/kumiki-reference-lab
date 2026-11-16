"""Offline tests for derived editorial measurements and the census writer.

Every fixture is a stored census-shaped dictionary; no media, no network and
no ffmpeg are touched. The writer is exercised against a temporary evidence
tree.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.acquisition import (
    editorial_aggregate, editorial_columns, editorial_section_lines,
)
from kumiki_reference_lab.acquisition.editorial import derive_editorial

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "derive_census_editorial", ROOT / "scripts" / "derive_census_editorial.py")
writer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(writer)


def _scan(*, duration=24.0, cuts=(96, 192, 288, 384, 480), timebase=(1, 24),
          series=None, strobe=False, fps=None) -> dict:
    scan: dict = {
        "durationSeconds": duration,
        "timebase": {"numerator": timebase[0], "denominator": timebase[1]},
        "cutPts": list(cuts),
        "strobe": strobe,
        "series": [] if series is None else series,
        "seriesSummary": {"sampledSeconds": duration,
                          "decodeCoverageFraction": 1.0},
    }
    if fps is not None:
        scan["fps"] = {"numerator": fps[0], "denominator": fps[1]}
    return scan


def _row(seconds: float, luma: float, *, saturation=0.5, rgb=None) -> dict:
    return {
        "sourceSeconds": seconds,
        "meanRgb": rgb or [luma, luma, luma],
        "meanDisplayLumaProxy": luma,
        "meanSaturationProxy": saturation,
    }


class ShotStructureTests(unittest.TestCase):
    def test_perfect_regular_cuts_have_exact_quantiles(self) -> None:
        block = derive_editorial(_scan())
        self.assertEqual(block["shotCount"], 6)
        self.assertAlmostEqual(block["medianShotSeconds"], 4.0)
        self.assertAlmostEqual(block["p10ShotSeconds"], 4.0)
        self.assertAlmostEqual(block["p90ShotSeconds"], 4.0)
        self.assertAlmostEqual(block["meanShotSeconds"], 4.0)
        self.assertAlmostEqual(block["longestShotSeconds"], 4.0)
        self.assertEqual(block["shotsUnderHalfSecond"], 0)
        self.assertEqual(block["degraded"], ["series-empty"])

    def test_single_shot_film_has_zero_cuts_and_one_shot(self) -> None:
        block = derive_editorial(_scan(duration=100.0, cuts=()))
        self.assertEqual(block["shotCount"], 1)
        self.assertAlmostEqual(block["medianShotSeconds"], 100.0)
        self.assertAlmostEqual(block["p10ShotSeconds"], 100.0)
        self.assertAlmostEqual(block["p90ShotSeconds"], 100.0)
        self.assertEqual(block["shotsUnderHalfSecondFraction"], 0.0)
        self.assertIsNone(block["paceDriftRatio"])
        self.assertIsNone(block["paceTrend"])
        self.assertEqual(block["cutsPerMinuteOfRuntime"], 0.0)

    def test_sub_second_shots_are_counted_and_fractioned(self) -> None:
        # 0.4 s and 0.6 s shots against a 1.0 s third shot.
        scan = _scan(duration=2.0, timebase=(1, 10), cuts=(4, 10))
        block = derive_editorial(scan)
        self.assertEqual(block["shotCount"], 3)
        self.assertAlmostEqual(block["medianShotSeconds"], 0.6)
        self.assertEqual(block["shotsUnderHalfSecond"], 1)
        self.assertEqual(block["shotsUnderOneSecond"], 2)
        self.assertAlmostEqual(block["shotsUnderHalfSecondFraction"], 1 / 3, 6)

    def test_whole_number_fps_is_the_fallback_timebase(self) -> None:
        scan = _scan(duration=3.0, cuts=(24, 48), timebase=(0, 0),
                     fps=(24, 1))
        block = derive_editorial(scan)
        self.assertEqual(block["shotCount"], 3)
        self.assertAlmostEqual(block["medianShotSeconds"], 1.0)


class PaceClassificationTests(unittest.TestCase):
    def test_accelerating_last_third(self) -> None:
        # One candidate in the first third, three in the last.
        block = derive_editorial(_scan(
            duration=300.0, timebase=(1, 1), cuts=(10, 210, 220, 230)))
        self.assertAlmostEqual(block["paceFirstThird"], 0.6)
        self.assertAlmostEqual(block["paceLastThird"], 1.8)
        self.assertAlmostEqual(block["paceDriftRatio"], 3.0)
        self.assertEqual(block["paceTrend"], "accelerating")

    def test_decelerating_last_third(self) -> None:
        block = derive_editorial(_scan(
            duration=300.0, timebase=(1, 1), cuts=(10, 20, 30, 210)))
        self.assertEqual(block["paceTrend"], "decelerating")
        self.assertAlmostEqual(block["paceDriftRatio"], 1 / 3, 6)

    def test_steady_within_the_fifteen_percent_band(self) -> None:
        block = derive_editorial(_scan(
            duration=300.0, timebase=(1, 1), cuts=(10, 20, 210, 220)))
        self.assertAlmostEqual(block["paceDriftRatio"], 1.0)
        self.assertEqual(block["paceTrend"], "steady")

    def test_first_third_without_cuts_has_no_ratio(self) -> None:
        block = derive_editorial(_scan(
            duration=300.0, timebase=(1, 1), cuts=(210, 220)))
        self.assertIsNone(block["paceDriftRatio"])
        self.assertIsNone(block["paceTrend"])
        self.assertIsNotNone(block["medianShotSecondsLastThird"])


class AppearanceTests(unittest.TestCase):
    def test_monotonic_luma_ramp_has_slope_and_r2_near_one(self) -> None:
        series = [_row(float(index), 0.1 + 0.1 * index) for index in range(10)]
        block = derive_editorial(_scan(series=series))
        self.assertAlmostEqual(block["lumaSlopePerMinute"], 6.0, 6)
        self.assertAlmostEqual(block["lumaSlopeR2"], 1.0, 6)
        self.assertAlmostEqual(block["lumaRange"], 0.9, 6)
        self.assertIsNotNone(block["lumaStdDevAcrossSeries"])
        # Saturation never changes, so its slope is 0 and r2 is undefined.
        self.assertAlmostEqual(block["saturationSlopePerMinute"], 0.0, 6)
        self.assertIsNone(block["saturationSlopeR2"])

    def test_static_series_is_fully_static(self) -> None:
        series = [_row(float(index), 0.3) for index in range(5)]
        block = derive_editorial(_scan(series=series, duration=5.0))
        self.assertEqual(block["staticFraction"], 1.0)
        self.assertEqual(block["flickerLumaPerSecond"], 0.0)
        self.assertEqual(block["flickerP90"], 0.0)
        self.assertEqual(block["lumaRange"], 0.0)
        self.assertEqual(block["lumaStdDevAcrossSeries"], 0.0)

    def test_flicker_p90_and_static_fraction_separate(self) -> None:
        series = [_row(0.0, 0.2), _row(1.0, 0.4), _row(2.0, 0.4),
                  _row(3.0, 0.1)]
        block = derive_editorial(_scan(series=series, duration=4.0))
        self.assertAlmostEqual(block["flickerLumaPerSecond"], 0.2, 6)
        self.assertAlmostEqual(block["staticFraction"], 1 / 3, 6)
        self.assertGreater(block["flickerP90"], 0.2)


class DegenerateInputTests(unittest.TestCase):
    def test_empty_mapping_never_raises(self) -> None:
        block = derive_editorial({})
        self.assertIsNone(block["shotCount"])
        self.assertEqual(block["seriesSamples"], 0)
        self.assertIn("scan-empty", block["degraded"])
        self.assertIn("duration-missing-or-invalid", block["degraded"])
        self.assertTrue(block["limits"])

    def test_non_mapping_never_raises(self) -> None:
        block = derive_editorial(None)  # type: ignore[arg-type]
        self.assertIn("scan-not-an-object", block["degraded"])
        self.assertIsNone(block["medianShotSeconds"])

    def test_zero_samples_and_single_sample(self) -> None:
        empty = derive_editorial(_scan(series=[]))
        self.assertEqual(empty["seriesSamples"], 0)
        self.assertIn("series-empty", empty["degraded"])
        self.assertIsNone(empty["flickerLumaPerSecond"])
        self.assertIsNone(empty["staticFraction"])
        single = derive_editorial(_scan(series=[_row(0.0, 0.3)]))
        self.assertEqual(single["seriesSamples"], 1)
        self.assertIn("series-single-sample", single["degraded"])
        self.assertIsNone(single["lumaSlopePerMinute"])
        self.assertEqual(single["lumaStdDevAcrossSeries"], 0.0)

    def test_cuts_outside_the_runtime_are_dropped_and_reported(self) -> None:
        block = derive_editorial(_scan(
            duration=10.0, timebase=(1, 1), cuts=(2, 20)))
        self.assertEqual(block["shotCount"], 2)
        self.assertEqual(block["cutsPerMinuteOfRuntime"], 6.0)
        self.assertTrue(any(reason.startswith("cut-outside-runtime")
                            for reason in block["degraded"]))

    def test_malformed_field_types_do_not_raise(self) -> None:
        block = derive_editorial({
            "durationSeconds": "not-a-number",
            "timebase": {"numerator": 0, "denominator": 0},
            "cutPts": ["x", 12, None],
            "series": [None, 7, {"sourceSeconds": "bad"}],
            "seriesSummary": "bad",
            "strobe": "yes",
        })
        self.assertIsNone(block["medianShotSeconds"])
        self.assertIn("duration-missing-or-invalid", block["degraded"])
        self.assertTrue(any(reason.startswith("cut-pts-malformed")
                            for reason in block["degraded"]))
        self.assertIn("timebase-missing-or-invalid", block["degraded"])

    def test_whole_record_is_unwrapped(self) -> None:
        block = derive_editorial({"census": _scan(), "record": {"id": 1}})
        self.assertEqual(block["shotCount"], 6)


class WriterTests(unittest.TestCase):
    def _write_record(self, root: Path) -> Path:
        path = root / "example" / "census" / "1-a.json"
        writer_path = path
        path.parent.mkdir(parents=True)
        record = {
            "schemaVersion": "kumiki.example-census-evidence.v1",
            "census": _scan(series=[_row(float(i), 0.2 + 0.05 * i)
                                    for i in range(5)]),
            "record": {"id": 1, "slug": "a"},
        }
        text = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
        writer_path.write_text(text, encoding="utf-8")
        return writer_path

    def test_writer_is_additive_atomic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._write_record(root)
            first = writer.run(root=root, site=None, dry_run=False, limit=None,
                              report_only=False)
            self.assertEqual(first["written"], 1)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(list(payload)[-1], "editorial")
            self.assertEqual(payload["editorial"]["shotCount"], 6)
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))

            before = path.read_bytes()
            second = writer.run(root=root, site=None, dry_run=False, limit=None,
                                report_only=False)
            self.assertEqual(second["written"], 0)
            self.assertEqual(second["unchanged"], 1)
            self.assertEqual(path.read_bytes(), before)

    def test_dry_run_and_report_mode_do_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._write_record(root)
            before = path.read_bytes()
            writer.run(root=root, site=None, dry_run=True, limit=None,
                       report_only=False)
            self.assertEqual(path.read_bytes(), before)
            writer.run(root=root, site=None, dry_run=False, limit=None,
                       report_only=True)
            self.assertEqual(path.read_bytes(), before)

    def test_malformed_record_is_skipped_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "example" / "census" / "broken.json"
            path.parent.mkdir(parents=True)
            path.write_text("{not json", encoding="utf-8")
            other = root / "example" / "census" / "no-block.json"
            other.write_text('{"record": {"id": 2}}\n', encoding="utf-8")
            result = writer.run(root=root, site=None, dry_run=False,
                                limit=None, report_only=False)
            self.assertEqual(result["skipped"], 2)
            self.assertEqual(result["written"], 0)


class ReportIntegrationTests(unittest.TestCase):
    def _record(self, *, cut_seconds: float, strobe=False) -> dict:
        return {
            "editorial": {
                "shotCount": int(24 / cut_seconds),
                "medianShotSeconds": cut_seconds,
                "shotsUnderHalfSecondFraction": 0.25,
                "paceTrend": "accelerating",
                "paceDriftRatio": 3.0,
                "flickerLumaPerSecond": 0.02,
                "strobeFlag": strobe,
            },
            "census": {"cutsPerMinute": 60.0 / cut_seconds, "strobe": strobe},
            "record": {"id": "x"},
        }

    def test_columns_and_section_are_deterministic(self) -> None:
        columns = editorial_columns(self._record(cut_seconds=1.5))
        self.assertEqual(columns["median_shot_s"], 1.5)
        self.assertEqual(columns["shots_lt_0_5s_pct"], 25.0)
        self.assertEqual(columns["pace_trend"], "accelerating")
        self.assertEqual(columns["flicker"], 0.02)

        rows = [
            {"id": "b", "editorial_present": True, "median_shot_s": 2.0,
             "pace_trend": "accelerating", "pace_drift_ratio": 3.0,
             "flicker": 0.02, "shot_count": 5},
            {"id": "a", "editorial_present": True, "median_shot_s": 1.0,
             "pace_trend": "decelerating", "pace_drift_ratio": 0.4,
             "flicker": 0.06, "shot_count": 10},
            {"id": "s", "editorial_present": True, "median_shot_s": 0.05,
             "pace_trend": "decelerating", "pace_drift_ratio": 0.4,
             "flicker": 0.01, "shot_count": 400, "strobe": True},
        ]
        aggregate = editorial_aggregate(rows)
        self.assertEqual(aggregate["n"], 3)
        self.assertEqual(aggregate["non_strobe_n"], 2)
        self.assertEqual(
            [entry["id"] for entry in aggregate["accelerating_clips"]], ["b"])
        self.assertEqual(
            [entry["id"] for entry in aggregate["decelerating_clips"]], ["a"])
        self.assertEqual(
            [entry["id"] for entry in aggregate["flicker_outliers"]], ["a"])
        self.assertEqual(aggregate["strobe_ids"], ["s"])
        self.assertEqual(aggregate["shot_count_range"], {"min": 5, "max": 10})
        first = editorial_section_lines(aggregate, site="Example")
        second = editorial_section_lines(aggregate, site="Example")
        self.assertEqual(first, second)
        text = "\n".join(first)
        self.assertIn("## Editorial structure", text)
        self.assertIn("strobe", text)

    def test_absent_block_renders_an_explicit_placeholder(self) -> None:
        columns = editorial_columns(self._record(cut_seconds=1.5))
        self.assertTrue(columns["editorial_present"])
        absent = editorial_columns({"census": {"cutsPerMinute": 10.0}})
        self.assertFalse(absent["editorial_present"])
        self.assertIsNone(absent["median_shot_s"])
        lines = editorial_section_lines({}, site="Example")
        self.assertIn("editorial: not present", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
