"""Official model output from the FluSight hub's public S3 mirror.

Verified 2026-08-31: bucket cdcepi-flusight-forecast-hub (us-east-1) allows anonymous
plain-HTTPS GETs; files are parquet only and carry two extra columns (round_id,
model_id) plus sample-trajectory rows beyond the hubverse submission columns.
2024-25 season: 27 weekly files each for FluSight-baseline and FluSight-ensemble,
26 for UMass-flusion (2025-01-25 missing for all; 2025-04-26 also for UMass-flusion).
"""

import io
from datetime import date
from pathlib import Path

import httpx
import pandas as pd

BUCKET_URL = "https://cdcepi-flusight-forecast-hub.s3.amazonaws.com"

_SUBMISSION_COLUMNS = [
    "reference_date",
    "target",
    "horizon",
    "target_end_date",
    "location",
    "output_type",
    "output_type_id",
    "value",
]


def normalize_model_output(raw: pd.DataFrame) -> pd.DataFrame:
    """Mirror parquet -> our 8-column quantile frame (SubmissionSchema-shaped)."""
    frame = raw.loc[raw["output_type"] == "quantile"].copy()
    frame["output_type_id"] = frame["output_type_id"].astype(float)
    frame["reference_date"] = pd.to_datetime(frame["reference_date"])
    frame["target_end_date"] = pd.to_datetime(frame["target_end_date"])
    return frame.loc[:, _SUBMISSION_COLUMNS].reset_index(drop=True)


def fetch_model_output(  # pragma: no cover — network; exercised by integration tests
    model: str,
    reference_date: date,
    cache_dir: Path | None = None,
    timeout: float = 60.0,
) -> pd.DataFrame:
    """Download one official weekly file (anonymous), normalized; parquet-cached."""
    name = f"{reference_date.isoformat()}-{model}.parquet"
    if cache_dir is not None:
        cache_path = cache_dir / model / name
        if cache_path.exists():
            return normalize_model_output(pd.read_parquet(cache_path))

    url = f"{BUCKET_URL}/model-output/{model}/{name}"
    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()
    raw = pd.read_parquet(io.BytesIO(response.content))

    if cache_dir is not None:
        cache_path = cache_dir / model / name
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        raw.to_parquet(cache_path)
    return normalize_model_output(raw)


def list_reference_dates(  # pragma: no cover — network; exercised by integration tests
    model: str, year_prefix: str, timeout: float = 60.0
) -> list[date]:
    """Reference dates with a file for `model`, via anonymous ListObjectsV2."""
    url = f"{BUCKET_URL}/?list-type=2&prefix=model-output/{model}/{year_prefix}&max-keys=1000"
    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()
    dates: list[date] = []
    for chunk in response.text.split("<Key>")[1:]:
        key = chunk.split("</Key>")[0]
        stem = key.rsplit("/", 1)[-1]
        dates.append(date.fromisoformat(stem[:10]))
    return sorted(dates)
