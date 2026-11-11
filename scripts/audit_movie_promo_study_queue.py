"""Validate unmeasured official-trailer study targets without treating metadata as footage.

This queue is separate from the source-hashed, actually measured index.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


SCHEMA = "kumiki.movie-promotion-study-queue.v1"
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def audit(queue: dict, catalog: dict) -> list[str]:
    errors: list[str] = []
    if queue.get("schemaVersion") != SCHEMA:
        errors.append("unsupported study queue schema")
    if queue.get("researchStatus") != "metadata-only-no-media-analysis":
        errors.append("queue wrongly claims media analysis")
    try:
        snapshot = date.fromisoformat(queue["retrievedOn"])
    except (ValueError, TypeError, KeyError):
        errors.append("invalid queue date")
        snapshot = date.min
    catalog_ids = {row["youtubeId"] for row in catalog.get("entries", [])}
    seen_ids: set[str] = set()
    seen_uploads: set[str] = set()
    entries = queue.get("entries")
    if not isinstance(entries, list) or not entries:
        return errors + ["missing queued entries"]
    for i, item in enumerate(entries):
        if not isinstance(item, dict):
            errors.append(f"row {i}: not an object")
            continue
        slug = item.get("id")
        video_id = item.get("youtubeId")
        if not isinstance(slug, str) or not SLUG.fullmatch(slug):
            errors.append(f"row {i}: invalid slug")
        elif slug in seen_ids:
            errors.append(f"{slug}: duplicate slug")
        else:
            seen_ids.add(slug)
        if not isinstance(video_id, str) or not VIDEO_ID.fullmatch(video_id):
            errors.append(f"row {i}: invalid YouTube id")
            continue
        if video_id in seen_uploads or video_id in catalog_ids:
            errors.append(f"{slug}: duplicate official upload")
        seen_uploads.add(video_id)
        if item.get("officialYoutubeUrl") != f"https://www.youtube.com/watch?v={video_id}":
            errors.append(f"{slug}: upload URL mismatch")
        if item.get("mediaAnalysisStatus") != "not-performed" or item.get("researchStatus") != "metadata-only-not-frame-reviewed":
            errors.append(f"{slug}: false evidence status")
        if "sourceSha256" in item or "windows" in item or "measurements" in item:
            errors.append(f"{slug}: unmeasured record must not contain source evidence")
        rights = item.get("rights", {})
        if rights != {"referenceOnly": True, "mediaProcessingPermission": "not-established", "redistributionAuthorized": False}:
            errors.append(f"{slug}: improper rights declaration")
        try:
            published = date.fromisoformat(item["publishedOn"])
            if not date(2005, 1, 1) <= published <= snapshot:
                errors.append(f"{slug}: invalid publication date")
        except (KeyError, ValueError, TypeError):
            errors.append(f"{slug}: malformed publication date")
        if (not all(isinstance(item.get(field), str) and item[field].strip()
                    for field in ("title", "filmStudio", "officialUploader"))
                or isinstance(item.get("filmReleaseYear"), bool)
                or not isinstance(item.get("filmReleaseYear"), int)
                or not 1990 <= item["filmReleaseYear"] <= snapshot.year):
            errors.append(f"{slug}: invalid film metadata")
        if not isinstance(item.get("studyQuestion"), str) or not item["studyQuestion"].endswith("?"):
            errors.append(f"{slug}: expected testable study question")
        tags = item.get("candidateResearchTags")
        if (not isinstance(tags, list) or not tags
                or not all(isinstance(tag, str) and SLUG.fullmatch(tag) for tag in tags)
                or len(tags) != len(set(map(str, tags)))):
            errors.append(f"{slug}: invalid proposed research tags")
        view = item.get("viewEvidence", {})
        count = view.get("reportedViews")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            errors.append(f"{slug}: invalid reported views")
        if view.get("retrievedOn") != queue.get("retrievedOn"):
            errors.append(f"{slug}: unaligned evidence retrieval date")
        if view.get("sourceKind") not in {"youtube-search-index", "third-party-channel-statistics", "third-party-video-statistics"}:
            errors.append(f"{slug}: invalid view evidence category")
        url = view.get("sourceUrl")
        try:
            parsed = urlparse(url) if isinstance(url, str) else None
            host = parsed.hostname if parsed is not None else None
            if (parsed is None or parsed.scheme != "https"
                    or (view.get("sourceKind") == "youtube-search-index" and
                        (host not in {"www.youtube.com", "youtube.com"}
                         or url != item.get("officialYoutubeUrl")))
                    or (view.get("sourceKind") == "third-party-channel-statistics" and
                        host != "trari.com")
                    or (view.get("sourceKind") == "third-party-video-statistics" and
                        (host != "chartslist.com" or
                         not parsed.path.startswith(f"/youtube/video/{video_id}/")))):
                errors.append(f"{slug}: unsafe evidence URL")
        except ValueError:
            errors.append(f"{slug}: unsafe evidence URL")
        if item.get("proposedAcquisitionPriority") not in {"first-wave", "second-wave"}:
            errors.append(f"{slug}: invalid queue priority")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=Path("research/analysis/movie-promotions/study-queue.v1.json"))
    parser.add_argument("--catalog", type=Path, default=Path("research/popular-movie-videos.v1.json"))
    args = parser.parse_args()
    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    errors = audit(queue, catalog)
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    print(f"Validated {len(queue['entries'])} unmeasured official movie-promotion study targets.")


if __name__ == "__main__":
    main()
