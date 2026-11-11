"""Small-agent-friendly, offline frame review: view, advance, annotate, export.

Source video is temporary. Low-resolution PNGs live only in Git-ignored
workspace/frame-review/<id>/, until explicitly cleaned up. Image-capable
agents can open any numbered PNG without loading a full video or long prompt.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "kumiki.agent-frame-workspace.v1"
NOTES_VERSION = "kumiki.agent-frame-notes.v1"
_CATEGORIES = (
    "animation", "typography", "character", "camera", "lighting",
    "composition", "visual-style", "transition", "material", "other",
)
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,85}$")


def _write_json_atomic(path: Path, document: dict[str, Any]) -> None:
    data = (json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")
    if len(data) > 8_000_000:
        raise ValueError("frame review JSON exceeds 8 MiB")
    filename: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".review-",
                                         dir=path.parent, suffix=".tmp",
                                         delete=False) as stream:
            filename = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(filename, path)
        filename = None
    finally:
        if filename:
            Path(filename).unlink(missing_ok=True)


def make_frame_sink(staging: Path, *, max_bytes: int = 256 * 1024 * 1024,
                    max_frames: int = 108000) -> Callable[[int, bytes], None]:
    """Write individually addressable PNGs, with an enforced total disk budget."""
    if (type(max_bytes) is not int or not 1 <= max_bytes <= 1024 * 1024 * 1024
            or type(max_frames) is not int or not 1 <= max_frames <= 108000
            or not staging.is_dir() or staging.is_symlink()):
        raise ValueError("invalid frame-workspace limits")
    frames = staging / "frames"
    frames.mkdir()
    total = 0
    count = 0

    def save(index: int, png: bytes) -> None:
        nonlocal total, count
        if (type(index) is not int or index != count or count >= max_frames
                or not isinstance(png, bytes) or
                not png.startswith(b"\x89PNG\r\n\x1a\n")):
            raise ValueError("frame sink received unordered or invalid frame data")
        total += len(png)
        if total > max_bytes:
            raise ValueError("frame previews exceeded local disk budget")
        (frames / f"frame-{index:06d}.png").write_bytes(png)
        count += 1

    return save


def _render_viewer(frame_count: int) -> str:
    """Standalone file:// viewer; references local preview PNGs, no network."""
    return ("""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Kumiki Frame Review</title>
<style>
body{font-family:system-ui;background:#11151e;color:#eef2fa;margin:2em auto;max-width:1000px}
img{width:100%;max-height:70vh;object-fit:contain;image-rendering:auto;background:#080a10}
button,input{font-size:1.05rem;padding:.45em;background:#253145;color:white;border:1px solid #52647a}
p{color:#adb9ca}
</style><h1>Frame-by-frame review</h1><p>Offline previews only. Arrow keys step frames.</p>
<img id="frame" alt="Decoded source frame"><p id="counter"></p>
<button id="prev">Previous</button> <button id="next">Next</button>
<input id="seek" type="range" min="0" max="__MAX__" value="0" style="width:45%">
<script>
const count=__COUNT__,img=document.getElementById('frame');
const label=document.getElementById('counter'),seek=document.getElementById('seek');
let index=0;
function render(i){index=Math.max(0,Math.min(count-1,i));
img.src='frames/frame-'+String(index).padStart(6,'0')+'.png';
label.textContent='Frame '+index+' / '+(count-1);seek.value=index}
document.getElementById('prev').onclick=()=>render(index-1);
document.getElementById('next').onclick=()=>render(index+1);
seek.oninput=()=>render(Number(seek.value));
document.onkeydown=e=>{if(e.key==='ArrowLeft')render(index-1);
if(e.key==='ArrowRight')render(index+1)};render(0)
</script></html>""".replace("__MAX__", str(frame_count - 1))
             .replace("__COUNT__", str(frame_count)))


def finalize_frame_workspace(
    staging: Path, *, study_id: str, watch_url: str,
    numeric: dict[str, Any], preview_width: int, preview_height: int,
) -> None:
    if not _ID.fullmatch(study_id) or not staging.is_dir() or staging.is_symlink():
        raise ValueError("invalid frame workspace destination")
    frame_count = numeric["frameCount"]
    if (type(frame_count) is not int or frame_count < 1 or
            len(numeric["frames"]) != frame_count):
        raise ValueError("numeric frame count is inconsistent")
    frames_dir = staging / "frames"
    if (not frames_dir.is_dir() or frames_dir.is_symlink() or
            len(list(frames_dir.iterdir())) != frame_count):
        raise ValueError("frame review previews must cover every decoded frame")
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "id": study_id,
        "watchUrl": watch_url,
        "sourceSha256": numeric["sourceSha256"],
        "referenceFilename": study_id + ".json",
        "frameCount": frame_count,
        "width": preview_width,
        "height": preview_height,
        "previewFormat": "PNG",
        "previewRetention": "local-gitignored-until-cleanup",
        "reviewStatus": "unreviewed",
    }
    _write_json_atomic(staging / "manifest.json", manifest)
    (staging / "index.html").write_text(_render_viewer(frame_count), encoding="utf-8")


def _review_paths(workspace: Path) -> tuple[Path, Path]:
    workspace = workspace.absolute()
    if (workspace.is_symlink() or not workspace.is_dir()
            or workspace.parent.name != "frame-review"
            or workspace.parent.parent.name != "workspace"
            or not _ID.fullmatch(workspace.name)):
        raise ValueError("workspace must be an existing Git-ignored workspace/frame-review/<id>")
    return workspace, workspace.parent.parent.parent


def load_workspace(workspace: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    workspace, root = _review_paths(workspace)
    manifest_path = workspace / "manifest.json"
    if (manifest_path.is_symlink() or not manifest_path.is_file() or
            manifest_path.stat().st_size > 16000):
        raise ValueError("frame review manifest missing or unsafe")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schemaVersion") != SCHEMA_VERSION or
            manifest.get("id") != workspace.name or
            manifest.get("referenceFilename") != workspace.name + ".json"
            or not re.fullmatch(r"[a-f0-9]{64}", manifest.get("sourceSha256", ""))):
        raise ValueError("invalid frame review manifest")
    reference = root / "research" / "analysis" / "online-videos" / manifest["referenceFilename"]
    if not reference.is_file() or reference.is_symlink() or reference.stat().st_size > 90_000_000:
        raise ValueError("source reference evidence is missing")
    report = json.loads(reference.read_text(encoding="utf-8"))
    numeric = report["numericEvidence"]
    if (numeric["sourceSha256"] != manifest["sourceSha256"] or
            len(numeric["frames"]) != manifest["frameCount"] or
            report["id"] != manifest["id"]):
        raise ValueError("review workspace and source reference disagree")
    return manifest, numeric, reference


def _frame_path(workspace: Path, index: int) -> Path:
    file = workspace / "frames" / f"frame-{index:06d}.png"
    if not file.is_file() or file.is_symlink():
        raise ValueError("requested frame preview is missing")
    return file


def show_frame(workspace: Path, index: int) -> dict[str, Any]:
    manifest, numeric, reference = load_workspace(workspace)
    total = manifest["frameCount"]
    if type(index) is not int or not 0 <= index < total:
        raise ValueError("frame index out of range")
    row = numeric["frames"][index]
    response = {
        "frameIndex": index, "frameCount": total,
        "imagePath": str(_frame_path(workspace.absolute(), index)),
        "decodedSeconds": row["decodedSeconds"],
        "decodedPts": row["decodedPts"],
        "appearance": row["appearance"],
        "changeFromPrevious": row["changeFromPrevious"],
        "cutCandidate": row["cutCandidate"],
        "previousImagePath": str(_frame_path(workspace.absolute(), index - 1))
                             if index > 0 else None,
        "nextImagePath": str(_frame_path(workspace.absolute(), index + 1))
                         if index < total - 1 else None,
        "sourceReference": str(reference),
        "instruction": (
            "Open imagePath to see pixels; use previousImagePath/nextImagePath "
            "for motion comparisons. Do not infer exact fonts or people identities."
        ),
    }
    return response


def next_frame(workspace: Path, *, after: int = -1,
               mode: str = "every", min_change: float = .08,
               interval: int = 24) -> dict[str, Any]:
    manifest, numeric, _ = load_workspace(workspace)
    if (type(after) is not int or not -1 <= after < manifest["frameCount"]
            or mode not in ("every", "cuts", "changed", "interval", "shots")
            or type(min_change) not in (int, float) or not 0 <= min_change <= 1
            or type(interval) is not int or not 1 <= interval <= 3600):
        raise ValueError("invalid frame review selection")
    shot_frames = None
    if mode == "shots":
        from kumiki_reference_lab.pipeline.shot_intelligence import build_shot_intelligence
        shot_frames = {i for shot in build_shot_intelligence(numeric)["shots"]
                       for i in shot["representativeFrameIndices"]}
    for i in range(after + 1, manifest["frameCount"]):
        row = numeric["frames"][i]
        if ((mode == "shots" and i in shot_frames) or mode == "every" or
                (mode == "cuts" and row["cutCandidate"]) or
                (mode == "changed" and row["changeFromPrevious"] and
                 row["changeFromPrevious"]["meanPixelDelta"] >= min_change) or
                (mode == "interval" and i % interval == 0)):
            return show_frame(workspace, i)
    return {"complete": True, "frameCount": manifest["frameCount"],
            "lastInspectedIndex": after, "mode": mode}


def _load_annotations(workspace: Path) -> list[dict[str, Any]]:
    path = workspace / "annotations.json"
    if not path.exists():
        return []
    if path.is_symlink() or path.stat().st_size > 8_000_000:
        raise ValueError("annotations file is oversized or unsafe")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(doc, dict) or doc.get("schemaVersion") != NOTES_VERSION
            or not isinstance(doc.get("observations"), list)
            or len(doc["observations"]) > 10000):
        raise ValueError("annotation file has invalid structure")
    return doc["observations"]


def annotate_frame(
    workspace: Path, *, start: int, end: int | None = None,
    category: str, description: str, evidence: str = "",
    confidence: str = "low",
) -> dict[str, Any]:
    manifest, numeric, _ = load_workspace(workspace)
    if end is None:
        end = start
    if (type(start) is not int or type(end) is not int or
            not 0 <= start <= end < manifest["frameCount"] or
            end - start > 1800 or category not in _CATEGORIES or
            confidence not in ("low", "medium", "high") or
            type(description) is not str or not 3 <= len(description.strip()) <= 240
            or type(evidence) is not str or len(evidence) > 240):
        raise ValueError("annotation is missing bounded, reviewable visual evidence")
    note = {
        "startFrameIndex": start, "endFrameIndex": end,
        "startSeconds": numeric["frames"][start]["decodedSeconds"],
        "endSeconds": numeric["frames"][end]["decodedSeconds"],
        "category": category, "description": description.strip(),
        "evidence": evidence.strip(), "confidence": confidence,
        "reviewStatus": "agent-proposal-not-human-verified",
    }
    note["id"] = hashlib.sha256(json.dumps(note, sort_keys=True).encode()).hexdigest()[:16]
    prior = _load_annotations(workspace)
    if len(prior) >= 10000:
        raise ValueError("annotation limit reached")
    if all(existing["id"] != note["id"] for existing in prior):
        prior.append(note)
    _write_json_atomic(workspace / "annotations.json", {
        "schemaVersion": NOTES_VERSION, "observations": prior,
    })
    return note


def export_annotations(workspace: Path) -> Path:
    manifest, _, reference = load_workspace(workspace)
    notes = _load_annotations(workspace)
    destination = reference.with_suffix(".frame-notes.json")
    if destination.is_symlink():
        raise ValueError("unsafe annotation export path")
    doc = {
        "schemaVersion": NOTES_VERSION, "sourceReference": reference.name,
        "sourceSha256": manifest["sourceSha256"],
        "sourceWatchUrl": manifest["watchUrl"],
        "frameCount": manifest["frameCount"],
        "observations": notes,
        "reviewStatus": "unreviewed-machine-annotations",
        "mediaRetainedInGit": False,
    }
    _write_json_atomic(destination, doc)
    return destination


def cleanup_workspace(workspace: Path) -> None:
    workspace, _ = _review_paths(workspace)
    load_workspace(workspace)
    # Delete only the specific validated local frame-review folder. Never
    # touch source videos, repository analysis evidence or other workspaces.
    for p in workspace.rglob("*"):
        if p.is_symlink():
            raise ValueError("refuse to clean a workspace with symlinks")
    shutil.rmtree(workspace)



def scan_frames(
    workspace: Path, *, model: str, categories: tuple[str, ...] = (
        "animation", "typography", "visual-style",
    ), mode: str = "changed", after: int = -1,
    max_calls: int = 24, max_failures: int = 3,
    min_change: float = .08, interval: int = 24,
    port: int = 10100, timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Bounded, resumable low-model inference, one short task at a time.

    Skip already annotated frame/category pairs. Failures are reported, not
    published as observations. Stop once the failure budget is exhausted.
    """
    if (type(max_calls) is not int or not 1 <= max_calls <= 500
            or type(max_failures) is not int or not 1 <= max_failures <= 50
            or not categories or len(categories) > 10
            or any(cat not in _CATEGORIES for cat in categories)
            or len(set(categories)) != len(categories)):
        raise ValueError("invalid low-resource scan budget or categories")
    manifest, numeric, _ = load_workspace(workspace)
    if (type(after) is not int or not -1 <= after < manifest["frameCount"]
            or mode not in ("every", "changed", "cuts", "interval", "shots")
            or type(min_change) not in (int, float) or not 0 <= min_change <= 1
            or type(interval) is not int or not 1 <= interval <= 3600):
        raise ValueError("invalid scan frame selection")
    from kumiki_reference_lab.pipeline.magnitude_vision import infer_workspace_frame
    prior = _load_annotations(workspace)
    visited = {(x["endFrameIndex"], x["category"]) for x in prior}
    # Read the numeric report ONCE, rather than reparsing it for every frame.
    if mode == "shots":
        from kumiki_reference_lab.pipeline.shot_intelligence import (
            build_shot_intelligence, prioritized_frame_plan,
        )
        source_shots = build_shot_intelligence(numeric)
        plan = prioritized_frame_plan(
            source_shots, max_frames=min(1000, manifest["frameCount"]))
        targets = [row["frameIndex"] for row in plan["frameTasks"]
                   if row["frameIndex"] > after]
    else:
        targets = [0] if after < 0 else []
    for i in ([] if mode == "shots" else range(after + 1, manifest["frameCount"])):
        row = numeric["frames"][i]
        if (mode == "every" or
                (mode == "cuts" and row["cutCandidate"]) or
                (mode == "changed" and row["changeFromPrevious"] and
                 row["changeFromPrevious"]["meanPixelDelta"] >= min_change) or
                (mode == "interval" and i % interval == 0)):
            if i not in targets:
                targets.append(i)
    attempts = successes = failures = skipped = 0
    errors: list[dict[str, Any]] = []
    exhausted = False
    last_index = after
    for idx in targets:
        for category in categories:
            if (idx, category) in visited:
                skipped += 1
                continue
            if attempts >= max_calls or failures >= max_failures:
                exhausted = True
                break
            attempts += 1
            try:
                infer_workspace_frame(
                    workspace, index=idx, category=category, model=model,
                    port=port, timeout_seconds=timeout_seconds, save=True,
                )
            except (ValueError, OSError) as exc:
                failures += 1
                # Never echo server exception bodies or sensitive media URLs.
                errors.append({"frameIndex": idx, "category": category,
                               "errorClass": type(exc).__name__})
            else:
                successes += 1
                visited.add((idx, category))
            last_index = idx
        if exhausted:
            break
    notes_path = export_annotations(workspace)
    return {
        "schemaVersion": "kumiki.low-compute-frame-scan.v1",
        "sourceSha256": manifest["sourceSha256"],
        "frameCount": manifest["frameCount"],
        "mode": mode, "categories": list(categories),
        "modelTag": model, "modelCalls": attempts, "successful": successes,
        "failed": failures, "alreadyAnnotatedSkipped": skipped,
        "lastAttemptedFrameIndex": last_index,
        "remainingWork": exhausted, "errors": errors,
        "savedTo": str(notes_path),
        "status": "unreviewed-machine-hypotheses",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent-friendly frame-by-frame review")
    parser.add_argument("command", choices=["show", "next", "annotate", "infer", "scan", "export", "cleanup"])
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--after", type=int, default=-1)
    parser.add_argument("--mode", choices=["every", "cuts", "changed", "interval", "shots"])
    parser.add_argument("--interval", type=int, default=24)
    parser.add_argument("--min-change", type=float, default=.08)
    parser.add_argument("--end", type=int)
    parser.add_argument("--category", choices=_CATEGORIES, default="animation")
    parser.add_argument("--description", default="")
    parser.add_argument("--evidence", default="")
    parser.add_argument("--confidence", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--model", help="local Magnitude vision model for infer")
    parser.add_argument("--port", type=int, default=10100)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--categories", default="animation,typography,visual-style")
    parser.add_argument("--max-calls", type=int, default=24)
    parser.add_argument("--max-failures", type=int, default=3)
    parser.add_argument("--no-save", action="store_true", help="infer without saving an annotation")
    args = parser.parse_args(argv)
    try:
        if args.command == "show":
            result: Any = show_frame(args.workspace, args.index)
        elif args.command == "next":
            result = next_frame(args.workspace, after=args.after,
                                mode=args.mode or "every", min_change=args.min_change,
                                interval=args.interval)
        elif args.command == "annotate":
            result = annotate_frame(
                args.workspace, start=args.index, end=args.end,
                category=args.category, description=args.description,
                evidence=args.evidence, confidence=args.confidence,
            )
        elif args.command == "infer":
            from kumiki_reference_lab.pipeline.magnitude_vision import infer_workspace_frame
            result = infer_workspace_frame(
                args.workspace, index=args.index, category=args.category,
                model=args.model, port=args.port, timeout_seconds=args.timeout,
                save=not args.no_save,
            )
        elif args.command == "scan":
            result = scan_frames(
                args.workspace, model=args.model,
                categories=tuple(s.strip() for s in args.categories.split(",")),
                mode=args.mode or "changed", after=args.after, max_calls=args.max_calls,
                max_failures=args.max_failures, interval=args.interval,
                min_change=args.min_change, port=args.port,
                timeout_seconds=args.timeout,
            )
        elif args.command == "export":
            result = {"savedTo": str(export_annotations(args.workspace))}
        else:
            cleanup_workspace(args.workspace)
            result = {"cleaned": True}
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"frame review failed: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
