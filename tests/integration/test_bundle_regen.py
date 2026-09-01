"""Bundle regression: committed serve_data/ must regenerate exactly from the
persisted backtest parquets + pinned vintage + benchmark cache, and the pinned
vintage sha must still be what TRUTH_AS_OF resolves to on the live clone.

Also proves the cache-enumeration == S3-enumeration equivalence the offline
builder relies on: the benchmark cache must hold exactly the official files the
S3 mirror lists for each bundled season (the recorded weekly gaps included).
"""

from pathlib import Path

import pytest

from prime_radiant.epi.backtest.report import SEASONS, TRUTH_AS_OF
from prime_radiant.epi.data.benchmarks import list_reference_dates
from prime_radiant.epi.data.vintages import resolve_vintage
from prime_radiant.epi.serve.bundle import (
    OFFICIAL_MODELS,
    TRUTH_VINTAGE_SHA,
    build_bundle,
)

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).parents[2]
SERVE_DATA = REPO_ROOT / "serve_data"


def test_committed_bundle_regenerates_exactly(tmp_path: Path) -> None:
    fresh = build_bundle(
        backtest_dir=REPO_ROOT / "data" / "backtest",
        benchmark_cache=REPO_ROOT / "data" / "benchmarks",
        truth_parquet=REPO_ROOT
        / "data"
        / "vintage_cache"
        / f"{TRUTH_VINTAGE_SHA}--target-hospital-admissions.parquet",
        truth_vintage_sha=TRUTH_VINTAGE_SHA,
        reports_dir=REPO_ROOT / "reports",
        locations_csv=REPO_ROOT / "data" / "hub" / "auxiliary-data" / "locations.csv",
        out_dir=tmp_path / "serve_data",
    )
    fresh_files = sorted(p.relative_to(fresh) for p in fresh.rglob("*") if p.is_file())
    committed_files = sorted(
        p.relative_to(SERVE_DATA) for p in SERVE_DATA.rglob("*") if p.is_file()
    )
    assert fresh_files == committed_files
    for name in fresh_files:
        assert (fresh / name).read_bytes() == (SERVE_DATA / name).read_bytes(), name


def test_pinned_vintage_sha_matches_truth_as_of() -> None:
    vintage = resolve_vintage(REPO_ROOT / "data" / "hub", TRUTH_AS_OF)
    assert vintage.sha == TRUTH_VINTAGE_SHA


def test_benchmark_cache_enumeration_matches_s3() -> None:
    for model in OFFICIAL_MODELS:
        for season, (start, end, prefixes) in SEASONS.items():
            listed = {
                d
                for prefix in prefixes
                for d in list_reference_dates(model, prefix)
                if start <= d <= end
            }
            cached = {
                # stems are <YYYY-MM-DD>-<model>
                path.stem[:10]
                for path in (REPO_ROOT / "data" / "benchmarks" / model).glob("*.parquet")
                if start.isoformat() <= path.stem[:10] <= end.isoformat()
            }
            assert {d.isoformat() for d in listed} == cached, (model, season)
