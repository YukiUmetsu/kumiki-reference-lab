"""Report the observed technique distribution, not metadata-imputed video styles."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from kumiki_reference_lab.catalog.whatships_data_dashboard import build_whatships_browser


def summarize_tracked_whatships_observations(
    snapshot: Path, repository_root: Path,
) -> dict[str, Any]:
    data = build_whatships_browser(snapshot, repository_root=repository_root)
    tracked = [x for x in data["entries"]
               if x["repositoryAnalysisStatus"] == "tracked-partial-evidence"]
    observed = [x for x in tracked if x["spotCheckCoverage"] == "selected-moments-only"]
    numeric = [x for x in tracked if x["numericStatus"] == "sampled-numeric-unreviewed"]
    style_counts = Counter(tag for row in observed
                           for tag in set(row["visualObservationTags"]))
    category_counts = Counter(row["category"] for row in tracked)
    measured_frames = sum(sum(window["sampledFrames"] for window in row["numeric"]["windows"])
                          for row in numeric)
    measured_windows = sum(row["numeric"]["windowsMeasured"] for row in numeric)
    return {
        "schemaVersion":"kumiki.whatships-research-coverage-report.v1",
        "catalogSnapshotOn":data["retrievedOn"],
        "catalogVideoCount":data["totalVideos"],
        "trackedEvidenceRecordCount":len(tracked),
        "partiallyObservedVideoCount":len(observed),
        "sourcePtsNumericVideoCount":len(numeric),
        "sourcePtsMeasuredWindowCount":measured_windows,
        "sourcePtsSampledFrameCount":measured_frames,
        "fullyHumanReviewedVideoCount":0,
        "trackedRecordsByCategory":dict(sorted(category_counts.items())),
        "observedVisualTags":dict(sorted(style_counts.items(),
                                          key=lambda p:(-p[1],p[0]))),
        "methodLimits":[
            "Visual tags count only explicitly observed, selected-moment browser spot checks.",
            "Missing styles among unobserved catalog videos are unknown, not negative observations.",
            "The observed cohort is not random; style-frequency figures are not population estimates.",
            "Original-PTS sampled RGB and cut data do not prove camera work, physical lighting or film quality.",
            "A completed character model or numeric probe does not constitute full human review.",
        ],
    }
