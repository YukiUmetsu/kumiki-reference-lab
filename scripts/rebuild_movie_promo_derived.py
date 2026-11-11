"""Rebuild every source-hash-bound movie-promotion derivative as one unit.

No network, media, or video decoder is required. Original measured index/detail
files are read-only inputs. This prevents a newly measured film from silently
leaving comparison, timed-event, and image-motion reports out of sync.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from scripts.audit_movie_promo_evidence import audit
from scripts.derive_movie_promo_motion_proxies import build_from_folder as build_motion
from scripts.derive_movie_promo_timed_events import derive_from_folder as build_timed
from scripts.summarize_movie_promo_evidence import build_comparison

DEFAULT_ROOT = Path("research/analysis/movie-promotions")
OUTPUT_NAMES = (
    "comparison.v1.json",
    "timed-events.v1.json",
    "image-motion-proxies.v1.json",
)


def build_reports(root: Path) -> dict[str, dict]:
    """Fail closed on any malformed or unindexed measured source."""
    problems = audit(root)
    if problems:
        raise ValueError("upstream movie-promotion evidence invalid: " + "; ".join(problems))
    source_bytes = (root / "index.json").read_bytes()
    index = json.loads(source_bytes)
    blob_sha = hashlib.sha1(
        b"blob " + str(len(source_bytes)).encode("ascii") + b"\0" + source_bytes
    ).hexdigest()
    reports = {
        "comparison.v1.json": build_comparison(index, blob_sha),
        "timed-events.v1.json": build_timed(root),
        "image-motion-proxies.v1.json": build_motion(root),
    }
    assert set(reports) == set(OUTPUT_NAMES)
    if any(report.get("sourceIndexGitBlobSha") != blob_sha for report in reports.values()):
        raise ValueError("derived reports disagree on source-index identity")
    return reports


def verify_reports(root: Path, reports: dict[str, dict] | None = None) -> None:
    """Reject missing, stale, or extra tracked derived JSON."""
    expected = reports if reports is not None else build_reports(root)
    target = root / "derived"
    existing = {path.name for path in target.glob("*.json")}
    if existing != set(OUTPUT_NAMES):
        raise ValueError(
            f"derived report files differ: missing={sorted(set(OUTPUT_NAMES) - existing)} "
            f"unexpected={sorted(existing - set(OUTPUT_NAMES))}"
        )
    for name in OUTPUT_NAMES:
        path = target / name
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ValueError(f"{name}: missing or unreadable derived JSON") from error
        if committed != expected[name]:
            raise ValueError(f"{name}: derived report does not match measured source evidence")


def write_reports(root: Path, reports: dict[str, dict] | None = None) -> None:
    """Prepare every JSON file before replacing any existing derived report."""
    expected = reports if reports is not None else build_reports(root)
    target = root / "derived"
    target.mkdir(parents=True, exist_ok=True)
    # The temporary staging directory contains JSON only, never source media.
    with tempfile.TemporaryDirectory(prefix=".movie-promo-derivatives-", dir=root) as tmp:
        staged = Path(tmp)
        for name in OUTPUT_NAMES:
            content = json.dumps(expected[name], indent=2, ensure_ascii=False,
                                 allow_nan=False) + "\n"
            (staged / name).write_text(content, encoding="utf-8")
        for name in OUTPUT_NAMES:
            os.replace(staged / name, target / name)
    verify_reports(root, expected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--verify", action="store_true", help="validate all derived reports without writes")
    args = parser.parse_args()
    reports = build_reports(args.root)
    if args.verify:
        verify_reports(args.root, reports)
        print(f"Verified all {len(OUTPUT_NAMES)} source-hashed movie-promotion derivatives.")
    else:
        write_reports(args.root, reports)
        print(f"Regenerated all {len(OUTPUT_NAMES)} source-hashed movie-promotion derivatives.")


if __name__ == "__main__":
    main()
