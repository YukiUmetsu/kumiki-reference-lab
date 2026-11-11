"""Agent-friendly frame navigation, restricted output, and small Magnitude requests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kumiki_reference_lab.pipeline.agent_frame_review import (
    annotate_frame, cleanup_workspace, export_annotations, finalize_frame_workspace,
    load_workspace, make_frame_sink, next_frame, scan_frames, show_frame,
)
from kumiki_reference_lab.pipeline.magnitude_vision import (
    infer_workspace_frame, magnitude_focused_observation,
)
from kumiki_reference_lab.pipeline.online_study import study_online_video

_MINIMAL_PNG = b"\x89PNG\r\n\x1a\nmock-preview-data"


def _numeric() -> dict:
    return {
        "sourceSha256": "a" * 64,
        "video": {
            "width": 160, "height": 90, "sourceTimebase": {
                "numerator": 1, "denominator": 1000,
            },
        },
        "frameCount": 4,
        "cutCandidateFrameIndices": [2],
        "frames": [
            {"frameIndex": i, "decodedPts": i * 100, "decodedSeconds": i / 10,
             "appearance": {"meanRgb": [0.1, 0.3, 0.5]},
             "changeFromPrevious": ({
                 "meanPixelDelta": value, "changedPixelFraction": value,
             } if i else None),
             "cutCandidate": i == 2}
            for i, value in enumerate([0, .01, .8, .3])
        ],
    }


class FrameReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "pyproject.toml").write_text("[project]\nname='tmp'\n")
        self.observed: list[Path] = []

    def _study(self) -> tuple[Path, Path]:
        def fake_download(url, source_dir, **kwargs):
            path = source_dir / "source.mp4"
            path.write_bytes(b"ephemeral video bytes")
            self.observed.append(path)
            return path
        def fake_analyze(source, *, frame_sink=None, **kwargs):
            self.assertIsNotNone(frame_sink)
            for i in range(4):
                frame_sink(i, _MINIMAL_PNG)
            return _numeric(), []
        with patch("kumiki_reference_lab.pipeline.online_study.download_public_video",
                   side_effect=fake_download), patch(
            "kumiki_reference_lab.pipeline.online_study.analyze_all_frames",
            side_effect=fake_analyze,
        ):
            result = study_online_video(
                "https://example.org/videos/showcase", self.root,
                rights_basis="written-permission",
                rights_note="the author authorized downloading for analysis",
                acknowledge_rights=True,
                review_frames=True, max_review_bytes=1000,
            )
        workspace = self.root / "workspace" / "frame-review" / result.stem
        return result, workspace

    def test_end_to_end_agent_review_without_video_retention(self):
        result, workspace = self._study()
        self.assertTrue(result.is_file())
        self.assertTrue((workspace / "index.html").is_file())
        self.assertTrue((workspace / "frames" / "frame-000003.png").is_file())
        self.assertFalse(self.observed[0].exists())
        manifest, numeric, reference = load_workspace(workspace)
        self.assertEqual(manifest["frameCount"], 4)
        self.assertEqual(reference, result)
        self.assertEqual(numeric["sourceSha256"], "a" * 64)
        self.assertEqual(show_frame(workspace, 2)["cutCandidate"], True)
        self.assertEqual(next_frame(workspace, mode="cuts")["frameIndex"], 2)
        self.assertEqual(next_frame(workspace, after=2, mode="changed",
                                    min_change=.2)["frameIndex"], 3)
        self.assertTrue(next_frame(workspace, after=3)["complete"])
        self.assertEqual(next_frame(workspace, mode="interval",
                                    interval=3)["frameIndex"], 0)
        note = annotate_frame(
            workspace, start=2, end=3, category="animation",
            description="The rectangular element moves toward the center.",
            evidence="Frame 3 differs from frame 2.", confidence="low",
        )
        self.assertEqual(note["startSeconds"], .2)
        # Same proposal is idempotent.
        second = annotate_frame(
            workspace, start=2, end=3, category="animation",
            description="The rectangular element moves toward the center.",
            evidence="Frame 3 differs from frame 2.", confidence="low",
        )
        self.assertEqual(note["id"], second["id"])
        exported = export_annotations(workspace)
        self.assertEqual(len(json.loads(exported.read_text())["observations"]), 1)
        self.assertEqual(json.loads(exported.read_text())["sourceSha256"], "a" * 64)
        cleanup_workspace(workspace)
        self.assertFalse(workspace.exists())
        self.assertTrue(result.exists())
        self.assertTrue(exported.exists())

    @patch("kumiki_reference_lab.pipeline.magnitude_vision.infer_workspace_frame")
    def test_small_model_scan_budget_and_resumption(self, infer):
        _, workspace = self._study()
        def fake_inference(ws, *, index, category, **kwargs):
            annotate_frame(
                ws, start=index, category=category,
                description=f"Observed {category} change at frame {index}.",
                evidence="Direct local frame preview available.")
            return {"status": "unreviewed-local-model-proposal"}
        infer.side_effect = fake_inference
        first = scan_frames(
            workspace, model="mini-vision", mode="changed",
            categories=("animation", "typography"), max_calls=3,
            min_change=.08)
        self.assertEqual(first["modelCalls"], 3)
        self.assertTrue(first["remainingWork"])
        exported = json.loads(Path(first["savedTo"]).read_text())
        self.assertEqual(len(exported["observations"]), 3)
        second = scan_frames(
            workspace, model="mini-vision", mode="changed",
            categories=("animation", "typography"), max_calls=3,
            min_change=.08)
        self.assertEqual(second["modelCalls"], 3)
        self.assertGreaterEqual(second["alreadyAnnotatedSkipped"], 3)
        self.assertFalse(second["remainingWork"])
        self.assertEqual(len(json.loads(Path(second["savedTo"]).read_text())["observations"]), 6)

    def test_frame_sink_disk_cap(self):
        staging = self.root / "staging"
        staging.mkdir()
        callback = make_frame_sink(staging, max_bytes=len(_MINIMAL_PNG))
        callback(0, _MINIMAL_PNG)
        with self.assertRaisesRegex(ValueError, "disk budget"):
            callback(1, _MINIMAL_PNG)

    def test_frame_sink_rejects_unordered_and_bogus_images(self):
        staging = self.root / "staging"
        staging.mkdir()
        callback = make_frame_sink(staging)
        with self.assertRaises(ValueError):
            callback(2, _MINIMAL_PNG)
        with self.assertRaises(ValueError):
            callback(0, b"not a PNG")

    def test_cleanup_rejects_unrelated_directory(self):
        unsafe = self.root / "not-a-workspace"
        unsafe.mkdir()
        (unsafe / "keep.txt").write_text("keep")
        with self.assertRaises(ValueError):
            cleanup_workspace(unsafe)
        self.assertTrue((unsafe / "keep.txt").exists())

    def test_failed_study_discards_partial_previews(self):
        def fake_download(url, source_dir, **kwargs):
            path = source_dir / "source.mp4"
            path.write_bytes(b"temporary")
            self.observed.append(path)
            return path
        def fail(source, *, frame_sink=None, **kwargs):
            frame_sink(0, _MINIMAL_PNG)
            raise ValueError("simulated decoder failure")
        with patch("kumiki_reference_lab.pipeline.online_study.download_public_video",
                   side_effect=fake_download), patch(
            "kumiki_reference_lab.pipeline.online_study.analyze_all_frames", side_effect=fail,
        ):
            with self.assertRaisesRegex(ValueError, "decoder failure"):
                study_online_video(
                    "https://example.org/videos/showcase", self.root,
                    rights_basis="written-permission",
                    rights_note="the author authorized downloading for analysis",
                    acknowledge_rights=True, review_frames=True,
                )
        self.assertFalse(self.observed[0].exists())
        frame_dir = self.root / "workspace" / "frame-review"
        self.assertEqual(list(frame_dir.iterdir()), [])

    def test_annotate_rejects_out_of_bounds_or_unsupported_categories(self):
        _, workspace = self._study()
        with self.assertRaises(ValueError):
            annotate_frame(workspace, start=-1, category="animation",
                           description="some visible movement")
        with self.assertRaises(ValueError):
            annotate_frame(workspace, start=0, category="identity",
                           description="someone visible")

    @patch("kumiki_reference_lab.pipeline.magnitude_vision.magnitude_focused_observation")
    def test_infer_uses_adjacent_frames_but_not_across_cuts(self, model):
        _, workspace = self._study()
        model.return_value = {
            "schemaVersion": "kumiki.magnitude-focused-vision.v1",
            "description": "A brief sliding motion",
            "evidence": "The frame shifted", "category": "animation",
            "confidence": "low", "status": "unreviewed-local-model-proposal",
            "modelTag": "mini-vision", "sourceFrameCount": 2,
        }
        paired = infer_workspace_frame(workspace, index=1,
                                       category="animation", model="mini-vision")
        self.assertEqual(paired["startFrameIndex"], 0)
        self.assertEqual(len(model.call_args.args[0]), 2)
        cut = infer_workspace_frame(workspace, index=2,
                                    category="animation", model="mini-vision")
        self.assertEqual(cut["startFrameIndex"], 2)
        self.assertEqual(len(model.call_args.args[0]), 1)


class MagnitudeApiTests(unittest.TestCase):
    @patch("kumiki_reference_lab.pipeline.magnitude_vision.http.client.HTTPConnection")
    def test_openai_compatible_local_vision_request(self, client):
        response = SimpleNamespace(
            status=200, read=lambda limit: json.dumps({
                "choices": [{"message": {"content": json.dumps({
                    "description": "Flat green shape moving right",
                    "evidence": "Compared two adjacent frames",
                })}}]
            }).encode())
        connection = client.return_value
        connection.getresponse.return_value = response
        result = magnitude_focused_observation(
            [_MINIMAL_PNG, _MINIMAL_PNG], category="animation",
            model="mini-vision:gguf:q4", port=10100)
        self.assertEqual(result["description"], "Flat green shape moving right")
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(client.call_args.args[:2], ("127.0.0.1", 10100))
        args = connection.request.call_args.args
        self.assertEqual(args[1], "/inference/v1/chat/completions")
        body = json.loads(connection.request.call_args.kwargs["body"])
        self.assertEqual(len(body["messages"][0]["content"]), 3)
        self.assertEqual(body["max_tokens"], 180)
        connection.close.assert_called_once()

    @patch("kumiki_reference_lab.pipeline.magnitude_vision.http.client.HTTPConnection")
    def test_small_model_plain_text_fallback(self, client):
        client.return_value.getresponse.return_value = SimpleNamespace(
            status=200, read=lambda length: json.dumps({
                "choices": [{"message": {"content": "Soft diffuse highlights"}}]
            }).encode())
        result = magnitude_focused_observation(
            [_MINIMAL_PNG], category="lighting", model="small")
        self.assertEqual(result["description"], "Soft diffuse highlights")

    def test_magnitude_rejects_invalid_category_and_input(self):
        with self.assertRaises(ValueError):
            magnitude_focused_observation(
                [_MINIMAL_PNG], category="real-person-identity", model="small")
        with self.assertRaises(ValueError):
            magnitude_focused_observation(
                [b"not png"], category="lighting", model="small")


if __name__ == "__main__":
    unittest.main()
