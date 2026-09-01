"""FluSight dashboard — Gradio app for the HF Space.

Thin shim over panel_data/panel_plots (the Remy_v1 house shape): create_app()
assembles the Blocks; only __main__ launches. Serve-time module: imports only
what the Space installs (gradio + the panel modules' pandas/plotly).
"""

import gradio as gr

import panel_data
import panel_plots

MODELS = ("ensemble", "lgbm", "baseline")


def create_app(bundle: panel_data.Bundle | None = None) -> gr.Blocks:
    if bundle is None:
        bundle = panel_data.load_bundle(panel_data.bundle_dir())
    manifest = bundle.manifest
    reference = str(manifest["reference_date"])
    seasons = sorted(bundle.league)
    default_season = seasons[-1]
    choices = panel_data.state_choices(bundle)
    labels = {code: label for label, code in choices}

    def make_choropleth(model: str):
        return panel_plots.choropleth_figure(panel_data.choropleth_frame(bundle, model), reference)

    def make_fan(location: str, model: str):
        history, bands = panel_data.fan_series(bundle, location, model)
        return panel_plots.fan_figure(history, bands, labels[location], model)

    def make_reliability(season: str):
        return panel_plots.reliability_figure(
            panel_data.reliability_seasons(bundle, season), season
        )

    def make_league(season: str):
        return panel_data.league_view(bundle, season)

    with gr.Blocks(title="Prime Radiant — FluSight") as demo:
        gr.Markdown(
            "# Prime Radiant — FluSight forecasts\n"
            "Weekly confirmed-flu hospital admissions, quantile forecasts "
            "(CDC FluSight format), WIS-scored backtests over three seasons.\n\n"
            f"**Latest forecast round:** {reference} · "
            f"**truth as of:** {manifest['truth_as_of']} · "
            "data is a frozen backtest bundle, not a live feed."
        )
        with gr.Tab("Map"):
            map_model = gr.Dropdown(choices=list(MODELS), value="ensemble", label="Model")
            map_plot = gr.Plot(value=make_choropleth("ensemble"))
            gr.Markdown(
                "Predicted change over 3 weeks: horizon-3 median minus the last "
                "observation at or before the reference date. Red = predicted rise. "
                "Puerto Rico is not drawable on the USA map — use the fan chart tab."
            )
            map_model.change(make_choropleth, [map_model], map_plot)
        with gr.Tab("Fan chart"):
            with gr.Row():
                fan_state = gr.Dropdown(choices=choices, value="US", label="Location")
                fan_model = gr.Dropdown(choices=list(MODELS), value="ensemble", label="Model")
            fan_plot = gr.Plot(value=make_fan("US", "ensemble"))
            fan_state.change(make_fan, [fan_state, fan_model], fan_plot)
            fan_model.change(make_fan, [fan_state, fan_model], fan_plot)
        with gr.Tab("Reliability"):
            rel_season = gr.Dropdown(choices=seasons, value=default_season, label="Season")
            rel_plot = gr.Plot(value=make_reliability(default_season))
            rel_season.change(make_reliability, [rel_season], rel_plot)
            gr.Plot(value=panel_plots.horizon_reliability_figure(bundle.coverage_horizons))
        with gr.Tab("League table"):
            league_season = gr.Dropdown(choices=seasons, value=default_season, label="Season")
            league_table = gr.Dataframe(value=make_league(default_season))
            league_season.change(make_league, [league_season], league_table)
            gr.Markdown(
                "`wis_scaled_relative_skill` < 1 beats FluSight-baseline on the "
                "common task set. Full column definitions in the repo's reports/."
            )
    return demo


if __name__ == "__main__":  # pragma: no cover — manual/Space entrypoint
    create_app().launch()
