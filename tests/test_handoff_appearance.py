"""Controlled two-hop appearance checks without an external video dependency."""

import random
import unittest
from fractions import Fraction

from kumiki_reference_lab.analyzers.motion.handoff_appearance import (
    two_hop_patch_agreement,
)
from kumiki_reference_lab.analyzers.motion.tracklets import build_sparse_tracklets
from kumiki_reference_lab.cli.app import build_parser


WIDTH, HEIGHT = 160, 90


def _noise(seed=17):
    rng = random.Random(seed)
    return bytes(rng.randrange(256) for _ in range(WIDTH * HEIGHT))


def _shift(frame, dx, dy):
    return bytes(frame[((y - dy) % HEIGHT) * WIDTH + (x - dx) % WIDTH]
                 for y in range(HEIGHT) for x in range(WIDTH))


def _pairs():
    return [{"startPts": 0, "endPts": 10,
             "status": "single-image-translation-candidate",
             "vectors": [{"x": 30, "y": 40, "dx": 2, "dy": 0}]},
            {"startPts": 10, "endPts": 20,
             "status": "single-image-translation-candidate",
             "vectors": [{"x": 32, "y": 40, "dx": 2, "dy": 0}]}]


class TwoHopAppearanceTests(unittest.TestCase):
    def test_cli_appearance_flags_are_opt_in(self):
        parser = build_parser()
        self.assertFalse(parser.parse_args(["sparse-flow", "source.mp4"])
                         .tracklet_appearance_consistency)
        self.assertTrue(parser.parse_args([
            "sparse-flow", "source.mp4", "--tracklet-appearance-consistency"
        ]).tracklet_appearance_consistency)
        self.assertTrue(parser.parse_args([
            "analyze", "source.mp4", "--out", "runs", "--sparse-flow",
            "--sparse-tracklet-appearance-consistency"
        ]).sparse_tracklet_appearance_consistency)

    def test_consistent_texture_across_three_frames_is_source_linked(self):
        original = _noise()
        frames = [original, _shift(original, 2, 0), _shift(original, 4, 0)]
        report = build_sparse_tracklets(
            _pairs(), timebase=Fraction(1, 100), appearance_consistency=True,
            appearance_frames=frames, frame_width=WIDTH, frame_height=HEIGHT)
        self.assertEqual(report["method"],
                         "mutual-nearest-adjacent-endpoint-appearance-gated-v1")
        self.assertEqual(report["appearanceInconsistentLinkCandidates"], 0)
        self.assertEqual(report["appearanceUnobservableLinkCandidates"], 0)
        self.assertEqual(report["tracklets"][0]["pairCount"], 2)
        self.assertEqual(report["tracklets"][0]["observations"][0]
                         ["twoHopAppearanceCorrelation"], None)
        self.assertEqual(report["tracklets"][0]["observations"][1]
                         ["twoHopAppearanceCorrelation"], 1.0)
        self.assertEqual(report["tracklets"][0]["observations"][1]
                         ["twoHopAppearanceShiftPixels"], {"dx": 0, "dy": 0})

    def test_unrelated_two_hop_appearance_rejects_geometric_handoff(self):
        first = _noise()
        frames = [first, _shift(first, 2, 0), _noise(91)]
        baseline = build_sparse_tracklets(_pairs(), timebase=Fraction(1, 100))
        self.assertEqual(len(baseline["tracklets"]), 1)
        checked = build_sparse_tracklets(
            _pairs(), timebase=Fraction(1, 100), appearance_consistency=True,
            appearance_frames=frames, frame_width=WIDTH, frame_height=HEIGHT)
        self.assertEqual(checked["tracklets"], [])
        self.assertEqual(checked["appearanceInconsistentLinkCandidates"], 1)

    def test_one_pixel_endpoint_error_can_be_tolerated_without_gap_filling(self):
        first = _noise()
        result = two_hop_patch_agreement(
            first, _shift(first, 4, 0), WIDTH, HEIGHT,
            first_point={"x": 30, "y": 40}, last_point={"x": 35, "y": 40})
        self.assertEqual(result["status"], "appearance-consistent")
        self.assertEqual(result["correlation"], 1.0)
        self.assertEqual(result["shiftPixels"], {"dx": -1, "dy": 0})

    def test_unobservable_and_invalid_source_frames_fail_closed(self):
        flat = bytes([128] * WIDTH * HEIGHT)
        first = _noise()
        result = two_hop_patch_agreement(
            flat, first, WIDTH, HEIGHT,
            first_point={"x": 30, "y": 40}, last_point={"x": 34, "y": 40})
        self.assertEqual(result["status"], "unobservable")
        checked = build_sparse_tracklets(
            _pairs(), timebase=Fraction(1, 100), appearance_consistency=True,
            appearance_frames=[flat, first, first], frame_width=WIDTH,
            frame_height=HEIGHT)
        self.assertEqual(checked["appearanceUnobservableLinkCandidates"], 1)
        self.assertEqual(checked["tracklets"], [])
        with self.assertRaisesRegex(ValueError, "sampled grayscale frames"):
            build_sparse_tracklets(_pairs(), timebase=Fraction(1, 100),
                                   appearance_consistency=True, appearance_frames=[first],
                                   frame_width=WIDTH, frame_height=HEIGHT)
        with self.assertRaisesRegex(ValueError, "same-size"):
            two_hop_patch_agreement(first, b"short", WIDTH, HEIGHT,
                                    first_point={"x": 30, "y": 40},
                                    last_point={"x": 34, "y": 40})

    def test_optional_motion_and_appearance_gates_can_combine(self):
        first = _noise()
        frames = [first, _shift(first, 2, 0), _shift(first, 4, 0)]
        result = build_sparse_tracklets(
            _pairs(), timebase=Fraction(1, 100), appearance_consistency=True,
            motion_consistency=True, appearance_frames=frames,
            frame_width=WIDTH, frame_height=HEIGHT)
        self.assertEqual(result["method"],
                         "mutual-nearest-adjacent-endpoint-motion-gated-appearance-gated-v1")
        self.assertEqual(result["tracklets"][0]["observations"][1]
                         ["motionResidualPixels"], 0.0)
        self.assertEqual(result["tracklets"][0]["observations"][1]
                         ["twoHopAppearanceCorrelation"], 1.0)

    def test_appearance_cannot_resolve_geometric_ambiguity_or_cross_cuts(self):
        first = _noise()
        frames = [first, _shift(first, 2, 0), _shift(first, 4, 0)]
        ambiguous = _pairs()
        ambiguous[1]["vectors"].append({"x": 32, "y": 40, "dx": -4, "dy": 0})
        report = build_sparse_tracklets(
            ambiguous, timebase=Fraction(1, 100), appearance_consistency=True,
            appearance_frames=frames, frame_width=WIDTH, frame_height=HEIGHT)
        self.assertEqual(report["tracklets"], [])
        self.assertEqual(report["appearanceInconsistentLinkCandidates"], 0)
        cut = _pairs()
        cut[1]["status"] = "cut-boundary"
        cut[1]["vectors"] = []
        report = build_sparse_tracklets(
            cut, timebase=Fraction(1, 100), appearance_consistency=True,
            appearance_frames=frames, frame_width=WIDTH, frame_height=HEIGHT)
        self.assertEqual(report["tracklets"], [])


if __name__ == "__main__":
    unittest.main()
