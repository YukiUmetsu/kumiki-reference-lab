"""Mock macOS Vision on non-Mac CI; preserve source-timebase evidence."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.mac_vision_detection import (
    _detect_humans_with_vision, _native_rect, detect_mac_vision_people,
)
from kumiki_reference_lab.pipeline.subject_detections import (
    associate_detection_tracklets, load_subject_detections,
)


class MacVisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "local-video.mp4"
        self.source.write_bytes(b"synthetic local source; real FFmpeg mocked")
        self.out = root / "human-detections.json"
        self.meta = {
            "source": {"sha256": "a"*64},
            "video": {"streamIndex": 0, "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }
        self.frames = [SimpleNamespace(pts=i*1000, ordinal=i) for i in range(3)]
        self.cuts = SimpleNamespace(timebase=Fraction(1,1000), pts=(1500,))

    def mock_run(self, *, cuts=None, detect=None):
        cuts = self.cuts if cuts is None else cuts
        detected = detect or (lambda *args: [{
            "category": "person", "score": .91, "box": [.1,.2,.2,.5]
        }])
        with (patch("kumiki_reference_lab.pipeline.mac_vision_detection.inspect_source",
                    return_value=self.meta),
              patch("kumiki_reference_lab.pipeline.mac_vision_detection.read_frame_pts",
                    return_value=self.frames),
              patch("kumiki_reference_lab.pipeline.mac_vision_detection.read_rgb_frames",
                    side_effect=lambda *args, **kwargs: [
                        b"\x7f" * (kwargs["width"]*kwargs["height"]*3)
                        for _ in args[2]]),
              patch("kumiki_reference_lab.pipeline.mac_vision_detection.detect_hard_cut_pts",
                    return_value=cuts),
              patch("kumiki_reference_lab.pipeline.mac_vision_detection._detect_humans_with_vision",
                    side_effect=detected)):
            return detect_mac_vision_people(
                self.source, self.out, max_samples=5, width=160, height=90)

    def test_pts_grounded_local_people_to_tracklet_handoff(self):
        self.mock_run()
        data = load_subject_detections(self.out)
        self.assertEqual(data["sourceSha256"], "a"*64)
        self.assertEqual([x["sourcePts"] for x in data["frames"]], [0,1000,2000])
        self.assertEqual(data["cutCandidatePts"], [1500])
        self.assertTrue(all(row["detections"][0]["category"] == "person"
                            for row in data["frames"]))
        self.assertIsNone(data["detector"]["modelSha256"])
        scene, report = associate_detection_tracklets(data)
        self.assertEqual(report["trackletCount"], 2)  # cut prevents identity link
        self.assertEqual(scene["actions"], [])
        self.assertEqual(scene["identityClaims"], [])
        with self.assertRaisesRegex(ValueError, "nonexisting"):
            self.mock_run()

    def test_native_rect_flips_bottom_origin_to_top(self):
        rect = SimpleNamespace(origin=SimpleNamespace(x=.2, y=.2),
                               size=SimpleNamespace(width=.3, height=.25))
        self.assertEqual(_native_rect(rect), (.2,.55,.3,.25))
        self.assertEqual(_native_rect(((.2,.2),(.3,.25))), (.2,.55,.3,.25))
        rect.origin.x = float("nan")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            _native_rect(rect)

    def test_mac_vision_binding_mock_no_host_dependency(self):
        class Observation:
            def __init__(self, x, confidence):
                self.x = x
                self.value = confidence
            def confidence(self):
                return self.value
            def boundingBox(self):
                return ((self.x,.1),(.25,.55))

        class Request:
            def alloc(self):
                return self
            def init(self):
                return self
            def results(self):
                return [Observation(.6,.82), Observation(.1,.97), Observation(.1,.92)]

        class Handler:
            def alloc(self):
                return self
            def initWithData_options_(self, data, opts):
                return self
            def performRequests_error_(self, requests, error):
                return True, None

        foundation = SimpleNamespace(NSData=SimpleNamespace(
            dataWithBytes_length_=lambda blob, length: blob))
        vision = SimpleNamespace(VNDetectHumanRectanglesRequest=Request(),
                                 VNImageRequestHandler=Handler())
        with (patch("kumiki_reference_lab.pipeline.mac_vision_detection.sys.platform", "darwin"),
              patch.dict(sys.modules, {"Foundation": foundation, "Vision": vision})):
            proposals = _detect_humans_with_vision(b"\x80"*160*90*3, 160, 90)
        self.assertEqual(len(proposals), 2)
        self.assertEqual(proposals[0]["box"][0], .1)
        self.assertTrue(all(p["category"] == "person" for p in proposals))

    def test_fails_without_macos_when_not_mocked(self):
        with patch("kumiki_reference_lab.pipeline.mac_vision_detection.sys.platform", "linux"):
            with self.assertRaisesRegex(ValueError, "requires macOS"):
                _detect_humans_with_vision(b"\x80"*160*90*3, 160, 90)

    def test_mismatched_cut_timebase_never_publishes(self):
        with self.assertRaisesRegex(ValueError, "timestamps differ"):
            self.mock_run(cuts=SimpleNamespace(timebase=Fraction(1,90000), pts=()))
        self.assertFalse(self.out.exists())

    def test_vision_runtime_error_never_publishes(self):
        def fail(*args):
            raise ValueError("synthetic vision error")
        with self.assertRaisesRegex(ValueError, "synthetic vision error"):
            self.mock_run(detect=fail)
        self.assertFalse(self.out.exists())

    def test_parameter_bounds_and_cli(self):
        for opts in ({"seconds": 121}, {"max_samples": 25},
                     {"width": 1000}, {"cut_threshold": float("nan")}):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                detect_mac_vision_people(self.source, self.out, **opts)
        args = build_parser().parse_args(
            ["mac-vision-humans", "clip.mp4", "--out", "detections.json",
             "--max-seconds", "15"])
        self.assertEqual(args.command, "mac-vision-humans")
        self.assertEqual(args.seconds if hasattr(args,"seconds") else args.max_seconds, 15)


if __name__ == "__main__":
    unittest.main()
