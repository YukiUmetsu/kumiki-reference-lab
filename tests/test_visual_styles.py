"""Visual style catalog keeps creator attribution separate from view counts and frame review."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.visual_styles import (
    load_visual_styles, search_visual_styles, style_family_counts, validate_visual_styles,
)
from kumiki_reference_lab.cli.app import main


ROOT = Path(__file__).resolve().parents[1] / "research/visual-styles.v1.json"


class VisualStyleTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_visual_styles(ROOT)

    def test_curated_styles_have_source_attribution_and_no_fake_audience_proof(self):
        self.assertEqual(len(self.catalog["entries"]), 12)
        self.assertEqual(len(style_family_counts(self.catalog)), 6)
        self.assertEqual(len({e["id"] for e in self.catalog["entries"]}), 12)
        self.assertEqual(len({e["creatorSource"]["url"] for e in self.catalog["entries"]}), 12)
        self.assertTrue(all(e["audienceStatus"] == "not-measured-for-this-work"
                            and e["reviewStatus"] == "source-described-not-frame-reviewed"
                            and e["rights"] == "inspiration-only" for e in self.catalog["entries"]))
        paper = search_visual_styles(self.catalog, family="paper-and-collage")
        self.assertEqual({e["id"] for e in paper}, {"layered-paper-cut", "paper-cut-look-in-3d"})
        self.assertEqual(search_visual_styles(self.catalog, "halftone")[0]["id"], "comic-halftone-3d")
        self.assertEqual(search_visual_styles(self.catalog, "2.5D camera")[0]["id"],
                         "print-texture-2point5d")

    def test_validation_fails_closed_for_malformed_values(self):
        for name, mutation in (
            ("duplicate", lambda c: c["entries"].append(copy.deepcopy(c["entries"][0]))),
            ("rights", lambda c: c["entries"][0].update(rights="free-to-redistribute")),
            ("audience", lambda c: c["entries"][0].update(audienceStatus="viral-confirmed")),
            ("frame", lambda c: c["entries"][0].update(reviewStatus="frame-reviewed")),
            ("url", lambda c: c["entries"][0]["creatorSource"].update(url="https://a@bad.example/")),
            ("schema", lambda c: c.update(schemaVersion="v2")),
            ("family", lambda c: c["entries"][0].update(family=[])),
            ("source", lambda c: c["entries"][0]["creatorSource"].update(sourceType=[])),
            ("unknown", lambda c: c["entries"][0].update(viewCount=100000)),
        ):
            with self.subTest(name=name):
                collection = copy.deepcopy(self.catalog)
                mutation(collection)
                self.assertTrue(validate_visual_styles(collection))

    def test_cli_and_untrusted_json_guards(self):
        for action, count in ((["validate"], 12), (["list", "--family", "stylized-3d"], 3),
                              (["search", "paper cut"], 2)):
            with self.subTest(action=action):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(main(["visual-styles", *action, "--root", str(ROOT)]), 0)
                payload = json.loads(out.getvalue())
                self.assertEqual(payload.get("entryCount", payload.get("count")), count)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "styles.json"
            path.write_text('{"schemaVersion":"x","schemaVersion":"y"}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_visual_styles(path)
            alias = Path(temp) / "alias.json"
            alias.symlink_to(ROOT)
            with self.assertRaisesRegex(ValueError, "regular"):
                load_visual_styles(alias)
