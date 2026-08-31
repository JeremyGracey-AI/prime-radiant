"""Golden regression: the committed replica submission must be exactly reproducible.

Also the determinism quality gate across sessions: same vintage + same reference
date -> identical submission (seeded numpy stream keyed on reference date).
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.data.benchmarks import fetch_model_output
from prime_radiant.epi.data.hub import ensure_hub_clone
from prime_radiant.epi.replication import fingerprint_vintage, replica_submission

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).parents[2]
HUB_DIR = REPO_ROOT / "data" / "hub"
VINTAGE_CACHE = REPO_ROOT / "data" / "vintage_cache"
BENCHMARK_CACHE = REPO_ROOT / "data" / "benchmarks"
GOLDEN = REPO_ROOT / "tests" / "golden" / "2024-11-23-prime-radiant-replica.csv"
REFERENCE = date(2024, 11, 23)


def test_replica_reproduces_committed_golden_exactly() -> None:
    ensure_hub_clone(HUB_DIR)
    official = fetch_model_output("FluSight-baseline", REFERENCE, cache_dir=BENCHMARK_CACHE)
    vintage = fingerprint_vintage(HUB_DIR, REFERENCE, official, VINTAGE_CACHE)
    replica = replica_submission(vintage, REFERENCE)

    fresh = replica.copy()
    fresh["reference_date"] = fresh["reference_date"].dt.date.astype(str)
    fresh["target_end_date"] = fresh["target_end_date"].dt.date.astype(str)

    committed = pd.read_csv(GOLDEN, dtype={"location": str}, parse_dates=False)
    pd.testing.assert_frame_equal(
        fresh.reset_index(drop=True), committed.reset_index(drop=True), check_dtype=False
    )
