"""League-table assembly and calibration-curve math (offline, synthetic)."""

from pathlib import Path

import pandas as pd
import pytest

from prime_radiant.epi.backtest.report import (
    coverage_curve,
    league_rows,
    render_calibration_png,
)

pytestmark = pytest.mark.unit


def _forecast_frame(
    shift: float = 0.0, teds: tuple[str, ...] = ("2025-12-06", "2025-12-13")
) -> pd.DataFrame:
    # Tasks at `teds`; central 50% interval = (10, 20) around median 15 (+shift).
    rows = []
    for ted in teds:
        for level, value in (
            (0.05, 5.0),
            (0.25, 10.0),
            (0.5, 15.0),
            (0.75, 20.0),
            (0.95, 30.0),
        ):
            rows.append(
                {
                    "location": "US",
                    "horizon": 0,
                    "target_end_date": pd.Timestamp(ted),
                    "output_type_id": level,
                    "value": value + shift,
                }
            )
    return pd.DataFrame(rows)


def _truth() -> pd.DataFrame:
    # First observation (16) inside the (10,20) interval, second far outside.
    # 16, not the median 15: an exact-median observation makes ae_median 0 and
    # the baseline-relative ae column 0/0.
    return pd.DataFrame(
        {
            "date": [
                pd.Timestamp("2025-12-06"),
                pd.Timestamp("2025-12-13"),
                pd.Timestamp("2025-12-20"),
            ],
            "location": ["US", "US", "US"],
            "value": [16.0, 100.0, 40.0],
        }
    )


class TestCoverageCurve:
    def test_hand_computed_coverage(self) -> None:
        curve = coverage_curve(_forecast_frame(), _truth(), widths=(0.5,))
        assert len(curve) == 1
        row = curve.iloc[0]
        assert row["nominal"] == 0.5
        assert row["empirical"] == pytest.approx(0.5)  # 1 of 2 tasks covered
        assert row["n"] == 2


class TestLeagueRows:
    def test_relative_skill_on_common_tasks(self) -> None:
        # PARTIALLY-OVERLAPPING task sets, neither containing the other:
        # baseline covers {A,B}, ours covers {B,C}, intersection = {B}. This
        # kills BOTH demonstrated mutant families: per-model-own-tasks (ours
        # n_relative would be 2) and keep-last-model-keys (also 2). The first
        # rebuild of this test used a CONTAINED subset and the last-keys mutant
        # accidentally computed the correct intersection — verified empirically.
        truth = _truth()
        frames = {
            "FluSight-baseline": _forecast_frame(teds=("2025-12-06", "2025-12-13")),
            "our-model": _forecast_frame(shift=5.0, teds=("2025-12-13", "2025-12-20")),
        }
        rows = league_rows(frames, truth, season="2025-26", truth_as_of="2026-07-09")
        table = rows.set_index(["model_id", "horizon"])
        base = table.loc[("FluSight-baseline", "all")]
        ours = table.loc[("our-model", "all")]
        assert base["n"] == 2 and ours["n"] == 2
        assert base["n_relative"] == 1 and ours["n_relative"] == 1  # exactly {B}
        assert base["wis_scaled_relative_skill"] == pytest.approx(1.0)

        # expected ratio on the intersection ONLY (task B = 2025-12-13),
        # recomputed independently on truth restricted to that task
        restricted_truth = truth.loc[truth["date"] == pd.Timestamp("2025-12-13")]
        single = league_rows(frames, restricted_truth, season="s", truth_as_of="x").set_index(
            ["model_id", "horizon"]
        )
        expected_ratio = (
            single.loc[("our-model", "all"), "wis"]
            / single.loc[("FluSight-baseline", "all"), "wis"]
        )
        assert ours["wis_scaled_relative_skill"] == pytest.approx(expected_ratio)
        # full-set means differ from intersection means on both sides
        assert ours["wis_scaled_relative_skill"] != pytest.approx(ours["wis"] / base["wis"])
        assert set(rows["truth_as_of"]) == {"2026-07-09"}

    def test_log_columns_present_and_distinct(self) -> None:
        frames = {"FluSight-baseline": _forecast_frame(), "m": _forecast_frame(shift=3.0)}
        rows = league_rows(frames, _truth(), season="s", truth_as_of="x")
        assert {"wis__log", "ae_median__log", "wis_scaled_relative_skill__log"} <= set(rows.columns)
        row = rows.set_index(["model_id", "horizon"]).loc[("m", "all")]
        assert row["wis__log"] != pytest.approx(row["wis"])


class TestRenderCalibrationPng:
    def test_renders_headless_nontrivial_png(self, tmp_path: Path) -> None:
        curves = {"2025-26": {"m1": coverage_curve(_forecast_frame(), _truth(), widths=(0.5, 0.9))}}
        by_horizon = {0: coverage_curve(_forecast_frame(), _truth(), widths=(0.5, 0.9))}
        out = tmp_path / "calibration.png"
        render_calibration_png(curves, by_horizon, out)
        assert out.exists()
        # The old >10KB bar was vacuous — an EMPTY figure exceeds it (adversarial
        # finding; ~47KB measured). Honest unit check: render an empty figure at
        # the same geometry and require the real one to carry more ink. The
        # integration test holds the full-data plot to an absolute 150KB bar.
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, _axes = plt.subplots(2, 2, figsize=(11, 9.2))
        empty = tmp_path / "empty.png"
        fig.tight_layout()
        fig.savefig(empty, dpi=150)
        plt.close(fig)
        assert out.stat().st_size > 1.2 * empty.stat().st_size
