import importlib.util
import json
import unittest
from pathlib import Path

from kumiki_reference_lab.contracts.source import SCHEMA_VERSION
from kumiki_reference_lab.contracts.analysis import (
    FRAME_TIMELINE_VERSION, SHOT_CANDIDATES_VERSION, CONTACT_SHEET_VERSION,
    IMAGE_MOTION_VERSION, ROI_TRACK_VERSION, ANALYSIS_RUN_VERSION, SPARSE_FLOW_VERSION,
    ROI_TRACK_RESEED_VERSION, ANALYSIS_RUN_RESEED_VERSION, DENSE_FLOW_VERSION,
    ROI_REVIEW_VERSION,
    SPARSE_FLOW_REVIEW_VERSION,
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
from kumiki_reference_lab.integrations.kumiki.film_feedback import VERSION as FILM_FEEDBACK_VERSION


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
                              ("dense-flow", DENSE_FLOW_VERSION),
                              ("sparse-flow-review", SPARSE_FLOW_REVIEW_VERSION),
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
                              ("roi-review", ROI_REVIEW_VERSION),
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
        feedback = json.loads((root / "film-map-feedback.schema.json").read_text())
        self.assertEqual(feedback["properties"]["schemaVersion"]["const"],
                         FILM_FEEDBACK_VERSION)
        self.assertEqual(feedback["properties"]["reviewStatus"]["const"], "draft")

    def test_catalog_schema_versions(self):
        root = Path(__file__).resolve().parents[1] / "schemas/v1"
        for name, version in (("cinematic-technique", TECHNIQUE_SCHEMA_VERSION),
                              ("cinematic-techniques-index", INDEX_SCHEMA_VERSION)):
            schema = json.loads((root / (name + ".schema.json")).read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["schemaVersion"]["const"], version)

    def test_manual_roi_reseed_has_v2_contract_while_v1_remains_strict(self):
        root = Path(__file__).resolve().parents[1]
        roi = json.loads((root / "schemas/v1/roi-track.schema.json").read_text())
        run = json.loads((root / "schemas/v1/analysis-run.schema.json").read_text())
        roi_v2 = json.loads((root / "schemas/v2/roi-track.schema.json").read_text())
        run_v2 = json.loads((root / "schemas/v2/analysis-run.schema.json").read_text())
        example = json.loads((root / "examples/roi-reseeds.example.json").read_text())
        self.assertEqual(roi["properties"]["schemaVersion"]["const"], ROI_TRACK_VERSION)
        self.assertNotIn("manualReseeds", roi["properties"]["analyzer"]["properties"])
        self.assertNotIn("segmentIndex", roi["properties"]["observations"]["items"]["properties"])
        self.assertEqual(roi_v2["properties"]["schemaVersion"]["const"], ROI_TRACK_RESEED_VERSION)
        self.assertIn("manualReseeds", roi_v2["properties"]["analyzer"]["required"])
        self.assertIn("segmentIndex", roi_v2["properties"]["observations"]["items"]["required"])
        self.assertIn("manual-reseed", roi_v2["properties"]["observations"]["items"]
                      ["properties"]["status"]["enum"])
        self.assertNotIn("roiReseeds", run["properties"]["settings"]["properties"])
        self.assertEqual(run_v2["properties"]["schemaVersion"]["const"], ANALYSIS_RUN_RESEED_VERSION)
        self.assertIn("roiReseeds", run_v2["properties"]["settings"]["required"])
        self.assertEqual(example[0]["sourcePts"], 700)
        self.assertEqual(len(example), 2)

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "jsonschema unavailable")
    def test_analysis_run_schemas_accept_combined_optional_motion_settings(self):
        from jsonschema import Draft202012Validator, ValidationError

        root = Path(__file__).resolve().parents[1] / "schemas"
        base = {
            "sourceSha256": "0" * 64, "streamIndex": 0, "seconds": 2,
            "thumbnails": 4, "motion": False, "roi": [0.2, 0.2, 0.2, 0.2],
            "samples": 12, "width": 160, "height": 90,
            "cutThreshold": 0.95, "ffmpeg": "ffmpeg", "ffprobe": "ffprobe",
            "rightsStatus": "review-required",
            "sparseFlow": True, "sparseSamples": 8, "sparsePoints": 40,
            "sparseRadius": 8, "sparseCorrelation": 0.68,
            "sparsePyramidLevels": 2, "sparseSubpixelRefinement": True,
            "sparseSubpixelReverseCheck": True, "sparseQuadrantConsistency": True,
            "sparseProjectiveHypotheses": True, "sparseModelValidation": True,
            "sparseTrackletMotionConsistency": True,
            "sparseTrackletAppearanceConsistency": True,
            "denseFlow": True, "denseSamples": 8, "denseGridStep": 12,
            "versions": {"run": "kumiki.analysis-run.v1", "source": "v1",
                         "frames": "v1", "cuts": "v1", "contact": "v1",
                         "motion": "v1", "roi": "kumiki.roi-track.v1",
                         "sparseFlow": "kumiki.sparse-flow.v1",
                         "denseFlow": "kumiki.dense-flow.v1"},
        }
        for version in (1, 2):
            with self.subTest(version=version):
                schema = json.loads((root / f"v{version}/analysis-run.schema.json").read_text())
                Draft202012Validator.check_schema(schema)
                settings = json.loads(json.dumps(base))
                if version == 2:
                    settings["roiReseeds"] = [{"sourcePts": 700, "box": [0.2, 0.2, 0.2, 0.2]}]
                    settings["versions"]["run"] = "kumiki.analysis-run.v2"
                    settings["versions"]["roi"] = "kumiki.roi-track.v2"
                report = {
                    "schemaVersion": f"kumiki.analysis-run.v{version}",
                    "settings": settings,
                    "sourceTimebase": {"numerator": 1, "denominator": 1000},
                    "coverage": "bounded-from-start-not-necessarily-full-video",
                    "artifacts": {name: f"{name}.json" for name in ("inspect", "frames", "cuts", "contactSheet")},
                    "files": [{"path": f"file-{i}", "sha256": "0" * 64} for i in range(7)],
                    "catalogProposals": [], "interpretationStatus": "not-performed",
                }
                validator = Draft202012Validator(schema)
                validator.validate(report)
                settings["sparseLkRefinement"] = True
                settings.pop("sparseSubpixelRefinement")
                settings.pop("sparseSubpixelReverseCheck")
                validator.validate(report)
                settings["unexpectedSetting"] = True
                with self.assertRaises(ValidationError):
                    validator.validate(report)


if __name__ == "__main__":
    unittest.main()
