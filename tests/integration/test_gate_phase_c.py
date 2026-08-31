"""Phase C gate: relative WIS < 1.0 vs the OFFICIAL FluSight-baseline on two
retrospective seasons (2024-25, 2025-26), horizons 0-3, vintage data.

Forecast frames are parquet-persisted under data/backtest/ — the first run trains
~23 boosters x ~54 origins (tens of minutes); warm reruns score in seconds.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.backtest.rolling import run_backtest
from prime_radiant.epi.data.benchmarks import fetch_model_output, list_reference_dates
from prime_radiant.epi.data.hub import TARGET_FILE, ensure_hub_clone, load_target_data
from prime_radiant.eval.scoring import score_quantile_frame
from prime_radiant.eval.wis import relative_wis

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).parents[2]
HUB_DIR = REPO_ROOT / "data" / "hub"
VINTAGE_CACHE = REPO_ROOT / "data" / "vintage_cache"
BENCHMARK_CACHE = REPO_ROOT / "data" / "benchmarks"
BACKTEST_DIR = REPO_ROOT / "data" / "backtest"
LOCATIONS_CSV = REPO_ROOT / "tests" / "fixtures" / "locations.csv"

SEASONS = {
    "2024-25": (date(2024, 11, 23), date(2025, 5, 31), ("2024-1", "2025-0")),
    "2025-26": (date(2025, 11, 22), date(2026, 5, 30), ("2025-1", "2026-0")),
}
SCORED_HORIZONS = (0, 1, 2, 3)
TASK_KEYS = ["location", "target_end_date", "horizon"]


def _season_origins(prefixes: tuple[str, str], start: date, end: date) -> list[date]:
    dates = [d for p in prefixes for d in list_reference_dates("FluSight-baseline", p)]
    return sorted(d for d in set(dates) if start <= d <= end)


@pytest.fixture(scope="module")
def truth() -> pd.DataFrame:
    ensure_hub_clone(HUB_DIR)
    return load_target_data(HUB_DIR / TARGET_FILE)


class TestPhaseCGate:
    def test_relative_wis_beats_official_baseline_on_two_seasons(self, truth: pd.DataFrame) -> None:
        verdicts: dict[str, dict[str, float]] = {}
        for season, (start, end, prefixes) in SEASONS.items():
            origins = _season_origins(prefixes, start, end)
            assert len(origins) >= 25, f"{season}: only {len(origins)} origins found"

            ours = run_backtest(HUB_DIR, origins, LOCATIONS_CSV, BACKTEST_DIR, VINTAGE_CACHE)
            official = pd.concat(
                [
                    fetch_model_output("FluSight-baseline", origin, cache_dir=BENCHMARK_CACHE)
                    for origin in origins
                ],
                ignore_index=True,
            )
            official = official.loc[official["horizon"].isin(SCORED_HORIZONS)]

            scored_official = score_quantile_frame(official, truth)
            ratios: dict[str, float] = {}
            for model in ("lgbm", "ensemble"):
                frame = ours[model]
                frame = frame.loc[frame["horizon"].isin(SCORED_HORIZONS)]
                scored_model = score_quantile_frame(frame, truth)
                shared_official = scored_official.merge(
                    scored_model.loc[:, TASK_KEYS], on=TASK_KEYS
                )
                shared_model = scored_model.merge(scored_official.loc[:, TASK_KEYS], on=TASK_KEYS)
                assert len(shared_model) == len(shared_official) > 3000
                ratios[model] = relative_wis(
                    shared_model["wis"].to_numpy(), shared_official["wis"].to_numpy()
                )
            verdicts[season] = ratios
            print(f"\n[gate] {season}: " + ", ".join(f"{m}={r:.4f}" for m, r in ratios.items()))

        for season, ratios in verdicts.items():
            best = min(ratios.values())
            assert best < 1.0, (
                f"{season}: neither model beats the official baseline "
                f"(lgbm={ratios['lgbm']:.4f}, ensemble={ratios['ensemble']:.4f})"
            )

        # Golden regression rule (brief quality gate 6): fail if any relative WIS
        # regresses more than 2% past the committed value.
        import json

        stored = json.loads((REPO_ROOT / "tests" / "golden" / "wis_baseline.json").read_text())
        stored_ratios = stored["phase_c"]["relative_wis_vs_official_baseline"]
        for season, ratios in verdicts.items():
            for model, ratio in ratios.items():
                ceiling = stored_ratios[season][model] * 1.02
                assert ratio <= ceiling + 1e-9, (
                    f"{season}/{model}: relative WIS {ratio:.4f} regressed past "
                    f"golden {stored_ratios[season][model]:.4f} (+2% = {ceiling:.4f})"
                )
