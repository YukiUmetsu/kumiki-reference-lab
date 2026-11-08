import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.techniques.propose import (
    _expansion_cues, _highlight_cues, propose_techniques,
)
from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.analyze import run_analysis


CATALOG = Path(__file__).resolve().parents[1] / "catalog" / "entries"
ENTRY = {"revision": 1, "_entrySha256": "1" * 64}
SOURCE_SHA = "2" * 64


def _affine_pair(start, end, *, scale=1.045, status="measured"):
    return {
        "startPts": start, "endPts": end, "status": status,
        "geometryHypothesis": {
            "status": "affine-image-plane-candidate",
            "model": {"inlierFraction": 0.8, "areaScaleCandidate": scale,
                      "anisotropyCandidate": 1.025, "rotationDegreesCandidate": 0.2,
                      "reflectionOrInvalidGeometry": False,
                      "inlierSpanFraction": {"x": 0.6, "y": 0.7}},
        },
    }


def _appearance_frame(pts, x, luma=0.5, fraction=0.05):
    return {"sourcePts": pts, "appearance": {
        "brightPixelCentroid": {"x": x, "y": 0.5},
        "brightPixelFraction": fraction, "meanLumaProxy": luma,
    }}


class TechniqueCueRulesTests(unittest.TestCase):
    def test_enlargement_requires_two_adjacent_supported_pairs(self):
        report = {"pairs": [_affine_pair(0, 10), _affine_pair(10, 20),
                             _affine_pair(20, 30, scale=1.001)]}
        found = _expansion_cues(report, ENTRY, SOURCE_SHA)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["sourcePtsRange"], {"startPts": 0, "endPts": 20})
        self.assertEqual(found[0]["evidence"]["measurements"]["sampledPairCount"], 2)
        self.assertEqual(found[0]["interpretationStatus"], "review-required-not-verified")
        self.assertIn("Digital crop", " ".join(found[0]["plausibleAlternatives"]))

    def test_enlargement_cannot_cross_cut_or_high_anisotropy(self):
        pair = _affine_pair(10, 20)
        pair["geometryHypothesis"]["model"]["anisotropyCandidate"] = 1.2
        report = {"pairs": [_affine_pair(0, 10), {"status": "cut-boundary"},
                             pair, _affine_pair(20, 30)]}
        self.assertEqual(_expansion_cues(report, ENTRY, SOURCE_SHA), [])

    def test_highlight_cue_requires_stable_luma_and_consecutive_times(self):
        samples = [_appearance_frame(0, .2), _appearance_frame(10, .25),
                   _appearance_frame(20, .36)]
        changes = [{"startPts": 0, "endPts": 10,
                    "status": "measured-display-appearance-change"},
                   {"startPts": 10, "endPts": 20,
                    "status": "measured-display-appearance-change"}]
        found = _highlight_cues({"samples": samples, "changes": changes}, ENTRY, SOURCE_SHA)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["evidence"]["measurements"]
                         ["brightCentroidDisplacementNormalized"]["dx"], .16)
        changed = copy.deepcopy(samples)
        changed[1]["appearance"]["meanLumaProxy"] = .8
        self.assertEqual(_highlight_cues({"samples": changed, "changes": changes},
                                         ENTRY, SOURCE_SHA), [])
        changes[0]["status"] = "cut-boundary"
        self.assertEqual(_highlight_cues({"samples": samples, "changes": changes},
                                         ENTRY, SOURCE_SHA), [])

    def test_bright_static_content_is_not_a_lighting_suggestion(self):
        samples = [_appearance_frame(x * 10, .2) for x in range(4)]
        changes = [{"startPts": x * 10, "endPts": (x + 1) * 10,
                    "status": "measured-display-appearance-change"} for x in range(3)]
        self.assertEqual(_highlight_cues({"samples": samples, "changes": changes},
                                         ENTRY, SOURCE_SHA), [])

    def test_cli_parser_has_review_only_command(self):
        args = build_parser().parse_args(["propose-techniques", "run/analysis-run.json"])
        self.assertEqual(args.command, "propose-techniques")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe unavailable")
class TechniqueProvenanceIntegrationTests(unittest.TestCase):
    def _run(self, root):
        source = root / "source.mkv"
        result = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
            "-c:v", "ffv1", str(source),
        ], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        return run_analysis(source, root / "runs", seconds=2, thumbnails=4)

    def test_verified_bundle_produces_stable_empty_review_when_stages_absent(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = self._run(Path(temp))
            first = propose_techniques(manifest, CATALOG)
            self.assertEqual(first, propose_techniques(manifest, CATALOG))
            self.assertEqual(first["status"], "review-candidates-only")
            self.assertEqual(first["candidates"], [])
            self.assertFalse(first["method"]["hasSemanticUnderstanding"])
            self.assertTrue(first["method"]["humanApprovalRequired"])
            self.assertEqual(first["availableEvidence"], ["cuts"])
            self.assertEqual(len(first["provenance"]["analysisRunSha256"]), 64)

    def test_integrity_check_rejects_modified_frame_before_proposing(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest_path = self._run(Path(temp))
            manifest = json.loads(manifest_path.read_text())
            image_path = next(record["path"] for record in manifest["files"]
                              if record["path"].endswith(".jpg"))
            (manifest_path.parent / image_path).write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "missing or modified"):
                propose_techniques(manifest_path, CATALOG)

    def test_rejects_wrong_catalog_or_manifest_name(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = self._run(Path(temp))
            with self.assertRaisesRegex(ValueError, "catalog directory"):
                propose_techniques(manifest, Path(temp) / "missing-catalog")
            with self.assertRaisesRegex(ValueError, "expected an analysis-run.json"):
                propose_techniques(manifest.parent / "source-manifest.json", CATALOG)


if __name__ == "__main__":
    unittest.main()
