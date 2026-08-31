"""Seasonal-naive reference model (contract-tested only; no official counterpart)."""

from datetime import date

import pandas as pd
import pytest

from prime_radiant.epi.models.seasonal import seasonal_naive

pytestmark = pytest.mark.unit

LEVELS3 = (0.25, 0.5, 0.75)


def _two_season_history() -> pd.DataFrame:
    # Same CDC epiweek one and two seasons back carries values 10 and 30.
    rows = []
    for start, base in (("2023-11-04", 10.0), ("2024-11-02", 30.0)):
        dates = pd.date_range(start, periods=6, freq="7D")
        rows.append(pd.DataFrame({"date": dates, "location": "US", "value": base}))
    return pd.concat(rows, ignore_index=True)


class TestSeasonalNaive:
    def test_quantiles_from_same_epiweek_history(self) -> None:
        # Target weeks fall on epiweeks whose history is {10, 30}:
        # type-7 quantiles at (.25,.5,.75) = (15, 20, 25) -> rounded (15, 20, 25).
        out = seasonal_naive(_two_season_history(), date(2025, 11, 8), quantile_levels=LEVELS3)
        h0 = out.loc[out["horizon"] == 0].sort_values("output_type_id")
        assert h0["value"].tolist() == [15, 20, 25]

    def test_output_is_monotone_int_and_nonnegative(self) -> None:
        out = seasonal_naive(_two_season_history(), date(2025, 11, 8), quantile_levels=LEVELS3)
        assert out["value"].dtype == "int64"
        assert (out["value"] >= 0).all()
        for _, group in out.groupby("horizon"):
            assert group.sort_values("output_type_id")["value"].is_monotonic_increasing

    def test_falls_back_to_last_value_when_no_seasonal_history(self) -> None:
        dates = pd.date_range("2025-09-06", periods=4, freq="7D")
        short = pd.DataFrame({"date": dates, "location": "US", "value": [5.0, 6, 7, 8]})
        out = seasonal_naive(short, date(2025, 10, 4), quantile_levels=LEVELS3)
        assert set(out[out["horizon"] == 1]["value"]) == {8}
