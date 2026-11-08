"""Temporary local cross-repository integration fixture; no production assets."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description="Local real-PTS Reference Lab ↔ Kumiki UI integration smoke")
parser.add_argument("--kumiki-ui", type=Path, required=True,
                    help="path to a checked-out kumiki-ui repository")
UI = parser.parse_args().kumiki_ui.resolve()
if not (UI / "scripts/film-feedback-queue.mjs").is_file():
    parser.error("expected a kumiki-ui checkout containing film-feedback-queue.mjs")
sys.path.insert(0, str(LAB / "src"))

from kumiki_reference_lab.analyzers.media.inspect import inspect_source, sha256_file
from kumiki_reference_lab.backends.ffmpeg.frames import read_frame_pts
from kumiki_reference_lab.core.timebase import as_rational_dict


def run(*args, cwd=None):
    result = subprocess.run([str(x) for x in args], cwd=cwd, text=True,
                            capture_output=True, timeout=120,
                            env={**os.environ, "PYTHONPATH": str(LAB / "src")})
    if result.returncode:
        raise RuntimeError(f"Failed: {args}\n{result.stderr}")
    return result.stdout.strip()


# Synthetically declared interior windows exercise the contract. They are not
# claims about actual detected cuts or creative matching quality.
with tempfile.TemporaryDirectory(prefix="kumiki-real-pts-e2e-") as name:
    tmp = Path(name)
    original, render = tmp / "source.mkv", tmp / "render.mkv"
    for path, fps in ((original, 10), (render, 30)):
        run("ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=s=160x90:r={fps}:d=3",
            "-c:v", "ffv1", str(path))
    video = inspect_source(original)["video"]
    tb = Fraction(**video["sourceTimebase"])
    frames = read_frame_pts(original, video["streamIndex"], seconds=3)
    indexed = {frame.pts * tb: frame.pts for frame in frames}
    start, end, chosen = (indexed[Fraction(n, 10)] for n in (10, 20, 11))

    film = {
        "schemaVersion": 1, "id": "cross-repo-test", "fps": {"num": 30, "den": 1},
        "outputs": [{"id": "landscape", "preset": "youtube"}],
        "scenes": [{"id": "cause", "recipeId": "cause-effect", "durationFrames": 90,
                    "cueFrames": [25, 55, 80],
                    "content": {"initial": "Cause", "event": "An event",
                                "links": ["Connection"], "outcome": "Effect",
                                "qualification": "Demonstration"}}],
    }
    handoff = {
        "schemaVersion": "kumiki.film-handoff.v1",
        "status": "candidate-drafting-evidence-not-an-executable-film",
        "study": {"sourceSha256": sha256_file(original), "manifestSha256": "a" * 64},
        "target": {"repository": "YukiUmetsu/kumiki-ui",
                   "executableDocument": False, "installedCapabilitiesVerified": False},
        "timing": {"videoSourceTimebase": as_rational_dict(tb),
                   "audioVideoClockRelation": "not-independently-synchronized"},
        "interiorWindows": [{"id": "candidate-interval-001",
                             "startCutCandidatePts": start, "endCutCandidatePts": end,
                             "sourceStartSeconds": as_rational_dict(start * tb),
                             "sourceEndSeconds": as_rational_dict(end * tb),
                             "sourceDurationSeconds": as_rational_dict((end - start) * tb),
                             "sceneRecipeId": None, "sceneContent": None,
                             "reviewStatus": "not-reviewed"}],
    }
    anchors = {
        "schemaVersion": "kumiki.reference-anchors.v1",
        "sourceSha256": sha256_file(original),
        "anchors": [{"id": "focus-01", "sourceWindowId": "candidate-interval-001",
                     "sourcePts": chosen, "filmSceneId": "cause", "filmFrameOffset": 3,
                     "relationship": "inspired-by",
                     "note": "Review the camera perspective at this causal change."}],
    }
    paths = {}
    for key, data in (("film", film), ("handoff", handoff), ("anchors", anchors)):
        path = tmp / f"{key}.json"
        path.write_text(json.dumps(data))
        paths[key] = path
    map_path = tmp / "reference-film-map.json"
    run("node", UI / "scripts/film-reference-map.mjs", paths["handoff"], paths["film"],
        paths["anchors"], f"--out={map_path}", cwd=UI)
    report_index = run(sys.executable, "-m", "kumiki_reference_lab", "review-film-map",
                       map_path, paths["film"], original, render,
                       "--max-seconds", "3", "--out", tmp / "runs", cwd=LAB)
    manifest = Path(report_index).parent / "film-map-review.json"
    feedback_path = run(sys.executable, "-m", "kumiki_reference_lab", "film-feedback",
                        "init", manifest, "--reviewer-id", "editor-1", "--out",
                        tmp / "feedback", cwd=LAB)
    feedback_data = json.loads(Path(feedback_path).read_text())
    feedback_data["findings"] = [{
        "id": "finding-perspective", "anchorId": "focus-01", "category": "camera",
        "severity": "significant", "observation": "The synthetic shot lacks intentional framing.",
        "suggestedChange": "Replace it with an authored camera movement.",
    }]
    Path(feedback_path).write_text(json.dumps(feedback_data))
    run(sys.executable, "-m", "kumiki_reference_lab", "film-feedback", "validate",
        manifest, feedback_path, cwd=LAB)
    queue_path = tmp / "queue.json"
    run("node", UI / "scripts/film-feedback-queue.mjs", map_path, manifest,
        feedback_path, paths["film"], f"--out={queue_path}", cwd=UI)
    queue = json.loads(queue_path.read_text())
    assert len(queue["tasks"]) == 1
    assert queue["tasks"][0]["sceneId"] == "cause"
    assert queue["tasks"][0]["filmFrame"] == 3
    assert queue["artisticApproval"] == "not-granted"
    print("PASS: real FFmpeg source/render PTS -> FD1 review map -> JPEG evidence -> feedback -> scene queue")
