"""NHSN Weekly Hospital Respiratory Data via Socrata (data.cdc.gov), anonymous.

Verified 2026-08-30: `ua7e-t2fy` is the final weekly dataset, `mpgq-jmmr` the
preliminary edition (same schema); no app token needed at our volume, and a single
request with $limit=25000 returns the full history (~21k rows). Values arrive as
JSON strings and can be fractional in early data (weekly averages).

The jurisdiction column holds 67 values — states + DC/territories by abbreviation,
"USA", and HHS "Region 1".."Region 10" aggregates. Everything outside the hub's 53
codes is dropped via the locations bridge to avoid double counting.
"""

from pathlib import Path
from typing import Literal

import httpx
import pandas as pd

from prime_radiant.epi.data.locations import fips_for_nhsn_jurisdiction

_DATASETS = {
    "final": "ua7e-t2fy",
    "preliminary": "mpgq-jmmr",
}
_VALUE_COLUMN = "totalconfflunewadm"
# 25000 > the ~21k-row full history; verified to return in a single anonymous request.
_LIMIT = 25000

Dataset = Literal["final", "preliminary"]


def dataset_url(dataset: str) -> str:
    try:
        dataset_id = _DATASETS[dataset]
    except KeyError:
        raise ValueError(f"dataset must be 'final' or 'preliminary', got {dataset!r}") from None
    return f"https://data.cdc.gov/resource/{dataset_id}.json"


def fetch_admissions(
    locations_csv: Path,
    dataset: Dataset = "final",
    timeout: float = 60.0,
) -> pd.DataFrame:
    response = httpx.get(
        dataset_url(dataset),
        params={
            "$select": f"weekendingdate,jurisdiction,{_VALUE_COLUMN}",
            "$limit": str(_LIMIT),
        },
        timeout=timeout,
    )
    response.raise_for_status()
    raw = pd.DataFrame(response.json())

    raw["location"] = raw["jurisdiction"].map(
        lambda j: fips_for_nhsn_jurisdiction(j, locations_csv)
    )
    frame = raw.dropna(subset=["location"]).copy()
    frame["date"] = pd.to_datetime(frame["weekendingdate"])
    frame["value"] = pd.to_numeric(frame[_VALUE_COLUMN])
    frame = (
        frame.loc[:, ["date", "location", "value"]]
        .dropna(subset=["value"])  # early voluntary-reporting era has gaps
        .sort_values(["location", "date"])
        .reset_index(drop=True)
    )
    return frame
