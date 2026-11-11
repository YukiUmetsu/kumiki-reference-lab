"""Optional global translation is PTS-anchored, cut-gated, never camera truth."""
from __future__ import annotations

import importlib.util
import json
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.analyzers.appearance.source_visual_probe import (
    analyze_source_visual_window,
)
from kumiki_reference_lab.catalog.whatships_analysis_store import (
    _validate_image_translation,
)
from kumiki_reference_lab.cli.app import build_parser


class ImageTranslationSchemaTests(unittest.TestCase):
    def test_cut_boundaries_demand_abstention(self):
        _validate_image_translation({
            "status":"cut-boundary","dxPixels":None,
            "dyPixels":None,"peakToSidelobeRatio":None,
        },pair_status="cut-candidate-between-samples",width=160,height=90)
        with self.assertRaisesRegex(ValueError,"abstain"):
            _validate_image_translation({
                "status":"measured-image-translation","dxPixels":3.0,
                "dyPixels":0.0,"peakToSidelobeRatio":12,
            },pair_status="cut-candidate-between-samples",
                width=160,height=90)

    def test_unreviewed_motion_never_accepts_camera_claims_or_unsafe_fields(self):
        for proposal in (
            {"status":"camera-pan","dxPixels":3,"dyPixels":0,"peakToSidelobeRatio":12},
            {"status":"measured-image-translation","dxPixels":200,"dyPixels":0,
             "peakToSidelobeRatio":12},
            {"status":"measured-image-translation","dxPixels":2,"dyPixels":0,
             "peakToSidelobeRatio":float("nan")},
            {"status":"ambiguous-correlation","dxPixels":3,"dyPixels":0,
             "peakToSidelobeRatio":5},
            {"status":"measured-image-translation","dxPixels":2,"dyPixels":0,
             "peakToSidelobeRatio":12,"localVideoPath":"/private/clip.mp4"},
        ):
            with self.subTest(proposal=proposal),self.assertRaises(ValueError):
                _validate_image_translation(
                    proposal,pair_status="rgb-image-difference-proxy",
                    width=160,height=90)
        _validate_image_translation({
            "status":"measured-image-translation","dxPixels":2.0,
            "dyPixels":-1.0,"peakToSidelobeRatio":12.5,
        },pair_status="rgb-image-difference-proxy",width=160,height=90)

    def test_cli_parse_for_real_source_window_translation(self):
        args=build_parser().parse_args([
            "source-visual-probe","original.mp4",
            "--out","study","--image-translation"])
        self.assertTrue(args.image_translation)


@unittest.skipUnless(importlib.util.find_spec("numpy"),
                     "Optional NumPy motion extra is not installed")
class RealPhaseTranslationMathTests(unittest.TestCase):
    def test_random_textured_frame_shifts_not_a_camera_label(self):
        from kumiki_reference_lab.analyzers.motion.phase import measure_image_shift
        w,h=160,90
        rnd=random.Random(42)
        src=bytes(rnd.randrange(256) for _ in range(w*h))
        target=bytearray(w*h)
        for y in range(h):
            for x in range(w-4):
                target[y*w+x+4]=src[y*w+x]
        report=measure_image_shift(src,bytes(target),w,h)
        self.assertEqual(report["status"],"measured-image-translation")
        self.assertAlmostEqual(report["dxPixels"],4,delta=.6)
        self.assertAlmostEqual(report["dyPixels"],0,delta=.6)
        self.assertGreater(report["peakToSidelobeRatio"],6)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Real FFmpeg/FFprobe not installed")
class RealPtsImageTranslationFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/"generated-red-blue.mp4"
        run=subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
            "-f","lavfi","-i","color=c=red:s=160x90:r=5:d=2",
            "-f","lavfi","-i","color=c=blue:s=160x90:r=5:d=2",
            "-filter_complex","[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map","[v]","-c:v","mpeg4","-q:v","5",
            "-pix_fmt","yuv420p",str(self.source),
        ],capture_output=True,timeout=25)
        if run.returncode:
            self.fail("could not generate controlled two-shot source")
    def test_cut_pairs_abstain_and_noncut_global_shift_is_measured_only_by_model(self):
        def fake_shift(before,after,width,height):
            self.assertEqual((width,height),(160,90))
            self.assertEqual(len(before),160*90)
            self.assertEqual(len(after),160*90)
            return {"status":"measured-image-translation","dxPixels":0.0,
                    "dyPixels":0.0,"peakToSidelobeRatio":12.0}
        with patch(
            "kumiki_reference_lab.analyzers.motion.phase.measure_image_shift",
            side_effect=fake_shift,
        ) as measured:
            data=analyze_source_visual_window(
                self.source,seconds=4,max_samples=10,width=160,height=90,
                image_translation=True)
        self.assertGreaterEqual(len(data["cutCandidatePts"]),1)
        cut_pairs=[p for p in data["sampledFramePairs"]
                   if p["status"]=="cut-candidate-between-samples"]
        self.assertTrue(cut_pairs)
        self.assertTrue(all(p["imageTranslation"]["status"]=="cut-boundary"
                            and p["imageTranslation"]["dxPixels"] is None
                            for p in cut_pairs))
        normal_pairs=[p for p in data["sampledFramePairs"]
                      if p["status"]=="rgb-image-difference-proxy"]
        self.assertEqual(measured.call_count,len(normal_pairs))
        self.assertTrue(all(p["imageTranslation"]["status"]=="measured-image-translation"
                            for p in normal_pairs))
        self.assertEqual(data["scan"]["sourceTimebaseVerified"],True)
        self.assertTrue(all(p["startPts"]<p["endPts"] for p in data["sampledFramePairs"]))


if __name__=="__main__":
    unittest.main()
