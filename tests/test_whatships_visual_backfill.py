"""Source-hashed What Ships numeric visual backfill, checkpoints, QA semantics."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.analyzers.appearance.source_visual_probe import SCHEMA_VERSION as PROBE_VERSION
from kumiki_reference_lab.cli.app import build_parser, main
from kumiki_reference_lab.pipeline.whatships_visual_backfill import backfill_whatships_visual_probes
from kumiki_reference_lab.pipeline.whatships_local_worker import _new_index, _configuration
from tests.test_video_sources import whatships_fixture


class WhatshipsVisualBackfillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = self.root/"snapshot.json"
        self.snapshot.write_text(json.dumps(whatships_fixture()))
        self.bindings = self.root/"private-bindings.json"
        self.original_index = self.root/"analysis-index.json"
        self.out = self.root/"visual-out"
        self.sources = {}
        self.probe_calls = []
        self.fail_window_start = None
        media = []
        completed = []
        for slug in ("film-one", "film-two"):
            video = self.root/(slug+".mp4")
            video.write_bytes(("synthetic authorized "+slug).encode())
            sha = hashlib.sha256(video.read_bytes()).hexdigest()
            self.sources[slug] = (video,sha)
            media.append({
                "sourceId":"whatships:"+slug,
                "watchUrl":f"https://whatships.com/videos/{slug}/",
                "localPath":str(video.resolve()), "mediaSha256":sha,
                "mediaSizeBytes":video.stat().st_size,
                "sourceStreamIndex":0,
                "sourceTimebase":{"numerator":1,"denominator":1000},
                "rightsBasis":"written-permission",
                "rightsNote":"The creator granted permission to inspect this fixture locally.",
                "identityNote":"The source post and clip frames were matched by the operator.",
                "rightsStatus":"user-declared-authorized",
                "verificationStatus":"operator-attestation-not-independently-verified",
                "boundOn":"2026-11-10",
            })
            study_folder = self.root/"prior-character-studies"/slug
            study_folder.mkdir(parents=True)
            windows = []
            for i,(start,end) in enumerate(((0,3),(5,8))):
                child_relative = f"windows/window-{i:03d}/study-manifest.json"
                child = study_folder/child_relative
                child.parent.mkdir(parents=True)
                child.write_text(json.dumps({
                    "schemaVersion":"kumiki.local-character-study.v1",
                    "sourceSha256":sha,
                    "scanStartSeconds":start,
                    "maxSeconds":end-start,
                    "status":"completed-unverified-model-proposals",
                }))
                windows.append({
                    "index":i, "startSeconds":start, "endSeconds":end,
                    "manifest":child_relative, "status":"completed-unverified-model-proposals",
                })
            manifest = study_folder/"batch-manifest.json"
            manifest.write_text(json.dumps({
                "schemaVersion":"kumiki.local-character-study-batch.v1",
                "sourceSha256":sha, "windowCount":2,
                "modelTag":"vision-local:8b", "detectorBackend":"ollama",
                "status":"completed-multiple-independent-unverified-studies",
                "windows":windows,
            }))
            completed.append({
                "sourceId":"whatships:"+slug,"mediaSha256":sha,
                "status":"completed-unreviewed",
                "studyManifestPath":str(manifest.resolve()),
                "studyManifestSha256":hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "windowCount":2,
                "requestedWindowSpanFraction":.2,
                "error":None,
            })
        self.bindings.write_text(json.dumps({
            "schemaVersion":"kumiki.whatships-local-media-bindings.v1",
            "createdOn":"2026-11-10",
            "catalogIndexUrl":"https://whatships.com/search-index.json",
            "disclaimer":"self-declared-source-identity-and-authorization-only",
            "bindings":media,
        }))
        config = _configuration(
            model="vision-local:8b", detector="ollama",
            window_seconds=3, window_count=2, max_samples=5, max_calls=4,
            max_pairs=2, width=160,height=90,port=11434,
            timeout_seconds=30,review=True,interactions=True)
        index = _new_index(config,whatships_fixture())
        index["entries"] = completed
        self.original_index.write_text(json.dumps(index))

    def fake_inspect(self, source, *, ffprobe, rights_status):
        slug = source.stem
        self.assertEqual(rights_status,"user-declared-authorized")
        self.assertIn(slug,self.sources)
        return {
            "source":{"sha256":self.sources[slug][1]},
            "video":{"streamIndex":0,"sourceTimebase":{"numerator":1,"denominator":1000}},
        }

    def fake_probe(self, source, *, start_seconds, seconds, max_samples,
                   width, height, cut_threshold, rights_status, ffmpeg, ffprobe):
        self.probe_calls.append((source.stem,start_seconds,seconds))
        if self.fail_window_start == start_seconds:
            raise ValueError("synthetic visual decoder error")
        sha = self.sources[source.stem][1]
        return {
            "schemaVersion":PROBE_VERSION,
            "sourceSha256":sha,
            "sourceStreamIndex":0,
            "sourceTimebase":{"numerator":1,"denominator":1000},
            "scan":{"startSeconds":start_seconds,"sourceWindowEndSeconds":start_seconds+seconds,
                    "sampledSourcePtsCount":5,"decoder":"source-prefix-ordinal-pts-v1"},
            "sampledFrames":[],
            "evidenceStatus":"original-source-pts-sampled-numeric-proxies-not-human-reviewed",
        }

    def run_mock(self, **changes):
        with (
            patch("kumiki_reference_lab.pipeline.whatships_visual_backfill.inspect_source",
                  side_effect=self.fake_inspect),
            patch("kumiki_reference_lab.pipeline.whatships_visual_backfill.analyze_source_visual_window",
                  side_effect=self.fake_probe),
        ):
            return backfill_whatships_visual_probes(
                self.snapshot,self.bindings,self.original_index,self.out,**changes)

    def test_first_video_probed_without_rerunning_character_model(self):
        path = self.run_mock()
        report = json.loads(path.read_text())
        self.assertEqual(report["catalogVideoCount"],2)
        self.assertEqual(report["operatorBoundMediaCount"],2)
        self.assertEqual(report["completedNumericProbeVideos"],1)
        self.assertEqual(report["measuredOriginalSourceWindows"],2)
        self.assertEqual(report["humanReviewedNumericProbeVideos"],0)
        self.assertEqual(self.probe_calls,[
            ("film-two",0,3),("film-two",5,3),
        ])
        self.assertNotIn(str(self.root),path.read_text())
        private = json.loads((self.out/"visual-index.json").read_text())
        self.assertEqual(private["entries"][0]["status"],"measured-numeric-proxies-unreviewed")
        for artifact in private["entries"][0]["probeArtifacts"]:
            self.assertTrue(Path(artifact["path"]).is_file())
            self.assertEqual(artifact["sampledFrameCount"],5)

    def test_resumes_second_video_only_with_intact_prior_source_probes(self):
        self.run_mock()
        prior = self.out/"visual-index.json"
        self.probe_calls.clear()
        self.out = self.root/"continued"
        report = json.loads(self.run_mock(previous_index=prior,max_videos=2).read_text())
        self.assertEqual(report["completedNumericProbeVideos"],2)
        self.assertEqual(report["completedThisInvocation"],1)
        self.assertEqual(self.probe_calls,[
            ("film-one",0,3),("film-one",5,3),
        ])

    def test_failure_in_later_window_discards_incomplete_video_but_can_retry(self):
        self.fail_window_start = 5
        report = json.loads(self.run_mock(max_videos=1).read_text())
        self.assertEqual(report["completedNumericProbeVideos"],0)
        index = json.loads((self.out/"visual-index.json").read_text())
        self.assertEqual(index["entries"][0]["status"],"failed-preserved-for-retry")
        self.assertEqual(index["entries"][0]["probeArtifacts"],[])
        self.assertFalse((self.out/"runs"/"film-two").exists())
        self.fail_window_start = None
        prior = self.out/"visual-index.json"
        self.out = self.root/"retry"
        self.assertEqual(json.loads(self.run_mock(previous_index=prior).read_text())
                         ["completedNumericProbeVideos"],1)

    def test_fingerprint_drift_prevents_probes(self):
        self.sources["film-two"][0].write_bytes(b"altered while still having same filename")
        result = json.loads(self.run_mock().read_text())
        self.assertEqual(result["completedNumericProbeVideos"],0)
        self.assertEqual(self.probe_calls,[])
        private = json.loads((self.out/"visual-index.json").read_text())
        self.assertIn("fingerprint differs",private["entries"][0]["error"])

    def test_tampered_previous_visual_artifact_cannot_be_reused(self):
        self.run_mock()
        prior = self.out/"visual-index.json"
        data = json.loads(prior.read_text())
        Path(data["entries"][0]["probeArtifacts"][0]["path"]).write_text('{"bogus":true}')
        self.out = self.root/"retry"
        with self.assertRaisesRegex(ValueError,"artifact changed"):
            self.run_mock(previous_index=prior)
        self.assertFalse(self.out.exists())

    def test_corrupt_original_child_window_does_not_inflate_coverage(self):
        child = self.root/"prior-character-studies"/"film-two"/"windows"/"window-001"/"study-manifest.json"
        child.write_text("{}")
        result = json.loads(self.run_mock().read_text())
        self.assertEqual(result["completedNumericProbeVideos"],0)
        self.assertEqual(self.probe_calls,[])

    def test_invalid_budget_or_no_finished_character_studies(self):
        for changes in ({"max_videos":0},{"max_samples":25},{"height":20},
                        {"cut_threshold":float("nan")},{"start_offset":True}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.run_mock(**changes)
        self.assertFalse(self.out.exists())
        old = json.loads(self.original_index.read_text())
        old["entries"] = []
        self.original_index.write_text(json.dumps(old))
        result = json.loads(self.run_mock().read_text())
        self.assertEqual(result["completedNumericProbeVideos"],0)
        self.assertEqual(result["catalogVideoCount"],2)
        self.assertEqual(self.probe_calls,[])

    def test_cli_parses_source_provenance_and_runs_private_backfill(self):
        args = build_parser().parse_args([
            "whatships-visual-backfill",str(self.bindings),str(self.original_index),
            "--snapshot",str(self.snapshot),"--out",str(self.out),
            "--max-videos","1","--max-samples","6",
        ])
        self.assertEqual(args.command,"whatships-visual-backfill")
        self.assertEqual(args.max_samples,6)
        with (
            patch("kumiki_reference_lab.pipeline.whatships_visual_backfill.inspect_source",
                  side_effect=self.fake_inspect),
            patch("kumiki_reference_lab.pipeline.whatships_visual_backfill.analyze_source_visual_window",
                  side_effect=self.fake_probe),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main([
                    "whatships-visual-backfill",
                    str(self.bindings),str(self.original_index),
                    "--snapshot",str(self.snapshot),"--out",str(self.out),
                ])
        self.assertEqual(code,0)
        self.assertTrue(Path(buf.getvalue().strip()).exists())


if __name__ == "__main__":
    unittest.main()
