"""Dashboard figures: structural checks on the plotly output.

The abbreviation guard is the load-bearing one: plotly's USA-states choropleth
silently renders NOTHING for FIPS codes, so a mapping regression would ship a
blank map with no error. The guard turns that into a loud failure.
"""

from typing import Any

import pandas as pd
import pytest

from panel_plots import (
    choropleth_figure,
    fan_figure,
    horizon_reliability_figure,
    reliability_figure,
)

pytestmark = pytest.mark.unit


def _traces(figure: Any) -> list[Any]:
    """plotly stubs type Figure.data opaquely; tests need plain attribute access."""
    return list(figure.data)


def _choropleth_input() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "location": ["01", "06"],
            "abbreviation": ["AL", "CA"],
            "location_name": ["Alabama", "California"],
            "anchor": [20.0, 30.0],
            "predicted": [18.0, 45.0],
            "change": [-2.0, 15.0],
        }
    )


def _bands() -> pd.DataFrame:
    rows = [
        {
            "target_end_date": pd.Timestamp("2024-11-16"),
            **dict.fromkeys(("median", "lo50", "hi50", "lo80", "hi80", "lo95", "hi95"), 20.0),
        }
    ]
    for week, median in enumerate((21.0, 22.0, 23.0, 24.0)):
        rows.append(
            {
                "target_end_date": pd.Timestamp("2024-11-23") + pd.Timedelta(weeks=week),
                "median": median,
                "lo50": median - 2,
                "hi50": median + 2,
                "lo80": median - 4,
                "hi80": median + 4,
                "lo95": median - 6,
                "hi95": median + 6,
            }
        )
    return pd.DataFrame.from_records(rows)


def _history() -> pd.DataFrame:
    dates = pd.date_range("2024-09-07", "2024-11-16", freq="7D")
    return pd.DataFrame({"date": dates, "value": [15.0] * len(dates)})


class TestChoroplethFigure:
    def test_uses_usa_states_mode_with_diverging_midpoint_zero(self) -> None:
        figure = choropleth_figure(_choropleth_input(), "2024-11-23")
        trace = _traces(figure)[0]
        assert trace.type == "choropleth"
        assert trace.locationmode == "USA-states"
        assert list(trace.locations) == ["AL", "CA"]
        assert trace.zmid == 0
        layout: Any = figure.layout  # plotly stubs type layout opaquely
        assert layout.geo.scope == "usa"

    def test_rejects_fips_locations_loudly(self) -> None:
        frame = _choropleth_input()
        frame["abbreviation"] = frame["location"]  # the silent-blank-map regression
        with pytest.raises(ValueError, match="two-letter"):
            choropleth_figure(frame, "2024-11-23")


class TestFanFigure:
    def test_band_pairs_then_median_then_observed(self) -> None:
        figure = fan_figure(_history(), _bands(), "Alabama (AL)", "ensemble")
        # 3 interval bands x 2 traces + median + observed history = 8 traces
        assert len(_traces(figure)) == 8
        fills = [trace.fill for trace in _traces(figure)]
        assert fills.count("tonexty") == 3
        names = [trace.name for trace in _traces(figure)]
        assert "95% interval" in names
        assert "80% interval" in names
        assert "50% interval" in names
        assert names[-2] == "median"
        assert names[-1] == "observed"

    def test_bands_are_added_widest_first_so_narrow_draws_on_top(self) -> None:
        figure = fan_figure(_history(), _bands(), "Alabama (AL)", "ensemble")
        band_names = [trace.name for trace in _traces(figure) if trace.fill == "tonexty"]
        assert band_names == ["95% interval", "80% interval", "50% interval"]


class TestReliabilityFigures:
    def test_diagonal_reference_plus_one_trace_per_model(self) -> None:
        coverage = pd.DataFrame(
            {
                "model": ["a", "a", "b", "b"],
                "season": ["2024-25"] * 4,
                "nominal": [0.5, 0.95, 0.5, 0.95],
                "empirical": [0.4, 0.9, 0.5, 0.96],
                "n": [100, 100, 100, 100],
            }
        )
        figure = reliability_figure(coverage, "2024-25")
        traces = _traces(figure)
        assert len(traces) == 3  # diagonal + a + b
        diagonal = traces[0]
        assert list(diagonal.x) == [0, 1]
        assert list(diagonal.y) == [0, 1]
        for trace in traces[1:]:
            assert trace.customdata is not None  # n rides along for hover honesty

    def test_horizon_curves_one_trace_per_horizon(self) -> None:
        coverage = pd.DataFrame(
            {
                "horizon": [0, 0, 3, 3],
                "nominal": [0.5, 0.95, 0.5, 0.95],
                "empirical": [0.41, 0.9, 0.32, 0.8],
                "n": [4505, 4505, 4501, 4501],
            }
        )
        figure = horizon_reliability_figure(coverage)
        traces = _traces(figure)
        assert len(traces) == 3  # diagonal + h=0 + h=3
        names = [trace.name for trace in traces[1:]]
        assert names == ["h=0", "h=3"]
