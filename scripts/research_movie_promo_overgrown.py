"""One-shot, source-hashed analysis of an official Blender Studio feature-film teaser.

Only downloads public, unauthenticated media from Blender's own PeerTube server. All audiovisual
media and image galleries live in TemporaryDirectory and are deleted before
the resulting numeric JSON is staged. Never circumvent DRM or authorization.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
import statistics
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from scripts.audit_movie_promo_evidence import audit
from scripts.export_movie_promo_evidence import build_evidence
from scripts.rebuild_movie_promo_derived import write_reports


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research/analysis/movie-promotions"
INDEX = DATA / "index.json"
DETAIL = DATA / "overgrown-blender-teaser.json"
VIDEO_ID = "overgrown-blender-teaser"
PEERTUBE_ROOT = "https://video.blender.org"

TARGETS = {
    "overgrown": {
        "id": "overgrown-blender-teaser",
        "catalogId": "uncataloged-blender-overgrown-official-teaser",
        "uuid": "7ad3cbee-fe5f-41c2-93ea-b108986939f4",
        "title": "OVERGROWN - Blender Feature Film (Teaser)",
        "sourceEdition": "Blender Studio official PeerTube OVERGROWN feature-film teaser (not a verified YouTube edition)",
    },
    "agent327": {
        "id": "agent-327-barbershop-teaser",
        "catalogId": "uncataloged-blender-agent327-feature-teaser",
        "uuid": "264ff760-803e-430e-8d81-15648e904183",
        "title": "Agent 327: Operation Barbershop",
        "sourceEdition": "Blender Studio official PeerTube Agent 327: Operation Barbershop feature-film teaser (not a verified YouTube edition)",
    },
}


def run(*command: str, output: bool = False) -> str:
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        # CDN endpoints may contain temporary access tokens; redact all URLs.
        safe = re.sub(r"https?://\S+", "[redacted-url]", (result.stderr or "")[-1800:])
        raise RuntimeError(f"{command[0]} failed with code {result.returncode}: {safe}")
    return result.stdout if output else ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_info(path: Path) -> tuple[float, list[int]]:
    payload = json.loads(run("ffprobe", "-v", "error", "-show_format",
                             "-show_streams", "-of", "json", str(path), output=True))
    video = next((x for x in payload["streams"] if x["codec_type"] == "video"), None)
    audio = next((x for x in payload["streams"] if x["codec_type"] == "audio"), None)
    if video is None or audio is None:
        raise ValueError("cannot analyze: required video or audio stream absent")
    duration = float(payload["format"]["duration"])
    if not math.isfinite(duration) or not 80 <= duration <= 300:
        raise ValueError(f"unreasonable promotional source duration: {duration!r}")
    width, height = int(video["width"]), int(video["height"])
    if not 240 <= width <= 3840 or not 120 <= height <= 2160:
        raise ValueError("unreasonable video resolution")
    return duration, [width, height]


def rational_seconds(value: dict) -> float:
    return float(Fraction(value["numerator"], value["denominator"]))


def window_summary(window: dict) -> dict:
    cuts = window["shotCutCandidates"]
    intervals = [rational_seconds(x["durationSeconds"])
                 for x in window["editRhythm"]["intervals"]]
    appearance = window["appearanceSamples"]
    pairs = window["imageMotion"].get("pairs", [])
    status_counts = collections.Counter(
        pair["status"] for pair in window["sparseFlow"].get("pairs", []))
    if not appearance:
        raise ValueError("expected sampled appearance evidence")
    return {
        "window": window["window"],
        "sourceOffsetSeconds": window["sourceOffsetSeconds"],
        "scanSeconds": window["scanWindowSeconds"],
        "windowSourceSha256": window["windowSourceSha256"],
        "cutCandidateCount": len(cuts),
        "observedInterCutIntervalCount": len(intervals),
        "medianInterCandidateGapSeconds": round(statistics.median(intervals), 3) if intervals else None,
        "audioLevelAttackCandidateCount": len(window["audioOnsets"].get("candidates", [])),
        "meanSampledLumaProxy": round(statistics.mean(x["meanLumaProxy"] for x in appearance), 4),
        "meanSampledSaturation": round(statistics.mean(x["meanSaturation"] for x in appearance), 4),
        "appearanceFrameSamples": len(appearance),
        "motionMeasuredPairs": sum(x.get("dxPixels") is not None for x in pairs),
        "motionSampledPairs": len(pairs),
        "sparsePairStatuses": dict(sorted(status_counts.items())),
        "cutCandidateCountAtThreshold015": window["sensitivityCutCandidateCount"],
    }


def _publisher_host(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == "video.blender.org"


def _json_public_publisher(url: str) -> dict:
    if not _publisher_host(url):
        raise ValueError("unapproved video metadata host")
    with urlopen(Request(url, headers={"Accept": "application/json"}),
                 timeout=45) as response:
        if not _publisher_host(response.geturl()):
            raise ValueError("video API redirected outside publisher domain")
        payload = response.read(1_000_001)
    if len(payload) > 1_000_000:
        raise ValueError("unexpectedly large video metadata response")
    return json.loads(payload)


def acquire_public_source(directory: Path, target: dict) -> tuple[Path, dict]:
    """Read a known official, public Blender Open Movies PeerTube identity.

    No YouTube downloader, arbitrary host, user cookies or access workaround.
    """
    uuid = target["uuid"]
    metadata = _json_public_publisher(PEERTUBE_ROOT + "/api/v1/videos/" + uuid)
    channel = metadata.get("channel") or {}
    privacy = metadata.get("privacy") or {}
    if (metadata.get("uuid") != uuid
            or metadata.get("name", "").strip().casefold() != target["title"].casefold()
            or (channel.get("name") != "blender_open_movies"
                and channel.get("displayName") != "Blender Open Movies")
            or privacy.get("id") != 1):
        raise ValueError("public Blender Open Movies publisher identity mismatch")
    source_page = PEERTUBE_ROOT + "/videos/watch/" + uuid
    files = list(metadata.get("files", []))
    for playlist in metadata.get("streamingPlaylists", []):
        files.extend(playlist.get("files", []))
    eligible = []
    for item in files:
        source_url = item.get("fileDownloadUrl") or item.get("fileUrl")
        if not isinstance(source_url, str) or not _publisher_host(source_url):
            continue
        size = item.get("size")
        if isinstance(size, int) and size > 200 * 1024 * 1024:
            continue
        resolution = item.get("resolution", {})
        res_id = resolution.get("id", 0) if isinstance(resolution, dict) else 0
        if not isinstance(res_id, int) or res_id < 240:
            continue
        eligible.append((abs(res_id - 480), source_url))
    if not eligible:
        raise ValueError("official Blender PeerTube source has no bounded public file")
    eligible.sort(key=lambda row: row[0])
    original = directory / (target["id"] + ".mp4")
    request = Request(eligible[0][1], headers={"Accept": "video/*"})
    total = 0
    with urlopen(request, timeout=90) as response:
        if not _publisher_host(response.geturl()):
            raise ValueError("publisher media redirected outside the approved domain")
        with original.open("wb") as outfile:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 200 * 1024 * 1024:
                    raise ValueError("publisher media exceeds 200 MiB safety budget")
                outfile.write(chunk)
    if total < 100_000:
        raise ValueError("publisher returned no usable promotional media")
    return original, {
        "sourceTrackId": uuid,
        "officialPlayerUrl": source_page,
        "sourceEdition": target["sourceEdition"],
    }


def generate(target_key: str = "overgrown") -> None:
    target = TARGETS[target_key]
    video_id = target["id"]
    detail_path = DATA / (video_id + ".json")
    if detail_path.exists():
        raise FileExistsError("refusing to overwrite previously measured film")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    if any(v.get("id") == video_id for v in index["videos"]):
        raise ValueError("already indexed: " + video_id)

    with tempfile.TemporaryDirectory(prefix="kumiki-movie-research-") as temporary:
        temp = Path(temporary)
        media = temp / "media"
        runs_root = temp / "runs"
        media.mkdir()
        runs_root.mkdir()
        original, edition = acquire_public_source(media, target)
        duration, resolution = media_info(original)
        original_sha = sha256_file(original)
        offsets = {
            "opening": 0,
            "middle": int((duration - 20) / 2),
            "ending": int(duration - 20.5),
        }
        if offsets["middle"] < 20 or offsets["ending"] - offsets["middle"] < 20:
            raise ValueError("sample windows overlap or exceed the original")
        plan = {
            "id": video_id,
            "catalogId": target["catalogId"],
            "officialPlayerUrl": edition["officialPlayerUrl"],
            "sourceTrackId": edition["sourceTrackId"],
            "sourceEdition": edition["sourceEdition"],
            "sourceSha256": original_sha,
            "sourceDurationSeconds": duration,
            "sourceResolution": resolution,
            "catalogUploadIdentityMatch": "not-verified",
            "windows": [],
        }
        for name, offset in offsets.items():
            slug = video_id + ("" if name == "opening" else "-" + name)
            clip = media / (slug + ".mp4")
            if name != "opening":
                run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(offset), "-i", str(original), "-t", "20",
                    "-map", "0:v:0", "-map", "0:a:0",
                    "-vf", "scale=640:-2",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
                    "-c:a", "aac", "-b:a", "96k", str(clip))
            if not clip.is_file():
                raise ValueError(f"{name}: source clip absent")
            run("kumiki-ref", "study-reference", str(clip),
                "--max-seconds", "20", "--out", str(runs_root / slug))
            sensitive = json.loads(run("kumiki-ref", "cuts", str(clip),
                                       "--max-seconds", "20", "--threshold",
                                       "0.15", output=True))
            if sensitive["sourceSha256"] != sha256_file(clip):
                raise ValueError(f"{name}: threshold source identity mismatch")
            plan["windows"].append({
                "window": name, "sourceOffsetSeconds": offset,
                "windowSourceSha256": sha256_file(clip),
                "cutCandidateCountAtThreshold015": len(sensitive["candidates"]),
            })

        detail = build_evidence(plan, media_root=media, runs_root=runs_root)
        summaries = [window_summary(w) for w in detail["windows"]]
        record = {
            "id": plan["id"],
            "catalogId": plan["catalogId"],
            "officialPlayerUrl": plan["officialPlayerUrl"],
            "sourceSha256": plan["sourceSha256"],
            "sourceDurationSeconds": duration,
            "sourceResolution": resolution,
            "catalogUploadIdentityMatch": "not-verified",
            "sourceTrackId": edition["sourceTrackId"],
            "sourceEdition": edition["sourceEdition"],
            "windows": summaries,
        }
        index["videos"].append(record)
        index["scope"] = (
            f"{sum(len(v['windows']) for v in index['videos'])} selected "
            f"non-overlapping 20-second windows across {len(index['videos'])} "
            "source-hashed movie promotions; not whole-trailer coverage."
        )
        index["method"] += (
            f" Additional {target['title']} official Blender Open Movies public "
            "PeerTube teaser was downloaded, source-hashed, measured in three "
            "bounded windows, and deleted after numeric export. PeerTube edition "
            "identity is not assumed identical to alternate YouTube uploads."
        )
        index["mediaCleanupStatus"] = "verified-deleted-after-export"
        # Fail closed while the temporary footage still exists: nothing is
        # committed until this function exits and the temp directory is gone.
        staged_index = temp / "index.json"
        staged_detail = temp / "detail.json"
        staged_index.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
        staged_detail.write_text(json.dumps(detail, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
        detail_path.write_bytes(staged_detail.read_bytes())
        INDEX.write_bytes(staged_index.read_bytes())
        issues = audit(DATA)
        if issues:
            raise ValueError("evidence integrity audit failed: " + "; ".join(issues))
        print(f"analyzed {video_id}: sourceSHA256={original_sha}, "
              f"duration={duration:.3f}, windows=3", flush=True)

    # TemporaryDirectory has been removed before any file can be git-staged.
    # Media has been deleted; regenerate and verify all dependent numeric reports.
    write_reports(DATA)
    assert not list(DATA.glob("*.mp4"))
    print("all temporary audio/video/frame media deleted; numeric-only evidence ready")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=sorted(TARGETS), required=True,
                        help="explicit, source-identified Blender publisher film")
    generate(parser.parse_args().target)
