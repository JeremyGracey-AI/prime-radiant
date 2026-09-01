"""LightGBM quantile model: determinism, monotone output, delta semantics."""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prime_radiant.epi.features.assemble import prepare_origin
from prime_radiant.epi.models.lgbm_quantile import fit_predict

pytestmark = pytest.mark.unit

LOCATIONS_CSV = Path(__file__).parent.parent / "fixtures" / "locations.csv"
ORIGIN = date(2025, 12, 6)
LEVELS5 = (0.1, 0.25, 0.5, 0.75, 0.9)


def _history(constant: float | None = None) -> pd.DataFrame:
    dates = pd.date_range(end=pd.Timestamp(ORIGIN) - pd.Timedelta(days=7), periods=40, freq="7D")
    rows = []
    for i, loc in enumerate(("06", "US")):
        if constant is not None:
            values = np.full(len(dates), constant * (i + 1))
        else:
            rng = np.random.default_rng(3 + i)
            values = 60.0 * (i + 1) + np.cumsum(rng.normal(0, 4, len(dates)))
            values = np.maximum(values, 1.0)
        rows.append(pd.DataFrame({"date": dates, "location": loc, "value": values}))
    return pd.concat(rows, ignore_index=True)


class TestFitPredict:
    def test_output_shape_and_nonnegativity(self) -> None:
        inputs = prepare_origin(_history(), ORIGIN, LOCATIONS_CSV)
        out = fit_predict(inputs, quantile_levels=LEVELS5, num_boost_round=10)
        assert len(out) == 2 * 4 * len(LEVELS5)  # locations x horizons x levels
        assert (out["value"] >= 0).all()

    def test_quantiles_monotone_within_each_task(self) -> None:
        inputs = prepare_origin(_history(), ORIGIN, LOCATIONS_CSV)
        out = fit_predict(inputs, quantile_levels=LEVELS5, num_boost_round=10)
        for _key, group in out.groupby(["location", "horizon"]):
            ordered = group.sort_values("output_type_id")["value"]
            assert ordered.is_monotonic_increasing

    def test_crossing_fix_is_actually_exercised(self) -> None:
        # Adversarial review proved the test above vacuous: its smooth fixture
        # never produces a crossing, so deleting the np.sort passed every test
        # while 210/212 real-vintage tasks crossed. This fixture is
        # SELF-VALIDATING: it first proves the raw boosters DO cross, then
        # asserts fit_predict's output is monotone anyway.
        import lightgbm as lgb

        from prime_radiant.epi.models.lgbm_quantile import _params
        from prime_radiant.epi.schemas import QUANTILE_LEVELS

        rng = np.random.default_rng(42)
        dates = pd.date_range(
            end=pd.Timestamp(ORIGIN) - pd.Timedelta(days=7), periods=60, freq="7D"
        )
        rows = []
        for i, loc in enumerate(("06", "48", "US")):
            values = np.maximum(40.0 * (i + 1) + np.cumsum(rng.normal(0, 25, len(dates))), 0.5)
            rows.append(pd.DataFrame({"date": dates, "location": loc, "value": values}))
        history = pd.concat(rows, ignore_index=True)
        inputs = prepare_origin(history, ORIGIN, LOCATIONS_CSV)

        # precondition: raw per-level boosters cross somewhere on this fixture
        dataset = lgb.Dataset(
            inputs.x_train.to_numpy(float), label=inputs.y_train, free_raw_data=False
        )
        raw = np.column_stack(
            [
                np.asarray(
                    lgb.train(_params(level, 59_460_707), dataset, num_boost_round=5).predict(
                        inputs.x_predict.to_numpy(float)
                    ),
                    dtype=float,
                )
                for level in QUANTILE_LEVELS
            ]
        )
        raw_crossings = int((np.diff(raw, axis=1) < 0).sum())
        assert raw_crossings > 0, "fixture failed to produce a crossing — test is vacuous"

        out = fit_predict(inputs, num_boost_round=5)
        for _key, group in out.groupby(["location", "horizon"]):
            ordered = group.sort_values("output_type_id")["value"]
            assert ordered.is_monotonic_increasing

    def test_constant_history_predicts_the_constant(self) -> None:
        # All training deltas are exactly 0 -> every quantile of delta is 0 ->
        # prediction inverts to the constant itself.
        inputs = prepare_origin(_history(constant=120.0), ORIGIN, LOCATIONS_CSV)
        out = fit_predict(inputs, quantile_levels=LEVELS5, num_boost_round=10)
        ca = out.loc[out["location"] == "06"]
        assert ca["value"].to_numpy() == pytest.approx(np.full(len(ca), 120.0), abs=1e-6)

    def test_deterministic_across_runs(self) -> None:
        inputs = prepare_origin(_history(), ORIGIN, LOCATIONS_CSV)
        first = fit_predict(inputs, quantile_levels=LEVELS5, num_boost_round=25)
        second = fit_predict(inputs, quantile_levels=LEVELS5, num_boost_round=25)
        pd.testing.assert_frame_equal(first, second)
