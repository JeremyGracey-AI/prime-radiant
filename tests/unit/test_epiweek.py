"""Epiweek arithmetic: the date spine of every FluSight submission and backtest."""

from datetime import date

import pytest

from prime_radiant.epi.data.epiweek import reference_date_for, target_end_date

pytestmark = pytest.mark.unit


class TestTargetEndDate:
    def test_positive_horizon_adds_weeks(self) -> None:
        # Hub rule (README): target_end_date = reference_date + 7*horizon days
        assert target_end_date(date(2026, 1, 3), horizon=2) == date(2026, 1, 17)

    def test_zero_horizon_is_reference_date(self) -> None:
        assert target_end_date(date(2026, 1, 3), horizon=0) == date(2026, 1, 3)

    def test_negative_horizon_goes_back_one_week(self) -> None:
        assert target_end_date(date(2026, 1, 3), horizon=-1) == date(2025, 12, 27)

    def test_rejects_non_saturday_reference_date(self) -> None:
        with pytest.raises(ValueError, match="Saturday"):
            target_end_date(date(2026, 1, 2), horizon=0)  # a Friday


class TestReferenceDateFor:
    def test_wednesday_submission_maps_to_that_weeks_saturday(self) -> None:
        # 2025-12-31 is a Wednesday; its CDC epiweek ends Saturday 2026-01-03
        assert reference_date_for(date(2025, 12, 31)) == date(2026, 1, 3)

    def test_saturday_maps_to_itself(self) -> None:
        assert reference_date_for(date(2026, 1, 3)) == date(2026, 1, 3)

    def test_sunday_starts_the_next_epiweek(self) -> None:
        # CDC epiweeks run Sunday..Saturday, so a Sunday maps 6 days forward
        assert reference_date_for(date(2026, 1, 4)) == date(2026, 1, 10)

    def test_always_returns_a_saturday(self) -> None:
        for offset in range(14):
            d = date(2026, 1, 1 + offset)
            assert reference_date_for(d).weekday() == 5  # Saturday
