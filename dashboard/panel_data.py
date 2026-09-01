"""Data layer for the FluSight dashboard: bundle loading + panel frames.

Serve-time module: ships flat to the HF Space root and may import ONLY what the
Space installs (pandas/pyarrow + stdlib) — never prime_radiant, whose
dependency tree would drag lightgbm/libomp onto the Space.

The choropleth "3-week change" anchors on the last observation AT OR BEFORE the
forecast reference date, never on the latest truth row: the frozen bundle's
truth extends past the forecast window, and anchoring after the prediction
would be a vintage-semantics bug.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

MODELS = ("ensemble", "lgbm", "baseline")
SCHEMA_VERSION = 1

SUBMISSION_COLUMNS = [
    "reference_date",
    "target",
    "horizon",
    "target_end_date",
    "location",
    "output_type",
    "output_type_id",
    "value",
]

REQUIRED_FILES = (
    "forecasts/ensemble.parquet",
    "forecasts/lgbm.parquet",
    "forecasts/baseline.parquet",
    "truth.parquet",
    "locations.csv",
    "coverage_seasons.csv",
    "coverage_horizons.csv",
    "manifest.json",
)

# central intervals drawn as fan bands: width -> (lower level, upper level)
BAND_LEVELS = {
    0.95: (0.025, 0.975),
    0.80: (0.1, 0.9),
    0.50: (0.25, 0.75),
}


@dataclass(frozen=True)
class Bundle:
    forecasts: dict[str, pd.DataFrame]
    truth: pd.DataFrame
    league: dict[str, pd.DataFrame]
    locations: pd.DataFrame
    coverage_seasons: pd.DataFrame
    coverage_horizons: pd.DataFrame
    manifest: dict


def bundle_dir() -> Path:
    """serve_data/ next to this file (Space root) or at the repo root (dev)."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "serve_data", here.parent / "serve_data"):
        if candidate.is_dir():
            return candidate
    raise RuntimeError(f"no serve_data/ next to {here} or its parent — build it with `make bundle`")


def load_bundle(root: Path) -> Bundle:
    """Load and integrity-check the serve bundle; every failure is loud."""
    missing = [name for name in REQUIRED_FILES if not (root / name).exists()]
    league_paths = sorted(root.glob("league/backtest_*.csv"))
    if not league_paths:
        missing.append("league/backtest_*.csv")
    if missing:
        raise RuntimeError(f"bundle at {root} is missing: {', '.join(missing)}")

    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError(
            f"bundle schema_version {manifest.get('schema_version')!r} != {SCHEMA_VERSION}"
        )

    locations = pd.read_csv(root / "locations.csv", dtype={"abbreviation": str, "location": str})
    universe = set(locations["location"])

    forecasts: dict[str, pd.DataFrame] = {}
    for model in MODELS:
        frame = pd.read_parquet(root / "forecasts" / f"{model}.parquet")
        absent = [column for column in SUBMISSION_COLUMNS if column not in frame.columns]
        if absent or frame.empty:
            raise RuntimeError(f"forecasts/{model}.parquet malformed: missing {absent or 'rows'}")
        strays = sorted(set(frame["location"]) - universe)
        if strays:
            raise RuntimeError(
                f"forecasts/{model}.parquet has locations outside the universe: {strays}"
            )
        forecasts[model] = frame

    truth = pd.read_parquet(root / "truth.parquet")
    if truth.empty or not {"date", "location", "value"}.issubset(truth.columns):
        raise RuntimeError("truth.parquet malformed")

    league = {
        path.stem.removeprefix("backtest_"): pd.read_csv(path, dtype={"horizon": str})
        for path in league_paths
    }
    coverage_seasons = pd.read_csv(root / "coverage_seasons.csv")
    coverage_horizons = pd.read_csv(root / "coverage_horizons.csv")

    rows = sum(len(frame) for frame in forecasts.values())
    print(
        f"[startup] loaded bundle: reference_date {manifest['reference_date']}, "
        f"truth_as_of {manifest['truth_as_of']}, {rows} forecast rows, "
        f"{len(truth)} truth rows, seasons {sorted(league)}"
    )
    return Bundle(
        forecasts=forecasts,
        truth=truth,
        league=league,
        locations=locations,
        coverage_seasons=coverage_seasons,
        coverage_horizons=coverage_horizons,
        manifest=manifest,
    )


def latest_reference(bundle: Bundle, model: str) -> pd.Timestamp:
    latest = bundle.forecasts[model]["reference_date"].max()
    assert isinstance(latest, pd.Timestamp)  # column is datetime64 by contract
    return latest


def _anchors(truth: pd.DataFrame, reference: pd.Timestamp) -> pd.DataFrame:
    """Last observed value at or before the reference date, per location."""
    eligible = truth.loc[truth["date"] <= reference].sort_values("date", kind="stable")
    last = eligible.groupby("location", sort=False).tail(1)
    return last.loc[:, ["location", "date", "value"]].rename(
        columns={"date": "anchor_date", "value": "anchor"}
    )


def choropleth_frame(bundle: Bundle, model: str = "ensemble") -> pd.DataFrame:
    """Per-state predicted 3-week change: h3 median minus the anchor observation."""
    frame = bundle.forecasts[model]
    reference = latest_reference(bundle, model)
    h3 = frame.loc[
        (frame["reference_date"] == reference)
        & (frame["horizon"] == 3)
        & (frame["output_type_id"] == 0.5),
        ["location", "value"],
    ].rename(columns={"value": "predicted"})
    names = bundle.locations.loc[:, ["location", "abbreviation", "location_name"]]
    merged = h3.merge(_anchors(bundle.truth, reference), on="location").merge(names, on="location")
    merged = merged.loc[merged["location"] != "US"].reset_index(drop=True)
    merged["change"] = merged["predicted"] - merged["anchor"]
    return merged.loc[
        :, ["location", "abbreviation", "location_name", "anchor", "predicted", "change"]
    ]


def fan_series(
    bundle: Bundle, location: str, model: str = "ensemble"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(observed history, quantile bands) for one location's latest forecast."""
    frame = bundle.forecasts[model]
    reference = latest_reference(bundle, model)
    selected = frame.loc[(frame["reference_date"] == reference) & (frame["location"] == location)]
    pivot = selected.pivot(index="target_end_date", columns="output_type_id", values="value")
    bands = pd.DataFrame(
        {
            "target_end_date": pivot.index,
            "median": pivot[0.5].to_numpy(),
            "lo50": pivot[BAND_LEVELS[0.50][0]].to_numpy(),
            "hi50": pivot[BAND_LEVELS[0.50][1]].to_numpy(),
            "lo80": pivot[BAND_LEVELS[0.80][0]].to_numpy(),
            "hi80": pivot[BAND_LEVELS[0.80][1]].to_numpy(),
            "lo95": pivot[BAND_LEVELS[0.95][0]].to_numpy(),
            "hi95": pivot[BAND_LEVELS[0.95][1]].to_numpy(),
        }
    ).sort_values("target_end_date", ignore_index=True)

    anchors = _anchors(bundle.truth, reference)
    anchor = anchors.loc[anchors["location"] == location]
    if not anchor.empty:  # prepend the anchor point to close the history->forecast gap
        value = float(anchor["anchor"].iloc[0])
        anchor_row = pd.DataFrame(
            [
                {
                    "target_end_date": anchor["anchor_date"].iloc[0],
                    **{
                        column: value
                        for column in ("median", "lo50", "hi50", "lo80", "hi80", "lo95", "hi95")
                    },
                }
            ]
        )
        bands = pd.concat([anchor_row, bands], ignore_index=True)

    history = bundle.truth.loc[bundle.truth["location"] == location, ["date", "value"]].sort_values(
        "date", ignore_index=True
    )
    return history, bands


def state_choices(bundle: Bundle) -> list[tuple[str, str]]:
    """(label, location code) pairs: US first, then states by name."""
    frame = bundle.locations
    us = frame.loc[frame["location"] == "US"]
    rest = frame.loc[frame["location"] != "US"].sort_values("location_name")
    ordered = pd.concat([us, rest])
    return [
        (f"{name} ({abbrev})", code)
        for name, abbrev, code in zip(
            ordered["location_name"], ordered["abbreviation"], ordered["location"], strict=True
        )
    ]


def league_view(bundle: Bundle, season: str) -> pd.DataFrame:
    return bundle.league[season].loc[
        :,
        [
            "model_id",
            "horizon",
            "n",
            "wis",
            "wis_scaled_relative_skill",
            "interval_coverage_50",
            "interval_coverage_95",
        ],
    ]


def reliability_seasons(bundle: Bundle, season: str) -> pd.DataFrame:
    subset = bundle.coverage_seasons.loc[bundle.coverage_seasons["season"] == season]
    return subset.reset_index(drop=True)
