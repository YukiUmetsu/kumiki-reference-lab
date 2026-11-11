"""Deterministic shot candidates and sparse image-plane motion for weak local AI.

Works entirely from saved frame evidence and low-resolution local review PNGs.
No model calls, no video re-download, no claims of tracked objects or true camera
movement. Returned source times are FFmpeg decoder PTS-derived proxies.
"""
from __future__ import annotations

import math
import statistics
import struct
import zlib
from pathlib import Path
from typing import Any

VERSION = "kumiki.online-temporal-analysis.v1"
_LIMITS = [
    "Shot boundaries are grouped frame-difference cut candidates, not verified edit decisions.",
    "A flash, rapid motion or dissolve can produce false or missed shot boundaries.",
    "Display frame differences are not optical flow or object trajectories.",
    "Block matching produces approximate image-plane translation of textured patches.",
    "Dominant image-plane motion is NOT proof of a physical camera move.",
    "Regional residuals are NOT persistent object or character identities.",
    "Motion pairs are sampled, not complete tracking of all decoded frames.",
    "Velocity is estimated between adjacent sampled frame pairs, not a continuous trajectory.",
    "Motion matching is bounded by preview resolution and search radius; failures abstain.",
    "Timing is based on FFmpeg decoder PTS, not independently verified original packet timing.",
]


def _difference(row: dict[str, Any]) -> float:
    change = row.get("changeFromPrevious")
    value = change.get("meanPixelDelta", 0.0) if isinstance(change, dict) else 0.0
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("invalid per-frame pixel-difference evidence")
    return float(value)


def _validate_numeric(numeric: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(numeric, dict):
        raise ValueError("temporal analysis requires numeric evidence")
    rows = numeric.get("frames")
    if (not isinstance(rows, list) or not 1 <= len(rows) <= 108000
            or numeric.get("frameCount") != len(rows)):
        raise ValueError("numeric frame count is invalid")
    source_hash = numeric.get("sourceSha256")
    if (not isinstance(source_hash, str) or len(source_hash) != 64
            or any(c not in "0123456789abcdef" for c in source_hash)):
        raise ValueError("numeric evidence has no valid SHA-256")
    prior_time: float | None = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("frameIndex") != index:
            raise ValueError("numeric frame indices are not sequential")
        seconds = row.get("decodedSeconds")
        if type(seconds) not in (float, int) or not math.isfinite(seconds):
            raise ValueError("invalid decoded time")
        if prior_time is not None and seconds <= prior_time:
            raise ValueError("decoded frame times must be increasing")
        prior_time = float(seconds)
        if type(row.get("cutCandidate")) is not bool:
            raise ValueError("cut candidate missing")
        _difference(row)
        appearance = row.get("appearance")
        if (not isinstance(appearance, dict)
                or type(appearance.get("displayLumaProxy")) not in (int, float)
                or not math.isfinite(appearance["displayLumaProxy"])
                or not 0 <= appearance["displayLumaProxy"] <= 1):
            raise ValueError("invalid display luminance evidence")
    return rows


def _cut_boundaries(rows: list[dict[str, Any]],
                    minimum_shot_frames: int) -> tuple[list[int], list[int]]:
    candidates = [i for i in range(1, len(rows)) if rows[i]["cutCandidate"]]
    clusters: list[list[int]] = []
    for i in candidates:
        if clusters and i - clusters[-1][-1] < minimum_shot_frames:
            clusters[-1].append(i)
        else:
            clusters.append([i])
    preferred = [max(group, key=lambda i: (_difference(rows[i]), -i))
                 for group in clusters]
    boundaries = [0]
    ignored: list[int] = []
    for index in preferred:
        if (index - boundaries[-1] >= minimum_shot_frames
                and len(rows) - index >= minimum_shot_frames):
            boundaries.append(index)
        else:
            ignored.append(index)
    selected = set(boundaries)
    ignored.extend(i for i in candidates if i not in selected and i not in ignored)
    return boundaries, sorted(ignored)


def build_shot_plan(numeric: dict[str, Any], *,
                    minimum_shot_frames: int = 4) -> dict[str, Any]:
    """Partition decoded frames into non-overlapping heuristic shot candidates.

    Each shot suggests stable and changed frames for inexpensive model review.
    A shot represents temporal segmentation, NOT a confirmed semantic scene.
    """
    if (type(minimum_shot_frames) is not int
            or not 1 <= minimum_shot_frames <= 120):
        raise ValueError("minimum_shot_frames must be between 1 and 120")
    rows = _validate_numeric(numeric)
    boundaries, ignored = _cut_boundaries(rows, minimum_shot_frames)
    if len(boundaries) > 4096:
        raise ValueError("shot candidate count exceeds 4096-report budget")
    shots: list[dict[str, Any]] = []
    for j, start in enumerate(boundaries):
        end = boundaries[j + 1] - 1 if j + 1 < len(boundaries) else len(rows) - 1
        # Incoming cut belongs to the previous shot's transition, not its own
        # within-shot dynamics.
        interior = list(range(start + 1, end + 1))
        deltas = [_difference(rows[i]) for i in interior]
        count = len(deltas)
        stable = min(
            range(start, end + 1),
            key=lambda i: (_difference(rows[i]) if i > start else .015,
                           abs(i - (start + end) / 2), i),
        )
        peak = max(interior, key=lambda i: (_difference(rows[i]), -i)) if interior else start
        middle = (start + end) // 2
        representatives = sorted({start, stable, middle, peak, end})
        review = sorted({stable, peak})
        mean_delta = sum(deltas) / count if count else 0.0
        static_fraction = sum(v < .025 for v in deltas) / count if count else 1.0
        high_fraction = sum(v >= .12 for v in deltas) / count if count else 0.0
        luma = sum(float(rows[i]["appearance"]["displayLumaProxy"])
                   for i in range(start, end + 1)) / (end - start + 1)
        shots.append({
            "shotIndex": j,
            "startFrameIndex": start, "endFrameIndex": end,
            "startSeconds": round(float(rows[start]["decodedSeconds"]), 6),
            "endSeconds": round(float(rows[end]["decodedSeconds"]), 6),
            "frameCount": end - start + 1,
            "entryCutCandidateFrameIndex": start if start else None,
            "reviewFrameIndices": review,
            "representativeFrameIndices": representatives,
            "timing": {
                "meanFrameDifference": round(mean_delta, 5),
                "peakFrameDifference": round(max(deltas, default=0.0), 5),
                "peakChangeFrameIndex": peak,
                "lowChangeFraction": round(static_fraction, 5),
                "highChangeFraction": round(high_fraction, 5),
                "meanDisplayLuma": round(luma, 5),
            },
            "classificationStatus": "unverified-shot-candidate",
        })
    return {
        "schemaVersion": VERSION,
        "sourceSha256": numeric["sourceSha256"],
        "frameCount": len(rows),
        "segmentation": {
            "method": "clustered-hard-cut-candidates-v1",
            "minimumShotFrames": minimum_shot_frames,
            "detectedCutCandidates": sum(r["cutCandidate"] for r in rows[1:]),
            "selectedShotBoundaries": boundaries[1:],
            "suppressedCandidateIndices": ignored,
            "status": "heuristic-not-human-verified",
        },
        "shots": shots,
        "motion": {
            "status": "not-measured",
            "samplingMethod": "none",
            "evaluatedPairs": 0,
            "pairs": [],
        },
        "limitations": list(_LIMITS),
    }


def _decode_review_png(path: Path, *, width: int, height: int) -> bytes:
    """Decode ONLY the known three-chunk RGB PNG shape produced by _png_rgb.

    Reject oversized, malformed, unexpected, or compressed-bomb PNGs.
    """
    if (not path.is_file() or path.is_symlink()
            or type(width) is not int or type(height) is not int
            or not 64 <= width <= 320 or not 36 <= height <= 180
            or path.stat().st_size > 1_000_000):
        raise ValueError("unsafe local RGB frame preview")
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("invalid frame PNG signature")
    offset = 8
    chunks: list[tuple[bytes, bytes]] = []
    while offset + 12 <= len(data) and len(chunks) < 4:
        length = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if length > 1_000_000 or end > len(data):
            raise ValueError("oversized or truncated PNG chunk")
        chunk_data = data[offset + 8:offset + 8 + length]
        checksum = int.from_bytes(data[offset + 8 + length:end], "big")
        if zlib.crc32(kind + chunk_data) & 0xffffffff != checksum:
            raise ValueError("frame PNG CRC mismatch")
        chunks.append((kind, chunk_data))
        offset = end
    if offset != len(data) or [kind for kind, _ in chunks] != [
            b"IHDR", b"IDAT", b"IEND"]:
        raise ValueError("unexpected RGB frame PNG format")
    ihdr, compressed, trailer = (chunk for _, chunk in chunks)
    if trailer or len(ihdr) != 13 or struct.unpack(">IIBBBBB", ihdr) != (
            width, height, 8, 2, 0, 0, 0):
        raise ValueError("RGB frame PNG dimensions or pixel format differ")
    row_stride = width * 3
    expected = (row_stride + 1) * height
    decoder = zlib.decompressobj()
    try:
        decoded = decoder.decompress(compressed, expected + 1)
    except zlib.error as exc:
        raise ValueError("invalid compressed RGB frame") from exc
    if (len(decoded) != expected or not decoder.eof
            or decoder.unconsumed_tail or decoder.unused_data):
        raise ValueError("RGB frame decompression is incomplete or oversized")
    result = bytearray(row_stride * height)
    for y in range(height):
        scanline = y * (row_stride + 1)
        if decoded[scanline] != 0:
            raise ValueError("only unfiltered RGB frame PNGs are supported")
        result[y * row_stride:(y + 1) * row_stride] = decoded[
            scanline + 1:scanline + 1 + row_stride]
    return bytes(result)


def _grayscale(rgb: bytes, width: int, height: int, step: int) -> tuple[bytes, int, int]:
    if len(rgb) != width * height * 3:
        raise ValueError("RGB buffer length mismatch")
    sampled_width = (width + step - 1) // step
    sampled_height = (height + step - 1) // step
    values = bytearray(sampled_width * sampled_height)
    for sy, y in enumerate(range(0, height, step)):
        for sx, x in enumerate(range(0, width, step)):
            start = (y * width + x) * 3
            r, g, b = rgb[start:start + 3]
            values[sy * sampled_width + sx] = (3 * r + 6 * g + b) // 10
    return bytes(values), sampled_width, sampled_height


def match_image_plane_motion(
    previous: bytes, current: bytes, *, width: int, height: int,
    reduction: int = 4, search_radius: int = 3,
    min_texture: float = 12.0,
) -> dict[str, Any]:
    """Bounded RGB block matching; no optical-flow or camera claims.

    A small 5x5 grayscale patch in the CURRENT frame is matched against
    PREVIOUS-frame patches in a local search window. Signed dx/dy describe
    observed current-image displacement relative to previous image pixels.
    """
    if (type(width) is not int or type(height) is not int
            or not 64 <= width <= 320 or not 36 <= height <= 180
            or type(reduction) is not int or not 2 <= reduction <= 4
            or type(search_radius) is not int or not 1 <= search_radius <= 4
            or type(min_texture) not in (int, float)
            or not math.isfinite(min_texture) or not 0 <= min_texture <= 64):
        raise ValueError("invalid bounded block-matching parameters")
    before, w, h = _grayscale(previous, width, height, reduction)
    after, _, _ = _grayscale(current, width, height, reduction)
    patch_radius = 2
    margin = patch_radius + search_radius
    if w <= 2 * margin + 1 or h <= 2 * margin + 1:
        raise ValueError("review image too small for bounded motion search")
    # Fixed 4x3 grid: 12 regions, at most 9x9 candidates each, 25 pixels
    # per patch. CPU only, no large NumPy/AI installation required.
    centers = [
        (min(w - 1 - margin, max(margin, round((col + .5) * w / 4))),
         min(h - 1 - margin, max(margin, round((row + .5) * h / 3))),
         col, row)
        for row in range(3) for col in range(4)
    ]
    regions: list[dict[str, Any]] = []
    for cx, cy, col, row in centers:
        block = [after[(cy + yy) * w + cx + xx]
                 for yy in range(-patch_radius, patch_radius + 1)
                 for xx in range(-patch_radius, patch_radius + 1)]
        average = sum(block) / len(block)
        texture = sum(abs(pixel - average) for pixel in block) / len(block)
        if texture < min_texture:
            continue
        best_key: tuple[int, int, int, int] | None = None
        best_shift = (0, 0)
        zero_cost = 0
        for shift_y in range(-search_radius, search_radius + 1):
            for shift_x in range(-search_radius, search_radius + 1):
                loss = 0
                k = 0
                for yy in range(-patch_radius, patch_radius + 1):
                    at = (cy + yy + shift_y) * w + cx + shift_x - patch_radius
                    for xx in range(patch_radius * 2 + 1):
                        loss += abs(block[k] - before[at + xx])
                        k += 1
                if shift_x == 0 and shift_y == 0:
                    zero_cost = loss
                key = (loss, abs(shift_x) + abs(shift_y), shift_y, shift_x)
                if best_key is None or key < best_key:
                    best_key = key
                    # Previous image coordinates = current + shift, so
                    # current-minus-previous motion is the negative shift.
                    best_shift = (-shift_x, -shift_y)
        assert best_key is not None
        matched = best_key[0] / (25 * 255)
        gain = ((zero_cost - best_key[0]) / zero_cost
                if zero_cost else 0.0)
        # Flat-matching or no improvement over staying still is not a
        # sufficient basis for a moving-foreground hypothesis.
        regions.append({
            "gridColumn": col, "gridRow": row,
            "centerX": min(width - 1, cx * reduction),
            "centerY": min(height - 1, cy * reduction),
            "dxPixels": best_shift[0] * reduction,
            "dyPixels": best_shift[1] * reduction,
            "textureProxy": round(texture / 255, 4),
            "matchError": round(matched, 5),
            "improvementOverNoShift": round(gain, 4),
        })
    if not regions:
        return {
            "status": "abstain-insufficient-texture",
            "matchedRegions": 0, "dominantVectorPixels": None,
            "coherenceFraction": None, "relativeMotionRegions": [],
            "searchRadiusPixels": reduction * search_radius,
            "spatialSamplingStepPixels": reduction,
        }
    # Dominant displacement is a robust scene-level image-plane statistic,
    # not a camera track. Matching errors remain available for quality review.
    med_x = statistics.median(r["dxPixels"] for r in regions)
    med_y = statistics.median(r["dyPixels"] for r in regions)
    inliers = [r for r in regions
               if abs(r["dxPixels"] - med_x) <= reduction
               and abs(r["dyPixels"] - med_y) <= reduction]
    coherence = len(inliers) / len(regions)
    relative = [
        {**r, "residualDxPixels": round(r["dxPixels"] - med_x, 2),
         "residualDyPixels": round(r["dyPixels"] - med_y, 2)}
        for r in regions
        if abs(r["dxPixels"] - med_x) > reduction
        or abs(r["dyPixels"] - med_y) > reduction
    ]
    enough = len(regions) >= 4
    status = ("coherent-image-plane-proxy" if enough and coherence >= .65
              else "ambiguous-image-plane-proxy")
    return {
        "status": status,
        "matchedRegions": len(regions),
        "dominantVectorPixels": {
            "dx": round(float(med_x), 2), "dy": round(float(med_y), 2),
        } if enough else None,
        "coherenceFraction": round(coherence, 4) if enough else None,
        "relativeMotionRegions": relative[:12],
        "searchRadiusPixels": reduction * search_radius,
        "spatialSamplingStepPixels": reduction,
    }


def _sample_indices(shots: list[dict[str, Any]], max_pairs: int,
                    stride: int) -> list[int]:
    indices = []
    for shot in shots:
        start, end = shot["startFrameIndex"], shot["endFrameIndex"]
        if end <= start:
            continue
        indices.extend(range(start + 1, end + 1, stride))
        peak = shot["timing"]["peakChangeFrameIndex"]
        if peak > start:
            indices.append(peak)
    ordered = sorted(set(indices))
    if len(ordered) <= max_pairs:
        return ordered
    if max_pairs == 1:
        return [ordered[len(ordered) // 2]]
    return sorted({ordered[round(i * (len(ordered) - 1) / (max_pairs - 1))]
                   for i in range(max_pairs)})


def derive_temporal_report(
    workspace: Path, *, max_motion_pairs: int = 96,
    stride: int = 8, minimum_shot_frames: int = 4,
    search_radius: int = 3, min_texture: float = 12.0,
) -> dict[str, Any]:
    """Add sampled local pixel-motion evidence to a shot-candidate plan."""
    from kumiki_reference_lab.pipeline.agent_frame_review import (
        load_workspace, _frame_path,
    )
    if (type(max_motion_pairs) is not int or not 1 <= max_motion_pairs <= 500
            or type(stride) is not int or not 1 <= stride <= 240):
        raise ValueError("invalid temporal motion sampling budget")
    manifest, numeric, _ = load_workspace(workspace)
    plan = build_shot_plan(numeric, minimum_shot_frames=minimum_shot_frames)
    width, height = manifest["width"], manifest["height"]
    if (type(width) is not int or type(height) is not int
            or not 64 <= width <= 320 or not 36 <= height <= 180):
        raise ValueError("invalid local preview resolution")
    frames = numeric["frames"]
    indices = _sample_indices(plan["shots"], max_motion_pairs, stride)
    motion_pairs: list[dict[str, Any]] = []
    for index in indices:
        previous = _decode_review_png(
            _frame_path(workspace.absolute(), index - 1),
            width=width, height=height)
        current = _decode_review_png(
            _frame_path(workspace.absolute(), index),
            width=width, height=height)
        dt = float(frames[index]["decodedSeconds"]) - float(
            frames[index - 1]["decodedSeconds"])
        if dt <= 0:
            raise ValueError("motion sample has nonpositive presentation interval")
        motion = match_image_plane_motion(
            previous, current, width=width, height=height,
            search_radius=search_radius, min_texture=min_texture,
        )
        vector = motion["dominantVectorPixels"]
        motion_pairs.append({
            "fromFrameIndex": index - 1,
            "toFrameIndex": index,
            "startSeconds": frames[index - 1]["decodedSeconds"],
            "endSeconds": frames[index]["decodedSeconds"],
            "deltaSeconds": round(dt, 6),
            "frameDifferenceProxy": _difference(frames[index]),
            **motion,
            "dominantVelocityPixelsPerSecond": ({
                "vx": round(vector["dx"] / dt, 2),
                "vy": round(vector["dy"] / dt, 2),
            } if vector is not None and motion["status"] ==
                 "coherent-image-plane-proxy" else None),
        })
    plan["motion"] = {
        "status": ("sampled-block-matching-proxies" if indices
                   else "no-pairs-available"),
        "samplingMethod": "uniform-candidate-pairs-and-per-shot-change-peaks",
        "requestedMaxPairs": max_motion_pairs,
        "stride": stride, "evaluatedPairs": len(motion_pairs),
        "pairs": motion_pairs,
    }
    return plan


def write_temporal_report(workspace: Path, *, max_motion_pairs: int = 96,
                          stride: int = 8, minimum_shot_frames: int = 4,
                          search_radius: int = 3) -> Path:
    """Persist only metadata and numeric estimates; previews remain local."""
    from kumiki_reference_lab.pipeline.agent_frame_review import (
        _write_json_atomic, load_workspace,
    )
    manifest, _, reference = load_workspace(workspace)
    report = derive_temporal_report(
        workspace, max_motion_pairs=max_motion_pairs,
        stride=stride, minimum_shot_frames=minimum_shot_frames,
        search_radius=search_radius,
    )
    if report["sourceSha256"] != manifest["sourceSha256"]:
        raise ValueError("temporal source hash mismatch")
    destination = reference.with_suffix(".temporal.json")
    if destination.exists() and destination.is_symlink():
        raise ValueError("unsafe temporal output symlink")
    _write_json_atomic(destination, report)
    return destination
