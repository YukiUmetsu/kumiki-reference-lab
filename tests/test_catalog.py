import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.catalog.store import (
    build_catalog_index, load_catalog, search_catalog,
)
from kumiki_reference_lab.catalog.validate import validate_technique
from kumiki_reference_lab.cli.app import main


ROOT = Path(__file__).resolve().parents[1] / "catalog/entries"


class CatalogTests(unittest.TestCase):
    def test_authored_entries_validate_and_remain_research_candidates(self):
        entries = load_catalog(ROOT)
        self.assertEqual(len(entries), 5)
        self.assertEqual([entry["id"] for entry in entries],
                         sorted(entry["id"] for entry in entries))
        self.assertTrue(all(entry["evidence"] == [] and
                            entry["status"] == "research-candidate" and
                            entry["kumiki"]["implementationStatus"] == "not-implemented"
                            for entry in entries))

    def test_story_first_search_finds_appropriate_category(self):
        matches = search_catalog(load_catalog(ROOT), "reveal material shape", limit=3)
        self.assertEqual(matches[0]["id"], "lighting.softbox-curvature-reveal")
        self.assertEqual(search_catalog(load_catalog(ROOT), "qxznonexistent"), [])
        with self.assertRaisesRegex(ValueError, "meaningful"):
            search_catalog(load_catalog(ROOT), "how to the")

    def test_index_is_deterministic_and_metadata_only(self):
        entries = load_catalog(ROOT)
        index = build_catalog_index(entries)
        self.assertEqual(index, build_catalog_index(list(reversed(entries))))
        self.assertEqual(len(index["entries"]), 5)
        self.assertNotIn("recipe", index["entries"][0])
        self.assertNotIn("evidence", index["entries"][0])
        self.assertEqual(len(index["entries"][0]["entrySha256"]), 64)
        json.dumps(index, sort_keys=True)

    def test_verification_requires_actual_evidence_and_human_approval(self):
        entry = copy.deepcopy(load_catalog(ROOT)[0])
        entry.pop("_entrySha256")
        entry["status"] = "verified"
        self.assertTrue(any("verified techniques require evidence" in error
                            for error in validate_technique(entry)))

    def test_bad_beats_and_unknown_fields_are_rejected(self):
        entry = copy.deepcopy(load_catalog(ROOT)[0])
        entry.pop("_entrySha256")
        entry["recipe"]["beats"][1]["start"] = 0.01
        entry["unsupportedMagicShader"] = True
        errors = validate_technique(entry)
        self.assertTrue(any("gap/overlap" in error for error in errors))
        self.assertTrue(any("unknown" in error for error in errors))

    def test_catalog_rejects_invalid_or_misplaced_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = root / "camera" / "bad.json"
            invalid.parent.mkdir()
            invalid.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                load_catalog(root)
            entry = copy.deepcopy(load_catalog(ROOT)[0])
            entry.pop("_entrySha256")
            invalid.write_text(json.dumps(entry), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expected catalog/entries"):
                load_catalog(root)

    def test_catalog_rejects_duplicate_json_properties(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "test.json"
            candidate.write_text('{"id":"first","id":"second"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON property"):
                load_catalog(root)

    def test_untrusted_types_are_validation_errors_not_tracebacks(self):
        entry = copy.deepcopy(load_catalog(ROOT)[0])
        entry.pop("_entrySha256")
        entry["category"] = {"bad": "type"}
        entry["parameters"][0]["name"] = []
        entry["status"] = ["research-candidate"]
        errors = validate_technique(entry)
        self.assertGreaterEqual(len(errors), 3)

    def test_cli_validates_searches_and_exports_index(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                self.assertEqual(main(["catalog", "validate", "--root", str(ROOT)]), 0)
                self.assertEqual(main(["catalog", "search", "explain scale",
                                       "--root", str(ROOT)]), 0)
                self.assertEqual(main(["catalog", "index", "--root", str(ROOT),
                                       "--out", str(output)]), 0)
                self.assertEqual(main(["catalog", "index", "--root", str(ROOT),
                                       "--out", str(output)]), 0)
            index = json.loads((output / "catalog-index.json").read_text())
            self.assertEqual(len(index["entries"]), 5)
            self.assertIn("valid", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
