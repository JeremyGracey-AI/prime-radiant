# Prime Radiant — Calibrated Forecasting

Two forecasting threads share this repo and a calibration thesis. These instructions are
agent-agnostic: any harness working here follows them.

- **Phase 1 — Metaculus bot** (`src/prime_radiant/metaculus.py`, `config.py`): LLM
  retrieval → ensemble → aggregation on binary questions, scored with Brier.
  Status: its Phase A (client) is done; retrieval onward is **parked** — see
  `NOTES/restart.md`.
- **Phase 2 — FluSight epi forecaster** (`src/prime_radiant/epi/`, shared scoring in
  `src/prime_radiant/eval/`): CDC FluSight quantile forecasts (WIS-scored) for weekly
  confirmed-flu hospital admissions. Pure statistical pipeline — **no LLM calls**.
  Brief: `HANDOFF_PHASE2.md` (authoritative for epi work).

## Constraints (non-negotiable)

1. **Repo location:** `~/src/github.com/JeremyGracey-AI/prime-radiant`. Never create
   folders in `~/GitHub`, `~/Desktop`, or home root.
2. **Toolchain:** Python ≥3.11 (`requires-python`), 3.12 pinned locally, 3.11–3.13 CI
   matrix. `uv` for env/deps (`uv.lock` committed). Gate before declaring any phase done:
   `uv run ruff check . && uv run ruff format --check . && uv run pyright &&
   uv run pytest -q -m "not integration" --cov=prime_radiant --cov-fail-under=85`
   (offline; integration tests run separately: `make test-integration`, needs network)
3. **Secrets in `.env` only** (`ANTHROPIC_API_KEY`, `METACULUS_TOKEN`, news API key —
   all Metaculus-thread; **epi data needs no keys**). `.env` is gitignored. Never print
   keys, never commit them.
4. **Cost caps (Metaculus thread):** per-question budget (config
   `per_question_budget_usd`, default $0.25) and per-run cap. The epi thread costs ≈ $0
   by design — keep it that way (CPU only, no paid APIs).
5. **Leakage/vintage discipline (both threads):** never train, retrieve, or score on
   data dated after the forecast origin. For epi backtests: vintages only, never the
   latest revision for historical scoring. This is a **tested invariant**, not a comment.
6. **Flag destructive or irreversible actions** (force-push, deleting data, live
   submissions). Metaculus: no live submission before its Phase D + explicit go.
   FluSight: no PR against `cdcepi/FluSight-forecast-hub` without `LIVE=1` **and**
   explicit go from Jeremy.
7. **Scope:** Phase 2 = the FluSight epi forecaster and is sanctioned work. Still
   parked in `NOTES/parking-lot.md`: ABM, generative agents, rate-change target,
   ED-visit target, sample trajectories, RSV hub, Scenario Modeling Hub demo.

## House style

Copied from the Aug 2026 GitHub audit (see `HANDOFF_PHASE2.md` table): hatchling build,
PEP 735 `[dependency-groups]`, ruff line-length 100 + `E F W I UP B SIM`, pyright basic,
Makefile targets `install-dev test lint typecheck check`. Where audit sources conflict,
the uv+pyright pattern (governance-drift-researcher) wins over pip+mypy. Every
dependency version cap gets a why-comment. Test markers: `unit | integration |
contract | e2e` — unit/contract run offline (fixtures + cassettes); only
`integration` touches network or the real hub clone.

## Restart notes (mandatory)

Maintain `NOTES/restart.md` and update it at the end of every session:

```md
# Current task
## Goal
## Current state
- done / done / in progress
## Next step
<one action>
## Verify
<command>
## Blockers
```

## Composition (name the parts)

- **Metaculus plumbing:** `forecasting-tools`, isolated behind `metaculus.py`; parsing
  is ours and pure; swappable at that interface.
- **FluSight data:** hub `target-data/` via blobless+sparse local clone (gitignored
  `data/hub/`) — its git history IS the vintage store; NHSN Socrata `ua7e-t2fy`
  (final) / `mpgq-jmmr` (preliminary), anonymous.
- **Contracts:** pandera schemas at every stage boundary (`epi/schemas.py`);
  hypothesis property tests for invariants (quantile monotonicity, as-of discipline,
  date arithmetic).
- **Config:** `config.py` (pydantic-settings, loads `.env`).
- **Storage:** DuckDB over Parquet in gitignored `data/`; committed outputs only in
  `reports/` (PNG/CSV summaries) and `tests/golden/`.
