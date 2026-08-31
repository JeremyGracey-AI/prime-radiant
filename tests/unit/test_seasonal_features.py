"""Season-week encoding (flusion convention: season starts at epiweek 31)."""

from datetime import date

import pytest

from prime_radiant.epi.features.seasonal import delta_xmas, season_week

pytestmark = pytest.mark.unit


class TestSeasonWeek:
    def test_epiweek_40_is_season_week_10(self) -> None:
        assert season_week(date(2025, 10, 4)) == 10  # CDC epiweek 40

    def test_epiweek_52_is_season_week_22(self) -> None:
        assert season_week(date(2025, 12, 27)) == 22  # CDC epiweek 52

    def test_new_year_continues_the_season(self) -> None:
        # 2026-01-10 is the Saturday ENDING CDC epiweek 1 (which starts Sun Jan 4)
        assert season_week(date(2026, 1, 10)) == 23  # 22 + 1
        assert season_week(date(2026, 1, 17)) == 24  # epiweek 2

    def test_season_start(self) -> None:
        assert season_week(date(2025, 8, 2)) == 1  # CDC epiweek 31


class TestDeltaXmas:
    def test_christmas_week_is_zero(self) -> None:
        # Christmas lands in CDC epiweek 52 -> season week 22
        assert delta_xmas(22) == 0

    def test_signed_distance(self) -> None:
        assert delta_xmas(10) == -12
        assert delta_xmas(30) == 8
