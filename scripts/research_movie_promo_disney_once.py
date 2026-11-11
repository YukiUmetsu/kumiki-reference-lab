"""One-shot, source-hashed analysis of an openly playable Disney trailer.

Only downloads a public, unauthenticated publisher stream. All audiovisual
media and image galleries live in TemporaryDirectory and are deleted before
the resulting numeric JSON is staged. Never circumvent DRM or authorization.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import shutil
import statistics
import subprocess
import tempfile
from datetime import date
from fractions import Fraction
from pathlib import Path

from scripts.audit_movie_promo_evidence import audit
from scripts.export_movie_promo_evidence import build_evidence
from scripts.summarize_movie_promo_evidence import build_comparison


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research/analysis/movie-promotions"
INDEX = DATA / "index.json"
DETAIL = DATA / "elemental-official-trailer.json"
SOURCE_URL = "https://video.disney.com/watch/elemental-official-trailer-5f7f993024c6cebd6b4f2a72"
VIDEO_ID = "elemental-official-trailer"


def run(*command: str, output: bool = False) -> str:
    result = subprocess.run(command, check=True, text=True, capture_output=True)
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


def acquire_public_source(directory: Path) -> Path:
    target = directory / (VIDEO_ID + ".mp4")
    # The normal publisher stream only: no cookies, authentication, proxies,
    # DRM workarounds or third-party mirror URLs. yt-dlp's Disney extractor.
    run("yt-dlp", "--no-playlist", "--no-progress", "--no-warnings",
        "--max-filesize", "200M",
        "-f", "best[ext=mp4][height<=480]/best[ext=mp4]",
        "-o", str(target), SOURCE_URL)
    if not target.is_file() or target.stat().st_size < 100_000:
        raise ValueError("publisher did not provide a usable public MP4")
    return target


def generate() -> None:
    if DETAIL.exists():
        raise FileExistsError("refusing to overwrite previously measured film")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    if any(v.get("id") == VIDEO_ID for v in index["videos"]):
        raise ValueError("already indexed: " + VIDEO_ID)

    with tempfile.TemporaryDirectory(prefix="kumiki-movie-research-") as temporary:
        temp = Path(temporary)
        media = temp / "media"
        runs_root = temp / "runs"
        media.mkdir()
        runs_root.mkdir()
        original = acquire_public_source(media)
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
            "id": VIDEO_ID,
            "catalogId": "uncataloged-disney-elemental-official-trailer",
            "officialPlayerUrl": SOURCE_URL,
            "sourceSha256": original_sha,
            "sourceDurationSeconds": duration,
            "sourceResolution": resolution,
            "catalogUploadIdentityMatch": "not-cataloged",
            "windows": [],
        }
        for name, offset in offsets.items():
            slug = VIDEO_ID + ("" if name == "opening" else "-" + name)
            clip = media / (slug + ".mp4")
            if name != "opening":
                run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(offset), "-i", str(original), "-t", "20",
                    "-map", "0:v:0", "-map", "0:a:0",
                    "-vf", "scale=trunc(min(960,iw)/2)*2:-2",
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
            "catalogUploadIdentityMatch": "not-cataloged",
            "windows": summaries,
        }
        index["videos"].append(record)
        index["scope"] = (
            f"{sum(len(v['windows']) for v in index['videos'])} selected "
            f"non-overlapping 20-second windows across {len(index['videos'])} "
            "source-hashed movie promotions; not whole-trailer coverage."
        )
        index["method"] += (
            " Additional Elemental official Disney public-player video was "
            "downloaded with unauthenticated public access, hashed, measured "
            "in three bounded windows, and deleted immediately after export."
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
        DETAIL.write_bytes(staged_detail.read_bytes())
        INDEX.write_bytes(staged_index.read_bytes())
        issues = audit(DATA)
        if issues:
            raise ValueError("evidence integrity audit failed: " + "; ".join(issues))
        print(f"analyzed {VIDEO_ID}: sourceSHA256={original_sha}, "
              f"duration={duration:.3f}, windows=3", flush=True)

    # TemporaryDirectory has been removed before any file can be git-staged.
    comparison_path = DATA / "derived/comparison.v1.json"
    index_bytes = INDEX.read_bytes()
    git_blob = hashlib.sha1(
        b"blob " + str(len(index_bytes)).encode("ascii") + b"\0" + index_bytes).hexdigest()
    comparison = build_comparison(json.loads(index_bytes), git_blob)
    comparison_path.write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert not list(DATA.glob("*.mp4"))
    print("all temporary audio/video/frame media deleted; numeric-only evidence ready")


if __name__ == "__main__":
    generate()
