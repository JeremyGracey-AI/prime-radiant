"""Rolling-origin backtest: per origin, resolve an honest vintage, run the models,
persist every forecast frame as parquet so scoring and gate reruns never retrain.

Vintage anchor: origin - 3 days (the Wednesday submission evening a live
forecaster would act on). The two-condition usability guard exists because
schema-pass is not enough — the vintage store holds a clean-form but truncated
106-row file (2024-11-15) and same-day commits with divergent row counts.
"""

from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from prime_radiant.epi.data.locations import season_locations_filename
from prime_radiant.epi.data.vintages import VintageNotFoundError, as_of
from prime_radiant.epi.features.assemble import prepare_origin
from prime_radiant.epi.models.baseline import flusight_baseline
from prime_radiant.epi.models.ensemble import per_quantile_median
from prime_radiant.epi.models.lgbm_quantile import fit_predict
from prime_radiant.epi.models.postprocess import finalize_quantiles
from prime_radiant.epi.schemas import QUANTILE_LEVELS
from prime_radiant.epi.submission.format import build_submission_frame

_MIN_HISTORY_WEEKS = 52
_MAX_STALENESS_DAYS = 14
MODELS = ("lgbm", "baseline", "ensemble")


def vintage_is_usable(vintage: pd.DataFrame, cutoff: date) -> bool:
    dates = vintage.dropna(subset=["value"])["date"]
    if dates.empty:
        return False
    span_weeks = (dates.max() - dates.min()).days / 7
    fresh_enough = (pd.Timestamp(cutoff) - dates.max()).days <= _MAX_STALENESS_DAYS
    return bool(span_weeks >= _MIN_HISTORY_WEEKS and fresh_enough)


class NoUsableVintageError(LookupError):
    """No vintage passed the guard for this origin — the honest miss.

    Deliberately its own type: KeyError/IndexError are LookupError subclasses,
    so a bare `except LookupError` around the guard let hub-side schema drift
    masquerade as "off-season, skip" (adversarial finding). Drift must crash
    red; only THIS error means the data genuinely is not there yet."""


def resolve_usable_vintage(  # pragma: no cover — needs the real clone; integration-tested
    hub_clone: Path, origin: date, vintage_cache: Path | None
) -> pd.DataFrame:
    cutoff = origin - timedelta(days=7)
    # Strictly earlier-only fallback: days_back < 3 would admit Thursday+ commits
    # a live Wednesday-11pm-ET run could never see (adversarial finding; the
    # fallback never fired across all 55 gate origins — every one resolved at 3).
    for days_back in (3, 4, 5, 6, 7, 8, 9, 10):
        try:
            frame = as_of(hub_clone, origin - timedelta(days=days_back), cache_dir=vintage_cache)
        except VintageNotFoundError:
            continue
        if vintage_is_usable(frame, cutoff):
            return frame
    raise NoUsableVintageError(f"no usable vintage found for origin {origin}")


def to_integer_submission(continuous: pd.DataFrame, reference_date: date) -> pd.DataFrame:
    """Continuous count quantiles -> hub-valid integer submission frame."""
    levels = np.array(QUANTILE_LEVELS)
    records: list[dict] = []
    for key, group in continuous.groupby(["location", "horizon"], sort=True):
        location, horizon = key  # type: ignore[misc]  # stubs type group keys as Hashable
        ordered = group.sort_values("output_type_id")
        values = finalize_quantiles(levels, ordered["value"].to_numpy(float))
        for level, value in zip(levels, values, strict=True):
            records.append(
                {
                    "location": location,
                    "horizon": int(horizon),
                    "output_type_id": float(level),
                    "value": int(value),
                }
            )
    return build_submission_frame(pd.DataFrame.from_records(records), reference_date)


def run_origin(  # pragma: no cover — needs clone + ~30s of training; integration-tested
    hub_clone: Path,
    origin: date,
    output_dir: Path,
    vintage_cache: Path | None = None,
    locations_csv: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """All three models for one origin, parquet-persisted and idempotent.

    Populations default to the SEASON-CORRECT hub snapshot for the origin
    (auxiliary-data/locations_2023xx.csv...), closing the census anachronism."""
    paths = {model: output_dir / model / f"{origin.isoformat()}.parquet" for model in MODELS}
    if all(path.exists() for path in paths.values()):
        return {model: pd.read_parquet(path) for model, path in paths.items()}

    if locations_csv is None:
        locations_csv = hub_clone / "auxiliary-data" / season_locations_filename(origin)
    vintage = resolve_usable_vintage(hub_clone, origin, vintage_cache)
    history = vintage.loc[:, ["date", "location", "value"]]

    inputs = prepare_origin(history, origin, locations_csv)
    lgbm_continuous = fit_predict(inputs)
    baseline_frame = flusight_baseline(history, origin)
    baseline_scorable = baseline_frame.loc[baseline_frame["horizon"] >= 0].assign(
        value=lambda f: f["value"].astype(float)
    )
    ensemble_continuous = per_quantile_median([lgbm_continuous, baseline_scorable])

    frames = {
        "lgbm": to_integer_submission(lgbm_continuous, origin),
        "baseline": build_submission_frame(baseline_frame, origin),
        "ensemble": to_integer_submission(ensemble_continuous, origin),
    }
    for model, frame in frames.items():
        paths[model].parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(paths[model])
    return frames


def run_backtest(  # pragma: no cover — thin loop over run_origin; integration-tested
    hub_clone: Path,
    origins: Iterable[date],
    output_dir: Path,
    vintage_cache: Path | None = None,
) -> dict[str, pd.DataFrame]:
    collected: dict[str, list[pd.DataFrame]] = {model: [] for model in MODELS}
    for origin in origins:
        frames = run_origin(hub_clone, origin, output_dir, vintage_cache)
        for model, frame in frames.items():
            collected[model].append(frame)
    return {model: pd.concat(parts, ignore_index=True) for model, parts in collected.items()}
