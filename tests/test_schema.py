import json
import unittest
from pathlib import Path

from kumiki_reference_lab.contracts.source import SCHEMA_VERSION
from kumiki_reference_lab.contracts.analysis import (
    FRAME_TIMELINE_VERSION, SHOT_CANDIDATES_VERSION, CONTACT_SHEET_VERSION,
)


class SchemaTests(unittest.TestCase):
    def test_versioned_schema_is_valid_json_with_consistent_version(self):
        path = Path(__file__).resolve().parents[1] / "schemas/v1/source-manifest.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schemaVersion"]["const"], SCHEMA_VERSION)
        self.assertEqual(set(schema["required"]),
                         {"schemaVersion", "source", "video", "timestamps", "analysis"})
        self.assertEqual(schema["properties"]["timestamps"]["properties"]
                         ["originalFramePtsExtracted"]["const"], False)

    def test_analysis_schema_versions(self):
        root = Path(__file__).resolve().parents[1] / "schemas/v1"
        for name, version in (("frame-timeline", FRAME_TIMELINE_VERSION),
                              ("shot-candidates", SHOT_CANDIDATES_VERSION),
                              ("contact-sheet", CONTACT_SHEET_VERSION)):
            schema = json.loads((root / (name + ".schema.json")).read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["schemaVersion"]["const"], version)


if __name__ == "__main__":
    unittest.main()
