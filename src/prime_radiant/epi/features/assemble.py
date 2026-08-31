"""Pooled training/prediction panel for the LightGBM quantile model.

`prepare_origin` owns the origin cut: everything it emits — features, targets,
and the fitted transform — is derived ONLY from rows dated <= origin - 7 days.
Callers hand it a full vintage frame; the leakage contract lives here, not in
caller conventions. (Vintage honesty w.r.t. publication time is the vintage
store's job; this layer guards the model's time cut.)

Shape follows flusion's GBQR: one pooled panel across locations, horizon as a
feature, one-hot location + log_pop, target = transformed delta y[t+7h] - y[t],
training rows filtered to in-season weeks 5-45.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pandas as pd

from prime_radiant.epi.data.locations import load_locations
from prime_radiant.epi.features.lags import LAG_COLUMNS, add_lag_features
from prime_radiant.epi.features.seasonal import delta_xmas, season_week
from prime_radiant.epi.features.transform import LocationTransform

TRAIN_SEASON_WEEKS = (5, 45)  # flusion's training-row filter


@dataclass(frozen=True)
class OriginInputs:
    x_train: pd.DataFrame
    y_train: npt.NDArray[np.floating]
    x_predict: pd.DataFrame
    predict_meta: pd.DataFrame  # location, horizon, last transformed value, last date
    transform: LocationTransform
    feature_columns: list[str]


def prepare_origin(
    history: pd.DataFrame,
    origin: date,
    locations_csv: Path,
    horizons: tuple[int, ...] = (0, 1, 2, 3),
) -> OriginInputs:
    cutoff = pd.Timestamp(origin) - pd.Timedelta(days=7)
    rows = (
        history.dropna(subset=["value"])
        .loc[history["date"] <= cutoff, ["date", "location", "value"]]
        .sort_values(["location", "date"])
        .reset_index(drop=True)
    )

    locations_frame = load_locations(locations_csv)
    populations = pd.Series(
        locations_frame["population"].to_numpy(float),
        index=pd.Index(locations_frame["location"]),
    )
    all_locations = sorted(populations.index)

    transform = LocationTransform.fit(rows, populations, cutoff=origin - timedelta(days=7))
    rows["y"] = [
        transform.forward(np.array([v]), loc)[0]
        for v, loc in zip(rows["value"], rows["location"], strict=True)
    ]

    featured = add_lag_features(rows)
    featured["season_week"] = featured["date"].map(lambda t: season_week(t.date()))
    featured["delta_xmas"] = featured["season_week"].map(delta_xmas)
    featured["log_pop"] = np.log(populations.reindex(featured["location"]).to_numpy(float))

    base_columns = ["y", *LAG_COLUMNS, "season_week", "delta_xmas", "log_pop"]
    one_hot = pd.get_dummies(
        pd.Categorical(featured["location"], categories=all_locations), prefix="loc"
    ).astype(float)
    featured = pd.concat([featured, one_hot], axis=1)
    feature_columns = [*base_columns, "horizon", *one_hot.columns]

    # training rows: every (t, horizon) whose target row t+7h exists, in-season only
    value_at = featured.set_index(["location", "date"])["y"]
    train_parts: list[pd.DataFrame] = []
    targets: list[np.ndarray] = []
    complete = featured.dropna(subset=LAG_COLUMNS)
    in_season = complete["season_week"].between(*TRAIN_SEASON_WEEKS)
    complete = complete.loc[in_season]
    for horizon in horizons:
        target_index = pd.MultiIndex.from_arrays(
            [complete["location"], complete["date"] + pd.Timedelta(days=7 * horizon)]
        )
        target_y = value_at.reindex(target_index).to_numpy(float)
        has_target = ~np.isnan(target_y)
        part = complete.loc[has_target].copy()
        part["horizon"] = float(horizon)
        train_parts.append(part)
        targets.append(target_y[has_target] - part["y"].to_numpy(float))

    x_train = pd.concat(train_parts, ignore_index=True).loc[:, feature_columns]
    y_train = np.concatenate(targets)

    # prediction rows: each location's last observation, one row per horizon
    last_rows = featured.loc[featured.groupby("location")["date"].idxmax()]
    predict_parts: list[pd.DataFrame] = []
    meta_records: list[dict] = []
    for horizon in horizons:
        part = last_rows.copy()
        # horizon measured from the last observation to the target week, so a
        # lagging location still aims at the same target_end_date
        target_dates = pd.Timestamp(origin) + pd.Timedelta(days=7) * horizon
        part["horizon"] = (target_dates - part["date"]).dt.days / 7.0
        predict_parts.append(part)
        for _, row in part.iterrows():
            meta_records.append(
                {
                    "location": row["location"],
                    "horizon": horizon,
                    "last_y": row["y"],
                    "last_date": row["date"],
                }
            )
    x_predict = pd.concat(predict_parts, ignore_index=True).loc[:, feature_columns]
    predict_meta = pd.DataFrame.from_records(meta_records)

    return OriginInputs(
        x_train=x_train.reset_index(drop=True),
        y_train=y_train,
        x_predict=x_predict.reset_index(drop=True),
        predict_meta=predict_meta,
        transform=transform,
        feature_columns=feature_columns,
    )
