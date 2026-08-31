"""Official-baseline replication utilities: vintage fingerprinting + replica runs.

Used by the Phase B cross-validation and the Phase D backtests. The fingerprint
trick: an official file's horizon -1 rows are degenerate (all quantiles equal the
last observed value per location), so they identify the exact target-data vintage
the official Wednesday run saw — no guessing about run-time data availability.
"""
# pragma-no-cover rationale: these paths need the real hub clone + S3 files, so
# they are exercised by the integration suite, not the offline coverage run.

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from prime_radiant.epi.data.vintages import VintageNotFoundError, as_of, resolve_vintage
from prime_radiant.epi.models.baseline import flusight_baseline
from prime_radiant.epi.submission.format import build_submission_frame


def official_last_values(official: pd.DataFrame) -> pd.Series:  # pragma: no cover
    medians = official.loc[
        (official["horizon"] == -1) & (official["output_type_id"] == 0.5),
        ["location", "value"],
    ]
    series = pd.Series(medians["value"].to_numpy(), index=pd.Index(medians["location"]))
    return series.sort_index()


def fingerprint_vintage(  # pragma: no cover
    hub_clone: Path,
    reference_date: date,
    official: pd.DataFrame,
    vintage_cache: Path | None = None,
) -> pd.DataFrame:
    """The as-of vintage whose per-location last values match the official h=-1 rows."""
    target = official_last_values(official)
    cutoff = pd.Timestamp(reference_date) - pd.Timedelta(days=7)
    seen: set[str] = set()
    for days_back in (3, 2, 4, 1, 5, 0, 6, 7, 8, 9):
        candidate = reference_date - timedelta(days=days_back)
        try:
            vintage = resolve_vintage(hub_clone, candidate)
        except VintageNotFoundError:
            continue
        if vintage.sha in seen:
            continue
        seen.add(vintage.sha)
        frame = as_of(hub_clone, candidate, cache_dir=vintage_cache)
        window = frame.loc[frame["date"] <= cutoff].dropna(subset=["value"])
        last = (
            window.sort_values("date").groupby("location")["value"].last().round().astype(int)
        ).sort_index()
        shared = target.index.intersection(last.index)
        if len(shared) == len(target) and (last.loc[shared] == target).all():
            return frame
    raise LookupError(
        f"no candidate vintage matches official h=-1 fingerprint for {reference_date}"
    )


def replica_submission(  # pragma: no cover
    vintage: pd.DataFrame, reference_date: date
) -> pd.DataFrame:
    history = vintage.loc[:, ["date", "location", "value"]]
    return build_submission_frame(flusight_baseline(history, reference_date), reference_date)
