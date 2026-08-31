"""Phase B done condition: our WIS scores the official FluSight-baseline output and
our replica within tolerance of each other on 2024-25 — validating both at once.

Vintage fingerprinting (epi/replication.py): each official file's horizon -1 rows
identify the exact target-data vintage the official Wednesday run saw; the replica
is fed THAT vintage, making horizon-0 comparison exact-match-up-to-rounding and the
season WIS ratio a tight cross-validation.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.data.benchmarks import fetch_model_output, list_reference_dates
from prime_radiant.epi.data.hub import TARGET_FILE, ensure_hub_clone, load_target_data
from prime_radiant.epi.replication import fingerprint_vintage, replica_submission
from prime_radiant.eval.scoring import mean_wis, score_quantile_frame
from prime_radiant.eval.wis import relative_wis

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).parents[2]
HUB_DIR = REPO_ROOT / "data" / "hub"
VINTAGE_CACHE = REPO_ROOT / "data" / "vintage_cache"
BENCHMARK_CACHE = REPO_ROOT / "data" / "benchmarks"

SEASON_START = date(2024, 11, 23)
SEASON_END = date(2025, 5, 31)
SCORED_HORIZONS = (0, 1, 2, 3)  # horizon -1 is submitted but not scored


@pytest.fixture(scope="module")
def hub_clone() -> Path:
    return ensure_hub_clone(HUB_DIR)


@pytest.fixture(scope="module")
def season_dates() -> list[date]:
    dates = [
        d
        for prefix in ("2024-1", "2025-0")
        for d in list_reference_dates("FluSight-baseline", prefix)
    ]
    return sorted(d for d in dates if SEASON_START <= d <= SEASON_END)


@pytest.fixture(scope="module")
def truth(hub_clone: Path) -> pd.DataFrame:
    return load_target_data(hub_clone / TARGET_FILE)


def _replica_for(hub_clone: Path, reference_date: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    official = fetch_model_output("FluSight-baseline", reference_date, cache_dir=BENCHMARK_CACHE)
    vintage = fingerprint_vintage(hub_clone, reference_date, official, VINTAGE_CACHE)
    return official, replica_submission(vintage, reference_date)


class TestScorerAndReplicaCrossValidation:
    def test_horizon_zero_exact_match_on_spot_weeks(
        self, hub_clone: Path, season_dates: list[date]
    ) -> None:
        spots = [season_dates[0], season_dates[len(season_dates) // 2], season_dates[-1]]
        for reference_date in spots:
            official, replica = _replica_for(hub_clone, reference_date)
            keys = ["location", "output_type_id"]
            ours = replica[replica["horizon"] == 0].set_index(keys)["value"].sort_index()
            theirs = official[official["horizon"] == 0].set_index(keys)["value"].sort_index()
            # Exact up to cross-language float rounding: R and numpy disagree by
            # ~1e-12 on interpolated quantiles, and floor/ceil amplifies that to
            # exactly +-1 at integer boundaries (diagnosed 2026-08-31: raw
            # 3302.0000000000005 vs R's 3302.0, and 140.0 vs R's 140.000...1).
            # Bar calibrated by the adversarial full-season sweep: worst date
            # 2025-02-15 at 1.07% off-by-1, every breaching cell within 6e-14 of
            # an integer. Real algorithm defects measure 40%+ (perturbing the
            # window/pause constants broke 500+/1219 cells), so 2% separates
            # noise from defect with an order of magnitude on each side.
            # Beyond +-1 is always a real defect.
            deltas = (ours - theirs).abs()
            assert int((deltas > 1).sum()) == 0, (
                f"{reference_date}: differences beyond +-1 at {deltas[deltas > 1].index.tolist()}"
            )
            mismatch_rate = float((deltas == 1).mean())
            assert mismatch_rate <= 0.02, (
                f"{reference_date}: {mismatch_rate:.2%} of horizon-0 values off by 1 "
                "(float-boundary noise peaked at 1.07% across 2024-25)"
            )

    def test_season_wis_ratio_within_tolerance(
        self, hub_clone: Path, season_dates: list[date], truth: pd.DataFrame
    ) -> None:
        official_scores: list[pd.DataFrame] = []
        replica_scores: list[pd.DataFrame] = []
        task_keys = ["location", "target_end_date", "horizon"]
        for reference_date in season_dates:
            official, replica = _replica_for(hub_clone, reference_date)
            official = official.loc[official["horizon"].isin(SCORED_HORIZONS)]
            replica = replica.loc[replica["horizon"].isin(SCORED_HORIZONS)]

            scored_official = score_quantile_frame(official, truth)
            scored_replica = score_quantile_frame(replica, truth)
            # identical task sets on both sides, always
            scored_official_shared = scored_official.merge(
                scored_replica.loc[:, task_keys], on=task_keys
            )
            scored_replica_shared = scored_replica.merge(
                scored_official.loc[:, task_keys], on=task_keys
            )
            official_scores.append(scored_official_shared)
            replica_scores.append(scored_replica_shared)

        all_official = pd.concat(official_scores, ignore_index=True)
        all_replica = pd.concat(replica_scores, ignore_index=True)
        assert len(all_official) == len(all_replica) > 4000

        ratio = relative_wis(all_replica["wis"].to_numpy(), all_official["wis"].to_numpy())
        assert 0.95 <= ratio <= 1.05, (
            f"replica/official season WIS ratio {ratio:.4f} "
            f"(replica {mean_wis(all_replica):.3f} vs official {mean_wis(all_official):.3f})"
        )
