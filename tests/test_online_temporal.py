"""No-model temporal shot and regional motion tests, including real PNG files."""
from __future__ import annotations

import io
import json
import random
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path

from kumiki_reference_lab.analyzers.motion.review import _png_rgb
from kumiki_reference_lab.pipeline.agent_frame_review import (
    finalize_frame_workspace,
)
from kumiki_reference_lab.pipeline.online_temporal import (
    _decode_review_png, build_shot_plan, derive_temporal_report,
    match_image_plane_motion, write_temporal_report, main,
)

WIDTH, HEIGHT = 128, 72
HASH = "a" * 64
ID = "example-org-test001"


def _rgb_random(width: int = WIDTH, height: int = HEIGHT) -> bytes:
    rng = random.Random(42)
    return bytes(rng.randrange(256) for _ in range(width * height * 3))


def _translated(raw: bytes, dx: int, dy: int, width: int = WIDTH,
                height: int = HEIGHT) -> bytes:
    result = bytearray(len(raw))
    for y in range(height):
        for x in range(width):
            xx, yy = x - dx, y - dy
            if 0 <= xx < width and 0 <= yy < height:
                i, j = (y * width + x) * 3, (yy * width + xx) * 3
                result[i:i + 3] = raw[j:j + 3]
    return bytes(result)


def _numeric(count: int = 30, cuts: tuple[int, ...] = (10, 20)) -> dict:
    frames = []
    for i in range(count):
        difference = (.65 if i in cuts else .05 if i % 5 else .15) if i else 0
        frames.append({
            "frameIndex": i, "decodedSeconds": round(i / 10, 6),
            "decodedPts": i * 100, "cutCandidate": i in cuts,
            "appearance": {"displayLumaProxy": .5,
                           "meanRgb": [.5, .5, .5],
                           "saturationProxy": .25,
                           "brightPixelFraction": .1,
                           "darkPixelFraction": .1},
            "changeFromPrevious": (
                {"meanPixelDelta": difference,
                 "changedPixelFraction": difference} if i else None),
        })
    return {
        "sourceSha256": HASH,
        "frameCount": count,
        "cutCandidateFrameIndices": list(cuts),
        "frames": frames,
        "video": {"width": WIDTH, "height": HEIGHT},
    }


class ShotPlanningTests(unittest.TestCase):
    def test_nonoverlapping_shots_represent_every_frame(self):
        report = build_shot_plan(_numeric())
        shots = report["shots"]
        self.assertEqual(len(shots), 3)
        self.assertEqual([(s["startFrameIndex"], s["endFrameIndex"])
                          for s in shots], [(0, 9), (10, 19), (20, 29)])
        self.assertEqual([i for s in shots for i in range(
            s["startFrameIndex"], s["endFrameIndex"] + 1)], list(range(30)))
        self.assertEqual(report["segmentation"]["selectedShotBoundaries"], [10, 20])
        self.assertEqual(report["motion"]["status"], "not-measured")
        self.assertEqual([s["entryCutCandidateFrameIndex"] for s in shots],
                         [None, 10, 20])
        for shot in shots:
            self.assertTrue(all(
                shot["startFrameIndex"] <= i <= shot["endFrameIndex"]
                for i in shot["reviewFrameIndices"]))

    def test_cluster_adjacent_cut_candidates(self):
        numeric = _numeric(cuts=(10, 11, 20))
        numeric["frames"][11]["changeFromPrevious"]["meanPixelDelta"] = .9
        report = build_shot_plan(numeric)
        self.assertEqual(report["segmentation"]["selectedShotBoundaries"], [11, 20])
        self.assertIn(10, report["segmentation"]["suppressedCandidateIndices"])

    def test_rejects_invalid_index_or_time(self):
        numeric = _numeric()
        numeric["frames"][9]["frameIndex"] = 19
        with self.assertRaisesRegex(ValueError, "sequential"):
            build_shot_plan(numeric)
        numeric = _numeric()
        numeric["frames"][9]["decodedSeconds"] = -2
        with self.assertRaisesRegex(ValueError, "increasing"):
            build_shot_plan(numeric)


class PatchMotionTests(unittest.TestCase):
    def test_recovers_global_image_plane_shift(self):
        original = _rgb_random()
        moved = _translated(original, 4, 0)
        result = match_image_plane_motion(
            original, moved, width=WIDTH, height=HEIGHT)
        self.assertEqual(result["status"], "coherent-image-plane-proxy")
        self.assertAlmostEqual(result["dominantVectorPixels"]["dx"], 4, delta=1)
        self.assertAlmostEqual(result["dominantVectorPixels"]["dy"], 0, delta=1)
        self.assertGreaterEqual(result["matchedRegions"], 4)
        self.assertGreaterEqual(result["coherenceFraction"], .65)

    def test_static_textured_frame_recovers_zero_shift(self):
        raw = _rgb_random()
        result = match_image_plane_motion(raw, raw, width=WIDTH, height=HEIGHT)
        self.assertEqual(result["dominantVectorPixels"], {"dx": 0.0, "dy": 0.0})

    def test_abstains_on_flat_frame(self):
        raw = bytes(WIDTH * HEIGHT * 3)
        result = match_image_plane_motion(raw, raw, width=WIDTH, height=HEIGHT)
        self.assertEqual(result["status"], "abstain-insufficient-texture")
        self.assertIsNone(result["dominantVectorPixels"])

    def test_minimum_supported_frame_dimensions(self):
        raw = _rgb_random(64, 36)
        measured = match_image_plane_motion(raw, raw, width=64, height=36)
        self.assertEqual(measured["dominantVectorPixels"], {"dx": 0.0, "dy": 0.0})

    def test_rejects_bad_buffers(self):
        with self.assertRaisesRegex(ValueError, "length mismatch"):
            match_image_plane_motion(b"short", b"short", width=WIDTH, height=HEIGHT)


class TemporalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.workspace = self.root / "workspace" / "frame-review" / ID
        (self.workspace / "frames").mkdir(parents=True)
        self.data_dir = self.root / "research" / "analysis" / "online-videos"
        self.data_dir.mkdir(parents=True)
        self.numeric = _numeric()
        (self.data_dir / (ID + ".json")).write_text(json.dumps({
            "id": ID, "numericEvidence": self.numeric, "schemaVersion": "test"
        }))
        texture = _rgb_random()
        moved = _translated(texture, 4, 0)
        for i in range(self.numeric["frameCount"]):
            raw = moved if i % 2 else texture
            (self.workspace / "frames" / f"frame-{i:06d}.png").write_bytes(
                _png_rgb(raw, WIDTH, HEIGHT))
        finalize_frame_workspace(
            self.workspace, study_id=ID,
            watch_url="https://example.org/reference",
            numeric=self.numeric, preview_width=WIDTH, preview_height=HEIGHT)

    def test_cinematic_insights_gets_stdlib_motion_without_cv2(self):
        from kumiki_reference_lab.pipeline.temporal_motion import build_temporal_motion
        from kumiki_reference_lab.pipeline.shot_intelligence import build_shot_intelligence
        shots = build_shot_intelligence(self.numeric)
        # Force the exact optional-dependency absence that cheap CI and
        # smaller local systems may experience.
        with patch.dict(sys.modules, {"cv2": None, "numpy": None}):
            data = build_temporal_motion(
                self.workspace, shots, max_pairs=8)
        self.assertEqual(
            data["status"], "measured-sampled-stdlib-block-motion-proxies")
        self.assertEqual(data["reportedPairCount"], len(data["pairs"]))
        self.assertLessEqual(len(data["pairs"]), 8)
        self.assertEqual(data["featureTracklets"], [])
        for pair in data["pairs"]:
            shot = next(s for s in shots["shots"]
                        if s["shotId"] == pair["shotId"])
            self.assertGreaterEqual(
                pair["startFrameIndex"], shot["startFrameIndex"])
            self.assertLess(
                pair["endFrameIndex"], shot["endFrameIndexExclusive"])
            self.assertEqual(
                pair["globalImageMotion"]["interpretation"],
                "not-optical-flow-not-verified-physical-camera")
            self.assertNotEqual(
                pair["globalImageMotion"]["status"],
                "supported-screen-affine-candidate")
            self.assertIsNone(pair["meanImageFeatureSpeedPixelsPerSecond"])

    def test_png_roundtrip_and_crc_detection(self):
        path = self.workspace / "frames" / "frame-000000.png"
        decoded = _decode_review_png(path, width=WIDTH, height=HEIGHT)
        self.assertEqual(decoded, _rgb_random())
        with self.assertRaisesRegex(ValueError, "dimensions"):
            _decode_review_png(path, width=160, height=90)
        altered = bytearray(path.read_bytes())
        altered[-14] ^= 1  # IEND CRC or an immediately preceding chunk byte
        path.write_bytes(bytes(altered))
        with self.assertRaises(ValueError):
            _decode_review_png(path, width=WIDTH, height=HEIGHT)

    def test_paginated_shots_standalone_cli(self):
        sink = io.StringIO()
        with redirect_stdout(sink):
            code = main(["shots", "--workspace", str(self.workspace),
                         "--limit", "2"])
        self.assertEqual(code, 0)
        first = json.loads(sink.getvalue())
        self.assertEqual(first["totalShotCandidates"], 3)
        self.assertTrue(first["hasMore"])
        sink = io.StringIO()
        with redirect_stdout(sink):
            code = main(["shots", "--workspace", str(self.workspace),
                         "--after-shot", str(first["nextAfterShotIndex"]),
                         "--limit", "2"])
        self.assertEqual(code, 0)
        second = json.loads(sink.getvalue())
        self.assertEqual(len(second["shots"]), 1)
        self.assertFalse(second["hasMore"])

    def test_sampled_motion_is_shot_local_and_json_persists(self):
        report = derive_temporal_report(
            self.workspace, max_motion_pairs=8, stride=4)
        self.assertEqual(len(report["shots"]), 3)
        self.assertLessEqual(len(report["motion"]["pairs"]), 8)
        self.assertEqual(report["motion"]["status"], "sampled-block-matching-proxies")
        boundaries = {s["startFrameIndex"] for s in report["shots"]}
        for pair in report["motion"]["pairs"]:
            self.assertNotIn(pair["toFrameIndex"], boundaries - {0})
            self.assertEqual(pair["toFrameIndex"] - pair["fromFrameIndex"], 1)
            self.assertGreater(pair["deltaSeconds"], 0)
        filename = write_temporal_report(
            self.workspace, max_motion_pairs=8, stride=4)
        self.assertTrue(filename.is_file())
        data = json.loads(filename.read_text())
        self.assertEqual(data["sourceSha256"], HASH)
        self.assertEqual(data["motion"]["evaluatedPairs"],
                         len(data["motion"]["pairs"]))
        self.assertTrue(all(isinstance(p["startSeconds"], (float, int))
                            for p in data["motion"]["pairs"]))
        # Only derived JSON enters research tree.
        self.assertTrue(all(p.suffix == ".json" for p in self.data_dir.iterdir()))



if __name__ == "__main__":
    unittest.main()
