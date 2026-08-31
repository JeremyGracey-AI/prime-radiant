"""Panel assembly contract: vintage-honest features, targets, and scaler.

The leakage property here is the brief's quality gate 4 applied to Phase C:
NOTHING prepared for an origin — features, targets, or the fitted transform —
may change when rows after the origin's data cutoff are appended.
"""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from prime_radiant.epi.features.assemble import prepare_origin

pytestmark = pytest.mark.contract

LOCATIONS_CSV = Path(__file__).parent.parent / "fixtures" / "locations.csv"
ORIGIN = date(2025, 12, 6)  # a Saturday


def _history(n_weeks: int = 30, locations: tuple[str, ...] = ("06", "US")) -> pd.DataFrame:
    end = pd.Timestamp(ORIGIN) - pd.Timedelta(days=7)
    dates = pd.date_range(end=end, periods=n_weeks, freq="7D")
    rows = []
    for i, loc in enumerate(locations):
        base = 50.0 * (i + 1)
        values = base + 10.0 * np.sin(np.arange(n_weeks) / 4.0) + np.arange(n_weeks)
        rows.append(pd.DataFrame({"date": dates, "location": loc, "value": values}))
    return pd.concat(rows, ignore_index=True)


class TestPrepareOrigin:
    def test_train_and_predict_share_feature_columns(self) -> None:
        inputs = prepare_origin(_history(), ORIGIN, LOCATIONS_CSV)
        assert list(inputs.x_train.columns) == list(inputs.x_predict.columns)
        assert len(inputs.x_train) == len(inputs.y_train)
        assert len(inputs.x_train) > 0

    def test_predict_rows_cover_locations_by_horizons(self) -> None:
        inputs = prepare_origin(_history(), ORIGIN, LOCATIONS_CSV, horizons=(0, 1, 2, 3))
        assert len(inputs.x_predict) == 2 * 4
        assert sorted(set(inputs.predict_meta["horizon"])) == [0, 1, 2, 3]

    def test_targets_are_transformed_deltas(self) -> None:
        # For a location with CONSTANT values the transformed delta is exactly 0.
        history = _history()
        history.loc[history["location"] == "06", "value"] = 120.0
        inputs = prepare_origin(history, ORIGIN, LOCATIONS_CSV)
        ca_rows = inputs.x_train["loc_06"] == 1
        assert np.allclose(inputs.y_train[ca_rows.to_numpy()], 0.0, atol=1e-12)

    def test_leakage_property_fixed_case(self) -> None:
        history = _history()
        cutoff = pd.Timestamp(ORIGIN) - pd.Timedelta(days=7)
        future = pd.DataFrame(
            {
                "date": [pd.Timestamp(ORIGIN) + pd.Timedelta(days=7)] * 2,
                "location": ["06", "US"],
                "value": [99999.0, 88888.0],
            }
        )
        clean = prepare_origin(history.loc[history["date"] <= cutoff], ORIGIN, LOCATIONS_CSV)
        dirty = prepare_origin(
            pd.concat([history, future], ignore_index=True), ORIGIN, LOCATIONS_CSV
        )
        pd.testing.assert_frame_equal(clean.x_train, dirty.x_train)
        np.testing.assert_array_equal(clean.y_train, dirty.y_train)
        pd.testing.assert_frame_equal(clean.x_predict, dirty.x_predict)
        pd.testing.assert_series_equal(clean.transform.scale, dirty.transform.scale)
        pd.testing.assert_series_equal(clean.transform.center, dirty.transform.center)

    @settings(max_examples=15, deadline=None)
    @given(
        future_value=st.floats(min_value=0.0, max_value=1e6, allow_nan=False),
        weeks_ahead=st.integers(min_value=0, max_value=8),
    )
    def test_leakage_property_random_future(self, future_value: float, weeks_ahead: int) -> None:
        history = _history()
        future = pd.DataFrame(
            {
                "date": [pd.Timestamp(ORIGIN) + pd.Timedelta(days=7 * weeks_ahead)],
                "location": ["06"],
                "value": [future_value],
            }
        )
        clean = prepare_origin(history, ORIGIN, LOCATIONS_CSV)
        dirty = prepare_origin(
            pd.concat([history, future], ignore_index=True), ORIGIN, LOCATIONS_CSV
        )
        pd.testing.assert_frame_equal(clean.x_train, dirty.x_train)
        np.testing.assert_array_equal(clean.y_train, dirty.y_train)
        pd.testing.assert_series_equal(clean.transform.scale, dirty.transform.scale)
