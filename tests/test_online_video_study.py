"""Provider-neutral online video research: security, decoding, provenance and cleanup."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kumiki_reference_lab.acquisition.online_video import (
    download_public_video, reference_id, require_public_dns,
    require_rights, validate_watch_url,
)
from kumiki_reference_lab.pipeline.online_frames import (
    analyze_all_frames, frame_change, frame_metrics,
)
from kumiki_reference_lab.pipeline.online_semantics import (
    analyze_visual_samples, validate_visual_observation,
)
from kumiki_reference_lab.pipeline.online_study import study_online_video


class UrlAndAcquisitionTests(unittest.TestCase):
    def test_no_platform_allowlist(self):
        for url in (
            "https://www.youtube.com/watch?v=abc",
            "https://www.tiktok.com/@creator/video/1234",
            "https://player.vimeo.com/video/456",
            "https://cinema.example.org/my-video",
            "https://new-video-platform.example/watch/abc",
        ):
            with self.subTest(url=url):
                self.assertEqual(validate_watch_url(url), url)
                self.assertTrue(reference_id(url))

    def test_reject_sensitive_or_local_urls(self):
        for url in (
            "http://videos.example.com/video", "https://localhost/watch",
            "https://192.168.1.10/watch", "https://169.254.169.254/latest",
            "https://videos.internal/watch", "https://example.com:8080/abc",
            "https://user:pass@example.com/watch",
            "https://example.com/watch?access_token=abc",
            "file:///etc/passwd", "https://example.com/watch#fragment",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_watch_url(url)

    @patch("kumiki_reference_lab.acquisition.online_video.socket.getaddrinfo")
    def test_reject_private_dns_answers(self, resolver):
        resolver.return_value = [(2, 1, 6, "", ("10.0.0.7", 443))]
        with self.assertRaises(ValueError):
            require_public_dns("https://unfamiliar.example/watch")
        resolver.return_value = [(2, 1, 6, "", ("8.8.8.8", 443))]
        require_public_dns("https://unfamiliar.example/watch")

    def test_explicit_rights_basis(self):
        with self.assertRaises(ValueError):
            require_rights("other-lawful-authorization", "only private research",
                           acknowledged=False)
        require_rights("permissive-license", "creator-granted open license for analysis",
                       acknowledged=True)

    @patch("kumiki_reference_lab.acquisition.online_video.require_public_dns")
    @patch("kumiki_reference_lab.acquisition.online_video.subprocess.run")
    def test_platform_neutral_download_command(self, run, dns):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def fake_run(argv, **kwargs):
                (root / "source.mp4").write_bytes(b"example")
                return SimpleNamespace(returncode=0)
            run.side_effect = fake_run
            result = download_public_video(
                "https://independent.example/watch", root,
                rights_basis="written-permission",
                rights_note="copyright owner granted permission for this reference",
                acknowledge_rights=True,
            )
            self.assertEqual(result, root / "source.mp4")
            self.assertIn("--no-playlist", run.call_args.args[0])
            self.assertIn("--ignore-config", run.call_args.args[0])
            dns.assert_called_once()

    @patch("kumiki_reference_lab.acquisition.online_video.require_public_dns")
    @patch("kumiki_reference_lab.acquisition.online_video.subprocess.run")
    def test_download_failure_does_not_echo_sensitive_stderr(self, run, dns):
        run.return_value = SimpleNamespace(returncode=1, stderr="signed-secret-cdn-token")
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "unauthenticated extractor") as error:
                download_public_video(
                    "https://independent.example/watch", Path(folder),
                    rights_basis="permissive-license",
                    rights_note="creator granted reuse and scientific study",
                    acknowledge_rights=True,
                )
            self.assertNotIn("signed-secret", str(error.exception))


class FrameEvidenceTests(unittest.TestCase):
    def test_frame_math(self):
        frame_a = bytes([0, 0, 0]) * (64 * 36)
        frame_b = bytes([255, 255, 255]) * (64 * 36)
        self.assertEqual(frame_metrics(frame_a, width=64, height=36)["displayLumaProxy"], 0)
        self.assertEqual(frame_metrics(frame_b, width=64, height=36)["displayLumaProxy"], 1)
        self.assertEqual(frame_change(frame_a, frame_b, width=64, height=36)["meanPixelDelta"], 1)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "FFmpeg/FFprobe not installed")
    def test_real_all_frame_decoding_with_pts(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "synthetic.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=12:duration=2",
                "-an", "-c:v", "mpeg4", "-y", str(source),
            ], check=True, capture_output=True, timeout=30)
            report, previews = analyze_all_frames(
                source, max_seconds=2, max_frames=40,
                width=160, height=90, semantic_stride=6,
                max_semantic_frames=3,
            )
            self.assertEqual(report["frameCount"], 24)
            self.assertEqual(len(report["frames"]), 24)
            self.assertTrue(report["decoderTimebaseMatchesSource"])
            self.assertGreaterEqual(len(previews), 2)
            self.assertLessEqual(len(previews), 3)
            self.assertTrue(previews[0][1].startswith(b"\x89PNG"))
            self.assertTrue(all(
                a["decodedPts"] < b["decodedPts"] for a, b in
                zip(report["frames"], report["frames"][1:])
            ))


_VISUAL = {
    "typography": {"style": "geometric heavy sans", "visibleText": "HELLO", "motion": "slides in"},
    "characters": [{"look": "round blue animated figure", "action": "turning"}],
    "animation": ["2D cutout", "kinetic typography"],
    "camera": "horizontal image translation visible",
    "lighting": "soft diffuse shading",
    "composition": "central figure",
    "visualStyle": "paper-cut collage",
}


class SemanticAndRunnerTests(unittest.TestCase):
    def test_visual_semantics_validate(self):
        self.assertEqual(validate_visual_observation(_VISUAL)["visualStyle"], "paper-cut collage")
        invalid = {**_VISUAL, "characters": [{"look": "ethnicity unknown", "action": "running"}]}
        with self.assertRaises(ValueError):
            validate_visual_observation(invalid)

    @patch("kumiki_reference_lab.pipeline.online_semantics._ollama_json")
    def test_ollama_comparison(self, infer):
        infer.return_value = _VISUAL
        result = analyze_visual_samples([(1, b"png1"), (8, b"png2")], model="localvision")
        self.assertEqual(result[0]["comparisonFrameIndex"], None)
        self.assertEqual(result[1]["comparisonFrameIndex"], 1)
        self.assertEqual(len(infer.call_args.args[0]), 2)
        interrupted = analyze_visual_samples(
            [(1, b"png1"), (8, b"png2")], model="localvision",
            cut_candidate_indices=(5,))
        self.assertIsNone(interrupted[1]["comparisonFrameIndex"])
        self.assertEqual(len(infer.call_args.args[0]), 1)

    @patch("kumiki_reference_lab.pipeline.online_study.analyze_all_frames")
    @patch("kumiki_reference_lab.pipeline.online_study.download_public_video")
    def test_publishes_only_data_and_cleans_media(self, acquire, frames):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "pyproject.toml").write_text("[project]\nname='test'\n")
            observed = []
            def fake_download(url, path, **kwargs):
                media = path / "source.mp4"
                media.write_bytes(b"private-temporary-footage")
                observed.append(media)
                return media
            acquire.side_effect = fake_download
            frames.return_value = ({
                "sourceSha256": "e" * 64, "video": {"streamIndex": 0},
                "frameCount": 2, "frames": [{"frameIndex": 0}, {"frameIndex": 1}],
                "analysisWindow": {"completeVideo": True},
            }, [])
            result = study_online_video(
                "https://unknown.example/watch", root,
                rights_basis="written-permission",
                rights_note="the rightsholder explicitly authorized this research",
                acknowledge_rights=True,
            )
            self.assertTrue(result.is_file())
            self.assertFalse(observed[0].exists())
            payload = json.loads(result.read_text())
            self.assertEqual(payload["numericEvidence"]["frameCount"], 2)
            self.assertEqual(payload["semanticStatus"], "not-measured")
            self.assertEqual(payload["source"]["mediaRetained"], False)
            with self.assertRaises(ValueError):
                study_online_video(
                    "https://unknown.example/watch", root,
                    rights_basis="written-permission",
                    rights_note="the rightsholder explicitly authorized this research",
                    acknowledge_rights=True,
                )

    @patch("kumiki_reference_lab.pipeline.online_study.analyze_all_frames")
    @patch("kumiki_reference_lab.pipeline.online_study.download_public_video")
    def test_failure_cleans_media_without_writing_report(self, acquire, frames):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "pyproject.toml").write_text("[project]\nname='test'\n")
            observed = []
            def fake_download(url, path, **kwargs):
                media = path / "source.mp4"
                media.write_bytes(b"temporary")
                observed.append(media)
                return media
            acquire.side_effect = fake_download
            frames.side_effect = ValueError("decoder error")
            with self.assertRaisesRegex(ValueError, "decoder error"):
                study_online_video(
                    "https://unknown.example/watch", root,
                    rights_basis="written-permission",
                    rights_note="rightsholder explicitly authorized local analysis",
                    acknowledge_rights=True,
                )
            self.assertFalse(observed[0].exists())
            self.assertFalse((root / "research" / "analysis" / "online-videos").exists())


if __name__ == "__main__":
    unittest.main()
