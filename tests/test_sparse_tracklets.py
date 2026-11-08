"""Synthetic continuity tests; do not depend on FFmpeg or third-party models."""

import json
import unittest
from fractions import Fraction

from kumiki_reference_lab.analyzers.motion.tracklets import build_sparse_tracklets


def _vector(x, y, dx, dy, group="unclassified"):
    return {"x": x, "y": y, "dx": dx, "dy": dy, "group": group}


def _pair(start, end, *vectors, status="single-image-translation-candidate"):
    return {"startPts": start, "endPts": end, "status": status,
            "vectors": list(vectors)}


def _build(pairs):
    return build_sparse_tracklets(pairs, timebase=Fraction(1, 100))


class SparseTrackletTests(unittest.TestCase):
    def test_consistent_points_link_across_consecutive_pairs_with_original_pts(self):
        pairs = [
            _pair(10, 20, _vector(30, 40, 2, 1, "dominant")),
            _pair(20, 35, _vector(32, 41, 2, 1, "secondary")),
            _pair(35, 52, _vector(34, 42, 2, 1, "secondary")),
        ]
        result = _build(pairs)
        self.assertEqual(result["status"], "candidate-only")
        self.assertEqual(len(result["tracklets"]), 1)
        track = result["tracklets"][0]
        self.assertEqual(track["id"], "tracklet-0001")
        self.assertEqual(track["pairCount"], 3)
        self.assertEqual(track["endReason"], "scan-end")
        self.assertEqual([(obs["pairIndex"], obs["vectorIndex"],
                           obs["startPts"], obs["endPts"])
                          for obs in track["observations"]],
                         [(0, 0, 10, 20), (1, 0, 20, 35), (2, 0, 35, 52)])
        self.assertEqual([obs["handoffErrorPixels"]
                          for obs in track["observations"]], [None, 0.0, 0.0])
        self.assertEqual([obs["group"] for obs in track["observations"]],
                         ["dominant", "secondary", "secondary"])
        self.assertFalse(result["semanticIdentityVerified"])
        self.assertFalse(result["calibratedConfidence"])
        motion = track["kinematics"]
        self.assertEqual(motion["durationSeconds"], {"numerator": 21, "denominator": 50})
        self.assertEqual(motion["summedImageDisplacementPixels"], {"dx": 6, "dy": 3})
        self.assertAlmostEqual(motion["observedPathLengthPixels"], 6.7082, places=4)
        self.assertAlmostEqual(motion["meanImageVelocityPixelsPerSecond"]["dx"],
                               14.2857, places=4)
        self.assertAlmostEqual(motion["meanImageVelocityPixelsPerSecond"]["dy"],
                               7.1429, places=4)
        self.assertAlmostEqual(motion["meanImageSpeedPixelsPerSecond"], 15.9719, places=4)
        self.assertEqual(motion["basis"], "observed-pairs-only-no-gap-filling")
        json.dumps(result, allow_nan=False)

    def test_missing_or_distant_observation_does_not_invent_continuity(self):
        result = _build([
            _pair(0, 10, _vector(10, 10, 2, 0)),
            _pair(10, 20, _vector(60, 10, 2, 0)),
            _pair(20, 30),
            _pair(30, 40, _vector(64, 10, 2, 0)),
        ])
        self.assertEqual(result["status"], "insufficient-continuity")
        self.assertEqual(result["tracklets"], [])
        self.assertEqual(result["singlePairCandidatesDiscarded"], 3)

    def test_cut_boundary_ends_track_and_prevents_cross_cut_link(self):
        result = _build([
            _pair(0, 10, _vector(10, 10, 2, 0)),
            _pair(10, 20, _vector(12, 10, 2, 0)),
            _pair(20, 30, status="cut-boundary"),
            _pair(30, 40, _vector(14, 10, 2, 0)),
            _pair(40, 50, _vector(16, 10, 2, 0)),
        ])
        self.assertEqual(len(result["tracklets"]), 2)
        self.assertEqual([t["pairCount"] for t in result["tracklets"]], [2, 2])
        self.assertEqual([t["endReason"] for t in result["tracklets"]],
                         ["cut-boundary", "scan-end"])
        self.assertEqual([t["observations"][0]["pairIndex"]
                          for t in result["tracklets"]], [0, 3])

    def test_missing_pair_or_nonadjacent_pts_ends_track(self):
        result = _build([
            _pair(0, 10, _vector(10, 10, 2, 0)),
            _pair(10, 20, _vector(12, 10, 2, 0)),
            _pair(24, 30, _vector(14, 10, 2, 0)),
            _pair(30, 40, _vector(16, 10, 2, 0)),
        ])
        self.assertEqual(len(result["tracklets"]), 2)
        self.assertEqual(result["tracklets"][0]["endReason"],
                         "nonadjacent-or-missing-observation")

    def test_ambiguous_endpoint_does_not_choose_arbitrary_neighbor(self):
        result = _build([
            _pair(0, 10, _vector(10, 10, 2, 0)),
            _pair(10, 20, _vector(12, 10, 2, 0),
                  _vector(12, 10, -1, 0)),
        ])
        self.assertEqual(result["status"], "insufficient-continuity")
        self.assertEqual(result["tracklets"], [])
        self.assertEqual(result["singlePairCandidatesDiscarded"], 3)

    def test_two_old_tracks_competing_for_one_new_point_abstain(self):
        result = _build([
            _pair(0, 10, _vector(10, 10, 2, 0),
                  _vector(14, 10, -2, 0)),
            _pair(10, 20, _vector(12, 10, 2, 0)),
        ])
        self.assertEqual(result["tracklets"], [])
        self.assertEqual(result["singlePairCandidatesDiscarded"], 3)

    def test_borderline_error_is_measured_and_deterministic(self):
        pairs = [
            _pair(0, 10, _vector(10, 10, 2, 0)),
            _pair(10, 20, _vector(13, 10, 1, 0)),
        ]
        result = _build(pairs)
        self.assertEqual(result, _build(pairs))
        self.assertEqual(result["tracklets"][0]["observations"][1]
                         ["handoffErrorPixels"], 1.0)
        self.assertEqual(result["linkTolerancePixels"], 2.0)
        self.assertEqual(result["ambiguityMarginPixels"], 0.5)

    def test_opposing_movements_keep_path_length_even_with_zero_net_displacement(self):
        result = _build([
            _pair(0, 10, _vector(10, 20, 2, 0)),
            _pair(10, 30, _vector(12, 20, -2, 0)),
        ])
        motion = result["tracklets"][0]["kinematics"]
        self.assertEqual(motion["durationSeconds"], {"numerator": 3, "denominator": 10})
        self.assertEqual(motion["summedImageDisplacementPixels"], {"dx": 0, "dy": 0})
        self.assertEqual(motion["observedPathLengthPixels"], 4)
        self.assertAlmostEqual(motion["meanImageSpeedPixelsPerSecond"], 13.3333)
        self.assertEqual(motion["meanImageVelocityPixelsPerSecond"], {"dx": 0, "dy": 0})

    def test_invalid_timebase_or_nonpositive_duration_fails_closed(self):
        pairs = [_pair(20, 10, _vector(10, 20, 2, 0)),
                 _pair(10, 0, _vector(12, 20, 2, 0))]
        with self.assertRaises(ValueError):
            _build(pairs)
        with self.assertRaises(ValueError):
            build_sparse_tracklets(pairs, timebase=Fraction(0, 1))
        with self.assertRaises(ValueError):
            build_sparse_tracklets(pairs, timebase=Fraction(-1, 100))

    def test_optional_pts_scaled_motion_check_preserves_variable_frame_intervals(self):
        pairs = [
            _pair(5, 15, _vector(10, 20, 2, 1)),
            _pair(15, 35, _vector(12, 21, 4, 2)),
            _pair(35, 40, _vector(16, 23, 1, 0.5)),
        ]
        original = _build(pairs)
        self.assertNotIn("motionMinimumTolerancePixels", original)
        self.assertNotIn("motionResidualPixels", original["tracklets"][0]["observations"][0])
        checked = build_sparse_tracklets(
            pairs, timebase=Fraction(1, 100), motion_consistency=True)
        self.assertEqual(checked["method"],
                         "mutual-nearest-adjacent-endpoint-motion-gated-v1")
        self.assertEqual(checked["motionInconsistentLinkCandidates"], 0)
        self.assertEqual(checked["tracklets"][0]["pairCount"], 3)
        self.assertEqual([o["motionResidualPixels"]
                          for o in checked["tracklets"][0]["observations"]],
                         [None, 0.0, 0.0])
        self.assertEqual(checked["tracklets"][0]["kinematics"]["durationSeconds"],
                         {"numerator": 7, "denominator": 20})
        json.dumps(checked, allow_nan=False)

    def test_optional_motion_check_abstains_on_endpoint_identity_switch(self):
        pairs = [
            _pair(0, 10, _vector(30, 40, 4, 0)),
            _pair(10, 20, _vector(34, 40, -4, 0)),
        ]
        self.assertEqual(_build(pairs)["tracklets"][0]["pairCount"], 2)
        checked = build_sparse_tracklets(
            pairs, timebase=Fraction(1, 100), motion_consistency=True)
        self.assertEqual(checked["status"], "insufficient-continuity")
        self.assertEqual(checked["tracklets"], [])
        self.assertEqual(checked["motionInconsistentLinkCandidates"], 1)
        self.assertEqual(checked["singlePairCandidatesDiscarded"], 2)

    def test_motion_check_cannot_override_mutual_nearest_ambiguity(self):
        pairs = [
            _pair(0, 10, _vector(30, 40, 4, 0)),
            _pair(10, 20, _vector(34, 40, 4, 0),
                  _vector(34, 40, -4, 0)),
        ]
        checked = build_sparse_tracklets(
            pairs, timebase=Fraction(1, 100), motion_consistency=True)
        self.assertEqual(checked["tracklets"], [])
        self.assertEqual(checked["motionInconsistentLinkCandidates"], 0)
        with self.assertRaisesRegex(ValueError, "boolean"):
            build_sparse_tracklets(pairs, timebase=Fraction(1, 100),
                                   motion_consistency=1)


if __name__ == "__main__":
    unittest.main()
