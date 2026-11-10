"""Real-source calibration metadata must remain honest, bounded and verifiable offline."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.analyzers.media.inspect import inspect_source
from kumiki_reference_lab.catalog.open_footage import (
    load_open_footage, validate_open_footage, verify_open_footage_media,
)
from kumiki_reference_lab.cli.app import main


ROOT = Path(__file__).resolve().parents[1] / "research/open-footage-calibration.v1.json"


class OpenFootageTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_open_footage(ROOT)

    def test_real_source_registry_separates_measurements_reviews_and_audience(self):
        self.assertEqual(len(self.dataset["entries"]), 4)
        self.assertEqual(len({r["media"]["sha256"] for r in self.dataset["entries"]}), 4)
        for item in self.dataset["entries"]:
            self.assertEqual(item["audienceStatus"], "not-measured-for-this-file")
            self.assertEqual(item["frameObservations"]["reviewMode"],
                             "contact-sheets-only-no-full-speed-viewing")
            self.assertEqual(item["sample"]["startSeconds"], 0)
            self.assertEqual(item["sample"]["requestedSeconds"], 10)
            self.assertFalse(any(key.lower().startswith("viewcount") for key in item))
        paper = self.dataset["entries"][0]
        self.assertEqual(paper["sample"]["imageMotion"]["activeRuns"], 0)
        self.assertIn("title cards", paper["frameObservations"]["sampledWindowNote"])

    def test_fails_closed_for_mutated_source_and_unsupported_claims(self):
        mutations = (
            ("duplicate-id", lambda d: d["entries"].append(copy.deepcopy(d["entries"][0]))),
            ("fake-views", lambda d: d["entries"][0].update(viewCount=9000000)),
            ("fake-playback", lambda d: d["entries"][0]["frameObservations"].update(reviewMode="human-full-video-review")),
            ("fake-license", lambda d: d["entries"][0]["rights"].update(license="CC0")),
            ("unhashable-license", lambda d: d["entries"][0]["rights"].update(license=[])),
            ("license-url", lambda d: d["entries"][0]["rights"].update(licenseUrl="https://example.com/")),
            ("evil-download", lambda d: d["entries"][0]["media"].update(downloadUrl="https://evil.example/x")),
            ("path-traversal", lambda d: d["entries"][0]["media"].update(localName="../../outside.webm")),
            ("bad-source-sha", lambda d: d["entries"][0]["media"].update(sha256="x" * 64)),
            ("unknown-style", lambda d: d["entries"][0]["frameObservations"].update(visibleTags=["viral"])),
            ("negative-motion", lambda d: d["entries"][0]["sample"]["imageMotion"].update(activeRuns=-1)),
            ("bool-count", lambda d: d["entries"][0]["sample"]["imageMotion"].update(activeRuns=True)),
            ("bad-duration", lambda d: d["entries"][0]["media"].update(durationMilliseconds=False)),
            ("invalid-stream", lambda d: d["entries"][0]["media"].update(streamIndex=True)),
            ("invalid-timebase", lambda d: d["entries"][0]["media"].update(sourceTimebase={"numerator": 0, "denominator": 1})),
            ("changed-start", lambda d: d["entries"][0]["sample"].update(startSeconds=20)),
            ("oversized-window", lambda d: d["entries"][0]["sample"].update(requestedSeconds=100)),
            ("span-beyond-window", lambda d: d["entries"][0]["sample"]["imageMotion"].update(sampledSpanSeconds=20.0)),
        )
        for name, mutation in mutations:
            with self.subTest(name=name):
                example = copy.deepcopy(self.dataset)
                mutation(example)
                self.assertTrue(validate_open_footage(example))

    def test_cli_listing_and_invalid_file_guards(self):
        for action, key in (("validate", "entryCount"), ("list", "count")):
            with self.subTest(action=action):
                with io.StringIO() as output, contextlib.redirect_stdout(output):
                    self.assertEqual(main(["open-footage", action, "--root", str(ROOT)]), 0)
                    self.assertEqual(json.loads(output.getvalue())[key], 4)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            duplicate = dest / "duplicate.json"
            duplicate.write_text('{"schemaVersion":"a","schemaVersion":"b"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_open_footage(duplicate)
            alias = dest / "alias.json"
            alias.symlink_to(ROOT)
            with self.assertRaisesRegex(ValueError, "regular"):
                load_open_footage(alias)
            invalid_json = dest / "bad.json"
            invalid_json.write_text('{"x":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid"):
                load_open_footage(invalid_json)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "needs local FFmpeg/FFprobe; not required in lightweight hosted CI")
    def test_verification_checks_actual_decoded_source_not_only_declared_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            path = dest / "paper-stop-motion.webm"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                            "-f", "lavfi", "-i", "testsrc=size=160x90:rate=12:duration=1.5",
                            "-c:v", "libvpx", "-an", str(path)], check=True, timeout=30)
            detected = inspect_source(path)
            modified = copy.deepcopy(self.dataset)
            modified["entries"] = modified["entries"][:1]
            entry = modified["entries"][0]
            media = entry["media"]
            media.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         sizeBytes=path.stat().st_size,
                         durationMilliseconds=round(float(detected["video"]["durationSecondsReported"]) * 1000),
                         width=160, height=90,
                         sourceTimebase=detected["video"]["sourceTimebase"])
            self.assertTrue(verify_open_footage_media(modified, dest)["verifiedLocalMedia"])
            with self.assertRaisesRegex(ValueError, "reference ID not found"):
                verify_open_footage_media(modified, dest, reference_id="nonexistent")
            with self.assertRaisesRegex(ValueError, "do not match"):
                modified["entries"][0]["media"]["sizeBytes"] += 1
                verify_open_footage_media(modified, dest)
            modified["entries"][0]["media"]["sizeBytes"] -= 1
            correct_sha = media["sha256"]
            media["sha256"] = ("0" if correct_sha[0] != "0" else "1") + correct_sha[1:]
            with self.assertRaisesRegex(ValueError, "do not match"):
                verify_open_footage_media(modified, dest)
            media["sha256"] = correct_sha
            path.rename(dest / "other.webm")
            path.symlink_to(dest / "other.webm")
            with self.assertRaisesRegex(ValueError, "regular"):
                verify_open_footage_media(modified, dest)


if __name__ == "__main__":
    unittest.main()
