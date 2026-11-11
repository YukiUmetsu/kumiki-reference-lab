"""Checkpointed, SHA-verified What Ships source studies with redacted progress."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.cli.app import build_parser, main
from kumiki_reference_lab.pipeline.whatships_local_worker import (
    _plan_windows, run_whatships_local_analysis,
)
from tests.test_video_sources import whatships_fixture


class WhatshipsLocalAnalysisWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = self.root/"catalog.json"
        self.snapshot.write_text(json.dumps(whatships_fixture()))
        self.source_a = self.root/"first.mp4"
        self.source_b = self.root/"second.mp4"
        self.source_a.write_bytes(b"synthetic first local movie")
        self.source_b.write_bytes(b"synthetic second local movie")
        self.sha_a = hashlib.sha256(self.source_a.read_bytes()).hexdigest()
        self.sha_b = hashlib.sha256(self.source_b.read_bytes()).hexdigest()
        self.bindings = self.root/"private-bindings.json"
        self.ledger = {
            "schemaVersion": "kumiki.whatships-local-media-bindings.v1",
            "createdOn": "2026-11-10",
            "catalogIndexUrl": "https://whatships.com/search-index.json",
            "disclaimer": "self-declared-source-identity-and-authorization-only",
            "bindings": [
                self.binding(self.source_a, self.sha_a, "film-one"),
                self.binding(self.source_b, self.sha_b, "film-two"),
            ],
        }
        self.write_ledger()
        self.out = self.root/"new-batch"
        self.calls = []
        self.fail_source = None
        self.mismatch_sha = False
        self.duration_a = "85.000000"
        self.duration_b = "32.000000"

    def binding(self, file, sha, slug):
        return {
            "sourceId": "whatships:"+slug,
            "watchUrl": f"https://whatships.com/videos/{slug}/",
            "localPath": str(file.resolve()),
            "mediaSha256": sha,
            "mediaSizeBytes": file.stat().st_size,
            "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator":1,"denominator":1000},
            "rightsBasis": "written-permission",
            "rightsNote": "Creator granted specific permission for private local analysis.",
            "identityNote": "Exact original post and visual video title were independently compared.",
            "rightsStatus": "user-declared-authorized",
            "verificationStatus": "operator-attestation-not-independently-verified",
            "boundOn": "2026-11-10",
        }

    def write_ledger(self):
        self.bindings.write_text(json.dumps(self.ledger))

    def fake_inspect(self, source, *, ffprobe, rights_status):
        self.assertEqual(rights_status, "user-declared-authorized")
        which = source.name == "first.mp4"
        return {
            "source": {"sha256": "f"*64 if self.mismatch_sha else (
                self.sha_a if which else self.sha_b)},
            "video": {
                "streamIndex": 0, "sourceTimebase": {"numerator":1,"denominator":1000},
                "durationSecondsReported": self.duration_a if which else self.duration_b,
            },
        }

    def fake_study(self, source, folder, **kwargs):
        self.calls.append((source.name, kwargs))
        if self.fail_source == source.name:
            raise ValueError("synthetic local vision model unavailable")
        folder.mkdir()
        expected_sha = self.sha_a if source.name == "first.mp4" else self.sha_b
        payload = {
            "schemaVersion": "kumiki.local-character-study-batch.v1",
            "sourceSha256": expected_sha, "modelTag": kwargs["model"],
            "detectorBackend": kwargs["detector"],
            "windowCount": kwargs["window_count"],
            "status": "completed-multiple-independent-unverified-studies",
            "windows": [],
        }
        path = folder/"batch-manifest.json"
        path.write_text(json.dumps(payload))
        return path

    def run_fake(self, **changes):
        with (
            patch("kumiki_reference_lab.pipeline.whatships_local_worker.inspect_source",
                  side_effect=self.fake_inspect),
            patch("kumiki_reference_lab.pipeline.whatships_local_worker.run_character_study_batch",
                  side_effect=self.fake_study),
        ):
            return run_whatships_local_analysis(
                self.snapshot, self.bindings, self.out,
                **{"model":"local-vision:8b", **changes})

    def test_first_batch_checkpoint_and_redacted_per_category_coverage(self):
        report_path = self.run_fake()
        report = json.loads(report_path.read_text())
        self.assertEqual(report["catalogVideoCount"], 2)
        self.assertEqual(report["operatorBoundMediaCount"], 2)
        self.assertEqual(report["completedUnreviewedVideoCount"], 1)
        self.assertEqual(report["completedThisInvocation"], 1)
        self.assertEqual(report["boundNotYetCompleted"], 1)
        self.assertEqual(report["humanReviewedVideos"], 0)
        self.assertNotIn(str(self.root), report_path.read_text())
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0], "second.mp4")  # category-balanced design first
        self.assertEqual(self.calls[0][1]["window_count"], 2)
        self.assertEqual(self.calls[0][1]["window_seconds"], 10)
        self.assertEqual(self.calls[0][1]["stride_seconds"], 22)
        self.assertEqual(self.calls[0][1]["rights_status"], "user-declared-authorized")
        data = json.loads((self.out/"analysis-index.json").read_text())
        self.assertEqual(len(data["entries"]), 1)
        self.assertEqual(data["entries"][0]["status"], "completed-unreviewed")
        self.assertTrue(Path(data["entries"][0]["studyManifestPath"]).is_file())
        self.assertEqual(data["entries"][0]["windowCount"], 2)

    def test_avoids_duplicate_success_on_resume_and_handles_other_item(self):
        first = self.run_fake(max_videos=1)
        resume_file = self.out/"analysis-index.json"
        self.assertTrue(resume_file.exists())
        self.calls.clear()
        self.out = self.root/"second-batch"
        report = self.run_fake(max_videos=2, previous_index=resume_file)
        data = json.loads(report.read_text())
        self.assertEqual(data["completedUnreviewedVideoCount"], 2)
        self.assertEqual(data["completedThisInvocation"], 1)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0], "first.mp4")
        self.assertEqual(self.calls[0][1]["window_count"], 2)
        self.assertEqual(self.calls[0][1]["stride_seconds"], 75)
        self.assertEqual(len(json.loads((self.out/"analysis-index.json").read_text())["entries"]), 2)

    def test_later_failure_does_not_erase_prior_video_and_can_retry(self):
        self.fail_source = "first.mp4"
        first = self.run_fake(max_videos=2)
        report = json.loads(first.read_text())
        self.assertEqual(report["completedUnreviewedVideoCount"], 1)
        self.assertEqual(report["failedVideoCount"], 1)
        self.assertEqual(report["completedThisInvocation"], 1)
        private = json.loads((self.out/"analysis-index.json").read_text())
        bad = next(x for x in private["entries"] if x["status"] == "failed-preserved-for-retry")
        self.assertIn("model unavailable", bad["error"])
        self.assertIsNone(bad["studyManifestPath"])
        self.assertTrue((self.out/"runs"/"film-two"/"batch-manifest.json").exists())
        self.assertFalse((self.out/"runs"/"film-one").exists())
        self.fail_source = None
        prior = self.out/"analysis-index.json"
        self.out = self.root/"retry"
        second = self.run_fake(previous_index=prior, max_videos=1)
        report = json.loads(second.read_text())
        self.assertEqual(report["completedUnreviewedVideoCount"], 2)
        self.assertEqual(report["failedVideoCount"], 0)
        self.assertEqual(report["completedThisInvocation"], 1)

    def test_changed_local_video_is_never_analyzed(self):
        self.source_b.write_bytes(b"some new substituted video bytes")
        report = json.loads(self.run_fake(max_videos=1).read_text())
        self.assertEqual(report["completedUnreviewedVideoCount"], 0)
        self.assertEqual(report["failedVideoCount"], 1)
        self.assertEqual(self.calls, [])
        private = json.loads((self.out/"analysis-index.json").read_text())
        self.assertIn("byte fingerprint changed", private["entries"][0]["error"])

    def test_source_stream_mismatch_abstains_before_model_inference(self):
        self.mismatch_sha = True
        report = json.loads(self.run_fake(max_videos=1).read_text())
        self.assertEqual(report["completedUnreviewedVideoCount"], 0)
        self.assertEqual(self.calls, [])

    def test_tampered_previous_success_is_not_silently_skipped(self):
        self.run_fake(max_videos=1)
        prior = self.out/"analysis-index.json"
        index = json.loads(prior.read_text())
        Path(index["entries"][0]["studyManifestPath"]).write_text("{}")
        self.out = self.root/"later-run"
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            self.run_fake(previous_index=prior)
        self.assertFalse(self.out.exists())

    def test_missing_authorized_bindings_creates_honest_zero_coverage(self):
        self.ledger["bindings"] = []
        self.write_ledger()
        report = json.loads(self.run_fake().read_text())
        self.assertEqual(report["operatorBoundMediaCount"], 0)
        self.assertEqual(report["completedUnreviewedVideoCount"], 0)
        self.assertEqual(report["unboundCatalogVideos"], 2)
        self.assertEqual(self.calls, [])

    def test_auto_window_plan_is_bounded_and_says_requested_not_measured(self):
        self.assertEqual(_plan_windows("85.0", window_seconds=10, window_count=2),
                         (10,2,75,round(20/85,6)))
        self.assertEqual(_plan_windows("5.0", window_seconds=10, window_count=6),
                         (5,1,5,1.0))
        span, count, stride, fraction = _plan_windows(
            "7200", window_seconds=15, window_count=6)
        self.assertEqual((span,count,stride), (15,6,717))
        self.assertAlmostEqual(fraction, 90/7200, places=5)
        for duration in ("N/A", "NaN", "-5", "0", None):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                _plan_windows(duration, window_seconds=10, window_count=2)

    def test_rejects_bad_budgets_before_any_output_or_inference(self):
        for args in (
            {"max_videos":0}, {"max_videos":5}, {"start_offset":True},
            {"model":"../../bad"}, {"window_count":7}, {"max_calls":50},
            {"port":False}, {"width":1000}, {"review":None},
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                run_whatships_local_analysis(
                    self.snapshot, self.bindings, self.out,
                    **{"model":"local-vision:8b",**args})
        self.assertFalse(self.out.exists())
        self.assertEqual(self.calls, [])

    def test_cli_parse_and_run_bound_file(self):
        args = build_parser().parse_args([
            "whatships-analyze", str(self.bindings), "--snapshot", str(self.snapshot),
            "--model", "local:8b", "--out", str(self.out),
            "--skip-interactions", "--max-videos", "2",
        ])
        self.assertEqual(args.command, "whatships-analyze")
        self.assertTrue(args.skip_interactions)
        self.assertEqual(args.max_videos, 2)
        with (
            patch("kumiki_reference_lab.pipeline.whatships_local_worker.inspect_source",
                  side_effect=self.fake_inspect),
            patch("kumiki_reference_lab.pipeline.whatships_local_worker.run_character_study_batch",
                  side_effect=self.fake_study),
        ):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main([
                    "whatships-analyze", str(self.bindings),
                    "--snapshot", str(self.snapshot), "--model", "local:8b",
                    "--out", str(self.out), "--max-videos", "1",
                ])
        self.assertEqual(code,0)
        self.assertTrue(Path(output.getvalue().strip()).is_file())


if __name__ == "__main__":
    unittest.main()
