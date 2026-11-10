"""Browser observation notes are explicitly partial and cannot assert measured shots."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.browser_observations import (
    load_browser_observations, search_browser_observations,
)
from kumiki_reference_lab.catalog.video_sources import load_source_references
from kumiki_reference_lab.cli.app import main


ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return {
        "schemaVersion": "kumiki.browser-video-observations.v1",
        "reviewedOn": "2026-11-10",
        "methodology": "Selected public browser playback frames, not a complete review.",
        "observations": [
            {
                "sourceId": "whatships:claude-motion-reel",
                "reviewedOn": "2026-11-10",
                "method": "browser-player",
                "coverage": "selected-moments-only",
                "visualTags": ["kinetic-typography", "easing-demo"],
                "visibleMoments": ["Colored dots move on easing tracks.",
                                   "Repeated oversized black lettering on fluorescent yellow."],
                "techniqueHypotheses": ["Study timing contrasts across scenes."],
            },
            {
                "sourceId": "whatships:paper-mono-code",
                "reviewedOn": "2026-11-10",
                "method": "browser-player",
                "coverage": "selected-moments-only",
                "visualTags": ["editorial-collage"],
                "visibleMoments": ["Overlapping typographic sheets fold in a 3D-like composition."],
                "techniqueHypotheses": [],
            },
        ],
    }


class BrowserObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "observations.json"
        self.data = load_source_references(ROOT / "research", ROOT / "research/whatships-motion-2026-11-10.json")
        self.write(fixture())

    def write(self, value):
        self.path.write_text(json.dumps(value), encoding="utf-8")

    def load(self):
        return load_browser_observations(self.data, self.path)

    def test_joins_video_links_and_keeps_observations_distinct_from_metadata(self):
        observations = self.load()
        self.assertEqual(len(observations["observations"]), 2)
        first = observations["observations"][0]
        self.assertEqual(first["sourceId"], "whatships:claude-motion-reel")
        self.assertEqual(first["source"]["provider"], "whatships")
        self.assertIn("x.com", first["source"]["originalUrl"])
        self.assertIn("whatships.com", first["source"]["watchUrl"])
        self.assertEqual(first["coverage"], "selected-moments-only")
        self.assertNotIn("cutFrequency", first)
        self.assertEqual([v["sourceId"] for v in search_browser_observations(observations,
                                                                              visual_tag="editorial-collage")],
                         ["whatships:paper-mono-code"])
        self.assertEqual([v["sourceId"] for v in search_browser_observations(observations,
                                                                              source_id="whatships:claude-motion-reel")],
                         ["whatships:claude-motion-reel"])

    def test_rejects_unlinked_or_overstated_evidence(self):
        mutations = [
            ("unknown source", lambda p: p["observations"][0].update(sourceId="whatships:unknown")),
            ("pretend full review", lambda p: p["observations"][0].update(coverage="full-review")),
            ("measured cut rate", lambda p: p["observations"][0].update(cutFrequency=10)),
            ("invalid tag", lambda p: p["observations"][0].update(visualTags=["<script>"])),
            ("duplicate source", lambda p: p["observations"].append(copy.deepcopy(p["observations"][0]))),
            ("empty moments", lambda p: p["observations"][0].update(visibleMoments=[])),
            ("oversized note", lambda p: p["observations"][0].update(visibleMoments=["a" * 1000])),
            ("non-calendar-style date", lambda p: p.update(reviewedOn="2026-W45-2")),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                payload = fixture()
                mutate(payload)
                self.write(payload)
                with self.assertRaises(ValueError):
                    self.load()

    def test_rejects_invalid_json_duplicate_properties_and_symlinks(self):
        self.path.write_text('{"schemaVersion":"a","schemaVersion":"b"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            self.load()
        self.path.write_bytes(b" " * (256 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, "256 KiB"):
            self.load()
        self.path.unlink()
        self.path.symlink_to(ROOT / "research/whatships-motion-2026-11-10.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.load()

    def test_bundled_browser_studies_and_cli_filter(self):
        bundled = ROOT / "research/whatships-browser-observations-2026-11-10.json"
        data = load_source_references(ROOT / "research", ROOT / "research/whatships-index-2026-11-10.json")
        observations = load_browser_observations(data, bundled)
        self.assertEqual(len(observations["observations"]), 9)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["video-sources", "observations", "--source-id", "whatships:subvocal",
                         "--youtube-root", str(ROOT / "research"),
                         "--whatships", str(ROOT / "research/whatships-index-2026-11-10.json"),
                         "--observations", str(bundled)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["count"], 1)


if __name__ == "__main__":
    unittest.main()
