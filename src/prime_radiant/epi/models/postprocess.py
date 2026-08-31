"""Shared quantile postprocessing: hub rounding and non-negativity.

Official convention (verified in flusight-baseline.R, 2026-08-31): floor for
levels < 0.5, ceiling for levels >= 0.5 — which widens intervals slightly and
preserves monotonicity across levels.
"""

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.floating]


def finalize_quantiles(levels: FloatArray, values: FloatArray) -> npt.NDArray[np.int64]:
    clipped = np.maximum(values, 0.0)
    rounded = np.where(np.asarray(levels) < 0.5, np.floor(clipped), np.ceil(clipped))
    return rounded.astype(np.int64)
