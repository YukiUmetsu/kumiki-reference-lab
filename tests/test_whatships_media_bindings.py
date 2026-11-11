"""Explicit rights, exact catalog IDs and private source file hash protections."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.catalog.whatships_media_bindings import (
    eligible_bound_media, load_media_bindings, media_coverage, register_local_media,
)
from kumiki_reference_lab.catalog.video_sources import _load_snapshot
from kumiki_reference_lab.cli.app import main
from tests.test_video_sources import whatships_fixture


class WhatshipsMediaBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = self.root/"whatships.json"
        self.snapshot.write_text(json.dumps(whatships_fixture()))
        self.video = self.root/"authorized-clip.mp4"
        self.video.write_bytes(b"original simulated video source; ffprobe mocked")
        self.out = self.root/"binding-run"
        self.note = ("Permission to study this supplied video for private research; "
                     "no publication or redistribution authorized.")
        self.match = ("I compared the clip's opening and product title with the "
                      "exact What Ships page for film-one.")
        self.sha = hashlib.sha256(self.video.read_bytes()).hexdigest()

    def info(self, source, *, ffprobe, rights_status):
        self.assertEqual(rights_status, "user-declared-authorized")
        return {
            "source": {"sha256": self.sha, "sizeBytes": source.stat().st_size,
                       "rightsStatus": rights_status},
            "video": {"streamIndex": 0,
                      "sourceTimebase": {"numerator": 1, "denominator": 1000}},
        }

    def bind(self, *, previous=None, source_id="whatships:film-one",
             video=None, rights_note=None, identity_note=None,
             acknowledge_rights=True):
        with patch(
            "kumiki_reference_lab.catalog.whatships_media_bindings.inspect_source",
            side_effect=self.info,
        ):
            return register_local_media(
                self.snapshot, video or self.video, source_id, self.out,
                previous=previous, rights_basis="written-permission",
                rights_note=rights_note or self.note,
                identity_note=identity_note or self.match,
                acknowledge_rights=acknowledge_rights,
            )

    def test_binding_records_sha_and_never_claims_verified_rights(self):
        path = self.bind()
        doc = json.loads(path.read_text())
        self.assertEqual(doc["schemaVersion"], "kumiki.whatships-local-media-bindings.v1")
        self.assertEqual(len(doc["bindings"]), 1)
        row = doc["bindings"][0]
        self.assertEqual(row["sourceId"], "whatships:film-one")
        self.assertEqual(row["watchUrl"], "https://whatships.com/videos/film-one/")
        self.assertEqual(row["localPath"], str(self.video.resolve()))
        self.assertEqual(row["mediaSha256"], self.sha)
        self.assertEqual(row["rightsStatus"], "user-declared-authorized")
        self.assertEqual(row["verificationStatus"],
                         "operator-attestation-not-independently-verified")
        summary = json.loads((self.out/"coverage.json").read_text())
        self.assertEqual(summary["indexedVideoCount"], 2)
        self.assertEqual(summary["boundMediaCount"], 1)
        self.assertEqual(summary["actuallyAnalyzedVideoCount"], 0)
        self.assertNotIn(str(self.root), json.dumps(summary))
        verified = media_coverage(self.snapshot, path, verify_files=True)
        self.assertEqual(verified["physicalVerification"], "sha256-rechecked")
        plan = eligible_bound_media(self.snapshot, path)
        self.assertEqual(plan["eligibleVerifiedBindings"], 1)
        self.assertEqual(plan["entries"][0]["sourceId"], "whatships:film-one")
        self.assertNotIn(str(self.root), json.dumps(plan))
        with self.assertRaisesRegex(ValueError, "new directory"):
            self.bind()

    def test_rejects_unacknowledged_rights_and_unknown_catalog_id(self):
        with self.assertRaisesRegex(ValueError, "explicitly acknowledge"):
            self.bind(acknowledge_rights=False)
        with self.assertRaisesRegex(ValueError, "unknown indexed"):
            self.bind(source_id="whatships:fictional-nonexistent")
        self.assertFalse(self.out.exists())

    def test_rejects_false_path_symlink_and_remote_watch_url(self):
        alias = self.root/"symlink.mp4"
        alias.symlink_to(self.video)
        with self.assertRaisesRegex(ValueError, "symlink/URL"):
            self.bind(video=alias)
        with self.assertRaisesRegex(ValueError, "regular supported"):
            self.bind(video=Path("https://whatships.com/videos/film-one/"))
        self.assertFalse(self.out.exists())

    def test_source_hash_changes_fail_closed_on_verified_queue(self):
        path = self.bind()
        self.video.write_bytes(b"other video, maybe same name")
        with self.assertRaisesRegex(ValueError, "differs from registered"):
            eligible_bound_media(self.snapshot, path)
        # A cheap metadata report MUST say it has not rehashed source media.
        summary = media_coverage(self.snapshot, path)
        self.assertEqual(summary["physicalVerification"], "not-performed")

    def test_immutable_add_second_source_and_reject_same_video_for_other_id(self):
        first = self.bind()
        next_output = self.root/"second-run"
        self.out = next_output
        self.sha = hashlib.sha256(self.video.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "same local video"):
            self.bind(previous=first, source_id="whatships:film-two")
        distinct = self.root/"different.mp4"
        distinct.write_bytes(b"separate authorized video")
        self.sha = hashlib.sha256(distinct.read_bytes()).hexdigest()
        second = self.bind(previous=first, source_id="whatships:film-two", video=distinct)
        self.assertEqual(len(json.loads(second.read_text())["bindings"]), 2)
        self.assertEqual(len(json.loads(first.read_text())["bindings"]), 1)

    def test_duplicate_or_malformed_binding_never_becomes_eligible(self):
        path = self.bind()
        doc = json.loads(path.read_text())
        for mutate in (
            lambda x: x["bindings"][0].update(rightsStatus="independently-certified"),
            lambda x: x["bindings"][0].update(watchUrl="https://malicious.test/clip"),
            lambda x: x["bindings"][0].update(mediaSha256="1"*64),
            lambda x: x["bindings"][0].update(sourceId="whatships:unknown"),
            lambda x: x["bindings"][0].update(localPath="https://bad.test/test.mp4"),
            lambda x: x["bindings"][0].update(rightsNote="tiny"),
            lambda x: x["bindings"].append(copy.deepcopy(x["bindings"][0])),
        ):
            modified = copy.deepcopy(doc)
            mutate(modified)
            tmp = self.root/"changed.json"
            tmp.write_text(json.dumps(modified))
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                eligible_bound_media(self.snapshot, tmp)

    def test_cli_private_bind_and_redacted_report(self):
        with patch(
            "kumiki_reference_lab.catalog.whatships_media_bindings.inspect_source",
            side_effect=self.info,
        ):
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                exit_code = main([
                    "whatships-media", "bind",
                    "whatships:film-one", str(self.video),
                    "--snapshot", str(self.snapshot),
                    "--rights-basis", "written-permission",
                    "--rights-note", self.note,
                    "--identity-note", self.match,
                    "--acknowledge-rights", "--out", str(self.out),
                ])
        self.assertEqual(exit_code, 0)
        self.assertEqual(Path(capture.getvalue().strip()),
                         self.out/"media-bindings.json")
        report = io.StringIO()
        with contextlib.redirect_stdout(report):
            result = main([
                "whatships-media", "report",
                str(self.out/"media-bindings.json"),
                "--snapshot", str(self.snapshot),
            ])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(report.getvalue())["boundMediaCount"], 1)
        self.assertNotIn(str(self.root), report.getvalue())

    def test_default_catalog_counts_all_2861_as_unbound_if_no_local_media(self):
        path = self.root/"empty-ledger.json"
        path.write_text(json.dumps({
            "schemaVersion": "kumiki.whatships-local-media-bindings.v1",
            "createdOn": "2026-11-10",
            "catalogIndexUrl": "https://whatships.com/search-index.json",
            "disclaimer": "self-declared-source-identity-and-authorization-only",
            "bindings": [],
        }))
        snapshot = Path(__file__).resolve().parents[1]/"research/whatships-index-2026-11-10.json"
        report = media_coverage(snapshot, path, verify_files=False)
        self.assertEqual(report["indexedVideoCount"], 2861)
        self.assertEqual(report["boundMediaCount"], 0)
        self.assertEqual(report["unboundVideoCount"], 2861)


if __name__ == "__main__":
    unittest.main()
