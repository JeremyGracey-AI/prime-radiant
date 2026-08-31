"""Per-location value transform, simplified from the flusion GBQR pipeline:

count -> per-100k rate -> (rate + 0.01)^0.25 -> per-location scale by the
in-season 95th percentile (+eps) -> center by the in-season mean.

Convergent evidence (UMass-flusion and CMU both use rate + 4th root + per-location
scaling): this stack is what the winning models model. Source-specific offsets are
dropped — we are single-source (NHSN) and the Phase C gate is < 1.0, not flusion
replication.

`fit` accepts an explicit `cutoff`: transform statistics fitted past the forecast
origin leak the future through the scaler even when every feature is vintage-honest.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt
import pandas as pd

from prime_radiant.epi.features.seasonal import season_week

FloatArray = npt.NDArray[np.floating]

_RATE_OFFSET = 0.01
_SCALE_EPS = 0.01
_IN_SEASON = (10, 45)  # flusion's window for scaling statistics


@dataclass(frozen=True)
class LocationTransform:
    populations: pd.Series
    scale: pd.Series
    center: pd.Series

    @classmethod
    def fit(
        cls,
        history: pd.DataFrame,
        populations: pd.Series,
        cutoff: date | None = None,
    ) -> "LocationTransform":
        rows = history.dropna(subset=["value"]).copy()
        if cutoff is not None:
            rows = rows.loc[rows["date"] <= pd.Timestamp(cutoff)]
        weeks = rows["date"].map(lambda t: season_week(t.date()))
        in_season = rows.loc[weeks.between(*_IN_SEASON)]
        if in_season.empty:  # short histories (tests, season edges): use all rows
            in_season = rows

        pops = populations.reindex(in_season["location"]).to_numpy(float)
        transformed = _root_rate(in_season["value"].to_numpy(float), pops)
        frame = pd.DataFrame({"location": in_season["location"], "y": transformed})
        scale = frame.groupby("location")["y"].quantile(0.95) + _SCALE_EPS
        centered = frame["y"] / frame["location"].map(scale)
        center = (
            pd.DataFrame({"location": frame["location"], "c": centered})
            .groupby("location")["c"]
            .mean()
        )
        return cls(populations=populations, scale=scale, center=pd.Series(center))

    def to_transformed_rate(self, counts: FloatArray, location: str) -> FloatArray:
        return _root_rate(np.asarray(counts, float), float(self.populations.at[location]))

    def forward(self, counts: FloatArray, location: str) -> FloatArray:
        y = self.to_transformed_rate(counts, location)
        return y / float(self.scale.at[location]) - float(self.center.at[location])

    def inverse(self, values: FloatArray, location: str) -> FloatArray:
        y = (np.asarray(values, float) + float(self.center.at[location])) * float(
            self.scale.at[location]
        )
        rate = np.maximum(y, 0.0) ** 4 - _RATE_OFFSET
        counts = np.maximum(rate, 0.0) * float(self.populations.at[location]) / 100_000.0
        return counts


def _root_rate(counts: FloatArray, population: FloatArray | float) -> FloatArray:
    rate = counts / population * 100_000.0
    return (rate + _RATE_OFFSET) ** 0.25
