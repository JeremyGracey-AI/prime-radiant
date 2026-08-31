"""Score a long quantile frame against observed truth, per forecast task.

Two scales, per the official FluSight evaluation convention: "natural", and "log"
= scoringutils log_shift with offset 1 (log(x+1) applied to forecast values and
observed alike before the same WIS formula). Interval coverage is transform-
invariant, so coverage-style consumers read the natural-scale frame. The
`observed` column always reports the natural-scale observation for readability.
"""

from typing import Literal, cast

import numpy as np
import pandas as pd

from prime_radiant.eval.wis import wis_components

_TASK_KEYS = ["location", "target_end_date", "horizon"]

Scale = Literal["natural", "log"]


def score_quantile_frame(
    forecasts: pd.DataFrame, truth: pd.DataFrame, scale: Scale = "natural"
) -> pd.DataFrame:
    """Per-task WIS + components + ae_median. Tasks lacking (non-NA) truth are
    dropped — callers comparing two models must intersect task sets first."""
    if scale not in ("natural", "log"):
        raise ValueError(f"scale must be 'natural' or 'log', got {scale!r}")

    observed = (
        truth.dropna(subset=["value"])
        .rename(columns={"date": "target_end_date", "value": "observed"})
        .loc[:, ["location", "target_end_date", "observed"]]
    )
    merged = forecasts.merge(observed, on=["location", "target_end_date"], how="inner")

    records = []
    for keys, group in merged.groupby(_TASK_KEYS, sort=True):
        key_tuple = cast("tuple", keys)  # pandas stubs type group keys as Hashable
        ordered = group.sort_values("output_type_id")
        levels = ordered["output_type_id"].to_numpy(dtype=float)
        values = ordered["value"].to_numpy(dtype=float)
        observed_value = float(ordered["observed"].iloc[0])

        if scale == "log":
            scored_values = np.log(values + 1.0)
            scored_observation = float(np.log(observed_value + 1.0))
        else:
            scored_values = values
            scored_observation = observed_value

        parts = wis_components(levels, scored_values, scored_observation)
        median_value = float(scored_values[np.isclose(levels, 0.5)][0])
        records.append(
            dict(
                zip(_TASK_KEYS, key_tuple, strict=True),
                observed=observed_value,
                wis=parts.total,
                dispersion=parts.dispersion,
                overprediction=parts.overprediction,
                underprediction=parts.underprediction,
                ae_median=abs(scored_observation - median_value),
            )
        )
    columns = [
        *_TASK_KEYS,
        "observed",
        "wis",
        "dispersion",
        "overprediction",
        "underprediction",
        "ae_median",
    ]
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame.from_records(records).loc[:, columns]


def mean_wis(scores: pd.DataFrame) -> float:
    return float(np.mean(scores["wis"]))
