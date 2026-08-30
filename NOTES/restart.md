# Current task

Phase A — Scaffold (from the Prime Radiant Phase 1 handoff brief).

## Goal

Repo scaffold at canonical path + Metaculus client fetching open binary questions,
validated by Ruff + Pyright + pytest.

## Current state

- done: repo at `~/src/github.com/JeremyGracey-AI/prime-radiant`, git init, `.gitignore`
  (`.env`, `data/`) before first commit
- done: uv project, Python 3.12 pinned, deps (`forecasting-tools` + direct `pydantic`,
  `pydantic-settings`, `python-dotenv`; dev: pytest/ruff/pyright)
- done: `config.py` (cost caps: per-question $0.25, per-run $2.50), `metaculus.py`
  (pure `parse_binary_question` + thin async-wrapped fetch via forecasting-tools)
- done: 4 tests green against recorded-shape fixture; Ruff + Pyright clean
- done: live smoke fetch — 5 real open binary questions fetched and parsed end-to-end
  with Jeremy's METACULUS_TOKEN (2026-08-30 PM)
- done: `tests/fixtures/posts_response.json` re-recorded from live API responses
  (binary post 45207 + a real multiple_choice post; account-specific `my_forecasts`
  redacted). Tests updated to recorded values; all green.
- Phase A fully done: `uv run ruff check . && uv run pyright && uv run pytest` all clean.

## Next step

Start Phase B (retrieval): query generation + date-filtered news fetch + relevance
filter, with an explicit leakage unit test (post-cutoff article must be rejected).
First task: verify whether tournament enrollment provides AskNews credentials; else
get a free Serper key (serper.dev) for `NEWS_API_KEY`.

## Verify

`uv run ruff check . && uv run pyright && uv run pytest`

## Blockers

- None for Phase A.
- News API decision deferred to Phase B: AskNews if tournament-provided, else Serper/NewsAPI
  (`NEWS_API_KEY` in `.env` is intentionally empty until then).
- forecasting-tools does NOT auto-load `.env`: callers must run python-dotenv's
  `load_dotenv()` first (the Phase C run module should own this).

## Notes / gaps (per house rules: state the gap)

- Brief says "follow the clean-code skill" — no skill by that name exists on this machine;
  stand-in: superpowers TDD + verification skills, Ruff strict-ish lint set, Pyright.
- `forecasting-tools` is heavy (streamlit/litellm in its tree). Accepted for the time-box;
  isolated behind `metaculus.py` (parse is ours, pure); swap path to thin httpx client
  pre-declared if it fights back. Its `get_questions_matching_filter` is async — wrapped
  in `asyncio.run` for now.
- Metaculus legacy `api2` endpoint is dead (403); current API is `/api/posts/` and
  requires auth even for reads.
