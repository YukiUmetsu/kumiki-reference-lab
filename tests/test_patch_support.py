"""Opt-in local appearance support is not semantic occlusion detection."""

import importlib.util
import json
import random
import unittest

from kumiki_reference_lab.analyzers.motion.patch_support import assess_patch_support
from kumiki_reference_lab.cli.app import build_parser


class PatchSupportTests(unittest.TestCase):
    def test_global_patch_match_can_hide_local_appearance_loss(self):
        from kumiki_reference_lab.analyzers.motion.handoff_appearance import _ncc

        rng = random.Random(323)
        original = bytes(rng.randint(116, 140) if y < 5 else
                         rng.randint(10, 245) for y in range(9) for _ in range(9))
        # The lower half still matches strongly enough to dominate a global
        # NCC score, although the upper half has lost all useful texture.
        obstructed = bytes(128 if y < 5 else original[y * 9 + x]
                           for y in range(9) for x in range(9))
        self.assertGreater(_ncc(tuple(original), tuple(obstructed)), 0.85)
        result = assess_patch_support(original, obstructed)
        self.assertEqual(result["status"], "localized-appearance-unreliable")
        self.assertEqual(result["supportingQuadrants"], 2)
        self.assertEqual(result["quadrantCorrelations"][:2], [None, None])
        self.assertEqual(assess_patch_support(original, original)["status"], "supported")
        json.dumps(result, allow_nan=False)

    def test_invalid_patches_rejected(self):
        with self.assertRaisesRegex(ValueError, "nine-pixel"):
            assess_patch_support(b"tiny", b"tiny")

    def test_cli_flags_default_off(self):
        parser = build_parser()
        self.assertFalse(parser.parse_args(["sparse-flow", "example.mp4"])
                         .quadrant_consistency)
        self.assertTrue(parser.parse_args(["sparse-flow", "example.mp4",
                                           "--quadrant-consistency"])
                        .quadrant_consistency)
        self.assertTrue(parser.parse_args(["analyze", "example.mp4", "--out", "runs",
                                           "--sparse-flow", "--sparse-quadrant-consistency"])
                        .sparse_quadrant_consistency)


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy unavailable")
class PatchSupportFlowTests(unittest.TestCase):
    def test_opt_in_guard_preserves_strong_integer_translations(self):
        import numpy as np

        from kumiki_reference_lab.analyzers.motion.features import sparse_patch_flows

        original = np.random.default_rng(277).integers(0, 255, (90, 160), dtype=np.uint8)
        shifted = np.roll(original, 3, axis=1)
        baseline = sparse_patch_flows(original.tobytes(), shifted.tobytes(), 160, 90)
        guarded = sparse_patch_flows(original.tobytes(), shifted.tobytes(), 160, 90,
                                     quadrant_consistency=True)
        self.assertGreater(len(baseline["accepted"]), 20)
        self.assertEqual(len(guarded["accepted"]), len(baseline["accepted"]))
        self.assertEqual(guarded["rejected"]["quadrant-inconsistent"], 0)
        self.assertTrue(all(v["quadrantSupportCount"] >= 3 and
                            len(v["quadrantCorrelations"]) == 4
                            for v in guarded["accepted"]))
        self.assertNotIn("quadrant-inconsistent", baseline["rejected"])
        with self.assertRaisesRegex(ValueError, "boolean"):
            sparse_patch_flows(original.tobytes(), shifted.tobytes(), 160, 90,
                               quadrant_consistency=1)


if __name__ == "__main__":
    unittest.main()
