"""Check tracked movie-promotion summary against its source-hashed detail files.

This audits internal consistency, not the authenticity of unavailable source media.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

_SHA = re.compile(r"[0-9a-f]{64}\Z")


def audit(root: Path) -> list[str]:
    errors = []
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    if index.get("schemaVersion") != "kumiki.movie-promotion-measurements.v1":
        errors.append("index: unexpected schema")
    seen = set()
    for item in index.get("videos", []):
        slug = item.get("id", "")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            errors.append(f"invalid id: {slug!r}")
            continue
        if slug in seen:
            errors.append(f"{slug}: duplicate id")
        seen.add(slug)
        path = root / f"{slug}.json"
        if not path.is_file():
            errors.append(f"{slug}: missing detail file")
            continue
        detail = json.loads(path.read_text(encoding="utf-8"))
        for field, counterpart in (("id", "id"), ("catalogId", "catalogId"),
                                   ("sourceSha256", "originalSourceSha256"),
                                   ("sourceDurationSeconds", "originalDurationSeconds")):
            if item.get(field) != detail.get(counterpart):
                errors.append(f"{slug}: {field} mismatch")
        if detail.get("schemaVersion") != "kumiki.movie-promotion-window-evidence.v1":
            errors.append(f"{slug}: unexpected detail schema")
        if detail.get("rightsStatus") != "review-required":
            errors.append(f"{slug}: missing rights review")
        if not _SHA.fullmatch(str(item.get("sourceSha256", ""))):
            errors.append(f"{slug}: invalid original SHA-256")
        duration = item.get("sourceDurationSeconds")
        if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                or not math.isfinite(duration) or duration <= 0):
            errors.append(f"{slug}: invalid source duration")
            duration = None
        summaries = item.get("windows", [])
        windows = detail.get("windows", [])
        if len(summaries) != len(windows):
            errors.append(f"{slug}: window count mismatch")
        names = set()
        for summary, window in zip(summaries, windows):
            name = summary.get("window")
            if name in names:
                errors.append(f"{slug}: duplicate window {name}")
            names.add(name)
            if name != window.get("window"):
                errors.append(f"{slug}: window order/name mismatch")
            for field in ("windowSourceSha256", "sourceOffsetSeconds"):
                if summary.get(field) != window.get(field):
                    errors.append(f"{slug}/{name}: {field} mismatch")
            if not _SHA.fullmatch(str(summary.get("windowSourceSha256", ""))):
                errors.append(f"{slug}/{name}: invalid clip SHA-256")
            offset = summary.get("sourceOffsetSeconds")
            scan = summary.get("scanSeconds")
            detail_scan = window.get("scanWindowSeconds")
            if (any(isinstance(v, bool) or not isinstance(v, (int, float))
                    or not math.isfinite(v) for v in (offset, scan, detail_scan))
                    or offset < 0 or scan <= 0 or detail_scan <= 0):
                errors.append(f"{slug}/{name}: invalid window bounds")
            else:
                if scan != detail_scan:
                    errors.append(f"{slug}/{name}: scan duration mismatch")
                # Re-encoded clips have approximate original offsets.
                if duration is not None and offset + scan > duration + 0.5:
                    errors.append(f"{slug}/{name}: window exceeds source duration")
            if summary.get("cutCandidateCount") != len(window.get("shotCutCandidates", [])):
                errors.append(f"{slug}/{name}: cut candidate count mismatch")
            if summary.get("appearanceFrameSamples") != len(window.get("appearanceSamples", [])):
                errors.append(f"{slug}/{name}: appearance sample count mismatch")
            if summary.get("cutCandidateCountAtThreshold015") != window.get("sensitivityCutCandidateCount"):
                errors.append(f"{slug}/{name}: sensitivity count mismatch")
    for path in root.glob("*.json"):
        if path.name != "index.json" and path.stem not in seen:
            errors.append(f"{path.name}: unindexed detail file")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("research/analysis/movie-promotions"))
    args = parser.parse_args()
    errors = audit(args.root)
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    print("Movie-promotion index and detailed evidence are internally consistent.")


if __name__ == "__main__":
    main()
