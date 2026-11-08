"""Exact, user-anchored, monotonic PTS pairing shared by comparison analyzers."""

from __future__ import annotations

from fractions import Fraction


def align_source_times(
    reference_times: list[Fraction], candidate_times: list[Fraction], *,
    reference_anchor_ms: int, candidate_anchor_ms: int,
    tolerance_ms: int = 150, time_scale: str = "1",
) -> tuple[dict[str, Fraction], tuple[tuple[int, int, Fraction], ...]]:
    """Maximize matched pairs then minimize alignment error, without reuse."""
    if any(type(v) is not int or not -3_600_000 <= v <= 3_600_000
           for v in (reference_anchor_ms, candidate_anchor_ms)):
        raise ValueError("comparison anchors must be integer milliseconds within one hour")
    if type(tolerance_ms) is not int or not 0 <= tolerance_ms <= 5000:
        raise ValueError("comparison tolerance must be 0..5000 milliseconds")
    if not isinstance(time_scale, str) or len(time_scale) > 32:
        raise ValueError("invalid time scale")
    try:
        scale = Fraction(time_scale)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("time scale must be a decimal or positive rational") from exc
    if not Fraction(1, 4) <= scale <= 4 or scale.denominator > 1_000_000:
        raise ValueError("time scale must be between 1/4 and 4 with bounded precision")
    if any(b <= a for times in (reference_times, candidate_times)
           for a, b in zip(times, times[1:])):
        raise ValueError("comparison PTS must be strictly increasing")

    ref_anchor = Fraction(reference_anchor_ms, 1000)
    candidate_anchor = Fraction(candidate_anchor_ms, 1000)
    tolerance = Fraction(tolerance_ms, 1000)
    n, m = len(candidate_times), len(reference_times)
    empty: tuple[int, Fraction, tuple[tuple[int, int, Fraction], ...]] = (0, Fraction(0), ())
    dp = [[empty for _ in range(m + 1)] for _ in range(n + 1)]

    def better(a: tuple, b: tuple) -> tuple:
        if a[0] != b[0]:
            return a if a[0] > b[0] else b
        if a[1] != b[1]:
            return a if a[1] < b[1] else b
        return a if a[2] <= b[2] else b

    for ci in range(1, n + 1):
        expected_time = ref_anchor + (candidate_times[ci - 1] - candidate_anchor) * scale
        for ri in range(1, m + 1):
            best = better(dp[ci - 1][ri], dp[ci][ri - 1])
            error = reference_times[ri - 1] - expected_time
            if abs(error) <= tolerance:
                count, total, matched = dp[ci - 1][ri - 1]
                proposed = (count + 1, total + abs(error),
                            matched + ((ci - 1, ri - 1, error),))
                best = better(proposed, best)
            dp[ci][ri] = best
    alignment = {"referenceAnchor": ref_anchor, "candidateAnchor": candidate_anchor,
                 "scale": scale, "tolerance": tolerance}
    return alignment, dp[n][m][2]
