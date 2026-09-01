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
- done: Phase E adversarial workflow (4 agents). Live-gates SURVIVED (five
  independent gates verified against live GitHub state: sole-admin repo, zero
  secrets/variables/environments, boolean-input semantics doc-confirmed,
  contents:read token, exit-1 step with no submission code). Submission validity
  SURVIVED (every hubValidations check replicated against the LIVE hub config;
  magnitudes sane vs official baseline for the same round; zero fixture drift).
  Test-honesty PARTIALLY REFUTED and fixed: exact-conjunction assertion replaces
  substring checks (the ||-compound mutant passed all 7 old tests; now fails —
  verified empirically), counts_lt_popn boundary tested at value == population
  (>-mutant killed; our >= matches hubValidations' strict `<`), raw-float writer
  test kills the astype mutant. Hardened from findings: dispatch inputs reach
  shell via env indirection, persist-credentials false, metadata pyproject path
  fixed (was dead code), writer refuses multi-reference-date frames.
- **CI re-proof on the hardened workflow**: run 33458426164 — success; dry-run
  green, live-submit SKIPPED, submission artifact 19,900 bytes.
- Accepted as-is (refuter-noted): validate_submission checks the subset
  direction only for task ids; if the hub ever moves a task id to 'required',
  add the completeness direction (moot today: every task id is optional, and
  the 23 quantile levels ARE checked as strict set equality).
- Process note (recorded): one commit slipped past lint because a gate chain
  piped `make check` through tail (pipeline exit = tail's); fixed in the next
  commit with the gate run unpiped. Gate commands in future sessions: never
  pipe the gate command itself.

## Next step

Phase F (dashboard): Gradio app — US choropleth of predicted 3-week change,
per-state fan chart with observed history, reliability plot, model-vs-baseline
table; space-deploy.yml pushes to HF Space jeremygracey-ai/prime-radiant
(CPU-basic; secrets only via Space settings). New plan-mode session with
verification workflow first.

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
