"""Multi-character image-plane evidence is not semantic action or identity recognition."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.character_motion import (
    _read_config, combine_character_tracks, run_character_motion,
)
from kumiki_reference_lab.reviews.character_scene import load_character_scene


def _fraction(seconds):
    f = Fraction(seconds)
    return {"numerator": f.numerator, "denominator": f.denominator}


def track(xs, *, initial_y=15, missing_last=False):
    width, height, box_w, box_h = 160, 90, 20, 20
    observations = []
    origin_x = xs[0]
    for i, x in enumerate(xs):
        visible = i == 0 or not (missing_last and i == len(xs) - 1)
        status = ("seeded" if i == 0 else "cut-boundary" if not visible
                  else "matched-template")
        pix = {"x": x, "y": initial_y, "width": box_w, "height": box_h} if visible else None
        norm = ({k: round(pix[k] / (width if k in ("x", "width") else height), 7)
                 for k in pix} if pix else None)
        observations.append({
            "sampleOrdinal": i, "sourcePts": 1000 * i,
            "sourceSeconds": _fraction(i),
            "status": status,
            "boxPixels": pix, "boxNormalized": norm,
            "displacementPixels": ({"dx": x - origin_x, "dy": 0} if visible else None),
            "appearanceCorrelation": None if i == 0 or not visible else 0.95,
            "peakMargin": None if i == 0 or not visible else 0.18,
        })
    return {
        "schemaVersion": "kumiki.roi-track.v1",
        "sourceSha256": "a" * 64,
        "sourceStreamIndex": 0,
        "sourceTimebase": {"numerator": 1, "denominator": 1000},
        "scanWindowSeconds": 5,
        "coverage": "bounded-from-start-not-necessarily-full-video",
        "analyzer": {
            "analysisResolution": {"width": width, "height": height},
            "searchRadiusPixels": 12,
            "seedBoxNormalized": [xs[0] / width, initial_y / height,
                                  box_w / width, box_h / height],
        },
        "cutCandidatePts": [],
        "observations": observations,
    }


def roster():
    return [
        {"id": "person_a", "kind": "animated-human", "label": "Character A",
         "visualDescription": "Red jacket, black hair", "seedBox": [0.05, 1/6, 0.125, 2/9],
         "reseeds": None},
        {"id": "person_b", "kind": "animated-human", "label": "Character B",
         "visualDescription": "Blue scarf", "seedBox": [90/160, 1/6, 0.125, 2/9],
         "reseeds": None},
    ]


class CharacterMotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        (self.base / "synthetic.mp4").write_bytes(b"synthetic fixture; analyzer mocked")
        self.roster = roster()
        self.tracks = {"person_a": track([8, 12, 16]), "person_b": track([90, 80, 70])}

    def test_combine_two_subjects_no_fake_actions(self):
        scene, report = combine_character_tracks(self.roster, self.tracks)
        self.assertEqual(scene["sourceSha256"], "a" * 64)
        self.assertEqual(len(scene["appearances"]), 6)
        self.assertEqual(len(scene["characters"]), 2)
        self.assertEqual(scene["actions"], [])
        self.assertEqual(scene["utterances"], [])
        self.assertEqual(scene["identityClaims"], [])
        self.assertEqual(report["pairSummary"][0]["coVisibleSamples"], 3)
        self.assertEqual(report["pairSummary"][0]["closerSteps"], 2)
        self.assertEqual(report["pairSummary"][0]["fartherSteps"], 0)
        self.assertEqual(report["samples"][0]["pairwise"][0]["changeFromPreviousSample"],
                         "not-comparable")
        self.assertEqual(report["samples"][1]["pairwise"][0]["changeFromPreviousSample"],
                         "image-centers-closer")
        self.assertIn("not-semantic-recognition", report["evidenceStatus"])
        self.assertTrue(all(a["confidence"] == "low" and a["visibleTraits"] == []
                            and a["endPts"] - a["startPts"] == 1 for a in scene["appearances"]))

    def test_cut_loss_does_not_imply_presence(self):
        self.tracks["person_b"] = track([90, 80, 70], missing_last=True)
        scene, report = combine_character_tracks(self.roster, self.tracks)
        self.assertEqual(report["pairSummary"][0]["coVisibleSamples"], 2)
        self.assertEqual(len(scene["appearances"]), 5)
        self.assertIsNone(report["samples"][-1]["characters"]["person_b"]["boxNormalized"])
        self.assertEqual(report["samples"][-1]["pairwise"], [])

    def test_reseed_breaks_proximity_trend(self):
        item = self.tracks["person_b"]
        item["schemaVersion"] = "kumiki.roi-track.v2"
        item["analyzer"]["manualReseeds"] = [
            {"sourcePts": 2000, "box": [70/160, 15/90, 20/160, 20/90]}
        ]
        item["analyzer"]["identityLinkStatus"] = "not-established"
        for index, obs in enumerate(item["observations"]):
            obs["segmentIndex"] = 1 if index == 2 else 0
        item["observations"][2]["status"] = "manual-reseed"
        item["observations"][2]["displacementPixels"] = {"dx": 0, "dy": 0}
        scene, report = combine_character_tracks(self.roster, self.tracks)
        self.assertEqual(len(scene["appearances"]), 6)
        self.assertEqual(report["pairSummary"][0]["closerSteps"], 1)
        self.assertEqual(report["samples"][2]["pairwise"][0]["changeFromPreviousSample"],
                         "not-comparable")

    def test_reject_mismatched_source_clock_and_sample_grid(self):
        mutations = [
            lambda x: x.update(sourceSha256="b"*64),
            lambda x: x.update(sourceStreamIndex=1),
            lambda x: x.update(sourceTimebase={"numerator": 1, "denominator": 90000}),
            lambda x: x["observations"][1].update(sourcePts=900),
            lambda x: x["analyzer"].update(analysisResolution={"width": 180, "height": 90}),
            lambda x: x.update(cutCandidatePts=[1000]),
        ]
        for change in mutations:
            x = copy.deepcopy(self.tracks)
            change(x["person_b"])
            with self.subTest(change=change), self.assertRaises(ValueError):
                combine_character_tracks(self.roster, x)

    def test_config_schema_bounds_and_symlinks(self):
        config = self.base / "seeds.json"
        data = {"schemaVersion": "kumiki.multi-character-seeds.v1",
                "characters": self.roster}
        config.write_text(json.dumps(data))
        self.assertEqual(len(_read_config(config, width=160, height=90, radius=12)), 2)
        config.write_text('{"schemaVersion":"x","schemaVersion":"y"}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            _read_config(config, width=160, height=90, radius=12)
        for altered in [
            {"characters": [self.roster[0]]},
            {"characters": self.roster + [copy.deepcopy(self.roster[0])]},
        ]:
            candidate = {**data, **altered}
            config.write_text(json.dumps(candidate))
            with self.assertRaises(ValueError):
                _read_config(config, width=160, height=90, radius=12)
        config.unlink()
        config.symlink_to(self.base)
        with self.assertRaisesRegex(ValueError, "regular"):
            _read_config(config, width=160, height=90, radius=12)

    def test_runner_atomic_publishes_only_validated_result(self):
        config = self.base / "seeds.json"
        config.write_text(json.dumps({
            "schemaVersion": "kumiki.multi-character-seeds.v1", "characters": self.roster}))
        destination = self.base / "motion"
        by_box = [self.tracks["person_a"], self.tracks["person_b"]]
        with patch("kumiki_reference_lab.pipeline.character_motion.analyze_roi_track",
                   side_effect=by_box) as mock:
            result_path = run_character_motion(
                self.base / "synthetic.mp4", config, destination)
        self.assertEqual(mock.call_count, 2)
        self.assertTrue(result_path.is_file())
        result = json.loads(result_path.read_text())
        self.assertEqual(result["sampleCount"], 3)
        self.assertEqual(load_character_scene(destination / "character-scene.json")["actions"], [])
        self.assertEqual(len(list((destination / "roi-tracks").glob("*.json"))), 2)
        with self.assertRaisesRegex(ValueError, "nonexisting"):
            run_character_motion(self.base / "synthetic.mp4", config, destination)

    def test_failure_never_publishes_partial(self):
        config = self.base / "seeds.json"
        config.write_text(json.dumps({
            "schemaVersion": "kumiki.multi-character-seeds.v1", "characters": self.roster}))
        dest = self.base / "failed"
        with patch("kumiki_reference_lab.pipeline.character_motion.analyze_roi_track",
                   side_effect=[self.tracks["person_a"], RuntimeError("tracking failed")]):
            with self.assertRaisesRegex(RuntimeError, "tracking failed"):
                run_character_motion(self.base / "synthetic.mp4", config, dest)
        self.assertFalse(dest.exists())

    def test_cli(self):
        args = build_parser().parse_args([
            "character-motion", "clip.mp4", "seeds.json", "--out", "runs/multi",
            "--max-seconds", "12"])
        self.assertEqual(args.command, "character-motion")
        self.assertEqual(args.max_seconds, 12)
        self.assertEqual(args.seeds, Path("seeds.json"))


if __name__ == "__main__":
    unittest.main()
