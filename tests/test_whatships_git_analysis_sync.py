"""Git in-place evidence sync: no silent overwrite, no private extra data, rollback."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kumiki_reference_lab.catalog.whatships_analysis_store import (
    export_repository_analysis, sync_repository_analysis,validate_repository_analysis,
)
from kumiki_reference_lab.cli.app import main
from tests.test_video_sources import whatships_fixture


class WhatshipsGitAnalysisSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.snapshot=self.root/"catalog.json"
        self.snapshot.write_text(json.dumps(whatships_fixture()))
        self.store=self.root/"tracked-research"
        self.incoming=self.root/"new-export"
        self.spot1=self.root/"spot1.json"
        self.spot2=self.root/"spot2.json"
        self.make_spot(self.spot1,"film-one","A paper card folds through the layout.")
        self.make_spot(self.spot2,"film-two","A product video has a changing colorful screen.")
        export_repository_analysis(self.snapshot,self.store,observations_path=self.spot1)

    def make_spot(self,path,slug,moment):
        path.write_text(json.dumps({
            "schemaVersion":"kumiki.browser-video-observations.v1",
            "reviewedOn":"2026-11-10",
            "methodology":"selected site viewing observations",
            "observations":[{
                "sourceId":"whatships:"+slug,"reviewedOn":"2026-11-10",
                "method":"browser-player","coverage":"selected-moments-only",
                "visualTags":["product-visual"],"visibleMoments":[moment],
                "techniqueHypotheses":["Prototype this presentation without claiming it drove popularity."],
            }],
        }))

    def test_merges_new_video_without_erasing_old_observation(self):
        export_repository_analysis(self.snapshot,self.incoming,observations_path=self.spot2)
        result=sync_repository_analysis(self.snapshot,self.incoming,self.store)
        self.assertEqual(result["previousVideoEvidenceRecords"],1)
        self.assertEqual(result["mergedVideoEvidenceRecords"],2)
        self.assertEqual(result["recordsChangedOrAdded"],1)
        self.assertEqual(validate_repository_analysis(self.store,self.snapshot)
                         ["sourceLinkedAnalysisRecords"],2)
        self.assertIn("paper card",(self.store/"film-one.json").read_text())
        self.assertIn("changing colorful screen",(self.store/"film-two.json").read_text())
        again=sync_repository_analysis(self.snapshot,self.incoming,self.store)
        self.assertEqual(again["recordsChangedOrAdded"],0)

    def test_conflicting_evidence_needs_explicit_replace(self):
        self.make_spot(self.spot2,"film-one","New observation from a different review.")
        export_repository_analysis(self.snapshot,self.incoming,observations_path=self.spot2)
        original=(self.store/"film-one.json").read_bytes()
        before=(self.store/"index.json").read_bytes()
        with self.assertRaisesRegex(ValueError,"explicit --replace-existing"):
            sync_repository_analysis(self.snapshot,self.incoming,self.store)
        self.assertEqual((self.store/"film-one.json").read_bytes(),original)
        self.assertEqual((self.store/"index.json").read_bytes(),before)
        summary=sync_repository_analysis(
            self.snapshot,self.incoming,self.store,replace_existing=True)
        self.assertEqual(summary["recordsChangedOrAdded"],1)
        self.assertIn("New observation",(self.store/"film-one.json").read_text())
        self.assertEqual(validate_repository_analysis(self.store,self.snapshot)
                         ["browserSpotChecks"],1)

    def test_additional_character_status_keeps_existing_browser_evidence(self):
        self.make_spot(self.spot2,"film-one","A paper card folds through the layout.")
        export_repository_analysis(self.snapshot,self.incoming,observations_path=self.spot2)
        path=self.incoming/"film-one.json"
        row=json.loads(path.read_text())
        row["evidence"]["characterStudyStatus"]={
            "status":"completed-unreviewed-model-proposals",
            "detail":"Raw model scenes remain in private local study artifacts; not imported or human certified.",
        }
        row["coverage"]["hasUnreviewedCharacterJob"]=True
        path.write_text(json.dumps(row))
        indexfile=self.incoming/"index.json"
        index=json.loads(indexfile.read_text())
        index["entries"][0]["evidenceKinds"].append("characterStudyStatus")
        index["entries"][0]["evidenceKinds"].sort()
        index["unreviewedCharacterJobCount"]=1
        indexfile.write_text(json.dumps(index))
        sync_repository_analysis(self.snapshot,self.incoming,self.store)
        result=json.loads((self.store/"film-one.json").read_text())
        self.assertIn("browserSpotCheck",result["evidence"])
        self.assertIn("characterStudyStatus",result["evidence"])
        self.assertFalse(result["coverage"]["fullFilmReviewed"])

    def test_rejects_unapproved_private_path_or_fake_complete_review(self):
        export_repository_analysis(self.snapshot,self.incoming,observations_path=self.spot2)
        path=self.incoming/"film-two.json"
        row=json.loads(path.read_text())
        row["localVideoPath"]="/Users/private/secret-film.mp4"
        path.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError,"approved fields"):
            sync_repository_analysis(self.snapshot,self.incoming,self.store)
        row.pop("localVideoPath")
        row["coverage"]["fullFilmReviewed"]=True
        path.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError,"review coverage claims"):
            sync_repository_analysis(self.snapshot,self.incoming,self.store)
        self.assertFalse((self.store/"film-two.json").exists())

    def test_invalid_snapshot_or_tampered_source_fails_before_writing(self):
        export_repository_analysis(self.snapshot,self.incoming,observations_path=self.spot2)
        self.snapshot.write_text(self.snapshot.read_text()+" ")
        with self.assertRaisesRegex(ValueError,"snapshot"):
            sync_repository_analysis(self.snapshot,self.incoming,self.store)
        self.assertFalse((self.store/"film-two.json").exists())

    def test_atomic_file_rollback_if_index_write_fails(self):
        export_repository_analysis(self.snapshot,self.incoming,observations_path=self.spot2)
        from kumiki_reference_lab.catalog import whatships_analysis_store as mod
        original=mod._atomic_write_bytes
        state={"calls":0}
        def failing(path,content):
            state["calls"]+=1
            if path.name=="index.json":
                raise OSError("synthetic disk error on index update")
            return original(path,content)
        before=(self.store/"index.json").read_bytes()
        with patch.object(mod,"_atomic_write_bytes",side_effect=failing):
            with self.assertRaisesRegex(OSError,"synthetic disk error"):
                sync_repository_analysis(self.snapshot,self.incoming,self.store)
        self.assertEqual((self.store/"index.json").read_bytes(),before)
        self.assertFalse((self.store/"film-two.json").exists())
        self.assertEqual(validate_repository_analysis(self.store,self.snapshot)
                         ["sourceLinkedAnalysisRecords"],1)

    def test_cli_updates_git_worktree(self):
        export_repository_analysis(self.snapshot,self.incoming,observations_path=self.spot2)
        import contextlib,io
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code=main([
                "whatships-all","sync-analysis","--snapshot",str(self.snapshot),
                "--incoming",str(self.incoming),"--root",str(self.store),
            ])
        self.assertEqual(exit_code,0)
        report=json.loads(output.getvalue())
        self.assertEqual(report["mergedVideoEvidenceRecords"],2)
        self.assertIn("git add/commit",report["note"])


if __name__=="__main__":
    unittest.main()
