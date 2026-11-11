"""Frame-level numeric PTS history survives private-to-Git export, sans private paths."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.whatships_analysis_store import (
    export_repository_analysis,validate_repository_analysis,
    sync_repository_analysis,
)
from kumiki_reference_lab.pipeline.whatships_local_worker import (
    _configuration,_new_index,
)
from kumiki_reference_lab.pipeline.whatships_visual_backfill import _config
from tests.test_video_sources import whatships_fixture


class WhatshipsNumericFrameExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.catalog=self.root/"snapshot.json"
        self.catalog.write_text(json.dumps(whatships_fixture()))
        self.bindings=self.root/"private-bindings.json"
        self.char_index=self.root/"private-analysis-index.json"
        self.visual_index=self.root/"private-visual-index.json"
        self.out=self.root/"safe-git-export"
        self.sha="a"*64
        private_video=str(self.root/"my-private-source.mp4")
        self.bindings.write_text(json.dumps({
            "schemaVersion":"kumiki.whatships-local-media-bindings.v1",
            "createdOn":"2026-11-10",
            "catalogIndexUrl":"https://whatships.com/search-index.json",
            "disclaimer":"self-declared-source-identity-and-authorization-only",
            "bindings":[{
                "sourceId":"whatships:film-one",
                "watchUrl":"https://whatships.com/videos/film-one/",
                "localPath":private_video,
                "mediaSha256":self.sha,
                "mediaSizeBytes":16000,
                "sourceStreamIndex":0,
                "sourceTimebase":{"numerator":1,"denominator":1000},
                "rightsBasis":"written-permission",
                "rightsNote":"The creator provided private analysis permission for a locally supplied clip.",
                "identityNote":"Original source creator and title were matched to this exact catalog entry.",
                "rightsStatus":"user-declared-authorized",
                "verificationStatus":"operator-attestation-not-independently-verified",
                "boundOn":"2026-11-10",
            }],
        }))
        report=self.root/"private-character-batch.json"
        report.write_text(json.dumps({
            "schemaVersion":"kumiki.local-character-study-batch.v1",
            "sourceSha256":self.sha,
            "status":"completed-multiple-independent-unverified-studies",
            "windowCount":1,"modelTag":"local-vision:8b",
            "detectorBackend":"ollama",
        }))
        cfg=_configuration(
            model="local-vision:8b",detector="ollama",window_seconds=3,
            window_count=1,max_samples=5,max_calls=4,max_pairs=2,
            width=160,height=90,port=11434,timeout_seconds=60,
            review=True,interactions=True)
        character=_new_index(cfg,whatships_fixture())
        character["entries"]=[{
            "sourceId":"whatships:film-one","mediaSha256":self.sha,
            "status":"completed-unreviewed",
            "studyManifestPath":str(report.resolve()),
            "studyManifestSha256":hashlib.sha256(report.read_bytes()).hexdigest(),
            "windowCount":1,"requestedWindowSpanFraction":.25,
            "error":None,
        }]
        self.char_index.write_text(json.dumps(character))
        self.numeric_file=self.root/"private-visual-window-000.json"
        self.write_numeric()
        visual={
            "schemaVersion":"kumiki.whatships-source-visual-backfill.v1",
            "catalogIndexUrl":"https://whatships.com/search-index.json",
            "configuration":_config(max_samples=5,width=160,height=90,cut_threshold=.25),
            "entries":[{
                "sourceId":"whatships:film-one",
                "mediaSha256":self.sha,
                "studyManifestSha256":character["entries"][0]["studyManifestSha256"],
                "status":"measured-numeric-proxies-unreviewed",
                "windowCount":1,
                "probeArtifacts":[{
                    "path":str(self.numeric_file.resolve()),
                    "sha256":hashlib.sha256(self.numeric_file.read_bytes()).hexdigest(),
                    "startSeconds":0,"endSeconds":3,"sampledFrameCount":2,
                }],
                "error":None,
            }],
        }
        self.visual_index.write_text(json.dumps(visual))

    def write_numeric(self,*,extra_field=False):
        def frame(pts,brightness):
            row={
                "sourcePts":pts,
                "sourceSeconds":{"numerator":pts//1000,"denominator":1},
                "appearance":{
                    "meanRgb":[brightness,.2,.4],
                    "meanDisplayLumaProxy":brightness,
                    "displayLumaStdDev":.1,
                    "meanSaturationProxy":.3,
                    "shadowPixelFraction":.05,
                    "brightPixelFraction":.1,
                },
            }
            if extra_field:
                row["localPath"]="/Users/secret/private.mp4"
            return row
        self.numeric_file.write_text(json.dumps({
            "schemaVersion":"kumiki.source-pts-visual-probe.v1",
            "sourceSha256":self.sha,"sourceStreamIndex":0,
            "sourceTimebase":{"numerator":1,"denominator":1000},
            "scan":{
                "startSeconds":0,"sourceWindowEndSeconds":3,
                "sampledSourcePtsCount":2,"decoder":"source-prefix-ordinal-pts-v1",
                "cutThreshold":.25,"frameWidth":160,"frameHeight":90,
            },
            "sampledFrames":[frame(0,.2),frame(1000,.25)],
            "sampledFramePairs":[{
                "startPts":0,"endPts":1000,
                "sourceDeltaSeconds":{"numerator":1,"denominator":1},
                "status":"rgb-image-difference-proxy",
                "meanAbsoluteDisplayRgbDelta":.05,
                "meanAbsoluteDisplayRgbDeltaPerSecond":.05,
            }],
            "cutCandidatePts":[],
            "sampledWindowSummary":{
                "cutCandidateCountBetweenFirstAndLastSample":0,
                "cutCandidateRatePerRequestedMinute":0.0,
                "meanSampledDisplayLumaProxy":.225,
                "meanSampledSaturationProxy":.3,
                "meanWithinShotDisplayRgbDelta":.05,
                "withinShotComparedPairs":1,
                "cutSeparatedPairs":0,
            },
            "evidenceStatus":"original-source-pts-sampled-numeric-proxies-not-human-reviewed",
        }))

    def export(self):
        return export_repository_analysis(
            self.catalog,self.out,bindings_path=self.bindings,
            analysis_path=self.char_index,visual_path=self.visual_index)

    def test_full_original_frame_timeline_is_committed_not_only_aggregate(self):
        result=self.export()
        self.assertTrue(result.is_file())
        record=json.loads((self.out/"film-one.json").read_text())
        self.assertEqual(record["sourceMediaSha256"],self.sha)
        self.assertTrue(record["coverage"]["hasSampledNumericSourceFrames"])
        self.assertTrue(record["coverage"]["hasUnreviewedCharacterJob"])
        self.assertFalse(record["coverage"]["fullFilmReviewed"])
        self.assertEqual(record["evidence"]["numericVisual"]["windows"][0]["sampledFrames"][0]
                         ["sourcePts"],0)
        self.assertEqual(record["evidence"]["numericVisual"]["windows"][0]["sampledFrames"][1]
                         ["sourcePts"],1000)
        self.assertEqual(record["evidence"]["numericVisual"]["windows"][0]
                         ["sampledFramePairs"][0]["meanAbsoluteDisplayRgbDelta"],.05)
        self.assertNotIn(str(self.root),(self.out/"film-one.json").read_text())
        self.assertNotIn("/Users/secret/",(self.out/"film-one.json").read_text())
        validated=validate_repository_analysis(self.out,self.catalog)
        self.assertEqual(validated["numericSampledVideos"],1)

    def test_extra_per_frame_path_fails_closed_before_git_export(self):
        self.write_numeric(extra_field=True)
        visual=json.loads(self.visual_index.read_text())
        visual["entries"][0]["probeArtifacts"][0]["sha256"]=hashlib.sha256(
            self.numeric_file.read_bytes()).hexdigest()
        self.visual_index.write_text(json.dumps(visual))
        with self.assertRaisesRegex(ValueError,"unapproved data"):
            self.export()
        self.assertFalse(self.out.exists())


if __name__=="__main__":
    unittest.main()
