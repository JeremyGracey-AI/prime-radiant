"""Pandera contracts for the epi pipeline's stage boundaries.

Facts encoded here were verified against hub-config/tasks.json and
model-output/README.md on 2026-08-30:
- exactly 23 quantile levels, quantile is the only required output type;
- horizons -1..3; locations are "US" or 2-digit FIPS strings;
- submissions carry exactly 8 columns, no extras;
- integer values for `wk inc flu hosp` are README policy for 2025-26 — tasks.json
  types quantile values as double>=0, so THIS schema is the gate that catches a
  float regression.
"""

import pandas as pd
import pandera.pandas as pa

QUANTILE_LEVELS: tuple[float, ...] = (
    0.01,
    0.025,
    *(round(0.05 * i, 2) for i in range(1, 20)),  # 0.05 .. 0.95
    0.975,
    0.99,
)

TARGETS: tuple[str, ...] = (
    "wk inc flu hosp",
    "wk flu hosp rate change",
    "peak inc flu hosp",
    "peak week inc flu hosp",
    "wk inc flu prop ed visits",
)

HORIZONS: tuple[int, ...] = (-1, 0, 1, 2, 3)

_LOCATION_PATTERN = r"^(US|\d{2})$"

RawTargetSchema = pa.DataFrameSchema(
    {
        "date": pa.Column("datetime64[ns]", coerce=True),
        "location": pa.Column(str, pa.Check.str_matches(_LOCATION_PATTERN)),
        "location_name": pa.Column(str),
        # float, NOT int: early NHSN data holds weekly averages like 8.5. Integer
        # coercion is the submission layer's job. Nullable: the real hub file
        # carries NA cells (verified 2026-08-30); the raw layer represents reality.
        "value": pa.Column(float, pa.Check.ge(0), nullable=True, coerce=True),
        "weekly_rate": pa.Column(float, pa.Check.ge(0), nullable=True, coerce=True),
    },
    strict=True,
    name="RawTargetSchema",
)


def _quantiles_non_decreasing(df: pd.DataFrame) -> bool:
    grouped = df.sort_values("output_type_id").groupby(
        ["reference_date", "target", "horizon", "location"], observed=True, sort=False
    )
    return bool(grouped["value"].apply(lambda s: s.is_monotonic_increasing).all())


SubmissionSchema = pa.DataFrameSchema(
    {
        "reference_date": pa.Column("datetime64[ns]", coerce=True),
        "target": pa.Column(str, pa.Check.isin(TARGETS)),
        "horizon": pa.Column("int64", pa.Check.isin(HORIZONS), coerce=True),
        "target_end_date": pa.Column("datetime64[ns]", coerce=True),
        "location": pa.Column(str, pa.Check.str_matches(_LOCATION_PATTERN)),
        "output_type": pa.Column(str, pa.Check.isin(["quantile"])),
        "output_type_id": pa.Column(float, pa.Check.isin(QUANTILE_LEVELS)),
        # coerce=False is load-bearing: astype(int) would silently truncate 100.5;
        # a float column must FAIL here, not be rounded into compliance.
        "value": pa.Column("int64", pa.Check.ge(0), coerce=False),
    },
    checks=pa.Check(
        _quantiles_non_decreasing,
        error="quantile values must be non-decreasing within each task group",
    ),
    strict=True,  # model-output/README: "No additional columns are allowed."
    name="SubmissionSchema",
)

FeatureSchema = pa.DataFrameSchema(
    {
        "date": pa.Column("datetime64[ns]", coerce=True),
        "location": pa.Column(str, pa.Check.str_matches(_LOCATION_PATTERN)),
        "value": pa.Column(float, pa.Check.ge(0), coerce=True),
    },
    strict=False,  # feature columns accrete in later phases; the core spine is fixed
    name="FeatureSchema",
)
