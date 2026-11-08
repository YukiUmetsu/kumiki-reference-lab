import json
import unittest
from pathlib import Path

from kumiki_reference_lab.contracts.source import SCHEMA_VERSION
from kumiki_reference_lab.contracts.analysis import (
    FRAME_TIMELINE_VERSION, SHOT_CANDIDATES_VERSION, CONTACT_SHEET_VERSION,
    IMAGE_MOTION_VERSION, ROI_TRACK_VERSION, ANALYSIS_RUN_VERSION, SPARSE_FLOW_VERSION,
    APPEARANCE_VERSION, APPEARANCE_COMPARISON_VERSION, FRAME_COMPARISON_VERSION,
    TECHNIQUE_PROPOSALS_VERSION,
    TECHNIQUE_REVIEW_VERSION,
    SHOT_EVIDENCE_VERSION,
    REFERENCE_STUDY_VERSION,
    REVIEW_NOTES_VERSION,
    SHOT_GALLERY_VERSION,
    AUDIO_TIMELINE_VERSION,
    AUDIO_LEVELS_VERSION,
    AUDIO_ONSETS_VERSION,
    AV_CUT_EVIDENCE_VERSION,
    EDIT_RHYTHM_VERSION,
    TIMELINE_REVIEW_VERSION,
    TIMELINE_REVIEW_V1_VERSION,
    REFERENCE_STUDY_V1_VERSION,
    REFERENCE_STUDY_V2_VERSION,
    REFERENCE_STUDY_V3_VERSION,
    REFERENCE_STUDY_V4_VERSION,
)
from kumiki_reference_lab.catalog.validate import TECHNIQUE_SCHEMA_VERSION, INDEX_SCHEMA_VERSION
from kumiki_reference_lab.integrations.kumiki.film_handoff import FILM_HANDOFF_VERSION
from kumiki_reference_lab.integrations.kumiki.film_map_review import VERSION as FILM_MAP_REVIEW_VERSION


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
                              ("contact-sheet", CONTACT_SHEET_VERSION),
                              ("image-motion", IMAGE_MOTION_VERSION),
                              ("sparse-flow", SPARSE_FLOW_VERSION),
                              ("appearance", APPEARANCE_VERSION),
                              ("appearance-comparison", APPEARANCE_COMPARISON_VERSION),
                              ("frame-comparison", FRAME_COMPARISON_VERSION),
                              ("technique-proposals", TECHNIQUE_PROPOSALS_VERSION),
                              ("technique-review", TECHNIQUE_REVIEW_VERSION),
                              ("shot-evidence", SHOT_EVIDENCE_VERSION),
                              ("review-notes", REVIEW_NOTES_VERSION),
                              ("shot-gallery", SHOT_GALLERY_VERSION),
                              ("audio-timeline", AUDIO_TIMELINE_VERSION),
                              ("audio-levels", AUDIO_LEVELS_VERSION),
                              ("audio-onsets", AUDIO_ONSETS_VERSION),
                              ("av-cut-evidence", AV_CUT_EVIDENCE_VERSION),
                              ("edit-rhythm", EDIT_RHYTHM_VERSION),
                              ("roi-track", ROI_TRACK_VERSION),
                              ("analysis-run", ANALYSIS_RUN_VERSION)):
            schema = json.loads((root / (name + ".schema.json")).read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["schemaVersion"]["const"], version)
        legacy = json.loads((root / "reference-study.schema.json").read_text())
        self.assertEqual(legacy["properties"]["schemaVersion"]["const"],
                         REFERENCE_STUDY_V1_VERSION)
        updated = json.loads((root.parent / "v2/reference-study.schema.json").read_text())
        self.assertEqual(updated["properties"]["schemaVersion"]["const"],
                         REFERENCE_STUDY_V2_VERSION)
        v3 = json.loads((root.parent / "v3/reference-study.schema.json").read_text())
        self.assertEqual(v3["properties"]["schemaVersion"]["const"],
                         REFERENCE_STUDY_V3_VERSION)
        v4 = json.loads((root.parent / "v4/reference-study.schema.json").read_text())
        self.assertEqual(v4["properties"]["schemaVersion"]["const"],
                         REFERENCE_STUDY_V4_VERSION)
        current = json.loads((root.parent / "v5/reference-study.schema.json").read_text())
        self.assertEqual(current["properties"]["schemaVersion"]["const"],
                         REFERENCE_STUDY_VERSION)
        timeline_v1 = json.loads((root / "timeline-review.schema.json").read_text())
        self.assertEqual(timeline_v1["properties"]["schemaVersion"]["const"],
                         TIMELINE_REVIEW_V1_VERSION)
        timeline_v2 = json.loads((root.parent / "v2/timeline-review.schema.json").read_text())
        self.assertEqual(timeline_v2["properties"]["schemaVersion"]["const"],
                         TIMELINE_REVIEW_VERSION)
        handoff = json.loads((root / "film-handoff.schema.json").read_text())
        self.assertEqual(handoff["properties"]["schemaVersion"]["const"],
                         FILM_HANDOFF_VERSION)
        film_review = json.loads((root / "film-map-review.schema.json").read_text())
        self.assertEqual(film_review["properties"]["schemaVersion"]["const"],
                         FILM_MAP_REVIEW_VERSION)
        self.assertEqual(film_review["properties"]["qualityVerdict"]["const"],
                         "not-performed")

    def test_catalog_schema_versions(self):
        root = Path(__file__).resolve().parents[1] / "schemas/v1"
        for name, version in (("cinematic-technique", TECHNIQUE_SCHEMA_VERSION),
                              ("cinematic-techniques-index", INDEX_SCHEMA_VERSION)):
            schema = json.loads((root / (name + ".schema.json")).read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["schemaVersion"]["const"], version)


if __name__ == "__main__":
    unittest.main()
