"""Serve-bundle builder for the HF Space dashboard.

Offline by construction: origins are enumerated from the persisted backtest
parquet filenames, official benchmarks come from the local cache directory only
(a cache miss is a loud error, never a fetch), truth is an explicit pinned
vintage parquet, and coverage curves are precomputed here so the Space needs
neither lightgbm nor this package at serve time. `season_forecast_frames` /
`build_reports` hit S3 unconditionally and are deliberately not reused.

Every output is deterministic (no timestamps, stable sort orders), because the
committed serve_data/ is regression-checked byte-for-byte like reports/.
"""

import json
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from prime_radiant.epi.backtest.report import (
    COVERAGE_WIDTHS_11,
    SCORED_HORIZONS,
    SEASONS,
    TRUTH_AS_OF,
    coverage_curve,
)
from prime_radiant.epi.data.benchmarks import normalize_model_output

# The clone's last target-data commit at or before TRUTH_AS_OF (2026-07-09) —
# the exact vintage the committed reports/ were scored against. Pinned by sha so
# building needs no git; the integration suite cross-checks it against
# resolve_vintage on the live clone.
TRUTH_VINTAGE_SHA = "786312d702f4cac588832f3028fa7288ba264cd4"

OUR_MODELS = ("ensemble", "lgbm", "baseline")
OFFICIAL_MODELS = ("FluSight-baseline", "FluSight-ensemble", "UMass-flusion")


def season_origins(backtest_dir: Path) -> dict[str, list[date]]:
    """Origins per season, enumerated from filenames; model dirs must agree."""
    stems_by_model = {
        model: {path.stem for path in (backtest_dir / model).glob("*.parquet")}
        for model in OUR_MODELS
    }
    union: set[str] = set().union(*stems_by_model.values())
    for model, stems in stems_by_model.items():
        missing = union - stems
        if missing:
            raise ValueError(f"backtest dirs disagree: {model}/ lacks {sorted(missing)}")
    origins = sorted(date.fromisoformat(stem) for stem in union)
    by_season: dict[str, list[date]] = {}
    assigned: set[date] = set()
    for season, (start, end, _prefixes) in SEASONS.items():
        selected = [origin for origin in origins if start <= origin <= end]
        if selected:
            by_season[season] = selected
            assigned.update(selected)
    orphans = [origin for origin in origins if origin not in assigned]
    if orphans:  # silently dropping them would misreport what the bundle covers
        listed = ", ".join(origin.isoformat() for origin in orphans)
        raise ValueError(f"origins outside every season window: {listed}")
    return by_season


def load_cached_benchmark(cache_dir: Path, model: str, start: date, end: date) -> pd.DataFrame:
    """Cached official weekly files within [start, end], normalized. Never fetches."""
    model_dir = cache_dir / model
    paths = sorted(
        path
        for path in model_dir.glob("*.parquet")
        if start <= date.fromisoformat(path.stem[:10]) <= end
    )
    if not paths:
        raise FileNotFoundError(
            f"no cached {model} files in {model_dir} within [{start}, {end}] — "
            "the bundle builder never fetches; warm the cache via the integration suite"
        )
    return pd.concat(
        [normalize_model_output(pd.read_parquet(path)) for path in paths],
        ignore_index=True,
    )


def build_bundle(
    *,
    backtest_dir: Path,
    benchmark_cache: Path,
    truth_parquet: Path,
    truth_vintage_sha: str,
    reports_dir: Path,
    locations_csv: Path,
    out_dir: Path,
    widths: tuple[float, ...] = COVERAGE_WIDTHS_11,
) -> Path:
    """Assemble the dashboard's serve bundle under out_dir; returns out_dir."""
    if not truth_parquet.exists():
        raise FileNotFoundError(str(truth_parquet))
    if not locations_csv.exists():
        raise FileNotFoundError(str(locations_csv))
    by_season = season_origins(backtest_dir)
    for season in by_season:  # validate every input before writing anything
        league_csv = reports_dir / f"backtest_{season}.csv"
        if not league_csv.exists():
            raise FileNotFoundError(str(league_csv))

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "forecasts").mkdir(exist_ok=True)
    (out_dir / "league").mkdir(exist_ok=True)

    our_frames: dict[str, pd.DataFrame] = {}
    for model in OUR_MODELS:
        paths = sorted((backtest_dir / model).glob("*.parquet"))
        frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
        frame = frame.loc[frame["horizon"].isin(SCORED_HORIZONS)].reset_index(drop=True)
        frame.to_parquet(
            out_dir / "forecasts" / f"{model}.parquet", index=False, compression="zstd"
        )
        our_frames[model] = frame

    shutil.copyfile(truth_parquet, out_dir / "truth.parquet")
    shutil.copyfile(locations_csv, out_dir / "locations.csv")
    for season in by_season:
        shutil.copyfile(
            reports_dir / f"backtest_{season}.csv",
            out_dir / "league" / f"backtest_{season}.csv",
        )

    truth = pd.read_parquet(truth_parquet)
    season_records: list[dict[str, object]] = []
    lgbm_frames: list[pd.DataFrame] = []
    for season in by_season:
        start, end, _prefixes = SEASONS[season]
        frames: dict[str, pd.DataFrame] = {}
        for official in OFFICIAL_MODELS:
            benchmark = load_cached_benchmark(benchmark_cache, official, start, end)
            frames[official] = benchmark.loc[benchmark["horizon"].isin(SCORED_HORIZONS)]
        for model in OUR_MODELS:
            ours = our_frames[model]
            in_season = (ours["reference_date"] >= pd.Timestamp(start)) & (
                ours["reference_date"] <= pd.Timestamp(end)
            )
            frames[f"prime-radiant-{model}"] = ours.loc[in_season]
        for name, frame in frames.items():
            for record in coverage_curve(frame, truth, widths).to_dict("records"):
                season_records.append({"model": name, "season": season, **record})
        lgbm_frames.append(frames["prime-radiant-lgbm"])

    seasons_table = pd.DataFrame.from_records(
        season_records, columns=["model", "season", "nominal", "empirical", "n"]
    ).sort_values(["model", "season", "nominal"], ignore_index=True)
    seasons_table.to_csv(out_dir / "coverage_seasons.csv", index=False, float_format="%.6f")

    pooled_lgbm = pd.concat(lgbm_frames, ignore_index=True)
    horizon_records: list[dict[str, object]] = []
    for horizon in SCORED_HORIZONS:
        sliced = pooled_lgbm.loc[pooled_lgbm["horizon"] == horizon]
        for record in coverage_curve(sliced, truth, widths).to_dict("records"):
            horizon_records.append({"horizon": horizon, **record})
    horizons_table = pd.DataFrame.from_records(
        horizon_records, columns=["horizon", "nominal", "empirical", "n"]
    )
    horizons_table.to_csv(out_dir / "coverage_horizons.csv", index=False, float_format="%.6f")

    manifest = {
        "schema_version": 1,
        "reference_date": max(
            origin for origins in by_season.values() for origin in origins
        ).isoformat(),
        "truth_as_of": TRUTH_AS_OF.isoformat(),
        "truth_vintage_sha": truth_vintage_sha,
        "models": sorted([*OFFICIAL_MODELS, *(f"prime-radiant-{m}" for m in OUR_MODELS)]),
        "seasons": {season: len(origins) for season, origins in by_season.items()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return out_dir
