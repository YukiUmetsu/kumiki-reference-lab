"""Bounded Lucas-Kanade refinement of already accepted patch correspondences.

This is an opt-in, short-baseline, 2D brightness-constancy experiment. It never
creates a match, rescues a rejected point, or recovers camera/object identity.
Both directions must converge and agree; otherwise keep the integer match.
"""

from __future__ import annotations

import math
from typing import Any

PATCH_SIZE = 9
MAX_ITERATIONS = 8
MAX_FRACTIONAL_DEPARTURE = 1.25
REVERSE_TOLERANCE_PIXELS = 0.75


class BoundedLKPair:
    def __init__(self, before: bytes, after: bytes, width: int, height: int):
        import numpy as np

        if (type(width) is not int or type(height) is not int or
                not 64 <= width <= 240 or not 36 <= height <= 135 or
                type(before) is not bytes or type(after) is not bytes or
                len(before) != width * height or len(after) != width * height):
            raise ValueError("LK refinement requires bounded grayscale frame pairs")
        self.width, self.height = width, height
        self.before = np.frombuffer(before, dtype=np.uint8).reshape(height, width).astype(float)
        self.after = np.frombuffer(after, dtype=np.uint8).reshape(height, width).astype(float)
        half = PATCH_SIZE // 2
        self.ox, self.oy = np.meshgrid(np.arange(-half, half + 1, dtype=float),
                                      np.arange(-half, half + 1, dtype=float))

    def _sample(self, frame: Any, x: float, y: float) -> Any | None:
        import numpy as np

        xx, yy = self.ox + x, self.oy + y
        left, top = np.floor(xx).astype(int), np.floor(yy).astype(int)
        if (np.any(left < 0) or np.any(top < 0) or
                np.any(left + 1 >= self.width) or np.any(top + 1 >= self.height)):
            return None
        wx, wy = xx - left, yy - top
        return ((1 - wx) * (1 - wy) * frame[top, left] +
                wx * (1 - wy) * frame[top, left + 1] +
                (1 - wx) * wy * frame[top + 1, left] +
                wx * wy * frame[top + 1, left + 1])

    def _align(self, template: Any, frame: Any, x: float, y: float,
               initial_x: float, initial_y: float) -> dict[str, Any] | None:
        import numpy as np

        if template is None:
            return None
        centered = template - template.mean()
        if float(np.std(centered)) < 5.0:
            return None
        u, v = initial_x, initial_y
        first_rms = None
        iterations = 0
        for iteration in range(MAX_ITERATIONS):
            warped = self._sample(frame, x + u, y + v)
            if warped is None:
                return None
            residual = (warped - warped.mean()) - centered
            rms = float(np.sqrt(np.mean(residual ** 2)))
            if first_rms is None:
                first_rms = rms
            xp = self._sample(frame, x + u + 1, y + v)
            xm = self._sample(frame, x + u - 1, y + v)
            yp = self._sample(frame, x + u, y + v + 1)
            ym = self._sample(frame, x + u, y + v - 1)
            if xp is None or xm is None or yp is None or ym is None:
                return None
            gx, gy = (xp - xm) / 2, (yp - ym) / 2
            gradient = np.stack(((gx - gx.mean()).ravel(),
                                 (gy - gy.mean()).ravel()), axis=1)
            gram = gradient.T @ gradient
            try:
                singular = np.linalg.eigvalsh(gram)
                if singular[0] < 20 or singular[-1] / singular[0] > 500:
                    return None
                update = np.linalg.solve(gram, -gradient.T @ residual.ravel())
            except np.linalg.LinAlgError:
                return None
            if not np.all(np.isfinite(update)):
                return None
            step = float(np.linalg.norm(update))
            if step > 0.75:
                update *= 0.75 / step
            u += float(update[0])
            v += float(update[1])
            iterations = iteration + 1
            if math.hypot(u - initial_x, v - initial_y) > MAX_FRACTIONAL_DEPARTURE:
                return None
            if step < 0.01:
                break
        final = self._sample(frame, x + u, y + v)
        if final is None:
            return None
        end_rms = float(np.sqrt(np.mean(((final - final.mean()) - centered) ** 2)))
        if not math.isfinite(end_rms):
            return None
        return {"dx": u, "dy": v, "initialRms": first_rms,
                "finalRms": end_rms, "iterations": iterations}

    def refine(self, x: int, y: int, dx: int, dy: int) -> dict[str, Any]:
        """Return either a cross-checked fractional result or explicit fallback."""
        if any(type(v) is not int for v in (x, y, dx, dy)):
            raise ValueError("LK starts only from integer-verified correspondences")
        fallback: dict[str, Any] = {
            "status": "integer-fallback", "offsetPixels": None,
            "reverseErrorPixels": None, "photometricRmsGray": None,
            "iterations": 0,
        }
        template = self._sample(self.before, x, y)
        forward = self._align(template, self.after, x, y, dx, dy)
        if forward is None:
            return {**fallback, "reason": "unobservable-or-unstable-forward"}
        # A numerical update is not evidence unless it improves the measured
        # photometric fit on exactly the same patch.
        gain = forward["initialRms"] - forward["finalRms"]
        if gain < 0.5 or forward["finalRms"] > forward["initialRms"] * 0.98:
            return {**fallback, "reason": "no-meaningful-photometric-gain"}
        reverse_template = self._sample(self.after, x + forward["dx"],
                                        y + forward["dy"])
        reverse = self._align(reverse_template, self.before,
                              x + forward["dx"], y + forward["dy"],
                              -forward["dx"], -forward["dy"])
        if reverse is None:
            return {**fallback, "reason": "unobservable-or-unstable-reverse"}
        reverse_error = math.hypot(forward["dx"] + reverse["dx"],
                                   forward["dy"] + reverse["dy"])
        if reverse_error > REVERSE_TOLERANCE_PIXELS:
            return {**fallback, "reason": "fractional-reverse-inconsistent"}
        offset_x, offset_y = forward["dx"] - dx, forward["dy"] - dy
        if not all(map(math.isfinite, (offset_x, offset_y, reverse_error))):
            return {**fallback, "reason": "nonfinite-estimate"}
        return {"status": "fractional-lk-bidirectional-candidate",
                "reason": None,
                "offsetPixels": {"dx": round(offset_x, 4),
                                 "dy": round(offset_y, 4)},
                "reverseErrorPixels": round(reverse_error, 4),
                "photometricRmsGray": round(forward["finalRms"], 4),
                "iterations": forward["iterations"]}
