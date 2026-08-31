"""Seasonal-naive reference model.

Quantiles for a target week are the empirical (type-7) quantiles of the values seen
at the SAME CDC epiweek in prior seasons; with no same-epiweek history the model
degenerates to the last observed value. Reference-only — there is no official
counterpart to validate against, so contract tests carry it.
"""

from datetime import date

import numpy as np
import pandas as pd
from epiweeks import Week

from prime_radiant.epi.data.epiweek import target_end_date
from prime_radiant.epi.models.postprocess import finalize_quantiles
from prime_radiant.epi.schemas import QUANTILE_LEVELS

HORIZONS: tuple[int, ...] = (-1, 0, 1, 2, 3)


def _epiweek_number(day: date) -> int:
    return Week.fromdate(day, system="cdc").week


def seasonal_naive(
    history: pd.DataFrame,
    reference_date: date,
    quantile_levels: tuple[float, ...] = QUANTILE_LEVELS,
    horizons: tuple[int, ...] = HORIZONS,
) -> pd.DataFrame:
    levels = np.array(quantile_levels)
    cutoff = pd.Timestamp(reference_date) - pd.Timedelta(days=7)

    records: list[dict] = []
    for location, group in history.groupby("location", sort=True):
        past = group.loc[group["date"] <= cutoff].dropna(subset=["value"]).copy()
        if past.empty:
            raise ValueError(f"no history for location {location!r} before {cutoff.date()}")
        past["epiweek"] = past["date"].map(lambda t: _epiweek_number(t.date()))
        last_value = float(past.sort_values("date")["value"].iloc[-1])

        for horizon in horizons:
            week_number = _epiweek_number(target_end_date(reference_date, horizon))
            pool = past.loc[past["epiweek"] == week_number, "value"].to_numpy(dtype=float)
            if len(pool) == 0:
                values = np.full(len(levels), last_value)
            else:
                values = np.quantile(pool, levels, method="linear")
            for level, value in zip(levels, finalize_quantiles(levels, values), strict=True):
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
