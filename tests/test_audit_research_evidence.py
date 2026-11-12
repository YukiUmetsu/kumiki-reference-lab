"""Offline tests for the on-disk research evidence auditor.

The fixtures are tiny synthetic record trees; no network, ffmpeg, or real
``research/analysis`` data is touched. Every test builds its own temporary
root so the suite stays fast and order-independent.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_research_evidence import main, run_audit

GOOD_SHA = "a" * 64
GOOD_IMAGE_SHA = "b" * 64


def _appearance(luma: float, saturation: float) -> dict[str, object]:
    return {
        "meanRgb": [luma, luma, luma],
        "meanDisplayLumaProxy": luma,
        "displayLumaStdDev": 0.1,
        "meanSaturationProxy": saturation,
        "shadowPixelFraction": 0.5,
        "brightPixelFraction": 0.1,
    }


def _frame(pts: int, luma: float, saturation: float) -> dict[str, object]:
    return {
        "sourcePts": pts,
        "sourceSeconds": {"numerator": pts, "denominator": 30000},
        "appearance": _appearance(luma, saturation),
    }


def _pair(
    start_pts: int, end_pts: int, *, status: str,
    delta: float | None, delta_per_second: float | None,
) -> dict[str, object]:
    return {
        "startPts": start_pts,
        "endPts": end_pts,
        "sourceDeltaSeconds": {
            "numerator": end_pts - start_pts, "denominator": 30000,
        },
        "status": status,
        "meanAbsoluteDisplayRgbDelta": delta,
        "meanAbsoluteDisplayRgbDeltaPerSecond": delta_per_second,
    }


def _window(
    start: int, end: int, *, luma: float, saturation: float,
    cuts: list[int], pairs: list[dict[str, object]],
    delta: float, within: int, cut_separated: int,
) -> dict[str, object]:
    pts = [start * 30000 + offset for offset in (0, (end - start) * 15000,
                                                 (end - start) * 30000)]
    frames = [_frame(value, luma, saturation) for value in pts]
    requested = end - start
    return {
        "startSeconds": start,
        "endSeconds": end,
        "probe": {
            "schemaVersion": "kumiki.source-pts-visual-probe.v1",
            "sourceSha256": GOOD_SHA,
            "sourceStreamIndex": 0,
            "sourceTimebase": {"numerator": 1, "denominator": 30000},
            "rightsStatus": "user-declared-authorized",
            "scan": {
                "startSeconds": start,
                "requestedSeconds": requested,
                "sourceWindowEndSeconds": end,
                "decoder": "test",
                "frameWidth": 160,
                "frameHeight": 90,
                "sampledSourcePtsCount": len(frames),
                "sampledPtsStart": pts[0],
                "sampledPtsEnd": pts[-1],
                "cutThreshold": 0.25,
                "sourceTimebaseVerified": True,
            },
            "cutCandidatePts": cuts,
            "sampledFrames": frames,
            "sampledFramePairs": pairs,
            "sampledWindowSummary": {
                "cutCandidateCountBetweenFirstAndLastSample": len(cuts),
                "cutCandidateRatePerRequestedMinute": len(cuts) * 60 / requested,
                "meanSampledDisplayLumaProxy": luma,
                "meanSampledSaturationProxy": saturation,
                "meanWithinShotDisplayRgbDelta": delta,
                "withinShotComparedPairs": within,
                "cutSeparatedPairs": cut_separated,
            },
            "evidenceStatus": "test",
            "methodLimits": [],
        },
    }


def good_video(record_id: int = 1, sha: str = GOOD_SHA) -> dict[str, object]:
    window_zero = _window(
        0, 10, luma=0.2, saturation=0.3, cuts=[],
        pairs=[
            _pair(0, 150000, status="rgb-image-difference-proxy",
                  delta=0.1, delta_per_second=0.02),
            _pair(150000, 300000, status="rgb-image-difference-proxy",
                  delta=0.1, delta_per_second=0.03),
        ],
        delta=0.1, within=2, cut_separated=0,
    )
    window_one = _window(
        20, 30, luma=0.4, saturation=0.5, cuts=[660000],
        pairs=[
            _pair(600000, 750000, status="cut-candidate-between-samples",
                  delta=None, delta_per_second=None),
            _pair(750000, 900000, status="rgb-image-difference-proxy",
                  delta=0.2, delta_per_second=0.04),
        ],
        delta=0.2, within=1, cut_separated=1,
    )
    return {
        "schemaVersion": "kumiki.demo-video-evidence.v1",
        "clipId": record_id,
        "slug": f"demo-{record_id}",
        "source": {
            "mediaSha256": sha,
            "durationSeconds": 100.0,
            "resolution": [1280, 720],
            "frameRate": {"numerator": 30, "denominator": 1},
            "sourceTimebase": {"numerator": 1, "denominator": 30000},
            "container": "mp4",
        },
        "acquisition": {
            "provider": "test",
            "videoUrl": "https://example.invalid/clip.mp4",
            "method": "test",
            "mediaRetained": False,
            "attestation": {"rightsBasis": "test", "note": "test"},
        },
        "coverage": {
            "windowsMeasured": 2,
            "windowSeconds": 10,
            "sampledSeconds": 20,
            "fractionOfRuntime": 0.2,
            "fullRuntimeMeasured": False,
        },
        "windows": [window_zero, window_one],
        "summary": {
            "cutCandidates": 1,
            "cutCandidateRatePerMinute": 3.0,
            "meanDisplayLuma": 0.3,
            "meanSaturation": 0.4,
            "meanWithinShotRgbDeltaPerSecond": 0.03,
            "sampledFrames": 6,
            "windowsWithCuts": 1,
        },
        "evidenceStatus": "test",
        "rightsStatus": "review-required",
        "limits": [],
        "generatedAt": "2026-01-01T00:00:00Z",
    }


def good_still(record_id: int = 1, sha: str = GOOD_IMAGE_SHA) -> dict[str, object]:
    return {
        "schemaVersion": "kumiki.demo-still-evidence.v1",
        "clipId": record_id,
        "slug": f"still-{record_id}",
        "still": {
            "imageUrl": "https://example.invalid/poster.jpg",
            "imageSha256": sha,
            "imageFormat": "jpg",
            "imageBytes": 200000,
            "imageWidth": 1280,
            "imageHeight": 720,
            "metrics": {
                "meanRgb": [0.2, 0.2, 0.2],
                "meanDisplayLumaProxy": 0.2,
                "displayLumaStdDev": 0.1,
                "meanSaturationProxy": 0.1,
                "shadowPixelFraction": 0.5,
                "brightPixelFraction": 0.1,
                "lumaHistogram": [0.2, 0.2, 0.2, 0.2, 0.2],
                "dominantHueFamily": "neutral",
                "edgeDensityProxy": 0.05,
            },
        },
        "acquisition": {"method": "test", "imageRetained": False},
        "coverage": {
            "isSourceVideoFrame": True,
            "note": "test",
        },
        "evidenceStatus": "test",
        "limits": [],
        "generatedAt": "2026-01-01T00:00:00Z",
    }


class AuditorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        (self.root / "demo" / "videos").mkdir(parents=True)
        (self.root / "demo" / "stills").mkdir(parents=True)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def write(self, folder: str, name: str, payload: object) -> Path:
        path = self.root / "demo" / folder / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def rules(self, report: dict[str, object]) -> list[str]:
        return [finding["rule"] for finding in report["findings"]]

    def exit_code(self, *arguments: str) -> int:
        with contextlib.redirect_stdout(io.StringIO()):
            return main(["--root", str(self.root), *arguments])

    def test_clean_tree_has_no_findings(self) -> None:
        self.write("videos", "1-demo.json", good_video(1))
        # A still for a *different* work must not create a cross-family pair.
        self.write("stills", "2-demo.json", good_still(2))
        report = run_audit(self.root)
        self.assertEqual(report["findings"], [])
        counts = report["sites"]["demo"]["recordCounts"]
        self.assertEqual(counts, {"video": 1, "still": 1, "unclassified": 0})

    def test_clean_tree_exits_zero(self) -> None:
        self.write("videos", "1-demo.json", good_video(1))
        self.write("stills", "2-demo.json", good_still(2))
        self.assertEqual(self.exit_code(), 0)

    def test_bad_window_arithmetic_is_error(self) -> None:
        record = good_video()
        summary = record["windows"][0]["probe"]["sampledWindowSummary"]
        summary["meanSampledDisplayLumaProxy"] = 0.9
        summary["withinShotComparedPairs"] = 99
        record["windows"][0]["endSeconds"] = 12
        self.write("videos", "1-demo.json", record)
        report = run_audit(self.root)
        rules = self.rules(report)
        self.assertIn("arithmetic.window-luma", rules)
        self.assertIn("arithmetic.window-within-pairs", rules)
        self.assertIn("arithmetic.window-span", rules)
        self.assertIn("arithmetic.record-summary", rules)
        self.assertEqual(report["summary"]["bySeverity"]["error"], 4)

    def test_bad_coverage_fraction_is_error(self) -> None:
        record = good_video()
        record["coverage"]["fractionOfRuntime"] = 0.9
        self.write("videos", "1-demo.json", record)
        report = run_audit(self.root)
        self.assertIn("arithmetic.coverage-fraction", self.rules(report))

    def test_duplicate_sha_pair_is_one_warning(self) -> None:
        self.write("videos", "1-demo.json", good_video(1))
        self.write("videos", "2-demo.json", good_video(2))
        report = run_audit(self.root)
        findings = [finding for finding in report["findings"]
                    if finding["rule"] == "duplicate.source-sha256"]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["severity"], "warning")
        self.assertEqual(finding["class"], "same-media-same-site-same-family")
        self.assertEqual(len(finding["group"]), 2)
        self.assertEqual(
            {member["path"] for member in finding["group"]},
            {"demo/videos/1-demo.json", "demo/videos/2-demo.json"})
        self.assertEqual(report["summary"]["bySeverity"]["error"], 0)
        self.assertEqual(report["summary"]["duplicates"]["groups"], 1)
        self.assertEqual(
            report["summary"]["duplicates"]["byClass"][finding["class"]], 1)

    def test_cross_site_duplicate_class(self) -> None:
        other = self.root / "other" / "videos"
        other.mkdir(parents=True)
        (other / "9-other.json").write_text(
            json.dumps(good_video(9)), encoding="utf-8")
        self.write("videos", "1-demo.json", good_video(1))
        report = run_audit(self.root)
        findings = [finding for finding in report["findings"]
                    if finding["rule"] == "duplicate.source-sha256"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["class"], "same-media-cross-site")
        self.assertEqual(
            {member["site"] for member in findings[0]["group"]},
            {"demo", "other"})

    def test_cross_family_pair_is_one_expected_warning(self) -> None:
        self.write("videos", "1-demo.json", good_video(1))
        self.write("stills", "1-demo.json", good_still(1))
        report = run_audit(self.root)
        findings = [finding for finding in report["findings"]
                    if finding["rule"] == "duplicate.media-cross-family"]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["severity"], "warning")
        self.assertEqual(finding["class"], "same-media-cross-family")
        self.assertEqual(
            {(member["site"], member["family"], member["id"])
             for member in finding["group"]},
            {("demo", "video", 1), ("demo", "still", 1)})
        self.assertIn("expected", finding["detail"])
        self.assertEqual(report["summary"]["bySeverity"]["error"], 0)

    def test_warnings_only_tree_exits_zero(self) -> None:
        self.write("videos", "1-demo.json", good_video(1))
        self.write("videos", "2-demo.json", good_video(2))
        self.assertEqual(self.exit_code(), 0)

    def test_strict_duplicates_exits_one(self) -> None:
        self.write("videos", "1-demo.json", good_video(1))
        self.write("videos", "2-demo.json", good_video(2))
        report = run_audit(self.root, strict_duplicates=True)
        self.assertEqual(report["summary"]["bySeverity"]["error"], 1)
        self.assertEqual(self.exit_code("--strict-duplicates"), 1)

    def test_integrity_error_exits_one(self) -> None:
        record = good_video()
        record["coverage"]["fractionOfRuntime"] = 0.9
        self.write("videos", "1-demo.json", record)
        self.assertEqual(self.exit_code(), 1)

    def test_duplicate_identity_is_still_an_error(self) -> None:
        self.write("videos", "1-demo.json", good_video(1, sha="a" * 64))
        self.write("videos", "2-demo.json", good_video(1, sha="c" * 64))
        report = run_audit(self.root)
        self.assertIn("duplicate.identity", self.rules(report))
        self.assertEqual(report["summary"]["bySeverity"]["error"], 1)

    def test_bad_histogram_still_is_error(self) -> None:
        record = good_still()
        record["still"]["metrics"]["lumaHistogram"] = [0.5, 0.5, 0.5, 0.5, 0.5]
        self.write("stills", "1-demo.json", record)
        report = run_audit(self.root)
        self.assertIn("still.histogram-sum", self.rules(report))

    def test_unreadable_file_is_error(self) -> None:
        (self.root / "demo" / "videos" / "broken.json").write_text(
            "{not valid json", encoding="utf-8")
        report = run_audit(self.root)
        self.assertIn("json.parse", self.rules(report))
        self.assertEqual(
            report["sites"]["demo"]["recordCounts"]["unclassified"], 1)

    def test_unknown_schema_is_error(self) -> None:
        record = copy.deepcopy(good_video())
        record["schemaVersion"] = "not-a-kumiki-schema"
        self.write("videos", "1-demo.json", record)
        report = run_audit(self.root)
        self.assertIn("schema.unknown", self.rules(report))

    def test_index_count_mismatch_is_warn_only(self) -> None:
        self.write("videos", "1-demo.json", good_video())
        (self.root / "demo" / "index.json").write_text(json.dumps({
            "counts": {"measured": 5},
            "records": [],
        }), encoding="utf-8")
        report = run_audit(self.root)
        self.assertIn("index.count-mismatch", self.rules(report))
        self.assertEqual(report["summary"]["bySeverity"]["error"], 0)
        self.assertEqual(report["summary"]["bySeverity"]["warning"], 1)

    def test_site_filter(self) -> None:
        other = self.root / "other" / "videos"
        other.mkdir(parents=True)
        (other / "9-other.json").write_text(
            json.dumps(good_video(9, sha="c" * 64)), encoding="utf-8")
        self.write("videos", "1-demo.json", good_video())
        report = run_audit(self.root, ["demo"])
        self.assertEqual(list(report["sites"]), ["demo"])


if __name__ == "__main__":
    unittest.main()
