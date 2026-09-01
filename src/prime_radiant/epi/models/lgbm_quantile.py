"""Pooled LightGBM quantile model (flusion GBQR shape, single-source).

One booster per quantile level, trained on the pooled panel with horizon as a
feature; the model predicts the transformed DELTA from the last observation.
Post-processing: add back the last value, sort across levels within each
(location, horizon) in transformed space (crossing fix — valid because the
inverse transform is monotone), invert to counts, clip at zero. Integer rounding
happens only at the submission boundary.

Determinism recipe per LightGBM 4.7.0 docs: deterministic + force_row_wise +
fixed seed, num_threads=1 as belt-and-braces; native lgb.train because the
sklearn wrapper routes these through kwargs with a support warning. The docs
promise "stable" (not bit-exact) within one compiled binary — the determinism
test is the empirical arbiter on this machine.
"""

import numpy as np
import pandas as pd

from prime_radiant.epi.features.assemble import OriginInputs
from prime_radiant.epi.schemas import QUANTILE_LEVELS

DEFAULT_SEED = 59_460_707


def _params(alpha: float, seed: int) -> dict:
    return {
        "objective": "quantile",
        "alpha": alpha,
        "deterministic": True,
        "force_row_wise": True,
        "seed": seed,
        "num_threads": 1,
        "verbosity": -1,
    }


def fit_predict(
    inputs: OriginInputs,
    quantile_levels: tuple[float, ...] = QUANTILE_LEVELS,
    seed: int = DEFAULT_SEED,
    num_boost_round: int = 100,
) -> pd.DataFrame:
    """Train one booster per level and emit continuous count quantiles >= 0."""
    import lightgbm as lgb  # heavy native import kept local to this model path

    x_train = inputs.x_train.to_numpy(float)
    x_predict = inputs.x_predict.to_numpy(float)
    dataset = lgb.Dataset(x_train, label=inputs.y_train, free_raw_data=False)

    # np.asarray narrows lightgbm's union predict return for column_stack —
    # the older numpy stubs resolved on the 3.11 matrix leg reject the union.
    deltas = np.column_stack(
        [
            np.asarray(
                lgb.train(_params(level, seed), dataset, num_boost_round=num_boost_round).predict(
                    x_predict
                ),
                dtype=float,
            )
            for level in quantile_levels
        ]
    )
    transformed = inputs.predict_meta["last_y"].to_numpy(float)[:, None] + deltas
    transformed = np.sort(transformed, axis=1)  # crossing fix, in transformed space

    records: list[dict] = []
    meta_pairs = zip(
        inputs.predict_meta["location"].tolist(),
        inputs.predict_meta["horizon"].tolist(),
        strict=True,
    )
    for row_index, (location, horizon) in enumerate(meta_pairs):
        counts = inputs.transform.inverse(transformed[row_index], str(location))
        for level, value in zip(quantile_levels, counts, strict=True):
            records.append(
                {
                    "location": location,
                    "horizon": int(horizon),
                    "output_type_id": float(level),
                    "value": float(value),
                }
            )
    frame = pd.DataFrame.from_records(records)
    return frame.sort_values(["location", "horizon", "output_type_id"]).reset_index(drop=True)
