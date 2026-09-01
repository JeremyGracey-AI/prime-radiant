# Current task

Phase 2 (FluSight epi forecaster) — Phase E: Submission automation.
Brief: `HANDOFF_PHASE2.md`.

## Goal

weekly-forecast.yml (cron + dispatch -> fetch -> forecast -> validate -> file ->
artifact); PR step inert without LIVE gates; metadata.py renders the registration
YAML. Done = CI dry run emits a validating file; PR step skipped without LIVE.

## Current state

- **DONE CONDITION MET IN CI**: run 33456866973
  (https://github.com/JeremyGracey-AI/prime-radiant/actions/runs/33456866973)
  conclusion=success; dry-run job green on a cold runner (hub clone -> forecast
  -> validate -> artifact "submission", 19,900 bytes); live-submit job
  conclusion=SKIPPED — the semantic proof of the gates.
- done: epi/cli.py (`prime-radiant epi forecast|validate`); auto reference date =
  latest enumerated round <= live Saturday with guard-passing vintage (clamped;
  guard untouched; today selects 2026-05-30). Submitted model = ENSEMBLE.
- done: submission/write.py (hub CSV conventions, TDD); validate gains the hub's
  counts_lt_popn check (recon caught we lacked it).
- done: submission/metadata.py — JGracey-prime_radiant YAML validated against the
  RECORDED hub schema; designated_model=true per approved plan (flip before the
  registration PR for soft launch). Registration/fork/PAT are go-live actions:
  NOT executed; see NOTES/go-live-runbook.md.
- done: weekly-forecast.yml — SHA-pinned, permissions contents:read, concurrency,
  timeouts, cron 22:17 UTC Tue; live job triple-gated + secret-gated + exits 1
  loudly until go-live. Workflow-honesty test enforces statically.
- 181 offline tests (cov 93.68%) + 8 integration green.
- NOT yet run: Phase E adversarial workflow (next before declaring done).

## Next step

Phase E adversarial verification; then Phase F (Gradio dashboard on HF Spaces).

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
