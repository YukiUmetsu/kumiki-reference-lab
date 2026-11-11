"""Offline tests of publisher identity and temporary-media acquisition controls."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from scripts import research_movie_promo_overgrown as research


class FakeVideoResponse(io.BytesIO):
    def __init__(self, url: str, content: bytes):
        super().__init__(content)
        self._url = url

    def geturl(self) -> str:
        return self._url


class BlenderPublisherResearchTests(unittest.TestCase):
    def test_known_film_editions_have_distinct_source_ids(self):
        targets = research.TARGETS
        self.assertEqual(set(targets), {"overgrown", "agent327"})
        self.assertEqual(len({x["id"] for x in targets.values()}), 2)
        self.assertEqual(len({x["uuid"] for x in targets.values()}), 2)
        for t in targets.values():
            self.assertEqual(str(UUID(t["uuid"])), t["uuid"])
            self.assertTrue(t["sourceEdition"].startswith("Blender Studio official PeerTube"))
            self.assertTrue(t["catalogId"].startswith("uncataloged-"))

    def test_publisher_host_check_rejects_lookalikes(self):
        self.assertTrue(research._publisher_host("https://video.blender.org/videos/watch/test"))
        for url in ("http://video.blender.org/test", "https://video.blender.org.evil.example/",
                    "https://video.blender.org@evil.example/", "file:///etc/passwd"):
            with self.subTest(url=url):
                self.assertFalse(research._publisher_host(url))

    def _metadata(self, name: str) -> dict:
        url = "https://video.blender.org/static/agent327-480p.mp4"
        return {
            "uuid": research.TARGETS["agent327"]["uuid"],
            "name": name,
            "channel": {"name": "blender_open_movies"},
            "privacy": {"id": 1},
            "files": [{
                "fileDownloadUrl": url,
                "size": 120_000,
                "resolution": {"id": 480},
            }],
            "streamingPlaylists": [],
        }

    def test_acquires_only_exact_public_publisher_file_in_temporary_directory(self):
        target = research.TARGETS["agent327"]
        metadata = self._metadata(target["title"])
        payload = b"x" * 120_000
        video_url = metadata["files"][0]["fileDownloadUrl"]
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(research, "_json_public_publisher", return_value=metadata), \
                 patch.object(research, "urlopen", side_effect=lambda request, timeout: FakeVideoResponse(video_url, payload)):
                path, edition = research.acquire_public_source(Path(tmp), target)
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(path.name, target["id"] + ".mp4")
            self.assertEqual(edition["sourceTrackId"], target["uuid"])
            self.assertEqual(edition["sourceEdition"], target["sourceEdition"])
            self.assertEqual(edition["officialPlayerUrl"],
                             "https://video.blender.org/videos/watch/" + target["uuid"])
        self.assertFalse(path.exists(), "temporary media must be deleted on exit")

    def test_rejects_fake_channel_private_media_or_wrong_title(self):
        target = research.TARGETS["agent327"]
        for mutation in ("private", "wrong-title", "wrong-channel", "wrong-uuid"):
            metadata = self._metadata(target["title"])
            if mutation == "private":
                metadata["privacy"]["id"] = 2
            elif mutation == "wrong-title":
                metadata["name"] = "Unrelated video"
            elif mutation == "wrong-channel":
                metadata["channel"]["name"] = "imposter"
            else:
                metadata["uuid"] = "00000000-0000-0000-0000-000000000001"
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                with patch.object(research, "_json_public_publisher", return_value=metadata), \
                     patch.object(research, "urlopen", side_effect=AssertionError("unexpected download")):
                    with self.assertRaisesRegex(ValueError, "identity mismatch"):
                        research.acquire_public_source(Path(tmp), target)

    def test_rejects_redirects_or_nonpublisher_video_file(self):
        target = research.TARGETS["agent327"]
        bad = self._metadata(target["title"])
        bad["files"][0]["fileDownloadUrl"] = "https://evil.example/video.mp4"
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(research, "_json_public_publisher", return_value=bad):
            with self.assertRaisesRegex(ValueError, "no bounded public file"):
                research.acquire_public_source(Path(tmp), target)

    def test_existing_overgrown_record_cannot_be_overwritten(self):
        with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
            research.generate("overgrown")

    def test_one_shot_source_preflight_does_not_edit_existing_index(self):
        source = research.INDEX.read_bytes()
        index = json.loads(source)
        self.assertTrue(any(x["id"] == research.TARGETS["overgrown"]["id"]
                            for x in index["videos"]))
        self.assertEqual(len({x["id"] for x in index["videos"]}), len(index["videos"]))
        self.assertEqual(source, research.INDEX.read_bytes())


if __name__ == "__main__":
    unittest.main()
