"""Flusion-style transform: count -> per-100k rate -> 4th root -> per-location scale/center.

Hand math for the core: pop 1,000,000, count 15 -> rate 1.5 per 100k;
(1.5 + 0.01) ** 0.25 = 1.10855... The inverse must round-trip counts exactly
(within float) and be strictly monotone.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from prime_radiant.epi.features.transform import LocationTransform

pytestmark = pytest.mark.unit

POPULATIONS = pd.Series({"06": 1_000_000.0, "US": 10_000_000.0})


def _history() -> pd.DataFrame:
    dates = pd.date_range("2025-11-01", periods=8, freq="7D")  # season weeks ~15-22
    rows = []
    for loc, base in (("06", 15.0), ("US", 400.0)):
        for i, d in enumerate(dates):
            rows.append({"date": d, "location": loc, "value": base + 5 * i})
    return pd.DataFrame(rows)


class TestLocationTransform:
    def test_forward_hand_computed_rate_and_root(self) -> None:
        transform = LocationTransform.fit(_history(), POPULATIONS)
        y = transform.to_transformed_rate(np.array([15.0]), "06")
        assert y[0] == pytest.approx((1.5 + 0.01) ** 0.25, abs=1e-12)

    def test_round_trip_counts(self) -> None:
        transform = LocationTransform.fit(_history(), POPULATIONS)
        counts = np.array([0.0, 3.0, 15.0, 250.0])
        forward = transform.forward(counts, "06")
        back = transform.inverse(forward, "06")
        assert back == pytest.approx(counts, abs=1e-9)

    def test_inverse_is_monotone(self) -> None:
        transform = LocationTransform.fit(_history(), POPULATIONS)
        ys = np.linspace(-2.0, 3.0, 50)
        back = transform.inverse(ys, "06")
        assert (np.diff(back) >= 0).all()

    def test_inverse_clips_at_zero(self) -> None:
        transform = LocationTransform.fit(_history(), POPULATIONS)
        assert transform.inverse(np.array([-100.0]), "06")[0] == 0.0

    def test_scaling_is_per_location(self) -> None:
        transform = LocationTransform.fit(_history(), POPULATIONS)
        y_ca = transform.forward(np.array([15.0]), "06")
        y_us = transform.forward(np.array([15.0]), "US")
        assert y_ca[0] != pytest.approx(y_us[0])

    def test_fit_ignores_rows_after_cutoff(self) -> None:
        # The subtle leak: a scaler fitted on future data poisons every origin.
        history = _history()
        cutoff = pd.Timestamp("2025-12-06")
        future = pd.DataFrame(
            {"date": [pd.Timestamp("2026-01-03")], "location": ["06"], "value": [9999.0]}
        )
        clean = LocationTransform.fit(history.loc[history["date"] <= cutoff], POPULATIONS)
        poisoned = LocationTransform.fit(
            pd.concat([history.loc[history["date"] <= cutoff], future], ignore_index=True),
            POPULATIONS,
            cutoff=date(2025, 12, 6),
        )
        assert clean.forward(np.array([20.0]), "06") == pytest.approx(
            poisoned.forward(np.array([20.0]), "06"), abs=1e-12
        )


class TestOffSeasonFallback:
    def test_entirely_off_season_history_fits_on_all_rows(self) -> None:
        # July dates sit outside the in-season week band; the fit must fall
        # back to the full history instead of producing empty groupings
        dates = pd.date_range("2025-07-05", periods=4, freq="7D")
        history = pd.DataFrame({"date": dates, "location": "06", "value": [8.0, 9.0, 7.0, 10.0]})
        transform = LocationTransform.fit(history, POPULATIONS)
        assert "06" in transform.scale.index
        assert transform.scale.loc["06"] > 0
        # and the round-trip still holds on the fallback statistics
        counts = history["value"].to_numpy(float)
        forwarded = transform.forward(counts, "06")
        assert np.allclose(transform.inverse(forwarded, "06"), counts)
