"""App smoke + committed-bundle contract: the real serve_data/ must support
every panel, and create_app() must assemble Blocks against it offline."""

from pathlib import Path
from typing import Any

import gradio as gr
import pytest

import panel_data
import panel_plots

pytestmark = pytest.mark.unit

SERVE_DATA = Path(__file__).parents[2] / "serve_data"


def _traces(figure: Any) -> list[Any]:
    return list(figure.data)


@pytest.fixture(scope="module")
def bundle() -> panel_data.Bundle:
    return panel_data.load_bundle(SERVE_DATA)


class TestCommittedBundleContract:
    def test_choropleth_covers_the_52_mappable_jurisdictions(
        self, bundle: panel_data.Bundle
    ) -> None:
        frame = panel_data.choropleth_frame(bundle)
        assert len(frame) == 52  # universe minus US (not drawable on scope='usa')
        # the abbreviation guard must accept the real data end-to-end
        figure = panel_plots.choropleth_figure(frame, bundle.manifest["reference_date"])
        assert len(_traces(figure)[0].locations) == 52
        assert "DC" in list(_traces(figure)[0].locations)

    def test_fan_series_works_for_the_national_row(self, bundle: panel_data.Bundle) -> None:
        history, bands = panel_data.fan_series(bundle, "US")
        assert not history.empty
        assert len(bands) == 5  # anchor point + horizons 0-3

    def test_every_season_has_reliability_and_league_rows(self, bundle: panel_data.Bundle) -> None:
        for season in ("2023-24", "2024-25", "2025-26"):
            assert not panel_data.reliability_seasons(bundle, season).empty
            assert not panel_data.league_view(bundle, season).empty


class TestCreateApp:
    def test_builds_blocks_offline_against_the_committed_bundle(
        self, bundle: panel_data.Bundle
    ) -> None:
        import app

        demo = app.create_app(bundle)
        assert isinstance(demo, gr.Blocks)
