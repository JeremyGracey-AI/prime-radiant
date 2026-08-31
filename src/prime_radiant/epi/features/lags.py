"""Trailing-window features on the transformed series, per location.

All windows are backward-looking and INCLUDE the current row (flusion's trailing
windows do too) — the leakage property in the contract suite pins this: a row's
features never change when later rows are appended.
"""

import numpy as np
import pandas as pd

LAG_COLUMNS = [
    "lag1",
    "lag2",
    "diff1",
    "diff2",
    "roll_mean_2",
    "roll_mean_4",
    "roll_slope_3",
    "roll_slope_5",
]


def _trailing_slope(series: pd.Series, window: int) -> pd.Series:  # noqa: D401
    x = np.arange(window, dtype=float)

    def slope(values: np.ndarray) -> float:
        return float(np.polyfit(x, values, deg=1)[0])

    result = series.rolling(window, min_periods=window).apply(slope, raw=True)
    return pd.Series(result)


def add_lag_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values(["location", "date"]).reset_index(drop=True).copy()
    grouped = out.groupby("location", sort=False)["y"]
    out["lag1"] = grouped.shift(1)
    out["lag2"] = grouped.shift(2)
    out["diff1"] = out["y"] - out["lag1"]
    out["diff2"] = out["lag1"] - out["lag2"]
    out["roll_mean_2"] = grouped.transform(lambda s: s.rolling(2, min_periods=2).mean())
    out["roll_mean_4"] = grouped.transform(lambda s: s.rolling(4, min_periods=4).mean())
    out["roll_slope_3"] = grouped.transform(lambda s: _trailing_slope(s, 3))
    out["roll_slope_5"] = grouped.transform(lambda s: _trailing_slope(s, 5))
    return out
