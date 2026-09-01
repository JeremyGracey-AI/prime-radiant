"""FluSight-baseline replica: deterministic pieces verified against hand math.

Method verified from epipredict::cdc_baseline_forecaster source (2026-08-31):
per-location week-over-week diffs (7-day date-join, never across gaps), symmetrized,
deterministic evenly-spaced type-7 quantile grid; horizon 0 = grid + last value,
truncated at 0 (no recentering); horizons 1-3 accumulate shuffled grids, recentered
to the last value, truncated; horizon -1 degenerate; floor(<0.5)/ceil(>=0.5) rounding.

Hand-computed micro-example (nsims=5, levels 0.25/0.5/0.75):
history 10,12,11,15 weekly -> diffs (2,-1,4) -> sym pool (-4,-2,-1,1,2,4);
grid = type-7 quantiles at linspace(0,1,5) = (-4,-1.75, 0, 1.75, 4);
horizon 0 raw = grid+15 = (11, 13.25, 15, 16.75, 19);
quantiles(0.25,0.5,0.75) of that = (13.25, 15, 16.75) -> rounded (13, 15, 17).
"""

from datetime import date

import pandas as pd
import pytest

from prime_radiant.epi.models.baseline import (
    BaselineConfig,
    flusight_baseline,
    week_over_week_diffs,
)

pytestmark = pytest.mark.unit

LEVELS3 = (0.25, 0.5, 0.75)


def _history(values: list[float], start: str = "2025-10-04", location: str = "US") -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(values), freq="7D")
    return pd.DataFrame({"date": dates, "location": location, "value": values})


class TestWeekOverWeekDiffs:
    def test_consecutive_weeks(self) -> None:
        diffs = week_over_week_diffs(_history([10, 12, 11, 15]))
        assert diffs.tolist() == [2.0, -1.0, 4.0]

    def test_no_diff_across_a_gap(self) -> None:
        frame = _history([10, 12, 11, 15])
        frame = frame.drop(index=2)  # missing week -> two seams, no cross-gap diff
        diffs = week_over_week_diffs(frame)
        assert diffs.tolist() == [2.0]

    def test_pause_weeks_are_excluded(self) -> None:
        # Official 2024-25 window drops the reporting pause 2024-05-04..2024-11-02:
        # diffs into, inside, and out of the pause must all vanish.
        dates = pd.date_range("2024-04-20", periods=4, freq="7D")  # ..27, 05-04, 05-11
        frame = pd.DataFrame({"date": dates, "location": "US", "value": [1.0, 2, 4, 8]})
        config = BaselineConfig(quantile_levels=LEVELS3, nsims=5)
        diffs = week_over_week_diffs(frame, pause=config.pause)
        assert diffs.tolist() == [1.0]  # only 04-20 -> 04-27 survives


class TestFlusightBaselineDeterministicParts:
    def test_hand_computed_horizon_zero(self) -> None:
        config = BaselineConfig(quantile_levels=LEVELS3, nsims=5)
        out = flusight_baseline(_history([10, 12, 11, 15]), date(2025, 11, 1), config)
        h0 = out.loc[out["horizon"] == 0].sort_values("output_type_id")
        assert h0["value"].tolist() == [13, 15, 17]

    def test_horizon_minus_one_is_degenerate_last_value(self) -> None:
        config = BaselineConfig(quantile_levels=LEVELS3, nsims=5)
        out = flusight_baseline(_history([10, 12, 11, 15]), date(2025, 11, 1), config)
        h_minus = out[out["horizon"] == -1]
        assert set(h_minus["value"]) == {15}

    def test_truncation_at_zero(self) -> None:
        config = BaselineConfig(quantile_levels=LEVELS3, nsims=5)
        out = flusight_baseline(_history([3, 1, 2, 1]), date(2025, 11, 1), config)
        assert (out["value"] >= 0).all()

    def test_deterministic_given_reference_date(self) -> None:
        config = BaselineConfig(quantile_levels=LEVELS3, nsims=101)
        history = _history([10, 12, 11, 15, 13, 18, 16, 20])
        first = flusight_baseline(history, date(2025, 11, 29), config)
        second = flusight_baseline(history, date(2025, 11, 29), config)
        pd.testing.assert_frame_equal(first, second)

    def test_quantiles_monotone_within_each_horizon(self) -> None:
        config = BaselineConfig(quantile_levels=LEVELS3, nsims=101)
        out = flusight_baseline(_history([10, 12, 11, 15, 9, 30, 22]), date(2025, 11, 22), config)
        for horizon, group in out.groupby("horizon"):
            ordered = group.sort_values("output_type_id")["value"]
            assert ordered.is_monotonic_increasing, f"horizon {horizon} not monotone"

    def test_history_after_cutoff_is_ignored(self) -> None:
        # Vintage discipline inside the model: rows dated after reference_date - 7d
        # must not affect the forecast.
        config = BaselineConfig(quantile_levels=LEVELS3, nsims=5)
        history = _history([10, 12, 11, 15])
        # last row lands on 2025-10-25; reference 2025-11-01 uses it as "last value".
        polluted = pd.concat(
            [
                history,
                pd.DataFrame(
                    {"date": [pd.Timestamp("2025-11-01")], "location": ["US"], "value": [999.0]}
                ),
            ],
            ignore_index=True,
        )
        clean = flusight_baseline(history, date(2025, 11, 1), config)
        dirty = flusight_baseline(polluted, date(2025, 11, 1), config)
        pd.testing.assert_frame_equal(clean, dirty)


class TestGuardBranches:
    def test_single_observation_collapses_to_last_value(self) -> None:
        # one point in the window -> no 7-day pairs -> empty diffs -> the grid
        # degenerates to zeros and every horizon-0 quantile equals last value
        config = BaselineConfig(quantile_levels=LEVELS3, nsims=5)
        frame = flusight_baseline(_history([15.0]), date(2025, 11, 8), config)
        h0 = frame.loc[frame["horizon"] == 0]
        assert set(h0["value"]) == {15}

    def test_no_training_data_fails_loudly(self) -> None:
        config = BaselineConfig(quantile_levels=LEVELS3, nsims=5)
        empty = _history([float("nan"), float("nan")])
        with pytest.raises(ValueError, match="no training data"):
            flusight_baseline(empty, date(2025, 11, 8), config)
