"""Honest backtest reports: league tables + calibration curves.

Column vocabulary copied from the official FluSight evaluation surface
(hubPredEvalsData scores.csv): model_id, wis, wis_scaled_relative_skill,
ae_median(+_scaled_relative_skill), interval_coverage_50/95, n — with __log
variants for the log(x+1) scale (interval coverage is transform-invariant and
appears once).

Relative skill is computed on the COMMON task intersection across all reported
models, where the official pairwise scaled relative skill provably collapses to
the plain mean-WIS ratio vs FluSight-baseline — so the official column name is
exactly earned. n and n_relative are both disclosed.

Truth is pinned to a fixed as-of date (stamped in every row) so regeneration
stays byte-stable when the hub resumes committing.
"""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from prime_radiant.epi.data.benchmarks import fetch_model_output, list_reference_dates
from prime_radiant.epi.data.vintages import as_of
from prime_radiant.eval.scoring import score_quantile_frame
from prime_radiant.eval.wis import interval_coverage

TRUTH_AS_OF = date(2026, 7, 9)  # the clone's last target-data commit at build time
RELATIVE_REFERENCE = "FluSight-baseline"
SCORED_HORIZONS = (0, 1, 2, 3)
COVERAGE_WIDTHS_11 = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98)

SEASONS: dict[str, tuple[date, date, tuple[str, str]]] = {
    "2023-24": (date(2023, 10, 14), date(2024, 5, 4), ("2023-1", "2024-0")),
    "2024-25": (date(2024, 11, 23), date(2025, 5, 31), ("2024-1", "2025-0")),
    "2025-26": (date(2025, 11, 22), date(2026, 5, 30), ("2025-1", "2026-0")),
}

_TASK_KEYS = ["location", "target_end_date", "horizon"]


def _observed_lookup(truth: pd.DataFrame) -> pd.DataFrame:
    return (
        truth.dropna(subset=["value"])
        .rename(columns={"date": "target_end_date", "value": "observed"})
        .loc[:, ["location", "target_end_date", "observed"]]
    )


def coverage_curve(
    forecasts: pd.DataFrame, truth: pd.DataFrame, widths: tuple[float, ...]
) -> pd.DataFrame:
    """Empirical central-interval coverage vs nominal width, over scored tasks."""
    merged = forecasts.merge(_observed_lookup(truth), on=["location", "target_end_date"])
    records = []
    for width in widths:
        covered = 0
        total = 0
        for _, group in merged.groupby(_TASK_KEYS, sort=False):
            ordered = group.sort_values("output_type_id")
            try:
                hit = interval_coverage(
                    ordered["output_type_id"].to_numpy(float),
                    ordered["value"].to_numpy(float),
                    float(ordered["observed"].iloc[0]),
                    width=width,
                )
            except ValueError:
                continue  # levels for this width not submitted by this model
            total += 1
            covered += int(hit)
        records.append(
            {"nominal": width, "empirical": covered / total if total else np.nan, "n": total}
        )
    return pd.DataFrame.from_records(records)


def _coverage_rate(scored_tasks: pd.DataFrame, forecasts: pd.DataFrame, width: float) -> float:
    merged = forecasts.merge(
        scored_tasks.loc[:, [*_TASK_KEYS, "observed"]], on=_TASK_KEYS, how="inner"
    )
    covered = []
    for _, group in merged.groupby(_TASK_KEYS, sort=False):
        ordered = group.sort_values("output_type_id")
        try:
            covered.append(
                interval_coverage(
                    ordered["output_type_id"].to_numpy(float),
                    ordered["value"].to_numpy(float),
                    float(ordered["observed"].iloc[0]),
                    width=width,
                )
            )
        except ValueError:
            # a model that does not submit the levels for this width gets NaN,
            # not a crash — honest blanks in the league table
            return float("nan")
    return float(np.mean(covered)) if covered else float("nan")


def league_rows(
    forecast_frames: dict[str, pd.DataFrame],
    truth: pd.DataFrame,
    season: str,
    truth_as_of: str,
) -> pd.DataFrame:
    """One row per model per horizon-slice ('all' plus each scored horizon)."""
    scored = {
        model: {
            "natural": score_quantile_frame(frame, truth),
            "log": score_quantile_frame(frame, truth, scale="log"),
        }
        for model, frame in forecast_frames.items()
    }

    # common task intersection across ALL models -> relative columns
    common: pd.DataFrame | None = None
    for tables in scored.values():
        keys = tables["natural"].loc[:, _TASK_KEYS]
        common = keys if common is None else common.merge(keys, on=_TASK_KEYS)
    assert common is not None

    def _slice(frame: pd.DataFrame, horizon: int | str) -> pd.DataFrame:
        if horizon == "all":
            return frame
        return frame.loc[frame["horizon"] == horizon]

    records = []
    horizons: list[int | str] = ["all", *SCORED_HORIZONS]
    for model, tables in scored.items():
        natural, logged = tables["natural"], tables["log"]
        natural_common = natural.merge(common, on=_TASK_KEYS)
        logged_common = logged.merge(common, on=_TASK_KEYS)
        reference_natural = scored[RELATIVE_REFERENCE]["natural"].merge(common, on=_TASK_KEYS)
        reference_logged = scored[RELATIVE_REFERENCE]["log"].merge(common, on=_TASK_KEYS)

        for horizon in horizons:
            n_all = len(_slice(natural, horizon))
            n_rel = len(_slice(natural_common, horizon))
            record = {
                "season": season,
                "model_id": model,
                "horizon": horizon,
                "n": n_all,
                "n_relative": n_rel,
                "truth_as_of": truth_as_of,
                "wis": _slice(natural, horizon)["wis"].mean(),
                "ae_median": _slice(natural, horizon)["ae_median"].mean(),
                "wis__log": _slice(logged, horizon)["wis"].mean(),
                "ae_median__log": _slice(logged, horizon)["ae_median"].mean(),
                "wis_scaled_relative_skill": (
                    _slice(natural_common, horizon)["wis"].mean()
                    / _slice(reference_natural, horizon)["wis"].mean()
                ),
                "wis_scaled_relative_skill__log": (
                    _slice(logged_common, horizon)["wis"].mean()
                    / _slice(reference_logged, horizon)["wis"].mean()
                ),
                "ae_median_scaled_relative_skill": (
                    _slice(natural_common, horizon)["ae_median"].mean()
                    / _slice(reference_natural, horizon)["ae_median"].mean()
                ),
                "interval_coverage_50": _coverage_rate(
                    _slice(natural, horizon), forecast_frames[model], 0.5
                ),
                "interval_coverage_95": _coverage_rate(
                    _slice(natural, horizon), forecast_frames[model], 0.95
                ),
            }
            records.append(record)
    return pd.DataFrame.from_records(records)


def render_calibration_png(
    season_curves: dict[str, dict[str, pd.DataFrame]],
    lgbm_by_horizon: dict[int, pd.DataFrame],
    out_path: Path,
) -> None:
    """Coverage-vs-nominal panels per season + a per-horizon panel for our lgbm."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n_panels = len(season_curves) + 1
    n_cols = 2
    n_rows = (n_panels + 1) // 2
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(11, 4.6 * n_rows))
    flat_axes = np.array(axes).flatten()

    for ax, (season, curves) in zip(flat_axes, season_curves.items(), strict=False):
        for model, curve in curves.items():
            ax.plot(curve["nominal"] * 100, curve["empirical"] * 100, marker="o", label=model)
        ax.plot([0, 100], [0, 100], linestyle="--", color="grey", linewidth=1)
        n = int(curves[next(iter(curves))]["n"].iloc[0]) if curves else 0
        ax.set_title(f"{season} (n={n} tasks)")
        ax.set_xlabel("Nominal central interval (%)")
        ax.set_ylabel("Empirical coverage (%)")
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.legend(fontsize=7)

    ax = flat_axes[len(season_curves)]
    for horizon, curve in lgbm_by_horizon.items():
        ax.plot(curve["nominal"] * 100, curve["empirical"] * 100, marker="o", label=f"h={horizon}")
    ax.plot([0, 100], [0, 100], linestyle="--", color="grey", linewidth=1)
    ax.set_title("prime-radiant lgbm, by horizon (all seasons)")
    ax.set_xlabel("Nominal central interval (%)")
    ax.set_ylabel("Empirical coverage (%)")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.legend(fontsize=7)

    for extra_ax in flat_axes[n_panels:]:
        extra_ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def season_forecast_frames(  # pragma: no cover — S3/parquet IO; integration-tested
    season: str, backtest_dir: Path, benchmark_cache: Path
) -> dict[str, pd.DataFrame]:
    start, end, prefixes = SEASONS[season]
    origins = sorted(
        d
        for p in prefixes
        for d in list_reference_dates(RELATIVE_REFERENCE, p)
        if start <= d <= end
    )
    frames: dict[str, pd.DataFrame] = {}
    for official in ("FluSight-baseline", "FluSight-ensemble", "UMass-flusion"):
        parts = []
        for origin in origins:
            try:
                parts.append(fetch_model_output(official, origin, cache_dir=benchmark_cache))
            except Exception:  # missing weeks (verified: 2025-04-26, 2026-01-17 for UMass)
                continue
        frames[official] = pd.concat(parts, ignore_index=True)
    for ours in ("lgbm", "ensemble", "baseline"):
        paths = sorted((backtest_dir / ours).glob("*.parquet"))
        parts = [
            pd.read_parquet(path) for path in paths if start <= date.fromisoformat(path.stem) <= end
        ]
        frames[f"prime-radiant-{ours}"] = pd.concat(parts, ignore_index=True)
    for model, frame in frames.items():
        frames[model] = frame.loc[frame["horizon"].isin(SCORED_HORIZONS)].copy()
    return frames


def build_reports(  # pragma: no cover — orchestration over IO; integration-tested
    hub_clone: Path,
    backtest_dir: Path,
    benchmark_cache: Path,
    vintage_cache: Path,
    reports_dir: Path,
) -> None:
    truth = as_of(hub_clone, TRUTH_AS_OF, cache_dir=vintage_cache)
    reports_dir.mkdir(parents=True, exist_ok=True)

    season_curves: dict[str, dict[str, pd.DataFrame]] = {}
    lgbm_scored_frames: list[pd.DataFrame] = []
    for season in SEASONS:
        frames = season_forecast_frames(season, backtest_dir, benchmark_cache)
        rows = league_rows(frames, truth, season, TRUTH_AS_OF.isoformat())
        rows = rows.sort_values(["horizon", "wis"], key=lambda s: s.astype(str))
        rows.to_csv(reports_dir / f"backtest_{season}.csv", index=False, float_format="%.6f")

        season_curves[season] = {
            model: coverage_curve(frame, truth, COVERAGE_WIDTHS_11)
            for model, frame in frames.items()
        }
        lgbm_scored_frames.append(frames["prime-radiant-lgbm"])

    pooled_lgbm = pd.concat(lgbm_scored_frames, ignore_index=True)
    lgbm_by_horizon = {
        horizon: coverage_curve(
            pooled_lgbm.loc[pooled_lgbm["horizon"] == horizon], truth, COVERAGE_WIDTHS_11
        )
        for horizon in SCORED_HORIZONS
    }
    render_calibration_png(season_curves, lgbm_by_horizon, reports_dir / "calibration.png")
