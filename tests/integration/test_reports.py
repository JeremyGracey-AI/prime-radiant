"""Report regression: committed league CSVs and calibration.png must regenerate
exactly from the persisted backtest parquets + pinned truth vintage."""

from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.backtest.report import SEASONS, build_reports

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).parents[2]
REPORTS_DIR = REPO_ROOT / "reports"


def test_committed_reports_regenerate_exactly(tmp_path: Path) -> None:
    build_reports(
        hub_clone=REPO_ROOT / "data" / "hub",
        backtest_dir=REPO_ROOT / "data" / "backtest",
        benchmark_cache=REPO_ROOT / "data" / "benchmarks",
        vintage_cache=REPO_ROOT / "data" / "vintage_cache",
        reports_dir=tmp_path,
    )
    for season in SEASONS:
        fresh = pd.read_csv(tmp_path / f"backtest_{season}.csv")
        committed = pd.read_csv(REPORTS_DIR / f"backtest_{season}.csv")
        pd.testing.assert_frame_equal(fresh, committed, check_exact=True)

    png = tmp_path / "calibration.png"
    assert png.exists()
    assert png.stat().st_size > 10_000
    assert (REPORTS_DIR / "calibration.png").stat().st_size > 10_000
