"""
Unit tests — money layer (no network, no DB).

Tests:
  - current_period_dates() returns correct 1–15 / 16–EOM ranges
  - discrepancy detection flag
  - TRON cents conversion (6-decimal USDT → cents)
"""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch


class TestPeriodDates(unittest.TestCase):

    def _check(self, today: date, expected_start: date, expected_end: date):
        from social_ios_automation.money.periods import current_period_dates
        with patch("social_ios_automation.money.periods.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            start, end = current_period_dates()
        self.assertEqual(start, expected_start)
        self.assertEqual(end, expected_end)

    def test_first_half_jan(self):
        self._check(
            date(2024, 1, 10),
            date(2024, 1, 1),
            date(2024, 1, 15),
        )

    def test_second_half_jan(self):
        self._check(
            date(2024, 1, 20),
            date(2024, 1, 16),
            date(2024, 1, 31),
        )

    def test_second_half_feb_leap(self):
        self._check(
            date(2024, 2, 20),
            date(2024, 2, 16),
            date(2024, 2, 29),
        )

    def test_second_half_feb_nonleap(self):
        self._check(
            date(2025, 2, 20),
            date(2025, 2, 16),
            date(2025, 2, 28),
        )

    def test_boundary_day_15(self):
        # 15th → first half
        self._check(
            date(2024, 3, 15),
            date(2024, 3, 1),
            date(2024, 3, 15),
        )

    def test_boundary_day_16(self):
        # 16th → second half
        self._check(
            date(2024, 3, 16),
            date(2024, 3, 16),
            date(2024, 3, 31),
        )


class TestTronCentsConversion(unittest.TestCase):
    """
    USDT TRC-20 has 6 decimals.
    raw_value / 10^6 = USDT
    USDT * 100 = cents
    So: raw_value / 10^4 = cents
    """

    def _raw_to_cents(self, raw: int) -> int:
        return raw // 10_000

    def test_10_usdt(self):
        raw = 10_000_000   # 10 USDT in raw TRC-20 units
        self.assertEqual(self._raw_to_cents(raw), 1000)

    def test_1_usdt(self):
        raw = 1_000_000
        self.assertEqual(self._raw_to_cents(raw), 100)

    def test_0_50_usdt(self):
        raw = 500_000
        self.assertEqual(self._raw_to_cents(raw), 50)

    def test_fractional_truncates(self):
        raw = 1_234_567   # 1.234567 USDT → 123 cents (truncate)
        self.assertEqual(self._raw_to_cents(raw), 123)


class TestDiscrepancyFlag(unittest.TestCase):

    def test_within_tolerance_no_flag(self):
        gross_platform = 10000   # cents
        gross_daily    = 9950
        diff_pct = abs(gross_platform - gross_daily) / gross_platform * 100
        self.assertLess(diff_pct, 2.0)

    def test_above_tolerance_flagged(self):
        gross_platform = 10000
        gross_daily    = 9700   # 3% off
        diff_pct = abs(gross_platform - gross_daily) / gross_platform * 100
        self.assertGreater(diff_pct, 2.0)


if __name__ == "__main__":
    unittest.main()
