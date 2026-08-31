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

# All five hub targets, for reference and later phases.
TARGETS: tuple[str, ...] = (
    "wk inc flu hosp",
    "wk flu hosp rate change",
    "peak inc flu hosp",
    "peak week inc flu hosp",
    "wk inc flu prop ed visits",
)

# SubmissionSchema covers ONLY what we actually ship (integer quantiles, horizons,
# per-week target_end_date). The other targets have different value domains
# (doubles in [0,1], pmf categories, null horizons) — each gets its own schema
# when its phase lands. Adversarial review demonstrated that one schema for all
# five both rejects hub-valid frames and accepts hub-invalid ones.
SUBMISSION_TARGETS: tuple[str, ...] = ("wk inc flu hosp",)

HORIZONS: tuple[int, ...] = (-1, 0, 1, 2, 3)

# The hub enumerates exactly 53 locations (tasks.json). A regex is over-permissive:
# gap FIPS ("03"), excluded territories ("60" AS), and nonsense ("99") match \d{2}
# but are hub-invalid. Constant cross-verified against the recorded locations.csv
# fixture by a contract test.
HUB_LOCATIONS: tuple[str, ...] = (
    "01",
    "02",
    "04",
    "05",
    "06",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "40",
    "41",
    "42",
    "44",
    "45",
    "46",
    "47",
    "48",
    "49",
    "50",
    "51",
    "53",
    "54",
    "55",
    "56",
    "72",
    "US",
)

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


_TASK_GROUP = ["reference_date", "target", "horizon", "location"]


def _quantiles_non_decreasing(df: pd.DataFrame) -> bool:
    grouped = df.sort_values("output_type_id").groupby(_TASK_GROUP, observed=True, sort=False)
    return bool(grouped["value"].apply(lambda s: s.is_monotonic_increasing).all())


def _quantile_sets_complete(df: pd.DataFrame) -> bool:
    # tasks.json marks all 23 levels `required`: a partial set or a duplicated
    # level is hub-invalid even though every row passes the column checks.
    expected = set(QUANTILE_LEVELS)
    grouped = df.groupby(_TASK_GROUP, observed=True, sort=False)
    return bool(
        grouped["output_type_id"]
        .apply(lambda s: len(s) == len(QUANTILE_LEVELS) and set(s) == expected)
        .all()
    )


def _date_arithmetic_holds(df: pd.DataFrame) -> bool:
    # Hub rule (model-output/README): target_end_date = reference_date + 7*horizon.
    expected = df["reference_date"] + pd.to_timedelta(df["horizon"] * 7, unit="D")
    return bool((df["target_end_date"] == expected).all())


def _reference_dates_are_saturdays(df: pd.DataFrame) -> bool:
    return bool((df["reference_date"].dt.weekday == 5).all())


SubmissionSchema = pa.DataFrameSchema(
    {
        "reference_date": pa.Column("datetime64[ns]", coerce=True),
        "target": pa.Column(str, pa.Check.isin(SUBMISSION_TARGETS)),
        "horizon": pa.Column("int64", pa.Check.isin(HORIZONS), coerce=True),
        "target_end_date": pa.Column("datetime64[ns]", coerce=True),
        "location": pa.Column(str, pa.Check.isin(HUB_LOCATIONS)),
        "output_type": pa.Column(str, pa.Check.isin(["quantile"])),
        "output_type_id": pa.Column(float, pa.Check.isin(QUANTILE_LEVELS)),
        # coerce=False is load-bearing: astype(int) would silently truncate 100.5;
        # a float column must FAIL here, not be rounded into compliance.
        "value": pa.Column("int64", pa.Check.ge(0), coerce=False),
    },
    checks=[
        pa.Check(
            _quantiles_non_decreasing,
            error="quantile values must be non-decreasing within each task group",
        ),
        pa.Check(
            _quantile_sets_complete,
            error="each task group must carry exactly the 23 required quantile levels",
        ),
        pa.Check(
            _date_arithmetic_holds,
            error="target_end_date must equal reference_date + 7*horizon days",
        ),
        pa.Check(
            _reference_dates_are_saturdays,
            error="reference_date must be a Saturday",
        ),
    ],
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
