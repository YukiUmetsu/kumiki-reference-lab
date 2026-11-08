"""Synthetic continuity tests; do not depend on FFmpeg or third-party models."""

import json
import unittest

from kumiki_reference_lab.analyzers.motion.tracklets import build_sparse_tracklets


def _vector(x, y, dx, dy, group="unclassified"):
    return {"x": x, "y": y, "dx": dx, "dy": dy, "group": group}


def _pair(start, end, *vectors, status="single-image-translation-candidate"):
    return {"startPts": start, "endPts": end, "status": status,
            "vectors": list(vectors)}


class SparseTrackletTests(unittest.TestCase):
    def test_consistent_points_link_across_consecutive_pairs_with_original_pts(self):
        pairs = [
            _pair(10, 20, _vector(30, 40, 2, 1, "dominant")),
            _pair(20, 35, _vector(32, 41, 2, 1, "secondary")),
            _pair(35, 52, _vector(34, 42, 2, 1, "secondary")),
        ]
        result = build_sparse_tracklets(pairs)
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
        json.dumps(result, allow_nan=False)

    def test_missing_or_distant_observation_does_not_invent_continuity(self):
        result = build_sparse_tracklets([
            _pair(0, 10, _vector(10, 10, 2, 0)),
            _pair(10, 20, _vector(60, 10, 2, 0)),
            _pair(20, 30),
            _pair(30, 40, _vector(64, 10, 2, 0)),
        ])
        self.assertEqual(result["status"], "insufficient-continuity")
        self.assertEqual(result["tracklets"], [])
        self.assertEqual(result["singlePairCandidatesDiscarded"], 3)

    def test_cut_boundary_ends_track_and_prevents_cross_cut_link(self):
        result = build_sparse_tracklets([
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
        result = build_sparse_tracklets([
            _pair(0, 10, _vector(10, 10, 2, 0)),
            _pair(10, 20, _vector(12, 10, 2, 0)),
            _pair(24, 30, _vector(14, 10, 2, 0)),
            _pair(30, 40, _vector(16, 10, 2, 0)),
        ])
        self.assertEqual(len(result["tracklets"]), 2)
        self.assertEqual(result["tracklets"][0]["endReason"],
                         "nonadjacent-or-missing-observation")

    def test_ambiguous_endpoint_does_not_choose_arbitrary_neighbor(self):
        result = build_sparse_tracklets([
            _pair(0, 10, _vector(10, 10, 2, 0)),
            _pair(10, 20, _vector(12, 10, 2, 0),
                  _vector(12, 10, -1, 0)),
        ])
        self.assertEqual(result["status"], "insufficient-continuity")
        self.assertEqual(result["tracklets"], [])
        self.assertEqual(result["singlePairCandidatesDiscarded"], 3)

    def test_two_old_tracks_competing_for_one_new_point_abstain(self):
        result = build_sparse_tracklets([
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
        result = build_sparse_tracklets(pairs)
        self.assertEqual(result, build_sparse_tracklets(pairs))
        self.assertEqual(result["tracklets"][0]["observations"][1]
                         ["handoffErrorPixels"], 1.0)
        self.assertEqual(result["linkTolerancePixels"], 2.0)
        self.assertEqual(result["ambiguityMarginPixels"], 0.5)


if __name__ == "__main__":
    unittest.main()
