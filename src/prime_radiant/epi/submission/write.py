"""Hub-format submission CSV writer.

File naming and column conventions verified against the hub's model-output README
and the recorded official parquet: YYYY-MM-DD-<team>-<model>.csv, exactly the 8
hubverse columns, ISO dates, output_type_id as plain decimal strings, integer
values with no float suffix, no index column.
"""

from datetime import date
from pathlib import Path

import pandas as pd

_COLUMNS = [
    "reference_date",
    "target",
    "horizon",
    "target_end_date",
    "location",
    "output_type",
    "output_type_id",
    "value",
]


def submission_filename(reference_date: date, team_abbr: str, model_abbr: str) -> str:
    return f"{reference_date.isoformat()}-{team_abbr}-{model_abbr}.csv"


def _format_level(level: float) -> str:
    # plain decimal, trailing zeros trimmed: 0.5 -> "0.5", 0.975 -> "0.975"
    return f"{level:.3f}".rstrip("0").rstrip(".") if level != int(level) else str(int(level))


def write_submission_csv(
    frame: pd.DataFrame, out_dir: Path, team_abbr: str, model_abbr: str
) -> Path:
    from typing import cast

    first = pd.Timestamp(frame["reference_date"].iloc[0])
    assert not pd.isna(first)  # SubmissionSchema guarantees a real date
    reference_date = cast(date, first.date())  # stubs keep NaTType in the union
    out = frame.loc[:, _COLUMNS].copy()
    out["reference_date"] = pd.to_datetime(out["reference_date"]).dt.date.astype(str)
    out["target_end_date"] = pd.to_datetime(out["target_end_date"]).dt.date.astype(str)
    out["output_type_id"] = out["output_type_id"].map(_format_level)
    out["value"] = out["value"].astype(int)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / submission_filename(reference_date, team_abbr, model_abbr)
    out.to_csv(path, index=False)
    return path
