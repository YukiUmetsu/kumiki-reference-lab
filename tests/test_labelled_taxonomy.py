"""Offline tests for the labelled motion-component taxonomy and applier.

Every fixture is synthetic. No research record, media, network or ffmpeg is
used, and the only repository files read are the taxonomy JSON and its human
doc. The tests pin the contract: unique ids, resolvable thresholds, explicit
missing-field refusal, gate-floor handling, deterministic and idempotent
output, and no writes outside the declared outputs.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "label_taxonomy", ROOT / "scripts" / "label_taxonomy.py")
driver = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(driver)

TAXONOMY_PATH = ROOT / "catalog" / "taxonomy" / "motion-components.v1.json"
DOC_PATH = ROOT / "docs" / "labelled-motion-taxonomy.md"
NOT_SET = object()


def base_census(**overrides) -> dict:
    census = {
        "durationSeconds": 120.0,
        "cutPts": list(range(1000, 61000, 1000)),
        "cutCount": 60,
        "cutsPerMinute": 50.0,
        "medianCutGapSeconds": 1.2,
        "medianCutGapFrames": 30.0,
        "minCutGapSeconds": 0.2,
        "p10CutGapSeconds": 0.4,
        "burstFraction": 0.1,
        "strobe": False,
        "seriesSummary": {
            "meanDisplayLuma": 0.3,
            "meanSaturation": 0.4,
            "samples": 120,
            "sampledSeconds": 120.0,
            "decodeCoverageFraction": 1.0,
        },
    }
    census.update(overrides)
    return census


def base_editorial(**overrides) -> dict:
    editorial = {
        "shotCount": 61,
        "medianShotSeconds": 1.2,
        "paceFirstThird": 60.0,
        "paceMiddleThird": 50.0,
        "paceLastThird": 40.0,
        "paceDriftRatio": 1.5,
        "paceTrend": "accelerating",
        "flickerLumaPerSecond": 0.02,
        "staticFraction": 0.2,
        "lumaSlopePerMinute": 0.1,
        "lumaSlopeR2": 0.5,
        "seriesSamples": 120,
        "degraded": [],
    }
    editorial.update(overrides)
    return editorial


def base_audio(**overrides) -> dict:
    audio = {
        "durationSeconds": 120.0,
        "integratedLufs": -12.0,
        "loudnessRangeLu": 8.0,
        "truePeakDbfs": -0.2,
        "rmsDbfs": -16.0,
        "silenceFraction": 0.01,
        "tailSilenceSeconds": 0.2,
        "onsetsPerMinuteOfRuntime": 300.0,
        "loudnessSlopeLuPerMinute": 3.0,
        "loudnessSlopeR2": 0.5,
    }
    audio.update(overrides)
    return audio


def joined(*, census: dict | None = None, editorial=NOT_SET, audio=NOT_SET,
           motion=NOT_SET, identity=NOT_SET) -> dict:
    record = {
        "site": "fixture",
        "id": "1",
        "slug": "one",
        "census": copy.deepcopy(census) if census is not None
        else copy.deepcopy(base_census()),
    }
    if editorial is not NOT_SET:
        record["editorial"] = (copy.deepcopy(editorial) if editorial is not None
                               else None)
    if audio is not NOT_SET:
        record["audio"] = copy.deepcopy(audio) if audio is not None else None
    if motion is not NOT_SET:
        record["motionProfile"] = copy.deepcopy(motion)
    if identity is not NOT_SET:
        record["identityVerification"] = copy.deepcopy(identity)
    return record


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def make_site(root: Path, site: str = "fixture",
              records: list[dict] | None = None) -> None:
    for record in records or []:
        identifier = str(record["id"])
        slug = record.get("slug", identifier)
        census = {
            "schemaVersion": f"kumiki.{site}-census-evidence.v1",
            "site": site,
            "record": {"id": identifier, "slug": slug,
                       "path": f"{site}/videos/{identifier}-{slug}.json"},
            "census": copy.deepcopy(record["census"]),
        }
        if record.get("editorial") is not None:
            census["editorial"] = copy.deepcopy(record["editorial"])
        if record.get("identityVerification") is not None:
            census["identityVerification"] = copy.deepcopy(
                record["identityVerification"])
        if record.get("motionProfile") is not None:
            census["motionProfile"] = copy.deepcopy(record["motionProfile"])
        write_json(root / site / "census" / f"{identifier}-{slug}.json", census)
        if record.get("audio") is not None:
            audio = {
                "schemaVersion": f"kumiki.{site}-audio-evidence.v1",
                "site": site,
                "record": {"id": identifier, "slug": slug,
                           "path": f"{site}/videos/{identifier}-{slug}.json"},
                "audio": copy.deepcopy(record["audio"]),
            }
            write_json(root / site / "audio" / f"{identifier}-{slug}.json", audio)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


class TaxonomyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = driver.load_taxonomy(TAXONOMY_PATH)

    def test_taxonomy_schema_and_unique_ids(self) -> None:
        self.assertEqual(self.taxonomy["schema"],
                         "kumiki.motion-component-taxonomy.v1")
        ids = [label["id"] for label in self.taxonomy["labels"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.taxonomy["version"], 1)

    def test_required_layers_exist(self) -> None:
        layers = {layer["id"] for layer in self.taxonomy["layers"]}
        self.assertEqual(layers, {
            "A-pacing", "B-temporal-appearance", "C-audio-energy",
            "D-transition-motion", "E-editorial-composites", "F-out-of-scope",
        })

    def test_every_label_has_required_fields_and_nonclaims(self) -> None:
        for label in self.taxonomy["labels"]:
            for field in driver.REQUIRED_LABEL_FIELDS:
                self.assertIn(field, label, label.get("id"))
            self.assertTrue(label["nonClaims"], label["id"])
            self.assertIn(label["evidenceTier"], driver.VALID_TIERS)

    def test_every_threshold_reference_resolves(self) -> None:
        thresholds = self.taxonomy["thresholds"]
        for label in self.taxonomy["labels"]:
            for condition in driver._iter_conditions({
                    key: label.get(key) for key in
                    ("positive", "exclusions", "eligibility", "gate",
                     "confidence")}):
                if condition.get("never"):
                    continue
                name = condition.get("threshold")
                if name is not None:
                    self.assertIn(name, thresholds, label["id"])

    def test_predicates_do_not_embed_numeric_literals(self) -> None:
        for label in self.taxonomy["labels"]:
            for condition in driver._iter_conditions({
                    key: label.get(key) for key in
                    ("positive", "exclusions", "eligibility", "gate")}):
                value = condition.get("value")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self.fail(f"{label['id']} embeds numeric literal {value!r}")

    def test_layer_d_is_unmeasured_and_requires_motion_profile(self) -> None:
        layer_d = [label for label in self.taxonomy["labels"]
                   if label["layer"] == "D-transition-motion"]
        self.assertEqual(len(layer_d), 7)
        for label in layer_d:
            self.assertEqual(label["evidenceTier"], "unmeasured")
            self.assertTrue(any(path.startswith("motionProfile.")
                                for path in label["requires"]), label["id"])
            self.assertEqual(label["exemplars"], [])

    def test_layer_f_is_non_assignable(self) -> None:
        layer_f = [label for label in self.taxonomy["labels"]
                   if label["layer"] == "F-out-of-scope"]
        self.assertEqual(len(layer_f), 9)
        for label in layer_f:
            self.assertFalse(label.get("assignable", True), label["id"])
            self.assertEqual(label["requires"], [])
            self.assertEqual(label["exemplars"], [])

    def test_computable_labels_have_exemplars(self) -> None:
        for label in self.taxonomy["labels"]:
            if label["evidenceTier"] == "unmeasured":
                self.assertEqual(label["exemplars"], [], label["id"])
                continue
            self.assertGreaterEqual(len(label["exemplars"]), 3, label["id"])
            self.assertLessEqual(len(label["exemplars"]), 6, label["id"])
            for exemplar in label["exemplars"]:
                self.assertEqual(set(exemplar), {"site", "id", "slug"})


class AssignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = driver.load_taxonomy(TAXONOMY_PATH)

    def assign(self, record: dict) -> dict:
        return driver.assign_record(record, self.taxonomy)

    def test_rapid_montage_assignment(self) -> None:
        assigned = self.assign(joined(editorial=base_editorial(),
                                      identity={"kind": "strict-sha",
                                                "shaMatched": True}))
        self.assertIn("a.rapid-montage", assigned["labels"])

    def test_single_shot_is_not_long_take(self) -> None:
        census = base_census(cutPts=[], cutCount=0, cutsPerMinute=0.0,
                             burstFraction=0.0)
        assigned = self.assign(joined(census=census, editorial=None))
        self.assertIn("a.single-shot", assigned["labels"])
        self.assertNotIn("a.long-take", assigned["labels"])
        self.assertNotIn("a.steady-cut", assigned["labels"])

    def test_missing_census_field_is_refused(self) -> None:
        census = base_census()
        del census["cutCount"]
        assigned = self.assign(joined(census=census, editorial=None))
        self.assertNotIn("a.rapid-montage", assigned["labels"])
        self.assertTrue(
            assigned["layerStatus"]["A-pacing"].startswith(
                "partial:missing-census"),
            assigned["layerStatus"]["A-pacing"])

    def test_missing_motion_profile_is_refused_and_reported(self) -> None:
        assigned = self.assign(joined(editorial=base_editorial(),
                                      audio=base_audio()))
        self.assertEqual(assigned["layerStatus"]["D-transition-motion"],
                         "missing-motion-profile")
        self.assertNotIn("d.hard-cut-dominant", assigned["labels"])

    def test_motion_profile_enables_layer_d(self) -> None:
        motion = {
            "transitions": {
                "shares": {
                    "hard-cut": 0.8,
                    "short-dissolve": 0.05,
                    "long-dissolve": 0.05,
                    "fade-through-black": 0.0,
                    "fade-through-white": 0.0,
                    "unknown": 0.1,
                },
                "transitionCount": 50,
            },
            "globalMotion": {
                "panFraction": 0.7, "staticFraction": 0.1,
                "observablePairs": 100,
            },
            "localMotion": {"centreShare": 0.3},
            "overlayActivity": {"upperThirdActivity": 0.5,
                                "lowerThirdActivity": 0.1},
        }
        assigned = self.assign(joined(editorial=base_editorial(),
                                      audio=base_audio(), motion=motion))
        self.assertIn("d.hard-cut-dominant", assigned["labels"])
        self.assertIn("d.pan-dominant", assigned["labels"])

    def test_composite_refuses_when_audio_is_missing(self) -> None:
        assigned = self.assign(joined(editorial=base_editorial(), audio=None))
        self.assertNotIn("e.building", assigned["labels"])
        self.assertEqual(assigned["layerStatus"]["E-editorial-composites"],
                         "partial:missing-audio")

    def test_composite_assigns_when_all_components_exist(self) -> None:
        assigned = self.assign(joined(editorial=base_editorial(),
                                      audio=base_audio()))
        self.assertIn("e.building", assigned["labels"])

    def test_audio_gate_floor_is_not_a_measurement(self) -> None:
        assigned = self.assign(joined(
            editorial=None, audio=base_audio(integratedLufs=-70.0)))
        self.assertNotIn("c.quiet-mix", assigned["labels"])
        self.assertNotIn("c.loud-mix", assigned["labels"])
        self.assertEqual(assigned["unassigned"].get("c.quiet-mix"),
                         "integrated-at-or-below-gate")
        self.assertEqual(assigned["unassigned"].get("c.loud-mix"),
                         "integrated-at-or-below-gate")

    def test_quiet_mix_above_gate_is_assigned(self) -> None:
        assigned = self.assign(joined(
            editorial=None, audio=base_audio(integratedLufs=-25.0)))
        self.assertIn("c.quiet-mix", assigned["labels"])

    def test_confidence_high_requires_strict_identity(self) -> None:
        assigned = self.assign(joined(
            editorial=base_editorial(),
            identity={"kind": "strict-sha", "shaMatched": True}))
        self.assertEqual(assigned["confidence"]["a.rapid-montage"], "high")

    def test_confidence_low_without_identity(self) -> None:
        assigned = self.assign(joined(editorial=base_editorial()))
        self.assertEqual(assigned["confidence"]["a.rapid-montage"], "low")

    def test_out_of_scope_labels_are_never_assigned(self) -> None:
        assigned = self.assign(joined(editorial=base_editorial(),
                                      audio=base_audio()))
        self.assertEqual(assigned["layerStatus"]["F-out-of-scope"],
                         "out-of-scope-layer")
        self.assertFalse(any(label.startswith("f.")
                             for label in assigned["labels"]))


class DriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = driver.load_taxonomy(TAXONOMY_PATH)

    def run_driver(self, root: Path, *, dry_run: bool = False,
                   json_out: Path | None = None,
                   md_out: Path | None = None) -> dict:
        return driver.run(
            root, ["fixture"], TAXONOMY_PATH,
            json_out or root / "out" / "taxonomy-assignments.json",
            md_out or root / "out" / "taxonomy-assignments.md",
            dry_run=dry_run)

    def test_summary_schema_and_counts(self) -> None:
        records = [
            joined(census=base_census(), editorial=base_editorial(),
                   audio=base_audio()),
            joined(census=base_census(cutPts=[], cutCount=0,
                                      cutsPerMinute=0.0),
                   editorial=None),
        ]
        records[1]["id"] = "2"
        records[1]["slug"] = "two"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_site(root, records=records)
            summary = self.run_driver(root)
            self.assertEqual(summary["schema"],
                             "kumiki.taxonomy-assignments.v1")
            self.assertEqual(summary["recordCount"], 2)
            self.assertEqual(summary["siteCount"], 1)
            self.assertEqual(summary["perSite"]["fixture"]["recordCount"], 2)
            self.assertEqual(
                sum(row["assigned"] for row in summary["labels"]),
                sum(len(record["labels"]) for record in
                    json.loads((root / "fixture" / "taxonomy-labels.json")
                               .read_text())["records"]))
            output = json.loads(
                (root / "fixture" / "taxonomy-labels.json").read_text())
            self.assertEqual(output["schema"],
                             "kumiki.fixture-taxonomy-labels.v1")
            self.assertEqual(output["recordCount"], 2)

    def test_cooccurrence_is_symmetric(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_site(root, records=[joined(editorial=base_editorial(),
                                            audio=base_audio())])
            summary = self.run_driver(root)
            for layer in ("A-pacing", "C-audio-energy"):
                block = summary["cooccurrence"][layer]
                counts = block["counts"]
                for row in range(len(counts)):
                    for column in range(len(counts)):
                        self.assertEqual(counts[row][column],
                                         counts[column][row])
                for index in range(len(counts)):
                    self.assertEqual(
                        counts[index][index],
                        next(row["assigned"] for row in summary["labels"]
                             if row["id"] == block["labels"][index]))

    def test_unmeasured_labels_are_all_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_site(root, records=[joined(editorial=base_editorial(),
                                            audio=base_audio())])
            summary = self.run_driver(root)
            self.assertEqual(len(summary["unmeasuredLabels"]), 16)
            for row in summary["unmeasuredLabels"]:
                self.assertEqual(row["assigned"], 0, row["id"])

    def test_determinism_same_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_site(root, records=[joined(census=base_census(),
                                            editorial=base_editorial(),
                                            audio=base_audio())])
            first = self.run_driver(
                root, json_out=root / "out" / "a.json")
            first_json = (root / "out" / "a.json").read_text()
            first_site = (root / "fixture" / "taxonomy-labels.json").read_text()
            second = self.run_driver(
                root, json_out=root / "out" / "b.json")
            second_json = (root / "out" / "b.json").read_text()
            second_site = (root / "fixture" / "taxonomy-labels.json").read_text()
            self.assertEqual(first, second)
            self.assertEqual(first_json, second_json)
            self.assertEqual(first_site, second_site)

    def test_idempotent_second_run_does_not_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_site(root, records=[joined(editorial=base_editorial(),
                                            audio=base_audio())])
            self.run_driver(root)
            outputs = [
                root / "fixture" / "taxonomy-labels.json",
                root / "out" / "taxonomy-assignments.json",
                root / "out" / "taxonomy-assignments.md",
            ]
            for path in outputs:
                os.utime(path, (1_000_000_000, 1_000_000_000))
            self.run_driver(root)
            for path in outputs:
                self.assertEqual(path.stat().st_mtime_ns // 1_000_000_000,
                                 1_000_000_000, path.name)

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_site(root, records=[joined(editorial=base_editorial(),
                                            audio=base_audio())])
            before = snapshot(root)
            self.run_driver(root, dry_run=True)
            self.assertEqual(snapshot(root), before)

    def test_no_writes_outside_declared_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_site(root, records=[joined(editorial=base_editorial(),
                                            audio=base_audio())])
            before = set(snapshot(root))
            self.run_driver(root)
            after = set(snapshot(root))
            declared = {
                "fixture/taxonomy-labels.json",
                "out/taxonomy-assignments.json",
                "out/taxonomy-assignments.md",
            }
            self.assertEqual(after - before, declared)
            for forbidden in ("videos", "stills", "dataset"):
                self.assertFalse((root / "fixture" / forbidden).exists())
            self.assertFalse((root / "fixture" / "audio" /
                              "taxonomy-labels.json").exists())


class DocumentationTests(unittest.TestCase):
    def test_doc_opens_with_scope_and_limits(self) -> None:
        text = DOC_PATH.read_text(encoding="utf-8")
        first_heading = next(line for line in text.splitlines() if line.strip())
        self.assertEqual(first_heading,
                         "# Labelled motion-component taxonomy")
        self.assertIn("measured predicates", text)
        self.assertIn("not a creative archetype", text)
        self.assertIn("Layer D", text)
        self.assertIn("unmeasured", text)
        self.assertIn("does not", text)


if __name__ == "__main__":
    unittest.main()
