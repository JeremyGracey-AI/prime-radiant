# Model card — JGracey-prime_radiant

## Summary

Quantile forecasts of weekly confirmed-influenza hospital admissions for the
US and its states/territories, in the CDC
[FluSight](https://github.com/cdcepi/FluSight-forecast-hub) format: 23 quantile
levels, horizons 0–3 weeks, reference dates on Saturdays. The submitted model
is an **ensemble**: the per-quantile median of a pooled LightGBM quantile
regressor and a validated replica of FluSight-baseline.

## Intended use

Research and public-health situational awareness via the FluSight hub and the
[dashboard](https://huggingface.co/spaces/jeremygracey-ai/prime-radiant).
Not a clinical decision tool; forecasts carry wide, honestly-quantified
uncertainty and should be read through their intervals, never their medians
alone.

## Architecture

- **LightGBM component** — one booster per quantile level (23), trained jointly
  across all locations with horizon as a feature, predicting the *change* in
  4th-root per-100k admission rates. Per-location scale/center statistics are
  fitted per forecast origin from as-of data only. Post-processing sorts
  quantiles in transformed space, inverts, clips at zero, and rounds integers
  at the submission boundary. `lightgbm==4.7.0` exact-pinned: its determinism
  is binary-scoped.
- **Baseline component** — a replica of FluSight-baseline, cross-validated
  against the official implementation to a season relative WIS of 0.999989 on
  fingerprint-matched vintages.
- **Ensemble** — per-quantile median of the two.

## Data

NHSN weekly confirmed-flu hospital admissions, read exclusively through the
FluSight hub's `target-data/` **git history as a vintage store**: training,
scoring, and anchoring never see data committed after the forecast origin.
Population denominators come from the hub's season-correct `auxiliary-data`
snapshots. No other data sources, no LLM calls, ≈$0 compute.

## Evaluation

Rolling-origin backtests over three seasons (2023-24, 2024-25, 2025-26),
scored with WIS on natural and log(x+1) scales against a truth vintage pinned
to a stated as-of date; relative skill is computed on the common task
intersection vs FluSight-baseline. Full league tables: `reports/backtest_*.csv`.

| Season | ensemble rel. WIS | lgbm rel. WIS | Best official comparator |
|---|---|---|---|
| 2023-24 | loses to UMass-flusion | loses | UMass-flusion |
| 2024-25 | loses to UMass-flusion | loses | UMass-flusion |
| 2025-26 | competitive | **0.609 (wins)** | UMass-flusion 0.625 |

## Known limitations (stated, not hidden)

- **Interval under-coverage**: the LightGBM model's 50% intervals empirically
  cover ~34–40% of observations, worsening with horizon. Season-bagging is the
  sanctioned fix, deliberately parked.
- Single data source and single target; no rate-change/peak/ED-visit targets.
- 2022-23 is not backtestable (the hub's vintage history begins Oct 2023).
- The dashboard serves a frozen backtest bundle, not a live feed.

## Provenance

Built agent-assisted with Claude Code under human-gated go-live controls;
every phase adversarially verified. See `AI-USE.md` and `CONTRIBUTING.md`.
Accountable: Jeremy Gracey.
