"""Replica of the official FluSight-baseline (epipredict::cdc_baseline_forecaster).

Algorithm verified from the R source (cmu-delphi/epipredict + cdcepi/Flusight-baseline,
2026-08-31), constants as used for the 2024-25 season:

- per-location residual pool = week-over-week diffs y(t+7d) - y(t), joined on exact
  dates (a gap yields no diff), over window_start <= t <= reference_date - 7d,
  excluding the 2024 reporting pause;
- symmetrize c(r, -r); "sample" = DETERMINISTIC type-7 quantile grid of nsims values
  at evenly spaced probabilities (numpy method="linear" == R type 7);
- hub horizon 0: grid + last observed value, truncated at 0 — deterministic; the
  truncated vector is carried forward;
- hub horizons 1..3: carried += a fresh random permutation of the grid (empirical
  h-fold convolution); the EMITTED copy is median-recentered to the last value and
  truncated, the carried copy is neither recentered nor truncated again;
- hub horizon -1: degenerate — every quantile equals the last observed value;
- floor(<0.5)/ceil(>=0.5) integer rounding.

Horizons >= 1 cannot be bit-exact vs the official files (R RNG); we use our own
seeded numpy stream (seed derived from reference_date, so runs are reproducible).
Validation is exact at horizon 0 and tolerance-based at horizons 1-3.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt
import pandas as pd

from prime_radiant.epi.models.postprocess import finalize_quantiles
from prime_radiant.epi.schemas import QUANTILE_LEVELS

FloatArray = npt.NDArray[np.floating]


@dataclass(frozen=True)
class BaselineConfig:
    quantile_levels: tuple[float, ...] = QUANTILE_LEVELS
    nsims: int = 100_000
    window_start: date = date(2022, 8, 6)  # official 2024-25 constant
    pause: tuple[date, date] = (date(2024, 5, 4), date(2024, 11, 2))  # reporting pause
    horizons: tuple[int, ...] = (-1, 0, 1, 2, 3)
    # Same numeric base the official script feeds R's set.seed; our numpy stream is
    # deliberately our own — reproducible per reference date, not bit-matching R.
    seed_base: int = 59_460_707


def week_over_week_diffs(frame: pd.DataFrame, pause: tuple[date, date] | None = None) -> FloatArray:
    """First differences over exactly 7 days for one location; gaps yield no diff."""
    rows = frame.dropna(subset=["value"]).loc[:, ["date", "value"]]
    if pause is not None:
        in_pause = rows["date"].between(pd.Timestamp(pause[0]), pd.Timestamp(pause[1]))
        rows = rows.loc[~in_pause]
    following = rows.assign(date=rows["date"] - pd.Timedelta(days=7)).rename(
        columns={"value": "next_value"}
    )
    joined = rows.merge(following, on="date")
    return (joined["next_value"] - joined["value"]).to_numpy(dtype=float)


def _sample_grid(diffs: FloatArray, nsims: int) -> FloatArray:
    if len(diffs) == 0:
        return np.zeros(nsims)
    symmetrized = np.concatenate([diffs, -diffs])
    return np.quantile(symmetrized, np.linspace(0.0, 1.0, nsims), method="linear")


_DEFAULT_CONFIG = BaselineConfig()


def flusight_baseline(
    history: pd.DataFrame,
    reference_date: date,
    config: BaselineConfig = _DEFAULT_CONFIG,
) -> pd.DataFrame:
    """History (date, location, value) as of a vintage -> long quantile frame."""
    cutoff = pd.Timestamp(reference_date) - pd.Timedelta(days=7)
    levels = np.array(config.quantile_levels)
    rng = np.random.default_rng(config.seed_base + reference_date.toordinal())

    records: list[dict] = []
    for location, group in history.groupby("location", sort=True):
        train = group.loc[
            (group["date"] >= pd.Timestamp(config.window_start)) & (group["date"] <= cutoff)
        ].sort_values("date")
        train = train.dropna(subset=["value"])
        if train.empty:
            raise ValueError(f"no training data for location {location!r} before {cutoff.date()}")
        last_value = float(train["value"].iloc[-1])

        grid = _sample_grid(week_over_week_diffs(train, pause=config.pause), config.nsims)
        carried = np.maximum(grid + last_value, 0.0)  # horizon 0, truncated once

        emitted: dict[int, npt.NDArray[np.int64]] = {}
        if -1 in config.horizons:
            emitted[-1] = finalize_quantiles(levels, np.full(len(levels), last_value))
        if 0 in config.horizons:
            emitted[0] = finalize_quantiles(levels, np.quantile(carried, levels, method="linear"))
        for horizon in sorted(h for h in config.horizons if h >= 1):
            carried = carried + rng.permutation(grid)
            recentered = carried - (np.median(carried) - last_value)
            emitted[horizon] = finalize_quantiles(
                levels, np.quantile(np.maximum(recentered, 0.0), levels, method="linear")
            )

        for horizon, values in emitted.items():
            for level, value in zip(levels, values, strict=True):
                records.append(
                    {
                        "location": location,
                        "horizon": horizon,
                        "output_type_id": float(level),
                        "value": int(value),
                    }
                )

    frame = pd.DataFrame(records).sort_values(["location", "horizon", "output_type_id"])
    return frame.reset_index(drop=True)
