"""Source-PTS evidence window merge policy: append, never silently rewrite."""
from __future__ import annotations

import unittest

from kumiki_reference_lab.catalog.whatships_analysis_store import _append_numeric_windows


def study(windows, sha="a"*64):
    return {
        "sourceSha256":sha,
        "windows":[{"startSeconds":a,"endSeconds":b,"sampled":"same"}
                   for a,b in windows],
        "evidenceStatus":"sampled-original-source-pts-metrics-not-expert-reviewed",
    }


class IncrementalNumericWindowMergeTests(unittest.TestCase):
    def test_nonoverlapping_windows_are_sorted_and_preserved(self):
        prior=study([(0,3),(17,20)])
        incoming=study([(12,15),(8,11)])
        result=_append_numeric_windows(prior,incoming)
        self.assertEqual([(x["startSeconds"],x["endSeconds"])
                          for x in result["windows"]],
                         [(0,3),(8,11),(12,15),(17,20)])
        self.assertEqual(len(prior["windows"]),2)

    def test_exact_duplicate_window_is_idempotent(self):
        prior=study([(0,3),(17,20)])
        self.assertEqual(_append_numeric_windows(prior,study([(17,20)])),prior)

    def test_conflicting_overlap_cannot_be_silently_merged(self):
        old=study([(0,3),(17,20)])
        for newer in (study([(1,4)]),
                      study([(2,3)]),
                      study([(16,18)])):
            with self.subTest(newer=newer), self.assertRaisesRegex(
                ValueError,"overlapping numeric source windows differ"):
                _append_numeric_windows(old,newer)
        edited=study([(0,3)])
        edited["windows"][0]["sampled"]="modified claim"
        with self.assertRaisesRegex(ValueError,"overlapping numeric"):
            _append_numeric_windows(old,edited)

    def test_different_media_sha_never_appends(self):
        with self.assertRaisesRegex(ValueError,"different source"):
            _append_numeric_windows(study([(0,3)]),study([(3,5)],"b"*64))

    def test_caps_total_windows_without_renumbering_timestamps(self):
        full=study([(i*2,i*2+1) for i in range(64)])
        with self.assertRaisesRegex(ValueError,"bounded per-film limit"):
            _append_numeric_windows(full,study([(130,131)]))
        self.assertEqual(len(full["windows"]),64)


if __name__=="__main__":
    unittest.main()
