"""Public X post acquisition: rights gating, no cookies, real PTS, ephemeral video."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.catalog.whatships_analysis_store import (
    export_repository_analysis, validate_repository_analysis,
)
from kumiki_reference_lab.catalog.whatships_ephemeral_acquire import (
    _download_one_public_x_post, _x_video_origin,
    acquire_and_measure_x_video,
)
from kumiki_reference_lab.cli.app import build_parser, main
from tests.test_video_sources import whatships_fixture


class PublicXAcquisitionSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_original_post_is_exact_approved_catalog_link(self):
        snapshot=whatships_fixture()
        self.assertEqual(
            _x_video_origin(snapshot,"whatships:film-one"),
            "https://x.com/creator_a/status/2108251509830140401")
        with self.assertRaisesRegex(ValueError,"no verified X post"):
            _x_video_origin(snapshot,"whatships:film-two")
        with self.assertRaisesRegex(ValueError,"absent"):
            _x_video_origin(snapshot,"whatships:unknown")
        for url in (
            "http://x.com/user/status/2108251509830140401",
            "https://x.com.evil.test/user/status/2108251509830140401",
            "https://x.com@evil.test/user/status/2108251509830140401",
            "https://x.com/user/status/2108251509830140401?redirect=evil",
            "https://x.com/user/other/2108251509830140401",
        ):
            item=copy.deepcopy(snapshot)
            item["videos"][0]["detail"]["tweetUrl"]=url
            with self.subTest(url=url),self.assertRaises(ValueError):
                _x_video_origin(item,"whatships:film-one")

    def test_downloader_never_inherits_user_config_cookies_or_plugins(self):
        where=self.root/"video"
        where.mkdir()
        seen=[]
        class Proc:
            returncode=0
        def fake_run(args, **kwargs):
            seen.append((args,kwargs))
            (where/"source.mp4").write_bytes(b"small video")
            return Proc()
        with patch(
            "kumiki_reference_lab.catalog.whatships_ephemeral_acquire.subprocess.run",
            side_effect=fake_run,
        ):
            result=_download_one_public_x_post(
                "https://x.com/creator_a/status/2108251509830140401",
                where,yt_dlp="yt-dlp",timeout_seconds=60)
        self.assertEqual(result,where/"source.mp4")
        args,kwargs=seen[0]
        for flag in ("--ignore-config","--no-plugin-dirs","--no-playlist",
                     "--max-filesize","--no-continue","--no-part","--"):
            self.assertIn(flag,args)
        self.assertNotIn("--cookies",args)
        self.assertNotIn("--cookies-from-browser",args)
        self.assertEqual(kwargs["timeout"],60)
        self.assertEqual(kwargs["stderr"],subprocess.DEVNULL)
        self.assertEqual(kwargs["stdout"],subprocess.DEVNULL)

    def test_zero_multiple_oversized_or_extraneous_files_are_rejected(self):
        folder=self.root/"movie"
        folder.mkdir()
        class Proc:
            returncode=0
        def fake_run(args,**kwargs):
            (folder/"source.mp4").write_bytes(b"good clip")
            (folder/"source.webm").write_bytes(b"extra clip")
            return Proc()
        with patch(
            "kumiki_reference_lab.catalog.whatships_ephemeral_acquire.subprocess.run",
            side_effect=fake_run,
        ):
            with self.assertRaisesRegex(ValueError,"multiple"):
                _download_one_public_x_post(
                    "https://x.com/creator_a/status/2108251509830140401",
                    folder,yt_dlp="yt-dlp",timeout_seconds=60)

    def test_timeout_and_unavailable_post_do_not_create_evidence(self):
        folder=self.root/"empty"
        folder.mkdir()
        with patch(
            "kumiki_reference_lab.catalog.whatships_ephemeral_acquire.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["yt-dlp"],20),
        ):
            with self.assertRaisesRegex(ValueError,"bounded timeout"):
                _download_one_public_x_post(
                    "https://x.com/creator_a/status/2108251509830140401",
                    folder,yt_dlp="yt-dlp",timeout_seconds=60)

    def test_cli_refuses_missing_acknowledgement_or_rights_notes(self):
        args=build_parser().parse_args([
            "whatships-acquire-measure","whatships:film-one",
            "--rights-basis","written-permission",
            "--rights-note","The author gave written research permission.",
            "--identity-note","Exact original post and media were checked.",
        ])
        self.assertFalse(args.acknowledge_rights)
        self.assertEqual(args.source_id,"whatships:film-one")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Real FFmpeg and FFprobe needed for source-video integration")
class RealEphemeralXVideoStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.snapshot=self.root/"catalog.json"
        self.snapshot.write_text(json.dumps(whatships_fixture()))
        self.corpus=self.root/"research/analysis/whatships"
        self.corpus.parent.mkdir(parents=True)
        export_repository_analysis(self.snapshot,self.corpus)
        self.original=self.root/"original-generated-video.mp4"
        proc=subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
            "-f","lavfi","-i","color=c=red:s=160x90:r=5:d=2",
            "-f","lavfi","-i","color=c=blue:s=160x90:r=5:d=2",
            "-filter_complex","[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map","[v]","-c:v","mpeg4","-q:v","5",
            "-pix_fmt","yuv420p",str(self.original),
        ],capture_output=True,timeout=30)
        if proc.returncode:
            self.fail("could not generate original FFmpeg test fixture")
        self.sha=hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.download_location=None

    def fake_acquire(self,url,destination,*,yt_dlp,timeout_seconds):
        self.assertEqual(url,"https://x.com/creator_a/status/2108251509830140401")
        self.assertTrue(destination.is_dir())
        self.download_location=destination
        target=destination/"source.mp4"
        shutil.copyfile(self.original,target)
        return target

    def run_mock(self,**changes):
        with patch(
            "kumiki_reference_lab.catalog.whatships_ephemeral_acquire._download_one_public_x_post",
            side_effect=self.fake_acquire,
        ):
            return acquire_and_measure_x_video(
                self.snapshot,"whatships:film-one",self.corpus,
                **{
                    "rights_basis":"own-original-work",
                    "rights_note":"This is my own original FFmpeg-generated synthetic video.",
                    "identity_note":"Controlled synthetic video is mapped to fixture film-one only for a test.",
                    "acknowledge_rights":True,
                    "window_seconds":4,"window_count":1,"max_samples":8,
                    **changes,
                })

    def test_real_frame_pts_numeric_data_retained_but_download_is_deleted(self):
        result=self.run_mock()
        self.assertEqual(result["newMeasuredWindows"],1)
        self.assertEqual(result["newSampledOriginalSourceFrames"],8)
        self.assertTrue(result["gitWorkingTreeUpdated"])
        self.assertFalse(result["temporaryVideoRetained"])
        self.assertEqual(result["sourceIdentityStatus"],
                         "operator-attested-not-independently-verified")
        self.assertFalse(self.download_location.exists())
        self.assertEqual(validate_repository_analysis(self.corpus,self.snapshot)
                         ["numericSampledVideos"],1)
        record=json.loads((self.corpus/"film-one.json").read_text())
        self.assertEqual(record["sourceMediaSha256"],self.sha)
        window=record["evidence"]["numericVisual"]["windows"][0]
        self.assertEqual(window["startSeconds"],0)
        self.assertEqual(window["endSeconds"],4)
        self.assertEqual(window["scan"]["sampledSourcePtsCount"],8)
        self.assertGreater(window["scan"]["sourcePtsFramesSeenInInventory"],8)
        self.assertNotIn(str(self.download_location),
                         (self.corpus/"film-one.json").read_text())
        self.assertNotIn("FFmpeg-generated synthetic video",
                         (self.corpus/"film-one.json").read_text())

    def test_second_run_does_not_replace_finished_video_but_cleans_up(self):
        self.run_mock()
        before=(self.corpus/"film-one.json").read_bytes()
        result=self.run_mock()
        self.assertEqual(result["newMeasuredWindows"],0)
        self.assertFalse(result["gitWorkingTreeUpdated"])
        self.assertFalse(self.download_location.exists())
        self.assertEqual(before,(self.corpus/"film-one.json").read_bytes())

    def test_identity_rights_gating_happens_before_download(self):
        self.download_location=None
        with self.assertRaisesRegex(ValueError,"explicit authorized-source rights"):
            self.run_mock(acknowledge_rights=False)
        self.assertIsNone(self.download_location)
        with self.assertRaisesRegex(ValueError,"rights basis and exact"):
            self.run_mock(rights_note="short")
        self.assertIsNone(self.download_location)

    def test_failure_during_numeric_probe_removes_download_and_keeps_repo_intact(self):
        original=(self.corpus/"index.json").read_bytes()
        with patch(
            "kumiki_reference_lab.catalog.whatships_ephemeral_acquire._download_one_public_x_post",
            side_effect=self.fake_acquire,
        ), patch(
            "kumiki_reference_lab.catalog.whatships_ephemeral_acquire.measure_whatships_to_repository",
            side_effect=ValueError("synthetic local decoder error"),
        ):
            with self.assertRaisesRegex(ValueError,"local decoder error"):
                acquire_and_measure_x_video(
                    self.snapshot,"whatships:film-one",self.corpus,
                    rights_basis="own-original-work",
                    rights_note="This synthetic media is original testing content.",
                    identity_note="The controlled source identity is verified by test fixture.",
                    acknowledge_rights=True,
                )
        self.assertFalse(self.download_location.exists())
        self.assertEqual(original,(self.corpus/"index.json").read_bytes())
        self.assertFalse((self.corpus/"film-one.json").exists())


if __name__=="__main__":
    unittest.main()
