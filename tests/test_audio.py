"""Offline tests for the audio census engine and corpus driver.

No network and no real ffmpeg: the extraction, EBU R128 pass, probing and
download calls are patched. Synthetic PCM is raw ``s16le`` bytes written
without a ``wave`` container, so the 8 kHz mono convention is explicit.
"""

from __future__ import annotations

import importlib.util
import json
import math
import tempfile
import unittest
from array import array
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from kumiki_reference_lab.acquisition import audio

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audio_census", ROOT / "scripts" / "audio_census.py")
audio_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audio_script)

RATE = audio.PCM_SAMPLE_RATE


def _noise(count: int, *, amplitude: int = 2, seed: int = 7) -> list[int]:
    """Deterministic low-level dither: small but frame-to-frame varying."""
    values: list[int] = []
    state = seed
    for _ in range(count):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        values.append((state >> 16) % (2 * amplitude + 1) - amplitude)
    return values


def _tone(amplitude: float, seconds: float, frequency: float = 220.0) -> list[int]:
    return [
        int(amplitude * 32767 * math.sin(2 * math.pi * frequency * index / RATE))
        for index in range(int(seconds * RATE))
    ]


def _write_pcm(path: Path, samples: list[int]) -> Path:
    path.write_bytes(array("h", samples).tobytes())
    return path


def _bursts() -> list[int]:
    """Twelve 120 BPM sine bursts over a low dither floor."""
    samples: list[int] = []
    for _ in range(12):
        samples += _noise(int(0.38 * RATE))
        samples += _tone(0.5, 0.12)
    samples += _noise(1000)
    return samples


def _clicks(bpm: float = 120.0, seconds: float = 10.0) -> list[int]:
    period = int(round(60.0 / bpm * RATE))
    click = _tone(0.8, 0.01, frequency=1000.0)
    samples: list[int] = []
    for _ in range(int(seconds * bpm / 60.0)):
        samples += _noise(period - len(click))
        samples += click
    samples += _noise(1000)
    return samples


def _summary(values: list[float]) -> dict:
    momentary = [
        {"seconds": second + step / 10.0, "lufs": value}
        for second, value in enumerate(values)
        for step in range(10)
    ]
    return {
        "integratedLufs": -23.0,
        "loudnessRangeLu": 5.0,
        "truePeakDbfs": -1.5,
        "momentaryLufs": momentary,
    }


class AudioMeasurementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "source.pcm"

    def _measure(self, samples: list[int], **summary) -> dict:
        _write_pcm(self.path, samples)
        return audio.measure_audio(
            self.path, loudness_summary=summary or {})

    def test_sine_bursts_silence_onsets_and_regularity(self) -> None:
        measured = self._measure(_bursts())
        self.assertEqual(measured["onsetCount"], 12)
        self.assertAlmostEqual(measured["medianOnsetGapSeconds"], 0.5, places=2)
        self.assertEqual(measured["regularityIndex"], 1.0)
        self.assertGreater(measured["silenceFraction"], 0.5)
        self.assertLess(measured["silenceFraction"], 1.0)
        self.assertEqual(measured["onsetRateTrend"], "steady")

    def test_click_train_tempo_hypothesis(self) -> None:
        measured = self._measure(_clicks())
        self.assertIsNotNone(measured["tempoHypothesisBpm"])
        self.assertLessEqual(
            abs(measured["tempoHypothesisBpm"] - 120.0), 3.0)
        self.assertGreaterEqual(measured["tempoConfidence"], 0.5)
        self.assertEqual(measured["onsetCount"], 20)

    def test_crescendo_loudness_slope_is_positive(self) -> None:
        climax = [round(-32.0 + 2.5 * second, 1) for second in range(6)]
        measured = self._measure(_tone(0.3, 6.0), **_summary(climax))
        self.assertGreater(measured["loudnessSlopeLuPerMinute"], 0)
        self.assertGreater(measured["loudnessSlopeR2"], 0.99)
        self.assertGreater(measured["firstHalfVsSecondHalfLu"], 0)
        self.assertEqual(measured["shortTermLufsSeries"], climax)
        self.assertEqual(measured["integratedLufs"], -23.0)
        self.assertEqual(measured["truePeakDbfs"], -1.5)

    def test_monotonic_decline_slope_is_negative(self) -> None:
        decay = [round(-15.0 - 2.0 * second, 1) for second in range(6)]
        measured = self._measure(_tone(0.3, 6.0), **_summary(decay))
        self.assertLess(measured["loudnessSlopeLuPerMinute"], 0)
        self.assertLess(measured["firstHalfVsSecondHalfLu"], 0)

    def test_constant_tone_has_no_onsets_or_tempo(self) -> None:
        measured = self._measure(_tone(0.5, 2.0))
        self.assertEqual(measured["onsetCount"], 0)
        self.assertIsNone(measured["regularityIndex"])
        self.assertIsNone(measured["medianOnsetGapSeconds"])
        self.assertIsNone(measured["tempoHypothesisBpm"])
        self.assertIsNone(measured["tempoConfidence"])
        self.assertEqual(measured["silenceFraction"], 0.0)
        self.assertAlmostEqual(measured["samplePeakDbfs"], -6.02, places=1)

    def test_empty_short_and_malformed_pcm_are_refused(self) -> None:
        self.path.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "empty"):
            audio.measure_audio(self.path, loudness_summary={})
        _write_pcm(self.path, _noise(10))
        with self.assertRaisesRegex(ValueError, "shorter"):
            audio.measure_audio(self.path, loudness_summary={})
        self.path.write_bytes(b"\x01\x02\x03")
        with self.assertRaisesRegex(ValueError, "whole number"):
            audio.measure_audio(self.path, loudness_summary={})

    def test_dc_and_digital_silence(self) -> None:
        dc = self._measure([32767] * (2 * RATE))
        self.assertAlmostEqual(dc["rmsDbfs"], 0.0, places=1)
        self.assertAlmostEqual(dc["samplePeakDbfs"], 0.0, places=1)
        self.assertEqual(dc["onsetCount"], 0)
        self.assertIsNone(dc["tempoHypothesisBpm"])
        silent = self._measure([0] * (2 * RATE))
        self.assertEqual(silent["silenceFraction"], 1.0)
        self.assertEqual(silent["rmsDbfs"], -120.0)
        self.assertEqual(silent["headSilenceSeconds"], 2.0)
        self.assertEqual(silent["tailSilenceSeconds"], 2.0)
        self.assertIsNone(silent["tempoHypothesisBpm"])

    def test_ebur128_log_parses_summary_and_momentary_values(self) -> None:
        log = "\n".join([
            "[Parsed_ebur128_0 @ 0x1] t: 0.0999773  TARGET:-23 LUFS    "
            "M:-120.7 S:-120.7     I: -70.0 LUFS       LRA:   0.0 LU",
            "[Parsed_ebur128_0 @ 0x1] t: 1.099977   TARGET:-23 LUFS    "
            "M: -20.4 S:-120.7     I: -20.4 LUFS       LRA:   1.0 LU",
            "Summary:",
            "  Integrated loudness:",
            "    I:         -20.4 LUFS",
            "    Threshold: -30.4 LUFS",
            "  Loudness range:",
            "    LRA:         1.0 LU",
            "  True peak:",
            "    Peak:      -1.5 dBFS",
        ])
        parsed = audio.parse_ebur128_log(log)
        self.assertEqual(parsed["integratedLufs"], -20.4)
        self.assertEqual(parsed["loudnessRangeLu"], 1.0)
        self.assertEqual(parsed["truePeakDbfs"], -1.5)
        self.assertEqual(len(parsed["momentaryLufs"]), 2)
        self.assertEqual(parsed["momentaryLufs"][0]["lufs"], -120.7)

        measured = self._measure(
            _tone(0.3, 2.0),
            integratedLufs=-20.4, loudnessRangeLu=1.0, truePeakDbfs=-1.5,
            momentaryLufs=parsed["momentaryLufs"])
        self.assertEqual(
            measured["shortTermLufsSeries"], [-70.0, -20.4])

    def test_measurement_contract_and_non_claims(self) -> None:
        measured = self._measure(_bursts())
        for key in (
            "integratedLufs", "loudnessRangeLu", "truePeakDbfs",
            "samplePeakDbfs", "rmsDbfs", "silenceFraction",
            "headSilenceSeconds", "tailSilenceSeconds",
            "shortTermLufsSeries", "shortTermRangeLu",
            "loudnessSlopeLuPerMinute", "loudnessSlopeR2",
            "firstHalfVsSecondHalfLu", "onsetCount",
            "onsetsPerMinuteOfRuntime", "onsetRateSeries",
            "onsetRateTrend", "medianOnsetGapSeconds", "regularityIndex",
            "tempoHypothesisBpm", "tempoConfidence", "limits",
        ):
            self.assertIn(key, measured)
        self.assertEqual(measured["methods"], {
            "loudness": audio.METHOD_EBUR128,
            "envelope": audio.METHOD_ENVELOPE,
        })
        self.assertIn("No speech/music separation", measured["limits"][0])
        self.assertTrue(any(
            "transcription" in limit for limit in measured["limits"]))
        self.assertTrue(any(
            "sync-to-picture" in limit for limit in measured["limits"]))
        self.assertEqual(len(measured["limits"]), 5)

    def test_has_audio_stream(self) -> None:
        self.assertTrue(audio.has_audio_stream(
            {"streams": [{"codec_type": "video"},
                         {"codec_type": "audio"}]}))
        self.assertFalse(audio.has_audio_stream(
            {"streams": [{"codec_type": "video"}]}))
        self.assertFalse(audio.has_audio_stream({"streams": []}))
        self.assertFalse(audio.has_audio_stream({}))
        with self.assertRaises(ValueError):
            audio.has_audio_stream([])  # type: ignore[arg-type]


class AudioExtractionTests(unittest.TestCase):
    def test_extract_audio_command_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "clip.mp4"
            source.write_bytes(b"media")
            destination = root / "source.pcm"
            body = array("h", _tone(0.2, 0.2)).tobytes()

            def fake_run(command, **kwargs):  # noqa: ANN001
                Path(command[-1]).write_bytes(body)
                return CompletedProcess(command, 0, "", "")

            with patch.object(audio.subprocess, "run", side_effect=fake_run) as run:
                result = audio.extract_audio(source, destination)
            command = run.call_args[0][0]
            self.assertEqual(result, destination)
            self.assertTrue(destination.is_file())
            for flag in ("-vn", "-ac", "-ar", "-f", "s16le"):
                self.assertIn(flag, command)
            self.assertIn("8000", command)
            self.assertIn("1", command)

    def test_extract_audio_refuses_symlink_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "clip.mp4"
            target.write_bytes(b"media")
            link = root / "link.mp4"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                audio.extract_audio(link, root / "source.pcm")


class _Options:
    def __init__(self, root: Path, **overrides) -> None:
        values = {
            "root": root, "max_file_bytes": 400 * 1024 ** 2,
            "max_duration_seconds": 600.0, "ffmpeg": "ffmpeg",
            "ffprobe": "ffprobe", "yt_dlp": "yt-dlp",
            "timeout_seconds": 60.0, "sample_stratified": 0,
            "jobs": 1, "delay_seconds": 0.0, "limit": 0, "resume": True,
        }
        values.update(overrides)
        self.__dict__.update(values)


def _item(root: Path, *, sha: str | None = "a" * 64,
          duration: float | None = 10.0) -> dict:
    return {
        "id": "1", "slug": "clip",
        "recordPath": "promonews/videos/1-clip.json",
        "videoUrl": "https://www.youtube.com/watch?v=abcdefghijk",
        "storedProvider": "youtube", "delivery": "youtube",
        "mediaSha256": sha, "durationSeconds": duration,
        "hosts": ("youtube.com",), "allowQuery": False,
        "outputPath": root / "promonews" / "audio" / "1-clip.json",
    }


def _fake_download(created: list[Path]):
    def download(url, delivery, directory, **kwargs):  # noqa: ANN001
        path = Path(directory) / "source.mp4"
        path.write_bytes(b"media")
        created.append(path)
        return path, "ytdlp-merge"
    return download


def _fake_extract(created: list[Path]):
    def extract(media_path, destination, **kwargs):  # noqa: ANN001
        destination = Path(destination)
        destination.write_bytes(array("h", _tone(0.2, 1.0)).tobytes())
        created.append(destination)
        return destination
    return extract


def _measurement() -> dict:
    return {
        "durationSeconds": 10.0, "integratedLufs": -23.0,
        "loudnessRangeLu": 5.0, "truePeakDbfs": -1.5,
        "rmsDbfs": -20.0, "silenceFraction": 0.25,
        "onsetCount": 20, "onsetsPerMinuteOfRuntime": 120.0,
        "onsetRateTrend": "steady", "tempoHypothesisBpm": 120.0,
        "limits": list(audio.AUDIO_LIMITS),
    }


def _metadata(**overrides) -> dict:
    values = {
        "durationSeconds": 10.0, "mediaSha256": "a" * 64,
        "sizeBytes": 1000, "audioCodec": "aac",
    }
    values.update(overrides)
    return values


class AudioScriptLifecycleTests(unittest.TestCase):
    def test_duration_mismatch_is_a_skip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created: list[Path] = []
            with patch.object(audio_script, "download_media",
                              side_effect=_fake_download(created)), \
                 patch.object(audio_script, "probe_media",
                              return_value={"streams": [
                                  {"codec_type": "audio"}]}), \
                 patch.object(audio_script, "source_metadata",
                              return_value=_metadata(durationSeconds=30.0)):
                with self.assertRaises(audio_script.BatchSkip) as raised:
                    audio_script.run_audio_item(
                        _item(root), site="promonews",
                        options=_Options(root))
            self.assertEqual(raised.exception.reason, "duration-mismatch")
            self.assertFalse(created[0].exists())
            self.assertFalse(
                (root / "promonews" / "audio" / "1-clip.json").exists())

    def test_no_audio_stream_is_a_skip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created: list[Path] = []
            with patch.object(audio_script, "download_media",
                              side_effect=_fake_download(created)), \
                 patch.object(audio_script, "probe_media",
                              return_value={"streams": [
                                  {"codec_type": "video"}]}), \
                 patch.object(audio_script, "source_metadata") as metadata:
                with self.assertRaises(audio_script.BatchSkip) as raised:
                    audio_script.run_audio_item(
                        _item(root), site="promonews",
                        options=_Options(root))
            self.assertEqual(raised.exception.reason, "no-audio-stream")
            metadata.assert_not_called()
            self.assertFalse(created[0].exists())

    def test_sha_mismatch_is_recorded_not_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created: list[Path] = []
            pcm: list[Path] = []
            with patch.object(audio_script, "download_media",
                              side_effect=_fake_download(created)), \
                 patch.object(audio_script, "probe_media",
                              return_value={"streams": [
                                  {"codec_type": "audio"}]}), \
                 patch.object(audio_script, "source_metadata",
                              return_value=_metadata(mediaSha256="b" * 64)), \
                 patch.object(audio_script, "extract_audio",
                              side_effect=_fake_extract(pcm)), \
                 patch.object(audio_script, "ebur128_summary",
                              return_value={}), \
                 patch.object(audio_script, "measure_audio",
                              return_value=_measurement()):
                row = audio_script.run_audio_item(
                    _item(root), site="promonews", options=_Options(root))
            output = root / "promonews" / "audio" / "1-clip.json"
            self.assertTrue(output.is_file())
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["schemaVersion"],
                             "kumiki.promonews-audio-evidence.v1")
            self.assertEqual(
                payload["source"]["mediaSha256Observed"], "b" * 64)
            self.assertFalse(payload["source"]["shaMatchesRecord"])
            self.assertFalse(payload["acquisition"]["mediaRetained"])
            self.assertEqual(payload["audio"], _measurement())
            self.assertEqual(row["shaMatchesRecord"], False)
            self.assertTrue(created and pcm)
            self.assertFalse(created[0].exists())
            self.assertFalse(pcm[0].exists())
            self.assertEqual(list(output.parent.glob("*.tmp")), [])


class AudioScriptIdSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def _write_record(self, record_id: int, name: str) -> None:
        videos = self.root / "promonews" / "videos"
        videos.mkdir(parents=True, exist_ok=True)
        (videos / f"{record_id:03d}-{name}.json").write_text(json.dumps({
            "nid": record_id, "slug": name, "provider": "youtube",
            "videoUrl": "https://www.youtube.com/watch?v=abcdefghijk",
            "source": {"mediaSha256": "a" * 64, "durationSeconds": 10.0,
                       "sizeBytes": 1000},
        }), encoding="utf-8")

    def test_all_three_forms_and_numeric_equality(self) -> None:
        self.assertEqual(
            audio_script.load_ids_file(
                self.write("list.json", '["1", 2, "3"]')),
            ["1", "2", "3"])
        self.assertEqual(
            audio_script.load_ids_file(
                self.write("object.json", '{"ids": [1, 2]}')),
            ["1", "2"])
        self.assertEqual(
            audio_script.load_ids_file(self.write("lines.txt", "1\n2\n3\n")),
            ["1", "2", "3"])

    def test_malformed_and_blank_ids_are_refused(self) -> None:
        for name, text in (
                ("empty.txt", " \n"), ("bad.json", "{not json"),
                ("no-ids.json", '{"other": []}'), ("scalar.json", '"1"'),
                ("blank-list.json", '["1", " "]'),
                ("blank-line.txt", "1\n \n2\n")):
            with self.subTest(name=name):
                path = self.write(name, text)
                with self.assertRaises(ValueError) as caught:
                    audio_script.load_ids_file(path)
                self.assertIn(str(path), str(caught.exception))

    def test_filter_preserves_record_order_and_reports_missing(self) -> None:
        rows = [{"id": "3"}, {"id": "1"}, {"id": "2"}]
        chosen, missing = audio_script.select_ids(rows, ["3", 1, "999"])
        self.assertEqual([row["id"] for row in chosen], ["3", "1"])
        self.assertEqual(missing, ["999"])

    def test_missing_id_becomes_a_skip_row(self) -> None:
        self._write_record(1, "clip-1")
        ids_path = self.write("ids.json", '["1", 999]')

        def fake_run(item: dict, *, site: str, options: object) -> dict:
            return {"id": item["id"], "slug": item["slug"]}

        with patch.object(audio_script, "run_audio_item", side_effect=fake_run):
            code = audio_script.main([
                "--root", str(self.root), "--site", "promonews",
                "--ids-file", str(ids_path), "--acknowledge-rights",
                "--delay-seconds", "0"])

        self.assertEqual(code, 0)
        index = json.loads(
            (self.root / "promonews" / "audio-index.json").read_text(
                encoding="utf-8"))
        missing = [row for row in index["skips"]
                   if row["reason"] == "missing-from-catalog"]
        self.assertEqual([row["id"] for row in missing], ["999"])

    def test_main_selects_exactly_three_ids_offline(self) -> None:
        for record_id in range(1, 6):
            self._write_record(record_id, f"clip-{record_id}")
        ids_path = self.write("ids.txt", "5\n2\n4\n")
        calls: list[str] = []

        def fake_run(item: dict, *, site: str, options: object) -> dict:
            calls.append(str(item["id"]))
            return {"id": item["id"], "slug": item["slug"]}

        with patch.object(audio_script, "run_audio_item", side_effect=fake_run):
            code = audio_script.main([
                "--root", str(self.root), "--site", "promonews",
                "--ids-file", str(ids_path), "--acknowledge-rights",
                "--delay-seconds", "0"])

        self.assertEqual(code, 0)
        self.assertEqual(calls, ["2", "4", "5"])
        index = json.loads(
            (self.root / "promonews" / "audio-index.json").read_text(
                encoding="utf-8"))
        self.assertEqual(index["counts"], {"measured": 3, "skipped": 0,
                                           "failed": 0})


class AudioScriptBatchTests(unittest.TestCase):
    def _write_record(self, root: Path, name: str, *, record_id: int) -> None:
        videos = root / "promonews" / "videos"
        videos.mkdir(parents=True, exist_ok=True)
        payload = {
            "nid": record_id, "slug": name, "provider": "youtube",
            "videoUrl": "https://www.youtube.com/watch?v=abcdefghijk",
            "source": {"mediaSha256": "a" * 64, "durationSeconds": 10.0,
                       "sizeBytes": 1000},
        }
        (videos / f"{record_id:03d}-{name}.json").write_text(
            json.dumps(payload), encoding="utf-8")

    def test_index_is_atomic_and_isolates_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_record(root, "a", record_id=1)
            self._write_record(root, "b", record_id=2)
            created: list[Path] = []
            pcm: list[Path] = []
            calls = {"count": 0}

            def measure(*args, **kwargs):  # noqa: ANN001
                calls["count"] += 1
                if calls["count"] == 1:
                    raise RuntimeError("decoder failed")
                return _measurement()

            with patch.object(audio_script, "download_media",
                              side_effect=_fake_download(created)), \
                 patch.object(audio_script, "probe_media",
                              return_value={"streams": [
                                  {"codec_type": "audio"}]}), \
                 patch.object(audio_script, "source_metadata",
                              return_value=_metadata()), \
                 patch.object(audio_script, "extract_audio",
                              side_effect=_fake_extract(pcm)), \
                 patch.object(audio_script, "ebur128_summary",
                              return_value={}), \
                 patch.object(audio_script, "measure_audio",
                              side_effect=measure):
                code = audio_script.main([
                    "--root", str(root), "--site", "promonews",
                    "--acknowledge-rights", "--delay-seconds", "0",
                ])
            self.assertEqual(code, 0)
            index_path = root / "promonews" / "audio-index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(index["schemaVersion"],
                             "kumiki.promonews-audio-index.v1")
            self.assertEqual(index["counts"],
                             {"measured": 1, "skipped": 0, "failed": 1})
            self.assertEqual(len(index["records"]), 1)
            self.assertEqual(len(index["failures"]), 1)
            self.assertIn("decoder failed", index["failures"][0]["reason"])
            self.assertEqual(list(index_path.parent.glob("*.tmp")), [])
            for path in created + pcm:
                self.assertFalse(path.exists())

    def test_missing_url_is_a_skip_not_a_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            videos = root / "promonews" / "videos"
            videos.mkdir(parents=True)
            (videos / "123-clip.json").write_text(json.dumps({
                "nid": 123, "slug": "clip", "provider": "youtube",
                "videoUrl": None, "source": {"mediaSha256": "a" * 64},
            }), encoding="utf-8")
            with patch.object(audio_script, "download_media") as download:
                code = audio_script.main([
                    "--root", str(root), "--site", "promonews",
                    "--acknowledge-rights"])
            self.assertEqual(code, 0)
            download.assert_not_called()
            index = json.loads(
                (root / "promonews" / "audio-index.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(index["counts"]["skipped"], 1)
            self.assertEqual(index["skips"][0]["reason"], "missing-url")

    def test_stratified_sample_spreads_across_the_record_list(self) -> None:
        paths = [Path(f"{index:03d}-clip.json") for index in range(10)]
        picked = audio_script.stratified_sample(paths, 3)
        self.assertEqual(
            [path.name for path in picked],
            ["001-clip.json", "005-clip.json", "008-clip.json"])
        self.assertEqual(audio_script.stratified_sample(paths, 0), paths)
        self.assertEqual(audio_script.stratified_sample(paths, 20), paths)


if __name__ == "__main__":
    unittest.main()
