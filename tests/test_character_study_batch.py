"""Atomic multi-window studies do not invent cross-window character identities."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.character_study_batch import (
    _window_schedule, run_character_study_batch,
)


class LocalCharacterStudyBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "original-video.mp4"
        self.source.write_bytes(b"synthetic source; sub-pipelines mocked")
        self.sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.out = self.root / "all-windows"
        self.calls = []
        self.failure_index = None
        self.mismatch_index = None

    def fake_study(self, source, folder, *, model, detector, start_seconds,
                   max_seconds, **kwargs):
        index = len(self.calls)
        self.calls.append((start_seconds, max_seconds))
        if self.failure_index == index:
            raise ValueError("synthetic window failed")
        folder.mkdir(parents=True)
        manifest = {
            "schemaVersion": "kumiki.local-character-study.v1",
            "sourceSha256": "f"*64 if self.mismatch_index == index else self.sha,
            "scanStartSeconds": start_seconds,
            "maxSeconds": max_seconds,
            "sourceWindowEndSeconds": start_seconds + max_seconds,
            "scanPrefixSeconds": (start_seconds+max_seconds
                                  if start_seconds+max_seconds <= 120 else None),
            "sourceDecodeMode": ("prefix-ordinal-pts-v1"
                                 if start_seconds+max_seconds <= 120 else
                                 "verified-seek-original-pts-v1"),
            "status": "completed-unverified-model-proposals",
            "modelTag": model, "detectorBackend": detector,
            "detectedRegionProposals": 10,
            "provisionalTracklets": 2,
            "provisionalCharacterIdsObserved": 2,
            "visionAppearanceProposals": 8,
        }
        result = folder / "study-manifest.json"
        result.write_text(json.dumps(manifest))
        return result

    def run_fake(self, **kwargs):
        with patch(
            "kumiki_reference_lab.pipeline.character_study_batch.run_local_character_study",
            side_effect=self.fake_study,
        ):
            return run_character_study_batch(
                self.source, self.out, model="local-vision:8b",
                **kwargs)

    def test_three_independent_windows_and_aggregate_counts(self):
        path = self.run_fake(start_seconds=10, window_seconds=5,
                             stride_seconds=15, window_count=3)
        manifest = json.loads(path.read_text())
        self.assertEqual(self.calls, [(10,5), (25,5), (40,5)])
        self.assertEqual(
            [(w["startSeconds"], w["endSeconds"]) for w in manifest["windows"]],
            [(10,15), (25,30), (40,45)],
        )
        self.assertEqual(manifest["sourceSha256"], self.sha)
        self.assertEqual(manifest["totalCounts"]["provisionalTracklets"], 6)
        self.assertEqual(manifest["totalCounts"]["visionAppearanceProposals"], 24)
        self.assertEqual(manifest["upperBoundModelCalls"], 57)
        self.assertEqual(manifest["identityContinuityAcrossWindows"], "not-established")
        self.assertNotIn("uniqueCharacters", manifest)
        for row in manifest["windows"]:
            child = self.out / row["manifest"]
            self.assertTrue(child.is_file())
            self.assertEqual(json.loads(child.read_text())["sourceSha256"], self.sha)
        with self.assertRaisesRegex(ValueError, "new nonexisting directory"):
            self.run_fake()

    def test_failure_after_first_window_never_publishes_partial_batch(self):
        self.failure_index = 1
        with self.assertRaisesRegex(ValueError, "window failed"):
            self.run_fake(window_count=3)
        self.assertEqual(self.calls, [(0,10), (10,10)])
        self.assertFalse(self.out.exists())

    def test_source_hash_mismatch_is_fail_closed(self):
        self.mismatch_index = 1
        with self.assertRaisesRegex(ValueError, "source identity"):
            self.run_fake(window_count=3)
        self.assertFalse(self.out.exists())

    def test_window_validation_rejects_overlaps_and_120s_excess(self):
        for args in (
            {"start_seconds": -1, "window_seconds": 10, "stride_seconds": 10, "window_count": 3},
            {"start_seconds": True, "window_seconds": 10, "stride_seconds": 10, "window_count": 3},
            {"start_seconds": 0, "window_seconds": 0, "stride_seconds": 10, "window_count": 3},
            {"start_seconds": 0, "window_seconds": 31, "stride_seconds": 31, "window_count": 3},
            {"start_seconds": 0, "window_seconds": 10, "stride_seconds": 9, "window_count": 3},
            {"start_seconds": 0, "window_seconds": 10, "stride_seconds": 10, "window_count": 7},
            {"start_seconds": 3590, "window_seconds": 10, "stride_seconds": 10, "window_count": 2},
            {"start_seconds": 0, "window_seconds": 10, "stride_seconds": True, "window_count": 2},
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                _window_schedule(**args)
        self.assertEqual(_window_schedule(
            start_seconds=0, window_seconds=10, stride_seconds=None, window_count=2),
            [(0, 10), (10, 20)])

    def test_late_seek_windows_still_have_distinct_local_id_namespaces(self):
        manifest_path = self.run_fake(
            start_seconds=125, window_seconds=3, window_count=2,
            stride_seconds=10)
        result = json.loads(manifest_path.read_text())
        self.assertEqual(self.calls, [(125,3), (135,3)])
        self.assertEqual(result["windowCount"], 2)
        self.assertEqual(result["identityContinuityAcrossWindows"], "not-established")
        self.assertEqual(result["totalCounts"]["provisionalTracklets"], 4)
        for row in result["windows"]:
            child = json.loads((self.out / row["manifest"]).read_text())
            self.assertEqual(child["sourceDecodeMode"], "verified-seek-original-pts-v1")
            self.assertIsNone(child["scanPrefixSeconds"])

    def test_local_inference_bounds_refused_without_any_model_invocation(self):
        for kwargs in (
            {"model": "../illegal"},
            {"model": "local-vision:8b", "detector": "cloud"},
            {"model": "local-vision:8b", "max_calls": 13},
            {"model": "local-vision:8b", "max_pairs": 7},
            {"model": "local-vision:8b", "port": False},
            {"model": "local-vision:8b", "review": None},
            {"model": "local-vision:8b", "window_count": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_character_study_batch(self.source, self.out, **kwargs)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.out.exists())

    def test_one_window_no_interactions_has_smaller_call_budget(self):
        result = self.run_fake(window_count=1, interactions=False, detector="apple-vision")
        payload = json.loads(result.read_text())
        self.assertEqual(payload["upperBoundModelCalls"], 8)
        self.assertEqual(payload["windowCount"], 1)

    def test_cli(self):
        args = build_parser().parse_args([
            "character-study-batch", "clip.mp4", "--model", "local-vision:8b",
            "--window-count", "4", "--window-seconds", "12",
            "--stride-seconds", "20", "--out", "runs/multi",
            "--skip-interactions",
        ])
        self.assertEqual(args.command, "character-study-batch")
        self.assertEqual(args.window_count, 4)
        self.assertEqual(args.stride_seconds, 20)
        self.assertTrue(args.skip_interactions)


if __name__ == "__main__":
    unittest.main()
