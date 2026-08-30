# Prime Radiant — Calibrated Forecasting Bot

Calibrated LLM forecasting bot for Metaculus binary questions: retrieval → ensemble →
aggregation, every forecast logged, scored with Brier + reliability diagram. These
instructions are agent-agnostic: any harness working here follows them.

## Constraints (non-negotiable)

1. **Repo location:** `~/src/github.com/JeremyGracey-AI/prime-radiant`. Never create
   folders in `~/GitHub`, `~/Desktop`, or home root.
2. **Toolchain:** Python 3.12 (pinned), `uv` for env/deps, Ruff + Pyright + pytest as the
   validation layer. Run all three before declaring any phase done:
   `uv run ruff check . && uv run pyright && uv run pytest`
3. **Secrets in `.env` only** (`ANTHROPIC_API_KEY`, `METACULUS_TOKEN`, news API key).
   `.env` is gitignored. Never print keys, never commit them.
4. **Cost caps:** hard per-question budget (config `per_question_budget_usd`, default
   $0.25) and per-run cap (`per_run_budget_usd`). Log token spend on every run.
5. **Leakage guards:** never retrieve or reason on any source dated after a backtest
   question's freeze date. News retrieval is date-filtered to the question window.
6. **Flag destructive or irreversible actions** (force-push, deleting data, live
   submissions) before doing them. No live submissions before Phase D is done and
   Jeremy explicitly says go.
7. **Scope:** Phase 2/3 ideas (ABM, generative agents) go to `NOTES/parking-lot.md`,
   not into code.

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

## Architecture

Metaculus fetch → query generation → date-filtered news retrieval → relevance filter →
inside/outside-view reasoning → K samples (K=5) → trimmed mean → extremize → calibrate
(Platt, once ≥30 resolved) → submit (live) or record (dry-run) → log everything.

Storage: DuckDB (`data/forecasts.duckdb`) + JSONL log per run. Everything reproducible
from logs.

## Composition (name the parts)

- **Metaculus plumbing:** `forecasting-tools` package, isolated behind
  `src/prime_radiant/metaculus.py`. Parsing (raw post JSON → our `Question` model) is
  ours and pure; the dependency is swappable at that interface.
- **Config:** `src/prime_radiant/config.py` (pydantic-settings, loads `.env`).
- **Tests:** fixtures under `tests/fixtures/` are recorded/representative API shapes;
  unit tests never need network or tokens.
