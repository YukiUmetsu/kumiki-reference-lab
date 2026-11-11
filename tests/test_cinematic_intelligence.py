"""Low-compute shot/motion/audio/OCR/recipe/catalog regression checks."""
from __future__ import annotations

import io
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kumiki_reference_lab.pipeline.agent_frame_review import (
    finalize_frame_workspace, scan_frames,
)
from kumiki_reference_lab.pipeline.cinematic_catalog import (
    build_cinematic_catalog, search_cinematic_catalog,
)
from kumiki_reference_lab.pipeline.cinematic_insights import (
    analyze_cinematic_workspace, derive_audio_visual_hypotheses,
    derive_kumiki_recipe_proposals, derive_technique_hypotheses,
)
from kumiki_reference_lab.pipeline.online_audio_cues import (
    _rms_dbfs, build_online_audio_cues,
)
from kumiki_reference_lab.pipeline.screen_text import parse_tesseract_tsv
from kumiki_reference_lab.pipeline.seeded_subjects import (
    validate_region_seeds, build_seeded_region_tracks, screen_relationship_proxies,
)
from kumiki_reference_lab.pipeline.shot_intelligence import (
    build_shot_intelligence, prioritized_frame_plan,
)
from kumiki_reference_lab.pipeline.temporal_motion import (
    _pair_plan, build_temporal_motion,
)


def evidence(size: int = 24, cut: int = 12) -> dict:
    frames = []
    for i in range(size):
        bright = i >= cut
        delta = 0.65 if i == cut else .015
        frames.append({
            "frameIndex": i, "decodedPts": i * 100,
            "decodedSeconds": i / 10,
            "appearance": {
                "meanRgb": ([.8, .8, .8] if bright else [.25, .25, .25]),
                "displayLumaProxy": .8 if bright else .25,
                "saturationProxy": .1 if bright else .25,
                "brightPixelFraction": .7 if bright else .1,
                "darkPixelFraction": .1 if bright else .6,
            },
            "changeFromPrevious": None if i == 0 else {
                "meanPixelDelta": delta,
                "changedPixelFraction": 0.8 if i == cut else .04,
            },
            "cutCandidate": i == cut,
        })
    return {
        "schemaVersion": "kumiki.online-frame-evidence.v1",
        "sourceSha256": "a" * 64, "frameCount": size,
        "frames": frames, "cutCandidateFrameIndices": [cut],
        "video": {"width": 160, "height": 90},
    }


def fixture(root: Path) -> Path:
    (root / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    identifier = "example-abc"
    numeric = evidence()
    storage = root / "research" / "analysis" / "online-videos"
    storage.mkdir(parents=True)
    (storage / f"{identifier}.json").write_text(json.dumps({
        "schemaVersion": "kumiki.online-video-reference.v1",
        "id": identifier, "numericEvidence": numeric,
        "audioEvidence": {
            "schemaVersion": "kumiki.online-audio-cues.v1",
            "status": "measured-decoded-audio-envelope",
            "transientCandidates": [
                {"decodedOffsetMs": 1200, "riseDb": 15},
            ], "frames": [],
        },
    }))
    workspace = root / "workspace" / "frame-review" / identifier
    (workspace / "frames").mkdir(parents=True)
    for i in range(24):
        (workspace / "frames" / f"frame-{i:06d}.png").write_bytes(
            b"\x89PNG\r\n\x1a\npreview-test-bytes")
    finalize_frame_workspace(
        workspace, study_id=identifier,
        watch_url="https://example.org/example",
        numeric=numeric, preview_width=160, preview_height=90)
    return workspace


class ShotIntelligenceTests(unittest.TestCase):
    def test_detects_shot_boundary_and_stable_representative_plan(self):
        shots = build_shot_intelligence(evidence())
        self.assertEqual(shots["shotCount"], 2)
        self.assertEqual(shots["candidateCutFrameIndices"], [12])
        self.assertEqual([(s["startFrameIndex"], s["endFrameIndexExclusive"])
                          for s in shots["shots"]], [(0, 12), (12, 24)])
        self.assertEqual(shots["shots"][0]["imageEvidence"]["displayPaletteProxy"],
                         "dark")
        self.assertEqual(shots["shots"][1]["imageEvidence"]["displayPaletteProxy"],
                         "bright")
        plan = prioritized_frame_plan(shots, max_frames=4)
        self.assertEqual([task["frameIndex"] for task in plan["frameTasks"]][:2],
                         [0, 12])
        self.assertEqual(len(plan["frameTasks"]), 4)

    def test_flash_too_short_to_create_spurious_shot(self):
        numeric = evidence()
        numeric["frames"][2]["changeFromPrevious"]["meanPixelDelta"] = .9
        numeric["frames"][3]["changeFromPrevious"]["meanPixelDelta"] = .9
        self.assertEqual(build_shot_intelligence(numeric)["shotCount"], 2)

    def test_rejects_bad_timestamps_and_nan(self):
        numeric = evidence()
        numeric["frames"][8]["decodedSeconds"] = .2
        with self.assertRaises(ValueError):
            build_shot_intelligence(numeric)
        numeric = evidence()
        numeric["frames"][7]["appearance"]["displayLumaProxy"] = math.nan
        with self.assertRaises(ValueError):
            build_shot_intelligence(numeric)

    def test_flow_pair_plan_cannot_cross_candidate_cut(self):
        shots = build_shot_intelligence(evidence())
        pairs = _pair_plan(shots["shots"], max_pairs=12)
        self.assertTrue(pairs)
        self.assertLessEqual(len(pairs), 12)
        self.assertTrue(all((i < 12 and j < 12) or (i >= 12 and j >= 12)
                            for _, i, j in pairs))


class ScreenTextTests(unittest.TestCase):
    def test_bounded_tesseract_word_grouping(self):
        tsv = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\t"
               "top\twidth\theight\tconf\ttext\n"
               "5\t1\t1\t1\t1\t1\t4\t8\t30\t10\t92\tHello\n"
               "5\t1\t1\t1\t1\t2\t36\t8\t28\t10\t91\tworld\n"
               "5\t1\t2\t1\t1\t1\t4\t8\t30\t10\t-1\tbad\n")
        result = parse_tesseract_tsv(tsv, width=160, height=90)
        self.assertEqual(result[0]["visibleText"], "Hello world")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["boxNormalized"][0], .025)


class AudioTests(unittest.TestCase):
    def test_rms_pcm_bounds(self):
        self.assertEqual(_rms_dbfs(b"\x00\x00" * 800)[0], -120)
        self.assertGreater(_rms_dbfs(struct.pack("<h", 10000) * 800)[0], -15)

    @patch("kumiki_reference_lab.pipeline.online_audio_cues.probe_media")
    def test_no_audio_not_assumed_silence(self, probe):
        probe.return_value = {"streams": [{"codec_type": "video", "index": 0}]}
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.write_bytes(b"local")
            result = build_online_audio_cues(source)
        self.assertEqual(result["status"], "no-audio-stream")
        self.assertEqual(result["frames"], [])

    @patch("kumiki_reference_lab.pipeline.online_audio_cues.subprocess.Popen")
    @patch("kumiki_reference_lab.pipeline.online_audio_cues.probe_media")
    def test_level_attack_does_not_claim_music_beat(self, probe, popen):
        probe.return_value = {"streams": [{"codec_type": "audio", "index": 1}]}
        pcm = (struct.pack("<h", 20) * 800 * 5 +
               struct.pack("<h", 26000) * 800 +
               struct.pack("<h", 1000) * 800 * 2)
        class Process:
            def __init__(self):
                self.stdout = io.BytesIO(pcm)
            def wait(self, timeout=None):
                return 0
            def poll(self):
                return 0
        popen.return_value = Process()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            source.write_bytes(b"local")
            result = build_online_audio_cues(source)
        self.assertEqual(result["status"], "measured-decoded-audio-envelope")
        self.assertTrue(result["transientCandidates"])
        self.assertEqual(result["audioVideoClockStatus"],
                         "not-independently-aligned")

    def test_candidate_cut_proximity_is_unverified(self):
        shots = build_shot_intelligence(evidence())
        report = derive_audio_visual_hypotheses(shots, {
            "status": "measured-decoded-audio-envelope",
            "transientCandidates": [{"decodedOffsetMs": 1200}],
        })
        self.assertEqual(report["candidates"][0]["shotId"], "shot-0002")
        self.assertIn("not-independently", report["clockRelation"])


class CinematicIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = fixture(self.root)

    def test_insights_and_kumiki_recipe_and_catalog_search(self):
        notes = {
            "schemaVersion": "kumiki.agent-frame-notes.v1",
            "sourceSha256": "a" * 64,
            "frameCount": 24,
            "observations": [
                {"id": "note1", "startFrameIndex": 3,
                 "endFrameIndex": 7, "category": "visual-style",
                 "description": "A paper-cut layer appears to slide.",
                 "confidence": "low"},
            ],
        }
        notes_file = (self.root / "research" / "analysis" /
                      "online-videos" / "example-abc.frame-notes.json")
        notes_file.write_text(json.dumps(notes))
        result = analyze_cinematic_workspace(
            self.workspace, motion=False, ocr=False)
        document = json.loads(result.read_text())
        self.assertEqual(document["shotIntelligence"]["shotCount"], 2)
        self.assertEqual(document["temporalMotion"]["status"], "not-requested")
        self.assertTrue(document["kumikiRecipeProposals"])
        self.assertTrue(any(x["techniqueId"] == "style.paper-cut-layered-motion"
                            for x in document["techniqueHypotheses"]))
        self.assertFalse(document["kumikiRecipeProposals"][0]["visualStartingPoint"]
                         ["targetComponentApiVerified"])
        catalog = build_cinematic_catalog(result.parent)
        matched = search_cinematic_catalog(catalog, query="paper cut")
        self.assertTrue(matched["techniques"])
        self.assertEqual(matched["techniques"][0]["distinctAnalyzedReferenceCount"], 1)
        with self.assertRaisesRegex(ValueError, "already exist"):
            analyze_cinematic_workspace(self.workspace, motion=False, ocr=False)

    def test_shot_aware_frame_navigation_and_skipped_cv2(self):
        from kumiki_reference_lab.pipeline.agent_frame_review import next_frame
        self.assertEqual(next_frame(self.workspace, mode="shots")["frameIndex"], 0)
        self.assertEqual(next_frame(self.workspace, after=0,
                                    mode="shots")["frameIndex"], 5)
        with patch.dict(sys.modules, {"cv2": None}):
            motion = build_temporal_motion(
                self.workspace, build_shot_intelligence(evidence()))
        self.assertEqual(motion["status"], "not-run-install-pip-extra-dense")

    def test_bounded_seeded_subjects_and_relationship_geometry(self):
        seed = {
            "schemaVersion": "kumiki.online-region-seeds.v1",
            "sourceSha256": "a" * 64,
            "subjects": [{
                "id": "subject-one", "kind": "animated-character",
                "label": "Original character A", "startFrameIndex": 0,
                "boxNormalized": [.1, .1, .4, .4],
            }],
        }
        self.assertEqual(len(validate_region_seeds(
            seed, source_sha="a" * 64, frame_count=24)), 1)
        path = self.root / "roi-seeds.json"
        path.write_text(json.dumps(seed))
        with patch.dict(sys.modules, {"cv2": None}):
            result = build_seeded_region_tracks(
                self.workspace, build_shot_intelligence(evidence()), path)
        self.assertEqual(result["status"], "not-run-install-pip-extra-dense")
        seed["subjects"][0]["boxNormalized"] = [.9, .1, .4, .4]
        with self.assertRaises(ValueError):
            validate_region_seeds(seed, source_sha="a" * 64, frame_count=24)
        track_a = {
            "id": "one", "observations": [
                {"frameIndex": 0, "boxNormalized": [.1, .2, .2, .2]},
                {"frameIndex": 1, "boxNormalized": [.25, .2, .2, .2]},
            ],
        }
        track_b = {
            "id": "two", "observations": [
                {"frameIndex": 0, "boxNormalized": [.7, .2, .2, .2]},
                {"frameIndex": 1, "boxNormalized": [.6, .2, .2, .2]},
            ],
        }
        proxy = screen_relationship_proxies([track_a, track_b])
        self.assertEqual(proxy[0]["screenDistanceTrend"], "closer")
        self.assertEqual(proxy[0]["coVisibleSampleCount"], 2)
        self.assertIn("not-a-social-interaction", proxy[0]["status"])

    def test_catalog_rejects_duplicate_content_identity(self):
        first = analyze_cinematic_workspace(self.workspace, motion=False)
        duplicate = first.parent / "newid-other.insights.json"
        obj = json.loads(first.read_text())
        obj["id"] = "newid-other"
        duplicate.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError, "duplicate source SHA"):
            build_cinematic_catalog(first.parent)


if __name__ == "__main__":
    unittest.main()
