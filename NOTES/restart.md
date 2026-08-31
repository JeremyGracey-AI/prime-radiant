# Current task

Phase 2 (FluSight epi forecaster) — Phase C: Model + ensemble. Brief: `HANDOFF_PHASE2.md`.

## Goal

LightGBM quantile model + per-quantile-median ensemble with the baseline replica.
Gate: relative WIS < 1.0 vs official FluSight-baseline on >=2 seasons, horizons 0-3,
vintage data.

## Current state

- **GATE PASSED, both seasons, both models:** 2024-25 lgbm 0.7958 / ensemble 0.8989;
  2025-26 lgbm 0.5915 / ensemble 0.7474 (relative WIS vs OFFICIAL baseline files,
  final truth, shared task sets). Goldens in tests/golden/wis_baseline.json with the
  <=2%-regression rule enforced by the gate test.
- done: lightgbm==4.7.0 exact pin (arm64 wheel; Homebrew libomp system dep — note
  for Phase G Docker/CI); native lgb.train, deterministic+force_row_wise+seed+
  num_threads=1; determinism verified empirically (identical reruns).
- done: epi/features/ — flusion-derived: 4th-root per-100k rate transform with
  per-location in-season 95th-pct scale/center (fitted PER ORIGIN <= cutoff; leakage
  property covers scaler + features), lags/diffs/rolling means/slopes, season_week/
  delta_xmas, pooled panel with one-hot location + log_pop + horizon-as-feature,
  delta targets, in-season weeks 5-45 training filter.
- done: epi/models/lgbm_quantile.py (23 boosters, post-hoc sort in transformed
  space, invert, clip; ints only at submission), ensemble.py (per-quantile median).
- done: epi/backtest/rolling.py — vintage anchor origin-3d (Wednesday), two-condition
  usability guard, parquet persistence under data/backtest (54 origins cached; full
  cold run ~4-6 min on this machine, warm reruns seconds).
- done: old-form vintage adapter in hub.py (2023-24 unlocked for Phase D).
- fixed en route: benchmarks normalizer now filters to the primary target — 2025-26
  official files carry a SECOND quantile target (prop ed visits) that doubled task
  groups; the adversarially-rebuilt WIS validation caught it as duplicate levels.
- 146 offline tests (cov 95.58%) + 6 integration green.
- done: adversarial verification (4 agents). Gate numbers reproduced to 4dp by an
  INDEPENDENT from-scratch scorer; task sets exact (full grid both sides); ensemble
  parquets exactly reproduce median+rounding at all 268,180 rows; all 55 origins
  resolved at the Wednesday anchor (fallback never fired); contamination tests
  byte-identical; one origin retrained bit-for-bit. Best finding: the gate is
  CONSERVATIVE — 3 holiday-week 2024-25 origins gave the official run fresher
  (Thursday+) data than our live-Wednesday vintage; info-equal subset: lgbm 0.7311,
  ensemble 0.8222 (documented in wis_baseline.json). Fixed from findings: vacuous
  crossing test replaced with a self-validating fixture (raw boosters provably
  cross; deleting the sort now fails tests — previously 210/212 real tasks would
  cross undetected); vintage fallback made strictly-earlier-only.

## Verify

`make check` (offline) · `make test-integration` (network; ~40s warm)

## Stated gaps (Phase D items)

- Population table is the one non-vintaged input (current census vs 2024-25
  snapshot: 53/53 rows differ, mean +1.27%): no outcome signal, forward/inverse
  cancel, but vintage locations.csv properly in Phase D.
- libomp is a Homebrew system dep for lightgbm — Docker/CI legs (Phase G).
- vintage_is_usable passes negative staleness (future-dated rows) — harmless,
  double-covered by downstream cutoff filters; tighten if Phase D touches it.

## Blockers

- None. Fingerprinting resolved the vintage-anchor problem (Saturday as_of is ~3 days
  late vs the official Wednesday run; hub commits land Wed/Thu).

## Notes / gaps

- Replica horizons ≥1 cannot be bit-exact vs official (R RNG); validated via season
  WIS ratio instead — landed at 0.999989.
- Official "relative WIS" is the pairwise geometric-mean variant; ours is the plain
  ratio on identical task sets (documented in wis.py).
- `epi/replication.py` is integration-tested only (pragma: no cover with rationale).
- **Deliberately deferred to Phase D** (state-the-gap): log1p scoring scale (official
  pipeline scores natural AND log(x+1); needed for official-comparable reports, not
  for the Phase B done condition). Two replica divergences proven unreachable in the
  2024-25 backtest, documented by the adversarial pass: anchor value is window- but
  not pause-filtered (only matters for mid-pause reference dates); h=-1 uses
  per-location last value vs official's global-max-date slice (equivalent 27/27
  dates this season). Revisit if Phase D backtests pre-2024-25 seasons.
- Metaculus thread still parked; ai-use SHA pin + pre-commit still Phase G items.
