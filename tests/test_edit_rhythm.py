import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.shots.rhythm import (
    build_edit_rhythm, summarize_edit_rhythm,
)
from kumiki_reference_lab.cli.app import build_parser
from kumiki_reference_lab.pipeline.analyze import run_analysis


def region(id_number, time_numerator, time_denominator=1):
    return {
        "id": f"region-{id_number:03d}",
        "startPtsInclusive": time_numerator,
        "startSeconds": {"numerator": time_numerator,
                         "denominator": time_denominator},
    }


class EditRhythmPureTests(unittest.TestCase):
    def test_first_and_final_partial_regions_not_counted_as_complete_shots(self):
        rows = [region(1, 0), region(2, 1), region(3, 3), region(4, 4)]
        result = summarize_edit_rhythm(rows)
        self.assertEqual(result["videoCutCandidateCount"], 3)
        self.assertEqual(result["observedInterCutIntervalCount"], 2)
        self.assertEqual(result["status"], "bounded-candidate-inter-cut-intervals")
        first, second = result["intervals"]
        self.assertEqual(first["durationSeconds"], {"numerator": 2, "denominator": 1})
        self.assertEqual(first["regionId"], "region-002")
        self.assertEqual(first["changeVsPrevious"], "not-applicable-first-interval")
        self.assertIsNone(first["durationRatioToPrevious"])
        self.assertEqual(second["durationSeconds"], {"numerator": 1, "denominator": 1})
        self.assertEqual(second["durationRatioToPrevious"],
                         {"numerator": 1, "denominator": 2})
        self.assertEqual(second["changeVsPrevious"], "shorter")
        self.assertEqual(result["durationRangeSeconds"]["median"],
                         {"numerator": 3, "denominator": 2})

    def test_single_cut_cannot_establish_intercut_duration(self):
        result = summarize_edit_rhythm([region(1, 0), region(2, 1)])
        self.assertEqual(result["videoCutCandidateCount"], 1)
        self.assertEqual(result["observedInterCutIntervalCount"], 0)
        self.assertEqual(result["intervals"], [])
        self.assertIsNone(result["durationRangeSeconds"]["median"])
        self.assertEqual(summarize_edit_rhythm([region(1, 0)])["videoCutCandidateCount"], 0)

    def test_invalid_non_monotonic_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            summarize_edit_rhythm([region(1, 0), region(2, 2), region(3, 1)])

    def test_equal_intervals_report_same_without_fabricating_acceleration(self):
        result = summarize_edit_rhythm([
            region(1, 0), region(2, 1), region(3, 2), region(4, 3)])
        self.assertEqual(result["intervals"][1]["changeVsPrevious"], "same")
        self.assertEqual(result["intervals"][1]["durationRatioToPrevious"],
                         {"numerator": 1, "denominator": 1})

    def test_cli_argument_is_available(self):
        args = build_parser().parse_args(["edit-rhythm", "run/analysis-run.json"])
        self.assertEqual(args.command, "edit-rhythm")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe unavailable")
class EditRhythmIntegrationTests(unittest.TestCase):
    def test_derived_intervals_from_verified_run_and_tamper_guard(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "three-distinct-colors.mkv"
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1",
                "-f", "lavfi", "-i", "color=c=yellow:s=160x90:r=10:d=1",
                "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1",
                "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
                "-map", "[v]", "-c:v", "ffv1", str(source),
            ]
            generated = subprocess.run(command, capture_output=True, timeout=30)
            self.assertEqual(generated.returncode, 0,
                             generated.stderr.decode(errors="replace"))
            manifest = run_analysis(source, root / "runs", seconds=3, thumbnails=4,
                                    threshold=.12)
            result = build_edit_rhythm(manifest)
            self.assertEqual(result["schemaVersion"], "kumiki.edit-rhythm.v1")
            self.assertEqual(result["videoCutCandidateCount"], 2)
            self.assertEqual(result["observedInterCutIntervalCount"], 1)
            self.assertEqual(result["intervals"][0]["durationSeconds"],
                             {"numerator": 1, "denominator": 1})
            self.assertEqual(result["qualityVerdict"], "not-performed")
            (manifest.parent / "shot-candidates.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "missing or modified"):
                build_edit_rhythm(manifest)


if __name__ == "__main__":
    unittest.main()
