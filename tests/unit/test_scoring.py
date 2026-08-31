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
