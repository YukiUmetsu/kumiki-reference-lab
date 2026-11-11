"""Optional offline OCR of sampled local frame previews with Tesseract.

OCR text and screen-space boxes are cues; exact font recognition, authored
letter animation and stable title identity are NOT established. No network.
"""
from __future__ import annotations

import csv
import io
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kumiki.online-screen-text.v1"


def parse_tesseract_tsv(
    data: str, *, width: int, height: int, max_lines: int = 20,
) -> list[dict[str, Any]]:
    if (type(data) is not str or len(data) > 2_000_000
            or type(width) is not int or type(height) is not int
            or not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("OCR TSV exceeds bounded preview constraints")
    reader = csv.DictReader(io.StringIO(data), delimiter="\t")
    if reader.fieldnames is None or not {
            "left", "top", "width", "height", "conf", "text",
            "block_num", "par_num", "line_num",
    }.issubset(reader.fieldnames):
        raise ValueError("unexpected Tesseract TSV columns")
    lines: dict[tuple[str, str, str], list[tuple[int, int, int, int, str, float]]] = {}
    for i, row in enumerate(reader):
        if i >= 2000:
            raise ValueError("OCR TSV word budget exceeded")
        text = re.sub(r"\s+", " ", row["text"] or "").strip()
        if not text:
            continue
        try:
            conf = float(row["conf"])
            x, y, w, h = (int(row[c]) for c in ("left", "top", "width", "height"))
        except (TypeError, ValueError) as exc:
            raise ValueError("OCR TSV contains invalid coordinates") from exc
        if (not math.isfinite(conf) or conf < 40 or
                not 0 <= x < width or not 0 <= y < height or
                not 0 < w <= width - x or not 0 < h <= height - y):
            continue
        group = (row["block_num"], row["par_num"], row["line_num"])
        lines.setdefault(group, []).append((x, y, w, h, text[:80], conf))
    result = []
    for words in lines.values():
        x = min(w[0] for w in words)
        y = min(w[1] for w in words)
        right = max(w[0] + w[2] for w in words)
        bottom = max(w[1] + w[3] for w in words)
        text = " ".join(w[4] for w in sorted(words, key=lambda v: v[0]))[:80]
        if len(text) < 2:
            continue
        result.append({
            "visibleText": text,
            "boxNormalized": [
                round(x / width, 5), round(y / height, 5),
                round((right - x) / width, 5),
                round((bottom - y) / height, 5),
            ],
            "meanOcrConfidence": round(sum(w[5] for w in words) / len(words), 2),
            "status": "unverified-small-preview-ocr",
        })
    return sorted(result, key=lambda row: (
        row["boxNormalized"][1], row["boxNormalized"][0]))[:max_lines]


def build_screen_text(
    workspace: Path, shots: dict[str, Any], *,
    max_frames: int = 48, tesseract: str = "tesseract",
) -> dict[str, Any]:
    from kumiki_reference_lab.pipeline.agent_frame_review import load_workspace
    from kumiki_reference_lab.pipeline.shot_intelligence import prioritized_frame_plan
    if type(max_frames) is not int or not 1 <= max_frames <= 96:
        raise ValueError("OCR frame budget must be 1..96")
    manifest, _, _ = load_workspace(workspace)
    if manifest["sourceSha256"] != shots["sourceSha256"]:
        raise ValueError("OCR provenance and shots do not match")
    plan = prioritized_frame_plan(shots, max_frames=max_frames)
    base = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha256": manifest["sourceSha256"],
        "observedFrames": [], "textMotionCandidates": [],
        "limitations": [
            "Small OCR previews may omit or misread letters.",
            "Matching text strings across distant samples does not prove stable object identity.",
            "No exact font family, text keyframes or authored typography motion is recovered.",
        ],
    }
    if not shutil.which(tesseract):
        return {**base, "status": "not-run-tesseract-not-installed"}
    previous: dict[tuple[str, str], tuple[int, list[float]]] = {}
    for task in sorted(plan["frameTasks"], key=lambda x: x["frameIndex"]):
        idx = task["frameIndex"]
        path = workspace / "frames" / f"frame-{idx:06d}.png"
        if (path.is_symlink() or not path.is_file() or
                path.stat().st_size > 1_000_000):
            raise ValueError("OCR preview missing or unsafe")
        try:
            done = subprocess.run(
                [tesseract, str(path.resolve()), "stdout", "--psm", "11", "tsv"],
                stdin=subprocess.DEVNULL, capture_output=True,
                check=False, timeout=12,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("local Tesseract failed to complete a bounded OCR job") from exc
        if done.returncode or len(done.stdout) > 2_000_000:
            raise ValueError("local OCR returned an unusable result")
        observations = parse_tesseract_tsv(
            done.stdout.decode("utf-8", errors="replace"),
            width=manifest["width"], height=manifest["height"],
        )
        base["observedFrames"].append({
            "frameIndex": idx, "shotId": task["shotId"],
            "textLines": observations,
        })
        for item in observations:
            key = task["shotId"], item["visibleText"].casefold()
            last = previous.get(key)
            if last:
                prev_i, box = last
                now = item["boxNormalized"]
                movement = math.hypot((now[0] + now[2]/2) - (box[0] + box[2]/2),
                                      (now[1] + now[3]/2) - (box[1] + box[3]/2))
                if movement >= .025:
                    base["textMotionCandidates"].append({
                        "startFrameIndex": prev_i, "endFrameIndex": idx,
                        "shotId": task["shotId"],
                        "visibleText": item["visibleText"],
                        "centerDisplacementNormalized": round(movement, 5),
                        "status": "candidate-text-position-change-not-verified-animation",
                    })
            previous[key] = idx, item["boxNormalized"]
    return {**base, "status": "unreviewed-local-ocr-observations",
            "reviewedFrameCount": len(base["observedFrames"])}
