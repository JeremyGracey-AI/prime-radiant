# Current task

Phase 2 (FluSight epi forecaster) — Phase B: Scorer + baselines. Brief: `HANDOFF_PHASE2.md`.

## Goal

`eval/wis.py`, FluSight-baseline replica, seasonal-naive, hubverse formatter/validator.
Done = our WIS scores the official FluSight-baseline (S3) and our replica within
tolerance of each other on 2024-25; golden submission file committed.

## Current state

- done: `eval/wis.py` (pinball formulation, WIS = 2×mean pinball; scoringutils-convention
  decomposition; inclusive 50/95 coverage; relative WIS) — TDD'd from the hand-computed
  16/3 example out of Bracher et al.'s own algebra
- done: `eval/scoring.py` (frame-level per-task scoring, NA-truth dropped)
- done: `epi/models/baseline.py` — replica of epipredict::cdc_baseline_forecaster
  (verified from R source): deterministic type-7 quantile grid, pause-excluded
  7-day-join diffs, cumulative shuffled convolution at horizons 1-3, floor/ceil
  rounding; own seeded numpy RNG keyed on reference_date. `epi/models/seasonal.py`
  (reference-only). `epi/models/postprocess.py` shared rounding.
- done: `epi/submission/format.py` + `validate.py` (live tasks.json cross-check;
  drift fails loudly). `epi/data/benchmarks.py` (anonymous S3, parquet-only mirror,
  normalizes round_id/model_id extras).
- done: `epi/replication.py` — **vintage fingerprinting**: official h=-1 rows identify
  the exact vintage the official Wednesday run saw; replica fed that vintage.
- **DONE CONDITION RESULT (2024-25, 27 weeks, 5,724 scored tasks, horizons 0-3):**
  replica/official relative WIS = **0.999989** (mean 263.126 vs 263.129) — see
  `tests/golden/wis_baseline.json`. Horizon-0 values match exactly except rare ±1
  from cross-language float rounding (R vs numpy ~1e-12 at ceil/floor boundaries;
  diagnosed, documented in the integration test; ≤0.5% rate asserted).
- done: golden `tests/golden/2024-11-23-prime-radiant-replica.csv` committed and
  byte-reproduced by `tests/integration/test_golden.py` (cross-session determinism).
- done: hypothesis property — arbitrary histories through replica+formatter always
  pass SubmissionSchema. 100 offline tests, cov 95.8%; 5 integration tests green.
- done: adversarial verification (4 agents). REPLICA CLAIM SURVIVED emphatically:
  constants empirically pinned (window 2022-08-06 + pause exclusion verified against
  the archived 2024-25 R script AND by perturbation — wrong constants break 500+
  cells/week); fingerprint unambiguous on all 27 dates; h=-1 exact 32,913/32,913;
  full-season h0 sweep 99.88% exact, nothing beyond +-1. WIS VALIDATION REFUTED and
  fixed (commit follows): old _check_symmetric had a tautological condition and
  missed below-0.5/even/crossed/boundary level sets — rewritten with 9 new rejection
  tests; validator now tested against MUTATED tasks.json (hub-side drift), wraps
  structural KeyError, searches all rounds; golden compare is check_exact.

## Next step

Phase C: LightGBM quantile model (lag/diff/seasonal features), monotone/non-negative/
integer postprocessing, per-quantile-median ensemble with the baseline replica.
Done gate: relative WIS < 1.0 vs FluSight-baseline on >=2 retrospective seasons at
horizons 0-3, computed on vintage data. If not: fix features before adding models.

## Verify

`make check` (offline) · `make test-integration` (network; ~40s warm)

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
