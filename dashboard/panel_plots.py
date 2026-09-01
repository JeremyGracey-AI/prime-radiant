"""Figures for the FluSight dashboard (plotly, serve-time module).

Ships flat to the HF Space root; imports only the Space's requirements
(plotly/pandas). Band colors follow the house amber; diverging map colors are
RdBu reversed so red = predicted rise, centered at zero change.
"""

import pandas as pd
import plotly.graph_objects as go

AMBER = "217, 119, 6"  # house token, rgb
BAND_ALPHAS = {95: 0.12, 80: 0.22, 50: 0.34}
OBSERVED_COLOR = "#3f4a3c"  # house deep green-grey
MEDIAN_COLOR = "rgb(180, 83, 9)"


def choropleth_figure(frame: pd.DataFrame, reference_date: str) -> go.Figure:
    """US state choropleth of predicted 3-week change (h3 median − anchor)."""
    bad = frame.loc[~frame["abbreviation"].str.fullmatch(r"[A-Z]{2}"), "abbreviation"]
    if not bad.empty:
        # plotly renders NOTHING for FIPS codes under USA-states — fail loudly
        # instead of shipping a silently blank map.
        raise ValueError(f"not two-letter state abbreviations: {sorted(set(bad))}")
    trace = go.Choropleth(
        locations=frame["abbreviation"],
        z=frame["change"],
        locationmode="USA-states",
        colorscale="RdBu_r",
        zmid=0,
        colorbar={"title": {"text": "Δ admissions"}},
        customdata=frame.loc[:, ["location_name", "anchor", "predicted"]].to_numpy(),
        hovertemplate=(
            "%{customdata[0]}<br>last observed: %{customdata[1]:.0f}"
            "<br>predicted (3 wk): %{customdata[2]:.0f}"
            "<br>change: %{z:+.0f}<extra></extra>"
        ),
    )
    figure = go.Figure(data=[trace])
    title = f"Predicted 3-week change in weekly flu admissions (reference {reference_date})"
    figure.update_layout(
        geo={"scope": "usa"},
        title={"text": title},
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
    )
    return figure


def fan_figure(
    history: pd.DataFrame, bands: pd.DataFrame, location_label: str, model: str
) -> go.Figure:
    """Observed history plus nested forecast intervals, widest band first."""
    figure = go.Figure()
    for width in (95, 80, 50):  # widest first so narrower bands draw on top
        group = f"band{width}"
        figure.add_trace(
            go.Scatter(
                x=bands["target_end_date"],
                y=bands[f"hi{width}"],
                mode="lines",
                line={"width": 0},
                hoverinfo="skip",
                showlegend=False,
                legendgroup=group,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=bands["target_end_date"],
                y=bands[f"lo{width}"],
                mode="lines",
                line={"width": 0},
                fill="tonexty",
                fillcolor=f"rgba({AMBER}, {BAND_ALPHAS[width]})",
                hoverinfo="skip",
                name=f"{width}% interval",
                legendgroup=group,
            )
        )
    figure.add_trace(
        go.Scatter(
            x=bands["target_end_date"],
            y=bands["median"],
            mode="lines+markers",
            line={"color": MEDIAN_COLOR, "width": 2},
            name="median",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=history["date"],
            y=history["value"],
            mode="lines",
            line={"color": OBSERVED_COLOR, "width": 1.5},
            name="observed",
        )
    )
    figure.update_layout(
        title={"text": f"{location_label} — {model} forecast"},
        yaxis={"title": {"text": "Weekly flu admissions"}, "rangemode": "tozero"},
        hovermode="x unified",
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
    )
    return figure


def _diagonal() -> go.Scatter:
    return go.Scatter(
        x=[0, 1],
        y=[0, 1],
        mode="lines",
        line={"color": "grey", "dash": "dash", "width": 1},
        hoverinfo="skip",
        showlegend=False,
    )


def _coverage_layout(figure: go.Figure, title: str) -> go.Figure:
    figure.update_layout(
        title={"text": title},
        xaxis={"title": {"text": "Nominal central interval"}, "range": [0, 1]},
        yaxis={"title": {"text": "Empirical coverage"}, "range": [0, 1]},
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
    )
    return figure


def reliability_figure(coverage: pd.DataFrame, season: str) -> go.Figure:
    """Coverage-vs-nominal per model for one season; n rides along in hover."""
    figure = go.Figure(data=[_diagonal()])
    for model in coverage["model"].unique():
        subset = coverage.loc[coverage["model"] == model].sort_values("nominal")
        figure.add_trace(
            go.Scatter(
                x=subset["nominal"],
                y=subset["empirical"],
                mode="lines+markers",
                name=str(model),
                customdata=subset["n"].to_numpy(),
                hovertemplate="nominal %{x:.2f}: empirical %{y:.3f} (n=%{customdata})",
            )
        )
    return _coverage_layout(figure, f"Interval coverage — {season}")


def horizon_reliability_figure(coverage: pd.DataFrame) -> go.Figure:
    """lgbm coverage by horizon, pooled across seasons."""
    figure = go.Figure(data=[_diagonal()])
    for horizon in sorted(coverage["horizon"].unique()):
        subset = coverage.loc[coverage["horizon"] == horizon].sort_values("nominal")
        figure.add_trace(
            go.Scatter(
                x=subset["nominal"],
                y=subset["empirical"],
                mode="lines+markers",
                name=f"h={horizon}",
                customdata=subset["n"].to_numpy(),
                hovertemplate="nominal %{x:.2f}: empirical %{y:.3f} (n=%{customdata})",
            )
        )
    return _coverage_layout(figure, "prime-radiant lgbm coverage by horizon (all seasons)")
