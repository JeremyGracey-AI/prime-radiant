"""Frame-level scoring: submission frame + truth -> per-task WIS rows."""

import pandas as pd
import pytest

from prime_radiant.eval.scoring import score_quantile_frame

pytestmark = pytest.mark.unit


def _forecasts() -> pd.DataFrame:
    rows = []
    for level, value in ((0.25, 10), (0.5, 15), (0.75, 20)):
        rows.append(
            {
                "location": "06",
                "horizon": 0,
                "target_end_date": pd.Timestamp("2024-11-23"),
                "output_type_id": level,
                "value": value,
            }
        )
    return pd.DataFrame(rows)


def _truth(value: float = 22.0) -> pd.DataFrame:
    return pd.DataFrame(
        {"date": [pd.Timestamp("2024-11-23")], "location": ["06"], "value": [value]}
    )


class TestScoreQuantileFrame:
    def test_single_task_matches_hand_example(self) -> None:
        scores = score_quantile_frame(_forecasts(), _truth())
        assert len(scores) == 1
        assert abs(scores["wis"].iloc[0] - 16.0 / 3.0) < 1e-12
        assert scores["observed"].iloc[0] == 22.0

    def test_task_without_truth_is_dropped(self) -> None:
        truth = _truth().assign(date=[pd.Timestamp("2030-01-04")])
        scores = score_quantile_frame(_forecasts(), truth)
        assert len(scores) == 0

    def test_na_truth_is_dropped(self) -> None:
        scores = score_quantile_frame(_forecasts(), _truth(value=float("nan")))
        assert len(scores) == 0

    def test_components_present_and_sum_to_wis(self) -> None:
        scores = score_quantile_frame(_forecasts(), _truth())
        row = scores.iloc[0]
        total = row["dispersion"] + row["overprediction"] + row["underprediction"]
        assert abs(total - row["wis"]) < 1e-10

    def test_ae_median_is_abs_error_of_the_median(self) -> None:
        scores = score_quantile_frame(_forecasts(), _truth())
        assert scores["ae_median"].iloc[0] == pytest.approx(7.0)  # |22 - 15|

    def test_log_scale_follows_log_shift_offset_1(self) -> None:
        # Official convention: log(x+1) applied to forecasts AND observed, then
        # the same WIS formula. Hand math: q=(10,15,20) y=22 becomes
        # q'=(ln11,ln16,ln21), y'=ln23.
        import numpy as np

        scores = score_quantile_frame(_forecasts(), _truth(), scale="log")
        q = np.log(np.array([10.0, 15.0, 20.0]) + 1)
        y = float(np.log(23.0))
        losses = (np.array([(y <= v) for v in q]).astype(float) - np.array([0.25, 0.5, 0.75])) * (
            q - y
        )
        expected = 2.0 / 3.0 * losses.sum()
        assert scores["wis"].iloc[0] == pytest.approx(expected, abs=1e-12)
        # observed column stays on the natural scale for readability
        assert scores["observed"].iloc[0] == 22.0

    def test_scale_rejects_unknown(self) -> None:
        from typing import cast

        from prime_radiant.eval.scoring import Scale

        with pytest.raises(ValueError, match="natural|log"):
            # deliberately invalid literal — the runtime guard is under test
            score_quantile_frame(_forecasts(), _truth(), scale=cast(Scale, "sqrt"))
