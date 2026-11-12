"""Offline tests for scripts/refresh_video_evidence_summaries.py."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts import refresh_video_evidence_summaries as refresh

LEGACY_KEYS = (
    "cutCandidates",
    "cutCandidateRatePerMinute",
    "meanDisplayLuma",
    "meanSaturation",
    "meanWithinShotRgbDeltaPerSecond",
    "sampledFrames",
    "windowsWithCuts",
)
VALIDITY_KEYS = (
    "medianCutGapSeconds",
    "medianCutGapFrames",
    "minCutGapSeconds",
    "cutCandidateCount",
    "burstFraction",
    "withinShotPairs",
    "cutSeparatedPairs",
    "deltaBasisPairs",
    "cutsPerMinuteCi95",
    "validityFlags",
)


def probe(*, pairs: bool = True) -> dict:
    payload = {
        "sourceTimebase": {"numerator": 1, "denominator": 12800},
        "cutCandidatePts": [0, 12800, 25600],
        "sampledFrames": [{"sourcePts": index * 12800} for index in range(6)],
        "sampledWindowSummary": {
            "cutCandidateCountBetweenFirstAndLastSample": 3,
            "meanSampledDisplayLumaProxy": 0.4,
            "meanSampledSaturationProxy": 0.5,
            "withinShotComparedPairs": 4,
            "cutSeparatedPairs": 2,
        },
    }
    if pairs:
        payload["sampledFramePairs"] = [
            {"meanAbsoluteDisplayRgbDeltaPerSecond": 0.1 * (index + 1)}
            for index in range(6)
        ]
    return payload


def legacy_summary() -> dict:
    return {key: value for key, value in (
        ("cutCandidates", 3),
        ("cutCandidateRatePerMinute", 6.0),
        ("meanDisplayLuma", 0.4),
        ("meanSaturation", 0.5),
        ("meanWithinShotRgbDeltaPerSecond", 0.35),
        ("sampledFrames", 6),
        ("windowsWithCuts", 1),
    )}


def record(*, with_windows: bool = True, pairs: bool = True) -> dict:
    payload = {
        "schemaVersion": "kumiki.example-video-evidence.v1",
        "source": {
            "durationSeconds": 60.0,
            "frameRate": {"numerator": 25, "denominator": 1},
            "sourceTimebase": {"numerator": 1, "denominator": 12800},
        },
        "coverage": {
            "windowsMeasured": 1,
            "windowSeconds": 30,
            "sampledSeconds": 30,
            "fractionOfRuntime": 0.5,
        },
        "summary": legacy_summary(),
        "generatedAt": "2026-01-01T00:00:00Z",
    }
    if with_windows:
        payload["windows"] = [{
            "startSeconds": 0,
            "endSeconds": 30,
            "probe": probe(pairs=pairs),
        }]
    return payload


def dump(payload: dict) -> str:
    return json.dumps(
        payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


class RefreshVideoEvidenceSummariesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name) / "analysis"
        self.videos = self.root / "example" / "videos"
        self.videos.mkdir(parents=True)

    def write_record(self, name: str, payload: dict) -> Path:
        path = self.videos / name
        path.write_text(dump(payload), encoding="utf-8")
        return path

    def run_main(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = refresh.main(["--root", str(self.root), *args])
        return code, output.getvalue()

    def test_refresh_adds_validity_keys_to_legacy_record(self) -> None:
        path = self.write_record("legacy.json", record())
        code, output = self.run_main()
        self.assertEqual(code, 0)
        summary = json.loads(path.read_text(encoding="utf-8"))["summary"]
        self.assertEqual(tuple(summary)[:len(LEGACY_KEYS)], LEGACY_KEYS)
        for key in VALIDITY_KEYS:
            self.assertIn(key, summary)
        self.assertEqual(summary["cutCandidateCount"], 3)
        self.assertEqual(summary["withinShotPairs"], 4)
        self.assertEqual(summary["cutSeparatedPairs"], 2)
        self.assertEqual(summary["deltaBasisPairs"], 6)
        self.assertIn("changed=1", output)

    def test_second_run_writes_nothing_and_keeps_mtime(self) -> None:
        path = self.write_record("legacy.json", record())
        first_code, _ = self.run_main()
        self.assertEqual(first_code, 0)
        first_bytes = path.read_bytes()
        marker = 1_000_000_000
        os.utime(path, ns=(marker, marker))

        code, output = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(path.read_bytes(), first_bytes)
        self.assertEqual(path.stat().st_mtime_ns, marker)
        self.assertIn("changed=0", output)
        self.assertIn("unchanged=1", output)

    def test_record_without_windows_is_skipped(self) -> None:
        payload = record(with_windows=False)
        path = self.write_record("no-windows.json", payload)
        before = path.read_bytes()
        code, output = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(path.read_bytes(), before)
        self.assertIn("skipped=1", output)
        self.assertIn("changed=0", output)

    def test_dry_run_writes_nothing(self) -> None:
        path = self.write_record("legacy.json", record())
        before = path.read_bytes()
        code, output = self.run_main("--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(path.read_bytes(), before)
        self.assertIn("changed=1", output)
        self.assertIn("dry-run", output)

    def test_missing_frame_pairs_is_partial_and_preserves_stored_values(
        self,
    ) -> None:
        payload = record(pairs=False)
        payload["summary"]["deltaBasisPairs"] = 12
        payload["summary"]["meanWithinShotRgbDeltaPerSecond"] = 0.7
        path = self.write_record("partial.json", payload)

        code, output = self.run_main()
        self.assertEqual(code, 0)
        summary = json.loads(path.read_text(encoding="utf-8"))["summary"]
        self.assertEqual(summary["deltaBasisPairs"], 12)
        self.assertEqual(summary["meanWithinShotRgbDeltaPerSecond"], 0.7)
        self.assertIn("partial=1", output)


if __name__ == "__main__":
    unittest.main()
