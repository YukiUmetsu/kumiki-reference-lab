import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kumiki_reference_lab.pipeline.analyze import run_analysis
from kumiki_reference_lab.contracts.analysis import ANALYSIS_RUN_VERSION, ANALYSIS_RUN_RESEED_VERSION


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/FFprobe binaries unavailable")
class AnalysisPipelineIntegrationTests(unittest.TestCase):
    def _flat_video(self, source: Path) -> None:
        process = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=10:d=1",
            "-c:v", "ffv1", str(source),
        ], capture_output=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))

    def test_transactional_analysis_creates_complete_bundle_and_reuses_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            output = root / "runs"
            manifest_path = run_analysis(source, output, seconds=2, thumbnails=5)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["interpretationStatus"], "not-performed")
            self.assertEqual(manifest["catalogProposals"], [])
            self.assertEqual(set(manifest["artifacts"]), {"inspect", "frames", "cuts", "contactSheet"})
            for relative in manifest["artifacts"].values():
                self.assertTrue((manifest_path.parent / relative).is_file())
            self.assertEqual(run_analysis(source, output, seconds=2, thumbnails=5),
                             manifest_path)
            self.assertEqual(len(list(output.glob("analysis-*"))), 1)
            self.assertGreaterEqual(len(manifest["files"]), 7)

    def test_corruption_blocks_idempotent_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            output = root / "runs"
            manifest_path = run_analysis(source, output, seconds=2)
            manifest = json.loads(manifest_path.read_text())
            image = next(item["path"] for item in manifest["files"]
                         if item["path"].endswith(".jpg"))
            (manifest_path.parent / image).write_bytes(b"corruption")
            with self.assertRaisesRegex(ValueError, "missing or modified"):
                run_analysis(source, output, seconds=2)

    def test_modified_run_metadata_cannot_claim_interpretation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            output = root / "runs"
            manifest_path = run_analysis(source, output, seconds=2)
            manifest = json.loads(manifest_path.read_text())
            manifest["interpretationStatus"] = "complete"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "altered stage metadata"):
                run_analysis(source, output, seconds=2)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy extra unavailable")
    def test_motion_run_is_integrated_and_failed_roi_never_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            result = run_analysis(source, root / "good", seconds=2, motion=True,
                                  samples=10)
            manifest = json.loads(result.read_text())
            self.assertIn("motion", manifest["artifacts"])
            self.assertTrue((result.parent / "image-motion.json").is_file())

            failed_output = root / "failed"
            with self.assertRaisesRegex(ValueError, "insufficient texture"):
                run_analysis(source, failed_output, seconds=2,
                             roi=(0.2, 0.2, 0.1, 0.2), samples=10)
            self.assertEqual(list(failed_output.iterdir()), [])

    def test_invalid_budget_does_not_create_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs"
            with self.assertRaisesRegex(ValueError, "between 1 and 30"):
                run_analysis(Path("missing.mp4"), output, seconds=200)
            self.assertFalse(output.exists())

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy motion extra unavailable")
    def test_roi_reseeds_have_distinct_immutable_run_identity(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "patch.mkv"
            patch = np.random.default_rng(63).integers(0, 255, (18, 24), dtype=np.uint8)
            frames = []
            for i in range(12):
                frame = np.zeros((90, 160), dtype=np.uint8)
                if i not in (4, 5, 6):
                    frame[20+i:38+i, 30+2*i:54+2*i] = patch
                frames.append(frame.tobytes())
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "rawvideo", "-pixel_format", "gray", "-video_size", "160x90",
                "-framerate", "10", "-i", "-", "-c:v", "ffv1", str(source),
            ], input=b"".join(frames), capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
            from kumiki_reference_lab.analyzers.subjects.roi import analyze_roi_track
            seed = (30/160, 20/90, 24/160, 18/90)
            pts = analyze_roi_track(source, seed, seconds=2, max_samples=12,
                                    cut_threshold=0.95)["observations"][7]["sourcePts"]
            reseeds = [{"sourcePts": pts, "box": [44/160, 27/90, 24/160, 18/90]}]
            runs = root / "runs"
            default = run_analysis(source, runs, seconds=2, roi=seed, samples=12,
                                   threshold=0.95)
            manual = run_analysis(source, runs, seconds=2, roi=seed, samples=12,
                                  roi_reseeds=reseeds, threshold=0.95)
            self.assertNotEqual(default, manual)
            manifest = json.loads(manual.read_text())
            self.assertEqual(manifest["settings"]["roiReseeds"], reseeds)
            self.assertEqual(manifest["schemaVersion"], ANALYSIS_RUN_RESEED_VERSION)
            self.assertEqual(run_analysis(source, runs, seconds=2, roi=seed, samples=12,
                                          roi_reseeds=reseeds, threshold=0.95), manual)
            artifact = json.loads((manual.parent / "roi-track.json").read_text())
            self.assertEqual(artifact["observations"][7]["status"], "manual-reseed")
            self.assertNotIn("roiReseeds", json.loads(default.read_text())["settings"])
            self.assertEqual(json.loads(default.read_text())["schemaVersion"], ANALYSIS_RUN_VERSION)
            if importlib.util.find_spec("cv2") and importlib.util.find_spec("jsonschema"):
                from jsonschema import Draft202012Validator

                combined = run_analysis(
                    source, runs, seconds=2, roi=seed, samples=12,
                    roi_reseeds=reseeds, sparse_flow=True, sparse_samples=8,
                    sparse_model_validation=True, dense_flow=True, dense_samples=8,
                    threshold=0.95,
                )
                combined_manifest = json.loads(combined.read_text())
                schema = json.loads((Path(__file__).resolve().parents[1] /
                                     "schemas/v2/analysis-run.schema.json").read_text())
                Draft202012Validator(schema).validate(combined_manifest)
                self.assertEqual({"sparseFlow", "denseFlow", "trackRoi"} &
                                 combined_manifest["artifacts"].keys(),
                                 {"sparseFlow", "denseFlow", "trackRoi"})

    def test_roi_reseeds_require_an_initial_seed_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs"
            with self.assertRaisesRegex(ValueError, "ROI box"):
                run_analysis(Path("missing.mp4"), output,
                             roi_reseeds=[{"sourcePts": 20, "box": [0.2, 0.2, 0.2, 0.2]}])
            self.assertFalse(output.exists())

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy extra unavailable")
    def test_sparse_flow_stage_is_opt_in_atomic_and_checksummed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            output = root / "runs"
            manifest_path = run_analysis(source, output, seconds=2, thumbnails=4,
                                         sparse_flow=True, sparse_samples=6)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["artifacts"]["sparseFlow"], "sparse-flow.json")
            self.assertEqual(manifest["settings"]["sparseSamples"], 6)
            self.assertEqual(manifest["settings"]["versions"]["sparseFlow"],
                             "kumiki.sparse-flow.v1")
            sparse_path = manifest_path.parent / "sparse-flow.json"
            sparse = json.loads(sparse_path.read_text())
            self.assertEqual(sparse["schemaVersion"], "kumiki.sparse-flow.v1")
            self.assertTrue(all(pair["status"] == "insufficient-consensus"
                                for pair in sparse["pairs"]))
            self.assertEqual(run_analysis(source, output, seconds=2, thumbnails=4,
                                          sparse_flow=True, sparse_samples=6), manifest_path)
            sparse_path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "missing or modified"):
                run_analysis(source, output, seconds=2, thumbnails=4,
                             sparse_flow=True, sparse_samples=6)

    def test_invalid_sparse_budget_does_not_publish_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs"
            with self.assertRaisesRegex(ValueError, "sparse-flow requires"):
                run_analysis(Path("missing.mp4"), output, seconds=30, sparse_flow=True)
            self.assertFalse(output.exists())

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy extra unavailable")
    def test_opt_in_sparse_pyramid_has_separate_atomic_run_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            runs = root / "runs"
            baseline = run_analysis(source, runs, seconds=2, thumbnails=4,
                                    sparse_flow=True, sparse_samples=5)
            multiscale = run_analysis(source, runs, seconds=2, thumbnails=4,
                                      sparse_flow=True, sparse_samples=5,
                                      sparse_pyramid_levels=2)
            self.assertNotEqual(baseline, multiscale)
            self.assertNotIn("sparsePyramidLevels", json.loads(baseline.read_text())["settings"])
            self.assertEqual(json.loads(multiscale.read_text())["settings"]
                             ["sparsePyramidLevels"], 2)
            report = json.loads((multiscale.parent / "sparse-flow.json").read_text())
            self.assertEqual(report["analyzer"]["pyramidLevels"], 2)
            self.assertEqual(run_analysis(source, runs, seconds=2, thumbnails=4,
                                          sparse_flow=True, sparse_samples=5,
                                          sparse_pyramid_levels=2), multiscale)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy extra unavailable")
    def test_opt_in_sparse_subpixel_has_separate_atomic_run_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            runs = root / "runs"
            baseline = run_analysis(source, runs, seconds=2, thumbnails=4,
                                    sparse_flow=True, sparse_samples=5)
            refined = run_analysis(source, runs, seconds=2, thumbnails=4,
                                   sparse_flow=True, sparse_samples=5,
                                   sparse_subpixel_refinement=True)
            self.assertNotEqual(baseline, refined)
            self.assertNotIn("sparseSubpixelRefinement",
                             json.loads(baseline.read_text())["settings"])
            self.assertTrue(json.loads(refined.read_text())["settings"]
                            ["sparseSubpixelRefinement"])
            report = json.loads((refined.parent / "sparse-flow.json").read_text())
            self.assertEqual(report["analyzer"]["subpixelPeakModel"],
                             "separable-3-point-ncc-parabola-v1")
            self.assertEqual(run_analysis(
                source, runs, seconds=2, thumbnails=4, sparse_flow=True,
                sparse_samples=5, sparse_subpixel_refinement=True), refined)
            checked = run_analysis(
                source, runs, seconds=2, thumbnails=4, sparse_flow=True,
                sparse_samples=5, sparse_subpixel_refinement=True,
                sparse_subpixel_reverse_check=True)
            self.assertNotEqual(refined, checked)
            self.assertTrue(json.loads(checked.read_text())["settings"]
                            ["sparseSubpixelReverseCheck"])
            with self.assertRaisesRegex(ValueError, "reverse check requires"):
                run_analysis(source, runs, seconds=2, thumbnails=4,
                             sparse_flow=True, sparse_samples=5,
                             sparse_subpixel_reverse_check=True)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy extra unavailable")
    def test_projective_opt_in_is_separately_hashed_and_source_linked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            runs = root / "runs"
            baseline = run_analysis(source, runs, seconds=2, thumbnails=4,
                                    sparse_flow=True, sparse_samples=5)
            projective = run_analysis(source, runs, seconds=2, thumbnails=4,
                                      sparse_flow=True, sparse_samples=5,
                                      sparse_projective_hypotheses=True)
            self.assertNotEqual(baseline, projective)
            self.assertNotIn("sparseProjectiveHypotheses",
                             json.loads(baseline.read_text())["settings"])
            self.assertTrue(json.loads(projective.read_text())["settings"]
                            ["sparseProjectiveHypotheses"])
            sparse = json.loads((projective.parent / "sparse-flow.json").read_text())
            self.assertTrue(all(p["projectiveHypothesis"]["status"] ==
                                "insufficient-points" for p in sparse["pairs"]))
            self.assertEqual(run_analysis(
                source, runs, seconds=2, thumbnails=4, sparse_flow=True,
                sparse_samples=5, sparse_projective_hypotheses=True), projective)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy extra unavailable")
    def test_tracklet_motion_consistency_opt_in_has_distinct_run_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            runs = root / "runs"
            original = run_analysis(source, runs, seconds=2, thumbnails=4,
                                    sparse_flow=True, sparse_samples=5)
            checked = run_analysis(source, runs, seconds=2, thumbnails=4,
                                   sparse_flow=True, sparse_samples=5,
                                   sparse_tracklet_motion_consistency=True)
            self.assertNotEqual(original, checked)
            self.assertNotIn("sparseTrackletMotionConsistency",
                             json.loads(original.read_text())["settings"])
            self.assertTrue(json.loads(checked.read_text())["settings"]
                            ["sparseTrackletMotionConsistency"])
            self.assertEqual(json.loads((checked.parent / "sparse-flow.json").read_text())
                             ["temporalTracklets"]["method"],
                             "mutual-nearest-adjacent-endpoint-motion-gated-v1")
            self.assertEqual(run_analysis(
                source, runs, seconds=2, thumbnails=4, sparse_flow=True,
                sparse_samples=5, sparse_tracklet_motion_consistency=True), checked)
            appearance = run_analysis(source, runs, seconds=2, thumbnails=4,
                                      sparse_flow=True, sparse_samples=5,
                                      sparse_tracklet_appearance_consistency=True)
            self.assertNotEqual(appearance, checked)
            self.assertNotEqual(appearance, original)
            self.assertTrue(json.loads(appearance.read_text())["settings"]
                            ["sparseTrackletAppearanceConsistency"])
            self.assertEqual(json.loads((appearance.parent / "sparse-flow.json").read_text())
                             ["temporalTracklets"]["method"],
                             "mutual-nearest-adjacent-endpoint-appearance-gated-v1")

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy extra unavailable")
    def test_lk_refinement_opt_in_has_separate_immutable_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            runs = root / "runs"
            original = run_analysis(source, runs, seconds=2, thumbnails=4,
                                    sparse_flow=True, sparse_samples=5)
            lk = run_analysis(source, runs, seconds=2, thumbnails=4,
                              sparse_flow=True, sparse_samples=5,
                              sparse_lk_refinement=True)
            self.assertNotEqual(original, lk)
            self.assertNotIn("sparseLkRefinement", json.loads(original.read_text())["settings"])
            self.assertTrue(json.loads(lk.read_text())["settings"]["sparseLkRefinement"])
            sparse = json.loads((lk.parent / "sparse-flow.json").read_text())
            self.assertEqual(sparse["analyzer"]["method"],
                             "shi-tomasi-approx-patch-ncc-fb-consensus-affine-lk-v1")
            self.assertEqual(run_analysis(
                source, runs, seconds=2, thumbnails=4, sparse_flow=True,
                sparse_samples=5, sparse_lk_refinement=True), lk)
            with self.assertRaisesRegex(ValueError, "cannot combine"):
                run_analysis(source, runs, seconds=2, thumbnails=4,
                             sparse_flow=True, sparse_samples=5,
                             sparse_lk_refinement=True, sparse_subpixel_refinement=True)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy extra unavailable")
    def test_quadrant_appearance_guard_has_distinct_immutable_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            runs = root / "runs"
            original = run_analysis(source, runs, seconds=2, thumbnails=4,
                                    sparse_flow=True, sparse_samples=5)
            guarded = run_analysis(source, runs, seconds=2, thumbnails=4,
                                   sparse_flow=True, sparse_samples=5,
                                   sparse_quadrant_consistency=True)
            self.assertNotEqual(original, guarded)
            self.assertNotIn("sparseQuadrantConsistency",
                             json.loads(original.read_text())["settings"])
            self.assertTrue(json.loads(guarded.read_text())["settings"]
                            ["sparseQuadrantConsistency"])
            self.assertEqual(json.loads((guarded.parent / "sparse-flow.json").read_text())
                             ["analyzer"]["quadrantGuardMinimumSupport"], 3)
            self.assertEqual(run_analysis(
                source, runs, seconds=2, thumbnails=4, sparse_flow=True,
                sparse_samples=5, sparse_quadrant_consistency=True), guarded)

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy extra unavailable")
    def test_appearance_bundle_is_atomic_and_may_combine_with_sparse_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "flat.mkv"
            self._flat_video(source)
            runs = root / "runs"
            manifest_path = run_analysis(source, runs, seconds=2, thumbnails=4,
                                         sparse_flow=True, sparse_samples=6,
                                         appearance=True, appearance_samples=6)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["artifacts"]["appearance"], "appearance.json")
            self.assertEqual(manifest["artifacts"]["sparseFlow"], "sparse-flow.json")
            self.assertEqual(manifest["settings"]["versions"]["appearance"],
                             "kumiki.appearance.v1")
            report_path = manifest_path.parent / "appearance.json"
            report = json.loads(report_path.read_text())
            self.assertEqual(report["schemaVersion"], "kumiki.appearance.v1")
            self.assertEqual(len(report["changes"]), len(report["samples"]) - 1)
            self.assertEqual(run_analysis(source, runs, seconds=2, thumbnails=4,
                                          sparse_flow=True, sparse_samples=6,
                                          appearance=True, appearance_samples=6), manifest_path)
            report_path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "missing or modified"):
                run_analysis(source, runs, seconds=2, thumbnails=4,
                             sparse_flow=True, sparse_samples=6,
                             appearance=True, appearance_samples=6)

    def test_invalid_appearance_budget_prevents_partial_run(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "runs"
            with self.assertRaisesRegex(ValueError, "appearance requires"):
                run_analysis(Path("missing.mp4"), output, seconds=30,
                             appearance=True)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
