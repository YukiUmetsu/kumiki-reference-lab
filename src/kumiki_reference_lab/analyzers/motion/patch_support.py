"""Optional local patch-support check after accepted bidirectional NCC matches.

Checks four overlapping 5x5 subpatches of an already verified 9x9 match.
This can expose localized appearance loss, but cannot identify occlusion or
verify a physical subject. Ambiguous or untextured subpatches count as lost.
"""

from __future__ import annotations

import math
from typing import Any

PATCH_SIZE = 9
SUBPATCH_SIZE = 5
MIN_LOCAL_STD = 5.0
MIN_LOCAL_NCC = 0.65
MIN_SUPPORTING_QUADRANTS = 3


def assess_patch_support(before: bytes, after: bytes) -> dict[str, Any]:
    if type(before) is not bytes or type(after) is not bytes or len(before) != 81 or len(after) != 81:
        raise ValueError("quadrant support requires two nine-pixel grayscale patches")

    scores: list[float | None] = []
    for top in (0, PATCH_SIZE - SUBPATCH_SIZE):
        for left in (0, PATCH_SIZE - SUBPATCH_SIZE):
            indices = [(top + y) * PATCH_SIZE + left + x
                       for y in range(SUBPATCH_SIZE) for x in range(SUBPATCH_SIZE)]
            aa = [before[i] for i in indices]
            bb = [after[i] for i in indices]
            mean_a, mean_b = sum(aa) / 25, sum(bb) / 25
            centered_a = [a - mean_a for a in aa]
            centered_b = [b - mean_b for b in bb]
            length_a = sum(a * a for a in centered_a)
            length_b = sum(b * b for b in centered_b)
            if min(length_a, length_b) < SUBPATCH_SIZE ** 2 * MIN_LOCAL_STD ** 2:
                scores.append(None)
                continue
            score = sum(a * b for a, b in zip(centered_a, centered_b, strict=True)) / math.sqrt(length_a * length_b)
            scores.append(round(score, 5))
    support = sum(score is not None and score >= MIN_LOCAL_NCC for score in scores)
    return {"status": "supported" if support >= MIN_SUPPORTING_QUADRANTS else
                      "localized-appearance-unreliable",
            "quadrantCorrelations": scores, "supportingQuadrants": support}
