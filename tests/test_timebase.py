import unittest
from fractions import Fraction

from kumiki_reference_lab.core.timebase import (
    as_rational_dict, map_pts_to_frame, parse_rational, presentation_seconds,
)


class TimebaseTests(unittest.TestCase):
    def test_fractional_rates_are_exact(self):
        self.assertEqual(parse_rational("30000/1001"), Fraction(30000, 1001))
        self.assertEqual(as_rational_dict(Fraction(30000, 1001)),
                         {"numerator": 30000, "denominator": 1001})

    def test_unknown_or_invalid_rates(self):
        for value in [None, "N/A", "0/0", "0/1", "1/0", "not-a-rate"]:
            self.assertIsNone(parse_rational(value))

    def test_pts_are_not_frame_indices(self):
        self.assertEqual(presentation_seconds(90090, Fraction(1, 90000)),
                         Fraction(1001, 1000))
        self.assertEqual(map_pts_to_frame(90090, Fraction(1, 90000),
                                          Fraction(30000, 1001)), 30)

    def test_negative_and_half_frame_rounding(self):
        self.assertEqual(map_pts_to_frame(1, Fraction(1, 2), Fraction(1, 1)), 1)
        self.assertEqual(map_pts_to_frame(-1, Fraction(1, 2), Fraction(1, 1)), -1)
        self.assertEqual(map_pts_to_frame(0, Fraction(1, 100),
                                          Fraction(30, 1)), 0)

    def test_invalid_ticks(self):
        with self.assertRaises(TypeError):
            presentation_seconds(True, Fraction(1, 30))
        with self.assertRaises(ValueError):
            presentation_seconds(3, Fraction(0, 1))


if __name__ == "__main__":
    unittest.main()
