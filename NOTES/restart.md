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
- done: fetch call path executed once and verified to the auth boundary — fails with
  `ValueError: METACULUS_TOKEN ... not set`, i.e. filter construction, kwargs, and
  asyncio wrapping all run (2026-08-30)
- NOT done: full live fetch of 5 open questions — **no METACULUS_TOKEN on this machine**
  (checked `~/.zsh_secrets`); Metaculus API 403s unauthenticated reads (verified
  2026-08-30). Jeremy: create a token at metaculus.com and add to `.env`.

## Next step

Jeremy adds `METACULUS_TOKEN` to `.env`; run the live smoke fetch
(`uv run python -c "from prime_radiant.metaculus import fetch_open_binary_questions; print(fetch_open_binary_questions(5))"`),
re-record `tests/fixtures/posts_response.json` from a real response (fixture is
currently hand-built from forecasting-tools' parser — re-recording catches schema
drift), then start Phase B (retrieval + date-filter leakage test).

## Verify

`uv run ruff check . && uv run pyright && uv run pytest`

## Blockers

- METACULUS_TOKEN absent → live fetch untested (unit tests don't need it).
- News API decision deferred to Phase B: AskNews if tournament-provided, else Serper/NewsAPI.

## Notes / gaps (per house rules: state the gap)

- Brief says "follow the clean-code skill" — no skill by that name exists on this machine;
  stand-in: superpowers TDD + verification skills, Ruff strict-ish lint set, Pyright.
- `forecasting-tools` is heavy (streamlit/litellm in its tree). Accepted for the time-box;
  isolated behind `metaculus.py` (parse is ours, pure); swap path to thin httpx client
  pre-declared if it fights back. Its `get_questions_matching_filter` is async — wrapped
  in `asyncio.run` for now.
- Metaculus legacy `api2` endpoint is dead (403); current API is `/api/posts/` and
  requires auth even for reads.
