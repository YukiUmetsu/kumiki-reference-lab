import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.backends.ffmpeg.scene import CutScan
from kumiki_reference_lab.contracts.frames import FramePts
from kumiki_reference_lab.analyzers.motion.consensus import group_sparse_flows
from kumiki_reference_lab.analyzers.motion.geometry import fit_image_affine
from kumiki_reference_lab.analyzers.motion.sparse import analyze_sparse_flow


class ConsensusTests(unittest.TestCase):
    def test_consensus_reports_independent_image_movement_without_attributing_camera(self):
        points = ([{"x": i * 6, "y": i * 3, "dx": 2, "dy": 1}
                   for i in range(9)] +
                  [{"x": 100 + i * 2, "y": 35 + i * 3, "dx": -6, "dy": 0}
                   for i in range(4)])
        report = group_sparse_flows(points, 160, 90)
        self.assertEqual(report["status"], "multiple-image-translations")
        self.assertEqual([c["support"] for c in report["clusters"]], [9, 4])
        self.assertEqual(report["clusters"][1]["dxPixels"], -6)
        self.assertNotIn("camera", json.dumps(report))

    def test_tied_clusters_report_dominant_ambiguity(self):
        points = ([{"x": i, "y": 10, "dx": 1, "dy": 0} for i in range(5)] +
                  [{"x": i, "y": 40, "dx": -5, "dy": 1} for i in range(5)])
        self.assertEqual(group_sparse_flows(points, 160, 90)["status"],
                         "ambiguous-dominant-group")

    def test_small_or_invalid_vector_sets_are_not_fabricated(self):
        vectors = [{"x": 10, "y": 10, "dx": 1, "dy": 1}]
        self.assertEqual(group_sparse_flows(vectors, 160, 90)["status"],
                         "insufficient-consensus")
        with self.assertRaises(ValueError):
            group_sparse_flows([{"x": 1, "y": 1, "dx": float("nan"), "dy": 0}], 160, 90)


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy unavailable")
class FeatureTrackingTests(unittest.TestCase):
    def test_texture_tracks_integer_displacement_with_spatial_support(self):
        import numpy as np

        from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows

        base = np.random.default_rng(13).integers(0, 255, size=(90, 160), dtype=np.uint8)
        shifted = np.roll(np.roll(base, 2, axis=0), 4, axis=1)
        tracks = sparse_patch_flows(base.tobytes(), shifted.tobytes(), 160, 90)
        self.assertGreater(len(tracks["accepted"]), 20)
        consensus = group_sparse_flows(tracks["accepted"], 160, 90)
        self.assertEqual(consensus["status"], "single-image-translation-candidate")
        self.assertEqual(consensus["clusters"][0]["dxPixels"], 4)
        self.assertEqual(consensus["clusters"][0]["dyPixels"], 2)
        self.assertGreater(consensus["clusters"][0]["spatialCellCount"], 8)

    def test_independently_moving_textured_patch_forms_secondary_group(self):
        import numpy as np

        from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows

        rng = np.random.default_rng(43)
        background = rng.integers(0, 255, (90, 160), dtype=np.uint8)
        object_pixels = rng.integers(0, 255, (36, 46), dtype=np.uint8)
        before = background.copy()
        before[30:66, 92:138] = object_pixels
        after = np.roll(background, 2, axis=1)
        after[30:66, 85:131] = object_pixels
        tracks = sparse_patch_flows(before.tobytes(), after.tobytes(), 160, 90,
                                    max_points=64)
        result = group_sparse_flows(tracks["accepted"], 160, 90)
        self.assertEqual(result["status"], "multiple-image-translations")
        self.assertEqual([c["dxPixels"] for c in result["clusters"]], [2, -7])
        self.assertGreaterEqual(result["clusters"][1]["support"], 5)

    def test_flat_frame_is_unobservable(self):
        from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows

        flat = bytes([128] * (160 * 90))
        tracks = sparse_patch_flows(flat, flat, 160, 90)
        self.assertEqual(tracks["detectedCorners"], 0)
        self.assertEqual(group_sparse_flows(tracks["accepted"], 160, 90)["status"],
                         "insufficient-consensus")

    def test_optional_coarse_to_fine_recovers_motion_larger_than_local_search(self):
        import numpy as np

        from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows

        base = np.random.default_rng(513).integers(0, 256, (90, 160), dtype=np.uint8)
        shifted = np.roll(base, 14, axis=1)
        baseline = sparse_patch_flows(base.tobytes(), shifted.tobytes(), 160, 90,
                                      max_points=64, radius=8)
        improved = sparse_patch_flows(base.tobytes(), shifted.tobytes(), 160, 90,
                                      max_points=64, radius=8, pyramid_levels=2)
        self.assertFalse(any(v["dx"] == 14 for v in baseline["accepted"]))
        recovered = [v for v in improved["accepted"] if v["dx"] == 14 and v["dy"] == 0]
        self.assertGreaterEqual(len(recovered), 6)
        self.assertTrue(all(v["searchLevel"] == 2 and
                            v["roundtripErrorPixels"] <= 1.5 for v in recovered))
        self.assertTrue(all(v["searchLevel"] in (1, 2) for v in improved["accepted"]))

    def test_coarse_to_fine_does_not_invent_motion_on_flat_video(self):
        from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows

        flat = bytes([100] * (160 * 90))
        result = sparse_patch_flows(flat, flat, 160, 90, pyramid_levels=2)
        self.assertEqual(result["detectedCorners"], 0)
        self.assertEqual(result["accepted"], [])
        with self.assertRaisesRegex(ValueError, "pyramid_levels"):
            sparse_patch_flows(flat, flat, 160, 90, pyramid_levels=3)
        with self.assertRaisesRegex(ValueError, "pyramid_levels"):
            sparse_patch_flows(flat, flat, 160, 90, pyramid_levels=True)

    def test_coarse_fallback_preserves_successful_level_one_matches(self):
        import numpy as np

        from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows

        original = np.random.default_rng(219).integers(0, 256, (90, 160),
                                                        dtype=np.uint8)
        translated = np.roll(original, 4, axis=1)
        baseline = sparse_patch_flows(original.tobytes(), translated.tobytes(),
                                      160, 90, radius=8)
        extended = sparse_patch_flows(original.tobytes(), translated.tobytes(),
                                      160, 90, radius=8, pyramid_levels=2)
        self.assertGreater(len(baseline["accepted"]), 10)
        by_origin = {(v["x"], v["y"]): v for v in extended["accepted"]}
        for vector in baseline["accepted"]:
            candidate = by_origin[(vector["x"], vector["y"])]
            self.assertEqual(candidate["searchLevel"], 1)
            self.assertEqual({k: v for k, v in candidate.items()
                              if k != "searchLevel"}, vector)

    def test_coarse_fallback_abstains_on_repeated_texture(self):
        import numpy as np

        from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows

        tile = np.random.default_rng(24).integers(0, 256, (8, 8), dtype=np.uint8)
        original = np.tile(tile, (12, 20))[:90, :160]
        translated = np.roll(original, 14, axis=1)
        result = sparse_patch_flows(original.tobytes(), translated.tobytes(),
                                    160, 90, max_points=64, radius=8,
                                    pyramid_levels=2)
        self.assertEqual(result["detectedCorners"], 64)
        self.assertEqual(result["accepted"], [])
        self.assertEqual(result["rejected"]["forward-failed"], 64)
        refined = sparse_patch_flows(original.tobytes(), translated.tobytes(),
                                     160, 90, max_points=64, radius=8,
                                     pyramid_levels=2, subpixel_refinement=True,
                                     subpixel_reverse_check=True)
        self.assertEqual(refined["accepted"], [])

    def test_affine_fit_recovers_controlled_image_zoom_without_calling_it_a_camera(self):
        points = [{"x": x, "y": y,
                   "dx": 0.065 * (x - 80) + 2,
                   "dy": 0.065 * (y - 45) - 1}
                  for x in range(15, 146, 20) for y in range(15, 76, 15)]
        points += [{"x": 22 + i, "y": 40 + i, "dx": -8, "dy": 7}
                   for i in range(5)]
        result = fit_image_affine(points, 160, 90)
        self.assertEqual(result["status"], "affine-image-plane-candidate")
        self.assertGreaterEqual(result["inliers"], 34)
        self.assertAlmostEqual(result["model"]["areaScaleCandidate"], 1.065, delta=0.001)
        self.assertLess(result["model"]["rmsAffinePixels"], 0.1)
        self.assertFalse(result["model"]["calibratedConfidence"])
        self.assertEqual(len(result["inlierPointIndices"]), result["inliers"])

    def test_patch_tracker_and_affine_fit_recover_resampled_scale(self):
        import numpy as np

        from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows

        before = np.random.default_rng(111).integers(0, 256, (90, 160), dtype=np.uint8)
        yy, xx = np.indices(before.shape)
        sx = np.rint((xx - 80) / 1.06 + 80).astype(int)
        sy = np.rint((yy - 45) / 1.06 + 45).astype(int)
        after = before[np.clip(sy, 0, 89), np.clip(sx, 0, 159)]
        vectors = sparse_patch_flows(before.tobytes(), after.tobytes(), 160, 90,
                                     max_points=64)["accepted"]
        result = fit_image_affine(vectors, 160, 90)
        self.assertGreater(len(vectors), 25)
        self.assertEqual(result["status"], "affine-image-plane-candidate")
        self.assertAlmostEqual(result["model"]["areaScaleCandidate"], 1.06,
                               delta=0.015)

    def test_affine_fit_recovers_controlled_image_rotation(self):
        import math

        angle = math.radians(4)
        cosine, sine = math.cos(angle), math.sin(angle)
        points = []
        for x in range(15, 146, 20):
            for y in range(15, 76, 15):
                dx = (cosine - 1) * (x - 80) - sine * (y - 45)
                dy = sine * (x - 80) + (cosine - 1) * (y - 45)
                points.append({"x": x, "y": y, "dx": dx, "dy": dy})
        result = fit_image_affine(points, 160, 90)
        self.assertEqual(result["status"], "affine-image-plane-candidate")
        self.assertAlmostEqual(result["model"]["rotationDegreesCandidate"], 4, delta=0.1)

    def test_affine_not_selected_for_pure_translation_or_collinear_points(self):
        points = [{"x": x, "y": y, "dx": 3, "dy": -2}
                  for x in range(15, 146, 20) for y in range(15, 76, 15)]
        self.assertEqual(fit_image_affine(points, 160, 90)["status"],
                         "translation-sufficient")
        collinear = [{"x": i * 10, "y": 40, "dx": 2, "dy": 0}
                     for i in range(12)]
        self.assertEqual(fit_image_affine(collinear, 160, 90)["status"],
                         "no-robust-affine-consensus")
        self.assertEqual(fit_image_affine(points[:3], 160, 90)["status"],
                         "insufficient-points")


@unittest.skipUnless(importlib.util.find_spec("numpy") and shutil.which("ffmpeg") and
                     shutil.which("ffprobe"), "NumPy/FFmpeg not available")
class SparseFlowIntegrationTests(unittest.TestCase):
    def _create_clip(self, path: Path, *, filter_name: str = "testsrc2=s=160x90:r=10:d=1",
                     vfr: bool = False) -> None:
        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", filter_name]
        if vfr:
            args += ["-vf", "setpts='if(lt(N,5),N,N*2)/(10*TB)'", "-fps_mode", "vfr"]
        args += ["-c:v", "ffv1", str(path)]
        process = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_real_video_reports_pts_and_schema_and_cut_independent_motion(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "vfr.mkv"
            self._create_clip(video, vfr=True)
            artifact = analyze_sparse_flow(video, seconds=2, max_samples=8,
                                           threshold=0.95)
            self.assertEqual(artifact["schemaVersion"], "kumiki.sparse-flow.v1")
            # Nearest-PTS sampling de-duplicates frames if target times round
            # to the same source frame; max_samples is a cap, not a promise.
            self.assertGreaterEqual(len(artifact["samples"]), 5)
            self.assertLessEqual(len(artifact["samples"]), 8)
            self.assertEqual(len(artifact["pairs"]), len(artifact["samples"]) - 1)
            self.assertTrue(all(pair["deltaTimeSeconds"]["numerator"] > 0
                                for pair in artifact["pairs"]))
            self.assertGreater(len({p["deltaTimeSeconds"]["numerator"]
                                    for p in artifact["pairs"]}), 1)
            self.assertFalse(artifact["analyzer"]["calibratedConfidence"])
            self.assertIn(artifact["temporalTracklets"]["status"],
                          ("candidate-only", "insufficient-continuity"))
            self.assertFalse(artifact["temporalTracklets"]["semanticIdentityVerified"])
            self.assertTrue(all(track["kinematics"]["durationSeconds"]["numerator"] > 0
                                and track["kinematics"]["durationSeconds"]["denominator"] > 0
                                for track in artifact["temporalTracklets"]["tracklets"]))
            self.assertTrue(all((pair["geometryHypothesis"] is None)
                                == (pair["status"] == "cut-boundary")
                                for pair in artifact["pairs"]))
            json.dumps(artifact, allow_nan=False)

    def test_real_video_opt_in_pyramid_contract_has_traceable_search_levels(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "source.mkv"
            self._create_clip(video)
            artifact = analyze_sparse_flow(video, seconds=2, max_samples=5,
                                           pyramid_levels=2)
            self.assertEqual(artifact["analyzer"]["method"],
                             "shi-tomasi-approx-patch-ncc-fb-consensus-affine-pyramid2-v1")
            self.assertEqual(artifact["analyzer"]["pyramidLevels"], 2)
            self.assertTrue(all("searchLevel" in vector
                                for pair in artifact["pairs"] for vector in pair["vectors"]))
            json.dumps(artifact, allow_nan=False)

    def test_real_video_opt_in_subpixel_contract_is_explicitly_integer_reverse_only(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "source.mkv"
            self._create_clip(video, vfr=True)
            artifact = analyze_sparse_flow(video, seconds=2, max_samples=6,
                                           subpixel_refinement=True)
            self.assertEqual(artifact["analyzer"]["method"],
                             "shi-tomasi-approx-patch-ncc-fb-consensus-affine-subpixel-v1")
            self.assertEqual(artifact["analyzer"]["subpixelReverseVerification"],
                             "integer-peak-only")
            vectors = [v for pair in artifact["pairs"] for v in pair["vectors"]]
            self.assertGreaterEqual(len(vectors), 1)
            self.assertTrue(all(v["subpixelReverseVerification"] == "integer-peak-only"
                                and v["subpixelPeakStatus"] in
                                ("candidate-1d-parabola", "integer-fallback")
                                for v in vectors))
            multiscale = analyze_sparse_flow(video, seconds=2, max_samples=5,
                                             pyramid_levels=2,
                                             subpixel_refinement=True)
            self.assertEqual(multiscale["analyzer"]["method"],
                             "shi-tomasi-approx-patch-ncc-fb-consensus-affine-pyramid2-subpixel-v1")
            self.assertEqual(multiscale["analyzer"]["pyramidLevels"], 2)
            checked = analyze_sparse_flow(video, seconds=2, max_samples=5,
                                          subpixel_refinement=True,
                                          subpixel_reverse_check=True)
            self.assertEqual(checked["analyzer"]["method"],
                             "shi-tomasi-approx-patch-ncc-fb-consensus-affine-subpixel-bidir-v1")
            self.assertEqual(checked["analyzer"]["subpixelReverseVerification"],
                             "fractional-bilinear-patch-check")
            self.assertTrue(all("subpixelReverseErrorPixels" in v
                                for pair in checked["pairs"] for v in pair["vectors"]))
            json.dumps(artifact, allow_nan=False)

    def test_opt_in_projective_evidence_preserves_cut_and_vfr_uncertainty(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "source.mkv"
            self._create_clip(video, vfr=True)
            original = analyze_sparse_flow(video, seconds=2, max_samples=6)
            self.assertNotIn("projectiveModel", original["analyzer"])
            self.assertTrue(all("projectiveHypothesis" not in pair
                                for pair in original["pairs"]))
            projective = analyze_sparse_flow(video, seconds=2, max_samples=6,
                                             projective_hypotheses=True)
            self.assertEqual(projective["analyzer"]["projectiveModel"],
                             "normalized-dlt-bounded-ransac-v1")
            self.assertEqual(projective["analyzer"]["projectiveMaxHypotheses"], 256)
            self.assertTrue(all((pair["projectiveHypothesis"] is None)
                                == (pair["status"] == "cut-boundary")
                                for pair in projective["pairs"]))
            self.assertEqual([pair["startPts"] for pair in original["pairs"]],
                             [pair["startPts"] for pair in projective["pairs"]])
            json.dumps(projective, allow_nan=False)

    def test_flat_video_does_not_invent_vectors(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "flat.mkv"
            self._create_clip(video, filter_name="color=c=gray:s=160x90:r=10:d=1")
            result = analyze_sparse_flow(video, seconds=2, max_samples=6,
                                         threshold=0.95)
            self.assertTrue(all(pair["status"] == "insufficient-consensus"
                                for pair in result["pairs"]))
            self.assertTrue(all(not pair["vectors"] for pair in result["pairs"]))
            self.assertEqual(result["temporalTracklets"]["tracklets"], [])

    def test_cut_boundary_prevents_any_point_matching(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "source.mkv"
            video.write_bytes(b"source fixture")
            frames = [FramePts(i, i * 10, "pts") for i in range(5)]
            manifest = {"video": {"streamIndex": 0, "sourceTimebase":
                                   {"numerator": 1, "denominator": 100}},
                        "source": {"sha256": "a" * 64}}
            gray = bytes([128] * (160 * 90))
            with (patch("kumiki_reference_lab.analyzers.motion.sparse.inspect_source",
                        return_value=manifest),
                  patch("kumiki_reference_lab.analyzers.motion.sparse.read_frame_pts",
                        return_value=frames),
                  patch("kumiki_reference_lab.analyzers.motion.sparse.detect_hard_cut_pts",
                        return_value=CutScan(Fraction(1, 100), (10,))),
                  patch("kumiki_reference_lab.analyzers.motion.sparse.read_gray_frames",
                        return_value=[gray] * 5),
                  patch("kumiki_reference_lab.analyzers.motion.sparse.sparse_patch_flows",
                        return_value={"detectedCorners": 0, "accepted": [],
                                      "rejected": {key: 0 for key in (
                                          "low-texture", "forward-failed", "backward-failed",
                                          "roundtrip-inconsistent")}}) as match):
                output = analyze_sparse_flow(video, max_samples=5)
            self.assertEqual(output["pairs"][0]["status"], "cut-boundary")
            self.assertEqual(output["pairs"][0]["vectors"], [])
            self.assertEqual(output["pairs"][0]["consensus"], None)
            self.assertEqual(match.call_count, 3)
            self.assertEqual(output["temporalTracklets"]["tracklets"], [])


if __name__ == "__main__":
    unittest.main()
