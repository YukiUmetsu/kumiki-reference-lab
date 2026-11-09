import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from kumiki_reference_lab.analyzers.appearance.analyze import analyze_appearance
from kumiki_reference_lab.analyzers.appearance.ramps import detect_luma_ramp_candidates
from kumiki_reference_lab.backends.ffmpeg.probe import ProbeError
from kumiki_reference_lab.backends.ffmpeg.raw_frames import read_rgb_frames


class LumaRampCandidateTests(unittest.TestCase):
    @staticmethod
    def _observations(levels, *, local=False):
        samples = []
        for index, level in enumerate(levels):
            grid = [{"meanLumaProxy": level if not local or cell < 2 else 0.5}
                    for cell in range(9)]
            samples.append({"sourcePts": index * 10,
                            "appearance": {"meanLumaProxy": level,
                                           "spatialGrid3x3": grid}})
        changes = [{"status": "measured-display-appearance-change"}
                   for _ in levels[1:]]
        return samples, changes

    def test_coherent_darkening_candidate_not_asserted_as_proven_fade(self):
        samples, changes = self._observations([0.64, 0.5, 0.35, 0.2, 0.08])
        result = detect_luma_ramp_candidates(samples, changes, timebase=Fraction(1, 100))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["kind"], "fade-to-black-candidate")
        self.assertEqual(result[0]["durationSeconds"],
                         {"numerator": 2, "denominator": 5})
        self.assertEqual(result[0]["interpretationStatus"],
                         "review-required-not-verified")

    def test_local_brightness_motion_or_short_jump_is_not_a_global_ramp(self):
        samples, changes = self._observations([0.6, 0.5, 0.4, 0.3, 0.2], local=True)
        self.assertEqual(detect_luma_ramp_candidates(
            samples, changes, timebase=Fraction(1, 100)), [])
        samples, changes = self._observations([0.6, 0.5, 0.4, 0.3, 0.2])
        self.assertEqual(detect_luma_ramp_candidates(
            samples, changes, timebase=Fraction(1, 1000)), [])
        samples, changes = self._observations([0.65, 0.25, 0.25, 0.25, 0.25])
        self.assertEqual(detect_luma_ramp_candidates(
            samples, changes, timebase=Fraction(1, 100)), [])

    def test_cut_boundary_blocks_cumulative_fade_evidence(self):
        samples, changes = self._observations([0.8, 0.7, 0.6, 0.5, 0.4])
        changes[2]["status"] = "cut-boundary"
        self.assertEqual(detect_luma_ramp_candidates(
            samples, changes, timebase=Fraction(1, 100)), [])

    def test_up_and_down_global_ramps_are_not_assumed_fades_without_black(self):
        samples, changes = self._observations([0.75, 0.65, 0.55, 0.45,
                                                0.55, 0.65, 0.75])
        result = detect_luma_ramp_candidates(samples, changes,
                                             timebase=Fraction(1, 100))
        self.assertEqual(len(result), 2)
        self.assertEqual([r["kind"] for r in result],
                         ["global-brightness-ramp-candidate"] * 2)


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy unavailable")
class AppearanceStatisticsTests(unittest.TestCase):
    def test_saturated_red_and_neutral_gray_are_measured_distinctly(self):
        from kumiki_reference_lab.analyzers.appearance.statistics import describe_rgb_frame

        red = describe_rgb_frame(bytes([255, 0, 0]) * (160 * 90), 160, 90)
        self.assertEqual(red["meanRgb"], [1.0, 0.0, 0.0])
        self.assertEqual(red["hueHistogram12"][0], 1.0)
        self.assertEqual(red["chromaticPixelFraction"], 1)
        self.assertEqual(red["brightPixelFraction"], 0)
        self.assertIsNone(red["brightPixelCentroid"])
        self.assertEqual(len(red["spatialGrid3x3"]), 9)
        gray = describe_rgb_frame(bytes([128, 128, 128]) * (160 * 90), 160, 90)
        self.assertEqual(gray["meanSaturation"], 0)
        self.assertEqual(gray["chromaticPixelFraction"], 0)
        self.assertEqual(sum(gray["hueHistogram12"]), 0)

    def test_high_contrast_bright_region_has_measured_centroid(self):
        from kumiki_reference_lab.analyzers.appearance.statistics import describe_rgb_frame

        image = b"".join((bytes([0, 0, 0]) * 80 + bytes([255, 255, 255]) * 80)
                         for _ in range(90))
        result = describe_rgb_frame(image, 160, 90)
        self.assertEqual(result["brightPixelFraction"], 0.5)
        self.assertEqual(result["lumaContrastP90MinusP10"], 1)
        self.assertAlmostEqual(result["brightPixelCentroid"]["x"], 0.75, delta=0.002)
        self.assertAlmostEqual(result["brightPixelCentroid"]["y"], 0.5, delta=0.002)
        self.assertLess(result["spatialGrid3x3"][0]["meanLumaProxy"],
                        result["spatialGrid3x3"][2]["meanLumaProxy"])

    def test_bad_rgb_buffer_rejected(self):
        from kumiki_reference_lab.analyzers.appearance.statistics import describe_rgb_frame

        with self.assertRaises(ValueError):
            describe_rgb_frame(b"bad", 160, 90)

    def test_rgb_decoder_rejects_timestamp_mismatch(self):
        with patch("subprocess.run", return_value=CompletedProcess(
            [], 0, b"12345", b"[Parsed_showinfo_1] config in time_base: 1/1000\n"
                              b"[Parsed_showinfo_1] n: 0 pts: 200 pts_time:0.2\n"
        )):
            with self.assertRaisesRegex(ProbeError, "do not match"):
                read_rgb_frames(Path("test.mkv"), 0, [0], [100],
                                timebase=Fraction(1, 1000), seconds=1,
                                width=64, height=36)


@unittest.skipUnless(importlib.util.find_spec("numpy") and shutil.which("ffmpeg") and
                     shutil.which("ffprobe"), "NumPy/FFmpeg unavailable")
class AppearanceIntegrationTests(unittest.TestCase):
    def _clip(self, target: Path, *, vfr: bool = False) -> None:
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                   "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=1"]
        if vfr:
            command += ["-vf", "setpts='if(lt(N,5),N,N*2)/(10*TB)'", "-fps_mode", "vfr"]
        command += ["-c:v", "ffv1", str(target)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_vfr_real_video_reports_measured_appearance_at_source_times(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "vfr.mkv"
            self._clip(source, vfr=True)
            artifact = analyze_appearance(source, seconds=2, max_samples=10,
                                          threshold=0.95)
            self.assertEqual(artifact["schemaVersion"], "kumiki.appearance.v1")
            self.assertGreater(len(artifact["samples"]), 5)
            self.assertEqual(len(artifact["changes"]), len(artifact["samples"]) - 1)
            increments = [b["sourcePts"] - a["sourcePts"]
                          for a, b in zip(artifact["samples"], artifact["samples"][1:])]
            self.assertGreater(max(increments), min(increments))
            self.assertFalse(artifact["analyzer"]["physicalPhotometry"])
            self.assertTrue(all(len(s["appearance"]["hueHistogram12"]) == 12
                                for s in artifact["samples"]))
            json.dumps(artifact, allow_nan=False)

    def test_rgb_frame_decoder_color_conversion_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "gray.mkv"
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                       "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
                       "-c:v", "ffv1", str(target)]
            process = subprocess.run(command, capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0)
            artifact = analyze_appearance(target, seconds=2, max_samples=5,
                                          threshold=0.95)
            values = [entry["appearance"]["meanSaturation"] for entry in artifact["samples"]]
            self.assertTrue(all(value < 0.02 for value in values))

    def test_encoded_global_fade_to_black_remains_review_only(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "global-fade.mkv"
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                       "-f", "lavfi", "-i", "color=c=white:s=160x90:r=10:d=1",
                       "-vf", "fade=t=out:st=0:d=0.7", "-c:v", "ffv1", str(video)]
            process = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            artifact = analyze_appearance(video, seconds=2, max_samples=10,
                                          threshold=0.95)
            ramps = artifact["lumaRampCandidates"]
            self.assertGreaterEqual(len(ramps), 1)
            self.assertEqual(ramps[0]["kind"], "fade-to-black-candidate")
            self.assertEqual(artifact["analyzer"]["rampModel"],
                             "spatially-coherent-luma-ramp-candidate-v1")
            self.assertFalse(artifact["analyzer"]["physicalPhotometry"])
            self.assertTrue(all(ramp["endPts"] > ramp["startPts"] for ramp in ramps))
            json.dumps(artifact, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
