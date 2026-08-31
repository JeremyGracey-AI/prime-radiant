"""Vintage usability guard: schema-pass is NOT enough (verified trap: a clean-form
but 106-row truncated vintage exists at 2024-11-15)."""

from datetime import date

import pandas as pd
import pytest

from prime_radiant.epi.backtest.rolling import vintage_is_usable

pytestmark = pytest.mark.unit

CUTOFF = date(2025, 11, 29)


def _vintage(start: str, end: str) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="7D")
    return pd.DataFrame({"date": dates, "location": "US", "value": 10.0})


class TestVintageIsUsable:
    def test_full_history_recent_vintage_passes(self) -> None:
        assert vintage_is_usable(_vintage("2022-02-05", "2025-11-22"), CUTOFF)

    def test_truncated_vintage_rejected(self) -> None:
        # the 2024-11-15 mode: clean header, ~2 weeks of rows
        assert not vintage_is_usable(_vintage("2025-11-15", "2025-11-22"), CUTOFF)

    def test_stale_vintage_rejected(self) -> None:
        # deep history but last row far behind the cutoff (same-day divergent
        # commit mode): max date must be within 14 days of the cutoff
        assert not vintage_is_usable(_vintage("2022-02-05", "2025-09-06"), CUTOFF)
