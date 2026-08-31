"""Score a long quantile frame against observed truth, per forecast task."""

from typing import cast

import numpy as np
import pandas as pd

from prime_radiant.eval.wis import wis_components

_TASK_KEYS = ["location", "target_end_date", "horizon"]


def score_quantile_frame(forecasts: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    """Per-task WIS + components. Tasks lacking (non-NA) truth are dropped —
    callers comparing two models must intersect task sets first."""
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
        parts = wis_components(
            ordered["output_type_id"].to_numpy(dtype=float),
            ordered["value"].to_numpy(dtype=float),
            float(ordered["observed"].iloc[0]),
        )
        records.append(
            dict(
                zip(_TASK_KEYS, key_tuple, strict=True),
                observed=float(ordered["observed"].iloc[0]),
                wis=parts.total,
                dispersion=parts.dispersion,
                overprediction=parts.overprediction,
                underprediction=parts.underprediction,
            )
        )
    columns = [*_TASK_KEYS, "observed", "wis", "dispersion", "overprediction", "underprediction"]
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame.from_records(records).loc[:, columns]


def mean_wis(scores: pd.DataFrame) -> float:
    return float(np.mean(scores["wis"]))
