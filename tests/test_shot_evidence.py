import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.shots.evidence import (
    build_shot_evidence, summarize_edit_regions,
)
from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.analyze import run_analysis


def _frames(points, anomalies=None):
    return {"sourceTimebase": {"numerator": 1, "denominator": 100},
            "frames": [{"sampleOrdinal": n, "sourcePts": pts}
                       for n, pts in enumerate(points)],
            "anomalies": anomalies if anomalies is not None else []}


def _cuts(*pts):
    return {"candidates": [{"sourcePts": pts} for pts in pts]}


def _appearance(*pts):
    return {"samples": [{"sourcePts": pts, "appearance": {
        "meanLumaProxy": 0.5, "lumaContrastP90MinusP10": .6,
        "meanSaturation": .1, "brightPixelFraction": .2}}
                         for pts in pts]}


def _motion(*pairs):
    return {"samples": [{"sourcePts": n} for n in range(6)],
            "pairs": [{"startPts": a, "endPts": b,
                       "dxNormalized": .05, "dyNormalized": 0.0}
                      for a, b in pairs]}


def _sparse(*pairs):
    return {"samples": [{"sourcePts": n} for n in range(6)],
            "pairs": [{"startPts": a, "endPts": b,
                       "geometryHypothesis": {"status": "affine-image-plane-candidate"}}
                      for a, b in pairs]}


class ShotEvidencePureTests(unittest.TestCase):
    def test_segmentation_is_inclusive_start_exclusive_candidate_end(self):
        result = summarize_edit_regions(
            _frames([0, 1, 2, 3, 4, 5]), _cuts(0, 3),
            appearance=_appearance(0, 2, 3, 5),
            motion=_motion((0, 2), (2, 3), (3, 5)),
            sparse=_sparse((0, 2), (2, 3), (3, 5)),
        )
        self.assertEqual(result["status"], "candidate-edit-regions")
        self.assertEqual(result["ignoredCutCandidatePts"], [0])
        self.assertEqual(len(result["regions"]), 2)
        first, second = result["regions"]
        self.assertEqual((first["startPtsInclusive"], first["endPtsExclusive"],
                          first["lastObservedFramePts"]), (0, 3, 2))
        self.assertEqual((second["startPtsInclusive"], second["endPtsExclusive"]),
                         (3, None))
        self.assertEqual((first["frameCount"], second["frameCount"]), (3, 3))
        self.assertEqual(first["observations"]["appearance"]["sourcePts"], [0, 2])
        self.assertEqual(first["observations"]["motion"]["pairCount"], 1)
        self.assertEqual(second["observations"]["sparseFlow"]
                         ["affineImageCandidatePairCount"], 1)
        self.assertEqual(first["interpretationStatus"], "not-performed")

    def test_no_edits_does_not_manufacture_an_end_timestamp(self):
        result = summarize_edit_regions(_frames([10, 20, 30]), _cuts())
        self.assertEqual(len(result["regions"]), 1)
        self.assertIsNone(result["regions"][0]["endPtsExclusive"])
        self.assertEqual(result["regions"][0]["lastObservedFramePts"], 30)
        self.assertIsNone(result["regions"][0]["observations"]["motion"])

    def test_missing_or_decreasing_pts_blocks_all_segments(self):
        for frames in (_frames([0, None, 2], [{"sampleOrdinal": 1,
                                               "reason": "missing-source-pts"}]),
                       _frames([0, 4, 3])):
            report = summarize_edit_regions(frames, _cuts())
            self.assertEqual(report["status"], "blocked-unreliable-source-pts")
            self.assertEqual(report["regions"], [])
            self.assertGreater(len(report["framePtsAnomalies"]), 0)

    def test_unmatched_cut_or_invalid_stage_samples_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "not present"):
            summarize_edit_regions(_frames([0, 10, 20]), _cuts(5))
        with self.assertRaisesRegex(ValueError, "appearance has sample PTS"):
            summarize_edit_regions(_frames([0, 10, 20]), _cuts(),
                                   appearance=_appearance(0, 15))

    def test_parser_exposes_machine_readable_edit_evidence(self):
        args = build_parser().parse_args(["shot-evidence", "run/analysis-run.json"])
        self.assertEqual(args.command, "shot-evidence")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe unavailable")
class ShotEvidenceIntegrationTests(unittest.TestCase):
    def test_verified_run_generates_stable_region_summary_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            video = root / "source.mkv"
            run = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(video),
            ], capture_output=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr.decode(errors="replace"))
            manifest = run_analysis(video, root / "runs", seconds=2, thumbnails=4)
            result = build_shot_evidence(manifest)
            self.assertEqual(result, build_shot_evidence(manifest))
            self.assertEqual(result["schemaVersion"], "kumiki.shot-evidence.v1")
            self.assertEqual(result["availableStages"], ["cuts", "frames"])
            self.assertEqual(len(result["regions"]), 1)
            self.assertEqual(result["regions"][0]["frameCount"], 10)
            cuts = manifest.parent / "shot-candidates.json"
            cuts.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing or modified"):
                build_shot_evidence(manifest)


if __name__ == "__main__":
    unittest.main()
