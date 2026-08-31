"""Trailing-window features: hand-computed on the series 1, 2, 4, 8."""

import numpy as np
import pandas as pd
import pytest

from prime_radiant.epi.features.lags import add_lag_features

pytestmark = pytest.mark.unit


def _frame() -> pd.DataFrame:
    dates = pd.date_range("2025-11-01", periods=4, freq="7D")
    return pd.DataFrame({"date": dates, "location": "US", "y": [1.0, 2.0, 4.0, 8.0]})


class TestAddLagFeatures:
    def test_lags_and_diffs(self) -> None:
        out = add_lag_features(_frame())
        assert out["lag1"].tolist()[1:] == [1.0, 2.0, 4.0]
        assert np.isnan(out["lag1"].iloc[0])
        assert out["diff1"].tolist()[1:] == [1.0, 2.0, 4.0]

    def test_rolling_means_include_current_row(self) -> None:
        out = add_lag_features(_frame())
        assert out["roll_mean_2"].tolist()[1:] == [1.5, 3.0, 6.0]
        assert out["roll_mean_4"].iloc[3] == pytest.approx(3.75)

    def test_rolling_slope_is_trailing_polyfit(self) -> None:
        out = add_lag_features(_frame())
        # slope of [1,2,4] over x=[0,1,2] is 1.5; of [2,4,8] is 3.0
        assert out["roll_slope_3"].iloc[2] == pytest.approx(1.5)
        assert out["roll_slope_3"].iloc[3] == pytest.approx(3.0)

    def test_per_location_isolation(self) -> None:
        two = pd.concat(
            [_frame(), _frame().assign(location="06", y=[10.0, 10.0, 10.0, 10.0])],
            ignore_index=True,
        )
        out = add_lag_features(two)
        ca = out.loc[out["location"] == "06"]
        assert np.isnan(ca["lag1"].iloc[0])  # no bleed from US rows
        assert ca["diff1"].tolist()[1:] == [0.0, 0.0, 0.0]
