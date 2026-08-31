"""Per-quantile median ensemble — the same aggregation FluSight-ensemble uses
(hubEnsembles simple_ensemble, agg median), over our members.

Medians of sorted-per-member quantile vectors are themselves monotone, so the
ensemble needs no re-sorting.
"""

import pandas as pd

_KEYS = ["location", "horizon", "output_type_id"]


def per_quantile_median(members: list[pd.DataFrame]) -> pd.DataFrame:
    aligned = []
    reference_index = None
    for member in members:
        indexed = member.set_index(_KEYS)["value"].sort_index()
        if reference_index is None:
            reference_index = indexed.index
        elif not indexed.index.equals(reference_index):
            raise ValueError("ensemble members must share identical task sets")
        aligned.append(indexed)
    stacked = pd.concat(aligned, axis=1)
    return stacked.median(axis=1).rename("value").reset_index()
