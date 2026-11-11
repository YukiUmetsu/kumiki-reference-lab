"""Real FFprobe source verification for private What Ships analysis scheduling.

Real media is generated locally; the VLM-dependent video study is mocked.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.pipeline.whatships_local_worker import run_whatships_local_analysis
from tests.test_video_sources import whatships_fixture


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Real FFmpeg / FFprobe not installed")
class RealWhatshipsLocalWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/"original-test-film.mp4"
        result = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-nostdin", "-y",
            "-f", "lavfi", "-i",
            "color=c=blue:s=160x90:r=5:d=3,drawbox=x=35:y=10:w=40:h=65:color=yellow:t=fill",
            "-c:v", "mpeg4", "-q:v", "5", "-pix_fmt", "yuv420p", str(self.source),
        ], capture_output=True, timeout=20, check=False)
        if result.returncode:
            self.fail("Could not generate original FFmpeg smoke clip")
        self.snapshot = self.root/"catalog.json"
        self.snapshot.write_text(json.dumps(whatships_fixture()))
        info = inspect_source(self.source, rights_status="user-declared-authorized")
        self.sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.assertEqual(info["source"]["sha256"], self.sha)
        self.bindings = self.root/"bindings.json"
        self.bindings.write_text(json.dumps({
            "schemaVersion":"kumiki.whatships-local-media-bindings.v1",
            "createdOn":"2026-11-10",
            "catalogIndexUrl":"https://whatships.com/search-index.json",
            "disclaimer":"self-declared-source-identity-and-authorization-only",
            "bindings":[{
                "sourceId":"whatships:film-one",
                "watchUrl":"https://whatships.com/videos/film-one/",
                "localPath":str(self.source.resolve()),
                "mediaSha256":self.sha,
                "mediaSizeBytes":self.source.stat().st_size,
                "sourceStreamIndex":info["video"]["streamIndex"],
                "sourceTimebase":info["video"]["sourceTimebase"],
                "rightsBasis":"own-original-work",
                "rightsNote":"This synthetic video was created by this test from original color shapes.",
                "identityNote":"Test-only synthetic fixture representing a known What Ships catalog ID.",
                "rightsStatus":"user-declared-authorized",
                "verificationStatus":"operator-attestation-not-independently-verified",
                "boundOn":"2026-11-10",
            }],
        }))
        self.out = self.root/"private-output"

    def test_real_local_video_probe_and_bounded_3_second_short_movie(self):
        recorded = []
        def fake_study(source, folder, **kwargs):
            self.assertEqual(source, self.source)
            self.assertEqual(kwargs["rights_status"], "user-declared-authorized")
            recorded.append(kwargs)
            folder.mkdir()
            manifest = folder/"batch-manifest.json"
            manifest.write_text(json.dumps({
                "schemaVersion":"kumiki.local-character-study-batch.v1",
                "sourceSha256":self.sha,
                "modelTag":kwargs["model"],
                "detectorBackend":kwargs["detector"],
                "windowCount":kwargs["window_count"],
                "status":"completed-multiple-independent-unverified-studies",
            }))
            return manifest
        with patch(
            "kumiki_reference_lab.pipeline.whatships_local_worker.run_character_study_batch",
            side_effect=fake_study,
        ):
            report_path = run_whatships_local_analysis(
                self.snapshot, self.bindings, self.out,
                model="simulated-local-vision:1b",
                window_seconds=10, window_count=3,
                max_samples=5, max_calls=4, max_pairs=2,
            )
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["window_seconds"], 3)
        self.assertEqual(recorded[0]["window_count"], 1)
        self.assertEqual(recorded[0]["stride_seconds"], 3)
        result = json.loads(report_path.read_text())
        self.assertEqual(result["completedUnreviewedVideoCount"], 1)
        self.assertEqual(result["humanReviewedVideos"], 0)
        self.assertNotIn(str(self.root), report_path.read_text())


if __name__ == "__main__":
    unittest.main()
