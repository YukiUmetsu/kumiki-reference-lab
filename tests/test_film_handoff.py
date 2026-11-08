import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.integrations.kumiki.film_handoff import (
    export_film_handoff, film_handoff_from_reports,
)
from kumiki_reference_lab.pipeline.study import study_reference


CATALOG = Path(__file__).resolve().parents[1] / "catalog" / "entries"


def ratio(num, den=1):
    return {"numerator": num, "denominator": den}


def fixtures():
    source = "a" * 64
    run = "b" * 64
    times = [ratio(0), ratio(1), ratio(2)]
    regions = [{"id": f"region-{n+1:03d}", "startSeconds": value,
                "startPtsInclusive": n} for n, value in enumerate(times)]
    evidence = {"schemaVersion": "kumiki.shot-evidence.v1",
                "sourceSha256": source, "analysisRunSha256": run,
                "sourceStreamIndex": 0, "sourceTimebase": ratio(1),
                "regions": regions}
    rhythm = {"schemaVersion": "kumiki.edit-rhythm.v1",
              "sourceSha256": source, "analysisRunSha256": run,
              "sourceStreamIndex": 0, "sourceTimebase": ratio(1),
              "videoCutCandidateCount": 2, "observedInterCutIntervalCount": 1,
              "intervals": [{"regionId": "region-002",
                             "fromVideoCutCandidatePts": 1,
                             "toVideoCutCandidatePts": 2,
                             "fromSeconds": ratio(1), "toSeconds": ratio(2),
                             "durationSeconds": ratio(1)}]}
    onsets = {"schemaVersion": "kumiki.audio-onsets.v1",
              "sourceSha256": source, "sourceTimebase": ratio(1, 100),
              "scanWindowSeconds": 2,
              "status": "source-pts-aligned-level-attack-candidates",
              "candidates": [{
        "id": "onset-001", "anchorSourcePts": 123,
        "anchorSourceSeconds": ratio(123, 100),
        "supportWindow": {"startSeconds": ratio(12, 10),
                          "endSeconds": ratio(13, 10)},
        "signal": "candidate-rms-rise"}]}
    proposals = {"schemaVersion": "kumiki.technique-proposals.v1",
                 "source": {"sha256": source},
                 "provenance": {"analysisRunSha256": run},
                 "candidates": [{"id": "cue-01", "techniqueId": "camera.example",
                                 "sourcePtsRange": {"startPts": 1,
                                                    "endPts": 2}}]}
    study = {"schemaVersion": "kumiki.reference-study.v5",
             "settings": {"sourceSha256": source, "analysisRunSha256": run,
                          "seconds": 2}}
    return study, evidence, rhythm, onsets, proposals


class FilmHandoffPureTests(unittest.TestCase):
    def plan(self, *, fps_num=30000, fps_den=1001):
        return film_handoff_from_reports(
            *fixtures(), manifest_sha256="f" * 64,
            fps_num=fps_num, fps_den=fps_den)

    def test_explicit_unassigned_film_slots_and_no_claimed_audio_sync(self):
        packet = self.plan()
        self.assertEqual(packet["schemaVersion"], "kumiki.film-handoff.v1")
        self.assertFalse(packet["target"]["executableDocument"])
        self.assertFalse(packet["target"]["installedCapabilitiesVerified"])
        self.assertEqual(packet["timing"]["audioVideoClockRelation"],
                         "not-independently-synchronized")
        self.assertEqual(packet["boundaries"]["candidateCutCount"], 2)
        self.assertEqual(len(packet["interiorWindows"]), 1)
        window = packet["interiorWindows"][0]
        self.assertEqual(window["sourceRegionId"], "region-002")
        self.assertEqual(window["suggestedFilmFrames"], 30)
        self.assertEqual(window["roundingErrorSeconds"], ratio(1, 1000))
        self.assertIsNone(window["sceneRecipeId"])
        self.assertIsNone(window["sceneContent"])
        self.assertIsNone(packet["audioAttackCandidates"][0]["filmCue"])
        self.assertIsNone(packet["catalogTechniqueCues"][0]["implementationId"])
        self.assertNotIn("scenes", packet)

    def test_short_interval_requires_manual_retiming_not_automatic_minimum(self):
        study, evidence, rhythm, onsets, proposals = fixtures()
        evidence["regions"][2]["startSeconds"] = ratio(1001, 1000)
        rhythm["intervals"][0]["toSeconds"] = ratio(1001, 1000)
        rhythm["intervals"][0]["durationSeconds"] = ratio(1, 1000)
        packet = film_handoff_from_reports(
            study, evidence, rhythm, onsets, proposals,
            manifest_sha256="f" * 64, fps_num=30, fps_den=1)
        self.assertEqual(packet["interiorWindows"][0]["suggestedFilmFrames"], 0)
        self.assertEqual(packet["interiorWindows"][0]["renderability"],
                         "requires-authored-retiming")

    def test_rejects_inconsistent_cut_identity_and_fps(self):
        study, evidence, rhythm, onsets, proposals = fixtures()
        rhythm["intervals"][0]["toVideoCutCandidatePts"] = 999
        with self.assertRaisesRegex(ValueError, "not grounded"):
            film_handoff_from_reports(study, evidence, rhythm, onsets, proposals,
                                      manifest_sha256="f" * 64,
                                      fps_num=30, fps_den=1)
        with self.assertRaisesRegex(ValueError, "FPS"):
            self.plan(fps_den=0)
        with self.assertRaisesRegex(ValueError, "FPS"):
            self.plan(fps_num=100000, fps_den=1)

    def test_does_not_import_attacks_with_inconsistent_audio_pts(self):
        study, evidence, rhythm, onsets, proposals = fixtures()
        onsets["candidates"][0]["anchorSourceSeconds"] = ratio(124, 100)
        with self.assertRaisesRegex(ValueError, "invalid source PTS support"):
            film_handoff_from_reports(study, evidence, rhythm, onsets, proposals,
                                      manifest_sha256="f" * 64,
                                      fps_num=30, fps_den=1)

    def test_cli_exposes_explicit_frame_rate(self):
        args = build_parser().parse_args([
            "export-film-handoff", "study-manifest.json", "--fps-num", "24000",
            "--fps-den", "1001", "--out", "handoff"])
        self.assertEqual((args.fps_num, args.fps_den), (24000, 1001))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                     importlib.util.find_spec("numpy"),
                     "FFmpeg/FFprobe and NumPy required for local full integration")
class FilmHandoffIntegrationTests(unittest.TestCase):
    def test_export_from_verified_study_reuse_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "sample.mkv"
            result = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
                "-c:v", "ffv1", str(source),
            ], capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0)
            page = study_reference(source, root / "runs", catalog_root=CATALOG,
                                   seconds=2, thumbnails=4)
            manifest = page.parent / "study-manifest.json"
            destination = root / "handoff"
            path = export_film_handoff(manifest, destination)
            self.assertEqual(path.name, "film-handoff.json")
            packet = json.loads(path.read_text())
            self.assertEqual(packet["interiorWindows"], [])
            self.assertEqual(packet["boundaries"]["candidateCutCount"], 0)
            self.assertEqual(export_film_handoff(manifest, destination), path)
            with self.assertRaisesRegex(ValueError, "outside immutable bundles"):
                export_film_handoff(manifest, page.parent / "extras")
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "already exists"):
                export_film_handoff(manifest, destination)
            (page.parent / "shot-evidence.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "missing, altered or untracked"):
                export_film_handoff(manifest, root / "other-handoff")


if __name__ == "__main__":
    unittest.main()
