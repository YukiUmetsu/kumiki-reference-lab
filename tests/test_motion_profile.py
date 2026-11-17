"""Offline tests for the measured motion/transition profile (NumPy only)."""

from __future__ import annotations

import unittest

import numpy as np

from kumiki_reference_lab.acquisition import (
    MOTION_PROFILE_LIMITS, TRANSITION_CLASSES, classify_transitions,
    global_motion, local_motion_distribution, motion_signature,
    overlay_activity,
)

WIDTH, HEIGHT = 64, 36


def _solid(value: int, *, width: int = WIDTH, height: int = HEIGHT) -> bytes:
    return bytes([value, value, value]) * (width * height)


def _texture(seed: int = 1, *, width: int = WIDTH,
             height: int = HEIGHT) -> bytes:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:height, 0:width]
    base = ((x * 255) // max(width - 1, 1) + seed * 53).astype(np.uint16) % 256
    noise = rng.integers(0, 48, size=(height, width), dtype=np.uint16)
    red = np.clip(base + noise, 0, 255).astype(np.uint8)
    green = np.clip((y * 255) // max(height - 1, 1) + noise + seed * 29,
                    0, 255).astype(np.uint8)
    blue = np.clip(255 - base + noise // 2, 0, 255).astype(np.uint8)
    return np.stack([red, green, blue], axis=2).tobytes()


def _blend(before: bytes, after: bytes, alpha: float,
           *, width: int = WIDTH, height: int = HEIGHT) -> bytes:
    left = np.frombuffer(before, dtype=np.uint8).astype(np.float64)
    right = np.frombuffer(after, dtype=np.uint8).astype(np.float64)
    return np.round(left * (1 - alpha) + right * alpha).astype(np.uint8).tobytes()


class TransitionTests(unittest.TestCase):
    def test_hard_cut(self) -> None:
        frames = [_texture(1)] * 6 + [_texture(2)] * 6
        block = classify_transitions(
            frames, cut_pts=[6], timebase=0.1, fps=10, duration_seconds=1.2)
        self.assertEqual(block["cuts"][0]["transitionClass"], "hard-cut")
        self.assertEqual(block["counts"]["hard-cut"], 1)
        self.assertEqual(block["transitionCount"], 1)
        self.assertAlmostEqual(block["transitionRatePerMinute"], 50.0)
        self.assertAlmostEqual(sum(block["shares"].values()), 1.0, places=5)

    def test_half_second_dissolve_is_long(self) -> None:
        first, second = _texture(3), _texture(4)
        frames = [first] * 3
        frames += [_blend(first, second, step / 6.0) for step in range(1, 6)]
        frames += [second] * 3
        block = classify_transitions(
            frames, cut_pts=[6], timebase=0.1, fps=10, duration_seconds=1.2)
        self.assertEqual(block["cuts"][0]["transitionClass"], "long-dissolve")
        self.assertGreater(
            block["cuts"][0]["detail"]["activeSpanSeconds"], 0.25)

    def test_very_short_dissolve_is_short(self) -> None:
        first, second = _texture(5), _texture(6)
        frames = [first] * 3 + [_blend(first, second, 0.5)] + [second] * 3
        # Frames are 0.05 s apart; the graded run is well under 0.25 s.
        block = classify_transitions(
            frames, cut_pts=[3], timebase=0.05, fps=20, duration_seconds=0.4)
        self.assertEqual(
            block["cuts"][0]["transitionClass"], "short-dissolve")

    def test_fade_through_black(self) -> None:
        lumas = [0.8] * 6 + [0.65, 0.5, 0.35, 0.2, 0.08, 0.0,
                             0.08, 0.2, 0.35, 0.5, 0.65, 0.8]
        frames = [_solid(round(value * 255)) for value in lumas]
        block = classify_transitions(
            frames, cut_pts=[10], timebase=0.05, fps=20, duration_seconds=1.0)
        self.assertEqual(
            block["cuts"][0]["transitionClass"], "fade-through-black")
        self.assertEqual(block["counts"]["fade-through-black"], 1)

    def test_fade_through_white(self) -> None:
        lumas = [0.3, 0.4, 0.55, 0.7, 0.85, 0.95, 0.97, 0.95, 0.85, 0.7,
                 0.55, 0.4, 0.3]
        frames = [_solid(round(value * 255)) for value in lumas]
        block = classify_transitions(
            frames, cut_pts=[6], timebase=0.05, fps=20, duration_seconds=0.7)
        self.assertEqual(
            block["cuts"][0]["transitionClass"], "fade-through-white")

    def test_no_cuts_gives_empty_counts_and_zero_rate(self) -> None:
        block = classify_transitions(
            [_texture(7)] * 3, cut_pts=[], timebase=0.1, fps=10,
            duration_seconds=2.0)
        self.assertEqual(block["transitionCount"], 0)
        self.assertEqual(block["transitionRatePerMinute"], 0.0)
        self.assertEqual(set(block["counts"]), set(TRANSITION_CLASSES))
        self.assertTrue(all(value == 0 for value in block["shares"].values()))


class GlobalMotionTests(unittest.TestCase):
    def test_static_pair_is_static(self) -> None:
        frame = _texture(10, width=160, height=90)
        block = global_motion(
            [frame, frame], width=160, height=90, sample_seconds=1.0)
        self.assertEqual(block["status"], "measured")
        self.assertAlmostEqual(block["medianAbsDxPixelsPerSecond"], 0.0,
                               places=4)
        self.assertEqual(block["staticFraction"], 1.0)
        self.assertEqual(block["panFraction"], 0.0)
        self.assertAlmostEqual(block["zoomProxy"], 1.0, places=4)

    def test_twenty_pixel_per_second_pan(self) -> None:
        source = np.frombuffer(
            _texture(11, width=160, height=90), dtype=np.uint8
        ).reshape(90, 160, 3)
        frames = [np.roll(source, shift, axis=1).tobytes()
                  for shift in (0, 20, 40)]
        block = global_motion(
            frames, width=160, height=90, sample_seconds=1.0)
        self.assertEqual(block["panFraction"], 1.0)
        self.assertAlmostEqual(block["medianAbsDxPixelsPerSecond"], 20.0,
                               delta=1.5)
        self.assertEqual(block["staticFraction"], 0.0)

    def test_insufficient_frames_is_reported(self) -> None:
        block = global_motion(
            [_texture(12)], width=160, height=90)
        self.assertEqual(block["status"], "insufficient-frames")
        self.assertIsNone(block["medianAbsDxPixelsPerSecond"])


class LocalMotionTests(unittest.TestCase):
    def test_centre_weighted_motion_concentrates_in_centre_cell(self) -> None:
        width, height = 90, 90
        first = np.frombuffer(
            _texture(20, width=width, height=height), dtype=np.uint8
        ).reshape(height, width, 3).copy()
        second = first.copy()
        second[30:60, 30:60] = np.clip(
            second[30:60, 30:60].astype(np.int16) + 60, 0, 255).astype(np.uint8)
        block = local_motion_distribution(
            [first.tobytes(), second.tobytes()], width=width, height=height)
        self.assertAlmostEqual(sum(block["cellShares"]), 1.0, places=5)
        self.assertGreater(block["centreShare"], 0.95)
        self.assertAlmostEqual(block["motionCoverage"], 1 / 9, places=5)
        self.assertEqual(block["dominantCell"], [1, 1])

    def test_identical_frames_still_normalize(self) -> None:
        frame = _texture(21)
        block = local_motion_distribution(
            [frame, frame], width=WIDTH, height=HEIGHT)
        self.assertAlmostEqual(sum(block["cellShares"]), 1.0, places=5)
        self.assertEqual(block["motionCoverage"], 0.0)
        self.assertEqual(block["status"], "no-observable-change-uniform")


class OverlayActivityTests(unittest.TestCase):
    def test_activity_is_bounded_and_responds_to_detail_change(self) -> None:
        static = [_texture(30)] * 3
        quiet = overlay_activity(static, width=WIDTH, height=HEIGHT)
        changed = [_texture(31), _texture(32), _texture(33)]
        busy = overlay_activity(changed, width=WIDTH, height=HEIGHT)
        for block in (quiet, busy):
            self.assertGreaterEqual(block["lowerThirdActivity"], 0.0)
            self.assertLessEqual(block["lowerThirdActivity"], 1.0)
            self.assertGreaterEqual(block["upperThirdActivity"], 0.0)
            self.assertLessEqual(block["upperThirdActivity"], 1.0)
        self.assertGreater(busy["lowerThirdActivity"],
                           quiet["lowerThirdActivity"])


class SignatureCompositionTests(unittest.TestCase):
    def test_all_four_blocks_and_limits_are_composed(self) -> None:
        frames = [_texture(40)] * 6 + [_texture(41)] * 6
        signature = motion_signature(
            frames, width=WIDTH, height=HEIGHT, cut_pts=[6],
            timebase=0.1, fps=10, sample_seconds=1.0, duration_seconds=1.2)
        for key in ("transitions", "globalMotion", "localMotion",
                    "overlayActivity"):
            self.assertIn(key, signature)
        self.assertEqual(signature["limits"], MOTION_PROFILE_LIMITS)
        joined = " ".join(signature["limits"]).lower()
        for phrase in ("effect recognition", "template detection",
                       "camera or rig", "animation-technique",
                       "ground truth"):
            self.assertIn(phrase, joined)
        self.assertAlmostEqual(
            sum(signature["transitions"]["shares"].values()), 1.0, places=5)
        self.assertAlmostEqual(
            sum(signature["localMotion"]["cellShares"]), 1.0, places=5)

    def test_per_cut_mapping_is_accepted(self) -> None:
        first, second = _texture(50), _texture(51)
        windows = {
            6: [(0.2, first), (0.4, first), (0.6, second), (0.8, second)],
        }
        block = classify_transitions(
            windows, cut_pts=[6], timebase=0.1, fps=10, duration_seconds=1.2)
        self.assertEqual(block["cuts"][0]["transitionClass"], "hard-cut")


if __name__ == "__main__":
    unittest.main()
