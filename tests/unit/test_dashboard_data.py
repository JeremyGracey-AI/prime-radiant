"""Dashboard data layer: bundle loading (loud integrity checks) + panel frames.

The choropleth anchor test is the load-bearing one: "3-week change" anchors on
the last observation AT OR BEFORE the reference date, never on the latest truth
row — the frozen bundle's truth extends past the forecast window, and anchoring
after the prediction would be a vintage-semantics bug.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from panel_data import (
    Bundle,
    choropleth_frame,
    fan_series,
    latest_reference,
    league_view,
    load_bundle,
    reliability_seasons,
    state_choices,
)

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parents[1] / "fixtures"

BAND_LEVELS = (0.025, 0.1, 0.25, 0.5, 0.75, 0.9, 0.975)


def _forecast_frame(reference: str) -> pd.DataFrame:
    # includes the national row and PR so the not-drawable exclusion is
    # exercised by this synthetic fixture, not only the committed-bundle test
    rows = []
    for horizon in (0, 1, 2, 3):
        target_end = pd.Timestamp(reference) + pd.Timedelta(weeks=horizon)
        for location in ("01", "06", "US", "72"):
            for level in BAND_LEVELS:
                rows.append(
                    {
                        "reference_date": pd.Timestamp(reference),
                        "target": "wk inc flu hosp",
                        "horizon": horizon,
                        "target_end_date": target_end,
                        "location": location,
                        "output_type": "quantile",
                        "output_type_id": level,
                        # spread quantiles around a horizon-dependent median
                        "value": 15.0 + horizon + (level - 0.5) * 20,
                    }
                )
    return pd.DataFrame.from_records(rows)


def _truth_frame(end: str = "2024-12-14") -> pd.DataFrame:
    # Truth runs PAST the forecast window (like the frozen bundle): the value at
    # the reference date (20.0) differs from the last value (50.0).
    dates = pd.date_range("2024-09-07", end, freq="7D")
    rows = []
    for location in ("01", "06", "US", "72"):
        for when in dates:
            value = 20.0 if when <= pd.Timestamp("2024-11-23") else 50.0
            rows.append(
                {
                    "date": when,
                    "location": location,
                    "location_name": location,
                    "value": value,
                    "weekly_rate": 0.5,
                }
            )
    return pd.DataFrame.from_records(rows)


def _write_bundle(root: Path, truth: pd.DataFrame | None = None) -> Path:
    (root / "forecasts").mkdir(parents=True)
    (root / "league").mkdir()
    for model in ("ensemble", "lgbm", "baseline"):
        _forecast_frame("2024-11-23").to_parquet(
            root / "forecasts" / f"{model}.parquet", index=False
        )
    (_truth_frame() if truth is None else truth).to_parquet(root / "truth.parquet", index=False)
    (root / "locations.csv").write_bytes((FIXTURES / "locations.csv").read_bytes())
    (root / "league" / "backtest_2024-25.csv").write_text(
        "season,model_id,horizon,n,n_relative,truth_as_of,wis,ae_median,wis__log,"
        "ae_median__log,wis_scaled_relative_skill,wis_scaled_relative_skill__log,"
        "ae_median_scaled_relative_skill,interval_coverage_50,interval_coverage_95\n"
        "2024-25,prime-radiant-lgbm,all,5724,5724,2026-07-09,26.9,15.5,0.35,0.21,"
        "0.59,0.79,0.62,0.34,0.74\n"
    )
    pd.DataFrame(
        {
            "model": ["prime-radiant-lgbm", "prime-radiant-lgbm"],
            "season": ["2024-25", "2024-25"],
            "nominal": [0.5, 0.95],
            "empirical": [0.34, 0.74],
            "n": [5724, 5724],
        }
    ).to_csv(root / "coverage_seasons.csv", index=False)
    pd.DataFrame(
        {"horizon": [0, 3], "nominal": [0.5, 0.5], "empirical": [0.41, 0.32], "n": [4505, 4501]}
    ).to_csv(root / "coverage_horizons.csv", index=False)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "reference_date": "2024-11-23",
                "truth_as_of": "2026-07-09",
                "truth_vintage_sha": "feedface" * 5,
                "models": ["prime-radiant-ensemble"],
                "seasons": {"2024-25": 1},
            }
        )
    )
    return root


@pytest.fixture()
def bundle(tmp_path: Path) -> Bundle:
    return load_bundle(_write_bundle(tmp_path / "serve_data"))


class TestLoadBundle:
    def test_missing_files_are_all_named_loudly(self, tmp_path: Path) -> None:
        (tmp_path / "empty").mkdir()
        with pytest.raises(RuntimeError) as excinfo:
            load_bundle(tmp_path / "empty")
        assert "truth.parquet" in str(excinfo.value)
        assert "manifest.json" in str(excinfo.value)

    def test_unknown_schema_version_is_rejected(self, tmp_path: Path) -> None:
        root = _write_bundle(tmp_path / "serve_data")
        manifest = json.loads((root / "manifest.json").read_text())
        manifest["schema_version"] = 2
        (root / "manifest.json").write_text(json.dumps(manifest))
        with pytest.raises(RuntimeError, match="schema_version"):
            load_bundle(root)

    def test_forecast_location_outside_universe_is_rejected(self, tmp_path: Path) -> None:
        root = _write_bundle(tmp_path / "serve_data")
        frame = pd.read_parquet(root / "forecasts" / "ensemble.parquet")
        frame.loc[frame.index[:3], "location"] = "99"
        frame.to_parquet(root / "forecasts" / "ensemble.parquet", index=False)
        with pytest.raises(RuntimeError, match="99"):
            load_bundle(root)

    def test_startup_line_reports_what_loaded(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        load_bundle(_write_bundle(tmp_path / "serve_data"))
        out = capsys.readouterr().out
        assert "[startup]" in out
        assert "2024-11-23" in out


class TestChoroplethFrame:
    def test_anchor_is_last_observed_at_or_before_reference_date(self, bundle: Bundle) -> None:
        frame = choropleth_frame(bundle, model="ensemble")
        # truth continues to 50.0 after the reference date; the anchor must be
        # the 20.0 observed AT the reference date, never the later value
        assert (frame["anchor"] == 20.0).all()
        # h3 median = 15 + 3 = 18 -> change = -2
        assert (frame["predicted"] == 18.0).all()
        assert (frame["change"] == -2.0).all()

    def test_excludes_the_locations_usa_states_cannot_draw(self, bundle: Bundle) -> None:
        # US and PR (72) are in the forecasts but not drawable under
        # locationmode='USA-states'; leaving them in would let an invisible
        # region set the color scale (adversarial finding)
        frame = choropleth_frame(bundle, model="ensemble")
        assert set(frame["abbreviation"]) == {"AL", "CA"}
        assert "US" not in set(frame["location"])
        assert "72" not in set(frame["location"])
        assert frame["abbreviation"].str.fullmatch(r"[A-Z]{2}").all()

    def test_nan_on_anchor_date_falls_back_to_last_real_observation(self, tmp_path: Path) -> None:
        # adversarial finding: a NaN truth value on the anchor date must not
        # become the anchor — the last REAL observation must
        truth = _truth_frame()
        on_anchor_date = (truth["location"] == "01") & (truth["date"] == pd.Timestamp("2024-11-23"))
        truth.loc[on_anchor_date, "value"] = float("nan")
        bundle = load_bundle(_write_bundle(tmp_path / "serve_data", truth=truth))
        frame = choropleth_frame(bundle, model="ensemble")
        row = frame.loc[frame["location"] == "01"].iloc[0]
        assert row["anchor"] == 20.0  # from 2024-11-16, not NaN from 2024-11-23

    def test_location_with_no_real_observation_fails_loudly(self, tmp_path: Path) -> None:
        truth = _truth_frame()
        truth.loc[truth["location"] == "06", "value"] = float("nan")
        bundle = load_bundle(_write_bundle(tmp_path / "serve_data", truth=truth))
        with pytest.raises(RuntimeError, match="06"):
            choropleth_frame(bundle, model="ensemble")


class TestFanSeries:
    def test_no_anchor_prepend_when_truth_covers_the_first_target_date(
        self, bundle: Bundle
    ) -> None:
        # adversarial finding: prepending the anchor when h0's target_end_date
        # already has truth duplicates the x value and draws a vertical segment
        history, bands = fan_series(bundle, "01", model="ensemble")
        assert list(history.columns) == ["date", "value"]
        assert history["value"].iloc[-1] == 50.0
        assert len(bands) == 4  # horizons 0-3, no anchor row
        assert bands["target_end_date"].is_monotonic_increasing
        assert not bands["target_end_date"].duplicated().any()
        assert bands.iloc[0]["target_end_date"] == pd.Timestamp("2024-11-23")
        assert bands.iloc[0]["median"] == 15.0  # h0 median, not the anchor
        for _, row in bands.iterrows():
            assert (
                row["lo95"]
                <= row["lo80"]
                <= row["lo50"]
                <= row["median"]
                <= row["hi50"]
                <= row["hi80"]
                <= row["hi95"]
            )

    def test_anchor_prepended_only_across_a_real_gap(self, tmp_path: Path) -> None:
        # truth ends a week before the reference date -> a real gap exists and
        # the anchor point closes it
        bundle = load_bundle(
            _write_bundle(tmp_path / "serve_data", truth=_truth_frame(end="2024-11-16"))
        )
        _, bands = fan_series(bundle, "01", model="ensemble")
        assert len(bands) == 5  # anchor + horizons 0-3
        first = bands.iloc[0]
        assert first["target_end_date"] == pd.Timestamp("2024-11-16")
        assert first["median"] == 20.0
        assert bands["target_end_date"].is_monotonic_increasing
        assert not bands["target_end_date"].duplicated().any()


class TestSelectorsAndTables:
    def test_state_choices_cover_the_universe_with_us_first(self, bundle: Bundle) -> None:
        choices = state_choices(bundle)
        assert choices[0][1] == "US"
        assert len(choices) == 53  # US + 50 states + DC + PR (the hub universe)
        assert all(code == "US" or len(label) > 2 for label, code in choices)

    def test_latest_reference_is_the_manifest_round(self, bundle: Bundle) -> None:
        assert latest_reference(bundle, "ensemble") == pd.Timestamp("2024-11-23")

    def test_league_view_selects_display_columns(self, bundle: Bundle) -> None:
        view = league_view(bundle, "2024-25")
        assert list(view.columns) == [
            "model_id",
            "horizon",
            "n",
            "wis",
            "wis_scaled_relative_skill",
            "interval_coverage_50",
            "interval_coverage_95",
        ]

    def test_reliability_seasons_filters_to_the_season(self, bundle: Bundle) -> None:
        subset = reliability_seasons(bundle, "2024-25")
        assert (subset["season"] == "2024-25").all()
        assert len(subset) == 2
