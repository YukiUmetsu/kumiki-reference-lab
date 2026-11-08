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
            json.dumps(artifact, allow_nan=False)

    def test_flat_video_does_not_invent_vectors(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "flat.mkv"
            self._create_clip(video, filter_name="color=c=gray:s=160x90:r=10:d=1")
            result = analyze_sparse_flow(video, seconds=2, max_samples=6,
                                         threshold=0.95)
            self.assertTrue(all(pair["status"] == "insufficient-consensus"
                                for pair in result["pairs"]))
            self.assertTrue(all(not pair["vectors"] for pair in result["pairs"]))

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


if __name__ == "__main__":
    unittest.main()
