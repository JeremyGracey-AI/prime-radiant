"""Per-quantile median ensemble (FluSight-ensemble's aggregation, our members)."""

import pandas as pd
import pytest

from prime_radiant.epi.models.ensemble import per_quantile_median

pytestmark = pytest.mark.unit


def _member(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "location": "06",
            "horizon": 1,
            "output_type_id": [0.25, 0.5, 0.75],
            "value": values,
        }
    )


class TestPerQuantileMedian:
    def test_median_of_two_members_is_midpoint(self) -> None:
        out = per_quantile_median([_member([10, 20, 30]), _member([20, 40, 60])])
        assert out.sort_values("output_type_id")["value"].tolist() == [15.0, 30.0, 45.0]

    def test_median_of_three_members_is_middle(self) -> None:
        out = per_quantile_median(
            [_member([10, 20, 30]), _member([20, 40, 60]), _member([12, 22, 32])]
        )
        assert out.sort_values("output_type_id")["value"].tolist() == [12.0, 22.0, 32.0]

    def test_misaligned_members_rejected(self) -> None:
        other = _member([1, 2, 3]).assign(location="US")
        with pytest.raises(ValueError, match="task sets"):
            per_quantile_median([_member([10, 20, 30]), other])
