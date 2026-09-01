"""Serve-bundle builder: offline assembly of the dashboard's data (unit, synthetic).

The bundle must build from local inputs only — origins enumerated from backtest
filenames, benchmarks from the cache directory, truth from an explicit parquet —
and byte-identical on rebuild, because the committed serve_data/ is regression-
checked the same way reports/ is.
"""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.serve.bundle import (
    build_bundle,
    load_cached_benchmark,
    season_origins,
)

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parents[1] / "fixtures"
OUR_MODELS = ("ensemble", "lgbm", "baseline")


def _forecast_frame(reference: str, horizons: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for horizon in horizons:
        target_end = pd.Timestamp(reference) + pd.Timedelta(weeks=horizon)
        for location in ("01", "06"):
            for level, value in (
                (0.05, 5.0),
                (0.25, 10.0),
                (0.5, 15.0),
                (0.75, 20.0),
                (0.95, 30.0),
            ):
                rows.append(
                    {
                        "reference_date": pd.Timestamp(reference),
                        "target": "wk inc flu hosp",
                        "horizon": horizon,
                        "target_end_date": target_end,
                        "location": location,
                        "output_type": "quantile",
                        "output_type_id": level,
                        "value": value,
                    }
                )
    return pd.DataFrame.from_records(rows)


def _truth_frame() -> pd.DataFrame:
    dates = pd.date_range("2024-11-02", "2025-01-04", freq="7D")
    rows = []
    for location in ("01", "06"):
        for when in dates:
            rows.append(
                {
                    "date": when,
                    "location": location,
                    "location_name": location,
                    "value": 12.0,
                    "weekly_rate": 0.5,
                }
            )
    return pd.DataFrame.from_records(rows)


@pytest.fixture()
def bundle_inputs(tmp_path: Path) -> dict[str, Path]:
    backtest = tmp_path / "backtest"
    for model in OUR_MODELS:
        horizons = (-1, 0, 1, 2, 3) if model == "baseline" else (0, 1, 2, 3)
        frame = _forecast_frame("2024-11-23", horizons)
        (backtest / model).mkdir(parents=True)
        frame.to_parquet(backtest / model / "2024-11-23.parquet", index=False)

    benchmarks = tmp_path / "benchmarks"
    raw = FIXTURES / "2024-11-23-FluSight-baseline.parquet"
    for official in ("FluSight-baseline", "FluSight-ensemble", "UMass-flusion"):
        target = benchmarks / official / f"2024-11-23-{official}.parquet"
        target.parent.mkdir(parents=True)
        target.write_bytes(raw.read_bytes())

    truth = tmp_path / "truth-input.parquet"
    _truth_frame().to_parquet(truth, index=False)

    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "backtest_2024-25.csv").write_text("season,model_id\n2024-25,stub\n")

    return {
        "backtest_dir": backtest,
        "benchmark_cache": benchmarks,
        "truth_parquet": truth,
        "reports_dir": reports,
        "locations_csv": FIXTURES / "locations.csv",
    }


def _build(inputs: dict[str, Path], out_dir: Path) -> Path:
    return build_bundle(
        **inputs,
        truth_vintage_sha="feedface" * 5,
        out_dir=out_dir,
        widths=(0.5, 0.9),
    )


class TestSeasonOrigins:
    def test_enumerates_origins_from_filenames_by_season(self, tmp_path: Path) -> None:
        for model in OUR_MODELS:
            (tmp_path / model).mkdir()
            for stem in ("2023-10-14", "2025-11-22", "2025-11-29"):
                (tmp_path / model / f"{stem}.parquet").write_bytes(b"")
        origins = season_origins(tmp_path)
        assert origins == {
            "2023-24": [date(2023, 10, 14)],
            "2025-26": [date(2025, 11, 22), date(2025, 11, 29)],
        }

    def test_raises_on_origins_outside_every_season_window(self, tmp_path: Path) -> None:
        # 2024-06-01 falls between seasons: silently dropping it would misreport
        # what the bundle covers.
        for model in OUR_MODELS:
            (tmp_path / model).mkdir()
            (tmp_path / model / "2024-06-01.parquet").write_bytes(b"")
        with pytest.raises(ValueError, match="2024-06-01"):
            season_origins(tmp_path)

    def test_raises_when_model_dirs_disagree(self, tmp_path: Path) -> None:
        for model in OUR_MODELS:
            (tmp_path / model).mkdir()
            (tmp_path / model / "2024-11-23.parquet").write_bytes(b"")
        (tmp_path / "ensemble" / "2024-11-30.parquet").write_bytes(b"")
        with pytest.raises(ValueError, match="2024-11-30"):
            season_origins(tmp_path)


class TestLoadCachedBenchmark:
    def test_reads_and_normalizes_cached_files_in_window(self, tmp_path: Path) -> None:
        cache = tmp_path / "FluSight-baseline"
        cache.mkdir()
        raw = FIXTURES / "2024-11-23-FluSight-baseline.parquet"
        (cache / raw.name).write_bytes(raw.read_bytes())
        frame = load_cached_benchmark(
            tmp_path, "FluSight-baseline", date(2024, 11, 1), date(2025, 5, 31)
        )
        assert list(frame.columns) == [
            "reference_date",
            "target",
            "horizon",
            "target_end_date",
            "location",
            "output_type",
            "output_type_id",
            "value",
        ]
        assert (frame["output_type"] == "quantile").all()

    def test_ignores_files_outside_the_window(self, tmp_path: Path) -> None:
        cache = tmp_path / "FluSight-baseline"
        cache.mkdir()
        raw = FIXTURES / "2024-11-23-FluSight-baseline.parquet"
        (cache / raw.name).write_bytes(raw.read_bytes())
        with pytest.raises(FileNotFoundError, match="FluSight-baseline"):
            load_cached_benchmark(
                tmp_path, "FluSight-baseline", date(2023, 10, 1), date(2024, 5, 31)
            )

    def test_empty_cache_fails_loudly_rather_than_fetching(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="UMass-flusion"):
            load_cached_benchmark(tmp_path, "UMass-flusion", date(2024, 11, 1), date(2025, 5, 31))


class TestBuildBundle:
    def test_writes_the_full_layout(self, bundle_inputs: dict[str, Path], tmp_path: Path) -> None:
        out = _build(bundle_inputs, tmp_path / "serve_data")
        expected = {
            "forecasts/ensemble.parquet",
            "forecasts/lgbm.parquet",
            "forecasts/baseline.parquet",
            "truth.parquet",
            "league/backtest_2024-25.csv",
            "locations.csv",
            "coverage_seasons.csv",
            "coverage_horizons.csv",
            "manifest.json",
        }
        actual = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()}
        assert actual == expected

    def test_forecasts_keep_only_scored_horizons(
        self, bundle_inputs: dict[str, Path], tmp_path: Path
    ) -> None:
        out = _build(bundle_inputs, tmp_path / "serve_data")
        baseline = pd.read_parquet(out / "forecasts" / "baseline.parquet")
        assert sorted(baseline["horizon"].unique()) == [0, 1, 2, 3]

    def test_truth_is_a_byte_copy_of_the_pinned_vintage(
        self, bundle_inputs: dict[str, Path], tmp_path: Path
    ) -> None:
        out = _build(bundle_inputs, tmp_path / "serve_data")
        assert (out / "truth.parquet").read_bytes() == bundle_inputs["truth_parquet"].read_bytes()

    def test_coverage_tables_cover_all_models_and_lgbm_horizons(
        self, bundle_inputs: dict[str, Path], tmp_path: Path
    ) -> None:
        out = _build(bundle_inputs, tmp_path / "serve_data")
        seasons = pd.read_csv(out / "coverage_seasons.csv")
        assert list(seasons.columns) == ["model", "season", "nominal", "empirical", "n"]
        assert set(seasons["model"]) == {
            "FluSight-baseline",
            "FluSight-ensemble",
            "UMass-flusion",
            "prime-radiant-ensemble",
            "prime-radiant-lgbm",
            "prime-radiant-baseline",
        }
        horizons = pd.read_csv(out / "coverage_horizons.csv")
        assert list(horizons.columns) == ["horizon", "nominal", "empirical", "n"]
        assert sorted(horizons["horizon"].unique()) == [0, 1, 2, 3]

    def test_manifest_is_honest_and_timestamp_free(
        self, bundle_inputs: dict[str, Path], tmp_path: Path
    ) -> None:
        out = _build(bundle_inputs, tmp_path / "serve_data")
        manifest = json.loads((out / "manifest.json").read_text())
        assert manifest == {
            "schema_version": 1,
            "reference_date": "2024-11-23",
            "truth_as_of": "2026-07-09",
            "truth_vintage_sha": "feedface" * 5,
            "models": [
                "FluSight-baseline",
                "FluSight-ensemble",
                "UMass-flusion",
                "prime-radiant-baseline",
                "prime-radiant-ensemble",
                "prime-radiant-lgbm",
            ],
            "seasons": {"2024-25": 1},
        }

    def test_rebuild_is_byte_identical(
        self, bundle_inputs: dict[str, Path], tmp_path: Path
    ) -> None:
        first = _build(bundle_inputs, tmp_path / "one")
        second = _build(bundle_inputs, tmp_path / "two")
        first_files = sorted(p.relative_to(first) for p in first.rglob("*") if p.is_file())
        second_files = sorted(p.relative_to(second) for p in second.rglob("*") if p.is_file())
        assert first_files == second_files
        for name in first_files:
            assert (first / name).read_bytes() == (second / name).read_bytes(), name

    def test_missing_truth_fails_loudly(
        self, bundle_inputs: dict[str, Path], tmp_path: Path
    ) -> None:
        bundle_inputs["truth_parquet"] = tmp_path / "absent.parquet"
        with pytest.raises(FileNotFoundError, match="absent.parquet"):
            _build(bundle_inputs, tmp_path / "serve_data")

    def test_missing_league_csv_fails_loudly(
        self, bundle_inputs: dict[str, Path], tmp_path: Path
    ) -> None:
        (bundle_inputs["reports_dir"] / "backtest_2024-25.csv").unlink()
        with pytest.raises(FileNotFoundError, match="backtest_2024-25.csv"):
            _build(bundle_inputs, tmp_path / "serve_data")

    def test_missing_locations_csv_fails_loudly(
        self, bundle_inputs: dict[str, Path], tmp_path: Path
    ) -> None:
        bundle_inputs["locations_csv"] = tmp_path / "missing-locations.csv"
        with pytest.raises(FileNotFoundError, match="missing-locations.csv"):
            _build(bundle_inputs, tmp_path / "serve_data")
