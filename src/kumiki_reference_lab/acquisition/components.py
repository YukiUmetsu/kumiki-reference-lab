"""Reusable artistic components measured from a reference corpus.

What this module does
---------------------
It turns per-record measurements (a full-runtime census record with an optional
editorial block, or a windowed video record, each optionally joined with an
audio record and catalog metadata) into a flat feature row, clusters the rows,
and describes each cluster with a measured profile and a concrete reuse recipe.

What it deliberately does not do
--------------------------------
It never labels a cluster as a genre, a mood, a quality tier or an authorial
intent. Component names are assembled from a fixed vocabulary of timing words
(fast/quick/steady/slow/long, bursty, accelerating/decelerating, strobe) and are
selected by explicit numeric thresholds. A name is a summary of a measured
ordering, not an aesthetic claim.

Purism
------
Everything here is a pure function of the values it is handed: no file I/O, no
network, no media decode, no clock, no randomness. Determinism comes from stable
input order, index-based tie-breaks and a fixed stride for large samples.

Vocabulary that matters
-----------------------
``cut rate``
    Detected scene-change candidates per minute. A candidate is an ffmpeg
    scene-score exceedance, not a verified edit: fast motion, flashes,
    transitions and compression can add candidates, and a soft dissolve can
    hide one.
``shot``
    The interval between consecutive detected candidates. It is a lower bound on
    an edit interval, never a shot list.
``component``
    A measurement cluster: records whose measured timing/texture features are
    close under complete-linkage agglomeration after robust standardization. It
    is a description of where records sit in a measured feature space, not a
    claim that they share a style, market, mood or intent.
"""

from __future__ import annotations

import math
import statistics
from array import array
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "CLUSTER_FEATURES",
    "FEATURE_SPECS",
    "FORBIDDEN_NAME_TERMS",
    "NAME_VOCABULARY",
    "agglomerative",
    "build_component_evidence",
    "choose_k",
    "component_profile",
    "corpus_features",
    "extract_features",
    "feature_coverage",
    "name_component",
    "name_components",
    "reuse_recipe",
    "robust_standardize",
    "silhouette_score",
]

SCHEMA_VERSION = "kumiki.artistic-components.v1"

#: Standardized values are clipped here so a single extreme record cannot
#: dominate a Euclidean distance built from median/IQR scaling.
STANDARDIZE_CLIP = 4.0

#: Features used to form components. These are timing and luminance-instability
#: measurements only: palette and audio are measured per component but do not
#: decide membership. Changing this tuple changes every component.
CLUSTER_FEATURES: tuple[str, ...] = (
    "cutsPerMinute",
    "medianShotSeconds",
    "burstFraction",
    "shotsUnderHalfSecondPct",
    "paceDriftRatio",
    "flickerLumaPerSecond",
)

# ---------------------------------------------------------------------------
# small numeric helpers
# ---------------------------------------------------------------------------


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _first_number(*values: object) -> float | None:
    for value in values:
        number = _finite(value)
        if number is not None:
            return number
    return None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _path(mapping: object, *keys: str) -> object:
    current: object = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _number_at(mapping: object, *keys: str) -> float | None:
    return _finite(_path(mapping, *keys))


def _quantile(sorted_values: Sequence[float], fraction: float) -> float:
    """Linear-interpolated quantile (the common type-7 definition)."""
    if not sorted_values:
        raise ValueError("quantile of an empty sequence")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = fraction * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return float(sorted_values[lower]) * (1.0 - weight) + float(
        sorted_values[upper]) * weight


def _quantiles(values: Iterable[float]) -> dict[str, float] | None:
    clean = sorted(float(value) for value in values)
    if not clean:
        return None
    return {
        "p10": _quantile(clean, 0.10),
        "median": _quantile(clean, 0.50),
        "p90": _quantile(clean, 0.90),
        "min": clean[0],
        "max": clean[-1],
    }


# ---------------------------------------------------------------------------
# feature extraction
# ---------------------------------------------------------------------------

_PACE_CODES = {"accelerating": 1.0, "steady": 0.0, "decelerating": -1.0}
_ONSET_CODES = _PACE_CODES


def _context(record: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Collect the blocks a getter may read, without interpreting them."""
    census_record = _mapping(record.get("censusRecord"))
    video_record = _mapping(record.get("videoRecord"))
    audio_record = _mapping(record.get("audioRecord"))

    census = _mapping(record.get("census")) or _mapping(census_record.get("census"))
    editorial = _mapping(record.get("editorial")) or _mapping(
        census_record.get("editorial"))
    summary = _mapping(record.get("summary")) or _mapping(video_record.get("summary"))
    audio = _mapping(record.get("audio")) or _mapping(audio_record.get("audio"))
    source = _mapping(record.get("source")) or _mapping(
        census_record.get("source")) or _mapping(video_record.get("source"))
    catalog = _mapping(record.get("catalog")) or _mapping(
        video_record.get("catalog")) or _mapping(census_record.get("catalog"))
    coverage = _mapping(record.get("coverage")) or _mapping(
        census_record.get("coverage")) or _mapping(video_record.get("coverage"))
    return {
        "census": census,
        "editorial": editorial,
        "summary": summary,
        "audio": audio,
        "source": source,
        "catalog": catalog,
        "coverage": coverage,
        "record": record,
    }


def _duration(ctx: Mapping[str, Any]) -> float | None:
    source = ctx["source"]
    census = ctx["census"]
    catalog = ctx["catalog"]
    return _first_number(
        source.get("durationSeconds"),
        census.get("durationSeconds"),
        catalog.get("durationSeconds"),
        _path(ctx["record"], "durationSeconds"),
    )


def _cuts_per_minute(ctx: Mapping[str, Any]) -> float | None:
    census = ctx["census"]
    editorial = ctx["editorial"]
    summary = ctx["summary"]
    direct = _first_number(
        census.get("cutsPerMinute"),
        editorial.get("cutsPerMinuteOfRuntime"),
        summary.get("cutCandidateRatePerMinute"),
    )
    if direct is not None:
        return direct
    cut_count = _first_number(census.get("cutCount"), summary.get("cutCandidateCount"))
    duration = _duration(ctx)
    if cut_count is None or not duration:
        return None
    return cut_count / duration * 60.0


def _median_shot(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(
        ctx["editorial"].get("medianShotSeconds"),
        ctx["census"].get("medianCutGapSeconds"),
        ctx["summary"].get("medianCutGapSeconds"),
    )


def _p90_shot(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(ctx["editorial"].get("p90ShotSeconds"))


def _p10_shot(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(
        ctx["editorial"].get("p10ShotSeconds"),
        ctx["census"].get("p10CutGapSeconds"),
    )


def _burst(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(
        ctx["census"].get("burstFraction"),
        ctx["summary"].get("burstFraction"),
    )


def _shots_under_half(ctx: Mapping[str, Any]) -> float | None:
    fraction = _first_number(
        ctx["editorial"].get("shotsUnderHalfSecondFraction"))
    return None if fraction is None else fraction * 100.0


def _pace_drift(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(ctx["editorial"].get("paceDriftRatio"))


def _pace_code(ctx: Mapping[str, Any]) -> float | None:
    trend = ctx["editorial"].get("paceTrend")
    if isinstance(trend, str):
        return _PACE_CODES.get(trend.lower())
    return None


def _first_third_rate(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(ctx["editorial"].get("paceFirstThird"))


def _last_third_rate(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(ctx["editorial"].get("paceLastThird"))


def _flicker(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(ctx["editorial"].get("flickerLumaPerSecond"))


def _static_fraction(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(ctx["editorial"].get("staticFraction"))


def _mean_luma(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(
        _path(ctx["census"], "seriesSummary", "meanDisplayLuma"),
        ctx["summary"].get("meanDisplayLuma"),
    )


def _mean_saturation(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(
        _path(ctx["census"], "seriesSummary", "meanSaturation"),
        ctx["summary"].get("meanSaturation"),
    )


def _integrated_lufs(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(ctx["audio"].get("integratedLufs"))


def _loudness_range(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(ctx["audio"].get("loudnessRangeLu"))


def _true_peak(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(ctx["audio"].get("truePeakDbfs"))


def _silence_fraction(ctx: Mapping[str, Any]) -> float | None:
    return _first_number(ctx["audio"].get("silenceFraction"))


def _onset_rate(ctx: Mapping[str, Any]) -> float | None:
    audio = ctx["audio"]
    direct = _first_number(audio.get("onsetsPerMinuteOfRuntime"))
    if direct is not None:
        return direct
    count = _first_number(audio.get("onsetCount"))
    duration = _first_number(audio.get("durationSeconds"))
    if count is None or not duration:
        return None
    return count / duration * 60.0


def _onset_code(ctx: Mapping[str, Any]) -> float | None:
    trend = ctx["audio"].get("onsetRateTrend")
    if isinstance(trend, str):
        return _ONSET_CODES.get(trend.lower())
    return None


def _tempo(ctx: Mapping[str, Any]) -> float | None:
    confidence = _first_number(ctx["audio"].get("tempoConfidence"))
    bpm = _first_number(ctx["audio"].get("tempoHypothesisBpm"))
    if bpm is None or confidence is None or confidence < 0.2:
        return None
    return bpm


#: Every feature a component can report. ``getter`` reads one normalized
#: context; ``unit`` is the unit of the stored value; ``meaning`` is the
#: component-level reading of that value (never an aesthetic judgement).
FEATURE_SPECS: dict[str, dict[str, Any]] = {
    "cutsPerMinute": {
        "getter": _cuts_per_minute,
        "unit": "cuts/min",
        "meaning": "detected scene-change candidates per minute",
        "cluster": True,
        "direction": "faster with more candidates",
    },
    "medianShotSeconds": {
        "getter": _median_shot,
        "unit": "s",
        "meaning": "median interval between detected scene-change candidates",
        "cluster": True,
        "direction": "longer with fewer candidates",
    },
    "p10ShotSeconds": {
        "getter": _p10_shot,
        "unit": "s",
        "meaning": "10th-percentile interval between detected candidates (short end)",
        "cluster": False,
    },
    "p90ShotSeconds": {
        "getter": _p90_shot,
        "unit": "s",
        "meaning": "90th-percentile interval between detected candidates (long end)",
        "cluster": False,
    },
    "burstFraction": {
        "getter": _burst,
        "unit": "fraction",
        "meaning": "share of candidates that land within a burst window of the previous one",
        "cluster": True,
        "direction": "higher with more clustered candidates",
    },
    "shotsUnderHalfSecondPct": {
        "getter": _shots_under_half,
        "unit": "%",
        "meaning": "share of detected intervals shorter than 0.5 s",
        "cluster": True,
        "direction": "higher with more sub-half-second intervals",
    },
    "paceDriftRatio": {
        "getter": _pace_drift,
        "unit": "ratio",
        "meaning": "last-third cut rate divided by first-third cut rate",
        "cluster": True,
        "direction": "above 1 accelerates, below 1 decelerates",
    },
    "paceTrendCode": {
        "getter": _pace_code,
        "unit": "code",
        "meaning": "editorial paceTrend as -1 decelerating / 0 steady / +1 accelerating",
        "cluster": False,
    },
    "paceFirstThirdCutsPerMinute": {
        "getter": _first_third_rate,
        "unit": "cuts/min",
        "meaning": "candidate rate inside the first third of the runtime",
        "cluster": False,
    },
    "paceLastThirdCutsPerMinute": {
        "getter": _last_third_rate,
        "unit": "cuts/min",
        "meaning": "candidate rate inside the last third of the runtime",
        "cluster": False,
    },
    "flickerLumaPerSecond": {
        "getter": _flicker,
        "unit": "luma/s",
        "meaning": "median absolute second-to-second change in mean display luma",
        "cluster": True,
        "direction": "higher with less stable sample-to-sample luma",
    },
    "staticFraction": {
        "getter": _static_fraction,
        "unit": "fraction",
        "meaning": "share of sampled consecutive pairs with near-zero RGB change",
        "cluster": False,
    },
    "meanLuma": {
        "getter": _mean_luma,
        "unit": "0-1",
        "meaning": "mean display-luma proxy across the appearance sample",
        "cluster": False,
    },
    "meanSaturation": {
        "getter": _mean_saturation,
        "unit": "0-1",
        "meaning": "mean saturation proxy across the appearance sample",
        "cluster": False,
    },
    "durationSeconds": {
        "getter": _duration,
        "unit": "s",
        "meaning": "measured runtime of the rendition, not an editorial duration",
        "cluster": False,
    },
    "integratedLufs": {
        "getter": _integrated_lufs,
        "unit": "LUFS",
        "meaning": "integrated programme loudness of the measured audio stream",
        "cluster": False,
    },
    "loudnessRangeLu": {
        "getter": _loudness_range,
        "unit": "LU",
        "meaning": "loudness range of the measured audio stream",
        "cluster": False,
    },
    "truePeakDbfs": {
        "getter": _true_peak,
        "unit": "dBFS",
        "meaning": "true peak of the measured audio stream",
        "cluster": False,
    },
    "silenceFraction": {
        "getter": _silence_fraction,
        "unit": "fraction",
        "meaning": "share of measured audio windows below the silence gate",
        "cluster": False,
    },
    "onsetPerMinute": {
        "getter": _onset_rate,
        "unit": "onsets/min",
        "meaning": "detected audio onsets per minute of measured runtime",
        "cluster": False,
    },
    "onsetTrendCode": {
        "getter": _onset_code,
        "unit": "code",
        "meaning": "onset-rate trend as -1 decelerating / 0 steady / +1 accelerating",
        "cluster": False,
    },
    "tempoHypothesisBpm": {
        "getter": _tempo,
        "unit": "BPM",
        "meaning": "periodicity hypothesis with at least 0.2 confidence; not a beat grid",
        "cluster": False,
    },
}

_FEATURE_NAMES = tuple(FEATURE_SPECS)


def _identity(record: Mapping[str, Any]) -> tuple[str | None, str | None]:
    block = _mapping(record.get("record"))
    for source in (block, record):
        identifier = source.get("id")
        if identifier is None:
            for key in ("projectId", "clipId", "nid", "postId"):
                identifier = source.get(key)
                if identifier is not None:
                    break
        slug = source.get("slug")
        if identifier is not None or slug is not None:
            return (None if identifier is None else str(identifier),
                    None if slug is None else str(slug))
    return None, None


def _evidence_level(record: Mapping[str, Any]) -> str:
    ctx = _context(record)
    if ctx["census"] and (
            "cutCount" in ctx["census"] or "cutPts" in ctx["census"]):
        return "full-film"
    if ctx["summary"]:
        return "windowed"
    return "none"


def _strobe(record: Mapping[str, Any]) -> bool | None:
    ctx = _context(record)
    for value in (
        ctx["census"].get("strobe"),
        ctx["editorial"].get("strobeFlag"),
        _path(ctx["record"], "strobe"),
    ):
        if isinstance(value, bool):
            return value
    return None


def extract_features(record: Mapping[str, Any], *, site: str) -> dict[str, Any]:
    """Flatten one joined record into feature values plus light metadata.

    ``record`` may be a raw census record, a raw windowed video record, a raw
    audio record, or a joined dict with ``censusRecord`` / ``videoRecord`` /
    ``audioRecord`` / ``catalog`` keys (the shape the derivation script builds).
    Absent features are ``None``; they are never zero-filled here.
    """
    if not isinstance(record, Mapping):
        raise TypeError("record must be a mapping")
    ctx = _context(record)
    identifier, slug = _identity(record)
    row: dict[str, Any] = {
        "site": site,
        "id": identifier,
        "slug": slug,
        "evidenceLevel": _evidence_level(record),
        "strobe": _strobe(record),
    }
    features: dict[str, float | None] = {}
    for name, spec in FEATURE_SPECS.items():
        value = spec["getter"](ctx)
        features[name] = None if value is None else float(value)
    row.update(features)
    row["features"] = features
    return row


def corpus_features(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Extract features from an iterable of records, preserving input order.

    Each item is either a raw record carrying a ``site`` field, or a wrapper
    ``{"site": ..., "record": {...}}``. Order is the caller's order so that
    downstream cluster ids and tie-breaks stay stable.
    """
    rows: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, Mapping):
            raise TypeError("each record must be a mapping")
        if "census" in item or "summary" in item or "audio" in item:
            site = item.get("site") or "unknown"
            payload = item
        elif isinstance(item.get("record"), Mapping) and "site" in item:
            site = item.get("site") or "unknown"
            payload = _mapping(item.get("record"))
        else:
            site = item.get("site") or "unknown"
            payload = item
        rows.append(extract_features(payload, site=str(site)))
    return rows


def feature_value(row: Mapping[str, Any], name: str) -> float | None:
    """Read one feature from a row produced by :func:`extract_features`."""
    nested = row.get("features")
    if isinstance(nested, Mapping) and name in nested:
        return _finite(nested.get(name))
    return _finite(row.get(name))


def feature_coverage(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Count non-null values per feature across ``rows``."""
    row_list = list(rows)
    total = len(row_list)
    coverage: dict[str, dict[str, Any]] = {}
    for name, spec in FEATURE_SPECS.items():
        present = sum(1 for row in row_list if feature_value(row, name) is not None)
        coverage[name] = {
            "present": present,
            "total": total,
            "fraction": (present / total) if total else 0.0,
            "unit": spec["unit"],
            "meaning": spec["meaning"],
        }
    return coverage


# ---------------------------------------------------------------------------
# robust standardization
# ---------------------------------------------------------------------------


def robust_standardize(values: Sequence[object]) -> tuple[list[float], dict[str, Any]]:
    """Median/IQR standardization with a documented zero-IQR fallback.

    The scale is the interquartile range. When the IQR is 0 (more than a quarter
    of the corpus shares one value) the fallback is ``1.4826 * MAD`` around the
    median; when that is also 0 every value is identical and the scale is 1.0,
    which maps all values to 0.0. Missing values (``None``/NaN) become 0.0,
    i.e. the corpus median, and are counted. Standardized values are clipped to
    ±:data:`STANDARDIZE_CLIP` so one extreme record cannot dominate a distance.
    """
    cleaned: list[float | None] = []
    for value in values:
        cleaned.append(_finite(value))
    present = [value for value in cleaned if value is not None]
    if not present:
        return [0.0] * len(cleaned), {
            "median": None,
            "iqr": None,
            "scale": None,
            "fallback": "no-values",
            "n": 0,
            "missing": len(cleaned),
            "clipped": 0,
        }
    ordered = sorted(present)
    median = _quantile(ordered, 0.50)
    q25 = _quantile(ordered, 0.25)
    q75 = _quantile(ordered, 0.75)
    iqr = q75 - q25
    fallback: str | None = None
    scale = iqr
    if iqr <= 0.0:
        deviations = sorted(abs(value - median) for value in present)
        mad = _quantile(deviations, 0.50)
        if mad > 0.0:
            scale = 1.4826 * mad
            fallback = "mad"
        else:
            scale = 1.0
            fallback = "unit"
    standardized: list[float] = []
    clipped = 0
    for value in cleaned:
        if value is None:
            standardized.append(0.0)
            continue
        z = (value - median) / scale
        if z > STANDARDIZE_CLIP:
            z = STANDARDIZE_CLIP
            clipped += 1
        elif z < -STANDARDIZE_CLIP:
            z = -STANDARDIZE_CLIP
            clipped += 1
        standardized.append(z)
    return standardized, {
        "median": median,
        "iqr": iqr,
        "scale": scale,
        "fallback": fallback,
        "n": len(present),
        "missing": len(cleaned) - len(present),
        "clipped": clipped,
    }


# ---------------------------------------------------------------------------
# clustering
# ---------------------------------------------------------------------------


def _rows_of(features: Sequence[Mapping[str, Any] | Sequence[float]],
             feature_names: Sequence[str]) -> list[list[float | None]]:
    rows: list[list[float | None]] = []
    for row in features:
        if isinstance(row, Mapping):
            rows.append([feature_value(row, name) for name in feature_names])
        else:
            values = list(row)
            if len(values) != len(feature_names):
                raise ValueError(
                    "vector row length does not match feature_names")
            rows.append([_finite(value) for value in values])
    return rows


def _design_matrix(
    features: Sequence[Mapping[str, Any] | Sequence[float]],
    feature_names: Sequence[str],
) -> tuple[list[list[float]], dict[str, Any], list[list[bool]]]:
    raw = _rows_of(features, feature_names)
    n = len(raw)
    columns = [[raw[i][j] for i in range(n)] for j in range(len(feature_names))]
    vectors = [[0.0] * len(feature_names) for _ in range(n)]
    stats: dict[str, Any] = {}
    present: list[list[bool]] = [[True] * len(feature_names) for _ in range(n)]
    for j, name in enumerate(feature_names):
        standardized, info = robust_standardize(columns[j])
        stats[name] = info
        for i in range(n):
            vectors[i][j] = standardized[i]
            present[i][j] = _finite(raw[i][j]) is not None
    return vectors, stats, present


def _distance_matrix(vectors: Sequence[Sequence[float]]) -> list[array]:
    n = len(vectors)
    matrix = [array("d", [0.0]) * n for _ in range(n)]
    for i in range(n):
        vi = vectors[i]
        row_i = matrix[i]
        for j in range(i + 1, n):
            vj = vectors[j]
            total = 0.0
            for left, right in zip(vi, vj):
                delta = left - right
                total += delta * delta
            distance = math.sqrt(total)
            row_i[j] = distance
            matrix[j][i] = distance
    return matrix


def _combine(linkage: str, distance_a: float, distance_b: float,
             size_a: int, size_b: int) -> float:
    if linkage == "complete":
        return distance_a if distance_a >= distance_b else distance_b
    if linkage == "single":
        return distance_a if distance_a <= distance_b else distance_b
    total = size_a + size_b
    return (size_a * distance_a + size_b * distance_b) / total


def _agglomerate(
    vectors: Sequence[Sequence[float]],
    *,
    linkage: str,
    stop_k: int,
    snapshots: Sequence[int] = (),
) -> tuple[list[dict[str, Any]], dict[int, list[int]]]:
    """Run agglomeration down to ``stop_k`` clusters.

    Returns ``(merges, partitions)`` where ``partitions[k]`` is the list of
    original indices per cluster, ordered by smallest member, for every k in
    ``snapshots`` (and for ``stop_k``).
    """
    if linkage not in ("complete", "average", "single"):
        raise ValueError("linkage must be complete, average or single")
    n = len(vectors)
    wanted = sorted({k for k in snapshots if 1 <= k <= n} | {stop_k})
    if n == 0:
        return [], {k: [] for k in wanted}
    matrix = _distance_matrix(vectors)
    import heapq

    capacity = 2 * n + 1
    nearest = [-1] * capacity
    nearest_distance = [math.inf] * capacity
    size = [1] * capacity
    members: dict[int, list[int]] = {i: [i] for i in range(n)}
    alive: set[int] = set(range(n))

    def scan(origin: int) -> tuple[int, float]:
        best_id = -1
        best_distance = math.inf
        row = matrix[origin]
        for other in alive:
            if other == origin:
                continue
            distance = row[other]
            if distance < best_distance or (
                    distance == best_distance and other < best_id):
                best_id = other
                best_distance = distance
        return best_id, best_distance

    heap: list[tuple[float, int, int]] = []
    for node in range(n):
        target, distance = scan(node)
        nearest[node] = target
        nearest_distance[node] = distance
        if target >= 0:
            heapq.heappush(heap, (distance, node, target))

    merges: list[dict[str, Any]] = []
    partitions: dict[int, list[int]] = {}
    next_id = n

    def snapshot(k: int) -> None:
        clusters = sorted((sorted(part) for part in members.values()),
                          key=lambda part: part[0])
        partitions[k] = clusters

    if n in wanted:
        snapshot(n)

    while len(alive) > stop_k and len(alive) > 1:
        left = right = -1
        while heap:
            distance, candidate, target = heapq.heappop(heap)
            if candidate not in alive or target not in alive:
                continue
            if nearest[candidate] != target:
                continue
            if nearest_distance[candidate] != distance:
                continue
            left, right = candidate, target
            break
        if left < 0:
            # Defensive: rebuild every nearest entry and retry.
            for node in list(alive):
                target, distance = scan(node)
                nearest[node] = target
                nearest_distance[node] = distance
                if target >= 0:
                    heapq.heappush(heap, (distance, node, target))
            continue
        if right < left:
            left, right = right, left
        size_left = size[left]
        size_right = size[right]

        new_id = next_id
        next_id += 1
        size[new_id] = size_left + size_right
        members[new_id] = sorted(members.pop(left) + members.pop(right))
        alive.discard(left)
        alive.discard(right)
        alive.add(new_id)

        row_extras: dict[int, float] = {}
        for other in alive:
            if other == new_id:
                continue
            distance = _combine(
                linkage,
                matrix[left][other],
                matrix[right][other],
                size_left,
                size_right,
            )
            row_extras[other] = distance
        new_row = array("d", [0.0]) * (new_id + 1)
        for other, distance in row_extras.items():
            new_row[other] = distance
        matrix.append(new_row)
        for other, distance in row_extras.items():
            other_row = matrix[other]
            while len(other_row) <= new_id:
                other_row.append(0.0)
            other_row[new_id] = distance

        for other in alive:
            if other == new_id:
                continue
            if nearest[other] in (left, right):
                target, distance = scan(other)
                nearest[other] = target
                nearest_distance[other] = distance
                if target >= 0:
                    heapq.heappush(heap, (distance, other, target))
            else:
                distance = matrix[new_id][other]
                if distance < nearest_distance[other]:
                    nearest[other] = new_id
                    nearest_distance[other] = distance
                    heapq.heappush(heap, (distance, other, new_id))
        target, distance = scan(new_id)
        nearest[new_id] = target
        nearest_distance[new_id] = distance
        if target >= 0:
            heapq.heappush(heap, (distance, new_id, target))

        merges.append({
            "left": left,
            "right": right,
            "cluster": new_id,
            "distance": matrix[left][right],
            "size": size[new_id],
        })
        if len(alive) in wanted:
            snapshot(len(alive))

    for k in wanted:
        partitions.setdefault(k, sorted(
            (sorted(part) for part in members.values()), key=lambda part: part[0]))
    return merges, partitions


def agglomerative(
    features: Sequence[Mapping[str, Any] | Sequence[float]],
    *,
    linkage: str = "complete",
    max_k: int = 8,
    k: int | None = None,
    feature_names: Sequence[str] | None = None,
) -> list[list[int]]:
    """Cluster rows, returning ``k`` clusters as sorted lists of row indices.

    Deterministic: input order is preserved, ties break on the smaller index,
    and every cluster is ordered by its smallest member. ``k`` defaults to
    ``max_k``; when ``k`` is not below the row count every row is a singleton.
    """
    names = tuple(feature_names or CLUSTER_FEATURES)
    vectors, _stats, _present = _design_matrix(features, names)
    target = max(1, int(max_k if k is None else k))
    if target >= len(vectors):
        return [[index] for index in range(len(vectors))]
    _merges, partitions = _agglomerate(
        vectors, linkage=linkage, stop_k=target, snapshots=(target,))
    return partitions[target]


def _silhouette_from_matrix(matrix: Sequence[Sequence[float]],
                            labels: Sequence[int],
                            indices: Sequence[int]) -> float:
    sample = list(indices)
    if not sample:
        return 0.0
    cluster_members: dict[int, list[int]] = {}
    for index in sample:
        cluster_members.setdefault(int(labels[index]), []).append(index)
    scores: list[float] = []
    for index in sample:
        own = int(labels[index])
        own_members = cluster_members.get(own, [])
        if len(own_members) <= 1:
            scores.append(0.0)
            continue
        row = matrix[index]
        own_total = sum(row[other] for other in own_members if other != index)
        a = own_total / (len(own_members) - 1)
        best_b = math.inf
        for other_cluster, other_members in cluster_members.items():
            if other_cluster == own or not other_members:
                continue
            mean = sum(row[other] for other in other_members) / len(other_members)
            if mean < best_b:
                best_b = mean
        if best_b is math.inf:
            scores.append(0.0)
            continue
        denominator = a if a > best_b else best_b
        scores.append(0.0 if denominator <= 0 else (best_b - a) / denominator)
    return sum(scores) / len(scores)


def _sample_indices(n: int, cap: int = 2000) -> list[int]:
    if n <= cap:
        return list(range(n))
    step = int(math.ceil(n / cap))
    return list(range(0, n, step))


def _silhouette_from_vectors(vectors: Sequence[Sequence[float]],
                             labels: Sequence[int]) -> float:
    if not vectors:
        return 0.0
    matrix = _distance_matrix(vectors)
    return _silhouette_from_matrix(
        matrix, labels, _sample_indices(len(vectors)))


def silhouette_score(
    features: Sequence[Mapping[str, Any] | Sequence[float]],
    labels: Sequence[int],
    *,
    feature_names: Sequence[str] | None = None,
) -> float:
    """Mean silhouette of ``labels`` in robust-standardized feature space.

    Points are compared with Euclidean distance. For n > 2000 a deterministic
    fixed-stride sample of at most 2000 points is scored, and cluster means are
    taken over that sample; this keeps runtime bounded without randomness.
    Singleton clusters score 0 by convention.
    """
    if len(features) != len(labels):
        raise ValueError("features and labels must have the same length")
    names = tuple(feature_names or CLUSTER_FEATURES)
    vectors, _stats, _present = _design_matrix(features, names)
    return _silhouette_from_vectors(vectors, labels)


def choose_k(
    features: Sequence[Mapping[str, Any] | Sequence[float]],
    *,
    candidates: Iterable[int] = range(3, 9),
    linkage: str = "complete",
    feature_names: Sequence[str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Pick the candidate k with the best silhouette, ties to the smaller k.

    Returns ``(k, info)``. ``info`` carries the silhouette per candidate, the
    labels for the winning k, per-point silhouettes and the standardization
    statistics, so callers need not cluster twice.
    """
    names = tuple(feature_names or CLUSTER_FEATURES)
    vectors, stats, present = _design_matrix(features, names)
    n = len(vectors)
    valid = sorted({int(k) for k in candidates if 2 <= int(k) < n})
    info: dict[str, Any] = {
        "n": n,
        "linkage": linkage,
        "featureNames": list(names),
        "standardization": stats,
        "candidateSilhouette": {},
        "coverage": {
            name: {
                "present": sum(1 for row in present if row[j]),
                "total": n,
            }
            for j, name in enumerate(names)
        },
    }
    if not valid:
        info.update({"labels": [0] * n, "silhouette": None,
                     "pointSilhouettes": [0.0] * n})
        return 1, info
    matrix = _distance_matrix(vectors)
    stop_k = valid[0]
    _merges, partitions = _agglomerate(
        vectors, linkage=linkage, stop_k=stop_k, snapshots=valid)
    sample = _sample_indices(n)
    best_k = valid[0]
    best_score = -2.0
    for candidate in valid:
        clusters = partitions[candidate]
        labels = [0] * n
        for cluster_index, cluster in enumerate(clusters):
            for row_index in cluster:
                labels[row_index] = cluster_index
        score = _silhouette_from_matrix(matrix, labels, sample)
        info["candidateSilhouette"][candidate] = score
        if score > best_score or (score == best_score and candidate < best_k):
            best_k = candidate
            best_score = score
    clusters = partitions[best_k]
    labels = [0] * n
    for cluster_index, cluster in enumerate(clusters):
        for row_index in cluster:
            labels[row_index] = cluster_index
    point_scores = _point_silhouettes(matrix, labels)
    info.update({
        "labels": labels,
        "clusters": clusters,
        "silhouette": best_score,
        "pointSilhouettes": point_scores,
    })
    return best_k, info


def _point_silhouettes(matrix: Sequence[Sequence[float]],
                       labels: Sequence[int]) -> list[float]:
    n = len(labels)
    members: dict[int, list[int]] = {}
    for index, label in enumerate(labels):
        members.setdefault(int(label), []).append(index)
    scores: list[float] = []
    for index in range(n):
        own = int(labels[index])
        own_members = members.get(own, [])
        if len(own_members) <= 1:
            scores.append(0.0)
            continue
        row = matrix[index]
        a = sum(row[other] for other in own_members if other != index) / (
            len(own_members) - 1)
        best_b = math.inf
        for other_cluster, other_members in members.items():
            if other_cluster == own or not other_members:
                continue
            mean = sum(row[other] for other in other_members) / len(other_members)
            if mean < best_b:
                best_b = mean
        denominator = a if a > best_b else best_b
        scores.append(0.0 if denominator <= 0 else (best_b - a) / denominator)
    return scores


# ---------------------------------------------------------------------------
# naming
# ---------------------------------------------------------------------------

#: Words a component name may contain. Nothing here describes a mood, a genre,
#: a quality tier or an intention.
NAME_VOCABULARY: tuple[str, ...] = (
    "rapid-cut",
    "fast-cut",
    "quick-cut",
    "steady-cut",
    "slow-burn",
    "long-take",
    "bursty",
    "accelerating",
    "decelerating",
    "steady",
    "strobe-textured",
    "variant",
)

#: A name containing any of these would assert something not measured.
FORBIDDEN_NAME_TERMS: tuple[str, ...] = (
    "mood", "beautiful", "energetic", "premium", "style", "genre",
    "award-winning", "emotional", "luxury", "cinematic", "viral",
)

#: Base cut-rate bands, fastest first. Values are cuts per minute.
CUT_RATE_BANDS: tuple[tuple[float, str], ...] = (
    (44.0, "rapid-cut"),
    (32.0, "fast-cut"),
    (22.0, "quick-cut"),
    (10.0, "steady-cut"),
    (3.5, "slow-burn"),
    (float("-inf"), "long-take"),
)
#: A median detected interval at or above this is named a long take even if the
#: per-minute rate is inflated by a dense burst elsewhere.
LONG_TAKE_SECONDS = 12.0
#: A median interval at or above this with a slow rate is named slow-burn.
SLOW_BURN_SECONDS = 5.0
#: Above this burst fraction a component is named bursty.
BURSTY_FRACTION = 0.25
#: Pace drift at or above this is accelerating.
ACCELERATING_DRIFT = 1.5
#: Pace drift at or below this is decelerating.
DECELERATING_DRIFT = 0.6
#: Pace drift inside this band with a slow name gets the steady prefix.
STEADY_DRIFT_LOW = 0.75
STEADY_DRIFT_HIGH = 1.35


def _base_name(cut_rate: float | None, median_shot: float | None) -> str:
    if median_shot is not None and median_shot >= LONG_TAKE_SECONDS:
        return "long-take"
    if (median_shot is not None and median_shot >= SLOW_BURN_SECONDS
            and (cut_rate is None or cut_rate < 24.0)):
        return "slow-burn"
    if cut_rate is None:
        # With no rate, invert the median interval into an approximate rate.
        if median_shot is None or median_shot <= 0:
            return "steady-cut"
        cut_rate = 60.0 / median_shot
    for threshold, name in CUT_RATE_BANDS:
        if cut_rate >= threshold:
            return name
    return "long-take"


def _allowed_name_tokens() -> frozenset[str]:
    tokens: set[str] = {"variant"}
    for term in NAME_VOCABULARY:
        tokens.update(part for part in term.split("-") if part)
    return frozenset(tokens)


_ALLOWED_NAME_TOKENS = _allowed_name_tokens()


def _check_name(name: str) -> str:
    lowered = name.lower()
    for term in FORBIDDEN_NAME_TERMS:
        if term in lowered:
            raise AssertionError(f"component name asserts {term!r}: {name!r}")
    for token in (part for part in name.split("-") if part):
        if token.isdigit():
            continue
        if token not in _ALLOWED_NAME_TOKENS:
            raise AssertionError(f"token {token!r} is not in NAME_VOCABULARY")
    return name


def name_component(profile: Mapping[str, Any]) -> str:
    """Name a component from measured thresholds only.

    The base word comes from the median cut rate, with the median detected
    interval able to override it for long/slow records. One modifier is added,
    in priority order: ``bursty`` (burst fraction), ``accelerating`` /
    ``decelerating`` (pace drift), or ``steady`` for slow/long records with a
    near-flat pace. No term describes mood, genre, quality or intent.
    """
    features = _mapping(profile.get("features"))
    cut_rate = _number_at(features, "cutsPerMinute", "median")
    median_shot = _number_at(features, "medianShotSeconds", "median")
    burst = _number_at(features, "burstFraction", "median")
    drift = _number_at(features, "paceDriftRatio", "median")
    base = _base_name(cut_rate, median_shot)
    prefix: str | None = None
    if burst is not None and burst >= BURSTY_FRACTION:
        prefix = "bursty"
    elif drift is not None and drift >= ACCELERATING_DRIFT:
        prefix = "accelerating"
    elif drift is not None and drift <= DECELERATING_DRIFT:
        prefix = "decelerating"
    elif (drift is not None and STEADY_DRIFT_LOW <= drift <= STEADY_DRIFT_HIGH
          and base in ("slow-burn", "long-take")):
        prefix = "steady"
    name = base if prefix is None else f"{prefix}-{base}"
    return _check_name(name)


def _unique_names(names: Sequence[str]) -> list[str]:
    """Disambiguate collisions deterministically, keeping the fixed vocabulary."""
    seen: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        count = seen.get(name, 0) + 1
        seen[name] = count
        if count == 1:
            result.append(_check_name(name))
        else:
            result.append(_check_name(f"{name}-variant-{count}"))
    return result


def name_components(profiles: Sequence[Mapping[str, Any]]) -> list[str]:
    """Name profiles in order, appending ``-variant-N`` on a collision."""
    return _unique_names([name_component(profile) for profile in profiles])


# ---------------------------------------------------------------------------
# profiles and recipes
# ---------------------------------------------------------------------------


def _row_for(entry: int | Mapping[str, Any],
             features: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    if isinstance(entry, Mapping):
        return entry
    return features[entry]


def component_profile(
    rows: Sequence[int | Mapping[str, Any]],
    features: Sequence[Mapping[str, Any]],
    *,
    corpus_size: int | None = None,
) -> dict[str, Any]:
    """Describe a component: size, share, per-feature quantiles and coverage.

    ``rows`` may be indices into ``features`` or feature-row mappings. Features
    are reported with their p10/median/p90 and the number of rows that actually
    carry a value; nothing is dropped from the other features' math.
    """
    selected = [_row_for(entry, features) for entry in rows]
    total = corpus_size if corpus_size is not None else len(features)
    sites: dict[str, int] = {}
    levels: dict[str, int] = {}
    for row in selected:
        site = str(row.get("site") or "unknown")
        sites[site] = sites.get(site, 0) + 1
        level = str(row.get("evidenceLevel") or "unknown")
        levels[level] = levels.get(level, 0) + 1
    per_feature: dict[str, Any] = {}
    for name, spec in FEATURE_SPECS.items():
        values = [value for row in selected
                  if (value := feature_value(row, name)) is not None]
        quantiles = _quantiles(values)
        per_feature[name] = {
            "unit": spec["unit"],
            "meaning": spec["meaning"],
            "coverage": len(values),
            "missing": len(selected) - len(values),
            "p10": None if quantiles is None else quantiles["p10"],
            "median": None if quantiles is None else quantiles["median"],
            "p90": None if quantiles is None else quantiles["p90"],
        }
    return {
        "n": len(selected),
        "share": (len(selected) / total) if total else 0.0,
        "sites": dict(sorted(sites.items())),
        "evidenceLevels": dict(sorted(levels.items())),
        "features": per_feature,
    }


def _median_of(profile: Mapping[str, Any], name: str) -> float | None:
    return _number_at(_mapping(profile.get("features")), name, "median")


def _band(profile: Mapping[str, Any], name: str) -> dict[str, Any]:
    feature = _mapping(_mapping(profile.get("features")).get(name))
    return {
        "p10": _finite(feature.get("p10")),
        "median": _finite(feature.get("median")),
        "p90": _finite(feature.get("p90")),
        "unit": feature.get("unit") or FEATURE_SPECS[name]["unit"],
        "derivedFrom": int(feature.get("coverage") or 0),
    }


def reuse_recipe(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Turn a component profile into concrete production numbers.

    Cuts for a target duration are ``round(median cut rate × seconds / 60)``.
    The shot bands, loudness band, onset band and palette band are the p10/p90
    of the measured component. These are corpus mid-points, not prescriptions:
    they describe what this cluster's records measured, not what a new piece
    should do.
    """
    rate = _median_of(profile, "cutsPerMinute")
    shots = {
        "medianSeconds": _median_of(profile, "medianShotSeconds"),
        "p10Seconds": _number_at(
            _mapping(profile.get("features")), "medianShotSeconds", "p10"),
        "p90Seconds": _number_at(
            _mapping(profile.get("features")), "medianShotSeconds", "p90"),
        "unit": "s",
    }
    targets: dict[str, Any] = {}
    for seconds in (15, 30, 60, 90):
        target = None if rate is None else int(round(rate * seconds / 60.0))
        targets[f"{seconds}s"] = {
            "seconds": seconds,
            "cuts": target,
            "medianShotSeconds": (None if target in (None, 0)
                                  else seconds / target),
        }
    drift = _median_of(profile, "paceDriftRatio")
    if drift is None:
        trend = "not-measured"
    elif drift >= ACCELERATING_DRIFT:
        trend = "accelerating"
    elif drift <= DECELERATING_DRIFT:
        trend = "decelerating"
    else:
        trend = "near-flat"
    pace = {
        "trend": trend,
        "driftRatio": drift,
        "firstThirdCutsPerMinute": _median_of(
            profile, "paceFirstThirdCutsPerMinute"),
        "lastThirdCutsPerMinute": _median_of(
            profile, "paceLastThirdCutsPerMinute"),
        "firstThirdCoverage": int(_mapping(
            _mapping(profile.get("features")).get("paceFirstThirdCutsPerMinute")
        ).get("coverage") or 0),
        "lastThirdCoverage": int(_mapping(
            _mapping(profile.get("features")).get("paceLastThirdCutsPerMinute")
        ).get("coverage") or 0),
        "driftRatioBand": _band(profile, "paceDriftRatio"),
    }
    loudness = {
        "integratedLufs": _band(profile, "integratedLufs"),
        "loudnessRangeLu": _band(profile, "loudnessRangeLu"),
        "truePeakDbfs": _band(profile, "truePeakDbfs"),
        "silenceFraction": _band(profile, "silenceFraction"),
    }
    onset = {
        "onsetsPerMinute": _band(profile, "onsetPerMinute"),
        "trendCode": _band(profile, "onsetTrendCode"),
        "tempoHypothesisBpm": _band(profile, "tempoHypothesisBpm"),
    }
    palette = {
        "meanLuma": _band(profile, "meanLuma"),
        "meanSaturation": _band(profile, "meanSaturation"),
    }
    return {
        "targetCuts": targets,
        "cutRatePerMinute": None if rate is None else {
            "median": rate,
            "p10": _number_at(
                _mapping(profile.get("features")), "cutsPerMinute", "p10"),
            "p90": _number_at(
                _mapping(profile.get("features")), "cutsPerMinute", "p90"),
        },
        "shotSeconds": shots,
        "pace": pace,
        "loudness": loudness,
        "onset": onset,
        "palette": palette,
        "burstFraction": _band(profile, "burstFraction"),
        "flickerLumaPerSecond": _band(profile, "flickerLumaPerSecond"),
        "derivedFrom": int(profile.get("n") or 0),
        "formula": "cuts = round(median cutsPerMinute * seconds / 60)",
        "note": (
            "Measured mid-points of this component, not prescriptions; a "
            "different target duration does not change the measured rate. A "
            "0-cut target at a short duration is the arithmetic result of a "
            "very low measured rate; use the shot-duration band there."
        ),
    }


# ---------------------------------------------------------------------------
# evidence envelope
# ---------------------------------------------------------------------------


def build_component_evidence(
    components: Sequence[Mapping[str, Any]],
    *,
    corpus_size: int,
    generated_from: Mapping[str, Any],
    coverage: Mapping[str, Any],
    method: Mapping[str, Any] | None = None,
    limits: Sequence[str] | None = None,
    stills_only: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the committed schema block for the component library."""
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedFrom": dict(generated_from),
        "corpusSize": int(corpus_size),
        "method": dict(method or {}),
        "featureCoverage": dict(coverage),
        "components": list(components),
        "stillsOnly": dict(stills_only) if stills_only else None,
        "limits": list(limits or []),
    }
