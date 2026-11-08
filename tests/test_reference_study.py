import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.study import study_reference
from kumiki_reference_lab.pipeline.study import _verify_study
from kumiki_reference_lab.pipeline.analyze import _file_records
from kumiki_reference_lab.contracts.analysis import (
    REFERENCE_STUDY_V1_VERSION, REFERENCE_STUDY_V2_VERSION,
    REFERENCE_STUDY_V3_VERSION,
    REFERENCE_STUDY_V4_VERSION,
)
from kumiki_reference_lab.core.artifacts import write_json_artifact


CATALOG = Path(__file__).resolve().parents[1] / "catalog" / "entries"


class StudyCommandTests(unittest.TestCase):
    def test_cli_parses_study_command(self):
        args = build_parser().parse_args(["study-reference", "source.mp4", "--out", "runs"])
        self.assertEqual(args.command, "study-reference")
        self.assertEqual(args.max_seconds, 10)

    def test_invalid_study_budget_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "missing"
            with self.assertRaisesRegex(ValueError, "study seconds"):
                study_reference(Path("not-a-file"), output, seconds=50,
                                catalog_root=CATALOG)
            self.assertFalse(output.exists())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                     importlib.util.find_spec("numpy"),
                     "FFmpeg/FFprobe and NumPy required")
class StudyReferenceIntegrationTests(unittest.TestCase):
    def test_timeline_stage_failure_does_not_publish_partial_study(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0)
            output = root / "studies"
            with patch("kumiki_reference_lab.pipeline.study.build_timeline_view",
                       side_effect=RuntimeError("audio measurement failed")):
                with self.assertRaisesRegex(RuntimeError, "audio measurement failed"):
                    study_reference(source, output, catalog_root=CATALOG,
                                    seconds=2, thumbnails=4)
            self.assertEqual(list(output.glob("study-*")), [])
            self.assertEqual(len(list(output.glob("analysis/analysis-*"))), 1)
            overview = study_reference(source, output, catalog_root=CATALOG,
                                       seconds=2, thumbnails=4)
            self.assertTrue(overview.is_file())

    def test_audio_track_is_included_when_source_has_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sound.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000:duration=1",
                "-shortest", "-c:v", "ffv1", "-c:a", "pcm_s16le", str(source),
            ], capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0,
                             process.stderr.decode(errors="replace"))
            overview = study_reference(source, root / "studies", catalog_root=CATALOG,
                                       seconds=2, thumbnails=4)
            manifest = json.loads((overview.parent / "study-manifest.json").read_text())
            timeline = overview.parent / manifest["artifacts"]["timelineView"]
            av = json.loads((timeline.parent / "av-cut-evidence.json").read_text())
            onsets = json.loads((timeline.parent / "audio-onsets.json").read_text())
            self.assertEqual(av["status"], "candidate-cross-stream-pts-association")
            self.assertEqual(onsets["status"], "source-pts-aligned-level-attack-candidates")
            self.assertIn("Audio near cuts", timeline.read_text())

    def test_one_command_publishes_complete_reusable_gallery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
            output = root / "studies"
            gallery = study_reference(source, output, catalog_root=CATALOG,
                                      seconds=2, thumbnails=4)
            self.assertTrue(gallery.is_file())
            manifest = gallery.parent / "study-manifest.json"
            report = json.loads(manifest.read_text())
            self.assertEqual(report["schemaVersion"], "kumiki.reference-study.v5")
            self.assertEqual(report["humanReviewStatus"], "unreviewed")
            self.assertEqual(report["qualityVerdict"], "not-performed")
            self.assertTrue((manifest.parent / report["artifacts"]["shotEvidence"]).is_file())
            self.assertTrue((manifest.parent / report["artifacts"]["editRhythm"]).is_file())
            self.assertTrue((manifest.parent / report["artifacts"]["techniqueProposals"]).is_file())
            self.assertTrue((manifest.parent / report["artifacts"]["shotGallery"]).is_file())
            self.assertTrue((manifest.parent / report["artifacts"]["reviewGallery"]).is_file())
            timeline = manifest.parent / report["artifacts"]["timelineView"]
            self.assertTrue(timeline.is_file())
            self.assertIn('role="img"', timeline.read_text())
            self.assertIn("No audio stream", timeline.read_text())
            self.assertEqual(
                json.loads((timeline.parent / "av-cut-evidence.json").read_text())["status"],
                "no-audio-stream",
            )
            self.assertEqual(
                json.loads((timeline.parent / "audio-onsets.json").read_text())["status"],
                "no-audio-stream",
            )
            self.assertEqual(report["settings"]["timelineWindowMs"], 400)
            self.assertIn("Shot storyboard", gallery.read_text())
            self.assertIn("Edit rhythm", gallery.read_text())
            self.assertIn("Evidence timeline", gallery.read_text())
            rhythm = json.loads((manifest.parent / "edit-rhythm.json").read_text())
            self.assertEqual(rhythm["schemaVersion"], "kumiki.edit-rhythm.v1")
            self.assertEqual(rhythm["observedInterCutIntervalCount"], 0)
            self.assertEqual(study_reference(source, output, catalog_root=CATALOG,
                                             seconds=2, thumbnails=4), gallery)
            # The nested timeline is part of the immutable study inventory.
            timeline.write_text("modified", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing, altered or untracked"):
                study_reference(source, output, catalog_root=CATALOG,
                                seconds=2, thumbnails=4)
            self.assertEqual(len(list(output.glob("analysis/analysis-*"))), 1)

    def test_v1_through_v4_studies_remain_readable_after_v5_upgrade(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mkv"
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0)
            output = root / "runs"
            overview = study_reference(source, output, catalog_root=CATALOG,
                                       seconds=2, thumbnails=4)
            study = json.loads((overview.parent / "study-manifest.json").read_text())
            legacy = output / "study-legacy-example"
            legacy.mkdir()
            shutil.copy2(overview.parent / "technique-proposals.json", legacy)
            shutil.copy2(overview.parent / "shot-evidence.json", legacy)
            gallery_source = overview.parent / study["artifacts"]["reviewGallery"]
            gallery_destination = legacy / study["artifacts"]["reviewGallery"]
            shutil.copytree(gallery_source.parent, gallery_destination.parent)
            timeline_keys = {"timelineStyleRevision", "timelineWindowMs",
                             "timelineMaxAudioFrames", "timelineOnsetMinRiseDb",
                             "timelineOnsetMinPeakDbFs", "timelineOnsetCooldownMs"}
            old_settings = {k: v for k, v in study["settings"].items()
                            if k != "editRhythmSha256" and k not in timeline_keys}
            old_settings["studyVersion"] = REFERENCE_STUDY_V1_VERSION
            old_study = {
                "schemaVersion": REFERENCE_STUDY_V1_VERSION,
                "settings": old_settings,
                "artifacts": {k: study["artifacts"][k] for k in (
                    "techniqueProposals", "shotEvidence", "reviewGallery")},
                "files": _file_records(legacy),
                "humanReviewStatus": "unreviewed",
                "qualityVerdict": "not-performed",
            }
            write_json_artifact(legacy, "study-manifest.json", old_study)
            self.assertEqual(_verify_study(legacy, old_settings), gallery_destination)

            v2 = output / "study-v2-legacy-example"
            v2.mkdir()
            for name in ("technique-proposals.json", "shot-evidence.json", "index.html"):
                shutil.copy2(overview.parent / name, v2)
            for key in ("reviewGallery", "shotGallery"):
                source_html = overview.parent / study["artifacts"][key]
                destination_html = v2 / study["artifacts"][key]
                shutil.copytree(source_html.parent, destination_html.parent)
            v2_settings = old_settings | {"studyVersion": REFERENCE_STUDY_V2_VERSION}
            v2_study = {
                "schemaVersion": REFERENCE_STUDY_V2_VERSION,
                "settings": v2_settings,
                "artifacts": {k: v for k, v in study["artifacts"].items()
                              if k not in ("editRhythm", "timelineView")},
                "files": _file_records(v2),
                "humanReviewStatus": "unreviewed",
                "qualityVerdict": "not-performed",
            }
            write_json_artifact(v2, "study-manifest.json", v2_study)
            self.assertEqual(_verify_study(v2, v2_settings), v2 / "index.html")

            v3 = output / "study-v3-legacy-example"
            v3.mkdir()
            for name in ("technique-proposals.json", "shot-evidence.json",
                         "edit-rhythm.json", "index.html"):
                shutil.copy2(overview.parent / name, v3)
            for key in ("reviewGallery", "shotGallery"):
                source_html = overview.parent / study["artifacts"][key]
                destination_html = v3 / study["artifacts"][key]
                shutil.copytree(source_html.parent, destination_html.parent)
            v3_settings = {k: v for k, v in study["settings"].items()
                           if k not in timeline_keys}
            v3_settings["studyVersion"] = REFERENCE_STUDY_V3_VERSION
            v3_study = {
                "schemaVersion": REFERENCE_STUDY_V3_VERSION,
                "settings": v3_settings,
                "artifacts": {k: v for k, v in study["artifacts"].items()
                              if k != "timelineView"},
                "files": _file_records(v3),
                "humanReviewStatus": "unreviewed",
                "qualityVerdict": "not-performed",
            }
            write_json_artifact(v3, "study-manifest.json", v3_study)
            self.assertEqual(_verify_study(v3, v3_settings), v3 / "index.html")

            v4 = output / "study-v4-legacy-example"
            v4.mkdir()
            for name in ("technique-proposals.json", "shot-evidence.json",
                         "edit-rhythm.json", "index.html"):
                shutil.copy2(overview.parent / name, v4)
            for key in ("reviewGallery", "shotGallery", "timelineView"):
                source_html = overview.parent / study["artifacts"][key]
                destination_html = v4 / study["artifacts"][key]
                shutil.copytree(source_html.parent, destination_html.parent)
            onset_keys = {"timelineOnsetMinRiseDb", "timelineOnsetMinPeakDbFs",
                          "timelineOnsetCooldownMs"}
            v4_settings = {k: v for k, v in study["settings"].items()
                           if k not in onset_keys}
            v4_settings["studyVersion"] = REFERENCE_STUDY_V4_VERSION
            v4_settings["timelineStyleRevision"] = "offline-observation-tracks-v1"
            v4_study = {
                "schemaVersion": REFERENCE_STUDY_V4_VERSION,
                "settings": v4_settings,
                "artifacts": study["artifacts"],
                "files": _file_records(v4),
                "humanReviewStatus": "unreviewed",
                "qualityVerdict": "not-performed",
            }
            write_json_artifact(v4, "study-manifest.json", v4_study)
            self.assertEqual(_verify_study(v4, v4_settings), v4 / "index.html")


if __name__ == "__main__":
    unittest.main()
