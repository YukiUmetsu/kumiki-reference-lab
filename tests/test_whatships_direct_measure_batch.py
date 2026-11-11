"""Incremental per-source Git checkpoints for authorized multi-video reference study."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.catalog.whatships_analysis_store import (
    export_repository_analysis, validate_repository_analysis,
)
from kumiki_reference_lab.catalog.whatships_direct_measure_batch import (
    measure_whatships_batch,
)
from kumiki_reference_lab.cli.app import main
from tests.test_video_sources import whatships_fixture


class WhatshipsDirectMeasureBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name)
        self.catalog=self.work/"catalog.json"
        self.catalog.write_text(json.dumps(whatships_fixture()))
        self.root=self.work/"analysis"
        export_repository_analysis(self.catalog,self.root)
        self.ledger=self.work/"private-bindings.json"
        self.media={}
        bindings=[]
        for slug in ("film-one","film-two"):
            path=self.work/(slug+".mp4")
            path.write_bytes(("source-frame-video-"+slug).encode("utf-8"))
            sha=hashlib.sha256(path.read_bytes()).hexdigest()
            self.media[slug]=(path,sha)
            bindings.append({
                "sourceId":"whatships:"+slug,
                "watchUrl":f"https://whatships.com/videos/{slug}/",
                "localPath":str(path.resolve()),
                "mediaSha256":sha,
                "mediaSizeBytes":path.stat().st_size,
                "sourceStreamIndex":0,
                "sourceTimebase":{"numerator":1,"denominator":1000},
                "rightsBasis":"own-original-work",
                "rightsNote":"The operator generated the synthetic local video for testing.",
                "identityNote":"The source and catalog ID match this controlled fixture.",
                "rightsStatus":"user-declared-authorized",
                "verificationStatus":"operator-attestation-not-independently-verified",
                "boundOn":"2026-11-11",
            })
        self.doc={
            "schemaVersion":"kumiki.whatships-local-media-bindings.v1",
            "createdOn":"2026-11-11",
            "catalogIndexUrl":"https://whatships.com/search-index.json",
            "disclaimer":"self-declared-source-identity-and-authorization-only",
            "bindings":bindings,
        }
        self.save_ledger()
        self.calls=[]
        self.fail_slug=None

    def save_ledger(self):
        self.ledger.write_text(json.dumps(self.doc))

    def inspect(self, source, *, ffprobe, rights_status):
        self.assertEqual(rights_status,"user-declared-authorized")
        path,sha=self.media[source.stem]
        return {
            "source":{"sha256":sha},
            "video":{"streamIndex":0,
                     "sourceTimebase":{"numerator":1,"denominator":1000},
                     "durationSecondsReported":"4.0"},
        }

    def probe(self, source, *, start_seconds, seconds,
              max_samples, width, height, cut_threshold,
              rights_status, ffmpeg, ffprobe):
        slug=source.stem
        self.calls.append(slug)
        if slug==self.fail_slug:
            raise ValueError("/Users/private/movie.mp4 could not be decoded")
        positions=[0,500,1000,1500,2000]
        return {
            "schemaVersion":"kumiki.source-pts-visual-probe.v1",
            "sourceSha256":self.media[slug][1],
            "sourceStreamIndex":0,
            "sourceTimebase":{"numerator":1,"denominator":1000},
            "scan":{
                "startSeconds":0,"requestedSeconds":3,
                "sourceWindowEndSeconds":3,
                "sourceTimebaseVerified":True,
                "sampledSourcePtsCount":5,"sourcePtsFramesSeenInInventory":15,
                "decoder":"source-prefix-ordinal-pts-v1",
                "cutThreshold":cut_threshold,
                "frameWidth":width,"frameHeight":height,
            },
            "cutCandidatePts":[],
            "sampledFrames":[{
                "sourcePts":pts,"sourceSeconds":{"numerator":pts,"denominator":1000},
                "appearance":{
                    "meanRgb":[.2,.2,.2],"meanDisplayLumaProxy":.2,
                    "displayLumaStdDev":.1,"meanSaturationProxy":.3,
                    "shadowPixelFraction":.1,"brightPixelFraction":.1,
                },
            } for pts in positions],
            "sampledFramePairs":[{
                "startPts":positions[i-1],"endPts":positions[i],
                "sourceDeltaSeconds":{"numerator":1,"denominator":2},
                "status":"rgb-image-difference-proxy",
                "meanAbsoluteDisplayRgbDelta":.04,
                "meanAbsoluteDisplayRgbDeltaPerSecond":.08,
            } for i in range(1,5)],
            "sampledWindowSummary":{
                "cutCandidateCountBetweenFirstAndLastSample":0,
                "cutCandidateRatePerRequestedMinute":0.,
                "meanSampledDisplayLumaProxy":.2,
                "meanSampledSaturationProxy":.3,
                "meanWithinShotDisplayRgbDelta":.04,
                "withinShotComparedPairs":4,"cutSeparatedPairs":0,
            },
            "evidenceStatus":"original-source-pts-sampled-numeric-proxies-not-human-reviewed",
        }

    def run_batch(self, **kwargs):
        with (
            patch("kumiki_reference_lab.catalog.whatships_direct_measure.inspect_source",
                  side_effect=self.inspect),
            patch("kumiki_reference_lab.catalog.whatships_direct_measure.analyze_source_visual_window",
                  side_effect=self.probe),
        ):
            return measure_whatships_batch(
                self.catalog,self.ledger,self.root,
                **{"max_videos":2,"window_seconds":3,"window_count":1,
                   "max_samples":5,**kwargs})

    def test_category_balanced_batch_persists_both_movies_in_git(self):
        result=self.run_batch()
        self.assertEqual(self.calls,["film-two","film-one"])
        self.assertEqual(result["succeededThisRun"],2)
        self.assertEqual(result["failedThisRun"],0)
        self.assertEqual(result["trackedMeasuredVideoCount"],2)
        self.assertEqual(result["fullVideoHumanReviewCount"],0)
        self.assertNotIn(str(self.work),json.dumps(result))
        state=validate_repository_analysis(self.root,self.catalog)
        self.assertEqual(state["numericSampledVideos"],2)
        self.assertEqual(set(x["sourceId"] for x in result["succeeded"]),
                         {"whatships:film-one","whatships:film-two"})

    def test_second_invocation_skips_already_measured_source_files(self):
        self.run_batch(max_videos=1)
        self.calls.clear()
        result=self.run_batch(max_videos=2)
        self.assertEqual(result["previouslyMeasuredBoundSources"],1)
        self.assertEqual(result["succeededThisRun"],1)
        self.assertEqual(self.calls,["film-one"])
        again=self.run_batch(max_videos=2)
        self.assertEqual(again["succeededThisRun"],0)
        self.assertEqual(again["attemptedThisRun"],0)
        self.assertEqual(again["previouslyMeasuredBoundSources"],2)

    def test_one_unavailable_movie_does_not_erase_other_completed_movies(self):
        self.fail_slug="film-two"
        result=self.run_batch()
        self.assertEqual(result["failedThisRun"],1)
        self.assertEqual(result["succeededThisRun"],1)
        self.assertEqual(result["trackedMeasuredVideoCount"],1)
        self.assertEqual(result["failed"][0]["sourceId"],"whatships:film-two")
        self.assertNotIn("/Users/private",json.dumps(result))
        self.assertTrue((self.root/"film-one.json").is_file())
        self.assertFalse((self.root/"film-two.json").exists())
        self.fail_slug=None
        self.calls.clear()
        recovery=self.run_batch(max_videos=2)
        self.assertEqual(recovery["succeededThisRun"],1)
        self.assertEqual(self.calls,["film-two"])
        self.assertEqual(recovery["trackedMeasuredVideoCount"],2)

    def test_replaced_authorized_media_file_is_not_falsely_counted(self):
        self.media["film-two"][0].write_bytes(b"changed video bytes")
        result=self.run_batch(max_videos=2)
        self.assertEqual(result["failedThisRun"],1)
        self.assertEqual(result["succeededThisRun"],1)
        self.assertEqual(self.calls,["film-one"])
        self.assertEqual(validate_repository_analysis(self.root,self.catalog)
                         ["numericSampledVideos"],1)

    def test_explicit_offset_skips_repeat_failure_without_losing_source(self):
        self.fail_slug="film-two"
        result=self.run_batch(max_videos=1,start_offset=1)
        self.assertEqual(result["startOffset"],1)
        self.assertEqual(self.calls,["film-one"])
        self.assertEqual(result["succeededThisRun"],1)
        self.assertEqual(result["unmeasuredEligibleBeforeRun"],2)
        self.assertEqual(result["trackedMeasuredVideoCount"],1)

    def test_category_selection_only_processes_requested_video_type(self):
        result=self.run_batch(max_videos=2,category="motion")
        self.assertEqual(self.calls,["film-one"])
        self.assertEqual(result["succeededThisRun"],1)
        self.assertEqual(result["categoryFilter"],"motion")
        self.assertFalse((self.root/"film-two.json").exists())

    def test_no_authorized_bindings_reports_zero_eligible(self):
        self.doc["bindings"]=[]
        self.save_ledger()
        result=self.run_batch()
        self.assertEqual(result["operatorBoundVideoCount"],0)
        self.assertEqual(result["attemptedThisRun"],0)
        self.assertEqual(result["trackedMeasuredVideoCount"],0)
        self.assertEqual(self.calls,[])

    def test_rejects_invalid_batch_bounds_and_category_before_writes(self):
        for change in ({"max_videos":0},{"max_videos":5},
                       {"max_videos":True},{"start_offset":True},
                       {"start_offset":-1},{"category":"bad-category"}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.run_batch(**change)
        self.assertEqual(self.calls,[])

    def test_cli_runs_bounded_category_sample_without_private_paths_in_output(self):
        capture=io.StringIO()
        with (
            patch("kumiki_reference_lab.catalog.whatships_direct_measure.inspect_source",
                  side_effect=self.inspect),
            patch("kumiki_reference_lab.catalog.whatships_direct_measure.analyze_source_visual_window",
                  side_effect=self.probe),
            contextlib.redirect_stdout(capture),
        ):
            rc=main([
                "whatships-measure-batch",str(self.ledger),
                "--snapshot",str(self.catalog),
                "--repository-root",str(self.root),
                "--max-videos","1","--window-seconds","3",
                "--window-count","1","--max-samples","5",
            ])
        self.assertEqual(rc,0)
        report=json.loads(capture.getvalue())
        self.assertEqual(report["succeededThisRun"],1)
        self.assertNotIn(str(self.work),capture.getvalue())
        self.assertTrue((self.root/"film-two.json").is_file())


if __name__=="__main__":
    unittest.main()
